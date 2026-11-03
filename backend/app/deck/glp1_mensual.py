"""Relleno de la plantilla GLP-1 mensual (11 diapositivas; referencia: Resultados_GLP1_Agosto_2026).

Rellena en su lugar tablas y textos. Los resaltes de la plantilla (recuadros rojos y rellenos puntuales) eran manuales: se quitan
y se vuelve a marcar con recuadro rojo la fila con más visitas (o la de mayor venta) de cada tabla. La nota de la plantilla
("Nota: el 31 de agosto…") es del mes de referencia y se elimina. La plantilla no se modifica en estructura.
"""
from __future__ import annotations

import copy
from decimal import Decimal

from lxml import etree
from pptx.oxml.ns import qn

from .. import format as F
from ..calc import indicators as ind
from ..models import GBlock, GRow, Period
from ..narrative.aetops import Box
from ..narrative.glp1 import check, compose_glp1, sx
from ..narrative.writer import Para, verify_edited
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
        ln.set("w", "6350")
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
        if want is None and not is_red:
            continue                                             # línea ajena al resalte: no se toca
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


# ----------------------------------------------------------------------------- tablas
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
        marks.append((start, best_row(rows, "visitas")))
    for start, i in marks:
        if i is not None:
            box_row(w.t, start + i, 0, 7)
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
    # resaltes: fila con más visitas de cada bloque
    trs = w.t._tbl.tr_lst
    hrows = [i for i, r in enumerate(w.t.rows) if (ops.cell_text(r.cells[0]).startswith("Edad /"))]
    for hr in hrows:
        for c0, k in ((0, 0), (9, 1)):
            if w.t.cell(hr, c0).is_spanned or not ops.cell_text(w.t.cell(hr, c0)).startswith("Edad /"):
                continue
            vals = []
            r = hr + 1
            while r < len(trs) and ops.cell_text(w.t.cell(r, c0)) not in ("",) and not ops.cell_text(w.t.cell(r, c0)).startswith("Edad /"):
                try:
                    vals.append((r, int(ops.cell_text(w.t.cell(r, c0 + 1)).replace(",", ""))))
                except ValueError:
                    pass
                r += 1
            if vals:
                box_row(w.t, max(vals, key=lambda t: t[1])[0], c0, c0 + 7)
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
    for pi, p in enumerate(prods):
        base = 1 + pi * 3
        rs = sorted(by[p], key=lambda r: (0 if r.dim2.lower().startswith("f") else 1, r.dim2))
        for k in range(3):
            r = base + k
            if r >= rows_total:
                continue
            row = rs[k] if k < 2 and k < len(rs) else None
            put_row(w, r, 0, spec, row)
        vis = [(k, x.values["visitas"].v or 0) for k, x in enumerate(rs[:2])]
        if vis and base < rows_total:
            box_row(w.t, base + max(vis, key=lambda t: t[1])[0], 0, 9)
    # el último producto no lleva fila separadora al final de la plantilla original
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
    i = best_row(rows, "monto")
    if i is not None:
        box_row(w.t, 1 + i, 0, 7)
    w.finish()
    w2 = fl.table(5, "Tabla 11", rows=11, cols=7)
    clear_red(w2.t)
    est = B["trafico_estado"].rows
    if len(est) > 10:
        rep.notes.append(f"Diap. 5: {len(est)} estados con tráfico y la plantilla admite 10; se muestran los 10 con más visitas.")
    fill_region(w2, 1, 11, 1, est[:10], TRAF_NOSHARE)
    w2.finish()


def fill_pago(fl: Filler, B):
    w = fl.table(6, "Tabla 7", rows=6, cols=8)
    clear_red(w.t)
    fill_region(w, 1, 6, 1, B["pago"].rows, MONEY)
    w.finish()
    w2 = fl.table(6, "Tabla 10", rows=3, cols=8)
    clear_red(w2.t)
    fill_region(w2, 1, 3, 1, B["entrega"].rows, MONEY)
    w2.finish()


def fill_funnel(fl: Filler, B, funnel: GBlock | None, rep: FillReport):
    if funnel is None:
        raise DataMissing("Falta el embudo (tabla de tráfico, vista general).")
    w = fl.table(7, "Tabla 8", rows=9, cols=7)
    rows = {r.key: r for r in funnel.rows}
    for i, stage in enumerate(("ver producto", "agregar a carrito", "iniciar compra", "compra", "carritos abandonados")):
        r = 2 * i
        row = rows[stage]
        w.put(r, 0, {"carritos abandonados": "Carritos abandonados"}.get(stage, stage.capitalize()))
        w.put(r, 1, F.fmt_pct(row.values["tasa_calc"], 2, sign=False))
        w.put(r, 4, F.fmt_num(row.values["conteo"], 0))
    for r in range(1, 9, 2):                                      # filas separadoras sin datos
        pass
    w.check_stale()
    ops.sync_frame_height(w.shape)
    w2 = fl.table(7, "Tabla 3", rows=5, cols=8)
    clear_red(w2.t)
    neg = sorted(B["negados"].rows, key=lambda r: -(r.values["monto_negado"].v or 0))[:4]
    if len(B["negados"].rows) > 4:
        rep.notes.append(f"Diap. 7: {len(B['negados'].rows)} productos negados y la plantilla muestra los 4 de mayor monto.")
    spec = ["key", "n:pedidos", "n:piezas", "m:monto_negado", "n:pacientes", "ticket", "share", "delta"]
    fill_region(w2, 1, 5, 1, neg, spec)
    if neg:
        box_row(w2.t, 1, 0, 7)
    w2.finish()


def fill_productos(fl: Filler, B):
    w = fl.table(8, "Tabla 2", rows=11, cols=8)
    clear_red(w.t)
    rows = sorted(B["productos"].rows, key=lambda r: -(r.values["pedidos"].v or 0))[:10]
    fill_region(w, 1, 11, 1, rows, MONEY)
    w.finish()


def fill_programas(fl: Filler, B):
    w = fl.table(9, "Tabla 2", rows=7, cols=8)
    clear_red(w.t)
    fill_region(w, 1, 7, 1, B["programas"].rows[:6], MONEY)
    w.finish()


def fill_fuentes(fl: Filler, B, rep: FillReport):
    w = fl.table(10, "Tabla 2", rows=18, cols=7)
    clear_red(w.t)
    rows = B["fuentes"].rows[:12]
    canal = B["canal_resumen"].rows if "canal_resumen" in B else []
    if canal:
        ops.resize_rows(w.t, 16, 18, 16, len(canal))               # sub-tabla Pago/Orgánico (de abajo hacia arriba)
    n = fill_region(w, 1, 13, 1, rows, TRAF_NOSHARE)
    w.put(0, 0, "Fuente de tráfico")
    rep.titles_fixed.append("Diap. 10: encabezado 'Categoría de dispositivo' (son fuentes de tráfico) → 'Fuente de tráfico'")
    if canal:
        hdr = n + 2                                                  # n = primera fila tras las fuentes; 2 separadoras y luego "Canal"
        for i, row in enumerate(canal):
            put_row(w, hdr + 1 + i, 0, TRAF_NOSHARE[:-1], row)
            w.blank(hdr + 1 + i, 6)
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
