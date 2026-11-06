"""Fase 5 · QA VISUAL con render real (spec Fase 1 §7.B; RQ-14; AC-16).

LibreOffice (headless) → PDF → PNG por diapositiva, y sobre ese render:
  * las comprobaciones de PDF que ya existían (`checks.check_render`): texto fuera de la página, invasión del pie, colisión de palabras, cobertura del texto;
  * VISUAL_DIAPOSITIVA_EN_BLANCO · VISUAL_GRAFICA_EN_BLANCO · VISUAL_CONTRASTE_BAJO · VISUAL_INCONSISTENCIA_TITULO (esta fase).
Genera `informe.json` y un visor `informe.html` (una fila por diapositiva: PNG + hallazgos) para la revisión humana de una muestra.

Límites declarados (no se presentan como garantía):
  * LibreOffice ≠ PowerPoint: sustituye fuentes (Aptos Narrow → Carlito) y puede ajustar el texto distinto. Aprobar esta revisión NO garantiza que PowerPoint muestre lo mismo.
  * El contraste se MUESTREA en píxeles del render (color más frecuente = fondo; píxel de mayor contraste = texto): es un indicio, no una medición de accesibilidad.
  * No corre en el navegador (Pyodide): no hay LibreOffice. Requiere `soffice` y `pdftoppm`; sin ellos el resultado es `omitida`, nunca `aprobada`.
  * Privacidad: el PPTX contiene cifras de negocio. Ejecutar esto en GitHub Actions implica subirlo; por omisión solo con datos sintéticos (decisión A-6 de la spec).
"""
from __future__ import annotations

import html
import json
import shutil
from pathlib import Path

from pptx import Presentation
from pptx.util import Emu

from . import checks
from .checks import Issue, QAReport

CONTRASTE_MIN = 2.5                 # relación WCAG por debajo de la cual una palabra se considera casi ilegible (umbral laxo: AA exige 4.5)
BLANCO_STD_MAX = 2.0                # desviación típica (0-255) de una imagen "en blanco"
PALABRAS_MUESTRA = 600
DPI_CONTRASTE = 300                 # el contraste se muestrea a más resolución que los PNG que se entregan: a 110 DPI el suavizado de un trazo fino lo falsea
ALTO_MIN_PX = 6
TOLERANCIA_TITULO_PT = 10.8         # 0.15 in


def disponible() -> tuple[bool, str]:
    faltan = [x for x in ("soffice", "pdftotext", "pdftoppm") if not (shutil.which(x) or (x == "soffice" and shutil.which("libreoffice")))]
    return (not faltan, "" if not faltan else "sin " + ", ".join(faltan))


# --------------------------------------------------------------------------------------------- análisis de imagen
def _luminancia(rgb) -> float:
    def c(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * c(r) + 0.7152 * c(g) + 0.0722 * c(b)


def contraste(a, b) -> float:
    la, lb = _luminancia(a), _luminancia(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _fondo_y_texto(region):
    """(color de fondo = el más frecuente, color de texto = el píxel de mayor contraste frente al fondo) de una región RGB."""
    from collections import Counter
    px = list(region.get_flattened_data() if hasattr(region, "get_flattened_data") else region.getdata())
    fondo = Counter((p[0] // 8 * 8, p[1] // 8 * 8, p[2] // 8 * 8) for p in px).most_common(1)[0][0]
    texto = max(set(px), key=lambda p: contraste(fondo, p))               # el píxel MÁS legible frente al fondo: un borde u otro adorno de color cercano no cuenta como texto
    return fondo, texto


def analizar_imagen(png: Path) -> dict:
    from PIL import Image, ImageStat
    im = Image.open(png).convert("RGB")
    return {"std": float(ImageStat.Stat(im.convert("L")).stddev[0]), "tam": im.size}


def contrastes_bajos(png: Path, palabras, pagina_w: float, pagina_h: float) -> list[tuple[str, float]]:
    from PIL import Image
    im = Image.open(png).convert("RGB")
    sx, sy = im.width / pagina_w, im.height / pagina_h
    malos = []
    paso = max(1, len(palabras) // PALABRAS_MUESTRA)
    for x0, y0, x1, y1, texto in palabras[::paso]:
        box = (max(0, int(x0 * sx)), max(0, int(y0 * sy)), min(im.width, int(x1 * sx) + 1), min(im.height, int(y1 * sy) + 1))
        if box[3] - box[1] < ALTO_MIN_PX or box[2] <= box[0] or not texto.strip():
            continue
        fondo, fg = _fondo_y_texto(im.crop(box))
        r = contraste(fondo, fg)
        if r < CONTRASTE_MIN and sum((fondo[i] - fg[i]) ** 2 for i in range(3)) > 0:
            malos.append((texto, r))
    return malos


def _png_analisis(pdf: Path, pagina: int, out_dir: Path) -> Path:
    """Página `pagina` renderizada a DPI_CONTRASTE solo para el muestreo (no forma parte de la entrega)."""
    import subprocess
    destino = out_dir / "_analisis"
    destino.mkdir(exist_ok=True)
    prefijo = destino / f"p{pagina}"
    subprocess.run(["pdftoppm", "-r", str(DPI_CONTRASTE), "-f", str(pagina), "-l", str(pagina), "-png", "-singlefile", str(pdf), str(prefijo)], check=True, capture_output=True)
    return Path(str(prefijo) + ".png")


# --------------------------------------------------------------------------------------------- reglas sobre el PPTX
def _formas_grafica(slide):
    for sh in slide.shapes:
        if sh._element.tag.endswith("graphicFrame") and not (getattr(sh, "has_table", False) and sh.has_table):
            yield sh


def _titulo(slide):
    for sh in slide.shapes:
        if sh.is_placeholder and sh.placeholder_format.type is not None and "TITLE" in str(sh.placeholder_format.type):
            return sh
    return None


def inconsistencia_titulos(prs) -> list[tuple[int, float]]:
    """Diapositivas cuyo título se aparta de la mediana de las que comparten su diseño (layout)."""
    from statistics import median
    por_layout: dict[str, list[tuple[int, float, float]]] = {}
    for i, s in enumerate(prs.slides, 1):
        t = _titulo(s)
        if t is not None and t.left is not None:
            por_layout.setdefault(s.slide_layout.name, []).append((i, Emu(t.left).pt, Emu(t.top).pt))
    out = []
    for grupo in por_layout.values():
        if len(grupo) < 3:
            continue
        mx, my = median(g[1] for g in grupo), median(g[2] for g in grupo)
        out += [(i, max(abs(x - mx), abs(y - my))) for i, x, y in grupo if max(abs(x - mx), abs(y - my)) > TOLERANCIA_TITULO_PT]
    return out


# --------------------------------------------------------------------------------------------- API
def revisar(pptx: str | Path, out_dir: str | Path, plantilla: str | Path | None = None, dpi: int = 110) -> dict:
    """Informe de QA visual. Si no hay LibreOffice: `{"estado": "omitida", "motivo": ...}` (nunca «aprobada»)."""
    pptx, out_dir = Path(pptx), Path(out_dir)
    ok, motivo = disponible()
    if not ok:
        return {"estado": "omitida", "motivo": f"omitida ({motivo})", "issues": [], "pngs": [], "etiqueta": ETIQUETA_VISUAL}
    from ..render import RenderError, convert_to_pdf, pdf_to_pngs
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        pdf = convert_to_pdf(pptx, out_dir)
        pngs = pdf_to_pngs(pdf, out_dir / "png", dpi=dpi)
    except (RenderError, Exception) as e:                                  # noqa: BLE001
        return {"estado": "error", "motivo": f"no se pudo renderizar ({type(e).__name__}: {str(e)[:120]})", "issues": [], "pngs": [], "etiqueta": ETIQUETA_VISUAL}
    rep = QAReport()
    try:
        checks.check_render(pptx, pdf, rep)
        prs = Presentation(pptx)
        paginas = checks.pdf_words(pdf)
    except Exception as e:                                                 # noqa: BLE001 — un archivo extraño es un resultado «error», no una excepción
        return {"estado": "error", "motivo": f"no se pudo analizar el render ({type(e).__name__})", "issues": [], "pngs": [p.name for p in pngs], "etiqueta": ETIQUETA_VISUAL}
    if len(pngs) == len(prs.slides) == len(paginas):
        for n, (slide, png, pg) in enumerate(zip(prs.slides, pngs, paginas), 1):
            a = analizar_imagen(png)
            tiene_contenido = any((sh.has_text_frame and sh.text_frame.text.strip()) or getattr(sh, "has_table", False) for sh in slide.shapes)
            if a["std"] < BLANCO_STD_MAX and tiene_contenido:
                rep.add("VISUAL_DIAPOSITIVA_EN_BLANCO", "error", n, "El render de la diapositiva está en blanco aunque el PPTX declara contenido.")
            from PIL import Image
            im = Image.open(png).convert("L")
            sx, sy = im.width / Emu(prs.slide_width).pt, im.height / Emu(prs.slide_height).pt
            for g in _formas_grafica(slide):
                box = (int(Emu(g.left).pt * sx), int(Emu(g.top).pt * sy), int((Emu(g.left).pt + Emu(g.width).pt) * sx), int((Emu(g.top).pt + Emu(g.height).pt) * sy))
                box = (max(0, box[0]), max(0, box[1]), min(im.width, box[2]), min(im.height, box[3]))
                if box[2] - box[0] > 20 and box[3] - box[1] > 20:
                    from PIL import ImageStat
                    if ImageStat.Stat(im.crop(box)).stddev[0] < BLANCO_STD_MAX:
                        rep.add("VISUAL_GRAFICA_EN_BLANCO", "warn", n, f"La gráfica «{g.name}» se renderiza vacía (sin variación de color).")
            malos = contrastes_bajos(_png_analisis(pdf, n, out_dir), pg["words"], pg["w"], pg["h"])
            if malos:
                rep.add("VISUAL_CONTRASTE_BAJO", "warn", n, f"{len(malos)} palabra(s) con contraste < {CONTRASTE_MIN} en el render (p. ej. «{malos[0][0]}», {malos[0][1]:.2f}).")
    else:
        rep.add("VISUAL_CONTEO", "error", None, f"PNG ({len(pngs)}), páginas ({len(paginas)}) y diapositivas ({len(prs.slides)}) no coinciden.")
    for n, d in inconsistencia_titulos(prs):
        rep.add("VISUAL_INCONSISTENCIA_TITULO", "warn", n, f"El título se aparta {d:.0f} pt de las diapositivas del mismo diseño.")
    shutil.rmtree(out_dir / "_analisis", ignore_errors=True)
    informe = {"estado": "aprobada" if rep.passed else "rechazada", "etiqueta": ETIQUETA_VISUAL, "dpi": dpi, "pptx": pptx.name,
               "issues": [i.__dict__ for i in rep.issues], "pngs": [p.name for p in pngs], "diapositivas": len(prs.slides)}
    (out_dir / "informe.json").write_text(json.dumps(informe, ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / "informe.html").write_text(visor_html(informe), encoding="utf-8")
    return informe


ETIQUETA_VISUAL = ("Revisión visual con render de LibreOffice (no PowerPoint): fuentes sustituidas y ajuste de texto pueden diferir. "
                   "Es una revisión automática y no sustituye la revisión humana de una muestra.")


def visor_html(informe: dict) -> str:
    """Visor lado a lado: render por diapositiva con sus hallazgos marcados. Todo texto se escapa."""
    por_diap: dict = {}
    for i in informe["issues"]:
        por_diap.setdefault(i["slide"], []).append(i)
    filas = []
    for n, png in enumerate(informe["pngs"], 1):
        hall = "".join(f"<li class='{html.escape(i['severity'])}'><code>{html.escape(i['id'])}</code> {html.escape(i['message'])}</li>" for i in por_diap.get(n, []))
        filas.append(f"<section><h3>Diapositiva {n}</h3><img src='png/{html.escape(png)}' alt='diapositiva {n}'><ul>{hall or '<li>Sin hallazgos</li>'}</ul></section>")
    globales = "".join(f"<li class='{html.escape(i['severity'])}'><code>{html.escape(i['id'])}</code> {html.escape(i['message'])}</li>" for i in por_diap.get(None, []))
    return ("<!doctype html><meta charset='utf-8'><title>QA visual</title><style>body{font:14px system-ui;margin:16px}img{max-width:100%;border:1px solid #ccc}"
            ".error{color:#b00020}.warn{color:#8a5a00}section{margin:12px 0}</style>"
            f"<h1>QA visual · {html.escape(informe['pptx'])} · {html.escape(informe['estado'])}</h1><p>{html.escape(informe['etiqueta'])}</p>"
            f"<ul>{globales}</ul>{''.join(filas)}")
