"""AETOPS desde datos crudos (docs/CONTRATO_DATOS.md): agrega `ventas` + `catalogo` (+ `negados`) a las mismas estructuras
que ya consume el resto del sistema (Table/Group, ProductTable, NegadosTable). Validaciones, narrativa, PPTX, QA: sin cambios.

Pacientes y pedidos son conteos de ids DISTINTOS dentro de cada grupo; por eso no suman entre grupos (esperado).
Un faltante de venta en una ventana es cero ventas (no "dato faltante"); %Δ con base cero queda sin valor.
"""
from __future__ import annotations

import csv
import datetime as dt
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

import openpyxl

from ..calc import indicators as ind
from ..calc.tables_extra import derive_alta
from ..models import (MONTHS, Finding, Group, Lineage, NegadoRow, NegadosTable, Period, PeriodRow, ProductRow,
                      ProductTable, Table, Value)

VENTAS_REQ = ["fecha_pedido", "id_pedido", "id_paciente", "paciente_nuevo", "sku", "canal", "estado", "piezas", "monto_venta"]
CATALOGO_REQ = ["sku", "producto", "linea", "categoria"]
NEGADOS_REQ = ["producto", "alta", "pedidos", "cantidad_negada", "monto_negado"]
LINE_ORDER = ["AE-A", "AE-B", "AE-C", "HYR"]
METRICS = ("monto", "piezas", "pacientes", "pedidos", "productos")
PCT_METRICS = METRICS + ("ticket", "size_b", "v_paciente", "share")


def _norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower().strip()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


@dataclass
class RawTables:
    ventas: list[dict] = field(default_factory=list)
    catalogo: list[dict] = field(default_factory=list)
    negados: list[dict] = field(default_factory=list)
    file: str = ""
    findings: list[Finding] = field(default_factory=list)
    has_negados: bool = False


def _rows(header_row, rows_iter, required: list[str], name: str, findings: list[Finding], optional=()) -> list[dict]:
    hdr = [_norm(c) for c in header_row]
    miss = [c for c in required if c not in hdr]
    if miss:
        findings.append(Finding("RAW_COLUMN_MISSING", "block", f"Tabla '{name}': faltan columnas obligatorias: {', '.join(miss)}.", name))
        return []
    out = []
    for i, r in enumerate(rows_iter, 2):
        if r is None or all(c in (None, "") for c in r):
            continue
        d = {h: (r[k] if k < len(r) else None) for k, h in enumerate(hdr) if h}
        d["_row"] = i
        out.append(d)
    return out


def load(path: str | Path) -> RawTables:
    """`.xlsx` con hojas ventas/catalogo/negados, o carpeta con ventas.csv/catalogo.csv/negados.csv."""
    p = Path(path)
    raw = RawTables(file=p.name)
    f = raw.findings
    if p.is_dir():
        def csv_rows(n):
            fp = p / f"{n}.csv"
            if not fp.exists():
                return None
            with fp.open(newline="", encoding="utf-8-sig") as fh:
                rd = csv.reader(fh)
                hdr = next(rd, [])
                return hdr, list(rd)
        for name, req, attr in (("ventas", VENTAS_REQ, "ventas"), ("catalogo", CATALOGO_REQ, "catalogo"), ("negados", NEGADOS_REQ, "negados")):
            got = csv_rows(name)
            if got is None:
                if name != "negados":
                    f.append(Finding("RAW_TABLE_MISSING", "block", f"Falta la tabla '{name}'.", name))
                continue
            setattr(raw, attr, _rows(got[0], got[1], req, name, f))
            raw.has_negados |= name == "negados"
        return raw
    wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
    sheets = {_norm(n): n for n in wb.sheetnames}
    for name, req, attr in (("ventas", VENTAS_REQ, "ventas"), ("catalogo", CATALOGO_REQ, "catalogo"), ("negados", NEGADOS_REQ, "negados")):
        if name not in sheets:
            if name != "negados":
                f.append(Finding("RAW_TABLE_MISSING", "block", f"Falta la hoja '{name}'.", name))
            continue
        it = wb[sheets[name]].iter_rows(values_only=True)
        hdr = next(it, ())
        setattr(raw, attr, _rows(hdr, it, req, name, f))
        raw.has_negados |= name == "negados"
    wb.close()
    return raw


def is_raw_workbook(path: str | Path) -> bool:
    p = Path(path)
    if p.is_dir():
        return (p / "ventas.csv").exists()
    try:
        wb = openpyxl.load_workbook(p, read_only=True)
        ok = "ventas" in {_norm(n) for n in wb.sheetnames}
        wb.close()
        return ok
    except Exception:
        return False


def _date(v):
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    if isinstance(v, (int, float)) and not isinstance(v, bool) and 20000 < v < 80000:     # serial de Excel
        return dt.date(1899, 12, 30) + dt.timedelta(days=int(v))
    if isinstance(v, str):
        s = v.strip()[:10]
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
            try:
                return dt.datetime.strptime(s, fmt).date()
            except ValueError:
                pass
    return None


# ------------------------------------------------------------------------------------------ agregación
def _windows(period: Period):
    y, i = period.year, period.index
    if period.periodicity == "mensual":
        pm, py = (i - 1, y) if i > 1 else (12, y - 1)
        return {"cur": (y, {i}), "yoy": (y - 1, {i}), "mom": (py, {pm})}
    months = {3 * (i - 1) + k for k in (1, 2, 3)}
    return {"cur": (y, months), "yoy": (y - 1, months)}


@dataclass
class _Acc:
    monto: Decimal = Decimal(0)
    piezas: Decimal = Decimal(0)
    pacientes: set = field(default_factory=set)
    pedidos: set = field(default_factory=set)
    skus: set = field(default_factory=set)


def _value(d, tag: str, file: str) -> Value:
    src = Lineage(file, "ventas", "agregado", tag)
    return Value(d, "zero" if d == 0 else "ok", src)


def _period_row(label: str, a: _Acc | None, file: str) -> PeriodRow:
    a = a or _Acc()
    v = {"monto": _value(a.monto, "sum(monto_venta)", file), "piezas": _value(a.piezas, "sum(piezas)", file),
         "pacientes": _value(Decimal(len(a.pacientes)), "distinct(id_paciente)", file),
         "pedidos": _value(Decimal(len(a.pedidos)), "distinct(id_pedido)", file),
         "productos": _value(Decimal(len(a.skus)), "distinct(sku)", file)}
    v["ticket"] = ind.ratio(v["monto"], v["pedidos"], "monto/pedidos")
    v["size_b"] = ind.ratio(v["piezas"], v["pacientes"], "piezas/pacientes")
    v["v_paciente"] = ind.ratio(v["monto"], v["pacientes"], "monto/pacientes")
    return PeriodRow(label, v)


def _order(kind: str, names, cur: dict):
    if kind == "linea":
        return sorted(names, key=lambda n: (LINE_ORDER.index(n) if n in LINE_ORDER else 99, n))
    if kind == "canal":
        return sorted(names)
    return sorted(names, key=lambda n: -(cur.get(n).monto if cur.get(n) else Decimal(0)))


def aggregate(raw: RawTables, period: Period) -> tuple[dict, dict, dict, list[Finding]]:
    """Devuelve (tables, products, negados, findings)."""
    f: list[Finding] = list(raw.findings)
    if any(x.severity == "block" for x in f):
        return {}, {}, {}, f
    cat: dict[str, dict] = {}
    for r in raw.catalogo:
        sku = str(r["sku"]).strip() if r.get("sku") is not None else ""
        lin, ctg = str(r.get("linea") or "").strip(), str(r.get("categoria") or "").strip()
        if not sku:
            continue
        if sku in cat and (cat[sku]["linea"], cat[sku]["categoria"]) != (lin, ctg):
            f.append(Finding("RAW_SKU_MULTI_LINE", "block", f"El SKU {sku} aparece con más de una línea o categoría en el catálogo.", f"catalogo fila {r['_row']}"))
        cat[sku] = {"producto": str(r.get("producto") or sku).strip(), "linea": lin, "categoria": ctg}
    wins = _windows(period)
    keys = [k for k in ("cur", "yoy", "mom") if k in wins]
    acc: dict[tuple, _Acc] = defaultdict(_Acc)          # (ventana, dimensión, valor) -> acumulado
    prod: dict[tuple, dict] = defaultdict(lambda: {"monto": Decimal(0), "canales": set()})   # (ventana, sku)
    bad_date = bad_num = empty_id = unknown_sku = neg = 0
    seen_lines: set = set()
    dup = 0
    month_rows: dict[tuple, int] = defaultdict(int)
    nuevo_bad = 0
    for r in raw.ventas:
        d = _date(r.get("fecha_pedido"))
        if d is None:
            bad_date += 1
            continue
        month_rows[(d.year, d.month)] += 1
        win = next((k for k in keys if d.year == wins[k][0] and d.month in wins[k][1]), None)
        if win is None:
            continue
        monto, piezas = ind.to_dec(r.get("monto_venta")), ind.to_dec(r.get("piezas"))
        if monto is None or piezas is None:
            bad_num += 1
            continue
        pid, pac = str(r.get("id_pedido") or "").strip(), str(r.get("id_paciente") or "").strip()
        sku = str(r.get("sku") or "").strip()
        if not pid or not pac or not sku:
            empty_id += 1
            continue
        if monto < 0 or piezas < 0:
            neg += 1
        if (pid, sku, win) in seen_lines:
            dup += 1
        seen_lines.add((pid, sku, win))
        c = cat.get(sku)
        if c is None:
            unknown_sku += 1
            continue
        canal = str(r.get("canal") or "").strip() or "SIN CANAL"
        for dim, val in (("total", "TOTAL"), ("canal", canal), ("linea", c["linea"]), ("categoria", c["categoria"])):
            a = acc[(win, dim, val)]
            a.monto += monto
            a.piezas += piezas
            a.pacientes.add(pac)
            a.pedidos.add(pid)
            a.skus.add(sku)
        pr = prod[(win, sku)]
        pr["monto"] += monto
        pr["canales"].add(canal)
    ev = lambda n: f"{n} fila(s)"          # noqa: E731
    for n, code, msg in ((bad_date, "RAW_DATE_UNREADABLE", "con fecha ilegible"), (bad_num, "RAW_NUMBER_UNREADABLE", "con piezas o monto ilegibles"),
                         (empty_id, "RAW_ID_EMPTY", "sin id_pedido, id_paciente o sku"), (unknown_sku, "RAW_SKU_NOT_IN_CATALOG", "con un SKU que no está en el catálogo")):
        if n:
            f.append(Finding(code, "block", f"Ventas: {ev(n)} {msg}.", "ventas"))
    if neg:
        f.append(Finding("RAW_NEGATIVE_VALUES", "warn", f"Ventas: {ev(neg)} con piezas o monto negativos (no se tratan como devolución).", "ventas"))
    if dup:
        f.append(Finding("RAW_DUP_LINES", "warn", f"Ventas: {ev(dup)} repetidas (mismo pedido y SKU en la misma ventana).", "ventas"))
    for k in keys:
        if not acc.get((k, "total", "TOTAL")):
            nombre = {"cur": "el periodo del reporte", "yoy": "el mismo periodo del año anterior", "mom": "el mes anterior"}[k]
            f.append(Finding("RAW_PERIOD_EMPTY" if k == "cur" else "RAW_WINDOW_MISSING", "block",
                             f"Ventas: no hay datos de {nombre}; la extracción debe cubrirlo.", "ventas"))
    if period.periodicity == "mensual":
        a, b = month_rows.get((period.year, period.index)), wins["mom"]
        pm = month_rows.get((b[0], next(iter(b[1]))))
        if a and pm and a < 0.5 * pm:
            f.append(Finding("RAW_LOW_VOLUME", "warn", f"El mes del reporte trae {a} filas contra {pm} del mes anterior: posible extracción incompleta.", "ventas"))
    if any(x.severity == "block" for x in f):
        return {}, {}, {}, f

    file = raw.file
    labels = {"yoy": (str(period.year - 1), str(period.year)),
              "mom": (period.previous_month_name.capitalize(), period.month_name.capitalize())}
    tables: dict[str, Table] = {}
    for comp, base in (("yoy", "yoy"), ("mom", "mom")):
        if base not in wins:
            continue
        for kind, dim in (("panorama", "total"), ("canal", "canal"), ("linea", "linea"), ("categoria", "categoria")):
            cur = {v: a for (w, dm, v), a in acc.items() if w == "cur" and dm == dim}
            prv = {v: a for (w, dm, v), a in acc.items() if w == base and dm == dim}
            names = _order(kind, set(cur) | set(prv), cur)
            groups = [Group(n, _period_row(labels[comp][0], prv.get(n), file), _period_row(labels[comp][1], cur.get(n), file)) for n in names]
            tables[f"aetops.{kind}.{comp}"] = Table(f"aetops.{kind}.{comp}", "YoY" if comp == "yoy" else "MoM", groups)
        pano = tables[f"aetops.panorama.{comp}"].groups[0]
        for kind in ("canal", "linea", "categoria"):
            for g in tables[f"aetops.{kind}.{comp}"].groups:
                for side, tot in ((g.previous, pano.previous), (g.current, pano.current)):
                    side.values["share"] = ind.share(side.values["monto"], tot.values["monto"], "monto/total")
        for kind in ("panorama", "canal", "linea", "categoria"):
            for g in tables[f"aetops.{kind}.{comp}"].groups:
                if kind == "panorama":
                    for side, tot in ((g.previous, g.previous), (g.current, g.current)):
                        side.values["share"] = ind.share(side.values["monto"], tot.values["monto"], "monto/total")
                g.pct = {k: ind.pct_change(g.current.values[k], g.previous.values[k], k) for k in PCT_METRICS}

    # productos: Top 20 por venta actual; crecimiento y decrecimiento por Δ$ contra el periodo de comparación
    cmp_win = "mom" if "mom" in wins else "yoy"
    skus = {s for (w, s) in prod if w in ("cur", cmp_win)}
    rows = []
    for s in skus:
        a, p = prod.get(("cur", s)), prod.get((cmp_win, s))
        av = ind.derived(a["monto"], "sum(monto_venta)") if a else ind.derived(Decimal(0), "sum(monto_venta)")
        pv = ind.derived(p["monto"], "sum(monto_venta)") if p else ind.make(None)
        c = cat[s]
        rows.append(ProductRow(sivec=s, producto=c["producto"], aetop=c["linea"], canales=ind.derived(Decimal(len(a["canales"])) if a else Decimal(0), "distinct(canal)"),
                               actual=av, anterior=pv, delta=ind.delta_abs(av, pv, "actual-anterior"), pasted_delta=ind.make(None)))
    top = sorted((r for r in rows if r.actual.v), key=lambda r: -r.actual.v)[:20]
    grow = sorted((r for r in rows if r.delta.v and r.delta.v > 0), key=lambda r: -r.delta.v)[:10]
    decl = sorted((r for r in rows if r.delta.v and r.delta.v < 0), key=lambda r: r.delta.v)[:10]
    products = {"aetops.productos.top": ProductTable("aetops.productos.top", "top", top),
                "aetops.productos.growth": ProductTable("aetops.productos.growth", "growth", grow),
                "aetops.productos.decline": ProductTable("aetops.productos.decline", "decline", decl)}

    negados: dict[str, NegadosTable] = {}
    if raw.has_negados:
        label = period.month_name.capitalize() if period.periodicity == "mensual" else f"Q{period.index} {period.year}"
        nrows = []
        for r in raw.negados:
            nm = str(r.get("producto") or "").strip()
            if not nm:
                continue
            nrows.append(NegadoRow(name=nm, alta=str(r.get("alta") or "").strip(), pedidos=ind.make(r.get("pedidos")),
                                   cantidad=ind.make(r.get("cantidad_negada")), monto=ind.make(r.get("monto_negado")),
                                   share=ind.make(None), pasted_share=ind.make(None)))
        nrows.sort(key=lambda x: -(x.monto.v or Decimal(0)))
        total = ind.derived(sum((x.monto.v for x in nrows if x.monto.v is not None), Decimal(0)), "sum(monto)") if nrows else ind.derived(None, "sum(monto)")
        for x in nrows:
            x.share = ind.share(x.monto, total, "monto/total negado")
        negados["aetops.negados.producto"] = NegadosTable("aetops.negados.producto", label, nrows, total)
        negados["aetops.negados.alta"] = derive_alta(negados["aetops.negados.producto"], None)
    return tables, products, negados, f
