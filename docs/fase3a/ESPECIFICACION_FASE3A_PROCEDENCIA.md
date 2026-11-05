# Report Intelligence — Fase 3A · Procedencia y reproducibilidad
## Subfase 3A-0: especificación definitiva (solo documentación)

| | |
|---|---|
| Estado | **Propuesta para autorización.** No hay código de la Fase 3A. Nada de este documento está implementado |
| Punto de partida | `main` con los PR #11 a #14 fusionados; `ENGINE`/`APP` aún sin versión (`backend/app/version.py` devuelve `None`) |
| Fuente que desarrolla | `docs/fase1/ESPECIFICACION_FASE1_REPORT_INTELLIGENCE_FINAL.md` §5 (procedencia), §9 (archivos), §11 (T-07, T-08, T-16, V-02), §12 (AC-10, AC-11, AC-12, AC-28) |
| Relación con la especificación original | Este documento es una **adenda**. No modifica la especificación original; cada diferencia está listada en §2 |
| Decisiones del usuario incorporadas | H-1 a H-8 y los puntos 9 a 12 de la instrucción de 3A-0 |

**Fuera de alcance (expreso):** Fase 3B (linaje y auditoría del reporte), Fase 4, Fase 5, interfaz (`frontend/`), conexión o ejecución del motor de reglas, `release.yml`, etiquetas y releases (A-5 sin autorización), cambios en fórmulas, cifras, plantillas o láminas.

---

## 1. Decisiones y supuestos

### 1.1 Decisiones aprobadas

| ID | Decisión | Dónde se concreta |
|---|---|---|
| H-1 | `procedencia.json` junto al reporte **y** una tabla independiente en el historial, con una única fuente de verdad | §7 |
| H-2 | `APP_VERSION` y `ENGINE_VERSION` en SemVer, con el SHA del commit; reglas de incremento y línea base explícitas | §4 |
| H-3 | Los párrafos editados a mano forman parte del resultado canónico y cambian el hash | §6 |
| H-4 | Se registra expresamente que el motor de reglas **no** se ejecutó; la versión del catálogo se registra como metadato | §2, §5 |
| H-5 | Versiones de Pyodide, Python y python-pptx como información de entorno, **fuera** del hash | §3.4, §5 |
| H-6 | A-5 sin autorización: no se crea `release.yml`, etiquetas ni publicaciones | §10 (3A-5 diferida) |
| H-7 | La Fase 3B no se diseña ni implementa | §0 |
| H-8 | La interfaz queda fuera de 3A | §8, §13 (L-1) |

### 1.2 Supuestos (declarados, no verificados todavía)

| ID | Supuesto | Cómo se verifica |
|---|---|---|
| S-1 | En Pyodide, `pyodide.__version__`, `sys.version` y `pptx.__version__` son legibles desde Python, y la zona horaria con `js.Intl.DateTimeFormat().resolvedOptions().timeZone`. Así **no** hace falta tocar `worker.js` | En 3A-3, con la infraestructura de `tools/pyodide_node_check.mjs` y la E2E de `tests/e2e/` |
| S-2 | «Filas, columnas detectadas y periodo detectado» de cada archivo fuente se obtienen leyendo el libro con `openpyxl` en modo solo lectura, sin tocar los importadores (protegidos). No se guarda ningún contenido de celdas | En 3A-3: prueba de que el manifiesto no contiene valores de celdas |
| S-3 | Un fallo al construir la procedencia **no** debe impedir generar el reporte (principio 2, «sin regresiones») | Prueba en 3A-3 (ver D-A) |
| S-4 | `Lineage.file` es el nombre base del archivo (comprobado: `libro_x.xlsx`, sin ruta) | Prueba de dos directorios distintos en 3A-2 |

### 1.3 Puntos que esta especificación propone y que necesitan tu confirmación expresa

| ID | Propuesta | Alternativa |
|---|---|---|
| D-A | Si falla la procedencia: el reporte se genera igual y el error se guarda en `procedencia_error.json` (no en `qa_report.json` ni en `manifest.json`) | Bloquear la generación (más estricto, riesgo de regresión) |
| D-B | `exacta` exige integridad verificada contra el historial; un `procedencia.json` suelto, sin registro, llega como máximo a `parcial` (§3.3) | Permitir `exacta` solo con el archivo |
| D-C | `APP_VERSION` y `ENGINE_VERSION` empiezan en **`1.0.0`** en 3A-1 | Otro valor inicial (p. ej. `0.1.0`) |
| D-D | `procedencia.json` queda disponible en el directorio del reporte y en el historial, pero **sin botón de descarga** (la interfaz está fuera de 3A) | Permitir un cambio mínimo en `frontend/` |

---

## 2. Adenda al §5.1 de la especificación original

La especificación original define **nueve** campos. Se conservan los nueve, con sus nombres exactos. No se renombra ni se elimina ninguno.

| Campo original (§5.1) | Esquema definitivo | Cambio |
|---|---|---|
| `version_codigo` | igual: versión de la app + SHA del commit | ninguno |
| `version_motor` | igual: `ENGINE_VERSION` | ninguno |
| `version_definiciones` | igual: versión de `definiciones.json` | ninguno |
| `version_reglas` | igual (versión global y por `regla_id` con su estado de validación) **más** un subobjeto `ejecucion` | **ampliado por dentro**: ahí vive el registro de «motor no ejecutado» (H-4) |
| `version_plantillas` | igual | ninguno |
| `archivos_fuente` | igual, con un `id` por archivo (§6) | campo `id` agregado dentro de cada elemento |
| `fecha_generacion` | igual | ninguno |
| `configuracion` | igual | ninguno |
| `hash_resultado` | igual | ninguno |

**Discrepancia resuelta:** `reglas_ejecutadas` **no** se añade como décimo campo de primer nivel. Se registra como `version_reglas.ejecucion.motor_ejecutado`. Con esto el manifiesto sigue teniendo los nueve campos de la especificación.

**Adiciones de primer nivel (no están en la especificación original y quedan registradas aquí como cambio justificado):**

| Campo nuevo | Motivo | Origen de la decisión |
|---|---|---|
| `esquema` (`"procedencia/1"`) | Permitir leer manifiestos futuros sin ambigüedad | Necesidad técnica de versionar el formato |
| `entorno` | Pyodide, Python y python-pptx como información, fuera del hash | H-5 (decisión del usuario) |

Estas dos adiciones, y el subobjeto `ejecucion`, requieren tu aprobación explícita de este documento. AC-10 se redacta en §11 como «los nueve campos de §5.1 presentes», más los dos campos aditivos.

---

## 3. Procedencia, integridad y reproducibilidad

Tres conceptos distintos, con evidencia distinta:

| Concepto | Pregunta que responde | Evidencia | Qué NO prueba |
|---|---|---|---|
| **Procedencia** | ¿De qué se produjo este reporte? | El manifiesto: versiones, SHA-256 de plantilla y de fuentes, configuración | Que el manifiesto no haya sido alterado ni que el resultado se pueda rehacer |
| **Integridad** | ¿El registro es el que se escribió, sin alteraciones? | `manifiesto_sha256` guardado en el historial (inmutable) frente al SHA-256 de los bytes de `procedencia.json` | Que el contenido sea correcto, solo que no cambió |
| **Reproducibilidad** | ¿Al regenerar se obtiene el mismo resultado canónico? | Regenerar con las mismas entradas y comparar `hash_resultado` | Identidad byte a byte del `.pptx` (§5.2 original: no se promete) |

### 3.1 Comprobaciones

| ID | Comprobación | Fuente de la evidencia |
|---|---|---|
| C1 | Existe el manifiesto, es JSON válido y su `esquema` se conoce | `procedencia.json` o fila de `procedencia` |
| C2 | Integridad: `sha256(bytes del manifiesto)` = `manifiesto_sha256` del historial | tabla `procedencia` |
| C3a | Cada archivo fuente registrado fue aportado de nuevo | el usuario vuelve a cargarlos |
| C3b | El SHA-256 de cada archivo aportado coincide con el registrado | cálculo local |
| C4 | El SHA-256 de la plantilla actual coincide con `version_plantillas` | cálculo local |
| C5 | `version_codigo` actual (versión + SHA) = el registrado | `version.py` y `_build_info.json` |
| C6 | `version_motor`, `version_definiciones`, `version_reglas` y la `configuracion` actuales = las registradas | catálogo y estado de la sesión |
| C7 | El `hash_resultado` de la regeneración = el registrado | regeneración con las mismas entradas |

### 3.2 Asignación de estados

El orden de evaluación es el de la tabla; gana la primera fila que se cumple.

| Estado | Condición | Qué muestra el sistema |
|---|---|---|
| `no_reproducible` | C1 falla (sin manifiesto, **legado**, esquema desconocido) **o** C2 falla (manifiesto alterado) **o** C3b falla (un archivo fuente aportado difiere) | La causa exacta. No afirma equivalencia. Ofrece regenerar como reporte **nuevo** |
| `parcial` | C1 y C2 pasan, C3b no falla, y se cumple al menos una: C3a falta (archivo no aportado), C4 falla, C5 falla, C6 falla, o no hay registro contra el cual verificar C2 (D-B) | La lista de componentes que difieren. **No regenera en silencio.** Permite regenerar «con versiones actuales», marcado *no equivalente al original* |
| `exacta` | C1 a C6 pasan **y** C7 pasa | «Idéntico» |

Casos límite, definidos aquí para que no queden implícitos:
- **C1 a C6 pasan y C7 falla** (mismos insumos y versiones, hash distinto): estado `parcial` con la alerta «anomalía de determinismo». Es un defecto del sistema y debe abrirse como incidencia.
- **Solo difiere `entorno`:** no cambia el estado. Se informa como nota (§3.4).
- **Solo difiere el SHA del commit, con las mismas versiones de motor, definiciones y reglas:** sigue siendo `parcial` (la especificación original lo exige: «el código actual es posterior»). Una equivalencia por versión de motor sería una ampliación y **no** se adopta sin tu decisión.
- **Reportes anteriores a la Fase 3A:** `no_reproducible (legado)` (AC-12).

### 3.3 Integridad sin registro (D-B)

Con solo el archivo `procedencia.json` (p. ej. compartido por correo) no existe `manifiesto_sha256` contra el cual comparar. Se declara «integridad no verificable» y el estado máximo es `parcial`. `exacta` exige el historial.

### 3.4 Por qué `entorno` está fuera del hash

- `hash_resultado` debe responder una sola pregunta: «¿el resultado es el mismo?». Los resultados numéricos usan `Decimal`, cuya aritmética es exacta y no depende de la versión de Python o de Pyodide.
- Si el entorno entrara en el hash, cada actualización del navegador o de Pyodide cambiaría el hash sin que el resultado cambiara, y haría `parcial` a todo el historial sin razón.
- Sí importa como **evidencia diagnóstica**: si el hash difiere con versiones iguales, la diferencia de `entorno` es la primera sospecha.
- Por eso se registra en el manifiesto, se compara y se informa, pero no decide el estado.

---

## 4. Versionado (H-2)

### 4.1 Reglas de SemVer (`MAJOR.MINOR.PATCH`)

**`ENGINE_VERSION`** (versión del resultado que produce el motor):

| Incremento | Cuándo |
|---|---|
| MAJOR | Cambia un valor numérico existente o la definición o fórmula de una métrica. Exige una entrada en `CAMBIOS_JUSTIFICADOS.md` (regla, valor antes, valor después, aprobación) |
| MINOR | Se agregan salidas, campos o hallazgos **sin** cambiar ningún valor existente |
| PATCH | Cambia redacción determinista o formato sin tocar cifras (p. ej. el patrón de «Conclusiones Clave»), o una corrección que no altera ningún valor |

**`APP_VERSION`** (versión de la aplicación publicada):

| Incremento | Cuándo |
|---|---|
| MAJOR | Cambia el formato del manifiesto, el contrato de datos o un comportamiento incompatible con reportes anteriores |
| MINOR | Funcionalidad nueva compatible |
| PATCH | Correcciones sin funcionalidad nueva |

**Identidad completa del código:** `APP_VERSION` + SHA del commit (`version_codigo`). Dos compilaciones con el mismo `APP_VERSION` y distinto SHA son código distinto: el estado de reproducibilidad lo detecta (C5).

### 4.2 Origen del SHA

| Contexto | SHA |
|---|---|
| GitHub Actions (`pages.yml`) | `GITHUB_SHA`, estampado por `build_site.py` en `backend/app/_build_info.json` dentro de `app.zip` |
| Compilación local | `git rev-parse HEAD`; si hay cambios sin confirmar, el valor lleva el sufijo `+dirty` |
| Sin información (p. ej. pruebas sin git) | `"desconocido"` (nunca se inventa) |

### 4.3 Línea base actual

- **Estado actual:** `version.versiones()` devuelve `app: None` y `motor: None`. Todo reporte generado hasta ahora es `no_reproducible (legado)`.
- **Propuesta (D-C):** al implementar 3A-1, `APP_VERSION = 1.0.0` y `ENGINE_VERSION = 1.0.0`.
- **Qué identifica `ENGINE_VERSION = 1.0.0`:** el motor de cálculo tal como lo congela la línea base `tests/regression/base/engine/` (4 escenarios; commit `386099b`), con SHA-256 de los cuatro archivos concatenados `73c840b368935f6757c7984eb77066b2e8950969ba36df43c63d507eb879d3a8`. Ese hash se guardará en `tests/regression/engine_version.json`.
- **Acoplamiento con la regresión:** una prueba nueva compara el SHA-256 actual de la línea base del motor contra el registrado. Si difiere y `ENGINE_VERSION` no cambió (o falta la entrada en `CAMBIOS_JUSTIFICADOS.md`), la prueba falla. Así no se puede cambiar un resultado numérico sin cambiar la versión.
- Las huellas de láminas (`tests/regression/base/deck/`) **no** acoplan `ENGINE_VERSION`: dependen de la plantilla local y no son reproducibles en CI. Un cambio de redacción se versiona por PATCH de forma manual y revisada.

---

## 5. Esquema JSON definitivo — `procedencia.json` (`"esquema": "procedencia/1"`)

Los valores del ejemplo son **ilustrativos** (marcados «ejemplo»), no resultados reales.

```json
{
  "esquema": "procedencia/1",
  "version_codigo":       { "app": "1.0.0", "commit": "d4cd706…(40 hex)" },
  "version_motor":        { "engine": "1.0.0" },
  "version_definiciones": { "archivo": "definiciones.json", "version": "1.0.0" },
  "version_reglas": {
    "catalogo": { "archivo": "reglas.json", "version": "1.1.0" },
    "reglas": [
      { "regla_id": "R-REL-PAC-PED", "regla_version": "1.0.0",
        "validacion_sintetica": "aprobada",
        "validacion_operacional": "no_validada_con_datos_reales" }
    ],
    "ejecucion": {
      "motor_ejecutado": false,
      "resultados_incluidos": false,
      "flags": { "validacion_fase1": false, "relacion_pedidos_carritos": false,
                 "anexo_calidad": false, "qa_pptx_exportado": false, "escenarios_estrictos": false },
      "nota": "El motor de reglas no se ejecutó en esta generación; las versiones listadas son metadatos del catálogo, no resultados."
    }
  },
  "version_plantillas": [
    { "id": "aetops-mensual/1", "nombre": "template.pptx", "sha256": "(64 hex)" }
  ],
  "archivos_fuente": [
    { "id": "F1", "nombre": "AETOPS_crudo_ejemplo.xlsx", "tamano_bytes": 0, "sha256": "(64 hex)",
      "filas": { "ventas": 0, "catalogo": 0 }, "columnas": { "ventas": ["…"], "catalogo": ["…"] },
      "periodo_detectado": "2026-09" }
  ],
  "fecha_generacion": { "utc": "2026-11-05T04:30:00Z", "zona_horaria": "America/Mexico_City" },
  "configuracion": {
    "metas": { "total": "12000000" },
    "umbrales": { "umbral_conciliacion_compras": "0.2" },
    "escenarios": { "e1_porcentaje": "0.25", "e2_porcentaje": "0.10" },
    "contexto": { "lineas": 0, "sha256": "(64 hex)" },
    "ia": { "usada": false, "modelo_declarado": null }
  },
  "hash_resultado": { "algoritmo": "sha256", "contrato": "resultado_canonico/1", "valor": "(64 hex)" },
  "entorno": { "pyodide": "0.27.7", "python": "3.12.7", "python_pptx": "1.0.2" }
}
```

Reglas del esquema:
- `version_codigo.commit` es el SHA completo o `"desconocido"`.
- `archivos_fuente[*].nombre` es solo el **nombre base**; nunca una ruta. No hay contenido de celdas (principio 5).
- `archivos_fuente[*].id` (`F1`, `F2`, …) se asigna por orden ascendente de `sha256` (no por orden de carga ni por nombre); es el vínculo con el hash canónico (§6).
- `configuracion.contexto` guarda el número de líneas y su SHA-256, no el texto (el texto ya está en el reporte y en el historial). Si no hay contexto, `lineas: 0`.
- `configuracion.ia.usada: true` marca un reporte con texto de IA; el texto aceptado se reutiliza desde `ia_log.json` (§5.2 original).
- `version_reglas.ejecucion`: mientras `motor_ejecutado` sea `false`, `resultados_incluidos` es `false` y **no** puede existir ningún resultado por regla en el manifiesto ni en el hash. Esto es un invariante probado (§11).
- `entorno.*` es `"desconocido"` cuando no se puede leer (p. ej. fuera de Pyodide no hay `pyodide`).
- El manifiesto **no** incluye sus propios hashes de integridad: `manifiesto_sha256` vive solo en el historial (evita autorreferencia).

---

## 6. Contrato del hash canónico — `resultado_canonico/1`

### 6.1 Qué entra

El **resultado final** del reporte, tal como se entrega:

| Bloque | Contenido |
|---|---|
| `periodo` | unidad, periodicidad, año, índice |
| `fuentes` | lista `[{"id": "F1", "sha256": …}]` ordenada por `sha256` |
| `valores` | todos los `Value` del `Result` (`tables`, `products`, `negados`, `extras`; o `blocks`, `funnel`, `extras` en GLP-1), con `Decimal` exactos y su `Lineage` |
| `hallazgos` | cada hallazgo con `id`, `severity`, `message`, `evidence` y los siete campos de la Fase 1 (`tipo`, `gravedad`, `estado_verificacion`, `efecto_generacion`, `faltante`, `regla_id`, `regla_version`) |
| `narrativa` | por sección, la lista **final** de párrafos visibles (`texto`, `tipo`, `editado`), incluidos los **editados a mano** (H-3), el resumen ejecutivo, las recomendaciones y el descubrimiento si existen |

Los párrafos editados manualmente se consideran parte del resultado final: si el usuario cambia una coma, `hash_resultado` cambia. El texto reescrito con IA entra igual (es el texto aceptado); el reporte queda marcado con `configuracion.ia.usada` (§5.2 original: «reproducible en cifras y texto determinista; texto de IA restaurado desde el registro»).

### 6.2 Qué NO entra (datos volátiles)

Fechas y horas, zona horaria, rutas absolutas, `run_id`, número de versión del historial, SHA del PPTX/PDF (el contenedor ZIP no es reproducible byte a byte), versiones de código y de entorno (se comparan aparte, §3), nombres de archivo fuente (se reemplazan por `id`).

### 6.3 Serialización

1. Se construye el objeto con la misma semántica de `tools/capture_baseline.py::canon` (`Decimal` → texto exacto, dataclass → dict, enum → valor, conjuntos ordenados).
2. Textos normalizados a Unicode NFC.
3. JSON con claves ordenadas, sin espacios (`separators=(",", ":")`), `ensure_ascii=False`, codificado en UTF-8.
4. `hash_resultado = SHA-256` de esos bytes, en hexadecimal minúscula.
5. `float` no se espera en los resultados: si aparece, se serializa con `repr`, igual que la línea base.

### 6.4 Trazabilidad de fuentes sin rutas dependientes del equipo

- En `valores`, todo `Lineage.file` se sustituye por el `id` de la fuente (`F1`, `F2`, …) si coincide con un archivo cargado. El valor vacío `""` se conserva.
- El vínculo `id` → nombre y SHA-256 vive en `archivos_fuente` del manifiesto. Así el linaje de cada celda sigue siendo trazable (`F1!Base!C3`) sin que el nombre del archivo ni su ruta cambien el hash. Cambiar el **contenido** de un archivo cambia su `sha256` y, con él, el hash; renombrarlo, no.
- Cualquier texto de `message` o `evidence` que contenga una ruta absoluta (POSIX o de Windows) se reemplaza por su nombre base antes de serializar. Una prueba exige el mismo hash con los mismos datos cargados desde dos directorios distintos y con distinto nombre de archivo.

### 6.5 Garantía de no alteración del reporte

El manifiesto y el hash se calculan **después** de guardar el PPTX y a partir de objetos ya producidos. No se inserta nada en el PPTX, no se vuelve a leer el PPTX para calcular el hash y no se llama al motor de reglas. La regresión de huellas de láminas y del motor debe seguir idéntica.

---

## 7. Modelo de persistencia (H-1)

### 7.1 Única fuente de verdad

1. El manifiesto se construye **una sola vez**, en memoria, y se serializa **una sola vez** a bytes UTF-8.
2. Esos mismos bytes se escriben en `procedencia.json` (copia distribuible) y en la tabla `procedencia` del historial.
3. La fila del historial es el **registro autoritativo** (la tabla es inmutable, igual que `runs`). El archivo es una copia exportable cuya integridad se verifica con `manifiesto_sha256`.
4. Ningún campo se calcula dos veces por rutas distintas. Los campos que ya existen en `runs` (`template_sha`, tabla `sources`) siguen donde están y se verifican contra el manifiesto con un invariante de prueba (no se escriben desde otra fuente).

### 7.2 Tabla nueva (la tabla `runs` no se modifica)

```sql
CREATE TABLE IF NOT EXISTS procedencia(
  run_id INTEGER PRIMARY KEY REFERENCES runs(id),
  esquema TEXT NOT NULL,
  manifiesto TEXT NOT NULL,            -- bytes exactos de procedencia.json (UTF-8)
  manifiesto_sha256 TEXT NOT NULL,     -- integridad (C2)
  hash_resultado TEXT NOT NULL         -- copia indexable del hash; debe coincidir con el manifiesto
);
CREATE TRIGGER IF NOT EXISTS procedencia_no_update BEFORE UPDATE ON procedencia BEGIN SELECT RAISE(ABORT, 'historial inmutable'); END;
CREATE TRIGGER IF NOT EXISTS procedencia_no_delete BEFORE DELETE ON procedencia BEGIN SELECT RAISE(ABORT, 'historial inmutable'); END;
```

- Se agrega al `SCHEMA` de `history/store.py` con `IF NOT EXISTS`: los historiales que ya existen en los navegadores siguen abriendo sin migración (la tabla se crea al conectar).
- Un historial exportado o importado (`.sqlite`) conserva la tabla.
- Sin historial (p. ej. línea de comandos sin base de datos) solo se escribe el archivo; la integridad queda «no verificable» (§3.3).
- La fila guarda `hash_resultado` por separado solo para consultar; la prueba exige que coincida con el del manifiesto.

### 7.3 Ubicación del archivo

`procedencia.json` en el directorio de salida del reporte, junto a `manifest.json`. **No** reemplaza ni modifica `manifest.json` (que conserva su contenido actual). Los dos son archivos distintos con propósitos distintos.

---

## 8. Arquitectura y flujo técnico

### 8.1 Módulos

| Módulo | Responsabilidad |
|---|---|
| `backend/app/version.py` (existente) | `APP_VERSION`, `ENGINE_VERSION`, lectura de `_build_info.json`; `versiones()` deja de devolver `None` |
| `backend/app/provenance.py` (nuevo) | Funciones **puras**: `canonico(...)`, `hash_resultado(...)`, `construir_manifiesto(...)`, `serializar(...)`, `comparar(...)`. Sin red, sin escritura, sin llamar al motor de reglas |
| `tools/build_site.py` (existente) | Escribe `backend/app/_build_info.json` en `app.zip` (SHA y fecha de compilación) |
| `backend/app/build.py` (existente) | Una llamada aditiva, después de guardar el PPTX y antes de cerrar |
| `backend/app/history/store.py` (existente) | Tabla `procedencia` y funciones de lectura y escritura |

### 8.2 Flujo (por reporte generado)

1. La aplicación genera el reporte **como hoy** (sin cambios).
2. Se guarda el PPTX y se aplica el QA existente.
3. `provenance` toma los objetos ya producidos (`Result`, narrativa final, plantilla, fuentes, configuración).
4. Calcula `hash_resultado` (§6) y arma el manifiesto (§5).
5. Serializa **una vez**; escribe `procedencia.json` y, si hay historial, la fila de `procedencia` en la misma transacción que `record_run`.
6. Si algo falla en los pasos 3 a 5: el reporte ya está generado y no se altera; se guarda `procedencia_error.json` (D-A).

### 8.3 Qué NO hace la Fase 3A

No ejecuta ni conecta el motor de reglas (flags en `false`), no cambia la interfaz, no toca `manifest.json`, `qa_report.json`, fórmulas, cifras, plantillas o láminas.

---

## 9. Reutilización de la infraestructura existente

| Existe | Qué se hace | Justificación |
|---|---|---|
| `history/store.py` (`runs`, `sources`, inmutabilidad por disparadores, `next_version`, `sha256`) | Se **extiende** con una tabla; se reutilizan `sha256` y el patrón de inmutabilidad; `runs` y `sources` no se modifican | Evita un segundo registro |
| `Lineage` (`models.py`) | Se **reutiliza** tal cual como trazabilidad de celdas; solo se sustituye `file` por `id` al serializar (§6.4) | Es la trazabilidad que pide la especificación |
| `tools/capture_baseline.py::canon` | Su **semántica** se replica dentro del backend | `tools/` no viaja en `app.zip` (solo dos herramientas de machotes), así que el motor no puede importarla en el navegador. `capture_baseline.py` **no se modifica** para no tocar la línea base. Una prueba comprueba que ambas producen la misma estructura de `valores` (salvo la sustitución de `file`) |
| `config.versiones()` y `config.cargar(...)` | Se reutilizan para `version_definiciones`, `version_reglas` y los flags | Ya existen |
| `manifest.json` (de `build.py`) | **Se conserva** sin cambios. `procedencia.json` es un archivo aparte | El contenido actual del manifiesto no coincide con §5.1 y lo usa la interfaz |
| `ia_log.json` | Se reutiliza para el texto de IA (§5.2 original); no se duplica en el manifiesto | Ya registra lo enviado y lo recibido |
| `tests/regression` y `archivos_protegidos.py` | Se reutilizan para demostrar la no regresión | Ya existen |

---

## 10. Subfases y dependencias

Cada subfase requiere tu autorización antes de empezar. Ninguna está autorizada hoy.

| Subfase | Objetivo | Archivos | Depende de |
|---|---|---|---|
| **3A-0** | Esta especificación | `docs/fase3a/` | — |
| **3A-1** | Versiones SemVer, estampado de commit y acoplamiento con la línea base | `version.py`, `tools/build_site.py`, `tests/regression/engine_version.json`, pruebas | 3A-0 aprobada |
| **3A-2** | Resultado canónico y `hash_resultado` | `provenance.py` (solo funciones puras), pruebas | 3A-1 |
| **3A-3** | Manifiesto `procedencia.json`, entorno y escritura junto al reporte | `provenance.py`, `build.py` (llamada aditiva), `web/service.py` (permitir servir el archivo), pruebas | 3A-2 |
| **3A-4** | Tabla `procedencia` en el historial, comparación y estados | `history/store.py`, `provenance.py`, pruebas | 3A-3 |
| **3A-5** | `release.yml` y etiquetas (A-5) | `.github/workflows/release.yml` | **Diferida: A-5 sin autorización** |

Detalle de cada subfase:

**3A-1**
- Implementación esperada: constantes `APP_VERSION` y `ENGINE_VERSION`; `build_site.py` escribe `_build_info.json`; `version.versiones()` devuelve los valores; `engine_version.json` con el SHA de la línea base.
- Pruebas: T-16; `app.zip` contiene `_build_info.json` y los módulos; la prueba de acoplamiento falla si cambia la línea base sin cambiar `ENGINE_VERSION`.
- Aceptación: versión y SHA legibles desde `app.zip`; 0 cambios en reportes, huellas y línea base.

**3A-2**
- Implementación esperada: `canonico()` y `hash_resultado()` sin tocar el pipeline ni `build.py`.
- Pruebas: mismo hash en dos corridas; distinto con un dato alterado; **distinto al editar un párrafo**; igual al renombrar el archivo o moverlo de directorio; igual en Python 3.12 y 3.13 y en Pyodide (reutiliza `tools/pyodide_node_check.mjs`); la estructura de `valores` coincide con `capture_baseline.canon`.
- Aceptación: criterios de AC-10 (parte de hash) y 0 cambios de comportamiento.

**3A-3**
- Implementación esperada: `construir_manifiesto()`, `entorno`, escritura de `procedencia.json` después del PPTX, `procedencia_error.json` ante fallos (D-A).
- Pruebas: T-07 (nueve campos presentes, más `esquema` y `entorno`); sin contenido de celdas; el PPTX y `manifest.json` idénticos con y sin procedencia; fallo simulado de procedencia no impide generar el reporte; `motor_ejecutado: false` y sin resultados de reglas.
- Aceptación: AC-10 completo; huellas de láminas y línea base del motor sin cambios.

**3A-4**
- Implementación esperada: tabla `procedencia` (§7.2), `comparar()` con los tres estados (§3.2).
- Pruebas: T-08 con manifiestos sintéticos (coincidente, versión distinta, archivo faltante, sin manifiesto, hash de entrada distinto, manifiesto alterado, anomalía de determinismo); un historial anterior abre sin migración; las filas son inmutables.
- Aceptación: AC-11 (0 regeneraciones silenciosas) y AC-12 (legado = `no_reproducible`).

**3A-5 (diferida)**
- No se implementa. Si en el futuro autorizas A-5: `release.yml` etiqueta `app-vX.Y.Z` y publica su `app.zip` con su SHA-256 (V-02, AC-28). Mientras tanto, los reportes cuyo código no sea recuperable quedan en `parcial` (§5.3 original).

---

## 11. Pruebas y criterios de aceptación

| Prueba | Qué valida | Subfase |
|---|---|---|
| T-07 | Manifiesto con los nueve campos; hash estable en dos corridas y distinto con un dato alterado; sin contenido de archivos | 3A-2 y 3A-3 |
| T-08 | Estados `exacta`, `parcial`, `no_reproducible`; nunca regenera en silencio; legado = `no_reproducible` | 3A-4 |
| T-16 | `app.zip` con los módulos y la versión y SHA estampados | 3A-1 |
| PR-1 (nueva) | Editar un párrafo cambia el hash (H-3) | 3A-2 |
| PR-2 (nueva) | Mismo hash desde dos directorios y con distinto nombre de archivo | 3A-2 |
| PR-3 (nueva) | `ejecucion.motor_ejecutado = false` y ningún resultado por regla en manifiesto ni en hash | 3A-3 |
| PR-4 (nueva) | `entorno` y fechas no afectan el hash | 3A-2 y 3A-3 |
| PR-5 (nueva) | Fila de `procedencia` = bytes del archivo; `manifiesto_sha256` coincide; invariantes con `runs` y `sources` | 3A-4 |
| PR-6 (nueva) | Un fallo de procedencia no impide generar el reporte | 3A-3 |
| PR-7 (nueva) | Acoplamiento `ENGINE_VERSION` ↔ línea base del motor | 3A-1 |

| Criterio | Redacción |
|---|---|
| AC-10 | Los nueve campos de §5.1 presentes (más `esquema` y `entorno`) en el 100 % de los reportes nuevos; `hash_resultado` idéntico en dos corridas con las mismas entradas; versión y SHA estampados en `app.zip` |
| AC-11 | Los tres estados de §3.2 se producen y se muestran correctamente; 0 regeneraciones silenciosas con versiones distintas |
| AC-12 | Los reportes previos a la 3A se muestran como `no_reproducible (legado)` |
| AC-28 | **Fuera de alcance** mientras A-5 no se autorice |
| Generales | 0 pruebas fallidas; CI en verde; `capture_baseline --check` sin diferencias; `archivos_protegidos --check` limpio con los nuevos autorizados; las pruebas de las Fases 1, 2A y 2B sin cambios |

---

## 12. Archivos protegidos y estrategia de regresión

### 12.1 Estado en el manifiesto de protegidos (`tests/regression/protegidos.json`)

| Archivo | Estado hoy | Subfase | Tratamiento |
|---|---|---|---|
| `tools/build_site.py` | protegido | 3A-1 | Se autoriza con motivo: estampado de versión |
| `backend/app/build.py` | protegido | 3A-3 | Se autoriza: llamada aditiva |
| `backend/app/web/service.py` | protegido | 3A-3 | Se autoriza: permitir servir `procedencia.json` |
| `backend/app/history/store.py` | protegido | 3A-4 | Se autoriza: tabla nueva |
| `backend/app/version.py` | fuera del manifiesto (creado en Fase 1) | 3A-1 | Se revisa por diff |
| `backend/app/provenance.py` | nuevo | 3A-2 | Archivo nuevo |
| `frontend/*`, `.github/workflows/*`, plantillas, importadores, `calc/`, `deck/`, `narrative/` | protegidos | — | **No se tocan** |

Cada autorización se registra con `tools/archivos_protegidos.py --write --autorizar ruta="motivo"`, igual que en cambios anteriores, y se acompaña de un comentario de motivo en la revisión.

### 12.2 Estrategia

1. **Foto previa:** antes de cada subfase, `capture_baseline --check`, `archivos_protegidos --check` y la suite completa en verde.
2. **No alteración:** `capture_baseline --check` debe seguir sin diferencias después de cada subfase (huellas del motor y, con plantilla local, de láminas).
3. **Pruebas de equivalencia:** la generación con procedencia produce un PPTX y un `manifest.json` idénticos a los de antes (PR-6 y T-07).
4. **Entorno:** pruebas en Python 3.12 (CI) y 3.13; el hash se verifica también en Pyodide con `tools/pyodide_node_check.mjs`.
5. **CI:** `tests.yml` ya ejecuta unidad y regresión; las pruebas nuevas sin plantilla ni Pyodide corren allí. Las que los requieren se omiten con motivo explícito (como la E2E actual).
6. **Cierre de cada subfase:** informe con pruebas antes y después, `ENGINE_VERSION` sin cambios (salvo que la subfase lo justifique), y sin Fase 3B ni UI.

---

## 13. Riesgos y limitaciones

| ID | Riesgo o limitación | Medida |
|---|---|---|
| R-1 | Hash inestable por orden de claves, `Decimal` o texto Unicode | Serialización canónica (§6.3), NFC y pruebas en 3.12, 3.13 y Pyodide |
| R-2 | Alterar el reporte sin querer | Cálculo posterior al PPTX, sin releer el PPTX y regresión de huellas |
| R-3 | Historiales ya existentes en navegadores | Tabla nueva con `IF NOT EXISTS`; `runs` no se toca |
| R-4 | Fuga de datos | Solo nombres base, tamaños, SHA-256, conteos y nombres de columnas; sin celdas (S-2) |
| R-5 | `build_site.py` es la única vía a producción | Cambio aditivo y prueba T-16 sobre el zip generado |
| R-6 | Un nombre de columna puede ser sensible | Se registran solo los nombres de columnas que la especificación pide («columnas detectadas»); no se guarda ningún valor |
| R-7 | El motor de reglas se conecte después y cambie el hash | Es legítimo: `ENGINE_VERSION` sube, `ejecucion.motor_ejecutado` pasa a `true` y los reportes anteriores quedan `parcial` |
| **L-1** | **Limitación (D-D):** `procedencia.json` no tendrá botón de descarga en la interfaz porque la interfaz queda fuera de 3A. Existirá en el directorio del reporte, en el historial y se podrá servir desde el backend, pero la persona usuaria no podrá descargarlo desde pantalla hasta una fase de interfaz | Documentada; decisión D-D |
| L-2 | Reproducir con código anterior sigue sin ser posible mientras A-5 no se autorice | Estado `parcial` documentado |
| L-3 | La comparación (3A-4) solo existe en backend; no hay pantalla que la muestre | Fase de interfaz posterior |

---

## 14. Lista para tu autorización

Para aprobar **3A-0** necesito tu confirmación sobre:

1. El esquema definitivo de §5, incluidas las dos adiciones de primer nivel (`esquema`, `entorno`) y el subobjeto `version_reglas.ejecucion` (§2).
2. El contrato del hash canónico (§6), en particular que los párrafos de IA aceptados entran y que `Lineage.file` se sustituye por `id`.
3. La asignación de estados (§3.2), incluida la regla de que un SHA de commit distinto es `parcial`.
4. D-A, D-B, D-C y D-D (§1.3).
5. Que la siguiente subfase en autorizarse sea **3A-1** (versiones y estampado), sin tocar nada más.

Mientras no la autorices, no se escribe código de la Fase 3A, no se toca la Fase 3B, la Fase 4 ni la interfaz, y A-5 sigue sin autorización.
