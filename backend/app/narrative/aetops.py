"""Narrativa ejecutiva AETOPS mensual a partir de insights verificables (docs/OBJETIVO_Y_NARRATIVA.md)."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ..format import quantize_half_up
from ..models import Group, Period
from ..pipeline import Result
from . import insights as I
from .rules import RULES, NarrativeRules
from .writer import Para, fit, para, verify_all

ND = "n/d"
KIND = {"canal": ("el canal", "canales", "otros"), "línea": ("la línea", "líneas", "otras"),
        "categoría": ("la categoría", "categorías", "otras")}


@dataclass(frozen=True)
class Box:
    """Capacidad estimada de un cuadro de texto de la plantilla."""
    cpl: int          # caracteres por línea
    lines: int        # líneas disponibles


# ----------------------------------------------------------------------------- formato
def pct_d(d: Decimal | None, sign: bool = True) -> str:
    if d is None:
        return ND
    q = quantize_half_up(d * 100, 0)
    if q == 0:
        return "0%"
    return f"+{q:,.0f}%" if q > 0 and sign else f"{q:,.0f}%"


def pp_s(d: Decimal | None) -> str:
    if d is None:
        return ND
    q = quantize_half_up(d * 100, 0)
    return "0 pp" if q == 0 else (f"+{q:,.0f} pp" if q > 0 else f"{q:,.0f} pp")


def pp_abs(d: Decimal | None) -> str:
    if d is None:
        return ND
    return f"{quantize_half_up(abs(d) * 100, 0):,.0f} pp"


def money(d: Decimal | None, sign: bool = False) -> str:
    if d is None:
        return ND
    a, s = abs(d), "-" if d < 0 else ("+" if sign and d > 0 else "")
    if a >= 1_000_000:
        return f"{s}${quantize_half_up(a / 1_000_000, 2):,.2f} M"
    if a >= 1_000:
        return f"{s}${quantize_half_up(a / 1_000, 1):,.1f} K"
    return f"{s}${quantize_half_up(a, 0):,.0f}"


def count(d: Decimal | None) -> str:
    return ND if d is None else f"{quantize_half_up(d, 0):,.0f}"


def val(row, key):
    x = row.values.get(key)
    return x.v if x is not None else None


def pct_of(g: Group, key: str) -> Decimal | None:
    x = g.pct.get(key)
    return x.v if x is not None else None


def verb(d: Decimal | None, rules: NarrativeRules = RULES) -> str:
    if d is None:
        return "sin dato"
    return "se mantiene estable" if abs(d) < rules.relevance else ("crece" if d > 0 else "baja")


def labels_for_products(rows) -> dict[str, str]:
    """'PROLIA 60MG…' -> 'Prolia'; si dos productos comparten primera palabra se añade la presentación."""
    uniq = {r.producto: r for r in rows}.values()                      # un mismo producto en varias listas no es duplicado
    firsts = [r.producto.split()[0].upper() for r in uniq if r.producto.split()]
    dup = {f for f in firsts if firsts.count(f) > 1}
    out = {}
    for r in rows:
        w = r.producto.split()
        base = "-".join(p.capitalize() for p in w[0].split("-")) if w else r.producto
        if w and w[0].upper() in dup and len(w) > 1 and any(ch.isdigit() for ch in w[1]):
            base += f" {w[1]}"
        out[r.producto] = base
    return out


# ----------------------------------------------------------------------------- 1 · panorama
def s_panorama(yoy: Group, mom: Group | None, period: Period, rules: NarrativeRules) -> list[Para]:
    c = yoy.current.values
    prev_y = period.prev_year_label
    ps: list[Para] = []
    if mom is not None:
        ps.append(para("hecho", lambda w: (
            f"En {w.t(period.label)}, la venta total AETOP llega a {w.n(money(val(yoy.current, 'monto')))}, "
            f"{w.n(pct_d(pct_of(yoy, 'monto')))} vs {w.t(prev_y)} y "
            f"{w.n(pct_d(pct_of(mom, 'monto')))} vs {w.t(period.previous_month_name)}."), 0,
            evidence=[_src(c["monto"])]))
    else:
        ps.append(para("hecho", lambda w: (
            f"En {w.t(period.label)}, la venta total AETOP llega a {w.n(money(val(yoy.current, 'monto')))} y "
            f"{verb(pct_of(yoy, 'monto'), rules)} {w.n(pct_d(pct_of(yoy, 'monto')))} vs {w.t(prev_y)}."), 0,
            evidence=[_src(c["monto"])]))
    ps.append(para("hecho", lambda w: (
        f"En el comparativo anual, pacientes {w.n(pct_d(pct_of(yoy, 'pacientes')))}, piezas "
        f"{w.n(pct_d(pct_of(yoy, 'piezas')))} y pedidos {w.n(pct_d(pct_of(yoy, 'pedidos')))}; el ticket promedio "
        f"{w.n(pct_d(pct_of(yoy, 'ticket')))}."), 1))
    dec = I.decompose_sales(yoy.previous, yoy.current, rules)
    if dec:
        vol, price = Decimal(str(round(dec.volume, 4))), Decimal(str(round(dec.price, 4)))
        if dec.volume >= 0.6:
            lead = "principalmente por volumen"
        elif dec.price >= 0.6:
            lead = "principalmente por el valor por pieza"
        else:
            lead = "por una combinación de volumen y valor por pieza"
        ps.append(para("interpretacion", lambda w: (
            f"El cambio anual en venta se explica {lead}: pacientes y piezas por paciente aportan "
            f"{w.n(pct_d(vol, False))} del cambio y el valor por pieza {w.n(pct_d(price, False))}."), 1,
            basis="Venta = Pacientes × (Piezas/Paciente) × (Venta/Pieza); aporte = ln(factor₁/factor₀) ÷ ln(venta₁/venta₀)"))
    press = I.pressures(yoy, rules)
    if press:
        ps.append(para("hecho", lambda w: (
            "La principal presión se observa en " + ", ".join(
                f"{lbl} ({w.n(pct_d(v))})" for lbl, v in press[:4]) + "."), 1))
    if mom is not None:
        ps.append(para("hecho", lambda w: (
            f"Contra {w.t(period.previous_month_name)}, piezas {w.n(pct_d(pct_of(mom, 'piezas')))}, pacientes "
            f"{w.n(pct_d(pct_of(mom, 'pacientes')))} y pedidos {w.n(pct_d(pct_of(mom, 'pedidos')))}; el avance mensual es "
            f"{_cmp(pct_of(mom, 'monto'), pct_of(yoy, 'monto'))} al anual."), 2))
    py, pm = pct_of(yoy, "productos"), pct_of(yoy, "monto")
    if py is not None and pm is not None:
        less = py < pm
        pmo = pct_of(mom, "productos") if mom is not None else None
        ps.append(para("interpretacion" if less else "hecho", lambda w: (
            f"Se venden {w.n(count(val(yoy.current, 'productos')))} productos ({w.n(pct_d(py))} vs {w.t(prev_y)}"
            + (f" y {w.n(pct_d(pmo))} vs {w.t(period.previous_month_name)}" if pmo is not None else "") + "); "
            + ("la amplitud de portafolio crece menos que la venta, por lo que el avance se sostiene más por volumen "
               "y valor que por más productos." if less and (pm or 0) > 0 else
               "la amplitud de portafolio acompaña a la venta." if not less else
               "la amplitud de portafolio cae menos que la venta.")), 3,
            basis="productos vendidos Δ% < venta Δ%" if less else ""))
    return ps


def _share(w, c) -> str:
    if c.share_prev is None or c.share_cur is None:
        return "share sin dato"
    if c.pp is not None and abs(c.pp) < Decimal("0.01"):
        return f"{w.n(pct_d(c.share_cur, False))} de share (sin cambio relevante)"
    return f"share de {w.n(pct_d(c.share_prev, False))} a {w.n(pct_d(c.share_cur, False))}"


def _cmp(a: Decimal | None, b: Decimal | None) -> str:
    if a is None or b is None:
        return "comparable"
    return "menor" if a < b else ("mayor" if a > b else "igual")


def _src(v) -> str:
    return f"{v.src.sheet}!{v.src.cells}" if v is not None and v.src is not None and v.src.cells else ""


# ----------------------------------------------------------------------------- 2-5, 8-9 · grupos
def _group_sentence(c: I.Contribution, kind: str, total_pct, rules, pedidos_ok: bool, prev_name: str) -> Para:
    g = c.group
    plural, otros = KIND[kind][1], KIND[kind][2]
    fl = I.flags(c, total_pct, pedidos_ok, rules)
    interp = fl & {"valor_sobre_volumen", "caida_por_mezcla", "base_pequena", "crece_menos_que_total", "sin_venta_actual"}
    basis = []

    def build(w):
        s = f"{w.b(g.name)} {verb(c.pct, rules)}"
        if not (c.pct is not None and abs(c.pct) < rules.relevance):
            s += f" {w.n(pct_d(c.pct))} en venta"
        else:
            s += f" ({w.n(pct_d(c.pct))})"
        extras = [f"piezas {w.n(pct_d(pct_of(g, 'piezas')))}", f"pacientes {w.n(pct_d(pct_of(g, 'pacientes')))}"]
        if pedidos_ok:
            extras.append(f"pedidos {w.n(pct_d(pct_of(g, 'pedidos')))}")
        s += " (" + ", ".join(extras) + ")"
        if "crece_menos_que_total" in fl:
            s += (f", pero pierde participación ({w.n(pct_d(c.share_prev, False))} → {w.n(pct_d(c.share_cur, False))}): "
                  f"{otros} {plural} crecen más rápido")
            basis.append("crece menos que el total y su share baja")
        elif "gana_share" in fl:
            s += f" y gana participación ({w.n(pct_d(c.share_prev, False))} → {w.n(pct_d(c.share_cur, False))})"
        elif "pierde_share" in fl:
            s += f" y pierde participación ({w.n(pct_d(c.share_prev, False))} → {w.n(pct_d(c.share_cur, False))})"
        s += "."
        if "valor_sobre_volumen" in fl:
            s += (f" El avance se explica más por valor por paciente ({w.n(pct_d(pct_of(g, 'v_paciente')))}) que por "
                  f"pacientes ({w.n(pct_d(pct_of(g, 'pacientes')))}).")
            basis.append("venta ↑ con pacientes ↓")
        if "caida_por_mezcla" in fl:
            s += (f" La caída es de valor más que de volumen: las piezas {w.n(pct_d(pct_of(g, 'piezas')))}.")
            basis.append("venta ↓ con piezas ≥ 0")
        if "sin_venta_actual" in fl:
            s += f" No registra venta en el periodo (antes {w.n(money(val(g.previous, 'monto')))})."
            basis.append("monto actual = 0 con monto previo > 0")
        if "base_pequena" in fl:
            s += f" Parte de una base pequeña (share previo {w.n(pct_d(c.share_prev, False))})."
            basis.append("crecimiento > 100 % con share previo < 5 %")
        return s

    p = para("interpretacion" if interp else "hecho", build, 3)
    p.basis = "; ".join(basis)
    p.evidence = [_src(g.current.values.get("monto"))]
    return p


def s_groups(kind: str, groups: list[Group], pano: Group, period: Period, rules: NarrativeRules,
             pedidos_ok: bool = True, mom: bool = False, max_detail: int | None = None) -> list[Para]:
    tp, tc = val(pano.previous, "monto"), val(pano.current, "monto")
    total_pct = pct_of(pano, "monto")
    cs = I.contributions(groups, tp, tc)
    if not cs:
        return [para("info_insuficiente", lambda w: f"Sin {kind}s para mostrar.", 0)]
    prev_name = period.previous_month_name if mom else period.prev_year_label
    net = (tc - tp) if tp is not None and tc is not None else None
    ps: list[Para] = []
    lead = None
    if net is not None and net > 0:
        pos = [c for c in cs if c.delta > 0]
        lead = max(pos, key=lambda c: c.delta) if pos else None
        if lead:
            ps.append(para("hecho", lambda w: (
                f"{w.b(lead.group.name)} es {KIND[kind][0]} que más aporta al crecimiento: {w.n(money(lead.delta, True))} "
                f"({w.n(pct_d(lead.share_of_change, False))} del avance), con venta {w.n(pct_d(lead.pct))} y "
                f"{_share(w, lead)}."), 0,
                evidence=[_src(lead.group.current.values.get("monto"))]))
    elif net is not None and net < 0:
        neg = [c for c in cs if c.delta < 0]
        lead = min(neg, key=lambda c: c.delta) if neg else None
        if lead:
            ps.append(para("hecho", lambda w: (
                f"{w.b(lead.group.name)} es {KIND[kind][0]} que más resta: {w.n(money(lead.delta, True))} contra "
                f"{w.t(prev_name)}, con venta {w.n(pct_d(lead.pct))}."), 0))
    rest = sorted((c for c in cs if c is not lead), key=lambda c: abs(c.delta), reverse=True)
    detail = rest if max_detail is None else rest[:max(max_detail - (1 if lead else 0), 0)]
    # el mayor retroceso siempre se menciona
    worst = min(cs, key=lambda c: c.delta)
    if worst is not lead and worst.delta < 0 and worst not in detail:
        detail = detail[:-1] + [worst] if max_detail is not None and detail else detail + [worst]
    for i, c in enumerate(detail):
        p = _group_sentence(c, kind, total_pct, rules, pedidos_ok, prev_name)
        p.priority = 2 + i
        ps.append(p)
    others = [c for c in rest if c not in detail]
    if others:
        ps.append(para("hecho", lambda w: "Resto: " + ", ".join(
            f"{w.b(c.group.name)} {w.n(pct_d(c.pct))}" for c in others) + ".", 1))
    if not pedidos_ok and kind == "canal":
        q = para("info_insuficiente", lambda w: (
            "No se comparan pedidos por canal: su suma no coincide con el total de pedidos del panorama."), 9)
        q.visible = False
        ps.append(q)
    return ps


# ----------------------------------------------------------------------------- 6-7 · productos
def s_productos(top, growth, decline, pano: Group, rules: NarrativeRules, vs: str = "el mes anterior") -> list[Para]:
    allp = list(top) + list(growth) + list(decline)
    names = labels_for_products(allp)
    total = val(pano.current, "monto")
    ranked = sorted((r for r in top if r.actual.v is not None), key=lambda r: r.actual.v, reverse=True)
    ps: list[Para] = []
    conc = I.concentration(top, total, rules.top_concentration)
    if ranked and conc:
        lead, n4 = ranked[0], conc[1]
        ps.append(para("hecho", lambda w: (
            f"{w.b(names[lead.producto])} es el producto de mayor venta: {w.n(money(lead.actual.v))} "
            f"({w.n(pct_d(conc[0], False))} de la venta total); los {w.n(str(rules.top_concentration))} primeros "
            f"suman {w.n(pct_d(n4, False))}."), 0, evidence=[_src(lead.actual)]))
    net = I.net_by_line(top)
    if net:
        tot = sum(net.values(), Decimal(0))
        new = [r for r in top if r.delta.status == "new_item"]
        ps.append(para("hecho", lambda w: (
            f"Entre los {w.n(str(len(top)))} productos listados, el cambio vs {w.t(vs)} es "
            f"{w.n(money(tot, True))}: " + ", ".join(
                f"{w.b(k)} {w.n(money(v, True))}" for k, v in sorted(net.items(), key=lambda kv: -abs(kv[1])))
            + (f"; incluye {w.n(str(len(new)))} producto(s) sin venta previa." if new else ".")), 1))
    mixed = I.mixed_lines(growth, decline)
    for line in mixed[:2]:
        up = max((r for r in growth if r.aetop == line), key=lambda r: r.delta.v or 0)
        dn = min((r for r in decline if r.aetop == line), key=lambda r: r.delta.v or 0)
        ps.append(para("interpretacion", lambda w: (
            f"En {w.b(line)} conviven alzas ({w.b(names[up.producto])} {w.n(money(up.delta.v, True))}) y bajas "
            f"({w.b(names[dn.producto])} {w.n(money(dn.delta.v, True))}): lectura mixta dentro de la línea."), 2,
            basis="la línea aparece en el Top de alzas y en el de bajas"))
    return ps


def s_movers(rows, kind: str, pano: Group, names: dict[str, str], rules: NarrativeRules) -> list[Para]:
    if not rows:
        return [para("info_insuficiente", lambda w: "Sin productos para mostrar.", 0)]
    tot = sum((r.delta.v for r in rows if r.delta.v is not None), Decimal(0))
    tp, tc = val(pano.previous, "monto"), val(pano.current, "monto")
    net = (tc - tp) if tp is not None and tc is not None else None
    lead = "El crecimiento lo encabezan" if kind == "growth" else "Las principales caídas son"
    ps = [para("hecho", lambda w: (
        lead + " " + ", ".join(f"{w.b(names[r.producto])} ({w.n(money(r.delta.v, True))})" for r in rows[:5]) + "."), 0)]
    by_line = I.net_by_line(rows)
    big = sorted(by_line.items(), key=lambda kv: -abs(kv[1]))[:2]
    ps.append(para("hecho", lambda w: (
        f"Los {w.n(str(len(rows)))} de la lista suman {w.n(money(tot, True))}; se concentran en "
        + " y ".join(f"{w.b(k)} ({w.n(pct_d(v / tot, False))})" for k, v in big if tot != 0)
        + (f", equivalente a {w.n(pct_d(abs(tot / net), False))} del cambio en venta."
           if net and net != 0 and (tot > 0) == (net > 0) else ".")), 1)
        if tot != 0 else para("info_insuficiente", lambda w: "Sin neto para comparar.", 9))
    return ps


# ----------------------------------------------------------------------------- 10 · negados
def s_negados(alta, producto, pano: Group, rules: NarrativeRules) -> list[Para]:
    if alta is None or not alta.rows:
        return [para("info_insuficiente", lambda w: "Sin información de negados.", 0)]
    rows = sorted(alta.rows, key=lambda r: r.monto.v or Decimal(0), reverse=True)
    sales = val(pano.current, "monto")
    tot = alta.total.v
    ps = []
    ratio = (tot / sales) if tot is not None and sales else None
    ps.append(para("hecho", lambda w: (
        f"El monto negado total asciende a {w.n(money(tot))}"
        + (f", equivalente a {w.n(pct_d(ratio, False))} de la venta del periodo" if ratio is not None else "")
        + f", concentrado principalmente en {w.b(rows[0].name)} con {w.n(money(rows[0].monto.v))} y "
          f"{w.n(pct_d(rows[0].share.v, False))} del total"
        + (f", seguido de {w.b(rows[1].name)} con {w.n(money(rows[1].monto.v))} y {w.n(pct_d(rows[1].share.v, False))}."
           if len(rows) > 1 else ".")), 0))
    by_qty = max(rows, key=lambda r: r.cantidad.v or Decimal(0))
    if by_qty is not rows[0]:
        ps.append(para("interpretacion", lambda w: (
            f"Por cantidad negada, {w.b(by_qty.name)} concentra el mayor volumen ({w.n(count(by_qty.cantidad.v))} "
            f"piezas), mientras que {w.b(rows[0].name)} concentra el mayor monto: el impacto no está en una sola línea."), 1,
            basis="la línea líder por piezas difiere de la líder por monto"))
    if producto and producto.rows:
        tops = sorted(producto.rows, key=lambda r: r.monto.v or Decimal(0), reverse=True)[:3]
        names = labels_for_products([type("R", (), {"producto": r.name}) for r in tops])
        share3 = sum((r.monto.v for r in tops if r.monto.v is not None), Decimal(0)) / tot if tot else None
        ps.append(para("hecho", lambda w: (
            "Los productos con mayor monto negado son " + ", ".join(
                f"{w.b(names[r.name])} ({w.n(money(r.monto.v))})" for r in tops)
            + (f", que suman {w.n(pct_d(share3, False))} del total." if share3 is not None else ".")), 2))
    ped = sum((r.pedidos.v for r in rows if r.pedidos.v is not None), Decimal(0))
    qty = sum((r.cantidad.v for r in rows if r.cantidad.v is not None), Decimal(0))
    ps.append(para("hecho", lambda w: (
        f"En total se registran {w.n(count(ped))} pedidos y {w.n(count(qty))} piezas negadas."), 3))
    ps.append(para("interpretacion", lambda w: (
        "Es venta no concretada: un punto a revisar para su recuperación."), 4,
        basis="definición de negado (venta no concretada) — pendiente de validar"))
    return ps


# ----------------------------------------------------------------------------- 11 · conclusiones
def s_conclusiones(yoy, mom, canal, linea, prod, neg_total, pano_yoy, period, rules) -> list[Para]:
    def line(label, key):
        a = pct_of(yoy, key)
        v = "creció" if (a or 0) > 0 else "cayó" if (a or 0) < 0 else "se mantuvo"
        if mom is None:
            return para("hecho", lambda w: f"{label} {v} {w.n(pct_d(a))} vs {w.t(period.prev_year_label)}", 0)
        b = pct_of(mom, key)
        return para("hecho", lambda w: f"{label} {v} {w.n(pct_d(a))} YoY y {w.n(pct_d(b))} MoM", 0)
    ps = [line("El monto de venta", "monto"), line("La cantidad de piezas", "piezas"),
          line("La cantidad de pacientes", "pacientes"), line("La cantidad de pedidos", "pedidos"),
          line("El ticket promedio", "ticket")]
    ps.append(para("hecho", lambda w: "**Insights clave:**", 0))
    dec = I.decompose_sales(yoy.previous, yoy.current, rules)
    if dec:
        vol = Decimal(str(round(dec.volume, 4)))
        who = "volumen" if dec.volume >= 0.6 else "valor por pieza" if dec.price >= 0.6 else "volumen y valor por pieza"
        mom_txt = (lambda w: f" y {w.n(pct_d(pct_of(mom, 'monto')))} MoM") if mom is not None else (lambda w: "")
        ps.append(para("interpretacion", lambda w: (
            f"En {w.t(period.label)}, la venta llega a {w.n(money(val(yoy.current, 'monto')))} "
            f"({w.n(pct_d(pct_of(yoy, 'monto')))} YoY{mom_txt(w)}); el cambio anual se "
            f"explica principalmente por {who} ({w.n(pct_d(vol, False))} del cambio)."), 1,
            basis="descomposición de la venta (pacientes × piezas por paciente × valor por pieza)"))
    press = I.pressures(yoy, rules)
    if press:
        ps.append(para("hecho", lambda w: (
            "Presiones del periodo: " + ", ".join(f"{lbl} ({w.n(pct_d(v))})" for lbl, v in press[:3]) + "."), 2))
    tp, tc = val(pano_yoy.previous, "monto"), val(pano_yoy.current, "monto")
    for kind, groups in (("canal", canal), ("línea", linea)):
        cs = I.contributions(groups, tp, tc)
        if len(cs) >= 2:
            top, low = max(cs, key=lambda c: c.delta), min(cs, key=lambda c: c.delta)
            ps.append(para("hecho", lambda w: (
                f"Por {kind}, {w.b(top.group.name)} es el mayor aporte al avance anual ({w.n(money(top.delta, True))}, "
                f"share {w.n(pct_d(top.share_cur, False))})"
                + (f" y {w.b(low.group.name)} el que menos aporta ({w.n(money(low.delta, True))})." if low is not top else ".")),
                2 if kind == "canal" else 3))
    if prod:
        names = labels_for_products(prod["growth"] + prod["decline"])
        up, dn = prod["growth"][:3], prod["decline"][:3]
        ps.append(para("hecho", lambda w: (
            "En productos, el crecimiento lo encabezan " + ", ".join(w.b(names[r.producto]) for r in up)
            + "; las caídas más relevantes están en " + ", ".join(w.b(names[r.producto]) for r in dn) + "."), 4))
    if neg_total is not None:
        ratio = neg_total / val(yoy.current, "monto") if val(yoy.current, "monto") else None
        ps.append(para("interpretacion", lambda w: (
            f"Los negados suman {w.n(money(neg_total))}"
            + (f" ({w.n(pct_d(ratio, False))} de la venta del periodo)" if ratio is not None else "")
            + ": venta no concretada que conviene revisar para su recuperación."), 5,
            basis="definición de negado (venta no concretada) — pendiente de validar"))
    return ps


# ----------------------------------------------------------------------------- orquestación
def compose_aetops_mensual(result: Result, period: Period, boxes: dict[str, Box],
                           cat_yoy_shown: list[Group], cat_mom_shown: list[Group],
                           rules: NarrativeRules = RULES) -> dict[str, list[Para]]:
    T = result.tables
    py, pm = T["aetops.panorama.yoy"].groups[0], T["aetops.panorama.mom"].groups[0]
    pedidos_ok = not any(f.id == "TOTALS_MISMATCH" and "canal" in f.message and "pedidos" in f.message
                         for f in result.findings)
    prod = {k: result.products[f"aetops.productos.{k}"].rows for k in ("top", "growth", "decline")}
    names = labels_for_products(prod["top"] + prod["growth"] + prod["decline"])
    neg_alta, neg_prod = result.negados.get("aetops.negados.alta"), result.negados.get("aetops.negados.producto")
    out = {
        "panorama": s_panorama(py, pm, period, rules),
        "canal_yoy": s_groups("canal", T["aetops.canal.yoy"].groups, py, period, rules, pedidos_ok),
        "canal_mom": s_groups("canal", T["aetops.canal.mom"].groups, pm, period, rules, pedidos_ok, mom=True),
        "linea_yoy": s_groups("línea", T["aetops.linea.yoy"].groups, py, period, rules),
        "linea_mom": s_groups("línea", T["aetops.linea.mom"].groups, pm, period, rules, mom=True),
        "productos": s_productos(prod["top"], prod["growth"], prod["decline"], pm, rules),
        "crecimiento": s_movers(prod["growth"], "growth", pm, names, rules),
        "decrecimiento": s_movers(prod["decline"], "decline", pm, names, rules),
        "cat_yoy": s_groups("categoría", cat_yoy_shown, py, period, rules, max_detail=3),
        "cat_mom": s_groups("categoría", cat_mom_shown, pm, period, rules, mom=True, max_detail=3),
        "negados": s_negados(neg_alta, neg_prod, pm, rules),
        "conclusiones": s_conclusiones(py, pm, T["aetops.canal.yoy"].groups, T["aetops.linea.yoy"].groups, prod,
                                       neg_alta.total.v if neg_alta else None, py, period, rules),
    }
    for key, paras in out.items():
        box = boxes.get(key)
        vis = [p for p in paras if p.visible]
        hidden = [p for p in paras if not p.visible]
        out[key] = (fit(vis, box.cpl, box.lines) if box else vis) + hidden
    return out


def check(narr: dict[str, list[Para]]) -> list[str]:
    return verify_all([p for ps in narr.values() for p in ps])


def compose_aetops_trimestral(result: Result, period: Period, boxes: dict[str, Box], cat_shown: list[Group],
                              rules: NarrativeRules = RULES) -> dict[str, list[Para]]:
    """Trimestral: solo comparativo YoY (mismo trimestre del año anterior)."""
    T = result.tables
    py = T["aetops.panorama.yoy"].groups[0]
    pedidos_ok = not any(f.id == "TOTALS_MISMATCH" and "canal" in f.message and "pedidos" in f.message
                         for f in result.findings)
    prod = {k: result.products[f"aetops.productos.{k}"].rows for k in ("top", "growth", "decline")}
    names = labels_for_products(prod["top"] + prod["growth"] + prod["decline"])
    neg_alta, neg_prod = result.negados.get("aetops.negados.alta"), result.negados.get("aetops.negados.producto")
    movers = (s_movers(prod["growth"], "growth", py, names, rules) +
              s_movers(prod["decline"], "decline", py, names, rules))
    for p in movers[2:]:
        p.priority += 1
    out = {
        "panorama": s_panorama(py, None, period, rules),
        "linea_yoy": s_groups("línea", T["aetops.linea.yoy"].groups, py, period, rules),
        "canal_yoy": s_groups("canal", T["aetops.canal.yoy"].groups, py, period, rules, pedidos_ok),
        "productos": s_productos(prod["top"], prod["growth"], prod["decline"], py, rules, vs=period.prev_year_label),
        "movers": movers,
        "cat_yoy": s_groups("categoría", cat_shown, py, period, rules, max_detail=3),
        "negados": s_negados(neg_alta, neg_prod, py, rules),
        "conclusiones": s_conclusiones(py, None, T["aetops.canal.yoy"].groups, T["aetops.linea.yoy"].groups, prod,
                                       neg_alta.total.v if neg_alta else None, py, period, rules),
    }
    for key, paras in out.items():
        box = boxes.get(key)
        vis = [p for p in paras if p.visible]
        hidden = [p for p in paras if not p.visible]
        out[key] = (fit(vis, box.cpl, box.lines) if box else vis) + hidden
    return out
