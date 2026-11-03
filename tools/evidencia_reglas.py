"""Ejecuta el motor de reglas sobre los machotes sintéticos y guarda los resultados (evidencia reproducible de la Fase 2B).

    python tools/evidencia_reglas.py [--salida docs/fase1/implementacion/evidencia_2b/resultados_machotes.json]

Solo lee `data/ejemplos`. La salida es determinista (sin fechas ni rutas absolutas): dos ejecuciones dan el mismo archivo.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.models import Period  # noqa: E402
from backend.app.validator import motor  # noqa: E402
from backend.app.validator.normalizar import construir_contexto  # noqa: E402

ESCENARIOS = [("GLP1", "mensual", 2026, 9, "GLP1_crudo_ejemplo.xlsx"), ("GLP1", "trimestral", 2026, 3, "GLP1_crudo_ejemplo.xlsx"),
              ("AETOPS", "mensual", 2026, 9, "AETOPS_crudo_ejemplo.xlsx"), ("AETOPS", "trimestral", 2026, 3, "AETOPS_crudo_ejemplo.xlsx")]


def generar() -> tuple[dict, dict]:
    out, tiempos = {}, {}
    for u, tipo, y, i, f in ESCENARIOS:
        p = ROOT / "data" / "ejemplos" / f
        t0 = time.time()
        ctx = construir_contexto(p, Period(u, tipo, y, i))
        t1 = time.time()
        res = motor.ejecutar(ctx)
        t2 = time.time()
        nombre = f"{u}_{tipo}_{y}-{i:02d}"
        out[nombre] = {"libro": f, "libro_sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "sintetico": True,
                       "resumen": motor.resumen(res), "resultados": [r.to_dict() for r in res]}
        tiempos[nombre] = {"lectura_s": round(t1 - t0, 2), "reglas_s": round(t2 - t1, 3)}
    return out, tiempos


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--salida", default=str(ROOT / "docs/fase1/implementacion/evidencia_2b/resultados_machotes.json"))
    a = ap.parse_args(argv)
    datos, tiempos = generar()
    Path(a.salida).parent.mkdir(parents=True, exist_ok=True)
    Path(a.salida).write_text(json.dumps(datos, ensure_ascii=False, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(json.dumps(tiempos, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
