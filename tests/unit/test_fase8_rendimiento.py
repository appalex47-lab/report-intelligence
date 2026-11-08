"""Fase 8 · revisión de rendimiento del motor (CPython, con plantillas reales; se OMITE sin ellas). Límites generosos (≈4× lo medido) para detectar degradaciones graves.
Medido el 2026-11-08 (sin render, equipo de desarrollo): análisis 3.9–8.3 s, generación 5.3–9.7 s, flujo integral (ajuste + revisión) 1.2 s ≈ 9–15 % de la generación,
vista previa servida en 0.01–0.02 s, PPTX 112–147 KB, previsualizacion.json 0.4–0.7 MB, pico de memoria ≈ 540 MB en 8 generaciones seguidas. No es una prueba de carga."""
import importlib
import json
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
TPL = ROOT / "templates"
EJ = ROOT / "data" / "ejemplos"
CASOS = [("aetops", "mensual", 2026, 9, "AETOPS_crudo_ejemplo.xlsx", {"total": "12000000"}, "aetops-mensual"),
         ("glp1", "mensual", 2026, 9, "GLP1_crudo_ejemplo.xlsx", None, "glp1-mensual")]
pytestmark = pytest.mark.skipif(not all((TPL / c[6] / "1/template.pptx").exists() for c in CASOS), reason="OMITIDA (no ejecutada): faltan plantillas reales (no se versionan)")


@pytest.mark.parametrize("unit,per,year,idx,libro,metas,tpl", CASOS, ids=["aetops_mensual", "glp1_mensual"])
def test_tiempos_de_analisis_generacion_y_vista_previa_dentro_de_los_limites(tmp_path, monkeypatch, unit, per, year, idx, libro, metas, tpl):
    monkeypatch.setenv("REPORT_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("REPORT_HISTORY_DB", str(tmp_path / "h" / "h.sqlite"))
    monkeypatch.setenv("REPORT_TEMPLATES_DIR", str(tmp_path / "tpl"))
    (tmp_path / "h").mkdir()
    from backend.app.web import bridge, service
    importlib.reload(service)
    importlib.reload(bridge)
    service.RENDER = False

    def call(method, path, body=None, up=None):
        return json.loads(bridge.handle(method, path, json.dumps(body) if body is not None else "", str(up) if up else "", up.name if up else ""))

    assert call("POST", f"/api/templates/{tpl}", up=TPL / tpl / "1/template.pptx")["status"] == 200
    rid = call("POST", "/api/runs", {"unit": unit, "periodicity": per, "year": year, "index": idx})["json"]["id"]
    assert call("POST", f"/api/runs/{rid}/file", up=EJ / libro)["status"] == 200
    if metas:
        call("PUT", f"/api/runs/{rid}/targets", metas)
    t = time.perf_counter()
    assert call("GET", f"/api/runs/{rid}/analysis")["status"] == 200
    analisis = time.perf_counter() - t
    t = time.perf_counter()
    assert call("POST", f"/api/runs/{rid}/generate", {})["status"] == 200
    generacion = time.perf_counter() - t
    t = time.perf_counter()
    vp = call("GET", f"/api/runs/{rid}/preview")
    preview = time.perf_counter() - t
    out = service._dir(rid) / "out"
    assert analisis < 40 and generacion < 60 and preview < 2, (analisis, generacion, preview)
    assert vp["status"] == 200 and (out / "previsualizacion.json").stat().st_size < 3_000_000                 # el modelo de la vista previa sigue siendo ligero
    assert next(out.glob("*.pptx")).stat().st_size < 1_000_000
