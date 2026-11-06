# Fase 5 · Auditoría de cierre

| | |
|---|---|
| Alcance auditado | `docs/fase5/IMPLEMENTACION_FASE5.md`, `QA_PPTX.md`, `ANEXO_CALIDAD_DATOS.md`, `DESCARGA_DATA_HTM.md`, `CIERRE_FASES_3_Y_4.md` |
| Método | Pruebas ejecutadas de nuevo sobre el código final, inspección visual de los decks generados, medición directa y revisión de cada afirmación documental contra el código. No reescribe ninguna auditoría anterior |
| Base | Contenido de los PR #22 (`abf651b`) y #23 (`27c106b`) sobre `main` en `f15abfea707c1f0adcdedcc6d94ddcbc2024226e`; ambos PR **siguen abiertos** (la fusión fue bloqueada por el entorno, ver `CIERRE_FASES_3_Y_4.md` §1) |

## 1. Criterios mínimos del encargo para «lista para revisión»

| # | Criterio | Estado | Evidencia |
|---|---|---|---|
| 1 | Alcance de la Fase 5 atendido | **PARCIAL** | RQ-14 y RQ-15 cumplidos; RQ-13 **parcial** (AC-14: faltan cifras, fórmulas, unidades y denominadores, L-1); RQ-19 **parcial** (panel y archivo, no diapositiva, L-3) |
| 2 | AC-11 y AC-12 resueltos si corresponde a su alcance, con evidencia de interfaz | **NO CUMPLIDOS** | No corresponden a la Fase 5 (RQ-13/14/15/19); la interfaz no los muestra (`CIERRE_FASES_3_Y_4.md` §2) |
| 3 | AC-28 demostrado mediante publicación real | **NO DEMOSTRADO** | `main` no cambió, el entorno no alcanza `github.io` ni la API de Pages, y no hay condiciones para publicar |
| 4 | Auditoría de calidad de datos documentada | **CUMPLIDO** | `ANEXO_CALIDAD_DATOS.md`, 35 pruebas |
| 5 | PPTX validado estructural y visualmente | **CUMPLIDO con límites** | `QA_PPTX.md`: 49 diapositivas inspeccionadas; 0 hallazgos en los 4 decks de referencia; L-2, L-5, V-5 |
| 6 | Bug `data.htm` corregido y cubierto por pruebas | **MITIGADO; causa NO demostrada** | Se endureció la descarga y se cubrió con 20 casos en Chromium real; la causa original no se reprodujo (`DESCARGA_DATA_HTM.md`) |
| 7 | Compatibilidad evaluada | **CUMPLIDO** (plantillas anteriores: no verificable) | 30 pruebas (`test_compatibilidad.py`) |
| 8 | Sin regresiones en lo protegido | **CUMPLIDO** | §3 y §4 |
| 9 | CI verde sobre el SHA exacto del PR | **ver el informe y el PR** | se registra tras publicar el HEAD definitivo |
| 10 | Documentación completa | **CUMPLIDO** | `docs/fase5/*` |
| 11 | Evidencia reproducible | **CUMPLIDO** | comandos y SHA en §3; los decks se regeneran con `tools/capture_baseline` y `tools/visual_qa.py` |
| 12 | Sin defectos bloqueantes conocidos sin declarar | **CUMPLIDO** | §2 y §5 |

## 2. Defectos hallados y corregidos durante la fase

| ID | Severidad | Defecto | Dónde se detectó | Corrección |
|---|---|---|---|---|
| F5-1 | ALTO | El panel de la Fase 4 rotulaba los montos como «MXN»: **unidad inventada**, ningún libro declara la moneda | revisión del anexo | `unidad: "moneda"` + nota «la moneda no está declarada»; prueba que lo impide |
| F5-2 | MEDIO | `PPTX_DIAPOSITIVA_VACIA` nunca saltaba: una diapositiva sin formas no se revisaba | prueba de defecto inyectado | se recorren todas las diapositivas |
| F5-3 | MEDIO | Un paquete con relación rota hacía lanzar una excepción técnica | prueba de relación rota | cualquier excepción es un hallazgo `PPTX_ZIP` |
| F5-4 | MEDIO | La revisión visual lanzaba `BadZipFile` con un archivo que no es PPTX | prueba de archivo no renderizable | resultado `error` controlado |
| F5-5 | MEDIO | Umbral de letra fijo de 9 pt: 319 falsos positivos en decks reales | calibración con decks de referencia | umbral calibrado con la plantilla (D5-1) |
| F5-6 | BAJO | Gráfica vacía heredada de la plantilla marcada como error | calibración | se compara contra la plantilla (D5-2) |
| F5-7 | MEDIO | El criterio de contraste marcó texto blanco sobre azul como ilegible (1,29) por un borde rojo dentro de la caja | calibración | color de texto = píxel de mayor contraste (D5-4); 2 pruebas |
| F5-8 | ALTO | `extensionPedida` aceptaba extensiones de 2 a 5 letras: el historial `.sqlite` se habría descargado como `historial.sqlite.bin` | prueba de regresión de descarga | admite 2 a 6 letras |
| F5-9 | BAJO | Mis pruebas construían mal las variantes «columnas invertidas» (movían valores sin su formato de fecha y corrompían el libro) | falla de la prueba | construcción corregida; no era un defecto del producto |

## 3. Pruebas (código final, sin cambios posteriores)

| Prueba | Resultado |
|---|---|
| Suite completa local, con Pyodide obligatorio (`REPORT_PYODIDE_REQUIRED=1`), `REPORT_PYODIDE_WORK`, `REPORT_PYODIDE_DIR` y LibreOffice | **1432 aprobadas, 0 fallidas, 35 omitidas** (37 min 48 s). Por carpeta: unit 1315, regresión 90, e2e 27, golden 35 omitidas. Las 35 omitidas son todas de `tests/golden` (faltan las plantillas/Excel reales trimestrales); 0 omitidas fuera de esa carpeta. Referencia anterior (PR #23): 1292 → +140 |
| T-11 `test_qa_pptx_export.py` | 39 aprobadas: deck limpio sin hallazgos; un defecto inyectado por prueba (tokens, duplicado, letra, fuente ajena, fuera de lienzo, solape, tablas y diapositivas vacías, ZIP, XML, relación rota, huérfano, imagen, gráfica); 4 decks reales de referencia con 0 hallazgos y defectos inyectados detectados |
| T-12 `test_qa_visual.py` | 14 aprobadas con render real (6 defectos inyectados detectados; deck limpio, texto claro sobre fondo oscuro, gráfica con datos y títulos alineados sin falsos positivos; 2 decks reales) |
| Anexo `test_calidad.py` | 35 aprobadas (libros limpios, con defectos y variantes con defectos inyectados; origen nunca «real»; servicio) |
| Compatibilidad `test_compatibilidad.py` | 30 aprobadas (variantes estructurales idénticas al original, hojas y columnas ausentes, periodo vacío, plantillas) |
| Descarga `tests/e2e/test_descarga_regresion.py` | 20 aprobadas en Chromium real |
| Panel y anexo en navegador `test_escenarios_panel.py` | 4 aprobadas con el motor real en Pyodide (GLP-1, AETOPS y formatos antiguos; sin errores de consola) |
| `test_hash_pyodide` | aprobada (hash canónico en Pyodide = CPython) |
| `archivos_protegidos --check` / `capture_baseline --check` | sin cambios / 8 de 8 idéntico (motor y deck) |

**Qué validan:** que cada defecto inyectado se detecte con su `id` y que los decks de referencia den 0 hallazgos; que el anexo coincida con los hallazgos del propio motor; que la descarga no pueda llamarse `data.htm` ni entregar HTML como PPTX. **Qué no validan:** cómo se ve en PowerPoint, la causa original de `data.htm`, datos de producción, Firefox/Safari/WebViews, rendimiento con libros grandes en el navegador, ni (L-1) la trazabilidad de cada cifra impresa.

**Qué corre en CI (`tests.yml`):** `tests/unit`, `tests/regression` y solo `test_hash_pyodide`. Las pruebas de navegador, las de LibreOffice (T-12) y las que usan plantillas reales **no corren en CI** (requieren Playwright, LibreOffice o archivos no versionados) y se omiten con motivo; se ejecutaron localmente.

## 4. Regresiones y archivos protegidos

* Modificados con autorización documentada en `tests/regression/protegidos.json` (motivos anteriores conservados): `backend/app/build.py`, `backend/app/web/service.py`, `frontend/index.html`.
* Sin ninguna modificación: `build_site.py`, los cuatro workflows, contratos, `reglas.json`, `definiciones.json`, narrativa, deck, validator, líneas base, `engine_version.json`, `hash_resultado.json`, `procedencia`.
* `hash_resultado` y `ENGINE_VERSION` no cambian; los decks de la línea base son idénticos (8 de 8): la revisión estructural suma hallazgos al QA, no modifica el PPTX.
* No se eliminó ni se debilitó ninguna prueba existente: solo se ampliaron `test_escenarios.py`, `escenarios_panel.mjs` y `test_escenarios_panel.py`.

## 5. Observaciones, limitaciones y pendientes

Ver `IMPLEMENTACION_FASE5.md` §7 y §8, `QA_PPTX.md` §3 y `CIERRE_FASES_3_Y_4.md`. Resumen: **pendientes obligatorios** — AC-14 parcial (L-1), anexo no es diapositiva (L-3, decisión), AC-11/AC-12 sin presentación, AC-28 sin demostrar, validación de la publicación real, fusión de los PR #22 y #23; **no bloqueantes** — contraste muestreado, holgura de 3,9 pt, `chartEx` de la plantilla GLP-1 no verificable sin PowerPoint, plantillas anteriores inexistentes.

## 6. Dictamen

**NO APROBADO** como «lista para revisión» según los criterios mínimos del encargo, **no por defectos del código** (la implementación está completa y validada: 1432 pruebas, 0 fallidas) sino porque dos criterios obligatorios no se pueden demostrar con lo disponible: **AC-28** (publicación real) y la **integración** de los PR #22 y #23 (bloqueada por el entorno), de la que depende la validación de la publicación. Además AC-14, RQ-19 y AC-11/AC-12 quedan parciales o sin cumplir (§1). Cambiaría a «aprobado con observaciones» cuando: (a) se fusionen los PR #22 y #23, (b) se publique y verifique el sitio real y una release, (c) se decida lo de AC-11/AC-12, la diapositiva del anexo y las comprobaciones de cifras (L-1).
