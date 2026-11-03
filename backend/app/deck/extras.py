"""Diapositivas añadidas al reporte: Resumen ejecutivo (al inicio) y Recomendaciones (al final).

Se clonan de la diapositiva 'Conclusiones Clave' de la plantilla para conservar barras, logos, pie y tipografías."""
from __future__ import annotations

import copy

from . import pptx_ops as ops

R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
TITLE, BODY = "CuadroTexto 9", "CuadroTexto 12"


def clone_slide(prs, src_idx: int, insert_at: int):
    """Duplica una diapositiva (formas + relaciones de imagen) y la coloca en `insert_at`."""
    src = prs.slides[src_idx]
    new = prs.slides.add_slide(src.slide_layout)
    for sh in list(new.shapes):
        sh._element.getparent().remove(sh._element)
    rid_map = {}
    for rid, rel in src.part.rels.items():
        if rel.is_external or rel.reltype.endswith(("/slideLayout", "/notesSlide")):
            continue
        rid_map[rid] = new.part.relate_to(rel.target_part, rel.reltype)
    tree = new.shapes._spTree
    for el in src.shapes._spTree:
        if el.tag.endswith(("}nvGrpSpPr", "}grpSpPr")):
            continue
        c = copy.deepcopy(el)
        for node in c.iter():
            for k, v in list(node.attrib.items()):
                if k.startswith("{" + R_NS + "}") and v in rid_map:
                    node.set(k, rid_map[v])
        tree.append(c)
    ids = prs.slides._sldIdLst
    el = list(ids)[-1]
    ids.remove(el)
    ids.insert(insert_at, el)
    return new


def exec_capacity(prs, conclusions_idx: int | None = None) -> tuple[int, int]:
    """(caracteres por línea, líneas con margen) del cuerpo de 'Conclusiones', de donde se clonan las diapositivas nuevas."""
    src = len(prs.slides) - 1 if conclusions_idx is None else conclusions_idx
    cpl, lines = ops.narrative_box(ops.shape_by_name(prs.slides[src], BODY))
    return cpl, max(int(lines * 0.85), 4)


def add_executive_slides(prs, resumen_paras, recs_paras, to_paragraphs, fit_fn, conclusions_idx: int | None = None):
    """Clona 'Conclusiones' dos veces: resumen al inicio y recomendaciones al final.
    Devuelve (mapa a índices de la plantilla para el QA, párrafos del resumen, párrafos de recomendaciones)."""
    n0 = len(prs.slides)
    src = n0 - 1 if conclusions_idx is None else conclusions_idx
    res = clone_slide(prs, src, 0)                       # resumen ejecutivo: primera
    rec = clone_slide(prs, src + 1, len(prs.slides))     # recomendaciones: última (src se desplazó por la inserción)
    kept_all = []
    for sl, title, paras in ((res, "Resumen Ejecutivo", resumen_paras), (rec, "Recomendaciones", recs_paras)):
        t, b = ops.shape_by_name(sl, TITLE), ops.shape_by_name(sl, BODY)
        ops.set_simple_text(t, title)
        cpl, lines = ops.narrative_box(b)
        kept = fit_fn(paras, cpl, max(int(lines * 0.85), 4))      # margen: el contexto del equipo no se descarta, lo demás cede
        ops.set_paragraphs(b, to_paragraphs(kept), align="l")
        kept_all.append(kept)
    return [src] + list(range(n0)) + [src], kept_all[0], kept_all[1]


SECCIONES = [("datos", "Lo que dicen los datos"), ("significado", "Lo que significa"), ("hipotesis", "Hipótesis a validar"), ("accion", "Qué haríamos")]


def _lines(text: str, cpl: int) -> int:
    return sum(max(1, -(-len(p) // cpl)) for p in text.split("\n"))


def _write(shape, lines: list[str], size: float, color: str = "262626", bold_first: bool = False, align: str = "l", gap: float = 0):
    """Escribe párrafos en una forma nueva; `**x**` = negrita."""
    import re as _re
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN
    from pptx.util import Pt
    tf = shape.text_frame
    tf.word_wrap = True
    for i, text in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = {"l": PP_ALIGN.LEFT, "c": PP_ALIGN.CENTER}[align]
        if gap:
            p.space_after = Pt(gap)
        for part in _re.split(r"(\*\*.+?\*\*)", text):
            if not part:
                continue
            bold = part.startswith("**") and part.endswith("**")
            r = p.add_run()
            r.text = part[2:-2] if bold else part
            r.font.size, r.font.bold, r.font.name = Pt(size), bold or (bold_first and i == 0), "Aptos Narrow"
            r.font.color.rgb = RGBColor.from_string(color)


def add_discovery_slide(prs, discovery: dict, slide_map: list[int] | None, n_template: int, added_prefix: str = "RI_"):
    """Hoja completa de descubrimiento (IA propuesta, validada por el usuario): titular, lo que dicen los datos, lo que significa,
    hipótesis, qué haríamos y, a la derecha, la evidencia citada textualmente. Se clona la última diapositiva de texto y se coloca
    antes de ella. Devuelve (mapa de QA, párrafos publicados)."""
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.text import MSO_ANCHOR
    from pptx.util import Emu, Pt
    from ..narrative.writer import Para
    n = len(prs.slides)
    sl = clone_slide(prs, n - 1, n - 1)
    t, b = ops.shape_by_name(sl, TITLE), ops.shape_by_name(sl, BODY)
    ops.set_simple_text(t, (discovery.get("titulo") or "Descubrimiento del periodo")[:64])
    t.width = 9_600_000 - t.left
    t.text_frame.word_wrap = True
    left, right_x, top_body, h_body = 567871, 7_650_000, 1_780_000, 4_380_000
    full_w = 11_640_000 - left
    # titular (banda)
    tit = discovery.get("titular")
    if tit and tit.get("texto"):
        band = sl.shapes.add_shape(MSO_SHAPE.RECTANGLE, Emu(left), Emu(1_010_000), Emu(full_w), Emu(640_000))
        band.name = f"{added_prefix}descubrimiento_titular"
        band.fill.solid()
        band.fill.fore_color.rgb = RGBColor.from_string("FCEBDD")
        band.line.fill.background()
        band.shadow.inherit = False
        band.text_frame.margin_left = band.text_frame.margin_right = Emu(120_000)
        band.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        _write(band, [tit["texto"]], 13, "7A3B12", align="l")
    # cuerpo (izquierda): secciones fijas cada mes
    b.left, b.top, b.width, b.height = Emu(left), Emu(top_body), Emu(right_x - left - 150_000), Emu(h_body)
    for r in b.text_frame.paragraphs[0].runs:
        r.font.size = Pt(11)
    cpl, max_lines = ops.narrative_box(b)
    max_lines = int(max_lines * 0.97)
    entries: list[list] = []                              # [texto, prioridad, sección, tipo]
    by = {k: [i for i in discovery.get("items", []) if i.get("seccion") == k] for k, _ in SECCIONES}
    for key, title in SECCIONES:
        if not by[key]:
            continue
        entries.append([f"**{title}**", 0, key, "contexto"])
        for i, it in enumerate(by[key]):
            text = "• " + it["texto"]
            if key == "hipotesis" and it.get("validar"):
                text += f" Para validarla: {it['validar']}"
            entries.append([text, 1 + i + (1 if key == "hipotesis" else 0), key, it.get("tipo", "hecho")])

    def total():
        heads = [e for e in entries if e[1] == 0]
        return sum(_lines(e[0], cpl) for e in entries) + max(len(heads) - 1, 0)
    while total() > max_lines:
        cand = [e for e in entries if e[1] > 0]
        if not cand:
            break
        drop = max(cand, key=lambda e: (e[1], entries.index(e)))
        entries.remove(drop)
        if not any(e[2] == drop[2] and e[1] > 0 for e in entries):
            entries[:] = [e for e in entries if not (e[2] == drop[2] and e[1] == 0)]
    lines: list[str] = []
    for e in entries:
        if e[1] == 0 and lines:
            lines.append("")
        lines.append(e[0])
    ops.set_paragraphs(b, lines, align="l")
    # evidencia citada (derecha), textual
    ev = discovery.get("evidencia") or []
    panel = sl.shapes.add_shape(MSO_SHAPE.RECTANGLE, Emu(right_x), Emu(top_body), Emu(11_640_000 - right_x), Emu(h_body))
    panel.name = f"{added_prefix}descubrimiento_evidencia"
    panel.fill.solid()
    panel.fill.fore_color.rgb = RGBColor.from_string("F2F2F2")
    panel.line.fill.background()
    panel.shadow.inherit = False
    panel.text_frame.margin_left = panel.text_frame.margin_right = Emu(100_000)
    panel.text_frame.vertical_anchor = MSO_ANCHOR.TOP
    ecpl = max(int((Emu(11_640_000 - right_x).pt - 16) / (0.45 * 8.5)), 20)
    cap = int((Emu(h_body).pt - 10) / (1.2 * 8.5)) - 3
    ev_lines, used = ["**Evidencia citada**"], 1
    shown = 0
    for e in ev:
        txt = f"{e['id']} · {e['texto']}"
        k = _lines(txt, ecpl) + 0.5
        if used + k > cap:
            break
        ev_lines += [txt]
        used += k
        shown += 1
    if shown < len(ev):
        ev_lines.append(f"(+{len(ev) - shown} hechos citados más en narrative.json)")
    _write(panel, ev_lines, 8.5, "404040", gap=4)
    note = sl.shapes.add_textbox(Emu(left), Emu(6_240_000), Emu(full_w), Emu(240_000))
    note.name = f"{added_prefix}descubrimiento_nota"
    _write(note, ["Hoja propuesta con IA a partir de los datos de este reporte; cada cifra proviene de los hechos citados y fue revisada y validada por el equipo."], 8, "7F7F7F")
    sm = list(slide_map) if slide_map else list(range(n_template))
    kept = [Para(e[0].lstrip("• "), e[3] if e[3] in ("hecho", "interpretacion", "recomendacion", "hipotesis") else "contexto", e[1],
                 basis="propuesto por IA y validado por el usuario", evidence=[], visible=True) for e in entries]
    if tit and tit.get("texto"):
        kept.insert(0, Para(tit["texto"], "interpretacion", 0, basis="titular propuesto por IA y validado por el usuario", evidence=list(tit.get("hechos", []))))
    return sm[:-1] + [sm[-1], sm[-1]], kept
