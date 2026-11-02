# Contrato de datos (extracción cruda)

> **Estado:** AETOPS (`ventas` + `catalogo` + `negados`) ya está implementado (`backend/app/raw/aetops.py`, probado con datos sintéticos
> `tools/make_raw_synthetic.py`; falta validar con una muestra real). `trafico` y GLP-1 aún no. Propuesta para validar con quien hace la extracción. Reemplazará a los machotes por bloques cuando se construya la
> capa de agregación (hoy el motor lee los machotes; ver `tools/make_machotes.py`). Un archivo por unidad (AETOPS y GLP-1),
> con una tabla por hoja (o un CSV por tabla). El **SKU** (en AETOPS, el Sivec) es la llave común.

## Decisiones ya tomadas
- **IVA, estatus, cancelaciones y devoluciones: no se contemplan.** `monto_venta` se toma tal como viene en la extracción.
- **No se piden:** inventario, precio de lista/descuento, costo/margen (el origen no los tiene).
- **Metas:** se capturan a mano en la herramienta; solo la **meta general** de AETOPS (obligatoria). No hay tabla de metas.
- Negados sigue por separado, como hoy (se le agrega `sku` opcional para cruzarlo con productos sin depender del nombre).
- Ventana de datos: el periodo del reporte + el periodo anterior + el mismo periodo del año anterior (lo simple: **13 meses**).
  Con más meses se llena el historial y las tendencias.
- Identificadores de paciente **anónimos** (hash); nunca nombres ni datos de contacto.

## Tabla 1 · `ventas` (una fila por línea de pedido)
| Columna | Tipo | AETOPS | GLP-1 | Uso |
|---|---|---|---|---|
| fecha_pedido | fecha | obligatoria | obligatoria | periodo, MoM, YoY |
| id_pedido | texto | obligatoria | obligatoria | pedidos (distintos) |
| id_paciente | texto anónimo | obligatoria | obligatoria | pacientes (distintos) |
| paciente_nuevo | SI/NO (**primer pedido histórico** del paciente; confirmado) | obligatoria | obligatoria | captación vs recompra |
| sku | texto | obligatoria | obligatoria | llave al catálogo |
| canal | texto | obligatoria | obligatoria | tabla de canales |
| estado | texto | obligatoria | obligatoria | región |
| sucursal | texto | opcional | opcional | el origen la tiene; hoy no está en el reporte |
| piezas | entero | obligatoria | obligatoria | |
| monto_venta | número | obligatoria | obligatoria | |
| dispositivo / edad / sexo | — | **no existen por pedido** (confirmado) | pendiente (ver abajo) | en AETOPS vienen solo de `trafico` |
| forma_pago | texto | — | obligatoria | |
| modo_entrega | texto | — | obligatoria | |
| programa_lealtad | texto | — | opcional | |

Línea (AE-A/AE-B/AE-C/HYR) y categoría **no** van aquí: salen del catálogo por SKU.
Se calculan: pacientes y pedidos distintos, productos vendidos (SKU distintos), ticket = monto ÷ pedidos, share, %Δ MoM/YoY, Top 20, mayores alzas y bajas.

## Tabla 2 · `catalogo` (una fila por SKU)
sku · producto · linea (AETOPS) · categoria · laboratorio (opcional). Un SKU = una línea y una categoría; si no, error.

## Tabla 3 · `trafico` — **archivo aparte** (confirmado: ventas y analítica web salen de sistemas distintos)
(embudo por producto; una fila por mes × SKU × dispositivo × fuente de tráfico)
mes (AAAA-MM) · sku · dispositivo · fuente_trafico · estado (opcional) · edad_rango (opcional) · sexo (opcional) · sesiones · vistas_producto · add_to_cart · begin_checkout · purchase.
Viene de analítica web: **no** se espera que `purchase` cuadre con las ventas; solo se avisa si la diferencia es grande.
GLP-1: de aquí salen el embudo y el tráfico por fuente y estado.

## Tabla 4 · `negados` (como hoy)
producto · sku (opcional) · alta (línea) · pedidos · cantidad_negada · monto_negado. Un producto sin stock que se negó a la venta.

## Validaciones (bloquean / avisan)
- **Bloquean:** columna obligatoria ausente o renombrada; fecha o número ilegible; SKU de ventas que no está en el catálogo;
  SKU con dos líneas o categorías; ventas fuera de la ventana pedida sin mes anterior / mismo periodo del año anterior;
  periodo elegido sin ventas; `id_paciente` o `id_pedido` vacío.
- **Avisan:** valores negativos (no se trata devolución: se marcan); líneas duplicadas (mismo pedido y SKU); mes con menos de
  X % de las filas del mes anterior (posible extracción incompleta); `purchase` vs ventas con diferencia > 20 %; paciente
  marcado nuevo con pedidos anteriores en la ventana; edad fuera de 0–110; categorías o canales nuevos.

## Qué cambia en el motor
Una capa nueva convierte estas tablas en las mismas estructuras que ya lee el motor (`Table/Group`, `ProductTable`,
`NegadosTable`, `GBlock`). Validaciones de cuadre, narrativa, PPTX, PDF, QA e historial no cambian. Los pacientes distintos
dejan de sumarse entre grupos, así que desaparecen los avisos de totales que no cuadran por esa causa. Se valida contra el
reporte publicado de septiembre antes de usarla.

## Pendiente de confirmar
1. ~~¿Ventas y analítica web del mismo sistema?~~ **No**: `trafico` se carga como segundo archivo por unidad (ventas+catálogo+negados en uno; tráfico en otro). Inventario: no existe, se omite.
2. ~~`paciente_nuevo`~~: primer pedido **histórico**.
3. ~~Estado/edad/sexo por pedido en AETOPS~~: el pedido real solo trae **sucursal y estado**; edad y sexo vienen de analítica (`trafico`).
4. ~~GLP-1 edad/sexo~~: las hojas 1–3 del libro actual ya son de **analítica** (visitas, usuarios, add to cart, nuevos/recurrentes, rebote,
   tiempo de interacción), no de venta. Por tanto edad, sexo y dispositivo salen de `trafico` y **no** van en `ventas`. `trafico` debe
   admitir esas métricas (usuarios, usuarios_nuevos, usuarios_recurrentes, tasa_rebote, tiempo_interaccion).
