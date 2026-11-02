from decimal import Decimal

from backend.app.models import Period
from backend.app.pipeline import run_aetops
from tests.fixtures import build_base

SEP = Period("AETOPS", "mensual", 2026, 9)
Q3 = Period("AETOPS", "trimestral", 2026, 3)


def ids(res, sev=None):
    return [f.id for f in res.findings if sev is None or f.severity == sev]


def blockers(res):
    return [(f.id, f.message) for f in res.findings if f.severity == "block"]


def test_clean_monthly_workbook_passes_with_expected_period(tmp_path):
    res = run_aetops(build_base(tmp_path / "ok"), "mensual", SEP)
    assert res.can_generate, blockers(res)


def test_categoria_groups_use_name_column_and_share_over_panorama_total(tmp_path):
    res = run_aetops(build_base(tmp_path / "ok"), "mensual", SEP)
    t = res.tables["aetops.categoria.yoy"]
    assert [g.name for g in t.groups] == ["CAT 1", "CAT 2"]
    g = t.groups[0]
    assert g.current.values["monto"].v == 900 and g.pct["monto"].v == Decimal("0.5")
    assert g.current.values["share"].v == Decimal("0.6")                    # 900/1500
    assert [g.name for g in res.tables["aetops.categoria.mom"].groups] == ["CAT 1", "CAT 2"]


def test_wrong_expected_period_blocks(tmp_path):
    res = run_aetops(build_base(tmp_path / "ok"), "mensual", Period("AETOPS", "mensual", 2026, 10))
    assert "PERIOD_MISMATCH" in ids(res, "block") and not res.can_generate
    res = run_aetops(build_base(tmp_path / "ok"), "mensual", Period("AETOPS", "mensual", 2027, 9))
    assert "PERIOD_MISMATCH" in ids(res, "block")                           # YoY 2026/2025 vs 2027


def test_products_delta_and_roles(tmp_path):
    res = run_aetops(build_base(tmp_path / "ok"), "mensual", SEP)
    assert set(res.products) == {"aetops.productos.top", "aetops.productos.growth", "aetops.productos.decline"}
    top = res.products["aetops.productos.top"].rows
    assert top[0].delta.v == 300 and top[0].delta.status == "ok"
    assert res.products["aetops.productos.decline"].rows[0].delta.v == -300


def test_new_product_is_flagged_not_zeroed(tmp_path):
    res = run_aetops(build_base(tmp_path / "ok"), "mensual", SEP)
    new = res.products["aetops.productos.top"].rows[2]
    assert new.anterior.status == "missing"                                 # '#N/A' ≠ 0
    assert new.delta.status == "new_item" and new.delta.v == 100            # monto completo + bandera
    assert new.pasted_delta.v == 0                                          # lo que enmascaraba el Excel
    assert "FORMULA_MASKS_MISSING" in ids(res, "info")


def test_product_sort_order_is_checked(tmp_path):
    assert "SORT_ORDER" not in ids(run_aetops(build_base(tmp_path / "a"), "mensual", SEP))
    assert "SORT_ORDER" in ids(run_aetops(build_base(tmp_path / "b", sort_broken=True), "mensual", SEP))


def test_negados_total_share_and_duplicate_block(tmp_path):
    res = run_aetops(build_base(tmp_path / "ok"), "mensual", SEP)
    prod, alta = res.negados["aetops.negados.producto"], res.negados["aetops.negados.alta"]
    assert prod.total.v == 1000 and alta.total.v == 1000
    assert [r.share.v for r in prod.rows] == [Decimal("0.6"), Decimal("0.3"), Decimal("0.1")]
    assert len(res.negados) == 2                       # el bloque duplicado no genera una tabla extra
    assert "TOTALS_MISMATCH" not in ids(res)


def test_negados_alta_total_mismatch_and_stale_label(tmp_path):
    res = run_aetops(build_base(tmp_path / "x", alta_off=True), "mensual", SEP)
    assert any(f.id == "TOTALS_MISMATCH" and "Negados" in f.message for f in res.findings)
    res = run_aetops(build_base(tmp_path / "y", negados_label="Julio"), "mensual", SEP)
    assert any(f.id == "PERIOD_MISMATCH" and "Negados" in f.message for f in res.findings)


def test_quarterly_profile_requires_only_yoy(tmp_path):
    p = build_base(tmp_path / "q", quarterly=True)
    res = run_aetops(p, "trimestral", Q3)
    assert "MISSING_COMPARISON" not in ids(res)
    assert not any(k.endswith(".mom") for k in res.tables)
    # el negados está rotulado 'Septiembre', no 'Q3' -> el motor lo señala
    assert any(f.id == "PERIOD_MISMATCH" and "Negados" in f.message for f in res.findings)


def test_monthly_profile_rejects_yoy_only_workbook(tmp_path):
    res = run_aetops(build_base(tmp_path / "q", quarterly=True), "mensual", SEP)
    missing = [f for f in res.findings if f.id == "MISSING_COMPARISON"]
    assert missing and all(f.severity == "block" for f in missing) and not res.can_generate
