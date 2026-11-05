# Matriz de trazabilidad actualizada — Fase 2B

Cadena: **Requerimiento → Regla → Fórmula/Indicador → Criterio de aceptación → Prueba → Evidencia**. Basada en la matriz de la especificación final (§14), con el estado de cumplimiento comprobado al cierre de la Fase 2B. Un requisito solo figura como cumplido si existe una prueba ejecutada y aprobada que lo respalda (ver `F2B_MATRIZ_PRUEBAS.md` y `evidencia_2b/`). «Parcial» o «No cumplido» no son fallos: indican funcionalidad de fases posteriores.

## 1. Requerimientos

| Req. | Requerimiento | Regla | Fórmula / indicador | Criterios | Pruebas | Estado | Evidencia |
|---|---|---|---|---|---|---|---|
| RQ-01 | Regla `R-REL-PAC-PED` (§3.3) | R-REL-PAC-PED | F-04, F-05, F-06, F-07 | AC-05 | T-01 | **Cumplido (2B)** | T-01: 18 pruebas aprobadas |
| RQ-02 | Regla `R-CUADRE-DIM` (§3.3) | R-CUADRE-DIM | F-08 | AC-06 | T-02 | **Cumplido (2B)** | T-02: 25 pruebas aprobadas |
| RQ-03 | Regla `R-CONC-COMPRAS` con fuentes diferenciadas | R-CONC-COMPRAS | F-03 | AC-07, AC-29 | T-03, T-21 | **Cumplido (2B)** | T-03 y T-21 aprobadas |
| RQ-04 | Regla `R-DENOM` | R-DENOM | F-01, F-02, F-03, F-11 (razones) | AC-08, AC-04 | T-04 | **Cumplido (2B)** | T-04: 13 pruebas aprobadas |
| RQ-05 | Regla `R-COBERTURA-ATC` (comparabilidad de carritos agregados y pedidos) | R-COBERTURA-ATC | IND-01 (F-01, F-02) | AC-09, AC-31, AC-30, AC-04 | T-05 | **Cumplido en el motor (2B); panel/anexo pendientes (Fase 4)** | T-05: 12 pruebas aprobadas |
| RQ-06 | Catálogo de definiciones versionado | — | — | AC-10 | T-07 | **Parcial** | Catálogo creado y validado (Fase 1); ninguna regla lo lee todavía; T-07 omitida |
| RQ-07 | Hallazgo con nomenclatura explícita | — | — | AC-03 | T-06 | **Parcial** | 17 pruebas de compatibilidad (Fase 1) aprobadas; falta validator/catalogo.py; T-06 omitida |
| RQ-08 | Migración compatible de `severity` | — | — | AC-02 | T-06, T-13 | **Cumplido (alcance actual)** | Compatibilidad de severity y T-13 aprobadas; la API no usa los campos nuevos |
| RQ-09 | «No verificable» con `faltante` | R-DENOM, R-COBERTURA-ATC | — | AC-04 | T-06 | **Parcial** | `not_verifiable` exige `faltante` (probado); falta el catálogo por id (T-06 omitida) |
| RQ-10 | Manifiesto de procedencia | — | — | AC-10 | T-07, T-16 | **No cumplido (Fase 3)** | T-07 y T-16 omitidas |
| RQ-11 | Reproducibilidad y sus estados | — | — | AC-11, AC-12 | T-08 | **No cumplido (Fase 3)** | T-08 omitida |
| RQ-12 | Releases etiquetadas | — | — | AC-28, AC-10 | T-16, V-02 | **No cumplido (A-5 pendiente)** | T-16 y V-02 omitidas |
| RQ-13 | QA estructural del PPTX exportado | — | — | AC-14 | T-11 | **No cumplido (Fase 5)** | T-11 omitida |
| RQ-14 | QA visual con render real | — | — | AC-16 | T-12 | **No cumplido (Fase 5)** | T-12 omitida |
| RQ-15 | Límites del QA declarados en la interfaz | — | — | AC-15 | T-11 | **No cumplido (Fase 5)** | T-11 omitida |
| RQ-16 | Escenario E1 (negados) con valor heredado | — | F-09 | AC-13 | T-09 | **Parcial** | Fórmula/cifra sin cambios (línea base, archivo protegido); etiquetas pendientes; T-09 omitida |
| RQ-17 | Escenario E2 heredado, diferenciado del indicador agregado | — | F-10, F-12 | AC-13 | T-10b | **Parcial** | Fórmula/lámina sin cambios; aclaración en panel/anexo pendiente; T-10b omitida |
| RQ-18 | Etiquetas de supuesto heredado, de «ilustrativo» y de métrica heredada | — | — | AC-13 | T-09, T-10b, T-11 | **Parcial** | Cada resultado lleva `estado_validacion`; rótulos en panel/anexo pendientes |
| RQ-19 | Anexo de calidad de datos | — | — | AC-14 | T-11 | **No cumplido (Fase 5)** | T-11 omitida |
| RQ-20 | Procedimiento y herramienta de anonimización | — | — | AC-17 | T-15 | **No cumplido** | T-15 omitida |
| RQ-21 | Validación con datos reales (modo informe) | Todas las R-* | — | AC-18 | V-01 | **No cumplido (A-2 pendiente)** | V-01 omitida |
| RQ-22 | No-regresión | — | — | AC-01 | T-13 | **Cumplido (alcance actual)** | T-13: 15 pruebas aprobadas; 74 archivos protegidos sin cambios |
| RQ-23 | La IA no altera cifras ni sustituye cálculos | — | — | AC-27 | T-14 | **Cumplido (alcance actual)** | T-14: 4 pruebas aprobadas (sin llamadas reales a la IA) |
| RQ-24 | Flags de reversión | — | — | AC-21 | T-13 | **Parcial** | Flags definidos y desactivados; ninguno gobierna comportamiento; T-13 solo trivial |
| RQ-25 | Rendimiento | — | — | AC-20 | T-19 | **Parcial** | Medición del motor (200 000 líneas: 6,95 s); T-19 omitida (no hay dos configuraciones) |
| RQ-26 | Validación sintética vs operacional diferenciadas y rotuladas | Todas las R-* | — | AC-24 | T-18 | **Parcial** | Etiqueta `not_validated_with_real_data` en cada resultado; T-18 omitida |
| RQ-27 | Incorporar extractos reales después sin rehacer la arquitectura | Todas las R-* | — | AC-25, AC-23 | T-17 | **No cumplido** | T-17 omitida |
| RQ-28 | Indicador IND-01 «Relación pedidos/carritos» (metodología agregada, §8.2) | R-COBERTURA-ATC | IND-01 (F-01, F-02) | AC-22, AC-23, AC-30, AC-29 | T-10 | **Cumplido en el motor (2B); panel/anexo pendientes** | T-10 aprobada |
| RQ-29 | Escenarios de prueba reproducibles y sin datos reales | — | — | AC-26 | T-20 | **Cumplido (modelo y catálogo)** | T-20: 10 pruebas aprobadas |
| RQ-30 | Suites existentes sin regresión | — | — | AC-19 | S-01, S-02 | **Cumplido en S-01; S-02 omitida** | S-01: 369 aprobadas; S-02: 35 omitidas (sin REPORT_FIXTURES_DIR) |
| RQ-31 | Diferenciación de fuentes de pedidos: sistema de ventas vs GA4 | R-CONC-COMPRAS, R-COBERTURA-ATC | F-01, F-02, F-03 | AC-29, AC-07 | T-21, T-03, T-10 | **Cumplido (2B)** | T-21: 3, T-03 y T-10 aprobadas |
| RQ-32 | Aplicabilidad por unidad y fidelidad a los machotes | Todas las R-* | — | AC-32 | T-22 | **Cumplido (2B)** | T-22: 5 pruebas aprobadas |

## 2. Criterios de aceptación

| AC | Criterio (resumen en la especificación §12) | Estado al cierre de la 2B |
|---|---|---|
| AC-01 | **0 diferencias** en valores numéricos respecto a la línea base, salvo las listadas en `CAMBIOS_JUSTIFICADOS.md` con autorización | Cumplido (alcance actual) |
| AC-02 | 100 % de los `id` de hallazgo existentes conservan el mismo `severity`; la UI y las pruebas previas pasan sin edición | Cumplido (17 pruebas de Fase 1 + línea base) |
| AC-03 | 100 % de los hallazgos nuevos y migrados tienen `tipo`, `gravedad`, `estado_verificacion`, `efecto_generacion`; los nuevos además `regla_id`… | Parcial (campos poblados por las reglas; catálogo por id pendiente) |
| AC-04 | Todo hallazgo con `estado_verificacion = no_verificable` trae `faltante` no vacío; **0** valores inventados o ceros implícitos | Cumplido para las reglas del motor |
| AC-05 | `R-REL-PAC-PED`: ≥ 12 casos (T-01) pasan con los valores exactos de §3.3 (ejemplo de 6 pedidos con `m=1` y `m=2`); opera sobre `id_pedido` e… | Cumplido |
| AC-06 | `R-CUADRE-DIM`: ≥ 16 casos (T-02) pasan, incluidas las **cuatro combinaciones** exclusiva/exhaustiva con un caso que cumple y uno que incump… | Cumplido |
| AC-07 | `R-CONC-COMPRAS`: ≥ 8 casos (T-03) pasan; cada lado identifica su fuente («sistema de ventas» / «GA4»); ninguna fuente sustituye ni se suma … | Cumplido |
| AC-08 | `R-DENOM`: ≥ 3 casos (T-04) pasan; **0** ratios con denominador cero mostrados como 0 % | Cumplido |
| AC-09 | `R-COBERTURA-ATC`: ≥ 12 casos (T-05) pasan con los tres estados de §8.2; periodos distintos ⇒ sin variaciones y con limitación; universos, f… | Cumplido |
| AC-10 | Manifiesto con los 9 campos de §5.1 en el 100 % de los reportes nuevos; `hash_resultado` idéntico en dos corridas con las mismas entradas; v… | No cumplido (Fase 3) |
| AC-11 | Los tres estados de §5.3 se producen y se muestran correctamente; **0** regeneraciones silenciosas con versiones distintas | No cumplido (Fase 3) |
| AC-12 | Los reportes previos a Fase 1 se muestran como `no_reproducible (legado)` | No cumplido (Fase 3) |
| AC-13 | Escenarios E1 y E2: solo los valores heredados (25 % y 10 %) visibles, con fórmula, variable y la etiqueta «Supuesto heredado, no validado»;… | Parcial (fórmulas y cifras sin cambios; etiquetas pendientes) |
| AC-14 | QA estructural detecta 100 % de los defectos inyectados (token, duplicado, fuente mínima, unidad sin denominador, fórmula alterada, cifra no… | No cumplido (Fase 5) |
| AC-15 | La interfaz nunca presenta el QA estructural como «revisión visual» ni declara «verificado visualmente» sin render | No cumplido (Fase 5) |
| AC-16 | *(Condicional)* QA visual produce PNG por diapositiva y un informe de hallazgos con datos sintéticos; no se ejecuta en Actions con datos rea… | No cumplido (Fase 5; condicional) |
| AC-17 | `tools/anonimizar_extracto.py` conserva conteos distintos y relaciones y no deja campos prohibidos | No cumplido |
| AC-18 | *(Condicional)* Informe de validación con datos reales entregado **cuando existan los extractos** y con tu confirmación; mientras no existan… | No cumplido (condicional; sin extractos) |
| AC-19 | Inventario de pruebas (§11.2) completo y consistente: las **22 pruebas obligatorias nuevas** (T-01 a T-11, T-10b y T-13 a T-22) y la suite u… | Parcial (inventario ejecutado: 12 aprobadas, 15 omitidas con motivo) |
| AC-20 | Tiempo de generación en el navegador (mediana de 5 corridas con los ejemplos sintéticos) no aumenta más de 15 % frente a la línea base (flag… | No cumplido (no aplica sin cableado) |
| AC-21 | Con los flags de Fase 1 desactivados, la salida es idéntica a la línea base | Cumplido de forma trivial (flags sin efecto) |
| AC-22 | Relación pedidos/carritos: `(pedidos / carritos) × 100` exacta en `Decimal` (ejemplo 250/1 000 ⇒ 25 %); se muestran volumen de carritos (con… | Cumplido en el motor |
| AC-23 | La metodología agregada no exige identificadores: la relación se calcula con fixtures que **no contienen** ninguna columna de ID de carrito,… | Cumplido |
| AC-24 | Toda regla con validación operacional no confirmada muestra «No validada con datos reales»; **0** reglas presentadas como confirmadas sin re… | Parcial (etiqueta en cada resultado) |
| AC-25 | Un extracto sintético con otros nombres de columna se incorpora solo con cambios de configuración; **0** cambios de código | No cumplido |
| AC-26 | Todas las fixtures de `tests/fixtures/fase1/` son sintéticas (`sintetico: true`), se regeneran de forma determinista (mismo hash en dos ejec… | Cumplido (modelo y catálogo) |
| AC-27 | La IA no introduce ni modifica cifras: 0 cifras fuera del conjunto verificado en pruebas con modelo simulado, incluidas las de escenarios y … | Cumplido (alcance actual) |
| AC-28 | *(Condicional, si se autoriza A-5)* El workflow de release publica `app-vX.Y.Z` con su `app.zip` y su SHA | No cumplido (condicional) |
| AC-29 | Fuentes de pedidos diferenciadas: **0** casos en que una fuente sustituya a la otra, se sumen ambas o se presenten como equivalentes; cada r… | Cumplido |
| AC-30 | Relaciones superiores a 100 %: el valor original se conserva (p. ej. 1 200/1 000 ⇒ 120 %); no se trunca, no se corrige, no se ajusta numerad… | Cumplido |
| AC-31 | Unidad de carritos: se muestra la unidad declarada o «unidad no declarada»; con unidad no declarada el cálculo se permite con interpretación… | Cumplido |
| AC-32 | Aplicabilidad por unidad: las columnas documentadas coinciden con los encabezados reales de los dos machotes; **0** exigencias de `trafico` … | Cumplido |

**Lectura:** las cinco reglas, IND-01, las fuentes diferenciadas, la aplicabilidad por unidad y la no regresión están cumplidos con evidencia. Lo pendiente corresponde a funcionalidad que aún no existe (procedencia, etiquetas en panel/anexo, QA del PPTX, anonimización, escenarios parametrizados) o a insumos que dependen del usuario (extractos reales, releases).
