# Fase 4 · Auditoría de cierre

| | |
|---|---|
| Alcance auditado | `docs/fase4/IMPLEMENTACION_FASE4.md` (escenarios E1/E2 e IND-01) |
| Método | Una sola revisión integral contra: encargo, especificación de Fase 1 §8, criterios de aceptación, seguridad, arquitectura, pruebas, regresiones y documentación. No se añadieron requisitos durante la revisión |
| Base | `main` en `f15abfea707c1f0adcdedcc6d94ddcbc2024226e` (PR #21 fusionado) |
| No reescribe | Auditorías ni dictámenes de fases anteriores |

> **Nota posterior.** Las cifras de pruebas de §3 corresponden al SHA `7f641e7`. La auditoría independiente posterior encontró y corrigió defectos adicionales; su resultado, las pruebas actualizadas y el estado vigente están en §8 (añadida al final, sin reescribir lo anterior).

## 1. Criterios de aceptación de la Fase 4

| # | Criterio | Estado | Evidencia |
|---|---|---|---|
| 1 | E1 implementado y explicable | **VERIFICADO** | ficha con fórmula, variables tipificadas, efecto del supuesto, confiable/validar; `test_e1_*`; panel en navegador |
| 2 | E2 implementado y explicable | **VERIFICADO** | ídem; `test_e2_*` (solo GLP-1; AETOPS «No aplica: sin hoja `trafico`») |
| 3 | 25 % y 10 % como supuestos heredados no validados | **VERIFICADO** | `test_supuestos_son_los_heredados_y_estan_rotulados`, `test_e1_variables_separan…`, mutación «sin etiqueta» detectada |
| 4 | IND-01 integrado según su definición | **VERIFICADO** | `test_ind01_ejemplo_25_por_ciento_exacto`, `test_ind01_machote_glp1…` (12,48 % y 14,00 %) |
| 5 | Pedidos del sistema de ventas separados de compras GA4 | **VERIFICADO** | `test_ind01_ninguna_fuente_sustituye_ni_se_combina`, `test_ninguna_clave_calcula_…`, mutación «suma fuentes» detectada |
| 6 | Unidad de carritos identificada o declarada no verificable | **VERIFICADO** (declarada **NO VERIFICABLE** con los machotes) | `test_ind01_unidad_declarada_o_no`; el contrato no define `add_to_cart` |
| 7 | Relaciones > 100 % con advertencia y explicación | **VERIFICADO** | `test_ind01_mayor_100_…`, `test_anomalia_matematica_distinta_de_limitacion`, mutaciones «clamp» y «siempre anomalía» detectadas |
| 8 | Cálculos con trazabilidad | **VERIFICADO** | toda variable con `tipo` y `fuente` (`test_toda_variable_tiene_tipo_fuente…`); cifras idénticas a la narrativa |
| 9 | La interfaz permite interpretar los resultados | **VERIFICADO** | `tests/e2e/test_escenarios_panel.py` (navegador real, motor real) y captura revisada |
| 10 | Pruebas funcionales ejecutadas | **VERIFICADO** | §3 |
| 11 | Pruebas de regresión ejecutadas | **VERIFICADO** | §3 y §4 |
| 12 | Sin defectos bloqueantes | **VERIFICADO** | §2 (todos corregidos); §5 sin bloqueantes |
| 13 | Documentación completa | **VERIFICADO** | `IMPLEMENTACION_FASE4.md` y este documento |
| 14 | CI en verde sobre el SHA exacto del último commit | ver §6 | run de `Pruebas` del SHA definitivo |

## 2. Hallazgos de la revisión y su cierre

| ID | Hallazgo | Clasificación | Cierre |
|---|---|---|---|
| H4-1 | `service.py` importaba directamente `validator.normalizar`; la prueba T-14 (la IA no puede tocar el motor, el motor no depende de la IA) falló | **Bloqueante** (regresión de una garantía) | Se movió la lectura del contexto a `escenarios.construir_desde_libro`; el servicio solo importa `escenarios`. T-14 no se modificó y pasa |
| H4-2 | La primera corrida completa falló `test_hash_pyodide` | No es del código: faltaba `REPORT_PYODIDE_WORK` en mi comando local | Se repitió con la variable correcta: pasa. CI la fija |
| H4-3 | Mis dos primeras pruebas comparaban la cifra con el formato equivocado y una frase | Defecto de prueba propio | Corregidas con el mismo formateador que usa la presentación |
| H4-4 | La prueba estructural de claves rechazaba las advertencias «no_se_suman» y «equivalencia» | Defecto de prueba propio | Se exceptúan esas tres claves (son advertencias, no cálculos) |
| H4-5 | Mi script de mutación, interrumpido a propósito, dejó una mutación en el archivo | Operativo propio | Se restauró desde la copia y se comprobó byte a byte antes de seguir |

## 3. Pruebas

| Prueba | Resultado | Evidencia | SHA |
|---|---|---|---|
| `tests/unit/test_escenarios.py` | 45 pasan | fórmulas, supuestos, faltantes, fuentes, unidad, >100 %, prohibiciones, servicio | `7f641e7` |
| `tests/e2e/test_escenarios_panel.py` (navegador real + Pyodide) | 2 pasan | panel visible, sin errores de consola ni recursos caídos, flujo normal disponible | `7f641e7` |
| Mutaciones deliberadas (10) | 10 detectadas | clamp 100, r fijo, complemento, brecha invertida, sin etiqueta, faltante como cero, siempre anomalía, suma de fuentes, E2 sin condición, aviso con causa | código de `7f641e7` |
| `tests/regression` (90) | 90 pasan | línea base, hash, protegidos, versión del motor | código de `7f641e7` salvo `service.py` (reverificado, §4) |
| Pruebas de T-14, web, bridge y protegidos tras la corrección H4-1 | 91 pasan | con Pyodide | `7f641e7` |
| Suite completa local (Pyodide activo, obligatorio) | **1278 aprobadas, 0 fallidas, 35 omitidas** (16 min 35 s; las 35 omitidas son las de `tests/golden`, ya omitidas antes de la Fase 4; referencia anterior 1231/0/35: +47 = las pruebas nuevas) | salida local de la corrida (`REPORT_PYODIDE_REQUIRED=1`) | `7f641e7` |
| `archivos_protegidos --check` | sin cambios | ver §4 | `7f641e7` |
| `capture_baseline --check` | idéntico (motor y deck, escenarios de la línea base) | ver §4 | `7f641e7` |

## 4. Regresiones y protegidos

* Archivos de código modificados: `backend/app/web/service.py` y `frontend/index.html` (ambos ya estaban en el manifiesto de autorizados; se **reautorizaron conservando los motivos anteriores**) y `tests/regression/protegidos.json` (solo esas dos entradas).
* Archivos sin ninguna modificación: `build_site.py`, `pages.yml`, `pdf.yml`, `tests.yml`, `release.yml`, contratos, `reglas.json`, `definiciones.json`, narrativa, deck, validator, líneas base (`tests/regression/base`), `engine_version.json`, `hash_resultado.json`.
* `ENGINE_VERSION` no cambia; el manifiesto de procedencia y el `hash_resultado` no cambian (pruebas de regresión en verde).
* Las láminas actuales no cambian (línea base idéntica; A-3 no autorizada).

## 5. Observaciones y limitaciones

| Tipo | Elemento |
|---|---|
| **No bloqueante** | El panel es de lectura: no se persiste en el manifiesto ni en el historial; los porcentajes ya constan en `configuracion.escenarios` del manifiesto (3A-3), sin etiqueta textual (el contrato 3A está congelado) |
| **No bloqueante** | No hay anexo: el anexo de calidad de datos es de la Fase 5 (RQ-19) |
| **No bloqueante** | El texto de las láminas actuales no lleva la etiqueta «Supuesto heredado, no validado»: requiere A-3 |
| **No bloqueante** | La unidad de carritos solo se declara editando `unidad_carritos` en `reglas.json`; la interfaz la muestra pero no la captura |
| **No bloqueante** | Libros en formato antiguo (por bloques): IND-01 «no calculable» por diseño (requiere datos crudos); E1/E2 salen de los mismos bloques que la narrativa |
| **No bloqueante** | En el machote sintético, E2 equivale a ≈69 % de la venta: es la cifra del motor vigente sobre datos sintéticos; el panel la rotula como ilustrativa y supuesto heredado, y no la altera |
| **No verificable** | Unidad de `add_to_cart`; duplicados, atribución y ventana de maduración de GA4; si `negados` corresponde al periodo; definición de «carritos_abandonados» en la herramienta de analítica |
| **No verificado** | Comportamiento con datos reales de producción (solo machotes y fixtures sintéticos); las reglas siguen «no validadas con datos reales» |
| **Riesgo residual** | Si se cambiara `RULES` (25 %/10 %) sin actualizar `reglas.json`, el panel lo declara como `inconsistencia_configuracion` en vez de elegir en silencio |

Seguridad: toda cadena que llega al DOM se escapa con `esc()`; los números se formatean con `Number()`; no se añade ninguna llamada de red ni escritura; el servicio no importa el motor (T-14).

## 6. Dictamen

Pendiente del CI del SHA definitivo (se registra en el informe y en la descripción del PR). Con el CI en success, la Fase 4 queda **implementada y validada, con observaciones no bloqueantes**; la integración requiere autorización expresa.

---

## 8. Auditoría independiente posterior (antes de la fusión)

Revisión hecha sin apoyarse en los informes previos: reproducción de las cifras desde el libro con un cálculo que no usa el código del módulo, lectura crítica del código, pruebas con libros alterados y revisión de cada afirmación documental frente al código y al catálogo de definiciones.

### 8.1 Hallazgos y cierre

| ID | Severidad | Hallazgo | Evidencia | Cierre |
|---|---|---|---|---|
| A-03 | MEDIO | Textos «r = 25 % / c = 10 %» fijos en `pendientes_validacion` y en la comparación; si cambiara el valor aplicado, el texto contradiría al cálculo | `escenarios.py` (`construir`, `comparar`) | Derivados del valor aplicado; prueba con otros valores |
| A-04 | MEDIO | El estado global de IND-01 decía «calculable con limitación» aunque todos los resultados fueran «calculable» (unidad declarada y sin otras limitaciones) | reproducido con unidad `eventos` | Regla explícita (todos calculables → calculable); prueba y mutación |
| A-05 | MEDIO | Una celda vacía de `monto_negado` se suma como 0 (igual que la presentación) y el panel la rotulaba «observado» sin aviso | libro con la primera fila de `negados` vacía: E1 pasó de 1 923 284 a 1 695 529 sin advertencia | Se mantiene la misma cifra que la presentación (no se altera la narrativa protegida) y se **advierte** en el panel; prueba y mutación |
| A-06 | BAJO | Campo `en_presentacion` sin uso y no verificable (la narrativa conserva como máximo 5 recomendaciones) | grep: ningún consumidor | Eliminado; prueba de ausencia |
| A-07 | MEDIO | El panel decía que el contrato «NO define» qué cuenta `add_to_cart`, pero el catálogo aprobado lo clasifica como evento de analítica (sin validar) y deja la unidad de los carritos agregados sin declarar | `definiciones.json`: `evento`, `carritos_agregados` | Texto corregido en panel y documentación; prueba que lo ata al catálogo. El estado sigue **NO VERIFICABLE** |
| A-08 | MEDIO | El panel releía el libro completo en cada análisis: ≈ +4,3 s sobre 4,1 s del motor en el libro de ejemplo (2,4 MB) | medición directa | Lectura reutilizada por (archivo, tamaño, fecha, periodo); sigue habiendo un costo en la primera lectura (observación) |
| A-09 | BAJO | GLP-1 sin hoja `trafico` se declaraba «No aplica» en IND-01; en GLP-1 es un faltante | libro de ejemplo sin esa hoja | «No calculable» con `faltante` |
| A-10 | BAJO | Cobertura ausente: trimestres, libros sin hoja opcional, formato antiguo (en navegador), T-14 sobre el módulo nuevo, conservación del resultado original | revisión de pruebas | 13 pruebas unitarias (45 → 58) y 1 de navegador (2 → 3) añadidas |

### 8.2 Verificado de forma independiente
* **12,48 % y 14,00 %** reproducidos con `openpyxl` sin usar el código del módulo: 2 356 pedidos distintos de septiembre de 2026 (con y sin los criterios del motor, coinciden), 2 643 compras GA4 y 18 883 carritos ⇒ 12,4768 % y 13,9967 %; brecha 12,18 %.
* **E1/E2** coinciden con la cifra que imprime la recomendación de la presentación (mismo formateador).
* **Fuentes**: el único cálculo que combina las dos es la brecha F-03 informativa; ninguna estructura suma, promedia ni sustituye (prueba estructural de claves y 3 mutaciones).
* **T-14**: `service.py` no importa el motor; el módulo nuevo tampoco usa red, escritura, procesos ni IA.

### 8.3 Pruebas y estado vigente (código de `9e45c8c`)

| Prueba | Resultado |
|---|---|
| Suite completa local (Pyodide obligatorio, `REPORT_PYODIDE_WORK` y `REPORT_PYODIDE_DIR` fijados) | **1292 aprobadas, 0 fallidas, 35 omitidas** (17 min 15 s); las 35 son todas de `tests/golden` (0 fuera); referencia anterior 1278 |
| `tests/unit/test_escenarios.py` | 58 aprobadas |
| `tests/e2e/test_escenarios_panel.py` (navegador real + Pyodide: GLP-1 crudo, AETOPS crudo, formatos antiguos) | 3 aprobadas |
| Mutaciones deliberadas | 12 de 12 detectadas; las 12 producen código sintácticamente válido (no se detectan por romper la sintaxis) |
| `archivos_protegidos --check` | sin cambios |
| `capture_baseline --check` | idéntico (8 de 8) |
| CI del SHA definitivo | se registra en el PR (un commit de solo documentación no lo cambia de resultado) |
