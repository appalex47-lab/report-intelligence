# AC-28 · publicación real y GitHub Pages: estado, evidencia y procedimiento

**AC-28 permanece NO DEMOSTRADO.** Un workflow verde, un despliegue «success» o pruebas locales no lo cumplen: exige una publicación real de la versión `app-vX.Y.Z` con su `app.zip` y su SHA-256, verificada.

## 1. Configuración verificada (5.1)

| Elemento | Hallazgo | Fuente |
|---|---|---|
| Workflow de publicación | `.github/workflows/pages.yml` (*Publicar en GitHub Pages*): se dispara con `push` a `main` y a mano; `permissions: contents: read, pages: write, id-token: write`; job `build` (`python tools/build_site.py --out _site` + `upload-pages-artifact@v3`) y job `deploy` (`deploy-pages@v4`, entorno `github-pages`) | el archivo |
| Rama de publicación | `main` (única) | `on.push.branches` |
| Fuente de Pages | debe ser «GitHub Actions» (Settings → Pages); **no verificable desde aquí** (la API de Pages devuelve 403 por el proxy). Es coherente con que el despliegue se cree y complete («Created deployment for 47dc3af…», «Reported success!») | logs del run 20 |
| Artefacto | sitio estático: `index.html`, `worker.js`, `app.zip` (backend + perfiles, con `_build_info.json` sellado con versión y SHA), 4 wheels, `.nojekyll`; el motor Pyodide **no** va en el sitio (se carga de la CDN) | `tools/build_site.py`; log: «app.zip (78 archivos)» |
| Rutas | todas relativas (`index.html`, `worker.js`, `app.zip`, `wheels/…`, `templates/…`): coherentes con servir bajo `/report-intelligence/` | `frontend/*`, `build_site.py` |
| Plantillas PPTX | no se versionan ni se publican; la aplicación las pide a `/templates/<formato>/1/template.pptx` y, si faltan (404), pide cargarlas en la pestaña «Plantillas» | `worker.js`, pruebas e2e |
| Errores de construcción | ninguno: `build` terminó en success en los runs 18, 19 y 20 | Actions |

## 2. Evidencia de publicación disponible (y su alcance)

| Dato | Valor | Cómo se obtuvo |
|---|---|---|
| Despliegue sobre `main` tras el #21 | run 18, `f15abfe`, success | API de Actions |
| Tras fusionar el #22 | run 19, `9007f75`, **cancelado** | API de Actions |
| Tras fusionar el #23 | run 20, **`47dc3af47e9425cebd135e9aec0b4a2f783225ff`**: falló 3 veces en `deploy-pages` («Deployment failed, try again later», estado `deployment_queued` hasta agotar el tiempo) y **terminó en success en el 4.º intento** | API de Actions y logs del job |
| URL del entorno | `https://appalex47-lab.github.io/report-intelligence/` | log: «Evaluated environment url» |
| SHA publicado | `47dc3af` (contiene los PR #22 y #23; **no** contiene la Fase 5) | log: «Created deployment for 47dc3af…» |

**Alcance de esta evidencia:** prueba que GitHub reportó un despliegue correcto del SHA `47dc3af`. **No prueba** que el sitio cargue, que corresponda a ese SHA ni que funcione.

**Investigación de la concurrencia (`cancel-in-progress: true`), con logs de los jobs `deploy`:**

| Run / intento | Hecho observado (log) |
|---|---|
| 19 (PR #22), intento 1 | `deploy-pages` en `deployment_queued` desde las 17:51:19 durante ~9 min **sin avanzar** (atasco del lado de GitHub, anterior a cualquier cancelación). A las 18:00:00 aparece `Canceling Pages deployment…` / `Canceled deployment…`: lo canceló la concurrencia al iniciar el run 20 |
| 20 (PR #23), intentos 1, 2 y 3 | `deployment_queued` sostenido y `##[error]Deployment failed, try again later.` (6 min, 1,5 min y 1,7 min) |
| 19, intento 2 (reintento manual) | cancelado a los 6 s por la concurrencia al arrancar el intento 4 del run 20 |
| 20, intento 4 | `deploy-pages` en success en 6 s |
| Runs 15, 16, 17 y 18 (misma configuración) | success sin incidencias, incluidas fusiones seguidas |

**Conclusión (decisión del 2026-11-06):** la concurrencia **sí produce cancelaciones** (run 19, dos veces) —es su función: descarta el despliegue superado—, pero **no hay evidencia suficiente de que provoque los fallos**: el atasco en `deployment_queued` del run 19 empezó 9 minutos antes de la cancelación; no se demuestra que el despliegue cancelado dejara bloqueado el siguiente (en el intento 4 hubo una cancelación y el despliegue funcionó); y la misma configuración funcionó cuatro veces. Cambiar a `cancel-in-progress: false` no se demuestra necesario, por lo que **se conserva `pages.yml` sin cambios** (autorizado solo si se demostraba necesario). La recomendación queda como hipótesis no demostrada y como opción si el atasco se repite:

```yaml
# opción NO aplicada (hipótesis no demostrada; GitHub la recomienda en su plantilla de Pages)
concurrency:
  group: pages
  cancel-in-progress: false
```

## 3. Verificación externa (5.3): intento y resultado

| Intento | Resultado exacto | Clasificación |
|---|---|---|
| `curl https://appalex47-lab.github.io/report-intelligence/` | `curl: (56) CONNECT tunnel failed, response 403`; código HTTP 000 | **proxy del entorno** |
| `curl https://example.com` (control) | el mismo `CONNECT tunnel failed, response 403` | confirma que el proxy bloquea **cualquier** host no autorizado |
| `WebFetch` a `https://appalex47-lab.github.io/report-intelligence/` (ruta de red distinta de `curl`, 2026-11-06) | `getaddrinfo ENOTFOUND appalex47-lab.github.io`: el host está fuera de los dominios permitidos de la sesión | limitación de red del entorno; para verificar desde aquí habría que permitir ese host en la red del entorno |
| API de Pages (`gh api repos/…/pages`) | 403 «Access to this GitHub API path is not permitted through this proxy» | permisos del proxy |
| Descarga del artefacto `github-pages` (id 13528548724, no expirado) | falla al resolver el almacenamiento de blobs de Actions | proxy del entorno |

**No hay evidencia de que el sitio esté caído ni de que funcione**: la limitación es de acceso desde este entorno (red/proxy), no de publicación ni de la aplicación. No se inventó ninguna captura ni resultado.

## 4. Verificaciones que deben hacerse desde un navegador externo

Con el sitio publicado desde un `main` que **ya contenga la Fase 5** (esta rama fusionada):

1. Abrir `https://appalex47-lab.github.io/report-intelligence/` en Chrome, Firefox y Safari (y móvil): carga sin pantalla de error; el arranque del motor termina («Iniciando el motor en tu navegador…» desaparece).
2. Consola del navegador sin errores bloqueantes; pestaña Red sin recursos caídos (esperados: 404 de `templates/*/template.pptx` si no se publicaron plantillas).
3. Verificar el SHA publicado: `curl -sL <url>/app.zip -o app.zip && unzip -p app.zip backend/app/_build_info.json` → el campo `commit` debe ser el SHA completo del `main` fusionado y **sin** el sufijo `+dirty` (que marca un árbol modificado).
4. Cargar un libro de ejemplo (`data/ejemplos/GLP1_crudo_ejemplo.xlsx`), elegir GLP-1 / mensual / septiembre 2026: el paso «Validar» muestra el panel de escenarios y el anexo de calidad.
5. Con plantillas cargadas: generar el reporte, marcar y desmarcar «Incluir el anexo…», descargar el `.pptx` (extensión y contenido correctos), abrirlo en PowerPoint y revisar las diapositivas.
6. Descargar `anexo_calidad.json`, `narrative.json`, `qa_report.json`, `manifest.json`, `procedencia.json`, y el historial (`historial.sqlite`).
7. Registrar fecha, navegador, versión, SHA y resultados.

## 5. Procedimiento exacto tras la autorización de fusión del PR #24

1. Fusionar el PR #24 (autorización del usuario). El `push` a `main` dispara *Publicar en GitHub Pages*.
2. Esperar el run de Pages sobre el SHA de fusión y comprobar `conclusion: success`. **Si falla en `deploy-pages` con `deployment_queued`**, relanzar solo el job fallido (ya ocurrió con el run 20); si persiste, cancelar el despliegue pendiente desde Settings → Pages.
3. Ejecutar las verificaciones del §4 desde un navegador externo.
4. **Release (solo con autorización y tras el paso 3):** ensayo `gh workflow run release.yml -f publicar=false` (construye, valida, comprueba CI y etiqueta libre; no crea nada); con el ensayo en success y `APP_VERSION` decidida, `gh workflow run release.yml -f publicar=true` desde `main`: crea el **borrador**, verifica los assets descargados, lo publica y comprueba etiqueta → commit → `app.zip` → SHA-256.
5. Comprobar la release publicada: `gh release view app-vX.Y.Z`, descargar `app.zip` y `app.zip.sha256`, `sha256sum -c`, y que `_build_info.json` dentro del zip coincida con el SHA etiquetado.
6. Solo entonces actualizar AC-28 a CUMPLIDO, con la evidencia anterior (SHA, URL, fecha, navegador).

## 6. Dictamen

**AC-28: NO DEMOSTRADO.** Preparado: configuración verificada, procedimiento exacto y lista de verificaciones externas. Falta: la fusión del #24, la publicación real, la verificación desde un navegador externo y la ejecución de `release.yml` con `publicar=true`.

### Actualización posterior a la fusión (2026-11-06)
El dictamen anterior es el de antes de fusionar. Tras la fusión del PR #24 (`428ecee`) y con el host de Pages permitido en el entorno, AC-28 pasa a **PARCIALMENTE CUMPLIDO**: despliegue `success`, `app.zip` publicado con `commit` = SHA fusionado y recorrido funcional con Chromium contra el sitio real (con el runtime de Pyodide y la plantilla servidos localmente). Falta la verificación desde un navegador externo y el release publicado (el run 42308811022 falló al verificar el borrador). Detalle y límites en `CIERRE_FINAL_FASE5.md` §12–13.

## 7. Procedimiento para la comprobación final de AC-28 desde tu dispositivo (2026-11-07)
La prueba con Chromium automatizado **no equivale** a esta comprobación: usó el runtime de Pyodide y la plantilla servidos desde archivos locales. Aquí se comprueba el sitio tal como lo ve una persona usuaria.

**Qué necesitas:** un navegador de tu dispositivo (idealmente uno distinto de Chrome de escritorio: Safari o Firefox, y el móvil), el libro de ejemplo `data/ejemplos/AETOPS_crudo_ejemplo.xlsx` del repositorio y, para generar el PPTX, la plantilla `templates/aetops-mensual/1/template.pptx` (no se publica).

1. Abre `https://appalex47-lab.github.io/report-intelligence/`. **Esperado:** la página carga y «Iniciando el motor en tu navegador…» desaparece (la primera vez descarga Pyodide del CDN, puede tardar un minuto).
2. Abre las herramientas de desarrollo (en móvil, una consola remota o conectar el dispositivo) y revisa la consola. **Esperado:** sin errores en rojo. Son esperables 404 de `templates/*/template.pptx` mientras no cargues plantillas.
3. Verifica el commit publicado (en cualquier terminal): `curl -sL https://appalex47-lab.github.io/report-intelligence/app.zip -o app.zip && unzip -p app.zip backend/app/_build_info.json`. **Esperado:** `commit` es el SHA del `main` vigente al desplegar (`86bc9cc2a4d3355b6ef0fff435c001fc0c166d36` o posterior) y **sin** `+dirty`.
4. Carga el libro de ejemplo, elige AETOPS / mensual / septiembre 2026 y pulsa «Validar». **Esperado:** aparece el panel de validación con los escenarios y el anexo de calidad.
5. Si cargas la plantilla de AETOPS mensual: genera el reporte y descarga el `.pptx`. **Esperado:** se guarda como `Resultados_AETOP_Septiembre_2026.pptx` (no `data.htm`), abre en PowerPoint y tiene 13 diapositivas; el banner dice «Revisión estructural. La revisión visual requiere render».
6. Marca y desmarca «Incluir el anexo…» y repite: con la casilla marcada el PPTX debe terminar con la diapositiva «Calidad de datos y supuestos».
7. Anota **fecha, dispositivo, navegador y versión, resultado de cada paso y cualquier error de consola**. Si algo falla, indica el paso y el texto exacto del error.

AC-28 solo pasa a CUMPLIDO con este resultado **y** con el release publicado (§5 puntos 4 y 5 del procedimiento anterior).

## 8. Actualización de la publicación (2026-11-07)
La release `app-v1.0.0` ya está **publicada** (id 437239935, etiqueta → `428eceeef3e776286e1ec8053ef3cffc0bd9caa9`, `app.zip` SHA-256 `671a02b92ffde5a9bf4e3c56e0f9a19b491ddf68799092b9a0236119abdbc9c1`, verificado contra `app.zip.sha256`). Detalle, origen (reintento del run #2 con el `release.yml` anterior) e integridad en `CIERRE_FINAL_FASE5.md` §13.3. Con esto, los puntos 4 y 5 del §5 («release publicado y comprobado») quedan **resueltos**; no se debe ejecutar de nuevo `publicar=true` para `1.0.0` (la etiqueta existe y el control anti-duplicados lo rechazará).

**AC-28 sigue PARCIALMENTE CUMPLIDO y pendiente de la verificación externa del usuario (§7).** Para el paso 3 del §7: el `app.zip` que sirve Pages cita el commit de `main` vigente al desplegar (`f8c80c6c3d2d6935c0d1649c1cabc9581394f91d` o posterior), mientras que el `app.zip` de la release cita `428eceeef3e776286e1ec8053ef3cffc0bd9caa9`; ambos tienen el mismo código empaquetado y solo difiere `_build_info.json`. Ver la observación técnica 1 de la §13.3.

## 9. Resultado de la verificación externa del usuario (2026-11-06)
Realizada por el usuario desde un **dispositivo Android**, con **Chrome**; fecha **2026-11-06, hora local aproximada de México** (la hora exacta no se registró). **No se registraron** el modelo del dispositivo ni la versión del navegador, y no se inventan. Los resultados los confirma el usuario; esta sesión no los observó.

| Paso del §7 | Resultado | Nota |
|---|---|---|
| 1. Abrir el sitio | **APROBADO** | «La aplicación abre correctamente desde GitHub Pages» |
| (navegación) | **APROBADO** | «La navegación funciona correctamente» |
| 2. Consola del navegador | **NO VERIFICADA** | no se pudo inspeccionar la consola de Chrome Android: no hay una computadora para usar Chrome DevTools remoto. No es una aprobación ni un error |
| 3. Commit del `app.zip` publicado | **NO REPORTADO** | no consta que se ejecutara |
| 4. Validar y ver el panel de escenarios/anexo | **NO REPORTADO por separado** | la generación del reporte (siguiente fila) funcionó, pero no se confirmó el panel de forma específica |
| 5. Generar el reporte PPTX | **APROBADO** | «La generación del reporte PPTX funciona» |
| 5. Descargar el PPTX | **APROBADO** | «La descarga del PPTX funciona» |
| 5. Abrir el PPTX descargado | **APROBADO** | «El archivo PPTX descargado abre correctamente» (no se informaron el nombre del archivo, el número de diapositivas ni el texto del banner) |
| 6. Anexo de calidad activado/desactivado | **NO REPORTADO** | |
| 7. Registro | parcial | fecha y hora aproximada, plataforma (Android) y navegador (Chrome); sin modelo ni versión |

«No se detectaron problemas funcionales durante estas pruebas» (usuario). **Distinción que debe mantenerse:** las pruebas **funcionales** de los pasos 1 y 5 están aprobadas; la **inspección de la consola** (paso 2) no se realizó y permanece **NO VERIFICADA**.

**Build probado:** no se registró qué commit tenía desplegado Pages durante la prueba (se redespliega con cada push a `main`). Todos los commits de `main` desde `428ecee` hasta `6ea53b9` solo cambian archivos que no forman parte del paquete (workflow de release, `tools/release_app.py`, pruebas y documentación; verificado con `git diff --name-only`), de modo que el código de la aplicación probada es el mismo, con independencia del despliegue concreto.

**Distinguir esta prueba de las automatizadas:** es la primera prueba de una persona usuaria con un navegador real (§2 y §8 solo tenían Chromium automatizado con Pyodide y plantilla locales). Aporta evidencia sobre Pyodide desde el CDN real y la descarga en un navegador móvil, pero no sustituye a los pasos no reportados.

### 9.1 Evaluación del estado de AC-28
* **Criterio de la especificación de la 3A** (`release.yml` etiqueta `app-vX.Y.Z` y publica `app.zip` con su SHA-256): **cumplido** por la release publicada y su integridad verificada (`CIERRE_FINAL_FASE5.md` §13.3).
* **Criterio de verificación de la Fase 5** (§7: abrir, revisar la consola sin errores bloqueantes, verificar el commit, generar y descargar el PPTX; «solo pasa a CUMPLIDO con este resultado y con el release publicado»): el release está publicado y los pasos funcionales están aprobados, pero **la consola está NO VERIFICADA** y los pasos 3, 4 y 6 no constan.
* **Conclusión: AC-28 se conserva como PARCIALMENTE CUMPLIDO.** «Cumplido con observación» no es uno de los estados definidos (CUMPLIDO, PARCIALMENTE CUMPLIDO, NO CUMPLIDO, NO VERIFICABLE, FUERA DEL ALCANCE) y rebajar a posteriori un paso del procedimiento aprobado sería cambiar el criterio. Pasa a CUMPLIDO si ocurre una de dos cosas: (a) se inspecciona la consola en el dispositivo (p. ej. Chrome DevTools remoto desde una computadora) y se reportan los pasos 3, 4 y 6; o (b) **el usuario decide expresamente** dispensar la inspección de consola, y entonces se registra como desviación aceptada por el usuario. Esta sesión no toma esa decisión.
