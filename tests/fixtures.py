"""Libro sintético con el layout de la hoja `Base` (cifras inventadas, calculadas a mano)."""
from __future__ import annotations

from pathlib import Path

import openpyxl

HDR = ["Monto Venta", "Piezas", "Pacientes", "Pedidos", "Ticket Promedio", "Producto Vendidos"]


def _put(ws, r, label, vals):
    ws.cell(r, 2, label)
    for i, v in enumerate(vals):
        if v is not None:
            ws.cell(r, 3 + i, v)


def _delta(ws, r, p, c):
    for i, (a, b) in enumerate(zip(p, c)):
        if a not in (None, 0) and b is not None:
            ws.cell(r, 3 + i, (b - a) / a)


def build_base(path: Path, *, mom_identical=False, header_typo=False, mom_label_mismatch=False,
               pedidos_blank=False, canal_total_off=False, ext=".xlsx", quarterly=False,
               sort_broken=False, negados_label="Septiembre", alta_off=False) -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Base"

    def header(r, first, extra=()):
        ws.cell(r, 2, first)
        for i, h in enumerate(HDR + list(extra)):
            ws.cell(r, 3 + i, "Monto Venat" if (header_typo and i == 0 and first == "Canal") else h)

    # Panorama YoY: 2025 -> 2026
    p25 = [1000, 200, 100, 50, 20, 40]
    p26 = [1500, 300, 120, 60, 25, 45]
    if pedidos_blank:
        p26[3] = None
    ws.cell(1, 2, "Yoy"); header(2, "Año")
    _put(ws, 3, 2025, p25); _put(ws, 4, 2026, p26); _delta(ws, 5, p25, p26)
    # Panorama MoM
    m_prev = list(p25)               # consistente con las sumas de canales/líneas/categorías
    m_cur = list(m_prev) if mom_identical else p26
    if not quarterly:
        ws.cell(7, 2, "MoM"); header(8, "Año")
        _put(ws, 9, "Agosto", m_prev); _put(ws, 10, "Septiembre", m_cur)

    # Canales YoY (A y B suman el panorama)
    ws.cell(13, 2, "YoY"); header(14, "Canal", ["Share"])
    a25, a26 = [400, 80, 40, 20, 20, 30], [900, 180, 70, 36, 25, 35 if not canal_total_off else 35]
    b25, b26 = [600, 120, 60, 30, 20, 25], [600, 120, 50, 24, 25, 20]
    if canal_total_off:
        b26[0] = 100
    r = 15
    for name, x, y in (("CANAL A", a25, a26), ("CANAL B", b25, b26)):
        ws.cell(r, 2, name); _put(ws, r + 1, 2025, x); _put(ws, r + 2, 2026, y); _delta(ws, r + 3, x, y)
        r += 4
    # Canales MoM: el segundo grupo con otro rótulo de periodo
    rr = r
    if not quarterly:
        ws.cell(r + 1, 2, "MoM"); header(r + 2, "Canal", ["Share"])
        rr = r + 3
        for i, name in enumerate(("CANAL A", "CANAL B")):
            l0, l1 = ("Agosto", "Septiembre") if not (mom_label_mismatch and i == 1) else ("Julio", "Agosto")
            ws.cell(rr, 2, name); _put(ws, rr + 1, l0, a25 if i == 0 else b25)
            _put(ws, rr + 2, l1, a26 if i == 0 else b26); rr += 4

    # Líneas YoY (L1 = A, L2 = B) + una fila sobrante sin rótulo como en el Excel real
    start = rr + 2
    ws.cell(start, 2, "YoY"); header(start + 1, "AETOP", ["Share"])
    r = start + 2
    for name, x, y in (("AE-A", a25, a26), ("AE-B", b25, b26)):
        ws.cell(r, 2, name); _put(ws, r + 1, 2025, x); _put(ws, r + 2, 2026, y); _delta(ws, r + 3, x, y)
        r += 4
    ws.cell(r, 3, 123456)           # fila sobrante
    r += 2
    if not quarterly:                # Líneas MoM
        ws.cell(r, 2, "MoM"); header(r + 1, "AETOP", ["Share"]); r += 2
        for name, x, y in (("AE-A", a25, a26), ("AE-B", b25, b26)):
            ws.cell(r, 2, name); _put(ws, r + 1, "Agosto", x); _put(ws, r + 2, "Septiembre", y)
            r += 4
        r += 1
    # Categorías: el nombre va en la columna C de la 1.ª fila del grupo
    c1 = ([600, 120, 60, 30, 20, 25], [900, 180, 70, 36, 25, 30])
    c2 = ([400, 80, 40, 20, 20, 15], [600, 120, 50, 24, 25, 15])
    for marker, l0, l1 in (("YoY", 2025, 2026), ("MoM", "Agosto", "Septiembre")):
        if marker == "MoM" and quarterly:
            continue
        ws.cell(r, 2, marker); ws.cell(r + 1, 2, "Año"); ws.cell(r + 1, 3, "Categoría")
        for i, h in enumerate(HDR + ["Share"]):
            ws.cell(r + 1, 4 + i, h)
        r += 2
        for name, (x, y) in (("CAT 1", c1), ("CAT 2", c2)):
            ws.cell(r, 2, l0); ws.cell(r, 3, name)
            for i, v in enumerate(x): ws.cell(r, 4 + i, v)
            ws.cell(r + 1, 2, l1)
            for i, v in enumerate(y): ws.cell(r + 1, 4 + i, v)
            r += 3
        r += 1
    _add_products_and_negados(wb, sort_broken, negados_label, alta_off)
    path = path.with_suffix(ext)
    wb.save(path)
    return path


def _add_products_and_negados(wb, sort_broken, negados_label, alta_off):
    t = wb.create_sheet("Tablas")
    H = ["Sivec", "Producto", "AETOP", "Canales de Venta", "Venta Mes Actual", "Venta Mes Anterior", "Delta"]

    def block(r0, c0, rows):
        for i, h in enumerate(H):
            t.cell(r0, c0 + i, h)
        for j, row in enumerate(rows):
            for i, v in enumerate(row):
                t.cell(r0 + 1 + j, c0 + i, v)

    top = [(1, "PROD 1", "AE-A", 4, 1000, 700, 300), (2, "PROD 2", "AE-B", 3, 800, 750, 50),
           (3, "PROD 3 NUEVO", "AE-C", 1, 100, "#N/A", 0)]          # IFERROR(...,0) en el Excel
    if sort_broken:
        top[0], top[1] = top[1], top[0]
    block(1, 1, top)
    block(1, 10, [(4, "PROD 4", "AE-A", 2, 500, 200, 300), (5, "PROD 5", "AE-B", 2, 300, 250, 50)])
    block(7, 10, [(6, "PROD 6", "AE-A", 2, 100, 400, -300), (7, "PROD 7", "AE-B", 1, 200, 250, -50)])

    n = wb.create_sheet("Negados")
    n.cell(1, 1, negados_label)
    hp = ["Nombre del Producto", "Alta", "Pedidos", "Cantidad Negada", "Monto Negado", "Share"]
    prods = [("NEG 1", "AE-A", 5, 6, 600, 0.6), ("NEG 2", "AE-B", 3, 3, 300, 0.3), ("NEG 3", "AE-A", 1, 1, 100, 0.1)]
    for off in (1, 8):                                   # bloque y su duplicado (como en el Excel real)
        for i, h in enumerate(hp):
            n.cell(2, off + i, h)
        for j, row in enumerate(prods):
            for i, v in enumerate(row):
                n.cell(3 + j, off + i, v)
    for i, h in enumerate(["Alta", "Pedidos", "Cantidad Negada", "Monto Negado", "Share"]):
        n.cell(2, 15 + i, h)
    altas = [("AE-A", 6, 7, 700, 0.7), ("AE-B", 3, 3, 300 if not alta_off else 100, 0.3)]
    for j, row in enumerate(altas):
        for i, v in enumerate(row):
            n.cell(3 + j, 15 + i, v)
