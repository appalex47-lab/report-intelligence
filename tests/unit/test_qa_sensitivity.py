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


def _logo(tmp_path):
    from PIL import Image
    p = tmp_path / "logo.png"
    Image.new("RGB", (200, 100), (232, 98, 42)).save(p)
    return p


def test_a_moved_or_missing_logo_is_flagged_using_real_geometry(tmp_path):
    from backend.app.render import pdf_to_pngs
    logo = _logo(tmp_path)

    def tpl(s):
        s.shapes.add_picture(str(logo), Inches(10.5), Inches(0.2), Inches(2), Inches(1))

    def moved(s):
        s.shapes.add_picture(str(logo), Inches(8.0), Inches(2.0), Inches(2), Inches(1))

    def missing(s):
        text(s, 1, 4, 3, 0.5, "sin logo")

    t = deck(tmp_path, "tpl", tpl)
    tp = pdf_to_pngs(convert_to_pdf(t, tmp_path / "t"), tmp_path / "t" / "png")
    for name, builder in (("moved", moved), ("missing", missing)):
        o = deck(tmp_path, name, builder)
        op = pdf_to_pngs(convert_to_pdf(o, tmp_path / name), tmp_path / name / "png")
        rep = checks.QAReport()
        checks.check_static_regions(op, tp, rep, t)
        assert "STATIC_REGION_CHANGED" in {i.id for i in rep.issues}, name
    same = deck(tmp_path, "same", tpl)
    sp = pdf_to_pngs(convert_to_pdf(same, tmp_path / "s"), tmp_path / "s" / "png")
    rep = checks.QAReport()
    checks.check_static_regions(sp, tp, rep, t)
    assert rep.passed


def test_content_overlapping_a_fixed_logo_zone_does_not_hide_the_logo_check(tmp_path):
    """Una tabla que pasa por debajo del logo NO debe dar falsos positivos si el logo no se tocó."""
    from backend.app.render import pdf_to_pngs
    logo = _logo(tmp_path)

    def tpl(s):
        s.shapes.add_picture(str(logo), Inches(10.5), Inches(0.2), Inches(2), Inches(0.6))
        text(s, 1, 1.0, 5, 0.5, "x")

    def out(s):
        s.shapes.add_picture(str(logo), Inches(10.5), Inches(0.2), Inches(2), Inches(0.6))
        text(s, 11, 1.0, 2, 0.5, "contenido bajo el logo")           # texto en la zona alta-derecha, fuera del logo

    t, o = deck(tmp_path, "t", tpl), deck(tmp_path, "o", out)
    tp = pdf_to_pngs(convert_to_pdf(t, tmp_path / "tt"), tmp_path / "tt" / "png")
    op = pdf_to_pngs(convert_to_pdf(o, tmp_path / "oo"), tmp_path / "oo" / "png")
    rep = checks.QAReport()
    checks.check_static_regions(op, tp, rep, t)
    assert rep.passed, [i.message for i in rep.issues]
