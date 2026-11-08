"""Fase 6 · diseño adaptativo de la interfaz: 10 pantallas medidas en 5 anchos (1280, 1024, 768, 390 y 320 px) en Chromium con Pyodide real. Comprueba lo medible por
máquina (sin desborde horizontal, nada fuera del área visible, tablas contenidas, controles táctiles de al menos 24 px, sin texto diminuto ni controles recortados); no juzga la
estética. No corre en CI (necesita Pyodide, Playwright y plantillas): se omite con motivo. Variables: REPORT_PYODIDE_DIR, REPORT_WHEELS_DIR (opcional)."""
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
SCRIPT = Path(__file__).with_name("responsivo.mjs")
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



ANCHOS = ("escritorio", "portatil", "tablet", "movil", "movil_pequeno")
PANTALLAS = ("1_cargar_vacio", "2_cargar_con_libro", "3_validar", "4_metas_y_contexto", "5_narrativa", "6_generar_antes", "7_generar_resultado",
             "8_generar_desactualizado", "9_historial", "10_plantillas")


def _medidas(resultado):
    assert resultado["ok"], resultado
    assert not resultado["consola"], resultado["consola"]
    assert set(resultado["pantallas"]) == set(PANTALLAS)
    for pant, anchos in resultado["pantallas"].items():
        assert set(anchos) == set(ANCHOS), pant
        for ancho, m in anchos.items():
            yield pant, ancho, m


def test_ninguna_pantalla_tiene_desplazamiento_horizontal_de_pagina_en_ningun_ancho(resultado):
    malas = [(p, a, m["scrollW"], m["ancho"]) for p, a, m in _medidas(resultado) if m["desborde_horizontal"]]
    assert not malas, malas


def test_ningun_elemento_queda_fuera_del_area_visible(resultado):
    malas = [(p, a, m["fuera"]) for p, a, m in _medidas(resultado) if m["n_fuera"]]
    assert not malas, malas


def test_las_tablas_caben_o_se_desplazan_dentro_de_su_contenedor(resultado):
    malas = [(p, a, m["tablas_que_no_caben"]) for p, a, m in _medidas(resultado) if m["n_tablas"]]
    assert not malas, malas


def test_los_controles_tactiles_miden_al_menos_24_px_en_tablet_y_movil(resultado):
    malas = [(p, a, m["tactiles_pequenos"]) for p, a, m in _medidas(resultado) if a in ("tablet", "movil", "movil_pequeno") and m["n_tactiles"]]
    assert not malas, malas


def test_sin_texto_diminuto_ni_controles_recortados(resultado):
    malas = [(p, a, m["texto_diminuto"], m["recortados"]) for p, a, m in _medidas(resultado) if m["n_diminutos"] or m["n_recortados"]]
    assert not malas, malas


def test_se_generan_las_capturas_de_tablet_y_movil_de_cada_pantalla(resultado):
    assert len(list(Path(resultado["_salida"]).glob("*.png"))) == 2 * len(PANTALLAS)
