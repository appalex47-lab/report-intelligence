"""QA visual local de un PPTX (Fase 5, spec §7.B): LibreOffice → PDF → PNG por diapositiva + informe y visor HTML.

    python tools/visual_qa.py deck.pptx --out carpeta_salida [--plantilla template.pptx] [--dpi 110]

Código de salida: 0 aprobada · 1 rechazada o con error · 2 omitida (sin LibreOffice/pdftoppm: NUNCA se reporta como aprobada).
Corre en el equipo local: el PPTX no sale de él. En GitHub Actions implicaría subirlo (usar solo datos sintéticos).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.qa import visual  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pptx")
    ap.add_argument("--out", required=True)
    ap.add_argument("--plantilla")
    ap.add_argument("--dpi", type=int, default=110)
    a = ap.parse_args(argv)
    if not Path(a.pptx).is_file():
        print(f"No existe el archivo: {a.pptx}", file=sys.stderr)
        return 1
    inf = visual.revisar(a.pptx, a.out, a.plantilla, a.dpi)
    print(json.dumps({k: inf[k] for k in ("estado", "motivo") if k in inf} | {"hallazgos": [(i["id"], i["severity"], i["slide"]) for i in inf["issues"]],
                                                                               "diapositivas": inf.get("diapositivas")}, ensure_ascii=False))
    return {"aprobada": 0, "omitida": 2}.get(inf["estado"], 1)


if __name__ == "__main__":
    sys.exit(main())
