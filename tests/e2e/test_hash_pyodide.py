"""`hash_resultado` dentro de Pyodide = el de CPython (spec Fase 3A §6.3; 3A-2).

Calcula el hash de los 4 escenarios de la línea base en Pyodide (Node) con el `app.zip` que arma `tools/build_site.py` —el mismo que
publica GitHub Pages— y lo compara con los valores congelados en `tests/regression/hash_resultado.json`.

Se OMITE, con el motivo, si falta: `REPORT_PYODIDE_WORK` (carpeta de trabajo con `node_modules/pyodide` 0.27.x y `sp/` con openpyxl, et_xmlfile
y yaml; ver `tools/pyodide_node_check.mjs`), Node.js, o `REPORT_WHEELS_DIR` (opcional: si falta, `build_site.py` descarga los wheels). No se
ejecuta en CI.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = Path(__file__).with_name("hash_pyodide.mjs")


def test_el_hash_en_pyodide_coincide_con_el_de_cpython(tmp_path):
    work = os.environ.get("REPORT_PYODIDE_WORK")
    if not work or not (Path(work) / "node_modules" / "pyodide").exists() or not (Path(work) / "sp").exists():
        pytest.skip("OMITIDA (no ejecutada): REPORT_PYODIDE_WORK no apunta a una carpeta con node_modules/pyodide y sp/")
    if not shutil.which("node"):
        pytest.skip("OMITIDA (no ejecutada): Node.js no está instalado")
    site = tmp_path / "sitio"
    cmd = [sys.executable, str(ROOT / "tools" / "build_site.py"), "--out", str(site)]
    if os.environ.get("REPORT_WHEELS_DIR"):
        cmd += ["--wheels", os.environ["REPORT_WHEELS_DIR"]]
    subprocess.run(cmd, check=True, cwd=ROOT, capture_output=True)
    salida = tmp_path / "pyodide.json"
    r = subprocess.run(["node", "--experimental-default-type=module", str(SCRIPT), work, str(site / "app.zip"), str(salida)],
                       capture_output=True, text=True, timeout=900)
    assert r.returncode == 0 and salida.exists(), (r.stdout[-500:], r.stderr[-1500:])
    en_pyodide = json.loads(salida.read_text(encoding="utf-8"))
    esperado = json.loads((ROOT / "tests/regression/hash_resultado.json").read_text(encoding="utf-8"))["escenarios"]
    assert en_pyodide["plataforma"] == "emscripten"
    assert en_pyodide["escenarios"] == esperado
