"""Tablas por grupos con más grupos que la plantilla (p. ej. una línea nueva en el catálogo): deben caber sobre el pie de página.

Caso real: un catálogo con una 5.ª línea (AE-D) hacía que la tabla «Línea MoM» creciera hasta invadir el pie (QA: OVERFLOW_ESTIMATED).
La corrección solo actúa si la tabla no cabe; si cabe, no cambia nada.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import openpyxl
import pytest
from pptx import Presentation
from pptx.util import Emu, Pt

from backend.app.deck import pptx_ops as ops
from backend.app.models import Period
from backend.app.qa.checks import estimate_table_height, row_content_floors, row_min_heights

ROOT = Path(__file__).resolve().parents[2]
TPL = ROOT / "templates" / "aetops-mensual" / "1" / "template.pptx"
LIBRO = ROOT / "data" / "ejemplos" / "AETOPS_crudo_ejemplo.xlsx"


def tabla(n_filas, alto_pt, top_pt=100, fs=11, relleno_fs=None):
    prs = Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[6])
    sh = s.shapes.add_table(n_filas, 3, Pt(10), Pt(top_pt), Pt(300), Pt(alto_pt * n_filas))
    for r in sh.table.rows:
        r.height = Pt(alto_pt)
    for i, r in enumerate(sh.table.rows):
        for j, c in enumerate(r.cells):
            c.text = " " if (relleno_fs and j > 0) else f"x{i}{j}"
            for p in c.text_frame.paragraphs:
                for run in p.runs:
                    run.font.size = Pt(relleno_fs if (relleno_fs and j > 0) else fs)
    return sh


def test_si_la_tabla_cabe_no_se_toca_nada():
    sh = tabla(10, 20)
    antes = [r.height for r in sh.table.rows]
    assert ops.compact_to_fit(sh, 400, row_content_floors(sh)) is None
    assert [r.height for r in sh.table.rows] == antes


def test_si_no_cabe_se_compacta_sin_bajar_del_minimo_de_cada_fila():
    sh = tabla(20, 30, top_pt=100)                              # 600 pt de alto frente a 440 disponibles (el mínimo real suma ≈ 432)
    floors = row_content_floors(sh)
    assert sum(floors) < 440
    res = ops.compact_to_fit(sh, 540, floors)
    assert res and res[0] == pytest.approx(600) and res[1] <= 440.5
    assert all(Emu(r.height).pt >= f - 0.2 for r, f in zip(sh.table.rows, floors))
    assert Emu(sh.top).pt + Emu(sh.height).pt <= 540.5                                  # el marco se sincroniza


def test_si_ni_compactando_al_minimo_cabe_las_filas_quedan_en_su_minimo():
    sh = tabla(40, 30, top_pt=100)
    floors = row_content_floors(sh)
    res = ops.compact_to_fit(sh, 300, floors)
    assert res and all(Emu(r.height).pt == pytest.approx(f, abs=0.2) for r, f in zip(sh.table.rows, floors))
    assert estimate_table_height(sh) + 100 > 300                                         # sigue sin caber: el QA lo seguirá señalando


def test_las_celdas_de_relleno_a_18pt_inflan_la_fila_y_se_reducen_sin_tocar_texto_visible():
    sh = tabla(6, 14, relleno_fs=18)
    antes = row_content_floors(sh)
    textos = [[c.text for c in r.cells] for r in sh.table.rows]
    ops.set_filler_font(sh.table, [0, 2, 4], range(1, 3), 11)
    despues = row_content_floors(sh)
    assert all(d < a for i, (a, d) in enumerate(zip(antes, despues)) if i in (0, 2, 4))
    assert all(a == d for i, (a, d) in enumerate(zip(antes, despues)) if i not in (0, 2, 4))
    assert textos == [[c.text for c in r.cells] for r in sh.table.rows]                  # ningún texto cambió


def test_los_minimos_reales_no_son_menores_que_la_estimacion_del_qa_para_filas_con_texto():
    sh = tabla(5, 20)
    for real, est in zip(row_content_floors(sh), row_min_heights(sh)):
        assert real >= est - 0.01


@pytest.fixture
def libro_con_linea_nueva(tmp_path):
    """El machote AETOPS con 3 SKU reasignados a una 5.ª línea «AE-D» (como en el catálogo real del usuario)."""
    dst = tmp_path / "con_AE-D.xlsx"
    shutil.copy(LIBRO, dst)
    wb = openpyxl.load_workbook(dst)
    cat = wb["catalogo"]
    cols = [c.value for c in cat[1]]
    il = cols.index("linea")
    cambiados = 0
    for row in cat.iter_rows(min_row=2):
        if cambiados < 6 and row[il].value == "AE-A":
            row[il].value = "AE-D"
            cambiados += 1
    wb.save(dst)
    return dst


@pytest.mark.skipif(not TPL.exists(), reason="plantilla real no disponible (no se versiona)")
def test_aetops_mensual_con_una_quinta_linea_pasa_el_qa_estructural(libro_con_linea_nueva):
    from backend.app.build import build_aetops
    from backend.app.pipeline import run_aetops_raw
    p = Period("AETOPS", "mensual", 2026, 9)
    res = run_aetops_raw(libro_con_linea_nueva, p)
    assert any(g.name == "AE-D" for g in res.tables["aetops.linea.mom"].groups)         # el escenario realmente tiene 5 líneas
    with tempfile.TemporaryDirectory() as td:
        b = build_aetops(res, p, TPL, Path(td), render=False)
        assert not [i for i in b.qa.issues if i.id == "OVERFLOW_ESTIMATED"], [i.message for i in b.qa.issues if i.severity != "info"]
        assert any("se compactó el alto de las filas" in n for n in b.fill.notes)
        prs = Presentation(b.pptx)
        pie = next(sh for sh in prs.slides[0].shapes if sh.is_placeholder and "pie" in sh.name.lower())
        for sl in prs.slides:
            for sh in sl.shapes:
                if getattr(sh, "has_table", False) and sh.has_table and sh.name in ("Tabla 2", "Tabla 8"):
                    assert Emu(sh.top).pt + Emu(sh.height).pt <= Emu(pie.top).pt + 1


@pytest.mark.skipif(not TPL.exists(), reason="plantilla real no disponible (no se versiona)")
def test_el_caso_normal_de_cuatro_lineas_no_se_compacta():
    from backend.app.build import build_aetops
    from backend.app.pipeline import run_aetops_raw
    p = Period("AETOPS", "mensual", 2026, 9)
    with tempfile.TemporaryDirectory() as td:
        b = build_aetops(run_aetops_raw(LIBRO, p), p, TPL, Path(td), render=False)
        assert not any("compactó" in n for n in b.fill.notes) and b.qa.passed


TPL_Q = ROOT / "templates" / "aetops-trimestral" / "1" / "template.pptx"


@pytest.mark.skipif(not TPL_Q.exists(), reason="plantilla real no disponible (no se versiona)")
def test_aetops_trimestral_con_quinta_linea_ya_no_la_omite(libro_con_linea_nueva):
    from backend.app.build import build_aetops
    from backend.app.pipeline import run_aetops_raw
    p = Period("AETOPS", "trimestral", 2026, 3)
    res = run_aetops_raw(libro_con_linea_nueva, p)
    nombres = [g.name for g in res.tables["aetops.linea.yoy"].groups]
    assert "AE-D" in nombres
    with tempfile.TemporaryDirectory() as td:
        b = build_aetops(res, p, TPL_Q, Path(td), render=False)
        assert not any("se omiten" in n and "AE-D" in n for n in b.fill.notes), b.fill.notes
        assert not [i for i in b.qa.issues if i.id == "OVERFLOW_ESTIMATED"]
        prs = Presentation(b.pptx)
        textos = " ".join(c.text for sh in prs.slides[2].shapes if getattr(sh, "has_table", False) and sh.has_table
                          for r in sh.table.rows for c in r.cells)
        assert "AE-D" in textos


@pytest.mark.skipif(not TPL_Q.exists(), reason="plantilla real no disponible (no se versiona)")
def test_trimestral_con_cuatro_lineas_no_cambia():
    from backend.app.build import build_aetops
    from backend.app.pipeline import run_aetops_raw
    p = Period("AETOPS", "trimestral", 2026, 3)
    with tempfile.TemporaryDirectory() as td:
        b = build_aetops(run_aetops_raw(LIBRO, p), p, TPL_Q, Path(td), render=False)
        assert not any("compactó" in n or "se omiten" in n for n in b.fill.notes)


def test_conclusiones_reproduce_el_patron_del_original_sin_vacios_entre_cifras():
    from backend.app.narrative.writer import Para, to_paragraphs_conclusiones
    mk = lambda t: Para(t, "hecho", 0, nums=set())          # noqa: E731
    out = to_paragraphs_conclusiones([mk("a"), mk("b"), mk("**Insights clave:**"), mk("i1"), mk("i2")])
    assert out == ["a", "b", "", "**Insights clave:**", "i1", "", "i2"]
    sin_enc = to_paragraphs_conclusiones([mk("a"), mk("b")])
    assert sin_enc == ["a", "", "b"]                          # sin encabezado: patrón general


@pytest.mark.skipif(not TPL.exists(), reason="plantilla real no disponible (no se versiona)")
def test_conclusiones_usa_el_patron_general_si_cabe_y_el_compacto_si_no():
    from backend.app.deck.aetops_mensual import FillReport, Filler, conclusiones_paragraphs
    from backend.app.narrative.writer import Para, to_paragraphs
    prs = Presentation(TPL)
    fl = Filler(prs, FillReport())
    sh = next(s for s in prs.slides[10].shapes if s.name == "CuadroTexto 12")
    mk = lambda t, n=1: Para((t + " ") * n, "hecho", 0, nums=set())          # noqa: E731
    corto = [mk("a"), mk("b"), mk("**Insights clave:**"), mk("c")]
    assert conclusiones_paragraphs(fl, sh, corto) == to_paragraphs(corto)           # cabe: idéntico al patrón de siempre
    largo = [mk("x", 30)] * 5 + [mk("**Insights clave:**")] + [mk("y", 60)] * 6
    out = conclusiones_paragraphs(fl, sh, largo)
    assert out != to_paragraphs(largo) and out[1] != "" and any("Conclusiones" in n for n in fl.rep.notes)


def test_conclusiones_editadas_sin_negritas_tambien_se_compactan():
    """Caso real (Chrome/Android): el texto reescrito con IA trae «Insights clave:» sin `**`; antes se ignoraba el encabezado y el
    patrón compacto no se aplicaba, así que la lámina seguía invadiendo el pie."""
    from backend.app.narrative.writer import Para, to_paragraphs_conclusiones
    mk = lambda t: Para(t, "hecho", 0, edited=True, nums=set())          # noqa: E731
    out = to_paragraphs_conclusiones([mk("a"), mk("b"), mk("Insights clave:"), mk("c"), mk("d")])
    assert out == ["a", "b", "", "Insights clave:", "c", "", "d"]
    largo = to_paragraphs_conclusiones([mk("Esta es una frase larga que termina en dos puntos y no es un encabezado de sección:"), mk("b")])
    assert largo == ["Esta es una frase larga que termina en dos puntos y no es un encabezado de sección:", "", "b"]
