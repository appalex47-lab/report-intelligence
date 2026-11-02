from decimal import Decimal

from backend.app.calc import indicators as ind
from backend.app.deck.aetops_mensual import fit_label
from backend.app.models import Group, PeriodRow
from backend.app.narrative import deterministic as N


def V(x):
    return ind.make(x)


def group(name, pct_monto, share="0.1"):
    keys = ("monto", "piezas", "pacientes", "pedidos", "ticket", "productos", "share")
    cur = PeriodRow("2026", {k: V(share if k == "share" else 100) for k in keys})
    prv = PeriodRow("2025", {k: V(50) for k in keys})
    pct = {k: V(pct_monto) for k in keys}
    return Group(name, prv, cur, pct)


def test_percent_and_money_use_half_up_like_the_decks():
    assert N.pct(V("0.625")) == "+63%" and N.pct(V("-0.625")) == "-63%" and N.pct(V("0")) == "0%"
    assert N.pct(V(None)) == "n/d"
    assert N.money_short(Decimal("11560021")) == "$11.56 M"
    assert N.money_short(Decimal("209173"), sign=True) == "+$209.2 K"
    assert N.money_short(Decimal("-153096"), sign=True) == "-$153.1 K"
    assert N.money_short(None) == "n/d"


def test_short_product_name():
    assert N.short("PROLIA 60MG/1ML JPRELL CAJ") == "Prolia"
    assert N.short("RIM-VOQ 15 MG TAB") == "Rim-Voq"


def test_narrative_never_states_causes():
    text = " ".join(N.groups([group("AE-A", "0.67")], "líneas"))
    for banned in ("debido", "por falta", "porque", "causa", "gracias a"):
        assert banned not in text.lower()


def test_compact_group_narrative_stays_short_for_many_categories():
    gs = [group(f"CAT {i}", str(Decimal(i) / 10 - Decimal("0.3"))) for i in range(9)]
    out = N.groups_compact(gs)
    assert len([p for p in out if p]) <= 4                     # ≤ 3 detalles + 1 línea de resto
    assert "Resto:" in out[-1]
    assert "CAT 8" in out[0]                                   # primero el de mayor avance
    assert "CAT 0" in " ".join(out)                            # y el mayor retroceso aparece


def test_missing_values_show_nd_not_zero():
    g = group("X", None)
    assert "n/d" in N.groups([g], "x")[0]


def test_fit_label_abbreviates_only_what_does_not_fit():
    assert [fit_label(x) for x in ("2025", "Julio", "Agosto", "Noviembre", "Diciembre", "Septiembre")] == \
        ["2025", "Julio", "Agosto", "Noviembre", "Diciembre", "Sep"]
