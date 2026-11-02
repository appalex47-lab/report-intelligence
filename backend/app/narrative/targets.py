"""Cumplimiento de meta: venta ÷ meta, brecha en pesos y estado, total y por línea."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ..targets import Targets
from .rules import RULES, NarrativeRules


@dataclass(frozen=True)
class Attainment:
    name: str                 # 'TOTAL' o la línea
    actual: Decimal
    target: Decimal
    pct: Decimal              # actual ÷ meta
    gap: Decimal              # actual − meta
    status: str               # cumple | cerca | debajo


def status_of(pct: Decimal, rules: NarrativeRules = RULES) -> str:
    return "cumple" if pct >= 1 else "cerca" if pct >= 1 - rules.target_tolerance else "debajo"


def attainment(result, targets: Targets | None, rules: NarrativeRules = RULES) -> list[Attainment]:
    if targets is None:
        return []
    out: list[Attainment] = []

    def add(name, actual, target):
        if actual is not None and target:
            pct = actual / target
            out.append(Attainment(name, actual, target, pct, actual - target, status_of(pct, rules)))
    pano = result.tables["aetops.panorama.yoy"].groups[0]
    add("TOTAL", pano.current.values["monto"].v, targets.total)
    if "aetops.linea.yoy" in result.tables:
        for g in result.tables["aetops.linea.yoy"].groups:
            add(g.name, g.current.values["monto"].v, targets.by_group.get(g.name))
    return out
