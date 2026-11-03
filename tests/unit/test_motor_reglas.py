"""Motor de reglas (Fase 2A): pruebas de humo y de comportamiento clave sobre contextos sintéticos y los machotes.

NO son las pruebas exhaustivas de la Fase 2B: cubren que el motor, el catálogo y las cinco reglas se comportan según la
especificación en los casos principales. Los contextos sintéticos no usan datos reales.
"""
from __future__ import annotations

import copy
import datetime as dt
import re
from decimal import Decimal
from pathlib import Path

import pytest

from backend.app import config
from backend.app.models import Finding, Period
from backend.app.validator import motor, operandos
from backend.app.validator.motor import Operando, Razon, Resultado, evaluar_razon
from backend.app.validator.normalizar import Contexto, Linea

D = Decimal
EJEMPLOS = Path(__file__).resolve().parents[2] / "data" / "ejemplos"


def L(i, ped, pac, fecha, sku="S1", canal="WEB", monto="100", **extra):
    v = {"id_pedido": ped, "id_paciente": pac, "fecha_pedido": str(fecha), "sku": sku, "canal": canal, "monto_venta": monto, "piezas": "1"} | extra
    return Linea(i, ped, pac, fecha, sku, D(monto), D(1), v)


COLS_V = {"fecha_pedido", "id_pedido", "id_paciente", "paciente_nuevo", "sku", "canal", "estado", "piezas", "monto_venta"}
CAT = {"S1": {"sku": "S1", "categoria": "A"}, "S2": {"sku": "S2", "categoria": "B"}}


def ctx_de(lineas, unidad="GLP1", mes=1, trafico=None, columnas=None, cat=None):
    c = Contexto(unidad, Period(unidad, "mensual", 2026, mes), "sintetico.xlsx")
    c.columnas = columnas if columnas is not None else {"ventas": set(COLS_V), "catalogo": {"sku", "producto", "categoria"}}
    c.lineas, c.catalogo = lineas, CAT if cat is None else cat
    if trafico is not None:
        c.columnas["trafico"] = {"mes", "vista", "valor", "sku", "visitas", "add_to_cart", "compras"}
        c.trafico_sitio = trafico
    return c


def ene(d):
    return dt.date(2026, 1, d)


def ejemplo_spec():
    """Ejemplo de §3.3 (6 pedidos, enero)."""
    return [L(1, "P-001", "X1", ene(5)), L(2, "P-001", "X1", ene(5), "S2"), L(3, "P-001", "X1", ene(5), "S3"),
            L(4, "P-002", "X2", ene(7)), L(5, "P-002", "X2", ene(7)),                                     # dos filas idénticas
            L(6, "P-003", "X1", ene(9)), L(7, "P-003", "X3", ene(9)),
            L(8, "P-004", "X4", ene(28)), L(9, "P-004", "X4", dt.date(2026, 2, 2)),
            L(10, "P-005", "", ene(12)),
            L(11, "P-006", "X1", ene(20))]


def por_codigo(res, codigo):
    return next((r for r in res if r.codigo == codigo), None)


# ------------------------------------------------------------------------------------------------ catálogo y motor
def test_el_catalogo_de_reglas_es_valido_y_tiene_las_cinco_reglas():
    assert config.validar("reglas", config.cargar("reglas")) == []
    assert list(motor.catalogo()) == list(config.REGLAS_FASE1)
    for d in motor.catalogo().values():
        assert d.validacion == motor.ESTADO_VALIDACION == "not_validated_with_real_data"


@pytest.mark.parametrize("cambio,fragmento", [
    (lambda c: c["reglas"].append(copy.deepcopy(c["reglas"][0])), "duplicada"),
    (lambda c: c["reglas"][0]["parametros"].append("inventado"), "no existe en reglas.parametros"),
    (lambda c: c["reglas"][0]["activacion"].update(flag="otro"), "flag"),
    (lambda c: c["reglas"][0]["severidad"].update(valid="grave"), "valores válidos"),
    (lambda c: c["reglas"][0].update(version="uno"), "MAJOR.MINOR.PATCH"),
    (lambda c: c["reglas"][0]["unidades"].append("OTRA"), "unidades"),
])
def test_un_catalogo_de_reglas_invalido_se_rechaza(cambio, fragmento):
    c = copy.deepcopy(config.cargar("reglas"))
    cambio(c)
    assert any(fragmento in e for e in config.validar("reglas", c)), config.validar("reglas", c)


def test_los_valores_heredados_se_conservan_y_no_hay_parametros_nuevos_de_negocio():
    p = config.cargar("reglas")["parametros"]
    assert (p["e1_recuperacion_negados_medio"]["valor"], p["e2_recuperacion_abandono_medio"]["valor"],
            p["umbral_conciliacion_compras"]["valor"]) == (D("0.25"), D("0.1"), D("0.2"))


def test_los_estados_son_los_documentados():
    assert motor.ESTADOS == ("valid", "warning", "error", "not_verifiable", "not_applicable")
    assert "not_validated_with_real_data" in motor.ESTADOS_COMPLETOS


def test_not_verifiable_exige_faltante_y_los_estados_se_validan():
    with pytest.raises(ValueError):
        Resultado("R", "1.0.0", "c", "not_verifiable", "info", "m")
    with pytest.raises(ValueError):
        Resultado("R", "1.0.0", "c", "raro", "info", "m")
    with pytest.raises(ValueError):
        Resultado("R", "1.0.0", "c", "valid", "grave", "m")


def test_ejecutar_no_modifica_el_contexto_y_es_reproducible():
    c = ctx_de(ejemplo_spec())
    antes = (len(c.lineas), list(c.lineas), copy.deepcopy(c.columnas))
    a, b = motor.ejecutar(c), motor.ejecutar(c)
    assert [r.to_dict() for r in a] == [r.to_dict() for r in b]
    assert (len(c.lineas), list(c.lineas), c.columnas) == antes


def test_un_fallo_interno_se_muestra_como_error_no_se_oculta(monkeypatch):
    def boom(ctx, d):
        raise RuntimeError("falla simulada")
    monkeypatch.setitem(motor.FUNCIONES, "R-DENOM", boom)
    res = motor.ejecutar(ctx_de(ejemplo_spec()), ids=["R-DENOM"])
    assert res[0].estado == "error" and res[0].codigo == "fallo_interno" and "falla simulada" in res[0].mensaje


def test_columnas_requeridas_ausentes_son_not_verifiable_con_faltante():
    c = ctx_de(ejemplo_spec(), columnas={"ventas": {"id_pedido", "fecha_pedido"}})
    r = motor.ejecutar(c, ids=["R-REL-PAC-PED"])[0]
    assert r.estado == "not_verifiable" and {"archivo": "ventas", "columna": "id_paciente", "granularidad": None} in r.faltante


def test_a_hallazgos_usa_severity_heredado_sin_bloquear_y_llena_los_campos_de_fase1():
    res = motor.ejecutar(ctx_de(ejemplo_spec()))
    hs = motor.a_hallazgos(res)
    assert hs and all(isinstance(h, Finding) and h.severity in ("warn", "info") for h in hs)         # nunca 'block'
    assert not any(r.severity == "block" for r in res)
    h = next(h for h in hs if h.id.endswith("paciente_contradictorio"))
    assert (h.regla_id, h.regla_version, h.efecto_generacion, h.estado_verificacion) == ("R-REL-PAC-PED", "1.0.0", "advertir", "inconsistente")
    nv = next(h for h in motor.a_hallazgos(motor.ejecutar(ctx_de(ejemplo_spec(), "AETOPS"))) if h.id.startswith("R-CONC"))
    assert nv.severity == "info" and nv.efecto_generacion == "informar"
    assert all(h.estado_verificacion in ("inconsistente", "supuesto", "verificado", "no_verificable", None) for h in hs)
    assert not any(h.id.endswith("cobertura_paciente") and h.estado_verificacion == "supuesto" for h in hs)     # observación aritmética: verificada


# ------------------------------------------------------------------------------------------------ R-REL-PAC-PED
def test_rel_pac_ped_ejemplo_de_la_especificacion():
    res = motor.ejecutar(ctx_de(ejemplo_spec()), ids=["R-REL-PAC-PED"])
    g = res[0]
    assert g.estado == "error" and g.evidencia["clases"] == {"C0": 0, "C1": 0, "C2": 1, "sin_fecha": 0, "E": 5}
    assert (g.evidencia["universo_periodo"], g.evidencia["A"], g.evidencia["B"], g.evidencia["C"], g.evidencia["pacientes_unicos"]) == (5, 3, 1, 1, 2)
    assert D(g.evidencia["cobertura_paciente"]) == D("0.6") and D(g.evidencia["razon_recurrencia"]) == D("1.5")
    assert all(g.evidencia["identidades"].values()) and g.evidencia["pedidos_archivo"] == 6
    codigos = [r.codigo for r in res]
    assert {"paciente_contradictorio", "fecha_contradictoria", "duplicado_exacto", "cobertura_paciente"} <= set(codigos)
    assert por_codigo(res, "paciente_contradictorio").estado == "error" and por_codigo(res, "paciente_contradictorio").evidencia["muestra_id_pedido"] == ["P-003"]
    assert por_codigo(res, "duplicado_exacto").severity == "info" and por_codigo(res, "duplicado_exacto").evidencia["n"] == 1
    assert por_codigo(res, "cobertura_paciente").estado == "warning"
    assert "C0 (excluido por estatus)" in g.evidencia["clases_reservadas_inactivas"][0]


def test_rel_pac_ped_con_dos_pacientes_permitidos_por_pedido():
    res = motor.ejecutar(ctx_de(ejemplo_spec()), ids=["R-REL-PAC-PED"], overrides={"max_pacientes_por_pedido": 2})
    g = res[0]
    assert (g.evidencia["A"], g.evidencia["C"], g.evidencia["pacientes_unicos"]) == (4, 0, 3) and D(g.evidencia["cobertura_paciente"]) == D("0.8")
    assert por_codigo(res, "paciente_contradictorio") is None and por_codigo(res, "fecha_contradictoria") is not None


def test_rel_pac_ped_valido_y_pedidos_con_varias_lineas_y_pacientes_recurrentes_no_alertan():
    lin = [L(1, "A", "X1", ene(3)), L(2, "A", "X1", ene(3), "S2"), L(3, "B", "X1", ene(9)), L(4, "C", "X2", ene(10))]
    res = motor.ejecutar(ctx_de(lin), ids=["R-REL-PAC-PED"])
    assert res[0].estado == "valid" and res[0].evidencia["pacientes_unicos"] == 2 and res[0].evidencia["universo_periodo"] == 3
    assert [r.estado for r in res if r.codigo != "relacion_paciente_pedido"] == ["valid"]


def test_rel_pac_ped_no_inventa_estatus_y_el_campo_estado_no_es_un_estatus():
    lin = [L(1, "A", "X1", ene(3), estado="CANCELADO"), L(2, "B", "X2", ene(4), estado="JALISCO")]
    res = motor.ejecutar(ctx_de(lin), ids=["R-REL-PAC-PED"])
    assert res[0].estado == "valid" and res[0].evidencia["universo_periodo"] == 2                      # «estado» no excluye nada
    res = motor.ejecutar(ctx_de(lin), ids=["R-REL-PAC-PED"], overrides={"estatus_excluidos": ["CANCELADO"]})
    assert por_codigo(res, "estatus_no_disponible").estado == "warning" and res[0].evidencia["universo_periodo"] == 2


def test_rel_pac_ped_sin_pedidos_en_el_periodo_es_not_verifiable():
    r = motor.ejecutar(ctx_de([L(1, "A", "X", dt.date(2025, 5, 1))]), ids=["R-REL-PAC-PED"])[0]
    assert r.estado == "not_verifiable" and r.faltante


# ------------------------------------------------------------------------------------------------ R-CUADRE-DIM
def lin_cuadre():
    # canal exclusivo por pedido; sku NO exclusivo para el pedido P1 (dos SKU)
    return [L(1, "P1", "X1", ene(2), "S1", "WEB"), L(2, "P1", "X1", ene(2), "S2", "WEB"), L(3, "P2", "X2", ene(3), "S1", "TEL")]


def cfg_con_dims(**dims):
    c = copy.deepcopy(config.cargar("reglas"))
    c["dimensiones"] = dims
    return c


def test_cuadre_detecta_dimension_no_exclusiva_sin_declaracion_y_no_elimina_registros():
    c = ctx_de(lin_cuadre())
    n = len(c.lineas)
    res = motor.ejecutar(c, ids=["R-CUADRE-DIM"])
    sku = por_codigo(res, "dimension_sku_pedido")
    assert sku.estado == "warning" and sku.severity == "warn" and "no sumar" in sku.mensaje.lower()
    assert sku.evidencia["suma_de_subtotales"] == 3 and sku.evidencia["entidades_totales"] == 2 and sku.evidencia["entidades_con_mas_de_un_valor"] == 1
    canal = por_codigo(res, "dimension_canal_pedido")
    assert canal.estado == "not_verifiable" and canal.faltante                                            # sin solapamiento observado ≠ exclusiva demostrada
    assert res[0].codigo == "cuadre_dimensiones" and res[0].estado == "warning" and len(c.lineas) == n


@pytest.mark.parametrize("dim,excl,exh,ok", [("canal", True, True, True), ("sku", True, True, False), ("canal", True, False, True),
                                            ("sku", True, False, False), ("sku", False, True, True), ("sku", False, False, True)])
def test_cuadre_combinaciones_de_dimensiones_declaradas(dim, excl, exh, ok):
    # canal: suma = total (2 = 2). sku: suma 3 > total 2. Condición por combinación: SÍ/SÍ suma = total; SÍ/NO suma ≤ total;
    # NO/SÍ suma ≥ total; NO/NO sin relación exigible.
    cfg = cfg_con_dims(**{dim: {"entidad": "pedido", "exclusiva": excl, "exhaustiva": exh, "justificacion": "prueba sintética"}})
    res = motor.ejecutar(ctx_de(lin_cuadre()), ids=["R-CUADRE-DIM"], cfg=cfg)
    r = por_codigo(res, f"dimension_{dim}_pedido")
    assert r.estado == ("valid" if ok else "error"), (dim, excl, exh, r.mensaje)
    assert (res[0].estado == "error") == (not ok)


def test_cuadre_sin_asignar_es_una_categoria_virtual_solo_si_la_dimension_es_exhaustiva():
    lin = lin_cuadre() + [L(9, "P3", "X3", ene(4), "S1", "")]                      # P3 sin canal
    ee = cfg_con_dims(canal={"entidad": "pedido", "exclusiva": True, "exhaustiva": True, "justificacion": "prueba"})
    r = por_codigo(motor.ejecutar(ctx_de(lin), ids=["R-CUADRE-DIM"], cfg=ee), "dimension_canal_pedido")
    assert r.estado == "valid" and r.evidencia["sin_categoria"] == 1 and r.evidencia["suma"] == 3 == r.evidencia["total"]
    en = cfg_con_dims(canal={"entidad": "pedido", "exclusiva": True, "exhaustiva": False, "justificacion": "prueba"})
    r = por_codigo(motor.ejecutar(ctx_de(lin), ids=["R-CUADRE-DIM"], cfg=en), "dimension_canal_pedido")
    assert r.estado == "valid" and r.evidencia["suma"] == 2 and r.evidencia["total"] == 3                      # suma ≤ total


def test_cuadre_sin_columna_de_la_dimension_es_not_verifiable_no_se_inventa():
    c = ctx_de(lin_cuadre())            # el contexto no tiene la columna `region`/`sucursal`
    res = motor.ejecutar(c, ids=["R-CUADRE-DIM"])
    assert por_codigo(res, "dimension_region") is not None and por_codigo(res, "dimension_region").estado == "not_verifiable"


# ------------------------------------------------------------------------------------------------ R-CONC-COMPRAS
def tr(add=1000, compras=130, mes=1):
    return {(2026, mes): {"add_to_cart": D(add) if add is not None else None, "compras": D(compras) if compras is not None else None, "visitas": D(1)}}


def pedidos_n(n):
    return [L(i, f"P{i}", f"X{i}", ene(2)) for i in range(1, n + 1)]


@pytest.mark.parametrize("compras,estado", [(130, "warning"), (110, "valid"), (120, "valid"), (121, "warning"), (79, "warning"), (80, "valid")])
def test_conc_compras_umbral_heredado_20_por_ciento_estricto(compras, estado):
    r = motor.ejecutar(ctx_de(pedidos_n(100), trafico=tr(compras=compras)), ids=["R-CONC-COMPRAS"])[0]
    assert r.estado == estado
    assert {"pedidos_sistema_ventas", "compras_ga4"} <= set(r.evidencia) and r.evidencia["pedidos_sistema_ventas"]["fuente"] == "sistema_ventas"
    assert r.evidencia["compras_ga4"]["fuente"] == "ga4"
    if estado == "warning":
        assert "no un error confirmado" in r.mensaje and "fuentes distintas" in r.mensaje and r.severity == "warn"
        assert r.evidencia["hipotesis_a_validar"]


def test_conc_compras_no_aplica_a_aetops_y_no_se_inventa_si_faltan_datos():
    assert motor.ejecutar(ctx_de(pedidos_n(3), "AETOPS"), ids=["R-CONC-COMPRAS"])[0].estado == "not_applicable"
    assert "trafico" in motor.ejecutar(ctx_de(pedidos_n(3), "AETOPS"), ids=["R-CONC-COMPRAS"])[0].mensaje
    r = motor.ejecutar(ctx_de(pedidos_n(100), trafico={}), ids=["R-CONC-COMPRAS"])[0]
    assert r.estado == "not_verifiable" and r.valor is None                                                   # no sustituye una fuente por otra
    r = motor.ejecutar(ctx_de([], trafico=tr()), ids=["R-CONC-COMPRAS"])[0]
    assert r.estado == "not_verifiable" and r.valor is None                                                   # sin pedidos: no es 0 %


# ------------------------------------------------------------------------------------------------ R-DENOM
def op(v, f="sistema_ventas", p="2026-01", g="mes"):
    return Operando(None if v is None else D(v), f, p, g, "x")


def test_denom_nunca_convierte_denominador_cero_o_inexistente_en_cero_por_ciento():
    assert evaluar_razon(Razon("r", "r", op(5), op(0))).valor is None and evaluar_razon(Razon("r", "r", op(5), op(0))).estado == "not_verifiable"
    e = evaluar_razon(Razon("r", "r", op(5), op(None)))
    assert e.estado == "not_verifiable" and e.valor is None and e.faltante
    e = evaluar_razon(Razon("r", "r", op(None), op(5)))
    assert e.estado == "not_verifiable" and e.valor is None
    assert evaluar_razon(Razon("r", "r", op(0), op(5))).valor == 0 and evaluar_razon(Razon("r", "r", op(0), op(5))).estado == "valid"   # numerador 0 sí es 0


def test_denom_negativos_periodos_granularidad_y_fuentes():
    assert evaluar_razon(Razon("r", "r", op(5), op(-1))).estado == "error"
    assert evaluar_razon(Razon("r", "r", op(5), op(-1), permite_negativo=True)).estado == "valid"
    e = evaluar_razon(Razon("r", "r", op(5), op(10, p="2026-02")))
    assert e.estado == "warning" and e.valor == D("0.5") and "no equivalente temporalmente" in e.problemas[0]
    assert "granularidades" in evaluar_razon(Razon("r", "r", op(5), op(10, g="dia"))).problemas[0]
    e = evaluar_razon(Razon("r", "r", op(5, "ga4"), op(10), (("sistema_ventas", "ga4"),)))
    assert e.estado == "warning" and "fuentes" in e.problemas[0]
    assert evaluar_razon(Razon("r", "r", op(25), op(100), por_cien=True)).valor == D(25)


def test_denom_como_regla_identifica_numerador_denominador_y_fuentes():
    res = motor.ejecutar(ctx_de(pedidos_n(100), trafico=tr(compras=110)), ids=["R-DENOM"])
    assert {r.codigo for r in res} == {"razon_ticket", "razon_ind01_sistema_ventas", "razon_ind01_ga4", "razon_brecha_compras"}
    for r in res:
        assert r.evidencia["numerador"]["fuente"] and r.evidencia["denominador"]["fuente"] and r.evidencia["denominador"]["periodo"]
    assert [r.codigo for r in motor.ejecutar(ctx_de(pedidos_n(3), "AETOPS"), ids=["R-DENOM"])] == ["razon_ticket"]
    sin = motor.ejecutar(ctx_de([L(1, "P1", "X", dt.date(2025, 1, 1))]), ids=["R-DENOM"])[0]
    assert sin.estado == "not_verifiable" and sin.valor is None                                               # ticket sin pedidos: no es 0


# ------------------------------------------------------------------------------------------------ R-COBERTURA-ATC / IND-01
def ind(ped, add=1000, compras=130, over=None, unidad=None):
    cfg = None
    ov = dict(over or {})
    if unidad:
        ov["unidad_carritos"] = unidad
    return motor.ejecutar(ctx_de(pedidos_n(ped), trafico=tr(add=add, compras=compras)), ids=["R-COBERTURA-ATC"], overrides=ov)


def test_ind01_ejemplo_250_de_1000_es_25_por_ciento_exacto_y_unidad_no_declarada():
    r = ind(250)[0]
    assert r.valor == D(25) and r.estado == "warning" and r.severity == "info"
    assert "unidad no declarada" in r.mensaje and r.evidencia["carritos_agregados"]["unidad"] == "unidad no declarada"
    assert "Por cada 100 carritos agregados" in r.mensaje and "25.00" in r.mensaje
    assert re.search(r"abandon", r.mensaje, re.I) is None and "75" not in r.mensaje                           # sin complemento ni «abandono»
    assert "complemento" in r.evidencia["naturaleza"]


def test_ind01_con_unidad_declarada_y_sin_otras_limitaciones_es_valido():
    r = ind(250, unidad="eventos")[0]
    assert r.estado == "valid" and r.valor == D(25) and r.evidencia["estado_ind01"] == "calculable"
    assert ind(250, unidad="otra: sesiones web")[0].evidencia["carritos_agregados"]["unidad"] == "sesiones web"
    assert "no reconocido" in ind(250, unidad="cosas")[0].evidencia["limitaciones"][0]


def test_ind01_dos_fuentes_son_resultados_independientes_y_la_fuente_es_configurable():
    res = ind(250, compras=300)
    assert [r.codigo for r in res] == ["relacion_pedidos_carritos_sistema_ventas", "relacion_pedidos_carritos_ga4_compras"]
    assert (res[0].valor, res[1].valor) == (D(25), D(30)) and res[0].evidencia["fuente_pedidos"] != res[1].evidencia["fuente_pedidos"]
    uno = ind(250, compras=300, over={"fuente_pedidos": "ga4_compras"})
    assert len(uno) == 1 and uno[0].valor == D(30) and "compras GA4" in uno[0].mensaje
    inv = ind(250, over={"fuente_pedidos": "otra"})[0]
    assert inv.estado == "error" and inv.codigo == "configuracion_invalida"


def test_ind01_mayor_a_100_se_conserva_con_advertencia_sin_causa_inventada():
    r = ind(1200)[0]
    assert r.valor == D(120) and r.estado == "warning" and r.severity == "warn"
    assert "mayor que 100" in r.mensaje and "puede ocurrir" in r.mensaje and "unidades equivalentes" in r.mensaje
    assert re.search(r"error|abandon|causa", r.mensaje, re.I) is None


def test_ind01_faltantes_y_carritos_cero_son_no_calculables_nunca_cero():
    r = ind(250, add=0)[0]
    assert r.estado == "not_verifiable" and r.valor is None and r.faltante
    r = ind(250, add=None)[0]
    assert r.estado == "not_verifiable" and r.valor is None
    r = motor.ejecutar(ctx_de(pedidos_n(5), trafico={}), ids=["R-COBERTURA-ATC"])[0]
    assert r.estado == "not_verifiable" and r.valor is None and "faltan meses" in r.evidencia["problemas"][0] or r.faltante
    assert motor.ejecutar(ctx_de(pedidos_n(5), "AETOPS"), ids=["R-COBERTURA-ATC"])[0].estado == "not_applicable"


def test_ind01_no_usa_desgloses_ni_identificadores_de_carrito():
    c = ctx_de(pedidos_n(250), trafico=tr())
    assert operandos.carritos_agregados(c).nombre.startswith("trafico.add_to_cart (nivel sitio)")
    texto = Path(operandos.__file__).read_text(encoding="utf-8") + Path(motor.__file__).read_text(encoding="utf-8")
    assert not re.search(r"id_carrito|cart_id|transaction", texto, re.I)


def test_ind01_filtro_de_canal_configurable_y_advertencia_si_hay_varios_canales():
    lin = [L(i, f"P{i}", f"X{i}", ene(2), canal="WEB" if i <= 100 else "TEL") for i in range(1, 201)]
    c = ctx_de(lin, trafico=tr())
    r = motor.ejecutar(c, ids=["R-COBERTURA-ATC"], overrides={"unidad_carritos": "eventos"})[0]
    assert r.estado == "warning" and "2 canales sin filtro" in r.mensaje and r.valor == D(20)
    r = motor.ejecutar(c, ids=["R-COBERTURA-ATC"], overrides={"unidad_carritos": "eventos", "filtro_canal_relacion": "WEB"})[0]
    assert r.estado == "valid" and r.valor == D(10)


# ------------------------------------------------------------------------------------------------ machotes sintéticos
@pytest.mark.skipif(not (EJEMPLOS / "GLP1_crudo_ejemplo.xlsx").exists(), reason="machote no disponible")
def test_machote_glp1_sept_2026_cifras_y_estados():
    from backend.app.validator.normalizar import construir_contexto
    res = motor.ejecutar(construir_contexto(EJEMPLOS / "GLP1_crudo_ejemplo.xlsx", Period("GLP1", "mensual", 2026, 9)))
    conc = por_codigo(res, "conciliacion_compras")
    assert (conc.evidencia["pedidos_sistema_ventas"]["valor"], conc.evidencia["compras_ga4"]["valor"]) == (D(2356), D(2643)) and conc.estado == "valid"
    v, g = por_codigo(res, "relacion_pedidos_carritos_sistema_ventas"), por_codigo(res, "relacion_pedidos_carritos_ga4_compras")
    assert (round(v.valor, 2), round(g.valor, 2)) == (D("12.48"), D("14.00")) and v.evidencia["carritos_agregados"]["valor"] == D(18883)
    assert por_codigo(res, "relacion_paciente_pedido").estado == "valid" and por_codigo(res, "dimension_sku_pedido").estado == "warning"
    assert all(r.estado_validacion == "not_validated_with_real_data" and r.severity != "block" for r in res)


@pytest.mark.skipif(not (EJEMPLOS / "AETOPS_crudo_ejemplo.xlsx").exists(), reason="machote no disponible")
def test_machote_aetops_sept_2026_no_exige_trafico():
    from backend.app.validator.normalizar import construir_contexto
    res = motor.ejecutar(construir_contexto(EJEMPLOS / "AETOPS_crudo_ejemplo.xlsx", Period("AETOPS", "mensual", 2026, 9)))
    assert {r.regla_id for r in res if r.estado == "not_applicable"} == {"R-CONC-COMPRAS", "R-COBERTURA-ATC"}
    assert por_codigo(res, "relacion_paciente_pedido").evidencia["universo_periodo"] == 1436
    assert por_codigo(res, "dimension_sucursal_pedido").estado == "warning" and por_codigo(res, "dimension_canal_pedido").estado == "not_verifiable"
