"""Pruebas doradas contra los archivos reales de ejemplo (contienen datos comerciales,
por eso NO están en el repo). Se ejecutan solo si REPORT_FIXTURES_DIR apunta a una carpeta
que los contenga; en caso contrario se omiten (no se simula éxito)."""
import glob
import os
from decimal import Decimal

import pytest

from backend.app import format as fmt
from backend.app.pipeline import run_aetops_base

D = os.environ.get("REPORT_FIXTURES_DIR")
FILES = glob.glob(os.path.join(D, "*AETOPS_2026_Septiembre_listo_MoM.xlsx")) if D else []
pytestmark = pytest.mark.skipif(not FILES, reason="REPORT_FIXTURES_DIR sin archivos de ejemplo")


@pytest.fixture(scope="module")
def res():
    return run_aetops_base(FILES[0])


def q(v, places="0.01"):
    return v.v.quantize(Decimal(places))


def test_panorama_matches_published_deck(res):
    g = res.tables["aetops.panorama.yoy"].groups[0]
    c, p = g.current.values, g.previous.values
    assert c["monto"].v == 11560021 and p["monto"].v == 6942601
    assert q(c["size_b"]) == Decimal("1.89") and q(p["size_b"]) == Decimal("1.67")
    assert q(c["v_paciente"]) == Decimal("10312.24") and q(p["v_paciente"]) == Decimal("8889.37")
    assert q(c["ticket"], "1") == 8101 and q(p["ticket"], "1") == 7792
    # textos tal como se publican en la diapositiva 1 del PPTX (+67%, +63%, +44%, +60%)
    assert [fmt.fmt_pct(g.pct[k]) for k in ("monto", "piezas", "pacientes", "pedidos")] == \
        ["+67%", "+63%", "+44%", "+60%"]


def test_canal_and_linea_match_published_deck(res):
    canal = {g.name: g for g in res.tables["aetops.canal.yoy"].groups}
    assert fmt.fmt_pct(canal["LLAMADAS GOOGLE"].pct["monto"]) == "+175%"
    assert fmt.fmt_pct(canal["LLAMADAS GOOGLE"].current.values["share"], sign=False) == "38%"
    linea = {g.name: g for g in res.tables["aetops.linea.yoy"].groups}
    assert fmt.fmt_pct(linea["AE-A"].pct["monto"]) == "+67%"
    assert fmt.fmt_pct(linea["AE-A"].current.values["share"], sign=False) == "61%"
    assert linea["AE-A"].previous.values["ticket"].v.quantize(Decimal("1")) == 9233


def test_real_file_defects_are_detected(res):
    """El Excel 'Septiembre' recibido trae datos de Agosto y grupos con periodos distintos."""
    ids = {f.id for f in res.findings if f.severity == "block"}
    assert {"IDENTICAL_PERIODS", "PERIOD_LABELS_INCONSISTENT"} <= ids
    assert not res.can_generate


# ---------------------------------------------------------------- Fase 4b
from backend.app.models import Period  # noqa: E402
from backend.app.pipeline import run_aetops  # noqa: E402

Q3_FILES = glob.glob(os.path.join(D, "*AETOPS_2026_Trimestre_Q3.xlsx")) if D else []


@pytest.fixture(scope="module")
def full():
    return run_aetops(FILES[0], "mensual", Period("AETOPS", "mensual", 2026, 9))


def test_categorias_match_published_deck(full):
    cat = {g.name: g for g in full.tables["aetops.categoria.yoy"].groups}
    onc = cat["Oncología y Hematología"]
    assert onc.current.values["monto"].v == 3360439 and onc.previous.values["monto"].v == 2047653
    assert fmt.fmt_pct(onc.pct["monto"]) == "+64%"
    assert fmt.fmt_pct(onc.current.values["share"], sign=False) == "29%"
    ort = [g for n, g in cat.items() if n.startswith("Ortopedia")][0]
    assert fmt.fmt_pct(ort.pct["monto"]) == "+38%"


def test_productos_match_published_deck(full):
    top = full.products["aetops.productos.top"].rows[0]
    assert (top.actual.v, top.anterior.v, top.delta.v) == (1087846, 878673, 209173)   # Prolia
    assert full.products["aetops.productos.growth"].rows[0].delta.v == 339129          # Rim-Voq
    assert full.products["aetops.productos.decline"].rows[0].delta.v == -153096        # Pamorelin 22.5
    assert any(f.id == "FORMULA_MASKS_MISSING" for f in full.findings)               # Higlobin (#N/A)


def test_negados_match_published_deck(full):
    alta = {r.name: r for r in full.negados["aetops.negados.alta"].rows}
    assert alta["AE-A"].pedidos.v == 61 and alta["AE-A"].monto.v == 1146774
    assert fmt.fmt_pct(alta["AE-A"].share, sign=False) == "47%"
    total = full.negados["aetops.negados.producto"].total
    assert fmt.fmt_money(total, 0) == "$2,434,797" and fmt.fmt_num(total, 0)[:4] == "2,43"


def test_wrong_period_chosen_by_user_is_caught(full):
    assert any(f.id == "PERIOD_MISMATCH" and f.severity == "block" for f in full.findings)


@pytest.mark.skipif(not Q3_FILES, reason="sin Excel trimestral de ejemplo")
def test_quarterly_q3_real_file_loads_with_yoy_only():
    res = run_aetops(Q3_FILES[0], "trimestral", Period("AETOPS", "trimestral", 2026, 3))
    assert not any(k.endswith(".mom") for k in res.tables)
    assert res.tables["aetops.panorama.yoy"].groups[0].current.values["monto"].v == 33925038
    assert len(res.tables["aetops.categoria.yoy"].groups) == 13
    # el Excel Q3 trae dos totales de negados que se contradicen (productos 6.14 M vs líneas 1.66 M): no se publica
    blocks = [f for f in res.findings if f.severity == "block"]
    assert [f.id for f in blocks] == ["TOTALS_MISMATCH"] and "Negados" in blocks[0].message and not res.can_generate
