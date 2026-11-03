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


# --- Evolución compatible del hallazgo (docs/MODELO_HALLAZGOS.md; spec Fase 1 §4.2-4.3) ---------------------------------
# `severity` NO cambia: sigue siendo la única fuente que leen `has_blockers()`, la interfaz y el historial.
SEVERITY_A_EFECTO = {"block": "bloquear", "warn": "advertir", "info": "informar"}
EFECTO_A_SEVERITY = {v: k for k, v in SEVERITY_A_EFECTO.items()}
TIPOS_HALLAZGO = ("integridad", "consistencia", "cobertura", "definicion", "conciliacion", "narrativa", "presentacion")
GRAVEDADES = ("critica", "alta", "media", "baja")
ESTADOS_VERIFICACION = ("verificado", "inconsistente", "no_verificable", "supuesto")
EFECTOS_GENERACION = tuple(EFECTO_A_SEVERITY)
MODELO_HALLAZGOS_VERSION = "1.0.0"


@dataclass(frozen=True)
class Finding:
    """Hallazgo de validación. Firma histórica `(id, severity, message, evidence)`; los siete campos nuevos son
    opcionales, solo por palabra clave, y quedan en `None` (o vacío) si no se aportan: nada se inventa."""
    id: str
    severity: Literal["block", "warn", "info"]
    message: str
    evidence: str = ""
    tipo: str | None = field(default=None, kw_only=True)
    gravedad: str | None = field(default=None, kw_only=True)
    estado_verificacion: str | None = field(default=None, kw_only=True)
    efecto_generacion: str | None = field(default=None, kw_only=True)
    faltante: tuple = field(default=(), kw_only=True)
    regla_id: str | None = field(default=None, kw_only=True)
    regla_version: str | None = field(default=None, kw_only=True)

    def __post_init__(self):
        for name, allowed in (("tipo", TIPOS_HALLAZGO), ("gravedad", GRAVEDADES),
                              ("estado_verificacion", ESTADOS_VERIFICACION), ("efecto_generacion", EFECTOS_GENERACION)):
            val = getattr(self, name)
            if val is not None and val not in allowed:
                raise ValueError(f"Finding.{name}={val!r} no es válido; opciones: {allowed}")
        derivado = SEVERITY_A_EFECTO.get(self.severity)
        if self.efecto_generacion is None:
            if derivado is not None:                  # solo severity: se deriva con la correspondencia documentada
                object.__setattr__(self, "efecto_generacion", derivado)
        elif derivado is not None and self.efecto_generacion != derivado:
            raise ValueError(f"Finding {self.id!r}: severity={self.severity!r} es incoherente con "
                             f"efecto_generacion={self.efecto_generacion!r} (esperado {derivado!r})")
        if not isinstance(self.faltante, tuple):
            object.__setattr__(self, "faltante", tuple(self.faltante or ()))
        if self.estado_verificacion == "no_verificable" and not self.faltante:
            raise ValueError(f"Finding {self.id!r}: estado_verificacion='no_verificable' exige `faltante` (qué dato falta)")

    def to_dict(self) -> dict:
        """Serialización JSON: conserva `severity`; los campos nuevos se incluyen solo si tienen valor."""
        d = {"id": self.id, "severity": self.severity, "message": self.message, "evidence": self.evidence}
        for name in ("tipo", "gravedad", "estado_verificacion", "efecto_generacion", "regla_id", "regla_version"):
            if getattr(self, name) is not None:
                d[name] = getattr(self, name)
        if self.faltante:
            d["faltante"] = [dict(x) if isinstance(x, dict) else x for x in self.faltante]
        return d


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
    def label(self) -> str:
        """'agosto' (mensual) o 'Q3 2026' (trimestral): lo que va en el texto."""
        return self.month_name if self.periodicity == "mensual" else f"Q{self.index} {self.year}"

    @property
    def prev_year_label(self) -> str:
        return f"Q{self.index} {self.year - 1}" if self.periodicity == "trimestral" else str(self.year - 1)

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


@dataclass
class GRow:
    key: str                              # "CENTRO", "Mounjaro", "18-24"…
    dim2: str = ""                        # p. ej. sexo en producto×sexo
    values: dict[str, Value] = field(default_factory=dict)
    share: Value | None = None            # calculado: base ÷ Σ del bloque
    delta: Value | None = None            # %Δ: motor (si hay bloque anterior) o pegado
    delta_src: Literal["engine", "pasted", "none"] = "none"
    pasted_delta: Value | None = None
    engine_delta: Value | None = None     # recálculo contra el bloque anterior (contraste)
    ticket_calc: Value | None = None      # Monto ÷ Pedidos
    pasted_ticket: Value | None = None    # el ticket que trae el Excel (solo contraste)
    delta_yoy: Value | None = None        # %Δ contra el mismo periodo del año anterior (solo datos crudos)


@dataclass
class GBlock:
    name: str                             # "region", "edad_producto:mounjaro"…
    sheet: str
    origin: str                           # coordenada del encabezado
    rows: list[GRow]
    declared_total: dict[str, Value] = field(default_factory=dict)   # fila "Total" del Excel
    basis: str = ""
    role: str = "main"                    # main | prior
