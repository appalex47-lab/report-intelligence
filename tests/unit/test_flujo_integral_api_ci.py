"""Bloque integral · recorrido por la API (FastAPI) que SÍ corre en CI: sin plantillas ni navegador.

Alcance honesto: NO genera el PPTX con una plantilla real (eso lo cubren, solo en local, `test_flujo_integral_servicio.py` y `tests/e2e/test_flujo_integral.py`).
Aquí la corrida se siembra con un PPTX sintético y se ejecutan de verdad, con el mismo código de producción, `Plan.ajustar` y `Plan.revisar` (SlideSpec, vista previa y QA
integral) y luego se consulta TODO por las rutas HTTP: plan, resultado, vista previa, descarga, bloqueo por error, bloqueo por resultado obsoleto y compatibilidad con
reportes generados antes del bloque."""
import importlib
import io
import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pptx import Presentation

from tests.unit import _deck

SIN_EXIGENCIAS = {"nombre": "Sin exigencias", "profundidad": "intermedio", "tipo_conclusion": "sin_conclusion", "orden_narrativo": [], "tipos_obligatorios": []}
EXIGE_CONCLUSIONES = {"nombre": "Exige conclusiones", "profundidad": "intermedio", "tipo_conclusion": "sin_conclusion",
                      "orden_narrativo": ["panorama", "conclusiones"], "tipos_obligatorios": ["conclusiones"]}
DIAPOS = [{"titulo": "Panorama del mes", "cuerpo": "Las ventas del periodo se mantienen estables.", "pt_cuerpo": 16},
          {"titulo": "Análisis de Productos", "cuerpo": "Los productos principales conservan su participación.", "pt_cuerpo": 16}]


@pytest.fixture()
def ctx(tmp_path, monkeypatch):
    monkeypatch.setenv("REPORT_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("REPORT_HISTORY_DB", str(tmp_path / "h" / "h.sqlite"))
    monkeypatch.setenv("REPORT_TEMPLATES_DIR", str(tmp_path / "tpl"))
    (tmp_path / "h").mkdir()
    from backend.app.web import app as appmod, plan_api, plan_service, service
    for m in (service, plan_service, plan_api, appmod):
        importlib.reload(m)
    c = TestClient(appmod.app)
    rid = c.post("/api/runs", json={"unit": "aetops", "periodicity": "mensual", "year": 2026, "index": 9}).json()["id"]
    return c, service, plan_service, rid, tmp_path


def sembrar(ctx, escenario: dict | None, diapos=DIAPOS):
    """Deja la corrida como si se hubiera generado: PPTX sintético + los dos ganchos del flujo (los mismos que invoca build.py) + qa_report.json."""
    c, S, P, rid, tmp = ctx
    if escenario is not None:
        assert c.put("/api/escenarios-reporte/prueba", json=escenario).status_code == 200
        assert c.put(f"/api/runs/{rid}/plan", json={"escenario_id": "prueba"}).status_code == 200
    st = S._load(rid)
    out = S._dir(rid) / "out"
    out.mkdir(parents=True)
    pptx = _deck.crear(out / "Resultados_AETOP_Septiembre_2026.pptx", diapos)
    from backend.app.plan.flujo import Plan
    from backend.app.qa import checks
    plan = Plan(P._escenario_de(st), "aetops/mensual", ["input.xlsx"], True, {}, huella_entradas=P._huella_entradas(rid, st))
    fill, qa = SimpleNamespace(narrative={}), checks.QAReport()
    plan.ajustar(pptx, {}, fill)
    plan.revisar(qa, pptx, fill, {}, out)
    (out / "qa_report.json").write_text(json.dumps(qa.to_dict()), encoding="utf-8")
    st["generated"] = True
    S._save(rid, st)
    return pptx.name, qa


def test_resultado_valido_y_vigente_trae_plan_vista_previa_calidad_y_descarga_un_pptx_valido(ctx):
    c, _, _, rid, _ = ctx
    nombre, qa = sembrar(ctx, SIN_EXIGENCIAS)
    assert qa.passed, [i.__dict__ for i in qa.issues if i.severity == "error"]
    r = c.get(f"/api/runs/{rid}/result").json()
    assert r["qa_passed"] and r["downloadable"] and r["vigente"] is True and r["motivos_obsoleto"] == [] and r["qa_integral"]["exportable"] is True
    p = c.get(f"/api/runs/{rid}/plan").json()                                                     # plan y SlideSpec
    assert p["generado"] and p["vigente"] is True and [d["indice"] for d in p["diapositivas"]] == [1, 2] and p["qa_integral"]["estado"]
    v = c.get(f"/api/runs/{rid}/preview")                                                          # vista previa disponible
    assert v.status_code == 200 and len(v.json()["diapositivas"]) == 2
    d = c.get(f"/api/runs/{rid}/files/{nombre}")                                                  # descarga de un PPTX válido
    assert d.status_code == 200 and zipfile.ZipFile(io.BytesIO(d.content)).testzip() is None and len(Presentation(io.BytesIO(d.content)).slides) == 2
    for n in ("slidespec.json", "qa_integral.json", "plan_reporte.json", "previsualizacion.json"):
        assert c.get(f"/api/runs/{rid}/files/{n}").status_code == 200, n


def test_un_error_del_qa_integral_bloquea_la_descarga_pero_no_oculta_la_vista_previa_ni_los_hallazgos(ctx):
    c, _, _, rid, _ = ctx
    nombre, qa = sembrar(ctx, EXIGE_CONCLUSIONES)
    assert not qa.passed
    r = c.get(f"/api/runs/{rid}/result").json()
    assert r["qa_passed"] is False and r["downloadable"] is False and r["qa_integral"]["exportable"] is False and r["vigente"] is True
    bloqueo = c.get(f"/api/runs/{rid}/files/{nombre}")
    assert bloqueo.status_code == 403 and "QA" in bloqueo.json()["error"]
    errores = [h for h in c.get(f"/api/runs/{rid}/plan").json()["qa_integral"]["hallazgos"] if h["severidad"] == "ERROR"]
    assert errores and all(h["motivo"] and h["accion"] for h in errores)                         # cada error dice motivo y acción
    assert c.get(f"/api/runs/{rid}/preview").status_code == 200                                    # la vista previa sigue disponible para corregir
    assert c.get(f"/api/runs/{rid}/files/qa_integral.json").status_code == 200                      # y el informe se puede leer


@pytest.mark.parametrize("cambio", [
    lambda c, rid: c.put(f"/api/runs/{rid}/context", json={"items": ["un dato nuevo del equipo"]}),
    lambda c, rid: c.put(f"/api/runs/{rid}/targets", json={"total": "999"}),
    lambda c, rid: c.put(f"/api/runs/{rid}/plan", json={"adaptativo": False}),
    lambda c, rid: c.put(f"/api/runs/{rid}/plan", json={"cambios": {"audiencia": "Otra audiencia"}}),
    lambda c, rid: c.delete("/api/escenarios-reporte/prueba"),
], ids=["contexto", "metas", "adaptativo", "escenario_ajustado", "escenario_borrado"])
def test_un_cambio_despues_de_generar_invalida_resultado_vista_previa_y_descarga(ctx, cambio):
    c, _, _, rid, _ = ctx
    nombre, _ = sembrar(ctx, SIN_EXIGENCIAS)
    assert c.get(f"/api/runs/{rid}/files/{nombre}").status_code == 200
    cambio(c, rid)
    r = c.get(f"/api/runs/{rid}/result").json()
    assert r["vigente"] is False and r["downloadable"] is False and r["motivos_obsoleto"]
    assert c.get(f"/api/runs/{rid}/files/{nombre}").status_code == 403
    assert "desactualiz" in c.get(f"/api/runs/{rid}/files/{nombre}").json()["error"].lower() or "cambió" in c.get(f"/api/runs/{rid}/files/{nombre}").json()["error"].lower()
    v = c.get(f"/api/runs/{rid}/preview")
    assert v.status_code == 409 and "desactualizada" in v.json()["error"]


def test_los_datos_del_reporte_no_se_pierden_al_quedar_obsoleto(ctx):
    c, _, _, rid, _ = ctx
    nombre, _ = sembrar(ctx, SIN_EXIGENCIAS)
    c.put(f"/api/runs/{rid}/context", json={"items": ["x"]})
    assert c.get(f"/api/runs/{rid}/files/qa_report.json").status_code == 200               # los archivos de apoyo siguen consultables
    assert c.get(f"/api/runs/{rid}/files/qa_integral.json").status_code == 200
    assert c.get(f"/api/runs/{rid}/result").status_code == 200 and c.get(f"/api/runs/{rid}").json()["generated"] is True


# ---------------------------------------------------------------------------------------------------------------------- compatibilidad con reportes anteriores
def _como_antes_del_bloque(ctx):
    """Un reporte generado ANTES del bloque: PPTX y qa_report.json, sin ninguno de los archivos del flujo integrado ni la clave `plan` en el estado."""
    c, S, P, rid, _ = ctx
    out = S._dir(rid) / "out"
    out.mkdir(parents=True)
    pptx = _deck.crear(out / "Resultados_AETOP_Agosto_2026.pptx", DIAPOS)
    (out / "qa_report.json").write_text(json.dumps({"passed": True, "issues": [{"id": "PPTX_REVISION_ESTRUCTURAL", "severity": "info", "slide": None, "message": "x"}]}), encoding="utf-8")
    (out / "manifest.json").write_text(json.dumps({"pptx_sha256": "abc"}), encoding="utf-8")
    st = S._load(rid)
    st.pop("plan", None)
    st["generated"] = True
    S._save(rid, st)
    return pptx.name


def test_un_reporte_anterior_al_bloque_se_consulta_y_se_descarga_sin_bloqueo_ni_regeneracion(ctx):
    c, _, _, rid, _ = ctx
    nombre = _como_antes_del_bloque(ctx)
    run = c.get(f"/api/runs/{rid}").json()
    assert run["generated"] is True and run["plan"] is None and run["id"] == rid                 # se consulta; la clave nueva es None, no un error
    r = c.get(f"/api/runs/{rid}/result")
    assert r.status_code == 200
    r = r.json()
    assert r["qa_passed"] and r["downloadable"] is True and r["vigente"] is None and r["qa_integral"] is None and r["pptx"] == nombre
    assert r["qa"]["issues"][0]["id"] == "PPTX_REVISION_ESTRUCTURAL"                              # su QA anterior intacto
    for n in (nombre, "qa_report.json", "manifest.json"):
        assert c.get(f"/api/runs/{rid}/files/{n}").status_code == 200, n                          # descarga sin bloqueo
    d = c.get(f"/api/runs/{rid}/files/{nombre}")
    assert len(Presentation(io.BytesIO(d.content)).slides) == 2


def test_un_reporte_anterior_sigue_descargable_aunque_se_edite_el_contexto_pero_lo_dice(ctx):
    """Sin huellas guardadas no hay con qué comparar: no se bloquea (no hay razón técnica) y el plan indica que no hay vista previa ni QA integral."""
    c, _, _, rid, _ = ctx
    nombre = _como_antes_del_bloque(ctx)
    c.put(f"/api/runs/{rid}/context", json={"items": ["cambio posterior"]})
    assert c.get(f"/api/runs/{rid}/files/{nombre}").status_code == 200
    p = c.get(f"/api/runs/{rid}/plan").json()
    assert p["generado"] is False and p["escenario_id"] == "aetops-mensual"                       # el plan se puede elegir para regenerar, sin obligarlo
    v = c.get(f"/api/runs/{rid}/preview")
    assert v.status_code == 404 and "genera el reporte" in v.json()["error"]


def test_el_historial_de_reportes_anteriores_no_cambia_de_forma(ctx):
    c, _, _, rid, _ = ctx
    r = c.get("/api/history/runs")
    assert r.status_code == 200 and isinstance(r.json(), list)
    assert c.get("/api/history/trends").status_code == 200
