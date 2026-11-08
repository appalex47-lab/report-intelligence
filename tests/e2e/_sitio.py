"""Infraestructura común de las pruebas de navegador (Playwright + Pyodide real): construye el sitio, lo sirve y ejecuta los scripts de Node.

Configuración por variables de entorno (la misma en el equipo de desarrollo y en CI):
  REPORT_BROWSER            chromium (por omisión) | firefox | webkit
  REPORT_PYODIDE_DIR        distribución completa de Pyodide 0.27.x en disco; si falta pero REPORT_PYODIDE_CDN=1, se usa la CDN fijada por el propio worker (jsdelivr, v0.27.7)
  REPORT_PYODIDE_CDN        «1» = Pyodide desde la CDN (CI: no hay que descargar 400 MB)
  REPORT_PLAYWRIGHT_DIR     carpeta que contiene `node_modules/playwright` (por omisión, la instalación global de npm)
  REPORT_WHEELS_DIR         .whl ya descargados (opcional; si no, build_site los descarga de PyPI con versión fija)
  REPORT_PYODIDE_REQUIRED   «1» = la falta de un requisito es un FALLO, no una omisión (CI)
Las plantillas del sitio son las reales si están en `templates/` y las sintéticas si no (tests/plantillas.py): nunca se mezclan.
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
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests import plantillas as PL

ROOT = Path(__file__).resolve().parents[2]
LIBROS = ROOT / "data" / "ejemplos"
NAVEGADORES = ("chromium", "firefox", "webkit")


def navegador() -> str:
    b = os.environ.get("REPORT_BROWSER", "chromium").lower()
    if b not in NAVEGADORES:
        raise ValueError(f"REPORT_BROWSER debe ser uno de {NAVEGADORES}, no «{b}»")
    return b


def omitir(motivo: str):
    if os.environ.get("REPORT_PYODIDE_REQUIRED") == "1":
        pytest.fail(f"REPORT_PYODIDE_REQUIRED=1 y falta un requisito: {motivo}")
    pytest.skip(f"OMITIDA (no ejecutada): {motivo}")


@dataclass
class Sitio:
    url: str
    npm_root: Path
    env: dict
    plantillas: str                      # «reales» | «sinteticas»
    navegador: str


def _playwright_dir() -> Path:
    explicit = os.environ.get("REPORT_PLAYWRIGHT_DIR")
    if explicit:
        return Path(explicit) / "node_modules"
    npm_root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip() if shutil.which("npm") else ""
    return Path(npm_root) if npm_root else Path("/nonexistent")


def construir(tmp_path_factory, con_plantillas: bool = True) -> Sitio:
    """Valida los requisitos, construye el sitio (build_site + plantillas) y lo sirve en un puerto libre. Devuelve la URL y el entorno de Node."""
    pyodide = os.environ.get("REPORT_PYODIDE_DIR")
    por_cdn = os.environ.get("REPORT_PYODIDE_CDN") == "1"
    if pyodide and not (Path(pyodide) / "pyodide.js").exists():
        omitir("REPORT_PYODIDE_DIR no apunta a una distribución de Pyodide (pyodide.js)")
    if not pyodide and not por_cdn:
        omitir("ni REPORT_PYODIDE_DIR ni REPORT_PYODIDE_CDN=1: no hay Pyodide completo")
    if not shutil.which("node"):
        omitir("Node.js no está instalado")
    pw = _playwright_dir()
    if not (pw / "playwright").exists():
        omitir(f"el paquete 'playwright' de Node no está en {pw}")
    sitio = tmp_path_factory.mktemp("sitio")
    cmd = [sys.executable, str(ROOT / "tools" / "build_site.py"), "--out", str(sitio)]
    if os.environ.get("REPORT_WHEELS_DIR"):
        cmd += ["--wheels", os.environ["REPORT_WHEELS_DIR"]]
    subprocess.run(cmd, check=True, cwd=ROOT, capture_output=True)
    query = ""
    if pyodide:
        (sitio / "pyodide").symlink_to(Path(pyodide), target_is_directory=True)
        query = "?py=/pyodide/"
    if con_plantillas:
        for f in PL.FORMATOS:
            if PL.disponible(f):
                d = sitio / "templates" / f / "1"
                d.mkdir(parents=True)
                shutil.copy(PL.ruta(f), d / "template.pptx")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(sitio))
    handler.log_message = lambda *a, **k: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    tmp_path_factory._servidor_e2e = srv                                             # se mantiene vivo mientras dure la sesión de pruebas
    env = {**os.environ, "NODE_PATH": str(pw), "PLAYWRIGHT_REQUIRE_FROM": str(pw.parent) + "/", "REPORT_BROWSER": navegador()}
    return Sitio(f"http://127.0.0.1:{srv.server_address[1]}/index.html{query}", pw, env, PL.origen(), navegador())


def ejecutar(s: Sitio, script: Path, *args: str, timeout: int = 1500) -> dict:
    """Ejecuta un script de Node con la URL del sitio y devuelve el objeto de su línea «RESULTADO {json}»."""
    r = subprocess.run(["node", str(script), s.url, *args], capture_output=True, text=True, env=s.env, timeout=timeout)
    linea = next((ln for ln in r.stdout.splitlines() if ln.startswith("RESULTADO ")), None)
    assert linea, f"el script no devolvió resultado:\n{r.stdout[-800:]}\n{r.stderr[-800:]}"
    return json.loads(linea[len("RESULTADO "):])
