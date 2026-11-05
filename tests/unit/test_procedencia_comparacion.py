"""Fase 3A-4 · `provenance.comparar` (pura): criterios C1 a C7 y estados de la spec §3.2. T-08, PR-10, PR-11, AC-11, AC-12."""
import copy
import json

import pytest

from backend.app import provenance as pv
from tests.proc_util import SHA_A, SHA_B, manifiesto_valido, mutado

SHA_C = "c" * 64                                           # distinto del hash registrado (SHA_A)

M = manifiesto_valido()
HASH = M["hash_resultado"]["valor"]
FUENTES = [{"nombre": "input.xlsx", "sha256": SHA_B}]


def verif(registro="presente", copia="integra", codigos=(), error=None, detalle=()):
    return {"run_id": 1, "registro": {"estado": registro, "detalle": list(detalle), "esquema": "procedencia/1", "manifiesto_sha256": "c" * 64,
                                      "hash_resultado": HASH, "codigos": list(codigos)},
            "copia": {"estado": copia, "detalle": ["detalle de la copia"]}, "error_de_generacion": error,
            "integridad": "verificada" if registro == "presente" else "ausente"}


def igual(m=M):
    return {k: copy.deepcopy(m[k]) for k in pv.ACTUAL_CAMPOS}


def cmp(**kw):
    base = dict(verificacion=verif(), registrado=M, actual=igual(), fuentes_aportadas=FUENTES, regeneracion={"hash_resultado": HASH})
    base.update(kw)
    return pv.comparar(**base)


def pasa(r, *ids):
    return all(r["comprobaciones"][i]["resultado"] == "pasa" for i in ids)


# ------------------------------------------------------------------------------------------------------------------- exacta
def test_todo_igual_y_regeneracion_real_con_el_mismo_hash_es_exacta():
    r = cmp()
    assert r["estado"] == "exacta" and r["causa"] == pv.IGUALDAD_CANONICA and r["diferencias"] == [] and r["alertas"] == []
    assert pasa(r, *pv.COMPROBACIONES) and r["regeneracion"] == {"ejecutada": True, "hash_registrado": HASH, "hash_regenerado": HASH, "error": None}
    assert "canónico" in r["causa"] and "binaria ni visual" in r["causa"]


def test_pr11_sin_regeneracion_nunca_es_exacta():
    r = cmp(regeneracion=None)
    assert r["estado"] == "no_evaluada" and r["estado"] != "exacta" and r["comprobaciones"]["C7"]["resultado"] == "no_evaluada"
    assert pasa(r, "C1", "C2", "C3a", "C3b", "C4", "C5", "C6")


def test_pr10_diferencia_de_entorno_es_nota_y_no_cambia_el_estado_ni_afirma_igualdad_binaria():
    a = igual()
    a["entorno"] = {"pyodide": "0.28.0", "python": "3.13.1", "python_pptx": "1.0.2"}
    r = cmp(actual=a)
    assert r["estado"] == "exacta" and r["diferencias"] == []
    assert len(r["notas"]) == 2 and all(n.startswith("entorno:") for n in r["notas"])
    assert any("binaria ni visual" in x for x in r["alertas"])


def test_exacta_solo_cuando_se_cumplen_todos_los_criterios():
    """Cada criterio, quitado uno a uno, impide «exacta»."""
    casos = {
        "C1": dict(verificacion=verif(registro="ausente", copia="ausente")),
        "C2": dict(verificacion=verif(registro="corrupto", codigos=["sha"])),
        "C3a": dict(fuentes_aportadas=[]),
        "C3b": dict(fuentes_aportadas=[{"nombre": "input.xlsx", "sha256": SHA_A}]),
        "C4": dict(actual={**igual(), "version_plantillas": [{"id": "aetops-mensual/1", "nombre": "t.pptx", "sha256": SHA_B}]}),
        "C5": dict(actual={**igual(), "version_codigo": {"app": "1.0.0", "commit": "1" * 40}}),
        "C6": dict(actual={**igual(), "version_motor": {"engine": "1.1.0"}}),
        "C7": dict(regeneracion={"hash_resultado": SHA_C}),
    }
    for clave, kw in casos.items():
        r = cmp(**kw)
        assert r["estado"] != "exacta", clave
        assert r["estado"] in ("parcial", "no_reproducible"), clave


# ------------------------------------------------------------------------------------------------------------------- no_reproducible
@pytest.mark.parametrize("v,causa", [
    (verif(registro="ausente", copia="ausente"), "legado"),
    (verif(registro="ausente", copia="ausente", error={"etapa": "archivo"}), "error al generarla"),
    (verif(registro="ausente", copia="invalida"), "no es válida"),
    (verif(registro="esquema_no_soportado", detalle=["esquema 'procedencia/2'"]), "esquema"),
    (verif(registro="corrupto", codigos=["sha"], detalle=["sha"]), "alterado"),
    (verif(registro="corrupto", codigos=["invalido"], detalle=["x"]), "alterado"),
    (verif(registro="ilegible", detalle=["no se pudo leer la base"]), "historial"),
    (verif(registro="presente", copia="alterada"), "copia"),
])
def test_c1_o_c2_fallan_son_no_reproducible_con_su_causa_exacta(v, causa):
    r = cmp(verificacion=v)
    assert r["estado"] == "no_reproducible" and causa in r["causa"]
    assert r["comprobaciones"]["C1"]["resultado"] == "falla" or r["comprobaciones"]["C2"]["resultado"] == "falla"
    assert r["regeneracion"]["ejecutada"] is False                         # no se mira la regeneración si la evidencia no es válida


def test_error_de_generacion_nunca_es_parcial_ni_exacta_e4():
    r = cmp(verificacion=verif(registro="ausente", copia="ausente", error={"etapa": "historial"}), registrado=None)
    assert r["estado"] == "no_reproducible"


def test_c3b_una_fuente_aportada_distinta_es_no_reproducible_aunque_falten_otras_cosas():
    r = cmp(fuentes_aportadas=[{"nombre": "input.xlsx", "sha256": SHA_A}], actual={**igual(), "version_motor": {"engine": "9.9.9"}})
    assert r["estado"] == "no_reproducible" and "difiere" in r["causa"]
    assert any(d["componente"] == "archivos_fuente.F1.sha256" and d["actual"] == SHA_A for d in r["diferencias"])


def test_c3b_un_archivo_aportado_que_no_corresponde_a_ninguna_fuente_es_no_reproducible():
    r = cmp(fuentes_aportadas=FUENTES + [{"nombre": "extra.xlsx", "sha256": SHA_A}])
    assert r["estado"] == "no_reproducible" and r["comprobaciones"]["C3b"]["resultado"] == "falla"


def test_c3b_aportar_a_la_vez_la_fuente_original_y_otra_con_el_mismo_nombre_pero_otro_contenido_no_es_exacta():
    r = cmp(fuentes_aportadas=FUENTES + [{"nombre": "input.xlsx", "sha256": SHA_A}])
    assert r["estado"] == "no_reproducible" and r["comprobaciones"]["C3b"]["resultado"] == "falla"


def test_c3_el_contenido_manda_no_el_nombre():
    r = cmp(fuentes_aportadas=[{"nombre": "renombrado.xlsx", "sha256": SHA_B}])
    assert r["estado"] == "exacta"


# ------------------------------------------------------------------------------------------------------------------- parcial
def test_c3a_fuente_no_aportada_es_parcial_y_lista_la_diferencia():
    r = cmp(fuentes_aportadas=[], regeneracion=None)
    assert r["estado"] == "parcial" and r["comprobaciones"]["C3a"]["resultado"] == "falla" and "C3a" in r["causa"]
    assert {"componente": "archivos_fuente.F1", "registrado": SHA_B, "actual": "‹ausente›", "motivo": "no aportado"} in r["diferencias"]


def test_fuentes_no_entregadas_equivale_a_no_aportadas():
    assert cmp(fuentes_aportadas=None, regeneracion=None)["estado"] == "parcial"


@pytest.mark.parametrize("campo,valor,componente", [
    ("version_plantillas", [{"id": "aetops-mensual/1", "nombre": "template.pptx", "sha256": SHA_B}], "version_plantillas[0].sha256"),
    ("version_plantillas", [{"id": "aetops-mensual/2", "nombre": "template.pptx", "sha256": SHA_A}], "version_plantillas[0].id"),
    ("version_codigo", {"app": "1.0.1", "commit": "0" * 40}, "version_codigo.app"),
    ("version_codigo", {"app": "1.0.0", "commit": "1" * 40}, "version_codigo.commit"),
    ("version_motor", {"engine": "1.0.1"}, "version_motor.engine"),
    ("version_definiciones", {"archivo": "definiciones.json", "version": "2.0.0"}, "version_definiciones.version"),
])
def test_c4_c5_c6_una_version_distinta_es_parcial_con_la_diferencia_exacta(campo, valor, componente):
    a = igual()
    a[campo] = valor
    r = cmp(actual=a)
    assert r["estado"] == "parcial" and any(d["componente"] == componente for d in r["diferencias"]), r["diferencias"]


def test_c6_cambios_en_reglas_y_configuracion_se_listan_hoja_por_hoja():
    a = igual()
    a["version_reglas"]["catalogo"]["version"] = "9.0.0"
    a["version_reglas"]["reglas"][0]["regla_version"] = "2.0.0"
    a["configuracion"]["metas"]["total"] = "999"
    a["configuracion"]["umbrales"]["nuevo_umbral"] = "1"
    a["configuracion"]["ia"]["usada"] = True
    r = cmp(actual=a, regeneracion=None)
    comps = {d["componente"] for d in r["diferencias"]}
    assert r["estado"] == "parcial"
    assert {"version_reglas.catalogo.version", "version_reglas.reglas[0].regla_version", "configuracion.metas.total",
            "configuracion.umbrales.nuevo_umbral", "configuracion.ia.usada"} <= comps
    assert next(d for d in r["diferencias"] if d["componente"] == "configuracion.umbrales.nuevo_umbral")["registrado"] == "‹ausente›"


@pytest.mark.parametrize("commit_reg,commit_act", [("desconocido", "desconocido"), ("0" * 40 + "+dirty", "0" * 40 + "+dirty"), ("0" * 40, "desconocido"),
                                                    ("0" * 40, "0" * 40 + "+dirty")])
def test_c5_un_commit_desconocido_o_dirty_no_demuestra_el_mismo_codigo_aunque_sean_iguales(commit_reg, commit_act):
    m = mutado(M, "version_codigo.commit", commit_reg)
    a = {**igual(m), "version_codigo": {"app": "1.0.0", "commit": commit_act}}
    r = cmp(registrado=m, actual=a)
    assert r["estado"] == "parcial" and r["comprobaciones"]["C5"]["resultado"] == "falla"


def test_a05_la_ausencia_de_evidencia_actual_nunca_es_coincidencia():
    for campo in pv.ACTUAL_CAMPOS:
        a = igual()
        a[campo] = None
        r = cmp(actual=a)
        if campo == "entorno":
            assert r["estado"] == "exacta"                                 # el entorno es solo informativo
        else:
            assert r["estado"] == "parcial", campo
            assert any(d["actual"] == "‹ausente›" and d["motivo"] == "sin evidencia actual" for d in r["diferencias"]), campo
    assert cmp(actual=None)["estado"] == "parcial"


def test_db_sin_registro_y_copia_valida_es_como_maximo_parcial_aunque_todo_coincida():
    r = cmp(verificacion=verif(registro="ausente", copia="sin_registro"))
    assert r["estado"] == "parcial" and "D-B" in r["causa"] and r["comprobaciones"]["C2"]["resultado"] == "no_evaluada"
    assert r["regeneracion"]["ejecutada"] is True and r["regeneracion"]["hash_regenerado"] == HASH       # la evidencia se conserva, pero no eleva el estado


def test_anomalia_de_determinismo_c1_a_c6_pasan_y_c7_falla():
    r = cmp(regeneracion={"hash_resultado": SHA_C})
    assert r["estado"] == "parcial" and "anomalía de determinismo" in r["causa"] and pasa(r, "C1", "C2", "C3a", "C3b", "C4", "C5", "C6")
    assert r["comprobaciones"]["C7"]["resultado"] == "falla"
    assert any("anomalía de determinismo" in x and "entradas no registradas" in x for x in r["alertas"])
    assert {"componente": "hash_resultado.valor", "registrado": HASH, "actual": SHA_C, "motivo": "difiere"} in r["diferencias"]


def test_la_anomalia_senala_el_entorno_como_primera_sospecha_cuando_difiere():
    a = igual()
    a["entorno"]["python"] = "3.99.0"
    r = cmp(actual=a, regeneracion={"hash_resultado": SHA_C})
    assert r["estado"] == "parcial" and any("diferencia de entorno" in x for x in r["alertas"])


def test_a08_un_contrato_de_hash_distinto_al_actual_se_rechaza_como_manifiesto_invalido_y_no_se_compara():
    m = mutado(M, "hash_resultado.contrato", "resultado_canonico/0")
    r = cmp(registrado=m, actual=igual(m))
    assert r["estado"] == "no_reproducible" and "manifiesto válido" in r["causa"]


# ------------------------------------------------------------------------------------------------------------------- regeneración fallida
@pytest.mark.parametrize("regen", [{"error": "ValueError: boom"}, {"hash_resultado": "no es un hash"}, {"hash_resultado": None}, {}, "texto", 5, []])
def test_a09_una_regeneracion_fallida_o_invalida_nunca_es_exito(regen):
    r = cmp(regeneracion=regen)
    assert r["estado"] == "no_evaluada" and r["comprobaciones"]["C7"]["resultado"] == "error" and r["regeneracion"]["error"]
    assert r["regeneracion"]["hash_regenerado"] is None


def test_el_mensaje_de_error_de_regeneracion_no_filtra_rutas():
    r = cmp(regeneracion={"error": "FileNotFoundError: /home/usuario/secreto/libro.xlsx"})
    assert "/home/usuario" not in json.dumps(r) and "libro.xlsx" in r["regeneracion"]["error"]


# ------------------------------------------------------------------------------------------------------------------- precedencia y orden
def test_el_orden_de_la_spec_gana_la_primera_fila():
    # C2 falla + C3a falla + C7 distinto → no_reproducible (no parcial)
    r = cmp(verificacion=verif(registro="corrupto", codigos=["sha"]), fuentes_aportadas=[], regeneracion={"hash_resultado": SHA_A})
    assert r["estado"] == "no_reproducible"
    # C3b + C4 → no_reproducible
    r = cmp(fuentes_aportadas=[{"nombre": "input.xlsx", "sha256": SHA_A}], actual={**igual(), "version_plantillas": []})
    assert r["estado"] == "no_reproducible"
    # C4 + C7 → parcial
    r = cmp(actual={**igual(), "version_plantillas": []}, regeneracion={"hash_resultado": SHA_A})
    assert r["estado"] == "parcial"


def test_una_regeneracion_con_hash_igual_no_eleva_un_estado_parcial():
    a = igual()
    a["version_motor"] = {"engine": "2.0.0"}
    assert cmp(actual=a)["estado"] == "parcial"


# ------------------------------------------------------------------------------------------------------------------- determinismo y auditoría
def test_a02_la_comparacion_es_determinista_y_serializable():
    a, b = cmp(), cmp()
    assert a == b and pv.serializar_comparacion(a) == pv.serializar_comparacion(b)
    sucia = cmp(actual={**igual(), "version_motor": {"engine": "1.1.0"}}, fuentes_aportadas=[])
    assert pv.serializar_comparacion(sucia) == pv.serializar_comparacion(cmp(actual={**igual(), "version_motor": {"engine": "1.1.0"}}, fuentes_aportadas=[]))
    assert json.loads(pv.serializar_comparacion(sucia))["esquema"] == "comparacion/1"


def test_a10_la_evidencia_conserva_lo_necesario_para_auditar():
    r = cmp(actual={**igual(), "version_motor": {"engine": "1.1.0"}})
    assert set(r) == {"esquema", "estado", "causa", "comprobaciones", "diferencias", "notas", "alertas", "regeneracion", "evidencia"}
    assert set(r["comprobaciones"]) == set(pv.COMPROBACIONES)
    assert r["evidencia"] == {"run_id": 1, "manifiesto_sha256": "c" * 64, "integridad": "verificada", "copia": "integra"}
    assert r["diferencias"][0] == {"componente": "version_motor.engine", "registrado": "1.0.0", "actual": "1.1.0", "motivo": "difiere"}


def test_comparar_no_modifica_sus_argumentos():
    v, m, a, f = verif(), copy.deepcopy(M), igual(), copy.deepcopy(FUENTES)
    antes = copy.deepcopy((v, m, a, f))
    pv.comparar(verificacion=v, registrado=m, actual=a, fuentes_aportadas=f, regeneracion={"hash_resultado": SHA_A})
    assert (v, m, a, f) == antes


def test_valores_largos_se_recortan_en_las_diferencias():
    a = igual()
    a["configuracion"]["metas"]["total"] = "9" * 5000
    d = next(x for x in cmp(actual=a, regeneracion=None)["diferencias"] if x["componente"] == "configuracion.metas.total")
    assert len(d["actual"]) <= pv.MAX_VALOR_DIFF + 1


# ------------------------------------------------------------------------------------------------------------------- entradas inválidas
def test_argumentos_invalidos_se_rechazan_sin_clasificar():
    with pytest.raises(pv.ErrorProcedencia):
        pv.comparar(verificacion={}, registrado=M, actual=igual(), fuentes_aportadas=FUENTES)
    with pytest.raises(pv.ErrorProcedencia, match="campos desconocidos"):
        pv.comparar(verificacion=verif(), registrado=M, actual={**igual(), "extra": 1}, fuentes_aportadas=FUENTES)
    with pytest.raises(pv.ErrorProcedencia):
        pv.serializar_comparacion({"esquema": "otro"})


def test_manifiesto_ausente_o_invalido_con_registro_presente_no_se_compara():
    for malo in (None, {}, {"esquema": "procedencia/1"}, mutado(M, "hash_resultado.valor", "corto")):
        r = cmp(registrado=malo)
        assert r["estado"] == "no_reproducible" and "manifiesto válido" in r["causa"]


def test_el_modulo_sigue_siendo_puro():
    import ast
    import pathlib
    src = (pathlib.Path(pv.__file__)).read_text(encoding="utf-8")
    prohibidos = {"requests", "urllib", "socket", "subprocess", "os", "shutil", "sqlite3", "datetime", "time", "random", "tempfile", "glob"}
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.Import):
            assert not ({a.name.split(".")[0] for a in n.names} & prohibidos), n.names
        if isinstance(n, ast.ImportFrom):
            assert (n.module or "").split(".")[0] not in prohibidos, n.module
