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

| Estado | Condición (spec §3.2, en este orden; gana la primera) | Evidencia obligatoria |
|---|---|---|
| `no_reproducible` | C1 falla (sin manifiesto, legado, esquema desconocido, manifiesto inválido) **o** C2 falla (manifiesto alterado) **o** C3b falla (un archivo fuente aportado difiere) | Resultado de `provenance_verify.verificar` y fuentes aportadas |
| `parcial` | C1 y C2 pasan, C3b no falla y se cumple al menos una: C3a falta, C4, C5 o C6 fallan, o no hay registro contra el cual verificar C2 (D-B); **o** C1 a C6 pasan y C7 falla (anomalía de determinismo) | Estado actual (plantilla, versiones, configuración) |
| `exacta` | C1 a C6 pasan **y** C7 pasa: existe una regeneración real y su `hash_resultado` es igual al registrado | Regeneración ejecutada |
| `no_evaluada` (**no es un estado de la spec**, ver I-3) | C1 a C6 pasan pero no se regeneró, o la regeneración falló | — |

* **Qué se compara:** C1/C2 integridad del registro (y de su copia); C3a/C3b fuentes por SHA-256 (el contenido manda, no el nombre); C4 plantilla (`id` + SHA-256); C5 `version_codigo` (app + commit); C6 `version_motor`, `version_definiciones`, `version_reglas` y `configuracion` completas; C7 `hash_resultado` regenerado. `entorno` solo se informa como nota.
* **Ausencia de evidencia:** cualquier componente actual no aportado (`None`) es una diferencia «sin evidencia actual» y nunca coincidencia. Un commit `desconocido` o `+dirty`, aunque sea igual en ambos lados, **no demuestra** que sea el mismo código (C5 falla).
* **Versiones incompatibles:** esquema de procedencia desconocido → C1 falla (`no_reproducible`); versión de motor/definiciones/reglas/código distinta → C5/C6 (`parcial`); un `hash_resultado.contrato` distinto del actual hace que el manifiesto sea inválido en la validación de 3A-3 (esquema cerrado) → `no_reproducible`.
* **Registro de diferencias:** lista ordenada y determinista de `{componente, registrado, actual, motivo}` hoja por hoja (valores largos recortados a 200 caracteres), más `notas` (entorno), `alertas` (anomalía de determinismo, entorno diferente con resultado igual) y `avisos` (fuentes ilegibles, «no se regeneró»).
* **Regeneración fallida:** C7 = `error`, estado `no_evaluada`, mensaje normalizado (sin rutas absolutas). Nunca `exacta` ni `parcial` inventado.

### Interpretaciones que la especificación no fija (revisar)

| ID | Punto | Decisión conservadora tomada |
|---|---|---|
| I-1 | C2 compara «los bytes de `procedencia.json`» con `manifiesto_sha256`. Si la **copia** difiere pero el **registro** está íntegro | `no_reproducible` (causa explícita «copia alterada; el registro autoritativo está íntegro»). La comparación siempre usa el manifiesto del registro, nunca el de la copia. Una copia **ausente** no impide comparar |
| I-2 | Un archivo aportado que no corresponde a ninguna fuente registrada (ni por SHA ni por nombre) | C3b falla (`no_reproducible`): no hay forma de demostrar que sea equivalente |
| I-3 | La spec no dice qué estado tiene «C1 a C6 pasan y no se regeneró» ni «la regeneración falló» (PR-11 solo dice «nunca `exacta`») | `no_evaluada`, que no afirma ni niega reproducibilidad. 3A-3 ya usaba este valor |
| I-4 | La comparación no define dónde se conserva su resultado | Se devuelve un resultado estructurado y determinista (`serializar_comparacion`); **no** se crea tabla ni archivo (no está especificado y no se debe inventar un esquema). Quien la llame puede guardar esos bytes |

Además: el texto editado a mano entra en el hash (3A-2) pero **no** se guarda en el manifiesto. Regenerar sin las mismas ediciones produce una anomalía de determinismo (correctamente visible, nunca `exacta`); con las mismas ediciones coincide (prueba incluida). Esto es una propiedad del contrato ya aprobado, no un defecto de 3A-4.

## 3. Arquitectura

```
provenance.comparar (puro)          clasifica C1..C7 → estado, diferencias, notas, alertas, evidencia
provenance_verify.verificar         C1/C2 (integridad del registro y de la copia); ahora añade `registro.codigos` (causas estructuradas)
provenance_compare.evaluar          reúne la evidencia actual, decide si hay que regenerar, regenera SOLO si se pide y C1..C6 pasan
provenance_compare.regenerador      construye el callable de regeneración real (motor + build_* con la plantilla, sin historial, en una carpeta temporal)
```

Garantías verificadas por pruebas: solo lectura (ningún archivo del reporte, del historial ni de las fuentes cambia y no se crean temporales); jamás regenera en silencio; ninguna excepción se convierte en éxito (`evaluar` no lanza: devuelve `no_evaluada` con la causa); determinismo (mismas entradas → mismos bytes de evidencia); `provenance.py` sigue puro; `comparar` también se ejecuta en Pyodide con idéntico resultado.

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
| A09 | Errores de regeneración no son éxitos | `test_a09_una_regeneracion_que_lanza_…`, `test_una_regeneracion_que_devuelve_basura_…`, `test_a09_una_regeneracion_fallida_o_invalida_…` |
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
* `evaluar` no puede comprobar que el callable de regeneración use las mismas fuentes que `fuentes`; `regenerador()` está construido para recibirlas una sola vez.
* `exacta` solo es alcanzable en una compilación con commit estampado (`app.zip` desde `build_site.py`); en un árbol sin estampar C5 falla por diseño.
