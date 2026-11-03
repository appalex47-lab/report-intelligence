"""Historial de reportes (docs/ARQUITECTURA.md §11.1): SQLite, solo inserción.

- Cada reporte generado guarda una foto de sus KPIs, sus archivos fuente (SHA-256), versiones y el narrative.json.
- Regenerar el mismo periodo crea la versión N+1; nada se sobrescribe ni se borra (lo impiden triggers).
- De aquí salen las series para detectar tendencias.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from ..models import Period

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs(
  id INTEGER PRIMARY KEY AUTOINCREMENT, unit TEXT NOT NULL, periodicity TEXT NOT NULL, year INTEGER NOT NULL,
  idx INTEGER NOT NULL, version INTEGER NOT NULL, created_at TEXT NOT NULL, profile TEXT, template TEXT,
  template_sha TEXT, pptx_sha TEXT, pdf_sha TEXT, qa_passed INTEGER, downloadable INTEGER,
  findings TEXT, narrative TEXT, context TEXT, UNIQUE(unit, periodicity, year, idx, version));
CREATE TABLE IF NOT EXISTS sources(run_id INTEGER NOT NULL, name TEXT, sha256 TEXT, size INTEGER);
CREATE TABLE IF NOT EXISTS kpis(run_id INTEGER NOT NULL, scope TEXT NOT NULL, name TEXT NOT NULL,
  which TEXT NOT NULL, label TEXT, metric TEXT NOT NULL, value TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS kpis_idx ON kpis(scope, name, metric);
CREATE TRIGGER IF NOT EXISTS runs_no_update BEFORE UPDATE ON runs BEGIN SELECT RAISE(ABORT, 'historial inmutable'); END;
CREATE TRIGGER IF NOT EXISTS runs_no_delete BEFORE DELETE ON runs BEGIN SELECT RAISE(ABORT, 'historial inmutable'); END;
CREATE TRIGGER IF NOT EXISTS kpis_no_update BEFORE UPDATE ON kpis BEGIN SELECT RAISE(ABORT, 'historial inmutable'); END;
CREATE TRIGGER IF NOT EXISTS kpis_no_delete BEFORE DELETE ON kpis BEGIN SELECT RAISE(ABORT, 'historial inmutable'); END;
CREATE TRIGGER IF NOT EXISTS src_no_update BEFORE UPDATE ON sources BEGIN SELECT RAISE(ABORT, 'historial inmutable'); END;
CREATE TRIGGER IF NOT EXISTS src_no_delete BEFORE DELETE ON sources BEGIN SELECT RAISE(ABORT, 'historial inmutable'); END;
"""
METRICS = ("monto", "piezas", "pacientes", "pedidos", "ticket", "productos", "size_b", "v_paciente", "share")


def connect(path: str | Path) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    con.executescript(SCHEMA)
    return con


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@dataclass(frozen=True)
class KpiRow:
    scope: str          # panorama | canal | linea | categoria | negados
    name: str           # TOTAL, 'APP FESA', 'AE-A'…
    which: str          # current | prev_year | prev_period
    label: str          # '2026', 'Q3 2025', 'Agosto'…
    metric: str
    value: Decimal


def snapshot_from_result(result, period: Period, targets=None) -> list[KpiRow]:
    """Foto de los KPIs del reporte: valores del periodo y de su(s) comparativo(s)."""
    rows: list[KpiRow] = []
    for key, table in result.tables.items():
        _, scope, cmp_ = key.split(".")
        for g in table.groups:
            for which, side in (("current", g.current), ("prev_year" if cmp_ == "yoy" else "prev_period", g.previous)):
                if cmp_ == "mom" and which == "current":
                    continue                                   # el periodo actual ya sale del YoY
                for m in METRICS:
                    v = side.values.get(m)
                    if v is not None and v.v is not None:
                        rows.append(KpiRow(scope, g.name, which, side.label, m, v.v))
    alta = result.negados.get("aetops.negados.alta")
    if alta and alta.total.v is not None:
        rows.append(KpiRow("negados", "TOTAL", "current", period.label, "monto", alta.total.v))
    if targets is not None:                         # las metas capturadas viajan con el reporte
        if targets.total is not None:
            rows.append(KpiRow("meta", "TOTAL", "current", period.label, "monto", targets.total))
        for k, v in targets.by_group.items():
            rows.append(KpiRow("meta", k, "current", period.label, "monto", v))
    return rows


def snapshot_from_glp1(blocks: dict, period: Period, targets=None) -> list[KpiRow]:
    """Foto de KPIs de GLP-1 desde el bloque 'panorama' (periodo actual y sus comparativos)."""
    pano = blocks.get("panorama")
    rows: list[KpiRow] = []
    if not pano:
        return rows
    P = pano.rows[0].values
    py, pp = (f"Q{period.index} {period.year - 1}" if period.periodicity == "trimestral" else str(period.year - 1)), None
    if period.periodicity == "mensual":
        pp = period.previous_month_name.capitalize()
    else:
        pp = f"Q{period.index - 1} {period.year}" if period.index > 1 else f"Q4 {period.year - 1}"
    cur = period.label if period.periodicity == "trimestral" else str(period.year)
    for suf, which, label in (("", "current", cur), ("_prev", "prev_period", pp), ("_yoy", "prev_year", py)):
        for m in ("monto", "pedidos", "pacientes", "piezas", "ticket"):
            x = P.get(m + suf)
            if x is not None and x.v is not None:
                rows.append(KpiRow("panorama", "TOTAL", which, label, m, x.v))
    neg = blocks.get("negados")
    if neg and neg.rows:
        rows.append(KpiRow("negados", "TOTAL", "current", period.label, "monto",
                           sum((r.values["monto_negado"].v or Decimal(0)) for r in neg.rows)))
    if targets is not None and targets.total is not None:
        rows.append(KpiRow("meta", "TOTAL", "current", period.label, "monto", targets.total))
    return rows


def next_version(con, period: Period) -> int:
    r = con.execute("SELECT COALESCE(MAX(version),0) FROM runs WHERE unit=? AND periodicity=? AND year=? AND idx=?",
                    (period.unit, period.periodicity, period.year, period.index)).fetchone()
    return r[0] + 1


def record_run(con, period: Period, kpis: list[KpiRow], *, profile: str = "", template: Path | None = None,
               sources: list[Path] | None = None, pptx: Path | None = None, pdf: Path | None = None,
               qa_passed: bool = False, downloadable: bool = False, findings: list | None = None,
               narrative: dict | None = None, context: list[str] | None = None) -> int:
    version = next_version(con, period)
    cur = con.execute(
        "INSERT INTO runs(unit,periodicity,year,idx,version,created_at,profile,template,template_sha,pptx_sha,pdf_sha,"
        "qa_passed,downloadable,findings,narrative,context) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (period.unit, period.periodicity, period.year, period.index, version,
         datetime.now(timezone.utc).isoformat(timespec="seconds"), profile,
         template.name if template else None, sha256(template) if template else None,
         sha256(pptx) if pptx else None, sha256(pdf) if pdf else None, int(qa_passed), int(downloadable),
         json.dumps(findings or [], ensure_ascii=False), json.dumps(narrative or {}, ensure_ascii=False),
         json.dumps(context or [], ensure_ascii=False)))
    rid = cur.lastrowid
    con.executemany("INSERT INTO sources(run_id,name,sha256,size) VALUES (?,?,?,?)",
                    [(rid, Path(p).name, sha256(Path(p)), Path(p).stat().st_size) for p in (sources or [])])
    con.executemany("INSERT INTO kpis(run_id,scope,name,which,label,metric,value) VALUES (?,?,?,?,?,?,?)",
                    [(rid, k.scope, k.name, k.which, k.label, k.metric, str(k.value)) for k in kpis])
    con.commit()
    return rid


def list_runs(con, unit: str | None = None):
    q = "SELECT id,unit,periodicity,year,idx,version,created_at,qa_passed,downloadable FROM runs"
    args: tuple = ()
    if unit:
        q, args = q + " WHERE unit=?", (unit,)
    return con.execute(q + " ORDER BY year, idx, version", args).fetchall()


# ----------------------------------------------------------------------------- series
@dataclass(frozen=True)
class Point:
    year: int
    idx: int
    value: Decimal
    source: str                 # 'run' (reporte de ese periodo) | 'derivado' (comparativo de otro reporte)
    run_id: int


def _shift(periodicity: str, year: int, idx: int, steps: int) -> tuple[int, int]:
    n = 12 if periodicity == "mensual" else 4
    t = year * n + (idx - 1) + steps
    return t // n, t % n + 1


def series(con, unit: str, periodicity: str, scope: str, name: str, metric: str) -> list[Point]:
    """Serie cronológica de un KPI. Un valor de un reporte del propio periodo (última versión) gana sobre el
    derivado como comparativo de otro reporte."""
    rows = con.execute(
        "SELECT r.id, r.year, r.idx, r.version, k.which, k.value FROM kpis k JOIN runs r ON r.id=k.run_id "
        "WHERE r.unit=? AND r.periodicity=? AND k.scope=? AND k.name=? AND k.metric=? ORDER BY r.year, r.idx, r.version",
        (unit, periodicity, scope, name, metric)).fetchall()
    best: dict[tuple[int, int], tuple[int, int, Point]] = {}
    for rid, y, i, ver, which, val in rows:
        if which == "current":
            ty, ti, rank = y, i, 2
        elif which == "prev_year":
            ty, ti, rank = y - 1, i, 1
        else:
            ty, ti = _shift(periodicity, y, i, -1)
            rank = 1
        p = Point(ty, ti, Decimal(val), "run" if rank == 2 else "derivado", rid)
        cur = best.get((ty, ti))
        if cur is None or (rank, ver) >= (cur[0], cur[1]):
            best[(ty, ti)] = (rank, ver, p)
    return [v[2] for _, v in sorted(best.items())]


def contiguous(periodicity: str, pts: list[Point]) -> bool:
    return all(_shift(periodicity, a.year, a.idx, 1) == (b.year, b.idx) for a, b in zip(pts, pts[1:]))
