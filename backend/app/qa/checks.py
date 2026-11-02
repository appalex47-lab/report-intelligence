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
from PIL import Image, ImageChops, ImageStat
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


def _picture_hashes(slide) -> list[str]:
    """SHA-1 del binario de cada imagen (incluye SVG con respaldo PNG), leído desde la relación del XML."""
    out = []
    for sh in slide.shapes:
        if sh.shape_type != 13:
            continue
        for rid in _BLIPS(sh._element):
            out.append(hashlib.sha1(slide.part.related_part(rid).blob).hexdigest())
    return sorted(out)


def check_editable_and_static(out: Path, template: Path, rep: QAReport) -> None:
    a, b = Presentation(template), Presentation(out)
    if len(a.slides) != len(b.slides):
        rep.add("SLIDE_COUNT_CHANGED", "error", None, "El número de diapositivas cambió respecto a la plantilla.")
        return
    for n, (sa, sb) in enumerate(zip(a.slides, b.slides), 1):
        ta = sum(1 for s in sa.shapes if getattr(s, "has_table", False) and s.has_table)
        tb = sum(1 for s in sb.shapes if getattr(s, "has_table", False) and s.has_table)
        if ta != tb:
            rep.add("TABLE_LOST", "error", n, f"Tablas editables: {tb} (plantilla {ta}).")
        if _picture_hashes(sa) != _picture_hashes(sb):
            rep.add("PICTURES_CHANGED", "error", n, "Las imágenes (logos) no son idénticas a las de la plantilla.")
        na = sum(1 for s in sa.shapes if s.has_text_frame)
        nb = sum(1 for s in sb.shapes if s.has_text_frame)
        if na != nb:
            rep.add("TEXT_SHAPES_CHANGED", "error", n, f"Cuadros de texto: {nb} (plantilla {na}).")
        for s in sb.shapes:
            txt = s.text_frame.text if s.has_text_frame else ""
            if re.search(r"\{\{|\[PENDIENTE|\bTODO\b", txt):
                rep.add("PLACEHOLDER_LEFT", "error", n, f"Marcador sin rellenar en '{s.name}'.")


def check_static_regions(png_out: list[Path], png_tpl: list[Path], rep: QAReport) -> None:
    """Barras, logos y pie de página deben ser idénticos a los de la plantilla renderizada."""
    zones = {"barra superior": (0.0, 0.0, 1.0, 0.07), "logo superior": (0.80, 0.04, 1.0, 0.17),
             "logo inferior": (0.80, 0.90, 1.0, 1.0), "barra inferior": (0.0, 0.985, 1.0, 1.0)}
    for n, (po, pt) in enumerate(zip(png_out, png_tpl), 1):
        io, it = Image.open(po).convert("L"), Image.open(pt).convert("L")
        if io.size != it.size:
            rep.add("RENDER_SIZE_DIFF", "error", n, "El render tiene otro tamaño que la plantilla.")
            continue
        W, H = io.size
        for name, (x0, y0, x1, y1) in zones.items():
            box = (int(x0 * W), int(y0 * H), int(x1 * W), int(y1 * H))
            d = ImageChops.difference(io.crop(box), it.crop(box))
            mean = ImageStat.Stat(d).mean[0]
            if mean > STATIC_DIFF_MAX:
                rep.add("STATIC_REGION_CHANGED", "error", n, f"'{name}' difiere de la plantilla (Δ medio {mean:.1f}).")


def check_stale(fill_report, rep: QAReport) -> None:
    for s in fill_report.stale:
        rep.add("STALE_DATA", "error", None, f"Dato de la plantilla sin sustituir: {s}")
