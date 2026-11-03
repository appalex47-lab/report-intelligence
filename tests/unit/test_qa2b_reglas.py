"""QA de la Fase 2B — pruebas funcionales por regla (T-01 a T-05, T-10, T-21). Datos sintéticos inventados.

El identificador de la prueba de la especificación va en el nombre (`test_t01_…`) para construir la matriz de pruebas
(`tools/matriz_pruebas_fase1.py`). Cada escenario compara el resultado obtenido contra el esperado de la especificación.
"""
from __future__ import annotations

import copy

import pytest

from backend.app import config
from backend.app.validator import motor
from backend.app.validator.motor import Operando, Razon, evaluar_razon
from tests.qa_util import CAT, D, L, cod, codigos, ctx_de, fecha as F, pedidos_n, run, tr


def ev(r, *ks):
    out = r.evidencia
    for k in ks:
        out = out[k]
    return out


# =================================================================================== T-01 · R-REL-PAC-PED
def test_t01_un_pedido_un_paciente():
    r = run(ctx_de([L(1, "P1", "X1", F(5))]), "R-REL-PAC-PED")
    g = r[0]
    assert g.estado == "valid" and (ev(g, "A"), ev(g, "B"), ev(g, "C"), ev(g, "pacientes_unicos")) == (1, 0, 0, 1)
    assert cod(r, "cobertura_paciente").estado == "valid"


def test_t01_un_paciente_con_varios_pedidos_es_valido_y_se_informa_la_recurrencia():
    g = run(ctx_de([L(1, "P1", "X1", F(2)), L(2, "P2", "X1", F(3)), L(3, "P3", "X1", F(4))]), "R-REL-PAC-PED")[0]
    assert g.estado == "valid" and ev(g, "pacientes_unicos") == 1 and ev(g, "universo_periodo") == 3 and D(ev(g, "razon_recurrencia")) == 3


def test_t01_un_pedido_con_varias_lineas_cuenta_una_vez():
    g = run(ctx_de([L(1, "P1", "X1", F(2), "S1"), L(2, "P1", "X1", F(2), "S2"), L(3, "P1", "X1", F(2), "S3")]), "R-REL-PAC-PED")[0]
    assert ev(g, "universo_periodo") == 1 and g.estado == "valid"                      # nunca se cuentan filas como pedidos


def test_t01_un_pedido_sin_paciente_baja_la_cobertura_pero_no_es_error():
    r = run(ctx_de([L(1, "P1", "", F(2)), L(2, "P2", "X2", F(3))]), "R-REL-PAC-PED")
    assert r[0].estado == "valid" and ev(r[0], "B") == 1 and D(ev(r[0], "cobertura_paciente")) == D("0.5")
    c = cod(r, "cobertura_paciente")
    assert c.estado == "warning" and c.severity == "info" and c.evidencia["muestra_id_pedido"] == ["P1"]


def test_t01_un_pedido_asociado_a_dos_pacientes_es_error_y_no_cuenta_para_pacientes_unicos():
    r = run(ctx_de([L(1, "P1", "X1", F(2)), L(2, "P1", "X2", F(2)), L(3, "P2", "X3", F(3))]), "R-REL-PAC-PED")
    assert r[0].estado == "error" and (ev(r[0], "C"), ev(r[0], "A"), ev(r[0], "pacientes_unicos"), ev(r[0], "universo_periodo")) == (1, 1, 1, 2)
    c = cod(r, "paciente_contradictorio")
    assert c.estado == "error" and c.severity == "warn" and c.evidencia["muestra_id_pedido"] == ["P1"]       # sigue en el universo de pedidos
    ok = run(ctx_de([L(1, "P1", "X1", F(2)), L(2, "P1", "X2", F(2))]), "R-REL-PAC-PED", max_pacientes_por_pedido=2)
    assert ok[0].estado == "valid" and cod(ok, "paciente_contradictorio") is None


def test_t01_fechas_contradictorias_dentro_del_periodo():
    r = run(ctx_de([L(1, "P1", "X1", F(3)), L(2, "P1", "X1", F(20)), L(3, "P2", "X2", F(4))]), "R-REL-PAC-PED")
    assert r[0].estado == "error" and ev(r[0], "clases", "C2") == 1 and ev(r[0], "universo_periodo") == 1
    assert cod(r, "fecha_contradictoria").evidencia["muestra_id_pedido"] == ["P1"]
    assert D(ev(r[0], "tasa_no_asignables")) == D("0.5") and ev(r[0], "no_asignables") == 1                    # F-06


def test_t01_fechas_contradictorias_fuera_del_periodo_no_alertan_ese_periodo():
    r = run(ctx_de([L(1, "P1", "X1", F(3, 3)), L(2, "P1", "X1", F(9, 4)), L(3, "P2", "X2", F(4))]), "R-REL-PAC-PED")
    assert r[0].estado == "valid" and cod(r, "fecha_contradictoria") is None and ev(r[0], "clases", "C2") == 1


def test_t01_pedido_con_fecha_ilegible_se_cuenta_aparte_y_las_identidades_cierran():
    r = run(ctx_de([L(1, "P1", "X1", None), L(2, "P2", "X2", F(3))]), "R-REL-PAC-PED")
    assert ev(r[0], "clases", "sin_fecha") == 1 and all(ev(r[0], "identidades").values())


def test_t01_registros_duplicados_se_informan_y_no_se_eliminan():
    lin = [L(1, "P1", "X1", F(2)), L(2, "P1", "X1", F(2)),                       # fila idéntica (duplicado exacto + línea repetida)
           L(3, "P2", "X2", F(3), monto="100"), L(4, "P2", "X2", F(3), monto="250")]   # mismo pedido y SKU con distinto importe
    ctx = ctx_de(lin)
    r = run(ctx, "R-REL-PAC-PED")
    assert cod(r, "duplicado_exacto").evidencia["n"] == 1 and cod(r, "linea_duplicada").evidencia["n"] == 2
    assert all(x.severity == "info" and x.estado == "warning" for x in (cod(r, "duplicado_exacto"), cod(r, "linea_duplicada")))
    assert len(ctx.lineas) == 4 and ev(r[0], "universo_periodo") == 2


def test_t01_identificadores_vacios():
    r = run(ctx_de([L(1, "", "X1", F(2)), L(2, "P2", "", F(3)), L(3, "P3", "X3", F(4))]), "R-REL-PAC-PED")
    assert r[0].estado == "error" and cod(r, "lineas_sin_id_pedido").evidencia["lineas"] == 1
    assert ev(r[0], "universo_periodo") == 2 and ev(r[0], "B") == 1                    # la línea sin id_pedido no se clasifica; sin paciente = B


def test_t01_periodo_sin_pedidos_es_not_verifiable_con_faltante():
    r = run(ctx_de([L(1, "P1", "X1", F(3, 5))]), "R-REL-PAC-PED")[0]
    assert r.estado == "not_verifiable" and r.faltante and r.valor is None


def test_t01_funciona_igual_en_aetops_y_no_inventa_estatus():
    r = run(ctx_de([L(1, "P1", "X1", F(3), estado="CANCELADO")], unidad="AETOPS"), "R-REL-PAC-PED")
    assert r[0].estado == "valid" and ev(r[0], "universo_periodo") == 1 and "C0" in ev(r[0], "clases_reservadas_inactivas")[0]
    assert cod(run(ctx_de([L(1, "P1", "X1", F(3))]), "R-REL-PAC-PED", estatus_excluidos=["CANCELADO"]), "estatus_no_disponible").estado == "warning"


def test_t01_la_regla_no_modifica_los_datos_originales():
    lin = [L(1, "P1", "X1", F(2)), L(2, "P1", "X2", F(2)), L(3, "", "X3", F(3))]
    ctx = ctx_de(lin)
    antes = [(ln.id_pedido, ln.id_paciente, ln.fecha, ln.monto, dict(ln.valores)) for ln in ctx.lineas]
    run(ctx, "R-REL-PAC-PED")
    assert antes == [(ln.id_pedido, ln.id_paciente, ln.fecha, ln.monto, dict(ln.valores)) for ln in ctx.lineas]


# =================================================================================== T-02 · R-CUADRE-DIM
def lin_dim():
    return [L(1, "P1", "X1", F(2), "S1", "WEB", sucursal="N", region="R1"), L(2, "P1", "X1", F(2), "S2", "WEB", sucursal="S", region="R1"),
            L(3, "P2", "X1", F(3), "S1", "TEL", sucursal="N", region="R1"), L(4, "P3", "X3", F(4), "S3", "WEB", sucursal="N", region="R2")]


def test_t02_dimension_exclusiva_no_genera_advertencia_pero_tampoco_se_da_por_demostrada():
    r = run(ctx_de(lin_dim()), "R-CUADRE-DIM")
    assert cod(r, "dimension_canal_pedido").estado == "not_verifiable" and cod(r, "dimension_region_pedido").estado == "not_verifiable"
    decl = {"canal": {"entidad": "pedido", "exclusiva": True, "exhaustiva": True, "justificacion": "prueba sintética"}}
    c = copy.deepcopy(config.cargar("reglas")); c["dimensiones"] = decl
    assert cod(motor.ejecutar(ctx_de(lin_dim()), ids=["R-CUADRE-DIM"], cfg=c), "dimension_canal_pedido").estado == "valid"


def test_t02_dimension_con_valores_compartidos_por_pedido():
    s = cod(run(ctx_de(lin_dim()), "R-CUADRE-DIM"), "dimension_sku_pedido")
    assert s.estado == "warning" and s.severity == "warn" and s.evidencia["suma_de_subtotales"] == 4 and s.evidencia["entidades_totales"] == 3
    assert "no sumar" in s.mensaje.lower() and s.evidencia["tratamiento"] == "no se filtra ni elimina ningún registro"


def test_t02_paciente_en_varios_canales_y_en_varias_sucursales():
    r = run(ctx_de(lin_dim(), unidad="AETOPS"), "R-CUADRE-DIM")
    assert cod(r, "dimension_canal_paciente").estado == "warning" and cod(r, "dimension_canal_paciente").evidencia["entidades_con_mas_de_un_valor"] == 1
    assert cod(r, "dimension_sucursal_paciente").estado == "warning" and cod(r, "dimension_sucursal_pedido").estado == "warning"


def test_t02_pedido_con_varias_categorias_via_catalogo():
    r = run(ctx_de(lin_dim()), "R-CUADRE-DIM")
    cat = cod(r, "dimension_categoria_pedido")
    assert cat.estado == "warning" and cat.evidencia["ejemplos"][0]["id"] == "P1" and cat.evidencia["ejemplos"][0]["valores"] == ["A", "B"]


def test_t02_el_resumen_advierte_que_hay_dimensiones_que_no_permiten_sumar_subtotales():
    r = run(ctx_de(lin_dim()), "R-CUADRE-DIM")[0]
    assert r.codigo == "cuadre_dimensiones" and r.estado == "warning" and "no pueden sumarse" in r.mensaje


def test_t02_no_elimina_datos_ni_altera_los_totales_originales():
    ctx = ctx_de(lin_dim())
    antes = (len(ctx.lineas), sorted(ctx.pedidos_sistema_ventas()), sum(ln.monto for ln in ctx.lineas))
    run(ctx, "R-CUADRE-DIM")
    assert antes == (len(ctx.lineas), sorted(ctx.pedidos_sistema_ventas()), sum(ln.monto for ln in ctx.lineas))


def test_t02_una_linea_sin_paciente_sigue_contando_para_la_entidad_pedido():
    """Defecto D-2B-01 (corregido): antes se descartaban las líneas sin id_paciente de todo el análisis."""
    lin = [L(1, "P1", "", F(2), "S1"), L(2, "P1", "", F(2), "S2"), L(3, "P2", "X2", F(3), "S1")]
    s = cod(run(ctx_de(lin), "R-CUADRE-DIM"), "dimension_sku_pedido")
    assert s.evidencia["entidades_totales"] == 2 and s.evidencia["entidades_con_mas_de_un_valor"] == 1
    assert cod(run(ctx_de(lin), "R-CUADRE-DIM"), "dimension_sku_paciente").evidencia["entidades_totales"] == 1


@pytest.mark.parametrize("dim,excl,exh,ok", [("canal", True, True, True), ("sku", True, True, False), ("canal", True, False, True),
                                            ("sku", True, False, False), ("sku", False, True, True), ("canal", False, True, True),
                                            ("sku", False, False, True), ("canal", False, False, True)])
def test_t02_cuatro_combinaciones_exclusiva_exhaustiva(dim, excl, exh, ok):
    c = copy.deepcopy(config.cargar("reglas"))
    c["dimensiones"] = {dim: {"entidad": "pedido", "exclusiva": excl, "exhaustiva": exh, "justificacion": "prueba"}}
    res = motor.ejecutar(ctx_de(lin_dim()), ids=["R-CUADRE-DIM"], cfg=c)
    assert cod(res, f"dimension_{dim}_pedido").estado == ("valid" if ok else "error")


def test_t02_tolerancia_configurable_y_columna_inexistente_y_periodo_vacio():
    c = copy.deepcopy(config.cargar("reglas"))
    c["dimensiones"] = {"sku": {"entidad": "pedido", "exclusiva": True, "exhaustiva": True, "justificacion": "prueba"}}     # suma 4 vs total 3
    assert cod(motor.ejecutar(ctx_de(lin_dim()), ids=["R-CUADRE-DIM"], cfg=c), "dimension_sku_pedido").estado == "error"
    assert cod(motor.ejecutar(ctx_de(lin_dim()), ids=["R-CUADRE-DIM"], cfg=c, overrides={"tolerancia_conteo": 1}), "dimension_sku_pedido").estado == "valid"
    sin_col = ctx_de(lin_dim(), columnas={"ventas": {"fecha_pedido", "id_pedido", "id_paciente", "sku", "canal"}, "catalogo": {"sku", "categoria"}})
    r = cod(run(sin_col, "R-CUADRE-DIM"), "dimension_estado")
    assert r.estado == "not_verifiable" and r.faltante
    assert run(ctx_de([L(1, "P1", "X1", F(3, 8))]), "R-CUADRE-DIM")[0].estado == "not_verifiable"


# =================================================================================== T-03 · R-CONC-COMPRAS
@pytest.mark.parametrize("compras,estado,signo", [(100, "valid", 0), (110, "valid", 1), (90, "valid", -1), (120, "valid", 1), (80, "valid", -1),
                                                 (130, "warning", 1), (70, "warning", -1), (121, "warning", 1), (79, "warning", -1)])
def test_t03_umbral_heredado_20_por_ciento_en_ambos_sentidos(compras, estado, signo):
    r = run(ctx_de(pedidos_n(100), trafico=tr(compras=compras)), "R-CONC-COMPRAS")[0]
    assert r.estado == estado and r.valor == D(compras - 100) / D(100)
    assert (r.valor > 0) - (r.valor < 0) == signo
    assert r.evidencia["pedidos_sistema_ventas"]["valor"] == 100 and r.evidencia["compras_ga4"]["valor"] == compras
    if estado == "warning":
        assert "no un error confirmado" in r.mensaje and r.severity == "warn"


def test_t03_las_fuentes_permanecen_separadas_nunca_se_suman_ni_se_sustituyen():
    r = run(ctx_de(pedidos_n(100), trafico=tr(compras=130)), "R-CONC-COMPRAS")[0]
    assert r.evidencia["pedidos_sistema_ventas"]["fuente"] == "sistema_ventas" and r.evidencia["compras_ga4"]["fuente"] == "ga4"
    assert "230" not in r.mensaje and r.valor != 230 and "no se sustituyen, no se suman" in r.evidencia["regla"]


def test_t03_periodos_incompatibles_y_fuente_faltante_no_se_completan():
    # trimestre con solo 2 de 3 meses de tráfico: el periodo del tráfico no coincide con el de ventas
    lin = [L(i, f"P{i}", f"X{i}", F(2, 1 + i % 3)) for i in range(1, 31)]
    parcial = {**tr(compras=10, mes=1), **tr(compras=10, mes=2)}
    r = run(ctx_de(lin, mes=1, tipo="trimestral", trafico=parcial), "R-CONC-COMPRAS")[0]
    assert r.estado == "not_verifiable" and r.valor is None and "2026-03" in r.mensaje + str(r.evidencia)
    completo = {**parcial, **tr(compras=10, mes=3)}
    assert run(ctx_de(lin, mes=1, tipo="trimestral", trafico=completo), "R-CONC-COMPRAS")[0].evidencia["compras_ga4"]["valor"] == 30
    otro_mes = run(ctx_de(pedidos_n(10), trafico=tr(mes=2)), "R-CONC-COMPRAS")[0]
    assert otro_mes.estado == "not_verifiable" and otro_mes.valor is None
    sin_hoja = motor.ejecutar(ctx_de(pedidos_n(10)), ids=["R-CONC-COMPRAS"])[0]
    assert sin_hoja.estado == "not_verifiable" and {"archivo": "trafico", "columna": "compras", "granularidad": None} in sin_hoja.faltante
    sin_valor = run(ctx_de(pedidos_n(10), trafico=tr(compras=None)), "R-CONC-COMPRAS")[0]
    assert sin_valor.estado == "not_verifiable" and sin_valor.valor is None


def test_t03_pedidos_cero_no_se_muestra_como_cero_por_ciento():
    r = run(ctx_de([], trafico=tr()), "R-CONC-COMPRAS")[0]
    assert r.estado == "not_verifiable" and r.valor is None


def test_t03_aplicabilidad_por_unidad_y_umbral_configurable():
    glp = run(ctx_de(pedidos_n(100), trafico=tr(compras=130)), "R-CONC-COMPRAS")[0]
    aet = run(ctx_de(pedidos_n(100), unidad="AETOPS", trafico=tr(compras=130)), "R-CONC-COMPRAS")[0]
    assert glp.estado == "warning" and aet.estado == "not_applicable" and "No aplica" in aet.mensaje and aet.valor is None
    assert run(ctx_de(pedidos_n(100), trafico=tr(compras=130)), "R-CONC-COMPRAS", umbral_conciliacion_compras=D("0.5"))[0].estado == "valid"
    assert run(ctx_de(pedidos_n(100), trafico=tr(compras=130)), "R-CONC-COMPRAS", umbral_conciliacion_compras=None)[0].estado == "not_verifiable"


# =================================================================================== T-04 · R-DENOM
def op(v, f="sistema_ventas", p="2026-01", g="mes"):
    return Operando(None if v is None else D(v), f, p, g, "x")


@pytest.mark.parametrize("num,den,estado,tiene_valor", [(5, 10, "valid", True), (5, 0, "not_verifiable", False), (5, -1, "error", False),
                                                        (5, None, "not_verifiable", False), (None, 10, "not_verifiable", False), (None, None, "not_verifiable", False),
                                                        (0, 10, "valid", True), (-5, 10, "error", False)])
def test_t04_denominador_y_numerador(num, den, estado, tiene_valor):
    e = evaluar_razon(Razon("r", "r", op(num), op(den), por_cien=True))
    assert e.estado == estado and (e.valor is not None) == tiene_valor
    if den in (0, None) or num is None:
        assert e.valor is None and e.problemas                          # nunca 0 %: queda sin valor y explica por qué
    if estado == "not_verifiable":
        assert e.faltante


def test_t04_periodos_granularidades_y_fuentes_distintos_advierten_sin_ocultar_el_valor():
    assert evaluar_razon(Razon("r", "r", op(5), op(10, p="2026-02"))).estado == "warning"
    assert evaluar_razon(Razon("r", "r", op(5), op(10, g="dia"))).estado == "warning"
    assert evaluar_razon(Razon("r", "r", op(5, "ga4"), op(10), (("sistema_ventas", "ga4"),))).estado == "warning"
    w = evaluar_razon(Razon("r", "r", op(5), op(10, p="2026-02")))
    assert w.valor == D("0.5") and "no equivalente temporalmente" in w.problemas[0]


def test_t04_como_regla_nunca_genera_un_porcentaje_enganoso_e_identifica_fuentes():
    res = motor.ejecutar(ctx_de(pedidos_n(10), trafico=tr(add=0, compras=5)), ids=["R-DENOM"])
    ind = cod(res, "razon_ind01_sistema_ventas")
    assert ind.estado == "not_verifiable" and ind.valor is None and "0 %" not in ind.mensaje.replace("No se muestra 0 %", "")
    assert "No se muestra 0 %" in ind.mensaje
    for r in res:
        assert r.evidencia["numerador"]["fuente"] and r.evidencia["denominador"]["fuente"] and r.evidencia["denominador"]["periodo"]
    sin = motor.ejecutar(ctx_de([]), ids=["R-DENOM"])
    assert sin[0].codigo == "razon_ticket" and sin[0].estado == "not_verifiable" and sin[0].valor is None


# =================================================================================== T-05 / T-10 · R-COBERTURA-ATC e IND-01
def ind(ped, add=1000, compras=130, unidad="eventos", **ov):
    if unidad:
        ov["unidad_carritos"] = unidad
    return run(ctx_de(pedidos_n(ped), trafico=tr(add=add, compras=compras)), "R-COBERTURA-ATC", **ov)


@pytest.mark.parametrize("ped,esperado", [(250, 25), (999, D("99.9")), (1000, 100), (1001, D("100.1")), (1200, 120)])
def test_t05_relacion_menor_igual_y_mayor_a_100_se_conserva(ped, esperado):
    r = ind(ped)[0]
    assert r.valor == D(esperado) and (r.estado, r.severity) == (("valid", "info") if ped <= 1000 else ("warning", "warn"))
    if ped > 1000:
        assert "mayor que 100" in r.mensaje and "puede ocurrir" in r.mensaje


def test_t05_t10_ejemplo_de_la_especificacion_250_de_1000():
    r = ind(250)[0]
    assert r.valor == D(25) and "Por cada 100 carritos agregados (eventos), se registran 25.00 pedidos del sistema de ventas" in r.mensaje
    assert "75" not in r.mensaje and "75" not in str(r.evidencia.get("relacion"))                  # sin complemento


def test_t05_carritos_cero_o_faltantes_no_calculables_nunca_cero():
    for kw in ({"add": 0}, {"add": None}):
        r = ind(250, **kw)[0]
        assert r.estado == "not_verifiable" and r.valor is None and r.faltante
    r = run(ctx_de(pedidos_n(5), trafico={}), "R-COBERTURA-ATC")[0]
    assert r.estado == "not_verifiable" and r.valor is None and "faltan meses" in r.evidencia["carritos_agregados"]["nombre"]
    sin_pedidos = run(ctx_de([], trafico=tr()), "R-COBERTURA-ATC", unidad_carritos="eventos")
    assert all(x.estado == "not_verifiable" or x.codigo.endswith("ga4_compras") for x in sin_pedidos)
    assert cod(sin_pedidos, "relacion_pedidos_carritos_sistema_ventas").valor is None                 # sin ventas válidas: faltante, no 0 %


def test_t05_unidad_no_declarada_se_comunica_y_no_se_llama_carritos_unicos():
    r = ind(250, unidad=None)[0]
    assert r.estado == "warning" and "unidad no declarada" in r.mensaje and r.severity == "info" and r.valor == D(25)
    for u in ("eventos", "otra: sesiones web"):
        assert "carritos únicos" not in ind(250, unidad=u)[0].mensaje.lower()
    assert "carritos únicos" not in r.mensaje.lower() and "únicos" not in r.mensaje


def test_t05_diferentes_fuentes_de_pedidos_son_resultados_independientes():
    res = ind(250, compras=300)
    assert codigos(res) == ["relacion_pedidos_carritos_sistema_ventas", "relacion_pedidos_carritos_ga4_compras"]
    assert (res[0].valor, res[1].valor) == (D(25), D(30))
    assert res[0].evidencia["numerador"]["fuente"] == "sistema_ventas" and res[1].evidencia["numerador"]["fuente"] == "ga4"
    assert "compras GA4" in res[1].mensaje and "pedidos del sistema de ventas" in res[0].mensaje
    assert ind(250, compras=300, fuente_pedidos="sistema_ventas")[0].valor == D(25) and len(ind(250, fuente_pedidos="sistema_ventas")) == 1


def test_t05_periodos_no_coincidentes():
    lin = [L(i, f"P{i}", f"X{i}", F(2, 1 + i % 3)) for i in range(1, 31)]
    r = run(ctx_de(lin, tipo="trimestral", trafico={**tr(mes=1), **tr(mes=2)}), "R-COBERTURA-ATC", unidad_carritos="eventos")
    assert all(x.estado == "not_verifiable" and x.valor is None for x in r)
    ok = run(ctx_de(lin, tipo="trimestral", trafico={**tr(add=100, compras=9, mes=1), **tr(add=100, compras=9, mes=2), **tr(add=100, compras=9, mes=3)}),
             "R-COBERTURA-ATC", unidad_carritos="eventos")
    assert cod(ok, "relacion_pedidos_carritos_sistema_ventas").valor == D(10) and ok[0].evidencia["periodo"] == "2026-01..03"
    # razón con periodos distintos (comparabilidad): se calcula pero se limita, nunca se presenta como equivalente
    e = evaluar_razon(Razon("r", "r", op(10), op(100, "ga4", p="2026-02"), por_cien=True))
    assert e.estado == "warning" and e.valor == D(10)


def test_t05_aplicabilidad_glp1_y_aetops():
    assert ind(250)[0].regla_id == "R-COBERTURA-ATC"
    a = run(ctx_de(pedidos_n(5), unidad="AETOPS"), "R-COBERTURA-ATC")[0]
    assert a.estado == "not_applicable" and a.valor is None and "No aplica" in a.mensaje


def test_t05_no_declara_abandono_ni_inventa_causas_ni_confunde_e2():
    from backend.app.narrative.rules import RULES
    textos = [r.mensaje for r in ind(1200, compras=1500, unidad=None)] + [r.mensaje for r in ind(250)]
    import re
    for t in textos:
        assert re.search(r"abandon|recuperaci[oó]n|causa[d]?o|bloqueador|duplicad", t, re.I) is None, t
    mayor = ind(1200)[0].mensaje
    assert "puede ocurrir porque pedidos y carritos no necesariamente representan unidades equivalentes, o porque sus fuentes, periodos, universos o filtros no coinciden" in mayor
    r = ind(250, unidad=None)[0]
    assert "carritos_abandonados" not in str(r.evidencia) and "E2" not in r.mensaje
    assert (RULES.recovery_scenario, RULES.cart_recovery_scenario) == (D("0.25"), D("0.10"))


def test_t10_filtro_de_canal_y_advertencia_si_hay_varios_canales():
    lin = [L(i, f"P{i}", f"X{i}", F(2), canal="WEB" if i <= 100 else "TEL") for i in range(1, 201)]
    c = ctx_de(lin, trafico=tr())
    sin = run(c, "R-COBERTURA-ATC", unidad_carritos="eventos")[0]
    assert sin.estado == "warning" and "2 canales sin filtro" in sin.mensaje
    con = run(c, "R-COBERTURA-ATC", unidad_carritos="eventos", filtro_canal_relacion="WEB")[0]
    assert con.estado == "valid" and con.valor == D(10)


# =================================================================================== T-21 · fuentes de pedidos diferenciadas
def test_t21_si_falta_una_fuente_no_se_sustituye_por_la_otra():
    # sin compras GA4: la relación con ventas se calcula y la de GA4 queda no calculable (no usa pedidos como compras)
    res = ind(250, compras=None)
    v, g = cod(res, "relacion_pedidos_carritos_sistema_ventas"), cod(res, "relacion_pedidos_carritos_ga4_compras")
    assert v.valor == D(25) and g.estado == "not_verifiable" and g.valor is None
    # sin pedidos del sistema de ventas: la relación con GA4 se calcula y la de ventas queda no calculable
    res = run(ctx_de([], trafico=tr(compras=300)), "R-COBERTURA-ATC", unidad_carritos="eventos")
    assert cod(res, "relacion_pedidos_carritos_ga4_compras").valor == D(30) and cod(res, "relacion_pedidos_carritos_sistema_ventas").valor is None


def test_t21_no_se_suman_ni_se_presentan_como_equivalentes_en_ningun_resultado():
    ctx = ctx_de(pedidos_n(100), trafico=tr(compras=130))
    res = motor.ejecutar(ctx)
    for r in res:
        assert D(230) != r.valor and "230" not in r.mensaje
        assert "equivalentes" not in r.mensaje.replace("no necesariamente representan unidades equivalentes", "")
    conc = cod(res, "conciliacion_compras")
    assert conc.evidencia["pedidos_sistema_ventas"]["fuente"] != conc.evidencia["compras_ga4"]["fuente"]
    assert cod(res, "razon_brecha_compras").evidencia["numerador"]["fuente"] == "ga4-sistema_ventas"


def test_t21_cada_cifra_identifica_su_fuente_en_todas_las_reglas_con_dos_fuentes():
    res = motor.ejecutar(ctx_de(pedidos_n(100), trafico=tr(compras=130)), ids=["R-CONC-COMPRAS", "R-DENOM", "R-COBERTURA-ATC"])
    for r in res:
        txt = str(r.evidencia)
        assert "sistema_ventas" in txt or "ga4" in txt, r.id
