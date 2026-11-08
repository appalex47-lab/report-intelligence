"""Rutas de la API (FastAPI) que completan el contrato con el puente del navegador: las del bloque integral (las mismas que `plan_routes.py`) y las dos que solo existían en el
puente (`POST /api/runs/{id}/ia/check` y `GET /api/history/export`, Fase 8). Fuera de `app.py` (archivo protegido), que solo incluye este router."""
from __future__ import annotations

from fastapi import APIRouter, Body
from fastapi.responses import FileResponse

from . import plan_service as P

router = APIRouter()


@router.get("/api/escenarios-reporte")
def escenarios_reporte():
    return P.escenarios_reporte()


@router.put("/api/escenarios-reporte/{eid}")
def escenario_guardar(eid: str, body: dict = Body(...)):
    return P.guardar_escenario({**body, "id": eid})


@router.delete("/api/escenarios-reporte/{eid}")
def escenario_borrar(eid: str):
    return P.borrar_escenario(eid)


@router.get("/api/runs/{rid}/plan")
def plan_get(rid: str):
    return P.plan_info(rid)


@router.put("/api/runs/{rid}/plan")
def plan_put(rid: str, body: dict = Body(...)):
    return P.set_plan(rid, body)


@router.get("/api/runs/{rid}/preview")
def preview(rid: str):
    return P.vista_previa(rid)


@router.post("/api/runs/{rid}/ia/check")
def ia_check(rid: str, body: dict = Body(...)):
    """Igual que el puente: valida las reescrituras propuestas por la IA y deja constancia en ia_log.json."""
    return P.S.check_rewrites(rid, body.get("items", []), str(body.get("model", "")))


@router.get("/api/history/export")
def history_export():
    """Igual que el puente: descarga del historial SQLite (404 «Aún no hay historial.» si no existe)."""
    if not P.S.HISTORY_DB.exists():
        raise P.S.ServiceError("Aún no hay historial.", 404)
    return FileResponse(P.S.HISTORY_DB, filename="historial.sqlite", media_type="application/octet-stream")
