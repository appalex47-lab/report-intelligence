"""Fase 4 · el panel de escenarios E1/E2 e IND-01 se ve y se entiende en un navegador real con el motor real (Pyodide).

Sigue el patrón de `test_descarga_pptx.py`: si falta un requisito (Pyodide, Node + Playwright) la prueba se OMITE con el motivo; nunca se da por
aprobada sin ejecutarse. No requiere plantillas PPTX: solo llega al paso «Validar». En CI con `REPORT_PYODIDE_REQUIRED=1` la omisión es un fallo.
"""
from __future__ import annotations

import functools
import http.server
import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from tests.e2e import _sitio as S

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = Path(__file__).with_name("escenarios_panel.mjs")
EJEMPLOS = ROOT / "data" / "ejemplos"


_omitir = S.omitir


@pytest.fixture(scope="module")
def sitio(tmp_path_factory):
    s = S.construir(tmp_path_factory)
    yield s.url, s.npm_root



def _correr(sitio, tmp_path, unidad, libro):
    url, npm_root = sitio
    env = {**os.environ, "NODE_PATH": str(npm_root), "PLAYWRIGHT_REQUIRE_FROM": str(npm_root) + "/"}
    r = subprocess.run(["node", str(SCRIPT), url, str(libro), str(tmp_path), unidad, "9"], capture_output=True, text=True, env=env, timeout=900)
    linea = next((ln for ln in r.stdout.splitlines() if ln.startswith("RESULTADO ")), None)
    assert linea, f"el script no devolvió resultado:\n{r.stdout[-800:]}\n{r.stderr[-800:]}"
    res = json.loads(linea[len("RESULTADO "):])
    assert res["ok"], res
    assert not [c for c in res["consola"] if c.startswith(("error", "pageerror"))], res["consola"]      # sin errores de consola
    assert not [x for x in res["red"] if "favicon" not in x], res["red"]                              # sin recursos caídos (el sitio incluye las plantillas, reales o sintéticas)
    assert res["paso_validar_visible"] and res["hay_boton_continuar"]                                     # el flujo normal sigue disponible
    return res


def test_panel_glp1_muestra_e1_e2_ind01_supuestos_fuentes_y_advertencias(sitio, tmp_path):
    res = _correr(sitio, tmp_path, "glp1", EJEMPLOS / "GLP1_crudo_ejemplo.xlsx")
    t = res["panel_texto"]
    assert res["escenarios"] == ["E1", "E2"] and res["tiene_comparacion"] == 1 and res["tiene_ind01"] == 1
    assert sorted(res["fuentes"]) == ["ga4_compras", "sistema_ventas"]                                    # las dos fuentes, por separado
    for esperado in ("Supuesto heredado, no validado", "Comparación E1 vs. E2", "Relación pedidos (sistema de ventas) / carritos agregados",
                     "Relación compras GA4 / carritos agregados", "12.48", "14.00", "unidad no declarada", "NO VERIFICABLE", "no se suman",
                     "ilustrativos", "Pendientes de validación", "carritos_abandonados"):
        assert esperado.lower() in t.lower() or esperado.replace(".", ",") in t, f"falta en el panel: {esperado}"
    for prohibida in ("carritos abandonados comprobados", "usuarios que abandonaron el carrito", "carritos únicos"):
        assert prohibida not in t.lower()


def test_panel_aetops_declara_que_e2_e_ind01_no_aplican_sin_trafico(sitio, tmp_path):
    res = _correr(sitio, tmp_path, "aetops", EJEMPLOS / "AETOPS_crudo_ejemplo.xlsx")
    t = res["panel_texto"]
    assert res["escenarios"] == ["E1", "E2"] and res["fuentes"] == []
    assert t.lower().count("sin hoja `trafico`") >= 2 and "Supuesto heredado, no validado" in t


def test_panel_con_libros_en_formato_antiguo_no_inventa_cifras(sitio, tmp_path):
    """Formato por bloques (no crudo): el panel aparece, no rompe el flujo y declara lo que no puede calcular."""
    from tests.fixtures import build_base
    res = _correr(sitio, tmp_path, "glp1", ROOT / "data" / "GLP1_sintetico_limpio.xlsx")
    t = res["panel_texto"]
    assert res["escenarios"] == ["E1", "E2"] and res["fuentes"] == [] and res["tiene_comparacion"] == 1
    assert "No verificable" in t and "no es de datos crudos" in t and "Supuesto heredado, no validado" in t
    res2 = _correr(sitio, tmp_path, "aetops", build_base(tmp_path / "base_antigua.xlsx"))
    assert res2["escenarios"] == ["E1", "E2"] and res2["fuentes"] == [] and "sin hoja `trafico`" in res2["panel_texto"].lower()


def test_anexo_de_calidad_visible_con_15_dimensiones_y_origen_nunca_real(sitio, tmp_path):
    """Fase 5: el anexo aparece en el paso «Validar», con sus 15 dimensiones, el origen inferido del libro y sin afirmar que sean datos reales."""
    res = _correr(sitio, tmp_path, "glp1", EJEMPLOS / "GLP1_crudo_ejemplo.xlsx")
    assert res["anexo_presente"] == 1 and len(res["anexo_dimensiones"]) == 15 and res["anexo_origen"] == ["ejemplo_o_sintetico_inferido"]
    t = res["anexo_texto"]
    for esperado in ("Anexo de calidad de datos", "Origen de los datos", "ejemplo o sintético", "no son resultados de producción", "Calidad estructural",
                     "Consistencia entre fuentes", "Datos no verificables", "Supuestos y limitaciones", "No verificable"):
        assert esperado in t, esperado
    assert "son datos reales" not in t                                                       # nunca afirma que sean reales
    aet = _correr(sitio, tmp_path, "aetops", EJEMPLOS / "AETOPS_crudo_ejemplo.xlsx")
    assert aet["anexo_presente"] == 1 and len(aet["anexo_dimensiones"]) == 15
    leg = _correr(sitio, tmp_path, "glp1", ROOT / "data" / "GLP1_sintetico_limpio.xlsx")
    assert leg["anexo_presente"] == 1 and "no evaluable" in leg["anexo_texto"] and leg["anexo_origen"] == ["ejemplo_o_sintetico_inferido"]       # el nombre «sintetico» lo delata; si no, quedaría «no_declarado»
