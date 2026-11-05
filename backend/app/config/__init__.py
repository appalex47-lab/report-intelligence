"""Configuración de Fase 1 como DATOS versionados (docs/CONFIGURACION_FASE1.md).

Reutiliza el patrón ya existente de `profiles/*.yaml` (configuración separada del código) pero en JSON, que es lo que
fija la especificación de Fase 1 y no añade dependencias. En esta fase SOLO se cargan y se validan estructuralmente:
ninguna regla, escenario ni indicador consume todavía estos archivos, y el motor actual no los lee.

Principios: nada se inventa (lo no configurado es `null`), los números se leen como `Decimal` exactos, y cada archivo
declara su `esquema` y su `version`.
"""
from __future__ import annotations

import json
import re
from decimal import Decimal
from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parent
ARCHIVOS = {
    "definiciones": "definiciones.json",
    "reglas": "reglas.json",
    "mapeo_columnas": "mapeo_columnas.json",
    "validacion_registro": "validacion_registro.json",
}
ESQUEMAS = {"definiciones": "definiciones/1", "reglas": "reglas/1", "mapeo_columnas": "mapeo_columnas/1",
            "validacion_registro": "validacion_registro/1"}

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
ORIGENES = ("heredado", "nuevo", "no_configurado")
VALIDACION_OPERACIONAL = ("no_validada_con_datos_reales", "confirmada", "no_aplica")
VALIDACION_SINTETICA = ("pendiente", "aprobada", "fallida", "no_aplica")
TIPOS_DEFINICION = ("entidad", "metrica", "indicador")
UNIDADES_NEGOCIO = ("GLP1", "AETOPS")
FLAGS = ("validacion_fase1", "relacion_pedidos_carritos", "anexo_calidad", "qa_pptx_exportado", "escenarios_estrictos")
REGLAS_FASE1 = ("R-REL-PAC-PED", "R-CUADRE-DIM", "R-CONC-COMPRAS", "R-DENOM", "R-COBERTURA-ATC")
ESTADOS_REGLA = ("valid", "warning", "error", "not_verifiable", "not_applicable")   # resultados del motor de reglas (Fase 2A)
SEVERITIES = ("block", "warn", "info")
# La metodología agregada NO usa identificadores de carrito, de transacción ni de sesión (spec §8.2, AC-23).
PROHIBIDO_EN_MAPEO = re.compile(r"carrit|transacci|sesion|session|cart_id", re.IGNORECASE)


class ConfigError(Exception):
    """El archivo de configuración no existe o no es JSON legible."""


def cargar(nombre: str, directorio: Path | None = None) -> dict:
    """Lee un archivo de configuración. Los números decimales se leen como `Decimal` (sin errores de coma flotante)."""
    if nombre not in ARCHIVOS:
        raise ConfigError(f"Configuración desconocida: {nombre!r}; opciones: {sorted(ARCHIVOS)}")
    ruta = Path(directorio or CONFIG_DIR) / ARCHIVOS[nombre]
    try:
        return json.loads(ruta.read_text(encoding="utf-8"), parse_float=Decimal)
    except FileNotFoundError as e:
        raise ConfigError(f"No existe {ruta}") from e
    except json.JSONDecodeError as e:
        raise ConfigError(f"{ruta.name} no es JSON válido: {e}") from e


def _tipo(v, tipos) -> bool:
    return isinstance(v, tipos)


def _campo(d: dict, k: str, tipos, errs: list, ruta: str, *, nulo: bool = False):
    if k not in d:
        errs.append(f"{ruta}: falta el campo obligatorio {k!r}")
        return None
    v = d[k]
    if v is None:
        if not nulo:
            errs.append(f"{ruta}.{k}: no puede ser null")
        return None
    if not _tipo(v, tipos):
        errs.append(f"{ruta}.{k}: tipo {type(v).__name__} inválido")
        return None
    return v


def _cabecera(d, nombre: str, errs: list):
    if not isinstance(d, dict):
        errs.append(f"{nombre}: la raíz debe ser un objeto")
        return False
    esq = _campo(d, "esquema", str, errs, nombre)
    if esq is not None and esq != ESQUEMAS[nombre]:
        errs.append(f"{nombre}.esquema: se esperaba {ESQUEMAS[nombre]!r} y llegó {esq!r}")
    ver = _campo(d, "version", str, errs, nombre)
    if ver is not None and not SEMVER.match(ver):
        errs.append(f"{nombre}.version: {ver!r} no es MAJOR.MINOR.PATCH")
    return True


def validar_definiciones(d) -> list[str]:
    errs: list[str] = []
    if not _cabecera(d, "definiciones", errs):
        return errs
    _campo(d, "fuente_documental", str, errs, "definiciones")
    items = _campo(d, "definiciones", list, errs, "definiciones")
    ids: set[str] = set()
    for i, e in enumerate(items or []):
        ruta = f"definiciones[{i}]"
        if not isinstance(e, dict):
            errs.append(f"{ruta}: debe ser un objeto")
            continue
        did = _campo(e, "id", str, errs, ruta)
        if did is not None:
            ruta = f"definiciones[{did}]"
            if did in ids:
                errs.append(f"{ruta}: identificador duplicado")
            ids.add(did)
        for k in ("nombre", "descripcion", "granularidad", "referencia"):
            _campo(e, k, str, errs, ruta)
        ver = _campo(e, "version", str, errs, ruta)
        if ver is not None and not SEMVER.match(ver):
            errs.append(f"{ruta}.version: {ver!r} no es MAJOR.MINOR.PATCH")
        t = _campo(e, "tipo", str, errs, ruta)
        if t is not None and t not in TIPOS_DEFINICION:
            errs.append(f"{ruta}.tipo: {t!r} no está en {TIPOS_DEFINICION}")
        _campo(e, "unidad", str, errs, ruta, nulo=True)
        o = _campo(e, "origen", str, errs, ruta)
        if o is not None and o not in ("heredado", "nuevo"):
            errs.append(f"{ruta}.origen: {o!r} debe ser 'heredado' o 'nuevo'")
        vo = _campo(e, "validacion_operacional", str, errs, ruta)
        if vo is not None and vo not in VALIDACION_OPERACIONAL:
            errs.append(f"{ruta}.validacion_operacional: {vo!r} no válido")
        lim = _campo(e, "limitaciones", list, errs, ruta)
        if lim is not None and not all(isinstance(x, str) and x for x in lim):
            errs.append(f"{ruta}.limitaciones: debe ser una lista de textos no vacíos")
        ap = _campo(e, "aplicabilidad", dict, errs, ruta)
        if ap is not None:
            un = _campo(ap, "unidades", list, errs, f"{ruta}.aplicabilidad")
            if un is not None and (not un or any(u not in UNIDADES_NEGOCIO for u in un)):
                errs.append(f"{ruta}.aplicabilidad.unidades: debe contener solo {UNIDADES_NEGOCIO}")
            _campo(ap, "condicion", str, errs, f"{ruta}.aplicabilidad", nulo=True)
        fu = _campo(e, "fuente", (dict, list), errs, ruta, nulo=True)
        for f in ([fu] if isinstance(fu, dict) else (fu or [])):
            if not isinstance(f, dict):
                errs.append(f"{ruta}.fuente: cada fuente debe ser un objeto {{hoja, columna}}")
                continue
            for k in ("hoja", "columna"):
                _campo(f, k, str, errs, f"{ruta}.fuente")
    return errs


def _validar_parametro(nombre: str, p, errs: list):
    ruta = f"reglas.parametros[{nombre}]"
    if not isinstance(p, dict):
        errs.append(f"{ruta}: debe ser un objeto")
        return
    if "valor" not in p:
        errs.append(f"{ruta}: falta 'valor' (use null si no está configurado)")
    o = _campo(p, "origen", str, errs, ruta)
    if o is not None and o not in ORIGENES:
        errs.append(f"{ruta}.origen: {o!r} no está en {ORIGENES}")
    if o == "no_configurado" and p.get("valor") is not None:
        errs.append(f"{ruta}: origen 'no_configurado' exige valor null (no se inventan valores)")
    if o in ("heredado", "nuevo") and p.get("valor") is None:
        errs.append(f"{ruta}: origen {o!r} exige un valor; si no hay, use origen 'no_configurado'")
    _campo(p, "referencia", str, errs, ruta)
    vo = _campo(p, "validacion_operacional", str, errs, ruta)
    if vo is not None and vo not in VALIDACION_OPERACIONAL:
        errs.append(f"{ruta}.validacion_operacional: {vo!r} no válido")


def validar_reglas(d) -> list[str]:
    errs: list[str] = []
    if not _cabecera(d, "reglas", errs):
        return errs
    flags = _campo(d, "flags", dict, errs, "reglas")
    if flags is not None:
        if set(flags) != set(FLAGS):
            errs.append(f"reglas.flags: deben ser exactamente {FLAGS}")
        for k, v in flags.items():
            if not isinstance(v, bool):
                errs.append(f"reglas.flags[{k}]: debe ser true/false")
    pars = _campo(d, "parametros", dict, errs, "reglas")
    for k, p in (pars or {}).items():
        _validar_parametro(k, p, errs)
    dims = _campo(d, "dimensiones", dict, errs, "reglas")
    for k, dd in (dims or {}).items():
        ruta = f"reglas.dimensiones[{k}]"
        if not isinstance(dd, dict):
            errs.append(f"{ruta}: debe ser un objeto")
            continue
        _campo(dd, "entidad", str, errs, ruta)
        for prop in ("exclusiva", "exhaustiva"):
            if prop not in dd or not (dd[prop] is None or isinstance(dd[prop], bool)):
                errs.append(f"{ruta}.{prop}: debe ser true, false o null (sin declarar)")
        _campo(dd, "justificacion", str, errs, ruta, nulo=True)
        if dd.get("exclusiva") is not None and dd.get("exhaustiva") is not None and not dd.get("justificacion"):
            errs.append(f"{ruta}: declarar exclusiva/exhaustiva exige justificación")
    errs += _validar_catalogo_reglas(d, pars or {})
    return errs


def _validar_catalogo_reglas(d: dict, parametros: dict) -> list[str]:
    """Catálogo de reglas (Fase 2A): cada regla se describe como DATO; el código solo la ejecuta."""
    errs: list[str] = []
    items = _campo(d, "reglas", list, errs, "reglas")
    vistos: set[str] = set()
    for i, r in enumerate(items or []):
        ruta = f"reglas.reglas[{i}]"
        if not isinstance(r, dict):
            errs.append(f"{ruta}: debe ser un objeto")
            continue
        rid = _campo(r, "id", str, errs, ruta)
        if rid is not None:
            ruta = f"reglas.reglas[{rid}]"
            if rid in vistos:
                errs.append(f"{ruta}: regla duplicada")
            vistos.add(rid)
        for k in ("nombre", "descripcion", "tipo"):
            _campo(r, k, str, errs, ruta)
        ver = _campo(r, "version", str, errs, ruta)
        if ver is not None and not SEMVER.match(ver):
            errs.append(f"{ruta}.version: {ver!r} no es MAJOR.MINOR.PATCH")
        _campo(r, "gravedad", str, errs, ruta, nulo=True)
        un = _campo(r, "unidades", list, errs, ruta)
        if un is not None and (not un or any(u not in UNIDADES_NEGOCIO for u in un)):
            errs.append(f"{ruta}.unidades: debe contener solo {UNIDADES_NEGOCIO}")
        cols = _campo(r, "columnas_requeridas", list, errs, ruta)
        for c in cols or []:
            if not (isinstance(c, dict) and isinstance(c.get("hoja"), str) and isinstance(c.get("columna"), str)):
                errs.append(f"{ruta}.columnas_requeridas: cada elemento debe ser {{hoja, columna}}")
        pn = _campo(r, "parametros", list, errs, ruta)
        for n in pn or []:
            if n not in parametros:
                errs.append(f"{ruta}.parametros: {n!r} no existe en reglas.parametros")
        act = _campo(r, "activacion", dict, errs, ruta)
        if act is not None:
            fl = _campo(act, "flag", str, errs, f"{ruta}.activacion")
            if fl is not None and fl not in FLAGS:
                errs.append(f"{ruta}.activacion.flag: {fl!r} no está en {FLAGS}")
            _campo(act, "condicion", str, errs, f"{ruta}.activacion")
        sev = _campo(r, "severidad", dict, errs, ruta)
        if sev is not None:
            if set(sev) != set(ESTADOS_REGLA):
                errs.append(f"{ruta}.severidad: debe definir exactamente {ESTADOS_REGLA}")
            if any(v not in SEVERITIES for v in sev.values()):
                errs.append(f"{ruta}.severidad: valores válidos {SEVERITIES}")
        sc = _campo(r, "severidad_codigos", dict, errs, ruta)
        if sc is not None and any(v not in SEVERITIES for v in sc.values()):
            errs.append(f"{ruta}.severidad_codigos: valores válidos {SEVERITIES}")
        ev = _campo(r, "evidencia", list, errs, ruta)
        if ev is not None and not all(isinstance(x, str) and x for x in ev):
            errs.append(f"{ruta}.evidencia: debe ser una lista de textos")
        ms = _campo(r, "mensajes", dict, errs, ruta)
        if ms is not None and (not ms or not all(isinstance(k, str) and isinstance(v, str) and v for k, v in ms.items())):
            errs.append(f"{ruta}.mensajes: debe ser {{codigo.estado: texto}} no vacío")
    return errs


def validar_mapeo_columnas(d) -> list[str]:
    errs: list[str] = []
    if not _cabecera(d, "mapeo_columnas", errs):
        return errs
    unidades = _campo(d, "unidades", dict, errs, "mapeo_columnas")
    for u, spec in (unidades or {}).items():
        if u not in UNIDADES_NEGOCIO:
            errs.append(f"mapeo_columnas.unidades[{u}]: unidad desconocida")
            continue
        hojas = _campo(spec, "hojas", dict, errs, f"mapeo_columnas.unidades[{u}]") if isinstance(spec, dict) else None
        for h, hs in (hojas or {}).items():
            ruta = f"mapeo_columnas.unidades[{u}].hojas[{h}]"
            al = _campo(hs, "alias", dict, errs, ruta) if isinstance(hs, dict) else None
            for canon, lst in (al or {}).items():
                if PROHIBIDO_EN_MAPEO.search(canon) or (isinstance(lst, list) and any(PROHIBIDO_EN_MAPEO.search(str(x)) for x in lst)):
                    errs.append(f"{ruta}: no se mapean identificadores de carrito, transacción o sesión ({canon!r})")
                if not isinstance(lst, list) or not all(isinstance(x, str) and x for x in lst):
                    errs.append(f"{ruta}.alias[{canon}]: debe ser una lista de textos")
    return errs


def validar_validacion_registro(d) -> list[str]:
    errs: list[str] = []
    if not _cabecera(d, "validacion_registro", errs):
        return errs
    items = _campo(d, "reglas", list, errs, "validacion_registro")
    vistos: set[str] = set()
    for i, e in enumerate(items or []):
        ruta = f"validacion_registro.reglas[{i}]"
        if not isinstance(e, dict):
            errs.append(f"{ruta}: debe ser un objeto")
            continue
        rid = _campo(e, "regla_id", str, errs, ruta)
        if rid is not None:
            ruta = f"validacion_registro.reglas[{rid}]"
            if rid in vistos:
                errs.append(f"{ruta}: regla duplicada")
            vistos.add(rid)
        rv = _campo(e, "regla_version", str, errs, ruta, nulo=True)
        if rv is not None and not SEMVER.match(rv):
            errs.append(f"{ruta}.regla_version: {rv!r} no es MAJOR.MINOR.PATCH")
        vs = _campo(e, "validacion_sintetica", str, errs, ruta)
        if vs is not None and vs not in VALIDACION_SINTETICA:
            errs.append(f"{ruta}.validacion_sintetica: {vs!r} no válido")
        vo = _campo(e, "validacion_operacional", str, errs, ruta)
        if vo is not None and vo not in VALIDACION_OPERACIONAL:
            errs.append(f"{ruta}.validacion_operacional: {vo!r} no válido")
        for k in ("extracto_id", "fecha", "confirmado_por"):
            _campo(e, k, str, errs, ruta, nulo=True)
        if "parametros_confirmados" not in e:
            errs.append(f"{ruta}: falta 'parametros_confirmados' (use null)")
        if vo == "confirmada":                      # solo con evidencia real y confirmación explícita (spec §10.5)
            for k in ("extracto_id", "fecha", "confirmado_por", "regla_version"):
                if not e.get(k):
                    errs.append(f"{ruta}: 'confirmada' exige {k}")
        if vs == "aprobada" and not e.get("regla_version"):
            errs.append(f"{ruta}: 'aprobada' exige regla_version (la regla debe existir)")
    return errs


VALIDADORES = {"definiciones": validar_definiciones, "reglas": validar_reglas, "mapeo_columnas": validar_mapeo_columnas,
               "validacion_registro": validar_validacion_registro}


def validar(nombre: str, datos: dict) -> list[str]:
    """Lista de errores estructurales (vacía = válido). No interpreta reglas de negocio."""
    return VALIDADORES[nombre](datos)


def validar_todo(directorio: Path | None = None) -> dict[str, list[str]]:
    return {n: validar(n, cargar(n, directorio)) for n in ARCHIVOS}


def indice_definiciones(datos: dict) -> dict[str, dict]:
    """id -> definición. Una definición inexistente lanza KeyError con el id (no se devuelve un valor por defecto)."""
    return {e["id"]: e for e in datos["definiciones"]}


def versiones(directorio: Path | None = None) -> dict:
    """Versión de cada archivo de configuración (para identificar qué versión se usó)."""
    return {n: cargar(n, directorio)["version"] for n in ARCHIVOS}
