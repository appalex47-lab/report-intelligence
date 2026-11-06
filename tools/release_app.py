"""Fase 3A-5 · prepara y VERIFICA la release `app-vX.Y.Z` de la aplicación (docs/fase3a/IMPLEMENTACION_3A5_RELEASES.md).

Lo usa `.github/workflows/release.yml`; vive aparte para poder probarse sin GitHub. Solo biblioteca estándar. NO publica nada, no ejecuta git
y no llama a GitHub: recibe las respuestas de la API ya descargadas (archivos JSON) y decide. Regla general: **ante cualquier duda, falla**
(una respuesta incompleta, un campo ausente o un error de consulta nunca se interpretan como «todo bien»).

Cadena que se verifica:  versión → etiqueta → commit → build → artefacto → SHA-256

* `preparar`            valida el `app.zip` (íntegro, sin rutas peligrosas, compilado de ESE commit con árbol limpio, `APP_VERSION` igual) y
                        escribe `app.zip`, `app.zip.sha256` y `NOTAS.md`.
* `verificar-ci`        el commit EXACTO pasó los controles: la ejecución de `tests.yml` de ese SHA terminó en success y ninguna otra falló,
                        sigue pendiente o fue cancelada.
* `etiqueta-libre`      la etiqueta no existe ni como referencia ni como release (borradores incluidos): una versión no se reutiliza.
* `verificar-carpeta`   la carpeta de la release (la que bajó el job de publicación) es la que construyó el job de construcción.
* `verificar-release`   la release (borrador o publicada) tiene exactamente los dos assets, descargados con el SHA-256 declarado, y —si está
                        publicada— la etiqueta (ligera o anotada) apunta al commit exacto del que se compiló el zip.

Uso:  python tools/release_app.py preparar --zip _site/app.zip --commit <sha 40 hex> --out _release
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import subprocess
import sys
import time
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
VERSION_PY = "backend/app/version.py"
BUILD_INFO = "backend/app/_build_info.json"
BUILD_INFO_ESQUEMA = "build_info/1"
PREFIJO_ETIQUETA = "app-v"
ASSET_ZIP, ASSET_SHA, ASSET_NOTAS = "app.zip", "app.zip.sha256", "NOTAS.md"
ASSETS_ESPERADOS = frozenset({ASSET_ZIP, ASSET_SHA})
SEMVER = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)")             # se usa con fullmatch: `$` aceptaría un salto de línea final
_APP_VERSION = re.compile(r'^APP_VERSION\s*=\s*"([^"]*)"', re.M)
_SHA_COMMIT = re.compile(r"[0-9a-f]{40}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_LINEA_SHA = re.compile(r"([0-9a-f]{64})  (app\.zip)\n?")
MAX_ZIP = 200 * 1024 * 1024                         # un app.zip real pesa unos MB: más de esto no es el artefacto esperado
MAX_DESCOMPRIMIDO = 600 * 1024 * 1024               # suma de tamaños descomprimidos (protección contra «zip bombs»)
MAX_ENTRADAS = 5000
MAX_VERSION_PY = 1_000_000
MAX_JSON = 5_000_000                                # respuestas de la API: más que esto no es una respuesta esperable

RUTA_TESTS = ".github/workflows/tests.yml"          # CI requerido para publicar (decisión T-11: la spec no lista los checks obligatorios)
RUTA_RELEASE = ".github/workflows/release.yml"      # el propio workflow de release se excluye de la comprobación del CI
CONCLUSIONES_ACEPTABLES = frozenset({"success", "skipped", "neutral"})
# Espera por consistencia eventual de GitHub (listado de releases, etiqueta recién creada): espera progresiva con tope y límite TOTAL.
# 2 + 4 + 8 + 16 + 16 + 16 + 16 = 78 s ≤ 90 s: nunca más de 90 s de espera acumulada, y no más de 8 consultas.
ESPERA_INICIAL, ESPERA_FACTOR, ESPERA_MAXIMA, ESPERA_LIMITE = 2.0, 2.0, 16.0, 90.0
_REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
_URL_BORRADOR = re.compile(r"https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/releases/tag/untagged-[0-9a-f]{8,64}")


class ErrorRelease(Exception):
    """El artefacto o los datos no permiten preparar/verificar la release (el mensaje dice qué)."""


# ------------------------------------------------------------------------------------------------------------------- versión y etiqueta
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


def _exigir_commit(commit) -> str:
    if not isinstance(commit, str) or not _SHA_COMMIT.fullmatch(commit):
        raise ErrorRelease(f"el commit debe ser un SHA de 40 caracteres hexadecimales en minúsculas: {commit!r}")
    return commit


def sha256_archivo(ruta: Path) -> str:
    h = hashlib.sha256()
    with Path(ruta).open("rb") as fh:
        for bloque in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


# ------------------------------------------------------------------------------------------------------------------- el zip
def _revisar_entradas(z: zipfile.ZipFile) -> None:
    """Rutas peligrosas, duplicados, enlaces simbólicos y tamaños desmesurados."""
    infos = z.infolist()
    if len(infos) > MAX_ENTRADAS:
        raise ErrorRelease(f"el zip tiene demasiadas entradas ({len(infos)})")
    vistos, total = set(), 0
    for i in infos:
        n = i.filename
        if not n or "\x00" in n or "\\" in n or n.startswith("/") or re.match(r"^[A-Za-z]:", n):
            raise ErrorRelease(f"entrada con ruta no permitida: {n!r}")
        partes = PurePosixPath(n).parts
        if ".." in partes or any(p in ("", ".") for p in n.rstrip("/").split("/")):
            raise ErrorRelease(f"entrada con ruta no permitida: {n!r}")
        if n in vistos:
            raise ErrorRelease(f"entrada duplicada en el zip: {n!r}")
        vistos.add(n)
        modo = (i.external_attr >> 16) & 0xFFFF
        if stat.S_ISLNK(modo):
            raise ErrorRelease(f"el zip contiene un enlace simbólico: {n!r}")
        total += i.file_size
        if total > MAX_DESCOMPRIMIDO:
            raise ErrorRelease("el contenido descomprimido excede el tamaño esperado")


def validar_zip(ruta_zip: Path, version: str, commit: str) -> None:
    """Falla (`ErrorRelease`) salvo que el zip sea íntegro y seguro, esté compilado de `commit` con el árbol limpio y empaquete `APP_VERSION == version`."""
    _exigir_commit(commit)
    ruta_zip = Path(ruta_zip)
    if not ruta_zip.is_file():
        raise ErrorRelease(f"no existe el artefacto {ruta_zip.name}")
    if ruta_zip.stat().st_size > MAX_ZIP:
        raise ErrorRelease("el artefacto excede el tamaño esperado")
    try:
        with zipfile.ZipFile(ruta_zip) as z:
            _revisar_entradas(z)
            if z.testzip() is not None:
                raise ErrorRelease("el zip está dañado (falla la comprobación de integridad)")
            nombres = set(z.namelist())
            for necesario in (BUILD_INFO, VERSION_PY):
                if necesario not in nombres:
                    raise ErrorRelease(f"el zip no contiene {necesario}")
            if z.getinfo(BUILD_INFO).file_size > 10_000 or z.getinfo(VERSION_PY).file_size > MAX_VERSION_PY:
                raise ErrorRelease("un archivo de identificación del zip excede el tamaño esperado")
            if z.getinfo(BUILD_INFO).file_size == 0 or z.getinfo(VERSION_PY).file_size == 0:
                raise ErrorRelease("un archivo de identificación del zip está vacío")
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


def _notas(version: str, tag: str, commit: str, sha: str) -> str:
    return (f"Aplicación `{version}` (etiqueta `{tag}`)\n\n- Commit: `{commit}`\n- SHA-256 de `{ASSET_ZIP}`: `{sha}`\n\n"
            f"`{ASSET_ZIP}` es el paquete que publica GitHub Pages para ese commit. Verificación: `sha256sum -c {ASSET_SHA}`.\n"
            "Los reportes cuyo manifiesto de procedencia registre este commit se pueden regenerar con este código.\n")


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
    (destino / ASSET_NOTAS).write_text(_notas(version, tag, commit, sha), encoding="utf-8")
    return {"etiqueta": tag, "version": version, "sha256": sha, "commit": commit}


def verificar_carpeta(carpeta: Path, version: str, commit: str, sha_esperado: str, tag_esperada: str | None = None) -> None:
    """La carpeta de la release es EXACTAMENTE la que preparó el job de construcción: mismo SHA-256 del zip, `app.zip.sha256` y `NOTAS.md`
    coherentes, y el zip sigue validando contra `commit`. Falla si falta, sobra o difiere algo."""
    _exigir_commit(commit)
    tag = etiqueta(version)
    if tag_esperada is not None and tag_esperada != tag:
        raise ErrorRelease(f"la etiqueta esperada {tag_esperada!r} no corresponde a la versión {version} ({tag})")
    if not isinstance(sha_esperado, str) or not _SHA256.fullmatch(sha_esperado):
        raise ErrorRelease("el SHA-256 esperado no es válido")
    carpeta = Path(carpeta)
    if not carpeta.is_dir():
        raise ErrorRelease("no existe la carpeta de la release")
    if {p.name for p in carpeta.iterdir()} != {ASSET_ZIP, ASSET_SHA, ASSET_NOTAS}:
        raise ErrorRelease("la carpeta de la release debe contener exactamente app.zip, app.zip.sha256 y NOTAS.md")
    real = sha256_archivo(carpeta / ASSET_ZIP)
    if real != sha_esperado:
        raise ErrorRelease("el app.zip recibido no es el que construyó el job de construcción (SHA-256 distinto)")
    _comprobar_linea_sha(carpeta / ASSET_SHA, real)
    if (carpeta / ASSET_NOTAS).read_text(encoding="utf-8") != _notas(version, tag, commit, real):
        raise ErrorRelease("NOTAS.md no corresponde a la versión, el commit y el SHA-256 esperados")
    validar_zip(carpeta / ASSET_ZIP, version, commit)


def _comprobar_linea_sha(ruta: Path, sha_real: str) -> None:
    texto = Path(ruta).read_text(encoding="utf-8")
    m = _LINEA_SHA.fullmatch(texto)
    if m is None:
        raise ErrorRelease("app.zip.sha256 no tiene el formato «<sha256>  app.zip»")
    if m.group(1) != sha_real:
        raise ErrorRelease("el SHA-256 declarado en app.zip.sha256 no coincide con el del app.zip")


# ------------------------------------------------------------------------------------------------------------------- CI del SHA exacto
def _ruta_workflow(ruta) -> str:
    return str(ruta).split("@", 1)[0] if ruta is not None else ""


def verificar_ci(datos, commit: str, requerido: str = RUTA_TESTS, excluir=(RUTA_RELEASE,)) -> dict:
    """`datos` es la respuesta de `GET /repos/{r}/actions/runs?head_sha={commit}&per_page=100`. Exige que el commit EXACTO haya superado el CI.

    Rechaza: respuesta que no es la esperada o está incompleta/paginada, ejecuciones de otro SHA, ejecuciones pendientes, fallidas, canceladas
    o con una conclusión desconocida, y la AUSENCIA del workflow requerido (`tests.yml`, el que ejecuta unidad, regresión y Pyodide). Las
    ejecuciones del propio workflow de release (`excluir`) no cuentan. Devuelve un resumen si todo está en regla."""
    _exigir_commit(commit)
    if not isinstance(datos, dict) or not isinstance(datos.get("workflow_runs"), list) or not isinstance(datos.get("total_count"), int) \
            or isinstance(datos.get("total_count"), bool):
        raise ErrorRelease("la respuesta de la API de ejecuciones no tiene el formato esperado (se rechaza, no se interpreta como válida)")
    runs = datos["workflow_runs"]
    if datos["total_count"] != len(runs) or len(runs) >= 100:
        raise ErrorRelease("la respuesta de la API de ejecuciones está incompleta o paginada: no se puede afirmar que el CI esté en verde")
    excluidas = {_ruta_workflow(x) for x in excluir}
    ok_requerido, vistas = 0, []
    for r in runs:
        if not isinstance(r, dict):
            raise ErrorRelease("una ejecución de la API no tiene el formato esperado")
        ruta = _ruta_workflow(r.get("path"))
        if r.get("head_sha") != commit:
            raise ErrorRelease(f"una ejecución corresponde a otro SHA ({r.get('head_sha')!r}), no a {commit}")
        if ruta in excluidas:
            continue
        estado, conclusion = r.get("status"), r.get("conclusion")
        nombre = f"{ruta or '?'} (#{r.get('run_number')})"
        if estado != "completed":
            raise ErrorRelease(f"el CI sigue pendiente: {nombre} está en estado {estado!r}")
        if conclusion not in CONCLUSIONES_ACEPTABLES:
            raise ErrorRelease(f"el CI no está en verde: {nombre} terminó con {conclusion!r}")
        vistas.append(nombre)
        if ruta == _ruta_workflow(requerido) and conclusion == "success":
            ok_requerido += 1
    if ok_requerido == 0:
        raise ErrorRelease(f"no hay una ejecución de {requerido} en success para el SHA {commit}: el commit no ha superado el CI requerido")
    return {"commit": commit, "ejecuciones_revisadas": vistas, "requerido": requerido}


# ------------------------------------------------------------------------------------------------------------------- etiqueta
def verificar_etiqueta_libre(refs, tags_de_releases, tag: str) -> None:
    """`refs`: respuesta de `GET /repos/{r}/git/matching-refs/tags/{tag}`; `tags_de_releases`: `tag_name` de TODAS las releases (borradores
    incluidos). Falla si la etiqueta existe como referencia o como release: una versión no se reutiliza ni se reescribe."""
    if not isinstance(tag, str) or not tag.startswith(PREFIJO_ETIQUETA):
        raise ErrorRelease(f"etiqueta no válida: {tag!r}")
    etiqueta(tag[len(PREFIJO_ETIQUETA):])
    if not isinstance(refs, list) or not all(isinstance(x, dict) for x in refs):
        raise ErrorRelease("la respuesta de matching-refs no tiene el formato esperado (se rechaza, no se interpreta como «libre»)")
    if not isinstance(tags_de_releases, list) or not all(isinstance(x, str) for x in tags_de_releases):
        raise ErrorRelease("la lista de releases no tiene el formato esperado (se rechaza, no se interpreta como «libre»)")
    if any(x.get("ref") == f"refs/tags/{tag}" for x in refs):
        raise ErrorRelease(f"la etiqueta {tag} ya existe: una versión publicada no se reutiliza (sube APP_VERSION)")
    if tag in tags_de_releases:
        raise ErrorRelease(f"ya existe una release (publicada o borrador) para {tag}: no se crea otra")


def commit_de_etiqueta(ref, tag_anotada=None, tag: str | None = None) -> str:
    """Commit al que apunta una etiqueta. `ref`: `GET /git/ref/tags/{tag}`. Etiqueta ligera: el objeto es un `commit`. Anotada: el objeto es un
    `tag` y hay que leerlo (`tag_anotada`: `GET /git/tags/{sha}`), que a su vez debe apuntar a un `commit`. Cualquier otro caso falla."""
    if not isinstance(ref, dict) or not isinstance(ref.get("object"), dict):
        raise ErrorRelease("la referencia de la etiqueta no tiene el formato esperado")
    if tag is not None and ref.get("ref") != f"refs/tags/{tag}":
        raise ErrorRelease(f"la referencia {ref.get('ref')!r} no es la de la etiqueta {tag}")
    obj = ref["object"]
    if obj.get("type") == "commit":
        return _exigir_commit(obj.get("sha"))
    if obj.get("type") == "tag":
        if not isinstance(tag_anotada, dict) or tag_anotada.get("sha") != obj.get("sha"):
            raise ErrorRelease("falta el objeto de la etiqueta anotada o no corresponde a la referencia")
        interno = tag_anotada.get("object")
        if not isinstance(interno, dict) or interno.get("type") != "commit":
            raise ErrorRelease("la etiqueta anotada no apunta directamente a un commit")
        return _exigir_commit(interno.get("sha"))
    raise ErrorRelease(f"la etiqueta apunta a un objeto de tipo {obj.get('type')!r}, no a un commit")


# ------------------------------------------------------------------------------------------------------------------- la release
def verificar_release(release, carpeta_descargas: Path, version: str, commit: str, sha_esperado: str, *, publicada: bool,
                      ref=None, tag_anotada=None) -> dict:
    """Verifica la release tal como GitHub la tiene. `release`: JSON de la release; `carpeta_descargas`: assets DESCARGADOS de GitHub.

    Siempre: estado (borrador o publicada) y nombre de etiqueta correctos; exactamente dos assets, ambos `uploaded`, con el tamaño de lo
    descargado; el `app.zip` descargado tiene el SHA-256 esperado (el que calculó el job de construcción), `app.zip.sha256` es coherente, el
    zip valida contra `commit` y las notas citan etiqueta, commit y SHA-256. Si está `publicada`: además la etiqueta existe y apunta al
    commit exacto (ligera o anotada)."""
    _exigir_commit(commit)
    tag = etiqueta(version)
    if not isinstance(sha_esperado, str) or not _SHA256.fullmatch(sha_esperado):
        raise ErrorRelease("el SHA-256 esperado no es válido")
    if not isinstance(release, dict):
        raise ErrorRelease("la release no tiene el formato esperado")
    if release.get("tag_name") != tag:
        raise ErrorRelease(f"la release es de {release.get('tag_name')!r}, no de {tag}")
    borrador_esperado = not publicada
    if release.get("draft") is not borrador_esperado:
        raise ErrorRelease("la release " + ("sigue siendo un borrador" if publicada else "ya no es un borrador"))
    if release.get("prerelease") is not False:
        raise ErrorRelease("la release no debe ser una pre-release")
    assets = release.get("assets")
    if not isinstance(assets, list) or not all(isinstance(a, dict) for a in assets):
        raise ErrorRelease("la lista de assets no tiene el formato esperado")
    nombres = [a.get("name") for a in assets]
    if len(nombres) != len(set(nombres)):
        raise ErrorRelease("hay assets con el mismo nombre")
    if set(nombres) != ASSETS_ESPERADOS:
        raise ErrorRelease(f"los assets deben ser exactamente {sorted(ASSETS_ESPERADOS)} y son {sorted(map(str, nombres))}")
    carpeta = Path(carpeta_descargas)
    for a in assets:
        if a.get("state") != "uploaded":
            raise ErrorRelease(f"el asset {a.get('name')} no terminó de subirse (estado {a.get('state')!r})")
        archivo = carpeta / a["name"]
        if not archivo.is_file():
            raise ErrorRelease(f"no se descargó el asset {a['name']}")
        if a.get("size") != archivo.stat().st_size:
            raise ErrorRelease(f"el tamaño descargado de {a['name']} no coincide con el que declara GitHub")
    if {p.name for p in carpeta.iterdir()} != ASSETS_ESPERADOS:
        raise ErrorRelease("la carpeta de descargas contiene archivos que no son assets de la release")
    real = sha256_archivo(carpeta / ASSET_ZIP)
    if real != sha_esperado:
        raise ErrorRelease("el app.zip descargado de GitHub no tiene el SHA-256 que calculó el job de construcción")
    _comprobar_linea_sha(carpeta / ASSET_SHA, real)
    validar_zip(carpeta / ASSET_ZIP, version, commit)
    cuerpo = release.get("body")
    if not isinstance(cuerpo, str) or not all(x in cuerpo for x in (tag, commit, real)):
        raise ErrorRelease("las notas de la release no citan la etiqueta, el commit y el SHA-256 esperados")
    resultado = {"etiqueta": tag, "commit": commit, "sha256": real, "publicada": publicada}
    if publicada:
        apuntado = commit_de_etiqueta(ref, tag_anotada, tag)
        if apuntado != commit:
            raise ErrorRelease(f"la etiqueta {tag} apunta a {apuntado}, no al commit compilado {commit}")
        resultado["apunta_a"] = apuntado
    return resultado


# ------------------------------------------------------------------------------------------------------------------- consistencia eventual
# GitHub puede tardar unos segundos en devolver, en el LISTADO de releases, un borrador recién creado (el run 42308811022 lo consultó 1 s después y
# obtuvo «hay 0»). Se distingue entre: (a) RETRASO DE PROPAGACIÓN —el recurso aún no aparece o aún no está completo—, que se reintenta con espera
# progresiva hasta un límite, y (b) DEFECTO REAL —duplicados, otra release con la etiqueta, assets inesperados, estado equivocado—, que falla de
# inmediato sin esperar. Las funciones reciben las consultas a GitHub como argumentos, de modo que las pruebas reproducen el retraso sin red.
def esperas(inicial: float = ESPERA_INICIAL, factor: float = ESPERA_FACTOR, maxima: float = ESPERA_MAXIMA, limite: float = ESPERA_LIMITE):
    """Esperas sucesivas (progresivas, con tope por espera); la suma nunca supera `limite`."""
    total, e = 0.0, float(inicial)
    while total + min(e, maxima) <= limite:
        yield min(e, maxima)
        total += min(e, maxima)
        e *= factor


def _esperar(consulta, descripcion: str, *, dormir=None, inicial=ESPERA_INICIAL, factor=ESPERA_FACTOR, maxima=ESPERA_MAXIMA, limite=ESPERA_LIMITE):
    """`consulta()` devuelve `(listo, valor)`; si no está listo, `valor` es el motivo. Un `ErrorRelease` de `consulta` (defecto real) no se reintenta."""
    dormir = dormir or time.sleep                               # se resuelve al llamar (permite sustituirlo sin dormir de verdad)
    esperado, intentos, motivo = 0.0, 0, ""
    for pausa in esperas(inicial, factor, maxima, limite):
        intentos += 1
        listo, valor = consulta()
        if listo:
            return valor
        motivo = valor
        dormir(pausa)
        esperado += pausa
    listo, valor = consulta()                                    # última consulta tras la última espera
    intentos += 1
    if listo:
        return valor
    raise ErrorRelease(f"{descripcion} no apareció tras {intentos} consultas y {esperado:g} s de espera (límite {limite:g} s): {valor or motivo}. "
                       "No es un retraso de propagación esperable: revísese la ejecución y el estado real en GitHub")


def esperar_borrador(listar, obtener, tag: str, url: str, **espera) -> dict:
    """Espera el borrador creado por ESTA ejecución y devuelve su JSON completo, leído directamente por su identificador.

    Identidad: la `html_url` (`…/releases/tag/untagged-…`) que imprimió `gh release create`; una release distinta —aunque comparta etiqueta o nombre
    parecido— nunca se acepta. `listar()` -> lista de releases; `obtener(id)` -> JSON de la release o `None` si GitHub aún responde 404."""
    def consulta():
        releases = listar()
        if not isinstance(releases, list):
            raise ErrorRelease("el listado de releases no tiene el formato esperado")
        validas = [r for r in releases if isinstance(r, dict)]
        con_tag = [r for r in validas if r.get("tag_name") == tag]
        con_url = [r for r in validas if r.get("html_url") == url]
        if len(con_tag) > 1:
            raise ErrorRelease(f"hay {len(con_tag)} releases con la etiqueta {tag}: defecto real, no un retraso")
        if len(con_url) > 1:
            raise ErrorRelease("hay varias releases con la URL del borrador creado: defecto real, no un retraso")
        if con_tag and not con_url:
            raise ErrorRelease(f"existe una release con la etiqueta {tag} que no es el borrador creado por esta ejecución")
        if not con_url:
            return False, "el borrador todavía no aparece en el listado de GitHub"
        r = con_url[0]
        if con_tag and con_tag[0].get("id") != r.get("id"):
            raise ErrorRelease(f"la etiqueta {tag} pertenece a otra release distinta del borrador creado")
        rid = r.get("id")
        if isinstance(rid, bool) or not isinstance(rid, int) or rid <= 0:
            raise ErrorRelease("el borrador listado no tiene un identificador válido")
        if r.get("tag_name") != tag:
            return False, f"el borrador aparece con tag_name {r.get('tag_name')!r}, todavía no {tag!r}"
        d = obtener(rid)
        if d is None:
            return False, f"GitHub aún no devuelve la release {rid} al consultarla por su identificador"
        if not isinstance(d, dict) or d.get("id") != rid:
            raise ErrorRelease("la consulta por identificador devolvió otra release")
        if d.get("tag_name") != tag:
            return False, f"la release {rid} todavía no tiene la etiqueta {tag!r} (tiene {d.get('tag_name')!r})"
        if d.get("draft") is not True:
            raise ErrorRelease("la release creada no es un borrador: defecto real")
        if d.get("prerelease") is not False:
            raise ErrorRelease("la release no debe ser una pre-release")
        assets = d.get("assets")
        if not isinstance(assets, list) or not all(isinstance(a, dict) for a in assets):
            raise ErrorRelease("la lista de assets no tiene el formato esperado")
        nombres = [a.get("name") for a in assets]
        if len(nombres) != len(set(nombres)):
            raise ErrorRelease("hay assets con el mismo nombre: defecto real")
        sobran = sorted(map(str, set(nombres) - ASSETS_ESPERADOS))
        if sobran:
            raise ErrorRelease(f"assets inesperados en el borrador: {sobran}")
        faltan = sorted(ASSETS_ESPERADOS - set(nombres))
        if faltan:
            return False, f"todavía faltan assets: {faltan}"
        pendientes = sorted(str(a.get("name")) for a in assets if a.get("state") != "uploaded")
        if pendientes:
            return False, f"assets aún sin terminar de subirse: {pendientes}"
        return True, d
    return _esperar(consulta, f"El borrador de {tag}", **espera)


def esperar_publicada(obtener, obtener_ref, obtener_tag, rid: int, tag: str, **espera):
    """Tras publicar el borrador: espera a que la release (consultada por id) figure publicada y a que exista la etiqueta; devuelve
    `(release, ref, tag_anotada | None)`. `obtener_*` devuelven `None` si GitHub aún responde 404."""
    def consulta():
        d = obtener(rid)
        if d is None:
            return False, f"GitHub aún no devuelve la release {rid}"
        if not isinstance(d, dict) or d.get("id") != rid:
            raise ErrorRelease("la consulta por identificador devolvió otra release")
        if d.get("tag_name") != tag:
            raise ErrorRelease(f"la release {rid} tiene la etiqueta {d.get('tag_name')!r}, no {tag!r}")
        if d.get("draft") is not False:
            return False, "la release todavía figura como borrador"
        ref = obtener_ref(tag)
        if ref is None:
            return False, f"la etiqueta {tag} todavía no existe en GitHub"
        anotada = None
        obj = ref.get("object") if isinstance(ref, dict) else None
        if not isinstance(obj, dict):
            raise ErrorRelease("la referencia de la etiqueta no tiene el formato esperado")
        if obj.get("type") == "tag":
            anotada = obtener_tag(obj.get("sha"))
            if anotada is None:
                return False, "el objeto de la etiqueta anotada todavía no se puede leer"
        return True, (d, ref, anotada)
    return _esperar(consulta, f"La release publicada {tag}", **espera)


def _gh(args) -> str | None:
    """`gh api …` -> stdout; `None` si GitHub responde 404; cualquier otro fallo se muestra tal cual (no se oculta ningún error de GitHub)."""
    r = subprocess.run(["gh", "api", *args], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        if "HTTP 404" in (r.stderr or ""):
            return None
        raise ErrorRelease(f"gh api {' '.join(args)[:100]} falló: {(r.stderr or r.stdout).strip()[:400]}")
    if len(r.stdout) > MAX_JSON:
        raise ErrorRelease("la respuesta de GitHub excede el tamaño esperado")
    return r.stdout


def _json(texto: str | None):
    if texto is None:
        return None
    try:
        return json.loads(texto)
    except ValueError as e:
        raise ErrorRelease(f"respuesta de GitHub no válida: {str(e)[:80]}") from None


def _validar_repo(repo: str) -> str:
    if not _REPO.fullmatch(repo or ""):
        raise ErrorRelease(f"repositorio no válido: {repo!r}")
    return repo


def _escribir_json(ruta: Path, valor) -> None:
    Path(ruta).write_text(json.dumps(valor, ensure_ascii=False), encoding="utf-8")


# ------------------------------------------------------------------------------------------------------------------- entrada/salida
def _leer_json(ruta: Path):
    ruta = Path(ruta)
    if not ruta.is_file():
        raise ErrorRelease(f"no existe el archivo {ruta.name}")
    if ruta.stat().st_size > MAX_JSON:
        raise ErrorRelease(f"{ruta.name} excede el tamaño esperado")
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, ValueError) as e:
        raise ErrorRelease(f"{ruta.name} no es JSON válido: {str(e)[:80]}") from None


def _leer_objetos_json(ruta: Path) -> list:
    """Varios valores JSON concatenados (salida de `gh api --paginate --jq '.[]|select(...)'`)."""
    ruta = Path(ruta)
    if not ruta.is_file() or ruta.stat().st_size > MAX_JSON:
        raise ErrorRelease(f"no existe {ruta.name} o excede el tamaño esperado")
    texto, i, out, dec = ruta.read_text(encoding="utf-8"), 0, [], json.JSONDecoder()
    while True:
        while i < len(texto) and texto[i].isspace():
            i += 1
        if i >= len(texto):
            return out
        try:
            v, i = dec.raw_decode(texto, i)
        except ValueError as e:
            raise ErrorRelease(f"{ruta.name} no es JSON válido: {str(e)[:80]}") from None
        out.append(v)


def _imprimir(r: dict, claves) -> None:
    for k in claves:
        v = str(r[k])
        if "\n" in v or "\r" in v:                       # los valores van a $GITHUB_OUTPUT: nunca una línea extra
            raise ErrorRelease(f"el valor de {k} contiene un salto de línea")
        print(f"{k}={v}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("preparar")
    p.add_argument("--zip", type=Path, required=True)
    p.add_argument("--commit", required=True)
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("verificar-ci")
    p.add_argument("--runs", type=Path, required=True)
    p.add_argument("--commit", required=True)
    p = sub.add_parser("etiqueta-libre")
    p.add_argument("--tag", required=True)
    p.add_argument("--refs", type=Path, required=True)
    p.add_argument("--releases", type=Path, required=True, help="un tag_name por línea")
    p = sub.add_parser("verificar-carpeta")
    p.add_argument("--dir", type=Path, required=True)
    p.add_argument("--commit", required=True)
    p.add_argument("--sha256", required=True)
    p.add_argument("--tag", required=True)
    p = sub.add_parser("verificar-release")
    p.add_argument("--release", type=Path, required=True, help="JSON de la release (un solo objeto)")
    p.add_argument("--dir", type=Path, required=True, help="assets descargados")
    p.add_argument("--commit", required=True)
    p.add_argument("--sha256", required=True)
    p.add_argument("--modo", choices=("borrador", "publicada"), required=True)
    p.add_argument("--ref", type=Path)
    p.add_argument("--tag-obj", type=Path)
    p = sub.add_parser("esperar-borrador")
    p.add_argument("--repo", required=True)
    p.add_argument("--tag", required=True)
    p.add_argument("--url-file", type=Path, required=True, help="archivo con la URL que imprimió `gh release create`")
    p.add_argument("--out", type=Path, required=True, help="aquí se escribe el JSON de la release (un solo objeto)")
    p = sub.add_parser("esperar-publicada")
    p.add_argument("--repo", required=True)
    p.add_argument("--tag", required=True)
    p.add_argument("--id", type=int, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--ref-out", type=Path, required=True)
    p.add_argument("--tag-obj-out", type=Path, required=True, help="solo se crea si la etiqueta es anotada")
    a = ap.parse_args(argv)
    try:
        commit = getattr(a, "commit", "").strip().lower()      # `etiqueta-libre` no recibe commit
        if a.cmd == "preparar":
            r = preparar(a.zip, commit, a.out)
            _imprimir(r, ("etiqueta", "version", "sha256", "commit"))
        elif a.cmd == "verificar-ci":
            verificar_ci(_leer_json(a.runs), commit)
        elif a.cmd == "etiqueta-libre":
            tags = [l.strip() for l in a.releases.read_text(encoding="utf-8").splitlines() if l.strip()] if a.releases.is_file() else None
            if tags is None:
                raise ErrorRelease("no existe la lista de releases")
            verificar_etiqueta_libre(_leer_json(a.refs), tags, a.tag)
        elif a.cmd == "verificar-carpeta":
            if not a.tag.startswith(PREFIJO_ETIQUETA):
                raise ErrorRelease(f"etiqueta no válida: {a.tag!r}")
            verificar_carpeta(a.dir, a.tag[len(PREFIJO_ETIQUETA):], commit, a.sha256.strip().lower(), a.tag)
        elif a.cmd == "esperar-borrador":
            repo = _validar_repo(a.repo)
            if not a.tag.startswith(PREFIJO_ETIQUETA):
                raise ErrorRelease(f"etiqueta no válida: {a.tag!r}")
            texto = a.url_file.read_text(encoding="utf-8") if a.url_file.is_file() else ""
            url = texto.strip()
            m = _URL_BORRADOR.fullmatch(url)
            if not m or m.group(1).lower() != repo.lower() or "\n" in url:
                raise ErrorRelease(f"la URL del borrador no es la esperada de {repo}: {url[:120]!r}")

            def listar():
                texto_ = _gh(["--paginate", f"repos/{repo}/releases", "--jq", ".[]"])
                if texto_ is None:
                    raise ErrorRelease("GitHub respondió 404 al listar las releases")
                dec, i, out = json.JSONDecoder(), 0, []
                while True:
                    while i < len(texto_) and texto_[i].isspace():
                        i += 1
                    if i >= len(texto_):
                        return out
                    try:
                        v, i = dec.raw_decode(texto_, i)
                    except ValueError as e:
                        raise ErrorRelease(f"respuesta de GitHub no válida: {str(e)[:80]}") from None
                    out.append(v)
            d = esperar_borrador(listar, lambda rid: _json(_gh([f"repos/{repo}/releases/{rid}"])), a.tag, url)
            _escribir_json(a.out, d)
            print(f"borrador {d['id']} listo")
        elif a.cmd == "esperar-publicada":
            repo = _validar_repo(a.repo)
            if not a.tag.startswith(PREFIJO_ETIQUETA) or a.id <= 0:
                raise ErrorRelease("etiqueta o identificador no válidos")
            a.tag_obj_out.unlink(missing_ok=True)
            d, ref, anotada = esperar_publicada(
                lambda rid: _json(_gh([f"repos/{repo}/releases/{rid}"])),
                lambda t: _json(_gh([f"repos/{repo}/git/ref/tags/{t}"])),
                lambda sha: _json(_gh([f"repos/{repo}/git/tags/{sha}"])) if isinstance(sha, str) and _SHA_COMMIT.fullmatch(sha) else None,
                a.id, a.tag)
            _escribir_json(a.out, d)
            _escribir_json(a.ref_out, ref)
            if anotada is not None:
                _escribir_json(a.tag_obj_out, anotada)
            print(f"release {d['id']} publicada")
        else:
            objs = _leer_objetos_json(a.release)
            if len(objs) != 1:
                raise ErrorRelease(f"debe haber exactamente una release para la etiqueta y hay {len(objs)}")
            publicada = a.modo == "publicada"
            if publicada and a.ref is None:
                raise ErrorRelease("para una release publicada hace falta --ref")
            version = version_del_repositorio()
            verificar_release(objs[0], a.dir, version, commit, a.sha256.strip().lower(), publicada=publicada,
                              ref=_leer_json(a.ref) if a.ref else None, tag_anotada=_leer_json(a.tag_obj) if a.tag_obj else None)
    except ErrorRelease as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
