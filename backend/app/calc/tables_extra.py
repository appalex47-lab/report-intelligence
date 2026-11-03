"""Productos (Top / crecimiento / decrecimiento) y Negados (por producto y por línea)."""
from __future__ import annotations

from decimal import Decimal

from ..importer.sheets import RawBlock
from ..models import Lineage, NegadoRow, NegadosTable, ProductRow, ProductTable, Value
from . import indicators as ind


def _v(cell, file: str, sheet: str) -> Value:
    if not cell:
        return ind.make(None)
    raw, coord = cell
    return ind.make(raw, Lineage(file, sheet, coord.split("!", 1)[1], "pasted"))


def _s(cell) -> str:
    if not cell or cell[0] is None:
        return ""
    v = cell[0]
    return str(int(v)) if isinstance(v, float) and v.is_integer() else str(v).strip()


def build_products(blocks: list[RawBlock], file: str, sheet: str) -> dict[str, ProductTable]:
    out: dict[str, ProductTable] = {}
    for b in blocks:
        rows = []
        for r in b.rows:
            actual, ant = _v(r.get("actual"), file, sheet), _v(r.get("anterior"), file, sheet)
            rows.append(ProductRow(
                sivec=_s(r.get("sivec")), producto=_s(r.get("producto")), aetop=_s(r.get("aetop")),
                canales=_v(r.get("canales"), file, sheet), actual=actual, anterior=ant,
                delta=ind.delta_abs(actual, ant, "actual-anterior"),
                pasted_delta=_v(r.get("delta"), file, sheet)))
        out[f"aetops.productos.{b.role}"] = ProductTable(f"aetops.productos.{b.role}", b.role, rows)
    return out


def build_negados(blocks: list[RawBlock], file: str, sheet: str) -> dict[str, NegadosTable]:
    out: dict[str, NegadosTable] = {}
    for b in blocks:
        if f"aetops.negados.{b.role}" in out:      # bloque duplicado: se conserva el primero
            continue
        rows = []
        for r in b.rows:
            rows.append(NegadoRow(
                name=_s(r.get("_name")), alta=_s(r.get("alta")) if b.role == "producto" else _s(r.get("_name")),
                pedidos=_v(r.get("pedidos"), file, sheet), cantidad=_v(r.get("cantidad"), file, sheet),
                monto=_v(r.get("monto"), file, sheet), share=ind.make(None),
                pasted_share=_v(r.get("share"), file, sheet)))
        total_d = sum((x.monto.v for x in rows if x.monto.v is not None), Decimal(0))
        total = ind.derived(total_d, "sum(monto)") if rows else ind.derived(None, "sum(monto)")
        for x in rows:
            x.share = ind.share(x.monto, total, "monto/total negado")
        out[f"aetops.negados.{b.role}"] = NegadosTable(f"aetops.negados.{b.role}", b.label, rows, total)
    return out


def derive_alta(producto: NegadosTable, pasted: NegadosTable | None) -> NegadosTable:
    """La tabla por línea ('Alta') sale de sumar la lista de productos (el detalle manda); lo pegado en el Excel
    solo se contrasta. Así el total de negados es único y trazable."""
    acc: dict[str, list[Decimal]] = {}
    order: list[str] = []
    for r in producto.rows:
        if not r.alta:
            continue
        a = acc.setdefault(r.alta, [Decimal(0), Decimal(0), Decimal(0)])
        if r.alta not in order:
            order.append(r.alta)
        for i, v in enumerate((r.pedidos.v, r.cantidad.v, r.monto.v)):
            if v is not None:
                a[i] += v
    total = sum((v[2] for v in acc.values()), Decimal(0))
    tot = ind.derived(total, "sum(monto por Alta)")
    old = {r.name: r for r in (pasted.rows if pasted else [])}
    rows = []
    for name in sorted(order, key=lambda k: -acc[k][2]):
        ped, cant, monto = acc[name]
        row = NegadoRow(name=name, alta=name, pedidos=ind.derived(ped, "sum(pedidos)"),
                        cantidad=ind.derived(cant, "sum(cantidad)"), monto=ind.derived(monto, "sum(monto)"),
                        share=ind.make(None), pasted_share=old[name].pasted_share if name in old else ind.make(None))
        row.share = ind.share(row.monto, tot, "monto/total negado")
        rows.append(row)
    return NegadosTable("aetops.negados.alta", pasted.label if pasted else producto.label, rows, tot)
