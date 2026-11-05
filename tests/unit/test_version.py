"""Fase 3A-1 · versiones formales (APP_VERSION, ENGINE_VERSION) e identidad del commit (`backend/app/version.py`).

No cambia ningún resultado de reportes: estas pruebas solo cubren la lectura de versiones y del SHA estampado en la compilación.
"""
import json
import shutil

import pytest

from backend.app import config, version

SHA = "0123456789abcdef0123456789abcdef01234567"


def _info(tmp_path, monkeypatch, contenido=None, texto=None):
    p = tmp_path / "_build_info.json"
    if texto is not None:
        p.write_text(texto, encoding="utf-8")
    elif contenido is not None:
        p.write_text(json.dumps(contenido), encoding="utf-8")
    monkeypatch.setattr(version, "BUILD_INFO", p)
    return p


def test_las_versiones_formales_son_semver_y_arrancan_en_1_0_0():
    assert version.APP_VERSION == "1.0.0" and version.ENGINE_VERSION == "1.0.0"
    assert version.SEMVER.match(version.APP_VERSION) and version.SEMVER.match(version.ENGINE_VERSION)
    for malo in ("1.0", "01.0.0", "1.0.0-beta", "v1.0.0", "1.0.0.0", ""):
        assert not version.SEMVER.match(malo), malo


def test_con_informacion_de_compilacion_limpia(tmp_path, monkeypatch):
    _info(tmp_path, monkeypatch, {"esquema": "build_info/1", "commit": SHA})
    v = version.versiones()
    assert v["app"] == "1.0.0" and v["motor"] == "1.0.0" and v["commit"] == SHA
    assert v["compilacion"] == {"commit": SHA, "sha": SHA, "estado": "limpia"}


def test_con_arbol_modificado_se_identifica_el_commit_pero_no_se_presenta_como_limpio(tmp_path, monkeypatch):
    _info(tmp_path, monkeypatch, {"esquema": "build_info/1", "commit": SHA + "+dirty"})
    c = version.compilacion()
    assert c == {"commit": SHA + "+dirty", "sha": SHA, "estado": "dirty"}
    assert version.commit().endswith("+dirty") and c["estado"] != "limpia"


@pytest.mark.parametrize("texto", [
    None,                                                  # el archivo no existe
    "",                                                    # vacío
    "no es json",                                          # dañado
    "[]",                                                  # JSON de otro tipo
    '{"commit": 12345}',                                   # tipo equivocado
    '{"commit": "abc123"}',                                # SHA corto
    '{"commit": "' + SHA.upper() + '"}',                   # mayúsculas: formato no válido
    '{"commit": "' + SHA + '+sucio"}',                     # sufijo desconocido
    '{"esquema": "build_info/1"}',                         # sin commit
])
def test_sin_informacion_valida_el_commit_es_desconocido_y_no_hay_error(tmp_path, monkeypatch, texto):
    _info(tmp_path, monkeypatch, texto=texto)
    assert version.commit() == "desconocido"
    assert version.compilacion() == {"commit": "desconocido", "sha": None, "estado": "desconocida"}
    v = version.versiones()                                # versiones() nunca falla
    assert v["app"] == "1.0.0" and v["motor"] == "1.0.0" and v["commit"] == "desconocido"


def test_versiones_conserva_los_campos_que_ya_devolvia(tmp_path, monkeypatch):
    _info(tmp_path, monkeypatch)
    v = version.versiones()
    assert {"app", "motor", "modelo_hallazgos", "configuracion"} <= set(v)
    assert v["configuracion"] == config.versiones()
    assert v["modelo_hallazgos"] == version.MODELO_HALLAZGOS_VERSION


@pytest.mark.skipif(shutil.which("git") is None, reason="git no está disponible en el PATH")
def test_en_el_repositorio_no_hay_un_build_info_versionado():
    """`_build_info.json` solo existe dentro de app.zip: no es un archivo generado del repositorio."""
    import subprocess
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    r = subprocess.run(["git", "-C", str(root), "ls-files", "backend/app/_build_info.json"], capture_output=True, text=True)
    if r.returncode == 0:
        assert r.stdout.strip() == ""
