from decimal import Decimal

from backend.app import format as fmt
from backend.app.calc import indicators as ind


def V(x):
    return ind.make(x)


def test_percent_rounds_half_up_like_excel_and_decks():
    assert fmt.fmt_pct(V("0.625")) == "+63%"          # round() de Python daría 62
    assert fmt.fmt_pct(V("0.005")) == "+1%"
    assert fmt.fmt_pct(V("-0.625")) == "-63%"
    assert fmt.fmt_pct(V("0.1057"), decimals=2) == "+10.57%"
    assert fmt.fmt_pct(V("0")) == "0%"


def test_missing_shows_dash_never_zero():
    assert fmt.fmt_pct(V(None)) == "—" and fmt.fmt_money(V(None)) == "—"


def test_money_and_numbers():
    assert fmt.fmt_money(V("11560021")) == "$11,560,021"
    assert fmt.fmt_money(V("-153096")) == "-$153,096"
    assert fmt.fmt_num(V("8100.925718"), 2) == "8,100.93"
    assert fmt.fmt_num(V("1.665"), 2) == "1.67"       # half-up
