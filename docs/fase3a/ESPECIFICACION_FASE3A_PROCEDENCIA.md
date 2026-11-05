# Report Intelligence — Fase 3A · Procedencia y reproducibilidad
## Subfase 3A-0: especificación definitiva (solo documentación)

| | |
|---|---|
| Estado | **3A-0 con revisión favorable del usuario; decisiones D-A a D-D aprobadas.** Cierra al fusionarse el PR #15. No hay código de la Fase 3A y nada de este documento está implementado. **La subfase 3A-1 no está autorizada** |
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

### 1.3 Decisiones D-A a D-D (aprobadas por el usuario)

| ID | Decisión aprobada | Dónde se concreta |
|---|---|---|
| D-A | Si falla la procedencia, **el reporte se genera igual**. El fallo se registra en `procedencia_error.json` (no en `qa_report.json` ni en `manifest.json`), con las garantías de §8.4 | §8.4 |
| D-B | `exacta` exige integridad verificada contra el historial; un manifiesto sin historial alcanza **como máximo `parcial`** | §3.2 y §3.3 |
| D-C | `APP_VERSION` y `ENGINE_VERSION` comienzan en **`1.0.0`**. Es la **primera versión formalmente identificada bajo este esquema**; **no** es el inicio histórico del proyecto, que existía antes sin versión estampada | §4.3 |
| D-D | **No** se incorpora botón de descarga ni ningún cambio de interfaz. `procedencia.json` queda en el directorio del reporte y en el historial | §13 (L-1) |

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
| `exacta` | C1 a C6 pasan **y** C7 pasa. C7 exige una **regeneración real** (ver §3.5): sin regeneración no existe `exacta` | «El resultado canónico es idéntico» (nunca «el archivo es idéntico») |

Casos límite, definidos aquí para que no queden implícitos:
- **C1 a C6 pasan y C7 falla** (mismos insumos y versiones, hash distinto): estado `parcial` con la alerta «anomalía de determinismo». Es un defecto del sistema y debe abrirse como incidencia.
- **Solo difiere `entorno`:** no cambia el estado. Se informa como nota (§3.4).
- **Solo difiere el SHA del commit, con las mismas versiones de motor, definiciones y reglas:** sigue siendo `parcial` (la especificación original lo exige: «el código actual es posterior»). Una equivalencia por versión de motor sería una ampliación y **no** se adopta sin tu decisión.
- **Reportes anteriores a la Fase 3A:** `no_reproducible (legado)` (AC-12).
- **Reporte con `procedencia_error.json` y sin `procedencia.json` válido (§8.4):** `no_reproducible`, con la causa «procedencia no disponible por un error al generarla». No hay evidencia suficiente y no se declara reproducibilidad.

### 3.3 Integridad sin registro (D-B)

Con solo el archivo `procedencia.json` (p. ej. compartido por correo) no existe `manifiesto_sha256` contra el cual comparar. Se declara «integridad no verificable» y el estado máximo es `parcial`. `exacta` exige el historial.

### 3.4 `entorno`: fuera del hash, pero no irrelevante

`entorno` (versiones de Pyodide, Python y python-pptx) se registra en el manifiesto como **evidencia diagnóstica** y queda **fuera** de `hash_resultado`.

**Por qué fuera del hash.** `hash_resultado` responde una sola pregunta: «¿el resultado canónico es el mismo?». Si el entorno entrara en el hash, cualquier actualización de Pyodide o del navegador cambiaría el hash aunque el resultado canónico no cambiara, y dejaría `parcial` a todo el historial sin que haya una diferencia en el resultado.

**Por qué no es irrelevante.** No se presupone que las versiones no afecten ningún comportamiento:

| Una diferencia de entorno puede… | Efecto | Lo que la Fase 3A garantiza |
|---|---|---|
| Cambiar cómo se escribe el contenedor del PPTX (python-pptx, ZIP, marcas de tiempo) | Los **bytes** del `.pptx` pueden diferir | No se promete igualdad binaria (§3.5) |
| Cambiar la forma de construir o serializar el XML de las láminas (python-pptx, `lxml`) | El PPTX puede abrirse o dibujarse de forma ligeramente distinta | No se promete igualdad visual (§3.5) |
| Cambiar el render del PDF o de las imágenes de QA (motor de conversión, tipografías) | Los márgenes, saltos de línea o recortes pueden variar | El QA se evalúa en cada generación; no se hereda |
| Cambiar la lectura de los libros de entrada o la aritmética (bibliotecas o Python) | **Podría** cambiar el resultado canónico | Se detecta: si cambia, `hash_resultado` cambia (C7) |

**Uso en el sistema:**
- `entorno` se compara y se informa como **nota**; **no decide** el estado de reproducibilidad por sí solo.
- Si C1 a C6 pasan y C7 falla, la diferencia de `entorno` es la **primera sospecha** (junto con un defecto de determinismo) y se muestra en la alerta de «anomalía de determinismo» (§3.2).
- Si el resultado canónico coincide pero el entorno difiere, la reproducibilidad **canónica** es `exacta` y se advierte expresamente que **no** implica igualdad binaria ni visual del PPTX, y que una diferencia de entorno puede limitar la reproducibilidad técnica o visual del archivo.

### 3.5 Tres igualdades distintas: canónica, binaria y visual

Estas tres condiciones **no son equivalentes** y la Fase 3A **no** afirma que lo sean.

| Igualdad | Qué compara | ¿La garantiza la Fase 3A? |
|---|---|---|
| **Del resultado canónico** | El `hash_resultado` definido en §6 (cifras con su linaje, hallazgos, textos finales, incluidos los editados) | **Sí.** Es la única que se promete y es la que significa `exacta` |
| **Binaria del PPTX** | Que los bytes del `.pptx` sean idénticos | **No.** El contenedor ZIP lleva marcas de tiempo y metadatos; el entorno también puede alterar los bytes. Nunca se afirma ni se prueba |
| **Visual del reporte** | Que las láminas se vean igual al abrirlas o renderizarlas | **No.** Depende de la plantilla, las tipografías, el render y el entorno. La revisión visual es una verificación aparte (QA), no una propiedad de la procedencia |

Consecuencias:
- **`exacta` significa únicamente** que, con las mismas entradas y las mismas versiones registradas, una **regeneración real** produce un resultado canónico cuyo `hash_resultado` coincide con el del reporte original. El sistema regenera, calcula el hash y lo compara; comparar solo los manifiestos no basta.
- Un mismo resultado canónico puede dar PPTX con bytes distintos y con diferencias visuales; el sistema no lo oculta.
- Un PPTX con bytes distintos **no** es evidencia de un resultado distinto, y un PPTX visualmente igual **no** es evidencia de un resultado canónico igual.
- Ningún mensaje de la aplicación debe usar «idéntico» sin decir **qué** es idéntico («resultado canónico»).

---

## 4. Versionado (H-2)

### 4.1 Reglas de SemVer (`MAJOR.MINOR.PATCH`)

**`ENGINE_VERSION`** (versión del resultado que produce el motor):

| Incremento | Cuándo |
|---|---|
| MAJOR | Cambia un valor numérico existente o la definición o fórmula de una métrica. Exige justificar el cambio por escrito (regla, valor antes, valor después, aprobación) en la descripción del cambio y en esta documentación; ver la nota de abajo sobre `CAMBIOS_JUSTIFICADOS.md` |
| MINOR | Se agregan salidas, campos o hallazgos **sin** cambiar ningún valor existente |
| PATCH | Cambia redacción determinista o formato sin tocar cifras (p. ej. el patrón de «Conclusiones Clave»), o una corrección que no altera ningún valor |

**`APP_VERSION`** (versión de la aplicación publicada):

| Incremento | Cuándo |
|---|---|
| MAJOR | Cambia el formato del manifiesto, el contrato de datos o un comportamiento incompatible con reportes anteriores |
| MINOR | Funcionalidad nueva compatible |
| PATCH | Correcciones sin funcionalidad nueva |

> **Nota sobre `CAMBIOS_JUSTIFICADOS.md`.** Los documentos de la Fase 1 lo citan como registro de cambios que alteran un resultado, pero **el archivo no existe** y la subfase 3A-1 **no lo crea** (decisión del usuario, X-2). Mientras no exista, la justificación de un cambio de `ENGINE_VERSION` se documenta en la descripción del PR y en la especificación o documentación existente. Crear ese archivo es una decisión pendiente, fuera de 3A-1.

**Identidad completa del código:** `APP_VERSION` + SHA del commit (`version_codigo`). Dos compilaciones con el mismo `APP_VERSION` y distinto SHA son código distinto: el estado de reproducibilidad lo detecta (C5).

### 4.2 Origen del SHA

| Contexto | SHA |
|---|---|
| GitHub Actions (`pages.yml`) | `GITHUB_SHA`, estampado por `build_site.py` en `backend/app/_build_info.json` **dentro de `app.zip`** (no es un archivo del repositorio) |
| Compilación local | `git rev-parse HEAD`; si hay cambios sin confirmar en lo que se empaqueta, el valor lleva el sufijo `+dirty` |
| Sin información (p. ej. pruebas sin git) | `"desconocido"` (nunca se inventa) |

**`_build_info.json`** contiene únicamente `{"esquema": "build_info/1", "commit": "<sha>"}`. **No lleva fecha de compilación ni ningún otro valor variable** (decisión X-1: la especificación de Fase 1 §8.1 hablaba de «SHA y fecha de compilación»; la fecha se omite).

### 4.2.1 Estados de la identidad del commit

| `compilacion.estado` | Significado | Valor de `commit` |
|---|---|---|
| `limpia` | Commit identificado y árbol sin cambios al compilar | `<40 hex>` |
| `dirty` | Commit identificado, pero el árbol tenía cambios en lo empaquetado | `<40 hex>+dirty` |
| `desconocida` | No hay información suficiente (falta `_build_info.json`, está dañado o su SHA no es válido). No es un error | `desconocido` |

Una compilación `dirty` **no** se presenta como una compilación reproducible del commit limpio: el commit identifica el punto de partida, no el contenido real. `version.py` solo **lee** el archivo; no ejecuta git en tiempo de ejecución. En CI de un *pull request*, `GITHUB_SHA` es el commit de la fusión simulada, no el de la rama.

### 4.3 Línea base actual

- **Estado antes de 3A-1:** `version.versiones()` devolvía `app: None` y `motor: None`. Todo reporte generado hasta entonces es `no_reproducible (legado)`.
- **Decisión aprobada (D-C), implementada en 3A-1:** `APP_VERSION = 1.0.0` y `ENGINE_VERSION = 1.0.0`. **`1.0.0` es la primera versión formalmente identificada bajo este esquema; no marca el inicio histórico del proyecto.** El código anterior ya existía y evolucionó sin versión estampada; no se le asigna ninguna versión retroactiva ni se infiere una historia de versiones.
- **Qué identifica `ENGINE_VERSION = 1.0.0`:** los resultados de referencia del motor en `tests/regression/base/engine/` (4 escenarios; commit `386099b`), identificados por el digest de §4.4. La referencia vive en `tests/regression/engine_version.json`.
- **Acoplamiento con la regresión (alcance exacto):** `tests/regression/test_engine_version.py` exige que el digest actual de esa línea base coincida con el último registrado y que la versión registrada sea la de `ENGINE_VERSION`. Si los resultados de referencia cambian, la prueba falla hasta que se registre una `ENGINE_VERSION` nueva. **No es un detector automático de cambios en el código del motor** (ver §4.4).
- Las huellas de láminas (`tests/regression/base/deck/`) **no** acoplan `ENGINE_VERSION`: dependen de la plantilla local y no son reproducibles en CI. Un cambio de redacción se versiona por PATCH de forma manual y revisada.

### 4.4 Digest de la línea base del motor: algoritmo exacto y alcance

**Algoritmo `RI-ENGINE-BASELINE/1`.** El digest es el SHA-256 del siguiente flujo de bytes:

```
b"RI-ENGINE-BASELINE/1\n"
por cada archivo *.json de tests/regression/base/engine/, en orden ascendente del nombre codificado en UTF-8:
    b"file " + <nombre del archivo> + b"\n"
    b"len "  + <largo del contenido en bytes, en ASCII decimal> + b"\n"
    <contenido>      (bytes del archivo; los saltos CRLF se convierten a LF)
    b"\n"
```

| Pregunta | Respuesta |
|---|---|
| Orden de los archivos | Ascendente por nombre (bytes UTF-8) |
| ¿Se incluyen los nombres? | Sí (`file <nombre>`), así que renombrar un archivo cambia el digest |
| Separación de contenidos | Cada contenido va precedido de su nombre y de su largo (`len N`) y seguido de `\n`: no hay concatenación ambigua (mover texto de un archivo a otro cambia el digest) |
| Codificación | Nombres en UTF-8; el contenido se usa tal como está guardado (los snapshots ya son UTF-8). CRLF → LF para que el digest no dependa del sistema de archivos |
| Cómo se recalcula | `python tests/regression/test_engine_version.py` imprime el digest actual |
| Cómo se actualiza la referencia | (1) justificar el cambio de resultados y regenerar la línea base con `tools/capture_baseline.py --write`; (2) subir `ENGINE_VERSION` en `backend/app/version.py` según §4.1; (3) `python tests/regression/test_engine_version.py --actualizar`, que agrega una entrada al `historial` de `engine_version.json` y **se niega** a registrar una huella nueva con una versión ya registrada o menor que la última |

Valor de referencia de `ENGINE_VERSION = 1.0.0`: `f80a6024f4ccbf47be48307ff76d2c1ccc30547eef29cf304cabdd052a285d3a`. (Un cálculo previo de esta especificación, por concatenación simple de los archivos, queda sustituido por este algoritmo, porque aquella concatenación era ambigua.)

**Tres cosas distintas, que no se confunden:**

| Concepto | Qué es | ¿Lo detecta la prueba? |
|---|---|---|
| Cambio en los **resultados de referencia** | Los 4 snapshots de `base/engine/` cambian de contenido | **Sí**: cambia el digest |
| Cambio en el **código del motor** | Se modifica código de cálculo, agregación, reglas, etc. | **No** directamente. Solo se nota si altera alguno de los 4 escenarios de referencia; un cambio que no altere esos resultados pasa inadvertido |
| **Incremento de `ENGINE_VERSION`** | Decisión humana, regida por §4.1 | La prueba solo exige coherencia entre la huella y la versión; no decide cuándo subirla |

La prueba de snapshots **no** es un detector automático de todos los cambios posibles en el código del motor. Solo garantiza que *esos resultados de referencia* y `ENGINE_VERSION` no se desacoplen; las historias de versiones del historial no se pueden repetir con otra huella, pero un historial editado a mano sigue siendo una decisión humana revisable en el PR.

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
| `backend/app/version.py` (existente) | `APP_VERSION`, `ENGINE_VERSION`, lectura de `_build_info.json` (`commit()`, `compilacion()`); `versiones()` devuelve las versiones y la identidad del commit y conserva los demás campos |
| `backend/app/provenance.py` (nuevo) | Funciones **puras**: `canonico(...)`, `hash_resultado(...)`, `construir_manifiesto(...)`, `serializar(...)`, `comparar(...)`. Sin red, sin escritura, sin llamar al motor de reglas |
| `tools/build_site.py` (existente) | Escribe `backend/app/_build_info.json` **dentro de `app.zip`** con el SHA del commit (sin fecha; X-1) |
| `backend/app/build.py` (existente) | Una llamada aditiva, después de guardar el PPTX y antes de cerrar |
| `backend/app/history/store.py` (existente) | Tabla `procedencia` y funciones de lectura y escritura |

### 8.2 Flujo (por reporte generado)

1. La aplicación genera el reporte **como hoy** (sin cambios).
2. Se guarda el PPTX y se aplica el QA existente.
3. `provenance` toma los objetos ya producidos (`Result`, narrativa final, plantilla, fuentes, configuración).
4. Calcula `hash_resultado` (§6) y arma el manifiesto (§5).
5. Serializa **una vez**; escribe `procedencia.json` (escritura atómica, §8.4) y, si hay historial, inserta la fila de `procedencia` **después** de `record_run` y en **su propia transacción** (la corrida de `runs` ya existe y no se revierte si esta inserción falla).
6. Si algo falla en los pasos 3 a 5: el reporte ya está generado y no se altera; se aplica el manejo de errores de §8.4 (D-A).

### 8.3 Qué NO hace la Fase 3A

No ejecuta ni conecta el motor de reglas (flags en `false`), no cambia la interfaz, no toca `manifest.json`, `qa_report.json`, fórmulas, cifras, plantillas o láminas.

### 8.4 Errores de procedencia (D-A)

Un fallo de procedencia **nunca** impide ni deshace la generación de un reporte que ya se produjo correctamente.

**Garantías:**

| # | Garantía |
|---|---|
| E-1 | **No se pierde el reporte.** La procedencia se construye después de guardar el PPTX y el QA. Cualquier excepción se captura dentro del bloque de procedencia; el PPTX, el PDF, `manifest.json`, `qa_report.json` y la fila de `runs` quedan como están |
| E-2 | **`procedencia_error.json` registra el fallo cuando es técnicamente posible.** Se escribe en el directorio del reporte, junto a `manifest.json`. Contiene: `esquema` (`"procedencia_error/1"`), el tipo de error y su mensaje (sin rutas absolutas ni contenido de archivos), la etapa en que ocurrió (`canonico`, `manifiesto`, `serializacion`, `archivo`, `historial`), la fecha UTC y la identificación del reporte (§ asociación) |
| E-3 | **Nunca se presenta un manifiesto incompleto como válido.** `procedencia.json` solo se escribe cuando el manifiesto completo (los nueve campos más `esquema` y `entorno`) se construyó, se validó contra el esquema y se serializó. La escritura es atómica: se escribe a un archivo temporal y se renombra al terminar. Si algo falla antes, **no** queda `procedencia.json` (ni parcial ni con campos vacíos) y, si ya existiera uno parcial por un fallo a medias, se elimina o no se renombra |
| E-4 | **No se declara reproducibilidad sin evidencia suficiente.** Un reporte con `procedencia_error.json` y sin `procedencia.json` válido se clasifica `no_reproducible` con la causa «procedencia no disponible por un error al generarla» (§3.2). Nunca `parcial` ni `exacta` |
| E-5 | **El error queda asociado al reporte.** `procedencia_error.json` incluye la identificación del reporte: unidad, periodicidad, año, índice, nombre del PPTX generado y, si existe, `run_id` y la versión del historial. Si el historial registró la corrida pero falló la fila de `procedencia`, esa corrida queda sin procedencia y se trata como en E-4 |
| E-6 | **Fila del historial atómica con el manifiesto.** La fila de `procedencia` solo se inserta si el manifiesto es válido; no se guarda un manifiesto incompleto en la base de datos. Un fallo al insertarla no revierte `runs` ni el reporte (E-1) |
| E-7 | **Si ni siquiera se puede escribir `procedencia_error.json`** (disco o permisos), el fallo no se oculta: la función de procedencia devuelve el error a quien la llamó y la generación continúa. No se reintenta ni se bloquea el reporte. En ese caso la ausencia de `procedencia.json` ya implica `no_reproducible` (E-4) |

**Qué NO hace el manejo de errores:** no reintenta en silencio, no genera un manifiesto «de emergencia» con datos inventados, no marca el reporte como no apto y no modifica `qa_report.json` ni `manifest.json`.

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
- Implementación esperada: constantes `APP_VERSION` y `ENGINE_VERSION`; `build_site.py` escribe `_build_info.json` (solo SHA) dentro de `app.zip`; `version.versiones()` devuelve las versiones y el commit; `tests/regression/engine_version.json` con el digest de §4.4 y su prueba.
- Pruebas: T-16; `app.zip` contiene `_build_info.json` y los módulos; PR-7 (alcance acotado de §4.4); lectura de versiones con y sin información de compilación; estados `limpia`, `dirty` y `desconocida`.
- Actualizaciones autorizadas fuera del código nuevo: la afirmación de `None` en `tests/unit/test_config_fase1.py` y la fila desactualizada de `docs/CONFIGURACION_FASE1.md` (X-3).
- Aceptación: versión y SHA legibles desde `app.zip`; 0 cambios en reportes, huellas y línea base.

**3A-2**
- Implementación esperada: `canonico()` y `hash_resultado()` sin tocar el pipeline ni `build.py`.
- Pruebas: mismo hash en dos corridas; distinto con un dato alterado; **distinto al editar un párrafo**; igual al renombrar el archivo o moverlo de directorio; igual en Python 3.12 y 3.13 y en Pyodide (reutiliza `tools/pyodide_node_check.mjs`); la estructura de `valores` coincide con `capture_baseline.canon`.
- Aceptación: criterios de AC-10 (parte de hash) y 0 cambios de comportamiento.

**3A-3**
- Implementación esperada: `construir_manifiesto()`, `entorno`, escritura atómica de `procedencia.json` después del PPTX, y manejo de errores de §8.4 con `procedencia_error.json` (D-A).
- Pruebas: T-07 (nueve campos presentes, más `esquema` y `entorno`); sin contenido de celdas; el PPTX y `manifest.json` idénticos con y sin procedencia; PR-6, PR-8 y PR-9 (fallos inyectados); `motor_ejecutado: false` y sin resultados de reglas.
- Aceptación: AC-10 completo; huellas de láminas y línea base del motor sin cambios.

**3A-4**
- Implementación esperada: tabla `procedencia` (§7.2), `comparar()` con los tres estados (§3.2).
- Pruebas: T-08 con manifiestos sintéticos (coincidente, versión distinta, archivo faltante, sin manifiesto, hash de entrada distinto, manifiesto alterado, anomalía de determinismo, reporte con `procedencia_error.json`); PR-5, PR-10 y PR-11; un historial anterior abre sin migración; las filas son inmutables.
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
| PR-6 (nueva) | Un fallo de procedencia (inyectado en cada etapa: `canonico`, `manifiesto`, `serializacion`, `archivo`, `historial`) no impide ni altera la generación: PPTX, `manifest.json`, `qa_report.json` y `runs` idénticos a los de una generación sin fallo (E-1) | 3A-3 y 3A-4 |
| PR-8 (nueva) | Nunca queda un `procedencia.json` incompleto: ante un fallo no existe el archivo (ni parcial ni con campos vacíos) y no se inserta la fila de `procedencia` (E-3, E-6) | 3A-3 y 3A-4 |
| PR-9 (nueva) | `procedencia_error.json` se escribe con el esquema definido y la identificación del reporte (unidad, periodo, PPTX, `run_id` si existe); sin rutas absolutas ni contenido de archivos; un reporte con error y sin manifiesto válido se clasifica `no_reproducible`, nunca `parcial` ni `exacta` (E-2, E-4, E-5) | 3A-3 y 3A-4 |
| PR-10 (nueva) | Tres igualdades: con el mismo resultado canónico y PPTX con bytes distintos, la comparación devuelve `exacta` sin afirmar igualdad binaria ni visual; una diferencia de `entorno` se informa como nota y no cambia el estado (§3.4, §3.5) | 3A-4 |
| PR-11 (nueva) | `exacta` no se asigna sin regeneración real: con C1 a C6 en verde y sin regenerar, el resultado nunca es `exacta` (§3.5) | 3A-4 |
| PR-7 (nueva) | Acoplamiento `ENGINE_VERSION` ↔ digest de la línea base del motor (§4.4). Cubre los **resultados de referencia**; no detecta por sí sola cambios en el código del motor | 3A-1 |

| Criterio | Redacción |
|---|---|
| AC-10 | Los nueve campos de §5.1 presentes (más `esquema` y `entorno`) en el 100 % de los reportes nuevos; `hash_resultado` idéntico en dos corridas con las mismas entradas; versión y SHA estampados en `app.zip` |
| AC-11 | Los tres estados de §3.2 se producen y se muestran correctamente; 0 regeneraciones silenciosas con versiones distintas; `exacta` solo tras una regeneración real con `hash_resultado` coincidente, sin afirmar igualdad binaria ni visual del PPTX (§3.5) |
| AC-12 | Los reportes previos a la 3A se muestran como `no_reproducible (legado)` |
| AC-13A (nuevo, de esta fase) | Ante cualquier fallo de procedencia el reporte se genera sin cambios; nunca existe un `procedencia.json` incompleto; el fallo queda en `procedencia_error.json` asociado al reporte y el reporte no se declara reproducible (§8.4) |
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
| **L-1** | **Limitación (D-D, aprobada):** no hay botón de descarga ni cambio de interfaz. `procedencia.json` existe en el directorio del reporte y en el historial, y el backend podrá servirlo (permiso en `service.py`, §12.1), pero la persona usuaria no podrá descargarlo desde pantalla hasta una fase de interfaz | Documentada; decisión D-D |
| R-8 | Confundir «exacta» con igualdad del archivo o de su aspecto | §3.5: tres igualdades distintas; los mensajes dicen siempre «resultado canónico» (PR-10) |
| R-9 | Un fallo de procedencia produzca un registro incompleto o parezca un reporte reproducible | §8.4: escritura atómica, sin manifiesto parcial, `no_reproducible` ante error, `procedencia_error.json` asociado (PR-6, PR-8, PR-9) |
| L-2 | Reproducir con código anterior sigue sin ser posible mientras A-5 no se autorice | Estado `parcial` documentado |
| L-3 | La comparación (3A-4) solo existe en backend; no hay pantalla que la muestre | Fase de interfaz posterior |

---

## 14. Estado de cierre de la subfase 3A-0

| Elemento | Estado |
|---|---|
| Revisión del documento | **Favorable** (usuario). No se registraron objeciones al esquema de §5, al contrato de §6 ni a la asignación de estados de §3.2 |
| D-A, D-B, D-C, D-D | **Aprobadas** (§1.3) |
| Precisión: `exacta` exige regeneración real; canónica ≠ binaria ≠ visual | **Incorporada** (§3.2, §3.5) |
| Precisión: `entorno` fuera del hash, pero no irrelevante | **Incorporada** (§3.4) |
| Precisión: errores de procedencia | **Incorporada** (§8.4, PR-6, PR-8, PR-9, AC-13A) |
| `1.0.0` = primera versión formalmente identificada, no inicio histórico | **Incorporada** (§1.3, §4.3) |
| Fusión del PR #15 | **Pendiente** (solo documentación; la decide el usuario) |
| Subfase **3A-1** | **Autorizada e implementada; en revisión (PR exclusivo).** No fusionada |
| Subfases 3A-2 a 3A-4 | No autorizadas; cada una requiere su propia autorización |
| 3A-5 (`release.yml`, etiquetas) | Diferida: A-5 sin autorización |
| Fase 3B, Fase 4, Fase 5, interfaz, conexión del motor de reglas | Fuera de alcance |

Hasta que se autorice 3A-1 no se escribe código de la Fase 3A, no se modifica ningún archivo de implementación y no se alteran las fases anteriores, sus reglas, fórmulas, plantillas ni pruebas.
