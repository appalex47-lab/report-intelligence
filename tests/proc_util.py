"""Utilidades compartidas por las pruebas de procedencia (Fase 3A-3): libros, plantilla y corridas mínimas, sin datos reales ni plantillas con marca."""
from __future__ import annotations

import copy
import dataclasses
import shutil
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import openpyxl

from backend.app import provenance as pv
from backend.app import provenance_capture as cap
from backend.app.history import store as hist
from backend.app.models import Group, Lineage, Period, PeriodRow, Table, Value
from backend.app.narrative.writer import Para

SHA_A, SHA_B = "a" * 64, "b" * 64
P = Period("AETOPS", "mensual", 2026, 9)
AHORA = datetime(2026, 11, 5, 12, 0, 0, tzinfo=timezone.utc)


@dataclasses.dataclass
class R:
    """Un Result mínimo de AETOPS."""
    tables: dict
    findings: list
    products: dict = dataclasses.field(default_factory=dict)
    negados: dict = dataclasses.field(default_factory=dict)
    extras: dict = dataclasses.field(default_factory=dict)


def resultado(archivo="input.xlsx", x="10"):
    v = lambda a: Value(Decimal(a), "ok", Lineage(archivo, "ventas", "C3", "pasted"), "")          # noqa: E731
    g = Group("AE-A", PeriodRow("2025", {"monto": v("5")}), PeriodRow("2026", {"monto": v(x)}))
    return R({"aetops.linea.yoy": Table("aetops.linea.yoy", "yoy", [g])}, [])


def narrativa(*textos):
    return {"conclusiones": [Para(t, "hecho") for t in textos]}


def libro(destino: Path, filas=3, extra_hoja=False, nombre_hoja="ventas") -> Path:
    """Un .xlsx pequeño con una hoja `ventas` (con fechas) y, opcionalmente, otra hoja."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = nombre_hoja
    ws.append(["fecha_pedido", "id_pedido", "monto_venta"])
    for i in range(filas):
        ws.append([datetime(2026, 7 + i % 3, 1 + i), f"P{i}", 100 + i])
    ws.append([None, None, None])                                   # fila vacía: no cuenta
    if extra_hoja:
        w2 = wb.create_sheet("catalogo")
        w2.append(["sku", "producto"])
        w2.append(["S1", "Prolia"])
    wb.save(destino)
    return destino


def plantilla(base: Path, formato="aetops-mensual") -> Path:
    p = base / "templates" / formato / "1" / "template.pptx"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"PK\x03\x04 plantilla de prueba")
    return p


def historial(path: Path, template: Path | None = None, sources=None, periodo=P) -> tuple[Path, int]:
    """Crea (o abre) un historial real y registra una corrida con `record_run`, como hace `build._record`. Devuelve (ruta, run_id)."""
    con = hist.connect(path)
    try:
        rid = hist.record_run(con, periodo, [], profile=periodo.periodicity, template=template, sources=sources, qa_passed=True, downloadable=True)
    finally:
        con.close()
    return path, rid


def capturar(tmp: Path, *, sources=None, db=True, run_id=None, narr=None, resultado_=None, **kw) -> tuple[dict, Path, Path | None]:
    """Ejecuta `provenance_capture.ejecutar` sobre una carpeta de reporte nueva. Devuelve (salida, carpeta, ruta_historial)."""
    carpeta = tmp / "reporte"
    carpeta.mkdir(parents=True, exist_ok=True)
    tpl = plantilla(tmp)
    if sources is None:
        sources = [libro(tmp / "input.xlsx")]
    ruta_db = None
    if db:
        ruta_db, rid = historial(tmp / "historial" / "h.sqlite", tpl, sources)
        run_id = run_id or rid
    out = cap.ejecutar(carpeta=carpeta, period=P, result=resultado_ or resultado(), narrative=narr if narr is not None else narrativa("Hola"),
                       sources=sources, template=tpl, pptx=None, history_db=ruta_db, run_id=run_id, ahora=AHORA, **kw)
    return out, carpeta, ruta_db


def manifiesto_valido() -> dict:
    """Un manifiesto válido y determinista (construido a mano, sin leer archivos)."""
    return pv.construir_manifiesto(
        version_codigo={"app": "1.0.0", "commit": "0" * 40}, version_motor={"engine": "1.0.0"},
        version_definiciones={"archivo": "definiciones.json", "version": "1.0.0"},
        version_reglas={"catalogo": {"archivo": "reglas.json", "version": "1.1.0"},
                        "reglas": [{"regla_id": "R-REL-PAC-PED", "regla_version": "1.0.0", "validacion_sintetica": "aprobada",
                                    "validacion_operacional": "no_validada_con_datos_reales"}],
                        "ejecucion": {"motor_ejecutado": False, "resultados_incluidos": False, "flags": {"validacion_fase1": False},
                                      "nota": cap.NOTA_MOTOR}},
        version_plantillas=[{"id": "aetops-mensual/1", "nombre": "template.pptx", "sha256": SHA_A}],
        archivos_fuente=[{"id": "F1", "nombre": "input.xlsx", "tamano_bytes": 10, "sha256": SHA_B, "filas": {"ventas": 3},
                          "columnas": {"ventas": ["fecha_pedido"]}, "periodo_detectado": "2026-07..2026-09"}],
        fecha_generacion={"utc": "2026-11-05T12:00:00Z", "zona_horaria": None},
        configuracion={"metas": {"total": "100"}, "umbrales": {"relevance": "0.05"}, "escenarios": {"recuperacion_negados": "0.25"},
                       "contexto": {"lineas": 0, "sha256": SHA_A}, "ia": {"usada": None, "modelo_declarado": None}},
        hash_resultado={"algoritmo": "sha256", "contrato": pv.CONTRATO, "valor": SHA_A}, entorno={"pyodide": "desconocido", "python": "3.12.0", "python_pptx": "1.0.2"})


def mutado(m: dict, ruta: str, valor) -> dict:
    """Copia profunda de `m` con `ruta` («a.b.0.c») reemplazada por `valor` (o eliminada con `...`)."""
    x = copy.deepcopy(m)
    partes = ruta.split(".")
    cur = x
    for p in partes[:-1]:
        cur = cur[int(p)] if isinstance(cur, list) else cur[p]
    ult = partes[-1]
    if valor is ...:
        if isinstance(cur, list):
            del cur[int(ult)]
        else:
            del cur[ult]
    elif isinstance(cur, list):
        cur[int(ult)] = valor
    else:
        cur[ult] = valor
    return x
