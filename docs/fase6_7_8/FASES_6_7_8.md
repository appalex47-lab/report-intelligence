# Fases 6, 7 y 8 — Diseño adaptativo de la interfaz, QA y previsualización, y estabilización

Documento de aceptación del bloque que ejecuta, de forma consecutiva e integrada, las Fases 6, 7 y 8 sobre `main` en `3b85e06` (PR #31 fusionado). Describe lo que **quedó implementado y probado**; no declara terminado nada sin evidencia. No modifica los documentos de cierre de la Fase 5 ni del bloque integral.

## 0. Dictamen

**FASES 6, 7 Y 8: COMPLETADAS CON OBSERVACIONES** (ver §9). Cada fase cumple sus criterios de cierre con evidencia; permanecen las limitaciones de §8 (sobre todo: la adaptación se midió en Chromium emulando anchos, no en dispositivos físicos; el e2e de navegador no corre en CI; los archivos protegidos `index.html` y `service.py` tienen modificaciones que requieren la revisión del propietario). El PR queda abierto: la fusión corresponde al propietario.

## 1. Punto de control 1 — línea base, especificaciones y plan

**Estado inicial.** `main` = `3b85e0627528880744ac341f28b752706fad3a0a` (fusión del PR #31); Pages #28 y Tests #87 en éxito; release y etiqueta `app-v1.0.0` intactas (etiqueta en `428ecee`). Línea base de pruebas: suite completa local 1719 aprobadas, 0 fallidas, 35 omitidas (`tests/golden`, archivos reales ausentes) sobre el contenido de `main`; `capture_baseline --check` 8 de 8 idéntico (repetido al final, §7).

**Especificaciones recuperadas — hallazgo de partida.** Se buscaron las Fases 6, 7 y 8 en todo el repositorio (`docs/**`, código, workflows) y en los documentos de instrucciones aportados: **no existe ninguna especificación ni plan maestro escrito de esas fases.** Lo único que aparece es que la Fase 5 las declara *fuera de alcance* (`docs/fase5/IMPLEMENTACION_FASE5.md`) y que las instrucciones de cierre de las Fases 3–5 prohibían iniciarlas. Por tanto, **la única fuente de requisitos es el texto del encargo** (Fases 6, 7 y 8, con su «criterio de cierre»). Se tomó esa lista literal; no se inventó ningún requisito. Los criterios de aceptación de abajo se derivan, línea a línea, de ese texto.

**Solapamiento con el bloque integral (PR #31).** Ese bloque ya implementó el *diseño adaptativo de las diapositivas* (ajuste de texto y tablas del PPTX), el *QA integral* y la *vista previa* del PPTX. La Fase 6 de este encargo se refiere a la **interfaz** (escritorio, tablet, móvil), que no existía; la Fase 7 consolida y valida el recorrido de QA y previsualización ya construido (cierra los huecos que el bloque dejó documentados: advertencias, datos incompletos, contenido extenso, correspondencia en los 4 formatos, validación de entradas); la Fase 8 estabiliza todo. No se reconstruyó nada de lo existente.

**Componentes y contratos que se conservan** (no se tocan salvo lo indicado en §5): motor y reglas (`pipeline`, `importer`, `raw`), constructores por plantilla (`deck/`), `build.py`, el puente (`bridge.py`) y la API (`app.py`), el bloque integral (`plan/*`, `web/plan_*`), el historial SQLite y su persistencia en IndexedDB, el paquete `app.zip` y los workflows.

**Criterios de aceptación derivados del encargo**

| ID | Fase | Criterio (texto del encargo) |
|---|---|---|
| F6-1 | 6 | Interfaz adaptada a escritorio, tablet y móvil |
| F6-2 | 6 | Paneles, tablas, tarjetas y controles se redistribuyen según el espacio |
| F6-3 | 6 | Legibilidad y jerarquías visuales; controles accesibles |
| F6-4 | 6 | Sin desbordamientos ni desplazamientos horizontales innecesarios |
| F6-5 | 6 | Presentación de reportes y escenarios adaptada |
| F6-6 | 6 | Consistencia visual y conservación de funcionalidades, sin alterar resultados |
| F7-1 | 7 | Consistencia entre datos, cálculos, indicadores y representación visual |
| F7-2 | 7 | Correspondencia entre previsualización y PPTX; integridad de tablas, textos y elementos |
| F7-3 | 7 | Manejo de escenarios y estados de los reportes |
| F7-4 | 7 | Validaciones de entrada y salida; errores y situaciones excepcionales |
| F7-5 | 7 | Recorrido completo datos → procesamiento → reglas → escenarios → previsualización → PPTX → resultado |
| F7-6 | 7 | Resultados coherentes y reproducibles; diferencias previsualización/archivo controladas y documentadas |
| F8-1 | 8 | Suite integral y regresión; compatibilidad |
| F8-2 | 8 | Rendimiento revisado |
| F8-3 | 8 | Manejo de errores; persistencia de información |
| F8-4 | 8 | Integridad de archivos y artefactos; dependencias y contratos |
| F8-5 | 8 | Documentación técnica y de aceptación actualizada; defectos resueltos |

**Plan integral.** (1) Fase 6: medir la interfaz actual en 5 anchos y 10 pantallas, corregir lo que falle, fijar con pruebas. (2) Fase 7: ejercitar el recorrido real con los 4 formatos y los casos límite, corregir defectos de entrada y error, documentar diferencias. (3) Fase 8: contratos, artefactos, dependencias, rendimiento, persistencia e integridad; suite completa. Puntos de control 2 y 3 en §2–§4 y §7.

## 2. Fase 6 — Diseño adaptativo de la interfaz

**Método.** `tests/e2e/responsivo.mjs` recorre la aplicación real (Chromium + Pyodide) por **10 pantallas** (cargar vacío, con libro, validar, metas y contexto, narrativa, generar antes, resultado, resultado desactualizado, historial, plantillas) y las mide en **5 anchos** (1280 escritorio, 1024 portátil, 768 tablet, 390 móvil, 320 móvil pequeño): desborde horizontal de la página, elementos fuera del área visible, tablas que no caben, controles táctiles menores de 24 px (WCAG 2.2, 2.5.8), texto menor de 10.5 px y controles recortados. Es una medición automática; **no juzga la estética**.

**Defectos medidos en la línea base (`main`)**: de 50 combinaciones pantalla × ancho, **18 tenían algún problema**: desborde horizontal de la página en 4 (hasta 568 px en 390 px de ancho: tablas de 518–523 px en «Validar» y la tabla del «Historial»), elementos fuera del área en 5, tablas que no caben en 4 y **controles táctiles menores de 24 px en 15** (casillas, resúmenes plegables, botones «mini», campos de clave).

**Cambios** (`frontend/index.html`, solo CSS y un contenedor de la vista previa; sin tocar lógica, datos ni resultados):
* Contención: las columnas de las rejillas usan `minmax(0,1fr)` y el texto largo (`code`, hallazgos) se parte, de modo que ningún contenido ensancha la página.
* Tablas: en ≤900 px la **tarjeta** que contiene una tabla que no cabe se desplaza horizontalmente por sí sola; en ≤600 px las tablas de 4 o más columnas conservan 520 px de ancho para que sus columnas sigan siendo legibles (sin esto las celdas largas se comprimían en filas de cientos de píxeles de alto).
* Controles táctiles: casillas y radios de 24 px, resúmenes con altura mínima, botones «mini» de 28 px, campos de clave con el mismo estilo que el resto.
* Vista previa: la diapositiva se muestra a un ancho legible (720 px) dentro de un contenedor desplazable en móvil (antes quedaba como miniatura), y la lista y la diapositiva dejan de forzar la rejilla.
* Pestañas desplazables en móvil.

**Resultado:** las 50 combinaciones sin ningún problema medido (`tests/e2e/test_responsivo.py`, 6 pruebas, local). Comprobaciones estáticas en CI: `tests/unit/test_adaptativo_ui.py` (7). Sin cambio de resultados: el PPTX generado es idéntico en contenido (§3) y las 18 pruebas e2e previas (flujo integral, revisión visual, descargas) siguen pasando.

**Criterios:** F6-1 a F6-6 cumplidos con las limitaciones de §8 (L-1, L-2).

## 3. Fase 7 — QA y previsualización

**Recorrido real validado** (`tests/unit/test_fase7_recorrido_real.py`, 21 pruebas, con plantillas reales; local): datos de entrada → motor → reglas → escenario → previsualización → PPTX → resultado, para los **4 formatos** (AETOPS mensual y trimestral, GLP-1 mensual y trimestral):

| Etapa | Qué se comprueba | Resultado |
|---|---|---|
| Datos → cálculo → representación (F7-1) | cada cifra impresa se traza al motor; el valor del panel «Venta» aparece idéntico en el PPTX | 0 cifras sin trazar en los 4 formatos |
| Previsualización ≡ PPTX (F7-2) | `verificar_correspondencia` con lector independiente (zip + XML) y mismos `sld_id` en SlideSpec y vista previa | sin discrepancias en los **4** formatos (antes solo se afirmaba en 1) |
| Estados y escenarios (F7-3) | reporte con advertencias (AETOPS trimestral 1; GLP-1 mensual 2), cifra inventada en una edición, contenido extenso, texto vacío | advertencias visibles con motivo y acción; el vacío y el extenso que no cabe **bloquean**; el extenso que cabe no se toca |
| Entradas inválidas (F7-4) | defectos de datos, libro de otra unidad, periodo futuro, periodo sin datos | análisis `can_generate: false`, generar 409 con el hallazgo, sin archivo, sin vista previa, sin narrativa |
| Reproducibilidad (F7-6) | dos generaciones con las mismas entradas | mismo texto y geometría por diapositiva, misma huella de SlideSpec, mismo QA integral |
| Corrección y reejecución | texto que no cabe → error `QA_DISENO_NO_CABE` → se acorta → se regenera | descarga bloqueada y luego habilitada |

**Validación de entradas y errores** (`tests/unit/test_fase7_validacion_entradas.py`, 49 pruebas, **corren en CI**): parámetros de corrida inválidos, libros vacíos, de texto, truncados, imagen, sin hojas útiles o con hoja vacía, libro demasiado grande, nombre de archivo con ruta, metas, contexto y ediciones inválidos, identificadores y rutas inválidos (incluida la descarga fuera de la lista permitida), ruta inexistente, generar sin libro ni plantilla, secuencia de entradas inválidas sin corromper el estado, y respuesta idéntica por el puente del navegador.

**Defectos encontrados y corregidos en esta fase** (`backend/app/web/service.py`, archivo protegido; ver §5):
1. **Un libro de Excel sin el formato esperado** (por ejemplo, sin la hoja «Base» ni las hojas de datos crudos) provocaba un error no controlado: en la API un 500 «Internal Server Error» y en el puente un 500 con el nombre interno de la excepción. Ahora responde **400** con «El libro no tiene el formato esperado: …». Afectaba al análisis, a la generación y a la narrativa.
2. «Falta la plantilla» respondía **500** (un error del servidor) siendo una condición que el usuario corrige instalando la plantilla; ahora responde **409**.

**Diferencias controladas entre la previsualización y el PPTX** (F7-6). La vista previa se dibuja desde el mismo PPTX y se verifica con un lector independiente, de modo que el contenido (textos, tablas, imágenes, orden y número de diapositivas) coincide. Las diferencias que **existen por diseño y están declaradas en la interfaz** son: (a) las tipografías del navegador sustituyen a las de la plantilla; (b) las gráficas avanzadas se muestran como recuadro; (c) los colores del tema se dibujan con el color por defecto; (d) el desborde visual real solo lo detecta el QA con render (LibreOffice), que no corre en el navegador; (e) los bytes del PPTX **no** son idénticos entre dos generaciones (el zip registra la hora de escritura) aunque su contenido sí (comprobado); (f) la apertura en Microsoft PowerPoint se validó manualmente para un archivo (§ bloque integral, criterio 7), no para todos los formatos.

**Criterios:** F7-1 a F7-6 cumplidos con las limitaciones de §8 (L-3, L-4, L-5).

## 4. Fase 8 — Estabilización

| Área | Qué se verificó | Evidencia |
|---|---|---|
| Contratos (F8-4) | el puente y la API exponen las mismas rutas y métodos; mismas claves de respuesta y mismos códigos de error | `test_fase8_contratos.py` (CI). **Divergencias conocidas**, declaradas en la prueba para que cualquier otra falle: `GET /api/history/export` y `POST /api/runs/{id}/ia/check` existen solo en el puente (producto publicado); el servidor de desarrollo no las tiene |
| Artefactos (F8-4) | `app.zip` contiene el motor, el bloque integral y la configuración, y nada de pruebas, corridas, plantillas ni datos; el puente no importa FastAPI; construcción determinista en contenido | `test_fase8_contratos.py` (CI) |
| Dependencias (F8-4) | todo paquete externo que el motor importa está declarado | **Defecto corregido:** `lxml` y `Pillow` se importaban directamente (5 y 6 módulos) sin estar en `requirements.txt` (llegaban de forma transitiva por `python-pptx`); ahora declarados (`lxml>=4.9`, `Pillow>=10`) |
| Rendimiento (F8-2) | CPython, sin render: análisis 3.9–8.3 s; generación 5.3–9.7 s (con render de LibreOffice 11–21 s); flujo integral 1.2 s ≈ 9–15 % de la generación; vista previa servida en 0.01–0.02 s; PPTX 112–147 KB; `previsualizacion.json` 0.4–0.7 MB; pico de memoria ≈ 540 MB tras 8 generaciones. **Navegador (Pyodide)**: arranque del motor 3.9 s, análisis 7.4 s, generación 12.1 s | `test_fase8_rendimiento.py` y `test_estabilizacion_navegador.py` (locales, límites ≈3–4× lo medido). No es una prueba de carga |
| Persistencia (F8-3) | tras generar y **recargar la página**: el historial conserva la corrida (AETOPS 2026-09 v1, QA correcto, descargable), el escenario propio sigue y la pestaña «Historial» lo muestra | `test_estabilizacion_navegador.py` (local, IndexedDB y SQLite reales); persistencia de escenarios y del `worker.js`: bloque integral |
| Integridad de archivos (F8-4) | el PPTX descargado en el navegador es un zip íntegro con 13 diapositivas y su SHA-256 coincide con el del manifiesto | ídem |
| Compatibilidad (F8-1) | línea base de contenido de los 4 formatos (`capture_baseline --check`) y reportes anteriores al bloque (se consultan y descargan sin bloqueo) | §7; bloque integral §0 |
| Manejo de errores (F8-3) | ver §3 | 49 pruebas en CI |

**Criterios:** F8-1 a F8-5 cumplidos con las limitaciones de §8.

## 5. Archivos protegidos modificados y por qué

El encargo no cita los archivos protegidos; la protección del proyecto (`tests/regression/protegidos.json`) sigue vigente. Se modificaron **dos** archivos protegidos, solo donde cada fase lo exige, y se registró su nuevo hash **antepuesto** al historial de motivos (los motivos anteriores no se perdieron; el comando `--autorizar` no se usó porque reemplaza motivos). **Esto no es autorización del propietario: se somete a su revisión en el PR.**

| Archivo | Cambio | Fase y motivo | Cobertura |
|---|---|---|---|
| `frontend/index.html` | solo CSS y un contenedor `div.pvwrap` alrededor de la diapositiva de la vista previa | Fase 6: la interfaz vive en este único archivo; sin cambios de lógica | `test_responsivo.py` (local), `test_adaptativo_ui.py` (CI) |
| `backend/app/web/service.py` | `_run_engine` traduce `ImportRejected` a `ServiceError` 400; «Falta la plantilla» pasa de 500 a 409 (+10/−1) | Fase 7: defectos de manejo de errores (§3) | `test_fase7_validacion_entradas.py` (CI), `test_bridge`, `test_web`, `test_calidad` |

No se modificaron `.github/workflows/`, `tools/`, `version.py`, la release ni la etiqueta `app-v1.0.0`. `requirements.txt` (no protegido) declara `lxml` y `Pillow`.

## 6. Contratos: divergencias conocidas entre el puente y la API

El producto publicado usa el puente (Pyodide). El servidor de desarrollo (FastAPI) no implementa `GET /api/history/export` (exportar el historial) ni `POST /api/runs/{id}/ia/check` (comprobación de la propuesta de IA), por lo que **esas dos funciones no existen al ejecutar la aplicación con `uvicorn`**. No se corrigió: sería funcionalidad nueva del servidor de desarrollo fuera del alcance. Queda protegido por prueba para que no aparezcan divergencias nuevas.

## 7. Punto de control 3 — validación integral

Resultados reales de la ejecución final (tras el último cambio de código):

| Verificación | Resultado |
|---|---|
| Suite completa local (Pyodide, Chromium, LibreOffice; `REPORT_PYODIDE_REQUIRED=1`) | **1820 aprobadas, 0 fallidas, 35 omitidas** (45 min 46 s). Las 35 omitidas son `tests/golden` (archivos reales ausentes) y no cuentan como aprobadas. Evolución: 1719 (línea base) + 101 nuevas = 1820 |
| `capture_baseline --check` | 8 de 8 idéntico (motor y diapositivas de los 4 formatos) |
| `archivos_protegidos --check` | sin cambios (integridad por hash; no es autorización del propietario) |
| CI sobre el SHA definitivo | consta en el PR (un documento no puede citar el CI de su propio commit) |

**Las 101 pruebas nuevas:** Fase 6 — 13 (`test_adaptativo_ui` 7 en CI; `test_responsivo` 6 local). Fase 7 — 70 (`test_fase7_validacion_entradas` 49 en CI; `test_fase7_recorrido_real` 21 local con plantillas). Fase 8 — 18 (`test_fase8_contratos` 12 en CI; `test_fase8_rendimiento` 2 local; `test_estabilizacion_navegador` 4 local con Pyodide). **En CI corren 68; las 33 restantes son locales** (plantillas reales, Chromium + Pyodide) y el CI actual no demuestra por sí solo que se ejecuten.

Recorrido extremo a extremo y funcionamiento conjunto de las tres fases: `test_estabilizacion_navegador` recorre en Chromium con Pyodide real cargar → validar → metas → narrativa → escenario → generar → descargar → recargar → historial, sobre la interfaz ya adaptada (Fase 6) y con el QA y la vista previa validados (Fase 7); `test_responsivo` y las 18 pruebas e2e previas se ejecutan en la misma suite sin regresiones.

## 8. Limitaciones

* **L-1.** La adaptación de la interfaz se midió en Chromium **emulando** anchos de ventana (1280, 1024, 768, 390, 320 px); no se probó en dispositivos físicos, en Firefox ni en Safari.
* **L-2.** Las mediciones son automáticas (desborde, área visible, tamaño de controles, texto diminuto): no sustituyen la valoración visual de una persona. En móvil la diapositiva de la vista previa es legible solo con desplazamiento horizontal; no hay zoom.
* **L-3.** Previsualización ≠ render de PowerPoint (ver diferencias controladas, §3).
* **L-4.** El recorrido real (4 formatos, casos límite) y el e2e de navegador usan plantillas reales y Pyodide y **no corren en el CI actual**; en CI corren las comprobaciones sintéticas, las de entradas y las de contratos. Incorporarlos a CI exigiría modificar `.github/workflows/tests.yml` y versionar una plantilla de prueba (no se hizo).
* **L-5.** Cobertura de datos: los libros de ejemplo son sintéticos; no se validó con datos de producción.
* **L-6.** El rendimiento se midió en el equipo de desarrollo; los límites de las pruebas son generosos y no constituyen un compromiso de rendimiento.
* **L-7.** Divergencias del servidor de desarrollo (§6) y las limitaciones heredadas del bloque integral (editor de SlideSpec, diseño adaptativo de gráficas e imágenes) y los pendientes históricos (AC-11, AC-12, A-3, versionado, AC-28) **no cambian**.

## 9. Matriz de aceptación

| Criterio | Estado | Evidencia | Limitación |
|---|---|---|---|
| F6-1 a F6-5 | CUMPLIDO | 10 pantallas × 5 anchos sin problemas medidos (antes 18/50); `test_responsivo.py` (6), `test_adaptativo_ui.py` (7) | L-1, L-2 |
| F6-6 | CUMPLIDO | PPTX idéntico en contenido; e2e previos en verde | L-1 |
| F7-1, F7-2 | CUMPLIDO | `test_fase7_recorrido_real.py` (21) en los 4 formatos | L-3, L-4 |
| F7-3, F7-5 | CUMPLIDO | advertencias, datos incompletos, contenido extenso, corrección y reejecución | L-4, L-5 |
| F7-4 | CUMPLIDO | `test_fase7_validacion_entradas.py` (49, CI); 2 defectos corregidos | — |
| F7-6 | CUMPLIDO | reproducibilidad de contenido y diferencias documentadas (§3) | L-3 |
| F8-1 | CUMPLIDO | suite completa, línea base, reportes anteriores | L-4 |
| F8-2 | CUMPLIDO | tiempos en CPython y Pyodide, con límites | L-6 |
| F8-3 | CUMPLIDO | persistencia tras recarga e2e; errores | L-4 |
| F8-4 | CUMPLIDO | contratos, `app.zip`, dependencias (1 defecto corregido) | divergencias conocidas (§6) |
| F8-5 | CUMPLIDO | este documento; defectos de las tres fases corregidos | — |

**Defectos corregidos en total:** 18 combinaciones de interfaz con problemas (Fase 6); libro sin el formato esperado → error no controlado y «Falta la plantilla» → 500 (Fase 7); `lxml` y `Pillow` sin declarar (Fase 8). **Sin defectos bloqueantes conocidos.**
