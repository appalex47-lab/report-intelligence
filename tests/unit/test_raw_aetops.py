"""Capa de agregación AETOPS desde datos crudos: el resultado debe coincidir con un cálculo independiente (fuerza bruta)."""
import datetime as dt
import importlib.util
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

import openpyxl
import pytest

from backend.app.models import Period
from backend.app.pipeline import run_aetops_raw
from backend.app.raw.aetops import is_raw_workbook

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("mrs", ROOT / "tools/make_raw_synthetic.py")
mrs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mrs)

P9 = Period("AETOPS", "mensual", 2026, 9)
Q3 = Period("AETOPS", "trimestral", 2026, 3)


@pytest.fixture(scope="module")
def xl(tmp_path_factory):
    return mrs.build(tmp_path_factory.mktemp("raw") / "crudo.xlsx")


def brute(xl, months, year, key):
    wb = openpyxl.load_workbook(xl, data_only=True)
    cat = {r[0]: r for r in wb["catalogo"].iter_rows(min_row=2, values_only=True)}
    m = ped = pac = Decimal(0)
    P, O, S = set(), set(), set()
    pieces = Decimal(0)
    for r in wb["ventas"].iter_rows(min_row=2, values_only=True):
        d = r[0]
        if not isinstance(d, (dt.date, dt.datetime)) or d.year != year or d.month not in months:
            continue
        if key(cat[r[4]], r) is False:
            continue
        m += Decimal(str(r[9]))
        pieces += Decimal(str(r[8]))
        P.add(r[2]); O.add(r[1]); S.add(r[4])
    return m, pieces, len(P), len(O), len(S)


def test_detects_raw_workbook(xl):
    assert is_raw_workbook(xl)


def test_clean_synthetic_has_no_findings_and_totals_match_brute_force(xl):
    res = run_aetops_raw(xl, P9)
    assert [f for f in res.findings if f.severity == "block"] == [], res.findings
    tot = lambda comp: res.tables[f"aetops.panorama.{comp}"].groups[0]            # noqa: E731
    for comp, (yr, months) in {"yoy": (2025, {9}), "mom": (2026, {8})}.items():
        m, pcs, pac, ped, sk = brute(xl, months, yr, lambda c, r: True)
        v = tot(comp).previous.values
        assert (v["monto"].v, v["piezas"].v, v["pacientes"].v, v["pedidos"].v, v["productos"].v) == (m, pcs, pac, ped, sk)
    m, pcs, pac, ped, sk = brute(xl, {9}, 2026, lambda c, r: True)
    cur = tot("yoy").current.values
    assert cur["monto"].v == m and cur["pacientes"].v == pac and cur["ticket"].v == m / ped


def test_group_metrics_and_distinct_patients_do_not_sum(xl):
    res = run_aetops_raw(xl, P9)
    lin = {g.name: g for g in res.tables["aetops.linea.yoy"].groups}
    assert list(lin)[:1] == ["AE-A"]
    for name, g in lin.items():
        m, _p, pac, ped, _s = brute(xl, {9}, 2026, lambda c, r, n=name: c[2] == n or False)
        assert g.current.values["monto"].v == m and g.current.values["pacientes"].v == pac
    assert sum(g.current.values["monto"].v for g in lin.values()) == res.tables["aetops.panorama.yoy"].groups[0].current.values["monto"].v
    assert sum(g.current.values["pacientes"].v for g in lin.values()) >= res.tables["aetops.panorama.yoy"].groups[0].current.values["pacientes"].v
    shares = sum(g.current.values["share"].v for g in lin.values())
    assert abs(shares - 1) < Decimal("0.0001")


def test_products_and_negados(xl):
    res = run_aetops_raw(xl, P9)
    top = res.products["aetops.productos.top"].rows
    assert len(top) == 20 and [r.actual.v for r in top] == sorted((r.actual.v for r in top), reverse=True)
    g, d = res.products["aetops.productos.growth"].rows, res.products["aetops.productos.decline"].rows
    assert all(r.delta.v > 0 for r in g) and all(r.delta.v < 0 for r in d)
    assert [r.delta.v for r in g] == sorted((r.delta.v for r in g), reverse=True)
    neg, alta = res.negados["aetops.negados.producto"], res.negados["aetops.negados.alta"]
    assert neg.label == "Septiembre" and neg.total.v == alta.total.v


def test_quarterly_is_yoy_only(xl):
    res = run_aetops_raw(xl, Q3)
    assert not any(k.endswith(".mom") for k in res.tables)
    m, *_ = brute(xl, {7, 8, 9}, 2026, lambda c, r: True)
    assert res.tables["aetops.panorama.yoy"].groups[0].current.values["monto"].v == m
    assert res.negados["aetops.negados.producto"].label == "Q3 2026"
    assert [f for f in res.findings if f.severity == "block"] == []


def test_defects_are_blocked_or_warned(tmp_path):
    f = mrs.build(tmp_path / "d.xlsx", defects=True)
    res = run_aetops_raw(f, P9)
    ids = {x.id for x in res.findings}
    assert {"RAW_SKU_NOT_IN_CATALOG", "RAW_DATE_UNREADABLE"} <= ids and not res.can_generate


def test_missing_prior_window_blocks(tmp_path):
    f = mrs.build(tmp_path / "s.xlsx", n_months=3)
    ids = {x.id for x in run_aetops_raw(f, P9).findings}
    assert "RAW_WINDOW_MISSING" in ids


def test_missing_columns_and_tables(tmp_path):
    wb = openpyxl.Workbook()
    wb.active.title = "ventas"
    wb.active.append(["fecha_pedido", "sku"])
    p = tmp_path / "m.xlsx"
    wb.save(p)
    ids = {x.id for x in run_aetops_raw(p, P9).findings}
    assert {"RAW_COLUMN_MISSING", "RAW_TABLE_MISSING"} <= ids
