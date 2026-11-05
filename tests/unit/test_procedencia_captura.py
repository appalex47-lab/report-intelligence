"""Fase 3A-3 · captura de procedencia (`provenance_capture`): flujo normal, entradas límite, fallos inducidos por etapa y seguridad."""
import json
import os
import sqlite3
from pathlib import Path

import pytest

from backend.app import provenance as pv
from backend.app import provenance_capture as cap
from backend.app.history import store as hist
from tests.proc_util import AHORA, P, capturar, libro, narrativa, plantilla, resultado


def archivos(carpeta):
    return sorted(p.name for p in carpeta.iterdir())


def leer(carpeta):
    return pv.leer_manifiesto((carpeta / "procedencia.json").read_bytes())[0]


# --------------------------------------------------------------------------------------------------------------- flujo normal
def test_con_historial_registra_fila_y_copia_identicas(tmp_path):
    out, carpeta, db = capturar(tmp_path)
    assert out["estado"] == "registrada" and out["registro"] == "registrada" and out["error"] is None and out["archivo"] == "procedencia.json"
    datos = (carpeta / "procedencia.json").read_bytes()
    con = hist.connect(db)
    fila = hist.get_procedencia(con, out["run_id"])
    assert fila["manifiesto"] == datos and fila["manifiesto_sha256"] == out["manifiesto_sha256"] == pv.sha256_hex(datos)
    assert fila["hash_resultado"] == out["hash_resultado"] == leer(carpeta)["hash_resultado"]["valor"]
    con.close()
    assert archivos(carpeta) == ["procedencia.json"]                             # ni temporales ni error


def test_el_manifiesto_describe_fuente_plantilla_y_no_guarda_valores_de_celdas(tmp_path):
    out, carpeta, _ = capturar(tmp_path)
    m = leer(carpeta)
    f = m["archivos_fuente"][0]
    assert f["id"] == "F1" and f["nombre"] == "input.xlsx" and f["filas"] == {"ventas": 3} and f["columnas"] == {"ventas": ["fecha_pedido", "id_pedido", "monto_venta"]}
    assert f["periodo_detectado"] == "2026-07..2026-09" and f["sha256"] == hist.sha256(tmp_path / "input.xlsx")
    assert m["version_plantillas"][0]["id"] == "aetops-mensual/1" and m["fecha_generacion"]["utc"] == "2026-11-05T12:00:00Z"
    texto = (carpeta / "procedencia.json").read_text(encoding="utf-8")
    assert "Prolia" not in texto and "P0" not in texto and str(tmp_path) not in texto
    assert m["version_reglas"]["ejecucion"]["motor_ejecutado"] is False


def test_sin_historial_solo_deja_la_copia_con_estado_propio(tmp_path):
    out, carpeta, db = capturar(tmp_path, db=False)
    assert db is None and out["estado"] == "copia_sin_registro" and out["registro"] is None and (carpeta / "procedencia.json").is_file()


def test_es_idempotente_con_la_misma_fecha(tmp_path):
    out1, carpeta, db = capturar(tmp_path)
    antes = (carpeta / "procedencia.json").read_bytes()
    out2 = cap.ejecutar(carpeta=carpeta, period=P, result=resultado(), narrative=narrativa("Hola"), sources=[tmp_path / "input.xlsx"],
                        template=tmp_path / "templates" / "aetops-mensual" / "1" / "template.pptx", history_db=db, run_id=out1["run_id"], ahora=AHORA)
    assert out2["estado"] == "registrada" and out2["registro"] == "ya_registrada" and (carpeta / "procedencia.json").read_bytes() == antes
    assert out2["manifiesto_sha256"] == out1["manifiesto_sha256"]


def test_una_nueva_captura_del_mismo_run_con_otros_bytes_no_sustituye_el_registro(tmp_path):
    out1, carpeta, db = capturar(tmp_path)
    original = (carpeta / "procedencia.json").read_bytes()
    from datetime import datetime, timezone
    out2 = cap.ejecutar(carpeta=carpeta, period=P, result=resultado(), narrative=narrativa("Hola"), sources=[tmp_path / "input.xlsx"],
                        template=tmp_path / "templates" / "aetops-mensual" / "1" / "template.pptx", history_db=db, run_id=out1["run_id"],
                        ahora=datetime(2027, 1, 1, tzinfo=timezone.utc))
    assert out2["estado"] == "error" and out2["etapa"] == "historial" and out2["archivo_error"] == "procedencia_error.json"
    assert not (carpeta / "procedencia.json").exists()                            # la copia se retiró: no queda una copia que no coincide
    con = hist.connect(db)
    assert hist.get_procedencia(con, out1["run_id"])["manifiesto"] == original     # el registro autoritativo sigue intacto
    con.close()


def test_varias_fuentes_con_ids_estables_y_contenido_duplicado_con_otro_nombre(tmp_path):
    a = libro(tmp_path / "a.xlsx", filas=2)
    b = libro(tmp_path / "b.xlsx", filas=4, extra_hoja=True)
    copia_de_a = tmp_path / "copia_a.xlsx"
    copia_de_a.write_bytes(a.read_bytes())
    out, carpeta, _ = capturar(tmp_path, sources=[b, a, copia_de_a])
    m = leer(carpeta)
    assert out["estado"] == "registrada" and len(m["archivos_fuente"]) == 2                  # el contenido idéntico cuenta una sola vez
    assert [f["id"] for f in m["archivos_fuente"]] == ["F1", "F2"]
    assert {f["nombre"] for f in m["archivos_fuente"]} <= {"a.xlsx", "b.xlsx", "copia_a.xlsx"}
    assert any(f["filas"] == {"ventas": 4, "catalogo": 1} for f in m["archivos_fuente"])


def test_mismo_nombre_y_distinto_contenido_se_rechaza_por_ambiguo(tmp_path):
    a = libro(tmp_path / "x" / "datos.xlsx", filas=2)
    b = libro(tmp_path / "y" / "datos.xlsx", filas=5)
    out, carpeta, _ = capturar(tmp_path, sources=[a, b], db=False)                     # contrato 3A-2: el linaje «datos.xlsx» sería ambiguo
    assert out["estado"] == "error" and out["etapa"] == "canonico" and "contenido distinto" in out["error"]


def test_sin_fuentes_registra_una_lista_vacia(tmp_path):
    out, carpeta, _ = capturar(tmp_path, sources=[])
    assert out["estado"] == "registrada" and leer(carpeta)["archivos_fuente"] == []


def test_una_fuente_que_no_es_xlsx_se_registra_solo_con_su_sha(tmp_path):
    csv = tmp_path / "datos.csv"
    csv.write_text("a,b\n1,2\n", encoding="utf-8")
    out, carpeta, _ = capturar(tmp_path, sources=[csv])
    f = leer(carpeta)["archivos_fuente"][0]
    assert out["estado"] == "registrada" and f["filas"] == {} and f["periodo_detectado"] is None and f["sha256"] == hist.sha256(csv)


def test_ia_tres_estados(tmp_path):
    for ia, esperado in ((None, {"usada": None, "modelo_declarado": None}), ({"usada": False}, {"usada": False, "modelo_declarado": None}),
                         ({"usada": True, "modelo_declarado": "modelo-x"}, {"usada": True, "modelo_declarado": "modelo-x"})):
        d = tmp_path / str(ia is None) / str(ia)
        d.mkdir(parents=True)
        out, carpeta, _ = capturar(d, db=False, ia=ia)
        assert out["estado"] == "copia_sin_registro" and leer(carpeta)["configuracion"]["ia"] == esperado


def test_el_contexto_se_registra_solo_con_su_sha(tmp_path):
    out, carpeta, _ = capturar(tmp_path, context=["línea secreta 1", "línea secreta 2"])
    cfg = leer(carpeta)["configuracion"]["contexto"]
    assert cfg["lineas"] == 2 and "secreta" not in (carpeta / "procedencia.json").read_text(encoding="utf-8")


def test_el_hash_depende_de_las_entradas_pero_no_de_la_fecha(tmp_path):
    a = capturar(tmp_path / "1", db=False)[0] if (tmp_path / "1").mkdir() is None else None
    (tmp_path / "2").mkdir()
    from datetime import datetime, timezone
    b = capturar(tmp_path / "2", db=False)[0]
    assert a["hash_resultado"] == b["hash_resultado"]                              # mismos bytes de fuente, mismo resultado
    (tmp_path / "3").mkdir()
    c = capturar(tmp_path / "3", db=False, resultado_=resultado(x="11"))[0]
    assert c["hash_resultado"] != a["hash_resultado"]


# --------------------------------------------------------------------------------------------------------------- entradas inválidas
def test_fuente_inexistente_directorio_o_corrupta_dejan_error_y_ninguna_copia(tmp_path):
    corrupto = tmp_path / "roto.xlsx"
    corrupto.write_bytes(b"esto no es un zip")
    carpeta_csv = tmp_path / "csvs"
    carpeta_csv.mkdir()
    for i, fuente in enumerate([tmp_path / "no_existe.xlsx", carpeta_csv, corrupto]):
        d = tmp_path / f"caso{i}"
        d.mkdir()
        out, carpeta, _ = capturar(d, sources=[fuente], db=False)
        assert out["estado"] == "error" and out["etapa"] == "entradas" and out["archivo_error"] == "procedencia_error.json"
        assert archivos(carpeta) == ["procedencia_error.json"]
        doc = json.loads((carpeta / "procedencia_error.json").read_text(encoding="utf-8"))
        assert doc["esquema"] == pv.ESQUEMA_ERROR and doc["etapa"] == "entradas" and str(d) not in doc["mensaje"]


def test_plantilla_inexistente(tmp_path):
    carpeta = tmp_path / "r"
    carpeta.mkdir()
    out = cap.ejecutar(carpeta=carpeta, period=P, result=resultado(), narrative=narrativa("x"), sources=[], template=tmp_path / "no.pptx", ahora=AHORA)
    assert out["estado"] == "error" and out["etapa"] == "entradas" and archivos(carpeta) == ["procedencia_error.json"]


def test_hay_historial_pero_no_se_conoce_la_corrida(tmp_path):
    _, db = (tmp_path / "h.sqlite"), None
    out = cap.ejecutar(carpeta=tmp_path, period=P, result=resultado(), narrative=narrativa("x"), sources=[], template=plantilla(tmp_path),
                       history_db=tmp_path / "h.sqlite", run_id=None, ahora=AHORA)
    assert out["estado"] == "error" and out["etapa"] == "historial" and not (tmp_path / "procedencia.json").exists()


def test_la_corrida_no_existe_en_el_historial(tmp_path):
    out, carpeta, db = capturar(tmp_path, run_id=None)
    assert out["estado"] == "registrada"
    carpeta2 = tmp_path / "otro"
    carpeta2.mkdir()
    out = cap.ejecutar(carpeta=carpeta2, period=P, result=resultado(), narrative=narrativa("x"), sources=[], template=plantilla(tmp_path),
                       history_db=db, run_id=999, ahora=AHORA)
    assert out["estado"] == "error" and out["etapa"] == "historial" and archivos(carpeta2) == ["procedencia_error.json"]


# --------------------------------------------------------------------------------------------------------------- fallos inducidos
@pytest.mark.parametrize("etapa,parche", [
    ("entradas", ("describir_fuente", RuntimeError("falla al leer"))),
    ("entradas", ("describir_plantilla", RuntimeError("falla plantilla"))),
    ("entradas", ("version_reglas", RuntimeError("catálogo ilegible"))),
    ("canonico", (None, None)),
    ("manifiesto", ("_construir_manifiesto", None)),
    ("serializacion", ("_serializar", None)),
])
def test_fallo_inducido_en_cada_etapa_nunca_deja_manifiesto_incompleto(tmp_path, monkeypatch, etapa, parche):
    if etapa == "canonico":
        monkeypatch.setattr(pv, "calcular", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("fallo canónico")))
    elif etapa == "manifiesto":
        monkeypatch.setattr(pv, "construir_manifiesto", lambda **k: (_ for _ in ()).throw(RuntimeError("fallo manifiesto")))
    elif etapa == "serializacion":
        monkeypatch.setattr(pv, "serializar_manifiesto", lambda m: (_ for _ in ()).throw(RuntimeError("fallo serialización")))
    else:
        monkeypatch.setattr(cap, parche[0], lambda *a, **k: (_ for _ in ()).throw(parche[1]))
    out, carpeta, db = capturar(tmp_path)
    assert out["estado"] == "error" and out["etapa"] == etapa and out["archivo"] is None
    assert archivos(carpeta) == ["procedencia_error.json"]
    con = hist.connect(db)
    assert hist.get_procedencia(con, out["run_id"]) is None                          # nada a medias en la base
    con.close()


def test_fallo_al_registrar_en_el_historial(tmp_path, monkeypatch):
    monkeypatch.setattr(hist, "record_procedencia", lambda *a, **k: (_ for _ in ()).throw(sqlite3.OperationalError("database or disk is full")))
    out, carpeta, db = capturar(tmp_path)
    assert out["estado"] == "error" and out["etapa"] == "historial" and archivos(carpeta) == ["procedencia_error.json"]


def test_fallo_al_escribir_la_copia_deja_la_fila_y_la_marca_para_reexportar(tmp_path, monkeypatch):
    monkeypatch.setattr(cap, "escribir_atomico", lambda destino, datos: (_ for _ in ()).throw(OSError("No space left on device"))
                        if destino.name == "procedencia.json" else Path(destino).write_bytes(datos))
    out, carpeta, db = capturar(tmp_path)
    assert out["estado"] == "registrada_sin_copia" and out["etapa"] == "archivo" and out["registro"] == "registrada"
    assert archivos(carpeta) == ["procedencia_error.json"]
    con = hist.connect(db)
    assert hist.get_procedencia(con, out["run_id"]) is not None
    con.close()


def test_si_ni_el_archivo_de_error_se_puede_escribir_se_devuelve_en_la_salida(tmp_path, monkeypatch):
    monkeypatch.setattr(cap, "describir_fuente", lambda p: (_ for _ in ()).throw(RuntimeError("x")))
    monkeypatch.setattr(cap, "escribir_atomico", lambda *a: (_ for _ in ()).throw(OSError("solo lectura")))
    out, carpeta, _ = capturar(tmp_path, db=False)
    assert out["estado"] == "error" and out["archivo_error"] is None and out["error"] and archivos(carpeta) == []


def test_ejecutar_nunca_lanza_ni_con_argumentos_absurdos(tmp_path):
    out = cap.ejecutar(carpeta=tmp_path / "no_existe" / "x", period=P, result=None, narrative=None, sources=None, template=None, ahora=AHORA)
    assert out["estado"] == "error"


def test_se_retiran_copias_y_errores_de_una_generacion_anterior(tmp_path):
    carpeta = tmp_path / "reporte"
    carpeta.mkdir()
    (carpeta / "procedencia.json").write_text("viejo")
    (carpeta / "procedencia_error.json").write_text("viejo")
    out, carpeta, _ = capturar(tmp_path, db=False)
    assert out["estado"] == "copia_sin_registro" and archivos(carpeta) == ["procedencia.json"]
    assert (carpeta / "procedencia.json").read_bytes() != b"viejo"


# --------------------------------------------------------------------------------------------------------------- escritura atómica y seguridad
def test_escribir_atomico_reemplaza_sin_dejar_temporales(tmp_path):
    cap.escribir_atomico(tmp_path / "a.json", b"uno")
    cap.escribir_atomico(tmp_path / "a.json", b"dos")
    assert (tmp_path / "a.json").read_bytes() == b"dos" and archivos(tmp_path) == ["a.json"]


def test_si_el_reemplazo_falla_se_borra_el_temporal_y_el_destino_no_cambia(tmp_path, monkeypatch):
    (tmp_path / "a.json").write_bytes(b"original")
    monkeypatch.setattr(os, "replace", lambda *a: (_ for _ in ()).throw(OSError("fallo")))
    with pytest.raises(OSError):
        cap.escribir_atomico(tmp_path / "a.json", b"nuevo")
    assert (tmp_path / "a.json").read_bytes() == b"original" and archivos(tmp_path) == ["a.json"]


def test_si_la_escritura_falla_a_medias_no_queda_nada(tmp_path, monkeypatch):
    import tempfile
    real = os.fdopen

    class Roto:
        def __init__(self, fh): self.fh = fh
        def __enter__(self): return self
        def __exit__(self, *a): self.fh.close()
        def write(self, d): raise OSError("disco lleno")
    monkeypatch.setattr(os, "fdopen", lambda fd, mode: Roto(real(fd, mode)))
    with pytest.raises(OSError):
        cap.escribir_atomico(tmp_path / "a.json", b"x" * 100)
    assert archivos(tmp_path) == []


def test_los_nombres_hostiles_no_escapan_ni_rompen_el_manifiesto(tmp_path):
    hostil = tmp_path / "..%2f‮evil\n\tñ😀 datos.xlsx"
    libro(hostil)
    out, carpeta, _ = capturar(tmp_path, sources=[hostil], db=False)
    assert out["estado"] == "copia_sin_registro"
    nombre = leer(carpeta)["archivos_fuente"][0]["nombre"]
    assert "/" not in nombre and "\n" not in nombre and "\t" not in nombre
    assert archivos(carpeta) == ["procedencia.json"]                                # solo los dos nombres fijados por el sistema


def test_un_nombre_larguisimo_se_acota(tmp_path):
    largo = tmp_path / (("n" * 200) + ".xlsx")
    libro(largo)
    out, carpeta, _ = capturar(tmp_path, sources=[largo], db=False)
    assert out["estado"] == "copia_sin_registro" and len(leer(carpeta)["archivos_fuente"][0]["nombre"]) <= cap.MAX_NOMBRE


def test_el_mensaje_de_error_no_filtra_rutas_absolutas(tmp_path):
    out, carpeta, _ = capturar(tmp_path, sources=[tmp_path / "secretos" / "no_existe.xlsx"], db=False)
    assert str(tmp_path) not in out["error"] and str(tmp_path) not in (carpeta / "procedencia_error.json").read_text(encoding="utf-8")


def test_no_se_toca_nada_fuera_de_la_carpeta_del_reporte_ni_se_modifican_las_fuentes(tmp_path):
    src = libro(tmp_path / "input.xlsx")
    antes = src.read_bytes()
    out, carpeta, db = capturar(tmp_path, sources=[src])
    assert src.read_bytes() == antes
    assert sorted(p.name for p in tmp_path.iterdir()) == ["historial", "input.xlsx", "reporte", "templates"]


def test_los_permisos_del_archivo_no_dan_escritura_a_otros(tmp_path):
    out, carpeta, _ = capturar(tmp_path, db=False)
    assert (carpeta / "procedencia.json").stat().st_mode & 0o022 == 0


def test_entorno_y_zona_horaria_no_fallan_y_no_traen_datos_sensibles():
    e = cap.entorno()
    assert set(e) == {"pyodide", "python", "python_pptx"} and all(isinstance(v, str) for v in e.values())
    z = cap.zona_horaria()
    assert z is None or isinstance(z, str)
