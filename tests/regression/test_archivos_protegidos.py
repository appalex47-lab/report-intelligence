"""No-regresión estructural (Fase 2B): los archivos de la aplicación que las fases de reglas no deben tocar siguen idénticos.

Cubre rutas de ejecución, importadores, cálculos, narrativa, escenarios heredados (E1/E2), láminas/relleno de plantillas,
QA, historial y la interfaz. Si una fase autorizada cambia uno, se actualiza `tests/regression/protegidos.json`
(`python tools/archivos_protegidos.py --write`) junto con su justificación; no se acepta una diferencia en silencio.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools import archivos_protegidos as ap  # noqa: E402

NUCLEO = ["backend/app/pipeline.py", "backend/app/build.py", "backend/app/cli.py", "backend/app/raw/glp1.py", "backend/app/raw/aetops.py",
          "backend/app/raw/common.py", "backend/app/narrative/rules.py", "backend/app/narrative/executive.py", "backend/app/narrative/glp1_exec.py",
          "backend/app/deck/glp1_mensual.py", "backend/app/deck/aetops_mensual.py", "backend/app/importer/base_sheet.py",
          "backend/app/validator/rules.py", "backend/app/web/service.py", "backend/app/history/store.py", "profiles/glp1/mensual.yaml", "frontend/index.html"]


def test_el_manifiesto_cubre_el_nucleo_de_la_aplicacion():
    datos = json.loads(ap.MANIFIESTO.read_text(encoding="utf-8"))["archivos"]
    assert not [f for f in NUCLEO if f not in datos]


def test_los_archivos_protegidos_no_han_cambiado():
    assert ap.verificar() == []
