"""Fase 3A-4 · `provenance_compare.evaluar` con historial real: evidencia, regeneración bajo demanda, solo lectura y fallos."""
import json
import sqlite3

import pytest

from backend.app import provenance as pv
from backend.app import provenance_capture as cap
from backend.app import provenance_compare as cmpm
from backend.app import provenance_verify as ver
from backend.app import version
from backend.app.history import store as hist
from backend.app.targets import Targets
from tests.proc_util import P, capturar, libro, narrativa, plantilla, resultado

COMMIT = "a" * 40


@pytest.fixture(autouse=True)
def commit_estampado(monkeypatch):
    """En una compilación real el commit viene estampado; en el entorno de pruebas es «desconocido» y eso (correctamente) impide «exacta»."""
    monkeypatch.setattr(version, "commit", lambda: COMMIT)


@pytest.fixture
def caso(tmp_path):
    out, carpeta, db = capturar(tmp_path)
    tpl = tmp_path / "templates" / "aetops-mensual" / "1" / "template.pptx"
    return dict(tmp=tmp_path, out=out, carpeta=carpeta, db=db, run_id=out["run_id"], fuente=tmp_path / "input.xlsx", tpl=tpl)


def regen_ok(c):
    return lambda: cap.construir(period=P, result=resultado(), narrative=narrativa("Hola"), sources=[c["fuente"]], template=c["tpl"])[0]["hash_resultado"]["valor"]


def ev(c, **kw):
    base = dict(carpeta=c["carpeta"], fuentes=[c["fuente"]], template=c["tpl"])
    base.update(kw)
    return cmpm.evaluar(c["db"], c["run_id"], **base)


def estado(r):
    return r["estado"]


# ---------------------------------------------------------------------------------------------------------------- A: exacta
def test_a01_a03_regeneracion_real_identica_es_exacta_y_usa_la_procedencia_existente(caso):
    r = ev(caso, regenerar=regen_ok(caso))
    assert estado(r) == "exacta" and r["regeneracion"]["hash_regenerado"] == r["regeneracion"]["hash_registrado"] == caso["out"]["hash_resultado"]
    assert all(r["comprobaciones"][k]["resultado"] == "pasa" for k in pv.COMPROBACIONES)
    assert r["evidencia"]["manifiesto_sha256"] == caso["out"]["manifiesto_sha256"] and r["avisos"] == []


def test_pr11_sin_regenerar_no_hay_exacta(caso):
    r = ev(caso)
    assert estado(r) == "no_evaluada" and r["regeneracion"]["ejecutada"] is False


def test_repetir_la_comparacion_da_el_mismo_resultado(caso):
    a, b = ev(caso, regenerar=regen_ok(caso)), ev(caso, regenerar=regen_ok(caso))
    assert pv.serializar_comparacion(a) == pv.serializar_comparacion(b)


# ---------------------------------------------------------------------------------------------------------------- nunca regenera en silencio
def test_ac11_solo_regenera_si_se_pide_y_si_c1_a_c6_pasan(caso):
    llamadas = []

    def regen():
        llamadas.append(1)
        return regen_ok(caso)()
    ev(caso)                                                                         # no se pide → no se llama
    assert llamadas == []
    ev(caso, fuentes=[], regenerar=regen)                                            # C3a falla → no hay nada equivalente que regenerar
    ev(caso, fuentes=[libro(caso["tmp"] / "otro" / "input.xlsx", filas=7)], regenerar=regen)           # C3b falla
    ev(caso, targets=Targets.parse({"total": "5"}), regenerar=regen)                 # C6 falla
    ev(caso, template=None, regenerar=regen)                                         # C4 sin evidencia
    assert llamadas == []
    r = ev(caso, fuentes=[], regenerar=regen)
    assert "no se regeneró" in " ".join(r["avisos"])
    ev(caso, regenerar=regen)
    assert llamadas == [1]


def test_regeneracion_con_hash_distinto_es_parcial_con_anomalia(caso):
    r = ev(caso, regenerar=lambda: "f" * 64)
    assert estado(r) == "parcial" and "anomalía de determinismo" in r["causa"] and r["regeneracion"]["hash_regenerado"] == "f" * 64


@pytest.mark.parametrize("falla", [RuntimeError("boom"), OSError("disco"), KeyError("x"), cap.ErrorCaptura("entradas", "falta algo")])
def test_a09_una_regeneracion_que_lanza_no_es_un_exito(caso, falla):
    def regen():
        raise falla
    r = ev(caso, regenerar=regen)
    assert estado(r) == "no_evaluada" and r["comprobaciones"]["C7"]["resultado"] == "error" and r["regeneracion"]["error"]


@pytest.mark.parametrize("devuelve", [None, "", "xx", 5, "z" * 64, "A" * 64])
def test_una_regeneracion_que_devuelve_basura_no_es_un_exito(caso, devuelve):
    r = ev(caso, regenerar=lambda: devuelve)
    assert estado(r) in ("no_evaluada", "parcial") and estado(r) != "exacta"


# ---------------------------------------------------------------------------------------------------------------- B: parcial
def test_fuente_no_aportada_es_parcial(caso):
    assert estado(ev(caso, fuentes=[])) == "parcial" and estado(ev(caso, fuentes=None)) == "parcial"


def test_plantilla_distinta_es_parcial(caso):
    nueva = caso["tmp"] / "otra" / "templates" / "aetops-mensual" / "1" / "template.pptx"
    nueva.parent.mkdir(parents=True)
    nueva.write_bytes(b"PK otra plantilla")
    r = ev(caso, template=nueva, regenerar=regen_ok(caso))
    assert estado(r) == "parcial" and any(d["componente"] == "version_plantillas[0].sha256" for d in r["diferencias"])
    assert r["regeneracion"]["ejecutada"] is False


def test_metas_distintas_son_parcial_y_listan_la_diferencia(caso):
    r = ev(caso, targets=Targets.parse({"total": "123"}))
    assert estado(r) == "parcial" and any(d["componente"] == "configuracion.metas.total" and d["actual"] == "123" for d in r["diferencias"])


def test_contexto_e_ia_distintos_son_parcial(caso):
    assert estado(ev(caso, context=["texto nuevo"])) == "parcial"
    assert estado(ev(caso, ia={"usada": True, "modelo_declarado": "m"})) == "parcial"


def test_version_del_motor_distinta_es_parcial(caso, monkeypatch):
    monkeypatch.setattr(version, "ENGINE_VERSION", "1.1.0")
    r = ev(caso)
    assert estado(r) == "parcial" and any(d["componente"] == "version_motor.engine" for d in r["diferencias"])


def test_commit_distinto_es_parcial_aunque_las_versiones_coincidan(caso, monkeypatch):
    monkeypatch.setattr(version, "commit", lambda: "b" * 40)
    r = ev(caso, regenerar=regen_ok(caso))
    assert estado(r) == "parcial" and any(d["componente"] == "version_codigo.commit" for d in r["diferencias"])


def test_sin_commit_estampado_nunca_es_exacta(caso, monkeypatch):
    monkeypatch.setattr(version, "commit", lambda: "desconocido")
    r = ev(caso, regenerar=regen_ok(caso))
    assert estado(r) == "parcial" and r["comprobaciones"]["C5"]["resultado"] == "falla"


def test_entorno_distinto_es_solo_nota(caso, monkeypatch):
    monkeypatch.setattr(cap, "entorno", lambda: {"pyodide": "9.9", "python": "3.99", "python_pptx": "9.9"})
    r = ev(caso, regenerar=regen_ok(caso))
    assert estado(r) == "exacta" and r["notas"] and any("binaria ni visual" in a for a in r["alertas"])


# ---------------------------------------------------------------------------------------------------------------- C: negativos
def test_fuente_modificada_es_no_reproducible(caso):
    r = ev(caso, fuentes=[libro(caso["tmp"] / "mod" / "input.xlsx", filas=9)], regenerar=regen_ok(caso))
    assert estado(r) == "no_reproducible" and r["regeneracion"]["ejecutada"] is False


def test_ac12_reporte_legado_sin_procedencia_es_no_reproducible(tmp_path):
    carpeta = tmp_path / "viejo"
    carpeta.mkdir()
    db, rid = __import__("tests.proc_util", fromlist=["historial"]).historial(tmp_path / "h.sqlite", plantilla(tmp_path))
    r = cmpm.evaluar(db, rid, carpeta=carpeta, fuentes=[], regenerar=lambda: pytest.fail("no debe regenerar"))
    assert estado(r) == "no_reproducible" and "legado" in r["causa"]


def test_reporte_con_error_de_procedencia_es_no_reproducible_e4(tmp_path):
    from tests.proc_util import historial
    tpl = plantilla(tmp_path)
    db, rid = historial(tmp_path / "h.sqlite", tpl)
    carpeta = tmp_path / "reporte"
    carpeta.mkdir()
    out = cap.ejecutar(carpeta=carpeta, period=P, result=resultado(), narrative=narrativa("x"), sources=[tmp_path / "no_existe.xlsx"], template=tpl,
                       history_db=db, run_id=rid)
    r = cmpm.evaluar(db, rid, carpeta=carpeta, fuentes=[])
    assert out["estado"] == "error" and estado(r) == "no_reproducible" and "error al generarla" in r["causa"]


def _manipular(db, sql, *p):
    con = sqlite3.connect(db)
    con.execute("DROP TRIGGER procedencia_no_update")
    con.execute(sql, p)
    con.commit()
    con.close()


def test_registro_manipulado_es_no_reproducible(caso):
    _manipular(caso["db"], "UPDATE procedencia SET manifiesto = replace(manifiesto, 'input.xlsx', 'falso.xlsx')")
    r = ev(caso, regenerar=lambda: pytest.fail("no debe regenerar"))
    assert estado(r) == "no_reproducible" and r["comprobaciones"]["C2"]["resultado"] == "falla"


def test_registro_con_manifiesto_invalido_y_sha_coherente_es_no_reproducible(caso):
    mal = b'{"esquema": "procedencia/1"}\n'
    _manipular(caso["db"], "UPDATE procedencia SET manifiesto=?, manifiesto_sha256=?", mal.decode(), pv.sha256_hex(mal))
    r = ev(caso)
    assert estado(r) == "no_reproducible" and r["comprobaciones"]["C1"]["resultado"] == "falla"


@pytest.mark.parametrize("esquema", ["procedencia/0", "procedencia/2"])
def test_a08_esquema_incompatible_es_no_reproducible(caso, esquema):
    _manipular(caso["db"], "UPDATE procedencia SET esquema=?", esquema)
    r = ev(caso)
    assert estado(r) == "no_reproducible" and "esquema" in r["causa"]


def test_copia_alterada_es_no_reproducible_aunque_el_registro_este_integro(caso):
    p = caso["carpeta"] / "procedencia.json"
    p.write_bytes(p.read_bytes() + b" ")
    r = ev(caso, regenerar=regen_ok(caso))
    assert estado(r) == "no_reproducible" and "copia" in r["causa"] and r["evidencia"]["integridad"] == "verificada"


def test_copia_ausente_con_registro_integro_no_impide_la_comparacion(caso):
    (caso["carpeta"] / "procedencia.json").unlink()
    assert estado(ev(caso, regenerar=regen_ok(caso))) == "exacta"


def test_historial_ilegible_o_inexistente_no_se_compara(tmp_path):
    basura = tmp_path / "x.sqlite"
    basura.write_bytes(b"no soy sqlite " * 40)
    assert estado(cmpm.evaluar(basura, 1)) == "no_reproducible"
    assert estado(cmpm.evaluar(tmp_path / "nada.sqlite", 1)) == "no_reproducible"


def test_db_solo_con_copia_valida_es_a_lo_sumo_parcial(tmp_path):
    out, carpeta, _ = capturar(tmp_path, db=False)
    tpl = tmp_path / "templates" / "aetops-mensual" / "1" / "template.pptx"
    r = cmpm.evaluar(tmp_path / "nada.sqlite", 1, carpeta=carpeta, fuentes=[tmp_path / "input.xlsx"], template=tpl,
                     regenerar=lambda: out["hash_resultado"])
    assert estado(r) == "parcial" and "D-B" in r["causa"]


def test_fuente_ilegible_no_cuenta_como_aportada_y_se_avisa(caso):
    r = ev(caso, fuentes=[caso["tmp"] / "no_existe.xlsx"])
    assert estado(r) == "parcial" and any("no se pudo leer" in a for a in r["avisos"])


# ---------------------------------------------------------------------------------------------------------------- D: seguridad
def _foto(c):
    return {str(p.relative_to(c["tmp"])): p.read_bytes() for p in c["tmp"].rglob("*") if p.is_file()}


def test_la_comparacion_no_modifica_ninguna_evidencia(caso):
    antes = _foto(caso)
    ev(caso, regenerar=regen_ok(caso))
    ev(caso, fuentes=[])
    ev(caso, regenerar=lambda: "f" * 64)
    ev(caso, regenerar=lambda: (_ for _ in ()).throw(RuntimeError("x")))
    assert _foto(caso) == antes


def test_la_comparacion_no_crea_archivos_ni_temporales(caso):
    antes = sorted(p.relative_to(caso["tmp"]).as_posix() for p in caso["tmp"].rglob("*"))
    ev(caso, regenerar=regen_ok(caso))
    assert sorted(p.relative_to(caso["tmp"]).as_posix() for p in caso["tmp"].rglob("*")) == antes


def test_un_error_interno_jamas_es_exito(caso, monkeypatch):
    monkeypatch.setattr(ver, "verificar", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("fallo interno /home/x/secreto")))
    r = cmpm.evaluar(caso["db"], caso["run_id"], carpeta=caso["carpeta"], fuentes=[caso["fuente"]], template=caso["tpl"], regenerar=regen_ok(caso))
    assert estado(r) == "no_evaluada" and "error al comparar" in r["causa"] and "/home/x" not in r["causa"]


def test_acepta_una_conexion_abierta_sin_modificarla(caso):
    con = hist.connect(caso["db"])
    r = cmpm.evaluar(con, caso["run_id"], carpeta=caso["carpeta"], fuentes=[caso["fuente"]], template=caso["tpl"], regenerar=regen_ok(caso))
    assert estado(r) == "exacta"
    con.execute("SELECT 1")                                                             # sigue abierta
    con.close()


def test_el_resultado_se_puede_conservar_como_evidencia(caso):
    r = ev(caso, fuentes=[], targets=Targets.parse({"total": "1"}))
    datos = pv.serializar_comparacion(r)
    assert json.loads(datos)["estado"] == "parcial" and len(json.loads(datos)["diferencias"]) >= 2
