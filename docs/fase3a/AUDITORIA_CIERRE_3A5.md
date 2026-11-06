# Auditoría de cierre · Subfase 3A-5 (releases `app-vX.Y.Z`)

Documento de revisión independiente de `IMPLEMENTACION_3A5_RELEASES.md`: permite revisar el trabajo sin reconstruir la conversación.

## 1. Integración previa de 3A-4 (resumen verificado)

| Elemento | Resultado |
|---|---|
| PR #20 antes de fusionar | abierto, base `main`, HEAD `2d6725f8e06a4a2e5fd4063c2770fb4368afc130`, CI run 48 en success, 0 revisiones, 0 comentarios de revisión (solo la plantilla de CodeRabbit), `mergeable_state: clean`, sin cambios locales ajenos, diff de 13 archivos revisado |
| Condiciones de aceptación | dictamen B, R-09 (original PARCIAL + vigente CUMPLIDO), R-02/R-13/I-06 NO VERIFICABLES, D-08 a D-12 pendientes, integridad no criptográfica, B/C con PPTX sustituido y sin afirmar narrativa real: **todas verificadas en el contenido de la rama** |
| Fusión | método `merge` protegido por el SHA revisado; commit de fusión `8d1bbc7f7dd6778c78ba95c0ead424654bf4f57d`; PR `MERGED` a las 01:08:32 UTC del 6 de noviembre de 2026; `main` contiene `provenance_compare.py`, `test_procedencia_regenerador.py` y la auditoría |
| CI posterior | run 49 `Pruebas` sobre `8d1bbc7`: success |
| GitHub Pages | run 17: `build` y `deploy` en success y despliegue `github-pages` asociado a `8d1bbc7`. **No se verificó el sitio publicado**: el entorno no alcanza `github.io` (proxy). El contenido en vivo es NO VERIFICADO |

## 2. Reconstrucción del alcance de 3A-5

* **Fuente única del alcance:** spec 3A §10 («`release.yml` etiqueta `app-vX.Y.Z` y publica su `app.zip` con su SHA-256 (V-02, AC-28)»), §12.1, AC-28, L-2, H-6 y Fase 1 (§5.3, RQ-12, V-02, A-5, DD-16).
* **Autorización:** la spec y DD-16 dejaban A-5 «sin autorización / por ejecutar al ordenar la Fase 3A». La instrucción de ejecutar 3A-5 se interpretó como esa autorización, **limitada al workflow y a su verificación**; **no** se interpretó como orden de publicar una release.
* **Vacíos de la especificación** (resueltos solo por el lado restrictivo y registrados como T-1 a T-10 en la implementación): disparo, validación, nombre de los assets, qué ocurre si la etiqueta existe, permisos.

## 3. Matriz de cumplimiento

Estados: CUMPLIDO · PARCIALMENTE CUMPLIDO · INCUMPLIDO · NO VERIFICABLE · NO APLICA.

| ID | Requisito (fuente) | Evidencia | Prueba | Estado | Observaciones |
|---|---|---|---|---|---|
| 5-01 | Existe `.github/workflows/release.yml` (§10, 3A-5) | archivo nuevo en el PR | `test_el_workflow_cumple_todas_las_garantias` | CUMPLIDO | |
| 5-02 | Etiqueta `app-vX.Y.Z` con `X.Y.Z = APP_VERSION` (§10) | `release_app.etiqueta()` y `version_del_repositorio()` | `test_la_version_del_repositorio_es_la_de_la_aplicacion`, `test_etiqueta_valida`, 15 inválidas | CUMPLIDO | SemVer estricto |
| 5-03 | Publica `app.zip` con su SHA-256 (§10; AC-28) | el workflow crea la release con `app.zip` y `app.zip.sha256` | `test_preparar_escribe_los_tres_archivos…`, `test_el_archivo_sha256_es_verificable_con_sha256sum`; estructura del workflow | PARCIALMENTE CUMPLIDO | La lógica está implementada y probada; **la publicación real no se ejecutó** (ver 5-04) |
| 5-04 | V-02: ejecución real del workflow y asset descargable con SHA coincidente (Fase 1) | el paso de verificación existe en el workflow | ninguna ejecutable sin publicar | NO VERIFICABLE | Requiere publicar una release; no autorizado aquí. AC-28 no queda demostrado |
| 5-05 | El código etiquetado es el que generó el reporte (§5.3 Fase 1, A-5) | `validar_zip` exige `_build_info.commit == $GITHUB_SHA` sin `+dirty`, y `APP_VERSION` empaquetado igual | `test_zip_invalido[...]` (11 casos), `test_el_app_zip_real_…` | CUMPLIDO | Con `app.zip` real y con zips sintéticos |
| 5-06 | Una versión publicada no se reescribe | comprobación de etiqueta existente; sin `--clobber`/borrado/forzado | `test_mutaciones_deliberadas_del_workflow_son_detectadas`, `problemas_workflow` | CUMPLIDO | La comprobación se prueba por estructura, no ejecutando `git ls-remote` |
| 5-07 | No publicar por iniciativa propia (H-6, DD-13/DD-16) | disparo solo manual, `publicar=false` por omisión, solo desde `main` | `test_el_workflow_no_se_dispara_con_push_ni_pr_ni_programacion`, mutaciones | CUMPLIDO | |
| 5-08 | Permisos mínimos / sin secretos propios | `contents: read` global, `write` solo en el job, solo `github.token` | mutaciones de permisos y de `secrets.` | CUMPLIDO | |
| 5-09 | No cambiar contratos 3A-0 a 3A-4 ni `build_site.py` | diff: 3 archivos nuevos + 1 de docs + 1 de pruebas | `archivos_protegidos --check`, `capture_baseline --check` 8/8, y `git diff origin/main` sin líneas en `service.py`, `store.py`, `build_site.py` ni los tres workflows existentes (comprobación manual, no una prueba automática); `test_release_yml_no_se_empaqueta_en_el_sitio` cubre solo que `release.yml` no entra en `PACKAGED` | CUMPLIDO | |
| 5-10 | Reportes sin código recuperable siguen en `parcial` mientras no exista release (§10, L-2) | L-2 actualizado: sigue vigente hasta que se ejecute el workflow | — | NO APLICA | Es una consecuencia de 3A-4, no un cambio de 3A-5; documentado |
| 5-11 | T-16: `app.zip` con versión y SHA estampados (Fase 1) | cubierto desde 3A-1 | `test_build_site.py`, `test_build_dirty.py` | CUMPLIDO | heredado, sin cambios |

## 4. Pruebas y resultados

| Comando | Total | Aprobadas | Fallidas | Omitidas |
|---|---|---|---|---|
| `python -m pytest tests/unit/test_release_app.py` | 60 | 60 | 0 | 0 |
| Suite completa local, `REPORT_PYODIDE_REQUIRED=1`, Pyodide activo | 1101 | **1066** | **0** | **35** |

* Base anterior (`main` con 3A-4): 1006 / 0 / 35. Diferencia: +60, todas de `test_release_app.py`.
* Las 35 omitidas son las mismas de `tests/golden` (faltan plantillas, Excel o fixtures reales, o LibreOffice); ninguna fuera de esa carpeta. No hay omisiones nuevas.
* `capture_baseline --check`: 8 de 8 idéntico. `archivos_protegidos --check`: sin cambios. `service.py`, `store.py`, `build_site.py` y los tres workflows existentes: sin diferencias respecto a `main`.
* Pyodide: no se tocó el núcleo ni ningún contrato validado allí; el paso obligatorio de CI sigue ejecutándose sin modificaciones.
* **Mutaciones deliberadas** (copia fuera del repositorio): 11 del workflow (todas detectadas) y 10 del script (todas detectadas tras afinar una prueba: `testzip` desactivado sobrevivía porque la corrupción caía en un archivo que de todas formas se leía).
* **Defecto propio hallado por las pruebas y corregido:** `$` en las expresiones regulares aceptaba un salto de línea final (`"1.0.0\n"`, o un SHA con `\n`); ahora se usa `fullmatch`. Relevante porque la etiqueta se escribe en `$GITHUB_OUTPUT`.

## 5. Lo que el CI no demuestra

La ejecución del workflow en GitHub (permisos reales del repositorio, `gh release create`, `upload-artifact`, descarga del asset). Un CI verde del PR demuestra que la lógica y la estructura son correctas, no que una release se publique.

## 6. Riesgos residuales

1. AC-28/V-02 sin cerrar hasta una ejecución real con `publicar` (decisión del usuario; publica algo hacia fuera).
2. El workflow no exige CI verde del commit antes de publicar.
3. Si `APP_VERSION` no cambia, el workflow falla al repetir la etiqueta (intencionado, pero puede sorprender).
4. La reproducibilidad byte a byte del `app.zip` entre construcciones no se afirma.
5. Estado de GitHub Pages en vivo no verificado desde este entorno.

## 7. Exclusiones respetadas

Sin 3A-6/3B; sin publicar release; sin tocar contratos, archivos protegidos ni workflows existentes; sin eliminar ni debilitar pruebas.

## 8. Dictamen

**B. IMPLEMENTADA CON OBSERVACIONES.** Todo lo implementable y verificable sin publicar está cumplido y probado; AC-28/V-02 queda NO VERIFICABLE por requerir una publicación real, que no se ejecutó.
