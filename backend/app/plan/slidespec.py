"""SlideSpec: especificación estructurada y estable de cada diapositiva del reporte.

Se DERIVA del PPTX generado (que sigue siendo el producto de los generadores por plantilla) más los valores del motor, de modo que la especificación,
la vista previa y el archivo exportado describen exactamente lo mismo. Cada diapositiva tiene:
* un identificador estable `tipo:sldId` (el `sldId` de OOXML no cambia al reordenar ni depende del título ni de la posición);
* tipo, objetivo, título, mensaje principal, bloques (texto, tablas, imágenes, gráficas), métricas con su estado (real / estimado / no disponible /
  sin respaldo), visualizaciones, fuentes, restricciones de espacio, densidad y notas;
* un estado propio y una validación que se puede ejecutar ANTES de representarla.
Reglas de integridad: nunca se inventa una métrica ni un periodo; un dato faltante se declara («no_disponible»); una cifra sin valor del motor se
marca «sin_respaldo» y el QA la informa; las estimaciones se distinguen de los datos reales.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

from ..qa import cifras
from . import reglas
from .escenario import TIPOS_DIAPOSITIVA

ESQUEMA = "slidespec/1"
ESTADOS_METRICA = ("real", "estimado", "no_disponible", "sin_respaldo")
DENSIDADES = ("pocos_elementos", "multiples_kpis", "tabla", "grafico", "narrativa_extensa", "mixta")
_ID = re.compile(r"[a-z_]+:\d{1,6}")

# El orden importa: la primera coincidencia gana. Se aplica al TÍTULO (los títulos repetidos son normales: dos «Análisis de Productos»).
_TIPOS = (
    ("resumen_ejecutivo", re.compile(r"^\s*resumen ejecutivo", re.I)),
    ("recomendaciones", re.compile(r"^\s*recomendaciones", re.I)),
    ("conclusiones", re.compile(r"^\s*conclusiones", re.I)),
    ("panorama", re.compile(r"panorama", re.I)),
    ("negados", re.compile(r"negados", re.I)),
    ("productos", re.compile(r"productos", re.I)),
    ("categorias", re.compile(r"categor[ií]as", re.I)),
    ("canales", re.compile(r"canales", re.I)),
    ("lineas", re.compile(r"l[ií]neas", re.I)),
    ("perfil_paciente", re.compile(r"qui[eé]n busca", re.I)),
    ("comportamiento_compra", re.compile(r"comportamiento de compra", re.I)),
    ("engagement_digital", re.compile(r"engagement", re.I)),
)
# Objetivo por tipo: solo lo que la documentación define (OBJETIVO_Y_NARRATIVA §1, extras y anexo). El resto es None («no definido»).
_OBJETIVO = {
    "panorama": "Mostrar el nivel de venta y su variación contra el año anterior y el periodo anterior, y si el crecimiento viene de volumen o de precio y mezcla.",
    "canales": "Identificar qué canales explican el resultado: aporte y cambio de participación.",
    "lineas": "Identificar qué líneas explican el resultado: aporte y cambio de participación.",
    "categorias": "Identificar qué categorías explican el resultado: aporte y cambio de participación.",
    "productos": "Mostrar los productos líderes, las mayores alzas y bajas, y de qué línea vienen.",
    "negados": "Mostrar la venta negada como porcentaje de la venta y su concentración por línea y producto.",
    "conclusiones": "Indicar qué sostener, qué vigilar y dónde hay venta por recuperar.",
    "recomendaciones": "Proponer acciones priorizadas: qué hacer, por qué, cuánto está en juego y qué métrica seguir.",
    "descubrimiento": "Mostrar los hallazgos propuestos por IA y validados por la persona usuaria.",
    "anexo_calidad": "Informar la calidad de los datos y los supuestos del reporte.",
}


@dataclass
class Bloque:
    tipo: str                           # texto | tabla | imagen | grafica
    forma: str                          # nombre de la forma en el PPTX
    resumen: str = ""
    caracteres: int = 0
    filas: int | None = None
    columnas: int | None = None
    decorativo: bool = False            # imagen que se repite en casi todas las diapositivas (marca/fondo de la plantilla)


@dataclass
class Metrica:
    texto: str                          # tal como está impreso
    estado: str                         # real | estimado | no_disponible | sin_respaldo
    forma: str = ""
    fuente: str | None = None           # archivo de origen cuando el valor se traza al motor


@dataclass
class SlideSpec:
    id: str
    tipo: str
    titulo: str | None
    objetivo: str | None
    mensaje: str | None
    sld_id: int
    indice: int                         # informativo (1-based); NUNCA es la clave
    bloques: list[Bloque] = field(default_factory=list)
    metricas: list[Metrica] = field(default_factory=list)
    visualizaciones: list[str] = field(default_factory=list)
    fuentes: list[str] = field(default_factory=list)
    densidad: str = "pocos_elementos"
    restricciones: dict = field(default_factory=dict)
    notas: list[str] = field(default_factory=list)
    agregada: bool = False              # la añadió el generador (descubrimiento, anexo) en lugar de venir de la plantilla
    estado: str = "completa"            # completa | con_avisos | incompleta
    avisos: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SpecReporte:
    escenario_id: str
    perfil: str
    diapositivas: list[SlideSpec]
    ancho_pt: float
    alto_pt: float
    esquema: str = ESQUEMA

    def to_dict(self) -> dict:
        d = {"esquema": self.esquema, "escenario_id": self.escenario_id, "perfil": self.perfil, "ancho_pt": self.ancho_pt, "alto_pt": self.alto_pt,
             "diapositivas": [s.to_dict() for s in self.diapositivas]}
        d["huella"] = hashlib.sha256(json.dumps(d, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        return d

    def por_id(self) -> dict[str, SlideSpec]:
        return {s.id: s for s in self.diapositivas}


# -------------------------------------------------------------------------------------------------------------------- lectura de formas
def _es_marcador(sh) -> bool:
    return (sh.name or "").startswith("Marcador")


def _tamano_max(sh) -> float:
    if not sh.has_text_frame:
        return 0.0
    t = [r.font.size.pt for p in sh.text_frame.paragraphs for r in p.runs if r.font.size]
    return max(t) if t else 0.0


def titulo_de(slide) -> tuple[str | None, str | None]:
    """(texto, forma) del título: entre los cuadros de texto CORTOS (≤ 120 caracteres, ≤ 2 párrafos) de la parte alta de la diapositiva (30 %), el de mayor
    tamaño de letra y, a igualdad, el más alto. Un cuerpo de texto largo nunca se toma por título: una diapositiva sin título se detecta como tal."""
    try:
        alto = slide.part.package.presentation_part.presentation.slide_height
    except AttributeError:
        alto = None
    mejor = None
    for sh in slide.shapes:
        if not (sh.has_text_frame and sh.text_frame.text.strip()) or _es_marcador(sh) or (sh.name or "").startswith(reglas.PREFIJO_AGREGADA):
            continue
        texto = " ".join(sh.text_frame.text.split())
        pars = [p for p in sh.text_frame.paragraphs if p.text.strip()]
        if len(texto) > 120 or len(pars) > 2 or (alto and (sh.top or 0) > 0.30 * alto):
            continue
        k = (-_tamano_max(sh), sh.top or 0)
        if mejor is None or k < mejor[0]:
            mejor = (k, texto, sh.name)
    return (mejor[1], mejor[2]) if mejor else (None, None)


def clasificar(titulo: str | None, nombres: list[str]) -> str:
    if any(n.startswith("RI_anexo_") for n in nombres):
        return "anexo_calidad"
    if any(n.startswith("RI_descubrimiento_") for n in nombres):
        return "descubrimiento"
    for tipo, rx in _TIPOS:
        if titulo and rx.search(titulo):
            return tipo
    return "contenido"


def _hash_imagen(sh) -> str:
    """Identidad de una imagen para detectar la que se repite en todas las diapositivas: el hash del archivo incrustado o, si la plantilla la trae sin
    imagen incrustada, su nombre y tamaño."""
    try:
        return hashlib.sha1(sh.image.blob).hexdigest()
    except Exception:                                               # noqa: BLE001 — una imagen ilegible la reporta el QA, no rompe la especificación
        return f"sin-recurso:{sh.name}:{sh.width}x{sh.height}"


def _densidad(n_tablas: int, n_graficas: int, chars: int, n_metricas: int) -> str:
    if n_tablas and chars >= 350:
        return "mixta"
    if n_tablas:
        return "tabla"
    if n_graficas and chars >= 350:
        return "mixta"
    if n_graficas:
        return "grafico"
    if chars >= 900:
        return "narrativa_extensa"
    if n_metricas >= 6:
        return "multiples_kpis"
    return "pocos_elementos"


def _limpiar(t: str) -> str:
    return re.sub(r"\s+", " ", t.replace("**", "")).strip()


def _estado_texto(t: str) -> str | None:
    low = t.lower()
    if any(x in low for x in reglas.SIN_DATO):
        return "no_disponible"
    if any(x in low for x in reglas.ESTIMACION):
        return "estimado"
    return None


# -------------------------------------------------------------------------------------------------------------------- construcción
def construir(pptx: Path | str, valores_motor, narrativa: set[str] | None, escenario_id: str, perfil: str, fuentes: list[str] | None = None) -> SpecReporte:
    """SlideSpec del reporte a partir del PPTX guardado. `valores_motor`: `cifras.recolectar_valores(result)`; `narrativa`: cifras de los textos verificados."""
    prs = Presentation(str(pptx))
    ind = cifras.Indice(valores_motor or [])
    narrativa = narrativa or set()
    fuentes = [f for f in (fuentes or []) if f]
    slides = list(prs.slides)
    # Una imagen que está en ≥ 80 % de las diapositivas es marca/fondo de la plantilla, no una visualización del reporte.
    conteo: dict[str, int] = {}
    for s in slides:
        for h in {_hash_imagen(sh) for sh in s.shapes if sh.shape_type == MSO_SHAPE_TYPE.PICTURE}:
            conteo[h] = conteo.get(h, 0) + 1
    repetidas = {h for h, n in conteo.items() if len(slides) >= 4 and n >= 0.8 * len(slides)}
    out: list[SlideSpec] = []
    ancho, alto = prs.slide_width * reglas.EMU_PT, prs.slide_height * reglas.EMU_PT
    for i, s in enumerate(slides, 1):
        nombres = [sh.name or "" for sh in s.shapes]
        titulo, forma_titulo = titulo_de(s)
        tipo = clasificar(titulo, nombres)
        bloques: list[Bloque] = []
        metricas: list[Metrica] = []
        textos: list[tuple[str, str]] = []                          # (forma, texto) del cuerpo, para el mensaje
        chars = 0
        nt = ng = 0
        for sh in s.shapes:
            if _es_marcador(sh) or sh.name == forma_titulo:
                continue
            if getattr(sh, "has_table", False) and sh.has_table:
                nt += 1
                filas = [[c.text_frame.text.strip() for c in r.cells] for r in sh.table.rows]
                bloques.append(Bloque("tabla", sh.name, resumen=" | ".join(filas[0])[:120] if filas else "", filas=len(filas), columnas=len(filas[0]) if filas else 0,
                                      caracteres=sum(len(c) for f in filas for c in f)))
                for f in filas:
                    for c in f:
                        _metricas_de(c, sh.name, ind, narrativa, fuentes, metricas)
            elif getattr(sh, "has_chart", False) and sh.has_chart:
                ng += 1
                bloques.append(Bloque("grafica", sh.name, resumen=str(sh.chart.chart_type)))
            elif sh.shape_type == MSO_SHAPE_TYPE.PICTURE:
                deco = _hash_imagen(sh) in repetidas
                if not deco:
                    ng += 1
                bloques.append(Bloque("imagen", sh.name, decorativo=deco))
            elif sh.has_text_frame and sh.text_frame.text.strip():
                t = " ".join(sh.text_frame.text.split())
                bloques.append(Bloque("texto", sh.name, resumen=t[:120], caracteres=len(t)))
                chars += len(t)
                textos.append((sh.name, sh.text_frame.text))
                for p in sh.text_frame.paragraphs:
                    if p.text.strip():
                        _metricas_de(p.text, sh.name, ind, narrativa, fuentes, metricas)
        mensaje = None
        if textos:
            mayor = max(textos, key=lambda x: len(x[1]))[1]
            for p in mayor.splitlines():
                if len(_limpiar(p)) >= 25:
                    mensaje = _limpiar(p)[:300]
                    break
        agregada = any(n.startswith(reglas.PREFIJO_AGREGADA) for n in nombres)
        visual = [f"tabla {b.filas}×{b.columnas} ({b.forma})" for b in bloques if b.tipo == "tabla"] + \
                 [f"{b.tipo} ({b.forma})" for b in bloques if b.tipo in ("grafica", "imagen") and not b.decorativo]
        notas = sorted({m for m in ("Supuesto heredado, no validado",) if any(m.lower() in b.resumen.lower() for b in bloques)} |
                       ({"Contiene estimaciones o escenarios ilustrativos"} if any(m.estado == "estimado" for m in metricas) else set()))
        spec = SlideSpec(
            id=f"{tipo}:{s.slide_id}", tipo=tipo, titulo=titulo, objetivo=_OBJETIVO.get(tipo), mensaje=mensaje, sld_id=s.slide_id, indice=i, bloques=bloques,
            metricas=metricas, visualizaciones=visual, fuentes=sorted(set(m.fuente for m in metricas if m.fuente)), densidad=_densidad(nt, ng, chars, len(metricas)),
            restricciones={"area_segura_pt": [reglas.MARGEN_SEGURO_PT, reglas.MARGEN_SEGURO_PT, round(ancho - reglas.MARGEN_SEGURO_PT, 1), round(alto - reglas.MARGEN_SEGURO_PT, 1)],
                           "letra_minima_pt": reglas.LETRA_MIN_PT},
            notas=notas, agregada=agregada)
        spec.avisos = [m for _, m in validar_diapositiva(spec)]
        spec.estado = "incompleta" if any(c in ("SPEC_SIN_TITULO", "SPEC_SIN_CONTENIDO") for c, _ in validar_diapositiva(spec)) else ("con_avisos" if spec.avisos else "completa")
        out.append(spec)
    return SpecReporte(escenario_id=escenario_id, perfil=perfil, diapositivas=out, ancho_pt=round(ancho, 1), alto_pt=round(alto, 1))


def _metricas_de(texto: str, forma: str, ind, narrativa: set[str], fuentes: list[str], salida: list[Metrica]) -> None:
    est = _estado_texto(texto)
    if est == "no_disponible":
        salida.append(Metrica(_limpiar(texto)[:80], "no_disponible", forma))
    for tok, _, _ in cifras.numeros(texto):
        if est == "estimado":
            salida.append(Metrica(tok, "estimado", forma))
        elif cifras.trazable(tok, ind, narrativa):
            salida.append(Metrica(tok, "real", forma, fuentes[0] if fuentes else None))
        else:
            salida.append(Metrica(tok, "sin_respaldo", forma))


# -------------------------------------------------------------------------------------------------------------------- validación (antes de representar)
def validar_diapositiva(sp: SlideSpec) -> list[tuple[str, str]]:
    """Invariantes de una diapositiva: [(código, mensaje)]. No depende del PPTX: se puede ejecutar antes de representarla."""
    p: list[tuple[str, str]] = []
    if not _ID.fullmatch(sp.id or ""):
        p.append(("SPEC_ID_INVALIDO", f"El identificador «{sp.id}» no tiene el formato tipo:sldId."))
    if sp.tipo not in TIPOS_DIAPOSITIVA:
        p.append(("SPEC_TIPO_INVALIDO", f"El tipo «{sp.tipo}» no es reconocido."))
    if not (sp.titulo or "").strip():
        p.append(("SPEC_SIN_TITULO", "La diapositiva no tiene título."))
    if not [b for b in sp.bloques if not b.decorativo]:
        p.append(("SPEC_SIN_CONTENIDO", "La diapositiva no tiene contenido (texto, tabla o visualización)."))
    if sp.densidad not in DENSIDADES:
        p.append(("SPEC_DENSIDAD_INVALIDA", f"La densidad «{sp.densidad}» no es reconocida."))
    for m in sp.metricas:
        if m.estado not in ESTADOS_METRICA:
            p.append(("SPEC_ESTADO_INVALIDO", f"La métrica «{m.texto}» tiene un estado no reconocido."))
    nombres = [b.forma for b in sp.bloques]
    if len(nombres) != len(set(nombres)):
        p.append(("SPEC_FORMA_REPETIDA", "Hay dos bloques que apuntan a la misma forma."))
    return p


def validar(spec: SpecReporte) -> list[tuple[str | None, str, str]]:
    """Validación del reporte completo: [(id de diapositiva | None, código, mensaje)]. Ids únicos, tipos y estructura de cada una."""
    out: list[tuple[str | None, str, str]] = []
    vistos: set[str] = set()
    for s in spec.diapositivas:
        if s.id in vistos:
            out.append((s.id, "SPEC_ID_REPETIDO", f"El identificador {s.id} aparece más de una vez."))
        vistos.add(s.id)
        out += [(s.id, c, m) for c, m in validar_diapositiva(s)]
    if not spec.diapositivas:
        out.append((None, "SPEC_VACIA", "El reporte no tiene diapositivas."))
    return out
