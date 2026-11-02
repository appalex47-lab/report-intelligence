from decimal import Decimal

from backend.app.calc import indicators as ind


def V(x):
    return ind.make(x)


def test_to_dec_handles_junk():
    assert ind.to_dec(None) is None
    assert ind.to_dec("") is None
    assert ind.to_dec("abc") is None
    assert ind.to_dec(True) is None
    assert ind.to_dec("$1,234.5") == Decimal("1234.5")
    assert ind.to_dec(0.1) == Decimal("0.1")          # sin ruido binario


def test_missing_is_not_zero():
    assert V(None).status == "missing" and V(None).v is None
    assert V(0).status == "zero" and V(0).v == 0


def test_ratio_divide_by_zero_or_missing_is_missing_not_zero():
    assert ind.ratio(V(10), V(0), "x").status == "missing"
    assert ind.ratio(V(10), V(None), "x").status == "missing"
    assert ind.ratio(V(None), V(5), "x").status == "missing"
    assert ind.ratio(V(10), V(4), "x").v == Decimal("2.5")


def test_pct_change_base_zero_and_missing():
    assert ind.pct_change(V(10), V(0), "x").status == "missing"
    assert ind.pct_change(V(10), V(None), "x").status == "missing"
    assert ind.pct_change(V(150), V(100), "x").v == Decimal("0.5")
    assert ind.pct_change(V(50), V(100), "x").v == Decimal("-0.5")       # negativos se conservan


def test_delta_new_item_keeps_full_amount_with_flag():
    d = ind.delta_abs(V(246500), V(None), "x")
    assert d.v == Decimal("246500") and d.status == "new_item"
    assert ind.delta_abs(V(100), V(40), "x").v == 60


def test_no_float_rounding_inside_engine():
    assert ind.pct_change(V("0.3"), V("0.1"), "x").v == Decimal("2")     # float daría 1.9999…
