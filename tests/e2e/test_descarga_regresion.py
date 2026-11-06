"""Fase 5 · INC-001 «data.htm»: regresión de la descarga en un navegador real con la función `download()` REAL de `frontend/index.html`.

No necesita Pyodide ni plantillas: sirve `frontend/` tal cual y sustituye solo lo que el motor devuelve (nombre y bytes) para forzar cada situación.
Requiere Node + Playwright (global) y Chromium; si falta algo se OMITE con el motivo (con `REPORT_PYODIDE_REQUIRED=1`, como en CI, falla).

Causa raíz: NO REPRODUCIDA (ver docs/fase5/DESCARGA_DATA_HTM.md). Esta prueba fija las garantías con las que el nombre y el tipo del archivo dejan de depender del motor.
"""
from __future__ import annotations

import base64
import functools
import http.server
import json
import os
import shutil
import subprocess
import threading
import zipfile
from io import BytesIO
from pathlib import Path

import pytest
from pptx import Presentation

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = Path(__file__).with_name("descarga_regresion.mjs")


def _omitir(motivo: str):
    if os.environ.get("REPORT_PYODIDE_REQUIRED") == "1":
        pytest.fail(f"REPORT_PYODIDE_REQUIRED=1 y falta un requisito: {motivo}")
    pytest.skip(f"OMITIDA (no ejecutada): {motivo}")


@pytest.fixture(scope="module")
def navegador():
    if not shutil.which("node"):
        _omitir("Node.js no está instalado")
    npm_root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip() if shutil.which("npm") else ""
    if not npm_root or not (Path(npm_root) / "playwright").exists():
        _omitir("el paquete 'playwright' de Node no está instalado globalmente")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT / "frontend"))
    handler.log_message = lambda *a, **k: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/index.html", Path(npm_root)
    srv.shutdown()


def pptx_valido() -> bytes:
    b = BytesIO()
    prs = Presentation()
    prs.slides.add_slide(prs.slide_layouts[6])
    prs.save(b)
    return b.getvalue()


def b64(x: bytes) -> str:
    return base64.b64encode(x).decode()


def ejecutar(navegador, tmp_path, casos):
    url, npm_root = navegador
    f = tmp_path / "casos.json"
    f.write_text(json.dumps(casos), encoding="utf-8")
    env = {**os.environ, "NODE_PATH": str(npm_root), "PLAYWRIGHT_REQUIRE_FROM": str(npm_root) + "/"}
    r = subprocess.run(["node", str(SCRIPT), url, str(f), str(tmp_path)], capture_output=True, text=True, env=env, timeout=300)
    linea = next((ln for ln in r.stdout.splitlines() if ln.startswith("RESULTADO ")), None)
    assert linea, f"sin resultado:\n{r.stdout[-600:]}\n{r.stderr[-600:]}"
    return json.loads(linea[len("RESULTADO "):])


PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


def test_un_pptx_valido_se_descarga_con_nombre_y_tipo_correctos_y_se_abre(navegador, tmp_path):
    datos = pptx_valido()
    r = ejecutar(navegador, tmp_path, [{"id": "ok", "path": "/runs/abc/files/Resultados_AETOP_Septiembre_2026.pptx", "name": "Resultados_AETOP_Septiembre_2026.pptx", "b64": b64(datos)}])["ok"]
    assert r["descarga"]["nombre"] == "Resultados_AETOP_Septiembre_2026.pptx" and r["descarga"]["bytes"] == len(datos)
    assert r["blobs"][-1]["tipo"] == PPTX
    ruta = Path(r["descarga"]["ruta"])
    assert zipfile.is_zipfile(ruta) and len(Presentation(str(ruta)).slides) == 1                   # el contenido real se abre
    assert ruta.read_bytes() == datos


@pytest.mark.parametrize("nombre_motor", ["data.htm", "data.html", "download", "", None, "../../etc/passwd", "reporte.txt", "a/b\\c.docx"])
def test_el_nombre_que_devuelva_el_motor_no_puede_producir_data_htm(navegador, tmp_path, nombre_motor):
    """La extensión sale de lo pedido (.pptx): aunque el motor diga «data.htm», el archivo se llama *.pptx y es un PPTX."""
    datos = pptx_valido()
    r = ejecutar(navegador, tmp_path, [{"id": "n", "path": "/runs/abc/files/x.pptx", "name": nombre_motor, "b64": b64(datos)}])["n"]
    assert r["descarga"] is not None and r["descarga"]["nombre"].endswith(".pptx") and not r["descarga"]["nombre"].lower().endswith((".htm", ".html"))
    assert "/" not in r["descarga"]["nombre"] and "\\" not in r["descarga"]["nombre"] and ".." not in r["descarga"]["nombre"]
    assert r["blobs"][-1]["tipo"] == PPTX


@pytest.mark.parametrize("contenido", [b"<!DOCTYPE html><html><body>404 Not Found</body></html>", b"<html>x</html>", b"   \n<!doctype html>...", b"", b"PK\x03\x04truncado sin fin de ZIP",
                                       b"PK\x03\x04" + b"0" * 100 + b"PK\x05\x06" + b"\0" * 18])
def test_lo_que_no_es_un_pptx_completo_no_se_entrega_como_pptx(navegador, tmp_path, contenido):
    r = ejecutar(navegador, tmp_path, [{"id": "x", "path": "/runs/abc/files/x.pptx", "name": "x.pptx", "b64": b64(contenido)}])["x"]
    assert r["descarga"] is None and r["blobs"] == [] and r["toast"], r                               # nada se descarga y el usuario ve un motivo


def test_un_zip_que_no_es_office_se_rechaza(navegador, tmp_path):
    b = BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("hola.txt", "no soy una presentación")
    r = ejecutar(navegador, tmp_path, [{"id": "z", "path": "/runs/abc/files/x.pptx", "name": "x.pptx", "b64": b64(b.getvalue())}])["z"]
    assert r["descarga"] is None and "no un PPTX" in r["toast"]


def test_pdf_json_y_png_llevan_su_tipo_y_se_validan(navegador, tmp_path):
    png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
    r = ejecutar(navegador, tmp_path, [
        {"id": "pdf", "path": "/runs/a/files/r.pdf", "name": "r.pdf", "b64": b64(b"%PDF-1.4\n%fin")},
        {"id": "pdf_malo", "path": "/runs/a/files/r.pdf", "name": "r.pdf", "b64": b64(b"<html>no soy pdf</html>")},
        {"id": "json", "path": "/runs/a/files/narrative.json", "name": "narrative.json", "b64": b64(b'{"a": 1}')},
        {"id": "json_malo", "path": "/runs/a/files/narrative.json", "name": "narrative.json", "b64": b64(b"{roto")},
        {"id": "png", "path": "/runs/a/files/s-01.png", "name": "s-01.png", "b64": b64(png)}])
    assert r["pdf"]["blobs"][-1]["tipo"] == "application/pdf" and r["pdf"]["descarga"]["nombre"] == "r.pdf"
    assert r["json"]["blobs"][-1]["tipo"] == "application/json" and r["png"]["blobs"][-1]["tipo"] == "image/png"
    assert r["pdf_malo"]["descarga"] is None and r["json_malo"]["descarga"] is None


def test_machote_e_historial_sin_extension_en_la_ruta_usan_la_del_motor(navegador, tmp_path):
    xlsx = BytesIO()
    with zipfile.ZipFile(xlsx, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
    r = ejecutar(navegador, tmp_path, [
        {"id": "machote", "path": "/machote", "name": "MACHETE_GLP1.xlsx", "b64": b64(xlsx.getvalue())},
        {"id": "historial", "path": "/history/export", "name": "historial.sqlite", "b64": b64(b"SQLite format 3\x00" + b"0" * 50)},
        {"id": "historial_malo", "path": "/history/export", "name": "historial.sqlite", "b64": b64(b"<html>x</html>")}])
    assert r["machote"]["descarga"]["nombre"] == "MACHETE_GLP1.xlsx" and r["machote"]["blobs"][-1]["tipo"].endswith("spreadsheetml.sheet")
    assert r["historial"]["descarga"]["nombre"] == "historial.sqlite" and r["historial"]["blobs"][-1]["tipo"] == "application/vnd.sqlite3"
    assert r["historial_malo"]["descarga"] is None


def test_la_url_del_blob_no_se_revoca_antes_de_tiempo(navegador, tmp_path):
    """El código anterior la revocaba a los 4 s: un equipo o red lentos podían no haber empezado a guardar el archivo."""
    r = ejecutar(navegador, tmp_path, [{"id": "t", "path": "/runs/a/files/x.pptx", "name": "x.pptx", "b64": b64(pptx_valido())}])["t"]
    assert r["descarga"] is not None and r["revocadas_antes_de_5s"] == 0


def test_en_un_navegador_integrado_se_avisa_antes_de_descargar(navegador, tmp_path):
    ua = "Mozilla/5.0 (Linux; Android 13; Pixel 7 Build/TQ3A; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/120.0 Mobile Safari/537.36"
    r = ejecutar(navegador, tmp_path, [{"id": "wv", "path": "/runs/a/files/x.pptx", "name": "x.pptx", "b64": b64(pptx_valido()), "ua": ua},
                                       {"id": "normal", "path": "/runs/a/files/x.pptx", "name": "x.pptx", "b64": b64(pptx_valido())}])
    assert "navegador integrado" in r["wv"]["toast"] and "Chrome o Safari" in r["wv"]["toast"]
    assert "navegador integrado" not in r["normal"]["toast"] and r["normal"]["descarga"]["nombre"] == "x.pptx"
