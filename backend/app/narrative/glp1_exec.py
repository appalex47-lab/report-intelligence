"""Resumen ejecutivo y recomendaciones de GLP-1 (misma estructura que AETOPS: dónde estamos, descubrimientos, qué hacer).

Todo sale de reglas explícitas sobre cifras validadas; los impactos son ESCENARIOS con su supuesto a la vista, no pronósticos.
Las coincidencias no se presentan como causas: cuando los datos solo muestran una coincidencia, la acción es revisar/validar.
"""
from __future__ import annotations

from decimal import Decimal

from ..models import GBlock, GRow, Period, PeriodRow, Value
from ..calc import indicators as ind
from . import insights as I
from .aetops import ND, count, money, pct_d, pp_abs
from .executive import PRIO, Executive, Rec, prio_of
from .glp1 import cur_label, dl, move, pct2, prev_label, short, sx, v
from .rules import RULES, NarrativeRules
from .targets import Attainment, status_of
from .writer import Para, para


def attainment_glp1(blocks: dict[str, GBlock], targets, rules: NarrativeRules = RULES) -> list[Attainment]:
    """Meta general opcional de GLP-1 (venta del periodo ÷ meta)."""
    pano = blocks.get("panorama")
    if targets is None or targets.total is None or not pano:
        return []
    actual = pano.rows[0].values["monto"].v
    if actual is None or not targets.total:
        return []
    pct = actual / targets.total
    return [Attainment("TOTAL", actual, targets.total, pct, actual - targets.total, status_of(pct, rules))]


def _chg(a: Value | None, b: Value | None, tag: str) -> Decimal | None:
    if a is None or b is None:
        return None
    return ind.pct_change(a, b, tag).v


def build_executive_glp1(blocks: dict[str, GBlock], funnel: GBlock | None, period: Period, rules: NarrativeRules = RULES,
                         att: list[Attainment] | None = None) -> Executive:
    pano = blocks.get("panorama")
    if not pano:
        return Executive()
    P = pano.rows[0].values
    sales = P["monto"].v
    if not sales:
        return Executive()
    cur, prev = cur_label(period), prev_label(period)
    ex = Executive()
    D: list[tuple[Decimal, Para]] = []
    R: list[Rec] = []
    d_prev = {k: _chg(P.get(k), P.get(k + "_prev"), k) for k in ("monto", "pedidos", "pacientes", "ticket", "pacientes_nuevos")}
    d_yoy = {k: _chg(P.get(k), P.get(k + "_yoy"), k) for k in ("monto", "pedidos", "pacientes", "ticket", "pacientes_nuevos")}

    # ------------------------------------------------------------------ dónde estamos
    base = "_yoy" if "monto_yoy" in P else "_prev" if "monto_prev" in P else None
    dec = None
    if base:
        mk = lambda suf: PeriodRow("", {k: P[k + suf] for k in ("monto", "piezas", "pacientes") if k + suf in P})   # noqa: E731
        dec = I.decompose_sales(mk(base), mk(""), rules)
    yoy_txt = (lambda w: f" y {w.n(pct_d(d_yoy['monto']))} vs el mismo periodo del año anterior") if d_yoy["monto"] is not None else (lambda w: "")
    who = ""
    if dec:
        who = ("volumen" if dec.volume >= 0.6 else "el valor por pieza" if dec.price >= 0.6 else "una combinación de volumen y valor por pieza")
    cmp_lbl = "el mismo periodo del año anterior" if base == "_yoy" else prev
    health = para("interpretacion" if dec else "hecho", lambda w: (
        f"{w.t(cur.capitalize())} cierra con una venta de {w.n(money(sales))}, {w.n(pct_d(d_prev['monto']))} vs {w.t(prev)}{yoy_txt(w)}; "
        f"{w.n(count(P['pedidos'].v))} pedidos, {w.n(count(P['pacientes'].v))} pacientes y ticket promedio de {w.n(money(P['ticket'].v))}"
        + (f". El cambio contra {cmp_lbl} se explica principalmente por {who} ({w.n(pct_d(Decimal(str(round(dec.volume, 4))), False))} del cambio)." if dec else ".")),
        0, basis=("Venta = Pacientes × (Piezas/Paciente) × (Venta/Pieza); aporte = ln(factor₁/factor₀) ÷ ln(venta₁/venta₀)" if dec else ""))
    D.append((Decimal(10), health))
    tot_att = next((a for a in (att or []) if a.name == "TOTAL"), None)
    if tot_att:
        D.append((Decimal(9), para("hecho", lambda w: (
            f"La venta alcanza {w.n(pct_d(tot_att.pct, False))} de la meta ({w.n(money(tot_att.target))}; {w.n(money(tot_att.gap, True))})."), 0,
            evidence=["metas"])))
        if tot_att.status != "cumple":
            sc = abs(tot_att.gap) / sales * rules.weight("meta")
            R.append(Rec(prio_of(sc, rules), sc, "Revisar el avance contra la meta", para("recomendacion", lambda w: (
                f"{w.b('Revisar el avance contra la meta')}: la venta queda en {w.n(pct_d(tot_att.pct, False))} de la meta "
                f"({w.n(money(tot_att.gap, True))}). Seguimiento: venta vs meta cada mes."), 3, basis="venta < 100 % de la meta")))

    # ------------------------------------------------------------------ embudo
    F = {r.key: r for r in funnel.rows} if funnel else {}
    if F and "vistas_producto" in P and P["vistas_producto"].v:
        conv = P["compras"].v / P["vistas_producto"].v if P["compras"].v is not None else None
        conv_prev = (P["compras_prev"].v / P["vistas_producto_prev"].v) if "compras_prev" in P and P.get("vistas_producto_prev") and P["vistas_producto_prev"].v and P["compras_prev"].v is not None else None
        if conv is not None:
            def f_para(w):
                s = (f"El embudo convierte {w.n(count(P['vistas_producto'].v))} vistas de producto en {w.n(count(P['compras'].v))} compras "
                     f"({w.n(pct2(conv))})")
                if conv_prev is not None:
                    s += f", {w.n(pp_abs(conv - conv_prev))} {'más' if conv >= conv_prev else 'menos'} que {w.t(prev)} ({w.n(pct2(conv_prev))})"
                return s + f"; los carritos abandonados suman {w.n(count(P['carritos_abandonados'].v))}."
            D.append((abs(conv - conv_prev) * Decimal(10) if conv_prev is not None else Decimal("0.02"), para("hecho", f_para, 1, evidence=["embudo"])))
        aband, tick = P["carritos_abandonados"].v, P["ticket"].v
        if aband and tick:
            amt = aband * rules.cart_recovery_scenario * tick
            sc = amt / sales * rules.weight("proteger")
            R.append(Rec(prio_of(sc, rules), sc, "Reducir el abandono de carrito", para("recomendacion", lambda w: (
                f"{w.b('Reducir el abandono de carrito')}: hay {w.n(count(aband))} carritos abandonados. Escenario ilustrativo: cerrar "
                f"{w.n(pct_d(rules.cart_recovery_scenario, False))} de ellos con el ticket promedio equivale a {w.n(money(amt))} "
                f"({w.n(pct_d(amt / sales, False))} de la venta). Seguimiento: carritos abandonados y conversión final."), 1,
                basis="carritos abandonados × 10 % × ticket promedio; escenario ilustrativo, no pronóstico")))

    # ------------------------------------------------------------------ concentración y movimientos
    prods = blocks.get("productos")
    if prods and prods.rows:
        t = prods.rows[0]
        if t.share and t.share.v is not None and t.share.v >= rules.concentration_share:
            D.append((t.share.v * Decimal("0.1"), para("hecho", lambda w: (
                f"{w.b(short(t.key))} concentra {w.n(pct_d(t.share.v, False))} de la venta ({w.n(money(v(t, 'monto')))})."), 1)))
            sc = t.share.v * Decimal("0.1") * rules.weight("proteger")
            R.append(Rec(prio_of(sc, rules), sc, f"Proteger {short(t.key, 30)}", para("recomendacion", lambda w: (
                f"{w.b('Proteger ' + short(t.key, 30))}: concentra {w.n(pct_d(t.share.v, False))} de la venta; asegurar abasto y continuidad. "
                f"Seguimiento: venta y pacientes de ese producto cada mes."), 3, basis="producto con ≥ 50 % de la venta (concentración)")))
    seg_candidates = []
    for name, label, key, as_sex in (("sexo", "sexo", "visitas", True), ("edad", "edad", "visitas", False), ("dispositivo", "dispositivo", "visitas", False),
                                     ("region", "región", "monto", False), ("pago", "forma de pago", "monto", False), ("entrega", "modo de entrega", "monto", False)):
        b = blocks.get(name)
        if not b:
            continue
        for r in b.rows:
            if r.share and r.share.v and dl(r) is not None and r.share.v >= Decimal("0.10"):
                seg_candidates.append((r.share.v * abs(dl(r)), dl(r), label, sx(r.key) if as_sex else r.key, r, key))
    drops = sorted((c for c in seg_candidates if c[1] <= -rules.relevance), key=lambda c: -c[0])
    rises = sorted((c for c in seg_candidates if c[1] >= rules.relevance), key=lambda c: -c[0])
    for sc, d, label, nm, r, key in drops[:2]:
        D.append((sc, para("hecho", lambda w: (
            f"{w.b(nm.capitalize() if label != 'región' else nm.capitalize())} ({w.t(label)}) cae {w.n(pct_d(abs(d), False))} vs {w.t(prev)} "
            f"con {w.n(pct_d(r.share.v, False))} de {'las visitas' if key == 'visitas' else 'la venta'}."), 2)))
    if drops:
        sc, d, label, nm, r, key = drops[0]
        scr = sc * rules.weight("validar")
        R.append(Rec(prio_of(scr, rules), scr, f"Validar la caída en {nm} ({label})", para("recomendacion", lambda w: (
            f"{w.b('Validar la caída en ' + nm + ' (' + label + ')')}: cae {w.n(pct_d(abs(d), False))} vs {w.t(prev)} con {w.n(pct_d(r.share.v, False))} de "
            f"{'las visitas' if key == 'visitas' else 'la venta'}. Seguimiento: {w.t('visitas' if key == 'visitas' else 'venta')} de ese segmento cada mes."), 3,
            basis="segmento con ≥ 10 % de participación y caída ≥ 5 %")))
    for sc, d, label, nm, r, key in rises[:1]:
        D.append((sc, para("hecho", lambda w: (
            f"{w.b(nm.capitalize())} ({w.t(label)}) sube {w.n(pct_d(d, False))} vs {w.t(prev)} con {w.n(pct_d(r.share.v, False))} de "
            f"{'las visitas' if key == 'visitas' else 'la venta'}."), 3)))

    # pacientes nuevos
    if P.get("pacientes_nuevos") and P["pacientes_nuevos"].v is not None and P["pacientes"].v:
        nuevos = P["pacientes_nuevos"].v / P["pacientes"].v
        D.append((Decimal("0.01"), para("hecho", lambda w: (
            f"{w.n(count(P['pacientes_nuevos'].v))} pacientes son nuevos ({w.n(pct_d(nuevos, False))} de los pacientes del periodo"
            + (f"; {w.n(pct_d(d_prev['pacientes_nuevos']))} vs {w.t(prev)}" if d_prev['pacientes_nuevos'] is not None else "") + ")."), 4)))

    # ------------------------------------------------------------------ negados
    neg = blocks.get("negados")
    if neg and neg.rows:
        tot = sum((v(r, "monto_negado") or Decimal(0) for r in neg.rows), Decimal(0))
        ratio = tot / sales
        t = neg.rows[0]
        D.append((ratio, para("hecho", lambda w: (
            f"Los negados suman {w.n(money(tot))}, equivalente a {w.n(pct_d(ratio, False))} de la venta, concentrados en "
            f"{w.b(short(t.key))} ({w.n(pct_d(t.share.v, False))})."), 1)))
        if ratio >= rules.materiality:
            rec_amt = tot * rules.recovery_scenario
            sc = ratio * rules.weight("abasto")
            R.append(Rec(prio_of(sc, rules), sc, "Priorizar el abasto de los productos más negados", para("recomendacion", lambda w: (
                f"{w.b('Priorizar el abasto de los productos más negados')} ({w.b(short(t.key))}): {w.n(money(tot))} ({w.n(pct_d(ratio, False))} de la venta) "
                f"corresponden a productos sin stock que se negaron a la venta. Escenario ilustrativo: recuperar {w.n(pct_d(rules.recovery_scenario, False))} "
                f"equivale a {w.n(money(rec_amt))} ({w.n(pct_d(rec_amt / sales, False))} de la venta). Seguimiento: monto y pedidos negados."), 1,
                basis="negado = producto sin stock negado a la venta (definición del negocio); el escenario es ilustrativo, no pronóstico")))
        # coincidencia: producto que baja y aparece en negados (por nombre normalizado)
        if prods:
            nk = {r.key.strip().lower(): r for r in neg.rows}
            cross = [r for r in prods.rows if dl(r) is not None and dl(r) <= -rules.relevance and r.key.strip().lower() in nk]
            if cross:
                c = cross[0]
                sc = (abs((v(c, 'monto') or 0) * dl(c)) + (v(nk[c.key.strip().lower()], 'monto_negado') or 0)) / sales * rules.weight("disponibilidad")
                R.append(Rec(prio_of(sc, rules), sc, f"Revisar la disponibilidad de {short(c.key, 30)}", para("recomendacion", lambda w: (
                    f"{w.b('Revisar la disponibilidad de ' + short(c.key, 30))}: baja {w.n(pct_d(dl(c)))} y acumula "
                    f"{w.n(money(v(nk[c.key.strip().lower()], 'monto_negado')))} en negados. Seguimiento: negados y venta de ese producto."), 3,
                    basis="el producto aparece en caídas y en negados (coincidencia, no causa)")))

    # ------------------------------------------------------------------ selección y armado (igual que AETOPS)
    D.sort(key=lambda t: t[0], reverse=True)
    R.sort(key=lambda r: r.score, reverse=True)
    ex.descubrimientos = D
    ex.recs = R[:rules.max_recommendations]
    for i, r in enumerate(ex.recs, 1):
        r.para.text = f"**{i}. [{PRIO[r.prio]}]** {r.para.text}"
        r.para.priority = 0 if i <= 3 else 3
        r.para.nums.update({str(i)})
        ex.recomendaciones.append(r.para)
    head = lambda t: para("hecho", lambda w: f"**{t}**", 0)                    # noqa: E731
    resumen = [head("Dónde estamos"), health]
    meta_p = next((p for s, p in D if s == 9), None)
    if meta_p:
        resumen.append(meta_p)
    resumen.append(head("Descubrimientos del periodo"))
    for k, p in enumerate([p for s, p in D if s not in (9, 10)][:4]):
        resumen.append(Para("• " + p.text, p.kind, 1 + k, p.basis, p.evidence, set(p.nums)))
    if ex.recs:
        resumen.append(head("Qué hacer"))
        for k, r in enumerate(ex.recs[:3]):
            resumen.append(para("recomendacion", lambda w: f"• **[{PRIO[r.prio]}]** {w.t(r.action)}.", 1 + k, basis=r.para.basis))
    ex.resumen = resumen
    return ex
