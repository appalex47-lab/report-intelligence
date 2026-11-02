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


def repaired_q3(dst: Path) -> Path:
    """Copia del Q3 real con la tabla de negados por línea alineada a la de productos (Σ por 'Alta'):
    simula que el dueño del Excel corrigió la contradicción detectada."""
    import openpyxl
    wb = openpyxl.load_workbook(XL[0], data_only=True)
    ws = wb["Negados"]
    agg: dict[str, list] = {}
    for r in range(3, ws.max_row + 1):
        name, alta = ws.cell(r, 1).value, ws.cell(r, 2).value
        if name is None or alta is None:
            continue
        a = agg.setdefault(str(alta), [0, 0, 0.0])
        a[0] += ws.cell(r, 3).value or 0
        a[1] += ws.cell(r, 4).value or 0
        a[2] += ws.cell(r, 5).value or 0
    total = sum(v[2] for v in agg.values())
    for r in range(3, 3 + 8):                                            # bloque O:S
        for c in range(15, 20):
            ws.cell(r, c).value = None
    for i, (alta, (ped, cant, monto)) in enumerate(sorted(agg.items(), key=lambda kv: -kv[1][2])):
        for c, v in zip(range(15, 20), (alta, ped, cant, monto, monto / total)):
            ws.cell(3 + i, c).value = v
    wb.save(dst)
    return dst


@pytest.fixture(scope="module")
def q3_fixed(tmp_path_factory):
    return repaired_q3(tmp_path_factory.mktemp("fix") / "q3_corregido.xlsx")


@pytest.fixture(scope="module")
def built(tmp_path_factory, q3_fixed):
    res = run_aetops(q3_fixed, "trimestral", Q3)
    assert res.can_generate, [(f.id, f.message) for f in res.findings if f.severity == "block"]
    return res, build_aetops(res, Q3, Path(TPL[0]), tmp_path_factory.mktemp("q3"))


def test_real_q3_excel_is_blocked_because_negados_totals_contradict():
    res = run_aetops(XL[0], "trimestral", Q3)
    blocks = [f for f in res.findings if f.severity == "block"]
    assert [f.id for f in blocks] == ["TOTALS_MISMATCH"] and "Negados" in blocks[0].message
    with pytest.raises(Exception) as e:
        build_aetops(res, Q3, Path(TPL[0]), Path("/tmp/no_se_genera"))
    assert "TOTALS_MISMATCH" in str(e.value)


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
    assert len(b.pngs) == 10 and b.pdf.exists() and b.fill.stale == [] and b.fill.narrative_problems == []


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
    pano = [sh for sh in p.slides[1].shapes if sh.has_table][0].table
    assert pano.cell(3, 1).text == "$33,925,038" and pano.cell(2, 1).text == "$21,310,695"
    assert pano.cell(3, 2).text == "6,119" and pano.cell(2, 0).text == "2025"
    canal = [sh for sh in p.slides[3].shapes if sh.has_table][0].table
    names = [canal.cell(r, 0).text for r in range(len(canal.rows)) if canal.cell(r, 1).text == " "]
    assert names == [g.name for g in res.tables["aetops.canal.yoy"].groups]       # sin el bloque de Telegram viejo


def test_no_excel_heatmap_leftovers_and_no_negative_zero(built):
    _, b = built
    p = Presentation(b.pptx)
    neg = [sh for sh in p.slides[7].shapes if sh.has_table][0].table
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


def test_manual_edits_are_verified_against_known_figures(tmp_path, q3_fixed):
    res = run_aetops(q3_fixed, "trimestral", Q3)
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
    canal = [sh for sh in p.slides[3].shapes if sh.has_table][0].table
    assert len(canal.rows) == 2 + 4 * 2                                        # 2 canales: se eliminaron bloques y separador


def test_executive_summary_first_and_recommendations_last(built):
    res, b = built
    p = Presentation(b.pptx)
    assert len(p.slides) == 10
    first = " ".join(sh.text_frame.text for sh in p.slides[0].shapes if sh.has_text_frame)
    last = " ".join(sh.text_frame.text for sh in p.slides[9].shapes if sh.has_text_frame)
    assert "Resumen Ejecutivo" in first and "Dónde estamos" in first and "Descubrimientos del periodo" in first
    assert "Qué hacer" in first and "[ALTA]" in first
    assert "Recomendaciones" in last and "Escenario ilustrativo" in last and "Seguimiento:" in last
    assert "Conclusiones Clave" in " ".join(sh.text_frame.text for sh in p.slides[8].shapes if sh.has_text_frame)


def test_recommendations_are_typed_justified_and_verified(built):
    _, b = built
    recs = [p for p in b.fill.narrative["recomendaciones"]]
    assert recs and all(p.kind == "recomendacion" and p.basis for p in recs)
    assert [p.plain.split("]")[0] for p in recs][0].endswith("ALTA")                 # ordenadas por prioridad
    assert not b.fill.narrative_problems
    negado = next(p for p in recs if "abasto" in p.plain)
    assert "sin stock" in negado.plain and "ilustrativo" in negado.plain and "no pronóstico" in negado.basis


def test_added_slides_keep_static_elements_and_pass_qa(built):
    _, b = built
    assert b.downloadable and not [i for i in b.qa.issues if i.id in ("STATIC_REGION_CHANGED", "PICTURES_CHANGED")]


# ----------------------------------------------------------------------------- contexto e historial
def test_context_goes_to_the_summary_marked_and_unverified(tmp_path, q3_fixed):
    res = run_aetops(q3_fixed, "trimestral", Q3)
    ctx = "Incidencia de abasto en Pamorelin del 12 al 20 de septiembre (por falta de stock en el proveedor)."
    b = build_aetops(res, Q3, Path(TPL[0]), tmp_path / "o", context=[ctx], sources=[q3_fixed])
    first = " ".join(sh.text_frame.text for sh in Presentation(b.pptx).slides[0].shapes if sh.has_text_frame)
    assert "Contexto aportado por el equipo" in first and "Pamorelin" in first
    assert b.downloadable and any(i.id == "CONTEXT_UNVERIFIED" for i in b.qa.issues)
    assert not b.fill.narrative_problems                                   # el contexto no pasa por el verificador de cifras/causas
    kinds = {p.kind for p in b.fill.narrative["resumen_ejecutivo"]}
    assert "contexto" in kinds


def test_history_records_every_generation_as_a_new_version_and_writes_trends(tmp_path, q3_fixed):
    import sqlite3
    db = tmp_path / "hist" / "historial.sqlite"
    res = run_aetops(q3_fixed, "trimestral", Q3)
    b1 = build_aetops(res, Q3, Path(TPL[0]), tmp_path / "a", history_db=db, sources=[q3_fixed], context=["nota"])
    b2 = build_aetops(res, Q3, Path(TPL[0]), tmp_path / "b", history_db=db, sources=[q3_fixed])
    assert b1.manifest["historial"]["version"] == 1 and b2.manifest["historial"]["version"] == 2
    con = sqlite3.connect(db)
    assert con.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 2         # la v1 sigue ahí
    assert con.execute("SELECT context FROM runs WHERE version=1").fetchone()[0] == '["nota"]'
    assert con.execute("SELECT pptx_sha FROM runs WHERE version=1").fetchone()[0] == b1.manifest["pptx_sha256"]
    with pytest.raises(sqlite3.DatabaseError):
        con.execute("DELETE FROM runs")
    import json
    t = json.loads((tmp_path / "b" / "trends.json").read_text(encoding="utf-8"))
    by = {x["metrica"]: x for x in t}
    # con un solo reporte el historial trae 2 puntos (Q3 2025 y Q3 2026, ambos ya en el archivo)
    assert by["monto"]["tendencia"] == "insuficiente" and len(by["monto"]["puntos"]) == 2
    assert {p["periodo"] for p in by["monto"]["puntos"]} == {"Q3 2025", "Q3 2026"}
