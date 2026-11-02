"""Validación de metas: obligatorias en AETOPS (total + todas las líneas), opcionales en GLP-1."""
from __future__ import annotations

from decimal import Decimal

from ..models import Finding
from ..targets import Targets


def validate_targets(result, targets: Targets | None, required: bool) -> list[Finding]:
    out: list[Finding] = []
    lines = [g.name for g in result.tables["aetops.linea.yoy"].groups] if "aetops.linea.yoy" in result.tables else []
    if targets is None or (targets.total is None and not targets.by_group):
        if required:
            out.append(Finding("TARGETS_MISSING", "block",
                               "Faltan las metas del periodo: capturar la meta total y la de cada línea antes de generar.",
                               "metas"))
        return out
    if targets.total is None:
        if required:
            out.append(Finding("TARGETS_MISSING", "block", "Falta la meta total del periodo.", "metas"))
    elif targets.total <= 0:
        out.append(Finding("TARGET_NONPOSITIVE", "block", "La meta total debe ser mayor que cero.", "metas"))
    if required:
        for ln in lines:
            if ln not in targets.by_group:
                out.append(Finding("TARGET_LINE_MISSING", "block", f"Falta la meta de la línea {ln}.", "metas"))
    for k, v in targets.by_group.items():
        if v <= 0:
            out.append(Finding("TARGET_NONPOSITIVE", "block", f"La meta de {k} debe ser mayor que cero.", "metas"))
        if lines and k not in lines:
            out.append(Finding("TARGET_GROUP_UNKNOWN", "warn", f"Hay meta para '{k}', que no está en el Excel.", "metas"))
    if targets.total and targets.by_group and required:
        s = sum(targets.by_group.values(), Decimal(0))
        if abs(s - targets.total) / targets.total > Decimal("0.005"):
            out.append(Finding("TARGETS_SUM_MISMATCH", "warn",
                               f"Las metas por línea suman {s:,.0f} y la meta total es {targets.total:,.0f}.", "metas"))
    return out
