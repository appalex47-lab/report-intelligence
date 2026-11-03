"""El sitio estático (GitHub Pages) se arma completo y el paquete de la aplicación se importa sin servidor ni LibreOffice."""
import importlib.util
import json
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_site_bundle(tmp_path):
    wheels = tmp_path / "w"
    wheels.mkdir()
    for n in ("python_pptx-1.0.2-py3-none-any.whl", "XlsxWriter-3.3.1-py3-none-any.whl", "openpyxl-3.1.5-py2.py3-none-any.whl", "et_xmlfile-2.0.0-py3-none-any.whl"):
        (wheels / n).write_bytes(b"x")
    out = tmp_path / "_site"
    subprocess.run([sys.executable, str(ROOT / "tools/build_site.py"), "--out", str(out), "--wheels", str(wheels)], check=True)
    assert (out / "index.html").exists() and (out / "worker.js").exists() and (out / ".nojekyll").exists()
    names = json.loads((out / "wheels/index.json").read_text())
    assert len(names) == 4 and sorted(names) == names
    with zipfile.ZipFile(out / "app.zip") as z:
        zn = set(z.namelist())
    for need in ("backend/app/web/bridge.py", "backend/app/pipeline.py", "profiles/aetops/mensual.yaml", "profiles/glp1/trimestral.yaml",
                 "tools/make_machotes.py", "tools/make_glp1_synthetic.py"):
        assert need in zn, need
    assert not any("__pycache__" in n or n.endswith(".pyc") for n in zn)
    assert not any(n.endswith(".pptx") for n in zn)                       # las plantillas con marca no se publican


def test_frontend_has_no_server_dependency():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert 'fetch("/api' not in html and "href=\"/api" not in html and "localhost" not in html


def test_browser_modules_do_not_need_render_libs():
    """Lo que se importa en el navegador no debe requerir Pillow/fastapi/LibreOffice al cargar."""
    for rel in ("backend/app/web/bridge.py", "backend/app/web/service.py", "backend/app/qa/checks.py", "backend/app/render.py"):
        src = (ROOT / rel).read_text(encoding="utf-8")
        top = [ln for ln in src.splitlines() if ln.startswith(("import ", "from "))]
        assert not any("fastapi" in ln or "PIL" in ln for ln in top), (rel, top)
