"""Puente sin servidor: las mismas rutas del API (`app.py`) atendidas dentro del navegador (Pyodide) o en pruebas.

    handle(method, path, body_json="", upload_path="", upload_name="") -> JSON str
        {"status": 200, "json": ...}                        respuesta JSON
        {"status": 200, "file": "/ruta", "name": "x.pptx"}   archivo (el navegador lo lee del sistema de archivos virtual)
        {"status": 4xx, "error": "mensaje"}
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import service as S

ROUTES: list[tuple[str, re.Pattern, str]] = []


def route(method: str, pattern: str):
    def deco(fn):
        ROUTES.append((method, re.compile("^" + pattern + "$"), fn.__name__))
        return fn
    return deco


def _file(path: Path, name: str | None = None) -> dict:
    return {"status": 200, "file": str(path), "name": name or path.name}


@route("POST", r"/api/runs")
def create(m, body, up):
    try:
        return {"status": 200, "json": S.create_run(body["unit"], body["periodicity"], int(body["year"]), int(body["index"]))}
    except (KeyError, ValueError, TypeError):
        return {"status": 400, "error": "Faltan datos: unit, periodicity, year, index."}


@route("GET", r"/api/runs/(\w+)")
def get(m, body, up):
    return {"status": 200, "json": S.get_run(m[1])}


@route("POST", r"/api/runs/(\w+)/file")
def upload(m, body, up):
    return {"status": 200, "json": S.store_file(m[1], up[1], Path(up[0]).read_bytes())}


@route("PUT", r"/api/runs/(\w+)/targets")
def targets(m, body, up):
    return {"status": 200, "json": S.set_targets(m[1], body or {})}


@route("PUT", r"/api/runs/(\w+)/context")
def context(m, body, up):
    return {"status": 200, "json": S.set_context(m[1], (body or {}).get("items", []))}


@route("PUT", r"/api/runs/(\w+)/edits")
def edits(m, body, up):
    return {"status": 200, "json": S.set_edits(m[1], body or {})}


@route("GET", r"/api/runs/(\w+)/analysis")
def analysis(m, body, up):
    return {"status": 200, "json": S.analyze(m[1])}


@route("GET", r"/api/runs/(\w+)/narrative")
def narrative(m, body, up):
    return {"status": 200, "json": S.narrative(m[1])}


@route("POST", r"/api/runs/(\w+)/verify")
def verify(m, body, up):
    b = body or {}
    return {"status": 200, "json": S.verify_text(m[1], [str(t) for t in b.get("texts", [])], b.get("allowed"))}


@route("POST", r"/api/runs/(\w+)/generate")
def generate(m, body, up):
    return {"status": 200, "json": S.generate(m[1])}


@route("GET", r"/api/runs/(\w+)/result")
def result(m, body, up):
    return {"status": 200, "json": S.result_info(m[1])}


@route("GET", r"/api/runs/(\w+)/files/([^/]+)")
def files(m, body, up):
    return _file(S.file_path(m[1], m[2]))


@route("POST", r"/api/runs/(\w+)/ia/check")
def ia_check(m, body, up):
    b = body or {}
    return {"status": 200, "json": S.check_rewrites(m[1], b.get("items", []), str(b.get("model", "")))}


@route("GET", r"/api/templates")
def templates(m, body, up):
    return {"status": 200, "json": S.list_templates()}


@route("POST", r"/api/templates/([\w\-]+)")
def template_upload(m, body, up):
    return {"status": 200, "json": S.save_template(m[1], up[1], Path(up[0]).read_bytes())}


@route("GET", r"/api/history/runs")
def h_runs(m, body, up):
    return {"status": 200, "json": S.history_runs((body or {}).get("unit"))}


@route("GET", r"/api/history/trends")
def h_trends(m, body, up):
    b = body or {}
    return {"status": 200, "json": S.history_trends(b.get("unit", "aetops"), b.get("periodicity", "mensual"))}


@route("GET", r"/api/history/export")
def h_export(m, body, up):
    if not S.HISTORY_DB.exists():
        return {"status": 404, "error": "Aún no hay historial."}
    return _file(S.HISTORY_DB, "historial.sqlite")


@route("GET", r"/api/machote")
def machote(m, body, up):
    b = body or {}
    p = S.machote(b["unit"], b["periodicity"], int(b["year"]), int(b["index"]))
    return _file(p)


@route("GET", r"/api/info")
def info(m, body, up):
    return {"status": 200, "json": {"render": S.RENDER, "browser": S.IN_BROWSER}}


def handle(method: str, path: str, body_json: str = "", upload_path: str = "", upload_name: str = "") -> str:
    body = json.loads(body_json) if body_json else None
    for meth, rx, fname in ROUTES:
        mt = rx.match(path)
        if meth == method and mt:
            try:
                out = globals()[fname](mt, body, (upload_path, upload_name))
            except S.ServiceError as e:
                out = {"status": e.status, "error": str(e)}
            except Exception as e:                                     # noqa: BLE001 - al navegador siempre una respuesta legible
                out = {"status": 500, "error": f"{type(e).__name__}: {e}"}
            return json.dumps(out, ensure_ascii=False, default=str)
    return json.dumps({"status": 404, "error": "Ruta no encontrada."})
