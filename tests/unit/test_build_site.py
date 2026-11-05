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


# --- Fase 3A-1: SHA del commit estampado en app.zip (spec Fase 3A §4.2) -------------------------------------------------------
import os  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import types  # noqa: E402

import pytest  # noqa: E402

requiere_git = pytest.mark.skipif(shutil.which("git") is None, reason="git no está disponible en el PATH")

SHA40 = "0123456789abcdef0123456789abcdef01234567"


def _wheels(tmp_path):
    w = tmp_path / "w"
    w.mkdir()
    for n in ("python_pptx-1.0.2-py3-none-any.whl", "XlsxWriter-3.3.1-py3-none-any.whl", "openpyxl-3.1.5-py2.py3-none-any.whl", "et_xmlfile-2.0.0-py3-none-any.whl"):
        (w / n).write_bytes(b"x")
    return w


def _build(tmp_path, env_extra=None):
    out = tmp_path / "_site"
    env = {k: v for k, v in os.environ.items() if k != "GITHUB_SHA"}
    env.update(env_extra or {})
    subprocess.run([sys.executable, str(ROOT / "tools/build_site.py"), "--out", str(out), "--wheels", str(_wheels(tmp_path))], check=True, env=env)
    return out


@requiere_git
def test_app_zip_lleva_build_info_solo_con_el_sha_sin_fechas(tmp_path):
    out = _build(tmp_path, {"GITHUB_SHA": SHA40})
    with zipfile.ZipFile(out / "app.zip") as z:
        assert z.namelist().count("backend/app/_build_info.json") == 1
        info = json.loads(z.read("backend/app/_build_info.json"))
    assert set(info) == {"esquema", "commit"}                          # ningún valor variable: ni fecha ni ruta
    assert info["esquema"] == "build_info/1"
    assert re.fullmatch(r"[0-9a-f]{40}(\+dirty)?", info["commit"])
    assert info["commit"].startswith(SHA40)                            # GITHUB_SHA tiene prioridad (CI)


@requiere_git
def test_sin_github_sha_se_usa_git_y_el_sha_es_el_de_head(tmp_path):
    r = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True)
    if r.returncode != 0:
        return
    out = _build(tmp_path)
    with zipfile.ZipFile(out / "app.zip") as z:
        info = json.loads(z.read("backend/app/_build_info.json"))
    assert info["commit"].removesuffix("+dirty") == r.stdout.strip()


def test_el_build_info_no_se_crea_en_el_repositorio(tmp_path):
    _build(tmp_path)
    assert not (ROOT / "backend/app/_build_info.json").exists()


def test_una_copia_suelta_de_build_info_no_viaja_en_el_zip(tmp_path):
    from tools import build_site
    src = tmp_path / "backend"
    (src / "app").mkdir(parents=True)
    (src / "app" / "_build_info.json").write_text('{"commit": "x"}')
    (src / "app" / "otro.py").write_text("x = 1\n")
    with zipfile.ZipFile(tmp_path / "t.zip", "w") as z:
        n = build_site.add_tree(z, "backend", src)
        assert n == 1 and z.namelist() == ["backend/app/otro.py"]


def _run_git(salidas):
    """Falso `subprocess.run` para git: `salidas` = {primer_argumento_de_git: (returncode, stdout)}."""
    def run(cmd, **kw):
        sub = cmd[3]                                                    # ["git", "-C", root, <subcomando>, ...]
        rc, out = salidas.get(sub, (1, ""))
        return types.SimpleNamespace(returncode=rc, stdout=out)
    return run


def test_commit_info_limpio_con_sha_de_ci():
    from tools import build_site
    run = _run_git({"status": (0, "")})
    assert build_site.commit_info(env={"GITHUB_SHA": SHA40}, run=run) == SHA40


def test_commit_info_con_arbol_modificado_agrega_dirty():
    from tools import build_site
    run = _run_git({"rev-parse": (0, SHA40 + "\n"), "status": (0, " M backend/app/version.py\n")})
    assert build_site.commit_info(env={}, run=run) == SHA40 + "+dirty"
    assert build_site.commit_info(env={"GITHUB_SHA": SHA40}, run=run) == SHA40 + "+dirty"


def test_commit_info_sin_informacion_es_desconocido_y_nunca_inventa_un_sha():
    from tools import build_site
    assert build_site.commit_info(env={}, run=_run_git({})) == "desconocido"                       # git falla
    assert build_site.commit_info(env={}, run=_run_git({"rev-parse": (0, "no-es-un-sha\n")})) == "desconocido"

    def sin_git(cmd, **kw):
        raise FileNotFoundError("git")
    assert build_site.commit_info(env={}, run=sin_git) == "desconocido"                            # git no instalado
    assert build_site.commit_info(env={"GITHUB_SHA": "corto"}, run=sin_git) == "desconocido"      # un SHA de entorno inválido no se acepta


@requiere_git
def test_las_versiones_se_leen_dentro_del_paquete_con_y_sin_informacion_de_compilacion(tmp_path):
    """El paquete compilado (zip descomprimido, como en Pyodide) lee el SHA; el repositorio sin compilar da «desconocido»."""
    out = _build(tmp_path, {"GITHUB_SHA": SHA40})
    ext = tmp_path / "ext"
    with zipfile.ZipFile(out / "app.zip") as z:
        z.extractall(ext)
    code = "import json; from backend.app import version; print(json.dumps(version.versiones()))"
    env = {**os.environ, "PYTHONPATH": str(ext)}
    con = json.loads(subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True, env=env, cwd=ext).stdout)
    assert con["app"] == "1.0.0" and con["motor"] == "1.0.0" and con["commit"].startswith(SHA40)
    assert con["compilacion"]["estado"] in ("limpia", "dirty")
    sin = json.loads(subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True,
                                    env={**os.environ, "PYTHONPATH": str(ROOT)}, cwd=ROOT).stdout)
    assert sin["commit"] == "desconocido" and sin["compilacion"]["estado"] == "desconocida"
    assert sin["app"] == con["app"] and sin["motor"] == con["motor"]
