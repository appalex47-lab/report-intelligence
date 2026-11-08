"""Fase 5 · T-11: QA ESTRUCTURAL del PPTX exportado (`backend/app/qa/pptx_export.py`; spec Fase 1 §7.A; AC-14, AC-15).

Un deck sintético LIMPIO (construido aquí con python-pptx; no usa plantillas ni datos reales) y variantes con UN defecto inyectado cada una: cada
defecto debe detectarse con su `id` y el deck limpio no debe producir ningún hallazgo (0 falsos positivos). Con plantillas locales (no versionadas)
se verifican además los 4 decks de referencia generados con los libros de ejemplo; sin ellas esa prueba se OMITE con el motivo.

Qué NO valida (declarado): trazabilidad de cifras, fórmulas derivadas, unidades y denominadores (ver el docstring del módulo): AC-14 queda PARCIAL.
"""
from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

import pytest
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
from pptx.util import Emu, Inches, Pt

from backend.app.qa import pptx_export as P
from backend.app.qa.checks import QAReport
from tests import plantillas as PL

ROOT = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------------------------- deck sintético
def _texto(slide, x, y, w, h, t, pt=12, nombre=None, fuente="Calibri"):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if nombre:
        tb.name = nombre
    p = tb.text_frame.paragraphs[0]
    r = p.add_run()
    r.text = t
    r.font.size = Pt(pt)
    r.font.name = fuente
    return tb


def deck_limpio(path: Path, con_grafica=True) -> Path:
    prs = Presentation()
    blank = prs.slide_layouts[6]
    s1 = prs.slides.add_slide(blank)
    _texto(s1, 0.5, 0.3, 9, 0.6, "Resumen ejecutivo del periodo", 24, "titulo")
    _texto(s1, 0.5, 1.2, 9, 1.0, "La venta del periodo fue de $12.22 M, +56% vs el mismo periodo del año anterior.", 14, "hecho")
    _texto(s1, 0.5, 2.5, 9, 1.0, "Seguimiento: monto y pedidos negados cada mes durante el trimestre.", 14, "seguimiento")
    s2 = prs.slides.add_slide(blank)
    _texto(s2, 0.5, 0.3, 9, 0.6, "Panorama general", 24, "titulo")
    tabla = s2.shapes.add_table(3, 3, Inches(0.5), Inches(1.2), Inches(6), Inches(1.5)).table
    for i, fila in enumerate((("Año", "Venta", "Pedidos"), ("2025", "$7.85 M", "927"), ("2026", "$12.22 M", "1,353"))):
        for j, v in enumerate(fila):
            tabla.cell(i, j).text = v
            tabla.cell(i, j).text_frame.paragraphs[0].runs[0].font.size = Pt(11)
            tabla.cell(i, j).text_frame.paragraphs[0].runs[0].font.name = "Calibri"
    if con_grafica:
        cd = CategoryChartData()
        cd.categories = ["Ago", "Sep"]
        cd.add_series("Venta", (11.1, 12.2))
        s2.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.5), Inches(3.2), Inches(5), Inches(3), cd)
    prs.save(path)
    return path


def reescribir(origen: Path, destino: Path, cambios=None, agregar=None, quitar=()):
    """Copia un PPTX aplicando cambios a nivel de ZIP: {parte: función(bytes)->bytes}, partes nuevas y partes a quitar."""
    cambios, agregar = cambios or {}, agregar or {}
    with zipfile.ZipFile(origen) as zi, zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as zo:
        for n in zi.namelist():
            if n in quitar:
                continue
            datos = zi.read(n)
            zo.writestr(n, cambios[n](datos) if n in cambios else datos)
        for n, d in agregar.items():
            zo.writestr(n, d)
    return destino


def ids(res) -> set[str]:
    return {i.id for i in res.issues}


def graves(res) -> set[str]:
    return {i.id for i in res.issues if i.severity in ("error", "warn")}


@pytest.fixture()
def limpio(tmp_path):
    return deck_limpio(tmp_path / "limpio.pptx")


# --------------------------------------------------------------------------------------------- deck limpio: 0 falsos positivos
def test_el_deck_limpio_no_produce_ningun_hallazgo(limpio):
    r = P.revisar(limpio)
    assert r.issues == [] and r.errores == []


def test_el_deck_limpio_con_su_propia_plantilla_tampoco(limpio):
    assert P.revisar(limpio, limpio).issues == []


def test_la_etiqueta_declara_que_es_estructural_y_no_visual():
    """AC-15: el informe nunca se presenta como revisión visual."""
    assert P.ETIQUETA == "Revisión estructural. La revisión visual requiere render."
    assert "verificado visualmente" not in P.ETIQUETA.lower() and P.ETIQUETA.lower().count("visual") == 1
    rep = QAReport()
    P.agregar_a(rep, deck_limpio(Path(__import__("tempfile").mkdtemp()) / "d.pptx"))
    assert any(i.id == "PPTX_REVISION_ESTRUCTURAL" and i.message == P.ETIQUETA and i.severity == "info" for i in rep.issues) and rep.passed


# --------------------------------------------------------------------------------------------- defectos de texto y formato
@pytest.mark.parametrize("texto", ["Valor: None", "Plantilla {{ventas}} sin llenar", "Importe Decimal(12.5)", "Campo RI_TOTAL", "KeyError: 'venta'", "Traceback (most recent call last)", "El valor es nan"])
def test_token_tecnico_se_detecta_y_bloquea(limpio, tmp_path, texto):
    prs = Presentation(limpio)
    _texto(prs.slides[0], 0.5, 4.5, 9, 0.5, texto)
    prs.save(tmp_path / "x.pptx")
    r = P.revisar(tmp_path / "x.pptx")
    assert "PPTX_TOKEN_TECNICO" in {i.id for i in r.errores}


@pytest.mark.parametrize("texto", ["Ninguna novedad", "Nanotecnología aplicada", "Resultado no nulo", "None"[:0] + "Nonato vendió 5"])
def test_palabras_legitimas_que_contienen_un_token_no_son_falsos_positivos(limpio, tmp_path, texto):
    prs = Presentation(limpio)
    _texto(prs.slides[0], 0.5, 4.5, 9, 0.5, texto)
    prs.save(tmp_path / "x.pptx")
    assert "PPTX_TOKEN_TECNICO" not in ids(P.revisar(tmp_path / "x.pptx"))


def test_texto_duplicado_en_dos_formas_se_detecta(limpio, tmp_path):
    prs = Presentation(limpio)
    t = "Los negados equivalen a una fracción relevante de la venta del periodo."
    _texto(prs.slides[0], 0.5, 4.0, 9, 0.5, t, nombre="a")
    _texto(prs.slides[0], 0.5, 5.0, 9, 0.5, t, nombre="b")
    prs.save(tmp_path / "x.pptx")
    assert "PPTX_DUPLICADO" in {i.id for i in P.revisar(tmp_path / "x.pptx").errores}


def test_un_texto_corto_repetido_no_es_duplicado(limpio, tmp_path):
    prs = Presentation(limpio)
    _texto(prs.slides[0], 0.5, 4.0, 4, 0.5, "TOTAL")
    _texto(prs.slides[0], 5.0, 4.0, 4, 0.5, "TOTAL")
    prs.save(tmp_path / "x.pptx")
    assert "PPTX_DUPLICADO" not in ids(P.revisar(tmp_path / "x.pptx"))


def test_doble_espacio_se_detecta_y_el_heredado_de_la_plantilla_no(limpio, tmp_path):
    prs = Presentation(limpio)
    _texto(prs.slides[0], 0.5, 4.5, 9, 0.5, "Ventas  del periodo")
    prs.save(tmp_path / "x.pptx")
    assert "PPTX_TEXTO" in ids(P.revisar(tmp_path / "x.pptx"))
    assert "PPTX_TEXTO" not in ids(P.revisar(tmp_path / "x.pptx", tmp_path / "x.pptx"))        # si la plantilla ya lo traía, no es del reporte


def test_fuente_menor_al_minimo_se_detecta_y_se_calibra_con_la_plantilla(limpio, tmp_path):
    prs = Presentation(limpio)
    _texto(prs.slides[0], 0.5, 4.5, 9, 0.5, "Nota al pie diminuta", pt=6)
    prs.save(tmp_path / "x.pptx")
    assert "PPTX_FUENTE_MIN" in {i.id for i in P.revisar(tmp_path / "x.pptx").errores}
    assert "PPTX_FUENTE_MIN" not in ids(P.revisar(tmp_path / "x.pptx", tmp_path / "x.pptx"))   # la plantilla ya usa 6 pt: umbral calibrado
    assert "PPTX_FUENTE_MIN" not in ids(P.revisar(tmp_path / "x.pptx", fuente_min=6.0))          # configurable
    assert "PPTX_FUENTE_MIN" in {i.id for i in P.revisar(limpio.parent / "x.pptx", limpio, fuente_min=9).errores}  # contra la plantilla limpia (11 pt mínimo ⇒ umbral 9)


def test_fuente_ajena_a_la_plantilla_se_detecta(limpio, tmp_path):
    prs = Presentation(limpio)
    _texto(prs.slides[0], 0.5, 4.5, 9, 0.5, "Texto con otra tipografía", fuente="Comic Sans MS")
    prs.save(tmp_path / "x.pptx")
    assert "PPTX_FUENTE_INCONSISTENTE" in ids(P.revisar(tmp_path / "x.pptx", limpio))
    assert "PPTX_FUENTE_INCONSISTENTE" not in ids(P.revisar(tmp_path / "x.pptx"))             # sin plantilla no hay familia de referencia


# --------------------------------------------------------------------------------------------- geometría
def test_forma_fuera_del_lienzo_se_detecta(limpio, tmp_path):
    prs = Presentation(limpio)
    _texto(prs.slides[0], 9.5, 4.5, 3, 0.5, "Me salgo del lienzo")
    prs.save(tmp_path / "x.pptx")
    assert "PPTX_FUERA_DE_LIENZO" in {i.id for i in P.revisar(tmp_path / "x.pptx").errores}


def test_forma_justo_en_el_borde_no_es_falso_positivo(limpio, tmp_path):
    prs = Presentation(limpio)
    t = _texto(prs.slides[0], 0, 0, 1, 1, "Borde")
    t.width, t.left = Emu(prs.slide_width), Emu(0)
    prs.save(tmp_path / "x.pptx")
    assert "PPTX_FUERA_DE_LIENZO" not in ids(P.revisar(tmp_path / "x.pptx"))


def test_recuadros_de_texto_casi_iguales_se_detectan_como_solape(limpio, tmp_path):
    prs = Presentation(limpio)
    _texto(prs.slides[0], 0.5, 4.5, 6, 1.0, "Primer recuadro con una explicación", nombre="uno")
    _texto(prs.slides[0], 0.6, 4.55, 6, 1.0, "Segundo recuadro distinto encima", nombre="dos")
    prs.save(tmp_path / "x.pptx")
    assert "PPTX_SOLAPE_DECLARADO" in ids(P.revisar(tmp_path / "x.pptx"))


def test_diapositiva_vacia_y_tabla_vacia(limpio, tmp_path):
    prs = Presentation(limpio)
    prs.slides.add_slide(prs.slide_layouts[6])
    t = prs.slides[1].shapes.add_table(2, 2, Inches(0.5), Inches(4), Inches(3), Inches(1))
    prs.save(tmp_path / "x.pptx")
    r = ids(P.revisar(tmp_path / "x.pptx"))
    assert "PPTX_DIAPOSITIVA_VACIA" in r and "PPTX_TABLA_VACIA" in r


# --------------------------------------------------------------------------------------------- paquete
def test_zip_ilegible_o_truncado_es_un_error_sin_lanzar(limpio, tmp_path):
    datos = limpio.read_bytes()
    (tmp_path / "t.pptx").write_bytes(datos[: len(datos) // 2])
    (tmp_path / "v.pptx").write_bytes(b"")
    (tmp_path / "h.pptx").write_bytes(b"<html>no soy un zip</html>")
    for n in ("t", "v", "h"):
        r = P.revisar(tmp_path / f"{n}.pptx")
        assert "PPTX_ZIP" in {i.id for i in r.errores}, n


def test_xml_mal_formado_se_detecta(limpio, tmp_path):
    destino = reescribir(limpio, tmp_path / "x.pptx", {"ppt/slides/slide1.xml": lambda b: b[: len(b) // 2]})
    r = P.revisar(destino)
    assert "PPTX_XML" in {i.id for i in r.errores} and not any(i.id == "PPTX_ZIP" and "python-pptx" in i.message for i in r.issues)


def test_relacion_rota_se_detecta(limpio, tmp_path):
    def romper(b):
        return re.sub(rb'Target="slides/slide2.xml"', b'Target="slides/slide99.xml"', b)
    destino = reescribir(limpio, tmp_path / "x.pptx", {"ppt/_rels/presentation.xml.rels": romper})
    assert "PPTX_REL_ROTA" in {i.id for i in P.revisar(destino).errores}


def test_parte_huerfana_se_advierte_y_la_heredada_de_la_plantilla_no(limpio, tmp_path):
    destino = reescribir(limpio, tmp_path / "x.pptx", agregar={"ppt/media/sobrante.png": b"\x89PNG\r\n\x1a\n" + b"0" * 20})
    r = P.revisar(destino)
    assert any(i.id == "PPTX_HUERFANO" and i.severity == "warn" and "sobrante.png" in i.message for i in r.issues)
    assert "PPTX_HUERFANO" not in ids(P.revisar(destino, destino))


def test_imagen_danada_se_detecta(limpio, tmp_path):
    from PIL import Image
    prs = Presentation(limpio)
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), "red").save(buf, "PNG")
    buf.seek(0)
    prs.slides[0].shapes.add_picture(buf, Inches(7), Inches(4), Inches(1), Inches(1))
    prs.save(tmp_path / "ok.pptx")
    assert "PPTX_IMAGEN" not in ids(P.revisar(tmp_path / "ok.pptx"))                          # imagen sana: 0 falsos positivos
    with zipfile.ZipFile(tmp_path / "ok.pptx") as z:
        media = next(n for n in z.namelist() if n.startswith("ppt/media/"))
    destino = reescribir(tmp_path / "ok.pptx", tmp_path / "mala.pptx", {media: lambda b: b[:30] + b"\x00" * 40})
    assert "PPTX_IMAGEN" in {i.id for i in P.revisar(destino).errores}
    sin_firma = reescribir(tmp_path / "ok.pptx", tmp_path / "sinfirma.pptx", {media: lambda b: b"NOESUNPNG" + b[9:]})
    assert "PPTX_IMAGEN" in {i.id for i in P.revisar(sin_firma).errores}


def test_grafica_sin_series_se_detecta_y_la_sana_no(limpio, tmp_path):
    assert "PPTX_GRAFICO_VACIO" not in ids(P.revisar(limpio))
    with zipfile.ZipFile(limpio) as z:
        chart = next(n for n in z.namelist() if re.fullmatch(r"ppt/charts/chart\d+\.xml", n))
    destino = reescribir(limpio, tmp_path / "x.pptx", {chart: lambda b: re.sub(rb"<c:ser>.*?</c:ser>", b"", b, flags=re.S)})
    assert "PPTX_GRAFICO_VACIO" in {i.id for i in P.revisar(destino).errores}


def test_grafica_vacia_heredada_de_la_plantilla_solo_informa(limpio, tmp_path):
    with zipfile.ZipFile(limpio) as z:
        chart = next(n for n in z.namelist() if re.fullmatch(r"ppt/charts/chart\d+\.xml", n))
    vacia = reescribir(limpio, tmp_path / "vacia.pptx", {chart: lambda b: re.sub(rb"<c:ser>.*?</c:ser>", b"", b, flags=re.S)})
    r = P.revisar(vacia, vacia)
    assert r.errores == [] and any(i.id == "PPTX_GRAFICO_VACIO" and i.severity == "info" for i in r.issues)


def test_entradas_duplicadas_y_rutas_inseguras_en_el_zip(limpio, tmp_path):
    destino = tmp_path / "x.pptx"
    with zipfile.ZipFile(limpio) as zi, zipfile.ZipFile(destino, "w") as zo:
        for n in zi.namelist():
            zo.writestr(n, zi.read(n))
        zo.writestr("ppt/../../escape.xml", b"<a/>")
    assert "PPTX_ZIP" in {i.id for i in P.revisar(destino).errores}


def test_xml_con_entidades_externas_no_se_resuelve(limpio, tmp_path):
    xxe = b'<?xml version="1.0"?><!DOCTYPE a [<!ENTITY x SYSTEM "file:///etc/passwd">]><a>&x;</a>'
    destino = reescribir(limpio, tmp_path / "x.pptx", agregar={"ppt/extra.xml": xxe})
    r = P.revisar(destino)                                                                    # no lanza, no lee archivos: a lo sumo informa XML inválido
    assert all("root:" not in i.message for i in r.issues)


def test_revisar_nunca_lanza_con_entradas_absurdas(tmp_path):
    assert "PPTX_ZIP" in ids(P.revisar(tmp_path / "no_existe.pptx"))
    assert "PPTX_ZIP" in ids(P.revisar(tmp_path))                                              # un directorio


# --------------------------------------------------------------------------------------------- integración con el QAReport
def test_agregar_a_marca_el_reporte_como_rechazado_solo_con_errores(limpio, tmp_path):
    ok = QAReport()
    P.agregar_a(ok, limpio)
    assert ok.passed
    prs = Presentation(limpio)
    _texto(prs.slides[0], 0.5, 4.5, 9, 0.5, "Valor: None")
    prs.save(tmp_path / "x.pptx")
    mal = QAReport()
    P.agregar_a(mal, tmp_path / "x.pptx")
    assert not mal.passed and any(i.id == "PPTX_TOKEN_TECNICO" for i in mal.issues)
    solo_aviso = QAReport()
    prs2 = Presentation(limpio)
    _texto(prs2.slides[0], 0.5, 4.5, 9, 0.5, "Ventas  del periodo")
    prs2.save(tmp_path / "y.pptx")
    P.agregar_a(solo_aviso, tmp_path / "y.pptx")
    assert solo_aviso.passed and any(i.id == "PPTX_TEXTO" for i in solo_aviso.issues)         # una advertencia no bloquea la descarga


def test_build_integra_la_revision_estructural():
    """La generación llama a la revisión tras guardar el PPTX y no puede fallar por ella."""
    src = (ROOT / "backend/app/build.py").read_text(encoding="utf-8")
    assert "pptx_export.agregar_a(qa, pptx, template)" in src and "PPTX_REVISION_NO_EJECUTADA" in src


# --------------------------------------------------------------------------------------------- decks de referencia reales (si hay plantillas)
ESCENARIOS = {"aetops_mensual_2026-09": "aetops-mensual", "aetops_trimestral_2026-Q3": "aetops-trimestral",
              "glp1_mensual_2026-09": "glp1-mensual", "glp1_trimestral_2026-Q3": "glp1-trimestral"}


@pytest.mark.parametrize("nombre", sorted(ESCENARIOS))
def test_decks_de_referencia_generados_no_tienen_hallazgos(nombre, tmp_path):
    """0 falsos positivos en decks reales de referencia (libros de EJEMPLO sintéticos + plantillas locales). Sin plantilla: omitida con motivo."""
    tpl = PL.ruta(ESCENARIOS[nombre])
    if not tpl.exists():
        pytest.skip(f"OMITIDA (no ejecutada): la plantilla {ESCENARIOS[nombre]} no se versiona y no está disponible")
    import sys
    sys.path.insert(0, str(ROOT))
    from tools.capture_baseline import _run
    from backend.app.build import build_aetops, build_glp1
    unit, period, _path, _tpl, res, _ = _run(nombre)
    b = (build_aetops if unit == "AETOPS" else build_glp1)(res, period, tpl, tmp_path, render=False)
    r = P.revisar(b.pptx, tpl)
    assert r.errores == [] and graves(r) == set(), [(i.id, i.message) for i in r.issues]
    assert any(i.id == "PPTX_REVISION_ESTRUCTURAL" for i in b.qa.issues) and b.qa.passed
    # y cada defecto inyectado en el deck real se detecta
    prs = Presentation(b.pptx)
    _texto(prs.slides[1], 0.2, 0.2, 3, 0.3, "Valor: None")
    _texto(prs.slides[1], 0.2, 0.6, 3, 0.3, "Letra diminuta", pt=4)
    prs.save(tmp_path / "defectuoso.pptx")
    assert {"PPTX_TOKEN_TECNICO", "PPTX_FUENTE_MIN"} <= {i.id for i in P.revisar(tmp_path / "defectuoso.pptx", tpl).errores}
