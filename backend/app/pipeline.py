"""Orquestador: Excel AETOPS -> tablas + hallazgos."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .calc.tables_aetops import build_tables
from .calc.tables_extra import build_negados, build_products
from .importer.base_sheet import import_base
from .importer.profile import load_glp1_profile, load_profile
from .importer.sheets import import_negados, import_products
from .models import Finding, GBlock, NegadosTable, Period, ProductTable, Table
from .validator import extra
from .validator.rules import has_blockers, validate


@dataclass
class Result:
    tables: dict[str, Table]
    findings: list[Finding]
    products: dict[str, ProductTable] = field(default_factory=dict)
    negados: dict[str, NegadosTable] = field(default_factory=dict)

    @property
    def can_generate(self) -> bool:
        return not has_blockers(self.findings)


def run_aetops(path: str | Path, profile_name: str = "mensual",
               period: Period | None = None) -> Result:
    profile = load_profile("aetops", profile_name)
    raw = import_base(path, profile)
    tables = build_tables(raw, profile.ticket_source)
    findings = validate(raw, tables) + extra.required_comparisons(raw, profile)

    pblocks, pf = import_products(path, profile)
    nblocks, nf = import_negados(path, profile)
    prod = build_products(pblocks, Path(path).name, profile.products.get("sheet", ""))
    neg = build_negados(nblocks, Path(path).name, profile.negados.get("sheet", ""))
    findings += pf + nf + extra.products(prod) + extra.negados(neg)
    if period is not None:
        findings += extra.expected_period(tables, neg, period)
    return Result(tables, findings, prod, neg)


def run_aetops_base(path: str | Path, profile_name: str = "mensual") -> Result:
    """Compatibilidad 4a: solo la hoja Base (sin productos/negados)."""
    profile = load_profile("aetops", profile_name)
    raw = import_base(path, profile)
    tables = build_tables(raw, profile.ticket_source)
    return Result(tables, validate(raw, tables))


@dataclass
class GlpResult:
    blocks: dict[str, GBlock]
    funnel: GBlock | None
    findings: list[Finding]

    @property
    def can_generate(self) -> bool:
        return not has_blockers(self.findings)


def run_glp1(path: str | Path, profile_name: str = "mensual", period: Period | None = None) -> GlpResult:
    from .calc.glp1 import build_glp1
    from .importer.glp1_blocks import import_glp1
    from .validator.glp1_rules import validate_glp1

    profile = load_glp1_profile(profile_name)
    raw = import_glp1(path, profile)
    blocks, funnel = build_glp1(raw, profile)
    return GlpResult(blocks, funnel, validate_glp1(raw, blocks, funnel, profile, period))
