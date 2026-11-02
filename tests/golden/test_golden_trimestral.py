"""Fase 5b · AETOPS trimestral con la plantilla Q1 y el Excel Q3 reales (NO están en el repo)."""
import glob
import os
import re
import shutil
from pathlib import Path

import pytest
from pptx import Presentation

from backend.app.build import build_aetops
from backend.app.models import Period
from backend.app.pipeline import run_aetops
from backend.app.qa import checks
from backend.app.render import convert_to_pdf
from tests.fixtures import build_base

D = os.environ.get("REPORT_FIXTURES_DIR")
TPL = glob.glob(os.path.join(D, "*Resultados_AETOP_Q1_2026.pptx")) if D else []
XL = glob.glob(os.path.join(D, "*AETOPS_2026_Trimestre_Q3.xlsx")) if D else []
pytestmark = pytest.mark.skipif(not (TPL and XL and shutil.which("soffice")),
                                reason="faltan la plantilla Q1 / Excel Q3 reales o LibreOffice")
Q3 = Period("AETOPS", "trimestral", 2026, 3)


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    res = run_aetops(XL[0], "trimestral", Q3)
    assert res.can_generate
    return res, build_aetops(res, Q3, Path(TPL[0]), tmp_path_factory.mktemp("q3"))


def all_text(prs):
    out = []
    for s in prs.slides:
        for sh in s.shapes:
            if sh.has_text_frame:
                out.append(sh.text_frame.text)
            if getattr(sh, "has_table", False) and sh.has_table:
                out += [c.text for r in sh.table.rows for c in r.cells]
    return out


def test_original_q1_template_passes_qa_baseline(tmp_path):
    pdf = convert_to_pdf(Path(TPL[0]), tmp_path)
    rep = checks.QAReport()
    checks.check_render(Path(TPL[0]), pdf, rep)
    assert rep.passed, [(i.id, i.slide, i.message) for i in rep.issues]


def test_real_q3_report_is_publishable(built):
    res, b = built
    assert b.downloadable, [(i.id, i.slide, i.message) for i in b.qa.issues if i.severity == "error"]
    assert len(b.pngs) == 8 and b.pdf.exists() and b.fill.stale == [] and b.fill.narrative_problems == []


def test_quarter_labels_replace_the_template_ones(built):
    _, b = built
    texts = all_text(Presentation(b.pptx))
    assert not [t for t in texts if re.search(r"\bQ1\b", t)], "quedó un 'Q1' de la plantilla"
    assert any("Venta Q3 Actual 2026" in t for t in texts) and any("Venta Q3 Año 2025" in t for t in texts)
    prose = " ".join(t for t in texts if len(t) > 60)
    assert "mes anterior" not in prose and "julio" not in prose.lower()          # no es un reporte mensual


def test_values_come_from_the_workbook(built):
    res, b = built
    p = Presentation(b.pptx)
    pano = [sh for sh in p.slides[0].shapes if sh.has_table][0].table
    assert pano.cell(3, 1).text == "$33,925,038" and pano.cell(2, 1).text == "$21,310,695"
    assert pano.cell(3, 2).text == "6,119" and pano.cell(2, 0).text == "2025"
    canal = [sh for sh in p.slides[2].shapes if sh.has_table][0].table
    names = [canal.cell(r, 0).text for r in range(len(canal.rows)) if canal.cell(r, 1).text == " "]
    assert names == [g.name for g in res.tables["aetops.canal.yoy"].groups]       # sin el bloque de Telegram viejo


def test_no_excel_heatmap_leftovers_and_no_negative_zero(built):
    _, b = built
    p = Presentation(b.pptx)
    neg = [sh for sh in p.slides[6].shapes if sh.has_table][0].table
    fills = [c._tc.xpath("./a:tcPr/a:solidFill/a:srgbClr/@val") for r in list(neg.rows)[1:12] for c in list(r.cells)[2:]]
    assert not [f for f in fills if f]                                     # el mapa de calor viejo no sobrevive
    assert not [t for t in all_text(p) if t.strip() in ("-0%", "-$0")]


def test_narrative_is_quarterly_and_analytical(built):
    _, b = built
    n = {k: " ".join(p.plain for p in v if p.visible) for k, v in b.fill.narrative.items()}
    assert "En Q3 2026, la venta total AETOP llega a" in n["panorama"] and "vs Q3 2025" in n["panorama"]
    assert "volumen" in n["panorama"] and "La principal presión" not in n["panorama"] or "ticket" in n["panorama"]
    assert "LLAMADAS GOOGLE es el canal que más aporta" in n["canal_yoy"]
    assert "AE-A es la línea que más aporta" in n["linea_yoy"]
    assert "pedidos" not in n["canal_yoy"]                                  # pedidos por canal: no confiables
    data = Path(b.pptx).parent / "narrative.json"
    assert data.exists() and "interpretacion" in data.read_text(encoding="utf-8")


def test_manual_edits_are_verified_against_known_figures(tmp_path):
    res = run_aetops(XL[0], "trimestral", Q3)
    ok = build_aetops(res, Q3, Path(TPL[0]), tmp_path / "a", narrative={"conclusiones": ["La venta creció +59% vs Q3 2025."]})
    assert not [i for i in ok.qa.issues if i.id == "EDITED_TEXT_UNVERIFIED"]
    bad = build_aetops(res, Q3, Path(TPL[0]), tmp_path / "b", narrative={"conclusiones": ["La venta creció +99%."]})
    assert [i for i in bad.qa.issues if i.id == "EDITED_TEXT_UNVERIFIED"]
    assert bad.downloadable                       # una cifra dudosa en texto editado avisa pero no bloquea


def test_fewer_rows_than_the_template_still_renders_cleanly(tmp_path):
    x = build_base(tmp_path / "syn", quarterly=True)
    res = run_aetops(x, "trimestral", None)
    assert res.can_generate
    b = build_aetops(res, Q3, Path(TPL[0]), tmp_path / "out")
    assert b.downloadable, [(i.id, i.slide, i.message) for i in b.qa.issues if i.severity == "error"]
    p = Presentation(b.pptx)
    canal = [sh for sh in p.slides[2].shapes if sh.has_table][0].table
    assert len(canal.rows) == 2 + 4 * 2                                        # 2 canales: se eliminaron bloques y separador
