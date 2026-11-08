"""Bloque integral · Diseño adaptativo y previsualización. PPTX sintéticos: corre en CI."""
import hashlib
import json
import shutil
import sys
from pathlib import Path

import pytest
from lxml import etree
from pptx import Presentation
from pptx.util import Pt

sys.path.insert(0, str(Path(__file__).parent))
import _deck as D                                                       # noqa: E402

from backend.app.plan import adaptativo as ad, previsualizacion as pv, reglas   # noqa: E402


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _correr(ruta, aplicar=True, dens=None):
    n = len(Presentation(str(ruta)).slides)
    return ad.adaptar(ruta, [f"contenido:{i}" for i in range(n)], dens or ["mixta"] * n, aplicar=aplicar)


def _textos(ruta):
    prs = Presentation(str(ruta))
    return [[sh.text_frame.text for sh in s.shapes if sh.has_text_frame] + [c.text_frame.text for sh in s.shapes if getattr(sh, "has_table", False) and sh.has_table
            for r in sh.table.rows for c in r.cells] for s in prs.slides]


# ------------------------------------------------------------------------------------------------------------------- diseño adaptativo
def test_si_todo_cabe_no_cambia_nada_ni_siquiera_el_archivo(tmp_path):
    p = D.crear(tmp_path / "a.pptx", [{"titulo": "Panorama General", "cuerpo": "Un texto corto que cabe de sobra.", "tabla": [["a", "b"], ["1", "2"]]}])
    antes = _sha(p)
    inf = _correr(p)
    assert not inf.modificado and inf.acciones == [] and inf.avisos == [] and _sha(p) == antes


def test_con_aplicar_desactivado_analiza_pero_no_modifica_el_archivo(tmp_path):
    p = D.crear(tmp_path / "a.pptx", [{"titulo": "Panorama General", "cuerpo": D.LARGO, "caja": (40, 90, 400, 60)}])
    antes = _sha(p)
    inf = _correr(p, aplicar=False)
    assert _sha(p) == antes and not inf.modificado and inf.avisos                   # detecta el desborde y lo informa, sin tocar el archivo


def test_si_hay_espacio_libre_debajo_se_amplia_el_cuadro_sin_tocar_la_letra(tmp_path):
    p = D.crear(tmp_path / "a.pptx", [{"titulo": "Panorama General", "cuerpo": "Frase de prueba bastante larga para ocupar varias líneas dentro del cuadro. " * 6, "caja": (40, 90, 880, 40)}])
    h0 = D.formas(p)["Cuerpo"].height
    inf = _correr(p)
    assert [a.tipo for a in inf.acciones] == ["ampliar_cuadro"] and D.formas(p)["Cuerpo"].height > h0 and set(D.tamanos(p, 0, "Cuerpo")) == {14.0}
    assert inf.avisos == [] and inf.estimaciones["contenido:0"]["Cuerpo"] <= 1.0


def test_si_hay_una_forma_debajo_se_reduce_la_letra_de_forma_proporcional_y_no_se_pisa(tmp_path):
    texto = "Frase de prueba bastante larga para ocupar varias líneas dentro del cuadro. " * 6
    p = D.crear(tmp_path / "a.pptx", [{"titulo": "Panorama General", "cuerpo": texto + "\n" + texto, "caja": (40, 90, 880, 100), "obstaculo": (40, 196, 880, 40), "pt_cuerpo": 16}])
    top0, h0 = D.formas(p)["Cuerpo"].top, D.formas(p)["Cuerpo"].height
    inf = _correr(p)
    assert [a.tipo for a in inf.acciones] == ["reducir_letra"]
    nuevos = D.tamanos(p, 0, "Cuerpo")
    assert 9.0 <= min(nuevos) < 16.0 and len(set(nuevos)) == 1                      # misma escala para todos los runs; jamás bajo 9 pt
    assert D.formas(p)["Cuerpo"].height == h0 and D.formas(p)["Cuerpo"].top == top0
    assert not [a for a in inf.avisos if a.codigo == "DISENO_SOLAPE"]


def test_se_conserva_la_jerarquia_al_reducir_la_letra(tmp_path):
    p = D.crear(tmp_path / "a.pptx", [{"titulo": "Panorama General", "cuerpo": ("Texto largo de prueba. " * 90), "caja": (40, 90, 880, 100), "obstaculo": (40, 196, 880, 40), "pt_cuerpo": 16}])
    t0 = Presentation(str(p)).slides[0].shapes
    titulo0 = [r.font.size.pt for sh in t0 if sh.name == "Titulo" for pa in sh.text_frame.paragraphs for r in pa.runs]
    _correr(p)
    titulo1 = [r.font.size.pt for sh in Presentation(str(p)).slides[0].shapes if sh.name == "Titulo" for pa in sh.text_frame.paragraphs for r in pa.runs]
    assert titulo0 == titulo1 == [28.0] and max(D.tamanos(p, 0, "Cuerpo")) < 28.0       # el título no se toca y el cuerpo sigue por debajo de él


def test_si_aun_asi_no_cabe_no_se_recorta_nada_y_se_avisa_con_una_propuesta(tmp_path):
    p = D.crear(tmp_path / "a.pptx", [{"titulo": "Panorama General", "cuerpo": D.LARGO * 3, "caja": (40, 90, 400, 80), "obstaculo": (40, 176, 400, 30), "pt_cuerpo": 14}])
    antes = _textos(p)
    inf = _correr(p)
    assert _textos(p) == antes                                                           # ni una palabra eliminada
    av = [a for a in inf.avisos if a.codigo == "DISENO_NO_CABE"]
    assert av and "Abreviar" in av[0].accion and min(D.tamanos(p, 0, "Cuerpo")) >= reglas.LETRA_MIN_PT


def test_el_piso_de_letra_se_respeta_aunque_el_original_ya_sea_pequeno(tmp_path):
    p = D.crear(tmp_path / "a.pptx", [{"titulo": "Panorama General", "cuerpo": D.LARGO, "caja": (40, 90, 400, 60), "obstaculo": (40, 152, 400, 30), "pt_cuerpo": 10}])
    _correr(p)
    assert min(D.tamanos(p, 0, "Cuerpo")) >= reglas.LETRA_MIN_PT


def test_una_tabla_que_no_cabe_reduce_su_letra_y_ajusta_las_filas(tmp_path):
    filas = [["Producto", "Monto", "Piezas"]] + [[f"PRODUCTO NÚMERO {i} CON NOMBRE LARGO PARA OCUPAR ESPACIO", f"${i * 1000:,}", str(i)] for i in range(1, 16)]
    p = D.crear(tmp_path / "a.pptx", [{"titulo": "Análisis de Productos", "tabla": filas, "tabla_y": 100, "alto_fila": 30, "pt_tabla": 14}])
    inf = _correr(p, dens=["tabla"])
    assert any(a.tipo == "ajustar_tabla" for a in inf.acciones)
    tam = {r.font.size.pt for row in D.formas(p)["Tabla"].table.rows for c in row.cells for pa in c.text_frame.paragraphs for r in pa.runs}
    assert min(tam) >= reglas.LETRA_MIN_PT and max(tam) < 14.0 and sum(1 for t in _textos(p)[0] if t.startswith("PRODUCTO NÚMERO")) == 15       # las 15 filas siguen ahí


def test_una_tabla_gigante_no_pierde_filas_y_se_avisa(tmp_path):
    filas = [["Producto", "Monto"]] + [[f"P{i}", str(i)] for i in range(60)]
    p = D.crear(tmp_path / "a.pptx", [{"titulo": "Análisis de Productos", "tabla": filas, "tabla_y": 100, "alto_fila": 14, "pt_tabla": 11}])
    inf = _correr(p, dens=["tabla"])
    assert len(Presentation(str(p)).slides[0].shapes[1].table.rows) == 61
    assert [a.codigo for a in inf.avisos].count("DISENO_NO_CABE") == 1


def test_el_ajuste_es_idempotente(tmp_path):
    p = D.crear(tmp_path / "a.pptx", [{"titulo": "Panorama General", "cuerpo": D.LARGO, "caja": (40, 90, 880, 60), "obstaculo": (40, 156, 880, 30)}])
    _correr(p)
    despues = _sha(p)
    inf2 = _correr(p)
    assert not inf2.acciones and _sha(p) == despues


def test_un_cuadro_que_se_ajusta_solo_o_sin_ajuste_de_linea_no_se_marca_como_desbordado(tmp_path):
    p = D.crear(tmp_path / "a.pptx", [{"titulo": "Resumen Ejecutivo", "cuerpo": "Título largo " * 20, "caja": (40, 90, 100, 30)}])
    prs = Presentation(str(p))
    sh = next(s for s in prs.slides[0].shapes if s.name == "Cuerpo")
    sh.text_frame.word_wrap = False
    prs.save(str(p))
    inf = _correr(p, aplicar=False)                                                       # sin ajuste de línea: una sola línea, cabe en alto
    assert not [a for a in inf.avisos if a.codigo == "DISENO_NO_CABE"]
    from pptx.enum.text import MSO_AUTO_SIZE
    prs = Presentation(str(p))
    sh = next(s for s in prs.slides[0].shapes if s.name == "Cuerpo")
    sh.text_frame.word_wrap = True
    sh.text_frame.auto_size = MSO_AUTO_SIZE.SHAPE_TO_FIT_TEXT
    prs.save(str(p))
    assert not [a for a in _correr(p, aplicar=False).avisos if a.codigo == "DISENO_NO_CABE"]


def test_un_cuadro_autoajustable_se_mide_contra_el_espacio_libre_hasta_la_forma_de_abajo(tmp_path):
    texto = "Frase de prueba bastante larga para ocupar varias líneas dentro del cuadro. " * 8
    libre = D.crear(tmp_path / "libre.pptx", [{"titulo": "Panorama General", "cuerpo": texto, "caja": (40, 90, 880, 30), "auto": True}])
    tope = D.crear(tmp_path / "tope.pptx", [{"titulo": "Panorama General", "cuerpo": texto, "caja": (40, 90, 880, 30), "auto": True, "obstaculo": (40, 150, 880, 30)}])
    assert _correr(libre, aplicar=False).avisos == []                                        # crece hacia abajo sin pisar nada: cabe
    inf = _correr(tope)                                                                       # la forma de abajo le corta el crecimiento: hay que reducir la letra
    assert [a.tipo for a in inf.acciones] == ["reducir_letra"] and min(D.tamanos(tope, 0, "Cuerpo")) < 14.0


def test_el_piso_es_acumulado_y_dos_pasadas_no_encadenan_reducciones(tmp_path):
    p = D.crear(tmp_path / "a.pptx", [{"titulo": "Panorama General", "cuerpo": D.LARGO * 3, "caja": (40, 90, 880, 60), "obstaculo": (40, 156, 880, 30), "pt_cuerpo": 16}])
    _correr(p)
    primero = D.tamanos(p, 0, "Cuerpo")
    _correr(p)
    _correr(p)
    assert D.tamanos(p, 0, "Cuerpo") == primero and min(primero) >= 16.0 * 0.80 - 0.5        # nunca por debajo del 80 % del tamaño ORIGINAL, por muchas pasadas que haya


def test_el_tamano_de_letra_heredado_no_se_estima_y_se_dice(tmp_path):
    p = D.crear(tmp_path / "a.pptx", [{"titulo": "Panorama General", "cuerpo": "Texto con tamaño heredado."}])
    prs = Presentation(str(p))
    sh = next(s for s in prs.slides[0].shapes if s.name == "Cuerpo")
    for r in sh.text_frame.paragraphs[0].runs:
        r.font.size = None
    prs.save(str(p))
    inf = _correr(p)
    assert [a.codigo for a in inf.avisos] == ["DISENO_NO_ESTIMABLE"] and not inf.acciones


def test_la_densidad_define_cuanto_puede_bajar_la_letra(tmp_path):
    texto = "Frase de prueba bastante larga para ocupar varias líneas dentro del cuadro. " * 14
    d = {"titulo": "Panorama General", "cuerpo": texto, "caja": (40, 90, 880, 110), "obstaculo": (40, 206, 880, 30), "pt_cuerpo": 16}
    a, b = D.crear(tmp_path / "a.pptx", [d]), D.crear(tmp_path / "b.pptx", [d])
    _correr(a, dens=["pocos_elementos"])
    _correr(b, dens=["narrativa_extensa"])
    assert min(D.tamanos(b, 0, "Cuerpo")) <= min(D.tamanos(a, 0, "Cuerpo"))             # la narrativa extensa tolera una reducción mayor


def test_los_ids_y_densidades_deben_corresponder_a_las_diapositivas(tmp_path):
    p = D.crear(tmp_path / "a.pptx", [{"titulo": "Panorama General", "cuerpo": "x"}])
    with pytest.raises(ValueError, match="no corresponde"):
        ad.adaptar(p, ["a", "b"], ["mixta"], aplicar=False)


# ------------------------------------------------------------------------------------------------------------------- previsualización
@pytest.fixture()
def deck(tmp_path):
    return D.crear(tmp_path / "p.pptx", [
        {"titulo": "Panorama General", "cuerpo": "Texto del panorama con cifras 1,500.", "tabla": [["Año", "Monto"], ["2025", "$1,000"], ["2026", "$2,000"]], "imagen": True, "color": "#1F4E79", "fondo": "#FFF2CC"},
        {"titulo": "Conclusiones Clave", "cuerpo": "Conclusión de cierre del periodo."},
    ])


def test_el_modelo_describe_formas_textos_tablas_e_imagenes_y_corresponde_al_archivo(deck):
    m = pv.modelo(deck, ["panorama:1", "conclusiones:2"], ["panorama", "conclusiones"])
    assert m["esquema"] == pv.ESQUEMA and m["huella"] == _sha(deck) and (m["ancho_pt"], m["alto_pt"]) == (960.0, 540.0)
    d = m["diapositivas"][0]
    assert d["id"] == "panorama:1" and d["tipo"] == "panorama"
    tipos = {f["tipo"] for f in d["formas"]}
    assert {"texto", "tabla", "imagen"} <= tipos
    tabla = next(f for f in d["formas"] if f["tipo"] == "tabla")
    assert len(tabla["filas"]) == 3 and [c["parrafos"][0]["runs"][0]["t"] for c in tabla["filas"][1]["celdas"]] == ["2025", "$1,000"]
    cuerpo = next(f for f in d["formas"] if f["nombre"] == "Cuerpo")
    assert cuerpo["relleno"] == "#FFF2CC" and cuerpo["parrafos"][0]["runs"][0]["c"] == "#1F4E79" and cuerpo["parrafos"][0]["runs"][0]["pt"] == 14.0
    assert pv.verificar_correspondencia(m, deck) == []
    json.dumps(m)                                                                          # serializable


def test_la_vista_previa_de_otro_archivo_o_modificado_esta_obsoleta(deck, tmp_path):
    m = pv.modelo(deck)
    copia = tmp_path / "c.pptx"
    shutil.copy(deck, copia)
    prs = Presentation(str(copia))
    next(s for s in prs.slides[0].shapes if s.name == "Cuerpo").text_frame.paragraphs[0].runs[0].text = "ALTERADO"
    prs.save(str(copia))
    assert [c for c, _, _ in pv.verificar_correspondencia(m, copia)] == ["PREVIEW_OBSOLETA"]


def test_un_modelo_adulterado_con_la_huella_correcta_se_detecta_con_el_lector_independiente(deck):
    m = pv.modelo(deck)
    m["diapositivas"][0]["formas"][0]["parrafos"][0]["runs"][0]["t"] = "Otra cosa"
    assert "PREVIEW_TEXTO" in [c for c, _, _ in pv.verificar_correspondencia(m, deck)]
    m2 = pv.modelo(deck)
    m2["diapositivas"][0]["formas"] = [f for f in m2["diapositivas"][0]["formas"] if f["tipo"] != "tabla"]
    assert {"PREVIEW_TEXTO", "PREVIEW_TABLAS"} <= {c for c, _, _ in pv.verificar_correspondencia(m2, deck)}
    m3 = pv.modelo(deck)
    m3["diapositivas"][0]["formas"] = [f for f in m3["diapositivas"][0]["formas"] if f["tipo"] != "imagen"]
    assert "PREVIEW_IMAGENES" in [c for c, _, _ in pv.verificar_correspondencia(m3, deck)]


def test_diapositivas_en_otro_orden_o_de_mas_o_de_menos_se_detectan(deck):
    m = pv.modelo(deck)
    m["diapositivas"].reverse()
    assert [c for c, _, _ in pv.verificar_correspondencia(m, deck)] == ["PREVIEW_ORDEN", "PREVIEW_ORDEN"]
    m = pv.modelo(deck)
    m["diapositivas"].pop()
    assert [c for c, _, _ in pv.verificar_correspondencia(m, deck)] == ["PREVIEW_NUM_DIAPOSITIVAS"]
    m = pv.modelo(deck)
    m["esquema"] = "otro/1"
    assert [c for c, _, _ in pv.verificar_correspondencia(m, deck)] == ["PREVIEW_ESQUEMA"]


def test_un_archivo_que_no_es_pptx_es_un_hallazgo_no_una_excepcion(deck, tmp_path):
    m = pv.modelo(deck)
    malo = tmp_path / "malo.pptx"
    malo.write_bytes(b"no es un zip")
    m["huella"] = _sha(malo)
    assert [c for c, _, _ in pv.verificar_correspondencia(m, malo)] == ["PREVIEW_ARCHIVO_ILEGIBLE"]


def test_los_grupos_se_aplanan_con_su_transformacion_y_sus_imagenes_se_verifican(tmp_path):
    p = D.crear(tmp_path / "g.pptx", [{"titulo": "Panorama General", "cuerpo": "Con un grupo."}])
    prs = Presentation(str(p))
    sl = prs.slides[0]
    g = sl.shapes.add_group_shape()
    t = g.shapes.add_textbox(Pt(100), Pt(300), Pt(200), Pt(40))
    t.name = "Hijo"
    t.text_frame.text = "Texto dentro del grupo"
    import io
    g.shapes.add_picture(io.BytesIO(D._png()), Pt(320), Pt(300), Pt(60), Pt(36)).name = "ImgHija"
    prs.save(str(p))
    m = pv.modelo(p)
    nombres = {f["nombre"]: f for f in m["diapositivas"][0]["formas"]}
    assert "Hijo" in nombres and "ImgHija" in nombres and nombres["Hijo"]["tipo"] == "texto" and nombres["ImgHija"]["tipo"] == "imagen"
    assert pv.verificar_correspondencia(m, p) == []                                       # el contenido del grupo SÍ se muestra y se verifica


def test_el_contenido_alternativo_se_muestra_como_recuadro_y_cuenta_como_grafica(tmp_path):
    p = D.crear(tmp_path / "alt.pptx", [{"titulo": "Panorama General", "cuerpo": "Con contenido alternativo."}])
    prs = Presentation(str(p))
    tree = prs.slides[0].shapes._spTree
    MC, P, A = "http://schemas.openxmlformats.org/markup-compatibility/2006", "http://schemas.openxmlformats.org/presentationml/2006/main", "http://schemas.openxmlformats.org/drawingml/2006/main"
    alt = etree.fromstring(f'<mc:AlternateContent xmlns:mc="{MC}" xmlns:p="{P}" xmlns:a="{A}"><mc:Choice Requires="x"><p:graphicFrame><p:xfrm><a:off x="1270000" y="2540000"/>'
                           f'<a:ext cx="2540000" cy="1270000"/></p:xfrm></p:graphicFrame></mc:Choice></mc:AlternateContent>')
    tree.append(alt)
    prs.save(str(p))
    m = pv.modelo(p)
    g = [f for f in m["diapositivas"][0]["formas"] if f["tipo"] == "grafica"]
    assert len(g) == 1 and (g[0]["x"], g[0]["y"], g[0]["w"], g[0]["h"]) == (100.0, 200.0, 200.0, 100.0) and "gráfica avanzada" in g[0]["nota"]
    assert pv.verificar_correspondencia(m, p) == []


def test_una_imagen_demasiado_grande_se_marca_no_se_oculta(tmp_path, monkeypatch):
    p = D.crear(tmp_path / "i.pptx", [{"titulo": "Panorama General", "cuerpo": "Con imagen.", "imagen": True}])
    monkeypatch.setattr(pv, "MAX_IMAGEN", 10)
    m = pv.modelo(p)
    img = next(f for f in m["diapositivas"][0]["formas"] if f["tipo"] == "imagen")
    assert m["imagenes"][img["imagen"]] is None and pv.verificar_correspondencia(m, p) == []
