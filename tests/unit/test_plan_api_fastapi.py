"""API (FastAPI, `app.py`) del bloque integral: registro de las rutas nuevas, respuestas, validación de entradas, errores y compatibilidad con las rutas anteriores.
Sin plantillas ni LibreOffice (corre en CI); la prueba de generación completa se omite con motivo si faltan las plantillas locales."""
import importlib
import inspect
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from tests import plantillas as PL

ROOT = Path(__file__).resolve().parents[2]
TPL = PL.ruta("aetops-mensual")

NUEVAS = {("GET", "/api/escenarios-reporte"), ("PUT", "/api/escenarios-reporte/{eid}"), ("DELETE", "/api/escenarios-reporte/{eid}"),
          ("GET", "/api/runs/{rid}/plan"), ("PUT", "/api/runs/{rid}/plan"), ("GET", "/api/runs/{rid}/preview")}
ANTERIORES = {("POST", "/api/runs"), ("GET", "/api/runs/{rid}"), ("POST", "/api/runs/{rid}/file"), ("PUT", "/api/runs/{rid}/targets"), ("PUT", "/api/runs/{rid}/context"),
              ("PUT", "/api/runs/{rid}/edits"), ("GET", "/api/runs/{rid}/analysis"), ("GET", "/api/runs/{rid}/narrative"), ("POST", "/api/runs/{rid}/verify"),
              ("POST", "/api/runs/{rid}/generate"), ("GET", "/api/runs/{rid}/result"), ("GET", "/api/runs/{rid}/files/{name}"), ("GET", "/api/templates"),
              ("GET", "/api/info"), ("GET", "/api/history/runs"), ("GET", "/api/history/trends"), ("GET", "/api/machote")}


@pytest.fixture()
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("REPORT_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("REPORT_HISTORY_DB", str(tmp_path / "h" / "h.sqlite"))
    monkeypatch.setenv("REPORT_TEMPLATES_DIR", str(tmp_path / "tpl"))
    (tmp_path / "h").mkdir()
    from backend.app.web import app as appmod, plan_api, plan_service, service
    importlib.reload(service)
    importlib.reload(plan_service)
    importlib.reload(plan_api)
    importlib.reload(appmod)
    return TestClient(appmod.app), appmod, tmp_path


def _rutas(appmod):
    esquema = appmod.app.openapi()["paths"]                                              # el esquema OpenAPI lista también las rutas de un router incluido
    return {(m.upper(), p) for p, ops in esquema.items() for m in ops}


def nueva_corrida(c, unit="aetops", per="mensual"):
    return c.post("/api/runs", json={"unit": unit, "periodicity": per, "year": 2026, "index": 9}).json()["id"]


# ----------------------------------------------------------------------------------------------------------------------- registro de rutas
def test_las_rutas_nuevas_estan_registradas_y_las_anteriores_siguen_ahi(api):
    _, appmod, _ = api
    rutas = _rutas(appmod)
    assert NUEVAS <= rutas, NUEVAS - rutas
    assert ANTERIORES <= rutas, ANTERIORES - rutas                                        # ninguna ruta anterior desapareció


def test_las_rutas_nuevas_no_pisan_a_las_anteriores_y_cada_ruta_aparece_una_sola_vez(api):
    _, appmod, _ = api
    from fastapi.routing import APIRoute
    rutas = [r for r in appmod.app.routes if isinstance(r, APIRoute)]
    for inc in (r for r in appmod.app.routes if type(r).__name__ == "_IncludedRouter"):
        rutas += [r for r in getattr(inc, "routes", []) if isinstance(r, APIRoute)]
    todas = [(m, r.path) for r in rutas for m in r.methods]
    repetidas = {x for x in todas if todas.count(x) > 1}
    assert not repetidas, repetidas
    assert len(todas) >= len(NUEVAS | ANTERIORES) - 2


def test_generate_acepta_anexo_y_el_nuevo_parametro_adaptativo(api):
    c, appmod, _ = api
    assert list(inspect.signature(appmod.generate).parameters) == ["rid", "anexo", "adaptativo"]
    rid = nueva_corrida(c)
    for q in ("", "?anexo=true", "?adaptativo=false", "?anexo=false&adaptativo=true"):
        r = c.post(f"/api/runs/{rid}/generate{q}")
        assert r.status_code == 400 and "Primero carga el libro" in r.json()["error"], (q, r.text)        # mismo error de siempre, ahora también con los parámetros nuevos
    assert c.post(f"/api/runs/{rid}/generate?adaptativo=quizas").status_code == 422        # un valor que no es booleano lo rechaza FastAPI


# ----------------------------------------------------------------------------------------------------------------------- escenarios
def test_el_catalogo_responde_con_los_cuatro_perfiles_y_las_opciones(api):
    c, _, _ = api
    r = c.get("/api/escenarios-reporte")
    assert r.status_code == 200
    j = r.json()
    assert [e["id"] for e in j["catalogo"]] == ["aetops-mensual", "aetops-trimestral", "glp1-mensual", "glp1-trimestral"] and j["propios"] == []
    assert {"ejecutivo", "intermedio", "detallado"} == set(j["opciones"]["profundidades"]) and j["opciones"]["max_texto"] == 800


def test_crear_listar_actualizar_y_borrar_un_escenario_propio(api):
    c, _, _ = api
    r = c.put("/api/escenarios-reporte/mio", json={"nombre": "Propio", "objetivo": "Mi objetivo", "orden_narrativo": ["panorama"], "tipos_obligatorios": ["panorama"]})
    assert r.status_code == 200 and r.json()["id"] == "mio" and r.json()["origen"] == "usuario"
    assert [e["id"] for e in c.get("/api/escenarios-reporte").json()["propios"]] == ["mio"]
    assert c.put("/api/escenarios-reporte/mio", json={"nombre": "Propio v2"}).json()["nombre"] == "Propio v2"        # mismo id: se actualiza
    assert c.delete("/api/escenarios-reporte/mio").json() == {"borrado": "mio"}
    assert c.get("/api/escenarios-reporte").json()["propios"] == []
    d = c.delete("/api/escenarios-reporte/mio")
    assert d.status_code == 404 and "No existe" in d.json()["error"]


@pytest.mark.parametrize("eid,cuerpo,estado", [
    ("aetops-mensual", {"nombre": "x"}, 400),                                            # no pisa el catálogo
    ("Mayusculas", {"nombre": "x"}, 400),                                                # id inválido
    ("ok", {"nombre": ""}, 400), ("ok", {"nombre": "x", "profundidad": "extrema"}, 400), ("ok", {"nombre": "x", "campo_nuevo": 1}, 400),
    ("ok", {"nombre": "x", "orden_narrativo": ["inventada"]}, 400), ("ok", {"nombre": "x", "objetivo": "y" * 801}, 400),
    ("ok", {"nombre": "x", "indicadores_relevantes": ["ventas_inventadas"]}, 400),
])
def test_un_escenario_invalido_se_rechaza_con_400_y_un_mensaje(api, eid, cuerpo, estado):
    c, _, _ = api
    r = c.put(f"/api/escenarios-reporte/{eid}", json=cuerpo)
    assert r.status_code == estado and r.json()["error"]
    assert c.get("/api/escenarios-reporte").json()["propios"] == []                      # y no deja nada guardado


def test_un_cuerpo_que_no_es_objeto_se_rechaza_con_422_y_borrar_el_catalogo_con_404(api):
    c, _, _ = api
    assert c.put("/api/escenarios-reporte/ok", json=["no", "es", "objeto"]).status_code == 422
    assert c.put("/api/escenarios-reporte/ok", content=b"no es json", headers={"content-type": "application/json"}).status_code == 422
    assert c.delete("/api/escenarios-reporte/aetops-mensual").status_code == 404


# ----------------------------------------------------------------------------------------------------------------------- plan y vista previa
def test_el_plan_de_una_corrida_nueva_usa_el_escenario_de_su_perfil(api):
    c, _, _ = api
    rid = nueva_corrida(c)
    p = c.get(f"/api/runs/{rid}/plan").json()
    assert p["escenario_id"] == "aetops-mensual" and p["generado"] is False and p["adaptativo"] is True and {"contexto_negocio", "mensaje_central"} <= set(p["no_definidos"])
    g = nueva_corrida(c, "glp1")
    assert c.get(f"/api/runs/{g}/plan").json()["escenario_id"] == "glp1-mensual"


def test_ajustar_el_plan_valida_y_un_plan_invalido_conserva_el_anterior(api):
    c, _, _ = api
    rid = nueva_corrida(c)
    assert c.put(f"/api/runs/{rid}/plan", json={"cambios": {"audiencia": "Comité"}}).json()["escenario"]["audiencia"] == "Comité"
    assert c.put(f"/api/runs/{rid}/plan", json={"cambios": {"profundidad": "extrema"}}).status_code == 400
    assert c.put(f"/api/runs/{rid}/plan", json={"escenario_id": "no-existe"}).status_code == 409
    assert c.put(f"/api/runs/{rid}/plan", json={"cambios": "texto"}).status_code == 400
    assert c.put(f"/api/runs/{rid}/plan", json={"adaptativo": False}).json()["adaptativo"] is False
    p = c.get(f"/api/runs/{rid}/plan").json()
    assert p["escenario"]["audiencia"] == "Comité" and p["adaptativo"] is False             # lo válido anterior sigue
    assert c.put(f"/api/runs/{rid}/plan", json=["no objeto"]).status_code == 422


def test_una_corrida_inexistente_da_404_y_sin_generar_no_hay_vista_previa(api):
    c, _, _ = api
    for ruta in ("plan", "preview"):
        assert c.get(f"/api/runs/{'0' * 32}/{ruta}").status_code == 404
        assert c.get(f"/api/runs/zzzz/{ruta}").status_code == 404
    assert c.put("/api/runs/zzzz/plan", json={}).status_code == 404
    rid = nueva_corrida(c)
    v = c.get(f"/api/runs/{rid}/preview")
    assert v.status_code == 404 and "genera el reporte" in v.json()["error"]


# ----------------------------------------------------------------------------------------------------------------------- compatibilidad con lo anterior
def test_las_rutas_anteriores_responden_igual_que_siempre(api):
    c, _, _ = api
    assert c.get("/api/info").status_code == 200 and c.get("/api/templates").status_code == 200
    rid = nueva_corrida(c)
    run = c.get(f"/api/runs/{rid}").json()
    assert run["id"] == rid and run["generated"] is False and run["plan"] is None and {"targets", "context", "edits", "discovery"} <= set(run)   # la clave nueva se suma, no reemplaza
    assert c.put(f"/api/runs/{rid}/context", json={"items": ["a"]}).json()["context"] == ["a"]
    assert c.get(f"/api/runs/{rid}/result").status_code == 404                              # sin generar: igual que antes
    assert c.get(f"/api/runs/{rid}/files/qa_report.json").status_code == 404
    assert c.post("/api/runs", json={"unit": "x"}).status_code in (400, 422)


@pytest.mark.skipif(not TPL.exists(), reason="OMITIDA (no ejecutada): no hay plantilla de AETOPS mensual (ni real ni sintética)")
def test_generar_por_la_api_agrega_los_campos_nuevos_sin_quitar_los_anteriores(api):
    c, appmod, tmp = api
    from backend.app.web import service
    service.RENDER = False
    assert c.post("/api/templates/aetops-mensual", files={"file": ("t.pptx", TPL.read_bytes())}).status_code == 200
    rid = nueva_corrida(c)
    assert c.post(f"/api/runs/{rid}/file", files={"file": ("l.xlsx", (ROOT / "data/ejemplos/AETOPS_crudo_ejemplo.xlsx").read_bytes())}).status_code == 200
    c.put(f"/api/runs/{rid}/targets", json={"total": "12000000"})
    r = c.post(f"/api/runs/{rid}/generate?adaptativo=false")
    assert r.status_code == 200, r.text
    j = r.json()
    assert {"ia_log", "qa", "qa_passed", "downloadable", "pptx", "pdf", "slides", "trends"} <= set(j)        # todo lo anterior
    assert j["vigente"] is True and j["qa_integral"]["exportable"] is True and j["downloadable"] is True       # y lo nuevo
    assert c.get(f"/api/runs/{rid}/plan").json()["adaptativo"] is False
    assert c.get(f"/api/runs/{rid}/preview").json()["diapositivas"]
    for n in ("slidespec.json", "qa_integral.json", "plan_reporte.json", "previsualizacion.json", j["pptx"]):
        assert c.get(f"/api/runs/{rid}/files/{n}").status_code == 200, n
    c.put(f"/api/runs/{rid}/context", json={"items": ["cambio"]})                           # un cambio posterior invalida
    assert c.get(f"/api/runs/{rid}/files/{j['pptx']}").status_code == 403 and c.get(f"/api/runs/{rid}/preview").status_code == 409
    assert c.get(f"/api/runs/{rid}/result").json()["downloadable"] is False
