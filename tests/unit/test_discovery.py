"""Descubrimiento único con IA: la IA propone citando hechos; solo pasa lo que usa cifras de los hechos citados."""
import importlib
import importlib.util
import json
from pathlib import Path

import pytest

from backend.app.models import Period
from backend.app.narrative.facts import Fact, aetops_facts, glp1_facts, tokens, verify_discovery
from backend.app.pipeline import run_aetops_raw, run_glp1_raw

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("mrs", ROOT / "tools/make_realistic_samples.py")
mrs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mrs)
TPL = ROOT / "templates"
HAS_TPL = (TPL / "aetops-mensual/1/template.pptx").exists() and (TPL / "glp1-mensual/1/template.pptx").exists()
P9 = Period("AETOPS", "mensual", 2026, 9)


@pytest.fixture(scope="module")
def sheets(tmp_path_factory):
    d = tmp_path_factory.mktemp("d")
    a = run_aetops_raw(mrs.build_aetops(d / "a.xlsx"), P9)
    g = run_glp1_raw(mrs.build_glp1(d / "g.xlsx"), Period("GLP1", "mensual", 2026, 9))
    return aetops_facts(a, P9), glp1_facts(g.blocks, g.funnel, Period("GLP1", "mensual", 2026, 9))


def test_fact_sheets_are_rich_unique_ids_and_cross_themes(sheets):
    for facts in sheets:
        ids = [f.id for f in facts]
        assert len(ids) == len(set(ids)) and len(facts) >= 40
        assert all(f.nums or "sin venta" in f.texto for f in facts[:30])
        assert len({f.tema for f in facts}) >= 6 and any(f.tema == "cruce" for f in facts)
        assert all(f.id.isascii() for f in facts)


def mk(facts, **kw):
    a, b = facts[0], next(f for f in facts if f.tema != facts[0].tema)
    good = {"texto": f"La venta y su contexto: {a.texto.split(':', 1)[1]}", "tipo": "hecho", "hechos": [a.id]}
    return a, b, {"titulo": "Un ángulo propio", "angulo": "cruce", "viñetas": [good, {"texto": b.texto.split(": ", 1)[-1], "tipo": "interpretacion", "hechos": [b.id]}]}


def test_valid_discovery_passes_and_numbers_are_bolded(sheets):
    a, b, payload = mk(sheets[0])
    out = verify_discovery(sheets[0], payload)
    assert out["ok"], out
    assert all("**" in v["texto"] for v in out["viñetas"] if tokens(v["texto"]))


def test_invented_number_is_rejected(sheets):
    a, b, payload = mk(sheets[0])
    payload["viñetas"][0]["texto"] += " Subió +87%."
    out = verify_discovery(sheets[0], payload)
    assert not out["ok"] and "cifra(s) que no están" in " ".join(out["viñetas"][0]["problemas"])


def test_unknown_fact_missing_citation_causal_words_and_hypothesis_rules(sheets):
    a, b, payload = mk(sheets[0])
    p = json.loads(json.dumps(payload))
    p["viñetas"][0]["hechos"] = ["ZZ99"]
    assert "no existen" in " ".join(verify_discovery(sheets[0], p)["viñetas"][0]["problemas"])
    p = json.loads(json.dumps(payload))
    p["viñetas"][1]["hechos"] = []
    assert "no cita hechos" in " ".join(verify_discovery(sheets[0], p)["viñetas"][1]["problemas"])
    p = json.loads(json.dumps(payload))
    p["viñetas"][0]["texto"] = "Sube debido a una campaña."
    assert "causal" in " ".join(verify_discovery(sheets[0], p)["viñetas"][0]["problemas"])
    p = json.loads(json.dumps(payload))
    p["viñetas"][1]["tipo"] = "hipotesis"
    assert "qué validar" in " ".join(verify_discovery(sheets[0], p)["viñetas"][1]["problemas"])
    p["viñetas"][1]["validar"] = "Revisar la campaña del periodo."
    assert verify_discovery(sheets[0], p)["ok"]


def test_must_cross_at_least_two_themes(sheets):
    a = sheets[0][0]
    same = [f for f in sheets[0] if f.tema == a.tema][:2]
    payload = {"titulo": "Solo un tema", "viñetas": [{"texto": f.texto.split(": ", 1)[-1], "tipo": "hecho", "hechos": [f.id]} for f in same]}
    out = verify_discovery(sheets[0], payload)
    assert not out["ok"] and "dos temas" in " ".join(out["problemas"])


def test_title_without_numbers_and_malformed_payloads(sheets):
    a, b, payload = mk(sheets[0])
    payload["titulo"] = "Crece 56% por canales"
    assert not verify_discovery(sheets[0], payload)["ok"]
    for bad in (None, [], "texto", {"titulo": "x"}, {"titulo": "x", "viñetas": "no"}):
        assert not verify_discovery(sheets[0], bad)["ok"]


def test_sign_matters_and_plus_is_optional():
    f = Fact("PA1", "panorama", "La venta cambió +10% y el ticket -5%.", tokens("La venta cambió +10% y el ticket -5%."))
    f2 = Fact("CA1", "canal", "Canal X vende $1.00 M.", tokens("Canal X vende $1.00 M."))
    ok = verify_discovery([f, f2], {"titulo": "t", "viñetas": [{"texto": "Sube 10% mientras vende $1.00M.", "tipo": "hecho", "hechos": ["PA1", "CA1"]},
                                                                {"texto": "El ticket baja -5%.", "tipo": "hecho", "hechos": ["PA1"]}]})
    assert ok["ok"], ok
    bad = verify_discovery([f, f2], {"titulo": "t", "viñetas": [{"texto": "El ticket sube 5%.", "tipo": "hecho", "hechos": ["PA1"]},
                                                                 {"texto": "Vende $1.00 M.", "tipo": "hecho", "hechos": ["CA1"]}]})
    assert not bad["viñetas"][0]["ok"]


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


@pytest.mark.skipif(not HAS_TPL, reason="plantillas reales no disponibles")
@pytest.mark.parametrize("unit", ["aetops", "glp1"])
def test_end_to_end_discovery_adds_a_slide_and_cannot_be_forged(br, tmp_path, unit):
    bridge, S = br
    f = (mrs.build_aetops if unit == "aetops" else mrs.build_glp1)(tmp_path / f"{unit}.xlsx")
    rid = call(bridge, "POST", "/api/runs", {"unit": unit, "periodicity": "mensual", "year": 2026, "index": 9})["json"]["id"]
    call(bridge, "POST", f"/api/runs/{rid}/file", up=f)
    if unit == "aetops":
        call(bridge, "PUT", f"/api/runs/{rid}/targets", {"total": "12000000"})
    facts = call(bridge, "GET", f"/api/runs/{rid}/ia/facts")["json"]["hechos"]
    a = facts[0]
    b = next(x for x in facts if x["tema"] != a["tema"])
    payload = {"titulo": "Un cruce propio del periodo", "angulo": "cruce", "viñetas": [
        {"texto": a["texto"].split(": ", 1)[-1], "tipo": "hecho", "hechos": [a["id"]]},
        {"texto": b["texto"].split(": ", 1)[-1], "tipo": "interpretacion", "hechos": [b["id"]]},
        {"texto": "Conviene mirar si esto se repite el próximo periodo.", "tipo": "hipotesis", "hechos": [a["id"], b["id"]], "validar": "Comparar con el siguiente cierre."}]}
    chk = call(bridge, "POST", f"/api/runs/{rid}/ia/discovery/check", {"payload": payload, "model": "m"})["json"]
    assert chk["ok"], chk
    items = [{"texto": v["texto"], "tipo": v["tipo"], "hechos": v["hechos"], "validar": v["validar"]} for v in chk["viñetas"]]
    forged = json.loads(json.dumps(items))
    forged[0]["texto"] += " Sube 999%."
    assert call(bridge, "PUT", f"/api/runs/{rid}/discovery", {"titulo": "x", "items": forged})["status"] == 400        # el servidor no confía en la interfaz
    assert call(bridge, "PUT", f"/api/runs/{rid}/discovery", {"titulo": chk["titulo"], "items": items})["json"]["discovery"]["items"]
    g = call(bridge, "POST", f"/api/runs/{rid}/generate")
    assert g["status"] == 200 and g["json"]["qa_passed"], g
    out = Path(S.RUNS_DIR) / rid / "out"
    from pptx import Presentation
    prs = Presentation(next(out.glob("*.pptx")))
    titles = [next((sh.text_frame.text for sh in sl.shapes if sh.name == "CuadroTexto 9"), "") for sl in prs.slides]
    assert "Un cruce propio del periodo" in titles and titles[0] == "Resumen Ejecutivo" and titles[-1] == "Recomendaciones"
    assert titles.index("Un cruce propio del periodo") == len(titles) - 3 or titles.index("Un cruce propio del periodo") == len(titles) - 2
    blob = "\n".join(sh.text_frame.text for sl in prs.slides for sh in sl.shapes if sh.has_text_frame)
    assert "Hipótesis a validar" in blob and "validado por el equipo" in blob
    log = json.loads((out / "ia_log.json").read_text(encoding="utf-8"))
    assert log[-1]["modo"] == "descubrimiento" and log[-1]["aceptado"] is True
    assert call(bridge, "PUT", f"/api/runs/{rid}/discovery", None)["json"]["discovery"] is None                  # se puede quitar
