"""Fase 3A-4 · comparación por regeneración y estados de reproducibilidad (docs/fase3a/ESPECIFICACION_FASE3A_PROCEDENCIA.md §3).

Separación de responsabilidades (igual que en 3A-3):
  * `provenance.comparar`  (puro)  clasifica la evidencia: C1 a C7 → `exacta` / `parcial` / `no_reproducible` / `no_evaluada`.
  * `provenance_verify`            integridad del registro y de su copia (C1, C2).
  * este módulo (con E/S)          reúne la evidencia ACTUAL (versiones, plantilla, configuración, fuentes aportadas), decide si hay que
                                   regenerar, REGENERA de verdad cuando se le pide y entrega todo a `comparar`.

Garantías:
  * Solo lectura sobre la evidencia original: el historial se abre en modo lectura y no se escribe ningún archivo del reporte ni del historial.
  * Nunca regenera en silencio: solo regenera si el llamador entrega un `regenerar` Y C1 a C6 ya pasan (si no, no habría nada equivalente que
    regenerar y el estado se decide sin ejecutar nada).
  * Un fallo, de cualquier tipo, jamás se presenta como éxito: se devuelve `no_evaluada` con la causa; nunca `exacta`.
  * `evaluar` no lanza por datos corruptos ni por fallos de la regeneración: los describe.
"""
from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from . import config, provenance as pv, version
from . import provenance_capture as cap
from . import provenance_verify as ver
from .history import store as hist
from .models import Period

_FORMATO = {"aetops": "AETOPS", "glp1": "GLP1"}


def estado_actual(period: Period | None, template=None, targets=None, context=None, ia=None) -> dict:
    """Evidencia ACTUAL con las mismas funciones que usa la captura (`provenance_capture`). Lo que no se puede leer queda en `None`
    (= sin evidencia), nunca se rellena con un valor supuesto."""
    def intento(f):
        try:
            return f()
        except Exception:                                                  # noqa: BLE001 - sin evidencia, no un error: lo decide `comparar`
            return None
    v = intento(version.versiones)
    return {
        "version_codigo": {"app": v["app"], "commit": v["commit"]} if v else None,
        "version_motor": {"engine": v["motor"]} if v else None,
        "version_definiciones": intento(lambda: {"archivo": config.ARCHIVOS["definiciones"], "version": config.versiones()["definiciones"]}),
        "version_reglas": intento(cap.version_reglas),
        "version_plantillas": intento(lambda: [cap.describir_plantilla(template, period)]) if template is not None and period is not None else None,
        "configuracion": intento(lambda: cap.configuracion(targets, context, ia)),
        "entorno": intento(cap.entorno),
    }


def fuentes_aportadas(rutas) -> tuple[list[dict], list[str]]:
    """(`[{"nombre", "sha256"}]`, avisos). Una ruta que no es un archivo legible NO se cuenta como aportada (y se avisa)."""
    out, avisos = [], []
    for r in rutas or []:
        p = Path(r)
        try:
            if not p.is_file():
                raise OSError("no es un archivo")
            out.append({"nombre": cap._nombre_seguro(p.name), "sha256": hist.sha256(p)})
        except OSError as e:
            avisos.append(f"la fuente «{cap._nombre_seguro(p.name)}» no se pudo leer ({type(e).__name__}); no se cuenta como aportada")
    return out, avisos


def _abrir(origen):
    if isinstance(origen, sqlite3.Connection):
        return origen, False
    p = Path(origen) if origen is not None else None
    if p is None or not p.is_file():
        return None, False
    return sqlite3.connect(f"file:{p.as_posix()}?mode=ro", uri=True), True


def _manifiesto_y_periodo(origen, run_id: int, carpeta, verif: dict) -> tuple[dict | None, Period | None]:
    """Manifiesto contra el que comparar: el del REGISTRO si es íntegro; si no hay registro, el de la copia válida (D-B). El periodo sale de
    `runs` (solo lectura) cuando existe."""
    manifiesto, periodo = None, None
    try:
        con, propia = _abrir(origen)
        try:
            if con is not None:
                if verif["registro"]["estado"] == "presente":
                    fila = hist.get_procedencia(con, run_id)
                    manifiesto = pv.leer_manifiesto(fila["manifiesto"])[0] if fila else None
                r = con.execute("SELECT unit, periodicity, year, idx FROM runs WHERE id=?", (run_id,)).fetchone() \
                    if con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='runs'").fetchone() else None
                if r:
                    periodo = Period(r[0], r[1], r[2], r[3])
        finally:
            if propia and con is not None:
                con.close()
    except sqlite3.Error:
        manifiesto = None
    if manifiesto is None and verif["registro"]["estado"] == "ausente" and verif["copia"]["estado"] == "sin_registro" and carpeta is not None:
        datos, _f = ver._leer_archivo(Path(carpeta) / cap.ARCHIVO_COPIA)
        manifiesto = pv.leer_manifiesto(datos)[0] if datos is not None else None
    if periodo is None and manifiesto is not None and manifiesto["version_plantillas"]:
        formato = manifiesto["version_plantillas"][0]["id"].split("/")[0]                    # «aetops-mensual/1» → unidad y periodicidad
        unidad, _s, per = formato.partition("-")
        if unidad in _FORMATO and per in ("mensual", "trimestral"):
            periodo = Period(_FORMATO[unidad], per, 0, 1)                                    # solo se usa para identificar el formato de la plantilla
    return manifiesto, periodo


def evaluar(origen, run_id: int, *, carpeta=None, fuentes=None, template=None, targets=None, context=None, ia=None, regenerar=None) -> dict:
    """Evalúa la reproducibilidad de la corrida `run_id` (spec §3). `origen`: conexión o ruta del historial; `carpeta`: carpeta del reporte;
    `fuentes`: rutas de los libros aportados de nuevo; `template`, `targets`, `context`, `ia`: la plantilla y la configuración ACTUALES;
    `regenerar`: `None` (no regenerar) o un callable sin argumentos que realiza la regeneración real y devuelve el `hash_resultado` obtenido
    (cualquier excepción cuenta como regeneración fallida, nunca como éxito). Devuelve el resultado de `provenance.comparar` más `avisos`."""
    avisos: list[str] = []
    try:
        verif = ver.verificar(origen, run_id, carpeta)
        manifiesto, periodo = _manifiesto_y_periodo(origen, run_id, carpeta, verif)
        aportadas, avisos = fuentes_aportadas(fuentes) if fuentes is not None else (None, [])
        actual = estado_actual(periodo, template, targets, context, ia)
        previo = pv.comparar(verificacion=verif, registrado=manifiesto, actual=actual, fuentes_aportadas=aportadas, regeneracion=None)
        resultado = previo
        # Solo se regenera si hay algo equivalente que regenerar: C1 a C6 en verde (el estado previo es «no_evaluada»). Nunca antes.
        if regenerar is not None and previo["estado"] == "no_evaluada" and previo["comprobaciones"]["C7"]["resultado"] == "no_evaluada":
            try:
                regen = {"hash_resultado": regenerar()}
            except Exception as e:                                          # noqa: BLE001 - la regeneración fallida NO es un éxito
                regen = {"error": f"{type(e).__name__}: {e}"}
            resultado = pv.comparar(verificacion=verif, registrado=manifiesto, actual=actual, fuentes_aportadas=aportadas, regeneracion=regen)
        elif regenerar is not None:
            avisos.append("no se regeneró: C1 a C6 no pasan, así que no hay un resultado equivalente que comparar")
    except Exception as e:                                                  # noqa: BLE001 - jamás un fallo interno como éxito
        return {"esquema": pv.ESQUEMA_COMPARACION, "estado": "no_evaluada", "causa": f"error al comparar: {pv.nfc(pv.rutas_a_nombre_base(str(e)))[:300]}",
                "comprobaciones": {}, "diferencias": [], "notas": [], "alertas": [], "regeneracion": {"ejecutada": False, "hash_registrado": None,
                                                                                                    "hash_regenerado": None, "error": None},
                "evidencia": {"run_id": run_id, "manifiesto_sha256": None, "integridad": None, "copia": None}, "avisos": avisos}
    resultado["avisos"] = avisos
    return resultado


def regenerador(*, period: Period, fuentes, template, targets=None, context=None, edits=None, discovery=None, ia=None):
    """Devuelve el callable que `evaluar` ejecuta para REGENERAR de verdad: corre el motor sobre las fuentes aportadas y construye el reporte
    completo (con la plantilla actual) en una carpeta temporal, SIN historial, y devuelve el `hash_resultado` que calcula la captura de
    procedencia de esa construcción (el mismo código y el mismo contrato 3A-2 que el reporte original). No toca nada fuera de la carpeta
    temporal, que se borra al terminar. Si algo falla lanza (no devuelve un hash de relleno)."""
    fuentes = [Path(f) for f in fuentes]

    def correr() -> str:
        from .build import build_aetops, build_glp1
        from .pipeline import run_aetops, run_aetops_raw, run_glp1, run_glp1_raw
        from .raw.aetops import is_raw_workbook
        if len(fuentes) != 1:
            raise cap.ErrorCaptura("entradas", "la regeneración necesita exactamente un libro de entrada")
        p = fuentes[0]
        with tempfile.TemporaryDirectory(prefix="regeneracion_") as td:
            if period.unit == "GLP1":
                res = run_glp1_raw(p, period) if is_raw_workbook(p) else run_glp1(p, period.periodicity, period)
                b = build_glp1(res, period, Path(template), Path(td) / "out", narrative=edits or None, sources=[p], context=context or None,
                               targets=targets, history_db=None, render=False, discovery=discovery, ia=ia)
            else:
                res = (run_aetops_raw(p, period, targets=targets, require_targets=True) if is_raw_workbook(p)
                       else run_aetops(p, period.periodicity, period, targets=targets, require_targets=True))
                b = build_aetops(res, period, Path(template), Path(td) / "out", narrative=edits or None, context=context or None,
                                 history_db=None, sources=[p], targets=targets, render=False, discovery=discovery, ia=ia)
            proc = b.procedencia or {}
            if proc.get("estado") != "copia_sin_registro" or not proc.get("hash_resultado"):
                raise RuntimeError(f"la regeneración no produjo un hash_resultado (estado {proc.get('estado')!r}, etapa {proc.get('etapa')!r})")
            return proc["hash_resultado"]
    return correr
