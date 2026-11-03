"""Reglas que comparan las dos fuentes de pedidos con el tráfico: R-CONC-COMPRAS y R-COBERTURA-ATC (Fase 2A; spec §3.3, §8.2).

Solo GLP-1 (AETOPS no tiene hoja `trafico`: el motor devuelve «No aplica»). Las fuentes nunca se sustituyen ni se suman.
"""
from __future__ import annotations

from decimal import Decimal

from . import operandos, rel_pedidos_carritos
from .motor import Definicion, Operando, Razon, Resultado, evaluar_razon, regla


@regla("R-CONC-COMPRAS")
def r_conc_compras(ctx, d: Definicion) -> list[Resultado]:
    ped, com = operandos.pedidos_ventas(ctx), operandos.compras_ga4(ctx)
    umbral = d.p("umbral_conciliacion_compras")
    if umbral is None:
        return [d.resultado("conciliacion_compras", "not_verifiable", clave="conciliacion_compras.not_verifiable", motivo="`umbral_conciliacion_compras` no está configurado",
                            faltante=({"archivo": "reglas.json", "columna": "umbral_conciliacion_compras", "granularidad": None},))]
    op = lambda o: {"valor": o.valor, "fuente": o.fuente, "periodo": o.periodo, "nombre": o.nombre}      # noqa: E731
    dif = None if (com.valor is None or ped.valor is None) else com.valor - ped.valor
    ev = evaluar_razon(Razon("brecha_compras", "brecha", Operando(dif, "ga4-sistema_ventas", ped.periodo, "mes", "compras GA4 − pedidos"), ped,
                             (("ga4-sistema_ventas", operandos.SISTEMA_VENTAS),), numerador_con_signo=True))
    base = {"pedidos_sistema_ventas": op(ped), "compras_ga4": op(com), "periodo": ped.periodo,
            "alcance": "nivel sitio; ventas sin filtro de canal", "regla": "las fuentes no se sustituyen, no se suman y no son equivalentes"}
    if ev.valor is None:
        return [d.resultado("conciliacion_compras", "not_verifiable", clave="conciliacion_compras.not_verifiable", motivo="; ".join(ev.problemas),
                            faltante=ev.faltante or ({"archivo": "trafico", "columna": "compras", "granularidad": "mes"},), evidencia=base | {"problemas": list(ev.problemas)})]
    brecha = ev.valor
    fmt = lambda x: f"{x * 100:+,.2f} %"          # noqa: E731
    kw = dict(pedidos=f"{ped.valor:,.0f}", compras=f"{com.valor:,.0f}", brecha=fmt(brecha), umbral=f"{Decimal(str(umbral)) * 100:,.0f} %")
    evid = base | {"brecha": str(brecha), "umbral": str(umbral), "aviso_heredado": "TRAFICO_PURCHASE_DIFFERS (raw/glp1.py): se emite si |brecha| > umbral; no se modifica",
                   "hipotesis_a_validar": d["hipotesis"]}
    if abs(brecha) > Decimal(str(umbral)):
        return [d.resultado("conciliacion_compras", "warning", valor=brecha, evidencia=evid, hipotesis=", ".join(d["hipotesis"]), **kw)]
    return [d.resultado("conciliacion_compras", "valid", valor=brecha, evidencia=evid, **kw)]


@regla("R-COBERTURA-ATC")
def r_cobertura_atc(ctx, d: Definicion) -> list[Resultado]:
    return rel_pedidos_carritos.calcular(ctx, d)
