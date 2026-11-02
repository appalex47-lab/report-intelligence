"""Dorados contra los libros reales de GLP-1 (datos comerciales: NO están en el repo).
Se activan con REPORT_FIXTURES_DIR; si no, se omiten."""
import glob
import os
from decimal import Decimal

import pytest

from backend.app import format as fmt
from backend.app.models import Period
from backend.app.pipeline import run_glp1

D = os.environ.get("REPORT_FIXTURES_DIR")
SEPT = glob.glob(os.path.join(D, "*GLP1_2026_Septiembre_MoM.xlsx")) if D else []
Q3 = glob.glob(os.path.join(D, "*GLP1_2026_Trimestre_Q3.xlsx")) if D else []
pytestmark = pytest.mark.skipif(not SEPT, reason="REPORT_FIXTURES_DIR sin libros de ejemplo de GLP-1")


@pytest.fixture(scope="module")
def res():
    return run_glp1(SEPT[0], "mensual", Period("GLP1", "mensual", 2026, 9))


def test_real_blocks_are_found_without_unmapped_columns(res):
    assert "COLUMN_UNMAPPED" not in {f.id for f in res.findings}
    assert {"edad", "sexo", "dispositivo", "producto_sexo", "region", "pago", "entrega", "negados",
            "productos", "programas", "fuentes"} <= set(res.blocks)
    assert len(res.blocks["region"].rows) == 7 and len(res.blocks["trafico_estado"].rows) == 10


def test_product_row_matches_published_deck(res):
    p = res.blocks["productos"].rows[0]
    assert (p.values["pedidos"].v, p.values["piezas"].v, p.values["monto"].v) == (533, 581, 2694543)
    assert fmt.fmt_pct(p.delta, 2) == "-10.57%" and p.delta_src == "pasted"


def test_funnel_has_five_stages_with_real_typo_accepted(res):
    assert [r.key for r in res.funnel.rows][-1] == "Carritos abandonados"
    assert res.funnel.rows[3].values["conteo"].v == 3912
    assert any(f.id == "HEADER_TYPO_ACCEPTED" and "embudo" in f.message for f in res.findings)


def test_real_workbook_defects_are_reported(res):
    got = {f.id for f in res.findings}
    assert {"SHARE_ZERO", "TICKET_FORMULA_UNVERIFIED", "DELTA_METRIC_UNVERIFIED", "PERIOD_UNDECLARED",
            "BLANK_ROW_INSIDE"} <= got
    assert not res.can_generate                    # hueco real en el bloque anterior de fuentes de tráfico


@pytest.mark.skipif(not Q3, reason="sin libro trimestral")
def test_quarterly_real_workbook_loads():
    r = run_glp1(Q3[0], "trimestral", Period("GLP1", "trimestral", 2026, 3))
    assert "COLUMN_UNMAPPED" not in {f.id for f in r.findings}
    assert len(r.blocks["region"].rows) >= 7 and r.funnel is not None
