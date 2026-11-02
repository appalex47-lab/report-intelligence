# Report Intelligence — Diagnóstico Fase 1 (auditoría)

Fecha: 2026-11-02 · Alcance: 5 PPTX y 4 Excel operativos + 2 machotes recibidos.
Convención: **[V]** verificado contra los archivos · **[I]** inferido (falta confirmar) · **[P]** pendiente de validación humana.

---

## 1. Resumen ejecutivo

1. **Los PPTX originales no se parecen a lo que genera la app hoy.** Son diapositivas 13.33×7.5" con barras naranjas arriba y abajo, logos *e-commerce* y *Farmacias Especializadas*, tablas nativas con formato condicional (verde / rojo / amarillo) y texto narrativo a la derecha o izquierda. **No contienen gráficas de barras**; la app actual las agrega y usa otra paleta. [V]
2. **Las gráficas no son lo central:** de 5 PPTX, solo el de GLP-1 Agosto trae una gráfica nativa (embudo `chartEx`, diapositiva 7). El resto es *tablas + texto*. [V]
3. **Los Excel son libros armados a mano**, no tablas de datos limpias: bloques apilados o lado a lado, encabezados mal rotulados, valores pegados y fórmulas sueltas. El motor actual asume estructuras que no existen. [V]
4. **Hallazgo crítico de calidad de datos:** el archivo `AETOPS_2026_Septiembre_listo_MoM.xlsx` **contiene datos de Agosto**. En `Base`, la fila 2026 (Monto 11,560,021; Piezas 2,119; Pacientes 1,121; Pedidos 1,427) es idéntica al PPTX de Agosto, y el bloque MoM tiene "Agosto" y "Septiembre" con los **mismos números**. Las hojas "Venta Septiembre / Venta Agosto" tienen encabezados "Venta Agosto / Venta Julio". [V]
5. **`GLP1_2026_Septiembre_MoM.xlsx` mezcla periodos:** las hojas 1, 4 y 6 parecen de Septiembre, pero la hoja 7 (productos) coincide **exactamente** con el PPTX de Agosto (Mounjaro 533 pedidos, $2,694,543, −10.57%). [V]
6. **Faltan 3 de los 4 formatos de referencia** (ver §2). Sin ellos no se puede replicar el formato trimestral ni GLP-1 trimestral.
7. **Decisión de arquitectura pendiente:** replicar fielmente estos PPTX (logos, formato condicional, tablas con celdas combinadas) con la librería actual del navegador **no es viable**; ver §8.

---

## 2. Inventario recibido

| Archivo | Qué es | Diapositivas / hojas |
|---|---|---|
| `Resultados_AETOP_Agosto_2026.pptx` | AETOPS **mensual** (YoY + MoM) | 11 |
| `Resultados_AETOP_Nov_2025_1.pptx` | AETOPS mensual, versión anterior (con "Causas de la caída") | 12 |
| `Resultados_AETOP_Q1_2026.pptx` | AETOPS **trimestral** (solo YoY) | 8 |
| `Resultados_GLP1_Agosto_2026.pptx` | GLP-1 **mensual** | 11 |
| `Radiogr_fia_GLP1_2025_.pptx` | GLP-1 **anual 2025** ("Radiografía") | 6 |
| `AETOPS_2026_Septiembre_listo_MoM.xlsx` | Fuente AETOPS mensual | 7 hojas |
| `AETOPS_2026_Trimestre_Q3.xlsx` | Fuente AETOPS trimestral | 8 hojas |
| `GLP1_2026_Septiembre_MoM.xlsx` | Fuente GLP-1 mensual | 9 hojas (`1`…`9`) |
| `GLP1_2026_Trimestre_Q3.xlsx` | Fuente GLP-1 trimestral | 9 hojas (`1`…`9`) |
| `MACHETE_AETOPS/GLP1_Report_Intelligence.xlsx` | Machotes de la app | 6 y 8 hojas |

**Cobertura de los 4 formatos**

| Formato | PPTX de referencia | Excel de referencia | Par coherente |
|---|---|---|---|
| AETOPS mensual | Agosto 2026, Nov 2025 | Septiembre (en realidad Agosto) | ⚠️ El Excel corresponde al PPTX de Agosto |
| AETOPS trimestral | Q1 2026 | Q3 2026 | ❌ Periodos distintos |
| GLP-1 mensual | Agosto 2026 | Septiembre MoM | ❌ Periodos mezclados |
| GLP-1 trimestral | **No hay** (solo la Radiografía anual 2025, formato distinto) | Q3 2026 | ❌ |

**Faltan:** PPTX GLP-1 trimestral real; PPTX AETOPS Q3 y su Excel Q1 (o su par equivalente); un Excel que corresponda al PPTX GLP-1 Agosto; los **logos originales** (están embebidos en los PPTX, se pueden extraer).

---

## 3. Cómo funciona cada presentación

Elementos comunes a **todas** las diapositivas [V]: barra naranja superior e inferior, logo e-commerce (SVG, arriba derecha), logo Farmacias Especializadas (PNG, abajo derecha), pie de página fijo *"La información presentada es recopilada y gestionada por el Departamento de E-Commerce…"*, título naranja, fuente **Aptos Narrow** (tablas) / Arial (algunos textos). Acentos de color: azul `0070C0` (encabezados), verde `C6EFCE/006100` y rojo `FFC7CE/9C0006` (deltas), amarillo para neutro.

### 3.1 AETOPS mensual (Agosto 2026, 11 diapositivas)

| # | Contenido | Tipo |
|---|---|---|
| 1 | Panorama General: tabla **YoY** y tabla **MoM** (Monto, Piezas, Pacientes, Pedidos, Ticket, Productos, Size B, V. Paciente) + fila de %Δ + texto | tablas + narrativa |
| 2 | Análisis por **canal** YoY (APP FESA, ECOMMERCE, LLAMADAS GOOGLE, WHATSAPP) | tabla con bloques por canal |
| 3 | Análisis por canal **MoM** | ídem |
| 4 | Análisis por **línea** AETOP (AE-A, AE-B, AE-C, HYR) YoY | ídem |
| 5 | Análisis por línea MoM | ídem |
| 6 | Productos: Top 20 por venta actual vs mes anterior (Sivec, Producto, AETOP, Canales, Venta actual, anterior, Delta) | tabla + narrativa |
| 7 | Productos con mayor crecimiento / decrecimiento (Top 10 c/u) | 2 tablas + 2 textos |
| 8 | Categorías YoY | tabla + narrativa |
| 9 | Categorías MoM (2 tablas) | tablas + narrativa |
| 10 | Negados: por línea ("Alta") y Top productos | 2 tablas + narrativa |
| 11 | Conclusiones Clave: viñetas con %YoY/%MoM + "Insights clave" | texto |

> ⚠️ **[P] Rótulos cruzados en el original de Agosto:** la diapositiva 2 se titula *"Análisis Líneas AETOP YoY"* pero su tabla es por **canal**; la 4 se titula *"Análisis de Canales YoY"* pero su tabla es por **línea**. En el PPTX Nov 2025 el orden es el contrario (Líneas → Canales). Hay que confirmar cuál es el correcto antes de automatizar.

Diferencias vs Nov 2025: tenía diapositiva **"Causas de la caída en WhatsApp y Google"** (tablas Canal/Motivo, AETOP/Motivo); Agosto ya no. Los deltas muestran centavos ($5,274.46) en Nov 2025 y enteros en Agosto. [V]

### 3.2 AETOPS trimestral (Q1 2026, 8 diapositivas)

Panorama (solo **YoY**), Líneas YoY, Canales YoY, Productos Top 20, Crecimiento/Decrecimiento, Categorías YoY, Negados, Conclusiones. **No hay MoM**; la columna de venta se rotula *"Venta Q1 Actual 2026 / Venta Q1 Año 2025"*. Compara contra el mismo trimestre del año anterior. [V]

### 3.3 GLP-1 mensual (Agosto 2026, 11 diapositivas)

| # | Contenido |
|---|---|
| 1 | ¿Quién busca GLP1? — Edad, Sexo, Dispositivo (3 tablas con share y %Δ) + narrativa + nota de incidencia |
| 2 | Edad por producto (Mounjaro / Rybelsus) — tabla doble de 17 columnas |
| 3 | Producto × Sexo (visitas, usuarios, ATC, tiempo de interacción, rebote) — fila resaltada en rojo = líder |
| 4 | Narrativa Mounjaro |
| 5 | Región: venta (Región, Pedidos, Piezas, Monto, Pacientes, Ticket, Share, %Δ) + tráfico por estado |
| 6 | Comportamiento de compra: Forma de pago y Modo de entrega |
| 7 | Embudo (**gráfica nativa chartEx**) + Negados |
| 8 | Productos Top 10 por monto |
| 9 | Programas de apoyo (lealtad) |
| 10 | Fuentes de tráfico |
| 11 | Conclusiones Clave |

Cada diapositiva lleva una **nota manual** ("el 31 de agosto se tuvo una afectación de aprox. 10 minutos") → dato que no está en ningún Excel. [V]

### 3.4 GLP-1 "trimestral"

No existe PPTX trimestral. La **Radiografía 2025** (6 diapositivas) es anual: Demografía, Comportamiento (pago, canales, programas, entrega), Compra vs Negado; **sin columnas %Δ ni share de producto de negados**, narrativa en cuadro lateral con imagen. [V] Si el trimestral debe parecerse a la Radiografía o al mensual es **[P]**.

---

## 4. Estructura real de los Excel

### 4.1 AETOPS (`Base`, `Tablas`, `Negados`, `listo`, hojas de venta)

- **`Base`** (193×23): bloques **apilados** con rótulo en la columna B ("YoY", "MoM", nombre del canal / línea). [V]
  - Filas 1–12: Panorama (YoY y MoM). Fórmulas: `Size B = Piezas/Pacientes`, `V.Paciente = Monto/Pacientes`, `%Δ = (act−ant)/ant`. **Ticket, Monto, Piezas, Pacientes, Pedidos y Productos están pegados como valores**, no calculados. [V]
  - Filas 13–56: canales YoY (13) y MoM (38). Filas 57–95: líneas AE-A/B/C/HYR YoY. Fila 96 en adelante: YoY (categorías, **[I]**) y MoM en 139. Cada bloque = 2 filas (periodo anterior, actual) + fila de %Δ.
- **`Venta <mes>`** (tablas `Tabla2`, `Tabla22`): detalle por producto, **dos bloques lado a lado**. Columna "% Δ" en realidad contiene el **delta absoluto en pesos**; "% Δ2" es el delta de share. Encabezado "Venta Agosto" en la hoja "Venta Septiembre". [V]
- **`Tablas`**: Top 10 crecimiento / decrecimiento (dos bloques lado a lado) con `VLOOKUP` a la tabla del periodo anterior y `IFERROR(E-F,0)`. **El `IFERROR(...,0)` convierte "producto sin venta previa" en 0**, justo lo que el prompt maestro prohíbe. [V]
- **`Negados`**: 3 bloques lado a lado (producto, producto duplicado, resumen por "Alta"). En Q3 el rótulo dice *"Q3 juli y septiembre"*. [V]
- **`listo`**: copia de trabajo con abreviaturas ("ae", "ab", "ac"). **`Hoja1`** (Q3): residual con "Venta Abril". **`AETOP 2025`**: tabla de canales 2025 sin periodo explícito. [V]
- Encabezados incorrectos en Q3: `Q3 Jul a Sep 2026` dice **"Venta Junio"**. [V]

### 4.2 GLP-1 (hojas `1` … `9`)

| Hoja | Contenido |
|---|---|
| 1 | Edad (filas 2–7), Sexo (desde A10) y Dispositivo (desde A16): Visitas, Usuarios, ATC, recurrentes, nuevos, Share, %Δ |
| 2 | Edad × producto (Mounjaro / Rybelsus), dos bloques |
| 3 | Producto × Sexo |
| 4 | Región (bloque izquierdo = periodo actual; **bloque derecho = periodo anterior** con Monto y Share) + tráfico por estado (desde A12) |
| 5 | Forma de pago + (bloque derecho anterior), Modo de entrega (desde A10) y Embudo (desde A17) |
| 6 | Negados por producto |
| 7 | Productos |
| 8 | Programa de lealtad |
| 9 | Fuentes de tráfico (bloques actual/anterior; **10 fórmulas** en el total) |

Problemas [V]:
- **La columna `Share` vale 0 en casi todas las filas** (son valores literales, no fórmulas). En el PPTX sí hay shares (44%, 81%…): hoy se **calculan fuera del Excel**. En la hoja 7 aparece `0.125441` en filas sueltas (arrastre de otra tabla).
- Los nombres de forma de pago cambian de ortografía entre el bloque actual y el anterior ("Tarjeta de Credito" / "Tarjeta de Crédito", "Debito" / "Débito"), lo que rompe un cruce por nombre exacto.
- Filas vacías intercaladas (hoja 3), subtotales mezclados con datos (hoja 9, última fila).
- `Tiempo de interacción` es texto `hh:mm:ss`.
- Cabeceras con errores tipográficos de origen: `& de rebote`, `{`.

### 4.3 Hallazgos adicionales (Fase 4a, detectados por el motor sobre el Excel real)

- **Pedidos por canal sobrecontados:** Σ pedidos de los 4 canales = 2,998 vs 1,427 del panorama (≈2.1×). Los Tickets pegados por canal sí cuadran con el total (Monto ÷ ticket = 395 + 385 + 448 + 199 = 1,427). El PPTX publica esos pedidos inflados (p. ej. Llamadas Google +186 %). En líneas y panorama, Ticket = Monto ÷ Pedidos **sí** coincide. **[P]** Definir cómo se cuentan los pedidos por canal. Mientras tanto el motor usa el Ticket pegado en canales y lo marca (`TICKET_FORMULA_UNVERIFIED`).
- **Grupo con periodo distinto en la misma tabla:** en canales MoM, WHATSAPP dice "Julio → Agosto" y los demás "Agosto → Septiembre" (`PERIOD_LABELS_INCONSISTENT`).
- **Redondeo:** el PPTX usa mitad hacia arriba (0.625 → +63 %); `round()` de Python daría 62 %. El formato de presentación lo implementa explícitamente.
- Share de canal y línea = Monto ÷ **total del panorama del mismo periodo** (verificado: APP FESA 2025 = 16.47 %). Resuelve la duda de denominador para AETOPS.

---

## 5. Brecha: app actual vs originales

| Aspecto | Original | App actual |
|---|---|---|
| Plantilla | PPTX con logos, barras, fuentes, formato condicional | Se arma desde cero con PptxGenJS, paleta azul propia |
| Gráficas | Casi ninguna (1 embudo nativo) | Agrega barras que no existen en el original |
| Tablas | Con bloques por canal/línea, celdas combinadas, color por signo | Tablas planas |
| Diapositivas | AETOPS 11/8, GLP-1 11 | ~6–8, estructura distinta |
| Narrativa | Redactada por un analista | Frases fijas |
| Periodos | YoY + MoM (mensual), solo YoY (trimestral) | Un solo "anterior" |
| Faltante vs cero | `IFERROR→0`, celdas vacías | `?? 0` en el código |
| Nota manual | Incidencias por diapositiva | No existe |

**Consecuencia:** el generador actual no es un punto de partida para la fidelidad; sirve como prototipo del flujo.

---

## 6. Qué se puede automatizar / qué no

**Automatizable (determinístico):** todas las tablas numéricas (YoY, MoM, canales, líneas, categorías, productos, negados, share, %Δ, Size B, V. Paciente, ticket), orden de Top N, colores por signo, y el pie de página/logos (son plantilla).

**Requiere intervención humana:**
- Narrativa y conclusiones (hoy redactadas a mano; la IA puede proponerlas con datos ya calculados, con revisión).
- Notas de incidencia ("afectación de 10 minutos").
- Selección de periodos de comparación y confirmación del periodo real del Excel.
- Decidir cuántas filas mostrar (Top 20 / 10 / 15) cuando el contenido no cabe.
- Rótulos de diapositiva cuando el original está cruzado (§3.1).

---

## 7. Pendientes de validación (preguntas abiertas)

1. ¿El Excel "Septiembre" de AETOPS debía traer Septiembre? Hoy trae Agosto. ¿Es un error de carga o el archivo de ejemplo?
2. ¿GLP-1 trimestral = formato de la Radiografía, o el mensual con comparativo trimestral? ¿Hay PPTX Q de referencia?
3. ¿Qué diapositivas llevan MoM en trimestral? (Q1 solo muestra YoY.)
4. ¿Cuál rótulo es correcto en Agosto: "Líneas" o "Canales" (§3.1)?
5. Denominador de **Share** en GLP-1 (¿total de regiones mostradas o total del periodo?): el Excel trae 0.
6. Redondeo: %Δ se muestra con 0, 1 o 2 decimales según la tabla (GLP-1 diap. 1–7: 0; diap. 8: 2; diap. 10: 1). ¿Se unifica?
7. Regla del Top N de productos (README menciona ~80 % acumulado, mínimo 8, máximo 15; los originales muestran 20 y 10). ¿Cuál vale?
8. ¿Excluir productos con venta 0 en ambos periodos? (Aparecen filas con `$0` en Agosto, diap. 6.)
9. Los PPTX tienen fórmulas de color (verde/rojo/amarillo): ¿umbral del amarillo? (visto en "0%"; el −3% aparece en rojo).

---

## 8. Decisión de arquitectura (propuesta)

El prompt pide **usar los PPTX originales como plantilla, con texto y tablas editables, validación visual y PDF fiel**. Con la app 100 % estática actual eso es limitado:

| Opción | Fidelidad | PDF fiel | Esfuerzo | Notas |
|---|---|---|---|---|
| **A. Mantener navegador + PptxGenJS** | Media-baja (reconstrucción) | No (no hay motor de render) | Bajo | No conserva logos/tema original sin reimplementarlos |
| **B. Navegador + plantilla XML** (rellenar el `.pptx` original con JSZip) | Alta en tablas/texto | No | Medio | Sin backend, pero complejo editar tablas dinámicas |
| **C. Backend Python** (`python-pptx` sobre plantilla original + LibreOffice → PDF) | Alta | Sí (render real) | Medio-alto | Requiere hosting; los datos salen del navegador (documentar seguridad) |

**Recomendación:** **C** para PPTX/PDF (es la única que cumple "PDF = PPTX" y validación visual con render real), conservando el motor de importación/cálculo en JavaScript para la validación previa si se desea. Si se exige 100 % local/estático, **B** es el mejor compromiso, sin PDF fiel. **Decisión del usuario requerida.**

## 8.1 Decisiones del usuario (2026-11-02)

- **Arquitectura: aprobada la opción C** (backend Python con `python-pptx` sobre las plantillas originales + LibreOffice para el PDF).
- **Los archivos recibidos son ejemplos.** Los desajustes de periodo (§1, puntos 4–5) y los PPTX/Excel faltantes (§2) no bloquean la construcción: la herramienta debe entender la *estructura* y validar el periodo en tiempo de ejecución, no depender de estos archivos concretos.
- Las preguntas abiertas del §7 se resuelven como **reglas configurables** (redondeo, Top N, umbral de color, denominador de Share) con valores por defecto tomados de los originales, no como bloqueos.

## 9. Siguiente paso propuesto

1. Definir los valores por defecto de las reglas del §7 a partir de los originales (configurables).
2. Diseño técnico (Fase 3) de la opción C.
3. Después: (a) reescribir el importador con **mapeo de bloques** por hoja, (b) pruebas de cálculo contra los PPTX (tolerancia 0), (c) plantillas por formato.

Matriz de trazabilidad: ver [`MATRIZ_TRAZABILIDAD.md`](MATRIZ_TRAZABILIDAD.md).
