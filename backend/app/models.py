"""Modelo canónico: valores con estado y trazabilidad (docs/ARQUITECTURA.md §4)."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

Status = Literal["ok", "zero", "missing", "new_item"]


@dataclass(frozen=True)
class Lineage:
    file: str
    sheet: str
    cells: str          # p. ej. "Base!C3" o "Base!C3:C4"
    transform: str      # "pasted" | "ratio(Monto,Pedidos)" | "pct_change(...)"


@dataclass(frozen=True)
class Value:
    """Nunca un float desnudo: el faltante es un estado, no un cero."""
    v: Decimal | None
    status: Status
    src: Lineage | None = None
    note: str = ""

    @property
    def is_missing(self) -> bool:
        return self.v is None


@dataclass(frozen=True)
class Finding:
    id: str
    severity: Literal["block", "warn", "info"]
    message: str
    evidence: str = ""


@dataclass
class PeriodRow:
    label: str                         # "2025", "Agosto"…
    values: dict[str, Value]           # clave canónica -> Value


@dataclass
class Group:
    name: str                          # "APP FESA", "AE-A" o "TOTAL"
    previous: PeriodRow
    current: PeriodRow
    pct: dict[str, Value] = field(default_factory=dict)   # %Δ calculado por el motor


@dataclass
class Table:
    key: str                           # "aetops.canal.yoy"
    comparison: Literal["YoY", "MoM"]
    groups: list[Group]


MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
          "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


@dataclass(frozen=True)
class Period:
    """Periodo del reporte (elegido por el usuario)."""
    unit: Literal["AETOPS", "GLP1"]
    periodicity: Literal["mensual", "trimestral"]
    year: int
    index: int          # mes 1-12 o trimestre 1-4

    @property
    def month_name(self) -> str:
        return MONTHS[self.index - 1]

    @property
    def previous_month_name(self) -> str:
        return MONTHS[(self.index - 2) % 12]


@dataclass
class ProductRow:
    sivec: str
    producto: str
    aetop: str
    canales: Value
    actual: Value
    anterior: Value
    delta: Value                         # calculado por el motor
    pasted_delta: Value                  # lo que trae el Excel (solo contraste)


@dataclass
class ProductTable:
    key: str                             # "aetops.productos.top" | ".growth" | ".decline"
    role: str
    rows: list[ProductRow]


@dataclass
class NegadoRow:
    name: str                            # producto o línea ("Alta")
    alta: str
    pedidos: Value
    cantidad: Value
    monto: Value
    share: Value                         # calculado: monto ÷ total negado
    pasted_share: Value


@dataclass
class NegadosTable:
    key: str                             # "aetops.negados.producto" | ".alta"
    label: str                           # rótulo de periodo de la hoja ("Julio")
    rows: list[NegadoRow]
    total: Value
