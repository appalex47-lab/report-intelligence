"""Orquestación: resultado del motor -> PPTX -> PDF -> QA. La descarga solo se habilita con QA verde."""
from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from pptx import Presentation

from .deck.aetops_mensual import FillReport, fill_aetops_mensual
from .deck.aetops_trimestral import fill_aetops_trimestral
from .deck.extras import add_discovery_slide, add_executive_slides
from .deck.glp1_mensual import DECORATIVE, fill_glp1
from .history import store as hist
from .narrative import trends
from .narrative.executive import build_executive
from .narrative.glp1_exec import attainment_glp1, build_executive_glp1
from .narrative.targets import attainment
from .narrative.writer import Para, fit, to_paragraphs, verify_all, verify_edited
from .models import Period
from .pipeline import GlpResult, Result
from .provenance_capture import ejecutar as registrar_procedencia
from .qa import checks
from .render import convert_to_pdf, pdf_to_pngs


class ReportBlocked(Exception):
    def __init__(self, findings):
        self.findings = findings
        super().__init__("; ".join(f"{f.id}: {f.message}" for f in findings[:3]))


@dataclass
class BuildResult:
    pptx: Path
    pdf: Path
    pngs: list[Path]
    qa: checks.QAReport
    fill: FillReport
    downloadable: bool
    manifest: dict = field(default_factory=dict)
    procedencia: dict = field(default_factory=dict)        # resultado de la captura de procedencia (Fase 3A-3); no altera el reporte


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _render_and_check(pptx: Path, template: Path, out_dir: Path, slide_map, qa, render: bool, decorative=None):
    """QA del PPTX. Con `render` (LibreOffice disponible): PDF + comprobaciones visuales completas. Sin él (navegador): solo QA
    estructural y estimación geométrica; no hay PDF ni vista previa. Devuelve (pdf|None, pngs, carpeta temporal|None)."""
    checks.check_editable_and_static(pptx, template, qa, slide_map, decorative)
    checks.check_geometry(pptx, qa, template, slide_map)
    if not render:
        qa.add("QA_VISUAL_OMITIDO", "info", None,
               "QA estructural (sin render): no se generó PDF ni se comprobó el desborde visual; revisa el PPTX antes de distribuirlo.")
        return None, [], None
    pdf = convert_to_pdf(pptx, out_dir)
    pngs = pdf_to_pngs(pdf, out_dir / "png")
    tpl_dir = out_dir / "_plantilla"
    tpl_pdf = convert_to_pdf(template, tpl_dir)
    tpl_pngs = pdf_to_pngs(tpl_pdf, tpl_dir / "png")
    checks.check_render(pptx, pdf, qa)
    checks.check_static_regions(pngs, tpl_pngs, qa, template, slide_map, decorative)
    return pdf, pngs, tpl_dir


def _discovery_slide(prs, discovery: dict | None, fill, slide_map, n_template: int):
    """Agrega la hoja de descubrimiento (IA propuesta y validada por el usuario) y la deja registrada en narrative.json."""
    if not (discovery or {}).get("items"):
        return slide_map
    sm, kept = add_discovery_slide(prs, discovery, slide_map, n_template)
    fill.narrative["descubrimiento_ia"] = kept
    return sm


def _exec_slides(prs, ex, fill, context, ed_res, ed_rec):
    """Añade resumen ejecutivo y recomendaciones (con contexto del equipo y ediciones manuales verificadas). Devuelve el mapa de QA."""
    ctx = [c.strip() for c in (context or []) if c and c.strip()]
    if ctx:                                         # contexto aportado por el equipo: marcado, sin verificar, nunca se descarta
        ex.resumen.append(Para("**Contexto aportado por el equipo**", "contexto", 0, basis="texto del equipo; no verificado"))
        ex.resumen += [Para(c, "contexto", 0, basis="texto del equipo; no verificado") for c in ctx]
    fill.narrative_problems += verify_all(ex.resumen + ex.recomendaciones)
    known = set().union(*(p.nums for ps in fill.narrative.values() for p in ps), *(p.nums for p in ex.resumen + ex.recomendaciones))
    for edits, attr in ((ed_res, "resumen"), (ed_rec, "recomendaciones")):
        if edits is not None:                       # edición manual: se publica, pero una cifra sin respaldo se avisa
            paras = [Para(t, "hecho", 0, edited=True) for t in edits if t.strip() != ""]
            fill.edited_unverified += [f"{attr}: {x}" for p in paras for x in verify_edited(p.plain, known)]
            setattr(ex, attr, paras)
    slide_map, kept_res, kept_rec = add_executive_slides(prs, ex.resumen, ex.recomendaciones, to_paragraphs, fit)
    fill.narrative["resumen_ejecutivo"], fill.narrative["recomendaciones"] = kept_res, kept_rec
    fill.narrative["descubrimientos"] = [p for _, p in ex.descubrimientos]
    fill.recommendations = ex.recs
    return slide_map


def build_aetops(result: Result, period: Period, template: Path, out_dir: Path,
                         narrative: dict | None = None, allow_blockers: bool = False,
                         fix_titles: bool = True, executive: bool = True,
                 context: list[str] | None = None, history_db: Path | None = None,
                 sources: list[Path] | None = None, targets=None, render: bool = True, discovery: dict | None = None,
                 ia: dict | None = None) -> BuildResult:
    template, out_dir = Path(template), Path(out_dir)
    blockers = [f for f in result.findings if f.severity == "block"]
    if blockers and not allow_blockers:
        raise ReportBlocked(blockers)
    out_dir.mkdir(parents=True, exist_ok=True)

    prs = Presentation(template)
    n_template = len(prs.slides)
    fill_fn = fill_aetops_mensual if period.periodicity == "mensual" else fill_aetops_trimestral
    att = attainment(result, targets)
    narrative = dict(narrative or {})
    ed_res, ed_rec = narrative.pop("resumen_ejecutivo", None), narrative.pop("recomendaciones", None)
    fill = fill_fn(prs, result, period, narrative, fix_titles, att=att)
    slide_map = None
    if executive:                                   # resumen ejecutivo (inicio) + recomendaciones (final)
        slide_map = _exec_slides(prs, build_executive(result, period, att=att), fill, context, ed_res, ed_rec)
    slide_map = _discovery_slide(prs, discovery, fill, slide_map, n_template)
    stem = period.month_name.capitalize() if period.periodicity == "mensual" else f"Q{period.index}"
    pptx = out_dir / f"Resultados_AETOP_{stem}_{period.year}.pptx"
    prs.save(pptx)

    qa = checks.QAReport()
    pdf, pngs, tpl_dir = _render_and_check(pptx, template, out_dir, slide_map, qa, render)
    checks.check_stale(fill, qa)
    for prob in fill.narrative_problems:
        qa.add("NARRATIVE_UNVERIFIED", "error", None, f"Narrativa sin evidencia: {prob}")
    for prob in fill.edited_unverified:
        qa.add("EDITED_TEXT_UNVERIFIED", "warn", None, f"Texto editado a mano: {prob}")
    (out_dir / "narrative.json").write_text(json.dumps({
        key: [{"texto": p.plain, "tipo": p.kind, "regla": p.basis, "cifras": sorted(p.nums), "evidencia": p.evidence,
               "prioridad": p.priority, "visible_en_diapositiva": p.visible, "editado": p.edited}
              for p in paras] for key, paras in fill.narrative.items()}, ensure_ascii=False, indent=1), encoding="utf-8")
    if context:
        qa.add("CONTEXT_UNVERIFIED", "info", None, "El resumen incluye contexto aportado por el equipo; no se verifica contra los datos.")
    for t in fill.titles_fixed:
        qa.add("LABEL_CROSSED_FIXED", "info", None, f"Título cruzado en la plantilla, corregido: {t}")
    for n in fill.notes:
        qa.add("FILL_NOTE", "info", None, n)
    for f in result.findings:
        if f.severity == "warn":
            qa.add(f"DATA_{f.id}", "warn", None, f.message)
    if blockers:
        qa.add("GENERATED_WITH_BLOCKERS", "error", None,
               "Generado ignorando hallazgos bloqueantes (solo desarrollo): NO apto para descarga.")

    manifest = {
        "periodo": period.label if period.periodicity == "trimestral" else f"{period.month_name} {period.year}", "plantilla": template.name,
        "plantilla_sha256": _sha(template), "pptx_sha256": _sha(pptx), "pdf_sha256": _sha(pdf) if pdf else None,
        "qa_passed": qa.passed, "hallazgos_bloqueantes": [f.id for f in blockers],
        "fuente_render": "Carlito (sustituye Aptos Narrow solo en PDF/QA)",
    }
    (out_dir / "qa_report.json").write_text(json.dumps(qa.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    if tpl_dir:
        shutil.rmtree(tpl_dir, ignore_errors=True)
    if history_db:
        _record(result, period, template, out_dir, pptx, pdf, qa, fill, context, sources, history_db, manifest, targets)
    proc = _procedencia(out_dir, period, result, fill, sources, template, pptx, history_db, manifest, targets, context, ia)
    return BuildResult(pptx, pdf, pngs, qa, fill, qa.passed, manifest, proc)


def _procedencia(out_dir, period, result, fill, sources, template, pptx, history_db, manifest, targets, context, ia) -> dict:
    """Captura y registra la procedencia DESPUÉS de guardar el PPTX y la corrida del historial (Fase 3A-3). No lanza nunca y no modifica el
    reporte: si falla, queda `procedencia_error.json` y el reporte sigue siendo válido (spec §8.4)."""
    try:
        run_id = (manifest.get("historial") or {}).get("run_id")
        return registrar_procedencia(carpeta=out_dir, period=period, result=result, narrative=fill.narrative, sources=sources, template=template,
                                     pptx=pptx, history_db=history_db or None, run_id=run_id, targets=targets, context=context, ia=ia)
    except Exception as e:                                  # noqa: BLE001 - la captura ya no lanza; esto cubre un fallo imprevisto de la propia llamada
        return {"estado": "error", "etapa": None, "error": f"{type(e).__name__}", "archivo": None, "archivo_error": None}


def _record(result, period, template, out_dir, pptx, pdf, qa, fill, context, sources, history_db, manifest, targets=None, kpis=None):
    """Guarda la foto de KPIs del reporte (nueva versión, nunca sobrescribe) y escribe trends.json."""
    con = hist.connect(history_db)
    narrative = {k: [{"texto": p.plain, "tipo": p.kind, "regla": p.basis} for p in ps] for k, ps in fill.narrative.items()}
    rid = hist.record_run(
        con, period, kpis if kpis is not None else hist.snapshot_from_result(result, period, targets), profile=period.periodicity, template=template,
        sources=sources, pptx=pptx, pdf=pdf, qa_passed=qa.passed, downloadable=qa.passed,
        findings=[{"id": f.id, "severity": f.severity, "message": f.message} for f in result.findings],
        narrative=narrative, context=context)
    ver = con.execute("SELECT version FROM runs WHERE id=?", (rid,)).fetchone()[0]
    manifest["historial"] = {"run_id": rid, "version": ver}
    ts = trends.trends_for(con, period.unit, period.periodicity)
    (out_dir / "trends.json").write_text(json.dumps([{
        "metrica": t.metric, "tendencia": t.direction, "racha": t.streak,
        "ultima_variacion": float(t.last) if t.last is not None else None,
        "acumulada": float(t.cumulative) if t.cumulative is not None else None,
        "texto": t.para.plain if t.para else "", "tipo": t.para.kind if t.para else "", "regla": t.para.basis if t.para else "",
        "puntos": [{"periodo": trends.plabel(period.periodicity, p), "valor": float(p.value), "fuente": p.source} for p in t.points]}
        for t in ts], ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    con.close()


def build_glp1(result: GlpResult, period: Period, template: Path, out_dir: Path, narrative: dict | None = None,
               allow_blockers: bool = False, sources: list[Path] | None = None, executive: bool = True,
               context: list[str] | None = None, targets=None, history_db: Path | None = None, render: bool = True,
               discovery: dict | None = None, ia: dict | None = None) -> BuildResult:
    """GLP-1 mensual: rellena la plantilla, convierte a PDF y aplica el QA (sin resumen ejecutivo ni metas por ahora)."""
    template, out_dir = Path(template), Path(out_dir)
    blockers = [f for f in result.findings if f.severity == "block"]
    if blockers and not allow_blockers:
        raise ReportBlocked(blockers)
    out_dir.mkdir(parents=True, exist_ok=True)
    prs = Presentation(template)
    n_template = len(prs.slides)
    narrative = dict(narrative or {})
    ed_res, ed_rec = narrative.pop("resumen_ejecutivo", None), narrative.pop("recomendaciones", None)
    att = attainment_glp1(result.blocks, targets)
    fill = fill_glp1(prs, result.blocks, result.funnel, period, narrative)
    slide_map = None
    if executive:
        slide_map = _exec_slides(prs, build_executive_glp1(result.blocks, result.funnel, period, att=att), fill, context, ed_res, ed_rec)
    slide_map = _discovery_slide(prs, discovery, fill, slide_map, n_template)
    stem = period.month_name.capitalize() if period.periodicity == "mensual" else f"Q{period.index}"
    pptx = out_dir / f"Resultados_GLP1_{stem}_{period.year}.pptx"
    prs.save(pptx)
    qa = checks.QAReport()
    pdf, pngs, tpl_dir = _render_and_check(pptx, template, out_dir, slide_map, qa, render, DECORATIVE)
    checks.check_stale(fill, qa)
    for prob in fill.narrative_problems:
        qa.add("NARRATIVE_UNVERIFIED", "error", None, f"Narrativa sin evidencia: {prob}")
    for prob in fill.edited_unverified:
        qa.add("EDITED_TEXT_UNVERIFIED", "warn", None, f"Texto editado a mano: {prob}")
    (out_dir / "narrative.json").write_text(json.dumps({
        key: [{"texto": p.plain, "tipo": p.kind, "regla": p.basis, "cifras": sorted(p.nums), "evidencia": p.evidence,
               "prioridad": p.priority, "visible_en_diapositiva": p.visible, "editado": p.edited} for p in paras]
        for key, paras in fill.narrative.items()}, ensure_ascii=False, indent=1), encoding="utf-8")
    if context:
        qa.add("CONTEXT_UNVERIFIED", "info", None, "El resumen incluye contexto aportado por el equipo; no se verifica contra los datos.")
    for t in fill.titles_fixed:
        qa.add("LABEL_CROSSED_FIXED", "info", None, f"Título corregido: {t}")
    for n in fill.notes:
        qa.add("FILL_NOTE", "info", None, n)
    for f in result.findings:
        if f.severity == "warn":
            qa.add(f"DATA_{f.id}", "warn", None, f.message)
    if blockers:
        qa.add("GENERATED_WITH_BLOCKERS", "error", None, "Generado ignorando hallazgos bloqueantes (solo desarrollo): NO apto para descarga.")
    manifest = {"periodo": period.label if period.periodicity == "trimestral" else f"{period.month_name} {period.year}", "plantilla": template.name, "plantilla_sha256": _sha(template),
                "pptx_sha256": _sha(pptx), "pdf_sha256": _sha(pdf) if pdf else None, "qa_passed": qa.passed,
                "hallazgos_bloqueantes": [f.id for f in blockers], "fuente_render": "Carlito (sustituye Aptos Narrow solo en PDF/QA)"}
    (out_dir / "qa_report.json").write_text(json.dumps(qa.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    if tpl_dir:
        shutil.rmtree(tpl_dir, ignore_errors=True)
    if history_db:
        class _R:                                   # _record solo usa .findings del resultado
            findings = result.findings
        _record(_R, period, template, out_dir, pptx, pdf, qa, fill, context, sources, history_db, manifest, targets,
                kpis=hist.snapshot_from_glp1(result.blocks, period, targets))
    proc = _procedencia(out_dir, period, result, fill, sources, template, pptx, history_db, manifest, targets, context, ia)
    return BuildResult(pptx, pdf, pngs, qa, fill, qa.passed, manifest, proc)


build_aetops_mensual = build_aetops          # nombre de la 5a (compatibilidad)
