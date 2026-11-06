# Fase 5 · Cierre final

Documento redactado el 2026-11-06 **antes de la fusión** del PR #24. Un documento no puede contener el SHA de su propio commit ni el resultado del CI que lo valida; por eso los datos de fusión, publicación y release (§9–§13) se registran en el PR #24 y en el informe final de la sesión, y aquí solo figura lo verificable antes de fusionar. No sustituye `AUDITORIA_CIERRE_FASE5.md`, que conserva el dictamen anterior.

## 1. Objetivo de la Fase 5
RQ-13/14/15/19: QA estructural, de cifras y visual del PPTX exportado, anexo de calidad de datos, descarga robusta (INC-001 `data.htm`), compatibilidad de libros/plantillas y preparación de la publicación real (AC-28).

## 2. Decisiones aplicadas en este cierre
| Tema | Decisión | Dónde |
|---|---|---|
| Anexo en el PPTX | Desactivado por omisión; activación voluntaria (casilla o flag `anexo_calidad`); línea base intacta (8 de 8 idéntico) | D5-11 |
| Manifiesto | No se incorpora el resumen del anexo; mecanismos separados hasta una definición funcional | L-8, `PENDIENTES_POSTERIORES.md` §4 |
| AC-11 / AC-12 | No implementados; formalizados como pendientes (requisito, dependencias, comportamiento, criterios, pruebas, asignación) | `PENDIENTES_POSTERIORES.md` §1–2 |
| `pages.yml` | **Sin cambios**: la concurrencia cancela despliegues superados, pero no se demuestra que cause los fallos (atasco previo en `deployment_queued`, 4 despliegues anteriores correctos) | `PUBLICACION_AC28.md` §2, D5-12 |
| Narrativa GLP-1 «Mounjaro (74 %, $9.20 M)» | Intacta; sin denominador explícito; requiere decisión A-3 | L-9, `PENDIENTES_POSTERIORES.md` §3 |

## 3. Alcance ejecutado y cambios
36 archivos en el PR (25 nuevos, 11 modificados, 0 eliminados), incluidos los documentos de este cierre (`CIERRE_FINAL_FASE5.md`, `PENDIENTES_POSTERIORES.md`). Detalle en `IMPLEMENTACION_FASE5.md`. Esta ronda no cambió código: la revisión de AC-14, QA estructural/visual y descarga se hizo ejecutando de nuevo las pruebas sobre el código final y no halló defectos nuevos.

## 4. Criterios de aceptación (estado definitivo antes de la fusión)
| ID | Estado | Nota |
|---|---|---|
| RQ-13 QA estructural | PARCIALMENTE CUMPLIDO | depende de AC-14 |
| AC-14 cifras, fórmulas, unidades, denominadores | PARCIALMENTE CUMPLIDO | 9/9 mutaciones; no garantiza el 100 % de errores posibles; 1 observación real en GLP-1 (A-3) |
| RQ-14 / AC-16 QA visual | CUMPLIDO | LibreOffice, solo local |
| RQ-15 / AC-15 límites declarados | CUMPLIDO | |
| RQ-19 anexo de calidad | PARCIALMENTE CUMPLIDO | opt-in; fuera del manifiesto |
| AC-21 salida idéntica con flags apagados | CUMPLIDO | 8 de 8 |
| 3.5 compatibilidad | CUMPLIDO | plantillas anteriores: NO VERIFICABLE |
| 3.6 `data.htm` | PARCIALMENTE CUMPLIDO | mitigado; causa no demostrada; solo Chromium probado |
| AC-28 publicación real | NO VERIFICABLE | `github.io` inaccesible desde el entorno (`curl` 403, `WebFetch` ENOTFOUND) |
| AC-11 | NO CUMPLIDO · FUERA DEL ALCANCE | fase de interfaz posterior |
| AC-12 | NO CUMPLIDO · FUERA DEL ALCANCE | ídem |

## 5. Pruebas
Suite completa local, Pyodide obligatorio (`REPORT_PYODIDE_REQUIRED=1`), navegador y LibreOffice, sobre el código final: **1500 aprobadas, 0 fallidas, 35 omitidas** en 40 min 05 s. Las 35 omitidas son `tests/golden` (faltan la plantilla Q1 y el Excel Q3 reales): 8 `test_golden_deck`, 5 `test_golden_glp1`, 8 `test_golden_real_files`, 14 `test_golden_trimestral`. Ninguna omisión nueva.

## 6. Comparación de regresión
Referencia previa del PR (`c544478`): 1432 aprobadas. Última ejecución previa (`75cf2d3`): 1500/0/35. Esta ejecución: 1500/0/35 (idéntica, sin regresiones). No se eliminó ni debilitó ninguna prueba (el diff de `tests/` no tiene líneas eliminadas salvo hashes y motivos de `protegidos.json`).

## 7. Archivos protegidos y línea base
`archivos_protegidos --check`: sin cambios. `capture_baseline --check`: idéntico (motor y deck). Sin dependencias nuevas (`requirements*`, `package*.json` sin diff). Modificados con autorización documentada: `build.py`, `service.py`, `bridge.py`, `app.py`, `index.html`.

## 8. CI
Solo corren en CI `tests/unit`, `tests/regression` y `test_hash_pyodide`; las pruebas de navegador, LibreOffice y plantillas reales se ejecutaron localmente. El CI del SHA exacto a fusionar se registra en el PR #24.

## 9–13. Fusión, SHA, publicación, AC-28 y release
Se registran en el PR #24 y en el informe final tras la fusión. Condiciones inamovibles: AC-28 no se declara cumplido sin verificación real desde un navegador externo; `release.yml` con `publicar=true` solo tras esa verificación (ver `PUBLICACION_AC28.md` §5).

## 14. Pendientes posteriores
`PENDIENTES_POSTERIORES.md` (AC-11, AC-12, A-3, L-8, AC-28, `deployment_queued`, navegadores adicionales, plantillas anteriores, golden, anexo por omisión, release).

## 15. Limitaciones y riesgos
No se validó: el aspecto en PowerPoint, el sitio publicado, datos de producción, Firefox/Safari/WebViews, ni el significado de una cifra. El detector de AC-14 no es exhaustivo.

## 16. Dictamen previo a la fusión
Apto para fusionar si el CI del SHA exacto está en verde, sin conflictos con `main`. **No** equivale a «Fase 5 cerrada y verificada»: eso exige AC-28 con evidencia real.
