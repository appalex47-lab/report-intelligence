"""Datos crudos SINTÉTICOS de AETOPS (ventas + catálogo + negados) según docs/CONTRATO_DATOS.md. Cifras inventadas.

    python tools/make_raw_synthetic.py --salida data/AETOPS_crudo_sintetico.xlsx [--hasta 2026-9] [--meses 14] [--defectos]
"""
from __future__ import annotations

import argparse
import datetime as dt
import random
import sys
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

LINEAS = ["AE-A", "AE-A", "AE-A", "AE-B", "AE-B", "AE-C", "HYR"]
CATS = ["Oncología y Hematología", "Neurología", "Endocrinología", "Dermatología", "Cardiología", "Infectología"]
CANALES = ["APP FESA", "ECOMMERCE", "LLAMADAS GOOGLE", "WHATSAPP"]
ESTADOS = ["CDMX", "JALISCO", "NUEVO LEÓN", "PUEBLA", "YUCATÁN"]


def _months(until: tuple[int, int], n: int):
    y, m = until
    out = []
    for _ in range(n):
        out.append((y, m))
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    return out[::-1]


def build(path: Path, until=(2026, 9), n_months=14, defects=False, seed=7) -> Path:
    rnd = random.Random(seed)
    cat_rows = []
    for i in range(1, 41):
        cat_rows.append((f"SKU{i:03d}", f"PRODUCTO {i:02d}", rnd.choice(LINEAS), CATS[i % len(CATS)]))
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "ventas"
    ws.append(["fecha_pedido", "id_pedido", "id_paciente", "paciente_nuevo", "sku", "canal", "estado", "sucursal",
               "piezas", "monto_venta"])
    seen_pat: set = set()
    order = 0
    for (y, m) in _months(until, n_months):
        growth = 1 + 0.02 * ((y - 2025) * 12 + m)
        for _ in range(int(400 * growth)):
            order += 1
            pat = f"P{rnd.randint(1, 1800):05d}"
            new = "NO" if pat in seen_pat else "SI"
            seen_pat.add(pat)
            day = rnd.randint(1, 28)
            canal = rnd.choices(CANALES, weights=[3, 4, 2, 1])[0]
            for sku, _p, _lin, _c in rnd.sample(cat_rows, rnd.choice([1, 1, 2, 3])):
                pcs = rnd.randint(1, 4)
                ws.append([dt.date(y, m, day), f"O{order:06d}", pat, new, sku, canal, rnd.choice(ESTADOS), f"S{rnd.randint(1, 9)}",
                           pcs, round(pcs * rnd.uniform(180, 2400), 2)])
    cs = wb.create_sheet("catalogo")
    cs.append(["sku", "producto", "linea", "categoria", "laboratorio"])
    for r in cat_rows:
        cs.append([*r, "LAB X"])
    ns = wb.create_sheet("negados")
    ns.append(["producto", "sku", "alta", "pedidos", "cantidad_negada", "monto_negado"])
    for sku, prod, lin, _c in rnd.sample(cat_rows, 8):
        q = rnd.randint(1, 9)
        ns.append([prod, sku, lin, rnd.randint(1, q), q, round(q * rnd.uniform(300, 2500), 2)])
    if defects:
        ws.append([dt.date(until[0], until[1], 3), "O999990", "P99999", "SI", "SKU_NO_EXISTE", "ECOMMERCE", "CDMX", "S1", 1, 100])
        ws.append(["no es fecha", "O999991", "P99998", "SI", "SKU001", "ECOMMERCE", "CDMX", "S1", 1, 100])
        ws.append([dt.date(until[0], until[1], 4), "O999992", "P99997", "SI", "SKU001", "ECOMMERCE", "CDMX", "S1", -1, -100])
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path


def blank(path: Path) -> Path:
    """Plantilla vacía del contrato (solo encabezados) para quien hace la extracción."""
    wb = openpyxl.Workbook()
    wb.active.title = "ventas"
    wb.active.append(["fecha_pedido", "id_pedido", "id_paciente", "paciente_nuevo", "sku", "canal", "estado", "sucursal", "piezas", "monto_venta"])
    wb.create_sheet("catalogo").append(["sku", "producto", "linea", "categoria", "laboratorio"])
    wb.create_sheet("negados").append(["producto", "sku", "alta", "pedidos", "cantidad_negada", "monto_negado"])
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--salida", type=Path, default=Path("data/AETOPS_crudo_sintetico.xlsx"))
    ap.add_argument("--hasta", default="2026-9")
    ap.add_argument("--meses", type=int, default=14)
    ap.add_argument("--defectos", action="store_true")
    ap.add_argument("--plantilla", action="store_true", help="solo encabezados, sin datos")
    a = ap.parse_args()
    if a.plantilla:
        print(blank(a.salida))
        raise SystemExit
    y, m = a.hasta.split("-")
    print(build(a.salida, (int(y), int(m)), a.meses, a.defectos))
