# Bloque integral: escenarios y SlideSpec, diseño adaptativo, QA y previsualización

Documento técnico de lo que **quedó implementado** en la rama `claude/bloque-integral-slidespec-adaptativo-qa` (un único PR hacia `main`, sin fusionar). Describe el código real; no declara terminado nada que no tenga evidencia. No modifica los documentos de cierre de la Fase 5 ni su dictamen (`docs/fase5/*` no se tocó).

## 0. Estado del bloque y cambios de comportamiento (D-7)

**Dictamen honesto:** el flujo integral funciona de extremo a extremo para un reporte válido, un reporte con error bloqueante y un reporte desactualizado; sin embargo **seis de los doce criterios de aceptación están solo PARCIALMENTE cumplidos** (1, 2, 3, 4, 5 y 7; ver §13), el de archivos protegidos lo está con autorización limitada del propietario y el de documentación está en reevaluación. El PR está **abierto y sin fusionar**; la decisión de fusionarlo es exclusivamente del propietario.

### Cambios de comportamiento respecto a la versión publicada (D-7)

Estos cambios son intencionales, pero **alteran lo que el usuario experimentaba antes**:

1. **El flujo integral se ejecuta siempre para los reportes nuevos del flujo web.** `service.generate` construye un `Plan` en cada generación (escenario del perfil por omisión); no hay un modo web que lo desactive. (Llamar a `build.build_*` directamente sin `plan` sigue comportándose exactamente como antes.)
2. **El diseño adaptativo está activado por defecto** (casilla «Diseño adaptativo» marcada). Si todo cabe no cambia el PPTX (los 4 decks de referencia son idénticos con y sin plan); si el estimador detecta desborde, amplía el cuadro o reduce la letra (piso 9 pt) y lo registra en el informe.
3. **Un error del QA integral bloquea la descarga** del PPTX/PDF (403), igual que un error del QA anterior. Antes del bloque no existían esos controles, de modo que un reporte con, por ejemplo, una diapositiva obligatoria ausente según el escenario podía descargarse.
4. **Un resultado obsoleto bloquea la descarga.** Si después de generar cambia el libro, las ediciones de narrativa, el contexto, las metas, el descubrimiento, el escenario (o se borra), las opciones o la plantilla, el PPTX anterior ya no se puede descargar (403) y la vista previa no se entrega (409). Antes, un PPTX generado seguía descargable aunque se hubiera editado la narrativa.
5. **Qué debe hacer el usuario:** pulsar de nuevo **«Volver a generar»** (paso Generar). Eso recalcula el motor, rehace el PPTX, la vista previa y el QA y restablece la descarga. Si solo se quiere volver atrás, restaurar exactamente el estado anterior (mismos contenidos y opciones) también restablece la vigencia sin regenerar (la vigencia se calcula por huella).

### Compatibilidad con reportes generados antes del bloque

Un reporte generado antes del bloque **no tiene** `plan_reporte.json` ni los demás archivos del flujo. El sistema lo trata como «anterior al flujo integrado» (`vigente: null`):

* **Se puede consultar:** `GET /api/runs/{id}` y `/result` responden con todos los campos anteriores (`qa`, `qa_passed`, `pptx`, `trends`…); los campos nuevos valen `null` (`plan`, `qa_integral`) o `null`/`[]` (`vigente`, `motivos_obsoleto`). No se pierde información.
* **Se puede descargar sin regenerar:** el PPTX, el PDF y los JSON anteriores siguen descargables, **también si el contexto se edita después**: sin huellas guardadas no hay contra qué comparar, y bloquearlo no tendría una razón técnica real.
* **No queda inutilizable:** la vista previa responde 404 «genera el reporte»; el plan (`GET /plan`) devuelve el escenario del perfil con `generado: false`, de modo que el usuario puede elegir uno y regenerar **si quiere**, pero no está obligado.
* **Evidencia:** `tests/unit/test_flujo_integral_api_ci.py` (3 pruebas de compatibilidad, **corren en CI**) y `test_flujo_integral_servicio.py::test_un_reporte_generado_antes_del_flujo_integral_no_se_bloquea` (local, con plantillas). Límite: se simula el reporte anterior con un PPTX sintético y los archivos mínimos que genera el flujo anterior; **no se probó con reportes reales generados por la versión publicada 1.0.0**.

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

**Suite completa local** (Pyodide obligatorio, navegador, LibreOffice) sobre el código final del bloque: **1714 aprobadas, 0 fallidas, 35 omitidas** en 34 min 24 s (con `REPORT_PYODIDE_REQUIRED=1`). Evolución: 1669 (bloque original) → 1698 (+29, corrección controlada) → 1714 (+16: 11 del recorrido por la API en CI y 5 de revisión visual local). Las 35 omitidas son todas de `tests/golden` (8 `test_golden_deck`, 5 `test_golden_glp1`, 8 `test_golden_real_files`, 14 `test_golden_trimestral`; faltan la plantilla Q1 y el Excel Q3 reales): no se declaran aprobadas. Referencia previa: 1500 aprobadas (1714 − 1500 = 214 = 125 del bloque + 29 de la corrección + 16 del cierre condicionado + 44 de la corrección de `release.yml`, ya integrada en `main`). `capture_baseline --check`: 8 de 8 idéntico. `archivos_protegidos --check`: sin cambios (tras registrar la reautorización de §2).

| Archivo (pruebas nuevas) | N.º | Qué demuestra | Dónde corre |
|---|---|---|---|
| `tests/unit/test_plan_escenario_slidespec.py` | 34 | catálogo válido; «no definido» sin inventar; 14 validaciones de escenario; escenarios propios (CRUD, no pisan el catálogo, registros dañados); ids estables e independientes de la posición y de títulos repetidos; estados de métrica (real/sin respaldo/estimado/no disponible); densidades; imagen decorativa; invariantes previas a la representación; un cuerpo largo no se toma por título | CI (PPTX sintéticos) |
| `tests/unit/test_plan_adaptativo_preview.py` | 24 | no-op si todo cabe (ni el archivo cambia); ampliar, reducir proporcional con piso de 9 pt y jerarquía; sin recortar nada y con aviso; tablas pequeñas y gigantes; piso acumulado e idempotencia; cuadros autoajustables y sin ajuste de línea; letra heredada no estimable; modelo de vista previa; correspondencia con el PPTX (archivo alterado, modelo adulterado, orden, número, ilegible); grupos y contenido alternativo; imagen grande | CI |
| `tests/unit/test_plan_qa_integral.py` | 33 | cada hallazgo con elemento, motivo y acción; estructura, contenido, diseño y exportación; severidades del QA anterior **sin degradar**; ERROR bloquea; correspondencia del archivo final con el SlideSpec; `Plan` y vigencia (PPTX cambiado, entradas cambiadas, archivos faltantes) | CI |
| `tests/unit/test_plan_adaptativo_render.py` | 2 | con **render real de LibreOffice**: sin ajuste 57 palabras pasan de la nota de abajo; con ajuste 1 (y el sistema sigue avisando) | local (se omite sin LibreOffice) |
| `tests/unit/test_flujo_integral_servicio.py` | 23 | por el puente, con motor, libros y plantillas reales: reporte válido; huella del PPTX = manifiesto = historial; **los 4 decks de referencia idénticos con y sin el plan**; 6 tipos de cambio invalidan resultados (descarga 403, vista previa 409) y regenerar los restablece; borrar el escenario invalida; reportes anteriores no se bloquean; el contexto del escenario llega al PPTX; escenario que exige una diapositiva ausente bloquea y se corrige; CRUD y errores claros; GLP-1 | local (se omite sin plantillas) |
| `tests/e2e/test_flujo_integral.py` (+ `flujo_integral.mjs`) | 9 | en **Chromium con Pyodide real**: escenario y etapas → generar → vista previa dibujada y navegable → cambio → «Resultados desactualizados» (descarga y vista previa fuera) → regenerar → caso bloqueante (QA rechazado, descarga bloqueada, vista previa disponible) → corrección y reejecución del QA → descarga de un PPTX válido; sin errores de consola | local |

**Pruebas añadidas en el cierre condicionado (corren en CI, sin plantillas ni navegador):** `tests/unit/test_flujo_integral_api_ci.py` (11): recorrido por las rutas HTTP con la corrida sembrada con un PPTX sintético y los dos ganchos reales del flujo (`Plan.ajustar` y `Plan.revisar`): resultado válido y vigente con plan, vista previa, QA, descarga de un PPTX que se abre con python-pptx y archivos del flujo; error del QA integral (descarga 403, vista previa y hallazgos con motivo y acción disponibles); cinco tipos de cambio posterior (contexto, metas, adaptativo, ajuste del escenario, borrado del escenario) que dejan el resultado obsoleto (descarga 403, vista previa 409); los archivos de apoyo no se pierden; y tres de compatibilidad con reportes anteriores. Se comprobó por mutación que quitar el bloqueo por vigencia o el `downloadable` hace fallar 5 de ellas. **Alcance honesto:** no generan con una plantilla real; eso lo cubren solo en local `test_flujo_integral_servicio.py` y `tests/e2e/test_flujo_integral.py`.

**Revisión visual reproducible (solo local):** `tests/e2e/test_revision_visual.py` (+ `revision_visual.mjs`, 5 pruebas): Chromium con Pyodide real; mide en escritorio (1280 px) y en pantalla pequeña (390 px) que no hay desborde horizontal, que se ven las seis etapas, el escenario y el botón Generar, que aparecen vista previa, lista de diapositivas y estado de descarga, y que un cambio muestra «Resultados desactualizados» y quita la descarga; guarda 5 capturas. Mide, **no juzga** la estética: ver §15.

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
12. **La fidelidad de la vista previa no está certificada** en todos los motores ni plantillas: se verificó contra los 4 decks de referencia y con un lector independiente, pero no contra renders de otras plantillas.
13. El recorrido integral en **navegador** solo existe para AETOPS mensual con la plantilla real y solo en Chromium; GLP-1 se probó por el puente, no en navegador. **Ningún** recorrido en navegador corre en el CI actual (§16).
14. **Pantalla pequeña:** a 390 px la interfaz no desborda, pero la diapositiva de la vista previa queda muy pequeña (el texto de la diapositiva apenas se lee); se muestra tal cual.
15. **Observación de interfaz (no se modifica `index.html`):** con resultados desactualizados el recuadro de calidad sigue diciendo «QA aprobado» en verde junto a «descarga bloqueada»; el aviso «Resultados desactualizados» está justo encima y la etapa «Exportación» se muestra en rojo, pero el mensaje combinado puede confundir.

## 12. Pendientes históricos y dependencias (sin cambios)

* **AC-11 y AC-12 siguen NO CUMPLIDOS.** Análisis: este bloque añade infraestructura que una pantalla de reproducibilidad podría reutilizar (vigencia por huella, estado visible por reporte, etapas del flujo), pero **no muestra los estados `exacta`/`parcial`/`no_reproducible` ni el rótulo `legado`**. Faltaría la ruta del servicio y la pantalla del historial; por eso el criterio original no está satisfecho y no se cambia su estado.
* **A-3** (narrativa «Mounjaro (74 %, $9.20 M)» sin base declarada): sin cambios; el QA sigue informándola como `PPTX_SIN_DENOMINADOR`.
* Versionado de la release, primera publicación real con el `release.yml` corregido y verificación restante de AC-28 (consola de Chrome Android y pasos 3, 4 y 6): sin cambios. No se publicó ninguna release ni se tocó la etiqueta `app-v1.0.0`, `APP_VERSION`, Pages ni los workflows.

## 13. Criterios de aceptación y evidencia

Referencia: los 12 criterios de §12 del prompt maestro del bloque. Un criterio solo es CUMPLIDO si la capacidad completa está implementada **y** validada; tener pruebas unitarias no basta. «CI» = lo ejecuta el workflow `Pruebas`; «local» = solo en el equipo de desarrollo.

| # | Criterio | Estado | Justificación y evidencia | Limitación pendiente |
|---|---|---|---|---|
| 1 | Escenarios y SlideSpec implementados y probados | **PARCIALMENTE CUMPLIDO** | Existe un modelo estructurado de escenario y de SlideSpec (id estable `tipo:sldId`, tipo, título, mensaje, bloques, métricas con estado, densidad, restricciones), con validación; 34 + 19 pruebas (CI) y 23 (local, plantillas reales). El SlideSpec **se deriva del PPTX ya generado** y se usa para validar. | **No hay editor individual de SlideSpec** (ni edición, ocultación o reordenamiento por diapositiva). **La estructura narrativa no se controla desde el SlideSpec antes de la representación:** el orden narrativo, las obligatorias, la profundidad, los indicadores y la conclusión del escenario son solo expectativas del QA (`qa_integral.py`); lo único del escenario que cambia el PPTX es el contexto de negocio. |
| 2 | Diseño adaptativo sobre distintos tipos y densidades | **PARCIALMENTE CUMPLIDO** | Ajusta **texto** (cuadros autoajustables, ampliación del cuadro, reducción proporcional de letra con piso de 9 pt y 80–85 % del original acumulado) y **tablas**; no-op si todo cabe; avisa (`DISENO_NO_CABE`, `DISENO_SOLAPE`, `DISENO_FUERA_DE_AREA`) cuando no puede corregir. 24 pruebas (CI) + 2 con render real de LibreOffice (local: 57 → 1 palabra fuera de zona). | **No cubre completamente gráficas ni imágenes** (solo informa si se salen del área segura); **no resuelve todos los problemas de composición y densidad** (no recompone la lámina); en los 4 decks de referencia no interviene porque todo cabe; el estimador no está verificado en PowerPoint. |
| 3 | QA detecta y clasifica los problemas | **PARCIALMENTE CUMPLIDO** | Verificaciones implementadas: estructura (ids, orden, obligatorias, referencias), contenido (títulos, vacíos, métricas sin respaldo, cifras vs motor, conclusiones sin evidencia, indicadores), diseño (avisos del ajuste, contraste con colores explícitos), exportación (correspondencia con el PPTX, integridad, número y orden, recursos gráficos). Clasifica ERROR/ADVERTENCIA/INFORMACIÓN con diapositiva, elemento, descripción, motivo y acción; el QA anterior se incorpora sin degradar severidades. 33 pruebas (CI) y 13/13 mutaciones. | No se comprueban todas las inconsistencias visuales ni semánticas: «distribuciones inconsistentes» solo en títulos; «gráficos o tablas recortados» y «fuera de límites» los cubre el QA anterior; el contraste ignora colores heredados del tema; la clasificación del tipo de diapositiva y de métricas es heurística. |
| 4 | La previsualización representa el resultado esperado | **PARCIALMENTE CUMPLIDO** | Se construye del **mismo PPTX** y se verifica con un lector independiente (huella, número y orden de diapositivas, textos, tablas, imágenes y gráficas); se actualiza o invalida por huella. Comprueba estructura, contenido y elementos identificables. 24 pruebas (CI), 4 decks reales sin discrepancias (local), 9 e2e (local). | **No equivale a una representación visual idéntica a PowerPoint** (tipografías del navegador, gráficas avanzadas como recuadro, colores del tema por defecto). **No se certificó la fidelidad de renderizado en todos los motores y plantillas.** |
| 5 | El flujo integral funciona sin inconsistencias | **PARCIALMENTE CUMPLIDO** | Ver desglose abajo. Validado: reporte válido, error bloqueante, resultado obsoleto, regeneración y corrección con reejecución del QA. | Sin recorrido integral validado para **reporte con advertencias**, **datos incompletos** ni **contenido extenso** (solo pruebas unitarias o sintéticas); solo AETOPS mensual en navegador; solo Chromium. |
| 6 | La exportación respeta los bloqueos de QA | **CUMPLIDO** | ERROR → `passed=false`, descarga 403 en el servidor (no solo en la interfaz), manifiesto e historial lo reflejan; resultado obsoleto → 403. Probado en CI (`test_flujo_integral_api_ci.py`, mutación incluida), por el puente con plantillas reales (local) y en Chromium (local). | Ninguna relevante para el criterio. |
| 7 | El PPTX generado es válido | **PARCIALMENTE CUMPLIDO** | **Validación estructural:** zip íntegro, python-pptx lo abre, número, orden, títulos, tablas e imágenes contra el SlideSpec (CI con PPTX sintéticos; local con plantillas). **Apertura y descarga en Chromium:** el PPTX descargado se abre con python-pptx y coincide con lo previsualizado (local). | **La apertura real en Microsoft PowerPoint no se ha confirmado.** |
| 8 | Las pruebas nuevas pasan | **CUMPLIDO** | 170 nuevas (125 + 29 + 16) aprobadas en la suite completa local (1714 aprobadas, 0 fallidas); el CI ejecuta las que no requieren plantillas, navegador ni LibreOffice. | — |
| 9 | Las pruebas de regresión pasan o sus limitaciones están documentadas | **CUMPLIDO** | 1714 aprobadas, 0 fallidas, 35 omitidas; línea base 8 de 8 idéntica; 35 omitidas (`tests/golden`) documentadas y no contadas como aprobadas. | Las omitidas siguen sin ejecutarse. |
| 10 | La documentación corresponde al código real | **PARCIALMENTE CUMPLIDO (corregida; pendiente de nueva evaluación)** | Se corrigió la matriz (antes marcaba CUMPLIDO los criterios 1, 3, 5 y 7), se añadieron §0 (D-7 y compatibilidad), §15 y §16 y se actualizó la descripción del PR. | Debe reevaluarse por el propietario o en una revisión posterior; hasta entonces no se declara cumplido. |
| 11 | Los archivos protegidos permanecen intactos | **PARCIALMENTE CUMPLIDO, con autorización limitada del propietario** | Seis archivos protegidos tienen modificaciones (§14.2). El propietario autorizó conservar **exclusivamente** los diffs presentes en el commit `16a658a`; sin ampliarlos ni alterar sus motivos históricos. Intactos: release, etiqueta, `app.zip`, `APP_VERSION`, Pages, workflows y `docs/fase5/*`. | `archivos_protegidos --check` es una comprobación de **integridad (hashes)**, no una prueba de autorización ni de consentimiento. |
| 12 | CI pasa sobre el SHA exacto del PR | **CUMPLIDO, solo si se confirma en el SHA final** | Se confirma en el informe y en el PR contra el SHA definitivo; un documento no puede citar el CI de su propio commit. | El CI no ejecuta e2e, plantillas reales, LibreOffice ni golden (§16). |

### Desglose del criterio 5 (qué se probó y dónde)

| Caso | CI | Local (plantillas reales) | Navegador (Chromium + Pyodide) |
|---|---|---|---|
| Reporte válido (plan, vista previa, QA, descarga) | sí (API con PPTX sintético) | sí (23, por el puente) | sí (9) |
| Error bloqueante y corrección | sí (API, sintético) | sí | sí |
| Resultado obsoleto tras un cambio | sí (5 tipos de cambio) | sí (6 tipos) | sí |
| Reportes anteriores al bloque | sí (3 pruebas) | sí (1) | no |
| Reporte con advertencias | **no** (solo unidades del QA) | **no** | **no** |
| Datos incompletos | **no** | **no** | **no** |
| Contenido extenso | **no** (solo unidades del diseño) | **no** | **no** |
| GLP-1 | no | sí (por el puente) | **no** |

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

## 15. Revisión visual de la interfaz

**Evidencia reproducible** (local): `tests/e2e/test_revision_visual.py` (§10) recorre el flujo en Chromium con Pyodide real y mide, a 1280 px y a 390 px: sin desborde horizontal, seis etapas visibles, escenario y botón Generar visibles, vista previa y lista de diapositivas tras generar, estado de descarga y aviso de resultados desactualizados. En la ejecución de este cierre las 5 pruebas pasaron y se inspeccionaron las capturas de escritorio y de 390 px. **Eso no certifica el diseño visual:** lo medible por máquina no sustituye la valoración de una persona. No corre en CI.

**Checklist para el propietario** (verificación manual en el sitio, con un libro real):

1. Paso «Generar»: ¿se entiende en qué etapa se está? Las seis etapas (Escenario, Estructura, Diseño adaptativo, Calidad, Vista previa, Exportación) se ven y cambian de estado al generar.
2. Cambiar de escenario en el selector: el objetivo, el orden y las obligatorias cambian; «Ajustar este reporte» permite editar y «Aplicar ajustes» marca «Ajustado para este reporte».
3. Guardar como escenario propio, recargar la página, volver a elegirlo y borrarlo: debe persistir y desaparecer.
4. Generar: aparecen la calidad agrupada por severidad (error/advertencia/información, cada hallazgo con motivo y acción), la vista previa y el botón «Descargar PPTX».
5. Vista previa: botones ← →, flechas del teclado, lista lateral; los avisos por diapositiva; los botones «← Escenario», «← Metas y contexto», «← Narrativa».
6. Abrir el PPTX descargado en **PowerPoint** y compararlo con la vista previa (diapositiva por diapositiva): es la verificación que falta.
7. Cambiar el contexto después de generar: debe aparecer «Resultados desactualizados», la etapa «Exportación» en rojo, la descarga deshabilitada y la vista previa oculta; «Volver a generar» lo restablece.
8. Provocar un error (p. ej. un escenario propio que exija «conclusiones» en un reporte sin esa diapositiva): la descarga queda bloqueada, la vista previa sigue disponible y el hallazgo dice cómo corregir.
9. Pantalla pequeña (teléfono o ventana de 390 px): sin desplazamiento horizontal; evaluar si la vista previa es legible (se espera que el texto sea muy pequeño).
10. Flujo anterior: abrir un reporte generado antes del bloque (historial) y comprobar que se consulta y se descarga sin pedir regenerar.
11. Observación a decidir: con resultados desactualizados el recuadro dice «QA aprobado» en verde junto a «descarga bloqueada» (§11, punto 15).

## 16. Pruebas de extremo a extremo y CI: lo que falta

* **Qué corre en el CI actual:** `tests/unit`, `tests/regression` y la verificación del hash en Pyodide (`.github/workflows/tests.yml`). Incluye ahora el recorrido por la API con PPTX sintético (`test_flujo_integral_api_ci.py`), las pruebas de `app.py` y el arnés de `worker.js` en Node.
* **Qué no corre y por qué:**
  1. El recorrido en navegador (`tests/e2e/test_flujo_integral.py`, `test_persistencia_escenarios.py`, `test_revision_visual.py`) necesita Chromium con Playwright, Pyodide completo y, el primero, las plantillas reales (que **no se versionan**).
  2. Las pruebas con plantillas reales, con LibreOffice y las 35 `tests/golden` necesitan archivos que no están en el repositorio.
* **Qué haría falta, y requiere autorización del propietario:** ejecutar en CI el e2e de persistencia (no necesita plantillas) exigiría **modificar `.github/workflows/tests.yml`** (instalar Playwright y Chromium y definir `REPORT_PYODIDE_DIR`). Archivo protegido; **no se modificó ni se intentó autorizar**. Un e2e del flujo completo en CI además requeriría una plantilla de prueba versionada. Hasta entonces el CI verde **no demuestra** que esos recorridos pasen.
