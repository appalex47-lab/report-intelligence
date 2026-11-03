"""API de la pantalla de revisión (sin plantillas reales: la generación se prueba solo si existen en templates/)."""
import importlib
import io
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.fixtures import build_base

ROOT = Path(__file__).resolve().parents[2]
HAS_TPL = (ROOT / "templates/aetops-mensual/1/template.pptx").exists() and bool(shutil.which("soffice"))   # estos tests renderizan con LibreOffice


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("REPORT_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("REPORT_HISTORY_DB", str(tmp_path / "h.sqlite"))
    from backend.app.web import service
    importlib.reload(service)
    from backend.app.web import app as appmod
    importlib.reload(appmod)
    return TestClient(appmod.app)


def _run(c, unit="aetops", per="mensual", year=2026, idx=9):
    return c.post("/api/runs", json={"unit": unit, "periodicity": per, "year": year, "index": idx}).json()["id"]


def _upload(c, rid, path: Path, name="libro.xlsx"):
    return c.post(f"/api/runs/{rid}/file", files={"file": (name, path.read_bytes())})


def test_flow_validation_and_targets_required(client, tmp_path):
    rid = _run(client)
    assert client.get(f"/api/runs/{rid}/analysis").status_code == 400            # sin libro
    assert _upload(client, rid, build_base(tmp_path / "b.xlsx")).status_code == 200
    a = client.get(f"/api/runs/{rid}/analysis").json()
    assert "TARGETS_MISSING" in [f["id"] for f in a["findings"]] and not a["can_generate"]
    assert a["targets_required"] and a["targets_lines"] == []
    client.put(f"/api/runs/{rid}/targets", json={"total": "$2,000", "AE-A": 1000})
    a = client.get(f"/api/runs/{rid}/analysis").json()
    assert "TARGETS_MISSING" not in [f["id"] for f in a["findings"]] or a["cumplimiento"]
    assert a["cumplimiento"][0]["nombre"] == "TOTAL"


def test_upload_security(client, tmp_path):
    rid = _run(client)
    assert client.post(f"/api/runs/{rid}/file", files={"file": ("x.xlsm", b"PK\x03\x04")}).status_code == 400
    assert client.post(f"/api/runs/{rid}/file", files={"file": ("x.xlsx", b"no es zip")}).status_code == 400
    assert client.get("/api/runs/no-es-un-id").status_code == 404
    assert client.get(f"/api/runs/{'0' * 32}").status_code == 404
    assert client.put(f"/api/runs/{rid}/targets", json={"total": "abc"}).status_code == 400
    assert client.put(f"/api/runs/{rid}/targets", json={"total": "-5"}).status_code == 400
    assert client.post("/api/runs", json={"unit": "x", "periodicity": "mensual", "year": 2026, "index": 1}).status_code == 400
    assert client.post("/api/runs", json={"unit": "aetops", "periodicity": "mensual", "year": 2026, "index": 13}).status_code == 400


def test_files_whitelist_and_no_download_before_generate(client):
    rid = _run(client)
    assert client.get(f"/api/runs/{rid}/files/run.json").status_code == 404
    assert client.get(f"/api/runs/{rid}/files/..%2Frun.json").status_code == 404
    assert client.get(f"/api/runs/{rid}/result").status_code == 404


def _unused_test_glp1_generator_unavailable(client):
    rid = _run(client, "glp1")
    ex = ROOT / "data/GLP1_sintetico_limpio.xlsx"
    assert _upload(client, rid, ex).status_code == 200
    a = client.get(f"/api/runs/{rid}/analysis").json()
    assert a["generator_available"] is False and a["can_generate"] is False
    assert client.post(f"/api/runs/{rid}/generate").status_code == 501
    assert client.get(f"/api/runs/{rid}/narrative").status_code == 501


def test_machote_download_and_example_imports_clean(client, tmp_path):
    r = client.get("/api/machote", params={"unit": "aetops", "periodicity": "mensual", "year": 2026, "index": 9})
    assert r.status_code == 200 and r.content[:2] == b"PK"
    assert client.get("/api/machote", params={"unit": "aetops", "periodicity": "mensual", "year": 2026, "index": 14}).status_code == 400
    import importlib.util
    spec = importlib.util.spec_from_file_location("mm", ROOT / "tools/make_machotes.py")
    mm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mm)
    from backend.app.models import Period
    from backend.app.pipeline import run_aetops
    p = Period("AETOPS", "mensual", 2026, 9)
    f = mm.make("aetops", p, tmp_path, example=True)
    res = run_aetops(f, "mensual", p)
    assert res.findings == [] and res.can_generate


@pytest.mark.skipif(not HAS_TPL, reason="plantilla real no disponible (no se versiona)")
def test_generate_with_machote_example(client, tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("mm", ROOT / "tools/make_machotes.py")
    mm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mm)
    from backend.app.models import Period
    f = mm.make("aetops", Period("AETOPS", "mensual", 2026, 9), tmp_path, example=True)
    rid = _run(client)
    assert _upload(client, rid, f).status_code == 200
    client.put(f"/api/runs/{rid}/targets", json={"total": 1600000})
    n = client.get(f"/api/runs/{rid}/narrative")
    assert n.status_code == 200 and n.json()["secciones"][0]["clave"] == "resumen_ejecutivo"
    v = client.post(f"/api/runs/{rid}/verify", json={"texts": ["Vendimos $999 M por una promoción"]}).json()
    assert v[0]["problemas"]
    g = client.post(f"/api/runs/{rid}/generate")
    assert g.status_code == 200
    info = g.json()
    assert info["pptx"] and info["slides"]
    assert (client.get(f"/api/runs/{rid}/files/{info['pptx']}").status_code == 200) == info["downloadable"]


@pytest.mark.skipif(not HAS_TPL, reason="plantilla real no disponible (no se versiona)")
def test_generate_from_raw_data(client, tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("mrs", ROOT / "tools/make_raw_synthetic.py")
    mrs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mrs)
    f = mrs.build(tmp_path / "crudo.xlsx")
    rid = _run(client)
    assert _upload(client, rid, f).status_code == 200
    client.put(f"/api/runs/{rid}/targets", json={"total": 9000000})
    a = client.get(f"/api/runs/{rid}/analysis").json()
    assert a["can_generate"], [x for x in a["findings"] if x["severity"] == "block"]
    g = client.post(f"/api/runs/{rid}/generate")
    assert g.status_code == 200, g.text
    info = g.json()
    assert info["pptx"] and info["slides"]
    print([i for i in info["qa"]["issues"] if i["severity"] != "info"])


def test_glp1_raw_validates_via_api(client, tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("mg", ROOT / "tools/make_raw_glp1_synthetic.py")
    mg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mg)
    rid = _run(client, "glp1")
    assert _upload(client, rid, mg.build(tmp_path / "g.xlsx")).status_code == 200
    a = client.get(f"/api/runs/{rid}/analysis").json()
    assert not [f for f in a["findings"] if f["severity"] == "block"] and a["targets_required"] is False


@pytest.mark.skipif(not (ROOT / "templates/glp1-mensual/1/template.pptx").exists() or not shutil.which("soffice"), reason="requiere plantilla GLP-1 real y LibreOffice")
def test_glp1_generate_via_api(client, tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("mg", ROOT / "tools/make_raw_glp1_synthetic.py")
    mg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mg)
    rid = _run(client, "glp1")
    _upload(client, rid, mg.build(tmp_path / "g.xlsx"))
    n = client.get(f"/api/runs/{rid}/narrative")
    assert n.status_code == 200 and n.json()["secciones"][0]["clave"] == "resumen_ejecutivo"
    g = client.post(f"/api/runs/{rid}/generate")
    assert g.status_code == 200 and g.json()["downloadable"] and g.json()["pptx"].startswith("Resultados_GLP1")
