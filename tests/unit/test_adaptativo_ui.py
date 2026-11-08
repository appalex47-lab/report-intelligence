"""Fase 6 · diseño adaptativo de la interfaz: comprobaciones ESTÁTICAS de `frontend/index.html` que sí corren en CI.

Alcance honesto: no ejecutan el JavaScript ni miden el diseño; solo garantizan que las reglas que lo hacen adaptativo no se pierdan por accidente. La medición real
(5 anchos, 10 pantallas, Chromium con Pyodide) está en tests/e2e/test_responsivo.py y solo corre en local."""
import re
from pathlib import Path

HTML = (Path(__file__).resolve().parents[2] / "frontend" / "index.html").read_text(encoding="utf-8")
CSS = HTML[HTML.index("<style>"):HTML.index("</style>")]


def test_declara_el_viewport_para_pantallas_pequenas():
    assert '<meta name="viewport" content="width=device-width, initial-scale=1">' in HTML


def test_los_puntos_de_ruptura_anteriores_se_conservan():
    assert "@media(max-width:900px){.work{grid-template-columns:1fr}}" in CSS               # panel de revisión de narrativa a una columna
    assert "@media(max-width:900px){.pvlay{grid-template-columns:1fr}" in CSS               # vista previa: lista sobre la diapositiva
    assert "@media(max-width:900px){.rail{position:static!important;max-height:none!important}}" in CSS


def test_el_contenido_no_ensancha_la_pagina():
    assert ".wrap{grid-template-columns:minmax(0,1fr)}" in CSS
    assert "#view,.grid:not(.g2){grid-template-columns:minmax(0,1fr)}" in CSS
    assert "code,.find>div,.sub{overflow-wrap:anywhere}" in CSS


def test_una_tabla_que_no_cabe_se_desplaza_dentro_de_su_tarjeta_y_no_en_la_pagina():
    assert re.search(r"@media\(max-width:900px\)\{[^}]*\.card\{overflow-x:auto\}", CSS)
    assert "table:has(tr>:nth-child(4)){min-width:520px}" in CSS                            # tablas anchas conservan columnas legibles


def test_los_controles_tactiles_tienen_tamano_minimo_en_pantallas_pequenas():
    bloque = CSS[CSS.index("/* Fase 6"):]
    assert "input[type=checkbox],input[type=radio]{width:24px;height:24px}" in bloque
    assert "summary{min-height:24px}" in bloque and ".mini{min-height:28px;padding:4px 8px}" in bloque


def test_la_vista_previa_es_desplazable_y_conserva_un_ancho_legible_en_movil():
    assert ".pvwrap{max-width:100%;overflow-x:auto}" in CSS
    assert ".pvwrap .pvs{min-width:720px}" in CSS
    assert '<div class="pvwrap"><div class="pvs" id="pvs"' in HTML                         # la diapositiva sigue siendo #pvs (la escala usa su ancho)


def test_las_pestanas_se_desplazan_en_movil_en_lugar_de_desbordar():
    assert ".tabs{overflow-x:auto}.tab{white-space:nowrap}" in CSS
