"""Fase 7 · validación de entradas y manejo de errores por la API (FastAPI). Corre en CI: no necesita plantillas ni navegador.

Regla que se comprueba: ninguna entrada inválida produce un error 500 ni deja la corrida en un estado incoherente; cada rechazo trae un mensaje comprensible y la corrida
anterior sigue utilizable. (Las entradas válidas de extremo a extremo las cubren las pruebas con plantillas reales, solo locales.)"""
import importlib
import io
import json
from pathlib import Path

import openpyxl
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
EJEMPLO = ROOT / "data" / "ejemplos" / "AETOPS_crudo_ejemplo.xlsx"


@pytest.fixture()
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("REPORT_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("REPORT_HISTORY_DB", str(tmp_path / "h" / "h.sqlite"))
    monkeypatch.setenv("REPORT_TEMPLATES_DIR", str(tmp_path / "tpl"))
    (tmp_path / "h").mkdir()
    from backend.app.web import app as appmod, plan_api, plan_service, service
    for m in (service, plan_service, plan_api, appmod):
        importlib.reload(m)
    return TestClient(appmod.app, raise_server_exceptions=False), tmp_path


def nueva(c, unit="aetops", per="mensual", year=2026, index=9):
    r = c.post("/api/runs", json={"unit": unit, "periodicity": per, "year": year, "index": index})
    return r


def subir(c, rid, datos: bytes, nombre="libro.xlsx"):
    return c.post(f"/api/runs/{rid}/file", files={"file": (nombre, datos)})


def xlsx(hojas: dict) -> bytes:
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for nombre, filas in hojas.items():
        ws = wb.create_sheet(nombre)
        for f in filas:
            ws.append(f)
    b = io.BytesIO()
    wb.save(b)
    return b.getvalue()


def sin_500(r):
    assert r.status_code < 500, (r.status_code, r.text[:300])
    return r


# ------------------------------------------------------------------------------------------------------------------- creación de corridas
@pytest.mark.parametrize("cuerpo", [
    {"unit": "otra", "periodicity": "mensual", "year": 2026, "index": 9},
    {"unit": "aetops", "periodicity": "semanal", "year": 2026, "index": 9},
    {"unit": "aetops", "periodicity": "mensual", "year": 1900, "index": 9},
    {"unit": "aetops", "periodicity": "mensual", "year": 2026, "index": 13},
    {"unit": "aetops", "periodicity": "mensual", "year": 2026, "index": 0},
    {"unit": "aetops", "periodicity": "trimestral", "year": 2026, "index": 5},
    {"unit": "aetops", "periodicity": "mensual", "year": "dos mil", "index": 9},
    {"unit": "aetops", "periodicity": "mensual", "year": 2026},
    {},
])
def test_una_corrida_con_parametros_invalidos_se_rechaza_sin_500(api, cuerpo):
    c, _ = api
    r = sin_500(c.post("/api/runs", json=cuerpo))
    assert r.status_code in (400, 422)


def test_un_cuerpo_que_no_es_json_se_rechaza_sin_500(api):
    c, _ = api
    r = sin_500(c.post("/api/runs", content=b"esto no es json", headers={"content-type": "application/json"}))
    assert r.status_code == 422


# ------------------------------------------------------------------------------------------------------------------- libros de entrada
@pytest.mark.parametrize("nombre,datos", [
    ("vacio.xlsx", b""),
    ("texto.xlsx", b"esto no es un libro de Excel"),
    ("truncado.xlsx", EJEMPLO.read_bytes()[:2000]),
    ("imagen.xlsx", b"\x89PNG\r\n\x1a\n" + b"\x00" * 200),
    ("sin_hojas_utiles.xlsx", xlsx({"Hoja1": [["a", "b"], [1, 2]]})),
    ("hoja_vacia.xlsx", xlsx({"ventas": []})),
])
def test_un_libro_invalido_se_rechaza_sin_500_y_la_corrida_sigue_siendo_utilizable(api, nombre, datos):
    c, _ = api
    rid = nueva(c).json()["id"]
    r = sin_500(subir(c, rid, datos, nombre))
    if r.status_code == 200:                                          # si lo acepta, la validación debe señalar que no sirve para generar
        a = sin_500(c.get(f"/api/runs/{rid}/analysis"))
        assert a.status_code != 200 or a.json().get("can_generate") is False, a.text[:300]
    else:
        assert r.status_code in (400, 413, 415, 422) and r.json().get("error"), r.text[:300]
    assert c.get(f"/api/runs/{rid}").status_code == 200              # la corrida no quedó rota
    assert sin_500(c.post(f"/api/runs/{rid}/generate")).status_code in (400, 404, 409)    # y no se genera nada con una entrada inválida


def test_un_libro_demasiado_grande_se_rechaza(api, monkeypatch):
    c, _ = api
    from backend.app.web import service
    monkeypatch.setattr(service, "MAX_UPLOAD", 1024)
    rid = nueva(c).json()["id"]
    r = sin_500(subir(c, rid, b"x" * 5000))
    assert r.status_code in (400, 413) and r.json().get("error")


def test_un_nombre_de_archivo_con_ruta_no_escribe_fuera_de_la_corrida(api):
    c, tmp = api
    rid = nueva(c).json()["id"]
    sin_500(subir(c, rid, EJEMPLO.read_bytes(), "../../../../fuera.xlsx"))
    assert not list(tmp.rglob("fuera.xlsx")) and not (tmp.parent / "fuera.xlsx").exists()


def test_un_libro_valido_reemplaza_a_uno_invalido_y_deja_la_corrida_lista(api):
    c, _ = api
    rid = nueva(c).json()["id"]
    sin_500(subir(c, rid, b"basura", "malo.xlsx"))
    r = subir(c, rid, EJEMPLO.read_bytes(), "bueno.xlsx")
    assert r.status_code == 200
    a = c.get(f"/api/runs/{rid}/analysis")
    assert a.status_code == 200 and a.json()["can_generate"] in (True, False) and a.json().get("kpis")


# ------------------------------------------------------------------------------------------------------------------- metas, contexto y ediciones
@pytest.mark.parametrize("cuerpo", [{"total": "-5"}, {"total": "abc"}, {"total": ""}, {"inexistente": "10"}, {"total": "1e999"}, {"total": None}, [], "texto"])
def test_metas_invalidas_no_producen_500(api, cuerpo):
    c, _ = api
    rid = nueva(c).json()["id"]
    r = sin_500(c.put(f"/api/runs/{rid}/targets", json=cuerpo))
    assert r.status_code in (200, 400, 422)
    assert c.get(f"/api/runs/{rid}").status_code == 200


def test_el_contexto_y_las_ediciones_invalidos_se_rechazan_sin_500(api):
    c, _ = api
    rid = nueva(c).json()["id"]
    for cuerpo in ({"items": "no es lista"}, {"items": [1, 2]}, {"items": ["x"] * 500}, {"otra": 1}, [], None):
        sin_500(c.put(f"/api/runs/{rid}/context", json=cuerpo))
    for cuerpo in ({"slide": "inexistente", "text": "x"}, {"edits": "no"}, {"edits": {"clave_inexistente": ["x"]}}, [], None):
        sin_500(c.put(f"/api/runs/{rid}/edits", json=cuerpo))
    assert c.get(f"/api/runs/{rid}").status_code == 200


# ------------------------------------------------------------------------------------------------------------------- identificadores y rutas
@pytest.mark.parametrize("rid", ["", "x", "0" * 31, "0" * 33, "G" * 32, "../../etc/passwd", "%2e%2e", "a" * 300])
def test_un_id_de_corrida_invalido_da_404_o_400_nunca_500(api, rid):
    c, _ = api
    for ruta in (f"/api/runs/{rid}", f"/api/runs/{rid}/result", f"/api/runs/{rid}/plan", f"/api/runs/{rid}/preview", f"/api/runs/{rid}/analysis"):
        r = sin_500(c.get(ruta))
        assert r.status_code in (400, 404, 405), (ruta, r.status_code)


@pytest.mark.parametrize("nombre", ["..%2f..%2frun.json", "../run.json", "..\\run.json", "%00", "run.json", "input.xlsx", "qa_report.json%00.pptx", "a" * 300 + ".pptx"])
def test_la_descarga_no_sirve_archivos_fuera_de_la_lista_permitida(api, nombre):
    c, _ = api
    rid = nueva(c).json()["id"]
    r = sin_500(c.get(f"/api/runs/{rid}/files/{nombre}"))
    assert r.status_code in (400, 404), (nombre, r.status_code)
    assert b"run.json" not in r.content or r.status_code != 200


def test_las_rutas_inexistentes_responden_404_con_cuerpo_comprensible(api):
    c, _ = api
    r = sin_500(c.get("/api/no-existe"))
    assert r.status_code == 404
    assert sin_500(c.post("/api/runs/xyz/no-existe")).status_code in (404, 405)


def test_generar_sin_libro_ni_plantilla_da_un_error_comprensible(api):
    c, _ = api
    rid = nueva(c).json()["id"]
    r = sin_500(c.post(f"/api/runs/{rid}/generate"))
    assert r.status_code in (400, 404, 409) and r.json().get("error")
    subir(c, rid, EJEMPLO.read_bytes())
    r = sin_500(c.post(f"/api/runs/{rid}/generate"))
    assert r.status_code in (400, 404, 409) and r.json().get("error")          # sin plantilla instalada


def test_el_estado_de_la_corrida_no_se_corrompe_tras_una_secuencia_de_entradas_invalidas(api):
    c, tmp = api
    rid = nueva(c).json()["id"]
    for _ in range(3):
        sin_500(subir(c, rid, b"basura"))
        sin_500(c.put(f"/api/runs/{rid}/targets", json={"total": "abc"}))
    estado = json.loads((tmp / "runs" / rid / "run.json").read_text(encoding="utf-8"))
    assert estado["id"] == rid and estado["unit"] == "aetops"


# ------------------------------------------------------------------------------------------------------------------- el puente del navegador responde igual
def test_el_puente_traduce_un_libro_sin_el_formato_esperado_a_400_con_mensaje(tmp_path, monkeypatch):
    monkeypatch.setenv("REPORT_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("REPORT_HISTORY_DB", str(tmp_path / "h" / "h.sqlite"))
    monkeypatch.setenv("REPORT_TEMPLATES_DIR", str(tmp_path / "tpl"))
    (tmp_path / "h").mkdir()
    from backend.app.web import bridge, service
    importlib.reload(service)
    importlib.reload(bridge)
    libro = tmp_path / "otro.xlsx"
    libro.write_bytes(xlsx({"Hoja1": [["a", "b"], [1, 2]]}))

    def call(method, path, body=None, up=None):
        return json.loads(bridge.handle(method, path, json.dumps(body) if body is not None else "", str(up) if up else "", up.name if up else ""))

    rid = call("POST", "/api/runs", {"unit": "aetops", "periodicity": "mensual", "year": 2026, "index": 9})["json"]["id"]
    assert call("POST", f"/api/runs/{rid}/file", up=libro)["status"] == 200
    for metodo, ruta in (("GET", f"/api/runs/{rid}/analysis"), ("POST", f"/api/runs/{rid}/generate"), ("GET", f"/api/runs/{rid}/narrative")):
        r = call(metodo, ruta)
        assert r["status"] == 400 and "formato esperado" in r["error"] and "ImportRejected" not in r["error"], (ruta, r)     # sin nombres de clase internos


def test_sin_plantilla_instalada_generar_responde_409_y_dice_cual_falta(api):
    c, _ = api
    rid = nueva(c).json()["id"]
    subir(c, rid, EJEMPLO.read_bytes())
    r = c.post(f"/api/runs/{rid}/generate", json={})
    assert r.status_code == 409 and "plantilla" in r.json()["error"].lower()
