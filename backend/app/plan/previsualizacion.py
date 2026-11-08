"""Previsualización: la vista previa se construye A PARTIR DEL PPTX guardado (no de un modelo paralelo), de modo que lo que se ve es lo que se exporta.

`modelo(pptx)` extrae, por diapositiva, cada forma con su posición (pt), texto con su formato, tablas e imágenes. La interfaz lo dibuja a escala.
`verificar_correspondencia(modelo, pptx)` comprueba, con un segundo lector independiente (zip + XML, sin python-pptx), que el modelo coincide con el
archivo: huella, número y orden de diapositivas, textos, tablas e imágenes. Una vista previa cuya huella ya no es la del PPTX está OBSOLETA y no se usa.

Límites (se declaran en la interfaz y la documentación): no es un render de PowerPoint. Las tipografías son las del navegador (se pide la de la
plantilla, p. ej. «Aptos Narrow», con respaldo), las gráficas que son imágenes se muestran como imágenes y las gráficas nativas como un recuadro con su tipo, los
colores del tema (no RGB explícito) se dibujan con el color por defecto, y los grupos de formas se muestran como un recuadro. El desborde visual real solo
lo detecta el QA visual con LibreOffice.
"""
from __future__ import annotations

import base64
import hashlib
import re
import zipfile
from collections import Counter
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_COLOR_TYPE, MSO_FILL
from pptx.enum.shapes import MSO_SHAPE_TYPE

from . import reglas

ESQUEMA = "previsualizacion/1"
MAX_IMAGEN = 160_000                      # bytes por imagen embebida
MAX_IMAGENES_TOTAL = 3_000_000
_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_MC = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"


def huella_archivo(pptx: Path | str) -> str:
    return hashlib.sha256(Path(pptx).read_bytes()).hexdigest()


def _color(c) -> str | None:
    try:
        if c is not None and c.type == MSO_COLOR_TYPE.RGB:
            return "#" + str(c.rgb)
    except Exception:                                               # noqa: BLE001 — un color que no se puede leer no impide la vista previa
        return None
    return None


def _relleno(sh) -> str | None:
    try:
        f = sh.fill
        return _color(f.fore_color) if f.type == MSO_FILL.SOLID else None
    except Exception:                                               # noqa: BLE001
        return None


def _pt(emu) -> float:
    return round((emu or 0) * reglas.EMU_PT, 1)


def _parrafos(tf) -> list[dict]:
    out = []
    for p in tf.paragraphs:
        runs = [{"t": r.text, "pt": r.font.size.pt if r.font.size else None, "b": bool(r.font.bold), "i": bool(r.font.italic),
                 "c": _color(r.font.color) if r.font.color else None, "f": r.font.name} for r in p.runs if r.text]
        if not runs and not p.text:
            runs = []
        out.append({"a": str(p.alignment).split(".")[-1].split(" ")[0].lower() if p.alignment is not None else None, "runs": runs})
    return out


def _caja(sh, tr) -> tuple[float, float, float, float]:
    """(x, y, w, h) en pt, con la transformación acumulada de los grupos que contienen la forma (ox, oy, sx, sy, chx, chy)."""
    ox, oy, sx, sy, chx, chy = tr
    return (_pt(ox + ((sh.left or 0) - chx) * sx), _pt(oy + ((sh.top or 0) - chy) * sy), _pt((sh.width or 0) * sx), _pt((sh.height or 0) * sy))


def _transf_grupo(sh, tr) -> tuple:
    """Transformación que un grupo aplica a sus hijos (composición con la de los grupos que lo contienen)."""
    xf = sh._element.grpSpPr.find(_A + "xfrm")
    if xf is None:
        return tr
    g = lambda n, a: int(xf.find(_A + n).get(a))                    # noqa: E731
    try:
        off_x, off_y, ext_x, ext_y = g("off", "x"), g("off", "y"), g("ext", "cx"), g("ext", "cy")
        ch_x, ch_y, che_x, che_y = g("chOff", "x"), g("chOff", "y"), g("chExt", "cx"), g("chExt", "cy")
    except (AttributeError, TypeError, ValueError):
        return tr
    ox, oy, sx, sy, chx, chy = tr
    sx2, sy2 = (ext_x / che_x if che_x else 1.0), (ext_y / che_y if che_y else 1.0)
    # posición del grupo en el espacio padre → espacio absoluto
    return (ox + (off_x - chx) * sx, oy + (off_y - chy) * sy, sx * sx2, sy * sy2, ch_x, ch_y)


_TR0 = (0, 0, 1.0, 1.0, 0, 0)


def _aplanar(shapes, tr=_TR0):
    """(forma, transformación) de todas las formas, entrando en los grupos (su contenido SÍ se muestra y se verifica)."""
    for sh in shapes:
        if sh.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from _aplanar(sh.shapes, _transf_grupo(sh, tr))
        else:
            yield sh, tr


def _forma(sh, z: int, imagenes: dict, presupuesto: list[int], tr=_TR0) -> dict:
    x, y, w, h = _caja(sh, tr)
    d = {"nombre": sh.name or "", "z": z, "x": x, "y": y, "w": w, "h": h, "relleno": _relleno(sh) if not getattr(sh, "has_table", False) else None}
    if getattr(sh, "has_table", False) and sh.has_table:
        t = sh.table
        d["tipo"] = "tabla"
        d["columnas"] = [_pt(c.width) for c in t.columns]
        d["filas"] = [{"h": _pt(r.height), "celdas": [{"parrafos": _parrafos(c.text_frame), "relleno": _relleno(c) if hasattr(c, "fill") else None,
                                                       "span": c.span_width if c.is_merge_origin else 1, "oculta": bool(c.is_spanned)} for c in r.cells]} for r in t.rows]
    elif getattr(sh, "has_chart", False) and sh.has_chart:
        d["tipo"], d["nota"] = "grafica", str(sh.chart.chart_type)
    elif sh.shape_type == MSO_SHAPE_TYPE.PICTURE:
        d["tipo"] = "imagen"
        try:
            blob = sh.image.blob
            h = hashlib.sha1(blob).hexdigest()
            if h not in imagenes:
                if len(blob) <= MAX_IMAGEN and presupuesto[0] + len(blob) <= MAX_IMAGENES_TOTAL:
                    presupuesto[0] += len(blob)
                    imagenes[h] = f"data:{sh.image.content_type};base64,{base64.b64encode(blob).decode()}"
                else:
                    imagenes[h] = None                              # demasiado grande para la vista previa: se muestra un recuadro, no se oculta
            d["imagen"] = h
        except ValueError:                                          # la plantilla trae el marco de imagen sin archivo incrustado: es una propiedad heredada, no un daño
            d["imagen"], d["nota"] = None, "imagen sin recurso incrustado (heredada de la plantilla)"
        except Exception:                                           # noqa: BLE001 — imagen ilegible: la reporta el QA integral
            d["imagen"], d["nota"] = None, "imagen no legible"
    elif sh.has_text_frame and sh.text_frame.text.strip():
        d["tipo"] = "texto"
        d["parrafos"] = _parrafos(sh.text_frame)
        d["ajuste"] = "sin_ajuste_linea" if sh.text_frame.word_wrap is False else "ajuste_linea"
    else:
        d["tipo"] = "forma"
    return d


def _alternativas(slide) -> list[dict]:
    """Contenido `mc:AlternateContent` (p. ej. gráficas avanzadas que PowerPoint dibuja y python-pptx no expone): se muestra un recuadro, no se oculta."""
    out = []
    for k, alt in enumerate(slide._element.cSld.spTree.iter(_MC + "AlternateContent")):
        xf = alt.find(".//" + _P + "xfrm")
        off = xf.find(_A + "off") if xf is not None else None
        ext = xf.find(_A + "ext") if xf is not None else None
        if off is None or ext is None:
            out.append({"nombre": f"AlternateContent {k + 1}", "z": 10_000 + k, "x": 0.0, "y": 0.0, "w": 0.0, "h": 0.0, "relleno": None, "tipo": "grafica",
                        "nota": "contenido alternativo sin geometría"})
            continue
        out.append({"nombre": f"AlternateContent {k + 1}", "z": 10_000 + k, "x": _pt(int(off.get("x"))), "y": _pt(int(off.get("y"))), "w": _pt(int(ext.get("cx"))),
                    "h": _pt(int(ext.get("cy"))), "relleno": None, "tipo": "grafica", "nota": "gráfica avanzada: PowerPoint la dibuja; esta vista previa solo marca su lugar"})
    return out


def modelo(pptx: Path | str, ids: list[str] | None = None, tipos: list[str] | None = None) -> dict:
    """Modelo de la vista previa. `ids`/`tipos`: los del SlideSpec (misma longitud que las diapositivas) para que la interfaz los muestre."""
    prs = Presentation(str(pptx))
    imagenes: dict = {}
    presupuesto = [0]
    diaps = []
    for i, s in enumerate(prs.slides, 1):
        fondo = None
        try:
            if s.background.fill.type == MSO_FILL.SOLID:
                fondo = _color(s.background.fill.fore_color)
        except Exception:                                           # noqa: BLE001
            fondo = None
        diaps.append({"indice": i, "sld_id": s.slide_id, "id": ids[i - 1] if ids and len(ids) == len(prs.slides) else None,
                      "tipo": tipos[i - 1] if tipos and len(tipos) == len(prs.slides) else None, "fondo": fondo,
                      "formas": [_forma(sh, z, imagenes, presupuesto, tr) for z, (sh, tr) in enumerate(_aplanar(s.shapes))] + _alternativas(s)})
    return {"esquema": ESQUEMA, "huella": huella_archivo(pptx), "ancho_pt": _pt(prs.slide_width), "alto_pt": _pt(prs.slide_height),
            "diapositivas": diaps, "imagenes": imagenes}


# ------------------------------------------------------------------------------------------------- correspondencia con el archivo (lector independiente)
def _tokens(t: str) -> Counter:
    return Counter(re.findall(r"\S+", t))


def _texto_modelo(d: dict) -> Counter:
    c: Counter = Counter()
    for f in d["formas"]:
        for p in f.get("parrafos", []):
            c += _tokens(" ".join(r["t"] for r in p["runs"]))
        for fila in f.get("filas", []):
            for ce in fila["celdas"]:
                for p in ce["parrafos"]:
                    c += _tokens(" ".join(r["t"] for r in p["runs"]))
    return c


def _lectura_xml(pptx: Path | str) -> list[dict]:
    """[{sld_id, texto: Counter, tablas, imagenes, graficas}] en el orden de `sldIdLst`, leyendo el zip y el XML directamente."""
    with zipfile.ZipFile(str(pptx)) as z:
        pres = etree.fromstring(z.read("ppt/presentation.xml"))
        rels = etree.fromstring(z.read("ppt/_rels/presentation.xml.rels"))
        destino = {r.get("Id"): r.get("Target") for r in rels}
        out = []
        for sid in pres.iter(_P + "sldId"):
            ruta = destino[sid.get(_R + "id")]
            ruta = ruta if ruta.startswith("/") else "ppt/" + ruta
            ruta = ruta.lstrip("/")
            x = etree.fromstring(z.read(ruta))
            texto: Counter = Counter()
            for t in x.iter(_A + "t"):
                texto += _tokens(t.text or "")
            graficas = sum(1 for g in x.iter(_A + "graphicData") if g.get("uri", "").endswith("/chart") and not any(a.tag == _MC + "AlternateContent" for a in g.iterancestors()))
            out.append({"sld_id": int(sid.get("id")), "texto": texto, "tablas": len(list(x.iter(_A + "tbl"))),
                        "imagenes": sum(1 for p in x.iter(_P + "pic") if not any(a.tag == _MC + "AlternateContent" for a in p.iterancestors())),
                        "graficas": graficas + len(list(x.iter(_MC + "AlternateContent")))})
        return out


def verificar_correspondencia(m: dict, pptx: Path | str) -> list[tuple[str, int | None, str]]:
    """[(código, n.º de diapositiva | None, mensaje)]: vacío = la vista previa corresponde exactamente al PPTX."""
    out: list[tuple[str, int | None, str]] = []
    if m.get("esquema") != ESQUEMA:
        return [("PREVIEW_ESQUEMA", None, "La vista previa no tiene el esquema esperado.")]
    if m.get("huella") != huella_archivo(pptx):
        return [("PREVIEW_OBSOLETA", None, "La vista previa no corresponde al archivo PPTX actual (su huella cambió): debe regenerarse.")]
    try:
        real = _lectura_xml(pptx)
    except Exception as e:                                          # noqa: BLE001 — si el archivo no se puede leer, eso ES el hallazgo
        return [("PREVIEW_ARCHIVO_ILEGIBLE", None, f"No se pudo leer el PPTX para compararlo con la vista previa ({type(e).__name__}).")]
    dm = m["diapositivas"]
    if len(dm) != len(real):
        return [("PREVIEW_NUM_DIAPOSITIVAS", None, f"La vista previa tiene {len(dm)} diapositivas y el PPTX {len(real)}.")]
    for i, (a, b) in enumerate(zip(dm, real), 1):
        if a["sld_id"] != b["sld_id"]:
            out.append(("PREVIEW_ORDEN", i, f"La diapositiva {i} es la {a['sld_id']} en la vista previa y la {b['sld_id']} en el PPTX (distinto orden)."))
            continue
        if _texto_modelo(a) != b["texto"]:
            out.append(("PREVIEW_TEXTO", i, f"El texto de la diapositiva {i} no coincide entre la vista previa y el PPTX."))
        if sum(1 for f in a["formas"] if f["tipo"] == "tabla") != b["tablas"]:
            out.append(("PREVIEW_TABLAS", i, f"El número de tablas de la diapositiva {i} no coincide."))
        if sum(1 for f in a["formas"] if f["tipo"] == "imagen") != b["imagenes"]:
            out.append(("PREVIEW_IMAGENES", i, f"El número de imágenes de la diapositiva {i} no coincide."))
        if sum(1 for f in a["formas"] if f["tipo"] == "grafica") != b["graficas"]:
            out.append(("PREVIEW_GRAFICAS", i, f"El número de gráficas de la diapositiva {i} no coincide."))
    return out
