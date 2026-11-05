"""Fase 3A-3 · la procedencia NO altera el reporte (decisión D-A) en el flujo real de `build_*` con la plantilla local.

Necesita las plantillas reales (gitignoradas); sin ellas se omite con ese motivo. Se compara una generación con procedencia contra otra con la
captura forzada a fallar: PPTX (texto y geometría), narrativa, QA y manifiesto del reporte deben ser idénticos."""
import json
import sqlite3

import pytest

from backend.app import build as B
from backend.app import provenance_verify as ver
from backend.app.history import store as hist
from backend.app.models import Period
from tools import capture_baseline as cb

ESC = list(cb.SCENARIOS)
pytestmark = pytest.mark.skipif(not all((cb.TEMPLATES / s[5] / "1" / "template.pptx").is_file() for s in cb.SCENARIOS.values()),
                                reason="faltan las plantillas reales (no se versionan): la generación real no puede ejecutarse")


def _generar(nombre, destino, con_historial=True):
    unidad, per, anio, idx, libro, tpl = cb.SCENARIOS[nombre]
    periodo = Period(unidad, per, anio, idx)
    plantilla = cb.TEMPLATES / tpl / "1" / "template.pptx"
    fuente = cb.DATA / libro
    db = destino / "h.sqlite" if con_historial else None
    if unidad == "AETOPS":
        from backend.app.pipeline import run_aetops_raw
        res = run_aetops_raw(fuente, periodo)
        return B.build_aetops(res, periodo, plantilla, destino / "out", render=False, sources=[fuente], history_db=db), db
    from backend.app.pipeline import run_glp1_raw
    res = run_glp1_raw(fuente, periodo)
    return B.build_glp1(res, periodo, plantilla, destino / "out", render=False, sources=[fuente], history_db=db), db


def _huella(carpeta, b):
    from tests.regression.test_hash_resultado import ROOT  # noqa: F401
    m = {k: v for k, v in b.manifest.items() if k not in ("historial",)}
    return {"slides": cb._slide_texts(b.pptx), "narrative": (carpeta / "narrative.json").read_text(encoding="utf-8"),
            "qa": (carpeta / "qa_report.json").read_text(encoding="utf-8"), "manifest": m}


@pytest.mark.parametrize("nombre", ESC)
def test_el_reporte_es_identico_con_y_sin_procedencia_y_queda_verificable(nombre, tmp_path, monkeypatch):
    con, db = _generar(nombre, tmp_path / "con")
    assert con.procedencia["estado"] == "registrada" and con.procedencia["error"] is None
    carpeta = tmp_path / "con" / "out"
    monkeypatch.setattr(B, "registrar_procedencia", lambda **k: (_ for _ in ()).throw(RuntimeError("procedencia caída")))
    sin, _ = _generar(nombre, tmp_path / "sin")
    assert sin.procedencia["estado"] == "error"                                    # el fallo de procedencia se informa…
    assert (tmp_path / "sin" / "out" / "procedencia.json").exists() is False       # …y no deja manifiesto
    a, b = _huella(carpeta, con), _huella(tmp_path / "sin" / "out", sin)
    assert a["slides"] == b["slides"] and a["narrative"] == b["narrative"] and a["qa"] == b["qa"]                  # …sin cambiar el reporte
    assert {k: v for k, v in a["manifest"].items() if k not in ("pptx_sha256",)} == {k: v for k, v in b["manifest"].items() if k not in ("pptx_sha256",)}
    v = ver.verificar(db, con.procedencia["run_id"], carpeta)
    assert (v["integridad"], v["copia"]["estado"]) == ("verificada", "integra")


def test_el_historial_de_runs_no_cambia_de_contrato(tmp_path):
    _, db = _generar(ESC[0], tmp_path)
    con = hist.connect(db)
    assert [r[1] for r in con.execute("PRAGMA table_info(runs)")] == [
        "id", "unit", "periodicity", "year", "idx", "version", "created_at", "profile", "template", "template_sha", "pptx_sha", "pdf_sha",
        "qa_passed", "downloadable", "findings", "narrative", "context"]
    con.close()
