"""Importador por bloques de la hoja `Base` de AETOPS (docs/ARQUITECTURA.md §5).

No lee "una tabla por hoja": detecta secciones (YoY/MoM) por anclas, clasifica por
encabezados con el perfil y registra la celda de origen de cada valor.
Nunca ejecuta macros (openpyxl) y rechaza .xlsm.
"""
from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import openpyxl
from openpyxl.utils import get_column_letter

from ..models import Finding
from .profile import Profile, norm

MAX_BYTES = 25 * 1024 * 1024


class ImportRejected(Exception):
    pass


@dataclass
class RawRow:
    label: str
    cells: dict[str, tuple[object, str]]   # clave canónica -> (valor crudo, coordenada)


@dataclass
class RawGroup:
    name: str
    periods: list[RawRow] = field(default_factory=list)   # [anterior, actual]
    pasted_delta: dict[str, tuple[object, str]] | None = None


@dataclass
class RawSection:
    marker: str                 # "YoY" | "MoM"
    kind: str                   # panorama | canal | linea | categoria | unknown
    start_row: int
    groups: list[RawGroup] = field(default_factory=list)


@dataclass
class RawBase:
    file: str
    sheet: str
    sections: list[RawSection]
    findings: list[Finding]


def _check_file(path: Path) -> None:
    if path.suffix.lower() == ".xlsm":
        raise ImportRejected("Archivos con macros (.xlsm) no se aceptan.")
    if path.suffix.lower() not in {".xlsx"}:
        raise ImportRejected(f"Extensión no soportada: {path.suffix}")
    if path.stat().st_size > MAX_BYTES:
        raise ImportRejected("Archivo demasiado grande.")
    if not zipfile.is_zipfile(path):
        raise ImportRejected("El archivo no es un libro OOXML válido.")


def _classify(header: dict[str, str], profile: Profile) -> str:
    b = header.get(profile.label_col, "")
    c = header.get("C", "")
    for kind, spec in profile.kinds.items():
        if b in spec.get("header_b", ()) and (
            "header_c" not in spec or c in spec["header_c"]
        ):
            return kind
    return "unknown"


def _label(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


def import_base(path: str | Path, profile: Profile) -> RawBase:
    path = Path(path)
    _check_file(path)
    wb = openpyxl.load_workbook(path, data_only=True, keep_vba=False)
    findings: list[Finding] = []
    if profile.sheet not in wb.sheetnames:
        raise ImportRejected(f"Falta la hoja '{profile.sheet}'.")
    ws = wb[profile.sheet]
    lc = profile.label_col

    # 1) ubicar marcadores de sección
    markers: list[tuple[int, str]] = []
    for r in range(1, ws.max_row + 1):
        txt = norm(ws[f"{lc}{r}"].value)
        if txt in profile.section_markers:
            markers.append((r, _label(ws[f"{lc}{r}"].value)))
    if not markers:
        raise ImportRejected("No se encontraron secciones YoY/MoM en la hoja Base.")

    sections: list[RawSection] = []
    for i, (start, marker) in enumerate(markers):
        end = markers[i + 1][0] - 1 if i + 1 < len(markers) else ws.max_row
        hdr_row = start + 1
        header = {
            get_column_letter(c.column): norm(c.value)
            for c in ws[hdr_row] if c.value is not None
        }
        kind = _classify(header, profile)
        sec = RawSection(marker=marker, kind=kind, start_row=start)
        sections.append(sec)

        if kind == "unknown":
            findings.append(Finding(
                "SECTION_UNKNOWN", "block",
                f"Sección '{marker}' en fila {start}: encabezados no reconocidos por el perfil.",
                f"{profile.sheet}!{hdr_row}"))
            continue
        if kind in profile.unsupported_kinds:
            findings.append(Finding(
                "SECTION_NOT_IMPLEMENTED", "info",
                f"Sección '{kind}' ({marker}, fila {start}) aún sin parser; no se usa.",
                f"{profile.sheet}!{hdr_row}"))
            continue

        # 2) mapeo de columnas (nunca se asigna a ciegas)
        col_metric: dict[str, str] = {}
        for col, text in header.items():
            if col == lc:
                continue
            key = profile.metric_alias.get(text)
            if key is None:
                findings.append(Finding(
                    "COLUMN_UNMAPPED", "block",
                    f"Encabezado '{text}' sin mapeo aprobado (sección {kind}/{marker}).",
                    f"{profile.sheet}!{col}{hdr_row}"))
            else:
                col_metric[col] = key

        # 3) cuerpo: anclas de grupo, filas de periodo y fila de variaciones
        grouped = kind != "panorama"
        current: RawGroup | None = None if grouped else RawGroup("TOTAL")
        if current is not None:
            sec.groups.append(current)
        for r in range(hdr_row + 1, end + 1):
            label = _label(ws[f"{lc}{r}"].value)
            cells = {
                key: (ws[f"{col}{r}"].value, f"{profile.sheet}!{col}{r}")
                for col, key in col_metric.items()
                if ws[f"{col}{r}"].value is not None
            }
            if not label and not cells:
                continue
            if label and not cells and grouped:
                current = RawGroup(label)
                sec.groups.append(current)
                continue
            if current is None:
                findings.append(Finding(
                    "ROW_IGNORED", "info", f"Fila {r} fuera de un grupo; ignorada.",
                    f"{profile.sheet}!{r}"))
                continue
            if label and len(current.periods) < 2:
                current.periods.append(RawRow(label, cells))
            elif not label and len(current.periods) == 2 and current.pasted_delta is None:
                current.pasted_delta = cells
            else:
                findings.append(Finding(
                    "ROW_IGNORED", "info",
                    f"Fila {r} sobrante en '{current.name}' ({kind}/{marker}); ignorada.",
                    f"{profile.sheet}!{r}"))
    return RawBase(str(path.name), profile.sheet, sections, findings)
