"""Fase 7 · QA y previsualización: recorrido real  datos de entrada → motor → reglas → escenario → previsualización → PPTX → resultado.

Usa el puente (el mismo que la interfaz), el motor, los libros de ejemplo y las plantillas: las REALES si están en `templates/` y, si no (CI, clon limpio), las SINTÉTICAS versionadas
(tests/plantillas.py): misma estructura, sin marca ni datos. Nada se omite en CI. No basta con que el archivo se genere: se comprueba qué contiene, que lo
previsualizado coincide con él (lector independiente), que lo que bloquea bloquea y que lo regenerado es el mismo contenido."""
import importlib
import io
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tests import plantillas as PL

EJ = ROOT / "data" / "ejemplos"
FALTAN = [k for k in PL.FORMATOS if not PL.disponible(k)]
pytestmark = pytest.mark.skipif(bool(FALTAN), reason=f"OMITIDA (no ejecutada): faltan plantillas ({', '.join(FALTAN)}); ni reales ni sintéticas")

LARGO = "El canal digital mantiene un desempeño sostenido en el periodo, con variaciones moderadas entre líneas y categorías que conviene seguir. "


@pytest.fixture()
def br(tmp_path, monkeypatch):
    monkeypatch.setenv("REPORT_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("REPORT_HISTORY_DB", str(tmp_path / "h" / "h.sqlite"))
    monkeypatch.setenv("REPORT_TEMPLATES_DIR", str(tmp_path / "tpl"))
    from backend.app.web import bridge, service
    importlib.reload(service)
    importlib.reload(bridge)
    service.RENDER = False
    (tmp_path / "h").mkdir()
    for k in PL.FORMATOS:
        assert call(bridge, "POST", f"/api/templates/{k}", up=PL.ruta(k))["status"] == 200
    return bridge, service


def call(bridge, method, path, body=None, up=None):
    return json.loads(bridge.handle(method, path, json.dumps(body) if body is not None else "", str(up) if up else "", up.name if up else ""))


def correr(br, unit, per, year, idx, libro, metas=None, ediciones=None):
    bridge, service = br
    rid = call(bridge, "POST", "/api/runs", {"unit": unit, "periodicity": per, "year": year, "index": idx})["json"]["id"]
    assert call(bridge, "POST", f"/api/runs/{rid}/file", up=EJ / libro)["status"] == 200
    if metas:
        call(bridge, "PUT", f"/api/runs/{rid}/targets", metas)
    if ediciones:
        call(bridge, "PUT", f"/api/runs/{rid}/edits", ediciones)
    return rid


def generar(br, rid):
    return call(br[0], "POST", f"/api/runs/{rid}/generate", {})


def informe(br, rid):
    return call(br[0], "GET", f"/api/runs/{rid}/plan")["json"]


def out_dir(br, rid):
    return br[1]._dir(rid) / "out"


REFERENCIAS = [("aetops", "mensual", 2026, 9, "AETOPS_crudo_ejemplo.xlsx", {"total": "12000000"}), ("aetops", "trimestral", 2026, 3, "AETOPS_crudo_ejemplo.xlsx", {"total": "34000000"}),
               ("glp1", "mensual", 2026, 9, "GLP1_crudo_ejemplo.xlsx", None), ("glp1", "trimestral", 2026, 3, "GLP1_crudo_ejemplo.xlsx", None)]
IDS = ["aetops_mensual", "aetops_trimestral", "glp1_mensual", "glp1_trimestral"]


# ------------------------------------------------------------------------------------------------------------ previsualización ≡ PPTX en los 4 formatos
@pytest.mark.parametrize("unit,per,year,idx,libro,metas", REFERENCIAS, ids=IDS)
def test_la_vista_previa_coincide_con_el_pptx_segun_un_lector_independiente_en_los_cuatro_formatos(br, unit, per, year, idx, libro, metas):
    from backend.app.plan import previsualizacion as pv
    rid = correr(br, unit, per, year, idx, libro, metas)
    g = generar(br, rid)
    assert g["status"] == 200, g
    out = out_dir(br, rid)
    vista = json.loads((out / "previsualizacion.json").read_text(encoding="utf-8"))
    pptx = next(out.glob("*.pptx"))
    assert pv.verificar_correspondencia(vista, pptx) == []                                       # lector zip + XML, independiente de python-pptx
    assert call(br[0], "GET", f"/api/runs/{rid}/preview")["json"]["huella"] == vista["huella"]    # lo que sirve la API es lo guardado
    spec = json.loads((out / "slidespec.json").read_text(encoding="utf-8"))
    assert [d["sld_id"] for d in spec["diapositivas"]] == [d["sld_id"] for d in vista["diapositivas"]]
    errores = [h for h in informe(br, rid)["qa_integral"]["hallazgos"] if h["severidad"] == "ERROR"]
    assert not errores, errores


@pytest.mark.parametrize("unit,per,year,idx,libro,metas", REFERENCIAS, ids=IDS)
def test_las_cifras_impresas_se_trazan_al_motor_en_los_cuatro_formatos(br, unit, per, year, idx, libro, metas):
    """Coherencia datos → cálculos → representación: ninguna cifra impresa del reporte válido queda sin trazar al motor (salvo las advertencias ya documentadas)."""
    rid = correr(br, unit, per, year, idx, libro, metas)
    assert generar(br, rid)["status"] == 200
    hs = informe(br, rid)["qa_integral"]["hallazgos"]
    sin_trazar = [h for h in hs if h["id"] in ("PPTX_CIFRA_NO_TRAZADA", "QA_CONTENIDO_SIN_RESPALDO") and h["severidad"] != "INFORMACIÓN"]
    assert not sin_trazar, sin_trazar


def test_los_indicadores_del_panel_son_los_mismos_que_imprime_el_pptx(br):
    """Lo que la pantalla «Validar» muestra (Lectura rápida del motor) aparece, con el mismo valor, en el PPTX generado."""
    from pptx import Presentation
    rid = correr(br, "aetops", "mensual", 2026, 9, "AETOPS_crudo_ejemplo.xlsx", {"total": "12000000"})
    an = call(br[0], "GET", f"/api/runs/{rid}/analysis")["json"]
    assert generar(br, rid)["status"] == 200
    texto = " ".join(sh.text_frame.text for s in Presentation(str(next(out_dir(br, rid).glob("*.pptx")))).slides for sh in s.shapes if sh.has_text_frame)
    venta = next(k for k in an["kpis"] if k["metrica"] == "Venta")["valor"]
    assert f"${venta / 1e6:.2f} M" in texto, (venta, texto[:300])


# ------------------------------------------------------------------------------------------------------------ reproducibilidad
def test_regenerar_con_las_mismas_entradas_da_el_mismo_contenido(br):
    """Los bytes del PPTX difieren (el zip registra la hora de escritura) pero el contenido, el SlideSpec y la geometría son idénticos: la diferencia está controlada."""
    from tools import capture_baseline as cb
    res = []
    for _ in range(2):
        rid = correr(br, "aetops", "mensual", 2026, 9, "AETOPS_crudo_ejemplo.xlsx", {"total": "12000000"})
        assert generar(br, rid)["status"] == 200
        out = out_dir(br, rid)
        spec = json.loads((out / "slidespec.json").read_text(encoding="utf-8"))
        res.append((cb._slide_texts(next(out.glob("*.pptx"))), spec["huella"], [d["tipo"] for d in spec["diapositivas"]],
                    json.loads((out / "qa_integral.json").read_text(encoding="utf-8"))["resumen"]))
    assert res[0] == res[1]


# ------------------------------------------------------------------------------------------------------------ reportes con advertencias
@pytest.mark.parametrize("unit,per,year,idx,libro,metas", [REFERENCIAS[1], REFERENCIAS[2]], ids=["aetops_trimestral", "glp1_mensual"])
def test_un_reporte_con_advertencias_se_genera_las_muestra_y_no_bloquea(br, unit, per, year, idx, libro, metas):
    rid = correr(br, unit, per, year, idx, libro, metas)
    g = generar(br, rid)
    assert g["status"] == 200
    r = call(br[0], "GET", f"/api/runs/{rid}/result")["json"]
    assert r["qa_passed"] and r["downloadable"] and r["vigente"] is True and r["qa_integral"]["resumen"]["advertencias"] > 0
    adv = [h for h in informe(br, rid)["qa_integral"]["hallazgos"] if h["severidad"] == "ADVERTENCIA"]
    assert adv and all(h["motivo"] and h["accion"] and h["id"] for h in adv)                     # cada advertencia explica el problema y cómo resolverlo
    assert call(br[0], "GET", f"/api/runs/{rid}/preview")["status"] == 200                       # y la vista previa está disponible para revisarlas


def test_una_cifra_inventada_en_la_narrativa_editada_se_advierte_y_se_nombra(br):
    rid = correr(br, "aetops", "mensual", 2026, 9, "AETOPS_crudo_ejemplo.xlsx", {"total": "12000000"},
                 {"resumen_ejecutivo": ["La venta fue de $99.99 M, un +400 % frente al año anterior."]})
    assert generar(br, rid)["status"] == 200
    adv = [h for h in informe(br, rid)["qa_integral"]["hallazgos"] if h["severidad"] == "ADVERTENCIA"]
    assert any("$99.99 M" in h["descripcion"] for h in adv), adv                                # nunca pasa como dato verificado


# ------------------------------------------------------------------------------------------------------------ datos incompletos o inválidos
@pytest.mark.parametrize("unit,per,year,idx,libro,codigo", [
    ("aetops", "mensual", 2026, 9, "AETOPS_crudo_con_defectos.xlsx", "RAW_"),
    ("glp1", "mensual", 2026, 9, "GLP1_crudo_con_defectos.xlsx", "RAW_"),
    ("aetops", "mensual", 2026, 9, "GLP1_crudo_ejemplo.xlsx", "RAW_COLUMN_MISSING"),
    ("glp1", "mensual", 2026, 9, "AETOPS_crudo_ejemplo.xlsx", "RAW_COLUMN_MISSING"),
    ("aetops", "mensual", 2030, 1, "AETOPS_crudo_ejemplo.xlsx", "RAW_PERIOD_EMPTY"),
    ("aetops", "mensual", 2024, 3, "AETOPS_crudo_ejemplo.xlsx", "RAW_PERIOD_EMPTY"),
], ids=["aetops_defectos", "glp1_defectos", "aetops_libro_de_glp1", "glp1_libro_de_aetops", "periodo_futuro", "periodo_sin_datos"])
def test_los_datos_incompletos_o_invalidos_bloquean_con_un_hallazgo_y_no_producen_archivo(br, unit, per, year, idx, libro, codigo):
    rid = correr(br, unit, per, year, idx, libro, {"total": "12000000"} if unit == "aetops" else None)
    an = call(br[0], "GET", f"/api/runs/{rid}/analysis")
    assert an["status"] == 200 and an["json"]["can_generate"] is False
    bloqueantes = [f["id"] for f in an["json"]["findings"] if f["severity"] == "block"]
    assert bloqueantes and any(b.startswith(codigo) for b in bloqueantes), bloqueantes
    g = generar(br, rid)
    assert g["status"] == 409 and "bloqueantes" in g["error"]
    assert not list(out_dir(br, rid).glob("*.pptx")) if out_dir(br, rid).exists() else True        # no se entrega ningún archivo
    assert call(br[0], "GET", f"/api/runs/{rid}/preview")["status"] == 404
    assert call(br[0], "GET", f"/api/runs/{rid}/narrative")["status"] == 409                         # ni siquiera se puede revisar la narrativa


# ------------------------------------------------------------------------------------------------------------ contenido extenso
def test_un_texto_extenso_que_cabe_no_se_toca_y_uno_que_no_cabe_bloquea_con_motivo_y_se_corrige(br):
    # 1) extenso pero cabe: sin ajustes ni avisos
    rid = correr(br, "aetops", "mensual", 2026, 9, "AETOPS_crudo_ejemplo.xlsx", {"total": "12000000"}, {"resumen_ejecutivo": [LARGO * 14]})
    assert generar(br, rid)["status"] == 200
    p = informe(br, rid)
    assert p["diseno"]["acciones"] == [] and p["diseno"]["avisos"] == [] and p["qa_integral"]["resumen"]["errores"] == 0
    # 2) no cabe ni con la letra al 80 %: se ajusta, se avisa, se BLOQUEA la descarga y se explica cómo corregir
    call(br[0], "PUT", f"/api/runs/{rid}/edits", {"resumen_ejecutivo": [LARGO * 60]})
    assert generar(br, rid)["status"] == 200
    p = informe(br, rid)
    assert [a["tipo"] for a in p["diseno"]["acciones"]] == ["reducir_letra"] and [a["codigo"] for a in p["diseno"]["avisos"]] == ["DISENO_NO_CABE"]
    err = [h for h in p["qa_integral"]["hallazgos"] if h["severidad"] == "ERROR"]
    assert [h["id"] for h in err] == ["QA_DISENO_NO_CABE"] and err[0]["motivo"] and err[0]["accion"]
    r = call(br[0], "GET", f"/api/runs/{rid}/result")["json"]
    assert r["qa_passed"] is False and r["downloadable"] is False
    assert call(br[0], "GET", f"/api/runs/{rid}/files/{r['pptx']}")["status"] == 403
    assert call(br[0], "GET", f"/api/runs/{rid}/preview")["status"] == 200                          # la vista previa sigue disponible para corregir
    # 3) se corrige el texto, se reejecuta y se habilita
    call(br[0], "PUT", f"/api/runs/{rid}/edits", {"resumen_ejecutivo": [LARGO * 5]})
    assert generar(br, rid)["status"] == 200
    r = call(br[0], "GET", f"/api/runs/{rid}/result")["json"]
    assert r["qa_passed"] and r["downloadable"] and r["vigente"] is True


def test_un_texto_editado_vacio_bloquea_y_uno_con_marcado_no_rompe_el_archivo(br):
    from pptx import Presentation
    rid = correr(br, "aetops", "mensual", 2026, 9, "AETOPS_crudo_ejemplo.xlsx", {"total": "12000000"}, {"resumen_ejecutivo": [""]})
    assert generar(br, rid)["status"] == 200
    assert call(br[0], "GET", f"/api/runs/{rid}/result")["json"]["downloadable"] is False
    assert "QA_CONTENIDO_VACIO" in [h["id"] for h in informe(br, rid)["qa_integral"]["hallazgos"] if h["severidad"] == "ERROR"]
    call(br[0], "PUT", f"/api/runs/{rid}/edits", {"resumen_ejecutivo": ["<script>alert(1)</script> & <b>negrita</b>"]})
    assert generar(br, rid)["status"] == 200
    p = next(out_dir(br, rid).glob("*.pptx"))
    texto = " ".join(sh.text_frame.text for s in Presentation(str(p)).slides for sh in s.shapes if sh.has_text_frame)
    assert "<script>alert(1)</script>" in texto and len(Presentation(io.BytesIO(p.read_bytes())).slides) == 13      # texto literal, archivo íntegro
