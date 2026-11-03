"""Operandos y razones que el motor de reglas sabe calcular (Fase 2A). Una sola definición por cifra: las reglas
`R-CONC-COMPRAS`, `R-DENOM` y `R-COBERTURA-ATC` las reutilizan, así no se duplican fórmulas ni se contradicen.

Cada operando nombra su FUENTE ("sistema_ventas" = ventas.id_pedido; "ga4" = trafico.*) y su periodo. Un dato que no
se puede obtener es `None` (faltante), nunca cero. Las fórmulas son F-01, F-02, F-03 y F-11 de la especificación.
"""
from __future__ import annotations

from decimal import Decimal

from .motor import Operando, Razon

SISTEMA_VENTAS = "sistema_ventas"
GA4 = "ga4"


def _trafico(ctx, metrica: str) -> tuple[Decimal | None, list[str]]:
    """Suma de la métrica a nivel sitio en los meses del periodo. Si falta algún mes, no se completa: faltante."""
    y, ms = ctx.ventana()
    faltan = [f"{y}-{m:02d}" for m in sorted(ms) if ctx.trafico_sitio.get((y, m), {}).get(metrica) is None]
    if faltan:
        return None, faltan
    return sum((ctx.trafico_sitio[(y, m)][metrica] for m in ms), Decimal(0)), []


def pedidos_ventas(ctx, canal: str | None = None) -> Operando:
    """Pedidos del sistema de ventas (id_pedido distintos) del periodo; criterios idénticos a los del motor actual."""
    ids = ctx.pedidos_sistema_ventas()
    if canal:
        ids = {ln.id_pedido for ln in ctx.lineas_periodo() if ln.id_pedido in ids and ln.valores.get("canal", "") == canal}
    return Operando(Decimal(len(ids)), SISTEMA_VENTAS, ctx.etiqueta_periodo(), "mes", "ventas.id_pedido distintos")


def compras_ga4(ctx) -> Operando:
    v, faltan = _trafico(ctx, "compras")
    return Operando(v, GA4, ctx.etiqueta_periodo(), "mes", "trafico.compras (nivel sitio)" + (f"; faltan meses {faltan}" if faltan else ""))


def carritos_agregados(ctx) -> Operando:
    v, faltan = _trafico(ctx, "add_to_cart")
    return Operando(v, GA4, ctx.etiqueta_periodo(), "mes", "trafico.add_to_cart (nivel sitio)" + (f"; faltan meses {faltan}" if faltan else ""))


def monto_ventas(ctx) -> Operando:
    ids = ctx.pedidos_sistema_ventas()
    total = sum((ln.monto for ln in ctx.lineas_periodo() if ln.id_pedido in ids and ln.monto is not None), Decimal(0))
    return Operando(total, SISTEMA_VENTAS, ctx.etiqueta_periodo(), "mes", "ventas.monto_venta")


def tiene_trafico(ctx) -> bool:
    return ctx.hoja_trafico and {"add_to_cart", "compras"} <= ctx.columnas.get("trafico", set())


def razones(ctx, canal: str | None = None) -> list[Razon]:
    """Razones calculables en la unidad. En AETOPS (sin `trafico`) solo el ticket."""
    ped = pedidos_ventas(ctx, canal)
    out = [Razon("ticket", "Ticket promedio (F-11)", monto_ventas(ctx), pedidos_ventas(ctx), ((SISTEMA_VENTAS, SISTEMA_VENTAS),))]
    if ctx.unidad == "GLP1" and tiene_trafico(ctx):
        car, com = carritos_agregados(ctx), compras_ga4(ctx)
        out += [
            Razon("ind01_sistema_ventas", "Relación pedidos (sistema de ventas) / carritos agregados (F-01)", ped, car, ((SISTEMA_VENTAS, GA4),), por_cien=True),
            Razon("ind01_ga4", "Relación compras GA4 / carritos agregados (F-02)", com, car, ((GA4, GA4),), por_cien=True),
            Razon("brecha_compras", "Diferencia compras GA4 frente a pedidos del sistema de ventas (F-03)",
                  Operando(None if com.valor is None else com.valor - ped.valor, "ga4-sistema_ventas", ctx.etiqueta_periodo(), "mes", "compras GA4 − pedidos del sistema de ventas"),
                  ped, (("ga4-sistema_ventas", SISTEMA_VENTAS),), numerador_con_signo=True),
        ]
    return out
