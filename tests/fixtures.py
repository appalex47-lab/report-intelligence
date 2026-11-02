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
               pedidos_blank=False, canal_total_off=False, ext=".xlsx") -> Path:
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
    m_prev = [1400, 280, 110, 55, 25.45, 42]
    m_cur = list(m_prev) if mom_identical else p26
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
    path = path.with_suffix(ext)
    wb.save(path)
    return path
