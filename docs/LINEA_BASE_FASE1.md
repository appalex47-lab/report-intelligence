# Línea base de la Fase 1 — antes y después

Auditoría de la arquitectura existente: `docs/fase1/implementacion/F1_AUDITORIA_Y_LINEA_BASE.md` (no se duplica aquí).
Fecha de las ejecuciones: 2026-11-03 (UTC). Entorno: Linux 6.18.44, Python 3.13.18, LibreOffice y `pdftoppm` presentes, plantillas locales no versionadas presentes, `REPORT_FIXTURES_DIR` sin definir. CI y `Dockerfile` usan Python 3.12: la suite también se ejecutó en 3.12 (ver §2b).

## 1. Referencias
| Dato | Valor |
|---|---|
| Rama de origen | `main` en `6e1104d` (PR #10 fusionado) |
| Rama de trabajo | `claude/awesome-wozniak-f35r21`, reiniciada desde `main` |
| Commit de línea base (P-00) | `386099b` (solo archivos nuevos: `tools/capture_baseline.py`, `tests/regression/**`, documento de auditoría) |
| Árbol al iniciar | Limpio |

## 2. Resultados: antes y después
| Comprobación | Línea base (antes de cambiar código, `6e1104d`) | Después de los cambios del modelo | Diferencia |
|---|---|---|---|
| `python -m pytest tests/unit -q` (comando oficial de `tests.yml`) | **181 passed**, 0 failed, 0 error, 0 skipped, 526,63 s | **228 passed**, 0 failed, 0 error, 0 skipped, 506,31 s | +47 pruebas nuevas (todas aprobadas); las 181 originales siguen aprobadas; ninguna editada |
| `tools/capture_baseline.py --check` (motor, hallazgos, narrativa y huellas del deck; 4 escenarios) | idéntico a sí mismo (determinismo comprobado al capturar) | **idéntico** en los 4 escenarios y en ambas capas | 0 diferencias |
| `python -m pytest tests/regression -q` | 13 passed (69,5 s) | **13 passed** (71,7 s) | Ninguna |
| `python -m pytest tests/golden -q` | 35 skipped (sin `REPORT_FIXTURES_DIR`) | 35 skipped | Ninguna; omitidas por falta de archivos reales, no aprobadas |
| `python tools/make_fixtures_fase1.py --check` | no existía | **idéntico** | — |

Las 47 pruebas nuevas: `test_hallazgo_compat.py` (compatibilidad de `Finding`), `test_config_fase1.py` (catálogo y configuración) y `test_fixtures_fase1.py` (fixtures). Se agregaron en archivos nuevos de `tests/unit/`; no se tocó ninguna prueba existente.

## 2b. Verificación en Python 3.12 (el de CI y el `Dockerfile`)
Entorno: venv con Python 3.12.3 e instalación de `requirements.txt` (pytest 9.2.0, python-pptx 1.0.2, openpyxl 3.1.5, fastapi 0.162.0); mismo árbol de código (`e93f8fa`).
| Comprobación | Resultado en Python 3.12 |
|---|---|
| `python -m pytest tests/unit -q` | **228 passed**, 0 failed, 0 skipped, 1 warning, 564,8 s (la advertencia es de `fastapi/starlette` por `httpx`, ajena al código del proyecto) |
| `tools/capture_baseline.py --check` | 4 escenarios idénticos en motor y deck (los snapshots se capturaron en 3.13: el resultado no depende de la versión) |
Lo que sigue **sin ejecutarse**: Pyodide (el motor en el navegador).

Seguimiento posterior: se añadió 1 prueba (`test_el_directorio_de_fixtures_no_oculta_el_modulo_tests_fixtures`; aprobada sola en 3.13 y 3.12) y un paso en `tests.yml` que ejecuta `tests/regression` en CI. La suite completa **no se repitió** con esa prueba adicional (serían 229); la confirmará el CI del PR.

## 3. Regresiones
**Ninguna.** Las 181 pruebas originales siguen aprobadas, la foto del motor y del deck es idéntica, y los hallazgos conservan `id` y `severity`. Los tiempos son comparables (la diferencia de 20 s está dentro de la variación del entorno; no se interpreta como mejora).

## 4. Qué demuestra y qué no
- Demuestra que, sobre los machotes sintéticos, el comportamiento del motor, la narrativa, los hallazgos y la estructura del PPTX generado no cambiaron.
- No demuestra nada sobre datos reales, sobre Python 3.12 (CI) ni sobre la apariencia visual (no hay render en la línea base).
- La capa `deck` solo se compara donde exista la plantilla local con el mismo SHA-256; en CI se omite.

## 5. Cómo reproducir
```bash
git checkout 6e1104d && python -m pytest tests/unit -q            # línea base anterior (181)
git checkout claude/awesome-wozniak-f35r21
python -m pytest tests/unit -q                                      # después (228)
python tools/capture_baseline.py --check                            # foto del motor y del deck
python -m pytest tests/regression -q
python -m pytest tests/golden -q                                    # se omite sin REPORT_FIXTURES_DIR
python tools/make_fixtures_fase1.py --check
```
Si `--check` o `tests/regression` fallan: no se regenera la foto; se documenta el cambio en `CAMBIOS_JUSTIFICADOS.md` (spec §11.6).

## 6. Pruebas de la especificación y su estado tras esta fase
Todas las pruebas funcionales T-01 a T-22 (incluida T-10b) siguen **Pendiente**. Lo logrado en esta fase: P-00 realizado; S-01 con evidencia previa y posterior (181 → 228 aprobadas); S-02 omitida con motivo; T-12 no existe todavía; el mecanismo de comparación que servirá a T-13 existe y funciona; T-06 (migración de hallazgos), T-20 (fixtures) y parte de T-07 (versiones) tienen **pruebas preliminares** en los archivos nuevos, pero no se declaran aprobadas porque las pruebas definitivas de la especificación cubren más (por ejemplo, T-06 exige el catálogo `validator/catalogo.py` por `id`, que no existe todavía).
