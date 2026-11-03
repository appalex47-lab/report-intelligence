"""Hoja de hechos para el «descubrimiento único» con IA.

Cada hecho es una frase determinista y verificada (cifras ya calculadas por el motor), con un id y un tema. La IA solo puede
combinar estos hechos —citándolos— y no puede usar ninguna cifra que no esté en los hechos que cita (ver `verify_discovery`).
Los hechos incluyen cruces entre dimensiones (canal × línea, fuente × conversión, región × tráfico…) para que cada reporte
pueda sostener un hallazgo propio y no solo el titular de siempre.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal

from ..models import GBlock, GRow, Period
from . import insights as I
from .aetops import count, money, pct_d, pp_s
from .glp1 import cur_label, prev_label, short, sx
from .rules import RULES
from .writer import CAUSAL, NUMBER

YEAR = re.compile(r"(19|20)\d\d")


@dataclass
class Fact:
    id: str
    tema: str
    texto: str
    nums: set[str] = field(default_factory=set)
    nuevo: bool = False          # True = no aparece en ninguna otra diapositiva de la presentación (el descubrimiento debe apoyarse en estos)

    def to_dict(self) -> dict:
        return {"id": self.id, "tema": self.tema, "texto": self.texto, "cifras": sorted(self.nums), "nuevo": self.nuevo}


def norm_tok(t: str) -> str:
    """Normaliza una cifra para compararla: sin espacios y sin '+' (el signo '-' sí cuenta: cambia el sentido)."""
    return re.sub(r"\s+", "", t).lstrip("+")


def tokens(text: str) -> set[str]:
    return {norm_tok(m.group(0)) for m in NUMBER.finditer(text.replace("**", "")) if m.group(0).strip()}


PREFIX = {"panorama": "PA", "canal": "CA", "línea": "LI", "categoría": "CT", "cruce": "CR", "producto": "PR", "negados": "NE", "meta": "ME", "embudo": "EM",
          "edad": "ED", "sexo": "SX", "dispositivo": "DI", "fuentes": "FU", "region": "RE", "pago": "PG", "entrega": "EN", "productos": "PD", "programas": "PM",
          "mezcla": "MZ", "productividad": "PV", "abasto": "AB", "pacientes": "PC", "geografia": "GE", "canasta": "CS", "calendario": "CL", "tendencia": "TE", "mezcla canal-línea": "CX"}


class _Sheet:
    def __init__(self):
        self.items: list[Fact] = []
        self._n: dict[str, int] = {}

    def add(self, tema: str, texto: str, nuevo: bool = False):
        k = PREFIX.get(tema, "XX")
        self._n[k] = self._n.get(k, 0) + 1
        self.items.append(Fact(f"{k}{self._n[k]}", tema, texto, tokens(texto), nuevo))


def _d(x):
    return x.v if x is not None else None


# ------------------------------------------------------------------------------------------------ AETOPS
def aetops_facts(result, period: Period, att=None) -> list[Fact]:
    S = _Sheet()
    T = result.tables
    if "aetops.panorama.yoy" not in T:
        return []
    py = T["aetops.panorama.yoy"].groups[0]
    pm = T["aetops.panorama.mom"].groups[0] if "aetops.panorama.mom" in T else None
    prev_y = period.prev_year_label
    sales, tp = _d(py.current.values["monto"]), _d(py.previous.values["monto"])
    lab = {"monto": "venta", "pacientes": "pacientes", "piezas": "piezas", "pedidos": "pedidos", "ticket": "ticket promedio", "productos": "productos vendidos"}
    for k, name in lab.items():
        cur = _d(py.current.values[k])
        fmt = (lambda v: money(v)) if k in ("monto", "ticket") else (lambda v: count(v))
        mom = f"; {pct_d(_d(pm.pct[k]))} vs {period.previous_month_name}" if pm else ""
        S.add("panorama", f"Panorama: {name} de {period.label}: {fmt(cur)} ({pct_d(_d(py.pct[k]))} vs {prev_y}{mom}).")
    dec = I.decompose_sales(py.previous, py.current, RULES)
    if dec:
        S.add("panorama", f"El cambio anual de la venta se explica {pct_d(Decimal(str(round(dec.volume, 4))), False)} por volumen (pacientes y piezas por paciente) y "
                          f"{pct_d(Decimal(str(round(dec.price, 4))), False)} por venta por pieza.")
    v_pac = _d(py.current.values.get("v_paciente"))
    if v_pac:
        S.add("panorama", f"Valor por paciente: {money(v_pac)} ({pct_d(_d(py.pct.get('v_paciente')))} vs {prev_y}); piezas por paciente: {_d(py.current.values.get('size_b')):.2f} "
                          f"({pct_d(_d(py.pct.get('size_b')))}).")
    for kind, key, nm in (("canal", "aetops.canal.yoy", "Canal"), ("línea", "aetops.linea.yoy", "Línea"), ("categoría", "aetops.categoria.yoy", "Categoría")):
        if key not in T:
            continue
        cs = I.contributions(T[key].groups, tp, sales)
        by = {c.group.name: c for c in cs}
        for g in T[key].groups:
            c = by.get(g.name)
            share = ""
            if c and c.share_prev is not None and c.share_cur is not None:
                share = f"; participación {pct_d(c.share_prev, False)} → {pct_d(c.share_cur, False)} ({pp_s(c.pp)})"
            aporte = f"; aporta {money(c.delta, True)}" + (f" ({pct_d(c.share_of_change, False)} del avance)" if c and c.share_of_change else "") if c else ""
            S.add(kind, f"{nm} {g.name}: venta {money(_d(g.current.values['monto']))} ({pct_d(_d(g.pct['monto']))} vs {prev_y}){share}{aporte}; "
                        f"pacientes {pct_d(_d(g.pct['pacientes']))}, ticket {money(_d(g.current.values['ticket']))} ({pct_d(_d(g.pct['ticket']))}).")
    if "aetops.canal.yoy" in T and "aetops.linea.yoy" in T:
        # cruce canal × línea: qué canal depende más de qué línea no se puede sin filas crudas; sí se compara ticket y pacientes entre canales
        ch = T["aetops.canal.yoy"].groups
        best_t = max(ch, key=lambda g: _d(g.current.values["ticket"]) or 0)
        low_t = min(ch, key=lambda g: _d(g.current.values["ticket"]) or 0)
        if best_t is not low_t:
            S.add("cruce", f"Entre canales, el ticket promedio más alto es de {best_t.name} ({money(_d(best_t.current.values['ticket']))}) y el más bajo de {low_t.name} "
                           f"({money(_d(low_t.current.values['ticket']))}).")
    _aetops_nuevos(S, result, period)
    prods = result.products or {}
    names = {}
    for k in ("top", "growth", "decline"):
        for r in (prods.get(f"aetops.productos.{k}").rows if prods.get(f"aetops.productos.{k}") else []):
            names[r.producto] = short(r.producto, 40)
    for r in (prods["aetops.productos.top"].rows[:10] if "aetops.productos.top" in prods else []):
        S.add("producto", f"Producto {names[r.producto]} ({r.aetop}): venta {money(_d(r.actual))}, cambio {money(_d(r.delta), True)}; se vende en {count(_d(r.canales))} canales.")
    for k, lead in (("growth", "alza"), ("decline", "caída")):
        for r in (prods[f"aetops.productos.{k}"].rows[:6] if f"aetops.productos.{k}" in prods else []):
            nuevo = " (sin venta en el periodo previo)" if r.delta.status == "new_item" else ""
            S.add("producto", f"Mayor {lead}: {names[r.producto]} ({r.aetop}) {money(_d(r.delta), True)}{nuevo}.")
    if "aetops.productos.growth" in prods and "aetops.productos.decline" in prods:
        net = I.net_by_line(prods["aetops.productos.growth"].rows + prods["aetops.productos.decline"].rows)
        for ln, v in sorted(net.items(), key=lambda t: -abs(t[1]))[:3]:
            S.add("cruce", f"En la línea {ln}, las mayores alzas y caídas de productos suman {money(v, True)} netos.")
    alta, neg = result.negados.get("aetops.negados.alta"), result.negados.get("aetops.negados.producto")
    if alta and alta.total.v and sales:
        S.add("negados", f"Negados (producto sin stock negado a la venta): {money(alta.total.v)}, {pct_d(alta.total.v / sales, False)} de la venta del periodo.")
        for r in alta.rows[:3]:
            S.add("negados", f"Negados en {r.name}: {money(_d(r.monto))} ({pct_d(_d(r.share), False)} del total negado), {count(_d(r.pedidos))} pedidos.")
    if neg:
        for r in neg.rows[:3]:
            S.add("negados", f"Producto más negado {short(r.name, 40)}: {money(_d(r.monto))}, {count(_d(r.pedidos))} pedidos, {count(_d(r.cantidad))} piezas.")
    for a in (att or []):
        S.add("meta", f"Meta {a.name}: la venta alcanza {pct_d(a.pct, False)} de la meta de {money(a.target)} ({money(a.gap, True)}).")
    return S.items


def _pp(x: Decimal | None) -> str:
    return "n/d" if x is None else f"{x * 100:.1f}%"


def _aetops_nuevos(S: _Sheet, result, period: Period) -> None:
    """Hechos que NO están en ninguna otra diapositiva: descomposición por grupo, productividad, tasa de negado por línea y cruces de filas crudas."""
    T = result.tables
    py = T["aetops.panorama.yoy"].groups[0]
    tot_size, tot_vp = _d(py.current.values.get("size_b")), _d(py.current.values.get("v_paciente"))
    tot_ped_pac = _rate(_d(py.current.values["pedidos"]), _d(py.current.values["pacientes"]))
    for kind, key, nm in (("mezcla", "aetops.canal.yoy", "canal"), ("mezcla", "aetops.linea.yoy", "línea"), ("mezcla", "aetops.categoria.yoy", "categoría")):
        for g in T.get(key, type("T", (), {"groups": []})).groups:
            dec = I.decompose_sales(g.previous, g.current, RULES)
            if dec:
                S.add("mezcla", f"En {nm} {g.name}, el cambio anual de la venta ({pct_d(_d(g.pct['monto']))}) se explica {pct_d(Decimal(str(round(dec.volume, 4))), False)} por volumen "
                                f"(pacientes y piezas por paciente) y {pct_d(Decimal(str(round(dec.price, 4))), False)} por venta por pieza.", True)
    for key, nm in (("aetops.canal.yoy", "canal"), ("aetops.linea.yoy", "línea")):
        for g in T.get(key, type("T", (), {"groups": []})).groups:
            size, vp = _d(g.current.values.get("size_b")), _d(g.current.values.get("v_paciente"))
            pp = _rate(_d(g.current.values["pedidos"]), _d(g.current.values["pacientes"]))
            if size and vp and tot_size and tot_vp:
                S.add("productividad", f"Productividad del {nm} {g.name}: {size:.2f} piezas por paciente (total {tot_size:.2f}), {money(vp)} por paciente (total {money(tot_vp)})"
                                       + (f" y {pp:.2f} pedidos por paciente (total {tot_ped_pac:.2f})" if pp and tot_ped_pac else "") + ".", True)
    alta, linea = result.negados.get("aetops.negados.alta"), T.get("aetops.linea.yoy")
    if alta and linea and alta.total.v:
        sales_by = {g.name: _d(g.current.values["monto"]) for g in linea.groups}
        tot_sales = _d(py.current.values["monto"])
        for r in alta.rows:
            v = sales_by.get(r.name)
            if v:
                S.add("abasto", f"Tasa de negado de la línea {r.name}: lo negado ({money(_d(r.monto))}) equivale a {_pp(_d(r.monto) / v)} de su venta (todas las líneas: {_pp(alta.total.v / tot_sales)}).", True)
    X = getattr(result, "extras", {}) or {}
    cur, yoy = X.get("pac_cur"), X.get("pac_yoy")
    if cur and cur.get("nuevo") and cur.get("recurrente"):
        n, r = cur["nuevo"], cur["recurrente"]
        tot = n["monto"] + r["monto"]
        tn, tr = (n["monto"] / n["pedidos"]) if n["pedidos"] else None, (r["monto"] / r["pedidos"]) if r["pedidos"] else None
        prev = ""
        if yoy and yoy.get("nuevo") and yoy.get("recurrente"):
            tot_y = yoy["nuevo"]["monto"] + yoy["recurrente"]["monto"]
            prev = f", contra {_pp(yoy['nuevo']['monto'] / tot_y)} un año antes"
        S.add("pacientes", f"Pacientes nuevos (primer pedido histórico): {count(Decimal(n['pacientes']))} pacientes y {_pp(n['monto'] / tot)} de la venta{prev}; su ticket es {money(tn)} "
                           f"contra {money(tr)} de los recurrentes.", True)
    c10, c10y = X.get("conc_cur"), X.get("conc_yoy")
    if c10 and c10["total"]:
        prev = f" (hace un año: {_pp(c10y['top10'] / c10y['total'])})" if c10y and c10y["total"] else ""
        S.add("pacientes", f"El 10% de los pacientes ({count(Decimal(c10['top_n']))} de {count(Decimal(c10['n']))}) concentra {_pp(c10['top10'] / c10['total'])} de la venta{prev}.", True)
    est, esty = X.get("estado_cur"), X.get("estado_yoy")
    if est:
        tot = sum(est.values(), Decimal(0))
        top = sorted(est.items(), key=lambda t: -t[1])[:3]
        S.add("geografia", "Estados con más venta: " + ", ".join(f"{e} {_pp(m / tot)}" for e, m in top) + f"; los tres suman {_pp(sum(m for _, m in top) / tot)}.", True)
        if esty:
            toty = sum(esty.values(), Decimal(0))
            gain = sorted(((e, est[e] / tot - esty.get(e, Decimal(0)) / toty) for e in est if toty), key=lambda t: -abs(t[1]))[:2]
            for e, dpp in gain:
                S.add("geografia", f"El estado {e} cambia su participación en {pp_s(dpp)} contra el mismo periodo del año anterior ({_pp(esty.get(e, Decimal(0)) / toty)} → {_pp(est[e] / tot)}).", True)
    cl, cly = X.get("cl_cur"), X.get("cl_yoy")
    if cl:
        by_line: dict[str, dict[str, Decimal]] = {}
        by_canal: dict[str, Decimal] = {}
        for (cn, ln), m in cl.items():
            by_line.setdefault(ln, {})[cn] = m
            by_canal[cn] = by_canal.get(cn, Decimal(0)) + m
        tot = sum(by_canal.values(), Decimal(0))
        for ln, d in sorted(by_line.items(), key=lambda t: -sum(t[1].values(), Decimal(0)))[:3]:
            sl = sum(d.values(), Decimal(0))
            cn, m = max(d.items(), key=lambda t: t[1])
            S.add("mezcla canal-línea", f"El {_pp(m / sl)} de la venta de {ln} pasa por {cn}, contra {_pp(by_canal[cn] / tot)} de la venta total en ese canal.", True)
    cs, csy = X.get("canasta_cur"), X.get("canasta_yoy")
    if cs and cs["un"]["pedidos"] and cs["varios"]["pedidos"]:
        n_tot = cs["un"]["pedidos"] + cs["varios"]["pedidos"]
        t1, t2 = cs["un"]["monto"] / cs["un"]["pedidos"], cs["varios"]["monto"] / cs["varios"]["pedidos"]
        S.add("canasta", f"El {_pp(Decimal(cs['varios']['pedidos']) / n_tot)} de los pedidos lleva 2 o más productos; su ticket es {money(t2)} frente a {money(t1)} de los de un solo producto.", True)
    q, qy = X.get("quinc_cur"), X.get("quinc_yoy")
    if q and q.get(1) is not None and q.get(2) is not None and (q[1] + q[2]):
        t = q[1] + q[2]
        prev = f" (un año antes: {_pp(qy[1] / (qy[1] + qy[2]))} / {_pp(qy[2] / (qy[1] + qy[2]))})" if qy and qy.get(1) is not None and qy.get(2) is not None and (qy[1] + qy[2]) else ""
        S.add("calendario", f"La venta se reparte {_pp(q[1] / t)} en la primera quincena y {_pp(q[2] / t)} en la segunda{prev}.", True)


# ------------------------------------------------------------------------------------------------ GLP-1
def _rate(num, den):
    return (num / den) if num is not None and den else None


def glp1_facts(blocks: dict[str, GBlock], funnel: GBlock | None, period: Period, extras: dict | None = None) -> list[Fact]:
    S = _Sheet()
    cur, prev = cur_label(period), prev_label(period)
    pano = blocks.get("panorama")
    if pano:
        P = pano.rows[0].values

        def ch(k, suf):
            a, b = _d(P.get(k)), _d(P.get(k + suf))
            return pct_d((a - b) / b) if a is not None and b else "n/d"
        for k, name, fmt in (("monto", "venta", money), ("pedidos", "pedidos", count), ("pacientes", "pacientes", count), ("ticket", "ticket promedio", money),
                             ("pacientes_nuevos", "pacientes nuevos", count)):
            if k in P:
                S.add("panorama", f"Panorama: {name} de {cur}: {fmt(_d(P[k]))} ({ch(k, '_prev')} vs {prev}; {ch(k, '_yoy')} vs el mismo periodo del año anterior).")
        if "compras" in P and "vistas_producto" in P and _d(P["vistas_producto"]):
            conv = _rate(_d(P["compras"]), _d(P["vistas_producto"]))
            S.add("embudo", f"Embudo: {count(_d(P['vistas_producto']))} vistas de producto, {count(_d(P['add_to_cart']))} add to cart, {count(_d(P['begin_checkout']))} inicios de compra y "
                            f"{count(_d(P['compras']))} compras; conversión final {conv * 100:.2f}%; carritos abandonados {count(_d(P['carritos_abandonados']))}.".replace("%;", "%;"))
    for name, label, key in (("edad", "Edad", "visitas"), ("sexo", "Sexo", "visitas"), ("dispositivo", "Dispositivo", "visitas"), ("fuentes", "Fuente de tráfico", "visitas")):
        b = blocks.get(name)
        if not b:
            continue
        tot = sum((_d(r.values["visitas"]) or 0) for r in b.rows)
        tot_atc = sum((_d(r.values["atc"]) or 0) for r in b.rows)
        for r in b.rows[:10]:
            vis, atc = _d(r.values["visitas"]), _d(r.values["atc"])
            tasa = _rate(atc, vis)
            share = vis / tot if tot and vis else None
            S.add(name, f"{label} {sx(r.key) if name == 'sexo' else r.key}: {count(vis)} visitas ({pct_d(share, False)} del total; {pct_d(_d(r.delta))} vs {prev}), "
                        f"{count(atc)} add to cart ({tasa * 100:.1f}% de sus visitas contra {(tot_atc / tot) * 100:.1f}% del total).", True)
    for name, label in (("region", "Región"), ("pago", "Forma de pago"), ("entrega", "Modo de entrega"), ("productos", "Producto"), ("programas", "Programa")):
        b = blocks.get(name)
        if not b:
            continue
        for r in b.rows[:8]:
            yoy = _d(r.delta_yoy) if r.delta_yoy is not None else None
            S.add(name, f"{label} {short(r.key, 40)}: venta {money(_d(r.values['monto']))} ({pct_d(_d(r.share), False)} del total; {pct_d(_d(r.delta))} vs {prev}"
                        + (f"; {pct_d(yoy)} vs el mismo periodo del año anterior" if yoy is not None else "") + f"), {count(_d(r.values['pedidos']))} pedidos, ticket {money(_d(r.values['ticket']))}.")
    # cruces: sexo × producto, edad × producto
    ps = blocks.get("producto_sexo")
    if ps:
        by: dict[str, dict[str, GRow]] = {}
        for r in ps.rows:
            by.setdefault(r.key, {})[sx(r.dim2)] = r
        for p, d in list(by.items())[:5]:
            if len(d) == 2:
                a, b = (d[k] for k in sorted(d))
                S.add("cruce", f"{p}: {sorted(d)[0].lower()} {count(_d(a.values['visitas']))} visitas ({pct_d(_d(a.delta))}) frente a {sorted(d)[1].lower()} {count(_d(b.values['visitas']))} ({pct_d(_d(b.delta))}).")
    for k, b in blocks.items():
        if k.startswith("edad_producto:") and b.rows:
            lead = max(b.rows, key=lambda r: _d(r.values["visitas"]) or 0)
            S.add("cruce", f"En {k.split(':', 1)[1].capitalize()}, el grupo de edad con más visitas es {lead.key} ({count(_d(lead.values['visitas']))}; {pct_d(_d(lead.delta))} vs {prev}).")
    can = blocks.get("canal_resumen")
    if can and len(can.rows) >= 2:
        for r in can.rows:
            v, a = _d(r.values["visitas"]), _d(r.values["atc"])
            S.add("fuentes", f"Canal {r.key}: {count(v)} visitas y {count(a)} add to cart ({_rate(a, v) * 100:.1f}% de sus visitas).")
    if pano and "compras" in pano.rows[0].values:
        P = pano.rows[0].values
        v, a, c = _d(P.get("vistas_producto")), _d(P.get("add_to_cart")), _d(P.get("compras"))
        if v and a and c:
            S.add("embudo", f"De cada 100 vistas de producto, {a / v * 100:.1f} llegan a add to cart; de cada 100 add to cart, {c / a * 100:.1f} terminan en compra y {100 - c / a * 100:.1f} se abandonan.", True)
    _glp1_nuevos(S, blocks, extras, period)
    neg = blocks.get("negados")
    if neg and neg.rows and pano:
        tot = sum((_d(r.values["monto_negado"]) or 0) for r in neg.rows)
        S.add("negados", f"Negados (producto sin stock negado a la venta): {money(tot)}, {pct_d(tot / _d(pano.rows[0].values['monto']), False)} de la venta.")
        for r in neg.rows[:3]:
            S.add("negados", f"Producto más negado {short(r.key, 40)}: {money(_d(r.values['monto_negado']))}, {count(_d(r.values['pedidos']))} pedidos.")
    return S.items


def _glp1_nuevos(S: _Sheet, blocks: dict, X: dict | None, period: Period) -> None:
    X = X or {}
    cur, yoy = X.get("pac_cur"), X.get("pac_yoy")
    if cur and cur.get("nuevo") and cur.get("recurrente"):
        n, r = cur["nuevo"], cur["recurrente"]
        tot = n["monto"] + r["monto"]
        prev = ""
        if yoy and yoy.get("nuevo") and yoy.get("recurrente"):
            ty = yoy["nuevo"]["monto"] + yoy["recurrente"]["monto"]
            prev = f", contra {_pp(yoy['nuevo']['monto'] / ty)} un año antes"
        S.add("pacientes", f"Pacientes nuevos (primer pedido histórico): {count(Decimal(n['pacientes']))} pacientes y {_pp(n['monto'] / tot)} de la venta{prev}; ticket "
                           f"{money(n['monto'] / n['pedidos'] if n['pedidos'] else None)} contra {money(r['monto'] / r['pedidos'] if r['pedidos'] else None)} de los recurrentes.", True)
    c10, c10y = X.get("conc_cur"), X.get("conc_yoy")
    if c10 and c10["total"]:
        prev = f" (hace un año: {_pp(c10y['top10'] / c10y['total'])})" if c10y and c10y["total"] else ""
        S.add("pacientes", f"El 10% de los pacientes ({count(Decimal(c10['top_n']))} de {count(Decimal(c10['n']))}) concentra {_pp(c10['top10'] / c10['total'])} de la venta{prev}.", True)
    q, qy = X.get("quinc_cur"), X.get("quinc_yoy")
    if q and q.get(1) is not None and q.get(2) is not None and (q[1] + q[2]):
        t = q[1] + q[2]
        S.add("calendario", f"La venta se reparte {_pp(q[1] / t)} en la primera quincena y {_pp(q[2] / t)} en la segunda.", True)
    est, tr = X.get("estado_cur"), blocks.get("trafico_estado")
    if est and tr:
        from ..importer.profile import norm as _norm
        vis = {_norm(r.key): _d(r.values["visitas"]) for r in tr.rows}
        rows = [(r.key, est[_norm(r.key)]["pedidos"], _d(r.values["visitas"])) for r in tr.rows if _norm(r.key) in est and _d(r.values["visitas"])]
        if len(rows) >= 3:
            tp, tv = sum(p for _, p, _ in rows), sum(v for _, _, v in rows)
            rates = sorted(((k, p / v * 1000, p) for k, p, v in rows), key=lambda t: -t[1])
            S.add("geografia", f"Pedidos por cada mil visitas (promedio de los estados con tráfico: {tp / tv * 1000:.1f}): más alto en {rates[0][0]} ({rates[0][1]:.1f}) y {rates[1][0]} ({rates[1][1]:.1f}); "
                               f"más bajo en {rates[-1][0]} ({rates[-1][1]:.1f}).", True)


def trend_facts(trends_list, start: int = 1) -> list[Fact]:
    """Tendencias del historial (2+ variaciones consecutivas fuera de la banda ±5 %): son el «patrón» entre meses."""
    out = []
    for t in trends_list:
        if t.para is None or t.para.kind == "info_insuficiente":
            continue
        texto = "Tendencia: " + t.para.plain
        out.append(Fact(f"TE{start + len(out)}", "tendencia", texto, tokens(texto)))
    return out


# ------------------------------------------------------------------------------------------------ verificación del descubrimiento
# Hoja completa con la misma estructura cada mes: titular + datos + significado + hipótesis + acciones (+ evidencia citada).
SECCIONES = {"datos": ("hecho", "Lo que dicen los datos"), "significado": ("interpretacion", "Lo que significa"),
             "hipotesis": ("hipotesis", "Hipótesis a validar"), "accion": ("recomendacion", "Qué haríamos")}
MAX_BULLETS, MAX_LEN, MAX_TITULAR = 12, 300, 240
TIPOS = tuple(v[0] for v in SECCIONES.values())
MIN_STRICT = {"datos": 2, "significado": 1, "accion": 1}


def bold_numbers(text: str) -> str:
    plain = text.replace("**", "")
    return NUMBER.sub(lambda m: f"**{m.group(0)}**" if m.group(0).strip() and not YEAR.fullmatch(m.group(0).strip()) else m.group(0), plain)


def _check_text(texto: str, validar: str, ids: list[str], byid: dict, maxlen: int, need_new: bool = False) -> list[str]:
    probs: list[str] = []
    if not texto or len(texto) > maxlen:
        probs.append(f"texto vacío o de más de {maxlen} caracteres")
    if not ids:
        probs.append("no cita hechos")
    bad = [i for i in ids if i not in byid]
    if bad:
        probs.append("cita hechos que no existen: " + ", ".join(bad[:3]))
    cited = [byid[i] for i in ids if i in byid]
    if need_new and cited and not any(f.nuevo for f in cited):
        probs.append("repite lo que ya muestra la presentación: debe apoyarse en al menos un hecho nuevo (nuevo=true)")
    allowed = set().union(*(f.nums for f in cited)) if cited else set()
    extra = sorted(t for t in tokens(texto + " " + validar) if t not in allowed and not YEAR.fullmatch(t))
    if extra:
        probs.append("cifra(s) que no están en los hechos citados: " + ", ".join(extra[:4]))
    if any(c in (texto + " " + validar).lower() for c in CAUSAL):
        probs.append("vocabulario causal")
    if re.search(r"https?://|www\.", texto):
        probs.append("contiene enlaces")
    return probs


def verify_discovery(facts: list[Fact], payload: dict, strict: bool = True) -> dict:
    """Valida lo que devolvió la IA (o lo que el usuario editó). Cada texto cita hechos que existen y usa solo cifras de los hechos que cita;
    sin vocabulario causal ni enlaces; las hipótesis traen qué validar. En modo estricto la hoja debe tener la estructura completa
    (titular, al menos 2 de datos, 1 de significado y 1 acción) y cruzar al menos dos temas."""
    byid = {f.id: f for f in facts}
    out = {"ok": False, "problemas": [], "titulo": "", "angulo": "", "titular": {"texto": "", "hechos": [], "ok": False, "problemas": []}, "viñetas": []}
    if not isinstance(payload, dict):
        out["problemas"].append("respuesta con formato inválido")
        return out
    titulo = str(payload.get("titulo") or "").strip()
    if not titulo or len(titulo) > 64:
        out["problemas"].append("falta el título o es demasiado largo (máximo 64 caracteres)")
    elif re.search(r"\d", YEAR.sub("", titulo)):
        out["problemas"].append("el título no debe llevar cifras")
    out["titulo"], out["angulo"] = titulo, str(payload.get("angulo") or "").strip()[:120]
    temas: set[str] = set()
    tit = payload.get("titular")
    if isinstance(tit, dict) and tit.get("texto"):
        ids = [str(x).strip() for x in tit.get("hechos") or []] if isinstance(tit.get("hechos"), list) else []
        texto = str(tit["texto"]).strip()
        probs = _check_text(texto, "", ids, byid, MAX_TITULAR, need_new=True)
        out["titular"] = {"texto": bold_numbers(texto) if not probs else texto, "hechos": ids, "ok": not probs, "problemas": probs,
                          "evidencia": [byid[i].texto for i in ids if i in byid]}
        temas |= {byid[i].tema for i in ids if i in byid}
    elif strict:
        out["problemas"].append("falta el titular del hallazgo")
    items = payload.get("viñetas") if isinstance(payload.get("viñetas"), list) else payload.get("vinetas")
    if not isinstance(items, list) or not ((3 if strict else 1) <= len(items) <= MAX_BULLETS):
        out["problemas"].append(f"se esperan entre {3 if strict else 1} y {MAX_BULLETS} viñetas")
        return out
    for it in items:
        d = it if isinstance(it, dict) else {}
        seccion = str(d.get("seccion") or "").strip().lower()
        if seccion not in SECCIONES:
            seccion = next((k for k, v in SECCIONES.items() if v[0] == str(d.get("tipo") or "").strip().lower()), "")
        texto, validar = str(d.get("texto") or "").strip(), str(d.get("validar") or "").strip()
        ids = [str(x).strip() for x in d.get("hechos") or []] if isinstance(d.get("hechos"), list) else []
        probs = [] if seccion else ["sección inválida (datos, significado, hipotesis o accion)"]
        probs += _check_text(texto, validar, ids, byid, MAX_LEN, need_new=seccion in ("datos", "significado", "hipotesis"))
        if seccion == "hipotesis" and not validar:
            probs.append("una hipótesis debe indicar qué validar")
        temas |= {byid[i].tema for i in ids if i in byid}
        out["viñetas"].append({"ok": not probs, "problemas": probs, "seccion": seccion, "tipo": SECCIONES.get(seccion, ("",))[0], "validar": validar, "hechos": ids,
                               "texto": bold_numbers(texto) if not probs else texto, "evidencia": [byid[i].texto for i in ids if i in byid]})
    good = [b for b in out["viñetas"] if b["ok"]]
    if strict:
        for sec, mn in MIN_STRICT.items():
            if sum(1 for b in good if b["seccion"] == sec) < mn:
                out["problemas"].append(f"faltan viñetas válidas en «{SECCIONES[sec][1]}» (mínimo {mn})")
        if len(temas) < 2:
            out["problemas"].append("el descubrimiento debe cruzar al menos dos temas distintos")
        nuevos = {i for b in good for i in b["hechos"] if i in byid and byid[i].nuevo}
        if len(nuevos) < 2:
            out["problemas"].append("debe aportar al menos dos hechos nuevos que no estén ya en las otras diapositivas")
        if out["titular"]["texto"] and not out["titular"]["ok"]:
            out["problemas"].append("el titular no pasa la verificación")
    else:
        if len(good) != len(out["viñetas"]):
            out["problemas"].append("hay viñetas que no pasan la verificación")
        if out["titular"]["texto"] and not out["titular"]["ok"]:
            out["problemas"].append("el titular no pasa la verificación")
    out["ok"] = not out["problemas"]
    return out
