"""Fase 5 · T-12: QA VISUAL con render real (`backend/app/qa/visual.py`, `tools/visual_qa.py`; spec §7.B; AC-16).

CONDICIONAL: requiere `soffice` y `pdftoppm`. Sin ellos se OMITE con el motivo («omitida (sin LibreOffice)»); nunca se da por aprobada sin ejecutarse.
`tests.yml` no instala LibreOffice, así que en CI esta prueba queda omitida; se ejecuta en el equipo local o en un workflow con LibreOffice y datos SINTÉTICOS.
Deck limpio sintético (0 falsos positivos) y defectos inyectados: texto superpuesto, contraste bajo, diapositiva en blanco, texto fuera de la página,
título desalineado y gráfica vacía. Se valida además que el informe y el visor existan y que el visor escape el texto.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches, Pt

from backend.app.qa import visual
from tests.unit.test_qa_pptx_export import _texto, deck_limpio

ROOT = Path(__file__).resolve().parents[2]
OK, MOTIVO = visual.disponible()
pytestmark = pytest.mark.skipif(not OK, reason=f"OMITIDA (no ejecutada): omitida ({MOTIVO})")


def correr(pptx: Path, tmp_path: Path, **kw) -> dict:
    return visual.revisar(pptx, tmp_path / "salida", **kw)


def ids(inf) -> set[str]:
    return {i["id"] for i in inf["issues"]}


@pytest.fixture(scope="module")
def limpio(tmp_path_factory):
    return deck_limpio(tmp_path_factory.mktemp("v") / "limpio.pptx")


# --------------------------------------------------------------------------------------------- 0 falsos positivos
def test_deck_limpio_aprobado_sin_hallazgos_y_con_png_por_diapositiva(limpio, tmp_path):
    inf = correr(limpio, tmp_path)
    assert inf["estado"] == "aprobada" and inf["issues"] == [] and len(inf["pngs"]) == inf["diapositivas"] == 2
    assert all((tmp_path / "salida" / "png" / n).stat().st_size > 1000 for n in inf["pngs"])
    assert (tmp_path / "salida" / "informe.json").exists() and (tmp_path / "salida" / "informe.html").exists()
    assert "no PowerPoint" in inf["etiqueta"] and "no sustituye la revisión humana" in inf["etiqueta"]
    assert not (tmp_path / "salida" / "_analisis").exists()                                  # no deja los PNG de análisis


# --------------------------------------------------------------------------------------------- defectos inyectados
def test_texto_superpuesto_se_detecta(limpio, tmp_path):
    prs = Presentation(limpio)
    _texto(prs.slides[0], 0.5, 4.0, 9, 0.6, "Texto uno que ocupa este lugar completo del lienzo", 20)
    _texto(prs.slides[0], 0.5, 4.0, 9, 0.6, "Texto dos que lo cubre por completo encima", 20)
    prs.save(tmp_path / "x.pptx")
    inf = correr(tmp_path / "x.pptx", tmp_path)
    assert "TEXT_COLLISION" in ids(inf) and inf["estado"] == "rechazada"


def test_contraste_bajo_se_detecta(limpio, tmp_path):
    prs = Presentation(limpio)
    tb = _texto(prs.slides[0], 0.5, 4.2, 9, 0.8, "Texto casi invisible sobre fondo blanco", 24)
    tb.text_frame.paragraphs[0].runs[0].font.color.rgb = RGBColor(0xEE, 0xEE, 0xEE)
    prs.save(tmp_path / "x.pptx")
    assert "VISUAL_CONTRASTE_BAJO" in ids(correr(tmp_path / "x.pptx", tmp_path))


def test_texto_claro_sobre_fondo_oscuro_no_es_falso_positivo(limpio, tmp_path):
    prs = Presentation(limpio)
    caja = prs.slides[0].shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.5), Inches(4.2), Inches(9), Inches(0.8))
    caja.fill.solid()
    caja.fill.fore_color.rgb = RGBColor(0x00, 0x70, 0xC0)
    caja.text_frame.text = "Encabezado blanco sobre azul"
    run = caja.text_frame.paragraphs[0].runs[0]
    run.font.size, run.font.color.rgb = Pt(20), RGBColor(0xFF, 0xFF, 0xFF)
    prs.save(tmp_path / "x.pptx")
    assert "VISUAL_CONTRASTE_BAJO" not in ids(correr(tmp_path / "x.pptx", tmp_path))


def test_diapositiva_en_blanco_con_contenido_declarado(limpio, tmp_path):
    prs = Presentation(limpio)
    tapa = prs.slides[0].shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
    tapa.fill.solid()
    tapa.fill.fore_color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    tapa.line.fill.background()
    prs.save(tmp_path / "x.pptx")
    inf = correr(tmp_path / "x.pptx", tmp_path)
    assert any(i["id"] == "VISUAL_DIAPOSITIVA_EN_BLANCO" and i["slide"] == 1 for i in inf["issues"])


def test_texto_fuera_de_la_pagina_se_detecta(limpio, tmp_path):
    prs = Presentation(limpio)
    _texto(prs.slides[0], 9.2, 4.5, 3, 0.5, "Texto que se sale por la derecha de la diapositiva", 18)
    prs.save(tmp_path / "x.pptx")
    inf = correr(tmp_path / "x.pptx", tmp_path)
    # LibreOffice recorta lo que sale de la página: el texto falta en el PDF (PDF_TEXT_MISMATCH) o aparece fuera (TEXT_OUT_OF_PAGE). Ambos son detección.
    assert ids(inf) & {"TEXT_OUT_OF_PAGE", "PDF_TEXT_MISMATCH"} and inf["estado"] == "rechazada"


def test_titulo_desalineado_se_detecta(tmp_path):
    prs = Presentation()
    for i in range(4):
        s = prs.slides.add_slide(prs.slide_layouts[5])
        s.shapes.title.text = f"Título {i + 1}"
        _texto(s, 0.5, 3.0, 9, 1, f"Contenido de la diapositiva {i + 1}", 16)
    prs.slides[2].shapes.title.top = prs.slides[2].shapes.title.top + Inches(1.0)
    prs.save(tmp_path / "x.pptx")
    inf = correr(tmp_path / "x.pptx", tmp_path)
    assert any(i["id"] == "VISUAL_INCONSISTENCIA_TITULO" and i["slide"] == 3 for i in inf["issues"])
    prs2 = Presentation()
    for i in range(4):
        s = prs2.slides.add_slide(prs2.slide_layouts[5])
        s.shapes.title.text = f"Título {i + 1}"
        _texto(s, 0.5, 3.0, 9, 1, f"Contenido {i + 1}", 16)
    prs2.save(tmp_path / "y.pptx")
    assert "VISUAL_INCONSISTENCIA_TITULO" not in ids(correr(tmp_path / "y.pptx", tmp_path))   # títulos alineados: 0 falsos positivos


def test_grafica_vacia_se_renderiza_en_blanco(tmp_path):
    from pptx.chart.data import CategoryChartData
    from pptx.enum.chart import XL_CHART_TYPE
    prs = Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _texto(s, 0.5, 0.3, 9, 0.6, "Gráfica", 24)
    cd = CategoryChartData()
    cd.categories = ["A", "B"]
    cd.add_series("S", (0, 0))
    g = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(1), Inches(1.5), Inches(5), Inches(4), cd)
    g.chart.has_legend = False
    g.chart.has_title = False                                                                 # con título el render no queda en blanco: sería otra gráfica
    g.chart.category_axis.visible = False
    g.chart.value_axis.visible = False
    g.chart.value_axis.has_major_gridlines = False
    prs.save(tmp_path / "x.pptx")
    inf = correr(tmp_path / "x.pptx", tmp_path)
    assert any(i["id"] == "VISUAL_GRAFICA_EN_BLANCO" for i in inf["issues"]), inf["issues"]
    # y una gráfica con datos NO se marca (0 falsos positivos)
    prs2 = Presentation()
    s2 = prs2.slides.add_slide(prs2.slide_layouts[6])
    _texto(s2, 0.5, 0.3, 9, 0.6, "Gráfica con datos", 24)
    cd2 = CategoryChartData()
    cd2.categories = ["A", "B"]
    cd2.add_series("S", (5, 9))
    s2.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(1), Inches(1.5), Inches(5), Inches(4), cd2)
    prs2.save(tmp_path / "y.pptx")
    assert "VISUAL_GRAFICA_EN_BLANCO" not in {i["id"] for i in correr(tmp_path / "y.pptx", tmp_path)["issues"]}


# --------------------------------------------------------------------------------------------- informe, visor y herramienta
def test_visor_escapa_el_texto_de_los_hallazgos():
    inf = {"pptx": "<script>alert(1)</script>.pptx", "estado": "aprobada", "etiqueta": "<b>x</b>", "pngs": ["a.png"],
           "issues": [{"id": "X", "severity": "warn", "slide": 1, "message": "<img src=x onerror=alert(1)>"}]}
    h = visual.visor_html(inf)
    assert "<script>" not in h and "<img src=x" not in h and "&lt;script&gt;" in h


def test_herramienta_de_linea_de_comandos(limpio, tmp_path):
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "visual_qa.py"), str(limpio), "--out", str(tmp_path / "o")], capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["estado"] == "aprobada"
    assert subprocess.run([sys.executable, str(ROOT / "tools" / "visual_qa.py"), str(tmp_path / "no_existe.pptx"), "--out", str(tmp_path / "p")],
                          capture_output=True, text=True, cwd=ROOT).returncode == 1


def test_sin_libreoffice_el_resultado_es_omitida_y_nunca_aprobada(limpio, tmp_path, monkeypatch):
    monkeypatch.setattr(visual, "disponible", lambda: (False, "sin soffice"))
    inf = visual.revisar(limpio, tmp_path / "s")
    assert inf["estado"] == "omitida" and "omitida" in inf["motivo"] and inf["pngs"] == [] and inf["estado"] != "aprobada"


def test_un_archivo_no_renderizable_da_error_controlado(tmp_path):
    malo = tmp_path / "malo.pptx"
    malo.write_bytes(b"no es un pptx")
    inf = visual.revisar(malo, tmp_path / "s")
    assert inf["estado"] in ("error", "rechazada") and inf["estado"] != "aprobada"


# --------------------------------------------------------------------------------------------- decks reales de referencia (si hay plantillas)
ESCENARIOS = {"aetops_mensual_2026-09": "aetops-mensual", "glp1_mensual_2026-09": "glp1-mensual"}


@pytest.mark.parametrize("nombre", sorted(ESCENARIOS))
def test_decks_reales_de_referencia_aprobados_sin_hallazgos(nombre, tmp_path):
    """Libros de EJEMPLO sintéticos + plantillas locales (no versionadas): 0 hallazgos. Sin plantilla se omite con motivo."""
    tpl = ROOT / "templates" / ESCENARIOS[nombre] / "1" / "template.pptx"
    if not tpl.exists():
        pytest.skip("OMITIDA (no ejecutada): la plantilla no se versiona y no está disponible")
    sys.path.insert(0, str(ROOT))
    from tools.capture_baseline import _run
    from backend.app.build import build_aetops, build_glp1
    unit, period, _p, _t, res, _ = _run(nombre)
    b = (build_aetops if unit == "AETOPS" else build_glp1)(res, period, tpl, tmp_path / "deck", render=False)
    inf = visual.revisar(b.pptx, tmp_path / "v", tpl)
    assert inf["estado"] == "aprobada" and inf["issues"] == [], inf["issues"]
