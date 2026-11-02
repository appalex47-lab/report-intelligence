"""python -m backend.app.cli <libro.xlsx> [--perfil mensual|trimestral] [--periodo AAAA-N]

--periodo: año y mes (mensual) o trimestre (trimestral); ej. 2026-9 o 2026-3.
Sin --periodo no se valida contra el periodo esperado.
"""
from __future__ import annotations

import sys

from .models import Period
from .pipeline import run_aetops


def _f(v, pct=False):
    if v.v is None:
        return "—"
    return f"{float(v.v) * 100:+.1f}%" if pct else f"{float(v.v):,.2f}"


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
    return 0 if res.can_generate else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
