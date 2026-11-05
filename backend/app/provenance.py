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
