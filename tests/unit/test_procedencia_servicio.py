"""Fase 3A-3 · integración con el servicio web: declaración de IA, lista blanca de descargas y generación real (si hay plantilla y LibreOffice)."""
import importlib
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import provenance as pv
from backend.app import provenance_verify as ver
from tests.proc_util import libro

ROOT = Path(__file__).resolve().parents[2]
HAS_TPL = (ROOT / "templates/aetops-mensual/1/template.pptx").exists() and bool(shutil.which("soffice"))


@pytest.fixture()
def cliente(tmp_path, monkeypatch):
    monkeypatch.setenv("REPORT_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("REPORT_HISTORY_DB", str(tmp_path / "h.sqlite"))
    from backend.app.web import service
    importlib.reload(service)
    from backend.app.web import app as appmod
    importlib.reload(appmod)
    return TestClient(appmod.app), service


def _nueva(c):
    return c.post("/api/runs", json={"unit": "aetops", "periodicity": "mensual", "year": 2026, "index": 9}).json()["id"]


def test_ia_info_sin_uso_con_log_y_con_log_corrupto(cliente):
    c, service = cliente
    rid = _nueva(c)
    assert service._ia_info(rid, {}) == {"usada": False, "modelo_declarado": None}
    assert service._ia_info(rid, {"discovery": {"items": [{"x": 1}]}}) == {"usada": True, "modelo_declarado": None}
    log = service._dir(rid) / "ia_log.json"
    log.write_text(json.dumps([{"modelo": "m-1", "enviado": ["secreto"]}, {"modelo": "m-2" * 100, "enviado": ["secreto"]}]), encoding="utf-8")
    info = service._ia_info(rid, {})
    assert info["usada"] is True and len(info["modelo_declarado"]) <= 80 and "secreto" not in json.dumps(info)
    log.write_text("no es json", encoding="utf-8")
    assert service._ia_info(rid, {}) == {"usada": False, "modelo_declarado": None}
    log.write_text("[]", encoding="utf-8")
    assert service._ia_info(rid, {})["usada"] is False
    log.write_text("[1, 2]", encoding="utf-8")
    assert service._ia_info(rid, {}) == {"usada": True, "modelo_declarado": None}


def test_los_archivos_de_procedencia_se_pueden_descargar_y_otros_nombres_no(cliente):
    c, service = cliente
    rid = _nueva(c)
    out = service._dir(rid) / "out"
    out.mkdir()
    for n in ("procedencia.json", "procedencia_error.json", "secreto.txt", "procedencia.json.tmp", ".procedencia.json.abc.tmp"):
        (out / n).write_text("{}", encoding="utf-8")
    assert c.get(f"/api/runs/{rid}/files/procedencia.json").status_code == 200
    assert c.get(f"/api/runs/{rid}/files/procedencia_error.json").status_code == 200
    for n in ("secreto.txt", "procedencia.json.tmp", ".procedencia.json.abc.tmp", "..%2Finput.xlsx", "../input.xlsx"):
        assert c.get(f"/api/runs/{rid}/files/{n}").status_code in (400, 403, 404, 422)


@pytest.mark.skipif(not HAS_TPL, reason="plantilla real o LibreOffice no disponibles (no se versionan)")
def test_generar_por_la_api_deja_procedencia_verificable_en_el_historial(cliente, tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("mm", ROOT / "tools/make_machotes.py")
    mm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mm)
    from backend.app.models import Period
    c, service = cliente
    f = mm.make("aetops", Period("AETOPS", "mensual", 2026, 9), tmp_path, example=True)
    rid = _nueva(c)
    assert c.post(f"/api/runs/{rid}/file", files={"file": ("libro.xlsx", f.read_bytes())}).status_code == 200
    c.put(f"/api/runs/{rid}/targets", json={"total": 1600000})
    assert c.post(f"/api/runs/{rid}/generate").status_code == 200
    r = c.get(f"/api/runs/{rid}/files/procedencia.json")
    assert r.status_code == 200
    m, errs = pv.leer_manifiesto(r.content)
    assert errs == [] and m["configuracion"]["ia"] == {"usada": False, "modelo_declarado": None}
    assert [x["nombre"] for x in m["archivos_fuente"]] == ["input.xlsx"]
    assert ver.verificar(tmp_path / "h.sqlite", 1, service._dir(rid) / "out")["integridad"] == "verificada"
