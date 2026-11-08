"""Persistencia de escenarios propios (PUT/DELETE + recarga) con Pyodide/SQLite reales y el IndexedDB real de Chromium.

Sigue el patrón de `test_descarga_pptx.py`: si falta un requisito (Pyodide, Node + Playwright) la prueba se OMITE con el motivo; nunca se da por
aprobada sin ejecutarse. No requiere plantillas ni libros. En CI con `REPORT_PYODIDE_REQUIRED=1` la omisión es un fallo.
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
SCRIPT = Path(__file__).with_name("persistencia_escenarios.mjs")


_omitir = S.omitir


@pytest.fixture(scope="module")
def sitio(tmp_path_factory):
    s = S.construir(tmp_path_factory, con_plantillas=False)
    yield s.url, s.npm_root



def test_un_escenario_propio_sobrevive_a_la_recarga_y_el_borrado_tambien(sitio):
    url, npm_root = sitio
    env = {**os.environ, "NODE_PATH": str(npm_root), "PLAYWRIGHT_REQUIRE_FROM": str(npm_root) + "/"}
    r = subprocess.run(["node", str(SCRIPT), url], capture_output=True, text=True, env=env, timeout=900)
    linea = next((ln for ln in r.stdout.splitlines() if ln.startswith("RESULTADO ")), None)
    assert linea, f"el script no devolvió resultado:\n{r.stdout[-800:]}\n{r.stderr[-800:]}"
    o = json.loads(linea[len("RESULTADO "):])
    assert o["ok"], o
    p = o["pasos"]
    assert "prueba-persistencia" not in p["inicial"]
    assert "prueba-persistencia" in p["tras_put"]
    assert "prueba-persistencia" in p["tras_recargar"], "el escenario propio se perdió al recargar (no se persistió el historial tras el PUT)"
    assert p["contenido"]["objetivo"] == "Objetivo propio" and p["contenido"]["origen"] == "usuario"
    assert "prueba-persistencia" not in p["tras_delete_y_recargar"], "el escenario borrado reapareció tras recargar"
    assert not o["consola"], o["consola"]
