"""Fase 3A-4 (D-07) · fallos reales del regenerador, recorriendo `evaluar → regenerador → correr → build_aetops`.

Se ejecuta en CI: no usa plantillas externas. Se usan el MOTOR real (libro de ejemplo versionado), el REGENERADOR real y la CAPTURA real
(`cap.ejecutar`). Lo único que se sustituye en los escenarios B y C es la construcción del PPTX (`backend.app.build.build_aetops`), porque
generarlo exige la plantilla con marca, que no se versiona.

LIMITACIÓN (explícita): B y C no prueban el PPTX ni la narrativa real de un reporte; la narrativa que usa el sustituto es fija. La
regeneración con plantillas reales sigue validándose localmente con `tests/regression/test_procedencia_regeneracion.py`.
El escenario A, en cambio, usa el `build_aetops` REAL (se bloquea antes de abrir la plantilla).

Cada prueba comprueba además que lo que debía ejecutarse se ejecutó (contadores), para que no pueda pasar sin recorrer el flujo real."""
import shutil
import types
from pathlib import Path

import pytest

from backend.app import build as B
from backend.app import provenance_capture as cap
from backend.app import provenance_compare as cmpm
from backend.app import version
from backend.app.history import store as hist
from backend.app.models import Period
from backend.app.narrative.writer import Para
from backend.app.pipeline import run_aetops_raw
from backend.app.targets import Targets
from tests.proc_util import AHORA, historial, plantilla

ROOT = Path(__file__).resolve().parents[2]
EJEMPLO = ROOT / "data" / "ejemplos" / "AETOPS_crudo_ejemplo.xlsx"
OTRO = ROOT / "data" / "ejemplos" / "AETOPS_crudo_con_defectos.xlsx"           # otro libro versionado: contenido (SHA-256) distinto
PERIODO = Period("AETOPS", "mensual", 2026, 9)
METAS = Targets.parse({"total": "12000000"})
COMMIT = "a" * 40


def narrativa():
    """Narrativa fija del sustituto y del reporte original (no es la narrativa real de un PPTX)."""
    return {"conclusiones": [Para("Texto de prueba de la regeneración.", "hecho")]}


class Sustituto:
    """Sustituto controlado de `build_aetops`: registra cada invocación y delega en la CAPTURA REAL. Nunca devuelve un hash fabricado."""

    def __init__(self, modo, otra_fuente=None, narr=None):
        self.modo, self.otra_fuente, self.narr = modo, otra_fuente, narr or narrativa
        self.llamadas, self.out_dirs, self.fuentes_manifiesto, self.proc = 0, [], None, None

    def __call__(self, result, period, template, out_dir, **kw):
        self.llamadas += 1
        out_dir = Path(out_dir)
        self.out_dirs.append(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        fuentes = kw["sources"]
        if self.modo == "procedencia_en_error":
            fuentes = [Path("no_existe.xlsx")]                                  # la captura REAL falla en la etapa «entradas»
        elif self.modo == "otras_fuentes":
            fuentes = [self.otra_fuente]                                        # la captura REAL registra otra fuente
        proc = cap.ejecutar(carpeta=out_dir, period=period, result=result, narrative=self.narr(), sources=fuentes, template=template,
                            targets=kw.get("targets"), history_db=None)
        self.proc = proc
        if self.modo == "sin_procedencia_json":
            (out_dir / cap.ARCHIVO_COPIA).unlink()                              # termina «bien» pero no deja el archivo
        archivo = out_dir / cap.ARCHIVO_COPIA
        if archivo.exists():
            from backend.app import provenance as pv
            m, _ = pv.leer_manifiesto(archivo.read_bytes())
            self.fuentes_manifiesto = sorted(f["sha256"] for f in m["archivos_fuente"]) if m else None
        return types.SimpleNamespace(procedencia=proc)


@pytest.fixture(autouse=True)
def commit_estampado(monkeypatch):
    monkeypatch.setattr(version, "commit", lambda: COMMIT)


@pytest.fixture(scope="module")
def original(tmp_path_factory):
    """Un reporte «original» real: motor real + captura real + fila en un historial real. Solo lectura para todas las pruebas."""
    base = tmp_path_factory.mktemp("regenerador")
    fuente = base / "input.xlsx"                                                # como el servicio: la carga se guarda como input.xlsx
    shutil.copyfile(EJEMPLO, fuente)
    tpl = plantilla(base)                                                       # plantilla ficticia con el formato de ruta de las reales
    db, rid = historial(base / "historial" / "h.sqlite", tpl, [fuente], PERIODO)
    carpeta = base / "reporte"
    carpeta.mkdir()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(version, "commit", lambda: COMMIT)
        res = run_aetops_raw(fuente, PERIODO, targets=METAS, require_targets=True)
        out = cap.ejecutar(carpeta=carpeta, period=PERIODO, result=res, narrative=narrativa(), sources=[fuente], template=tpl, targets=METAS,
                           history_db=db, run_id=rid, ahora=AHORA)
    assert out["estado"] == "registrada", out
    return {"db": db, "run_id": rid, "carpeta": carpeta, "fuente": fuente, "tpl": tpl, "hash": out["hash_resultado"], "sha": hist.sha256(fuente)}


def evaluar(o, regenerar):
    """`evaluar` real con la configuración ACTUAL igual a la original (metas incluidas) para que C1 a C6 pasen y la regeneración se ejecute."""
    return cmpm.evaluar(o["db"], o["run_id"], carpeta=o["carpeta"], fuentes=[o["fuente"]], template=o["tpl"], targets=METAS, regenerar=regenerar)


def espiar(regenerar):
    """Envuelve el callable de regeneración para comprobar que `evaluar` lo invocó y con qué."""
    llamadas = []

    def envoltura(fuentes, shas):
        llamadas.append((list(fuentes), list(shas)))
        return regenerar(fuentes, shas)
    envoltura.llamadas = llamadas
    return envoltura


def triple(r):
    return (r["estado"], r["evaluacion"]["estado"], r["regeneracion"]["estado"])


def comprobar_fallo_visible(r, esperado_en_error):
    assert triple(r) == (None, "fallida", "fallida")
    assert r["regeneracion"]["ejecutada"] is True and r["regeneracion"]["hash_regenerado"] is None
    assert r["comprobaciones"]["C7"]["resultado"] == "error" and r["regeneracion"]["error"]           # el error se conserva y es visible
    for texto in esperado_en_error:
        assert texto in r["regeneracion"]["error"], r["regeneracion"]["error"]
    assert "exacta" not in str(r["estado"]) and r["regeneracion"]["estado"] != "completada"


# ------------------------------------------------------------------------------------------------------------------ Escenario A
def test_A_excepcion_real_de_construccion_build_aetops_real_sin_metas(original, monkeypatch):
    """`evaluar → regenerador → correr → build_aetops (REAL) → ReportBlocked → regeneración fallida`. Sin sustitutos de `build_*`."""
    reales = []
    real = B.build_aetops

    def espia_real(*a, **kw):                                                   # delega en el build_aetops REAL; solo cuenta e intercepta la excepción
        reales.append(kw.get("targets"))
        try:
            return real(*a, **kw)
        except B.ReportBlocked as e:
            reales.append(type(e))
            raise
    monkeypatch.setattr(B, "build_aetops", espia_real)
    regenerar = espiar(cmpm.regenerador(period=PERIODO, template=original["tpl"], targets=None))            # targets=None: bloqueo real
    r = evaluar(original, regenerar)
    assert len(regenerar.llamadas) == 1                                          # `evaluar` ejecutó el regenerador
    fuentes, shas = regenerar.llamadas[0]
    assert [Path(f).name for f in fuentes] == ["input.xlsx"] and shas == [original["sha"]]
    assert reales == [None, B.ReportBlocked]                                    # se invocó el build_aetops real con targets=None y lanzó ReportBlocked
    comprobar_fallo_visible(r, ["ReportBlocked", "TARGETS_MISSING"])
    assert r["estado"] is None


def test_A_correr_lanza_ReportBlocked_y_no_deja_temporales(original, monkeypatch):
    """Mismo escenario sin `evaluar`: la excepción exacta sale de `correr` y el directorio temporal no queda."""
    vistos = []
    real = B.build_aetops

    def espia_real(res, period, template, out_dir, **kw):
        vistos.append(Path(out_dir))
        return real(res, period, template, out_dir, **kw)
    monkeypatch.setattr(B, "build_aetops", espia_real)
    with pytest.raises(B.ReportBlocked, match="TARGETS_MISSING"):
        cmpm.regenerador(period=PERIODO, template=original["tpl"], targets=None)([original["fuente"]], [original["sha"]])
    assert len(vistos) == 1 and not vistos[0].parent.exists()


# ------------------------------------------------------------------------------------------------------------------ Escenario B
@pytest.mark.parametrize("modo,texto_error", [
    ("procedencia_en_error", ["RuntimeError", "estado 'error'", "etapa 'entradas'"]),
    ("sin_procedencia_json", ["FileNotFoundError", "procedencia.json"]),
    ("otras_fuentes", ["RuntimeError", "no son las verificadas"]),
])
def test_B_salida_incompleta_o_invalida_es_regeneracion_fallida(original, monkeypatch, modo, texto_error):
    sustituto = Sustituto(modo, otra_fuente=OTRO)
    monkeypatch.setattr(B, "build_aetops", sustituto)
    regenerar = espiar(cmpm.regenerador(period=PERIODO, template=original["tpl"], targets=METAS))
    r = evaluar(original, regenerar)
    assert len(regenerar.llamadas) == 1 and sustituto.llamadas == 1             # se ejecutó el regenerador y se invocó el sustituto
    comprobar_fallo_visible(r, texto_error)
    assert sustituto.proc is not None                                           # la captura real se ejecutó dentro del sustituto
    assert not sustituto.out_dirs[0].parent.exists()                            # los temporales se limpian aunque haya excepción
    if modo == "otras_fuentes":                                                 # el manifiesto producido listaba otra fuente, no la verificada
        assert sustituto.fuentes_manifiesto == [hist.sha256(OTRO)] != [original["sha"]]


# ------------------------------------------------------------------------------------------------------------------ Escenario C
def test_C_regeneracion_valida_con_captura_real_es_exacta(original, monkeypatch):
    sustituto = Sustituto("ok")
    monkeypatch.setattr(B, "build_aetops", sustituto)
    regenerar = espiar(cmpm.regenerador(period=PERIODO, template=original["tpl"], targets=METAS))
    r = evaluar(original, regenerar)
    assert len(regenerar.llamadas) == 1 and sustituto.llamadas == 1             # regenerador y sustituto se ejecutaron
    assert sustituto.proc["estado"] == "copia_sin_registro" and sustituto.proc["hash_resultado"]       # la captura real produjo una procedencia válida
    assert sustituto.fuentes_manifiesto == [original["sha"]]                    # el manifiesto contiene exactamente las fuentes verificadas
    assert triple(r) == ("exacta", "completada", "completada")
    assert r["regeneracion"]["hash_regenerado"] == r["regeneracion"]["hash_registrado"] == original["hash"]
    assert r["comprobaciones"]["C7"]["resultado"] == "pasa" and r["diferencias"] == [] and r["regeneracion"]["error"] is None
    assert not sustituto.out_dirs[0].parent.exists()


def test_C_el_hash_lo_calcula_la_captura_real_no_el_sustituto(original, monkeypatch):
    """Si la narrativa del reporte regenerado cambia, el hash cambia: el sustituto no puede estar fabricando un éxito."""
    sustituto = Sustituto("ok", narr=lambda: {"conclusiones": [Para("Otro texto distinto.", "hecho")]})
    monkeypatch.setattr(B, "build_aetops", sustituto)
    r = evaluar(original, cmpm.regenerador(period=PERIODO, template=original["tpl"], targets=METAS))
    assert sustituto.llamadas == 1 and triple(r) == ("parcial", "completada", "completada")
    assert r["regeneracion"]["hash_regenerado"] != original["hash"] and "anomalía de determinismo" in r["causa"]


def test_el_original_no_se_modifica_durante_las_pruebas(original):
    """Solo lectura: la fila de procedencia y la copia siguen siendo las del reporte original."""
    from backend.app import provenance_verify as ver
    v = ver.verificar(original["db"], original["run_id"], original["carpeta"])
    assert v["integridad"] == "verificada" and v["copia"]["estado"] == "integra"
