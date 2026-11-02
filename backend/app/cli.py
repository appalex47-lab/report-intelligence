"""python -m backend.app.cli <libro.xlsx> [--unidad aetops|glp1] [--perfil mensual|trimestral] [--periodo AAAA-N]
                           [--plantilla plantilla.pptx --salida carpeta/]   (genera PPTX+PDF+QA)
                           [--historial historial.sqlite] [--contexto "texto" ...]  (historial inmutable; contexto del periodo)

--periodo: año y mes (mensual) o trimestre (trimestral); ej. 2026-9 o 2026-3.
Sin --periodo no se valida contra el periodo esperado.
"""
from __future__ import annotations

import sys

from .models import Period
from pathlib import Path

from .pipeline import run_aetops, run_glp1


def _f(v, pct=False):
    if v.v is None:
        return "—"
    return f"{float(v.v) * 100:+.1f}%" if pct else f"{float(v.v):,.2f}"


def _glp1(path, prof, per):
    if per is not None:
        per = Period("GLP1", per.periodicity, per.year, per.index)
    res = run_glp1(path, prof, per)
    for name, b in res.blocks.items():
        if b.role == "prior":
            continue
        first = b.rows[0] if b.rows else None
        key = {"traffic": "visitas", "money": "monto", "negados": "monto_negado"}.get(b.basis, "")
        extra = ""
        if first and key in first.values:
            extra = f"  1.ª fila: {first.key} {key}={_f(first.values[key])} share={_f(first.share, True) if first.share else '—'}"
        print(f"{name:<28} {len(b.rows):>3} filas ({b.origin}){extra}")
    if res.funnel:
        print("embudo: " + " · ".join(f"{r.key}={_f(r.values['conteo'])}" for r in res.funnel.rows))
    print("\n-- Hallazgos")
    for f in res.findings:
        print(f"  [{f.severity.upper():5}] {f.id}: {f.message} ({f.evidence})")
    print(f"\nPuede generar: {res.can_generate}")
    return 0 if res.can_generate else 1


def main(argv: list[str]) -> int:
    args = argv[1:]
    if not args or args[0].startswith("-"):
        print(__doc__)
        return 2
    path, prof, per = args[0], "mensual", None
    if "--perfil" in args:
        prof = args[args.index("--perfil") + 1]
    if "--periodo" in args:
        y, i = args[args.index("--periodo") + 1].split("-")
        per = Period("AETOPS", prof, int(y), int(i))
    if "--unidad" in args and args[args.index("--unidad") + 1].lower() == "glp1":
        return _glp1(path, prof, per)
    res = run_aetops(path, prof, per)
    for key, t in res.tables.items():
        print(f"\n== {key} ({t.comparison})")
        for g in t.groups:
            c = g.current.values
            print(f"  {g.name[:24]:<24} {g.previous.label}->{g.current.label}  monto={_f(c['monto'])} "
                  f"Δ={_f(g.pct['monto'], True)} ticket={_f(c['ticket'])} share={_f(c['share'], True)}")
    for key, pt in res.products.items():
        print(f"\n== {key} ({len(pt.rows)} filas)")
        for r in pt.rows[:3]:
            print(f"  {r.producto[:30]:<30} actual={_f(r.actual)} ant={_f(r.anterior)} delta={_f(r.delta)} [{r.delta.status}]")
    for key, nt in res.negados.items():
        print(f"\n== {key} (periodo hoja: '{nt.label or '—'}') total={_f(nt.total)}")
        for r in nt.rows[:3]:
            print(f"  {r.name[:30]:<30} monto={_f(r.monto)} share={_f(r.share, True)}")
    print("\n-- Hallazgos")
    for f in res.findings:
        print(f"  [{f.severity.upper():5}] {f.id}: {f.message} ({f.evidence})")
    print(f"\nPuede generar: {res.can_generate}")
    if "--plantilla" in args:
        return _build(res, prof, per, args)
    return 0 if res.can_generate else 1


def _build(res, prof, per, args):
    from .build import ReportBlocked, build_aetops
    if per is None or "--salida" not in args:
        print("Para generar: --perfil mensual|trimestral --periodo AAAA-N --plantilla X.pptx --salida carpeta/")
        return 2
    try:
        ctx = [args[i + 1] for i, a in enumerate(args) if a == "--contexto" and i + 1 < len(args)]
        db = Path(args[args.index("--historial") + 1]) if "--historial" in args else None
        b = build_aetops(res, per, Path(args[args.index("--plantilla") + 1]), Path(args[args.index("--salida") + 1]),
                         context=ctx or None, history_db=db, sources=[Path(args[0])])
    except ReportBlocked as e:
        print(f"\nNO SE GENERA: hallazgos bloqueantes sin resolver ({e}).")
        return 1
    print(f"\nPPTX: {b.pptx}\nPDF:  {b.pdf}\nQA {'APROBADO' if b.qa.passed else 'RECHAZADO'}; "
          f"descarga {'habilitada' if b.downloadable else 'BLOQUEADA'}")
    for i in b.qa.issues:
        if i.severity != "info" or i.id in ("FILL_NOTE", "LABEL_CROSSED_FIXED"):
            print(f"  [{i.severity.upper():5}] {i.id}" + (f" (diap. {i.slide})" if i.slide else "") + f": {i.message}")
    return 0 if b.downloadable else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
