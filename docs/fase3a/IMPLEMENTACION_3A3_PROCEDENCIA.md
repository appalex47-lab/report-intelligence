# Fase 3A-3 · Manifiesto de procedencia, tabla autoritativa y verificación

| | |
|---|---|
| Especificación | `ESPECIFICACION_FASE3A_PROCEDENCIA.md` (§3 estados, §5 esquema, §7 persistencia, §8.4 errores) |
| Depende de | 3A-1 (versiones y commit), 3A-2 (`hash_resultado`, contrato `resultado_canonico/1`, **sin cambios**) |
| Estado | Implementada; PR independiente **sin fusionar**. No declara completa la reproducibilidad (ver §9) |
| Fuera de alcance | Interfaz y botones, conexión del motor de reglas, comparación por regeneración (3A-4), `release.yml` (3A-5), Fase 3B |

## 1. Qué hace

Cada reporte generado deja ahora, **después** de guardar el PPTX y la corrida del historial:

1. una fila **autoritativa e inmutable** en la tabla `procedencia` del historial (los bytes exactos del manifiesto);
2. una **copia verificable** `procedencia.json` en la carpeta del reporte, byte a byte idéntica a la fila;
3. si algo falla, `procedencia_error.json` (y el reporte se genera igual). Nunca queda un manifiesto incompleto.

Además hay funciones de **solo lectura** para verificar el registro y su copia, comparar las fuentes aportadas con las registradas y re-exportar la copia perdida.

## 2. Arquitectura

```
build_aetops / build_glp1
   │  (1) PPTX, qa_report, manifest.json   ← sin cambios
   │  (2) _record → runs/sources/kpis      ← sin cambios (contrato `runs` intacto)
   └─ (3) _procedencia()  ──►  provenance_capture.ejecutar()   [nunca lanza]
                                  ├─ construir():  entradas → canónico (3A-2) → manifiesto → serialización
                                  ├─ history.store.record_procedencia()   (tabla autoritativa, su propia transacción)
                                  └─ escribir_atomico(procedencia.json)    (copia)
provenance_verify.verificar / comparar_fuentes / reexportar_copia   [solo lectura salvo la copia]
```

| Módulo | Responsabilidad |
|---|---|
| `provenance.py` (funciones nuevas) | `validar_manifiesto`, `construir_manifiesto`, `serializar_manifiesto`, `leer_manifiesto`: puras, esquema cerrado, sin E/S |
| `provenance_capture.py` | Lee entradas (huella de fuentes y plantilla, entorno, configuración, versión de reglas), orquesta, escribe de forma atómica, registra errores |
| `provenance_verify.py` | Distingue integridad, disponibilidad de fuentes y reproducibilidad |
| `history/store.py` | Tabla `procedencia`, triggers, `record_procedencia`, `get_procedencia`, `buscar_procedencia_por_sha` |
| `build.py` | Llamada aditiva `_procedencia(...)` y campo `BuildResult.procedencia`; parámetro opcional `ia` |
| `web/service.py` | Declara el uso de IA (`_ia_info`) y permite descargar `procedencia.json` / `procedencia_error.json` |

Decisiones de diseño:

* **Primero la tabla, luego la copia.** La fila es la fuente de verdad; si la copia falla, el estado es `registrada_sin_copia` y se puede re-exportar. Al revés (copia primero) una copia podría quedar sin registro.
* **La tabla no se actualiza ni se borra** (triggers), igual que `runs`, `sources` y `kpis`. `runs` no se modifica: la procedencia es una tabla aparte que referencia `runs(id)`.
* **El hash de resultado es el de 3A-2**, calculado en el mismo flujo con las fuentes reales y la narrativa final. El manifiesto lo copia; no lo recalcula con otro contrato.
* **El manifiesto no contiene** valores de celdas, texto del contexto (solo líneas y SHA-256), claves, rutas absolutas ni texto enviado a la IA (solo `usada` y `modelo_declarado`).
* **Fallo de procedencia ≠ fallo de reporte** (D-A). `ejecutar` captura toda excepción; `build._procedencia` captura incluso un fallo imprevisto de la propia llamada.

## 3. Esquema de almacenamiento

```sql
CREATE TABLE IF NOT EXISTS procedencia(
  run_id INTEGER PRIMARY KEY REFERENCES runs(id),
  esquema TEXT NOT NULL,
  manifiesto TEXT NOT NULL,                       -- bytes UTF-8 exactos de procedencia.json
  manifiesto_sha256 TEXT NOT NULL CHECK(length(manifiesto_sha256) = 64),
  hash_resultado TEXT NOT NULL CHECK(length(hash_resultado) = 64));
CREATE INDEX IF NOT EXISTS procedencia_sha ON procedencia(manifiesto_sha256);
-- triggers: procedencia_run_existe (BEFORE INSERT), procedencia_no_update, procedencia_no_delete
```

* `connect()` ejecuta el esquema con `IF NOT EXISTS`: un historial anterior abre **sin migración** y recibe la tabla vacía. Sin `json_valid` (portabilidad a Pyodide).
* SQLite no aplica claves foráneas por omisión: la existencia de la corrida la impone el trigger.
* `record_procedencia` valida el manifiesto antes de insertar, calcula el SHA-256 **de los bytes** (no acepta uno externo), y se confirma en su propia transacción (`commit`; `rollback` ante cualquier error).
* Idempotencia: mismos bytes → `ya_registrada`; bytes distintos → `ProcedenciaExistente` (nunca sustituye). Una carrera entre conexiones se resuelve releyendo la fila.

## 4. Estructura del manifiesto (`procedencia/1`)

Esquema cerrado (campos extra o ausentes se rechazan); JSON con claves ordenadas, NFC, sangría de 1 espacio, `\n` final, sin `NaN`/`Infinity`, máximo 2 000 000 bytes.

| Campo | Contenido |
|---|---|
| `esquema` | `procedencia/1` |
| `version_codigo` | `app`, `commit` (40 hex, con `+dirty` o `desconocido`) |
| `version_motor` | `engine` |
| `version_definiciones` | archivo y versión |
| `version_reglas` | versión del catálogo, reglas con versión y validación, y `ejecucion` (`motor_ejecutado: false`, `resultados_incluidos: false`, nota) — son metadatos, no resultados |
| `version_plantillas` | `id` (`formato/versión`), nombre y SHA-256 |
| `archivos_fuente` | por fuente: `id` (F1…, por orden de SHA como en el hash), nombre base, tamaño, SHA-256, filas por hoja, columnas, periodo detectado |
| `fecha_generacion` | `utc` y `zona_horaria` (puede ser `null`) |
| `configuracion` | metas, umbrales, escenarios, contexto (líneas + SHA-256), `ia` (`usada`: `true`/`false`/`null` = no declarado) |
| `hash_resultado` | `algoritmo`, `contrato`, `valor` (3A-2) |
| `entorno` | Pyodide, Python, python-pptx (diagnóstico; **fuera del hash**) |

## 5. Procedimiento de captura

`ejecutar(...)` → diccionario con `estado`, `etapa`, `run_id`, `hash_resultado`, `manifiesto_sha256`, `archivo`, `registro`, `error`, `archivo_error`.

| Estado | Significado |
|---|---|
| `registrada` | fila + copia (con historial) |
| `copia_sin_registro` | sin historial: solo `procedencia.json`; la verificación lo topa en `parcial` (D-B) |
| `registrada_sin_copia` | fila escrita, copia fallida; `procedencia_error.json` explica la etapa; recuperable |
| `error` | no hay fila ni copia; `procedencia_error.json` si pudo escribirse |

Al empezar se retiran `procedencia.json` y `procedencia_error.json` de una generación anterior en esa carpeta. Etapas de error: `entradas`, `canonico`, `manifiesto`, `serializacion`, `historial`, `archivo`.

## 6. Procedimiento de verificación y recuperación

`verificar(origen, run_id, carpeta=None)` (solo lectura; la base se abre `mode=ro` y no se crea ni migra nada):

| Registro | Copia | Integridad | Reproducibilidad |
|---|---|---|---|
| presente e íntegro | íntegra / ausente / alterada | `verificada` | `no_evaluada` (requiere 3A-4) |
| corrupto, esquema no soportado, ilegible | cualquiera | `fallida` | `no_reproducible` |
| ausente | válida (`sin_registro`) | `no_verificable` | `no_evaluada`, tope `parcial` |
| ausente | inválida / ilegible | `fallida` | `no_reproducible` |
| ausente | ausente (con `procedencia_error.json`) | `ausente` | `no_reproducible` (error al generarla) |
| ausente | ausente (sin error) | `ausente` | `no_reproducible` (legado) |

Una copia alterada **se informa pero nunca sustituye** al registro. Perder o cambiar las fuentes **no** afecta la integridad (`comparar_fuentes` devuelve `disponible` / `modificada` / `ausente` por fuente: es disponibilidad, no un estado de reproducibilidad).

Recuperación: `reexportar_copia` escribe en `procedencia.json` los bytes exactos del registro íntegro (`creada` / `sin_cambios` / `sustituida`); no sobrescribe una copia distinta salvo `sustituir_alterada=True`, y no exporta un registro corrupto.

## 7. Errores y su tratamiento (spec §8.4)

| Falla | Resultado |
|---|---|
| Fuente/plantilla inexistente, directorio, libro corrupto | `error` en `entradas`; reporte intacto |
| Linaje ambiguo (mismo nombre, distinto contenido) u otro fallo de 3A-2 | `error` en `canonico` |
| Manifiesto inválido / no serializable | `error` en `manifiesto` / `serializacion` |
| Historial lleno, bloqueado, solo lectura, corrida inexistente, hay historial pero se desconoce la corrida | `error` en `historial`; rollback; sin copia |
| Falla al escribir la copia | `registrada_sin_copia` en `archivo` |
| Falla al escribir hasta `procedencia_error.json` | `archivo_error: null` y el mensaje va en la salida (E-7) |
| Re-captura de la misma corrida con bytes distintos | `error` en `historial`; el registro original **no cambia**; la copia previa se retira y puede re-exportarse |

Los mensajes se normalizan (rutas a nombre base, NFC, máximo 500 caracteres). Los archivos temporales se crean en la misma carpeta (`.nombre.*.tmp`) y siempre se borran.

## 8. Compatibilidad histórica

* Reportes y corridas anteriores a 3A-3 **no se modifican ni se inventa su procedencia**: se verifican como `ausente` / `no_reproducible (legado)`.
* El hash 3A-2 de los cuatro escenarios de la línea base es idéntico al congelado (`tests/regression/hash_resultado.json`); el digest del motor y `APP_VERSION`/`ENGINE_VERSION` no cambian.
* Un historial `.sqlite` importado desde una versión anterior abre sin migración.

## 9. Estados y limitaciones

* **Reproducibilidad.** Este PR **solo** determina las condiciones negativas que la spec fija con la integridad. `exacta` y `parcial` (por regeneración y comparación real) pertenecen a 3A-4; hoy el máximo es `no_evaluada`.
* Integridad del registro ≠ reproducibilidad del reporte: un manifiesto íntegro de un reporte cuya fuente se perdió es íntegro y no reproducible en la práctica.
* La integridad protege contra alteraciones **accidentales y detectables** (SHA-256 de los bytes y triggers); quien controle el archivo `.sqlite` puede reescribirlo entero. No hay firma criptográfica (fuera de alcance).
* El campo `zona_horaria` y `pyodide` solo son reales dentro del navegador; en CPython pueden ser `null` / `desconocido`.
* `ia.usada` solo refleja lo que el servicio sabe (`ia_log.json` o hoja de descubrimiento validada); `null` = no declarado.
* El motor de reglas no se ejecuta ni se conecta (H-4).

## 10. Pruebas

| Archivo | Cubre |
|---|---|
| `tests/unit/test_procedencia_manifiesto.py` | esquema cerrado, validación, serialización determinista, lectura hostil (tamaño, profundidad, claves repetidas, NaN, no UTF-8) |
| `tests/unit/test_procedencia_historial.py` | tabla e índice, historial anterior, inmutabilidad, idempotencia, conflicto, restricciones, fallos inducidos (disco lleno, E/S, solo lectura, bloqueo), concurrencia, `runs` intacto |
| `tests/unit/test_procedencia_captura.py` | flujo con/sin historial, varias fuentes, duplicados, ambigüedad, IA tri-estado, contexto, fallo inducido en cada etapa, escritura atómica, nombres hostiles, sin fugas de rutas |
| `tests/unit/test_procedencia_verificacion.py` | todas las filas de la tabla de §6, solo lectura, `comparar_fuentes`, `reexportar_copia` |
| `tests/unit/test_procedencia_servicio.py` | `_ia_info`, lista blanca de descargas, generación por la API (si hay plantilla y LibreOffice) |
| `tests/regression/test_procedencia_flujo.py` | motor real → hash → captura → fila → copia → verificación → recuperación en los 4 escenarios (apto para CI); hash = congelado de 3A-2; coherencia con `sources`/`runs` |
| `tests/regression/test_procedencia_build.py` | `build_*` real: PPTX, narrativa, QA y `manifest.json` idénticos con y sin procedencia (requiere plantillas locales) |
| `tests/e2e/test_descarga_pptx.py` | en el navegador con Pyodide real: la procedencia generada es válida y coincide con la fila del historial exportado |

Los resultados de la ejecución están en el informe del PR.

## 11. Riesgos residuales

1. Una re-captura de la misma corrida con otros bytes retira la copia previa aunque el registro siga íntegro (se recupera con `reexportar_copia`). Es un caso que el flujo normal no produce (cada generación crea una corrida nueva).
2. Las pruebas que usan plantillas reales o LibreOffice solo corren localmente; CI cubre el motor, el flujo con plantilla ficticia y el hash en Pyodide. La prueba del navegador con `sqlite3` en Pyodide solo corre donde hay una distribución completa de Pyodide.
3. Sin firma: ver §9.
4. Costo medido: ≈ 120 ms y ≈ 3,5 kB por reporte de ejemplo.
