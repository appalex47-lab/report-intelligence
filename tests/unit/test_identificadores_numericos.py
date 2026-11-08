"""Códigos (SKU, id de pedido y de paciente) guardados como NÚMERO en el libro: se leen como texto, sin «.0».

Defecto que corrige: un libro cuyos SKU eran números con literal «23522.0» se leía como el texto «23522.0»; en la tabla «Análisis de Productos» el código Sivec salía «23522.0» y el
QA marcaba una advertencia `PPTX_CIFRA_NO_TRAZADA` por cada código (40 en el libro de ejemplo). Además un catálogo con texto y ventas con número no coincidían (SKU «no está en el catálogo»).
Corre en CI: usa las plantillas sintéticas si no están las reales (tests/plantillas.py)."""
import importlib
import json
import re
import zipfile
from decimal import Decimal
from pathlib import Path

import openpyxl
import pytest

from backend.app.raw.common import IDENTIFICADORES, como_identificador
from tests import plantillas as PL

ROOT = Path(__file__).resolve().parents[2]
EJ = ROOT / "data" / "ejemplos"


# ------------------------------------------------------------------------------------------------------------------- la función
@pytest.mark.parametrize("entrada,esperado", [
    (23522, "23522"), (23522.0, "23522"), (Decimal("23522.0"), "23522"), ("23522.0", "23522"), ("23522.00", "23522"), (" 23522 ", "23522"), ("23522", "23522"),
    ("A2507-000001", "A2507-000001"), ("PX000277", "PX000277"), ("007", "007"), ("0023522.0", "0023522"),            # un texto con ceros a la izquierda conserva su forma
    (1.5, "1.5"), ("1.5", "1.5"), ("10.50", "10.50"), ("ABC.0", "ABC.0"), ("5.0", "5.0"), ("", ""), (None, None), (True, True),
])
def test_como_identificador(entrada, esperado):
    assert como_identificador(entrada) == esperado


def test_las_columnas_de_codigos_son_sku_y_los_ids():
    assert set(IDENTIFICADORES) == {"sku", "id_pedido", "id_paciente"}                  # las cantidades y los montos NO se tocan


# ------------------------------------------------------------------------------------------------------------------- libros con códigos numéricos
def con_codigos_numericos(origen: Path, destino: Path, hojas_columnas: dict[str, list[str]]) -> Path:
    """Copia del libro con esas columnas guardadas como NÚMERO con literal «N.0» (openpyxl escribiría «N» y lo releería como entero; muchos exportadores escriben «N.0»)."""
    wb = openpyxl.load_workbook(origen)
    for hoja, cols in hojas_columnas.items():                                           # 1) el texto «24369» pasa a ser el NÚMERO 24369 (celda numérica, no cadena compartida)
        cabecera = [c.value for c in wb[hoja][1]]
        for col in cols:
            j = cabecera.index(col) + 1
            for r in range(2, wb[hoja].max_row + 1):
                c = wb[hoja].cell(r, j)
                if isinstance(c.value, str) and c.value.isdigit():
                    c.value = int(c.value)
    intermedio = destino.with_suffix(".tmp.xlsx")
    wb.save(intermedio)
    hojas = {n: f"xl/worksheets/sheet{i}.xml" for i, n in enumerate(wb.sheetnames, 1)}
    letras = {}
    for hoja, cols in hojas_columnas.items():
        cabecera = [c.value for c in wb[hoja][1]]
        letras[hoja] = [openpyxl.utils.get_column_letter(cabecera.index(c) + 1) for c in cols]
    zin, zout = zipfile.ZipFile(intermedio), zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED)
    for item in zin.infolist():
        datos = zin.read(item.filename)
        for hoja, ruta in hojas.items():
            if item.filename == ruta and hoja in letras:
                for L in letras[hoja]:
                    datos = re.sub(rb'(<c r="%s(?:[2-9]|[1-9]\d+)"[^>]*>)<v>(\d+)</v>' % L.encode(), rb"\1<v>\2.0</v>", datos)       # 2) el literal pasa a «24369.0»
        zout.writestr(item, datos)
    zout.close()
    intermedio.unlink()
    return destino


def test_el_libro_variante_realmente_guarda_numeros_con_literal_decimal(tmp_path):
    """Control de la propia prueba: sin la corrección el defecto se reproduce (si esto falla, la variante no está reproduciendo el caso)."""
    v = con_codigos_numericos(EJ / "AETOPS_crudo_ejemplo.xlsx", tmp_path / "v.xlsx", {"catalogo": ["sku"]})
    with zipfile.ZipFile(v) as z:
        hoja = z.read("xl/worksheets/sheet2.xml").decode("utf-8")
    assert re.search(r'<c r="A2"[^>]*><v>\d+\.0</v>', hoja)
    celda = openpyxl.load_workbook(v, read_only=True, data_only=True)["catalogo"]["A2"].value
    assert celda == float(int(celda)) and isinstance(celda, float)                       # openpyxl lo entrega como float (23522.0), no como texto


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
    for k in ("aetops-mensual", "glp1-mensual"):
        assert call(bridge, "POST", f"/api/templates/{k}", up=PL.ruta(k))["status"] == 200
    return bridge, service


def call(bridge, method, path, body=None, up=None):
    return json.loads(bridge.handle(method, path, json.dumps(body) if body is not None else "", str(up) if up else "", up.name if up else ""))


def textos(pptx: Path) -> list:
    from pptx import Presentation
    out = []
    for s in Presentation(str(pptx)).slides:
        for sh in s.shapes:
            if sh.has_table:
                out.append([[c.text_frame.text for c in r.cells] for r in sh.table.rows])
            elif sh.has_text_frame:
                out.append(sh.text_frame.text)
    return out


def generar(br, unit, per, idx, libro, metas=None):
    bridge, service = br
    rid = call(bridge, "POST", "/api/runs", {"unit": unit, "periodicity": per, "year": 2026, "index": idx})["json"]["id"]
    assert call(bridge, "POST", f"/api/runs/{rid}/file", up=libro)["status"] == 200
    if metas:
        call(bridge, "PUT", f"/api/runs/{rid}/targets", metas)
    an = call(bridge, "GET", f"/api/runs/{rid}/analysis")["json"]
    g = call(bridge, "POST", f"/api/runs/{rid}/generate", {})
    assert g["status"] == 200, (g, [f["id"] for f in an["findings"] if f["severity"] == "block"])
    hs = call(bridge, "GET", f"/api/runs/{rid}/plan")["json"]["qa_integral"]["hallazgos"]
    return an, hs, textos(next((service._dir(rid) / "out").glob("*.pptx")))


CASOS = [
    ("aetops", "mensual", 9, "AETOPS_crudo_ejemplo.xlsx", {"total": "12000000"}, {"ventas": ["sku"], "catalogo": ["sku"], "negados": ["sku"]}),
    ("glp1", "mensual", 9, "GLP1_crudo_ejemplo.xlsx", None, {"ventas": ["sku"], "catalogo": ["sku"]}),
]


@pytest.mark.parametrize("unit,per,idx,nombre,metas,columnas", CASOS, ids=["aetops", "glp1"])
def test_codigos_numericos_dan_el_mismo_reporte_que_codigos_de_texto_y_sin_advertencias_de_cifras(br, tmp_path, unit, per, idx, nombre, metas, columnas):
    variante = con_codigos_numericos(EJ / nombre, tmp_path / "variante.xlsx", columnas)
    an0, hs0, t0 = generar(br, unit, per, idx, EJ / nombre, metas)
    an1, hs1, t1 = generar(br, unit, per, idx, variante, metas)
    assert t1 == t0                                                                      # mismas tablas y textos: los códigos no llevan «.0»
    assert not [h for h in hs1 if h["id"] == "PPTX_CIFRA_NO_TRAZADA"] and [h["id"] for h in hs1] == [h["id"] for h in hs0]
    assert not [f for f in an1["findings"] if f["id"].startswith("RAW_SKU")]
    assert not [x for x in re.findall(r"\b\d{5}\.0\b", json.dumps(t1))]                   # ningún código de 5 cifras termina en «.0»


def test_catalogo_de_texto_y_ventas_con_numeros_coinciden(br, tmp_path):
    """Antes de la corrección: «24369» (catálogo) y «24369.0» (ventas) eran SKU distintos y el reporte se bloqueaba por «SKU que no está en el catálogo»."""
    variante = con_codigos_numericos(EJ / "AETOPS_crudo_ejemplo.xlsx", tmp_path / "mixto.xlsx", {"ventas": ["sku"]})
    an, hs, t = generar(br, "aetops", "mensual", 9, variante, {"total": "12000000"})
    assert an["can_generate"] is True and not [f for f in an["findings"] if f["id"] == "RAW_SKU_NOT_IN_CATALOG"]


def test_csv_con_codigos_exportados_desde_numeros(br, tmp_path):
    """Una carpeta de CSV cuyos SKU salieron de números («24369.0») se lee igual que la del ejemplo."""
    import csv
    carpeta = tmp_path / "csv"
    carpeta.mkdir()
    wb = openpyxl.load_workbook(EJ / "AETOPS_crudo_ejemplo.xlsx", read_only=True, data_only=True)
    for hoja in wb.sheetnames:
        with (carpeta / f"{hoja}.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            for i, fila in enumerate(wb[hoja].iter_rows(values_only=True)):
                cab = i == 0
                w.writerow([("" if v is None else v) if cab else (f"{v}.0" if isinstance(v, str) and v.isdigit() and len(v) == 5 else ("" if v is None else v)) for v in fila])
    from backend.app.raw import aetops as raw
    t = raw.load(carpeta)
    assert t.ventas[0]["sku"].isdigit() and t.catalogo[0]["sku"].isdigit() and "." not in t.ventas[0]["sku"]
    assert not [x for x in t.findings if x.severity == "block"]
