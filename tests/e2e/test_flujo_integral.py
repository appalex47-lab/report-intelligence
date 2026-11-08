"""Flujo integrado en un navegador real (Chromium) con el motor REAL en Pyodide: escenario → generar → vista previa → QA → cambio (obsoleto) → regenerar →
caso bloqueante → corrección → descarga. No corre en CI (necesita Pyodide completo, Playwright y las plantillas, que no se versionan): se omite con motivo.
Variables: REPORT_PYODIDE_DIR (distribución de Pyodide 0.27.x), REPORT_WHEELS_DIR (opcional)."""
import functools
import http.server
import json
import os
import shutil
import subprocess
import sys
import threading
import zipfile
from pathlib import Path

import pytest

from tests.e2e import _sitio as S

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = Path(__file__).with_name("flujo_integral.mjs")
LIBRO = ROOT / "data" / "ejemplos" / "AETOPS_crudo_ejemplo.xlsx"


_omitir = S.omitir


@pytest.fixture(scope="module")
def resultado(tmp_path_factory):
    s = S.construir(tmp_path_factory)
    salida = tmp_path_factory.mktemp("salida")
    res = S.ejecutar(s, SCRIPT, str(LIBRO), str(salida), "9")
    res["_salida"] = salida
    res["_navegador"], res["_plantillas"] = s.navegador, s.plantillas
    return res



def test_el_recorrido_completo_termina_bien_y_sin_errores_de_consola(resultado):
    assert resultado["ok"], resultado
    assert not [c for c in resultado["consola"] if c.startswith(("error", "pageerror"))], resultado["consola"]


def test_escenario_y_etapas_visibles_antes_de_generar(resultado):
    e = resultado["pasos"]["escenario"]
    assert e["seleccionado"] == "aetops-mensual" and e["adaptativo"] is True
    assert set(e["opciones"]) >= {"aetops-mensual", "aetops-trimestral", "glp1-mensual", "glp1-trimestral"}
    assert len(e["etapas"]) == 6 and "Escenario" in e["etapas"][0]


def test_reporte_valido_vista_previa_calidad_y_exportacion_habilitada(resultado):
    g = resultado["pasos"]["generado"]
    assert not g["obsoleto"] and g["dlHabilitado"] and g["errores"] == 0
    assert "QA aprobado" in g["banner"] and "Revisión estructural" in g["banner"]
    assert g["diapositivas"] == 13 and g["formasDibujadas"] >= 4                       # la vista previa dibuja de verdad
    assert any("Exportación habilitada" in x for x in g["etapas"]) and any("Vista previa" in x for x in g["etapas"])


def test_navegacion_de_la_vista_previa(resultado):
    n = resultado["pasos"]["navegacion"]
    assert (n["k0"], n["k1"], n["k2"], n["k3"]) == ("0", "1", "0", "3")
    assert n["texto_diapositiva"].strip() and n["tablaDibujada"] is True                  # la diapositiva 4 trae una tabla y se dibuja


def test_un_cambio_despues_de_generar_invalida_la_vista_previa_el_qa_y_la_descarga(resultado):
    o = resultado["pasos"]["obsoleto"]
    assert o["obsoleto"] and not o["dlHabilitado"] and o["previewVisible"] is False


def test_regenerar_deja_los_resultados_vigentes_y_el_escenario_llega_al_reporte(resultado):
    r = resultado["pasos"]["regenerado"]
    assert not r["obsoleto"] and r["dlHabilitado"] and r["diapositivas"] == 13
    assert r["contextoEnVistaPrevia"] is True                                         # el contexto de negocio del escenario controla el contenido


def test_un_error_bloqueante_bloquea_la_exportacion_pero_no_oculta_la_vista_previa(resultado):
    b = resultado["pasos"]["bloqueado"]
    assert b["escenario"] == "exige-engagement"
    assert "QA rechazado" in b["banner"] and "QA_FALTA_TIPO_OBLIGATORIO" in b["hallazgos"] and b["errores"] >= 1
    assert not b["dlHabilitado"] and "Descarga bloqueada" in b["descargaIntentada"]
    assert b["diapositivas"] == 13                                                    # sigue habiendo vista previa para corregir


def test_corregido_el_problema_se_reejecuta_el_qa_y_se_habilita(resultado):
    c = resultado["pasos"]["corregido"]
    assert "QA aprobado" in c["banner"] and c["dlHabilitado"] and c["errores"] == 0, c


def test_el_pptx_descargado_es_valido_y_coincide_con_lo_previsualizado(resultado):
    assert resultado["nombre"].lower().endswith(".pptx") and resultado["primeros_bytes"] == "504b0304"
    ruta = Path(resultado["ruta"])
    with zipfile.ZipFile(ruta) as z:
        assert z.testzip() is None
    from pptx import Presentation
    assert len(Presentation(str(ruta)).slides) == resultado["pasos"]["corregido"]["diapositivas"] == 13
