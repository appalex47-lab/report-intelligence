"""El QA debe FALLAR cuando hay un problema real (no solo pasar cuando todo va bien)."""
import shutil
from pathlib import Path

import pytest
from pptx import Presentation
from pptx.util import Inches, Pt

from backend.app.qa import checks
from backend.app.render import convert_to_pdf

pytestmark = pytest.mark.skipif(not shutil.which("soffice"), reason="LibreOffice no disponible")


def deck(tmp_path: Path, name: str, builder) -> Path:
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    s = prs.slides.add_slide(prs.slide_layouts[6])
    builder(s)
    p = tmp_path / f"{name}.pptx"
    prs.save(p)
    return p


def text(s, x, y, w, h, t, size=14):
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tb.text_frame.text = t
    tb.text_frame.paragraphs[0].runs[0].font.size = Pt(size)
    return tb


def run_qa(tmp_path, name, builder):
    p = deck(tmp_path, name, builder)
    pdf = convert_to_pdf(p, tmp_path)
    rep = checks.QAReport()
    checks.check_render(p, pdf, rep)
    return {i.id for i in rep.issues if i.severity == "error"}


def test_clean_slide_passes(tmp_path):
    assert run_qa(tmp_path, "ok", lambda s: text(s, 1, 1, 5, 1, "Venta total $11,560,021 crece +67%")) == set()


def test_content_over_the_footer_is_flagged(tmp_path):
    errs = run_qa(tmp_path, "foot", lambda s: text(s, 1, 7.15, 5, 0.3, "$54,781 invade el pie de página"))
    assert "OVERFLOW_INTO_FOOTER" in errs


def test_text_outside_the_page_is_flagged(tmp_path):
    errs = run_qa(tmp_path, "out", lambda s: text(s, 13.0, 1, 3, 0.5, "Texto que se sale por la derecha"))
    assert "TEXT_OUT_OF_PAGE" in errs


def test_overlapping_text_is_flagged(tmp_path):
    def b(s):
        text(s, 1, 1, 5, 1, "Monto Venta total 1,000,000")
        text(s, 1.1, 1.05, 5, 1, "Pacientes pedidos 2,000,000")
    assert "TEXT_COLLISION" in run_qa(tmp_path, "coll", b)


def test_lost_table_and_changed_pictures_are_flagged(tmp_path):
    def with_table(s):
        s.shapes.add_table(2, 2, Inches(1), Inches(1), Inches(4), Inches(1))
        text(s, 1, 4, 5, 1, "x")
    tpl = deck(tmp_path, "tpl", with_table)
    out = deck(tmp_path, "out", lambda s: text(s, 1, 4, 5, 1, "x"))
    rep = checks.QAReport()
    checks.check_editable_and_static(out, tpl, rep)
    assert "TABLE_LOST" in {i.id for i in rep.issues}


def test_placeholders_left_in_text_are_flagged(tmp_path):
    tpl = deck(tmp_path, "tpl", lambda s: text(s, 1, 1, 5, 1, "x"))
    out = deck(tmp_path, "out", lambda s: text(s, 1, 1, 5, 1, "Venta {{monto}}"))
    rep = checks.QAReport()
    checks.check_editable_and_static(out, tpl, rep)
    assert "PLACEHOLDER_LEFT" in {i.id for i in rep.issues}
