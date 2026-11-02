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
