# Fase 1 de implementación — Modelo y línea base

**Estado:** auditoría del estado actual y línea base **completadas**. La parte de *modelo técnico y configuración* (sección 6 del encargo) **no se implementó**: el encargo recibido llega cortado en esa sección y se espera el texto restante (ver §9).

Fuente de verdad: `docs/fase1/ESPECIFICACION_FASE1_REPORT_INTELLIGENCE_FINAL.md` e `INFORME_CIERRE_AUDITORIA_FASE1.md`.
Alcance de este documento: solo hechos comprobados en el repositorio y resultados realmente ejecutados.

---

## 1. Estado de Git y entorno

| Dato | Valor |
|---|---|
| Repositorio | `appalex47-lab/report-intelligence` (remoto local: `repot-intelligence`) |
| Rama de trabajo | `claude/awesome-wozniak-f35r21`, reiniciada desde `origin/main` (la rama anterior ya estaba fusionada en el PR #10) |
| Commit inicial (`main`) | `6e1104d4b6b1f41dfd4352267ce1c1a95859d4e7` |
| Árbol de trabajo al iniciar | Limpio; sin archivos modificados previamente |
| Fecha de ejecución | 2026-11-03 (UTC) |
| Sistema | Linux 6.18.44 |
| Python local | 3.13.18 (el workflow `tests.yml` y el `Dockerfile` usan **3.12**; ver incidencia INC-F1-02) |
| Herramientas externas | LibreOffice (`/usr/bin/soffice`) y `pdftoppm` presentes en este entorno |
| `REPORT_FIXTURES_DIR` | No definida |

**Dependencias instaladas relevantes** (`requirements.txt` declara rangos): openpyxl 3.1.5, PyYAML 6.0.3, pydantic 2.13.5, python-pptx 1.0.2, pytest 9.2.0, fastapi 0.162.0, uvicorn 0.54.0, python-multipart 0.0.32, httpx 0.28.1; además presentes en el entorno: lxml 6.1.3, pandas 3.0.5, Pillow 12.3.0, XlsxWriter 3.2.9, et_xmlfile 2.0.0.

**Plantillas PPTX:** existen en este entorno cuatro archivos `templates/<formato>/1/template.pptx`, pero están **excluidos por `.gitignore`** (contienen marca y datos comerciales). No están en el repositorio ni en CI. Por eso varias pruebas **se ejecutan aquí y se omiten en CI**.

---

## 2. Auditoría del estado actual (lo que realmente existe)

### 2.1 Tecnologías y estructura
- **Lenguaje:** Python (backend); JavaScript/HTML sin framework (frontend); YAML para perfiles; SQLite para el historial.
- **Backend:** `backend/app/` — 52 módulos, ≈ 8 060 líneas. Subpaquetes: `calc/`, `deck/`, `history/`, `importer/`, `narrative/`, `qa/`, `raw/`, `validator/`, `web/`.
- **Frontend:** `frontend/index.html` (720 líneas) y `frontend/worker.js` (119). La aplicación publicada corre en el navegador con **Pyodide 0.27.7** dentro de un Web Worker; `backend/app/web/bridge.py` replica las rutas de la API.
- **Otros directorios:** `profiles/` (perfiles YAML de importación), `templates/` (plantillas, no versionadas), `tools/` (generadores y `build_site.py`), `data/ejemplos/` (machotes sintéticos), `docs/`, `docker/`, `legacy/`, `convertir/`, `salida_revision/`.

### 2.2 Puntos de entrada
| Entrada | Ubicación |
|---|---|
| CLI | `python -m backend.app.cli` (`backend/app/cli.py`) |
| API FastAPI (servidor) | `backend/app/web/app.py` (rutas `/api/runs…`, `/api/templates`, `/api/history…`, `/api/machote`) |
| Navegador (Pyodide) | `frontend/worker.js` → `backend/app/web/bridge.py` → `backend/app/web/service.py` |
| Empaquetado del sitio | `tools/build_site.py` |

### 2.3 Flujo de procesamiento
`importer/` (libro con hojas de resumen, perfiles YAML) **o** `raw/` (datos crudos: `ventas`, `catalogo`, `trafico`, `negados`) → `pipeline.py` (`run_aetops`, `run_aetops_raw`, `run_glp1`, `run_glp1_raw`) → `calc/` + `validator/` (hallazgos) → `narrative/` (hechos, escenarios, resumen ejecutivo, recomendaciones) → `deck/` (relleno en el lugar de la plantilla) → `qa/` + `render.py` (LibreOffice) → `history/store.py`.

### 2.4 Motor de reglas y modelo de datos
- **Modelo:** `backend/app/models.py`. `Finding(id, severity ∈ {block, warn, info}, message, evidence)` es un `dataclass` **inmutable**; `Value` distingue faltante de cero; `Lineage` registra procedencia.
- **Validaciones:** `validator/rules.py`, `validator/glp1_rules.py`, `validator/extra.py`, `validator/targets.py`. `has_blockers()` lee `severity`.
- **Uso de `Finding`/`severity`:** 83 construcciones de `Finding(` en `backend/app` y 25 referencias a `severity` entre backend y frontend.
- **Umbrales y escenarios:** `backend/app/narrative/rules.py` (`NarrativeRules`, dataclass inmutable) incluye `recovery_scenario = 0.25` y `cart_recovery_scenario = 0.10`.
- **Aviso de compras vs pedidos:** `backend/app/raw/glp1.py` (`TRAFICO_PURCHASE_DIFFERS`, umbral 20 %).

### 2.5 Configuración y persistencia (arquitectura reutilizable)
| Mecanismo existente | Ubicación | Observación |
|---|---|---|
| Perfiles de importación como **datos** (YAML) | `profiles/{aetops,glp1}/{mensual,trimestral}.yaml`, cargados por `importer/profile.py` (`PROFILES_DIR`) | Patrón ya establecido de configuración como dato |
| Umbrales como dataclass inmutable | `narrative/rules.py` (`RULES`) | Configurable por código, no por archivo |
| Variables de entorno | `REPORT_RUNS_DIR`, `REPORT_TEMPLATES_DIR`, `REPORT_HISTORY_DB` (`web/service.py`) | Rutas de ejecución |
| Historial | `history/store.py`: SQLite **solo inserción** (triggers impiden UPDATE/DELETE) | Guarda KPIs, hashes SHA-256 de fuentes, versión de plantilla y hallazgos |
| Persistencia en navegador | IndexedDB para plantillas e historial (frontend) | |
| Metas | Capturadas a mano (`targets.py`) | |

### 2.6 Integraciones
- **Cohere (opcional):** la llamada sale del navegador con la clave del usuario (`frontend/index.html`, `web/service.py`); la IA no modifica cifras (re-verificación en `narrative/facts.py`).
- **LibreOffice:** render PPTX→PDF/PNG para QA (`render.py`); no disponible en el navegador.
- No existe consulta en línea a GA4: `trafico` se carga como archivo.

### 2.7 Workflows de GitHub Actions
| Workflow | Disparador | Qué hace |
|---|---|---|
| `tests.yml` | `pull_request`, `push` a `main` | Python 3.12; `pip install -r requirements.txt`; **`python -m pytest tests/unit -q`** |
| `pages.yml` | `push` a `main`, manual | Empaqueta y publica el sitio estático |
| `pdf.yml` | `push` de `convertir/**.pptx`, manual | Convierte PPTX a PDF con LibreOffice y deja el PDF como artefacto |

---

## 3. Módulos críticos y dependencias

Dependencias internas calculadas por análisis estático de imports (`ast`) sobre `backend/app`:

| Módulo | Lo importan |
|---|---|
| `models` | 28 módulos (casi todo el backend: `build`, `calc/*`, `deck/*`, `importer/*`, `narrative/*`, `pipeline`, `raw/*`, `validator/*`, `web/service`, `history/store`, `cli`, `format`) |
| `narrative.rules` | `narrative.{aetops, executive, facts, glp1, glp1_exec, insights, targets, trends}` |
| `validator.rules` | `pipeline` |
| `raw.common` | `raw.glp1` |
| `raw.aetops` | `pipeline`, `web.service` |
| `raw.glp1` | `pipeline` |
| `narrative.glp1_exec` | `build`, `web.service` |
| `pipeline` | `build`, `cli`, `deck.aetops_mensual`, `deck.aetops_trimestral`, `narrative.aetops`, `narrative.executive`, `web.service` |
| `build` | `cli`, `web.service` |
| `web.service` | `web.app`, `web.bridge` |

**Lectura para las siguientes fases:** `models.py` es el módulo de mayor impacto (28 dependientes); cualquier cambio en `Finding` debe ser **solo aditivo** y conservar la firma posicional `(id, severity, message, evidence)`. `narrative.rules` concentra los supuestos heredados (25 %, 10 %) y alimenta 8 módulos: no se cambia su comportamiento.

---

## 4. Línea base de pruebas

### 4.1 Comando oficial y resultado
Comando oficial (de `tests.yml`): `python -m pytest tests/unit -q`.

| Dato | Valor |
|---|---|
| Comando ejecutado | `python3 -m pytest tests/unit -q -p no:cacheprovider --junitxml=…` sobre `6e1104d` |
| Inicio (según junit) | 2026-11-03T06:07:53Z |
| Total | **181** |
| Aprobadas | **181** |
| Fallidas | 0 |
| Con error | 0 |
| Omitidas | 0 |
| Tiempo | **526,63 s** (8 min 46 s) |
| Advertencias de pytest | 0 |
| Comparación con la línea base histórica | Coincide con `181 passed` sobre `c8ba722`; el resultado se **volvió a ejecutar**, no se asumió |

Notas: (a) la ejecución coincidió en parte con otras consultas de solo lectura (recolección de pruebas y la suite golden), por lo que el tiempo puede estar ligeramente inflado; (b) con 0 omitidas, esta ejecución **sí corrió** las pruebas que necesitan plantillas reales y LibreOffice, que en CI se omiten porque las plantillas no se versionan; (c) las 5 pruebas más lentas: `test_bridge::test_full_flow_without_render_for_both_units` (55 s), `test_discovery::…adds_one_slide[glp1]` (53 s), `test_raw_glp1::…sample_scale_and_defects` (32 s), `test_web::test_generate_from_raw_data` (31 s), `test_bridge::test_period_without_data…` (30 s).

### 4.2 Pruebas existentes
- `tests/unit`: 181 pruebas en 21 archivos (`test_aetops_4b`, `test_aetops_base`, `test_bridge`, `test_build_gate`, `test_build_site`, `test_discovery`, `test_executive`, `test_format`, `test_glp1`, `test_glp1_deck`, `test_glp1_exec`, `test_glp1_synthetic`, `test_history_trends`, `test_indicators`, `test_narrative_insights`, `test_pptx_ops`, `test_qa_sensitivity`, `test_raw_aetops`, `test_raw_glp1`, `test_targets`, `test_web`).
- `tests/golden`: 35 pruebas en 4 archivos; **todas omitidas** sin `REPORT_FIXTURES_DIR` (ejecución real: `35 skipped in 0.43s`).
- No hay pruebas de integración separadas: las de `test_bridge`, `test_web` y `test_discovery` recorren el flujo completo.

### 4.3 Pruebas especiales (según la especificación)
| ID | Qué es | Condición de ejecución | Estado en esta fase |
|---|---|---|---|
| **S-01** | Suite unitaria existente | Siempre | **Aprobada en la línea base**: 181/181 (evidencia previa a cualquier cambio de Fase 1; su aprobación para Fase 1 se vuelve a exigir en cada PR) |
| **S-02** | Suite golden existente (35) | `REPORT_FIXTURES_DIR` con plantillas y libros reales | **Omitida** (sin `REPORT_FIXTURES_DIR`); no se usaron datos reales ni se inventaron fixtures |
| **T-12** | QA visual con render real | `soffice` y `pdftoppm` en el PATH; se ejecuta en `visual-qa.yml` o `tools/visual_qa.py` | **No existe todavía** (pertenece a la fase 5). Las herramientas sí están presentes en este entorno |
| **P-00** | Captura de la línea base antes de cambiar código | Prerrequisito de toda otra prueba | **Realizada en esta fase** (§5) |

---

## 5. Mecanismo de línea base (P-00) y anti-regresión

### 5.1 Qué se agregó (solo archivos nuevos; no se tocó código existente)
| Archivo | Función |
|---|---|
| `tools/capture_baseline.py` | `--write` captura la foto; `--check` la compara y lista diferencias. Solo lee: ejecuta los pipelines existentes sobre `data/ejemplos` |
| `tests/regression/base/engine/*.json` | Foto del **motor** por escenario: valores `Decimal` exactos, tablas/bloques, productos, negados, embudo, extras, hallazgos (`id`, `severity`, mensaje, evidencia) y SHA-256 del libro. No necesita plantillas |
| `tests/regression/base/deck/*.json` | Foto del **PPTX generado** (sin render): SHA-256 del texto y la geometría de cada diapositiva, más la narrativa. Solo huellas: el texto estático de la plantilla puede contener marca y no se publica |
| `tests/regression/test_linea_base.py` | 13 pruebas: existencia de la foto; motor y hallazgos idénticos; `id`/`severity` conservados (`block|warn|info`); deck idéntico (se **omite con motivo** si la plantilla local no existe o tiene otro SHA-256) |

### 5.2 Escenarios cubiertos (machotes sintéticos versionados)
`aetops_mensual_2026-09`, `aetops_trimestral_2026-Q3`, `glp1_mensual_2026-09`, `glp1_trimestral_2026-Q3`. Datos: `data/ejemplos/AETOPS_crudo_ejemplo.xlsx` y `GLP1_crudo_ejemplo.xlsx` (inventados; sin datos reales).

### 5.3 Verificación del mecanismo
| Comprobación | Resultado |
|---|---|
| Determinismo: `--write` seguido de `--check` | Los 4 escenarios, capas `engine` y `deck`: **idénticos** |
| Sensibilidad: se alteró la `severity` de un hallazgo en una copia temporal | `--check` detectó **1 diferencia** (`/hallazgos[0]/severity`) |
| `python3 -m pytest tests/regression` | **13 passed** en 69,5 s (con plantillas locales presentes) |
| Tamaño de la foto | ≈ 1,3 MB (`engine` 1,3 MB; `deck` 64 KB) |

Cómo usarlo en las fases siguientes: `python tools/capture_baseline.py --check`. **Si falla, no se regenera la foto**: primero se justifica el cambio en `CAMBIOS_JUSTIFICADOS.md` (spec §11.6).

---

## 6. Incidencias y limitaciones detectadas

| ID | Descripción | Impacto | Tratamiento |
|---|---|---|---|
| INC-F1-01 | Las plantillas reales existen localmente pero **no están versionadas**: la capa `deck` de la línea base y varias pruebas de `tests/unit` solo se ejecutan donde estén | CI las omite; la capa `deck` no es verificable en CI | Documentado; la capa `engine` sí corre en CI; la capa `deck` se omite con motivo cuando falta la plantilla |
| INC-F1-02 | Python local 3.13.18 frente a 3.12 en CI y `Dockerfile` | Posibles diferencias no detectadas entre entornos | Documentado; no se cambió ningún entorno. Las pruebas pasaron en 3.13; en 3.12 no se ejecutaron en esta fase |
| INC-F1-03 | `tests/unit` tarda ≈ 9 min en este entorno | Retroalimentación lenta | Sin cambios; informativo |
| INC-F1-04 | La suite golden (35) no pudo ejecutarse: requiere archivos reales fuera del repositorio | Cobertura golden sin evidencia | Omitida con motivo; no se simuló ni se usaron datos reales |
| INC-F1-05 | `.github/workflows/tests.yml` solo ejecuta `tests/unit`; las pruebas de `tests/regression` no entran en CI | La capa `engine` no se vigila automáticamente | **No se modificó el workflow** (fuera del alcance acordado); se propone decidirlo con el resto del encargo |
| INC-F1-06 | El `Dockerfile` declara que no se verificó la construcción de la imagen | Fuera de alcance | Informativo |

Limitaciones de la línea base: usa solo machotes sintéticos (no evidencia operacional); la capa `deck` es huella de texto y geometría, **no** una comparación visual; no incluye render (T-12 no existe todavía).

---

## 7. Garantías de no regresión de esta fase

- **No se modificó ningún archivo existente.** Archivos agregados: `tools/capture_baseline.py`, `tests/regression/**` y este documento.
- No se tocaron `models.py`, `rules.py`, `raw/`, `glp1_exec.py`, `docs/CONTRATO_DATOS.md`, plantillas, perfiles, datos de ejemplo, workflows ni `severity`.
- No se agregaron dependencias.
- El resultado de `tests/unit` se registró **antes** de añadir los archivos nuevos (181/181); los archivos nuevos viven fuera de `tests/unit`.

---

## 8. Pruebas pendientes (de la especificación; no se ejecutaron en esta fase)

Todas las pruebas de Fase 1 de la especificación (T-01 a T-22, incluida T-10b) siguen **«Pendiente»**. En esta fase solo se establecieron: S-01 (línea base), P-00 y el mecanismo de comparación que servirá a T-13. T-12, S-02, V-01 y V-02 permanecen condicionales.

## 9. Parte no realizada: modelo técnico y configuración (sección 6 del encargo)

El texto del encargo termina en la sección 6, a mitad de frase («…No»). No se implementó el modelo de configuración. Hallazgos que condicionan su diseño, ya comprobados arriba:
1. Ya existe una arquitectura de configuración reutilizable: **perfiles YAML** (`profiles/`, `importer/profile.py`) y **dataclasses de umbrales** (`narrative/rules.py`).
2. `Finding` es un dataclass inmutable con 83 usos y firma posicional; la especificación (§4.2–4.3) pide **campos opcionales por palabra clave** y derivar `severity` de `efecto_generacion`.
3. Los archivos de configuración de la especificación (`reglas.json`, `definiciones.json`, `mapeo_columnas.json`, `validacion_registro.json`) no existen aún.

Se espera el resto del encargo para decidir qué se crea y bajo qué restricciones.
