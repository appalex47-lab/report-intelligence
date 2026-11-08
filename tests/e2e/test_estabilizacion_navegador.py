"""Fase 8 · estabilización en el navegador real (Chromium + Pyodide): rendimiento, persistencia tras recargar e integridad del PPTX descargado. No corre en CI (necesita Pyodide,
Playwright y plantillas): se omite con motivo. Variables: REPORT_PYODIDE_DIR, REPORT_WHEELS_DIR (opcional)."""
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
SCRIPT = Path(__file__).with_name("estabilizacion_navegador.mjs")
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
def resultado(tmp_path_factory):
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
    url = f"http://127.0.0.1:{srv.server_address[1]}/index.html?py=/pyodide/"
    salida = tmp_path_factory.mktemp("salida")
    env = {**os.environ, "NODE_PATH": str(npm_root), "PLAYWRIGHT_REQUIRE_FROM": str(npm_root) + "/"}
    r = subprocess.run(["node", str(SCRIPT), url, str(LIBRO), str(salida), "9"], capture_output=True, text=True, env=env, timeout=1500)
    srv.shutdown()
    linea = next((ln for ln in r.stdout.splitlines() if ln.startswith("RESULTADO ")), None)
    assert linea, f"el script no devolvió resultado:\n{r.stdout[-800:]}\n{r.stderr[-800:]}"
    res = json.loads(linea[len("RESULTADO "):])
    res["_salida"] = salida
    return res


import hashlib


def test_el_recorrido_termina_sin_errores_de_consola(resultado):
    assert resultado["ok"], resultado
    assert not resultado["consola"], resultado["consola"]


def test_rendimiento_dentro_de_los_limites_acordados_con_pyodide(resultado):
    """Límites generosos (≈3× lo medido) para detectar degradaciones graves, no para fijar un rendimiento exacto. Los tiempos reales quedan en el informe."""
    t = resultado["tiempos"]
    assert t["arranque_motor_s"] < 120, t
    assert t["carga_del_libro_s"] < 60, t
    assert t["analisis_s"] < 90, t
    assert t["generacion_s"] < 240, t


def test_el_historial_y_los_escenarios_propios_sobreviven_a_recargar_la_pagina(resultado):
    pers = resultado["persistencia"]
    mensuales = [r for r in pers["historial"] if r["unidad"] == "AETOPS" and r["periodicidad"] == "mensual" and r["anio"] == 2026 and r["indice"] == 9]
    assert mensuales, pers["historial"]
    assert pers["historial_visible"] is True
    assert "estabilizacion" in pers["escenarios"], pers["escenarios"]


def test_el_pptx_descargado_es_integro_y_coincide_con_el_manifiesto(resultado):
    d = resultado["descarga"]
    assert d["zip"] and d["bytes"] > 50_000 and d["nombre"].endswith(".pptx")
    assert d["sha256"] == resultado["manifiesto_sha256"]
    ruta = Path(resultado["_salida"]) / d["nombre"]
    assert hashlib.sha256(ruta.read_bytes()).hexdigest() == d["sha256"]
    from pptx import Presentation
    assert len(Presentation(str(ruta)).slides) == 13
