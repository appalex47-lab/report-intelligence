"""El historial de motivos de autorización de los archivos protegidos no se pierde (incidente del PR #31: `--autorizar` reemplaza el motivo previo).

No modifica ni sustituye a `tools/archivos_protegidos.py`; solo exige que, para los archivos tocados por el bloque integral, el motivo vigente SIGA
conteniendo el rastro de las autorizaciones anteriores (fases 3A, 4, 5 y el cambio del usuario, commit 67fd179). Un `--check` verde no es consentimiento del
propietario; esta prueba tampoco lo es: solo detecta que se borró historia."""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
D = json.loads((ROOT / "tests" / "regression" / "protegidos.json").read_text(encoding="utf-8"))["autorizados"]

# archivo → fragmentos de motivos anteriores que deben seguir apareciendo (verbatim de `main` antes del bloque integral)
HISTORIAL = {
    "backend/app/build.py": ["AC-14, RQ-19", "RQ-13", "Fase 3A-3"],
    "backend/app/web/service.py": ["RQ-19", "Fase 5: anexo de calidad de datos", "Fase 4: añade la clave escenarios_indicador", "Fase 3A-3"],
    "backend/app/web/bridge.py": ["Fase 5 (RQ-19)"],
    "backend/app/web/app.py": ["Fase 5 (RQ-19)"],
    "frontend/index.html": ["Fase 5 (RQ-19)", "INC-001", "Fase 4: panel de escenarios", "commit 67fd179"],
    "frontend/worker.js": ["commit 67fd179"],
}


@pytest.mark.parametrize("archivo", sorted(HISTORIAL))
def test_el_motivo_conserva_el_historial_de_autorizaciones_anteriores(archivo):
    motivo = D[archivo]["motivo"]
    faltan = [f for f in HISTORIAL[archivo] if f not in motivo]
    assert not faltan, f"{archivo}: el motivo perdió historial previo {faltan}. No uses --autorizar sobre un archivo con motivos anteriores sin conservarlos."
    assert "Bloque integral" in motivo and "Antes —" in motivo       # el motivo nuevo no reemplaza: se antepone


def test_todo_archivo_autorizado_tiene_motivo_y_hash():
    for k, v in D.items():
        assert v.get("motivo", "").strip() and len(v.get("sha256", "")) == 64, k
