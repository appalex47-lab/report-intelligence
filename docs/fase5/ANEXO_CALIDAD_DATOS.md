# Anexo de calidad de datos (RQ-19)

Dónde se ve: panel «Anexo de calidad de datos» en el paso «Validar» (plegable) y archivo `anexo_calidad.json` junto al reporte generado (botón de descarga). Código: `backend/app/calidad.py`. **Informa; no corrige, no completa y no excluye datos**; el único que bloquea la generación sigue siendo el motor de validación.

## 1. Qué evalúa

| Dimensión (`id`) | Qué comprueba | Ejemplos de `id` de hallazgo |
|---|---|---|
| Calidad estructural (`estructural`) | hojas leídas, hojas opcionales ausentes (`trafico` en GLP-1, `negados`), formato antiguo | `EST-HOJAS`, `EST-SIN-TRAFICO`, `EST-SIN-NEGADOS`, `EST-FORMATO-ANTIGUO` |
| Calidad semántica (`semantica`) | montos negativos o 0, piezas ≤ 0, SKU de ventas ausente del catálogo, hallazgos del motor | `SEM-MONTO-NEG`, `SEM-PIEZAS`, `SEM-SKU-SIN-CATALOGO` |
| Calidad temporal (`temporal`) | periodo sin ventas, rango de fechas, meses de tráfico faltantes, `negados` sin fecha | `TEM-PERIODO-VACIO`, `TEM-TRAFICO-MESES`, `TEM-NEGADOS-SIN-FECHA` |
| Integridad (`integridad`) | pedidos con más de un paciente, pedidos que no cumplen los criterios de pedido válido, bloqueos del motor | `INT-PEDIDO-MULTIPACIENTE`, `INT-PEDIDOS-EXCLUIDOS` |
| Consistencia entre fuentes (`consistencia`) | pedidos del sistema de ventas frente a compras GA4 (sin combinarlas) | `CON-VENTAS-GA4` |
| Completitud (`completitud`) | fechas ausentes, advertencias de `negados` | `COM-FECHA`, `COM-E1-NEGADOS` |
| Duplicados (`duplicados`) | líneas idénticas en el periodo | `DUP-LINEAS` |
| Valores vacíos (`vacios`) | por columna del periodo, con porcentaje y filas de ejemplo; alta si la columna es requerida | `VAC-<COLUMNA>` |
| Tipos de datos (`tipos`) | fechas y números ilegibles | `TIP-FECHA`, `TIP-MONTO_VENTA`, `TIP-PIEZAS` |
| Unidades de medición (`unidades`) | unidad de los carritos agregados | `UNI-CARRITOS` |
| Trazabilidad (`trazabilidad`) | archivo (nombre, tamaño, SHA-256), versiones de la aplicación y del motor | `TRA-ARCHIVO`, `TRA-VERSIONES` |
| Riesgo de interpretación (`riesgo`) | relaciones > 100 %, escenarios con supuesto heredado | `RIE-MAYOR-100-*`, `RIE-E1`, `RIE-E2` |
| Impacto sobre los indicadores (`impacto`) | por indicador, qué hallazgos medios o altos lo afectan | `IMP-IND-01`, `IMP-E1`… |
| Datos no verificables (`no_verificables`) | unidad de `add_to_cart`, GA4, `carritos_abandonados`, moneda | `NVE-*` |
| Supuestos y limitaciones (`supuestos`) | 25 %, 10 %, validación solo sintética de las reglas | `SUP-*` |

Cada hallazgo trae `id`, `descripcion`, `severidad` (alta, media, baja, informativa), `naturaleza`, `evidencia`, `impacto` e `indicadores` afectados. La evidencia cita hoja, columna, número de filas y hasta 5 filas de ejemplo.

## 2. Naturaleza del dato y origen del libro

| Naturaleza | Significado |
|---|---|
| `observado` | viene del libro tal cual |
| `faltante` | celda o mes que debía existir y está vacío |
| `inferido` | lo deduce el sistema (p. ej. `carritos_abandonados` = `add_to_cart − compras` cuando viene vacío) y se marca siempre |
| `no_verificable` | el libro no permite comprobarlo |

Las seis categorías del encargo (real, sintético, ejemplo, faltante, inferido, no verificable) están definidas en el anexo (`origen_datos.categorias`). **El sistema nunca afirma que los datos sean reales**: solo infiere «ejemplo o sintético» por el nombre del archivo (`ejemplo`, `sintético`, `demo`, `muestra`…) y, si no, lo deja «no declarado», con la advertencia «No presentar estos resultados como datos de producción sin confirmarlo fuera del sistema».

## 3. Resultados con los libros de ejemplo (sintéticos)

| Libro | Altas | Medias | Bajas | Informativas | Origen |
|---|---|---|---|---|---|
| `GLP1_crudo_ejemplo.xlsx` | 0 | 14 | 1 | 7 | ejemplo inferido |
| `AETOPS_crudo_ejemplo.xlsx` | 0 | 5 | 1 | 5 | ejemplo inferido |
| `GLP1_crudo_con_defectos.xlsx` | 7 | 15 | 2 | 6 | no declarado (el nombre no lo delata) |
| `AETOPS_crudo_con_defectos.xlsx` | 10 | 11 | 1 | 5 | no declarado |

Las medias de los libros limpios son no verificables y supuestos, no errores de datos. En los libros con defectos, el anexo encuentra cada defecto que el motor ya bloquea (fecha ilegible, SKU fuera del catálogo, id vacío, número ilegible) con el **mismo conteo** (p. ej. 1 fila con fecha ilegible) y agrega los que el motor no reporta (pedidos excluidos por no ser válidos, montos negativos con su fila, columna requerida vacía).

## 4. Diapositiva final en el PPTX (RQ-19)

**Revisión documental (3.1).** La especificación exige la diapositiva: «Anexo "Calidad de datos y supuestos" al final del deck, sin mover láminas existentes» (§6, punto 7); RQ-19: «Diapositiva final con definiciones, versiones, estados, no verificables, fuentes y limitaciones» (§14); T-11: «anexo presente»; la decisión D5 del deck: «solo agregar el anexo de calidad de datos». También exige que el anexo esté en el panel y en el manifiesto. Conclusión: **opción C (ambas presentaciones)**; la versión anterior de esta fase solo tenía el panel y el JSON.

**Implementación** (`backend/app/deck/anexo.py`): una diapositiva «Calidad de datos y supuestos» **al final**, clonada de la última para conservar barras, logos, pie y tipografías: origen de los datos y su advertencia, conteo de hallazgos, datos no verificables (hasta 4), supuestos (hasta 3), hasta 6 hallazgos principales de severidad alta o media, y la trazabilidad (archivo, prefijo del SHA-256, versiones). Letra ≥ 9 pt; lo que no cabe cede por prioridad y los títulos y el origen nunca se pierden. El contenido completo sigue en el panel y en `anexo_calidad.json`; ninguna cifra del negocio se agrega (cada número impreso sale del JSON del anexo, con prueba).

**Es opt-in**, porque el flag `anexo_calidad` de `reglas.json` sigue desactivado y con los flags apagados la salida debe ser idéntica a la línea base (AC-21; `capture_baseline --check` lo verifica en 8 de 8). Se activa con una casilla en el paso «Generar» o con el flag. Activarlo **por omisión** cambia la línea base de los decks y es una decisión pendiente del usuario.

**Evidencia:** 12 pruebas (`test_anexo_pptx.py`): la diapositiva se agrega al final y las existentes quedan idénticas (texto de cada diapositiva); en los 4 decks reales el deck con anexo = el deck sin anexo + 1 diapositiva, sin hallazgos nuevos de QA, y el QA visual con LibreOffice aprueba sin hallazgos. Revisada visualmente en las 4 plantillas (legible, sin saturar). El manifiesto de procedencia **no** se modificó (su contrato está congelado): el resumen del anexo en el manifiesto que menciona la especificación queda como limitación L-8.

## 5. Qué NO hace

* No valida los datos contra el sistema de origen ni detecta errores de captura que sean valores plausibles.
* Los libros en formato antiguo (por bloques) no tienen filas de ventas: hasta seis dimensiones quedan «no evaluable» y consta cuáles hallazgos del motor existen.
* El anexo no se añade al manifiesto de procedencia (contrato 3A congelado, L-8).
* No mide el rendimiento con libros grandes en el navegador.
