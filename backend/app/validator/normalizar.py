"""Lectura y normalización para el motor de reglas (Fase 2A): construye un `Contexto` de SOLO LECTURA.

Reutiliza el lector existente (`raw.common.read_tables`, mismas columnas obligatorias que `raw.glp1`/`raw.aetops`); no
duplica el parseo de fechas ni de números. No filtra ni corrige datos: guarda todas las líneas tal como llegan, y cada
regla decide qué comparar. Las columnas y hojas realmente presentes quedan registradas para poder declarar `faltante`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

from ..calc import indicators as ind
from ..models import Finding, Period
from ..raw import aetops as raw_aetops
from ..raw import glp1 as raw_glp1
from ..raw.common import norm, read_tables, to_date


@dataclass(frozen=True)
class Linea:
    """Una fila de `ventas` (una línea de pedido), normalizada."""
    fila: int
    id_pedido: str
    id_paciente: str
    fecha: date | None
    sku: str
    monto: Decimal | None
    piezas: Decimal | None
    valores: dict = field(default_factory=dict, compare=False, hash=False)      # todas las columnas de la fila (texto normalizado)


@dataclass
class Contexto:
    unidad: str                                           # "GLP1" | "AETOPS"
    periodo: Period
    archivo: str = ""
    columnas: dict[str, set[str]] = field(default_factory=dict)       # hoja -> columnas presentes (normalizadas)
    lineas: list[Linea] = field(default_factory=list)
    catalogo: dict[str, dict] = field(default_factory=dict)           # sku -> fila del catálogo
    trafico_sitio: dict[tuple[int, int], dict] = field(default_factory=dict)   # (año, mes) -> {add_to_cart, compras, visitas}
    hallazgos_lectura: list[Finding] = field(default_factory=list)

    @property
    def hoja_trafico(self) -> bool:
        return "trafico" in self.columnas

    def ventana(self) -> tuple[int, set[int]]:
        """(año, meses) del periodo del reporte; misma definición que usa el motor actual (`raw.glp1._windows`)."""
        return raw_glp1._windows(self.periodo)["cur"]

    def en_periodo(self, fecha: date | None) -> bool:
        y, ms = self.ventana()
        return fecha is not None and fecha.year == y and fecha.month in ms

    def etiqueta_periodo(self) -> str:
        y, ms = self.ventana()
        return f"{y}-{min(ms):02d}" if len(ms) == 1 else f"{y}-{min(ms):02d}..{max(ms):02d}"

    def lineas_periodo(self) -> list[Linea]:
        return [ln for ln in self.lineas if self.en_periodo(ln.fecha)]

    def pedidos_sistema_ventas(self) -> set[str]:
        """Pedidos del sistema de ventas del periodo, con los MISMOS criterios que el motor actual (`raw.glp1.build`):
        fecha legible, importe y piezas numéricos, id_pedido/id_paciente/sku no vacíos y SKU presente en el catálogo."""
        return {ln.id_pedido for ln in self.lineas_periodo()
                if ln.monto is not None and ln.piezas is not None and ln.id_pedido and ln.id_paciente and ln.sku and ln.sku in self.catalogo}


class ErrorLectura(Exception):
    """El archivo no existe o no se puede leer como libro de datos crudos (mensaje explicativo, sin traza técnica)."""


def _s(v) -> str:
    return "" if v is None else str(v).strip()


def construir_contexto(path: str | Path, period: Period) -> Contexto:
    unidad = period.unit
    specs = (dict(raw_glp1.SPECS) if unidad == "GLP1" else
             {"ventas": raw_aetops.VENTAS_REQ, "catalogo": raw_aetops.CATALOGO_REQ, "negados": raw_aetops.NEGADOS_REQ})
    if not Path(path).exists():
        raise ErrorLectura(f"No existe el archivo o carpeta de datos: {Path(path).name}")
    try:
        tabs, hallazgos = read_tables(path, specs, optional={"negados", "trafico"})
    except Exception as e:                                       # noqa: BLE001 — se traduce a un mensaje comprensible
        raise ErrorLectura(f"No se pudo leer {Path(path).name} como libro de datos crudos ({type(e).__name__}). "
                           "Verifica que sea un .xlsx válido o una carpeta con un CSV por tabla.") from e
    ctx = Contexto(unidad, period, Path(path).name, hallazgos_lectura=hallazgos)
    for hoja, filas in tabs.items():
        if filas:
            ctx.columnas[hoja] = {k for k in filas[0] if k != "_row"}
    for r in tabs.get("catalogo", []):
        if r.get("sku") is not None:
            ctx.catalogo[_s(r["sku"])] = {k: v for k, v in r.items() if k != "_row"}
    for r in tabs.get("ventas", []):
        ctx.lineas.append(Linea(r["_row"], _s(r.get("id_pedido")), _s(r.get("id_paciente")), to_date(r.get("fecha_pedido")),
                                _s(r.get("sku")), ind.to_dec(r.get("monto_venta")), ind.to_dec(r.get("piezas")),
                                {k: _s(v) for k, v in r.items() if k != "_row"}))
    # tráfico a nivel sitio: vista=general y sku vacío (los desgloses no suman el total y no se usan)
    acum: dict[tuple[int, int], dict] = {}
    for r in tabs.get("trafico", []):
        if norm(r.get("vista")) != "general" or _s(r.get("sku")):
            continue
        d = to_date(r.get("mes"))
        if d is None:
            continue
        a = acum.setdefault((d.year, d.month), {"add_to_cart": Decimal(0), "compras": Decimal(0), "visitas": Decimal(0)})
        for k in a:
            v = ind.to_dec(r.get(k))
            a[k] = None if (a[k] is None or v is None) else a[k] + v
    ctx.trafico_sitio = acum
    return ctx
