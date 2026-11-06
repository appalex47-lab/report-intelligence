# Cierre de la Fase 3

| | |
|---|---|
| Estado | **FASE 3 CERRADA TÉCNICAMENTE CON OBSERVACIONES.** Todo lo implementable y verificable está implementado, validado e integrado; **quedan dos puntos que requieren decisión del usuario** (§4.1): la ejecución real de V-02/AC-28 y la presentación en pantalla de AC-11/AC-12 (L-1, L-3). Ver también §2 (3B sin definición) |
| Base verificada | `main` en `f15abfea707c1f0adcdedcc6d94ddcbc2024226e` (fusión del PR #21 sobre `a501b1b`) |
| Fecha | 2026-11-06 (revisado tras la auditoría independiente de este PR) |

Este documento no reescribe ninguna auditoría anterior. Distingue **implementado** (existe en el código), **validado** (probado y con CI) e **integrado** (en `main`).

> **Corrección respecto de la versión inicial de este documento.** La primera redacción declaraba «FASE 3 CERRADA Y CONFIRMADA» y marcaba AC-11/AC-12 como «cumplido» y AC-28 como no impeditivo por AC-19. La auditoría independiente comprobó que (a) AC-11 y AC-12 dicen «se muestran» y la propia 3A-4 documenta que la comparación **solo existe en backend** (L-3: sin pantalla ni botón), y (b) AC-28 es aplicable (A-5 **sí** se autorizó) y la especificación de 3A declara que «sigue sin cumplirse hasta ejecutar el workflow». Esta versión lo dice así.

## 1. Objetivo y alcance
La Fase 3 de la especificación de Fase 1 (RQ-10, RQ-11, RQ-12) es la procedencia y reproducibilidad de los reportes, desarrollada en `ESPECIFICACION_FASE3A_PROCEDENCIA.md` (subfases 3A-0 a 3A-5). Criterios de la 3A (§12.1): AC-10, AC-11, AC-12, **AC-13A** (propio de la 3A), AC-28 y los «Generales»; pruebas T-07, T-08, T-16 y V-02.

## 2. Fase 3B
Los documentos del repositorio solo nombran la 3B como «linaje y auditoría del reporte» y siempre como **fuera de alcance de 3A** (`ESPECIFICACION_FASE3A_PROCEDENCIA.md` §0, H-7). Ningún documento le asigna requisitos (RQ), criterios (AC), pruebas ni entregables, y ninguna instrucción del usuario la definió. La trazabilidad de Fase 1 asigna todo lo marcado «Fase 3» (RQ-10, RQ-11, T-07, T-08, T-16) a la procedencia. Por eso:
* no se inventa su alcance ni se implementa;
* no se declara «opcional por conveniencia»: se declara **sin definición normativa**; no hay criterio contra el cual medirla;
* el cierre se evalúa sobre los requisitos que sí están definidos. **Si el usuario entiende la 3B como obligatoria, debe aportar su alcance**; no existe en el repositorio.

## 3. Estado por subfase
| Subfase | PR | Implementada | Validada | Integrada |
|---|---|---|---|---|
| 3A-0 especificación | #15 (constancia en #17) | sí | revisión documental | sí |
| 3A-1 versiones (T-16) | #16 | sí | CI | sí |
| 3A-2 hash canónico | #18 | sí | CI | sí |
| 3A-3 manifiesto y captura | #19 | sí | CI | sí |
| 3A-4 comparación (T-08) | #20 (`8d1bbc7`) | sí | CI y auditoría integral | sí |
| 3A-5 `release.yml` (RQ-12) | #21 (`f15abfe`) | sí | CI run 53 sobre `a501b1b`; 225 pruebas propias | **sí** |

## 4. Criterios de aceptación (redacción de `ESPECIFICACION_FASE3A_PROCEDENCIA.md` §12.1)
| Criterio | Estado | Evidencia / alcance exacto |
|---|---|---|
| AC-10 manifiesto, `hash_resultado` estable, versión y SHA en `app.zip` | **cumplido** | `test_procedencia_manifiesto`, `test_provenance`, `test_procedencia_captura`, `test_version`, `test_build_site`, `tests/regression/test_hash_resultado` |
| AC-11 los tres estados se producen y se **muestran** | **cumplido en backend; la presentación en pantalla NO existe** | estados y 0 regeneraciones silenciosas: `test_procedencia_comparacion`, `_evaluar`, `_regenerador`, `_revision_3a4`. La 3A-4 declara L-3: «la comparación solo existe en backend: no hay pantalla ni botón»; la 3A excluye la interfaz (H-8, L-1) |
| AC-12 reportes previos como `no_reproducible (legado)` | **cumplido en backend; presentación en pantalla NO existe** | `provenance_verify.py` («reporte anterior a la Fase 3A: legado»); mismas pruebas |
| AC-13A fallo de procedencia no impide el reporte; nunca un `procedencia.json` incompleto | **cumplido** | `test_procedencia_captura`, `test_procedencia_servicio` (PR-8, PR-9) |
| AC-28 release publicada | **NO CUMPLIDO — workflow implementado y probado, no demostrado** | A-5 sí se autorizó, por lo que AC-28 es aplicable; V-02 (ejecución real) exige publicar una release real, no autorizado. La 3A declara: «sigue sin cumplirse hasta ejecutar el workflow con `publicar` activado» |
| Generales | **cumplido** | 0 fallidas, CI en verde, `capture_baseline --check` idéntico, `archivos_protegidos --check` limpio (ver §5) |

### 4.1 Decisiones que corresponden al usuario (no las toma este documento)
1. **AC-28 / V-02.** O se acepta como observación no bloqueante (AC-19 permite que una condicional termine «omitida con motivo y lugar registrados»; el motivo aquí es que la ejecución exige una release real), o se autoriza ejecutar el workflow para demostrarlo.
2. **Presentación de AC-11/AC-12.** La 3A aprobó expresamente no tener interfaz (H-8, L-1, L-3), pero redactó AC-11/AC-12 con «se muestran». Hay que decidir si esa presentación pertenece a una fase de interfaz posterior (lectura consistente con L-3) o es un requisito pendiente de la Fase 3.

## 5. Evidencia posterior a la integración (verificada de nuevo en la auditoría)
* Fusión: `f15abfe` contiene `a501b1b`; `release.yml`, `tools/release_app.py` y sus pruebas están en `main`.
* CI sobre `f15abfe`: `Pruebas` run 54 success; `Publicar en GitHub Pages` run 18 success.
* Suite completa local del código de 3A-5 (Pyodide activo): 1231 aprobadas, 0 fallidas, 35 omitidas (`tests/golden`, ya omitidas antes).
* `archivos_protegidos --check`: sin cambios. `capture_baseline --check`: idéntico (motor y deck), ejecutado sobre `main`.
* Sin etiquetas `app-v*` ni releases en el repositorio.

## 6. Trazabilidad vigente (la de `F2B_TRAZABILIDAD.md` es una fotografía del cierre de la 2B y no se reescribe)
| Requisito | Estado de la 2B | Estado vigente | Evidencia |
|---|---|---|---|
| RQ-10 manifiesto de procedencia | No cumplido (Fase 3) | cumplido (AC-10, AC-13A) | pruebas de §4 |
| RQ-11 reproducibilidad y sus estados | No cumplido (Fase 3) | cumplido en backend (AC-11/AC-12; ver §4.1) | `test_procedencia_comparacion` y relacionadas |
| RQ-12 releases etiquetadas | No cumplido (A-5 pendiente) | implementado y probado; **no demostrado** (AC-28) | `test_release_*` |

## 7. Limitaciones
| Tipo | Elemento |
|---|---|
| No verificable sin autorización | V-02 / AC-28: comportamiento real de GitHub al publicar una release |
| No verificable | Alcance de la 3B (sin definición normativa) |
| Pendiente de decisión | Presentación en pantalla de AC-11/AC-12 (§4.1) |
| No bloqueante | Limpieza manual de estados parciales de una publicación fallida; ventana mínima de carrera; política de CI conservadora; sin afirmación de reproducibilidad byte a byte |

## 8. Dictamen
Fase 3 **cerrada técnicamente con observaciones**: sin defectos conocidos en lo implementado, con dos puntos de decisión del usuario (§4.1) y la 3B sin definición. No se declara «cerrada y confirmada» mientras AC-28 siga aplicable y sin demostrar.
