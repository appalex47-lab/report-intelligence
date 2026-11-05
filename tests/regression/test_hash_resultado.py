"""Fase 3A-2 · `hash_resultado` con el flujo REAL de Report Intelligence (spec Fase 3A §6; `backend/app/provenance.py`).

Qué demuestra, con los libros de ejemplo (sin plantillas, corre en CI) y, si existen las plantillas locales, con la generación real del PPTX:

  * COMPATIBILIDAD CON LA LÍNEA BASE: el bloque `valores` del resultado canónico es idéntico a `tools/capture_baseline.py::canon`
    de los cuatro escenarios congelados (no hay un segundo mecanismo que pueda divergir).
  * REPRODUCIBILIDAD: el hash de cada escenario es el mismo al repetir, desde otro directorio, con otro nombre de archivo, en otro
    proceso y con otra semilla de hash de Python; y es el valor congelado en `tests/regression/hash_resultado.json`
    (el mismo valor se verifica en Python 3.12 —CI— y 3.13).
  * SENSIBILIDAD: editar un párrafo o cambiar el contenido de la fuente cambia el hash.
  * NO ALTERA NADA: calcular el hash no modifica el resultado ni el PPTX; el PPTX nunca es una entrada.
  * NO ADELANTA OTRAS SUBFASES: no hay tabla `procedencia`, ni `procedencia.json`, ni cambios en `runs`.

Si el motor cambia de forma legítima (línea base regenerada y `ENGINE_VERSION` subida según la spec §4.1), este archivo se actualiza con
`python tests/regression/test_hash_resultado.py --actualizar` y la diferencia se revisa en el PR.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app import provenance as pv  # noqa: E402
from backend.app.models import Period  # noqa: E402
from tools import capture_baseline as cb  # noqa: E402

REGISTRO = ROOT / "tests" / "regression" / "hash_resultado.json"
ESCENARIOS = list(cb.SCENARIOS)


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _correr(unidad: str, path, periodo: Period):
    from backend.app.pipeline import run_aetops_raw, run_glp1_raw
    return (run_aetops_raw if unidad == "AETOPS" else run_glp1_raw)(path, periodo)


def hash_escenario(nombre: str, libro: Path | None = None, narrativa=None) -> dict:
    """Hash canónico de un escenario de la línea base (resultado del motor sobre el libro de ejemplo, sin plantilla)."""
    unidad, periodicidad, anio, indice, archivo, _ = cb.SCENARIOS[nombre]
    libro = libro or cb.DATA / archivo
    periodo = Period(unidad, periodicidad, anio, indice)
    res = _correr(unidad, libro, periodo)
    canon = pv.canonico(periodo, [{"nombre": str(libro), "sha256": _sha(libro)}], res, narrativa)
    return {"hash": pv.hash_resultado(canon)["valor"], "bloques": pv.huellas_por_bloque(canon), "bytes": len(pv.serializar(canon))}


def calcular_todo() -> dict:
    return {n: hash_escenario(n) for n in ESCENARIOS}


def cargar() -> dict:
    return json.loads(REGISTRO.read_text(encoding="utf-8"))


def actualizar() -> str:
    d = {"esquema": "hash_resultado_base/1", "contrato": pv.CONTRATO, "algoritmo": pv.ALGORITMO,
         "nota": "Hash canónico de los 4 escenarios de la línea base (libro de ejemplo, sin narrativa de plantilla). Se actualiza solo con un cambio "
                 "legítimo del motor (spec Fase 3A §4.1) o del contrato (spec §6).", "escenarios": calcular_todo()}
    REGISTRO.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return "actualizado"


# --------------------------------------------------------------------------------------------------- compatibilidad con la línea base
@pytest.mark.parametrize("nombre", ESCENARIOS)
def test_valores_son_identicos_a_la_canonicalizacion_de_la_linea_base(nombre):
    unidad, periodicidad, anio, indice, archivo, _ = cb.SCENARIOS[nombre]
    periodo = Period(unidad, periodicidad, anio, indice)
    res = _correr(unidad, cb.DATA / archivo, periodo)
    engine = ({"tables": res.tables, "products": res.products, "negados": res.negados, "extras": res.extras} if unidad == "AETOPS"
              else {"blocks": res.blocks, "funnel": res.funnel, "extras": res.extras})
    assert pv.canonico(periodo, [], res)["valores"] == cb.canon(engine)             # sin fuentes no se renombra ningún linaje
    # con la fuente cargada, lo único que cambia en `valores` es el nombre del archivo del linaje, que pasa a ser su id
    con = json.dumps(pv.canonico(periodo, [{"nombre": archivo, "sha256": _sha(cb.DATA / archivo)}], res)["valores"], sort_keys=True, ensure_ascii=False)
    assert archivo not in con and '"file": "F1"' in con
    assert con.replace('"file": "F1"', f'"file": "{archivo}"') == json.dumps(cb.canon(engine), sort_keys=True, ensure_ascii=False)


def test_los_hallazgos_del_motor_coinciden_con_los_de_la_linea_base():
    for nombre in ESCENARIOS:
        unidad, periodicidad, anio, indice, archivo, _ = cb.SCENARIOS[nombre]
        res = _correr(unidad, cb.DATA / archivo, Period(unidad, periodicidad, anio, indice))
        c = pv.canonico(Period(unidad, periodicidad, anio, indice), [], res)
        base = cb._findings(res.findings)
        assert [(x["id"], x["severity"], x["message"], x["evidence"]) for x in c["hallazgos"]] == [
            (x["id"], x["severity"], x["message"], x["evidence"]) for x in base]
        assert all(set(pv.CAMPOS_HALLAZGO) == set(x) for x in c["hallazgos"])


# --------------------------------------------------------------------------------------------------- reproducibilidad
def test_el_hash_de_cada_escenario_es_el_congelado_y_tambien_en_esta_version_de_python():
    d = cargar()
    assert d["contrato"] == pv.CONTRATO and d["algoritmo"] == pv.ALGORITMO and sorted(d["escenarios"]) == sorted(ESCENARIOS)
    for nombre in ESCENARIOS:
        actual = hash_escenario(nombre)
        esperado = d["escenarios"][nombre]
        assert actual["bloques"] == esperado["bloques"], (
            f"{nombre}: cambió el bloque {[b for b in pv.BLOQUES if actual['bloques'][b] != esperado['bloques'][b]]}. Si es legítimo, sube "
            "ENGINE_VERSION (spec §4.1) y ejecuta `python tests/regression/test_hash_resultado.py --actualizar`.")
        assert actual["hash"] == esperado["hash"] and actual["bytes"] == esperado["bytes"], nombre


@pytest.mark.parametrize("nombre", ESCENARIOS)
def test_el_hash_no_depende_del_directorio_ni_del_nombre_del_archivo(nombre, tmp_path):
    base = hash_escenario(nombre)["hash"]
    archivo = cb.SCENARIOS[nombre][4]
    otro = tmp_path / "carpeta distinta" / "Copia (final) ñ.xlsx"
    otro.parent.mkdir()
    shutil.copy(cb.DATA / archivo, otro)
    assert hash_escenario(nombre, otro)["hash"] == base
    assert hash_escenario(nombre)["hash"] == base                                         # repetir tampoco cambia


@pytest.mark.parametrize("nombre", ESCENARIOS)
def test_cambiar_el_contenido_de_la_fuente_cambia_el_hash(nombre, tmp_path):
    archivo = cb.SCENARIOS[nombre][4]
    copia = tmp_path / archivo
    datos = bytearray((cb.DATA / archivo).read_bytes())
    copia.write_bytes(bytes(datos))
    base = hash_escenario(nombre)["hash"]
    assert hash_escenario(nombre, copia)["hash"] == base                                  # misma copia byte a byte
    datos[-1] ^= 0x01                                                                     # un solo bit: otra identidad de entrada
    copia.write_bytes(bytes(datos))
    unidad, periodicidad, anio, indice, _, _ = cb.SCENARIOS[nombre]
    res = _correr(unidad, cb.DATA / archivo, Period(unidad, periodicidad, anio, indice))      # el resultado es el mismo; solo cambia la fuente
    c = pv.canonico(Period(unidad, periodicidad, anio, indice), [{"nombre": archivo, "sha256": _sha(copia)}], res)
    assert pv.hash_resultado(c)["valor"] != base
    assert [b for b in pv.BLOQUES if pv.huellas_por_bloque(c)[b] != cargar()["escenarios"][nombre]["bloques"][b]] == ["fuentes"]


def test_el_hash_es_el_mismo_en_otro_proceso_con_distintas_semillas_de_hash():
    esperado = {n: cargar()["escenarios"][n]["hash"] for n in ESCENARIOS}
    codigo = ("import json; from tests.regression.test_hash_resultado import calcular_todo; "
              "print(json.dumps({n: v['hash'] for n, v in calcular_todo().items()}))")
    for semilla in ("0", "7", "random"):
        env = {**os.environ, "PYTHONHASHSEED": semilla, "PYTHONPATH": str(ROOT)}
        r = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, cwd=ROOT, env=env, timeout=600)
        assert r.returncode == 0, r.stderr[-800:]
        assert json.loads(r.stdout.strip().splitlines()[-1]) == esperado, f"semilla {semilla}"


# --------------------------------------------------------------------------------------------------- sensibilidad con narrativa
def test_editar_un_parrafo_cambia_el_hash_y_lo_invisible_no():
    from backend.app.narrative.writer import Para
    nombre = ESCENARIOS[0]
    base = hash_escenario(nombre, narrativa={"conclusiones": [Para("Las ventas subieron +26%.", "hecho")]})["hash"]
    assert hash_escenario(nombre, narrativa={"conclusiones": [Para("Las ventas subieron +26%.", "hecho")]})["hash"] == base
    assert hash_escenario(nombre, narrativa={"conclusiones": [Para("Las ventas subieron +26%", "hecho", edited=True)]})["hash"] != base
    assert hash_escenario(nombre, narrativa={"conclusiones": [Para("Las ventas subieron +26%.", "hecho"),
                                                              Para("solo narrative.json", "calidad", visible=False)]})["hash"] == base


# --------------------------------------------------------------------------------------------------- no adelanta otras subfases
def test_no_se_toca_el_historial_ni_la_tabla_runs():
    from backend.app.history import store
    con = sqlite3.connect(":memory:")
    con.executescript(store.SCHEMA)
    tablas = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "procedencia" not in tablas
    columnas = [r[1] for r in con.execute("PRAGMA table_info(runs)")]
    assert columnas == ["id", "unit", "periodicity", "year", "idx", "version", "created_at", "profile", "template", "template_sha", "pptx_sha",
                        "pdf_sha", "qa_passed", "downloadable", "findings", "narrative", "context"]
    assert not (ROOT / "backend/app/web/procedencia.json").exists()


# --------------------------------------------------------------------------------------------------- flujo real de generación (plantillas locales)
TPL_A = ROOT / "templates" / "aetops-mensual" / "1" / "template.pptx"
TPL_G = ROOT / "templates" / "glp1-mensual" / "1" / "template.pptx"


def _generar(unidad, tmp, libro, narrativa=None):
    from backend.app.build import build_aetops, build_glp1
    periodo = Period(unidad, "mensual", 2026, 9)
    res = _correr(unidad, libro, periodo)
    if unidad == "AETOPS":
        b = build_aetops(res, periodo, TPL_A, tmp, narrative=narrativa, sources=[libro], render=False)
    else:
        b = build_glp1(res, periodo, TPL_G, tmp, narrative=narrativa, sources=[libro], render=False)
    return periodo, res, b


@pytest.mark.skipif(not (TPL_A.exists() and TPL_G.exists()), reason="plantillas reales no disponibles (no se versionan)")
@pytest.mark.parametrize("unidad,archivo", [("AETOPS", "AETOPS_crudo_ejemplo.xlsx"), ("GLP1", "GLP1_crudo_ejemplo.xlsx")])
def test_con_el_flujo_real_de_generacion_el_hash_es_reproducible_y_no_altera_el_reporte(unidad, archivo, tmp_path):
    libro = cb.DATA / archivo
    f = [{"nombre": str(libro), "sha256": _sha(libro)}]
    p1, r1, b1 = _generar(unidad, tmp_path / "uno", libro)
    pptx_antes, narr_antes = _sha(b1.pptx), json.dumps(cb.canon(b1.fill.narrative), sort_keys=True)
    h1 = pv.calcular(p1, f, r1, b1.fill.narrative)["valor"]
    assert _sha(b1.pptx) == pptx_antes and json.dumps(cb.canon(b1.fill.narrative), sort_keys=True) == narr_antes     # calcular no altera nada
    otro = tmp_path / "otra carpeta" / "renombrado.xlsx"
    otro.parent.mkdir()
    shutil.copy(libro, otro)
    p2, r2, b2 = _generar(unidad, tmp_path / "dos", otro)
    h2 = pv.calcular(p2, [{"nombre": str(otro), "sha256": _sha(otro)}], r2, b2.fill.narrative)["valor"]
    assert h1 == h2                                                                       # otra ruta, otro nombre, otra corrida
    assert {"resumen_ejecutivo", "recomendaciones"} <= set(b1.fill.narrative)             # el resumen y las recomendaciones forman parte
    texto_final = {s: [p.plain for p in ps if p.visible] for s, ps in b1.fill.narrative.items()}
    assert any(texto_final.values())
    assert h1 != hash_escenario(next(n for n in ESCENARIOS if n.startswith(unidad.lower()) and "mensual" in n))["hash"]   # con narrativa real ≠ sin ella


@pytest.mark.skipif(not (TPL_A.exists() and TPL_G.exists()), reason="plantillas reales no disponibles (no se versionan)")
@pytest.mark.parametrize("unidad,archivo,seccion", [("AETOPS", "AETOPS_crudo_ejemplo.xlsx", "conclusiones"), ("GLP1", "GLP1_crudo_ejemplo.xlsx", "conclusiones")])
def test_un_texto_editado_a_mano_en_el_flujo_real_cambia_el_hash(unidad, archivo, seccion, tmp_path):
    libro = cb.DATA / archivo
    f = [{"nombre": str(libro), "sha256": _sha(libro)}]
    p, r, b = _generar(unidad, tmp_path / "a", libro)
    base = pv.calcular(p, f, r, b.fill.narrative)["valor"]
    texto = [x.plain for x in b.fill.narrative[seccion] if x.visible]
    assert texto, "la sección de conclusiones debe tener texto"
    editado = list(texto)
    editado[0] = editado[0] + " (revisado)"
    p2, r2, b2 = _generar(unidad, tmp_path / "b", libro, {seccion: editado})
    assert pv.calcular(p2, f, r2, b2.fill.narrative)["valor"] != base
    # la misma edición repetida da el mismo hash
    p3, r3, b3 = _generar(unidad, tmp_path / "c", libro, {seccion: editado})
    assert pv.calcular(p3, f, r3, b3.fill.narrative)["valor"] == pv.calcular(p2, f, r2, b2.fill.narrative)["valor"]


if __name__ == "__main__":
    if "--actualizar" in sys.argv:
        print(actualizar())
    else:
        print(json.dumps({n: v["hash"] for n, v in calcular_todo().items()}, indent=1))
