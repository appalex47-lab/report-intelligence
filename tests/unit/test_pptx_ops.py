from decimal import Decimal

from pptx import Presentation
from pptx.util import Emu, Inches

from backend.app.deck import pptx_ops as ops


def make_table(rows=5, cols=3):
    prs = Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[6])
    gf = s.shapes.add_table(rows, cols, Inches(1), Inches(1), Inches(6), Inches(0.3 * rows))
    t = gf.table
    for r in range(rows):
        for c in range(cols):
            t.cell(r, c).text = f"r{r}c{c}"
            run = t.cell(r, c).text_frame.paragraphs[0].runs[0]
            run.font.size = Emu(12 * 12700)
            run.font.name = "Aptos Narrow"
    return prs, s, gf, t


def test_delta_style_matches_excel_palette():
    assert ops.delta_style(Decimal("0.01")) == ("C6EFCE", "006100")
    assert ops.delta_style(Decimal("-0.01")) == ("FFC7CE", "9C0006")
    assert ops.delta_style(Decimal("0")) == ("FFEB9C", "9C5700")
    assert ops.delta_style(None) is None


def test_set_cell_keeps_font_and_applies_colors():
    _, _, _, t = make_table()
    ops.set_cell(t.cell(1, 1), "$1,234", fill="C6EFCE", font="006100")
    run = t.cell(1, 1).text_frame.paragraphs[0].runs[0]
    assert run.text == "$1,234" and run.font.size.pt == 12 and run.font.name == "Aptos Narrow"
    assert str(run.font.color.rgb) == "006100"
    assert str(t.cell(1, 1).fill.fore_color.rgb) == "C6EFCE"


def test_set_cell_on_empty_cell_inherits_format_from_prototype():
    _, _, _, t = make_table()
    ops.clear_cell(t.cell(2, 0))
    assert not t.cell(2, 0).text_frame.paragraphs[0].runs          # sin runs
    ops.set_cell(t.cell(2, 0), "X", proto=t.cell(1, 0))
    run = t.cell(2, 0).text_frame.paragraphs[0].runs[0]
    assert run.text == "X" and run.font.size.pt == 12 and run.font.name == "Aptos Narrow"


def test_clearing_a_cell_leaves_no_empty_run_but_keeps_font_size():
    """Un run vacío agranda la fila al renderizar; el tamaño se conserva en endParaRPr."""
    _, _, _, t = make_table()
    ops.set_cell(t.cell(1, 1), "")
    p = t.cell(1, 1).text_frame.paragraphs[0]._p
    assert not p.findall("{http://schemas.openxmlformats.org/drawingml/2006/main}r")
    end = p.find("{http://schemas.openxmlformats.org/drawingml/2006/main}endParaRPr")
    assert end is not None and end.get("sz") == "1200"
    ops.set_cell(t.cell(1, 1), "")                                  # idempotente: no crea runs
    assert not t.cell(1, 1).text_frame.paragraphs[0].runs


def test_resize_rows_clones_prototype_and_deletes_tail():
    _, _, gf, t = make_table(rows=5)
    ops.resize_rows(t, 1, 5, 1, 7)                     # 4 filas de datos -> 7
    assert len(t.rows) == 8
    assert t.cell(7, 0).text == "r1c0"                 # las nuevas son copias de la fila prototipo
    ops.resize_rows(t, 1, 8, 1, 2)
    assert len(t.rows) == 3
    ops.sync_frame_height(gf)
    assert gf.height == sum(r.height for r in t.rows)


def test_resize_blocks_repeats_whole_blocks():
    _, _, _, t = make_table(rows=1 + 2 * 3)            # cabecera + 3 bloques de 2 filas
    ops.resize_blocks(t, 1, 2, 3, 5)
    assert len(t.rows) == 1 + 2 * 5
    ops.resize_blocks(t, 1, 2, 5, 1)
    assert len(t.rows) == 3


def test_set_paragraphs_bold_markup_and_format_inheritance():
    prs = Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[6])
    tb = s.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(2))
    tb.text_frame.text = "viejo"
    tb.text_frame.paragraphs[0].runs[0].font.size = Emu(14 * 12700)
    ops.set_paragraphs(tb, ["La venta crece **+67%** vs 2025.", "", "Segundo párrafo."])
    ps = tb.text_frame.paragraphs
    assert [p.text for p in ps] == ["La venta crece +67% vs 2025.", "", "Segundo párrafo."]
    runs = ps[0].runs
    assert [r.font.bold for r in runs] == [False, True, False]
    assert all(r.font.size.pt == 14 for r in runs)


def test_shape_by_name_fails_loudly_when_template_changes():
    prs = Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[6])
    import pytest
    with pytest.raises(KeyError):
        ops.shape_by_name(s, "No existe")
