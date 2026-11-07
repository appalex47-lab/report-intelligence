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

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = Path(__file__).with_name("revision_visual.mjs")
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
