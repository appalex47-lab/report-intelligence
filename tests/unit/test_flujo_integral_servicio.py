"""Bloque integral · flujo completo por el puente (el mismo que usa la interfaz) con el motor, los libros de ejemplo y las plantillas locales.
Usa las plantillas reales si están en `templates/` y, si no, las sintéticas versionadas (tests/plantillas.py); la equivalencia con la línea base de los 4 decks solo se comprueba con las reales."""
import hashlib
import importlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tests import plantillas as PL

HAS_AE = PL.disponible("aetops-mensual")
HAS_GLP = PL.disponible("glp1-mensual")
pytestmark = pytest.mark.skipif(not HAS_AE, reason="OMITIDA (no ejecutada): la plantilla real de AETOPS mensual no está disponible (no se versiona)")


@pytest.fixture()
def br(tmp_path, monkeypatch):
    monkeypatch.setenv("REPORT_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("REPORT_HISTORY_DB", str(tmp_path / "h" / "h.sqlite"))
    monkeypatch.setenv("REPORT_TEMPLATES_DIR", str(tmp_path / "tpl"))
    from backend.app.web import bridge, service
    importlib.reload(service)
    importlib.reload(bridge)
    service.RENDER = False
    (tmp_path / "h").mkdir()
    return bridge, service, tmp_path


def call(bridge, method, path, body=None, up=None):
    return json.loads(bridge.handle(method, path, json.dumps(body) if body is not None else "", str(up) if up else "", up.name if up else ""))


def nuevo(br, unit="aetops", per="mensual", libro="AETOPS_crudo_ejemplo.xlsx", tpl="aetops-mensual"):
    bridge, _s, _t = br
    assert call(bridge, "POST", f"/api/templates/{tpl}", up=PL.ruta(tpl))["status"] == 200
    rid = call(bridge, "POST", "/api/runs", {"unit": unit, "periodicity": per, "year": 2026, "index": 9 if per == "mensual" else 3})["json"]["id"]
    assert call(bridge, "POST", f"/api/runs/{rid}/file", up=ROOT / "data" / "ejemplos" / libro)["status"] == 200
    if unit == "aetops":
        call(bridge, "PUT", f"/api/runs/{rid}/targets", {"total": "12000000"})
    return rid


def generar(br, rid, **body):
    return call(br[0], "POST", f"/api/runs/{rid}/generate", body)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


@pytest.fixture()
def generado(br):
    rid = nuevo(br)
    g = generar(br, rid)
    assert g["status"] == 200, g
    return br, rid, g["json"]


# ------------------------------------------------------------------------------------------------------------------------- reporte válido
def test_un_reporte_valido_trae_escenario_slidespec_vista_previa_y_qa_integral(generado):
    br, rid, j = generado
    bridge, S, _ = br
    assert j["qa_passed"] and j["downloadable"] and j["vigente"] is True and j["qa_integral"]["exportable"] and j["qa_integral"]["resumen"]["errores"] == 0
    p = call(bridge, "GET", f"/api/runs/{rid}/plan")["json"]
    assert p["escenario_id"] == "aetops-mensual" and p["generado"] and p["vigente"] is True and len(p["diapositivas"]) == 13
    assert {d["tipo"] for d in p["diapositivas"]} >= {"resumen_ejecutivo", "panorama", "canales", "productos", "negados", "conclusiones", "recomendaciones"}
    assert len({d["id"] for d in p["diapositivas"]}) == 13                                         # ids estables y únicos
    v = call(bridge, "GET", f"/api/runs/{rid}/preview")["json"]
    assert len(v["diapositivas"]) == 13 and v["huella"] == sha(S._dir(rid) / "out" / j["pptx"])    # la vista previa es de ESTE archivo
    out = S._dir(rid) / "out"
    assert {"plan_reporte.json", "slidespec.json", "previsualizacion.json", "qa_integral.json"} <= {f.name for f in out.glob("*.json")}


def test_la_correspondencia_entre_vista_previa_slidespec_y_pptx_se_verifica_de_forma_independiente(generado):
    from backend.app.plan import previsualizacion as pv, qa_integral as qi, slidespec as ss
    br, rid, j = generado
    out = br[1]._dir(rid) / "out"
    pptx = out / j["pptx"]
    vista = json.loads((out / "previsualizacion.json").read_text(encoding="utf-8"))
    assert pv.verificar_correspondencia(vista, pptx) == []
    spec = json.loads((out / "slidespec.json").read_text(encoding="utf-8"))
    assert [d["sld_id"] for d in spec["diapositivas"]] == [d["sld_id"] for d in vista["diapositivas"]]
    assert not [h for h in qi.revisar_exportacion(pptx, ss.construir(pptx, set(), set(), "x", "y", []), vista) if h.severidad == qi.ERROR]


def test_la_huella_del_manifiesto_y_del_historial_es_la_del_pptx_final(generado):
    """El ajuste de diseño corre ANTES del manifiesto y del historial (que registran el hash del PPTX): lo registrado es el archivo definitivo."""
    import sqlite3
    br, rid, j = generado
    out = br[1]._dir(rid) / "out"
    pptx = out / j["pptx"]
    assert json.loads((out / "manifest.json").read_text(encoding="utf-8"))["pptx_sha256"] == sha(pptx)
    assert json.loads((out / "plan_reporte.json").read_text(encoding="utf-8"))["huellas"]["pptx"] == sha(pptx)
    con = sqlite3.connect(br[1].HISTORY_DB)
    assert [r[0] for r in con.execute("SELECT pptx_sha FROM runs ORDER BY id DESC LIMIT 1")] == [sha(pptx)]
    con.close()


def test_con_el_diseno_adaptativo_activado_o_no_los_decks_de_referencia_son_identicos_porque_todo_cabe(br, tmp_path):
    from tools import capture_baseline as cb
    rid = nuevo(br)
    on = generar(br, rid, adaptativo=True)["json"]
    sa = br[1]._dir(rid) / "out"
    ta = cb._slide_texts(sa / on["pptx"])
    plan_on = json.loads((sa / "plan_reporte.json").read_text(encoding="utf-8"))
    off = generar(br, rid, adaptativo=False)["json"]
    tb = cb._slide_texts(sa / off["pptx"])
    assert plan_on["diseno"]["acciones"] == [] and ta == tb                                       # texto Y geometría de cada forma, idénticos


@pytest.mark.parametrize("nombre", ["aetops_mensual_2026-09", "aetops_trimestral_2026-Q3", "glp1_mensual_2026-09", "glp1_trimestral_2026-Q3"])
def test_el_plan_no_altera_ninguno_de_los_cuatro_decks_de_referencia(nombre, tmp_path):
    """Equivalencia con la línea base: generar CON el plan integral produce el mismo texto y la misma geometría que generar SIN él."""
    from backend.app.plan import escenario as es, flujo
    from tools import capture_baseline as cb
    unit, period, path, tpl, res, _ = cb._run(nombre)
    plantilla = PL.ruta(tpl)
    if not plantilla.exists():
        pytest.skip(f"OMITIDA (no ejecutada): falta la plantilla {tpl}")
    f = __import__("backend.app.build", fromlist=["x"])
    build = f.build_aetops if unit == "AETOPS" else f.build_glp1
    a, b = tmp_path / "sin", tmp_path / "con"
    sin = build(res, period, plantilla, a, render=False)
    plan = flujo.Plan(es.catalogo()[es.id_para_perfil(unit, period.periodicity)], f"{unit.lower()}/{period.periodicity}", [path.name], True, {})
    con = build(res, period, plantilla, b, render=False, plan=plan)
    assert cb._slide_texts(sin.pptx) == cb._slide_texts(con.pptx)
    assert plan.informe_diseno.acciones == [] and not [h for h in plan.informe.hallazgos if h.severidad == "ERROR"]


# ------------------------------------------------------------------------------------------------------------------------- vigencia
@pytest.mark.parametrize("cambio", [
    ("PUT", "context", {"items": ["Un contexto nuevo"]}),
    ("PUT", "targets", {"total": "9000000"}),
    ("PUT", "edits", {"conclusiones": ["Conclusión editada a mano para la prueba."]}),
    ("PUT", "plan", {"cambios": {"audiencia": "Otra audiencia"}}),
    ("PUT", "plan", {"adaptativo": False}),
    ("PUT", "plan", {"escenario_id": "aetops-trimestral"}),
])
def test_cualquier_cambio_despues_de_generar_invalida_resultados_descarga_y_vista_previa(generado, cambio):
    br, rid, j = generado
    bridge = br[0]
    metodo, ruta, cuerpo = cambio
    assert call(bridge, metodo, f"/api/runs/{rid}/{ruta}", cuerpo)["status"] == 200
    r = call(bridge, "GET", f"/api/runs/{rid}/result")["json"]
    assert r["vigente"] is False and r["downloadable"] is False and r["motivos_obsoleto"]
    d = call(bridge, "GET", f"/api/runs/{rid}/files/{j['pptx']}")
    assert d["status"] == 403 and "cambió después de generarlo" in d["error"]
    v = call(bridge, "GET", f"/api/runs/{rid}/preview")
    assert v["status"] == 409 and "desactualizada" in v["error"]
    assert call(bridge, "GET", f"/api/runs/{rid}/plan")["json"]["vigente"] is False
    g = generar(br, rid)["json"]                                                                  # regenerar deja todo vigente otra vez
    assert g["vigente"] is True and g["downloadable"] is True and call(bridge, "GET", f"/api/runs/{rid}/preview")["status"] == 200


def test_volver_al_estado_anterior_sin_regenerar_tambien_es_vigente(generado):
    """La huella es del CONTENIDO, no de «se tocó algo»: si se restituye lo mismo, lo generado vuelve a corresponder."""
    br, rid, j = generado
    bridge = br[0]
    call(bridge, "PUT", f"/api/runs/{rid}/context", {"items": ["x"]})
    assert call(bridge, "GET", f"/api/runs/{rid}/result")["json"]["vigente"] is False
    call(bridge, "PUT", f"/api/runs/{rid}/context", {"items": []})
    assert call(bridge, "GET", f"/api/runs/{rid}/result")["json"]["vigente"] is True


def test_borrar_el_escenario_propio_con_el_que_se_genero_invalida_lo_generado(br):
    bridge = br[0]
    rid = nuevo(br)
    base = call(bridge, "GET", "/api/escenarios-reporte")["json"]["catalogo"][0]
    call(bridge, "PUT", "/api/escenarios-reporte/mio", {k: base[k] for k in ("nombre", "perfil", "orden_narrativo", "tipos_obligatorios", "profundidad", "tipo_conclusion")})
    call(bridge, "PUT", f"/api/runs/{rid}/plan", {"escenario_id": "mio"})
    assert generar(br, rid)["json"]["vigente"] is True
    assert call(bridge, "DELETE", "/api/escenarios-reporte/mio")["status"] == 200
    r = call(bridge, "GET", f"/api/runs/{rid}/result")["json"]
    assert r["vigente"] is False and r["downloadable"] is False                                   # un escenario inexistente nunca se asume vigente
    assert call(bridge, "GET", f"/api/runs/{rid}/plan")["status"] == 409


def test_un_reporte_generado_antes_del_flujo_integral_no_se_bloquea(generado):
    br, rid, j = generado
    out = br[1]._dir(rid) / "out"
    for n in ("plan_reporte.json", "slidespec.json", "previsualizacion.json", "qa_integral.json"):
        (out / n).unlink()
    r = call(br[0], "GET", f"/api/runs/{rid}/result")["json"]
    assert r["vigente"] is None and r["downloadable"] is True and r["qa_integral"] is None and "antes del flujo integrado" in r["motivos_obsoleto"][0]
    assert call(br[0], "GET", f"/api/runs/{rid}/files/{j['pptx']}")["status"] == 200


# ------------------------------------------------------------------------------------------------------------------------- escenario
def test_el_contexto_de_negocio_del_escenario_llega_al_pptx_marcado_como_texto_del_equipo(br):
    from pptx import Presentation
    bridge, S, _ = br
    rid = nuevo(br)
    call(bridge, "PUT", f"/api/runs/{rid}/plan", {"cambios": {"contexto_negocio": "Campaña de otoño en canales digitales\nCambio de proveedor logístico"}})
    j = generar(br, rid)["json"]
    texto = " ".join(sh.text_frame.text for s in Presentation(str(S._dir(rid) / "out" / j["pptx"])).slides for sh in s.shapes if sh.has_text_frame)
    assert "Campaña de otoño" in texto and "Cambio de proveedor logístico" in texto and "Contexto aportado por el equipo" in texto
    assert any(i["id"] == "CONTEXT_UNVERIFIED" for i in j["qa"]["issues"])                         # sigue siendo texto del equipo, no verificado


def test_un_escenario_que_exige_una_diapositiva_que_no_hay_bloquea_la_exportacion_y_se_corrige(br):
    bridge, S, _ = br
    rid = nuevo(br)
    base = call(bridge, "GET", "/api/escenarios-reporte")["json"]["catalogo"][0]
    call(bridge, "PUT", "/api/escenarios-reporte/exige", {"nombre": "Exige engagement", "perfil": "*", "profundidad": "ejecutivo", "tipo_conclusion": "acciones_priorizadas",
                                                        "orden_narrativo": base["orden_narrativo"] + ["engagement_digital"], "tipos_obligatorios": base["tipos_obligatorios"] + ["engagement_digital"]})
    call(bridge, "PUT", f"/api/runs/{rid}/plan", {"escenario_id": "exige"})
    j = generar(br, rid)["json"]
    assert j["qa_passed"] is False and j["downloadable"] is False and j["qa_integral"]["exportable"] is False
    out = S._dir(rid) / "out"
    assert json.loads((out / "qa_report.json").read_text(encoding="utf-8"))["passed"] is False
    assert json.loads((out / "manifest.json").read_text(encoding="utf-8"))["qa_passed"] is False   # el manifiesto ya refleja el error nuevo
    d = call(bridge, "GET", f"/api/runs/{rid}/files/{j['pptx']}")
    assert d["status"] == 403 and "QA no aprobó" in d["error"]
    assert call(bridge, "GET", f"/api/runs/{rid}/preview")["status"] == 200                         # la vista previa sigue disponible para corregir
    q = call(bridge, "GET", f"/api/runs/{rid}/plan")["json"]["qa_integral"]
    assert "QA_FALTA_TIPO_OBLIGATORIO" in [h["id"] for h in q["hallazgos"] if h["severidad"] == "ERROR"]
    call(bridge, "PUT", f"/api/runs/{rid}/plan", {"escenario_id": "aetops-mensual"})
    g = generar(br, rid)["json"]                                                                    # se corrige y se reejecuta el QA
    assert g["qa_passed"] and g["downloadable"] and call(bridge, "GET", f"/api/runs/{rid}/files/{g['pptx']}")["status"] == 200


def test_crud_de_escenarios_y_errores_claros(br):
    bridge = br[0]
    cat = call(bridge, "GET", "/api/escenarios-reporte")["json"]
    assert len(cat["catalogo"]) == 4 and cat["propios"] == [] and "ejecutivo" in cat["opciones"]["profundidades"]
    assert call(bridge, "PUT", "/api/escenarios-reporte/aetops-mensual", {"nombre": "x"})["status"] == 400                       # no pisa el catálogo
    assert call(bridge, "PUT", "/api/escenarios-reporte/malo", {"nombre": "x", "profundidad": "extrema"})["status"] == 400
    assert call(bridge, "DELETE", "/api/escenarios-reporte/aetops-mensual")["status"] == 404                                       # el catálogo no se borra
    assert call(bridge, "PUT", "/api/escenarios-reporte/ok", {"nombre": "Propio", "objetivo": "Mi objetivo"})["status"] == 200
    assert [e["id"] for e in call(bridge, "GET", "/api/escenarios-reporte")["json"]["propios"]] == ["ok"]
    assert call(bridge, "DELETE", "/api/escenarios-reporte/ok")["status"] == 200 and call(bridge, "DELETE", "/api/escenarios-reporte/ok")["status"] == 404


def test_un_plan_invalido_se_rechaza_al_guardar_y_conserva_el_anterior(br):
    bridge = br[0]
    rid = nuevo(br)
    assert call(bridge, "PUT", f"/api/runs/{rid}/plan", {"cambios": {"audiencia": "Comité"}})["json"]["escenario"]["audiencia"] == "Comité"
    assert call(bridge, "PUT", f"/api/runs/{rid}/plan", {"cambios": {"profundidad": "extrema"}})["status"] == 400
    assert call(bridge, "PUT", f"/api/runs/{rid}/plan", {"escenario_id": "no-existe"})["status"] == 409
    assert call(bridge, "PUT", f"/api/runs/{rid}/plan", {"cambios": "texto"})["status"] == 400
    assert call(bridge, "GET", f"/api/runs/{rid}/plan")["json"]["escenario"]["audiencia"] == "Comité"      # el plan válido anterior sigue


def test_sin_generar_no_hay_vista_previa_y_se_dice(br):
    bridge = br[0]
    rid = nuevo(br)
    v = call(bridge, "GET", f"/api/runs/{rid}/preview")
    assert v["status"] == 404 and "genera el reporte" in v["error"]
    assert call(bridge, "GET", f"/api/runs/{rid}/plan")["json"]["generado"] is False


@pytest.mark.skipif(not HAS_GLP, reason="OMITIDA (no ejecutada): falta la plantilla real de GLP-1 mensual")
def test_glp1_recorre_el_mismo_flujo_con_un_escenario_que_no_define_lo_que_la_especificacion_no_define(br):
    bridge = br[0]
    rid = nuevo(br, unit="glp1", libro="GLP1_crudo_ejemplo.xlsx", tpl="glp1-mensual")
    p = call(bridge, "GET", f"/api/runs/{rid}/plan")["json"]
    assert p["escenario_id"] == "glp1-mensual" and {"objetivo", "audiencia"} <= set(p["no_definidos"])
    j = generar(br, rid)["json"]
    assert j["qa_passed"] and j["vigente"] is True
    q = call(bridge, "GET", f"/api/runs/{rid}/plan")["json"]
    assert "QA_ESCENARIO_INCOMPLETO" in [h["id"] for h in q["qa_integral"]["hallazgos"]] and call(bridge, "GET", f"/api/runs/{rid}/preview")["status"] == 200
