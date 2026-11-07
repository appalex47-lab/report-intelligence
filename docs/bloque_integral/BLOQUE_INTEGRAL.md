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

Integración: `build.py` (parámetro opcional `plan` y dos ganchos), `web/service.py`, `web/bridge.py`, `web/app.py` (escenarios, plan, vista previa, vigencia), `frontend/index.html` (paso «Generar») y `frontend/worker.js` (persistir los escenarios propios). **Sin `plan`, `build.py` se comporta exactamente como antes.** Seis archivos protegidos se modificaron con reautorización documentada en `tests/regression/protegidos.json` (motivo por archivo).

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

`GET/PUT/DELETE /api/escenarios-reporte[/{id}]`, `GET/PUT /api/runs/{id}/plan`, `GET /api/runs/{id}/preview`, `POST /api/runs/{id}/generate` (ahora acepta `adaptativo`), `GET /api/runs/{id}/result` (agrega `vigente`, `motivos_obsoleto`, `qa_integral`) y descarga de `plan_reporte.json`, `slidespec.json`, `previsualizacion.json`, `qa_integral.json`. Todas las rutas existen en el puente del navegador y en la API.

## 10. Pruebas ejecutadas

{{PRUEBAS}}

## 11. Limitaciones conocidas

1. **No hay editor de SlideSpec por diapositiva** (D-1): el SlideSpec describe y valida; el usuario controla escenario, narrativa, contexto, metas y opciones.
2. La clasificación del tipo de diapositiva y de las métricas es **heurística** (título y texto): una diapositiva con un título nuevo queda «no clasificada» (INFORMACIÓN) y las métricas no disponibles/estimadas se detectan por palabras clave.
3. El diseño adaptativo es una **estimación**; en un reporte real puede no coincidir con PowerPoint. El render real solo existe localmente (LibreOffice); en el navegador no hay QA visual.
4. La vista previa no es un render de PowerPoint (§8).
5. Las plantillas reales no se versionan: las pruebas de integración con plantillas y de navegador corren solo localmente; en CI corren las sintéticas. Las 35 pruebas `tests/golden` siguen omitidas por falta de archivos reales.
6. Con un escenario cuyo orden o tipos obligatorios no correspondan al perfil, el QA lo avisa pero no lo impide.
7. La verificación en navegadores distintos de Chromium (Firefox, Safari, móviles) y con datos de producción **no se hizo**.
8. El QA integral de contraste no evalúa colores heredados del tema.

## 12. Pendientes históricos y dependencias (sin cambios)

* **AC-11 y AC-12 siguen NO CUMPLIDOS.** Análisis: este bloque añade infraestructura que una pantalla de reproducibilidad podría reutilizar (vigencia por huella, estado visible por reporte, etapas del flujo), pero **no muestra los estados `exacta`/`parcial`/`no_reproducible` ni el rótulo `legado`**. Faltaría la ruta del servicio y la pantalla del historial; por eso el criterio original no está satisfecho y no se cambia su estado.
* **A-3** (narrativa «Mounjaro (74 %, $9.20 M)» sin base declarada): sin cambios; el QA sigue informándola como `PPTX_SIN_DENOMINADOR`.
* Versionado de la release, primera publicación real con el `release.yml` corregido y verificación restante de AC-28 (consola de Chrome Android y pasos 3, 4 y 6): sin cambios. No se publicó ninguna release ni se tocó la etiqueta `app-v1.0.0`, `APP_VERSION`, Pages ni los workflows.

## 13. Criterios de aceptación y evidencia

{{MATRIZ}}
