"""Fase 5 · compatibilidad de libros y plantillas (encargo 3.5). Libros de EJEMPLO sintéticos y variantes estructurales; las plantillas reales no se versionan:
las pruebas que las necesitan se OMITEN con motivo si faltan.

Garantías: columnas adicionales y en otro orden, y hojas en otro orden, NO cambian el resultado del motor (se compara el resultado canónico completo);
las hojas opcionales ausentes y los datos incompletos se comunican con mensajes claros y controlados (nunca una excepción técnica ni un reporte engañoso);
una plantilla que no corresponde se rechaza al cargarla, con el motivo.
"""
from __future__ import annotations

import io
import shutil
import sys
import zipfile
from pathlib import Path

import openpyxl
import pytest
from pptx import Presentation

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from backend.app.build import ReportBlocked, build_aetops, build_glp1  # noqa: E402
from backend.app.deck.aetops_mensual import DataMissing, TemplateMismatch  # noqa: E402
from backend.app.models import Period  # noqa: E402
from backend.app.pipeline import run_aetops_raw, run_glp1_raw  # noqa: E402
from tools.capture_baseline import canon  # noqa: E402

EJ = ROOT / "data" / "ejemplos"
PG, PA = Period("GLP1", "mensual", 2026, 9), Period("AETOPS", "mensual", 2026, 9)
TPL = {"g": ROOT / "templates/glp1-mensual/1/template.pptx", "a": ROOT / "templates/aetops-mensual/1/template.pptx"}


def col(ws, nombre):
    return [str(c.value).strip().lower() if c.value is not None else "" for c in ws[1]].index(nombre) + 1


def variante(tmp_path, src, fn, nombre="v.xlsx"):
    p = tmp_path / nombre
    shutil.copy(EJ / src, p)
    wb = openpyxl.load_workbook(p)
    fn(wb)
    wb.save(p)
    return p


def extra_al_inicio(wb):
    for ws in wb.worksheets:
        ws.insert_cols(1)
        ws.cell(1, 1).value = "columna_adicional"
        ws.cell(2, 1).value = "x"


def invertir_columnas(wb):
    """Invierte el orden de las columnas moviendo cada celda CON su formato (si no, una fecha quedaría en una columna sin formato de fecha y el libro se corrompería)."""
    for ws in wb.worksheets:
        n = ws.max_column
        celdas = [[(c.value, c.number_format) for c in fila] for fila in ws.iter_rows(max_col=n)]
        for i, fila in enumerate(celdas, 1):
            for j, (v, fmt) in enumerate(reversed(fila), 1):
                ws.cell(i, j).value = v
                ws.cell(i, j).number_format = fmt


def hojas_al_reves(wb):
    wb._sheets.reverse()


def motor(unidad, libro):
    return (run_glp1_raw(libro, PG) if unidad == "g" else run_aetops_raw(libro, PA))


def sin_linaje(o):
    """Quita el linaje (`src`: archivo, hoja y celdas de origen): cambia legítimamente al desplazar columnas o renombrar el archivo. Los valores y estados se comparan completos."""
    if isinstance(o, dict):
        return {k: sin_linaje(v) for k, v in o.items() if k != "src"}
    if isinstance(o, list):
        return [sin_linaje(v) for v in o]
    return o


def resultado(unidad, res):
    if unidad == "g":
        return sin_linaje(canon({"blocks": res.blocks, "funnel": res.funnel, "extras": res.extras}))
    return sin_linaje(canon({"tables": res.tables, "products": res.products, "negados": res.negados, "extras": res.extras}))


LIBROS = {"g": "GLP1_crudo_ejemplo.xlsx", "a": "AETOPS_crudo_ejemplo.xlsx"}
VARIANTES = {"columna adicional al inicio": extra_al_inicio, "columnas en orden inverso": invertir_columnas, "hojas en otro orden": hojas_al_reves}


@pytest.fixture(scope="module")
def base():
    return {u: resultado(u, motor(u, EJ / LIBROS[u])) for u in LIBROS}


@pytest.mark.parametrize("unidad", ["g", "a"])
@pytest.mark.parametrize("nombre", sorted(VARIANTES))
def test_variantes_estructurales_no_cambian_el_resultado_del_motor(tmp_path, base, unidad, nombre):
    res = motor(unidad, variante(tmp_path, LIBROS[unidad], VARIANTES[nombre]))
    assert res.can_generate and not [f for f in res.findings if f.severity == "block"]
    assert resultado(unidad, res) == base[unidad]                    # idéntico al libro original, valor por valor


@pytest.mark.parametrize("unidad", ["g", "a"])
def test_encabezados_con_mayusculas_y_espacios_se_leen_igual(tmp_path, base, unidad):
    def f(wb):
        for ws in wb.worksheets:
            for c in ws[1]:
                if c.value:
                    c.value = f"  {str(c.value).upper()} "
    res = motor(unidad, variante(tmp_path, LIBROS[unidad], f))
    assert res.can_generate and resultado(unidad, res) == base[unidad]


@pytest.mark.parametrize("unidad,hoja,id_", [("g", "ventas", "RAW_TABLE_MISSING"), ("a", "ventas", "RAW_TABLE_MISSING"), ("a", "catalogo", "RAW_TABLE_MISSING")])
def test_hoja_obligatoria_ausente_bloquea_con_mensaje_claro(tmp_path, unidad, hoja, id_):
    res = motor(unidad, variante(tmp_path, LIBROS[unidad], lambda wb: wb.__delitem__(hoja)))
    bloqueos = [f for f in res.findings if f.severity == "block"]
    assert not res.can_generate and any(f.id == id_ and hoja in f.message for f in bloqueos)


@pytest.mark.parametrize("unidad,hoja,columna", [("g", "ventas", "monto_venta"), ("g", "ventas", "sku"), ("a", "ventas", "fecha_pedido"), ("a", "catalogo", "linea")])
def test_columna_obligatoria_ausente_bloquea_y_la_nombra(tmp_path, unidad, hoja, columna):
    res = motor(unidad, variante(tmp_path, LIBROS[unidad], lambda wb: wb[hoja].delete_cols(col(wb[hoja], columna))))
    assert not res.can_generate and any(f.id == "RAW_COLUMN_MISSING" and columna in f.message for f in res.findings)


def test_columna_opcional_ausente_no_bloquea(tmp_path):
    res = motor("g", variante(tmp_path, LIBROS["g"], lambda wb: wb["ventas"].delete_cols(col(wb["ventas"], "programa_lealtad"))))
    assert res.can_generate


@pytest.mark.parametrize("unidad", ["g", "a"])
def test_periodo_sin_datos_bloquea_con_mensaje_y_no_genera_cifras(unidad):
    per = Period("GLP1" if unidad == "g" else "AETOPS", "mensual", 2024, 3)
    res = (run_glp1_raw if unidad == "g" else run_aetops_raw)(EJ / LIBROS[unidad], per)
    assert not res.can_generate and any(f.id == "RAW_PERIOD_EMPTY" for f in res.findings)


def test_libro_ilegible_da_error_controlado_en_el_servicio(tmp_path, monkeypatch):
    import importlib
    monkeypatch.setenv("REPORT_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("REPORT_HISTORY_DB", str(tmp_path / "h.sqlite"))
    from backend.app.web import service
    importlib.reload(service)
    rid = service.create_run("glp1", "mensual", 2026, 9)["id"]
    for nombre, datos in (("a.txt", b"hola"), ("a.xlsx", b"no es un excel"), ("a.xlsx", b"PK\x03\x04roto")):
        with pytest.raises(service.ServiceError):
            service.store_file(rid, nombre, datos)


# --------------------------------------------------------------------------------------------- plantillas
def _requiere(clave):
    if not TPL[clave].exists():
        pytest.skip("OMITIDA (no ejecutada): la plantilla real no se versiona y no está disponible")


@pytest.mark.parametrize("unidad", ["g", "a"])
@pytest.mark.parametrize("nombre", sorted(VARIANTES))
def test_el_deck_es_igual_con_variantes_estructurales(tmp_path, unidad, nombre):
    """Con la plantilla real: las variantes de estructura producen el MISMO texto en cada diapositiva que el libro original."""
    _requiere(unidad)
    def textos(libro, out):
        res = motor(unidad, libro)
        b = (build_glp1 if unidad == "g" else build_aetops)(res, PG if unidad == "g" else PA, TPL[unidad], out, render=False)
        prs = Presentation(b.pptx)
        return [[sh.text_frame.text for sh in s.shapes if sh.has_text_frame] for s in prs.slides], b
    original, _ = textos(EJ / LIBROS[unidad], tmp_path / "o")
    otra, b = textos(variante(tmp_path, LIBROS[unidad], VARIANTES[nombre]), tmp_path / "v")
    assert otra == original and b.qa.passed


def test_glp1_sin_hojas_opcionales_pide_los_bloques_que_faltan(tmp_path):
    _requiere("g")
    for hoja in ("negados", "trafico"):
        res = motor("g", variante(tmp_path, LIBROS["g"], lambda wb, h=hoja: wb.__delitem__(h), f"s_{hoja}.xlsx"))
        with pytest.raises(DataMissing) as e:
            build_glp1(res, PG, TPL["g"], tmp_path / f"o_{hoja}", render=False)
        assert "Faltan bloques" in str(e.value)                       # mensaje controlado, no una excepción técnica


def test_aetops_sin_negados_no_se_entrega_como_aprobado(tmp_path):
    """Sin `negados` el deck conserva cifras viejas de la plantilla: el QA lo detecta (STALE_DATA) y la descarga queda bloqueada."""
    _requiere("a")
    res = motor("a", variante(tmp_path, LIBROS["a"], lambda wb: wb.__delitem__("negados")))
    b = build_aetops(res, PA, TPL["a"], tmp_path / "o", render=False)
    assert not b.qa.passed and any(i.id == "STALE_DATA" for i in b.qa.issues)


def test_plantilla_con_una_diapositiva_menos_da_error_controlado(tmp_path):
    _requiere("a")
    prs = Presentation(TPL["a"])
    ids = prs.slides._sldIdLst
    sl = list(ids)[2]
    prs.part.drop_rel(sl.rId)
    ids.remove(sl)
    prs.save(tmp_path / "t.pptx")
    res = motor("a", EJ / LIBROS["a"])
    with pytest.raises(TemplateMismatch) as e:
        build_aetops(res, PA, tmp_path / "t.pptx", tmp_path / "o", render=False)
    assert "plantilla" in str(e.value).lower()


@pytest.fixture()
def servicio(tmp_path, monkeypatch):
    import importlib
    monkeypatch.setenv("REPORT_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("REPORT_HISTORY_DB", str(tmp_path / "h.sqlite"))
    from backend.app.web import service
    importlib.reload(service)
    monkeypatch.setattr(service, "TEMPLATES_DIR", tmp_path / "plantillas")
    return service


def test_al_cargar_una_plantilla_se_rechaza_la_que_no_corresponde_con_el_motivo(servicio, tmp_path):
    for nombre, datos, motivo in (("t.txt", b"hola", "debe ser un .pptx"), ("t.pptx", b"PKroto", "dañado"), ("t.pptx", b"hola", "debe ser un .pptx")):
        with pytest.raises(servicio.ServiceError) as e:
            servicio.save_template("aetops-mensual", nombre, datos)
        assert motivo in str(e.value)
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("hola.txt", "x")
    with pytest.raises(servicio.ServiceError) as e:
        servicio.save_template("aetops-mensual", "t.pptx", b.getvalue())
    assert "no es una presentación" in str(e.value)
    ajena = io.BytesIO()
    Presentation().save(ajena)
    with pytest.raises(servicio.ServiceError) as e:
        servicio.save_template("aetops-mensual", "t.pptx", ajena.getvalue())
    assert "no corresponde" in str(e.value) and "diapositivas" in str(e.value)
    with pytest.raises(servicio.ServiceError):
        servicio.save_template("formato-inexistente", "t.pptx", b"PK")


def test_la_unica_version_de_plantilla_es_la_1():
    """«Plantillas anteriores»: el repositorio solo conoce la versión 1 de cada formato; no hay versiones previas contra las cuales probar compatibilidad."""
    versiones = {p.parent.name for p in (ROOT / "templates").glob("*/*/template.pptx")}
    assert versiones <= {"1"}
