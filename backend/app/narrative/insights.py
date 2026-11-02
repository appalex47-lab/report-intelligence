"""Insights deterministas: aritmética verificable sobre tablas ya validadas. Sin texto, sin causas."""
from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal

from ..models import Group, PeriodRow
from .rules import RULES, NarrativeRules

ZERO = Decimal(0)


def _v(row: PeriodRow, key: str) -> Decimal | None:
    x = row.values.get(key)
    return x.v if x is not None else None


# --------------------------------------------------------------------------- descomposición
@dataclass(frozen=True)
class Decomposition:
    total_pct: float                       # cambio de venta (fracción)
    shares: dict[str, float]               # aporte de cada factor al cambio (suma 1)
    volume: float                          # pacientes + piezas por paciente
    price: float                           # venta por pieza


def decompose_sales(prev: PeriodRow, cur: PeriodRow, rules: NarrativeRules = RULES) -> Decomposition | None:
    """Venta = Pacientes × (Piezas/Paciente) × (Venta/Pieza). Aporte de cada factor = ln(f₁/f₀) ÷ ln(V₁/V₀).
    Es una identidad aritmética (no un modelo): los aportes suman 100 %."""
    keys = ("monto", "piezas", "pacientes")
    p = [_v(prev, k) for k in keys]
    c = [_v(cur, k) for k in keys]
    if any(x is None or x <= 0 for x in p + c):
        return None
    m0, q0, a0 = (float(x) for x in p)
    m1, q1, a1 = (float(x) for x in c)
    total = math.log(m1 / m0)
    if abs(total) < rules.min_total_change:
        return None
    parts = {"pacientes": math.log(a1 / a0),
             "piezas_por_paciente": math.log((q1 / a1) / (q0 / a0)),
             "precio_por_pieza": math.log((m1 / q1) / (m0 / q0))}
    shares = {k: v / total for k, v in parts.items()}
    return Decomposition(m1 / m0 - 1, shares, shares["pacientes"] + shares["piezas_por_paciente"],
                         shares["precio_por_pieza"])


# --------------------------------------------------------------------------- aportes por grupo
@dataclass(frozen=True)
class Contribution:
    group: Group
    delta: Decimal                        # Δ$ del grupo
    share_of_change: Decimal | None       # Δ grupo ÷ Δ total (solo si ambos > 0)
    pct: Decimal | None                   # %Δ de venta del grupo
    share_prev: Decimal | None
    share_cur: Decimal | None
    pp: Decimal | None                    # cambio de participación (fracción: 0.03 = 3 pp)


def contributions(groups: list[Group], total_prev: Decimal | None, total_cur: Decimal | None) -> list[Contribution]:
    net = (total_cur - total_prev) if total_prev is not None and total_cur is not None else None
    out = []
    for g in groups:
        m0, m1 = _v(g.previous, "monto"), _v(g.current, "monto")
        if m0 is None or m1 is None:
            continue
        d = m1 - m0
        sc = d / net if net and net > 0 and d > 0 else None
        s0, s1 = _v(g.previous, "share"), _v(g.current, "share")
        out.append(Contribution(g, d, sc, g.pct["monto"].v, s0, s1,
                                (s1 - s0) if s0 is not None and s1 is not None else None))
    return out


def flags(c: Contribution, total_pct: Decimal | None, pedidos_ok: bool = True,
          rules: NarrativeRules = RULES) -> set[str]:
    """Patrones que el analista menciona a mano; cada uno es una regla explícita sobre los datos."""
    f: set[str] = set()
    g = c.group
    pa, pz = g.pct["pacientes"].v, g.pct["piezas"].v
    if c.pct is not None and c.pct > 0 and pa is not None and pa < 0:
        f.add("valor_sobre_volumen")                       # venta ↑ con pacientes ↓
    if c.pct is not None and c.pct < 0 and pz is not None and pz >= 0:
        f.add("caida_por_mezcla")                          # venta ↓ con piezas ≥ 0
    if (c.pct is not None and c.pct > rules.small_base_growth
            and c.share_prev is not None and c.share_prev < rules.small_base_share):
        f.add("base_pequena")
    if c.pp is not None and abs(c.pp) >= rules.share_pp:
        f.add("gana_share" if c.pp > 0 else "pierde_share")
    if (c.pct is not None and c.pct > 0 and total_pct is not None and total_pct > 0 and c.pct < total_pct
            and c.pp is not None and c.pp < 0):
        f.add("crece_menos_que_total")                     # crece, pero menos que el total => pierde share
    return f


# --------------------------------------------------------------------------- productos
def net_by_line(rows) -> dict[str, Decimal]:
    out: dict[str, Decimal] = {}
    for r in rows:
        if r.delta.v is not None:
            out[r.aetop] = out.get(r.aetop, ZERO) + r.delta.v
    return out


def concentration(rows, total: Decimal | None, n: int) -> tuple[Decimal, Decimal] | None:
    """(participación del líder, participación de los N primeros) sobre la venta total."""
    vals = sorted((r.actual.v for r in rows if r.actual.v is not None), reverse=True)
    if not vals or not total or total <= 0:
        return None
    return vals[0] / total, sum(vals[:n], ZERO) / total


def mixed_lines(growth, decline) -> list[str]:
    g, d = {r.aetop for r in growth}, {r.aetop for r in decline}
    return sorted(g & d)
