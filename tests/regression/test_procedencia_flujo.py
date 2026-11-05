"""Fase 3A-3 · flujo completo sobre los escenarios de la línea base (sin plantillas con marca, apto para CI):
motor real → hash 3A-2 → captura → fila en el historial → copia JSON → verificación → recuperación → comparación de fuentes.

El hash que queda en el manifiesto debe ser EXACTAMENTE el congelado en `hash_resultado.json` (contrato 3A-2 intacto)."""
import functools
import json
import shutil
import tempfile
from pathlib import Path

import pytest

from backend.app import provenance as pv
from backend.app import provenance_capture as cap
from backend.app import provenance_verify as ver
from backend.app.history import store as hist
from backend.app.models import Period
from tests.proc_util import AHORA, plantilla
from tests.regression.test_hash_resultado import ESCENARIOS, cargar, cb, narrativa_compuesta, _correr


@functools.lru_cache(maxsize=None)
def _carga_estable(nombre):
    """Una carpeta fija por escenario con la carga guardada como `input.xlsx` (como el servicio): permite compartir el resultado del motor."""
    d = Path(tempfile.mkdtemp(prefix="proc_flujo_")) / "input.xlsx"
    shutil.copyfile(cb.DATA / cb.SCENARIOS[nombre][4], d)
    return d


def _correr_flujo(nombre, tmp):
    unidad, periodicidad, anio, indice, archivo, _ = cb.SCENARIOS[nombre]
    periodo = Period(unidad, periodicidad, anio, indice)
    estable = _carga_estable(nombre)
    fuente = tmp / "input.xlsx"                                                    # misma carga y mismo nombre que en el servicio
    shutil.copyfile(estable, fuente)
    res = _correr(unidad, estable, periodo)                                        # el resultado no depende de la carpeta (probado en 3A-2)
    tpl = plantilla(tmp, f"{unidad.lower()}-{periodicidad}")
    db = tmp / "historial" / "h.sqlite"
    db.parent.mkdir()
    con = hist.connect(db)
    rid = hist.record_run(con, periodo, [], profile=periodicidad, template=tpl, sources=[fuente], qa_passed=True, downloadable=True)
    con.close()
    carpeta = tmp / "reporte"
    carpeta.mkdir()
    out = cap.ejecutar(carpeta=carpeta, period=periodo, result=res, narrative=narrativa_compuesta(nombre), sources=[fuente], template=tpl,
                       history_db=db, run_id=rid, ahora=AHORA)
    return periodo, fuente, tpl, db, rid, carpeta, out


@pytest.mark.parametrize("nombre", ESCENARIOS)
def test_flujo_completo_y_hash_igual_al_congelado(nombre, tmp_path):
    periodo, fuente, tpl, db, rid, carpeta, out = _correr_flujo(nombre, tmp_path)
    assert out["estado"] == "registrada" and out["error"] is None
    assert out["hash_resultado"] == cargar()["con_narrativa_compuesta"][nombre]["hash"]                  # contrato 3A-2 intacto
    datos = (carpeta / "procedencia.json").read_bytes()
    m, errs = pv.leer_manifiesto(datos)
    assert errs == [] and m["hash_resultado"] == {"algoritmo": "sha256", "contrato": pv.CONTRATO, "valor": out["hash_resultado"]}
    con = hist.connect(db)
    fila = hist.get_procedencia(con, rid)
    # coherencia con lo que el historial ya guarda por su cuenta (tablas `sources` y `runs`)
    fuentes_db = con.execute("SELECT sha256, name FROM sources WHERE run_id=?", (rid,)).fetchall()
    plantilla_db = con.execute("SELECT template_sha FROM runs WHERE id=?", (rid,)).fetchone()[0]
    runs_antes = con.execute("SELECT * FROM runs WHERE id=?", (rid,)).fetchall()
    con.close()
    assert fila["manifiesto"] == datos and fila["manifiesto_sha256"] == pv.sha256_hex(datos)
    assert [f["sha256"] for f in m["archivos_fuente"]] == [s[0] for s in fuentes_db]
    assert m["version_plantillas"][0]["sha256"] == plantilla_db
    v = ver.verificar(db, rid, carpeta)
    assert (v["integridad"], v["copia"]["estado"], v["reproducibilidad"]["estado"]) == ("verificada", "integra", "no_evaluada")
    assert ver.comparar_fuentes(datos, [fuente]) == {"F1": "disponible"}
    # idempotencia: repetir la captura con los mismos datos no cambia nada
    out2 = cap.ejecutar(carpeta=carpeta, period=periodo, result=_correr(cb.SCENARIOS[nombre][0], _carga_estable(nombre), periodo),
                        narrative=narrativa_compuesta(nombre), sources=[fuente], template=tpl, history_db=db, run_id=rid, ahora=AHORA)
    assert out2["registro"] == "ya_registrada" and (carpeta / "procedencia.json").read_bytes() == datos
    con = hist.connect(db)
    assert con.execute("SELECT * FROM runs WHERE id=?", (rid,)).fetchall() == runs_antes                    # `runs` no se tocó
    con.close()


def test_la_fuente_cambiada_se_detecta_y_la_copia_perdida_se_recupera(tmp_path):
    periodo, fuente, tpl, db, rid, carpeta, out = _correr_flujo(ESCENARIOS[0], tmp_path)
    datos = (carpeta / "procedencia.json").read_bytes()
    fuente.write_bytes(fuente.read_bytes() + b"x")
    assert ver.comparar_fuentes(datos, [fuente]) == {"F1": "modificada"}
    assert ver.verificar(db, rid, carpeta)["integridad"] == "verificada"                                    # la fuente no afecta a la integridad del registro
    (carpeta / "procedencia.json").unlink()
    assert ver.reexportar_copia(db, rid, carpeta) == "creada" and (carpeta / "procedencia.json").read_bytes() == datos


def test_dos_reportes_con_las_mismas_entradas_dan_el_mismo_hash_y_distinto_registro(tmp_path):
    a = _correr_flujo(ESCENARIOS[0], tmp_path / "a") if (tmp_path / "a").mkdir() is None else None
    (tmp_path / "b").mkdir()
    b = _correr_flujo(ESCENARIOS[0], tmp_path / "b")
    assert a[-1]["hash_resultado"] == b[-1]["hash_resultado"] and a[-1]["manifiesto_sha256"] == b[-1]["manifiesto_sha256"]


def test_el_manifiesto_no_incluye_rutas_ni_datos_de_celdas(tmp_path):
    _, fuente, _, _, _, carpeta, _ = _correr_flujo(ESCENARIOS[0], tmp_path)
    texto = (carpeta / "procedencia.json").read_text(encoding="utf-8")
    assert str(tmp_path) not in texto and len(texto) < 20_000
    assert json.loads(texto)["configuracion"]["contexto"]["lineas"] == 0
