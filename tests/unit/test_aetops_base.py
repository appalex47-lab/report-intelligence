from decimal import Decimal

import pytest

from backend.app.importer.base_sheet import ImportRejected
from backend.app.pipeline import run_aetops_base
from tests.fixtures import build_base


def ids(res, severity=None):
    return [f.id for f in res.findings if severity is None or f.severity == severity]


def test_panorama_formulas_by_hand(tmp_path):
    res = run_aetops_base(build_base(tmp_path / "ok"))
    g = res.tables["aetops.panorama.yoy"].groups[0]
    a, b = g.previous.values, g.current.values
    assert (a["ticket"].v, b["ticket"].v) == (Decimal("20"), Decimal("25"))          # 1000/50, 1500/60
    assert (a["size_b"].v, b["size_b"].v) == (Decimal("2"), Decimal("2.5"))          # 200/100, 300/120
    assert (a["v_paciente"].v, b["v_paciente"].v) == (Decimal("10"), Decimal("12.5"))
    assert g.pct["monto"].v == Decimal("0.5") and g.pct["pedidos"].v == Decimal("0.2")
    assert g.current.label == "2026" and g.previous.label == "2025"


def test_canal_and_linea_share_uses_panorama_total(tmp_path):
    res = run_aetops_base(build_base(tmp_path / "ok"))
    for key in ("aetops.canal.yoy", "aetops.linea.yoy"):
        t = res.tables[key]
        assert [g.name for g in t.groups][0] in ("CANAL A", "AE-A")
        first = t.groups[0]
        assert first.current.values["share"].v == Decimal("0.6")                      # 900/1500
        assert first.previous.values["share"].v == Decimal("0.4")                     # 400/1000
        assert first.pct["monto"].v == Decimal("1.25")                                # (900-400)/400


def test_clean_file_has_no_blockers_and_extra_row_is_reported(tmp_path):
    res = run_aetops_base(build_base(tmp_path / "ok"))
    assert res.can_generate, [(f.id, f.message) for f in res.findings if f.severity == "block"]
    assert "ROW_IGNORED" in ids(res, "info")                       # no se ignora en silencio
    assert ids(res).count("ROW_IGNORED") == 1


def test_identical_mom_periods_block_generation(tmp_path):
    res = run_aetops_base(build_base(tmp_path / "dup", mom_identical=True))
    assert "IDENTICAL_PERIODS" in ids(res, "block") and not res.can_generate


def test_mom_group_with_other_period_labels_blocks(tmp_path):
    res = run_aetops_base(build_base(tmp_path / "lbl", mom_label_mismatch=True))
    assert "PERIOD_LABELS_INCONSISTENT" in ids(res, "block") and not res.can_generate


def test_unmapped_column_is_never_assigned_silently(tmp_path):
    res = run_aetops_base(build_base(tmp_path / "typo", header_typo=True))
    f = [x for x in res.findings if x.id == "COLUMN_UNMAPPED"]
    assert f and f[0].severity == "block" and "monto venat" in f[0].message
    assert not res.can_generate


def test_missing_pedidos_is_missing_not_zero(tmp_path):
    res = run_aetops_base(build_base(tmp_path / "miss", pedidos_blank=True))
    g = res.tables["aetops.panorama.yoy"].groups[0]
    assert g.current.values["pedidos"].status == "missing"
    assert g.current.values["ticket"].status == "missing"          # no 0, no excepción
    assert g.pct["pedidos"].status == "missing"


def test_totals_mismatch_is_warned(tmp_path):
    res = run_aetops_base(build_base(tmp_path / "tot", canal_total_off=True))
    assert any(f.id == "TOTALS_MISMATCH" and "monto" in f.message for f in res.findings)


def test_pasted_delta_from_excel_is_cross_checked_not_trusted(tmp_path):
    # el Excel sintético pega %Δ correctos -> no debe haber PASTED_DIFFERS en monto
    res = run_aetops_base(build_base(tmp_path / "ok"))
    assert not [f for f in res.findings if f.id == "PASTED_DIFFERS" and "/monto" in f.message]


def test_xlsm_and_bad_files_are_rejected(tmp_path):
    p = build_base(tmp_path / "macro", ext=".xlsm")
    with pytest.raises(ImportRejected):
        run_aetops_base(p)
    fake = tmp_path / "fake.xlsx"
    fake.write_text("no soy un zip")
    with pytest.raises(ImportRejected):
        run_aetops_base(fake)


def test_calc_does_not_depend_on_pptx_or_validator():
    """Regresión de arquitectura: cambiar plantillas no puede tocar los cálculos."""
    import pathlib, re
    for f in pathlib.Path("backend/app/calc").glob("*.py"):
        src = f.read_text()
        assert not re.search(r"^\s*(from|import)\s+.*\b(pptx|validator|pdf)\b", src, re.M), f
