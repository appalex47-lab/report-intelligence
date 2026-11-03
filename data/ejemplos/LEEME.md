# Archivos de ejemplo (datos inventados que imitan la escala real)

Generados con `python tools/make_realistic_samples.py --salida data/ejemplos --hasta 2026-9`. **No son datos reales.**

| Archivo | Para qué |
|---|---|
| `AETOPS_crudo_ejemplo.xlsx` | AETOPS: 15 meses (`ventas`, `catalogo`, `negados`). Probar mensual Septiembre 2026 y trimestral Q3 2026. Meta sugerida: $12 M (mes) / $34 M (trimestre). |
| `AETOPS_crudo_con_defectos.xlsx` | Mismo formato con errores típicos: SKU fuera del catálogo, fecha ilegible, monto en texto, pedido sin id, valor negativo. Debe **bloquear**. |
| `GLP1_crudo_ejemplo.xlsx` | GLP-1: 15 meses (`ventas`, `catalogo`, `trafico`, `negados`). Mensual y trimestral. Meta opcional sugerida: $14 M (mes) / $40 M (trimestre). |
| `GLP1_crudo_con_defectos.xlsx` | Con errores típicos (SKU inexistente, fecha ilegible, paciente vacío). Debe **bloquear**. |

Escala resultante (Septiembre 2026): AETOPS ≈ $12.3 M, 1,436 pedidos, ticket ≈ $8.5 K, YoY ≈ +58 %;
GLP-1 ≈ $12.7 M, 2,356 pedidos, ticket ≈ $5.4 K.
