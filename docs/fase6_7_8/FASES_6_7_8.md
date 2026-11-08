# Fases 6, 7 y 8 — Diseño adaptativo de la interfaz, QA y previsualización, y estabilización

Documento de aceptación de las Fases 6, 7 y 8 (PR #32, sobre `main` en `3b85e06`). Describe lo que **quedó implementado y probado**; no declara terminado nada sin evidencia. No modifica los documentos de cierre de la Fase 5 ni el texto del bloque integral (a este solo se le añade una nota de actualización al final de su §16).

## 0. Dictamen

**ACEPTACIÓN TÉCNICA AL 100 %** de los 17 criterios F6-1 a F8-5 (matriz de trazabilidad en §9), con las limitaciones reales de §8 (la principal: no se probó en dispositivos físicos). Las 33 pruebas que antes solo corrían en el equipo de desarrollo (y los e2e del bloque integral) se ejecutan ahora en CI; siguen omitidas, con motivo, las que por naturaleza exigen los archivos reales o LibreOffice (§4.2). Cifras y SHA finales: §7.

## 1. Punto de control 1 — línea base, especificaciones y plan

**Estado inicial.** `main` = `3b85e0627528880744ac341f28b752706fad3a0a` (fusión del PR #31); Pages #28 y Tests #87 en éxito; release y etiqueta `app-v1.0.0` intactas (etiqueta en `428ecee`). Línea base de pruebas: 1719 aprobadas, 0 fallidas, 35 omitidas (`tests/golden`, archivos reales ausentes); `capture_baseline --check` 8 de 8 idéntico.

**Especificaciones recuperadas.** No existe ninguna especificación ni plan maestro escrito de las Fases 6, 7 y 8 en el repositorio ni en los documentos de instrucciones (la Fase 5 solo las declara «fuera de alcance»). La única fuente de requisitos es el texto de los encargos; los criterios de abajo se derivan literalmente de él, sin inventar ninguno.

**Solapamiento con el bloque integral (PR #31).** Ese bloque ya implementó el diseño adaptativo de las *diapositivas*, el QA integral y la vista previa del PPTX. La Fase 6 de estos encargos se refiere a la **interfaz** (escritorio, tablet, móvil), que no existía; la Fase 7 consolida y valida el QA y la previsualización ya construidos; la Fase 8 estabiliza todo. No se reconstruyó nada de lo existente.

| ID | Fase | Criterio (texto del encargo) |
|---|---|---|
| F6-1 | 6 | Interfaz adaptada a escritorio, tablet y móvil |
| F6-2 | 6 | Paneles, tablas, tarjetas y controles se redistribuyen según el espacio |
| F6-3 | 6 | Legibilidad y jerarquías visuales; controles accesibles; interacción táctil |
| F6-4 | 6 | Sin desbordamientos ni desplazamientos horizontales innecesarios |
| F6-5 | 6 | Presentación de reportes y escenarios (vista previa incluida) adaptada |
| F6-6 | 6 | Consistencia visual y conservación de funcionalidades, sin alterar resultados |
| F7-1 | 7 | Consistencia entre datos, cálculos, indicadores y representación visual |
| F7-2 | 7 | Correspondencia entre previsualización y PPTX; integridad de tablas, cifras, textos y gráficos |
| F7-3 | 7 | Manejo de escenarios y estados de los reportes |
| F7-4 | 7 | Validaciones de entrada y salida; errores y situaciones excepcionales |
| F7-5 | 7 | Recorrido completo datos → procesamiento → reglas → escenarios → previsualización → PPTX → resultado |
| F7-6 | 7 | Resultados coherentes y reproducibles; diferencias previsualización/archivo controladas y documentadas |
| F8-1 | 8 | Suite integral y regresión; compatibilidad |
| F8-2 | 8 | Rendimiento revisado |
| F8-3 | 8 | Manejo de errores; persistencia de información |
| F8-4 | 8 | Integridad de archivos y artefactos; dependencias y contratos (sin divergencias evitables) |
| F8-5 | 8 | Documentación técnica y de aceptación actualizada; defectos resueltos; todo ejecutado de forma automatizada y reproducible |

## 2. Fase 6 — Diseño adaptativo de la interfaz

**Método.** `tests/e2e/responsivo.mjs` recorre la aplicación real (navegador + Pyodide) por **10 pantallas** (cargar vacío, con libro, validar, metas y contexto, narrativa, generar antes, resultado, resultado desactualizado, historial, plantillas) en **5 anchos** (1280 escritorio, 1024 portátil, 768 tablet, 390 móvil, 320 móvil pequeño) y mide: desborde horizontal de la página, elementos fuera del área visible, tablas que no caben, controles táctiles menores de 24 px (WCAG 2.2, 2.5.8), texto menor de 10.5 px y controles recortados. `tests/e2e/tactil.mjs` repite el flujo completo **solo con toques** en un contexto táctil de 390 × 844. Todo se ejecuta en **Chromium, Firefox y WebKit** (CI, §4). Es medición automática: **no juzga la estética**.

**Defectos medidos en la línea base (`main`)**: de 50 combinaciones pantalla × ancho, **18 tenían algún problema**: desborde horizontal de la página en 4 (hasta 568 px a 390 px de ancho), elementos fuera del área en 5, tablas que no caben en 4 y **controles táctiles menores de 24 px en 15** (casillas, resúmenes plegables, botones «mini», campos de clave).

**Cambios** (`frontend/index.html`, solo CSS y un contenedor de la vista previa; sin tocar lógica, datos ni resultados): contención del contenido (`minmax(0,1fr)`, texto largo que se parte); en ≤900 px la tarjeta que contiene una tabla que no cabe se desplaza por sí sola, y en ≤600 px las tablas de 4+ columnas conservan 520 px para que sus columnas sigan siendo legibles; casillas y radios de 24 px, resúmenes y botones «mini» con altura mínima; vista previa a un ancho legible (720 px) dentro de un contenedor desplazable en móvil; pestañas desplazables.

**Resultado.** 50 de 50 combinaciones sin problemas medidos, en los tres motores (`test_responsivo.py`, 6 pruebas × 3 motores). Interacción táctil (`test_tactil.py`, 5 × 3): los toques avanzan el flujo hasta generar, la casilla de diseño adaptativo cambia, la vista previa navega (siguiente, anterior y lista), el plegable se abre, las pestañas cambian, cada objetivo táctil es visible y de ≥ 24 px y la vista previa se desplaza en lugar de desbordar la página. Comprobaciones estáticas de las reglas CSS en CI: `test_adaptativo_ui.py` (7). El PPTX generado y las 18 pruebas e2e previas siguen sin cambios (sin alterar resultados).

**Hallazgos por motor durante la integración** (corregidos en las pruebas, no en la interfaz): Firefox da caja a lo que hay dentro de un `<details>` cerrado (la medición ahora lo ignora); WebKit y Firefox en Linux informan `maxTouchPoints = 0` aunque haya toques (la prueba comprueba que los toques `tap` ocurrieron y surtieron efecto); WebKit registra como error de consola el 404 de una plantilla ausente (el sitio de prueba incluye las plantillas).

## 3. Fase 7 — QA y previsualización

**Recorrido real validado** (`tests/unit/test_fase7_recorrido_real.py`, 25 pruebas, motor + libros de ejemplo + plantillas, por el puente): datos de entrada → motor → reglas → escenario → previsualización → PPTX → resultado, para los **4 formatos** (AETOPS mensual y trimestral, GLP-1 mensual y trimestral):

| Etapa | Qué se comprueba | Resultado |
|---|---|---|
| Datos → cálculo → representación (F7-1) | cada cifra impresa se traza al motor; el valor del panel «Venta» aparece idéntico en el PPTX | 0 cifras sin trazar en los 4 formatos |
| Previsualización ≡ PPTX (F7-2) | `verificar_correspondencia` con lector independiente (zip + XML), mismos `sld_id` en SlideSpec y vista previa | sin discrepancias en los **4** formatos |
| Tablas y gráficos (F7-2) | mismo número de tablas, mismas filas y columnas y **mismo texto de cada celda** (leído con python-pptx, independiente del modelo); la gráfica avanzada de GLP-1 está representada exactamente en la diapositiva donde el PPTX la tiene | idénticos en los 4 formatos |
| Estados y escenarios (F7-3) | reporte con advertencias (AETOPS trimestral, GLP-1 mensual), cifra inventada en una edición, contenido extenso, texto vacío | advertencias visibles con motivo y acción; el vacío y el extenso que no cabe **bloquean**; el extenso que cabe no se toca |
| Entradas inválidas (F7-4) | defectos de datos, libro de otra unidad, periodo futuro, periodo sin datos | análisis `can_generate: false`, generar 409 con el hallazgo, sin archivo, sin vista previa, sin narrativa |
| Reproducibilidad (F7-6) | dos generaciones con las mismas entradas | mismo texto y geometría por diapositiva, misma huella de SlideSpec, mismo QA integral |
| Corrección y reejecución | texto que no cabe → error `QA_DISENO_NO_CABE` → se acorta → se regenera | descarga bloqueada y luego habilitada |
| Descarga y apertura (F7-5) | el PPTX descargado en el navegador es un zip íntegro con 13 diapositivas y su SHA-256 coincide con el manifiesto; se abre con python-pptx | en los 3 motores |

**Validación de entradas y errores** (`test_fase7_validacion_entradas.py`, 49 pruebas): parámetros de corrida inválidos, libros vacíos, de texto, truncados, imagen, sin hojas útiles o con hoja vacía, libro demasiado grande, nombre de archivo con ruta, metas, contexto y ediciones inválidos, identificadores y rutas inválidos (incluida la descarga fuera de la lista permitida), ruta inexistente, generar sin libro ni plantilla, secuencia de entradas inválidas sin corromper el estado, y respuesta idéntica por el puente.

**Defectos encontrados y corregidos** (`backend/app/web/service.py`, ver §5): (1) un libro de Excel sin el formato esperado provocaba un error no controlado (500 en la API; 500 con el nombre interno de la excepción en el puente): ahora responde **400** con «El libro no tiene el formato esperado: …»; (2) «Falta la plantilla» respondía **500** y ahora **409**.

**Diferencias controladas entre la previsualización y el PPTX** (F7-6). El contenido (textos, tablas, imágenes, orden y número de diapositivas) coincide, verificado. Las diferencias que existen por diseño y están declaradas en la interfaz: (a) las tipografías del navegador sustituyen a las de la plantilla; (b) las gráficas avanzadas se muestran como recuadro que marca su lugar; (c) los colores del tema se dibujan con el color por defecto; (d) el desborde visual real solo lo detecta el QA con render (LibreOffice), que no corre en el navegador; (e) los **bytes** del PPTX no son idénticos entre dos generaciones (el zip registra la hora de escritura) aunque su contenido sí (comprobado); (f) la apertura en Microsoft PowerPoint se validó manualmente para un archivo real (bloque integral, criterio 7), no para todos los formatos.

## 4. Fase 8 — Estabilización y ejecución automatizada

### 4.1 Por qué las 33 pruebas no corrían en CI, y cómo se resolvió

Las pruebas añadidas en la primera entrega que solo corrían en el equipo de desarrollo eran 33 (`test_responsivo` 6, `test_fase7_recorrido_real` 21, `test_fase8_rendimiento` 2, `test_estabilizacion_navegador` 4), más los e2e del bloque integral. Había **tres causas**:

1. **Plantillas.** Las plantillas PPTX reales no se versionan (marca y datos comerciales, `templates/README.md`) y los rellenos exigen su estructura exacta. **Solución:** `tools/make_plantillas_sinteticas.py` genera, a partir de las reales, **plantillas sintéticas** versionadas en `tests/fixtures/plantillas_sinteticas/` (4 archivos de 66–94 KB). Conservan lo que el relleno y el QA necesitan (nombres, tipos, geometría y orden de los shapes; tamaños de tabla; formatos; colores —el relleno de GLP-1 lee el rojo de la plantilla—; rótulos estructurales; longitud y reparto de palabras de cada texto narrativo, porque el relleno calcula la capacidad de cada cuadro con él) y eliminan lo sensible: logotipos e imágenes (sustituidos por imágenes neutras del mismo tamaño), miniatura, autor y metadatos, todas las cifras y la narrativa original (sustituida, letra por letra, por texto de relleno de la misma longitud). `tests/unit/test_plantillas_sinteticas.py` (21 pruebas, CI) garantiza que lo versionado no contiene nada de lo eliminado —**comprobado que esas pruebas rechazan las 4 plantillas reales**— y que la estructura es idéntica a la de las reales donde estas existen (verificado: 4 de 4). `tests/plantillas.py` elige las reales si están en `templates/` y las sintéticas si no, sin mezclarlas.
2. **Navegador y Pyodide.** Faltaba en CI un navegador de Playwright y un Pyodide completo. **Solución:** nuevo trabajo `navegador` en `.github/workflows/tests.yml` con matriz **chromium / firefox / webkit** (un trabajo por motor, `fail-fast: false`): instala `playwright@1.63.0` y el motor, y usa Pyodide 0.27.7 desde la **CDN fijada por el propio worker** (no hay que descargar 400 MB; es la misma CDN que usa la aplicación publicada). `tests/e2e/_sitio.py` unifica la infraestructura (motor elegido por `REPORT_BROWSER`, Pyodide en disco o CDN, plantillas, sitio construido con `build_site`); con `REPORT_PYODIDE_REQUIRED=1` la falta de un requisito es un **fallo**, no una omisión.
3. **Archivos personales.** Ninguna prueba depende de archivos personales: los libros son los sintéticos de `data/ejemplos/` (versionados) y las plantillas, las sintéticas.

### 4.2 Qué ejecuta ahora el CI

| Trabajo | Qué ejecuta |
|---|---|
| `unit` | `tests/unit` (incluye el recorrido real de los 4 formatos, el flujo integral por el puente, rendimiento y contratos, con plantillas sintéticas), `tests/regression` y el hash canónico en Pyodide |
| `navegador (chromium)`, `(firefox)`, `(webkit)` | `tests/e2e` completo (59 pruebas por motor): flujo integral, vista previa, persistencia, descarga, panel de escenarios, responsivo en 5 anchos, táctil, revisión visual y estabilización |

**Omitidas en CI, con motivo (no se presentan como aprobadas).** Las pruebas heredadas que antes se omitían por falta de plantilla (`test_plan_api_fastapi`, `test_tabla_compacta`, `test_anexo_pptx`, `test_qa_cifras`, `test_qa_pptx_export`, `test_compatibilidad`, `test_discovery`, `test_bridge`: 31 pruebas) usan ahora el selector de plantillas y **corren** en CI. Siguen omitiéndose, porque su naturaleza lo exige: (a) las **golden** (35, `tests/golden`) y las de regresión que comparan contra la plantilla o el resultado **real** registrado (`test_linea_base`, `test_hash_resultado`, `test_procedencia_build`, `test_procedencia_regeneracion`, `capture_baseline`: 23); (b) las que necesitan **LibreOffice** (render real: `test_plan_adaptativo_render`, `test_glp1_deck`, `test_qa_visual`, partes de `test_web` y `test_procedencia_servicio`); (c) la comparación de la plantilla sintética con la real (4), que necesita la real. El equipo de desarrollo las ejecuta con las plantillas reales y LibreOffice (suite local, `capture_baseline --check` 8 de 8 idéntico).

### 4.3 Contratos, artefactos, dependencias, rendimiento, persistencia

| Área | Qué se verificó | Evidencia |
|---|---|---|
| Contratos (F8-4) | el puente del navegador y la API exponen **exactamente las mismas rutas y métodos, sin excepciones**; mismas claves de respuesta y mismos códigos de error | `test_fase8_contratos.py` (14, CI). **Divergencias eliminadas:** `GET /api/history/export` y `POST /api/runs/{id}/ia/check` solo existían en el puente; ahora también en la API (`plan_api.py`, módulo nuevo; `app.py` no cambió) y se prueba que responden igual |
| Artefactos (F8-4) | `app.zip` contiene el motor, el bloque integral y la configuración, y nada de pruebas, corridas, plantillas ni datos; el puente no importa FastAPI; construcción determinista en contenido | `test_fase8_contratos.py` (CI) |
| Dependencias (F8-4) | todo paquete externo que el motor importa está declarado | **Defecto corregido:** `lxml` y `Pillow` se importaban directamente sin estar en `requirements.txt` (llegaban transitivamente por `python-pptx`); ahora declarados |
| Rendimiento (F8-2) | CPython, sin render: análisis 3.9–8.3 s; generación 5.3–9.7 s (con LibreOffice 11–21 s); flujo integral ≈ 9–15 % de la generación; vista previa servida en 0.01–0.02 s; PPTX 112–147 KB; `previsualizacion.json` 0.4–0.7 MB; pico ≈ 540 MB tras 8 generaciones. Navegador (Pyodide, local): arranque 3.9 s, análisis 7.4 s, generación 12.1 s | `test_fase8_rendimiento.py` (CI, plantillas sintéticas; límites ≈ 4× lo medido) y `test_estabilizacion_navegador.py` (3 motores). No es una prueba de carga |
| Persistencia (F8-3) | tras generar y **recargar la página**: el historial conserva la corrida (AETOPS 2026-09 v1, QA correcto, descargable), el escenario propio sigue y la pestaña «Historial» lo muestra | `test_estabilizacion_navegador.py`, `test_persistencia_escenarios.py` (3 motores, IndexedDB y SQLite reales); `test_worker_persistencia.py` |
| Integridad de archivos (F8-4) | el PPTX descargado en el navegador es un zip íntegro con 13 diapositivas y su SHA-256 coincide con el manifiesto | ídem |
| Compatibilidad (F8-1) | línea base de contenido de los 4 formatos (equipo de desarrollo, plantillas reales) y reportes anteriores al bloque (se consultan y descargan sin bloqueo) | §7; bloque integral §0 |
| Manejo de errores (F8-3) | ver §3 | 49 pruebas en CI |

## 5. Archivos protegidos modificados y por qué

La protección del proyecto (`tests/regression/protegidos.json`) sigue vigente. Se modificaron **tres** archivos protegidos, solo donde cada fase lo exige, con el motivo nuevo **antepuesto** al historial (los motivos anteriores están íntegros; no se usó `--autorizar`, que los reemplaza). Los dos primeros ya constaban en el PR; el tercero (workflow de pruebas) lo autoriza expresamente la orden de aceptación «exclusivamente para habilitar estas validaciones».

| Archivo | Cambio | Fase y motivo | Cobertura |
|---|---|---|---|
| `frontend/index.html` | solo CSS y un `div.pvwrap` alrededor de la diapositiva de la vista previa | Fase 6; sin cambios de lógica | `test_responsivo` y `test_tactil` (3 motores), `test_adaptativo_ui` |
| `backend/app/web/service.py` | `_run_engine` traduce `ImportRejected` a `ServiceError` 400; «Falta la plantilla» de 500 a 409 (+10/−1) | Fase 7; defectos de manejo de errores | `test_fase7_validacion_entradas`, `test_bridge`, `test_web`, `test_calidad` |
| `.github/workflows/tests.yml` | `unit` con tiempo límite y plantillas sintéticas; nuevo trabajo `navegador` (matriz de 3 motores) | Fase 8; ejecutar en CI lo que solo corría en local | su propia ejecución en el PR |

No se modificaron `pages.yml`, `release.yml`, `tools/` existentes, `version.py`, la release ni la etiqueta `app-v1.0.0`. Archivos nuevos no protegidos: `tools/make_plantillas_sinteticas.py`, `tests/fixtures/plantillas_sinteticas/*`, `tests/plantillas.py`, `tests/e2e/_sitio.py`, `backend/app/web/plan_api.py` (ampliado). `requirements.txt` declara `lxml` y `Pillow`. `archivos_protegidos --check` es una comprobación de integridad por hash; **no** equivale a la autorización del propietario.

## 6. Contratos

Sin divergencias entre el puente y la API (§4.3). La prueba ya no admite excepciones: cualquier ruta nueva en un solo camino la hace fallar.

## 7. Resultados finales

| Verificación | Resultado |
|---|---|
| Suite completa local, modo desarrollo (plantillas reales; Pyodide, Chromium y LibreOffice; `REPORT_PYODIDE_REQUIRED=1`) | **1852 aprobadas, 0 fallidas, 35 omitidas** (56 min 50 s). Las 35 omitidas son `tests/golden` (archivos reales ausentes) y no cuentan como aprobadas. Colección total: 1887 pruebas (1855 de la línea base + 32 nuevas de la aceptación). Tras esa ejecución, 8 archivos de prueba pasaron a usar el selector de plantillas; se volvieron a ejecutar en modo desarrollo (**206 aprobadas, 0 omitidas**) y con plantillas sintéticas (**185 aprobadas, 0 omitidas** en los 6 archivos que antes se omitían en CI) |
| Simulación de CI en un clon limpio (sin plantillas reales) de `tests/unit` y `tests/regression` | 1717 aprobadas y 75 omitidas antes de la última conversión; las omitidas se explican en §4.2 |
| `capture_baseline --check` (plantillas reales) | 8 de 8 idéntico (motor y diapositivas de los 4 formatos) |
| `archivos_protegidos --check` | sin cambios (integridad por hash; no es autorización del propietario) |
| CI sobre el SHA definitivo | consta en el PR (un documento no puede citar el CI de su propio commit): trabajos `unit`, `navegador (chromium)`, `navegador (firefox)` y `navegador (webkit)` |
| CI en iteraciones previas del PR | 4 de 4 trabajos en verde en la ejecución 91 (`unit`: 1621 aprobadas y 74 omitidas en `tests/unit`, 74 aprobadas y 23 omitidas en `tests/regression`, hash en Pyodide aprobado; cada navegador: 59 aprobadas, 0 omitidas) |

## 8. Limitaciones reales

* **L-1.** La adaptación de la interfaz y la interacción táctil se midieron en Chromium, Firefox y WebKit de Playwright **emulando** anchos y toques; **no se probó en dispositivos físicos** (teléfonos, tabletas) ni en versiones de navegador distintas de las de Playwright 1.63.0.
* **L-2.** Las mediciones son automáticas (desborde, área visible, tamaño de controles, texto diminuto): no sustituyen la valoración visual de una persona. En móvil la diapositiva de la vista previa se lee con desplazamiento horizontal; no hay zoom.
* **L-3.** Previsualización ≠ render de PowerPoint (diferencias controladas, §3). La apertura en Microsoft PowerPoint se validó manualmente para un archivo real, no para todos los formatos.
* **L-4.** En CI las pruebas usan plantillas **sintéticas** (misma estructura, sin marca ni datos): demuestran el comportamiento del código, pero no sustituyen a las reales. Con las reales corren, solo en el equipo de desarrollo, la línea base de contenido (`capture_baseline`) y la equivalencia de los 4 decks de referencia con y sin plan. Las 35 pruebas golden siguen omitidas por falta de archivos reales y las 2 con render de LibreOffice se omiten sin LibreOffice; ninguna se presenta como aprobada.
* **L-5.** Los libros de ejemplo son sintéticos; no se validó con datos de producción.
* **L-6.** El rendimiento se midió en el equipo de desarrollo y los límites de las pruebas son generosos; no constituyen un compromiso. Las pruebas de navegador dependen de la CDN de Pyodide (versión fijada) y de PyPI (versiones fijadas) durante la ejecución en CI.
* **L-7.** Una ejecución de CI (la 94, sobre `8ea3e7b`) falló **de forma intermitente** en 4 de las 5 pruebas táctiles de Chromium (el recorrido se detuvo tras el paso «Validar»); las mismas pruebas pasaron en las ejecuciones 89–93 de Firefox y WebKit y en 6 ejecuciones locales consecutivas, y en Chromium en CI en las ejecuciones 89 y 91. El mensaje de error no quedó registrado, por lo que **la causa no está confirmada**; la hipótesis más probable es un toque recibido mientras la capa de carga de la aplicación cubría el control en un ejecutor lento. Se endureció la prueba (espera a que termine la capa de carga antes de cada toque, tiempos de espera de 60 s y registro del último toque y del error en el resultado) y se vuelve a ejecutar en el CI del SHA definitivo; si reaparece, el registro dirá en qué toque.
* **L-8.** Pendientes históricos (AC-11, AC-12, A-3, versionado, AC-28) y limitaciones del bloque integral (editor de SlideSpec, diseño adaptativo de gráficas e imágenes) **no cambian**.

## 9. Matriz de trazabilidad de los 17 criterios

Todas las pruebas de la columna «Dónde corre en CI» se ejecutan en el PR; «×3» = en Chromium, Firefox y WebKit.

| Criterio | Implementación | Prueba | Dónde corre en CI | Estado |
|---|---|---|---|---|
| F6-1 | `index.html` (CSS adaptativo) | `test_responsivo` (50 combinaciones) | `navegador` ×3 | CUMPLIDO |
| F6-2 | tarjetas desplazables, rejillas `minmax(0,1fr)`, tablas anchas | `test_responsivo`, `test_adaptativo_ui` | `navegador` ×3, `unit` | CUMPLIDO |
| F6-3 | controles ≥ 24 px, resúmenes y «mini» | `test_responsivo`, `test_tactil` | `navegador` ×3 | CUMPLIDO |
| F6-4 | contención del contenido | `test_responsivo` (desborde, fuera de área, tablas) | `navegador` ×3 | CUMPLIDO |
| F6-5 | `div.pvwrap`, vista previa a 720 px desplazable | `test_tactil`, `test_revision_visual` | `navegador` ×3 | CUMPLIDO |
| F6-6 | sin cambios de lógica ni de resultados | 59 e2e por motor, `test_flujo_integral_servicio` | `navegador` ×3, `unit` | CUMPLIDO |
| F7-1 | motor + `plan/qa_integral.py` | `test_fase7_recorrido_real` (cifras trazadas, indicadores = PPTX) | `unit` | CUMPLIDO |
| F7-2 | `plan/previsualizacion.py` | `test_fase7_recorrido_real` (correspondencia, tablas, gráficos) en 4 formatos | `unit` | CUMPLIDO |
| F7-3 | escenarios, vigencia, QA | `test_fase7_recorrido_real`, `test_flujo_integral_api_ci` | `unit` | CUMPLIDO |
| F7-4 | `service.py` (400/409) | `test_fase7_validacion_entradas` (49) | `unit` | CUMPLIDO |
| F7-5 | flujo completo | `test_flujo_integral`, `test_estabilizacion_navegador`, recorrido real | `navegador` ×3, `unit` | CUMPLIDO |
| F7-6 | contenido reproducible; diferencias documentadas (§3) | `test_regenerar_con_las_mismas_entradas_da_el_mismo_contenido` | `unit` | CUMPLIDO |
| F8-1 | suite integral; regresión | `unit`, `regression`, `navegador` ×3; `capture_baseline` (desarrollo) | CI + desarrollo | CUMPLIDO |
| F8-2 | medición de rendimiento | `test_fase8_rendimiento`, `test_estabilizacion_navegador` | `unit`, `navegador` ×3 | CUMPLIDO |
| F8-3 | persistencia, errores | `test_estabilizacion_navegador`, `test_persistencia_escenarios`, validación de entradas | `navegador` ×3, `unit` | CUMPLIDO |
| F8-4 | contratos sin divergencias, `app.zip`, dependencias | `test_fase8_contratos` (14), `test_plantillas_sinteticas` (21) | `unit` | CUMPLIDO |
| F8-5 | este documento; CI con navegadores y plantillas sintéticas | el propio CI del PR | `unit` + `navegador` ×3 | CUMPLIDO |

**Defectos corregidos en total:** 18 combinaciones de interfaz con problemas (Fase 6); libro sin el formato esperado → error no controlado, y «Falta la plantilla» → 500 (Fase 7); `lxml` y `Pillow` sin declarar y dos rutas de la API ausentes respecto del puente (Fase 8); 33 pruebas que no corrían en CI (causas y solución en §4.1). **Sin defectos bloqueantes conocidos.**
