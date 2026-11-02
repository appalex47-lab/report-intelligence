"""Orquestador: Excel AETOPS -> tablas + hallazgos."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .calc.tables_aetops import build_tables
from .calc.tables_extra import build_negados, build_products, derive_alta
from .importer.base_sheet import import_base
from .importer.profile import load_glp1_profile, load_profile
from .importer.sheets import import_negados, import_products
from .models import Finding, GBlock, NegadosTable, Period, ProductTable, Table
from .validator import extra
from .validator.targets import validate_targets
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


def run_aetops(path: str | Path, profile_name: str = "mensual", period: Period | None = None,
               targets=None, require_targets: bool = False) -> Result:
    """`require_targets`: la herramienta (CLI/API) lo activa para AETOPS; el motor puro lo deja opcional."""
    profile = load_profile("aetops", profile_name)
    raw = import_base(path, profile)
    tables = build_tables(raw, profile.ticket_source)
    findings = validate(raw, tables) + extra.required_comparisons(raw, profile)

    pblocks, pf = import_products(path, profile)
    nblocks, nf = import_negados(path, profile)
    prod = build_products(pblocks, Path(path).name, profile.products.get("sheet", ""))
    neg = build_negados(nblocks, Path(path).name, profile.negados.get("sheet", ""))
    if "aetops.negados.producto" in neg:           # la tabla por línea se deriva del detalle; la pegada queda de contraste
        pasted = neg.get("aetops.negados.alta")
        if pasted is not None:
            neg["aetops.negados.alta_excel"] = pasted
        neg["aetops.negados.alta"] = derive_alta(neg["aetops.negados.producto"], pasted)
    findings += pf + nf + extra.products(prod) + extra.negados(neg)
    if period is not None:
        findings += extra.expected_period(tables, neg, period)
    res = Result(tables, findings, prod, neg)
    if require_targets or targets is not None:
        res.findings += validate_targets(res, targets, require_targets)
    return res


def run_aetops_raw(path: str | Path, period: Period, targets=None, require_targets: bool = False) -> Result:
    """AETOPS desde datos crudos (ventas + catálogo + negados): ver docs/CONTRATO_DATOS.md."""
    from .raw import aetops as raw_aetops
    raw = raw_aetops.load(path)
    tables, prod, neg, findings = raw_aetops.aggregate(raw, period)
    if tables:
        findings += extra.products(prod) + extra.negados(neg) + extra.expected_period(tables, neg, period)
    res = Result(tables, findings, prod, neg)
    if require_targets or targets is not None:
        if tables:
            res.findings += validate_targets(res, targets, require_targets)
    return res


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


def run_glp1_raw(path: str | Path, period: Period) -> "GlpResult":
    """GLP-1 desde datos crudos (ventas + catálogo + tráfico + negados): ver docs/CONTRATO_DATOS.md."""
    from .raw import glp1 as raw_glp1
    blocks, funnel, findings = raw_glp1.build(path, period)
    return GlpResult(blocks, funnel, findings)


def run_glp1(path: str | Path, profile_name: str = "mensual", period: Period | None = None) -> GlpResult:
    from .calc.glp1 import build_glp1
    from .importer.glp1_blocks import import_glp1
    from .validator.glp1_rules import validate_glp1

    profile = load_glp1_profile(profile_name)
    raw = import_glp1(path, profile)
    blocks, funnel = build_glp1(raw, profile)
    return GlpResult(blocks, funnel, validate_glp1(raw, blocks, funnel, profile, period))
