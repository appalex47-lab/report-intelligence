"""Motor de reglas de negocio (Fase 2A).

Separación de responsabilidades (las reglas NO leen archivos ni modifican datos):
    lectura y normalización  -> `validator/normalizar.py`  (construye un `Contexto` de solo lectura)
    motor de reglas          -> este módulo (catálogo de reglas desde `config/reglas.json`, ejecución, estados)
    reglas                   -> `validator/rules_datos.py`, `validator/rules_conc.py` (una función por regla)
    resultados y evidencias  -> `Resultado` (inmutable, con su evidencia)
    consumo                  -> `a_hallazgos()` convierte a `Finding` (con `severity` heredado); ningún servicio lo
                                invoca todavía: los flags de `reglas.json` siguen desactivados.

Cada regla es DATO (id, versión, unidades, columnas requeridas, parámetros, severidad, mensajes) y una función que
solo calcula. Nada se inventa: un dato faltante produce `not_verifiable` con `faltante`, nunca un cero.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Callable

from .. import config
from ..models import Finding

ESTADOS = config.ESTADOS_REGLA                                  # valid | warning | error | not_verifiable | not_applicable
ESTADO_VALIDACION = "not_validated_with_real_data"             # sexto estado: regla implementada, sin validación operacional
ESTADOS_COMPLETOS = ESTADOS + (ESTADO_VALIDACION,)
_ESTADO_A_VERIFICACION = {"valid": "verificado", "warning": "supuesto", "error": "inconsistente", "not_verifiable": "no_verificable"}


@dataclass(frozen=True)
class Resultado:
    """Resultado inmutable de una regla. `estado` es el desenlace; `estado_validacion` dice si la regla está validada
    con datos reales (no lo está mientras no exista confirmación en `validacion_registro.json`)."""
    regla_id: str
    regla_version: str
    codigo: str
    estado: str
    severity: str
    mensaje: str
    evidencia: dict = field(default_factory=dict)
    faltante: tuple = ()
    valor: Decimal | None = None
    estado_validacion: str = ESTADO_VALIDACION
    tipo: str | None = None
    verificacion: str | None = None               # excepción al estado_verificacion derivado del estado (p. ej. «verificado» en un aviso aritmético)

    def __post_init__(self):
        if self.estado not in ESTADOS:
            raise ValueError(f"estado {self.estado!r} no válido; opciones: {ESTADOS}")
        if self.severity not in config.SEVERITIES:
            raise ValueError(f"severity {self.severity!r} no válida")
        if self.estado == "not_verifiable" and not self.faltante:
            raise ValueError(f"{self.regla_id}/{self.codigo}: not_verifiable exige `faltante` (qué dato falta)")

    @property
    def id(self) -> str:
        return f"{self.regla_id}/{self.codigo}"

    def to_dict(self) -> dict:
        return {"regla_id": self.regla_id, "regla_version": self.regla_version, "codigo": self.codigo, "estado": self.estado,
                "severity": self.severity, "mensaje": self.mensaje, "evidencia": _json(self.evidencia),
                "faltante": [dict(x) if isinstance(x, dict) else x for x in self.faltante],
                "valor": None if self.valor is None else str(self.valor), "estado_validacion": self.estado_validacion}

    def a_hallazgo(self) -> Finding:
        """Adaptador a `Finding`: `severity` heredado (nunca 'block'); campos de Fase 1 poblados cuando aplican."""
        kw = {"tipo": self.tipo, "regla_id": self.regla_id, "regla_version": self.regla_version}
        ver = self.verificacion or _ESTADO_A_VERIFICACION.get(self.estado)
        if ver:
            kw["estado_verificacion"] = ver
            if ver == "no_verificable":
                kw["faltante"] = self.faltante
        return Finding(self.id, self.severity, self.mensaje, _evidencia_texto(self.evidencia), **kw)


def _json(o):
    if isinstance(o, Decimal):
        return str(o)
    if isinstance(o, dict):
        return {str(k): _json(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, set, frozenset)):
        return [_json(v) for v in (sorted(o, key=str) if isinstance(o, (set, frozenset)) else o)]
    return o


def _evidencia_texto(ev: dict) -> str:
    return "; ".join(f"{k}={_json(v)}" for k, v in list(ev.items())[:6])


# ------------------------------------------------------------------------------------------------ catálogo y registro
FUNCIONES: dict[str, Callable] = {}


def regla(regla_id: str):
    """Registra la función que implementa una regla del catálogo."""
    def deco(fn):
        FUNCIONES[regla_id] = fn
        return fn
    return deco


@dataclass(frozen=True)
class Definicion:
    """Una regla del catálogo `config/reglas.json` (solo lectura)."""
    datos: dict
    parametros: dict                       # nombre -> valor (None si no está configurado)
    validacion: str                        # estado de validación operacional

    def __getitem__(self, k):
        return self.datos[k]

    @property
    def id(self) -> str:
        return self.datos["id"]

    @property
    def version(self) -> str:
        return self.datos["version"]

    def p(self, nombre: str):
        return self.parametros.get(nombre)

    def severidad_de(self, clave: str, estado: str) -> str:
        """`severity` heredado de un resultado: primero la excepción por clave, si no la de su estado."""
        return self.datos["severidad_codigos"].get(clave) or self.datos["severidad"][estado]

    def mensaje(self, clave: str, **kw) -> str:
        plantilla = self.datos["mensajes"].get(clave)
        if plantilla is None:
            raise KeyError(f"{self.id}: falta el mensaje {clave!r} en config/reglas.json")
        return plantilla.format(**kw)

    def resultado(self, codigo: str, estado: str, *, clave: str | None = None, evidencia: dict | None = None, faltante=(),
                  valor: Decimal | None = None, severity: str | None = None, verificacion: str | None = None, **kw) -> Resultado:
        clave = clave or f"{codigo}.{estado}"
        sev = severity or self.severidad_de(clave, estado)
        return Resultado(self.id, self.version, codigo, estado, sev, self.mensaje(clave, **kw), evidencia or {},
                         tuple(faltante), valor, self.validacion, self.datos.get("tipo"), verificacion)


def catalogo(cfg: dict | None = None, registro: dict | None = None, overrides: dict | None = None) -> dict[str, Definicion]:
    """Lee el catálogo de reglas y resuelve parámetros y estado de validación. `overrides` (solo pruebas) sustituye parámetros."""
    cfg = cfg if cfg is not None else config.cargar("reglas")
    registro = registro if registro is not None else config.cargar("validacion_registro")
    vo = {e["regla_id"]: e["validacion_operacional"] for e in registro["reglas"]}
    pars = {k: v["valor"] for k, v in cfg["parametros"].items()}
    pars.update(overrides or {})
    out = {}
    for r in cfg["reglas"]:
        estado_val = vo.get(r["id"], "no_validada_con_datos_reales")
        etiqueta = ESTADO_VALIDACION if estado_val == "no_validada_con_datos_reales" else ("confirmed" if estado_val == "confirmada" else "not_applicable")
        d = dict(r)
        d["dimensiones_declaradas"] = cfg.get("dimensiones", {})
        out[r["id"]] = Definicion(d, {n: pars.get(n) for n in r["parametros"]}, etiqueta)
    return out


# ------------------------------------------------------------------------------------------------ ejecución
def faltantes_de(ctx, columnas_requeridas: list[dict]) -> tuple:
    """Columnas requeridas que no existen en el contexto (hoja ausente o columna ausente)."""
    out = []
    for c in columnas_requeridas:
        if c["columna"] not in ctx.columnas.get(c["hoja"], set()):
            out.append({"archivo": c["hoja"], "columna": c["columna"], "granularidad": None})
    return tuple(out)


def ejecutar(ctx, ids: list[str] | None = None, cfg: dict | None = None, registro: dict | None = None,
             overrides: dict | None = None) -> list[Resultado]:
    """Ejecuta las reglas del catálogo sobre un `Contexto`. No modifica el contexto ni escribe nada.

    Por regla: unidad no aplicable -> `not_applicable`; columnas requeridas ausentes -> `not_verifiable` con `faltante`;
    una excepción interna se muestra como `error`/`fallo_interno` (no se oculta ni detiene al resto).
    """
    from . import rules_conc, rules_datos  # noqa: F401  (registran sus funciones)
    out: list[Resultado] = []
    cat = catalogo(cfg, registro, overrides)
    desconocidas = [i for i in (ids or []) if i not in cat]
    if desconocidas:
        raise ValueError(f"Regla(s) inexistente(s) en el catálogo: {desconocidas}; opciones: {list(cat)}")
    for rid, d in cat.items():
        if ids and rid not in ids:
            continue
        if ctx.unidad not in d["unidades"]:
            out.append(d.resultado(_codigo_aplicabilidad(rid), "not_applicable", unidad=ctx.unidad,
                                   evidencia={"unidad": ctx.unidad, "unidades_aplicables": d["unidades"]}))
            continue
        falta = faltantes_de(ctx, d["columnas_requeridas"])
        if falta:
            out.append(d.resultado(_codigo_aplicabilidad(rid), "not_verifiable", clave=_clave_faltante(rid), faltante=falta,
                                   motivo="faltan columnas requeridas: " + ", ".join(f"{x['archivo']}.{x['columna']}" for x in falta),
                                   evidencia={"faltante": list(falta)}))
            continue
        try:
            out.extend(FUNCIONES[rid](ctx, d))
        except Exception as e:                                  # noqa: BLE001 — se informa, no se silencia
            out.append(Resultado(rid, d.version, "fallo_interno", "error", "warn",
                                 f"La regla falló internamente ({type(e).__name__}): {e}", {"excepcion": type(e).__name__}, (), None, d.validacion, d.datos.get("tipo")))
    return out


# código y clave de mensaje usados cuando la regla no llega a ejecutarse (aplicabilidad o columnas)
_CODIGOS = {"R-REL-PAC-PED": "relacion_paciente_pedido", "R-CUADRE-DIM": "cuadre_dimensiones", "R-CONC-COMPRAS": "conciliacion_compras",
            "R-DENOM": "razon_no_calculable", "R-COBERTURA-ATC": "relacion_pedidos_carritos"}


def _codigo_aplicabilidad(rid: str) -> str:
    return _CODIGOS[rid]


def _clave_faltante(rid: str) -> str:
    return "columnas_faltantes.not_verifiable"


def a_hallazgos(resultados: list[Resultado], incluir_validos: bool = False) -> list[Finding]:
    """Convierte resultados a `Finding`. Por defecto omite los `valid` (no son un hallazgo)."""
    return [r.a_hallazgo() for r in resultados if incluir_validos or r.estado != "valid"]


def resumen(resultados: list[Resultado]) -> dict:
    por_estado = {e: 0 for e in ESTADOS}
    for r in resultados:
        por_estado[r.estado] += 1
    return {"por_estado": por_estado, "bloquea": any(r.severity == "block" for r in resultados),
            "estado_validacion": sorted({r.estado_validacion for r in resultados})}


# ------------------------------------------------------------------------------------------------ R-DENOM reutilizable
@dataclass(frozen=True)
class Operando:
    valor: Decimal | None
    fuente: str                                   # p. ej. "sistema_ventas" | "ga4"
    periodo: str                                  # etiqueta comparable, p. ej. "2026-09"
    granularidad: str = "mes"
    nombre: str = ""                              # descripción legible ("ventas.id_pedido distintos")


@dataclass(frozen=True)
class Razon:
    id: str
    nombre: str
    numerador: Operando
    denominador: Operando
    fuentes_permitidas: tuple = ()                # pares (fuente_numerador, fuente_denominador); vacío = sin restricción
    permite_negativo: bool = False                # permite denominador y numerador negativos
    numerador_con_signo: bool = False             # el numerador es una diferencia y puede ser negativo (el denominador no)
    por_cien: bool = False


@dataclass(frozen=True)
class EvaluacionRazon:
    estado: str                                   # valid | warning | error | not_verifiable
    valor: Decimal | None                         # None si no es calculable; NUNCA 0 por falta de datos
    problemas: tuple
    faltante: tuple


def evaluar_razon(r: Razon) -> EvaluacionRazon:
    """Núcleo de R-DENOM: decide si una razón se puede calcular y con qué limitaciones. Sin redondeos ni sustituciones."""
    falta, problemas = [], []
    if r.numerador.valor is None:
        falta.append({"archivo": r.numerador.fuente, "columna": r.numerador.nombre or "numerador", "granularidad": r.numerador.granularidad})
    if r.denominador.valor is None:
        falta.append({"archivo": r.denominador.fuente, "columna": r.denominador.nombre or "denominador", "granularidad": r.denominador.granularidad})
    if falta:
        return EvaluacionRazon("not_verifiable", None, ("falta " + " y ".join(f"{x['columna']} ({x['archivo']})" for x in falta),), tuple(falta))
    den = r.denominador.valor
    if den == 0:
        return EvaluacionRazon("not_verifiable", None, ("el denominador es cero",),
                               ({"archivo": r.denominador.fuente, "columna": (r.denominador.nombre or "denominador") + " distinto de cero", "granularidad": r.denominador.granularidad},))
    if den < 0 and not r.permite_negativo:
        return EvaluacionRazon("error", None, ("el denominador es negativo",), ())
    if r.numerador.valor < 0 and not (r.permite_negativo or r.numerador_con_signo):
        return EvaluacionRazon("error", None, ("el numerador es negativo",), ())
    if r.numerador.periodo != r.denominador.periodo:
        problemas.append(f"periodos distintos ({r.numerador.periodo} frente a {r.denominador.periodo}): no equivalente temporalmente")
    if r.numerador.granularidad != r.denominador.granularidad:
        problemas.append(f"granularidades incompatibles ({r.numerador.granularidad} frente a {r.denominador.granularidad})")
    if r.fuentes_permitidas and (r.numerador.fuente, r.denominador.fuente) not in r.fuentes_permitidas:
        problemas.append(f"combinación de fuentes no prevista ({r.numerador.fuente} / {r.denominador.fuente})")
    valor = r.numerador.valor / den * (100 if r.por_cien else 1)
    return EvaluacionRazon("warning" if problemas else "valid", valor, tuple(problemas), ())


def main(argv=None) -> int:
    """python -m backend.app.validator.motor <libro.xlsx> --unidad aetops|glp1 --periodo AAAA-N [--tipo mensual|trimestral]"""
    import argparse
    from ..models import Period
    from .normalizar import construir_contexto
    ap = argparse.ArgumentParser(description="Ejecuta el motor de reglas sobre un libro de datos crudos (solo lectura)")
    ap.add_argument("libro")
    ap.add_argument("--unidad", required=True, choices=["aetops", "glp1"])
    ap.add_argument("--periodo", required=True, help="AAAA-N (mes 1-12 o trimestre 1-4)")
    ap.add_argument("--tipo", default="mensual", choices=["mensual", "trimestral"])
    a = ap.parse_args(argv)
    y, i = (int(x) for x in a.periodo.split("-"))
    ctx = construir_contexto(a.libro, Period("GLP1" if a.unidad == "glp1" else "AETOPS", a.tipo, y, i))
    res = ejecutar(ctx)
    for r in res:
        print(f"[{r.estado:<14}] {r.id}: {r.mensaje}")
    print(resumen(res))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
