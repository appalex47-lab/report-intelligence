"""Catálogo de definiciones y contratos de configuración (Fase 1 · 6.3, 6.4, 6.6)."""
from __future__ import annotations

import copy
import json
from decimal import Decimal
from pathlib import Path

import pytest

from backend.app import config
from backend.app.version import versiones

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "fase1"
OBLIGATORIOS = ("id", "nombre", "descripcion", "version", "tipo", "unidad", "fuente", "granularidad", "aplicabilidad",
                "limitaciones", "origen", "validacion_operacional", "referencia")


def _fx(name):
    return json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("nombre", sorted(config.ARCHIVOS))
def test_los_archivos_se_leen_y_cumplen_su_esquema(nombre):
    datos = config.cargar(nombre)
    assert config.validar(nombre, datos) == []
    assert datos["esquema"] == config.ESQUEMAS[nombre]


def test_versiones_identificadas():
    v = config.versiones()
    assert set(v) == set(config.ARCHIVOS) and all(config.SEMVER.match(x) for x in v.values())
    assert versiones()["configuracion"] == v
    assert versiones()["app"] == "1.0.0" and versiones()["motor"] == "1.0.0"   # Fase 3A-1: primera versión formalmente identificada


def test_catalogo_real_campos_obligatorios_y_ids_unicos():
    cat = config.cargar("definiciones")
    ids = [e["id"] for e in cat["definiciones"]]
    assert len(ids) == len(set(ids)) >= 9
    for e in cat["definiciones"]:
        assert all(k in e for k in OBLIGATORIOS), e["id"]
        assert e["validacion_operacional"] == "no_validada_con_datos_reales"


def test_el_catalogo_solo_referencia_columnas_que_existen_en_los_machotes():
    """Cada fuente citada (hoja.columna) existe en los encabezados reales documentados de los machotes."""
    cols = {"ventas": {"fecha_pedido", "id_pedido", "id_paciente", "paciente_nuevo", "sku", "canal", "estado", "sucursal",
                       "region", "piezas", "monto_venta", "forma_pago", "modo_entrega", "programa_lealtad"},
            "catalogo": {"sku", "producto", "linea", "categoria", "laboratorio"},
            "trafico": {"mes", "vista", "valor", "sku", "visitas", "usuarios", "usuarios_nuevos", "usuarios_recurrentes",
                        "vistas_producto", "add_to_cart", "begin_checkout", "compras", "carritos_abandonados",
                        "sesiones_rebote", "segundos_interaccion_total"},
            "negados": {"producto", "sku", "alta", "pedidos", "cantidad_negada", "monto_negado"}}
    for e in config.cargar("definiciones")["definiciones"]:
        fu = e["fuente"]
        for f in ([fu] if isinstance(fu, dict) else (fu or [])):
            assert f["columna"] in cols[f["hoja"]], (e["id"], f)
        if "AETOPS" in e["aplicabilidad"]["unidades"]:
            assert all(f["hoja"] != "trafico" for f in ([fu] if isinstance(fu, dict) else fu)), e["id"]   # AETOPS no tiene tráfico


def test_los_ids_del_catalogo_se_consultan_y_una_definicion_inexistente_se_detecta():
    idx = config.indice_definiciones(config.cargar("definiciones"))
    assert idx["relacion_pedidos_carritos"]["tipo"] == "indicador"
    with pytest.raises(KeyError):
        idx["no_existe"]


def test_unidad_de_carritos_no_declarada_no_se_inventa():
    d = config.indice_definiciones(config.cargar("definiciones"))
    assert d["carritos_agregados"]["unidad"] is None
    assert config.cargar("reglas")["parametros"]["unidad_carritos"]["valor"] == "no_declarada"


@pytest.mark.parametrize("fx,fragmento", [("catalogo_id_duplicado", "duplicado"), ("catalogo_campo_faltante", "descripcion"),
                                           ("catalogo_version_invalida", "MAJOR.MINOR.PATCH"), ("catalogo_unidad_invalida", "unidades")])
def test_catalogos_invalidos_se_rechazan(fx, fragmento):
    errs = config.validar("definiciones", _fx(fx))
    assert errs and any(fragmento in e for e in errs), errs


def test_catalogo_sintetico_valido_pasa():
    assert config.validar("definiciones", _fx("catalogo_valido")) == []


def test_un_valor_no_configurado_no_se_convierte_en_valor():
    p = config.cargar("reglas")["parametros"]
    sin = [k for k, v in p.items() if v["origen"] == "no_configurado"]
    assert {"e1_recuperacion_negados_conservador", "e2_recuperacion_abandono_optimista", "estatus_excluidos",
            "cobertura_minima_paciente", "fuente_pedidos", "filtro_canal_relacion"} <= set(sin)
    assert all(p[k]["valor"] is None for k in sin)
    # un valor inventado para un parámetro 'no_configurado' se rechaza
    mal = copy.deepcopy(config.cargar("reglas")); mal["parametros"]["estatus_excluidos"]["valor"] = ["CANCELADO"]
    assert any("no_configurado" in e for e in config.validar("reglas", mal))
    # y un parámetro con origen heredado/nuevo sin valor también
    mal = copy.deepcopy(config.cargar("reglas")); mal["parametros"]["max_pacientes_por_pedido"]["valor"] = None
    assert config.validar("reglas", mal)


def test_los_numeros_se_leen_como_decimal_exacto():
    p = config.cargar("reglas")["parametros"]
    assert p["e1_recuperacion_negados_medio"]["valor"] == Decimal("0.25")
    assert p["e2_recuperacion_abandono_medio"]["valor"] == Decimal("0.10")
    assert isinstance(p["umbral_conciliacion_compras"]["valor"], Decimal)


def test_los_valores_heredados_no_se_desvian_del_codigo():
    """Evita duplicar con deriva: los heredados declarados en reglas.json deben coincidir con el código vigente."""
    from backend.app.narrative.rules import RULES
    p = config.cargar("reglas")["parametros"]
    assert p["e1_recuperacion_negados_medio"]["valor"] == RULES.recovery_scenario
    assert p["e2_recuperacion_abandono_medio"]["valor"] == RULES.cart_recovery_scenario
    src = (Path(__file__).resolve().parents[2] / "backend" / "app" / "raw" / "glp1.py").read_text(encoding="utf-8")
    assert 'Decimal("0.2")' in src and "TRAFICO_PURCHASE_DIFFERS" in src
    assert p["umbral_conciliacion_compras"]["valor"] == Decimal("0.2")
    for k, v in p.items():
        if v["origen"] == "heredado":
            assert v["validacion_operacional"] == "no_validada_con_datos_reales", k


def test_flags_existen_y_estan_desactivados():
    flags = config.cargar("reglas")["flags"]
    assert set(flags) == set(config.FLAGS) and not any(flags.values())


def test_dimensiones_exigen_justificacion_y_no_hay_propiedades_por_defecto():
    d = config.cargar("reglas")
    assert d["dimensiones"] == {}                                   # ninguna dimensión declarada
    d = copy.deepcopy(d); d["dimensiones"]["canal"] = {"entidad": "pedido", "exclusiva": True, "exhaustiva": True, "justificacion": None}
    assert any("justificación" in e for e in config.validar("reglas", d))
    d["dimensiones"]["canal"] = {"entidad": "pedido", "exclusiva": None, "exhaustiva": None, "justificacion": None}
    assert config.validar("reglas", d) == []                        # sin declarar es válido: la regla no se aplicará


def test_mapeo_no_define_identificadores_de_carrito_transaccion_o_sesion_ni_trafico_en_aetops():
    m = config.cargar("mapeo_columnas")
    assert "trafico" not in m["unidades"]["AETOPS"]["hojas"] and "trafico" in m["unidades"]["GLP1"]["hojas"]
    mal = copy.deepcopy(m); mal["unidades"]["GLP1"]["hojas"]["trafico"]["alias"]["cart_id"] = ["id_carrito"]
    assert any("carrito" in e for e in config.validar("mapeo_columnas", mal))


def test_registro_de_validacion_separa_sintetica_y_operacional():
    r = config.cargar("validacion_registro")
    assert [e["regla_id"] for e in r["reglas"]] == list(config.REGLAS_FASE1)
    for e in r["reglas"]:
        assert e["validacion_operacional"] == "no_validada_con_datos_reales"             # ninguna regla se validó con datos reales
        assert e["extracto_id"] is None and e["fecha"] is None and e["confirmado_por"] is None
    mal = copy.deepcopy(r); mal["reglas"][0]["validacion_operacional"] = "confirmada"
    assert any("confirmada" in e for e in config.validar("validacion_registro", mal))   # exige extracto, fecha y confirmante
    mal = copy.deepcopy(r); mal["reglas"][0]["validacion_sintetica"] = "aprobada"; mal["reglas"][0]["regla_version"] = None
    assert any("regla_version" in e for e in config.validar("validacion_registro", mal))


def test_registro_de_validacion_coincide_con_el_catalogo_de_reglas():
    """Evita el desfase documental: la versión registrada de cada regla es la del catálogo y la validación sintética está aprobada."""
    cat = {x["id"]: x["version"] for x in config.cargar("reglas")["reglas"]}
    for e in config.cargar("validacion_registro")["reglas"]:
        assert e["regla_version"] == cat[e["regla_id"]]
        assert e["validacion_sintetica"] == "aprobada"
    assert config.validar("validacion_registro", config.cargar("validacion_registro")) == []


def test_configuracion_desconocida_o_ausente_lanza_error_claro(tmp_path):
    with pytest.raises(config.ConfigError):
        config.cargar("inexistente")
    with pytest.raises(config.ConfigError):
        config.cargar("reglas", tmp_path)                            # directorio sin el archivo
    (tmp_path / "reglas.json").write_text("{no es json", encoding="utf-8")
    with pytest.raises(config.ConfigError):
        config.cargar("reglas", tmp_path)


def test_el_empaquetado_del_sitio_incluye_los_json(tmp_path):
    """build_site copia todo `backend/` salvo __pycache__/.pyc: los JSON viajan sin tocar el proceso de compilación."""
    import zipfile
    from tools import build_site
    z = tmp_path / "t.zip"
    with zipfile.ZipFile(z, "w") as zf:
        build_site.add_tree(zf, "backend", build_site.ROOT / "backend")
    names = set(zipfile.ZipFile(z).namelist())
    assert {f"backend/app/config/{n}" for n in config.ARCHIVOS.values()} <= names
