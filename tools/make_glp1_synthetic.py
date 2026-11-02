"""Genera un libro SINTÉTICO de GLP-1 con el formato operativo real (hojas 1–9).

Todas las cifras son inventadas (semilla fija, reproducible) y NO corresponden a ventas reales.
Coherencia interna (para poder reconciliar en pruebas):
  Σ visitas Edad = Σ Sexo = Σ Dispositivo = Σ Fuentes de tráfico
  Σ Monto/Pedidos de Región = Forma de pago = Modo de entrega = Productos = Programas
  Compra (embudo) = Σ Pedidos de Región
  Ticket = Monto ÷ Pedidos, Share = Monto ÷ Total, %Δ = (act − ant) ÷ ant (con bloque anterior)

Uso:
    python tools/make_glp1_synthetic.py data/GLP1_sintetico_limpio.xlsx
    python tools/make_glp1_synthetic.py data/GLP1_sintetico_con_defectos.xlsx --defectos
"""
from __future__ import annotations

import argparse
import random
from pathlib import Path

import openpyxl
from openpyxl.styles import Font, PatternFill

SEED = 20260901
VISITS = 52_000


def split(total: int, weights: list[float]) -> list[int]:
    """Reparte `total` en enteros proporcionales a `weights` sumando exactamente `total`."""
    s = sum(weights)
    raw = [total * w / s for w in weights]
    out = [int(x) for x in raw]
    for i in sorted(range(len(raw)), key=lambda i: raw[i] - out[i], reverse=True)[: total - sum(out)]:
        out[i] += 1
    return out


def pct(a: float, b: float) -> float:
    return round((a - b) / b, 4) if b else 0.0


def build(path: Path, defects: bool = False) -> Path:
    rng = random.Random(SEED)
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    bold = Font(bold=True)

    def sheet(name):
        ws = wb.create_sheet(name)
        return ws

    def header(ws, r, c, names):
        for i, n in enumerate(names):
            cell = ws.cell(r, c + i, n)
            cell.font = bold

    def put(ws, r, c, vals):
        for i, v in enumerate(vals):
            if v is not None:
                ws.cell(r, c + i, v)

    zero = (lambda x: 0) if defects else (lambda x: x)       # defecto real: Share = 0 pegado
    reb = "& de rebote" if defects else "% de rebote"          # defecto real: encabezado con typo

    # ------------------------------------------------------------- hoja 1: demografía
    TR = ["Visitas", "Total de usuarios", "Add to Cart", "Usuarios recurrentes", "Usuarios nuevos", "Share", "% Δ"]

    def traffic_rows(visits_list):
        rows = []
        for v in visits_list:
            users = round(v * 0.85)
            rec = round(users * rng.uniform(0.55, 0.70))
            rows.append([v, users, round(v * rng.uniform(0.06, 0.10)), rec, users - rec])
        return rows

    ws = sheet("1")
    ages = ["18-24", "25-34", "35-44", "45-54", "55-64", "65+"]
    av = split(VISITS, [12, 33, 19, 17, 14, 5])
    header(ws, 1, 1, ["Edad"] + TR)
    for i, (a, row, v) in enumerate(zip(ages, traffic_rows(av), av)):
        put(ws, 2 + i, 1, [a] + row + [zero(round(v / VISITS, 4)), round(rng.uniform(-0.15, 0.12), 4)])
    sx = split(VISITS, [70, 30])
    header(ws, 10, 1, ["Sexo"] + TR)
    for i, (a, row, v) in enumerate(zip(["Mujer", "Hombre"], traffic_rows(sx), sx)):
        put(ws, 11 + i, 1, [a] + row + [zero(round(v / VISITS, 4)), round(rng.uniform(-0.15, 0.12), 4)])
    dv = split(VISITS, [72, 26, 2, 0])
    header(ws, 15, 1, ["Categoría de dispositivo"] + TR)
    for i, (a, row, v) in enumerate(zip(["mobile", "desktop", "tablet", "smart tv"], traffic_rows(dv), dv)):
        put(ws, 16 + i, 1, [a] + row + [zero(round(v / VISITS, 4)), round(rng.uniform(-0.15, 0.12), 4)])

    # ------------------------------------------------------------- hoja 2: edad × producto
    ws = sheet("2")
    prods_age = [("Mounjaro", 1, 1), ("Wegovy", 9, 1), ("Ozempic", 17, 1), ("Rybelsus", 1, 14), ("Saxenda", 9, 14)]
    for name, r0, c0 in prods_age:
        header(ws, r0, c0, [f"Edad / {name}", "Visitas", "Total de usuarios", "Add to Cart",
                            "Usuarios recurrentes", "Usuarios nuevos", reb, "% Δ"])
        base = {"Mounjaro": 9000, "Wegovy": 2200, "Ozempic": 500, "Rybelsus": 1400, "Saxenda": 1300}[name]
        for i, (a, v) in enumerate(zip(ages, split(base, [12, 33, 19, 17, 14, 5]))):
            row = traffic_rows([v])[0]
            put(ws, r0 + 1 + i, c0, [a] + row[:5] + [round(rng.uniform(0.01, 0.05), 4), round(rng.uniform(-0.2, 0.2), 4)])

    # ------------------------------------------------------------- hoja 3: producto × sexo
    ws = sheet("3")
    header(ws, 1, 1, ["Producto", "Sexo", "Visitas", "Total de usuarios", "Add to Cart", "Usuarios recurrentes",
                      "Usuarios nuevos", "Tiempo de interacción", reb, "% Δ"])
    r = 2
    for name, base in (("Mounjaro", 8000), ("Ozempic", 340), ("Rybelsus", 880), ("Saxenda", 800),
                       ("Trulicity", 15), ("Wegovy", 1670)):
        for sexo, v in zip(("Femenino", "Masculino"), split(base, [68, 32])):
            row = traffic_rows([v])[0]
            secs = rng.randint(300, 6000)
            put(ws, r, 1, [name, sexo] + row + [f"{secs // 3600:02d}:{secs % 3600 // 60:02d}:{secs % 60:02d}",
                                                round(rng.uniform(0.0, 0.05), 4), round(rng.uniform(-0.3, 0.2), 4)])
            r += 1
        r += 1                                                  # fila separadora (como en el original)

    # ------------------------------------------------------------- hoja 4: región (+ tráfico por estado)
    regions = ["CENTRO", "BAJÍO", "NORESTE", "PACIFICO", "NOROESTE", "SURESTE", "OCCIDENTE", "NORTE"]
    rw = [44, 17, 12, 9, 5, 5, 4, 4]
    TOT_PED = 2600
    ped = split(TOT_PED, rw)
    reg = []
    for p_ in ped:
        monto = round(p_ * rng.uniform(4300, 5600))
        reg.append({"ped": p_, "pie": round(p_ * 1.1), "monto": monto, "pac": round(p_ * rng.uniform(0.75, 0.9))})
    TOT_MONTO = sum(x["monto"] for x in reg)
    ws = sheet("4")
    header(ws, 1, 1, ["Región", "Pedidos", "Piezas", "Monto Venta", "Pacientes", "Ticket Promedio", "Share", "% Δ"])
    prev_regs = []
    for i, (n, x) in enumerate(zip(regions, reg)):
        d = round(rng.uniform(-0.15, 0.15), 4)
        prev = round(x["monto"] / (1 + d))
        prev_regs.append((n, prev))
        put(ws, 2 + i, 1, [n, x["ped"], x["pie"], x["monto"], x["pac"], x["monto"] / x["ped"],
                           zero(round(x["monto"] / TOT_MONTO, 4)), pct(x["monto"], prev)])
    header(ws, 1, 11, ["Región", "Monto Venta", "Share"])         # bloque derecho = periodo anterior
    TP = sum(p for _, p in prev_regs)
    for i, (n, p) in enumerate(sorted(prev_regs, key=lambda t: -t[1])):
        put(ws, 2 + i, 11, [n, p, round(p / TP, 4)])
    header(ws, 11, 1, ["Región", "Visitas", "Total de usuarios", "Add to Cart", "Usuarios recurrentes",
                       "Usuarios nuevos", "% Δ"])
    states = ["Ciudad de México", "Jalisco", "Nuevo León", "Estado de México", "Querétaro", "Guanajuato",
              "Baja California", "Veracruz"]
    for i, (n, v) in enumerate(zip(states, split(int(VISITS * 0.7), [30, 12, 11, 8, 6, 5, 4, 4]))):
        row = traffic_rows([v])[0]
        put(ws, 12 + i, 1, [n] + row[:5] + [round(rng.uniform(-0.2, 0.1), 4)])

    # ------------------------------------------------------------- hoja 5: pago, entrega, embudo
    def money_rows(names, weights, ws, r0, c0=1, ranged_delta=True):
        peds, mts = split(TOT_PED, weights), split(TOT_MONTO, weights)
        out = []
        for i, (n, p_, m) in enumerate(zip(names, peds, mts)):
            d = round(rng.uniform(-0.12, 0.1), 4)
            put(ws, r0 + i, c0, [n, p_, round(p_ * 1.1), m, round(p_ * rng.uniform(0.75, 0.9)),
                                 (m / p_) if p_ else None, zero(round(m / TOT_MONTO, 4)), d])
            out.append((n, round(m / (1 + d))))
        return out

    ws = sheet("5")
    MH = ["Pedidos", "Piezas", "Monto Venta", "Pacientes", "Ticket Promedio", "Share", "% Δ"]
    pay = ["Tarjeta de Credito", "Efectivo", "Pendiente por Actualizar", "Tarjeta de Debito", "Transferencia electrónica"]
    header(ws, 1, 1, ["Forma de Pago"] + MH)
    prev_pay = money_rows(pay, [78, 13, 5, 3, 1], ws, 2)
    header(ws, 1, 12, ["Forma de Pago", "Monto Venta", "Share"])
    tp = sum(p for _, p in prev_pay)
    for i, (n, p) in enumerate(prev_pay):
        n2 = n.replace("Credito", "Crédito").replace("Debito", "Débito") if defects else n  # defecto: ortografía
        put(ws, 2 + i, 12, [n2, p, round(p / tp, 4)])
    header(ws, 10, 1, ["Modo de Entrega"] + MH)
    money_rows(["A domicilio", "Recoge en sucursal"], [72, 28], ws, 11)
    funnel = [("Ver producto", 480_000), ("Agregar a carrito", round(480_000 * 0.043)),
              ("Iniciar compra", round(480_000 * 0.026)), ("Compra", TOT_PED),
              ("Carritos abandonados", round(480_000 * 0.037))]
    for i, (n, c) in enumerate(funnel):
        put(ws, 17 + 2 * i, 1, [n, 1 if i == 0 else round(c / 480_000, 4), None, None, c])

    # ------------------------------------------------------------- hojas 6-8: negados, productos, programas
    LH = ["Pedidos", "Piezas", "Monto Venta", "Pacientes", "Ticket Promedio", "Share", "% Δ"]

    def listing(ws, first, names, weights, total_monto, total_ped, monto_col="Monto Venta", neg=False):
        header(ws, 1, 1, [first] + [monto_col if h == "Monto Venta" else h for h in LH])
        mts, peds = split(total_monto, weights), split(total_ped, weights)
        for i, (n, m, p_) in enumerate(zip(names, mts, peds)):
            put(ws, 2 + i, 1, [n, p_, round(p_ * 1.1), m, p_ if neg else round(p_ * rng.uniform(0.75, 0.9)),
                               (m / p_) if p_ else None, zero(round(m / total_monto, 4)),
                               round(rng.uniform(-0.4, 0.3), 4)])

    neg_names = ["MOUNJARO_ Tirzepatida_5 mg", "MOUNJARO KWIKPEN MULTIDOSIS 10 mg", "SAXENDA 6 mg/ ml PLP",
                 "MOUNJARO_ Tirzepatida_2.5 mg", "RYBELSUS 3mg TAB CAJ C/30", "WEGOVY 2.4MG/DOSIS"]
    listing(sheet("6"), "Nombre del Producto", neg_names, [60, 20, 8, 6, 4, 2], 786_000, 340,
            monto_col="Monto Negado", neg=True)
    prod_names = ["MOUNJARO KWIKPEN 5MG/0.6ML", "MOUNJARO KWIKPEN 10MG/0.6ML", "MOUNJARO KWIKPEN 7.5MG/0.6ML",
                  "MOUNJARO KWIKPEN 2.5MG/0.6ML", "WEGOVY 2.4MG/DOSIS", "WEGOVY 0.5MG/DOSIS", "WEGOVY 1MG/DOSIS",
                  "MOUNJARO KWIKPEN 12.5MG/0.6ML", "WEGOVY 1.7MG/DOSIS", "OZEMPIC 1.34 mg/ml", "SAXENDA 6 mg/ml",
                  "RYBELSUS 7mg TAB CAJ C/30"]
    listing(sheet("7"), "Producto", prod_names, [23, 13, 21, 15, 9, 5, 4, 3, 3, 2, 1, 1], TOT_MONTO, TOT_PED)
    prog = ["MAS CALIDAD DE VIDA", "ELILILLY ENLACE", "NUEVO YO", "SIN PROGRAMA ASIGNADO", "COMBOS MOSTRADOR"]
    listing(sheet("8"), "Programa de Lealtad", prog, [89, 4, 2, 4, 1], TOT_MONTO, TOT_PED)

    # ------------------------------------------------------------- hoja 9: fuentes de tráfico
    ws = sheet("9")
    src = ["Organic Search", "Paid Search", "Cross-network", "Direct", "Paid Social", "Paid Shopping", "Referral",
           "Organic Shopping", "Organic Social", "Email", "Unassigned"]
    vis = split(VISITS, [36, 20, 15, 9, 6, 4, 2, 1, 1, 1, 5])
    header(ws, 1, 1, ["Categoría de dispositivo"] + TR[:5] + ["% Δ"])
    header(ws, 1, 10, ["Categoría de dispositivo"] + TR[:5])
    cur_rows = traffic_rows(vis)
    for i, (n, row) in enumerate(zip(src, cur_rows)):
        d = round(rng.uniform(-0.2, 0.15), 4)
        put(ws, 2 + i, 1, [n] + row + [d])
        put(ws, 2 + i, 10, [n] + [round(x / (1 + d)) for x in row])
    tot = [sum(r_[k] for r_ in cur_rows) for k in range(5)]
    put(ws, 2 + len(src), 1, ["Total"] + tot)                       # total como valor (no fórmula)
    header(ws, 16, 1, ["Canal"] + TR[:5])
    paid = {"Paid Search", "Paid Social", "Paid Shopping", "Cross-network"}
    for j, (lab, test) in enumerate((("Pago", True), ("Organico", False))):
        sums = [sum(r_[k] for n, r_ in zip(src, cur_rows) if (n in paid) == test) for k in range(5)]
        put(ws, 17 + j, 1, [lab] + sums)

    # ------------------------------------------------------------- defectos plantados
    if defects:
        w4 = wb["4"]
        w4.insert_rows(5)                                           # fila en blanco dentro de la tabla
        wb["7"].append(["Total", None, None, TOT_MONTO])            # subtotal mezclado con datos
        wb["7"].append([prod_names[0], 10, 11, 12345, 9, 1234.5, 0, 0.0])   # producto repetido
        wb["6"].cell(3, 4).value = -abs(wb["6"].cell(3, 4).value)   # monto negado negativo

    # ------------------------------------------------------------- nota (al final, no afecta a las hojas 1–9)
    ws = sheet("LEEME_SINTETICO")
    notes = ["DATOS SINTÉTICOS: todas las cifras son inventadas y no corresponden a ventas reales.",
             "Unidad: GLP-1 · Periodicidad: mensual · Periodo declarado: Septiembre 2026",
             "Formato: igual al libro operativo real (hojas 1–9).",
             "Variante: " + ("CON defectos plantados (Share=0, encabezado '& de rebote', fila en blanco en hoja 4, "
                             "subtotal y producto repetido en hoja 7, monto negado negativo, ortografía distinta "
                             "en Forma de Pago)" if defects else "limpia (sin defectos conocidos)"),
             f"Semilla: {SEED}. Generado con tools/make_glp1_synthetic.py"]
    for i, t in enumerate(notes, 1):
        ws.cell(i, 1, t)
    ws["A1"].font = Font(bold=True, color="FFFFFF")
    ws["A1"].fill = PatternFill("solid", fgColor="C00000")
    ws.column_dimensions["A"].width = 110
    wb.save(path)
    return path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("salida", type=Path)
    ap.add_argument("--defectos", action="store_true", help="planta defectos reales conocidos")
    a = ap.parse_args()
    a.salida.parent.mkdir(parents=True, exist_ok=True)
    print(build(a.salida, a.defectos))


if __name__ == "__main__":
    main()
