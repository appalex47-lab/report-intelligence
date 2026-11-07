"""Flujo integrado: escenario → SlideSpec → diseño adaptativo → QA integral → vista previa → exportación.

`Plan` se entrega a `build.build_*(plan=…)`, que lo invoca en DOS puntos y en este orden (así lo que se valida es siempre el archivo final y la
el manifiesto y el historial registran el hash del PPTX definitivo):
  1. `ajustar`: justo después de guardar el PPTX y ANTES de cualquier QA, del manifiesto y del historial (que hashean el PPTX) → diseño adaptativo;
  2. `revisar`: tras el QA anterior y antes del manifiesto → SlideSpec final, vista previa, QA integral, archivos JSON y hallazgos nuevos en el QA del reporte
     (por eso `qa.passed`, `downloadable`, el manifiesto y el historial ya reflejan los errores nuevos).
Cada resultado lleva las huellas de lo que lo produjo; `vigente()` detecta que cambió el PPTX, el escenario o las entradas y entonces invalida lo anterior.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..qa import cifras
from . import adaptativo, previsualizacion, qa_integral, slidespec
from .escenario import EscenarioReporte

ARCHIVOS = ("plan_reporte.json", "slidespec.json", "previsualizacion.json", "qa_integral.json")
_SEV_QA = {qa_integral.ERROR: "error", qa_integral.ADVERTENCIA: "warn", qa_integral.INFO: "info"}


def _nums_narrativa(fill) -> set[str]:
    return {c for ps in fill.narrative.values() for p in ps for c in p.nums}


def _escribir(ruta: Path, obj) -> None:
    ruta.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


class Plan:
    def __init__(self, escenario: EscenarioReporte, perfil: str, fuentes: list[str] | None = None, adaptativo_activo: bool = True,
                 indicadores: dict | None = None, huella_entradas: str | None = None):
        self.escenario, self.perfil = escenario, perfil
        self.fuentes = [f for f in (fuentes or []) if f]
        self.adaptativo_activo = bool(adaptativo_activo)
        self.indicadores = indicadores or {}
        self.huella_entradas = huella_entradas
        self.informe_diseno: adaptativo.InformeDiseno | None = None
        self.informe: qa_integral.InformeQA | None = None

    # 1 ─ antes del QA
    def ajustar(self, pptx: Path, result, fill) -> None:
        spec = slidespec.construir(pptx, cifras.recolectar_valores(result), _nums_narrativa(fill), self.escenario.id, self.perfil, self.fuentes)
        self.informe_diseno = adaptativo.adaptar(pptx, [s.id for s in spec.diapositivas], [s.densidad for s in spec.diapositivas], aplicar=self.adaptativo_activo)

    # 2 ─ antes del manifiesto
    def revisar(self, qa, pptx: Path, fill, result, out_dir: Path) -> None:
        valores, nums = cifras.recolectar_valores(result), _nums_narrativa(fill)
        spec = slidespec.construir(pptx, valores, nums, self.escenario.id, self.perfil, self.fuentes)
        sd = spec.to_dict()
        vista = previsualizacion.modelo(pptx, [s.id for s in spec.diapositivas], [s.tipo for s in spec.diapositivas])
        huellas = {"pptx": previsualizacion.huella_archivo(pptx), "slidespec": sd["huella"], "escenario": self.escenario.huella(), "vista_previa": vista["huella"],
                   "entradas": self.huella_entradas, "adaptativo": self.adaptativo_activo}
        anteriores = list(qa.issues)
        inf = self.informe_diseno or adaptativo.InformeDiseno()
        self.informe = qa_integral.evaluar(spec=spec, esc=self.escenario, pptx=pptx, vista=vista, informe_diseno=inf, aplicado=self.adaptativo_activo, qa_anterior=anteriores,
                                           valores_motor=valores, narrativa_nums=nums, parrafos=fill.narrative, indicadores=self.indicadores, fuentes=self.fuentes,
                                           perfil=self.perfil, huellas=huellas)
        for h in self.informe.hallazgos:
            if h.origen == "integral":                                # los del QA anterior ya están en `qa`; aquí solo se añaden los nuevos, con su severidad
                qa.add(h.id, _SEV_QA[h.severidad], h.indice, h.descripcion + (f" Acción: {h.accion}" if h.accion else ""))
        out_dir = Path(out_dir)
        _escribir(out_dir / "slidespec.json", sd)
        _escribir(out_dir / "previsualizacion.json", vista)
        _escribir(out_dir / "qa_integral.json", self.informe.to_dict())
        _escribir(out_dir / "plan_reporte.json", {"esquema": "plan_reporte/1", "escenario": self.escenario.to_dict(), "perfil": self.perfil,
                                                  "opciones": {"diseno_adaptativo": self.adaptativo_activo}, "diseno": inf.to_dict(), "huellas": huellas,
                                                  "campos_no_definidos": self.escenario.no_definidos()})


def vigente(out_dir: Path, huella_entradas: str | None) -> dict:
    """¿Siguen vigentes la vista previa y el QA integral? Compara el PPTX actual, y las entradas del reporte, con las huellas guardadas al generar.

    {"vigente": bool, "motivos": [...]}. Si falta algún archivo, NO es vigente (nunca se asume que lo es)."""
    out_dir = Path(out_dir)
    motivos: list[str] = []
    try:
        plan = json.loads((out_dir / "plan_reporte.json").read_text(encoding="utf-8"))
        h = plan["huellas"]
    except (OSError, ValueError, KeyError):
        return {"vigente": False, "motivos": ["No hay resultados del flujo integrado para este reporte (plan_reporte.json)."]}
    pptx = next(out_dir.glob("*.pptx"), None)
    if pptx is None:
        return {"vigente": False, "motivos": ["No se encuentra el PPTX generado."]}
    if previsualizacion.huella_archivo(pptx) != h.get("pptx"):
        motivos.append("El PPTX cambió después de la vista previa y el QA.")
    if huella_entradas is not None and h.get("entradas") != huella_entradas:
        motivos.append("Cambió el contenido, las metas, el contexto, el escenario o las opciones desde que se generó el reporte.")
    return {"vigente": not motivos, "motivos": motivos}


def huella_de(*partes) -> str:
    """Huella determinista de las entradas del reporte (se calcula en el servicio con el libro, ediciones, contexto, metas, escenario y opciones)."""
    return hashlib.sha256(json.dumps(partes, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()
