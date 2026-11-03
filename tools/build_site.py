"""Construye el sitio estático para GitHub Pages (todo corre en el navegador con Pyodide; no hay servidor).

    python tools/build_site.py --out _site [--wheels carpeta]

Contenido de `_site/`:
  index.html, worker.js        pantalla de revisión + motor en un Web Worker
  app.zip                      backend/app, profiles/ y los generadores de machotes (se descomprime en el sistema virtual de Pyodide)
  wheels/                      python-pptx, XlsxWriter, openpyxl y et-xmlfile (lxml, PyYAML, Pillow y sqlite3 los trae Pyodide)
  legacy/                      la app anterior (JavaScript), por continuidad
Las plantillas PPTX NO van aquí (llevan marca): cada usuario las carga una vez y quedan en su navegador.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WHEELS = ["python-pptx==1.0.2", "XlsxWriter==3.3.1", "openpyxl==3.1.5", "et-xmlfile==2.0.0"]      # lo demás lo trae Pyodide
SKIP = {"__pycache__"}
APP_FILES = [("backend", ROOT / "backend"), ("profiles", ROOT / "profiles")]
TOOLS = ["make_machotes.py", "make_glp1_synthetic.py"]


def add_tree(z: zipfile.ZipFile, arc: str, src: Path) -> int:
    n = 0
    for p in sorted(src.rglob("*")):
        if p.is_dir() or SKIP & set(p.parts) or p.suffix in (".pyc",):
            continue
        z.write(p, f"{arc}/{p.relative_to(src).as_posix()}")
        n += 1
    return n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "_site")
    ap.add_argument("--wheels", type=Path, default=None, help="carpeta con los .whl (si no, se descargan de PyPI)")
    a = ap.parse_args()
    out = a.out
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for f in ("index.html", "worker.js"):
        shutil.copy(ROOT / "frontend" / f, out / f)
    (out / ".nojekyll").write_text("")
    with zipfile.ZipFile(out / "app.zip", "w", zipfile.ZIP_DEFLATED) as z:
        total = sum(add_tree(z, arc, src) for arc, src in APP_FILES)
        for t in TOOLS:
            z.write(ROOT / "tools" / t, f"tools/{t}")
            total += 1
    wd = out / "wheels"
    wd.mkdir()
    if a.wheels:
        for w in a.wheels.glob("*.whl"):
            shutil.copy(w, wd / w.name)
    else:
        subprocess.run([sys.executable, "-m", "pip", "download", *WHEELS, "--no-deps", "-d", str(wd), "-q"], check=True)
    names = sorted(p.name for p in wd.glob("*.whl"))
    for need in ("python_pptx", "xlsxwriter", "openpyxl", "et_xmlfile"):
        if not any(n.lower().startswith(need) for n in names):
            raise SystemExit(f"Falta el wheel de {need}.")
    (wd / "index.json").write_text(json.dumps(names))
    legacy = ROOT / "legacy"
    if legacy.exists():
        shutil.copytree(legacy, out / "legacy")
    print(f"sitio en {out}: app.zip ({total} archivos), wheels {names}")


if __name__ == "__main__":
    main()
