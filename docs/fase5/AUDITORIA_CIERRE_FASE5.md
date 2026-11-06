# Fase 5 · Auditoría de cierre

| | |
|---|---|
| Alcance auditado | `docs/fase5/*` y el código de la rama `claude/fase5-calidad-qa` (PR #24) |
| Método | Verificación del estado real del repositorio y de GitHub, pruebas ejecutadas de nuevo sobre el código final, inspección visual de los decks, mutación de las pruebas de AC-14 y revisión de cada afirmación documental contra el código. No reescribe ninguna auditoría anterior |
| Base | `main` en `47dc3af47e9425cebd135e9aec0b4a2f783225ff` (PR #22 y #23 fusionados) |

## 1. Matriz de criterios de la Fase 5

| ID | Requisito | Estado | Evidencia | Pendiente |
|---|---|---|---|---|
| RQ-13 | QA estructural del PPTX exportado | **PARCIALMENTE CUMPLIDO** | `qa/pptx_export.py` (39 pruebas) + `qa/cifras.py` (55); 0 hallazgos en los 4 decks de referencia | ver AC-14 |
| **AC-14** | detección de token, duplicado, fuente mínima, unidad sin denominador, fórmula alterada, cifra no trazada, con 0 falsos positivos en decks de referencia | **PARCIALMENTE CUMPLIDO** | todos los defectos de T-11 se detectan con su `id`; 9 mutaciones de 9 detectadas; 0 falsos positivos salvo una observación real en GLP-1 (`AC14_CIFRAS_FORMULAS.md` §4, §6) | el «100 %» no es demostrable para cualquier defecto posible; una cifra alterada puede coincidir por azar con otro valor del motor; la observación de GLP-1 exige cambiar la narrativa (A-3) |
| RQ-14 / **AC-16** | QA visual con render real: PNG por diapositiva e informe con datos sintéticos | **CUMPLIDO** | `qa/visual.py`, `tools/visual_qa.py`: 14 pruebas con LibreOffice, 6 defectos inyectados detectados, 0 falsos positivos en 4 decks reales + 4 con anexo; PNG por diapositiva, `informe.json` y `informe.html` | corre solo en local (sin LibreOffice, `omitida`, nunca «aprobada») |
| RQ-15 / **AC-15** | los límites del QA se declaran; nunca se llama «visual» a lo estructural | **CUMPLIDO** | banner «Revisión estructural. La revisión visual requiere render» verificado en el recorrido real con motor real (`test_descarga_pptx`, aserción añadida) y `ETIQUETA` probada | — |
| RQ-19 | anexo de calidad de datos | **PARCIALMENTE CUMPLIDO** | panel, `anexo_calidad.json` y **diapositiva final** (`deck/anexo.py`, 12 pruebas, 4 plantillas con QA estructural y visual) | la diapositiva es opt-in (D5-11, decisión del usuario); el resumen del anexo no entra en el manifiesto (L-8) |
| AC-21 | con los flags apagados, la salida es idéntica a la línea base | **CUMPLIDO** | `capture_baseline --check`: 8 de 8 idéntico (motor y deck) | — |
| 3.5 | compatibilidad de libros y plantillas | **CUMPLIDO** | 30 pruebas: columnas extra o en otro orden y hojas en otro orden no cambian el resultado del motor; hojas o columnas ausentes y plantillas incompatibles dan mensajes claros | plantillas anteriores: **NO VERIFICABLE** (solo existe la versión 1) |
| 3.6 | bug de descarga `data.htm` | **PARCIALMENTE CUMPLIDO** | descarga endurecida; 21 casos en Chromium real, incluidos archivos reales de cada formato | causa raíz **no reproducida ni demostrada**; Firefox, Safari y WebViews no probados (`DESCARGA_DATA_HTM.md`) |
| 3.7 / **AC-28** | publicación real y GitHub Pages | **NO VERIFICABLE** (NO DEMOSTRADO) | configuración verificada; despliegue de `47dc3af` en success (run 20, 4.º intento); procedimiento exacto preparado (`PUBLICACION_AC28.md`) | el entorno no alcanza `github.io` (403 del proxy); requiere fusionar el #24, publicar y verificar desde un navegador externo |
| AC-11 | estados de reproducibilidad «se muestran» | **FUERA DEL ALCANCE DE FASE 5** (NO CUMPLIDO como criterio de la Fase 3) | `AC11_AC12.md`: diferido a una «fase de interfaz posterior» sin numerar | definir esa fase |
| AC-12 | reportes previos como `no_reproducible (legado)` en pantalla | **FUERA DEL ALCANCE DE FASE 5** (NO CUMPLIDO) | ídem | ídem |

## 2. Defectos hallados y corregidos durante la fase

| ID | Severidad | Defecto | Corrección |
|---|---|---|---|
| F5-1 | ALTO | el panel de la Fase 4 rotulaba los montos «MXN»: unidad inventada | `unidad: "moneda"` + nota; prueba que lo impide |
| F5-2 | MEDIO | `PPTX_DIAPOSITIVA_VACIA` nunca saltaba | se recorren todas las diapositivas |
| F5-3 | MEDIO | un paquete con relación rota lanzaba una excepción técnica | cualquier excepción es un hallazgo `PPTX_ZIP` |
| F5-4 | MEDIO | la revisión visual lanzaba `BadZipFile` con un archivo no PPTX | resultado `error` controlado |
| F5-5 | MEDIO | umbral de letra fijo de 9 pt: 319 falsos positivos | calibrado con la plantilla |
| F5-6 | BAJO | gráfica vacía heredada de la plantilla marcada como error | se compara contra la plantilla |
| F5-7 | MEDIO | contraste: un borde rojo dentro de la caja hacía ilegible texto blanco sobre azul | texto = píxel de mayor contraste |
| F5-8 | ALTO | extensiones de 2 a 5 letras: el historial `.sqlite` se habría llamado `historial.sqlite.bin` | 2 a 6 letras |
| F5-9 | MEDIO | **AC-14:** al calibrar, el detector marcaba falsos positivos (dosis y códigos en nombres de producto, rangos de edad, años con coma, tablas con bloques apilados, filas de variación, porcentajes con signo) y una derivación demasiado permisiva dejaba pasar un porcentaje alterado | reglas de exclusión, bloques de tabla y derivación acotada a la misma celda/párrafo |
| F5-10 | BAJO | mis pruebas: variante de columnas invertidas corrupta (sin formato de fecha); una prueba con aserción vacía (`or True`) | reconstruida / eliminada |

Observación real (no defecto del detector): GLP-1, «Mounjaro (74 %, $9.20 M)…» no declara su base (L-9).

## 3. Pruebas (código final)

| Prueba | Resultado |
|---|---|
| **Suite completa local**, Pyodide obligatorio (`REPORT_PYODIDE_REQUIRED=1`, `REPORT_PYODIDE_WORK`, `REPORT_PYODIDE_DIR`), navegador y LibreOffice | **1500 aprobadas, 0 fallidas, 35 omitidas** (40 min 59 s). Por carpeta: unit 1382, regresión 90, e2e 28, golden 35 omitidas. Las 35 omitidas son todas de `tests/golden` (faltan plantilla Q1 y Excel Q3 reales); 0 fuera de esa carpeta. Referencia anterior (PR #24 en `c544478`): 1432 → +68 |
| T-11 `test_qa_pptx_export.py` / AC-14 `test_qa_cifras.py` | 39 / 55 aprobadas (la de cifras incluye los 4 decks reales de referencia) |
| T-12 `test_qa_visual.py` | 14 aprobadas con LibreOffice |
| Anexo `test_calidad.py` / `test_anexo_pptx.py` | 35 / 12 aprobadas |
| Compatibilidad `test_compatibilidad.py` | 30 aprobadas |
| Descarga `tests/e2e/test_descarga_regresion.py` | 21 aprobadas en Chromium real (incluye archivos reales de cada formato) |
| Panel y anexo en navegador con motor real (Pyodide) | 4 aprobadas |
| Recorrido real de punta a punta (`test_descarga_pptx`, con AC-15) | 2 aprobadas (se repitió tras añadir la aserción de AC-15) |
| `test_hash_pyodide` | aprobada |
| Mutación de `cifras.py` | 9 de 9 detectadas |
| `archivos_protegidos --check` / `capture_baseline --check` | sin cambios / 8 de 8 idéntico |

**Qué corre en CI** (`tests.yml`): `tests/unit`, `tests/regression` y solo `test_hash_pyodide`. Quedan **fuera de CI y se ejecutaron localmente**: las pruebas de navegador (Playwright), T-12 y las verificaciones con LibreOffice, y las que usan las plantillas reales (no versionadas); todas se omiten con motivo donde falta el software o el archivo.

**Qué NO validan:** el aspecto en PowerPoint, la causa original de `data.htm`, datos de producción, Firefox/Safari/WebViews, el significado de una cifra, ni el sitio publicado.

## 4. Regresiones y archivos protegidos

* Modificados con autorización documentada en `tests/regression/protegidos.json` (motivos anteriores conservados): `build.py`, `service.py`, `bridge.py`, `app.py`, `index.html`.
* Sin modificación: `build_site.py`, los cuatro workflows (incluido `pages.yml`), contratos, `reglas.json`, `definiciones.json`, narrativa, deck, validator, líneas base, `engine_version.json`, `hash_resultado.json`, procedencia.
* `hash_resultado` y `ENGINE_VERSION` no cambian; los decks de la línea base son idénticos (8 de 8): con el anexo apagado `generate` pasa `anexo=None` y el PPTX no cambia.
* No se eliminó ni se debilitó ninguna prueba: se ampliaron `test_escenarios.py`, `escenarios_panel.mjs`, `test_escenarios_panel.py`, `test_descarga_pptx.py` (aserción de AC-15) y `test_calidad.py` (adaptada a la nueva firma de `_escribir_anexo`, con la misma cobertura).
* Garantías verificadas: ninguna fórmula aprobada cambió; ventas y GA4 no se mezclan (el ticket se contrasta solo con Pedidos; prueba específica); no se inventan monedas ni unidades (prueba específica); los eventos no se convierten en carritos únicos; los valores superiores a 100 % no se tocan; los supuestos se rotulan.

## 5. Dictamen

**APROBADO CON OBSERVACIONES** para revisión. Esto **no es** autorización de fusión.

La implementación autorizada está completa y validada (1500 pruebas, 0 fallidas; QA estructural, de cifras y visual; anexo en panel, JSON y diapositiva; descarga endurecida; compatibilidad). Quedan observaciones que ninguna acción técnica dentro de esta fase puede cerrar:

1. **AC-28 / publicación real** — requiere fusionar el PR #24, publicar y verificar desde un navegador externo (`PUBLICACION_AC28.md`).
2. **AC-14 parcial** — el «100 %» no es demostrable en general; la observación de GLP-1 requiere A-3.
3. **Decisiones del usuario** (resueltas el 2026-11-06 en `CIERRE_FINAL_FASE5.md` §2): anexo desactivado por omisión (D5-11), sin resumen del anexo en el manifiesto (L-8), AC-11/AC-12 formalizados como pendientes posteriores sin implementar, `pages.yml` sin cambios (D5-12: necesidad no demostrada) y narrativa GLP-1 intacta (A-3 posterior). Este documento conserva el dictamen de esa fecha; el cierre definitivo está en `CIERRE_FINAL_FASE5.md`.
4. **`data.htm`** — causa no demostrada; navegadores adicionales sin probar.

**Condiciones para poder fusionar:** CI verde sobre el SHA exacto del HEAD, ausencia de conflictos con `main` y autorización expresa del usuario. **Condiciones para cerrar la fase:** publicar y verificar (AC-28), y resolver las decisiones del punto 3.
