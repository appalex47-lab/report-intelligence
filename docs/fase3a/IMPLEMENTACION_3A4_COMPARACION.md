# Fase 3A-4 · Comparación por regeneración y estados de reproducibilidad

| | |
|---|---|
| Especificación | `ESPECIFICACION_FASE3A_PROCEDENCIA.md` §3 (3.1 a 3.5), §8.4, PR-5/9/10/11, AC-11/AC-12, T-08 |
| Depende de | 3A-1 (versiones), 3A-2 (`hash_resultado`), 3A-3 (manifiesto, tabla `procedencia`, verificación). **Sus contratos no cambian** |
| Estado | Implementada; PR independiente **sin fusionar** |
| Fuera de alcance | Interfaz, botones, motor de reglas, `release.yml` (3A-5), Fase 3B, persistencia nueva de resultados de comparación |

## 1. Auditoría previa

* Estado inicial: `main` en `e4b2f65` (PR #19, 3A-3 integrada); CI posterior (run 42) y Pages (run 16) en success; árbol limpio.
* La especificación define los estados completamente en §3.1 (C1 a C7), §3.2 (orden y casos límite), §3.3 (D-B) y §3.5 (tres igualdades). **No se encontró una ambigüedad que impida implementar.** Hay cuatro puntos que la especificación no fija con precisión; se resolvieron siempre por la lectura más conservadora (nunca hacia «exacta») y quedan marcados abajo como **I-1 a I-4** para que se revisen.
* Discrepancia documentada entre especificación y código: la especificación (§8.1) coloca `comparar(...)` en `provenance.py` y **no** crea un módulo de orquestación; la regeneración real exige E/S (leer fuentes y plantilla, ejecutar el motor), que `provenance.py` no puede tener (es puro). Se mantuvo `comparar` puro en `provenance.py` y la E/S en un módulo nuevo `provenance_compare.py`, como 3A-3 hizo con captura y verificación.

## 2. Qué significa cada estado

Se separan **tres conceptos** que no deben mezclarse (revisión del PR #20):

| Concepto | Campo | Valores | Qué responde |
|---|---|---|---|
| A. **Reproducibilidad** | `estado` | `exacta`, `parcial`, `no_reproducible` (los de la spec) o `null` (**sin clasificar**: no es un cuarto estado) | ¿Qué reproducibilidad tiene el reporte según §3.2? |
| B. **Evaluación** | `evaluacion.estado` | `completada` (hay estado), `no_ejecutada` (falta una regeneración que no se pidió o no se ejecutó), `fallida` (la regeneración falló o hubo un error interno) | ¿Llegó la comparación a su fin? |
| C. **Regeneración** | `regeneracion.estado` | `no_solicitada`, `no_ejecutada`, `completada`, `fallida` | ¿Qué pasó técnicamente con la regeneración? |

Reglas de coherencia (las impone `validar_comparacion`): `estado = null` ⇔ `evaluacion.estado ≠ completada`; `exacta` exige C1–C7 en `pasa`, regeneración `completada` y `hash_regenerado == hash_registrado`, sin diferencias; `fallida` exige un error; una regeneración `no_solicitada` no puede traer hash.

| Reproducibilidad | Condición (spec §3.2, en este orden; gana la primera) | Evidencia obligatoria |
|---|---|---|
| `no_reproducible` | C1 falla (sin manifiesto, legado, esquema desconocido, manifiesto inválido) **o** C2 falla (manifiesto alterado) **o** C3b falla (una fuente aportada difiere) | Resultado de `provenance_verify.verificar` y fuentes aportadas |
| `parcial` | C1 y C2 pasan, C3b no falla y se cumple al menos una: C3a falta, C4, C5 o C6 fallan, o no hay registro contra el cual verificar C2 (D-B); **o** C1 a C6 pasan y C7 falla (anomalía de determinismo) | Estado actual (plantilla, versiones, configuración) |
| `exacta` | C1 a C6 pasan **y** C7 pasa: existe una regeneración real completada y su `hash_resultado` es igual al registrado | Regeneración completada |
| `null` (sin clasificar) | C1 a C6 pasan y no hay regeneración completada: **la spec no define estado para este caso** (PR-11 solo prohíbe `exacta`) | — |

Cómo queda cada escenario de la revisión (todos con prueba):

| Escenario | `estado` | `evaluacion` | `regeneracion` |
|---|---|---|---|
| C1–C6 pasan, no se solicita regeneración | `null` | `no_ejecutada` | `no_solicitada` |
| C1–C6 pasan, se solicita y termina con el mismo hash | `exacta` | `completada` | `completada` |
| Termina con hash diferente | `parcial` (anomalía de determinismo) | `completada` | `completada` |
| Falla, devuelve un resultado incompleto o vacío | `null` | `fallida` | `fallida` (con `error`) |
| Se solicita pero C1–C6 no pasan | el que corresponda por §3.2 | `completada` | `no_ejecutada` |
| Error interno de la comparación | `null` | `fallida` | `no_ejecutada` (con `error`) |

Una regeneración fallida **nunca** se trata como éxito parcial ni se convierte en `parcial`: no hay evidencia para clasificar. (Nota: `provenance_verify.verificar`, de 3A-3, conserva su propio valor `no_evaluada` dentro de `reproducibilidad.estado`; es el resultado de la verificación de integridad y no el de esta comparación.)

* **Qué se compara:** C1/C2 integridad del registro (y de su copia); C3a/C3b fuentes por SHA-256 (el contenido manda, no el nombre); C4 plantilla (`id` + SHA-256); C5 `version_codigo` (app + commit); C6 `version_motor`, `version_definiciones`, `version_reglas` y `configuracion` completas; C7 `hash_resultado` regenerado. `entorno` solo se informa como nota.
* **Ausencia de evidencia:** cualquier componente actual no aportado (`None`) es una diferencia «sin evidencia actual» y nunca coincidencia. Un commit `desconocido` o `+dirty`, aunque sea igual en ambos lados, **no demuestra** que sea el mismo código (C5 falla).
* **Versiones incompatibles:** esquema de procedencia desconocido → C1 falla (`no_reproducible`); versión de motor/definiciones/reglas/código distinta → C5/C6 (`parcial`); un `hash_resultado.contrato` distinto del actual hace que el manifiesto sea inválido en la validación de 3A-3 (esquema cerrado) → `no_reproducible`.
* **Registro de diferencias:** lista determinista de `{componente, registrado, actual, motivo}` hoja por hoja (valores largos recortados a 200 caracteres), más `notas` (entorno), `alertas` y `avisos`.

### Resolución de las interpretaciones (revisión del PR #20)

| ID | Resolución | Fundamento |
|---|---|---|
| **I-1** | **Confirmada**: no es una interpretación, es la lectura literal de la spec. §3.1 C2 compara «sha256(bytes del manifiesto)» con `manifiesto_sha256` (los bytes de `procedencia.json`) y §3.2 dice que si C2 falla → `no_reproducible`. La comparación siempre usa el manifiesto del **registro** (autoritativo, §7); la copia solo interviene en C2. Copia alterada → `no_reproducible` aunque el registro esté íntegro; registro alterado → `no_reproducible` aunque la copia sea intacta (la copia no lo rescata); ambos alterados o contradictorios (p. ej. copia válida de otra corrida) → `no_reproducible`; copia **ausente** con registro íntegro → se compara (no es una alteración); registro ausente con copia válida → máximo `parcial` (D-B); ambos ausentes → `no_reproducible` (legado o error). Qué detecta y qué no (cinco casos distintos): (1) contenido de origen distinto → `no_reproducible` (C3b); (2) copia de procedencia alterada → `no_reproducible` (C2); (3) registro alterado sin recalcular su SHA → `no_reproducible` (C2); (4) `hash_resultado` de la fila distinto del manifiesto → `no_reproducible` (C2); (5) **reescritura coherente de registro, SHA y copia**: la integridad NO la detecta, porque no hay autenticidad criptográfica (límite documentado en `IMPLEMENTACION_3A3_PROCEDENCIA.md` §9 y §11, riesgo 3). En ese caso solo la delata la comparación si lo reescrito participa en ella: el SHA de una fuente → `no_reproducible` (C3b); el `hash_resultado` → `parcial` (C7, anomalía de determinismo). Un cambio **solo de nombre** u otros metadatos que no participan en el hash ni en las comprobaciones **no se detecta** y el resultado sigue siendo `exacta` (la prueba `test_reescritura_coherente_que_solo_cambia_el_nombre_NO_se_detecta_y_es_exacta` lo documenta como límite conocido, no como detección). No se promete más autenticidad que esa | 13 pruebas en `TestI1CopiaVsRegistro` |
| **I-2** | **Confirmada y reforzada**. Hallazgo y corrección de un hueco real: `evaluar` verificaba las fuentes con `fuentes` pero `regenerador(fuentes=…)` recibía su propia lista, de modo que podía regenerarse con archivos **no verificados**. Ahora `regenerar(fuentes_verificadas, shas)` recibe solo las fuentes cuyo SHA-256 coincide con el registrado (sin repetidos) y el regenerador comprueba que el manifiesto que produce lista exactamente esas fuentes. Además, cualquier archivo aportado cuyo SHA no esté registrado hace fallar C3b, aunque comparta nombre con una fuente registrada que también se aportó. No existe un flujo legítimo con archivos auxiliares: el reporte tiene una sola fuente (`input.xlsx`); el contexto es texto y la plantilla se compara en C4 | 12 pruebas en `TestI2FuentesAportadas`; la verificación de fuentes por el regenerador se prueba además en `test_procedencia_regenerador.py` |
| **I-3** | **Resuelta separando los tres conceptos** (tabla de arriba). No se crea un cuarto estado de reproducibilidad: «sin clasificar» es `null`. El contrato `comparacion/1` pertenece a este PR (nada de él está fusionado), por lo que se ajustó antes de publicarlo | 17 pruebas en `TestI3TresConceptos` |
| **I-4** | **Confirmada**: sin persistencia. El resultado es JSON plano determinista (`serializar_comparacion`), se puede **verificar después** con `leer_comparacion`/`validar_comparacion` (estructura y coherencia lógica, p. ej. rechaza una `exacta` sin regeneración igual) y referencia el manifiesto (`evidencia.manifiesto_sha256`, `run_id`) y la regeneración (`hash_registrado`, `hash_regenerado`). No toca el historial (bytes idénticos antes y después, sin tablas nuevas). El servicio actual no tiene endpoint para la comparación (L-3) y no se modifica; el resultado ya es JSON puro, así que `bridge.handle` podrá devolverlo sin adaptador | 10 pruebas en `TestI4SinPersistencia` |

## 3. Arquitectura

```
provenance.comparar (puro)          clasifica C1..C7 → estado, diferencias, notas, alertas, evidencia
provenance_verify.verificar         C1/C2 (integridad del registro y de la copia); ahora añade `registro.codigos` (causas estructuradas)
provenance_compare.evaluar          reúne la evidencia actual, decide si hay que regenerar, regenera SOLO si se pide y C1..C6 pasan
provenance_compare.regenerador      construye el callable `regenerar(fuentes_verificadas, shas)` real (motor + build_* con la plantilla, sin historial, en carpeta temporal)
```

Garantías verificadas por pruebas: solo lectura (ningún archivo del reporte, del historial ni de las fuentes cambia y no se crean temporales); jamás regenera en silencio; ninguna excepción se convierte en éxito (`evaluar` no lanza: devuelve `estado = null` y `evaluacion = fallida` con la causa); determinismo (mismas entradas → mismos bytes de evidencia); `provenance.py` sigue puro; `comparar` también se ejecuta en Pyodide con idéntico resultado.

## 4. Matriz de criterios de aceptación

| ID | Criterio | Prueba (archivo · prueba) |
|---|---|---|
| A01 | La regeneración usa la procedencia existente | `test_procedencia_evaluar` · `test_a01_a03_regeneracion_real_identica_es_exacta_y_usa_la_procedencia_existente`; `test_procedencia_regeneracion` · `test_regenerar_con_las_mismas_entradas_es_exacta_y_determinista` |
| A02 | Comparación determinista | `test_procedencia_comparacion` · `test_a02_…`; `test_procedencia_evaluar` · `test_repetir_la_comparacion_…`; regeneración real repetida |
| A03 | Idéntica → `exacta` | los de A01 (4 escenarios reales) |
| A04 | Diferencias justificadas → `parcial` | `test_c3a_…`, `test_c4_c5_c6_…`, `test_c6_cambios_en_reglas_…`, `test_metas_distintas_…` |
| A05 | La ausencia de evidencia no es coincidencia | `test_a05_la_ausencia_de_evidencia_actual_…`, `test_c5_un_commit_desconocido_…`, `test_sin_commit_estampado_nunca_es_exacta` |
| A06 | Diferencias identificadas y documentadas | `test_c4_c5_c6_una_version_distinta_…` (componente exacto), `test_c6_…` (hoja por hoja) |
| A07 | Manifiestos incompletos | `test_manifiesto_ausente_o_invalido_con_registro_presente_no_se_compara`, `test_registro_con_manifiesto_invalido_y_sha_coherente_…` |
| A08 | Versiones incompatibles | `test_c1_o_c2_fallan_…` (esquema), `test_a08_esquema_incompatible_…`, `test_a08_un_contrato_de_hash_distinto_…` |
| A09 | Errores de regeneración no son éxitos | `test_a09_…` (ambos archivos), `TestI3TresConceptos::test_regeneracion_fallida_o_incompleta_…`; fallos reales del regenerador en `tests/unit/test_procedencia_regenerador.py` (escenarios A, B y C) |
| A10 | Evidencia suficiente para auditoría | `test_a10_la_evidencia_conserva_…`, `test_el_resultado_se_puede_conservar_como_evidencia` |
| A11 | Contratos 3A-0 a 3A-3 preservados | suites de 3A-1/2/3 completas sin cambios; `archivos_protegidos --check` |
| A12 | Hashes y líneas base congelados | `test_hash_resultado`, `test_linea_base`, `capture_baseline --check` |
| A13 | Suite anterior intacta | suite completa |
| A14 | Pyodide con validación obligatoria | `test_hash_pyodide` (incluye `comparar` dentro de Pyodide) con `REPORT_PYODIDE_REQUIRED=1` |
| A15 | CI del PR en success | ver informe |
| A16 | Pages sin regresiones | `app.zip` incluye `provenance_compare.py`; ver informe |
| T-08 | Coincidente, versión distinta, archivo faltante, sin manifiesto, hash de entrada distinto, manifiesto alterado, anomalía de determinismo, `procedencia_error.json` | `test_procedencia_comparacion` y `test_procedencia_evaluar` (cada caso) |
| PR-5 | Fila = bytes del archivo; invariantes con `runs`/`sources` | `test_procedencia_flujo` (3A-3) + comparación sobre esas filas |
| PR-10 | Tres igualdades; entorno solo nota | `test_pr10_…`, `test_entorno_distinto_es_solo_nota` |
| PR-11 | Sin regeneración nunca `exacta` | `test_pr11_…` (ambos archivos) |
| AC-11 | 0 regeneraciones silenciosas | `test_ac11_solo_regenera_si_se_pide_y_si_c1_a_c6_pasan` |
| AC-12 | Legado = `no_reproducible` | `test_ac12_reporte_legado_…` |
| E-4 | Error de procedencia nunca parcial/exacta | `test_reporte_con_error_de_procedencia_es_no_reproducible_e4` |
| D-B | Sin historial, máximo `parcial` | `test_db_sin_registro_y_copia_valida_…` (ambos archivos) |
| Seg. | No modifica evidencia; no crea archivos | `test_la_comparacion_no_modifica_ninguna_evidencia`, `test_la_comparacion_no_crea_archivos_ni_temporales`, `test_la_regeneracion_no_escribe_nada_fuera_…` |

## 5. Limitaciones

* La comparación solo existe en backend (L-3): no hay pantalla ni botón.
* «Regenerar con versiones actuales» como reporte nuevo (oferta de §3.2 para `parcial`) es una acción de interfaz, no se implementa aquí: la comparación nunca regenera por sí sola.
* Un callable de regeneración propio (distinto de `regenerador()`) es responsabilidad de quien lo escribe; `evaluar` solo le entrega fuentes verificadas.
* `exacta` solo es alcanzable en una compilación con commit estampado (`app.zip` desde `build_site.py`); en un árbol sin estampar C5 falla por diseño.
* **Cobertura de los fallos del regenerador (D-07).** `tests/unit/test_procedencia_regenerador.py` se ejecuta en CI y recorre `evaluar → regenerador → correr → build_aetops` con el motor, el regenerador y la captura reales. El escenario A usa el `build_aetops` real (bloqueo `TARGETS_MISSING` por no pasar metas). Los escenarios B y C **sustituyen la construcción del PPTX** (`build_aetops`) porque generarlo exige la plantilla con marca, que no se versiona: no prueban el PPTX ni la narrativa real de un reporte (el sustituto usa una narrativa fija). La regeneración con plantillas reales sigue validándose solo en local (`test_procedencia_regeneracion.py`, `test_procedencia_build.py`, generación por API), y un CI verde no la demuestra. La rama GLP-1 del regenerador no tiene cobertura propia.
