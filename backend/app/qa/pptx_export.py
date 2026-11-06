"""Fase 5 · QA ESTRUCTURAL del PPTX exportado (spec Fase 1 §7.A; RQ-13, RQ-15; AC-14, AC-15).

Se ejecuta sobre el `.pptx` ya guardado y solo LEE su estructura (ZIP, XML, relaciones y formas). **No ve cómo se dibuja la diapositiva**: eso lo
hace el QA visual con render real (`qa/visual.py`). Por eso el informe se rotula siempre «Revisión estructural. La revisión visual requiere render»
y nunca usa la palabra «visual» para sí mismo (AC-15). Funciona en el navegador (Pyodide): solo usa la biblioteca estándar, `lxml`, `python-pptx` y,
si existe, `PIL` (sin él, las imágenes solo se comprueban por su firma).

Qué comprueba (`id` de cada hallazgo):
  Paquete  PPTX_ZIP · PPTX_XML · PPTX_REL_ROTA · PPTX_HUERFANO · PPTX_IMAGEN · PPTX_GRAFICO_VACIO
  Diapositivas  PPTX_TOKEN_TECNICO (error) · PPTX_DUPLICADO · PPTX_TEXTO · PPTX_FUENTE_MIN · PPTX_FUENTE_INCONSISTENTE · PPTX_FUERA_DE_LIENZO ·
                PPTX_SOLAPE_DECLARADO · PPTX_TABLA_VACIA · PPTX_DIAPOSITIVA_VACIA · PPTX_FORMA_CERO
Con una plantilla, los umbrales se CALIBRAN contra ella (lo que la plantilla ya hace no es un defecto del reporte): tamaño mínimo de letra, familias
de fuente, textos estáticos y partes huérfanas heredadas. Sin plantilla se usan los valores por omisión (9 pt).

NO comprueba (limitación declarada, no implementada): trazabilidad de cada cifra impresa a su `Value`, recálculo de fórmulas derivadas,
unidades sin denominador. Esas comprobaciones (`PPTX_CIFRA_NO_TRAZADA`, `PPTX_FORMULA_NO_COINCIDE`, `PPTX_UNIDAD_AMBIGUA`, `PPTX_SIN_DENOMINADOR`
de la spec) exigen asociar cada celda de cada plantilla con su métrica y no están cubiertas: AC-14 queda PARCIAL.
"""
from __future__ import annotations

import hashlib
import posixpath
import re
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from lxml import etree

from .checks import Issue, QAReport

ETIQUETA = "Revisión estructural. La revisión visual requiere render."
FUENTE_MIN_PT = 9.0
TOLERANCIA_EMU = 12700                        # 1 pt: holgura al comparar con el lienzo
TOKEN = re.compile(r"\{\{|\bNone\b|\bnan\b|Decimal\(|\bRI_\w+|KeyError|Traceback", re.UNICODE)
DOBLE_ESPACIO = re.compile(r"\S {2,}\S")
DUP_MIN_CARACTERES = 30
PARTES_ENLAZABLES = ("ppt/slides/", "ppt/media/", "ppt/charts/", "ppt/embeddings/", "ppt/notesSlides/")
IMAGEN = (".png", ".jpg", ".jpeg", ".gif", ".bmp")
FIRMAS = {".png": b"\x89PNG\r\n\x1a\n", ".jpg": b"\xff\xd8\xff", ".jpeg": b"\xff\xd8\xff", ".gif": b"GIF8", ".bmp": b"BM"}
NS_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
NS_C = "{http://schemas.openxmlformats.org/drawingml/2006/chart}"
NS_CX = "{http://schemas.microsoft.com/office/drawing/2014/chartex}"


@dataclass
class Resultado:
    """Informe estructural: lista de hallazgos y la etiqueta obligatoria de sus límites."""
    issues: list
    etiqueta: str = ETIQUETA

    @property
    def errores(self) -> list:
        return [i for i in self.issues if i.severity == "error"]

    def to_dict(self) -> dict:
        return {"etiqueta": self.etiqueta, "errores": len(self.errores), "advertencias": sum(i.severity == "warn" for i in self.issues),
                "issues": [i.__dict__ for i in self.issues]}


def _parser():
    return etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)


# --------------------------------------------------------------------------------------------- paquete
def _resolver(origen: str, destino: str) -> str:
    base = posixpath.dirname(posixpath.dirname(origen))                   # el .rels de «a/b.xml» está en «a/_rels/b.xml.rels»
    return posixpath.normpath(destino.lstrip("/") if destino.startswith("/") else posixpath.join(base, destino))


def _referenciadas(z: zipfile.ZipFile, nombres: set[str]) -> tuple[set[str], list[tuple[str, str]]]:
    """(partes referenciadas, relaciones rotas). Una relación externa no se resuelve."""
    refs, rotas = set(), []
    for n in sorted(nombres):
        if not n.endswith(".rels"):
            continue
        try:
            raiz = etree.fromstring(z.read(n), _parser())
        except Exception:                                                  # noqa: BLE001 — ya lo informa PPTX_XML
            continue
        for rel in raiz.iter(NS_REL + "Relationship"):
            if rel.get("TargetMode") == "External":
                continue
            destino = _resolver(n, rel.get("Target", ""))
            if destino in nombres:
                refs.add(destino)
            else:
                rotas.append((n, rel.get("Target", "")))
    return refs, rotas


def revisar_paquete(path: Path, plantilla: Path | None = None) -> list[Issue]:
    out: list[Issue] = []
    try:
        z = zipfile.ZipFile(path)
    except Exception as e:                                                 # noqa: BLE001
        return [Issue("PPTX_ZIP", "error", None, f"El archivo no es un ZIP legible ({type(e).__name__}).")]
    with z:
        nombres_lista = z.namelist()
        nombres = set(nombres_lista)
        if len(nombres) != len(nombres_lista):
            out.append(Issue("PPTX_ZIP", "error", None, "El ZIP tiene entradas duplicadas."))
        if (malo := z.testzip()) is not None:
            out.append(Issue("PPTX_ZIP", "error", None, f"Entrada dañada en el ZIP: {malo}."))
        inseguras = [n for n in nombres if n.startswith("/") or ".." in n.split("/") or "\\" in n]
        if inseguras:
            out.append(Issue("PPTX_ZIP", "error", None, f"Rutas no permitidas en el ZIP: {sorted(inseguras)[:3]}."))
        for req in ("[Content_Types].xml", "ppt/presentation.xml"):
            if req not in nombres:
                out.append(Issue("PPTX_ZIP", "error", None, f"Falta la parte obligatoria {req}."))
        for n in sorted(nombres):
            if n.endswith((".xml", ".rels")):
                try:
                    etree.fromstring(z.read(n), _parser())
                except Exception as e:                                     # noqa: BLE001
                    out.append(Issue("PPTX_XML", "error", None, f"XML mal formado en {n} ({type(e).__name__})."))
        refs, rotas = _referenciadas(z, nombres)
        for rels, destino in rotas:
            out.append(Issue("PPTX_REL_ROTA", "error", None, f"La relación de {rels} apunta a una parte inexistente: {destino}."))
        heredados = _huerfanos_de(plantilla) if plantilla else set()
        graficas_plantilla = _graficas_de(plantilla) if plantilla else set()
        for n in sorted(nombres):
            if n.startswith(PARTES_ENLAZABLES) and not n.endswith("/") and not n.endswith(".rels") and n not in refs and n not in heredados:
                out.append(Issue("PPTX_HUERFANO", "warn", None, f"Parte sin ninguna relación que la use: {n}."))
        for n in sorted(nombres):
            ext = posixpath.splitext(n)[1].lower()
            if n.startswith("ppt/media/") and ext in IMAGEN:
                datos = z.read(n)
                if not datos.startswith(FIRMAS[ext]) or not _imagen_legible(datos):
                    out.append(Issue("PPTX_IMAGEN", "error", None, f"Imagen dañada o con firma incorrecta: {n}."))
            if n.startswith("ppt/charts/chart") and n.endswith(".xml") and "/_rels/" not in n:
                datos = z.read(n)
                try:
                    raiz = etree.fromstring(datos, _parser())
                except Exception:                                          # noqa: BLE001
                    continue
                if _grafica_vacia(raiz):
                    if hashlib.sha256(datos).hexdigest() in graficas_plantilla:       # la plantilla ya la trae vacía: no es un defecto del reporte
                        out.append(Issue("PPTX_GRAFICO_VACIO", "info", None, f"Gráfica sin datos heredada de la plantilla: {n}."))
                    else:
                        out.append(Issue("PPTX_GRAFICO_VACIO", "error", None, f"Gráfica sin series con datos: {n}."))
    return out


def _grafica_vacia(raiz) -> bool:
    """Gráfica clásica (c:ser con puntos o referencias) o extendida (cx:series con cx:data); sin series con datos = vacía."""
    if raiz.tag.startswith(NS_CX):
        series = list(raiz.iter(NS_CX + "series"))
        return not series or not any(list(raiz.iter(NS_CX + "data")) or list(raiz.iter(NS_CX + "pt")) for _ in series)
    series = list(raiz.iter(NS_C + "ser"))
    vacias = [s for s in series if not list(s.iter(NS_C + "pt")) and not list(s.iter(NS_C + "numLit")) and not list(s.iter(NS_C + "numRef"))]
    return not series or len(vacias) == len(series)


def _graficas_de(plantilla: Path) -> set[str]:
    """SHA-256 de las gráficas que la plantilla ya trae (para distinguir lo heredado)."""
    try:
        with zipfile.ZipFile(plantilla) as z:
            return {hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist() if n.startswith("ppt/charts/chart") and n.endswith(".xml")}
    except Exception:                                                      # noqa: BLE001
        return set()


def _huerfanos_de(plantilla: Path) -> set[str]:
    """Partes huérfanas que la propia plantilla ya trae (no son un defecto del reporte)."""
    try:
        with zipfile.ZipFile(plantilla) as z:
            nombres = set(z.namelist())
            refs, _ = _referenciadas(z, nombres)
            return {n for n in nombres if n.startswith(PARTES_ENLAZABLES) and not n.endswith(".rels") and n not in refs}
    except Exception:                                                      # noqa: BLE001
        return set()


def _imagen_legible(datos: bytes) -> bool:
    try:
        from PIL import Image
    except Exception:                                                      # noqa: BLE001 — sin PIL solo se valida la firma
        return True
    try:
        Image.open(BytesIO(datos)).verify()
        return True
    except Exception:                                                      # noqa: BLE001
        return False


# --------------------------------------------------------------------------------------------- diapositivas
def _marcos(sh):
    """(texto_frame, es_tabla) de una forma; las tablas aportan cada celda."""
    if getattr(sh, "has_table", False) and sh.has_table:
        for fila in sh.table.rows:
            for c in fila.cells:
                yield c.text_frame, True
    elif sh.has_text_frame:
        yield sh.text_frame, False


def _recorrer(prs):
    """(n.º de diapositiva, forma) incluyendo las formas dentro de grupos."""
    def formas(coleccion):
        for sh in coleccion:
            yield sh
            if sh.shape_type == 6:                                         # grupo
                yield from formas(sh.shapes)
    for i, s in enumerate(prs.slides, 1):
        for sh in formas(s.shapes):
            yield i, sh


def _perfil(prs) -> dict:
    """Lo que un deck usa: tamaño mínimo de letra, familias de fuente y textos."""
    tam, fams, textos = [], set(), set()
    for _i, sh in _recorrer(prs):
        for tf, _t in _marcos(sh):
            for p in tf.paragraphs:
                if p.text.strip():
                    textos.add(re.sub(r"\s+", " ", p.text).strip())
                for r in p.runs:
                    if r.font.size:
                        tam.append(r.font.size.pt)
                    if r.font.name:
                        fams.add(r.font.name)
    return {"min": min(tam) if tam else None, "familias": fams, "textos": textos}


def revisar_diapositivas(path: Path, plantilla: Path | None = None, fuente_min: float = FUENTE_MIN_PT) -> list[Issue]:
    from pptx import Presentation
    try:
        prs = Presentation(path)
    except Exception as e:                                                 # noqa: BLE001
        return [Issue("PPTX_ZIP", "error", None, f"python-pptx no puede abrir el archivo ({type(e).__name__}).")]
    base = {"min": None, "familias": set(), "textos": set()}
    if plantilla:
        try:
            base = _perfil(Presentation(plantilla))
        except Exception:                                                  # noqa: BLE001
            pass
    umbral = min(fuente_min, base["min"]) if base["min"] else fuente_min   # la plantilla puede usar letra más chica que el valor por omisión
    ancho, alto = prs.slide_width, prs.slide_height
    out: list[Issue] = []
    por_diapositiva: dict[int, list] = {i: [] for i in range(1, len(prs.slides) + 1)}      # incluye las que no tienen ninguna forma
    for i, sh in _recorrer(prs):
        por_diapositiva.setdefault(i, []).append(sh)
        if sh.left is not None and sh.width is not None and (
                sh.left < -TOLERANCIA_EMU or sh.top < -TOLERANCIA_EMU or sh.left + sh.width > ancho + TOLERANCIA_EMU or sh.top + sh.height > alto + TOLERANCIA_EMU):
            out.append(Issue("PPTX_FUERA_DE_LIENZO", "error", i, f"La forma «{sh.name}» sale del lienzo."))
        if sh.shape_type in (1, 17) and sh.width is not None and (sh.width == 0) != (sh.height == 0) and sh.has_text_frame and sh.text_frame.text.strip():
            out.append(Issue("PPTX_FORMA_CERO", "warn", i, f"La forma con texto «{sh.name}» tiene ancho o alto 0."))
        for tf, _t in _marcos(sh):
            for p in tf.paragraphs:
                texto = p.text
                if m := TOKEN.search(texto):
                    out.append(Issue("PPTX_TOKEN_TECNICO", "error", i, f"Token técnico visible «{m.group(0)}» en «{sh.name}»."))
                if DOBLE_ESPACIO.search(texto) and re.sub(r"\s+", " ", texto).strip() not in base["textos"]:
                    out.append(Issue("PPTX_TEXTO", "warn", i, f"Doble espacio en «{texto[:40]}»."))
                for r in p.runs:
                    if r.font.size and r.text.strip() and r.font.size.pt < umbral - 1e-9:
                        out.append(Issue("PPTX_FUENTE_MIN", "error", i, f"Letra de {r.font.size.pt:g} pt (< {umbral:g} pt) en «{r.text[:30]}»."))
                    if base["familias"] and r.font.name and r.text.strip() and r.font.name not in base["familias"]:
                        out.append(Issue("PPTX_FUENTE_INCONSISTENTE", "warn", i, f"Fuente «{r.font.name}» ausente de la plantilla en «{r.text[:30]}»."))
        if getattr(sh, "has_table", False) and sh.has_table and not any(c.text.strip() for f in sh.table.rows for c in f.cells):
            out.append(Issue("PPTX_TABLA_VACIA", "warn", i, f"La tabla «{sh.name}» no tiene texto en ninguna celda."))
    for i, formas in por_diapositiva.items():
        textos = {}
        for sh in formas:
            if getattr(sh, "has_table", False) and sh.has_table or not sh.has_text_frame:
                continue
            t = re.sub(r"\s+", " ", sh.text_frame.text).strip()
            if len(t) >= DUP_MIN_CARACTERES and t not in base["textos"]:
                if t in textos:
                    out.append(Issue("PPTX_DUPLICADO", "error", i, f"Texto repetido en «{textos[t]}» y «{sh.name}»: «{t[:40]}…»."))
                textos.setdefault(t, sh.name)
        con_texto = any((sh.has_text_frame and sh.text_frame.text.strip()) or (getattr(sh, "has_table", False) and sh.has_table)
                        or getattr(sh, "has_chart", False) and sh.has_chart or sh.shape_type == 13 for sh in formas)
        if not con_texto:
            out.append(Issue("PPTX_DIAPOSITIVA_VACIA", "warn", i, "La diapositiva no tiene texto, tabla, gráfica ni imagen."))
        cajas = [(sh.name, sh.left, sh.top, sh.left + sh.width, sh.top + sh.height) for sh in formas
                 if sh.has_text_frame and sh.text_frame.text.strip() and sh.shape_type == 17 and sh.width]
        for a in range(len(cajas)):
            for b in range(a + 1, len(cajas)):
                if _iou(cajas[a][1:], cajas[b][1:]) > 0.5 and cajas[a][0] != cajas[b][0] \
                        and not {re.sub(r"\s+", " ", _texto_de(formas, cajas[a][0])), re.sub(r"\s+", " ", _texto_de(formas, cajas[b][0]))} <= base["textos"]:
                    out.append(Issue("PPTX_SOLAPE_DECLARADO", "warn", i, f"Los recuadros de texto «{cajas[a][0]}» y «{cajas[b][0]}» se cubren más de la mitad."))
    return out


def _texto_de(formas, nombre: str) -> str:
    return next((sh.text_frame.text for sh in formas if sh.name == nombre and sh.has_text_frame), "")


def _iou(a, b) -> float:
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x1 - x0) * max(0, y1 - y0)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


# --------------------------------------------------------------------------------------------- API
def revisar(path: str | Path, plantilla: str | Path | None = None, fuente_min: float = FUENTE_MIN_PT) -> Resultado:
    """QA estructural completo. Nunca lanza: un archivo ilegible es un hallazgo `PPTX_ZIP`."""
    path = Path(path)
    plantilla = Path(plantilla) if plantilla else None
    issues = revisar_paquete(path, plantilla)
    if not any(i.id in ("PPTX_ZIP", "PPTX_XML", "PPTX_REL_ROTA") and i.severity == "error" for i in issues):   # con el paquete roto, python-pptx no puede leerlo
        try:
            issues += revisar_diapositivas(path, plantilla, fuente_min)
        except Exception as e:                                             # noqa: BLE001 — un archivo extraño es un hallazgo, no una excepción
            issues.append(Issue("PPTX_ZIP", "error", None, f"No se pudieron leer las diapositivas ({type(e).__name__})."))
    return Resultado(issues)


def agregar_a(rep: QAReport, path: str | Path, plantilla: str | Path | None = None) -> Resultado:
    """Añade los hallazgos al `QAReport` de la generación y deja constancia de los límites (AC-15)."""
    res = revisar(path, plantilla)
    for i in res.issues:
        rep.add(i.id, i.severity, i.slide, i.message)
    rep.add("PPTX_REVISION_ESTRUCTURAL", "info", None, ETIQUETA)
    return res
