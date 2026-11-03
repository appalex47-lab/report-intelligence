"""Cálculo GLP-1: Value con trazabilidad, Share y %Δ recalculados por el motor."""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from ..importer.glp1_blocks import RawGlp1
from ..importer.profile import GProfile, norm
from ..models import GBlock, GRow, Lineage, Value
from . import indicators as ind

SHARE_BASIS = {"traffic": "visitas", "money": "monto", "negados": "monto_negado"}


def _lin(file: str, coord: str, transform: str = "pasted") -> Lineage:
    sheet, cell = coord.split("!", 1)
    return Lineage(file, sheet, cell, transform)


def seconds(raw) -> Decimal | None:
    """hh:mm:ss (texto, time o timedelta) -> segundos. Cualquier otra cosa -> None."""
    if isinstance(raw, dt.time):
        return Decimal(raw.hour * 3600 + raw.minute * 60 + raw.second)
    if isinstance(raw, dt.timedelta):
        return Decimal(int(raw.total_seconds()))
    if isinstance(raw, str):
        parts = raw.strip().split(":")
        if len(parts) == 3 and all(p.isdigit() for p in parts):
            h, m, s = map(int, parts)
            return Decimal(h * 3600 + m * 60 + s)
    return None


def _val(file: str, cell, metric: str) -> Value:
    if not cell:
        return ind.make(None)
    raw, coord = cell
    if metric == "tiempo":
        return ind.make(seconds(raw), _lin(file, coord, "hms->segundos"))
    return ind.make(raw, _lin(file, coord))


def _key(cell) -> str:
    raw = cell[0]
    if isinstance(raw, float) and raw.is_integer():
        raw = int(raw)
    return str(raw).strip()


def build_glp1(raw: RawGlp1, profile: GProfile) -> tuple[dict[str, GBlock], GBlock | None]:
    blocks: dict[str, GBlock] = {}
    for name, rb in raw.blocks.items():
        rows = []
        for r in rb.rows:
            vals = {m: _val(raw.file, c, m) for m, c in r.items() if not m.startswith("_")}
            row = GRow(_key(r["_key"]), _key(r["_dim2"]) if "_dim2" in r else "", vals)
            money = "monto_negado" if "monto_negado" in vals else "monto"
            if "pedidos" in vals and money in vals:
                row.ticket_calc = ind.ratio(vals[money], vals["pedidos"], f"{money}/pedidos")
                pasted = vals.get("ticket")
                row.pasted_ticket = pasted
                if profile.ticket_source == "ratio" or pasted is None or pasted.is_missing:
                    vals["ticket"] = row.ticket_calc
                # con 'pasted' se conserva el valor del Excel (el validador lo contrasta)
            row.pasted_delta = vals.get("delta")
            rows.append(row)
        gb = GBlock(name, rb.sheet, rb.origin, rows, basis=rb.basis, role=rb.role)
        gb.declared_total = {m: _val(raw.file, c, m) for m, c in rb.declared_total.items()}
        # Share = base ÷ Σ del bloque (denominador = total del periodo)
        key = SHARE_BASIS.get(rb.basis)
        if key and rows:
            tot = sum((x.values[key].v for x in rows if key in x.values and x.values[key].v is not None), Decimal(0))
            total = ind.derived(tot, f"sum({key})")
            for x in rows:
                x.share = ind.share(x.values.get(key, ind.make(None)), total, f"{key}/total")
        blocks[name] = gb

    # %Δ: contra el bloque anterior del Excel (unión por nombre normalizado); si no existe, el pegado
    for name, rb in raw.blocks.items():
        gb = blocks[name]
        spec = rb.prior
        prior = blocks.get(spec["block"]) if spec else None
        pmap = {norm(r.key): r for r in prior.rows} if prior else {}
        for x in gb.rows:
            if prior is not None:
                p = pmap.get(norm(x.key))
                if p is not None and spec["metric"] in x.values and spec["metric"] in p.values:
                    x.engine_delta = ind.pct_change(x.values[spec["metric"]], p.values[spec["metric"]],
                                                    f"{spec['metric']} vs anterior")
            pasted_ok = x.pasted_delta is not None and not x.pasted_delta.is_missing
            if profile.delta_source == "engine" and x.engine_delta is not None:
                x.delta, x.delta_src = x.engine_delta, "engine"
            elif pasted_ok:
                x.delta, x.delta_src = x.pasted_delta, "pasted"
            elif x.engine_delta is not None:             # sin pegado, el motor lo calcula
                x.delta, x.delta_src = x.engine_delta, "engine"
            else:
                x.delta, x.delta_src = ind.make(None), "none"

    # embudo: tasa recalculada = conteo ÷ 'Ver producto'
    fb = None
    if raw.funnel:
        rows = []
        base = None
        for f in raw.funnel:
            cnt = _val(raw.file, f["count"], "conteo")
            if base is None:
                base = cnt
            row = GRow(f["stage"], "", {"tasa": _val(raw.file, f["rate"], "tasa"), "conteo": cnt})
            row.values["tasa_calc"] = ind.ratio(cnt, base, "conteo/ver_producto")
            rows.append(row)
        fb = GBlock("embudo", "5", "5!A", rows, basis="funnel")
    return blocks, fb
