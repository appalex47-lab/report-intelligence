"""Rutas del bloque integral para el puente del navegador (Pyodide): escenarios de reporte, plan de la corrida y vista previa.

Están FUERA de `bridge.py` (archivo protegido): `bridge.handle` solo delega aquí las rutas que no reconoce (`despachar`). Mismas rutas y mismas respuestas que la API
(`plan_api.py`). No importa FastAPI: en el navegador no existe."""
from __future__ import annotations

import re

from . import plan_service as P
from . import service as S

_ID = r"([a-z0-9][a-z0-9_-]{0,63})"
_RUTAS = [
    ("GET", r"/api/escenarios-reporte", lambda m, b: P.escenarios_reporte()),
    ("PUT", rf"/api/escenarios-reporte/{_ID}", lambda m, b: P.guardar_escenario({**(b or {}), "id": m[1]})),
    ("DELETE", rf"/api/escenarios-reporte/{_ID}", lambda m, b: P.borrar_escenario(m[1])),
    ("GET", r"/api/runs/(\w+)/plan", lambda m, b: P.plan_info(m[1])),
    ("PUT", r"/api/runs/(\w+)/plan", lambda m, b: P.set_plan(m[1], b or {})),
    ("GET", r"/api/runs/(\w+)/preview", lambda m, b: P.vista_previa(m[1])),
]
RUTAS = [(meth, re.compile("^" + pat + "$"), fn) for meth, pat, fn in _RUTAS]


def despachar(method: str, path: str, body) -> dict | None:
    """Respuesta `{"status", "json" | "error"}` si la ruta es de este bloque; `None` si no lo es (el puente responde 404)."""
    for meth, rx, fn in RUTAS:
        mt = rx.match(path)
        if meth == method and mt:
            try:
                return {"status": 200, "json": fn(mt, body)}
            except S.ServiceError as e:
                return {"status": e.status, "error": str(e)}
            except Exception as e:                                     # noqa: BLE001 - al navegador siempre una respuesta legible (igual que bridge.handle)
                return {"status": 500, "error": f"{type(e).__name__}: {e}"}
    return None
