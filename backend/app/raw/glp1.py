"""GLP-1 desde datos crudos (docs/CONTRATO_DATOS.md): `ventas` + `catalogo` + `trafico` (+ `negados`) -> los mismos GBlock
que produce el importador del libro operativo (región, pago, entrega, productos, programas, edad, sexo, dispositivo,
fuentes, estado, edad por producto, producto×sexo, negados y embudo).

Ventas (pedidos, monto, pacientes) salen de `ventas`; visitas, usuarios y embudo salen de `trafico` (analítica web, otro
sistema: no se espera que cuadre con las ventas). %Δ: contra el periodo anterior (MoM o QoQ) y contra el mismo periodo del
año anterior (YoY). Los usuarios de analítica se suman entre filas: es aproximado cuando se cruzan SKU (aviso informativo).
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal

from ..calc import indicators as ind
from ..models import Finding, GBlock, GRow, Lineage, Period, Value
from .common import norm, read_tables, to_date

SPECS = {
    "ventas": ["fecha_pedido", "id_pedido", "id_paciente", "paciente_nuevo", "sku", "canal", "estado", "piezas", "monto_venta",
               "forma_pago", "modo_entrega"],
    "catalogo": ["sku", "producto"],
    "trafico": ["mes", "vista", "valor", "sku", "visitas"],
    "negados": ["producto", "pedidos", "cantidad_negada", "monto_negado"],
}
TRAF_METRICS = {"visitas": "visitas", "usuarios": "usuarios", "usuarios_nuevos": "nuevos", "usuarios_recurrentes": "recurrentes",
                "add_to_cart": "atc"}
VISTAS = {"edad": "edad", "sexo": "sexo", "dispositivo": "dispositivo", "fuente": "fuentes", "estado": "trafico_estado"}
PAID_RX = re.compile(r"cpc|ppc|paid|cpm|display|cross.?network|retarget|sponsor", re.I)
UNASSIGNED_RX = re.compile(r"unassigned|not set|\(other\)|sin asignar", re.I)


def clasificar_fuente(valor: str) -> str:
    """Pago / Orgánico / Sin asignar a partir de la fuente/medio (ej. 'google / cpc', 'Paid Social', 'Organic Search')."""
    if UNASSIGNED_RX.search(valor):
        return "Sin asignar"
    if re.search(r"organic", valor, re.I):
        return "Orgánico"
    return "Pago" if PAID_RX.search(valor) else "Orgánico"


FUNNEL = [("ver producto", "vistas_producto"), ("agregar a carrito", "add_to_cart"), ("iniciar compra", "begin_checkout"),
          ("compra", "compras"), ("carritos abandonados", "carritos_abandonados")]


def _windows(period: Period):
    y, i = period.year, period.index
    if period.periodicity == "mensual":
        pm, py = (i - 1, y) if i > 1 else (12, y - 1)
        return {"cur": (y, {i}), "prev": (py, {pm}), "yoy": (y - 1, {i})}
    months = lambda q: {3 * (q - 1) + k for k in (1, 2, 3)}      # noqa: E731
    pq, py = (i - 1, y) if i > 1 else (4, y - 1)
    return {"cur": (y, months(i)), "prev": (py, months(pq)), "yoy": (y - 1, months(i))}


@dataclass
class _M:
    monto: Decimal = Decimal(0)
    piezas: Decimal = Decimal(0)
    pedidos: set = field(default_factory=set)
    pacientes: set = field(default_factory=set)
    nuevos: set = field(default_factory=set)


@dataclass
class _T:
    v: dict = field(default_factory=lambda: defaultdict(Decimal))


def _d(x, default=None):
    d = ind.to_dec(x)
    return default if d is None else d


def _val(d: Decimal | None, tag: str, file: str, sheet: str) -> Value:
    if d is None:
        return ind.make(None)
    return Value(d, "zero" if d == 0 else "ok", Lineage(file, sheet, "agregado", tag))


def build(path, period: Period) -> tuple[dict[str, GBlock], GBlock | None, list[Finding]]:
    tabs, f = read_tables(path, SPECS, optional={"negados", "trafico"})
    file = str(path).replace("\\", "/").split("/")[-1]
    if any(x.severity == "block" for x in f):
        return {}, None, f
    ventas, trafico = tabs["ventas"], tabs.get("trafico", [])
    cat = {str(r["sku"]).strip(): str(r.get("producto") or "").strip() for r in tabs["catalogo"] if r.get("sku") is not None}
    wins = _windows(period)
    which = lambda d: next((k for k, (y, ms) in wins.items() if d.year == y and d.month in ms), None)   # noqa: E731

    # ---------------- ventas
    money: dict[tuple, _M] = defaultdict(_M)           # (bloque, ventana, clave) -> acumulado
    bad_date = bad_num = empty = unknown = neg = 0
    orders_cur: set = set()
    has_loyalty = any(r.get("programa_lealtad") not in (None, "") for r in ventas)
    for r in ventas:
        d = to_date(r.get("fecha_pedido"))
        if d is None:
            bad_date += 1
            continue
        w = which(d)
        if w is None:
            continue
        monto, piezas = ind.to_dec(r.get("monto_venta")), ind.to_dec(r.get("piezas"))
        if monto is None or piezas is None:
            bad_num += 1
            continue
        pid, pac, sku = (str(r.get(k) or "").strip() for k in ("id_pedido", "id_paciente", "sku"))
        if not (pid and pac and sku):
            empty += 1
            continue
        prod = cat.get(sku)
        if prod is None:
            unknown += 1
            continue
        if monto < 0 or piezas < 0:
            neg += 1
        if w == "cur":
            orders_cur.add(pid)
        new = str(r.get("paciente_nuevo") or "").strip().upper() in ("SI", "SÍ", "S", "1", "TRUE")
        dims = {"region": str(r.get("region") or r.get("estado") or "").strip(), "pago": str(r.get("forma_pago") or "").strip(),
                "entrega": str(r.get("modo_entrega") or "").strip(), "productos": prod}
        if has_loyalty:
            dims["programas"] = str(r.get("programa_lealtad") or "").strip() or "Sin programa"
        for blk, key in dims.items():
            if not key:
                continue
            a = money[(blk, w, key)]
            a.monto += monto
            a.piezas += piezas
            a.pedidos.add(pid)
            a.pacientes.add(pac)
            if new:
                a.nuevos.add(pac)
    for n, code, msg in ((bad_date, "RAW_DATE_UNREADABLE", "con fecha ilegible"), (bad_num, "RAW_NUMBER_UNREADABLE", "con piezas o monto ilegibles"),
                         (empty, "RAW_ID_EMPTY", "sin id_pedido, id_paciente o sku"), (unknown, "RAW_SKU_NOT_IN_CATALOG", "con un SKU que no está en el catálogo")):
        if n:
            f.append(Finding(code, "block", f"Ventas: {n} fila(s) {msg}.", "ventas"))
    if neg:
        f.append(Finding("RAW_NEGATIVE_VALUES", "warn", f"Ventas: {neg} fila(s) con valores negativos (no se tratan como devolución).", "ventas"))
    if not any(w == "cur" for (_b, w, _k) in money):
        f.append(Finding("RAW_PERIOD_EMPTY", "block", "Ventas: no hay datos del periodo del reporte.", "ventas"))
    for w, name in (("prev", "el periodo anterior"), ("yoy", "el mismo periodo del año anterior")):
        if not any(k == w for (_b, k, _x) in money):
            f.append(Finding("RAW_WINDOW_MISSING", "warn", f"Ventas: no hay datos de {name}; no se calcula ese %Δ.", "ventas"))

    # ---------------- tráfico
    traf: dict[tuple, dict] = defaultdict(lambda: defaultdict(Decimal))   # (bloque, ventana, clave, dim2) -> métricas
    funnel: dict[str, dict] = defaultdict(lambda: defaultdict(Decimal))     # ventana -> conteos (nivel sitio)
    tbad = 0
    for r in trafico:
        d = to_date(r.get("mes"))
        if d is None:
            tbad += 1
            continue
        w = which(d)
        if w is None:
            continue
        vista, valor = norm(r.get("vista")), str(r.get("valor") or "").strip()
        sku = str(r.get("sku") or "").strip()
        m = {out: _d(r.get(src), Decimal(0)) for src, out in TRAF_METRICS.items()}
        m["rebotes"] = _d(r.get("sesiones_rebote"), Decimal(0))
        m["segundos"] = _d(r.get("segundos_interaccion_total"), Decimal(0))
        if vista == "general" and not sku:
            for _, col in FUNNEL:
                funnel[w][col] += _d(r.get(col), Decimal(0))
            continue
        blk = VISTAS.get(vista)
        if blk is None or not valor:
            continue
        targets = []
        if not sku:
            targets.append((blk, valor, ""))
            if blk == "fuentes":
                targets.append(("canal_resumen", clasificar_fuente(valor), ""))
        elif blk == "edad":
            p = cat.get(sku)
            if p:
                targets.append((f"edad_producto:{norm(p)}", valor, p))
        elif blk == "sexo":
            p = cat.get(sku)
            if p:
                targets.append(("producto_sexo", p, valor))
        for b, key, dim2 in targets:
            acc = traf[(b, w, key, dim2)]
            for k, v in m.items():
                acc[k] += v
    if tbad:
        f.append(Finding("RAW_DATE_UNREADABLE", "block", f"Tráfico: {tbad} fila(s) con mes ilegible.", "trafico"))
    if trafico:
        f.append(Finding("TRAFICO_USUARIOS_APROX", "info", "Usuarios de analítica: se suman entre filas; es aproximado donde se cruzan SKU o fuentes.", "trafico"))
        if not any(w == "cur" for (_b, w, _k, _d2) in traf) and not funnel.get("cur"):
            f.append(Finding("RAW_PERIOD_EMPTY", "block", "Tráfico: no hay datos del periodo del reporte.", "trafico"))
    if any(x.severity == "block" for x in f):
        return {}, None, f

    blocks: dict[str, GBlock] = {}

    def pct(cur: Value, other: Value, tag: str) -> Value | None:
        return ind.pct_change(cur, other, tag) if other is not None else None

    # bloques de dinero
    for blk in ("region", "pago", "entrega", "productos", "programas"):
        keys = {k for (b, w, k) in money if b == blk and w == "cur"}
        if not keys:
            continue
        rows = []
        for k in keys:
            def vals(w):
                a = money.get((blk, w, k))
                if a is None:
                    return None
                return {"pedidos": _val(Decimal(len(a.pedidos)), "distinct(id_pedido)", file, "ventas"), "monto": _val(a.monto, "sum(monto_venta)", file, "ventas"),
                        "piezas": _val(a.piezas, "sum(piezas)", file, "ventas"), "pacientes": _val(Decimal(len(a.pacientes)), "distinct(id_paciente)", file, "ventas"),
                        "pacientes_nuevos": _val(Decimal(len(a.nuevos)), "distinct(id_paciente nuevo)", file, "ventas")}
            cur = vals("cur")
            cur["ticket"] = ind.ratio(cur["monto"], cur["pedidos"], "monto/pedidos")
            row = GRow(k, "", cur)
            row.ticket_calc = cur["ticket"]
            for w, attr in (("prev", "engine_delta"), ("yoy", "delta_yoy")):
                o = vals(w)
                v = ind.pct_change(cur["monto"], o["monto"], f"monto vs {w}") if o else ind.derived(None, f"pct_change(monto vs {w})", "sin datos del periodo de comparación")
                setattr(row, attr, v)
            row.delta, row.delta_src = row.engine_delta, "engine"
            rows.append(row)
        rows.sort(key=lambda r: -(r.values["monto"].v or Decimal(0)))
        tot = ind.derived(sum((r.values["monto"].v for r in rows), Decimal(0)), "sum(monto)")
        for r in rows:
            r.share = ind.share(r.values["monto"], tot, "monto/total")
        blocks[blk] = GBlock(blk, "ventas", "agregado", rows, basis="money")

    # bloques de tráfico
    def tvals(acc):
        v = {"visitas": _val(acc["visitas"], "sum(visitas)", file, "trafico"), "usuarios": _val(acc["usuarios"], "sum(usuarios)", file, "trafico"),
             "atc": _val(acc["atc"], "sum(add_to_cart)", file, "trafico"), "recurrentes": _val(acc["recurrentes"], "sum(usuarios_recurrentes)", file, "trafico"),
             "nuevos": _val(acc["nuevos"], "sum(usuarios_nuevos)", file, "trafico")}
        if acc["visitas"]:
            v["rebote"] = ind.derived(acc["rebotes"] / acc["visitas"], "sesiones_rebote/visitas")
            v["tiempo"] = ind.derived(acc["segundos"] / acc["visitas"], "segundos/visitas")
        return v
    names = {b for (b, w, _k, _d2) in traf if w == "cur"}
    for b in sorted(names):
        keys = {(k, d2) for (bb, w, k, d2) in traf if bb == b and w == "cur"}
        rows = []
        for k, d2 in keys:
            cur = tvals(traf[(b, "cur", k, d2)])
            row = GRow(k, d2, cur)
            for w, attr in (("prev", "engine_delta"), ("yoy", "delta_yoy")):
                o = traf.get((b, w, k, d2))
                setattr(row, attr, ind.pct_change(cur["visitas"], tvals(o)["visitas"], f"visitas vs {w}") if o else
                        ind.derived(None, f"pct_change(visitas vs {w})", "sin datos del periodo de comparación"))
            row.delta, row.delta_src = row.engine_delta, "engine"
            rows.append(row)
        if b == "producto_sexo":
            rows.sort(key=lambda r: (r.key, r.dim2))
        elif b == "edad" or b.startswith("edad_producto"):
            rows.sort(key=lambda r: (int(m.group()) if (m := re.search(r"\d+", r.key)) else 999, r.key))
        else:
            rows.sort(key=lambda r: -(r.values["visitas"].v or Decimal(0)))
        tot = ind.derived(sum((r.values["visitas"].v for r in rows), Decimal(0)), "sum(visitas)")
        for r in rows:
            r.share = ind.share(r.values["visitas"], tot, "visitas/total")
        blocks[b] = GBlock(b, "trafico", "agregado", rows, basis="traffic")

    if "canal_resumen" in blocks:
        order = {"Pago": 0, "Orgánico": 1, "Sin asignar": 2}
        blocks["canal_resumen"].rows.sort(key=lambda r: order.get(r.key, 9))
        n_src = len({k for (b, w, k, _d) in traf if b == "fuentes" and w == "cur"})
        f.append(Finding("CANAL_CLASIFICADO", "info",
                         f"Canal Pago/Orgánico: {n_src} fuente(s)/medio clasificados por su medio (pago = cpc, ppc, paid, cpm, display, cross-network, retargeting; "
                         "orgánico = el resto; sin asignar aparte).", "trafico"))

    # negados (lista de productos sin stock)
    if "negados" in tabs:
        rows = []
        for r in tabs["negados"]:
            nm = str(r.get("producto") or "").strip()
            if not nm:
                continue
            vals = {"pedidos": ind.make(r.get("pedidos")), "piezas": ind.make(r.get("cantidad_negada")), "monto_negado": ind.make(r.get("monto_negado"))}
            row = GRow(nm, "", vals)
            row.ticket_calc = ind.ratio(vals["monto_negado"], vals["pedidos"], "monto_negado/pedidos")
            vals["ticket"] = row.ticket_calc
            row.delta, row.delta_src = ind.make(None), "none"
            rows.append(row)
        rows.sort(key=lambda r: -(r.values["monto_negado"].v or Decimal(0)))
        tot = ind.derived(sum((r.values["monto_negado"].v or Decimal(0) for r in rows), Decimal(0)), "sum(monto_negado)")
        for r in rows:
            r.share = ind.share(r.values["monto_negado"], tot, "monto_negado/total")
        blocks["negados"] = GBlock("negados", "negados", "agregado", rows, basis="negados")

    # embudo (nivel sitio): tasa = conteo ÷ 'Ver producto'
    fb = None
    if funnel.get("cur"):
        rows, base = [], None
        for stage, col in FUNNEL:
            raw = funnel["cur"].get(col)
            if col == "carritos_abandonados" and not raw:
                raw = funnel["cur"].get("add_to_cart", Decimal(0)) - funnel["cur"].get("compras", Decimal(0))
                note = "derivado: add_to_cart − compras"
            else:
                note = ""
            cnt = _val(raw, col, file, "trafico")
            if note:
                cnt = Value(cnt.v, cnt.status, cnt.src, note)
            base = base or cnt
            row = GRow(stage, "", {"conteo": cnt})
            row.values["tasa_calc"] = ind.ratio(cnt, base, "conteo/ver_producto")
            rows.append(row)
        fb = GBlock("embudo", "trafico", "agregado", rows, basis="funnel")
    # contraste: compras de analítica vs pedidos del sistema de ventas (solo aviso)
    if fb is not None and orders_cur:
        compras = next(r.values["conteo"].v for r in fb.rows if r.key == "compra")
        if compras is not None and abs(compras - len(orders_cur)) / len(orders_cur) > Decimal("0.2"):
            f.append(Finding("TRAFICO_PURCHASE_DIFFERS", "warn",
                             f"Compras de analítica ({compras:,.0f}) vs pedidos del sistema de ventas ({len(orders_cur):,}): difieren más de 20 %.", "trafico"))
    return blocks, fb, f
