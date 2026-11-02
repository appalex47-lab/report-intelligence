"""Tablas AETOPS: panorama, canales y líneas (YoY/MoM).

Todo se calcula aquí a partir de los valores crudos (Monto, Piezas, Pacientes,
Pedidos, Productos). Lo que el Excel trae pegado (Ticket, Size B, Share, %Δ) NO se
usa como fuente: se recalcula y se contrasta en el validador.
"""
from __future__ import annotations

from ..importer.base_sheet import RawBase, RawGroup, RawRow, RawSection
from ..models import Group, Lineage, PeriodRow, Table, Value
from . import indicators as ind

BASE_METRICS = ("monto", "piezas", "pacientes", "pedidos", "productos")
PCT_METRICS = BASE_METRICS + ("ticket", "size_b", "v_paciente", "share")


def _lineage(file: str, raw) -> Lineage:
    return Lineage(file, "Base", raw[1].split("!", 1)[1], "pasted")


def _row(file: str, raw_row: RawRow, ticket_pasted: bool = False) -> PeriodRow:
    vals: dict[str, Value] = {}
    for key in BASE_METRICS:
        raw = raw_row.cells.get(key)
        vals[key] = ind.make(raw[0], _lineage(file, raw)) if raw else ind.make(None)
    if ticket_pasted and raw_row.cells.get("ticket"):
        raw = raw_row.cells["ticket"]
        v = ind.make(raw[0], _lineage(file, raw))
        vals["ticket"] = Value(v.v, v.status, v.src, "pegado del Excel; fórmula pendiente de validación")
    else:
        vals["ticket"] = ind.ratio(vals["monto"], vals["pedidos"], "monto/pedidos")
    vals["size_b"] = ind.ratio(vals["piezas"], vals["pacientes"], "piezas/pacientes")
    vals["v_paciente"] = ind.ratio(vals["monto"], vals["pacientes"], "monto/pacientes")
    return PeriodRow(raw_row.label, vals)


def _group(file: str, g: RawGroup, ticket_pasted: bool = False) -> Group | None:
    if len(g.periods) != 2:
        return None
    return Group(g.name, _row(file, g.periods[0], ticket_pasted), _row(file, g.periods[1], ticket_pasted))


def build_tables(raw: RawBase, ticket_source: dict[str, str] | None = None) -> dict[str, Table]:
    """Devuelve {clave: Table}. Las secciones se identifican por (kind, marker)."""
    ticket_source = ticket_source or {}
    tables: dict[str, Table] = {}
    for sec in raw.sections:
        if sec.kind not in ("panorama", "canal", "linea"):
            continue
        pasted = ticket_source.get(sec.kind) == "pasted"
        groups = [g for g in (_group(raw.file, x, pasted) for x in sec.groups) if g]
        key = f"aetops.{sec.kind}.{sec.marker.lower()}"
        if key in tables:       # sección repetida: se conserva la primera y se avisa en validador
            continue
        tables[key] = Table(key, "YoY" if sec.marker.lower() == "yoy" else "MoM", groups)

    # %Δ y Share (el share usa como denominador el TOTAL del panorama del mismo periodo)
    for sec_marker in ("yoy", "mom"):
        pano = tables.get(f"aetops.panorama.{sec_marker}")
        total = pano.groups[0] if pano and pano.groups else None
        for kind in ("panorama", "canal", "linea"):
            t = tables.get(f"aetops.{kind}.{sec_marker}")
            if not t:
                continue
            for g in t.groups:
                for side in (g.previous, g.current):
                    denom_row = None
                    if total is not None:
                        denom_row = total.previous if side is g.previous else total.current
                    side.values["share"] = (
                        ind.share(side.values["monto"], denom_row.values["monto"], "monto/total")
                        if denom_row else ind.make(None)
                    )
                g.pct = {
                    k: ind.pct_change(g.current.values[k], g.previous.values[k], k)
                    for k in PCT_METRICS
                }
    return tables
