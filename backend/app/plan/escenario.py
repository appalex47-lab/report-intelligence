"""Escenarios de presentación del reporte (bloque integral: Escenarios y SlideSpec).

Un escenario describe PARA QUÉ se hace el reporte y qué debe cumplir su estructura: objetivo, audiencia, contexto, mensaje central, profundidad,
tipo de análisis, orden narrativo, indicadores relevantes y tipo de conclusión. NO son los escenarios financieros E1/E2 de la Fase 4 (`escenarios.py`).

Reglas:
* El catálogo (`config/escenarios_reporte.json`) solo contiene lo que la documentación define; lo demás es `None` («no definido»), nunca se inventa.
* Un escenario es configurable (se puede ajustar por reporte) y reutilizable (se puede guardar en el historial local como escenario propio).
* Controla cosas reales: el contexto de negocio llega a la hoja «Contexto aportado por el equipo»; el orden narrativo, los tipos obligatorios, la
  profundidad, los indicadores relevantes y el tipo de conclusión son las expectativas contra las que el QA integral valida la estructura.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

ESQUEMA = "escenarios_reporte/1"
CATALOGO = Path(__file__).resolve().parents[1] / "config" / "escenarios_reporte.json"

PROFUNDIDADES = ("ejecutivo", "intermedio", "detallado")
TIPOS_CONCLUSION = ("acciones_priorizadas", "resumen_hechos", "sin_conclusion")
# Tipos de diapositiva reconocidos (los usa SlideSpec). «contenido» = no clasificada: se informa, nunca se oculta.
TIPOS_DIAPOSITIVA = ("resumen_ejecutivo", "panorama", "canales", "lineas", "categorias", "productos", "negados", "perfil_paciente",
                     "comportamiento_compra", "engagement_digital", "conclusiones", "recomendaciones", "descubrimiento", "anexo_calidad", "contenido")
INDICADORES = ("monto", "pacientes", "ticket", "piezas")             # los que expone el panorama de AETOPS (`service._kpis`)
CAMPOS_TEXTO = ("objetivo", "audiencia", "contexto_negocio", "mensaje_central", "tipo_analisis")
MAX_TEXTO = 800
_ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")


class ErrorEscenario(ValueError):
    """El escenario no es válido (el mensaje dice qué campo y por qué)."""


@dataclass(frozen=True)
class EscenarioReporte:
    id: str
    nombre: str
    perfil: str = "*"                                   # «unidad/periodicidad» o «*» (cualquiera)
    objetivo: str | None = None
    audiencia: str | None = None
    contexto_negocio: str | None = None
    mensaje_central: str | None = None
    profundidad: str = "ejecutivo"
    tipo_analisis: str | None = None
    orden_narrativo: tuple[str, ...] = ()
    tipos_obligatorios: tuple[str, ...] = ()
    indicadores_relevantes: tuple[str, ...] = ()
    tipo_conclusion: str = "acciones_priorizadas"
    origen: str = "catalogo"                            # catalogo | usuario | ajustado

    def to_dict(self) -> dict:
        d = asdict(self)
        for k in ("orden_narrativo", "tipos_obligatorios", "indicadores_relevantes"):
            d[k] = list(d[k])
        return d

    def no_definidos(self) -> list[str]:
        """Campos descriptivos que la especificación no define para este escenario (se informan, no se rellenan)."""
        return [c for c in CAMPOS_TEXTO if not (getattr(self, c) or "").strip()]

    def huella(self) -> str:
        d = self.to_dict()
        d.pop("origen", None)
        return hashlib.sha256(json.dumps(d, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _texto(d: dict, campo: str) -> str | None:
    v = d.get(campo)
    if v is None:
        return None
    if not isinstance(v, str):
        raise ErrorEscenario(f"«{campo}» debe ser texto.")
    v = v.strip()
    if len(v) > MAX_TEXTO:
        raise ErrorEscenario(f"«{campo}» excede {MAX_TEXTO} caracteres.")
    return v or None


def _lista(d: dict, campo: str, permitidos: tuple[str, ...] | None) -> tuple[str, ...]:
    v = d.get(campo, [])
    if v is None:
        v = []
    if not isinstance(v, (list, tuple)) or not all(isinstance(x, str) for x in v):
        raise ErrorEscenario(f"«{campo}» debe ser una lista de textos.")
    if len(set(v)) != len(v):
        raise ErrorEscenario(f"«{campo}» tiene elementos repetidos.")
    if permitidos is not None:
        malos = [x for x in v if x not in permitidos]
        if malos:
            raise ErrorEscenario(f"«{campo}» tiene valores no reconocidos: {', '.join(map(repr, malos))}.")
    return tuple(v)


def desde_dict(d: dict, origen: str = "catalogo") -> EscenarioReporte:
    """Valida y construye. Rechaza campos desconocidos para que un error de escritura no pase como «no definido»."""
    if not isinstance(d, dict):
        raise ErrorEscenario("El escenario debe ser un objeto.")
    conocidos = set(EscenarioReporte.__dataclass_fields__) - {"origen"}
    extra = sorted(set(d) - conocidos)
    if extra:
        raise ErrorEscenario(f"Campos no reconocidos: {', '.join(extra)}.")
    id_ = d.get("id")
    if not isinstance(id_, str) or not _ID.fullmatch(id_):
        raise ErrorEscenario("«id» debe ser minúsculas, dígitos, guion o guion bajo (máx. 64).")
    nombre = d.get("nombre")
    if not isinstance(nombre, str) or not nombre.strip() or len(nombre) > 120:
        raise ErrorEscenario("«nombre» es obligatorio (máx. 120 caracteres).")
    prof = d.get("profundidad", "ejecutivo")
    if prof not in PROFUNDIDADES:
        raise ErrorEscenario(f"«profundidad» debe ser una de {', '.join(PROFUNDIDADES)}.")
    conc = d.get("tipo_conclusion", "acciones_priorizadas")
    if conc not in TIPOS_CONCLUSION:
        raise ErrorEscenario(f"«tipo_conclusion» debe ser uno de {', '.join(TIPOS_CONCLUSION)}.")
    perfil = d.get("perfil", "*")
    if not isinstance(perfil, str) or not re.fullmatch(r"\*|[a-z0-9]+/[a-z]+", perfil):
        raise ErrorEscenario("«perfil» debe ser «unidad/periodicidad» (p. ej. aetops/mensual) o «*».")
    orden = _lista(d, "orden_narrativo", TIPOS_DIAPOSITIVA)
    oblig = _lista(d, "tipos_obligatorios", TIPOS_DIAPOSITIVA)
    if orden and not set(oblig) <= set(orden):
        raise ErrorEscenario("«tipos_obligatorios» debe estar contenido en «orden_narrativo».")
    ind = _lista(d, "indicadores_relevantes", INDICADORES)
    return EscenarioReporte(id=id_, nombre=nombre.strip(), perfil=perfil, profundidad=prof, tipo_conclusion=conc, orden_narrativo=orden,
                            tipos_obligatorios=oblig, indicadores_relevantes=ind, origen=origen,
                            **{c: _texto(d, c) for c in CAMPOS_TEXTO})


def catalogo(ruta: Path = CATALOGO) -> dict[str, EscenarioReporte]:
    """Escenarios del catálogo, validados. Un catálogo dañado es un error visible, no un catálogo vacío."""
    try:
        datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ErrorEscenario(f"No se pudo leer el catálogo de escenarios ({type(e).__name__}).") from None
    if datos.get("esquema") != ESQUEMA:
        raise ErrorEscenario(f"Esquema de catálogo no reconocido: {datos.get('esquema')!r}.")
    out: dict[str, EscenarioReporte] = {}
    for d in datos.get("escenarios", []):
        e = desde_dict(d, "catalogo")
        if e.id in out:
            raise ErrorEscenario(f"Escenario repetido en el catálogo: {e.id}.")
        out[e.id] = e
    return out


def id_para_perfil(unidad: str, periodicidad: str) -> str:
    return f"{unidad.lower()}-{periodicidad.lower()}"


def ajustar(base: EscenarioReporte, cambios: dict | None) -> EscenarioReporte:
    """Ajustes por reporte sobre un escenario (mismo esquema y mismas validaciones). Si cambia algo, el origen pasa a «ajustado»."""
    if not cambios:
        return base
    d = base.to_dict()
    d.pop("origen")
    for k, v in cambios.items():
        if k in ("id", "origen"):
            continue
        d[k] = v
    nuevo = desde_dict(d, "ajustado")
    return replace(nuevo, origen="ajustado") if nuevo.huella() != base.huella() else base


def lineas_contexto(e: EscenarioReporte) -> list[str]:
    """El contexto de negocio del escenario, como líneas para la hoja «Contexto aportado por el equipo» (texto del equipo, no verificado)."""
    return [x.strip() for x in (e.contexto_negocio or "").splitlines() if x.strip()]


# ---------------------------------------------------------------------------------------------------- escenarios propios (reutilizables)
_TABLA = "CREATE TABLE IF NOT EXISTS escenarios_reporte(id TEXT PRIMARY KEY, json TEXT NOT NULL)"


def _con(con: sqlite3.Connection) -> sqlite3.Connection:
    con.execute(_TABLA)
    return con


def listar_propios(con: sqlite3.Connection) -> dict[str, EscenarioReporte]:
    out = {}
    for id_, js in _con(con).execute("SELECT id, json FROM escenarios_reporte ORDER BY id"):
        try:
            out[id_] = desde_dict(json.loads(js), "usuario")
        except (ValueError, ErrorEscenario):
            continue                                       # un registro dañado no tumba el resto; no se muestra como válido
    return out


def guardar_propio(con: sqlite3.Connection, d: dict) -> EscenarioReporte:
    e = desde_dict(d, "usuario")
    if e.id in catalogo():
        raise ErrorEscenario(f"«{e.id}» es un escenario del catálogo; usa otro id para guardar uno propio.")
    dd = e.to_dict()
    dd.pop("origen")
    _con(con).execute("INSERT OR REPLACE INTO escenarios_reporte(id, json) VALUES(?, ?)", (e.id, json.dumps(dd, ensure_ascii=False, sort_keys=True)))
    con.commit()
    return e


def borrar_propio(con: sqlite3.Connection, id_: str) -> bool:
    cur = _con(con).execute("DELETE FROM escenarios_reporte WHERE id = ?", (id_,))
    con.commit()
    return cur.rowcount > 0


def todos(con: sqlite3.Connection | None = None) -> dict[str, EscenarioReporte]:
    out = dict(catalogo())
    if con is not None:
        out.update({k: v for k, v in listar_propios(con).items() if k not in out})
    return out
