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
