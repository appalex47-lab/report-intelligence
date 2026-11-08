"""Selección de plantillas PPTX para las pruebas.

Las plantillas REALES no se versionan (marca y datos comerciales: `templates/README.md`). Las pruebas que las necesitan usan, en este orden:
  1. las reales, si están en `templates/` (equipo de desarrollo);
  2. las SINTÉTICAS versionadas en `tests/fixtures/plantillas_sinteticas/` (CI y cualquier clon limpio): misma estructura, sin marca ni datos
     (ver tools/make_plantillas_sinteticas.py y tests/unit/test_plantillas_sinteticas.py).
`REPORT_PLANTILLAS=sinteticas` fuerza las sintéticas aunque existan las reales (para comprobar que CI y local ven lo mismo); `reales` exige las reales.
Nunca se mezclan: `origen()` dice cuál se está usando, y lo que dependa de la plantilla real (línea base de contenido, pruebas golden) sigue omitiéndose sin ella.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REALES = ROOT / "templates"
SINTETICAS = ROOT / "tests" / "fixtures" / "plantillas_sinteticas"
FORMATOS = ("aetops-mensual", "aetops-trimestral", "glp1-mensual", "glp1-trimestral")


def origen() -> str:
    modo = os.environ.get("REPORT_PLANTILLAS", "").lower()
    if modo == "sinteticas":
        return "sinteticas"
    if all((REALES / f / "1" / "template.pptx").exists() for f in FORMATOS) or modo == "reales":
        return "reales"
    return "sinteticas"


def ruta(formato: str) -> Path:
    base = REALES if origen() == "reales" else SINTETICAS
    return base / formato / "1" / "template.pptx"


def disponible(formato: str) -> bool:
    return ruta(formato).exists()
