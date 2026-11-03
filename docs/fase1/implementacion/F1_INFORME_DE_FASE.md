# Informe de la Fase 1 de implementación — Modelo y línea base

Documentos relacionados: `docs/LINEA_BASE_FASE1.md` (antes/después), `docs/MODELO_HALLAZGOS.md`, `docs/CONFIGURACION_FASE1.md`, `docs/fase1/implementacion/F1_AUDITORIA_Y_LINEA_BASE.md`.

## A. Estado general
| Dato | Valor |
|---|---|
| Estado | **Completa dentro del alcance acordado** (modelo y línea base). No se avanzó a la Fase 2 |
| Rama | `claude/awesome-wozniak-f35r21` (independiente de `main`; `main` no se tocó) |
| Commit inicial | `6e1104d` (`main`, árbol limpio) |
| Commit de línea base | `386099b` |
| Commit final | el último de la rama tras este informe (ver `git log`) |

## B. Trabajo realizado
| Entregable | Dónde |
|---|---|
| Auditoría de la arquitectura actual | `docs/fase1/implementacion/F1_AUDITORIA_Y_LINEA_BASE.md`; resumen en `docs/ARQUITECTURA.md` §17 |
| Línea base reproducible y referencia de regresión congelada | `tools/capture_baseline.py`, `tests/regression/` (13 pruebas), `docs/LINEA_BASE_FASE1.md` |
| `Finding` evolucionado de forma compatible | `backend/app/models.py` (siete campos opcionales por palabra clave, derivación y coherencia con `severity`, `to_dict()`) |
| Catálogo de definiciones validado | `backend/app/config/definiciones.json` (9 definiciones ya documentadas en la especificación) |
| Contratos de configuración con validación estructural | `backend/app/config/` (`reglas.json`, `mapeo_columnas.json`, `validacion_registro.json`, cargador y validadores) |
| Versionamiento preparado | `backend/app/version.py` (modelo de hallazgos y versión de cada JSON; `app` y `motor` = `None`) |
| Fixtures sintéticas deterministas | `tools/make_fixtures_fase1.py`, `tests/fixtures/fase1/` (7 archivos, manifiesto con SHA-256, `sintetico: true`) |
| 47 pruebas de compatibilidad, catálogo/configuración y fixtures | `tests/unit/test_hallazgo_compat.py`, `test_config_fase1.py`, `test_fixtures_fase1.py` |
| Documentación | `docs/MODELO_HALLAZGOS.md`, `docs/CONFIGURACION_FASE1.md`, `docs/LINEA_BASE_FASE1.md`, notas en `docs/ARQUITECTURA.md` y `docs/CONTRATO_DATOS.md` |

## C. Trabajo no realizado (y por qué)
- Las cinco reglas, IND-01, E1/E2 parametrizados, anexo de calidad, QA estructural y visual, anonimización, procedencia completa: **fuera del alcance de esta fase**.
- `APP_VERSION` / `ENGINE_VERSION`: requieren estampar la versión al compilar el sitio (`tools/build_site.py`); esta fase no altera la compilación. `version.versiones()` devuelve `None` para ambos.
- `validator/catalogo.py` (mapa de `id` histórico a `tipo/gravedad/estado/efecto`): es de la fase de reglas.
- Cablear los campos nuevos a la API/interfaz: `web.service._finding` se dejó intacto a propósito.
- Ampliar `tests.yml` para que CI ejecute `tests/regression`: no se modificó ningún workflow (decisión pendiente, ver F).
- Ejecución en Python 3.12 (CI) y en Pyodide: no se hizo; solo Python 3.13.

## D. Pruebas
| Prueba | Resultado | Evidencia |
|---|---|---|
| Línea base | 181 passed / 0 failed / 0 skipped en 526,6 s (`6e1104d`); foto del motor y del deck capturada y determinista | `docs/LINEA_BASE_FASE1.md` §2; `tests/regression/base/` |
| Compatibilidad del modelo | 17 pruebas aprobadas (firma histórica, posicionales, `severity`, serialización, omisión y uso por palabra clave, derivación, incoherencia, `has_blockers`, interfaz) | `tests/unit/test_hallazgo_compat.py` |
| Catálogo y configuración | 23 aprobadas (lectura, esquema, versiones, campos obligatorios, ids únicos, definición inexistente, valor no configurado = `null`, sin deriva con el código, sin identificadores de carrito) | `tests/unit/test_config_fase1.py` |
| Fixtures | 7 aprobadas (mismos hashes en dos generaciones, `sintetico: true`, manifiesto, confinamiento al directorio, sin datos reales) | `tests/unit/test_fixtures_fase1.py`; `tools/make_fixtures_fase1.py --check` |
| Suite unitaria | **228 passed**, 0 failed, 0 skipped, 506,3 s | junit y log de la ejecución; `docs/LINEA_BASE_FASE1.md` |
| Regresión (`tests/regression`) | 13 passed; `capture_baseline --check`: 4 escenarios idénticos en motor y deck | `docs/LINEA_BASE_FASE1.md` |
| Suite golden | **35 omitidas**: faltan `REPORT_FIXTURES_DIR` y los archivos reales; no se simuló | Ejecución real: `35 skipped` |

Las pruebas de la especificación T-01 a T-22 siguen **Pendientes**; lo anterior son pruebas de esta fase, no su aprobación.

## E. Regresiones
**Ninguna.** Las 181 pruebas originales siguen aprobadas sin editarse; la foto del motor, los hallazgos, la narrativa y las huellas del deck son idénticos; `severity` y los `id` históricos se conservan. La única modificación de código existente es `Finding` en `models.py` (+48 líneas, solo aditiva).

## F. Riesgos y decisiones que requieren autorización
| # | Riesgo / decisión | Nivel |
|---|---|---|
| 1 | `models.py` lo importan 28 módulos. El cambio es aditivo y la suite lo cubre, pero no se ejecutó en Pyodide ni en Python 3.12 | Medio |
| 2 | `Finding` ahora lanza `ValueError` si se aportan campos nuevos inválidos o incoherentes (los constructores históricos no se ven afectados). Las fases de reglas deben construir hallazgos con cuidado | Bajo |
| 3 | `tests/fixtures/` (directorio) convive con `tests/fixtures.py` (módulo); hoy el módulo tiene prioridad y la suite lo confirma, pero es una fragilidad de nombres que fija la especificación | Bajo |
| 4 | Los valores heredados (25 %, 10 %, 20 %) quedan registrados en `reglas.json` y en el código: hay una prueba anti-deriva, pero dos fuentes hasta que una fase posterior haga leer el JSON al código | Bajo |
| 5 | **Decisión:** ¿ampliar `tests.yml` para ejecutar `tests/regression` en CI? (no se tocó ningún workflow) | Requiere autorización |
| 6 | **Decisión:** ¿confirmar la ubicación `backend/app/config/` (en lugar de un `config/` en la raíz)? Se eligió por compatibilidad con el empaquetado del sitio | Requiere confirmación |
| 7 | **Decisión:** autorizar el inicio de la Fase 2 (reglas). Sigue pendiente; no se avanzó | Requiere autorización |

## G. Entregables
Rutas listadas en B. Paquete ZIP de la fase y su inventario de cambios: ver §I.

## H. Recomendación
Lista para **revisión humana**. No se declara aprobada ninguna prueba de la especificación; lo que se demostró es compatibilidad y ausencia de regresiones sobre datos sintéticos.

---

## I. Inventario de cambios
| Archivo | Acción | Motivo | Riesgo |
|---|---|---|---|
| `tools/capture_baseline.py` | Creado (commit `386099b`) | Captura/comparación de la línea base | Bajo |
| `tests/regression/test_linea_base.py` | Creado (`386099b`) | Mecanismo anti-regresión | Bajo |
| `tests/regression/base/engine/*.json` (4) | Creados (`386099b`) | Foto del motor y hallazgos | Bajo |
| `tests/regression/base/deck/*.json` (4) | Creados (`386099b`) | Huellas del deck y narrativa | Bajo |
| `docs/fase1/implementacion/F1_AUDITORIA_Y_LINEA_BASE.md` | Creado (`386099b`); **modificado** después (línea de estado) | Auditoría del estado actual | Bajo |
| `backend/app/models.py` | **Modificado** (+48 líneas) | Evolución compatible de `Finding` | Medio |
| `backend/app/config/__init__.py` | Creado | Cargador y validadores estructurales | Bajo |
| `backend/app/config/definiciones.json` | Creado | Catálogo de definiciones | Bajo |
| `backend/app/config/reglas.json` | Creado | Parámetros, flags y dimensiones | Bajo |
| `backend/app/config/mapeo_columnas.json` | Creado | Alias de columnas (vacío) | Bajo |
| `backend/app/config/validacion_registro.json` | Creado | Registro de validación por regla | Bajo |
| `backend/app/version.py` | Creado | Lectura de versiones | Bajo |
| `tools/make_fixtures_fase1.py` | Creado | Generador determinista de fixtures | Bajo |
| `tests/fixtures/fase1/*.json` (7, con `manifest.json`) | Creados | Fixtures sintéticas | Bajo |
| `tests/unit/test_hallazgo_compat.py` | Creado | Compatibilidad de `Finding` | Bajo |
| `tests/unit/test_config_fase1.py` | Creado | Catálogo y configuración | Bajo |
| `tests/unit/test_fixtures_fase1.py` | Creado | Fixtures | Bajo |
| `docs/MODELO_HALLAZGOS.md` | Creado | Documentación del modelo | Bajo |
| `docs/CONFIGURACION_FASE1.md` | Creado | Documentación de la configuración | Bajo |
| `docs/LINEA_BASE_FASE1.md` | Creado | Antes/después | Bajo |
| `docs/ARQUITECTURA.md` | **Modificado** (+16, apartado §17 al final) | Registrar lo implementado | Bajo |
| `docs/CONTRATO_DATOS.md` | **Modificado** (+8, nota al final) | Declarar que el contrato no cambió | Bajo |
| `docs/fase1/implementacion/F1_INFORME_DE_FASE.md` | Creado | Este informe | Bajo |

No se eliminó ningún archivo. No se modificaron: plantillas, importadores, `raw/`, `rules.py`, `glp1_exec.py`, narrativa, IA, workflows, perfiles, datos de ejemplo, láminas, fórmulas ni porcentajes.

## J. Criterios de aceptación de la fase
| # | Criterio | Estado |
|---|---|---|
| 1 | Arquitectura actual documentada | Cumplido |
| 2 | Línea base registrada y reproducible | Cumplido |
| 3 | Referencia de regresión congelada | Cumplido |
| 4 | Modelo de hallazgos compatible | Cumplido (17 pruebas) |
| 5 | `severity` intacto | Cumplido |
| 6 | Catálogo con estructura validada | Cumplido |
| 7 | Contratos de configuración documentados | Cumplido |
| 8 | Fixtures deterministas | Cumplido |
| 9 | Pruebas de compatibilidad aprobadas | Cumplido |
| 10 | Sin regresiones atribuibles en la suite unitaria | Cumplido (228/228) |
| 11 | Sin cambios en fórmulas ni resultados históricos | Cumplido (foto idéntica) |
| 12 | Sin cambios en plantillas ni láminas | Cumplido |
| 13 | Sin funcionalidades de fases posteriores | Cumplido |
| 14 | Documentación refleja lo implementado | Cumplido |
| 15 | Evidencia reproducible | Cumplido (`docs/LINEA_BASE_FASE1.md` §5) |

## K. Reproducir
Ver `docs/CONFIGURACION_FASE1.md` §7 y `docs/LINEA_BASE_FASE1.md` §5.
