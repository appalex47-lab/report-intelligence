"""Fase 3A-3 · manifiesto `procedencia.json`: construcción, esquema cerrado, serialización y lectura verificada (funciones puras de `provenance.py`)."""
import json
import unicodedata

import pytest

from backend.app import provenance as pv
from tests.proc_util import SHA_A, SHA_B, manifiesto_valido, mutado

M = manifiesto_valido()


def test_el_manifiesto_valido_tiene_los_nueve_campos_de_la_spec_mas_esquema_y_entorno():
    nueve = {"version_codigo", "version_motor", "version_definiciones", "version_reglas", "version_plantillas", "archivos_fuente",
             "fecha_generacion", "configuracion", "hash_resultado"}
    assert set(M) == nueve | {"esquema", "entorno"} == set(pv.CAMPOS_MANIFIESTO)
    assert M["esquema"] == "procedencia/1" and pv.validar_manifiesto(M) == []


def test_la_serializacion_es_determinista_exacta_y_sin_mutar_el_manifiesto():
    antes = json.dumps(M, sort_keys=True)
    a, b = pv.serializar_manifiesto(M), pv.serializar_manifiesto(json.loads(json.dumps(M)))
    assert a == b and a.endswith(b"}\n") and a.decode("utf-8")
    assert json.loads(a) == M and json.dumps(M, sort_keys=True) == antes
    assert json.dumps(json.loads(a), ensure_ascii=False, indent=1, sort_keys=True).encode() + b"\n" == a            # formato documentado
    assert pv.sha256_hex(a) == pv.sha256_hex(b)


def test_leer_ida_y_vuelta():
    m, errs = pv.leer_manifiesto(pv.serializar_manifiesto(M))
    assert errs == [] and m == M


# ----------------------------------------------------------------------------------------------------------------- esquema cerrado
@pytest.mark.parametrize("ruta", ["esquema", "version_codigo", "version_motor", "version_definiciones", "version_reglas", "version_plantillas",
                                  "archivos_fuente", "fecha_generacion", "configuracion", "hash_resultado", "entorno",
                                  "version_codigo.app", "version_codigo.commit", "version_motor.engine", "version_reglas.ejecucion",
                                  "version_reglas.ejecucion.motor_ejecutado", "version_reglas.catalogo.version", "archivos_fuente.0.sha256",
                                  "archivos_fuente.0.id", "archivos_fuente.0.filas", "fecha_generacion.utc", "configuracion.ia",
                                  "configuracion.contexto.sha256", "hash_resultado.valor", "entorno.python"])
def test_un_campo_obligatorio_ausente_invalida_el_manifiesto(ruta):
    assert pv.validar_manifiesto(mutado(M, ruta, ...))


@pytest.mark.parametrize("ruta", ["", "version_codigo", "version_motor", "version_definiciones", "version_reglas", "version_reglas.catalogo",
                                  "version_reglas.ejecucion", "version_reglas.reglas.0", "version_plantillas.0", "archivos_fuente.0",
                                  "fecha_generacion", "configuracion", "configuracion.contexto", "configuracion.ia", "hash_resultado", "entorno"])
def test_un_campo_adicional_invalida_el_manifiesto(ruta):
    x = mutado(M, "esquema", M["esquema"])
    cur = x
    for p in [p for p in ruta.split(".") if p]:
        cur = cur[int(p)] if isinstance(cur, list) else cur[p]
    cur["extra"] = 1
    errs = pv.validar_manifiesto(x)
    assert errs and any("no previstos" in e for e in errs)


@pytest.mark.parametrize("ruta,valor", [
    ("esquema", "procedencia/2"), ("esquema", "procedencia/0"), ("esquema", ""), ("esquema", None),
    ("version_codigo.app", "1.0"), ("version_codigo.app", "v1.0.0"), ("version_codigo.commit", "abc"), ("version_codigo.commit", "A" * 40),
    ("version_motor.engine", "1.0.0-beta"), ("version_definiciones.version", 1), ("version_reglas.catalogo.version", ""),
    ("version_reglas.reglas.0.regla_version", "x"), ("version_reglas.reglas.0.validacion_sintetica", "quizá"),
    ("version_reglas.reglas.0.validacion_operacional", "confirmada_por_mi"), ("version_reglas.ejecucion.motor_ejecutado", "no"),
    ("version_reglas.ejecucion.flags", {"x": "no"}), ("version_reglas.ejecucion.nota", None),
    ("version_plantillas.0.sha256", "A" * 64), ("version_plantillas.0.sha256", "a" * 63), ("version_plantillas.0.id", ""),
    ("archivos_fuente.0.nombre", "dir/x.xlsx"), ("archivos_fuente.0.nombre", "C:\\x.xlsx"), ("archivos_fuente.0.nombre", ""),
    ("archivos_fuente.0.tamano_bytes", -1), ("archivos_fuente.0.tamano_bytes", True), ("archivos_fuente.0.tamano_bytes", "10"),
    ("archivos_fuente.0.filas", {"ventas": -1}), ("archivos_fuente.0.filas", {"ventas": "3"}), ("archivos_fuente.0.columnas", {"ventas": "a"}),
    ("archivos_fuente.0.periodo_detectado", 5), ("archivos_fuente.0.id", "F2"), ("archivos_fuente.0.id", "f1"),
    ("fecha_generacion.utc", "2026-11-05 12:00:00"), ("fecha_generacion.utc", "2026-11-05T12:00:00+00:00"), ("fecha_generacion.zona_horaria", 3),
    ("configuracion.metas", {"total": 1.5}), ("configuracion.umbrales", []), ("configuracion.contexto.lineas", -1),
    ("configuracion.ia.usada", "si"), ("configuracion.ia.modelo_declarado", 5),
    ("hash_resultado.algoritmo", "md5"), ("hash_resultado.contrato", "otro/1"), ("hash_resultado.valor", "z" * 64),
    ("entorno.python", ""), ("entorno.pyodide", None),
])
def test_valores_invalidos_se_rechazan(ruta, valor):
    assert pv.validar_manifiesto(mutado(M, ruta, valor))


def test_no_puede_haber_resultados_de_reglas_si_el_motor_no_se_ejecuto():
    x = mutado(M, "version_reglas.ejecucion.resultados_incluidos", True)
    assert any("no se ejecutó" in e for e in pv.validar_manifiesto(x))
    ok = mutado(mutado(M, "version_reglas.ejecucion.resultados_incluidos", True), "version_reglas.ejecucion.motor_ejecutado", True)
    assert pv.validar_manifiesto(ok) == []                                           # cuando algún día el motor se ejecute, será válido


def test_ids_de_fuentes_consecutivos_y_ordenados_por_sha_sin_repetidos():
    dos = mutado(M, "archivos_fuente", [{**M["archivos_fuente"][0], "id": "F1", "sha256": SHA_A},
                                        {**M["archivos_fuente"][0], "id": "F2", "sha256": SHA_B, "nombre": "otro.xlsx"}])
    assert pv.validar_manifiesto(dos) == []
    desordenado = mutado(M, "archivos_fuente", [{**M["archivos_fuente"][0], "id": "F1", "sha256": SHA_B},
                                                {**M["archivos_fuente"][0], "id": "F2", "sha256": SHA_A, "nombre": "otro.xlsx"}])
    assert pv.validar_manifiesto(desordenado)
    repetido = mutado(M, "archivos_fuente", [{**M["archivos_fuente"][0], "id": "F1"}, {**M["archivos_fuente"][0], "id": "F2", "nombre": "b.xlsx"}])
    assert pv.validar_manifiesto(repetido)
    assert pv.validar_manifiesto(mutado(M, "archivos_fuente", [])) == []             # sin fuentes es válido (el contrato lo permite)


@pytest.mark.parametrize("malo", [None, [], "x", 5, {}])
def test_un_manifiesto_que_no_es_un_objeto_completo_es_invalido(malo):
    assert pv.validar_manifiesto(malo)


# ----------------------------------------------------------------------------------------------------------------- construir y serializar
def test_construir_rechaza_un_manifiesto_incompleto_o_invalido():
    campos = dict(version_codigo=M["version_codigo"], version_motor=M["version_motor"], version_definiciones=M["version_definiciones"],
                  version_reglas=M["version_reglas"], version_plantillas=M["version_plantillas"], archivos_fuente=M["archivos_fuente"],
                  fecha_generacion=M["fecha_generacion"], configuracion=M["configuracion"], hash_resultado=M["hash_resultado"], entorno=M["entorno"])
    assert pv.construir_manifiesto(**campos) == M
    for k in campos:
        with pytest.raises(pv.ErrorProcedencia):
            pv.construir_manifiesto(**{**campos, k: None})
    with pytest.raises(pv.ErrorProcedencia):
        pv.construir_manifiesto(**{**campos, "version_codigo": {"app": "x", "commit": "desconocido"}})


def test_serializar_no_serializa_un_manifiesto_invalido_ni_demasiado_grande():
    with pytest.raises(pv.ErrorProcedencia):
        pv.serializar_manifiesto(mutado(M, "hash_resultado.valor", "x"))
    with pytest.raises(pv.ErrorProcedencia):
        pv.serializar_manifiesto({})
    enorme = mutado(M, "archivos_fuente.0.columnas", {"ventas": ["c" * 100] * 30000})
    with pytest.raises(pv.ErrorProcedencia):
        pv.serializar_manifiesto(enorme)


def test_los_textos_se_guardan_en_nfc_y_unicode_es_estable():
    nfd = unicodedata.normalize("NFD", "ñandú café.xlsx")
    m = mutado(M, "archivos_fuente.0.nombre", nfd)
    datos = pv.serializar_manifiesto(m)
    assert unicodedata.normalize("NFC", "ñandú café.xlsx").encode("utf-8") in datos and nfd.encode("utf-8") not in datos
    leido, errs = pv.leer_manifiesto(datos)
    assert errs == [] and leido["archivos_fuente"][0]["nombre"] == "ñandú café.xlsx"
    raro = mutado(M, "archivos_fuente.0.nombre", "日本語 😀 العربية ☃.xlsx")
    assert pv.leer_manifiesto(pv.serializar_manifiesto(raro))[0]["archivos_fuente"][0]["nombre"] == "日本語 😀 العربية ☃.xlsx"


def test_dos_claves_que_coinciden_en_nfc_son_un_error():
    m = mutado(M, "archivos_fuente.0.filas", {"é": 1, unicodedata.normalize("NFD", "é"): 2})
    with pytest.raises(pv.ErrorProcedencia):
        pv.serializar_manifiesto(m)


# ----------------------------------------------------------------------------------------------------------------- lectura de bytes corruptos
BUENO = pv.serializar_manifiesto(M)


@pytest.mark.parametrize("datos", [
    BUENO[:-5], BUENO[: len(BUENO) // 2], b"", b"\n", b"no es json", b"[]", b"null", b"{}", BUENO + b"basura", b"\xff\xfe\x00" + BUENO,
    BUENO.replace(b"procedencia/1", b"procedencia/9"), BUENO.replace(b'"esquema"', b'"Esquema"'), BUENO.replace(b"1.0.0", b"x.y.z", 1),
    b'{"esquema": "procedencia/1", "esquema": "procedencia/1"}', BUENO.replace(b"}", b',"extra": 1}', 1) if False else b'{"a": NaN}',
    b'{"a": Infinity}', b"[" * 5000 + b"]" * 5000, b'{"a": ' + b"[" * 3000 + b"]" * 3000 + b"}",
])
def test_bytes_corruptos_o_invalidos_se_rechazan_sin_lanzar(datos):
    m, errs = pv.leer_manifiesto(datos)
    assert m is None and errs


def test_leer_rechaza_claves_repetidas_nan_y_exceso_de_tamano():
    dup = BUENO.replace(b'"esquema": "procedencia/1"', b'"esquema": "procedencia/1",\n "esquema": "procedencia/1"', 1)
    assert pv.leer_manifiesto(dup)[0] is None
    assert pv.leer_manifiesto(b"x" * (pv.MAX_MANIFIESTO_BYTES + 1))[0] is None
    assert pv.leer_manifiesto("texto")[0] is None and pv.leer_manifiesto(None)[0] is None                       # solo bytes
    assert pv.leer_manifiesto(bytearray(BUENO))[0] == M


def test_leer_rechaza_un_campo_adicional_en_los_bytes():
    x = json.loads(BUENO)
    x["campo_nuevo"] = 1
    m, errs = pv.leer_manifiesto(json.dumps(x).encode())
    assert m is None and any("no previstos" in e for e in errs)
