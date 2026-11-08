"""Fase 8 · estabilización en el navegador real (Chromium + Pyodide): rendimiento, persistencia tras recargar e integridad del PPTX descargado. No corre en CI (necesita Pyodide,
Playwright y plantillas): se omite con motivo. Variables: REPORT_PYODIDE_DIR, REPORT_WHEELS_DIR (opcional)."""
import functools
import hashlib
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
SCRIPT = Path(__file__).with_name("estabilizacion_navegador.mjs")
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



def test_el_recorrido_termina_sin_errores_de_consola(resultado):
    assert resultado["ok"], resultado
    assert not resultado["consola"], resultado["consola"]


def test_rendimiento_dentro_de_los_limites_acordados_con_pyodide(resultado):
    """Límites generosos (≈3× lo medido) para detectar degradaciones graves, no para fijar un rendimiento exacto. Los tiempos reales quedan en el informe."""
    t = resultado["tiempos"]
    assert t["arranque_motor_s"] < 120, t
    assert t["carga_del_libro_s"] < 60, t
    assert t["analisis_s"] < 90, t
    assert t["generacion_s"] < 240, t


def test_el_historial_y_los_escenarios_propios_sobreviven_a_recargar_la_pagina(resultado):
    pers = resultado["persistencia"]
    mensuales = [r for r in pers["historial"] if r["unidad"] == "AETOPS" and r["periodicidad"] == "mensual" and r["anio"] == 2026 and r["indice"] == 9]
    assert mensuales, pers["historial"]
    assert pers["historial_visible"] is True
    assert "estabilizacion" in pers["escenarios"], pers["escenarios"]


def test_el_pptx_descargado_es_integro_y_coincide_con_el_manifiesto(resultado):
    d = resultado["descarga"]
    assert d["zip"] and d["bytes"] > 50_000 and d["nombre"].endswith(".pptx")
    assert d["sha256"] == resultado["manifiesto_sha256"]
    ruta = Path(resultado["_salida"]) / d["nombre"]
    assert hashlib.sha256(ruta.read_bytes()).hexdigest() == d["sha256"]
    from pptx import Presentation
    assert len(Presentation(str(ruta)).slides) == 13
