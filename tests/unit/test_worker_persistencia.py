"""Persistencia de `frontend/worker.js` (archivo protegido): escenarios propios (PUT/DELETE), recarga, historial existente y la persistencia anterior.
Ejecuta el worker real en Node (`vm`) con IndexedDB/Pyodide simulados; corre en CI. Si no hay Node se OMITE con motivo (no se cuenta como aprobada).
La comprobación con Pyodide y SQLite reales está en tests/e2e/test_persistencia_escenarios.py (solo local)."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HARNES = ROOT / "tests" / "unit" / "worker_persistencia.mjs"
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="OMITIDA (no ejecutada): no hay Node.js en este entorno")


def _correr(worker: Path | None = None):
    env = dict(os.environ)
    if worker:
        env["WORKER_JS"] = str(worker)
    p = subprocess.run([NODE, str(HARNES)], capture_output=True, text=True, timeout=120, env=env)
    return p.returncode, json.loads(p.stdout.strip().splitlines()[-1]) if p.stdout.strip() else {"stderr": p.stderr}


def test_el_worker_actual_persiste_escenarios_y_conserva_la_persistencia_anterior():
    rc, r = _correr()
    assert rc == 0 and not r.get("fallos"), r
    assert len(r["resultados"]) >= 12 and all(r["resultados"].values())


def test_el_arnes_detecta_la_regresion_si_se_quita_la_persistencia_de_escenarios(tmp_path):
    """Mutación: sin la línea nueva de worker.js, el PUT/DELETE no persiste y la prueba debe fallar (así se sabe que sí protege)."""
    src = (ROOT / "frontend" / "worker.js").read_text(encoding="utf-8")
    viejo = src.replace(' || (/^\\/api\\/escenarios-reporte\\//.test(m.path) && (m.method === "PUT" || m.method === "DELETE"))', "")
    assert viejo != src
    f = tmp_path / "worker.js"
    f.write_text(viejo, encoding="utf-8")
    rc, r = _correr(f)
    assert rc == 1 and {"put_persiste_historial", "delete_persiste_historial"} <= {x.split(":")[0] for x in r["fallos"]}, r
