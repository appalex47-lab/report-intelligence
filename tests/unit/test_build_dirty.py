"""Fase 3A-1 · detección de compilaciones «dirty» (`tools/build_site.py::commit_info`).

Demuestra con repositorios git reales (temporales) qué cambios locales hacen `+dirty` y cuáles no, y que la lista de rutas revisadas
cubre todo lo que realmente viaja en el artefacto publicado (`app.zip` y el sitio). Nada de esto toca el repositorio del proyecto.
"""
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from tools import build_site

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git no está instalado")

# Un archivo representativo dentro de cada ruta empaquetada (las carpetas se representan con un archivo interior).
ARCHIVOS = {
    "tools/build_site.py": "# construcción\n",
    ".github/workflows/pages.yml": "name: Pages\n",
    "tools/make_machotes.py": "# machotes\n",
    "tools/make_glp1_synthetic.py": "# glp1\n",
    "frontend/index.html": "<html></html>\n",
    "frontend/worker.js": "// worker\n",
    "backend/app/mod.py": "x = 1\n",
    "profiles/p.yaml": "a: 1\n",
    "legacy/index.html": "<html>legacy</html>\n",
}
IRRELEVANTES = {
    "docs/nota.md": "doc\n", "tests/test_x.py": "def test_x(): pass\n", "README.md": "readme\n", "requirements.txt": "pyyaml\n",
}
ENV_GIT = {**{k: v for k, v in os.environ.items() if not k.startswith("GIT_")}, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True, env=ENV_GIT).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    git(r, "init", "-q")
    for ruta, texto in {**ARCHIVOS, **IRRELEVANTES}.items():
        f = r / ruta
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(texto)
    git(r, "add", "-A")
    git(r, "commit", "-q", "-m", "base")
    return r


def info(repo, env=None):
    return build_site.commit_info(root=repo, env={} if env is None else env)


# 3. un árbol limpio conserva el SHA sin sufijo ---------------------------------------------------------------------------------
def test_arbol_limpio_conserva_el_sha_sin_sufijo(repo):
    head = git(repo, "rev-parse", "HEAD")
    assert info(repo) == head and "+dirty" not in info(repo)
    assert info(repo, {"GITHUB_SHA": head}) == head            # también con el SHA que entrega CI


# 1 y 2. modificar lo que construye o lo que se empaqueta produce dirty ---------------------------------------------------------
@pytest.mark.parametrize("ruta", sorted(ARCHIVOS))
def test_modificar_un_archivo_que_altera_el_artefacto_produce_dirty(repo, ruta):
    head = git(repo, "rev-parse", "HEAD")
    (repo / ruta).write_text("cambio local\n")
    assert info(repo) == head + "+dirty", ruta


def test_modificar_tools_build_site_produce_dirty(repo):
    """El caso señalado en la revisión: cambiar la propia construcción altera app.zip aunque no cambie ningún archivo empaquetado."""
    head = git(repo, "rev-parse", "HEAD")
    assert info(repo) == head
    (repo / "tools/build_site.py").write_text("# construcción modificada\n")
    assert info(repo) == head + "+dirty"


def test_cambios_preparados_nuevos_o_borrados_tambien_son_dirty(repo):
    head = git(repo, "rev-parse", "HEAD")
    (repo / "backend/app/mod.py").write_text("x = 2\n")
    git(repo, "add", "backend/app/mod.py")                                   # preparado (staged), sin confirmar
    assert info(repo) == head + "+dirty"
    git(repo, "reset", "-q", "--hard")
    assert info(repo) == head
    (repo / "backend/app/nuevo.py").write_text("y = 1\n")                    # archivo nuevo sin seguimiento dentro de lo empaquetado
    assert info(repo) == head + "+dirty"
    (repo / "backend/app/nuevo.py").unlink()
    (repo / "legacy/index.html").unlink()                                    # borrado
    assert info(repo) == head + "+dirty"


# 5. los archivos irrelevantes para el artefacto no producen falsos positivos ----------------------------------------------------
@pytest.mark.parametrize("ruta", sorted(IRRELEVANTES))
def test_archivos_que_no_alteran_el_artefacto_no_producen_dirty(repo, ruta):
    head = git(repo, "rev-parse", "HEAD")
    (repo / ruta).write_text("cambio local\n")
    assert info(repo) == head, ruta


def test_caches_y_archivos_temporales_no_producen_dirty(repo):
    head = git(repo, "rev-parse", "HEAD")
    for ruta in ("backend/app/__pycache__/mod.cpython-312.pyc", "backend/app/suelto.pyc", "profiles/__pycache__/x.pyc",
                 "backend/app/_build_info.json", ".pytest_cache/v/cache", "docs/nueva.md", "salida/reporte.pptx"):
        f = repo / ruta
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("temporal\n")
    assert info(repo) == head                      # ninguno de ellos viaja en el artefacto (la copia suelta de _build_info.json se omite al empaquetar)


# 4. sin información suficiente -> desconocido ----------------------------------------------------------------------------------
def test_sin_repositorio_ni_sha_es_desconocido(tmp_path):
    assert info(tmp_path) == "desconocido"


def test_un_sha_de_entorno_sin_poder_comprobar_el_arbol_no_se_certifica_limpio(tmp_path):
    sha = "0123456789abcdef0123456789abcdef01234567"
    assert info(tmp_path, {"GITHUB_SHA": sha}) == "desconocido"             # no es un repositorio: no se puede verificar el árbol

    def sin_git(cmd, **kw):
        raise FileNotFoundError("git")
    assert build_site.commit_info(root=tmp_path, env={"GITHUB_SHA": sha}, run=sin_git) == "desconocido"
    assert build_site.commit_info(root=tmp_path, env={}, run=sin_git) == "desconocido"


def test_un_sha_de_entorno_invalido_se_ignora_y_se_usa_git(repo):
    head = git(repo, "rev-parse", "HEAD")
    assert info(repo, {"GITHUB_SHA": "no-es-un-sha"}) == head


# La lista cubre lo que realmente viaja en el artefacto -------------------------------------------------------------------------
def _cubierto(ruta: str) -> bool:
    return any(ruta == p or ruta.startswith(p + "/") for p in build_site.PACKAGED)


def test_las_rutas_revisadas_existen_y_cubren_todo_lo_que_se_empaqueta_y_se_publica(tmp_path):
    for p in build_site.PACKAGED:
        assert (ROOT / p).exists(), f"la ruta revisada {p} no existe"
    assert "tools/build_site.py" in build_site.PACKAGED and ".github/workflows/pages.yml" in build_site.PACKAGED
    w = tmp_path / "w"
    w.mkdir()
    for n in ("python_pptx-1.0.2-py3-none-any.whl", "XlsxWriter-3.3.1-py3-none-any.whl", "openpyxl-3.1.5-py2.py3-none-any.whl", "et_xmlfile-2.0.0-py3-none-any.whl"):
        (w / n).write_bytes(b"x")
    out = tmp_path / "_site"
    env = {k: v for k, v in os.environ.items() if k != "GITHUB_SHA"}
    subprocess.run([sys.executable, str(ROOT / "tools/build_site.py"), "--out", str(out), "--wheels", str(w)], check=True, env=env)
    with zipfile.ZipFile(out / "app.zip") as z:
        for n in z.namelist():
            if n != build_site.BUILD_INFO:
                assert _cubierto(n), f"{n} viaja en app.zip pero no está en la lista de rutas revisadas"
    for f in out.rglob("*"):
        rel = f.relative_to(out).as_posix()
        if f.is_dir() or rel in ("app.zip", ".nojekyll") or rel.startswith("wheels/"):
            continue
        assert _cubierto(rel if rel.startswith("legacy/") else f"frontend/{rel}"), f"{rel} se publica pero no está en la lista revisada"
    assert json.loads(zipfile.ZipFile(out / "app.zip").read(build_site.BUILD_INFO))["commit"]
