"""Genera las PLANTILLAS SINTÉTICAS de prueba a partir de las plantillas reales (que no se versionan).

Por qué existen: las pruebas de integración, de navegador y de rendimiento necesitan una plantilla PPTX con la estructura real (nombres de shapes, tamaños de tabla, geometría,
texto de rótulos que el relleno busca) para ejecutarse en CI, y las plantillas reales contienen marca y datos comerciales (por eso no se versionan, `templates/README.md`).
Una plantilla sintética conserva TODO lo que el relleno y el QA necesitan y elimina lo sensible:

  conserva   nombres, tipos, geometría y orden de los shapes; tamaños de tabla; formatos de run, párrafo y celda; colores (el relleno de GLP-1 lee el rojo de la plantilla);
             rótulos cortos y estructurales (títulos, encabezados de tabla, rótulos con trimestre o año); el pie de página genérico; la longitud y el reparto de palabras de cada
             texto narrativo (el relleno calcula la capacidad de cada cuadro con el volumen del texto original).
  elimina    logotipos e imágenes (se sustituyen por imágenes neutras del mismo tamaño y formato), la miniatura del paquete, autor y metadatos de la presentación, los números de las
             tablas y de los textos (todo dígito pasa a «0» salvo años y trimestres de los rótulos) y el contenido de los textos narrativos (se sustituyen, letra por letra, por
             texto de relleno de la misma longitud).

Uso (solo con las plantillas reales a mano; el resultado SÍ se versiona en tests/fixtures/plantillas_sinteticas/):
    python tools/make_plantillas_sinteticas.py [--origen templates] [--destino tests/fixtures/plantillas_sinteticas]
La prueba tests/unit/test_plantillas_sinteticas.py comprueba, en CI, que lo versionado no contiene nada de lo eliminado.
"""
from __future__ import annotations

import argparse
import io
import re
import zipfile
from pathlib import Path

from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
FORMATOS = ("aetops-mensual", "aetops-trimestral", "glp1-mensual", "glp1-trimestral")
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
P = "http://schemas.openxmlformats.org/presentationml/2006/main"
NS = {"a": f"{{{A}}}", "p": f"{{{P}}}"}
RELLENO = "ejemplo"                                   # alfabeto del texto de relleno (la prueba de fuga lo exige)
LARGO_NARRATIVO = 45                                  # un cuadro de texto con más caracteres es narrativa, no rótulo
PIE = "La información presentada es recopilada y gestionada por el Departamento de E-Commerce con el fin de mejorar la experiencia del usuario."
SVG_NEUTRO = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96"><rect x="8" y="8" width="80" height="80" fill="#D9D9D9"/></svg>'


def _relleno(texto: str) -> str:
    """Misma longitud, mismas palabras (largo y puntuación), letras sustituidas por las de «ejemplo»; dígitos a 0."""
    out, i = [], 0
    for ch in texto:
        if ch.isalpha():
            c = RELLENO[i % len(RELLENO)]
            out.append(c.upper() if ch.isupper() else c)
            i += 1
        elif ch.isdigit():
            out.append("0")
        else:
            out.append(ch)
    return "".join(out)


def _es_rotulo(texto: str) -> bool:
    """Rótulo estructural: letras y, como mucho, trimestres («Q1») o años («2026»); sin otras cifras."""
    t = texto.strip()
    if len(t) > 60 or not re.search(r"[A-Za-zÁÉÍÓÚÜáéíóúüñÑ]", t):
        return False
    return not re.search(r"\d", re.sub(r"Q[1-4]|\b20\d\d\b", "", t))


def _parrafo_sin_cifras(p) -> None:
    """Un párrafo que es un rótulo se conserva entero; si no, todo dígito pasa a «0» (la longitud no cambia). El rótulo se juzga con el párrafo completo, no por run."""
    ts = [t for t in p.iter(f"{NS['a']}t") if t.text]
    texto = "".join(t.text for t in ts)
    if not any(c.isdigit() for c in texto) or _es_rotulo(texto):
        return
    for t in ts:
        t.text = re.sub(r"\d", "0", t.text)


def _texto_de(elem) -> str:
    return "".join(t.text or "" for t in elem.iter(f"{NS['a']}t"))


def _es_pie(sp) -> bool:
    ph = sp.find(f".//{NS['p']}ph")
    return ph is not None and ph.get("type") in ("ftr", "sldNum", "dt")


def sanear_xml(datos: bytes) -> bytes:
    raiz = etree.fromstring(datos)
    for tc in raiz.iter(f"{NS['a']}tc"):                                     # tablas: cada celda conserva su rótulo o pierde sus cifras
        for p in tc.iter(f"{NS['a']}p"):
            _parrafo_sin_cifras(p)
    for sp in raiz.iter(f"{NS['p']}sp"):                                     # cuadros de texto: narrativa -> relleno de la misma longitud; rótulos -> se conservan
        if _es_pie(sp):
            continue
        if len(_texto_de(sp)) > LARGO_NARRATIVO:
            for t in sp.iter(f"{NS['a']}t"):
                if t.text:
                    t.text = _relleno(t.text)
        else:
            for p in sp.iter(f"{NS['a']}p"):
                _parrafo_sin_cifras(p)
    return etree.tostring(raiz, xml_declaration=True, encoding="UTF-8", standalone=True)


def _png_neutro(original: bytes) -> bytes:
    from PIL import Image
    try:
        im = Image.open(io.BytesIO(original))
        tam, modo = im.size, im.mode
    except Exception:                                                    # noqa: BLE001
        tam, modo = (16, 16), "RGBA"
    color = (217, 217, 217, 255) if modo in ("RGBA", "LA", "P") else (217, 217, 217)
    nuevo = Image.new("RGBA" if len(color) == 4 else "RGB", tam, color)
    b = io.BytesIO()
    nuevo.save(b, "PNG")
    return b.getvalue()


APP_XML = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
           'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>Plantilla sintética de prueba</Application></Properties>').encode("utf-8")
CORE_XML = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>Plantilla sintética de prueba</dc:title><dc:creator></dc:creator>'
            '<cp:lastModifiedBy></cp:lastModifiedBy><dcterms:created xsi:type="dcterms:W3CDTF">2000-01-01T00:00:00Z</dcterms:created>'
            '<dcterms:modified xsi:type="dcterms:W3CDTF">2000-01-01T00:00:00Z</dcterms:modified></cp:coreProperties>').encode("utf-8")


def sanear(origen: Path, destino: Path) -> None:
    zin = zipfile.ZipFile(origen)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in sorted(zin.infolist(), key=lambda i: i.filename):       # orden fijo: la construcción es determinista
            n, datos = info.filename, zin.read(info.filename)
            if n.startswith("docProps/thumbnail"):
                continue                                                    # miniatura con la imagen de la marca
            if n == "docProps/app.xml":
                datos = APP_XML
            elif n == "docProps/core.xml":
                datos = CORE_XML
            elif n == "_rels/.rels":
                datos = re.sub(rb"<Relationship [^>]*thumbnail[^>]*/>", b"", datos)
            elif n.startswith("ppt/media/"):
                ext = n.rsplit(".", 1)[-1].lower()
                datos = _png_neutro(datos) if ext == "png" else SVG_NEUTRO.encode("utf-8") if ext == "svg" else _png_neutro(datos)
                if ext not in ("png", "svg"):
                    raise SystemExit(f"Formato de imagen no previsto en la plantilla: {n}")
            elif n.endswith(".xml") and (n.startswith(("ppt/slides/slide", "ppt/slideLayouts/", "ppt/slideMasters/", "ppt/notesSlides/", "ppt/notesMasters/"))):
                datos = sanear_xml(datos)
            zi = zipfile.ZipInfo(n, date_time=(2000, 1, 1, 0, 0, 0))        # fecha fija
            zi.compress_type = zipfile.ZIP_DEFLATED
            zout.writestr(zi, datos)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--origen", type=Path, default=ROOT / "templates")
    ap.add_argument("--destino", type=Path, default=ROOT / "tests" / "fixtures" / "plantillas_sinteticas")
    a = ap.parse_args(argv)
    for f in FORMATOS:
        src = a.origen / f / "1" / "template.pptx"
        if not src.exists():
            raise SystemExit(f"Falta la plantilla real {src}: este script solo se ejecuta con las plantillas reales a mano.")
        dst = a.destino / f / "1" / "template.pptx"
        sanear(src, dst)
        print(f"{f}: {src.stat().st_size // 1024} KB -> {dst.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
