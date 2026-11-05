# Auditoría integral y reconstrucción de criterios de aceptación · Subfase 3A-4 / PR #20

> **Naturaleza de este documento.** Es una **reconstrucción de criterios verificables** hecha a partir de las fuentes disponibles. **No es la recuperación del documento original perdido** («Revisión correctiva y validación final — PR #20»), cuyo texto termina a mitad de la sección 5 y cuyas dos observaciones técnicas no pudieron identificarse. No sustituye a ese documento ni inventa su contenido.
>
> Redactado durante una auditoría **sin cambios de código, de pruebas ni de documentos existentes** y sin commits. Este archivo es la única adición.

## 1. Objetivo y alcance

Determinar, con la documentación disponible y el código real del PR #20, si la implementación de 3A-4 cumple los requisitos verificables; detectar defectos y ambigüedades; y dejar una base trazable. No se rehace 3A-4 ni se pierde su trabajo.

Fuera de alcance: corregir (se proponen correcciones, no se aplican), 3A-5, 3B, interfaz.

## 2. Fuentes y jerarquía

| Nivel | Fuente | Uso |
|---|---|---|
| 1 | `docs/fase3a/ESPECIFICACION_FASE3A_PROCEDENCIA.md` (§3, §8.1, §8.4, §10, §11, §13) y contratos protegidos | Requisitos normativos (prefijo **N-**) |
| 2 | DOCX `0cc45571…` «Implementación condicional y cierre estricto — 3A-4» (15 991 B, SHA-256 `c8f96997…63ed8`) | Alcance, restricciones y criterios A01–A16 (prefijo **I-**) |
| 3 | DOCX `384cde9f…` «Revisión correctiva» secciones 0 a 5 (12 986 B, SHA-256 `7a7605b8…da14`) | Criterios I-1 a I-4 (prefijo **R-**) |
| 4 | DOCX `5eb7036f…` (3A-3) y `IMPLEMENTACION_3A2/3A3` | Contratos y restricciones heredados (prefijo **H-**) |
| 4 | DOCX `a734c424…` (esta auditoría; 13 039 B, SHA-256 `012d1c0b2e576c5778d54f5da19d055a821ec8ba25d252cb2c67eee884bcb0a9`) | Método y decisión expresa sobre `comparacion/1` |
| 5 | `IMPLEMENTACION_3A4_COMPARACION.md` y descripción del PR | Decisiones de implementación (no tienen autoridad para contradecir la spec) |
| 6 | Código y pruebas en `a661864` | Comportamiento real |

No se detectó contradicción entre fuentes del mismo nivel que obligue a elegir arbitrariamente.

## 3. Estado inicial del PR (verificado en GitHub y en el repositorio)

| Comprobación | Resultado |
|---|---|
| PR #20 | abierto, sin fusionar, no borrador, `mergeable_state: clean` |
| Rama | `claude/awesome-wozniak-f35r21` |
| HEAD | `a661864a6974ad1f4530f9cc1c1ccfeae5243a22` (igual local y remoto); base `main` = `e4b2f65` |
| Árbol de trabajo | limpio (antes de crear este documento) |
| CI | run 44 (`pull_request`), job `unit`: success, sobre `a661864` |
| Revisiones / bloqueos | ninguna revisión; un comentario automático de CodeRabbit sin hallazgos |
| Archivos modificados respecto a `main` | `provenance.py` (+386), `provenance_compare.py` (+191, nuevo), `provenance_verify.py` (+11/−4), `ESPECIFICACION…md` (+2/−1), `IMPLEMENTACION_3A4…md` (nuevo), `hash_pyodide.mjs` (+11/−2), `test_hash_pyodide.py` (+37/−1), 4 archivos de pruebas nuevos. Ningún archivo eliminado |
| Protecciones | `archivos_protegidos --check`: sin cambios; ningún archivo del PR es protegido |
| Líneas eliminadas en pruebas existentes | solo la línea de invocación del script de Pyodide y su comentario, ampliados con un argumento opcional; ninguna prueba eliminada ni debilitada |

## 4. Criterios de aceptación reconstruidos y 5. Matriz de trazabilidad

Estados: **CUMPLIDO**, **PARCIALMENTE CUMPLIDO**, **INCUMPLIDO**, **NO VERIFICABLE**, **REQUIERE AUTORIZACIÓN**. Las pruebas están en `tests/unit/test_procedencia_{comparacion,evaluar,revision_3a4}.py` (abreviadas **CMP**, **EVA**, **REV**), `tests/regression/test_procedencia_regeneracion.py` (**REG**, solo con plantillas locales) y `tests/e2e/test_hash_pyodide.py` (**PYO**).

### 5.1 Requisitos normativos (spec)

| ID | Fuente · sección | Requisito (paráfrasis fiel) | Implementación | Prueba | Estado | Riesgo / acción |
|---|---|---|---|---|---|---|
| N-01 | Spec §3.1 | Comprobaciones C1–C7 | `provenance._c1_c2`, `_c3`, `_c4`, `_c5`, `_c6`, `_c7` | CMP `test_todo_igual…`, `test_exacta_solo_cuando_se_cumplen_todos_los_criterios` | CUMPLIDO | — |
| N-02 | Spec §3.2 | Orden de evaluación: gana la primera fila | `provenance.comparar` | CMP `test_el_orden_de_la_spec_gana_la_primera_fila` | CUMPLIDO | — |
| N-03 | Spec §3.2/§3.5, PR-11 | `exacta` exige regeneración real con C7 | `comparar` (C7 `pasa`) | CMP `test_pr11…`; REV `test_nunca_exacta_sin_regeneracion_completada_e_igual`; mutación M01 (muerta) | CUMPLIDO | — |
| N-04 | Spec §3.2 caso límite | C1–C6 pasan y C7 falla → `parcial` + «anomalía de determinismo» | `comparar` | CMP `test_anomalia_de_determinismo…`, `test_la_anomalia_senala_el_entorno…` | CUMPLIDO | — |
| N-05 | Spec §3.2/§3.4, PR-10 | Solo difiere `entorno` → nota, no cambia el estado | `comparar` (notas) | CMP `test_pr10…`; EVA `test_entorno_distinto_es_solo_nota` | CUMPLIDO | — |
| N-06 | Spec §3.2 | Solo difiere el SHA del commit → `parcial` | `_c5` | EVA `test_commit_distinto_es_parcial…` | CUMPLIDO | — |
| N-07 | Spec §3.2, AC-12 | Legado = `no_reproducible` | `_c1_c2` | EVA `test_ac12…` | CUMPLIDO | — |
| N-08 | Spec §3.2/§8.4, E-4, PR-9 | `procedencia_error.json` sin manifiesto válido → `no_reproducible` («procedencia no disponible por un error al generarla») | `_c1_c2` | CMP `test_error_de_generacion_nunca_es_parcial_ni_exacta_e4`; EVA `test_reporte_con_error_de_procedencia…` | CUMPLIDO | — |
| N-09 | Spec §3.3, D-B | Sin registro autoritativo, máximo `parcial` | `comparar` (`sin_c2`) | CMP `test_db_sin_registro_y_copia_valida…`; EVA `test_db_solo_con_copia_valida…`; M07 (muerta) | CUMPLIDO | — |
| N-10 | Spec §3.5, R-8 | No usar «idéntico» sin decir qué | única aparición: `IGUALDAD_CANONICA` («resultado canónico… NO implica igualdad binaria ni visual») | CMP `test_todo_igual…` (texto) | CUMPLIDO | — |
| N-11 | Spec AC-11 | Los tres estados se producen **y se muestran** | Producción: `comparar`. Mostrar: no existe (L-3: sin UI) | todas las anteriores | PARCIALMENTE CUMPLIDO | Bajo. «Mostrar» queda fuera por L-3; ninguna acción en 3A-4 |
| N-12 | Spec AC-11 | 0 regeneraciones silenciosas con versiones distintas | `evaluar` regenera solo si se pide y C1–C6 pasan | EVA `test_ac11…`; M13 (muerta) | CUMPLIDO | — |
| N-13 | Spec §10/T-08 | Casos: coincidente, versión distinta, archivo faltante, sin manifiesto, hash de entrada distinto, manifiesto alterado, anomalía de determinismo, reporte con error | `comparar` / `evaluar` | CMP y EVA (un caso por cada uno) | CUMPLIDO | — |
| N-14 | Spec PR-5 (asignado a 3A-4) | Fila = bytes del archivo; `manifiesto_sha256` coincide; invariantes con `runs` y `sources` | Captura de 3A-3 | `tests/regression/test_procedencia_flujo.py` (3A-3) | CUMPLIDO | Bajo. Evidencia heredada de 3A-3: no se repite en pruebas de 3A-4 |
| N-15 | Spec §10 (3A-4) | Un historial anterior abre sin migración; las filas son inmutables | `history/store.py` (3A-3) | `test_procedencia_historial.py` (3A-3) | CUMPLIDO | Evidencia heredada de 3A-3 |
| N-16 | Spec §8.1 | `comparar` vive en `provenance.py` y es pura | `provenance.comparar` | CMP `test_el_modulo_sigue_siendo_puro`; PYO (se ejecuta en Pyodide con idéntico resultado) | CUMPLIDO | — |
| N-17 | Spec §3.2 («Qué muestra») | Lista de componentes que difieren; no regenera en silencio; permite regenerar «con versiones actuales» marcado *no equivalente* | Lista: `diferencias`. No silencio: ver N-12. La oferta de regenerar como reporte nuevo no existe | CMP/EVA | PARCIALMENTE CUMPLIDO | Bajo: la oferta es una acción de interfaz (L-3); documentada |

### 5.2 Instrucción original de 3A-4 (`0cc45571`)

| ID | Sección origen | Requisito | Evidencia | Estado | Riesgo / acción |
|---|---|---|---|---|---|
| I-01 | §2 | Auditoría previa (rama, árbol, `main`, 3A-3 integrada, leer spec) | Informe de la sesión; `IMPLEMENTACION_3A4…` §1 | CUMPLIDO | — |
| I-02 | §3 | Definir los estados por la spec; no inventar; si falta una definición indispensable, detenerse | I-3 de la revisión; `null` documentado | CUMPLIDO | El caso «sin regeneración» no lo define la spec; lo cubre la autorización del documento `a734c424` (ver §7 de esta auditoría) |
| I-03 | §3 reglas | Ausencia de evidencia ≠ coincidencia; error ≠ éxito; no ocultar diferencias; no alterar evidencia | CMP `test_a05…`, `test_a09…`; EVA `test_la_comparacion_no_modifica…`; M04, M05, M15 (muertas) | CUMPLIDO | — |
| I-04 | §4 | Matriz A01–A16 con prueba por criterio | `IMPLEMENTACION_3A4…` §4 | CUMPLIDO | Los conteos de esa tabla contienen errores (D-02) |
| I-05 | A15 | CI del PR en success | run 44 en `a661864` | CUMPLIDO | — |
| I-06 | A16 | GitHub Pages sin regresiones | Pages solo se despliega desde `main` | NO VERIFICABLE | Verificable solo tras fusionar. `app.zip` incluye `provenance_compare.py` (build de producción) |
| I-07 | A14 | Pyodide con validación obligatoria | PYO con `REPORT_PYODIDE_REQUIRED=1`; CI lo ejecuta | CUMPLIDO | — |
| I-08 | §5 | Mantener arquitectura; sin refactorizaciones; sin UI; sin dependencias nuevas | Diff: módulos nuevos separados, sin tocar protegidos | CUMPLIDO | — |
| I-09 | §6 A | Exacta: caso idéntico, repetición, solo cuando se cumplen todos los criterios | 4 escenarios reales (REG), CMP/EVA | CUMPLIDO | REG se omite en CI (D-09) |
| I-10 | §6 B | Parcial: diferencias, faltantes, versiones, motivos registrados | CMP/EVA | CUMPLIDO | — |
| I-11 | §6 C | Negativos: manifiesto inexistente/incompleto, ausentes, alterados, versiones, regeneración fallida, contradictoria, corrupta, error de lectura, error de escritura | Todos con prueba; «error de escritura» no aplica (la comparación no escribe: EVA `test_la_comparacion_no_crea_archivos…`) | CUMPLIDO | — |
| I-12 | §6 D | Nunca `exacta` con evidencia insuficiente; nunca ocultar diferencias; excepciones nunca éxito; ausencia ≠ coincidencia; no modificar evidencia | M01–M20 (19 de 20 muertas; ver §9) | CUMPLIDO | — |
| I-13 | §6 E / §8 | Regresión: 3A-0..3A-3, protegidos, hashes, baseline, procedencia, historial, build, Pyodide | Suite completa 995/0/35; `capture_baseline` 8/8; `archivos_protegidos` sin cambios | CUMPLIDO | — |
| I-14 | §7 | Ciclo de corrección con evidencia | Informe de la sesión (4 defectos corregidos) | CUMPLIDO | — |
| I-15 | §9 | Rama independiente; commits solo de 3A-4; PR con resultados; descripción actualizada | PR #20; 2 commits | CUMPLIDO | La rama es la asignada por el entorno (mismo nombre que las anteriores, reiniciada desde `main`) |
| I-16 | §11 | No debilitar ni eliminar pruebas; no modificar contratos anteriores ni hashes | Diff sin eliminaciones de pruebas; 3A-2/3A-3 intactos | CUMPLIDO | — |

### 5.3 Revisión correctiva disponible (`384cde9f`, secciones 0–5)

| ID | Sección | Requisito | Implementación | Prueba | Estado | Riesgo / acción |
|---|---|---|---|---|---|---|
| R-01 | §0 | Cerrar I-1..I-4 sin rehacer 3A-4 | `a661864` | REV | CUMPLIDO | Solo sobre lo recuperado: la parte perdida no se puede evaluar (R-02, R-13) |
| R-02 | §0 | **Dos observaciones técnicas** | — | — | NO VERIFICABLE | Ver §11 |
| R-03 | §1 | Verificar estado real del PR | §3 de este documento | — | CUMPLIDO | — |
| R-04 | §2 (I-1) | Copia vs registro: intacto, copia alterada, registro alterado, ambos, contradictoria, manifiesto ausente, registro ausente | `_c1_c2`; `evaluar` usa el manifiesto del registro | REV `TestI1CopiaVsRegistro` (10) | CUMPLIDO | — |
| R-05 | §2 criterio | Ninguna copia alterada ni evidencia contradictoria puede dar **falsamente** `exacta` | idem | REV, M02 (muerta) | PARCIALMENTE CUMPLIDO | Un reescrito **coherente** de registro + SHA + copia que solo cambia un nombre da `exacta` (verificado, §9); es inherente a la integridad no criptográfica y el resultado canónico sí coincide. Ver D-04, D-05 |
| R-06 | §3 (I-2) | Ocho casos de fuentes aportadas | `_c3`; `evaluar` entrega solo fuentes verificadas | REV `TestI2FuentesAportadas` (12); M03, M14, M16 (muertas) | CUMPLIDO | — |
| R-07 | §3 criterio | Ningún archivo distinto se ignora en silencio; no rechazar flujos legítimos | `_c3`; no existe flujo con archivos auxiliares (una sola fuente por reporte) | REV `test_ningun_archivo_distinto…`, `test_no_hay_un_flujo_legitimo…` | CUMPLIDO | Supuesto: una fuente por reporte; si cambia la arquitectura debe revisarse |
| R-08 | §4 (I-3) | Separar reproducibilidad / evaluación / regeneración | `comparar` | REV `TestI3TresConceptos` (17) | CUMPLIDO | — |
| R-09 | §4 | Pruebas obligatorias: sin solicitar, solicitada, termina bien, falla, resultado incompleto, hash distinto, idéntico | CMP/EVA/REV | idem | PARCIALMENTE CUMPLIDO | Cumplido a nivel `comparar` y `evaluar`. **«Resultado incompleto» a nivel del regenerador** (fallo de `build_*`) no tiene prueba: D-07 |
| R-10 | §4 criterio | Nunca `exacta` sin regeneración real y C1–C7; fallo ≠ éxito parcial; representación inequívoca; si la spec no define, documentar y **pedir autorización antes de modificar el contrato** | `null` + `evaluacion` + `regeneracion` | REV | CUMPLIDO | La autorización llegó en el documento `a734c424` §7 con seis condiciones; se verifican en el §7 de esta auditoría |
| R-11 | §5 (I-4) | Determinismo, serialización, integridad, validación posterior, referencias, historial intacto, sin persistencia | `serializar_comparacion`, `validar_comparacion`, `leer_comparacion` | REV `TestI4SinPersistencia` (10); M10, M11, M12 (muertas) | CUMPLIDO | Determinismo **entre procesos** sin prueba directa (D-08) |
| R-12 | §5 | «Consumir desde el servicio existente» | El resultado es JSON puro; el servicio no tiene endpoint (L-3) y `service.py` es protegido | REV `test_el_resultado_es_json_plano…` | PARCIALMENTE CUMPLIDO | Solo se demuestra compatibilidad de formato. Un endpoint requeriría tocar `service.py` (protegido): **REQUIERE AUTORIZACIÓN** si se desea |
| R-13 | §5 en adelante | Resto de la sección 5 y siguientes | — | — | NO VERIFICABLE | Texto perdido |

### 5.4 Restricciones heredadas (3A-0 a 3A-3)

| ID | Origen | Restricción | Evidencia | Estado |
|---|---|---|---|---|
| H-01 | 3A-3 (`5eb7036f`) Parte 2.2 / 4.5 | `runs` no se modifica; tabla `procedencia` autoritativa e inmutable | `store.py` sin cambios en 3A-4; `test_procedencia_historial` | CUMPLIDO |
| H-02 | 3A-2 | Contrato de `hash_resultado` intacto | `test_hash_resultado` + hashes congelados; `capture_baseline` 8/8 | CUMPLIDO |
| H-03 | 3A-3 Parte 4.3 | El motor de reglas no se ejecuta; no se altera el contenido del reporte | Sin cambios en `build.py`/`service.py`; `ejecucion.motor_ejecutado=false` | CUMPLIDO |
| H-04 | 3A-3 Parte 6 | Sin secretos ni datos sensibles; sin escrituras fuera de rutas permitidas | `comparar`/`evaluar` no escriben; mensajes con rutas normalizadas (CMP `test_el_mensaje_de_error_de_regeneracion_no_filtra_rutas`) | CUMPLIDO |
| H-05 | 3A-3 Parte 7 | No modificar archivos protegidos | `archivos_protegidos --check` sin cambios | CUMPLIDO |

## 6. Auditoría de I-1 a I-4 contra la especificación normativa

* **I-1.** La spec §3.1 C2 compara «sha256(bytes del manifiesto)» con `manifiesto_sha256` y §3.2 manda `no_reproducible` si C2 falla; por tanto copia alterada ⇒ `no_reproducible` es **lectura literal**, no una interpretación de la revisión. El manifiesto que se compara es siempre el del **registro** (autoritativo, §7); la copia solo interviene en C2. Probado: copia alterada, registro alterado (la copia no lo rescata), ambos alterados, copia válida de otra corrida, copia ausente (se compara), registro ausente con copia válida (≤ `parcial`), ambos ausentes. **Hallazgo:** un reescrito coherente de registro, SHA y copia que solo cambia un nombre produce `exacta` (verificado); es consecuencia de que el nombre no interviene en el hash y de que la integridad es detectable, no criptográfica (límite documentado en `IMPLEMENTACION_3A3` §9).
* **I-2.** Las fuentes se identifican por SHA-256; el nombre es informativo. Política: toda fuente aportada con SHA no registrado hace fallar C3b; toda fuente registrada no aportada falla C3a; contenido idéntico con nombres distintos y fuentes repetidas son una sola fuente. `evaluar` solo entrega a la regeneración las fuentes verificadas, y `regenerador` comprueba que el manifiesto producido lista exactamente esas fuentes. La política es conservadora y no rechaza ningún flujo que la arquitectura genere hoy (una fuente por reporte).
* **I-3.** La spec define tres estados; para «C1–C6 pasan y no hay regeneración completada» no define estado (PR-11 solo prohíbe `exacta`). La implementación usa `estado = null` (sin clasificar) con `evaluacion` y `regeneracion` separados, y `validar_comparacion` impone la coherencia (p. ej. `exacta` ⇒ regeneración completada con el mismo hash). No contradice la spec; la extiende por el único lado seguro.
* **I-4.** Sin persistencia: probado que el historial no cambia (bytes idénticos, sin tablas nuevas). Determinismo: mismos bytes en dos comparaciones y en ocho procesos con semillas de hash distintas. Verificabilidad posterior: `leer_comparacion`/`validar_comparacion`. Referencias: `evidencia.manifiesto_sha256`, `run_id`, `regeneracion.hash_registrado/regenerado`.

## 7. Auditoría de contratos y decisión expresa sobre `comparacion/1`

El documento `a734c424` §7 autoriza conservar la estructura actual de `comparacion/1` si se cumplen **simultáneamente** seis condiciones. Verificación:

| # | Condición | Resultado | Evidencia |
|---|---|---|---|
| 1 | No modifica contratos anteriores protegidos | **Se cumple** | `archivos_protegidos --check` sin cambios; ningún archivo protegido en el diff |
| 2 | No altera el comportamiento de 3A-2 ni 3A-3 | **Se cumple** | `provenance_verify.verificar` solo agrega `registro.codigos` (campo aditivo); las pruebas de 3A-2 y 3A-3 (entre ellas las 119 de `test_provenance.py`) pasan sin cambios en este PR; hashes y baseline idénticos |
| 3 | Mantiene la separación reproducibilidad / evaluación / regeneración | **Se cumple** | `TestI3TresConceptos`; `validar_comparacion` |
| 4 | Es compatible con la especificación normativa | **Se cumple** | La spec no define el esquema del resultado ni prohíbe `null`; los tres estados y su orden se respetan (N-01..N-09) |
| 5 | Representación determinista y verificable | **Se cumple** | `serializar_comparacion`, `leer_comparacion`; 8 semillas ⇒ 1 hash |
| 6 | Sin persistencia ni modificación indirecta del historial | **Se cumple** | `test_no_modifica_el_historial…`, `test_la_comparacion_no_crea_archivos…` |

Las seis condiciones se cumplen: **no hay motivo para detenerse**. La autorización cubre conservar la estructura; no cubre tocar contratos anteriores.

Otros contratos: `procedencia/1` (sin cambios), tabla `procedencia` (sin cambios), contrato de hash `resultado_canonico/1` (sin cambios), `runs` (sin cambios), `verificar()` (aditivo), `comparacion/1` (nuevo en este PR, nada fusionado).

## 8. Regresiones

| Aspecto | Resultado |
|---|---|
| Suite completa (Pyodide activo, `REPORT_PYODIDE_REQUIRED=1`), ejecutada de nuevo sobre `a661864` | **995 aprobadas, 0 fallidas, 35 omitidas** (15 min 42 s) |
| Omitidas | Las mismas 35, todas en `tests/golden`: 14 + 8 «faltan plantilla/Excel reales o LibreOffice», 7 + 4 «REPORT_FIXTURES_DIR sin archivos/libros de ejemplo», 1 + 1 «sin Excel/libro trimestral»; ninguna fuera de esa carpeta |
| `capture_baseline --check` | 8 de 8 idéntico |
| `archivos_protegidos --check` | sin cambios |
| Hashes de 3A-2 | iguales a los congelados |
| Pyodide | `comparar` produce los mismos bytes de evidencia que en CPython |
| CI | run 44 en success (incluye Pyodide obligatorio) |
| Pruebas nuevas | 151 (CMP 52, EVA 40, REV 49, REG 10; 995 − 844 = 151) |
| Pruebas modificadas | `test_hash_pyodide.py` (ampliada) y su script `hash_pyodide.mjs`; ninguna debilitada |

## 9. Pruebas y evidencias (incluye detección de pruebas débiles)

**Mutación (en una copia fuera del repositorio; el repositorio no se tocó).** Se introdujeron 20 defectos deliberados en `comparar`, `serializar_comparacion`, `leer_comparacion`, `evaluar` y `regenerador`, y se ejecutaron las pruebas unitarias de 3A-4:

* **19 de 20 detectados.** M01–M15, M18–M20 por las pruebas unitarias; **M16** (el regenerador no comprueba las fuentes usadas) solo por la prueba de regeneración real (`REG`), que se omite en CI.
* **1 sobrevive:** **M17** (diferencias sin ordenar). Con la mutación, el resultado cambia entre procesos con distinta semilla de hash (2 resultados distintos en 6 semillas) y ninguna prueba lo detecta, porque el determinismo solo se prueba dentro de un proceso. El código real es determinista (1 resultado en 8 semillas).

**Pruebas débiles, vacías o mal nombradas:**

* `test_ambos_alterados_y_coherentes_entre_si_con_sha_recalculado` (REV): su primera aserción es casi tautológica. Ejecutado ese escenario, el resultado real es **`exacta`** (C2 pasa, regeneración completada): la prueba no afirma el estado real y su comentario («nunca exacta por accidente») induce a error.
* `test_la_regeneracion_falla_de_forma_visible_si_la_plantilla_no_sirve` (REG): su nombre promete un fallo de regeneración, pero comprueba que una plantilla distinta da `parcial` sin regenerar. No ejercita el fallo.
* `test_a02_la_comparacion_es_determinista_y_serializable` (CMP): determinismo solo intra-proceso.

**Escenarios sin prueba:** fallo de `build_*` o producción de un resultado incompleto **dentro del regenerador** (R-09); determinismo entre procesos de `comparar`.

**Cobertura en CI:** `test_procedencia_regeneracion.py` (10 pruebas), `test_procedencia_build.py` y la prueba de generación por API requieren plantillas reales y se omiten en CI; el único resguardo de `regenerador` en CI es `comparar` en Pyodide, que no lo ejecuta.

## 10. Defectos y riesgos

Clasificación: **D** = defecto real (comportamiento o documentación que contradice la realidad); **M** = mejora recomendable; **L** = limitación.

| ID | Tipo | Gravedad | Descripción | Corrección propuesta (no aplicada) |
|---|---|---|---|---|
| D-01 | D (documentación en código) | Baja | `provenance_compare.py` líneas 4 y 13 aún dicen que la comparación devuelve `no_evaluada`, contradiciendo el contrato actual (`estado = null`, `evaluacion`) | Reescribir ambos comentarios |
| D-02 | D (documentación) | Baja | Conteos erróneos en la descripción del PR y en `IMPLEMENTACION_3A4…`: `TestI1` son 10 (dicen 8) y `TestI3` son 17 (dicen 12); `TestI2` (12) y `TestI4` (10) sí coinciden | Corregir cifras |
| D-03 | D (documentación) | Baja | `IMPLEMENTACION_3A4…` cita «spec L-2» para el límite de integridad no criptográfica; L-2 de la spec trata de reproducir con código anterior. El límite está en `IMPLEMENTACION_3A3` §9 | Corregir la referencia |
| D-04 | D (documentación y comentario de prueba) | Baja | El comentario de `test_ambos_alterados_y_coherentes_…` afirma que la comparación contra las fuentes reales «delata el cambio», y `IMPLEMENTACION_3A4…` (I-1) dice que esa comparación y la regeneración «siguen siendo la defensa». Ambas valen para cambios de **contenido**; no para un reescrito coherente que solo cambia un nombre (resultado real: `exacta`) | Precisar el alcance de ambas afirmaciones |
| D-05 | D (prueba) | Baja | Prueba vacía/engañosa citada arriba | Reescribirla afirmando el estado real y su razón |
| D-06 | D (prueba) | Baja | Prueba mal nombrada citada arriba | Renombrarla o añadir la prueba que su nombre promete |
| D-07 | D (cobertura) | Baja (antes «Baja–media»; ver §14) | Falta la prueba de regenerador cuando `build_*` falla o produce un resultado incompleto (escenario pedido en R-09) | Añadir una prueba con un `build_*` que lance y otra con `procedencia` sin hash, ambas esperando `fallida` |
| D-08 | M | Baja | Sin prueba de determinismo entre procesos de `comparar` (mutación M17) | Prueba con subprocesos y semillas, como en 3A-2 |
| D-09 | L/M | Baja | La regeneración real y `regenerador` no se ejercitan en CI (sin plantillas) | Documentarlo como limitación o añadir una prueba con plantilla ficticia que cubra el camino de fallo |
| D-10 | M | Baja | `evaluar` exige que quien llama aporte la misma `ia`, `targets` y `context` que el reporte original; con `ia=None` frente a `{"usada": False}` el resultado es `parcial`. No está dicho en la documentación | Documentarlo |
| D-11 | L | Baja | AC-11 «se muestran»: sin interfaz (L-3); y la oferta de regenerar «con versiones actuales» no existe | Fase de interfaz posterior |
| D-12 | L | Informativa | La integridad no es criptográfica (registro, SHA y copia reescritos a la vez no se detectan) | Ya documentada; sin acción en 3A-4 |

**Ningún defecto es funcional ni bloqueante.** Una evidencia independiente de defectos técnicos pendientes (D-07, D-08, D-09) existe, pero **no sustituye** a las observaciones originales perdidas ni demuestra que las resuelva.

## 11. Observaciones técnicas originales no recuperables

* La sección 0 de la revisión correctiva dice que se identificaron «cuatro interpretaciones de la especificación y **dos observaciones técnicas**».
* Las observaciones **existieron** según esa sección; **no se recuperaron** (el DOCX, SHA-256 `7a7605b813da3df89d142b0d0363acb214bfd3491c5f58e49302edec3220da14`, termina en «…suficientemente completo para que el»; búsqueda exhaustiva sin otra copia).
* **No es posible verificar** si la implementación actual las resolvió.
* Es una **limitación documental de esta auditoría**. No se deducen de los hallazgos de §10.

## 12. Decisiones que requieren autorización

1. **Aplicar las correcciones** D-01 a D-07 (y opcionalmente D-08, D-09, D-10). Esta auditoría tenía prohibido modificar nada.
2. **Endpoint del servicio** para exponer la comparación: exigiría modificar `service.py` (protegido); no es necesario para 3A-4.
3. **Observaciones técnicas perdidas:** que el usuario las reponga, o declare expresamente que se prescinde de ellas.
4. **Confirmación de que `estado = null` es la representación aceptada** para «sin clasificar» (la autorización condicionada de §7 la cubre; se pide confirmación solo por trazabilidad).

## 13. Dictamen final

**B. REQUIERE CORRECCIONES.**

* No hay requisitos INCUMPLIDOS ni regresiones: suite 995/0/35, CI verde, baseline y hashes intactos, ningún archivo protegido tocado, las seis condiciones de la autorización sobre `comparacion/1` se cumplen y 19 de 20 defectos inyectados fueron detectados.
* Sí hay defectos **demostrables y de gravedad baja** (D-01 a D-07): comentarios obsoletos, cifras y una referencia normativa incorrectas, una afirmación de la documentación que se demostró falsa para un caso, dos pruebas engañosas y un escenario obligatorio sin prueba.
* El balance de la matriz es: 5 requisitos PARCIALMENTE CUMPLIDOS (N-11, N-17, R-05, R-09, R-12), 3 NO VERIFICABLES (I-06 por depender de la fusión, R-02 y R-13 por el texto perdido), 0 INCUMPLIDOS y ninguno marcado REQUIERE AUTORIZACIÓN (R-12 lo requeriría solo si se quisiera un endpoint).
* **Este dictamen no declara un cierre satisfactorio**: quedan asuntos no verificables y defectos demostrables que lo impiden.
* No se emite **A** porque existen esos defectos y porque el cumplimiento de las dos observaciones perdidas no puede demostrarse. No se emite **C** porque no hay ambigüedad normativa que impida juzgar el alcance verificable: lo que falta solo impide verificar las dos observaciones.
* Cuando se apliquen las correcciones y el usuario decida sobre las observaciones perdidas, el dictamen pasaría a **A** si ninguna de ellas revela un defecto adicional.

## 14. Nota de resolución posterior (D-01 a D-07)

> Esta nota se añade **después** del dictamen de las secciones 1 a 13, que se conservan tal como se emitieron (salvo la gravedad de D-07, unificada en Baja con la justificación de abajo). No es una recuperación del documento original perdido.

**Fecha:** 5 de noviembre de 2026 · **Autorización:** documento «PR #20 — Autorización de implementación integral D-01 a D-07» · **Commit con el código y las pruebas:** `d790877c472e712c50cf034ebac5b6c14b2f1c20` · **CI de ese commit:** run 46 (`Pruebas`, `pull_request`), job `unit`, **success**, 22:25 a 22:30 UTC. El commit documental que contiene esta nota tiene su propio CI, que se cita en la descripción del PR (una nota no puede contener el hash de su propio commit).

### 14.1 Gravedad y prioridad de D-07

Gravedad **Baja** para los siete defectos. Justificación: `evaluar` captura toda excepción del regenerador (`provenance_compare.py`, `except Exception`), las validaciones del regenerador lanzan ante salida incompleta o inválida, y no se encontró ninguna ruta de falso éxito (además `exacta` exige que el hash regenerado sea igual al registrado). El defecto era la **falta de cobertura** de esos caminos de fallo, no un riesgo funcional comprobado. **Prioridad:** la más alta entre D-01 y D-07 (cubre un escenario obligatorio, R-09, y la única parte de la orquestación de la regeneración que no se ejercitaba en CI).

### 14.2 Resolución por defecto

| ID | Estado | Corrección | Archivos | Prueba o evidencia |
|---|---|---|---|---|
| D-01 | Resuelto | Docstring de `provenance_compare.py`: `estado` = `exacta`/`parcial`/`no_reproducible` o `null`; `evaluacion` y `regeneracion` separados; `no_evaluada` solo como resultado de una comprobación. Sin cambios de lógica | `backend/app/provenance_compare.py` | Diff de solo-docstring; `grep no_evaluada` en ese archivo devuelve solo la frase del docstring que aclara que es un resultado de comprobación y el uso legítimo en el resultado vacío de error interno |
| D-02 | Resuelto | Conteos recalculados con `pytest --collect-only`: `TestI1` 13, `TestI2` 12, `TestI3` 17, `TestI4` 10 (52 en `test_procedencia_revision_3a4.py`); `test_procedencia_regenerador.py` 8; `test_procedencia_regeneracion.py` 10 | `IMPLEMENTACION_3A4_COMPARACION.md`, descripción del PR | `--collect-only` por archivo y clase |
| D-03 | Resuelto | «(spec L-2)» sustituido por la referencia a `IMPLEMENTACION_3A3_PROCEDENCIA.md` §9 y §11 (riesgo 3) | `IMPLEMENTACION_3A4_COMPARACION.md` | Lectura de ambos documentos |
| D-04 | Resuelto | Se distinguen cinco casos (contenido de origen, copia, registro sin recalcular SHA, `hash_resultado` de la fila distinto del manifiesto, reescritura coherente) y se declara que un cambio solo de nombre no se detecta; no se promete autenticidad criptográfica | `IMPLEMENTACION_3A4_COMPARACION.md`; comentario de la prueba | Resultados medidos reproducidos por las cuatro pruebas de D-05 |
| D-05 | Resuelto | La prueba casi tautológica se sustituye por cuatro con aserciones concretas: solo nombre ⇒ `exacta` (límite conocido, no detección); SHA de la fuente ⇒ `no_reproducible` (C3b, sin regenerar); `hash_resultado` ⇒ `parcial` (C7, anomalía de determinismo); fila ≠ manifiesto ⇒ `no_reproducible` (C2) | `tests/unit/test_procedencia_revision_3a4.py` | Cuatro mutaciones deliberadas (C3b ignorado, C7 sin comparar, hash de fila ignorado, nombre participando en la comparación): las cuatro rompen la prueba correspondiente |
| D-06 | Resuelto | Renombrada a `test_una_plantilla_distinta_es_parcial_y_no_regenera`, con docstring que declara lo que realmente verifica (C4 falla ⇒ `parcial`; la regeneración no se ejecuta) | `tests/regression/test_procedencia_regeneracion.py` | La prueba sigue pasando (con plantillas locales) |
| D-07 | Resuelto | Nuevo módulo que corre en CI: escenario A con el `build_aetops` real (bloqueo `ReportBlocked`/`TARGETS_MISSING`), escenario B (procedencia en error, sin `procedencia.json`, otras fuentes) y escenario C (regeneración válida con captura real, `exacta`/`completada`/`completada`), con contadores de invocación, comprobación de los tres campos y de limpieza de temporales | `tests/unit/test_procedencia_regenerador.py` (8 pruebas) | Seis mutaciones deliberadas (excepción convertida en éxito, sin validar el estado de la procedencia, sin validar las fuentes usadas, regenerador sin exigir metas, error de regeneración como «pasa», temporal sin limpiar): todas detectadas |

### 14.3 Resultados de validación

* Suite completa local (Pyodide activo, `REPORT_PYODIDE_REQUIRED=1`): **1006 aprobadas, 0 fallidas, 35 omitidas** (antes 995/0/35; +11: 3 por la división de D-05 y 8 del módulo nuevo). Las 35 omitidas son las mismas de `tests/golden`.
* `python -m pytest tests/unit tests/regression` (local, con plantillas): **1003 aprobadas, 0 omitidas, 0 fallidas**.
* Pruebas nuevas y modificadas, ejecutadas dos veces: 60 aprobadas en ambas ejecuciones (D-05 y D-07).
* `archivos_protegidos --check`: sin cambios · `capture_baseline --check`: 8 de 8 idéntico · `service.py` y `store.py`: sin diferencias respecto a `main`.

### 14.4 Limitaciones que permanecen

* Los escenarios B y C de D-07 **sustituyen la generación del PPTX**: no prueban el PPTX ni la narrativa real de un reporte. La regeneración con plantillas reales (`test_procedencia_regeneracion.py`, `test_procedencia_build.py`, generación por API) solo se valida en local; un CI verde no la demuestra.
* La rama GLP-1 del regenerador sigue sin cobertura propia.
* El escenario A usa el bloqueo de metas de AETOPS; no se verificó un bloqueo equivalente para GLP-1.
* D-08 a D-12 **no se atendieron** (fuera del alcance autorizado).
* La integridad sigue sin ser criptográfica (D-12).
* Las **dos observaciones técnicas originales** de la revisión correctiva siguen siendo **NO VERIFICABLES**: no se recuperaron y no se reconstruyeron ni se identifican con D-01 a D-07.

### 14.5 Efecto sobre la matriz de la sección 5

Sin reescribir sus filas: R-09 deja de tener el vacío que citaba (D-07 resuelto) y su estado pasa a CUMPLIDO; R-05 sigue PARCIALMENTE CUMPLIDO (el límite de integridad es real, ahora descrito con precisión); N-11, N-17 y R-12 no cambian; R-02, R-13 e I-06 siguen NO VERIFICABLES. El dictamen global de la sección 13 sigue siendo **B** hasta que el usuario revise esta nota y decida sobre las observaciones perdidas y sobre D-08 a D-12.
