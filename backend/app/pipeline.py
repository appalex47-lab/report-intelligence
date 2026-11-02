"""Orquestador mínimo de la Fase 4a: Excel (hoja Base AETOPS) -> tablas + hallazgos."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .calc.tables_aetops import build_tables
from .importer.base_sheet import import_base
from .importer.profile import load_profile
from .models import Finding, Table
from .validator.rules import has_blockers, validate


@dataclass
class Result:
    tables: dict[str, Table]
    findings: list[Finding]

    @property
    def can_generate(self) -> bool:
        return not has_blockers(self.findings)


def run_aetops_base(path: str | Path, profile_name: str = "mensual") -> Result:
    profile = load_profile("aetops", profile_name)
    raw = import_base(path, profile)
    tables = build_tables(raw, profile.ticket_source)
    return Result(tables, validate(raw, tables))
