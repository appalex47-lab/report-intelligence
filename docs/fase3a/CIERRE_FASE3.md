# Cierre de la Fase 3

| | |
|---|---|
| Estado | **FASE 3 CERRADA Y CONFIRMADA**, bajo la interpretación normativa de §2 (3B sin definición) |
| Base verificada | `main` en `f15abfea707c1f0adcdedcc6d94ddcbc2024226e` (fusión del PR #21 sobre `a501b1b`) |
| Fecha | 2026-11-06 |

Este documento no reescribe ninguna auditoría anterior. Distingue **implementado** (existe en el código), **validado** (probado y con CI) e **integrado** (en `main`).

## 1. Objetivo y alcance
La Fase 3 de la especificación de Fase 1 (RQ-10, RQ-11, RQ-12) es la procedencia y reproducibilidad de los reportes, desarrollada en `ESPECIFICACION_FASE3A_PROCEDENCIA.md` (subfases 3A-0 a 3A-5). Criterios: AC-10, AC-11, AC-12 y AC-28 (condicional); pruebas T-07, T-08, T-16 y V-02 (condicional).

## 2. Fase 3B
Los documentos del repositorio solo nombran la 3B como «linaje y auditoría del reporte» y siempre como **fuera de alcance de 3A**. Ningún documento le asigna requisitos (RQ), criterios (AC), pruebas ni entregables; la trazabilidad de Fase 1 asigna todo lo de «Fase 3» a la procedencia (3A). Por eso:
* no se inventa su alcance ni se implementa;
* tampoco se declara «opcional por conveniencia»: se declara **sin definición normativa**, y no hay nada verificable contra lo cual medirla;
* el cierre se confirma sobre los requisitos que sí están definidos. **Si el usuario entiende la 3B como obligatoria, debe aportar su alcance**; esa información no existe en el repositorio.

## 3. Estado por subfase
| Subfase | Implementada | Validada | Integrada |
|---|---|---|---|
| 3A-0 especificación | sí | revisión documental | sí |
| 3A-1 versiones (T-16) | sí | CI | sí |
| 3A-2 hash canónico | sí | CI | sí |
| 3A-3 manifiesto y captura | sí | CI | sí |
| 3A-4 comparación (AC-11, AC-12) | sí | CI y auditoría integral | sí (PR #20, `8d1bbc7`) |
| 3A-5 `release.yml` (RQ-12) | sí | CI run 53 sobre `a501b1b`; 225 pruebas propias | **sí (PR #21, `f15abfe`)** |

## 4. Criterios de aceptación
| Criterio | Estado |
|---|---|
| AC-10 manifiesto y `hash_resultado` | cumplido (3A-2/3A-3) |
| AC-11 estados `exacta`/`parcial`/`no_reproducible` | cumplido (3A-4) |
| AC-12 reportes previos como `no_reproducible (legado)` | cumplido (3A-3/3A-4) |
| AC-28 release publicada | condicional: **workflow implementado y probado; ejecución real (V-02) omitida con motivo** (publicar una release no está autorizado). Según AC-19, una condicional omitida con motivo y lugar registrados no impide el cierre |

## 5. Evidencia posterior a la integración
* Fusión: `f15abfe`, contiene `a501b1b`; `release.yml`, `tools/release_app.py` y sus pruebas presentes en `main`.
* CI sobre `f15abfe`: `Pruebas` run 54 success; `Publicar en GitHub Pages` run 18 success.
* Última suite completa local (código de 3A-5, Pyodide activo): 1231 aprobadas, 0 fallidas, 35 omitidas (`tests/golden`, ya omitidas antes).
* `archivos_protegidos --check`: sin cambios. `capture_baseline --check`: idéntico (motor y deck), ejecutado sobre `main`.
* Sin etiquetas `app-v*` ni releases en el repositorio.

## 6. Limitaciones
| Tipo | Elemento |
|---|---|
| No verificable sin autorización | V-02 / AC-28: comportamiento real de GitHub al publicar |
| No verificable | Alcance de la 3B (sin definición normativa) |
| No bloqueante | Limpieza manual de estados parciales de una publicación fallida; ventana mínima de carrera; política de CI conservadora; sin afirmación de reproducibilidad byte a byte |

## 7. Dictamen
Fase 3 cerrada sobre sus requisitos normativos definidos. Pendientes no bloqueantes: V-02 y la definición de la 3B.
