"""Captura y verifica la LÍNEA BASE de Report Intelligence (Fase 1 · P-00).

Solo LEE: ejecuta los pipelines existentes sobre los machotes sintéticos de `data/ejemplos/` y guarda una foto
canónica (JSON) de lo que el sistema produce HOY, para detectar cualquier cambio en fases posteriores.
No modifica código del motor, plantillas ni datos de ejemplo.

Dos capas:
  * engine/  -> valores del motor (Decimal exactos), hallazgos (id, severity, mensaje, evidencia) y narrativa.
                No necesita plantillas: se reproduce en CI.
  * deck/    -> huella (SHA-256) del texto y la geometría de cada diapositiva del PPTX generado, más la narrativa.
                Necesita las plantillas reales, que NO se versionan (.gitignore); solo se compara si la plantilla local tiene el mismo SHA-256.

Uso:
    python tools/capture_baseline.py --write [--dir tests/regression/base]
    python tools/capture_baseline.py --check [--dir tests/regression/base]
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import sys
import tempfile
from decimal import Decimal
from enum import Enum
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.models import Period  # noqa: E402

DATA = ROOT / "data" / "ejemplos"
TEMPLATES = ROOT / "templates"

# nombre -> (unidad, periodicidad, año, índice, libro, plantilla)
SCENARIOS = {
    "aetops_mensual_2026-09": ("AETOPS", "mensual", 2026, 9, "AETOPS_crudo_ejemplo.xlsx", "aetops-mensual"),
    "aetops_trimestral_2026-Q3": ("AETOPS", "trimestral", 2026, 3, "AETOPS_crudo_ejemplo.xlsx", "aetops-trimestral"),
    "glp1_mensual_2026-09": ("GLP1", "mensual", 2026, 9, "GLP1_crudo_ejemplo.xlsx", "glp1-mensual"),
    "glp1_trimestral_2026-Q3": ("GLP1", "trimestral", 2026, 3, "GLP1_crudo_ejemplo.xlsx", "glp1-trimestral"),
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(Path(path).read_bytes())
    return h.hexdigest()


def canon(obj, _depth=0):
    """Estructura JSON determinista: Decimal -> texto exacto, dataclass -> dict, rutas absolutas -> relativas."""
    if _depth > 40:
        return "<profundidad>"
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, Enum):
        return str(obj.value)
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: canon(getattr(obj, f.name), _depth + 1) for f in dataclasses.fields(obj)}
    if isinstance(obj, dict):
        return {str(k): canon(v, _depth + 1) for k, v in sorted(obj.items(), key=lambda kv: str(kv[0]))}
    if isinstance(obj, (list, tuple)):
        return [canon(v, _depth + 1) for v in obj]
    if isinstance(obj, (set, frozenset)):
        return sorted(canon(v, _depth + 1) for v in obj)
    if isinstance(obj, float):
        return repr(obj)
    if isinstance(obj, Path):
        return _rel(str(obj))
    if isinstance(obj, str):
        return _rel(obj)
    if obj is None or isinstance(obj, (bool, int)):
        return obj
    return f"<{type(obj).__name__}>"


def _rel(s: str) -> str:
    return s.replace(str(ROOT) + "/", "").replace(str(ROOT), ".")


def _findings(findings) -> list:
    return [{"id": f.id, "severity": f.severity, "message": _rel(f.message), "evidence": _rel(f.evidence)} for f in findings]


def _run(name: str):
    unit, per, year, idx, book, tpl = SCENARIOS[name]
    period = Period(unit, per, year, idx)
    path = DATA / book
    if unit == "AETOPS":
        from backend.app.pipeline import run_aetops_raw
        res = run_aetops_raw(path, period)
        engine = {"tables": res.tables, "products": res.products, "negados": res.negados, "extras": res.extras}
    else:
        from backend.app.pipeline import run_glp1_raw
        res = run_glp1_raw(path, period)
        engine = {"blocks": res.blocks, "funnel": res.funnel, "extras": res.extras}
    return unit, period, path, tpl, res, engine


def capture_engine(name: str) -> dict:
    unit, period, path, tpl, res, engine = _run(name)
    return {
        "escenario": name, "libro": path.name, "libro_sha256": sha256(path),
        "puede_generar": res.can_generate,
        "hallazgos": _findings(res.findings),
        "motor": canon(engine),
    }


def _slide_texts(pptx: Path) -> list:
    from pptx import Presentation
    prs = Presentation(pptx)
    out = []
    for i, slide in enumerate(prs.slides, 1):
        items = []
        for sh in slide.shapes:
            rec = {"name": sh.name, "type": str(sh.shape_type), "box": [sh.left, sh.top, sh.width, sh.height]}
            if sh.has_text_frame:
                rec["text"] = [p.text for p in sh.text_frame.paragraphs]
            if getattr(sh, "has_table", False) and sh.has_table:
                rec["table"] = [[c.text for c in r.cells] for r in sh.table.rows]
            items.append(rec)
        out.append({"slide": i, "shapes": items})
    return out


def capture_deck(name: str) -> dict | None:
    """None si la plantilla local no existe. No renderiza (sin LibreOffice) para que sea rápido y determinista."""
    unit, period, path, tpl, res, _ = _run(name)
    template = TEMPLATES / tpl / "1" / "template.pptx"
    if not template.exists():
        return None
    with tempfile.TemporaryDirectory() as td:
        if unit == "AETOPS":
            from backend.app.build import build_aetops
            b = build_aetops(res, period, template, Path(td), render=False)
        else:
            from backend.app.build import build_glp1
            b = build_glp1(res, period, template, Path(td), render=False)
        texts = _slide_texts(b.pptx)
        # Solo huellas: el texto estático de la plantilla puede traer marca/datos comerciales y no se publica.
        huellas = [{"slide": s["slide"], "n_formas": len(s["shapes"]),
                    "sha256": hashlib.sha256(json.dumps(canon(s["shapes"]), ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()}
                   for s in texts]
        narrative = {k: [{"texto": p.plain, "tipo": p.kind, "regla": p.basis} for p in ps] for k, ps in b.fill.narrative.items()}
    return {
        "escenario": name, "plantilla": f"{tpl}/1/template.pptx", "plantilla_sha256": sha256(template),
        "n_diapositivas": len(texts), "diapositivas": huellas, "narrativa": canon(narrative),
    }


def _dump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def write(base: Path, with_deck: bool = True) -> list[str]:
    (base / "engine").mkdir(parents=True, exist_ok=True)
    (base / "deck").mkdir(parents=True, exist_ok=True)
    done = []
    for name in SCENARIOS:
        (base / "engine" / f"{name}.json").write_text(_dump(capture_engine(name)), encoding="utf-8")
        done.append(f"engine/{name}.json")
        if with_deck:
            d = capture_deck(name)
            if d is not None:
                (base / "deck" / f"{name}.json").write_text(_dump(d), encoding="utf-8")
                done.append(f"deck/{name}.json")
    return done


def diff(a, b, path="") -> list[str]:
    out: list[str] = []
    if type(a) is not type(b):
        return [f"{path}: tipo {type(a).__name__} != {type(b).__name__}"]
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a:
                out.append(f"{path}/{k}: nuevo")
            elif k not in b:
                out.append(f"{path}/{k}: ausente")
            else:
                out += diff(a[k], b[k], f"{path}/{k}")
    elif isinstance(a, list):
        if len(a) != len(b):
            out.append(f"{path}: longitud {len(a)} != {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            out += diff(x, y, f"{path}[{i}]")
    elif a != b:
        out.append(f"{path}: {a!r} != {b!r}")
    return out


def check(base: Path) -> dict:
    """Compara la foto actual con la guardada. Devuelve {escenario: {'engine': [difs], 'deck': [difs]|'omitida (motivo)'}}."""
    report = {}
    for name in SCENARIOS:
        r = {}
        stored = json.loads((base / "engine" / f"{name}.json").read_text(encoding="utf-8"))
        r["engine"] = diff(stored, json.loads(_dump(capture_engine(name))))
        dpath = base / "deck" / f"{name}.json"
        if not dpath.exists():
            r["deck"] = "omitida (sin foto guardada del deck)"
        else:
            stored_d = json.loads(dpath.read_text(encoding="utf-8"))
            tpl = TEMPLATES / stored_d["plantilla"]
            if not tpl.exists():
                r["deck"] = "omitida (plantilla local no disponible)"
            elif sha256(tpl) != stored_d["plantilla_sha256"]:
                r["deck"] = "omitida (la plantilla local tiene otro SHA-256)"
            else:
                r["deck"] = diff(stored_d, json.loads(_dump(capture_deck(name))))
        report[name] = r
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--write", action="store_true", help="escribe la foto de la línea base")
    g.add_argument("--check", action="store_true", help="compara contra la foto guardada")
    ap.add_argument("--dir", default=str(ROOT / "tests" / "regression" / "base"))
    ap.add_argument("--sin-deck", action="store_true", help="no capturar el texto del PPTX")
    a = ap.parse_args(argv)
    base = Path(a.dir)
    if a.write:
        for f in write(base, with_deck=not a.sin_deck):
            print("escrito", f)
        return 0
    rep = check(base)
    bad = 0
    for name, r in rep.items():
        for layer, val in r.items():
            if isinstance(val, str):
                print(f"{name} [{layer}]: {val}")
            elif val:
                bad += len(val)
                print(f"{name} [{layer}]: {len(val)} diferencias")
                for d in val[:20]:
                    print("   ", d)
            else:
                print(f"{name} [{layer}]: idéntico")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
