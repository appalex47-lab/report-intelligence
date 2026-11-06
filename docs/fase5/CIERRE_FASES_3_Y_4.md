# Cierre verificable de las Fases 3 y 4

Estado comprobado el 2026-11-06 sobre el repositorio y GitHub. No reescribe ninguna auditoría anterior (`docs/fase3a/*`, `docs/fase4/*`) y distingue **implementado**, **validado** e **integrado**.

## 1. Integración (verificada)

| | PR #22 (cierre documental de la Fase 3) | PR #23 (Fase 4) |
|---|---|---|
| HEAD fusionado | `abf651b88206862cec2b9e2199e2eac13e8018b5` | `27c106b35a375f528ba41590121d440472eca23c` |
| CI del SHA fusionado | `Pruebas` run 57, success | `Pruebas` run 58, success |
| **Commit de integración en `main`** | `9007f759fa215da5fcde14737c741ec77d6ed9af` | `47dc3af47e9425cebd135e9aec0b4a2f783225ff` |
| CI posterior en `main` | `Pruebas` run 60, success | `Pruebas` run 61, success |
| Publicación de Pages | run 19: **cancelado** (superado por el del #23) | run 20: falló 3 veces en `deploy-pages` («Deployment failed, try again later») y **terminó en success en el 4.º intento** |
| Orden | primero | segundo, tras comprobar que seguía limpio contra el nuevo `main` |

La integración se hizo cuando el usuario la autorizó expresamente en el chat; antes, el clasificador de permisos del entorno la había bloqueado en varias ocasiones. `main` actual: `47dc3af`. Documentación de cierre de la Fase 3 (`docs/fase3a/CIERRE_FASE3.md`) y de la Fase 4 (`docs/fase4/*`) **publicadas en `main`**.

## 2. Fase 3

| Criterio | Estado | Evidencia |
|---|---|---|
| AC-10 manifiesto y `hash_resultado` | **CUMPLIDO** | `test_procedencia_manifiesto`, `test_provenance`, `tests/regression/test_hash_resultado` |
| AC-13A fallo de procedencia no impide el reporte | **CUMPLIDO** | `test_procedencia_captura`, `test_procedencia_servicio` |
| AC-11 estados «se producen y se muestran» | **NO CUMPLIDO** | se producen en backend; no se muestran en la interfaz (`AC11_AC12.md`) |
| AC-12 reportes previos como `no_reproducible (legado)` | **NO CUMPLIDO** | ídem |
| AC-28 release publicada | **NO DEMOSTRADO** | workflow implementado y probado; sin publicación real verificada (`PUBLICACION_AC28.md`) |
| 3B | **SIN ALCANCE FORMAL** | ningún documento la define; no se desarrolló ni se marcó completada |

**AC-11 y AC-12 no corresponden a la Fase 5** (su alcance es RQ-13/14/15/19): la 3A los difirió a una «fase de interfaz posterior» sin numerar (H-8, D-D, L-1, L-3) y no hay dependencia técnica con la Fase 5. Se mantienen NO CUMPLIDOS; la evidencia, la fase responsable y las acciones futuras están en `AC11_AC12.md`.

**Dictamen de la Fase 3:** *no* se declara completamente cerrada: conserva AC-11 y AC-12 NO CUMPLIDOS y AC-28 NO DEMOSTRADO. Está implementada e integrada en backend y procedencia.

## 3. Fase 4

| Criterio | Estado |
|---|---|
| 14 criterios de `docs/fase4/AUDITORIA_CIERRE_FASE4.md` | **VERIFICADOS** (con observaciones no bloqueantes) |
| Integración | **integrada** (`47dc3af`) |

La Fase 5 corrigió un defecto de la Fase 4: el panel rotulaba los montos como «MXN»; ningún libro declara la moneda (unidad inventada). Ahora `unidad: "moneda"` con la nota «la moneda no está declarada en el libro», con una prueba que lo impide.

## 4. Observaciones y límites

No bloqueantes heredadas: limpieza manual de una publicación fallida, política de CI conservadora, unidad de carritos no verificable, 25 % y 10 % heredados sin validar. **No verificado:** el comportamiento del sitio publicado (el entorno no alcanza `github.io`) y con datos de producción (solo libros de ejemplo sintéticos). Pruebas y resultados con SHA: `AUDITORIA_CIERRE_FASE5.md` §3.
