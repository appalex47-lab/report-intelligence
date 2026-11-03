"""Relleno de la plantilla AETOPS trimestral (8 diapositivas; referencia: Resultados_AETOP_Q1_2026).

Solo compara contra el mismo trimestre del año anterior (YoY). Las particularidades de esta plantilla frente a la
mensual: panorama de una sola tabla, canales con una fila separadora antes del último bloque, Top de productos sin
columna Sivec, categorías en dos tablas separadas, y la tabla de negados contiene dentro la mini-tabla por línea.
"""
from __future__ import annotations

from decimal import Decimal

from .. import format as F
from ..calc import indicators as ind
from ..models import Group, Period
from ..narrative.aetops import Box, check as check_narrative, compose_aetops_trimestral
from ..narrative.writer import Para, to_paragraphs, verify_edited
from ..pipeline import Result
from . import pptx_ops as ops
from .aetops_mensual import (DataMissing, FillReport, Filler, fill_cat_blocks, fill_grouped_starts, fill_productos,
                             fmt_metric)

NARR = {
    "panorama": (1, "TextBox 17"), "linea_yoy": (2, "CuadroTexto 6"), "canal_yoy": (3, "CuadroTexto 6"),
    "productos": (4, "CuadroTexto 7"), "movers": (5, "CuadroTexto 21"), "cat_yoy": (6, "CuadroTexto 24"),
    "negados": (7, "CuadroTexto 6"), "conclusiones": (8, "CuadroTexto 12"),
}
LINEA_STARTS = [2, 6, 10, 14]
CANAL_STARTS = [2, 6, 10, 14, 19]          # fila 18 = separador antes del último canal


def pick_categories(groups: list[Group]) -> tuple[list[Group], list[Group], list[Group]]:
    """Tabla superior: las 3 que más suman (Δ$); inferior: las 3 que más restan. Selección editorial del original
    sustituida por un criterio explícito en pesos (evita ranking por % sobre bases mínimas)."""
    def delta(g):
        a, b = g.previous.values["monto"].v, g.current.values["monto"].v
        return (b - a) if a is not None and b is not None else None
    ok = [(g, delta(g)) for g in groups if delta(g) is not None]
    up = [g for g, d in sorted(ok, key=lambda t: t[1], reverse=True) if d > 0][:3]
    down = [g for g, d in sorted(ok, key=lambda t: t[1]) if d < 0][:3]
    shown = {id(g) for g in up + down}
    return up, down, [g for g in groups if id(g) not in shown]


def fill_panorama_single(fl: Filler, n: int, yoy: Group):
    w = fl.table(n, "Tabla 3", rows=5, cols=9)
    keys = ["monto", "piezas", "pacientes", "pedidos", "ticket", "productos", "size_b", "v_paciente"]
    for off, side in ((2, yoy.previous), (3, yoy.current)):
        w.put(off, 0, side.label)
        for c, k in enumerate(keys, 1):
            w.put(off, c, fmt_metric(k, side.values[k]))
    for c, k in enumerate(keys, 1):
        w.delta(4, c, yoy.pct[k])
    w.finish()


def fill_negados_q(fl: Filler, n: int, alta, producto, rep: FillReport):
    w = fl.table(n, "Tabla 2", rows=20, cols=6)
    allp = producto.rows if producto else []
    arows = sorted(alta.rows, key=lambda r: r.monto.v or Decimal(0), reverse=True) if alta else []
    prows = sorted(allp, key=lambda r: r.monto.v or Decimal(0), reverse=True)[:10]
    # de abajo hacia arriba (así los índices de lo ya escrito no se mueven)
    for i, r in enumerate(arows[:4]):                                   # mini-tabla por línea: filas 16-19
        w.put(16 + i, 1, r.name)
        w.put(16 + i, 2, F.fmt_num(r.pedidos, 0))
        w.put(16 + i, 3, F.fmt_num(r.cantidad, 0))
        w.put(16 + i, 4, F.fmt_money(r.monto, 0))
        w.put(16 + i, 5, F.fmt_pct(r.share, 0, sign=False))
    if len(arows) > 4:
        rep.notes.append(f"Diap. {n}: {len(arows)} líneas de negados y la plantilla admite 4.")
    total = alta.total if alta else (producto.total if producto else ind.make(None))
    w.put(13, 3, F.fmt_money(total, 0), fill=None)                      # 'Monto negado' | total (sin mapa de calor)
    src = arows or allp
    sp = sum((r.pedidos.v for r in src if r.pedidos.v is not None), Decimal(0))
    sc = sum((r.cantidad.v for r in src if r.cantidad.v is not None), Decimal(0))
    w.put(11, 2, F.fmt_num(ind.derived(sp, "sum(pedidos)"), 0), fill=None)
    w.put(11, 3, F.fmt_num(ind.derived(sc, "sum(cantidad)"), 0), fill=None)
    for i, r in enumerate(prows, 1):
        w.put(i, 0, r.name)
        w.put(i, 1, r.alta)
        w.put(i, 2, F.fmt_num(r.pedidos, 0), fill=None)
        w.put(i, 3, F.fmt_num(r.cantidad, 0), fill=None)
        w.put(i, 4, F.fmt_money(r.monto, 0), fill=None)
        w.put(i, 5, F.fmt_pct(r.share, 0, sign=False), fill=None)
    drop_alta = range(16 + max(len(arows), 1), 20) if len(arows) < 4 else range(0)
    drop_prod = range(1 + max(len(prows), 1), 11) if len(prows) < 10 else range(0)
    w.skip_rows.update(drop_alta)
    w.skip_rows.update(drop_prod)
    w.check_stale()
    if len(arows) < 4:                                                  # líneas sin datos: se eliminan sus filas
        ops.delete_rows(w.t, 16 + max(len(arows), 1), 20)
    if len(prows) < 10:
        ops.delete_rows(w.t, 1 + max(len(prows), 1), 11)
    ops.sync_frame_height(w.shape)


def fill_aetops_trimestral(prs, result: Result, period: Period, narrative: dict[str, list[str]] | None = None,
                           fix_titles: bool = True, att=None) -> FillReport:
    if period.periodicity != "trimestral":
        raise ValueError("La plantilla trimestral requiere un periodo trimestral.")
    rep = FillReport()
    fl = Filler(prs, rep)
    T = result.tables

    def tab(key):
        if key not in T:
            raise DataMissing(f"Falta la tabla '{key}' en el resultado del motor.")
        return T[key]

    yoy = tab("aetops.panorama.yoy").groups[0]
    linea, canal, cat = tab("aetops.linea.yoy"), tab("aetops.canal.yoy"), tab("aetops.categoria.yoy")
    prod = result.products
    for k in ("top", "growth", "decline"):
        if f"aetops.productos.{k}" not in prod:
            raise DataMissing(f"Falta el bloque de productos '{k}'.")
    neg_alta, neg_prod = result.negados.get("aetops.negados.alta"), result.negados.get("aetops.negados.producto")

    # --- narrativa
    boxes = {k: Box(*ops.narrative_box(fl.shape(n, name))) for k, (n, name) in NARR.items()}
    up, down, omitted = pick_categories(cat.groups)
    narr = compose_aetops_trimestral(result, period, boxes, up + down, att=att)
    rep.narrative_problems = check_narrative(narr)
    rep.narrative = narr
    for key, texts in (narrative or {}).items():
        allowed = set().union(*(p.nums for ps in narr.values() for p in ps))
        edited = [Para(t, "hecho", 0, edited=True, nums=set()) for t in texts if t != ""]
        rep.edited_unverified += [f"{key}: {x}" for p in edited for x in verify_edited(p.plain, allowed)]
        narr[key] = edited + [p for p in narr.get(key, []) if not p.visible]

    # --- tablas
    fill_panorama_single(fl, 1, yoy)
    fill_grouped_starts(fl, 2, "Tabla 8", linea, LINEA_STARTS, rows=18)
    fill_grouped_starts(fl, 3, "Tabla 7", canal, CANAL_STARTS, rows=23)
    q = period.index
    heads = {3: f"Venta Q{q} Actual {period.year}", 4: f"Venta Q{q} Año {period.year - 1}"}
    fill_productos(fl, 4, "Tabla 2", prod["aetops.productos.top"].rows, 20, rep, sivec=False,
                   headers={3: heads[3], 4: heads[4]})
    fill_productos(fl, 5, "Tabla 3", prod["aetops.productos.growth"].rows, 10, rep, sivec=False,
                   headers={3: heads[3], 4: heads[4]})
    fill_productos(fl, 5, "Tabla 8", prod["aetops.productos.decline"].rows, 10, rep, sivec=False,
                   headers={3: heads[3], 4: heads[4]})
    pad = lambda lst, k: lst + [None] * (k - len(lst))                   # noqa: E731
    fill_cat_blocks(fl, 6, "Tabla 2", [(2, pad(up, 3), 0)], rows=11)
    fill_cat_blocks(fl, 6, "Tabla 7", [(1, pad(down, 3), 0)], rows=10, has_title=False)
    rep.omitted_categories += [g.name for g in omitted]
    fill_negados_q(fl, 7, neg_alta, neg_prod, rep)
    for key, (n, name) in NARR.items():
        ops.set_paragraphs(fl.shape(n, name), to_paragraphs(narr[key]))
    if rep.omitted_categories:
        rep.notes.append("Categorías no mostradas por capacidad de la plantilla (6): " + ", ".join(rep.omitted_categories))
    return rep
