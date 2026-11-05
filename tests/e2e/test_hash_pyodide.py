"""`hash_resultado` dentro de Pyodide = el de CPython (spec Fase 3A §6.3; 3A-2).

Calcula el hash de los 4 escenarios de la línea base en Pyodide (Node) con el `app.zip` que arma `tools/build_site.py` —el mismo que
publica GitHub Pages— y lo compara con los valores congelados en `tests/regression/hash_resultado.json`. Es una ejecución REAL de Pyodide
(WebAssembly); nunca se simula con CPython.

Requisitos:
  * `REPORT_PYODIDE_WORK`: carpeta con `node_modules/pyodide` (`npm install pyodide@0.27.7`; solo el núcleo, sin CDN ni paquetes extra). Si
    la carpeta no tiene `sp/`, se prepara sola con los paquetes de Python puro que el motor importa (openpyxl, et_xmlfile, yaml) copiados del
    intérprete en uso: no se descarga ni se instala nada más.
  * Node.js (>= 18).
  * El `app.zip` se arma con `tools/build_site.py`; los wheels del sitio no intervienen, así que se usan archivos de relleno (como en
    `tests/unit/test_build_site.py`) y no se descarga nada de PyPI.

Si falta algún requisito la prueba se OMITE con el motivo, salvo que `REPORT_PYODIDE_REQUIRED=1` (lo fija CI): entonces FALLA, para que CI
no pueda omitirla en silencio.
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = Path(__file__).with_name("hash_pyodide.mjs")
PURE_PYTHON = ("openpyxl", "et_xmlfile", "yaml")           # lo único que importa el motor y no trae Pyodide en su núcleo


def _sin_requisito(motivo: str):
    if os.environ.get("REPORT_PYODIDE_REQUIRED") == "1":
        pytest.fail(f"Requisito de la verificación en Pyodide no cumplido (REPORT_PYODIDE_REQUIRED=1): {motivo}")
    pytest.skip(f"OMITIDA (no ejecutada): {motivo}")


def _preparar_sp(destino: Path) -> Path:
    destino.mkdir(parents=True, exist_ok=True)
    for paquete in PURE_PYTHON:
        spec = importlib.util.find_spec(paquete)
        if spec is None or not spec.submodule_search_locations:
            _sin_requisito(f"el paquete {paquete} no está instalado en este intérprete")
        shutil.copytree(list(spec.submodule_search_locations)[0], destino / paquete,
                        ignore=shutil.ignore_patterns("*.so", "*.pyd", "__pycache__", "*.pyc"), dirs_exist_ok=True)
    return destino


def test_el_hash_en_pyodide_coincide_con_el_de_cpython(tmp_path):
    work = os.environ.get("REPORT_PYODIDE_WORK")
    if not work or not (Path(work) / "node_modules" / "pyodide").exists():
        _sin_requisito("REPORT_PYODIDE_WORK no apunta a una carpeta con node_modules/pyodide")
    if not shutil.which("node"):
        _sin_requisito("Node.js no está instalado")
    work = Path(work)
    if not (work / "sp").exists():
        trabajo = tmp_path / "trabajo"
        trabajo.mkdir()
        (trabajo / "node_modules").symlink_to(work / "node_modules", target_is_directory=True)
        _preparar_sp(trabajo / "sp")
        work = trabajo
    site = tmp_path / "sitio"
    wheels = Path(os.environ["REPORT_WHEELS_DIR"]) if os.environ.get("REPORT_WHEELS_DIR") else tmp_path / "wheels"
    if not os.environ.get("REPORT_WHEELS_DIR"):
        wheels.mkdir()
        for n in ("python_pptx-1.0.2-py3-none-any.whl", "XlsxWriter-3.3.1-py3-none-any.whl", "openpyxl-3.1.5-py2.py3-none-any.whl", "et_xmlfile-2.0.0-py3-none-any.whl"):
            (wheels / n).write_bytes(b"x")
    subprocess.run([sys.executable, str(ROOT / "tools" / "build_site.py"), "--out", str(site), "--wheels", str(wheels)], check=True, cwd=ROOT, capture_output=True)
    salida = tmp_path / "pyodide.json"
    casos = _casos_comparacion()
    entrada = tmp_path / "comparaciones.json"
    entrada.write_text(json.dumps(casos), encoding="utf-8")
    r = subprocess.run(["node", "--experimental-default-type=module", str(SCRIPT), str(work), str(site / "app.zip"), str(salida), str(entrada)],
                       capture_output=True, text=True, timeout=900)
    assert r.returncode == 0 and salida.exists(), (r.stdout[-500:], r.stderr[-1500:])
    en_pyodide = json.loads(salida.read_text(encoding="utf-8"))
    esperado = json.loads((ROOT / "tests/regression/hash_resultado.json").read_text(encoding="utf-8"))["escenarios"]
    assert en_pyodide["plataforma"] == "emscripten"                 # Pyodide de verdad, no CPython
    assert en_pyodide["escenarios"] == esperado
    # y la canonicalización de la narrativa (negritas, NFC/NFD, no visibles, editados) da lo mismo que en CPython
    import unicodedata
    from backend.app import provenance as pv
    from backend.app.narrative.writer import Para
    muestra = {"conclusiones": [Para("Ventas **+26%** y piezas +16%, año 2026.", "hecho"),
                                Para(unicodedata.normalize("NFD", "Pacientes: ñandú café."), "hecho", edited=True),
                                Para("Nota de calidad solo para narrative.json", "calidad", visible=False)],
               "recomendaciones": [Para("1. [MEDIA] Proteger **AE-A**.", "recomendacion")]}
    assert en_pyodide["narrativa_muestra"] == pv.sha256_hex(pv.serializar({"narrativa": pv._narrativa(muestra)}))

    # Fase 3A-4: `provenance.comparar` es pura; dentro de Pyodide clasifica igual que en CPython (mismos bytes de evidencia serializada)
    from backend.app import provenance as pv2
    for nombre, c in casos.items():
        esperado_c = pv2.comparar(verificacion=c["verificacion"], registrado=c["registrado"], actual=c["actual"], fuentes_aportadas=c["fuentes"],
                                  regeneracion=c["regeneracion"])
        assert en_pyodide["comparaciones"][nombre] == pv2.sha256_hex(pv2.serializar_comparacion(esperado_c)), nombre
    assert {pv2.comparar(verificacion=c["verificacion"], registrado=c["registrado"], actual=c["actual"], fuentes_aportadas=c["fuentes"],
                         regeneracion=c["regeneracion"])["estado"] for c in casos.values()} == {"exacta", "parcial", "no_reproducible", "no_evaluada"}


def _casos_comparacion() -> dict:
    """Casos sintéticos (sin I/O) que cubren los cuatro estados de `comparar`."""
    import copy
    from tests.proc_util import manifiesto_valido
    m = manifiesto_valido()
    h = m["hash_resultado"]["valor"]
    verif = {"run_id": 1, "registro": {"estado": "presente", "detalle": [], "esquema": "procedencia/1", "manifiesto_sha256": "c" * 64,
                                      "hash_resultado": h, "codigos": []}, "copia": {"estado": "integra", "detalle": []}, "error_de_generacion": None,
             "integridad": "verificada"}
    actual = {k: copy.deepcopy(m[k]) for k in ("version_codigo", "version_motor", "version_definiciones", "version_reglas", "version_plantillas",
                                                 "configuracion", "entorno")}
    fuentes = [{"nombre": "input.xlsx", "sha256": m["archivos_fuente"][0]["sha256"]}]
    base = {"verificacion": verif, "registrado": m, "actual": actual, "fuentes": fuentes, "regeneracion": {"hash_resultado": h}}
    distinto = copy.deepcopy(base)
    distinto["actual"]["version_motor"] = {"engine": "2.0.0"}
    legado = copy.deepcopy(base)
    legado["verificacion"]["registro"]["estado"] = "ausente"
    legado["verificacion"]["copia"]["estado"] = "ausente"
    legado["registrado"] = None
    sin_regen = copy.deepcopy(base)
    sin_regen["regeneracion"] = None
    return {"exacta": base, "parcial": distinto, "no_reproducible": legado, "no_evaluada": sin_regen}
