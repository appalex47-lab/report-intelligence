"""Fase 3A-5 (A-5) · `tools/release_app.py` y `.github/workflows/release.yml`. Se ejecuta en CI.

Qué cubre: la lógica de validación y preparación de la release (con zips sintéticos y con el `app.zip` REAL de `build_site.py`). La verificación de
etiqueta/CI/release está en test_release_publicacion.py y la estructura del workflow en test_release_workflow.py. Qué NO cubre, y se dice
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
    ok = subprocess.run([sys.executable, str(ROOT / "tools/release_app.py"), "preparar", "--zip", str(z), "--commit", SHA, "--out", str(tmp_path / "o")],
                        capture_output=True, text=True)
    assert ok.returncode == 0
    clave = dict(l.split("=", 1) for l in ok.stdout.strip().splitlines())
    assert set(clave) == {"etiqueta", "version", "sha256", "commit"} and clave["commit"] == SHA
    mal = subprocess.run([sys.executable, str(ROOT / "tools/release_app.py"), "preparar", "--zip", str(z), "--commit", "b" * 40, "--out", str(tmp_path / "p")],
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


# ----------------------------------------------------------------------------------------------------------------- endurecimiento del zip
def _zip_con(ruta, entradas, modo_symlink=()):
    import stat as _st
    import warnings
    with zipfile.ZipFile(ruta, "w") as z, warnings.catch_warnings():
        warnings.simplefilter("ignore")                       # el módulo avisa de los nombres duplicados; justo lo que se quiere probar
        z.writestr(ra.BUILD_INFO, json.dumps({"esquema": "build_info/1", "commit": SHA}))
        z.writestr(ra.VERSION_PY, VERSION_PY)
        for nombre, datos in entradas:
            if nombre in modo_symlink:
                zi = zipfile.ZipInfo(nombre)
                zi.external_attr = (_st.S_IFLNK | 0o777) << 16
                z.writestr(zi, datos)
            else:
                z.writestr(nombre, datos)
    return ruta


@pytest.mark.parametrize("nombre", ["../evil.py", "backend/../../evil.py", "/etc/passwd", "C:/Windows/x", "a\\b.py", "backend//x.py", "./x.py",
                                    "backend/./x.py"])    # (un NUL en el nombre no es construible: `zipfile` lo trunca al escribir)
def test_rutas_peligrosas_en_el_zip_se_rechazan(tmp_path, nombre):
    with pytest.raises(ra.ErrorRelease, match="ruta no permitida"):
        ra.validar_zip(_zip_con(tmp_path / "z.zip", [(nombre, b"x")]), "1.0.0", SHA)


def test_entradas_duplicadas_se_rechazan(tmp_path):
    with pytest.raises(ra.ErrorRelease, match="duplicada"):
        ra.validar_zip(_zip_con(tmp_path / "z.zip", [("backend/app/otro.py", b"1"), ("backend/app/otro.py", b"2")]), "1.0.0", SHA)
    with pytest.raises(ra.ErrorRelease, match="duplicada"):                       # y duplicar un archivo de identificación: dos versiones del mismo
        ra.validar_zip(_zip_con(tmp_path / "y.zip", [(ra.VERSION_PY, b'APP_VERSION = "9.9.9"\n')]), "1.0.0", SHA)


def test_enlaces_simbolicos_se_rechazan(tmp_path):
    z = _zip_con(tmp_path / "z.zip", [("backend/app/enlace", b"/etc/passwd")], modo_symlink=("backend/app/enlace",))
    with pytest.raises(ra.ErrorRelease, match="enlace simbólico"):
        ra.validar_zip(z, "1.0.0", SHA)


def test_demasiadas_entradas_y_tamano_descomprimido(tmp_path, monkeypatch):
    z = _zip_con(tmp_path / "z.zip", [(f"backend/app/f{i}.py", b"x") for i in range(10)])
    monkeypatch.setattr(ra, "MAX_ENTRADAS", 5)
    with pytest.raises(ra.ErrorRelease, match="demasiadas entradas"):
        ra.validar_zip(z, "1.0.0", SHA)
    monkeypatch.setattr(ra, "MAX_ENTRADAS", 5000)
    monkeypatch.setattr(ra, "MAX_DESCOMPRIMIDO", 50)
    with pytest.raises(ra.ErrorRelease, match="descomprimido"):
        ra.validar_zip(z, "1.0.0", SHA)


def test_archivos_de_identificacion_vacios_se_rechazan(tmp_path):
    for vacio in (ra.BUILD_INFO, ra.VERSION_PY):
        z = tmp_path / f"{Path(vacio).name}.zip"
        with zipfile.ZipFile(z, "w") as zz:
            zz.writestr(ra.BUILD_INFO, b"" if vacio == ra.BUILD_INFO else json.dumps({"esquema": "build_info/1", "commit": SHA}))
            zz.writestr(ra.VERSION_PY, b"" if vacio == ra.VERSION_PY else VERSION_PY)
        with pytest.raises(ra.ErrorRelease, match="vacío"):
            ra.validar_zip(z, "1.0.0", SHA)


def test_directorios_y_archivos_normales_no_se_confunden_con_rutas_peligrosas(tmp_path):
    z = _zip_con(tmp_path / "z.zip", [("backend/app/web/", b""), ("profiles/aetops/mensual.yaml", b"a: 1"), ("frontend/index.html", b"<html>"),
                                      ("backend/app/.oculto", b"x"), ("tools/make_machotes.py", b"x")])
    ra.validar_zip(z, "1.0.0", SHA)


def test_el_app_zip_real_pasa_la_revision_de_entradas(sitio_real):
    with zipfile.ZipFile(sitio_real) as z:
        ra._revisar_entradas(z)


# ----------------------------------------------------------------------------------------------------------------- verificar_carpeta (job de construcción → job de publicación)
def _carpeta(tmp_path, **kw):
    z = zip_sintetico(tmp_path / "app.zip", **kw)
    return ra.preparar(z, SHA, tmp_path / "rel")


def test_la_carpeta_recibida_es_la_construida(tmp_path):
    r = _carpeta(tmp_path)
    ra.verificar_carpeta(tmp_path / "rel", r["version"], SHA, r["sha256"], r["etiqueta"])


@pytest.mark.parametrize("que", ["zip_distinto", "sha_distinto", "linea_sha", "notas", "falta", "sobra", "tag_distinta", "commit_distinto"])
def test_la_carpeta_alterada_se_rechaza(tmp_path, que):
    r = _carpeta(tmp_path)
    d, sha, commit, tag = tmp_path / "rel", r["sha256"], SHA, r["etiqueta"]
    if que == "zip_distinto":
        zip_sintetico(d / "app.zip", extra={"backend/app/mas.py": "x"})
    elif que == "sha_distinto":
        sha = "0" * 64
    elif que == "linea_sha":
        (d / "app.zip.sha256").write_text(f"{'0' * 64}  app.zip\n", encoding="utf-8")
    elif que == "notas":
        (d / "NOTAS.md").write_text("otra cosa", encoding="utf-8")
    elif que == "falta":
        (d / "NOTAS.md").unlink()
    elif que == "sobra":
        (d / "extra.txt").write_text("x")
    elif que == "tag_distinta":
        tag = "app-v9.9.9"
    elif que == "commit_distinto":
        commit = "b" * 40
    with pytest.raises(ra.ErrorRelease):
        ra.verificar_carpeta(d, r["version"], commit, sha, tag)


def test_la_carpeta_con_sha256_malformado_o_inexistente(tmp_path):
    r = _carpeta(tmp_path)
    for sha in ("", "abc", "G" * 64, None, "A" * 64):
        with pytest.raises(ra.ErrorRelease):
            ra.verificar_carpeta(tmp_path / "rel", r["version"], SHA, sha)
    with pytest.raises(ra.ErrorRelease, match="no existe"):
        ra.verificar_carpeta(tmp_path / "nada", r["version"], SHA, r["sha256"])


def test_la_salida_de_la_cli_nunca_trae_saltos_de_linea_dentro_de_un_valor(tmp_path):
    with pytest.raises(ra.ErrorRelease, match="salto de línea"):
        ra._imprimir({"etiqueta": "app-v1.0.0\nmalicioso=1"}, ("etiqueta",))
