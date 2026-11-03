"""Fixtures sintéticas de la Fase 1: deterministas, marcadas como sintéticas y confinadas a su directorio."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

from tools import make_fixtures_fase1 as mk

DIR = Path(__file__).resolve().parents[1] / "fixtures" / "fase1"


def test_dos_generaciones_consecutivas_producen_los_mismos_bytes_y_hashes():
    a, b = mk.generar(), mk.generar()
    assert a == b
    assert {n: hashlib.sha256(x).hexdigest() for n, x in a.items()} == {n: hashlib.sha256(x).hexdigest() for n, x in b.items()}


def test_las_fixtures_del_disco_coinciden_con_lo_generado():
    assert mk.verificar() == []


def test_el_manifiesto_identifica_cada_fixture_con_hash_verificable():
    man = json.loads((DIR / "manifest.json").read_text(encoding="utf-8"))
    assert man["sintetico"] is True and man["semilla"] == mk.SEMILLA
    listados = {f["archivo"] for f in man["fixtures"]}
    en_disco = {p.name for p in DIR.glob("*") if p.is_file()} - {"manifest.json"}
    assert listados == en_disco and listados                           # ni faltan ni sobran
    for f in man["fixtures"]:
        raw = (DIR / f["archivo"]).read_bytes()
        assert f["sintetico"] is True
        assert hashlib.sha256(raw).hexdigest() == f["sha256"] and len(raw) == f["bytes"]


def test_todas_las_fixtures_declaran_sintetico_true():
    for p in DIR.glob("*.json"):
        if p.name != "manifest.json":
            assert json.loads(p.read_text(encoding="utf-8")).get("sintetico") is True, p.name


def test_no_hay_identificadores_ni_datos_reales():
    """Los identificadores sintéticos llevan prefijo; no hay correos, teléfonos ni nombres de archivos de datos."""
    texto = "\n".join(p.read_text(encoding="utf-8") for p in DIR.glob("*.json"))
    assert not re.search(r"[\w.]+@[\w.]+\.\w+", texto)                  # sin correos
    assert not re.search(r"\b\d{10,}\b", texto)                         # sin teléfonos ni cuentas
    assert "SINT" in texto.upper()


def test_el_generador_solo_escribe_dentro_de_su_directorio(tmp_path):
    with pytest.raises(SystemExit):
        mk.escribir(tmp_path)
    with pytest.raises(SystemExit):
        mk.escribir(mk.PERMITIDO.parent)
    assert not list(tmp_path.iterdir())


def test_el_generador_no_depende_de_archivos_de_datos():
    fuente = Path(mk.__file__).read_text(encoding="utf-8")
    assert "read_excel" not in fuente and "openpyxl" not in fuente and "data/ejemplos" not in fuente


def test_el_directorio_de_fixtures_no_oculta_el_modulo_tests_fixtures():
    """`tests/fixtures/` (directorio, sin __init__.py) convive con `tests/fixtures.py` (módulo): el módulo debe seguir ganando."""
    import importlib
    mod = importlib.import_module("tests.fixtures")
    assert getattr(mod, "__file__", "").endswith("fixtures.py") and callable(mod.build_base)
    assert not (DIR.parent / "__init__.py").exists()
