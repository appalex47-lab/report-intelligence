"""El machote sintético de GLP-1 debe ser coherente y reproducible (fixture para la Fase 4c)."""
from pathlib import Path

import openpyxl
import pytest

from tools.make_glp1_synthetic import build

DATA = Path(__file__).resolve().parents[2] / "data"


def col(ws, c, r0, r1):
    return [ws.cell(r, c).value for r in range(r0, r1 + 1)]


def load(name):
    return openpyxl.load_workbook(DATA / name, data_only=True)


@pytest.fixture(scope="module")
def clean():
    return load("GLP1_sintetico_limpio.xlsx")


def test_sheets_follow_the_real_operational_layout(clean):
    assert clean.sheetnames[:9] == [str(i) for i in range(1, 10)]
    assert clean["1"]["A1"].value == "Edad" and clean["4"]["A1"].value == "Región"
    assert clean["5"]["A1"].value == "Forma de Pago" and clean["9"]["A1"].value == "Categoría de dispositivo"
    assert "SINTÉTICOS" in clean["LEEME_SINTETICO"]["A1"].value


def test_visits_reconcile_across_sheets(clean):
    totals = [sum(col(clean["1"], 2, 2, 7)), sum(col(clean["1"], 2, 11, 12)),
              sum(col(clean["1"], 2, 16, 19)), sum(col(clean["9"], 2, 2, 12))]
    assert len(set(totals)) == 1 and totals[0] == 52000


def test_sales_reconcile_across_sheets(clean):
    reg = sum(col(clean["4"], 4, 2, 9))
    assert reg == sum(col(clean["5"], 4, 2, 6)) == sum(col(clean["5"], 4, 11, 12)) \
        == sum(col(clean["7"], 4, 2, 13)) == sum(col(clean["8"], 4, 2, 6))
    assert sum(col(clean["4"], 2, 2, 9)) == clean["5"]["E23"].value == 2600     # Compra del embudo = Σ pedidos


def test_ticket_share_and_delta_are_consistent(clean):
    ws = clean["4"]
    total = sum(col(ws, 4, 2, 9))
    for r in range(2, 10):
        assert ws.cell(r, 6).value == pytest.approx(ws.cell(r, 4).value / ws.cell(r, 2).value)
        assert ws.cell(r, 7).value == pytest.approx(ws.cell(r, 4).value / total, abs=5e-5)
    prev = {ws.cell(r, 11).value: ws.cell(r, 12).value for r in range(2, 10)}
    centro = ws["D2"].value
    assert ws["H2"].value == pytest.approx((centro - prev["CENTRO"]) / prev["CENTRO"], abs=1e-3)


def test_clean_variant_has_no_literal_formulas_or_zero_shares(clean):
    assert not [c for ws in clean for r in ws.iter_rows() for c in r
                if isinstance(c.value, str) and c.value.startswith("=")]
    assert all(v > 0 for v in col(clean["4"], 7, 2, 9))


def test_defect_variant_plants_the_documented_defects():
    d = load("GLP1_sintetico_con_defectos.xlsx")
    assert all(v == 0 for v in col(d["7"], 7, 2, 13))                       # Share = 0 pegado
    assert d["2"]["G1"].value == "& de rebote"                              # encabezado con typo
    assert all(c.value is None for c in d["4"][5])                          # fila en blanco en la tabla
    names = [r[0].value for r in d["7"].iter_rows(min_row=2) if r[0].value]
    assert "Total" in names and len(names) != len(set(names))               # subtotal + producto repetido
    assert min(col(d["6"], 4, 2, 7)) < 0                                    # monto negado negativo
    pay_now = {c.value for c in d["5"]["A"][1:6]}
    pay_prev = {c.value for c in d["5"]["L"][1:6]}
    assert "Tarjeta de Credito" in pay_now and "Tarjeta de Crédito" in pay_prev   # ortografía distinta


def test_generator_is_deterministic(tmp_path, clean):
    again = openpyxl.load_workbook(build(tmp_path / "x.xlsx"), data_only=True)
    for name in clean.sheetnames:
        a = [[c.value for c in r] for r in clean[name].iter_rows()]
        b = [[c.value for c in r] for r in again[name].iter_rows()]
        assert a == b, name
