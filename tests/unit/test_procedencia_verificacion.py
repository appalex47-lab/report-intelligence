"""Fase 3A-3 · verificación, comparación de fuentes y re-exportación (`provenance_verify`): integridad ≠ disponibilidad ≠ reproducibilidad."""
import json
import sqlite3

import pytest

from backend.app import provenance as pv
from backend.app import provenance_verify as ver
from backend.app.history import store as hist
from tests.proc_util import capturar, libro, manifiesto_valido, historial, plantilla, P


@pytest.fixture
def caso(tmp_path):
    out, carpeta, db = capturar(tmp_path)
    return tmp_path, out, carpeta, db


def rutas(res):
    return res["registro"]["estado"], res["copia"]["estado"], res["integridad"], res["reproducibilidad"]["estado"]


def test_registro_y_copia_integros(caso):
    _, out, carpeta, db = caso
    r = ver.verificar(db, out["run_id"], carpeta)
    assert rutas(r) == ("presente", "integra", "verificada", "no_evaluada") and r["reproducibilidad"]["tope"] is None
    assert r["registro"]["manifiesto_sha256"] == out["manifiesto_sha256"]


def test_acepta_conexion_o_ruta_y_sin_carpeta(caso):
    _, out, _, db = caso
    con = hist.connect(db)
    assert ver.verificar(con, out["run_id"])["integridad"] == "verificada"
    con.close()
    assert ver.verificar(str(db), out["run_id"])["copia"]["estado"] == "no_aplica"


def test_la_verificacion_no_modifica_la_base_ni_la_copia(caso):
    _, out, carpeta, db = caso
    b1, c1 = db.read_bytes(), (carpeta / "procedencia.json").read_bytes()
    ver.verificar(db, out["run_id"], carpeta)
    ver.verificar(db, 999, carpeta)
    assert db.read_bytes() == b1 and (carpeta / "procedencia.json").read_bytes() == c1


def test_copia_ausente_con_registro_integro(caso):
    _, out, carpeta, db = caso
    (carpeta / "procedencia.json").unlink()
    assert rutas(ver.verificar(db, out["run_id"], carpeta)) == ("presente", "ausente", "verificada", "no_evaluada")


@pytest.mark.parametrize("alterar", [lambda b: b + b" ", lambda b: b.replace(b"input.xlsx", b"otro.xlsx"), lambda b: b"{}", lambda b: b"", lambda b: b"\xff\xfe\x00"])
def test_copia_alterada_se_detecta_pero_no_sustituye_al_registro(caso, alterar):
    _, out, carpeta, db = caso
    p = carpeta / "procedencia.json"
    p.write_bytes(alterar(p.read_bytes()))
    r = ver.verificar(db, out["run_id"], carpeta)
    assert rutas(r)[:3] == ("presente", "alterada", "verificada")                 # el registro autoritativo sigue siendo íntegro
    assert r["copia"]["detalle"]


def test_copia_ilegible_es_un_directorio(caso):
    _, out, carpeta, db = caso
    (carpeta / "procedencia.json").unlink()
    (carpeta / "procedencia.json").mkdir()
    assert ver.verificar(db, out["run_id"], carpeta)["copia"]["estado"] == "ilegible"


def _romper_registro(db, sql, *params):
    con = sqlite3.connect(db)
    con.execute("DROP TRIGGER procedencia_no_update")                              # simula manipulación directa de la base
    con.execute(sql, params)
    con.commit()
    con.close()


def test_registro_manipulado_se_detecta(caso):
    _, out, carpeta, db = caso
    _romper_registro(db, "UPDATE procedencia SET manifiesto = replace(manifiesto, 'input.xlsx', 'falso.xlsx')")
    r = ver.verificar(db, out["run_id"], carpeta)
    assert rutas(r)[0] == "corrupto" and r["integridad"] == "fallida" and r["reproducibilidad"]["estado"] == "no_reproducible"
    assert any("SHA-256" in d for d in r["registro"]["detalle"])


def test_registro_con_sha_y_bytes_coherentes_pero_manifiesto_invalido(caso):
    _, out, carpeta, db = caso
    mal = b'{"esquema": "procedencia/1"}\n'
    _romper_registro(db, "UPDATE procedencia SET manifiesto=?, manifiesto_sha256=?", mal.decode(), pv.sha256_hex(mal))
    r = ver.verificar(db, out["run_id"])
    assert r["registro"]["estado"] == "corrupto" and any("no válido" in d for d in r["registro"]["detalle"])


def test_hash_resultado_de_la_fila_distinto_al_del_manifiesto(caso):
    _, out, _, db = caso
    _romper_registro(db, "UPDATE procedencia SET hash_resultado=?", "f" * 64)
    r = ver.verificar(db, out["run_id"])
    assert r["registro"]["estado"] == "corrupto" and any("hash_resultado" in d for d in r["registro"]["detalle"])


@pytest.mark.parametrize("esquema", ["procedencia/0", "procedencia/2", "otra/1"])
def test_esquema_no_soportado(caso, esquema):
    _, out, _, db = caso
    _romper_registro(db, "UPDATE procedencia SET esquema=?", esquema)
    r = ver.verificar(db, out["run_id"])
    assert r["registro"]["estado"] == "esquema_no_soportado" and r["reproducibilidad"]["estado"] == "no_reproducible"


def test_sin_registro_pero_copia_valida_no_se_puede_verificar_y_topa_en_parcial(tmp_path):
    out, carpeta, _ = capturar(tmp_path, db=False)
    r = ver.verificar(tmp_path / "no_hay.sqlite", 1, carpeta)
    assert rutas(r) == ("ausente", "sin_registro", "no_verificable", "no_evaluada") and r["reproducibilidad"]["tope"] == "parcial"


def test_sin_registro_y_copia_invalida(tmp_path):
    out, carpeta, _ = capturar(tmp_path, db=False)
    (carpeta / "procedencia.json").write_bytes(b"basura")
    r = ver.verificar(tmp_path / "nada.sqlite", 1, carpeta)
    assert rutas(r) == ("ausente", "invalida", "fallida", "no_reproducible")


def test_legado_sin_nada(tmp_path):
    carpeta = tmp_path / "viejo"
    carpeta.mkdir()
    db, rid = historial(tmp_path / "h.sqlite", plantilla(tmp_path))
    r = ver.verificar(db, rid, carpeta)
    assert rutas(r) == ("ausente", "ausente", "ausente", "no_reproducible") and "legado" in r["reproducibilidad"]["causa"]
    assert r["error_de_generacion"] is None


def test_error_de_generacion_se_informa_y_no_se_confunde_con_legado(tmp_path):
    out, carpeta, db = capturar(tmp_path, sources=[tmp_path / "no_existe.xlsx"], db=False)
    r = ver.verificar(tmp_path / "x.sqlite", 1, carpeta)
    assert out["estado"] == "error" and r["error_de_generacion"]["etapa"] == "entradas" and "error al generarla" in r["reproducibilidad"]["causa"]
    assert r["integridad"] == "ausente"


def test_archivo_de_error_ilegible_no_rompe_la_verificacion(tmp_path):
    carpeta = tmp_path / "r"
    carpeta.mkdir()
    (carpeta / "procedencia_error.json").write_bytes(b"\xff no json")
    assert ver.verificar(tmp_path / "x.sqlite", 1, carpeta)["error_de_generacion"]["tipo_error"] == "ilegible"


def test_registrada_sin_copia_se_distingue_y_se_recupera(tmp_path, monkeypatch):
    from backend.app import provenance_capture as cap
    original = cap.escribir_atomico
    monkeypatch.setattr(cap, "escribir_atomico", lambda d, b: (_ for _ in ()).throw(OSError("disco")) if d.name == "procedencia.json" else original(d, b))
    out, carpeta, db = capturar(tmp_path)
    monkeypatch.undo()
    r = ver.verificar(db, out["run_id"], carpeta)
    assert out["estado"] == "registrada_sin_copia" and rutas(r)[:3] == ("presente", "ausente", "verificada") and r["error_de_generacion"]["etapa"] == "archivo"
    assert ver.reexportar_copia(db, out["run_id"], carpeta) == "creada"
    assert (carpeta / "procedencia.json").read_bytes() == hist.get_procedencia(hist.connect(db), out["run_id"])["manifiesto"]
    assert ver.reexportar_copia(db, out["run_id"], carpeta) == "sin_cambios"
    assert rutas(ver.verificar(db, out["run_id"], carpeta))[1] == "integra"


def test_base_inexistente_sin_tabla_o_corrupta(tmp_path):
    assert ver.verificar(tmp_path / "nada.sqlite", 1)["registro"]["estado"] == "ausente"
    vieja = tmp_path / "vieja.sqlite"
    sqlite3.connect(vieja).execute("CREATE TABLE runs(id INTEGER)").connection.close()
    assert ver.verificar(vieja, 1)["registro"]["estado"] == "ausente"
    basura = tmp_path / "basura.sqlite"
    basura.write_bytes(b"no soy sqlite " * 50)
    r = ver.verificar(basura, 1)
    assert r["registro"]["estado"] == "ilegible" and r["integridad"] == "fallida" and r["reproducibilidad"]["estado"] == "no_reproducible"


def test_run_id_inexistente(caso):
    _, _, _, db = caso
    assert ver.verificar(db, 999)["registro"]["estado"] == "ausente"


def test_una_corrida_sin_procedencia_en_un_historial_con_otra_si(caso):
    tmp, out, carpeta, db = caso
    con = hist.connect(db)
    rid2 = hist.record_run(con, P, [], qa_passed=True)
    con.close()
    assert ver.verificar(db, rid2)["integridad"] == "ausente" and ver.verificar(db, out["run_id"])["integridad"] == "verificada"


# ----------------------------------------------------------------------------------------------------------- comparar_fuentes
def test_comparar_fuentes_disponible_modificada_ausente(tmp_path):
    out, carpeta, _ = capturar(tmp_path, db=False)
    datos = (carpeta / "procedencia.json").read_bytes()
    fuente = tmp_path / "input.xlsx"
    assert ver.comparar_fuentes(datos, [fuente]) == {"F1": "disponible"}
    assert ver.comparar_fuentes(pv.leer_manifiesto(datos)[0], [fuente]) == {"F1": "disponible"}
    otra = libro(tmp_path / "otra" / "input.xlsx", filas=9)
    assert ver.comparar_fuentes(datos, [otra]) == {"F1": "modificada"}
    assert ver.comparar_fuentes(datos, []) == {"F1": "ausente"} == ver.comparar_fuentes(datos, None)
    assert ver.comparar_fuentes(datos, [tmp_path / "no_existe.xlsx"]) == {"F1": "ausente"}
    renombrada = tmp_path / "renombrada.xlsx"
    renombrada.write_bytes(fuente.read_bytes())
    assert ver.comparar_fuentes(datos, [renombrada]) == {"F1": "disponible"}            # el contenido manda, no el nombre


def test_comparar_fuentes_rechaza_un_manifiesto_invalido():
    for malo in (b"basura", {"esquema": "x"}):
        with pytest.raises(pv.ErrorProcedencia):
            ver.comparar_fuentes(malo, [])


def test_disponibilidad_de_fuentes_no_cambia_la_integridad(caso):
    tmp, out, carpeta, db = caso
    (tmp / "input.xlsx").unlink()
    r = ver.verificar(db, out["run_id"], carpeta)
    assert r["integridad"] == "verificada"                                          # perder la fuente no vuelve inválido el registro
    assert ver.comparar_fuentes((carpeta / "procedencia.json").read_bytes(), []) == {"F1": "ausente"}


# ----------------------------------------------------------------------------------------------------------- reexportar_copia
def test_reexportar_no_sobrescribe_una_copia_distinta_salvo_que_se_pida(caso):
    _, out, carpeta, db = caso
    p = carpeta / "procedencia.json"
    p.write_bytes(b"alterada")
    with pytest.raises(pv.ErrorProcedencia, match="no se sobrescribe"):
        ver.reexportar_copia(db, out["run_id"], carpeta)
    assert p.read_bytes() == b"alterada"
    assert ver.reexportar_copia(db, out["run_id"], carpeta, sustituir_alterada=True) == "sustituida"
    assert ver.verificar(db, out["run_id"], carpeta)["copia"]["estado"] == "integra"


def test_reexportar_exige_registro_existente_e_integro(caso):
    _, out, carpeta, db = caso
    with pytest.raises(pv.ErrorProcedencia, match="no tiene procedencia"):
        ver.reexportar_copia(db, 999, carpeta)
    _romper_registro(db, "UPDATE procedencia SET manifiesto_sha256=?", "0" * 64)
    (carpeta / "procedencia.json").unlink()
    with pytest.raises(pv.ErrorProcedencia, match="no es íntegro"):
        ver.reexportar_copia(db, out["run_id"], carpeta)
    assert not (carpeta / "procedencia.json").exists()


def test_reexportar_no_crea_la_base_si_no_existe(tmp_path):
    with pytest.raises(pv.ErrorProcedencia):
        ver.reexportar_copia(tmp_path / "nada.sqlite", 1, tmp_path)
    assert not (tmp_path / "nada.sqlite").exists()
