# AC-14 · cifras, fórmulas, unidades y denominadores del PPTX exportado

## 1. Requisito original y su contexto

| Fuente | Texto |
|---|---|
| AC-14 (`ESPECIFICACION_FASE1…FINAL.md` §12) | «QA estructural detecta 100 % de los defectos inyectados (token, duplicado, fuente mínima, unidad sin denominador, fórmula alterada, cifra no trazada) con **0 falsos positivos** en los decks de referencia» |
| §7.A (tabla de chequeos) | **Cifras:** «cada número impreso se puede trazar a un `Value` verificado» → `PPTX_CIFRA_NO_TRAZADA`. **Fórmulas:** «los derivados impresos (variaciones, participaciones, conversiones, escenarios) se recalculan desde sus `Value` y deben coincidir con lo impreso» → `PPTX_FORMULA_NO_COINCIDE`. **Unidades:** «`%`, `pp`, moneda y conteos coherentes con la métrica» → `PPTX_UNIDAD_AMBIGUA`. **Denominadores:** «cada ratio publicado declara su denominador (§3.2)» → `PPTX_SIN_DENOMINADOR` |
| §3.2 | «Todo ratio publicado muestra su denominador y la fuente de cada término… Denominador 0 o ausente ⇒ «No verificable» o «No calculable», nunca 0 %. Un mismo ratio en dos láminas usa el mismo denominador» |
| T-11 | «Decks sintéticos: uno limpio y otros con defectos inyectados (token, duplicado, fuente < mínima, unidad sin denominador, fórmula alterada, cifra no trazada, forma fuera de lienzo)» → «Cada defecto detectado con su `id`; deck limpio sin errores» · «100 % de defectos detectados y 0 falsos positivos en decks de referencia» |
| Límite declarado en §7.A | El QA estructural lee el XML y **no ve cómo se dibuja**; python-pptx no calcula ajuste de línea ni contraste |

**Momento del flujo:** sobre el `.pptx` **ya guardado**, durante la generación (`build.py`), con los valores que calculó el motor y las cifras de la narrativa ya verificada. **Qué se compara:** lo impreso contra (a) los valores del motor, (b) las cifras de la narrativa verificada y (c) lo impreso en la misma celda o párrafo.

## 2. Qué se implementó (`backend/app/qa/cifras.py`)

| Comprobación | Cómo | Qué NO cuenta como diferencia |
|---|---|---|
| `PPTX_CIFRA_NO_TRAZADA` | cada número impreso se busca entre los valores del motor con una tolerancia de **media unidad del último dígito impreso**, en los formatos `$12.22 M`, `$639.1 K`, `56%`, `+56%`, `55.6%`; un porcentaje puede ser una fracción del motor (0.56); se acepta lo que la narrativa verificó; un porcentaje también puede ser una **razón o variación de dos números de la misma celda/párrafo o de las formas `RI_*` generadas** (p. ej. «avanza 23.33 %» = 2,643 ÷ 11,329) | formato, redondeo, linaje; años, índices de lista, horas, códigos de 5 o más dígitos y dosis dentro de nombres de producto («ENZALUTAMIDA 40 MG»); celdas vacías y «—» |
| `PPTX_FORMULA_NO_COINCIDE` | en cada bloque de una tabla: **Ticket = Monto ÷ Pedidos** por fila; **fila de variación = actual ÷ anterior − 1** columna a columna; ticket impreso con **0 pedidos** (denominador cero); las tolerancias propagan el redondeo impreso de cada término | redondeo de los términos; tablas que apilan bloques (productos y resumen por alta) |
| `PPTX_UNIDAD_AMBIGUA` | por columna (según su encabezado): dinero con y sin `$`, conteos con `$` o `%`, porcentajes sin `%`; y **moneda inventada** (`MXN`, `USD`, `EUR`, `pesos`, `dólares`…) en cualquier texto | el `$` por sí solo no es una moneda declarada |
| `PPTX_SIN_DENOMINADOR` | un párrafo con un porcentaje de **proporción** (sin signo y distinto de 0) debe nombrar su base en algún punto del párrafo («de la venta», «de share», «del avance», «convierte … en …», «vs», …) | variaciones con signo (+8 %, −3 %) o 0 %, que heredan su base de la comparación; tablas |

Severidad `warn` (no bloquea la descarga): son heurísticas sobre texto y un falso positivo no debe impedir entregar un reporte válido. Los tokens técnicos (`PPTX_TOKEN_TECNICO`) siguen siendo `error`.

## 3. Trazabilidad requisito → implementación → prueba

| Requisito | Implementación | Prueba (`tests/unit/test_qa_cifras.py`, 55) |
|---|---|---|
| Cifra no trazada detectada | `comprobar_cifras`, `trazable`, `Indice` | `test_cifra_modificada_se_detecta`, `…_en_celda_modificada…`, `test_decks_de_referencia…` (inyecta «$987.65 M») |
| Sin falsos positivos por formato/redondeo/linaje | `analizar` (tolerancia por precisión impresa) | `test_formatos_y_redondeos…` (5), `test_porcentajes_como_fraccion…` (6), `test_lo_derivable…`, `test_anios_codigos_horas_nombres_e_indices…` (7) |
| Valores vacíos / cero | `_valor`, `numeros` | `test_cifra_con_valor_cero_y_celdas_vacias…`, `test_sin_valores_del_motor…` |
| Fórmula alterada | `_comprobar_bloque` | `test_ticket_alterado…`, `test_variacion_alterada…` |
| Denominador incorrecto / cero | `_comprobar_bloque` | `test_denominador_incorrecto_en_el_ticket…`, `test_ticket_con_cero_pedidos…` |
| Redondeo no es error | tolerancia propagada | `test_el_redondeo_del_ticket_no_es_un_error` (4) |
| Fuentes distintas no se mezclan | el ticket solo se contrasta con la columna **Pedidos**; una columna «Compras GA4» ni sustituye al denominador ni se usa para validar | `test_fuentes_distintas_no_se_mezclan_en_la_formula` |
| Unidades incompatibles / no declaradas / inventadas | `_comprobar_bloque`, `comprobar_moneda` | `test_moneda_mezclada…`, `test_conteo_con_signo…`, `test_porcentaje_sin_simbolo…`, `test_moneda_inventada_se_detecta` (5), `test_el_signo_de_pesos_solo…` |
| Denominador ausente | `comprobar_denominadores` | `test_porcentaje_de_proporcion_sin_base…`, `test_las_variaciones_con_signo_o_cero…` (4) |
| 0 falsos positivos en los decks de referencia | calibración | `test_decks_de_referencia_sin_falsos_positivos` (4) |
| Las pruebas detectan defectos reales | mutación | 9 mutaciones deliberadas del módulo, 9 detectadas |

## 4. Resultados sobre los 4 decks de referencia

AETOPS mensual y trimestral: **0 hallazgos**. GLP-1 mensual y trimestral: **1 hallazgo cada uno, `PPTX_SIN_DENOMINADOR`, que NO es un falso positivo**: el texto «Las presentaciones que más venden: Mounjaro (74 %, $9.20 M); Wegovy (18 %…)» publica participaciones sin nombrar su base (la venta total del periodo, que solo se infiere de la columna «Share» de la tabla vecina). §3.2 exige que el ratio publicado muestre su denominador. Es una **observación sobre la narrativa existente** (`glp1_exec.py`, protegida) y **no se modifica**: corregirla cambia el texto de las láminas y requiere la autorización A-3. La prueba de referencia admite exactamente ese hallazgo y falla ante cualquier otro.

Durante la calibración se corrigieron falsos positivos **del detector**: dosis dentro de nombres de producto y códigos de producto, rangos de edad («55-64»), años seguidos de coma, tablas con bloques apilados, filas de variación mezcladas con filas de datos, porcentajes con signo, y una derivación demasiado permisiva (con todos los números de la lámina un porcentaje alterado habría pasado por «derivable» por coincidencia) que se acotó a la misma celda/párrafo o a las formas generadas.

## 5. Limitaciones y alcance

* **No valida el significado**: comprueba que «927» provenga del motor o de lo impreso, no que sean pedidos. Las columnas se reconocen por el texto de su encabezado; una columna con un encabezado desconocido no se contrasta (no se adivina).
* **Una cifra que coincide con un valor del motor puede ser la métrica equivocada**: el motor tiene ~1 000 valores por deck y, con la precisión de un porcentaje de 0 decimales, una cifra alterada podría coincidir por azar con alguno. Mitigación: los números de dinero y conteos (con tolerancia pequeña) casi no colisionan; los porcentajes de 0 decimales sí pueden. Es un límite de la traza, no se oculta.
* Las unidades de origen que declara la fuente: ningún libro declara moneda; el comprobador no la infiere ni la exige, solo prohíbe inventarla.
* Alcance: texto corrido y tablas. Las gráficas se revisan por estructura (`PPTX_GRAFICO_VACIO`), no por sus valores.
* Las pruebas con los decks reales exigen plantillas no versionadas: se omiten con motivo donde faltan (CI); las 51 pruebas sintéticas sí corren en CI.

## 6. Dictamen de AC-14

**PARCIALMENTE CUMPLIDO.**

Cumple: las cuatro comprobaciones existen, **detectan cada defecto inyectado** (cifra modificada, fórmula alterada, denominador incorrecto, unidad incompatible, moneda inventada, porcentaje sin base, ticket con denominador cero) con su `id`, y dan **0 falsos positivos** en los decks de referencia, salvo la observación real descrita. Además se verificó por mutación que las pruebas no son artificiales.

No se puede declarar CUMPLIDO porque: (a) el criterio habla de «100 % de los defectos inyectados» y la cobertura se demuestra sobre el catálogo de defectos de T-11, no sobre cualquier defecto posible (p. ej. una cifra alterada que coincida por azar con otro valor del motor); (b) las comprobaciones por plantilla dependen del reconocimiento por encabezado y no cubren gráficas ni todas las tablas; (c) en GLP-1 deja una advertencia real que solo se resuelve cambiando el texto de la narrativa (A-3, fuera del alcance autorizado).
