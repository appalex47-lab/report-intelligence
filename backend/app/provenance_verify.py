"""Fase 3A-3 · lectura y verificación de la procedencia registrada (docs/fase3a/ESPECIFICACION_FASE3A_PROCEDENCIA.md §3 y §7).

Distingue, sin mezclarlas, tres cosas (spec §3):

  * INTEGRIDAD del registro y de su copia: ¿la fila de `procedencia` es la que se escribió? ¿`procedencia.json` es idéntico a ella?
  * DISPONIBILIDAD de las fuentes originales (`comparar_fuentes`): ¿siguen estando, y sin cambios?
  * REPRODUCIBILIDAD: aquí solo se determinan las condiciones NEGATIVAS que la spec §3.2 fija con la integridad (sin manifiesto o legado,
    esquema desconocido, registro alterado, error de procedencia) → `no_reproducible`. Que un registro sea íntegro NO significa que el reporte
    pueda reproducirse: en ese caso el estado es `no_evaluada` (los estados exacta / parcial requieren regenerar y comparar: subfase 3A-4).

La tabla `procedencia` es la fuente AUTORITATIVA; `procedencia.json` es una copia: una copia alterada se detecta y se informa, pero NUNCA
sustituye al registro. Todo es de solo lectura (la tabla se abre en modo lectura, sin crear ni migrar nada), salvo `reexportar_copia`, que
únicamente escribe el archivo de copia con los bytes exactos del registro.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from . import provenance as pv
from .history import store as hist
from .provenance_capture import ARCHIVO_COPIA, ARCHIVO_ERROR, escribir_atomico

MAX_LECTURA = pv.MAX_MANIFIESTO_BYTES + 1


def _abrir_lectura(origen):
    """(conexión, abierta_aquí). Acepta una conexión o una ruta; una ruta se abre SOLO LECTURA y si no existe devuelve `(None, False)`."""
    if isinstance(origen, sqlite3.Connection):
        return origen, False
    p = Path(origen)
    if not p.is_file():
        return None, False
    con = sqlite3.connect(f"file:{p.as_posix()}?mode=ro", uri=True)
    return con, True


def _tiene_tabla(con) -> bool:
    return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='procedencia'").fetchone() is not None


def _leer_archivo(p: Path) -> tuple[bytes | None, str | None]:
    try:
        with p.open("rb") as fh:
            datos = fh.read(MAX_LECTURA)
    except FileNotFoundError:
        return None, "ausente"
    except OSError as e:
        return None, f"no se pudo leer: {type(e).__name__}"
    return datos, None


def _verificar_registro(fila: dict) -> tuple[str, list[str], dict | None]:
    """(estado, detalle, manifiesto) de una fila de `procedencia`: «presente» | «corrupto» | «esquema_no_soportado»."""
    detalle: list[str] = []
    if fila["esquema"] != pv.ESQUEMA:
        return "esquema_no_soportado", [f"esquema {fila['esquema']!r}: solo se entiende {pv.ESQUEMA!r}"], None
    if hashlib.sha256(fila["manifiesto"]).hexdigest() != fila["manifiesto_sha256"]:
        detalle.append("el SHA-256 de los bytes del manifiesto no coincide con manifiesto_sha256")
    m, errs = pv.leer_manifiesto(fila["manifiesto"])
    if m is None:
        detalle += [f"manifiesto no válido: {e}" for e in errs[:4]]
    else:
        if m["esquema"] != fila["esquema"]:
            detalle.append("el esquema de la fila no coincide con el del manifiesto")
        if m["hash_resultado"]["valor"] != fila["hash_resultado"]:
            detalle.append("hash_resultado de la fila no coincide con el del manifiesto")
    return ("corrupto" if detalle else "presente"), detalle, m


def verificar(origen, run_id: int, carpeta=None) -> dict:
    """Verifica la procedencia de una corrida. `origen`: conexión o ruta de la base del historial; `carpeta`: carpeta del reporte (opcional).

    Devuelve `registro`, `copia`, `error_de_generacion`, `integridad` y `reproducibilidad` (ver el docstring del módulo). Nunca lanza por datos
    corruptos: los describe. Solo lectura."""
    res = {"run_id": run_id,
           "registro": {"estado": "ausente", "detalle": [], "esquema": None, "manifiesto_sha256": None, "hash_resultado": None},
           "copia": {"estado": "no_aplica", "detalle": []}, "error_de_generacion": None, "integridad": "ausente",
           "reproducibilidad": {"estado": "no_reproducible", "causa": None, "tope": None}}
    fila, bytes_registro, manifiesto_registro = None, None, None
    try:
        con, propia = _abrir_lectura(origen)
        try:
            if con is not None and _tiene_tabla(con):
                fila = hist.get_procedencia(con, run_id)
        finally:
            if propia and con is not None:
                con.close()
    except sqlite3.Error as e:
        res["registro"] = {"estado": "ilegible", "detalle": [f"no se pudo leer la base: {type(e).__name__}"], "esquema": None,
                           "manifiesto_sha256": None, "hash_resultado": None}
    if fila is not None:
        estado, detalle, manifiesto_registro = _verificar_registro(fila)
        res["registro"] = {"estado": estado, "detalle": detalle, "esquema": fila["esquema"], "manifiesto_sha256": fila["manifiesto_sha256"],
                           "hash_resultado": fila["hash_resultado"]}
        bytes_registro = fila["manifiesto"]

    copia_valida = None
    if carpeta is not None:
        carpeta = Path(carpeta)
        datos, falla = _leer_archivo(carpeta / ARCHIVO_COPIA)
        if datos is None:
            res["copia"] = {"estado": "ausente" if falla == "ausente" else "ilegible", "detalle": [] if falla == "ausente" else [falla]}
        else:
            m, errs = pv.leer_manifiesto(datos)
            copia_valida = m
            if bytes_registro is not None:
                if datos == bytes_registro:
                    res["copia"] = {"estado": "integra", "detalle": []}
                else:
                    res["copia"] = {"estado": "alterada", "detalle": ["los bytes de la copia difieren de los del registro autoritativo"]
                                    + ([] if m is not None else [f"además no es válida: {e}" for e in errs[:3]])}
            elif m is None:
                res["copia"] = {"estado": "invalida", "detalle": [f"copia no válida: {e}" for e in errs[:4]]}
            else:
                res["copia"] = {"estado": "sin_registro", "detalle": ["la copia es válida pero no hay registro autoritativo con el que compararla"]}
        d_err, _ = _leer_archivo(carpeta / ARCHIVO_ERROR)
        if d_err is not None:
            try:
                e = json.loads(d_err.decode("utf-8"))
                res["error_de_generacion"] = {"etapa": e.get("etapa"), "tipo_error": e.get("tipo_error"), "mensaje": e.get("mensaje")}
            except (ValueError, UnicodeDecodeError, AttributeError):
                res["error_de_generacion"] = {"etapa": None, "tipo_error": "ilegible", "mensaje": None}

    reg, cop = res["registro"]["estado"], res["copia"]["estado"]
    rep = res["reproducibilidad"]
    if reg == "presente":
        res["integridad"] = "verificada"
        rep.update(estado="no_evaluada", causa="la integridad del registro está verificada; la reproducibilidad se evalúa regenerando (subfase 3A-4)", tope=None)
    elif reg in ("corrupto", "esquema_no_soportado", "ilegible"):
        res["integridad"] = "fallida"
        rep.update(estado="no_reproducible", causa={"corrupto": "el registro de procedencia está alterado o es inválido",
                                                    "esquema_no_soportado": "esquema de procedencia no soportado",
                                                    "ilegible": "no se pudo leer el historial"}[reg])
    elif cop == "sin_registro":
        res["integridad"] = "no_verificable"
        rep.update(estado="no_evaluada", causa="solo hay una copia sin registro autoritativo: la integridad no se puede verificar", tope="parcial")
    elif cop in ("invalida", "ilegible"):
        res["integridad"] = "fallida"
        rep.update(estado="no_reproducible", causa="la única copia de la procedencia no es válida")
    else:                                                                 # sin registro y sin copia
        res["integridad"] = "ausente"
        rep.update(estado="no_reproducible", causa=("procedencia no disponible por un error al generarla" if res["error_de_generacion"]
                                                    else "sin procedencia (reporte anterior a la Fase 3A: legado)"))
    return res


def comparar_fuentes(manifiesto, rutas) -> dict:
    """Disponibilidad de las fuentes originales frente a lo registrado. `manifiesto`: dict válido o sus bytes; `rutas`: archivos aportados.
    Por fuente devuelve `disponible` (algún archivo con el mismo SHA-256), `modificada` (hay uno con el mismo nombre pero otro contenido) o
    `ausente`. NO es un estado de reproducibilidad: solo informa de las entradas."""
    if isinstance(manifiesto, (bytes, bytearray)):
        manifiesto, errs = pv.leer_manifiesto(manifiesto)
        if manifiesto is None:
            raise pv.ErrorProcedencia("manifiesto no válido: " + "; ".join(errs[:3]))
    elif pv.validar_manifiesto(manifiesto):
        raise pv.ErrorProcedencia("manifiesto no válido")
    aportadas = []
    for r in rutas or []:
        p = Path(r)
        if p.is_file():
            aportadas.append((p.name, hist.sha256(p)))
    out = {}
    for f in manifiesto["archivos_fuente"]:
        if any(sha == f["sha256"] for _n, sha in aportadas):
            out[f["id"]] = "disponible"
        elif any(n == f["nombre"] for n, _s in aportadas):
            out[f["id"]] = "modificada"
        else:
            out[f["id"]] = "ausente"
    return out


def reexportar_copia(origen, run_id: int, carpeta, sustituir_alterada: bool = False) -> str:
    """Vuelve a escribir `procedencia.json` con los bytes EXACTOS del registro autoritativo (caso «registro sin copia»). Devuelve «creada»,
    «sin_cambios» o «sustituida». Una copia existente que difiere NO se sobrescribe salvo `sustituir_alterada=True` (es evidencia)."""
    con, propia = _abrir_lectura(origen)
    try:
        fila = hist.get_procedencia(con, run_id) if con is not None and _tiene_tabla(con) else None
    finally:
        if propia and con is not None:
            con.close()
    if fila is None:
        raise pv.ErrorProcedencia(f"la corrida {run_id} no tiene procedencia registrada")
    estado, detalle, _m = _verificar_registro(fila)
    if estado != "presente":
        raise pv.ErrorProcedencia("el registro no es íntegro, no se exporta: " + "; ".join(detalle[:2]))
    destino = Path(carpeta) / ARCHIVO_COPIA
    actual, _falla = _leer_archivo(destino)
    if actual == fila["manifiesto"]:
        return "sin_cambios"
    if actual is not None and not sustituir_alterada:
        raise pv.ErrorProcedencia("ya existe una copia distinta del registro; no se sobrescribe sin sustituir_alterada=True")
    escribir_atomico(destino, fila["manifiesto"])
    return "sustituida" if actual is not None else "creada"
