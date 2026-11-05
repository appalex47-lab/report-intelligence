"""Congela los archivos de la aplicación que las fases de reglas NO deben modificar (Fase 2B · no-regresión).

Registra el SHA-256 de cada archivo versionado del backend, los perfiles, el frontend, las herramientas y los workflows
de publicación que no han cambiado desde la base (`main` antes de la Fase 1 de implementación). Si una fase posterior
autorizada necesita cambiar uno, se actualiza el manifiesto de forma explícita y queda justificado.

    python tools/archivos_protegidos.py --write [--base 6e1104d] [--autorizar ruta="motivo" ...]
    python tools/archivos_protegidos.py --check

`--autorizar` registra un archivo existente que se modificó por una decisión expresa (con su motivo): sigue protegido
con su hash nuevo, de modo que cualquier cambio posterior también se detecta.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFIESTO = ROOT / "tests" / "regression" / "protegidos.json"
DIRS = ("backend/app", "profiles", "frontend", "tools", ".github/workflows", "templates/README.md", "data/ejemplos", "docker")
EXCLUIR = ("tests/", "docs/")


def _git(*a) -> str:
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def candidatos(base: str) -> list[str]:
    cambiados = set(_git("diff", "--name-only", f"{base}..HEAD").split()) | set(_git("diff", "--name-only").split()) | set(_git("ls-files", "--others", "--exclude-standard").split())
    en_base = set(_git("ls-tree", "-r", "--name-only", base).split())
    return sorted(f for f in en_base if f.startswith(DIRS) and not f.startswith(EXCLUIR) and f not in cambiados and (ROOT / f).exists())


def escribir(base: str, autorizar: dict[str, str] | None = None) -> dict:
    previos = {}
    if MANIFIESTO.exists():
        previos = json.loads(MANIFIESTO.read_text(encoding="utf-8")).get("autorizados", {})
    autorizados = {f: {"motivo": m, "sha256": sha(ROOT / f)} for f, m in {**{k: v["motivo"] for k, v in previos.items()}, **(autorizar or {})}.items()}
    datos = {"base": base, "descripcion": "Archivos sin cambios desde la base; cambiarlos exige autorización y actualizar este manifiesto",
             "archivos": {f: sha(ROOT / f) for f in candidatos(base) if f not in autorizados}, "autorizados": autorizados}
    MANIFIESTO.write_text(json.dumps(datos, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return datos


def verificar() -> list[str]:
    datos = json.loads(MANIFIESTO.read_text(encoding="utf-8"))
    dif = []
    for f, h in datos["archivos"].items():
        p = ROOT / f
        if not p.exists():
            dif.append(f"eliminado: {f}")
        elif sha(p) != h:
            dif.append(f"modificado: {f}")
    for f, d in datos.get("autorizados", {}).items():
        p = ROOT / f
        if not p.exists():
            dif.append(f"eliminado (autorizado): {f}")
        elif sha(p) != d["sha256"]:
            dif.append(f"modificado después de su autorización: {f}")
    return dif


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--write", action="store_true")
    g.add_argument("--check", action="store_true")
    ap.add_argument("--base", default="6e1104d")
    ap.add_argument("--autorizar", action="append", default=[], metavar='RUTA=MOTIVO')
    a = ap.parse_args(argv)
    if a.write:
        aut = dict(x.split("=", 1) for x in a.autorizar)
        d = escribir(a.base, aut)
        print(f"{len(d['archivos'])} archivos protegidos + {len(d['autorizados'])} modificados con autorización (base {a.base})")
        return 0
    d = verificar()
    print("\n".join(d) if d else "archivos protegidos: sin cambios")
    return 1 if d else 0


if __name__ == "__main__":
    sys.exit(main())
