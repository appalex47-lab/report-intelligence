"""API de la pantalla de revisión. Arranque: uvicorn backend.app.web.app:app --port 8000"""
from __future__ import annotations

from pathlib import Path

from fastapi import Body, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from . import service as S

FRONT = Path(__file__).resolve().parents[3] / "frontend"
app = FastAPI(title="Report Intelligence", docs_url=None, redoc_url=None)


@app.exception_handler(S.ServiceError)
async def _err(_, e: S.ServiceError):
    return JSONResponse({"error": str(e)}, status_code=e.status)


@app.post("/api/runs")
def create(body: dict = Body(...)):
    try:
        return S.create_run(body["unit"], body["periodicity"], int(body["year"]), int(body["index"]))
    except (KeyError, ValueError, TypeError):
        raise HTTPException(400, "Faltan datos: unit, periodicity, year, index.") from None


@app.get("/api/runs/{rid}")
def get(rid: str):
    return S.get_run(rid)


@app.post("/api/runs/{rid}/file")
async def upload(rid: str, file: UploadFile = File(...)):
    data = await file.read(S.MAX_UPLOAD + 1)
    return S.store_file(rid, file.filename or "", data)


@app.put("/api/runs/{rid}/targets")
def targets(rid: str, body: dict = Body(...)):
    return S.set_targets(rid, body)


@app.put("/api/runs/{rid}/context")
def context(rid: str, body: dict = Body(...)):
    return S.set_context(rid, body.get("items", []))


@app.put("/api/runs/{rid}/edits")
def edits(rid: str, body: dict = Body(...)):
    return S.set_edits(rid, body)


@app.get("/api/runs/{rid}/analysis")
def analysis(rid: str):
    return S.analyze(rid)


@app.get("/api/runs/{rid}/narrative")
def narrative(rid: str):
    return S.narrative(rid)


@app.post("/api/runs/{rid}/verify")
def verify(rid: str, body: dict = Body(...)):
    return S.verify_text(rid, [str(t) for t in body.get("texts", [])], body.get("allowed"))


@app.get("/api/runs/{rid}/ia/facts")
def ia_facts(rid: str):
    return S.discovery_facts(rid)


@app.post("/api/runs/{rid}/ia/discovery/check")
def ia_discovery_check(rid: str, body: dict = Body(...)):
    return S.check_discovery(rid, body.get("payload"), str(body.get("model", "")))


@app.put("/api/runs/{rid}/discovery")
def discovery_set(rid: str, body: dict = Body(...)):
    return S.set_discovery(rid, body)


@app.post("/api/runs/{rid}/generate")
def generate(rid: str, anexo: bool | None = None):
    return S.generate(rid, anexo)


@app.get("/api/runs/{rid}/result")
def result(rid: str):
    return S.result_info(rid)


@app.get("/api/runs/{rid}/files/{name}")
def files(rid: str, name: str):
    return FileResponse(S.file_path(rid, name), filename=name if not name.endswith(".png") else None)


@app.get("/api/templates")
def templates():
    return S.list_templates()


@app.post("/api/templates/{key}")
async def template_upload(key: str, file: UploadFile = File(...)):
    return S.save_template(key, file.filename or "", await file.read(S.MAX_UPLOAD + 1))


@app.get("/api/info")
def info():
    return {"render": S.RENDER, "browser": S.IN_BROWSER}


@app.get("/api/history/runs")
def h_runs(unit: str | None = None):
    return S.history_runs(unit)


@app.get("/api/history/trends")
def h_trends(unit: str = "aetops", periodicity: str = "mensual"):
    return S.history_trends(unit, periodicity)


@app.get("/api/machote")
def machote(unit: str, periodicity: str, year: int, index: int):
    p = S.machote(unit, periodicity, year, index)
    return FileResponse(p, filename=p.name)


@app.get("/")
def index():
    return FileResponse(FRONT / "index.html")
