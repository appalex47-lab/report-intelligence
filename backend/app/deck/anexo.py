"""Fase 5 · Anexo «Calidad de datos y supuestos» como ÚLTIMA diapositiva del PPTX (spec Fase 1 §6 punto 7, RQ-19, T-11).

Es OPT-IN: gobernado por el flag `anexo_calidad` de `config/reglas.json` (desactivado por omisión: con el flag apagado el PPTX es idéntico a la línea base, AC-21) o
por la petición expresa del usuario al generar. No mueve ninguna diapositiva existente: se clona la última (para conservar barras, logos, pie y tipografías) y se
agrega al final. Su contenido sale íntegramente del anexo de calidad (`calidad.construir`), que sigue disponible completo en el panel y en `anexo_calidad.json`;
aquí solo hay un resumen legible, nunca una cifra nueva del negocio. Letra ≥ 9 pt; formas nombradas `RI_anexo_*` (las que añade el generador).
"""
from __future__ import annotations

from . import pptx_ops as ops
from .extras import BODY, TITLE, _lines, _write, clone_slide

PREFIJO = "RI_anexo_"
SECCIONES_DE_DETALLE = ("estructural", "semantica", "temporal", "integridad", "consistencia", "completitud", "duplicados", "vacios", "tipos", "unidades", "riesgo")
MAX_HALLAZGOS = 6


def _corto(t: str, n: int) -> str:
    t = " ".join(str(t).replace("`", "").split())
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


def resumen(anexo: dict) -> dict:
    """Lo que se imprime: origen, conteos, no verificables, supuestos, hallazgos principales y trazabilidad (todo derivado del anexo, nada nuevo)."""
    dims = {d["id"]: d for d in anexo.get("dimensiones", [])}
    sev = anexo["resumen"]["severidades"]
    orden = {"alta": 0, "media": 1, "baja": 2, "informativa": 3}
    principales = sorted((h for k in SECCIONES_DE_DETALLE for h in dims.get(k, {}).get("hallazgos", []) if h["severidad"] in ("alta", "media")),
                         key=lambda h: (orden[h["severidad"]], h["id"]))[:MAX_HALLAZGOS]
    traz = {h["id"]: h for h in dims.get("trazabilidad", {}).get("hallazgos", [])}
    arch = traz.get("TRA-ARCHIVO", {}).get("evidencia", {})
    ver = traz.get("TRA-VERSIONES", {}).get("evidencia", {})
    return {"origen": anexo["origen_datos"], "severidades": sev, "evaluadas": anexo["resumen"]["dimensiones_evaluadas"], "total": anexo["resumen"]["dimensiones"],
            "no_verificables": [h["descripcion"] for h in dims.get("no_verificables", {}).get("hallazgos", [])],
            "supuestos": [h["descripcion"] for h in dims.get("supuestos", {}).get("hallazgos", [])],
            "principales": [(h["id"], h["severidad"], h["descripcion"]) for h in principales],
            "archivo": arch.get("nombre"), "sha256": arch.get("sha256"), "app": ver.get("app"), "motor": ver.get("motor")}


def add_quality_annex(prs, anexo: dict, slide_map: list[int] | None, n_template: int):
    """Agrega la diapositiva final. Devuelve el mapa de QA actualizado (la nueva se mapea a la plantilla de la que se clonó)."""
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.text import MSO_ANCHOR
    from pptx.util import Emu, Pt
    r = resumen(anexo)
    n = len(prs.slides)
    sl = clone_slide(prs, n - 1, n)
    t, b = ops.shape_by_name(sl, TITLE), ops.shape_by_name(sl, BODY)
    ops.set_simple_text(t, "Calidad de datos y supuestos")
    left, right_x, top_body, h_body = 567871, 7_650_000, 1_320_000, 3_900_000
    b.left, b.top, b.width, b.height = Emu(left), Emu(top_body), Emu(right_x - left - 150_000), Emu(h_body)
    for run in b.text_frame.paragraphs[0].runs:
        run.font.size = Pt(10)
    cpl, max_lines = ops.narrative_box(b)
    max_lines = int(max_lines * 0.95)
    s = r["severidades"]
    ori = r["origen"]
    entradas: list[list] = [  # [texto, prioridad]
        ["**Origen de los datos**", 0], [_corto(ori["detalle"], 230), 0], [_corto(ori["advertencia"], 200), 0],
        ["**Resultado de la evaluación**", 0],
        [f"Hallazgos: {s['alta']} de severidad alta, {s['media']} media y {s['baja']} baja en {r['evaluadas']} de {r['total']} dimensiones evaluadas.", 0],
        ["**Datos no verificables**", 0]] + [["• " + _corto(x, 120), 1 + i] for i, x in enumerate(r["no_verificables"][:4])] + \
        [["**Supuestos y limitaciones**", 0]] + [["• " + _corto(x, 120), 5 + i] for i, x in enumerate(r["supuestos"][:3])]

    def total():
        return sum(_lines(e[0], cpl) for e in entradas) + sum(1 for e in entradas if e[0].startswith("**")) - 1
    while total() > max_lines:                                   # cede lo de menor prioridad; los títulos y el origen nunca se pierden
        cand = [e for e in entradas if e[1] > 0]
        if not cand:
            break
        entradas.remove(max(cand, key=lambda e: (e[1], entradas.index(e))))
    lineas: list[str] = []
    for e in entradas:
        if e[0].startswith("**") and lineas:
            lineas.append("")
        lineas.append(e[0])
    ops.set_paragraphs(b, lineas, align="l")
    # panel derecho: hallazgos principales + trazabilidad
    panel = sl.shapes.add_shape(MSO_SHAPE.RECTANGLE, Emu(right_x), Emu(top_body), Emu(11_640_000 - right_x), Emu(h_body))
    panel.name = PREFIJO + "hallazgos"
    panel.fill.solid()
    panel.fill.fore_color.rgb = RGBColor.from_string("F2F2F2")
    panel.line.fill.background()
    panel.shadow.inherit = False
    panel.text_frame.margin_left = panel.text_frame.margin_right = Emu(100_000)
    panel.text_frame.vertical_anchor = MSO_ANCHOR.TOP
    pcpl = max(int((Emu(11_640_000 - right_x).pt - 16) / (0.45 * 9)), 20)
    cap = int((Emu(h_body).pt - 10) / (1.2 * 9)) - 2
    pl = ["**Hallazgos principales**"]
    usado = 1
    for hid, sev, desc in r["principales"]:
        txt = f"{hid} ({sev}): {_corto(desc, 95)}"
        k = _lines(txt, pcpl) + 0.5
        if usado + k > cap - 6:
            break
        pl.append(txt)
        usado += k
    if not r["principales"]:
        pl.append("Ninguno de severidad alta o media.")
    pl += ["", "**Trazabilidad**", f"Archivo: {_corto(r['archivo'] or 'desconocido', 40)}"]
    if r["sha256"]:
        pl.append(f"SHA-256: {r['sha256'][:16]}…")
    if r["app"]:
        pl.append(f"Aplicación {r['app']} · motor {r['motor']}")
    pl.append("Detalle completo: anexo_calidad.json")
    _write(panel, pl, 9, "404040", gap=3)
    nota = sl.shapes.add_textbox(Emu(left), Emu(6_240_000), Emu(11_640_000 - left), Emu(240_000))
    nota.name = PREFIJO + "nota"
    _write(nota, ["Resumen automático del anexo de calidad de datos: informa, no corrige ni excluye datos. Los resultados de libros de ejemplo o sintéticos no son resultados de producción."], 9, "7F7F7F")
    sm = list(slide_map) if slide_map else list(range(n_template))
    return sm + [sm[-1]]
