# Objetivo del reporte y narrativa ejecutiva

> **Estado:** propósito y reglas construidos a partir de los reportes originales (AETOPS Agosto 2026, Q1 2026, Nov 2025;
> GLP-1 Agosto 2026). Decisiones del dueño del reporte ya cerradas: ver §8. Lo que sigue **[Validar]** está abierto.

## 1. Para qué existe el reporte (propuesta)

**Propósito.** Dar a la dirección de E-Commerce una lectura mensual y trimestral de la salud de la venta digital de AETOPS
(y, con otro enfoque, de GLP-1) que permita decidir **dónde actuar**, no solo conocer cifras.

**El reporte debe demostrar, en este orden:**

| # | Pregunta de la dirección | Qué demuestra el reporte | Dónde |
|---|---|---|---|
| 1 | ¿Cuánto vendimos y cómo vamos? | Nivel de venta y variación contra el año anterior (YoY) y el mes/trimestre anterior (MoM/QoQ) | Panorama |
| 2 | ¿El crecimiento es **real**? | Si viene de **volumen** (pacientes, piezas por paciente) o de **precio/mezcla**; si la amplitud de portafolio acompaña | Panorama |
| 3 | ¿**Quién** lo explica? | Canales, líneas y categorías que más aportan y las que restan; quién gana o pierde participación; avances sobre base pequeña | Canales · Líneas · Categorías |
| 4 | ¿**Qué productos** mueven el resultado? | Líderes, mayores alzas y bajas, y de qué línea vienen | Productos |
| 5 | ¿Qué **no** vendimos? | Venta negada como porcentaje de la venta, concentración por línea y producto | Negados |
| 6 | ¿Qué hacemos con esto? | Qué sostener, qué vigilar, dónde hay venta por recuperar | Conclusiones |

**Audiencia [Validar]:** dirección comercial / E-Commerce. Lectura ejecutiva: 5 minutos, sin tecnicismos.

**El reporte también recomienda.** Cierra con acciones priorizadas (qué hacer, por qué, cuánto está en juego, qué métrica seguir).

**Lo que el reporte NO hace:** no atribuye causas que los datos no demuestran (campañas, desabasto, estacionalidad,
precios). Cuando solo hay una coincidencia, la acción es *revisar/validar*, no *corregir*. Las causas las aporta quien conoce el
negocio (ver «Contexto del periodo», §10).

## 2. Qué cambia respecto a la narrativa anterior

| Antes (determinista v1) | Ahora |
|---|---|
| Lista cifras por grupo ("CANAL A: venta +125%, piezas +125%…") | Dice **qué significan**: quién aporta cuánto del avance, quién gana participación, si es volumen o ticket |
| Mismo patrón para todo | Prioriza lo relevante y calla lo estable; el texto cabe en su cuadro |
| Sin distinguir hecho de lectura | Cada enunciado es **hecho**, **interpretación** (con su regla) o **información insuficiente** |
| Podía repetir cifras dudosas | Una cifra que no cuadra (p. ej. pedidos por canal) **no se usa** y se avisa |
| Sin control | **Verificador:** toda cifra del texto debe estar registrada con su evidencia; palabras causales prohibidas |

## 3. Tipos de enunciado

| Tipo | Qué es | Ejemplo | Regla |
|---|---|---|---|
| **Hecho** | Aritmética sobre datos validados | "La venta llega a $11.56 M y crece +67% vs 2025" | Cada cifra trazable a su celda |
| **Interpretación** | Lectura que se sigue de los hechos por una regla **explícita** | "El crecimiento se explica principalmente por volumen" | Se guarda la regla (`basis`); se redacta sin causas externas |
| **Hipótesis** | Causa posible no demostrada | "Podría deberse a una campaña" | **No se genera** en modo determinista. Con IA: solo marcada y editable |
| **Información insuficiente** | Lo que no se puede afirmar | "No se compara pedidos por canal: no cuadran con el total" | Obligatoria cuando un dato clave falla validación |

## 4. Catálogo de insights (todos deterministas)

| Insight | Cálculo | Se muestra si |
|---|---|---|
| Descomposición del cambio en venta | Venta = Pacientes × (Piezas/Paciente) × (Venta/Pieza); aporte de cada factor = ln(factor₁/factor₀) ÷ ln(venta₁/venta₀) | El cambio de venta ≥ 0.5 % |
| Volumen vs precio | Volumen = pacientes × piezas/paciente; precio = venta/pieza | Siempre en panorama |
| Amplitud de portafolio | Productos vendidos vs periodo anterior, comparado con la venta | Siempre en panorama |
| Aporte al crecimiento | Δ$ del grupo ÷ Δ$ total | Δ total > 0 y Δ grupo > 0 (si no, solo Δ$) |
| Cambio de participación | share₁ − share₀ en puntos porcentuales | ≥ 2 pp, o crece pero menos que el total |
| Valor sobre volumen | Venta ↑ con pacientes ↓ | Se cumple |
| Caída por mezcla/ticket | Venta ↓ con piezas ≥ 0 | Se cumple |
| Base pequeña | Δ > 100 % con share previo < 5 % | Se cumple |
| Concentración de productos | Σ de los primeros N ÷ venta total | Siempre |
| Lectura mixta de una línea | Aparece en el Top de alzas **y** de bajas | Se cumple |
| Venta negada | Negado ÷ venta del periodo; concentración por línea y producto | Siempre |

Umbrales en `backend/app/narrative/rules.py` (configurables): relevancia 5 %, participación 2 pp, base pequeña 5 %, etc. **[Validar]**.

## 5. Estilo (tomado de los originales)

Directo y ejecutivo; verbos en presente ("llega", "crece", "sostiene", "pierde participación"); cifras en **negrita**;
$M/$K; porcentajes con signo (+67 %); un párrafo por idea; sin adjetivos de causa. Longitud limitada por el cuadro de la diapositiva.

## 6. Flujo de edición y trazabilidad

1. El sistema genera `narrative.json`: por diapositiva, cada párrafo con tipo, regla, cifras y evidencia (celdas del Excel).
2. Una persona revisa y edita; lo editado se marca `edited_by_user` y **también pasa por el verificador** (una cifra nueva sin evidencia se señala).
3. El PPTX y el PDF salen del mismo texto final.

## 7. Papel de la IA (Cohere, opcional)

Solo para **redactar mejor** los insights ya verificados (variar estilo, hilar párrafos). No puede introducir cifras ni causas;
sus hipótesis, si se piden, salen marcadas. Todo pasa por el mismo verificador. Apagada por defecto.

## 8. Decisiones con el dueño del reporte

| # | Tema | Estado |
|---|---|---|
| 1 | **Negado** | ✅ *Producto sin stock que se negó a la venta.* Con esa definición se puede decir "venta que no se concretó por no tener el producto" y hablar de abasto. |
| 2 | **Recomendaciones y acciones** | ✅ Sí: el reporte las incluye (resumen ejecutivo + diapositiva final). |
| 3 | **Alcance de la narrativa** | ✅ "Que explique dónde estamos, los descubrimientos del periodo y las recomendaciones", no solo tablas. |
| 4 | **Umbrales de relevancia** | ➡️ Se adopta la recomendación de la sección 9.1 (materialidad + banda de estabilidad). Ajustable. |
| 4b | **Diseño de la revisión** (maqueta) | ✅ Resumen ejecutivo **al inicio**; recomendaciones **sin responsable ni fecha**; tendencias **solo en la pantalla de revisión** (no es diapositiva); orden validar → narrativa → generar, sin cambios. |
| 5 | **Pedidos por canal** (suman 2.1× el total) | ⏳ Abierto. Mientras tanto no se usan en la narrativa. |
| 6 | **%Δ y Ticket de GLP-1**; si el mes del libro viene parcial | ⏳ Abierto. |
| 7 | **Criterio de categorías del trimestral** (las 3 que más suman y las 3 que más restan en pesos) | ⏳ Abierto: se mantiene hasta que se confirme. |

## 9. Descubrimientos y recomendaciones (implementado)

**Descubrimiento** = hallazgo con puntaje de materialidad (qué parte de la venta total mueve). El resumen muestra los 4 mayores.
**Recomendación** = regla → acción, con evidencia, impacto en *escenario* y métrica de seguimiento.

| Regla (dispara si…) | Acción sugerida | Accionabilidad |
|---|---|---|
| Negados ≥ 1 % de la venta | Priorizar el abasto de los productos más negados · *escenario ilustrativo: recuperar 25 % del monto negado* | 1.5 |
| Un producto cae **y** aparece en negados | Revisar la disponibilidad de ese producto (coincidencia, no causa) | 1.5 |
| Una línea/canal ≥ 50 % de la venta | Proteger esa línea (abasto y continuidad de sus productos principales) | 1.0 |
| Crece, pero cede ≥ 5 pp de participación | Investigar qué lo limita (revisar pacientes y valor por paciente) | 0.7 |
| Venta ↑ con pacientes ↓ | Validar la sostenibilidad (captación de pacientes) | 0.7 |
| Venta ↓ con piezas ≥ 0 | Revisar mezcla y precio | 0.7 |
| Una métrica del panorama cae ≥ 5 % | Vigilar esa métrica | 0.5 |

**Prioridad** = impacto (% de la venta) × accionabilidad: ALTA ≥ 7 %, MEDIA ≥ 3 %, BAJA debajo. Lo que se puede corregir directo (abasto)
pesa más que lo que solo pide investigar. Máximo 5 recomendaciones por reporte.

**Escenarios, no pronósticos.** El impacto se expresa como aritmética con su supuesto a la vista ("si se recuperara 25 %…").

### 9.1 Umbrales recomendados
- **Banda de estabilidad 5 %** para totales (YoY/MoM): por debajo se dice "estable".
- **Materialidad 1 % de la venta** para mencionar un grupo o producto: evita titulares como "+342 %" sobre una base mínima.
- **Participación:** 2 pp para mencionarla; 5 pp para recomendar investigar.
- **Concentración:** ≥ 50 % de la venta.
- Revisar los umbrales con **6 meses de historial** (ver §10): una banda fija es provisional; la variabilidad real de cada indicador la reemplazará.

## 10. Lo que falta para llegar al nivel del prompt maestro (§7)

| El prompt pide | Estado | Qué hace falta |
|---|---|---|
| Identificar variaciones relevantes | ✅ | — |
| Explicar cambios importantes | ✅ (descomposición, aportes, patrones) | — |
| Comparar periodos y generar conclusiones | ✅ | — |
| Proponer observaciones ejecutivas | ✅ (resumen y recomendaciones) | — |
| **Detectar tendencias** | ✅ (con historial) | `history/store.py` guarda la foto de KPIs de cada reporte (inmutable, versionado); `narrative/trends.py` detecta 2+ variaciones consecutivas fuera de la banda de ±5 %. Con menos de 3 periodos dice *información insuficiente*. Solo en pantalla de revisión (`trends.json`). |
| **Detectar desviaciones** | ❌ | Una referencia: **meta/presupuesto** por mes/línea, o la variabilidad histórica. |
| Distinguir hecho / interpretación / hipótesis / información insuficiente | ✅ (+ recomendación) | — |
| Respetar el estilo de los originales | ✅ | — |
| Permitir edición manual | ✅ (`narrative.json`, con verificación) | UI de revisión |
| **Explicar causas** | ✅ (aportadas por el equipo) | **«Contexto del periodo»** (`--contexto` / parámetro `context`): sale en el resumen ejecutivo como *contexto aportado*, sin verificar, y queda en el historial. Tiene prioridad sobre los hallazgos de menor importancia. |
| IA para redactar mejor (Cohere) | ✅ | Opcional; solo reformula insights ya verificados; cada texto se reverifica (ver `docs/ARQUITECTURA.md` §8.1) |

**Pendiente de la lista:** desviaciones (necesita meta o presupuesto) y la UI de revisión (la maqueta ya está aprobada).
