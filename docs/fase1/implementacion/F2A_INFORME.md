# Informe — Fase 2A: motor de reglas de negocio (implementación y configuración)

Referencias: `docs/MOTOR_REGLAS.md` (diseño, reglas, diagrama), `docs/CONFIGURACION_FASE1.md`, `docs/MODELO_HALLAZGOS.md`, especificación final de Fase 1.
**Estado: Fase 2A implementada y a la espera de revisión. No se declara terminada la Fase 2** (la 2B contempla pruebas exhaustivas, validación de resultados y comprobación completa de regresiones).

## 1. Verificación previa (antes de programar)
| Comprobación | Resultado |
|---|---|
| Especificación final de Fase 1 leída | Sí (la misma sobre la que se trabajó) |
| Fase 1 de implementación presente | Sí, en la rama de trabajo (`Finding` extendido, `backend/app/config/`, `version.py`, fixtures). **El PR #11 con esos componentes sigue abierto, sin fusionar** |
| Línea base disponible | Sí: `tests/regression/base/` y `tools/capture_baseline.py` (4 escenarios) |
| Dependencias de las cinco reglas | `models.Finding` (campos de Fase 1), `config` (parámetros y catálogo), lector `raw.common.read_tables`, `raw.glp1._windows` (definición de ventana), criterios de pedido de `raw.glp1.build` |
| Fórmulas F-01 a F-12 | Revisadas; implementadas F-01, F-02, F-03, F-04, F-05, F-06, F-07, F-08 (combinaciones) y F-11 como cálculo de solo lectura. F-09, F-10 y F-12 (E1, E2, derivación de `carritos_abandonados`) **no se tocaron** |

## 2. Qué se implementó
| Entregable | Dónde |
|---|---|
| Motor de reglas | `backend/app/validator/motor.py` |
| Configuración versionada del catálogo de reglas | `backend/app/config/reglas.json` (v1.1.0, sección `reglas`) + validador en `backend/app/config/__init__.py` |
| Cinco reglas | `rules_datos.py` (R-REL-PAC-PED, R-CUADRE-DIM, R-DENOM), `rules_conc.py` (R-CONC-COMPRAS, R-COBERTURA-ATC), `rel_pedidos_carritos.py` (IND-01) |
| Estados normalizados | `valid`, `warning`, `error`, `not_verifiable`, `not_applicable` (+ etiqueta `not_validated_with_real_data`); compatibilidad con `severity` (nunca `block`) |
| Mensajes comprensibles y evidencia | Plantillas en `reglas.json`; `Resultado.evidencia` |
| Lectura/normalización separadas | `validator/normalizar.py`, `validator/operandos.py` |
| Documentación y diagrama | `docs/MOTOR_REGLAS.md`, `docs/ARQUITECTURA.md` §17.1, `docs/CONFIGURACION_FASE1.md` |
| Pruebas de humo y de comportamiento clave | `tests/unit/test_motor_reglas.py` (47) |

## 3. Resultados sobre los machotes sintéticos (GLP-1 y AETOPS, sept-2026)
| Regla | GLP-1 | AETOPS |
|---|---|---|
| R-REL-PAC-PED | `valid`: 2 356 pedidos, 1 966 pacientes únicos, cobertura de paciente 100 % | `valid`: 1 436 pedidos, 962 pacientes únicos |
| R-CUADRE-DIM | `warning`: 4 combinaciones no exclusivas (estado y región por paciente; SKU por pedido y paciente); el resto `not_verifiable` (sin declarar) | `warning`: 10 combinaciones (sucursal, línea, categoría, SKU; canal y estado por paciente) |
| R-CONC-COMPRAS | `valid`: 2 356 (sistema de ventas) vs 2 643 (GA4), diferencia +12,18 % ≤ 20 % | `not_applicable` («sin hoja `trafico`») |
| R-DENOM | `valid` para ticket, IND-01 ×2 y brecha | `valid` (solo ticket) |
| R-COBERTURA-ATC / IND-01 | `warning` informativo, dos resultados independientes: **12,48 %** (pedidos del sistema de ventas) y **14,00 %** (compras GA4), 18 883 carritos agregados, «unidad no declarada» | `not_applicable` |

Coinciden con las observaciones OBS-04, OBS-05 y OBS-10 de la especificación. Son datos sintéticos: no son evidencia operacional.

## 4. Pruebas y comprobaciones (esta fase)
| Prueba | Resultado |
|---|---|
| `pytest tests/unit` (suite completa) | **276 passed**, 0 failed, 0 skipped, 499 s (antes: 181 originales + 48 de Fase 1 = 229; +47 nuevas) |
| Las 181 pruebas originales | Aprobadas, sin editar |
| `tools/capture_baseline.py --check` | Idéntico en los 4 escenarios (motor, hallazgos, narrativa, huellas del deck) |
| `pytest tests/regression tests/golden` | 13 passed; 35 skipped (golden: faltan `REPORT_FIXTURES_DIR` y los archivos reales) |
| Fixtures | `make_fixtures_fase1.py --check`: idénticas |
| Python 3.12 (CI) | Pruebas nuevas y de Fase 1 (87) aprobadas; la suite completa en 3.12 no se repitió en esta fase |

Estas pruebas **no son las pruebas exhaustivas de la 2B**; ninguna prueba T-xx de la especificación se marca como aprobada.

## 5. Inventario de archivos
| Archivo | Acción | Motivo | Riesgo |
|---|---|---|---|
| `backend/app/validator/motor.py` | Creado | Motor, estados, catálogo, adaptador a `Finding`, `evaluar_razon` | Bajo |
| `backend/app/validator/normalizar.py` | Creado | `Contexto` de solo lectura | Bajo |
| `backend/app/validator/operandos.py` | Creado | Cifras y razones compartidas | Bajo |
| `backend/app/validator/rules_datos.py` | Creado | R-REL-PAC-PED, R-CUADRE-DIM, R-DENOM | Bajo |
| `backend/app/validator/rules_conc.py` | Creado | R-CONC-COMPRAS, R-COBERTURA-ATC | Bajo |
| `backend/app/validator/rel_pedidos_carritos.py` | Creado | IND-01 | Bajo |
| `backend/app/config/reglas.json` | **Modificado** (v1.0.0 → v1.1.0, sección `reglas` añadida) | Catálogo versionado de reglas | Bajo |
| `backend/app/config/__init__.py` | **Modificado** | Validación estructural del catálogo de reglas | Bajo |
| `tests/unit/test_motor_reglas.py` | Creado | Pruebas de humo y comportamiento clave | Bajo |
| `docs/MOTOR_REGLAS.md` | Creado | Documentación técnica y diagrama | Bajo |
| `docs/ARQUITECTURA.md`, `docs/CONFIGURACION_FASE1.md` | **Modificados** (apartados añadidos) | Documentación | Bajo |
| `docs/fase1/implementacion/F2A_INFORME.md` | Creado | Este informe | Bajo |

No se modificaron: `models.py`, `validator/rules.py`, `raw/*`, `pipeline.py`, `web/*`, `build.py`, narrativa, IA, plantillas, láminas, importadores, workflows, `validacion_registro.json`, fórmulas ni cifras. No se eliminó ningún archivo.

## 6. Decisiones de interpretación a revisar
Detalladas en `docs/MOTOR_REGLAS.md` §4: (1) los pedidos del sistema de ventas usan los criterios del motor actual; (2) `calculable` de IND-01 exige unidad declarada, así que hoy todo resultado nace como advertencia informativa; (3) clase adicional `sin_fecha` en R-REL-PAC-PED; (4) R-CUADRE-DIM reporta solapamientos **observados** aunque no haya propiedades declaradas; (5) `tipo` propuesto por regla y `gravedad` en `null`; (6) `validacion_registro.json` sin cambios; (7) flags desactivados y servicios sin cablear.

## 7. Riesgos abiertos
| Riesgo | Nivel |
|---|---|
| Rama compartida: las confirmaciones de la 2A están en la misma rama que el PR #11 (Fase 1, abierto); si se quiere revisar por separado, hay que dividir | Medio (de proceso) |
| Interpretaciones de §6 aún no confirmadas por el usuario (AMB-1, AMB-5, AMB-7, AMB-9 siguen abiertas) | Medio |
| El motor no se ejecutó en Pyodide (navegador) | Medio |
| Lectura duplicada si luego se cablea junto a los pipelines existentes (≈ 4–7 s por libro grande) | Bajo |
| Sin validación con datos reales: todo resultado lleva `not_validated_with_real_data` | Esperado |

## 8. Dependencias para la Fase 2B
Fixtures funcionales y pruebas exhaustivas (T-01…T-05, T-10, T-21, T-22 y los casos de §3.3 y §8.2); decisión sobre el cableado a `web/service.analyze` y la interfaz (flag `validacion_fase1`/`relacion_pedidos_carritos`); confirmar AMB-1, AMB-5, AMB-7, AMB-9 y la `gravedad` por regla; aprobar la validación sintética y reflejarla en `validacion_registro.json`; probar en Pyodide; decidir si el PR #11 se fusiona antes.
