"""GLP-1 desde datos crudos: bloques equivalentes a los del libro operativo, verificados contra fuerza bruta."""
import importlib.util
from decimal import Decimal
from pathlib import Path

import openpyxl
import pytest

from backend.app.models import Period
from backend.app.pipeline import run_glp1_raw

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("mg", ROOT / "tools/make_raw_glp1_synthetic.py")
mg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mg)
P9, Q3 = Period("GLP1", "mensual", 2026, 9), Period("GLP1", "trimestral", 2026, 3)


@pytest.fixture(scope="module")
def xl(tmp_path_factory):
    return mg.build(tmp_path_factory.mktemp("g") / "g.xlsx")


def test_blocks_present_and_no_blockers(xl):
    r = run_glp1_raw(xl, P9)
    assert r.can_generate, r.findings
    for b in ("region", "pago", "entrega", "productos", "programas", "edad", "sexo", "dispositivo", "fuentes", "trafico_estado",
              "producto_sexo", "edad_producto:mounjaro", "negados"):
        assert b in r.blocks, b
    assert [x.key for x in r.funnel.rows] == ["ver producto", "agregar a carrito", "iniciar compra", "compra", "carritos abandonados"]
    assert r.funnel.rows[0].values["tasa_calc"].v == 1


def test_region_money_matches_brute_force_and_deltas(xl):
    r = run_glp1_raw(xl, P9)
    wb = openpyxl.load_workbook(xl, data_only=True)
    tot, peds = {}, {}
    prev = {}
    for row in wb["ventas"].iter_rows(min_row=2, values_only=True):
        d = row[0]
        reg = row[7]
        if (d.year, d.month) == (2026, 9):
            tot[reg] = tot.get(reg, Decimal(0)) + Decimal(str(row[9]))
            peds.setdefault(reg, set()).add(row[1])
        if (d.year, d.month) == (2026, 8):
            prev[reg] = prev.get(reg, Decimal(0)) + Decimal(str(row[9]))
    blk = {x.key: x for x in r.blocks["region"].rows}
    for reg, m in tot.items():
        x = blk[reg]
        assert x.values["monto"].v == m and x.values["pedidos"].v == len(peds[reg])
        assert x.values["ticket"].v == m / len(peds[reg])                      # Ticket = monto ÷ pedidos
        assert x.delta.v == (m - prev[reg]) / prev[reg] and x.delta_yoy.v is not None   # %Δ MoM y YoY
    assert abs(sum(x.share.v for x in blk.values()) - 1) < Decimal("0.0001")


def test_traffic_blocks_and_rates(xl):
    r = run_glp1_raw(xl, P9)
    ed = r.blocks["edad"].rows
    assert [x.key for x in ed] == ["18-24", "25-34", "35-44", "45-54", "55+"]
    assert all(0 < x.values["rebote"].v < 1 and x.values["tiempo"].v > 0 for x in ed)
    ps = r.blocks["producto_sexo"].rows
    assert {x.dim2 for x in ps} == {"Femenino", "Masculino"} and {x.key for x in ps} == set(mg.PRODUCTOS)
    assert all(x.delta.v is not None for x in r.blocks["dispositivo"].rows)


def test_quarterly_compares_previous_quarter_and_prior_year(xl):
    r = run_glp1_raw(xl, Q3)
    x = r.blocks["pago"].rows[0]
    assert x.engine_delta.v is not None and x.delta_yoy.v is not None
    assert r.can_generate


def test_missing_windows_warn_not_block(tmp_path):
    r = run_glp1_raw(mg.build(tmp_path / "s.xlsx", n_months=2), P9)
    ids = {f.id for f in r.findings}
    assert "RAW_WINDOW_MISSING" in ids and r.can_generate
    assert r.blocks["region"].rows[0].delta_yoy.v is None


def test_missing_columns_block(tmp_path):
    wb = openpyxl.Workbook()
    wb.active.title = "ventas"
    wb.active.append(["fecha_pedido"])
    p = tmp_path / "m.xlsx"
    wb.save(p)
    ids = {f.id for f in run_glp1_raw(p, P9).findings}
    assert {"RAW_COLUMN_MISSING", "RAW_TABLE_MISSING"} <= ids
