"""Identificación de versiones (docs/CONFIGURACION_FASE1.md §6; Fase 3A-1, docs/fase3a/ESPECIFICACION_FASE3A_PROCEDENCIA.md §4).

NO sustituye ningún mecanismo existente. El repositorio ya versiona: perfiles de importación (`Profile.version`), plantillas
(`templates/<formato>/<n>/`), cada corrida del historial (`runs.version`) y los archivos de configuración (`config.versiones()`).
Este módulo agrega la identificación formal de la aplicación y del motor:

* `APP_VERSION` y `ENGINE_VERSION` (SemVer). `1.0.0` es la **primera versión formalmente identificada bajo este esquema**; no es el
  inicio histórico del proyecto. La política de incremento está en la especificación de la Fase 3A (§4.1).
* El SHA del commit con el que se compiló el sitio. Lo escribe `tools/build_site.py` en `backend/app/_build_info.json` **dentro de
  `app.zip`** (no es un archivo del repositorio) y aquí solo se lee. No se ejecuta git en tiempo de ejecución.

Estados de la identidad del commit (`compilacion.estado`):

* `limpia`      — commit identificado y árbol sin cambios al compilar.
* `dirty`       — commit identificado, pero el árbol tenía cambios (`<sha>+dirty`): NO es una compilación reproducible del commit limpio.
* `desconocida` — no hay información suficiente (falta `_build_info.json`, está dañado o no tiene un SHA válido). No es un error.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import config
from .models import MODELO_HALLAZGOS_VERSION

APP_VERSION = "1.0.0"
ENGINE_VERSION = "1.0.0"

COMMIT_DESCONOCIDO = "desconocido"
BUILD_INFO = Path(__file__).with_name("_build_info.json")
BUILD_INFO_ESQUEMA = "build_info/1"
_COMMIT = re.compile(r"^[0-9a-f]{40}(\+dirty)?$")
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def commit() -> str:
    """SHA del commit con el que se compiló esta copia (`<sha>` o `<sha>+dirty`), o `"desconocido"`.

    Nunca lanza: un archivo ausente, ilegible, con otro formato o con un SHA mal formado equivale a «desconocido»."""
    try:
        datos = json.loads(BUILD_INFO.read_text(encoding="utf-8"))
        valor = datos.get("commit") if isinstance(datos, dict) else None
    except (OSError, ValueError):
        return COMMIT_DESCONOCIDO
    return valor if isinstance(valor, str) and _COMMIT.match(valor) else COMMIT_DESCONOCIDO


def compilacion() -> dict:
    """Identidad de la compilación: `{"commit": ..., "sha": <40 hex | None>, "estado": limpia | dirty | desconocida}`."""
    c = commit()
    if c == COMMIT_DESCONOCIDO:
        return {"commit": c, "sha": None, "estado": "desconocida"}
    sucio = c.endswith("+dirty")
    return {"commit": c, "sha": c.removesuffix("+dirty"), "estado": "dirty" if sucio else "limpia"}


def versiones() -> dict:
    """Versiones identificables: aplicación, motor, commit de la compilación, modelo de hallazgos y configuración."""
    return {
        "app": APP_VERSION,
        "motor": ENGINE_VERSION,
        "commit": commit(),
        "compilacion": compilacion(),
        "modelo_hallazgos": MODELO_HALLAZGOS_VERSION,
        "configuracion": config.versiones(),
    }
