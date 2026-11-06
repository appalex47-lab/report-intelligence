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

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = Path(__file__).with_name("escenarios_panel.mjs")
EJEMPLOS = ROOT / "data" / "ejemplos"


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


def _correr(sitio, tmp_path, unidad, libro):
    url, npm_root = sitio
    env = {**os.environ, "NODE_PATH": str(npm_root), "PLAYWRIGHT_REQUIRE_FROM": str(npm_root) + "/"}
    r = subprocess.run(["node", str(SCRIPT), url, str(libro), str(tmp_path), unidad, "9"], capture_output=True, text=True, env=env, timeout=900)
    linea = next((ln for ln in r.stdout.splitlines() if ln.startswith("RESULTADO ")), None)
    assert linea, f"el script no devolvió resultado:\n{r.stdout[-800:]}\n{r.stderr[-800:]}"
    res = json.loads(linea[len("RESULTADO "):])
    assert res["ok"], res
    assert not [c for c in res["consola"] if c.startswith(("error", "pageerror"))], res["consola"]      # sin errores de consola
    # las plantillas PPTX no se versionan: su 404 es el comportamiento normal de la aplicación sin plantillas, no un recurso caído
    assert not [x for x in res["red"] if "favicon" not in x and "/templates/" not in x], res["red"]       # sin otros recursos caídos
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
