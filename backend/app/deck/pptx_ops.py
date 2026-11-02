"""Operaciones de bajo nivel sobre PPTX que CONSERVAN el formato de la plantilla.

Regla: se sustituye el texto del primer *run* (fuente, tamaño y color se heredan); nunca se
recrea una tabla ni se rasteriza nada, para que todo siga siendo editable en PowerPoint.
"""
from __future__ import annotations

import copy
import re
from decimal import Decimal

from lxml import etree
from pptx.dml.color import RGBColor
from pptx.oxml.ns import qn

NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"

# Paleta de formato condicional de Excel usada en los PPTX de referencia
POS = ("C6EFCE", "006100")
NEG = ("FFC7CE", "9C0006")
NEU = ("FFEB9C", "9C5700")


def delta_style(v: Decimal | None) -> tuple[str, str] | None:
    """Verde si sube, rojo si baja, amarillo si es exactamente 0; sin dato -> sin color."""
    if v is None:
        return None
    return POS if v > 0 else NEG if v < 0 else NEU


# ----------------------------------------------------------------------------- celdas
def _first_rpr(cell):
    r = cell._tc.xpath(".//a:r/a:rPr")
    if r:
        return r[0]
    e = cell._tc.xpath(".//a:endParaRPr")
    return e[0] if e else None


def _empty_paragraph(p) -> None:
    """Deja el párrafo sin texto conservando el tamaño/fuente (en `endParaRPr`), sin runs vacíos."""
    runs = p._p.findall(qn("a:r"))
    end = p._p.find(qn("a:endParaRPr"))
    if runs and end is None:
        rpr = runs[0].find(qn("a:rPr"))
        if rpr is not None:
            end = copy.deepcopy(rpr)
            end.tag = qn("a:endParaRPr")
            p._p.append(end)
    for r in runs:
        p._p.remove(r)


def set_cell(cell, text: str, *, fill: str | None | bool = False, font: str | None = None,
             proto=None) -> None:
    """Escribe `text` en la celda. fill: False=no tocar, None=sin relleno, 'RRGGBB'=relleno.
    `proto`: celda de la que copiar el formato si ésta está vacía (sin runs)."""
    tf = cell.text_frame
    paras = tf.paragraphs
    for extra in paras[1:]:                        # una sola línea por celda
        extra._p.getparent().remove(extra._p)
    p = paras[0]
    runs = p.runs
    if text == "":
        _empty_paragraph(p)                          # sin runs vacíos: agrandan la fila al renderizar
        run = None
    elif runs:
        runs[0].text = text
        for r in runs[1:]:
            r._r.getparent().remove(r._r)
        run = runs[0]
    else:
        src = _first_rpr(proto) if proto is not None else _first_rpr(cell)
        run = p.add_run()
        run.text = text
        if src is not None:
            new = copy.deepcopy(src)
            new.tag = qn("a:rPr")
            old = run._r.find(qn("a:rPr"))
            if old is not None:
                run._r.remove(old)
            run._r.insert(0, new)
    if font and run is not None:
        run.font.color.rgb = RGBColor.from_string(font)
    if fill is not False:
        if fill is None:
            cell.fill.background()
        else:
            cell.fill.solid()
            cell.fill.fore_color.rgb = RGBColor.from_string(fill)


def cell_text(cell) -> str:
    return cell.text_frame.text


def clear_cell(cell, *, fill: str | None | bool = False) -> None:
    set_cell(cell, "", fill=fill)


# ----------------------------------------------------------------------------- filas
def resize_rows(table, start: int, end: int, proto_idx: int, needed: int) -> None:
    """La región de filas [start, end) debe tener `needed` filas: clona la de `proto_idx` o elimina del final.
    Actualiza el alto del marco para que no quede un hueco o un desborde estimado."""
    trs = table._tbl.tr_lst
    have = end - start
    if needed > have:
        proto = trs[proto_idx]
        anchor = trs[end - 1]
        for _ in range(needed - have):
            clone = copy.deepcopy(proto)
            anchor.addnext(clone)
            anchor = clone
    elif needed < have:
        for tr in trs[start + needed:end]:
            table._tbl.remove(tr)


def delete_rows(table, start: int, end: int) -> None:
    """Elimina las filas [start, end)."""
    for tr in table._tbl.tr_lst[start:end]:
        table._tbl.remove(tr)


def resize_blocks(table, first: int, block_len: int, have: int, needed: int) -> None:
    """Bloques repetidos de `block_len` filas desde `first`: clona/elimina bloques completos."""
    trs = table._tbl.tr_lst
    if needed > have:
        proto = trs[first + (have - 1) * block_len: first + have * block_len]
        anchor = trs[first + have * block_len - 1]
        for _ in range(needed - have):
            for tr in proto:
                clone = copy.deepcopy(tr)
                anchor.addnext(clone)
                anchor = clone
    elif needed < have:
        for tr in trs[first + needed * block_len: first + have * block_len]:
            table._tbl.remove(tr)


def sync_frame_height(shape) -> None:
    shape.height = sum(r.height for r in shape.table.rows)


# ----------------------------------------------------------------------------- texto libre
_BOLD = re.compile(r"(\*\*.+?\*\*)")


def set_paragraphs(shape, paragraphs: list[str]) -> None:
    """Sustituye el texto de un cuadro conservando el formato del 1.er run y el patrón del original
    (párrafos separados por párrafo vacío). `**x**` = negrita."""
    tf = shape.text_frame
    txBody = tf._txBody
    ps = txBody.findall(qn("a:p"))
    base_p = ps[0]
    base_ppr = base_p.find(qn("a:pPr"))
    base_rpr = None
    for r in txBody.iter(qn("a:r")):
        rp = r.find(qn("a:rPr"))
        if rp is not None:
            base_rpr = rp
            break
    base_rpr = copy.deepcopy(base_rpr) if base_rpr is not None else None
    base_ppr = copy.deepcopy(base_ppr) if base_ppr is not None else None
    for p in ps:
        txBody.remove(p)
    for text in paragraphs:
        p = etree.SubElement(txBody, qn("a:p"))
        if base_ppr is not None:
            p.append(copy.deepcopy(base_ppr))
        for part in _BOLD.split(text):
            if not part:
                continue
            bold = part.startswith("**") and part.endswith("**")
            r = etree.SubElement(p, qn("a:r"))
            if base_rpr is not None:
                rp = copy.deepcopy(base_rpr)
                rp.set("b", "1" if bold else "0")
                r.append(rp)
            t = etree.SubElement(r, qn("a:t"))
            t.text = part[2:-2] if bold else part


def set_simple_text(shape, text: str) -> None:
    set_paragraphs(shape, [text])


def shape_by_name(slide, name: str):
    for sh in slide.shapes:
        if sh.name == name:
            return sh
    raise KeyError(f"No existe el shape '{name}' en la diapositiva (¿cambió la plantilla?)")
