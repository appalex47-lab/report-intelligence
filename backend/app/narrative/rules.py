"""Umbrales de relevancia de la narrativa (configurables; ver docs/OBJETIVO_Y_NARRATIVA.md §4)."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class NarrativeRules:
    relevance: Decimal = Decimal("0.05")          # |Δ| < 5 % se considera estable
    share_pp: Decimal = Decimal("0.02")           # cambio de participación relevante: 2 pp
    small_base_share: Decimal = Decimal("0.05")   # base pequeña: share previo < 5 %
    small_base_growth: Decimal = Decimal("1.0")   # y crecimiento > 100 %
    min_total_change: float = 0.005               # ln(venta₁/venta₀) mínimo para descomponer
    top_concentration: int = 4                    # productos para "los N primeros suman X %"
    max_groups: int = 4


RULES = NarrativeRules()
