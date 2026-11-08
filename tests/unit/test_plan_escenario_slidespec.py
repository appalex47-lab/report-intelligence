"""Bloque integral · Escenarios y SlideSpec. PPTX sintéticos: corre en CI."""
import json
import sqlite3
import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import _deck as D                                              # noqa: E402

from backend.app.plan import escenario as es, slidespec as ss   # noqa: E402

MIN = {"id": "prueba", "nombre": "Prueba"}


# ------------------------------------------------------------------------------------------------------------------------------ escenarios
def test_el_catalogo_es_valido_y_cubre_los_cuatro_perfiles():
    cat = es.catalogo()
    assert set(cat) == {"aetops-mensual", "aetops-trimestral", "glp1-mensual", "glp1-trimestral"}
    for e in cat.values():
        assert set(e.tipos_obligatorios) <= set(e.orden_narrativo) and set(e.orden_narrativo) <= set(es.TIPOS_DIAPOSITIVA)


def test_lo_que_la_especificacion_no_define_queda_como_no_definido_y_no_se_inventa():
    cat = es.catalogo()
    assert cat["glp1-mensual"].objetivo is None and cat["glp1-mensual"].audiencia is None and cat["glp1-mensual"].tipo_analisis is None
    assert {"objetivo", "audiencia"} <= set(cat["glp1-mensual"].no_definidos())
    assert cat["aetops-mensual"].objetivo and "dirección" in cat["aetops-mensual"].audiencia.lower()
    assert cat["aetops-mensual"].mensaje_central is None                       # lo determina cada periodo: nunca se rellena de antemano


def test_el_id_de_cada_perfil_coincide_con_el_catalogo():
    assert es.id_para_perfil("AETOPS", "mensual") in es.catalogo() and es.id_para_perfil("glp1", "Trimestral") in es.catalogo()


@pytest.mark.parametrize("cambio,match", [
    ({"id": "Mayus"}, "id"), ({"id": ""}, "id"), ({"nombre": ""}, "nombre"), ({"profundidad": "extrema"}, "profundidad"),
    ({"tipo_conclusion": "x"}, "tipo_conclusion"), ({"perfil": "aetops"}, "perfil"), ({"objetivo": 3}, "objetivo"), ({"objetivo": "x" * 801}, "excede"),
    ({"orden_narrativo": ["inventada"]}, "no reconocidos"), ({"orden_narrativo": ["panorama", "panorama"]}, "repetidos"),
    ({"orden_narrativo": ["panorama"], "tipos_obligatorios": ["negados"]}, "contenido en"), ({"indicadores_relevantes": ["ventas_inventadas"]}, "no reconocidos"),
    ({"campo_nuevo": 1}, "no reconocidos"), ({"indicadores_relevantes": "monto"}, "lista"),
])
def test_un_escenario_invalido_se_rechaza_con_un_mensaje_que_dice_que_campo(cambio, match):
    with pytest.raises(es.ErrorEscenario, match=match):
        es.desde_dict({**MIN, **cambio})


def test_un_escenario_minimo_es_valido_y_su_huella_es_estable_y_sensible():
    a, b = es.desde_dict(MIN), es.desde_dict(MIN)
    assert a.huella() == b.huella() and a.origen == "catalogo"
    assert es.ajustar(a, {"objetivo": "otro"}).huella() != a.huella()
    assert es.desde_dict({**MIN, "orden_narrativo": ["panorama", "negados"]}).huella() != es.desde_dict({**MIN, "orden_narrativo": ["negados", "panorama"]}).huella()


def test_ajustar_valida_con_las_mismas_reglas_y_marca_el_origen():
    base = es.catalogo()["aetops-mensual"]
    assert es.ajustar(base, None) is base and es.ajustar(base, {}) is base
    aj = es.ajustar(base, {"audiencia": "Comité", "profundidad": "detallado"})
    assert aj.origen == "ajustado" and aj.audiencia == "Comité" and aj.id == base.id and base.audiencia != "Comité"      # el catálogo no se muta
    assert es.ajustar(base, {"audiencia": base.audiencia}) is base                                                         # sin cambio real, sigue siendo el original
    with pytest.raises(es.ErrorEscenario):
        es.ajustar(base, {"profundidad": "extrema"})
    assert es.ajustar(base, {"id": "otro"}).id == base.id                                                                  # el id no se ajusta


def test_el_contexto_de_negocio_se_convierte_en_lineas_para_el_contexto_del_equipo():
    e = es.desde_dict({**MIN, "contexto_negocio": "Campaña A\n\n  Cambio de proveedor  \n"})
    assert es.lineas_contexto(e) == ["Campaña A", "Cambio de proveedor"] and es.lineas_contexto(es.desde_dict(MIN)) == []


def test_escenarios_propios_se_guardan_listan_y_borran_pero_no_pisan_el_catalogo():
    con = sqlite3.connect(":memory:")
    assert es.listar_propios(con) == {}
    e = es.guardar_propio(con, {**MIN, "objetivo": "Mi objetivo", "orden_narrativo": ["panorama"], "tipos_obligatorios": ["panorama"]})
    assert e.origen == "usuario" and set(es.listar_propios(con)) == {"prueba"} and es.todos(con)["prueba"].objetivo == "Mi objetivo"
    es.guardar_propio(con, {**MIN, "objetivo": "Actualizado"})                                         # mismo id: se actualiza
    assert es.listar_propios(con)["prueba"].objetivo == "Actualizado"
    with pytest.raises(es.ErrorEscenario, match="catálogo"):
        es.guardar_propio(con, {"id": "aetops-mensual", "nombre": "x"})
    assert es.borrar_propio(con, "prueba") and not es.borrar_propio(con, "prueba") and es.listar_propios(con) == {}


def test_un_registro_propio_danado_no_tumba_a_los_demas_ni_se_muestra_como_valido():
    con = sqlite3.connect(":memory:")
    es.guardar_propio(con, MIN)
    con.execute("INSERT INTO escenarios_reporte VALUES('roto', '{no es json')")
    con.execute("INSERT INTO escenarios_reporte VALUES('malo', '{\"id\":\"malo\",\"nombre\":\"x\",\"profundidad\":\"zzz\"}')")
    assert set(es.listar_propios(con)) == {"prueba"}


def test_un_catalogo_danado_es_un_error_visible_no_un_catalogo_vacio(tmp_path):
    f = tmp_path / "c.json"
    f.write_text("{no", encoding="utf-8")
    with pytest.raises(es.ErrorEscenario, match="No se pudo leer"):
        es.catalogo(f)
    f.write_text(json.dumps({"esquema": "otro/9", "escenarios": []}), encoding="utf-8")
    with pytest.raises(es.ErrorEscenario, match="Esquema"):
        es.catalogo(f)
    f.write_text(json.dumps({"esquema": es.ESQUEMA, "escenarios": [MIN, MIN]}), encoding="utf-8")
    with pytest.raises(es.ErrorEscenario, match="repetido"):
        es.catalogo(f)


# ------------------------------------------------------------------------------------------------------------------------------ SlideSpec
@pytest.fixture()
def deck(tmp_path):
    return D.crear(tmp_path / "d.pptx", [
        {"titulo": "Resumen Ejecutivo", "cuerpo": "La venta llega a $11.56 M y crece +67% contra el año anterior de forma sostenida."},
        {"titulo": "Panorama General", "cuerpo": "Panorama del mes con cifras 2,392 piezas.", "tabla": [["Año", "Monto", "Piezas"], ["2025", "$1,000", "2,392"], ["2026", "$2,000", "3,696"]]},
        {"titulo": "Análisis de Productos", "cuerpo": "Productos líderes.", "imagen": True},
        {"titulo": "Análisis de Productos", "cuerpo": "Productos con alzas y bajas."},
        {"titulo": "Conclusiones Clave", "cuerpo": "Se sostiene el crecimiento por volumen y no por precio en el periodo."},
    ])


def _spec(deck, valores=(), narr=(), fuentes=("libro.xlsx",)):
    return ss.construir(deck, set(Decimal(v) for v in valores), set(narr), "aetops-mensual", "aetops/mensual", list(fuentes))


def test_cada_diapositiva_tiene_id_estable_tipo_y_los_titulos_repetidos_no_colisionan(deck):
    sp = _spec(deck)
    ids = [s.id for s in sp.diapositivas]
    assert len(set(ids)) == 5 and [s.tipo for s in sp.diapositivas] == ["resumen_ejecutivo", "panorama", "productos", "productos", "conclusiones"]
    assert ss.validar(sp) == []


def test_el_id_no_depende_de_la_posicion_ni_del_orden(deck):
    antes = {s.id: s.titulo for s in _spec(deck).diapositivas}
    D.reordenar(deck, [4, 3, 2, 1, 0])
    despues = _spec(deck)
    assert {s.id: s.titulo for s in despues.diapositivas} == antes                         # mismas ids, mismos títulos
    assert [s.indice for s in despues.diapositivas] == [1, 2, 3, 4, 5] and despues.diapositivas[0].tipo == "conclusiones"


def test_la_especificacion_es_determinista_y_su_huella_cambia_si_cambia_el_contenido(deck, tmp_path):
    a, b = _spec(deck).to_dict(), _spec(deck).to_dict()
    assert a == b and len(a["huella"]) == 64
    otro = D.crear(tmp_path / "o.pptx", [{"titulo": "Resumen Ejecutivo", "cuerpo": "Otro texto distinto de al menos veinticinco caracteres."}])
    assert _spec(otro).to_dict()["huella"] != a["huella"]


def test_objetivo_solo_donde_la_documentacion_lo_define(deck):
    por_tipo = {s.tipo: s for s in _spec(deck).diapositivas}
    assert por_tipo["panorama"].objetivo and "variación" in por_tipo["panorama"].objetivo
    assert por_tipo["resumen_ejecutivo"].objetivo is None                                   # no definido: no se inventa


def test_mensaje_principal_titulo_y_bloques(deck):
    s = _spec(deck).diapositivas[1]
    assert s.titulo == "Panorama General" and s.mensaje.startswith("Panorama del mes") and "**" not in s.mensaje
    assert [b.tipo for b in s.bloques] == ["texto", "tabla"] and s.bloques[1].filas == 3 and s.bloques[1].columnas == 3
    assert s.visualizaciones == ["tabla 3×3 (Tabla)"] and s.restricciones["letra_minima_pt"] == 9.0


def test_las_metricas_se_clasifican_en_real_sin_respaldo_estimado_y_no_disponible(tmp_path):
    p = D.crear(tmp_path / "m.pptx", [
        {"titulo": "Panorama General", "cuerpo": "La venta es $1,500 y el ticket $7,777.\nEscenario ilustrativo: recuperar $99,999.\nPedidos por canal: No verificable."}])
    sp = ss.construir(p, {Decimal(1500)}, set(), "x", "y", ["libro.xlsx"])
    est = {m.texto: m.estado for m in sp.diapositivas[0].metricas}
    assert est["$1,500"] == "real" and est["$7,777"] == "sin_respaldo" and est["$99,999"] == "estimado"
    assert "no_disponible" in est.values()
    real = next(m for m in sp.diapositivas[0].metricas if m.estado == "real")
    assert real.fuente == "libro.xlsx" and sp.diapositivas[0].fuentes == ["libro.xlsx"]                    # trazabilidad de la fuente
    assert ss.validar(sp) == []                                                                              # una cifra sin respaldo se informa en el QA, no invalida la especificación


def test_una_cifra_de_la_narrativa_verificada_cuenta_como_respaldada(tmp_path):
    p = D.crear(tmp_path / "n.pptx", [{"titulo": "Panorama General", "cuerpo": "Se estima un efecto de $5,000 por decisión editorial."}])
    assert [m.estado for m in ss.construir(p, set(), set(), "x", "y").diapositivas[0].metricas] == ["sin_respaldo"]
    assert [m.estado for m in ss.construir(p, set(), {"$5,000"}, "x", "y").diapositivas[0].metricas] == ["real"]


def test_densidad_por_tipo_de_contenido(tmp_path):
    p = D.crear(tmp_path / "d.pptx", [
        {"titulo": "Conclusiones Clave", "cuerpo": "Un mensaje breve de cierre del periodo."},
        {"titulo": "Panorama General", "cuerpo": "Tabla.", "tabla": [["a", "b"], ["1", "2"]]},
        {"titulo": "Análisis de Canales", "cuerpo": "X " * 300, "tabla": [["a", "b"], ["1", "2"]]},
        {"titulo": "Análisis de Productos", "cuerpo": "Con imagen.", "imagen": True},
        {"titulo": "Recomendaciones", "cuerpo": "Texto extenso. " * 80},
        {"titulo": "Análisis de Negados", "cuerpo": "$1 $2 $3 $4 $5 $6 $7 $8"},
    ])
    assert [s.densidad for s in ss.construir(p, set(), set(), "x", "y").diapositivas] == ["pocos_elementos", "tabla", "mixta", "grafico", "narrativa_extensa", "multiples_kpis"]


def test_una_imagen_que_esta_en_casi_todas_las_diapositivas_es_decoracion_de_la_plantilla(tmp_path):
    p = D.crear(tmp_path / "l.pptx", [{"titulo": f"Análisis de Productos {i}", "cuerpo": "Contenido.", "logo": True} for i in range(5)] + [{"titulo": "Conclusiones Clave", "cuerpo": "Contenido.", "imagen": True}])
    sp = ss.construir(p, set(), set(), "x", "y")
    assert all(b.decorativo for s in sp.diapositivas[:5] for b in s.bloques if b.tipo == "imagen")
    assert [b.decorativo for b in sp.diapositivas[5].bloques if b.tipo == "imagen"] == [False] and sp.diapositivas[5].visualizaciones == ["imagen (Imagen)"]


def test_las_invariantes_se_validan_antes_de_representar(tmp_path):
    p = D.crear(tmp_path / "v.pptx", [{"titulo": None, "cuerpo": "Esta diapositiva no tiene título pero sí un cuerpo de texto largo, con varias frases, que nunca debe confundirse con un encabezado de la diapositiva en la lectura automática."}, {"titulo": "Panorama General"}])
    sp = ss.construir(p, set(), set(), "x", "y")
    assert {c for _, c, _ in ss.validar(sp)} == {"SPEC_SIN_TITULO", "SPEC_SIN_CONTENIDO"}
    assert [s.estado for s in sp.diapositivas] == ["incompleta", "incompleta"]
    s = sp.diapositivas[0]
    s.id, s.tipo, s.densidad = "mal id", "inventado", "rara"
    s.bloques = s.bloques + s.bloques
    s.metricas.append(ss.Metrica("1", "inventado"))
    codigos = {c for c, _ in ss.validar_diapositiva(s)}
    assert {"SPEC_ID_INVALIDO", "SPEC_TIPO_INVALIDO", "SPEC_DENSIDAD_INVALIDA", "SPEC_ESTADO_INVALIDO", "SPEC_FORMA_REPETIDA"} <= codigos
    dup = ss.SpecReporte("x", "y", [sp.diapositivas[1], sp.diapositivas[1]], 960, 540)
    assert "SPEC_ID_REPETIDO" in {c for _, c, _ in ss.validar(dup)} and "SPEC_VACIA" in {c for _, c, _ in ss.validar(ss.SpecReporte("x", "y", [], 960, 540))}


def test_el_tipo_se_deduce_del_titulo_y_de_las_formas_que_agrega_el_generador():
    assert ss.clasificar("Análisis Líneas AETOP YoY", []) == "lineas" and ss.clasificar("¿Quién busca GLP1?", []) == "perfil_paciente"
    assert ss.clasificar("Conclusiones Clave", []) == "conclusiones" and ss.clasificar("Recomendaciones", []) == "recomendaciones"
    assert ss.clasificar("Lo que sea", ["RI_anexo_hallazgos"]) == "anexo_calidad" and ss.clasificar("Hallazgo X", ["RI_descubrimiento_titular"]) == "descubrimiento"
    assert ss.clasificar("Un título desconocido", []) == "contenido" and ss.clasificar(None, []) == "contenido"
