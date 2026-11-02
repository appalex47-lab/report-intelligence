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
    # --- materialidad y recomendaciones (propuesta; configurable) ---
    materiality: Decimal = Decimal("0.01")        # un grupo/producto solo "importa" si mueve ≥ 1 % de la venta total
    share_loss_pp: Decimal = Decimal("0.05")      # ceder ≥ 5 pp de participación mientras se crece es un hallazgo
    concentration_share: Decimal = Decimal("0.50")  # una línea/canal con ≥ 50 % de la venta es concentración
    recovery_scenario: Decimal = Decimal("0.25")  # escenario ilustrativo: recuperar 25 % del monto negado
    prio_high: Decimal = Decimal("0.07")          # puntaje (impacto × accionabilidad) ≥ 7 % de la venta -> ALTA
    prio_mid: Decimal = Decimal("0.03")           # ≥ 3 % -> MEDIA; menos -> BAJA
    max_recommendations: int = 5
    target_tolerance: Decimal = Decimal("0.05")     # ≥ 95 % de la meta = 'cerca'; menos = 'debajo'
    # accionabilidad: lo que se puede corregir directamente pesa más que lo que solo pide investigar
    actionability: tuple = (("abasto", Decimal("1.5")), ("disponibilidad", Decimal("1.5")), ("proteger", Decimal("1.0")),
                            ("meta", Decimal("1.2")), ("investigar", Decimal("0.7")), ("validar", Decimal("0.7")), ("mezcla", Decimal("0.7")),
                            ("vigilar", Decimal("0.5")))

    def weight(self, kind: str) -> Decimal:
        return dict(self.actionability).get(kind, Decimal("1"))


RULES = NarrativeRules()
