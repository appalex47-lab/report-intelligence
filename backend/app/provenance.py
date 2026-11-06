"""Fase 3A-2 · resultado canónico y `hash_resultado` (docs/fase3a/ESPECIFICACION_FASE3A_PROCEDENCIA.md §6).

Funciones PURAS: reciben objetos que el sistema ya produjo y devuelven estructuras y bytes. No leen ni escriben archivos, no usan
la red, no consultan el reloj ni el entorno, no llaman al motor de reglas y NO modifican lo que reciben. Solo biblioteca estándar
(corre igual en CPython y en Pyodide). No está conectado a `build.py`, a la interfaz ni al historial (eso es 3A-3 y 3A-4).

Qué se calcula (spec §6.1): el RESULTADO FINAL del reporte, en cinco bloques:

    periodo     unidad, periodicidad, año e índice
    fuentes     [{"id": "F1", "sha256": …}], sin duplicados, ordenada por sha256
    valores     todos los `Value` del `Result` con su `Lineage` (`Decimal` exactos)
    hallazgos   id, severity, message, evidence y los siete campos de la Fase 1
    narrativa   por sección, los párrafos visibles finales (texto, tipo, editado), incluidos los editados a mano

Identidades distintas que NO se confunden:
    * identidad de las entradas: el `sha256` de cada archivo fuente (bloque `fuentes`; cambia con el contenido, no con el nombre);
    * resultado canónico: este módulo (`hash_resultado`), lo que significa `exacta` en la spec (§3.5);
    * igualdad binaria del PPTX: NO se calcula ni se promete aquí; el PPTX nunca es una entrada.

Decisiones donde la especificación deja un detalle abierto (todas compatibles con §6 y documentadas en
docs/fase3a/IMPLEMENTACION_3A2_HASH_CANONICO.md): `texto` = el texto del párrafo sin marcas de negrita (`**`), igual que el `texto` de
`narrative.json` (el hash no distingue cambios de solo formato); fuentes con
el mismo contenido son una sola; un nombre de archivo repetido con contenido distinto, un tipo de dato no previsto, una profundidad
excesiva o una colisión de claves lanzan `ErrorProcedencia` (en lugar de calcular un hash que oculte el problema).
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import re
import unicodedata
from decimal import Decimal
from enum import Enum
from pathlib import PurePath

from .models import Lineage

CONTRATO = "resultado_canonico/1"
ALGORITMO = "sha256"
MAX_PROFUNDIDAD = 64
BLOQUES = ("periodo", "fuentes", "valores", "hallazgos", "narrativa")

# Los campos de un hallazgo que entran al hash (spec §6.1): los cuatro históricos y los siete de la Fase 1.
CAMPOS_HALLAZGO = ("id", "severity", "message", "evidence", "tipo", "gravedad", "estado_verificacion", "efecto_generacion",
                   "faltante", "regla_id", "regla_version")
_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")


class ErrorProcedencia(ValueError):
    """Entrada que no se puede canonicalizar sin ocultar un problema. Nunca se calcula un hash «aproximado»."""


# ------------------------------------------------------------------------------------------------------------------- texto y rutas
def nfc(texto: str) -> str:
    return unicodedata.normalize("NFC", texto)


# Ruta absoluta de Windows (C:\x\y.xlsx, C:/x/y.xlsx), UNC (\\servidor\recurso\y.xlsx) o POSIX con al menos dos tramos (/dir/y.xlsx).
# Un tramo suelto («/s», «y/o», una fecha 12/05/2026) no es una ruta absoluta y no se toca.
_RUTA = re.compile(
    r"(?:(?<!\w)[A-Za-z]:(?:\\|/(?!/))[^\s\"'<>|*?]*)"
    r"|(?:\\\\[^\s\\\"'<>|*?]+\\[^\s\"'<>|*?]*)"
    r"|(?:(?<![\w/.:~\\-])/(?:[^\s/\"'<>|*?:;,()\\]+/)+[^\s/\"'<>|*?:;,()\\]*)")


def _nombre_base(ruta: str) -> str:
    partes = [p for p in re.split(r"[\\/]+", ruta) if p]
    return partes[-1] if partes else ruta


def rutas_a_nombre_base(texto: str) -> str:
    """Reemplaza cada ruta absoluta (POSIX o de Windows) por su nombre base (spec §6.4). El resto del texto no cambia."""
    return _RUTA.sub(lambda m: _nombre_base(m.group(0)), texto)


# ------------------------------------------------------------------------------------------------------------------- fuentes
def fuentes_canonicas(fuentes) -> tuple[list[dict], dict[str, str]]:
    """`fuentes`: iterable de `{"nombre": str, "sha256": str}` (el nombre puede traer ruta: solo cuenta el nombre base).

    Devuelve (`[{"id": "F1", "sha256": …}, …]` ordenada por sha256, `{nombre_base: id}`). Dos archivos con el mismo contenido son una
    sola fuente (misma identidad de entrada); un mismo nombre con contenido distinto es ambiguo y se rechaza."""
    por_sha: dict[str, set[str]] = {}
    for i, f in enumerate(fuentes or []):
        try:
            nombre, sha = f["nombre"], f["sha256"]
        except (KeyError, TypeError):
            raise ErrorProcedencia(f"fuentes[{i}]: debe ser un objeto con 'nombre' y 'sha256'") from None
        if not isinstance(nombre, str) or not nombre.strip():
            raise ErrorProcedencia(f"fuentes[{i}].nombre: debe ser un texto no vacío")
        if not isinstance(sha, str) or not _SHA256.match(sha):
            raise ErrorProcedencia(f"fuentes[{i}].sha256: debe ser SHA-256 en hexadecimal (64 caracteres)")
        por_sha.setdefault(sha.lower(), set()).add(nfc(_nombre_base(nombre)))
    ids = {sha: f"F{n}" for n, sha in enumerate(sorted(por_sha), 1)}
    mapa: dict[str, str] = {}
    for sha, nombres in por_sha.items():
        for n in nombres:
            if n in mapa and mapa[n] != ids[sha]:
                raise ErrorProcedencia(f"el archivo «{n}» aparece con contenido distinto: no se puede asociar su linaje a una fuente")
            mapa[n] = ids[sha]
    return [{"id": ids[s], "sha256": s} for s in sorted(por_sha)], mapa


# ------------------------------------------------------------------------------------------------------------------- canonicalización
class _Ctx:
    def __init__(self, mapa: dict[str, str]):
        self.mapa = mapa


def _clave(k) -> str:
    """Clave canónica: `str(k)` como en `tools/capture_baseline.py::canon`, con los textos en NFC (también dentro de una clave-tupla)."""
    if isinstance(k, str):
        return nfc(k)
    if isinstance(k, tuple):
        return str(tuple(nfc(x) if isinstance(x, str) else x for x in k))
    return str(k)


def _canon(obj, ctx: _Ctx, depth: int = 0, rutas: bool = False):
    """Estructura JSON determinista. Misma semántica que `tools/capture_baseline.py::canon` salvo lo que la spec §6 cambia a propósito:
    texto en NFC, `Lineage.file` por `id` de fuente y rutas absolutas por su nombre base (solo en `message` y `evidence` de los hallazgos,
    que es donde la spec §6.4 lo indica); y un tipo no previsto, una profundidad excesiva o una colisión de claves son un ERROR
    (no un marcador que oculte el problema)."""
    if depth > MAX_PROFUNDIDAD:
        raise ErrorProcedencia(f"estructura demasiado profunda (más de {MAX_PROFUNDIDAD} niveles) o con ciclos")
    if obj is None or isinstance(obj, (bool, int)):
        return obj
    if isinstance(obj, str):
        return nfc(rutas_a_nombre_base(obj) if rutas else obj)
    if isinstance(obj, Decimal):
        return str(obj)                                        # texto exacto: Decimal('1.0') y Decimal('1.00') son distintos
    if isinstance(obj, float):
        return repr(obj)                                       # no se esperan floats; si aparece, igual que la línea base
    if isinstance(obj, Enum):
        return _canon(obj.value, ctx, depth + 1, rutas)
    if isinstance(obj, Lineage):
        return {"file": _linaje_archivo(obj.file, ctx), "sheet": _canon(obj.sheet, ctx, depth + 1),
                "cells": _canon(obj.cells, ctx, depth + 1), "transform": _canon(obj.transform, ctx, depth + 1)}
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {_clave(f.name): _canon(getattr(obj, f.name), ctx, depth + 1, rutas) for f in dataclasses.fields(obj)}
    if isinstance(obj, dict):
        out: dict = {}
        for k, v in obj.items():
            kc = _clave(k)
            if kc in out:
                raise ErrorProcedencia(f"dos claves distintas dan la misma clave canónica: {kc!r}")
            out[kc] = _canon(v, ctx, depth + 1, rutas)
        return out
    if isinstance(obj, (list, tuple)):
        return [_canon(v, ctx, depth + 1, rutas) for v in obj]
    if isinstance(obj, (set, frozenset)):
        return sorted((_canon(v, ctx, depth + 1, rutas) for v in obj), key=_texto_json)
    if isinstance(obj, PurePath):
        return nfc(_nombre_base(str(obj)))
    raise ErrorProcedencia(f"tipo no previsto en el resultado: {type(obj).__name__}")


def _linaje_archivo(valor, ctx: _Ctx):
    if valor is None or valor == "":
        return valor                                           # el valor vacío se conserva (spec §6.4)
    if not isinstance(valor, str):
        raise ErrorProcedencia(f"Lineage.file debe ser un texto, no {type(valor).__name__}")
    base = nfc(_nombre_base(rutas_a_nombre_base(valor)))
    return ctx.mapa.get(base, base)                            # si coincide con un archivo cargado: su id; si no, su nombre base


def _texto_json(x) -> str:
    return json.dumps(x, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


# ------------------------------------------------------------------------------------------------------------------- bloques
def _periodo(p) -> dict:
    try:
        unidad, periodicidad, anio, indice = p.unit, p.periodicity, p.year, p.index
    except AttributeError:
        raise ErrorProcedencia("periodo: debe tener unit, periodicity, year e index") from None
    if not (isinstance(unidad, str) and isinstance(periodicidad, str) and isinstance(anio, int) and isinstance(indice, int)
            and not isinstance(anio, bool) and not isinstance(indice, bool)):
        raise ErrorProcedencia("periodo: unit y periodicity deben ser texto; year e index, enteros")
    return {"unit": nfc(unidad), "periodicity": nfc(periodicidad), "year": anio, "index": indice}


def _valores(resultado, ctx: _Ctx) -> dict:
    if all(hasattr(resultado, a) for a in ("tables", "products", "negados", "extras")):
        claves = ("tables", "products", "negados", "extras")                 # AETOPS
    elif all(hasattr(resultado, a) for a in ("blocks", "funnel", "extras")):
        claves = ("blocks", "funnel", "extras")                              # GLP-1
    else:
        raise ErrorProcedencia("resultado: no es un Result de AETOPS (tables, products, negados, extras) ni de GLP-1 (blocks, funnel, extras)")
    return {k: _canon(getattr(resultado, k), ctx) for k in claves}


def _hallazgos(resultado, ctx: _Ctx) -> list:
    try:
        hs = list(resultado.findings)
    except (AttributeError, TypeError):
        raise ErrorProcedencia("resultado.findings: debe ser una lista de hallazgos") from None
    out = []
    for i, h in enumerate(hs):
        d = {}
        for c in CAMPOS_HALLAZGO:
            try:
                v = getattr(h, c)
            except AttributeError:
                raise ErrorProcedencia(f"hallazgos[{i}]: falta el campo {c!r}") from None
            d[c] = _canon(v, ctx, 1, rutas=c in ("message", "evidence"))
        out.append(d)
    return out


def _parrafo(p, seccion: str, i: int):
    """(texto, tipo, editado, visible) de un párrafo `Para` o de una entrada con forma de narrative.json."""
    if isinstance(p, dict):
        texto, tipo, editado = p.get("texto"), p.get("tipo"), p.get("editado", False)
        visible = p.get("visible_en_diapositiva", p.get("visible", True))
    else:
        try:
            texto, tipo, editado, visible = p.text, p.kind, getattr(p, "edited", False), getattr(p, "visible", True)
        except AttributeError:
            raise ErrorProcedencia(f"narrativa[{seccion}][{i}]: debe tener texto, tipo y editado") from None
    if not isinstance(texto, str) or not isinstance(tipo, str) or not isinstance(editado, bool) or not isinstance(visible, bool):
        raise ErrorProcedencia(f"narrativa[{seccion}][{i}]: texto y tipo deben ser texto; editado y visible, booleanos")
    return texto, tipo, editado, visible


def _narrativa(narrativa) -> dict:
    out = {}
    if narrativa is not None and not isinstance(narrativa, dict):
        raise ErrorProcedencia("narrativa: debe ser un diccionario {sección: [párrafos]}")
    for seccion, parrafos in (narrativa or {}).items():
        if not isinstance(seccion, str):
            raise ErrorProcedencia("narrativa: las secciones deben tener nombre de texto")
        clave = nfc(seccion)
        if clave in out:
            raise ErrorProcedencia(f"narrativa: la sección {clave!r} está repetida")
        if isinstance(parrafos, (str, bytes)) or not hasattr(parrafos, "__iter__"):
            raise ErrorProcedencia(f"narrativa[{seccion}]: debe ser una lista de párrafos")
        lista = []
        for i, p in enumerate(parrafos):
            texto, tipo, editado, visible = _parrafo(p, seccion, i)
            if visible:                                        # solo lo que sale en la lámina (spec §6.1)
                lista.append({"texto": nfc(texto.replace("**", "")), "tipo": nfc(tipo), "editado": editado})
        out[clave] = lista
    return out


# ------------------------------------------------------------------------------------------------------------------- API
def canonico(periodo, fuentes, resultado, narrativa=None) -> dict:
    """Resultado canónico (`resultado_canonico/1`) como estructura JSON. No modifica ninguno de sus argumentos.

    `fuentes`: `[{"nombre", "sha256"}]` de los archivos cargados (sin contenido). `resultado`: `Result` de AETOPS o de GLP-1.
    `narrativa`: `{sección: [párrafos finales]}`, p. ej. `FillReport.narrative` (después de aplicar ediciones y de ajustar a la lámina)."""
    lista, mapa = fuentes_canonicas(fuentes)
    ctx = _Ctx(mapa)
    return {"periodo": _periodo(periodo), "fuentes": lista, "valores": _valores(resultado, ctx),
            "hallazgos": _hallazgos(resultado, ctx), "narrativa": _narrativa(narrativa)}


def serializar(canon: dict) -> bytes:
    """Bytes que se entregan a SHA-256: JSON con claves ordenadas, sin espacios, `ensure_ascii=False`, UTF-8 (spec §6.3)."""
    if not isinstance(canon, dict):
        raise ErrorProcedencia("el resultado canónico debe ser un diccionario")
    try:
        return _texto_json_estricto(canon).encode("utf-8")
    except (UnicodeEncodeError, ValueError, TypeError) as e:
        raise ErrorProcedencia(f"el resultado canónico no se puede serializar: {e}") from None


def _texto_json_estricto(x) -> str:
    return json.dumps(x, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def sha256_hex(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def hash_resultado(canon: dict) -> dict:
    """Campo `hash_resultado` del manifiesto (spec §5): `{"algoritmo", "contrato", "valor"}`."""
    return {"algoritmo": ALGORITMO, "contrato": CONTRATO, "valor": sha256_hex(serializar(canon))}


def calcular(periodo, fuentes, resultado, narrativa=None) -> dict:
    """Atajo: canonicaliza y hashea. Equivale a `hash_resultado(canonico(...))`."""
    return hash_resultado(canonico(periodo, fuentes, resultado, narrativa))


def huellas_por_bloque(canon: dict) -> dict:
    """SHA-256 de cada bloque por separado. Es una AYUDA DE AUDITORÍA (qué bloque cambió); no forma parte del contrato ni del hash."""
    if not isinstance(canon, dict):
        raise ErrorProcedencia("el resultado canónico debe ser un diccionario")
    faltan = [b for b in BLOQUES if b not in canon]
    if faltan:
        raise ErrorProcedencia(f"resultado canónico incompleto: faltan {faltan}")
    return {b: sha256_hex(_texto_json_estricto(canon[b]).encode("utf-8")) for b in BLOQUES}


# ======================================================================================================================================
# Fase 3A-3 · manifiesto de procedencia (spec §5): construcción, validación estricta, serialización y lectura verificada.
# Siguen siendo funciones PURAS (sin archivos, reloj ni red): lo que lee o escribe un archivo vive en `provenance_capture.py` y
# `provenance_verify.py`. Aquí un manifiesto incompleto o inválido NUNCA se serializa ni se acepta (spec §8.4, E-3).
# ======================================================================================================================================
ESQUEMA = "procedencia/1"
ESQUEMA_ERROR = "procedencia_error/1"
MAX_MANIFIESTO_BYTES = 2_000_000
# Los nueve campos de §5.1 más los dos aditivos aprobados en la adenda (§2): `esquema` y `entorno`.
CAMPOS_MANIFIESTO = ("esquema", "version_codigo", "version_motor", "version_definiciones", "version_reglas", "version_plantillas",
                     "archivos_fuente", "fecha_generacion", "configuracion", "hash_resultado", "entorno")
ETAPAS_ERROR = ("entradas", "canonico", "manifiesto", "serializacion", "historial", "archivo")

_SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
_COMMIT = re.compile(r"^([0-9a-f]{40}(\+dirty)?|desconocido)$")
_SHA_MIN = re.compile(r"^[0-9a-f]{64}$")
_FECHA_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_ID_FUENTE = re.compile(r"^F[1-9]\d*$")
_VALIDACION_SINTETICA = ("pendiente", "aprobada", "fallida", "no_aplica")
_VALIDACION_OPERACIONAL = ("no_validada_con_datos_reales", "confirmada", "no_aplica")


def _nfc_arbol(x):
    if isinstance(x, str):
        return nfc(x)
    if isinstance(x, dict):
        out = {}
        for k, v in x.items():
            kc = nfc(k) if isinstance(k, str) else k
            if kc in out:
                raise ErrorProcedencia(f"dos claves del manifiesto coinciden tras normalizar a NFC: {kc!r}")
            out[kc] = _nfc_arbol(v)
        return out
    if isinstance(x, (list, tuple)):
        return [_nfc_arbol(v) for v in x]
    return x


def _es_texto(x) -> bool:
    return isinstance(x, str)


def _es_entero(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _solo_claves(d, claves, ruta, errs) -> bool:
    if not isinstance(d, dict):
        errs.append(f"{ruta}: debe ser un objeto")
        return False
    faltan = [k for k in claves if k not in d]
    sobran = [k for k in d if k not in claves]
    if faltan:
        errs.append(f"{ruta}: faltan campos {faltan}")
    if sobran:
        errs.append(f"{ruta}: campos no previstos {sobran}")
    return not faltan and not sobran


def validar_manifiesto(m) -> list[str]:
    """Errores del manifiesto contra el esquema `procedencia/1` (lista vacía = válido). Esquema CERRADO: faltantes y campos
    adicionales son errores (un campo nuevo exigiría otra versión del esquema). No interpreta reglas de negocio."""
    errs: list[str] = []
    if not _solo_claves(m, CAMPOS_MANIFIESTO, "manifiesto", errs):
        if not isinstance(m, dict):
            return errs
    if m.get("esquema") != ESQUEMA:
        errs.append(f"esquema: se esperaba {ESQUEMA!r} y llegó {m.get('esquema')!r}")

    vc = m.get("version_codigo")
    if _solo_claves(vc, ("app", "commit"), "version_codigo", errs):
        if not (_es_texto(vc["app"]) and _SEMVER.match(vc["app"])):
            errs.append("version_codigo.app: debe ser MAJOR.MINOR.PATCH")
        if not (_es_texto(vc["commit"]) and _COMMIT.match(vc["commit"])):
            errs.append("version_codigo.commit: debe ser un SHA de 40 hex (con o sin +dirty) o «desconocido»")
    vm = m.get("version_motor")
    if _solo_claves(vm, ("engine",), "version_motor", errs) and not (_es_texto(vm["engine"]) and _SEMVER.match(vm["engine"])):
        errs.append("version_motor.engine: debe ser MAJOR.MINOR.PATCH")
    vd = m.get("version_definiciones")
    if _solo_claves(vd, ("archivo", "version"), "version_definiciones", errs):
        if not (_es_texto(vd["archivo"]) and vd["archivo"]):
            errs.append("version_definiciones.archivo: debe ser un texto no vacío")
        if not (_es_texto(vd["version"]) and _SEMVER.match(vd["version"])):
            errs.append("version_definiciones.version: debe ser MAJOR.MINOR.PATCH")

    vr = m.get("version_reglas")
    if _solo_claves(vr, ("catalogo", "reglas", "ejecucion"), "version_reglas", errs):
        cat = vr["catalogo"]
        if _solo_claves(cat, ("archivo", "version"), "version_reglas.catalogo", errs) and not (_es_texto(cat["version"]) and _SEMVER.match(cat["version"])):
            errs.append("version_reglas.catalogo.version: debe ser MAJOR.MINOR.PATCH")
        if not isinstance(vr["reglas"], list):
            errs.append("version_reglas.reglas: debe ser una lista")
        else:
            vistas = set()
            for i, r in enumerate(vr["reglas"]):
                ruta = f"version_reglas.reglas[{i}]"
                if _solo_claves(r, ("regla_id", "regla_version", "validacion_sintetica", "validacion_operacional"), ruta, errs):
                    if not (_es_texto(r["regla_id"]) and r["regla_id"]) or r["regla_id"] in vistas:
                        errs.append(f"{ruta}.regla_id: debe ser un texto no vacío y único")
                    vistas.add(r["regla_id"] if _es_texto(r["regla_id"]) else None)
                    if r["regla_version"] is not None and not (_es_texto(r["regla_version"]) and _SEMVER.match(r["regla_version"])):
                        errs.append(f"{ruta}.regla_version: debe ser MAJOR.MINOR.PATCH o null")
                    if r["validacion_sintetica"] not in _VALIDACION_SINTETICA:
                        errs.append(f"{ruta}.validacion_sintetica: valor no válido")
                    if r["validacion_operacional"] not in _VALIDACION_OPERACIONAL:
                        errs.append(f"{ruta}.validacion_operacional: valor no válido")
        ej = vr["ejecucion"]
        if _solo_claves(ej, ("motor_ejecutado", "resultados_incluidos", "flags", "nota"), "version_reglas.ejecucion", errs):
            if not isinstance(ej["motor_ejecutado"], bool) or not isinstance(ej["resultados_incluidos"], bool):
                errs.append("version_reglas.ejecucion: motor_ejecutado y resultados_incluidos deben ser booleanos")
            elif ej["resultados_incluidos"] and not ej["motor_ejecutado"]:
                errs.append("version_reglas.ejecucion: no puede haber resultados de reglas si el motor no se ejecutó")
            if not (isinstance(ej["flags"], dict) and all(_es_texto(k) and isinstance(v, bool) for k, v in ej["flags"].items())):
                errs.append("version_reglas.ejecucion.flags: debe ser un objeto de booleanos")
            if not _es_texto(ej["nota"]):
                errs.append("version_reglas.ejecucion.nota: debe ser un texto")

    vp = m.get("version_plantillas")
    if not isinstance(vp, list):
        errs.append("version_plantillas: debe ser una lista")
    else:
        for i, p in enumerate(vp):
            ruta = f"version_plantillas[{i}]"
            if _solo_claves(p, ("id", "nombre", "sha256"), ruta, errs):
                if not (_es_texto(p["id"]) and p["id"]) or not (_es_texto(p["nombre"]) and p["nombre"]):
                    errs.append(f"{ruta}: id y nombre deben ser textos no vacíos")
                if not (_es_texto(p["sha256"]) and _SHA_MIN.match(p["sha256"])):
                    errs.append(f"{ruta}.sha256: debe ser SHA-256 en hexadecimal minúscula")

    af = m.get("archivos_fuente")
    if not isinstance(af, list):
        errs.append("archivos_fuente: debe ser una lista")
    else:
        shas = []
        for i, f in enumerate(af):
            ruta = f"archivos_fuente[{i}]"
            if not _solo_claves(f, ("id", "nombre", "tamano_bytes", "sha256", "filas", "columnas", "periodo_detectado"), ruta, errs):
                continue
            if f["id"] != f"F{i + 1}" or not _ID_FUENTE.match(str(f["id"])):
                errs.append(f"{ruta}.id: debe ser F{i + 1} (ids consecutivos por orden de sha256)")
            if not (_es_texto(f["nombre"]) and f["nombre"] and "/" not in f["nombre"] and "\\" not in f["nombre"]):
                errs.append(f"{ruta}.nombre: debe ser un nombre de archivo (sin ruta)")
            if not _es_entero(f["tamano_bytes"]) or f["tamano_bytes"] < 0:
                errs.append(f"{ruta}.tamano_bytes: debe ser un entero >= 0")
            if not (_es_texto(f["sha256"]) and _SHA_MIN.match(f["sha256"])):
                errs.append(f"{ruta}.sha256: debe ser SHA-256 en hexadecimal minúscula")
            else:
                shas.append(f["sha256"])
            if not (isinstance(f["filas"], dict) and all(_es_texto(k) and _es_entero(v) and v >= 0 for k, v in f["filas"].items())):
                errs.append(f"{ruta}.filas: debe ser un objeto {{hoja: entero >= 0}}")
            if not (isinstance(f["columnas"], dict) and all(_es_texto(k) and isinstance(v, list) and all(_es_texto(c) for c in v)
                                                            for k, v in f["columnas"].items())):
                errs.append(f"{ruta}.columnas: debe ser un objeto {{hoja: [nombres]}}")
            if f["periodo_detectado"] is not None and not _es_texto(f["periodo_detectado"]):
                errs.append(f"{ruta}.periodo_detectado: debe ser texto o null")
        if shas != sorted(shas) or len(set(shas)) != len(shas):
            errs.append("archivos_fuente: deben estar ordenados por sha256, sin repetidos")

    fg = m.get("fecha_generacion")
    if _solo_claves(fg, ("utc", "zona_horaria"), "fecha_generacion", errs):
        if not (_es_texto(fg["utc"]) and _FECHA_UTC.match(fg["utc"])):
            errs.append("fecha_generacion.utc: debe ser AAAA-MM-DDThh:mm:ssZ")
        if fg["zona_horaria"] is not None and not _es_texto(fg["zona_horaria"]):
            errs.append("fecha_generacion.zona_horaria: debe ser texto o null")

    cf = m.get("configuracion")
    if _solo_claves(cf, ("metas", "umbrales", "escenarios", "contexto", "ia"), "configuracion", errs):
        for k in ("metas", "umbrales", "escenarios"):
            if not (isinstance(cf[k], dict) and all(_es_texto(a) and (_es_texto(b) or _es_entero(b)) for a, b in cf[k].items())):
                errs.append(f"configuracion.{k}: debe ser un objeto de textos o enteros")
        if _solo_claves(cf["contexto"], ("lineas", "sha256"), "configuracion.contexto", errs):
            if not _es_entero(cf["contexto"]["lineas"]) or cf["contexto"]["lineas"] < 0:
                errs.append("configuracion.contexto.lineas: debe ser un entero >= 0")
            if not (_es_texto(cf["contexto"]["sha256"]) and _SHA_MIN.match(cf["contexto"]["sha256"])):
                errs.append("configuracion.contexto.sha256: debe ser SHA-256 en hexadecimal minúscula")
        if _solo_claves(cf["ia"], ("usada", "modelo_declarado"), "configuracion.ia", errs):
            if cf["ia"]["usada"] is not None and not isinstance(cf["ia"]["usada"], bool):
                errs.append("configuracion.ia.usada: debe ser booleano o null (no declarado)")
            if cf["ia"]["modelo_declarado"] is not None and not _es_texto(cf["ia"]["modelo_declarado"]):
                errs.append("configuracion.ia.modelo_declarado: debe ser texto o null")

    hr = m.get("hash_resultado")
    if _solo_claves(hr, ("algoritmo", "contrato", "valor"), "hash_resultado", errs):
        if hr["algoritmo"] != ALGORITMO or hr["contrato"] != CONTRATO:
            errs.append(f"hash_resultado: se esperaba {ALGORITMO}/{CONTRATO}")
        if not (_es_texto(hr["valor"]) and _SHA_MIN.match(hr["valor"])):
            errs.append("hash_resultado.valor: debe ser SHA-256 en hexadecimal minúscula")

    en = m.get("entorno")
    if _solo_claves(en, ("pyodide", "python", "python_pptx"), "entorno", errs) and not all(_es_texto(v) and v for v in en.values()):
        errs.append("entorno: pyodide, python y python_pptx deben ser textos no vacíos («desconocido» si no se pueden leer)")
    return errs


def construir_manifiesto(*, version_codigo, version_motor, version_definiciones, version_reglas, version_plantillas, archivos_fuente,
                         fecha_generacion, configuracion, hash_resultado, entorno) -> dict:
    """Arma el manifiesto (esquema `procedencia/1`) y lo VALIDA: si falta algo o algo es inválido lanza `ErrorProcedencia`."""
    m = _nfc_arbol({"esquema": ESQUEMA, "version_codigo": version_codigo, "version_motor": version_motor,
                    "version_definiciones": version_definiciones, "version_reglas": version_reglas, "version_plantillas": version_plantillas,
                    "archivos_fuente": archivos_fuente, "fecha_generacion": fecha_generacion, "configuracion": configuracion,
                    "hash_resultado": hash_resultado, "entorno": entorno})
    errs = validar_manifiesto(m)
    if errs:
        raise ErrorProcedencia("manifiesto inválido: " + "; ".join(errs[:6]) + (" …" if len(errs) > 6 else ""))
    return m


def serializar_manifiesto(m: dict) -> bytes:
    """Bytes EXACTOS de `procedencia.json` (y de la fila de la tabla): JSON con claves ordenadas, sangría de 1, UTF-8 y un salto de línea final.
    Es determinista: el mismo manifiesto da siempre los mismos bytes. Un manifiesto inválido NO se serializa."""
    errs = validar_manifiesto(m)
    if errs:
        raise ErrorProcedencia("no se serializa un manifiesto inválido: " + "; ".join(errs[:6]))
    try:
        datos = (json.dumps(_nfc_arbol(m), ensure_ascii=False, indent=1, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    except (UnicodeEncodeError, ValueError, TypeError) as e:
        raise ErrorProcedencia(f"el manifiesto no se puede serializar: {e}") from None
    if len(datos) > MAX_MANIFIESTO_BYTES:
        raise ErrorProcedencia(f"el manifiesto excede el tamaño máximo ({MAX_MANIFIESTO_BYTES} bytes)")
    return datos


def _sin_claves_repetidas(pares):
    d = {}
    for k, v in pares:
        if k in d:
            raise ValueError(f"clave repetida en el JSON: {k!r}")
        d[k] = v
    return d


def _rechazar_constante(c):
    raise ValueError(f"valor no permitido en el JSON: {c}")


def leer_manifiesto(datos) -> tuple[dict | None, list[str]]:
    """Lee bytes de un manifiesto: devuelve `(manifiesto, [])` si es válido o `(None, errores)`. Nunca lanza.
    Rechaza: no-UTF-8, JSON inválido o truncado, claves repetidas, NaN/Infinity, exceso de tamaño o de profundidad y todo lo que no
    cumpla el esquema cerrado `procedencia/1` (incluidos campos adicionales y esquemas desconocidos)."""
    if not isinstance(datos, (bytes, bytearray)):
        return None, ["el manifiesto debe leerse como bytes"]
    if len(datos) > MAX_MANIFIESTO_BYTES:
        return None, [f"el manifiesto excede el tamaño máximo ({MAX_MANIFIESTO_BYTES} bytes)"]
    try:
        texto = bytes(datos).decode("utf-8")
    except UnicodeDecodeError:
        return None, ["el manifiesto no es UTF-8 válido"]
    try:
        m = json.loads(texto, object_pairs_hook=_sin_claves_repetidas, parse_constant=_rechazar_constante)
    except (ValueError, RecursionError) as e:
        return None, [f"JSON inválido o truncado: {str(e)[:120]}"]
    errs = validar_manifiesto(m)
    return (m, []) if not errs else (None, errs)


# ======================================================================================================================================
# Fase 3A-4 · comparación y estados de reproducibilidad (docs/fase3a/ESPECIFICACION_FASE3A_PROCEDENCIA.md §3.1 a §3.5)
#
# `comparar` es PURA: no lee archivos, no regenera, no consulta el reloj ni escribe nada. Recibe la evidencia ya reunida (resultado de la
# verificación de integridad, el manifiesto registrado, el estado ACTUAL, las fuentes aportadas y, si se hizo, el resultado de una regeneración
# real) y la clasifica. Regla transversal: la ausencia de evidencia NUNCA cuenta como coincidencia.
# ======================================================================================================================================
ESQUEMA_COMPARACION = "comparacion/1"
ESTADOS = ("exacta", "parcial", "no_reproducible")          # estados de reproducibilidad de la spec; «sin clasificar» es `None`
COMPROBACIONES = ("C1", "C2", "C3a", "C3b", "C4", "C5", "C6", "C7")
ACTUAL_CAMPOS = ("version_codigo", "version_motor", "version_definiciones", "version_reglas", "version_plantillas", "configuracion", "entorno")
IGUALDAD_CANONICA = ("El resultado canónico es idéntico (hash_resultado). Esto NO implica igualdad binaria ni visual del PPTX (spec §3.5).")
MAX_VALOR_DIFF = 200


def _recortar(v):
    if isinstance(v, (dict, list)):
        v = json.dumps(v, ensure_ascii=False, sort_keys=True)
    texto = nfc(str(v)) if not isinstance(v, (bool, int)) and v is not None else v
    return texto[:MAX_VALOR_DIFF] + "…" if isinstance(texto, str) and len(texto) > MAX_VALOR_DIFF else texto


def _aplanar(x, ruta: str, out: dict) -> dict:
    if isinstance(x, dict):
        if not x:
            out[ruta] = {}
        for k in sorted(x):
            _aplanar(x[k], f"{ruta}.{k}" if ruta else str(k), out)
    elif isinstance(x, list):
        if not x:
            out[ruta] = []
        for i, v in enumerate(x):
            _aplanar(v, f"{ruta}[{i}]", out)
    else:
        out[ruta] = x
    return out


_AUSENTE = "‹ausente›"


def _diferencias(componente: str, registrado, actual) -> list[dict]:
    """Diferencias hoja por hoja entre dos estructuras JSON (orden determinista). Una hoja presente en un solo lado se informa como ausente."""
    a, b = _aplanar(registrado, "", {}), _aplanar(actual, "", {})
    out = []
    for ruta in sorted(set(a) | set(b)):
        va, vb = a.get(ruta, _AUSENTE), b.get(ruta, _AUSENTE)
        if type(va) is not type(vb) or va != vb:
            out.append({"componente": componente + (f".{ruta}" if ruta and not ruta.startswith("[") else ruta), "registrado": _recortar(va),
                        "actual": _recortar(vb), "motivo": "difiere"})
    return out


def _comprobacion(resultado: str, *detalle: str) -> dict:
    return {"resultado": resultado, "detalle": list(detalle)}


def _c1_c2(verificacion: dict) -> tuple[dict, dict, str | None]:
    """(C1, C2, causa_no_reproducible) a partir del resultado de `provenance_verify.verificar` (que ya distingue registro y copia)."""
    reg = verificacion["registro"]
    cop = verificacion["copia"]["estado"]
    estado = reg["estado"]
    if estado == "presente":
        c1 = _comprobacion("pasa", "el registro autoritativo existe, es válido y su esquema se conoce")
        if cop == "alterada":                                    # §3.1 C2 compara los bytes de `procedencia.json` con `manifiesto_sha256`
            return c1, _comprobacion("falla", "los bytes de procedencia.json difieren del registro autoritativo (copia alterada)"), \
                "manifiesto alterado: la copia procedencia.json no coincide con el registro (el registro autoritativo está íntegro)"
        return c1, _comprobacion("pasa", "sha256 del manifiesto = manifiesto_sha256 registrado"), None
    if estado == "esquema_no_soportado":
        return (_comprobacion("falla", *reg["detalle"]), _comprobacion("no_evaluada", "sin esquema conocido no se puede verificar"),
                "esquema de procedencia desconocido")
    if estado in ("corrupto", "ilegible"):
        causa = {"corrupto": "manifiesto alterado o inválido en el registro", "ilegible": "no se pudo leer el historial"}[estado]
        codigos = reg.get("codigos") or []
        c1_falla = estado == "ilegible" or "invalido" in codigos
        return (_comprobacion("falla" if c1_falla else "pasa", *(reg["detalle"] if c1_falla else [])),
                _comprobacion("falla" if estado == "corrupto" else "no_evaluada", *reg["detalle"]), causa)
    # registro ausente
    if cop == "sin_registro":
        return (_comprobacion("pasa", "la copia procedencia.json es válida"),
                _comprobacion("no_evaluada", "no hay registro autoritativo con el que verificar la integridad (D-B: máximo parcial)"), None)
    if cop in ("invalida", "ilegible"):
        return _comprobacion("falla", *verificacion["copia"]["detalle"]), _comprobacion("no_evaluada"), "la única copia de la procedencia no es válida"
    if verificacion.get("error_de_generacion"):
        return (_comprobacion("falla", "no hay manifiesto: la procedencia no se pudo generar"), _comprobacion("no_evaluada"),
                "procedencia no disponible por un error al generarla")
    return (_comprobacion("falla", "no hay manifiesto"), _comprobacion("no_evaluada"), "sin procedencia (reporte anterior a la Fase 3A: legado)")


def _c3(registrado: dict, aportadas) -> tuple[dict, dict, list[dict]]:
    """(C3a, C3b, diferencias). Una fuente se da por aportada si algún archivo tiene su SHA-256 (el nombre no importa, igual que en el hash)."""
    difs: list[dict] = []
    if aportadas is None:
        faltan = [f for f in registrado["archivos_fuente"]]
        for f in faltan:
            difs.append({"componente": f"archivos_fuente.{f['id']}", "registrado": f["sha256"], "actual": _AUSENTE, "motivo": "no aportado"})
        return (_comprobacion("falla" if faltan else "pasa", *[f"{f['id']} ({f['nombre']}) no fue aportada" for f in faltan]),
                _comprobacion("no_evaluada", "no se aportó ningún archivo"), difs)
    shas = {a["sha256"] for a in aportadas}
    registradas = {f["sha256"] for f in registrado["archivos_fuente"]}
    faltan, distintos = [], []
    for f in registrado["archivos_fuente"]:
        if f["sha256"] in shas:
            continue
        misma = [a for a in aportadas if a["nombre"] == f["nombre"]]
        if misma:
            distintos.append(f"{f['id']} ({f['nombre']}): el archivo aportado tiene otro contenido")
            difs.append({"componente": f"archivos_fuente.{f['id']}.sha256", "registrado": f["sha256"], "actual": misma[0]["sha256"],
                         "motivo": "contenido distinto"})
        else:
            faltan.append(f"{f['id']} ({f['nombre']}) no fue aportada")
            difs.append({"componente": f"archivos_fuente.{f['id']}", "registrado": f["sha256"], "actual": _AUSENTE, "motivo": "no aportado"})
    ya = {d["actual"] for d in difs}                                    # ya informadas arriba (mismo nombre, otro contenido)
    for a in sorted(aportadas, key=lambda x: (x["nombre"], x["sha256"])):
        if a["sha256"] not in registradas and a["sha256"] not in ya:
            distintos.append(f"«{a['nombre']}» no corresponde a ninguna fuente registrada")
            difs.append({"componente": "archivos_fuente.aportado", "registrado": _AUSENTE, "actual": a["sha256"], "motivo": "fuente no registrada"})
    return (_comprobacion("falla" if faltan else "pasa", *faltan), _comprobacion("falla" if distintos else "pasa", *distintos), difs)


def _c4(registrado: dict, actual: dict) -> tuple[dict, list[dict]]:
    act = actual.get("version_plantillas")
    if act is None:
        return _comprobacion("falla", "no se aportó la plantilla actual: sin evidencia"), [
            {"componente": "version_plantillas", "registrado": _recortar(registrado["version_plantillas"]), "actual": _AUSENTE, "motivo": "sin evidencia actual"}]
    clave = lambda p: sorted(({"id": x["id"], "sha256": x["sha256"]} for x in p), key=lambda d: (d["id"], d["sha256"]))        # noqa: E731
    difs = _diferencias("version_plantillas", clave(registrado["version_plantillas"]), clave(act))
    return _comprobacion("falla" if difs else "pasa", *[f"{d['componente']}: registrado {d['registrado']} / actual {d['actual']}" for d in difs]), difs


def _c5(registrado: dict, actual: dict) -> tuple[dict, list[dict]]:
    act = actual.get("version_codigo")
    reg = registrado["version_codigo"]
    if act is None:
        return _comprobacion("falla", "no se aportó la versión actual del código: sin evidencia"), [
            {"componente": "version_codigo", "registrado": _recortar(reg), "actual": _AUSENTE, "motivo": "sin evidencia actual"}]
    difs = _diferencias("version_codigo", reg, act)
    detalle = [f"{d['componente']}: registrado {d['registrado']} / actual {d['actual']}" for d in difs]
    for lado, c in (("registrado", reg["commit"]), ("actual", act.get("commit"))):
        if c == "desconocido" or c is None:
            detalle.append(f"el commit {lado} es desconocido: no se puede demostrar que sea el mismo código")
        elif isinstance(c, str) and c.endswith("+dirty"):
            detalle.append(f"el commit {lado} tiene cambios sin confirmar (+dirty): no identifica un código único")
    return _comprobacion("falla" if detalle else "pasa", *detalle), difs


def _c6(registrado: dict, actual: dict) -> tuple[dict, list[dict]]:
    difs: list[dict] = []
    detalle: list[str] = []
    for campo in ("version_motor", "version_definiciones", "version_reglas", "configuracion"):
        act = actual.get(campo)
        if act is None:
            difs.append({"componente": campo, "registrado": _recortar(registrado[campo]), "actual": _AUSENTE, "motivo": "sin evidencia actual"})
            detalle.append(f"{campo}: no se aportó el valor actual (sin evidencia)")
            continue
        for d in _diferencias(campo, registrado[campo], act):
            difs.append(d)
            detalle.append(f"{d['componente']}: registrado {d['registrado']} / actual {d['actual']}")
    return _comprobacion("falla" if detalle else "pasa", *detalle), difs


def _regen_info(registrado, estado: str, **kw) -> dict:
    return {"estado": estado, "ejecutada": estado in ("completada", "fallida"),
            "hash_registrado": registrado["hash_resultado"]["valor"] if registrado else None, "hash_regenerado": None, "error": None, **kw}


def _c7(registrado: dict, regeneracion) -> tuple[dict, list[dict], dict]:
    """(C7, diferencias, información técnica de la regeneración). `regeneracion`: `None` = no solicitada; `{"no_ejecutada": motivo}` = se pidió
    pero no se ejecutó; `{"hash_resultado"}` = completada; `{"error"}` o cualquier otra cosa = fallida (nunca éxito)."""
    reg_hash = registrado["hash_resultado"]
    if regeneracion is None:
        return (_comprobacion("no_evaluada", "no se solicitó regeneración: sin regeneración real no existe «exacta» (§3.5)"), [],
                _regen_info(registrado, "no_solicitada"))
    if isinstance(regeneracion, dict) and set(regeneracion) == {"no_ejecutada"}:
        motivo = nfc(str(regeneracion["no_ejecutada"]))[:300]
        return _comprobacion("no_evaluada", "se solicitó regeneración pero no se ejecutó: " + motivo), [], _regen_info(registrado, "no_ejecutada", error=motivo)
    info = _regen_info(registrado, "fallida")
    if not isinstance(regeneracion, dict):
        info["error"] = "evidencia de regeneración inválida"
        return _comprobacion("error", info["error"]), [], info
    if regeneracion.get("error"):
        info["error"] = nfc(rutas_a_nombre_base(str(regeneracion["error"])))[:500]
        return _comprobacion("error", "la regeneración falló: " + info["error"]), [], info
    valor = regeneracion.get("hash_resultado")
    if not isinstance(valor, str) or not _SHA_MIN.match(valor):
        info["error"] = "la regeneración no devolvió un hash_resultado válido (resultado incompleto)"
        return _comprobacion("error", info["error"]), [], info
    info["estado"], info["hash_regenerado"] = "completada", valor
    if valor != reg_hash["valor"]:
        return _comprobacion("falla", "el hash_resultado de la regeneración difiere del registrado"), [
            {"componente": "hash_resultado.valor", "registrado": reg_hash["valor"], "actual": valor, "motivo": "difiere"}], info
    return _comprobacion("pasa", "el hash_resultado de la regeneración es igual al registrado"), [], info


def comparar(*, verificacion: dict, registrado, actual: dict | None, fuentes_aportadas, regeneracion=None) -> dict:
    """Clasifica la reproducibilidad (spec §3.2). Se separan TRES conceptos que no deben mezclarse:

    * `estado` — estado de REPRODUCIBILIDAD, solo los de la spec: `exacta`, `parcial`, `no_reproducible`, o `None` cuando la evidencia no
      permite clasificar (no es un cuarto estado: significa «sin clasificar», y nunca equivale a coincidencia).
    * `evaluacion` — si la evaluación llegó a su fin: `completada` (hay estado), `no_ejecutada` (falta una regeneración que no se solicitó o no
      se ejecutó) o `fallida` (la regeneración falló).
    * `regeneracion` — resultado técnico de la regeneración: `no_solicitada`, `no_ejecutada`, `completada` o `fallida`.

    Orden de evaluación (el primer criterio que se cumple gana):
    1. `no_reproducible`: C1 falla (sin manifiesto, legado, esquema desconocido) o C2 falla (alterado) o C3b falla (una fuente aportada difiere).
    2. `parcial`: C3a, C4, C5 o C6 fallan, o no hay registro para verificar C2 (D-B), o C1 a C6 pasan y C7 falla (anomalía de determinismo).
    3. `exacta`: C1 a C7 pasan; C7 exige una regeneración real completada con el mismo `hash_resultado`.
    4. `estado = None`: C1 a C6 pasan pero no hay regeneración completada (no solicitada, no ejecutada o fallida).

    `verificacion` es el resultado de `provenance_verify.verificar`; `registrado` el manifiesto ya validado (o `None`); `actual` el estado actual
    (claves de `ACTUAL_CAMPOS`); `fuentes_aportadas` lista de `{"nombre", "sha256"}` o `None`; `regeneracion` ver `_c7`.
    Determinista y sin efectos: el mismo argumento da siempre el mismo resultado."""
    if not isinstance(verificacion, dict) or "registro" not in verificacion or "copia" not in verificacion:
        raise ErrorProcedencia("verificacion no es un resultado de provenance_verify.verificar")
    actual = actual or {}
    desconocidas = set(actual) - set(ACTUAL_CAMPOS)
    if desconocidas:
        raise ErrorProcedencia(f"campos desconocidos en el estado actual: {sorted(desconocidas)}")
    c1, c2, causa_no_repr = _c1_c2(verificacion)
    comps = {k: _comprobacion("no_evaluada", "no se evaluó: no hay un manifiesto válido") for k in COMPROBACIONES}
    comps["C1"], comps["C2"] = c1, c2
    valido = registrado is not None and not validar_manifiesto(registrado)
    sin_uso = ("no_solicitada" if regeneracion is None else "no_ejecutada")
    out = {"esquema": ESQUEMA_COMPARACION, "estado": "no_reproducible", "causa": causa_no_repr, "comprobaciones": comps, "diferencias": [],
           "notas": [], "alertas": [],
           "evaluacion": {"estado": "completada", "motivo": None},
           "regeneracion": _regen_info(registrado if valido else None, sin_uso,
                                       **({"error": "no se evalúa: la evidencia no es válida"} if sin_uso == "no_ejecutada" else {})),
           "evidencia": {"run_id": verificacion.get("run_id"), "manifiesto_sha256": verificacion["registro"].get("manifiesto_sha256"),
                         "integridad": verificacion.get("integridad"), "copia": verificacion["copia"]["estado"]}}
    if c1["resultado"] == "falla" or c2["resultado"] == "falla":
        return out
    if not valido:
        out["causa"] = "no hay un manifiesto válido que comparar"
        comps["C1"] = _comprobacion("falla", "no se entregó un manifiesto válido")
        return out
    out["regeneracion"] = _regen_info(registrado, sin_uso, **({"error": "no se evalúa: la evidencia no es válida"} if sin_uso == "no_ejecutada" else {}))
    difs: list[dict] = []
    comps["C3a"], comps["C3b"], d3 = _c3(registrado, fuentes_aportadas)
    comps["C4"], d4 = _c4(registrado, actual)
    comps["C5"], d5 = _c5(registrado, actual)
    comps["C6"], d6 = _c6(registrado, actual)
    difs += d3 + d4 + d5 + d6
    if actual.get("entorno") is not None:
        for d in _diferencias("entorno", registrado["entorno"], actual["entorno"]):
            out["notas"].append(f"entorno: {d['componente']} registrado {d['registrado']} / actual {d['actual']} (informativo; no decide el estado)")
    if comps["C3b"]["resultado"] == "falla":
        out["causa"] = "un archivo fuente aportado difiere del registrado"
        out["diferencias"] = difs
        return out
    sin_c2 = c2["resultado"] != "pasa"
    fallas = [k for k in ("C3a", "C4", "C5", "C6") if comps[k]["resultado"] == "falla"]
    comps["C7"], d7, out["regeneracion"] = _c7(registrado, regeneracion)
    if fallas or sin_c2:
        out["estado"] = "parcial"
        causas = [f"{k} falla" for k in fallas] + (["integridad no verificable: no hay registro autoritativo (D-B)"] if sin_c2 else [])
        out["causa"] = "; ".join(causas)
        out["diferencias"] = difs + d7                      # una regeneración, si la hubo, se conserva como evidencia pero no eleva el estado
        return out
    out["diferencias"] = difs + d7
    r = comps["C7"]["resultado"]
    if r == "pasa":
        out["estado"], out["causa"] = "exacta", IGUALDAD_CANONICA
        if out["notas"]:
            out["alertas"].append("el entorno difiere: la igualdad es solo del resultado canónico; no se garantiza igualdad binaria ni visual del PPTX")
    elif r == "falla":
        out["estado"] = "parcial"
        out["causa"] = "anomalía de determinismo: C1 a C6 pasan y el hash_resultado regenerado difiere"
        out["alertas"].append("anomalía de determinismo: mismos insumos y versiones, distinto hash_resultado. Es un defecto del sistema o una entrada "
                              "no registrada (p. ej. texto editado a mano); primera sospecha: " + ("diferencia de entorno" if out["notas"] else "entradas no registradas"))
    else:                                                   # C7 no evaluada o con error: la spec no define un estado → sin clasificar
        out["estado"] = None
        fallida = r == "error"
        out["causa"] = ("la regeneración falló: no hay evidencia para clasificar" if fallida else
                        "C1 a C6 pasan pero no hay regeneración completada: sin regeneración real no existe «exacta»")
        out["evaluacion"] = {"estado": "fallida" if fallida else "no_ejecutada", "motivo": out["causa"]}
    return out


_ESTADOS_REGEN = ("no_solicitada", "no_ejecutada", "completada", "fallida")
_ESTADOS_EVAL = ("completada", "no_ejecutada", "fallida")
_RESULTADOS_C = ("pasa", "falla", "no_evaluada", "error")


def validar_comparacion(r) -> list[str]:
    """Errores de estructura o de COHERENCIA de un resultado de `comparar` (lista vacía = válido). Permite verificar después, sin volver a
    regenerar, que un resultado guardado no fue alterado hasta contradecirse (p. ej. `exacta` sin regeneración completada e igual)."""
    claves = {"esquema", "estado", "causa", "comprobaciones", "diferencias", "notas", "alertas", "evaluacion", "regeneracion", "evidencia"}
    if not isinstance(r, dict):
        return ["la comparación debe ser un objeto"]
    errs: list[str] = []
    if not claves <= set(r) or set(r) - claves - {"avisos"}:                 # `avisos` es opcional: lo agrega la orquestación (provenance_compare)
        return [f"campos de primer nivel inválidos: faltan {sorted(claves - set(r))}, sobran {sorted(set(r) - claves - {'avisos'})}"]
    if "avisos" in r and not (isinstance(r["avisos"], list) and all(isinstance(x, str) for x in r["avisos"])):
        errs.append("avisos debe ser una lista de textos")
    if r["esquema"] != ESQUEMA_COMPARACION:
        errs.append(f"esquema desconocido: {r['esquema']!r}")
    if r["estado"] not in ("exacta", "parcial", "no_reproducible", None):
        errs.append(f"estado de reproducibilidad inválido: {r['estado']!r}")
    comps = r["comprobaciones"]
    if not isinstance(comps, dict) or set(comps) != set(COMPROBACIONES):
        return errs + ["comprobaciones incompletas o con claves desconocidas"]
    for k, c in comps.items():
        if not (isinstance(c, dict) and set(c) == {"resultado", "detalle"} and c["resultado"] in _RESULTADOS_C
                and isinstance(c["detalle"], list) and all(isinstance(x, str) for x in c["detalle"])):
            errs.append(f"comprobación {k} inválida")
    ev, rg = r["evaluacion"], r["regeneracion"]
    if not (isinstance(ev, dict) and set(ev) == {"estado", "motivo"} and ev["estado"] in _ESTADOS_EVAL):
        return errs + ["evaluacion inválida"]
    if not (isinstance(rg, dict) and set(rg) == {"estado", "ejecutada", "hash_registrado", "hash_regenerado", "error"} and rg["estado"] in _ESTADOS_REGEN
            and isinstance(rg["ejecutada"], bool)):
        return errs + ["regeneracion inválida"]
    if rg["ejecutada"] != (rg["estado"] in ("completada", "fallida")):
        errs.append("regeneracion.ejecutada no corresponde a su estado")
    for campo in ("hash_registrado", "hash_regenerado"):
        if rg[campo] is not None and not (isinstance(rg[campo], str) and _SHA_MIN.match(rg[campo])):
            errs.append(f"regeneracion.{campo} no es un SHA-256")
    if rg["estado"] == "completada" and rg["hash_regenerado"] is None:
        errs.append("una regeneración completada debe traer su hash")
    if rg["estado"] == "fallida" and not rg["error"]:
        errs.append("una regeneración fallida debe traer su error")
    if rg["estado"] in ("no_solicitada",) and rg["hash_regenerado"] is not None:
        errs.append("una regeneración no solicitada no puede traer hash")
    if (r["estado"] is None) != (ev["estado"] != "completada"):
        errs.append("estado y evaluacion se contradicen")
    if r["estado"] is None:
        previas_ok = all(comps[k]["resultado"] == "pasa" for k in ("C1", "C2", "C3a", "C3b", "C4", "C5", "C6"))
        error_interno = (ev["estado"] == "fallida" and rg["estado"] == "no_ejecutada" and bool(rg["error"])
                         and all(c["resultado"] == "no_evaluada" for c in comps.values()))            # fallo ajeno a la regeneración: nada se evaluó
        if not previas_ok and not error_interno:
            errs.append("sin clasificar solo es posible cuando C1 a C6 pasan (o la evaluación falló antes de empezar)")
        if ev["estado"] == "fallida" and rg["estado"] != "fallida" and not error_interno:
            errs.append("evaluación fallida sin regeneración fallida")
        if ev["estado"] == "no_ejecutada" and rg["estado"] not in ("no_solicitada", "no_ejecutada"):
            errs.append("evaluación no ejecutada con una regeneración ya realizada")
    if r["estado"] == "exacta":
        if not all(comps[k]["resultado"] == "pasa" for k in COMPROBACIONES):
            errs.append("«exacta» exige C1 a C7 en «pasa»")
        if not (rg["estado"] == "completada" and rg["hash_regenerado"] == rg["hash_registrado"] and rg["hash_registrado"]):
            errs.append("«exacta» exige una regeneración completada con el mismo hash_resultado")
        if r["diferencias"]:
            errs.append("«exacta» no admite diferencias")
    if r["estado"] in ("exacta", "parcial", "no_reproducible") and not isinstance(r["causa"], str):
        errs.append("la causa debe ser texto")
    for campo in ("diferencias", "notas", "alertas"):
        if not isinstance(r[campo], list):
            errs.append(f"{campo} debe ser una lista")
    evd = r["evidencia"]
    if not (isinstance(evd, dict) and set(evd) == {"run_id", "manifiesto_sha256", "integridad", "copia"}):
        errs.append("evidencia inválida")
    elif evd["manifiesto_sha256"] is not None and not (isinstance(evd["manifiesto_sha256"], str) and _SHA_MIN.match(evd["manifiesto_sha256"])):
        errs.append("evidencia.manifiesto_sha256 no es un SHA-256")
    return errs


def leer_comparacion(datos) -> tuple[dict | None, list[str]]:
    """Lee bytes de una comparación guardada: `(resultado, [])` o `(None, errores)`. Nunca lanza. Mismo rigor que `leer_manifiesto` (UTF-8,
    claves repetidas, NaN/Infinity, tamaño) más `validar_comparacion`."""
    if not isinstance(datos, (bytes, bytearray)):
        return None, ["la comparación debe leerse como bytes"]
    if len(datos) > MAX_MANIFIESTO_BYTES:
        return None, [f"la comparación excede el tamaño máximo ({MAX_MANIFIESTO_BYTES} bytes)"]
    try:
        r = json.loads(bytes(datos).decode("utf-8"), object_pairs_hook=_sin_claves_repetidas, parse_constant=_rechazar_constante)
    except UnicodeDecodeError:
        return None, ["la comparación no es UTF-8 válido"]
    except (ValueError, RecursionError) as e:
        return None, [f"JSON inválido o truncado: {str(e)[:120]}"]
    errs = validar_comparacion(r)
    return (r, []) if not errs else (None, errs)


def serializar_comparacion(resultado: dict) -> bytes:
    """Bytes deterministas (JSON de claves ordenadas, UTF-8) de un resultado de `comparar`, para conservarlo como evidencia de auditoría.
    Se rechaza un resultado estructural o lógicamente inválido (no se serializa una comparación incoherente)."""
    if not isinstance(resultado, dict) or resultado.get("esquema") != ESQUEMA_COMPARACION:
        raise ErrorProcedencia("no es un resultado de comparar")
    errs = validar_comparacion(resultado)
    if errs:
        raise ErrorProcedencia("la comparación no es coherente: " + "; ".join(errs[:3]))
    try:
        return (json.dumps(resultado, ensure_ascii=False, sort_keys=True, indent=1, allow_nan=False) + "\n").encode("utf-8")
    except (TypeError, ValueError) as e:
        raise ErrorProcedencia(f"la comparación no se puede serializar: {e}") from None
