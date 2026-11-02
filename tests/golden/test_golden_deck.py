"""Fase 5a contra la plantilla y los archivos reales (datos/branding de la empresa: NO están en el repo).
Se activan con REPORT_FIXTURES_DIR; si no, se omiten (no se simula éxito)."""
import glob
import os
import shutil
from pathlib import Path

import pytest
from pptx import Presentation

from backend.app.build import ReportBlocked, build_aetops_mensual
from backend.app.deck import pptx_ops as ops
from backend.app.deck.aetops_mensual import fill_aetops_mensual
from backend.app.models import Period
from backend.app.pipeline import run_aetops
from backend.app.qa import checks
from backend.app.render import convert_to_pdf, pdf_to_pngs
from tests.fixtures import build_base

D = os.environ.get("REPORT_FIXTURES_DIR")
TPL = glob.glob(os.path.join(D, "*Resultados_AETOP_Agosto_2026.pptx")) if D else []
XL = glob.glob(os.path.join(D, "*AETOPS_2026_Septiembre_listo_MoM.xlsx")) if D else []
pytestmark = pytest.mark.skipif(not (TPL and XL and shutil.which("soffice")),
                                reason="faltan la plantilla/Excel reales o LibreOffice")
AUG = Period("AETOPS", "mensual", 2026, 8)


def tables(prs, n):
    return {sh.name: [[c.text for c in r.cells] for r in sh.table.rows]
            for sh in prs.slides[n - 1].shapes if sh.has_table}


@pytest.fixture(scope="module")
def filled():
    res = run_aetops(XL[0], "mensual", AUG)
    prs = Presentation(TPL[0])
    rep = fill_aetops_mensual(prs, res, AUG)
    return res, prs, rep


def test_original_template_passes_qa_baseline(tmp_path):
    """Calibración: el deck publicado, renderizado con la fuente sustituta, no debe dar errores."""
    pdf = convert_to_pdf(Path(TPL[0]), tmp_path)
    rep = checks.QAReport()
    checks.check_render(Path(TPL[0]), pdf, rep)
    checks.check_editable_and_static(Path(TPL[0]), Path(TPL[0]), rep)
    assert rep.passed, [(i.id, i.slide, i.message) for i in rep.issues]


def test_filled_tables_are_identical_to_the_published_deck(filled):
    """Mismos datos de origen -> las tablas salen idénticas a las del PPTX publicado (0 celdas distintas)."""
    _, prs, _ = filled
    orig = Presentation(TPL[0])
    for n, names in ((2, ["Tabla 2"]), (7, ["Tabla 2", "Tabla 7"]), (10, ["Tabla 7", "Tabla 2"])):
        a, b = tables(orig, n), tables(prs, n)
        for name in names:
            assert a[name] == b[name], f"diapositiva {n} {name}"
    # panorama YoY (filas 0-4) y línea YoY: solo difiere el formato '1216' vs '1,216' del original
    assert tables(orig, 1)["Tabla 3"][:5] == tables(prs, 1)["Tabla 3"][:5]
    d4 = [(i, j) for i, (ra, rb) in enumerate(zip(tables(orig, 4)["Tabla 8"], tables(prs, 4)["Tabla 8"]))
          for j, (x, y) in enumerate(zip(ra, rb)) if x != y]
    assert d4 == [(4, 2)]                                     # '1216' (sin separador) en el original


def test_new_products_are_shown_as_new_not_as_zero(filled):
    orig, (res, prs, _) = Presentation(TPL[0]), filled
    a, b = tables(orig, 6)["Tabla 3"], tables(prs, 6)["Tabla 3"]
    diff_rows = {i for i, (ra, rb) in enumerate(zip(a, b)) if ra != rb}
    assert diff_rows and all(a[i][5] == "$0" and b[i][5] == "" for i in diff_rows)   # solo productos sin venta previa
    assert all(b[i][6].startswith("$") and b[i][6] != "$0" for i in diff_rows)        # Delta = venta actual


def test_nothing_stale_survives_and_crossed_titles_are_reported(filled):
    _, prs, rep = filled
    assert rep.stale == []
    assert len(rep.titles_fixed) == 4
    assert [sh.text_frame.text for sh in prs.slides[1].shapes if sh.name == "CuadroTexto 11"] == ["Análisis de Canales YoY"]


def test_real_excel_cannot_be_published_but_renders_cleanly_for_review(tmp_path):
    res = run_aetops(XL[0], "mensual", AUG)
    with pytest.raises(ReportBlocked):
        build_aetops_mensual(res, AUG, Path(TPL[0]), tmp_path / "a")
    b = build_aetops_mensual(res, AUG, Path(TPL[0]), tmp_path / "b", allow_blockers=True)
    assert not b.downloadable
    errors = {i.id for i in b.qa.issues if i.severity == "error"}
    assert errors == {"GENERATED_WITH_BLOCKERS"}               # ningún error visual: solo el bloqueo deliberado


def test_end_to_end_clean_workbook_is_downloadable(tmp_path):
    per = Period("AETOPS", "mensual", 2026, 9)
    res = run_aetops(build_base(tmp_path / "syn"), "mensual", per)
    assert res.can_generate
    b = build_aetops_mensual(res, per, Path(TPL[0]), tmp_path / "out")
    assert b.downloadable, [(i.id, i.slide, i.message) for i in b.qa.issues if i.severity == "error"]
    assert b.pptx.exists() and b.pdf.exists() and len(b.pngs) == 13        # 11 + resumen + recomendaciones
    assert b.fill.stale == []
    p = Presentation(b.pptx)                                    # sigue siendo editable: tablas y textos reales
    count = lambda prs: sum(1 for s in prs.slides for sh in s.shapes if getattr(sh, "has_table", False) and sh.has_table)  # noqa: E731
    assert count(p) == count(Presentation(TPL[0])) == 13
    assert not any(sh.shape_type == 13 and sh.name.startswith(("Tabla", "Cuadro")) for s in p.slides for sh in s.shapes)
    assert b.manifest["qa_passed"] and len(b.manifest["pptx_sha256"]) == 64


def test_forced_overflow_on_the_real_template_is_caught(tmp_path):
    prs = Presentation(TPL[0])
    sh = [s for s in prs.slides[5].shapes if s.has_table][0]
    ops.resize_rows(sh.table, 1, len(sh.table.rows), 1, 45)     # 45 filas: no caben
    p = tmp_path / "overflow.pptx"
    prs.save(p)
    rep = checks.QAReport()
    checks.check_render(p, convert_to_pdf(p, tmp_path), rep)
    assert {"OVERFLOW_INTO_FOOTER", "TEXT_OUT_OF_PAGE"} & {i.id for i in rep.issues if i.severity == "error"}


def _text(rep, key):
    return " ".join(p.plain for p in rep.narrative[key] if p.visible)


def test_narrative_reaches_the_analysts_conclusions_with_real_data(filled):
    """Mismos datos que el reporte publicado de Agosto: el texto automático debe llegar a las mismas lecturas."""
    _, _, rep = filled
    assert rep.narrative_problems == []                                   # toda cifra con evidencia, sin causas
    canal, linea = _text(rep, "canal_yoy"), _text(rep, "linea_yoy")
    assert "LLAMADAS GOOGLE es el canal que más aporta al crecimiento" in canal and "+175%" in canal
    assert "ECOMMERCE crece +12%" in canal and "pierde participación (35% → 24%)" in canal      # como el original
    assert "WHATSAPP" in canal and "valor por paciente" in canal                              # +26% venta con pacientes -10%
    assert "pedidos" not in canal                                                              # pedidos por canal: no confiables
    assert "AE-A es la línea que más aporta" in linea and "base pequeña" in linea             # HYR
    assert "AE-B" in linea and "pierde participación" in linea
    pano = _text(rep, "panorama")
    assert "+67% vs 2025" in pano and "volumen" in pano
    assert "21% de la venta del periodo" in _text(rep, "negados")
    assert any(not p.visible and p.kind == "info_insuficiente" for p in rep.narrative["canal_yoy"])
