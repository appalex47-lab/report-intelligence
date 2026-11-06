"""Fase 4 · escenarios E1 y E2 e indicador IND-01 (`backend/app/escenarios.py`) y su integración en el servicio.

Cubre: fórmulas exactas en Decimal y coincidencia con la narrativa vigente (misma cifra, sin segunda fuente de verdad), rotulado de los supuestos
heredados, datos faltantes / nulos / ceros, separación de las dos fuentes de pedidos, unidad de carritos, relaciones superiores a 100 %,
denominaciones prohibidas, ausencia de identificadores, determinismo, no mutación y robustez del servicio. Los contextos sintéticos están
declarados como tales; ninguna cifra de un libro real.
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import re
from decimal import Decimal
from pathlib import Path

import pytest

from backend.app import config, escenarios as E
from backend.app.models import Period
from backend.app.narrative.rules import RULES
from backend.app.pipeline import run_aetops_raw, run_glp1_raw
from backend.app.validator import operandos
from backend.app.validator.normalizar import Contexto, Linea, construir_contexto

D = Decimal
EJEMPLOS = Path(__file__).resolve().parents[2] / "data" / "ejemplos"
GLP1 = EJEMPLOS / "GLP1_crudo_ejemplo.xlsx"
AET = EJEMPLOS / "AETOPS_crudo_ejemplo.xlsx"
PER_G = Period("GLP1", "mensual", 2026, 9)
PER_A = Period("AETOPS", "mensual", 2026, 9)
COLS_V = {"fecha_pedido", "id_pedido", "id_paciente", "paciente_nuevo", "sku", "canal", "estado", "piezas", "monto_venta"}


# --------------------------------------------------------------------------------------------- fixtures sintéticos (NO son datos reales)
def ctx_sintetico(pedidos: int, carritos, compras="0", canal="WEB", canales=None, mes=1, trafico=True):
    c = Contexto("GLP1", Period("GLP1", "mensual", 2026, mes), "sintetico.xlsx")
    c.columnas = {"ventas": set(COLS_V), "catalogo": {"sku", "producto", "categoria"}}
    c.catalogo = {"S1": {"sku": "S1", "categoria": "A"}}
    for i in range(pedidos):
        cn = canales[i % len(canales)] if canales else canal
        v = {"id_pedido": f"P{i}", "id_paciente": f"X{i}", "fecha_pedido": "2026-01-10", "sku": "S1", "canal": cn, "monto_venta": "100", "piezas": "1"}
        c.lineas.append(Linea(i + 2, f"P{i}", f"X{i}", dt.date(2026, mes, 10), "S1", D(100), D(1), v))
    if trafico:
        c.columnas["trafico"] = {"mes", "vista", "valor", "sku", "visitas", "add_to_cart", "compras"}
        c.trafico_sitio = {(2026, mes): {"add_to_cart": None if carritos is None else D(str(carritos)), "compras": D(str(compras)), "visitas": D(5000)}}
    return c


def ind(ctx, unidad="glp1"):
    return E.ind01(ctx, unidad)


def por_fuente(i):
    return {r["fuente_pedidos"]: r for r in i["resultados"]}


def textos(o):
    """Todas las cadenas de una estructura anidada."""
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from textos(v)
    elif isinstance(o, (list, tuple)):
        for v in o:
            yield from textos(v)


@pytest.fixture(scope="module")
def glp1():
    res = run_glp1_raw(GLP1, PER_G)
    ctx = construir_contexto(GLP1, PER_G)
    return res, ctx, E.construir(res, "glp1", PER_G, ctx)


@pytest.fixture(scope="module")
def aet():
    res = run_aetops_raw(AET, PER_A)
    return res, E.construir(res, "aetops", PER_A, None)


# --------------------------------------------------------------------------------------------- E1
def test_e1_formula_exacta_y_misma_cifra_que_la_narrativa(glp1):
    res, _ctx, o = glp1
    e1 = o["escenarios"][0]
    m_neg = sum(r.values["monto_negado"].v for r in res.blocks["negados"].rows)
    venta = res.blocks["panorama"].rows[0].values["monto"].v
    assert e1["estado"] == "calculable"
    assert D(e1["resultado"]["ingreso_ilustrativo"]) == m_neg * RULES.recovery_scenario
    assert D(e1["resultado"]["proporcion_venta"]) == m_neg * RULES.recovery_scenario / venta
    # misma cifra que la recomendación de la presentación (una sola fuente de verdad, sin duplicar lógica)
    from backend.app.narrative.glp1_exec import build_executive_glp1
    ex = build_executive_glp1(res.blocks, res.funnel, PER_G)
    texto = " ".join(p.plain for p in ex.recomendaciones if "recuperar" in p.plain)
    from backend.app.narrative.aetops import money
    cifra = money(D(e1["resultado"]["ingreso_ilustrativo"]))                 # el mismo formateador que usa la presentación
    assert cifra in texto, (cifra, texto[:300])


def test_e1_aetops_usa_la_misma_lectura_que_la_narrativa(aet):
    res, o = aet
    e1 = o["escenarios"][0]
    alta = res.negados["aetops.negados.alta"]
    assert e1["estado"] == "calculable" and D(e1["resultado"]["ingreso_ilustrativo"]) == alta.total.v * RULES.recovery_scenario
    from backend.app.narrative.executive import build_executive
    ex = build_executive(res, PER_A)
    texto = " ".join(p.plain for p in ex.recomendaciones if "recuperar" in p.plain)
    from backend.app.narrative.aetops import money
    assert money(alta.total.v * RULES.recovery_scenario, True) in texto, texto[:300]


@pytest.mark.parametrize("m_neg,venta,estado", [(None, D(1000), "no_verificable"), (D(100), None, "no_verificable"), (D(100), D(0), "no_verificable"),
                                                (D(100), D(-5), "no_verificable"), (D(0), D(1000), "calculable")])
def test_e1_condiciones_faltante_no_es_cero(m_neg, venta, estado):
    e1 = E.escenario_e1(venta, m_neg, D("0.25"), True)
    assert e1["estado"] == estado
    if estado == "no_verificable":
        assert e1["resultado"] is None and e1["faltante"] and "0 %" not in e1["lectura"]       # ni se calcula ni se muestra 0
    else:
        assert D(e1["resultado"]["ingreso_ilustrativo"]) == 0


def test_e1_variables_separan_observado_calculado_y_supuesto(glp1):
    e1 = glp1[2]["escenarios"][0]
    tipos = {v["clave"]: v["tipo"] for v in e1["variables"]}
    assert tipos == {"M_neg": "observado", "r": "supuesto_heredado", "Venta_total": "observado"}
    r = next(v for v in e1["variables"] if v["clave"] == "r")
    assert D(r["valor"]) == D("0.25") and r["etiqueta"] == "Supuesto heredado, no validado" and r["fuente"].endswith("rules.py:21")
    assert e1["resultado"]["tipo"] == "calculado" and "proporcional a r" in e1["efecto_supuesto"]


# --------------------------------------------------------------------------------------------- E2
def test_e2_formula_exacta_y_misma_cifra_que_la_narrativa(glp1):
    res, _ctx, o = glp1
    e2 = o["escenarios"][1]
    P = res.blocks["panorama"].rows[0].values
    esperado = P["carritos_abandonados"].v * RULES.cart_recovery_scenario * P["ticket"].v
    assert e2["estado"] == "calculable" and D(e2["resultado"]["ingreso_ilustrativo"]) == esperado
    from backend.app.narrative.glp1_exec import build_executive_glp1
    texto = " ".join(p.plain for p in build_executive_glp1(res.blocks, res.funnel, PER_G).recomendaciones if "Reducir el abandono" in p.plain)
    from backend.app.narrative.aetops import money
    assert money(esperado) in texto, (money(esperado), texto[:300])
    assert e2["nombre"] == "Recuperación de abandono" and "histórica" in e2["denominacion_historica"]


def test_e2_variables_y_aclaracion_obligatoria(glp1):
    e2 = glp1[2]["escenarios"][1]
    assert {v["clave"]: v["tipo"] for v in e2["variables"]} == {"A": "observado", "c": "supuesto_heredado", "T": "calculado", "Venta_total": "observado"}
    assert e2["aclaracion_metrica"] == E.ACLARACION_ABANDONADOS
    assert "No constituye abandono individual comprobado" in e2["aclaracion_metrica"]
    assert next(v for v in e2["variables"] if v["clave"] == "c")["etiqueta"] == "Supuesto heredado, no validado"


@pytest.mark.parametrize("aband,tick,venta", [(None, D(5), D(10)), (D(0), D(5), D(10)), (D(10), None, D(10)), (D(10), D(0), D(10)), (D(10), D(5), None)])
def test_e2_condicion_vigente_a_y_t_positivos(aband, tick, venta):
    e2 = E.escenario_e2("glp1", venta, aband, tick, D("0.1"), False, True)
    assert e2["estado"] == "no_verificable" and e2["resultado"] is None and e2["faltante"]


def test_e2_aetops_no_aplica_sin_trafico(aet):
    e2 = aet[1]["escenarios"][1]
    assert e2["estado"] == "no_aplica" and "sin hoja `trafico`" in e2["lectura"] and e2["resultado"] is None


def test_e2_columna_vacia_se_declara_y_no_se_inventa_el_derivado():
    e2 = E.escenario_e2("glp1", D(1000), D(0), D(10), D("0.1"), True, True)
    assert e2["estado"] == "no_verificable" and "no se muestra" in e2["lectura"] and e2["resultado"] is None


# --------------------------------------------------------------------------------------------- supuestos
def test_supuestos_son_los_heredados_y_estan_rotulados(glp1):
    s = glp1[2]["supuestos"]
    assert D(s["r"]["valor"]) == D("0.25") and D(s["c"]["valor"]) == D("0.10")
    assert all(v["etiqueta"] == "Supuesto heredado, no validado" and not v["inconsistencia_configuracion"] for v in s.values())
    assert all(v["validacion_operacional"] == "no_validada_con_datos_reales" for v in s.values())
    assert all(v["variantes"] == {"conservador": "No configurado", "optimista": "No configurado"} for v in s.values())


def test_si_la_configuracion_difiere_de_las_reglas_se_declara(monkeypatch):
    cfg = copy.deepcopy(config.cargar("reglas"))
    cfg["parametros"]["e1_recuperacion_negados_medio"]["valor"] = 0.30
    monkeypatch.setattr(E.config, "cargar", lambda n: cfg if n == "reglas" else config.cargar.__wrapped__(n))
    assert E.supuestos()["r"]["inconsistencia_configuracion"] is True and E.supuestos()["r"]["valor"] == RULES.recovery_scenario


# --------------------------------------------------------------------------------------------- comparación
def test_comparacion_no_suma_ni_oculta_diferencias(glp1):
    c = glp1[2]["comparacion"]
    assert c["estado"] == "comparable" and set(c["montos"]) == {"E1", "E2"} and "no se suman" in c["no_sumar"]
    assert not any("total" in k.lower() or "suma" in k.lower() for k in c["montos"])
    assert any(f["aspecto"] == "Lo que NO demuestra" for f in c["filas"]) and c["conclusiones_requieren_validacion"] and c["conclusiones_confiables"]


def test_comparacion_parcial_si_un_escenario_no_calculable(aet):
    assert aet[1]["comparacion"]["estado"] == "parcial"


# --------------------------------------------------------------------------------------------- IND-01
def test_ind01_ejemplo_25_por_ciento_exacto():
    r = por_fuente(ind(ctx_sintetico(250, 1000, compras=300)))
    assert D(r["sistema_ventas"]["relacion"]) == D(25) and D(r["ga4_compras"]["relacion"]) == D(30)
    assert "25" in r["sistema_ventas"]["interpretacion"] and "sistema de ventas" in r["sistema_ventas"]["interpretacion"]
    assert r["sistema_ventas"]["estado"] == "calculable_con_limitacion" and r["sistema_ventas"]["mayor_100"] is None      # unidad no declarada


def test_ind01_machote_glp1_dos_resultados_independientes(glp1):
    i = glp1[2]["ind01"]
    r = por_fuente(i)
    assert round(D(r["sistema_ventas"]["relacion"]), 2) == D("12.48") and round(D(r["ga4_compras"]["relacion"]), 2) == D("14.00")
    assert r["sistema_ventas"]["numerador"]["valor"] == "2356" and r["ga4_compras"]["numerador"]["valor"] == "2643" and r["sistema_ventas"]["carritos"]["valor"] == "18883"
    f = i["fuentes_pedidos"]
    assert f["sistema_ventas"]["valor"] == "2356" and f["ga4_compras"]["valor"] == "2643" and round(D(f["brecha_relativa"]) * 100, 2) == D("12.18")
    assert "NO VALIDADA" in f["equivalencia"] and "no se suman" in f["no_se_suman"] and "no un error" in f["brecha_texto"]
    assert {d["aspecto"] for d in f["diferencias_documentadas"]} >= {"Conteo", "Definición", "Duplicados", "Atribución", "Temporalidad", "Limitaciones de medición"}


def test_ind01_ninguna_fuente_sustituye_ni_se_combina():
    # sin compras GA4 (None) no se toma la otra fuente: es «no calculable», nunca 0 % ni el valor de la otra
    c = ctx_sintetico(250, 1000)
    c.trafico_sitio = {(2026, 1): {"add_to_cart": D(1000), "compras": None, "visitas": D(1)}}
    r = por_fuente(ind(c))
    assert r["ga4_compras"]["estado"] == "no_calculable" and r["ga4_compras"]["relacion"] is None and r["ga4_compras"]["faltante"]
    assert D(r["sistema_ventas"]["relacion"]) == D(25)                                  # la otra fuente sigue siendo independiente
    assert not any("promedio" in t.lower() and "se promedian" not in t.lower() for t in textos(r))


@pytest.mark.parametrize("pedidos,carritos", [(0, 1000), (250, None), (250, 0)])
def test_ind01_faltante_o_division_cero_es_no_calculable(pedidos, carritos):
    r = por_fuente(ind(ctx_sintetico(pedidos, carritos, compras="0" if carritos is None else "5")))
    sv = r["sistema_ventas"]
    assert sv["estado"] == "no_calculable" and sv["relacion"] is None and sv["faltante"] and "No se muestra 0 %" in sv["interpretacion"]


def test_ind01_pedidos_cero_informado_con_carritos_es_calculable_0():
    r = por_fuente(ind(ctx_sintetico(0, 1000, compras="0")))
    assert r["ga4_compras"]["estado"] != "no_calculable" and D(r["ga4_compras"]["relacion"]) == 0       # el faltante ≠ cero informado


def test_ind01_mayor_100_se_conserva_se_explica_y_se_clasifica():
    r = por_fuente(ind(ctx_sintetico(1200, 1000, compras="1500")))
    sv, ga = r["sistema_ventas"], r["ga4_compras"]
    assert D(sv["relacion"]) == D(120) and D(ga["relacion"]) == D(150)                           # valor ORIGINAL: ni 100 ni ajustado
    m = sv["mayor_100"]
    assert m["valor_original"] == sv["relacion"] and m["aviso"] == E.AVISO_MAYOR_100
    assert m["clasificacion"] == "limitacion_metodologica" and "no demostrable como error" in m["explicacion_clasificacion"]
    causas = {c["causa"]: c["estado"] for c in m["causas_posibles"]}
    assert causas["Fuentes distintas"] == "concurre" and causas["Unidades distintas (eventos, sesiones, usuarios, pedidos)"] == "no_verificable"
    assert causas["Duplicados"] == "no_verificable" and causas["Periodos distintos"] == "no_concurre"
    assert m["variables"]["numerador"]["valor"] == "1200" and m["variables"]["carritos"]["valor"] == "1000"
    assert causas  # incluye atribución, universo y ventana temporal
    assert {"Atribución", "Universos o filtros distintos", "Ventana temporal de maduración"} <= set(causas)
    assert ga["mayor_100"]["causas_posibles"][0]["estado"] == "no_concurre"                       # GA4 / GA4: misma fuente


def test_ind01_exactamente_100_no_dispara_aviso():
    r = por_fuente(ind(ctx_sintetico(1000, 1000, compras="1")))["sistema_ventas"]
    assert D(r["relacion"]) == 100 and r["mayor_100"] is None


def test_ind01_el_aviso_no_afirma_una_causa():
    assert "puede ocurrir" in E.AVISO_MAYOR_100 and "Interprétese con cautela" in E.AVISO_MAYOR_100
    assert not re.search(r"\b(error de|se debe a|es causado)\b", E.AVISO_MAYOR_100)


def test_anomalia_matematica_distinta_de_limitacion():
    assert E.anomalia_matematica(D(5), D(10)) == [] and E.anomalia_matematica(D(120), D(100)) == []
    assert E.anomalia_matematica(D(-1), D(10)) and E.anomalia_matematica(D(1), D(-1)) and E.anomalia_matematica(D(1), D(0))


def test_ind01_unidad_declarada_o_no(monkeypatch):
    i = ind(ctx_sintetico(250, 1000))
    assert i["unidad_carritos"]["estado"] == "NO VERIFICABLE" and i["unidad_carritos"]["declarada"] == "no_declarada"
    assert "no se asume" in i["unidad_carritos"]["advertencia"] and "no se convierten" in i["unidad_carritos"]["no_se_convierte"]
    assert por_fuente(i)["sistema_ventas"]["carritos"]["unidad"] == "unidad no declarada"
    from backend.app.validator import motor
    orig = motor.catalogo

    def con_unidad(*a, **k):
        cat = orig(*a, **k)
        d = cat["R-COBERTURA-ATC"]
        cat["R-COBERTURA-ATC"] = type(d)(d.datos, {**d.parametros, "unidad_carritos": "eventos"}, d.validacion)
        return cat
    monkeypatch.setattr(motor, "catalogo", con_unidad)
    j = ind(ctx_sintetico(250, 1000))
    assert j["unidad_carritos"]["estado"] == "DECLARADA" and j["unidad_carritos"]["advertencia"] is None
    r = por_fuente(j)["sistema_ventas"]
    assert r["carritos"]["unidad"] == "eventos" and r["estado"] == "calculable"                 # con unidad declarada y sin otras limitaciones
    assert "carritos únicos" not in " ".join(textos(j)).lower()                                  # AC-31


def test_ind01_universo_con_varios_canales_se_advierte():
    r = por_fuente(ind(ctx_sintetico(250, 1000, canales=["WEB", "APP"])))["sistema_ventas"]
    assert any("canales" in x for x in r["limitaciones"])


def test_ind01_no_aplica_en_aetops_y_no_calculable_en_libro_no_crudo(aet):
    assert aet[1]["ind01"]["estado"] == "no_aplica" and "sin hoja `trafico`" in aet[1]["ind01"]["motivo"] and aet[1]["ind01"]["resultados"] == []
    j = ind(None, "glp1")
    assert j["estado"] == "no_calculable" and j["faltante"] and "libro no es de datos crudos" in j["motivo"]
    sin = ind(ctx_sintetico(10, 100, trafico=False))                                             # GLP-1 sin hoja trafico: es un faltante, no una inaplicabilidad
    assert sin["estado"] == "no_calculable" and sin["faltante"][0]["archivo"] == "trafico" and "no se calcula ni se sustituye" in sin["motivo"]


def test_ind01_no_usa_identificadores_de_carrito_transaccion_o_sesion():
    c = ctx_sintetico(250, 1000)
    assert not any(col for cols in c.columnas.values() for col in cols if re.search(r"(id_)?(carrito|transaccion|sesion|cart_id|transaction)", col))
    assert D(por_fuente(ind(c))["sistema_ventas"]["relacion"]) == 25                             # se calcula sin ninguna columna de identificador (AC-23)
    cfg = config.cargar("mapeo_columnas")
    assert not re.search(r"carrito_id|id_carrito|transaction_id|session_id|id_sesion", json.dumps(cfg))


def test_nunca_se_calcula_el_complemento(glp1):
    t = " ".join(textos(glp1[2])).lower()
    assert "100 −" not in t and "100 -" not in t and "(100 − relación)" not in t
    for r in glp1[2]["ind01"]["resultados"]:
        assert "abandon" not in r["interpretacion"].lower() or "no es una tasa de abandono" in r["interpretacion"].lower()


def test_denominaciones_prohibidas_no_aparecen_en_ninguna_salida(glp1, aet):
    for o in (glp1[2], aet[1]):
        todo = " ".join(textos(o)).lower()
        for prohibida in E.DENOMINACIONES_PROHIBIDAS:
            assert prohibida not in todo, prohibida


def claves(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield str(k)
            yield from claves(v)
    elif isinstance(o, (list, tuple)):
        for v in o:
            yield from claves(v)


def test_ninguna_clave_calcula_complemento_suma_ni_promedio_de_fuentes(glp1, aet):
    """Garantía estructural (AC-22, AC-29): no existe ningún campo de abandono derivado, de complemento, de suma ni de promedio entre fuentes."""
    for o in (glp1[2], aet[1]):
        for k in set(claves(o)) - {"no_se_suman", "equivalencia", "no_sumar"}:                      # estas tres son advertencias, no cálculos
            assert not re.search(r"abandono|complemento|restante|suma|total_pedidos|promedio|combinad|equivalen", k.lower()), k


# --------------------------------------------------------------------------------------------- integridad
def test_toda_variable_tiene_tipo_fuente_y_etiqueta_si_es_supuesto(glp1, aet):
    for o in (glp1[2], aet[1]):
        for e in o["escenarios"]:
            for v in e["variables"]:
                assert v["tipo"] in E.TIPOS and v["fuente"]
                assert (v["tipo"] != "supuesto_heredado") or v["etiqueta"] == E.ETIQUETA_SUPUESTO
        for r in (o["ind01"] or {}).get("resultados", []):
            assert r["numerador"]["fuente"] and r["carritos"]["fuente"] and r["numerador"]["tipo"] in E.TIPOS


def test_la_estructura_es_json_determinista_y_no_muta_la_entrada(glp1):
    res, ctx, o = glp1
    antes = copy.deepcopy(ctx.trafico_sitio), len(ctx.lineas)
    o2 = E.construir(res, "glp1", PER_G, ctx)
    assert json.dumps(o, sort_keys=True) == json.dumps(o2, sort_keys=True)
    assert (ctx.trafico_sitio, len(ctx.lineas)) == antes and o["esquema"] == E.ESQUEMA


def test_pendientes_de_validacion_declarados(glp1):
    p = " ".join(glp1[2]["pendientes_validacion"])
    assert "25 %" in p and "10 %" in p and "no validad" in p.lower() and "Equivalencia" in p and "Unidad" in p


# --------------------------------------------------------------------------------------------- servicio
@pytest.fixture()
def servicio(tmp_path, monkeypatch):
    import importlib
    monkeypatch.setenv("REPORT_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("REPORT_HISTORY_DB", str(tmp_path / "h.sqlite"))
    from backend.app.web import service
    importlib.reload(service)
    return service


def _analizar(S, unidad, libro):
    rid = S.create_run(unidad, "mensual", 2026, 9)["id"]
    S.store_file(rid, "l.xlsx", libro.read_bytes())
    return S.analyze(rid), rid


def test_el_servicio_expone_el_panel_en_glp1_y_aetops(servicio):
    a, _ = _analizar(servicio, "glp1", GLP1)
    x = a["escenarios_indicador"]
    assert [e["id"] for e in x["escenarios"]] == ["E1", "E2"] and x["ind01"]["estado"] == "calculable_con_limitacion"
    json.dumps(a)                                                                       # serializable tal como viaja a la interfaz
    b, _ = _analizar(servicio, "aetops", AET)
    assert b["escenarios_indicador"]["ind01"]["estado"] == "no_aplica"
    assert {"findings", "kpis", "can_generate", "cumplimiento"} <= set(a)               # el análisis existente no cambia de forma


def test_si_el_panel_falla_el_analisis_sigue_y_se_declara(servicio, monkeypatch):
    def roto(*a, **k):
        raise RuntimeError("boom")
    monkeypatch.setattr(E, "construir", roto)
    a, _ = _analizar(servicio, "glp1", GLP1)
    x = a["escenarios_indicador"]
    assert "No se pudo construir el panel" in x["no_disponible"] and x["escenarios"] == [] and a["findings"] is not None     # S-3: no bloquea
    assert "boom" not in json.dumps(x)                                                  # no filtra la traza al usuario


def test_el_panel_no_cambia_los_hallazgos_ni_la_generacion(servicio):
    a, rid = _analizar(servicio, "glp1", GLP1)
    solo = {k: v for k, v in a.items() if k != "escenarios_indicador"}
    from backend.app.web import service as S
    assert json.dumps(solo, sort_keys=True) == json.dumps({k: v for k, v in S.analyze(rid).items() if k != "escenarios_indicador"}, sort_keys=True)


# --------------------------------------------------------------------------------------------- auditoría independiente (PR #23): defectos hallados y su corrección
def test_ind01_estado_global_es_calculable_si_todos_lo_son(monkeypatch):
    """Hallazgo A-04: con unidad declarada y sin otras limitaciones el estado global no puede decir «con limitación»."""
    from backend.app.validator import motor
    orig = motor.catalogo

    def con_unidad(*a, **k):
        cat = orig(*a, **k)
        d = cat["R-COBERTURA-ATC"]
        cat["R-COBERTURA-ATC"] = type(d)(d.datos, {**d.parametros, "unidad_carritos": "eventos"}, d.validacion)
        return cat
    monkeypatch.setattr(motor, "catalogo", con_unidad)
    i = ind(ctx_sintetico(250, 1000, compras="300"))
    assert [r["estado"] for r in i["resultados"]] == ["calculable", "calculable"] and i["estado"] == "calculable"
    monkeypatch.undo()                                                                          # de aquí en adelante la unidad vuelve a «no declarada»
    assert ind(ctx_sintetico(250, 1000))["estado"] == "calculable_con_limitacion"              # unidad no declarada
    c = ctx_sintetico(250, 1000)
    c.trafico_sitio = {(2026, 1): {"add_to_cart": D(1000), "compras": None, "visitas": D(1)}}
    assert ind(c)["estado"] == "calculable_con_limitacion"                                      # uno calculable y otro no
    assert ind(ctx_sintetico(0, 0))["estado"] == "no_calculable"                                # ninguno calculable


def test_e1_celdas_vacias_de_negados_se_declaran_y_no_se_presentan_como_dato_completo(tmp_path):
    """Hallazgo A-05: la presentación suma las celdas vacías como 0; el panel hace lo mismo (misma cifra) pero lo advierte."""
    import shutil
    import openpyxl
    p = tmp_path / "l.xlsx"
    shutil.copy(GLP1, p)
    wb = openpyxl.load_workbook(p)
    ws = wb["negados"]
    j = [c.value for c in ws[1]].index("monto_negado") + 1
    ws.cell(2, j).value = None
    wb.save(p)
    res = run_glp1_raw(p, PER_G)
    o = E.construir(res, "glp1", PER_G, construir_contexto(p, PER_G))
    e1 = o["escenarios"][0]
    assert e1["estado"] == "calculable" and len(e1["advertencias"]) == 1 and "subestimado" in e1["advertencias"][0]
    assert D(e1["resultado"]["ingreso_ilustrativo"]) == sum((r.values["monto_negado"].v or 0) for r in res.blocks["negados"].rows) * RULES.recovery_scenario
    limpio = E.construir(run_glp1_raw(GLP1, PER_G), "glp1", PER_G, None)["escenarios"][0]
    assert limpio["advertencias"] == []


def test_los_textos_de_supuestos_siguen_el_valor_realmente_aplicado(monkeypatch):
    """Hallazgo A-03: ningún texto fija «25 %» o «10 %»; se deriva del valor aplicado (si cambia, el texto cambia y se declara la inconsistencia)."""
    import dataclasses
    monkeypatch.setattr(E, "RULES", dataclasses.replace(RULES, recovery_scenario=D("0.30"), cart_recovery_scenario=D("0.15")))
    res = run_glp1_raw(GLP1, PER_G)
    o = E.construir(res, "glp1", PER_G, None)
    texto = " ".join(textos(o))
    assert "r = 30 %" in texto and "c = 15 %" in texto and "r = 25 %" not in texto and "c = 10 %" not in texto
    assert o["supuestos"]["r"]["inconsistencia_configuracion"] is True and o["supuestos"]["c"]["inconsistencia_configuracion"] is True


def test_no_existe_el_campo_en_presentacion(glp1):
    """Hallazgo A-06: el campo afirmaba que el escenario «está en la presentación», pero la narrativa conserva como máximo N recomendaciones."""
    assert "en_presentacion" not in set(claves(glp1[2]))


@pytest.mark.parametrize("hoja,e1,e2,ind_estado", [("trafico", "calculable", "no_verificable", "no_calculable"),
                                                    ("negados", "no_verificable", "calculable", "calculable_con_limitacion")])
def test_libros_glp1_sin_hoja_opcional_degradan_sin_inventar(tmp_path, hoja, e1, e2, ind_estado):
    import openpyxl
    p = tmp_path / "l.xlsx"
    wb = openpyxl.load_workbook(GLP1)
    del wb[hoja]
    wb.save(p)
    res = run_glp1_raw(p, PER_G)
    o = E.construir(res, "glp1", PER_G, construir_contexto(p, PER_G))
    assert (o["escenarios"][0]["estado"], o["escenarios"][1]["estado"], o["ind01"]["estado"]) == (e1, e2, ind_estado)
    for e in o["escenarios"]:
        assert (e["estado"] != "no_verificable") or (e["resultado"] is None and e["faltante"])


def test_aetops_sin_hoja_negados_no_calcula_e1(tmp_path):
    import openpyxl
    p = tmp_path / "a.xlsx"
    wb = openpyxl.load_workbook(AET)
    del wb["negados"]
    wb.save(p)
    o = E.construir(run_aetops_raw(p, PER_A), "aetops", PER_A, None)
    assert o["escenarios"][0]["estado"] == "no_verificable" and o["escenarios"][0]["resultado"] is None and o["escenarios"][1]["estado"] == "no_aplica"


def test_libro_en_formato_antiguo_sin_ventas_no_inventa_escenarios():
    from backend.app.pipeline import run_glp1
    res = run_glp1(EJEMPLOS.parent / "GLP1_sintetico_limpio.xlsx", "mensual", PER_G)
    o = E.construir(res, "glp1", PER_G, None)
    assert [e["estado"] for e in o["escenarios"]] == ["no_verificable", "no_verificable"] and o["ind01"]["estado"] == "no_calculable"
    assert all(e["resultado"] is None for e in o["escenarios"]) and json.dumps(o)


def test_el_panel_no_altera_hash_resultado_ni_el_resultado_original(glp1):
    """El panel solo lee: construirlo no modifica los bloques del motor ni el resultado canónico que alimenta `hash_resultado`."""
    from backend.app import provenance as pv
    res, ctx, _ = glp1
    antes = repr(res.blocks), repr(res.funnel), pv.canonico(PER_G, [], res)["valores"] if hasattr(pv, "canonico") else None
    for _ in range(2):
        E.construir(res, "glp1", PER_G, ctx)
    despues = repr(res.blocks), repr(res.funnel), pv.canonico(PER_G, [], res)["valores"] if hasattr(pv, "canonico") else None
    assert antes == despues


def test_t14_escenarios_no_usa_red_escritura_procesos_ni_ia():
    """Garantía T-14 también para este módulo: solo lee; no depende de la IA ni de `service`; el servicio no importa el motor."""
    src = (Path(__file__).resolve().parents[2] / "backend/app/escenarios.py").read_text(encoding="utf-8")
    prohibido = re.compile(r"\b(requests|httpx|urllib|socket|http\.client|ftplib|smtplib|subprocess|os\.system)\b|\.write_text|\.write_bytes|open\([^)]*['\"][wa]", re.I)
    assert prohibido.search(src) is None
    assert not re.search(r"cohere|ia_log|verify_rewrite|web\.service|from \.web|import service", src, re.I)
    servicio = (Path(__file__).resolve().parents[2] / "backend/app/web/service.py").read_text(encoding="utf-8")
    assert not re.search(r"validator\.(motor|rules_conc|rules_datos|normalizar|operandos)|from \.\.validator import motor|config\.cargar", servicio)


def ctx_trimestral(meses: dict, pedidos_por_mes: int):
    """Q1 2026 sintético: `meses` = {mes: (add_to_cart, compras)} (None = mes sin dato)."""
    c = Contexto("GLP1", Period("GLP1", "trimestral", 2026, 1), "sintetico.xlsx")
    c.columnas = {"ventas": set(COLS_V), "catalogo": {"sku", "producto", "categoria"}, "trafico": {"mes", "vista", "valor", "sku", "visitas", "add_to_cart", "compras"}}
    c.catalogo = {"S1": {"sku": "S1", "categoria": "A"}}
    n = 0
    for m in (1, 2, 3):
        for i in range(pedidos_por_mes):
            n += 1
            c.lineas.append(Linea(n + 1, f"P{n}", f"X{n}", dt.date(2026, m, 10), "S1", D(100), D(1),
                                  {"id_pedido": f"P{n}", "id_paciente": f"X{n}", "fecha_pedido": f"2026-{m:02d}-10", "sku": "S1", "canal": "WEB", "monto_venta": "100", "piezas": "1"}))
    c.trafico_sitio = {(2026, m): {"add_to_cart": D(a), "compras": D(b), "visitas": D(1)} for m, (a, b) in meses.items() if a is not None}
    return c


def test_ind01_trimestral_suma_los_tres_meses_y_un_mes_faltante_no_se_completa():
    ok = por_fuente(ind(ctx_trimestral({1: (400, 50), 2: (300, 60), 3: (300, 90)}, 100)))      # 300 pedidos; 1 000 carritos; 200 compras
    assert D(ok["sistema_ventas"]["relacion"]) == D(30) and D(ok["ga4_compras"]["relacion"]) == D(20)
    assert ok["sistema_ventas"]["carritos"]["periodo"] == "2026-01..03"
    falta = por_fuente(ind(ctx_trimestral({1: (400, 50), 3: (300, 90)}, 100)))                 # falta febrero: no se completa con 0
    assert falta["sistema_ventas"]["estado"] == "no_calculable" and falta["sistema_ventas"]["relacion"] is None and falta["ga4_compras"]["estado"] == "no_calculable"


def test_el_catalogo_de_definiciones_respalda_el_texto_sobre_la_unidad_de_carritos():
    """Hallazgo A-07: lo que el panel dice sobre `add_to_cart` debe coincidir con el catálogo aprobado, no contradecirlo."""
    defs = {d["id"]: d for d in config.cargar("definiciones")["definiciones"]}
    assert "add_to_cart" in defs["evento"]["descripcion"] and defs["evento"]["unidad"] == "eventos" and "carrito individual" in defs["evento"]["descripcion"]
    assert defs["carritos_agregados"]["unidad"] is None and "no está declarada" in " ".join(defs["carritos_agregados"]["limitaciones"])
    u = ind(ctx_sintetico(250, 1000))["unidad_carritos"]
    assert "catálogo de definiciones" in u["evidencia"] and "métrica de eventos" in u["evidencia"] and u["estado"] == "NO VERIFICABLE"
    assert "NO define" not in u["evidencia"]                                                     # la versión inicial contradecía al catálogo


def test_el_contexto_se_lee_una_vez_por_archivo_y_se_vuelve_a_leer_si_cambia(tmp_path, monkeypatch):
    """Hallazgo A-08 (rendimiento): el panel duplicaba el costo de cada análisis; ahora la lectura se reutiliza mientras el archivo no cambie."""
    import shutil
    from backend.app.validator import normalizar
    llamadas = []
    real = normalizar.construir_contexto
    monkeypatch.setattr(normalizar, "construir_contexto", lambda *a, **k: (llamadas.append(1), real(*a, **k))[1])
    E._CACHE_CTX.clear()
    p = tmp_path / "l.xlsx"
    shutil.copy(GLP1, p)
    res = run_glp1_raw(p, PER_G)
    a = E.construir_desde_libro(res, "glp1", PER_G, p, True)
    b = E.construir_desde_libro(res, "glp1", PER_G, p, True)
    assert len(llamadas) == 1 and json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    with open(p, "ab") as f:                                                                    # el archivo cambia (tamaño y fecha): se vuelve a leer
        f.write(b"\0")
    try:
        E.construir_desde_libro(res, "glp1", PER_G, p, True)
    except Exception:                                                                           # un libro alterado puede no abrirse: lo que importa es que NO se reutilizó el anterior
        pass
    assert len(llamadas) == 2
    E.construir_desde_libro(res, "glp1", PER_G, p, False)                                       # libro no crudo: no se lee nada
    assert len(llamadas) == 2
    E._CACHE_CTX.clear()


def test_ninguna_variable_inventa_una_moneda(glp1, aet):
    """Hallazgo de la Fase 5: el panel rotulaba los montos como «MXN», pero ningún libro declara la moneda (unidad inventada)."""
    for o in (glp1[2], aet[1]):
        assert "MXN" not in " ".join(textos(o))
        for e in o["escenarios"]:
            for v in e["variables"]:
                if v["unidad"] == "moneda":
                    assert "moneda no está declarada" in v["nota"]
