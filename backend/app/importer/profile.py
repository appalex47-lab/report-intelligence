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
