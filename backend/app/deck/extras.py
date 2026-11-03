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


def add_discovery_slide(prs, title: str, paragraphs, to_paragraphs, fit_fn, slide_map: list[int] | None, n_template: int):
    """Descubrimiento único (IA, validado por el usuario): se clona la última diapositiva de texto y se coloca antes de ella.
    Devuelve (mapa de QA actualizado, párrafos que cupieron)."""
    n = len(prs.slides)
    sl = clone_slide(prs, n - 1, n - 1)
    t, b = ops.shape_by_name(sl, TITLE), ops.shape_by_name(sl, BODY)
    ops.set_simple_text(t, title)
    t.width = 9_600_000 - t.left                       # los títulos de la plantilla son cortos; este puede ser una frase
    t.text_frame.word_wrap = True
    cpl, lines = ops.narrative_box(b)
    kept = fit_fn(paragraphs, cpl, max(int(lines * 0.85), 4))
    ops.set_paragraphs(b, to_paragraphs(kept), align="l")
    sm = list(slide_map) if slide_map else list(range(n_template))
    return sm[:-1] + [sm[-1], sm[-1]], kept
