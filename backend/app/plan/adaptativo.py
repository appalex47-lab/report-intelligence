"""Diseño adaptativo: ajusta la composición de las diapositivas según su contenido, sin tocar el significado de los datos.

Trabaja sobre el PPTX ya generado (los generadores por plantilla siguen siendo la fuente del contenido) con reglas compartidas (`reglas.py`) y la
densidad de cada diapositiva (SlideSpec). Para cada cuadro de texto y cada tabla ESTIMA el espacio que necesita el texto (ancho medio de carácter ×
interlineado; es una estimación, no una medición) y, solo si la ocupación pasa de `UMBRAL_ACTUAR`, aplica en este orden:
  1. redistribuir: ampliar el cuadro hacia abajo si hay espacio libre dentro del área segura y sin pisar otra forma;
  2. reducir la letra de forma PROPORCIONAL (se conserva la jerarquía) sin bajar del piso (`LETRA_MIN_PT`, y el 80 % del tamaño original);
  3. en tablas: reducir la letra y ajustar la altura de las filas al texto;
  4. si aun así no cabe: NO se recorta ni se elimina contenido; se emite un aviso con una propuesta (dividir la diapositiva, abreviar el texto).
Si todo cabe, no cambia nada (propiedad comprobada contra los cuatro decks de referencia). Cada acción y cada aviso queda registrado.
"""
from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from pptx import Presentation
from pptx.enum.text import MSO_AUTO_SIZE
from pptx.util import Emu, Pt

from . import reglas

ESQUEMA = "diseno_adaptativo/1"
_INSET_H, _INSET_V = 91440, 45720                    # márgenes internos por defecto de un cuadro de texto de PowerPoint (EMU)
# Por densidad: cuánto puede bajar la letra respecto de su tamaño original (la tabla densa tolera menos que el texto corrido, que se puede abreviar).
PISO_ESCALA = {"pocos_elementos": 0.85, "multiples_kpis": 0.85, "tabla": 0.80, "grafico": 0.85, "narrativa_extensa": 0.80, "mixta": 0.80}


@dataclass
class Accion:
    diapositiva: str
    forma: str
    tipo: str                                        # ampliar_cuadro | reducir_letra | ajustar_tabla
    antes: str
    despues: str
    motivo: str


@dataclass
class Aviso:
    diapositiva: str
    forma: str
    codigo: str                                      # DISENO_NO_CABE | DISENO_NO_ESTIMABLE | DISENO_SOLAPE | DISENO_FUERA_DE_AREA
    mensaje: str
    motivo: str
    accion: str                                      # acción correctiva sugerida


@dataclass
class InformeDiseno:
    modificado: bool = False
    analizadas: int = 0
    acciones: list[Accion] = field(default_factory=list)
    avisos: list[Aviso] = field(default_factory=list)
    estimaciones: dict = field(default_factory=dict)         # id de diapositiva -> {forma: ocupación estimada tras el ajuste}

    def to_dict(self) -> dict:
        return {"esquema": ESQUEMA, "modificado": self.modificado, "analizadas": self.analizadas, "acciones": [asdict(a) for a in self.acciones],
                "avisos": [asdict(a) for a in self.avisos], "estimaciones": self.estimaciones}


# --------------------------------------------------------------------------------------------------------------------- estimación de texto
def _tamano_par(p) -> float | None:
    """Tamaño de letra EXPLÍCITO del párrafo (el mayor de sus runs); None si es heredado (no se puede estimar sin resolver la plantilla)."""
    t = [r.font.size.pt for r in p.runs if r.font.size]
    if t and len(t) == len([r for r in p.runs if r.text]):
        return max(t)
    if p.font.size:
        return p.font.size.pt
    return None


def _factor_ancho(p) -> float:
    nombres = " ".join((r.font.name or "") for r in p.runs).lower()
    return reglas.FACTOR_ANCHO_ESTRECHA if ("narrow" in nombres or "condensed" in nombres) else reglas.FACTOR_ANCHO_CARACTER


def _lineas(texto: str, ancho_pt: float, tam: float, negrita: bool, factor: float = reglas.FACTOR_ANCHO_CARACTER) -> int:
    cpl = max(1, int(ancho_pt / (tam * factor * (1.07 if negrita else 1.0))))
    n = 0
    for linea in texto.split("\n") or [""]:
        n += max(1, math.ceil(len(linea) * 1.04 / cpl))             # 4 % de holgura por palabras que no parten
    return n


def _interlineado(p) -> float:
    ls = p.line_spacing
    return float(ls) if isinstance(ls, float) else reglas.FACTOR_INTERLINEADO


def _alto_parrafos(parrafos, ancho_pt: float | None, escala: float = 1.0) -> float | None:
    """Alto estimado del texto. `ancho_pt=None` = sin ajuste de línea (wrap="none"): solo cuentan los saltos explícitos.
    El espacio previo del primer párrafo y el posterior del último no cuentan: no necesitan caber dentro del cuadro."""
    total = 0.0
    ps = [p for p in parrafos]
    for k, p in enumerate(ps):
        tam = _tamano_par(p)
        if tam is None:
            if not p.text.strip():
                continue
            return None
        tam *= escala
        neg = any(r.font.bold for r in p.runs)
        n = len((p.text or " ").split("\n")) if ancho_pt is None else _lineas(p.text if p.text else " ", ancho_pt, tam, neg, _factor_ancho(p))
        total += n * tam * _interlineado(p)
        if k > 0 and p.space_before is not None:
            total += p.space_before.pt
        if k < len(ps) - 1 and p.space_after is not None:
            total += p.space_after.pt
    return total


def _escala_autoajuste(tf) -> float:
    """Escala que la plantilla ya aplica (`normAutofit fontScale`): el texto se dibuja a ese tamaño."""
    na = tf._txBody.find("{http://schemas.openxmlformats.org/drawingml/2006/main}bodyPr/{http://schemas.openxmlformats.org/drawingml/2006/main}normAutofit")
    try:
        return int(na.get("fontScale")) / 100000 if na is not None and na.get("fontScale") else 1.0
    except ValueError:
        return 1.0


def ocupacion_texto(sh, escala: float = 1.0, limite_inferior_emu: int | None = None) -> tuple[float | None, float, float]:
    """(ocupación, alto necesario pt, alto disponible pt) de un cuadro de texto; ocupación None si no se puede estimar.
    Un cuadro que se ajusta solo a su texto (`spAutoFit`) crece hacia abajo: su capacidad es el espacio libre hasta `limite_inferior_emu` (la forma de abajo o
    el borde seguro), no su alto guardado. Sin ese límite no se puede decir nada y se informa ocupación 0."""
    from pptx.enum.text import MSO_AUTO_SIZE
    tf = sh.text_frame
    mt = (tf.margin_top if tf.margin_top is not None else _INSET_V) * reglas.EMU_PT
    mb = (tf.margin_bottom if tf.margin_bottom is not None else _INSET_V) * reglas.EMU_PT
    disp = sh.height * reglas.EMU_PT - mt - mb
    if tf.auto_size == MSO_AUTO_SIZE.SHAPE_TO_FIT_TEXT:
        if limite_inferior_emu is None:
            return 0.0, 0.0, max(disp, 0.0)
        disp = (limite_inferior_emu - sh.top) * reglas.EMU_PT - mt - mb
    ml = (tf.margin_left if tf.margin_left is not None else _INSET_H) * reglas.EMU_PT
    mr = (tf.margin_right if tf.margin_right is not None else _INSET_H) * reglas.EMU_PT
    ancho = None if tf.word_wrap is False else max(sh.width * reglas.EMU_PT - ml - mr, 1.0)
    necesario = _alto_parrafos(tf.paragraphs, ancho, escala * _escala_autoajuste(tf))
    if necesario is None or disp <= 0:
        return None, 0.0, max(disp, 0.0)
    return necesario / disp, necesario, disp


def ocupacion_tabla(sh, limite_inferior_emu: int, escala: float = 1.0) -> tuple[float | None, float, float, list[float]]:
    """(ocupación, alto necesario, alto disponible pt, altos necesarios por fila). Disponible = hasta `limite_inferior_emu`."""
    tbl = sh.table
    cols = [c.width * reglas.EMU_PT for c in tbl.columns]
    altos = []
    for r in tbl.rows:
        h = 0.0
        for j, c in enumerate(r.cells):
            tf = c.text_frame
            ml = (c.margin_left if c.margin_left is not None else _INSET_H) * reglas.EMU_PT
            mr = (c.margin_right if c.margin_right is not None else _INSET_H) * reglas.EMU_PT
            mt = (c.margin_top if c.margin_top is not None else _INSET_V) * reglas.EMU_PT
            mb = (c.margin_bottom if c.margin_bottom is not None else _INSET_V) * reglas.EMU_PT
            span = c.span_width if hasattr(c, "span_width") and c.is_merge_origin else 1
            ancho = sum(cols[j:j + span]) - ml - mr
            alto = _alto_parrafos(tf.paragraphs, max(ancho, 1.0), escala)
            if alto is None:
                if not tf.text.strip():
                    continue
                return None, 0.0, 0.0, []
            h = max(h, alto + mt + mb)
        altos.append(max(h, 1.0))
    necesario = sum(altos)
    disp = (limite_inferior_emu - sh.top) * reglas.EMU_PT
    return (necesario / disp if disp > 0 else None), necesario, max(disp, 0.0), altos


# --------------------------------------------------------------------------------------------------------------------- geometría
def _es_fondo(sh, ancho: int, alto: int) -> bool:
    return (sh.width or 0) * (sh.height or 0) >= 0.6 * ancho * alto


def _limite_inferior(slide, sh, ancho: int, alto: int) -> int:
    """Hasta dónde puede crecer `sh` hacia abajo (EMU): el borde seguro o el tope de la forma más cercana que queda debajo y se cruza con él."""
    tope = alto - int(reglas.MARGEN_SEGURO_PT / reglas.EMU_PT)
    mitad = (sh.top or 0) + (sh.height or 0) // 2
    for o in slide.shapes:
        if o.shape_id == sh.shape_id or _es_fondo(o, ancho, alto) or o.top is None or o.height is None:
            continue
        solape_h = min(o.left + o.width, sh.left + sh.width) - max(o.left, sh.left)
        if solape_h > 0.15 * min(o.width, sh.width) and o.top >= mitad:
            tope = min(tope, o.top - int(2 / reglas.EMU_PT))
    return max(tope, (sh.top or 0) + (sh.height or 0))


def _rect(sh):
    return (sh.left, sh.top, sh.left + sh.width, sh.top + sh.height)


def _inter(a, b) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return w * h if w > 0 and h > 0 else 0.0


# --------------------------------------------------------------------------------------------------------------------- escala de letra
def _aplicar_escala(parrafos, f: float, piso_pt: float) -> None:
    for p in parrafos:
        for r in p.runs:
            if r.font.size:
                r.font.size = Pt(max(round(r.font.size.pt * f * 2) / 2, min(piso_pt, r.font.size.pt)))


def _escala_minima(parrafos, piso_rel: float) -> float:
    """Escala mínima permitida: el 80-85 % del original y nunca por debajo de `LETRA_MIN_PT`; jamás mayor que 1 (no se agranda la letra)."""
    tams = [r.font.size.pt for p in parrafos for r in p.runs if r.font.size and r.text.strip()]
    if not tams:
        return 1.0
    return min(1.0, max(piso_rel, reglas.LETRA_MIN_PT / min(tams)))


def _fmt(f: float) -> str:
    return f"{f * 100:.0f} %"


_MARCA = re.compile(r"RI_escala=([0-9.]+)")


def _cnvpr(sh):
    r = sh._element.xpath(".//p:cNvPr")
    return r[0] if r else None


def _escala_previa(sh) -> float:
    """Escala de letra que una pasada anterior ya aplicó a esta forma (1.0 si ninguna): el piso se mide contra el tamaño ORIGINAL, no contra el actual."""
    c = _cnvpr(sh)
    m = _MARCA.search((c.get("descr") if c is not None else "") or "")
    return float(m.group(1)) if m else 1.0


def _marcar_escala(sh, total: float) -> None:
    c = _cnvpr(sh)
    if c is None:
        return
    d = _MARCA.sub("", c.get("descr") or "").strip()
    c.set("descr", (d + " " if d else "") + f"RI_escala={total:.3f}")


# --------------------------------------------------------------------------------------------------------------------- aplicación
def adaptar(pptx: Path | str, ids: list[str], densidades: list[str], aplicar: bool = True) -> InformeDiseno:
    """Analiza (y, con `aplicar`, ajusta y guarda) el PPTX. `ids[i]` y `densidades[i]` son los de la i-ésima diapositiva (SlideSpec)."""
    prs = Presentation(str(pptx))
    ancho, alto = prs.slide_width, prs.slide_height
    inf = InformeDiseno()
    slides = list(prs.slides)
    if not (len(ids) == len(densidades) == len(slides)):
        raise ValueError("El SlideSpec no corresponde al PPTX: distinto número de diapositivas.")
    for slide, sid, dens in zip(slides, ids, densidades):
        inf.analizadas += 1
        piso = PISO_ESCALA.get(dens, 0.80)
        modificadas: list = []
        est: dict = {}
        for sh in slide.shapes:
            if (sh.name or "").startswith("Marcador") or sh.top is None or sh.height is None:
                continue
            if getattr(sh, "has_table", False) and sh.has_table:
                lim = _limite_inferior(slide, sh, ancho, alto)
                occ, nec, disp, altos = ocupacion_tabla(sh, lim)
                if occ is None:
                    inf.avisos.append(Aviso(sid, sh.name, "DISENO_NO_ESTIMABLE", "El tamaño de letra de la tabla es heredado de la plantilla; no se pudo estimar su ajuste.",
                                            "Sin tamaño explícito no se puede calcular el espacio que ocupa.", "Revisar la tabla en el PPTX o en una vista con render."))
                    continue
                est[sh.name] = round(occ, 2)
                if occ <= reglas.UMBRAL_ACTUAR:
                    continue
                celdas = [p for r in sh.table.rows for c in r.cells for p in c.text_frame.paragraphs]
                previa = _escala_previa(sh)
                minimo = _escala_minima(celdas, min(1.0, piso / previa))
                f = max(minimo, min(1.0, 1.0 / occ))
                if aplicar and f < 1.0:
                    _aplicar_escala(celdas, f, reglas.LETRA_MIN_PT)
                    _marcar_escala(sh, previa * f)
                    occ2, nec2, _, altos2 = ocupacion_tabla(sh, lim)
                    for r, h in zip(sh.table.rows, altos2 or altos):
                        r.height = Emu(int(min(r.height, max(h, 1.0) / reglas.EMU_PT))) if r.height else r.height
                    inf.acciones.append(Accion(sid, sh.name, "ajustar_tabla", f"ocupación {_fmt(occ)}", f"letra al {_fmt(f)} · ocupación {_fmt(occ2 or 0)}",
                                               "La tabla no cabía en el espacio disponible de la diapositiva."))
                    occ = occ2 if occ2 is not None else occ
                    est[sh.name] = round(occ, 2)
                    modificadas.append(sh)
                if occ > reglas.HOLGURA_DESBORDE * 1.0 + 0.02:
                    inf.avisos.append(Aviso(sid, sh.name, "DISENO_NO_CABE", f"La tabla necesita ≈{nec:.0f} pt y hay ≈{disp:.0f} pt disponibles (ocupación estimada {_fmt(occ)}).",
                                            "Contiene más filas o texto del que cabe con la letra mínima permitida.",
                                            "Dividir la tabla en dos diapositivas o reducir filas; no se recorta contenido automáticamente."))
            elif sh.has_text_frame and sh.text_frame.text.strip():
                lim_t = _limite_inferior(slide, sh, ancho, alto)
                occ, nec, disp = ocupacion_texto(sh, 1.0, lim_t)
                if occ is None:
                    inf.avisos.append(Aviso(sid, sh.name, "DISENO_NO_ESTIMABLE", "El tamaño de letra del cuadro de texto es heredado; no se pudo estimar su ajuste.",
                                            "Sin tamaño explícito no se puede calcular el espacio que ocupa.", "Revisar el texto en el PPTX o en una vista con render."))
                    continue
                est[sh.name] = round(occ, 2)
                if occ <= reglas.UMBRAL_ACTUAR:
                    continue
                antes = f"ocupación {_fmt(occ)}"
                if aplicar:
                    lim = lim_t
                    mt = (sh.text_frame.margin_top if sh.text_frame.margin_top is not None else _INSET_V)
                    mb = (sh.text_frame.margin_bottom if sh.text_frame.margin_bottom is not None else _INSET_V)
                    nuevo_alto = int(nec / reglas.EMU_PT) + mt + mb
                    autoajustable = sh.text_frame.auto_size == MSO_AUTO_SIZE.SHAPE_TO_FIT_TEXT
                    if not autoajustable and nuevo_alto <= lim - sh.top and nuevo_alto > sh.height:
                        h0 = sh.height
                        sh.height = Emu(nuevo_alto)
                        inf.acciones.append(Accion(sid, sh.name, "ampliar_cuadro", f"alto {h0 * reglas.EMU_PT:.0f} pt · {antes}", f"alto {nuevo_alto * reglas.EMU_PT:.0f} pt",
                                                   "Había espacio libre debajo, dentro del área segura y sin pisar otra forma."))
                        modificadas.append(sh)
                        occ = nec / (nuevo_alto * reglas.EMU_PT - (mt + mb) * reglas.EMU_PT)
                    else:
                        parrafos = list(sh.text_frame.paragraphs)
                        previa = _escala_previa(sh)
                        minimo = _escala_minima(parrafos, min(1.0, piso / previa))
                        f = max(minimo, min(1.0, 1.0 / occ))
                        if f < 1.0:
                            _aplicar_escala(parrafos, f, reglas.LETRA_MIN_PT)
                            _marcar_escala(sh, previa * f)
                            occ2, _, _ = ocupacion_texto(sh, 1.0, lim_t)
                            inf.acciones.append(Accion(sid, sh.name, "reducir_letra", antes, f"letra al {_fmt(f)} · ocupación {_fmt(occ2 or 0)}",
                                                       "No hay espacio libre para ampliar el cuadro; se reduce la letra de forma proporcional (se conserva la jerarquía)."))
                            modificadas.append(sh)
                            occ = occ2 if occ2 is not None else occ
                    est[sh.name] = round(occ, 2)
                if occ > reglas.HOLGURA_DESBORDE * 1.0 + 0.02:
                    inf.avisos.append(Aviso(sid, sh.name, "DISENO_NO_CABE", f"El texto necesita ≈{nec:.0f} pt y hay ≈{disp:.0f} pt disponibles (ocupación estimada {_fmt(occ)}).",
                                            "El texto es más extenso de lo que cabe con la letra mínima permitida y sin espacio libre.",
                                            "Abreviar el texto o dividir el contenido en otra diapositiva; no se recorta automáticamente."))
        for sh in modificadas:                                   # una forma que se modificó no debe quedar fuera del área segura ni pisar a otra
            r = _rect(sh)
            seg = reglas.MARGEN_SEGURO_PT / reglas.EMU_PT
            if r[0] < seg * 0 or r[1] < 0 or r[2] > ancho or r[3] > alto - seg * 0.5:
                inf.avisos.append(Aviso(sid, sh.name, "DISENO_FUERA_DE_AREA", "La forma ajustada queda fuera del área segura.", "El ajuste la acercó al borde.",
                                        "Reducir contenido o moverla manualmente."))
            for o in slide.shapes:
                if o.shape_id == sh.shape_id or _es_fondo(o, ancho, alto) or (o.name or "").startswith("Marcador") or o.top is None or o.height is None:
                    continue
                if _inter(r, _rect(o)) > 0.05 * min(sh.width * sh.height, o.width * o.height):
                    inf.avisos.append(Aviso(sid, sh.name, "DISENO_SOLAPE", f"La forma ajustada se superpone con «{o.name}».", "Tras el ajuste ambas ocupan la misma zona.",
                                            "Mover o reducir una de las dos formas."))
        inf.estimaciones[sid] = est
    inf.modificado = bool(inf.acciones)
    if aplicar and inf.modificado:
        prs.save(str(pptx))
    return inf
