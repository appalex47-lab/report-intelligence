"""Fase 3A-3 · tabla autoritativa `procedencia` en `history/store.py`: escritura, inmutabilidad, idempotencia, concurrencia y fallos inducidos."""
import sqlite3
import threading

import pytest

from backend.app import provenance as pv
from backend.app.history import store as hist
from tests.proc_util import P, manifiesto_valido, mutado

DATOS = pv.serializar_manifiesto(manifiesto_valido())
RUNS_COLUMNAS = ["id", "unit", "periodicity", "year", "idx", "version", "created_at", "profile", "template", "template_sha", "pptx_sha", "pdf_sha",
                 "qa_passed", "downloadable", "findings", "narrative", "context"]


@pytest.fixture
def db(tmp_path):
    ruta = tmp_path / "h.sqlite"
    con = hist.connect(ruta)
    ids = [hist.record_run(con, P, [], qa_passed=True) for _ in range(3)]
    con.close()
    return ruta, ids


def test_la_tabla_se_crea_sola_y_runs_no_cambia():
    con = sqlite3.connect(":memory:")
    con.executescript(hist.SCHEMA)
    con.executescript(hist.SCHEMA)                                                  # repetible: IF NOT EXISTS
    assert [r[1] for r in con.execute("PRAGMA table_info(runs)")] == RUNS_COLUMNAS
    assert [(r[1], r[2], r[3], r[5]) for r in con.execute("PRAGMA table_info(procedencia)")] == [
        ("run_id", "INTEGER", 0, 1), ("esquema", "TEXT", 1, 0), ("manifiesto", "TEXT", 1, 0), ("manifiesto_sha256", "TEXT", 1, 0),
        ("hash_resultado", "TEXT", 1, 0)]
    triggers = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
    assert {"procedencia_no_update", "procedencia_no_delete", "procedencia_run_existe"} <= triggers


def test_un_historial_anterior_sin_la_tabla_sigue_funcionando_y_la_recibe(tmp_path):
    ruta = tmp_path / "viejo.sqlite"
    con = sqlite3.connect(ruta)
    esquema_viejo = hist.SCHEMA[:hist.SCHEMA.index("CREATE TABLE IF NOT EXISTS procedencia")]
    con.executescript(esquema_viejo)
    con.execute("INSERT INTO runs(unit,periodicity,year,idx,version,created_at) VALUES ('AETOPS','mensual',2025,8,1,'2025-09-01T00:00:00+00:00')")
    con.commit()
    assert "procedencia" not in {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    con.close()
    con = hist.connect(ruta)                                                        # el código nuevo abre el historial viejo
    assert len(hist.list_runs(con)) == 1 and hist.get_procedencia(con, 1) is None
    assert hist.record_procedencia(con, 1, DATOS) == "registrada"
    assert hist.next_version(con, P) == 1
    con.close()


def test_registrar_lee_y_buscar(db):
    ruta, ids = db
    con = hist.connect(ruta)
    assert hist.get_procedencia(con, ids[0]) is None
    assert hist.record_procedencia(con, ids[0], DATOS) == "registrada"
    fila = hist.get_procedencia(con, ids[0])
    assert fila["manifiesto"] == DATOS and fila["esquema"] == "procedencia/1"
    assert fila["manifiesto_sha256"] == pv.sha256_hex(DATOS) and fila["hash_resultado"] == manifiesto_valido()["hash_resultado"]["valor"]
    assert hist.buscar_procedencia_por_sha(con, fila["manifiesto_sha256"]) == [ids[0]]
    assert hist.buscar_procedencia_por_sha(con, "0" * 64) == []
    con.close()


def test_los_bytes_se_conservan_exactos_con_unicode(db):
    ruta, ids = db
    m = mutado(manifiesto_valido(), "archivos_fuente.0.nombre", "ñandú 日本語 😀.xlsx")
    datos = pv.serializar_manifiesto(m)
    con = hist.connect(ruta)
    hist.record_procedencia(con, ids[0], datos)
    assert hist.get_procedencia(con, ids[0])["manifiesto"] == datos
    con.close()


def test_es_idempotente_con_los_mismos_bytes_y_no_sustituye_otros(db):
    ruta, ids = db
    con = hist.connect(ruta)
    assert hist.record_procedencia(con, ids[0], DATOS) == "registrada"
    assert hist.record_procedencia(con, ids[0], DATOS) == "ya_registrada"
    otros = pv.serializar_manifiesto(mutado(manifiesto_valido(), "fecha_generacion.utc", "2026-11-06T00:00:00Z"))
    with pytest.raises(hist.ProcedenciaExistente):
        hist.record_procedencia(con, ids[0], otros)
    assert hist.get_procedencia(con, ids[0])["manifiesto"] == DATOS                  # lo registrado no cambió
    assert con.execute("SELECT COUNT(*) FROM procedencia").fetchone()[0] == 1
    con.close()


def test_es_inmutable_no_se_actualiza_ni_se_borra(db):
    ruta, ids = db
    con = hist.connect(ruta)
    hist.record_procedencia(con, ids[0], DATOS)
    for sql in ("UPDATE procedencia SET manifiesto='x'", "UPDATE procedencia SET manifiesto_sha256='" + "0" * 64 + "'", "DELETE FROM procedencia",
                "UPDATE procedencia SET run_id=99", "DELETE FROM procedencia WHERE run_id=1"):
        with pytest.raises(sqlite3.DatabaseError, match="historial inmutable"):
            con.execute(sql)
    assert hist.get_procedencia(con, ids[0])["manifiesto"] == DATOS
    con.close()


def test_leer_nunca_modifica_el_registro(db):
    ruta, ids = db
    con = hist.connect(ruta)
    hist.record_procedencia(con, ids[0], DATOS)
    con.close()
    antes = ruta.read_bytes()
    con = sqlite3.connect(f"file:{ruta.as_posix()}?mode=ro", uri=True)
    hist.get_procedencia(con, ids[0])
    hist.buscar_procedencia_por_sha(con, "0" * 64)
    con.close()
    assert ruta.read_bytes() == antes


def test_una_corrida_inexistente_no_admite_procedencia_ni_ids_invalidos(db):
    ruta, ids = db
    con = hist.connect(ruta)
    with pytest.raises(sqlite3.DatabaseError, match="la corrida no existe"):
        hist.record_procedencia(con, 999, DATOS)
    for malo in (0, -1, True, "1", None, 1.5):
        with pytest.raises(ValueError):
            hist.record_procedencia(con, malo, DATOS)
    assert con.execute("SELECT COUNT(*) FROM procedencia").fetchone()[0] == 0
    con.close()


@pytest.mark.parametrize("datos", [b"", b"no es json", DATOS[:-10], b"{}", DATOS.replace(b"procedencia/1", b"procedencia/2"),
                                   b"\xff\xfe", "texto"])
def test_nunca_se_guarda_un_manifiesto_invalido(db, datos):
    ruta, ids = db
    con = hist.connect(ruta)
    with pytest.raises(ValueError):
        hist.record_procedencia(con, ids[0], datos if not isinstance(datos, str) else datos.encode())
    assert con.execute("SELECT COUNT(*) FROM procedencia").fetchone()[0] == 0
    con.close()


def test_el_sha_de_la_fila_se_calcula_con_los_bytes_no_se_acepta_de_fuera(db):
    ruta, ids = db
    con = hist.connect(ruta)
    hist.record_procedencia(con, ids[0], DATOS)
    assert con.execute("SELECT manifiesto_sha256, hash_resultado FROM procedencia").fetchone() == (pv.sha256_hex(DATOS), "a" * 64)
    with pytest.raises(sqlite3.IntegrityError):                                      # un SHA de largo incorrecto lo impide la propia tabla
        con.execute("INSERT INTO procedencia VALUES (?,?,?,?,?)", (ids[1], "procedencia/1", "{}", "corto", "a" * 64))
    con.close()


# ----------------------------------------------------------------------------------------------------------------- fallos inducidos
def test_un_fallo_al_insertar_no_deja_registro_parcial(db):
    ruta, ids = db
    con = hist.connect(ruta)
    con.execute("CREATE TRIGGER fallo_inducido BEFORE INSERT ON procedencia BEGIN SELECT RAISE(ABORT, 'fallo inducido'); END")
    with pytest.raises(sqlite3.DatabaseError, match="fallo inducido"):
        hist.record_procedencia(con, ids[0], DATOS)
    assert con.execute("SELECT COUNT(*) FROM procedencia").fetchone()[0] == 0
    con.execute("DROP TRIGGER fallo_inducido")
    assert hist.record_procedencia(con, ids[0], DATOS) == "registrada"               # y el reintento funciona
    con.close()


class _ConexionFalla:
    """Simula «disco lleno» o error de E/S en el INSERT, y registra si se hizo rollback."""

    def __init__(self, con, error):
        self._c, self._e, self.rollbacks, self.commits = con, error, 0, 0

    def execute(self, sql, *a):
        if sql.lstrip().upper().startswith("INSERT"):
            raise self._e
        return self._c.execute(sql, *a)

    def rollback(self):
        self.rollbacks += 1
        self._c.rollback()

    def commit(self):
        self.commits += 1
        self._c.commit()


@pytest.mark.parametrize("error", [sqlite3.OperationalError("database or disk is full"), sqlite3.OperationalError("disk I/O error"),
                                   sqlite3.OperationalError("attempt to write a readonly database"), sqlite3.OperationalError("database is locked")])
def test_errores_de_escritura_se_propagan_con_rollback_y_sin_confirmar(db, error):
    ruta, ids = db
    con = hist.connect(ruta)
    falsa = _ConexionFalla(con, error)
    with pytest.raises(sqlite3.OperationalError):
        hist.record_procedencia(falsa, ids[0], DATOS)
    assert falsa.rollbacks == 1 and falsa.commits == 0
    assert con.execute("SELECT COUNT(*) FROM procedencia").fetchone()[0] == 0
    con.close()


def test_un_historial_de_solo_lectura_falla_y_no_registra(db):
    ruta, ids = db
    con = sqlite3.connect(f"file:{ruta.as_posix()}?mode=ro", uri=True)
    with pytest.raises(sqlite3.OperationalError):
        hist.record_procedencia(con, ids[0], DATOS)
    con.close()
    con = hist.connect(ruta)
    assert con.execute("SELECT COUNT(*) FROM procedencia").fetchone()[0] == 0
    con.close()


def test_una_base_bloqueada_por_otra_conexion_falla_sin_dejar_nada(db):
    ruta, ids = db
    otra = sqlite3.connect(ruta, isolation_level=None)
    otra.execute("BEGIN EXCLUSIVE")                                                 # otra escritura en curso
    con = sqlite3.connect(ruta, timeout=0.2)
    with pytest.raises(sqlite3.OperationalError, match="locked"):
        hist.record_procedencia(con, ids[0], DATOS)
    otra.execute("ROLLBACK")
    otra.close()
    assert con.execute("SELECT COUNT(*) FROM procedencia").fetchone()[0] == 0
    assert hist.record_procedencia(con, ids[0], DATOS) == "registrada"               # al liberarse, el reintento funciona
    con.close()


# ----------------------------------------------------------------------------------------------------------------- concurrencia
def test_dos_escrituras_simultaneas_de_la_misma_corrida_dejan_una_sola_fila(db):
    ruta, ids = db
    res, barrera = [], threading.Barrier(2)

    def escribe():
        con = hist.connect(ruta)
        con.execute("PRAGMA busy_timeout=5000")
        barrera.wait()
        try:
            res.append(hist.record_procedencia(con, ids[0], DATOS))
        except Exception as e:                                                      # noqa: BLE001
            res.append(type(e).__name__)
        finally:
            con.close()
    hilos = [threading.Thread(target=escribe) for _ in range(2)]
    [h.start() for h in hilos]
    [h.join() for h in hilos]
    assert set(res) <= {"registrada", "ya_registrada"} and "registrada" in res
    con = hist.connect(ruta)
    assert con.execute("SELECT COUNT(*) FROM procedencia").fetchone()[0] == 1
    assert hist.get_procedencia(con, ids[0])["manifiesto"] == DATOS
    con.close()


def test_escrituras_simultaneas_de_corridas_distintas_se_registran_todas(db):
    ruta, ids = db
    errores, barrera = [], threading.Barrier(len(ids))

    def escribe(rid):
        con = hist.connect(ruta)
        con.execute("PRAGMA busy_timeout=10000")
        barrera.wait()
        try:
            hist.record_procedencia(con, rid, pv.serializar_manifiesto(mutado(manifiesto_valido(), "configuracion.metas", {"total": str(rid)})))
        except Exception as e:                                                      # noqa: BLE001
            errores.append(repr(e))
        finally:
            con.close()
    hilos = [threading.Thread(target=escribe, args=(r,)) for r in ids]
    [h.start() for h in hilos]
    [h.join() for h in hilos]
    assert errores == []
    con = hist.connect(ruta)
    assert [r[0] for r in con.execute("SELECT run_id FROM procedencia ORDER BY run_id")] == ids
    con.close()


def test_leer_mientras_otra_conexion_escribe_ve_el_registro_completo_o_ninguno(db):
    ruta, ids = db
    visto, hecho = [], threading.Event()

    def lector():
        con = sqlite3.connect(f"file:{ruta.as_posix()}?mode=ro", uri=True, timeout=5)
        while not hecho.is_set():
            f = hist.get_procedencia(con, ids[0])
            visto.append(None if f is None else f["manifiesto"])
        con.close()
    h = threading.Thread(target=lector)
    h.start()
    con = hist.connect(ruta)
    hist.record_procedencia(con, ids[0], DATOS)
    con.close()
    hecho.set()
    h.join()
    assert set(visto) <= {None, DATOS}                                              # nunca una fila a medias


def test_el_registro_no_toca_runs_ni_las_otras_tablas(db):
    ruta, ids = db
    con = hist.connect(ruta)
    antes = {t: con.execute(f"SELECT * FROM {t} ORDER BY 1").fetchall() for t in ("runs", "sources", "kpis")}
    hist.record_procedencia(con, ids[0], DATOS)
    assert {t: con.execute(f"SELECT * FROM {t} ORDER BY 1").fetchall() for t in ("runs", "sources", "kpis")} == antes
    con.close()
