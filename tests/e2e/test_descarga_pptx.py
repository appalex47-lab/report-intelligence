"""Incidencia «Descargar PPTX» (paso 5): recorrido COMPLETO en un navegador con el motor real.

Abre la aplicación (el sitio se compila con `tools/build_site.py`), carga el libro sintético de AETOPS, avanza hasta el paso 5,
pulsa «Descargar PPTX», guarda el archivo y comprueba: extensión .pptx, firma `PK`, ZIP íntegro y que `python-pptx` lo abre con
diapositivas. No modifica `frontend/` ni instrumenta la aplicación.

Requisitos (si falta alguno la prueba se OMITE con el motivo; nunca se da por aprobada sin ejecutarse):
  * `REPORT_PYODIDE_DIR`: carpeta con una distribución completa de Pyodide 0.27.x (la misma versión que usa el worker). En CI no existe
    porque la CDN de Pyodide no es accesible desde todos los entornos; esta prueba se ejecuta localmente.
  * Node.js con el paquete `playwright` (global) y un Chromium instalado.
  * La plantilla real `templates/aetops-mensual/1/template.pptx` (no se versiona).
  * `REPORT_WHEELS_DIR` (opcional): carpeta con los .whl; si falta, `build_site.py` los descarga de PyPI.
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
import zipfile
from pathlib import Path

import pytest

from tests.e2e import _sitio as S

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = Path(__file__).with_name("descarga_pptx.mjs")
LIBRO = ROOT / "data" / "ejemplos" / "AETOPS_crudo_ejemplo.xlsx"


_omitir = S.omitir


@pytest.fixture(scope="module")
def sitio(tmp_path_factory):
    s = S.construir(tmp_path_factory)
    yield s.url, s.npm_root



def test_el_boton_descargar_pptx_entrega_un_pptx_valido_con_el_motor_real(sitio, tmp_path):
    url, npm_root = sitio
    env = {**os.environ, "NODE_PATH": str(npm_root), "PLAYWRIGHT_REQUIRE_FROM": str(npm_root) + "/"}
    r = subprocess.run(["node", str(SCRIPT), url, str(LIBRO), str(tmp_path), "9"], capture_output=True, text=True, env=env, timeout=900)
    linea = next((ln for ln in r.stdout.splitlines() if ln.startswith("RESULTADO ")), None)
    assert linea, f"el script no devolvió resultado:\n{r.stdout[-800:]}\n{r.stderr[-800:]}"
    res = json.loads(linea[len("RESULTADO "):])
    assert res["ok"], res
    assert res["boton_habilitado"] and "QA aprobado" in res["banner"]
    assert "Revisión estructural" in res["banner"] and "revisión visual requiere render" in res["banner"].lower() and "verificado visualmente" not in res["banner"].lower()   # AC-15
    assert res["nombre"].lower().endswith(".pptx")
    assert res["primeros_bytes"] == "504b0304"                                  # firma ZIP «PK\x03\x04»
    assert not [c for c in res["consola"] if c.startswith(("error", "pageerror"))], res["consola"]
    ruta = Path(res["ruta"])
    assert ruta.stat().st_size == res["bytes"] > 10_000
    with zipfile.ZipFile(ruta) as z:
        assert z.testzip() is None and "[Content_Types].xml" in z.namelist()      # ZIP íntegro
    from pptx import Presentation
    assert len(Presentation(str(ruta)).slides) >= 10                              # presentación abre y tiene diapositivas


def test_la_procedencia_generada_en_el_navegador_es_verificable(sitio, tmp_path):
    """Fase 3A-3 · con el motor real en Pyodide: `procedencia.json` existe, es válido, coincide con la fila del historial exportado y se verifica."""
    import base64
    import sqlite3
    from backend.app import provenance as pv
    from backend.app import provenance_verify as ver
    url, npm_root = sitio
    env = {**os.environ, "NODE_PATH": str(npm_root), "PLAYWRIGHT_REQUIRE_FROM": str(npm_root) + "/"}
    r = subprocess.run(["node", str(SCRIPT), url, str(LIBRO), str(tmp_path), "9"], capture_output=True, text=True, env=env, timeout=900)
    linea = next((ln for ln in r.stdout.splitlines() if ln.startswith("RESULTADO ")), None)
    assert linea, f"el script no devolvió resultado:\n{r.stdout[-800:]}\n{r.stderr[-800:]}"
    res = json.loads(linea[len("RESULTADO "):])
    assert res["ok"] and "procedencia_b64" in res, res
    datos = base64.b64decode(res["procedencia_b64"])
    m, errs = pv.leer_manifiesto(datos)
    assert errs == [] and m["archivos_fuente"][0]["nombre"] == "input.xlsx"
    assert m["entorno"]["pyodide"] != "desconocido" or m["entorno"]["python"]                 # el entorno real queda registrado
    assert "historial_b64" in res, res
    db = tmp_path / "historial.sqlite"
    db.write_bytes(base64.b64decode(res["historial_b64"]))
    rid = sqlite3.connect(db).execute("SELECT run_id FROM procedencia").fetchone()[0]
    v = ver.verificar(db, rid)
    assert v["integridad"] == "verificada" and v["registro"]["manifiesto_sha256"] == pv.sha256_hex(datos)
