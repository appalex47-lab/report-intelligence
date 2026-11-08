"""QA integral: estructura, contenido, diseño y exportación sobre el SlideSpec, el PPTX y la vista previa, junto con el QA que ya existía.

Clasificación (fiel, nunca a la baja): ERROR (impide dar por válido el reporte y BLOQUEA la exportación), ADVERTENCIA (hay que revisarla; no bloquea) e
INFORMACIÓN (comunica una condición). Cada hallazgo indica la diapositiva afectada, el elemento, la descripción, el motivo y la acción correctiva sugerida.
Los hallazgos del QA anterior (`checks`, `pptx_export`, `cifras`, visual) se incorporan con su severidad ORIGINAL: error → ERROR, warn → ADVERTENCIA,
info → INFORMACIÓN. Nada se convierte automáticamente en advertencia.
"""
from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path

from pptx import Presentation
from pptx.enum.dml import MSO_FILL

from ..qa import cifras
from . import adaptativo, previsualizacion, reglas, slidespec
from .escenario import EscenarioReporte

ESQUEMA = "qa_integral/1"
ERROR, ADVERTENCIA, INFO = "ERROR", "ADVERTENCIA", "INFORMACIÓN"
_SEV = {"error": ERROR, "warn": ADVERTENCIA, "info": INFO}
OCUPACION_SEVERA = 1.25             # tras el ajuste, una ocupación estimada mayor que esta es un desborde severo (ERROR); entre 1,02 y 1,25, ADVERTENCIA

# Motivo y acción de los hallazgos del QA anterior; los que no están aquí reciben un texto genérico que cita su origen.
_CONOCIDOS = {
    "PPTX_CIFRA_NO_TRAZADA": ("La cifra impresa no coincide con ningún valor calculado por el motor.", "Corregir el texto o la tabla, o aportar el dato de origen."),
    "PPTX_FORMULA_NO_COINCIDE": ("Un derivado impreso (ticket, variación) no se recalcula con sus componentes.", "Revisar la fórmula y los datos de origen de esa tabla."),
    "PPTX_SIN_DENOMINADOR": ("Un porcentaje de proporción no declara su base.", "Indicar sobre qué base se calcula el porcentaje (requiere decisión narrativa si el texto está protegido)."),
    "PPTX_UNIDAD_AMBIGUA": ("Una columna mezcla unidades o usa una moneda no declarada.", "Unificar la unidad y declarar la moneda solo si el libro la declara."),
    "PPTX_FUENTE_MIN": ("La letra es menor que el mínimo legible.", "Aumentar el tamaño de letra o reducir el contenido."),
    "PPTX_FUERA_DE_LIENZO": ("Una forma queda fuera de la diapositiva.", "Moverla o reducirla dentro del área visible."),
    "PPTX_TOKEN_TECNICO": ("Quedó un valor técnico visible (None, nan, {{…}}).", "Corregir el dato de origen que lo produjo."),
    "TEXT_OUT_OF_PAGE": ("El texto renderizado sale de la página.", "Reducir o reubicar el texto."),
    "OVERFLOW_INTO_FOOTER": ("El texto invade el pie de página.", "Abreviar el texto o reducir la letra."),
    "NARRATIVE_UNVERIFIED": ("Una cifra de la narrativa no tiene evidencia en los datos.", "Corregir el texto o la cifra."),
    "QA_VISUAL_OMITIDO": ("El navegador no puede renderizar (no hay LibreOffice).", "Revisar el PPTX en PowerPoint o con la herramienta visual local antes de distribuirlo."),
}


@dataclass
class Hallazgo:
    id: str
    severidad: str
    descripcion: str
    motivo: str
    accion: str
    diapositiva: str | None = None          # id estable de SlideSpec
    indice: int | None = None               # n.º de diapositiva (informativo)
    elemento: str | None = None
    origen: str = "integral"                # integral | qa_anterior


@dataclass
class InformeQA:
    hallazgos: list[Hallazgo]
    huellas: dict

    @property
    def errores(self) -> list[Hallazgo]:
        return [h for h in self.hallazgos if h.severidad == ERROR]

    @property
    def exportable(self) -> bool:
        return not self.errores

    def resumen(self) -> dict:
        return {"errores": len(self.errores), "advertencias": sum(h.severidad == ADVERTENCIA for h in self.hallazgos),
                "informacion": sum(h.severidad == INFO for h in self.hallazgos)}

    def to_dict(self) -> dict:
        r = self.resumen()
        return {"esquema": ESQUEMA, "exportable": self.exportable, "estado": "bloqueado" if r["errores"] else ("con_advertencias" if r["advertencias"] else "aprobado"),
                "resumen": r, "huellas": self.huellas, "hallazgos": [asdict(h) for h in self.hallazgos]}


# ----------------------------------------------------------------------------------------------------------------------- utilidades
def _id_de(spec: slidespec.SpecReporte | None, indice: int | None) -> str | None:
    if spec is None or indice is None or not (1 <= indice <= len(spec.diapositivas)):
        return None
    return spec.diapositivas[indice - 1].id


def incorporar_qa_anterior(issues, spec: slidespec.SpecReporte | None) -> list[Hallazgo]:
    """Los `Issue` de `checks.QAReport` (id, severity, slide, message) con su severidad original."""
    out = []
    for i in issues:
        motivo, accion = _CONOCIDOS.get(i.id, (f"Detectado por la revisión «{i.id}».", "Revisar el elemento señalado antes de distribuir el reporte."))
        out.append(Hallazgo(i.id, _SEV.get(i.severity, ADVERTENCIA), i.message, motivo, accion, _id_de(spec, i.slide), i.slide, None, "qa_anterior"))
    return out


def _luminancia(rgb: str) -> float:
    c = [int(rgb[k:k + 2], 16) / 255 for k in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contraste(fg: str, bg: str) -> float:
    a, b = _luminancia(fg), _luminancia(bg)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


# ----------------------------------------------------------------------------------------------------------------------- estructura
def revisar_estructura(spec: slidespec.SpecReporte, esc: EscenarioReporte, pptx: Path | str, perfil: str) -> list[Hallazgo]:
    out: list[Hallazgo] = []
    graves = {"SPEC_ID_INVALIDO", "SPEC_ID_REPETIDO", "SPEC_TIPO_INVALIDO", "SPEC_VACIA"}
    for sid, cod, msg in slidespec.validar(spec):
        if cod in ("SPEC_SIN_TITULO", "SPEC_SIN_CONTENIDO"):
            continue                                                 # son de contenido: se informan allí
        sp = spec.por_id().get(sid) if sid else None
        out.append(Hallazgo("QA_" + cod, ERROR if cod in graves else ADVERTENCIA, msg, "La especificación de la diapositiva no cumple sus invariantes.",
                            "Regenerar el reporte; si persiste, revisar la plantilla.", sid, sp.indice if sp else None))
    tipos = [s.tipo for s in spec.diapositivas]
    for t in esc.tipos_obligatorios:
        if t not in tipos:
            out.append(Hallazgo("QA_FALTA_TIPO_OBLIGATORIO", ERROR, f"Falta la diapositiva obligatoria «{t}» del escenario «{esc.nombre}».",
                                "El escenario exige este tipo de diapositiva y el reporte no la contiene.", f"Incluir la diapositiva «{t}» (o cambiar el escenario si no aplica).", None))
    if esc.orden_narrativo:
        previstos = [t for t in tipos if t in esc.orden_narrativo]
        pos = {t: i for i, t in enumerate(esc.orden_narrativo)}
        vistos: list[str] = []
        for t in previstos:
            if t not in vistos:
                vistos.append(t)
        rotos = [t for a, t in zip(vistos, vistos[1:]) if pos[a] > pos[t]]
        if rotos:
            out.append(Hallazgo("QA_ORDEN_NARRATIVO", ADVERTENCIA, f"El orden de las diapositivas no sigue el orden narrativo del escenario (a partir de «{rotos[0]}»).",
                                f"Orden esperado: {' → '.join(esc.orden_narrativo)}.", "Reordenar las diapositivas o ajustar el orden narrativo del escenario."))
    if "anexo_calidad" in tipos and tipos[-1] != "anexo_calidad":
        out.append(Hallazgo("QA_ANEXO_NO_ES_ULTIMA", ADVERTENCIA, "El anexo de calidad no es la última diapositiva.", "El anexo cierra el reporte.", "Moverlo al final."))
    for s in spec.diapositivas:
        if s.tipo == "contenido":
            out.append(Hallazgo("QA_TIPO_NO_CLASIFICADO", INFO, f"La diapositiva «{(s.titulo or '(sin título)')[:50]}» no corresponde a ningún tipo conocido.",
                                "Su título no coincide con los tipos del catálogo; no se validan expectativas del escenario sobre ella.", "Ninguna, salvo que deba clasificarse.", s.id, s.indice))
    if esc.profundidad == "ejecutivo" and "resumen_ejecutivo" not in tipos:
        out.append(Hallazgo("QA_PROFUNDIDAD_EJECUTIVA", ADVERTENCIA, "El escenario es ejecutivo y el reporte no tiene resumen ejecutivo.", "Una lectura ejecutiva empieza por su resumen.", "Generar con el resumen ejecutivo activado."))
    if esc.tipo_conclusion != "sin_conclusion" and not ({"conclusiones", "recomendaciones"} & set(tipos)):
        out.append(Hallazgo("QA_SIN_CONCLUSION", ADVERTENCIA, "El escenario espera una conclusión y el reporte no tiene diapositiva de conclusiones ni de recomendaciones.", f"Tipo de conclusión esperado: {esc.tipo_conclusion}.", "Incluir una diapositiva de conclusiones."))
    if esc.perfil not in ("*", perfil):
        out.append(Hallazgo("QA_ESCENARIO_OTRO_PERFIL", ADVERTENCIA, f"El escenario «{esc.nombre}» es del perfil {esc.perfil} y el reporte es {perfil}.", "Sus expectativas pueden no aplicar.", "Elegir el escenario del perfil del reporte."))
    # referencias válidas: cada bloque apunta a una forma que existe y cada id corresponde a la diapositiva real
    prs = Presentation(str(pptx))
    for s, real in zip(spec.diapositivas, prs.slides):
        nombres = {sh.name for sh in real.shapes}
        if real.slide_id != s.sld_id:
            out.append(Hallazgo("QA_REFERENCIA_DIAPOSITIVA", ERROR, f"La diapositiva {s.id} no es la {real.slide_id} del PPTX.", "El SlideSpec no corresponde al archivo.", "Regenerar el reporte.", s.id, s.indice))
        for b in s.bloques:
            if b.forma not in nombres and not b.forma.startswith("AlternateContent"):
                out.append(Hallazgo("QA_REFERENCIA_FORMA", ERROR, f"El bloque «{b.forma}» no existe en el PPTX.", "El SlideSpec hace referencia a una forma que no está en el archivo.", "Regenerar el reporte.", s.id, s.indice, b.forma))
    if len(spec.diapositivas) != len(prs.slides):
        out.append(Hallazgo("QA_NUM_DIAPOSITIVAS", ERROR, f"El SlideSpec tiene {len(spec.diapositivas)} diapositivas y el PPTX {len(prs.slides)}.", "No corresponden.", "Regenerar el reporte."))
    return out


# ----------------------------------------------------------------------------------------------------------------------- contenido
def revisar_contenido(spec: slidespec.SpecReporte, esc: EscenarioReporte, valores_motor, narrativa_nums: set[str], parrafos: dict | None,
                      indicadores: dict | None, fuentes: list[str]) -> list[Hallazgo]:
    out: list[Hallazgo] = []
    for s in spec.diapositivas:
        if not (s.titulo or "").strip():
            out.append(Hallazgo("QA_SIN_TITULO", ERROR, "La diapositiva no tiene título.", "Toda diapositiva necesita un título para orientar la lectura.", "Agregar un título.", s.id, s.indice))
        if not [b for b in s.bloques if not b.decorativo]:
            out.append(Hallazgo("QA_CONTENIDO_VACIO", ERROR, "La diapositiva no tiene contenido.", "No hay texto, tabla ni visualización.", "Agregar el contenido o eliminar la diapositiva.", s.id, s.indice))
        for b in s.bloques:
            if b.tipo == "tabla" and (b.filas or 0) <= 1:
                out.append(Hallazgo("QA_TABLA_SIN_DATOS", ADVERTENCIA, f"La tabla «{b.forma}» no tiene filas de datos.", "Solo contiene encabezado o está vacía.", "Revisar el dato de origen.", s.id, s.indice, b.forma))
        nd = [m for m in s.metricas if m.estado == "no_disponible"]
        if nd:
            out.append(Hallazgo("QA_DATO_NO_DISPONIBLE", INFO, f"La diapositiva declara {len(nd)} dato(s) no disponible(s): «{nd[0].texto[:50]}».",
                                "El dato no estaba en el libro o no pasó la validación; se declara en lugar de completarlo.", "Aportar el dato si debe aparecer.", s.id, s.indice))
        if any(m.estado == "estimado" for m in s.metricas):
            out.append(Hallazgo("QA_CONTIENE_ESTIMACIONES", INFO, "La diapositiva contiene estimaciones o escenarios ilustrativos (no son datos reales).", "Se rotulan como supuestos; no son resultados medidos.", "Ninguna: mantener el rótulo de supuesto.", s.id, s.indice))
    hay_real = any(m.estado == "real" for s in spec.diapositivas for m in s.metricas)
    if hay_real and not fuentes:
        out.append(Hallazgo("QA_SIN_FUENTE", ADVERTENCIA, "El reporte tiene cifras trazadas al motor pero no se registró el archivo de origen.", "La fuente de los datos es obligatoria para conservar la trazabilidad.", "Generar desde un libro cargado para que quede registrada."))
    # escenario: indicadores relevantes, mensaje central y campos no definidos
    for ind in esc.indicadores_relevantes:
        v = (indicadores or {}).get(ind)
        if v is None:
            out.append(Hallazgo("QA_INDICADOR_NO_DISPONIBLE", ADVERTENCIA, f"El indicador relevante «{ind}» del escenario no está disponible en este periodo.",
                                "El escenario lo marca como relevante y el motor no devolvió un valor (estado: no disponible).", "Revisar el libro del periodo; el indicador no se inventa ni se sustituye."))
    if esc.mensaje_central:
        ind_c = cifras.Indice(valores_motor or [])
        malas = [t for t, _, _ in cifras.numeros(esc.mensaje_central) if not cifras.trazable(t, ind_c, narrativa_nums)]
        if malas:
            out.append(Hallazgo("QA_MENSAJE_SIN_EVIDENCIA", ADVERTENCIA, f"El mensaje central del escenario cita cifras sin respaldo en los datos: {', '.join(malas[:4])}.",
                                "Una conclusión no debe afirmar cifras que el motor no calculó.", "Corregir el mensaje central o retirar la cifra."))
    nd_campos = esc.no_definidos()
    if nd_campos:
        out.append(Hallazgo("QA_ESCENARIO_INCOMPLETO", INFO, f"El escenario «{esc.nombre}» no define: {', '.join(nd_campos)}.",
                            "La especificación no los define para este escenario y no se inventan.", "Completarlos en el escenario si se quiere validarlos."))
    # conclusiones sin evidencia: una interpretación debe guardar la regla que la sustenta
    for clave, ps in (parrafos or {}).items():
        sin = [p for p in ps if getattr(p, "kind", "") == "interpretacion" and not getattr(p, "basis", "") and getattr(p, "visible", True)]
        if sin:
            out.append(Hallazgo("QA_INTERPRETACION_SIN_REGLA", ADVERTENCIA, f"{len(sin)} interpretación(es) de «{clave}» no registran la regla que las sustenta.",
                                "Una interpretación sin regla explícita no se puede auditar.", "Registrar la regla o redactarla como hecho verificable."))
    return out


# ----------------------------------------------------------------------------------------------------------------------- diseño
def _contraste_formas(pptx: Path | str, spec: slidespec.SpecReporte) -> list[Hallazgo]:
    prs = Presentation(str(pptx))
    out: list[Hallazgo] = []
    indeterminadas = 0
    for s, sl in zip(spec.diapositivas, prs.slides):
        bg = None
        try:
            if sl.background.fill.type == MSO_FILL.SOLID and sl.background.fill.fore_color.type is not None:
                bg = "#" + str(sl.background.fill.fore_color.rgb)
        except Exception:                                           # noqa: BLE001
            bg = None
        for sh in sl.shapes:
            if not sh.has_text_frame or not sh.text_frame.text.strip():
                continue
            fondo = previsualizacion._relleno(sh) or bg
            colores = {previsualizacion._color(r.font.color) for p in sh.text_frame.paragraphs for r in p.runs if r.text.strip()}
            if fondo is None or None in colores or not colores:
                indeterminadas += 1
                continue
            peor = min(contraste(c, fondo) for c in colores)
            if peor < 1.5:
                out.append(Hallazgo("QA_CONTRASTE_ILEGIBLE", ERROR, f"El texto de «{sh.name}» es prácticamente ilegible (contraste {peor:.1f}:1).", "Color de letra y de fondo casi iguales.", "Cambiar el color de la letra o del fondo.", s.id, s.indice, sh.name))
            elif peor < reglas.CONTRASTE_MIN:
                out.append(Hallazgo("QA_CONTRASTE_BAJO", ADVERTENCIA, f"El texto de «{sh.name}» tiene contraste insuficiente ({peor:.1f}:1; mínimo {reglas.CONTRASTE_MIN:.0f}:1).", "Color de letra y de fondo poco distintos.", "Aumentar el contraste.", s.id, s.indice, sh.name))
    if indeterminadas:
        out.append(Hallazgo("QA_CONTRASTE_NO_DETERMINABLE", INFO, f"El contraste de {indeterminadas} cuadro(s) de texto no se puede calcular sin render (colores del tema).",
                            "Los colores heredados del tema no están en el archivo.", "Revisarlos con el QA visual (LibreOffice) o en PowerPoint."))
    return out


def _consistencia_titulos(pptx: Path | str, spec: slidespec.SpecReporte) -> list[Hallazgo]:
    prs = Presentation(str(pptx))
    tam: dict[str, float] = {}
    for s, sl in zip(spec.diapositivas, prs.slides):
        for sh in sl.shapes:
            if sh.has_text_frame and sh.text_frame.text.strip() and " ".join(sh.text_frame.text.split()) == s.titulo:
                t = slidespec._tamano_max(sh)
                if t:
                    tam[s.id] = t
                break
    if tam and max(tam.values()) - min(tam.values()) > 6:
        return [Hallazgo("QA_TITULOS_INCONSISTENTES", ADVERTENCIA, f"Los títulos varían de {min(tam.values()):.0f} a {max(tam.values()):.0f} pt entre diapositivas.",
                         "Los títulos deben tener una jerarquía consistente.", "Unificar el tamaño de los títulos.")]
    return []


def revisar_diseno(inf: adaptativo.InformeDiseno, spec: slidespec.SpecReporte, pptx: Path | str, aplicado: bool) -> list[Hallazgo]:
    out: list[Hallazgo] = []
    por_id = spec.por_id()
    for a in inf.avisos:
        sp = por_id.get(a.diapositiva)
        sev = {"DISENO_NO_ESTIMABLE": INFO, "DISENO_NO_CABE": ADVERTENCIA, "DISENO_SOLAPE": ADVERTENCIA, "DISENO_FUERA_DE_AREA": ADVERTENCIA}.get(a.codigo, ADVERTENCIA)
        if a.codigo == "DISENO_NO_CABE":
            occ = inf.estimaciones.get(a.diapositiva, {}).get(a.forma, 0)
            if occ > OCUPACION_SEVERA:
                sev = ERROR
        out.append(Hallazgo("QA_" + a.codigo, sev, a.mensaje, a.motivo + ("" if aplicado else " (el diseño adaptativo estaba desactivado)"), a.accion, a.diapositiva, sp.indice if sp else None, a.forma))
    for a in inf.acciones:
        sp = por_id.get(a.diapositiva)
        out.append(Hallazgo("QA_DISENO_AJUSTE", INFO, f"Se ajustó «{a.forma}»: {a.tipo.replace('_', ' ')} ({a.antes} → {a.despues}).", a.motivo, "Ninguna: revisar el resultado en la vista previa.", a.diapositiva, sp.indice if sp else None, a.forma))
    return out + _contraste_formas(pptx, spec) + _consistencia_titulos(pptx, spec)


# ----------------------------------------------------------------------------------------------------------------------- exportación
def revisar_exportacion(pptx: Path | str, spec: slidespec.SpecReporte, vista: dict | None) -> list[Hallazgo]:
    """El archivo FINAL contra el SlideSpec y la vista previa: integridad, número y orden de diapositivas, recursos gráficos y contenido esperado."""
    out: list[Hallazgo] = []
    try:
        with zipfile.ZipFile(str(pptx)) as z:
            malo = z.testzip()
        if malo:
            return [Hallazgo("QA_EXPORTACION_ZIP", ERROR, f"El PPTX está dañado ({malo}).", "El archivo no es un ZIP íntegro.", "Regenerar el reporte.")]
        prs = Presentation(str(pptx))
    except Exception as e:                                          # noqa: BLE001 — si no se puede abrir, ESO es el hallazgo
        return [Hallazgo("QA_EXPORTACION_ILEGIBLE", ERROR, f"No se pudo abrir el PPTX ({type(e).__name__}).", "El archivo no es un PPTX válido.", "Regenerar el reporte.")]
    slides = list(prs.slides)
    if len(slides) != len(spec.diapositivas):
        return [Hallazgo("QA_EXPORTACION_NUM", ERROR, f"El PPTX tiene {len(slides)} diapositivas y el SlideSpec {len(spec.diapositivas)}.", "El archivo exportado no corresponde a lo especificado.", "Regenerar el reporte.")]
    for s, sl in zip(spec.diapositivas, slides):
        if sl.slide_id != s.sld_id:
            out.append(Hallazgo("QA_EXPORTACION_ORDEN", ERROR, f"La diapositiva {s.indice} del PPTX es la {sl.slide_id} y se esperaba la {s.sld_id}.", "El orden o la identidad de las diapositivas cambió.", "Regenerar el reporte.", s.id, s.indice))
            continue
        titulo, _ = slidespec.titulo_de(sl)
        if titulo != s.titulo:
            out.append(Hallazgo("QA_EXPORTACION_TITULO", ERROR, f"El título de la diapositiva {s.indice} no coincide con el especificado.", f"Esperado «{s.titulo}», en el archivo «{titulo}».", "Regenerar el reporte.", s.id, s.indice))
        tablas = [sh for sh in sl.shapes if getattr(sh, "has_table", False) and sh.has_table]
        esperadas = [b for b in s.bloques if b.tipo == "tabla"]
        if len(tablas) != len(esperadas):
            out.append(Hallazgo("QA_EXPORTACION_TABLAS", ERROR, f"La diapositiva {s.indice} tiene {len(tablas)} tabla(s) y se esperaban {len(esperadas)}.", "Contenido esperado ausente.", "Regenerar el reporte.", s.id, s.indice))
        else:
            for t, b in zip(tablas, esperadas):
                if (len(t.table.rows), len(t.table.columns)) != (b.filas, b.columnas):
                    out.append(Hallazgo("QA_EXPORTACION_TABLA_DIMENSION", ERROR, f"La tabla «{b.forma}» tiene otra dimensión que la especificada.", f"Esperada {b.filas}×{b.columnas}.", "Regenerar el reporte.", s.id, s.indice, b.forma))
    # recursos gráficos: cada imagen INCRUSTADA se puede abrir; las que la plantilla trae sin imagen incrustada se informan, no se tratan como dañadas
    # (la integridad de los recursos del paquete ya la comprueba `pptx_export`: PPTX_IMAGEN)
    sin_recurso = 0
    try:
        from PIL import Image
        import io
        for s, sl in zip(spec.diapositivas, slides):
            for sh in sl.shapes:
                if sh.shape_type == 13:
                    try:
                        blob = sh.image.blob
                    except ValueError:
                        sin_recurso += 1
                        continue
                    try:
                        Image.open(io.BytesIO(blob)).verify()
                    except Exception:                               # noqa: BLE001
                        out.append(Hallazgo("QA_EXPORTACION_IMAGEN", ERROR, f"La imagen «{sh.name}» no se puede abrir.", "Recurso gráfico dañado.", "Reemplazar la imagen o regenerar.", s.id, s.indice, sh.name))
    except ImportError:
        out.append(Hallazgo("QA_EXPORTACION_IMAGEN_NO_COMPROBADA", INFO, "No se comprobaron las imágenes (falta Pillow).", "Dependencia no disponible.", "Ninguna."))
    if sin_recurso:
        out.append(Hallazgo("QA_IMAGEN_SIN_RECURSO", INFO, f"{sin_recurso} imagen(es) de la plantilla no tienen imagen incrustada.", "Es una propiedad heredada de la plantilla (marcos de imagen sin archivo); no es un daño del reporte.", "Ninguna, salvo que deban mostrar una imagen."))
    # vista previa ↔ PPTX
    if vista is None:
        out.append(Hallazgo("QA_EXPORTACION_SIN_VISTA", ERROR, "No hay vista previa del reporte.", "Sin vista previa no se puede confirmar lo que se exportará.", "Regenerar el reporte."))
    else:
        for cod, n, msg in previsualizacion.verificar_correspondencia(vista, pptx):
            out.append(Hallazgo("QA_EXPORTACION_" + cod, ERROR, msg, "La vista previa no representa el archivo que se exportaría.", "Regenerar el reporte para actualizar la vista previa.", _id_de(spec, n), n))
    return out


# ----------------------------------------------------------------------------------------------------------------------- orquestación
def evaluar(*, spec, esc, pptx, vista, informe_diseno, aplicado, qa_anterior, valores_motor, narrativa_nums, parrafos, indicadores, fuentes, perfil, huellas) -> InformeQA:
    h: list[Hallazgo] = []
    h += incorporar_qa_anterior(qa_anterior, spec)
    h += revisar_estructura(spec, esc, pptx, perfil)
    h += revisar_contenido(spec, esc, valores_motor, narrativa_nums, parrafos, indicadores, fuentes)
    h += revisar_diseno(informe_diseno, spec, pptx, aplicado)
    h += revisar_exportacion(pptx, spec, vista)
    orden = {ERROR: 0, ADVERTENCIA: 1, INFO: 2}
    h.sort(key=lambda x: (orden[x.severidad], x.indice or 0, x.id))
    return InformeQA(h, huellas)
