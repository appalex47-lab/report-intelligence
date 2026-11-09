"""La columna «Sivec» (códigos de producto) no cuenta como cifras para el QA de cifras, moneda y denominadores.

Defecto que corrige: el QA solo reconocía como código un número plano de 5 o más cifras; un código Sivec de 4 cifras («7928») se tomaba por una cifra de venta y daba una advertencia
`PPTX_CIFRA_NO_TRAZADA` (visto con el libro real del usuario, octubre 2026). Corre en CI: usa PPTX sintéticos y las plantillas sintéticas."""
import importlib
import json
from decimal import Decimal
from pathlib import Path

import openpyxl
import pytest
from pptx import Presentation
from pptx.util import Pt

from backend.app.qa import cifras
from tests import plantillas as PL

ROOT = Path(__file__).resolve().parents[2]
EJ = ROOT / "data" / "ejemplos"


def pptx_con_tabla(filas, ruta=None):
    prs = Presentation()
    prs.slide_width, prs.slide_height = Pt(960), Pt(540)
    sl = prs.slides.add_slide(prs.slide_layouts[6])
    t = sl.shapes.add_table(len(filas), len(filas[0]), Pt(40), Pt(40), Pt(800), Pt(30 * len(filas))).table
    for i, f in enumerate(filas):
        for j, v in enumerate(f):
            t.cell(i, j).text = v
    return prs


VALORES = {Decimal("1250000"), Decimal("350")}


def sin_trazar(prs):
    return [i.message for i in cifras.comprobar_cifras(prs, VALORES, set()) if i.id == "PPTX_CIFRA_NO_TRAZADA"]


def test_un_codigo_sivec_de_cuatro_cifras_no_es_una_cifra():
    prs = pptx_con_tabla([["Sivec", "Producto", "Venta"], ["7928", "ENZALUTAMIDA", "$1,250,000"], ["1234", "OTRO", "350"]])
    assert sin_trazar(prs) == []


def test_una_cifra_inventada_en_otra_columna_de_la_misma_tabla_se_sigue_marcando():
    prs = pptx_con_tabla([["Sivec", "Producto", "Venta"], ["7928", "ENZALUTAMIDA", "$9,999,999"]])
    marcadas = sin_trazar(prs)
    assert len(marcadas) == 1 and "9,999,999" in marcadas[0] and "7928" not in marcadas[0]


def test_sin_encabezado_sivec_un_numero_de_cuatro_cifras_sigue_siendo_una_cifra():
    """Control: la exención es solo para la columna de códigos, no para cualquier entero."""
    prs = pptx_con_tabla([["Código", "Producto", "Venta"], ["7928", "ENZALUTAMIDA", "$1,250,000"]])
    assert len(sin_trazar(prs)) == 1


def test_la_columna_sivec_puede_estar_en_cualquier_posicion_y_el_encabezado_no_distingue_mayusculas():
    prs = pptx_con_tabla([["Producto", "SIVEC", "Venta"], ["ENZALUTAMIDA", "7928", "$1,250,000"]])
    assert sin_trazar(prs) == []


def test_las_comprobaciones_de_moneda_y_denominadores_tampoco_tratan_el_codigo_como_cifra():
    prs = pptx_con_tabla([["Sivec", "Producto"], ["7928", "ENZALUTAMIDA"], ["1234", "OTRO"]])
    for comprobar in (cifras.comprobar_moneda, cifras.comprobar_denominadores):
        assert [i for i in comprobar(prs) if "7928" in i.message or "1234" in i.message] == [], comprobar.__name__


# ------------------------------------------------------------------------------------------------------------------- extremo a extremo
@pytest.fixture()
def br(tmp_path, monkeypatch):
    monkeypatch.setenv("REPORT_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("REPORT_HISTORY_DB", str(tmp_path / "h" / "h.sqlite"))
    monkeypatch.setenv("REPORT_TEMPLATES_DIR", str(tmp_path / "tpl"))
    (tmp_path / "h").mkdir()
    from backend.app.web import bridge, service
    importlib.reload(service)
    importlib.reload(bridge)
    service.RENDER = False
    assert call(bridge, "POST", "/api/templates/aetops-mensual", up=PL.ruta("aetops-mensual"))["status"] == 200
    return bridge, service


def call(bridge, method, path, body=None, up=None):
    return json.loads(bridge.handle(method, path, json.dumps(body) if body is not None else "", str(up) if up else "", up.name if up else ""))


def test_un_libro_con_codigos_de_cuatro_cifras_no_da_advertencias_de_cifras(br, tmp_path):
    """Libro de ejemplo con el SKU 24369 cambiado a 7928 en todas las hojas: el código sale en la tabla de productos y no se marca."""
    wb = openpyxl.load_workbook(EJ / "AETOPS_crudo_ejemplo.xlsx")
    for ws in wb:
        cab = [c.value for c in ws[1]]
        j = cab.index("sku") + 1
        for r in range(2, ws.max_row + 1):
            if ws.cell(r, j).value == "24369":
                ws.cell(r, j).value = "7928"
    libro = tmp_path / "cuatro_cifras.xlsx"
    wb.save(libro)
    bridge, service = br
    rid = call(bridge, "POST", "/api/runs", {"unit": "aetops", "periodicity": "mensual", "year": 2026, "index": 9})["json"]["id"]
    assert call(bridge, "POST", f"/api/runs/{rid}/file", up=libro)["status"] == 200
    call(bridge, "PUT", f"/api/runs/{rid}/targets", {"total": "12000000"})
    assert call(bridge, "POST", f"/api/runs/{rid}/generate", {})["status"] == 200
    prs = Presentation(str(next((service._dir(rid) / "out").glob("*.pptx"))))
    codigos = [sh.table.cell(r, 0).text_frame.text for s in prs.slides for sh in s.shapes if sh.has_table and sh.table.cell(0, 0).text_frame.text.strip() == "Sivec" for r in range(1, len(sh.table.rows))]
    assert "7928" in codigos                                                                # el código de 4 cifras está impreso
    hs = call(bridge, "GET", f"/api/runs/{rid}/plan")["json"]["qa_integral"]["hallazgos"]
    assert not [h for h in hs if h["id"] == "PPTX_CIFRA_NO_TRAZADA"]
