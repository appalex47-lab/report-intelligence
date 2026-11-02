# Objetivo del reporte y narrativa ejecutiva

> **Estado:** propuesta construida a partir del análisis de los reportes originales (AETOPS Agosto 2026, Q1 2026, Nov 2025;
> GLP-1 Agosto 2026). Los puntos marcados **[Validar]** son decisiones del dueño del reporte.

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

**Lo que el reporte NO hace:** no atribuye causas que los datos no demuestran (campañas, desabasto, estacionalidad,
precios). Eso corresponde a quien conoce el negocio y se redacta a mano en la revisión.

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

## 8. Decisiones por validar con el dueño del reporte

1. ¿Es correcto el **propósito** de la sección 1 y la audiencia?
2. ¿Qué cuenta como **relevante** (umbrales de la sección 4)?
3. **Negado:** ¿es "venta no concretada por disponibilidad"? De eso depende hablar de "oportunidad de recuperación".
4. ¿El reporte debe incluir **recomendaciones/acciones** o solo lectura? (Hoy: lectura + "qué vigilar", sin acciones.)
5. **Pedidos por canal** suman 2.1× el total: ¿cuál es la definición correcta? Mientras tanto no se usan en la narrativa.
