from decimal import Decimal

import pytest

from backend.app.models import Period
from backend.app.narrative import aetops as NA
from backend.app.narrative.executive import build_executive
from backend.app.narrative.targets import attainment, status_of
from backend.app.narrative.writer import verify_all
from backend.app.pipeline import run_aetops
from backend.app.targets import Targets
from tests.fixtures import build_base

SEP = Period("AETOPS", "mensual", 2026, 9)


def run(tmp_path, targets, required=True):
    return run_aetops(build_base(tmp_path / "syn"), "mensual", SEP, targets=targets, require_targets=required)


def ids(res, sev=None):
    return [f.id for f in res.findings if sev is None or f.severity == sev]


def test_targets_parse_from_text_with_symbols():
    t = Targets.parse({"total": "$1,600", "AE-A": "900", "AE-B": 700})
    assert t.total == 1600 and t.by_group == {"AE-A": Decimal(900), "AE-B": Decimal(700)}
    with pytest.raises(ValueError):
        Targets.parse({"total": "abc"})


def test_aetops_requires_total_and_every_line(tmp_path):
    assert "TARGETS_MISSING" in ids(run(tmp_path, None), "block")
    r = run(tmp_path, Targets(Decimal(1600), {"AE-A": Decimal(900)}))
    assert [f.message for f in r.findings if f.id == "TARGET_LINE_MISSING"] == ["Falta la meta de la línea AE-B."]
    assert not r.can_generate
    ok = run(tmp_path, Targets(Decimal(1600), {"AE-A": Decimal(900), "AE-B": Decimal(700)}))
    assert not [f for f in ok.findings if f.id.startswith("TARGET")] and ok.can_generate


def test_targets_are_optional_when_not_required_e_g_glp1(tmp_path):
    assert not [f for f in run(tmp_path, None, required=False).findings if f.id.startswith("TARGET")]


def test_invalid_and_inconsistent_targets(tmp_path):
    r = run(tmp_path, Targets(Decimal(0), {"AE-A": Decimal(900), "AE-B": Decimal(-1), "XX": Decimal(5)}))
    got = set(ids(r))
    assert {"TARGET_NONPOSITIVE", "TARGET_GROUP_UNKNOWN"} <= got and not r.can_generate
    r = run(tmp_path, Targets(Decimal(5000), {"AE-A": Decimal(900), "AE-B": Decimal(700)}))
    assert "TARGETS_SUM_MISMATCH" in ids(r, "warn") and r.can_generate


def test_attainment_status_and_gap(tmp_path):
    t = Targets(Decimal(2000), {"AE-A": Decimal(800), "AE-B": Decimal(1000)})     # venta: total 1500, AE-A 900, AE-B 600
    att = {a.name: a for a in attainment(run(tmp_path, t), t)}
    assert att["TOTAL"].pct == Decimal("0.75") and att["TOTAL"].gap == -500 and att["TOTAL"].status == "debajo"
    assert att["AE-A"].pct == Decimal("1.125") and att["AE-A"].status == "cumple"
    assert att["AE-B"].gap == -400
    assert status_of(Decimal("0.96")) == "cerca" and status_of(Decimal("0.9")) == "debajo" and status_of(Decimal(1)) == "cumple"


def test_narrative_reads_the_deviation_and_recommends_for_lines_below_target(tmp_path):
    t = Targets(Decimal(2000), {"AE-A": Decimal(800), "AE-B": Decimal(1000)})
    res = run(tmp_path, t)
    att = attainment(res, t)
    ex = build_executive(res, SEP, att=att)
    text = " ".join(p.plain for p in ex.resumen)
    assert "La venta alcanza 75% de la meta ($2.0 K; -$500)" in text
    assert any("AE-B" in p.plain and "contra su meta" in p.plain and "60% de la meta" in p.plain for p in ex.recomendaciones)
    assert not any("AE-A" in p.plain and "contra su meta" in p.plain for p in ex.recomendaciones)     # AE-A cumple
    assert verify_all(ex.resumen + ex.recomendaciones) == []
    pano = " ".join(p.plain for p in NA.s_panorama(res.tables["aetops.panorama.yoy"].groups[0],
                                                     res.tables["aetops.panorama.mom"].groups[0], SEP, NA.RULES, att))
    assert "Por línea, quedan por debajo de su meta: AE-B (60%, -$400)" in pano


def test_no_targets_means_no_deviation_text(tmp_path):
    res = run(tmp_path, None, required=False)
    ex = build_executive(res, SEP)
    assert "meta" not in " ".join(p.plain for p in ex.resumen).lower()
