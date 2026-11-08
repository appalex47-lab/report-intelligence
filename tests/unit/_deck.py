"""Utilidad de pruebas del bloque integral: fabrica PPTX sintéticos (sin plantillas reales, así corren en CI) y los manipula."""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_AUTO_SIZE
from pptx.util import Emu, Pt

ANCHO, ALTO = 960.0, 540.0                     # pt (16:9)


def _png(color=(10, 98, 181)) -> bytes:
    b = io.BytesIO()
    Image.new("RGB", (40, 24), color).save(b, "PNG")
    return b.getvalue()


def _txt(sl, nombre, texto, x, y, w, h, pt, bold=False, color=None, fondo=None, wrap=True, fuente="Aptos Narrow", auto=False):
    sh = sl.shapes.add_textbox(Pt(x), Pt(y), Pt(w), Pt(h))
    sh.name = nombre
    tf = sh.text_frame
    tf.word_wrap = wrap
    tf.auto_size = MSO_AUTO_SIZE.SHAPE_TO_FIT_TEXT if auto else MSO_AUTO_SIZE.NONE      # por omisión, cuadro de tamaño fijo (como los de las plantillas)
    primero = True
    for linea in texto.split("\n"):
        p = tf.paragraphs[0] if primero else tf.add_paragraph()
        primero = False
        r = p.add_run()
        r.text = linea
        r.font.size = Pt(pt)
        r.font.bold = bold
        r.font.name = fuente
        if color:
            r.font.color.rgb = RGBColor.from_string(color.lstrip("#"))
    if fondo:
        sh.fill.solid()
        sh.fill.fore_color.rgb = RGBColor.from_string(fondo.lstrip("#"))
    return sh


def crear(ruta: Path | str, slides: list[dict]) -> Path:
    """`slides`: [{titulo, cuerpo, pt_cuerpo, caja (x,y,w,h), tabla (filas), pt_tabla, imagen (bool), logo (bool), color, fondo, obstaculo (x,y,w,h)}]."""
    prs = Presentation()
    prs.slide_width, prs.slide_height = Pt(ANCHO), Pt(ALTO)
    blanco = prs.slide_layouts[6]
    for d in slides:
        sl = prs.slides.add_slide(blanco)
        if d.get("titulo") is not None:
            _txt(sl, "Titulo", d["titulo"], 40, 20, 880, 50, d.get("pt_titulo", 28), bold=True)
        if d.get("cuerpo") is not None:
            x, y, w, h = d.get("caja", (40, 90, 880, 120))
            _txt(sl, "Cuerpo", d["cuerpo"], x, y, w, h, d.get("pt_cuerpo", 14), color=d.get("color"), fondo=d.get("fondo"), auto=d.get("auto", False))
        if d.get("obstaculo"):
            x, y, w, h = d["obstaculo"]
            _txt(sl, "Obstaculo", "Nota fija", x, y, w, h, 12)
        if d.get("tabla"):
            filas = d["tabla"]
            gf = sl.shapes.add_table(len(filas), len(filas[0]), Pt(40), Pt(d.get("tabla_y", 230)), Pt(880), Pt(d.get("alto_fila", 22) * len(filas)))
            gf.name = "Tabla"
            for i, f in enumerate(filas):
                gf.table.rows[i].height = Pt(d.get("alto_fila", 22))
                for j, v in enumerate(f):
                    c = gf.table.cell(i, j)
                    c.text_frame.paragraphs[0].text = ""
                    r = c.text_frame.paragraphs[0].add_run()
                    r.text = str(v)
                    r.font.size = Pt(d.get("pt_tabla", 11))
                    r.font.name = "Aptos Narrow"
        if d.get("imagen"):
            sl.shapes.add_picture(io.BytesIO(_png()), Pt(700), Pt(300), Pt(160), Pt(96)).name = "Imagen"
        if d.get("logo"):
            sl.shapes.add_picture(io.BytesIO(_png((200, 30, 30))), Pt(880), Pt(500), Pt(60), Pt(30)).name = "Logo"
    prs.save(str(ruta))
    return Path(ruta)


def reordenar(ruta: Path | str, orden: list[int]) -> None:
    """Reordena las diapositivas (índices 0-based). No cambia sus `sldId`."""
    prs = Presentation(str(ruta))
    lst = prs.slides._sldIdLst
    items = list(lst)
    for e in items:
        lst.remove(e)
    for i in orden:
        lst.append(items[i])
    prs.save(str(ruta))


def formas(ruta: Path | str, indice: int = 0) -> dict:
    prs = Presentation(str(ruta))
    return {sh.name: sh for sh in prs.slides[indice].shapes}


def tamanos(ruta: Path | str, indice: int, nombre: str) -> list[float]:
    prs = Presentation(str(ruta))
    sh = next(s for s in prs.slides[indice].shapes if s.name == nombre)
    return [r.font.size.pt for p in sh.text_frame.paragraphs for r in p.runs]


LARGO = ("Texto de prueba suficientemente largo para llenar el cuadro y obligar al diseño adaptativo a decidir qué hacer con él. " * 12).strip()
