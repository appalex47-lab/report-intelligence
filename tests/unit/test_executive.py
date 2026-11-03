from decimal import Decimal

import pytest
from pptx import Presentation
from pptx.util import Inches

from backend.app.deck import pptx_ops as ops
from backend.app.deck.extras import clone_slide
from backend.app.models import Period
from backend.app.narrative.executive import PRIO, build_executive, prio_of, product_key
from backend.app.narrative.rules import RULES
from backend.app.narrative.writer import verify_all
from backend.app.pipeline import run_aetops
from tests.fixtures import build_base

SEP = Period("AETOPS", "mensual", 2026, 9)


@pytest.fixture(scope="module")
def ex(tmp_path_factory):
    res = run_aetops(build_base(tmp_path_factory.mktemp("e") / "syn"), "mensual", SEP)
    return build_executive(res, SEP), res


def test_product_key_matches_the_same_product_across_lists():
    assert product_key("PAMORELIN 22.5 MG SUS INY FAM CAJ") == product_key("PAMORELIN 22.5 mg SUS INY")
    assert product_key("PAMORELIN 22.5 MG") != product_key("PAMORELIN 11.25 MG")
    assert product_key("PROLIA 60MG/1ML JPRELL CAJ")[0] == "PROLIA"


def test_priority_thresholds_and_actionability_weights():
    assert prio_of(Decimal("0.08"), RULES) == "alta" and prio_of(Decimal("0.04"), RULES) == "media"
    assert prio_of(Decimal("0.01"), RULES) == "baja"
    assert RULES.weight("abasto") > RULES.weight("proteger") > RULES.weight("investigar") > RULES.weight("vigilar")


def test_every_recommendation_has_rule_evidence_and_verified_figures(ex):
    e, _ = ex
    assert e.recomendaciones and len(e.recomendaciones) <= RULES.max_recommendations
    assert verify_all(e.resumen + e.recomendaciones) == []
    for p in e.recomendaciones:
        assert p.kind == "recomendacion" and p.basis
        assert any(f"[{t}]" in p.plain for t in PRIO.values())
    scores = [r.score for r in e.recs]
    assert scores == sorted(scores, reverse=True)                      # ordenadas por puntaje


def test_negado_recommendation_uses_the_business_definition_and_flags_the_scenario(ex):
    e, res = ex
    r = next(p for p in e.recomendaciones if "abasto" in p.plain)
    assert "productos sin stock que se negaron a la venta" in r.plain
    assert "Escenario ilustrativo: recuperar 25%" in r.plain
    assert "ilustrativo, no pronóstico" in r.basis
    # el escenario es aritmética sobre el monto negado: 25 % de 1000 = 250
    assert "+$250" in r.plain


def test_summary_has_the_three_blocks_and_no_causal_language(ex):
    e, _ = ex
    text = " ".join(p.plain for p in e.resumen)
    assert "Dónde estamos" in text and "Descubrimientos del periodo" in text and "Qué hacer" in text
    for banned in ("debido a", "porque", "por falta de", "gracias a"):
        assert banned not in text.lower()


def test_discoveries_are_ranked_by_materiality(ex):
    e, _ = ex
    scores = [s for s, _ in e.descubrimientos]
    assert scores == sorted(scores, reverse=True) and scores[0] == 10        # la salud del periodo va primero


def test_clone_slide_preserves_pictures_order_and_leaves_source_untouched(tmp_path):
    from PIL import Image
    img = tmp_path / "logo.png"
    Image.new("RGB", (40, 20), (200, 80, 20)).save(img)
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    for _ in range(2):
        s = prs.slides.add_slide(prs.slide_layouts[6])
        s.shapes.add_picture(str(img), Inches(1), Inches(1), Inches(1), Inches(0.5))
        tb = s.shapes.add_textbox(Inches(1), Inches(3), Inches(4), Inches(1))
        tb.text_frame.text = "original"
    new = clone_slide(prs, 1, 0)
    assert len(prs.slides) == 3 and prs.slides[0] is not None
    first = prs.slides[0]
    assert [sh.shape_type for sh in first.shapes].count(13) == 1
    pic = [sh for sh in first.shapes if sh.shape_type == 13][0]
    assert pic.image.blob == [sh for sh in prs.slides[2].shapes if sh.shape_type == 13][0].image.blob
    ops.set_simple_text([sh for sh in first.shapes if sh.has_text_frame][0], "clon")
    assert [sh for sh in prs.slides[2].shapes if sh.has_text_frame][0].text_frame.text == "original"
    out = tmp_path / "o.pptx"
    prs.save(out)
    assert len(Presentation(out).slides) == 3                                   # el archivo se guarda y reabre
