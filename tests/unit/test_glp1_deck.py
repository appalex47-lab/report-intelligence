"""Generador GLP-1 mensual (requiere la plantilla real, que no se versiona)."""
import importlib.util
import re
import shutil
from pathlib import Path

import pytest
from decimal import Decimal

from pptx import Presentation

from backend.app.build import build_glp1
from backend.app.models import Period
from backend.app.pipeline import run_glp1_raw

ROOT = Path(__file__).resolve().parents[2]
TPL = ROOT / "templates/glp1-mensual/1/template.pptx"
pytestmark = pytest.mark.skipif(not TPL.exists() or not shutil.which("soffice"), reason="requiere la plantilla real (no se versiona) y LibreOffice")
spec = importlib.util.spec_from_file_location("mg", ROOT / "tools/make_raw_glp1_synthetic.py")
mg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mg)
P9 = Period("GLP1", "mensual", 2026, 9)


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    d = tmp_path_factory.mktemp("g")
    res = run_glp1_raw(mg.build(d / "g.xlsx"), P9)
    return res, build_glp1(res, P9, TPL, d / "out")


def texts(path):
    prs = Presentation(path)
    out = []
    for s in prs.slides:
        for sh in s.shapes:
            if sh.has_text_frame:
                out.append(sh.text_frame.text)
            if getattr(sh, "has_table", False) and sh.has_table:
                out += [c.text for r in sh.table.rows for c in r.cells]
    return out


def test_qa_passes_and_outputs_exist(built):
    _res, b = built
    assert b.qa.passed and b.downloadable and b.pptx.exists() and b.pdf.exists() and len(b.pngs) == 13
    assert b.fill.narrative_problems == [] and b.fill.stale == []


def test_no_template_month_data_survives(built):
    _res, b = built
    blob = "\n".join(texts(b.pptx)).lower()
    assert "31 de agosto" not in blob and "mounjaro kwikpen" not in blob and "afectación" not in blob


def test_tables_match_engine(built):
    res, b = built
    prs = Presentation(b.pptx)
    t = [sh for sh in prs.slides[5].shapes if sh.name == "Tabla 8"][0].table
    rows = {r.cells[0].text: r for r in list(t.rows)[1:]}
    for g in res.blocks["region"].rows:
        c = rows[g.key.upper()].cells
        assert c[1].text.replace(",", "") == str(int(g.values["pedidos"].v))
        assert c[3].text.replace(",", "").replace("$", "") == str(int(round(g.values["monto"].v)))
    f = [sh for sh in prs.slides[7].shapes if sh.name == "Tabla 8"][0].table
    assert f.cell(0, 4).text.replace(",", "") == str(int(res.funnel.rows[0].values["conteo"].v))
    assert f.cell(8, 0).text == "Carritos abandonados"


def test_narrative_numbers_are_registered_and_sexes_translated(built):
    _res, b = built
    for key, ps in b.fill.narrative.items():
        for p in ps:
            assert p.kind in ("hecho", "interpretacion", "recomendacion"), (key, p.kind)
            if p.kind != "hecho":
                assert p.basis
    blob = "\n".join(texts(b.pptx))
    assert "Femenino" not in blob and "Mujer" in blob


def test_edited_text_is_flagged_when_number_unsupported(tmp_path):
    res = run_glp1_raw(mg.build(tmp_path / "g.xlsx"), P9)
    b = build_glp1(res, P9, TPL, tmp_path / "o", narrative={"conclusiones": ["Vendimos $999 M por una promoción"]})
    assert any("999" in x for x in b.fill.edited_unverified)


def test_canal_pago_organico_from_source_medium():
    from backend.app.raw.glp1 import clasificar_fuente as c
    assert [c(x) for x in ("google / cpc", "Paid Social", "Cross-network", "Organic Search", "google / organic", "(direct) / (none)",
                           "facebook / paid_social", "Referral", "Unassigned")] == ["Pago", "Pago", "Pago", "Orgánico", "Orgánico", "Orgánico",
                                                                                   "Pago", "Orgánico", "Sin asignar"]


def test_canal_subtable_matches_sum_of_sources(built):
    res, b = built
    can = {r.key: r for r in res.blocks["canal_resumen"].rows}
    fu = res.blocks["fuentes"].rows
    paid = sum(r.values["visitas"].v for r in fu if r.key.lower().startswith(("paid", "cross")))
    assert can["Pago"].values["visitas"].v == paid
    assert sum(r.values["visitas"].v for r in can.values()) == sum(r.values["visitas"].v for r in fu)


def test_quarterly_uses_quarter_labels_and_passes_qa(tmp_path):
    tq = ROOT / "templates/glp1-trimestral/1/template.pptx"
    if not tq.exists():
        pytest.skip("plantilla trimestral no disponible")
    q3 = Period("GLP1", "trimestral", 2026, 3)
    res = run_glp1_raw(mg.build(tmp_path / "g.xlsx", n_months=18), q3)
    b = build_glp1(res, q3, tq, tmp_path / "o")
    blob = "\n".join(texts(b.pptx))
    assert b.qa.passed and b.pptx.name == "Resultados_GLP1_Q3_2026.pptx" and "vs Q2 2026" in blob and "septiembre" not in blob.lower()


def test_executive_and_recommendation_slides_are_added(built):
    _res, b = built
    prs = Presentation(b.pptx)
    titles = [next((sh.text_frame.text for sh in s.shapes if sh.name == "CuadroTexto 9"), "") for s in prs.slides]
    assert titles[0] == "Resumen Ejecutivo" and titles[-1] == "Recomendaciones" and len(prs.slides) == 13
    assert "resumen_ejecutivo" in b.fill.narrative and "recomendaciones" in b.fill.narrative


def test_context_and_goal_reach_the_deck(tmp_path):
    from backend.app.targets import Targets
    res = run_glp1_raw(mg.build(tmp_path / "g.xlsx"), P9)
    b = build_glp1(res, P9, TPL, tmp_path / "o", context=["Campaña de verano del 10 al 20."], targets=Targets(Decimal(9_000_000), {}),
                   history_db=tmp_path / "h.sqlite")
    blob = "\n".join(texts(b.pptx))
    assert "Campaña de verano" in blob and "de la meta" in blob
    assert any(i.id == "CONTEXT_UNVERIFIED" for i in b.qa.issues) and b.qa.passed
    assert (tmp_path / "o" / "trends.json").exists() and b.manifest["historial"]["version"] == 1
