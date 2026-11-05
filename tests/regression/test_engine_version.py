"""Acoplamiento entre la línea base de resultados del motor y `ENGINE_VERSION` (Fase 3A-1; spec Fase 3A §4.3 y §4.4).

QUÉ VERIFICA
    Que los **resultados de referencia** del motor (`tests/regression/base/engine/*.json`, 4 escenarios) y `ENGINE_VERSION` van
    juntos: si esos resultados cambian, la huella (digest) cambia y la prueba exige registrar una `ENGINE_VERSION` nueva.

QUÉ NO VERIFICA (limitación expresa)
    NO es un detector automático de cambios en el código del motor. Solo ve el efecto del código sobre esos 4 escenarios de
    referencia: un cambio de código que no altere ninguno de esos resultados pasa inadvertido, y el incremento de
    `ENGINE_VERSION` sigue siendo una decisión humana regida por la política de la spec (§4.1). La prueba solo comprueba la
    coherencia entre dos registros: *huella de la línea base* ↔ *versión declarada*.

Tres cosas distintas (no se confunden):
    1. Cambio en los resultados de referencia  -> lo detecta el digest.
    2. Cambio en el código del motor           -> NO lo detecta esta prueba (solo si altera esos resultados).
    3. Incremento de `ENGINE_VERSION`          -> decisión humana; aquí solo se exige que no haya dos huellas con la misma versión.

ALGORITMO DEL DIGEST (`RI-ENGINE-BASELINE/1`)
    digest = SHA-256 del flujo de bytes siguiente:
        b"RI-ENGINE-BASELINE/1\\n"
        y, por cada archivo `*.json` de la carpeta, en orden ascendente del nombre codificado en UTF-8:
            b"file " + <nombre> + b"\\n"
            b"len "  + <largo del contenido en bytes, en ASCII decimal> + b"\\n"
            <contenido>   (bytes del archivo, con los saltos de línea CRLF convertidos a LF)
            b"\\n"
    Precisiones (para que otra implementación independiente obtenga el mismo SHA-256):
        * Archivos incluidos: solo los archivos regulares directamente en la carpeta (sin subcarpetas, sin enlaces a carpetas)
          cuyo nombre termina exactamente en `.json` en minúsculas. `a.JSON`, `a.json.bak` y las carpetas no cuentan.
        * Nombre: el nombre base (sin ruta), codificado en UTF-8 sin normalizar. Orden: por esos bytes, de menor a mayor
          (para texto UTF-8 coincide con el orden por punto de código).
        * Largo: número de bytes del contenido YA normalizado (CRLF -> LF), en decimal ASCII, sin ceros a la izquierda ni
          espacios (`len 0`, `len 8`, `len 12`).
        * CRLF -> LF: cada secuencia `\r\n` pasa a `\n`. Un `\r` suelto no se toca.
        * Archivo vacío: se incluye como `file <nombre>\nlen 0\n` + (0 bytes) + `\n`.
        * Carpeta sin archivos: el digest es el SHA-256 del encabezado `RI-ENGINE-BASELINE/1\n` solo.
        * Orden de los bytes entregados a SHA-256: encabezado y, por archivo, `file`, `len`, contenido, `\n`, exactamente en ese orden.
    El nombre y el largo hacen la concatenación inequívoca: renombrar un archivo, mover contenido de uno a otro o cambiar el
    orden de creación no produce el mismo digest por accidente. Codificación: UTF-8 para nombres; el contenido se usa tal
    como está guardado (los snapshots ya son UTF-8).

CÓMO SE RECALCULA Y SE ACTUALIZA LA REFERENCIA
    1. Los resultados de referencia solo se regeneran de forma justificada (`tools/capture_baseline.py --write`), nunca para
       «hacer pasar» una prueba.
    2. Si el cambio es legítimo, se sube `ENGINE_VERSION` en `backend/app/version.py` según la política (§4.1).
    3. Se ejecuta `python tests/regression/test_engine_version.py --actualizar`: calcula el digest actual y agrega una entrada
       al `historial` de `engine_version.json`. Se **niega** a registrar una huella nueva con una versión ya registrada.
    `python tests/regression/test_engine_version.py` (sin opciones) imprime el digest actual.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app import version  # noqa: E402

ALGORITMO = "RI-ENGINE-BASELINE/1"
CARPETA = ROOT / "tests" / "regression" / "base" / "engine"
REGISTRO = ROOT / "tests" / "regression" / "engine_version.json"


def archivos(carpeta: Path = CARPETA) -> list[Path]:
    """Archivos regulares de la carpeta (sin entrar en subcarpetas) cuyo nombre termina exactamente en `.json` (minúsculas)."""
    return sorted((p for p in carpeta.iterdir() if p.is_file() and p.name.endswith(".json")), key=lambda p: p.name.encode("utf-8"))


def digest(carpeta: Path = CARPETA) -> str:
    h = hashlib.sha256()
    h.update(ALGORITMO.encode("ascii") + b"\n")
    for p in archivos(carpeta):
        contenido = p.read_bytes().replace(b"\r\n", b"\n")
        h.update(b"file " + p.name.encode("utf-8") + b"\n")
        h.update(b"len " + str(len(contenido)).encode("ascii") + b"\n")
        h.update(contenido + b"\n")
    return h.hexdigest()


def _tupla(v: str) -> tuple[int, int, int]:
    m = version.SEMVER.match(v)
    assert m, f"{v!r} no es MAJOR.MINOR.PATCH"
    return tuple(int(x) for x in m.groups())


def cargar(registro: Path = REGISTRO) -> dict:
    return json.loads(registro.read_text(encoding="utf-8"))


def actualizar(registro: Path = REGISTRO, carpeta: Path = CARPETA, engine_version: str | None = None) -> str:
    """Agrega la huella actual al historial. Devuelve «sin cambios» o «registrada». Se niega a repetir una versión con otra huella."""
    ev = engine_version or version.ENGINE_VERSION
    _tupla(ev)
    d = cargar(registro) if registro.exists() else {"esquema": "engine_version/1", "algoritmo": ALGORITMO, "archivos": [], "historial": []}
    actual = digest(carpeta)
    hist = d["historial"]
    if hist and hist[-1]["digest"] == actual and hist[-1]["engine_version"] == ev:
        d["archivos"] = [p.name for p in archivos(carpeta)]
        registro.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        return "sin cambios"
    if any(e["engine_version"] == ev for e in hist):
        raise SystemExit(f"ENGINE_VERSION {ev} ya está registrada con otra huella: sube la versión según la política (spec §4.1) antes de actualizar.")
    if hist and _tupla(ev) <= _tupla(hist[-1]["engine_version"]):
        raise SystemExit(f"ENGINE_VERSION {ev} no es mayor que la última registrada ({hist[-1]['engine_version']}).")
    hist.append({"engine_version": ev, "digest": actual})
    d["archivos"] = [p.name for p in archivos(carpeta)]
    registro.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return "registrada"


# ------------------------------------------------------------------------------------------------------------------- pruebas
def test_la_linea_base_del_motor_coincide_con_la_version_registrada():
    d = cargar()
    assert d["esquema"] == "engine_version/1" and d["algoritmo"] == ALGORITMO
    ultimo = d["historial"][-1]
    assert digest() == ultimo["digest"], (
        "Los resultados de referencia del motor cambiaron. Si es legítimo: justifica el cambio, sube ENGINE_VERSION en "
        "backend/app/version.py (spec Fase 3A §4.1) y ejecuta `python tests/regression/test_engine_version.py --actualizar`.")
    assert ultimo["engine_version"] == version.ENGINE_VERSION, "ENGINE_VERSION no coincide con la última versión registrada para esta línea base"


def test_el_historial_es_coherente_una_version_una_huella():
    h = cargar()["historial"]
    assert h, "el historial no puede estar vacío"
    versiones = [e["engine_version"] for e in h]
    assert len(set(versiones)) == len(versiones), "una misma ENGINE_VERSION no puede tener dos huellas"
    assert len({e["digest"] for e in h}) == len(h), "una misma huella no puede aparecer con dos versiones"
    assert [_tupla(v) for v in versiones] == sorted(_tupla(v) for v in versiones), "las versiones del historial deben ir en orden ascendente"
    assert all(len(e["digest"]) == 64 and set(e["digest"]) <= set("0123456789abcdef") for e in h)


def test_el_registro_cubre_exactamente_los_snapshots_de_la_carpeta():
    assert cargar()["archivos"] == [p.name for p in archivos()]
    assert len(archivos()) == 4


def test_la_version_declarada_es_semver_y_la_primera_formal_es_1_0_0():
    for v in (version.APP_VERSION, version.ENGINE_VERSION):
        assert version.SEMVER.match(v), v
    assert cargar()["historial"][0]["engine_version"] == "1.0.0"          # primera versión formalmente identificada (D-C)


# --- el algoritmo es inequívoco (se prueba con carpetas sintéticas, no con la línea base real) -------------------------------
def _carpeta(tmp_path: Path, nombre: str, contenidos: dict[str, bytes]) -> Path:
    c = tmp_path / nombre
    c.mkdir()
    for n, b in contenidos.items():
        (c / n).write_bytes(b)
    return c


def test_digest_coincide_con_el_flujo_documentado_calculado_a_mano(tmp_path):
    c = _carpeta(tmp_path, "c", {"b.json": b'{"x":2}', "a.json": b'{"x":1}'})
    esperado = hashlib.sha256(
        b"RI-ENGINE-BASELINE/1\n"
        b"file a.json\nlen 7\n" b'{"x":1}' b"\n"
        b"file b.json\nlen 7\n" b'{"x":2}' b"\n").hexdigest()
    assert digest(c) == esperado                                         # orden por nombre; nombre y largo incluidos


# Vectores de prueba: los mismos valores figuran en docs/fase3a/ESPECIFICACION_FASE3A_PROCEDENCIA.md §4.4 para verificar otra implementación.
VECTOR_0 = "f2bc3a6368104bf178fc96f5d47607d669288352fcc0285d7bea24ff81e71fd5"      # carpeta sin archivos
VECTOR_1 = "64f9dd728a509d6a04199e0ac758288f134e67fd706ca7211e1112cd3e3ac22a"      # a.json vacío
VECTOR_2 = "271a02dc2a208b65775a086c047dd781335919dd63d0118f927942eff1b4c045"      # b.json = {"a":1}\r\n  (CRLF normalizado)
VECTOR_3 = "62d0dea4c4da4398e56cd77ae53f7b6522f260f08b28551889d445a0e3a5c7a8"      # a.json, z.json (12 bytes), ñ.json: orden por bytes UTF-8


def test_vectores_de_prueba_del_algoritmo(tmp_path):
    assert digest(_carpeta(tmp_path, "v0", {})) == VECTOR_0 == hashlib.sha256(b"RI-ENGINE-BASELINE/1\n").hexdigest()
    assert digest(_carpeta(tmp_path, "v1", {"a.json": b""})) == VECTOR_1                       # archivo vacío: len 0
    assert digest(_carpeta(tmp_path, "v2", {"b.json": b'{"a":1}\r\n'})) == VECTOR_2            # CRLF -> LF, len 8
    assert digest(_carpeta(tmp_path, "v3", {"z.json": b"0123456789ab", "\u00f1.json": b"hi", "a.json": b"x"})) == VECTOR_3   # len 12; ñ (c3 b1) va después de z


def test_solo_cuentan_los_archivos_json_regulares_de_la_carpeta(tmp_path):
    base = _carpeta(tmp_path, "b", {"a.json": b"x"})
    ruido = _carpeta(tmp_path, "r", {"a.json": b"x", "a.JSON": b"otro", "a.json.bak": b"otro", "nota.txt": b"otro"})
    (ruido / "sub.json").mkdir()                                       # una carpeta con nombre .json no cuenta
    (ruido / "sub").mkdir()
    (ruido / "sub" / "x.json").write_bytes(b"enterrado")               # ni lo que hay dentro de subcarpetas
    assert digest(ruido) == digest(base)


def test_digest_distingue_lo_que_una_concatenacion_simple_confundiria(tmp_path):
    base = digest(_carpeta(tmp_path, "1", {"a.json": b"AB", "b.json": b"C"}))
    mover = digest(_carpeta(tmp_path, "2", {"a.json": b"A", "b.json": b"BC"}))
    renombrar = digest(_carpeta(tmp_path, "3", {"a.json": b"AB", "c.json": b"C"}))
    assert len({base, mover, renombrar}) == 3                            # mismo texto concatenado «ABC», tres huellas distintas


def test_digest_ignora_el_orden_de_creacion_y_los_saltos_de_linea_de_windows(tmp_path):
    a = digest(_carpeta(tmp_path, "x", {"a.json": b"l1\nl2\n", "b.json": b"z"}))
    b = digest(_carpeta(tmp_path, "y", {"b.json": b"z", "a.json": b"l1\r\nl2\r\n"}))
    assert a == b


def test_actualizar_exige_subir_la_version_si_cambia_la_huella(tmp_path):
    c = _carpeta(tmp_path, "c", {"a.json": b"1"})
    reg = tmp_path / "engine_version.json"
    assert actualizar(reg, c, "1.0.0") == "registrada"
    assert actualizar(reg, c, "1.0.0") == "sin cambios"                  # misma huella, misma versión
    (c / "a.json").write_bytes(b"2")                                      # cambian los resultados de referencia
    import pytest
    with pytest.raises(SystemExit):                                       # misma versión con otra huella: se niega
        actualizar(reg, c, "1.0.0")
    with pytest.raises(SystemExit):                                       # una versión menor tampoco
        actualizar(reg, c, "0.9.0")
    assert actualizar(reg, c, "1.1.0") == "registrada"
    h = cargar(reg)["historial"]
    assert [e["engine_version"] for e in h] == ["1.0.0", "1.1.0"] and h[0]["digest"] != h[1]["digest"]


if __name__ == "__main__":
    if "--actualizar" in sys.argv:
        print(actualizar())
    else:
        print(digest())
