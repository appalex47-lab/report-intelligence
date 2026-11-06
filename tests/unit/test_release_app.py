"""Fase 3A-5 (A-5) · `tools/release_app.py` y `.github/workflows/release.yml`. Se ejecuta en CI.

Qué cubre: la lógica de validación y preparación de la release (con zips sintéticos y con el `app.zip` REAL de `build_site.py`) y la estructura de
seguridad del workflow (solo manual, ensayo por omisión, solo desde main, permisos mínimos, nunca reescribe etiquetas). Qué NO cubre, y se dice
expresamente: la ejecución del workflow en GitHub (V-02) —requiere publicar una release de verdad— no se prueba aquí."""
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("release_app", ROOT / "tools" / "release_app.py")
ra = importlib.util.module_from_spec(spec)
sys.modules["release_app"] = ra
spec.loader.exec_module(ra)

SHA = "a" * 40
VERSION_PY = 'APP_VERSION = "1.0.0"\nENGINE_VERSION = "1.0.0"\n'


def zip_sintetico(ruta, *, commit=SHA, version_py=VERSION_PY, esquema="build_info/1", sin=(), extra=None):
    with zipfile.ZipFile(ruta, "w") as z:
        if ra.BUILD_INFO not in sin:
            z.writestr(ra.BUILD_INFO, json.dumps({"esquema": esquema, "commit": commit}))
        if ra.VERSION_PY not in sin:
            z.writestr(ra.VERSION_PY, version_py)
        z.writestr("backend/app/otro.py", "x = 1\n")
        for n, d in (extra or {}).items():
            z.writestr(n, d)
    return ruta


# ----------------------------------------------------------------------------------------------------------------- versión y etiqueta
def test_la_version_del_repositorio_es_la_de_la_aplicacion():
    from backend.app import version
    assert ra.version_del_repositorio() == version.APP_VERSION and ra.etiqueta(version.APP_VERSION) == f"app-v{version.APP_VERSION}"


@pytest.mark.parametrize("v", ["1.0.0", "0.0.1", "10.20.30"])
def test_etiqueta_valida(v):
    assert ra.etiqueta(v) == f"app-v{v}"


@pytest.mark.parametrize("v", ["", "1.0", "v1.0.0", "01.0.0", "1.0.0-rc1", "1.0.0+x", " 1.0.0", "1.0.0\n", "1.0.0 ", "a.b.c", None, 1, "1.0.0/../x",
                               "1.0.0;rm -rf", "1..0"])
def test_etiqueta_invalida_nunca_se_adivina(v):
    with pytest.raises(ra.ErrorRelease):
        ra.etiqueta(v)


def test_leer_app_version():
    assert ra.leer_app_version('"""doc"""\nAPP_VERSION = "2.3.4"\n') == "2.3.4"
    for malo in ("", "ENGINE_VERSION = '1.0.0'", 'APP_VERSION = "1.0"', 'APP_VERSION = ""', '# APP_VERSION = "1.0.0"', 'X = 1'):
        with pytest.raises(ra.ErrorRelease):
            ra.leer_app_version(malo)


# ----------------------------------------------------------------------------------------------------------------- validar_zip
def test_zip_valido(tmp_path):
    ra.validar_zip(zip_sintetico(tmp_path / "a.zip"), "1.0.0", SHA)


@pytest.mark.parametrize("caso,kw,commit,version,texto", [
    ("commit distinto", dict(commit="b" * 40), SHA, "1.0.0", "compilado de"),
    ("con +dirty", dict(commit=SHA + "+dirty"), SHA, "1.0.0", "+dirty"),
    ("desconocido", dict(commit="desconocido"), SHA, "1.0.0", "desconocido"),
    ("sin build_info", dict(sin=("backend/app/_build_info.json",)), SHA, "1.0.0", "no contiene"),
    ("sin version.py", dict(sin=("backend/app/version.py",)), SHA, "1.0.0", "no contiene"),
    ("esquema distinto", dict(esquema="otro/9"), SHA, "1.0.0", "esquema"),
    ("version distinta", dict(version_py='APP_VERSION = "1.0.1"\n'), SHA, "1.0.0", "empaqueta APP_VERSION 1.0.1"),
    ("version ilegible", dict(version_py="nada"), SHA, "1.0.0", "APP_VERSION"),
    ("commit pedido corto", {}, "abc123", "1.0.0", "40 caracteres"),
    ("commit pedido en mayúsculas", {}, "A" * 40, "1.0.0", "40 caracteres"),
    ("commit pedido vacío", {}, "", "1.0.0", "40 caracteres"),
])
def test_zip_invalido(tmp_path, caso, kw, commit, version, texto):
    with pytest.raises(ra.ErrorRelease, match=re.escape(texto)):
        ra.validar_zip(zip_sintetico(tmp_path / "a.zip", **kw), version, commit)


def test_commit_con_salto_de_linea_final_se_rechaza(tmp_path):
    with pytest.raises(ra.ErrorRelease, match="40 caracteres"):
        ra.validar_zip(zip_sintetico(tmp_path / "a.zip"), "1.0.0", SHA + "\n")


def test_zip_inexistente_corrupto_y_no_zip(tmp_path):
    with pytest.raises(ra.ErrorRelease, match="no existe"):
        ra.validar_zip(tmp_path / "no.zip", "1.0.0", SHA)
    (tmp_path / "x.zip").write_bytes(b"esto no es un zip")
    with pytest.raises(ra.ErrorRelease, match="zip válido"):
        ra.validar_zip(tmp_path / "x.zip", "1.0.0", SHA)
    bueno = zip_sintetico(tmp_path / "b.zip")
    datos = bytearray(bueno.read_bytes())
    i = bytes(datos).index(b"x = 1\n")                           # contenido de un archivo que la validación NO lee: solo `testzip` lo detecta
    datos[i] ^= 0x01
    (tmp_path / "c.zip").write_bytes(bytes(datos))
    with pytest.raises(ra.ErrorRelease, match="dañado"):
        ra.validar_zip(tmp_path / "c.zip", "1.0.0", SHA)


def test_build_info_no_json_o_no_objeto(tmp_path):
    for contenido in (b"no json", b"\xff\xfe", b"[1, 2]", b'"texto"', b"null"):
        z = tmp_path / "z.zip"
        with zipfile.ZipFile(z, "w") as zz:
            zz.writestr(ra.BUILD_INFO, contenido)
            zz.writestr(ra.VERSION_PY, VERSION_PY)
        with pytest.raises(ra.ErrorRelease):
            ra.validar_zip(z, "1.0.0", SHA)


def test_archivos_de_identificacion_desmesurados_se_rechazan(tmp_path):
    z = zip_sintetico(tmp_path / "g.zip", extra={})
    with zipfile.ZipFile(z, "w") as zz:
        zz.writestr(ra.BUILD_INFO, json.dumps({"esquema": "build_info/1", "commit": SHA, "relleno": "x" * 20_000}))
        zz.writestr(ra.VERSION_PY, VERSION_PY)
    with pytest.raises(ra.ErrorRelease, match="tamaño"):
        ra.validar_zip(z, "1.0.0", SHA)


# ----------------------------------------------------------------------------------------------------------------- preparar
def test_preparar_escribe_los_tres_archivos_y_el_sha_es_el_del_zip(tmp_path):
    z = zip_sintetico(tmp_path / "app.zip")
    r = ra.preparar(z, SHA, tmp_path / "salida")
    esperado = hashlib.sha256(z.read_bytes()).hexdigest()
    assert r == {"etiqueta": f"app-v{ra.version_del_repositorio()}", "version": ra.version_del_repositorio(), "sha256": esperado, "commit": SHA} \
        if ra.version_del_repositorio() == "1.0.0" else r["sha256"] == esperado
    salida = tmp_path / "salida"
    assert sorted(p.name for p in salida.iterdir()) == ["NOTAS.md", "app.zip", "app.zip.sha256"]
    assert (salida / "app.zip").read_bytes() == z.read_bytes()
    assert (salida / "app.zip.sha256").read_text(encoding="utf-8") == f"{esperado}  app.zip\n"
    notas = (salida / "NOTAS.md").read_text(encoding="utf-8")
    assert SHA in notas and esperado in notas and r["etiqueta"] in notas


def test_el_archivo_sha256_es_verificable_con_sha256sum(tmp_path):
    z = zip_sintetico(tmp_path / "app.zip")
    ra.preparar(z, SHA, tmp_path / "salida")
    r = subprocess.run(["sha256sum", "-c", "app.zip.sha256"], cwd=tmp_path / "salida", capture_output=True, text=True)
    assert r.returncode == 0 and "app.zip: OK" in r.stdout


def test_preparar_no_escribe_nada_si_el_zip_no_vale(tmp_path):
    z = zip_sintetico(tmp_path / "app.zip", commit="b" * 40)
    with pytest.raises(ra.ErrorRelease):
        ra.preparar(z, SHA, tmp_path / "salida")
    assert not (tmp_path / "salida").exists()


def test_preparar_no_sobrescribe_una_carpeta_con_contenido(tmp_path):
    z = zip_sintetico(tmp_path / "app.zip")
    (tmp_path / "salida").mkdir()
    (tmp_path / "salida" / "otro.txt").write_text("no tocar")
    with pytest.raises(ra.ErrorRelease, match="nueva o estar vacía"):
        ra.preparar(z, SHA, tmp_path / "salida")
    assert (tmp_path / "salida" / "otro.txt").read_text() == "no tocar" and not (tmp_path / "salida" / "app.zip").exists()
    (tmp_path / "vacia").mkdir()
    ra.preparar(z, SHA, tmp_path / "vacia")                      # una carpeta vacía sí se acepta
    with pytest.raises(ra.ErrorRelease):
        ra.preparar(z, SHA, tmp_path / "vacia")                  # y una segunda vez ya no: no se reescribe


def test_preparar_con_version_del_repositorio_distinta_a_la_empaquetada(tmp_path):
    raiz = tmp_path / "repo" / "backend" / "app"
    raiz.mkdir(parents=True)
    (raiz / "version.py").write_text('APP_VERSION = "9.9.9"\n', encoding="utf-8")
    with pytest.raises(ra.ErrorRelease, match="empaqueta APP_VERSION 1.0.0"):
        ra.preparar(zip_sintetico(tmp_path / "app.zip"), SHA, tmp_path / "s", root=tmp_path / "repo")


def test_cli_exito_y_error(tmp_path):
    z = zip_sintetico(tmp_path / "app.zip")
    ok = subprocess.run([sys.executable, str(ROOT / "tools/release_app.py"), "--zip", str(z), "--commit", SHA, "--out", str(tmp_path / "o")],
                        capture_output=True, text=True)
    assert ok.returncode == 0
    clave = dict(l.split("=", 1) for l in ok.stdout.strip().splitlines())
    assert set(clave) == {"etiqueta", "version", "sha256", "commit"} and clave["commit"] == SHA
    mal = subprocess.run([sys.executable, str(ROOT / "tools/release_app.py"), "--zip", str(z), "--commit", "b" * 40, "--out", str(tmp_path / "p")],
                         capture_output=True, text=True)
    assert mal.returncode == 1 and mal.stdout == "" and "ERROR:" in mal.stderr and not (tmp_path / "p").exists()


# ----------------------------------------------------------------------------------------------------------------- app.zip REAL de build_site
@pytest.fixture(scope="module")
def sitio_real(tmp_path_factory):
    base = tmp_path_factory.mktemp("sitio")
    wheels = base / "w"
    wheels.mkdir()
    for n in ("python_pptx-1.0.2-py3-none-any.whl", "XlsxWriter-3.3.1-py3-none-any.whl", "openpyxl-3.1.5-py2.py3-none-any.whl", "et_xmlfile-2.0.0-py3-none-any.whl"):
        (wheels / n).write_bytes(b"x")
    out = base / "_site"
    env = {"PATH": "/usr/bin:/bin:/usr/local/bin", "GITHUB_SHA": SHA}
    subprocess.run([sys.executable, str(ROOT / "tools/build_site.py"), "--out", str(out), "--wheels", str(wheels)], check=True, env=env, cwd=ROOT,
                   capture_output=True)
    return out / "app.zip"


def test_el_app_zip_real_con_sha_de_actions_se_valida_si_el_arbol_esta_limpio(sitio_real):
    with zipfile.ZipFile(sitio_real) as z:
        sellado = json.loads(z.read(ra.BUILD_INFO))["commit"]
    if sellado.endswith("+dirty") or sellado == "desconocido":
        # Es lo que debe pasar con un árbol sin confirmar: la release lo rechaza. En CI el árbol está limpio y esta rama no se ejecuta.
        with pytest.raises(ra.ErrorRelease):
            ra.validar_zip(sitio_real, ra.version_del_repositorio(), SHA)
    else:
        assert sellado == SHA
        ra.validar_zip(sitio_real, ra.version_del_repositorio(), SHA)


def test_el_app_zip_real_empaqueta_la_version_del_repositorio_y_se_prepara_completo(sitio_real, tmp_path):
    with zipfile.ZipFile(sitio_real) as z:
        assert ra.leer_app_version(z.read(ra.VERSION_PY).decode()) == ra.version_del_repositorio()
    # Con un commit distinto del sellado la release se rechaza SIEMPRE (esto no depende de que el árbol esté limpio).
    with pytest.raises(ra.ErrorRelease, match="compilado de"):
        ra.preparar(sitio_real, "c" * 40, tmp_path / "x")


# ----------------------------------------------------------------------------------------------------------------- estructura del workflow
WF = ROOT / ".github" / "workflows" / "release.yml"
PINS = {"actions/checkout": "v4", "actions/setup-python": "v5", "actions/upload-artifact": "v4"}


def problemas_workflow(texto: str) -> list[str]:
    """Garantías de seguridad del workflow. Devuelve la lista de incumplimientos (vacía = correcto)."""
    p = []
    d = yaml.safe_load(texto)
    on = d.get("on", d.get(True))
    if not isinstance(on, dict) or set(on) != {"workflow_dispatch"}:
        p.append("debe dispararse solo con workflow_dispatch")
    entrada = ((on or {}).get("workflow_dispatch") or {}).get("inputs", {}).get("publicar") if isinstance(on, dict) else None
    if not entrada or entrada.get("type") != "boolean" or entrada.get("default") is not False:
        p.append("la entrada «publicar» debe ser booleana y valer false por omisión (ensayo)")
    if d.get("permissions") != {"contents": "read"}:
        p.append("los permisos globales deben ser solo contents: read")
    job = d["jobs"]["release"]
    if job.get("permissions") != {"contents": "write"}:
        p.append("el job debe pedir solo contents: write")
    if job.get("if") != "github.ref == 'refs/heads/main'":
        p.append("el job debe limitarse a refs/heads/main")
    if (d.get("concurrency") or {}).get("cancel-in-progress") is not False:
        p.append("la concurrencia no debe cancelar una publicación en curso")
    pasos = job["steps"]
    for s in pasos:
        u = s.get("uses")
        if u:
            nombre, _, ver = u.partition("@")
            if PINS.get(nombre) != ver:
                p.append(f"acción sin la versión fijada esperada: {u}")
    crear = [s for s in pasos if "gh release create" in s.get("run", "")]
    if len(crear) != 1 or crear[0].get("if") != "${{ inputs.publicar }}":
        p.append("gh release create debe existir una vez y solo bajo inputs.publicar")
    elif "--target \"$GITHUB_SHA\"" not in crear[0]["run"]:
        p.append("la etiqueta debe apuntar a $GITHUB_SHA")
    idx = {s.get("name", s.get("uses", "")): i for i, s in enumerate(pasos)}
    orden = [i for i, s in enumerate(pasos) if "tools/build_site.py" in s.get("run", "")] + \
            [i for i, s in enumerate(pasos) if "tools/release_app.py" in s.get("run", "")] + \
            [i for i, s in enumerate(pasos) if "ls-remote" in s.get("run", "")] + [i for i, s in enumerate(pasos) if "gh release create" in s.get("run", "")]
    if len(orden) != 4 or orden != sorted(orden):
        p.append("el orden debe ser: construir → validar → comprobar etiqueta → publicar")
    prohibidos = ("--clobber", "release delete", "tag -f", "tag --force", "push --force", "push -f", "--prerelease", "git push", "secrets.")
    for pr in prohibidos:
        if pr in texto:
            p.append(f"no debe contener «{pr}»")
    if not any("sha256sum -c" in s.get("run", "") for s in pasos if s.get("if") == "${{ inputs.publicar }}"):
        p.append("tras publicar debe verificarse el SHA-256 del asset descargado")
    del idx
    return p


def test_el_workflow_cumple_todas_las_garantias():
    assert problemas_workflow(WF.read_text(encoding="utf-8")) == []


def test_el_workflow_usa_las_mismas_versiones_de_acciones_que_pages():
    pages = (ROOT / ".github/workflows/pages.yml").read_text(encoding="utf-8")
    for nombre, ver in (("actions/checkout", "v4"), ("actions/setup-python", "v5")):
        assert f"{nombre}@{ver}" in pages and f"{nombre}@{ver}" in WF.read_text(encoding="utf-8")


def test_el_workflow_usa_el_script_del_repositorio_con_argumentos_existentes():
    texto = WF.read_text(encoding="utf-8")
    assert (ROOT / "tools/release_app.py").is_file() and (ROOT / "tools/build_site.py").is_file()
    helpv = subprocess.run([sys.executable, str(ROOT / "tools/release_app.py"), "--help"], capture_output=True, text=True).stdout
    for flag in re.findall(r"tools/release_app\.py((?: --[a-z]+ \S+)+)", texto)[0].split():
        if flag.startswith("--"):
            assert flag in helpv, flag


@pytest.mark.parametrize("mutacion,reemplazo", [
    ("workflow_dispatch:\n    inputs:", "push:\n      branches: [main]\n  workflow_dispatch:\n    inputs:"),
    ("        default: false", "        default: true"),
    ("permissions:\n  contents: read\n\nconcurrency", "permissions:\n  contents: write\n\nconcurrency"),
    ("    if: github.ref == 'refs/heads/main'", "    if: always()"),
    ("        if: ${{ inputs.publicar }}\n        run: |\n          gh release create", "        run: |\n          gh release create"),
    ("--target \"$GITHUB_SHA\"", "--target main"),
    ("--notes-file _release/NOTAS.md", "--notes-file _release/NOTAS.md --clobber"),
    ("actions/checkout@v4", "actions/checkout@main"),
    ("          sha256sum -c app.zip.sha256\n", ""),
    ("cancel-in-progress: false", "cancel-in-progress: true"),
    ("GH_TOKEN: ${{ github.token }}", "GH_TOKEN: ${{ secrets.PAT }}"),
])
def test_mutaciones_deliberadas_del_workflow_son_detectadas(mutacion, reemplazo):
    texto = WF.read_text(encoding="utf-8")
    assert texto.count(mutacion) == 1, mutacion
    assert problemas_workflow(texto.replace(mutacion, reemplazo)), mutacion


def test_el_workflow_no_se_dispara_con_push_ni_pr_ni_programacion():
    on = yaml.safe_load(WF.read_text(encoding="utf-8")).get("on") or yaml.safe_load(WF.read_text(encoding="utf-8"))[True]
    assert list(on) == ["workflow_dispatch"]


def test_release_yml_no_se_empaqueta_en_el_sitio():
    import tools.build_site as bs
    assert ".github/workflows/release.yml" not in bs.PACKAGED          # añadirlo cambiaría el cálculo de «dirty» y tools/build_site.py es protegido
