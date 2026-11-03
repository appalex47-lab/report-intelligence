"""Reglas 4b: comparativos exigidos, periodo esperado, productos y negados."""
from __future__ import annotations

from decimal import Decimal

from ..importer.base_sheet import RawBase
from ..importer.profile import Profile, norm
from ..models import Finding, NegadosTable, Period, ProductTable, Table

PASTED_TOL = Decimal("0.5")      # pesos de diferencia tolerados en deltas pegados


def _rounding_tol(pasted: Decimal) -> Decimal:
    """Un valor pegado con n decimales puede diferir hasta 0.5·10^-n del exacto."""
    exp = -pasted.normalize().as_tuple().exponent if pasted != 0 else 0
    return max(Decimal("0.000001"), Decimal("0.5") * Decimal(10) ** -max(exp, 0) + Decimal("0.000001"))


def required_comparisons(raw: RawBase, profile: Profile) -> list[Finding]:
    """El formato exige ciertos comparativos (mensual: YoY+MoM; trimestral: YoY)."""
    present = {(s.kind, s.marker.lower()) for s in raw.sections}
    out = []
    for kind in ("panorama", "canal", "linea", "categoria"):
        for marker in profile.comparisons:
            if (kind, marker) not in present:
                out.append(Finding(
                    "MISSING_COMPARISON", "block",
                    f"Falta la sección {kind}/{marker.upper()} que exige el formato "
                    f"'{profile.name}'. No se generan comparativos incompletos.", "Base"))
    return out


def expected_period(tables: dict[str, Table], negados: dict[str, NegadosTable],
                    period: Period) -> list[Finding]:
    out: list[Finding] = []
    seen: set[tuple] = set()
    for key, t in tables.items():
        for g in t.groups:
            pair = (key, g.previous.label, g.current.label)
            if pair in seen:
                continue
            seen.add(pair)
            prev, cur = norm(g.previous.label), norm(g.current.label)
            if t.comparison == "YoY":
                exp = (str(period.year - 1), str(period.year))
            else:
                exp = (period.previous_month_name, period.month_name)
            if (prev, cur) != exp:
                out.append(Finding(
                    "PERIOD_MISMATCH", "block",
                    f"{key} / {g.name}: el Excel compara '{g.previous.label}'→'{g.current.label}' "
                    f"pero el reporte es {period.month_name if period.periodicity == 'mensual' else 'Q' + str(period.index)} "
                    f"{period.year} (esperado '{exp[0]}'→'{exp[1]}').", key))
    any_label = any(norm(n.label) for n in negados.values())
    for key, nt in negados.items():
        lab = norm(nt.label)
        ok = (period.month_name in lab) if period.periodicity == "mensual" else (f"q{period.index}" in lab)
        if lab and not ok:
            out.append(Finding(
                "PERIOD_MISMATCH", "block",
                f"{key}: la hoja Negados está rotulada '{nt.label}' y no corresponde al periodo "
                f"{period.month_name if period.periodicity == 'mensual' else 'Q' + str(period.index)} "
                f"{period.year}.", key))
        elif not lab and not any_label:      # basta con que algún bloque declare el periodo
            out.append(Finding("PERIOD_UNLABELED", "warn",
                               f"{key}: la hoja Negados no declara periodo.", key))
    return out


def products(prod: dict[str, ProductTable]) -> list[Finding]:
    out: list[Finding] = []
    for key, t in prod.items():
        seen: set[str] = set()
        for r in t.rows:
            if r.sivec in seen:
                out.append(Finding("DUPLICATE_KEY", "warn",
                                   f"{key}: Sivec {r.sivec} repetido ({r.producto}).", key))
            seen.add(r.sivec)
        # orden esperado según el rol del bloque
        sortkey = {"top": ("actual", True), "growth": ("delta", True), "decline": ("delta", False)}.get(t.role)
        if sortkey:
            attr, desc = sortkey
            vals = [getattr(r, attr).v for r in t.rows if getattr(r, attr).v is not None]
            if vals != sorted(vals, reverse=desc):
                out.append(Finding("SORT_ORDER", "warn",
                                   f"{key}: filas no ordenadas por {attr} "
                                   f"({'desc' if desc else 'asc'}).", key))
        masked = 0
        for r in t.rows:
            if r.anterior.v is None and r.pasted_delta.v == 0 and r.actual.v:
                masked += 1                     # #N/A + IFERROR(...,0) en el Excel
            elif r.delta.v is not None and r.pasted_delta.v is not None and r.anterior.v is not None:
                if abs(r.delta.v - r.pasted_delta.v) > PASTED_TOL:
                    out.append(Finding(
                        "PASTED_DIFFERS", "warn",
                        f"{key} / {r.producto[:30]}: Delta Excel {r.pasted_delta.v} vs motor {r.delta.v}.",
                        r.pasted_delta.src.cells if r.pasted_delta.src else ""))
        if masked:
            out.append(Finding(
                "FORMULA_MASKS_MISSING", "info",
                f"{key}: {masked} producto(s) sin venta previa (#N/A) con Delta=0 en el Excel "
                "(IFERROR→0). El motor los marca 'nuevo' con Delta = venta actual; "
                "política configurable.", key))
    return out


def negados(neg: dict[str, NegadosTable]) -> list[Finding]:
    out: list[Finding] = []
    alta, pasted = neg.get("aetops.negados.alta"), neg.get("aetops.negados.alta_excel")
    prod = neg.get("aetops.negados.producto")
    if pasted and alta and alta.total.v and pasted.total.v:
        diff = abs(pasted.total.v - alta.total.v) / alta.total.v
        if diff > Decimal("0.005"):
            out.append(Finding(
                "NEGADOS_ALTA_DIFFERS", "warn",
                f"Negados: la tabla por línea del Excel suma {pasted.total.v:,.0f} y la suma de la lista de "
                f"productos es {alta.total.v:,.0f} (dif. {diff:.0%}). Se usa la lista de productos (el detalle); "
                "confirmar con quien arma el Excel cuál es el periodo/filtro de la tabla por línea.", "aetops.negados"))
    for key, t in neg.items():
        if key.endswith("_excel"):
            continue
        bad = [r for r in t.rows if r.share.v is not None and r.pasted_share.v is not None
               and abs(r.share.v - r.pasted_share.v) > _rounding_tol(r.pasted_share.v)]
        if bad:
            out.append(Finding(
                "PASTED_DIFFERS", "warn",
                f"{key}: {len(bad)} share(s) pegados no coinciden con monto ÷ total "
                f"(p. ej. {bad[0].name[:28]}).", key))
    return out
