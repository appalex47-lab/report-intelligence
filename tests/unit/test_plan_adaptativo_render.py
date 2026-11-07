"""Diseño adaptativo con render REAL (LibreOffice): demuestra que el ajuste corrige un desborde que el render sí ve. No corre sin LibreOffice y pdftotext:
se OMITE con motivo (nunca se da por aprobado)."""
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import _deck as D                                                           # noqa: E402

from backend.app.plan import adaptativo as ad, slidespec as ss              # noqa: E402
from backend.app.qa import checks, visual                                   # noqa: E402

pytestmark = pytest.mark.skipif(not (shutil.which("soffice") or shutil.which("libreoffice")) or not shutil.which("pdftotext"),
                                reason="OMITIDA (no ejecutada): hace falta LibreOffice y pdftotext para el render real")

TEXTO = "Frase de prueba bastante larga para ocupar varias líneas dentro del cuadro de texto de la diapositiva. " * 11


def _hallazgos(p, tmp_path, nombre):
    out = tmp_path / nombre
    out.mkdir()
    pdf = checks.convert_to_pdf if hasattr(checks, "convert_to_pdf") else None
    from backend.app.render import convert_to_pdf
    pdfp = convert_to_pdf(p, out)
    rep = checks.QAReport()
    checks.check_render(p, pdfp, rep)
    return [(i.id, i.message) for i in rep.issues if i.severity == "error"], pdfp


def _desborde(pdfp, ancho=960.0, alto=540.0, limite_y=None):
    """Palabras del cuerpo por debajo de `limite_y` (pt): el texto invadió la zona de la nota fija."""
    pag = checks.pdf_words(pdfp)[0]
    return [w for w in pag["words"] if w[1] >= limite_y and not w[4].startswith("Nota")]


def test_el_texto_que_desborda_su_cuadro_invade_la_nota_de_abajo_y_tras_el_ajuste_ya_no(tmp_path):
    base = {"titulo": "Panorama General", "cuerpo": TEXTO, "caja": (40, 90, 880, 90), "obstaculo": (40, 196, 880, 30), "pt_cuerpo": 16, "auto": False}
    sin, con = D.crear(tmp_path / "sin.pptx", [base]), D.crear(tmp_path / "con.pptx", [base])
    spec = ss.construir(con, set(), set(), "t", "x/y", [])
    inf = ad.adaptar(con, [s.id for s in spec.diapositivas], [s.densidad for s in spec.diapositivas], aplicar=True)
    assert inf.modificado
    # tope de la zona del cuerpo: el borde superior de la nota fija
    tope = 196.0
    _, pdf_sin = _hallazgos(sin, tmp_path, "r_sin")
    _, pdf_con = _hallazgos(con, tmp_path, "r_con")
    invade_sin, invade_con = _desborde(pdf_sin, limite_y=tope), _desborde(pdf_con, limite_y=tope)
    assert len(invade_sin) > 0, "la prueba no reproduce un desborde real: sin ajuste el texto debería pasar de la nota"
    assert len(invade_con) < len(invade_sin)                                             # el ajuste reduce el texto que invade la zona de abajo


def test_el_reporte_visual_del_pptx_ajustado_no_marca_texto_fuera_de_pagina(tmp_path):
    base = {"titulo": "Panorama General", "cuerpo": TEXTO, "caja": (40, 90, 880, 60), "pt_cuerpo": 16}
    p = D.crear(tmp_path / "a.pptx", [base])
    spec = ss.construir(p, set(), set(), "t", "x/y", [])
    ad.adaptar(p, [s.id for s in spec.diapositivas], [s.densidad for s in spec.diapositivas], aplicar=True)
    err, _ = _hallazgos(p, tmp_path, "r")
    assert not [e for e in err if e[0] in ("TEXT_OUT_OF_PAGE", "PAGE_COUNT_MISMATCH")]
