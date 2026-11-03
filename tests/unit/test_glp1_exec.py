"""Resumen ejecutivo y recomendaciones de GLP-1 (sin plantilla: solo reglas y verificación)."""
import importlib.util
from decimal import Decimal
from pathlib import Path

import pytest

from backend.app.history import store as hist
from backend.app.models import Period
from backend.app.narrative.glp1_exec import attainment_glp1, build_executive_glp1
from backend.app.narrative.writer import verify_all
from backend.app.pipeline import run_glp1_raw
from backend.app.targets import Targets

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("mg", ROOT / "tools/make_raw_glp1_synthetic.py")
mg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mg)
P9 = Period("GLP1", "mensual", 2026, 9)


@pytest.fixture(scope="module")
def res(tmp_path_factory):
    return run_glp1_raw(mg.build(tmp_path_factory.mktemp("g") / "g.xlsx"), P9)


def test_panorama_totals_match_blocks(res):
    P = res.blocks["panorama"].rows[0].values
    assert P["monto"].v == sum(r.values["monto"].v for r in res.blocks["region"].rows)
    assert P["ticket"].v == P["monto"].v / P["pedidos"].v
    assert "monto_prev" in P and "monto_yoy" in P and P["compras"].v > 0


def test_executive_is_verified_and_structured(res):
    ex = build_executive_glp1(res.blocks, res.funnel, P9)
    assert verify_all(ex.resumen + ex.recomendaciones) == []
    heads = [p.plain for p in ex.resumen if p.priority == 0 and p.kind == "hecho"]
    assert heads[0] == "Dónde estamos" and "Descubrimientos del periodo" in heads
    assert ex.recs and all(r.para.basis for r in ex.recs)
    assert all(r.prio in ("alta", "media", "baja") for r in ex.recs)


def test_target_attainment_is_optional_and_drives_a_recommendation(res):
    assert attainment_glp1(res.blocks, None) == []
    P = res.blocks["panorama"].rows[0].values
    att = attainment_glp1(res.blocks, Targets(P["monto"].v * 2, {}))
    assert att[0].status == "debajo" and att[0].pct == Decimal("0.5")
    ex = build_executive_glp1(res.blocks, res.funnel, P9, att=att)
    assert any("meta" in r.action.lower() for r in ex.recs)
    assert verify_all(ex.resumen + ex.recomendaciones) == []


def test_history_snapshot_feeds_trends(res, tmp_path):
    kp = hist.snapshot_from_glp1(res.blocks, P9, Targets(Decimal(1000), {}))
    assert {(k.which, k.metric) for k in kp if k.scope == "panorama"} >= {("current", "monto"), ("prev_period", "monto"), ("prev_year", "ticket")}
    con = hist.connect(tmp_path / "h.sqlite")
    hist.record_run(con, P9, kp)
    pts = hist.series(con, "GLP1", "mensual", "panorama", "TOTAL", "monto")
    assert [(p.year, p.idx) for p in pts] == [(2025, 9), (2026, 8), (2026, 9)]
