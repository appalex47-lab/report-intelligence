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

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = Path(__file__).with_name("persistencia_escenarios.mjs")


def _omitir(motivo: str):
    if os.environ.get("REPORT_PYODIDE_REQUIRED") == "1":
        pytest.fail(f"REPORT_PYODIDE_REQUIRED=1 y falta un requisito: {motivo}")
    pytest.skip(f"OMITIDA (no ejecutada): {motivo}")


@pytest.fixture(scope="module")
def sitio(tmp_path_factory):
    pyodide = os.environ.get("REPORT_PYODIDE_DIR")
    if not pyodide or not (Path(pyodide) / "pyodide.js").exists():
        _omitir("REPORT_PYODIDE_DIR no apunta a una distribución de Pyodide (pyodide.js)")
    if not shutil.which("node"):
        _omitir("Node.js no está instalado")
    npm_root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip() if shutil.which("npm") else ""
    if not npm_root or not (Path(npm_root) / "playwright").exists():
        _omitir("el paquete 'playwright' de Node no está instalado globalmente")
    site = tmp_path_factory.mktemp("sitio")
    cmd = [sys.executable, str(ROOT / "tools" / "build_site.py"), "--out", str(site)]
    if os.environ.get("REPORT_WHEELS_DIR"):
        cmd += ["--wheels", os.environ["REPORT_WHEELS_DIR"]]
    subprocess.run(cmd, check=True, cwd=ROOT, capture_output=True)
    (site / "pyodide").symlink_to(Path(pyodide), target_is_directory=True)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(site))
    handler.log_message = lambda *a, **k: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/index.html?py=/pyodide/", Path(npm_root)
    srv.shutdown()


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
