"""IND-01 «Relación pedidos/carritos» (metodología agregada; spec §8.2, fórmulas F-01 y F-02).

    Relación pedidos/carritos = (pedidos / carritos agregados) × 100        [pedidos: sistema de ventas O compras GA4]

Es una relación entre VOLÚMENES AGREGADOS a nivel sitio. No es una tasa de abandono, no se calcula su complemento, no usa
identificadores de carrito/transacción/sesión y nunca combina las dos fuentes de pedidos: si se calculan ambas, son dos
resultados independientes e identificados. Un resultado superior a 100 % se conserva, con una advertencia que no afirma causa.
"""
from __future__ import annotations

from decimal import Decimal

from . import operandos
from .motor import Definicion, Razon, Resultado, evaluar_razon

FUENTES = {
    "sistema_ventas": {"nombre": "Relación pedidos (sistema de ventas) / carritos agregados", "numerador_texto": "pedidos del sistema de ventas",
                       "fuente": "sistema de ventas", "pares": ((operandos.SISTEMA_VENTAS, operandos.GA4),)},
    "ga4_compras": {"nombre": "Relación compras GA4 / carritos agregados", "numerador_texto": "compras GA4",
                    "fuente": "GA4", "pares": ((operandos.GA4, operandos.GA4),)},
}


def etiqueta_unidad(valor) -> tuple[str, str | None]:
    """(texto de la unidad, limitación). Sin declaración válida: «unidad no declarada»."""
    if valor in (None, "no_declarada"):
        return "unidad no declarada", "unidad de los carritos no declarada: la interpretación es limitada"
    if valor in ("eventos", "sesiones"):
        return valor, None
    if isinstance(valor, str) and valor.startswith("otra:") and valor[5:].strip():
        return valor[5:].strip(), None
    return "unidad no declarada", f"valor de unidad_carritos no reconocido ({valor!r}): se trata como unidad no declarada"


def _op(o) -> dict:
    return {"valor": o.valor, "fuente": o.fuente, "periodo": o.periodo, "granularidad": o.granularidad, "nombre": o.nombre}


def calcular(ctx, d: Definicion) -> list[Resultado]:
    elegida = d.p("fuente_pedidos")
    if elegida not in (None, *FUENTES):
        return [d.resultado("configuracion_invalida", "error", configurado=repr(elegida), evidencia={"fuente_pedidos": elegida})]
    unidad, lim_unidad = etiqueta_unidad(d.p("unidad_carritos"))
    canal = d.p("filtro_canal_relacion")
    carritos = operandos.carritos_agregados(ctx)
    canales = {ln.valores.get("canal", "") for ln in ctx.lineas_periodo() if ln.valores.get("canal", "")}
    out: list[Resultado] = []
    for clave_f in ([elegida] if elegida else list(FUENTES)):
        f = FUENTES[clave_f]
        num = operandos.pedidos_ventas(ctx, canal) if clave_f == "sistema_ventas" else operandos.compras_ga4(ctx)
        ev = evaluar_razon(Razon(f"ind01_{clave_f}", f["nombre"], num, carritos, f["pares"], por_cien=True))
        base = {"nombre": f["nombre"], "fuente_pedidos": clave_f, "numerador": _op(num), "carritos_agregados": _op(carritos) | {"unidad": unidad},
                "periodo": ctx.etiqueta_periodo(), "universo": "nivel sitio (vista=general, sku vacío); ventas " + (f"filtradas por canal={canal}" if canal else "sin filtro de canal"),
                "naturaleza": "relación entre volúmenes agregados; no es tasa de abandono; no se calcula su complemento"}
        cod = f"relacion_pedidos_carritos_{clave_f}"
        if ev.estado in ("not_verifiable", "error") or ev.valor is None:
            motivo = "; ".join(ev.problemas) or "datos insuficientes"
            falta = ev.faltante or ({"archivo": "trafico", "columna": "add_to_cart / compras", "granularidad": "mes"},)
            out.append(d.resultado(cod, "not_verifiable", clave="relacion_pedidos_carritos.not_verifiable", nombre=f["nombre"], motivo=motivo,
                                   faltante=falta, evidencia=base | {"problemas": list(ev.problemas)}))
            continue
        lim = list(ev.problemas)
        if lim_unidad:
            lim.insert(0, lim_unidad)
        if not canal and len(canales) > 1:
            lim.append(f"las ventas incluyen {len(canales)} canales sin filtro: puede no ser directamente comparable")
        mayor = ev.valor > Decimal(100)
        if mayor:
            lim.append("la relación supera 100 %")
        rel = f"{ev.valor:,.2f}"
        kw = dict(nombre=f["nombre"], relacion=rel, unidad=unidad, numerador_texto=f["numerador_texto"], fuente=f["fuente"],
                  limitaciones="; ".join(lim) or "ninguna")
        evid = base | {"relacion": str(ev.valor), "limitaciones": lim, "estado_ind01": "calculable" if not lim else "calculable_con_limitacion"}
        if mayor:
            out.append(d.resultado(cod, "warning", clave="relacion_pedidos_carritos.warning_mayor_100", valor=ev.valor, evidencia=evid, **kw))
        elif lim:
            out.append(d.resultado(cod, "warning", clave="relacion_pedidos_carritos.warning", valor=ev.valor, evidencia=evid, **kw))
        else:
            out.append(d.resultado(cod, "valid", clave="relacion_pedidos_carritos.valid", valor=ev.valor, evidencia=evid, **kw))
    return out
