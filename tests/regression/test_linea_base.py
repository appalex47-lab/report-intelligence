"""Mecanismo anti-regresión de la Fase 1 (P-00 / T-13): compara la salida actual con la foto de la línea base.

* Capa `engine` (valores, hallazgos): siempre se ejecuta; no necesita plantillas.
* Capa `deck` (texto y geometría del PPTX): solo si la plantilla local existe y tiene el mismo SHA-256 que la usada
  al capturar la foto. Si no, se OMITE con motivo (nunca se da por aprobada).

Si una prueba falla, NO se actualiza la foto: primero se justifica el cambio en CAMBIOS_JUSTIFICADOS.md.
Regenerar la foto: python tools/capture_baseline.py --write
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools import capture_baseline as cb  # noqa: E402

BASE = Path(__file__).resolve().parent / "base"
NAMES = list(cb.SCENARIOS)


def test_la_foto_de_la_linea_base_existe():
    faltan = [n for n in NAMES if not (BASE / "engine" / f"{n}.json").exists()]
    assert not faltan, f"Falta la foto de la línea base: {faltan} (python tools/capture_baseline.py --write)"


@pytest.mark.parametrize("name", NAMES)
def test_motor_y_hallazgos_identicos_a_la_linea_base(name):
    stored = json.loads((BASE / "engine" / f"{name}.json").read_text(encoding="utf-8"))
    actual = json.loads(cb._dump(cb.capture_engine(name)))
    assert cb.diff(stored, actual) == []


@pytest.mark.parametrize("name", NAMES)
def test_severity_y_id_de_hallazgos_se_conservan(name):
    """Compatibilidad: `severity` sigue siendo block|warn|info y cada hallazgo conserva su id."""
    stored = json.loads((BASE / "engine" / f"{name}.json").read_text(encoding="utf-8"))
    actual = cb.capture_engine(name)
    assert [(f["id"], f["severity"]) for f in actual["hallazgos"]] == [(f["id"], f["severity"]) for f in stored["hallazgos"]]
    assert {f["severity"] for f in actual["hallazgos"]} <= {"block", "warn", "info"}


@pytest.mark.parametrize("name", NAMES)
def test_deck_identico_a_la_linea_base(name):
    dpath = BASE / "deck" / f"{name}.json"
    if not dpath.exists():
        pytest.skip("sin foto guardada del deck (se capturó sin plantilla)")
    stored = json.loads(dpath.read_text(encoding="utf-8"))
    tpl = cb.TEMPLATES / stored["plantilla"]
    if not tpl.exists():
        pytest.skip("plantilla real no disponible (no se versiona)")
    if cb.sha256(tpl) != stored["plantilla_sha256"]:
        pytest.skip("la plantilla local tiene otro SHA-256 que la usada en la foto")
    actual = json.loads(cb._dump(cb.capture_deck(name)))
    assert cb.diff(stored, actual) == []
