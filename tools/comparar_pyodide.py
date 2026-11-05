"""Compara la salida del motor en Pyodide con la referencia de CPython (`evidencia_2b/resultados_machotes.json`).

    python tools/comparar_pyodide.py /tmp/pyo/out_pyodide.json
Devuelve 0 si los resultados de los cuatro escenarios son idénticos.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REF = Path(__file__).resolve().parents[1] / "docs/fase1/implementacion/evidencia_2b/resultados_machotes.json"


def main(argv=None) -> int:
    ruta = Path((argv or sys.argv[1:])[0])
    a, b = json.loads(REF.read_text(encoding="utf-8")), json.loads(ruta.read_text(encoding="utf-8"))
    mal = 0
    for k in a:
        igual = k in b and json.dumps(a[k]["resultados"], sort_keys=True, ensure_ascii=False) == json.dumps(b[k]["resultados"], sort_keys=True, ensure_ascii=False)
        print(f"{k}: {len(a[k]['resultados'])} resultados — {'IDÉNTICO' if igual else 'DIFERENTE'}")
        mal += 0 if igual else 1
    return 1 if mal else 0


if __name__ == "__main__":
    sys.exit(main())
