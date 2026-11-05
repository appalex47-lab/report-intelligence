# Configuración de Fase 1 (modelo y línea base)

Código: `backend/app/config/` · Especificación: `docs/fase1/ESPECIFICACION_FASE1_REPORT_INTELLIGENCE_FINAL.md` (§3.1, §3.3, §4, §5, §9, §10).
**Estado: estructura, contratos y validación estructural. Ninguna regla, escenario ni indicador consume estos archivos todavía; el motor actual no los lee.**

## 1. Decisión de arquitectura
| Pregunta | Respuesta (comprobada en el repositorio) |
|---|---|
| ¿Ya existía configuración como dato? | Sí: `profiles/*.yaml` (perfiles de importación, `importer/profile.py`) y `narrative/rules.py` (umbrales como dataclass). Sin sistema equivalente para definiciones, parámetros de reglas, alias de columnas ni registro de validación |
| ¿Se creó un segundo sistema? | No. Se sigue el mismo patrón (datos separados del código) con JSON, que es lo que fija la especificación, y **sin dependencias nuevas** (`json` de la biblioteca estándar) |
| ¿Es compatible la ruta `config/…` de la especificación? | Sí, como `backend/app/config/`. `tools/build_site.py` empaqueta todo `backend/` salvo `__pycache__`/`.pyc`, así que los JSON viajan a Pyodide sin tocar la compilación (comprobado por prueba) |
| ¿Se duplican valores existentes? | Los heredados 25 % y 10 % y el umbral 20 % ya viven en código. Se **registran** en `reglas.json` con su `fuente_codigo`, y una prueba verifica que coincidan con el código para evitar deriva. Cuando una fase posterior haga que el código lea el JSON, el código dejará de tener el literal |

## 2. Principios aplicados
Nada se convierte en regla universal (cada definición y parámetro lleva `validacion_operacional`); versionado (`esquema` + `version` SemVer por archivo y por definición); parámetros fuera del código; lo no configurado es `null` con `origen: no_configurado`; ningún valor inventado (el validador **rechaza** un valor en un parámetro `no_configurado`); `origen` distingue `heredado`/`nuevo`; los números se leen como `Decimal` exacto; la ausencia no es cero (`null`, nunca `0`).

## 3. Archivos y campos
Todos tienen `esquema` (p. ej. `reglas/1`) y `version` (`MAJOR.MINOR.PATCH`). Validación: `config.validar(nombre, datos)` devuelve la lista de errores (vacía = válido); `config.validar_todo()` valida los cuatro.

### 3.1 `definiciones.json` — catálogo de definiciones
Contenido: las 9 definiciones **ya documentadas** en la especificación (§3.1 y §8.2): visita/sesión, evento, usuario, carritos agregados, pedido del sistema de ventas, compra GA4, paciente, carritos abandonados (métrica heredada) y relación pedidos/carritos (IND-01). No se añadió ninguna definición nueva.

| Campo | Tipo | Notas |
|---|---|---|
| `id` | texto, único | Duplicado ⇒ error |
| `nombre`, `descripcion` | texto | |
| `version` | SemVer | Versión de la definición |
| `tipo` | `entidad` \| `metrica` \| `indicador` | |
| `unidad` | texto \| `null` | `null` = unidad no declarada (p. ej. carritos agregados) |
| `fuente` | `{hoja, columna}` \| lista \| `null` | Solo columnas que existen en los machotes (prueba) |
| `granularidad` | texto | |
| `aplicabilidad` | `{unidades: [GLP1\|AETOPS…], condicion}` | Las definiciones de tráfico solo aplican a GLP-1 (AETOPS no tiene `trafico`) |
| `limitaciones` | lista de textos | |
| `origen` | `heredado` \| `nuevo` | |
| `validacion_operacional` | `no_validada_con_datos_reales` \| `confirmada` \| `no_aplica` | Hoy todas `no_validada…` |
| `referencia` | texto | Sección de la especificación o del contrato |

Evolución sin tocar código: cambiar una descripción o limitación solo exige editar el JSON y subir su `version`.

### 3.2 `reglas.json` — parámetros de reglas y escenarios
| Sección | Contenido |
|---|---|
| `flags` | Exactamente: `validacion_fase1`, `relacion_pedidos_carritos`, `anexo_calidad`, `qa_pptx_exportado`, `escenarios_estrictos`. Todos `false`; nada los lee aún |
| `parametros.<nombre>` | `{valor, origen, referencia, validacion_operacional[, fuente_codigo, nota]}` |
| `dimensiones.<id>` | `{entidad, exclusiva, exhaustiva, justificacion}`; vacío hoy. `null` en exclusiva/exhaustiva = sin declarar; declararlas exige justificación |

Parámetros hoy: heredados — `e1_recuperacion_negados_medio` 0.25, `e2_recuperacion_abandono_medio` 0.10, `umbral_conciliacion_compras` 0.2; nuevos (de la especificación) — `max_pacientes_por_pedido` 1, `tolerancia_conteo` 0, `tolerancia_monto_fraccion` 0.005, `unidad_carritos` `"no_declarada"`; **no configurados (`null`)** — conservador/optimista de E1 y E2, `estatus_excluidos`, `cobertura_minima_paciente`, `fuente_pedidos`, `filtro_canal_relacion`.

#### Catálogo de reglas (`reglas.json` → `reglas`, versión 1.1.0 del archivo; Fase 2A)
Cada regla es un dato: `id`, `nombre`, `descripcion`, `version`, `tipo`, `gravedad` (`null`), `unidades`, `columnas_requeridas`, `parametros` (nombres que deben existir en `parametros`), `activacion` (`flag` y `condicion`), `severidad` (por estado), `severidad_codigos` (excepciones por `codigo.estado`), `evidencia` (qué evidencia produce), `mensajes` (`codigo.estado` → texto con `{marcadores}`) y, según la regla, `dimensiones_candidatas`, `entidades`, `hipotesis`. `config.validar("reglas", …)` comprueba estructura y referencias cruzadas. Los marcadores de cada mensaje los llena la función de la regla; ver `docs/MOTOR_REGLAS.md`.

### 3.3 `mapeo_columnas.json` — alias de columnas
`unidades.<GLP1|AETOPS>.hojas.<hoja>.alias.<columna_canónica> = [alias…]`. Hoy **todos vacíos**: no se declara ningún alias; los nombres canónicos son los del contrato. AETOPS no tiene `trafico`. El validador rechaza cualquier alias o columna relacionada con carrito, transacción o sesión (AC-23).

### 3.4 `validacion_registro.json` — validación por regla
Una entrada por regla (`R-REL-PAC-PED`, `R-CUADRE-DIM`, `R-CONC-COMPRAS`, `R-DENOM`, `R-COBERTURA-ATC`): `regla_id`, `regla_version` (`null`: las reglas aún no existen), `validacion_sintetica` (`pendiente`|`aprobada`|`fallida`|`no_aplica`), `validacion_operacional`, `extracto_id`, `fecha`, `confirmado_por`, `parametros_confirmados`. La validación sintética y la operacional son campos separados. `confirmada` exige `extracto_id`, `fecha`, `confirmado_por` y `regla_version`; `aprobada` exige `regla_version`.

## 4. Versionamiento
| Qué | Estado |
|---|---|
| Ya existía | `Profile.version` (perfiles), carpeta de versión de plantillas (`templates/<formato>/<n>/`), `runs.version` en el historial |
| Preparado en esta fase | `MODELO_HALLAZGOS_VERSION` (`models.py`); versión de cada JSON (`config.versiones()`); `version.versiones()` que las reúne |
| **No** preparado (a propósito) | `APP_VERSION` y `ENGINE_VERSION`: la especificación los estampa al compilar el sitio (`tools/build_site.py`, fase 3). `version.versiones()` devuelve `None` para ambos. No se tocaron workflows ni la compilación, ni se publicaron releases |

## 5. Fixtures sintéticas
`tools/make_fixtures_fase1.py` → `tests/fixtures/fase1/`: `hallazgos_compat.json`, cinco catálogos (uno válido y cuatro inválidos) y `manifest.json`.
- Semilla fija (`20260601`); una `Random` por archivo derivada de la semilla y del nombre (determinista entre ejecuciones y versiones de Python).
- Cada archivo lleva `sintetico: true`; el manifiesto lista archivo, `sha256`, `bytes`.
- Solo escribe dentro de `tests/fixtures/fase1/` (aborta si se le pide otro destino); no lee archivos de datos; los identificadores llevan prefijo `SINT`.
- `tests/fixtures/` (directorio) convive con `tests/fixtures.py` (módulo): `from tests.fixtures import build_base` sigue funcionando porque el módulo tiene prioridad sobre un directorio sin `__init__.py` (comprobado con la suite).
- Estas fixtures cubren solo el **modelo y el catálogo**. Las fixtures funcionales de las reglas pertenecen a fases posteriores.

## 6. Campos reservados para fases posteriores
`flags.*`, `parametros.*` salvo los heredados, `dimensiones`, `mapeo_columnas.alias`, `validacion_registro.reglas[*].regla_version/extracto_id/fecha/confirmado_por/parametros_confirmados`, `Finding.tipo/gravedad/estado_verificacion/faltante/regla_id/regla_version`.

## 7. Cómo reproducir
```bash
python -m pytest tests/unit/test_hallazgo_compat.py tests/unit/test_config_fase1.py tests/unit/test_fixtures_fase1.py -q
python tools/make_fixtures_fase1.py --check
python tools/capture_baseline.py --check
python -m pytest tests/unit -q          # suite completa (≈ 9 min)
python -m pytest tests/regression -q
```
