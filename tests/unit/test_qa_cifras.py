"""Fase 5 · AC-14: comprobaciones de CIFRAS, FÓRMULAS, UNIDADES y DENOMINADORES (`backend/app/qa/cifras.py`; spec §7.A y §3.2; T-11).

Deck sintético con valores de origen controlados e inyección de un defecto por prueba; los casos válidos (formato, redondeo, derivados) no deben alertar.
Con plantillas locales se comprueban además los 4 decks de referencia: 0 falsos positivos y, como única salida, las observaciones reales documentadas.
"""
from __future__ import annotations

import sys
from decimal import Decimal as D
from pathlib import Path

import pytest
from pptx import Presentation
from pptx.util import Inches, Pt

from backend.app.qa import cifras as C
from tests import plantillas as PL

ROOT = Path(__file__).resolve().parents[2]
VALORES = {D("7853122"), D("12221525"), D("927"), D("1353"), D("8472"), D("9033"), D("0.5558"), D("0.4596"), D("0.0662"), D("18883"), D("11329"), D("2643"), D("495144"), D("0.1248")}
NARRATIVA = {"$12.22 M", "+56%"}


def tabla(slide, filas, x=0.5, y=1.5):
    t = slide.shapes.add_table(len(filas), len(filas[0]), Inches(x), Inches(y), Inches(9), Inches(0.4 * len(filas))).table
    for i, f in enumerate(filas):
        for j, v in enumerate(f):
            t.cell(i, j).text = v
            for p in t.cell(i, j).text_frame.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(11)
    return t


def texto(slide, y, t):
    tb = slide.shapes.add_textbox(Inches(0.5), Inches(y), Inches(9), Inches(0.5))
    tb.text_frame.text = t
    return tb


def deck(tmp_path, filas=None, textos=(), nombre="d.pptx"):
    prs = Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[6])
    tabla(s, filas or [["Año", "Monto Venta", "Pedidos", "Ticket Promedio"], ["2025", "$7,853,122", "927", "$8,472"], ["2026", "$12,221,525", "1,353", "$9,033"], ["", "56%", "46%", "7%"]])
    for k, t in enumerate(textos):
        texto(s, 4 + 0.6 * k, t)
    p = tmp_path / nombre
    prs.save(p)
    return p


def ids(issues):
    return [i.id for i in issues]


def revisar(p, valores=VALORES, narrativa=NARRATIVA):
    return C.revisar(p, valores, narrativa)


# --------------------------------------------------------------------------------------------- casos válidos: 0 alertas
def test_el_deck_correcto_no_alerta(tmp_path):
    assert revisar(deck(tmp_path, textos=["La venta de septiembre fue $12.22 M, +56% vs el mismo periodo del año anterior.", "El ticket promedio sube 7% vs 2025."])) == []


@pytest.mark.parametrize("impreso", ["$12.22 M", "$12,221,525", "$12.2 M", "$12 M", "12,221,525"])
def test_formatos_y_redondeos_de_un_mismo_valor_no_alertan(tmp_path, impreso):
    assert C.comprobar_cifras(Presentation(deck(tmp_path, textos=[f"Venta {impreso} del periodo"])), VALORES, set()) == []


@pytest.mark.parametrize("impreso", ["56%", "55.6%", "+56%", "46%", "+46%", "6.6%"])
def test_porcentajes_como_fraccion_del_motor_no_alertan(tmp_path, impreso):
    assert C.comprobar_cifras(Presentation(deck(tmp_path, textos=[f"Cambio {impreso} vs agosto"])), VALORES, set()) == []


def test_lo_derivable_de_dos_numeros_de_la_lamina_no_alerta(tmp_path):
    """Embudo: «avanza 23.33 %» = 2,643 ÷ 11,329; ninguno de los dos es el 23.33 en el motor."""
    assert C.comprobar_cifras(Presentation(deck(tmp_path, textos=["De 11,329 inicios de compra se concretan 2,643: avanza 23.33% al siguiente paso"])), VALORES, set()) == []


@pytest.mark.parametrize("texto", ["Hubo 5 reuniones", "ENZALUTAMIDA 40 MG CAP C/112", "Sivec 24369", "Tiempo 00:01:39", "Octubre de 2026", "Q3 2026", "1. Primer punto del plan"])
def test_anios_codigos_horas_nombres_e_indices_no_son_cifras(tmp_path, texto):
    got = [i for i in C.comprobar_cifras(Presentation(deck(tmp_path, textos=[texto])), VALORES, set()) if "Hubo 5" not in i.message]
    assert got == [], got


# --------------------------------------------------------------------------------------------- cifras
def test_cifra_modificada_se_detecta(tmp_path):
    r = C.comprobar_cifras(Presentation(deck(tmp_path, textos=["La venta de septiembre fue $13.57 M"])), VALORES, set())
    assert ids(r) == ["PPTX_CIFRA_NO_TRAZADA"] and "$13.57 M" in r[0].message


def test_cifra_en_celda_modificada_se_detecta(tmp_path):
    filas = [["Año", "Monto Venta", "Pedidos", "Ticket Promedio"], ["2025", "$7,853,122", "927", "$8,472"], ["2026", "$12,999,999", "1,353", "$9,607"]]
    assert "PPTX_CIFRA_NO_TRAZADA" in ids(C.comprobar_cifras(Presentation(deck(tmp_path, filas)), VALORES, set()))


def test_cifra_de_la_narrativa_verificada_se_acepta(tmp_path):
    assert C.comprobar_cifras(Presentation(deck(tmp_path, textos=["Resultado de $99.9 M calculado en la narrativa"])), VALORES, {"$99.9 M"}) == []


def test_sin_valores_del_motor_se_declara_que_no_se_comprobo(tmp_path):
    r = C.revisar(deck(tmp_path), None, None)
    assert "PPTX_CIFRA_NO_EVALUADA" in ids(r) and "PPTX_CIFRA_NO_TRAZADA" not in ids(r)


def test_cifra_con_valor_cero_y_celdas_vacias_no_alertan(tmp_path):
    filas = [["Año", "Monto Venta", "Pedidos", "Ticket Promedio"], ["2025", "$0", "0", ""], ["2026", "", "—", "—"]]
    assert [i for i in C.comprobar_cifras(Presentation(deck(tmp_path, filas)), VALORES | {D(0)}, set())] == []


# --------------------------------------------------------------------------------------------- fórmulas
def test_ticket_alterado_se_detecta(tmp_path):
    filas = [["Año", "Monto Venta", "Pedidos", "Ticket Promedio"], ["2025", "$7,853,122", "927", "$8,472"], ["2026", "$12,221,525", "1,353", "$9,500"]]
    r = C.comprobar_tablas(Presentation(deck(tmp_path, filas)))
    assert ids(r) == ["PPTX_FORMULA_NO_COINCIDE"] and "Ticket" in r[0].message


def test_variacion_alterada_se_detecta(tmp_path):
    filas = [["Año", "Monto Venta", "Pedidos", "Ticket Promedio"], ["2025", "$7,853,122", "927", "$8,472"], ["2026", "$12,221,525", "1,353", "$9,033"], ["", "80%", "46%", "7%"]]
    r = C.comprobar_tablas(Presentation(deck(tmp_path, filas)))
    assert ids(r) == ["PPTX_FORMULA_NO_COINCIDE"] and "80%" in r[0].message


def test_denominador_incorrecto_en_el_ticket_se_detecta(tmp_path):
    """Ticket calculado con pacientes en lugar de pedidos: 12,221,525 ÷ 962 = 12,704, no 9,033."""
    filas = [["Año", "Monto Venta", "Pacientes", "Pedidos", "Ticket Promedio"], ["2026", "$12,221,525", "962", "1,353", "$12,704"]]
    assert "PPTX_FORMULA_NO_COINCIDE" in ids(C.comprobar_tablas(Presentation(deck(tmp_path, filas))))


def test_ticket_con_cero_pedidos_se_detecta_y_no_divide(tmp_path):
    filas = [["Año", "Monto Venta", "Pedidos", "Ticket Promedio"], ["2026", "$12,221,525", "0", "$9,033"]]
    r = C.comprobar_tablas(Presentation(deck(tmp_path, filas)))
    assert any("0 pedidos" in i.message for i in r)


@pytest.mark.parametrize("monto,pedidos,ticket", [("$7,853,122", "927", "$8,472"), ("$12,221,525", "1,353", "$9,033"), ("$100", "3", "$33"), ("$1,000", "7", "$143")])
def test_el_redondeo_del_ticket_no_es_un_error(tmp_path, monto, pedidos, ticket):
    filas = [["Año", "Monto Venta", "Pedidos", "Ticket Promedio"], ["2026", monto, pedidos, ticket]]
    assert C.comprobar_tablas(Presentation(deck(tmp_path, filas))) == []


def test_fuentes_distintas_no_se_mezclan_en_la_formula(tmp_path):
    """El ticket se contrasta con PEDIDOS; una columna de compras GA4 no sustituye al denominador ni se usa para validar."""
    con_ga4 = [["Año", "Monto Venta", "Compras GA4", "Ticket Promedio"], ["2026", "$12,221,525", "2,643", "$4,624"]]
    assert C.comprobar_tablas(Presentation(deck(tmp_path, con_ga4))) == []                  # sin columna de pedidos no hay nada que contrastar: no se inventa
    mezcla = [["Año", "Monto Venta", "Pedidos", "Compras GA4", "Ticket Promedio"], ["2026", "$12,221,525", "1,353", "2,643", "$4,624"]]
    assert "PPTX_FORMULA_NO_COINCIDE" in ids(C.comprobar_tablas(Presentation(deck(tmp_path, mezcla))))   # ticket con compras GA4 ≠ monto ÷ pedidos


def test_las_tablas_con_bloques_apilados_no_confunden_columnas(tmp_path):
    filas = [["Producto", "Pedidos", "Cantidad", "Monto Negado", "Share"], ["A", "41", "42", "$104,728", "26%"], ["", "", "", "", ""], ["", "Monto negado", "$399,037", "", ""],
             ["", "", "", "", ""], ["Alta", "Pedidos", "Cantidad Negada", "Monto Negado", "Share"], ["AE-A", "73", "93", "$350,092", "88%"]]
    assert C.comprobar_tablas(Presentation(deck(tmp_path, filas))) == []


# --------------------------------------------------------------------------------------------- unidades
def test_moneda_mezclada_en_una_columna(tmp_path):
    filas = [["Año", "Monto Venta", "Pedidos", "Ticket Promedio"], ["2025", "$7,853,122", "927", "$8,472"], ["2026", "12,221,525", "1,353", "$9,033"]]
    assert any("mezcla" in i.message for i in C.comprobar_tablas(Presentation(deck(tmp_path, filas))))


def test_conteo_con_signo_de_pesos_o_porcentaje(tmp_path):
    filas = [["Año", "Monto Venta", "Pedidos", "Ticket Promedio"], ["2025", "$7,853,122", "$927", "$8,472"]]
    assert any("conteos" in i.message for i in C.comprobar_tablas(Presentation(deck(tmp_path, filas))))


def test_porcentaje_sin_simbolo_en_columna_de_share(tmp_path):
    filas = [["Producto", "Monto Venta", "Share"], ["A", "$100", "26%"], ["B", "$80", "21"]]
    assert any("sin `%`" in i.message for i in C.comprobar_tablas(Presentation(deck(tmp_path, filas))))


@pytest.mark.parametrize("texto", ["Venta de 12 MXN", "Total en dólares", "Ingreso USD 5", "Monto en pesos mexicanos", "€ 12"])
def test_moneda_inventada_se_detecta(tmp_path, texto):
    r = C.comprobar_moneda(Presentation(deck(tmp_path, textos=[texto])))
    assert ids(r) == ["PPTX_UNIDAD_AMBIGUA"] and "ningún libro declara la moneda" in r[0].message


def test_el_signo_de_pesos_solo_no_es_una_moneda_inventada(tmp_path):
    assert C.comprobar_moneda(Presentation(deck(tmp_path, textos=["Venta $12.22 M"]))) == []


# --------------------------------------------------------------------------------------------- denominadores
def test_porcentaje_de_proporcion_sin_base_se_detecta(tmp_path):
    r = C.comprobar_denominadores(Presentation(deck(tmp_path, textos=["El resultado es de 12% para el grupo seleccionado."])))
    assert ids(r) == ["PPTX_SIN_DENOMINADOR"]
    assert C.comprobar_denominadores(Presentation(deck(tmp_path, textos=["El resultado es 12% de la venta del periodo."]))) == []


@pytest.mark.parametrize("t", ["La venta crece +8% frente al mes previo", "Cae -3% en el trimestre", "Ticket promedio 0%", "Visitas 1,200 (+22%); usuarios 900 (-3%)"])
def test_las_variaciones_con_signo_o_cero_no_exigen_base_propia(tmp_path, t):
    assert C.comprobar_denominadores(Presentation(deck(tmp_path, textos=[t]))) == []


# --------------------------------------------------------------------------------------------- utilidades y decks reales
def test_recolectar_valores_recorre_dataclasses_y_estructuras():
    from backend.app.models import GBlock, GRow, Value
    b = GBlock("x", "h", "agregado", [GRow("k", "", {"m": Value(D("12.5"), "ok", None)})])
    assert D("12.5") in C.recolectar_valores({"bloque": b, "otros": [D(3), "texto", None]}) and D(3) in C.recolectar_valores([D(3)])


def test_el_indice_acepta_dentro_de_la_tolerancia_y_rechaza_fuera():
    ind = C.Indice([D("12221525")])
    assert ind.hay(D("12220000"), D("5000")) and not ind.hay(D("12200000"), D("5000"))


ESC = {"aetops_mensual_2026-09": ("aetops-mensual", set()), "aetops_trimestral_2026-Q3": ("aetops-trimestral", set()),
       "glp1_mensual_2026-09": ("glp1-mensual", {"Las presentaciones que más venden"}), "glp1_trimestral_2026-Q3": ("glp1-trimestral", {"Las presentaciones que más venden"})}


@pytest.mark.parametrize("nombre", sorted(ESC))
def test_decks_de_referencia_sin_falsos_positivos(nombre, tmp_path):
    """Libros de EJEMPLO sintéticos y plantillas locales. Única salida admitida: la observación real documentada (GLP-1: «Mounjaro (74%, $9.20 M)» no nombra su
    base, §3.2). Cualquier otro hallazgo, o ese en AETOPS, es un falso positivo y falla."""
    tpl = PL.ruta(ESC[nombre][0])
    if not tpl.exists():
        pytest.skip("OMITIDA (no ejecutada): la plantilla no se versiona y no está disponible")
    sys.path.insert(0, str(ROOT))
    from tools.capture_baseline import _run
    from backend.app.build import build_aetops, build_glp1
    unit, period, _p, _t, res, _ = _run(nombre)
    b = (build_aetops if unit == "AETOPS" else build_glp1)(res, period, tpl, tmp_path, render=False)
    nar = {c for ps in b.fill.narrative.values() for p in ps for c in p.nums}
    r = C.revisar(b.pptx, C.recolectar_valores(res), nar)
    permitido = ESC[nombre][1]
    inesperado = [(i.id, i.message) for i in r if not (i.id == "PPTX_SIN_DENOMINADOR" and any(m in i.message for m in permitido))]
    assert inesperado == [], inesperado
    assert len(r) == (1 if permitido else 0)
    # y el defecto inyectado en el deck real se detecta
    prs = Presentation(b.pptx)
    texto(prs.slides[1], 6.9, "Venta del periodo $987.65 M en MXN")
    prs.save(tmp_path / "mal.pptx")
    mal = ids(C.revisar(tmp_path / "mal.pptx", C.recolectar_valores(res), nar))
    assert "PPTX_CIFRA_NO_TRAZADA" in mal and "PPTX_UNIDAD_AMBIGUA" in mal
