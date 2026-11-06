"""Fase 5 · Anexo de calidad de datos (`backend/app/calidad.py`; RQ-19): 15 dimensiones, evidencia por hallazgo, origen de los datos y servicio.

Usa los libros de EJEMPLO (sintéticos) y variantes con defectos inyectados con openpyxl. Ninguna cifra es de producción.
"""
from __future__ import annotations

import copy
import json
import re
import shutil
from pathlib import Path

import openpyxl
import pytest

from backend.app import calidad as C
from backend.app import escenarios as E
from backend.app.models import Period
from backend.app.pipeline import run_aetops_raw, run_glp1_raw

ROOT = Path(__file__).resolve().parents[2]
EJ = ROOT / "data" / "ejemplos"
PG, PA = Period("GLP1", "mensual", 2026, 9), Period("AETOPS", "mensual", 2026, 9)


def anexo(libro: Path, unidad="glp1", nombre=None, crudo=True):
    per = PG if unidad == "glp1" else PA
    res = (run_glp1_raw if unidad == "glp1" else run_aetops_raw)(libro, per)
    ctx = E.contexto_cacheado(libro, per) if crudo else None
    esc = E.construir(res, unidad, per, ctx if unidad == "glp1" else None)
    return C.construir(res, unidad, per, ctx, {"nombre": nombre or libro.name}, esc), res, ctx


def ids(a):
    return {h["id"] for d in a["dimensiones"] for h in d["hallazgos"]}


def hall(a, id_):
    return next(h for d in a["dimensiones"] for h in d["hallazgos"] if h["id"] == id_)


def variante(tmp_path, fn, src="GLP1_crudo_ejemplo.xlsx", nombre="v.xlsx"):
    p = tmp_path / nombre
    shutil.copy(EJ / src, p)
    wb = openpyxl.load_workbook(p)
    fn(wb)
    wb.save(p)
    return p


def filas_del_periodo(ws, n, anio=2026, mes=9):
    """Números de fila de `ventas` cuya fecha cae en el periodo del reporte (sep-2026)."""
    c = col(ws, "fecha_pedido")
    out = []
    for fila in range(2, ws.max_row + 1):
        v = ws.cell(fila, c).value
        if v is not None and (v.year, v.month) == (anio, mes) if hasattr(v, "year") else str(v)[:7] == f"{anio}-{mes:02d}":
            out.append(fila)
        if len(out) == n:
            return out
    raise AssertionError("el libro de ejemplo no tiene suficientes filas del periodo")


def col(ws, nombre):
    return [str(c.value).strip().lower() if c.value is not None else "" for c in ws[1]].index(nombre) + 1


@pytest.fixture(scope="module")
def glp1():
    return anexo(EJ / "GLP1_crudo_ejemplo.xlsx")


@pytest.fixture(scope="module")
def aet():
    return anexo(EJ / "AETOPS_crudo_ejemplo.xlsx", "aetops")


# --------------------------------------------------------------------------------------------- forma
def test_quince_dimensiones_en_orden_y_json(glp1, aet):
    esperado = [d[0] for d in C.DIMENSIONES]
    assert len(esperado) == 15
    for a, _r, _c in (glp1, aet):
        assert [d["id"] for d in a["dimensiones"]] == esperado and a["esquema"] == C.ESQUEMA and a["resumen"]["dimensiones"] == 15
        json.dumps(a)


def test_todo_hallazgo_tiene_evidencia_impacto_severidad_y_naturaleza(glp1, aet):
    for a, _r, _c in (glp1, aet):
        for d in a["dimensiones"]:
            for h in d["hallazgos"]:
                assert h["id"] and h["descripcion"] and h["impacto"] and isinstance(h["evidencia"], dict)
                assert h["severidad"] in C.SEVERIDADES and h["naturaleza"] in ("observado", "faltante", "inferido", "no_verificable")


def test_las_seis_categorias_de_datos_estan_definidas(glp1):
    assert set(glp1[0]["origen_datos"]["categorias"]) == {"real", "sintetico", "ejemplo", "faltante", "inferido", "no_verificable"}


# --------------------------------------------------------------------------------------------- origen: nunca «real»
@pytest.mark.parametrize("nombre,esperado", [("GLP1_crudo_ejemplo.xlsx", "ejemplo_o_sintetico_inferido"), ("datos_sinteticos.xlsx", "ejemplo_o_sintetico_inferido"),
                                              ("demo.xlsx", "ejemplo_o_sintetico_inferido"), ("ventas_octubre.xlsx", "no_declarado"), (None, "no_declarado"), ("", "no_declarado")])
def test_el_origen_solo_se_infiere_ejemplo_y_nunca_se_afirma_real(nombre, esperado):
    o = C.clasificar_origen(nombre)
    assert o["clasificacion"] == esperado and o["clasificacion"] != "real"
    assert "real" not in o["clasificacion"].replace("no_declarado", "")
    if esperado == "no_declarado":
        assert "no se puede afirmar" in o["detalle"] and "No presentar" in o["advertencia"]
    else:
        assert "inferido; no verificado" in o["detalle"] and "no son resultados de producción" in o["advertencia"]


def test_el_anexo_declara_la_etiqueta_de_que_informa_y_no_corrige(glp1):
    assert "no corrige ni excluye datos" in glp1[0]["etiqueta"] and any("no valida" in x.lower() for x in glp1[0]["limitaciones"])


# --------------------------------------------------------------------------------------------- libros limpios
def test_libro_de_ejemplo_limpio_no_tiene_hallazgos_altos(glp1, aet):
    assert glp1[0]["resumen"]["severidades"]["alta"] == 0 and aet[0]["resumen"]["severidades"]["alta"] == 0
    assert glp1[0]["resumen"]["estado_global"] == "con_hallazgos" and glp1[0]["resumen"]["dimensiones_evaluadas"] == 15      # sí hay medias: no verificables y supuestos


def test_aetops_no_menciona_ga4_ni_e2(aet):
    t = json.dumps(aet[0], ensure_ascii=False)
    assert "NVE-GA4" not in ids(aet[0]) and "SUP-E2" not in ids(aet[0]) and "UNI-CARRITOS" not in ids(aet[0])
    assert "E2" not in " ".join(i for i in ids(aet[0]) if i.startswith("SUP"))


def test_no_verificables_y_supuestos_estan_listados(glp1):
    a = glp1[0]
    assert {"NVE-ADD-TO-CART", "NVE-GA4", "NVE-ABANDONADOS", "NVE-MONEDA"} <= ids(a) and {"SUP-E1", "SUP-E2", "SUP-REGLAS"} <= ids(a)
    assert all(h["naturaleza"] == "no_verificable" for d in a["dimensiones"] if d["id"] in ("no_verificables", "supuestos") for h in d["hallazgos"])
    assert hall(a, "TEM-NEGADOS-SIN-FECHA")["naturaleza"] == "no_verificable"


def test_consistencia_entre_fuentes_nombra_ambas_y_no_las_combina(glp1):
    h = hall(glp1[0], "CON-VENTAS-GA4")
    assert "2356" in h["descripcion"] and "2643" in h["descripcion"] and "NO VALIDADA" in h["impacto"] and "no se suman" in h["impacto"]


def test_impacto_por_indicador_cita_los_hallazgos_que_lo_afectan(glp1):
    imp = {h["evidencia"]["indicador"]: h["evidencia"]["hallazgos"] for h in next(d for d in glp1[0]["dimensiones"] if d["id"] == "impacto")["hallazgos"]}
    assert "IND-01" in imp and "NVE-ADD-TO-CART" in imp["IND-01"] and "E1" in imp and "SUP-E1" in imp["E1"]


def test_trazabilidad_del_archivo_y_versiones(tmp_path):
    a, _r, _c = anexo(EJ / "GLP1_crudo_ejemplo.xlsx")
    a2 = C.construir(_r, "glp1", PG, _c, {"nombre": "x.xlsx", "sha256": "a" * 64, "bytes": 10}, None)
    h = hall(a2, "TRA-ARCHIVO")
    assert h["evidencia"]["sha256"] == "a" * 64 and "aaaaaaaaaaaaaaaa" in h["descripcion"] and "aplicación" in hall(a2, "TRA-VERSIONES")["descripcion"]


# --------------------------------------------------------------------------------------------- defectos inyectados
def test_defectos_de_los_libros_con_defectos_coinciden_con_los_del_motor():
    for u, f in (("glp1", "GLP1_crudo_con_defectos.xlsx"), ("aetops", "AETOPS_crudo_con_defectos.xlsx")):
        a, res, _c = anexo(EJ / f, u)
        assert a["resumen"]["severidades"]["alta"] >= 5 and {"TIP-FECHA", "SEM-SKU-SIN-CATALOGO", "INT-PEDIDOS-EXCLUIDOS"} <= ids(a)
        motor = {fd.id for fd in res.findings if fd.severity == "block"}
        assert motor and all(f"MOT-{m}" in ids(a) for m in motor)                    # lo que bloquea el motor consta en el anexo
        assert hall(a, "TIP-FECHA")["evidencia"]["n_filas"] == 1                       # y el conteo propio coincide con el del motor (1 fila)


def test_monto_negativo_y_no_numerico_con_filas_de_ejemplo(tmp_path):
    marcas = []

    def f(wb):
        ws = wb["ventas"]
        c = col(ws, "monto_venta")
        f1, f2 = filas_del_periodo(ws, 2)
        ws.cell(f1, c).value = -100
        ws.cell(f2, c).value = "mucho"
        marcas.extend([f1, f2])
    a, _r, _c = anexo(variante(tmp_path, f, "AETOPS_crudo_ejemplo.xlsx"), "aetops")
    neg, tip = hall(a, "SEM-MONTO-NEG"), hall(a, "TIP-MONTO_VENTA")
    assert neg["evidencia"]["filas_ejemplo"] == [marcas[0]] and tip["evidencia"]["filas_ejemplo"] == [marcas[1]] and neg["severidad"] == tip["severidad"] == "alta"


def test_celdas_vacias_en_columna_requerida_y_opcional(tmp_path):
    def f(wb):
        ws = wb["ventas"]
        f1, f2, f3, f4 = filas_del_periodo(ws, 4)
        for fila in (f1, f2, f3):
            ws.cell(fila, col(ws, "id_paciente")).value = None
        ws.cell(f4, col(ws, "forma_pago")).value = None
    a, _r, _c = anexo(variante(tmp_path, f))
    assert hall(a, "VAC-ID_PACIENTE")["severidad"] == "alta" and hall(a, "VAC-ID_PACIENTE")["evidencia"]["n_filas"] == 3
    assert hall(a, "VAC-FORMA_PAGO")["severidad"] == "baja" and hall(a, "VAC-FORMA_PAGO")["naturaleza"] == "faltante"


def test_lineas_duplicadas_exactas(tmp_path):
    def f(wb):
        ws = wb["ventas"]
        fila = [c.value for c in ws[filas_del_periodo(ws, 1)[0]]]
        ws.append(fila)
        ws.append(fila)
    a, _r, _c = anexo(variante(tmp_path, f))
    h = hall(a, "DUP-LINEAS")
    assert h["severidad"] == "media" and "2 línea(s) repetida(s)" in h["descripcion"] and h["evidencia"]["n_filas"] == 3


def test_pedido_con_dos_pacientes(tmp_path):
    def f(wb):
        ws = wb["ventas"]
        a, b = filas_del_periodo(ws, 2)
        ws.cell(b, col(ws, "id_pedido")).value = ws.cell(a, col(ws, "id_pedido")).value
        ws.cell(b, col(ws, "id_paciente")).value = "OTRO-PACIENTE"
    a, _r, _c = anexo(variante(tmp_path, f))
    assert "INT-PEDIDO-MULTIPACIENTE" in ids(a)


def test_periodo_sin_ventas_es_un_hallazgo_alto():
    res = run_glp1_raw(EJ / "GLP1_crudo_ejemplo.xlsx", Period("GLP1", "mensual", 2024, 1))
    ctx = E.contexto_cacheado(EJ / "GLP1_crudo_ejemplo.xlsx", Period("GLP1", "mensual", 2024, 1))
    a = C.construir(res, "glp1", Period("GLP1", "mensual", 2024, 1), ctx, {"nombre": "x"}, None)
    assert hall(a, "TEM-PERIODO-VACIO")["severidad"] == "alta"


def test_trafico_con_mes_faltante_no_se_completa(tmp_path):
    def f(wb):
        ws = wb["trafico"]
        c = col(ws, "mes")
        for fila in range(2, ws.max_row + 1):
            v = ws.cell(fila, c).value
            if v is not None and str(v)[:7] == "2026-09":
                ws.cell(fila, c).value = "2025-01-01"
    a, _r, _c = anexo(variante(tmp_path, f))
    assert hall(a, "TEM-TRAFICO-MESES")["naturaleza"] == "faltante" and "IND-01" in hall(a, "TEM-TRAFICO-MESES")["indicadores"]


@pytest.mark.parametrize("hoja,id_", [("trafico", "EST-SIN-TRAFICO"), ("negados", "EST-SIN-NEGADOS")])
def test_hoja_opcional_ausente_se_declara(tmp_path, hoja, id_):
    a, _r, _c = anexo(variante(tmp_path, lambda wb: wb.__delitem__(hoja)))
    assert id_ in ids(a) and hall(a, id_)["naturaleza"] == "faltante"


def test_columnas_en_otro_orden_y_columnas_extra_no_rompen_el_anexo(tmp_path):
    def f(wb):
        ws = wb["ventas"]
        ws.insert_cols(1)                                  # columna adicional al inicio: desplaza todo
        ws.cell(1, 1).value = "columna_extra"
        ws.cell(2, 1).value = "x"
    a, _r, _c = anexo(variante(tmp_path, f))
    assert "ventas" in hall(a, "EST-HOJAS")["evidencia"]["hojas"] and a["resumen"]["severidades"]["alta"] == 0


def test_libro_en_formato_antiguo_es_no_evaluable_y_lo_declara():
    from backend.app.pipeline import run_glp1
    res = run_glp1(ROOT / "data" / "GLP1_sintetico_limpio.xlsx", "mensual", PG)
    a = C.construir(res, "glp1", PG, None, {"nombre": "antiguo.xlsx"}, None)
    estados = {d["id"]: d["estado"] for d in a["dimensiones"]}
    assert estados["tipos"] == estados["duplicados"] == estados["vacios"] == "no_evaluable" and "EST-FORMATO-ANTIGUO" in ids(a)
    assert a["resumen"]["dimensiones_evaluadas"] < 15 and a["origen_datos"]["clasificacion"] == "no_declarado"


# --------------------------------------------------------------------------------------------- no muta, determinismo, seguridad
def test_no_modifica_el_contexto_y_es_determinista(glp1):
    a, res, ctx = glp1
    antes = (len(ctx.lineas), copy.deepcopy(ctx.trafico_sitio), len(ctx.catalogo))
    esc = E.construir(res, "glp1", PG, ctx)
    b = C.construir(res, "glp1", PG, ctx, {"nombre": "GLP1_crudo_ejemplo.xlsx"}, esc)
    assert (len(ctx.lineas), ctx.trafico_sitio, len(ctx.catalogo)) == antes
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_el_modulo_solo_lee_sin_red_escritura_procesos_ni_ia():
    src = (ROOT / "backend/app/calidad.py").read_text(encoding="utf-8")
    prohibido = re.compile(r"\b(requests|httpx|urllib|socket|http\.client|subprocess|os\.system)\b|\.write_text|\.write_bytes|open\([^)]*['\"][wa]", re.I)
    assert prohibido.search(src) is None and not re.search(r"cohere|ia_log|verify_rewrite|web\.service", src, re.I)


def test_ninguna_moneda_inventada(glp1):
    t = json.dumps(glp1[0], ensure_ascii=False)
    assert "MXN" not in t and "no está declarada en el libro" in t


# --------------------------------------------------------------------------------------------- servicio
@pytest.fixture()
def servicio(tmp_path, monkeypatch):
    import importlib
    monkeypatch.setenv("REPORT_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("REPORT_HISTORY_DB", str(tmp_path / "h.sqlite"))
    from backend.app.web import service
    importlib.reload(service)
    return service


def _analizar(S, unidad, libro: Path):
    rid = S.create_run(unidad, "mensual", 2026, 9)["id"]
    S.store_file(rid, libro.name, libro.read_bytes())
    return S.analyze(rid), rid


def test_el_servicio_expone_el_anexo_con_sha256_del_archivo(servicio):
    import hashlib
    libro = EJ / "GLP1_crudo_ejemplo.xlsx"
    a, _ = _analizar(servicio, "glp1", libro)
    x = a["anexo_calidad"]
    assert not x.get("no_disponible") and x["origen_datos"]["clasificacion"] == "ejemplo_o_sintetico_inferido"
    assert hall(x, "TRA-ARCHIVO")["evidencia"]["sha256"] == hashlib.sha256(libro.read_bytes()).hexdigest()
    json.dumps(a)
    assert {"findings", "kpis", "can_generate", "escenarios_indicador"} <= set(a)        # el análisis existente no cambia de forma


def test_el_servicio_funciona_con_libro_aetops_y_con_formato_antiguo(servicio):
    a, _ = _analizar(servicio, "aetops", EJ / "AETOPS_crudo_ejemplo.xlsx")
    assert a["anexo_calidad"]["resumen"]["dimensiones_evaluadas"] == 15
    from tests.fixtures import build_base
    b, _ = _analizar(servicio, "aetops", build_base(Path(servicio.RUNS_DIR).parent / "base.xlsx"))
    assert "EST-FORMATO-ANTIGUO" in {h["id"] for d in b["anexo_calidad"]["dimensiones"] for h in d["hallazgos"]}


def test_si_el_anexo_falla_el_analisis_sigue_y_no_filtra_la_traza(servicio, monkeypatch):
    monkeypatch.setattr(C, "construir", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("secreto-interno")))
    a, _ = _analizar(servicio, "glp1", EJ / "GLP1_crudo_ejemplo.xlsx")
    x = a["anexo_calidad"]
    assert "No se pudo construir el anexo" in x["no_disponible"] and "secreto-interno" not in json.dumps(x) and a["findings"] is not None


def test_el_archivo_del_anexo_se_puede_descargar_solo_si_existe(servicio, tmp_path):
    rid = servicio.create_run("glp1", "mensual", 2026, 9)["id"]
    out = servicio._dir(rid) / "out"
    out.mkdir(parents=True)
    (out / "qa_report.json").write_text('{"passed": true, "issues": []}', encoding="utf-8")
    with pytest.raises(servicio.ServiceError):
        servicio.file_path(rid, "anexo_calidad.json")                                     # aún no existe
    (out / "anexo_calidad.json").write_text("{}", encoding="utf-8")
    assert servicio.file_path(rid, "anexo_calidad.json").name == "anexo_calidad.json"
    with pytest.raises(servicio.ServiceError):
        servicio.file_path(rid, "../anexo_calidad.json")                                  # sin salirse de la carpeta


def test_escribir_anexo_no_deja_un_archivo_si_no_pudo_construirse(servicio, monkeypatch, tmp_path):
    rid = servicio.create_run("glp1", "mensual", 2026, 9)["id"]
    servicio.store_file(rid, "GLP1_crudo_ejemplo.xlsx", (EJ / "GLP1_crudo_ejemplo.xlsx").read_bytes())
    st = servicio._load(rid)
    res = servicio._run_engine(rid, st)
    out = tmp_path / "out"
    out.mkdir()
    servicio._escribir_anexo(C.construir(res, "glp1", PG, None, {"nombre": "x"}, None), out)
    assert json.loads((out / "anexo_calidad.json").read_text(encoding="utf-8"))["esquema"] == C.ESQUEMA
    out2 = tmp_path / "out2"
    out2.mkdir()
    servicio._escribir_anexo({"esquema": C.ESQUEMA, "no_disponible": "x", "dimensiones": []}, out2)
    assert not (out2 / "anexo_calidad.json").exists()
