"""Fase 3A-4 · regeneración REAL (motor + construcción completa del reporte con la plantilla) y comparación de extremo a extremo.

Necesita las plantillas reales (gitignoradas); sin ellas se omite con ese motivo (no se da por aprobada). Cubre los cuatro escenarios de la línea base."""
import pytest

from backend.app import build as B
from backend.app import provenance_capture as cap
from backend.app import provenance_compare as cmpm
from backend.app import version
from backend.app.models import Period
from backend.app.targets import Targets
from tools import capture_baseline as cb

ESC = list(cb.SCENARIOS)
pytestmark = pytest.mark.skipif(not all((cb.TEMPLATES / s[5] / "1" / "template.pptx").is_file() for s in cb.SCENARIOS.values()),
                                reason="faltan las plantillas reales (no se versionan): la regeneración real no puede ejecutarse")
METAS = Targets.parse({"total": "12000000"})


@pytest.fixture(autouse=True)
def commit_estampado(monkeypatch):
    monkeypatch.setattr(version, "commit", lambda: "a" * 40)


def _datos(nombre):
    unidad, per, anio, idx, libro, tpl = cb.SCENARIOS[nombre]
    return Period(unidad, per, anio, idx), cb.DATA / libro, cb.TEMPLATES / tpl / "1" / "template.pptx"


def _original(nombre, destino, edits=None):
    periodo, fuente, plantilla = _datos(nombre)
    db = destino / "h.sqlite"
    if periodo.unit == "AETOPS":
        from backend.app.pipeline import run_aetops_raw
        b = B.build_aetops(run_aetops_raw(fuente, periodo, targets=METAS, require_targets=True), periodo, plantilla, destino / "out", render=False,
                           sources=[fuente], history_db=db, targets=METAS, narrative=edits)
    else:
        from backend.app.pipeline import run_glp1_raw
        b = B.build_glp1(run_glp1_raw(fuente, periodo), periodo, plantilla, destino / "out", render=False, sources=[fuente], history_db=db,
                         targets=METAS, narrative=edits)
    assert b.procedencia["estado"] == "registrada"
    return b, db, destino / "out"


def _evaluar(nombre, db, carpeta, run_id, fuente=None, regen=True, edits=None, **kw):
    periodo, f, plantilla = _datos(nombre)
    fuente = fuente or f
    kw.setdefault("targets", METAS)
    return cmpm.evaluar(db, run_id, carpeta=carpeta, fuentes=[fuente], template=plantilla, regenerar=(
        cmpm.regenerador(period=periodo, template=plantilla, edits=edits, **kw) if regen else None), **kw)


@pytest.mark.parametrize("nombre", ESC)
def test_regenerar_con_las_mismas_entradas_es_exacta_y_determinista(nombre, tmp_path):
    b, db, carpeta = _original(nombre, tmp_path)
    r1 = _evaluar(nombre, db, carpeta, b.procedencia["run_id"])
    assert r1["estado"] == "exacta", (r1["causa"], r1["diferencias"])
    assert r1["regeneracion"]["hash_regenerado"] == b.procedencia["hash_resultado"]
    r2 = _evaluar(nombre, db, carpeta, b.procedencia["run_id"])
    assert r1 == r2                                                                   # determinista


def test_la_regeneracion_no_escribe_nada_fuera_de_su_carpeta_temporal(tmp_path):
    nombre = ESC[0]
    b, db, carpeta = _original(nombre, tmp_path)
    antes = {str(p.relative_to(tmp_path)): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert _evaluar(nombre, db, carpeta, b.procedencia["run_id"])["estado"] == "exacta"
    assert {str(p.relative_to(tmp_path)): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == antes


def test_metas_distintas_son_parcial_y_no_se_regenera(tmp_path):
    nombre = ESC[0]
    b, db, carpeta = _original(nombre, tmp_path)
    r = _evaluar(nombre, db, carpeta, b.procedencia["run_id"], targets=Targets.parse({"total": "1"}))
    assert r["estado"] == "parcial" and r["regeneracion"]["ejecutada"] is False


def test_fuente_distinta_es_no_reproducible(tmp_path):
    import shutil
    nombre = ESC[0]
    b, db, carpeta = _original(nombre, tmp_path)
    otra = tmp_path / "otra" / cb.SCENARIOS[nombre][4]
    otra.parent.mkdir()
    shutil.copyfile(cb.DATA / cb.SCENARIOS[nombre][4], otra)
    otra.write_bytes(otra.read_bytes() + b"\0")
    r = _evaluar(nombre, db, carpeta, b.procedencia["run_id"], fuente=otra)
    assert r["estado"] == "no_reproducible"


def test_un_texto_editado_no_registrado_se_detecta_como_anomalia_no_como_exacta(tmp_path):
    """El texto editado a mano entra en el hash (3A-2) pero no se registra en el manifiesto: regenerarlo SIN esas ediciones debe verse como una
    diferencia, nunca como coincidencia."""
    nombre = ESC[0]
    periodo, fuente, plantilla = _datos(nombre)
    from backend.app.pipeline import run_aetops_raw
    base = B.build_aetops(run_aetops_raw(fuente, periodo, targets=METAS, require_targets=True), periodo, plantilla, tmp_path / "base", render=False,
                          sources=[fuente], history_db=None, targets=METAS)
    seccion = next(k for k, v in base.fill.narrative.items() if v)
    edicion = {seccion: ["Texto editado a mano por el equipo."]}
    b, db, carpeta = _original(nombre, tmp_path / "ed", edits=edicion) if (tmp_path / "ed").mkdir() is None else None
    if b.procedencia["hash_resultado"] == base.procedencia["hash_resultado"]:
        pytest.skip("la edición no cambió el texto final en este escenario")
    r = _evaluar(nombre, db, carpeta, b.procedencia["run_id"])
    assert r["estado"] == "parcial" and "anomalía de determinismo" in r["causa"]
    r2 = _evaluar(nombre, db, carpeta, b.procedencia["run_id"], edits=edicion)
    assert r2["estado"] == "exacta"                                                   # con las mismas ediciones sí coincide


def test_la_regeneracion_falla_de_forma_visible_si_la_plantilla_no_sirve(tmp_path):
    nombre = ESC[0]
    b, db, carpeta = _original(nombre, tmp_path)
    mala = tmp_path / "templates" / "aetops-mensual" / "1" / "template.pptx"
    mala.parent.mkdir(parents=True)
    mala.write_bytes(b"no es un pptx")
    periodo, fuente, _ = _datos(nombre)
    r = cmpm.evaluar(db, b.procedencia["run_id"], carpeta=carpeta, fuentes=[fuente], template=mala, targets=METAS,
                     regenerar=cmpm.regenerador(period=periodo, template=mala, targets=METAS))
    assert r["estado"] == "parcial"                                                   # la plantilla difiere (C4): no se regenera con una plantilla distinta
    assert r["regeneracion"]["ejecutada"] is False


def test_el_regenerador_rechaza_fuentes_distintas_a_las_verificadas(tmp_path):
    """Defensa contra cambios entre la verificación y la regeneración: si el archivo que se usa no tiene el SHA-256 verificado, lanza."""
    import shutil
    nombre = ESC[0]
    periodo, fuente, plantilla = _datos(nombre)
    b, db, carpeta = _original(nombre, tmp_path)
    sha_ok = __import__("backend.app.history.store", fromlist=["sha256"]).sha256(fuente)
    otra = tmp_path / "otra.xlsx"
    shutil.copyfile(fuente, otra)
    otra.write_bytes(otra.read_bytes() + b"\0")
    regen = cmpm.regenerador(period=periodo, template=plantilla, targets=METAS)
    with pytest.raises(Exception):                               # el libro alterado o no se lee, o su SHA no es el verificado
        regen([otra], [sha_ok])
    with pytest.raises(cap.ErrorCaptura, match="exactamente un libro"):
        regen([fuente, fuente], [sha_ok])
    assert regen([fuente], [sha_ok]) == b.procedencia["hash_resultado"]
