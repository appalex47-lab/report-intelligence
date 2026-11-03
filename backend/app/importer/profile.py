"""Carga de perfiles de importación (YAML) y normalización de textos."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import yaml

PROFILES_DIR = Path(__file__).resolve().parents[3] / "profiles"


def norm(text) -> str:
    """Minúsculas, sin acentos, espacios colapsados. None -> ''."""
    if text is None:
        return ""
    s = unicodedata.normalize("NFKD", str(text))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip().lower()


@dataclass(frozen=True)
class Profile:
    name: str
    version: int
    sheet: str
    label_col: str
    section_markers: tuple[str, ...]
    kinds: dict[str, dict[str, tuple[str, ...]]]
    metric_alias: dict[str, str]          # alias normalizado -> clave canónica
    unsupported_kinds: tuple[str, ...]
    ticket_source: dict[str, str]
    comparisons: tuple[str, ...]
    products: dict
    negados: dict


def _norm_cols(block: dict) -> dict:
    out = dict(block)
    if "columns" in out:
        out["columns"] = {k: tuple(norm(a) for a in v) for k, v in out["columns"].items()}
    if "key_header" in out:
        out["key_header"] = norm(out["key_header"])
    return out


def load_profile(unit: str = "aetops", name: str = "mensual") -> Profile:
    data = yaml.safe_load((PROFILES_DIR / unit / f"{name}.yaml").read_text(encoding="utf-8"))
    alias: dict[str, str] = {}
    for key, aliases in data["metrics"].items():
        for a in aliases:
            alias[norm(a)] = key
    kinds = {
        k: {f: (v if isinstance(v, str) else tuple(norm(x) for x in v)) for f, v in spec.items()}
        for k, spec in data["kinds"].items()
    }
    return Profile(
        name=data["profile"],
        version=int(data["version"]),
        sheet=data["sheet"],
        label_col=data["label_col"],
        section_markers=tuple(norm(x) for x in data["section_markers"]),
        kinds=kinds,
        metric_alias=alias,
        unsupported_kinds=tuple(norm(x) for x in data.get("unsupported_kinds", [])),
        ticket_source=dict(data.get("ticket_source", {})),
        comparisons=tuple(norm(x) for x in data.get("comparisons", ["yoy", "mom"])),
        products=_norm_cols(data.get("products", {})),
        negados=_norm_cols(data.get("negados", {})),
    )


@dataclass(frozen=True)
class GProfile:
    name: str
    version: int
    period_sheets: tuple[str, ...]
    metric_alias: dict[str, str]          # alias normalizado -> clave canónica
    typo_alias: dict[str, str]
    ticket_source: str
    blocks: dict[str, dict]
    funnel: dict
    delta_source: str


def load_glp1_profile(name: str = "mensual") -> GProfile:
    data = yaml.safe_load((PROFILES_DIR / "glp1" / f"{name}.yaml").read_text(encoding="utf-8"))
    alias = {norm(a): k for k, al in data["metrics"].items() for a in al}
    typos = {norm(a): k for k, al in data.get("typo_aliases", {}).items() for a in al}
    blocks = {}
    for bname, spec in data["blocks"].items():
        sp = dict(spec)
        if "header" in sp:
            sp["header"] = [[norm(x) for x in grp] for grp in sp["header"]]
        blocks[bname] = sp
    fn = dict(data.get("funnel", {}))
    if fn:
        fn["stages"] = [norm(x) for x in fn["stages"]]
        fn["typo_stages"] = {norm(k): norm(v) for k, v in fn.get("typo_stages", {}).items()}
    return GProfile(
        name=data["profile"], version=int(data["version"]),
        period_sheets=tuple(data.get("period_sheets", [])),
        metric_alias=alias, typo_alias=typos,
        ticket_source=data.get("ticket_source", "pasted"),
        blocks=blocks, funnel=fn, delta_source=data.get("delta_source", "pasted"))
