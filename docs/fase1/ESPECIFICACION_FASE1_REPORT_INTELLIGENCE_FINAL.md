# Report Intelligence — Especificación de Fase 1 (FINAL)

**Solo documentación.** No se modificó el repositorio, no hay código editado, commits ni funciones nuevas. Nada se implementa hasta recibir autorización explícita (ver §15). Las recomendaciones de §15 **no son autorizaciones**.

Base de código de referencia: `main` @ `c8ba722`.

Archivos de referencia inspeccionados para esta versión: `data/ejemplos/GLP1_crudo_ejemplo.xlsx` y `data/ejemplos/AETOPS_crudo_ejemplo.xlsx` (machotes **sintéticos**; ver §3.0), `docs/CONTRATO_DATOS.md` y el código de lectura de `raw/`.

**Estado de este documento:** versión final de la especificación documental de Fase 1. **Cerrar la especificación no equivale a autorizar la implementación**: las decisiones A-1 a A-8 (§15) siguen pendientes.

## Cambios respecto a v4 (resumen de la versión FINAL)

Detalle en los **Anexos A (cambios), B (inconsistencias resueltas) y C (auditoría de trazabilidad)** y en `INFORME_CIERRE_AUDITORIA_FASE1.md`.

1. **Machotes como fuente de verdad (§3.0, §3.4–3.6, §10.1).** Se inspeccionaron todas las hojas y columnas de ambos Excel. Se corrigieron nombres de campo de v4 que no existían en los machotes (`folio`, `pac_id`, `estatus`), se eliminó la expectativa de una hoja de tráfico en AETOPS y se documentó la aplicabilidad por unidad.
2. **Dos fuentes de pedidos (§3.1, §3.3 `R-CONC-COMPRAS`, §8.2).** «Pedidos del sistema de ventas» y «Compras GA4» están diferenciados; se prohíbe sustituir, sumar o equiparar; el indicador identifica su fuente y se presentan, si ambas, como resultados independientes.
3. **E2 separado del indicador agregado (§8.3).** Tres elementos distintos: escenario histórico E2, métrica heredada `carritos_abandonados` e indicador IND-01. Aclaración obligatoria en salidas nuevas.
4. **Unidad de los carritos (§3.3 `R-COBERTURA-ATC`, §8.2).** Por defecto «unidad no declarada»; el cálculo aritmético se permite con interpretación limitada.
5. **Relaciones superiores a 100 % (§8.2).** Se conserva el valor; advertencia sin afirmar causa.
6. **Pruebas (§11).** Inventario ampliado a 22 obligatorias + 4 condicionales + 2 existentes; orden de ejecución por oleadas, verificado sin ciclos; condiciones de activación explícitas; evidencia esperada por prueba.
7. **Trazabilidad (§14).** Cadena Requerimiento → Regla → Escenario/Indicador → AC → Prueba → Evidencia.
8. **Auditoría integral:** glosario (§3.4), catálogo de fórmulas (§3.5), fichas de escenario (§8.1, §8.3), cobertura de privacidad e IA (§10.8), ambigüedades (§16).
9. **Sin cambios** en: decisiones A-1 a A-8 (siguen pendientes), 25 % y 10 % heredados, fórmulas y cifras actuales, compatibilidad de `severity`, separación sintético/operacional.

## Historial de versiones anteriores

- **v4:** metodología agregada de pedidos contra carritos; `R-REL-PAC-PED` y `R-CUADRE-DIM` formalizadas; inventario de pruebas y AC-19; auditoría cruzada.
- **v3:** abandono por niveles E2-a/b/c (**sustituido en v4**); escenarios solo con 25 % y 10 % heredados; validación sintética vs operacional.
- **v2:** cinco reglas en alcance; procedencia y reproducibilidad; QA estructural vs visual; nomenclatura de hallazgos; matriz de trazabilidad.
- **v1:** decisiones pendientes, definiciones, arquitectura de validación, Fase 1, archivos, pruebas, criterios, riesgos.

## 0. Principios rectores

1. **Ninguna suposición se vuelve regla universal.** Toda definición es una propuesta configurable, con nombre, versión y fuente. Si falta el dato, el sistema responde **«No verificable»** e indica qué falta (archivo, columna, granularidad).
2. **Sin regresiones.** Los cálculos actuales no cambian sin una entrada de cambio justificado (regla, valor antes, valor después, aprobación). Los formatos, importadores y plantillas actuales siguen funcionando.
3. **La IA no introduce ni modifica cifras verificadas.** Fase 1 no amplía sus permisos.
4. **Lo derivado de volúmenes agregados no se presenta como seguimiento individual de carritos ni como ingreso recuperable demostrado.** La relación pedidos/carritos es una relación entre agregados y nunca una conversión individual ni una tasa de abandono (§8.2).
5. **Los datos del usuario no salen del navegador** salvo que el usuario lo decida expresamente (§7.C y §10).
6. **Honestidad sobre límites:** lo que python-pptx o la estimación geométrica no pueden verificar se declara, no se maquilla.
7. **Validación sintética ≠ validación operacional.** Que una regla pase pruebas con datos construidos demuestra que el código hace lo que dice la definición; no demuestra que la definición coincida con tu operación. Hasta la validación operacional, la regla se etiqueta «No validada con datos reales» y no se presenta como regla de negocio confirmada (§10.5).
8. **Metodología agregada vigente.** La comparación de carritos y pedidos se hace con volúmenes agregados. Fase 1 **no exige** ID de carrito, ID de transacción, relación individual ATC–purchase ni ventanas de vinculación (§8.2). Una trazabilidad individual, si algún día se desea, sería una evolución independiente fuera de esta especificación.
9. **Reproducibilidad de las pruebas.** Todo escenario de prueba usa datos sintéticos generados de forma determinista y versionados (§11.4). Ninguna prueba automatizada usa datos reales sin autorización expresa.
10. **Fuentes de pedidos diferenciadas.** Los pedidos del sistema de ventas (hoja `ventas`) y las compras de GA4 (`trafico.compras`) son fuentes distintas con universos y criterios propios. Nunca se sustituyen, se suman ni se presentan como equivalentes, y toda cifra que use una de ellas **nombra su fuente** (§3.1, §8.2).
11. **Fidelidad a los machotes.** La especificación solo menciona hojas, columnas y métricas que existen en los machotes o en el contrato vigente; lo que no existe se documenta como dependencia o como «No aplica». GLP-1 y AETOPS no tienen las mismas fuentes y sus reglas no se extienden de una a otra (§3.0, §3.6).
12. **Una especificación cerrada no es una autorización.** Las decisiones A-1 a A-8 conservan su estado hasta que el usuario las autorice de forma expresa (§15).

---

## 1. Hallazgos del código actual que condicionan el diseño

- `rules.py:21` — `recovery_scenario = 0.25`, aplicado al **monto negado**.
- `rules.py:25` — `cart_recovery_scenario = 0.10`, aplicado como `carritos_abandonados × 10 % × ticket promedio` (`glp1_exec.py:98`).
- `raw/glp1.py:333` y `docs/CONTRATO_DATOS.md`: si la columna `carritos_abandonados` viene vacía, el motor la **deriva** como `add_to_cart − compras` y lo marca como «derivado».
- El embudo calcula tasas contra «Ver producto». **No existe hoy en el motor un indicador con la denominación «Relación pedidos/carritos»**: la metodología descrita en §8.2 es la operación vigente del negocio y Fase 1 la incorpora como salida nueva (ver AMB-8).
- `ventas` (sistema de ventas) y `trafico` (analítica web) **son archivos y sistemas distintos** (contrato vigente). El motor ya los compara solo con un aviso: `TRAFICO_PURCHASE_DIFFERS` si `compras` difiere más de 20 % de los pedidos del periodo (`raw/glp1.py:350`).
- Las hojas de `ventas` de los machotes **no tienen columna de estatus de pedido**: `estado` es la entidad federativa. El contrato vigente decide que IVA, estatus, cancelaciones y devoluciones no se contemplan.
- AETOPS **no tiene hoja `trafico`** (el contrato indica que AETOPS aún no usa `trafico`).

Consecuencia: la etiqueta «carritos abandonados» y su cifra monetaria en la lámina actual son una **métrica agregada heredada**, no un abandono comprobado. Cambiar su texto o su cifra es un **cambio de láminas actuales que requiere tu autorización** (A-3). **Sin esa autorización, las láminas, fórmulas y cifras actuales no cambian.** Las salidas **nuevas** de Fase 1 no usan la expresión «abandono comprobado» ni calculan abandono (§8.2, §8.4).

---

## 2. Decisiones técnicas con recomendación por defecto

| # | Decisión | Recomendación | Estado |
|---|---|---|---|
| D1 | Definiciones de métricas | Catálogo versionado y configurable (§3) | Aprobado como base |
| D2 | ¿Qué unidad reporta la fuente en «carritos agregados» (eventos, sesiones u otra)? | Por defecto «unidad no declarada»: el cálculo aritmético se permite con interpretación limitada; el usuario puede declararla en la configuración. **No se requiere ningún identificador** (los machotes no la declaran) | Declaración del usuario; no bloquea (AMB-2) |
| D3 | «Responsable sugerido» | Solo «área sugerida» genérica | Pendiente |
| D4 | «Tiempo de interacción» | No ampliar; mostrar con etiqueta de fuente | Pendiente |
| D5 | Reestructurar el deck | Solo agregar el anexo de calidad de datos | Pendiente |
| D6 | Porcentajes de escenarios | Solo los heredados (25 % y 10 %), rotulados «Supuesto heredado, no validado»; conservador/optimista posteriores (§8.0) | Confirmación en A-4 |
| D7 | Preview/QA del PPTX | Estructural en navegador + visual en Actions o local (§7) | Aprobado como base |
| D8 | Mantener ruta de plantillas fijas | Sí | Pendiente |
| D9 | Datos reales de prueba | Extractos anonimizados (§10). **Opcionales para iniciar Fase 1**: sin ellos, las reglas dependientes salen «No validadas con datos reales» | Pendiente (no bloquea el inicio) |

---

## 3. Definiciones y reglas propuestas

### 3.0 Fuentes de datos: los machotes de referencia

**Archivos inspeccionados** (todas las hojas, encabezados y contenido): `data/ejemplos/GLP1_crudo_ejemplo.xlsx` y `data/ejemplos/AETOPS_crudo_ejemplo.xlsx`. Las copias de trabajo en `/tmp/ej/` son idénticas en contenido (difieren solo en metadatos del archivo). Según `data/ejemplos/LEEME.md` **son datos inventados que imitan la escala real; no son datos reales**. Toda cifra observada en este documento proviene de esos machotes sintéticos y **no constituye evidencia operacional**.

**Estructura real de los machotes**

| Unidad | Hoja | Filas | Columnas (orden real) | Qué representa |
|---|---|---|---|---|
| GLP-1 | `ventas` | 35 461 | `fecha_pedido`, `id_pedido`, `id_paciente`, `paciente_nuevo`, `sku`, `canal`, `estado`, `region`, `piezas`, `monto_venta`, `forma_pago`, `modo_entrega`, `programa_lealtad` | Sistema de ventas; **una fila por línea de pedido** |
| GLP-1 | `catalogo` | 16 | `sku`, `producto`, `categoria` | Un SKU = un producto y una categoría |
| GLP-1 | `trafico` | 1 260 | `mes`, `vista`, `valor`, `sku`, `visitas`, `usuarios`, `usuarios_nuevos`, `usuarios_recurrentes`, `vistas_producto`, `add_to_cart`, `begin_checkout`, `compras`, `carritos_abandonados`, `sesiones_rebote`, `segundos_interaccion_total` | Analítica web (GA4 u otra), **agregada por mes × vista × valor × SKU opcional** |
| GLP-1 | `negados` | 5 | `producto`, `sku`, `alta`, `pedidos`, `cantidad_negada`, `monto_negado` | Productos sin stock negados a la venta; **sin columna de fecha** |
| AETOPS | `ventas` | 22 466 | `fecha_pedido`, `id_pedido`, `id_paciente`, `paciente_nuevo`, `sku`, `canal`, `estado`, `sucursal`, `piezas`, `monto_venta` | Sistema de ventas; una fila por línea de pedido |
| AETOPS | `catalogo` | 28 | `sku`, `producto`, `linea`, `categoria`, `laboratorio` | Un SKU = una línea y una categoría |
| AETOPS | `negados` | 14 | `producto`, `sku`, `alta`, `pedidos`, `cantidad_negada`, `monto_negado` | Igual que GLP-1; `alta` trae la línea (AE-A, AE-B, AE-C, HYR) |
| AETOPS | **(no existe `trafico`)** | — | — | El contrato vigente indica que AETOPS aún no usa `trafico` |

**Diferencias entre unidades (no se extienden de una a otra)**

| Aspecto | GLP-1 | AETOPS |
|---|---|---|
| Hoja `trafico` (analítica) | Sí | **No** |
| Columnas propias de `ventas` | `region`, `forma_pago`, `modo_entrega`, `programa_lealtad` | `sucursal` |
| `catalogo` | `sku` (texto), `producto`, `categoria` | `sku` (numérico), `producto`, `linea`, `categoria`, `laboratorio` |
| `canal` (valores en el machote) | 1 (`ECOMMERCE`) | 4 (`WHATSAPP`, `LLAMADAS GOOGLE`, `APP FESA`, `ECOMMERCE`) |
| `negados.alta` | Vacía en todas las filas del machote | Línea (AE-A, AE-B, AE-C, HYR) |
| Compras GA4, carritos agregados, relación pedidos/carritos, `R-CONC-COMPRAS`, escenario E2 | **Aplican** | **No aplican** (sin `trafico`) |

**Clasificación de los datos**

| Clase | Elementos |
|---|---|
| **Campos disponibles** (columnas del machote) | Las de la tabla anterior |
| **Campos derivados** (los calcula el motor) | Pedidos únicos (`id_pedido` distintos), pacientes únicos (`id_paciente` distintos), ticket = `monto_venta` ÷ pedidos, participaciones, %Δ MoM/YoY; línea y categoría vía `catalogo`; `carritos_abandonados` cuando viene vacío (`add_to_cart − compras`, marcado «derivado»); tasa de rebote = `sesiones_rebote` ÷ `visitas`; tiempo de interacción = `segundos_interaccion_total` ÷ `visitas` |
| **Datos de otras integraciones** | Las métricas de `trafico` provienen de GA4 u otra herramienta de analítica y se **cargan como archivo**; la herramienta **no consulta GA4 en línea**. Las metas se capturan a mano. Estatus de pedido, cancelaciones, devoluciones, IVA, inventario, descuento y costo **no existen** y no se contemplan |

**Observaciones medidas en los machotes sintéticos** (hechos del archivo, no reglas ni evidencia operacional)

| ID | Observación | Consecuencia para esta especificación |
|---|---|---|
| OBS-01 | `estado` contiene entidades federativas (p. ej. `VERACRUZ`); **no hay columna de estatus de pedido** | Las clases de estatus de `R-REL-PAC-PED` quedan reservadas e inactivas (§3.3) |
| OBS-02 | GLP-1: 33 486 pedidos únicos, 7 184 pacientes únicos; AETOPS: 16 548 pedidos únicos, 3 817 pacientes únicos | Valores de referencia de los machotes |
| OBS-03 | Ningún `id_pedido` tiene más de un `id_paciente`, más de una `fecha_pedido` o filas idénticas duplicadas (en ambos) | Las clases contradictorias no aparecen en los machotes; se prueban con fixtures sintéticas dedicadas |
| OBS-04 | En AETOPS, `sucursal`, `linea` y `categoria` varían **dentro de un mismo pedido** (5 457, 3 796 y 4 563 pedidos); en GLP-1 ningún atributo de `ventas` ni `categoria` varía dentro de un pedido | Pedidos por `sucursal`/línea/categoría en AETOPS no son una dimensión exclusiva (§3.3 `R-CUADRE-DIM`) |
| OBS-05 | Un mismo paciente aparece con más de un valor de `estado` (GLP-1: 5 592; AETOPS: 2 807), de `canal` (AETOPS: 2 606) y de `sucursal` (AETOPS: 3 214) | Pacientes únicos por esas dimensiones no son exclusivos |
| OBS-06 | `paciente_nuevo` es un atributo por pedido (primer pedido histórico, confirmado en el contrato); 5 735 pacientes de GLP-1 y 2 975 de AETOPS tienen ambos valores | Es esperado; la regla `R-REL-PAC-PED` no lo usa |
| OBS-07 | En `trafico`, `carritos_abandonados = add_to_cart − compras` en las 1 260 filas | Propiedad del machote sintético, coincide con la derivación del contrato; no prueba cómo lo define GA4 |
| OBS-08 | `trafico` tiene nivel sitio (`vista = general`, `sku` vacío, 15 filas, una por mes) y desgloses por `edad`, `sexo`, `dispositivo`, `fuente`, `estado`. Los desgloses **no suman** el total `general` (sept-2026: `add_to_cart` general 18 883; `dispositivo` 3 642; `edad` 7 973) | Los carritos agregados se toman **solo del nivel sitio**; ningún desglose se declara exhaustivo |
| OBS-09 | `trafico` es mensual; `ventas` es diaria (`fecha_pedido`) | La comparación se hace a nivel mes (o trimestre = tres meses); usuarios no son aditivos entre meses, conteos sí |
| OBS-10 | Sept-2026 (GLP-1): pedidos del sistema de ventas 2 356; compras GA4 2 643; carritos agregados (`add_to_cart`) 18 883. Relaciones: 12,48 % (ventas) y 14,00 % (GA4); diferencia compras vs pedidos +12,18 % | Ilustración de dos fuentes distintas con cifras distintas (§8.2); en el machote ninguna relación supera 100 % (máx. 14,5 %) |
| OBS-11 | `negados` no trae fecha; `monto_negado` se toma del periodo del reporte por convención operativa | Limitación declarada de E1 (§8.1) |
| OBS-12 | Todos los `sku` de `ventas` y `negados` existen en `catalogo` en ambos machotes | Consistente con la validación vigente (SKU fuera de catálogo bloquea) |

**Diccionario de términos de esta especificación frente a los machotes**

| Término del documento | Columna / origen en el machote |
|---|---|
| Pedido del sistema de ventas | `ventas.id_pedido` (valores distintos) |
| Folio | Alias histórico de v1–v4; **equivale a `id_pedido`**. En adelante se usa `id_pedido` |
| Paciente | `ventas.id_paciente` (valores distintos) |
| Fecha del pedido | `ventas.fecha_pedido` |
| Línea de pedido | Una fila de `ventas` |
| Venta / monto | `ventas.monto_venta` |
| Compra GA4 | `trafico.compras` (evento `purchase` de la analítica), nivel sitio |
| Carrito agregado | `trafico.add_to_cart` (nivel sitio), en la unidad que reporte la fuente |
| Carritos abandonados (métrica heredada) | `trafico.carritos_abandonados` (dato o derivado `add_to_cart − compras`) |
| Estatus de pedido | **No existe** en los machotes ni en el contrato |
| Estado | `ventas.estado` = entidad federativa. **No** es estatus ni es `estado_verificacion` |

### 3.1 Catálogo de definiciones (propuesta, no regla universal)

| Término | Definición propuesta | Fuente requerida (columna) | Si falta |
|---|---|---|---|
| **Visita / Sesión** | Periodo de actividad según la herramienta de analítica. No se asume visita = sesión; el contrato nombra la columna `visitas` y la describe como sesiones | `trafico.visitas` (solo GLP-1) | «No verificable: falta columna» / «No aplica» en AETOPS |
| **Evento** | Interacción registrada (`vistas_producto`, `add_to_cart`, `begin_checkout`, `compras`). Un evento no es una persona, sesión ni carrito individual | `trafico` por columna (solo GLP-1) | «No verificable» para esa columna |
| **Usuario** | Usuario de analítica; no aditivo entre meses ni entre desgloses | `trafico.usuarios` (solo GLP-1) | «No verificable» |
| **Carritos agregados** | Volumen agregado de la métrica `add_to_cart` a **nivel sitio** en el periodo, **en la unidad que reporte la fuente** (eventos, sesiones u otra; por defecto «unidad no declarada»). Es un **volumen**, no una lista de carritos identificables | `trafico.add_to_cart` (`vista = general`, `sku` vacío) | «No calculable» para la relación pedidos/carritos |
| **Pedido del sistema de ventas** | Cada `id_pedido` distinto del archivo `ventas` con `fecha_pedido` en el periodo. Fuente de verdad de ventas | `ventas.id_pedido` | Bloqueo vigente por `id_pedido` vacío |
| **Compra GA4** | Valor de `trafico.compras` (evento `purchase` de la analítica) a nivel sitio. **No es sinónimo de pedido del sistema de ventas** | `trafico.compras` (solo GLP-1) | «No verificable» |
| **Pedido (sin calificar)** | **No se usa sin calificar la fuente** en reglas, fórmulas ni salidas nuevas: siempre «pedido del sistema de ventas» o «compra GA4» | — | — |
| **Paciente** | `id_paciente` distinto; nuevo/recurrente según `paciente_nuevo` (primer pedido histórico) | `ventas.id_paciente` | Bloqueo vigente por `id_paciente` vacío |

### 3.2 Denominadores
Todo ratio publicado muestra su denominador **y la fuente de cada término** (p. ej. `Relación = pedidos del sistema de ventas / carritos agregados`). Denominador 0 o ausente ⇒ «No verificable» o «No calculable», nunca 0 %. Un mismo ratio en dos láminas usa el mismo denominador. Numerador y denominador de archivos o fuentes distintos solo se combinan sin reservas si cubren **mismo periodo y mismo alcance**; si no, el cálculo se muestra con su limitación (en IND-01: `calculable_con_limitacion`, §8.2) o se marca *conciliación parcial*.

### 3.3 Las cinco reglas de Fase 1 (definición funcional)

**R-REL-PAC-PED — Pacientes únicos vs pedidos únicos del sistema de ventas.**

La regla opera **exclusivamente sobre pedidos únicos (`id_pedido` distintos) y pacientes únicos (`id_paciente` distintos), nunca sobre el número de filas**. Solo **clasifica y compara**: no filtra, no corrige y no sustituye ninguna cifra del motor ni de las láminas actuales. Aplica a GLP-1 y a AETOPS (ambas tienen `ventas`).

*Definiciones inequívocas*
- **Pedido único:** cada valor distinto de `id_pedido` en `ventas`. Un pedido tiene una o más **líneas** (filas).
- **Paciente único:** cada valor distinto y no nulo de `id_paciente`. Mismo identificador = mismo paciente (sin normalización difusa; la anonimización conserva igualdad).
- **Duplicados:** (i) varias filas con el mismo `id_pedido` son **líneas** del mismo pedido; (ii) filas idénticas en todas sus columnas son **duplicados exactos**; (iii) el contrato ya avisa de **líneas duplicadas** (mismo `id_pedido` y `sku`). Ninguno altera los conteos de valores distintos; (ii) y (iii) se **informan** (`informar`) con su cantidad y **no se eliminan** (una línea repetida puede ser legítima).
- **Pedido o paciente recurrente:** atributo de la fuente (`paciente_nuevo`: primer pedido histórico). La regla **no lo usa ni lo infiere**. Un paciente con historial previo y un solo pedido en el periodo es válido.
- **Cancelación:** **no es identificable** con los machotes ni con el contrato vigente (no existe columna de estatus; el contrato excluye estatus y cancelaciones). Todo `id_pedido` presente se trata como pedido. Es una **limitación declarada**, no una omisión.
- **Universo** `U = (archivo `ventas`, periodo, filtros de unidad declarados)`.
- **Parámetro `m` = `max_pacientes_por_pedido`** (entero ≥ 1, default 1): máximo de `id_paciente` distintos que un pedido único puede declarar legítimamente. No limita cuántos pedidos puede tener un paciente.

*Atributos por `id_pedido` `f`* (sobre todas sus líneas del archivo): `Fechas(f)` = valores distintos de `fecha_pedido`; `Pac(f)` = `id_paciente` distintos no nulos; `k(f) = |Pac(f)|`; `Estatus(f)` = estatus distintos **solo si existe una columna de estatus mapeada** (hoy no existe). Un `id_paciente` nulo en una línea se ignora.

*Clasificación exhaustiva y excluyente de pedidos (en este orden; cada `id_pedido` cae en exactamente una clase)*

| Clase | Condición | Estado con los machotes | ¿Entra al universo `O_U`? |
|---|---|---|---|
| **C0 Excluido por estatus** | Todos sus estatus ∈ `estatus_excluidos` | **Reservada e inactiva** (sin columna de estatus: C0 = ∅) | No |
| **C1 Estatus mixto** | Tiene estatus excluidos y no excluidos | **Reservada e inactiva** (C1 = ∅) | No: se cuenta y se lista aparte |
| **C2 Fecha contradictoria** | `|Fechas(f)| > 1` | Activa | **No**: sin fecha única no puede asignarse a un periodo; se cuenta y se lista aparte |
| **E Elegible** | Resto (una sola fecha; sin estatus excluido) | Activa | Sí, en el periodo que contiene su `fecha_pedido` |

Las clases C0 y C1 solo se activan si una decisión **futura y expresa** incorpora una columna de estatus al contrato y a `mapeo_columnas.json` (AMB-4). Mientras tanto `estatus_excluidos = null` y no se evalúan; no está permitido suponer que `estado` es un estatus.

*Universo y partición.* `O_U = { f ∈ E : fecha(f) ∈ periodo }`, particionado así:
- **A (identificados):** `1 ≤ k(f) ≤ m`.
- **B (sin paciente):** `k(f) = 0`. Con el contrato vigente un `id_paciente` vacío **bloquea** la generación, por lo que B = ∅ en una corrida válida; la clase se conserva por robustez y para el modo informe sobre extractos aún no validados.
- **C (paciente contradictorio):** `k(f) > m`.

`O_U = A ⊎ B ⊎ C`. **Pacientes únicos:** `P_U = ⋃ Pac(f)` para `f ∈ A`. **Cobertura de paciente:** `cob = |A| / |O_U|`.

*Decisión expresa sobre pedidos contradictorios*
1. **¿Forman parte del universo de pedidos?** C (paciente contradictorio): **sí**, su fecha es unívoca; permanece en `O_U`. C2 (fecha contradictoria; y C1 si algún día se activa): **no** se asignan a ningún `O_U`; se contabilizan en su propia clase.
2. **¿Se excluyen de los pedidos válidos?** C no se excluye del conteo de pedidos; se excluye **solo** de las operaciones que dependen del paciente (`A`, `P_U`, `cob`). C2 no se cuenta como válido por esta regla y queda declarado en su clase. **El KPI de pedidos publicado no se modifica.**
3. **Cobertura de paciente.** Denominador `|O_U|` (incluye B y C), numerador `|A|`. Siempre se reporta `|O_U| = |A| + |B| + |C|`. Los pedidos C2 (y C1, si se activa) quedan **fuera** del denominador y se informan con `no_asignables = |C1| + |C2|` y `tasa_no_asignables = no_asignables / (|C1| + |C2| + |E|)`.
4. **Cómo se informa.** Un hallazgo por clase, con conteos y hasta 5 `id_pedido` de muestra (lista completa en el informe descargable): `paciente_contradictorio` (`advertir`, `|C| > 0`), `fecha_contradictoria` (`advertir`, `|C2| > 0`), `estatus_mixto` (`advertir`, solo si C1 está activa y `|C1| > 0`), `duplicado_exacto` y `linea_duplicada` (`informar`), `cobertura_paciente` (`informar`).
5. **Sin alteración silenciosa.** Cada cifra se publica con su universo y denominador. Deben cumplirse las **identidades de control** `|id_pedido distintos del archivo| = |C0| + |C1| + |C2| + |E|` y `|O_U| = |A| + |B| + |C|`; si alguna falla, el hallazgo interno es `inconsistente`. La regla no modifica datos ni cifras del motor.
6. **`id_pedido` con más de una combinación de paciente y fecha.** Si `|Fechas(f)| > 1` es **C2**, con independencia de los pacientes (la fecha determina el periodo). Si `|Fechas(f)| = 1` y `k(f) > m` es **C**. Si `k(f) ≤ m` es **A** (incluido `k = 2` con `m = 2`). La evidencia indica el número de combinaciones `(id_paciente, fecha_pedido)` distintas.

*Invariantes.* **I1:** `C = ∅`. **I2:** `|P_U| ≤ m · |A|` (se cumple por construcción; si falla es un error interno). Con `m = 1`, I2 equivale a «pacientes únicos ≤ pedidos únicos identificados».

*Estados de salida.* `verificado` si I1 se cumple y no hay C1/C2; `inconsistente` (`advertir`) si `|C| + |C1| + |C2| > 0`; `no_verificable` (`informar`, con `faltante`) si falta `id_pedido`, `id_paciente` o `fecha_pedido`, si `cob` queda por debajo de `cobertura_minima_paciente` (sin valor universal: no configurado ⇒ solo se informa `cob`), o si los universos no son comparables.

*Otros casos*
| Caso | Tratamiento |
|---|---|
| Pedido con varias líneas | Un solo pedido único; varias líneas con el mismo paciente son normales (`k = 1`). Contar filas como pedidos **no está permitido** en esta regla |
| Paciente con más de un pedido | Válido y esperado; sin hallazgo. Se puede informar `razón_recurrencia = |A| / |P_U|` (descriptivo, `informar`) |
| Universos distintos | Solo se comparan cifras del **mismo** `U`. Si el KPI de pacientes y el de pedidos provienen de archivos, periodos o filtros distintos: `no_verificable` («universos no comparables», con la coordenada que difiere), **sin alerta** |
| KPI calculado sobre filas | Si una cifra publicada difiere de la normalizada solo por granularidad: `informar` «diferencia explicada por granularidad» (ambas cifras), **nunca** `advertir`. La cifra publicada no se modifica |
| Pedidos de otra fuente (compras GA4) | **Fuera del alcance de esta regla**: pacientes y pedidos se evalúan siempre dentro de `ventas` |

*Ejemplo de control (`m = 1`, periodo enero; ejemplo construido, no extraído de los machotes).*
P-001: 3 líneas, X1, 05-ene → A. P-002: 1 línea (dos filas idénticas), X2, 07-ene → A. P-003: 2 líneas, X1 y X3, 09-ene → C. P-004: 2 líneas, fechas 28-ene y 02-feb, X4 → C2. P-005: 1 línea sin `id_paciente`, 12-ene → B. P-006: X1, 20-ene → A.
Resultado: `6 = 0 (C0) + 0 (C1) + 1 (C2) + 5 (E)`; `O_U = 5 = |A| 3 + |B| 1 + |C| 1`; `P_U = {X1, X2}`, `|P_U| = 2 ≤ 1·3` ✓; `cob = 3/5 = 60 %`; `razón_recurrencia = 3/2 = 1,5`. Hallazgos: `paciente_contradictorio` (P-003) y `fecha_contradictoria` (P-004) en `advertir`; `duplicado_exacto` (1) y `cobertura_paciente` en `informar`.
Con `m = 2`: P-003 pasa a A; `|A| = 4`, `P_U = {X1, X2, X3}`, `cob = 4/5 = 80 %`, `C = ∅`; el hallazgo de P-004 permanece.
*Variante condicional* (solo si existiera una columna de estatus mapeada): se añaden P-007 «cancelado» (C0) y P-008 con líneas «entregado» y «cancelado» (C1); resultan `8 = 1 + 1 + 1 + 5` y un tercer hallazgo `estatus_mixto`. Estos valores son los de la prueba T-01.

*Validación operacional pendiente:* que `m = 1` describa tu operación y que, si algún día existe estatus, el tratamiento de C0/C1 sea el deseado (§10.4).

**R-CUADRE-DIM — Conciliación de totales entre dimensiones.**

*Definiciones.* Sea `R` el conjunto de registros de la **entidad contada** (pedido, línea, paciente, sesión…; se declara por dimensión) y `m(r) ≥ 0` su medida (conteo = 1, o monto). Una dimensión `D` tiene categorías `c₁…cₙ`; `cat(r) ⊆ {c₁…cₙ}` son las categorías a las que pertenece `r`. `T = Σ_r m(r)` y `S = Σ_c Σ_{r : c ∈ cat(r)} m(r) = Σ_r |cat(r)| · m(r)`.
- **Exclusiva:** ningún registro pertenece a más de una categoría (`|cat(r)| ≤ 1` para todo `r`). Categorías que se **superponen** (un registro cae en dos) o niveles jerárquicos mezclados (padre e hijo juntos) hacen la dimensión **no exclusiva**.
- **Exhaustiva:** todo registro pertenece al menos a una categoría (`|cat(r)| ≥ 1`), contando «Sin asignar» cuando está definida.
- **«Sin asignar»:** categoría para registros con valor nulo o no mapeado. Solo se usa en dimensiones declaradas exhaustivas y se crea **como categoría virtual dentro de la verificación**; no se añade a tablas ni láminas existentes. Si una tabla publicada omite esos registros, la regla informa `informar` «registros sin categoría: n (x %)», no una alerta.

*Condición esperada por combinación* (con `ε` = tolerancia configurada)

| Exclusiva | Exhaustiva | Condición | Por qué |
|---|---|---|---|
| Sí | Sí | `|S − T| ≤ ε` | `|cat(r)| = 1` para todo `r`, luego `S = T` |
| Sí | No | `S ≤ T + ε` | `|cat(r)| ∈ {0, 1}`; los registros sin categoría no suman |
| No | Sí | `S ≥ T − ε` | `|cat(r)| ≥ 1`; cada registro suma al menos una vez |
| No | No | **Ninguna exigible** | `|cat(r)|` puede ser 0 o ≥ 2; `S` puede quedar por debajo o por encima de `T` |

*Condiciones necesarias de aplicación.* (N1) Medida aditiva: conteos de registros o montos. Las desigualdades de las filas 2 y 3 exigen además `m(r) ≥ 0` (con montos negativos solo es exigible la fila 1). (N2) `S` y `T` se calculan sobre el **mismo universo, periodo, filtros y entidad contada**. (N3) Exclusividad y exhaustividad **declaradas y justificadas** en configuración. (N4) Un conteo de valores distintos (p. ej. pacientes únicos) **no** es aditivo entre categorías si la entidad puede caer en varias: se declara la entidad contada y, normalmente, la dimensión es no exclusiva.

*Declaración por dimensión (nunca universal).* En `reglas.json`, cada dimensión lleva `{id, entidad, exclusiva, exhaustiva, justificacion, fuente_justificacion}`. Si `exclusiva` o `exhaustiva` es `null`, o falta la justificación, la regla **no se aplica**: `no_verificable` («propiedades no declaradas»), `informar`. No hay propiedades por defecto.

*Resultados.* Condición cumplida ⇒ `verificado`. Condición incumplida ⇒ `inconsistente`, `advertir`, con `S`, `T`, diferencia y combinación. Combinación No/No ⇒ `informar` «sin relación exigible», **nunca** `advertir`. Tolerancia `ε` configurable (default: 0 en conteos enteros; 0,5 % o 1 unidad monetaria mínima en montos).

*Ejemplos (los usa T-02).* (1) Pedidos por sucursal, cada pedido una sucursal, con «Sin asignar»: Sí/Sí, `T = 100`, `S = 100` ✓; `S = 97` ⇒ inconsistente. (2) Top 5 productos por monto (cada línea un producto; no exhaustiva): Sí/No, `T = 1 000`, `S = 800` ✓; `S = 1 050` ⇒ inconsistente. (3) Pacientes únicos por canal (un paciente puede usar varios canales; todos tienen al menos uno): No/Sí, `T = 100`, `S = 120` ✓; `S = 95` ⇒ inconsistente. (4) Etiquetas opcionales múltiples: No/No, `S = 60` o `S = 140` frente a `T = 100`, sin hallazgo `advertir`.

*Dimensiones candidatas en los machotes* (las propiedades se **observaron** en los datos sintéticos; son **punto de partida para declarar y justificar**, no una declaración): 

| Dimensión (columna) | Unidad | Entidad contada | Observación en el machote | Propiedad candidata (a justificar) |
|---|---|---|---|---|
| `canal`, `estado`, `region`, `forma_pago`, `modo_entrega`, `programa_lealtad` | GLP-1 | Línea de pedido | Un valor por fila, sin nulos | Exclusiva y exhaustiva |
| Ídem | GLP-1 | Pedido | No varían dentro de un `id_pedido` (OBS-04) | Exclusiva y exhaustiva |
| `canal`, `estado` | AETOPS | Pedido | No varían dentro de un `id_pedido` | Exclusiva y exhaustiva |
| `sucursal`, `linea`, `categoria` | AETOPS | Línea de pedido | Un valor por fila (vía `catalogo`) | Exclusiva y exhaustiva |
| `sucursal`, `linea`, `categoria` | AETOPS | **Pedido** | Varían dentro de un pedido (OBS-04) | **No exclusiva**, exhaustiva ⇒ `S ≥ T` |
| Cualquiera de las anteriores | Ambas | **Paciente único** | Un paciente aparece con varios valores (OBS-05) | **No exclusiva** (conteo de distintos no aditivo) |
| Vistas de `trafico` (`edad`, `sexo`, `dispositivo`, `fuente`, `estado`) | GLP-1 | Métrica agregada | No suman el total `general` (OBS-08) | **No se declaran exhaustivas**: la regla no se aplica hasta que el usuario las declare y justifique |

Hasta que el usuario declare y justifique cada dimensión en `reglas.json`, la regla no se evalúa («propiedades no declaradas»).

**R-CONC-COMPRAS — Compras GA4 frente a pedidos del sistema de ventas.** *(Solo GLP-1; en AETOPS devuelve «No aplica: sin hoja `trafico`».)*
- **Dos fuentes, siempre identificadas.** «Pedidos del sistema de ventas» (`ventas.id_pedido` distintos del periodo) y «Compras GA4» (`trafico.compras`, nivel sitio, mismo periodo). Son métricas **distintas**, con criterios de registro, filtros y universos propios.
- **Prohibido:** sustituir una por la otra, sumarlas, presentarlas como equivalentes, tratar su diferencia como un error automáticamente o forzar una correspondencia pedido a pedido que los datos no permiten.
- **Brecha informativa:** `brecha = (compras GA4 − pedidos del sistema de ventas) / pedidos del sistema de ventas`, solo con mismo periodo y pedidos > 0; si no, «No calculable».
- **No es un error.** Una diferencia entre fuentes es esperable. El aviso vigente `TRAFICO_PURCHASE_DIFFERS` (se emite si la diferencia supera 20 %) **se conserva sin cambio** para no regresar, con `estado_verificacion = verificado` (la aritmética es exacta) y redacción neutra: «las fuentes difieren; no implica error». Ninguna de las dos cifras se corrige.
- Umbral configurable; el 20 % queda como default heredado, registrado como parámetro, no como verdad.
- Las causas posibles (bloqueadores de etiquetas, pagos fuera de línea, filtros, deduplicación) se listan como **hipótesis a validar**, sin atribuir una.
- Falta uno de los dos lados ⇒ «No verificable: falta {pedidos del sistema de ventas | compras GA4}». Efecto: `advertir` solo para el aviso heredado; el resto, `informar`.

**R-DENOM — Denominador ausente o cero.** Convierte cualquier ratio sin denominador válido en «No verificable» con `faltante` indicado. Efecto: `informar`; `bloquear` solo si la lámina es obligatoria y no tiene alternativa.

**R-COBERTURA-ATC — Comparabilidad de carritos agregados y pedidos.** *(Solo GLP-1; en AETOPS: «No aplica: sin hoja `trafico`». El ID se conserva por trazabilidad con v1–v4; la regla no detecta ni exige identificadores individuales.)*
- **Entradas:** carritos agregados (`trafico.add_to_cart`, nivel sitio, mes o meses del periodo); pedidos del sistema de ventas y/o compras GA4, **cada uno como fuente identificada** (`fuente_pedidos`); `unidad_carritos` declarada; periodo, universo y filtros de cada lado.
- **Qué evalúa antes de interpretar:** (1) disponibilidad de ambos valores; (2) **periodo**; (3) **fuente** de los pedidos; (4) **universo** de datos; (5) **filtros**; (6) **unidad de medición de los carritos**.
- **Unidad de los carritos.** `unidad_carritos ∈ {eventos, sesiones, otra (texto), no_declarada}`, configurable por fuente. Los machotes no la declaran, así que el valor inicial es **`no_declarada`**. Con unidad no declarada el cálculo aritmético **se permite** cuando ambos valores existen, pero se rotula «unidad no declarada» y la interpretación es limitada. **No se denomina «carritos únicos»** a una métrica cuya unidad declarada sea eventos u otra. La disponibilidad de un número no equivale a conocer su unidad semántica.
- **Estados de salida:** `calculable`, `calculable_con_limitacion` y `no_calculable` (definidos en §8.2). Falta un valor ⇒ `no_calculable`; nunca se inventa ni se sustituye un dato, ni se toma silenciosamente la otra fuente.
- **Sin identificadores:** no se exige ID de carrito, ni se usa `id_pedido`, un ID de transacción o un ID de sesión como sustituto; no se relaciona ningún carrito con ninguna compra.
- Efecto: `informar`; `advertir` únicamente cuando la relación supera 100 % (§8.2). Nunca bloquea.

### 3.4 Glosario (un término, un significado)

| Término | Significado único en este documento | No confundir con |
|---|---|---|
| **Pedido del sistema de ventas** | `id_pedido` distinto en `ventas` | Compra GA4 |
| **Compra GA4** | `trafico.compras` a nivel sitio | Pedido del sistema de ventas; «purchase» individual |
| **Pedido** (sin calificar) | Término **no usado** sin su fuente en reglas y salidas nuevas | — |
| **Carrito agregado** | Volumen de `trafico.add_to_cart` a nivel sitio, en la unidad de la fuente | Carrito individual identificable |
| **Carritos abandonados (métrica heredada)** | `trafico.carritos_abandonados` (dato o derivado `add_to_cart − compras`); alimenta E2 | Abandono comprobado; complemento de la relación |
| **Relación pedidos/carritos (IND-01)** | `(pedidos / carritos agregados) × 100` por fuente de pedidos | Conversión individual; tasa de abandono |
| **Paciente** | `id_paciente` distinto | `paciente_nuevo` (atributo por pedido) |
| **`id_pedido`** | Identificador del pedido en `ventas`; «folio» es solo su alias histórico | ID de transacción o de carrito |
| **Cobertura de paciente** (`cob`) | `|A| / |O_U|` en `R-REL-PAC-PED` | La regla `R-COBERTURA-ATC` (comparabilidad) |
| **Exclusiva / exhaustiva** | Propiedades de una dimensión respecto de una entidad contada (§3.3 `R-CUADRE-DIM`) | Que las categorías «sumen bien» por casualidad |
| **Dimensión** | Columna o vista por la que se desglosa una medida | Métrica |
| **Universo** | Archivo + periodo + filtros declarados de una cifra | Periodo solamente |
| **Fuente** | Sistema de origen de una cifra: sistema de ventas, analítica web (GA4 u otra), captura manual | Archivo o hoja |
| **Periodo** | Fecha de inicio, fecha de fin y granularidad (día, mes, trimestre) | Etiqueta del reporte |
| **`estado`** | Entidad federativa (columna de `ventas`) | `estado_verificacion` (campo del hallazgo, §4.2) y «estatus» de pedido (inexistente) |
| **Unidad de carritos** | `eventos`, `sesiones`, `otra` o `no_declarada` | Un identificador |
| **Supuesto heredado** | Parámetro histórico (25 %, 10 %) sin validación con datos reales | Resultado observado |

### 3.5 Catálogo de fórmulas

| ID | Fórmula | Numerador | Denominador | Fuentes | Condición de cálculo | Datos faltantes | División inválida | Interpretación |
|---|---|---|---|---|---|---|---|---|
| F-01 | `Relación_V = (Pedidos_V / Carritos) × 100` | Pedidos del sistema de ventas del periodo (`id_pedido` distintos) | Carritos agregados (nivel sitio) | `ventas`, `trafico` | Ambos presentes; `Carritos > 0`; mismo periodo | «No calculable» (sin valor sustituto) | `Carritos = 0` ⇒ no calculable | Pedidos por cada 100 carritos agregados, **fuente: sistema de ventas**; no es abandono |
| F-02 | `Relación_G = (Compras_G / Carritos) × 100` | Compras GA4 del periodo | Carritos agregados (nivel sitio) | `trafico` | Igual que F-01 | Igual | Igual | Compras GA4 por cada 100 carritos agregados, **fuente: GA4** |
| F-03 | `brecha = (Compras_G − Pedidos_V) / Pedidos_V` | Compras GA4 − pedidos del sistema de ventas | Pedidos del sistema de ventas | `trafico`, `ventas` | Mismo periodo; `Pedidos_V > 0` | «No verificable» | `Pedidos_V = 0` ⇒ no calculable | Diferencia entre fuentes; no es error |
| F-04 | `cob = |A| / |O_U|` | Pedidos identificados | Pedidos del universo | `ventas` | `|O_U| > 0` | «No verificable» | `|O_U| = 0` ⇒ no verificable | Proporción de pedidos con paciente identificado |
| F-05 | `razón_recurrencia = |A| / |P_U|` | Pedidos identificados | Pacientes únicos | `ventas` | `|P_U| > 0` | «No verificable» | `|P_U| = 0` ⇒ no verificable | Pedidos por paciente en el periodo |
| F-06 | `tasa_no_asignables = (|C1| + |C2|) / (|C1| + |C2| + |E|)` | Pedidos no asignables | Pedidos clasificables | `ventas` | Denominador > 0 | «No verificable» | Denominador 0 ⇒ no verificable | Peso de los pedidos que no pueden asignarse a un periodo |
| F-07 | `|P_U| ≤ m · |A|` (I2) | — | — | `ventas` | Siempre | — | — | Verificación interna |
| F-08 | `S = Σ_r |cat(r)|·m(r)`, `T = Σ_r m(r)`, condición por combinación | Suma de categorías | Total | Según dimensión | Dimensión declarada y justificada; `m(r) ≥ 0` para desigualdades | «No verificable: propiedades no declaradas» | No hay división | §3.3 `R-CUADRE-DIM` |
| F-09 | `Ingreso_ilustrativo_E1 = M_neg × r` | — | — | `negados.monto_negado` | `M_neg` disponible | Escenario no mostrado | No hay división | Supuesto heredado, no validado |
| F-10 | `Ingreso_ilustrativo_E2 = A × c × T` (fórmula vigente) | — | — | `trafico.carritos_abandonados`, `ventas` | `A > 0` y `T > 0` (conducta vigente) | Escenario no mostrado | `T = monto ÷ pedidos`: pedidos > 0 | Supuesto heredado, no validado; `A` no es abandono comprobado |
| F-11 | `ticket T = monto_venta ÷ pedidos del sistema de ventas` (vigente) | Σ `monto_venta` | Pedidos del sistema de ventas | `ventas` | Pedidos > 0 | «No verificable» | Pedidos = 0 ⇒ no verificable | Fórmula existente, sin cambio |
| F-12 | `carritos_abandonados = add_to_cart − compras` (vigente, solo si la columna viene vacía) | `add_to_cart` | — | `trafico` | Columna vacía | Se omite | No hay división | Derivado y marcado como tal; **no** es abandono comprobado |

Las fórmulas F-09 a F-12 son **vigentes**: esta especificación no las modifica.

### 3.6 Aplicabilidad por unidad

| Regla / indicador / escenario | GLP-1 | AETOPS |
|---|---|---|
| `R-REL-PAC-PED` | Aplica | Aplica |
| `R-CUADRE-DIM` | Aplica (dimensiones de GLP-1) | Aplica (dimensiones de AETOPS) |
| `R-CONC-COMPRAS` | Aplica | **No aplica** (sin `trafico`) |
| `R-DENOM` | Aplica | Aplica |
| `R-COBERTURA-ATC` e IND-01 | Aplica | **No aplica** (sin `trafico`) |
| Escenario E1 (negados) | Aplica | Aplica |
| Escenario E2 (métrica heredada) | Aplica | **No aplica** (sin `trafico`) |
| Si en el futuro AETOPS suma un archivo de tráfico | — | Las reglas «solo GLP-1» podrían habilitarse **por decisión expresa**; no es requisito de Fase 1 |

---

## 4. Arquitectura de validación y nomenclatura

### 4.1 Problema
La propiedad actual `severity` (`block | warn | info`) mezcla gravedad de negocio con efecto en la generación. La palabra «severity» se conservaría con otro significado y causaría confusión.

### 4.2 Nombres explícitos (campos nuevos del hallazgo)

| Campo | Valores | Significado |
|---|---|---|
| `tipo` | `integridad`, `consistencia`, `cobertura`, `definicion`, `conciliacion`, `narrativa`, `presentacion` | De qué trata |
| `gravedad` | `critica`, `alta`, `media`, `baja` | Importancia para el negocio. **No** es `severity` |
| `estado_verificacion` | `verificado`, `inconsistente`, `no_verificable`, `supuesto` | Qué sabemos. Es el campo que abreviábamos como «estado» |
| `efecto_generacion` | `bloquear`, `advertir`, `informar` | Qué hace el sistema |
| `faltante` | lista de `{archivo, columna, granularidad}` | Qué dato falta (obligatorio si `estado_verificacion = no_verificable`) |
| `regla_id` | texto, p. ej. `R-CONC-COMPRAS` | Regla que lo produjo |
| `regla_version` | texto, p. ej. `1.0.0` | Versión de esa regla |

Además se serializa un campo **derivado de solo lectura**, `validacion_operacional` (`no_validada_con_datos_reales` · `confirmada` · `no_aplica`), obtenido de `config/validacion_registro.json` a partir de `regla_id` y `regla_version`. No es parte del constructor de `Finding` y no altera `severity`. La interfaz y el anexo muestran «No validada con datos reales» cuando el valor no es `confirmada`.

### 4.3 Migración con compatibilidad
1. `severity` **no se renombra ni se elimina en Fase 1**. Se documenta como *alias heredado de `efecto_generacion`* con correspondencia fija: `block ↔ bloquear`, `warn ↔ advertir`, `info ↔ informar`.
2. `Finding` conserva su firma posicional `(id, severity, message, evidence)`; los campos nuevos son opcionales y solo por palabra clave. Si solo se da `severity`, `efecto_generacion` se deriva; si se dan ambos, deben ser coherentes (se valida al construir).
3. La serialización a JSON **sigue incluyendo `severity`** y añade los campos nuevos; interfaz, `has_blockers()` y pruebas existentes no cambian.
4. `validator/catalogo.py` asigna `(tipo, gravedad, estado_verificacion, efecto_generacion)` a cada `id` existente. Un `id` sin entrada recibe valores por defecto (`integridad`, `media`, `verificado`, efecto derivado de `severity`) y una prueba falla si aparece uno sin entrada.
5. Nuevo código y documentación usan solo los nombres explícitos. La retirada de `severity` queda fuera de Fase 1 y requeriría decisión aparte.
6. Contrato de compatibilidad: una prueba recorre todos los hallazgos de los ejemplos y comprueba que `severity` y `id` coinciden con la línea base.

### 4.4 Reglas de diseño
- «No verificable» es un estado, no un error; por defecto `efecto_generacion = informar`.
- `bloquear` nunca se ignora en silencio. Un hallazgo `advertir` que el usuario acepta queda registrado en el historial.
- Efecto y gravedad son independientes.

---

## 5. Procedencia y reproducción histórica

### 5.1 Manifiesto de procedencia (`procedencia.json`, uno por reporte generado)

| Campo | Contenido | Origen |
|---|---|---|
| `version_codigo` | versión de la app + SHA del commit desplegado | `build_site.py` estampa ambos al construir |
| `version_motor` | `ENGINE_VERSION` del motor de cálculo (`Decimal`, agregación, `Value`/`Lineage`) | constante nueva, incrementada cuando cambia un resultado numérico |
| `version_definiciones` | versión del catálogo `definiciones.json` | catálogo |
| `version_reglas` | versión global y por `regla_id`, con su estado de validación (sintética / operacional) | catálogo de reglas y registro de validación |
| `version_plantillas` | por plantilla: id, nombre y **SHA-256** | cálculo al cargar |
| `archivos_fuente` | por archivo: nombre, tamaño, **SHA-256**, filas, columnas detectadas, periodo detectado. **Sin contenido** | cálculo al cargar |
| `fecha_generacion` | UTC ISO-8601 y zona horaria del navegador | reloj del cliente |
| `configuracion` | metas, umbrales, parámetros de escenarios, flags de Fase 1, uso de IA (sí/no, modelo declarado) | estado de la sesión |
| `hash_resultado` | SHA-256 del **resultado canónico** (§5.2) | cálculo |

El manifiesto se guarda en el historial (IndexedDB), se puede descargar como `.json` y se resume en el anexo de calidad de datos. **No se guardan los archivos fuente** (principio 5): reproducir exige que el usuario los vuelva a aportar y que su SHA-256 coincida.

### 5.2 Qué es «reproducibilidad exacta»

Un reporte es **exactamente reproducible** cuando, con las mismas entradas y las mismas versiones, se obtiene el mismo **resultado canónico**:

- Mismos archivos fuente (SHA-256 idéntico) y misma configuración.
- Mismas versiones de código, motor, definiciones, reglas y plantillas.
- Mismo JSON canónico de resultados: todos los `Value` (`Decimal` exactos y su `Lineage`), lista de hallazgos con sus siete campos, y el texto determinista de cada lámina.

**No** se promete identidad byte a byte del `.pptx` (el contenedor ZIP lleva marcas de tiempo y metadatos). Se promete equivalencia canónica, verificada con `hash_resultado`.

**Texto de IA:** no es reproducible por naturaleza. Se guarda lo aceptado en `ia_log.json` y se reutiliza tal cual, sin volver a invocar el modelo. Un reporte con IA es «reproducible en cifras y texto determinista; texto de IA restaurado desde el registro».

### 5.3 Estados de reproducibilidad y comportamiento del sistema

| Estado | Condición | Qué hace el sistema |
|---|---|---|
| `exacta` | Todo coincide | Regenera y compara `hash_resultado`; informa «idéntico» |
| `parcial` | Faltan o difieren una o más versiones (p. ej. el código actual es posterior) o falta un archivo fuente | **No regenera en silencio.** Muestra qué componente difiere. Permite regenerar «con versiones actuales», marcado como *no equivalente al original*, con diferencias listadas |
| `no_reproducible` | Falta manifiesto (reportes anteriores a Fase 1) o los hashes de entrada no coinciden | Lo declara; no afirma equivalencia. Ofrece regenerar como reporte nuevo |

Limitaciones que se documentan en vez de ocultarse:
- Hoy **no existe** manifiesto; todo reporte previo a Fase 1 queda como `no_reproducible (legado)`. La afirmación de v1 de que los históricos «se regeneran» solo aplica a reportes creados **a partir de** Fase 1.
- Reproducir con código anterior exige poder obtener esa versión. Propuesta: etiquetar cada despliegue en git (`app-vX.Y.Z`) y publicar su `app.zip` como asset de GitHub Release. Si la versión no está publicada, el estado es `parcial` (decisión A-5).
- Las plantillas se identifican por hash; si el usuario cambió su archivo, el estado es `parcial`.

---

## 6. Alcance de Fase 1

Entra:
1. **Catálogo de definiciones** `definiciones.json` (v1) y su lectura en el pipeline.
2. **Hallazgo extendido** con los siete campos nuevos y migración compatible (§4).
3. **Las cinco reglas:** `R-REL-PAC-PED`, `R-CUADRE-DIM`, `R-CONC-COMPRAS`, `R-DENOM`, `R-COBERTURA-ATC`. Por defecto ninguna bloquea.
4. **Procedencia y reproducibilidad** (§5).
5. **Escenarios** con definición matemática (§8): estructura para tres escenarios, pero con valores iniciales **solo los heredados** (25 % y 10 %); e **indicador IND-01 «Relación pedidos/carritos»** con metodología agregada y fuente de pedidos identificada (§8.2), para GLP-1, mostrado en el anexo y el panel.
6. **QA estructural del PPTX exportado** (§7.A) y **harness de QA visual** para Actions/local (§7.B).
7. **Anexo «Calidad de datos y supuestos»** al final del deck, sin mover láminas existentes.
8. **Procedimiento y herramienta de anonimización**, y arquitectura de **validación sintética vs operacional** (§10): Fase 1 puede iniciar sin extractos; incorporarlos después no exige rehacer nada.
9. **Línea base y prueba de no-regresión** (§11.1).

Fuera de alcance: nuevos importadores, rediseño de plantillas, cambios en narrativa/IA, gráficos nuevos, retirada de `severity`, y **cualquier identificación individual de carritos** (ID de carrito, ID de transacción como vínculo, relación individual add_to_cart–purchase, ventanas de vinculación, abandono por carrito). Esa trazabilidad individual, si se desea algún día, sería una **evolución independiente** con su propia especificación y autorización; **no es requisito de Fase 1 ni condición para la metodología agregada vigente**. El único indicador nuevo de Fase 1 es la «Relación pedidos/carritos» (§8.2), que no modifica láminas existentes.

---

## 7. QA del PPTX exportado: estructural y visual (separados)

### 7.A QA estructural (re-lectura del archivo con python-pptx)

Se ejecuta **sobre el `.pptx` ya guardado**. Lee la estructura declarada en el archivo (XML); **no ve cómo se dibuja la diapositiva**.

| Chequeo | Qué verifica | `id` de salida |
|---|---|---|
| Cifras | Cada número impreso se puede trazar a un `Value` verificado | `PPTX_CIFRA_NO_TRAZADA` |
| Fórmulas | Los derivados impresos (variaciones, participaciones, conversiones, escenarios) se recalculan desde sus `Value` y deben coincidir con lo impreso | `PPTX_FORMULA_NO_COINCIDE` |
| Unidades | `%`, `pp`, moneda y conteos coherentes con la métrica | `PPTX_UNIDAD_AMBIGUA` |
| Denominadores | Cada ratio publicado declara su denominador (§3.2) | `PPTX_SIN_DENOMINADOR` |
| Textos | Duplicados, dobles espacios, términos del dominio mal escritos (diccionario acotado). No es corrector ortográfico general | `PPTX_DUPLICADO`, `PPTX_TEXTO` |
| Fuentes | Tamaño mínimo declarado (default 9 pt, configurable); familia de fuente consistente con la plantilla | `PPTX_FUENTE_MIN`, `PPTX_FUENTE_INCONSISTENTE` |
| Geometría | Formas dentro del lienzo; solapamiento de recuadros declarados; estimación de desborde (`check_geometry` existente, heurística) | `OVERFLOW_ESTIMATED` (existente), `PPTX_FUERA_DE_LIENZO`, `PPTX_SOLAPE_DECLARADO` |
| Tokens técnicos | `{{`, `None`, `nan`, `Decimal(`, `RI_`, `KeyError`, `Traceback` | `PPTX_TOKEN_TECNICO` (bloquea) |
| Gráficas (estructura) | Gráfico con serie y categorías no vacías; embudo sin segmentos de ancho 0 | `PPTX_GRAFICO_VACIO` |

Límites explícitos de 7.A:
- python-pptx **no** calcula el ajuste de línea real, la fuente sustituida, el contraste efectivo ni cómo se pinta una gráfica. Esos puntos se resuelven en 7.B.
- El desborde es una **estimación** (`CHAR_EM = 0.42`). Puede dar falsos positivos y falsos negativos.
- Un indicio de contraste calculado a partir de colores explícitos en el XML se etiqueta *indicio*, no verificación.

### 7.B QA visual (requiere render real)

| Chequeo | Método | Dónde |
|---|---|---|
| Render real de diapositivas | LibreOffice headless → PDF → PNG por diapositiva | Actions o equipo local |
| Superposiciones reales | Posición real del texto en el PDF (extracción de cajas de texto) y detección de cajas que se cruzan o salen del lienzo | Actions o local |
| Texto ilegible o recortado | Texto presente en el PDF pero fuera del recuadro; tamaño efectivo tras el ajuste | Actions o local |
| Gráficas | La imagen renderizada no está en blanco; las etiquetas existen en el PDF | Actions o local |
| Contraste | Muestreo de píxeles de texto vs fondo en el render | Actions o local |
| Consistencia visual | Comparación de estilo entre diapositivas del mismo tipo (posiciones, tamaños) | Actions o local |
| Revisión humana | Visor lado a lado: render por diapositiva con los hallazgos marcados | Artefacto de Actions o equipo local |

### 7.C Qué puede hacerse dónde

| Capacidad | Navegador (Pyodide) | GitHub Actions | Equipo local |
|---|---|---|---|
| QA estructural 7.A | **Sí** | Sí | Sí |
| Render real de diapositivas | **No** (no hay LibreOffice ni motor de render de PPTX) | Sí | Sí, con LibreOffice instalado |
| QA visual 7.B | **No** | Sí | Sí |
| Mantiene los datos en el navegador | Sí | **No**: el archivo tiene que subirse a GitHub | Sí |

Limitaciones técnicas:
1. **Privacidad en Actions.** Ejecutar QA visual allí implica subir el `.pptx` (y por tanto cifras de negocio) al repositorio o a un artefacto de GitHub. Propuesta: Actions solo con datos sintéticos o anonimizados por defecto; con datos reales únicamente si **tú** lo decides expresamente (decisión A-6). Alternativa sin subir datos: `tools/visual_qa.py` ejecutado en tu equipo.
2. **LibreOffice ≠ PowerPoint.** El render puede diferir (fuentes sustituidas, ajuste de línea, gráficas nativas). Aprobar 7.B **no garantiza** que PowerPoint lo muestre igual.
3. **La revisión humana de una muestra sigue siendo necesaria** antes de entregar a un tercero.
4. Hoy existe `pdf.yml`; su alcance exacto (qué convierte y qué publica) se confirma en la línea base y se extiende, no se asume.
5. En el navegador, la interfaz muestra el resultado de 7.A con la etiqueta «Revisión estructural. La revisión visual requiere render» y no emplea la palabra «visual» para ella.

---

## 8. Escenarios y relación pedidos/carritos

Esta sección distingue **tres elementos que no deben confundirse**: (1) el escenario histórico **E2**, (2) la métrica heredada **`carritos_abandonados`** que lo alimenta y (3) el indicador agregado **IND-01 «Relación pedidos/carritos»** (§8.2–8.3).

### 8.0 Estrategia de escenarios (sin cambios respecto a v4)

| Escenario | Valor inicial | Origen | Etiqueta obligatoria |
|---|---|---|---|
| E1 — Recuperación de negados | `r = 25 %` (`rules.py:21`) | Heredado de la versión actual | «Supuesto heredado, no validado» |
| E2 — Recuperación de abandono (denominación histórica) | `c = 10 %` (`rules.py:25`) | Heredado de la versión actual | «Supuesto heredado, no validado» |

- **Fórmulas vigentes sin cambio** (F-09 y F-10). Fase 1 **no** modifica fórmulas, cifras ni textos de las láminas existentes sin autorización (A-3).
- Los porcentajes son **supuestos heredados, no validados con datos reales**; nunca se presentan como resultados observados ni como parámetros aprobados.
- **Estructura para tres escenarios**, pero `r_conservador`, `r_optimista`, `c_conservador` y `c_optimista` existen con valor `null` («No configurado») y **no se muestran ni se inventan**. Podrán incorporarse con datos históricos suficientes o por decisión expresa posterior.
- La etiqueta «Supuesto heredado, no validado» aparece en el panel de escenarios, el anexo y el manifiesto. Añadirla al texto de las láminas existentes es un cambio de texto que solo se hace con A-3.

### 8.1 Ficha del escenario E1 — Recuperación de negados (GLP-1 y AETOPS)

| Elemento | Definición |
|---|---|
| Objetivo | Ilustrar el monto que equivaldría recuperar una fracción de lo negado por falta de stock |
| Entradas | `M_neg`: Σ `negados.monto_negado`; `Venta_total`: Σ `ventas.monto_venta` del periodo |
| Fuentes | Hoja `negados` y hoja `ventas` de la unidad (ambas existen en los dos machotes) |
| Condiciones | `M_neg` disponible; `Venta_total > 0` |
| Fórmula | `Ingreso_ilustrativo = M_neg × r`; `Proporción = Ingreso_ilustrativo / Venta_total` (F-09) |
| Salidas | Monto ilustrativo y su proporción de la venta, con la etiqueta heredada |
| Limitaciones | Monto negado ≠ demanda recuperable; no es pronóstico; no se suma entre periodos. **`negados` no trae fecha** (OBS-11): se asume que corresponde al periodo del reporte, lo que el machote no permite verificar |
| Dependencias | A-3 solo si se quisiera cambiar el texto de la lámina; ninguna para conservarla |
| Si faltan datos | `M_neg` ausente ⇒ el escenario no se muestra («No verificable»); no se sustituye por otra fuente |

### 8.2 IND-01 — Relación pedidos/carritos (metodología agregada vigente)

**Esta es una definición explícita del funcionamiento actual del negocio.** Aplica a **GLP-1** (única unidad con `trafico`); en AETOPS: «No aplica: sin hoja `trafico`».

**Definición.** Se comparan dos **volúmenes agregados** del mismo periodo:
- **Carritos agregados:** Σ `trafico.add_to_cart` a nivel sitio (`vista = general`, `sku` vacío) de los meses del periodo, en la unidad que reporte la fuente.
- **Pedidos realizados**, de una **fuente identificada** (parámetro `fuente_pedidos`):
  - `sistema_ventas`: pedidos únicos del sistema de ventas (`ventas.id_pedido` distintos con `fecha_pedido` en el periodo);
  - `ga4_compras`: compras GA4 (Σ `trafico.compras` a nivel sitio).

```
Relación pedidos/carritos = (Pedidos realizados / Carritos agregados) × 100
```

Cada cálculo se llama y muestra con su fuente:
- **«Relación pedidos (sistema de ventas) / carritos agregados»** — F-01.
- **«Relación compras GA4 / carritos agregados»** — F-02.

**Las dos fuentes nunca se combinan.** Si se calculan ambas se presentan como **resultados independientes y claramente identificados**; no se sustituye una por la otra cuando falta, no se suman, no se promedian y no se presentan como equivalentes. La diferencia entre ambas no se trata como error y no se fuerza ninguna conciliación individual (`R-CONC-COMPRAS`).

Ejemplo ilustrativo (no es un dato real):

| Indicador | Cantidad |
|---|---|
| Carritos agregados | 1,000 |
| Pedidos realizados (fuente: sistema de ventas) | 250 |
| Relación pedidos/carritos | 25 % |

Interpretación correcta: *«Por cada 100 carritos agregados, se registran 25 pedidos en el periodo, utilizando la fuente de pedidos seleccionada (sistema de ventas)»*. **No** se interpreta el 75 % restante como carritos abandonados comprobados: la diferencia aritmética no demuestra abandono individual.

Ilustración con el machote GLP-1 de sept-2026 (sintético, OBS-10): carritos agregados 18 883; pedidos del sistema de ventas 2 356 ⇒ **12,48 %**; compras GA4 2 643 ⇒ **14,00 %**. Son dos resultados independientes; sus fuentes difieren (+12,18 % de compras sobre pedidos).

**Naturaleza del indicador**
1. Es una **relación entre volúmenes agregados**, no una conversión individual de cada carrito.
2. **No requiere** identificar carritos ni relacionar un carrito con una transacción. **No se exige** ID de carrito en GA4 ni en otra fuente; **no se usa** `id_pedido`, un ID de transacción ni un ID de sesión como sustituto de un identificador de carrito; **no se diseña** relación individual entre `add_to_cart` y `purchase`.
3. **No es** una tasa de abandono individual verificable. La diferencia entre carritos y pedidos **no** se afirma como carritos abandonados y el abandono **no** se calcula como complemento (`100 − relación`).
4. Se muestran **siempre juntos y diferenciados** el volumen de carritos (con su unidad), el volumen de pedidos (con su fuente) y la relación porcentual.

**Denominación.** Permitidas: «Relación pedidos/carritos» (con su fuente) y «Conversión agregada de carritos a pedidos». Prohibidas en cualquier salida **nueva**: «carritos abandonados comprobados», «usuarios que abandonaron el carrito», «carritos sin compra identificados individualmente», «carritos únicos» para una métrica cuya unidad declarada no lo es, y cualquier rótulo o cálculo de abandono derivado de `100 − relación`. (Las láminas actuales con «carritos abandonados» no cambian sin A-3; ver §8.3.)

**Comparabilidad.** Antes de interpretar el resultado se consideran: **periodo, fuente, universo de datos, filtros, unidad de medición de los carritos y disponibilidad**. En GLP-1 el periodo se alinea a meses calendario (OBS-09): el mes de `fecha_pedido` frente al `mes` de `trafico`; un trimestre son tres meses completos. Los filtros y el universo se declaran en la configuración (p. ej. `filtro_canal_relacion`, por defecto sin filtro; AMB-9).

**Estados del indicador (regla `R-COBERTURA-ATC`)**

| Estado | Condición | Presentación |
|---|---|---|
| `calculable` | Numerador y carritos presentes y numéricos; `carritos > 0`; **periodo, fuente, universo y filtros declarados y coincidentes**; **unidad de carritos declarada**; relación ≤ 100 % | Relación con sus tres elementos |
| `calculable_con_limitacion` | Numerador y carritos presentes, `carritos > 0`, pero se cumple al menos una: (a) **periodos distintos** ⇒ «no equivalente temporalmente», sin variaciones contra otros periodos; (b) **universos, filtros o fuentes difieren** o no están declarados ⇒ «puede no ser directamente comparable», con la diferencia; (c) **unidad de carritos no declarada** ⇒ «unidad no declarada: interpretación limitada»; (d) **relación > 100 %** | El **cálculo aritmético se muestra** con la limitación escrita. Con los machotes actuales, que no declaran unidad, todo resultado nace en este estado hasta que el usuario declare la unidad |
| `no_calculable` | Falta el numerador o los carritos (ausente, nulo o no numérico), o `carritos = 0` | «No calculable», con `faltante`. **No se inventa ni se sustituye ningún valor, ni se toma la otra fuente de pedidos**; tampoco se muestra 0 % |

Faltante ≠ cero: si la fuente informa explícitamente `pedidos = 0` con `carritos > 0`, la relación es 0 % (calculable); si `pedidos` falta, es no calculable. La coincidencia de periodos exige misma fecha de inicio, de fin y granularidad (AMB-5).

**Relaciones superiores a 100 %.** Se muestran **tal como resultan** (p. ej. 1 200 pedidos / 1 000 carritos ⇒ **120 %**). Está prohibido truncarlas a 100 %, corregirlas, ajustar el denominador, alterar el numerador o declararlas error matemático. Se emite una **advertencia** (`efecto_generacion = advertir`, `estado_verificacion = supuesto`) con este sentido: *«La relación supera 100 %. Esto puede ocurrir porque pedidos y carritos no necesariamente representan unidades equivalentes, o porque sus fuentes, periodos, universos o filtros no coinciden. Interprétese con cautela.»* El aviso **no afirma una causa** que no se haya comprobado. El valor original se conserva.

**Estados de verificación y efecto:** `calculable` ⇒ `verificado`; `calculable_con_limitacion` ⇒ `supuesto`; `no_calculable` ⇒ `no_verificable`. Efecto `informar`, salvo `advertir` en el caso (d). Nunca bloquea.

### 8.3 Ficha del escenario E2 y su separación del indicador agregado

**Tabla de los tres elementos**

| Elemento | Qué es | Dónde se define | Qué NO es |
|---|---|---|---|
| **E2 — «Recuperación de abandono»** | Escenario histórico y su denominación heredada; ilustra el efecto de cerrar `c = 10 %` de la métrica heredada | §8.0, F-10 | No demuestra abandono individual; no es el indicador IND-01 |
| **Métrica heredada `carritos_abandonados`** | Columna de `trafico`: dato de la fuente o, si viene vacía, `add_to_cart − compras` marcado «derivado» (F-12). En el machote vale `add_to_cart − compras` en las 1 260 filas (OBS-07) | `docs/CONTRATO_DATOS.md`, `raw/glp1.py:333` | No es abandono comprobado ni identifica carritos |
| **IND-01 — Relación pedidos/carritos** | Indicador agregado nuevo con fuente identificada | §8.2 | No sustituye a E2 ni se usa para calcularlo |

**La denominación histórica «Recuperación de abandono» no constituye por sí misma una demostración de abandono individual.** Si el significado exacto de un dato heredado no puede determinarse con los machotes (p. ej. cómo define la herramienta de analítica la columna `carritos_abandonados` cuando viene informada por la fuente), **se conserva su definición histórica y se documenta la limitación** (AMB-10); no se inventa una interpretación.

**Aclaración obligatoria en toda salida nueva** (panel, anexo, paneles, hallazgos) que use `carritos_abandonados`: *«Métrica agregada heredada del embudo («carritos_abandonados»): dato de la fuente o derivado (add_to_cart − compras). No constituye abandono individual comprobado.»* La etiqueta no presenta la diferencia entre carritos y pedidos como abandono comprobado.

| Elemento de la ficha E2 | Definición |
|---|---|
| Objetivo | Ilustrar el monto equivalente a cerrar una fracción de la métrica heredada |
| Entradas | `A`: `trafico.carritos_abandonados` (nivel sitio, periodo); `T`: ticket = `monto_venta` ÷ pedidos del sistema de ventas (F-11); `Venta_total` |
| Fuentes | `trafico` y `ventas` de **GLP-1** |
| Condiciones | `A > 0`, `T > 0` y `Venta_total > 0` (conducta vigente `if aband and tick`) |
| Fórmula | `Ingreso_ilustrativo = A × c × T`, `c = 10 %` (F-10); `Proporción = Ingreso_ilustrativo / Venta_total`. **Sin cambios** |
| Salidas | Monto ilustrativo y proporción de la venta, con la etiqueta heredada y, en salidas nuevas, la aclaración anterior |
| Limitaciones | `A` es un agregado heredado; el ticket de pedidos concretados puede no representar el de un carrito no concretado; no es pronóstico ni resultado observado |
| Dependencias | **A-3**: cualquier cambio de texto o rótulo en la lámina existente. Sin A-3 la lámina permanece idéntica |
| Si faltan datos | `A` o `T` ausentes o cero ⇒ el escenario no se muestra (conducta vigente); no se sustituye por IND-01 ni por otra fuente |
| Unidad | **AETOPS: no aplica** (sin `trafico`) |

Fase 1 **no** modifica la fórmula, la cifra ni la lámina de E2.

### 8.4 Garantías (probadas en §11)
- IND-01 se calcula **solo** con dos volúmenes agregados; ninguna prueba, regla ni configuración exige un identificador de carrito, de transacción o de sesión.
- Toda cifra de IND-01 nombra la fuente de sus pedidos; ninguna fuente sustituye ni se suma a la otra.
- Ninguna salida nueva contiene las denominaciones prohibidas ni calcula `100 − relación`.
- Faltante ⇒ «No calculable»; periodos distintos ⇒ sin variaciones y con limitación; universo, filtros o fuentes distintos ⇒ advertencia; unidad no declarada ⇒ cálculo con interpretación limitada; > 100 % ⇒ valor conservado con advertencia.
- Los porcentajes 25 % y 10 % se muestran como «Supuesto heredado, no validado»; no se muestran escenarios conservador/optimista.
- Sin A-3, las láminas y cifras actuales son idénticas a la línea base.

### 8.5 Evolución futura independiente (fuera de Fase 1)
Una eventual trazabilidad individual de carritos (identificadores, vínculo entre eventos, ventanas de conversión) sería una **evolución independiente**, con especificación y autorización propias. **No es requisito de Fase 1 ni condición** para usar la metodología agregada. Esta especificación no define ninguna parte de ella.

---

## 9. Archivos que se modificarían o crearían

| Archivo | Cambio | Tipo |
|---|---|---|
| `backend/app/models.py` | `Finding` con 7 campos opcionales (por palabra clave) y derivación de `severity` | modificar |
| `backend/app/validator/catalogo.py` | mapa `id` → `tipo`, `gravedad`, `estado_verificacion`, `efecto_generacion` | nuevo |
| `backend/app/validator/rules.py` | `R-REL-PAC-PED`, `R-CUADRE-DIM`, `R-DENOM`; `has_blockers` sigue leyendo `severity` | modificar |
| `backend/app/validator/rules_conc.py` | `R-CONC-COMPRAS`, `R-COBERTURA-ATC` (comparabilidad de carritos agregados y pedidos) | nuevo |
| `backend/app/raw/common.py`, `raw/aetops.py`, `raw/glp1.py` | dimensiones con `exclusiva`/`exhaustiva` declaradas; conciliación parametrizable (hoy `glp1.py:350`); exposición de periodo, universo y fuente de cada agregado (sin cambiar cifras) | modificar |
| `backend/app/config/definiciones.json` | catálogo versionado | nuevo |
| `backend/app/config/reglas.json` | umbrales, tolerancias, versión por regla, `max_pacientes_por_pedido`, `estatus_excluidos` (= `null`: sin columna de estatus), `cobertura_minima_paciente`, `dimensiones` (exclusiva/exhaustiva con justificación), `fuente_pedidos` y `fuentes_relacion`, `unidad_carritos` por fuente (default `no_declarada`), `filtro_canal_relacion` (default `null`), escenarios con `origen` (heredados 25 % y 10 %; `null` para conservador/optimista), flags | nuevo |
| `backend/app/config/mapeo_columnas.json` | alias de columnas por archivo (pedidos, tráfico); permite aceptar extractos con otros nombres **sin tocar código**. **No define ni detecta identificadores de carrito, transacción o sesión** | nuevo |
| `backend/app/config/validacion_registro.json` | estado de validación por `regla_id`/`regla_version`: sintética y operacional, extracto, fecha, parámetros confirmados, confirmante | nuevo |
| `backend/app/validator/rel_pedidos_carritos.py` | indicador IND-01 «Relación pedidos/carritos» por fuente de pedidos y sus estados (§8.2); sin identificadores; solo GLP-1 | nuevo |
| `CAMBIOS_JUSTIFICADOS.md` | registro de cambios que alteren un resultado (§11.5) | nuevo |
| `tools/make_fixtures_fase1.py` | genera, con semilla fija, las fixtures sintéticas de §11.4 | nuevo |
| `tests/fixtures/fase1/` | fixtures sintéticas versionadas con manifiesto y hash (§11.4) | nuevo |
| `backend/app/provenance.py` | manifiesto, hashes, resultado canónico, estados de reproducibilidad | nuevo |
| `backend/app/version.py` | `APP_VERSION`, `ENGINE_VERSION` | nuevo |
| `backend/app/narrative/rules.py`, `executive.py`, `glp1_exec.py`, `targets.py` | escenarios parametrizados E1/E2 (defaults = comportamiento actual salvo A-3) | modificar |
| `backend/app/deck/extras.py`, `build.py` | anexo de calidad de datos; escritura del manifiesto; QA estructural tras guardar | modificar |
| `backend/app/qa/pptx_export.py` | QA estructural del PPTX exportado (§7.A) | nuevo |
| `backend/app/qa/checks.py` | registro de chequeos nuevos | modificar |
| `backend/app/qa/visual.py` | harness de QA visual (§7.B) para Actions/local | nuevo |
| `tools/visual_qa.py` | ejecución local de 7.B | nuevo |
| `tools/anonimizar_extracto.py` | anonimización local de extractos (§10) | nuevo |
| `tools/build_site.py` | estampar versión/SHA; incluir módulos y JSON nuevos en `app.zip` | modificar |
| `backend/app/web/service.py`, `bridge.py` | exponer campos nuevos, manifiesto, parámetros de escenarios, estado de reproducibilidad | modificar |
| `frontend/index.html`, `frontend/worker.js` | mostrar tipo/gravedad/estado/efecto; panel de escenarios; reproducibilidad | modificar |
| `.github/workflows/pdf.yml` (o nuevo `visual-qa.yml`) | ejecutar 7.B con datos sintéticos/anonimizados | modificar/nuevo |
| `.github/workflows/release.yml` | etiquetar y publicar `app-vX.Y.Z` con su `app.zip` (si se autoriza A-5) | nuevo |
| `docs/CONTRATO_DATOS.md`, `docs/ARQUITECTURA.md`, `docs/VALIDACION_DATOS_REALES.md` | documentar definiciones, reglas, procedencia y procedimiento | modificar/nuevo |
| `tests/unit/…` (ver §11.2) y `tests/regression/base/` | las 22 pruebas obligatorias nuevas y la línea base | nuevo |

No se tocan: plantillas, importadores, aritmética `Decimal`, `deck/glp1_mensual.py`, módulo de IA.

---

## 10. Validación con datos reales (extractos anonimizados)

**Estado actual: no hay datos reales disponibles para este proyecto.** Los archivos de `data/ejemplos` son sintéticos o simulados. Nada de lo que sigue se da por cumplido.

### 10.1 Qué necesito (extractos reales, **opcionales para iniciar Fase 1**)

Los nombres de columna son los de los machotes (fuente de verdad). Si el sistema real usa otros, se acepta y se documenta el mapeo en `mapeo_columnas.json`. **No se piden columnas que los machotes no tienen.**

**GLP-1**
| Hoja | Columnas | Granularidad |
|---|---|---|
| `ventas` | `fecha_pedido`, `id_pedido`, `id_paciente` (seudonimizado), `paciente_nuevo`, `sku`, `canal`, `estado`, `region`, `piezas`, `monto_venta`, `forma_pago`, `modo_entrega`, `programa_lealtad` | Línea de pedido |
| `catalogo` | `sku`, `producto`, `categoria` | SKU |
| `trafico` | `mes`, `vista`, `valor`, `sku`, `visitas`, `usuarios`, `usuarios_nuevos`, `usuarios_recurrentes`, `vistas_producto`, `add_to_cart`, `begin_checkout`, `compras`, `carritos_abandonados`, `sesiones_rebote`, `segundos_interaccion_total` | Mes × vista × valor × SKU opcional (nivel sitio: `vista = general`, `sku` vacío) |
| `negados` | `producto`, `sku`, `alta`, `pedidos`, `cantidad_negada`, `monto_negado` | Producto (sin fecha) |

**AETOPS**
| Hoja | Columnas | Granularidad |
|---|---|---|
| `ventas` | `fecha_pedido`, `id_pedido`, `id_paciente` (seudonimizado), `paciente_nuevo`, `sku`, `canal`, `estado`, `sucursal`, `piezas`, `monto_venta` | Línea de pedido |
| `catalogo` | `sku`, `producto`, `linea`, `categoria`, `laboratorio` | SKU |
| `negados` | `producto`, `sku`, `alta`, `pedidos`, `cantidad_negada`, `monto_negado` | Producto (sin fecha) |
| *(sin `trafico`)* | AETOPS no tiene hoja de tráfico en el machote ni en el contrato vigente; **no se solicita** | — |

**Información adicional que sí se necesita de ti** (no son columnas): (1) la **unidad** en que tu herramienta de analítica reporta `add_to_cart` (eventos, sesiones u otra); (2) el **periodo, filtros y universo** con que se exportó `trafico` y con que se extrajo `ventas`; (3) qué fuente de pedidos usas como referencia del negocio (AMB-1); (4) cómo se define `carritos_abandonados` cuando viene informado por la fuente (AMB-10); (5) si el archivo de `ventas` incluye canales distintos al web (AMB-9). **No se solicita ningún identificador de carrito, transacción o sesión.**

### 10.2 Periodo
- **Mínimo:** un mes cerrado `M`, el mes anterior `M-1` y el mismo mes del año anterior `M-12` (para variaciones y YoY).
- Para el reporte trimestral de GLP-1: un trimestre cerrado, el trimestre anterior y el mismo trimestre del año anterior.
- Preferible: dos meses distintos de `M` (uno de alta y otro de baja demanda) para probar umbrales.

### 10.3 Qué se anonimiza (antes de salir de tu equipo)
- **Se reemplaza de forma consistente (HMAC con sal local que no se comparte):** `id_paciente` e `id_pedido`. La consistencia preserva conteos distintos, relaciones paciente–pedido y duplicados.
- **Se elimina:** nombres, correos, teléfonos, direcciones, fechas de nacimiento, diagnósticos, notas y cualquier texto libre que existiera en el extracto (los machotes no contienen ninguno de estos campos).
- **Se conserva** (necesario para validar reglas): `fecha_pedido`, `estado` (entidad federativa), `sucursal` o `region`, `canal`, `sku`, `piezas`, `monto_venta`, `forma_pago`, `modo_entrega`, `programa_lealtad` y las métricas de `trafico`.
- Si montos o SKU resultan sensibles, se aplica un **factor multiplicativo único** por archivo (conserva proporciones, ratios y relaciones entre archivos si se usa el mismo factor en todos). Se declara en el procedimiento; no afecta reglas de conteo ni de cuadre.
- `tools/anonimizar_extracto.py` se ejecuta **en tu equipo**; solo salen los archivos ya anonimizados. Esos archivos no se suben al repositorio público: se entregan por el canal que tú elijas.

### 10.4 Validación sintética vs validación operacional, por regla

| Regla / función | Validación **sintética** (Fase 1, automatizada) | Validación **operacional** (requiere datos reales y tu confirmación) | Etiqueta mientras tanto |
|---|---|---|---|
| `R-REL-PAC-PED` | Clasificación de `id_pedido` (C2/E activas; C0/C1 reservadas), partición A/B/C, líneas múltiples, duplicados, recurrentes, universos distintos, sin `id_paciente` (T-01) | `m = 1` describe tu operación; qué es un «paciente»; si algún día existiera estatus, que el tratamiento de C0/C1 (AMB-4) sea el deseado | No validada con datos reales |
| `R-CUADRE-DIM` | Las cuatro combinaciones exclusiva/exhaustiva, «Sin asignar» virtual, superposición, tolerancia y dimensiones tipo machote (T-02) | Qué dimensiones reales son exclusivas y exhaustivas y su justificación; tolerancia por redondeo real | No validada con datos reales |
| `R-CONC-COMPRAS` | Brecha 0 %, 10 %, 30 %; falta un lado; periodos distintos | Umbral útil (el 20 % es un supuesto) y causas reales de la brecha | No validada con datos reales |
| `R-DENOM` | Denominador 0, ausente, válido | No aplica: es lógica pura | No aplica (validación sintética completa) |
| `R-COBERTURA-ATC` e IND-01 | Estados calculable / con limitación / no calculable; periodos, fuentes y universos distintos; unidad no declarada; > 100 %; faltantes (T-05, T-10, T-21) | **Unidad real** de «carritos agregados», fuente de referencia de «pedidos realizados» (AMB-1) y si la fórmula coincide con la que ya usas | No validada con datos reales |
| Escenarios E1/E2 | Aritmética, etiquetas, «No configurado» | Realismo de 25 % y 10 % (solo contrastable con históricos) | Supuesto heredado, no validado |
| QA estructural / visual | Decks sintéticos con defectos inyectados | Muestra de decks reales para falsos positivos | — |
| Procedencia / reproducibilidad | Totalmente sintético | — | No aplica |

### 10.5 Dos niveles de validación y cómo se rotulan

- **Validación sintética:** las pruebas automatizadas confirman que el código hace lo que dice la definición, con datos construidos de respuesta conocida. Se expresa como «lógica verificada». **No** afirma que la definición sea correcta para tu negocio.
- **Validación operacional:** con extractos reales anonimizados se comprueba (a) que las columnas existen y se mapean, (b) que la definición coincide con tu operación —lo confirmas tú—, (c) que umbrales y tolerancias son razonables. Se registra en `validacion_registro.json`. El estado `confirmada` **solo** se asigna con tu confirmación explícita.
- Una regla se muestra como regla de negocio confirmada únicamente con `validacion_operacional = confirmada`. En cualquier otro caso su hallazgo, el anexo y el manifiesto dicen **«No validada con datos reales»**, y las dos validaciones aparecen por separado.

### 10.6 Iniciar sin extractos y sumarlos después sin rehacer la arquitectura

**Inicio sin extractos (permitido).** Fase 1 puede implementarse con datos sintéticos. Las reglas con validación operacional pendiente quedan activas con parámetros por defecto declarados, rotuladas «No validadas con datos reales», y ninguna bloquea.

**Incorporación posterior, sin tocar código:**
1. Aportas el extracto anonimizado (y la unidad, periodo y filtros de «carritos agregados» y de «pedidos realizados»).
2. Se ajusta `mapeo_columnas.json` si tus columnas tienen otros nombres.
3. Se ejecuta el **modo informe de validación**: reglas sin generar deck; cuántas veces dispara cada una, qué columnas faltan, en qué estado queda la relación pedidos/carritos.
4. Revisas el informe y confirmas o corriges definiciones y umbrales.
5. Se actualiza `reglas.json` (nueva `regla_version`), `definiciones.json` y `validacion_registro.json` (`operacional = confirmada`, extracto, fecha, confirmante).
6. Los reportes nuevos usan la versión nueva; los anteriores conservan la suya (§5). La prueba T-17 simula este flujo con un extracto sintético, sin cambios de código.

### 10.7 Qué reglas dependen de información real
`R-REL-PAC-PED` (valor de `m`), `R-CUADRE-DIM` (propiedades de cada dimensión), `R-CONC-COMPRAS` (umbral), `R-COBERTURA-ATC` e IND-01 (unidad y fuente de los agregados) y los escenarios (porcentajes heredados). Todas salen «No validadas con datos reales» en Fase 1 hasta que exista el registro de validación operacional. Los datos sintéticos **nunca** se presentan como evidencia operacional, y los machotes lo son (`LEEME.md`).

### 10.8 Resumen de privacidad, datos e IA (reglas vigentes, sin debilitar)
- **Datos del usuario:** se procesan en el navegador; no se envían a un servidor propio. El paso por GitHub Actions solo se admite con datos sintéticos (A-6, recomendación pendiente).
- **Identificadores:** `id_paciente` e `id_pedido` anónimos (hash); nunca nombres ni datos de contacto. El manifiesto de procedencia no guarda el contenido de los archivos (§5.1).
- **Datos sintéticos vs operativos:** las fixtures de pruebas son sintéticas y se marcan `sintetico: true` (T-20); ninguna prueba automatizada lee datos reales sin autorización expresa.
- **IA (opcional, Cohere, clave del usuario):** la llamada sale del navegador y envía **párrafos de texto ya verificados** (cifras agregadas), no filas de ventas ni identificadores. La IA **no modifica cifras, no calcula y no es fuente de verdad**: todo texto se re-verifica contra las cifras del motor y se descarta si introduce una cifra nueva (T-14). Es una excepción consciente y opcional a «los datos no salen del navegador».
- **Fase 1 no amplía** los permisos de la IA ni los controles de privacidad.

---

## 11. Pruebas

### 11.1 Línea base (antes de tocar código) — prerrequisito P-00
Congelar en `tests/regression/base/`: valores del motor (JSON canónico), lista de hallazgos (`id`, `severity`), texto de cada lámina y hash de formas estáticas, para los ejemplos AETOPS y GLP-1 (mensual y trimestral). **P-00 no es una prueba: es una acción que debe ocurrir antes de cualquier cambio de código**, porque después no existiría el código de referencia.

**Evidencia ya disponible de la línea base (no de Fase 1):** S-01 en línea base: 181 passed in 475.65s (pytest tests/unit, sobre c8ba722, árbol limpio). Evidencia de la línea base previa a Fase 1; no es evidencia de aceptación de Fase 1. La suite golden (S-02) no se ejecutó en esta revisión.

### 11.2 Inventario único de pruebas

Cada prueba tiene requisito, entrada, resultado esperado, criterio de aprobación, dependencias, prerrequisitos, criterio de aceptación y estado. **Estado: ninguna prueba de Fase 1 está ejecutada ni aprobada**; todas figuran «Pendiente». La suite S-01 existente tiene la evidencia de línea base citada arriba, pero su aprobación para Fase 1 también queda «Pendiente» hasta ejecutarla sobre la implementación.

| ID | Tipo | Requisito | Entrada | Resultado esperado | Criterio de aprobación | Dependencias de ejecución | Activación | Prerrequisitos | AC | Estado |
|---|---|---|---|---|---|---|---|---|---|---|
| T-20 | Obligatoria | RQ-29 | `tools/make_fixtures_fase1.py` ejecutado dos veces; recorrido de `tests/fixtures/fase1/` | Mismo hash en ambas ejecuciones; cada fixture con `sintetico: true`; ninguna prueba abre rutas fuera del directorio de fixtures | Hashes iguales; 0 fixtures sin la marca; 0 lecturas de datos reales | Python | Siempre | — | AC-26 | Pendiente |
| T-22 | Obligatoria | RQ-32 | Encabezados reales de `data/ejemplos/GLP1_crudo_ejemplo.xlsx` y `AETOPS_crudo_ejemplo.xlsx` (sintéticos, versionados) y la tabla de §3.0; AETOPS sin hoja `trafico` | Columnas documentadas = encabezados reales (GLP-1: 13/3/15/6 columnas en `ventas`/`catalogo`/`trafico`/`negados`; AETOPS: 10/5/6 en `ventas`/`catalogo`/`negados`); reglas con `trafico` devuelven «No aplica» en AETOPS; el pipeline AETOPS corre sin `trafico` | Igualdad exacta de conjuntos de columnas; 0 exigencias de `trafico` a AETOPS; 0 campos inventados | Python; `openpyxl`; archivos de `data/ejemplos` | Siempre | — | AC-32 | Pendiente |
| T-06 | Obligatoria | RQ-07, RQ-08, RQ-09 | Hallazgos de los ejemplos AETOPS y GLP-1 de la línea base; constructor con y sin campos nuevos | `severity` ↔ `efecto_generacion`; firma posicional intacta; todo `id` existente en el catálogo; JSON conserva `severity`; `no_verificable` con `faltante` | 100 % de `id` y `severity` iguales a la línea base; ninguna prueba previa editada | Python | Siempre | P-00 | AC-02, AC-03, AC-04 | Pendiente |
| T-07 | Obligatoria | RQ-06, RQ-10 | Pipeline con fixtures sintéticas dos veces; una vez con un dato alterado | Manifiesto con los 9 campos; hashes estables; `hash_resultado` igual en dos corridas y distinto con el dato alterado; sin contenido de archivos en el manifiesto | Los 9 campos presentes; igualdad/diferencia de hash según el caso | Python | Siempre | T-20 | AC-10 | Pendiente |
| T-04 | Obligatoria | RQ-04 | `denom.json`: denominador 0, ausente, válido | 0 y ausente ⇒ «No verificable» con `faltante`; válido ⇒ ratio | Ningún 0 % por denominador cero; ≥ 3 casos | Python | Siempre | T-20, T-06 | AC-08, AC-04 | Pendiente |
| T-01 | Obligatoria | RQ-01 | `rel_pac_ped_base.json`: 6 `id_pedido` de §3.3 con `m=1`; variantes `m=2`, sin `id_paciente`, cobertura baja, universos distintos, KPI sobre filas, filas triplicadas, y variante con columna de estatus reservada (casos C0/C1, desactivada por defecto) | Base `m=1`: C2=1, E=5; A=3, B=1, C=1; `P_U`=2; cobertura de paciente 60 %; razón 1,5; 2 `advertir` + 2 `informar`. `m=2`: A=4, C=∅, 80 %. Universos distintos: `no_verificable` sin `advertir`. KPI sobre filas: `informar`. Variante con estatus: C0=1, C1=1 y 3 `advertir`. Sin columna de estatus: C0=C1=∅ | Valores exactos; identidades de control; resultado idéntico con filas triplicadas (0 conteos sobre filas); ≥ 12 casos | Python; fixtures sintéticas | Siempre; los casos con estatus se activan solo con la variante de configuración | T-20, T-06 | AC-05 | Pendiente |
| T-02 | Obligatoria | RQ-02 | `cuadre_dim_*.json`: los 4 ejemplos de §3.3 (cumple/incumple), No/No con `S<T` y `S>T`, dimensión sin propiedades, sin justificación, tolerancia, montos negativos, entidad de conteo distinto, «Sin asignar» virtual, superposición, y dos casos tipo machote (pedidos por `sucursal` AETOPS: no exclusiva/exhaustiva; pedidos por `canal`: exclusiva/exhaustiva) | Sí/Sí: `S=T`; Sí/No: `S≤T`; No/Sí: `S≥T`; No/No: nunca `advertir`; sin propiedades o justificación: `no_verificable`; incumplimiento: `inconsistente` + `advertir` | 16 casos pasan con resultado exacto | Python; fixtures sintéticas | Siempre | T-20, T-06 | AC-06 | Pendiente |
| T-21 | Obligatoria | RQ-31, RQ-03 | `fuentes_pedidos.json`: GLP-1 con ambas fuentes (pedidos del sistema de ventas y compras GA4) y casos en que falta una | Cada resultado nombra su fuente; no se sustituye una por otra; no se suman; no se presentan como equivalentes; falta una fuente ⇒ ese resultado «No calculable» sin tomar la otra; ambas relaciones, si se muestran, son independientes | 0 sustituciones, 0 sumas, 0 rótulos de equivalencia; ≥ 6 casos | Python; fixtures sintéticas | Siempre | T-20, T-06 | AC-29 | Pendiente |
| T-03 | Obligatoria | RQ-03, RQ-31 | `conc_compras.json`: brecha 0 %, 10 %, 30 %; umbral 20 % por defecto y otro configurado; falta un lado; periodos distintos; AETOPS sin `trafico` | Cada lado con su fuente; el aviso se emite solo si la brecha supera el umbral, con texto neutro (sin «error»); faltante ⇒ `no_verificable`; causas como hipótesis; datos de ventas sin cambio; AETOPS «No aplica» | ≥ 8 casos pasan; comparación de pedidos antes/después idéntica | Python; fixtures sintéticas | Siempre | T-20, T-06 | AC-07, AC-29 | Pendiente |
| T-05 | Obligatoria | RQ-05 | `comparabilidad.json`: periodos iguales y distintos; fuente, universo o filtro distinto; universo no declarado; unidad declarada (eventos, sesiones) y no declarada; falta numerador; falta carritos; carritos = 0; relación > 100 %; pedidos = 0 explícito | `calculable` (todo declarado y coincidente); `calculable_con_limitacion` (sin variaciones si periodos distintos; unidad no declarada ⇒ «interpretación limitada»); `no_calculable` con `faltante`; pedidos = 0 ⇒ 0 % calculable; > 100 % ⇒ valor conservado y advertencia; nunca «carritos únicos» con unidad eventos | ≥ 12 casos; ningún valor sustituido, truncado o inventado | Python; fixtures sintéticas | Siempre | T-20, T-06 | AC-09, AC-31, AC-30, AC-04 | Pendiente |
| T-08 | Obligatoria | RQ-11 | Manifiestos sintéticos: coincidente, con versión distinta, archivo faltante, sin manifiesto, hash de entrada distinto | `exacta` / `parcial` / `no_reproducible`; nunca regenera en silencio; legado ⇒ `no_reproducible` | Estado correcto en cada caso; diferencias listadas en `parcial` | Python | Siempre | T-07 | AC-11, AC-12 | Pendiente |
| T-09 | Obligatoria | RQ-16, RQ-18 | Ejemplos con negados; `reglas.json` con 25 % y valores `null` | Fórmula `M_neg × 0,25` idéntica a la actual; conservador/optimista «No configurado»; etiqueta «Supuesto heredado, no validado»; cifras de láminas = línea base | Igualdad exacta de cifras; etiqueta presente; ningún valor inventado | Python | Siempre | T-20, P-00 | AC-13 | Pendiente |
| T-10 | Obligatoria | RQ-28, RQ-31 | `rel_ped_car.json`: 1 000 carritos y 250 pedidos (25 %); 1 000 carritos y 1 200 pedidos (120 %); GLP-1 sept-2026 del machote (2 356 pedidos del sistema de ventas, 2 643 compras GA4, 18 883 carritos); fixtures **sin** columnas de ID de carrito, transacción o sesión | 25 % exacto; 120 % conservado con advertencia; machote: 12,48 % (ventas) y 14,00 % (GA4) como resultados independientes e identificados; texto «por cada 100 carritos agregados, N pedidos … fuente seleccionada»; los tres elementos visibles; ninguna denominación prohibida; ningún `100 − relación` | `Decimal` exacto; 0 coincidencias de denominaciones prohibidas en anexo, panel y hallazgos; cálculo posible sin ninguna columna de ID | Python; fixtures sintéticas; machote GLP-1 de `data/ejemplos` | Siempre | T-20, T-05, T-21 | AC-22, AC-23, AC-30, AC-29 | Pendiente |
| T-10b | Obligatoria | RQ-17, RQ-18 | GLP-1 de ejemplo con `carritos_abandonados` presente y derivado (`add_to_cart − compras`) | Fórmula `A × 0,10 × T` idéntica a la actual en ambos casos; marca «derivado» conservada; denominación histórica «Recuperación de abandono» intacta; aclaración de §8.3 solo en panel/anexo; lámina sin cambio sin A-3 | Igualdad exacta con la línea base; aclaración presente en salidas nuevas | Python | Siempre | T-20, P-00 | AC-13 | Pendiente |
| T-11 | Obligatoria | RQ-13, RQ-15, RQ-18, RQ-19 | Decks sintéticos: uno limpio y otros con defectos inyectados (token, duplicado, fuente < mínima, unidad sin denominador, fórmula alterada, cifra no trazada, forma fuera de lienzo) | Cada defecto detectado con su `id`; deck limpio sin errores; anexo presente; etiquetas «Revisión estructural» | 100 % de defectos detectados y 0 falsos positivos en decks de referencia | Python, python-pptx | Siempre | T-20, T-10 | AC-14, AC-15 | Pendiente |
| T-12 | Condicional | RQ-14 | Deck sintético con solape, texto recortado, gráfica vacía y contraste bajo inyectados | PNG por diapositiva; los defectos se detectan; informe generado | Detección de los defectos inyectados y 0 falsos positivos en decks de referencia | LibreOffice + pdftoppm; **no está en `tests.yml`** | Se activa si `soffice` y `pdftoppm` están en el PATH; se ejecuta en `visual-qa.yml` (Actions, solo datos sintéticos) o con `tools/visual_qa.py` local. Si no, `omitida (sin LibreOffice)` | T-20, T-11 | AC-16 | Pendiente |
| T-13 | Obligatoria | RQ-08, RQ-22, RQ-24 | Línea base congelada (`tests/regression/base/`) y ejecución con flags activos y desactivados | Con flags activos: valores y `severity` iguales; diferencias solo con entrada en `CAMBIOS_JUSTIFICADOS.md`. Con flags desactivados: salida idéntica | 0 diferencias numéricas no justificadas; igualdad total con flags desactivados | Python | Siempre | P-00, T-06 | AC-01, AC-21, AC-02 | Pendiente |
| T-14 | Obligatoria | RQ-23 | Salidas de IA simuladas (modelo falso) que intentan cambiar cifras de escenarios y de la relación pedidos/carritos o reemplazar un indicador | Se rechaza todo texto con cifras fuera del conjunto verificado; se conserva la versión determinista | 0 cifras nuevas aceptadas; pruebas de IA existentes sin cambios | Python (sin red) | Siempre | T-09, T-10 | AC-27 | Pendiente |
| T-15 | Obligatoria | RQ-20 | Extracto sintético con campos prohibidos y relaciones paciente–pedido conocidas | Conteos distintos y relaciones preservados; campos prohibidos eliminados | Igualdad de conteos antes/después; 0 campos prohibidos | Python | Siempre | T-20 | AC-17 | Pendiente |
| T-16 | Obligatoria | RQ-10, RQ-12 | `build_site.py` ejecutado en CI | `app.zip` contiene módulos y JSON nuevos y versión/SHA estampados | Archivos presentes; versión legible desde el zip | Python; ruedas vendorizadas | Siempre | T-07 | AC-10, AC-28 | Pendiente |
| T-18 | Obligatoria | RQ-26 | Registro de validación con reglas `confirmada` y no confirmadas | Toda regla no confirmada muestra «No validada con datos reales» en hallazgo, anexo y manifiesto; validaciones sintética y operacional separadas | 0 reglas presentadas como confirmadas sin registro | Python | Siempre | T-20, T-06 | AC-24 | Pendiente |
| T-17 | Obligatoria | RQ-27 | Extracto sintético con nombres de columna distintos; `mapeo_columnas.json` actualizado; `reglas.json` y `validacion_registro.json` actualizados | El mapeo lo acepta sin cambios de código; el modo informe corre; la actualización cambia `regla_version` y el rótulo a `confirmada`; reportes previos conservan su versión | 0 archivos de código modificados; estados esperados | Python | Siempre | T-20, T-07, T-18 | AC-25, AC-23 | Pendiente |
| T-19 | Obligatoria | RQ-25 | Generación de los ejemplos sintéticos con flags desactivados (referencia) y activados, 5 corridas cada una, en el mismo job | Mediana con flags activos ≤ 1,15 × mediana con flags desactivados | Umbral cumplido en el mismo runner | Python; runner de CI | Siempre | T-13 | AC-20 | Pendiente |
| V-01 | Condicional (manual) | RQ-21 | Extractos reales anonimizados, **si y cuando** el usuario los entregue | Informe de validación (disparos por regla, columnas faltantes, estado de la relación) | Informe revisado y confirmado por el usuario | Extractos reales; ejecución **local**, no en Actions | Se activa solo si A-2 se autoriza y el usuario entrega extractos; si no, `omitida (sin extractos)` | T-17 | AC-18 | Pendiente |
| V-02 | Condicional (manual) | RQ-12 | Ejecución del workflow `release.yml` en GitHub | Release `app-vX.Y.Z` con `app.zip` y SHA | Asset descargable con SHA coincidente | GitHub Actions | Se activa solo si A-5 se autoriza; si no, `omitida (A-5 no autorizada)` | T-16 | AC-28 | Pendiente |
| S-01 | Obligatoria (existente) | RQ-30 | Suite unitaria existente (`tests/unit`), sin editar | Todas pasan | 100 % `aprobada` | Python; las pruebas que requieren plantillas o LibreOffice se omiten por su propia condición | Siempre (se corre en la línea base y de nuevo en cada PR) | P-00 | AC-19 | Pendiente |
| S-02 | Condicional (existente) | RQ-30 | Suite golden existente (35 pruebas) | Todas pasan cuando se ejecuta | `aprobada` u `omitida`; nunca aprobada sin ejecutarse | `REPORT_FIXTURES_DIR` con plantillas reales no versionadas; ejecución local | Se activa solo si `REPORT_FIXTURES_DIR` apunta a las plantillas; si no, `omitida (sin REPORT_FIXTURES_DIR)` | P-00 | AC-19 | Pendiente |

### 11.3 Orden de ejecución, dependencias y condiciones

**Obligatorias nuevas (22):** T-01 a T-11, T-10b y T-13 a T-22. **Más** la suite unitaria existente S-01. **Condicionales (4):** T-12, S-02, V-01 y V-02.

**Orden técnicamente posible (oleadas).** Una prueba solo se ejecuta cuando todos sus prerrequisitos están `aprobada`. El grafo de prerrequisitos es **acíclico** (verificado al generar este documento) y P-00 precede a todo:

- **Oleada 0:** S-01, S-02, T-06, T-20, T-22
- **Oleada 1:** T-01, T-02, T-03, T-04, T-05, T-07, T-09, T-10b, T-13, T-15, T-18, T-21
- **Oleada 2:** T-08, T-10, T-16, T-17, T-19
- **Oleada 3:** T-11, T-14, V-01, V-02
- **Oleada 4:** T-12

Las dependencias reflejan cobertura que ya existía: T-17 requiere T-18 y T-07 (ambas en la oleada anterior), T-12 requiere el deck de T-11 y las fixtures de T-20, T-10 requiere T-05 y T-21 (los estados y las fuentes se prueban antes del indicador completo). No hay pruebas que se requieran mutuamente.

**Condiciones de activación de las condicionales**

| Prueba | Condición de activación | Si no se cumple |
|---|---|---|
| T-12 | Se activa si `soffice` y `pdftoppm` están en el PATH; se ejecuta en `visual-qa.yml` (Actions, solo datos sintéticos) o con `tools/visual_qa.py` local. Si no, `omitida (sin LibreOffice)` | `omitida (motivo)` si no se cumple |
| V-01 | Se activa solo si A-2 se autoriza y el usuario entrega extractos; si no, `omitida (sin extractos)` | `omitida (motivo)` si no se cumple |
| V-02 | Se activa solo si A-5 se autoriza; si no, `omitida (A-5 no autorizada)` | `omitida (motivo)` si no se cumple |
| S-02 | Se activa solo si `REPORT_FIXTURES_DIR` apunta a las plantillas; si no, `omitida (sin REPORT_FIXTURES_DIR)` | `omitida (motivo)` si no se cumple |

**Estados permitidos:** `pendiente`, `aprobada`, `fallida`, `omitida (motivo)`. Una prueba **omitida o no ejecutada nunca se reporta como aprobada**; el informe de CI lista las omitidas con su motivo y lugar de ejecución previsto. Una prueba cuyo prerrequisito está `fallida` u `omitida` queda `omitida (prerrequisito: …)`.

### 11.4 Escenarios de prueba reproducibles y sin datos reales
- Las fixtures se **generan** con `tools/make_fixtures_fase1.py` con **semilla fija** y se versionan en `tests/fixtures/fase1/` con un manifiesto (`sintetico: true`, hash, versión del generador).
- Los ejemplos numéricos de esta especificación (6 pedidos de §3.3, 4 combinaciones de §3.3, 1 000/250 y 1 000/1 200 de §8.2) son las fixtures de referencia.
- T-10 y T-22 usan además los **machotes sintéticos versionados** de `data/ejemplos` (no son datos reales).
- **Ninguna prueba automatizada usa datos reales** sin autorización expresa. Los datos sintéticos **no** se presentan como evidencia operacional (§10.5).

### 11.5 Evidencia esperada por prueba

| Prueba | Evidencia que demostraría que fue superada |
|---|---|
| T-20 | Informe JUnit + manifiesto de fixtures |
| T-22 | Informe JUnit de T-22 |
| T-06 | Informe JUnit de T-06 |
| T-07 | Informe JUnit de T-07 |
| T-04 | Informe JUnit de T-04 |
| T-01 | Informe JUnit de T-01 |
| T-02 | Informe JUnit de T-02 |
| T-21 | Informe JUnit de T-21 |
| T-03 | Informe JUnit de T-03 |
| T-05 | Informe JUnit de T-05 |
| T-08 | Informe JUnit de T-08 |
| T-09 | Informe JUnit de T-09 |
| T-10 | Informe JUnit de T-10 |
| T-10b | Informe JUnit de T-10b |
| T-11 | Informe JUnit de T-11 |
| T-12 | PNG + informe de hallazgos |
| T-13 | Informe JUnit de T-13 |
| T-14 | Informe JUnit de T-14 |
| T-15 | Informe JUnit de T-15 |
| T-16 | Informe JUnit de T-16 |
| T-18 | Informe JUnit de T-18 |
| T-17 | Informe JUnit de T-17 |
| T-19 | Medianas registradas en el job |
| V-01 | Informe de validación |
| V-02 | Asset y log del workflow |
| S-01 | Informe de pytest |
| S-02 | Informe de pytest local |

### 11.6 Cambio justificado
Si una modificación cambia un resultado, se registra en `CAMBIOS_JUSTIFICADOS.md` `{regla_id, descripción, valor_antes, valor_después, ejemplo, autorizado_por}`. Sin entrada, T-13 falla.

---

## 12. Criterios de aceptación medibles

Un criterio **no se considera satisfecho por estar documentado**: solo cuando la prueba o verificación asociada (§14) tiene estado `aprobada` con su evidencia.

| ID | Criterio |
|---|---|
| AC-01 | **0 diferencias** en valores numéricos respecto a la línea base, salvo las listadas en `CAMBIOS_JUSTIFICADOS.md` con autorización |
| AC-02 | 100 % de los `id` de hallazgo existentes conservan el mismo `severity`; la UI y las pruebas previas pasan sin edición |
| AC-03 | 100 % de los hallazgos nuevos y migrados tienen `tipo`, `gravedad`, `estado_verificacion`, `efecto_generacion`; los nuevos además `regla_id` y `regla_version` |
| AC-04 | Todo hallazgo con `estado_verificacion = no_verificable` trae `faltante` no vacío; **0** valores inventados o ceros implícitos |
| AC-05 | `R-REL-PAC-PED`: ≥ 12 casos (T-01) pasan con los valores exactos de §3.3 (ejemplo de 6 pedidos con `m=1` y `m=2`); opera sobre `id_pedido` e `id_paciente` distintos (**0** conteos sobre filas); se cumplen las identidades de control; **0** alertas cuando la diferencia se explica por granularidad o por universos distintos; las clases C0/C1 permanecen inactivas sin columna de estatus; no bloquea |
| AC-06 | `R-CUADRE-DIM`: ≥ 16 casos (T-02) pasan, incluidas las **cuatro combinaciones** exclusiva/exhaustiva con un caso que cumple y uno que incumple, y los casos de dimensiones de los machotes (pedidos por `sucursal` en AETOPS no exclusivos); No/No nunca emite `advertir`; una dimensión sin propiedades o sin justificación no se evalúa |
| AC-07 | `R-CONC-COMPRAS`: ≥ 8 casos (T-03) pasan; cada lado identifica su fuente («sistema de ventas» / «GA4»); ninguna fuente sustituye ni se suma a la otra; la diferencia se informa sin llamarla error ni intentar correspondencia individual; el umbral es configurable (default 20 %, aviso heredado); no modifica datos de ventas; no aplica a AETOPS (sin `trafico`) |
| AC-08 | `R-DENOM`: ≥ 3 casos (T-04) pasan; **0** ratios con denominador cero mostrados como 0 % |
| AC-09 | `R-COBERTURA-ATC`: ≥ 12 casos (T-05) pasan con los tres estados de §8.2; periodos distintos ⇒ sin variaciones y con limitación; universos, filtros o fuentes distintos ⇒ advertencia de no comparabilidad; unidad no declarada ⇒ cálculo con limitación; faltante ⇒ «No calculable» sin valor sustituido |
| AC-10 | Manifiesto con los 9 campos de §5.1 en el 100 % de los reportes nuevos; `hash_resultado` idéntico en dos corridas con las mismas entradas; versión y SHA estampados en `app.zip` |
| AC-11 | Los tres estados de §5.3 se producen y se muestran correctamente; **0** regeneraciones silenciosas con versiones distintas |
| AC-12 | Los reportes previos a Fase 1 se muestran como `no_reproducible (legado)` |
| AC-13 | Escenarios E1 y E2: solo los valores heredados (25 % y 10 %) visibles, con fórmula, variable y la etiqueta «Supuesto heredado, no validado»; E2 conserva su denominación histórica y fórmula `A × c × T`; en las salidas **nuevas** la métrica `carritos_abandonados` lleva la aclaración de §8.3; conservador/optimista ausentes («No configurado»); fórmulas y cifras de las láminas actuales **idénticas** a la línea base sin A-3; los supuestos nunca se presentan como resultados observados |
| AC-14 | QA estructural detecta 100 % de los defectos inyectados (token, duplicado, fuente mínima, unidad sin denominador, fórmula alterada, cifra no trazada) con **0 falsos positivos** en los decks de referencia |
| AC-15 | La interfaz nunca presenta el QA estructural como «revisión visual» ni declara «verificado visualmente» sin render |
| AC-16 | *(Condicional)* QA visual produce PNG por diapositiva y un informe de hallazgos con datos sintéticos; no se ejecuta en Actions con datos reales sin autorización expresa |
| AC-17 | `tools/anonimizar_extracto.py` conserva conteos distintos y relaciones y no deja campos prohibidos |
| AC-18 | *(Condicional)* Informe de validación con datos reales entregado **cuando existan los extractos** y con tu confirmación; mientras no existan, las reglas de §10.4 figuran como «No validadas con datos reales» y Fase 1 puede cerrarse sin ellos |
| AC-19 | Inventario de pruebas (§11.2) completo y consistente: las **22 pruebas obligatorias nuevas** (T-01 a T-11, T-10b y T-13 a T-22) y la suite unitaria existente (S-01) terminan `aprobada` en CI, ejecutadas en el orden de §11.3; las condicionales (T-12, S-02, V-01, V-02) terminan `aprobada` u `omitida` con motivo y lugar de ejecución registrados — **ninguna se reporta como aprobada si no se ejecutó**; 0 pruebas sin requisito, AC, entrada, resultado esperado, criterio de aprobación y evidencia; 0 requisitos sin prueba o verificación asociada; 0 dependencias circulares |
| AC-20 | Tiempo de generación en el navegador (mediana de 5 corridas con los ejemplos sintéticos) no aumenta más de 15 % frente a la línea base (flags desactivados en el mismo job) |
| AC-21 | Con los flags de Fase 1 desactivados, la salida es idéntica a la línea base |
| AC-22 | Relación pedidos/carritos: `(pedidos / carritos) × 100` exacta en `Decimal` (ejemplo 250/1 000 ⇒ 25 %); se muestran volumen de carritos (con su unidad o «unidad no declarada»), volumen de pedidos, fuente de pedidos y relación; **0** apariciones de las denominaciones prohibidas de §8.2 en salidas nuevas; **0** cálculos de `100 − relación` |
| AC-23 | La metodología agregada no exige identificadores: la relación se calcula con fixtures que **no contienen** ninguna columna de ID de carrito, de transacción o de sesión, `id_pedido` no se usa como sustituto de un ID de carrito, y `mapeo_columnas.json` no define ni detecta tales identificadores |
| AC-24 | Toda regla con validación operacional no confirmada muestra «No validada con datos reales»; **0** reglas presentadas como confirmadas sin registro; validación sintética y operacional siempre diferenciadas |
| AC-25 | Un extracto sintético con otros nombres de columna se incorpora solo con cambios de configuración; **0** cambios de código |
| AC-26 | Todas las fixtures de `tests/fixtures/fase1/` son sintéticas (`sintetico: true`), se regeneran de forma determinista (mismo hash en dos ejecuciones) y ninguna prueba automatizada lee datos reales |
| AC-27 | La IA no introduce ni modifica cifras: 0 cifras fuera del conjunto verificado en pruebas con modelo simulado, incluidas las de escenarios y la relación pedidos/carritos; la IA no calcula ni sustituye indicadores determinísticos |
| AC-28 | *(Condicional, si se autoriza A-5)* El workflow de release publica `app-vX.Y.Z` con su `app.zip` y su SHA |
| AC-29 | Fuentes de pedidos diferenciadas: **0** casos en que una fuente sustituya a la otra, se sumen ambas o se presenten como equivalentes; cada resultado nombra su fuente; si se muestran ambas relaciones aparecen como resultados independientes |
| AC-30 | Relaciones superiores a 100 %: el valor original se conserva (p. ej. 1 200/1 000 ⇒ 120 %); no se trunca, no se corrige, no se ajusta numerador ni denominador; se emite advertencia que habla de posible falta de comparabilidad sin afirmar una causa |
| AC-31 | Unidad de carritos: se muestra la unidad declarada o «unidad no declarada»; con unidad no declarada el cálculo se permite con interpretación limitada; **0** apariciones de «carritos únicos» para una métrica cuya unidad declarada es eventos u otra |
| AC-32 | Aplicabilidad por unidad: las columnas documentadas coinciden con los encabezados reales de los dos machotes; **0** exigencias de `trafico` a AETOPS; las reglas y escenarios que requieren `trafico` devuelven «No aplica: sin hoja `trafico`» en AETOPS; **0** columnas, hojas o métricas inventadas |

---

## 13. Riesgos y reversión

| Riesgo | Prob./Impacto | Mitigación | Reversión |
|---|---|---|---|
| Cambio silencioso de cifras | Media / Alto | Línea base, T-13, regla de cambio justificado | `git revert` del PR; el motor no se toca |
| Cambio en láminas actuales (texto de escenarios o de «carritos abandonados») sin autorización | Media / Alto | Fase 1 no las toca sin A-3; T-13 y T-10b comparan con la línea base | Sin A-3 no hay cambio que revertir; con A-3, `git revert` y `escenarios_estrictos=false` |
| Falsos positivos que saturan al usuario | Alta / Medio | Reglas nuevas en `advertir/informar`; umbrales configurables | Flag `validacion_fase1=false` |
| Definiciones que no coinciden con el negocio | Media / Alto | Catálogo versionado y visible; validación real (§10) | Volver a versión anterior del catálogo |
| Reglas entregadas sin datos reales | Alta / Medio | Etiqueta «No validadas con datos reales»; validación sintética y operacional separadas; mapeo y parámetros en configuración | Desactivar regla por flag |
| Relación pedidos/carritos interpretada como conversión individual o como abandono | Media / Alto | Denominación fija, lista de expresiones prohibidas, sin complemento, estados con limitación (§8.2); T-10 | Flag `relacion_pedidos_carritos=false` |
| Reproducibilidad prometida de más | Media / Alto | Tres estados; legado marcado; sin afirmar byte a byte | — |
| Código antiguo no recuperable | Media / Medio | Releases etiquetadas (A-5) | Estado `parcial` |
| Fuga de datos al usar Actions | Baja / Alto | Solo sintéticos por defecto; opt-in expreso; alternativa local | Retirar el artefacto y el workflow |
| Confundir QA estructural con visual | Media / Alto | Nombres y mensajes separados (AC-15) | — |
| Falsos positivos del QA | Media / Medio | Umbrales configurables; `RI_` y decorativos excluidos | Flag `qa_pptx_exportado=false` |
| Rotura de plantillas/formatos | Baja / Alto | No se tocan; pruebas de carga | Revert |
| Peso extra en Pyodide | Baja / Medio | Módulos pequeños, sin dependencias nuevas | Revert; `app.zip` anterior en Releases |
| Folios contradictorios alteran en silencio numeradores o denominadores | Media / Alto | Clasificación C0/C1/C2/E, identidades de control y descomposición de cobertura (§3.3); T-01 | Flag `validacion_fase1=false` |
| Dimensión declarada exclusiva o exhaustiva sin sustento | Media / Alto | Declaración y justificación obligatorias por dimensión; `null` ⇒ regla no aplicada (§3.3); T-02 | Corregir la declaración en `reglas.json` (nueva versión) |
| Prueba condicional reportada como aprobada sin haberse ejecutado | Media / Alto | Estados `omitida (motivo)` y AC-19; informe de CI | — |
| Fixtures con datos reales por error | Baja / Alto | Marca `sintetico: true`, generación determinista, T-20 | Retirar el archivo y regenerar |
| Una fuente de pedidos sustituye o se suma a la otra | Media / Alto | Parámetro `fuente_pedidos`; nombre de la fuente en cada cifra; T-21 | Flag `relacion_pedidos_carritos=false` |
| Relación > 100 % corregida o truncada por error | Baja / Alto | Regla expresa de conservar el valor; T-05 y T-10 | Revert del PR |
| «Carritos únicos» atribuido a una métrica que reporta eventos | Media / Alto | `unidad_carritos` con default `no_declarada`; denominaciones prohibidas; T-05 y T-10 | Flag `relacion_pedidos_carritos=false` |
| Exigir a AETOPS datos de `trafico` que no tiene | Media / Alto | Matriz de aplicabilidad (§3.6); T-22 | Corregir la regla; revert |
| Documentar columnas o fuentes que no existen en los machotes | Media / Alto | Verificación contra encabezados reales (T-22) | Corregir la documentación |

**Flags de Fase 1** (en `reglas.json`; activos tras la autorización; con todos desactivados la salida es idéntica a la línea base, AC-21): `validacion_fase1` (reglas nuevas), `relacion_pedidos_carritos`, `anexo_calidad`, `qa_pptx_exportado` y `escenarios_estrictos` (solo tiene efecto si se autoriza A-3; por defecto `false`, que conserva el comportamiento actual).

Mecanismos transversales: un PR por bloque con su suite verde; un flag por funcionalidad; Pages se despliega desde `main`, así que revertir es `git revert` + re-ejecutar el workflow; la versión de reglas y del motor viaja en cada reporte.

---

## 14. Matriz de trazabilidad (Requerimiento → Regla → Escenario/Indicador → Criterio → Prueba → Evidencia)

Para localizar rápido: *dónde se define una regla* (§3.3), *qué escenario o indicador la usa* (columna 4, §8), *qué criterio la valida* (§12), *qué prueba la comprueba* (§11.2) y *qué evidencia demostraría que fue superada* (última columna). Cuando una relación no aplica se indica «—».

| Req. | Requerimiento | Regla | Escenario / indicador | Archivo responsable | Implementación prevista | Prueba | Criterio | Evidencia esperada |
|---|---|---|---|---|---|---|---|---|
| RQ-01 | Regla `R-REL-PAC-PED` (§3.3) | R-REL-PAC-PED | — | `validator/rules.py`, `config/reglas.json` | Clasificación de `id_pedido` (C2/E activas; C0/C1 reservadas), partición A/B/C, `P_U`, cobertura de paciente, I1/I2, identidades de control | T-01 | AC-05 | Informe JUnit de T-01 + hash de la fixture `rel_pac_ped_*` |
| RQ-02 | Regla `R-CUADRE-DIM` (§3.3) | R-CUADRE-DIM | — | `validator/rules.py`, `config/reglas.json`, `raw/*.py` | Cuatro combinaciones exclusiva/exhaustiva; `dimensiones` declaradas y justificadas; «Sin asignar» virtual; tolerancia | T-02 | AC-06 | Informe JUnit de T-02 + fixtures `cuadre_dim_*` |
| RQ-03 | Regla `R-CONC-COMPRAS` con fuentes diferenciadas | R-CONC-COMPRAS | — | `validator/rules_conc.py`, `raw/glp1.py`, `config/reglas.json` | Brecha entre «Compras GA4» y «Pedidos del sistema de ventas» con ambas fuentes identificadas; umbral configurable (default 20 %); sin sustitución ni suma; sin correspondencia individual | T-03, T-21 | AC-07, AC-29 | Informe JUnit de T-03 y T-21 |
| RQ-04 | Regla `R-DENOM` | R-DENOM | — | `validator/rules.py` | Ratio sin denominador válido ⇒ «No verificable» con `faltante` | T-04 | AC-08, AC-04 | Informe JUnit de T-04 |
| RQ-05 | Regla `R-COBERTURA-ATC` (comparabilidad de carritos agregados y pedidos) | R-COBERTURA-ATC | IND-01 | `validator/rules_conc.py`, `raw/glp1.py`, `config/reglas.json` | Estados calculable / con limitación / no calculable según periodo, fuente, universo, filtros, unidad de carritos y disponibilidad; sin identificadores | T-05 | AC-09, AC-31, AC-30, AC-04 | Informe JUnit de T-05 + fixture `comparabilidad.json` |
| RQ-06 | Catálogo de definiciones versionado | — | — | `config/definiciones.json`, `provenance.py` | Definiciones de §3.1 y glosario de §3.4 versionados y leídos por reglas y anexo | T-07 | AC-10 | Informe JUnit de T-07 |
| RQ-07 | Hallazgo con nomenclatura explícita | — | — | `models.py`, `validator/catalogo.py` | 7 campos nuevos opcionales; catálogo por `id` | T-06 | AC-03 | Informe JUnit de T-06 |
| RQ-08 | Migración compatible de `severity` | — | — | `models.py`, `web/service.py`, `frontend/index.html` | `severity` alias derivado de `efecto_generacion`; JSON conserva `severity` | T-06, T-13 | AC-02 | Informe JUnit de T-06 y T-13 |
| RQ-09 | «No verificable» con `faltante` | R-DENOM, R-COBERTURA-ATC | — | `validator/*`, `models.py` | Estado + `faltante` obligatorio | T-06 | AC-04 | Informe JUnit de T-06 |
| RQ-10 | Manifiesto de procedencia | — | — | `provenance.py`, `version.py`, `tools/build_site.py`, `build.py` | Versiones, SHA-256 de plantillas y fuentes, fecha, configuración, `hash_resultado` | T-07, T-16 | AC-10 | Informe JUnit de T-07 y T-16; manifiesto de ejemplo |
| RQ-11 | Reproducibilidad y sus estados | — | — | `provenance.py`, `web/service.py`, `frontend/index.html` | Resultado canónico; estados exacta / parcial / no_reproducible; sin regeneración silenciosa | T-08 | AC-11, AC-12 | Informe JUnit de T-08 |
| RQ-12 | Releases etiquetadas | — | — | `.github/workflows/release.yml`, `tools/build_site.py` | Publica `app-vX.Y.Z` con su `app.zip` (si se autoriza A-5) | T-16, V-02 | AC-28, AC-10 | Informe de T-16; ejecución del workflow y asset publicado (V-02) |
| RQ-13 | QA estructural del PPTX exportado | — | — | `qa/pptx_export.py`, `qa/checks.py`, `build.py` | Re-lectura tras guardar: cifras, fórmulas, unidades, denominadores, textos, fuentes, geometría, tokens | T-11 | AC-14 | Informe JUnit de T-11 + decks de defectos inyectados |
| RQ-14 | QA visual con render real | — | — | `qa/visual.py`, `tools/visual_qa.py`, `pdf.yml`/`visual-qa.yml` | LibreOffice → PDF → PNG; solapes, recortes, gráficas, contraste, consistencia | T-12 | AC-16 | PNG por diapositiva e informe de hallazgos (artefacto del workflow o carpeta local) |
| RQ-15 | Límites del QA declarados en la interfaz | — | — | `frontend/index.html`, `web/service.py` | Etiquetas «Revisión estructural» / «requiere render» | T-11 | AC-15 | Informe JUnit de T-11 |
| RQ-16 | Escenario E1 (negados) con valor heredado | — | E1 | `narrative/rules.py`, `config/reglas.json` | Fórmula actual `M_neg × 25 %` sin cambio; etiqueta «Supuesto heredado, no validado»; conservador/optimista `null` | T-09 | AC-13 | Informe JUnit de T-09 + comparación con la línea base |
| RQ-17 | Escenario E2 heredado, diferenciado del indicador agregado | — | E2 | `narrative/rules.py`, `glp1_exec.py`, `config/reglas.json` | Fórmula actual `A × 10 % × T` sin cambio; denominación histórica conservada; aclaración sobre `carritos_abandonados` en panel y anexo; sin cambios en láminas sin A-3 | T-10b | AC-13 | Informe JUnit de T-10b + comparación con la línea base |
| RQ-18 | Etiquetas de supuesto heredado, de «ilustrativo» y de métrica heredada | — | E1, E2 | `narrative/executive.py`, `glp1_exec.py`, `deck/extras.py`, `frontend/index.html` | Rótulos obligatorios con fórmula visible en panel y anexo | T-09, T-10b, T-11 | AC-13 | Informe JUnit de T-09, T-10b y T-11 |
| RQ-19 | Anexo de calidad de datos | — | IND-01, E1, E2 | `deck/extras.py`, `build.py` | Diapositiva final con definiciones, versiones, estados, no verificables, fuentes y limitaciones | T-11 | AC-14 | Informe JUnit de T-11 + deck sintético con anexo |
| RQ-20 | Procedimiento y herramienta de anonimización | — | — | `tools/anonimizar_extracto.py`, `docs/VALIDACION_DATOS_REALES.md` | HMAC local con sal propia; elimina texto libre | T-15 | AC-17 | Informe JUnit de T-15 |
| RQ-21 | Validación con datos reales (modo informe) | Todas las R-* | — | `docs/VALIDACION_DATOS_REALES.md`, `web/service.py` | Informe de validación sin generar deck; opcional para iniciar Fase 1 | V-01 | AC-18 | Informe de validación firmado por el usuario (solo si existen extractos) |
| RQ-22 | No-regresión | — | — | `tests/regression/base/`, `CAMBIOS_JUSTIFICADOS.md` | Línea base y comparación | T-13 | AC-01 | Informe JUnit de T-13 + diff vacío frente a la línea base |
| RQ-23 | La IA no altera cifras ni sustituye cálculos | — | E1, E2, IND-01 | `narrative/*` (módulo de IA sin cambios) | Caso nuevo sobre escenarios y relación pedidos/carritos | T-14 | AC-27 | Informe JUnit de T-14 |
| RQ-24 | Flags de reversión | — | — | `config/reglas.json`, `web/service.py` | `validacion_fase1`, `relacion_pedidos_carritos`, `anexo_calidad`, `qa_pptx_exportado`, `escenarios_estrictos` (§13) | T-13 | AC-21 | Informe JUnit de T-13 (corrida con flags desactivados) |
| RQ-25 | Rendimiento | — | — | `build.py`, `provenance.py` | Hash incremental; sin dependencias nuevas | T-19 | AC-20 | Medianas de tiempo registradas en el job de CI |
| RQ-26 | Validación sintética vs operacional diferenciadas y rotuladas | Todas las R-* | — | `config/validacion_registro.json`, `models.py` (campo derivado), `deck/extras.py`, `frontend/index.html` | Rótulo «No validada con datos reales» hasta `confirmada` | T-18 | AC-24 | Informe JUnit de T-18 |
| RQ-27 | Incorporar extractos reales después sin rehacer la arquitectura | Todas las R-* | — | `config/mapeo_columnas.json`, `config/reglas.json`, `config/validacion_registro.json` | Mapeo, parámetros y confirmación en configuración versionada | T-17 | AC-25, AC-23 | Informe JUnit de T-17 + diff sin archivos de código |
| RQ-28 | Indicador IND-01 «Relación pedidos/carritos» (metodología agregada, §8.2) | R-COBERTURA-ATC | IND-01 | `validator/rel_pedidos_carritos.py`, `deck/extras.py`, `web/service.py` | `(pedidos / carritos) × 100` en `Decimal` por fuente de pedidos; tres elementos visibles; denominaciones prohibidas; sin complemento; sin identificadores; >100 % conservado con advertencia | T-10 | AC-22, AC-23, AC-30, AC-29 | Informe JUnit de T-10 + búsqueda de denominaciones prohibidas en las salidas |
| RQ-29 | Escenarios de prueba reproducibles y sin datos reales | — | — | `tools/make_fixtures_fase1.py`, `tests/fixtures/fase1/` | Fixtures sintéticas deterministas con semilla fija, manifiesto y hash | T-20 | AC-26 | Informe JUnit de T-20 + manifiesto de fixtures |
| RQ-30 | Suites existentes sin regresión | — | — | `tests/unit/*`, `tests/golden/*` | Se mantienen sin edición | S-01, S-02 | AC-19 | Informe de pytest en CI (S-01) y local (S-02) |
| RQ-31 | Diferenciación de fuentes de pedidos: sistema de ventas vs GA4 | R-CONC-COMPRAS, R-COBERTURA-ATC | IND-01 | `validator/rules_conc.py`, `validator/rel_pedidos_carritos.py`, `config/reglas.json` | Parámetro `fuente_pedidos`; resultados independientes e identificados; prohibido sustituir, sumar o equiparar; sin correspondencia individual | T-21, T-03, T-10 | AC-29, AC-07 | Informe JUnit de T-21, T-03 y T-10 |
| RQ-32 | Aplicabilidad por unidad y fidelidad a los machotes | Todas las R-* | E1, E2, IND-01 | `docs/CONTRATO_DATOS.md`, `config/reglas.json`, `config/mapeo_columnas.json` | Reglas que requieren `trafico` devuelven «No aplica» en AETOPS; columnas documentadas = encabezados reales; no se inventan campos | T-22 | AC-32 | Informe JUnit de T-22 (compara encabezados de `data/ejemplos/*`) |

---

## 15. Decisiones que requieren tu autorización

**La columna «Recomendación» es una propuesta de la documentación; no es una autorización.** Ninguna decisión está autorizada y **cerrar esta especificación no autoriza nada**. Sin tu respuesta, **no se implementa** el punto correspondiente.

### 15.1 Estado de las decisiones A-1 a A-8

| ID | Decisión | Recomendación | Estado de autorización |
|---|---|---|---|
| **A-1** | Autorizar el inicio de la implementación de Fase 1 (Sí / No / solo algunos bloques) | Sí, después de corregir y revisar la documentación (propuesta: cinco PR por bloque — modelo y línea base → reglas → procedencia → escenarios e indicador → QA y anexo) | **Pendiente. Sin autorización** |
| **A-2** | Entregar extractos anonimizados reales (§10) | Incorporarlos después de la implementación inicial | **Pendiente. Sin autorización** (no bloquea el inicio) |
| **A-3** | Modificar láminas actuales (texto o etiquetas del escenario de «carritos abandonados», etiqueta heredada en láminas) | No modificarlas por ahora | **Pendiente. Sin autorización**; hasta entonces no cambia nada |
| **A-4** | Escenarios 25 % y 10 % | Mantenerlos como supuestos heredados no validados | **Pendiente. Sin autorización** |
| **A-5** | Publicar releases etiquetadas (`app-vX.Y.Z` + `app.zip`) | Sí | **Pendiente. Sin autorización** |
| **A-6** | QA visual en GitHub Actions | Utilizar datos sintéticos; los datos reales se validan localmente | **Pendiente. Sin autorización** |
| **A-7** | Retirar `severity` | Mantener compatibilidad (no se retira en Fase 1) | **Pendiente. Sin autorización** |
| **A-8** | Decisiones restantes: D3 (responsable sugerido), D4 (tiempo de interacción), D5 (anexo único vs. rediseño), D8 (mantener plantillas fijas) | Aceptar las recomendaciones documentadas en §2 | **Pendiente. Sin autorización** |

### 15.2 Qué condiciona cada decisión

| ID | Qué falta decidir | Qué parte de la implementación depende | Comportamiento que se conserva mientras no haya autorización | Qué no está permitido asumir |
|---|---|---|---|---|
| A-1 | Si se inicia Fase 1 y con qué bloques | Todo el código, P-00 (línea base), las 22 pruebas obligatorias nuevas | Repositorio sin cambios; solo documentación | Que la especificación final autoriza implementar |
| A-2 | Si y cuándo se entregan extractos reales | V-01, validación operacional, estado `confirmada` de las reglas | Reglas activas con parámetros por defecto, rotuladas «No validadas con datos reales»; Fase 1 puede iniciar sin extractos | Que los machotes sintéticos validan las reglas; inventar datos |
| A-3 | Si se cambian láminas actuales | Texto/etiquetas de E2 y de «carritos abandonados»; etiqueta heredada en láminas; flag `escenarios_estrictos` | Láminas, textos, fórmulas y cifras idénticos a la línea base; aclaraciones solo en panel y anexo | Que la aclaración de §8.3 puede ir ya en las láminas; cambiar fórmulas |
| A-4 | Confirmar la estrategia de 25 % y 10 % | Rótulos y configuración de escenarios (§8.0) | Se muestran como «Supuesto heredado, no validado»; conservador y optimista «No configurado» | Presentarlos como validados o aprobados; inventar otros valores |
| A-5 | Si se publican releases etiquetadas | `release.yml`, V-02, parte de RQ-12, reproducción con código anterior | Sin releases; los reportes anteriores quedan `parcial` | Que existen versiones recuperables del código |
| A-6 | Si el QA visual corre en Actions | `visual-qa.yml`, T-12 en Actions | T-12 `omitida` en CI; QA visual local con `tools/visual_qa.py` | Subir PPTX con datos reales a GitHub |
| A-7 | Si algún día se retira `severity` | Nada en Fase 1 | `severity` se conserva con la compatibilidad de §4.3 | Retirarla o renombrarla |
| A-8 | D3, D4, D5, D8 | Responsable sugerido, tiempo de interacción, anexo de calidad, plantillas fijas | Comportamiento actual sin cambios | Ampliar «tiempo de interacción», reestructurar el deck o cambiar plantillas |

### 15.3 Mapa de estado de la especificación

| Categoría | Contenido | Dónde |
|---|---|---|
| **Requisitos definidos** | RQ-01 a RQ-32 | §14 |
| **Reglas documentadas** | `R-REL-PAC-PED`, `R-CUADRE-DIM`, `R-CONC-COMPRAS`, `R-DENOM`, `R-COBERTURA-ATC`; indicador IND-01 | §3.3, §8.2 |
| **Supuestos heredados** (no validados) | 25 % (E1), 10 % (E2), umbral 20 % del aviso de compras, `m = 1` por defecto, tolerancias iniciales, derivación `add_to_cart − compras` | §3.3, §8.0, §8.3 |
| **Decisiones pendientes** | A-1 a A-8; ambigüedades abiertas AMB-* | §15, §16 |
| **Dependencias de implementación** | Qué parte depende de cada decisión | §15.2 |
| **Pruebas no ejecutadas** | Las 27 entradas del inventario figuran «Pendiente» (la línea base de S-01 es evidencia previa, no de Fase 1) | §11.2 |

Para autorizar basta responder de forma expresa, por ejemplo: «Autorizo A-1 (sin extractos por ahora); A-2 después; A-3 no; A-4 confirmar; A-5 sí; A-6 sintéticos; A-7 mantener; A-8 aceptar». Las ambigüedades de §16 se confirman o corrigen al responder A-1.

---

## 16. Ambigüedades (resolución propuesta, **no aprobada** salvo las marcadas como cerradas documentalmente)

Puntos que la información disponible no permite cerrar. Cada resolución es una **propuesta documental**, no una decisión tomada.

| ID | Ambigüedad | Resolución propuesta | Estado | ¿Bloquea la autorización de Fase 1? |
|---|---|---|---|---|
| AMB-1 | ¿Qué fuente de pedidos es la «de referencia» del negocio para IND-01: sistema de ventas o compras GA4? | Calcular y mostrar **ambas** como resultados independientes e identificados; si el negocio designa una de referencia, se rotula como tal sin eliminar la otra. Ninguna se infiere ni se sustituye | Abierta | No |
| AMB-2 | Unidad real de «carritos agregados» (eventos, sesiones u otra) | Regla ya definida: default «unidad no declarada» con cálculo limitado; el usuario puede declararla en configuración | Regla cerrada documentalmente; falta solo la declaración del usuario | No |
| AMB-3 | Las láminas actuales usan «carritos abandonados» y su cifra monetaria | No cambiar nada sin A-3; aclaración solo en salidas nuevas (§8.3) | Abierta (A-3) | No |
| AMB-4 | ¿Se incorporará algún día una columna de estatus de pedido? | Hoy no existe y el contrato la excluye; las clases C0/C1 permanecen reservadas e inactivas | Cerrada para Fase 1; abierta solo si el negocio cambiara el contrato | No |
| AMB-5 | Criterio de «coincidencia de periodos» | Igualdad exacta de fecha de inicio, fecha de fin y granularidad (mes calendario en GLP-1) | Abierta | No |
| AMB-6 | Relación pedidos/carritos > 100 % | Valor conservado con advertencia (§8.2) | **Cerrada documentalmente** | No |
| AMB-7 | Valores por defecto de `cobertura_minima_paciente` y tolerancias | Sin umbral universal: no configurado ⇒ solo se informa; tolerancias de §3.3 como parámetros, no como verdad | Abierta | No |
| AMB-8 | El motor actual no tiene un indicador llamado «Relación pedidos/carritos»; la metodología es operación vigente del negocio | Incorporarlo como salida **nueva** en anexo y panel, sin tocar láminas; verificar que la fórmula coincida con la que se usa hoy | Abierta | No |
| AMB-9 | ¿La relación debe restringirse a los pedidos del canal web? (`canal` en GLP-1 solo tiene `ECOMMERCE` en el machote) | Parámetro `filtro_canal_relacion` (default sin filtro); si el archivo trae más de un canal, la relación se rotula «puede no ser directamente comparable» | Abierta | No |
| AMB-10 | Significado exacto de `carritos_abandonados` cuando la herramienta de analítica lo informa | Conservar la definición histórica; documentar la limitación; no inventar interpretación | Abierta | No |
| AMB-11 | `negados` no trae fecha: ¿corresponde siempre al periodo del reporte? | Mantener la convención operativa vigente; declararlo como limitación de E1 | Abierta | No |


---

## Anexo A. Resumen de cambios de v4 a FINAL

| Sección | Cambio realizado | Motivo |
|---|---|---|
| Encabezado | Versión FINAL; archivos de referencia; resumen de cambios; historial | Cierre documental |
| §0 | Principios 10 (fuentes de pedidos), 11 (fidelidad a los machotes) y 12 (cerrar ≠ autorizar) | Ajuste 1; revisión de machotes; decisiones pendientes |
| §1 | Tres hallazgos nuevos del código y los machotes | Sustento factual |
| §2 | D2 reformulada (unidad por defecto «no declarada») | Ajuste 3 |
| §3.0 (nueva) | Estructura real de los machotes, diferencias entre unidades, clasificación disponibles/derivados/otras integraciones, observaciones OBS-01 a OBS-12, diccionario de términos | Revisión obligatoria de los machotes |
| §3.1 | Definiciones con columna real; «Pedido del sistema de ventas» vs «Compra GA4»; «Pedido» sin calificar prohibido | Ajuste 1 |
| §3.3 `R-REL-PAC-PED` | Nombres reales (`id_pedido`, `id_paciente`, `fecha_pedido`); clases de estatus reservadas e inactivas; ejemplo de 6 pedidos y variante condicional | Los machotes no tienen estatus |
| §3.3 `R-CUADRE-DIM` | Tabla de dimensiones candidatas observadas en los machotes | Fundamento concreto |
| §3.3 `R-CONC-COMPRAS` | Fuentes identificadas; prohibiciones; «no es un error»; solo GLP-1 | Ajuste 1 |
| §3.3 `R-COBERTURA-ATC` | Unidad de carritos; estados; solo GLP-1 | Ajustes 3 y 4 |
| §3.4–3.6 (nuevas) | Glosario; catálogo de fórmulas F-01 a F-12; aplicabilidad por unidad | Auditoría integral (5.1, 5.2, 5.7) |
| §6 | Indicador IND-01 con fuente identificada | Ajuste 1 |
| §8 | Reescrita: fichas E1 y E2; IND-01 con dos fuentes, unidad, comparabilidad y > 100 %; tabla de tres elementos | Ajustes 1 a 4 |
| §9 | `reglas.json` con `fuente_pedidos`, `unidad_carritos`, `filtro_canal_relacion`; descripciones actualizadas | Consistencia |
| §10.1 | Reescrita según las columnas reales de los machotes | v4 pedía columnas inexistentes |
| §10.4, §10.7 | Filas actualizadas | Consistencia |
| §10.8 (nueva) | Resumen de privacidad, datos e IA | Auditoría 5.8 |
| §11 | Inventario ampliado (T-21, T-22), prerrequisitos, oleadas, condiciones de activación, evidencia por prueba, P-00 | Ajuste 5 |
| §12 | AC reescritos (05, 06, 07, 09, 13, 19, 20, 22, 23, 27) y nuevos (29 a 32) | Consistencia con reglas y pruebas |
| §13 | Seis riesgos nuevos | Cobertura de los nuevos controles |
| §14 | Matriz con columnas Regla, Escenario/indicador y Evidencia; RQ-31 y RQ-32 | Ruta verificable completa |
| §15 | Tabla A-1 a A-8 conservada; 15.2 dependencias; 15.3 mapa de estado | Decisiones pendientes |
| §16 | Ambigüedades AMB-1 a AMB-11 con estado | Resolver sin presentar como aprobado |

## Anexo B. Inconsistencias resueltas (v4 → FINAL)

| # | Inconsistencia encontrada en v4 | Resolución | Dónde |
|---|---|---|---|
| 1 | Se usaban `folio`, `pac_id` y `fecha de pedido`, nombres que no existen en los machotes | Se usan `id_pedido`, `id_paciente`, `fecha_pedido`; «folio» queda como alias histórico | §3.0, §3.3, §3.4 |
| 2 | `R-REL-PAC-PED` dependía de `estatus_excluidos`, pero los machotes y el contrato no tienen estatus (`estado` es entidad federativa) | C0/C1 reservadas e inactivas; cancelaciones declaradas no identificables; B conservada como defensiva | §3.3, §9, AMB-4 |
| 3 | El ejemplo de `R-REL-PAC-PED` y T-01 contenían un pedido «cancelado» y uno «mixto» como caso base | Caso base de 6 pedidos sin estatus; los casos de estatus pasan a variante condicional | §3.3, T-01 |
| 4 | §10.1 pedía a AETOPS un archivo de tráfico y columnas inexistentes («estatus», «indicador de negado» en pedidos, «cantidad», «monto de línea», «fuente/medio», ID de carrito) | Reescrito con las columnas reales; AETOPS sin `trafico` | §10.1 |
| 5 | No se indicaba qué reglas aplican a AETOPS | Matriz de aplicabilidad; `R-CONC-COMPRAS`, `R-COBERTURA-ATC`, IND-01 y E2 «No aplican» a AETOPS | §3.6, AC-32, T-22 |
| 6 | «Pedido» se usaba sin distinguir sistema de ventas y GA4 | Dos términos calificados; «pedido» sin calificar prohibido; AC-29 y T-21 | §3.1, §3.4, §8.2 |
| 7 | `R-CONC-COMPRAS` no prohibía explícitamente sustituir/sumar y no aclaraba que la diferencia no es un error | Prohibiciones y texto neutro; aviso heredado conservado | §3.3 |
| 8 | E2, la métrica `carritos_abandonados` e IND-01 estaban mezclados | Tabla de tres elementos y aclaración obligatoria | §8.3 |
| 9 | La unidad de los carritos estaba como ambigüedad abierta | Regla en `R-COBERTURA-ATC`: default «unidad no declarada», cálculo limitado | §3.3, §8.2, AC-31 |
| 10 | > 100 % se trataba como aviso informativo (AMB-6) y T-05 decía «efecto siempre `informar`» | Valor conservado, advertencia sin causa afirmada, `advertir`; AC-30 | §8.2, T-05, T-10 |
| 11 | Dependencia de T-12 de «un deck producido por T-11» no era un prerrequisito formal; T-13 y T-19 «requerían línea base» y T-19 comparaba con una versión que ya no existiría | P-00 como prerrequisito previo a todo cambio; T-12 requiere T-11 y T-20; T-19 compara flags desactivados contra activados en el mismo job | §11.2–11.3 |
| 12 | El grafo de prerrequisitos no estaba verificado | Verificado sin ciclos al generar el documento; orden por oleadas | §11.3 |
| 13 | AC-19 listaba 20 obligatorias | 22 obligatorias nuevas (T-21, T-22) + S-01; condicionales con activación | AC-19, §11.2 |
| 14 | La matriz no mostraba regla, escenario ni evidencia | Columnas añadidas | §14 |
| 15 | «Cobertura» se usaba para dos conceptos y `estado` chocaba con `estado_verificacion` | «Cobertura de paciente» vs `R-COBERTURA-ATC` (comparabilidad); glosario | §3.4 |
| 16 | La afirmación «los datos no salen del navegador» omitía la excepción opcional de la IA | Excepción documentada | §10.8 |
| 17 | Tabla `R-CUADRE-DIM` sin dimensiones reales | Dimensiones candidatas y observaciones OBS-04 a OBS-08 | §3.3 |
| 18 | E1 no declaraba que `negados` no trae fecha | Limitación declarada | §8.1, AMB-11 |

## Anexo C. Auditoría de trazabilidad y de consistencia

**Verificación programática realizada al generar este documento** (las tablas de §11.2, §12 y §14 salen de una única fuente de datos):

| Comprobación | Resultado |
|---|---|
| Requisitos con prueba o verificación asociada | 32 de 32 |
| Requisitos con criterio de aceptación, regla/escenario (o «—») y evidencia | 32 de 32 |
| Pruebas que referencian solo requisitos y AC existentes, y requisitos que las listan de vuelta | Sí (27 entradas) |
| Pruebas con entrada, resultado esperado, criterio, dependencias, activación, prerrequisitos y evidencia | 27 de 27 |
| Criterios de aceptación cubiertos por al menos una prueba | 32 de 32 |
| Dependencias circulares | Ninguna (5 oleadas) |
| Pruebas obligatorias nuevas | 22 |
| Pruebas aprobadas | **0** (ninguna está ejecutada); línea base S-01 citada solo como evidencia previa |

**Confirmaciones documentales**

| Punto | Estado |
|---|---|
| Fórmulas con numerador, denominador, fuentes, condiciones, datos faltantes y división inválida | Catálogo F-01 a F-12 (§3.5) |
| Cada regla tiene prueba | `R-REL-PAC-PED` T-01; `R-CUADRE-DIM` T-02; `R-CONC-COMPRAS` T-03 y T-21; `R-DENOM` T-04; `R-COBERTURA-ATC` T-05 (IND-01: T-10) |
| La metodología agregada no exige ID de carrito | §8.2, AC-23, T-10; el mapeo de columnas no define identificadores |
| Los machotes se reflejan tal como son | §3.0 y T-22; ninguna columna, hoja o métrica inventada |
| Cambios de lógica, fórmulas, cifras o plantillas no autorizados | Ninguno: esta tarea solo creó documentación en el directorio de trabajo temporal |
| Restricciones heredadas | 25 % y 10 % como supuestos no validados; sin escenarios inventados; `severity` compatible; separación sintético/operacional; privacidad; la IA no modifica cifras |

**Los 20 criterios para considerar finalizada la especificación**

| # | Criterio | Dónde se cumple |
|---|---|---|
| 1 | Sin contradicciones internas conocidas | Anexo B; verificación programática |
| 2 | Sin ambigüedades críticas sobre fuentes de datos | §3.0, §3.1, §8.2; AMB-1 y AMB-9 no bloquean |
| 3 | Pedidos del sistema de ventas y compras GA4 diferenciados | §3.1, §3.3 `R-CONC-COMPRAS`, §8.2, AC-29 |
| 4 | Relación pedidos/carritos como indicador agregado | §8.2, F-01, F-02 |
| 5 | Sin trazabilidad individual carrito–compra | §8.2, §8.5, AC-23 |
| 6 | La diferencia no se interpreta como abandono | §8.2, §8.4 |
| 7 | E2 conserva su naturaleza histórica | §8.3 |
| 8 | Unidad de carritos contemplada | §3.3, §8.2, AC-31 |
| 9 | > 100 % con tratamiento definido | §8.2, AC-30 |
| 10 | Machotes documentados según su estructura real | §3.0, T-22 |
| 11 | Sin campos ni fuentes inventados | §3.0, §10.1, AC-32 |
| 12 | Reglas, escenarios y AC consistentes | §3.3, §8, §12, §14 |
| 13 | Inventario de pruebas completo | §11.2 |
| 14 | Dependencias de pruebas ejecutables | §11.3 |
| 15 | Trazabilidad verificable | §14, este anexo |
| 16 | A-1 a A-8 conservan su estado | §15.1 (todas pendientes) |
| 17 | Sin pruebas no ejecutadas presentadas como aprobadas | §11.2 (todas «Pendiente») |
| 18 | Supuestos heredados sin validar artificialmente | §8.0, §15.3 |
| 19 | Reglas de privacidad y restricciones de IA conservadas | §10.8 |
| 20 | Sin modificar código, cifras, fórmulas ni plantillas | Anexo C; `git status` limpio |
