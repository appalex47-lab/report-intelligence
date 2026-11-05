"""Fase 3A-2 · resultado canónico y `hash_resultado` (`backend/app/provenance.py`; spec Fase 3A §6).

Todo con datos construidos a mano (sin plantillas ni libros): corre en CI. Las pruebas con los libros de ejemplo y con el flujo real de
generación están en `tests/regression/test_hash_resultado.py`.
"""
import copy
import dataclasses
import datetime
import hashlib
import json
import subprocess
import sys
import time
import unicodedata
from decimal import Decimal
from pathlib import Path

import pytest

from backend.app import provenance as pv
from backend.app.models import Finding, Group, Lineage, Period, PeriodRow, Table, Value
from backend.app.narrative.writer import Para

ROOT = Path(__file__).resolve().parents[2]
SHA_A, SHA_B = "a" * 64, "b" * 64
P = Period("AETOPS", "mensual", 2026, 9)


@dataclasses.dataclass
class R:
    """Un Result mínimo de AETOPS (tables, products, negados, extras, findings)."""
    tables: dict
    findings: list
    products: dict = dataclasses.field(default_factory=dict)
    negados: dict = dataclasses.field(default_factory=dict)
    extras: dict = dataclasses.field(default_factory=dict)


def val(x="10", archivo="libro.xlsx", cells="Base!C3", note=""):
    return Value(Decimal(x), "ok", Lineage(archivo, "Base", cells, "pasted"), note)


def resultado(x="10", archivo="libro.xlsx", findings=None, extras=None, cells="Base!C3", note=""):
    g = Group("AE-A", PeriodRow("2025", {"monto": val("5", archivo)}), PeriodRow("2026", {"monto": val(x, archivo, cells, note)}))
    return R({"aetops.linea.yoy": Table("aetops.linea.yoy", "yoy", [g])}, findings if findings is not None else [], extras=extras or {})


def fuentes(nombre="libro.xlsx", sha=SHA_A):
    return [{"nombre": nombre, "sha256": sha}]


def narr(*textos, editado=False, visible=True):
    return {"conclusiones": [Para(t, "hecho", edited=editado, visible=visible) for t in textos]}


def h(res=None, fte=None, nar=None, periodo=P):
    return pv.calcular(periodo, fuentes() if fte is None else fte, res or resultado(), nar if nar is not None else narr("Hola"))["valor"]


# ----------------------------------------------------------------------------------------------------------------- determinismo
def test_mismas_entradas_mismo_hash_y_formato_del_campo():
    a, b = h(), h()
    assert a == b and len(a) == 64 and a == a.lower()
    campo = pv.calcular(P, fuentes(), resultado(), narr("Hola"))
    assert campo == {"algoritmo": "sha256", "contrato": "resultado_canonico/1", "valor": a}


def test_el_orden_de_insercion_de_las_claves_no_cambia_el_hash():
    a = resultado(extras={"x": 1, "y": {"b": 2, "a": 1}})
    b = resultado(extras={"y": {"a": 1, "b": 2}, "x": 1})
    assert h(a) == h(b)


def test_el_orden_de_las_listas_si_cuenta_y_el_de_los_conjuntos_no():
    assert h(resultado(extras={"l": [1, 2, 3]})) != h(resultado(extras={"l": [3, 2, 1]}))
    assert h(resultado(extras={"s": {"b", "a", "c"}})) == h(resultado(extras={"s": {"c", "a", "b"}}))
    assert h(resultado(extras={"s": frozenset({"a", "b"})})) == h(resultado(extras={"s": {"b", "a"}}))


def test_el_orden_de_las_fuentes_no_cambia_el_hash():
    f1 = [{"nombre": "a.xlsx", "sha256": SHA_A}, {"nombre": "b.xlsx", "sha256": SHA_B}]
    assert h(fte=f1) == h(fte=list(reversed(f1)))


def test_el_resultado_no_depende_del_directorio_del_proceso(tmp_path, monkeypatch):
    a = h()
    monkeypatch.chdir(tmp_path)
    assert h() == a


def test_es_igual_en_otro_proceso_con_otra_semilla_de_hash_de_python():
    codigo = (
        "from decimal import Decimal\n"
        "from backend.app import provenance as pv\n"
        "from backend.app.models import Period\n"
        "from tests.unit.test_provenance import resultado, fuentes, narr\n"
        "print(pv.calcular(Period('AETOPS','mensual',2026,9), fuentes(), resultado(extras={'s': {'z','a','m','x','q'}, 'd': {'k2': 1, 'k1': 2}}), narr('Hola')) ['valor'])")
    valores = set()
    for semilla in ("0", "1", "12345", "random"):
        env = {"PYTHONHASHSEED": semilla, "PYTHONPATH": str(ROOT), "PATH": "/usr/bin:/bin"}
        r = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, cwd=ROOT, env=env, timeout=60)
        assert r.returncode == 0, r.stderr[-500:]
        valores.add(r.stdout.strip())
    assert len(valores) == 1


# ----------------------------------------------------------------------------------------------------------------- sensibilidad
@pytest.mark.parametrize("cambio", [
    dict(res=resultado("11")),                                                   # un valor
    dict(res=resultado(cells="Base!C4")),                                        # el linaje de la celda
    dict(res=resultado(note="nota")),                                            # la nota del valor
    dict(res=resultado(findings=[Finding("X", "warn", "mensaje")])),             # un hallazgo
    dict(nar=narr("Hola.")),                                                     # una coma/punto en un párrafo
    dict(nar=narr("Hola", "Otro")),                                              # un párrafo más
    dict(nar=narr("Hola", editado=True)),                                        # el mismo texto, ahora editado a mano
    dict(nar={"otra": narr("Hola")["conclusiones"]}),                            # el nombre de la sección
    dict(fte=fuentes(sha=SHA_B)),                                                # el CONTENIDO de la fuente
    dict(periodo=Period("AETOPS", "mensual", 2026, 10)),                         # el periodo
    dict(periodo=Period("GLP1", "mensual", 2026, 9)),
])
def test_cambiar_un_dato_relevante_cambia_el_hash(cambio):
    assert h(**cambio) != h()


def test_cada_campo_del_hallazgo_pesa():
    base = dict(id="X", severity="warn", message="m", evidence="e", tipo="integridad", gravedad="media", estado_verificacion="verificado",
                regla_id="R-1", regla_version="1.0.0")
    h0 = h(resultado(findings=[Finding(**base)]))
    cambios = [dict(id="Y"), dict(severity="info"), dict(severity="block"), dict(message="m2"), dict(evidence="e2"), dict(tipo="cobertura"),
               dict(gravedad="alta"), dict(estado_verificacion="no_verificable", faltante=("hoja",)), dict(regla_id="R-2"), dict(regla_version="1.0.1"),
               dict(faltante=("columna",)), dict(severity="warn", efecto_generacion="advertir", tipo=None)]
    vistos = {h0}
    for cambio in cambios:
        otro = h(resultado(findings=[Finding(**{**base, **cambio})]))
        assert otro != h0, cambio
        vistos.add(otro)
    assert len(vistos) == len(cambios) + 1                                    # cada cambio da un hash propio


def test_un_comentario_editado_a_mano_cambia_el_hash_y_la_coma_tambien():
    assert h(nar=narr("Ventas +26%, piezas +16%")) != h(nar=narr("Ventas +26% piezas +16%"))


def test_decimal_exacto_no_se_normaliza():
    assert h(resultado("1.0")) != h(resultado("1.00"))                           # texto exacto del Decimal (contrato §6.3)


# ----------------------------------------------------------------------------------------------------------------- exclusiones y normalización
def test_el_nombre_o_la_ruta_del_archivo_no_cambia_el_hash_pero_si_su_contenido():
    base = h(resultado(archivo="libro.xlsx"), fuentes("libro.xlsx"))
    assert h(resultado(archivo="OTRO NOMBRE.xlsx"), fuentes("OTRO NOMBRE.xlsx")) == base
    assert h(resultado(archivo="libro.xlsx"), fuentes("/home/u/dir/libro.xlsx")) == base
    assert h(resultado(archivo="libro.xlsx"), fuentes("C:\\Users\\u\\libro.xlsx")) == base
    assert h(resultado(archivo="libro.xlsx"), fuentes("libro.xlsx", SHA_B)) != base


def test_el_linaje_usa_el_id_de_la_fuente_y_conserva_el_valor_vacio():
    res = resultado(archivo="libro.xlsx")
    res.tables["aetops.linea.yoy"].groups[0].pct["x"] = Value(None, "missing", None, "")
    res.extras["sin_archivo"] = val(archivo="")
    c = pv.canonico(P, fuentes(), res, {})
    v = c["valores"]["tables"]["aetops.linea.yoy"]["groups"][0]["current"]["values"]["monto"]
    assert v["src"]["file"] == "F1" and c["valores"]["extras"]["sin_archivo"]["src"]["file"] == ""
    assert c["valores"]["tables"]["aetops.linea.yoy"]["groups"][0]["pct"]["x"]["src"] is None


def test_un_archivo_que_no_esta_entre_las_fuentes_queda_con_su_nombre_base_sin_ruta():
    c = pv.canonico(P, fuentes(), resultado(archivo="/tmp/ruta/larga/ajeno.xlsx"), {})
    assert c["valores"]["tables"]["aetops.linea.yoy"]["groups"][0]["current"]["values"]["monto"]["src"]["file"] == "ajeno.xlsx"


@pytest.mark.parametrize("a,b", [
    ("Error en /tmp/uno/libro.xlsx: falta la hoja", "Error en /home/otro/dir/libro.xlsx: falta la hoja"),
    ("Falla C:\\Users\\ana\\libro.xlsx.", "Falla D:\\datos\\x\\libro.xlsx."),
    ("Ver \\\\servidor\\carpeta\\libro.xlsx ahora", "Ver \\\\otro\\recurso\\libro.xlsx ahora"),
])
def test_las_rutas_absolutas_en_mensajes_y_evidencia_se_reemplazan_por_su_nombre_base(a, b):
    assert h(resultado(findings=[Finding("X", "warn", a)])) == h(resultado(findings=[Finding("X", "warn", b)]))
    assert h(resultado(findings=[Finding("X", "warn", "m", a)])) == h(resultado(findings=[Finding("X", "warn", "m", b)]))


def test_texto_que_no_es_una_ruta_absoluta_no_se_toca():
    for t in ("ventas/pedidos", "y/o", "12/05/2026", "proporción 3/4", "AE-A/AE-B", "/solo", "a /s b"):
        assert pv.rutas_a_nombre_base(t) == t, t
    assert pv.rutas_a_nombre_base("en /home/u/x/lib.xlsx fin") == "en lib.xlsx fin"
    assert pv.rutas_a_nombre_base("(/tmp/a/b.xlsx)") == "(b.xlsx)"
    assert pv.rutas_a_nombre_base("C:/a/b/c.csv y D:\\q\\r.txt") == "c.csv y r.txt"


def test_la_narrativa_no_pasa_por_la_normalizacion_de_rutas():
    assert h(nar=narr("ver /tmp/a/b.xlsx")) != h(nar=narr("ver /tmp/z/b.xlsx"))     # el texto del reporte se respeta tal cual


def test_los_parrafos_no_visibles_no_entran_al_hash_pero_si_los_visibles():
    base = h(nar=narr("Hola"))
    nota = {"conclusiones": [Para("Hola", "hecho"), Para("nota de calidad de datos", "calidad", visible=False)]}
    assert h(nar=nota) == base
    nota["conclusiones"][1].visible = True
    assert h(nar=nota) != base


def test_los_campos_de_apoyo_del_parrafo_no_entran_al_hash():
    a = {"c": [Para("T", "hecho", priority=0, basis="regla", evidence=["e1"], nums={"1"})]}
    b = {"c": [Para("T", "hecho", priority=9, basis="otra", evidence=[], nums=set())]}
    assert h(nar=a) == h(nar=b)


def test_unicode_se_normaliza_a_nfc_en_textos_y_claves():
    nfc, nfd = "Café Año", unicodedata.normalize("NFD", "Café Año")
    assert nfc != nfd and h(nar=narr(nfc)) == h(nar=narr(nfd))
    assert h(resultado(extras={nfc: 1})) == h(resultado(extras={nfd: 1}))
    assert h(resultado(findings=[Finding("X", "warn", nfc)])) == h(resultado(findings=[Finding("X", "warn", nfd)]))
    assert h(resultado(extras={(nfc, "b"): 1})) == h(resultado(extras={(nfd, "b"): 1}))             # clave-tupla


def test_las_marcas_de_negrita_no_son_contenido_igual_que_en_narrative_json():
    """`texto` es el de narrative.json (sin `**`): un cambio de solo formato no cambia el hash; un cambio de palabras, sí."""
    assert h(nar=narr("Ventas **+26%** y piezas")) == h(nar=narr("Ventas +26% y piezas"))
    assert h(nar=narr("Ventas **+26%** y piezas")) != h(nar=narr("Ventas **+27%** y piezas"))


def test_los_saltos_de_linea_del_texto_no_se_alteran():
    assert h(nar=narr("a\nb")) != h(nar=narr("a\r\nb"))


# ----------------------------------------------------------------------------------------------------------------- robustez
@pytest.mark.parametrize("valor", [
    None, "", 0, -1, 10 ** 30, True, False, Decimal("0"), Decimal("-0.50"), Decimal("1E+2"), [], {}, [[]], {"a": {}},
    {"a": [None, "", 0, False, {"b": []}]}, "ñ 日本語 😀 العربية \u200b\u202e", "tab\tcontrol\x01fin", "comillas \" y \\ y '", "linea\nsalto",
])
def test_valores_de_borde_se_serializan_de_forma_estable(valor):
    r = resultado(extras={"v": valor})
    a, b = h(r), h(copy.deepcopy(r))
    assert a == b
    assert json.loads(pv.serializar(pv.canonico(P, fuentes(), r, {})).decode("utf-8"))                     # JSON válido en UTF-8


def test_distingue_none_cadena_vacia_cero_falso_y_ausente():
    hs = {h(resultado(extras={"v": x})) for x in (None, "", 0, False, [], {})}
    assert len(hs) == 6
    assert h(resultado(extras={"v": None})) != h(resultado(extras={}))                                      # campo ausente != None


def test_enteros_y_decimales_no_se_confunden_con_texto():
    assert h(resultado(extras={"v": 1})) != h(resultado(extras={"v": "1"}))
    assert h(resultado(extras={"v": Decimal("1")})) != h(resultado(extras={"v": 1}))
    assert h(resultado(extras={"v": True})) != h(resultado(extras={"v": 1}))


def test_el_enum_y_la_ruta_se_canonicalizan_sin_depender_del_entorno():
    import enum

    class E(enum.Enum):
        A = "a"
    assert h(resultado(extras={"v": E.A})) == h(resultado(extras={"v": "a"}))
    assert h(resultado(extras={"p": Path("/x/y/z.xlsx")})) == h(resultado(extras={"p": Path("/otro/z.xlsx")}))


def test_sin_narrativa_o_con_seccion_vacia():
    assert pv.canonico(P, fuentes(), resultado(), None)["narrativa"] == {}
    assert pv.canonico(P, fuentes(), resultado(), {"s": []})["narrativa"] == {"s": []}
    assert h(nar={}) != h(nar={"s": []})


def test_sin_fuentes_es_valido():
    c = pv.canonico(P, [], resultado(), {})
    assert c["fuentes"] == [] and pv.hash_resultado(c)["valor"]
    assert pv.canonico(P, None, resultado(), {})["fuentes"] == []


def test_fuentes_con_el_mismo_contenido_son_una_sola_y_los_ids_van_por_sha():
    c = pv.canonico(P, [{"nombre": "x.xlsx", "sha256": SHA_B}, {"nombre": "copia de x.xlsx", "sha256": SHA_B.upper()},
                        {"nombre": "y.xlsx", "sha256": SHA_A}], resultado(), {})
    assert c["fuentes"] == [{"id": "F1", "sha256": SHA_A}, {"id": "F2", "sha256": SHA_B}]


@pytest.mark.parametrize("malas", [
    [{"nombre": "x"}], [{"sha256": SHA_A}], ["x.xlsx"], [{"nombre": "", "sha256": SHA_A}], [{"nombre": 5, "sha256": SHA_A}],
    [{"nombre": "x", "sha256": "corto"}], [{"nombre": "x", "sha256": "g" * 64}], [{"nombre": "x", "sha256": None}],
    [{"nombre": "a/x.xlsx", "sha256": SHA_A}, {"nombre": "b/x.xlsx", "sha256": SHA_B}],     # mismo nombre, contenido distinto: ambiguo
])
def test_fuentes_invalidas_se_rechazan(malas):
    with pytest.raises(pv.ErrorProcedencia):
        pv.canonico(P, malas, resultado(), {})


class _Raro:
    pass


@pytest.mark.parametrize("extra", [
    datetime.datetime(2026, 1, 1), datetime.date(2026, 1, 1), b"bytes", _Raro(), 1 + 2j, range(3), lambda: 1,
    {"a": {1, _Raro()}}, "\ud800",                                      # tipo no previsto / sustituto Unicode suelto (no codificable)
])
def test_tipos_o_textos_no_canonicalizables_son_un_error_y_no_un_hash(extra):
    with pytest.raises(pv.ErrorProcedencia):
        pv.calcular(P, fuentes(), resultado(extras={"v": extra}), {})


def test_profundidad_excesiva_y_ciclos_son_un_error():
    d = {}
    cur = d
    for _ in range(pv.MAX_PROFUNDIDAD + 5):
        cur["x"] = {}
        cur = cur["x"]
    with pytest.raises(pv.ErrorProcedencia):
        pv.calcular(P, fuentes(), resultado(extras=d), {})
    ciclo = {}
    ciclo["yo"] = ciclo
    with pytest.raises(pv.ErrorProcedencia):
        pv.calcular(P, fuentes(), resultado(extras=ciclo), {})
    ok = {}
    cur = ok
    for _ in range(20):
        cur["x"] = {}
        cur = cur["x"]
    assert pv.calcular(P, fuentes(), resultado(extras=ok), {})["valor"]                                    # profundidad razonable: sin problema


def test_colision_de_claves_canonicas_es_un_error():
    with pytest.raises(pv.ErrorProcedencia):
        pv.calcular(P, fuentes(), resultado(extras={1: "a", "1": "b"}), {})
    with pytest.raises(pv.ErrorProcedencia):
        pv.calcular(P, fuentes(), resultado(extras={"é": 1, unicodedata.normalize("NFD", "é"): 2}), {})


@pytest.mark.parametrize("res", [object(), None, "x", {"tables": {}}])
def test_un_resultado_que_no_es_aetops_ni_glp1_es_un_error(res):
    with pytest.raises(pv.ErrorProcedencia):
        pv.canonico(P, fuentes(), res, {})


def test_resultado_glp1_usa_blocks_funnel_extras():
    @dataclasses.dataclass
    class G:
        blocks: dict
        funnel: dict
        extras: dict
        findings: list
    c = pv.canonico(Period("GLP1", "mensual", 2026, 9), fuentes(), G({"b": val()}, {"f": val("2")}, {}, []), {})
    assert sorted(c["valores"]) == ["blocks", "extras", "funnel"]


@pytest.mark.parametrize("periodo", [None, object(), Period("AETOPS", "mensual", "2026", 9), Period("AETOPS", "mensual", 2026, True)])
def test_periodo_invalido_es_un_error(periodo):
    with pytest.raises(pv.ErrorProcedencia):
        pv.canonico(periodo, fuentes(), resultado(), {})


@pytest.mark.parametrize("nar", [
    {"s": "texto suelto"}, {"s": 5}, {"s": [object()]}, {"s": [{"texto": 1, "tipo": "x"}]}, {"s": [{"texto": "t", "tipo": "x", "editado": "si"}]},
    {1: []},
])
def test_narrativa_invalida_es_un_error(nar):
    with pytest.raises(pv.ErrorProcedencia):
        pv.canonico(P, fuentes(), resultado(), nar)


def test_narrativa_con_forma_de_narrative_json_equivale_a_los_parrafos():
    a = {"c": [Para("Hola", "hecho"), Para("oculta", "calidad", visible=False)]}
    b = {"c": [{"texto": "Hola", "tipo": "hecho", "editado": False, "visible_en_diapositiva": True},
               {"texto": "oculta", "tipo": "calidad", "editado": False, "visible_en_diapositiva": False}]}
    assert h(nar=a) == h(nar=b)


def test_un_hallazgo_sin_los_campos_exigidos_es_un_error():
    class Viejo:
        id, severity, message, evidence = "X", "warn", "m", ""
    with pytest.raises(pv.ErrorProcedencia):
        pv.canonico(P, fuentes(), resultado(findings=[Viejo()]), {})


# ----------------------------------------------------------------------------------------------------------------- no altera nada
def test_calcular_no_modifica_ninguna_de_sus_entradas():
    res = resultado(extras={"s": {"b", "a"}, "l": [3, 1], "d": {"z": 1, "a": 2}}, findings=[Finding("X", "warn", "ver /tmp/a/b.xlsx")])
    f = fuentes("/x/y/libro.xlsx")
    nar = {"c": [Para("**Texto** con ñ", "hecho"), Para("oculto", "q", visible=False)]}
    antes = (copy.deepcopy(res), copy.deepcopy(f), copy.deepcopy(nar), copy.deepcopy(P))
    pv.calcular(P, f, res, nar)
    assert (res, f, nar, P) == antes
    assert nar["c"][0].text == "**Texto** con ñ" and res.findings[0].message == "ver /tmp/a/b.xlsx"             # el original conserva sus `**`


def test_huellas_por_bloque_ayudan_a_auditar_que_bloque_cambio():
    base = pv.huellas_por_bloque(pv.canonico(P, fuentes(), resultado(), narr("a")))
    assert list(base) == list(pv.BLOQUES)
    otra = pv.huellas_por_bloque(pv.canonico(P, fuentes(), resultado(), narr("b")))
    assert [b for b in pv.BLOQUES if base[b] != otra[b]] == ["narrativa"]
    otra = pv.huellas_por_bloque(pv.canonico(P, fuentes(sha=SHA_B), resultado(), narr("a")))
    assert [b for b in pv.BLOQUES if base[b] != otra[b]] == ["fuentes"]
    with pytest.raises(pv.ErrorProcedencia):
        pv.huellas_por_bloque({"periodo": {}})


def test_la_serializacion_es_la_documentada():
    c = pv.canonico(P, fuentes(), resultado(), narr("Ñ"))
    b = pv.serializar(c)
    esperado = json.dumps(c, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    assert b == esperado and b"\n" not in b and b'": ' not in b and b", " not in b          # sin espacios ni saltos entre elementos
    assert "Ñ".encode("utf-8") in b                                                 # sin escapes \uXXXX
    assert pv.sha256_hex(b) == hashlib.sha256(b).hexdigest() == pv.hash_resultado(c)["valor"]
    assert list(json.loads(b)) == sorted(pv.BLOQUES)                                  # los cinco bloques del contrato, nada más


# ----------------------------------------------------------------------------------------------------------------- tamaño y pureza
def test_entrada_grande_dentro_de_limites():
    grande = {f"clave{i}": [Decimal(i), "texto largo " * 5, {"n": i, "ok": i % 2 == 0}] for i in range(30000)}
    r = resultado(extras=grande)
    t0 = time.time()
    a = h(r)
    assert time.time() - t0 < 30
    assert a == h(r)


def test_el_modulo_es_puro_solo_biblioteca_estandar_y_no_toca_el_motor_de_reglas():
    codigo = (
        "import sys\n"
        "import backend.app.provenance\n"
        "print(sorted(m for m in sys.modules if m.startswith('backend.app.')))\n"
        "assert not any(m.startswith('backend.app.validator') for m in sys.modules), 'cargó el motor de reglas'\n"
        "assert not any(m.startswith(('backend.app.history', 'backend.app.build', 'backend.app.web', 'backend.app.deck')) for m in sys.modules)\n")
    r = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, cwd=ROOT, env={"PYTHONPATH": str(ROOT), "PATH": "/usr/bin:/bin"})
    assert r.returncode == 0, r.stderr[-500:]
    import ast
    src = (ROOT / "backend/app/provenance.py").read_text(encoding="utf-8")
    prohibidos = {"requests", "urllib", "socket", "http", "subprocess", "os", "shutil", "sqlite3", "datetime", "time", "random", "tempfile", "glob"}
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.Import):
            assert not ({a.name.split(".")[0] for a in n.names} & prohibidos), n.names
        if isinstance(n, ast.ImportFrom):
            assert (n.module or "").split(".")[0] not in prohibidos, n.module
    assert "open(" not in src and ".write" not in src and "environ" not in src


def test_la_fase_3a2_no_adelanta_la_persistencia_ni_el_manifiesto():
    """3A-2 no crea la tabla `procedencia`, no escribe `procedencia.json` y no toca `runs`."""
    from backend.app.history import store
    assert "procedencia" not in store.SCHEMA.lower().replace("procedencia.json", "")
    assert not (ROOT / "backend/app/web" / "procedencia.json").exists()
    build_src = (ROOT / "backend/app/build.py").read_text(encoding="utf-8")
    assert "provenance" not in build_src and "procedencia" not in build_src


# ----------------------------------------------------------------------------------------------------------------- casos límite añadidos en la revisión
def test_serializar_rechaza_lo_que_no_es_json_estricto_en_lugar_de_ocultarlo():
    for malo in ({"a": object()}, {"a": float("nan")}, {"a": float("inf")}, {"a": "\ud800"}, {"a": 10 ** 5000}):
        with pytest.raises(pv.ErrorProcedencia):
            pv.serializar(malo)


def test_las_urls_y_las_fracciones_no_se_confunden_con_rutas():
    for t in ("https://host.com/a/b/c.xlsx", "http://x/y", "ver https://a.b/c/d y luego", "~/a/b", "./a/b", "../a/b", "a/b/c"):
        assert pv.rutas_a_nombre_base(t) == t, t


def test_el_nombre_del_linaje_y_el_de_la_fuente_se_comparan_en_nfc():
    nfd = unicodedata.normalize("NFD", "Reporte ñandú.xlsx")
    a = h(resultado(archivo="Reporte ñandú.xlsx"), fuentes(nfd))
    assert a == h(resultado(archivo=nfd), fuentes("Reporte ñandú.xlsx"))
    c = pv.canonico(P, fuentes(nfd), resultado(archivo="Reporte ñandú.xlsx"), {})
    assert c["valores"]["tables"]["aetops.linea.yoy"]["groups"][0]["current"]["values"]["monto"]["src"]["file"] == "F1"


def test_la_identidad_del_pptx_no_es_una_entrada():
    """El PPTX (su hash binario) no se puede pasar: la API solo recibe periodo, fuentes, resultado y narrativa."""
    import inspect
    assert list(inspect.signature(pv.calcular).parameters) == ["periodo", "fuentes", "resultado", "narrativa"]
    assert list(inspect.signature(pv.canonico).parameters) == ["periodo", "fuentes", "resultado", "narrativa"]


def test_un_historial_anterior_sin_objetos_de_resultado_no_se_puede_hashear_y_no_se_inventa_un_hash():
    """Los reportes anteriores guardaron hallazgos y narrativa como JSON, sin `Value` ni `Lineage`: quedan `no_reproducible (legado)`."""
    legado = {"tables": {}, "findings": [{"id": "X", "severity": "warn", "message": "m"}]}
    with pytest.raises(pv.ErrorProcedencia):
        pv.canonico(P, fuentes(), legado, {})
    with pytest.raises(pv.ErrorProcedencia):
        pv.canonico(P, fuentes(), resultado(findings=[{"id": "X", "severity": "warn", "message": "m"}]), {})
