"""Release · consistencia eventual de GitHub (defecto del run 42308811022: «debe haber exactamente una release para la etiqueta y hay 0»).

Reproduce el retraso sin red: las consultas a GitHub se sustituyen por funciones que tardan N consultas en devolver el recurso. Comprueba que
(a) un retraso de propagación se reintenta con espera progresiva y límite, (b) un defecto real falla de inmediato, sin esperar, y (c) agotado el límite
el error es claro y la espera acumulada nunca lo supera. Corre en CI."""
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import release_app as ra                                   # noqa: E402

TAG = "app-v1.0.0"
URL = "https://github.com/o/r/releases/tag/untagged-70ee1b65d3438b2dde44"


def asset(nombre, estado="uploaded"):
    return {"name": nombre, "state": estado, "size": 10}


def borrador(**kw):
    d = {"id": 437146660, "tag_name": TAG, "draft": True, "prerelease": False, "html_url": URL,
         "assets": [asset("app.zip"), asset("app.zip.sha256")]}
    d.update(kw)
    return d


class Reloj:
    """`dormir` falso: registra las esperas sin dormir."""
    def __init__(self):
        self.pausas = []

    def __call__(self, s):
        self.pausas.append(s)


def con_retraso(n, valor, antes=None):
    """Devuelve `antes` las primeras `n` llamadas y `valor` después; cuenta las llamadas."""
    estado = {"n": 0}

    def f(*a):
        estado["n"] += 1
        return antes if estado["n"] <= n else valor
    f.estado = estado
    return f


# ----------------------------------------------------------------------------------------------------------------------- esperas
def test_las_esperas_son_progresivas_con_tope_y_no_superan_el_limite():
    e = list(ra.esperas())
    assert e == [2, 4, 8, 16, 16, 16, 16]
    assert sum(e) <= ra.ESPERA_LIMITE == 90 and max(e) <= ra.ESPERA_MAXIMA


@pytest.mark.parametrize("limite", [1, 5, 30, 90, 300])
def test_la_suma_de_esperas_nunca_supera_el_limite(limite):
    assert sum(ra.esperas(limite=limite)) <= limite


# ----------------------------------------------------------------------------------------------- borrador: retraso de propagación (se reintenta)
@pytest.mark.parametrize("retraso", [0, 1, 2, 4, 7])
def test_el_borrador_que_tarda_en_aparecer_en_el_listado_se_acaba_encontrando(retraso):
    """El caso del run 42308811022: la primera consulta (1 s después de crear) devuelve el listado SIN el borrador."""
    reloj = Reloj()
    listar = con_retraso(retraso, [borrador()], antes=[])
    r = ra.esperar_borrador(listar, lambda rid: borrador(), TAG, URL, dormir=reloj)
    assert r["id"] == 437146660 and r["draft"] is True
    assert len(reloj.pausas) == retraso and reloj.pausas == list(ra.esperas())[:retraso]       # espera progresiva, una por consulta fallida


def test_aparece_primero_con_tag_provisional_y_despues_con_la_etiqueta():
    reloj = Reloj()
    listar = con_retraso(2, [borrador()], antes=[borrador(tag_name="untagged-70ee1b65d3438b2dde44")])
    assert ra.esperar_borrador(listar, lambda rid: borrador(), TAG, URL, dormir=reloj)["tag_name"] == TAG
    assert len(reloj.pausas) == 2


def test_la_consulta_directa_por_id_que_aun_da_404_se_reintenta():
    reloj = Reloj()
    obtener = con_retraso(3, borrador(), antes=None)
    assert ra.esperar_borrador(lambda: [borrador()], obtener, TAG, URL, dormir=reloj)["id"] == 437146660
    assert len(reloj.pausas) == 3


def test_assets_incompletos_o_sin_terminar_de_subir_se_esperan():
    reloj = Reloj()
    versiones = iter([borrador(assets=[]), borrador(assets=[asset("app.zip")]),
                      borrador(assets=[asset("app.zip"), asset("app.zip.sha256", "starter")]), borrador()])
    assert ra.esperar_borrador(lambda: [borrador()], lambda rid: next(versiones), TAG, URL, dormir=reloj)["assets"][1]["state"] == "uploaded"
    assert len(reloj.pausas) == 3


# ----------------------------------------------------------------------------------------------------- borrador: límite de espera (error claro)
def test_si_nunca_aparece_falla_con_un_mensaje_claro_y_sin_superar_el_limite():
    reloj = Reloj()
    listar = con_retraso(10**9, [], antes=[])
    with pytest.raises(ra.ErrorRelease) as e:
        ra.esperar_borrador(listar, lambda rid: None, TAG, URL, dormir=reloj)
    msg = str(e.value)
    assert "no apareció" in msg and "90" in msg and "todavía no aparece" in msg and TAG in msg
    assert sum(reloj.pausas) <= ra.ESPERA_LIMITE
    assert listar.estado["n"] == len(reloj.pausas) + 1 <= 8                  # número de consultas acotado


# ----------------------------------------------------------------------------------------------------- borrador: defectos reales (sin esperar)
def sin_espera(listar, obtener=lambda rid: borrador(), match="", **kw):
    reloj = Reloj()
    with pytest.raises(ra.ErrorRelease, match=match):
        ra.esperar_borrador(listar, obtener, TAG, URL, dormir=reloj, **kw)
    assert reloj.pausas == [], "un defecto real no debe esperar"


def test_dos_releases_con_la_misma_etiqueta_es_un_defecto_real():
    sin_espera(lambda: [borrador(), borrador(id=2, html_url=URL + "x")], match="2 releases con la etiqueta")


def test_una_release_con_la_etiqueta_que_no_es_el_borrador_creado_no_se_acepta():
    sin_espera(lambda: [borrador(html_url="https://github.com/o/r/releases/tag/untagged-ffffffffffff")], match="no es el borrador creado")


def test_una_release_de_nombre_parecido_no_se_acepta():
    otra = borrador(id=9, tag_name="app-v1.0.1", html_url="https://github.com/o/r/releases/tag/untagged-aaaaaaaaaa")
    reloj = Reloj()
    with pytest.raises(ra.ErrorRelease, match="no apareció"):                   # solo hay otra release: se espera y se agota; nunca se acepta
        ra.esperar_borrador(lambda: [otra], lambda rid: otra, TAG, URL, dormir=reloj)


def test_la_etiqueta_en_otra_release_distinta_del_borrador_es_defecto():
    sin_espera(lambda: [borrador(tag_name="x"), borrador(id=5, html_url="https://otra")], match="otra|no es el borrador")


def test_una_release_ya_publicada_no_es_un_borrador():
    sin_espera(lambda: [borrador()], obtener=lambda rid: borrador(draft=False), match="no es un borrador")


def test_prerelease_es_defecto():
    sin_espera(lambda: [borrador()], obtener=lambda rid: borrador(prerelease=True), match="pre-release")


def test_un_asset_inesperado_o_repetido_es_defecto():
    sin_espera(lambda: [borrador()], obtener=lambda rid: borrador(assets=[asset("app.zip"), asset("app.zip.sha256"), asset("malware.sh")]), match="inesperados")
    sin_espera(lambda: [borrador()], obtener=lambda rid: borrador(assets=[asset("app.zip"), asset("app.zip")]), match="mismo nombre")


def test_la_consulta_por_id_que_devuelve_otra_release_es_defecto():
    sin_espera(lambda: [borrador()], obtener=lambda rid: borrador(id=1), match="otra release")


@pytest.mark.parametrize("malo", [None, {}, "x", [1]])
def test_un_listado_con_formato_inesperado_no_se_acepta(malo):
    reloj = Reloj()
    if malo == [1]:
        with pytest.raises(ra.ErrorRelease, match="no apareció"):
            ra.esperar_borrador(lambda: malo, lambda rid: None, TAG, URL, dormir=reloj)
    else:
        with pytest.raises(ra.ErrorRelease, match="formato"):
            ra.esperar_borrador(lambda: malo, lambda rid: None, TAG, URL, dormir=reloj)
        assert reloj.pausas == []


def test_un_error_de_github_al_listar_no_se_oculta_ni_se_reintenta():
    def listar():
        raise ra.ErrorRelease("gh api falló: HTTP 500")
    sin_espera(listar, match="HTTP 500")


# ---------------------------------------------------------------------------------------------------------------------- publicada
def ref_ligera():
    return {"object": {"type": "commit", "sha": "a" * 40}}


def test_la_publicada_espera_a_que_deje_de_ser_borrador_y_exista_la_etiqueta():
    reloj = Reloj()
    obtener = con_retraso(2, borrador(draft=False), antes=borrador())          # 2 consultas aún como borrador
    refs = con_retraso(1, ref_ligera(), antes=None)                             # y la etiqueta tarda una consulta más
    d, ref, anotada = ra.esperar_publicada(obtener, refs, lambda s: None, 437146660, TAG, dormir=reloj)
    assert d["draft"] is False and ref["object"]["sha"] == "a" * 40 and anotada is None
    assert len(reloj.pausas) == 3 and reloj.pausas == list(ra.esperas())[:3]


def test_la_publicada_con_etiqueta_anotada_lee_el_objeto_de_la_etiqueta():
    reloj = Reloj()
    ref = {"object": {"type": "tag", "sha": "b" * 40}}
    d, r, anotada = ra.esperar_publicada(lambda rid: borrador(draft=False), lambda t: ref, con_retraso(1, {"object": {"sha": "a" * 40}}, antes=None), 437146660, TAG, dormir=reloj)
    assert anotada == {"object": {"sha": "a" * 40}} and len(reloj.pausas) == 1


def test_la_publicada_con_otro_id_o_etiqueta_es_defecto_real():
    for d in (borrador(draft=False, id=1), borrador(draft=False, tag_name="app-v9.9.9")):
        reloj = Reloj()
        with pytest.raises(ra.ErrorRelease):
            ra.esperar_publicada(lambda rid: d, lambda t: ref_ligera(), lambda s: None, 437146660, TAG, dormir=reloj)
        assert reloj.pausas == []


def test_la_publicada_que_nunca_se_publica_agota_el_limite_con_mensaje_claro():
    reloj = Reloj()
    with pytest.raises(ra.ErrorRelease, match="todavía figura como borrador") as e:
        ra.esperar_publicada(lambda rid: borrador(), lambda t: ref_ligera(), lambda s: None, 437146660, TAG, dormir=reloj)
    assert sum(reloj.pausas) <= ra.ESPERA_LIMITE and "no apareció" in str(e.value)


# ------------------------------------------------------------------------------------------------- de extremo a extremo con un `gh` falso
GH_FALSO = """#!/usr/bin/env python3
import json, os, sys
d = os.environ["GH_FALSO_DIR"]
args = sys.argv[1:]
cont = os.path.join(d, "cont.txt")
n = int(open(cont).read()) if os.path.exists(cont) else 0
rel = json.load(open(os.path.join(d, "release.json")))
ruta = [a for a in args if a.startswith("repos/")][0]
if ruta.endswith("/releases"):
    open(cont, "w").write(str(n + 1))
    if n < int(os.environ.get("GH_FALSO_RETRASO", "0")):
        sys.exit(0)                                   # listado vacío: el borrador aún no se propagó
    print(json.dumps(rel))
elif "/releases/" in ruta:
    print(json.dumps(rel))
else:
    sys.stderr.write("gh: Not Found (HTTP 404)\\n"); sys.exit(1)
"""


def _entorno(tmp_path, retraso):
    b = tmp_path / "bin"
    b.mkdir()
    gh = b / "gh"
    gh.write_text(GH_FALSO)
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
    (tmp_path / "release.json").write_text(json.dumps(borrador(html_url=URL.replace("/o/r/", "/o/r/"))))
    (tmp_path / "url.txt").write_text(URL + "\n")
    return {**os.environ, "PATH": f"{b}:{os.environ['PATH']}", "GH_FALSO_DIR": str(tmp_path), "GH_FALSO_RETRASO": str(retraso)}


def test_cli_de_extremo_a_extremo_con_un_gh_que_tarda_en_devolver_el_borrador(tmp_path, monkeypatch):
    env = _entorno(tmp_path, retraso=2)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(ra.time, "sleep", lambda s: None)              # sin dormir de verdad; las esperas ya se prueban arriba
    salida = tmp_path / "salida.json"
    rc = ra.main(["esperar-borrador", "--repo", "o/r", "--tag", TAG, "--url-file", str(tmp_path / "url.txt"), "--out", str(salida)])
    assert rc == 0 and json.loads(salida.read_text())["id"] == 437146660
    assert int((tmp_path / "cont.txt").read_text()) == 3                # 2 listados vacíos + 1 correcto


def test_cli_agota_el_limite_cuando_el_borrador_nunca_aparece(tmp_path, monkeypatch, capsys):
    env = _entorno(tmp_path, retraso=10**6)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(ra.time, "sleep", lambda s: None)
    rc = ra.main(["esperar-borrador", "--repo", "o/r", "--tag", TAG, "--url-file", str(tmp_path / "url.txt"), "--out", str(tmp_path / "s.json")])
    assert rc == 1 and "no apareció" in capsys.readouterr().err and not (tmp_path / "s.json").exists()


@pytest.mark.parametrize("url", ["", "https://evil.example/o/r/releases/tag/untagged-abcdef12", "https://github.com/otro/repo/releases/tag/untagged-abcdef12",
                                 "https://github.com/o/r/releases/tag/app-v1.0.0", URL + "\nGITHUB_ENV=x"])
def test_cli_rechaza_una_url_de_borrador_que_no_es_la_esperada(tmp_path, capsys, url):
    (tmp_path / "u.txt").write_text(url)
    rc = ra.main(["esperar-borrador", "--repo", "o/r", "--tag", TAG, "--url-file", str(tmp_path / "u.txt"), "--out", str(tmp_path / "s.json")])
    assert rc == 1 and "URL del borrador" in capsys.readouterr().err


def test_cli_rechaza_repositorio_o_etiqueta_no_validos(tmp_path, capsys):
    (tmp_path / "u.txt").write_text(URL)
    assert ra.main(["esperar-borrador", "--repo", "o/r; rm -rf /", "--tag", TAG, "--url-file", str(tmp_path / "u.txt"), "--out", str(tmp_path / "s.json")]) == 1
    assert ra.main(["esperar-borrador", "--repo", "o/r", "--tag", "v1.0.0", "--url-file", str(tmp_path / "u.txt"), "--out", str(tmp_path / "s.json")]) == 1
    assert ra.main(["esperar-publicada", "--repo", "o/r", "--tag", TAG, "--id", "0", "--out", "a", "--ref-out", "b", "--tag-obj-out", "c"]) == 1


def test_un_fallo_de_gh_distinto_de_404_se_muestra_tal_cual(tmp_path, monkeypatch, capsys):
    b = tmp_path / "bin"
    b.mkdir()
    gh = b / "gh"
    gh.write_text("#!/bin/sh\necho 'gh: Bad credentials (HTTP 401)' >&2\nexit 1\n")
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{b}:{os.environ['PATH']}")
    (tmp_path / "u.txt").write_text(URL)
    rc = ra.main(["esperar-borrador", "--repo", "o/r", "--tag", TAG, "--url-file", str(tmp_path / "u.txt"), "--out", str(tmp_path / "s.json")])
    assert rc == 1 and "Bad credentials (HTTP 401)" in capsys.readouterr().err
