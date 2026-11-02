"""Importador por bloques del libro operativo de GLP-1 (hojas 1–9).

No depende de posiciones fijas: localiza cada tabla por el texto de su encabezado (perfil YAML),
delimita sus filas y registra la celda de origen. Lo que no reconoce lo reporta; nunca lo asigna
a ciegas ni lo ignora en silencio.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import openpyxl
from openpyxl.utils import column_index_from_string, get_column_letter

from ..models import Finding
from .base_sheet import _check_file
from .profile import GProfile, norm

TOTAL_LABELS = {"total", "totales", "subtotal"}


@dataclass
class RawGBlock:
    name: str
    sheet: str
    origin: str
    basis: str
    role: str
    prior: dict | None
    rows: list[dict] = field(default_factory=list)        # {"_key":(raw,coord),"_dim2":..,metric:(raw,coord)}
    declared_total: dict = field(default_factory=dict)


@dataclass
class RawGlp1:
    file: str
    blocks: dict[str, RawGBlock]
    funnel: list[dict]
    findings: list[Finding]
    declared_period: tuple | None


def _txt(v) -> str:
    return "" if v is None else str(v).strip()


def import_glp1(path: str | Path, profile: GProfile) -> RawGlp1:
    path = Path(path)
    _check_file(path)
    wb = openpyxl.load_workbook(path, data_only=True, keep_vba=False)
    findings: list[Finding] = []
    typo_seen: set = set()
    known_alias = set(profile.metric_alias) | set(profile.typo_alias)

    # --- 1) localizar encabezados de todos los bloques de cada hoja
    found: dict[str, list[tuple]] = {}          # nombre de bloque -> [(fila, col, captura)]
    header_pos: dict[str, set] = {}
    for bname, spec in profile.blocks.items():
        ws = wb[spec["sheet"]] if spec["sheet"] in wb.sheetnames else None
        if ws is None:
            continue
        hits = []
        for row in ws.iter_rows():
            for c in row:
                if c.value is None:
                    continue
                t = norm(c.value)
                right = norm(ws.cell(c.row, c.column + 1).value)
                if "pattern" in spec:
                    m = re.match(spec["pattern"], t)
                    if m and right in known_alias:
                        hits.append((c.row, c.column, m.group(1).strip()))
                else:
                    first, second = spec["header"][0], (spec["header"][1] if len(spec["header"]) > 1 else None)
                    if t in first and (second is None or right in second):
                        hits.append((c.row, c.column, ""))
        hits.sort(key=lambda h: (h[1], h[0]))            # por columna y luego fila
        if "occurrence" in spec:
            hits = hits[spec["occurrence"] - 1: spec["occurrence"]]
        found[bname] = hits
        header_pos.setdefault(spec["sheet"], set()).update((h[0], h[1]) for h in hits)

    # --- 2) leer cada bloque
    blocks: dict[str, RawGBlock] = {}
    for bname, spec in profile.blocks.items():
        sheet = spec["sheet"]
        if sheet not in wb.sheetnames:
            findings.append(Finding("MISSING_SHEET", "block", f"Falta la hoja '{sheet}' ({bname}).", sheet))
            continue
        hits = found.get(bname, [])
        if not hits:
            if not spec.get("optional_block"):
                findings.append(Finding("MISSING_BLOCK", "block",
                                        f"No se encontró la tabla '{bname}' en la hoja '{sheet}'.", sheet))
            continue
        ws = wb[sheet]
        for hr, hc, capture in hits:
            name = f"{bname}:{norm(capture)}" if capture else bname
            origin = f"{sheet}!{get_column_letter(hc)}{hr}"
            blk = RawGBlock(name, sheet, origin, spec.get("basis", ""), spec.get("role", "main"),
                            spec.get("prior"))
            # encabezados contiguos
            run = []
            c = hc
            while c <= ws.max_column and ws.cell(hr, c).value is not None:
                run.append((c, norm(ws.cell(hr, c).value)))
                c += 1
            req, opt = spec["cols"]["required"], spec["cols"].get("optional", [])
            n_expected = 1 + len(req) + len(opt) + (1 if spec.get("dim2") else 0)
            mapped: dict[int, str] = {}
            dim2_col = None
            for idx, (col, text) in enumerate(run):
                if idx == 0:
                    continue
                if spec.get("dim2") and idx == 1:
                    dim2_col = col
                    continue
                key = profile.metric_alias.get(text)
                if key is None and text in profile.typo_alias:
                    key = profile.typo_alias[text]
                    if (bname, text) not in typo_seen:       # una vez por tabla del perfil
                        typo_seen.add((bname, text))
                        findings.append(Finding("HEADER_TYPO_ACCEPTED", "info",
                                                f"{bname}: encabezado '{text}' aceptado como '{key}' (errata conocida).",
                                                f"{sheet}!{get_column_letter(col)}{hr}"))
                if key is None:
                    if idx < n_expected:
                        findings.append(Finding("COLUMN_UNMAPPED", "block",
                                                f"{bname}: encabezado '{text}' sin mapeo aprobado.",
                                                f"{sheet}!{get_column_letter(col)}{hr}"))
                    continue                               # idx >= n_expected: bloque vecino, se ignora
                mapped[col] = key
            for rk in req:
                if rk not in mapped.values():
                    findings.append(Finding("COLUMN_MISSING", "block",
                                            f"{bname}: falta la columna requerida '{rk}'.", origin))
            # filas
            r, blanks, stop_row = hr + 1, 0, None
            while r <= ws.max_row:
                ftxt = _txt(ws.cell(r, hc).value)
                if (r, hc) in header_pos.get(sheet, set()):
                    break
                if not ftxt:
                    if spec.get("blank") == "skip":
                        blanks += 1
                        if blanks >= 3:
                            break
                        r += 1
                        continue
                    stop_row = r
                    break
                blanks = 0
                cells = {k: (ws.cell(r, col).value, f"{sheet}!{get_column_letter(col)}{r}")
                         for col, k in mapped.items() if ws.cell(r, col).value is not None}
                if norm(ftxt) in TOTAL_LABELS:
                    blk.declared_total = cells
                    findings.append(Finding("TOTAL_ROW", "info",
                                            f"{bname}: fila '{ftxt}' en {sheet}!{r}; se excluye de los datos "
                                            "y se usa para cuadrar.", f"{sheet}!{r}"))
                else:
                    cells["_key"] = (ws.cell(r, hc).value, f"{sheet}!{get_column_letter(hc)}{r}")
                    if dim2_col:
                        cells["_dim2"] = (ws.cell(r, dim2_col).value, f"{sheet}!{get_column_letter(dim2_col)}{r}")
                    blk.rows.append(cells)
                r += 1
            if stop_row:                       # ¿hay datos tras el hueco, antes del siguiente encabezado?
                for rr in range(stop_row + 1, min(stop_row + 3, ws.max_row) + 1):
                    if (rr, hc) in header_pos.get(sheet, set()):
                        break                  # empieza otra tabla: lo que sigue le pertenece
                    if _txt(ws.cell(rr, hc).value):
                        findings.append(Finding(
                            "BLANK_ROW_INSIDE", "block",
                            f"{bname}: fila en blanco en {sheet}!{stop_row} y hay filas después; "
                            "la tabla se leyó solo hasta el hueco.", f"{sheet}!{stop_row}"))
                        break
            blocks[name] = blk

    # --- 3) embudo (sin encabezado, filas espaciadas)
    funnel: list[dict] = []
    fcfg = profile.funnel
    if fcfg:
        if fcfg["sheet"] not in wb.sheetnames:
            findings.append(Finding("MISSING_SHEET", "block", f"Falta la hoja '{fcfg['sheet']}' (embudo).", fcfg["sheet"]))
        else:
            ws = wb[fcfg["sheet"]]
            rc, cc = column_index_from_string(fcfg["rate_col"]), column_index_from_string(fcfg["count_col"])
            start = next((r for r in range(1, ws.max_row + 1)
                          if norm(ws.cell(r, 1).value) == fcfg["stages"][0]), None)
            if start is None:
                findings.append(Finding("MISSING_BLOCK", "block", "No se encontró el embudo (Ver producto…).",
                                        fcfg["sheet"]))
            else:
                seen = set()
                for r in range(start, min(start + 14, ws.max_row) + 1):
                    t = norm(ws.cell(r, 1).value)
                    label = _txt(ws.cell(r, 1).value)
                    if t in fcfg["typo_stages"]:
                        findings.append(Finding("HEADER_TYPO_ACCEPTED", "info",
                                                f"embudo: etapa '{_txt(ws.cell(r, 1).value)}' aceptada como "
                                                f"'{fcfg['typo_stages'][t]}' (errata conocida).", f"{fcfg['sheet']}!A{r}"))
                        t = fcfg["typo_stages"][t]
                        label = t.capitalize()
                    if t in fcfg["stages"] and t not in seen:
                        seen.add(t)
                        funnel.append({"stage": label,
                                       "rate": (ws.cell(r, rc).value, f"{fcfg['sheet']}!{get_column_letter(rc)}{r}"),
                                       "count": (ws.cell(r, cc).value, f"{fcfg['sheet']}!{get_column_letter(cc)}{r}")})
                for st in fcfg["stages"]:
                    if st not in seen:
                        findings.append(Finding("MISSING_BLOCK", "block", f"Embudo sin la etapa '{st}'.",
                                                fcfg["sheet"]))

    # --- 4) periodo declarado por el libro (si lo hay)
    declared = None
    for sn in profile.period_sheets:
        if sn in wb.sheetnames:
            for row in wb[sn].iter_rows():
                for c in row:
                    t = norm(c.value)
                    m = re.search(r"periodo declarado:\s*q(\d)\s+(\d{4})", t)
                    if m:
                        declared = ("q", int(m.group(1)), int(m.group(2)))
                    m = re.search(r"periodo declarado:\s*([a-z]+)\s+(\d{4})", t)
                    if m and declared is None:
                        declared = ("mes", m.group(1), int(m.group(2)))
    return RawGlp1(path.name, blocks, funnel, findings, declared)
