"""Metas (presupuesto) del periodo: dato manual que se captura antes de generar.

AETOPS: obligatoria (total + una meta por línea). GLP-1: opcional (total y, si se desea, por grupo).
Se guardan en el historial con el reporte, para poder ver el cumplimiento a lo largo del tiempo."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path


@dataclass(frozen=True)
class Targets:
    total: Decimal | None
    by_group: dict[str, Decimal] = field(default_factory=dict)      # AETOPS: líneas (AE-A…); GLP-1: regiones, opcional

    @staticmethod
    def parse(data: dict) -> "Targets":
        """{'total': 33000000, 'AE-A': 21000000, …} (los números pueden venir como texto con $ y comas)."""
        def num(v):
            if v in (None, ""):
                return None
            try:
                return Decimal(str(v).replace("$", "").replace(",", "").strip())
            except InvalidOperation:
                raise ValueError(f"Meta inválida: {v!r}") from None
        total = num(data.get("total"))
        groups = {k: num(v) for k, v in data.items() if k != "total" and num(v) is not None}
        return Targets(total, groups)

    @staticmethod
    def load(path: str | Path) -> "Targets":
        return Targets.parse(json.loads(Path(path).read_text(encoding="utf-8")))

    def to_dict(self) -> dict:
        d = {k: str(v) for k, v in self.by_group.items()}
        if self.total is not None:
            d["total"] = str(self.total)
        return d
