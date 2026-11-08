"""Fase 5 · RQ-19: anexo «Calidad de datos y supuestos» como última diapositiva (`backend/app/deck/anexo.py`).

Opt-in (flag `anexo_calidad` apagado por omisión: sin él el PPTX es idéntico a la línea base). Con un deck sintético que imita las formas de la plantilla (no hay
plantillas ni datos reales) y, si existen plantillas locales, con los 4 decks de referencia: la diapositiva se agrega al final, no mueve ni altera las existentes,
no introduce cifras del negocio, supera el QA estructural y, con LibreOffice, el visual.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from pptx import Presentation
from pptx.util import Emu, Inches, Pt

from backend.app import calidad as C
from backend.app.deck import anexo as A
from backend.app.deck.extras import BODY, TITLE
from backend.app.models import Period
from backend.app.qa import cifras, pptx_export, visual
from tests import plantillas as PL

ROOT = Path(__file__).resolve().parents[2]
EJ = ROOT / "data" / "ejemplos"


def deck_base(tmp_path, n=3):
    """Deck sintético con las formas que clona el anexo (título «CuadroTexto 9» y cuerpo «CuadroTexto 12»)."""
    prs = Presentation()
    prs.slide_width, prs.slide_height = Emu(12_192_000), Emu(6_858_000)
    for k in range(n):
        s = prs.slides.add_slide(prs.slide_layouts[6])
        for nombre, x, y, w, h, t in ((TITLE, 567871, 400_000, 8_000_000, 500_000, f"Diapositiva {k + 1}"), (BODY, 567871, 1_300_000, 6_500_000, 4_500_000, f"Cuerpo de la diapositiva {k + 1}")):
            tb = s.shapes.add_textbox(Emu(x), Emu(y), Emu(w), Emu(h))
            tb.name = nombre
            r = tb.text_frame.paragraphs[0].add_run()
            r.text, r.font.size = t, Pt(12)
    p = tmp_path / "base.pptx"
    prs.save(p)
    return p


@pytest.fixture(scope="module")
def anexo_dict():
    from backend.app.pipeline import run_glp1_raw
    from backend.app import escenarios as E
    per = Period("GLP1", "mensual", 2026, 9)
    res = run_glp1_raw(EJ / "GLP1_crudo_ejemplo.xlsx", per)
    ctx = E.contexto_cacheado(EJ / "GLP1_crudo_ejemplo.xlsx", per)
    return C.construir(res, "glp1", per, ctx, {"nombre": "GLP1_crudo_ejemplo.xlsx", "sha256": "ab" * 32, "bytes": 1}, E.construir(res, "glp1", per, ctx))


def textos(prs, i):
    return [sh.text_frame.text for sh in prs.slides[i].shapes if sh.has_text_frame]


# --------------------------------------------------------------------------------------------- comportamiento
def test_agrega_una_diapositiva_al_final_sin_tocar_las_existentes(tmp_path, anexo_dict):
    base = deck_base(tmp_path)
    antes = [textos(Presentation(base), i) for i in range(3)]
    prs = Presentation(base)
    sm = A.add_quality_annex(prs, anexo_dict, None, 3)
    prs.save(tmp_path / "con.pptx")
    p = Presentation(tmp_path / "con.pptx")
    assert len(p.slides) == 4 and sm == [0, 1, 2, 2]                                   # la nueva se mapea a la diapositiva de la que se clonó
    assert [textos(p, i) for i in range(3)] == antes                                   # las tres originales, intactas
    assert textos(p, 3)[0] == "Calidad de datos y supuestos"


def test_el_contenido_resume_el_anexo_y_no_inventa_cifras(tmp_path, anexo_dict):
    prs = Presentation(deck_base(tmp_path))
    A.add_quality_annex(prs, anexo_dict, None, 3)
    t = " ".join(textos(prs, 3))
    s = anexo_dict["resumen"]["severidades"]
    assert f"{s['alta']} de severidad alta, {s['media']} media y {s['baja']} baja" in t
    assert "ejemplo o sintético" in t and "no son resultados de producción" in t and "anexo_calidad.json" in t
    assert ("ab" * 8) in t                                                              # prefijo del SHA-256 del libro
    assert "`" not in t and "MXN" not in t
    r = A.resumen(anexo_dict)
    assert r["total"] == 15 and len(r["principales"]) <= A.MAX_HALLAZGOS and all(sv in ("alta", "media") for _, sv, _ in r["principales"])


def test_cada_cifra_impresa_sale_del_anexo(tmp_path, anexo_dict):
    """Ningún número del negocio nuevo: todo lo que tiene dígitos en la diapositiva está en el JSON del anexo."""
    import re
    prs = Presentation(deck_base(tmp_path))
    A.add_quality_annex(prs, anexo_dict, None, 3)
    en_json = json.dumps(anexo_dict, ensure_ascii=False)
    for token in re.findall(r"\d[\d,.]*", " ".join(textos(prs, 3))):
        assert token.strip(".,") in en_json or token.strip(".,") in {"1.0.0"}, token


def test_las_formas_agregadas_llevan_el_prefijo_del_generador_y_la_letra_es_legible(tmp_path, anexo_dict):
    prs = Presentation(deck_base(tmp_path))
    A.add_quality_annex(prs, anexo_dict, None, 3)
    nuevas = [sh.name for sh in prs.slides[3].shapes if sh.name.startswith(A.PREFIJO)]
    assert set(nuevas) == {A.PREFIJO + "hallazgos", A.PREFIJO + "nota"}
    tam = [r.font.size.pt for sh in prs.slides[3].shapes if sh.has_text_frame for p in sh.text_frame.paragraphs for r in p.runs if r.font.size]
    assert tam and min(tam) >= 9                                                        # no baja del mínimo calibrado de las plantillas


def test_aunque_sobren_hallazgos_no_se_satura_la_diapositiva(tmp_path, anexo_dict):
    d = json.loads(json.dumps(anexo_dict))
    nuevos = [{"id": f"X-{i}", "descripcion": "descripción larga " * 12, "severidad": "alta", "naturaleza": "observado", "evidencia": {}, "impacto": "x", "indicadores": []} for i in range(30)]
    next(x for x in d["dimensiones"] if x["id"] == "integridad")["hallazgos"] += nuevos
    d["dimensiones"][13]["hallazgos"] = d["dimensiones"][13]["hallazgos"] * 5                  # muchos no verificables
    prs = Presentation(deck_base(tmp_path))
    A.add_quality_annex(prs, d, None, 3)
    prs.save(tmp_path / "x.pptx")
    assert len(A.resumen(d)["principales"]) == A.MAX_HALLAZGOS
    assert pptx_export.revisar(tmp_path / "x.pptx").errores == []                               # sigue dentro del lienzo y sin errores estructurales
    cuerpo = next(sh for sh in Presentation(tmp_path / "x.pptx").slides[3].shapes if sh.name == BODY)
    assert len(cuerpo.text_frame.text.splitlines()) <= 30


def test_pasa_el_qa_estructural_y_no_dispara_las_comprobaciones_de_cifras_en_su_diapositiva(tmp_path, anexo_dict):
    prs = Presentation(deck_base(tmp_path))
    A.add_quality_annex(prs, anexo_dict, None, 3)
    prs.save(tmp_path / "x.pptx")
    assert pptx_export.revisar(tmp_path / "x.pptx").issues == []
    sin_omitir = cifras.revisar(tmp_path / "x.pptx", set(), set())
    assert any(i.slide == 4 for i in sin_omitir)                                       # sin omitirla, los conteos del anexo se marcarían: de ahí `omitir`
    assert [i for i in cifras.revisar(tmp_path / "x.pptx", set(), set(), omitir={4}) if i.slide == 4] == []


def test_el_anexo_se_pide_por_flag_o_por_peticion_expresa(monkeypatch):
    assert C.anexo_activado(True) is True and C.anexo_activado(False) is False
    assert C.anexo_activado(None) is False                                             # flag `anexo_calidad` apagado por omisión (AC-21)
    from backend.app import config
    cfg = config.cargar("reglas")
    monkeypatch.setattr(C, "anexo_activado", C.anexo_activado)
    import copy
    cfg2 = copy.deepcopy(cfg)
    cfg2["flags"]["anexo_calidad"] = True
    monkeypatch.setattr(config, "cargar", lambda n: cfg2 if n == "reglas" else cfg)
    assert C.anexo_activado(None) is True and C.anexo_activado(False) is False


def test_el_servicio_sin_peticion_no_agrega_la_diapositiva_y_el_json_se_escribe_siempre():
    """Con el flag apagado el PPTX es idéntico a la línea base: `generate` pasa `anexo=None` a los constructores."""
    src = (ROOT / "backend/app/web/service.py").read_text(encoding="utf-8")
    assert "en_deck = anexo_d if calidad.anexo_activado(anexo) else None" in src and src.count("anexo=en_deck") == 2


ESC = {"aetops_mensual_2026-09": "aetops-mensual", "aetops_trimestral_2026-Q3": "aetops-trimestral", "glp1_mensual_2026-09": "glp1-mensual", "glp1_trimestral_2026-Q3": "glp1-trimestral"}


@pytest.mark.parametrize("nombre", sorted(ESC))
def test_decks_de_referencia_con_el_anexo(nombre, tmp_path):
    """Plantillas locales: el deck con anexo = el deck sin anexo + 1 diapositiva al final; mismas cifras; QA estructural y visual sin hallazgos nuevos."""
    tpl = PL.ruta(ESC[nombre])
    if not tpl.exists():
        pytest.skip("OMITIDA (no ejecutada): la plantilla no se versiona y no está disponible")
    sys.path.insert(0, str(ROOT))
    from tools.capture_baseline import _run
    from backend.app import escenarios as E
    from backend.app.build import build_aetops, build_glp1
    unit, period, path, _t, res, _ = _run(nombre)
    u = "glp1" if unit == "GLP1" else "aetops"
    ctx = E.contexto_cacheado(path, period)
    an = C.construir(res, u, period, ctx, {"nombre": path.name}, E.construir(res, u, period, ctx if u == "glp1" else None))
    build = build_aetops if unit == "AETOPS" else build_glp1
    sin = build(res, period, tpl, tmp_path / "sin", render=False)
    con = build(res, period, tpl, tmp_path / "con", render=False, anexo=an)
    ps, pc = Presentation(sin.pptx), Presentation(con.pptx)
    assert len(pc.slides) == len(ps.slides) + 1
    assert [textos(ps, i) for i in range(len(ps.slides))] == [textos(pc, i) for i in range(len(ps.slides))]      # lo existente, idéntico
    assert textos(pc, len(pc.slides) - 1)[0] == "Calidad de datos y supuestos" and con.qa.passed
    assert {(i.id, i.slide) for i in con.qa.issues if i.severity != "info"} == {(i.id, i.slide) for i in sin.qa.issues if i.severity != "info"}   # 0 hallazgos nuevos
    ok, _m = visual.disponible()
    if ok:
        inf = visual.revisar(con.pptx, tmp_path / "v", tpl)
        assert inf["estado"] == "aprobada" and inf["issues"] == [] and len(inf["pngs"]) == len(pc.slides)
