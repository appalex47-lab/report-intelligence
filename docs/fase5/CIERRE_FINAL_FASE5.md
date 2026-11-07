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
| AC-28 publicación real | PARCIALMENTE CUMPLIDO | sitio publicado verificado desde el entorno (commit, recursos, recorrido funcional); falta navegador externo y release publicado (§12–13) |
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

## 9. Fusión
PR #24 fusionado el 2026-11-06 a las 22:38:10 UTC (16:38:10 −06:00) con merge commit. Condiciones comprobadas antes de fusionar: CI `Pruebas` #66 en success sobre el HEAD exacto `2db6adf2a555c909bcf1f8f2655bb3529e0951f0`; `mergeable_state: clean`; `main` sin cambios (`47dc3af`) y rama al día; `archivos_protegidos --check` sin cambios; suite completa 1500/0/35; decisiones del apartado 2 aplicadas; diff solo con archivos de la Fase 5 (36: 25 nuevos, 11 modificados, 0 eliminados).

## 10. SHA fusionado
`428eceeef3e776286e1ec8053ef3cffc0bd9caa9` (contiene el HEAD `2db6adf`). CI posterior en `main`: `Pruebas` #67 en success.

## 11. Publicación
`Publicar en GitHub Pages` #21 en success **al primer intento** (build 22:38:16–22:38:23, deploy 22:38:27–22:38:41 UTC). La API de despliegues registra el despliegue 7612453960 para `428ecee` con estado `success` y `environment_url` `https://appalex47-lab.github.io/report-intelligence/`.

## 12. AC-28 · PARCIALMENTE CUMPLIDO
Para poder comprobarlo se permitió el host `appalex47-lab.github.io` en la red del entorno (con aprobación del usuario). Evidencia real:
* `GET /` → 200 (83 686 B, título «Report Intelligence»); `worker.js` y `app.zip` → 200.
* `app.zip` publicado: zip íntegro, 83 entradas, `_build_info.json` = `{"esquema": "build_info/1", "commit": "428eceeef3e776286e1ec8053ef3cffc0bd9caa9"}` (SHA fusionado, sin `+dirty`).
* Recorrido funcional con Chromium (Playwright) **contra el sitio publicado real**: el motor arranca, se carga el libro de ejemplo AETOPS, se valida, se generan metas y narrativa y se descarga el PPTX; banner «QA aprobado · descarga habilitada … Revisión estructural. La revisión visual requiere render»; `Resultados_AETOP_Septiembre_2026.pptx`, 142 580 B, firma `504b0304`, 13 diapositivas; consola sin errores.
* **Limitaciones, sin ocultarlas:** (1) el tiempo de ejecución de Pyodide (el sitio lo pide a un CDN no permitido aquí) y la plantilla de AETOPS mensual (no se publica: lleva marca comercial) se sirvieron desde archivos locales interceptando esas peticiones; (2) las otras tres plantillas dan 404, como se espera; (3) fue Chromium sin interfaz desde este entorno, **no** un navegador externo de una persona usuaria; no se probó Firefox, Safari ni móvil.
**Qué falta para CUMPLIDO:** la verificación del §4 de `PUBLICACION_AC28.md` desde un navegador externo (con Pyodide desde el CDN real) y el release publicado.

## 13. Release
* Ensayo (`publicar=false`), run 42308725556: **success** (paquete válido, CI del commit exacto, etiqueta libre; `publicar` omitido; no creó nada).
* Publicación (`publicar=true`), run 42308811022: **failure** en «Verificar el borrador»: `ERROR: debe haber exactamente una release para la etiqueta y hay 0`. La verificación consultó el listado de releases ≈1 s después de crear el borrador (creado 23:00:35, consulta 23:00:36) y no lo vio todavía; poco después el borrador sí aparece con `tag_name: app-v1.0.0`. Es consistente con **consistencia eventual de GitHub** (el workflow asumía lectura inmediata; era su primera ejecución real, V-02 de la 3A-5): es una inferencia a partir de esos tiempos, no una causa observada directamente. El paquete no presentó ningún defecto.
* Estado resultante, fallido de forma segura: borrador `app-v1.0.0` (id 437146660, no publicado), `target_commitish` = `428ecee`, assets `app.zip` (264 195 B) y `app.zip.sha256`; el SHA-256 del `app.zip` del borrador (`671a02b92ffde5a9bf4e3c56e0f9a19b491ddf68799092b9a0236119abdbc9c1`) coincide con su `.sha256`; su contenido es idéntico al `app.zip` publicado en el sitio (83 entradas, 0 diferencias). **No existe etiqueta git ni release publicada.**
* No se forzó ni se publicó por otra vía. El borrador bloquea un nuevo intento (`etiqueta-libre` incluye borradores); el borrado fue denegado primero por el clasificador de permisos y, tras la autorización expresa del usuario, por la propia API (`HTTP 403: Creating, editing, or deleting releases is not permitted for this session type`). No se eludió. Queda pendiente de eliminarse desde fuera de esta sesión (interfaz de GitHub).
* **Qué falta:** (a) eliminar el borrador 437146660; (b) corregir `release.yml` con una espera/reintento tras crear el borrador (PR propio, ver el PR de corrección de `release.yml`); (c) volver a ejecutar `publicar=true`. Mientras tanto el release **no está publicado**.

### 13.1 Corrección de `release.yml` y estado posterior (2026-11-06/07)
Se conserva lo anterior como evidencia histórica. Después:
* **PR de corrección [#26](https://github.com/appalex47-lab/report-intelligence/pull/26)** (`release.yml` + `tools/release_app.py` + pruebas): el borrador se identifica por la URL que imprimió `gh release create`, se lee por su identificador y se reintenta con espera progresiva (2, 4, 8, 16 s…; máximo 90 s) solo ante retraso de propagación; un defecto real (duplicados, otra release, assets inesperados, estado erróneo) falla de inmediato. Lo mismo para la release publicada y su etiqueta. Se conservan todos los controles (ensayo, CI del SHA exacto, etiqueta libre, SHA-256, tamaños, zip, permisos). Pruebas: 44 nuevas (41 + 3 mutaciones del workflow), mutación de la herramienta 7 de 7 detectadas, unit 1426 y regresión 90 aprobadas. CI `Pruebas` #69 en success sobre `187e59b4b26cd9e5ebc37d0643dc0357e778e933`. **Fusionado** como `a5402838324af7dbdde86bc04fb108062ed4d5b2`.
* **PR documental [#25](https://github.com/appalex47-lab/report-intelligence/pull/25)**: revisado (se corrigieron tres afirmaciones: la causa del fallo pasó de «condición de carrera» a «consistente con consistencia eventual», el alcance de la verificación del sitio y la causa del bloqueo del borrado); CI `Pruebas` #70 en success sobre `0da6c935854f3d636f5877e5de8f6b87e5096c46`. **Fusionado** como `86bc9cc2a4d3355b6ef0fff435c001fc0c166d36`.
* **`main` = `86bc9cc`**: `Pruebas` #72 en success y `Publicar en GitHub Pages` #23 en success.
* **Ensayo tras la corrección** (`publicar=false`, [run 42319718449](https://github.com/appalex47-lab/report-intelligence/actions/runs/42319718449)): **success**; no creó etiquetas, borradores ni releases (sigue habiendo una sola release, el borrador 437146660, y 0 etiquetas).
* **Borrador residual 437146660: NO eliminado.** La API respondió `HTTP 403: Creating, editing, or deleting releases is not permitted for this session type` incluso con la autorización expresa del usuario; no se eludió (ni vía otro workflow). Que el ensayo pasara con el borrador presente es coherente con que el job `construir` usa un token `contents: read` y GitHub no lista borradores con él (**inferencia, no verificada**); el job `publicar` (escritura) repite la comprobación de etiqueta libre y debería rechazarlo.
* **`publicar=true` NO se ejecutó**: la precondición «no queda un borrador residual» no se cumple. **El release `app-v1.0.0` no está publicado**, no existe la etiqueta y no hay artefactos publicados que verificar. La verificación de integridad hecha es sobre el **borrador** (SHA-256 `671a02b92ffde5a9bf4e3c56e0f9a19b491ddf68799092b9a0236119abdbc9c1` coincide con su `.sha256`; contenido idéntico al `app.zip` de Pages: 83 entradas, 0 diferencias).
* **Para terminar el release (acciones fuera de esta sesión):** (1) eliminar el borrador en GitHub (Releases → Drafts → «Aplicación 1.0.0» → Delete); (2) ejecutar *Release de la aplicación* con `publicar` desmarcado y, si termina en success, marcado; (3) comprobar etiqueta, release no borrador, `app.zip` y `.sha256` descargados (`sha256sum -c app.zip.sha256`) y que `_build_info.json` cite el commit etiquetado. La rama de publicación corregida **aún no se ha ejecutado de verdad**: sus pruebas simulan GitHub.

### 13.2 Matriz (2026-11-07, previa a la publicación; **sustituida por la §13.4**)
| Elemento | Estado | Nota |
|---|---|---|
| PR #24 | CUMPLIDO | fusionado como `428ecee` con CI en verde sobre el SHA exacto |
| CI sobre `main` | CUMPLIDO | `Pruebas` #67 (`428ecee`) y #72 (`86bc9cc`) en success; Pages #21 y #23 en success |
| Regresión | CUMPLIDO | 1500/0/35 antes de fusionar; tras la corrección de release: unit 1426, regresión 90 (las 35 omitidas son `tests/golden`, faltan archivos reales) |
| Archivos protegidos | CUMPLIDO | `--check` sin cambios en cada etapa |
| QA estructural | PARCIALMENTE CUMPLIDO | RQ-13 depende de AC-14 |
| QA visual | CUMPLIDO | solo local (LibreOffice) |
| AC-14 | PARCIALMENTE CUMPLIDO | no garantiza el 100 % de errores; observación real GLP-1 |
| AC-15 | CUMPLIDO | |
| AC-16 | CUMPLIDO | |
| AC-21 | CUMPLIDO | 8 de 8 idéntico |
| AC-28 | PARCIALMENTE CUMPLIDO | falta la comprobación desde un navegador externo real y el release publicado |
| GitHub Pages | CUMPLIDO | desplegado (`success`), `app.zip` con el commit fusionado; verificación funcional con Chromium desde el entorno (con Pyodide y plantilla locales) |
| Release v1.0.0 | NO CUMPLIDO | no publicado: borrador residual que esta sesión no puede eliminar |
| Integridad del `app.zip` | PARCIALMENTE CUMPLIDO | verificada en el borrador y contra Pages; falta verificarla en la release publicada |
| AC-11 | FUERA DEL ALCANCE | pendiente de la fase de interfaz (`PENDIENTES_POSTERIORES.md`) |
| AC-12 | FUERA DEL ALCANCE | ídem |
| A-3 | FUERA DEL ALCANCE | decisión narrativa posterior; la narrativa protegida no se tocó |

### 13.3 Publicación real de `app-v1.0.0` (verificada el 2026-11-07)
Registro posterior a la §13.1, tras el diagnóstico de solo lectura del estado de GitHub. No se modificó la release, la etiqueta, `APP_VERSION` ni Pages.
* **Release:** id 437239935, «Aplicación 1.0.0», **publicada** (no borrador ni pre-release) el 2026-11-07 a las 01:28:53 UTC; única release del repositorio. El `created_at` de la API muestra 22:38:10 UTC del día 6 porque GitHub copia ahí la fecha del commit, no la creación real.
* **Etiqueta:** `app-v1.0.0`, ligera, apunta a `428eceeef3e776286e1ec8053ef3cffc0bd9caa9` (merge del PR #24). Es la única etiqueta.
* **Assets:** la API lista 2: `app.zip` (264 195 B) y `app.zip.sha256` (74 B), ambos `uploaded`. La página de la release muestra 4; los otros dos son, con toda probabilidad, los archivos de código fuente que GitHub genera automáticamente (inferencia: no aparecen en la API).
* **Origen:** el **intento 2 del run #2** ([42308811022](https://github.com/appalex47-lab/report-intelligence/actions/runs/42308811022)), relanzado el 2026-11-07 a las 01:28:38 UTC (success a las 01:28:58). En ese intento el job `construir` conserva las horas del intento 1 (2026-11-06 23:00:15–23:00:26): **no se volvió a construir**; solo se re-ejecutó `publicar`, con el artefacto `release-app-v1.0.0` (id 13547456717, creado 23:00:24 UTC, sin caducar). Por eso el SHA-256 coincide con el del borrador analizado el día 6. Se ejecutó la definición de `release.yml` de `428ecee` (la **anterior** a la corrección del PR #26: sin el paso «Esperar el borrador…»); esta vez el listado devolvió el borrador a tiempo. Todos los pasos terminaron en success: CI del commit exacto, etiqueta libre, crear borrador, verificar borrador, publicar y verificar la publicada (etiqueta → commit → artefacto → SHA-256).
* **Orden respecto al borrado del borrador:** el borrador 437146660 ya no existe (la API responde 404), el id de la release publicada es posterior, y el paso «etiqueta (o un borrador) no existe» del job `publicar` (token de escritura) pasó en ese intento, por lo que el borrador ya estaba eliminado. La hora exacta del borrado no se puede determinar con la API. La eliminación no se hizo desde esta sesión.
* **Otros runs de `release.yml` sobre `f8c80c6`:** #4 ([42322926982](https://github.com/appalex47-lab/report-intelligence/actions/runs/42322926982)): los intentos 1 y 2 fallaron en «El commit exacto debe haber superado el CI» (el CI de `f8c80c6` seguía en curso) y el intento 3 terminó en success como ensayo (`publicar` omitido). #5 ([42324625930](https://github.com/appalex47-lab/report-intelligence/actions/runs/42324625930)): los intentos 1 y 2 fallaron en «La etiqueta no debe existir», como debe ser (control anti-duplicados). No se creó ninguna release ni etiqueta adicional.
* **CI de `main` (`f8c80c6`):** `Pruebas` #74 y `Publicar en GitHub Pages` #24 en success.

**Integridad de los assets (comprobación independiente, descargando de GitHub):**
* SHA-256 de `app.zip`: `671a02b92ffde5a9bf4e3c56e0f9a19b491ddf68799092b9a0236119abdbc9c1`; coincide con el contenido de `app.zip.sha256` (`sha256sum -c`: OK) y con el `digest` que reporta GitHub; `app.zip.sha256` tiene `digest` `1d667290ec765a9e2260b4e16c6104800b38ca8db1fb90704ba75b324b1c23b9`.
* Contenido: las 83 entradas de `app.zip` son **idénticas** a las de un paquete regenerado desde `428ecee` (`tools/build_site.py`); `_build_info.json` cita `428eceeef3e776286e1ec8053ef3cffc0bd9caa9`. Los SHA-256 de los zips regenerados no coinciden con el publicado porque el zip no es reproducible bit a bit; por eso se comparó entrada por entrada.
* Frente a `f8c80c6` (final de `main`) solo difiere `backend/app/_build_info.json` (el campo `commit`). Las diferencias de código fuente entre `428ecee` y `f8c80c6` son 7 archivos (+603/−17): `.github/workflows/release.yml`, `tools/release_app.py`, `tests/unit/test_release_espera.py`, `tests/unit/test_release_workflow.py` y tres documentos de `docs/fase5/`; **ninguno forma parte del paquete**. El `app.zip` que sirve Pages hoy (commit `f8c80c6`) es igual al regenerado desde `f8c80c6`.
* Conclusión: la release corresponde al código aprobado de la Fase 5 (`428ecee`) y su paquete equivale al de `f8c80c6` salvo el campo `commit`.

**Observaciones técnicas (no bloquean el cierre de la release):**
1. **La release fija `428ecee`, no el final de `main`.** Pages se redespliega con cada push a `main`; un reporte generado hoy registra en su procedencia `commit = f8c80c6` (o posterior), que no tiene release ni etiqueta. El código empaquetado es el mismo, pero esa referencia no se podrá regenerar mediante una etiqueta. Es una limitación del procedimiento, no un defecto del paquete.
2. **La corrección de `release.yml` (PR #26) no se ha ejercitado en una publicación real.** Esta publicación usó el `release.yml` anterior (reintento del run #2 en `428ecee`). Los runs #4 y #5 solo ejercieron los controles del job `construir`. La rama de publicación corregida sigue validada únicamente por pruebas que simulan GitHub; su primera ejecución real será la de la próxima versión.

### 13.4 Matriz vigente (2026-11-07, tras verificar la publicación)
Sustituye a la §13.2; los cambios respecto a ella son **Release v1.0.0**, **Integridad del `app.zip`** y la nota de AC-28.

| Elemento | Estado | Nota |
|---|---|---|
| PR #24 | CUMPLIDO | fusionado como `428ecee` con CI en verde sobre el SHA exacto |
| CI sobre `main` | CUMPLIDO | `Pruebas` #67 (`428ecee`), #72 (`86bc9cc`) y #74 (`f8c80c6`) en success; Pages #21, #23 y #24 en success |
| Regresión | CUMPLIDO | 1500/0/35 antes de fusionar; tras la corrección de release: unit 1426, regresión 90 (las 35 omitidas son `tests/golden`, faltan archivos reales) |
| Archivos protegidos | CUMPLIDO | `--check` sin cambios en cada etapa |
| QA estructural | PARCIALMENTE CUMPLIDO | RQ-13 depende de AC-14 |
| QA visual | CUMPLIDO | solo local (LibreOffice) |
| AC-14 | PARCIALMENTE CUMPLIDO | no garantiza el 100 % de errores; observación real GLP-1 |
| AC-15 | CUMPLIDO | |
| AC-16 | CUMPLIDO | |
| AC-21 | CUMPLIDO | 8 de 8 idéntico |
| AC-28 | PARCIALMENTE CUMPLIDO | **pendiente de la verificación externa del usuario** (`PUBLICACION_AC28.md` §7); la release ya está publicada |
| GitHub Pages | CUMPLIDO | desplegado (`success`), `app.zip` con el commit de `main`; verificación funcional con Chromium desde el entorno (con Pyodide y plantilla locales) |
| Release v1.0.0 | CUMPLIDO | publicada: etiqueta `app-v1.0.0` → `428ecee`, release 437239935, no borrador (§13.3) |
| Integridad del `app.zip` | CUMPLIDO | SHA-256 coincide con `.sha256` y con GitHub; contenido idéntico al regenerado desde `428ecee` (§13.3) |
| AC-11 | FUERA DEL ALCANCE | pendiente de la fase de interfaz (`PENDIENTES_POSTERIORES.md`) |
| AC-12 | FUERA DEL ALCANCE | ídem |
| A-3 | FUERA DEL ALCANCE | decisión narrativa posterior; la narrativa protegida no se tocó |

### 13.5 Verificación externa de AC-28 por el usuario (2026-11-06)
El usuario verificó el sitio desde un dispositivo **Android con Chrome** (fecha 2026-11-06, hora local aproximada de México; sin modelo ni versión registrados). **Aprobado:** la aplicación abre, la navegación funciona, la generación del PPTX funciona, la descarga funciona y el PPTX descargado abre correctamente; no se detectaron problemas funcionales. **NO VERIFICADA:** la consola de Chrome Android (no hay una computadora para DevTools remoto); no es una aprobación ni un error. **No reportados:** el commit del `app.zip` (paso 3), el panel de validación (paso 4) y el anexo activado/desactivado (paso 6). Detalle en `PUBLICACION_AC28.md` §9.

**Evaluación:** AC-28 **se conserva como PARCIALMENTE CUMPLIDO** según el criterio original del §7 (incluye la consola). El criterio de la especificación 3A (release publicada con su SHA-256) sí está cumplido. Pasaría a CUMPLIDO inspeccionando la consola y reportando los pasos pendientes, o si el usuario dispensa expresamente la consola (desviación aceptada, a registrar). No se usa «cumplido con observación» porque no es un estado definido.

### 13.6 Matriz vigente (2026-11-07, tras la verificación externa del usuario)
Sustituye a la §13.4; el único cambio es la nota de **AC-28** (el estado se conserva). La §13.4 queda como registro histórico.

| Elemento | Estado | Nota |
|---|---|---|
| PR #24 | CUMPLIDO | fusionado como `428ecee` con CI en verde sobre el SHA exacto |
| CI sobre `main` | CUMPLIDO | `Pruebas` #67 (`428ecee`), #72 (`86bc9cc`) y #74 (`f8c80c6`) en success; Pages #21, #23 y #24 en success |
| Regresión | CUMPLIDO | 1500/0/35 antes de fusionar; tras la corrección de release: unit 1426, regresión 90 (las 35 omitidas son `tests/golden`, faltan archivos reales) |
| Archivos protegidos | CUMPLIDO | `--check` sin cambios en cada etapa |
| QA estructural | PARCIALMENTE CUMPLIDO | RQ-13 depende de AC-14 |
| QA visual | CUMPLIDO | solo local (LibreOffice) |
| AC-14 | PARCIALMENTE CUMPLIDO | no garantiza el 100 % de errores; observación real GLP-1 |
| AC-15 | CUMPLIDO | |
| AC-16 | CUMPLIDO | |
| AC-21 | CUMPLIDO | 8 de 8 idéntico |
| AC-28 | PARCIALMENTE CUMPLIDO | verificación externa funcional del usuario (Android, Chrome) **aprobada**; **consola NO VERIFICADA** y pasos 3, 4 y 6 no reportados (`PUBLICACION_AC28.md` §9) |
| GitHub Pages | CUMPLIDO | desplegado (`success`), `app.zip` con el commit de `main`; verificación funcional con Chromium desde el entorno (con Pyodide y plantilla locales) |
| Release v1.0.0 | CUMPLIDO | publicada: etiqueta `app-v1.0.0` → `428ecee`, release 437239935, no borrador (§13.3) |
| Integridad del `app.zip` | CUMPLIDO | SHA-256 coincide con `.sha256` y con GitHub; contenido idéntico al regenerado desde `428ecee` (§13.3) |
| AC-11 | FUERA DEL ALCANCE | pendiente de la fase de interfaz (`PENDIENTES_POSTERIORES.md`) |
| AC-12 | FUERA DEL ALCANCE | ídem |
| A-3 | FUERA DEL ALCANCE | decisión narrativa posterior; la narrativa protegida no se tocó |

## 14. Pendientes posteriores
`PENDIENTES_POSTERIORES.md` (AC-11, AC-12, A-3, L-8, AC-28, `deployment_queued`, navegadores adicionales, plantillas anteriores, golden, anexo por omisión, release).

## 15. Limitaciones y riesgos
No se validó: el aspecto en PowerPoint, el sitio publicado desde un navegador externo (sí se verificó parcialmente desde el entorno, §12), datos de producción, Firefox/Safari/WebViews, ni el significado de una cifra. El detector de AC-14 no es exhaustivo.

## 16. Dictamen técnico (2026-11-07, previo a la publicación; **sustituido por la §16.1**)
**FASE 5 FUSIONADA CON OBSERVACIONES** (2026-11-07). Integrados en `main` el PR #24 (Fase 5), el PR #26 (corrección de `release.yml`) y el PR #25 (registro documental); CI y Pages en verde. **No** se declara «fusionada y publicada, pendiente de verificación externa» porque el release `app-v1.0.0` **no está publicado**, y tampoco «cerrada y verificada» porque AC-28 carece de la comprobación desde un navegador externo real. Para el cierre faltan: eliminar el borrador 437146660, ejecutar el release (ensayo y publicación) y la verificación del §7 de `PUBLICACION_AC28.md`. AC-11, AC-12 y A-3 siguen pendientes. No se inició la Fase 6.

### 16.1 Dictamen técnico vigente (2026-11-07)
**FASE 5 FUSIONADA Y PUBLICADA, PENDIENTE DE VERIFICACIÓN EXTERNA.** PR #24, #26, #25 y #27 integrados en `main` (`f8c80c6`) con CI y Pages en verde; la release `app-v1.0.0` está publicada y su integridad verificada (§13.3). **No** se declara «cerrada y verificada» porque AC-28 sigue PARCIALMENTE CUMPLIDO: falta la comprobación del sitio desde un navegador externo real, que debe hacer el usuario (`PUBLICACION_AC28.md` §7). Quedan además las observaciones técnicas 1 y 2 de la §13.3, y AC-11, AC-12 y A-3 siguen pendientes. No se inició la Fase 6.

### 16.2 Dictamen técnico vigente tras la verificación externa (2026-11-07)
**FASE 5 FUSIONADA Y PUBLICADA, CON VERIFICACIÓN EXTERNA FUNCIONAL REALIZADA POR EL USUARIO; AC-28 PARCIALMENTE CUMPLIDO (consola NO VERIFICADA).** Sustituye a la §16.1 en lo relativo a la verificación externa: ya existe evidencia de una persona usuaria con un navegador real (§13.5). **No** se declara «cerrada y verificada» mientras AC-28 no sea CUMPLIDO por el criterio original; la decisión de cómo cerrar el punto de la consola es del usuario. Siguen pendientes AC-11, AC-12, A-3 y las observaciones de la §13.3. No se inició la Fase 6.

### 16.3 Dictamen final de la Fase 5 (cierre formal, 2026-11-07)
**FASE 5: COMPLETADA, FUSIONADA Y PUBLICADA, CON OBSERVACIONES DE VERIFICACIÓN EXTERNA.** Sustituye a las §16.1 y §16.2 como dictamen vigente; ambas se conservan como registro histórico. El cierre formal lo **autoriza expresamente el usuario** el 2026-11-07, una vez fusionado el PR [#29](https://github.com/appalex47-lab/report-intelligence/pull/29) (merge `4df15399dce8cde762535d62d626d3e7cec3fde6`).

**Qué se afirma:** el trabajo de la Fase 5 está completo, integrado en `main` con CI en verde, y publicado (Pages desplegado y release `app-v1.0.0` publicada con su integridad verificada, §13.3). La aplicación se probó en un navegador Android real (Chrome) y el usuario confirmó: apertura, navegación, generación del reporte PPTX, descarga del archivo y apertura correcta del PPTX descargado, sin problemas funcionales (§13.5).

**Qué NO se afirma (observaciones de verificación externa, sin cambio de estado):**
* **AC-28: PARCIALMENTE CUMPLIDO.** No pasa a CUMPLIDO y el cierre de la fase no dispensa ninguno de los pasos pendientes.
* **Consola de Chrome Android: NO VERIFICADA** (ni aprobada ni error).
* **Pasos 3, 4 y 6 del procedimiento de AC-28: NO REPORTADOS** (commit del `app.zip`, panel de validación y anexo activado/desactivado).
* No se registraron el modelo del dispositivo ni la versión del navegador.

Estas limitaciones no invalidan las pruebas funcionales que sí se realizaron.

## 17. Separación entre el cierre de la Fase 5 y los pendientes posteriores
**Trabajo necesario para declarar terminada la Fase 5: concluido** (PR #24, #26, #25, #27, #28 y #29 fusionados; CI y Pages en verde; release publicada e íntegra; documentación de cierre coherente).

**Pendientes posteriores que permanecen ABIERTOS** (no se marcan como resueltos; detalle, causa, acción y evidencia en `PENDIENTES_POSTERIORES.md`):

| Pendiente | Estado |
|---|---|
| AC-11 (estados de reproducibilidad en la interfaz) | NO CUMPLIDO · FUERA DEL ALCANCE de la Fase 5; fase de interfaz por definir |
| AC-12 (reportes previos como legado en la interfaz) | NO CUMPLIDO · FUERA DEL ALCANCE de la Fase 5; fase de interfaz por definir |
| A-3 (narrativa protegida «Mounjaro (74 %, $9.20 M)» sin base declarada) | decisión narrativa posterior pendiente; no se tocó la narrativa |
| Versionado de la release (fija `428ecee`; Pages registra `main` vigente) | decisión del usuario pendiente |
| Primera publicación real con el `release.yml` corregido (PR #26) | sin ejercitar en real |
| AC-28: consola de Chrome Android y pasos 3, 4 y 6 | NO VERIFICADA / NO REPORTADOS; AC-28 PARCIALMENTE CUMPLIDO |
| Firefox, Safari y WebViews; causa raíz de `data.htm`; pruebas `golden` (35 omitidas); plantillas de versiones anteriores | abiertos (ver `PENDIENTES_POSTERIORES.md` §5) |

No se inició ninguna fase posterior (escenarios y SlideSpec, diseño adaptativo, QA y previsualización ni la siguiente fase general); requieren autorización expresa.
