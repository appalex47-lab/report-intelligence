"""Compatibilidad del modelo de hallazgos (Fase 1 · 6.2): la firma histórica y `severity` no cambian."""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from backend.app.models import (EFECTO_A_SEVERITY, MODELO_HALLAZGOS_VERSION, SEVERITY_A_EFECTO, Finding)
from backend.app.validator.rules import has_blockers

FIX = json.loads((Path(__file__).resolve().parents[1] / "fixtures" / "fase1" / "hallazgos_compat.json").read_text(encoding="utf-8"))
NUEVOS = ("tipo", "gravedad", "estado_verificacion", "efecto_generacion", "faltante", "regla_id", "regla_version")


def _build(d: dict) -> Finding:
    return Finding(d["id"], d["severity"], d["message"], d.get("evidence", ""),
                   **{k: v for k, v in d.items() if k not in ("id", "severity", "message", "evidence")})


def test_1_firma_historica_con_cuatro_argumentos():
    f = Finding("ID", "warn", "mensaje", "evidencia")
    assert (f.id, f.severity, f.message, f.evidence) == ("ID", "warn", "mensaje", "evidencia")
    assert Finding("ID", "info", "m").evidence == ""          # evidence sigue siendo opcional


def test_2_los_argumentos_posicionales_funcionan_igual():
    assert Finding("A", "block", "m", "e") == Finding(id="A", severity="block", message="m", evidence="e")
    assert [f.name for f in dataclasses.fields(Finding)][:4] == ["id", "severity", "message", "evidence"]


def test_los_campos_nuevos_son_solo_por_palabra_clave():
    with pytest.raises(TypeError):
        Finding("A", "warn", "m", "e", "integridad")           # 5.º posicional: no permitido
    kw = {f.name for f in dataclasses.fields(Finding) if f.kw_only}
    assert kw == set(NUEVOS)


def test_3_severity_conserva_su_significado_y_los_ids_historicos():
    for d in FIX["legado"]:
        f = _build(d)
        assert f.severity == d["severity"] and f.id == d["id"]
    assert set(SEVERITY_A_EFECTO) == {"block", "warn", "info"}


def test_4_la_serializacion_conserva_severity():
    for d in FIX["legado"] + FIX["nuevos"]:
        out = _build(d).to_dict()
        assert out["severity"] == d["severity"]
        assert {"id", "severity", "message", "evidence"} <= set(out)
    # sin campos nuevos aportados, solo aparece el efecto derivado además de las cuatro claves históricas
    assert set(Finding("A", "warn", "m").to_dict()) == {"id", "severity", "message", "evidence", "efecto_generacion"}


def test_5_los_campos_nuevos_pueden_omitirse():
    f = Finding("A", "info", "m")
    assert f.tipo is None and f.gravedad is None and f.estado_verificacion is None
    assert f.faltante == () and f.regla_id is None and f.regla_version is None


def test_6_los_campos_nuevos_se_aceptan_por_palabra_clave():
    for d in FIX["nuevos"]:
        f = _build(d)
        for k in NUEVOS:
            if k in d:
                assert getattr(f, k) == d[k]
    f = Finding("A", "info", "m", estado_verificacion="no_verificable", faltante=[{"archivo": "trafico", "columna": "compras"}])
    assert f.faltante == ({"archivo": "trafico", "columna": "compras"},)


@pytest.mark.parametrize("sev,efecto", list(SEVERITY_A_EFECTO.items()))
def test_7_efecto_generacion_se_deriva_de_severity(sev, efecto):
    assert Finding("A", sev, "m").efecto_generacion == efecto
    assert EFECTO_A_SEVERITY[efecto] == sev                     # correspondencia inversa


def test_7b_correspondencia_documentada_exacta():
    assert SEVERITY_A_EFECTO == {"block": "bloquear", "warn": "advertir", "info": "informar"}


def test_8_una_combinacion_incoherente_se_detecta():
    for d in FIX["incoherentes"]:
        with pytest.raises(ValueError, match="incoherente"):
            _build(d)


def test_8b_los_valores_no_validos_y_el_no_verificable_sin_faltante_se_rechazan():
    for d in FIX["invalidos"]:
        with pytest.raises(ValueError):
            _build(d)


def test_8c_dos_hallazgos_con_los_mismos_datos_son_iguales_y_hashables():
    assert Finding("A", "warn", "m") == Finding("A", "warn", "m", efecto_generacion="advertir")
    assert hash(Finding("A", "warn", "m")) == hash(Finding("A", "warn", "m"))


def test_9_has_blockers_conserva_su_comportamiento():
    assert has_blockers([Finding("A", "warn", "m"), Finding("B", "block", "m")]) is True
    assert has_blockers([Finding("A", "warn", "m"), Finding("B", "info", "m")]) is False
    assert has_blockers([]) is False
    # un hallazgo con campos nuevos bloquea igual que antes, según `severity`
    assert has_blockers([Finding("A", "block", "m", tipo="integridad", gravedad="alta")]) is True
    assert has_blockers([Finding("A", "warn", "m", efecto_generacion="advertir")]) is False


def test_10_la_interfaz_actual_sigue_leyendo_los_hallazgos():
    """`web.service._finding` (lo que consume el frontend) devuelve las mismas cuatro claves de siempre."""
    from backend.app.web.service import _finding
    con_nuevos = Finding("A", "warn", "m", "e", tipo="integridad", gravedad="alta", regla_id="R-X", regla_version="1.0.0")
    assert _finding(con_nuevos) == {"id": "A", "severity": "warn", "message": "m", "evidence": "e"}
    assert _finding(Finding("A", "warn", "m", "e")) == _finding(con_nuevos)


def test_la_version_del_modelo_es_semver():
    import re
    assert re.match(r"^\d+\.\d+\.\d+$", MODELO_HALLAZGOS_VERSION)
