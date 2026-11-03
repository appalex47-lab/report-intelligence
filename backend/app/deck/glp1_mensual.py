"""Relleno de la plantilla GLP-1 mensual (11 diapositivas; referencia: Resultados_GLP1_Agosto_2026).

Rellena en su lugar tablas y textos. Los resaltes de la plantilla (recuadros rojos y rellenos puntuales) eran manuales: se quitan
y se vuelve a marcar con recuadro rojo la fila con más visitas (o la de mayor venta) de cada tabla. La nota de la plantilla
("Nota: el 31 de agosto…") es del mes de referencia y se elimina. La plantilla no se modifica en estructura.
"""
from __future__ import annotations

import copy
import math
from decimal import Decimal

from lxml import etree
from pptx.oxml.ns import qn

from .. import format as F
from ..calc import indicators as ind
from ..models import GBlock, GRow, Period
from ..narrative.aetops import Box
from ..narrative.glp1 import check, compose_glp1, sx
from ..narrative.writer import Para, verify_edited
from ..qa.checks import ADDED
from . import pptx_ops as ops
from .aetops_mensual import DataMissing, FillReport, Filler

NARR = {"quien": (1, "TextBox 18"), "producto_sexo": (4, "CuadroTexto 3"), "region": (5, "CuadroTexto 6"), "pago": (6, "CuadroTexto 6"),
        "funnel": (7, "TextBox 17"), "productos": (8, "CuadroTexto 6"), "programas": (9, "CuadroTexto 6"),
        "fuentes": (10, "CuadroTexto 6"), "conclusiones": (11, "CuadroTexto 12")}
NOTES = {1: "TextBox 19", 2: "TextBox 17", 3: "TextBox 18", 4: "TextBox 17", 5: "TextBox 17", 6: "TextBox 17", 7: "TextBox 18",
         8: "TextBox 17", 9: "TextBox 17", 10: "TextBox 17", 11: "TextBox 17"}
REQUIRED = ["edad", "sexo", "dispositivo", "producto_sexo", "region", "trafico_estado", "pago", "entrega", "productos", "programas", "fuentes", "negados"]
RED = "FF0000"


# ----------------------------------------------------------------------------- formato de celdas
def hms(v) -> str:
    if v.v is None:
        return F.DASH
    s = int(F.quantize_half_up(v.v, 0))
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def cellfmt(kind: str, row: GRow) -> str:
    if kind == "key":
        return row.key
    if kind == "dim2":
        return sx(row.dim2)
    if kind == "share":
        return F.fmt_pct(row.share, 0, sign=False) if row.share else F.DASH
    if kind == "ticket":
        return F.fmt_money(row.values.get("ticket", ind.make(None)), 0)
    m, name = kind.split(":", 1)
    val = row.values.get(name, ind.make(None))
    return {"n": lambda: F.fmt_num(val, 0), "m": lambda: F.fmt_money(val, 0), "p": lambda: F.fmt_pct(val, 0, sign=False), "t": lambda: hms(val)}[m]()


def put_row(w, r: int, c0: int, spec: list[str], row: GRow | None, proto_row: int | None = None):
    """`proto_row`: fila de la que copiar el formato de texto cuando la celda de la plantilla está vacía (sin runs)."""
    for i, kind in enumerate(spec):
        c = c0 + i
        if w.t.cell(r, c).is_spanned:
            continue
        proto = w.t.cell(proto_row, c) if proto_row is not None else None
        if row is None:
            w.blank(r, c)
        elif kind == "delta":
            style = ops.delta_style(row.delta.v if row.delta is not None else None, 0)
            w.put(r, c, F.fmt_pct(row.delta if row.delta is not None else ind.make(None), 0, sign=False),
                  fill=style[0] if style else None, font=style[1] if style else None, proto=proto)
        else:
            w.put(r, c, cellfmt(kind, row), fill=None, proto=proto)


def fill_region(w, start: int, end: int, proto: int, rows: list[GRow], spec: list[str], c0: int = 0):
    """Región de filas [start, end): se ajusta a len(rows) filas y se escribe."""
    ops.resize_rows(w.t, start, end, proto, len(rows))
    for i, row in enumerate(rows):
        put_row(w, start + i, c0, spec, row)
    return start + len(rows)


# ----------------------------------------------------------------------------- resaltes (recuadro rojo)
def _line(tag: str, on: bool):
    ln = etree.Element(qn(f"a:{tag}"))
    if on:
        ln.set("w", "19050")
        ln.set("cap", "flat")
        ln.set("cmpd", "sng")
        ln.set("algn", "ctr")
        sf = etree.SubElement(ln, qn("a:solidFill"))
        etree.SubElement(sf, qn("a:srgbClr")).set("val", RED)
        etree.SubElement(ln, qn("a:prstDash")).set("val", "solid")
    else:
        etree.SubElement(ln, qn("a:noFill"))
    return ln


def _set_lines(cell, red: dict[str, bool]):
    tcPr = cell._tc.get_or_add_tcPr()
    for tag in ("lnL", "lnR", "lnT", "lnB"):
        old = tcPr.find(qn(f"a:{tag}"))
        is_red = old is not None and old.find(f".//{qn('a:srgbClr')}") is not None and old.find(f".//{qn('a:srgbClr')}").get("val") == RED
        want = red.get(tag)
        if want is None and (red or not is_red):
            continue                         # sin cambios en este borde; solo `_set_lines(cell, {})` quita los rojos existentes
        new = _line(tag, bool(want))
        if old is not None:
            tcPr.replace(old, new)
        else:
            order = ["lnL", "lnR", "lnT", "lnB"]
            pos = 0
            for t in order[:order.index(tag)]:
                if tcPr.find(qn(f"a:{t}")) is not None:
                    pos = list(tcPr).index(tcPr.find(qn(f"a:{t}"))) + 1
            tcPr.insert(pos, new)


def clear_red(table):
    for row in table.rows:
        for cell in row.cells:
            if not cell.is_spanned:
                _set_lines(cell, {})


def box_row(table, r: int, c0: int, c1: int):
    for c in range(c0, c1 + 1):
        cell = table.cell(r, c)
        if cell.is_spanned:
            continue
        _set_lines(cell, {"lnT": True, "lnB": True, "lnL": c == c0, "lnR": c == c1})


def best_row(rows: list[GRow], key: str) -> int | None:
    ok = [(i, r.values[key].v) for i, r in enumerate(rows) if key in r.values and r.values[key].v is not None]
    return max(ok, key=lambda t: t[1])[0] if ok else None


def box_cell(table, r: int, c: int):
    """Recuadro rojo alrededor de una celda; también el borde que comparten las vecinas, para que no quede una línea a medias."""
    cell = table.cell(r, c)
    if cell.is_spanned:
        return
    _set_lines(cell, {"lnT": True, "lnB": True, "lnL": True, "lnR": True})
    nr, nc = len(table.rows), len(table.columns)
    for dr, dc, tag in ((-1, 0, "lnB"), (1, 0, "lnT"), (0, -1, "lnR"), (0, 1, "lnL")):
        rr, cc = r + dr, c + dc
        if 0 <= rr < nr and 0 <= cc < nc and not table.cell(rr, cc).is_spanned:
            _set_lines(table.cell(rr, cc), {tag: True})


def _num(text: str) -> float | None:
    t = text.replace("$", "").replace(",", "").replace("%", "").strip()
    try:
        return float(t)
    except ValueError:
        return None


def mark_max(w, r0: int, r1: int, cols) -> list[int]:
    """Recuadra, en cada columna de KPI, la celda con el valor mayor entre las filas [r0, r1). Devuelve la fila con más
    marcas (para la corona). Con menos de 2 valores comparables no se marca nada (no hay mayor)."""
    wins: dict[int, int] = {}
    for c in cols:
        vals = [(r, _num(ops.cell_text(w.t.cell(r, c)))) for r in range(r0, r1)]
        vals = [(r, v) for r, v in vals if v is not None]
        if len(vals) < 2 or len({v for _, v in vals}) < 2:
            continue
        r, _ = max(vals, key=lambda t: t[1])
        box_cell(w.t, r, c)
        wins[r] = wins.get(r, 0) + 1
    return sorted(wins, key=lambda r: (-wins[r], r))


def leader_row(w, r0: int, r1: int, col: int) -> int | None:
    vals = [(r, _num(ops.cell_text(w.t.cell(r, col)))) for r in range(r0, r1)]
    vals = [(r, v) for r, v in vals if v is not None]
    return max(vals, key=lambda t: t[1])[0] if vals else None


# Coronas de la plantilla: imágenes decorativas que marcan al mayor; el generador las mueve a su fila o las quita
DECORATIVE = {1: {"Gráfico 8", "Gráfico 10", "Gráfico 11"}, 2: {"Gráfico 6", "Gráfico 7", "Gráfico 8", "Gráfico 10", "Gráfico 11", "Gráfico 12"}}
CROWNS = {2: ["Gráfico 8", "Gráfico 10", "Gráfico 11"], 3: ["Gráfico 6", "Gráfico 7", "Gráfico 8", "Gráfico 10", "Gráfico 11", "Gráfico 12"]}


def place_crowns(slide, shape, table, rows: list[int], names: list[str]):
    """Una corona junto a cada fila líder; las coronas sobrantes se quitan (no quedan huérfanas)."""
    tops, acc = [], shape.top
    for r in table.rows:
        tops.append((acc, acc + r.height))
        acc += r.height
    for i, name in enumerate(names):
        try:
            pic = ops.shape_by_name(slide, name)
        except KeyError:
            continue
        if i < len(rows) and rows[i] is not None:
            y0, y1 = tops[rows[i]]
            pic.top = int((y0 + y1) / 2 - pic.height / 2)
        else:
            pic._element.getparent().remove(pic._element)


# ----------------------------------------------------------------------------- tablas
KPI_T = range(1, 6)          # visitas … usuarios nuevos
KPI_M = range(1, 6)          # pedidos … ticket
TRAF = ["key", "n:visitas", "n:usuarios", "n:atc", "n:recurrentes", "n:nuevos", "share", "delta"]
TRAF_NOSHARE = ["key", "n:visitas", "n:usuarios", "n:atc", "n:recurrentes", "n:nuevos", "delta"]
MONEY = ["key", "n:pedidos", "n:piezas", "m:monto", "n:pacientes", "ticket", "share", "delta"]
MONEY_NEG = ["key", "n:pedidos", "n:piezas", "m:monto_negado", "n:pacientes", "ticket", "share", "delta"]


def fill_quien(fl: Filler, B):
    w = fl.table(1, "Tabla 2", rows=19, cols=8)
    clear_red(w.t)
    ed, sx_, dv = B["edad"].rows, B["sexo"].rows, B["dispositivo"].rows
    # 1) ajustar las tres regiones de abajo hacia arriba; 2) escribir con los índices ya definitivos
    ops.resize_rows(w.t, 15, 19, 15, len(dv))
    ops.resize_rows(w.t, 10, 12, 10, len(sx_))
    ops.resize_rows(w.t, 1, 7, 1, len(ed))
    s_start = 1 + len(ed) + 2 + 1
    d_start = s_start + len(sx_) + 2 + 1
    marks = []
    for start, rows in ((1, ed), (s_start, sx_), (d_start, dv)):
        for i, row in enumerate(rows):
            put_row(w, start + i, 0, TRAF, row)
            if rows is sx_:
                ops.set_cell(w.t.cell(start + i, 0), sx(row.key), fill=None)
        marks.append((start, len(rows)))
    for start, n in marks:
        mark_max(w, start, start + n, KPI_T)
    w.check_stale()
    ops.sync_frame_height(w.shape)


def fill_edad_producto(fl: Filler, B, rep: FillReport):
    w = fl.table(2, "Tabla 3", rows=23, cols=17)
    prods = {k.split(":", 1)[1]: b for k, b in B.items() if k.startswith("edad_producto:")}
    order = sorted(prods, key=lambda p: -sum((r.values["visitas"].v or 0) for r in prods[p].rows))
    slots = [(0, 0), (0, 9), (8, 0), (8, 9), (16, 0), (16, 9)]    # (fila del encabezado, columna inicial)
    spec = ["key", "n:visitas", "n:usuarios", "n:atc", "n:recurrentes", "n:nuevos", "p:rebote", "delta"]
    clear_red(w.t)
    if len(order) > 6:
        rep.notes.append(f"Diap. 2: {len(order)} productos con edad y la plantilla admite 6; se muestran los 6 con más visitas.")
    for (hr, c0), pk in zip(slots, order[:6] + [None] * (6 - len(order[:6]))):
        for r in range(hr + 1, hr + 7):
            for c in range(c0, c0 + 8):
                w.blank(r, c)
        if pk is None:
            for c in range(c0, c0 + 8):
                w.blank(hr, c)
            continue
        b = prods[pk]
        w.put(hr, c0, f"Edad / {_title(b)}")
        for i, row in enumerate(b.rows[:6]):
            put_row(w, hr + 1 + i, c0, spec, row, proto_row=1)
    sizes = {}
    for gi, hr in enumerate((0, 8, 16)):
        left = len(prods[order[2 * gi]].rows) if 2 * gi < len(order) else 0
        right = len(prods[order[2 * gi + 1]].rows) if 2 * gi + 1 < len(order) else 0
        sizes[hr] = min(max(left, right), 6)
    for hr in (0, 8, 16):
        w.skip_rows.update(range(hr + 1 + sizes[hr], hr + 7))
        if sizes[hr] == 0 and hr:
            w.skip_rows.add(hr - 1)
    w.check_stale()                                               # antes de borrar: los índices aún son los de la plantilla
    for hr in (16, 8, 0):
        if sizes[hr] == 0 and hr:
            ops.delete_rows(w.t, hr - 1, hr + 7)
        elif sizes[hr] < 6:
            ops.delete_rows(w.t, hr + 1 + sizes[hr], hr + 7)
    # resaltes: el mayor de cada KPI dentro de cada bloque; la corona va junto a la fila líder (más visitas) del bloque izquierdo
    nrows = len(w.t.rows)
    hrows = [i for i in range(nrows) if ops.cell_text(w.t.cell(i, 0)).startswith("Edad /")]
    crown_rows = []
    for hr in hrows:
        for c0 in (0, 9):
            if w.t.cell(hr, c0).is_spanned or not ops.cell_text(w.t.cell(hr, c0)).startswith("Edad /"):
                continue
            end = hr + 1
            while end < nrows and ops.cell_text(w.t.cell(end, c0)) and not ops.cell_text(w.t.cell(end, c0)).startswith("Edad /"):
                end += 1
            mark_max(w, hr + 1, end, range(c0 + 1, c0 + 6))
            if c0 == 0:
                crown_rows.append(leader_row(w, hr + 1, end, 1))
    place_crowns(fl.slide(2), w.shape, w.t, crown_rows, CROWNS[2])
    ops.sync_frame_height(w.shape)


def _title(b: GBlock) -> str:
    return b.name.split(":", 1)[1].capitalize()


def fill_producto_sexo(fl: Filler, B, rep: FillReport):
    w = fl.table(3, "Tabla 17", rows=18, cols=10)
    clear_red(w.t)
    by: dict[str, list[GRow]] = {}
    for r in B["producto_sexo"].rows:
        by.setdefault(r.key, []).append(r)
    prods = sorted(by)
    need = len(prods)
    total = 3 * need                                              # encabezado + 3 filas por producto (F, M, separador) menos el último separador
    trs = w.t._tbl.tr_lst
    if total > len(trs):
        for _ in range(total - len(trs)):
            trs[-1].addnext(copy.deepcopy(trs[-1]))
    elif total < len(trs):
        ops.delete_rows(w.t, total, len(trs))
    spec = ["key", "dim2", "n:visitas", "n:usuarios", "n:atc", "n:recurrentes", "n:nuevos", "t:tiempo", "p:rebote", "delta"]
    rows_total = len(w.t.rows)
    crown_rows: list[int | None] = []
    for pi, p in enumerate(prods):
        base = 1 + pi * 3
        rs = sorted(by[p], key=lambda r: (0 if r.dim2.lower().startswith("f") else 1, r.dim2))
        for k in range(3):
            r = base + k
            if r >= rows_total:
                continue
            row = rs[k] if k < 2 and k < len(rs) else None
            put_row(w, r, 0, spec, row)
        n_rows = min(len(rs), 2)
        if base < rows_total and n_rows:
            mark_max(w, base, base + n_rows, range(2, 7))
            crown_rows.append(leader_row(w, base, base + n_rows, 2))
    place_crowns(fl.slide(3), w.shape, w.t, crown_rows, CROWNS[3])
    w.check_stale()
    ops.sync_frame_height(w.shape)


def fill_region_slide(fl: Filler, B, rep: FillReport):
    w = fl.table(5, "Tabla 8", rows=7, cols=8)
    clear_red(w.t)
    rows = B["region"].rows
    fill_region(w, 1, 7, 1, rows, [k if k != "key" else "key" for k in MONEY])
    for r in range(1, 1 + len(rows)):
        c = w.t.cell(r, 0)
        ops.set_cell(c, rows[r - 1].key.upper(), fill=None)
    mark_max(w, 1, 1 + len(rows), KPI_M)
    w.finish()
    w2 = fl.table(5, "Tabla 11", rows=11, cols=7)
    clear_red(w2.t)
    est = B["trafico_estado"].rows
    if len(est) > 10:
        rep.notes.append(f"Diap. 5: {len(est)} estados con tráfico y la plantilla admite 10; se muestran los 10 con más visitas.")
    fill_region(w2, 1, 11, 1, est[:10], TRAF_NOSHARE)
    mark_max(w2, 1, 1 + len(est[:10]), KPI_T)
    w2.finish()


def fill_pago(fl: Filler, B):
    w = fl.table(6, "Tabla 7", rows=6, cols=8)
    clear_red(w.t)
    fill_region(w, 1, 6, 1, B["pago"].rows, MONEY)
    mark_max(w, 1, 1 + len(B["pago"].rows), KPI_M)
    w.finish()
    w2 = fl.table(6, "Tabla 10", rows=3, cols=8)
    clear_red(w2.t)
    fill_region(w2, 1, 3, 1, B["entrega"].rows, MONEY)
    mark_max(w2, 1, 1 + len(B["entrega"].rows), KPI_M)
    w2.finish()


FUNNEL_NAVY, FUNNEL_LINK, FUNNEL_LEAK = "104861", "9DBFD1", "ED7D31"


def _funnel_widths(counts: list[float], full: float) -> list[float]:
    """Ancho de cada etapa en escala logarítmica (con piso de 30 %): una escala lineal dejaría las últimas etapas ilegibles."""
    pos = [c for c in counts if c and c > 0]
    if not pos or max(pos) == min(pos):
        return [full] * len(counts)
    lo, hi = math.log(min(pos)), math.log(max(pos))
    return [full * (0.30 + 0.70 * ((math.log(c) - lo) / (hi - lo))) if c and c > 0 else full * 0.30 for c in counts]


def draw_funnel(slide, w, rows: dict[str, GRow]):
    """Embudo real con formas nativas (editables): barras centradas con ancho por etapa unidas por trapecios, y la fuga
    (carritos abandonados) aparte en naranja. La tabla conserva etapa, % contra «Ver producto» y la pérdida entre etapas."""
    from pptx.dml.color import RGBColor
    from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.util import Emu, Pt
    tbl, shp = w.t, w.shape
    x0 = shp.left + sum(c.width for c in list(tbl.columns)[:2])
    full = shp.left + sum(c.width for c in tbl.columns) - x0
    cx = x0 + full / 2
    ys, acc = [], shp.top
    for r in tbl.rows:
        ys.append((acc, acc + r.height))
        acc += r.height
    stages = ["ver producto", "agregar a carrito", "iniciar compra", "compra"]
    counts = [float(rows[k].values["conteo"].v or 0) for k in stages]
    widths = _funnel_widths(counts, full * 0.96)
    tree = slide.shapes

    def label(sh, text, size=9, color="FFFFFF", bold=True):
        tf = sh.text_frame
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf.word_wrap = False
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = text
        r.font.size, r.font.bold, r.font.name = Pt(size), bold, "Aptos Narrow"
        r.font.color.rgb = RGBColor.from_string(color)

    def bar(i, row_idx, width, color, text, name):
        y0, y1 = ys[row_idx]
        pad = 12000
        sh = tree.add_shape(MSO_SHAPE.RECTANGLE, Emu(int(cx - width / 2)), Emu(y0 + pad), Emu(int(width)), Emu(y1 - y0 - 2 * pad))
        sh.name = name
        sh.fill.solid()
        sh.fill.fore_color.rgb = RGBColor.from_string(color)
        sh.line.fill.background()
        sh.shadow.inherit = False
        label(sh, text)
        return sh

    for i, st in enumerate(stages):                                   # etapas: filas 0, 2, 4, 6
        bar(i, 2 * i, widths[i], FUNNEL_NAVY, F.fmt_num(rows[st].values["conteo"], 0), f"{ADDED}embudo_{i + 1}")
    for i in range(len(stages) - 1):                                  # unión entre etapas: filas 1, 3, 5
        top, bot = ys[2 * i][1] - 12000, ys[2 * i + 2][0] + 12000
        a_, b_ = widths[i] / 2, widths[i + 1] / 2
        fb = tree.build_freeform(int(cx - a_), top, scale=1.0)
        fb.add_line_segments([(int(cx + a_), top), (int(cx + b_), bot), (int(cx - b_), bot)], close=True)
        link = fb.convert_to_shape()
        link.name = f"{ADDED}embudo_union_{i + 1}"
        link.fill.solid()
        link.fill.fore_color.rgb = RGBColor.from_string(FUNNEL_LINK)
        link.line.fill.background()
        link.shadow.inherit = False
    leak = float(rows["carritos abandonados"].values["conteo"].v or 0)
    lw = _funnel_widths(counts + [leak], full * 0.96)[-1]
    bar(4, 8, lw, FUNNEL_LEAK, F.fmt_num(rows["carritos abandonados"].values["conteo"], 0), f"{ADDED}embudo_fuga")
    note = tree.add_textbox(Emu(int(x0)), Emu(int(ys[-1][1] + 25000)), Emu(int(full)), Emu(170000))
    note.name = f"{ADDED}embudo_nota"
    label(note, "Ancho de las barras en escala logarítmica (referencia visual); los números son los conteos reales.", size=7, color="7F7F7F", bold=False)


def fill_funnel(fl: Filler, B, funnel: GBlock | None, rep: FillReport):
    if funnel is None:
        raise DataMissing("Falta el embudo (tabla de tráfico, vista general).")
    w = fl.table(7, "Tabla 8", rows=9, cols=7)
    rows = {r.key: r for r in funnel.rows}
    stages = ("ver producto", "agregar a carrito", "iniciar compra", "compra", "carritos abandonados")
    for i, stage in enumerate(stages):
        r = 2 * i
        row = rows[stage]
        w.put(r, 0, {"carritos abandonados": "Carritos abandonados"}.get(stage, stage.capitalize()))
        w.put(r, 1, F.fmt_pct(row.values["tasa_calc"], 2, sign=False))
        for c in range(2, 7):                                         # las barras de la plantilla (celdas rellenas) se sustituyen por formas nativas
            w.put(r, c, "", fill=None)
    for i in range(3):                                                # filas separadoras: cuánto avanza a la siguiente etapa del embudo
        a_, b_ = rows[stages[i]].values["conteo"].v, rows[stages[i + 1]].values["conteo"].v
        txt = f"↓ avanza {F.fmt_pct(ind.derived(b_ / a_, 'avance'), 2, sign=False)}" if a_ and b_ is not None else ""
        r = 2 * i + 1
        w.put(r, 0, txt, font="595959", proto=w.t.cell(0, 0))
        for c in range(1, 7):
            w.put(r, c, "", fill=None)
    w.put(7, 0, "", proto=w.t.cell(0, 0))                             # entre «Compra» y «Carritos abandonados» no hay avance: la fuga se muestra aparte
    for c in range(1, 7):
        w.put(7, c, "", fill=None)
    w.check_stale()
    draw_funnel(fl.slide(7), w, rows)
    ops.sync_frame_height(w.shape)
    w2 = fl.table(7, "Tabla 3", rows=5, cols=8)
    clear_red(w2.t)
    neg = sorted(B["negados"].rows, key=lambda r: -(r.values["monto_negado"].v or 0))[:4]
    if len(B["negados"].rows) > 4:
        rep.notes.append(f"Diap. 7: {len(B['negados'].rows)} productos negados y la plantilla muestra los 4 de mayor monto.")
    spec = ["key", "n:pedidos", "n:piezas", "m:monto_negado", "n:pacientes", "ticket", "share", "delta"]
    fill_region(w2, 1, 5, 1, neg, spec)
    mark_max(w2, 1, 1 + len(neg), range(1, 6))
    w2.finish()


def fill_productos(fl: Filler, B):
    w = fl.table(8, "Tabla 2", rows=11, cols=8)
    clear_red(w.t)
    rows = sorted(B["productos"].rows, key=lambda r: -(r.values["pedidos"].v or 0))[:10]
    fill_region(w, 1, 11, 1, rows, MONEY)
    mark_max(w, 1, 1 + len(rows), KPI_M)
    w.finish()


def fill_programas(fl: Filler, B):
    w = fl.table(9, "Tabla 2", rows=7, cols=8)
    clear_red(w.t)
    fill_region(w, 1, 7, 1, B["programas"].rows[:6], MONEY)
    mark_max(w, 1, 1 + len(B["programas"].rows[:6]), KPI_M)
    w.finish()


def fill_fuentes(fl: Filler, B, rep: FillReport):
    w = fl.table(10, "Tabla 2", rows=18, cols=7)
    clear_red(w.t)
    rows = B["fuentes"].rows[:12]
    canal = B["canal_resumen"].rows if "canal_resumen" in B else []
    if canal:
        ops.resize_rows(w.t, 16, 18, 16, len(canal))               # sub-tabla Pago/Orgánico (de abajo hacia arriba)
    n = fill_region(w, 1, 13, 1, rows, TRAF_NOSHARE)
    mark_max(w, 1, n, KPI_T)
    w.put(0, 0, "Fuente de tráfico")
    rep.titles_fixed.append("Diap. 10: encabezado 'Categoría de dispositivo' (son fuentes de tráfico) → 'Fuente de tráfico'")
    if canal:
        hdr = n + 2                                                  # n = primera fila tras las fuentes; 2 separadoras y luego "Canal"
        for i, row in enumerate(canal):
            put_row(w, hdr + 1 + i, 0, TRAF_NOSHARE[:-1], row)
            w.blank(hdr + 1 + i, 6)
        mark_max(w, hdr + 1, hdr + 1 + len(canal), KPI_T)
        for r in (n, n + 1):
            for c in range(7):
                w.blank(r, c)
        w.check_stale()
    else:
        w.skip_rows.update(range(n, len(w.t.rows)))
        w.check_stale()
        ops.delete_rows(w.t, n, len(w.t.rows))
        rep.notes.append("Diap. 10: sin datos de canal (Pago/Orgánico); se omite esa sub-tabla.")
    ops.sync_frame_height(w.shape)


# ----------------------------------------------------------------------------- principal
def assemble(paras: list[Para]) -> list[str]:
    out: list[str] = []
    for p in (q for q in paras if q.visible):
        if out:
            out.append("")
        out += p.text.split("\n")
    return out


def fill_glp1(prs, blocks: dict[str, GBlock], funnel: GBlock | None, period: Period,
              narrative: dict[str, list[str]] | None = None, fix_titles: bool = True, att=None) -> FillReport:
    """Mensual y trimestral usan la misma estructura de láminas; cambian los periodos de comparación (mes/trimestre anterior)."""
    missing = [k for k in REQUIRED if k not in blocks]
    if missing or not any(k.startswith("edad_producto:") for k in blocks):
        raise DataMissing("Faltan bloques para rellenar la plantilla GLP-1: " + ", ".join(missing + ([] if any(k.startswith("edad_producto:") for k in blocks) else ["edad_producto"])))
    if funnel is None:
        raise DataMissing("Falta el embudo (tabla de tráfico, vista general).")
    rep = FillReport()
    fl = Filler(prs, rep)
    boxes = {k: Box(*ops.narrative_box(fl.shape(n, name))) for k, (n, name) in NARR.items()}
    narr = compose_glp1(blocks, funnel, period, boxes)
    rep.narrative_problems = check(narr)
    rep.narrative = narr
    for key, texts in (narrative or {}).items():
        if key not in narr:
            continue
        allowed = set().union(*(p.nums for ps in narr.values() for p in ps))
        edited = [Para(t, "hecho", 0, edited=True, nums=set()) for t in texts if t != ""]
        rep.edited_unverified += [f"{key}: {x}" for p in edited for x in verify_edited(p.plain, allowed)]
        narr[key] = edited + [p for p in narr.get(key, []) if not p.visible]
    fill_quien(fl, blocks)
    fill_edad_producto(fl, blocks, rep)
    fill_producto_sexo(fl, blocks, rep)
    fill_region_slide(fl, blocks, rep)
    fill_pago(fl, blocks)
    fill_funnel(fl, blocks, funnel, rep)
    fill_productos(fl, blocks)
    fill_programas(fl, blocks)
    fill_fuentes(fl, blocks, rep)
    for key, (n, name) in NARR.items():
        ops.set_paragraphs(fl.shape(n, name), assemble(narr[key]), align="l")
    for n, name in NOTES.items():                                  # la nota de la plantilla es del mes de referencia
        try:
            ops.set_simple_text(ops.shape_by_name(prs.slides[n - 1], name), "")
        except KeyError:
            pass
    return rep


fill_glp1_mensual = fill_glp1
