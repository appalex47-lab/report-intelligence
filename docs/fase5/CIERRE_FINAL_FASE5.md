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
* Publicación (`publicar=true`), run 42308811022: **failure** en «Verificar el borrador»: `ERROR: debe haber exactamente una release para la etiqueta y hay 0`. La verificación consultó el listado de releases ≈1 s después de crear el borrador (creado 23:00:35, consulta 23:00:36) y no lo vio todavía; poco después el borrador sí aparece con `tag_name: app-v1.0.0`. Es una **condición de carrera del workflow** (nunca se había ejecutado de verdad: V-02 de la 3A-5), no un defecto del paquete.
* Estado resultante, fallido de forma segura: borrador `app-v1.0.0` (id 437146660, no publicado), `target_commitish` = `428ecee`, assets `app.zip` (264 195 B) y `app.zip.sha256`; el SHA-256 del `app.zip` del borrador (`671a02b92ffde5a9bf4e3c56e0f9a19b491ddf68799092b9a0236119abdbc9c1`) coincide con su `.sha256`; su contenido es idéntico al `app.zip` publicado en el sitio (83 entradas, 0 diferencias). **No existe etiqueta git ni release publicada.**
* No se forzó ni se publicó por otra vía. El borrador bloquea un nuevo intento (`etiqueta-libre` incluye borradores); el permiso para eliminarlo fue denegado por el entorno, por lo que queda a decisión del usuario.
* **Qué falta:** (a) eliminar el borrador 437146660; (b) corregir `release.yml` con una espera/reintento tras crear el borrador (cambio en un workflow protegido: requiere autorización y PR propio); (c) volver a ejecutar `publicar=true`. Mientras tanto el release **no está publicado**.

## 14. Pendientes posteriores
`PENDIENTES_POSTERIORES.md` (AC-11, AC-12, A-3, L-8, AC-28, `deployment_queued`, navegadores adicionales, plantillas anteriores, golden, anexo por omisión, release).

## 15. Limitaciones y riesgos
No se validó: el aspecto en PowerPoint, el sitio publicado, datos de producción, Firefox/Safari/WebViews, ni el significado de una cifra. El detector de AC-14 no es exhaustivo.

## 16. Dictamen técnico definitivo
**FASE 5 FUSIONADA CON OBSERVACIONES.** El PR #24 está integrado en `main` (`428ecee`), con CI en verde y publicación desplegada y verificada de forma parcial. No es «cerrada y verificada» porque AC-28 carece de verificación desde un navegador externo y el release `app-v1.0.0` **no está publicado** (borrador por fallo del workflow). AC-11, AC-12 y A-3 siguen pendientes (`PENDIENTES_POSTERIORES.md`). No se inició la Fase 6.
