"""Descubrimiento único con IA: hoja completa que solo se apoya en hechos nuevos y cifras de los hechos que cita."""
import importlib
import importlib.util
import json
from pathlib import Path

import pytest

from backend.app.models import Period
from backend.app.narrative.facts import Fact, aetops_facts, glp1_facts, tokens, verify_discovery
from backend.app.pipeline import run_aetops_raw, run_glp1_raw
from tests import plantillas as PL

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("mrs", ROOT / "tools/make_realistic_samples.py")
mrs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mrs)
TPL = PL.REALES if PL.origen() == "reales" else PL.SINTETICAS            # misma estructura de carpetas
HAS_TPL = PL.disponible("aetops-mensual") and PL.disponible("glp1-mensual")
P9, G9 = Period("AETOPS", "mensual", 2026, 9), Period("GLP1", "mensual", 2026, 9)


@pytest.fixture(scope="module")
def sheets(tmp_path_factory):
    d = tmp_path_factory.mktemp("d")
    a = run_aetops_raw(mrs.build_aetops(d / "a.xlsx"), P9)
    g = run_glp1_raw(mrs.build_glp1(d / "g.xlsx"), G9)
    return aetops_facts(a, P9), glp1_facts(g.blocks, g.funnel, G9, g.extras)


def body(f: Fact) -> str:
    return f.texto.split(": ", 1)[-1]


def sheet_payload(facts, **kw):
    new = [f for f in facts if f.nuevo and len(f.texto) < 230]
    old = [f for f in facts if not f.nuevo and len(f.texto) < 230]
    n1, n2, n3 = new[0], next(f for f in new if f.tema != new[0].tema), new[-1]
    o1 = old[0]
    return {"titulo": "Un cruce propio del periodo", "angulo": "cruce", "titular": {"texto": body(n1), "hechos": [n1.id]}, "viñetas": [
        {"seccion": "datos", "texto": body(n1), "hechos": [n1.id]}, {"seccion": "datos", "texto": body(n2), "hechos": [n2.id, o1.id]},
        {"seccion": "significado", "texto": "El patrón se repite en otro frente del reporte.", "hechos": [n3.id]},
        {"seccion": "hipotesis", "texto": "Podría haber un efecto de mezcla entre los dos frentes.", "hechos": [n2.id], "validar": "Cruzar ambos frentes con el detalle por producto."},
        {"seccion": "accion", "texto": "Revisar este cruce en el cierre del próximo mes.", "hechos": [n1.id]}]}, (n1, n2, n3, o1)


def test_fact_sheets_are_rich_flag_what_is_new_and_have_ascii_ids(sheets):
    for facts in sheets:
        ids = [f.id for f in facts]
        assert len(ids) == len(set(ids)) and len(facts) >= 60 and all(i.isascii() for i in ids)
        assert sum(f.nuevo for f in facts) >= 20 and sum(not f.nuevo for f in facts) >= 20
        assert len({f.tema for f in facts if f.nuevo}) >= 4                      # nuevos de temas distintos (pacientes, geografía, mezcla…)
    assert {"productividad", "mezcla", "abasto", "pacientes"} <= {f.tema for f in sheets[0] if f.nuevo}
    assert {"embudo", "pacientes", "geografia"} <= {f.tema for f in sheets[1] if f.nuevo}


def test_full_sheet_passes_and_numbers_are_bolded(sheets):
    payload, _ = sheet_payload(sheets[0])
    out = verify_discovery(sheets[0], payload)
    assert out["ok"], out
    assert out["titular"]["ok"] and "**" in out["titular"]["texto"]
    assert {b["seccion"] for b in out["viñetas"]} == {"datos", "significado", "hipotesis", "accion"}


def test_bullets_that_only_repeat_the_existing_deck_are_rejected(sheets):
    payload, (n1, n2, n3, o1) = sheet_payload(sheets[0])
    payload["viñetas"][0] = {"seccion": "datos", "texto": body(o1), "hechos": [o1.id]}
    out = verify_discovery(sheets[0], payload)
    assert not out["ok"] and "repite lo que ya muestra" in " ".join(out["viñetas"][0]["problemas"])
    payload["titular"] = {"texto": body(o1), "hechos": [o1.id]}
    assert "repite lo que ya muestra" in " ".join(verify_discovery(sheets[0], payload)["titular"]["problemas"])


def test_actions_may_cite_existing_facts_but_must_cite_something(sheets):
    payload, (n1, n2, n3, o1) = sheet_payload(sheets[0])
    payload["viñetas"][-1]["hechos"] = [o1.id]
    assert verify_discovery(sheets[0], payload)["ok"]
    payload["viñetas"][-1]["hechos"] = []
    assert "no cita hechos" in " ".join(verify_discovery(sheets[0], payload)["viñetas"][-1]["problemas"])


def test_invented_number_unknown_fact_causes_and_missing_structure(sheets):
    base, _ = sheet_payload(sheets[0])
    p = json.loads(json.dumps(base))
    p["viñetas"][0]["texto"] += " Subió +87%."
    assert "cifra(s) que no están" in " ".join(verify_discovery(sheets[0], p)["viñetas"][0]["problemas"])
    p = json.loads(json.dumps(base))
    p["titular"]["texto"] += " Esto crece +87%."
    assert not verify_discovery(sheets[0], p)["titular"]["ok"]
    p = json.loads(json.dumps(base))
    p["viñetas"][1]["hechos"] = ["ZZ99"]
    assert "no existen" in " ".join(verify_discovery(sheets[0], p)["viñetas"][1]["problemas"])
    p = json.loads(json.dumps(base))
    p["viñetas"][2]["texto"] = "Sube debido a una campaña."
    assert "causal" in " ".join(verify_discovery(sheets[0], p)["viñetas"][2]["problemas"])
    p = json.loads(json.dumps(base))
    p["viñetas"][3]["validar"] = ""
    assert "qué validar" in " ".join(verify_discovery(sheets[0], p)["viñetas"][3]["problemas"])
    p = json.loads(json.dumps(base))
    p["viñetas"] = [b for b in p["viñetas"] if b["seccion"] != "accion"]
    assert "Qué haríamos" in " ".join(verify_discovery(sheets[0], p)["problemas"])
    p = json.loads(json.dumps(base))
    p.pop("titular")
    assert "titular" in " ".join(verify_discovery(sheets[0], p)["problemas"])
    p = json.loads(json.dumps(base))
    p["titulo"] = "Crece 56% por canales"
    assert not verify_discovery(sheets[0], p)["ok"]
    for bad in (None, [], "texto", {"titulo": "x"}, {"titulo": "x", "viñetas": "no"}):
        assert not verify_discovery(sheets[0], bad)["ok"]


def test_must_cross_two_themes_and_two_new_facts():
    f1 = Fact("PA1", "panorama", "Panorama: venta $1.00 M (+10%).", tokens("Panorama: venta $1.00 M (+10%)."), True)
    f2 = Fact("PA2", "panorama", "Panorama: pedidos 100 (+5%).", tokens("Panorama: pedidos 100 (+5%)."), True)
    payload = {"titulo": "Solo un tema", "titular": {"texto": "La venta llega a $1.00 M.", "hechos": ["PA1"]}, "viñetas": [
        {"seccion": "datos", "texto": "La venta sube +10%.", "hechos": ["PA1"]}, {"seccion": "datos", "texto": "Los pedidos suman 100.", "hechos": ["PA2"]},
        {"seccion": "significado", "texto": "Crecen juntos.", "hechos": ["PA1", "PA2"]}, {"seccion": "accion", "texto": "Vigilar los pedidos.", "hechos": ["PA2"]}]}
    out = verify_discovery([f1, f2], payload)
    assert not out["ok"] and "dos temas" in " ".join(out["problemas"])


def test_sign_matters_and_plus_is_optional():
    f1 = Fact("PA1", "panorama", "Panorama: la venta cambió +10% y el ticket -5%.", tokens("Panorama: la venta cambió +10% y el ticket -5%."), True)
    f2 = Fact("CA1", "canal", "Canal X vende $1.00 M.", tokens("Canal X vende $1.00 M."), True)

    def mk(txt):
        return {"titulo": "t", "titular": {"texto": "Crece la venta 10%.", "hechos": ["PA1"]}, "viñetas": [
            {"seccion": "datos", "texto": txt, "hechos": ["PA1", "CA1"]}, {"seccion": "datos", "texto": "Vende $1.00M.", "hechos": ["CA1"]},
            {"seccion": "significado", "texto": "Se mueven distinto.", "hechos": ["PA1"]}, {"seccion": "accion", "texto": "Revisar el ticket.", "hechos": ["PA1"]}]}
    assert verify_discovery([f1, f2], mk("Sube 10% mientras el ticket baja -5%."))["ok"]
    assert not verify_discovery([f1, f2], mk("El ticket sube 5%."))["viñetas"][0]["ok"]


@pytest.fixture()
def br(tmp_path, monkeypatch):
    monkeypatch.setenv("REPORT_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("REPORT_HISTORY_DB", str(tmp_path / "h" / "h.sqlite"))
    monkeypatch.setenv("REPORT_TEMPLATES_DIR", str(TPL))
    (tmp_path / "h").mkdir()
    from backend.app.web import service, bridge
    importlib.reload(service)
    importlib.reload(bridge)
    service.RENDER = False
    return bridge, service


def call(bridge, method, path, body=None, up=None):
    return json.loads(bridge.handle(method, path, json.dumps(body) if body is not None else "", str(up) if up else "", up.name if up else ""))


@pytest.mark.skipif(not HAS_TPL, reason="no hay plantillas (ni reales ni sintéticas)")
@pytest.mark.parametrize("unit", ["aetops", "glp1"])
def test_end_to_end_full_sheet_cannot_be_forged_and_adds_one_slide(br, tmp_path, unit):
    bridge, S = br
    f = (mrs.build_aetops if unit == "aetops" else mrs.build_glp1)(tmp_path / f"{unit}.xlsx")
    rid = call(bridge, "POST", "/api/runs", {"unit": unit, "periodicity": "mensual", "year": 2026, "index": 9})["json"]["id"]
    call(bridge, "POST", f"/api/runs/{rid}/file", up=f)
    if unit == "aetops":
        call(bridge, "PUT", f"/api/runs/{rid}/targets", {"total": "12000000"})
    hechos = call(bridge, "GET", f"/api/runs/{rid}/ia/facts")["json"]["hechos"]
    facts = [Fact(h["id"], h["tema"], h["texto"], set(h["cifras"]), h["nuevo"]) for h in hechos]
    payload, _ = sheet_payload(facts)
    chk = call(bridge, "POST", f"/api/runs/{rid}/ia/discovery/check", {"payload": payload, "model": "m"})["json"]
    assert chk["ok"], chk
    items = [{"seccion": v["seccion"], "texto": v["texto"], "hechos": v["hechos"], "validar": v["validar"]} for v in chk["viñetas"]]
    titular = {"texto": chk["titular"]["texto"], "hechos": chk["titular"]["hechos"]}
    forged = json.loads(json.dumps(items))
    forged[0]["texto"] += " Sube 999%."
    assert call(bridge, "PUT", f"/api/runs/{rid}/discovery", {"titulo": "x", "titular": titular, "items": forged})["status"] == 400
    saved = call(bridge, "PUT", f"/api/runs/{rid}/discovery", {"titulo": chk["titulo"], "titular": titular, "items": items})["json"]["discovery"]
    assert saved["evidencia"] and len(saved["items"]) == 5
    g = call(bridge, "POST", f"/api/runs/{rid}/generate")
    assert g["status"] == 200 and g["json"]["qa_passed"], g
    out = Path(S.RUNS_DIR) / rid / "out"
    from pptx import Presentation
    prs = Presentation(next(out.glob("*.pptx")))
    titles = [next((sh.text_frame.text for sh in sl.shapes if sh.name == "CuadroTexto 9"), "") for sl in prs.slides]
    k = titles.index("Un cruce propio del periodo")
    assert titles[0] == "Resumen Ejecutivo" and titles[-1] == "Recomendaciones" and k == len(titles) - 2
    names = {sh.name for sh in prs.slides[k].shapes}
    assert {"RI_descubrimiento_titular", "RI_descubrimiento_evidencia", "RI_descubrimiento_nota"} <= names
    blob = "\n".join(sh.text_frame.text for sh in prs.slides[k].shapes if sh.has_text_frame)
    for h in ("Lo que dicen los datos", "Lo que significa", "Hipótesis a validar", "Qué haríamos", "Evidencia citada"):
        assert h in blob
    log = json.loads((out / "ia_log.json").read_text(encoding="utf-8"))
    assert log[-1]["modo"] == "descubrimiento" and log[-1]["aceptado"] is True
    assert call(bridge, "PUT", f"/api/runs/{rid}/discovery", None)["json"]["discovery"] is None
