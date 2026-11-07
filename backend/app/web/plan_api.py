"""Rutas del bloque integral para la API (FastAPI): las mismas que `plan_routes.py` usa en el navegador. Fuera de `app.py` (archivo protegido), que solo la incluye."""
from __future__ import annotations

from fastapi import APIRouter, Body

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
