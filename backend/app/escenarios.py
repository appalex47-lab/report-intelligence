"""Fase 4 · Escenarios E1 y E2 e indicador IND-01 para la pantalla de revisión (spec Fase 1 §8; docs/fase4/IMPLEMENTACION_FASE4.md).

Este módulo SOLO LEE y presenta. No define fórmulas nuevas ni valores nuevos:
  · E1 (F-09) y E2 (F-10, F-11) usan las MISMAS cifras que la narrativa vigente (`narrative/executive.py`, `narrative/glp1_exec.py`),
    tomadas de los mismos bloques del motor; los porcentajes (25 % y 10 %) son los de `NarrativeRules` (los que se aplican de verdad)
    y se rotulan «Supuesto heredado, no validado».
  · IND-01 (F-01, F-02) reutiliza `validator/rel_pedidos_carritos.py` (regla R-COBERTURA-ATC) y `validator/operandos.py`.
Nunca suma ni sustituye las dos fuentes de pedidos, nunca calcula `100 − relación`, nunca trunca un valor superior a 100 %, y
un dato que falta es un estado («no verificable» con su `faltante`), nunca un cero.

Cada dato lleva un `tipo`: «observado» (viene del libro), «calculado» (aritmética sobre observados), «supuesto_heredado»
(parámetro histórico sin validación con datos reales) o «no_verificable». Fallar aquí NO impide generar el reporte (principio S-3).
"""
from __future__ import annotations

from decimal import Decimal

from . import config
from .narrative.rules import RULES

ESQUEMA = "escenarios_indicador/1"
ETIQUETA_SUPUESTO = "Supuesto heredado, no validado"
ACLARACION_ABANDONADOS = ("Métrica agregada heredada del embudo («carritos_abandonados»): dato de la fuente o derivado "
                          "(add_to_cart − compras). No constituye abandono individual comprobado.")
AVISO_MAYOR_100 = ("La relación supera 100 %. Esto puede ocurrir porque pedidos y carritos no necesariamente representan unidades "
                   "equivalentes, o porque sus fuentes, periodos, universos o filtros no coinciden. Interprétese con cautela.")
SIN_TRAFICO = "No aplica: sin hoja `trafico`"
# Denominaciones que ninguna salida nueva puede contener (spec §8.2). Las pruebas barren toda la estructura contra esta lista.
DENOMINACIONES_PROHIBIDAS = ("carritos abandonados comprobados", "usuarios que abandonaron el carrito",
                             "carritos sin compra identificados individualmente", "carritos únicos", "carritos unicos")

TIPOS = ("observado", "calculado", "supuesto_heredado", "no_verificable")


def _s(x) -> str | None:
    return None if x is None else str(x)


def _n(x, dec=2) -> str:
    return f"{x:,.{dec}f}"


def _var(clave, nombre, valor, tipo, fuente, unidad="", nota="", **extra) -> dict:
    assert tipo in TIPOS, tipo
    return {"clave": clave, "nombre": nombre, "valor": _s(valor), "unidad": unidad, "tipo": tipo, "fuente": fuente, "nota": nota, **extra}


# ------------------------------------------------------------------------------------------------ supuestos heredados
def supuestos() -> dict:
    """Los dos porcentajes heredados con su procedencia. El valor EFECTIVO es el de `NarrativeRules` (el que usa la narrativa); la
    configuración (`config/reglas.json`) los documenta: si difirieran, se declara la inconsistencia en vez de elegir en silencio."""
    par = config.cargar("reglas")["parametros"]
    out = {}
    for clave, regla, ref, pid in (("r", RULES.recovery_scenario, "backend/app/narrative/rules.py:21", "e1_recuperacion_negados_medio"),
                                   ("c", RULES.cart_recovery_scenario, "backend/app/narrative/rules.py:25", "e2_recuperacion_abandono_medio")):
        cfg = par.get(pid, {})
        incons = cfg.get("valor") is None or Decimal(str(cfg["valor"])) != regla
        out[clave] = {"valor": regla, "etiqueta": ETIQUETA_SUPUESTO, "origen": cfg.get("origen", "heredado"), "referencia": ref,
                      "parametro": pid, "validacion_operacional": cfg.get("validacion_operacional", "no_validada_con_datos_reales"),
                      "inconsistencia_configuracion": bool(incons),
                      "variantes": {"conservador": "No configurado", "optimista": "No configurado"}}
    return out


# ------------------------------------------------------------------------------------------------ entradas desde el motor
def _entradas(res, unidad: str) -> dict:
    """Cifras de entrada tomadas de los MISMOS bloques que la narrativa. Un valor ausente es None (faltante), nunca 0."""
    if unidad == "glp1":
        pano = res.blocks.get("panorama")
        P = pano.rows[0].values if pano and pano.rows else {}
        g = lambda k: (P[k].v if k in P and P[k] is not None else None)          # noqa: E731
        neg = res.blocks.get("negados")
        m_neg = sum(((r.values["monto_negado"].v or Decimal(0)) for r in neg.rows), Decimal(0)) if neg and neg.rows else None
        sin_monto = sum(1 for r in (neg.rows if neg else []) if r.values["monto_negado"].v is None)
        emb = next((r for r in (res.funnel.rows if res.funnel else []) if r.key == "carritos abandonados"), None)
        derivado = bool(emb and emb.values.get("conteo") is not None and "derivado" in (emb.values["conteo"].note or ""))
        return {"venta": g("monto"), "m_neg": m_neg, "negados_sin_monto": sin_monto, "negados_hoja": neg is not None and bool(neg.rows), "abandonados": g("carritos_abandonados"),
                "ticket": g("ticket"), "pedidos": g("pedidos"), "embudo_derivado": derivado, "tiene_embudo": res.funnel is not None}
    from .narrative.aetops import val                                              # AETOPS: misma lectura que executive.py
    T = res.tables
    py = T["aetops.panorama.yoy"].groups[0] if "aetops.panorama.yoy" in T and T["aetops.panorama.yoy"].groups else None
    alta = res.negados.get("aetops.negados.alta") if getattr(res, "negados", None) else None
    return {"venta": val(py.current, "monto") if py else None, "m_neg": alta.total.v if alta is not None and alta.total is not None else None,
            "negados_sin_monto": 0, "negados_hoja": alta is not None, "abandonados": None, "ticket": None, "pedidos": None, "embudo_derivado": False, "tiene_embudo": False}


# ------------------------------------------------------------------------------------------------ E1
def escenario_e1(venta, m_neg, r, hay_hoja_negados: bool, negados_sin_monto: int = 0) -> dict:
    """F-09: Ingreso_ilustrativo = M_neg × r;  Proporción = Ingreso_ilustrativo / Venta_total."""
    sup = supuestos()["r"]
    base = {"id": "E1", "nombre": "Recuperación de negados", "unidades": ["GLP-1", "AETOPS"],
            "formula": "Ingreso ilustrativo = M_neg × r;  Proporción de la venta = Ingreso ilustrativo ÷ Venta total   (F-09)",
            "etiqueta": ETIQUETA_SUPUESTO, "variantes": sup["variantes"], "advertencias": [],
            "objetivo": "Ilustrar el monto que equivaldría recuperar una fracción de lo negado por falta de stock."}
    faltan = []
    if m_neg is None:
        faltan.append({"archivo": "negados", "columna": "monto_negado", "granularidad": "libro"})
    if venta is None or venta <= 0:
        faltan.append({"archivo": "ventas", "columna": "monto_venta (Venta total del periodo > 0)", "granularidad": "periodo"})
    variables = [_var("M_neg", "Monto negado", m_neg, "observado" if m_neg is not None else "no_verificable",
                      "Σ negados.monto_negado", "MXN", "negados no trae fecha: se asume que corresponde al periodo del reporte (no verificable)"),
                 _var("r", "Porcentaje de recuperación", r, "supuesto_heredado", sup["referencia"], "fracción",
                      "Supuesto heredado, no validado con datos reales. No es una tasa observada.", etiqueta=ETIQUETA_SUPUESTO,
                      origen=sup["origen"], validacion=sup["validacion_operacional"]),
                 _var("Venta_total", "Venta total del periodo", venta, "observado" if venta is not None else "no_verificable",
                      "Σ ventas.monto_venta del periodo", "MXN")]
    if faltan:
        return base | {"estado": "no_verificable", "faltante": faltan, "variables": variables, "resultado": None,
                       "lectura": "No verificable: faltan datos para calcular el escenario. No se sustituye por otra fuente ni se muestra 0.",
                       "efecto_supuesto": None,
                       "confiable": [], "requiere_validacion": ["Disponer de negados.monto_negado y de la venta total del periodo."],
                       "limitaciones": _lim_e1()}
    ingreso = m_neg * r
    prop = ingreso / venta
    ratio = m_neg / venta
    avisos = ([f"{negados_sin_monto} fila(s) de negados no traen monto_negado: la presentación las suma como 0 y este panel hace lo mismo para "
               "coincidir con ella. El monto negado puede estar subestimado: complete el libro."] if negados_sin_monto else [])
    return base | {"advertencias": avisos,
        "estado": "calculable", "faltante": [], "variables": variables,
        "resultado": {"ingreso_ilustrativo": _s(ingreso), "proporcion_venta": _s(prop), "negados_sobre_venta": _s(ratio), "tipo": "calculado"},
        "lectura": (f"Escenario ilustrativo: recuperar {_n(r * 100, 0)} % de {_n(m_neg)} negados equivaldría a {_n(ingreso)} "
                    f"({_n(prop * 100)} % de la venta del periodo). No es un pronóstico ni un resultado observado."),
        "efecto_supuesto": (f"El resultado es proporcional a r: cada punto porcentual de r equivale a {_n(m_neg / 100)} (= M_neg × 1 %). "
                            f"Con otro valor de r el resultado cambia en la misma proporción; el {_n(r * 100, 0)} % es el heredado y no hay "
                            "otro valor aprobado."),
        "confiable": [f"El monto negado ({_n(m_neg)}) y la venta total ({_n(venta)}) provienen del libro.",
                      f"Los negados equivalen a {_n(ratio * 100)} % de la venta (cálculo directo sobre los dos datos observados)."],
        "requiere_validacion": [f"Que el {_n(r * 100, 0)} % de recuperación sea alcanzable (supuesto heredado, no validado).",
                                "Que el monto negado sea demanda recuperable.",
                                "Que el monto negado corresponda al periodo del reporte (negados no trae fecha)."],
        "limitaciones": _lim_e1()}


def _lim_e1() -> list[str]:
    return ["Monto negado ≠ demanda recuperable.", "No es un pronóstico.", "No se suma entre periodos.",
            "negados no trae fecha: se asume que corresponde al periodo del reporte, lo que el libro no permite verificar."]


# ------------------------------------------------------------------------------------------------ E2
def escenario_e2(unidad: str, venta, abandonados, ticket, c, derivado_en_embudo: bool, tiene_embudo: bool) -> dict:
    """F-10: Ingreso_ilustrativo = A × c × T, con T = monto_venta ÷ pedidos del sistema de ventas (F-11). Fórmula y condición
    (`A > 0` y `T > 0`) idénticas a la narrativa vigente; solo GLP-1."""
    sup = supuestos()["c"]
    base = {"id": "E2", "nombre": "Recuperación de abandono", "unidades": ["GLP-1"],
            "denominacion_historica": "La denominación «Recuperación de abandono» es histórica y no demuestra abandono individual.",
            "formula": "Ingreso ilustrativo = A × c × T;  Proporción de la venta = Ingreso ilustrativo ÷ Venta total   (F-10, F-11)",
            "etiqueta": ETIQUETA_SUPUESTO, "variantes": sup["variantes"], "aclaracion_metrica": ACLARACION_ABANDONADOS, "advertencias": [],
            "objetivo": "Ilustrar el monto equivalente a cerrar una fracción de la métrica heredada «carritos_abandonados»."}
    if unidad != "glp1":
        return base | {"estado": "no_aplica", "faltante": [], "variables": [], "resultado": None, "lectura": SIN_TRAFICO + " (AETOPS no tiene tráfico).",
                       "efecto_supuesto": None, "confiable": [], "requiere_validacion": [], "limitaciones": _lim_e2()}
    variables = [
        _var("A", "carritos_abandonados (métrica agregada heredada)", abandonados, "observado" if abandonados else "no_verificable",
             "trafico.carritos_abandonados (nivel sitio, periodo)", "conteo de la fuente", ACLARACION_ABANDONADOS),
        _var("c", "Porcentaje de cierre", c, "supuesto_heredado", sup["referencia"], "fracción",
             "Supuesto heredado, no validado con datos reales. No es una tasa observada.", etiqueta=ETIQUETA_SUPUESTO,
             origen=sup["origen"], validacion=sup["validacion_operacional"]),
        _var("T", "Ticket promedio", ticket, "calculado" if ticket else "no_verificable", "Σ monto_venta ÷ pedidos del sistema de ventas (F-11)", "MXN",
             "El ticket de pedidos concretados puede no representar el de un carrito no concretado."),
        _var("Venta_total", "Venta total del periodo", venta, "observado" if venta else "no_verificable", "Σ ventas.monto_venta del periodo", "MXN")]
    faltan = []
    if not tiene_embudo:
        faltan.append({"archivo": "trafico", "columna": "carritos_abandonados / add_to_cart / compras", "granularidad": "mes"})
    if not abandonados:
        faltan.append({"archivo": "trafico", "columna": "carritos_abandonados (A > 0)", "granularidad": "mes"})
    if not ticket:
        faltan.append({"archivo": "ventas", "columna": "monto_venta y pedidos (T > 0)", "granularidad": "periodo"})
    if not venta:
        faltan.append({"archivo": "ventas", "columna": "monto_venta (Venta total > 0)", "granularidad": "periodo"})
    if faltan:
        nota = ("La columna carritos_abandonados vino vacía: el embudo la deriva (add_to_cart − compras) pero el escenario conserva su "
                "condición vigente `A > 0` sobre el dato de la fuente, por lo que no se muestra." if (tiene_embudo and not abandonados and derivado_en_embudo) else
                "No verificable: faltan datos. No se sustituye por IND-01 ni por otra fuente.")
        return base | {"estado": "no_verificable", "faltante": faltan, "variables": variables, "resultado": None, "lectura": nota,
                       "efecto_supuesto": None, "confiable": [],
                       "requiere_validacion": ["Disponer de carritos_abandonados, ticket y venta total del periodo."], "limitaciones": _lim_e2()}
    ingreso = abandonados * c * ticket
    prop = ingreso / venta
    return base | {
        "estado": "calculable", "faltante": [], "variables": variables,
        "resultado": {"ingreso_ilustrativo": _s(ingreso), "proporcion_venta": _s(prop), "tipo": "calculado"},
        "lectura": (f"Escenario ilustrativo: cerrar {_n(c * 100, 0)} % de {_n(abandonados, 0)} (métrica heredada «carritos_abandonados») con el "
                    f"ticket promedio ({_n(ticket)}) equivaldría a {_n(ingreso)} ({_n(prop * 100)} % de la venta). No es un pronóstico ni un resultado observado."),
        "efecto_supuesto": (f"El resultado es proporcional a c: cada punto porcentual de c equivale a {_n(abandonados * ticket / 100)} (= A × T × 1 %). "
                            f"El {_n(c * 100, 0)} % es el heredado y no hay otro valor aprobado."),
        "confiable": [f"La métrica carritos_abandonados ({_n(abandonados, 0)}) y la venta total ({_n(venta)}) provienen del libro; el ticket es un cociente de datos observados."],
        "requiere_validacion": [f"Que el {_n(c * 100, 0)} % de cierre sea alcanzable (supuesto heredado, no validado).",
                                "Qué cuenta exactamente la fuente como «carritos_abandonados» (definición de la herramienta de analítica no verificable con el libro).",
                                "Que el ticket de pedidos concretados represente al de un carrito no concretado."],
        "limitaciones": _lim_e2()}


def _lim_e2() -> list[str]:
    return ["A es un agregado heredado: no demuestra abandono individual.",
            "El ticket de pedidos concretados puede no representar el de un carrito no concretado.",
            "No es un pronóstico ni un resultado observado.", "Solo GLP-1: AETOPS no tiene hoja `trafico`."]


# ------------------------------------------------------------------------------------------------ comparación E1 vs E2
def _dep(e1: dict, e2: dict) -> str:
    """«r = 25 % y c = 10 %» con los valores que realmente se aplican (no un texto fijo)."""
    partes = [f"{v['clave']} = {_n(Decimal(v['valor']) * 100, 0)} %" for e in (e1, e2) for v in e["variables"] if v["tipo"] == "supuesto_heredado" and v["valor"]]
    return " y ".join(partes) or "los supuestos heredados"


def comparar(e1: dict, e2: dict) -> dict:
    """Lado a lado, sin ocultar diferencias metodológicas. NO suma los montos: no se ha verificado que no se solapen."""
    def monto(e):
        return e["resultado"]["ingreso_ilustrativo"] if e.get("resultado") else None
    filas = [
        {"aspecto": "Qué ilustra", "e1": "Fracción de lo negado por falta de stock", "e2": "Fracción de la métrica heredada «carritos_abandonados»"},
        {"aspecto": "Supuesto del que depende", "e1": f"r = {_n(Decimal(e1['variables'][1]['valor']) * 100, 0)} % ({ETIQUETA_SUPUESTO})" if e1["variables"][1]["valor"] else ETIQUETA_SUPUESTO,
         "e2": f"c = {_n(Decimal(e2['variables'][1]['valor']) * 100, 0)} % ({ETIQUETA_SUPUESTO})" if e2["variables"] and e2["variables"][1]["valor"] else "No aplica"},
        {"aspecto": "Dato base (observado)", "e1": "Σ negados.monto_negado", "e2": "trafico.carritos_abandonados (nivel sitio)"},
        {"aspecto": "Dato intermedio calculado", "e1": "Ninguno", "e2": "Ticket = monto_venta ÷ pedidos del sistema de ventas"},
        {"aspecto": "Unidades de negocio", "e1": "GLP-1 y AETOPS", "e2": "Solo GLP-1"},
        {"aspecto": "Lo que NO demuestra", "e1": "Que lo negado sea demanda recuperable", "e2": "Abandono individual comprobado"},
        {"aspecto": "Relación con IND-01", "e1": "Ninguna", "e2": "Ninguna: IND-01 no sustituye ni alimenta a E2"}]
    return {"estado": "comparable" if (e1["estado"] == "calculable" and e2["estado"] == "calculable") else "parcial",
            "filas": filas, "montos": {"E1": monto(e1), "E2": monto(e2)},
            "no_sumar": ("Los montos de E1 y E2 no se suman ni se presentan como alternativas equivalentes: son ilustrativos, parten de supuestos "
                         "distintos y no se ha verificado que no se solapen."),
            "diferencias_metodologicas": ["E1 parte de un monto observado en negados; E2 parte de una métrica agregada heredada de tráfico.",
                                          "Los dos dependen de un porcentaje heredado, no validado, y de ningún modo son resultados observados."],
            "conclusiones_confiables": ["Los datos de entrada observados (con su fuente) y las proporciones calculadas directamente sobre ellos."],
            "conclusiones_requieren_validacion": [f"Cualquier monto «recuperable»: depende de {_dep(e1, e2)}, heredados y no validados."]}


# ------------------------------------------------------------------------------------------------ IND-01
def _causas_mayor_100(clave_fuente, num, carritos, unidad_texto, unidad_declarada, canal, n_canales) -> list[dict]:
    """Por qué puede aparecer una relación > 100 %: cada causa posible con lo que SÍ se puede comprobar. No afirma una causa."""
    def c(causa, estado, detalle):
        return {"causa": causa, "estado": estado, "detalle": detalle}
    out = [
        c("Fuentes distintas", "concurre" if clave_fuente == "sistema_ventas" else "no_concurre",
          "Los pedidos vienen del sistema de ventas y los carritos de GA4: sistemas distintos." if clave_fuente == "sistema_ventas"
          else "Numerador y denominador vienen de GA4."),
        c("Periodos distintos", "concurre" if num.periodo != carritos.periodo else "no_concurre",
          f"Numerador {num.periodo}; carritos {carritos.periodo}." ),
        c("Granularidades distintas", "concurre" if num.granularidad != carritos.granularidad else "no_concurre",
          f"Numerador {num.granularidad}; carritos {carritos.granularidad}."),
        c("Unidades distintas (eventos, sesiones, usuarios, pedidos)", "no_verificable" if not unidad_declarada else "concurre",
          "La unidad de los carritos no está declarada: no se puede comprobar si equivale a la del numerador." if not unidad_declarada
          else f"Los carritos se cuentan en «{unidad_texto}» y el numerador son pedidos o compras: no son la misma unidad."),
        c("Universos o filtros distintos", ("concurre" if (canal or n_canales > 1) and clave_fuente == "sistema_ventas" else "no_verificable"),
          (f"Las ventas se filtraron por canal «{canal}» pero el tráfico GA4 no tiene ese filtro." if canal else
           f"Las ventas incluyen {n_canales} canales y el tráfico GA4 es de nivel sitio." if n_canales > 1 and clave_fuente == "sistema_ventas"
           else "El libro no declara el universo del tráfico.")),
        c("Duplicados", "no_verificable", "En el sistema de ventas el conteo usa id_pedido distintos; en GA4 el libro agregado no permite detectar eventos duplicados."),
        c("Atribución", "no_verificable", "El libro no informa cómo GA4 atribuye las compras ni los carritos."),
        c("Ventana temporal de maduración", "no_verificable", "Un carrito agregado en un mes puede comprarse en otro; el libro agregado no lo distingue.")]
    return out


def anomalia_matematica(num, den) -> list[str]:
    """Inconsistencias ARITMÉTICAS (distintas de una limitación metodológica): valores que ningún conteo puede tener."""
    p = []
    if num is not None and num < 0:
        p.append("el numerador es negativo")
    if den is not None and den < 0:
        p.append("el denominador es negativo")
    if den is not None and den == 0:
        p.append("el denominador es cero")
    return p


def ind01(ctx, unidad: str = "glp1") -> dict:
    """IND-01 «Relación pedidos/carritos» con las dos fuentes de pedidos como resultados INDEPENDIENTES. `ctx=None` = libro no crudo."""
    from .validator import motor, operandos, rel_pedidos_carritos as rpc
    base = {"id": "IND-01", "nombre": "Relación pedidos/carritos",
            "formula": "Relación = (Pedidos realizados ÷ Carritos agregados) × 100   (F-01 con pedidos del sistema de ventas; F-02 con compras GA4)",
            "naturaleza": "Relación entre volúmenes agregados del mismo periodo. No es una tasa de abandono ni una conversión individual; no se calcula su complemento.",
            "estado_validacion": "No validado con datos reales"}
    if unidad != "glp1":
        return base | {"estado": "no_aplica", "resultados": [], "fuentes_pedidos": None, "unidad_carritos": None, "motivo": SIN_TRAFICO + ".", "faltante": []}
    if ctx is None:
        return base | {"estado": "no_calculable", "resultados": [], "fuentes_pedidos": None, "unidad_carritos": None,
                       "motivo": "El libro no es de datos crudos (ventas por pedido y tráfico): IND-01 no se calcula.",
                       "faltante": [{"archivo": "ventas / trafico", "columna": "libro de datos crudos", "granularidad": "libro"}]}
    if ctx.unidad != "GLP1":
        return base | {"estado": "no_aplica", "resultados": [], "fuentes_pedidos": None, "unidad_carritos": None, "motivo": SIN_TRAFICO + ".", "faltante": []}
    if not operandos.tiene_trafico(ctx):                    # GLP-1 SÍ debe traer `trafico` (§8.2): su ausencia es un faltante, no una inaplicabilidad
        return base | {"estado": "no_calculable", "resultados": [], "fuentes_pedidos": None, "unidad_carritos": None,
                       "motivo": "Falta la hoja `trafico` (columnas add_to_cart y compras) que IND-01 necesita en GLP-1: no se calcula ni se sustituye.",
                       "faltante": [{"archivo": "trafico", "columna": "add_to_cart / compras", "granularidad": "mes"}]}
    d = motor.catalogo()["R-COBERTURA-ATC"]
    resultados = rpc.calcular(ctx, d)
    unidad_texto, lim_unidad = rpc.etiqueta_unidad(d.p("unidad_carritos"))
    declarada = lim_unidad is None
    canal = d.p("filtro_canal_relacion")
    canales = {ln.valores.get("canal", "") for ln in ctx.lineas_periodo() if ln.valores.get("canal", "")}
    carritos = operandos.carritos_agregados(ctx)
    items = []
    for r in resultados:
        ev = r.evidencia
        clave = ev.get("fuente_pedidos")
        f = rpc.FUENTES.get(clave, {})
        num_op = operandos.pedidos_ventas(ctx, canal) if clave == "sistema_ventas" else operandos.compras_ga4(ctx)
        it = {"codigo": r.codigo, "nombre": ev.get("nombre", f.get("nombre")), "fuente_pedidos": clave, "fuente": f.get("fuente"),
              "estado": "no_calculable", "relacion": None, "mayor_100": None, "interpretacion": None, "limitaciones": [], "faltante": [],
              "numerador": {"nombre": f.get("numerador_texto"), "valor": _s(num_op.valor), "fuente": f.get("fuente"), "periodo": num_op.periodo,
                            "tipo": "observado" if num_op.valor is not None else "no_verificable"},
              "carritos": {"nombre": "carritos agregados (add_to_cart, nivel sitio)", "valor": _s(carritos.valor), "unidad": unidad_texto,
                           "fuente": "GA4", "periodo": carritos.periodo, "tipo": "observado" if carritos.valor is not None else "no_verificable"}}
        if r.estado == "not_verifiable" or r.valor is None:
            it |= {"estado": "no_calculable", "faltante": [dict(x) for x in r.faltante], "motivo": r.mensaje,
                   "interpretacion": "No calculable: faltan datos. No se muestra 0 % ni se toma la otra fuente de pedidos."}
        else:
            lim = list(ev.get("limitaciones", []))
            mayor = r.valor > Decimal(100)
            anom = anomalia_matematica(num_op.valor, carritos.valor)
            it |= {"estado": "calculable_con_limitacion" if lim else "calculable", "relacion": _s(r.valor), "limitaciones": lim, "mensaje": r.mensaje,
                   "relacion_tipo": "calculado",
                   "interpretacion": (f"Por cada 100 carritos agregados se registran {_n(r.valor)} {f.get('numerador_texto')} en el periodo "
                                      f"(fuente de pedidos: {f.get('fuente')}; unidad de los carritos: {unidad_texto}). No es una tasa de abandono.")}
            if mayor:
                it["mayor_100"] = {"valor_original": _s(r.valor), "aviso": AVISO_MAYOR_100,
                                   "clasificacion": "anomalia_matematica" if anom else "limitacion_metodologica",
                                   "explicacion_clasificacion": (("Inconsistencia aritmética detectada: " + "; ".join(anom)) if anom else
                                       "No hay inconsistencia aritmética (ambos volúmenes son conteos no negativos y el denominador es mayor que cero): "
                                       "es una limitación metodológica, no demostrable como error. El valor se conserva sin modificar."),
                                   "variables": {"numerador": it["numerador"], "carritos": it["carritos"]},
                                   "causas_posibles": _causas_mayor_100(clave, num_op, carritos, unidad_texto, declarada, canal, len(canales))}
        items.append(it)
    sistema = operandos.pedidos_ventas(ctx, canal)
    ga4 = operandos.compras_ga4(ctx)
    brecha = ((ga4.valor - sistema.valor) / sistema.valor) if (ga4.valor is not None and sistema.valor) else None
    fuentes = {"sistema_ventas": {"nombre": "Pedidos del sistema de ventas", "valor": _s(sistema.valor), "definicion": "id_pedido distintos con fecha_pedido en el periodo (ventas)",
                                  "fuente": "ventas", "periodo": sistema.periodo, "tipo": "observado" if sistema.valor is not None else "no_verificable"},
               "ga4_compras": {"nombre": "Compras registradas en GA4", "valor": _s(ga4.valor), "definicion": "Σ trafico.compras a nivel sitio (evento de compra de GA4)",
                               "fuente": "trafico (GA4)", "periodo": ga4.periodo, "tipo": "observado" if ga4.valor is not None else "no_verificable"},
               "brecha_relativa": _s(brecha),
               "brecha_texto": (None if brecha is None else
                                f"Las compras GA4 difieren {_n(brecha * 100)} % de los pedidos del sistema de ventas (F-03). Es información, no un error: no se concilia ni se corrige."),
               "equivalencia": "NO VALIDADA: no existe evidencia que permita afirmar que ambas fuentes cuentan las mismas transacciones.",
               "no_se_suman": "Las dos cifras no se suman, no se promedian, no se sustituyen entre sí y no se usan indistintamente en fórmulas.",
               "diferencias_documentadas": [
                   {"aspecto": "Conteo", "detalle": "Las dos cifras pueden diferir en cualquier periodo; la diferencia no se trata como error."},
                   {"aspecto": "Definición", "detalle": "El sistema de ventas cuenta pedidos creados (id_pedido); GA4 cuenta eventos de compra. Pedido creado ≠ compra registrada."},
                   {"aspecto": "Duplicados", "detalle": "No verificable con el libro agregado: GA4 puede registrar un evento más de una vez; el sistema de ventas se cuenta por id_pedido distinto."},
                   {"aspecto": "Atribución", "detalle": "No verificable: el libro no informa la atribución de GA4."},
                   {"aspecto": "Temporalidad", "detalle": "Se comparan por mes calendario (fecha del pedido frente al mes de tráfico); la fecha del evento y la del pedido pueden no coincidir."},
                   {"aspecto": "Limitaciones de medición", "detalle": "GA4 depende de consentimiento, bloqueadores y etiquetado; el sistema de ventas no. El libro no cuantifica esos efectos."}]}
    unidad = {"declarada": unidad_texto if declarada else "no_declarada", "texto": unidad_texto,
              "evidencia": ("El catálogo de definiciones del proyecto clasifica `add_to_cart` como métrica de eventos de analítica (un evento no es una persona, "
                            "una sesión ni un carrito individual), definición no validada con datos reales. La unidad con la que la fuente reporta los carritos "
                            "agregados no está declarada en los libros ni en la configuración y los datos no permiten comprobarla. El contrato de datos define "
                            "`visitas` como sesiones."),
              "estado": "DECLARADA" if declarada else "NO VERIFICABLE",
              "advertencia": (None if declarada else "Unidad de carritos no declarada: no se asume que un evento de carrito equivalga a un carrito distinto; la interpretación es limitada."),
              "no_se_convierte": "Los eventos no se convierten automáticamente en carritos individuales."}
    estados = [i["estado"] for i in items]
    if all(e == "no_calculable" for e in estados):
        estado = "no_calculable"
    elif all(e == "calculable" for e in estados):
        estado = "calculable"
    else:
        estado = "calculable_con_limitacion"                # al menos un resultado calculable y alguna limitación o un resultado no calculable
    return base | {"estado": estado, "resultados": items, "fuentes_pedidos": fuentes, "unidad_carritos": unidad, "motivo": None, "faltante": [],
                   "periodo": ctx.etiqueta_periodo(), "universo": "nivel sitio (vista=general, sku vacío)",
                   "nota_comparabilidad": "Con la unidad de carritos sin declarar, todo resultado nace «calculable con limitación»." if not declarada else None}


# ------------------------------------------------------------------------------------------------ ensamblado
def construir(res, unidad: str, period, ctx=None) -> dict:
    """Estructura completa del panel. `res` = resultado del motor (`GlpResult`/`Result`); `ctx` = Contexto de datos crudos (o None)."""
    sup = supuestos()
    ent = _entradas(res, unidad)
    e1 = escenario_e1(ent["venta"], ent["m_neg"], sup["r"]["valor"], ent["negados_hoja"], ent["negados_sin_monto"])
    e2 = escenario_e2(unidad, ent["venta"], ent["abandonados"], ent["ticket"], sup["c"]["valor"], ent["embudo_derivado"], ent["tiene_embudo"])
    out = {"esquema": ESQUEMA, "unidad": unidad, "periodo": f"{period.year}-{period.index:02d} ({period.periodicity})",
           "leyenda": {"observado": "Dato del libro", "calculado": "Aritmética sobre datos observados", "supuesto_heredado": ETIQUETA_SUPUESTO,
                       "no_verificable": "No verificable con el libro cargado"},
           "supuestos": {k: {"valor": _s(v["valor"]), "etiqueta": v["etiqueta"], "referencia": v["referencia"], "origen": v["origen"],
                             "validacion_operacional": v["validacion_operacional"], "inconsistencia_configuracion": v["inconsistencia_configuracion"],
                             "variantes": v["variantes"]} for k, v in sup.items()},
           "escenarios": [e1, e2], "comparacion": comparar(e1, e2), "ind01": ind01(ctx, unidad),
           "pendientes_validacion": [f"r = {_n(sup['r']['valor'] * 100, 0)} % (E1) y c = {_n(sup['c']['valor'] * 100, 0)} % (E2): supuestos heredados, no validados con datos reales.",
                                     "Equivalencia entre pedidos del sistema de ventas y compras GA4: no validada.",
                                     "Unidad de los carritos agregados: no verificable con el libro.",
                                     "Reglas del motor y IND-01: no validadas con datos reales (validación sintética)."]}
    return out


_CACHE_CTX: dict = {}


def _contexto(ruta, period):
    """Lee el libro crudo UNA vez por (archivo, tamaño, fecha de modificación, periodo): el análisis se pide varias veces por reporte y la lectura
    duplicaba su costo. Solo se guardan los últimos 4; el contexto es de solo lectura (las pruebas verifican que no se muta)."""
    from pathlib import Path
    from .validator.normalizar import construir_contexto
    st = Path(ruta).stat()
    clave = (str(ruta), st.st_mtime_ns, st.st_size, period.unit, period.periodicity, period.year, period.index)
    if clave not in _CACHE_CTX:
        if len(_CACHE_CTX) >= 4:
            _CACHE_CTX.pop(next(iter(_CACHE_CTX)))
        _CACHE_CTX[clave] = construir_contexto(ruta, period)
    return _CACHE_CTX[clave]


def construir_desde_libro(res, unidad: str, period, ruta, es_libro_crudo: bool) -> dict:
    """Punto de entrada del servicio: lee el contexto de datos crudos (solo GLP-1 y solo si el libro es crudo) y arma el panel. Así el servicio no
    importa el motor de reglas (garantía T-14: el módulo expuesto a la IA no depende del motor ni lo modifica)."""
    ctx = _contexto(ruta, period) if (unidad == "glp1" and es_libro_crudo) else None
    return construir(res, unidad, period, ctx)
