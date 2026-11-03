"""Servicio de la pantalla de revisión: corridas en disco, validación, narrativa editable y generación.

Una corrida = carpeta `runs/<uuid>/` con `run.json` (estado), `input.xlsx` y `out/` (resultado). Sin base de datos
propia: el historial inmutable (SQLite) es el de `history/store.py`. Todo lo calculado sale del motor; aquí solo se orquesta."""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import uuid
import zipfile
from pathlib import Path

from pptx import Presentation

from ..build import ReportBlocked, build_aetops, build_glp1
from ..deck.aetops_mensual import DataMissing, TemplateMismatch, fill_aetops_mensual
from ..deck.aetops_trimestral import fill_aetops_trimestral
from ..deck.glp1_mensual import fill_glp1
from ..history import store as hist
from ..models import Period
from ..narrative import trends
from ..narrative.executive import build_executive
from ..narrative.facts import aetops_facts, glp1_facts, trend_facts, verify_discovery
from ..narrative.glp1_exec import attainment_glp1, build_executive_glp1
from ..narrative.targets import attainment
from ..narrative.writer import CAUSAL, NUMBER, Para, verify_all, verify_edited
from ..pipeline import run_aetops, run_aetops_raw, run_glp1, run_glp1_raw
from ..raw.aetops import is_raw_workbook
from ..targets import Targets

ROOT = Path(__file__).resolve().parents[3]
RUNS_DIR = Path(os.environ.get("REPORT_RUNS_DIR", ROOT / "runs"))
TEMPLATES_DIR = Path(os.environ.get("REPORT_TEMPLATES_DIR", ROOT / "templates"))
HISTORY_DB = Path(os.environ.get("REPORT_HISTORY_DB", ROOT / "historial" / "historial.sqlite"))
MAX_UPLOAD = 25 * 1024 * 1024
IN_BROWSER = sys.platform == "emscripten"                       # Pyodide: sin LibreOffice (ni PDF ni QA visual)
RENDER = (not IN_BROWSER) and bool(shutil.which("soffice") or shutil.which("libreoffice"))
TEMPLATE_KEYS = {"aetops-mensual": "AETOPS mensual", "aetops-trimestral": "AETOPS trimestral", "glp1-mensual": "GLP-1 mensual",
                 "glp1-trimestral": "GLP-1 trimestral"}
ID_RE = re.compile(r"^[0-9a-f]{32}$")
LINES = ["AE-A", "AE-B", "AE-C", "HYR"]
SLIDE_TITLES = {
    "resumen_ejecutivo": "Resumen ejecutivo", "recomendaciones": "Recomendaciones", "panorama": "Panorama",
    "linea_yoy": "Líneas YoY", "linea_mom": "Líneas MoM", "canal_yoy": "Canales YoY", "canal_mom": "Canales MoM",
    "productos": "Productos", "movers": "Mayores alzas y bajas", "cat_yoy": "Categorías YoY", "cat_mom": "Categorías MoM",
    "negados": "Negados", "conclusiones": "Conclusiones", "crecimiento": "Productos: mayor crecimiento", "decrecimiento": "Productos: mayor decrecimiento",
    "quien": "¿Quién busca GLP1?", "producto_sexo": "Producto por sexo", "region": "Región", "pago": "Pago y entrega",
    "funnel": "Embudo y negados", "programas": "Programas", "fuentes": "Fuentes de tráfico",
}


class ServiceError(Exception):
    def __init__(self, msg: str, status: int = 400):
        super().__init__(msg)
        self.status = status


# ------------------------------------------------------------------ estado de la corrida
def _dir(run_id: str) -> Path:
    if not ID_RE.match(run_id or ""):
        raise ServiceError("Identificador de corrida inválido.", 404)
    d = RUNS_DIR / run_id
    if not d.is_dir():
        raise ServiceError("Corrida no encontrada.", 404)
    return d


def _load(run_id: str) -> dict:
    return json.loads((_dir(run_id) / "run.json").read_text(encoding="utf-8"))


def _save(run_id: str, st: dict) -> None:
    (_dir(run_id) / "run.json").write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


def period_of(st: dict) -> Period:
    return Period("AETOPS" if st["unit"] == "aetops" else "GLP1", st["periodicity"], int(st["year"]), int(st["index"]))


def create_run(unit: str, periodicity: str, year: int, index: int) -> dict:
    if unit not in ("aetops", "glp1") or periodicity not in ("mensual", "trimestral"):
        raise ServiceError("Unidad o periodicidad no válida.")
    if not (2000 <= year <= 2100) or not (1 <= index <= (12 if periodicity == "mensual" else 4)):
        raise ServiceError("Periodo no válido.")
    rid = uuid.uuid4().hex
    (RUNS_DIR / rid).mkdir(parents=True)
    st = {"id": rid, "unit": unit, "periodicity": periodicity, "year": year, "index": index, "filename": None,
          "targets": {}, "context": [], "edits": {}, "generated": False, "discovery": None}
    _save(rid, st)
    return public(st)


def public(st: dict) -> dict:
    return {**{k: st[k] for k in ("id", "unit", "periodicity", "year", "index", "filename", "targets", "context", "edits", "generated")},
            "discovery": st.get("discovery")}


def get_run(run_id: str) -> dict:
    return public(_load(run_id))


def store_file(run_id: str, filename: str, data: bytes) -> dict:
    st = _load(run_id)
    if not filename.lower().endswith(".xlsx"):
        raise ServiceError("Solo se aceptan libros .xlsx (sin macros).")
    if len(data) > MAX_UPLOAD:
        raise ServiceError("El archivo supera 25 MB.", 413)
    if data[:2] != b"PK":
        raise ServiceError("El archivo no es un libro .xlsx válido.")
    p = _dir(run_id) / "input.xlsx"
    p.write_bytes(data)
    try:
        with zipfile.ZipFile(p) as z:
            if any(n.lower().endswith("vbaproject.bin") for n in z.namelist()):
                raise ServiceError("El libro contiene macros; no se admite.")
            if "xl/workbook.xml" not in z.namelist():
                raise ServiceError("El archivo no es un libro de Excel.")
    except zipfile.BadZipFile:
        p.unlink(missing_ok=True)
        raise ServiceError("El archivo está dañado o no es .xlsx.") from None
    except ServiceError:
        p.unlink(missing_ok=True)
        raise
    st["filename"] = Path(filename).name[:120]
    st["generated"] = False
    _save(run_id, st)
    return public(st)


def set_targets(run_id: str, data: dict) -> dict:
    st = _load(run_id)
    try:
        t = Targets.parse(data or {})
    except ValueError as e:
        raise ServiceError(str(e)) from None
    if any(v < 0 for v in ([t.total] if t.total is not None else []) + list(t.by_group.values())):
        raise ServiceError("Las metas no pueden ser negativas.")
    st["targets"] = t.to_dict()
    _save(run_id, st)
    return public(st)


def set_context(run_id: str, items: list[str]) -> dict:
    st = _load(run_id)
    st["context"] = [str(x).strip()[:600] for x in (items or []) if str(x).strip()][:6]
    _save(run_id, st)
    return public(st)


def set_edits(run_id: str, edits: dict) -> dict:
    st = _load(run_id)
    st["edits"] = {str(k): [str(t) for t in v] for k, v in (edits or {}).items() if isinstance(v, list)}
    _save(run_id, st)
    return public(st)


# ------------------------------------------------------------------ análisis
def _targets(st: dict) -> Targets | None:
    return Targets.parse(st["targets"]) if st["targets"] else None


def _input(run_id: str) -> Path:
    p = _dir(run_id) / "input.xlsx"
    if not p.exists():
        raise ServiceError("Primero carga el libro de Excel.")
    return p


def _run_engine(run_id: str, st: dict):
    p, per = _input(run_id), period_of(st)
    if st["unit"] == "glp1":
        if is_raw_workbook(p):
            return run_glp1_raw(p, per)
        return run_glp1(p, st["periodicity"], per)
    if is_raw_workbook(p):                          # datos crudos (docs/CONTRATO_DATOS.md): ventas + catálogo + negados
        return run_aetops_raw(p, per, targets=_targets(st), require_targets=True)
    return run_aetops(p, st["periodicity"], per, targets=_targets(st), require_targets=True)


def _finding(f) -> dict:
    return {"id": f.id, "severity": f.severity, "message": f.message, "evidence": f.evidence}


def _kpis(res, st) -> list[dict]:
    if st["unit"] != "aetops" or "aetops.panorama.yoy" not in res.tables or not res.tables["aetops.panorama.yoy"].groups:
        return []                                   # periodo sin datos: ya hay un hallazgo que lo explica
    g = res.tables["aetops.panorama.yoy"].groups[0]
    out = []
    for k, label in (("monto", "Venta"), ("pacientes", "Pacientes"), ("ticket", "Ticket"), ("piezas", "Piezas")):
        v, d = g.current.values.get(k), g.pct.get(k)
        out.append({"metrica": label, "valor": float(v.v) if v and v.v is not None else None,
                    "delta": float(d.v) if d and d.v is not None else None})
    return out


def analyze(run_id: str) -> dict:
    st = _load(run_id)
    res = _run_engine(run_id, st)
    findings = [_finding(f) for f in res.findings]
    att = []
    if st["unit"] == "aetops" and res.tables:
        att = [{"nombre": a.name, "real": float(a.actual), "meta": float(a.target), "cumplimiento": float(a.pct),
                "brecha": float(a.gap), "estado": a.status} for a in attainment(res, _targets(st))]
    gen_ok = _has_template(st)
    return {"run": public(st), "can_generate": res.can_generate and gen_ok, "findings": findings,
            "kpis": _kpis(res, st), "cumplimiento": att,
            "targets_required": st["unit"] == "aetops", "targets_lines": [],
            "generator_available": gen_ok,
            "template_key": f"{st['unit']}-{st['periodicity']}", "template_label": TEMPLATE_KEYS.get(f"{st['unit']}-{st['periodicity']}", ""),
            "message": None if gen_ok else (f"Falta la plantilla PPTX de {TEMPLATE_KEYS.get(st['unit'] + '-' + st['periodicity'], 'este formato')}: "
                                            "cárgala en la pestaña «Plantillas» para poder revisar la narrativa y generar el reporte.")}


def _has_template(st: dict) -> bool:
    return (TEMPLATES_DIR / f"{st['unit']}-{st['periodicity']}" / "1" / "template.pptx").exists()


def template_path(st: dict) -> Path:
    p = TEMPLATES_DIR / f"{st['unit']}-{st['periodicity']}" / "1" / "template.pptx"
    if not p.exists():
        raise ServiceError(f"Falta la plantilla {p.relative_to(TEMPLATES_DIR.parent) if TEMPLATES_DIR.parent in p.parents else p.name}.", 500)
    return p


def _paras(ps: list[Para]) -> list[dict]:
    return [{"texto": p.plain, "tipo": p.kind, "regla": p.basis, "cifras": sorted(p.nums), "visible": p.visible,
             "editado": p.edited, "evidencia": p.evidence} for p in ps]


def narrative(run_id: str) -> dict:
    st = _load(run_id)
    res = _run_engine(run_id, st)
    if not res.can_generate:
        raise ServiceError("Hay hallazgos bloqueantes: corrígelos antes de revisar la narrativa.", 409)
    per, tpl = period_of(st), template_path(st)
    if st["unit"] == "glp1":
        try:
            fill = fill_glp1(Presentation(tpl), res.blocks, res.funnel, per, None)
        except (DataMissing, TemplateMismatch) as e:
            raise ServiceError(f"Faltan datos para la plantilla de GLP-1: {e}", 409) from None
        sections = dict(fill.narrative)
        ex = build_executive_glp1(res.blocks, res.funnel, per, att=attainment_glp1(res.blocks, _targets(st)))
        ctx = [c for c in st["context"] if c.strip()]
        if ctx:
            ex.resumen = ex.resumen + [Para("**Contexto aportado por el equipo**", "contexto", 0, basis="texto del equipo; no verificado")] \
                + [Para(c, "contexto", 0, basis="texto del equipo; no verificado") for c in ctx]
        sections["resumen_ejecutivo"], sections["recomendaciones"] = ex.resumen, ex.recomendaciones
        order = ["resumen_ejecutivo"] + [k for k in sections if k not in ("resumen_ejecutivo", "recomendaciones")] + ["recomendaciones"]
        known = sorted(set().union(*(p.nums for ps in sections.values() for p in ps)))
        return {"secciones": [{"clave": k, "titulo": SLIDE_TITLES.get(k, k), "parrafos": _paras(sections[k])} for k in order],
                "cifras_validas": known, "problemas": fill.narrative_problems + verify_all(ex.resumen + ex.recomendaciones),
                "ediciones": st["edits"]}
    att = attainment(res, _targets(st))
    prs = Presentation(tpl)
    try:
        fill = (fill_aetops_mensual if per.periodicity == "mensual" else fill_aetops_trimestral)(prs, res, per, None, True, att=att)
    except (DataMissing, TemplateMismatch) as e:
        raise ServiceError(f"La plantilla cargada no coincide con el formato ({e}). Vuelve a cargar el PPTX original en la pestaña «Plantillas».", 409) from None
    ex = build_executive(res, per, att=att)
    sections = dict(fill.narrative)
    ctx = [c for c in st["context"] if c.strip()]
    if ctx:                                         # igual que en la generación: contexto del equipo, marcado y sin verificar
        ex.resumen = ex.resumen + [Para("**Contexto aportado por el equipo**", "contexto", 0, basis="texto del equipo; no verificado")] \
            + [Para(c, "contexto", 0, basis="texto del equipo; no verificado") for c in ctx]
    sections["resumen_ejecutivo"], sections["recomendaciones"] = ex.resumen, ex.recomendaciones
    order = ["resumen_ejecutivo"] + [k for k in sections if k not in ("resumen_ejecutivo", "recomendaciones", "descubrimientos")] + ["recomendaciones"]
    known = sorted(set().union(*(p.nums for ps in sections.values() for p in ps)))
    return {"secciones": [{"clave": k, "titulo": SLIDE_TITLES.get(k, k), "parrafos": _paras(sections[k])} for k in order if k in sections],
            "cifras_validas": known, "problemas": fill.narrative_problems + verify_all(ex.resumen + ex.recomendaciones),
            "ediciones": st["edits"]}


def verify_text(run_id: str, texts: list[str], allowed: list[str] | None = None) -> list[dict]:
    st = _load(run_id)
    if allowed is None:
        allowed = narrative(run_id)["cifras_validas"]
    ok = set(allowed)
    return [{"texto": t, "problemas": verify_edited(t, ok)} for t in texts]


def history_trends(unit: str = "aetops", periodicity: str = "mensual") -> list[dict]:
    if not HISTORY_DB.exists():
        return []
    con = hist.connect(HISTORY_DB)
    try:
        return [{"metrica": t.metric, "tendencia": t.direction, "racha": t.streak,
                 "ultima_variacion": float(t.last) if t.last is not None else None,
                 "texto": t.para.plain if t.para else "", "tipo": t.para.kind if t.para else "",
                 "puntos": [{"periodo": trends.plabel(periodicity, p), "valor": float(p.value), "fuente": p.source} for p in t.points]}
                for t in trends.trends_for(con, unit.upper(), periodicity)]
    finally:
        con.close()


def history_runs(unit: str | None = None) -> list[dict]:
    if not HISTORY_DB.exists():
        return []
    con = hist.connect(HISTORY_DB)
    try:
        cols = ["id", "unidad", "periodicidad", "anio", "indice", "version", "creado", "qa_ok", "descargable"]
        return [dict(zip(cols, r)) for r in hist.list_runs(con, unit.upper() if unit else None)]
    finally:
        con.close()


# ------------------------------------------------------------------ generación
OUT_FILES = {"pptx", "pdf"}


def generate(run_id: str) -> dict:
    st = _load(run_id)
    res = _run_engine(run_id, st)
    out = _dir(run_id) / "out"
    shutil.rmtree(out, ignore_errors=True)
    try:
        if st["unit"] == "glp1":
            b = build_glp1(res, period_of(st), template_path(st), out, narrative=st["edits"] or None, sources=[_input(run_id)],
                           context=st["context"] or None, targets=_targets(st), history_db=HISTORY_DB, render=RENDER,
                           discovery=st.get("discovery"))
            st["generated"] = True
            _save(run_id, st)
            _copy_ia_log(run_id)
            return result_info(run_id, b.qa.passed)
        b = build_aetops(res, period_of(st), template_path(st), out, narrative=st["edits"] or None,
                         context=st["context"] or None, history_db=HISTORY_DB, sources=[_input(run_id)], targets=_targets(st),
                         render=RENDER, discovery=st.get("discovery"))
    except ReportBlocked as e:
        raise ServiceError(f"No se genera: hay hallazgos bloqueantes ({e}).", 409) from None
    except (DataMissing, TemplateMismatch) as e:
        raise ServiceError(f"Faltan datos para la plantilla: {e}", 409) from None
    st["generated"] = True
    _save(run_id, st)
    _copy_ia_log(run_id)
    return result_info(run_id, b.qa.passed)


def result_info(run_id: str, passed: bool | None = None) -> dict:
    out = _dir(run_id) / "out"
    if not out.is_dir():
        raise ServiceError("Aún no se ha generado el reporte.", 404)
    qa = json.loads((out / "qa_report.json").read_text(encoding="utf-8"))
    pptx = next(out.glob("*.pptx"), None)
    pdf = next(out.glob("*.pdf"), None)
    pngs = sorted(p.name for p in (out / "png").glob("*.png")) if (out / "png").is_dir() else []
    ok = bool(qa.get("passed", passed))
    return {"ia_log": (out / "ia_log.json").exists(), "qa": qa, "qa_passed": ok, "downloadable": ok, "pptx": pptx.name if pptx else None, "pdf": pdf.name if pdf else None,
            "slides": pngs, "trends": json.loads((out / "trends.json").read_text(encoding="utf-8")) if (out / "trends.json").exists() else []}


def file_path(run_id: str, name: str) -> Path:
    out = _dir(run_id) / "out"
    if not out.is_dir():
        raise ServiceError("Aún no se ha generado el reporte.", 404)
    if name in ("qa_report.json", "narrative.json", "manifest.json", "trends.json", "ia_log.json") or name.lower().endswith((".pptx", ".pdf")):
        p, base = out / name, out
    elif re.fullmatch(r"[\w\-]+\.png", name):
        p, base = out / "png" / name, out / "png"
    else:
        raise ServiceError("Archivo no permitido.", 404)
    if not p.is_file() or p.resolve().parent != base.resolve():
        raise ServiceError("Archivo no encontrado.", 404)
    if name.lower().endswith((".pptx", ".pdf")) and not json.loads((out / "qa_report.json").read_text(encoding="utf-8")).get("passed"):
        raise ServiceError("Descarga bloqueada: el QA no aprobó el reporte.", 403)
    return p


def machote(unit: str, periodicity: str, year: int, index: int, example: bool = False) -> Path:
    """Genera el machote de captura del periodo (tools/make_machotes.py) y devuelve la ruta del .xlsx."""
    import importlib.util
    import tempfile
    spec = importlib.util.spec_from_file_location("make_machotes", ROOT / "tools" / "make_machotes.py")
    if spec is None or spec.loader is None or not (ROOT / "tools" / "make_machotes.py").exists():
        raise ServiceError("El generador de machotes no está disponible.", 500)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    st = {"unit": unit, "periodicity": periodicity, "year": year, "index": index}
    if unit not in ("aetops", "glp1") or periodicity not in ("mensual", "trimestral") or not (1 <= index <= (12 if periodicity == "mensual" else 4)):
        raise ServiceError("Periodo no válido.")
    return mod.make(unit, period_of(st), Path(tempfile.mkdtemp(prefix="machote_")), example)


# ------------------------------------------------------------------ plantillas (se cargan una vez; no se versionan: llevan marca)
def list_templates() -> list[dict]:
    return [{"key": k, "label": v, "available": (TEMPLATES_DIR / k / "1" / "template.pptx").exists()} for k, v in TEMPLATE_KEYS.items()]


def save_template(key: str, filename: str, data: bytes) -> list[dict]:
    if key not in TEMPLATE_KEYS:
        raise ServiceError("Formato de plantilla desconocido.", 404)
    if not filename.lower().endswith(".pptx") or data[:2] != b"PK":
        raise ServiceError("La plantilla debe ser un .pptx.")
    if len(data) > MAX_UPLOAD:
        raise ServiceError("La plantilla supera 25 MB.", 413)
    import io
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            if "ppt/presentation.xml" not in z.namelist():
                raise ServiceError("El archivo no es una presentación de PowerPoint.")
            if any(n.lower().endswith(("vbaproject.bin",)) for n in z.namelist()):
                raise ServiceError("La plantilla contiene macros; no se admite.")
    except zipfile.BadZipFile:
        raise ServiceError("El archivo está dañado o no es .pptx.") from None
    _check_template_matches(key, data)
    d = TEMPLATES_DIR / key / "1"
    d.mkdir(parents=True, exist_ok=True)
    (d / "template.pptx").write_bytes(data)
    return list_templates()


def _check_template_matches(key: str, data: bytes) -> None:
    """Rechaza un PPTX que no sea el original de ese formato (si no, fallaría después, al generar)."""
    import io
    from ..deck import aetops_mensual, aetops_trimestral, glp1_mensual
    spec = {"aetops-mensual": (aetops_mensual.NARR, 11), "aetops-trimestral": (aetops_trimestral.NARR, 8),
            "glp1-mensual": (glp1_mensual.NARR, 11), "glp1-trimestral": (glp1_mensual.NARR, 11)}[key]
    narr, n_slides = spec
    prs = Presentation(io.BytesIO(data))
    label = TEMPLATE_KEYS[key]
    if len(prs.slides) != n_slides:
        raise ServiceError(f"Esta plantilla no corresponde a «{label}»: tiene {len(prs.slides)} diapositivas y el original tiene {n_slides}. "
                           "Carga el PPTX original de ese formato (sin el resumen ejecutivo ni las recomendaciones añadidas).")
    for _k, (slide, shape) in narr.items():
        if shape not in [sh.name for sh in prs.slides[slide - 1].shapes]:
            raise ServiceError(f"Esta plantilla no corresponde a «{label}»: en la diapositiva {slide} no existe «{shape}». "
                               "Carga el PPTX original de ese formato.")


# ------------------------------------------------------------------ redacción con IA (opcional; la llamada a Cohere la hace el navegador con la clave del usuario)
YEAR = re.compile(r"(19|20)\d\d")
MAX_GROWTH = 1.5


def _nums(text: str) -> set[str]:
    return {m.group(0).strip() for m in NUMBER.finditer(text.replace("**", ""))}


def _bold_numbers(text: str) -> str:
    """Devuelve el texto sin negritas previas y con cada cifra en **negrita** (como el texto determinista)."""
    plain = text.replace("**", "")
    return NUMBER.sub(lambda m: f"**{m.group(0)}**" if m.group(0).strip() and not YEAR.fullmatch(m.group(0).strip()) else m.group(0), plain)


def verify_rewrite(original: str, rewritten: str) -> dict:
    """La IA solo puede cambiar la redacción: mismas cifras (ni una más ni una menos), sin vocabulario causal, sin enlaces, longitud acotada."""
    probs: list[str] = []
    if not isinstance(rewritten, str) or not rewritten.strip():
        return {"ok": False, "problemas": ["respuesta vacía"], "texto": original}
    o_plain, r_plain = original.replace("**", ""), rewritten.replace("**", "")
    on, rn = _nums(o_plain), _nums(r_plain)
    missing = sorted(on - rn)
    extra = sorted(x for x in rn - on if not YEAR.fullmatch(x))
    if missing:
        probs.append("falta(n) la(s) cifra(s): " + ", ".join(missing[:4]))
    if extra:
        probs.append("cifra(s) nueva(s) no respaldada(s): " + ", ".join(extra[:4]))
    if any(c in r_plain.lower() for c in CAUSAL):
        probs.append("vocabulario causal")
    if re.search(r"https?://|www\.|\[[^\]]+\]\([^)]+\)", r_plain):
        probs.append("contiene enlaces")
    if len(r_plain) > MAX_GROWTH * max(len(o_plain), 40):
        probs.append("demasiado largo")
    return {"ok": not probs, "problemas": probs, "texto": _bold_numbers(rewritten) if not probs else original}


def check_rewrites(run_id: str, items: list[dict], model: str = "") -> list[dict]:
    """items: [{original, rewritten}] -> veredictos. Deja constancia de lo enviado y lo recibido (ia_log.json, se publica con el reporte)."""
    d = _dir(run_id)
    out = [verify_rewrite(str(i.get("original", "")), i.get("rewritten")) for i in items[:60]]
    log = d / "ia_log.json"
    prev = json.loads(log.read_text(encoding="utf-8")) if log.exists() else []
    from datetime import datetime, timezone
    prev.append({"fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"), "proveedor": "Cohere", "modelo": model[:80],
                 "enviado": [str(i.get("original", "")) for i in items[:60]],
                 "recibido": [{"texto": str(i.get("rewritten", ""))[:2000], "aceptado": o["ok"], "problemas": o["problemas"]} for i, o in zip(items, out)]})
    log.write_text(json.dumps(prev, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def _copy_ia_log(run_id: str) -> None:
    src = _dir(run_id) / "ia_log.json"
    if src.exists() and (_dir(run_id) / "out").is_dir():
        shutil.copy(src, _dir(run_id) / "out" / "ia_log.json")


# ------------------------------------------------------------------ descubrimiento único con IA (la IA propone; el usuario valida)
def _facts(run_id: str):
    st = _load(run_id)
    res = _run_engine(run_id, st)
    if not res.can_generate:
        raise ServiceError("Hay hallazgos bloqueantes: corrígelos antes de pedir un descubrimiento.", 409)
    per = period_of(st)
    if st["unit"] == "aetops":
        facts = aetops_facts(res, per, attainment(res, _targets(st)))
    else:
        facts = glp1_facts(res.blocks, res.funnel, per, getattr(res, "extras", None))
    if HISTORY_DB.exists():                           # el «patrón» entre meses: tendencias del historial (si hay suficientes periodos)
        con = hist.connect(HISTORY_DB)
        try:
            facts += trend_facts(trends.trends_for(con, per.unit, per.periodicity))
        finally:
            con.close()
    return st, facts


def discovery_facts(run_id: str) -> dict:
    """La hoja de hechos que se enviaría a la IA (se muestra al usuario antes de enviarla)."""
    _st, facts = _facts(run_id)
    return {"hechos": [f.to_dict() for f in facts], "temas": sorted({f.tema for f in facts})}


def check_discovery(run_id: str, payload: dict, model: str = "") -> dict:
    _st, facts = _facts(run_id)
    out = verify_discovery(facts, payload)
    log = _dir(run_id) / "ia_log.json"
    prev = json.loads(log.read_text(encoding="utf-8")) if log.exists() else []
    from datetime import datetime, timezone
    prev.append({"fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"), "proveedor": "Cohere", "modelo": model[:80], "modo": "descubrimiento",
                 "enviado": [f.id + ": " + f.texto for f in facts], "recibido": payload if isinstance(payload, dict) else str(payload)[:2000],
                 "aceptado": out["ok"], "problemas": out["problemas"]})
    log.write_text(json.dumps(prev, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def set_discovery(run_id: str, body: dict | None) -> dict:
    """Guarda la hoja que el usuario validó (o la quita). Se vuelve a verificar aquí: la interfaz no puede saltarse la regla."""
    st = _load(run_id)
    if not body or not body.get("items"):
        st["discovery"] = None
        _save(run_id, st)
        return public(st)
    _st, facts = _facts(run_id)
    byid = {f.id: f for f in facts}
    payload = {"titulo": body.get("titulo", ""), "titular": body.get("titular") or {},
               "viñetas": [{"seccion": i.get("seccion", ""), "texto": i.get("texto", ""), "hechos": i.get("hechos", []), "validar": i.get("validar", "")} for i in body["items"]]}
    chk = verify_discovery(facts, payload, strict=False)
    if not chk["ok"]:
        raise ServiceError("El descubrimiento no pasa la verificación: " + "; ".join(chk["problemas"] + [p for b in chk["viñetas"] for p in b["problemas"]])[:300], 400)
    cited: list[str] = []
    for i in list(chk["titular"]["hechos"]) + [h for b in chk["viñetas"] for h in b["hechos"]]:
        if i in byid and i not in cited:
            cited.append(i)
    st["discovery"] = {"titulo": chk["titulo"], "angulo": chk["angulo"],
                       "titular": {"texto": chk["titular"]["texto"], "hechos": chk["titular"]["hechos"]} if chk["titular"]["texto"] else None,
                       "items": [{"seccion": b["seccion"], "tipo": b["tipo"], "texto": b["texto"], "validar": b["validar"], "hechos": b["hechos"]} for b in chk["viñetas"]],
                       "evidencia": [{"id": i, "texto": byid[i].texto} for i in cited]}
    _save(run_id, st)
    return public(st)
