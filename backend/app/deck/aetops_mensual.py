"""Relleno de la plantilla AETOPS mensual (11 diapositivas) con datos del motor.

Spec en código para la versión 1 de la plantilla (nombres de shapes de `Resultados_AETOP_Agosto_2026`).
Si la plantilla cambia, `TemplateMismatch` lo dice explícitamente (no se rellena a ciegas).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal

from .. import format as F
from ..calc import indicators as ind
from ..models import Group, Period
from ..narrative.aetops import Box, check as check_narrative, compose_aetops_mensual
from ..narrative.writer import Para, to_paragraphs, verify_edited
from ..pipeline import Result
from . import pptx_ops as ops

DATA_RX = re.compile(r"\d")
METRICS = ("monto", "piezas", "pacientes", "pedidos", "ticket", "productos")


class TemplateMismatch(Exception):
    pass


class DataMissing(Exception):
    pass


@dataclass
class FillReport:
    notes: list[str] = field(default_factory=list)
    stale: list[str] = field(default_factory=list)
    omitted_categories: list[str] = field(default_factory=list)
    titles_fixed: list[str] = field(default_factory=list)
    bound: list[tuple[int, str]] = field(default_factory=list)      # (n.º de diapositiva, shape)
    narrative: dict = field(default_factory=dict)                   # clave -> [Para] (con tipo, regla y cifras)
    narrative_problems: list[str] = field(default_factory=list)     # cifras sin evidencia, vocabulario causal…
    edited_unverified: list[str] = field(default_factory=list)      # ediciones manuales con cifras nuevas


def fit_label(label: str) -> str:
    """La 1.ª columna es estrecha: 'Septiembre' (10) no cabe y parte la fila en dos; el propio deck
    ya abrevia ('Oct', 'Nov'). Solo se abrevia lo que excede 9 caracteres."""
    return label if len(label) <= 9 else label[:3]


# ----------------------------------------------------------------------------- formato por columna
def fmt_metric(key: str, v) -> str:
    if key in ("monto", "ticket"):
        return F.fmt_money(v, 0)
    if key == "v_paciente":
        return F.fmt_money(v, 2)
    if key == "size_b":
        return F.fmt_num(v, 2)
    if key == "share":
        return F.fmt_pct(v, 0, sign=False)
    return F.fmt_num(v, 0)


class TW:
    """Envoltorio de tabla: escribe celdas y recuerda cuáles (por coordenadas, no por id de nodo)."""

    def __init__(self, n: int, name: str, shape, table, rep: FillReport):
        self.n, self.name, self.shape, self.t, self.rep = n, name, shape, table, rep
        self.touched: set[tuple[int, int]] = set()
        self.skip_rows: set[int] = set()            # filas que se eliminarán: no cuentan como datos viejos

    def cell(self, r: int, c: int):
        return self.t.cell(r, c)

    @property
    def nrows(self) -> int:
        return len(self.t.rows)

    def put(self, r: int, c: int, text: str, **kw):
        ops.set_cell(self.t.cell(r, c), text, **kw)
        self.touched.add((r, c))

    def blank(self, r: int, c: int):
        if not self.t.cell(r, c).is_spanned:
            self.put(r, c, "", fill=None)

    def delta(self, r: int, c: int, v):
        style = ops.delta_style(v.v, 0)
        self.put(r, c, F.fmt_pct(v, 0, sign=False), fill=style[0] if style else None,
                 font=style[1] if style else None)

    def finish(self):
        self.check_stale()
        ops.sync_frame_height(self.shape)

    def check_stale(self):
        for r, row in enumerate(self.t.rows):
            if r in self.skip_rows:
                continue
            for c, cell in enumerate(row.cells):
                if (r, c) not in self.touched and not cell.is_spanned and DATA_RX.search(ops.cell_text(cell)):
                    self.rep.stale.append(f"diap. {self.n} '{self.name}' fila {r} col {c}: '{ops.cell_text(cell)[:30]}'")


class Filler:
    def __init__(self, prs, rep: FillReport):
        self.prs, self.rep = prs, rep

    def slide(self, n: int):
        return self.prs.slides[n - 1]

    def shape(self, n: int, name: str):
        try:
            sh = ops.shape_by_name(self.slide(n), name)
        except KeyError as e:
            raise TemplateMismatch(f"Diapositiva {n}: {e}") from None
        self.rep.bound.append((n, name))
        return sh

    def table(self, n: int, name: str, rows: int | None = None, cols: int | None = None) -> TW:
        sh = self.shape(n, name)
        if not sh.has_table:
            raise TemplateMismatch(f"Diapositiva {n}: '{name}' ya no es una tabla.")
        t = sh.table
        if (rows and len(t.rows) != rows) or (cols and len(t.columns) != cols):
            raise TemplateMismatch(
                f"Diapositiva {n}: '{name}' mide {len(t.rows)}x{len(t.columns)}; se esperaba {rows}x{cols}.")
        return TW(n, name, sh, t, self.rep)


# ----------------------------------------------------------------------------- tablas
def fill_panorama(fl: Filler, n: int, yoy: Group, mom: Group):
    w = fl.table(n, "Tabla 3", rows=11, cols=9)
    keys = ["monto", "piezas", "pacientes", "pedidos", "ticket", "productos", "size_b", "v_paciente"]
    for r_prev, g in ((2, yoy), (8, mom)):
        for off, side in ((0, g.previous), (1, g.current)):
            w.put(r_prev + off, 0, fit_label(side.label))
            for c, k in enumerate(keys, 1):
                w.put(r_prev + off, c, fmt_metric(k, side.values[k]))
        for c, k in enumerate(keys, 1):
            w.delta(r_prev + 2, c, g.pct[k])
    w.finish()


def fill_grouped(fl: Filler, n: int, name: str, tbl, header_cols: int = 8):
    w = fl.table(n, name, cols=header_cols)
    have = (w.nrows - 2) // 4
    ops.resize_blocks(w.t, 2, 4, have, len(tbl.groups))
    for c in range(1, header_cols):                                   # fila-título: solo 'YoY'/'MoM'
        w.blank(0, c)
    keys = ["monto", "piezas", "pacientes", "pedidos", "ticket", "productos", "share"]
    for i, g in enumerate(tbl.groups):
        r0 = 2 + 4 * i
        w.put(r0, 0, g.name)
        for c in range(1, header_cols):
            w.put(r0, c, "\u00a0")
        for off, side in ((1, g.previous), (2, g.current)):
            w.put(r0 + off, 0, fit_label(side.label))
            for c, k in enumerate(keys, 1):
                w.put(r0 + off, c, fmt_metric(k, side.values[k]))
        w.put(r0 + 3, 0, "")
        for c, k in enumerate(keys, 1):
            w.delta(r0 + 3, c, g.pct[k])
    w.finish()


def fill_grouped_starts(fl: Filler, n: int, name: str, tbl, starts: list[int], rows: int, cols: int = 8):
    """Como fill_grouped pero con bloques de 4 filas en posiciones fijas (puede haber filas separadoras).
    Los bloques sobrantes se eliminan junto con su separador."""
    w = fl.table(n, name, rows=rows, cols=cols)
    groups = tbl.groups
    used = min(len(groups), len(starts))
    if len(groups) > len(starts):
        fl.rep.notes.append(f"Diap. {n} '{name}': {len(groups)} grupos y la plantilla admite {len(starts)}; "
                            f"se omiten: {', '.join(g.name for g in groups[len(starts):])}.")
    for c in range(1, cols):
        w.blank(0, c)
    keys = ["monto", "piezas", "pacientes", "pedidos", "ticket", "productos", "share"]
    for g, r0 in zip(groups[:used], starts):
        w.put(r0, 0, g.name)
        for c in range(1, cols):
            w.put(r0, c, "\u00a0")
        for off, side in ((1, g.previous), (2, g.current)):
            w.put(r0 + off, 0, fit_label(side.label))
            for c, k in enumerate(keys, 1):
                w.put(r0 + off, c, fmt_metric(k, side.values[k]))
        w.put(r0 + 3, 0, "")
        for c, k in enumerate(keys, 1):
            w.delta(r0 + 3, c, g.pct[k])
    if used < len(starts):
        first_del = (starts[used - 1] + 4) if used else starts[0]
        w.skip_rows.update(range(first_del, w.nrows))
    w.check_stale()
    if used < len(starts):
        ops.delete_rows(w.t, first_del, w.nrows)
    ops.sync_frame_height(w.shape)


def _fill_cat_block(w: TW, r0: int, g: Group | None):
    keys = ["monto", "piezas", "pacientes", "pedidos", "ticket", "productos", "share"]
    if g is None:                                                      # bloque sin categoría: se vacía
        for r in range(r0, r0 + 3):
            for c in range(9):
                w.blank(r, c)
        return
    w.put(r0, 0, fit_label(g.previous.label))
    w.put(r0, 1, g.name)
    w.put(r0 + 1, 0, fit_label(g.current.label))
    for c, k in enumerate(keys, 2):
        w.put(r0, c, fmt_metric(k, g.previous.values[k]))
        w.put(r0 + 1, c, fmt_metric(k, g.current.values[k]))
        w.delta(r0 + 2, c, g.pct[k])
    w.put(r0 + 2, 0, "")
    w.put(r0 + 2, 1, "")


def fill_cat_blocks(fl: Filler, n: int, name: str, blocks: list[tuple[int, list[Group | None], int]], rows: int,
                    has_title: bool = True):
    """blocks = [(fila_inicial_de_datos, [grupo o None por bloque de 3 filas], filas_separadoras_previas)].
    La fila r0-2 es el título. Los bloques sin categoría se ELIMINAN (y la tabla secundaria completa si
    queda vacía); la primera tabla conserva al menos título y cabecera."""
    w = fl.table(n, name, rows=rows, cols=9)
    for r0, gs, _ in blocks:
        for c in range(1, 9 if has_title else 0):                       # fila-título: solo 'YoY'/'MoM'
            w.blank(r0 - 2, c)
        for i, g in enumerate(gs):
            _fill_cat_block(w, r0 + 3 * i, g)
    w.check_stale()                                                     # antes de mover filas
    for idx in range(len(blocks) - 1, -1, -1):                          # de abajo hacia arriba
        r0, gs, spacer = blocks[idx]
        used = sum(g is not None for g in gs)
        end = r0 + 3 * len(gs)
        if used == 0 and idx > 0:
            ops.delete_rows(w.t, r0 - (2 if has_title else 1) - spacer, rows if idx == len(blocks) - 1 else end)
        elif used < len(gs):
            ops.delete_rows(w.t, r0 + 3 * used, end)
    ops.sync_frame_height(w.shape)


def fill_productos(fl: Filler, n: int, name: str, rows, capacity: int, rep: FillReport, sivec: bool = True,
                   headers: dict[int, str] | None = None):
    """Con `sivec` la tabla tiene 7 columnas; sin él, 6 (Producto, AETOP, Canales, Actual, Anterior, Delta).
    `headers` {columna: texto} actualiza rótulos fijos de la plantilla (p. ej. 'Venta Q1 Actual 2026')."""
    w = fl.table(n, name, cols=7 if sivec else 6)
    for c, text in (headers or {}).items():
        w.put(0, c, text)
    rows = rows[:capacity]
    if len(rows) < capacity:
        rep.notes.append(f"Diap. {n} '{name}': {len(rows)} producto(s) de {capacity}; se eliminaron filas.")
    ops.resize_rows(w.t, 1, w.nrows, 1, max(len(rows), 1))
    o = 0 if sivec else -1                                              # desplazamiento de columnas
    new = 0
    for i, r in enumerate(rows, 1):
        if sivec:
            w.put(i, 0, r.sivec)
        w.put(i, 1 + o, r.producto)
        w.put(i, 2 + o, r.aetop)
        w.put(i, 3 + o, F.fmt_num(r.canales, 0))
        w.put(i, 4 + o, F.fmt_money(r.actual, 0))
        w.put(i, 5 + o, "" if r.anterior.v is None else F.fmt_money(r.anterior, 0))     # sin venta previa: vacío
        style = ops.delta_style(r.delta.v)
        w.put(i, 6 + o, F.fmt_money(r.delta, 0), fill=style[0] if style else None, font=style[1] if style else None)
        new += r.delta.status == "new_item"
    if not rows:
        for c in range(7 if sivec else 6):
            w.blank(1, c)
    if new:
        rep.notes.append(f"Diap. {n} '{name}': {new} producto(s) sin venta previa (Delta = venta actual).")
    w.finish()


def fill_negados(fl: Filler, n: int, alta, producto, rep: FillReport):
    # --- por línea (Alta)
    w = fl.table(n, "Tabla 7", rows=4, cols=5)
    arows = sorted(alta.rows, key=lambda r: r.monto.v or Decimal(0), reverse=True) if alta else []
    ops.resize_rows(w.t, 1, 4, 1, max(len(arows), 1))
    for i, r in enumerate(arows, 1):
        w.put(i, 0, r.name)
        w.put(i, 1, F.fmt_num(r.pedidos, 0))
        w.put(i, 2, F.fmt_num(r.cantidad, 0))
        w.put(i, 3, F.fmt_money(r.monto, 0))
        w.put(i, 4, F.fmt_pct(r.share, 0, sign=False))
    w.finish()
    # --- por producto: Top 10 + fila de totales (Σ de TODOS los negados) + monto negado total
    w = fl.table(n, "Tabla 2", rows=14, cols=6)
    allp = producto.rows if producto else []
    prows = sorted(allp, key=lambda r: r.monto.v or Decimal(0), reverse=True)[:10]
    ops.resize_rows(w.t, 1, 11, 1, max(len(prows), 1))
    for i, r in enumerate(prows, 1):
        w.put(i, 0, r.name)
        w.put(i, 1, r.alta)
        w.put(i, 2, F.fmt_num(r.pedidos, 0), fill=None)                 # sin el mapa de calor de Excel
        w.put(i, 3, F.fmt_num(r.cantidad, 0), fill=None)
        w.put(i, 4, F.fmt_money(r.monto, 0), fill=None)
        w.put(i, 5, F.fmt_pct(r.share, 0, sign=False), fill=None)
    sums = 1 + max(len(prows), 1)
    src = arows or allp
    sp = sum((r.pedidos.v for r in src if r.pedidos.v is not None), Decimal(0))
    sc = sum((r.cantidad.v for r in src if r.cantidad.v is not None), Decimal(0))
    for c in (0, 1, 4, 5):
        w.blank(sums, c)
    w.put(sums, 2, F.fmt_num(ind.derived(sp, "sum(pedidos)"), 0), fill=None)
    w.put(sums, 3, F.fmt_num(ind.derived(sc, "sum(cantidad)"), 0), fill=None)
    total = alta.total if alta else (producto.total if producto else ind.make(None))
    w.put(w.nrows - 1, 4, F.fmt_money(total, 0))
    w.finish()
    rep.notes.append("Tabla de negados sin el mapa de calor de Excel (la escala de color no se reproduce).")


# ----------------------------------------------------------------------------- categorías
def pick_categories_yoy(groups: list[Group]) -> tuple[list[Group], list[Group], list[Group]]:
    """Orden por venta actual; 4 en la primera tabla, 3 en la segunda (capacidad de la plantilla)."""
    gs = sorted(groups, key=lambda g: g.current.values["monto"].v or Decimal(0), reverse=True)
    return gs[:4], gs[4:7], gs[7:]


def pick_categories_mom(groups: list[Group]) -> tuple[list[Group], list[Group], list[Group]]:
    """Izquierda: categorías que suben; derecha: las que bajan (como el original). 4 por tabla."""
    key = lambda g: g.current.values["monto"].v or Decimal(0)           # noqa: E731
    up = sorted([g for g in groups if g.pct["monto"].v is not None and g.pct["monto"].v > 0], key=key, reverse=True)
    down = sorted([g for g in groups if g.pct["monto"].v is not None and g.pct["monto"].v < 0], key=key, reverse=True)
    shown = {id(g) for g in up[:4] + down[:4]}
    return up[:4], down[:4], [g for g in groups if id(g) not in shown]


# ----------------------------------------------------------------------------- orquestación
CROSSED_TITLES = {
    2: ("CuadroTexto 11", "Análisis de Canales YoY"),
    3: ("CuadroTexto 12", "Análisis de Canales MoM"),
    4: ("CuadroTexto 3", "Análisis Líneas AETOP YoY"),
    5: ("CuadroTexto 19", "Análisis Líneas AETOP MoM"),
}


NARR = {                      # clave de narrativa -> (diapositiva, shape de la plantilla)
    "panorama": (1, "CuadroTexto 6"), "canal_yoy": (2, "CuadroTexto 6"), "canal_mom": (3, "CuadroTexto 17"),
    "linea_yoy": (4, "CuadroTexto 6"), "linea_mom": (5, "CuadroTexto 6"), "productos": (6, "CuadroTexto 7"),
    "crecimiento": (7, "CuadroTexto 21"), "decrecimiento": (7, "CuadroTexto 27"), "cat_yoy": (8, "CuadroTexto 24"),
    "cat_mom": (9, "CuadroTexto 8"), "negados": (10, "CuadroTexto 6"), "conclusiones": (11, "CuadroTexto 12"),
}


def fill_aetops_mensual(prs, result: Result, period: Period, narrative: dict[str, list[str]] | None = None,
                        fix_titles: bool = True) -> FillReport:
    """`narrative`: ediciones manuales {clave: [párrafos]} que sustituyen al texto generado (se verifican)."""
    rep = FillReport()
    fl = Filler(prs, rep)
    T = result.tables

    def tab(key):
        if key not in T:
            raise DataMissing(f"Falta la tabla '{key}' en el resultado del motor.")
        return T[key]

    pano_yoy, pano_mom = tab("aetops.panorama.yoy").groups[0], tab("aetops.panorama.mom").groups[0]
    canal_yoy, canal_mom = tab("aetops.canal.yoy"), tab("aetops.canal.mom")
    linea_yoy, linea_mom = tab("aetops.linea.yoy"), tab("aetops.linea.mom")
    cat_yoy, cat_mom = tab("aetops.categoria.yoy"), tab("aetops.categoria.mom")
    prod = result.products
    for k in ("top", "growth", "decline"):
        if f"aetops.productos.{k}" not in prod:
            raise DataMissing(f"Falta el bloque de productos '{k}'.")
    neg_alta, neg_prod = result.negados.get("aetops.negados.alta"), result.negados.get("aetops.negados.producto")

    # --- narrativa: capacidad de cada cuadro -> compositor -> verificación
    boxes = {k: Box(*ops.narrative_box(fl.shape(n, name))) for k, (n, name) in NARR.items()}
    a, b, om_y = pick_categories_yoy(cat_yoy.groups)
    up, down, om_m = pick_categories_mom(cat_mom.groups)
    narr = compose_aetops_mensual(result, period, boxes, a + b, up + down)
    rep.narrative_problems = check_narrative(narr)
    rep.narrative = narr
    for key, texts in (narrative or {}).items():
        allowed = set().union(*(p.nums for ps in narr.values() for p in ps))
        edited = [Para(t, "hecho", 0, edited=True, nums=set()) for t in texts if t != ""]
        rep.edited_unverified += [f"{key}: {x}" for p in edited for x in verify_edited(p.plain, allowed)]
        narr[key] = edited + [p for p in narr.get(key, []) if not p.visible]

    # 1 · Panorama
    fill_panorama(fl, 1, pano_yoy, pano_mom)
    # 2-5 · canales y líneas (los títulos del original están cruzados: se corrigen y se informa)
    for n, name, tbl in ((2, "Tabla 2", canal_yoy), (3, "Tabla 2", canal_mom), (4, "Tabla 8", linea_yoy),
                         (5, "Tabla 2", linea_mom)):
        fill_grouped(fl, n, name, tbl)
        if fix_titles:
            tname, text = CROSSED_TITLES[n]
            sh = fl.shape(n, tname)
            if ops_text(sh) != text:
                rep.titles_fixed.append(f"diap. {n}: '{ops_text(sh)}' → '{text}'")
                ops.set_simple_text(sh, text)
    # 6 · productos · 7 · crecimiento / decrecimiento
    fill_productos(fl, 6, "Tabla 3", prod["aetops.productos.top"].rows, 20, rep)
    fill_productos(fl, 7, "Tabla 2", prod["aetops.productos.growth"].rows, 10, rep)
    fill_productos(fl, 7, "Tabla 7", prod["aetops.productos.decline"].rows, 10, rep)
    # 8 · categorías YoY (dos tablas apiladas en un mismo objeto: 4 + 3 bloques) · 9 · MoM (suben | bajan)
    pad = lambda lst, k: lst + [None] * (k - len(lst))                   # noqa: E731
    fill_cat_blocks(fl, 8, "Tabla 2", [(2, pad(a, 4), 0), (18, pad(b, 3), 2)], rows=27)
    fill_cat_blocks(fl, 9, "Tabla 3", [(2, pad(up, 4), 0)], rows=14)
    fill_cat_blocks(fl, 9, "Tabla 12", [(2, pad(down, 4), 0)], rows=14)
    rep.omitted_categories += [g.name for g in om_y] + [f"{g.name} (MoM)" for g in om_m]
    # 10 · negados
    fill_negados(fl, 10, neg_alta, neg_prod, rep)
    # textos
    for key, (n, name) in NARR.items():
        ops.set_paragraphs(fl.shape(n, name), to_paragraphs(narr[key]))
    if rep.omitted_categories:
        rep.notes.append("Categorías no mostradas por capacidad de la plantilla (selección editorial pendiente): "
                         + ", ".join(rep.omitted_categories))
    return rep


def ops_text(shape) -> str:
    return shape.text_frame.text.strip()
