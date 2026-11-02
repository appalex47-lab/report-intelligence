import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest

from backend.app.history import store as H
from backend.app.models import Period
from backend.app.narrative import trends as T
from backend.app.narrative.writer import verify
from backend.app.pipeline import run_aetops
from tests.fixtures import build_base

Q = lambda y, i: Period("AETOPS", "trimestral", y, i)  # noqa: E731


def kp(period, value, which="current", metric="monto", scope="panorama", name="TOTAL", label=None):
    return H.KpiRow(scope, name, which, label or period.label, metric, Decimal(str(value)))


@pytest.fixture()
def con(tmp_path):
    return H.connect(tmp_path / "h.sqlite")


# ----------------------------------------------------------------------------- inmutabilidad y versiones
def test_history_is_immutable_by_database_triggers(con, tmp_path):
    f = tmp_path / "libro.xlsx"
    f.write_bytes(b"x")
    rid = H.record_run(con, Q(2026, 3), [kp(Q(2026, 3), 100)], sources=[f])
    for sql in ("UPDATE runs SET qa_passed=0", "DELETE FROM runs", "UPDATE kpis SET value='1'", "DELETE FROM kpis",
                "DELETE FROM sources"):
        with pytest.raises(sqlite3.DatabaseError, match="historial inmutable"):
            con.execute(sql)
    assert con.execute("SELECT COUNT(*) FROM runs WHERE id=?", (rid,)).fetchone()[0] == 1
    assert con.execute("SELECT COUNT(*) FROM sources").fetchone()[0] == 1


def test_regenerating_a_period_creates_a_new_version_and_keeps_the_old_one(con, tmp_path):
    f = tmp_path / "libro.xlsx"
    f.write_bytes(b"datos-1")
    r1 = H.record_run(con, Q(2026, 3), [kp(Q(2026, 3), 100)], sources=[f])
    f.write_bytes(b"datos-2")
    r2 = H.record_run(con, Q(2026, 3), [kp(Q(2026, 3), 110)], sources=[f])
    vs = [v for (_, v) in con.execute("SELECT id, version FROM runs ORDER BY id")]
    assert vs == [1, 2] and r1 != r2
    shas = [s for (s,) in con.execute("SELECT sha256 FROM sources ORDER BY run_id")]
    assert shas[0] != shas[1] and len(shas[0]) == 64                    # cada versión recuerda su archivo fuente


def test_context_and_narrative_are_stored_with_the_run(con):
    H.record_run(con, Q(2026, 3), [], context=["Incidencia de abasto"], narrative={"resumen": [{"texto": "x"}]})
    ctx, narr = con.execute("SELECT context, narrative FROM runs").fetchone()
    assert "Incidencia de abasto" in ctx and "resumen" in narr


# ----------------------------------------------------------------------------- series
def test_series_merges_runs_with_comparatives_and_prefers_the_real_report(con):
    # el reporte de Q3 2026 trae Q3 2025 como comparativo (derivado); el de Q3 2025 lo trae como valor real
    H.record_run(con, Q(2026, 3), [kp(Q(2026, 3), 340), kp(Q(2026, 3), 213, "prev_year", label="Q3 2025")])
    H.record_run(con, Q(2025, 3), [kp(Q(2025, 3), 215)])
    s = H.series(con, "AETOPS", "trimestral", "panorama", "TOTAL", "monto")
    assert [(p.year, p.idx, p.value, p.source) for p in s] == [
        (2025, 3, Decimal("215"), "run"), (2026, 3, Decimal("340"), "run")]          # el real gana al derivado (213)


def test_series_uses_latest_version_of_the_same_period(con):
    H.record_run(con, Q(2026, 3), [kp(Q(2026, 3), 100)])
    H.record_run(con, Q(2026, 3), [kp(Q(2026, 3), 120)])
    s = H.series(con, "AETOPS", "trimestral", "panorama", "TOTAL", "monto")
    assert s[-1].value == Decimal("120")


def test_previous_period_comparative_is_placed_one_period_back(con):
    per = Period("AETOPS", "mensual", 2026, 1)
    H.record_run(con, per, [kp(per, 50, label="enero"), kp(per, 40, "prev_period", label="diciembre")])
    s = H.series(con, "AETOPS", "mensual", "panorama", "TOTAL", "monto")
    assert [(p.year, p.idx) for p in s] == [(2025, 12), (2026, 1)]                 # cruza el año


def test_unit_and_periodicity_series_do_not_mix(con):
    H.record_run(con, Q(2026, 3), [kp(Q(2026, 3), 100)])
    g = Period("GLP1", "trimestral", 2026, 3)
    H.record_run(con, g, [kp(g, 999)])
    assert [p.value for p in H.series(con, "AETOPS", "trimestral", "panorama", "TOTAL", "monto")] == [Decimal("100")]


# ----------------------------------------------------------------------------- tendencias
def pts(vals, start=(2025, 4)):
    out, (y, i) = [], start
    for v in vals:
        out.append(H.Point(y, i, Decimal(str(v)), "run", 1))
        y, i = H._shift("trimestral", y, i, 1)
    return out


def test_two_consecutive_rises_outside_the_band_are_a_trend():
    t = T.analyze("trimestral", pts([28.7, 26.4, 30.5, 33.9]), "monto")
    assert t.direction == "sube" and t.streak == 2
    assert round(float(t.last), 2) == 0.11 and round(float(t.cumulative), 2) == 0.28         # +11 % y +28 % desde Q1 26
    assert "segundo trimestre consecutivo" in t.para.plain and "Q1 2026" in t.para.plain
    assert t.para.kind == "interpretacion" and t.para.basis and verify(t.para) == []


def test_three_consecutive_falls_and_longer_streaks():
    t = T.analyze("trimestral", pts([100, 90, 80, 70]), "ticket")
    assert t.direction == "baja" and t.streak == 3 and "tercer trimestre consecutivo" in t.para.plain
    assert "cae" in t.para.plain


def test_changes_inside_the_stability_band_are_not_a_trend():
    t = T.analyze("trimestral", pts([100, 102, 104, 105]), "monto")                # ≤ 5 % cada vez
    assert t.direction in ("estable", "mixta") and t.streak < 2 and "no muestra una tendencia sostenida" in t.para.plain


def test_a_break_in_the_streak_only_counts_the_latest_run():
    t = T.analyze("trimestral", pts([100, 120, 100, 115, 130]), "monto")           # suben las dos últimas
    assert t.direction == "sube" and t.streak == 2


def test_little_history_is_reported_as_insufficient_not_guessed():
    t = T.analyze("trimestral", pts([100, 120]), "monto")
    assert t.direction == "insuficiente" and t.para.kind == "info_insuficiente" and "3" in t.para.plain


def test_gaps_in_the_history_block_the_claim():
    p = pts([100, 120, 140, 160])
    p[2] = H.Point(2026, 4, p[2].value, "run", 1)                                   # salta un trimestre
    t = T.analyze("trimestral", [p[0], p[1], H.Point(2026, 4, Decimal("140"), "run", 1)], "monto")
    assert t.direction == "insuficiente" and "huecos" in t.para.plain


# ----------------------------------------------------------------------------- de punta a punta con el motor
def test_snapshot_from_a_real_engine_result_feeds_the_series(con, tmp_path):
    per = Period("AETOPS", "mensual", 2026, 9)
    res = run_aetops(build_base(tmp_path / "syn"), "mensual", per)
    kpis = H.snapshot_from_result(res, per)
    assert {k.scope for k in kpis} >= {"panorama", "canal", "linea", "categoria", "negados"}
    H.record_run(con, per, kpis)
    s = H.series(con, "AETOPS", "mensual", "panorama", "TOTAL", "monto")
    assert [(p.year, p.idx, p.source) for p in s] == [(2025, 9, "derivado"), (2026, 8, "derivado"), (2026, 9, "run")] \
        or [(p.year, p.idx) for p in s][-1] == (2026, 9)
    assert s[-1].value == Decimal("1500")
