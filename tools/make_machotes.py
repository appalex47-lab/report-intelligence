"""Machotes de información (Excel de captura) para AETOPS y GLP-1, mensual y trimestral.

La estructura es exactamente la que lee el importador; los rótulos del periodo ya vienen puestos. Lo que el equipo
captura va en celdas amarillas; lo calculado va en gris (el motor lo recalcula, no hace falta capturarlo).

    python tools/make_machotes.py --unidad aetops --periodo 2026-9 --salida machotes/
    python tools/make_machotes.py --unidad glp1  --periodo 2026-3 --periodicidad trimestral --salida machotes/
    python tools/make_machotes.py --todos --periodo 2026-9 --salida machotes/        # los 4 formatos
    ... --ejemplo    # con cifras inventadas (para ver cómo se llena; NO usar como datos reales)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import openpyxl
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.models import MONTHS, Period  # noqa: E402

INPUT = PatternFill("solid", fgColor="FFF4C2")      # se captura
CALC = PatternFill("solid", fgColor="E6E8EC")       # se calcula (no capturar)
HEAD = PatternFill("solid", fgColor="0F5DA8")
SECT = PatternFill("solid", fgColor="D9E2F0")
WHITE = Font(bold=True, color="FFFFFF")
BOLD = Font(bold=True)
THIN = Side(style="thin", color="BFC5D0")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

LINEAS = ["AE-A", "AE-B", "AE-C", "HYR"]
CANALES = ["APP FESA", "ECOMMERCE", "LLAMADAS GOOGLE", "WHATSAPP"]
CATEGORIAS = ["Oncología y Hematología", "Ortopedia , Reumatología", "Neurología", "Endocrinología", "Dermatología",
              "Cardiología", "Infectología", "Inmunología", "Oftalmología", "Gastroenterología", "Ginecología",
              "Urología , Nefrología", "Neumología"]
M5 = ["Monto Venta", "Piezas", "Pacientes", "Pedidos"]


def month_cap(i: int) -> str:
    return MONTHS[i - 1].capitalize()


def labels(period: Period) -> dict:
    if period.periodicity == "mensual":
        return {"yoy": (period.year - 1, period.year),
                "mom": (month_cap(((period.index - 2) % 12) + 1), month_cap(period.index)), "neg": month_cap(period.index)}
    return {"yoy": (period.year - 1, period.year), "mom": None, "neg": f"Q{period.index} {period.year}"}


def num_validation(ws, rng: str, allow_neg=False):
    dv = DataValidation(type="decimal", operator="greaterThanOrEqual" if not allow_neg else "between",
                        formula1="0" if not allow_neg else "-1000000000", formula2=None if not allow_neg else "1000000000",
                        allow_blank=True, showErrorMessage=True, errorTitle="Valor no válido",
                        error="Captura solo números (sin $ ni texto). Si no hay dato, deja la celda VACÍA; no escribas 0 ni #N/A.")
    ws.add_data_validation(dv)
    dv.add(rng)


def style_cell(c, fill=None, bold=False):
    c.border = BOX
    if fill:
        c.fill = fill
    if bold:
        c.font = BOLD


def put_header(ws, r, c0, names):
    for i, n in enumerate(names):
        c = ws.cell(r, c0 + i, n)
        c.fill, c.font, c.border = HEAD, WHITE, BOX
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


# =========================================================================== AETOPS
EX = {  # cifras inventadas: (monto, piezas, pacientes, pedidos, productos)
    "TOTAL": [(1000000, 200, 100, 50, 40), (1500000, 300, 120, 60, 45)],
    "canal": {"APP FESA": [(200000, 40, 20, 10, 10), (450000, 90, 35, 18, 12)], "ECOMMERCE": [(300000, 60, 30, 15, 12), (500000, 100, 40, 20, 15)],
              "LLAMADAS GOOGLE": [(300000, 60, 30, 15, 10), (350000, 70, 30, 15, 10)], "WHATSAPP": [(200000, 40, 20, 10, 8), (200000, 40, 15, 7, 8)]},
    "linea": {"AE-A": [(600000, 120, 60, 30, 20), (900000, 180, 70, 36, 25)], "AE-B": [(250000, 50, 25, 12, 10), (400000, 80, 30, 14, 12)],
              "AE-C": [(100000, 20, 10, 5, 6), (140000, 28, 15, 7, 6)], "HYR": [(50000, 10, 5, 3, 4), (60000, 12, 6, 3, 2)]},
}


def _grp_block(ws, r, names, kind, fills, ex, mom=False, lab=None, total_row=None, cols_note=True):
    """Bloques de 4 filas: ancla, periodo previo, periodo actual, variaciones. Devuelve la fila siguiente."""
    prev, cur = (lab["mom"] if mom else lab["yoy"])
    for name in names:
        c = ws.cell(r, 2, name)
        style_cell(c, SECT, True)
        for k, lb in ((1, prev), (2, cur)):
            ws.cell(r + k, 2, lb).font = BOLD
            style_cell(ws.cell(r + k, 2))
            for j in range(3, 8):                    # C..G: Monto, Piezas, Pacientes, Pedidos, Ticket, (H) Producto
                pass
            for j in range(3, 9):
                style_cell(ws.cell(r + k, j), CALC if j in (7, 9) else INPUT)
            ws.cell(r + k, 7).fill = CALC
            ws.cell(r + k, 7, f'=IF(F{r + k}="","",IF(F{r + k}=0,"",C{r + k}/F{r + k}))')      # Ticket (referencia)
            style_cell(ws.cell(r + k, 9), CALC)
            if total_row:                                                                  # Share = monto ÷ total del periodo
                ws.cell(r + k, 9, f'=IF(C{r + k}="","",C{r + k}/$C${total_row[k - 1]})')
            if ex:
                for j, v in zip((3, 4, 5, 6, 8), ex[name][k - 1]):
                    ws.cell(r + k, j, v)
        for j in range(3, 10):
            style_cell(ws.cell(r + 3, j), CALC)
            col = get_column_letter(j)
            ws.cell(r + 3, j, f'=IF(OR({col}{r + 1}="",{col}{r + 1}=0,{col}{r + 2}=""),"",({col}{r + 2}-{col}{r + 1})/{col}{r + 1})')
        r += 4
    return r


def aetops_machote(period: Period, example: bool = False) -> openpyxl.Workbook:
    lab = labels(period)
    mensual = period.periodicity == "mensual"
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    leeme(wb, "AETOPS", period, example)
    ws = wb.create_sheet("Base")
    ws.column_dimensions["A"].width = 3
    ws.column_dimensions["B"].width = 26
    for j in range(3, 12):
        ws.column_dimensions[get_column_letter(j)].width = 15
    H = ["Monto Venta", "Piezas", "Pacientes", "Pedidos", "Ticket Promedio", "Producto Vendidos"]

    # --- panorama
    def panorama(r, marker, lb, ex_idx=None):
        ws.cell(r, 2, marker).font = BOLD
        put_header(ws, r + 1, 2, ["Año"] + H + ["Size B", "V. Paciente"])
        for k, l in ((2, lb[0]), (3, lb[1])):
            ws.cell(r + k, 2, l).font = BOLD
            style_cell(ws.cell(r + k, 2))
            for j in (3, 4, 5, 6, 8):
                style_cell(ws.cell(r + k, j), INPUT)
            for j, f in ((7, f'=IF(F{r + k}="","",IF(F{r + k}=0,"",C{r + k}/F{r + k}))'),
                         (9, f'=IF(E{r + k}="","",IF(E{r + k}=0,"",D{r + k}/E{r + k}))'),
                         (10, f'=IF(E{r + k}="","",IF(E{r + k}=0,"",C{r + k}/E{r + k}))')):
                ws.cell(r + k, j, f)
                style_cell(ws.cell(r + k, j), CALC)
            if example:
                for j, v in zip((3, 4, 5, 6, 8), EX["TOTAL"][k - 2]):
                    ws.cell(r + k, j, v)
        for j in range(3, 11):
            col = get_column_letter(j)
            style_cell(ws.cell(r + 4, j), CALC)
            ws.cell(r + 4, j, f'=IF(OR({col}{r + 2}="",{col}{r + 2}=0,{col}{r + 3}=""),"",({col}{r + 3}-{col}{r + 2})/{col}{r + 2})')
        return r + 6
    r = panorama(1, "YoY", lab["yoy"])
    yoy_tot = (3, 4)
    mom_tot = None
    if mensual:
        mom_tot = (r + 2, r + 3)
        r = panorama(r, "MoM", lab["mom"])

    def section(r, title_marker, header_first, names, kind, mom):
        ws.cell(r, 2, title_marker).font = BOLD
        put_header(ws, r + 1, 2, [header_first] + H + ["Share"])
        tot = mom_tot if mom else yoy_tot
        ex = EX[kind] if example else None
        return _grp_block(ws, r + 2, names, kind, None, ex, mom, lab, total_row=tot) + 1

    for kind, names, first in (("canal", CANALES, "Canal"), ("linea", LINEAS, "AETOP")):
        r = section(r, "YoY", first, names, kind, False)
        if mensual:
            r = section(r, "MoM", first, names, kind, True)

    # --- categorías: el nombre va en la columna C de la 1.ª fila del grupo
    def cats(r, marker, mom):
        prev, cur = lab["mom"] if mom else lab["yoy"]
        ws.cell(r, 2, marker).font = BOLD
        put_header(ws, r + 1, 2, ["Año", "Categoría"] + H + ["Share"])
        r += 2
        tot = mom_tot if mom else yoy_tot
        for name in CATEGORIAS:
            for k, lb in ((0, prev), (1, cur)):
                ws.cell(r + k, 2, lb).font = BOLD
                style_cell(ws.cell(r + k, 2))
                for j in (4, 5, 6, 7, 9):
                    style_cell(ws.cell(r + k, j), INPUT)
                ws.cell(r + k, 8, f'=IF(G{r + k}="","",IF(G{r + k}=0,"",D{r + k}/G{r + k}))')
                ws.cell(r + k, 10, f'=IF(D{r + k}="","",D{r + k}/$C${tot[k]})')
                for j in (8, 10):
                    style_cell(ws.cell(r + k, j), CALC)
            ws.cell(r, 3, name).font = BOLD
            style_cell(ws.cell(r, 3), SECT)
            for j in range(4, 11):
                style_cell(ws.cell(r + 2, j), CALC)
                col = get_column_letter(j)
                ws.cell(r + 2, j, f'=IF(OR({col}{r}="",{col}{r}=0,{col}{r + 1}=""),"",({col}{r + 1}-{col}{r})/{col}{r})')
            r += 3
        return r + 1
    r = cats(r, "YoY", False)
    if mensual:
        r = cats(r, "MoM", True)
    num_validation(ws, f"C3:J{r}")
    ws.freeze_panes = "C1"

    # --- Tablas: Top 20 / mayor crecimiento / mayor decrecimiento (solo mensual y trimestral con el mismo formato)
    t = wb.create_sheet("Tablas")
    for c in "ABCDEFG":
        t.column_dimensions[c].width = 16
    t.column_dimensions["B"].width = 42
    t.column_dimensions["K"].width = 42
    for c in "JLMNOP":
        t.column_dimensions[c].width = 16
    ant = "Venta Mes Anterior" if mensual else "Venta Mes Anterior"
    heads = ["Sivec", "Producto", "AETOP", "Canales de Venta", "Venta Mes Actual", ant, "Delta"]
    blocks = [(1, 1, 20), (1, 10, 10), (13, 10, 10)]
    for hr, c0, n in blocks:
        put_header(t, hr, c0, heads)
        for i in range(1, n + 1):
            r2 = hr + i
            for j in range(c0, c0 + 6):
                style_cell(t.cell(r2, j), INPUT)
            e, f = get_column_letter(c0 + 4), get_column_letter(c0 + 5)
            t.cell(r2, c0 + 6, f'=IF({e}{r2}="","",{e}{r2}-N({f}{r2}))')
            style_cell(t.cell(r2, c0 + 6), CALC)
        dv = DataValidation(type="list", formula1='"AE-A,AE-B,AE-C,HYR"', allow_blank=True)
        t.add_data_validation(dv)
        dv.add(f"{get_column_letter(c0 + 2)}{hr + 1}:{get_column_letter(c0 + 2)}{hr + n}")
        num_validation(t, f"{get_column_letter(c0 + 4)}{hr + 1}:{get_column_letter(c0 + 5)}{hr + n}")
    t.cell(1, 6).comment = Comment("Si el producto NO tuvo venta en el periodo anterior, deja esta celda VACÍA "
                                   "(no pongas 0 ni #N/A): se mostrará como producto nuevo.", "Report Intelligence")
    t["A24"] = "Cada bloque ordenado como en el reporte: izquierda = Top 20 por venta; derecha arriba = mayor crecimiento; derecha abajo = mayor decrecimiento."
    t["A24"].font = Font(italic=True, color="586379")

    # --- Negados
    n = wb.create_sheet("Negados")
    n["A1"] = lab["neg"]
    n["A1"].font = Font(bold=True, size=12)
    n["A1"].comment = Comment("Periodo de la hoja. Mensual: nombre del mes (ej. Septiembre). Trimestral: Q3 2026.", "Report Intelligence")
    put_header(n, 2, 1, ["Nombre del Producto", "Alta", "Pedidos", "Cantidad Negada", "Monto Negado", "Share"])
    n.column_dimensions["A"].width = 46
    for c in "BCDEF":
        n.column_dimensions[c].width = 16
    for i in range(3, 153):
        for j in range(1, 6):
            style_cell(n.cell(i, j), INPUT)
        n.cell(i, 6, f'=IF(E{i}="","",E{i}/SUM($E$3:$E$152))')
        style_cell(n.cell(i, 6), CALC)
    dv = DataValidation(type="list", formula1='"AE-A,AE-B,AE-C,HYR"', allow_blank=True)
    n.add_data_validation(dv)
    dv.add("B3:B152")
    num_validation(n, "C3:E152")
    n["B2"].comment = Comment("Producto sin stock que se negó a la venta. La tabla por línea (Alta) la calcula el sistema sumando esta lista.", "Report Intelligence")
    if example:
        for i, (nm, al, p, q, m) in enumerate([("PRODUCTO NEGADO 1 (ejemplo)", "AE-A", 5, 6, 600000),
                                               ("PRODUCTO NEGADO 2 (ejemplo)", "AE-B", 3, 3, 300000),
                                               ("PRODUCTO NEGADO 3 (ejemplo)", "AE-A", 1, 1, 100000)], 3):
            for j, v in enumerate((nm, al, p, q, m), 1):
                n.cell(i, j, v)
        for k, (nm, al, c, ant_, d) in enumerate([("PRODUCTO EJEMPLO 1", "AE-A", 4, 1000000, 700000), ("PRODUCTO EJEMPLO 2", "AE-B", 3, 800000, 750000),
                                                  ("PRODUCTO NUEVO (ejemplo)", "AE-C", 1, 100000, None)], 2):
            for hr, c0 in ((1, 1),):
                for j, v in enumerate((k - 1, nm, al, c, ant_, d), c0):
                    t.cell(k, j, v)
    return wb


# =========================================================================== GLP-1
def glp1_machote(period: Period, example: bool = False) -> openpyxl.Workbook:
    """Parte del libro operativo (hojas 1–9, mismas posiciones que lee el importador) con los datos vaciados."""
    from tools.make_glp1_synthetic import build
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        src = build(Path(d) / "s.xlsx")
        wb = openpyxl.load_workbook(src)
    del wb["LEEME_SINTETICO"]
    keep_text = {"1", "2", "3", "4", "5", "8", "9"}
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                v = c.value
                is_time = isinstance(v, str) and len(v) == 8 and v[2] == ":" and v[5] == ":"
                if isinstance(v, (int, float)) and not isinstance(v, bool) or is_time:
                    if not example:
                        c.value = None
                    c.fill, c.border = INPUT, BOX
                elif isinstance(v, str) and c.row == 1 or (isinstance(v, str) and ws.title in ("1", "9") and c.column == 1 and v in (
                        "Edad", "Sexo", "Categoría de dispositivo", "Canal", "Categoría de dispositivo")):
                    pass
        if ws.title in ("6", "7") and not example:       # listas libres: se capturan los productos del mes
            for r in range(2, ws.max_row + 1):
                for c in range(1, 9):
                    ws.cell(r, c).value = None
                    ws.cell(r, c).fill, ws.cell(r, c).border = INPUT, BOX
            for r in range(ws.max_row + 1, 22):
                for c in range(1, 9):
                    ws.cell(r, c).fill, ws.cell(r, c).border = INPUT, BOX
        for c in ws[1]:
            if c.value is not None:
                c.font = WHITE
                c.fill = HEAD
    # Ticket y Share: calculados (se recalculan al importar); se marcan en gris
    for ws in wb.worksheets:
        hdr_rows = [r for r in range(1, ws.max_row + 1) if ws.cell(r, 1).value in ("Región", "Forma de Pago", "Modo de Entrega",
                    "Nombre del Producto", "Producto", "Programa de Lealtad", "Edad", "Sexo", "Categoría de dispositivo", "Canal")]
        for hr in hdr_rows:
            for c in range(1, ws.max_column + 1):
                h = ws.cell(hr, c).value
                if h in ("Ticket Promedio", "Share"):
                    r2 = hr + 1
                    while r2 <= ws.max_row and ws.cell(r2, 1).value not in (None, ""):
                        ws.cell(r2, c).fill = CALC
                        ws.cell(r2, c).value = None
                        r2 += 1
    ps = wb.create_sheet("Parametros")
    ps["A1"], ps["B1"] = "Unidad", "GLP-1"
    ps["A2"], ps["B2"] = "Periodicidad", period.periodicity
    ps["A3"] = "Periodo declarado: " + (f"{month_cap(period.index)} {period.year}" if period.periodicity == "mensual" else f"Q{period.index} {period.year}")
    ps["A3"].font = BOLD
    ps["A5"] = "No cambies el texto de la fila 3 salvo que cambie el periodo: el sistema lo compara con el periodo que eliges."
    ps.column_dimensions["A"].width = 60
    leeme(wb, "GLP-1", period, example)
    wb.move_sheet("LEEME", offset=-(len(wb.sheetnames) - 1))
    return wb


# =========================================================================== LEEME
def leeme(wb, unidad: str, period: Period, example: bool):
    ws = wb.create_sheet("LEEME")
    ws.column_dimensions["A"].width = 118
    per = f"{month_cap(period.index)} {period.year}" if period.periodicity == "mensual" else f"Q{period.index} {period.year}"
    L = [
        (f"MACHOTE {unidad} · {period.periodicity} · {per}", "t"),
        ("DATOS DE EJEMPLO inventados: no usar como información real." if example else "Machote vacío: captura la información real del periodo.", "w" if example else None),
        ("", None),
        ("CÓMO LLENARLO", "h"),
        ("1. Captura SOLO en celdas amarillas. Las grises se calculan solas: no las captures ni las borres.", None),
        ("2. Números limpios: sin $, sin comas escritas a mano, sin texto. Si no hay dato, deja la celda VACÍA.", None),
        ("3. Nunca escribas 0 ni #N/A para decir «no hay dato»: 0 significa que se vendió cero; vacío significa que no existe.", None),
        ("4. No insertes filas en blanco dentro de una tabla y no pongas filas de «Total» entre los datos.", None),
        ("5. No cambies los nombres de hojas, encabezados ni rótulos del periodo (año/mes). Si cambia el periodo, genera otro machote.", None),
        ("6. Usa los nombres exactos de líneas, canales y formas de pago. Para agregar uno nuevo, copia un bloque completo.", None),
        ("7. Las METAS del periodo no van en este libro: se capturan en la herramienta antes de generar" + (" (obligatorias en AETOPS)." if unidad == "AETOPS" else " (opcionales en GLP-1)."), None),
        ("", None),
    ]
    if unidad == "AETOPS":
        L += [("QUÉ LLEVA CADA HOJA", "h"),
              ("Base: panorama, canales, líneas y categorías. Por cada grupo captura Monto, Piezas, Pacientes, Pedidos y Productos del periodo anterior y del actual.", None),
              ("Tablas: Top 20 de productos por venta (izquierda), mayor crecimiento (derecha arriba) y mayor decrecimiento (derecha abajo). Si un producto no vendió en el periodo anterior, deja «Venta Mes Anterior» vacía.", None),
              ("Negados: producto sin stock que se negó a la venta. Captura cada producto con su línea (Alta), pedidos, cantidad y monto negado. La tabla por línea la calcula el sistema.", None),
              ("Periodos: " + ("YoY compara contra el mismo mes del año anterior; MoM contra el mes anterior." if period.periodicity == "mensual" else "solo YoY: contra el mismo trimestre del año anterior."), None)]
    else:
        L += [("QUÉ LLEVA CADA HOJA", "h"),
              ("1 Edad/Sexo/Dispositivo · 2 Edad por producto · 3 Producto por sexo · 4 Región (+ bloque del mes anterior y tráfico por estado) · 5 Forma de pago, entrega y embudo · 6 Negados · 7 Productos · 8 Programas · 9 Fuentes de tráfico.", None),
              ("Los bloques «anterior» (hojas 4, 5 y 9, a la derecha) llevan las cifras del MES ANTERIOR: con ellos el sistema recalcula el %Δ. En las tablas sin bloque anterior, captura el %Δ contra el mes anterior.", None),
              ("Ticket Promedio = Monto Venta ÷ Pedidos (se calcula). Share = parte ÷ total (se calcula).", None),
              ("Embudo (hoja 5): captura el conteo de cada etapa en la columna E; la tasa se calcula contra «Ver producto».", None)]
    L += [("", None), ("ERRORES FRECUENTES Y QUÉ SIGNIFICAN", "h"),
          ("PERIOD_MISMATCH / IDENTICAL_PERIODS · el periodo del libro no es el elegido, o el mes anterior trae las mismas cifras que el actual (archivo sin actualizar).", None),
          ("COLUMN_UNMAPPED · cambió un encabezado: restáuralo tal como viene en el machote.", None),
          ("BLANK_ROW_INSIDE · hay una fila vacía dentro de una tabla: elimínala.", None),
          ("TOTALS_MISMATCH · las partes no suman el total (canales, líneas, categorías o formas de pago).", None),
          ("TARGETS_MISSING · faltan las metas (se capturan en la herramienta).", None),
          ("", None), ("Colores:  amarillo = captura · gris = calculado · azul = encabezado (no tocar).", None)]
    for i, (t, k) in enumerate(L, 1):
        c = ws.cell(i, 1, t)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        if k == "t":
            c.font = Font(bold=True, size=14)
        elif k == "h":
            c.font, c.fill = BOLD, SECT
        elif k == "w":
            c.font, c.fill = Font(bold=True, color="9C0006"), PatternFill("solid", fgColor="FFC7CE")
    ws.cell(len(L), 1).fill = INPUT
    return ws


def make(unit: str, period: Period, out: Path, example=False) -> Path:
    wb = aetops_machote(period, example) if unit == "aetops" else glp1_machote(period, example)
    tag = (f"{month_cap(period.index)}_{period.year}" if period.periodicity == "mensual" else f"Q{period.index}_{period.year}")
    name = f"MACHOTE_{unit.upper()}_{period.periodicity}_{tag}{'_EJEMPLO' if example else ''}.xlsx"
    out.mkdir(parents=True, exist_ok=True)
    path = out / name
    wb.save(path)
    return path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--unidad", choices=["aetops", "glp1"])
    ap.add_argument("--periodo", required=True, help="AAAA-N (mes 1-12 o trimestre 1-4)")
    ap.add_argument("--periodicidad", choices=["mensual", "trimestral"], default="mensual")
    ap.add_argument("--salida", type=Path, default=Path("machotes"))
    ap.add_argument("--ejemplo", action="store_true")
    ap.add_argument("--todos", action="store_true")
    a = ap.parse_args()
    y, i = a.periodo.split("-")
    combos = [(u, p) for u in ("aetops", "glp1") for p in ("mensual", "trimestral")] if a.todos else [(a.unidad, a.periodicidad)]
    for u, p in combos:
        idx = int(i) if p == "mensual" else ((int(i) - 1) // 3 + 1 if int(i) > 4 else int(i))
        print(make(u, Period("AETOPS" if u == "aetops" else "GLP1", p, int(y), idx), a.salida, a.ejemplo))


if __name__ == "__main__":
    main()
