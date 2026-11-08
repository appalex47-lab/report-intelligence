"""Revisión visual reproducible del paso «Generar» (escritorio y 390 px): capturas y comprobaciones medibles. No sustituye la revisión humana (checklist en
BLOQUE_INTEGRAL.md §15). No corre en CI (necesita Pyodide completo, Playwright y las plantillas, que no se versionan): se omite con motivo.
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
SCRIPT = Path(__file__).with_name("revision_visual.mjs")
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



def test_sin_desborde_horizontal_en_escritorio_ni_en_pantalla_pequena(resultado):
    assert resultado["ok"], resultado
    for k, v in resultado["vistas"].items():
        assert not v["desborde_horizontal"], f"{k}: scrollWidth {v['scrollW']} > ancho {v['ancho']}"


def test_las_seis_etapas_el_escenario_y_el_boton_generar_son_visibles_antes_y_despues_de_generar(resultado):
    for k in ("antes_escritorio", "generado_escritorio", "generado_movil"):
        v = resultado["vistas"][k]
        assert len(v["etapas"]) == 6 and v["escenario"] and v["generar"], (k, v)


def test_la_vista_previa_la_lista_y_el_estado_de_descarga_aparecen_al_generar(resultado):
    g = resultado["vistas"]["generado_escritorio"]
    assert g["vista_previa"] and g["lista_diapositivas"] > 0 and g["descarga_habilitada"] is True
    assert resultado["vistas"]["generado_movil"]["vista_previa"]


def test_un_cambio_muestra_el_aviso_de_resultados_desactualizados_y_quita_la_descarga(resultado):
    for k in ("obsoleto_escritorio", "obsoleto_movil"):
        v = resultado["vistas"][k]
        assert v["banner_obsoleto"] and v["descarga_habilitada"] is False, (k, v)


def test_sin_errores_de_consola_y_con_las_cinco_capturas(resultado):
    assert not resultado["consola"], resultado["consola"]
    assert len(list(Path(resultado["_salida"]).glob("*.png"))) == 5


def test_con_resultados_desactualizados_el_recuadro_de_qa_se_ve_como_aviso_y_no_como_aprobado(resultado):
    """Corrección D-7: el veredicto del QA anterior ya no se muestra en verde junto a «descarga bloqueada». Los valores reales no cambian."""
    for k in ("obsoleto_escritorio", "obsoleto_movil"):
        v = resultado["vistas"][k]
        b = v["qa_banner"]
        assert b["estado"] == "desactualizado" and b["clase_warn"] and not b["clase_ok"] and not b["clase_bad"], (k, b)
        assert b["titulo"] == "QA del reporte anterior (desactualizado) · descarga bloqueada", b
        assert "aprobado" not in b["titulo"].lower().replace("desactualizado", "")
        r = v["valores_reales"]
        assert r["vigente"] is False and r["downloadable"] is False and r["qa_passed"] is True, (k, r)      # el estado real no se altera: solo cambia la presentación


def test_con_resultados_vigentes_el_recuadro_de_qa_sigue_igual(resultado):
    for k in ("generado_escritorio", "generado_movil"):
        v = resultado["vistas"][k]
        assert v["qa_banner"]["estado"] == "ok" and v["qa_banner"]["clase_ok"] and v["qa_banner"]["titulo"] == "QA aprobado · descarga habilitada", (k, v["qa_banner"])
        assert v["valores_reales"]["vigente"] is True and v["valores_reales"]["downloadable"] is True

