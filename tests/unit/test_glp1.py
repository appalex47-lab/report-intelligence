import shutil
from decimal import Decimal
from pathlib import Path

import openpyxl
import pytest

from backend.app.importer.base_sheet import ImportRejected
from backend.app.models import Period
from backend.app.pipeline import run_glp1

DATA = Path(__file__).resolve().parents[2] / "data"
SEP = Period("GLP1", "mensual", 2026, 9)


def ids(res, sev=None):
    return [f.id for f in res.findings if sev is None or f.severity == sev]


def mutate(tmp_path, src="GLP1_sintetico_limpio.xlsx", fn=None, name="m.xlsx"):
    wb = openpyxl.load_workbook(DATA / src)
    if fn:
        fn(wb)
    out = tmp_path / name
    wb.save(out)
    return out


@pytest.fixture(scope="module")
def clean():
    return run_glp1(DATA / "GLP1_sintetico_limpio.xlsx", "mensual", SEP)


@pytest.fixture(scope="module")
def dirty():
    return run_glp1(DATA / "GLP1_sintetico_con_defectos.xlsx", "mensual", SEP)


def test_clean_machote_is_fully_parsed_and_passes(clean):
    assert clean.can_generate, [(f.id, f.message) for f in clean.findings if f.severity == "block"]
    assert not [f for f in clean.findings if f.severity == "warn"], [f.message for f in clean.findings if f.severity == "warn"]
    assert {"edad", "sexo", "dispositivo", "producto_sexo", "region", "region_anterior", "trafico_estado", "pago",
            "pago_anterior", "entrega", "negados", "productos", "programas", "fuentes", "fuentes_anterior",
            "canal_resumen"} <= set(clean.blocks)
    assert sum(1 for k in clean.blocks if k.startswith("edad_producto:")) == 5
    assert [r.key for r in clean.funnel.rows] == ["Ver producto", "Agregar a carrito", "Iniciar compra",
                                                  "Compra", "Carritos abandonados"]


def test_values_match_the_workbook_cells_with_lineage(clean):
    ws = openpyxl.load_workbook(DATA / "GLP1_sintetico_limpio.xlsx", data_only=True)["4"]
    row = clean.blocks["region"].rows[0]
    assert row.key == "CENTRO" and row.values["pedidos"].v == ws["B2"].value
    assert row.values["monto"].v == ws["D2"].value
    assert row.values["monto"].src.sheet == "4" and row.values["monto"].src.cells == "D2"


def test_shares_are_recalculated_and_sum_to_one(clean):
    for name in ("region", "pago", "entrega", "productos", "programas", "negados", "edad", "fuentes"):
        total = sum(r.share.v for r in clean.blocks[name].rows)
        assert abs(total - 1) < Decimal("0.000001"), name


def test_time_of_interaction_is_converted_to_seconds(clean):
    ws = openpyxl.load_workbook(DATA / "GLP1_sintetico_limpio.xlsx", data_only=True)["3"]
    h, m, s = map(int, ws["H2"].value.split(":"))
    assert clean.blocks["producto_sexo"].rows[0].values["tiempo"].v == h * 3600 + m * 60 + s
    assert clean.blocks["producto_sexo"].rows[0].dim2 == "Femenino"


def test_consistent_delta_is_published_without_metric_warning(clean):
    r = clean.blocks["region"].rows[0]
    assert r.delta_src == "pasted"
    assert abs(r.delta.v - r.engine_delta.v) < Decimal("0.001")
    assert "DELTA_METRIC_UNVERIFIED" not in ids(clean)


def test_funnel_rate_is_recomputed(clean):
    compra = clean.funnel.rows[3]
    assert compra.values["conteo"].v == 2600
    assert round(compra.values["tasa_calc"].v, 4) == Decimal("0.0054")


def test_defect_machote_triggers_each_planted_defect(dirty):
    got = set(ids(dirty))
    assert {"BLANK_ROW_INSIDE", "SHARE_ZERO", "TOTAL_ROW", "DUPLICATE_KEY", "NEGATIVE_VALUE",
            "NAME_VARIANT", "HEADER_TYPO_ACCEPTED"} <= got
    assert not dirty.can_generate and "BLANK_ROW_INSIDE" in ids(dirty, "block")


def test_zero_shares_are_recalculated_and_total_row_excluded(dirty):
    prod = dirty.blocks["productos"]
    assert all(r.values["share"].v == 0 for r in prod.rows)                 # lo pegado: 0
    assert sum(r.share.v for r in prod.rows) == pytest.approx(1)            # lo recalculado
    assert "Total" not in [r.key for r in prod.rows] and prod.declared_total["monto"].v > 0


def test_blank_row_truncation_is_visible_in_totals(dirty):
    assert len(dirty.blocks["region"].rows) < 8                              # se leyó solo hasta el hueco
    assert "CROSS_SHEET_TOTALS" in ids(dirty, "warn")


def test_name_variants_join_by_normalized_name(dirty):
    tarjeta = next(r for r in dirty.blocks["pago"].rows if r.key.startswith("Tarjeta de Cr"))
    assert tarjeta.engine_delta is not None and tarjeta.engine_delta.v is not None


def test_declared_period_mismatch_blocks_and_missing_declaration_warns(tmp_path):
    res = run_glp1(DATA / "GLP1_sintetico_limpio.xlsx", "mensual", Period("GLP1", "mensual", 2026, 10))
    assert "PERIOD_MISMATCH" in ids(res, "block")
    p = mutate(tmp_path, fn=lambda wb: wb.remove(wb["LEEME_SINTETICO"]))
    assert "PERIOD_UNDECLARED" in ids(run_glp1(p, "mensual", SEP), "warn")


def test_unknown_header_is_not_assigned_silently(tmp_path):
    p = mutate(tmp_path, fn=lambda wb: wb["4"].cell(1, 4, "Monto Venat"))
    res = run_glp1(p, "mensual", SEP)
    assert "COLUMN_UNMAPPED" in ids(res, "block") and "COLUMN_MISSING" in ids(res, "block")
    assert not res.can_generate


def test_missing_sheet_and_missing_block_block(tmp_path):
    p = mutate(tmp_path, fn=lambda wb: wb.remove(wb["6"]))
    res = run_glp1(p, "mensual", SEP)
    assert "MISSING_SHEET" in ids(res, "block") and not res.can_generate


def test_missing_values_are_not_zero(tmp_path):
    p = mutate(tmp_path, fn=lambda wb: setattr(wb["4"]["B2"], "value", None))
    res = run_glp1(p, "mensual", SEP)
    c = res.blocks["region"].rows[0]
    assert "pedidos" not in c.values or c.values["pedidos"].status == "missing"
    assert c.ticket_calc is None or c.ticket_calc.status == "missing"


def test_macro_workbooks_are_rejected(tmp_path):
    src = DATA / "GLP1_sintetico_limpio.xlsx"
    bad = tmp_path / "x.xlsm"
    shutil.copy(src, bad)
    with pytest.raises(ImportRejected):
        run_glp1(bad, "mensual", SEP)


def test_quarterly_profile_loads_same_structure():
    res = run_glp1(DATA / "GLP1_sintetico_limpio.xlsx", "trimestral", None)
    assert "region" in res.blocks and res.can_generate
