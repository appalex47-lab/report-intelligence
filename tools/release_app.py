"""Fase 3A-5 · prepara y verifica la release `app-vX.Y.Z` de la aplicación (docs/fase3a/IMPLEMENTACION_3A5_RELEASES.md).

Lo usa `.github/workflows/release.yml`; vive aparte para poder probarse sin GitHub. Solo biblioteca estándar. NO publica nada ni toca git:
valida el `app.zip` que armó `tools/build_site.py`, calcula su SHA-256 y escribe los archivos que el workflow adjunta a la release.

Reglas (spec Fase 3A §10, 3A-5): la etiqueta es `app-vX.Y.Z` con `X.Y.Z = APP_VERSION`; la release publica ese `app.zip` y su SHA-256. Para que la
etiqueta identifique de verdad el código que reproduce un reporte, el `app.zip` debe haberse compilado de ESE commit y con el árbol limpio: se
exige que `_build_info.json` (dentro del zip) tenga exactamente el SHA pedido, sin `+dirty` ni `desconocido`, y que el `APP_VERSION` empaquetado
coincida con el del repositorio. Si algo no cuadra se falla; nunca se corrige ni se inventa un valor.

Uso:  python tools/release_app.py --zip _site/app.zip --commit <sha 40 hex> --out _release
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_PY = "backend/app/version.py"
BUILD_INFO = "backend/app/_build_info.json"
BUILD_INFO_ESQUEMA = "build_info/1"
PREFIJO_ETIQUETA = "app-v"
ASSET_ZIP, ASSET_SHA, ASSET_NOTAS = "app.zip", "app.zip.sha256", "NOTAS.md"
SEMVER = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)")             # se usa con fullmatch: `$` aceptaría un salto de línea final
_APP_VERSION = re.compile(r'^APP_VERSION\s*=\s*"([^"]*)"', re.M)
_SHA_COMMIT = re.compile(r"[0-9a-f]{40}")
MAX_ZIP = 200 * 1024 * 1024                         # un app.zip real pesa unos MB: más de esto no es el artefacto esperado
MAX_VERSION_PY = 1_000_000


class ErrorRelease(Exception):
    """El artefacto o los datos no permiten preparar la release (el mensaje dice qué)."""


def leer_app_version(texto: str) -> str:
    """`APP_VERSION` de un `version.py` (sin importarlo, para poder leer también el que viaja dentro del zip)."""
    m = _APP_VERSION.search(texto)
    if m is None:
        raise ErrorRelease("no se encontró APP_VERSION en version.py")
    if not SEMVER.fullmatch(m.group(1)):
        raise ErrorRelease(f"APP_VERSION no es SemVer MAJOR.MINOR.PATCH: {m.group(1)!r}")
    return m.group(1)


def version_del_repositorio(root: Path = ROOT) -> str:
    return leer_app_version((root / VERSION_PY).read_text(encoding="utf-8"))


def etiqueta(version: str) -> str:
    """`app-vX.Y.Z`. Solo acepta SemVer estricto (sin prefijo `v`, sin ceros a la izquierda, sin sufijos)."""
    if not isinstance(version, str) or not SEMVER.fullmatch(version):
        raise ErrorRelease(f"versión no válida para una etiqueta: {version!r}")
    return f"{PREFIJO_ETIQUETA}{version}"


def sha256_archivo(ruta: Path) -> str:
    h = hashlib.sha256()
    with Path(ruta).open("rb") as fh:
        for bloque in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def validar_zip(ruta_zip: Path, version: str, commit: str) -> None:
    """Falla (`ErrorRelease`) salvo que el zip sea íntegro, esté compilado de `commit` con el árbol limpio y empaquete `APP_VERSION == version`."""
    if not isinstance(commit, str) or not _SHA_COMMIT.fullmatch(commit):
        raise ErrorRelease(f"el commit debe ser un SHA de 40 caracteres hexadecimales en minúsculas: {commit!r}")
    ruta_zip = Path(ruta_zip)
    if not ruta_zip.is_file():
        raise ErrorRelease(f"no existe el artefacto {ruta_zip.name}")
    if ruta_zip.stat().st_size > MAX_ZIP:
        raise ErrorRelease("el artefacto excede el tamaño esperado")
    try:
        with zipfile.ZipFile(ruta_zip) as z:
            if z.testzip() is not None:
                raise ErrorRelease("el zip está dañado (falla la comprobación de integridad)")
            nombres = set(z.namelist())
            for necesario in (BUILD_INFO, VERSION_PY):
                if necesario not in nombres:
                    raise ErrorRelease(f"el zip no contiene {necesario}")
            if z.getinfo(BUILD_INFO).file_size > 10_000 or z.getinfo(VERSION_PY).file_size > MAX_VERSION_PY:
                raise ErrorRelease("un archivo de identificación del zip excede el tamaño esperado")
            info_bruta, version_py = z.read(BUILD_INFO), z.read(VERSION_PY)
    except zipfile.BadZipFile as e:
        raise ErrorRelease(f"no es un zip válido: {e}") from None
    try:
        info = json.loads(info_bruta.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise ErrorRelease("_build_info.json no es JSON válido") from None
    if not isinstance(info, dict) or info.get("esquema") != BUILD_INFO_ESQUEMA:
        raise ErrorRelease(f"_build_info.json no tiene el esquema {BUILD_INFO_ESQUEMA}")
    sellado = info.get("commit")
    if sellado != commit:
        raise ErrorRelease(f"el zip está compilado de {sellado!r} y la release es de {commit!r} "
                           "(un SHA con +dirty o «desconocido» tampoco identifica un código recuperable)")
    empaquetada = leer_app_version(version_py.decode("utf-8", "replace"))
    if empaquetada != version:
        raise ErrorRelease(f"el zip empaqueta APP_VERSION {empaquetada} y la release es {version}")


def preparar(ruta_zip: Path, commit: str, destino: Path, root: Path = ROOT) -> dict:
    """Valida el zip y escribe en `destino` (carpeta nueva o vacía) `app.zip`, `app.zip.sha256` y `NOTAS.md`. Devuelve `{etiqueta, version, sha256, commit}`."""
    version = version_del_repositorio(root)
    tag = etiqueta(version)
    validar_zip(ruta_zip, version, commit)
    destino = Path(destino)
    if destino.exists() and (not destino.is_dir() or any(destino.iterdir())):
        raise ErrorRelease("la carpeta de salida debe ser nueva o estar vacía (no se sobrescribe nada)")
    destino.mkdir(parents=True, exist_ok=True)
    datos = Path(ruta_zip).read_bytes()
    sha = hashlib.sha256(datos).hexdigest()
    (destino / ASSET_ZIP).write_bytes(datos)
    if sha256_archivo(destino / ASSET_ZIP) != sha:      # la copia que se publica es la que se hasheó
        raise ErrorRelease("la copia del artefacto no coincide con el original")
    (destino / ASSET_SHA).write_text(f"{sha}  {ASSET_ZIP}\n", encoding="utf-8")
    (destino / ASSET_NOTAS).write_text(
        f"Aplicación `{version}` (etiqueta `{tag}`)\n\n- Commit: `{commit}`\n- SHA-256 de `{ASSET_ZIP}`: `{sha}`\n\n"
        f"`{ASSET_ZIP}` es el paquete que publica GitHub Pages para ese commit. Verificación: `sha256sum -c {ASSET_SHA}`.\n"
        "Los reportes cuyo manifiesto de procedencia registre este commit se pueden regenerar con este código.\n", encoding="utf-8")
    return {"etiqueta": tag, "version": version, "sha256": sha, "commit": commit}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--zip", type=Path, required=True)
    ap.add_argument("--commit", required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    try:
        r = preparar(a.zip, a.commit.strip().lower(), a.out)
    except ErrorRelease as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    for k in ("etiqueta", "version", "sha256", "commit"):
        print(f"{k}={r[k]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
