# Informe de auditoría — Fase 2B: QA integral del motor de reglas

Documentos relacionados: `F2B_MATRIZ_PRUEBAS.md`, `F2B_FORMULAS.md`, `F2B_TRAZABILIDAD.md`, `evidencia_2b/`, `docs/MOTOR_REGLAS.md`, `F2A_INFORME.md`.
Fuente de verdad: `docs/fase1/ESPECIFICACION_FASE1_REPORT_INTELLIGENCE_FINAL.md`. Datos: **sintéticos** (machotes de `data/ejemplos` y contextos inventados); nada de lo aquí medido es evidencia operacional.

## DICTAMEN: APROBADA CON OBSERVACIONES

Las cinco reglas e IND-01 funcionan según la especificación, sus resultados son reproducibles y **no hay regresiones**. Se encontraron y corrigieron **7 defectos** del motor. La aprobación es con observaciones porque el criterio «pruebas obligatorias ejecutadas» solo se cumple para las pruebas **aplicables al alcance de las Fases 1–2**: 15 pruebas de la matriz (T-06 a T-09, T-10b, T-11, T-12, T-15 a T-19, S-02, V-01, V-02) **no se ejecutaron porque verifican funcionalidad que aún no existe** (procedencia, etiquetas de panel/anexo, QA del PPTX, anonimización, releases) o requieren archivos reales; figuran como *omitidas con motivo*, no como aprobadas. Detalle en §2 y §12.

| Criterio de aceptación de la 2B | Estado |
|---|---|
| Las cinco reglas están implementadas | **Cumple** |
| Las pruebas obligatorias han sido ejecutadas | **Parcial**: 12 de 27 ejecutadas y aprobadas; 15 omitidas con motivo (funcionalidad de fases posteriores o insumos del usuario) |
| Las pruebas aplicables pasaron | **Cumple**: 12/12, sin fallos |
| Las condicionales tienen estado justificado | **Cumple** (T-12, S-02, V-01, V-02 con motivo) |
| Sin regresiones en las suites existentes | **Cumple**: 181 originales aprobadas sin editar; línea base idéntica; 74 archivos protegidos sin cambios |
| Fórmulas consistentes con la Fase 1 | **Cumple** (F-06 faltaba y se añadió) |
| Resultados reproducibles | **Cumple** (misma salida en dos procesos con semillas de hash distintas; evidencia JSON determinista) |
| Aplicabilidad GLP-1 / AETOPS correcta | **Cumple** (T-22) |
| Fuentes de compras diferenciadas | **Cumple** (T-21) |
| Limitaciones comunicadas | **Cumple** (unidad no declarada, > 100 %, no verificable con `faltante`, no validada con datos reales) |
| Sin cambios no autorizados en reportes/plantillas | **Cumple** (foto del deck idéntica; plantillas y `deck/` protegidos) |

## 1. Auditoría de la implementación de la Fase 2A

| # | Verificación | Resultado | Evidencia |
|---|---|---|---|
| 1 | Archivos de la 2A revisados | 6 módulos nuevos en `validator/`, `config/reglas.json` v1.1.0 y su validador, documentación y 47 pruebas | `F2A_INFORME.md` §5; revisión de código |
| 2 | Cinco reglas implementadas | Sí: `R-REL-PAC-PED`, `R-CUADRE-DIM`, `R-CONC-COMPRAS`, `R-DENOM`, `R-COBERTURA-ATC` (+ IND-01) | `motor.catalogo()`; `test_el_catalogo_de_reglas_es_valido…` |
| 3 | Cada regla corresponde a su definición | Sí, con **7 desviaciones corregidas** (D-2B-01 a D-2B-07, §12) | pruebas T-01…T-05 |
| 4 | Configuración versionada | Sí: `reglas.json` 1.1.0 y cada regla `1.0.0`; `validacion_registro.json` sin cambios (versiones de regla `null` hasta aprobar la validación) | `config.versiones()` |
| 5 | Funciones que consumen los resultados | `motor.a_hallazgos()` y `Resultado.a_hallazgo()`; **ningún servicio las invoca todavía** (búsqueda en `web/`, `build.py`, `pipeline.py`: sin referencias) | `test_t14_la_ia_no_puede_modificar_reglas…` |
| 6 | Las reglas no modifican los datos originales | Comprobado: contexto, líneas y totales idénticos antes y después | `test_t01_la_regla_no_modifica…`, `test_t02_no_elimina_datos…`, `test_ejecutar_no_modifica_el_contexto…` |
| 7 | Sin fórmulas duplicadas que se contradigan | Los criterios de pedido/monto replican los de `raw/glp1.build`; **coinciden exactamente** con el motor existente (pedidos, monto, ticket, compras y carritos en GLP-1; pedidos y monto en AETOPS) | `test_formulas_las_cifras_del_motor…` |
| 8 | Compatibilidad con servicios anteriores | `severity` heredado, nunca `block`; `has_blockers()` sin cambios; 74 archivos protegidos idénticos; suite completa sin regresión | `test_calidad_ninguna_advertencia_bloquea…`, T-13 |

## 2. Matriz de pruebas ejecutadas
Completa en `F2B_MATRIZ_PRUEBAS.md` (ID, regla, entrada, esperado, obtenido, estado, evidencia, observaciones). Generada automáticamente desde el informe JUnit; **una prueba sin ejecutar no puede salir como aprobada**.

| Estado | Pruebas |
|---|---|
| **Aprobadas (12)** | T-01, T-02, T-03, T-04, T-05, T-10, T-13, T-14, T-20, T-21, T-22, S-01 |
| **Omitidas con motivo (15)** | T-06 (falta `validator/catalogo.py`), T-07 y T-08 (procedencia, Fase 3), T-09 y T-10b (etiquetas/aclaraciones en panel y anexo, Fase 4; **las fórmulas y cifras de E1/E2 se verificaron sin cambios** por la línea base), T-11 (QA del PPTX, Fase 5), T-12 (condicional: `soffice` y `pdftoppm` están disponibles, pero `qa/visual.py` no existe), T-15 (anonimización no existe), T-16 (estampado de versión, Fase 3), T-17 (mapeo no consumido), T-18 (etiquetas en anexo/manifiesto), T-19 (no hay dos configuraciones —flags— que comparar), S-02 (35 golden: sin `REPORT_FIXTURES_DIR` y archivos reales), V-01 (sin extractos reales, A-2), V-02 (A-5 no autorizada) |
| Fallidas | **0** |

## 3. Resultados por regla
| Regla | Escenarios | Pruebas | Resultado |
|---|---|---|---|
| R-REL-PAC-PED | 1 pedido/1 paciente; paciente con varios pedidos; pedido con varias líneas; pedido sin paciente; pedido con 2 pacientes (m = 1 y 2); fechas contradictorias dentro y fuera del periodo; fecha ilegible; duplicados exactos y líneas repetidas; ids vacíos; periodo sin pedidos; AETOPS; `estado` no es estatus; inmutabilidad; ejemplo de la especificación (C2 = 1, E = 5, A = 3, B = 1, C = 1, pacientes 2, cobertura 60 %, razón 1,5) | T-01: 18 aprobadas | **Cumple**. Defecto F-06 corregido |
| R-CUADRE-DIM | Dimensión exclusiva; valores compartidos (SKU); paciente en varios canales y sucursales; pedido con varias categorías (catálogo); 8 combinaciones declaradas; «Sin asignar» virtual; tolerancia; columna inexistente; periodo vacío; sin eliminar datos | T-02: 25 aprobadas | **Cumple**. Defecto D-2B-01 corregido |
| R-CONC-COMPRAS | Brecha −30 %…+30 % (ambos sentidos, en el umbral exacto del 20 %); trimestre con tráfico incompleto; sin hoja de tráfico; GLP-1 y AETOPS; umbral configurable; pedidos 0 | T-03: 20 aprobadas (9 casos de umbral en ambos sentidos y los de periodos, faltantes y aplicabilidad) | **Cumple**. Fuentes separadas |
| R-DENOM | Denominador válido, cero, negativo, vacío; numerador ausente o negativo; periodos, granularidades y fuentes distintos; regla sobre contexto; carritos = 0 | T-04: 13 aprobadas | **Cumple**. Nunca un 0 % engañoso |
| R-COBERTURA-ATC / IND-01 | < 100 %, = 100 %, > 100 % (120 % conservado); carritos 0 o faltantes; unidad no declarada; dos fuentes; periodos no coincidentes; desgloses de tráfico que no son el total; filtro de canal; AETOPS | T-05: 12 y T-10: 10 aprobadas | **Cumple**: sin complemento, sin «abandono», sin causa inventada, E2 separado |
| Fuentes diferenciadas | Una fuente faltante no se sustituye por la otra; nada se suma | T-21: 3 aprobadas | **Cumple** |

(Los recuentos por prueba salen de `F2B_MATRIZ_PRUEBAS.md`; las pruebas de la 2A que coinciden con un mismo T-xx se suman.)

## 4. Validación de fórmulas
Auditoría completa en `F2B_FORMULAS.md`: F-01 a F-12 con numerador, denominador, fuente, periodo, granularidad, condiciones, faltantes, división inválida, precisión, redondeo y consistencia. Todo se calcula en `Decimal`; el valor guardado no se redondea y solo el texto muestra 2 decimales. **F-09, F-10 y F-12 (E1, E2, derivación de `carritos_abandonados`) no se modificaron** (archivos protegidos y líneas verificadas por prueba). Hallazgos: F-06 faltaba (corregido); la réplica de criterios de pedido es una duplicación controlada (coincide exactamente con el motor existente).

## 5. Resultados por unidad (machotes sintéticos; `evidencia_2b/resultados_machotes.json`)

| Unidad / periodo | valid | warning | error | not_verifiable | not_applicable | Cifras clave |
|---|---|---|---|---|---|---|
| GLP-1 mensual sept-2026 | 7 | 7 | 0 | 6 | 0 | 2 356 pedidos del sistema de ventas; 2 643 compras GA4 (+12,18 %); relaciones 12,48 % y 14,00 % |
| GLP-1 trimestral Q3-2026 | 7 | 7 | 0 | 6 | 0 | 6 791 pedidos; brecha +16,07 %; relaciones 12,06 % y 14,00 % |
| AETOPS mensual sept-2026 | 3 | 11 | 0 | 2 | 2 | 1 436 pedidos; sin reglas de tráfico |
| AETOPS trimestral Q3-2026 | 3 | 11 | 0 | 2 | 2 | ídem |

- **GLP-1** reconoce `ventas`, `catalogo`, `trafico` y `negados`; **AETOPS** reconoce `ventas`, `catalogo` y `negados` y **no intenta** ejecutar nada que requiera `trafico` (comprobado haciendo fallar `operandos._trafico` si se llamara: `R-CONC-COMPRAS` y `R-COBERTURA-ATC` devuelven `not_applicable`; `R-DENOM` solo evalúa el ticket).
- Los encabezados de los dos machotes coinciden exactamente con los documentados y el catálogo de reglas y de definiciones solo cita columnas existentes (T-22).
- Todo resultado lleva `not_validated_with_real_data`; los `warning` de GLP-1 sobre IND-01 son informativos (unidad de carritos no declarada); los `warning` de R-CUADRE-DIM señalan dimensiones no exclusivas observadas en los datos sintéticos.

## 6. Comparativo de línea base
| Referencia | Antes (línea base de Fase 1: `6e1104d`) | Después (Fase 2B) | Diferencia |
|---|---|---|---|
| `tests/unit` | 181 aprobadas | 369 aprobadas | +188 pruebas nuevas (Fase 1: 48, Fase 2A: 47, Fase 2B: 93); las 181 originales siguen aprobadas, sin editar |
| `tests/regression` | — (creada en Fase 1) | 15 aprobadas | — |
| `tests/golden` | 35 omitidas | 35 omitidas | Ninguna (faltan archivos reales) |
| Foto del motor, hallazgos, narrativa y huellas del deck (4 escenarios) | congelada | **idéntica** | 0 diferencias |
| Archivos protegidos (74) | congelados | **sin cambios** | 0 |
| Archivos modificados respecto a `main` previo a Fase 1 | — | `.github/workflows/tests.yml`, `backend/app/models.py` (solo `Finding`), `docs/ARQUITECTURA.md`, `docs/CONTRATO_DATOS.md` | todos autorizados o documentales |
| Ejecución completa (unit + regression + golden) | — | 384 aprobadas, 35 omitidas, 0 fallidas, 651 s | — |
| Python 3.12 (CI) | — | 182 aprobadas (QA, motor, configuración, compatibilidad, protegidos) | — |

Comparación reproducible: `python tools/capture_baseline.py --check` y `python tools/archivos_protegidos.py --check` (logs en `evidencia_2b/`).

## 7. Informe de regresiones
**No se encontró ninguna regresión.** Los cálculos existentes, las cifras de referencia, las láminas (huellas del PPTX generado), los importadores (`importer/`, `raw/`), las plantillas, los escenarios heredados (25 %, 10 %, 20 %), `severity` y las rutas de ejecución (`pipeline.py`, `build.py`, `cli.py`, `web/`) coinciden con el estado anterior. Una única prueba de la 2A se **actualizó** tras corregir el defecto D-2B-04 (el estado de verificación de los avisos aritméticos pasó de «supuesto» a «verificado», como exige la especificación); no es una prueba del conjunto original y el cambio está justificado en §12. Las 181 pruebas originales no se editaron.

## 8. Calidad del motor
| Verificación | Resultado |
|---|---|
| Excepciones | Un fallo interno de una regla se muestra como `error`/`fallo_interno` sin detener a las demás (probado); archivo inexistente o ilegible ⇒ `ErrorLectura` con mensaje comprensible (D-2B-07) |
| Datos incompletos / columnas faltantes | `not_verifiable` con `faltante` explícito; sin crash |
| Columnas adicionales | No cambian los resultados (comparación de salida completa) |
| Tipos incorrectos, nulos, duplicados | No rompen; las líneas inválidas no cuentan como pedidos del sistema de ventas; duplicados se informan sin eliminar |
| Archivos de ejemplo con defectos (`*_con_defectos.xlsx`) | Se ejecutan sin error; el motor señala el pedido sin paciente o sin `id_pedido` |
| Rendimiento | Contexto de un libro grande: 3,6–8,0 s; reglas: 0,25–1,1 s; **200 000 líneas sintéticas: 6,95 s** (límite de la prueba: 60 s) |
| Consistencia de mensajes | Todas las plantillas están bien formadas, sin «abandono», y cada clave usada en el código existe en la configuración |
| Reproducibilidad | Salida idéntica en dos procesos con `PYTHONHASHSEED` distinto; `resultados_machotes.json` idéntico en dos generaciones |
| No bloqueo | En ningún escenario se emite `block`; `has_blockers()` es falso |

## 9. Privacidad e IA
Comprobado por pruebas (T-14): el motor y la configuración no importan red, procesos ni escriben archivos; los datos permanecen en memoria del navegador/proceso; `config` no tiene funciones de escritura. La IA (Cohere, opt-in) **no** puede modificar reglas ni cifras: `web/service.py` no referencia el motor ni `config.cargar`, el motor no referencia la IA, y `verify_rewrite` rechaza una reescritura de un resultado que cambie una cifra o añada una explicación causal (el texto determinista se conserva). Todo resultado lleva `regla_id`, `regla_version` y evidencia con su fuente. No se hizo ninguna llamada real a la IA ni se transmitió ningún dato. **Observación:** la evidencia incluye muestras de `id_pedido`/`id_paciente` (anónimos según el contrato, máx. 3–5); si algún día se muestran o exportan fuera del navegador, hay que revisarlo.

## 10. Trazabilidad
Matriz actualizada en `F2B_TRAZABILIDAD.md` (Requerimiento → Regla → Fórmula/indicador → AC → Prueba → Evidencia, con estado). Resumen: RQ-01, 02, 03, 04, 05 (motor), 22, 23, 28 (motor), 29, 31 y 32 **cumplidos con evidencia**; los demás están parciales o pendientes por pertenecer a fases posteriores. Ningún requisito se marca cumplido sin prueba ejecutada.

## 11. Inventario de archivos de la Fase 2B
| Archivo | Acción | Motivo | Riesgo |
|---|---|---|---|
| `backend/app/validator/motor.py` | Modificado | `verificacion` en `Resultado`; ids inexistentes rechazados; `numerador_con_signo` | Bajo |
| `backend/app/validator/normalizar.py` | Modificado | `ErrorLectura` para archivos inexistentes o ilegibles | Bajo |
| `backend/app/validator/operandos.py` | Modificado | Faltante (no cero) sin pedidos válidos; brecha segura con `None`; numerador con signo | Bajo |
| `backend/app/validator/rules_datos.py` | Modificado | Análisis por entidad (D-2B-01); F-06 y universo del motor en la evidencia; `verificado` en observaciones | Bajo |
| `backend/app/validator/rules_conc.py` | Modificado | `verificado` en el aviso de conciliación; numerador con signo | Bajo |
| `tests/qa_util.py` | Creado | Constructores de contextos sintéticos | Bajo |
| `tests/unit/test_qa2b_reglas.py` | Creado | T-01…T-05, T-10, T-21 (68 pruebas) | Bajo |
| `tests/unit/test_qa2b_calidad.py` | Creado | Fórmulas, unidades (T-22), calidad, privacidad/IA (T-14), T-20 (25 pruebas) | Bajo |
| `tests/unit/test_motor_reglas.py` | Modificado | Una aserción de la 2A ajustada por D-2B-04 | Bajo |
| `tests/regression/test_archivos_protegidos.py`, `tests/regression/protegidos.json` | Creados | No regresión estructural (74 archivos) | Bajo |
| `tools/archivos_protegidos.py`, `tools/evidencia_reglas.py`, `tools/matriz_pruebas_fase1.py` | Creados | Herramientas reproducibles de evidencia | Bajo |
| `docs/MOTOR_REGLAS.md` | Modificado | Ajustes de la 2B | Bajo |
| `docs/fase1/implementacion/F2B_*.md`, `evidencia_2b/*` | Creados | Informe, matriz, fórmulas, trazabilidad y evidencias | Bajo |

No se modificaron: `pipeline.py`, `build.py`, `raw/*`, `importer/*`, `narrative/*`, `deck/*`, `qa/*`, `web/*`, `history/*`, `models.py`, plantillas, perfiles, workflows, fórmulas ni cifras.

## 12. Defectos
### Corregidos
| ID | Descripción | Severidad | Regla | Evidencia | Estado / solución |
|---|---|---|---|---|---|
| D-2B-01 | `R-CUADRE-DIM` descartaba del análisis de pedidos las líneas sin `id_paciente` | Media | R-CUADRE-DIM | `test_t02_una_linea_sin_paciente…` | **Corregido**: cada entidad usa sus propias líneas; el dato no se elimina |
| D-2B-02 | `R-DENOM` fallaba con `TypeError` (visible como `fallo_interno`) al calcular la brecha con pedidos faltantes | Media | R-DENOM | `test_calidad_hoja_ausente_tipos_incorrectos…` | **Corregido** |
| D-2B-03 | Sin pedidos válidos en el periodo, «pedidos del sistema de ventas» valía 0 y habría mostrado una relación 0 % engañosa | Alta | R-COBERTURA-ATC, R-DENOM, R-CONC | `test_t05_carritos_cero_o_faltantes…`, `test_t21_*` | **Corregido**: es un faltante |
| D-2B-04 | Avisos aritméticos (conciliación, duplicados, solapamiento observado) salían como «supuesto» en lugar de «verificado» | Baja | R-CONC, R-REL, R-CUADRE | `test_a_hallazgos_usa_severity_heredado…` | **Corregido** (campo `verificacion`); prueba de la 2A ajustada |
| D-2B-05 | `motor.ejecutar(ids=[…])` ignoraba en silencio ids de regla inexistentes | Baja | motor | prueba de calidad | **Corregido**: `ValueError` |
| D-2B-06 | Faltaba F-06 (`tasa_no_asignables`) y el universo de pedidos del motor en la evidencia de R-REL | Baja | R-REL-PAC-PED | `test_formulas_f04_f05_f06_f07…` | **Corregido** |
| D-2B-07 | Archivo inexistente o corrupto lanzaba una excepción técnica (`BadZipFile`, etc.) sin explicación | Baja | lectura | `test_calidad_archivo_inexistente_o_corrupto…` | **Corregido**: `ErrorLectura` |

### Pendientes / observaciones
| ID | Descripción | Severidad | Regla | Estado |
|---|---|---|---|---|
| O-2B-01 | Dos universos de pedidos conviven: el de R-REL-PAC-PED (todo `id_pedido` con fecha única) y el de «pedidos del sistema de ventas» (criterios del motor). Difieren con datos defectuosos (p. ej. 2 358 frente a 2 356). Documentado y expuesto en la evidencia (`pedidos_universo_motor`) | Baja | R-REL / R-CONC | Abierta (documental) |
| O-2B-02 | Réplica de los criterios de pedido de `raw/glp1.build` (duplicación controlada); si el motor existente cambia, hay que actualizar ambos. Lo vigila el manifiesto de archivos protegidos | Baja | operandos | Abierta (mantenimiento) |
| O-2B-03 | Formato numérico de los mensajes (`2,356`, `12.48 %`) distinto del de la especificación (coma decimal); sin efecto en valores | Baja | todas | Abierta (presentación) |
| O-2B-04 | El motor no se ejecutó en Pyodide (navegador) | Media | todas | Abierta |
| O-2B-05 | 15 pruebas de la matriz omitidas por funcionalidad futura o insumos del usuario (§2) | Informativa | — | Abierta por diseño |
| O-2B-06 | Con los machotes (unidad de carritos no declarada) IND-01 nunca llega a `valid`; hace falta decidir si se declara la unidad | Baja | IND-01 | Decisión del usuario (AMB-2) |
| O-2B-07 | R-CUADRE-DIM emite muchos `not_verifiable` mientras no se declaren propiedades (ruido para una futura interfaz) | Baja | R-CUADRE-DIM | Decisión de diseño |
| O-2B-08 | Motor sin cablear: los flags siguen desactivados; `gravedad` en `null`; AMB-1, 5, 7 y 9 sin confirmar | Media | todas | Pendiente de autorización |
| O-2B-09 | Sin validación con datos reales (A-2): todos los resultados llevan `not_validated_with_real_data` | Esperada | todas | Pendiente (usuario) |
| O-2B-10 | La rama contiene Fase 1, 2A y 2B bajo el mismo PR #11 (abierto) | Media (proceso) | — | Pendiente de decisión |

## 13. Evidencias de ejecución (`docs/fase1/implementacion/evidencia_2b/`)
`junit_unit_regression_golden_2b.xml` y `pytest_unit_regression_golden_2b.log` (384 aprobadas, 35 omitidas, 0 fallidas); `linea_base_check.log` (idéntico); `archivos_protegidos_check.log` (sin cambios); `fixtures_check.log` (idénticas); `pytest_py312_2b.log` (182 aprobadas en Python 3.12); `resultados_machotes.json` (salida determinista del motor sobre los 4 escenarios).

Reproducir:
```bash
python -m pytest tests/unit tests/regression tests/golden -q --junitxml=junit.xml
python tools/matriz_pruebas_fase1.py junit.xml --salida docs/fase1/implementacion/F2B_MATRIZ_PRUEBAS.md
python tools/capture_baseline.py --check
python tools/archivos_protegidos.py --check
python tools/evidencia_reglas.py
```

## 14. Actualización posterior al dictamen: decisiones delegadas
El usuario delegó la resolución de las observaciones abiertas; el registro completo está en `DECISIONES_DELEGADAS.md`.

| Observación | Estado actual |
|---|---|
| O-2B-04 Pyodide | **Cerrada con evidencia**: resultados idénticos a CPython en los 4 escenarios (Pyodide 0.27.7, Python 3.12.7, ejecutado en Node; salvedad: no en el Web Worker del navegador) |
| O-2B-06 unidad de carritos | **Decidida**: se mantiene «unidad no declarada» (es un hecho del usuario) |
| O-2B-08 cableado, `gravedad`, AMB-1/5/7/9 | **Decididas**: no se cablea todavía; `gravedad` en `null`; AMB-1, 5, 7 y 9 cerradas sin cambios de código |
| O-2B-10 PR | **Decidida**: se mantiene un solo PR #11 con descripción actualizada; sin fusionar |
| O-2B-01, 02, 03, 07 | Aceptadas como observaciones documentales (DD-10, DD-11) |
| O-2B-05, 09 | Siguen abiertas por diseño (funcionalidad de fases posteriores; sin datos reales, A-2) |

El dictamen **APROBADA CON OBSERVACIONES** se mantiene: las pruebas T-06 a T-19 siguen omitidas porque verifican funcionalidad que no existe todavía.

## 15. Cierre
**Dictamen: APROBADA CON OBSERVACIONES.** No se avanza a la Fase 3. Para continuar se espera tu revisión y la autorización expresa para la Fase 3.
