"""Flujo integrado en un navegador real (Chromium) con el motor REAL en Pyodide: escenario → generar → vista previa → QA → cambio (obsoleto) → regenerar →
caso bloqueante → corrección → descarga. No corre en CI (necesita Pyodide completo, Playwright y las plantillas, que no se versionan): se omite con motivo.
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
SCRIPT = Path(__file__).with_name("flujo_integral.mjs")
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


def test_el_recorrido_completo_termina_bien_y_sin_errores_de_consola(resultado):
    assert resultado["ok"], resultado
    assert not [c for c in resultado["consola"] if c.startswith(("error", "pageerror"))], resultado["consola"]


def test_escenario_y_etapas_visibles_antes_de_generar(resultado):
    e = resultado["pasos"]["escenario"]
    assert e["seleccionado"] == "aetops-mensual" and e["adaptativo"] is True
    assert set(e["opciones"]) >= {"aetops-mensual", "aetops-trimestral", "glp1-mensual", "glp1-trimestral"}
    assert len(e["etapas"]) == 6 and "Escenario" in e["etapas"][0]


def test_reporte_valido_vista_previa_calidad_y_exportacion_habilitada(resultado):
    g = resultado["pasos"]["generado"]
    assert not g["obsoleto"] and g["dlHabilitado"] and g["errores"] == 0
    assert "QA aprobado" in g["banner"] and "Revisión estructural" in g["banner"]
    assert g["diapositivas"] == 13 and g["formasDibujadas"] >= 4                       # la vista previa dibuja de verdad
    assert any("Exportación habilitada" in x for x in g["etapas"]) and any("Vista previa" in x for x in g["etapas"])


def test_navegacion_de_la_vista_previa(resultado):
    n = resultado["pasos"]["navegacion"]
    assert (n["k0"], n["k1"], n["k2"], n["k3"]) == ("0", "1", "0", "3")
    assert n["texto_diapositiva"].strip() and n["tablaDibujada"] is True                  # la diapositiva 4 trae una tabla y se dibuja


def test_un_cambio_despues_de_generar_invalida_la_vista_previa_el_qa_y_la_descarga(resultado):
    o = resultado["pasos"]["obsoleto"]
    assert o["obsoleto"] and not o["dlHabilitado"] and o["previewVisible"] is False


def test_regenerar_deja_los_resultados_vigentes_y_el_escenario_llega_al_reporte(resultado):
    r = resultado["pasos"]["regenerado"]
    assert not r["obsoleto"] and r["dlHabilitado"] and r["diapositivas"] == 13
    assert r["contextoEnVistaPrevia"] is True                                         # el contexto de negocio del escenario controla el contenido


def test_un_error_bloqueante_bloquea_la_exportacion_pero_no_oculta_la_vista_previa(resultado):
    b = resultado["pasos"]["bloqueado"]
    assert b["escenario"] == "exige-engagement"
    assert "QA rechazado" in b["banner"] and "QA_FALTA_TIPO_OBLIGATORIO" in b["hallazgos"] and b["errores"] >= 1
    assert not b["dlHabilitado"] and "Descarga bloqueada" in b["descargaIntentada"]
    assert b["diapositivas"] == 13                                                    # sigue habiendo vista previa para corregir


def test_corregido_el_problema_se_reejecuta_el_qa_y_se_habilita(resultado):
    c = resultado["pasos"]["corregido"]
    assert "QA aprobado" in c["banner"] and c["dlHabilitado"] and c["errores"] == 0, c


def test_el_pptx_descargado_es_valido_y_coincide_con_lo_previsualizado(resultado):
    assert resultado["nombre"].lower().endswith(".pptx") and resultado["primeros_bytes"] == "504b0304"
    ruta = Path(resultado["ruta"])
    with zipfile.ZipFile(ruta) as z:
        assert z.testzip() is None
    from pptx import Presentation
    assert len(Presentation(str(ruta)).slides) == resultado["pasos"]["corregido"]["diapositivas"] == 13
