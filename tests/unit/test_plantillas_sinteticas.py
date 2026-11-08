"""Plantillas sintéticas de prueba (tests/fixtures/plantillas_sinteticas/): no contienen marca ni datos comerciales y conservan lo que el relleno necesita.

Corre en CI (solo lee lo versionado). La comparación con las plantillas reales se hace únicamente donde estas existen (equipo de desarrollo) y se OMITE con motivo en CI."""
import io
import re
import zipfile
from pathlib import Path

import pytest
from lxml import etree
from PIL import Image
from pptx import Presentation

from tests import plantillas as PL

A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
SINT = {f: PL.SINTETICAS / f / "1" / "template.pptx" for f in PL.FORMATOS}
PIE = "La información presentada es recopilada y gestionada por el Departamento de E-Commerce con el fin de mejorar la experiencia del usuario."


@pytest.mark.parametrize("formato", PL.FORMATOS)
def test_estan_versionadas_y_se_abren(formato):
    assert SINT[formato].exists() and SINT[formato].stat().st_size < 200_000
    prs = Presentation(str(SINT[formato]))
    assert len(prs.slides) in (8, 11)


@pytest.mark.parametrize("formato", PL.FORMATOS)
def test_no_tienen_marca_ni_metadatos_ni_imagenes_reales(formato):
    z = zipfile.ZipFile(SINT[formato])
    nombres = z.namelist()
    assert not [n for n in nombres if "thumbnail" in n]                                          # la miniatura reproduce la lámina con su marca
    core, app = z.read("docProps/core.xml").decode("utf-8"), z.read("docProps/app.xml").decode("utf-8")
    assert "<dc:creator></dc:creator>" in core and "<cp:lastModifiedBy></cp:lastModifiedBy>" in core and "Plantilla sintética" in core
    assert "<Company>" not in app and "TitlesOfParts" not in app and "Microsoft" not in app    # sin empresa, sin títulos de láminas, sin aplicación de origen
    for n in nombres:
        if n.startswith("ppt/media/"):
            if n.endswith(".png"):
                im = Image.open(io.BytesIO(z.read(n))).convert("RGBA")
                assert len(im.getcolors(maxcolors=4)) == 1, f"{n}: la imagen no es neutra (un solo color)"
            elif n.endswith(".svg"):
                assert z.read(n).decode("utf-8").count("<path") == 0 and "Icons_" not in z.read(n).decode("utf-8")
            else:
                pytest.fail(f"formato de imagen no previsto: {n}")


@pytest.mark.parametrize("formato", PL.FORMATOS)
def test_no_conservan_cifras_ni_narrativa_de_los_reportes_originales(formato):
    """Todo texto largo (narrativa) es relleno de la misma longitud con las letras de «ejemplo»; ninguna cifra de tabla o texto sobrevive (solo años y trimestres de rótulos)."""
    z = zipfile.ZipFile(SINT[formato])
    for n in z.namelist():
        if not (n.startswith("ppt/slides/slide") and n.endswith(".xml")):
            continue
        raiz = etree.fromstring(z.read(n))
        for sp in raiz.iter(f"{P}sp"):
            ph = sp.find(f".//{P}ph")
            texto = "".join(t.text or "" for t in sp.iter(f"{A}t"))
            if ph is not None and ph.get("type") in ("ftr", "sldNum", "dt"):
                assert texto in (PIE, "") or texto.strip().isdigit() or texto == "‹#›", (n, texto[:60])
            elif len(texto) > 45:
                assert all(c in "ejmplo" for c in texto.lower() if c.isalpha()) and all(c == "0" for c in texto if c.isdigit()), (n, texto[:80])      # letras de «ejemplo» y ceros
        for t in raiz.iter(f"{A}t"):
            resto = re.sub(r"Q[1-4]|\b20\d\d\b", "", t.text or "")
            assert not re.search(r"[1-9]", resto) or (t.getparent() is not None and re.fullmatch(r"\d{1,2}", (t.text or "").strip())), (n, t.text)    # solo el número de diapositiva


@pytest.mark.parametrize("formato", PL.FORMATOS)
def test_conservan_la_estructura_que_necesita_el_relleno(formato):
    prs = Presentation(str(SINT[formato]))
    nombres = [sh.name for s in prs.slides for sh in s.shapes]
    assert any(n.startswith("Tabla") for n in nombres) and any(n.startswith("CuadroTexto") for n in nombres) and any("Marcador de pie" in n for n in nombres)
    tablas = [(len(sh.table.rows), len(sh.table.columns)) for s in prs.slides for sh in s.shapes if sh.has_table]
    assert tablas and all(f > 0 and c > 0 for f, c in tablas)
    assert (prs.slide_width, prs.slide_height) == (12192000, 6858000)


@pytest.mark.parametrize("formato", PL.FORMATOS)
def test_la_estructura_es_identica_a_la_de_la_plantilla_real(formato):
    real = PL.REALES / formato / "1" / "template.pptx"
    if not real.exists():
        pytest.skip(f"OMITIDA (no ejecutada): la plantilla real {formato} no está en este equipo (no se versiona)")

    def estructura(path):
        out = []
        for s in Presentation(str(path)).slides:
            for sh in s.shapes:
                fila = (sh.name, str(sh.shape_type), sh.left, sh.top, sh.width, sh.height)
                if sh.has_table:
                    fila += (len(sh.table.rows), len(sh.table.columns), tuple(c.width for c in sh.table.columns), tuple(r.height for r in sh.table.rows))
                if sh.has_text_frame:
                    fila += (len(sh.text_frame.text), len(sh.text_frame.paragraphs), tuple(len(r.text) for pa in sh.text_frame.paragraphs for r in pa.runs))
                out.append(fila)
        return out
    assert estructura(SINT[formato]) == estructura(real)


def test_la_seleccion_de_plantillas_nunca_mezcla_reales_y_sinteticas(monkeypatch):
    monkeypatch.setenv("REPORT_PLANTILLAS", "sinteticas")
    assert PL.origen() == "sinteticas" and all(PL.ruta(f).is_relative_to(PL.SINTETICAS) for f in PL.FORMATOS)
