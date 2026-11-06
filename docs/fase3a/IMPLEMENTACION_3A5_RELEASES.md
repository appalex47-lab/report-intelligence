# Fase 3A-5 · Releases etiquetadas `app-vX.Y.Z` (decisión A-5)

| | |
|---|---|
| Fuentes oficiales | `ESPECIFICACION_FASE3A_PROCEDENCIA.md` §10 (3A-5), §12.1, AC-28, L-2, H-6 · `docs/fase1/ESPECIFICACION_FASE1_REPORT_INTELLIGENCE_FINAL.md` §5.3 (propuesta de etiquetar cada despliegue), RQ-12, T-16, V-02, AC-28, A-5 · `docs/fase1/implementacion/DECISIONES_DELEGADAS.md` DD-16 |
| Depende de | 3A-1 (`APP_VERSION` y SHA estampado en `app.zip`), 3A-3 (el manifiesto registra `version_codigo` = versión + SHA) y 3A-4 (el estado `parcial` por código no recuperable). **Ninguno de sus contratos cambia** |
| Estado | Implementada y endurecida; PR independiente **sin fusionar**. **No se ha publicado ninguna release ni se ha ejecutado el workflow en GitHub** |
| Fuera de alcance | 3A-6/3B, interfaz, motor de reglas, publicar una release, modificar workflows existentes o `tools/build_site.py`, validar la ejecución real (V-02, ver §8) |

## 1. Qué se pidió y de dónde sale

La especificación define 3A-5 en una sola línea: *«`release.yml` etiqueta `app-vX.Y.Z` y publica su `app.zip` con su SHA-256 (V-02, AC-28)»*, con el archivo `.github/workflows/release.yml`. La propuesta original (Fase 1 §5.3) añade el motivo: reproducir con código anterior exige poder obtenerlo; sin release publicada el estado es `parcial`. DD-16 dejó la decisión «recomendada pero no ejecutada» hasta que se ordenara la Fase 3A; la autorización expresa de la subfase 3A-5 es la orden que faltaba.

**Requisito oficial** (de la especificación): etiquetar `app-vX.Y.Z` y publicar su `app.zip` con su SHA-256. **Todo lo demás de este documento son decisiones técnicas** (T-1 a T-12): la especificación no define el disparo, la validación, los nombres de los assets ni qué CI es obligatorio. Se tomaron siempre en el sentido más restrictivo y no se presentan como requisitos oficiales.

## 2. Qué se implementó

| Archivo | Tipo | Contenido |
|---|---|---|
| `.github/workflows/release.yml` | nuevo | Dos jobs separados: **`construir`** (solo lectura) y **`publicar`** (único con escritura, solo con `publicar` marcado) |
| `tools/release_app.py` | nuevo | Valida y verifica, sin red ni git: `preparar`, `verificar-ci`, `etiqueta-libre`, `verificar-carpeta`, `verificar-release`. Solo biblioteca estándar |
| `tests/unit/test_release_app.py`, `test_release_publicacion.py`, `test_release_workflow.py` | nuevos | Lógica y zip (69), cadena etiqueta→commit→artefacto→SHA y CI (121), estructura del workflow (35). Corren en CI |
| `ESPECIFICACION_FASE3A_PROCEDENCIA.md` | modificado | Seguimiento de estado (3A-5, AC-28, L-2, H-6, §12.1); sin cambiar requisitos |

No se modificó ningún archivo existente de código, de pruebas ni de workflows (`pages.yml`, `pdf.yml`, `tests.yml`) ni `tools/build_site.py`.

## 3. Arquitectura del workflow

```
workflow_dispatch (manual; publicar=false por omisión)
 └─ construir   permisos: contents: read, actions: read      (solo si ref = main)
      build_site → preparar (valida el zip, escribe app.zip / app.zip.sha256 / NOTAS.md)
      → verificar-ci (el SHA exacto superó tests.yml)  → etiqueta-libre (ni ref ni release)  → artefacto
      │   con publicar=false el workflow termina aquí (ensayo): no hay etiqueta ni release
 └─ publicar    permisos: contents: write, actions: read     (needs: construir; if: inputs.publicar y ref = main)
      descargar artefacto → verificar-carpeta (= la que construyó el job anterior, mismo SHA-256)
      → vuelve a comprobar CI y etiqueta libre (ahora también ve los borradores)
      → crea la release como BORRADOR (todavía no existe la etiqueta)
      → verifica el borrador descargando sus assets de GitHub
      → publica el borrador (GitHub crea la etiqueta en el commit exacto)
      → verifica la publicada: etiqueta → commit → artefacto → SHA-256
```

Ventaja del borrador: mientras es borrador **no existe la etiqueta**, así que un fallo antes de publicar no deja una etiqueta apuntando a un artefacto sin verificar.

## 4. Vínculo versión → etiqueta → commit → build → artefacto → SHA-256

| Eslabón | Cómo se verifica (`tools/release_app.py`) |
|---|---|
| versión → etiqueta | `etiqueta(APP_VERSION)`; SemVer estricto (`fullmatch`) |
| etiqueta libre | `verificar_etiqueta_libre`: no hay `refs/tags/<tag>` exacta ni una release (publicada o borrador) con ese `tag_name`; una respuesta que no es lista (p. ej. `{"message": "Not Found"}`) **no** cuenta como «libre» |
| etiqueta → commit | `commit_de_etiqueta`: **ligera** (`object.type = commit`) o **anotada** (`object.type = tag` + lectura del objeto, que debe apuntar directamente a un `commit`); `tree`, `blob`, anotada anidada o sin su objeto se rechazan; la referencia debe ser la de esa etiqueta |
| commit → build | el zip trae `_build_info.json` con `commit` exactamente igual (sin `+dirty` ni `desconocido`) y `APP_VERSION` empaquetado igual a la versión |
| build → artefacto | `verificar_carpeta`: la carpeta que recibe el job de publicación tiene el mismo SHA-256 que calculó el job de construcción y `NOTAS.md` coincide |
| artefacto → SHA-256 | `verificar_release`: los assets **descargados de GitHub** son exactamente `app.zip` y `app.zip.sha256`, estado `uploaded`, tamaño igual al declarado; el SHA-256 del `app.zip` descargado es el esperado; el archivo `.sha256` es coherente; el zip valida contra el commit de la etiqueta; las notas citan etiqueta, commit y SHA-256 |

## 5. Validación del CI del SHA exacto (decisión T-11)

**Ambigüedad documentada.** La especificación pide «CI en verde» como criterio general de las subfases, pero no lista qué checks son obligatorios para publicar una release. No se inventa una política oficial: se adopta una decisión técnica conservadora y comprobable, coherente con los controles que ya existen (`tests.yml` ejecuta unidad, regresión y la prueba obligatoria de Pyodide):

* Se consultan las ejecuciones de workflow del **SHA exacto** (`/actions/runs?head_sha=…&per_page=100`).
* Es **obligatoria** al menos una ejecución de `tests.yml` en `success`.
* Se rechaza cualquier ejecución (de cualquier workflow, salvo el propio `release.yml`) que esté pendiente, fallida, cancelada, con conclusión desconocida o de **otro SHA**.
* Se rechaza una respuesta que no tiene el formato esperado (errores de la API incluidos), que está incompleta (`total_count` ≠ ejecuciones devueltas) o que llena la página (podría haber más).
* Consecuencia asumida: si el despliegue de Pages del mismo commit sigue en curso, la publicación se rechaza hasta que termine (se puede reintentar).

## 6. Seguridad y permisos

| Aspecto | Medida (comprobada por pruebas estructurales) |
|---|---|
| Disparo | solo `workflow_dispatch`; `publicar` es booleano y vale `false` por omisión |
| Permisos globales | `permissions: {}` (ninguno por omisión) |
| `construir` | `contents: read`, `actions: read`; no contiene `gh release`, `PATCH`, `git tag` ni `git push` |
| `publicar` | único con `contents: write` (+ `actions: read` para releer el CI); `needs: construir`; `if` exactamente `inputs.publicar && github.ref == 'refs/heads/main'` (sin `always()` que anule el `needs`) |
| Ramas | ambos jobs solo desde `refs/heads/main` |
| Inyección de comandos | ningún script de shell contiene `${{ … }}`: las entradas y salidas llegan por `env`; las salidas se validan (SemVer, SHA hexadecimales) antes de escribirse en `$GITHUB_OUTPUT`, que nunca recibe un valor con salto de línea |
| Credenciales | `checkout` con `persist-credentials: false`; único token: `github.token`; sin secretos |
| Acciones | versiones fijadas (`checkout@v4`, `setup-python@v5`, `upload-artifact@v4`, `download-artifact@v4`) |
| Errores | sin `|| true`, `continue-on-error`, `set +e` ni `2>/dev/null`; los pasos fallan ante cualquier error de `gh` |
| Reescritura | sin `--clobber`, borrado, `--force` ni `tag -f`; si la etiqueta o una release ya existen, falla |
| Concurrencia | grupo `release`, sin cancelar una publicación en curso |
| Zip | rechaza rutas absolutas, `..`, `\`, `./`, dobles `//`, entradas duplicadas, enlaces simbólicos, más de 5000 entradas, más de 600 MB descomprimidos, archivos de identificación vacíos o desmesurados |

## 7. Pruebas

| Archivo | Pruebas | Qué demuestra |
|---|---|---|
| `test_release_app.py` | 69 | versión y etiqueta (15 versiones inválidas), `validar_zip` (11 causas de rechazo), endurecimiento del zip, `preparar`, `verificar_carpeta` (8 alteraciones), `app.zip` real de `build_site.py`, CLI |
| `test_release_publicacion.py` | 121 | etiqueta ligera y anotada válidas; etiqueta a otro commit; etiqueta inexistente; etiqueta duplicada o ya usada (referencia, release publicada, borrador); artefacto de otra versión o de otro commit; hash incorrecto; asset inexistente, de más, duplicado; descarga fallida o incompleta; metadatos inconsistentes; CI (fallido, pendiente, cancelado, ausente, de otro SHA, error de API, respuesta incompleta o paginada); CLI de punta a punta; recorrido de toda la cadena |
| `test_release_workflow.py` | 35 | estructura de dos jobs, permisos, condiciones, orden, ausencia de operaciones peligrosas, sintaxis de los scripts con `bash -n`, coherencia con las opciones de la CLI y 23 mutaciones del workflow |

Todo se ejecuta **sin publicar nada y sin crear etiquetas**: las respuestas de GitHub son JSON simulados con la forma documentada de la API.

**Hallazgos de las propias pruebas, corregidos:** (1) `$` en las regex aceptaba un salto de línea final; (2) la CLI de `etiqueta-libre` fallaba por leer un argumento inexistente; (3) el verificador de estructura no rechazaba `always()` en la condición de `publicar`. Además, 24 mutaciones deliberadas del script (copia fuera del repositorio) son detectadas por las pruebas.

## 8. Qué NO se verificó (requisitos no verificables)

* **V-02 / AC-28 — ejecución real del workflow.** Requiere publicar una release (acción hacia fuera) y no se hizo. Lo probado es la lógica y la estructura; **no** que GitHub se comporte como se asume en: la creación de borradores con `gh release create --draft`, la creación de la etiqueta al publicar un borrador con `target_commitish` igual a un SHA, la descarga de assets de un borrador con `Accept: application/octet-stream`, los permisos reales del `GITHUB_TOKEN` del repositorio, ni el formato exacto de las respuestas más allá de los campos documentados que se usan.
* La reproducibilidad **byte a byte** del `app.zip` entre construcciones no se afirma ni se prueba.

## 9. Limitaciones y observaciones (ninguna bloqueante para esta subfase)

1. Hasta que alguien ejecute el workflow con `publicar`, **no hay releases y L-2 sigue vigente**: los reportes cuyo código no sea recuperable siguen en `parcial`.
2. **Estados parciales:** si falla la verificación del borrador, queda un borrador sin etiqueta (inofensivo, pero hay que borrarlo a mano para repetir: la comprobación de etiqueta libre lo detecta y falla). Si la verificación falla **después** de publicar (p. ej. una etiqueta creada entre la comprobación y la publicación), la release ya es pública y el workflow termina en rojo; se corrige a mano. El workflow no borra nada por diseño.
3. Entre la comprobación de etiqueta libre y la publicación hay una ventana mínima (carrera); la concurrencia del workflow la reduce a quien cree etiquetas por fuera, y la verificación posterior la detectaría.
4. La política de CI (T-11) es conservadora: puede rechazar una publicación legítima mientras Pages sigue desplegando.
5. La etiqueta identifica el código; la comparación de 3A-4 no consulta releases (no se implementa; sería otra subfase).
6. Las pruebas de la estructura del workflow son de texto/YAML y `bash -n`: no sustituyen una ejecución real.

## 10. Exclusiones respetadas

Sin 3A-6/3B; sin interfaz ni motor de reglas; sin tocar contratos ni workflows existentes ni `build_site.py`; sin publicar release ni crear etiquetas; sin eliminar ni debilitar pruebas.
