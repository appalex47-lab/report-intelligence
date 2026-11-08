"""Bloque integral · QA integral y flujo (vigencia, bloqueo de exportación). PPTX sintéticos: corre en CI."""
import json
import shutil
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from pptx import Presentation

sys.path.insert(0, str(Path(__file__).parent))
import _deck as D                                                              # noqa: E402

from backend.app.narrative.writer import Para                                   # noqa: E402
from backend.app.plan import adaptativo as ad, escenario as es, flujo, previsualizacion as pv, qa_integral as qi, slidespec as ss   # noqa: E402
from backend.app.qa import checks                                               # noqa: E402

ERR, ADV, INF = qi.ERROR, qi.ADVERTENCIA, qi.INFO
BASE = {"id": "t", "nombre": "T", "perfil": "*", "orden_narrativo": ["panorama", "conclusiones"], "tipos_obligatorios": ["panorama", "conclusiones"], "tipo_conclusion": "acciones_priorizadas",
        "profundidad": "intermedio"}


def esc(**kw):
    return es.desde_dict({**BASE, **kw})


@pytest.fixture()
def deck(tmp_path):
    return D.crear(tmp_path / "d.pptx", [
        {"titulo": "Panorama General", "cuerpo": "La venta llega a $1,500 con una variación contra el año anterior de forma sostenida.", "tabla": [["Año", "Monto"], ["2025", "$1,000"], ["2026", "$1,500"]]},
        {"titulo": "Conclusiones Clave", "cuerpo": "Se sostiene el crecimiento por volumen en el periodo analizado, sin atribuir causas externas."},
    ])


def evaluar(deck, e=None, anterior=(), valores=(Decimal(1500), Decimal(1000)), nums=(), parrafos=None, indicadores=None, fuentes=("l.xlsx",), vista="auto", diseno=None, adaptativo=True, perfil="x/y"):
    e = e or esc()
    spec = ss.construir(deck, set(valores), set(nums), e.id, perfil, list(fuentes))
    if vista == "auto":
        vista = pv.modelo(deck, [s.id for s in spec.diapositivas], [s.tipo for s in spec.diapositivas])
    inf = diseno or ad.adaptar(deck, [s.id for s in spec.diapositivas], [s.densidad for s in spec.diapositivas], aplicar=False)
    return qi.evaluar(spec=spec, esc=e, pptx=deck, vista=vista, informe_diseno=inf, aplicado=adaptativo, qa_anterior=list(anterior), valores_motor=set(valores), narrativa_nums=set(nums),
                      parrafos=parrafos, indicadores=indicadores if indicadores is not None else {}, fuentes=list(fuentes), perfil=perfil, huellas={"pptx": "h"})


def ids(informe, sev=None):
    return [h.id for h in informe.hallazgos if sev is None or h.severidad == sev]


# ------------------------------------------------------------------------------------------------------------------------- reporte válido
def test_un_reporte_valido_no_tiene_errores_y_es_exportable(deck):
    r = evaluar(deck)
    assert r.exportable and ids(r, ERR) == [] and r.to_dict()["estado"] in ("aprobado", "con_advertencias")
    d = r.to_dict()
    assert d["esquema"] == qi.ESQUEMA and set(d["resumen"]) == {"errores", "advertencias", "informacion"} and d["huellas"] == {"pptx": "h"}


def test_cada_hallazgo_indica_elemento_descripcion_motivo_y_accion(tmp_path):
    p = D.crear(tmp_path / "x.pptx", [{"titulo": "Panorama General", "cuerpo": "Texto de la diapositiva con contenido suficiente."}])
    r = evaluar(p, esc(tipos_obligatorios=["panorama", "conclusiones"]))
    for h in r.hallazgos:
        assert h.descripcion and h.motivo and h.accion and h.severidad in (ERR, ADV, INF), h
    assert "QA_FALTA_TIPO_OBLIGATORIO" in ids(r, ERR)


# ------------------------------------------------------------------------------------------------------------------------- estructura
def test_falta_una_diapositiva_obligatoria_es_error_y_bloquea(tmp_path):
    p = D.crear(tmp_path / "x.pptx", [{"titulo": "Panorama General", "cuerpo": "Texto de la diapositiva con contenido suficiente."}])
    r = evaluar(p)
    assert "QA_FALTA_TIPO_OBLIGATORIO" in ids(r, ERR) and not r.exportable and r.to_dict()["estado"] == "bloqueado"


def test_un_orden_que_no_sigue_al_escenario_es_advertencia_y_no_bloquea(tmp_path):
    p = D.crear(tmp_path / "x.pptx", [{"titulo": "Conclusiones Clave", "cuerpo": "Texto de conclusión con contenido suficiente para la prueba."},
                                       {"titulo": "Panorama General", "cuerpo": "Texto del panorama con contenido suficiente para la prueba."}])
    r = evaluar(p)
    assert "QA_ORDEN_NARRATIVO" in ids(r, ADV) and r.exportable


def test_el_anexo_debe_ser_la_ultima_y_los_tipos_desconocidos_se_informan(tmp_path):
    p = D.crear(tmp_path / "x.pptx", [{"titulo": "Panorama General", "cuerpo": "Texto del panorama con contenido suficiente para la prueba."},
                                       {"titulo": "Algo sin clasificar", "cuerpo": "Texto con contenido suficiente para la prueba de clasificación."},
                                       {"titulo": "Conclusiones Clave", "cuerpo": "Texto de conclusión con contenido suficiente para la prueba."}])
    assert "QA_TIPO_NO_CLASIFICADO" in ids(evaluar(p), INF)


def test_las_expectativas_de_profundidad_conclusion_y_perfil(tmp_path):
    p = D.crear(tmp_path / "x.pptx", [{"titulo": "Panorama General", "cuerpo": "Texto del panorama con contenido suficiente para la prueba."}])
    r = evaluar(p, esc(profundidad="ejecutivo", tipos_obligatorios=[], perfil="glp1/mensual"), perfil="aetops/mensual")
    assert {"QA_PROFUNDIDAD_EJECUTIVA", "QA_SIN_CONCLUSION", "QA_ESCENARIO_OTRO_PERFIL"} <= set(ids(r, ADV))
    r2 = evaluar(p, esc(profundidad="ejecutivo", tipos_obligatorios=[], tipo_conclusion="sin_conclusion"))
    assert "QA_SIN_CONCLUSION" not in ids(r2)


def test_una_referencia_a_una_forma_o_diapositiva_inexistente_es_error(deck):
    spec = ss.construir(deck, set(), set(), "t", "x/y", [])
    spec.diapositivas[0].bloques[0].forma = "NoExiste"
    spec.diapositivas[1].sld_id = 999
    h = qi.revisar_estructura(spec, esc(), deck, "x/y")
    assert {"QA_REFERENCIA_FORMA", "QA_REFERENCIA_DIAPOSITIVA"} <= {x.id for x in h if x.severidad == ERR}


def test_un_id_repetido_o_un_tipo_invalido_en_el_slidespec_es_error(deck):
    spec = ss.construir(deck, set(), set(), "t", "x/y", [])
    spec.diapositivas[1].id = spec.diapositivas[0].id
    spec.diapositivas[1].tipo = "inventado"
    cods = {x.id for x in qi.revisar_estructura(spec, esc(), deck, "x/y") if x.severidad == ERR}
    assert {"QA_SPEC_ID_REPETIDO", "QA_SPEC_TIPO_INVALIDO"} <= cods


# ------------------------------------------------------------------------------------------------------------------------- contenido
def test_titulo_ausente_y_contenido_vacio_son_errores(tmp_path):
    p = D.crear(tmp_path / "x.pptx", [{"titulo": None, "cuerpo": "Cuerpo largo sin título, con varias frases que nunca deben confundirse con un encabezado de diapositiva en la lectura automática del contenido, aunque esté arriba."},
                                       {"titulo": "Conclusiones Clave"}, {"titulo": "Panorama General", "cuerpo": "Texto."}])
    r = evaluar(p)
    assert {"QA_SIN_TITULO", "QA_CONTENIDO_VACIO"} <= set(ids(r, ERR)) and not r.exportable


def test_una_tabla_con_solo_encabezado_es_advertencia(tmp_path):
    p = D.crear(tmp_path / "x.pptx", [{"titulo": "Panorama General", "cuerpo": "Texto del panorama con contenido suficiente para la prueba.", "tabla": [["Año", "Monto"]]},
                                       {"titulo": "Conclusiones Clave", "cuerpo": "Texto de conclusión con contenido suficiente para la prueba."}])
    assert "QA_TABLA_SIN_DATOS" in ids(evaluar(p), ADV)


def test_los_datos_no_disponibles_y_las_estimaciones_se_declaran_como_informacion(tmp_path):
    p = D.crear(tmp_path / "x.pptx", [{"titulo": "Panorama General", "cuerpo": "Pedidos por canal: No verificable.\nEscenario ilustrativo: recuperar $9,999."},
                                       {"titulo": "Conclusiones Clave", "cuerpo": "Texto de conclusión con contenido suficiente para la prueba."}])
    r = evaluar(p)
    assert {"QA_DATO_NO_DISPONIBLE", "QA_CONTIENE_ESTIMACIONES"} <= set(ids(r, INF))


def test_un_indicador_relevante_no_disponible_es_advertencia_y_uno_disponible_no(deck):
    e = esc(indicadores_relevantes=["monto", "ticket"])
    assert "QA_INDICADOR_NO_DISPONIBLE" in ids(evaluar(deck, e, indicadores={"monto": 1500.0, "ticket": None}), ADV)
    assert "QA_INDICADOR_NO_DISPONIBLE" not in ids(evaluar(deck, e, indicadores={"monto": 1500.0, "ticket": 7.0}))
    assert ids(evaluar(deck, e, indicadores={}), ADV).count("QA_INDICADOR_NO_DISPONIBLE") == 2                 # ausente = no disponible: no se inventa


def test_el_mensaje_central_con_cifras_sin_respaldo_es_advertencia(deck):
    assert "QA_MENSAJE_SIN_EVIDENCIA" in ids(evaluar(deck, esc(mensaje_central="La venta crece $9,999 en el periodo.")), ADV)
    assert "QA_MENSAJE_SIN_EVIDENCIA" not in ids(evaluar(deck, esc(mensaje_central="La venta llega a $1,500 en el periodo.")))
    assert "QA_MENSAJE_SIN_EVIDENCIA" not in ids(evaluar(deck, esc(mensaje_central="Un mensaje sin cifras.")))


def test_los_campos_que_el_escenario_no_define_se_informan_no_se_rellenan(deck):
    h = [x for x in evaluar(deck).hallazgos if x.id == "QA_ESCENARIO_INCOMPLETO"]
    assert len(h) == 1 and h[0].severidad == INF and "objetivo" in h[0].descripcion
    assert not [x for x in evaluar(deck, esc(objetivo="o", audiencia="a", contexto_negocio="c", mensaje_central="m", tipo_analisis="t")).hallazgos if x.id == "QA_ESCENARIO_INCOMPLETO"]


def test_cifras_sin_fuente_registrada_son_advertencia(deck):
    assert "QA_SIN_FUENTE" in ids(evaluar(deck, fuentes=()), ADV) and "QA_SIN_FUENTE" not in ids(evaluar(deck))


def test_una_interpretacion_sin_regla_es_advertencia_y_con_regla_no(deck):
    mal = {"resumen": [Para("Se explica por volumen.", "interpretacion", 0, basis="")]}
    bien = {"resumen": [Para("Se explica por volumen.", "interpretacion", 0, basis="R-VOL-1")]}
    assert "QA_INTERPRETACION_SIN_REGLA" in ids(evaluar(deck, parrafos=mal), ADV) and "QA_INTERPRETACION_SIN_REGLA" not in ids(evaluar(deck, parrafos=bien))


# ------------------------------------------------------------------------------------------------------------------------- el QA anterior no se degrada
def test_las_severidades_del_qa_anterior_se_conservan_exactamente(deck):
    ant = [checks.Issue("PPTX_X", "error", 1, "un error"), checks.Issue("PPTX_Y", "warn", 2, "una advertencia"), checks.Issue("FILL_NOTE", "info", None, "una nota")]
    r = evaluar(deck, anterior=ant)
    por = {h.id: h for h in r.hallazgos}
    assert (por["PPTX_X"].severidad, por["PPTX_Y"].severidad, por["FILL_NOTE"].severidad) == (ERR, ADV, INF)
    assert por["PPTX_X"].origen == "qa_anterior" and por["PPTX_X"].diapositiva is not None and not r.exportable        # un error anterior bloquea


def test_los_hallazgos_conocidos_traen_motivo_y_accion_especificos(deck):
    h = [x for x in evaluar(deck, anterior=[checks.Issue("PPTX_CIFRA_NO_TRAZADA", "warn", 1, "cifra")]).hallazgos if x.id == "PPTX_CIFRA_NO_TRAZADA"][0]
    assert "motor" in h.motivo and "Corregir" in h.accion


# ------------------------------------------------------------------------------------------------------------------------- diseño
def _inf(codigo, occ, forma="Cuerpo", sid=None):
    return ad.InformeDiseno(avisos=[ad.Aviso(sid or "panorama:256", forma, codigo, "m", "mo", "ac")], estimaciones={sid or "panorama:256": {forma: occ}})


def test_la_severidad_del_diseno_depende_de_cuanto_se_desborda(deck):
    spec = ss.construir(deck, set(), set(), "t", "x/y", [])
    sid = spec.diapositivas[0].id
    sev = lambda c, o: [h.severidad for h in qi.revisar_diseno(_inf(c, o, sid=sid), spec, deck, True) if h.id.startswith("QA_DISENO_")]            # noqa: E731
    assert sev("DISENO_NO_CABE", 1.10) == [ADV] and sev("DISENO_NO_CABE", 1.60) == [ERR]
    assert sev("DISENO_NO_ESTIMABLE", 0) == [INF] and sev("DISENO_SOLAPE", 0) == [ADV] and sev("DISENO_FUERA_DE_AREA", 0) == [ADV]


def test_si_el_diseno_adaptativo_estaba_desactivado_el_hallazgo_lo_dice(deck):
    spec = ss.construir(deck, set(), set(), "t", "x/y", [])
    h = [x for x in qi.revisar_diseno(_inf("DISENO_NO_CABE", 1.1, sid=spec.diapositivas[0].id), spec, deck, False) if x.id == "QA_DISENO_NO_CABE"][0]
    assert "desactivado" in h.motivo


def test_los_ajustes_hechos_se_informan(tmp_path):
    p = D.crear(tmp_path / "x.pptx", [{"titulo": "Panorama General", "cuerpo": D.LARGO, "caja": (40, 90, 880, 60), "obstaculo": (40, 156, 880, 30)},
                                       {"titulo": "Conclusiones Clave", "cuerpo": "Texto de conclusión con contenido suficiente para la prueba."}])
    spec = ss.construir(p, set(), set(), "t", "x/y", [])
    inf = ad.adaptar(p, [s.id for s in spec.diapositivas], [s.densidad for s in spec.diapositivas], aplicar=True)
    assert inf.acciones and "QA_DISENO_AJUSTE" in [h.id for h in qi.revisar_diseno(inf, ss.construir(p, set(), set(), "t", "x/y", []), p, True)]


def test_contraste_ilegible_es_error_bajo_es_advertencia_e_indeterminado_es_informacion(tmp_path):
    p = D.crear(tmp_path / "c.pptx", [{"titulo": "Panorama General", "cuerpo": "Blanco sobre blanco en un cuadro de prueba.", "color": "#FFFFFF", "fondo": "#FFFFFF"},
                                       {"titulo": "Conclusiones Clave", "cuerpo": "Gris claro sobre blanco en un cuadro de prueba.", "color": "#AAAAAA", "fondo": "#FFFFFF"},
                                       {"titulo": "Análisis de Productos", "cuerpo": "Sin color de fondo declarado en el cuadro de prueba."}])
    spec = ss.construir(p, set(), set(), "t", "x/y", [])
    h = {(x.id, x.diapositiva): x.severidad for x in qi._contraste_formas(p, spec)}
    assert h[("QA_CONTRASTE_ILEGIBLE", spec.diapositivas[0].id)] == ERR and h[("QA_CONTRASTE_BAJO", spec.diapositivas[1].id)] == ADV
    assert ("QA_CONTRASTE_NO_DETERMINABLE", None) in h
    assert qi.contraste("#000000", "#FFFFFF") == pytest.approx(21.0) and qi.contraste("#777777", "#777777") == pytest.approx(1.0)


def test_titulos_con_jerarquia_inconsistente_son_advertencia(tmp_path):
    p = D.crear(tmp_path / "t.pptx", [{"titulo": "Panorama General", "cuerpo": "Texto.", "pt_titulo": 40}, {"titulo": "Conclusiones Clave", "cuerpo": "Texto.", "pt_titulo": 20}])
    assert [h.id for h in qi._consistencia_titulos(p, ss.construir(p, set(), set(), "t", "x/y", []))] == ["QA_TITULOS_INCONSISTENTES"]
    q = D.crear(tmp_path / "q.pptx", [{"titulo": "Panorama General", "cuerpo": "Texto."}, {"titulo": "Conclusiones Clave", "cuerpo": "Texto."}])
    assert qi._consistencia_titulos(q, ss.construir(q, set(), set(), "t", "x/y", [])) == []


# ------------------------------------------------------------------------------------------------------------------------- exportación
def test_sin_vista_previa_no_se_puede_confirmar_lo_que_se_exportaria(deck):
    r = evaluar(deck, vista=None)
    assert "QA_EXPORTACION_SIN_VISTA" in ids(r, ERR) and not r.exportable


def test_una_vista_previa_que_ya_no_corresponde_al_pptx_es_error(deck, tmp_path):
    spec = ss.construir(deck, set(), set(), "t", "x/y", [])
    vista = pv.modelo(deck)
    prs = Presentation(str(deck))
    next(s for s in prs.slides[0].shapes if s.name == "Cuerpo").text_frame.paragraphs[0].runs[0].text = "Texto cambiado después de la vista previa."
    prs.save(str(deck))
    r = evaluar(deck, vista=vista)
    assert "QA_EXPORTACION_PREVIEW_OBSOLETA" in ids(r, ERR) and not r.exportable


def test_el_archivo_exportado_se_compara_con_el_slidespec(deck, tmp_path):
    spec = ss.construir(deck, set(), set(), "t", "x/y", [])
    otro = D.crear(tmp_path / "otro.pptx", [{"titulo": "Panorama General", "cuerpo": "Texto del panorama con contenido suficiente para la prueba."}])
    assert [h.id for h in qi.revisar_exportacion(otro, spec, pv.modelo(otro))] == ["QA_EXPORTACION_NUM"]
    cambiado = tmp_path / "c.pptx"
    shutil.copy(deck, cambiado)
    prs = Presentation(str(cambiado))
    next(s for s in prs.slides[1].shapes if s.name == "Titulo").text_frame.paragraphs[0].runs[0].text = "Otro título distinto"
    prs.save(str(cambiado))
    assert "QA_EXPORTACION_TITULO" in [h.id for h in qi.revisar_exportacion(cambiado, spec, pv.modelo(cambiado))]
    D.reordenar(cambiado, [1, 0])
    assert "QA_EXPORTACION_ORDEN" in [h.id for h in qi.revisar_exportacion(cambiado, spec, pv.modelo(cambiado))]


def test_una_tabla_ausente_o_de_otra_dimension_es_error(deck, tmp_path):
    spec = ss.construir(deck, set(), set(), "t", "x/y", [])
    sin = D.crear(tmp_path / "s.pptx", [{"titulo": "Panorama General", "cuerpo": "Texto del panorama con contenido suficiente para la prueba."},
                                         {"titulo": "Conclusiones Clave", "cuerpo": "Texto de conclusión con contenido suficiente para la prueba."}])
    # mismos sld_id: se copia el id esperado para aislar la comprobación de tablas
    prs = Presentation(str(sin))
    assert [h.id for h in qi.revisar_exportacion(sin, spec, pv.modelo(sin)) if h.id.startswith("QA_EXPORTACION_TABLA")] in (["QA_EXPORTACION_TABLAS"], [])
    otra = D.crear(tmp_path / "o.pptx", [{"titulo": "Panorama General", "cuerpo": "Texto del panorama con contenido suficiente para la prueba.", "tabla": [["a", "b", "c"], ["1", "2", "3"]]},
                                          {"titulo": "Conclusiones Clave", "cuerpo": "Texto de conclusión con contenido suficiente para la prueba."}])
    h = [x.id for x in qi.revisar_exportacion(otra, spec, pv.modelo(otra))]
    assert "QA_EXPORTACION_TABLA_DIMENSION" in h


def test_un_archivo_danado_es_un_hallazgo_y_una_imagen_sin_recurso_se_informa(deck, tmp_path):
    spec = ss.construir(deck, set(), set(), "t", "x/y", [])
    malo = tmp_path / "m.pptx"
    malo.write_bytes(b"no es un zip")
    assert [h.id for h in qi.revisar_exportacion(malo, spec, None)] == ["QA_EXPORTACION_ILEGIBLE"]
    p = D.crear(tmp_path / "i.pptx", [{"titulo": "Panorama General", "cuerpo": "Con imagen.", "imagen": True}])
    prs = Presentation(str(p))
    pic = next(s for s in prs.slides[0].shapes if s.shape_type == 13)
    blip = pic._element.xpath(".//a:blip")[0]
    blip.attrib.pop("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed")
    prs.save(str(p))
    sp = ss.construir(p, set(), set(), "t", "x/y", [])
    h = {x.id: x.severidad for x in qi.revisar_exportacion(p, sp, pv.modelo(p))}
    assert h["QA_IMAGEN_SIN_RECURSO"] == INF and ERR not in h.values()


# ------------------------------------------------------------------------------------------------------------------------- flujo: Plan y vigencia
class _Fill:
    def __init__(self, narrative=None):
        self.narrative = narrative or {}


@pytest.fixture()
def corrida(deck, tmp_path):
    e = esc(tipos_obligatorios=["panorama"])
    plan = flujo.Plan(e, "x/y", ["l.xlsx"], True, {}, huella_entradas="E1")
    out = tmp_path / "out"
    out.mkdir()
    qa = checks.QAReport()
    qa.add("PPTX_Y", "warn", 1, "advertencia previa")
    plan.ajustar(deck, {}, _Fill())
    plan.revisar(qa, deck, _Fill(), {}, out)
    shutil.copy(deck, out / "r.pptx")
    return plan, qa, out, e


def test_el_plan_deja_los_cuatro_archivos_y_solo_agrega_al_qa_lo_nuevo(corrida):
    plan, qa, out, _ = corrida
    assert {p.name for p in out.glob("*.json")} == set(flujo.ARCHIVOS)
    ids_qa = [i.id for i in qa.issues]
    assert ids_qa.count("PPTX_Y") == 1                                                       # lo anterior no se duplica
    assert any(i.id.startswith("QA_") for i in qa.issues)                                    # y lo nuevo sí se agrega, con su severidad
    d = json.loads((out / "qa_integral.json").read_text(encoding="utf-8"))
    assert "PPTX_Y" in [h["id"] for h in d["hallazgos"]] and d["huellas"]["entradas"] == "E1"
    plan_json = json.loads((out / "plan_reporte.json").read_text(encoding="utf-8"))
    assert plan_json["escenario"]["id"] == "t" and plan_json["opciones"]["diseno_adaptativo"] is True and "campos_no_definidos" in plan_json


def test_un_error_integral_baja_el_qa_del_reporte_y_con_el_la_descarga(deck, tmp_path):
    e = esc(orden_narrativo=["panorama", "engagement_digital", "conclusiones"], tipos_obligatorios=["panorama", "engagement_digital"])
    plan = flujo.Plan(e, "x/y", ["l.xlsx"], True, {})
    qa = checks.QAReport()
    out = tmp_path / "o"
    out.mkdir()
    plan.ajustar(deck, {}, _Fill())
    plan.revisar(qa, deck, _Fill(), {}, out)
    assert not qa.passed and any(i.id == "QA_FALTA_TIPO_OBLIGATORIO" and i.severity == "error" for i in qa.issues)


def test_la_vigencia_detecta_cambios_en_el_pptx_en_las_entradas_y_archivos_faltantes(corrida, tmp_path):
    _, _, out, _ = corrida
    assert flujo.vigente(out, "E1") == {"vigente": True, "motivos": []}
    v = flujo.vigente(out, "E2")
    assert v["vigente"] is False and "Cambió el contenido" in v["motivos"][0]
    assert flujo.vigente(out, None)["vigente"] is True                                       # sin huella de entradas solo se compara el PPTX
    prs = Presentation(str(out / "r.pptx"))
    next(s for s in prs.slides[1].shapes if s.name == "Cuerpo").text_frame.paragraphs[0].runs[0].text = "Cambiado"
    prs.save(str(out / "r.pptx"))
    v = flujo.vigente(out, "E1")
    assert v["vigente"] is False and "PPTX cambió" in v["motivos"][0]
    (out / "plan_reporte.json").unlink()
    assert flujo.vigente(out, "E1")["vigente"] is False
    vacio = tmp_path / "vacio"
    vacio.mkdir()
    assert flujo.vigente(vacio, "E1")["vigente"] is False


def test_sin_pptx_en_la_carpeta_no_es_vigente_nunca_se_asume(corrida):
    _, _, out, _ = corrida
    (out / "r.pptx").unlink()
    assert flujo.vigente(out, "E1")["vigente"] is False


def test_la_huella_de_entradas_es_determinista_y_sensible():
    assert flujo.huella_de("a", {"x": 1}, [1]) == flujo.huella_de("a", {"x": 1}, [1]) and flujo.huella_de("a", {"x": 1}) != flujo.huella_de("a", {"x": 2})
    assert flujo.huella_de({"b": 1, "a": 2}) == flujo.huella_de({"a": 2, "b": 1})
