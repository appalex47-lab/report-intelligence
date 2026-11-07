# Bloque integral: escenarios y SlideSpec, diseño adaptativo, QA y previsualización

Documento técnico de lo que **quedó implementado** en la rama `claude/bloque-integral-slidespec-adaptativo-qa` (un único PR hacia `main`, sin fusionar). Describe el código real; no declara terminado nada que no tenga evidencia. No modifica los documentos de cierre de la Fase 5 ni su dictamen (`docs/fase5/*` no se tocó).

## 1. Punto de partida y decisiones

Antes de programar se inspeccionó el repositorio: **«SlideSpec», «diseño adaptativo» y «previsualización» no están definidos en ninguna especificación ni roadmap del repositorio** (no existe un documento de hoja de ruta). Los únicos «escenarios» de la especificación son los financieros E1/E2 (Fase 4), que ya estaban implementados y no se tocaron. Por eso los requisitos de este bloque son los del prompt de trabajo y, donde la documentación no define algo, se tomó la solución más conservadora y se registró aquí.

| # | Decisión | Motivo |
|---|---|---|
| D-1 | **El SlideSpec se deriva del PPTX generado**; no lo genera. Los constructores por plantilla (`deck/`, `build.py`) siguen siendo la fuente del contenido. | Reescribirlos habría roto la equivalencia con la línea base (AC-21) y el contenido protegido. Consecuencia: el SlideSpec describe, valida y hace trazable cada diapositiva, pero **no hay un editor de SlideSpec por diapositiva**; lo que el usuario controla es el escenario (§3). |
| D-2 | Los escenarios de presentación (objetivo, audiencia, orden…) son **distintos** de los E1/E2 financieros. | Evitar la confusión que ya advertía la especificación (§8.3). |
| D-3 | Lo que la documentación no define queda `null` («no definido»); no se inventa. Solo se completaron objetivo, audiencia, tipo de análisis e indicadores de AETOPS a partir de `docs/OBJETIVO_Y_NARRATIVA.md` §1 y §4. | Regla de integridad del prompt. |
| D-4 | El **orden narrativo** de cada escenario es el de la estructura real de la plantilla, no el orden de preguntas de `OBJETIVO_Y_NARRATIVA §1` (que pone «productos» después de «categorías»; las plantillas lo ponen antes). | Las plantillas reproducen los reportes originales; exigir otro orden marcaría como defectuosos los cuatro decks de referencia. |
| D-5 | Identificador de diapositiva `tipo:sldId` (el `sldId` de OOXML). | No depende de la posición ni del título (hay títulos repetidos: dos «Análisis de Productos», cinco «¿Quién busca GLP1?»). |
| D-6 | El diseño adaptativo corre **justo después de guardar el PPTX y antes del QA, el manifiesto y el historial** (que registran su hash). | Lo validado y lo registrado debe ser el archivo definitivo. |
| D-7 | Un reporte cuyo contenido cambió después de generarlo **no se puede descargar** y su vista previa no se entrega (vigencia por huella). | «Evitar que una validación antigua se considere válida». Es un cambio de comportamiento: antes, tras editar la narrativa, aún se podía descargar el PPTX anterior. Los reportes generados antes de este bloque no se bloquean (`vigente: null`). |

## 2. Arquitectura

```
escenario ─┐
           ▼                  build.build_*(plan=Plan)
libro ─▶ motor ─▶ constructores por plantilla ─▶ PPTX guardado
                                                    │ plan.ajustar      (gancho 1: diseño adaptativo, antes del QA)
                                                    ▼
                          QA anterior (estructural, cifras, visual con LibreOffice)
                                                    │ plan.revisar      (gancho 2: antes del manifiesto)
                                                    ▼
        SlideSpec ─▶ vista previa ─▶ QA integral ─▶ qa_report.json (bloquea la descarga si hay ERROR) ─▶ manifiesto / historial / procedencia
```

| Módulo (`backend/app/plan/`) | Responsabilidad |
|---|---|
| `escenario.py` | Modelo `EscenarioReporte`, catálogo (`config/escenarios_reporte.json`), escenarios propios (tabla `escenarios_reporte` en el historial SQLite), validación, ajustes por reporte y huella. |
| `slidespec.py` | `SlideSpec`/`SpecReporte`: se construyen desde el PPTX y los valores del motor; validación por diapositiva (antes de representarla) y del reporte. |
| `adaptativo.py` | Estimación de ocupación de texto y tablas; redistribuir, reducir letra proporcionalmente, ajustar tablas; avisos con propuesta. |
| `previsualizacion.py` | Modelo de vista previa extraído del mismo PPTX y `verificar_correspondencia` con un lector independiente (zip + XML). |
| `qa_integral.py` | Hallazgos de estructura, contenido, diseño y exportación; incorpora el QA anterior sin degradarlo; decide si es exportable. |
| `flujo.py` | `Plan` (los dos ganchos), escritura de los archivos del flujo y `vigente()`. |
| `reglas.py` | Constantes compartidas (letra mínima, umbrales, márgenes). |

Integración: la lógica del bloque que vive en la capa web se trasladó a **módulos nuevos** (no protegidos) para dejar en los archivos protegidos solo los puntos de conexión: `web/plan_service.py` (escenarios propios, plan, vista previa, vigencia, `preparar`/`estado_resultado`/`verificar_descarga`), `web/plan_routes.py` (rutas y despacho del puente del navegador) y `web/plan_api.py` (las mismas rutas como `APIRouter` de FastAPI). Los seis archivos protegidos conservan solo lo indicado en §14.2. **Sin `plan`, `build.py` se comporta exactamente como antes.**

## 3. Escenarios

Un escenario define: objetivo, audiencia, contexto de negocio, mensaje central, profundidad (`ejecutivo`/`intermedio`/`detallado`), tipo de análisis, orden narrativo, tipos de diapositiva obligatorios, indicadores relevantes y tipo de conclusión. Es **configurable** (ajustes por reporte, con las mismas validaciones) y **reutilizable** (se guarda como escenario propio). El catálogo trae los cuatro perfiles; GLP-1 deja sin definir objetivo, audiencia y tipo de análisis porque la documentación no los define.

Lo que controla de verdad: (a) el **contexto de negocio** llega a la hoja «Contexto aportado por el equipo» (texto del equipo, sin verificar); (b) todo lo demás son las **expectativas contra las que el QA integral valida** la estructura y el contenido (orden, obligatorias, profundidad, indicadores, conclusión, mensaje central). El resto de campos son descriptivos y quedan registrados en `plan_reporte.json`.

## 4. SlideSpec

Por diapositiva: `id` (`tipo:sldId`), `tipo`, `titulo`, `objetivo` (solo donde la documentación lo define), `mensaje` (primer párrafo sustantivo del cuerpo), `bloques` (texto, tabla, imagen, gráfica, con la forma a la que apuntan), `metricas`, `visualizaciones`, `fuentes`, `densidad`, `restricciones` (área segura, letra mínima), `notas`, `agregada`, `estado` y `avisos`.

* **Tipos:** `resumen_ejecutivo, panorama, canales, lineas, categorias, productos, negados, perfil_paciente, comportamiento_compra, engagement_digital, conclusiones, recomendaciones, descubrimiento, anexo_calidad, contenido` (no clasificada: se informa).
* **Título:** texto corto (≤ 120 caracteres, ≤ 2 párrafos) de mayor tamaño en el 30 % superior; un cuerpo largo nunca se toma por título.
* **Estado de cada métrica:** `real` (se traza a un valor del motor o a la narrativa verificada, con su fuente), `estimado` (escenario ilustrativo / supuesto), `no_disponible` («No verificable», «Información insuficiente»…) y `sin_respaldo` (cifra impresa sin valor del motor: se informa, no se oculta).
* **Densidades:** `pocos_elementos, multiples_kpis, tabla, grafico, narrativa_extensa, mixta`.
* **Validación previa a la representación:** id válido y único, tipo y densidad conocidos, título presente, contenido presente, estados válidos, sin bloques que apunten a la misma forma.

## 5. Diseño adaptativo

Para cada cuadro de texto y tabla se **estima** la ocupación (ancho medio de carácter × interlineado; 0,45 para fuentes estrechas como Aptos Narrow, 0,50 en otro caso) respetando `wrap="none"`, el autoajuste de la plantilla y la escala que ya aplicó. Los cuadros autoajustables se miden contra el espacio libre hasta la forma de abajo o el borde seguro. **Solo si la ocupación pasa de 108 %** interviene, en este orden:

1. ampliar el cuadro hacia abajo (si hay espacio libre sin pisar otra forma);
2. reducir la letra de forma **proporcional** (se conserva la jerarquía), nunca bajo 9 pt ni bajo el 80–85 % del tamaño **original** (el piso es acumulativo: varias pasadas no encadenan reducciones);
3. en tablas, reducir letra y ajustar la altura de las filas;
4. si aun así no cabe: **no se recorta nada**; aviso `DISENO_NO_CABE` con propuesta (abreviar, dividir la diapositiva).

Si todo cabe, **no cambia nada, ni el archivo**. Es idempotente. Cada acción y cada aviso queda en `plan_reporte.json` y como hallazgo `QA_DISENO_AJUSTE`.

**Calibración y límites (importante):** el estimador se calibró contra los cuatro decks de referencia que el render real da por correctos (el primer ajuste daba ocupaciones de 200 % por ignorar `spAutoFit`, el espacio posterior del último párrafo y la fuente estrecha). Por eso «no interviene en los decks de referencia» **no es evidencia por sí sola**; la evidencia de que interviene bien es la prueba con render real de LibreOffice sobre un deck de estrés: sin ajuste 57 palabras pasan de la nota de abajo (el texto llega a y = 267 pt); con ajuste queda 1 palabra (y = 215 pt) y el sistema **sigue avisando** (`DISENO_NO_CABE`, ocupación estimada 170 %). Es una estimación, no una medición: PowerPoint puede diferir.

## 6. QA integral

| Grupo | Hallazgos (`id`) | Severidad |
|---|---|---|
| Estructura | `QA_SPEC_ID_INVALIDO`, `QA_SPEC_ID_REPETIDO`, `QA_SPEC_TIPO_INVALIDO`, `QA_SPEC_VACIA`, `QA_FALTA_TIPO_OBLIGATORIO`, `QA_REFERENCIA_FORMA`, `QA_REFERENCIA_DIAPOSITIVA`, `QA_NUM_DIAPOSITIVAS` | ERROR |
| | `QA_ORDEN_NARRATIVO`, `QA_ANEXO_NO_ES_ULTIMA`, `QA_PROFUNDIDAD_EJECUTIVA`, `QA_SIN_CONCLUSION`, `QA_ESCENARIO_OTRO_PERFIL`, `QA_SPEC_DENSIDAD_INVALIDA`, `QA_SPEC_ESTADO_INVALIDO`, `QA_SPEC_FORMA_REPETIDA` | ADVERTENCIA |
| | `QA_TIPO_NO_CLASIFICADO` | INFORMACIÓN |
| Contenido | `QA_SIN_TITULO`, `QA_CONTENIDO_VACIO` | ERROR |
| | `QA_TABLA_SIN_DATOS`, `QA_SIN_FUENTE`, `QA_INDICADOR_NO_DISPONIBLE`, `QA_MENSAJE_SIN_EVIDENCIA`, `QA_INTERPRETACION_SIN_REGLA` | ADVERTENCIA |
| | `QA_DATO_NO_DISPONIBLE`, `QA_CONTIENE_ESTIMACIONES`, `QA_ESCENARIO_INCOMPLETO` | INFORMACIÓN |
| Diseño | `QA_DISENO_NO_CABE` con ocupación estimada > 125 %, `QA_CONTRASTE_ILEGIBLE` (< 1,5:1) | ERROR |
| | `QA_DISENO_NO_CABE` (≤ 125 %), `QA_DISENO_SOLAPE`, `QA_DISENO_FUERA_DE_AREA`, `QA_CONTRASTE_BAJO` (< 3:1), `QA_TITULOS_INCONSISTENTES` (> 6 pt de rango) | ADVERTENCIA |
| | `QA_DISENO_NO_ESTIMABLE`, `QA_DISENO_AJUSTE`, `QA_CONTRASTE_NO_DETERMINABLE` | INFORMACIÓN |
| Exportación | `QA_EXPORTACION_ZIP/ILEGIBLE/NUM/ORDEN/TITULO/TABLAS/TABLA_DIMENSION/IMAGEN/SIN_VISTA`, `QA_EXPORTACION_PREVIEW_*` (obsoleta, texto, tablas, imágenes, gráficas, orden, número) | ERROR |
| | `QA_IMAGEN_SIN_RECURSO` | INFORMACIÓN |
| QA anterior | todos los de `checks`, `pptx_export`, `cifras` y el visual | **su severidad original** (error → ERROR, warn → ADVERTENCIA, info → INFORMACIÓN); nunca se degradan |

Cada hallazgo trae diapositiva (id estable e índice), elemento, descripción, motivo y acción sugerida. El contraste estático solo se calcula con colores RGB explícitos; con colores del tema se informa «no determinable sin render».

## 7. Condiciones de exportación

* **Cualquier ERROR** (nuevo o del QA anterior) pone `qa_report.json.passed = false` → `downloadable = false`; el manifiesto y el historial ya reflejan ese estado (los hallazgos se agregan antes de escribirlos). La descarga devuelve 403 («el QA no aprobó el reporte»).
* **ADVERTENCIA** e **INFORMACIÓN** no bloquean y son visibles (panel de calidad agrupado por severidad y recuadros por diapositiva).
* **Resultados desactualizados:** si cambió el PPTX, el libro, las ediciones, el contexto, las metas, el descubrimiento, el escenario efectivo (o su borrado), las opciones o la plantilla, `vigente = false`: la descarga devuelve 403, la vista previa devuelve 409 y la interfaz lo declara y pide volver a generar. Volver al mismo contenido vuelve a ser vigente.
* El usuario ve el estado de calidad y de exportación antes de descargar (etapas del flujo y banner).

## 8. Vista previa

Se construye del **mismo PPTX** (no de un modelo paralelo) y se guarda en `previsualizacion.json`. `verificar_correspondencia` la compara con el archivo con un segundo lector independiente (huella, número y orden de diapositivas por `sldIdLst`, textos, tablas, imágenes y gráficas). Aplana los grupos con su transformación y muestra el contenido alternativo (`mc:AlternateContent`) como recuadro. **Límites declarados en la interfaz:** no es PowerPoint (tipografías del navegador), las gráficas avanzadas se muestran como recuadro, los colores del tema se dibujan con el color por defecto y el desborde visual real solo lo detecta el QA visual con LibreOffice (que no corre en el navegador).

## 9. API

`GET/PUT/DELETE /api/escenarios-reporte[/{id}]`, `GET/PUT /api/runs/{id}/plan`, `GET /api/runs/{id}/preview`, `POST /api/runs/{id}/generate` (ahora acepta `adaptativo`), `GET /api/runs/{id}/result` (agrega `vigente`, `motivos_obsoleto`, `qa_integral`) y descarga de `plan_reporte.json`, `slidespec.json`, `previsualizacion.json`, `qa_integral.json`. Todas las rutas existen en el puente del navegador (`plan_routes.py`) y en la API (`plan_api.py`, incluida desde `app.py`); `tests/unit/test_plan_api_fastapi.py` comprueba que ambas responden igual (§10).

## 10. Pruebas ejecutadas

**Suite completa local** (Pyodide obligatorio, navegador, LibreOffice) sobre el código final del bloque: **1698 aprobadas, 0 fallidas, 35 omitidas** en 35 min 5 s (con `REPORT_PYODIDE_REQUIRED=1`; tras la corrección del PR: 1669 + 29 pruebas nuevas). Las 35 omitidas son todas de `tests/golden` (8 `test_golden_deck`, 5 `test_golden_glp1`, 8 `test_golden_real_files`, 14 `test_golden_trimestral`; faltan la plantilla Q1 y el Excel Q3 reales): no se declaran aprobadas. Referencia previa: 1500 aprobadas (1698 − 1500 = 198 = 125 del bloque + 29 de la corrección del PR + 44 de la corrección de `release.yml`, ya integrada en `main`). `capture_baseline --check`: 8 de 8 idéntico. `archivos_protegidos --check`: sin cambios (tras registrar la reautorización de §2).

| Archivo (pruebas nuevas) | N.º | Qué demuestra | Dónde corre |
|---|---|---|---|
| `tests/unit/test_plan_escenario_slidespec.py` | 34 | catálogo válido; «no definido» sin inventar; 14 validaciones de escenario; escenarios propios (CRUD, no pisan el catálogo, registros dañados); ids estables e independientes de la posición y de títulos repetidos; estados de métrica (real/sin respaldo/estimado/no disponible); densidades; imagen decorativa; invariantes previas a la representación; un cuerpo largo no se toma por título | CI (PPTX sintéticos) |
| `tests/unit/test_plan_adaptativo_preview.py` | 24 | no-op si todo cabe (ni el archivo cambia); ampliar, reducir proporcional con piso de 9 pt y jerarquía; sin recortar nada y con aviso; tablas pequeñas y gigantes; piso acumulado e idempotencia; cuadros autoajustables y sin ajuste de línea; letra heredada no estimable; modelo de vista previa; correspondencia con el PPTX (archivo alterado, modelo adulterado, orden, número, ilegible); grupos y contenido alternativo; imagen grande | CI |
| `tests/unit/test_plan_qa_integral.py` | 33 | cada hallazgo con elemento, motivo y acción; estructura, contenido, diseño y exportación; severidades del QA anterior **sin degradar**; ERROR bloquea; correspondencia del archivo final con el SlideSpec; `Plan` y vigencia (PPTX cambiado, entradas cambiadas, archivos faltantes) | CI |
| `tests/unit/test_plan_adaptativo_render.py` | 2 | con **render real de LibreOffice**: sin ajuste 57 palabras pasan de la nota de abajo; con ajuste 1 (y el sistema sigue avisando) | local (se omite sin LibreOffice) |
| `tests/unit/test_flujo_integral_servicio.py` | 23 | por el puente, con motor, libros y plantillas reales: reporte válido; huella del PPTX = manifiesto = historial; **los 4 decks de referencia idénticos con y sin el plan**; 6 tipos de cambio invalidan resultados (descarga 403, vista previa 409) y regenerar los restablece; borrar el escenario invalida; reportes anteriores no se bloquean; el contexto del escenario llega al PPTX; escenario que exige una diapositiva ausente bloquea y se corrige; CRUD y errores claros; GLP-1 | local (se omite sin plantillas) |
| `tests/e2e/test_flujo_integral.py` (+ `flujo_integral.mjs`) | 9 | en **Chromium con Pyodide real**: escenario y etapas → generar → vista previa dibujada y navegable → cambio → «Resultados desactualizados» (descarga y vista previa fuera) → regenerar → caso bloqueante (QA rechazado, descarga bloqueada, vista previa disponible) → corrección y reejecución del QA → descarga de un PPTX válido; sin errores de consola | local |

**Pruebas añadidas en la corrección del PR (29 nuevas):**

| Archivo | N.º | Qué demuestra | Dónde corre |
|---|---|---|---|
| `tests/unit/test_plan_api_fastapi.py` | 19 | `app.py`: las 6 rutas nuevas están registradas (esquema OpenAPI) y las 17 anteriores siguen; sin rutas duplicadas; `generate` acepta `anexo` y `adaptativo` (valor no booleano → 422; sin libro, el mismo error 400 de siempre); catálogo de 4 perfiles; crear/listar/actualizar/borrar escenario propio; 8 entradas inválidas → 400 con mensaje y sin dejar nada guardado; cuerpo que no es objeto → 422; plan de corrida nueva por perfil, ajustes válidos/ inválidos conservando el plan anterior; corrida inexistente → 404; vista previa sin generar → 404; rutas anteriores sin cambios (la clave `plan` solo se suma); con plantilla real: generar por la API, archivos nuevos descargables, cambio posterior → descarga 403 y vista previa 409 | CI (la prueba con plantilla real se omite con motivo si falta) |
| `tests/unit/test_worker_persistencia.py` (+ `worker_persistencia.mjs`) | 2 | ejecuta el `worker.js` **real** en Node (`vm`) con IndexedDB, Pyodide y puente simulados: PUT persiste el historial; tras «recargar» se restaura; DELETE persiste; `generate` sigue persistiendo; GET y otras rutas no; un error del puente no persiste; un historial anterior al bloque se restaura intacto; `importHistory` igual que antes. La segunda prueba **quita la línea nueva** y verifica que la prueba falla | CI (se omite sin Node) |
| `tests/e2e/test_persistencia_escenarios.py` (+ `.mjs`) | 1 | con **Pyodide, SQLite e IndexedDB reales** en Chromium: PUT → recargar → el escenario sigue con su contenido; DELETE → recargar → no reaparece; sin errores de consola | local |
| `tests/regression/test_motivos_protegidos.py` | 7 | el motivo vigente de cada archivo protegido tocado conserva el rastro de las autorizaciones anteriores (§14.1) | CI |

El simulador del arnés de `worker.js` **no** demuestra el comportamiento de SQLite; eso lo cubre la prueba local con Pyodide real. Las pruebas que dependen de plantillas reales, LibreOffice, Pyodide o navegador **no corren en el CI actual** (`tests.yml` ejecuta `tests/unit`, `tests/regression` y `test_hash_pyodide`); el CI verde no prueba por sí solo que se ejecuten todas las de integración y e2e.

**Mutación** sobre el código del bloque: 13 de 13 defectos detectados (cuerpo largo tomado por título, ajuste que nunca interviene, sin piso de letra, piso no acumulado, ajuste que oculta el aviso, error anterior degradado a advertencia, obligatorias no exigidas, título ausente no es error, vigencia que ignora el PPTX o las entradas, vista previa que no compara textos o acepta cualquier huella, escenario que acepta campos desconocidos).

**Defectos propios hallados y corregidos al probar:** estimador de texto que daba 200 % por ignorar `spAutoFit`, `wrap="none"`, el espacio posterior y la fuente estrecha; comprobación de imágenes que marcaba como dañadas las imágenes de la plantilla sin recurso incrustado (35 falsos ERROR); vista previa que omitía las imágenes dentro de grupos y el contenido alternativo; comparación de formas con `is` (python-pptx crea un objeto por acceso); reducción de letra que se encadenaba en cada pasada; una diapositiva sin título que tomaba su cuerpo por título; observador de tamaño que disparaba tras invalidar la vista previa; hash del PPTX atribuido a la procedencia cuando lo registran el manifiesto y el historial.

## 11. Limitaciones conocidas

1. **No hay editor de SlideSpec por diapositiva** (D-1): el SlideSpec describe y valida; el usuario controla escenario, narrativa, contexto, metas y opciones.
2. La clasificación del tipo de diapositiva y de las métricas es **heurística** (título y texto): una diapositiva con un título nuevo queda «no clasificada» (INFORMACIÓN) y las métricas no disponibles/estimadas se detectan por palabras clave.
3. El diseño adaptativo es una **estimación**; en un reporte real puede no coincidir con PowerPoint. El render real solo existe localmente (LibreOffice); en el navegador no hay QA visual.
4. La vista previa no es un render de PowerPoint (§8).
5. Las plantillas reales no se versionan: las pruebas de integración con plantillas y de navegador corren solo localmente; en CI corren las sintéticas. **El CI actual no demuestra por sí solo que todas las pruebas de integración y e2e se ejecuten.** Las 35 pruebas `tests/golden` siguen omitidas por falta de archivos reales y **no cuentan como aprobadas**.
6. Con un escenario cuyo orden o tipos obligatorios no correspondan al perfil, el QA lo avisa pero no lo impide.
7. La verificación en navegadores distintos de Chromium (Firefox, Safari, móviles) y con datos de producción **no se hizo**.
8. El QA integral de contraste no evalúa colores heredados del tema.
9. **El diseño adaptativo no cubre completamente gráficas, imágenes ni composición por densidad**: solo avisa si salen del área segura; no recompone la lámina.
10. **El SlideSpec no permite control individual por diapositiva** (no se reordena, oculta ni edita).
11. La vista previa es **estructural**, no el render de PowerPoint; **la apertura en PowerPoint no se verificó**.

## 12. Pendientes históricos y dependencias (sin cambios)

* **AC-11 y AC-12 siguen NO CUMPLIDOS.** Análisis: este bloque añade infraestructura que una pantalla de reproducibilidad podría reutilizar (vigencia por huella, estado visible por reporte, etapas del flujo), pero **no muestra los estados `exacta`/`parcial`/`no_reproducible` ni el rótulo `legado`**. Faltaría la ruta del servicio y la pantalla del historial; por eso el criterio original no está satisfecho y no se cambia su estado.
* **A-3** (narrativa «Mounjaro (74 %, $9.20 M)» sin base declarada): sin cambios; el QA sigue informándola como `PPTX_SIN_DENOMINADOR`.
* Versionado de la release, primera publicación real con el `release.yml` corregido y verificación restante de AC-28 (consola de Chrome Android y pasos 3, 4 y 6): sin cambios. No se publicó ninguna release ni se tocó la etiqueta `app-v1.0.0`, `APP_VERSION`, Pages ni los workflows.

## 13. Criterios de aceptación y evidencia

| # | Criterio | Estado | Evidencia y alcance |
|---|---|---|---|
| 1 | Escenarios y SlideSpec implementados y probados | **CUMPLIDO** | §3–§4; 34 + 23 pruebas. Con la limitación D-1: el SlideSpec se deriva del PPTX y no hay editor por diapositiva |
| 2 | El diseño adaptativo funciona sobre distintos tipos y densidades | **PARCIALMENTE CUMPLIDO** | Probado en texto corto/extenso, tablas pequeñas/gigantes, cuadros autoajustables y con render real (57 → 1 palabra fuera de zona). **No** adapta gráficas ni imágenes (solo informa si se salen) y no resuelve todo desborde (avisa); estimador no verificado en PowerPoint |
| 3 | QA detecta y clasifica correctamente los problemas | **CUMPLIDO** | §6; 33 pruebas y 13 de 13 mutaciones. Alcance: «gráficos recortados» y «fuera de límites» los cubre el QA anterior; «distribuciones inconsistentes» solo en títulos; contraste solo con colores explícitos |
| 4 | La previsualización representa el resultado real esperado | **PARCIALMENTE CUMPLIDO** | Sale del mismo PPTX y se verifica con un lector independiente (4 decks reales sin discrepancias); pero no es un render de PowerPoint (tipografías, gráficas avanzadas como recuadro, colores del tema) |
| 5 | El flujo integral funciona sin inconsistencias | **CUMPLIDO** | 9 pruebas en Chromium con Pyodide real + 23 por el puente: válido, con advertencias, bloqueante, datos incompletos, modificación tras la vista previa, reejecución del QA. Solo Chromium |
| 6 | La exportación respeta los bloqueos de QA | **CUMPLIDO** | ERROR → `passed=false`, descarga 403, manifiesto e historial lo reflejan; resultados obsoletos → 403 |
| 7 | El PPTX generado es válido | **CUMPLIDO** | zip íntegro, python-pptx lo abre, número/orden/títulos/tablas/imágenes contra el SlideSpec, descarga real en Chromium. **No verificado en PowerPoint** |
| 8 | Las pruebas nuevas pasan | **CUMPLIDO** | 154 de 154 (125 del bloque + 29 de la corrección) en la suite completa local |
| 9 | Las pruebas de regresión pasan o se documentan sus limitaciones | **CUMPLIDO** | 1698 aprobadas, 0 fallidas, 35 omitidas (`tests/golden`, archivos reales ausentes; no cuentan como aprobadas) y línea base 8 de 8 idéntica |
| 10 | La documentación corresponde al código real | **CUMPLIDO** | Este documento se contrastó con el código y las pruebas; declara sus limitaciones (§11) |
| 11 | Los archivos protegidos permanecen intactos | **PARCIALMENTE CUMPLIDO** | Intactos: release, etiqueta `app-v1.0.0`, `app.zip`, `APP_VERSION`, Pages, workflows y `docs/fase5/*`. **Se modifican seis archivos protegidos** solo en los puntos de conexión de §14.2; el historial de motivos se recuperó (§14.1). `archivos_protegidos --check` verifica hashes y **no equivale a la autorización del propietario**: la modificación de los seis archivos sigue requiriendo su revisión y aprobación |
| 12 | CI pasa sobre el SHA exacto del PR | **NO VERIFICADO en este documento** | Un documento no puede citar el CI de su propio commit; el resultado va en el PR y en el informe final. El CI no ejecuta las pruebas con plantillas reales, navegador ni LibreOffice (§10) |
| 13 | Persistencia de escenarios propios y rutas de `app.py` cubiertas por pruebas automatizadas | **CUMPLIDO** | §10: 19 pruebas de `app.py`, 2 del `worker.js` real (con mutación) en CI y 1 con Pyodide/SQLite/IndexedDB reales (local). Alcance: el arnés de CI simula el motor |
| 14 | Historial de motivos de autorización íntegro | **CUMPLIDO** | §14.1; 7 pruebas de guarda. Recuperado de `main` sin inventar texto |

## 14. Integridad de los archivos protegidos

### 14.1 Incidente: motivos de autorización sobrescritos y su recuperación

Al registrar la reautorización del bloque se usó `tools/archivos_protegidos.py --write --autorizar ruta=motivo`. Ese comando **reemplaza** el motivo anterior del archivo (mezcla `{**previos, **nuevos}`): los motivos de las fases 3A, 4 y 5 y el del «cambio del usuario, commit 67fd179» de `worker.js` e `index.html` se perdieron en el commit `6d56357` del PR, sin que el PR lo señalara. Se detectó en la revisión complementaria.

**Recuperación (commit `cf24847`):** se compararon, archivo por archivo, el `protegidos.json` de `origin/main` y el del PR. Los 8 archivos autorizados que el bloque no toca eran idénticos. Los 6 afectados recuperaron su texto **verbatim desde `main`**, precedido por el motivo nuevo y separado con «Antes —»; las 13 piezas de historia se trazaron a commits reales (73fe7c4, a5ed0ee, 04ed905, 7f641e7, baeaba9). No se redactó ningún motivo nuevo para lo anterior. La recuperación se hizo editando el JSON directamente, **sin volver a ejecutar `--autorizar`**; los hashes no cambiaron. Después, las re-escrituras de hashes se hicieron con `--write` **sin** `--autorizar` (conserva los motivos; verificado: motivos idénticos antes y después). `tools/archivos_protegidos.py` **no se modificó**. Para que no vuelva a pasar sin tocar la herramienta: `tests/regression/test_motivos_protegidos.py` exige que cada motivo conserve su rastro anterior; y la norma operativa es no usar `--autorizar` sobre un archivo con motivos previos sin copiar antes el texto.

### 14.2 Qué permanece modificado en cada archivo protegido (frente a `main`)

| Archivo | Líneas (+/−) | Permanece | Extraído a módulos nuevos | Inevitable | Riesgo de regresión y pruebas que lo cubren |
|---|---|---|---|---|---|
| `build.py` | 10/2 | parámetro `plan=None` y 2 llamadas (`plan.ajustar` tras guardar el PPTX; `plan.revisar` antes del manifiesto) | toda la lógica está en `plan/flujo.py` | los ganchos deben ejecutarse **dentro** de la secuencia (antes del QA/manifiesto/historial) | sin plan es idéntico: línea base 8/8 y 4 decks con/sin plan (`test_flujo_integral_servicio`); `test_build_gate`, `test_procedencia_*` |
| `service.py` | 17/9 | `plan` en `public`; `generate(…, adaptativo)` que llama `P.preparar` y pasa `plan`/contexto a los constructores; `result_info` mezcla `P.estado_resultado`; lista blanca de archivos y `P.verificar_descarga` | escenarios, plan, vigencia, vista previa, huella de entradas (`plan_service.py`, 194 líneas; antes 191 líneas en `service.py`) | `generate` y `file_path` son los puntos por los que pasa el flujo y la descarga | `test_web`, `test_calidad`, `test_anexo_pptx`, `test_procedencia_servicio`, `test_flujo_integral_servicio`, `test_plan_api_fastapi` |
| `bridge.py` | 6/2 | importa `plan_routes`; `generate` pasa `adaptativo`; delega rutas no reconocidas a `plan_routes.despachar` antes del 404 | tabla de rutas y manejo de errores (`plan_routes.py`) | el despacho del puente es el único punto de entrada del navegador | `test_bridge`, `test_flujo_integral_servicio` (por el puente), e2e en Chromium |
| `app.py` | 4/3 | importa `plan_api`; `include_router`; `generate(…, adaptativo)` | las 6 rutas (`plan_api.py`) | el router debe incluirse en la app | `test_plan_api_fastapi` (19), `test_web` |
| `index.html` | 144/10 | paso «Generar»: escenario, etapas, calidad por severidad, vista previa navegable, aviso de desactualizado | — | la interfaz del flujo vive en este archivo único (sin módulos en el sitio publicado) | `tests/e2e/test_flujo_integral.py` (9), `test_escenarios_panel`, `test_descarga_*` (locales; Chromium) |
| `worker.js` | 1/1 | persistir el historial también tras PUT/DELETE de escenarios | — | sin esta línea los escenarios propios se pierden al recargar (verificado con Chromium real; la prueba de mutación lo reproduce) | `test_worker_persistencia` (CI) y `test_persistencia_escenarios` (local) |

Estas reducciones **no cambiaron el comportamiento** (se verificó con la regresión y la equivalencia con/sin plan). Frente a la versión anterior del PR, el diff de `service.py` bajó de 191 a 26 líneas, el de `bridge.py` de 33 a 8 y el de `app.py` de 34 a 7.
