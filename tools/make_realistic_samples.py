"""Archivos de EJEMPLO que imitan datos reales (cifras inventadas pero con la escala, mezcla y estacionalidad típicas).

    python tools/make_realistic_samples.py --salida data/ejemplos/ [--hasta 2026-9]

Genera, según docs/CONTRATO_DATOS.md:
  AETOPS_crudo_ejemplo.xlsx   (ventas + catalogo + negados; 15 meses)
  GLP1_crudo_ejemplo.xlsx     (ventas + catalogo + trafico + negados; 15 meses)
  *_con_defectos.xlsx         (los mismos formatos con errores típicos, para probar las validaciones)
"""
from __future__ import annotations

import argparse
import datetime as dt
import math
import random
import sys
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# ------------------------------------------------------------------------------ AETOPS
AE_PRODUCTS = [  # (nombre, línea, categoría, precio de lista aprox., peso de ventas)
    ("LEUPRORELINA 22.5 MG SUSP INY C/1", "AE-A", "Oncología y Hematología", 8200, 9), ("DENOSUMAB 60 MG SOL INY JER PRECARGADA", "AE-A", "Ortopedia , Reumatología", 6900, 8),
    ("GOSERELINA 10.8 MG IMPLANTE C/1", "AE-A", "Oncología y Hematología", 9800, 7), ("BEVACIZUMAB 400 MG SOL INY FA 16 ML", "AE-A", "Oncología y Hematología", 21500, 5),
    ("TRASTUZUMAB 440 MG SOL INY FA", "AE-A", "Oncología y Hematología", 24800, 4), ("RITUXIMAB 500 MG SOL INY FA 50 ML", "AE-A", "Oncología y Hematología", 17600, 4),
    ("ENZALUTAMIDA 40 MG CAP C/112", "AE-A", "Oncología y Hematología", 38000, 3), ("ABIRATERONA 250 MG TAB C/120", "AE-A", "Oncología y Hematología", 14300, 4),
    ("LENALIDOMIDA 25 MG CAP C/21", "AE-A", "Oncología y Hematología", 32500, 3), ("PALBOCICLIB 125 MG CAP C/21", "AE-A", "Oncología y Hematología", 41000, 2),
    ("FULVESTRANT 250 MG SOL INY JER C/2", "AE-A", "Oncología y Hematología", 11900, 4), ("BORTEZOMIB 3.5 MG POLVO INY FA", "AE-A", "Oncología y Hematología", 8700, 3),
    ("ADALIMUMAB 40 MG SOL INY PLUMA C/2", "AE-B", "Inmunología", 15800, 6), ("ETANERCEPT 50 MG SOL INY PLUMA C/4", "AE-B", "Ortopedia , Reumatología", 17900, 4),
    ("TOCILIZUMAB 162 MG SOL INY JER", "AE-B", "Ortopedia , Reumatología", 12300, 3), ("SECUKINUMAB 150 MG SOL INY PLUMA C/2", "AE-B", "Dermatología", 18700, 3),
    ("USTEKINUMAB 45 MG SOL INY JER", "AE-B", "Dermatología", 16900, 3), ("VEDOLIZUMAB 300 MG POLVO INY FA", "AE-B", "Gastroenterología", 19500, 2),
    ("OCRELIZUMAB 300 MG SOL INY FA", "AE-B", "Neurología", 52000, 2), ("FINGOLIMOD 0.5 MG CAP C/28", "AE-B", "Neurología", 14500, 3),
    ("INSULINA GLARGINA 100 UI/ML PLUMA C/5", "AE-C", "Endocrinología", 2100, 5), ("SEMAGLUTIDA 1 MG SOL INY PLUMA", "AE-C", "Endocrinología", 3800, 3),
    ("EMPAGLIFLOZINA 25 MG TAB C/30", "AE-C", "Endocrinología", 1650, 4), ("SACUBITRILO/VALSARTAN 200 MG TAB C/28", "AE-C", "Cardiología", 1900, 3),
    ("EVOLOCUMAB 140 MG SOL INY PLUMA C/2", "AE-C", "Cardiología", 9400, 2), ("DOLUTEGRAVIR 50 MG TAB C/30", "HYR", "Infectología", 4100, 2),
    ("SOFOSBUVIR/VELPATASVIR 400/100 MG TAB C/28", "HYR", "Infectología", 24000, 1), ("PALIVIZUMAB 100 MG SOL INY FA", "HYR", "Infectología", 17400, 1),
]
AE_PRICE = 0.30        # calibra el ticket a ~$8 K y la venta mensual a ~$11-12 M (escala de los reportes)
AE_CANALES = [("ECOMMERCE", 0.38), ("APP FESA", 0.27), ("LLAMADAS GOOGLE", 0.22), ("WHATSAPP", 0.13)]
ESTADOS = ["CIUDAD DE MÉXICO", "JALISCO", "NUEVO LEÓN", "ESTADO DE MÉXICO", "PUEBLA", "QUERÉTARO", "GUANAJUATO", "VERACRUZ", "CHIHUAHUA", "BAJA CALIFORNIA", "YUCATÁN"]
EST_W = [20, 11, 10, 10, 5, 4, 4, 4, 3, 3, 3]


def _distinct(rnd, items, weights, k):
    """k elementos distintos, ponderados (un SKU no se repite dentro de un pedido)."""
    out, pool, w = [], list(items), list(weights)
    for _ in range(k):
        i = rnd.choices(range(len(pool)), w)[0]
        out.append(pool.pop(i))
        w.pop(i)
    return out


def months_back(until: tuple[int, int], n: int):
    y, m = until
    out = []
    for _ in range(n):
        out.append((y, m))
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    return out[::-1]


def season(m: int) -> float:
    return 1 + 0.06 * math.cos((m - 11) / 12 * 2 * math.pi)       # picos en nov-dic, valle a mitad de año


def build_aetops(path: Path, until=(2026, 9), n_months=15, defects=False, seed=2026, orders_base=900, growth_yoy=0.55) -> Path:
    rnd = random.Random(seed)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "ventas"
    ws.append(["fecha_pedido", "id_pedido", "id_paciente", "paciente_nuevo", "sku", "canal", "estado", "sucursal", "piezas", "monto_venta"])
    cat = wb.create_sheet("catalogo")
    cat.append(["sku", "producto", "linea", "categoria", "laboratorio"])
    skus = []
    for i, (name, lin, ctg, price, w) in enumerate(AE_PRODUCTS, 1):
        sku = str(20000 + i * 613 + rnd.randint(0, 99))       # Sivec numérico de 5 dígitos, como en los reportes
        skus.append((sku, name, lin, ctg, price, w))
        cat.append([sku, name, lin, ctg, rnd.choice(["ROCHE", "NOVARTIS", "PFIZER", "AMGEN", "LILLY", "MSD", "GSK", "SANOFI"])])
    weights = [s[5] for s in skus]
    patients = [f"PX{n:06d}" for n in range(1, 4200)]
    seen: set[str] = set()
    order = 0
    for (y, m) in months_back(until, n_months):
        t = (y - 2025) * 12 + m
        scale = (1 + growth_yoy / 12 * (t - 9)) * season(m)           # crecimiento anual compuesto aproximado
        n_orders = max(int(orders_base * max(scale, 0.25)), 60)
        for _ in range(n_orders):
            order += 1
            pat = rnd.choice(patients) if rnd.random() < 0.55 else patients[min(int(rnd.paretovariate(1.2)) * 90 + rnd.randint(0, 90), len(patients) - 1)]
            new = "NO" if pat in seen else "SI"
            seen.add(pat)
            canal = rnd.choices([c for c, _ in AE_CANALES], [w for _, w in AE_CANALES])[0]
            est = rnd.choices(ESTADOS, EST_W)[0]
            day = min(max(int(rnd.gauss(14, 8)), 1), 28)
            for sku, name, lin, ctg, price, _w in _distinct(rnd, skus, weights, 2 if rnd.random() < 0.35 else 1):
                pcs = rnd.choices([1, 2, 3, 4], [70, 18, 8, 4])[0]
                ws.append([dt.date(y, m, day), f"A{y % 100}{m:02d}-{order:06d}", pat, new, sku, canal, est, f"SUC-{rnd.randint(1, 14):02d}", pcs,
                           round(pcs * price * AE_PRICE * rnd.uniform(0.9, 1.04), 2)])
    ns = wb.create_sheet("negados")
    ns.append(["producto", "sku", "alta", "pedidos", "cantidad_negada", "monto_negado"])
    for sku, name, lin, ctg, price, w in rnd.sample(skus, 14):
        q = max(int(rnd.paretovariate(1.4) * 3), 1)
        ns.append([name, sku, lin, max(1, int(q * rnd.uniform(0.5, 1))), q, round(q * price * AE_PRICE * rnd.uniform(0.9, 1.0), 2)])
    if defects:
        d = dt.date(until[0], until[1], 5)
        ws.append([d, "A-BAD-1", "PX999991", "SI", "99999", "ECOMMERCE", "JALISCO", "SUC-01", 1, 8200])      # SKU fuera de catálogo
        ws.append(["05/13/26 ??", "A-BAD-2", "PX999992", "SI", skus[0][0], "ECOMMERCE", "JALISCO", "SUC-01", 1, 8200])   # fecha ilegible
        ws.append([d, "A-BAD-3", "PX999993", "SI", skus[1][0], "ECOMMERCE", "JALISCO", "SUC-01", 1, "ocho mil"])        # monto en texto
        ws.append([d, "", "PX999994", "SI", skus[2][0], "ECOMMERCE", "JALISCO", "SUC-01", 1, 9800])                    # sin id de pedido
        ws.append([d, "A-BAD-5", "PX999995", "NO", skus[3][0], "ECOMMERCE", "JALISCO", "SUC-01", -1, -21500])           # negativo
    wb.save(path)
    return path


# ------------------------------------------------------------------------------ GLP-1
GLP_SKUS = [  # (sku, producto, presentación, precio, peso)
    ("GLP-MJ-25", "Mounjaro", "MOUNJARO KWIKPEN MULTIDOSIS 2.5MG/0.6ML SOL INY PLUMA PRECARGADA C/1", 3800, 11),
    ("GLP-MJ-50", "Mounjaro", "MOUNJARO KWIKPEN MULTIDOSIS 5MG/0.6ML SOL INY PLUMA PRECARGADA C/1", 5050, 14),
    ("GLP-MJ-75", "Mounjaro", "MOUNJARO KWIKPEN MULTIDOSIS 7.5MG/0.6ML SOL INY PLUMA PRECARGADA C/1", 6870, 9),
    ("GLP-MJ-100", "Mounjaro", "MOUNJARO KWIKPEN MULTIDOSIS 10MG/0.6ML SOL INY PLUMA PRECARGADA C/1", 6680, 12),
    ("GLP-MJ-150", "Mounjaro", "MOUNJARO KWIKPEN MULTIDOSIS 15MG/0.6ML SOL INY PLUMA PRECARGADA C/1", 9160, 4),
    ("GLP-WG-24", "Wegovy", "WEGOVY 2.4MG/DOSIS_SEMAGLUTIDA___1_SOL_3 ml", 5280, 6), ("GLP-WG-05", "Wegovy", "WEGOVY 0.5MG/DOSIS_SEMAGLUTIDA___1_SOL_1.5 ml", 3120, 4),
    ("GLP-WG-10", "Wegovy", "WEGOVY 1MG/DOSIS_SEMAGLUTIDA___1_SOL_3 ml", 4190, 3), ("GLP-WG-17", "Wegovy", "WEGOVY 1.7MG/DOSIS_SEMAGLUTIDA___1_SOL_3 ml", 4980, 3),
    ("GLP-WG-025", "Wegovy", "WEGOVY 0.25MG/DOSIS_SEMAGLUTIDA___1_SOL_1.5 ml", 2530, 2),
    ("GLP-OZ-1", "Ozempic", "OZEMPIC 1 MG SOL INY PLUMA PRECARGADA 4 ML", 3900, 2), ("GLP-OZ-05", "Ozempic", "OZEMPIC 0.5 MG SOL INY PLUMA PRECARGADA 3 ML", 3300, 1),
    ("GLP-RY-7", "Rybelsus", "RYBELSUS 7 MG TAB C/30", 2900, 2), ("GLP-RY-14", "Rybelsus", "RYBELSUS 14 MG TAB C/30", 3300, 2),
    ("GLP-SX-6", "Saxenda", "SAXENDA 6 MG/ ml PLP CAJ C/ 1 DE 3 ml", 3100, 2), ("GLP-TR-15", "Trulicity", "TRULICITY 1.5 MG SOL INY PLUMA C/4", 4400, 0.4),
]
G_REGIONES = {"CIUDAD DE MÉXICO": "CENTRO", "ESTADO DE MÉXICO": "CENTRO", "MORELOS": "CENTRO", "QUERÉTARO": "BAJÍO", "GUANAJUATO": "BAJÍO", "NUEVO LEÓN": "NORESTE",
              "COAHUILA": "NORESTE", "CHIHUAHUA": "NOROESTE", "BAJA CALIFORNIA": "NOROESTE", "YUCATÁN": "SURESTE", "VERACRUZ": "SURESTE", "JALISCO": "PACIFICO"}
G_EST_W = [24, 12, 2, 5, 5, 8, 3, 4, 4, 3, 3, 9]
PAGOS = [("Tarjeta de Credito", 81), ("Efectivo", 14), ("Pendiente por Actualizar en Seus", 3), ("Tarjeta de Debito", 1.5), ("Pago eCommerce", 0.5)]
ENTREGAS = [("A domicilio", 72), ("Recoge en sucursal", 28)]
PROGRAMAS = [("MAS CALIDAD DE VIDA", 84), ("ELILILLY ENLACE", 5), ("SIN PROGRAMA ASIGNADO", 4), ("NUEVO YO", 4), ("Nuevo Yo Domiciliacion", 2), ("COMBOS MOSTRADOR", 1)]
EDADES = [("18-24", 8), ("25-34", 30), ("35-44", 19), ("45-54", 20), ("55-64", 16), ("65+", 5)]
SEXOS = [("Femenino", 67), ("Masculino", 33)]
DISP = [("mobile", 72), ("desktop", 27), ("tablet", 1)]
FUENTES = [("google / organic", 23), ("facebook / paid_social", 23), ("google / cpc", 12), ("(not set) / cross-network", 7), ("(direct) / (none)", 5), ("google / shopping paid", 5),
           ("(not set) / unassigned", 2), ("referral / referral", 1), ("instagram / organic_social", 1), ("chatgpt.com / ai_assistant", 0.5), ("google / organic_shopping", 0.3), ("mailing / email", 0.1)]


def build_glp1(path: Path, until=(2026, 9), n_months=15, defects=False, seed=11, orders_base=2150) -> Path:
    rnd = random.Random(seed)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "ventas"
    ws.append(["fecha_pedido", "id_pedido", "id_paciente", "paciente_nuevo", "sku", "canal", "estado", "region", "piezas", "monto_venta", "forma_pago", "modo_entrega",
               "programa_lealtad"])
    cat = wb.create_sheet("catalogo")
    cat.append(["sku", "producto", "categoria"])
    for sku, prod, pres, price, w in GLP_SKUS:
        cat.append([sku, prod, "GLP-1"])
    weights = [g[4] for g in GLP_SKUS]
    pat_pool = [f"GP{n:06d}" for n in range(1, 9000)]
    seen: set[str] = set()
    order = 0
    months = months_back(until, n_months)
    for (y, m) in months:
        t = (y - 2025) * 12 + m
        scale = (1 + 0.012 * (t - 9)) * season(m) * (0.93 if (y, m) >= (2026, 6) else 1)   # 2026: ligera baja, como en los reportes
        for _ in range(int(orders_base * scale)):
            order += 1
            pat = rnd.choice(pat_pool[: 5200]) if rnd.random() < 0.8 else rnd.choice(pat_pool)
            new = "NO" if pat in seen else "SI"
            seen.add(pat)
            est = rnd.choices(list(G_REGIONES), G_EST_W)[0]
            pago = rnd.choices([p for p, _ in PAGOS], [w for _, w in PAGOS])[0]
            ent = rnd.choices([e for e, _ in ENTREGAS], [w for _, w in ENTREGAS])[0]
            prog = rnd.choices([p for p, _ in PROGRAMAS], [w for _, w in PROGRAMAS])[0]
            day = min(max(int(rnd.gauss(15, 8)), 1), 28)
            for sku, prod, pres, price, _w in _distinct(rnd, GLP_SKUS, weights, 2 if rnd.random() < 0.06 else 1):
                pcs = rnd.choices([1, 2, 3], [86, 12, 2])[0]
                ws.append([dt.date(y, m, day), f"G{y % 100}{m:02d}-{order:06d}", pat, new, sku, "ECOMMERCE", est, G_REGIONES[est], pcs,
                           round(pcs * price * 0.85 * rnd.uniform(0.97, 1.02), 2), pago, ent, prog])
    ts = wb.create_sheet("trafico")
    ts.append(["mes", "vista", "valor", "sku", "visitas", "usuarios", "usuarios_nuevos", "usuarios_recurrentes", "vistas_producto", "add_to_cart", "begin_checkout",
               "compras", "carritos_abandonados", "sesiones_rebote", "segundos_interaccion_total"])

    def row(mes, vista, valor, sku, base, atc_rate=0.052, general=False):
        v = max(int(base * rnd.uniform(0.9, 1.1)), 1)
        u = int(v * rnd.uniform(0.78, 0.84))
        n = int(u * rnd.uniform(0.28, 0.42))
        atc = int(v * atc_rate * rnd.uniform(0.8, 1.2))
        ini = int(atc * 0.6)
        comp = int(atc * 0.14) if general else int(atc * 0.14)
        ts.append([mes, vista, valor, sku, v, u, n, u - n, int(v * 6.5) if general else int(v * 0.6), atc, ini, comp, atc - comp,
                   int(v * rnd.uniform(0.02, 0.045)), int(v * rnd.uniform(90, 160))])
    for (y, m) in months:
        t = (y - 2025) * 12 + m
        vis = 78000 * (1 + 0.004 * (t - 9)) * (0.92 if (y, m) >= (2026, 6) else 1) * season(m)
        mes = dt.date(y, m, 1)
        row(mes, "general", "", "", vis, atc_rate=0.26, general=True)
        for vista, vals in (("edad", EDADES), ("sexo", SEXOS), ("dispositivo", DISP), ("fuente", FUENTES)):
            tot = sum(w for _, w in vals)
            for val, w in vals:
                row(mes, vista, val, "", vis * w / tot, atc_rate=0.08 if "cpc" in val else 0.052)
        etot = sum(G_EST_W)
        for st, w in zip(G_REGIONES, G_EST_W):
            row(mes, "estado", st.title(), "", vis * w / etot * 0.9)
        for prod in sorted({g[1] for g in GLP_SKUS}):
            share = {"Mounjaro": 0.62, "Wegovy": 0.17, "Ozempic": 0.04, "Rybelsus": 0.07, "Saxenda": 0.08, "Trulicity": 0.004}[prod]
            sku = next(g[0] for g in GLP_SKUS if g[1] == prod)
            for val, w in EDADES:
                row(mes, "edad", val, sku, vis * share * w / 98)
            for val, w in SEXOS:
                row(mes, "sexo", val, sku, vis * share * w / 100)
    ns = wb.create_sheet("negados")
    ns.append(["producto", "sku", "alta", "pedidos", "cantidad_negada", "monto_negado"])
    for sku, prod, pres, price, w in [GLP_SKUS[1], GLP_SKUS[0], GLP_SKUS[14], GLP_SKUS[3], GLP_SKUS[2]]:
        q = rnd.randint(8, 250)
        ns.append([pres, sku, "", int(q * 0.9), q, round(q * price * 0.55, 2)])
    if defects:
        d = dt.date(until[0], until[1], 6)
        ws.append([d, "G-BAD-1", "GP999991", "SI", "GLP-XX-99", "ECOMMERCE", "JALISCO", "PACIFICO", 1, 5000, "Efectivo", "A domicilio", "MAS CALIDAD DE VIDA"])
        ws.append(["fecha rara", "G-BAD-2", "GP999992", "SI", "GLP-MJ-50", "ECOMMERCE", "JALISCO", "PACIFICO", 1, 5000, "Efectivo", "A domicilio", ""])
        ws.append([d, "G-BAD-3", "", "NO", "GLP-MJ-50", "ECOMMERCE", "JALISCO", "PACIFICO", 1, 5000, "Efectivo", "A domicilio", ""])
    wb.save(path)
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--salida", type=Path, default=Path("data/ejemplos"))
    ap.add_argument("--hasta", default="2026-9")
    a = ap.parse_args()
    a.salida.mkdir(parents=True, exist_ok=True)
    y, m = (int(x) for x in a.hasta.split("-"))
    for fn, name, kw in ((build_aetops, "AETOPS_crudo_ejemplo", {}), (build_aetops, "AETOPS_crudo_con_defectos", {"defects": True}),
                         (build_glp1, "GLP1_crudo_ejemplo", {}), (build_glp1, "GLP1_crudo_con_defectos", {"defects": True})):
        print(fn(a.salida / f"{name}.xlsx", (y, m), **kw))


if __name__ == "__main__":
    main()
