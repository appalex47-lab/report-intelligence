"""Fase 3A-4 · revisión correctiva del PR #20: I-1 (copia vs registro), I-2 (fuentes aportadas), I-3 (reproducibilidad / evaluación / regeneración)
e I-4 (resultado de la comparación sin persistencia)."""
import copy
import json
import sqlite3

import pytest

from backend.app import provenance as pv
from backend.app import provenance_capture as cap
from backend.app import provenance_compare as cmpm
from backend.app import version
from tests.proc_util import P, SHA_A, SHA_B, capturar, libro, manifiesto_valido, mutado, narrativa, resultado
from tests.unit.test_procedencia_comparacion import FUENTES, HASH, M, SHA_C, cmp, igual, verif

COMMIT = "a" * 40


@pytest.fixture(autouse=True)
def commit_estampado(monkeypatch):
    monkeypatch.setattr(version, "commit", lambda: COMMIT)


@pytest.fixture
def caso(tmp_path):
    out, carpeta, db = capturar(tmp_path)
    return dict(tmp=tmp_path, out=out, carpeta=carpeta, db=db, run_id=out["run_id"], fuente=tmp_path / "input.xlsx",
                tpl=tmp_path / "templates" / "aetops-mensual" / "1" / "template.pptx")


def regen_ok(c):
    return lambda f, s: cap.construir(period=P, result=resultado(), narrative=narrativa("Hola"), sources=[c["fuente"]], template=c["tpl"])[0]["hash_resultado"]["valor"]


def ev(c, **kw):
    base = dict(carpeta=c["carpeta"], fuentes=[c["fuente"]], template=c["tpl"], regenerar=regen_ok(c))
    base.update(kw)
    return cmpm.evaluar(c["db"], c["run_id"], **base)


def _romper_registro(db, sql, *p):
    con = sqlite3.connect(db)
    con.execute("DROP TRIGGER IF EXISTS procedencia_no_update")
    con.execute(sql, p)
    con.commit()
    con.close()


# ================================================================================================================ I-1
class TestI1CopiaVsRegistro:
    """El manifiesto que se compara es SIEMPRE el del registro autoritativo; la copia solo se usa para C2 (spec §3.1: bytes de procedencia.json
    frente a `manifiesto_sha256`). Ninguna copia o registro alterado, ni evidencia contradictoria, puede dar «exacta»."""

    def test_original_intacto(self, caso):
        r = ev(caso)
        assert r["estado"] == "exacta" and r["evidencia"]["integridad"] == "verificada" and r["evidencia"]["copia"] == "integra"

    def test_copia_alterada_registro_integro(self, caso):
        p = caso["carpeta"] / "procedencia.json"
        p.write_bytes(p.read_bytes().replace(b"input.xlsx", b"falso.xlsx"))
        r = ev(caso)
        assert r["estado"] == "no_reproducible" and r["comprobaciones"]["C2"]["resultado"] == "falla"
        assert "el registro autoritativo está íntegro" in r["causa"] and r["evidencia"]["manifiesto_sha256"] == caso["out"]["manifiesto_sha256"]
        assert r["evidencia"]["copia"] == "alterada" and r["regeneracion"]["estado"] == "no_ejecutada"

    def test_registro_alterado_copia_intacta_la_copia_no_lo_rescata(self, caso):
        _romper_registro(caso["db"], "UPDATE procedencia SET manifiesto = replace(manifiesto, 'input.xlsx', 'falso.xlsx')")
        r = ev(caso)
        assert r["estado"] == "no_reproducible" and r["comprobaciones"]["C2"]["resultado"] == "falla" and r["evidencia"]["integridad"] == "fallida"

    def test_ambos_alterados(self, caso):
        _romper_registro(caso["db"], "UPDATE procedencia SET manifiesto = replace(manifiesto, 'input.xlsx', 'falso.xlsx')")
        p = caso["carpeta"] / "procedencia.json"
        p.write_bytes(p.read_bytes().replace(b"input.xlsx", b"falso.xlsx"))     # incluso si la copia coincide con el registro manipulado
        r = ev(caso)
        assert r["estado"] == "no_reproducible" and r["comprobaciones"]["C2"]["resultado"] == "falla"

    def test_ambos_alterados_y_coherentes_entre_si_con_sha_recalculado(self, caso):
        """Un atacante que reescribe registro, sha y copia a la vez: el sha de la fila ya no es el del reporte original, pero internamente es
        coherente. Se acepta como registro íntegro (la integridad del historial es detectable, no criptográfica: límite documentado) PERO la
        comparación contra las fuentes reales delata el cambio."""
        alterado = (caso["carpeta"] / "procedencia.json").read_bytes().replace(b"input.xlsx", b"falso.xlsx")
        _romper_registro(caso["db"], "UPDATE procedencia SET manifiesto=?, manifiesto_sha256=?", alterado.decode(), pv.sha256_hex(alterado))
        (caso["carpeta"] / "procedencia.json").write_bytes(alterado)
        r = ev(caso)
        assert r["estado"] != "exacta" or r["regeneracion"]["hash_regenerado"] == r["regeneracion"]["hash_registrado"]    # nunca exacta por accidente
        _romper_registro(caso["db"], "UPDATE procedencia SET hash_resultado=?", "f" * 64)
        assert ev(caso)["estado"] == "no_reproducible"                             # y si el hash de la fila ya no coincide con el del manifiesto, se detecta

    def test_informacion_contradictoria_copia_valida_de_otra_corrida(self, caso, tmp_path):
        otra_dir = tmp_path / "otra"
        otra_dir.mkdir()
        out2, carpeta2, _ = capturar(otra_dir, db=False, resultado_=resultado(x="999"))
        assert out2["hash_resultado"] != caso["out"]["hash_resultado"]
        (caso["carpeta"] / "procedencia.json").write_bytes((carpeta2 / "procedencia.json").read_bytes())      # copia VÁLIDA pero contradictoria
        r = ev(caso)
        assert r["estado"] == "no_reproducible" and r["evidencia"]["copia"] == "alterada"

    def test_copia_ausente_no_impide_comparar_con_el_registro(self, caso):
        (caso["carpeta"] / "procedencia.json").unlink()
        r = ev(caso)
        assert r["estado"] == "exacta" and r["evidencia"]["copia"] == "ausente"

    def test_registro_ausente_con_copia_valida_es_a_lo_sumo_parcial(self, caso):
        r = cmpm.evaluar(caso["tmp"] / "no_hay.sqlite", caso["run_id"], carpeta=caso["carpeta"], fuentes=[caso["fuente"]], template=caso["tpl"],
                         regenerar=regen_ok(caso))
        assert r["estado"] == "parcial" and "D-B" in r["causa"]

    def test_registro_y_copia_ausentes(self, caso):
        (caso["carpeta"] / "procedencia.json").unlink()
        r = cmpm.evaluar(caso["tmp"] / "no_hay.sqlite", caso["run_id"], carpeta=caso["carpeta"], fuentes=[caso["fuente"]], template=caso["tpl"],
                         regenerar=regen_ok(caso))
        assert r["estado"] == "no_reproducible" and r["regeneracion"]["estado"] == "no_ejecutada"

    def test_la_evidencia_explica_el_resultado(self, caso):
        p = caso["carpeta"] / "procedencia.json"
        p.write_bytes(p.read_bytes() + b"\n")
        r = ev(caso)
        assert r["comprobaciones"]["C2"]["detalle"] and r["evidencia"] == {"run_id": caso["run_id"], "manifiesto_sha256": caso["out"]["manifiesto_sha256"],
                                                                           "integridad": "verificada", "copia": "alterada"}


# ================================================================================================================ I-2
M2 = None


def _manifiesto_dos_fuentes():
    f1 = {"id": "F1", "nombre": "a.xlsx", "tamano_bytes": 1, "sha256": "1" * 64, "filas": {"ventas": 1}, "columnas": {"ventas": ["fecha_pedido"]},
          "periodo_detectado": None}
    f2 = {**f1, "id": "F2", "nombre": "b.xlsx", "sha256": "2" * 64}
    return mutado(M, "archivos_fuente", [f1, f2])


class TestI2FuentesAportadas:
    def test_todas_las_fuentes_registradas_presentes(self):
        m = _manifiesto_dos_fuentes()
        r = cmp(registrado=m, actual=igual(m), fuentes_aportadas=[{"nombre": "a.xlsx", "sha256": "1" * 64}, {"nombre": "b.xlsx", "sha256": "2" * 64}])
        assert r["estado"] == "exacta"

    def test_fuente_registrada_ausente(self):
        m = _manifiesto_dos_fuentes()
        r = cmp(registrado=m, actual=igual(m), fuentes_aportadas=[{"nombre": "a.xlsx", "sha256": "1" * 64}])
        assert r["estado"] == "parcial" and r["comprobaciones"]["C3a"]["resultado"] == "falla" and r["regeneracion"]["estado"] == "completada"

    def test_fuente_adicional_no_registrada(self):
        r = cmp(fuentes_aportadas=FUENTES + [{"nombre": "auxiliar.xlsx", "sha256": SHA_C}])
        assert r["estado"] == "no_reproducible" and "no corresponde" in " ".join(r["comprobaciones"]["C3b"]["detalle"])

    def test_dos_archivos_con_el_mismo_nombre_y_contenido_diferente(self):
        r = cmp(fuentes_aportadas=[{"nombre": "input.xlsx", "sha256": SHA_B}, {"nombre": "input.xlsx", "sha256": SHA_C}])
        assert r["estado"] == "no_reproducible"                      # el segundo NO se ignora aunque el primero sea la fuente registrada
        r = cmp(fuentes_aportadas=[{"nombre": "input.xlsx", "sha256": SHA_A}, {"nombre": "input.xlsx", "sha256": SHA_C}])
        assert r["estado"] == "no_reproducible"                      # ninguno es la registrada

    def test_dos_archivos_con_contenido_identico_y_nombres_distintos(self):
        r = cmp(fuentes_aportadas=[{"nombre": "input.xlsx", "sha256": SHA_B}, {"nombre": "copia.xlsx", "sha256": SHA_B}])
        assert r["estado"] == "exacta"                                # el contenido manda; ambos son la misma fuente

    def test_archivo_sustituido(self):
        r = cmp(fuentes_aportadas=[{"nombre": "input.xlsx", "sha256": SHA_C}])
        assert r["estado"] == "no_reproducible" and any(d["motivo"] == "contenido distinto" for d in r["diferencias"])
        r = cmp(fuentes_aportadas=[{"nombre": "otro_nombre.xlsx", "sha256": SHA_C}])          # sustituido y además renombrado
        assert r["estado"] == "no_reproducible"

    def test_fuentes_repetidas(self):
        r = cmp(fuentes_aportadas=FUENTES * 3)
        assert r["estado"] == "exacta"

    def test_varias_fuentes_legitimas_en_cualquier_orden(self):
        m = _manifiesto_dos_fuentes()
        a, b = {"nombre": "a.xlsx", "sha256": "1" * 64}, {"nombre": "b.xlsx", "sha256": "2" * 64}
        r1 = cmp(registrado=m, actual=igual(m), fuentes_aportadas=[a, b])
        r2 = cmp(registrado=m, actual=igual(m), fuentes_aportadas=[b, a])
        assert r1["estado"] == r2["estado"] == "exacta" and pv.serializar_comparacion(r1) == pv.serializar_comparacion(r2)

    def test_ningun_archivo_distinto_se_ignora_en_silencio(self):
        """Barrido: cada archivo extra, con cualquier nombre (nuevo, igual a una fuente registrada o repetido), impide «exacta»."""
        for extra in ({"nombre": "input.xlsx", "sha256": SHA_C}, {"nombre": "nuevo.xlsx", "sha256": SHA_C}, {"nombre": "", "sha256": SHA_C},
                      {"nombre": "input.xlsx ", "sha256": SHA_C}):
            r = cmp(fuentes_aportadas=FUENTES + [extra])
            assert r["estado"] != "exacta", extra

    def test_no_hay_un_flujo_legitimo_con_archivos_auxiliares(self, caso):
        """El reporte se genera siempre con UNA fuente (el libro cargado, `input.xlsx`): el contexto del equipo es texto (solo su SHA entra
        en `configuracion`) y las plantillas se comparan aparte (C4). No hay archivos auxiliares que acompañen a las fuentes registradas, así que
        aportar uno es una discrepancia y no un flujo legítimo."""
        m = pv.leer_manifiesto((caso["carpeta"] / "procedencia.json").read_bytes())[0]
        assert [f["nombre"] for f in m["archivos_fuente"]] == ["input.xlsx"]

    def test_evaluar_solo_entrega_a_la_regeneracion_las_fuentes_verificadas(self, caso):
        copia = caso["tmp"] / "copia_exacta.xlsx"
        copia.write_bytes(caso["fuente"].read_bytes())
        recibido = []

        def regen(f, s):
            recibido.append((list(f), list(s)))
            return regen_ok(caso)(f, s)
        r = ev(caso, fuentes=[caso["fuente"], copia, caso["fuente"]], regenerar=regen)
        assert r["estado"] == "exacta" and len(recibido) == 1
        rutas, shas = recibido[0]
        assert len(rutas) == 1
        assert shas == [pv.leer_manifiesto((caso["carpeta"] / "procedencia.json").read_bytes())[0]["archivos_fuente"][0]["sha256"]]

    def test_una_fuente_extra_impide_regenerar(self, caso):
        extra = libro(caso["tmp"] / "x" / "extra.xlsx", filas=9)
        r = ev(caso, fuentes=[caso["fuente"], extra], regenerar=lambda f, s: pytest.fail("no debe regenerar con fuentes no verificadas"))
        assert r["estado"] == "no_reproducible" and r["regeneracion"]["estado"] == "no_ejecutada"


# ================================================================================================================ I-3
class TestI3TresConceptos:
    def test_sin_regeneracion_solicitada(self):
        r = cmp(regeneracion=None)
        assert (r["estado"], r["evaluacion"]["estado"], r["regeneracion"]["estado"]) == (None, "no_ejecutada", "no_solicitada")
        assert r["regeneracion"]["hash_registrado"] == HASH and r["regeneracion"]["hash_regenerado"] is None

    def test_regeneracion_solicitada_y_completada_identica(self):
        r = cmp()
        assert (r["estado"], r["evaluacion"]["estado"], r["regeneracion"]["estado"]) == ("exacta", "completada", "completada")

    def test_regeneracion_completada_con_hash_diferente(self):
        r = cmp(regeneracion={"hash_resultado": SHA_C})
        assert (r["estado"], r["evaluacion"]["estado"], r["regeneracion"]["estado"]) == ("parcial", "completada", "completada")

    @pytest.mark.parametrize("regen", [{"error": "boom"}, {"hash_resultado": None}, {"hash_resultado": ""}, {"hash_resultado": "abc"}, {}, "x", 1])
    def test_regeneracion_fallida_o_incompleta_no_es_un_exito_ni_un_exito_parcial(self, regen):
        r = cmp(regeneracion=regen)
        assert (r["estado"], r["evaluacion"]["estado"], r["regeneracion"]["estado"]) == (None, "fallida", "fallida")
        assert r["regeneracion"]["hash_regenerado"] is None and r["regeneracion"]["error"] and r["comprobaciones"]["C7"]["resultado"] == "error"

    def test_solicitada_pero_no_ejecutada(self):
        r = cmp(fuentes_aportadas=[], regeneracion={"no_ejecutada": "C1 a C6 no pasan"})
        assert (r["estado"], r["evaluacion"]["estado"], r["regeneracion"]["estado"]) == ("parcial", "completada", "no_ejecutada")
        r = cmp(regeneracion={"no_ejecutada": "motivo"})
        assert (r["estado"], r["evaluacion"]["estado"], r["regeneracion"]["estado"]) == (None, "no_ejecutada", "no_ejecutada")

    def test_nunca_exacta_sin_regeneracion_completada_e_igual(self):
        for regen in (None, {"error": "x"}, {"no_ejecutada": "x"}, {"hash_resultado": SHA_C}, {"hash_resultado": None}):
            assert cmp(regeneracion=regen)["estado"] != "exacta"

    def test_estado_none_nunca_se_confunde_con_coincidencia(self):
        r = cmp(regeneracion=None)
        assert r["estado"] is None and r["estado"] not in pv.ESTADOS and "exacta" not in (r["estado"] or "")

    def test_orquestacion_con_historial_real(self, caso):
        sin = ev(caso, regenerar=None)
        assert (sin["estado"], sin["evaluacion"]["estado"], sin["regeneracion"]["estado"]) == (None, "no_ejecutada", "no_solicitada")
        ok = ev(caso)
        assert (ok["estado"], ok["evaluacion"]["estado"], ok["regeneracion"]["estado"]) == ("exacta", "completada", "completada")

        def mal(f, s):
            raise RuntimeError("falla")
        fallo = ev(caso, regenerar=mal)
        assert (fallo["estado"], fallo["evaluacion"]["estado"], fallo["regeneracion"]["estado"]) == (None, "fallida", "fallida")
        sin_fuente = ev(caso, fuentes=[])
        assert (sin_fuente["estado"], sin_fuente["regeneracion"]["estado"]) == ("parcial", "no_ejecutada")
        dif = ev(caso, regenerar=lambda f, s: "f" * 64)
        assert (dif["estado"], dif["regeneracion"]["estado"]) == ("parcial", "completada")

    def test_error_interno_deja_la_evaluacion_fallida(self, caso, monkeypatch):
        from backend.app import provenance_verify as ver
        monkeypatch.setattr(ver, "verificar", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
        r = ev(caso)
        assert (r["estado"], r["evaluacion"]["estado"]) == (None, "fallida") and pv.validar_comparacion(r) == []

    def test_los_resultados_de_todos_los_casos_son_coherentes(self, caso):
        for r in (cmp(), cmp(regeneracion=None), cmp(regeneracion={"error": "x"}), cmp(regeneracion={"hash_resultado": SHA_C}), ev(caso), ev(caso, fuentes=[]),
                  cmp(verificacion=verif(registro="ausente", copia="ausente"), registrado=None)):
            assert pv.validar_comparacion(r) == [], r["causa"]

    def test_un_resultado_manipulado_hasta_contradecirse_se_detecta(self):
        base = cmp(regeneracion=None)
        quimera = copy.deepcopy(base)
        quimera["estado"] = "exacta"                                         # «exacta» sin regeneración
        assert pv.validar_comparacion(quimera)
        quimera["evaluacion"] = {"estado": "completada", "motivo": None}
        assert any("exacta" in e for e in pv.validar_comparacion(quimera))
        otro = copy.deepcopy(cmp())
        otro["regeneracion"]["hash_regenerado"] = SHA_C                       # «exacta» con hashes distintos
        assert pv.validar_comparacion(otro)
        otro2 = copy.deepcopy(cmp())
        otro2["comprobaciones"]["C4"]["resultado"] = "falla"
        assert pv.validar_comparacion(otro2)
        otro3 = copy.deepcopy(cmp(regeneracion={"error": "x"}))
        otro3["regeneracion"]["estado"] = "completada"
        assert pv.validar_comparacion(otro3)
        sc = copy.deepcopy(base)
        sc["comprobaciones"]["C3a"]["resultado"] = "falla"                    # sin clasificar con una comprobación previa en falla
        assert pv.validar_comparacion(sc)


# ================================================================================================================ I-4
class TestI4SinPersistencia:
    def test_dos_comparaciones_identicas_dan_los_mismos_bytes(self, caso):
        a, b = ev(caso), ev(caso)
        assert pv.serializar_comparacion(a) == pv.serializar_comparacion(b)

    def test_comparaciones_con_diferencias_son_estables_y_ordenadas(self):
        a = igual()
        a["configuracion"]["metas"]["total"] = "1"
        a["version_motor"] = {"engine": "9.9.9"}
        a["version_reglas"]["catalogo"]["version"] = "7.0.0"
        invertido = {k: a[k] for k in reversed(list(a))}                      # mismo contenido, otro orden de inserción
        r1, r2 = cmp(actual=a, regeneracion=None), cmp(actual=invertido, regeneracion=None)
        assert pv.serializar_comparacion(r1) == pv.serializar_comparacion(r2)
        assert [d["componente"] for d in r1["diferencias"]] == [d["componente"] for d in r2["diferencias"]]
        assert len(r1["diferencias"]) == 3

    def test_serializacion_repetida_y_con_claves_ordenadas(self):
        r = cmp()
        b = [pv.serializar_comparacion(r) for _ in range(3)]
        assert b[0] == b[1] == b[2] and json.loads(b[0]) == r
        claves = list(json.loads(b[0]))
        assert claves == sorted(claves)

    def test_se_puede_verificar_despues(self):
        for r in (cmp(), cmp(regeneracion=None), cmp(regeneracion={"error": "x"}), cmp(regeneracion={"hash_resultado": SHA_C})):
            leido, errs = pv.leer_comparacion(pv.serializar_comparacion(r))
            assert errs == [] and leido == r

    def test_resultado_vacio_o_incompleto_se_rechaza(self):
        for malo in ({}, {"esquema": "comparacion/1"}, None, [], "x"):
            with pytest.raises(pv.ErrorProcedencia):
                pv.serializar_comparacion(malo)
        r = cmp()
        del r["regeneracion"]
        with pytest.raises(pv.ErrorProcedencia):
            pv.serializar_comparacion(r)
        r2 = cmp()
        r2["comprobaciones"].pop("C7")
        with pytest.raises(pv.ErrorProcedencia):
            pv.serializar_comparacion(r2)

    def test_resultado_con_errores_se_conserva(self):
        r = cmp(regeneracion={"error": "FileNotFoundError: boom"})
        leido, errs = pv.leer_comparacion(pv.serializar_comparacion(r))
        assert errs == [] and leido["regeneracion"]["estado"] == "fallida" and leido["regeneracion"]["error"]

    def test_lectura_hostil(self):
        buena = pv.serializar_comparacion(cmp())
        casos = [b"", b"no json", buena[:-20], buena.replace(b'"estado": "exacta"', b'"estado": "exacta", "estado": "parcial"'),
                 buena.replace(b'"exacta"', b"NaN", 1), b"\xff\xfe", "texto", None, buena + b" " * (pv.MAX_MANIFIESTO_BYTES + 1)]
        for c in casos:
            leido, errs = pv.leer_comparacion(c)
            assert leido is None and errs, c if not isinstance(c, bytes) else c[:30]

    def test_referencia_suficiente_al_manifiesto_y_a_la_regeneracion(self, caso):
        r = ev(caso)
        assert r["evidencia"]["manifiesto_sha256"] == caso["out"]["manifiesto_sha256"] and r["evidencia"]["run_id"] == caso["run_id"]
        assert r["regeneracion"]["hash_registrado"] == r["regeneracion"]["hash_regenerado"] == caso["out"]["hash_resultado"]

    def test_no_modifica_el_historial_ni_siquiera_con_regeneracion(self, caso):
        antes = caso["db"].read_bytes()
        for _ in range(3):
            ev(caso)
        ev(caso, fuentes=[])
        ev(caso, regenerar=lambda f, s: "f" * 64)
        assert caso["db"].read_bytes() == antes
        con = sqlite3.connect(caso["db"])
        assert con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%compar%'").fetchall() == []   # ninguna tabla nueva
        con.close()

    def test_el_resultado_es_json_plano_consumible_desde_el_puente_del_servicio(self, caso):
        """El servicio devuelve JSON (`bridge.handle`); el resultado ya es JSON puro (sin Decimal, bytes ni objetos): no necesita adaptador."""
        r = ev(caso)
        assert json.loads(json.dumps(r)) == r
