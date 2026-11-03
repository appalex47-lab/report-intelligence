"""Indicadores: funciones puras y deterministas. Una sola implementación por fórmula.

Reglas (prompt maestro §6): sin división entre cero, el faltante NO es cero,
precisión Decimal interna, el redondeo solo ocurre al presentar.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from ..models import Lineage, Value


def to_dec(raw) -> Decimal | None:
    """Convierte una celda a Decimal. Vacío / texto / error -> None (faltante)."""
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, Decimal):
        return raw
    if isinstance(raw, (int, float)):
        try:
            return Decimal(str(raw))
        except InvalidOperation:
            return None
    if isinstance(raw, str):
        s = raw.strip().replace(",", "").replace("$", "")
        if not s:
            return None
        try:
            return Decimal(s)
        except InvalidOperation:
            return None
    return None


def make(raw, src: Lineage | None = None) -> Value:
    d = to_dec(raw)
    if d is None:
        return Value(None, "missing", src)
    return Value(d, "zero" if d == 0 else "ok", src)


def derived(d: Decimal | None, transform: str, note: str = "") -> Value:
    src = Lineage("", "", "", transform)
    if d is None:
        return Value(None, "missing", src, note)
    return Value(d, "zero" if d == 0 else "ok", src, note)


def ratio(num: Value, den: Value, name: str) -> Value:
    t = f"ratio({name})"
    if num.is_missing or den.is_missing:
        return derived(None, t, "operando faltante")
    if den.v == 0:
        return derived(None, t, "denominador cero")
    return derived(num.v / den.v, t)


def pct_change(actual: Value, previous: Value, name: str) -> Value:
    """(Actual − Anterior) ÷ Anterior. Anterior faltante o 0 -> faltante (no 0)."""
    t = f"pct_change({name})"
    if actual.is_missing or previous.is_missing:
        return derived(None, t, "operando faltante")
    if previous.v == 0:
        return derived(None, t, "base cero")
    return derived((actual.v - previous.v) / previous.v, t)


def delta_abs(actual: Value, previous: Value, name: str) -> Value:
    """Actual − Anterior. Sin venta previa -> monto completo con bandera new_item."""
    t = f"delta({name})"
    if actual.is_missing:
        return derived(None, t, "actual faltante")
    if previous.is_missing:
        return Value(actual.v, "new_item", Lineage("", "", "", t), "sin periodo previo")
    return derived(actual.v - previous.v, t)


def share(part: Value, total: Value, name: str) -> Value:
    return ratio(part, total, f"share({name})")
