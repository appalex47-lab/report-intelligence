"""Fase 6 · diseño adaptativo de la interfaz: 10 pantallas medidas en 5 anchos (1280, 1024, 768, 390 y 320 px) en Chromium con Pyodide real. Comprueba lo medible por
máquina (sin desborde horizontal, nada fuera del área visible, tablas contenidas, controles táctiles de al menos 24 px, sin texto diminuto ni controles recortados); no juzga la
estética. No corre en CI (necesita Pyodide, Playwright y plantillas): se omite con motivo. Variables: REPORT_PYODIDE_DIR, REPORT_WHEELS_DIR (opcional)."""
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
SCRIPT = Path(__file__).with_name("responsivo.mjs")
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


ANCHOS = ("escritorio", "portatil", "tablet", "movil", "movil_pequeno")
PANTALLAS = ("1_cargar_vacio", "2_cargar_con_libro", "3_validar", "4_metas_y_contexto", "5_narrativa", "6_generar_antes", "7_generar_resultado",
             "8_generar_desactualizado", "9_historial", "10_plantillas")


def _medidas(resultado):
    assert resultado["ok"], resultado
    assert not resultado["consola"], resultado["consola"]
    assert set(resultado["pantallas"]) == set(PANTALLAS)
    for pant, anchos in resultado["pantallas"].items():
        assert set(anchos) == set(ANCHOS), pant
        for ancho, m in anchos.items():
            yield pant, ancho, m


def test_ninguna_pantalla_tiene_desplazamiento_horizontal_de_pagina_en_ningun_ancho(resultado):
    malas = [(p, a, m["scrollW"], m["ancho"]) for p, a, m in _medidas(resultado) if m["desborde_horizontal"]]
    assert not malas, malas


def test_ningun_elemento_queda_fuera_del_area_visible(resultado):
    malas = [(p, a, m["fuera"]) for p, a, m in _medidas(resultado) if m["n_fuera"]]
    assert not malas, malas


def test_las_tablas_caben_o_se_desplazan_dentro_de_su_contenedor(resultado):
    malas = [(p, a, m["tablas_que_no_caben"]) for p, a, m in _medidas(resultado) if m["n_tablas"]]
    assert not malas, malas


def test_los_controles_tactiles_miden_al_menos_24_px_en_tablet_y_movil(resultado):
    malas = [(p, a, m["tactiles_pequenos"]) for p, a, m in _medidas(resultado) if a in ("tablet", "movil", "movil_pequeno") and m["n_tactiles"]]
    assert not malas, malas


def test_sin_texto_diminuto_ni_controles_recortados(resultado):
    malas = [(p, a, m["texto_diminuto"], m["recortados"]) for p, a, m in _medidas(resultado) if m["n_diminutos"] or m["n_recortados"]]
    assert not malas, malas


def test_se_generan_las_capturas_de_tablet_y_movil_de_cada_pantalla(resultado):
    assert len(list(Path(resultado["_salida"]).glob("*.png"))) == 2 * len(PANTALLAS)
