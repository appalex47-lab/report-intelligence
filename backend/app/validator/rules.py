"""Reglas de validación (docs/ARQUITECTURA.md §7). Cada regla = id + severidad + evidencia."""
from __future__ import annotations

from decimal import Decimal

from ..importer.base_sheet import RawBase
from ..models import Finding, Table
from ..calc.indicators import to_dec

TOTALS_TOLERANCE = Decimal("0.005")     # 0.5 %, configurable (config/rules.yaml, Fase 4b)
PASTED_TOLERANCE = Decimal("0.0001")
ADDITIVE = ("monto", "piezas", "pedidos")   # pacientes no es aditivo entre canales


def _rows_identical(a, b) -> bool:
    keys = ("monto", "piezas", "pacientes", "pedidos")
    return all(a.values[k].v is not None and a.values[k].v == b.values[k].v for k in keys)


def validate(raw: RawBase, tables: dict[str, Table]) -> list[Finding]:
    out: list[Finding] = list(raw.findings)

    # IDENTICAL_PERIODS: dos periodos de comparación con cifras idénticas
    for key, t in tables.items():
        if t.comparison != "MoM":
            continue
        for g in t.groups:
            if _rows_identical(g.previous, g.current):
                out.append(Finding(
                    "IDENTICAL_PERIODS", "block",
                    f"{key} / {g.name}: '{g.previous.label}' y '{g.current.label}' tienen "
                    "cifras idénticas; probable archivo sin actualizar.",
                    g.current.values["monto"].src.cells if g.current.values["monto"].src else ""))
                break

    # MISSING_COMPARISON: grupo incompleto (falta periodo anterior/actual)
    for sec in raw.sections:
        if sec.kind in ("canal", "linea", "panorama", "categoria"):
            for g in sec.groups:
                if len(g.periods) != 2:
                    out.append(Finding(
                        "MISSING_COMPARISON", "block",
                        f"{sec.kind}/{sec.marker} '{g.name}' tiene {len(g.periods)} periodo(s); se requieren 2.",
                        f"Base!fila {sec.start_row}"))

    # PERIOD_LABELS_INCONSISTENT: grupos de una misma tabla con rótulos de periodo distintos
    for key, t in tables.items():
        labels = {(g.previous.label, g.current.label) for g in t.groups}
        if len(labels) > 1:
            detail = "; ".join(
                f"{g.name}: {g.previous.label}->{g.current.label}" for g in t.groups)
            out.append(Finding(
                "PERIOD_LABELS_INCONSISTENT", "block",
                f"{key}: los grupos no comparan los mismos periodos ({detail}).", key))

    # TOTALS_MISMATCH: Σ canales / Σ líneas = total del panorama (solo métricas aditivas)
    for marker in ("yoy", "mom"):
        pano = tables.get(f"aetops.panorama.{marker}")
        if not pano or not pano.groups:
            continue
        for kind in ("canal", "linea", "categoria"):
            t = tables.get(f"aetops.{kind}.{marker}")
            if not t:
                continue
            for metric in ADDITIVE:
                for side in ("previous", "current"):
                    total = getattr(pano.groups[0], side).values[metric].v
                    parts = [getattr(g, side).values[metric].v for g in t.groups]
                    if total is None or any(p is None for p in parts) or total == 0:
                        continue
                    diff = abs(sum(parts) - total) / total
                    if diff > TOTALS_TOLERANCE:
                        out.append(Finding(
                            "TOTALS_MISMATCH", "warn",
                            f"{kind}/{marker.upper()} {metric} ({side}): Σ = {sum(parts)} vs "
                            f"panorama {total} (dif. {diff:.1%}).", f"aetops.{kind}.{marker}"))

    # TICKET_FORMULA_UNVERIFIED: ticket pegado que no equivale a Monto ÷ Pedidos
    for key, t in tables.items():
        for g in t.groups:
            v = g.current.values
            if v["ticket"].note.startswith("pegado") and v["pedidos"].v and v["monto"].v and v["ticket"].v:
                calc = v["monto"].v / v["pedidos"].v
                if abs(calc - v["ticket"].v) / v["ticket"].v > TOTALS_TOLERANCE:
                    out.append(Finding(
                        "TICKET_FORMULA_UNVERIFIED", "warn",
                        f"{key} / {g.name}: Ticket pegado {float(v['ticket'].v):,.2f} ≠ Monto÷Pedidos "
                        f"{float(calc):,.2f}. Se usa el valor del Excel; fórmula pendiente de validación.",
                        v["ticket"].src.cells if v["ticket"].src else ""))
                    break

    # PASTED_DIFFERS: el Excel trae %Δ pegado y el motor calcula otro valor
    for sec in raw.sections:
        key = f"aetops.{sec.kind}.{sec.marker.lower()}"
        t = tables.get(key)
        if not t:
            continue
        by_name = {g.name: g for g in t.groups}
        for rg in sec.groups:
            g = by_name.get(rg.name)
            if g is None or not rg.pasted_delta:
                continue
            for metric, (raw_v, coord) in rg.pasted_delta.items():
                mine = g.pct.get(metric)
                theirs = to_dec(raw_v)
                if mine is None or mine.v is None or theirs is None:
                    continue
                if abs(mine.v - theirs) > max(PASTED_TOLERANCE, abs(theirs) * Decimal('0.001')):
                    out.append(Finding(
                        "PASTED_DIFFERS", "warn",
                        f"{rg.name}/{metric}: Excel {theirs:.4f} vs motor {mine.v:.4f}.", coord))
    return out


def has_blockers(findings: list[Finding]) -> bool:
    return any(f.severity == "block" for f in findings)
