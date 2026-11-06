# Fase 5 · QA del PPTX, anexo de calidad de datos y descarga

| | |
|---|---|
| Alcance oficial | RQ-13 (QA **estructural** del PPTX exportado), RQ-14 (QA **visual** con render real), RQ-15 (límites del QA declarados en la interfaz), RQ-19 (anexo de calidad de datos); AC-14, AC-15, AC-16; pruebas T-11 y T-12. Fuentes: `docs/fase1/ESPECIFICACION_FASE1_REPORT_INTELLIGENCE_FINAL.md` §7 (7.A, 7.B, 7.C), §9, §11, §12, §14 y `docs/fase1/implementacion/F2B_TRAZABILIDAD.md` («No cumplido (Fase 5)») |
| Añadido por el encargo | Auditoría de cifras y compatibilidad (3.1, 3.2, 3.5), bug de descarga `data.htm` (INC-001, 3.6), validación de la publicación real (3.7) |
| Depende de | Fases 1 a 4. Se construyó sobre el contenido de los PR #22 y #23 (aún abiertos, ver `CIERRE_FASES_3_Y_4.md`) |
| Estado | **Implementada y validada localmente; PR abierto y sin fusionar. AC-28 y la validación de la publicación real NO se pudieron demostrar (§8)** |
| Fuera de alcance | Fase 6, Fase 3B, cambios de fórmulas o de `hash_resultado`, rediseño de láminas |

## 1. Interpretación documental

La especificación de Fase 1 asigna a la Fase 5 el QA del PPTX (RQ-13/14/15) y el anexo de calidad de datos (RQ-19, «Fase 5» en la trazabilidad de la 2B). El encargo agrega tareas transversales (auditoría de cifras, compatibilidad, descarga, publicación). No existe un documento titulado «Fase 5»: este alcance es la lectura de esas fuentes. Una contradicción documental: la spec (§9, RQ-19) describe el anexo como **«diapositiva final» del PPTX**, pero modificar el PPTX toca `build.py` y `deck/extras.py` (protegidos) y cambia las presentaciones; el flag `anexo_calidad` sigue desactivado. Se resolvió con la lectura conservadora: el anexo es un **panel** en «Validar» y un **archivo** `anexo_calidad.json` junto al reporte; la diapositiva no se creó (§7, L-3).

## 2. Qué se implementó

| Requisito | Componente | Archivos |
|---|---|---|
| RQ-13 · QA estructural (7.A) | Paquete (ZIP, XML, relaciones, huérfanos, imágenes, gráficas) y diapositivas (tokens técnicos, duplicados, textos, fuente mínima y familia, geometría, solape, tablas y diapositivas vacías). Umbrales **calibrados contra la plantilla**. Se ejecuta tras guardar el PPTX y suma sus hallazgos al `QAReport` | `backend/app/qa/pptx_export.py`, `backend/app/build.py` |
| RQ-15 · límites en la interfaz | La etiqueta «Revisión estructural. La revisión visual requiere render» aparece junto al resultado; el informe nunca se llama «visual» | `frontend/index.html`, `pptx_export.ETIQUETA` |
| RQ-14 · QA visual (7.B) | LibreOffice → PDF → PNG por diapositiva, comprobaciones de PDF existentes + diapositiva en blanco, gráfica en blanco, contraste muestreado en píxeles, consistencia de títulos, `informe.json` y visor `informe.html` | `backend/app/qa/visual.py`, `tools/visual_qa.py` |
| RQ-19 · anexo de calidad de datos | 15 dimensiones, evidencia por hallazgo (hoja, columna, filas de ejemplo), impacto, naturaleza y origen de los datos | `backend/app/calidad.py`, `backend/app/web/service.py`, `frontend/index.html` |
| 3.6 · descarga | `download()` endurecida: nombre y extensión de lo pedido, validación del contenido, MIME explícito, revocación tardía, aviso en navegadores integrados | `frontend/index.html` |
| 3.5 · compatibilidad | Pruebas de estructuras de libro y de plantillas | `tests/unit/test_compatibilidad.py` |
| 3.2 · cifras | Corrección de una unidad inventada («MXN») en el panel de la Fase 4 | `backend/app/escenarios.py` |

## 3. Decisiones técnicas

| ID | Decisión | Motivo |
|---|---|---|
| D5-1 | El umbral de letra mínima es `min(9 pt, mínimo de la plantilla)` | Las plantillas usan 6,5 a 8 pt legítimamente: un 9 fijo daba 319 falsos positivos en GLP-1 |
| D5-2 | Lo que la plantilla ya trae (textos con doble espacio, partes huérfanas, gráficas vacías) no es un defecto del reporte; una gráfica vacía heredada solo informa | `chartEx` vacío de la plantilla GLP-1; AC-14 exige 0 falsos positivos en decks de referencia |
| D5-3 | Los hallazgos estructurales con severidad `error` rechazan el QA (bloquean la descarga); los `warn` no | Mismo contrato del `QAReport` existente |
| D5-4 | Contraste: el color de texto es el píxel de **mayor contraste** frente al fondo (no el más alejado); umbral 2,5 | El criterio inicial (distancia de color) marcó como ilegible texto blanco sobre azul por un borde rojo; documentado en `QA_PPTX.md` |
| D5-5 | La revisión visual no corre en el navegador ni en `tests.yml`; sin LibreOffice el resultado es `omitida`, nunca `aprobada` | Spec §7.C; privacidad (A-6) |
| D5-6 | No se creó `visual-qa.yml` | La spec permite `tools/visual_qa.py` local; un workflow no validable aquí sería una afirmación sin evidencia |
| D5-7 | El anexo **nunca** afirma que los datos sean reales; solo infiere «ejemplo o sintético» por el nombre del archivo | Encargo: no presentar sintéticos como producción |
| D5-8 | La extensión del archivo descargado sale de la ruta pedida, no del motor | Causa raíz de `data.htm` no reproducible: se elimina la dependencia, no se adivina la causa |

## 4. Archivos

| Tipo | Archivos |
|---|---|
| Nuevos (código) | `backend/app/qa/pptx_export.py`, `backend/app/qa/visual.py`, `backend/app/calidad.py`, `tools/visual_qa.py` |
| Nuevos (pruebas) | `tests/unit/test_qa_pptx_export.py`, `test_qa_visual.py`, `test_calidad.py`, `test_compatibilidad.py`; `tests/e2e/descarga_regresion.mjs`, `test_descarga_regresion.py` |
| Modificados (código) | `backend/app/build.py`, `backend/app/web/service.py`, `frontend/index.html` — **protegidos, reautorizados con motivo en `tests/regression/protegidos.json`**; `backend/app/escenarios.py` |
| Modificados (pruebas) | `tests/unit/test_escenarios.py`, `tests/e2e/escenarios_panel.mjs`, `test_escenarios_panel.py` (se **amplían**; ninguna prueba existente se eliminó ni se debilitó) |
| Nuevos (docs) | `docs/fase5/*` |
| Sin cambios | `build_site.py`, workflows, contratos, `reglas.json`, `definiciones.json`, narrativa, deck, validator, líneas base, `engine_version.json`, `hash_resultado.json` |

## 5. Pruebas

Resultados y SHA en `AUDITORIA_CIERRE_FASE5.md` §3. Cobertura propia de la fase: T-11 (39 pruebas: deck limpio sin hallazgos, un defecto inyectado por prueba, casos de falsos positivos y los 4 decks reales de referencia), T-12 (14, con render real), anexo (35), compatibilidad (30), descarga en navegador (20), panel y anexo en navegador con motor real (4).

## 6. Estado de lo declarado

| Etiqueta | Elemento |
|---|---|
| VERIFICADO | QA estructural: 0 hallazgos en los 4 decks reales de referencia y detección de cada defecto inyectado; QA visual: 0 hallazgos en los 4 y detección de los 6 defectos inyectados; anexo: detecta los defectos de los libros con defectos y coincide con los hallazgos del propio motor; descarga: 20 casos en Chromium real |
| NO VERIFICADO | Los decks se generaron con libros de **ejemplo sintéticos**: no hay evidencia con datos de producción |
| NO VERIFICABLE | Cómo se ve cada diapositiva en PowerPoint (el render es de LibreOffice, con Carlito en lugar de Aptos Narrow); la gráfica `chartEx` vacía que trae la plantilla GLP-1 en PowerPoint |
| LIMITACIÓN CONOCIDA | Ver §7 |

## 7. Limitaciones

| ID | Limitación | Clase |
|---|---|---|
| L-1 | **AC-14 PARCIAL:** no existen las comprobaciones `PPTX_CIFRA_NO_TRAZADA`, `PPTX_FORMULA_NO_COINCIDE`, `PPTX_UNIDAD_AMBIGUA` y `PPTX_SIN_DENOMINADOR`. Exigen asociar cada cifra impresa de cada plantilla con su métrica; se intentó reproducir el texto de los párrafos y 2 a 3 por deck no coinciden por formato, así que su detección daría falsos positivos. Mitigación existente: la narrativa ya se verifica al generarla (`NARRATIVE_UNVERIFIED`) | Pendiente (requisito de la spec) |
| L-2 | El contraste se muestrea del render de LibreOffice: es un indicio, no una medición de accesibilidad; un píxel de alto contraste ajeno al texto puede ocultar texto ilegible | No bloqueante |
| L-3 | El anexo no es una diapositiva del PPTX (§1) | Pendiente de decisión |
| L-4 | La revisión visual no corre en el navegador ni en CI | Por diseño (spec §7.C) |
| L-5 | La holgura mínima sobre el pie fue de 3,9 pt en la diapositiva 1 del deck AETOPS mensual (sin desborde, pero justa) | Observación |
| L-6 | Rendimiento: el panel de escenarios y el anexo comparten una sola lectura del libro (caché por archivo), pero la primera lectura de un libro grande en Pyodide no se midió (solo 2,4 MB) | No verificado |
| L-7 | Plantillas anteriores: solo existe la versión 1 de cada formato; no hay versiones previas contra las que probar | No verificable |

## 8. Lo que no se pudo hacer, y por qué

* **Fusión de los PR #22 y #23:** el clasificador de permisos del entorno bloqueó la fusión («Merge Without Review») aunque el encargo la autorizaba. No se intentó por otra vía.
* **Validación real de GitHub Pages y AC-28:** requiere `main` actualizado, un despliegue y una publicación real; además el entorno no alcanza `github.io` ni la API de Pages (HTTP 000 y 403 del proxy). AC-28 **permanece NO DEMOSTRADO**.
* **Release y etiqueta:** no se crearon: las condiciones del encargo (PR integrados, versión publicada comprobada, criterios obligatorios verificados) no se cumplen.
