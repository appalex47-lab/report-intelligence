"""Descubrimientos y recomendaciones del periodo (resumen ejecutivo y diapositiva de recomendaciones).

Todo sale de reglas explícitas sobre cifras ya validadas (docs/OBJETIVO_Y_NARRATIVA.md §9):
  descubrimiento = hallazgo con puntaje de materialidad (qué tan grande es frente a la venta total);
  recomendación  = acción sugerida + evidencia + impacto en ESCENARIO (nunca pronóstico) + métrica de seguimiento.
No se atribuyen causas: cuando los datos solo muestran una coincidencia, la acción es "revisar/validar".
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal

from ..models import Period
from ..pipeline import Result
from . import insights as I
from .aetops import KIND, labels_for_products, money, pct_d, pct_of, pp_abs, val
from .rules import RULES, NarrativeRules
from .writer import Para, para

PRIO = {"alta": "ALTA", "media": "MEDIA", "baja": "BAJA"}


@dataclass
class Rec:
    prio: str                       # alta | media | baja
    score: Decimal
    action: str                     # frase corta para el resumen
    para: Para                      # texto completo (con cifras registradas)


@dataclass
class Executive:
    resumen: list[Para] = field(default_factory=list)
    recomendaciones: list[Para] = field(default_factory=list)
    recs: list[Rec] = field(default_factory=list)
    descubrimientos: list[tuple[Decimal, Para]] = field(default_factory=list)


def product_key(name: str) -> tuple:
    """Clave para reconocer un mismo producto entre listas con rótulos distintos ('PAMORELIN 22.5 MG SUS…')."""
    toks = re.findall(r"[A-Z0-9][A-Z0-9.\-]*", name.upper())
    nums = tuple(sorted(t for t in toks[1:4] if re.fullmatch(r"\d+(\.\d+)?", t)))
    return (toks[0] if toks else "", nums)


def prio_of(score: Decimal, rules: NarrativeRules) -> str:
    return "alta" if score >= rules.prio_high else "media" if score >= rules.prio_mid else "baja"


def build_executive(result: Result, period: Period, rules: NarrativeRules = RULES) -> Executive:
    T = result.tables
    py = T["aetops.panorama.yoy"].groups[0]
    pm = T["aetops.panorama.mom"].groups[0] if "aetops.panorama.mom" in T else None
    sales = val(py.current, "monto")
    if not sales:
        return Executive()
    prod = {k: result.products[f"aetops.productos.{k}"].rows for k in ("top", "growth", "decline")}
    names = labels_for_products(prod["top"] + prod["growth"] + prod["decline"])
    alta, neg_prod = result.negados.get("aetops.negados.alta"), result.negados.get("aetops.negados.producto")
    ex = Executive()
    D: list[tuple[Decimal, Para]] = []
    R: list[Rec] = []
    tp, tc = val(py.previous, "monto"), sales
    prev_y = period.prev_year_label

    # ------------------------------------------------------------------ descubrimientos
    dec = I.decompose_sales(py.previous, py.current, rules)
    who = ""
    if dec:
        who = ("volumen" if dec.volume >= 0.6 else "el valor por pieza" if dec.price >= 0.6
               else "una combinación de volumen y valor por pieza")
        vol = Decimal(str(round(dec.volume, 4)))
        mom_part = (lambda w: f" y {w.n(pct_d(pct_of(pm, 'monto')))} vs {w.t(period.previous_month_name)}") if pm else (lambda w: "")
        health = para("interpretacion", lambda w: (
            f"{w.t(period.label.capitalize())} cierra con una venta de {w.n(money(sales))}, {w.n(pct_d(pct_of(py, 'monto')))} "
            f"vs {w.t(prev_y)}{mom_part(w)}; el cambio anual se explica principalmente por {who} "
            f"({w.n(pct_d(vol, False))} del cambio)."), 0,
            basis="Venta = Pacientes × (Piezas/Paciente) × (Venta/Pieza); aporte = ln(factor₁/factor₀) ÷ ln(venta₁/venta₀)")
        D.append((Decimal(10), health))
    press = I.pressures(py, rules)
    if press:
        D.append((abs(press[0][1]) * Decimal("0.3"), para("hecho", lambda w: (
            "La presión del periodo está en " + ", ".join(
                f"{lbl} ({w.n(pct_d(v))})" for lbl, v in press[:3]) + "."), 2)))

    # grupos: concentración, pérdida de participación, valor sobre volumen, mezcla
    for kind, key in (("canal", "aetops.canal.yoy"), ("línea", "aetops.linea.yoy")):
        cs = I.contributions(T[key].groups, tp, tc)
        if not cs:
            continue
        top = max(cs, key=lambda c: c.delta)
        art, plural, otros = KIND[kind]
        if top.share_cur is not None and top.share_cur >= rules.concentration_share:
            D.append((top.share_cur * Decimal("0.1"), para("hecho", lambda w: (
                f"{w.b(top.group.name)} concentra {w.n(pct_d(top.share_cur, False))} de la venta"
                + (f" y aporta {w.n(pct_d(top.share_of_change, False))} del crecimiento" if top.share_of_change else "")
                + "."), 1)))
            line_prods = [r for r in prod["top"] if r.aetop == top.group.name][:2]
            if kind == "línea" and line_prods:
                sc = top.share_cur * Decimal("0.1") * rules.weight("proteger")
                R.append(Rec(prio_of(sc, rules), sc, f"Proteger {top.group.name}", para("recomendacion", lambda w: (
                    f"{w.b('Proteger ' + top.group.name)}: concentra {w.n(pct_d(top.share_cur, False))} de la venta; asegurar "
                    f"abasto y continuidad de sus productos principales ({', '.join(w.b(names[r.producto]) for r in line_prods)}). "
                    f"Seguimiento: venta y pacientes de {w.t(top.group.name)} cada mes."), 3,
                    basis="línea con ≥ 50 % de la venta total (concentración)")))
        elif top.share_of_change is not None and top.delta / sales >= rules.materiality:
            D.append((top.delta / sales, para("hecho", lambda w: (
                f"{w.b(top.group.name)} es {art} que más aporta: {w.n(money(top.delta, True))} "
                f"({w.n(pct_d(top.share_of_change, False))} del avance)."), 2)))
        for c in cs:
            f = I.flags(c, pct_of(py, "monto"), True, rules)
            g = c.group
            mat = abs(c.delta) / sales
            if "crece_menos_que_total" in f and c.pp is not None and c.pp <= -rules.share_loss_pp:
                sc = abs(c.pp)
                D.append((sc, para("hecho", lambda w: (
                    f"{w.b(g.name)} crece {w.n(pct_d(c.pct))} pero cede {w.n(pp_abs(c.pp))} de participación "
                    f"({w.n(pct_d(c.share_prev, False))} → {w.n(pct_d(c.share_cur, False))}): {otros} {plural} crecen más rápido."), 2)))
                sc = sc * rules.weight("investigar")
                R.append(Rec(prio_of(sc, rules), sc, f"Investigar qué limita a {g.name}", para("recomendacion", lambda w: (
                    f"{w.b('Investigar qué limita a ' + g.name)}: crece {w.n(pct_d(c.pct))} pero cede {w.n(pp_abs(c.pp))} de "
                    f"participación; revisar pacientes ({w.n(pct_d(pct_of(g, 'pacientes')))}) y valor por paciente "
                    f"({w.n(pct_d(pct_of(g, 'v_paciente')))}). Seguimiento: share de {w.t(g.name)} y pacientes."), 3,
                    basis="crece menos que el total y su share baja ≥ 5 pp")))
            elif "valor_sobre_volumen" in f and mat >= rules.materiality:
                D.append((mat, para("interpretacion", lambda w: (
                    f"{w.b(g.name)} vende {w.n(pct_d(c.pct))} con pacientes {w.n(pct_d(pct_of(g, 'pacientes')))}: su avance "
                    f"depende del valor por paciente ({w.n(pct_d(pct_of(g, 'v_paciente')))})."), 3, basis="venta ↑ con pacientes ↓")))
                R.append(Rec(prio_of(mat * rules.weight("validar"), rules), mat * rules.weight("validar"), f"Validar la sostenibilidad de {g.name}", para("recomendacion", lambda w: (
                    f"{w.b('Validar la sostenibilidad de ' + g.name)}: el avance depende del valor por paciente; revisar la "
                    f"captación de pacientes ({w.n(pct_d(pct_of(g, 'pacientes')))}). Seguimiento: pacientes por mes."), 3,
                    basis="venta ↑ con pacientes ↓")))
            elif "caida_por_mezcla" in f and mat >= rules.materiality:
                D.append((mat, para("interpretacion", lambda w: (
                    f"{w.b(g.name)} cae {w.n(pct_d(c.pct))} en venta con piezas {w.n(pct_d(pct_of(g, 'piezas')))}: "
                    f"la caída es de valor más que de volumen."), 3, basis="venta ↓ con piezas ≥ 0")))
                R.append(Rec(prio_of(mat * rules.weight("mezcla"), rules), mat * rules.weight("mezcla"), f"Revisar mezcla y precio en {g.name}", para("recomendacion", lambda w: (
                    f"{w.b('Revisar mezcla y precio en ' + g.name)}: venta {w.n(pct_d(c.pct))} con piezas "
                    f"{w.n(pct_d(pct_of(g, 'piezas')))}. Seguimiento: venta por pieza."), 3, basis="venta ↓ con piezas ≥ 0")))

    # productos: mayor movimiento y cruce con negados
    neg_keys = {}
    if neg_prod:
        for r in neg_prod.rows:
            neg_keys.setdefault(product_key(r.name), r)
    falling = [r for r in prod["decline"] + [x for x in prod["top"] if (x.delta.v or 0) < 0]
               if r.delta.v is not None and r.delta.v < 0]
    seen, cross = set(), []
    for r in falling:
        k = product_key(r.producto)
        if k in neg_keys and k not in seen:
            seen.add(k)
            cross.append((r, neg_keys[k]))
    if cross:
        sum_fall = sum((abs(r.delta.v) for r, _ in cross), Decimal(0))
        sum_neg = sum((n.monto.v or Decimal(0) for _, n in cross), Decimal(0))
        sc = (sum_fall + sum_neg) / sales
        D.append((sc, para("hecho", lambda w: (
            "Coinciden caída y negados en " + ", ".join(
                f"{w.b(names[r.producto])} ({w.n(money(r.delta.v, True))}; negados {w.n(money(n.monto.v))})" for r, n in cross[:3]) + "."), 1,
            evidence=[])))
        sc = sc * rules.weight("disponibilidad")
        R.append(Rec(prio_of(sc, rules), sc, "Revisar la disponibilidad de " + ", ".join(names[r.producto] for r, _ in cross[:3]),
                     para("recomendacion", lambda w: (
            f"{w.b('Revisar la disponibilidad de ' + ', '.join(names[r.producto] for r, _ in cross[:3]))}: caen "
            f"{w.n(money(sum_fall))} y acumulan {w.n(money(sum_neg))} en negados. Seguimiento: negados y venta de esos productos."),
            3, basis="el producto aparece en la lista de caídas y en la de negados (coincidencia, no causa)")))
    for key, lead in (("growth", "mayor alza"), ("decline", "mayor caída")):
        rows = prod[key]
        if rows and rows[0].delta.v is not None and abs(rows[0].delta.v) / sales >= rules.materiality:
            D.append((abs(rows[0].delta.v) / sales, para("hecho", lambda w: (
                f"{w.b(names[rows[0].producto])} es la {lead}: {w.n(money(rows[0].delta.v, True))}."), 4)))

    # negados: monto frente a la venta
    if alta and alta.total.v:
        ratio = alta.total.v / sales
        tops = sorted(neg_prod.rows, key=lambda r: r.monto.v or Decimal(0), reverse=True)[:3] if neg_prod else []
        nm = labels_for_products([type("R", (), {"producto": r.name}) for r in tops]) if tops else {}
        lead = max(alta.rows, key=lambda r: r.monto.v or Decimal(0)) if alta.rows else None
        D.append((ratio, para("hecho", lambda w: (
            f"Los negados suman {w.n(money(alta.total.v))}, equivalente a {w.n(pct_d(ratio, False))} de la venta"
            + (f", concentrados en {w.b(lead.name)} ({w.n(pct_d(lead.share.v, False))})" if lead else "") + "."), 1)))
        if ratio >= rules.materiality:
            rec_amt = alta.total.v * rules.recovery_scenario
            R.append(Rec(prio_of(ratio * rules.weight("abasto"), rules), ratio * rules.weight("abasto"), "Priorizar el abasto de los productos más negados", para("recomendacion", lambda w: (
                f"{w.b('Priorizar el abasto de los productos más negados')}"
                + (f" ({', '.join(w.b(nm[r.name]) for r in tops)})" if tops else "")
                + f": {w.n(money(alta.total.v))} ({w.n(pct_d(ratio, False))} de la venta) corresponden a productos sin stock que se negaron a la venta. "
                f"Escenario ilustrativo: recuperar {w.n(pct_d(rules.recovery_scenario, False))} equivale a "
                f"{w.n(money(rec_amt, True))} ({w.n(pct_d(rec_amt / sales, False))} de la venta). "
                f"Seguimiento: monto y pedidos negados."), 1,
                basis="negado = producto sin stock negado a la venta (definición del negocio); el escenario es ilustrativo, no pronóstico")))

    # presión en métricas del panorama
    if press:
        lbl, v = press[0]
        sc = abs(v) * Decimal("0.2") * rules.weight("vigilar")
        R.append(Rec(prio_of(sc, rules), sc, f"Vigilar {lbl}", para("recomendacion", lambda w: (
            f"{w.b('Vigilar ' + lbl)}: {w.n(pct_d(v))} vs {w.t(prev_y)}"
            + (f"; el crecimiento se sostiene por {who}" if who and who != 'el valor por pieza' else "")
            + f". Seguimiento: {w.t(lbl)} cada mes."), 4, basis="métrica del panorama con caída ≥ 5 %")))

    # ------------------------------------------------------------------ selección y armado
    D.sort(key=lambda t: t[0], reverse=True)
    R.sort(key=lambda r: r.score, reverse=True)
    ex.descubrimientos = D
    ex.recs = R[:rules.max_recommendations]
    for i, r in enumerate(ex.recs, 1):
        tag = PRIO[r.prio]
        r.para.text = f"**{i}. [{tag}]** {r.para.text}"
        r.para.priority = 0 if i <= 3 else 3
        r.para.nums.update({str(i)})
        ex.recomendaciones.append(r.para)

    head = lambda t: para("hecho", lambda w: f"**{t}**", 0)                    # noqa: E731
    resumen = [head("Dónde estamos")]
    health = next((p for s, p in D if s == 10), None)
    resumen.append(health or para("info_insuficiente", lambda w: "Sin información suficiente para describir el periodo.", 0))
    resumen.append(head("Descubrimientos del periodo"))
    rest = [p for s, p in D if s != 10][:4]
    for k, p in enumerate(rest):
        q = Para("• " + p.text, p.kind, 1 + k, p.basis, p.evidence, set(p.nums))
        resumen.append(q)
    if ex.recs:
        resumen.append(head("Qué hacer"))
        for k, r in enumerate(ex.recs[:3]):
            resumen.append(para("recomendacion", lambda w: f"• **[{PRIO[r.prio]}]** {w.t(r.action)}.", 1 + k,
                                basis=r.para.basis))
    ex.resumen = resumen
    return ex
