"""Importadores de hojas con bloques lado a lado: productos (`Tablas`) y `Negados`."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import openpyxl
from openpyxl.utils import get_column_letter

from ..models import Finding
from .base_sheet import _check_file
from .profile import Profile, norm


@dataclass
class RawBlock:
    role: str                                  # top|growth|decline | producto|alta
    label: str                                 # rótulo sobre el encabezado (negados)
    origin: str                                # coordenada del encabezado
    rows: list[dict[str, tuple[object, str]]] = field(default_factory=list)


def _open(path: Path, sheet: str):
    _check_file(path)
    wb = openpyxl.load_workbook(path, data_only=True, keep_vba=False)
    return wb[sheet] if sheet in wb.sheetnames else None


def _contiguous_header(ws, row: int, col: int) -> list[tuple[int, str]]:
    out, c = [], col
    while c <= ws.max_column and ws.cell(row, c).value is not None:
        out.append((c, norm(ws.cell(row, c).value)))
        c += 1
    return out


def _map_cols(header, columns: dict[str, tuple[str, ...]], sheet: str, row: int, findings):
    alias = {a: k for k, al in columns.items() for a in al}
    mapped: dict[int, str] = {}
    for col, text in header:
        key = alias.get(text)
        if key is None:
            findings.append(Finding(
                "COLUMN_UNMAPPED", "block",
                f"Encabezado '{text}' sin mapeo aprobado en {sheet}.",
                f"{sheet}!{get_column_letter(col)}{row}"))
        else:
            mapped[col] = key
    return mapped


def import_products(path: str | Path, profile: Profile) -> tuple[list[RawBlock], list[Finding]]:
    cfg = profile.products
    findings: list[Finding] = []
    if not cfg:
        return [], findings
    ws = _open(Path(path), cfg["sheet"])
    if ws is None:
        return [], [Finding("MISSING_SHEET", "block", f"Falta la hoja '{cfg['sheet']}'.", cfg["sheet"])]
    heads = sorted(
        ((c.column, c.row) for row in ws.iter_rows() for c in row
         if norm(c.value) == cfg["key_header"]))
    blocks: list[RawBlock] = []
    roles = list(cfg["roles"])
    for i, (col, hrow) in enumerate(heads):
        header = _contiguous_header(ws, hrow, col)
        mapped = _map_cols(header, cfg["columns"], cfg["sheet"], hrow, findings)
        if i >= len(roles):
            findings.append(Finding(
                "BLOCK_UNUSED", "info", f"Bloque de productos extra en {cfg['sheet']}!"
                f"{get_column_letter(col)}{hrow}; no se usa.", ""))
            continue
        blk = RawBlock(roles[i], "", f"{cfg['sheet']}!{get_column_letter(col)}{hrow}")
        key_col = next((c for c, k in mapped.items() if k == "producto"), None)
        if key_col is None:
            findings.append(Finding("COLUMN_UNMAPPED", "block",
                                    "Bloque de productos sin columna 'Producto'.", blk.origin))
            continue
        r = hrow + 1
        while r <= ws.max_row and ws.cell(r, key_col).value is not None:
            blk.rows.append({
                k: (ws.cell(r, c).value, f"{cfg['sheet']}!{get_column_letter(c)}{r}")
                for c, k in mapped.items()})
            r += 1
        blocks.append(blk)
    got = {b.role for b in blocks}
    for role in roles:
        if role not in got:
            findings.append(Finding("MISSING_BLOCK", "block",
                                    f"No se encontró el bloque de productos '{role}'.", cfg["sheet"]))
    return blocks, findings


def import_negados(path: str | Path, profile: Profile) -> tuple[list[RawBlock], list[Finding]]:
    cfg = profile.negados
    findings: list[Finding] = []
    if not cfg:
        return [], findings
    ws = _open(Path(path), cfg["sheet"])
    if ws is None:
        return [], [Finding("MISSING_SHEET", "block", f"Falta la hoja '{cfg['sheet']}'.", cfg["sheet"])]
    monto_alias = cfg["columns"]["monto"]
    hrow = next((r for r in range(1, min(ws.max_row, 8) + 1)
                 if any(norm(c.value) in monto_alias for c in ws[r])), None)
    if hrow is None:
        return [], [Finding("MISSING_BLOCK", "block", "No se encontró encabezado de negados.", cfg["sheet"])]
    # grupos de columnas contiguas = bloques
    cols = [c.column for c in ws[hrow] if c.value is not None]
    groups: list[list[int]] = []
    for c in cols:
        if groups and c == groups[-1][-1] + 1:
            groups[-1].append(c)
        else:
            groups.append([c])
    blocks: list[RawBlock] = []
    for g in groups:
        header = [(c, norm(ws.cell(hrow, c).value)) for c in g]
        first = header[0][1]
        role = "producto" if first in cfg["columns"]["producto"] else (
            "alta" if first in cfg["columns"]["alta"] else None)
        origin = f"{cfg['sheet']}!{get_column_letter(g[0])}{hrow}"
        if role is None:
            findings.append(Finding("SECTION_UNKNOWN", "block",
                                    f"Bloque de negados no reconocido ('{first}').", origin))
            continue
        mapped = _map_cols(header, cfg["columns"], cfg["sheet"], hrow, findings)
        label = str(ws.cell(hrow - 1, g[0]).value or "").strip() if hrow > 1 else ""
        blk = RawBlock(role, label, origin)
        key_col = g[0]
        r = hrow + 1
        while r <= ws.max_row and ws.cell(r, key_col).value is not None:
            row = {k: (ws.cell(r, c).value, f"{cfg['sheet']}!{get_column_letter(c)}{r}")
                   for c, k in mapped.items()}
            row["_name"] = (ws.cell(r, key_col).value, f"{cfg['sheet']}!{get_column_letter(key_col)}{r}")
            blk.rows.append(row)
            r += 1
        blocks.append(blk)
    return blocks, findings
