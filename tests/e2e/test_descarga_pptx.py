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

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = Path(__file__).with_name("descarga_pptx.mjs")
LIBRO = ROOT / "data" / "ejemplos" / "AETOPS_crudo_ejemplo.xlsx"
TPL = ROOT / "templates" / "aetops-mensual" / "1" / "template.pptx"


def _omitir(motivo: str):
    pytest.skip(f"OMITIDA (no ejecutada): {motivo}")


def _requisitos():
    pyodide = os.environ.get("REPORT_PYODIDE_DIR")
    if not pyodide or not (Path(pyodide) / "pyodide.js").exists():
        _omitir("REPORT_PYODIDE_DIR no apunta a una distribución de Pyodide (pyodide.js)")
    if not TPL.exists():
        _omitir("la plantilla real de AETOPS mensual no está disponible (no se versiona)")
    if not shutil.which("node"):
        _omitir("Node.js no está instalado")
    npm_root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip() if shutil.which("npm") else ""
    if not npm_root or not (Path(npm_root) / "playwright").exists():
        _omitir("el paquete 'playwright' de Node no está instalado globalmente")
    return Path(pyodide), Path(npm_root)


@pytest.fixture(scope="module")
def sitio(tmp_path_factory):
    pyodide, npm_root = _requisitos()
    site = tmp_path_factory.mktemp("sitio")
    cmd = [sys.executable, str(ROOT / "tools" / "build_site.py"), "--out", str(site)]
    if os.environ.get("REPORT_WHEELS_DIR"):
        cmd += ["--wheels", os.environ["REPORT_WHEELS_DIR"]]
    subprocess.run(cmd, check=True, cwd=ROOT, capture_output=True)
    (site / "pyodide").symlink_to(pyodide, target_is_directory=True)
    dest = site / "templates" / "aetops-mensual" / "1"
    dest.mkdir(parents=True)
    shutil.copy(TPL, dest / "template.pptx")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(site))
    handler.log_message = lambda *a, **k: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/index.html?py=/pyodide/", npm_root
    srv.shutdown()


def test_el_boton_descargar_pptx_entrega_un_pptx_valido_con_el_motor_real(sitio, tmp_path):
    url, npm_root = sitio
    env = {**os.environ, "NODE_PATH": str(npm_root), "PLAYWRIGHT_REQUIRE_FROM": str(npm_root) + "/"}
    r = subprocess.run(["node", str(SCRIPT), url, str(LIBRO), str(tmp_path), "9"], capture_output=True, text=True, env=env, timeout=900)
    linea = next((ln for ln in r.stdout.splitlines() if ln.startswith("RESULTADO ")), None)
    assert linea, f"el script no devolvió resultado:\n{r.stdout[-800:]}\n{r.stderr[-800:]}"
    res = json.loads(linea[len("RESULTADO "):])
    assert res["ok"], res
    assert res["boton_habilitado"] and "QA aprobado" in res["banner"]
    assert res["nombre"].lower().endswith(".pptx")
    assert res["primeros_bytes"] == "504b0304"                                  # firma ZIP «PK\x03\x04»
    assert not [c for c in res["consola"] if c.startswith(("error", "pageerror"))], res["consola"]
    ruta = Path(res["ruta"])
    assert ruta.stat().st_size == res["bytes"] > 10_000
    with zipfile.ZipFile(ruta) as z:
        assert z.testzip() is None and "[Content_Types].xml" in z.namelist()      # ZIP íntegro
    from pptx import Presentation
    assert len(Presentation(str(ruta)).slides) >= 10                              # presentación abre y tiene diapositivas
