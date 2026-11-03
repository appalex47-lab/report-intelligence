"""QA de la Fase 2B — fórmulas, unidades de negocio, calidad del motor, reproducibilidad, privacidad e IA.

Datos sintéticos inventados y machotes sintéticos de `data/ejemplos` (no son datos reales).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from decimal import Decimal
from pathlib import Path

import openpyxl
import pytest

from backend.app import config
from backend.app.models import Period
from backend.app.validator import motor, operandos
from backend.app.validator.normalizar import ErrorLectura, construir_contexto
from tests.qa_util import D, L, cod, ctx_de, fecha as F, pedidos_n, run, tr

ROOT = Path(__file__).resolve().parents[2]
EJ = ROOT / "data" / "ejemplos"
VALIDATOR = ROOT / "backend" / "app" / "validator"

# Encabezados reales de los machotes (especificación §3.0). Si un machote cambia, esta prueba lo detecta.
CABECERAS = {
    "GLP1": {"ventas": ["fecha_pedido", "id_pedido", "id_paciente", "paciente_nuevo", "sku", "canal", "estado", "region", "piezas", "monto_venta", "forma_pago", "modo_entrega", "programa_lealtad"],
             "catalogo": ["sku", "producto", "categoria"],
             "trafico": ["mes", "vista", "valor", "sku", "visitas", "usuarios", "usuarios_nuevos", "usuarios_recurrentes", "vistas_producto", "add_to_cart", "begin_checkout", "compras", "carritos_abandonados", "sesiones_rebote", "segundos_interaccion_total"],
             "negados": ["producto", "sku", "alta", "pedidos", "cantidad_negada", "monto_negado"]},
    "AETOPS": {"ventas": ["fecha_pedido", "id_pedido", "id_paciente", "paciente_nuevo", "sku", "canal", "estado", "sucursal", "piezas", "monto_venta"],
               "catalogo": ["sku", "producto", "linea", "categoria", "laboratorio"],
               "negados": ["producto", "sku", "alta", "pedidos", "cantidad_negada", "monto_negado"]},
}
LIBRO = {"GLP1": EJ / "GLP1_crudo_ejemplo.xlsx", "AETOPS": EJ / "AETOPS_crudo_ejemplo.xlsx"}
hay_machotes = pytest.mark.skipif(not all(p.exists() for p in LIBRO.values()), reason="machotes sintéticos no disponibles")


def cabeceras(path):
    wb = openpyxl.load_workbook(path, read_only=True)
    out = {ws.title: [c for c in next(ws.iter_rows(values_only=True))] for ws in wb.worksheets}
    wb.close()
    return out


# =================================================================================== T-22 · unidades y machotes reales
@hay_machotes
@pytest.mark.parametrize("unidad", ["GLP1", "AETOPS"])
def test_t22_los_encabezados_documentados_coinciden_con_los_machotes_reales(unidad):
    real = cabeceras(LIBRO[unidad])
    assert real == CABECERAS[unidad]                                       # mismas hojas, mismas columnas, mismo orden


@hay_machotes
def test_t22_aetops_no_tiene_hoja_trafico_y_el_motor_no_la_pide():
    assert "trafico" not in cabeceras(LIBRO["AETOPS"]) and "trafico" in cabeceras(LIBRO["GLP1"])
    ctx = construir_contexto(LIBRO["AETOPS"], Period("AETOPS", "mensual", 2026, 9))
    assert "trafico" not in ctx.columnas and ctx.trafico_sitio == {}
    original = operandos._trafico

    def prohibido(*a, **k):
        raise AssertionError("AETOPS no debe consultar tráfico")
    operandos._trafico = prohibido
    try:
        res = motor.ejecutar(ctx)
    finally:
        operandos._trafico = original
    assert {r.regla_id for r in res if r.estado == "not_applicable"} == {"R-CONC-COMPRAS", "R-COBERTURA-ATC"}
    assert not any(r.codigo == "fallo_interno" for r in res)
    assert {r.codigo for r in res if r.regla_id == "R-DENOM"} == {"razon_ticket"}


def test_t22_el_catalogo_de_reglas_solo_referencia_columnas_que_existen_en_los_machotes():
    cat = config.cargar("reglas")
    for r in cat["reglas"]:
        for u in r["unidades"]:
            for c in r["columnas_requeridas"]:
                assert c["columna"] in CABECERAS[u].get(c["hoja"], []), (r["id"], u, c)
        for u, dims in r.get("dimensiones_candidatas", {}).items():
            for d in dims:
                assert d["columna"] in CABECERAS[u][d["hoja"]], (r["id"], u, d)
    assert [r["id"] for r in cat["reglas"] if "AETOPS" not in r["unidades"]] == ["R-CONC-COMPRAS", "R-COBERTURA-ATC"]
    for d in config.cargar("definiciones")["definiciones"]:
        for u in d["aplicabilidad"]["unidades"]:
            fu = d["fuente"]
            for f in ([fu] if isinstance(fu, dict) else fu):
                assert f["columna"] in CABECERAS[u].get(f["hoja"], []), (d["id"], u, f)


@hay_machotes
def test_t22_los_resultados_no_se_presentan_como_operacionales():
    res = motor.ejecutar(construir_contexto(LIBRO["GLP1"], Period("GLP1", "mensual", 2026, 9)))
    assert all(r.estado_validacion == "not_validated_with_real_data" for r in res)
    assert "datos reales" in (EJ / "LEEME.md").read_text(encoding="utf-8")                                       # «No son datos reales»


# =================================================================================== fórmulas F-01 … F-12
def test_formulas_f01_f02_f03_f11_exactas_en_decimal_con_redondeo_solo_al_mostrar():
    ctx = ctx_de(pedidos_n(100), trafico=tr(add=300, compras=130))
    v, g = run(ctx, "R-COBERTURA-ATC", unidad_carritos="eventos")
    assert isinstance(v.valor, Decimal) and v.valor == D(100) / D(300) * 100            # F-01: pedidos/carritos × 100, sin redondear
    assert g.valor == D(130) / D(300) * 100                                              # F-02
    assert "33.33" in v.mensaje and str(v.valor) != "33.33" and len(str(v.valor)) > 6      # se muestra con 2 decimales; el valor guardado es exacto
    conc = run(ctx, "R-CONC-COMPRAS")[0]
    assert conc.valor == (D(130) - D(100)) / D(100) and isinstance(conc.valor, Decimal)  # F-03
    tk = next(r for r in motor.ejecutar(ctx, ids=["R-DENOM"]) if r.codigo == "razon_ticket")
    assert tk.valor == D(100) * D(100) / D(100)                                           # F-11: monto/pedidos (100 líneas de 100)


def test_formulas_f04_f05_f06_f07_con_el_ejemplo_de_la_especificacion():
    lin = [L(1, "P-001", "X1", F(5)), L(2, "P-001", "X1", F(5), "S2"), L(3, "P-001", "X1", F(5), "S3"), L(4, "P-002", "X2", F(7)), L(5, "P-002", "X2", F(7)),
           L(6, "P-003", "X1", F(9)), L(7, "P-003", "X3", F(9)), L(8, "P-004", "X4", F(28)), L(9, "P-004", "X4", F(2, 2)), L(10, "P-005", "", F(12)), L(11, "P-006", "X1", F(20))]
    g = run(ctx_de(lin), "R-REL-PAC-PED")[0].evidencia
    assert D(g["cobertura_paciente"]) == D(3) / D(5)                                     # F-04
    assert D(g["razon_recurrencia"]) == D(3) / D(2)                                      # F-05
    assert D(g["tasa_no_asignables"]) == D(1) / D(6) and g["no_asignables"] == 1         # F-06 = (|C1|+|C2|)/(|C1|+|C2|+|E|)
    assert g["pacientes_unicos"] <= 1 * g["A"]                                           # F-07 (I2) con m = 1


def test_formulas_f08_suma_total_por_combinacion_ya_cubierta_y_f09_f10_f12_no_se_modificaron():
    src = lambda p: (ROOT / p).read_text(encoding="utf-8")                                # noqa: E731
    assert "rec_amt = alta.total.v * rules.recovery_scenario" in src("backend/app/narrative/executive.py")                 # F-09 vigente
    assert "amt = aband * rules.cart_recovery_scenario * tick" in src("backend/app/narrative/glp1_exec.py")                # F-10 vigente
    assert 'funnel["cur"].get("add_to_cart", Decimal(0)) - funnel["cur"].get("compras", Decimal(0))' in src("backend/app/raw/glp1.py")   # F-12 vigente
    assert 'Decimal("0.2")' in src("backend/app/raw/glp1.py") and "TRAFICO_PURCHASE_DIFFERS" in src("backend/app/raw/glp1.py")


@hay_machotes
def test_formulas_las_cifras_del_motor_de_reglas_coinciden_con_las_del_motor_existente_glp1():
    """No hay fórmulas duplicadas que se contradigan: pedidos, monto, ticket, compras y carritos del nuevo motor = los del motor actual."""
    from backend.app.pipeline import run_glp1_raw
    per = Period("GLP1", "mensual", 2026, 9)
    viejo = run_glp1_raw(LIBRO["GLP1"], per)
    pano = viejo.blocks["panorama"].rows[0].values
    ctx = construir_contexto(LIBRO["GLP1"], per)
    assert operandos.pedidos_ventas(ctx).valor == pano["pedidos"].v
    assert operandos.monto_ventas(ctx).valor == pano["monto"].v
    tk = next(r for r in motor.ejecutar(ctx, ids=["R-DENOM"]) if r.codigo == "razon_ticket")
    assert tk.valor == pano["ticket"].v
    emb = {r.key: r.values["conteo"].v for r in viejo.funnel.rows}
    assert operandos.compras_ga4(ctx).valor == emb["compra"] and operandos.carritos_agregados(ctx).valor == emb["agregar a carrito"]
    legado = [f for f in viejo.findings if f.id == "TRAFICO_PURCHASE_DIFFERS"]
    conc = run(ctx, "R-CONC-COMPRAS")[0]
    assert (len(legado) == 1) == (conc.estado == "warning")                                  # mismo criterio que el aviso heredado


@hay_machotes
def test_formulas_las_cifras_del_motor_de_reglas_coinciden_con_las_del_motor_existente_aetops():
    from backend.app.pipeline import run_aetops_raw
    per = Period("AETOPS", "mensual", 2026, 9)
    viejo = run_aetops_raw(LIBRO["AETOPS"], per)
    tot = viejo.tables["aetops.panorama.yoy"].groups[0].current.values
    ctx = construir_contexto(LIBRO["AETOPS"], per)
    assert operandos.pedidos_ventas(ctx).valor == tot["pedidos"].v and operandos.monto_ventas(ctx).valor == tot["monto"].v


def test_formulas_denominador_nulo_o_cero_no_produce_division_invalida():
    for den in (0, None):
        r = run(ctx_de(pedidos_n(5), trafico=tr(add=den)), "R-COBERTURA-ATC", unidad_carritos="eventos")
        assert all(x.valor is None and x.estado == "not_verifiable" for x in r)


# =================================================================================== calidad del motor
def libro(tmp_path, ventas=None, trafico=True, quitar=(), extra=(), nombre="x.xlsx", hojas=("ventas", "catalogo", "trafico")):
    cols = [c for c in CABECERAS["GLP1"]["ventas"] if c not in quitar] + list(extra)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "ventas"
    ws.append(cols)
    base = {"fecha_pedido": F(5, 9), "id_pedido": "P1", "id_paciente": "X1", "paciente_nuevo": "SI", "sku": "S1", "canal": "WEB", "estado": "JAL", "region": "R",
            "piezas": 1, "monto_venta": 100, "forma_pago": "T", "modo_entrega": "D", "programa_lealtad": "N", "adicional": "z"}
    for v in (ventas or [{}]):
        d = base | v
        ws.append([d.get(c) for c in cols])
    if "catalogo" in hojas:
        c = wb.create_sheet("catalogo"); c.append(["sku", "producto", "categoria"]); c.append(["S1", "Prod", "A"])
    if trafico and "trafico" in hojas:
        t = wb.create_sheet("trafico"); t.append(CABECERAS["GLP1"]["trafico"])
        t.append([F(1, 9), "general", None, None, 10, 0, 0, 0, 0, 1000, 0, 130, 0, 0, 0])
    if "ventas" not in hojas:
        del wb["ventas"]
    p = tmp_path / nombre
    wb.save(p)
    return p


def contexto(p):
    return construir_contexto(p, Period("GLP1", "mensual", 2026, 9))


def test_calidad_columnas_adicionales_no_afectan(tmp_path):
    base = motor.ejecutar(contexto(libro(tmp_path)))
    extra = motor.ejecutar(contexto(libro(tmp_path, extra=("adicional",), nombre="e.xlsx")))
    assert [r.to_dict() for r in base] == [r.to_dict() for r in extra]


def test_calidad_columna_obligatoria_faltante_es_not_verifiable_con_explicacion(tmp_path):
    ctx = contexto(libro(tmp_path, quitar=("id_paciente",)))
    assert any(f.id == "RAW_COLUMN_MISSING" for f in ctx.hallazgos_lectura)
    res = motor.ejecutar(ctx)
    rel = res[0]
    assert rel.estado == "not_verifiable" and "ventas" in rel.mensaje and rel.faltante
    assert not any(r.codigo == "fallo_interno" for r in res) and not any(r.severity == "block" for r in res)


def test_calidad_hoja_ausente_tipos_incorrectos_y_nulos_no_rompen(tmp_path):
    res = motor.ejecutar(contexto(libro(tmp_path, hojas=("catalogo", "trafico"), nombre="sinventas.xlsx")))
    assert all(r.estado in motor.ESTADOS for r in res) and not any(r.codigo == "fallo_interno" for r in res)
    sucio = [{"monto_venta": "abc"}, {"fecha_pedido": "no es fecha", "id_pedido": "P2"}, {"piezas": "x", "id_pedido": "P3"},
             {"id_pedido": None, "id_paciente": None}, {"id_pedido": "P4", "sku": None, "canal": None}]
    ctx = contexto(libro(tmp_path, ventas=sucio, nombre="sucio.xlsx"))
    res = motor.ejecutar(ctx)
    assert not any(r.codigo == "fallo_interno" for r in res) and not any(r.severity == "block" for r in res)
    rel = res[0]
    assert rel.estado in ("valid", "error", "not_verifiable") and "Traceback" not in rel.mensaje
    pedidos = operandos.pedidos_ventas(ctx)
    assert pedidos.valor is None or pedidos.valor < 5                      # las líneas inválidas no se cuentan como pedidos del sistema de ventas


def test_calidad_archivo_inexistente_o_corrupto_falla_de_forma_controlada(tmp_path):
    with pytest.raises(ErrorLectura, match="No existe"):
        contexto(tmp_path / "no_existe.xlsx")
    malo = tmp_path / "malo.xlsx"
    malo.write_text("esto no es un libro", encoding="utf-8")
    with pytest.raises(ErrorLectura, match="No se pudo leer malo.xlsx"):
        contexto(malo)


def test_calidad_desgloses_de_trafico_no_se_usan_como_total_del_sitio(tmp_path):
    p = libro(tmp_path, nombre="desg.xlsx")
    wb = openpyxl.load_workbook(p)
    t = wb["trafico"]
    fila = lambda vista, valor, sku, add: [F(1, 9), vista, valor, sku, 5, 0, 0, 0, 0, add, 0, 20, 0, 0, 0]       # noqa: E731
    t.append(fila("edad", "18-24", None, 400)); t.append(fila("sexo", "M", None, 300)); t.append(fila("edad", "18-24", "S1", 99))
    wb.save(p)
    ctx = contexto(p)
    assert operandos.carritos_agregados(ctx).valor == D(1000) and operandos.compras_ga4(ctx).valor == D(130)      # solo vista=general y sku vacío
    wb = openpyxl.load_workbook(p); wb["trafico"].delete_rows(2); wb.save(p)                                         # sin fila general
    sin_total = contexto(p)
    assert operandos.carritos_agregados(sin_total).valor is None
    r = run(sin_total, "R-COBERTURA-ATC", unidad_carritos="eventos")
    assert all(x.estado == "not_verifiable" and x.valor is None for x in r)          # no suma desgloses para reconstruir el total


def test_calidad_ninguna_advertencia_bloquea_la_generacion():
    ctxs = [ctx_de(pedidos_n(100), trafico=tr(compras=c)) for c in (0, 10, 130, 500)] + [ctx_de([]), ctx_de(pedidos_n(3), "AETOPS")]
    for c in ctxs:
        res = motor.ejecutar(c)
        assert not any(r.severity == "block" for r in res) and not motor.resumen(res)["bloquea"]
        assert all(h.severity != "block" for h in motor.a_hallazgos(res))
        from backend.app.validator.rules import has_blockers
        assert has_blockers(motor.a_hallazgos(res)) is False


def test_calidad_mensajes_consistentes_sin_vocabulario_prohibido_y_todos_existen():
    cfg = config.cargar("reglas")
    claves = set()
    for r in cfg["reglas"]:
        for k, v in r["mensajes"].items():
            claves.add((r["id"], k))
            assert re.search(r"abandon|tasa de abandono", v, re.I) is None, (r["id"], k)
            assert "  " not in v and v.strip() == v, (r["id"], k)
            list(__import__("string").Formatter().parse(v))                                   # plantilla bien formada
    usadas = set()
    for f in ("rules_datos.py", "rules_conc.py", "rel_pedidos_carritos.py", "motor.py"):
        t = (VALIDATOR / f).read_text(encoding="utf-8")
        usadas |= set(re.findall(r'clave="([a-z_0-9.]+)"', t))
        usadas |= {f"{a}.{b}" for a, b in re.findall(r'resultado\(\s*"([a-z_0-9]+)",\s*"(valid|warning|error|not_verifiable|not_applicable)"', t)}
    todas = {k for _, k in claves}
    assert {u for u in usadas if "{" not in u} <= todas, sorted(u for u in usadas if u not in todas)


def test_calidad_rendimiento_con_un_archivo_grande_en_memoria():
    n = 200_000
    lin = [L(i, f"P{i // 2}", f"X{i % 9000}", F(1 + i % 27), f"S{1 + i % 3}", "WEB" if i % 4 else "TEL") for i in range(1, n + 1)]
    ctx = ctx_de(lin, trafico=tr(add=500_000, compras=90_000))
    t = time.time()
    res = motor.ejecutar(ctx)
    dt = time.time() - t
    assert not any(r.codigo == "fallo_interno" for r in res)
    assert dt < 60, f"el motor tardó {dt:.1f} s con {n:,} líneas"
    print(f"\nRENDIMIENTO motor.ejecutar: {n:,} líneas en {dt:.2f} s")


@hay_machotes
def test_calidad_reproducibilidad_entre_procesos_con_semillas_de_hash_distintas():
    script = ("import json,sys;from backend.app.models import Period;from backend.app.validator import motor;"
              "from backend.app.validator.normalizar import construir_contexto as c;"
              "r=motor.ejecutar(c(sys.argv[1],Period('AETOPS','mensual',2026,9)));print(json.dumps([x.to_dict() for x in r],sort_keys=True,default=str))")
    hashes = set()
    for seed in ("1", "977"):
        out = subprocess.run([sys.executable, "-c", script, str(LIBRO["AETOPS"])], capture_output=True, text=True, cwd=ROOT,
                             env={**os.environ, "PYTHONHASHSEED": seed, "PYTHONPATH": str(ROOT)}, timeout=300)
        assert out.returncode == 0, out.stderr[-500:]
        hashes.add(hashlib.sha256(out.stdout.encode()).hexdigest())
    assert len(hashes) == 1


# =================================================================================== T-14 · privacidad e IA
MODULOS_MOTOR = ["motor.py", "normalizar.py", "operandos.py", "rules_datos.py", "rules_conc.py", "rel_pedidos_carritos.py"]


def test_t14_el_motor_no_usa_red_ni_escribe_archivos_ni_ejecuta_procesos():
    prohibido = re.compile(r"\b(requests|httpx|urllib|socket|http\.client|ftplib|smtplib|subprocess|os\.system)\b|\.write_text|\.write_bytes|open\([^)]*['\"][wa]", re.I)
    for f in MODULOS_MOTOR + ["../config/__init__.py"]:
        txt = (VALIDATOR / f).read_text(encoding="utf-8")
        assert prohibido.search(txt) is None, f
    assert not [n for n in dir(config) if re.match(r"(guardar|escribir|save|write|dump)", n)]      # la configuración solo se lee


def test_t14_la_ia_no_puede_modificar_reglas_ni_el_motor_no_depende_de_la_ia():
    servicio = (ROOT / "backend/app/web/service.py").read_text(encoding="utf-8")
    assert not re.search(r"validator\.(motor|rules_conc|rules_datos|normalizar|operandos)|from \.\.validator import motor|config\.cargar", servicio)
    for f in MODULOS_MOTOR:
        assert not re.search(r"cohere|ia_log|verify_rewrite|narrative", (VALIDATOR / f).read_text(encoding="utf-8"), re.I), f


def test_t14_la_ia_no_puede_cambiar_cifras_verificadas_de_los_resultados():
    from backend.app.web.service import verify_rewrite
    r = run(ctx_de(pedidos_n(250), trafico=tr()), "R-COBERTURA-ATC", unidad_carritos="eventos")[0]
    ok = verify_rewrite(r.mensaje, r.mensaje.replace("Por cada 100", "De cada 100"))
    assert ok["ok"] is True
    for tampered in (r.mensaje.replace("25.00", "30.00"), r.mensaje + " Equivale a 75.00 % de abandono."):
        res = verify_rewrite(r.mensaje, tampered)
        assert res["ok"] is False and res["texto"] == r.mensaje                         # se descarta y se conserva el texto determinista
    causal = verify_rewrite(r.mensaje, r.mensaje + " Esto se debe a que los clientes abandonan.")
    assert causal["ok"] is False                                                        # no se convierte una hipótesis en hecho


def test_t14_todo_resultado_tiene_una_fuente_identificable():
    res = motor.ejecutar(ctx_de(pedidos_n(100), trafico=tr(compras=130)))
    for r in res:
        assert r.regla_id and re.match(r"^\d+\.\d+\.\d+$", r.regla_version) and r.evidencia, r.id
        assert r.estado_validacion == "not_validated_with_real_data"
    assert {x.regla_id for x in res} == set(config.REGLAS_FASE1)


# =================================================================================== T-20 · fixtures reproducibles
def test_t20_las_fixtures_sinteticas_son_deterministas_y_marcadas():
    from tools import make_fixtures_fase1 as mk
    assert mk.generar() == mk.generar() and mk.verificar() == []
    man = json.loads((ROOT / "tests/fixtures/fase1/manifest.json").read_text(encoding="utf-8"))
    assert man["sintetico"] is True and all(f["sintetico"] for f in man["fixtures"])
