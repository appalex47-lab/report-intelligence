"""Puente sin servidor (el que corre en el navegador con Pyodide): mismas rutas que el API, sin LibreOffice."""
import importlib
import importlib.util
import json
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TPL_DIR = ROOT / "templates"
HAS_TPL = (TPL_DIR / "aetops-mensual/1/template.pptx").exists() and (TPL_DIR / "glp1-mensual/1/template.pptx").exists()


@pytest.fixture()
def br(tmp_path, monkeypatch):
    monkeypatch.setenv("REPORT_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("REPORT_HISTORY_DB", str(tmp_path / "h" / "h.sqlite"))
    monkeypatch.setenv("REPORT_TEMPLATES_DIR", str(tmp_path / "tpl"))
    from backend.app.web import service, bridge
    importlib.reload(service)
    importlib.reload(bridge)
    service.RENDER = False                                           # como en el navegador
    (tmp_path / "h").mkdir()
    return bridge, service, tmp_path


def call(bridge, method, path, body=None, up=None):
    out = json.loads(bridge.handle(method, path, json.dumps(body) if body is not None else "", str(up) if up else "", up.name if up else ""))
    return out


def _mod(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools/make_realistic_samples.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_unknown_route_and_bad_ids(br):
    bridge, _s, _t = br
    assert call(bridge, "GET", "/api/nada")["status"] == 404
    assert call(bridge, "GET", "/api/runs/zzzz")["status"] == 404
    assert call(bridge, "POST", "/api/runs", {"unit": "x"})["status"] == 400
    assert call(bridge, "GET", "/api/info")["json"] == {"render": False, "browser": False}


def test_templates_upload_and_listing(br, tmp_path):
    bridge, _s, t = br
    assert all(not x["available"] for x in call(bridge, "GET", "/api/templates")["json"])
    bad = tmp_path / "x.pptx"
    bad.write_bytes(b"no es zip")
    assert call(bridge, "POST", "/api/templates/aetops-mensual", up=bad)["status"] == 400
    assert call(bridge, "POST", "/api/templates/otro", up=bad)["status"] == 404
    if HAS_TPL:
        good = TPL_DIR / "aetops-mensual/1/template.pptx"
        out = call(bridge, "POST", "/api/templates/aetops-mensual", up=good)
        assert out["status"] == 200 and {x["key"]: x["available"] for x in out["json"]}["aetops-mensual"]


def test_machote_download_through_bridge(br):
    bridge, _s, _t = br
    out = call(bridge, "GET", "/api/machote", {"unit": "aetops", "periodicity": "mensual", "year": 2026, "index": 9})
    assert out["status"] == 200 and Path(out["file"]).exists() and out["name"].endswith(".xlsx")


@pytest.mark.skipif(not HAS_TPL, reason="plantillas reales no disponibles")
def test_full_flow_without_render_for_both_units(br, tmp_path):
    bridge, S, t = br
    m = _mod("mrs")
    for key in ("aetops-mensual", "glp1-mensual"):
        shutil.copy(TPL_DIR / key / "1/template.pptx", (t / "tpl" / key / "1").mkdir(parents=True, exist_ok=True) or (t / "tpl" / key / "1" / "template.pptx"))
    for unit, build, targets in (("aetops", m.build_aetops, {"total": "12000000"}), ("glp1", m.build_glp1, {})):
        f = build(tmp_path / f"{unit}.xlsx")
        rid = call(bridge, "POST", "/api/runs", {"unit": unit, "periodicity": "mensual", "year": 2026, "index": 9})["json"]["id"]
        assert call(bridge, "POST", f"/api/runs/{rid}/file", up=f)["status"] == 200
        if targets:
            call(bridge, "PUT", f"/api/runs/{rid}/targets", targets)
        a = call(bridge, "GET", f"/api/runs/{rid}/analysis")["json"]
        assert a["can_generate"], a["findings"]
        n = call(bridge, "GET", f"/api/runs/{rid}/narrative")
        assert n["status"] == 200 and n["json"]["secciones"][0]["clave"] == "resumen_ejecutivo"
        g = call(bridge, "POST", f"/api/runs/{rid}/generate")
        assert g["status"] == 200, g
        info = g["json"]
        assert info["pptx"] and info["pdf"] is None and info["slides"] == [] and info["qa_passed"] and info["downloadable"]
        assert any(i["id"] == "QA_VISUAL_OMITIDO" for i in info["qa"]["issues"])
        dl = call(bridge, "GET", f"/api/runs/{rid}/files/{info['pptx']}")
        assert dl["status"] == 200 and Path(dl["file"]).stat().st_size > 50_000
    assert call(bridge, "GET", "/api/history/runs")["json"]
    assert call(bridge, "GET", "/api/history/export")["status"] == 200


def test_missing_template_is_explained_and_unblocked_after_upload(br, tmp_path):
    bridge, S, t = br
    m = _mod("mrs3")
    f = m.build_aetops(tmp_path / "a.xlsx")
    rid = call(bridge, "POST", "/api/runs", {"unit": "aetops", "periodicity": "mensual", "year": 2026, "index": 9})["json"]["id"]
    call(bridge, "POST", f"/api/runs/{rid}/file", up=f)
    call(bridge, "PUT", f"/api/runs/{rid}/targets", {"total": "10000000"})
    a = call(bridge, "GET", f"/api/runs/{rid}/analysis")["json"]
    assert a["generator_available"] is False and a["template_key"] == "aetops-mensual"
    assert "Falta la plantilla PPTX de AETOPS mensual" in a["message"] and "Plantillas" in a["message"]
    assert call(bridge, "GET", f"/api/runs/{rid}/narrative")["status"] in (404, 409, 500)      # no hay plantilla: error legible, no un fallo mudo
    if HAS_TPL:
        call(bridge, "POST", "/api/templates/aetops-mensual", up=TPL_DIR / "aetops-mensual/1/template.pptx")
        assert call(bridge, "GET", f"/api/runs/{rid}/analysis")["json"]["generator_available"] is True


@pytest.mark.skipif(not HAS_TPL, reason="plantillas reales no disponibles")
def test_wrong_template_is_rejected_with_a_clear_message(br):
    bridge, S, t = br
    ok = call(bridge, "POST", "/api/templates/aetops-mensual", up=TPL_DIR / "aetops-mensual/1/template.pptx")
    assert ok["status"] == 200
    # un PPTX de otro formato en la ranura equivocada
    bad = call(bridge, "POST", "/api/templates/aetops-mensual", up=TPL_DIR / "glp1-mensual/1/template.pptx")
    assert bad["status"] == 400 and "no corresponde a «AETOPS mensual»" in bad["error"]
    bad2 = call(bridge, "POST", "/api/templates/glp1-mensual", up=TPL_DIR / "aetops-mensual/1/template.pptx")
    assert bad2["status"] == 400 and "GLP-1 mensual" in bad2["error"]
    assert call(bridge, "POST", "/api/templates/aetops-trimestral", up=TPL_DIR / "aetops-mensual/1/template.pptx")["status"] == 400
    # la plantilla válida anterior sigue en su lugar
    assert {x["key"]: x["available"] for x in call(bridge, "GET", "/api/templates")["json"]}["aetops-mensual"]


def test_period_without_data_gives_a_clear_finding_not_a_crash(br, tmp_path):
    bridge, S, t = br
    m = _mod("mrs4")
    f = m.build_aetops(tmp_path / "a.xlsx", until=(2026, 9))
    for unit, build in (("aetops", m.build_aetops), ("glp1", m.build_glp1)):
        rid = call(bridge, "POST", "/api/runs", {"unit": unit, "periodicity": "mensual", "year": 2026, "index": 12})["json"]["id"]
        call(bridge, "POST", f"/api/runs/{rid}/file", up=build(tmp_path / f"{unit}.xlsx", until=(2026, 9)))
        a = call(bridge, "GET", f"/api/runs/{rid}/analysis")
        assert a["status"] == 200, a
        ids = {x["id"] for x in a["json"]["findings"]}
        assert "RAW_PERIOD_EMPTY" in ids and a["json"]["can_generate"] is False and a["json"]["kpis"] == []


def test_ai_rewrite_verifier_accepts_only_wording_changes():
    from backend.app.web.service import verify_rewrite as v
    orig = "En septiembre, la venta total llega a $12.22 M, +56% vs 2025 y +10% vs agosto."
    ok = v(orig, "La venta de septiembre alcanza $12.22 M: +56% frente a 2025 y +10% contra agosto.")
    assert ok["ok"] and "**$12.22 M**" in ok["texto"] and "**+56%**" in ok["texto"] and "**2025**" not in ok["texto"]
    assert not v(orig, "La venta llega a $12.22 M, +56% vs 2025.")["ok"]                          # se perdió +10%
    assert "nueva" in " ".join(v(orig, "La venta llega a $12.22 M, +56% vs 2025, +10% vs agosto y +99%.")["problemas"])
    assert not v(orig, "La venta llega a $12.22 M, +56% vs 2025 y +10% vs agosto debido a una campaña.")["ok"]
    assert not v(orig, "")["ok"] and not v(orig, None)["ok"]
    assert not v(orig, orig + " " + "texto " * 80)["ok"]
    assert not v(orig, "La venta llega a $12.22 M, +56% vs 2025 y +10% vs agosto https://x.co")["ok"]
    assert v(orig, orig)["ok"]                                                                    # idéntico: válido


def test_ai_check_route_logs_what_was_sent(br, tmp_path):
    bridge, S, t = br
    rid = call(bridge, "POST", "/api/runs", {"unit": "aetops", "periodicity": "mensual", "year": 2026, "index": 9})["json"]["id"]
    out = call(bridge, "POST", f"/api/runs/{rid}/ia/check", {"model": "command-a-03-2025", "items": [
        {"original": "Ventas $5 M (+10%).", "rewritten": "Las ventas suman $5 M (+10%)."}, {"original": "Ventas $5 M (+10%).", "rewritten": "Ventas $9 M."}]})
    assert out["status"] == 200 and [x["ok"] for x in out["json"]] == [True, False]
    log = json.loads((Path(S.RUNS_DIR) / rid / "ia_log.json").read_text(encoding="utf-8"))
    assert log[0]["proveedor"] == "Cohere" and log[0]["enviado"][0].startswith("Ventas") and log[0]["recibido"][1]["aceptado"] is False
