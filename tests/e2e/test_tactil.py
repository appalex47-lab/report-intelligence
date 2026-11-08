"""Fase 6 · interacción táctil (contexto de pantalla táctil de 390 × 844) en el navegador real con Pyodide: el flujo completo, la vista previa, las casillas, los plegables y las pestañas funcionan solo con toques.
Es emulación del motor del navegador: no sustituye una prueba en un dispositivo físico. Ver tests/e2e/_sitio.py para las variables de entorno."""
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
SCRIPT = Path(__file__).with_name("tactil.mjs")
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


def test_el_recorrido_tactil_termina_sin_errores(resultado):
    assert resultado["ok"], resultado
    assert not resultado["consola"], resultado["consola"]
    assert resultado["pasos"]["es_tactil"]["maxTouchPoints"] > 0


def test_los_toques_avanzan_el_flujo_hasta_generar(resultado):
    p = resultado["pasos"]
    assert (p["paso_validar"], p["paso_narrativa"], p["paso_generar"]) == (1, 3, 4)
    assert p["generado"]["descarga"] is True and p["generado"]["diapositivas"] == 13


def test_los_objetivos_tactiles_son_alcanzables_y_de_al_menos_24_px(resultado):
    malos = {k: v for k, v in resultado["objetivos"].items() if not v or not v["visible"] or min(v["w"], v["h"]) < 24}
    assert not malos, malos


def test_la_casilla_la_vista_previa_los_plegables_y_las_pestanas_responden_al_toque(resultado):
    p = resultado["pasos"]
    assert p["casilla"]["antes"] != p["casilla"]["despues"]
    assert (p["vista_previa"]["k0"], p["vista_previa"]["k1"], p["vista_previa"]["k2"], p["vista_previa"]["k3"]) == (0, 1, 0, 4)
    assert p["detalles_abierto"] is True
    assert p["pestana_historial"] == {"seleccionada": "true", "visible": True} and p["vuelta_a_reporte"] is True


def test_la_vista_previa_se_desplaza_en_lugar_de_desbordar_la_pagina(resultado):
    v = resultado["pasos"]["vista_previa_desplazable"]
    assert v["desplaza"] and v["ancho_diapositiva"] >= 700 and v["ancho_visible"] < v["ancho_diapositiva"]
    assert resultado["pasos"]["sin_desborde"] is True
