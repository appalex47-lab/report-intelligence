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


def load_profile(unit: str = "aetops", name: str = "mensual") -> Profile:
    data = yaml.safe_load((PROFILES_DIR / unit / f"{name}.yaml").read_text(encoding="utf-8"))
    alias: dict[str, str] = {}
    for key, aliases in data["metrics"].items():
        for a in aliases:
            alias[norm(a)] = key
    kinds = {
        k: {f: tuple(norm(x) for x in v) for f, v in spec.items()}
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
    )
