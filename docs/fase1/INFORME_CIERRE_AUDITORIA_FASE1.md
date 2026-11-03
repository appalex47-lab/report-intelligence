# Informe de cierre — Auditoría documental de la Fase 1 de Report Intelligence

**Documento auditado:** `ESPECIFICACION_FASE1_REPORT_INTELLIGENCE_v4.md`
**Resultado:** `ESPECIFICACION_FASE1_REPORT_INTELLIGENCE_FINAL.md`
**Alcance:** exclusivamente documental. No se modificó código, fórmulas implementadas, cifras ni plantillas.

> Nota sobre el encargo: el texto recibido termina a mitad de frase en la sección C («Distingue las incidencias docume…»). Se interpretó como la instrucción de distinguir las incidencias **documentales** de las que dependen de **decisiones** o de la **implementación**; la tabla de §10 incluye esa distinción.

---

## 1. Resumen ejecutivo

- Se inspeccionaron **todas las hojas, encabezados y contenido** de `GLP1_crudo_ejemplo.xlsx` y `AETOPS_crudo_ejemplo.xlsx` (versión de `data/ejemplos`; la copia de `/tmp/ej` es idéntica en contenido). **Son datos sintéticos**, según `data/ejemplos/LEEME.md`.
- La revisión contra los machotes detectó que v4 **usaba nombres y fuentes inexistentes** (`folio`, `pac_id`, `estatus`, tráfico para AETOPS, columnas inexistentes en §10.1). Se corrigieron en la versión FINAL.
- Se aplicaron los cinco ajustes obligatorios: fuentes de pedidos diferenciadas (sistema de ventas vs GA4); E2 separado del indicador agregado; unidad de los carritos; relaciones > 100 %; dependencias de pruebas.
- Se realizó una auditoría transversal con verificación programática de referencias cruzadas (secciones, T-, AC-, RQ-, AMB-, F-, OBS-): **0 referencias rotas**.
- Las decisiones **A-1 a A-8 siguen todas pendientes**. Ninguna prueba de Fase 1 está ejecutada ni aprobada.
- **No hay incidencias documentales que bloqueen la autorización de la Fase 1.** Quedan incidencias residuales que dependen de decisiones del usuario o de la implementación (§10).

## 2. Cambios realizados respecto a v4

| Sección | Cambio realizado | Motivo |
|---|---|---|
| §0 | Principios 10 a 12 | Fuentes de pedidos, fidelidad a los machotes, cerrar ≠ autorizar |
| §1 | Tres hallazgos del código/machotes | Sustento factual |
| §2 | D2 reformulada | Unidad por defecto «no declarada» |
| §3.0 (nueva) | Estructura real de los machotes, diferencias GLP-1/AETOPS, clasificación de datos, 12 observaciones, diccionario | Revisión obligatoria |
| §3.1 | Definiciones con columna real; dos fuentes de pedidos | Ajuste 1 |
| §3.3 `R-REL-PAC-PED` | Nombres reales; estatus reservado e inactivo; ejemplo de 6 pedidos | Los machotes no tienen estatus |
| §3.3 `R-CUADRE-DIM` | Dimensiones candidatas observadas | Fundamento concreto |
| §3.3 `R-CONC-COMPRAS` | Fuentes identificadas; prohibiciones; «no es un error»; solo GLP-1 | Ajuste 1 |
| §3.3 `R-COBERTURA-ATC` | Unidad de carritos; estados; solo GLP-1 | Ajustes 3 y 4 |
| §3.4–3.6 (nuevas) | Glosario, catálogo de fórmulas F-01 a F-12, aplicabilidad por unidad | Auditoría 5.1, 5.2, 5.7 |
| §8 | Fichas E1 y E2; IND-01 con dos fuentes; tabla de tres elementos; > 100 % | Ajustes 1 a 4 |
| §9, §10.1, §10.3, §10.4, §10.7 | Alineados con los machotes | Consistencia |
| §10.8 (nueva) | Privacidad, datos e IA | Auditoría 5.8 |
| §11 | 22 obligatorias + 4 condicionales + 2 existentes; prerrequisitos; oleadas; activación; evidencia | Ajuste 5 |
| §12 | AC reescritos y AC-29 a AC-32 | Consistencia |
| §13 | Seis riesgos nuevos | Nuevos controles |
| §14 | Matriz con regla, escenario/indicador y evidencia; RQ-31 y RQ-32 | Ruta verificable |
| §15, §16 | A-1 a A-8 con dependencias; AMB-1 a AMB-11 | Decisiones pendientes |
| Anexos A, B, C | Cambios, 18 inconsistencias, auditoría | Entregables |

## 3. Resultado de la revisión de los dos machotes

| Archivo | Hoja | Filas | Columnas reales | Uso en la especificación |
|---|---|---|---|---|
| GLP-1 | `ventas` | 35 461 | `fecha_pedido`, `id_pedido`, `id_paciente`, `paciente_nuevo`, `sku`, `canal`, `estado`, `region`, `piezas`, `monto_venta`, `forma_pago`, `modo_entrega`, `programa_lealtad` | Pedidos del sistema de ventas; `R-REL-PAC-PED`; `R-CUADRE-DIM`; E1, E2 (ticket) |
| GLP-1 | `catalogo` | 16 | `sku`, `producto`, `categoria` | Dimensión categoría |
| GLP-1 | `trafico` | 1 260 | `mes`, `vista`, `valor`, `sku`, `visitas`, `usuarios`, `usuarios_nuevos`, `usuarios_recurrentes`, `vistas_producto`, `add_to_cart`, `begin_checkout`, `compras`, `carritos_abandonados`, `sesiones_rebote`, `segundos_interaccion_total` | Compras GA4, carritos agregados, `R-CONC-COMPRAS`, `R-COBERTURA-ATC`, IND-01, E2 |
| GLP-1 | `negados` | 5 | `producto`, `sku`, `alta`, `pedidos`, `cantidad_negada`, `monto_negado` | E1 |
| AETOPS | `ventas` | 22 466 | `fecha_pedido`, `id_pedido`, `id_paciente`, `paciente_nuevo`, `sku`, `canal`, `estado`, `sucursal`, `piezas`, `monto_venta` | `R-REL-PAC-PED`; `R-CUADRE-DIM`; E1 |
| AETOPS | `catalogo` | 28 | `sku`, `producto`, `linea`, `categoria`, `laboratorio` | Dimensiones línea y categoría |
| AETOPS | `negados` | 14 | `producto`, `sku`, `alta`, `pedidos`, `cantidad_negada`, `monto_negado` | E1 |
| AETOPS | *(sin `trafico`)* | — | — | `R-CONC-COMPRAS`, `R-COBERTURA-ATC`, IND-01 y E2 **no aplican** |

Los encabezados reales **coinciden con la estructura conocida** indicada en el encargo (no se renombró ni inventó ningún campo).

**Hallazgos de la revisión que cambiaron la especificación**

1. `estado` es la entidad federativa; **no existe columna de estatus de pedido** y el contrato (`docs/CONTRATO_DATOS.md`) excluye estatus y cancelaciones. v4 dependía de `estatus_excluidos`. Las clases C0/C1 quedaron **reservadas e inactivas**.
2. AETOPS **no tiene `trafico`**; v4 le pedía columnas de tráfico. Ahora la matriz de aplicabilidad (§3.6) y T-22 lo fijan.
3. En AETOPS, `sucursal`, `linea` y `categoria` varían dentro de un mismo pedido (5 457, 3 796 y 4 563 pedidos): los pedidos por esas dimensiones **no son exclusivos**. En GLP-1 ningún atributo de `ventas` varía dentro de un pedido.
4. Los desgloses de `trafico` (`edad`, `sexo`, `dispositivo`, `fuente`, `estado`) **no suman** el total `general`; los carritos agregados se toman solo del nivel sitio.
5. En `trafico`, `carritos_abandonados = add_to_cart − compras` en las 1 260 filas (propiedad del machote sintético, igual a la derivación del contrato; no prueba cómo lo define GA4).
6. `negados` no trae fecha: queda como limitación declarada de E1.
7. Ningún `id_pedido` tiene más de un paciente o fecha, ni hay filas idénticas duplicadas: las clases contradictorias se prueban con fixtures dedicadas, no con los machotes.
8. Sept-2026 (GLP-1): 2 356 pedidos del sistema de ventas, 2 643 compras GA4, 18 883 carritos agregados ⇒ 12,48 % y 14,00 % como **dos resultados independientes**; en el machote ninguna relación supera 100 % (máximo 14,5 %).

## 4. Matriz de consistencia

| Aspecto auditado | Comprobación | Resultado | Dónde |
|---|---|---|---|
| 5.1 Términos | Glosario único; «pedido» sin calificar prohibido; `folio` solo como alias; `estado` vs `estado_verificacion`; dos «coberturas» separadas | Consistente | §3.0, §3.4 |
| 5.2 Fórmulas | 12 fórmulas con numerador, denominador, fuentes, condiciones, faltantes y división inválida; las vigentes (F-09 a F-12) no se modifican | Consistente | §3.5 |
| 5.3 Reglas | Cinco reglas + IND-01; fuentes diferenciadas; aplicabilidad por unidad; faltantes tratados; dependencias de decisiones declaradas | Consistente | §3.3, §3.6, §15.2 |
| 5.4 Escenarios | Fichas con objetivo, entradas, fuentes, condiciones, fórmula, salidas, limitaciones, dependencias y comportamiento sin datos | Consistente | §8.1, §8.3 |
| 5.5 Criterios de aceptación | 32 AC, cada uno cubierto por al menos una prueba; AC-19 alineado con el inventario (22 + S-01; 4 condicionales) | Consistente | §12 |
| 5.6 Pruebas | 27 entradas con requisito, entrada, resultado, criterio, dependencias, activación, prerrequisitos, AC y evidencia | Consistente | §11 |
| 5.7 Machotes | Columnas documentadas = encabezados reales; reglas de GLP-1 no se extienden a AETOPS; T-22 lo verifica | Consistente | §3.0, §3.6 |
| 5.8 Privacidad e IA | Controles de v4 conservados; excepción opcional de la IA documentada; la IA no modifica cifras | Consistente | §10.8 |
| Referencias cruzadas | Secciones, T-, V-, S-, AC-, RQ-, AMB-, F-, OBS- (verificación programática) | **0 rotas** | Todo el documento |

## 5. Matriz de trazabilidad (Requerimiento → Regla → Escenario/Indicador → Criterio → Prueba → Evidencia)

| Req. | Requerimiento | Regla | Escenario / indicador | Criterio | Prueba | Evidencia esperada |
|---|---|---|---|---|---|---|
| RQ-01 | Regla `R-REL-PAC-PED` (§3.3) | R-REL-PAC-PED | — | AC-05 | T-01 | Informe JUnit de T-01 + hash de la fixture `rel_pac_ped_*` |
| RQ-02 | Regla `R-CUADRE-DIM` (§3.3) | R-CUADRE-DIM | — | AC-06 | T-02 | Informe JUnit de T-02 + fixtures `cuadre_dim_*` |
| RQ-03 | Regla `R-CONC-COMPRAS` con fuentes diferenciadas | R-CONC-COMPRAS | — | AC-07, AC-29 | T-03, T-21 | Informe JUnit de T-03 y T-21 |
| RQ-04 | Regla `R-DENOM` | R-DENOM | — | AC-08, AC-04 | T-04 | Informe JUnit de T-04 |
| RQ-05 | Regla `R-COBERTURA-ATC` (comparabilidad de carritos agregados y pedidos) | R-COBERTURA-ATC | IND-01 | AC-09, AC-31, AC-30, AC-04 | T-05 | Informe JUnit de T-05 + fixture `comparabilidad.json` |
| RQ-06 | Catálogo de definiciones versionado | — | — | AC-10 | T-07 | Informe JUnit de T-07 |
| RQ-07 | Hallazgo con nomenclatura explícita | — | — | AC-03 | T-06 | Informe JUnit de T-06 |
| RQ-08 | Migración compatible de `severity` | — | — | AC-02 | T-06, T-13 | Informe JUnit de T-06 y T-13 |
| RQ-09 | «No verificable» con `faltante` | R-DENOM, R-COBERTURA-ATC | — | AC-04 | T-06 | Informe JUnit de T-06 |
| RQ-10 | Manifiesto de procedencia | — | — | AC-10 | T-07, T-16 | Informe JUnit de T-07 y T-16; manifiesto de ejemplo |
| RQ-11 | Reproducibilidad y sus estados | — | — | AC-11, AC-12 | T-08 | Informe JUnit de T-08 |
| RQ-12 | Releases etiquetadas | — | — | AC-28, AC-10 | T-16, V-02 | Informe de T-16; ejecución del workflow y asset publicado (V-02) |
| RQ-13 | QA estructural del PPTX exportado | — | — | AC-14 | T-11 | Informe JUnit de T-11 + decks de defectos inyectados |
| RQ-14 | QA visual con render real | — | — | AC-16 | T-12 | PNG por diapositiva e informe de hallazgos (artefacto del workflow o carpeta local) |
| RQ-15 | Límites del QA declarados en la interfaz | — | — | AC-15 | T-11 | Informe JUnit de T-11 |
| RQ-16 | Escenario E1 (negados) con valor heredado | — | E1 | AC-13 | T-09 | Informe JUnit de T-09 + comparación con la línea base |
| RQ-17 | Escenario E2 heredado, diferenciado del indicador agregado | — | E2 | AC-13 | T-10b | Informe JUnit de T-10b + comparación con la línea base |
| RQ-18 | Etiquetas de supuesto heredado, de «ilustrativo» y de métrica heredada | — | E1, E2 | AC-13 | T-09, T-10b, T-11 | Informe JUnit de T-09, T-10b y T-11 |
| RQ-19 | Anexo de calidad de datos | — | IND-01, E1, E2 | AC-14 | T-11 | Informe JUnit de T-11 + deck sintético con anexo |
| RQ-20 | Procedimiento y herramienta de anonimización | — | — | AC-17 | T-15 | Informe JUnit de T-15 |
| RQ-21 | Validación con datos reales (modo informe) | Todas las R-* | — | AC-18 | V-01 | Informe de validación firmado por el usuario (solo si existen extractos) |
| RQ-22 | No-regresión | — | — | AC-01 | T-13 | Informe JUnit de T-13 + diff vacío frente a la línea base |
| RQ-23 | La IA no altera cifras ni sustituye cálculos | — | E1, E2, IND-01 | AC-27 | T-14 | Informe JUnit de T-14 |
| RQ-24 | Flags de reversión | — | — | AC-21 | T-13 | Informe JUnit de T-13 (corrida con flags desactivados) |
| RQ-25 | Rendimiento | — | — | AC-20 | T-19 | Medianas de tiempo registradas en el job de CI |
| RQ-26 | Validación sintética vs operacional diferenciadas y rotuladas | Todas las R-* | — | AC-24 | T-18 | Informe JUnit de T-18 |
| RQ-27 | Incorporar extractos reales después sin rehacer la arquitectura | Todas las R-* | — | AC-25, AC-23 | T-17 | Informe JUnit de T-17 + diff sin archivos de código |
| RQ-28 | Indicador IND-01 «Relación pedidos/carritos» (metodología agregada, §8.2) | R-COBERTURA-ATC | IND-01 | AC-22, AC-23, AC-30, AC-29 | T-10 | Informe JUnit de T-10 + búsqueda de denominaciones prohibidas en las salidas |
| RQ-29 | Escenarios de prueba reproducibles y sin datos reales | — | — | AC-26 | T-20 | Informe JUnit de T-20 + manifiesto de fixtures |
| RQ-30 | Suites existentes sin regresión | — | — | AC-19 | S-01, S-02 | Informe de pytest en CI (S-01) y local (S-02) |
| RQ-31 | Diferenciación de fuentes de pedidos: sistema de ventas vs GA4 | R-CONC-COMPRAS, R-COBERTURA-ATC | IND-01 | AC-29, AC-07 | T-21, T-03, T-10 | Informe JUnit de T-21, T-03 y T-10 |
| RQ-32 | Aplicabilidad por unidad y fidelidad a los machotes | Todas las R-* | E1, E2, IND-01 | AC-32 | T-22 | Informe JUnit de T-22 (compara encabezados de `data/ejemplos/*`) |

## 6. Inventario de pruebas y su estado

**Ninguna prueba de Fase 1 está ejecutada: todas figuran «Pendiente».** No se marcó ninguna como aprobada.

| ID | Tipo | Requisito | Activación | Prerrequisitos | Estado |
|---|---|---|---|---|---|
| T-20 | Obligatoria | RQ-29 | Siempre | — | Pendiente |
| T-22 | Obligatoria | RQ-32 | Siempre | — | Pendiente |
| T-06 | Obligatoria | RQ-07, RQ-08, RQ-09 | Siempre | P-00 | Pendiente |
| T-07 | Obligatoria | RQ-06, RQ-10 | Siempre | T-20 | Pendiente |
| T-04 | Obligatoria | RQ-04 | Siempre | T-20, T-06 | Pendiente |
| T-01 | Obligatoria | RQ-01 | Siempre; los casos con estatus se activan solo con la variante de configuración | T-20, T-06 | Pendiente |
| T-02 | Obligatoria | RQ-02 | Siempre | T-20, T-06 | Pendiente |
| T-21 | Obligatoria | RQ-31, RQ-03 | Siempre | T-20, T-06 | Pendiente |
| T-03 | Obligatoria | RQ-03, RQ-31 | Siempre | T-20, T-06 | Pendiente |
| T-05 | Obligatoria | RQ-05 | Siempre | T-20, T-06 | Pendiente |
| T-08 | Obligatoria | RQ-11 | Siempre | T-07 | Pendiente |
| T-09 | Obligatoria | RQ-16, RQ-18 | Siempre | T-20, P-00 | Pendiente |
| T-10 | Obligatoria | RQ-28, RQ-31 | Siempre | T-20, T-05, T-21 | Pendiente |
| T-10b | Obligatoria | RQ-17, RQ-18 | Siempre | T-20, P-00 | Pendiente |
| T-11 | Obligatoria | RQ-13, RQ-15, RQ-18, RQ-19 | Siempre | T-20, T-10 | Pendiente |
| T-12 | Condicional | RQ-14 | Se activa si `soffice` y `pdftoppm` están en el PATH; se ejecuta en `visual-qa.yml` (Actions, solo datos sintéticos) o con `tools/visual_qa.py` local. Si no, `omitida (sin LibreOffice)` | T-20, T-11 | Pendiente |
| T-13 | Obligatoria | RQ-08, RQ-22, RQ-24 | Siempre | P-00, T-06 | Pendiente |
| T-14 | Obligatoria | RQ-23 | Siempre | T-09, T-10 | Pendiente |
| T-15 | Obligatoria | RQ-20 | Siempre | T-20 | Pendiente |
| T-16 | Obligatoria | RQ-10, RQ-12 | Siempre | T-07 | Pendiente |
| T-18 | Obligatoria | RQ-26 | Siempre | T-20, T-06 | Pendiente |
| T-17 | Obligatoria | RQ-27 | Siempre | T-20, T-07, T-18 | Pendiente |
| T-19 | Obligatoria | RQ-25 | Siempre | T-13 | Pendiente |
| V-01 | Condicional (manual) | RQ-21 | Se activa solo si A-2 se autoriza y el usuario entrega extractos; si no, `omitida (sin extractos)` | T-17 | Pendiente |
| V-02 | Condicional (manual) | RQ-12 | Se activa solo si A-5 se autoriza; si no, `omitida (A-5 no autorizada)` | T-16 | Pendiente |
| S-01 | Obligatoria (existente) | RQ-30 | Siempre (se corre en la línea base y de nuevo en cada PR) | P-00 | Pendiente |
| S-02 | Condicional (existente) | RQ-30 | Se activa solo si `REPORT_FIXTURES_DIR` apunta a las plantillas; si no, `omitida (sin REPORT_FIXTURES_DIR)` | P-00 | Pendiente |

**Orden de ejecución (prerrequisito P-00: capturar la línea base antes de cambiar código).** Grafo verificado sin ciclos:

- Oleada 0: S-01, S-02, T-06, T-20, T-22
- Oleada 1: T-01, T-02, T-03, T-04, T-05, T-07, T-09, T-10b, T-13, T-15, T-18, T-21
- Oleada 2: T-08, T-10, T-16, T-17, T-19
- Oleada 3: T-11, T-14, V-01, V-02
- Oleada 4: T-12

**Evidencia previa (no de Fase 1):** S-01 en línea base: 181 passed in 475.65s (pytest tests/unit, sobre c8ba722, árbol limpio). Evidencia de la línea base previa a Fase 1; no es evidencia de aceptación de Fase 1. En esta revisión se ejecutó `pytest tests/unit` sobre el código sin modificar; la suite golden (S-02) no se ejecutó.

**Condicionales y por qué:** T-12 (requiere LibreOffice, ausente de `tests.yml`), S-02 (requiere `REPORT_FIXTURES_DIR` con plantillas reales no versionadas), V-01 (requiere extractos reales y A-2), V-02 (requiere A-5).

## 7. Decisiones A-1 a A-8 y su estado

La recomendación **no es una autorización**. Todas siguen **pendientes**.

| ID | Decisión | Recomendación | Estado |
|---|---|---|---|
| A-1 | Autorizar Fase 1 | Sí, después de corregir y revisar la documentación | **Pendiente** |
| A-2 | Datos reales | Incorporarlos después de la implementación inicial | **Pendiente** |
| A-3 | Modificar láminas actuales | No modificarlas por ahora | **Pendiente** |
| A-4 | Escenarios 25 % y 10 % | Mantenerlos como supuestos heredados no validados | **Pendiente** |
| A-5 | Releases etiquetadas | Sí | **Pendiente** |
| A-6 | QA visual en Actions | Datos sintéticos; los datos reales se validan localmente | **Pendiente** |
| A-7 | Retirar `severity` | Mantener compatibilidad | **Pendiente** |
| A-8 | Decisiones restantes (D3, D4, D5, D8) | Aceptar las recomendaciones documentadas | **Pendiente** |

El detalle de qué parte de la implementación depende de cada una, qué se conserva mientras tanto y qué no puede asumirse está en `§15.2` de la especificación.

## 8. Limitaciones que permanecen

1. **Sin validación operacional:** todo se apoya en machotes sintéticos; las reglas saldrán «No validadas con datos reales» hasta que existan extractos y tu confirmación.
2. **Sin ejecución de pruebas de Fase 1:** la especificación no demuestra que el código las pase.
3. **QA visual:** el navegador no puede renderizar el PPTX; el render real requiere LibreOffice (Actions o equipo local) y no equivale a PowerPoint.
4. **Unidad de carritos desconocida:** los machotes no la declaran; todo resultado de IND-01 nace como «cálculo con limitación» hasta que el usuario la declare.
5. **Significado de `carritos_abandonados` en GA4** no determinable con los machotes; se conserva su definición histórica.
6. **Cancelaciones no identificables:** no existe estatus de pedido; es decisión vigente del contrato.
7. **`negados` sin fecha:** el periodo se asume por convención operativa.
8. **El motor actual no tiene el indicador IND-01:** se incorpora como salida nueva; falta confirmar que la fórmula coincide con la que el negocio usa hoy (AMB-8).
9. **Reportes anteriores a Fase 1** no son reproducibles de forma exacta.

## 9. Confirmación expresa

- **No se modificó código fuente, funciones, fórmulas implementadas, consultas, estructuras de datos, plantillas de PowerPoint, diseño de diapositivas, cifras históricas ni reglas de negocio aprobadas.**
- No se crearon commits ni se tocó el repositorio. Estado verificado al terminar: `HEAD` = `c8ba722 Merge pull request #9 from appalex47-lab/claude/awesome-wozniak-f35r21`; `git status --short` = vacío (árbol limpio).
- Los únicos archivos producidos son documentos en el directorio de trabajo temporal de la sesión: la especificación FINAL y este informe (más scripts auxiliares de generación y verificación, no incluidos en el repositorio).
- Las únicas ejecuciones sobre el código fueron de **solo lectura**: lectura de los Excel y `pytest tests/unit` (sin editar archivos).
- Las decisiones A-1 a A-8 no se marcaron como aprobadas; no se tomaron decisiones en nombre del usuario.
- Los supuestos heredados 25 % y 10 % se conservan como «Supuesto heredado, no validado»; no se inventaron escenarios conservador/optimista.

## 10. Registro de incidencias residuales

No se inventaron incidencias. **No existen contradicciones internas conocidas ni incidencias documentales que bloqueen la autorización de la Fase 1.** Lo que permanece son decisiones del usuario y dependencias de implementación o de datos reales:

| ID | Tipo | Descripción | Severidad | Motivo por el que permanece | Impacto | Responsable / decisión requerida | ¿Bloquea la autorización de Fase 1? |
|---|---|---|---|---|---|---|---|
| INC-01 | Decisión | Fuente de pedidos «de referencia» para IND-01 (AMB-1) | Baja | La documentación calcula y muestra ambas fuentes sin elegir una | Presentación de IND-01 | Usuario, al responder A-1 | No |
| INC-02 | Decisión | La lámina actual rotula «carritos abandonados» y puede leerse como abandono comprobado (AMB-3) | Media | Restricción: no modificar láminas sin A-3 | Posible lectura errónea en láminas existentes; las salidas nuevas incluyen la aclaración | Usuario: A-3 | No |
| INC-03 | Dependencia | La fórmula de IND-01 no existe en el motor; confirmar que coincide con la que se usa hoy (AMB-8) | Media | No hay forma de verificarlo con los machotes | Podría diferir de la práctica actual | Usuario, al responder A-1 | No (se confirma antes de implementar IND-01) |
| INC-04 | Dependencia de datos | Ninguna regla tiene validación operacional | Media | No hay extractos reales ni confirmación | Reglas etiquetadas «No validadas con datos reales» | Usuario: A-2 | No |
| INC-05 | Dependencia de datos | Significado de `carritos_abandonados` informado por la herramienta de analítica (AMB-10) | Baja | No determinable con los machotes | Interpretación limitada de E2 | Usuario / datos reales | No |
| INC-06 | Dependencia de datos | `negados` sin fecha (AMB-11) | Baja | Convención operativa vigente | Limitación de E1 | Usuario | No |
| INC-07 | Decisión | Restringir la relación al canal web (AMB-9) | Baja | El machote GLP-1 solo trae `ECOMMERCE`; no hay evidencia de otros canales | Comparabilidad con datos reales | Usuario, con extractos | No |
| INC-08 | Parámetros | Criterio de periodos y valores por defecto de cobertura/tolerancias (AMB-5, AMB-7) | Baja | Sin umbral universal; propuestas documentadas | Ajuste fino | Usuario, con datos reales | No |
| INC-09 | Implementación | 27 entradas del inventario de pruebas en estado «Pendiente» | Informativa | Se ejecutan durante la implementación | Sin evidencia de aceptación hasta entonces | Desarrollo, tras A-1 | No |
| INC-10 | Decisión | A-1 a A-8 pendientes | Informativa | Solo el usuario puede autorizarlas | Nada se implementa hasta entonces | Usuario | Es la propia decisión de autorizar (A-1) |
