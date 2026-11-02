# Matriz de trazabilidad — Report Intelligence (Fase 1)

Estado: **V** = coincide numéricamente con el PPTX de referencia · **I** = inferido por encabezados/estructura · **P** = pendiente de validación (no se inventa metodología).
Redondeo y formato salen del PPTX original (ver §Reglas). Los periodos de los Excel recibidos no coinciden con los PPTX (ver `DIAGNOSTICO_FASE1.md` §2), por eso **V** significa "la cifra del Excel es igual a la del PPTX de ese periodo", no "el archivo es del periodo indicado".

## A. AETOPS mensual (ref.: `Resultados_AETOP_Agosto_2026.pptx`)

| Diap. | Indicador / tabla | Excel · hoja · rango | Campo(s) | Transformación | Agregación | Periodo | Estado |
|---|---|---|---|---|---|---|---|
| 1 | Monto, Piezas, Pacientes, Pedidos, Productos vendidos (YoY) | `Base` B3:H4 | Monto Venta, Piezas, Pacientes, Pedidos, Producto Vendidos | Valor pegado (2025 y 2026) | Total del mes | Mes actual vs mismo mes año anterior | **V** |
| 1 | Ticket Promedio | `Base` G3:G4 | Ticket Promedio | Monto ÷ Pedidos (en Excel viene como valor, no fórmula) | Total | ídem | **V** (11,560,021/1,427 = 8,100.93) |
| 1 | Size B | `Base` I3:I4 | — | Piezas ÷ Pacientes (`=D/E`) | Total | ídem | **V** (1,304/781 = 1.67) |
| 1 | V. Paciente | `Base` J3:J4 | — | Monto ÷ Pacientes (`=C/E`) | Total | ídem | **V** (10,312.24) |
| 1 | %Δ YoY (fila de variaciones) | `Base` C5:J5 | — | (Act − Ant) ÷ Ant | Total | ídem | **V** (+67%, +63%, +44%, +60%…) |
| 1 | Panorama MoM | `Base` filas 8–12 | mismas columnas | Valor pegado; %Δ en fila siguiente | Total | Mes actual vs mes anterior | **P** (en el Excel recibido "Agosto" = "Septiembre") |
| 2/4 | Tabla por **canal** YoY (APP FESA, ECOMMERCE, LLAMADAS GOOGLE, WHATSAPP) | `Base` filas 13–37 (bloque por canal: 2025, 2026, %Δ) | 7 métricas + Share | Valores pegados; %Δ por métrica | Canal | YoY | **I** (rótulo de diapositiva cruzado, ver §7.4) |
| 3/5 | Tabla por canal MoM | `Base` filas 38–56 | ídem | ídem | Canal | MoM | **I** |
| 2/4 | Tabla por **línea** (AE-A/B/C, HYR) YoY | `Base` filas 57–95 | ídem | ídem | Línea AETOP | YoY | **I** |
| 5 | Tabla por línea MoM | `Base` (bloque MoM de líneas, ~filas 96–138) | ídem | ídem | Línea AETOP | MoM | **P** (rango sin confirmar) |
| 6 | Top productos (Sivec, Producto, AETOP, Canales, Venta actual, anterior, Delta) | `Tablas` A:G | Sivec…Delta | Delta = Venta actual − Venta anterior; anterior vía `VLOOKUP(Sivec)` a `Venta <mes anterior>`; `IFERROR(…,0)` | Producto | Mes vs mes anterior | **V** (Prolia 1,087,846 / 878,673 / 209,173) |
| 6 | Orden y corte del Top | `Tablas` | — | Orden por venta actual desc.; el PPTX muestra 20 filas | Producto | — | **P** (regla de corte) |
| 7 | Mayor crecimiento / decrecimiento (10 + 10) | `Tablas` A:G (izq.) y I:O (der.) | ídem | Orden por Delta desc./asc.; 10 filas | Producto | MoM | **I** |
| 8–9 | Categorías YoY / MoM | `Base` fila 96+ / 139+ | Categoría + 8 métricas | Valores pegados; %Δ | Categoría | YoY / MoM | **I** |
| 10 | Negados por **Alta** (AE-A/B/C) | `Negados` O:S · `listo` A:D | Alta, Pedidos, Cantidad Negada, Monto Negado, Share | Share = Monto negado ÷ Total negado | Línea | Mes | **V** (AE-A: 61, 98, 1,146,774, 47%) |
| 10 | Negados por producto (Top) | `Negados` A:F | Nombre, Alta, Pedidos, Cantidad, Monto, Share | Orden por monto desc. | Producto | Mes | **V** (Hydrea 71 / 103 / 293,584 / 12%) |
| 11 | Conclusiones (viñetas con %YoY/%MoM) | — | Resultados de diap. 1 | Texto con cifras calculadas | — | — | **P** (narrativa; cifras sí trazables) |

## B. AETOPS trimestral (ref.: `Resultados_AETOP_Q1_2026.pptx`; Excel recibido: Q3)

| Diap. | Indicador | Excel · hoja · rango | Transformación | Periodo | Estado |
|---|---|---|---|---|---|
| 1 | Panorama YoY (sin MoM) | `Base` B3:J5 | Igual que mensual; Q3 2026 = 33,925,038 vs 21,310,695 | Trimestre vs mismo trimestre año anterior | **I** (sin PPTX Q3 para comparar; fórmulas idénticas a mensual) |
| 2–3 | Líneas / Canales YoY | `Base` (misma estructura) | ídem | YoY | **P** (no hay PPTX Q3) |
| 4–5 | Productos Top 20; crecimiento/decrecimiento | `Q3 Jul a Sep 2026`, `Q3 Jul a Sep 2025`, `Tablas` | Delta = Actual − mismo trimestre año anterior | YoY | **P** (rótulos del Excel dicen "Venta Junio") |
| 6 | Categorías YoY | `Base` | ídem | YoY | **P** |
| 7 | Negados | `Negados` (rótulo "Q3 juli y septiembre") | ídem mensual | Trimestre | **I** |

## C. GLP-1 mensual (ref.: `Resultados_GLP1_Agosto_2026.pptx`; Excel: `GLP1_…_Septiembre_MoM`)

| Diap. | Indicador / tabla | Excel · hoja | Campo(s) | Transformación | Estado |
|---|---|---|---|---|---|
| 1 | Visitas por Edad | `1` | Edad, Visitas, Total de usuarios, Add to Cart, Recurrentes, Nuevos | Share = Visitas ÷ Total visitas (el Excel trae 0) ; %Δ = (act − ant) ÷ ant | **P** (denominador del share; Excel de otro mes) |
| 1 | Sexo, Dispositivo | `1` (Sexo desde A10 y Dispositivo desde A16, apilados bajo la tabla de Edad) | ídem | ídem | **I** (mismo bloque de columnas; share pendiente como arriba) |
| 2 | Edad × Mounjaro / Rybelsus | `2` (dos bloques lado a lado, 30 col.) | ídem + `% de rebote` | %Δ viene calculado | **I** |
| 3 | Producto × Sexo | `3` | Visitas…Tiempo de interacción (`hh:mm:ss`), rebote, %Δ | Filas en blanco intercaladas = separadores | **I** |
| 5 | Región (venta) | `4` (izq. actual, der. anterior) | Pedidos, Piezas, Monto, Pacientes, Ticket, Share, %Δ | Ticket = Monto ÷ Pedidos; Share = Monto ÷ Total; %Δ contra bloque derecho | **P** (Centro 1,211 pedidos en Excel vs 1,316 en PPTX Agosto: periodos distintos) |
| 5 | Tráfico por estado | `4` (desde A12, bajo la tabla de Región) | Región (Ciudad de México, Jalisco…), Visitas…Nuevos, %Δ | %Δ viene calculado | **I** |
| 6 | Forma de pago | `5` | Pedidos, Piezas, Monto, Pacientes, Ticket, Share, %Δ | idem; ortografía distinta entre bloques | **P** |
| 6 | Modo de entrega | `5` (desde A10, bajo Forma de pago) | Pedidos…Share, %Δ | Share = Monto ÷ Total | **I** |
| 7 | Embudo (Ver producto → Compra, carritos abandonados) | `5` (desde A17: Ver producto, Agregar a carrito… carritos abandonados A25) | Conteo y % por etapa | % = etapa ÷ Ver producto | **I** (en el PPTX de Agosto es gráfica nativa `chartEx`) |
| 7 | Negados | `6` | Producto, Pedidos, Piezas, Monto Negado, Pacientes, Ticket, Share, %Δ | Ticket = Monto ÷ Pedidos | **I** |
| 8 | Productos Top 10 | `7` | ídem | Orden por monto; %Δ | **V** (Mounjaro 533 / 581 / 2,694,543 / 455 / 5,055 / −10.57%) |
| 9 | Programas de apoyo | `8` | ídem | ídem | **I** |
| 10 | Fuentes de tráfico | `9` | Categoría, Visitas…Nuevos, %Δ | Bloque derecho = periodo anterior | **I** |
| 11 | Conclusiones | — | — | Narrativa | **P** |
| Todas | Nota de incidencia | — | — | **Entrada manual** | Requiere humano |

## D. GLP-1 trimestral

No hay PPTX de referencia (solo la Radiografía anual 2025). Excel Q3 disponible con la misma estructura de hojas `1`–`9`. **Matriz no construible** hasta recibir el PPTX o confirmar el formato.

## E. Reglas observadas en los PPTX (para el motor)

| Regla | Evidencia | Estado |
|---|---|---|
| Formato moneda `$#,##0` sin decimales (AETOPS Agosto/Q1); con centavos en Nov 2025 | PPTX | **P** (unificar) |
| %Δ: GLP-1 diap. 1–7 → 0 dec.; diap. 8 → 2 dec.; diap. 10 → 1 dec. | PPTX | **P** |
| Ticket Promedio = Monto ÷ Pedidos | Excel/PPTX | **V** |
| Size B = Piezas ÷ Pacientes; V. Paciente = Monto ÷ Pacientes | Fórmulas en `Base` | **V** |
| %Δ = (Actual − Anterior) ÷ Anterior | Fórmulas en `Base` | **V** |
| Producto sin venta previa: celda vacía en PPTX (Nov 2025) pero Delta = monto completo; en Excel `IFERROR→0` | PPTX/Excel | **P** (política de faltante ≠ cero) |
| Color de %Δ: verde `C6EFCE/006100` positivo, rojo `FFC7CE/9C0006` negativo, amarillo neutro (0%) | XML de diapositivas | **I** (umbral exacto sin confirmar) |
| Producto con venta $0 en ambos periodos se muestra con "$0" (AETOPS Agosto, diap. 6) | PPTX | **P** (README del repo dice excluirlos) |
