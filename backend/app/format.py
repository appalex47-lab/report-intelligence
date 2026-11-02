"""Formato de presentación. Único lugar donde se redondea (prompt maestro §6).

Excel y los PPTX de referencia redondean la mitad HACIA ARRIBA (0.625 -> 63 %);
el `round()` de Python redondea al par (0.625 -> 62 %), por eso no se usa.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from .models import Value

DASH = "—"


def quantize_half_up(v: Decimal, decimals: int) -> Decimal:
    return v.quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)


def fmt_pct(v: Value, decimals: int = 0, sign: bool = True) -> str:
    if v.v is None:
        return DASH
    q = quantize_half_up(v.v * 100, decimals)
    s = f"{q:,.{decimals}f}%"
    return ("+" + s) if sign and q > 0 else s


def fmt_money(v: Value, decimals: int = 0) -> str:
    if v.v is None:
        return DASH
    q = quantize_half_up(v.v, decimals)
    return ("-$" if q < 0 else "$") + f"{abs(q):,.{decimals}f}"


def fmt_num(v: Value, decimals: int = 0) -> str:
    if v.v is None:
        return DASH
    return f"{quantize_half_up(v.v, decimals):,.{decimals}f}"
