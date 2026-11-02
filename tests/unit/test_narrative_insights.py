import math
from decimal import Decimal

import pytest

from backend.app.calc import indicators as ind
from backend.app.deck.aetops_mensual import fit_label, pick_categories_mom, pick_categories_yoy
from backend.app.models import Group, Period, PeriodRow
from backend.app.narrative import insights as I
from backend.app.narrative.aetops import Box, check, compose_aetops_mensual, pct_d, money, pp_s, labels_for_products
from backend.app.narrative.writer import W, Para, fit, para, to_paragraphs, verify, verify_edited
from backend.app.pipeline import run_aetops
from tests.fixtures import build_base


def V(x):
    return ind.make(x)


def row(label, monto, piezas, pacientes, pedidos=10, share=None):
    vals = {"monto": V(monto), "piezas": V(piezas), "pacientes": V(pacientes), "pedidos": V(pedidos),
            "ticket": V(100), "productos": V(5), "share": V(share)}
    vals["v_paciente"] = ind.ratio(vals["monto"], vals["pacientes"], "x")
    return PeriodRow(label, vals)


def group(name, prev, cur):
    g = Group(name, row("2025", *prev), row("2026", *cur))
    for k in g.current.values:
        g.pct[k] = ind.pct_change(g.current.values[k], g.previous.values[k], k)
    return g


# ------------------------------------------------------------------ descomposición
def test_decomposition_shares_sum_to_one_and_identify_the_driver():
    prev, cur = row("a", 1000, 200, 100), row("b", 2000, 400, 200)          # solo se duplican los pacientes y las piezas
    d = I.decompose_sales(prev, cur)
    assert sum(d.shares.values()) == pytest.approx(1.0)
    assert d.shares["pacientes"] == pytest.approx(1.0) and d.shares["precio_por_pieza"] == pytest.approx(0.0, abs=1e-9)
    assert d.volume == pytest.approx(1.0) and d.total_pct == pytest.approx(1.0)


def test_decomposition_price_driven_and_guards():
    d = I.decompose_sales(row("a", 1000, 200, 100), row("b", 1500, 200, 100))   # solo sube el valor por pieza
    assert d.price == pytest.approx(1.0) and d.volume == pytest.approx(0.0, abs=1e-9)
    assert I.decompose_sales(row("a", 1000, 200, 100), row("b", 1000, 200, 100)) is None   # sin cambio
    assert I.decompose_sales(row("a", 1000, 0, 100), row("b", 1500, 200, 100)) is None     # dato inválido
    assert math.isclose(sum(I.decompose_sales(row("a", 1000, 250, 90), row("b", 900, 300, 80)).shares.values()), 1)


# ------------------------------------------------------------------ aportes y patrones
def test_contributions_and_share_of_change():
    a = group("A", (400, 80, 40, 20, "0.4"), (900, 180, 70, 36, "0.6"))
    b = group("B", (600, 120, 60, 30, "0.6"), (600, 120, 50, 24, "0.4"))
    cs = I.contributions([a, b], Decimal(1000), Decimal(1500))
    assert [c.delta for c in cs] == [500, 0]
    assert cs[0].share_of_change == Decimal(1) and cs[1].share_of_change is None      # solo aporta quien suma
    assert cs[0].pp == Decimal("0.2")


def test_flags_match_the_analyst_patterns():
    # WhatsApp: venta ↑, pacientes ↓
    w = group("W", (1000, 100, 100, 50, "0.25"), (1260, 121, 90, 55, "0.19"))
    f = I.flags(I.contributions([w], Decimal(4000), Decimal(6000))[0], Decimal("0.5"))
    assert {"valor_sobre_volumen", "pierde_share", "crece_menos_que_total"} <= f
    # AE-B: venta ↓ con piezas ↑ => mezcla/ticket
    b = group("B", (1000, 100, 100, 50, "0.3"), (880, 103, 95, 46, "0.26"))
    assert "caida_por_mezcla" in I.flags(I.contributions([b], Decimal(3000), Decimal(3400))[0], Decimal("0.1"))
    # HYR: +150 % desde una base pequeña
    h = group("H", (100, 10, 10, 5, "0.03"), (250, 20, 12, 8, "0.04"))
    assert "base_pequena" in I.flags(I.contributions([h], Decimal(3000), Decimal(6000))[0], Decimal("1"))
    # grupo estable: sin patrones
    s = group("S", (1000, 100, 100, 50, "0.3"), (1010, 101, 101, 50, "0.3"))
    assert I.flags(I.contributions([s], Decimal(3000), Decimal(3030))[0], Decimal("0.01")) == set()


# ------------------------------------------------------------------ escritor y verificador
def test_verifier_requires_evidence_for_every_number():
    ok = para("hecho", lambda w: f"La venta llega a {w.n('$11.56 M')} y crece {w.n('+67%')} vs 2025.")
    assert verify(ok) == []
    bad = Para("La venta crece **+67%** y sube 12% más.", "hecho", nums={"+67%"})
    assert any("12%" in p for p in verify(bad))


def test_verifier_blocks_causal_language_and_untyped_interpretations():
    assert verify(Para("Sube por campaña, debido a descuentos.", "hecho"))
    assert verify(Para("Se explica por volumen.", "interpretacion"))              # sin regla
    assert not verify(Para("Se explica por volumen.", "interpretacion", basis="regla"))
    assert verify(Para("Podría deberse a una campaña.", "hipotesis"))            # no permitida en determinista


def test_edited_text_is_checked_against_known_figures():
    allowed = {"+67%", "$11.56 M"}
    assert verify_edited("La venta llega a $11.56 M (+67%).", allowed) == []
    assert any("+99%" in p for p in verify_edited("La venta crece +99%.", allowed))
    assert verify_edited("Sube porque hubo campaña.", allowed)


def test_fit_drops_low_priority_but_never_the_required_ones():
    ps = [Para("a" * 100, "hecho", 0), Para("b" * 100, "hecho", 5), Para("c" * 100, "hecho", 2)]
    kept = fit(ps, cpl=50, max_lines=5)
    assert [p.text[0] for p in kept] == ["a", "c"]                                   # se va la de prioridad 5
    assert [p.text[0] for p in fit(ps, cpl=50, max_lines=1)] == ["a"]               # nunca la obligatoria


def test_paragraphs_are_separated_by_blank_lines_and_hidden_notes_excluded():
    hidden = Para("nota", "info_insuficiente", 9, visible=False)
    assert to_paragraphs([Para("uno", "hecho"), hidden, Para("dos", "hecho")]) == ["uno", "", "dos"]


# ------------------------------------------------------------------ formato
def test_formatting_half_up_signs_and_spanish_units():
    assert pct_d(Decimal("0.625")) == "+63%" and pct_d(Decimal("-0.625")) == "-63%" and pct_d(Decimal("0.001")) == "0%"
    assert pct_d(Decimal("0.38"), sign=False) == "38%" and pct_d(None) == "n/d"
    assert pp_s(Decimal("0.03")) == "+3 pp" and pp_s(Decimal("-0.02")) == "-2 pp"
    assert money(Decimal("11560021")) == "$11.56 M" and money(Decimal("-153096"), True) == "-$153.1 K"


def test_product_labels_disambiguate_only_real_duplicates():
    class R:
        def __init__(self, n): self.producto = n
    rows = [R("PROLIA 60MG/1ML"), R("PROLIA 60MG/1ML"), R("PAMORELIN 11.25 MG"), R("PAMORELIN 22.5 MG"), R("RIM-VOQ 15 MG")]
    lab = labels_for_products(rows)
    assert lab["PROLIA 60MG/1ML"] == "Prolia"                                        # mismo producto en dos listas
    assert lab["PAMORELIN 11.25 MG"] == "Pamorelin 11.25" and lab["PAMORELIN 22.5 MG"] == "Pamorelin 22.5"
    assert lab["RIM-VOQ 15 MG"] == "Rim-Voq"


# ------------------------------------------------------------------ composición completa
@pytest.fixture(scope="module")
def synthetic(tmp_path_factory):
    d = tmp_path_factory.mktemp("syn")
    per = Period("AETOPS", "mensual", 2026, 9)
    res = run_aetops(build_base(d / "syn"), "mensual", per)
    a, b, _ = pick_categories_yoy(res.tables["aetops.categoria.yoy"].groups)
    up, dn, _ = pick_categories_mom(res.tables["aetops.categoria.mom"].groups)
    return res, per, a + b, up + dn


def test_composed_narrative_is_fully_verified_and_has_no_causes(synthetic):
    res, per, cy, cm = synthetic
    narr = compose_aetops_mensual(res, per, {}, cy, cm)
    assert check(narr) == []
    for paras in narr.values():
        for p in paras:
            assert p.kind in ("hecho", "interpretacion", "info_insuficiente")
            assert p.kind != "interpretacion" or p.basis


def test_grammar_agrees_in_gender_and_number(synthetic):
    res, per, cy, cm = synthetic
    narr = compose_aetops_mensual(res, per, {}, cy, cm)
    text = " ".join(p.plain for k in ("linea_yoy", "canal_yoy", "cat_yoy") for p in narr[k])
    for wrong in ("es el línea", "es el categoría", "canals", "otros líneas", "otros categorías"):
        assert wrong not in text
    assert "es la línea que más aporta" in " ".join(p.plain for p in narr["linea_yoy"])
    assert "es el canal que más aporta" in " ".join(p.plain for p in narr["canal_yoy"])


def test_text_fits_the_given_box(synthetic):
    res, per, cy, cm = synthetic
    box = Box(cpl=40, lines=6)
    narr = compose_aetops_mensual(res, per, {k: box for k in ("panorama", "canal_yoy", "conclusiones")}, cy, cm)
    for k in ("panorama", "canal_yoy", "conclusiones"):
        vis = [p for p in narr[k] if p.visible]
        lines = sum(max(1, -(-len(p.plain) // 40)) for p in vis) + len(vis) - 1
        assert lines <= 6 or all(p.priority == 0 for p in vis), k
        assert vis[0].priority == 0                                                 # lo obligatorio se conserva


def test_unreliable_order_counts_per_channel_are_not_used(synthetic):
    res, per, cy, cm = synthetic
    from backend.app.models import Finding
    res.findings.append(Finding("TOTALS_MISMATCH", "warn", "canal/YOY pedidos (current): Σ = 2998 vs panorama 1427", ""))
    narr = compose_aetops_mensual(res, per, {}, cy, cm)
    visible = " ".join(p.plain for p in narr["canal_yoy"] if p.visible)
    assert "pedidos" not in visible
    hidden = [p for p in narr["canal_yoy"] if not p.visible]
    assert hidden and hidden[0].kind == "info_insuficiente"
    res.findings.pop()


def test_fit_label_abbreviates_only_what_does_not_fit():
    assert [fit_label(x) for x in ("2025", "Julio", "Agosto", "Noviembre", "Diciembre", "Septiembre")] == \
        ["2025", "Julio", "Agosto", "Noviembre", "Diciembre", "Sep"]


def test_verifier_does_not_swallow_punctuation_after_numbers():
    p = para("hecho", lambda w: f"AE-A {w.n('+$300')}, AE-B {w.n('+$50')}; total {w.n('1,500')}.")
    assert verify(p) == []


def test_zero_rounding_has_no_sign_and_is_neutral():
    from backend.app import format as F
    from backend.app.deck import pptx_ops as ops
    assert F.fmt_pct(V("-0.003"), 0, sign=False) == "0%" and F.fmt_pct(V("-0.004"), 0) == "0%"
    assert F.fmt_money(V("-0.4"), 0) == "$0"
    assert ops.delta_style(Decimal("-0.003"), 0) == ops.NEU           # se ve '0%': neutro
    assert ops.delta_style(Decimal("-0.003")) == ops.NEG              # sin redondeo, conserva el signo real


def test_other_groups_agree_in_gender_in_the_pierde_share_sentence():
    from backend.app.narrative.aetops import _group_sentence
    cases = {"línea": "otras líneas", "categoría": "otras categorías", "canal": "otros canales"}
    for kind, phrase in cases.items():
        g = group("X", (1000, 100, 100, 50, "0.3"), (1100, 105, 98, 52, "0.25"))
        c = I.contributions([g], Decimal(3000), Decimal(4000))[0]
        p = _group_sentence(c, kind, Decimal("0.33"), RULES_, True, "2025")
        assert phrase in p.plain, (kind, p.plain)


from backend.app.narrative.rules import RULES as RULES_  # noqa: E402
