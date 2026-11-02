# Machotes sintéticos de GLP-1

`GLP1_sintetico_limpio.xlsx` y `GLP1_sintetico_con_defectos.xlsx` usan el **formato operativo real** (hojas `1`–`9`)
con cifras **inventadas** (semilla fija). No son ventas reales. La hoja `LEEME_SINTETICO` (al final) lo indica.

| Archivo | Para qué |
|---|---|
| `GLP1_sintetico_limpio.xlsx` | Flujo feliz: totales coherentes entre hojas (visitas, ventas, pedidos = compras del embudo). |
| `GLP1_sintetico_con_defectos.xlsx` | Defectos reales plantados: Share = 0, encabezado `& de rebote`, fila en blanco, subtotal y producto repetido, monto negado negativo, ortografía distinta en Forma de Pago. |

Regenerar: `python tools/make_glp1_synthetic.py <salida.xlsx> [--defectos]`. Funcionan también con la app web actual.
