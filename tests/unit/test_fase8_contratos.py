"""Fase 8 · estabilización: contratos entre módulos y verificación de artefactos. Corre en CI (sin plantillas ni navegador).

1. El puente del navegador (`bridge.py` + `plan_routes.py`) y la API (`app.py` + `plan_api.py`) exponen EXACTAMENTE las mismas rutas y métodos: la aplicación publicada (puente) y la de
   desarrollo (API) no pueden divergir en silencio.
2. Cada ruta del contrato responde con las mismas claves por ambos caminos.
3. El paquete que se publica (`app.zip`) contiene todo lo que el motor necesita y nada que no deba publicarse; su construcción es determinista en contenido.
4. Las dependencias declaradas coinciden con las que se empaquetan para el navegador."""
import hashlib
import importlib
import io
import json
import re
import zipfile
from pathlib import Path

import openpyxl
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
EJEMPLO = ROOT / "data" / "ejemplos" / "AETOPS_crudo_ejemplo.xlsx"


def _normalizar(patron: str) -> str:
    p = patron.lstrip("^").rstrip("$")
    p = re.sub(r"\(\\w\+\)", "{id}", p)
    p = re.sub(r"\(\[a-z0-9\]\[a-z0-9_-\]\{0,63\}\)", "{id}", p)
    p = re.sub(r"\([^)]*\)", "{id}", p)
    return re.sub(r"\{[a-z_]+\}", "{id}", p)


@pytest.fixture()
def entorno(tmp_path, monkeypatch):
    monkeypatch.setenv("REPORT_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("REPORT_HISTORY_DB", str(tmp_path / "h" / "h.sqlite"))
    monkeypatch.setenv("REPORT_TEMPLATES_DIR", str(tmp_path / "tpl"))
    (tmp_path / "h").mkdir()
    from backend.app.web import app as appmod, bridge, plan_api, plan_routes, plan_service, service
    for m in (service, plan_service, plan_routes, plan_api, bridge, appmod):
        importlib.reload(m)
    return appmod, bridge, plan_routes, tmp_path


# ------------------------------------------------------------------------------------------------------------ 1. mismas rutas en el puente y en la API
def test_el_puente_y_la_api_exponen_las_mismas_rutas_y_metodos(entorno):
    appmod, bridge, plan_routes, _ = entorno
    del_puente = {(m, _normalizar(rx.pattern)) for m, rx, _ in bridge.ROUTES} | {(m, _normalizar(rx.pattern)) for m, rx, _ in plan_routes.RUTAS}
    de_la_api = set()
    for ruta, ops in appmod.app.openapi()["paths"].items():
        for metodo in ops:
            de_la_api.add((metodo.upper(), re.sub(r"\{[^}]+\}", "{id}", ruta)))
    de_la_api -= {("GET", "/")}                                                        # la página estática solo existe en la API de desarrollo
    solo_puente, solo_api = del_puente - de_la_api, de_la_api - del_puente
    # Divergencias CONOCIDAS (documentadas en docs/fase6_7_8/FASES_6_7_8.md §6): se listan para que cualquier otra diferencia falle.
    # El producto publicado es el puente; el servidor de desarrollo (API) no tiene la comprobación de la IA ni la exportación del historial.
    SOLO_PUENTE_CONOCIDAS = {("GET", "/api/history/export"), ("POST", "/api/runs/{id}/ia/check")}
    SOLO_API_CONOCIDAS = {("POST", "/api/templates/{id}"), ("GET", "/api/runs/{id}/files/{id}")}                # el puente las atiende con otro patrón (archivo)
    assert not (solo_puente - SOLO_PUENTE_CONOCIDAS), f"rutas solo en el puente: {sorted(solo_puente - SOLO_PUENTE_CONOCIDAS)}"
    assert not (solo_api - SOLO_API_CONOCIDAS), f"rutas solo en la API: {sorted(solo_api - SOLO_API_CONOCIDAS)}"


# ------------------------------------------------------------------------------------------------------------ 2. mismas respuestas por ambos caminos
def _xlsx_invalido() -> bytes:
    wb = openpyxl.Workbook()
    wb.active.append(["a", "b"])
    b = io.BytesIO()
    wb.save(b)
    return b.getvalue()


def _por_puente(bridge, method, path, body=None, up=None):
    return json.loads(bridge.handle(method, path, json.dumps(body) if body is not None else "", str(up) if up else "", up.name if up else ""))


def test_las_rutas_de_lectura_responden_con_las_mismas_claves_por_la_api_y_por_el_puente(entorno):
    appmod, bridge, _, tmp = entorno
    c = TestClient(appmod.app, raise_server_exceptions=False)
    rid_api = c.post("/api/runs", json={"unit": "aetops", "periodicity": "mensual", "year": 2026, "index": 9}).json()["id"]
    rid_br = _por_puente(bridge, "POST", "/api/runs", {"unit": "aetops", "periodicity": "mensual", "year": 2026, "index": 9})["json"]["id"]
    c.post(f"/api/runs/{rid_api}/file", files={"file": ("l.xlsx", EJEMPLO.read_bytes())})
    _por_puente(bridge, "POST", f"/api/runs/{rid_br}/file", up=EJEMPLO)
    for ruta in ("/api/runs/{}", "/api/runs/{}/plan", "/api/runs/{}/analysis"):
        a = c.get(ruta.format(rid_api))
        b = _por_puente(bridge, "GET", ruta.format(rid_br))
        assert a.status_code == b["status"] == 200, ruta
        assert set(a.json()) == set(b["json"]), (ruta, set(a.json()) ^ set(b["json"]))
    for ruta in ("/api/escenarios-reporte", "/api/templates", "/api/info"):
        a, b = c.get(ruta), _por_puente(bridge, "GET", ruta)
        assert a.status_code == b["status"] == 200 and set(a.json() if isinstance(a.json(), dict) else {}) == set(b["json"] if isinstance(b["json"], dict) else {}), ruta


@pytest.mark.parametrize("metodo,ruta,cuerpo,estado", [
    ("GET", "/api/runs/{rid}/preview", None, 404), ("GET", "/api/runs/{rid}/result", None, 404), ("POST", "/api/runs/{rid}/generate", {}, 400),
    ("PUT", "/api/runs/{rid}/plan", {"escenario_id": "no-existe"}, 409), ("DELETE", "/api/escenarios-reporte/no-existe", None, 404),
    ("GET", "/api/runs/{rid}/files/qa_report.json", None, 404),
])
def test_los_errores_tienen_el_mismo_codigo_por_la_api_y_por_el_puente(entorno, metodo, ruta, cuerpo, estado):
    appmod, bridge, _, _ = entorno
    c = TestClient(appmod.app, raise_server_exceptions=False)
    rid_api = c.post("/api/runs", json={"unit": "aetops", "periodicity": "mensual", "year": 2026, "index": 9}).json()["id"]
    rid_br = _por_puente(bridge, "POST", "/api/runs", {"unit": "aetops", "periodicity": "mensual", "year": 2026, "index": 9})["json"]["id"]
    a = c.request(metodo, ruta.format(rid=rid_api), json=cuerpo) if cuerpo is not None else c.request(metodo, ruta.format(rid=rid_api))
    b = _por_puente(bridge, metodo, ruta.format(rid=rid_br), cuerpo)
    assert a.status_code == b["status"] == estado, (ruta, a.status_code, b["status"])
    assert a.json().get("error") and b.get("error")                                      # y ambos explican el problema


# ------------------------------------------------------------------------------------------------------------ 3. artefacto publicado
def _construir_app_zip(destino: Path) -> Path:
    """Construye app.zip con la MISMA función que usa tools/build_site.py (sin descargar wheels)."""
    from tools import build_site as bs
    z_path = destino / "app.zip"
    with zipfile.ZipFile(z_path, "w", zipfile.ZIP_DEFLATED) as z:
        n = bs.add_tree(z, "backend/app", ROOT / "backend" / "app")
        assert n > 50
    return z_path


def test_app_zip_contiene_el_motor_y_el_bloque_integral_y_nada_de_pruebas_ni_corridas(tmp_path):
    z = zipfile.ZipFile(_construir_app_zip(tmp_path))
    nombres = z.namelist()
    for requerido in ("backend/app/build.py", "backend/app/web/bridge.py", "backend/app/web/plan_routes.py", "backend/app/web/plan_service.py", "backend/app/plan/flujo.py",
                      "backend/app/plan/previsualizacion.py", "backend/app/config/escenarios_reporte.json", "backend/app/version.py"):
        assert requerido in nombres, requerido
    assert not [n for n in nombres if n.startswith(("tests/", "runs/", "historial/", "templates/", "data/")) or "__pycache__" in n or n.endswith((".pyc", ".sqlite", ".pptx", ".xlsx"))]
    assert z.testzip() is None


def test_app_zip_no_incluye_fastapi_que_no_existe_en_el_navegador(tmp_path):
    """`app.py`/`plan_api.py` importan FastAPI; el puente (lo único que corre en Pyodide) no debe importarlo."""
    z = zipfile.ZipFile(_construir_app_zip(tmp_path))
    for n in ("backend/app/web/bridge.py", "backend/app/web/plan_routes.py", "backend/app/web/plan_service.py", "backend/app/web/service.py"):
        assert not re.search(r"^\s*(from|import)\s+fastapi", z.read(n).decode("utf-8"), re.M), n


def test_la_construccion_de_app_zip_es_determinista_en_contenido(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    a, b = zipfile.ZipFile(_construir_app_zip(tmp_path / "a")), zipfile.ZipFile(_construir_app_zip(tmp_path / "b"))
    assert a.namelist() == b.namelist()
    assert {n: hashlib.sha256(a.read(n)).hexdigest() for n in a.namelist()} == {n: hashlib.sha256(b.read(n)).hexdigest() for n in b.namelist()}


# ------------------------------------------------------------------------------------------------------------ 4. dependencias
def test_las_dependencias_que_importa_el_motor_estan_declaradas():
    declaradas = {re.split(r"[=<>~!\[; ]", ln.strip(), maxsplit=1)[0].lower().replace("_", "-") for ln in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
                  if ln.strip() and not ln.startswith("#")}
    importadas = set()
    for p in (ROOT / "backend" / "app").rglob("*.py"):
        if p.parts[-2] == "web" and p.name in ("app.py", "plan_api.py"):
            continue                                                            # solo del servidor de desarrollo
        for m in re.finditer(r"^\s*(?:from|import)\s+([A-Za-z_][\w]*)", p.read_text(encoding="utf-8"), re.M):
            importadas.add(m.group(1))
    externas = {"pptx": "python-pptx", "openpyxl": "openpyxl", "xlsxwriter": "xlsxwriter", "lxml": "lxml", "yaml": "pyyaml", "PIL": "pillow", "et_xmlfile": "et-xmlfile"}
    for modulo, paquete in externas.items():
        if modulo in importadas:
            assert paquete in declaradas, f"{modulo} se importa pero «{paquete}» no está en requirements.txt ({sorted(declaradas)})"
