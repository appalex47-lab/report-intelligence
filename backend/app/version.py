"""Identificación de versiones (Fase 1 · bloque de modelo; docs/CONFIGURACION_FASE1.md §6).

NO sustituye ningún mecanismo existente. Hoy el repositorio ya versiona: perfiles de importación (`Profile.version`),
plantillas (`templates/<formato>/<n>/`) y cada corrida del historial (`runs.version`). Esto solo agrega la lectura
de las versiones de los archivos de configuración y del modelo de hallazgos.

`APP_VERSION` y `ENGINE_VERSION` NO se definen aquí: la especificación los estampa al compilar el sitio
(`tools/build_site.py`, Fase 3 de implementación), y esta fase no altera el proceso de compilación.
"""
from __future__ import annotations

from . import config
from .models import MODELO_HALLAZGOS_VERSION


def versiones() -> dict:
    """Versiones identificables hoy. `None` = todavía no definido (no se inventa)."""
    return {
        "app": None,
        "motor": None,
        "modelo_hallazgos": MODELO_HALLAZGOS_VERSION,
        "configuracion": config.versiones(),
    }
