"""Datos crudos SINTÉTICOS de GLP-1 (ventas + catálogo + tráfico + negados) según docs/CONTRATO_DATOS.md. Cifras inventadas.

    python tools/make_raw_glp1_synthetic.py --salida data/GLP1_crudo_sintetico.xlsx [--hasta 2026-9] [--meses 14]
"""
from __future__ import annotations

import argparse
import datetime as dt
import random
from pathlib import Path

import openpyxl

PRODUCTOS = {"Mounjaro": ["GLP001", "GLP002"], "Wegovy": ["GLP003", "GLP004"], "Ozempic": ["GLP005"], "Saxenda": ["GLP006"]}
REGIONES = {"CDMX": "CENTRO", "EDOMEX": "CENTRO", "JALISCO": "OCCIDENTE", "NUEVO LEÓN": "NORTE", "YUCATÁN": "SURESTE"}
PAGOS = ["Tarjeta", "Transferencia", "Efectivo"]
ENTREGAS = ["Domicilio", "Sucursal"]
PROGRAMAS = ["Lealtad Plus", "Lealtad Base", ""]
EDADES = ["18-24", "25-34", "35-44", "45-54", "55+"]
SEXOS = ["Femenino", "Masculino"]
DISP = ["mobile", "desktop", "tablet"]
FUENTES = ["Organic Search", "Direct", "Paid Search", "Social", "Email"]
ESTADOS = list(REGIONES)


def _months(until, n):
    y, m = until
    out = []
    for _ in range(n):
        out.append((y, m))
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    return out[::-1]


def build(path: Path, until=(2026, 9), n_months=14, seed=11) -> Path:
    rnd = random.Random(seed)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "ventas"
    ws.append(["fecha_pedido", "id_pedido", "id_paciente", "paciente_nuevo", "sku", "canal", "estado", "region", "piezas", "monto_venta",
               "forma_pago", "modo_entrega", "programa_lealtad"])
    cat = wb.create_sheet("catalogo")
    cat.append(["sku", "producto", "categoria"])
    for p, skus in PRODUCTOS.items():
        for s in skus:
            cat.append([s, p, "GLP-1"])
    allsku = [s for v in PRODUCTOS.values() for s in v]
    seen, order = set(), 0
    for (y, m) in _months(until, n_months):
        growth = 1 + 0.03 * ((y - 2025) * 12 + m)
        for _ in range(int(300 * growth)):
            order += 1
            pat = f"P{rnd.randint(1, 1500):05d}"
            new = "NO" if pat in seen else "SI"
            seen.add(pat)
            est = rnd.choice(ESTADOS)
            row = [est, REGIONES[est], rnd.choice(PAGOS), rnd.choice(ENTREGAS), rnd.choice(PROGRAMAS)]
            for sku in rnd.sample(allsku, rnd.choice([1, 1, 2])):
                pcs = rnd.randint(1, 3)
                ws.append([dt.date(y, m, rnd.randint(1, 28)), f"G{order:06d}", pat, new, sku, "ECOMMERCE", row[0], row[1],
                           pcs, round(pcs * rnd.uniform(2500, 4800), 2), row[2], row[3], row[4]])
    ts = wb.create_sheet("trafico")
    hdr = ["mes", "vista", "valor", "sku", "visitas", "usuarios", "usuarios_nuevos", "usuarios_recurrentes", "vistas_producto",
           "add_to_cart", "begin_checkout", "compras", "carritos_abandonados", "sesiones_rebote", "segundos_interaccion_total"]
    ts.append(hdr)

    def row(mes, vista, valor, sku, base):
        v = int(base * rnd.uniform(0.8, 1.2))
        u = int(v * 0.85)
        n = int(u * 0.3)
        atc = int(v * 0.1)
        ts.append([mes, vista, valor, sku, v, u, n, u - n, int(v * 0.7), atc, int(atc * 0.6), int(atc * 0.3), atc - int(atc * 0.3),
                   int(v * 0.04), v * rnd.randint(70, 140)])
    for (y, m) in _months(until, n_months):
        mes = dt.date(y, m, 1)
        g = 1 + 0.03 * ((y - 2025) * 12 + m)
        row(mes, "general", "", "", 20000 * g)
        for vista, vals in (("edad", EDADES), ("sexo", SEXOS), ("dispositivo", DISP), ("fuente", FUENTES), ("estado", ESTADOS)):
            for v in vals:
                row(mes, vista, v, "", 20000 * g / len(vals))
        for sku in allsku:
            for v in EDADES:
                row(mes, "edad", v, sku, 1500 * g)
            for v in SEXOS:
                row(mes, "sexo", v, sku, 2500 * g)
    ns = wb.create_sheet("negados")
    ns.append(["producto", "sku", "alta", "pedidos", "cantidad_negada", "monto_negado"])
    for sku in rnd.sample(allsku, 3):
        q = rnd.randint(2, 9)
        ns.append([sku_name(sku), sku, "", rnd.randint(1, q), q, round(q * 3200, 2)])
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path


def sku_name(sku):
    return next(p for p, v in PRODUCTOS.items() if sku in v) + f" {sku}"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--salida", type=Path, default=Path("data/GLP1_crudo_sintetico.xlsx"))
    ap.add_argument("--hasta", default="2026-9")
    ap.add_argument("--meses", type=int, default=14)
    a = ap.parse_args()
    y, m = a.hasta.split("-")
    print(build(a.salida, (int(y), int(m)), a.meses))
