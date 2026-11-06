"""Fase 3A-5 · vínculo versión → etiqueta → commit → build → artefacto → SHA-256 y CI del SHA exacto (`tools/release_app.py`). Se ejecuta en CI.

Todo se prueba con respuestas de la API de GitHub simuladas (JSON con la forma documentada) y zips sintéticos: no se publica ninguna release, no se
crea ninguna etiqueta y no se llama a GitHub."""
import importlib.util
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("release_app", ROOT / "tools" / "release_app.py")
ra = importlib.util.module_from_spec(spec)
sys.modules.setdefault("release_app", ra)
spec.loader.exec_module(ra)

SHA = "a" * 40
OTRO = "b" * 40
SHA_TAG_OBJ = "c" * 40
VERSION = ra.version_del_repositorio()
TAG = ra.etiqueta(VERSION)
VERSION_PY = f'APP_VERSION = "{VERSION}"\nENGINE_VERSION = "1.0.0"\n'


# ----------------------------------------------------------------------------------------------------------------- simulación de GitHub
def zip_sintetico(ruta, *, commit=SHA, version_py=VERSION_PY):
    with zipfile.ZipFile(ruta, "w") as z:
        z.writestr(ra.BUILD_INFO, json.dumps({"esquema": "build_info/1", "commit": commit}))
        z.writestr(ra.VERSION_PY, version_py)
        z.writestr("backend/app/otro.py", "x = 1\n")
    return ruta


def run(ruta=".github/workflows/tests.yml", *, status="completed", conclusion="success", sha=SHA, n=1, event="push"):
    return {"id": n, "run_number": n, "path": ruta, "head_sha": sha, "status": status, "conclusion": conclusion, "event": event, "name": ruta}


def respuesta(*runs, total=None):
    return {"total_count": len(runs) if total is None else total, "workflow_runs": list(runs)}


def ref_ligera(commit=SHA, tag=TAG):
    return {"ref": f"refs/tags/{tag}", "object": {"type": "commit", "sha": commit}}


def ref_anotada(tag=TAG):
    return {"ref": f"refs/tags/{tag}", "object": {"type": "tag", "sha": SHA_TAG_OBJ}}


def tag_anotada(commit=SHA, tipo="commit", sha=SHA_TAG_OBJ):
    return {"sha": sha, "tag": TAG, "object": {"type": tipo, "sha": commit}}


class Mundo:
    """Una release preparada de verdad con `preparar`, y su 'descarga desde GitHub' en otra carpeta."""

    def __init__(self, tmp_path, *, commit=SHA, borrador=False):
        zip_sintetico(tmp_path / "app.zip", commit=commit)
        self.r = ra.preparar(tmp_path / "app.zip", commit, tmp_path / "rel")
        self.descargas = tmp_path / "dl"
        self.descargas.mkdir()
        for n in (ra.ASSET_ZIP, ra.ASSET_SHA):
            (self.descargas / n).write_bytes((tmp_path / "rel" / n).read_bytes())
        self.release = {"tag_name": TAG, "draft": borrador, "prerelease": False, "body": (tmp_path / "rel" / ra.ASSET_NOTAS).read_text(encoding="utf-8"),
                        "assets": [{"name": n, "state": "uploaded", "size": (self.descargas / n).stat().st_size} for n in (ra.ASSET_ZIP, ra.ASSET_SHA)]}
        self.sha = self.r["sha256"]

    def verificar(self, *, publicada=True, commit=SHA, ref=None, tag_obj=None, sha=None):
        return ra.verificar_release(self.release, self.descargas, VERSION, commit, sha or self.sha, publicada=publicada,
                                    ref=ref if ref is not None else ref_ligera(), tag_anotada=tag_obj)


# ----------------------------------------------------------------------------------------------------------------- 1-2: etiquetas ligera y anotada
def test_etiqueta_ligera_valida_apunta_al_commit():
    assert ra.commit_de_etiqueta(ref_ligera(), None, TAG) == SHA


def test_etiqueta_anotada_valida_se_resuelve_a_traves_del_objeto_tag():
    assert ra.commit_de_etiqueta(ref_anotada(), tag_anotada(), TAG) == SHA


def test_la_release_publicada_se_verifica_con_etiqueta_ligera_y_con_anotada(tmp_path):
    w = Mundo(tmp_path)
    assert w.verificar(ref=ref_ligera())["apunta_a"] == SHA
    assert w.verificar(ref=ref_anotada(), tag_obj=tag_anotada())["apunta_a"] == SHA


# ----------------------------------------------------------------------------------------------------------------- 3: etiqueta que apunta a otro commit
def test_etiqueta_ligera_que_apunta_a_otro_commit_se_rechaza(tmp_path):
    w = Mundo(tmp_path)
    with pytest.raises(ra.ErrorRelease, match="no al commit compilado"):
        w.verificar(ref=ref_ligera(OTRO))


def test_etiqueta_anotada_que_apunta_a_otro_commit_se_rechaza(tmp_path):
    w = Mundo(tmp_path)
    with pytest.raises(ra.ErrorRelease, match="no al commit compilado"):
        w.verificar(ref=ref_anotada(), tag_obj=tag_anotada(OTRO))


@pytest.mark.parametrize("ref,obj,texto", [
    (ref_anotada(), None, "falta el objeto de la etiqueta anotada"),
    (ref_anotada(), tag_anotada(sha="d" * 40), "no corresponde"),
    (ref_anotada(), tag_anotada(tipo="tag"), "directamente a un commit"),
    (ref_anotada(), tag_anotada(tipo="tree"), "directamente a un commit"),
    ({"ref": f"refs/tags/{TAG}", "object": {"type": "tree", "sha": SHA}}, None, "tipo 'tree'"),
    ({"ref": f"refs/tags/{TAG}", "object": {"type": "blob", "sha": SHA}}, None, "tipo 'blob'"),
    ({"ref": "refs/tags/app-v9.9.9", "object": {"type": "commit", "sha": SHA}}, None, "no es la de la etiqueta"),
    ({"ref": f"refs/tags/{TAG}", "object": {"type": "commit", "sha": "no-es-sha"}}, None, "40 caracteres"),
    ({"ref": f"refs/tags/{TAG}", "object": {"type": "commit", "sha": SHA.upper()}}, None, "40 caracteres"),
    ({"ref": f"refs/tags/{TAG}", "object": "texto"}, None, "formato"),
    ({"ref": f"refs/tags/{TAG}"}, None, "formato"),
    ([], None, "formato"),
    (None, None, "formato"),
])
def test_referencias_y_objetos_de_etiqueta_inconsistentes_se_rechazan(ref, obj, texto):
    with pytest.raises(ra.ErrorRelease, match=texto):
        ra.commit_de_etiqueta(ref, obj, TAG)


# ----------------------------------------------------------------------------------------------------------------- 4: etiqueta inexistente
@pytest.mark.parametrize("respuesta_api", [{"message": "Not Found", "documentation_url": "https://docs.github.com"}, {}, [], "", None])
def test_etiqueta_inexistente_en_una_release_publicada_se_rechaza(tmp_path, respuesta_api):
    w = Mundo(tmp_path)
    with pytest.raises(ra.ErrorRelease):
        ra.verificar_release(w.release, w.descargas, VERSION, SHA, w.sha, publicada=True, ref=respuesta_api)


def test_publicada_sin_pasar_la_referencia_se_rechaza(tmp_path):
    w = Mundo(tmp_path)
    with pytest.raises(ra.ErrorRelease):
        ra.verificar_release(w.release, w.descargas, VERSION, SHA, w.sha, publicada=True)


# ----------------------------------------------------------------------------------------------------------------- 5: etiqueta duplicada o ya utilizada
def test_etiqueta_libre_si_no_hay_ni_referencia_ni_release():
    ra.verificar_etiqueta_libre([], [], TAG)
    ra.verificar_etiqueta_libre([], ["app-v0.9.0", "otra"], TAG)


def test_etiqueta_ya_existente_como_referencia_se_rechaza():
    with pytest.raises(ra.ErrorRelease, match="ya existe"):
        ra.verificar_etiqueta_libre([ref_ligera()], [], TAG)
    with pytest.raises(ra.ErrorRelease, match="ya existe"):
        ra.verificar_etiqueta_libre([ref_anotada()], [], TAG)


def test_etiqueta_con_release_publicada_o_borrador_se_rechaza():
    with pytest.raises(ra.ErrorRelease, match="ya existe una release"):
        ra.verificar_etiqueta_libre([], [TAG], TAG)
    with pytest.raises(ra.ErrorRelease, match="ya existe una release"):
        ra.verificar_etiqueta_libre([], ["otra", TAG], TAG)


def test_matching_refs_devuelve_prefijos_pero_solo_la_coincidencia_exacta_bloquea():
    parecida = {"ref": f"refs/tags/{TAG}0", "object": {"type": "commit", "sha": SHA}}
    ra.verificar_etiqueta_libre([parecida], [f"{TAG}0"], TAG)             # app-v1.0.00 no es la misma etiqueta
    with pytest.raises(ra.ErrorRelease):
        ra.verificar_etiqueta_libre([parecida, ref_ligera()], [], TAG)


@pytest.mark.parametrize("refs,releases", [({"message": "Not Found"}, []), (None, []), ("x", []), ([1], []), ([], None), ([], "texto"), ([], [1, 2]),
                                           ([], {"a": 1})])
def test_respuestas_con_formato_inesperado_no_cuentan_como_etiqueta_libre(refs, releases):
    with pytest.raises(ra.ErrorRelease, match="formato"):
        ra.verificar_etiqueta_libre(refs, releases, TAG)


@pytest.mark.parametrize("tag", ["", "v1.0.0", "app-v1.0", "app-v01.0.0", "app-v1.0.0\n", "otra", None, "app-v1.0.0-rc1"])
def test_nombre_de_etiqueta_invalido_se_rechaza(tag):
    with pytest.raises(ra.ErrorRelease):
        ra.verificar_etiqueta_libre([], [], tag)


# ----------------------------------------------------------------------------------------------------------------- 6: artefacto que no corresponde a la versión
def test_artefacto_con_otra_version_empaquetada_se_rechaza(tmp_path):
    w = Mundo(tmp_path)
    zip_sintetico(w.descargas / ra.ASSET_ZIP, version_py='APP_VERSION = "9.9.9"\n')
    (w.descargas / ra.ASSET_SHA).write_text(f"{ra.sha256_archivo(w.descargas / ra.ASSET_ZIP)}  app.zip\n", encoding="utf-8")
    nuevo = ra.sha256_archivo(w.descargas / ra.ASSET_ZIP)
    for a in w.release["assets"]:
        a["size"] = (w.descargas / a["name"]).stat().st_size
    with pytest.raises(ra.ErrorRelease, match="empaqueta APP_VERSION 9.9.9"):
        w.verificar(sha=nuevo)


def test_artefacto_compilado_de_otro_commit_no_se_presenta_como_el_de_la_etiqueta(tmp_path):
    """Un zip válido, con su propio hash, pero compilado de OTRO commit: la etiqueta apunta a SHA y el zip dice OTRO."""
    w = Mundo(tmp_path, commit=OTRO)
    with pytest.raises(ra.ErrorRelease, match="compilado de"):
        w.verificar(commit=SHA)
    assert w.verificar(commit=OTRO, ref=ref_ligera(OTRO))["apunta_a"] == OTRO       # y coherente consigo mismo sí pasa


def test_artefacto_de_otra_version_ni_con_etiqueta_correcta_ni_con_hash_correcto_pasa(tmp_path):
    w = Mundo(tmp_path)
    w.release["tag_name"] = "app-v9.9.9"
    with pytest.raises(ra.ErrorRelease, match="no de"):
        w.verificar()


# ----------------------------------------------------------------------------------------------------------------- 7: hash incorrecto
def test_hash_esperado_distinto_al_del_zip_descargado(tmp_path):
    w = Mundo(tmp_path)
    with pytest.raises(ra.ErrorRelease, match="SHA-256"):
        w.verificar(sha="0" * 64)


def test_hash_declarado_en_el_archivo_sha256_distinto(tmp_path):
    w = Mundo(tmp_path)
    (w.descargas / ra.ASSET_SHA).write_text(f"{'0' * 64}  app.zip\n", encoding="utf-8")
    w.release["assets"][1]["size"] = (w.descargas / ra.ASSET_SHA).stat().st_size
    with pytest.raises(ra.ErrorRelease, match="no coincide"):
        w.verificar()


@pytest.mark.parametrize("contenido", ["", "no es un hash\n", f"{'a' * 64} app.zip\n", f"{'a' * 64}  otro.zip\n", f"{'A' * 64}  app.zip\n", f"{'a' * 63}  app.zip\n"])
def test_formato_incorrecto_del_archivo_sha256(tmp_path, contenido):
    w = Mundo(tmp_path)
    (w.descargas / ra.ASSET_SHA).write_text(contenido, encoding="utf-8")
    w.release["assets"][1]["size"] = (w.descargas / ra.ASSET_SHA).stat().st_size
    with pytest.raises(ra.ErrorRelease, match="formato"):
        w.verificar()


def test_zip_descargado_alterado_tras_la_subida(tmp_path):
    w = Mundo(tmp_path)
    datos = bytearray((w.descargas / ra.ASSET_ZIP).read_bytes())
    datos[-1] ^= 0xFF
    (w.descargas / ra.ASSET_ZIP).write_bytes(bytes(datos))
    with pytest.raises(ra.ErrorRelease):
        w.verificar()


# ----------------------------------------------------------------------------------------------------------------- 8-9: asset inexistente y descarga fallida
def test_asset_inexistente_en_la_release(tmp_path):
    w = Mundo(tmp_path)
    w.release["assets"] = w.release["assets"][:1]
    with pytest.raises(ra.ErrorRelease, match="exactamente"):
        w.verificar()
    w.release["assets"] = []
    with pytest.raises(ra.ErrorRelease, match="exactamente"):
        w.verificar()


def test_assets_de_mas_o_duplicados(tmp_path):
    w = Mundo(tmp_path)
    w.release["assets"].append({"name": "extra.txt", "state": "uploaded", "size": 1})
    with pytest.raises(ra.ErrorRelease, match="exactamente"):
        w.verificar()
    w.release["assets"] = [dict(w.release["assets"][0]), dict(w.release["assets"][0])]
    with pytest.raises(ra.ErrorRelease, match="mismo nombre"):
        w.verificar()


def test_descarga_fallida_archivo_ausente(tmp_path):
    w = Mundo(tmp_path)
    (w.descargas / ra.ASSET_ZIP).unlink()
    with pytest.raises(ra.ErrorRelease, match="no se descargó"):
        w.verificar()


def test_descarga_incompleta_el_tamano_no_coincide(tmp_path):
    w = Mundo(tmp_path)
    (w.descargas / ra.ASSET_ZIP).write_bytes((w.descargas / ra.ASSET_ZIP).read_bytes()[:-5])
    with pytest.raises(ra.ErrorRelease, match="tamaño"):
        w.verificar()
    w2 = Mundo(tmp_path / "otro") if (tmp_path / "otro").mkdir() is None else None
    (w2.descargas / ra.ASSET_ZIP).write_bytes(b"")
    with pytest.raises(ra.ErrorRelease):
        w2.verificar()


def test_asset_que_no_termino_de_subirse(tmp_path):
    w = Mundo(tmp_path)
    w.release["assets"][0]["state"] = "starter"
    with pytest.raises(ra.ErrorRelease, match="no terminó de subirse"):
        w.verificar()


def test_la_carpeta_de_descargas_con_archivos_ajenos(tmp_path):
    w = Mundo(tmp_path)
    (w.descargas / "otro.bin").write_bytes(b"x")
    with pytest.raises(ra.ErrorRelease, match="no son assets"):
        w.verificar()


# ----------------------------------------------------------------------------------------------------------------- 10: metadatos inconsistentes
def test_borrador_y_publicada_no_se_confunden(tmp_path):
    w = Mundo(tmp_path, borrador=True)
    assert w.verificar(publicada=False)["publicada"] is False
    with pytest.raises(ra.ErrorRelease, match="sigue siendo un borrador"):
        w.verificar(publicada=True)
    w2 = Mundo(tmp_path / "p") if (tmp_path / "p").mkdir() is None else None
    with pytest.raises(ra.ErrorRelease, match="ya no es un borrador"):
        w2.verificar(publicada=False)


def test_prerelease_se_rechaza(tmp_path):
    w = Mundo(tmp_path)
    w.release["prerelease"] = True
    with pytest.raises(ra.ErrorRelease, match="pre-release"):
        w.verificar()


@pytest.mark.parametrize("campo,valor", [("body", ""), ("body", None), ("body", "sin datos"), ("draft", None), ("draft", "false"), ("prerelease", None)])
def test_metadatos_de_la_release_inconsistentes_o_ausentes(tmp_path, campo, valor):
    w = Mundo(tmp_path)
    w.release[campo] = valor
    with pytest.raises(ra.ErrorRelease):
        w.verificar()


@pytest.mark.parametrize("quitar", ["etiqueta", "commit", "sha"])
def test_las_notas_deben_citar_etiqueta_commit_y_sha(tmp_path, quitar):
    w = Mundo(tmp_path)
    cita = {"etiqueta": TAG, "commit": SHA, "sha": w.sha}[quitar]
    w.release["body"] = w.release["body"].replace(cita, "XXX")
    with pytest.raises(ra.ErrorRelease, match="notas"):
        w.verificar()


@pytest.mark.parametrize("release", [None, [], "x", {"tag_name": TAG}, {"tag_name": TAG, "draft": False, "prerelease": False, "assets": "no"}])
def test_release_con_formato_inesperado(tmp_path, release):
    w = Mundo(tmp_path)
    with pytest.raises(ra.ErrorRelease):
        ra.verificar_release(release, w.descargas, VERSION, SHA, w.sha, publicada=True, ref=ref_ligera())


# ----------------------------------------------------------------------------------------------------------------- CI del SHA exacto
def test_ci_valido_ejecucion_de_tests_en_success():
    r = ra.verificar_ci(respuesta(run()), SHA)
    assert r["commit"] == SHA and r["requerido"] == ra.RUTA_TESTS


def test_ci_valido_con_otras_ejecuciones_en_verde_o_omitidas_y_la_propia_release_excluida():
    datos = respuesta(run(n=1), run(".github/workflows/pages.yml", n=2), run(".github/workflows/pdf.yml", conclusion="skipped", n=3),
                      run(".github/workflows/release.yml", status="in_progress", conclusion=None, n=4))
    assert len(ra.verificar_ci(datos, SHA)["ejecuciones_revisadas"]) == 3


def test_la_ruta_del_workflow_con_referencia_se_normaliza():
    ra.verificar_ci(respuesta(run(".github/workflows/tests.yml@refs/heads/main")), SHA)


@pytest.mark.parametrize("conclusion", ["failure", "cancelled", "timed_out", "action_required", "startup_failure", "stale", None, "", "desconocida"])
def test_ci_fallido_cancelado_o_con_conclusion_desconocida_se_rechaza(conclusion):
    with pytest.raises(ra.ErrorRelease, match="no está en verde"):
        ra.verificar_ci(respuesta(run(conclusion=conclusion)), SHA)


@pytest.mark.parametrize("estado", ["in_progress", "queued", "waiting", "requested", "pending", None])
def test_ci_pendiente_se_rechaza(estado):
    with pytest.raises(ra.ErrorRelease, match="pendiente"):
        ra.verificar_ci(respuesta(run(status=estado, conclusion=None)), SHA)


def test_ci_ausente_no_se_interpreta_como_verde():
    with pytest.raises(ra.ErrorRelease, match="no hay una ejecución"):
        ra.verificar_ci(respuesta(), SHA)
    with pytest.raises(ra.ErrorRelease, match="no hay una ejecución"):
        ra.verificar_ci(respuesta(run(".github/workflows/pages.yml")), SHA)             # hay verde, pero no el CI requerido
    with pytest.raises(ra.ErrorRelease, match="no hay una ejecución"):
        ra.verificar_ci(respuesta(run(".github/workflows/release.yml")), SHA)           # la propia release no cuenta como CI
    with pytest.raises(ra.ErrorRelease, match="no hay una ejecución"):
        ra.verificar_ci(respuesta(run(conclusion="skipped")), SHA)                      # tests.yml omitido tampoco demuestra nada


def test_ci_de_otro_sha_se_rechaza_aunque_este_en_verde():
    with pytest.raises(ra.ErrorRelease, match="otro SHA"):
        ra.verificar_ci(respuesta(run(sha=OTRO)), SHA)
    with pytest.raises(ra.ErrorRelease, match="otro SHA"):
        ra.verificar_ci(respuesta(run(n=1), run(".github/workflows/pages.yml", sha=OTRO, n=2)), SHA)
    with pytest.raises(ra.ErrorRelease, match="otro SHA"):
        ra.verificar_ci(respuesta(run(sha=None)), SHA)


def test_un_fallo_en_cualquier_otro_workflow_del_mismo_sha_tambien_bloquea():
    with pytest.raises(ra.ErrorRelease, match="no está en verde"):
        ra.verificar_ci(respuesta(run(n=1), run(".github/workflows/pages.yml", conclusion="failure", n=2)), SHA)


def test_si_el_ci_requerido_se_ejecuto_varias_veces_todas_deben_estar_en_verde():
    with pytest.raises(ra.ErrorRelease, match="no está en verde"):
        ra.verificar_ci(respuesta(run(n=1), run(n=2, conclusion="failure", event="pull_request")), SHA)
    ra.verificar_ci(respuesta(run(n=1), run(n=2, event="pull_request")), SHA)


@pytest.mark.parametrize("datos", [{"message": "Bad credentials"}, {"message": "Not Found"}, {"message": "API rate limit exceeded"}, [], None, "texto", 5,
                                   {"total_count": 1}, {"workflow_runs": []}, {"total_count": "1", "workflow_runs": [run()]},
                                   {"total_count": True, "workflow_runs": [run()]}, {"total_count": 1, "workflow_runs": "no"},
                                   {"total_count": 1, "workflow_runs": [None]}, {"total_count": 1, "workflow_runs": ["x"]}])
def test_error_de_consulta_o_respuesta_con_formato_inesperado_no_cuenta_como_validacion(datos):
    with pytest.raises(ra.ErrorRelease, match="formato"):
        ra.verificar_ci(datos, SHA)


def test_respuesta_incompleta_o_paginada_se_rechaza():
    with pytest.raises(ra.ErrorRelease, match="incompleta"):
        ra.verificar_ci(respuesta(run(), total=5), SHA)                                  # hay más ejecuciones de las devueltas
    muchas = [run(n=i) for i in range(100)]
    with pytest.raises(ra.ErrorRelease, match="incompleta"):
        ra.verificar_ci(respuesta(*muchas), SHA)                                          # tope de la página: puede haber más


def test_commit_invalido_para_el_ci():
    for malo in ("", "abc", SHA.upper(), SHA + "\n", None):
        with pytest.raises(ra.ErrorRelease, match="40 caracteres"):
            ra.verificar_ci(respuesta(run()), malo)


# ----------------------------------------------------------------------------------------------------------------- la CLI de punta a punta (sin GitHub)
def cli(*args):
    return subprocess.run([sys.executable, str(ROOT / "tools/release_app.py"), *map(str, args)], capture_output=True, text=True)


def test_cli_verificar_ci(tmp_path):
    (tmp_path / "ok.json").write_text(json.dumps(respuesta(run())))
    (tmp_path / "mal.json").write_text(json.dumps(respuesta(run(conclusion="failure"))))
    (tmp_path / "error.json").write_text(json.dumps({"message": "Bad credentials"}))
    (tmp_path / "vacio.json").write_text("")
    assert cli("verificar-ci", "--runs", tmp_path / "ok.json", "--commit", SHA).returncode == 0
    for malo in ("mal.json", "error.json", "vacio.json", "no_existe.json"):
        r = cli("verificar-ci", "--runs", tmp_path / malo, "--commit", SHA)
        assert r.returncode == 1 and "ERROR:" in r.stderr, malo


def test_cli_etiqueta_libre(tmp_path):
    (tmp_path / "refs_vacio.json").write_text("[]")
    (tmp_path / "refs_existe.json").write_text(json.dumps([ref_ligera()]))
    (tmp_path / "rel_vacio.txt").write_text("")
    (tmp_path / "rel_existe.txt").write_text(f"otra\n{TAG}\n")
    assert cli("etiqueta-libre", "--tag", TAG, "--refs", tmp_path / "refs_vacio.json", "--releases", tmp_path / "rel_vacio.txt").returncode == 0
    for refs, rel in (("refs_existe.json", "rel_vacio.txt"), ("refs_vacio.json", "rel_existe.txt"), ("refs_vacio.json", "no_existe.txt"),
                      ("no_existe.json", "rel_vacio.txt")):
        assert cli("etiqueta-libre", "--tag", TAG, "--refs", tmp_path / refs, "--releases", tmp_path / rel).returncode == 1, (refs, rel)


def test_cli_verificar_carpeta_y_release_de_punta_a_punta(tmp_path):
    w = Mundo(tmp_path, borrador=True)
    assert cli("verificar-carpeta", "--dir", tmp_path / "rel", "--commit", SHA, "--sha256", w.sha, "--tag", TAG).returncode == 0
    assert cli("verificar-carpeta", "--dir", tmp_path / "rel", "--commit", SHA, "--sha256", "0" * 64, "--tag", TAG).returncode == 1
    (tmp_path / "release.json").write_text(json.dumps(w.release, indent=2))
    ok = cli("verificar-release", "--modo", "borrador", "--release", tmp_path / "release.json", "--dir", w.descargas, "--commit", SHA, "--sha256", w.sha)
    assert ok.returncode == 0, ok.stderr
    w.release["draft"] = False
    (tmp_path / "release.json").write_text(json.dumps(w.release, indent=2) + json.dumps(w.release))             # dos objetos: ambiguo
    dos = cli("verificar-release", "--modo", "publicada", "--release", tmp_path / "release.json", "--dir", w.descargas, "--commit", SHA,
              "--sha256", w.sha, "--ref", tmp_path / "ref.json")
    assert dos.returncode == 1 and "exactamente una release" in dos.stderr
    (tmp_path / "release.json").write_text(json.dumps(w.release, indent=2))
    (tmp_path / "ref.json").write_text(json.dumps(ref_ligera()))
    ok = cli("verificar-release", "--modo", "publicada", "--release", tmp_path / "release.json", "--dir", w.descargas, "--commit", SHA,
             "--sha256", w.sha, "--ref", tmp_path / "ref.json")
    assert ok.returncode == 0, ok.stderr
    (tmp_path / "ref.json").write_text(json.dumps(ref_ligera(OTRO)))
    mal = cli("verificar-release", "--modo", "publicada", "--release", tmp_path / "release.json", "--dir", w.descargas, "--commit", SHA,
              "--sha256", w.sha, "--ref", tmp_path / "ref.json")
    assert mal.returncode == 1 and "no al commit compilado" in mal.stderr
    (tmp_path / "release.json").write_text("")                                                                   # ninguna release encontrada
    ninguna = cli("verificar-release", "--modo", "borrador", "--release", tmp_path / "release.json", "--dir", w.descargas, "--commit", SHA, "--sha256", w.sha)
    assert ninguna.returncode == 1 and "exactamente una release" in ninguna.stderr


def test_cli_release_publicada_con_etiqueta_anotada(tmp_path):
    w = Mundo(tmp_path)
    (tmp_path / "release.json").write_text(json.dumps(w.release))
    (tmp_path / "ref.json").write_text(json.dumps(ref_anotada()))
    (tmp_path / "tag.json").write_text(json.dumps(tag_anotada()))
    args = ["verificar-release", "--modo", "publicada", "--release", tmp_path / "release.json", "--dir", w.descargas, "--commit", SHA, "--sha256", w.sha,
            "--ref", tmp_path / "ref.json"]
    assert cli(*args, "--tag-obj", tmp_path / "tag.json").returncode == 0
    assert cli(*args).returncode == 1                                                                              # anotada sin su objeto
    (tmp_path / "tag.json").write_text(json.dumps(tag_anotada(OTRO)))
    assert cli(*args, "--tag-obj", tmp_path / "tag.json").returncode == 1


def test_el_vinculo_completo_version_etiqueta_commit_build_artefacto_sha(tmp_path):
    """Un solo recorrido de la cadena: cada eslabón alterado, por separado, rompe la verificación."""
    base = Mundo(tmp_path / "a") if (tmp_path / "a").mkdir() is None else None
    assert base.verificar()["apunta_a"] == SHA                                                   # cadena íntegra
    casos = {"version": dict(version_cambia=True), "etiqueta": dict(ref=ref_ligera(OTRO)), "commit_del_zip": dict(zip_commit=OTRO),
             "artefacto": dict(corrupto=True), "sha": dict(sha="1" * 64)}
    for n, kw in casos.items():
        d = tmp_path / n
        d.mkdir()
        w = Mundo(d, commit=kw.get("zip_commit", SHA))
        if kw.get("corrupto"):
            (w.descargas / ra.ASSET_ZIP).write_bytes(b"corrupto")
        if kw.get("version_cambia"):
            w.release["tag_name"] = "app-v9.9.9"
        with pytest.raises(ra.ErrorRelease):
            w.verificar(ref=kw.get("ref"), sha=kw.get("sha"))
