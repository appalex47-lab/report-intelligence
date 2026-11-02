"""python -m backend.app.cli <libro.xlsx>  -> resumen legible (para revisión rápida)."""
from __future__ import annotations

import sys

from .pipeline import run_aetops_base


def _f(v, pct=False):
    if v.v is None:
        return "—"
    return f"{float(v.v) * 100:+.1f}%" if pct else f"{float(v.v):,.2f}"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    res = run_aetops_base(argv[1])
    for key, t in res.tables.items():
        print(f"\n== {key} ({t.comparison})")
        for g in t.groups:
            c = g.current.values
            print(f"  {g.name:<18} {g.previous.label}->{g.current.label}  monto={_f(c['monto'])} "
                  f"Δ={_f(g.pct['monto'], True)} ticket={_f(c['ticket'])} size_b={_f(c['size_b'])} "
                  f"share={_f(c['share'], True)}")
    print("\n-- Hallazgos")
    for f in res.findings:
        print(f"  [{f.severity.upper():5}] {f.id}: {f.message} ({f.evidence})")
    print(f"\nPuede generar: {res.can_generate}")
    return 0 if res.can_generate else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
