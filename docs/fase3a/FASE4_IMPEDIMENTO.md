# Fase 4 — verificación de la especificación oficial

> **ESTADO: SUPERADO.** Este documento registra el impedimento tal como existía al redactarse. El usuario lo resolvió después definiendo la Fase 4 como **«Escenarios e indicador»** (E1, E2 e IND-01), que coincide con las notas de aplazamiento descritas abajo; su implementación está en el PR #23 (`docs/fase4/IMPLEMENTACION_FASE4.md`, si se fusiona). Se conserva como registro histórico y no se reescribe.

**Resultado (al redactarse): no existe una especificación oficial de la Fase 4 en el repositorio; no se implementó nada.**

Búsqueda en todos los documentos, el código y el historial de git (`git log -S`) de «Fase 4», «Fase 3B», «linaje», «Narrativa y recomendaciones» y «recomendaciones»:

* El nombre «Narrativa y recomendaciones» **no está definido** en ningún documento como fase. `docs/OBJETIVO_Y_NARRATIVA.md` describe una narrativa y recomendaciones ya implementadas (§9), anteriores a estas fases.
* La Fase 4 solo aparece como etiqueta de aplazamiento en `F2B_INFORME_AUDITORIA.md`, `F2B_MATRIZ_PRUEBAS.md` y `F2B_TRAZABILIDAD.md`: etiquetas y aclaraciones en panel y anexo (T-09, T-10b y la parte de panel/anexo de IND-01 / RQ-05). Son notas de qué se pospuso, no una especificación: no definen alcance, arquitectura, contratos, criterios de aceptación ni exclusiones. Además tocarían láminas y panel, lo que la especificación de Fase 1 reserva a la autorización A-3.
* Fase 5 (QA del PPTX) está nombrada aparte y no puede incorporarse.

Implementar sin especificación obligaría a inventar funcionalidades, reglas y criterios, lo que el encargo prohíbe. **Se necesita** el documento que defina la Fase 4 (o su alcance, criterios de aceptación y exclusiones). Con él, la implementación puede hacerse en una sola ejecución.
