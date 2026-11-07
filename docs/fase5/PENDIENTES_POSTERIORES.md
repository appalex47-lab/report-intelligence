# Pendientes que pasan a fases posteriores (registro formal)

Estado al 2026-11-07, tras el cierre formal de la Fase 5 (`CIERRE_FINAL_FASE5.md` §16.3 y §17). **Todo lo de este documento permanece ABIERTO y separado del trabajo necesario para terminar la Fase 5, que está concluido; ningún pendiente se marca como resuelto por ese cierre.** Este documento **no cierra ni cumple** ningún requisito: los formaliza para que no desaparezcan de la matriz de trazabilidad. Cada «propuesta» se deriva de textos ya aprobados (`ESPECIFICACION_FASE3A_PROCEDENCIA.md` §12.1, `ESPECIFICACION_FASE1…FINAL.md` §5.3) y se marca como tal; no es un requisito nuevo.

## 1. AC-11 · estados de reproducibilidad visibles en la interfaz — NO CUMPLIDO

| Campo | Contenido |
|---|---|
| Requisito aprobado | «Los tres estados de §3.2 se producen **y se muestran** correctamente; 0 regeneraciones silenciosas con versiones distintas; `exacta` solo tras una regeneración real con `hash_resultado` coincidente, sin afirmar igualdad binaria ni visual del PPTX» (3A §12.1) |
| Qué existe | La lógica de backend que **produce** los estados (`provenance_compare.py`, `provenance_verify.py`; ≈ 90 pruebas) |
| Qué falta | Que la interfaz **muestre** el estado. `frontend/index.html`, `worker.js`, `bridge.py`, `app.py` y `service.py` no tienen ruta, pantalla, botón ni texto de reproducibilidad |
| Dependencias técnicas conocidas | (a) una ruta del servicio y del puente que exponga la verificación/comparación de un reporte del historial; (b) un flujo para que la persona aporte los archivos fuente cuando haya que regenerar (la comparación solo regenera con fuentes de SHA verificado); (c) acceso al `procedencia.json` y a la tabla `procedencia` del historial; (d) que `service.py` siga sin importar `validator.*` ni `config.cargar` (prueba T-14); (e) los archivos protegidos `index.html`, `service.py`, `bridge.py`, `app.py` requerirán autorización explícita al tocarse |
| Comportamiento esperado (derivado de Fase 1 §5.3) | `exacta`: se declara reproducible, sin afirmar igualdad binaria del PPTX. `parcial`: **muestra qué componente difiere** y permite regenerar con versiones actuales. `no_reproducible`: lo declara y ofrece regenerar como reporte **nuevo**. Nunca regenerar en silencio con versiones distintas |
| Criterios de aceptación propuestos | 1) cada reporte del historial muestra su estado entre los tres valores; 2) `parcial` lista los componentes que difieren (versión del motor, plantilla, fuentes, reglas); 3) `exacta` solo aparece tras una regeneración real con `hash_resultado` coincidente; 4) regenerar con versiones distintas exige confirmación visible y produce un reporte nuevo; 5) el texto no afirma igualdad visual ni binaria |
| Pruebas necesarias | Navegador real (Playwright) con el motor Pyodide: un reporte `exacta`, uno `parcial` (plantilla distinta) y uno `no_reproducible`; prueba de que no hay regeneración silenciosa; prueba del texto (sin «idéntico»); regresión de protegidos y de la línea base |
| Propuesta de asignación | Una **fase de interfaz posterior a la 5** (la 3A la llamó «fase de interfaz posterior» sin numerarla). Requiere que el usuario la defina y numere; no se asigna aquí |

## 2. AC-12 · reportes previos como legado en la interfaz — NO CUMPLIDO

| Campo | Contenido |
|---|---|
| Requisito aprobado | «Los reportes previos a la 3A **se muestran** como `no_reproducible (legado)`» (3A §12.1) |
| Qué existe | Clasificación en backend: «sin procedencia (reporte anterior a la Fase 3A: legado)» (`provenance_verify.py`) |
| Qué falta | Que la pantalla del historial muestre esa clasificación |
| Dependencias técnicas conocidas | Las de AC-11 (ruta del servicio, historial); la lista de reportes del historial debe llevar el estado; compatibilidad con historiales anteriores a la 3A sin la tabla `procedencia` |
| Comportamiento esperado | Todo reporte sin manifiesto se rotula `no_reproducible (legado)` con una explicación breve; no se intenta regenerar como si tuviera procedencia |
| Criterios de aceptación propuestos | 1) un historial anterior a la 3A abre sin error; 2) sus reportes aparecen como `no_reproducible (legado)`; 3) los reportes con manifiesto no se rotulan como legado |
| Pruebas necesarias | Navegador real con un `historial.sqlite` sin tabla `procedencia` y otro mixto; texto exacto; ausencia de errores en consola |
| Propuesta de asignación | La misma fase de interfaz que AC-11 |

AC-11 y AC-12 **no se consideran cumplidos** por la existencia de la lógica de backend y siguen en la matriz de trazabilidad (`CIERRE_FINAL_FASE5.md` §4).

## 3. A-3 · narrativa protegida de GLP-1 — decisión pendiente

La narrativa «Mounjaro (74 %, $9.20 M)…» presenta un porcentaje **sin denominador explícito** (spec §3.2). El QA de la Fase 5 lo informa en cada deck GLP-1 como `PPTX_SIN_DENOMINADOR` (severidad `warn`, no bloquea). **No se modificó la narrativa, no se inventó una base de cálculo ni se alteró la cifra**: es un hallazgo real, no un falso positivo. Requiere una decisión narrativa A-3 posterior (qué base declarar) y autorización para tocar el archivo protegido. Hasta entonces el hallazgo permanece visible.

## 4. L-8 · resumen del anexo en el manifiesto — decisión tomada, definición pendiente

Decisión del usuario: **no** incorporar todavía el resumen del anexo de calidad al manifiesto de procedencia. El anexo (panel, `anexo_calidad.json`, diapositiva opt-in) y el manifiesto (contrato 3A congelado, `hash_resultado`) permanecen **separados** hasta que exista una definición funcional completa (qué campos, si entran o no al hash, y qué versión de contrato). Sin esa definición, RQ-19 queda **PARCIALMENTE CUMPLIDO**.

## 5. Otros pendientes

| Pendiente | Prioridad | Impacto | Causa | Fase | Acción | Evidencia necesaria |
|---|---|---|---|---|---|---|
| AC-28: consola del navegador y pasos no reportados de la verificación externa | media | la consola de Chrome Android está NO VERIFICADA y los pasos 3 (commit del `app.zip`), 4 (panel) y 6 (anexo) no constan; AC-28 sigue PARCIALMENTE CUMPLIDO | el usuario verificó desde Android (2026-11-06) y no dispone de una computadora para Chrome DevTools remoto | posterior (observación de verificación externa de la Fase 5) | inspeccionar la consola con DevTools remoto y reportar los pasos 3, 4 y 6; **o** dispensa expresa del usuario de la consola (desviación aceptada, a registrar) | consola sin errores bloqueantes, o decisión del usuario registrada (`PUBLICACION_AC28.md` §9) |
| Atascos de `deploy-pages` en `deployment_queued` | media | publicaciones que requieren reintento | lado de GitHub; la concurrencia no se demuestra causal | por definir | si se repite, valorar `cancel-in-progress: false` con nueva evidencia | logs de nuevos casos |
| Descarga `data.htm`: causa raíz y navegadores adicionales | baja | riesgo residual en Firefox, Safari y WebViews | no reproducida; el entorno solo trae Chromium | 5 / posterior | repetir `test_descarga_regresion.py` en Firefox/WebKit y probar a mano en un WebView | ejecución real por navegador |
| Plantillas de versiones anteriores | baja | compatibilidad NO VERIFICABLE | solo existe la versión 1 de la plantilla | posterior | probar cuando exista otra versión | plantilla real anterior |
| Pruebas golden (35 omitidas) | media | sin cobertura contra los archivos reales de referencia | faltan la plantilla Q1 y el Excel Q3 reales | por definir | aportar los archivos y ejecutar `tests/golden` | ejecución sin omisiones |
| Anexo en el PPTX por omisión | baja | decisión de producto | cambia la línea base de los decks | por definir | decidirlo con una nueva línea base | línea base regenerada |
| Release `app-v1.0.0` | — | **resuelto**: publicada el 2026-11-07 (etiqueta → `428ecee`), integridad verificada (`CIERRE_FINAL_FASE5.md` §13.3) | el borrador residual se eliminó fuera de esta sesión y el release salió del reintento del run #2 | 5 | ninguna sobre la release | — |
| La release fija `428ecee`, no el final de `main` | baja | los reportes generados con Pages hoy registran `f8c80c6` o posterior, sin etiqueta | Pages se redespliega con cada push; el release se fija a un commit | por definir | decidir el procedimiento de versionado (p. ej. fijar el commit desplegado, o publicar una nueva versión cuando cambie el paquete) | decisión del usuario |
| Rama de publicación corregida (PR #26) sin ejercitar en real | media | un comportamiento no previsto de GitHub podría requerir otro ajuste | la publicación v1.0.0 usó el `release.yml` anterior | 5 / próxima versión | observar la primera publicación real con el workflow corregido | run con `esperar-borrador` y `esperar-publicada` en success |
