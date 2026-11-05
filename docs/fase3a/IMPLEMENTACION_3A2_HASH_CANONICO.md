# Fase 3A · Subfase 3A-2 — Resultado canónico y `hash_resultado` (documentación técnica)

| | |
|---|---|
| Contrato que implementa | `docs/fase3a/ESPECIFICACION_FASE3A_PROCEDENCIA.md` §6 (`resultado_canonico/1`) |
| Código | `backend/app/provenance.py` (funciones puras, solo biblioteca estándar) |
| Pruebas | `tests/unit/test_provenance.py`, `tests/regression/test_hash_resultado.py` (+ `hash_resultado.json`), `tests/e2e/test_hash_pyodide.py` |
| Qué NO hace | No escribe `procedencia.json`, no crea la tabla `procedencia`, no toca `runs` ni `history/store.py`, no calcula estados de reproducibilidad, no se llama desde `build.py`, no ejecuta el motor de reglas, no cambia la interfaz. Eso es 3A-3 y 3A-4 |

## 1. Nombre y alcance: «hash de entradas» frente a `hash_resultado`

La especificación define esta subfase como **resultado canónico y `hash_resultado`** (§10 y §6): el hash cubre el **resultado final** del reporte, no los archivos de entrada en bruto. La **identidad de las entradas** está dentro de ese resultado como el bloque `fuentes` (SHA-256 de cada archivo cargado, sin su contenido ni su nombre). Se distinguen tres identidades que no se confunden:

| Identidad | Qué es | Dónde vive |
|---|---|---|
| De las entradas | SHA-256 de cada archivo fuente (cambia con el contenido, no con el nombre ni la ruta) | bloque `fuentes` del resultado canónico |
| Del resultado | `hash_resultado` = SHA-256 del resultado canónico | este módulo |
| Binaria del PPTX | SHA-256 de los bytes del `.pptx` | **no** se calcula ni se usa aquí (el PPTX nunca es una entrada; spec §3.5) |

No se modificó ningún contrato de la 3A-0.

## 2. Qué entra y qué no (spec §6.1 y §6.2)

| Bloque | Contenido | Fuente en el código existente |
|---|---|---|
| `periodo` | `unit`, `periodicity`, `year`, `index` | `models.Period` |
| `fuentes` | `[{"id": "F1", "sha256": …}]` ordenada por SHA-256 | lo aporta quien llama (nombre y SHA de los archivos cargados) |
| `valores` | `tables`, `products`, `negados`, `extras` (AETOPS) o `blocks`, `funnel`, `extras` (GLP-1), con `Value` y `Lineage` | `pipeline.Result` / `GlpResult` |
| `hallazgos` | `id`, `severity`, `message`, `evidence`, `tipo`, `gravedad`, `estado_verificacion`, `efecto_generacion`, `faltante`, `regla_id`, `regla_version` | `Result.findings` (`models.Finding`) |
| `narrativa` | por sección, los párrafos visibles finales: `texto`, `tipo`, `editado` | `FillReport.narrative` (después de ediciones y de ajustar a la lámina; incluye resumen ejecutivo, recomendaciones y descubrimientos) |

**Excluidos:** fechas y horas, zona horaria, rutas absolutas, `run_id`, versión del historial, SHA del PPTX/PDF, versiones de código y de entorno, nombres de archivo fuente, párrafos no visibles (`visible=False`, solo para `narrative.json`), y los campos de apoyo del párrafo (`priority`, `basis`, `evidence`, `nums`). Una prueba por cada exclusión demuestra que cambiarla no cambia el hash.

## 3. Algoritmo (spec §6.3) y detalle de la canonicalización

1. **Estructura:** misma semántica que `tools/capture_baseline.py::canon` (una prueba comprueba que `valores` es idéntico a esa canonicalización en los 4 escenarios de la línea base): `Decimal` → texto exacto, dataclass → objeto, enumeración → valor, conjuntos ordenados, claves con `str(k)`.
2. **Texto:** Unicode NFC (también en claves, incluidas las claves-tupla).
3. **Serialización:** JSON con claves ordenadas, `separators=(",", ":")`, `ensure_ascii=False`, `allow_nan=False`, UTF-8.
4. **Hash:** SHA-256 en hexadecimal minúscula de esos bytes. Campo del manifiesto: `{"algoritmo": "sha256", "contrato": "resultado_canonico/1", "valor": …}`.

### 3.1 Tratamiento de cada tipo de dato

| Dato | Tratamiento |
|---|---|
| `None` | `null`. Un campo con `None` es distinto de un campo ausente |
| Cadena vacía, `0`, `False`, lista vacía, objeto vacío | Seis valores distintos (probado) |
| Entero | Entero JSON. `1` ≠ `"1"` ≠ `True` ≠ `Decimal("1")` |
| `Decimal` | `str(Decimal)` exacto: `Decimal("1.0")` ≠ `Decimal("1.00")` (no se normalizan ceros finales; contrato §6.3) |
| `float` | `repr(float)`; no se esperan en los resultados (coincide con la línea base) |
| Booleano | `true` / `false` |
| Texto | NFC; en `Lineage` y en `Value.note`, `message` y `evidence` de hallazgos, las rutas absolutas pasan a su nombre base |
| Lista / tupla | Lista en el mismo orden (el orden cuenta) |
| Conjunto | Ordenado por su forma JSON (no depende del orden de iteración ni de `PYTHONHASHSEED`) |
| Objeto / diccionario | Claves con `str(k)` y NFC, ordenadas al serializar; **dos claves que dan la misma clave canónica son un error** |
| Dataclass | Todos sus campos; `Lineage.file` por el `id` de la fuente |
| `Path` | Su nombre base |
| Cualquier otro tipo (`datetime`, `bytes`, objetos…) | **Error** (`ErrorProcedencia`); no se cambia por un marcador que oculte datos |
| Profundidad mayor de 64 niveles o ciclos | **Error** |
| Texto no codificable en UTF-8 (sustituto suelto), `NaN` o enteros gigantes | **Error** al serializar |

### 3.2 Rutas absolutas (spec §6.4)

`rutas_a_nombre_base()` reemplaza por su nombre base: rutas de Windows con unidad (`C:\x\y.xlsx`, `C:/x/y.xlsx`), UNC (`\\servidor\recurso\y.xlsx`) y POSIX con al menos dos tramos (`/dir/y.xlsx`). No toca URLs (`https://…`), fracciones (`3/4`), fechas (`12/05/2026`), `y/o` ni tramos sueltos (`/s`). Se aplica **solo** a `Lineage`, `Value.note` y `message`/`evidence` de los hallazgos (lo que la spec indica), **no** a la narrativa: el texto del reporte se respeta tal cual.

### 3.3 Linaje y fuentes (spec §6.4)

`Lineage.file` se reemplaza por el `id` de la fuente cuando su nombre coincide con un archivo cargado; el valor vacío se conserva; un nombre que no está entre las fuentes queda con su nombre base (sin ruta). Los `id` (`F1`, `F2`…) se asignan por orden de SHA-256, no por orden de carga. Así renombrar o mover un archivo no cambia el hash y cambiar su contenido sí.

## 4. Vacíos de la especificación y cómo se resolvieron

Ninguno modifica un contrato de la 3A-0; son precisiones compatibles con ella (y con `narrative.json`, que ya existe).

| # | Vacío | Resolución |
|---|---|---|
| G-1 | «`texto`» ¿con o sin marcas de negrita `**`? | **Sin ellas**, igual que `texto` de `narrative.json` (`Para.plain`). Un cambio de solo formato (negritas) no cambia el hash; un cambio de palabras o de una coma, sí. Es la limitación de G-1 (ver §7) |
| G-2 | Dos archivos con el mismo contenido | Una sola fuente (misma identidad de entrada); el SHA se normaliza a minúsculas |
| G-3 | Un mismo nombre con contenido distinto | **Error**: no se puede asociar el linaje a una fuente |
| G-4 | `Lineage.file` que no coincide con ninguna fuente | Se conserva su nombre base (sin ruta) |
| G-5 | Tipos, profundidad o claves duplicadas no previstos | Error en lugar de un marcador (a diferencia de la línea base, que es solo una foto de comparación) |
| G-6 | Sección de narrativa sin párrafos visibles | Se conserva como lista vacía; una sección ausente es distinta de una vacía |
| G-7 | Forma de los párrafos | Objeto `Para` o entrada con forma de `narrative.json` (`texto`, `tipo`, `editado`, `visible_en_diapositiva`) |
| G-8 | El nombre del contrato dentro de los bytes hasheados | No se incluye: los bloques son exactamente los cinco de §6.1 (no se agregan campos por conveniencia) |
| G-9 | Qué pasa si el cálculo falla | `ErrorProcedencia`. El manejo (que el reporte se genere igual y `procedencia_error.json`) es de 3A-3 (spec §8.4) |

## 5. API

| Función | Qué hace |
|---|---|
| `canonico(periodo, fuentes, resultado, narrativa=None)` | Devuelve el resultado canónico (estructura JSON) sin modificar sus argumentos |
| `serializar(canon)` | Bytes UTF-8 que se entregan a SHA-256 |
| `hash_resultado(canon)` | `{"algoritmo", "contrato", "valor"}` (campo `hash_resultado` del manifiesto) |
| `calcular(...)` | `hash_resultado(canonico(...))` |
| `huellas_por_bloque(canon)` | SHA-256 de cada bloque: ayuda de auditoría para saber **qué bloque** cambió; no forma parte del contrato |
| `fuentes_canonicas(fuentes)` | `(lista con ids, mapa nombre→id)` |
| `rutas_a_nombre_base(texto)` | Normalización de rutas de §3.2 |

### Cómo se explica y se audita un hash
`canonico()` es la estructura exacta; `serializar()` son los bytes exactos; `huellas_por_bloque()` dice cuál de los cinco bloques cambió entre dos reportes. Una implementación independiente de §6.3 sobre la misma estructura obtiene el mismo SHA-256.

## 6. Integración con la arquitectura existente (sin segunda fuente de verdad)

* **Datos:** el módulo no guarda ni duplica nada: lee los mismos objetos que el sistema ya produce (`Result`, `FillReport.narrative`, los SHA-256 que ya calcula el historial para las fuentes).
* **`capture_baseline.py`:** su canonicalización es la referencia de `valores`; no se modificó. No se reutiliza su código porque `tools/` no viaja en `app.zip` (el navegador no podría importarlo); la equivalencia se prueba en los 4 escenarios.
* **`Lineage`:** se reutiliza tal cual; solo su `file` se reemplaza por el `id` al serializar.
* **`history/store.py`:** sin cambios. Una prueba verifica que no existe la tabla `procedencia` y que las columnas de `runs` son las mismas.
* **`build.py` / interfaz:** sin cambios. En 3A-3, `build.py` llamará a `calcular(period, fuentes, result, fill.narrative)` después de guardar el PPTX; para que el linaje coincida con los ids, **los nombres de `fuentes` deben ser los mismos que ve `Lineage.file`** (el nombre base del archivo cargado).

## 7. Compatibilidad con reportes históricos y limitaciones

* Los reportes anteriores guardaron hallazgos y narrativa como JSON, sin objetos `Value` ni `Lineage`: **no se pueden hashear** y el sistema no inventa un hash (se rechazan con `ErrorProcedencia`); quedan como `no_reproducible (legado)` (AC-12, 3A-4). Los resultados históricos y la línea base no cambian.
* **Cambio de solo formato (negritas):** no cambia el hash (G-1). Es una limitación aceptada del contrato `texto`.
* **`Decimal` sin normalizar:** dos corridas con distinta cantidad de ceros finales darían hashes distintos; hoy el motor es determinista y las 4 referencias son estables.
* **Saltos de línea y espacios del texto:** se respetan tal cual (`a\nb` ≠ `a\r\nb`).
* **Entrada inválida:** siempre error, nunca un hash aproximado; que un fallo no impida el reporte lo resuelve 3A-3.
* El hash congelado de los 4 escenarios (`tests/regression/hash_resultado.json`) no incluye narrativa de plantilla (esa parte se prueba en local con las plantillas reales).

## 8. Pruebas y evidencia

| Prueba | Qué demuestra | Dónde corre |
|---|---|---|
| `tests/unit/test_provenance.py` (106) | Determinismo (orden de claves, de fuentes, directorio, otro proceso con otras semillas de hash), sensibilidad por cada campo del hallazgo, valor, linaje, nota, párrafo (una coma), fuente (contenido) y periodo; exclusiones y normalizaciones (nombre y ruta del archivo, rutas Windows/POSIX/UNC, NFC en textos y claves, párrafos no visibles); robustez (None, ausente, vacío, enteros, decimales, booleanos, listas y objetos anidados, Unicode y caracteres de control, entradas grandes); entradas inválidas; que no altera sus entradas; pureza del módulo | CI y local |
| `tests/regression/test_hash_resultado.py` (21) | `valores` idéntico a `capture_baseline.canon` en los 4 escenarios; hash congelado de los 4 escenarios (Python 3.12 en CI y 3.13 local); independencia de directorio y nombre de archivo; sensibilidad al contenido de la fuente (solo cambia el bloque `fuentes`); otro proceso y otras semillas de hash; edición de un párrafo; sin tabla `procedencia` ni cambios en `runs`; **flujo real de generación** (AETOPS y GLP-1 con `build_aetops`/`build_glp1`: hash reproducible desde otra carpeta y con otro nombre de archivo, que calcular no altera el PPTX ni la narrativa, y que un texto editado a mano cambia el hash) | CI (sin plantillas) y local (con plantillas) |
| `tests/e2e/test_hash_pyodide.py` (1) | El hash de los 4 escenarios dentro de Pyodide (emscripten) con el `app.zip` de `build_site.py` es el mismo que en CPython | Local (omitida con motivo si falta Pyodide) |

### Cómo actualizar el hash congelado
Solo si el motor o el contrato cambian de forma legítima (spec §4.1): regenerar la línea base justificada, subir `ENGINE_VERSION` y ejecutar `python tests/regression/test_hash_resultado.py --actualizar`; la diferencia se revisa en el PR. La prueba indica qué bloque cambió.
