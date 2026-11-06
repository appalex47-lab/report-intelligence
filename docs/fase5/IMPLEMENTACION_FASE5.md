# Fase 5 · QA del PPTX, anexo de calidad de datos y descarga

| | |
|---|---|
| Alcance oficial | RQ-13 (QA **estructural** del PPTX exportado), RQ-14 (QA **visual** con render real), RQ-15 (límites del QA declarados en la interfaz), RQ-19 (anexo de calidad de datos); AC-14, AC-15, AC-16; pruebas T-11 y T-12. Fuentes: `docs/fase1/ESPECIFICACION_FASE1_REPORT_INTELLIGENCE_FINAL.md` §7 (7.A, 7.B, 7.C), §9, §11, §12, §14 y `docs/fase1/implementacion/F2B_TRAZABILIDAD.md` («No cumplido (Fase 5)») |
| Añadido por el encargo | Auditoría de cifras y compatibilidad (3.1, 3.2, 3.5), bug de descarga `data.htm` (INC-001, 3.6), validación de la publicación real (3.7) |
| Depende de | Fases 1 a 4, **ya integradas en `main`** (PR #22 y #23 fusionados; ver `CIERRE_FASES_3_Y_4.md`) |
| Estado | **Implementada y validada localmente; PR #24 abierto y sin fusionar. AC-28 y la validación de la publicación real siguen NO DEMOSTRADOS (§8)** |
| Fuera de alcance | Fase 6, Fase 3B, cambios de fórmulas o de `hash_resultado`, rediseño de láminas |

## 1. Interpretación documental (revisada en esta ejecución)

La especificación de Fase 1 asigna a la Fase 5 el QA del PPTX (RQ-13/14/15) y el anexo de calidad de datos (RQ-19, «Fase 5» en la trazabilidad de la 2B). El encargo agrega tareas transversales (auditoría de cifras, compatibilidad, descarga, publicación). No existe un documento titulado «Fase 5»: este alcance es la lectura de esas fuentes. **Anexo (resuelta):** la especificación exige una **diapositiva final** (§6 punto 7, RQ-19, T-11) además del panel y el manifiesto; se implementó como **opt-in** (flag `anexo_calidad` apagado por omisión para conservar la línea base, AC-21), ver `ANEXO_CALIDAD_DATOS.md` §4. **AC-11 y AC-12:** la documentación los asigna a una «fase de interfaz posterior» sin numerar; no son alcance de la Fase 5 (`AC11_AC12.md`).

## 2. Qué se implementó

| Requisito | Componente | Archivos |
|---|---|---|
| RQ-13 · QA estructural (7.A) | Paquete (ZIP, XML, relaciones, huérfanos, imágenes, gráficas) y diapositivas (tokens técnicos, duplicados, textos, fuente mínima y familia, geometría, solape, tablas y diapositivas vacías). Umbrales **calibrados contra la plantilla**. Se ejecuta tras guardar el PPTX y suma sus hallazgos al `QAReport` | `backend/app/qa/pptx_export.py`, `backend/app/build.py` |
| RQ-13 / AC-14 · cifras, fórmulas, unidades, denominadores | Trazabilidad de cifras contra los valores del motor (con tolerancia por precisión impresa), Ticket = Monto ÷ Pedidos, variación = actual ÷ anterior − 1, unidades por columna, moneda inventada y base de los porcentajes (`AC14_CIFRAS_FORMULAS.md`) | `backend/app/qa/cifras.py`, `backend/app/build.py` |
| RQ-15 · límites en la interfaz | La etiqueta «Revisión estructural. La revisión visual requiere render» aparece junto al resultado; el informe nunca se llama «visual» | `frontend/index.html`, `pptx_export.ETIQUETA` |
| RQ-14 · QA visual (7.B) | LibreOffice → PDF → PNG por diapositiva, comprobaciones de PDF existentes + diapositiva en blanco, gráfica en blanco, contraste muestreado en píxeles, consistencia de títulos, `informe.json` y visor `informe.html` | `backend/app/qa/visual.py`, `tools/visual_qa.py` |
| RQ-19 · anexo de calidad de datos | 15 dimensiones, evidencia por hallazgo (hoja, columna, filas de ejemplo), impacto, naturaleza y origen de los datos; panel, `anexo_calidad.json` y **diapositiva final opt-in** | `backend/app/calidad.py`, `backend/app/deck/anexo.py`, `backend/app/web/service.py`, `frontend/index.html` |
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
| D5-9 | Las comprobaciones de AC-14 son `warn` y no bloquean | Son heurísticas sobre texto; un falso positivo no debe impedir entregar un reporte válido |
| D5-10 | La derivación de un porcentaje se acota a la misma celda/párrafo o a las formas `RI_*` | Con todos los números de la lámina, un porcentaje alterado pasaba por «derivable» por coincidencia |
| D5-11 | **Decidido por el usuario:** el anexo en el PPTX es opt-in (casilla o flag) y **no se activa por omisión** | Activarlo por omisión cambiaría la línea base de los decks (8 de 8 idénticos con el anexo apagado) |
| D5-12 | **Decidido:** no se modifica `pages.yml`. La concurrencia cancela despliegues superados (run 19) pero no se demuestra que cause los fallos del run 20 (atasco previo en `deployment_queued`; 4 despliegues anteriores correctos con la misma configuración) | Autorización condicionada a demostrar la necesidad; `PUBLICACION_AC28.md` §2 |
| D5-7 | El anexo **nunca** afirma que los datos sean reales; solo infiere «ejemplo o sintético» por el nombre del archivo | Encargo: no presentar sintéticos como producción |
| D5-8 | La extensión del archivo descargado sale de la ruta pedida, no del motor | Causa raíz de `data.htm` no reproducible: se elimina la dependencia, no se adivina la causa |

## 4. Archivos

| Tipo | Archivos |
|---|---|
| Nuevos (código) | `backend/app/qa/pptx_export.py`, `backend/app/qa/cifras.py`, `backend/app/qa/visual.py`, `backend/app/calidad.py`, `backend/app/deck/anexo.py`, `tools/visual_qa.py` |
| Nuevos (pruebas) | `tests/unit/test_qa_pptx_export.py`, `test_qa_cifras.py`, `test_qa_visual.py`, `test_anexo_pptx.py`, `test_calidad.py`, `test_compatibilidad.py`; `tests/e2e/descarga_regresion.mjs`, `test_descarga_regresion.py` |
| Modificados (código) | `backend/app/build.py`, `backend/app/web/service.py`, `backend/app/web/bridge.py`, `backend/app/web/app.py`, `frontend/index.html` — **protegidos, reautorizados con motivo en `tests/regression/protegidos.json`** (motivos anteriores conservados); `backend/app/escenarios.py`, `backend/app/calidad.py` |
| Modificados (pruebas) | `tests/unit/test_escenarios.py`, `tests/e2e/escenarios_panel.mjs`, `test_escenarios_panel.py` (se **amplían**; ninguna prueba existente se eliminó ni se debilitó) |
| Nuevos (docs) | `docs/fase5/*` (incluye `AC14_CIFRAS_FORMULAS.md`, `AC11_AC12.md`, `PUBLICACION_AC28.md`) |
| Sin cambios | `build_site.py`, workflows, contratos, `reglas.json`, `definiciones.json`, narrativa, deck, validator, líneas base, `engine_version.json`, `hash_resultado.json` |

## 5. Pruebas

Resultados y SHA en `AUDITORIA_CIERRE_FASE5.md` §3 (suite completa: 1500 aprobadas, 0 fallidas, 35 omitidas). Cobertura propia de la fase: T-11 (39: deck limpio sin hallazgos, un defecto inyectado por prueba, falsos positivos y los 4 decks reales), AC-14 (55: cifras, fórmulas, unidades, denominadores, fuentes distintas, redondeos, valores vacíos y cero, 4 decks reales; 9 mutaciones detectadas de 9), T-12 (14, con render real), anexo (35 + 12 de la diapositiva), compatibilidad (30), descarga en Chromium real (21, con archivos reales de cada formato), panel y anexo con el motor real en Pyodide (4).

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
| L-1 | **AC-14 PARCIALMENTE CUMPLIDO** (`AC14_CIFRAS_FORMULAS.md` §6): las cuatro comprobaciones existen y detectan los defectos inyectados con 0 falsos positivos, pero no validan el significado de una cifra, dependen del reconocimiento por encabezado y una cifra alterada puede coincidir por azar con otro valor del motor | Observación |
| L-2 | El contraste se muestrea del render de LibreOffice: es un indicio, no una medición de accesibilidad; un píxel de alto contraste ajeno al texto puede ocultar texto ilegible | No bloqueante |
| L-3 | El anexo en el PPTX es opt-in; no se activa por omisión (D5-11, decidido) | Decisión tomada |
| L-4 | La revisión visual no corre en el navegador ni en CI | Por diseño (spec §7.C) |
| L-5 | La holgura mínima sobre el pie fue de 3,9 pt en la diapositiva 1 del deck AETOPS mensual (sin desborde, pero justa) | Observación |
| L-6 | Rendimiento: el panel de escenarios y el anexo comparten una sola lectura del libro (caché por archivo), pero la primera lectura de un libro grande en Pyodide no se midió (solo 2,4 MB) | No verificado |
| L-7 | Plantillas anteriores: solo existe la versión 1 de cada formato; no hay versiones previas contra las que probar | No verificable |
| L-8 | **Decidido por el usuario:** el resumen del anexo no se incorpora todavía al manifiesto; el anexo (panel, JSON y diapositiva) y el manifiesto de procedencia siguen siendo mecanismos separados hasta que exista una definición funcional completa | Contrato 3A congelado; ver `PENDIENTES_POSTERIORES.md` |
| L-9 | **Decidido por el usuario:** la narrativa protegida «Mounjaro (74 %, $9.20 M)» no se modifica; el porcentaje carece de denominador explícito y requiere una decisión narrativa A-3 posterior. No se inventa una base de cálculo ni se altera la cifra para eliminar la advertencia | Fuera de alcance; `PENDIENTES_POSTERIORES.md` |

## 8. Lo que no se pudo hacer, y por qué

* **Validación real de GitHub Pages y AC-28:** el despliegue de `47dc3af` terminó en success tras 3 fallos de `deploy-pages` y 1 éxito (run 20), pero el entorno no alcanza `github.io` (el proxy devuelve 403 en el túnel, también para `example.com`), la API de Pages y la descarga del artefacto. **AC-28 permanece NO DEMOSTRADO**; el procedimiento exacto y las verificaciones externas están en `PUBLICACION_AC28.md`.
* **Release y etiqueta:** no se crearon (no hay autorización de fusión del PR #24 ni versión publicada comprobada).
* **Firefox, Safari y WebViews:** no disponibles en el entorno (solo Chromium).
