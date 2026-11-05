"""Fase 3A-3 · captura y registro de la procedencia de un reporte (docs/fase3a/ESPECIFICACION_FASE3A_PROCEDENCIA.md §5, §7 y §8).

Qué hace, en este orden, DESPUÉS de que el PPTX y la fila de `runs` ya existen (nunca antes: no puede alterar el reporte):

  1. entradas        describe cada archivo fuente (SHA-256, tamaño, filas, columnas, periodo), la plantilla, la configuración y el entorno
  2. canonico        calcula `hash_resultado` con el contrato de 3A-2 (`provenance.calcular`), sin tocar ese contrato
  3. manifiesto      arma y VALIDA el manifiesto (esquema cerrado `procedencia/1`)
  4. serializacion   serializa UNA sola vez (bytes exactos)
  5. historial       inserta la fila en la tabla autoritativa `procedencia` (si hay historial)
  6. archivo         escribe `procedencia.json` (copia verificable) de forma atómica con esos mismos bytes

Orden de 5 y 6: primero el registro autoritativo y después la copia. Así un fallo entre los dos deja «registro sin copia» (se puede
volver a exportar la copia idéntica, `provenance_verify.reexportar_copia`) y nunca «copia sin registro» cuando hay historial.

Si algo falla, el reporte ya generado NO se pierde ni se altera (D-A): se registra `procedencia_error.json` (si se puede), no queda un
`procedencia.json` incompleto ni una fila parcial, y la función devuelve el detalle. Esta función NO lanza nunca.

No hay escritura fuera de la carpeta del reporte (nombres fijos), ni secretos, ni contenido de celdas: solo nombres de columnas, conteos,
SHA-256, versiones y la configuración aplicada.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
import tempfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from . import config, provenance as pv, version
from .history import store as hist
from .narrative.rules import RULES
from .raw import common as raw_common

ARCHIVO_COPIA = "procedencia.json"
ARCHIVO_ERROR = "procedencia_error.json"
MOTOR_REGLAS_EJECUTADO = False          # el motor de reglas aún no está conectado a los reportes (spec H-4): nunca se ejecuta al generar
NOTA_MOTOR = ("El motor de reglas no se ejecutó en esta generación; las versiones listadas son metadatos del catálogo, no resultados.")
COLUMNAS_FECHA = frozenset({"fecha_pedido", "fecha", "mes"})
MAX_FILAS_POR_HOJA = 2_000_000
MAX_NOMBRE = 255


class ErrorCaptura(pv.ErrorProcedencia):
    """Fallo de una etapa de la captura (`etapa` es una de `provenance.ETAPAS_ERROR`)."""

    def __init__(self, etapa: str, mensaje: str):
        super().__init__(mensaje)
        self.etapa = etapa


# ------------------------------------------------------------------------------------------------------------------- entradas
def _nombre_seguro(nombre) -> str:
    base = pv.nfc(Path(str(nombre)).name)
    base = "".join(c if c.isprintable() else "?" for c in base)[:MAX_NOMBRE].strip()
    return base or "sin_nombre"


def _inspeccionar_libro(p: Path) -> tuple[dict, dict, str | None]:
    """(filas por hoja, columnas por hoja, periodo detectado) con `openpyxl` en solo lectura. No guarda ningún valor de celda."""
    import openpyxl
    filas: dict[str, int] = {}
    columnas: dict[str, list[str]] = {}
    minimo = maximo = None
    wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
    try:
        for i, ws in enumerate(wb.worksheets, 1):
            clave = raw_common.norm(ws.title) or f"hoja_{i}"
            if clave in filas:
                raise ErrorCaptura("entradas", f"dos hojas del libro dan el mismo nombre normalizado ({clave!r})")
            it = ws.iter_rows(values_only=True)
            encabezado = [raw_common.norm(c) for c in next(it, ())]
            columnas[clave] = [c for c in encabezado if c]
            idx_fecha = [k for k, c in enumerate(encabezado) if c in COLUMNAS_FECHA]
            n = 0
            for r in it:
                if r is None or all(c in (None, "") for c in r):
                    continue
                n += 1
                if n > MAX_FILAS_POR_HOJA:
                    raise ErrorCaptura("entradas", f"la hoja {clave!r} excede {MAX_FILAS_POR_HOJA} filas")
                for k in idx_fecha:
                    if k < len(r):
                        d = raw_common.to_date(r[k])
                        if d is not None:
                            minimo = d if minimo is None or d < minimo else minimo
                            maximo = d if maximo is None or d > maximo else maximo
            filas[clave] = n
    finally:
        wb.close()
    if minimo is None:
        return filas, columnas, None
    a, b = minimo.strftime("%Y-%m"), maximo.strftime("%Y-%m")
    return filas, columnas, a if a == b else f"{a}..{b}"


def describir_fuente(path) -> dict:
    """`{"nombre", "tamano_bytes", "sha256", "filas", "columnas", "periodo_detectado"}` de un archivo fuente. El SHA-256 es el mismo que
    guarda el historial para esa fuente (`history.store.sha256`)."""
    p = Path(path)
    if p.is_dir():
        raise ErrorCaptura("entradas", "una carpeta de CSV no es un archivo fuente registrable")
    if not p.is_file():
        raise ErrorCaptura("entradas", f"la fuente «{p.name}» no existe")
    filas, columnas, periodo = _inspeccionar_libro(p) if p.suffix.lower() == ".xlsx" else ({}, {}, None)
    return {"nombre": _nombre_seguro(p.name), "tamano_bytes": p.stat().st_size, "sha256": hist.sha256(p),
            "filas": filas, "columnas": columnas, "periodo_detectado": periodo}


def describir_plantilla(template, period) -> dict:
    p = Path(template)
    if not p.is_file():
        raise ErrorCaptura("entradas", f"la plantilla «{p.name}» no existe")
    formato = f"{period.unit.lower()}-{period.periodicity}"
    version_dir = p.parent.name if p.parent.name.isdigit() and p.parent.parent.name == formato else "desconocida"
    return {"id": f"{formato}/{version_dir}", "nombre": _nombre_seguro(p.name), "sha256": hist.sha256(p)}


def entorno() -> dict:
    """Versiones de Pyodide, Python y python-pptx como información diagnóstica (fuera del hash, spec §3.4). «desconocido» si no se leen."""
    def leer(f):
        try:
            v = f()
            return str(v) if v else "desconocido"
        except Exception:                                  # noqa: BLE001 - es información auxiliar, nunca debe impedir la captura
            return "desconocido"

    def pyodide():
        if sys.platform != "emscripten":
            return None
        import pyodide as _p
        return _p.__version__

    def pptx():
        import pptx as _p
        return _p.__version__
    return {"pyodide": leer(pyodide), "python": leer(platform.python_version), "python_pptx": leer(pptx)}


def zona_horaria() -> str | None:
    """Zona horaria del navegador (en Pyodide, vía `js`); `None` si no se puede leer. No se inventa."""
    try:
        if sys.platform == "emscripten":
            from js import Intl                            # type: ignore[import-not-found]
            z = str(Intl.DateTimeFormat().resolvedOptions().timeZone)
            return z or None
    except Exception:                                      # noqa: BLE001
        return None
    return None


def _texto(v) -> str | int:
    if isinstance(v, bool):
        raise ErrorCaptura("entradas", "un valor de configuración booleano no es válido aquí")
    if isinstance(v, int):
        return v
    if isinstance(v, (Decimal, float)):
        return str(v) if isinstance(v, Decimal) else repr(v)
    return str(v)


def configuracion(targets=None, context=None, ia=None) -> dict:
    """Configuración EFECTIVAMENTE aplicada: metas capturadas, umbrales y escenarios de `NarrativeRules` (los que usa la narrativa),
    contexto del equipo (solo conteo y SHA-256, no el texto) y uso de IA declarado por quien generó el reporte (`None` = no declarado)."""
    metas = {str(k): _texto(v) for k, v in sorted((targets.to_dict() if targets is not None else {}).items())}
    escenarios_ids = {"recovery_scenario": "recuperacion_negados", "cart_recovery_scenario": "recuperacion_carritos"}
    umbrales, escenarios = {}, {}
    for nombre in sorted(RULES.__dataclass_fields__):
        v = getattr(RULES, nombre)
        if nombre == "actionability":
            for k, w in v:
                umbrales[f"actionability.{k}"] = _texto(w)
        elif nombre in escenarios_ids:
            escenarios[escenarios_ids[nombre]] = _texto(v)
        else:
            umbrales[nombre] = _texto(v)
    lineas = [pv.nfc(str(c).strip()) for c in (context or []) if c and str(c).strip()]
    ctx_sha = hashlib.sha256("\n".join(lineas).encode("utf-8")).hexdigest()
    if ia is None:
        ia_cfg = {"usada": None, "modelo_declarado": None}
    else:
        modelo = ia.get("modelo_declarado")
        ia_cfg = {"usada": ia.get("usada") if isinstance(ia.get("usada"), bool) else None,
                  "modelo_declarado": pv.nfc(str(modelo))[:80] if modelo else None}
    return {"metas": metas, "umbrales": umbrales, "escenarios": escenarios, "contexto": {"lineas": len(lineas), "sha256": ctx_sha}, "ia": ia_cfg}


def version_reglas() -> dict:
    """Versión del catálogo y de cada regla con su estado de validación, MÁS el registro de que el motor no se ejecutó (spec H-4)."""
    cat = config.cargar("reglas")
    registro = {e["regla_id"]: e for e in config.cargar("validacion_registro")["reglas"]}
    reglas = []
    for r in cat["reglas"]:
        e = registro.get(r["id"])
        if e is None:
            raise ErrorCaptura("entradas", f"la regla {r['id']} no tiene registro de validación (no se inventa su estado)")
        reglas.append({"regla_id": r["id"], "regla_version": r.get("version"), "validacion_sintetica": e["validacion_sintetica"],
                       "validacion_operacional": e["validacion_operacional"]})
    return {"catalogo": {"archivo": config.ARCHIVOS["reglas"], "version": cat["version"]}, "reglas": reglas,
            "ejecucion": {"motor_ejecutado": MOTOR_REGLAS_EJECUTADO, "resultados_incluidos": False,
                          "flags": {k: bool(v) for k, v in sorted(cat["flags"].items())}, "nota": NOTA_MOTOR}}


# ------------------------------------------------------------------------------------------------------------------- escritura
def escribir_atomico(destino: Path, datos: bytes) -> None:
    """Escribe `datos` en `destino` sin dejar nunca un archivo a medias: archivo temporal en la misma carpeta y `os.replace`. El nombre de
    destino lo fija este módulo (no viene del usuario); el temporal se borra siempre si algo falla."""
    destino = Path(destino)
    carpeta = destino.parent
    fd, tmp = tempfile.mkstemp(dir=carpeta, prefix=f".{destino.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(datos)
            fh.flush()
            try:
                os.fsync(fh.fileno())
            except OSError:
                pass
        os.replace(tmp, destino)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _ahora_utc(ahora: datetime | None) -> str:
    return (ahora or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _mensaje_seguro(exc: BaseException) -> str:
    return pv.nfc(pv.rutas_a_nombre_base(f"{exc}"))[:500]


def registrar_error(carpeta, etapa: str, exc: BaseException, period, pptx=None, run_id=None, ahora=None) -> str | None:
    """Escribe `procedencia_error.json` (spec §8.4 E-2) asociado al reporte. Devuelve su nombre o `None` si ni eso se pudo escribir."""
    try:
        doc = {"esquema": pv.ESQUEMA_ERROR, "tipo_error": type(exc).__name__, "mensaje": _mensaje_seguro(exc),
               "etapa": etapa if etapa in pv.ETAPAS_ERROR else "manifiesto", "fecha_utc": _ahora_utc(ahora),
               "reporte": {"unidad": period.unit, "periodicidad": period.periodicity, "anio": period.year, "indice": period.index,
                           "pptx": _nombre_seguro(pptx) if pptx else None, "run_id": run_id}}
        datos = (json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True) + "\n").encode("utf-8")
        escribir_atomico(Path(carpeta) / ARCHIVO_ERROR, datos)
        return ARCHIVO_ERROR
    except Exception:                                      # noqa: BLE001 - E-7: si ni el error se puede escribir, lo devuelve el llamador
        return None


def _quitar(carpeta: Path, nombre: str) -> None:
    try:
        (carpeta / nombre).unlink()
    except FileNotFoundError:
        pass


# ------------------------------------------------------------------------------------------------------------------- orquestación
def construir(*, period, result, narrative, sources, template, targets=None, context=None, ia=None, ahora=None) -> tuple[dict, bytes]:
    """Arma el manifiesto y sus bytes exactos sin escribir nada. Lanza `ErrorCaptura` (con su etapa) ante cualquier fallo."""
    try:
        descritas = [describir_fuente(p) for p in (sources or [])]
        plantilla = describir_plantilla(template, period)
        cfg = configuracion(targets, context, ia)
        reglas = version_reglas()
        vdef = config.versiones()["definiciones"]
        env = entorno()
        v = version.versiones()
    except ErrorCaptura:
        raise
    except Exception as e:                                 # noqa: BLE001
        raise ErrorCaptura("entradas", f"no se pudieron leer las entradas: {_mensaje_seguro(e)}") from e
    try:
        hash_res = pv.calcular(period, [{"nombre": d["nombre"], "sha256": d["sha256"]} for d in descritas], result, narrative)
        lista, _mapa = pv.fuentes_canonicas([{"nombre": d["nombre"], "sha256": d["sha256"]} for d in descritas])
    except pv.ErrorProcedencia as e:
        raise ErrorCaptura("canonico", _mensaje_seguro(e)) from e
    except Exception as e:                                 # noqa: BLE001
        raise ErrorCaptura("canonico", f"fallo inesperado al calcular el resultado canónico: {_mensaje_seguro(e)}") from e
    try:
        por_sha: dict[str, dict] = {}
        for d in sorted(descritas, key=lambda x: x["nombre"]):          # mismo contenido y distinto nombre: una sola fuente (la 1.ª por nombre)
            por_sha.setdefault(d["sha256"], d)
        archivos = [{"id": f["id"], **{k: por_sha[f["sha256"]][k] for k in ("nombre", "tamano_bytes", "sha256", "filas", "columnas", "periodo_detectado")}}
                    for f in lista]
        m = pv.construir_manifiesto(
            version_codigo={"app": v["app"], "commit": v["commit"]}, version_motor={"engine": v["motor"]},
            version_definiciones={"archivo": config.ARCHIVOS["definiciones"], "version": vdef}, version_reglas=reglas,
            version_plantillas=[plantilla], archivos_fuente=archivos,
            fecha_generacion={"utc": _ahora_utc(ahora), "zona_horaria": zona_horaria()}, configuracion=cfg, hash_resultado=hash_res, entorno=env)
    except pv.ErrorProcedencia as e:
        raise ErrorCaptura("manifiesto", _mensaje_seguro(e)) from e
    except Exception as e:                                 # noqa: BLE001
        raise ErrorCaptura("manifiesto", f"fallo inesperado al armar el manifiesto: {_mensaje_seguro(e)}") from e
    try:
        return m, pv.serializar_manifiesto(m)
    except pv.ErrorProcedencia as e:
        raise ErrorCaptura("serializacion", _mensaje_seguro(e)) from e
    except Exception as e:                                 # noqa: BLE001
        raise ErrorCaptura("serializacion", f"fallo inesperado al serializar: {_mensaje_seguro(e)}") from e


def ejecutar(*, carpeta, period, result, narrative, sources, template, pptx=None, history_db=None, run_id=None, targets=None,
             context=None, ia=None, ahora=None) -> dict:
    """Captura y registra la procedencia. NUNCA lanza ni modifica el reporte. Devuelve el resultado de cada etapa:

    `estado`: «registrada» (fila + copia), «copia_sin_registro» (sin historial: solo `procedencia.json`), «registrada_sin_copia»
    (fila sin copia: `procedencia_error.json` explica por qué y se puede reexportar) o «error» (no queda ni fila ni copia)."""
    carpeta = Path(carpeta)
    out = {"estado": "error", "etapa": None, "run_id": run_id, "hash_resultado": None, "manifiesto_sha256": None, "archivo": None,
           "registro": None, "error": None, "archivo_error": None}
    etapa = "entradas"
    try:
        _quitar(carpeta, ARCHIVO_COPIA)                    # nunca quedan copias ni errores de una generación anterior en esta carpeta
        _quitar(carpeta, ARCHIVO_ERROR)
        m, datos = construir(period=period, result=result, narrative=narrative, sources=sources, template=template, targets=targets,
                             context=context, ia=ia, ahora=ahora)
        out["hash_resultado"] = m["hash_resultado"]["valor"]
        out["manifiesto_sha256"] = hashlib.sha256(datos).hexdigest()
        if history_db is not None:
            etapa = "historial"
            if run_id is None:
                raise ErrorCaptura("historial", "hay historial pero no se conoce la corrida que se registró")
            con = hist.connect(history_db)
            try:
                out["registro"] = hist.record_procedencia(con, run_id, datos)
            finally:
                con.close()
        etapa = "archivo"
        escribir_atomico(carpeta / ARCHIVO_COPIA, datos)
        out["archivo"] = ARCHIVO_COPIA
        out["estado"] = "registrada" if history_db is not None else "copia_sin_registro"
        return out
    except Exception as e:                                 # noqa: BLE001 - D-A: un fallo de procedencia no impide ni deshace el reporte
        etapa = e.etapa if isinstance(e, ErrorCaptura) else etapa
        out["etapa"], out["error"] = etapa, _mensaje_seguro(e)
        if out["registro"] in ("registrada", "ya_registrada"):
            out["estado"] = "registrada_sin_copia"
        else:
            out["estado"] = "error"
            _quitar(carpeta, ARCHIVO_COPIA)
        out["archivo_error"] = registrar_error(carpeta, etapa, e, period, pptx, run_id, ahora)
        return out
