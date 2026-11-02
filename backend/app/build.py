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
from .deck.extras import add_executive_slides
from .narrative.executive import build_executive
from .narrative.writer import fit, to_paragraphs, verify_all
from .models import Period
from .pipeline import Result
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


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def build_aetops(result: Result, period: Period, template: Path, out_dir: Path,
                         narrative: dict | None = None, allow_blockers: bool = False,
                         fix_titles: bool = True, executive: bool = True) -> BuildResult:
    template, out_dir = Path(template), Path(out_dir)
    blockers = [f for f in result.findings if f.severity == "block"]
    if blockers and not allow_blockers:
        raise ReportBlocked(blockers)
    out_dir.mkdir(parents=True, exist_ok=True)

    prs = Presentation(template)
    fill_fn = fill_aetops_mensual if period.periodicity == "mensual" else fill_aetops_trimestral
    fill = fill_fn(prs, result, period, narrative, fix_titles)
    slide_map = None
    if executive:                                   # resumen ejecutivo (inicio) + recomendaciones (final)
        ex = build_executive(result, period)
        fill.narrative_problems += verify_all(ex.resumen + ex.recomendaciones)
        slide_map, kept_res, kept_rec = add_executive_slides(prs, ex.resumen, ex.recomendaciones, to_paragraphs, fit)
        fill.narrative["resumen_ejecutivo"], fill.narrative["recomendaciones"] = kept_res, kept_rec
        fill.narrative["descubrimientos"] = [p for _, p in ex.descubrimientos]
        fill.recommendations = ex.recs
    stem = period.month_name.capitalize() if period.periodicity == "mensual" else f"Q{period.index}"
    pptx = out_dir / f"Resultados_AETOP_{stem}_{period.year}.pptx"
    prs.save(pptx)

    pdf = convert_to_pdf(pptx, out_dir)
    pngs = pdf_to_pngs(pdf, out_dir / "png")
    tpl_dir = out_dir / "_plantilla"
    tpl_pdf = convert_to_pdf(template, tpl_dir)
    tpl_pngs = pdf_to_pngs(tpl_pdf, tpl_dir / "png")

    qa = checks.QAReport()
    checks.check_render(pptx, pdf, qa)
    checks.check_editable_and_static(pptx, template, qa, slide_map)
    checks.check_static_regions(pngs, tpl_pngs, qa, template, slide_map)
    checks.check_stale(fill, qa)
    for prob in fill.narrative_problems:
        qa.add("NARRATIVE_UNVERIFIED", "error", None, f"Narrativa sin evidencia: {prob}")
    for prob in fill.edited_unverified:
        qa.add("EDITED_TEXT_UNVERIFIED", "warn", None, f"Texto editado a mano: {prob}")
    (out_dir / "narrative.json").write_text(json.dumps({
        key: [{"texto": p.plain, "tipo": p.kind, "regla": p.basis, "cifras": sorted(p.nums), "evidencia": p.evidence,
               "prioridad": p.priority, "visible_en_diapositiva": p.visible, "editado": p.edited}
              for p in paras] for key, paras in fill.narrative.items()}, ensure_ascii=False, indent=1), encoding="utf-8")
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
        "plantilla_sha256": _sha(template), "pptx_sha256": _sha(pptx), "pdf_sha256": _sha(pdf),
        "qa_passed": qa.passed, "hallazgos_bloqueantes": [f.id for f in blockers],
        "fuente_render": "Carlito (sustituye Aptos Narrow solo en PDF/QA)",
    }
    (out_dir / "qa_report.json").write_text(json.dumps(qa.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    shutil.rmtree(tpl_dir, ignore_errors=True)
    return BuildResult(pptx, pdf, pngs, qa, fill, qa.passed, manifest)


build_aetops_mensual = build_aetops          # nombre de la 5a (compatibilidad)
