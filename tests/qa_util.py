"""Utilidades de las pruebas de QA de la Fase 2B: contextos sintéticos y lectura de resultados. Solo datos inventados."""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from backend.app.models import Period
from backend.app.validator import motor
from backend.app.validator.normalizar import Contexto, Linea

D = Decimal
COLS_V = {"fecha_pedido", "id_pedido", "id_paciente", "paciente_nuevo", "sku", "canal", "estado", "piezas", "monto_venta"}
CAT = {"S1": {"sku": "S1", "categoria": "A", "linea": "AE-A"}, "S2": {"sku": "S2", "categoria": "B", "linea": "AE-B"},
       "S3": {"sku": "S3", "categoria": "A", "linea": "AE-A"}}


def fecha(d, mes=1, anio=2026):
    return dt.date(anio, mes, d) if d is not None else None


def L(i, ped, pac, f, sku="S1", canal="WEB", monto="100", **extra):
    v = {"id_pedido": ped, "id_paciente": pac, "fecha_pedido": "" if f is None else str(f), "sku": sku, "canal": canal,
         "monto_venta": monto, "piezas": "1"} | extra
    return Linea(i, ped, pac, f, sku, D(monto) if monto not in (None, "") else None, D(1), v)


def ctx_de(lineas, unidad="GLP1", mes=1, tipo="mensual", trafico=None, columnas=None, cat=None, anio=2026):
    c = Contexto(unidad, Period(unidad, tipo, anio, mes), "sintetico.xlsx")
    c.columnas = columnas if columnas is not None else {"ventas": set(COLS_V) | {"sucursal", "region"}, "catalogo": {"sku", "producto", "categoria", "linea"}}
    c.lineas, c.catalogo = lineas, CAT if cat is None else cat
    if trafico is not None:
        c.columnas["trafico"] = {"mes", "vista", "valor", "sku", "visitas", "add_to_cart", "compras"}
        c.trafico_sitio = trafico
    return c


def tr(add=1000, compras=130, mes=1, anio=2026):
    f = lambda x: None if x is None else D(x)       # noqa: E731
    return {(anio, mes): {"add_to_cart": f(add), "compras": f(compras), "visitas": D(1)}}


def pedidos_n(n, mes=1):
    return [L(i, f"P{i}", f"X{i}", fecha(2, mes)) for i in range(1, n + 1)]


def run(ctx, rid, **overrides):
    return motor.ejecutar(ctx, ids=[rid], overrides=overrides or None)


def cod(res, codigo):
    return next((r for r in res if r.codigo == codigo), None)


def codigos(res):
    return [r.codigo for r in res]
