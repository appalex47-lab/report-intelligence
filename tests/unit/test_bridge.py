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
