"""Genera las fixtures SINTÉTICAS de la Fase 1 (modelo y línea base) de forma determinista.

* Semilla fija; dos ejecuciones producen los mismos bytes (y los mismos SHA-256).
* Cada fixture lleva `sintetico: true`; el manifiesto lista archivo, SHA-256 y tamaño.
* Solo escribe dentro de `tests/fixtures/fase1/`; no lee archivos de datos ni usa identificadores reales
  (todo identificador sintético empieza por `SINT-`).
* Estas fixtures cubren el MODELO (hallazgos) y el CATÁLOGO. Las fixtures funcionales de las reglas
  (`rel_pac_ped_*`, `cuadre_dim_*`, …) pertenecen a fases posteriores.

Uso:
    python tools/make_fixtures_fase1.py            # escribe
    python tools/make_fixtures_fase1.py --check    # verifica que el disco coincide con lo que se generaría
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PERMITIDO = ROOT / "tests" / "fixtures" / "fase1"
SEMILLA = 20260601
VERSION_GENERADOR = "1.0.0"


def _hallazgos(rng: random.Random) -> dict:
    """Hallazgos sintéticos: histórico (solo severity), con campos nuevos coherentes e incoherentes."""
    sev = ["block", "warn", "info"]
    efecto = {"block": "bloquear", "warn": "advertir", "info": "informar"}
    tipos = ["integridad", "consistencia", "cobertura", "definicion", "conciliacion", "narrativa", "presentacion"]
    grav = ["critica", "alta", "media", "baja"]
    legado, nuevos = [], []
    for i in range(1, 10):
        s = sev[(i - 1) % 3]
        legado.append({"id": f"SINT_LEGADO_{i:02d}", "severity": s, "message": f"Hallazgo sintético {i}", "evidence": f"hoja SINT-{rng.randint(100, 999)}"})
    for i in range(1, 7):
        s = rng.choice(sev)
        nuevos.append({"id": f"SINT_NUEVO_{i:02d}", "severity": s, "message": f"Hallazgo nuevo sintético {i}", "evidence": "",
                       "tipo": rng.choice(tipos), "gravedad": rng.choice(grav), "estado_verificacion": "verificado",
                       "efecto_generacion": efecto[s], "regla_id": "R-SINT", "regla_version": "0.0.1"})
    incoherentes = [
        {"id": "SINT_INCOHERENTE_01", "severity": "warn", "message": "x", "evidence": "", "efecto_generacion": "bloquear"},
        {"id": "SINT_INCOHERENTE_02", "severity": "info", "message": "x", "evidence": "", "efecto_generacion": "advertir"},
        {"id": "SINT_INCOHERENTE_03", "severity": "block", "message": "x", "evidence": "", "efecto_generacion": "informar"},
    ]
    invalidos = [
        {"id": "SINT_INVALIDO_01", "severity": "warn", "message": "x", "evidence": "", "tipo": "inventado"},
        {"id": "SINT_INVALIDO_02", "severity": "warn", "message": "x", "evidence": "", "gravedad": "enorme"},
        {"id": "SINT_INVALIDO_03", "severity": "warn", "message": "x", "evidence": "", "estado_verificacion": "quizas"},
        {"id": "SINT_INVALIDO_04", "severity": "info", "message": "x", "evidence": "", "estado_verificacion": "no_verificable"},
    ]
    return {"sintetico": True, "descripcion": "Hallazgos sintéticos para las pruebas de compatibilidad del modelo",
            "legado": legado, "nuevos": nuevos, "incoherentes": incoherentes, "invalidos": invalidos}


def _entrada(i: int, rng: random.Random) -> dict:
    return {"id": f"sint_def_{i:02d}", "nombre": f"Definición sintética {i}", "descripcion": f"Descripción sintética {i}",
            "version": f"1.{rng.randint(0, 3)}.0", "tipo": rng.choice(["entidad", "metrica", "indicador"]), "unidad": None,
            "fuente": {"hoja": "ventas", "columna": "id_pedido"}, "granularidad": "sintética",
            "aplicabilidad": {"unidades": ["GLP1"], "condicion": None}, "limitaciones": ["Solo para pruebas"],
            "origen": "nuevo", "validacion_operacional": "no_validada_con_datos_reales", "referencia": "SINT"}


def _catalogos(rng: random.Random) -> dict[str, dict]:
    base = {"esquema": "definiciones/1", "version": "1.0.0", "fuente_documental": "sintético",
            "definiciones": [_entrada(i, rng) for i in range(1, 4)]}
    dup = json.loads(json.dumps(base)); dup["definiciones"][2]["id"] = dup["definiciones"][0]["id"]
    faltante = json.loads(json.dumps(base)); del faltante["definiciones"][1]["descripcion"]
    mala_version = json.loads(json.dumps(base)); mala_version["version"] = "uno"
    mala_unidad = json.loads(json.dumps(base)); mala_unidad["definiciones"][0]["aplicabilidad"]["unidades"] = ["OTRA"]
    out = {"catalogo_valido": base, "catalogo_id_duplicado": dup, "catalogo_campo_faltante": faltante,
           "catalogo_version_invalida": mala_version, "catalogo_unidad_invalida": mala_unidad}
    for v in out.values():
        v["sintetico"] = True
    return out


def generar() -> dict[str, bytes]:
    """nombre de archivo -> bytes. Determinista: una `Random` por archivo, derivada de la semilla y del nombre."""
    def rng_for(nombre: str) -> random.Random:
        return random.Random(f"{SEMILLA}:{nombre}")
    files: dict[str, dict] = {"hallazgos_compat.json": _hallazgos(rng_for("hallazgos_compat"))}
    for nombre, cat in _catalogos(rng_for("catalogos")).items():
        files[f"{nombre}.json"] = cat
    out = {n: (json.dumps(o, ensure_ascii=False, indent=1, sort_keys=True) + "\n").encode("utf-8") for n, o in files.items()}
    manifiesto = {
        "esquema": "fixtures_fase1/1", "sintetico": True, "semilla": SEMILLA, "generador": "tools/make_fixtures_fase1.py",
        "version_generador": VERSION_GENERADOR,
        "aviso": "Datos inventados para pruebas. No contienen datos reales ni identificadores personales.",
        "fixtures": [{"archivo": n, "sintetico": True, "sha256": hashlib.sha256(b).hexdigest(), "bytes": len(b)} for n, b in sorted(out.items())],
    }
    out["manifest.json"] = (json.dumps(manifiesto, ensure_ascii=False, indent=1, sort_keys=True) + "\n").encode("utf-8")
    return out


def _dentro(destino: Path) -> Path:
    destino = destino.resolve()
    if destino != PERMITIDO and PERMITIDO not in destino.parents:
        raise SystemExit(f"Solo se permite escribir en {PERMITIDO}")
    return destino


def escribir(destino: Path = PERMITIDO) -> list[str]:
    destino = _dentro(destino)
    destino.mkdir(parents=True, exist_ok=True)
    gen = generar()
    for n, b in gen.items():
        (destino / n).write_bytes(b)
    return sorted(gen)


def verificar(destino: Path = PERMITIDO) -> list[str]:
    """Diferencias entre el disco y lo que se generaría ahora (vacío = idéntico)."""
    destino = _dentro(destino)
    gen = generar()
    difs = []
    for n, b in gen.items():
        p = destino / n
        if not p.exists():
            difs.append(f"falta {n}")
        elif p.read_bytes() != b:
            difs.append(f"distinto {n}")
    extra = sorted(p.name for p in destino.glob("*") if p.is_file() and p.name not in gen) if destino.exists() else []
    return difs + [f"sobra {n}" for n in extra]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    if a.check:
        d = verificar()
        print("\n".join(d) if d else "fixtures idénticas a lo generado")
        return 1 if d else 0
    for n in escribir():
        print("escrito", n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
