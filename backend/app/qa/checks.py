"""Control de calidad antes de habilitar la descarga (docs/ARQUITECTURA.md §10).

Las reglas se calibran contra el PPTX original sin modificar (debe salir sin errores).
"""
from __future__ import annotations

import hashlib
import re
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.util import Emu

EMU_PT = 1 / 12700
TOKEN = re.compile(r"[\w$%.,+\-/()]+", re.UNICODE)
COLLISION_IOU = 0.35
STATIC_DIFF_MAX = 4.0           # diferencia media (0-255) tolerada en zonas estáticas
TEXT_COVERAGE_MIN = 0.97


@dataclass
class Issue:
    id: str
    severity: str               # error | warn | info
    slide: int | None
    message: str


@dataclass
class QAReport:
    issues: list[Issue] = field(default_factory=list)

    def add(self, id_, sev, slide, msg):
        self.issues.append(Issue(id_, sev, slide, msg))

    @property
    def passed(self) -> bool:
        return not any(i.severity == "error" for i in self.issues)

    def to_dict(self):
        return {"passed": self.passed, "issues": [i.__dict__ for i in self.issues]}


# ----------------------------------------------------------------------------- PDF
def pdf_words(pdf: Path) -> list[dict]:
    """[{'page':1,'w':960,'h':540,'words':[(x0,y0,x1,y1,text),...]}] vía pdftotext -bbox-layout."""
    out = subprocess.run(["pdftotext", "-bbox-layout", str(pdf), "-"], check=True, capture_output=True).stdout
    root = ET.fromstring(out)
    pages = []
    for i, pg in enumerate(root.iter("{http://www.w3.org/1999/xhtml}page"), 1):
        words = [(float(w.get("xMin")), float(w.get("yMin")), float(w.get("xMax")), float(w.get("yMax")),
                  w.text or "") for w in pg.iter("{http://www.w3.org/1999/xhtml}word")]
        pages.append({"page": i, "w": float(pg.get("width")), "h": float(pg.get("height")), "words": words})
    return pages


def _iou_small(a, b) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    small = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return inter / small if small > 0 else 0.0


def _slide_tokens(slide) -> list[str]:
    toks: list[str] = []
    for sh in slide.shapes:
        if sh.has_text_frame:
            toks += TOKEN.findall(sh.text_frame.text)
        if getattr(sh, "has_table", False) and sh.has_table:
            for row in sh.table.rows:
                for c in row.cells:
                    toks += TOKEN.findall(c.text_frame.text)
    return toks


def footer_geometry(prs) -> tuple[float, set[str]]:
    """Parte alta del pie de página (pt) y sus palabras, tomados de la plantilla."""
    for sh in prs.slides[0].shapes:
        if sh.is_placeholder and "pie" in sh.name.lower() and sh.has_text_frame:
            return Emu(sh.top).pt, {t.lower() for t in TOKEN.findall(sh.text_frame.text)}
    return 7.05 * 72, set()


def check_render(pptx: Path, pdf: Path, rep: QAReport) -> None:
    prs = Presentation(pptx)
    pages = pdf_words(pdf)
    if len(pages) != len(prs.slides):
        rep.add("PAGE_COUNT_MISMATCH", "error", None,
                f"El PDF tiene {len(pages)} páginas y el PPTX {len(prs.slides)} diapositivas.")
        return
    footer_top, footer_tokens = footer_geometry(prs)
    for n, (slide, pg) in enumerate(zip(prs.slides, pages), 1):
        words = pg["words"]
        # (1) fuera de la página
        out = [w for w in words if w[2] > pg["w"] + 1 or w[3] > pg["h"] + 1 or w[0] < -1 or w[1] < -1]
        if out:
            rep.add("TEXT_OUT_OF_PAGE", "error", n, f"{len(out)} palabra(s) fuera de la página (p. ej. '{out[0][4]}').")
        # (2) contenido invadiendo el pie de página
        inv = [w for w in words if w[3] > footer_top + 1 and w[4].lower() not in footer_tokens]
        if inv:
            rep.add("OVERFLOW_INTO_FOOTER", "error", n,
                    f"{len(inv)} palabra(s) de contenido invaden el pie de página (p. ej. '{inv[0][4]}').")
        # (3) colisión de textos
        coll = 0
        ws = sorted(words, key=lambda w: w[1])
        for i, a in enumerate(ws):
            for b in ws[i + 1:]:
                if b[1] > a[3]:
                    break
                if _iou_small(a, b) > COLLISION_IOU:
                    coll += 1
        if coll:
            rep.add("TEXT_COLLISION", "error", n, f"{coll} par(es) de palabras se superponen en el PDF.")
        # (4) el PDF contiene lo que dice el PPTX
        want = [t.lower() for t in _slide_tokens(slide)]
        have = {w[4].lower() for w in words}
        have_joined = " ".join(w[4].lower() for w in words)
        miss = [t for t in want if t not in have and t not in have_joined]
        cov = 1 - len(miss) / len(want) if want else 1.0
        if cov < TEXT_COVERAGE_MIN:
            rep.add("PDF_TEXT_MISMATCH", "error", n,
                    f"Solo {cov:.0%} del texto del PPTX aparece en el PDF (p. ej. '{miss[0]}').")


# ----------------------------------------------------------------------------- PPTX
_BLIPS = etree.XPath(".//a:blip/@r:embed | .//asvg:svgBlip/@r:embed", namespaces={
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "asvg": "http://schemas.microsoft.com/office/drawing/2016/SVG/main"})


ADDED = "RI_"        # prefijo de las formas que añade el generador (embudo, notas): no cuentan como cambio de la plantilla


def _picture_hashes(slide, ignore: set[str] = frozenset()) -> list[str]:
    """SHA-1 del binario de cada imagen (incluye SVG con respaldo PNG), leído desde la relación del XML.
    `ignore`: nombres de imágenes decorativas (p. ej. coronas) que el generador puede mover o quitar."""
    out = []
    for sh in slide.shapes:
        if sh.shape_type != 13 or sh.name in ignore:
            continue
        for rid in _BLIPS(sh._element):
            out.append(hashlib.sha1(slide.part.related_part(rid).blob).hexdigest())
    return sorted(out)


def check_editable_and_static(out: Path, template: Path, rep: QAReport, slide_map: list[int] | None = None,
                              decorative: dict[int, set[str]] | None = None) -> None:
    """`slide_map[i]` = diapositiva de la plantilla de la que proviene la i-ésima del resultado (las clonadas)."""
    a, b = Presentation(template), Presentation(out)
    slide_map = slide_map or list(range(len(a.slides)))
    if len(slide_map) != len(b.slides):
        rep.add("SLIDE_COUNT_CHANGED", "error", None,
                f"El resultado tiene {len(b.slides)} diapositivas y se esperaban {len(slide_map)}.")
        return
    for n, (it, sb) in enumerate(zip(slide_map, b.slides), 1):
        sa = a.slides[it]
        ta = sum(1 for s in sa.shapes if getattr(s, "has_table", False) and s.has_table)
        tb = sum(1 for s in sb.shapes if getattr(s, "has_table", False) and s.has_table)
        if ta != tb:
            rep.add("TABLE_LOST", "error", n, f"Tablas editables: {tb} (plantilla {ta}).")
        deco = (decorative or {}).get(it, set())
        if _picture_hashes(sa, deco) != _picture_hashes(sb, deco):
            rep.add("PICTURES_CHANGED", "error", n, "Las imágenes (logos) no son idénticas a las de la plantilla.")
        na = sum(1 for s in sa.shapes if s.has_text_frame and not s.name.startswith(ADDED))
        nb = sum(1 for s in sb.shapes if s.has_text_frame and not s.name.startswith(ADDED))
        if na != nb:
            rep.add("TEXT_SHAPES_CHANGED", "error", n, f"Cuadros de texto: {nb} (plantilla {na}).")
        for s in sb.shapes:
            txt = s.text_frame.text if s.has_text_frame else ""
            if re.search(r"\{\{|\[PENDIENTE|\bTODO\b", txt):
                rep.add("PLACEHOLDER_LEFT", "error", n, f"Marcador sin rellenar en '{s.name}'.")


def static_zones(template: Path, slide_idx: int, skip: set[str] = frozenset()) -> dict[str, tuple[float, float, float, float]]:
    """Cajas (fracciones de la diapositiva) de los elementos fijos de la plantilla: imágenes, barras y pie de página."""
    prs = Presentation(template)
    W, H = prs.slide_width, prs.slide_height
    zones = {}
    for sh in prs.slides[slide_idx].shapes:
        fixed = sh.shape_type == 13 or sh.name.startswith("Rect") or (sh.is_placeholder and "pie" in sh.name.lower())
        if not fixed or not sh.width or not sh.height or sh.name in skip:
            continue
        m = 0.004                                                      # margen para el antialiasing
        zones[sh.name] = (max(sh.left / W - m, 0), max(sh.top / H - m, 0),
                          min((sh.left + sh.width) / W + m, 1), min((sh.top + sh.height) / H + m, 1))
    return zones


def check_static_regions(png_out: list[Path], png_tpl: list[Path], rep: QAReport, template: Path | None = None,
                         slide_map: list[int] | None = None, decorative: dict[int, set[str]] | None = None) -> None:
    """Logos, barras y pie de página deben ser idénticos a los de la plantilla renderizada (geometría real del PPTX)."""
    from PIL import Image, ImageChops, ImageStat                      # solo con render (no se carga en el navegador)
    slide_map = slide_map or list(range(len(png_out)))
    for n, (po, ti) in enumerate(zip(png_out, slide_map), 1):
        pt = png_tpl[ti]
        io, it = Image.open(po).convert("L"), Image.open(pt).convert("L")
        if io.size != it.size:
            rep.add("RENDER_SIZE_DIFF", "error", n, "El render tiene otro tamaño que la plantilla.")
            continue
        W, H = io.size
        zones = static_zones(template, ti, (decorative or {}).get(ti, set())) if template else {
            "barra superior": (0.0, 0.0, 1.0, 0.07), "logo inferior": (0.80, 0.90, 1.0, 1.0)}
        for name, (x0, y0, x1, y1) in zones.items():
            box = (int(x0 * W), int(y0 * H), max(int(x1 * W), int(x0 * W) + 1), max(int(y1 * H), int(y0 * H) + 1))
            d = ImageChops.difference(io.crop(box), it.crop(box))
            mean = ImageStat.Stat(d).mean[0]
            if mean > STATIC_DIFF_MAX:
                rep.add("STATIC_REGION_CHANGED", "error", n, f"'{name}' difiere de la plantilla (Δ medio {mean:.1f}).")


# ----------------------------------------------------------------------------- geometría (sin render)
CHAR_EM = 0.42           # ancho medio de carácter en em (Aptos Narrow ≈ 0.40-0.46)
LINE_EM = 1.2


def _font_pt(cell, default: float = 10.0) -> float:
    for r in cell._tc.iter("{http://schemas.openxmlformats.org/drawingml/2006/main}rPr"):
        if r.get("sz"):
            return int(r.get("sz")) / 100
    for r in cell._tc.iter("{http://schemas.openxmlformats.org/drawingml/2006/main}endParaRPr"):
        if r.get("sz"):
            return int(r.get("sz")) / 100
    return default


def row_min_heights(shape) -> list[float]:
    """Alto mínimo (pt) que necesita el texto de cada fila de una tabla (0 si la fila está vacía). Misma estimación que el QA."""
    tbl = shape.table
    widths = [Emu(c.width).pt for c in tbl.columns]
    out = []
    for row in tbl.rows:
        need = 0.0
        for ci, cell in enumerate(row.cells):
            if cell.is_spanned:
                continue
            text = cell.text_frame.text
            if not text.strip():
                continue
            span = cell.span_width if cell.is_merge_origin else 1
            usable = max(sum(widths[ci:ci + span]) - 3.0, 6.0)
            fs = _font_pt(cell)
            cpl = max(int(usable / (CHAR_EM * fs)), 1)
            lines = sum(max(1, -(-len(par) // cpl)) for par in text.split("\n"))
            need = max(need, lines * fs * LINE_EM + 1.5)
        out.append(need)
    return out


def row_content_floors(shape) -> list[float]:
    """Alto mínimo REAL (pt) de cada fila: incluye las celdas «en blanco» (un NBSP conserva su tamaño de letra y fuerza la altura de
    la fila) y los márgenes de celda. Es la cota inferior a la que se puede compactar una fila sin que el render la vuelva a estirar."""
    tbl = shape.table
    widths = [Emu(c.width).pt for c in tbl.columns]
    out = []
    for row in tbl.rows:
        need = 0.0
        for ci, cell in enumerate(row.cells):
            if cell.is_spanned:
                continue
            span = cell.span_width if cell.is_merge_origin else 1
            usable = max(sum(widths[ci:ci + span]) - 3.0, 6.0)
            fs = _font_pt(cell)
            cpl = max(int(usable / (CHAR_EM * fs)), 1)
            lines = sum(max(1, -(-len(par) // cpl)) for par in cell.text_frame.text.split("\n"))
            need = max(need, lines * fs * 1.22 + Emu(cell.margin_top).pt + Emu(cell.margin_bottom).pt + 1.0)
        out.append(need)
    return out


def estimate_table_height(shape) -> float:
    """Alto estimado (pt) de una tabla: cada fila crece si el texto de alguna celda no cabe en una línea."""
    return sum(max(Emu(row.height).pt, need) for row, need in zip(shape.table.rows, row_min_heights(shape)))


def check_geometry(pptx: Path, rep: QAReport, template: Path | None = None, slide_map: list[int] | None = None) -> None:
    """Sin render: una tabla cuyo alto estimado la hace invadir el pie de página se señala (aviso; el QA visual es el definitivo).
    Con plantilla, solo se avisa si la tabla crece frente a su versión original (lo que ya cabía en la plantilla no se cuestiona)."""
    prs = Presentation(pptx)
    footer_top, _ = footer_geometry(prs)
    tpl = Presentation(template) if template else None
    smap = slide_map or (list(range(len(tpl.slides))) if tpl else [])
    for n, slide in enumerate(prs.slides, 1):
        base = {}
        if tpl is not None and n - 1 < len(smap):
            for sh in tpl.slides[smap[n - 1]].shapes:
                if getattr(sh, "has_table", False) and sh.has_table:
                    base[sh.name] = Emu(sh.top).pt + estimate_table_height(sh)
        for sh in slide.shapes:
            if getattr(sh, "has_table", False) and sh.has_table:
                bottom = Emu(sh.top).pt + estimate_table_height(sh)
                if bottom > footer_top + 1 and bottom > base.get(sh.name, 0) + 6:
                    rep.add("OVERFLOW_ESTIMATED", "error" if bottom > footer_top + 12 else "warn", n,
                            f"La tabla '{sh.name}' podría invadir el pie de página (borde inferior estimado {bottom:.0f} pt; pie en {footer_top:.0f} pt): "
                            "acorta nombres o reduce filas.")


def check_stale(fill_report, rep: QAReport) -> None:
    for s in fill_report.stale:
        rep.add("STALE_DATA", "error", None, f"Dato de la plantilla sin sustituir: {s}")
