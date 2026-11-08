"""Lectura genérica de tablas crudas (hojas de un .xlsx o CSV en una carpeta) y utilidades de fecha."""
from __future__ import annotations

import csv
import datetime as dt
import re
import unicodedata
from decimal import Decimal
from pathlib import Path

import openpyxl

from ..models import Finding


IDENTIFICADORES = ("sku", "id_pedido", "id_paciente")          # columnas que son CÓDIGOS, no cantidades: se leen siempre como texto


def como_identificador(v):
    """Un código (SKU, id de pedido o de paciente) como texto. Un entero guardado como número (`23522`, `23522.0`, `Decimal`) se escribe «23522»: sin el «.0» que
    añade la conversión de un número decimal (muchos exportadores guardan los códigos como número) y sin que el mismo código sea distinto según cómo se guardó. Un texto
    que solo es un entero con «.0» («23522.0», típico de un CSV exportado desde un número) se trata igual. Todo lo demás se conserva tal cual (recortado). `None` sigue siendo `None`."""
    if v is None or isinstance(v, bool):
        return v
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() else str(v)
    if isinstance(v, Decimal):
        return str(int(v)) if v == v.to_integral_value() else str(v)
    s = str(v).strip()
    return s.split(".")[0] if re.fullmatch(r"\d{2,}\.0+", s) else s


def norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower().strip()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def read_tables(path: str | Path, specs: dict[str, list[str]], optional: set[str] = frozenset()) -> tuple[dict[str, list[dict]], list[Finding]]:
    """specs: {tabla: [columnas obligatorias]}. Devuelve ({tabla: filas}, hallazgos). Cada fila es dict con '_row'."""
    p = Path(path)
    out: dict[str, list[dict]] = {}
    f: list[Finding] = []
    raw: dict[str, tuple] = {}
    if p.is_dir():
        for name in specs:
            fp = p / f"{name}.csv"
            if fp.exists():
                with fp.open(newline="", encoding="utf-8-sig") as fh:
                    rd = csv.reader(fh)
                    hdr = next(rd, [])
                    raw[name] = (hdr, list(rd))
    else:
        wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
        names = {norm(n): n for n in wb.sheetnames}
        for name in specs:
            if name in names:
                it = wb[names[name]].iter_rows(values_only=True)
                hdr = next(it, ())
                raw[name] = (hdr, list(it))
        wb.close()
    for name, req in specs.items():
        if name not in raw:
            if name not in optional:
                f.append(Finding("RAW_TABLE_MISSING", "block", f"Falta la tabla '{name}'.", name))
            continue
        hdr = [norm(c) for c in raw[name][0]]
        miss = [c for c in req if c not in hdr]
        if miss:
            f.append(Finding("RAW_COLUMN_MISSING", "block", f"Tabla '{name}': faltan columnas obligatorias: {', '.join(miss)}.", name))
            continue
        rows = []
        for i, r in enumerate(raw[name][1], 2):
            if r is None or all(c in (None, "") for c in r):
                continue
            d = {h: (como_identificador(r[k] if k < len(r) else None) if h in IDENTIFICADORES else (r[k] if k < len(r) else None)) for k, h in enumerate(hdr) if h}
            d["_row"] = i
            rows.append(d)
        out[name] = rows
    return out, f


def to_date(v):
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    if isinstance(v, (int, float)) and not isinstance(v, bool) and 20000 < v < 80000:
        return dt.date(1899, 12, 30) + dt.timedelta(days=int(v))
    if isinstance(v, str):
        s = v.strip()
        for fmt, n in (("%Y-%m-%d", 10), ("%d/%m/%Y", 10), ("%Y/%m/%d", 10), ("%Y-%m", 7)):
            try:
                return dt.datetime.strptime(s[:n], fmt).date()
            except ValueError:
                pass
    return None
