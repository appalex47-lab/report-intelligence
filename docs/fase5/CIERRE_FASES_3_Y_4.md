# Cierre verificable de las Fases 3 y 4

Estado comprobado el 2026-11-06 sobre el repositorio y GitHub. Este documento no reescribe ninguna auditoría anterior (`docs/fase3a/*`, `docs/fase4/*`) y distingue **implementado**, **validado** e **integrado**.

## 1. Integración

| | PR #22 (cierre documental de la Fase 3) | PR #23 (Fase 4) |
|---|---|---|
| Estado | abierto, sin fusionar, limpio | abierto, sin fusionar, limpio |
| HEAD exacto | `abf651b88206862cec2b9e2199e2eac13e8018b5` | `27c106b35a375f528ba41590121d440472eca23c` |
| CI del SHA exacto | `Pruebas` run 57, success | `Pruebas` run 58, success |
| Cambios | 2 archivos de documentación | 9 archivos (código, pruebas, documentación) |
| **Fusión** | **NO se realizó** | **NO se realizó** |
| SHA de integración | no existe | no existe |

**Causa:** el clasificador de permisos del entorno bloqueó la fusión («Merge Without Review») aunque el encargo la autorizaba, tanto antes como durante esta ejecución. No se intentó por otra vía. `main` sigue en `f15abfea707c1f0adcdedcc6d94ddcbc2024226e` (PR #21). **Consecuencias:** no hay CI posterior a la integración que verificar; la documentación de cierre de la Fase 3 no está publicada en `main`; la Fase 5 se construyó sobre el contenido de ambos PR, de modo que su propio PR contiene también esos commits hasta que se fusionen.

## 2. Fase 3

| Subfase | PR | Implementada | Validada | Integrada |
|---|---|---|---|---|
| 3A-0 a 3A-5 | #15, #16/#17, #18, #19, #20, #21 | sí | CI | **sí (en `main`)** |

| Criterio | Estado | Evidencia |
|---|---|---|
| AC-10 manifiesto y `hash_resultado` | **CUMPLIDO** | `test_procedencia_manifiesto`, `test_provenance`, `tests/regression/test_hash_resultado` |
| AC-13A fallo de procedencia no impide el reporte | **CUMPLIDO** | `test_procedencia_captura`, `test_procedencia_servicio` |
| AC-11 estados de reproducibilidad «se producen y se muestran» | **NO CUMPLIDO** | Se producen en backend (`test_procedencia_comparacion` y relacionadas). **No se muestran**: `grep` de `frontend/index.html`, `worker.js`, `bridge.py`, `app.py` y `service.py` no encuentra ninguna presentación, ruta ni botón de reproducibilidad; el propio `procedencia.json` no tiene botón en la interfaz. La 3A-4 lo declara (L-3) |
| AC-12 reportes previos como `no_reproducible (legado)` | **NO CUMPLIDO** | Misma evidencia: la lógica existe (`provenance_verify.py`), la presentación no |
| AC-28 release publicada | **NO DEMOSTRADO** | El workflow y su lógica están probados (`test_release_*`); no se ejecutó una publicación real ni se verificó lo desplegado (§5) |
| 3B | **SIN ALCANCE FORMAL** | Ningún documento la define (solo «linaje y auditoría del reporte», fuera de alcance de 3A); no se desarrolló, no se marca como completada ni se usa para justificar cambios |

**¿Corresponden AC-11 y AC-12 a la Fase 5?** No: la especificación de Fase 1 asigna a la Fase 5 RQ-13, RQ-14, RQ-15 y RQ-19 (QA del PPTX y anexo de calidad). La presentación de la reproducibilidad no figura en ellos, y la 3A la difirió expresamente a «una fase de interfaz posterior» (L-1, L-3). Por eso no se implementó en esta fase y los dos criterios **permanecen NO CUMPLIDOS**. Corregirlos exige decidir a qué fase pertenece y diseñar la pantalla (qué reporte se verifica, con qué archivos fuente, cómo se regenera).

**Dictamen de la Fase 3:** *no* se declara completamente cerrada: conserva AC-11 y AC-12 NO CUMPLIDOS y AC-28 NO DEMOSTRADO. Está implementada e integrada en backend y procedencia; falta su presentación y la publicación real.

## 3. Fase 4

| Criterio | Estado |
|---|---|
| 14 criterios de `docs/fase4/AUDITORIA_CIERRE_FASE4.md` | **VERIFICADOS** (con observaciones no bloqueantes y la auditoría independiente corregida) |
| Integración | **pendiente** (PR #23 abierto) |

**Corrección posterior de la Fase 5:** el panel de la Fase 4 rotulaba los montos como «MXN»; ningún libro declara la moneda. Es una unidad inventada y se corrigió (`unidad: "moneda"` con la nota «la moneda no está declarada en el libro»), con una prueba que lo impide.

## 4. Pruebas y observaciones

Las pruebas y sus resultados con SHA están en `AUDITORIA_CIERRE_FASE5.md` §3. Observaciones no bloqueantes heredadas: limpieza manual de una publicación fallida, política de CI conservadora, sin anexo en el PPTX (ver `IMPLEMENTACION_FASE5.md` L-3), unidad de carritos no verificable, 25 % y 10 % heredados sin validar.

## 5. Lo que no se pudo verificar

* La **publicación real**: el entorno no alcanza `github.io` (HTTP 000) ni la API de GitHub Pages (403 del proxy), `main` no cambió y no se autorizó ni se cumplieron las condiciones para crear una release.
* El comportamiento con datos de producción: solo se usaron libros de ejemplo sintéticos.
