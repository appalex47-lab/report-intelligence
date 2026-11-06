# Fase 3A-5 · Releases etiquetadas `app-vX.Y.Z` (decisión A-5)

| | |
|---|---|
| Fuentes oficiales | `ESPECIFICACION_FASE3A_PROCEDENCIA.md` §10 (3A-5), §12.1, AC-28, L-2, H-6 · `docs/fase1/ESPECIFICACION_FASE1_REPORT_INTELLIGENCE_FINAL.md` §5.3 (propuesta de etiquetar cada despliegue), RQ-12, T-16, V-02, AC-28, A-5 · `docs/fase1/implementacion/DECISIONES_DELEGADAS.md` DD-16 |
| Depende de | 3A-1 (`APP_VERSION` y SHA estampado en `app.zip`), 3A-3 (el manifiesto registra `version_codigo` = versión + SHA) y 3A-4 (el estado `parcial` por código no recuperable). **Ninguno de sus contratos cambia** |
| Estado | Implementada; PR independiente **sin fusionar**. **No se ha publicado ninguna release ni se ha ejecutado el workflow en GitHub** |
| Fuera de alcance | 3A-6/3B, interfaz, motor de reglas, publicar una release, modificar workflows existentes o `tools/build_site.py`, validar la ejecución real (V-02, ver §7) |

## 1. Qué se pidió y de dónde sale

La especificación define 3A-5 en una sola línea: *«`release.yml` etiqueta `app-vX.Y.Z` y publica su `app.zip` con su SHA-256 (V-02, AC-28)»*, con el archivo `.github/workflows/release.yml`. La propuesta original (Fase 1 §5.3) añade el motivo: reproducir con código anterior exige poder obtenerlo; sin release publicada el estado es `parcial`. DD-16 dejó la decisión «recomendada pero no ejecutada» hasta que se ordenara la Fase 3A; la autorización expresa de la subfase 3A-5 es la orden que faltaba. **La especificación no define** cómo se dispara, cómo se valida ni el nombre de los assets: esas son las decisiones técnicas de §4, tomadas en el sentido más restrictivo.

## 2. Qué se implementó

| Archivo | Tipo | Contenido |
|---|---|---|
| `.github/workflows/release.yml` | nuevo | Workflow solo manual (`workflow_dispatch`) con la entrada `publicar` (false por omisión). Construye el sitio, valida el paquete, comprueba que la etiqueta no exista, sube los archivos como artefacto y, solo con `publicar`, crea la etiqueta y la release y verifica el SHA-256 del asset descargado |
| `tools/release_app.py` | nuevo | Valida el `app.zip` y escribe `app.zip`, `app.zip.sha256` y `NOTAS.md`. Solo biblioteca estándar; no publica ni ejecuta git |
| `tests/unit/test_release_app.py` | nuevo | 60 pruebas (corren en CI): lógica, `app.zip` real de `build_site.py`, estructura de seguridad del workflow y mutaciones deliberadas |
| `ESPECIFICACION_FASE3A_PROCEDENCIA.md` | modificado | Seguimiento de estado (3A-5, AC-28, L-2, H-6, §12.1); sin cambiar requisitos |

No se modificó ningún archivo existente de código, de pruebas ni de workflows (`pages.yml`, `pdf.yml`, `tests.yml`) ni `tools/build_site.py`.

## 3. Reglas de validación (`tools/release_app.py`)

La etiqueta solo sirve para recuperar código si el zip publicado se compiló **de ese commit** y **con el árbol limpio**. Por eso, antes de escribir nada, se exige:

1. `APP_VERSION` del repositorio es SemVer estricto (`MAJOR.MINOR.PATCH`, sin `v`, sin ceros a la izquierda, sin sufijos): etiqueta `app-v` + versión.
2. El commit pedido (`$GITHUB_SHA`) tiene 40 hexadecimales en minúsculas (se usa `fullmatch`: una prueba reveló que `$` aceptaría un salto de línea final).
3. El zip existe, es un zip válido, pasa `testzip()` y no excede el tamaño esperado.
4. Contiene `backend/app/_build_info.json` con esquema `build_info/1` y `commit` **exactamente igual** al pedido: un `+dirty` o `desconocido` se rechaza (no identifican un código recuperable).
5. Contiene `backend/app/version.py` y su `APP_VERSION` coincide con el del repositorio.
6. La carpeta de salida es nueva o está vacía (nunca se sobrescribe).

El SHA-256 se calcula sobre los mismos bytes que se copian a `app.zip`, y `app.zip.sha256` usa el formato de `sha256sum` (`<sha>  app.zip`), verificable con `sha256sum -c`.

## 4. Decisiones técnicas

| ID | Decisión | Motivo |
|---|---|---|
| T-1 | Disparo **solo manual** (`workflow_dispatch`); ningún push ni PR publica | Publicar es una acción hacia fuera (DD-13/DD-16); un push no debe crear etiquetas |
| T-2 | Entrada `publicar` con valor **false** por omisión: sin marcarla es un ensayo (construye, valida y deja el artefacto) | Permite probar el workflow sin publicar |
| T-3 | Solo desde `refs/heads/main` | La etiqueta debe apuntar a un commit ya revisado |
| T-4 | Permisos globales `contents: read`; el job pide `contents: write` | Mínimo privilegio; sin secretos propios (solo `github.token`) |
| T-5 | La etiqueta no debe existir; nunca se reescribe (sin `--clobber`, sin borrar ni forzar) | Una versión publicada es inmutable; si ya existe hay que subir `APP_VERSION` (política SemVer §4.1) |
| T-6 | `--target "$GITHUB_SHA"` | La etiqueta apunta exactamente al commit compilado |
| T-7 | Tras publicar se descarga el asset y se compara su SHA-256 con el calculado | Evidencia de que lo publicado es lo validado (V-02) |
| T-8 | Script auxiliar `tools/release_app.py` en lugar de lógica en línea en el YAML | La spec lista solo `release.yml`, pero la validación solo es probable en CI si vive en Python. Es aditivo y no está protegido |
| T-9 | Mismas versiones de acciones que `pages.yml` (`checkout@v4`, `setup-python@v5`); `upload-artifact@v4` | Consistencia; se prueba que no se usen referencias flotantes |
| T-10 | **No se añade `release.yml` a `build_site.PACKAGED`** | Cambiaría el cálculo de `+dirty` y `tools/build_site.py` es protegido; la spec no lo pide |

## 5. Contratos utilizados (no modificados)

`APP_VERSION` (`version.py`, 3A-1) · `_build_info.json` esquema `build_info/1` dentro de `app.zip` (3A-1) · `tools/build_site.py` tal como existe · el SHA que registra `version_codigo.commit` en el manifiesto (3A-3), que es el que la etiqueta apunta.

## 6. Pruebas (`tests/unit/test_release_app.py`)

| Grupo | Qué demuestra |
|---|---|
| Versión y etiqueta | la versión leída es la de la aplicación; 15 versiones inválidas (vacío, `v1.0.0`, `01.0.0`, sufijos, espacios, salto de línea, inyección) se rechazan |
| `validar_zip` | acepta el zip correcto; rechaza commit distinto, `+dirty`, `desconocido`, sin `_build_info`/`version.py`, esquema distinto, versión distinta o ilegible, commit pedido corto/mayúsculas/vacío/con salto de línea, zip inexistente, no-zip, corrupto en un archivo que solo `testzip` detecta, `_build_info` no JSON y archivos desmesurados |
| `preparar` | escribe los tres archivos; el SHA es el del zip; `sha256sum -c` lo valida; no escribe nada si el zip no vale; no sobrescribe; la CLI devuelve 0/1 y nada en stdout al fallar |
| `app.zip` real | se arma con `build_site.py`, se valida con el commit sellado y se rechaza con otro commit |
| Workflow | una función `problemas_workflow` comprueba disparo manual, ensayo por omisión, permisos, guarda de rama, versiones fijadas, `--target`, orden construir → validar → comprobar etiqueta → publicar, ausencia de `--clobber`/borrado/forzado/secretos y verificación del SHA descargado |
| Mutaciones | 11 mutaciones del workflow (añadir `push`, `default: true`, permisos globales de escritura, quitar la guarda, publicar sin condición, `--target main`, `--clobber`, acción flotante, quitar la verificación, cancelar en curso, usar un secreto) se detectan |

Además, 10 mutaciones del script, ejecutadas en una copia fuera del repositorio, las detecta la suite (una —`testzip` desactivado— sobrevivió al principio y obligó a afinar la prueba de corrupción).

## 7. Qué NO se verificó (requisitos no verificables)

* **V-02 / AC-28 — ejecución real del workflow.** Requiere publicar una release (acción hacia fuera) y no se ha hecho: no existe ninguna etiqueta `app-v*`. Lo probado es la lógica del script y la estructura del workflow, **no** que GitHub lo ejecute como se espera (p. ej. permisos del repositorio para crear releases, comportamiento de `gh release create` o de `upload-artifact`). Es la única forma de cerrar AC-28.
* El `app.zip` de CI depende de `build_site.py` con ruedas de PyPI; la prueba usa ruedas de relleno. La reproducibilidad **byte a byte** del zip entre dos construcciones **no** se afirma ni se prueba: la release publica *ese* zip y su hash, que es lo que importa.
* El workflow no comprueba que el CI del commit esté en verde antes de publicar (la guarda es «solo desde `main`»).

## 8. Limitaciones y riesgos residuales

1. Hasta que alguien ejecute el workflow con `publicar`, **no hay releases y L-2 sigue vigente**: los reportes cuyo código no sea recuperable siguen en `parcial`.
2. Una release se crea desde el commit de `main` en el momento de ejecutar: si `APP_VERSION` no se sube, el workflow falla al intentar repetir la etiqueta (diseño intencionado).
3. La etiqueta identifica el código; la comparación de 3A-4 no consulta releases (no se implementa; sería otra subfase).
4. `tools/release_app.py` no valida que el commit pertenezca a `main`; eso lo hace la guarda del workflow.
5. Las pruebas de la estructura del workflow son de texto/YAML: no sustituyen una ejecución real.

## 9. Exclusiones respetadas

Sin 3A-6 ni 3B; sin cambios en la interfaz, el motor, el historial, los contratos de 3A-0 a 3A-4, `build_site.py`, `pages.yml`, `pdf.yml` ni `tests.yml`; sin publicar ninguna release; sin tocar archivos protegidos.
