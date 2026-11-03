# Report Intelligence — Diseño técnico (Fase 3)

Basado en `DIAGNOSTICO_FASE1.md` y `MATRIZ_TRAZABILIDAD.md`. Decisión vigente: **backend Python que rellena las plantillas PPTX originales y genera el PDF con LibreOffice**. Los archivos recibidos son ejemplos: el diseño se apoya en la *estructura*, no en datos concretos.

---

## 1. Entorno inspeccionado y spike de factibilidad

| Recurso | Estado en el entorno |
|---|---|
| Python | 3.13 · `python-pptx 1.0.2`, `openpyxl 3.1.5`, `pandas 3.0`, `pydantic 2`, `lxml`, `PyYAML`, `Jinja2`, `uvicorn` ya instalados |
| FastAPI / pytest | **No instalados** (hay `starlette`); se declaran en `requirements.txt` |
| LibreOffice | 24.2 (headless) disponible → PPTX→PDF funciona |
| Docker | Disponible → empaquetado reproducible |
| Fuentes | Sin **Aptos / Aptos Narrow** (las plantillas las usan). Hay Carlito y Liberation |

**Spike (con las plantillas reales, resultados verificados):**

| Prueba | Resultado |
|---|---|
| Rellenar una celda de tabla conservando fuente, tamaño y color | ✅ funciona (se cambia el texto del primer *run*) |
| Clonar una fila de tabla (`deepcopy` de `<a:tr>`) | ✅ pero **22 filas desbordan la diapositiva** → hace falta lógica de ajuste |
| Guardar el PPTX de GLP-1 con `python-pptx` | ✅ el embudo `chartEx` (gráfica nativa) **se conserva** |
| PPTX → PDF con LibreOffice | ✅ renderiza, pero **sin Aptos Narrow el texto sale más ancho** y ya desborda en el original (diap. 6 AETOPS) |

Conclusión: la ruta es viable. Riesgos reales: **fuentes** (§9) y **ajuste de filas/texto** (§7.4).

---

## 2. Principios

1. **Excel = fuente; motor de cálculo = verdad; IA = interpretación; PPTX/PDF = salida.**
2. Un solo cálculo, un solo contenido: PPTX y PDF salen del **mismo** archivo (el PDF se convierte del PPTX, nunca se regenera aparte).
3. **Faltante ≠ cero.** El dato ausente es un valor propio (`Missing`) que se muestra como "—" y bloquea o advierte según la regla.
4. **Nada silencioso:** toda suposición (columna asignada, periodo detectado, fila omitida) queda registrada y visible.
5. Formatos independientes por **configuración**, no por código copiado.
6. Reglas abiertas del diagnóstico (§7) = **parámetros** con valor por defecto tomado de los originales.

---

## 3. Vista general

```
 Navegador (UI)                    Backend Python (FastAPI)
┌────────────────┐   HTTPS   ┌──────────────────────────────────────────────┐
│ Dashboard       │──────────▶│ API                                          │
│ Wizard 8 pasos  │           │  ├─ A. importer   (Excel → bloques crudos)   │
│ Revisión/edición│◀──────────│  ├─ B. normalizer (bloques → modelo canónico)│
└────────────────┘           │  ├─ C. calc       (modelo → KPIs + lineage)  │
                             │  ├─ D. validator  (reglas → hallazgos)       │
                             │  ├─ E. narrative  (KPIs agregados → texto)   │
                             │  ├─ F. pptx       (plantilla + datos → PPTX) │
                             │  ├─ G. pdf        (LibreOffice: PPTX → PDF)  │
                             │  ├─ qa            (render → chequeos visuales)│
                             │  └─ H. history    (SQLite + archivos)        │
                             └──────────────────────────────────────────────┘
```

Regla de dependencias (solo hacia abajo, sin ciclos): `importer → normalizer → calc → validator → narrative → pptx → pdf → qa`. `history` lo usa el orquestador. **`calc` no importa nada de `pptx`**, y viceversa (esto da la prueba de regresión "cambiar plantilla no cambia resultados").

---

## 4. Modelo de datos canónico (Pydantic)

```python
class Period(BaseModel):
    unit: Literal["AETOPS","GLP1"]
    periodicity: Literal["mensual","trimestral"]
    year: int
    index: int            # mes 1-12 o trimestre 1-4
    # derivados: label ("Agosto 2026"), start, end

class Comparison(BaseModel):
    kind: Literal["YoY","MoM","QoQ"]
    base: Period; other: Period

class Value(BaseModel):        # nunca un float desnudo
    v: Decimal | None          # None = faltante
    status: Literal["ok","missing","zero","negative","derived"]
    src: Lineage               # hoja, rango, celda(s), transformación

class Lineage(BaseModel):
    file: str; sheet: str; cells: str          # "Base!C3:C4"
    transform: str                             # "sum" | "ratio(C,E)" | "pasted"
    ruleset: str                               # versión de metodología

class Table(BaseModel):                        # salida de calc, entrada de pptx
    key: str                                   # "aetops.canal.yoy"
    columns: list[Column]; rows: list[Row]     # celdas = Value
    grouping: list[Group] | None               # bloques por canal/línea (2025/2026/%Δ)
```

- **Decimal** internamente; el redondeo ocurre solo al formatear (regla del prompt maestro).
- `Value.status="zero"` (cero real) se distingue de `"missing"` (celda vacía, producto sin venta previa).
- Cada celda mostrada en el PPTX conserva su `Lineage` → la UI permite "ver origen" de cualquier KPI.

---

## 5. Motor de importación (A) y normalización (B)

### 5.1 Problema (de la auditoría)
Los libros son bloques apilados o lado a lado, con encabezados mal rotulados. **No se puede leer "tabla = hoja".**

### 5.2 Enfoque: detección de bloques por anclas + perfil de mapeo

1. **Escaneo:** `openpyxl` (nunca ejecuta macros; se rechaza `.xlsm`) → por hoja se obtienen **regiones rectangulares contiguas** (bloques) separadas por filas/columnas vacías.
2. **Clasificación del bloque** por su fila de encabezados (conjunto de columnas, tolerante a mayúsculas/acentos/typos) contra el **catálogo de bloques** del perfil. Ej.: `{Canal, Monto Venta, Piezas, Pacientes, Pedidos, Ticket Promedio, Producto, Share}` → `canal_resumen`.
3. **Sub-bloques apilados** por filas-ancla ("YoY", "MoM", nombre de canal/línea, "AE-A"…) definidas en el perfil.
4. **Bloques lado a lado:** se parten por columnas vacías y por repetición del primer encabezado ("Sivec" aparece dos veces → dos bloques).
5. **Mapeo de columnas aprobado:** cada columna del perfil tiene lista de alias. Si un encabezado **no** coincide con certeza (> umbral) → estado `needs_confirmation`; **nunca** se asigna automáticamente. La confirmación se guarda y se reutiliza (`profiles/<unidad>/<version>.yaml`).
6. **Salida normalizada:** tablas largas (`pandas`) con tipos correctos (moneda, %, `hh:mm:ss`→segundos, texto) y la celda de origen por fila.

### 5.3 Perfiles de importación (YAML, versionados)

```yaml
# profiles/aetops/mensual.yaml
profile: aetops-mensual
version: 1
blocks:
  panorama:
    sheet: Base
    anchor: {text: "Yoy", col: B}          # ancla de inicio
    header: [Año, Monto Venta, Piezas, Pacientes, Pedidos, Ticket Promedio, Producto Vendidos]
    derived: {Size B: "Piezas/Pacientes", V. Paciente: "Monto Venta/Pacientes"}
  canal_yoy:
    sheet: Base
    repeat_by_anchor: [APP FESA, ECOMMERCE, LLAMADAS GOOGLE, WHATSAPP]
    rows_per_group: {anterior: 1, actual: 1, delta: 1}
  productos:
    sheet: "Tablas"
    split_side_by_side: true
aliases:
  "Piezas Vendidas": Piezas
  "Producto": Producto Vendidos      # en la hoja de canal, "Producto" = # productos
```

Los perfiles son **datos**, no código: agregar un cambio de estructura = editar YAML + prueba, sin tocar el motor.

### 5.4 Validación de periodo (lección de la auditoría)
El importador **extrae el periodo declarado** (encabezados "Venta Agosto", nombres de hoja, nombre de archivo) y lo compara con el periodo elegido por el usuario. Además detecta **bloques duplicados** (p. ej. "Agosto" = "Septiembre" idénticos). Resultado → hallazgo `PERIOD_MISMATCH` / `IDENTICAL_PERIODS` (§7).

---

## 6. Motor de cálculo (C)

- Funciones **puras y deterministas**; entrada = tablas normalizadas, salida = `Table`/`Value` con lineage. Sin I/O, sin red, sin reloj.
- **Una sola implementación** por indicador, en `calc/indicators.py`; mensual y trimestral la comparten. La diferencia entre formatos está en **qué comparaciones se piden** (`Comparison`), no en la fórmula.

| Indicador | Fórmula | Manejo de borde |
|---|---|---|
| Ticket Promedio | Monto ÷ Pedidos | Pedidos = 0 → `missing` ("n/d"), no 0 |
| Size B | Piezas ÷ Pacientes | ídem |
| V. Paciente | Monto ÷ Pacientes | ídem |
| %Δ | (Act − Ant) ÷ Ant | Ant = 0 o missing → `missing` con motivo; Ant < 0 → bandera |
| Delta ($) | Act − Ant | Ant missing → **Act completo** + bandera `NEW_ITEM` (como el PPTX Nov 2025) |
| Share | Parte ÷ Total | Denominador configurable (§12); suma ≠ 100 % ±tolerancia → advertencia |
| Top N / crecimiento / decrecimiento | Orden por Delta | N y exclusión de filas en 0 configurables |

- **Reconciliación:** `Σ canales = Σ líneas = Σ categorías = total panorama` (tolerancia configurable). Si no cuadra → hallazgo bloqueante o advertencia según regla.
- **Versión de metodología** (`ruleset: "2026.1"`) sellada en cada resultado e historial.

---

## 7. Motor de validación (D)

Reglas como objetos con `id`, `severity` (`block` / `warn` / `info`), mensaje y evidencia (celdas). Se ejecutan después de importar y después de calcular.

| ID | Qué detecta | Severidad |
|---|---|---|
| `PERIOD_MISMATCH` | Periodo declarado en el Excel ≠ periodo seleccionado | block |
| `IDENTICAL_PERIODS` | Dos periodos de comparación con cifras idénticas | block |
| `MISSING_COMPARISON` | Falta el periodo de comparación que exige la plantilla (YoY/MoM) | block (no se generan comparativos incompletos) |
| `SHARE_ZERO` | Columna Share toda en 0 (valor pegado) → se recalcula y se avisa | warn |
| `COLUMN_UNMAPPED` | Encabezado sin mapeo aprobado | block hasta confirmar |
| `TOTALS_MISMATCH` | No cuadran totales entre tablas | warn/block |
| `DUPLICATE_KEY` | Producto/Sivec duplicado | warn |
| `NEGATIVE_VALUE` | Venta/piezas negativas | warn |
| `FORMULA_MASKS_MISSING` | Celda con `IFERROR(...,0)` que oculta faltante | info |
| `LABEL_CROSSED` | Rótulo de diapositiva incongruente con el contenido (Líneas↔Canales) | warn (en plantilla) |

La pantalla de revisión muestra los hallazgos con su evidencia; **no se habilita "Generar" con hallazgos `block` abiertos**.

---

## 8. Narrativa (E)

- **Entrada exclusiva:** `Table`/`Value` ya calculados y validados, **agregados** (sin filas de pacientes ni archivos completos). Se envía solo lo mínimo; el envío a un servicio externo es **opt-in explícito** por reporte.
- **Salida estructurada**, no texto libre: cada afirmación = `{texto, tipo, evidencia[]}` con `tipo ∈ {hecho, interpretación, hipótesis, info_insuficiente}`. Un verificador automático comprueba que **cada número del texto exista en `evidencia`**; si no, se descarta la frase.
- Prohibido atribuir causa sin dato (p. ej. "por falta de inventario"); las hipótesis salen marcadas.
- **Edición humana** obligatoria antes de generar: la UI muestra el texto por diapositiva, editable; lo editado se guarda como `edited_by_user` en el historial.
- **Modo sin IA:** plantillas de frases deterministas ("X crece +N% vs …") como respaldo; la herramienta funciona completa sin IA.

---

## 9. Generación PPTX (F) y PDF (G)

### 9.1 Plantillas
Las **plantillas son los PPTX originales**, limpiados una sola vez (datos de ejemplo vaciados, logos y diseño conservados), guardadas en `templates/<formato>/<version>/template.pptx`. Cuatro formatos independientes: `aetops-mensual`, `aetops-trimestral`, `glp1-mensual`, `glp1-trimestral`.

### 9.2 Especificación de diapositiva (YAML) — separa plantilla de datos
```yaml
# templates/aetops-mensual/1/spec.yaml
slides:
  - id: panorama
    slide: 1
    bindings:
      - shape: "Tabla 3"            # nombre del shape en el PPTX
        table: aetops.panorama.yoy_mom
        rows: fixed                  # filas fijas: solo se sustituye texto
        format: {Monto Venta: money0, "Ticket Promedio": money0, "Size B": dec2}
        delta_row: {style: conditional_color}
      - shape: "CuadroTexto 6"
        text: narrative.panorama
  - id: productos
    slide: 6
    bindings:
      - shape: "Tabla 3"
        table: aetops.productos.top
        rows: {mode: fit, min: 8, max: 20}   # ajusta nº de filas (clona/elimina)
        overflow: shrink_font_then_split
```

### 9.3 Mecánica de relleno
- Se **sustituye el texto del primer *run*** (se conserva fuente, tamaño y color); **no** se recrean tablas ni se rasteriza nada → tablas y textos siguen **editables**.
- **Formato condicional:** regla `delta_color(valor)` → verde / rojo / amarillo aplicada con el relleno de celda, con umbral configurable (default: >0 verde, <0 rojo, ==0 amarillo).
- **Filas variables:** clonar/eliminar `<a:tr>` hasta `n`; la altura total debe caber en el área de la diapositiva.
- **Gráfica `chartEx` (embudo GLP-1):** se actualizan los datos del XML del gráfico (`chartEx1.xml` + libro incrustado); se conserva como objeto nativo.
- **Notas manuales** (p. ej. "afectación de 10 minutos"): campo por reporte, aplicado a cada diapositiva que tenga ese shape.
- **Diapositivas opcionales** (p. ej. "Causas de la caída" en Nov 2025): se incluyen/omiten según la configuración y datos disponibles.

### 9.4 PDF
`soffice --headless --convert-to pdf` sobre el **mismo PPTX final**. Un solo sistema de render para PDF y para QA visual.

### 9.5 Fuentes (riesgo abierto)
Las plantillas usan **Aptos Narrow**, que **no se puede redistribuir**. Sin ella LibreOffice sustituye por una fuente más ancha y el PDF difiere del PowerPoint real (ya se observó desbordamiento en el original). Opciones: (a) instalar Aptos en la imagen Docker con licencia propia; (b) sustituir por una métrica equivalente (p. ej. *Liberation Sans Narrow*) **en PDF y QA**, dejando el PPTX con Aptos; (c) aceptar y documentar la diferencia. **Decisión del usuario** (§13).

---

## 10. Validación visual / QA (antes de habilitar la descarga)

1. PPTX → PDF → PNG por diapositiva (LibreOffice + `pdftoppm`).
2. **Chequeos automáticos**
   - Texto fuera de su cuadro / cortado: se estima altura requerida vs. alto del shape.
   - Tabla que sobrepasa el área útil (límite = parte superior del pie de página).
   - Elementos fuera del lienzo o superpuestos (intersección de cajas, excepto lo declarado como decorativo).
   - Celdas con texto envuelto > N líneas.
   - Diapositiva vacía o con marcador sin rellenar (`{{…}}`).
3. **Comparación contra el original:** SSIM/diferencia de imagen sobre **elementos estáticos** (logos, barras, pie) para detectar plantilla alterada; el contenido variable se valida estructuralmente (mismas tablas, mismas columnas).
4. Resultado → `qa_report.json` + miniaturas en la UI. **Falla de QA bloquea la descarga** (se puede anular con motivo registrado).

---

## 11. Historial (H), API y seguridad

### 11.1 Historial
SQLite + carpeta de archivos. Registro **inmutable** por corrida:

| Campo | Contenido |
|---|---|
| id, creado_en, usuario | |
| unidad, periodicidad, ejercicio, periodo | |
| archivos fuente | nombre, tamaño, **SHA-256** (se guarda copia) |
| plantilla / spec / perfil / metodología | versiones |
| hallazgos de validación | snapshot |
| resultados | `Table` serializadas con lineage |
| narrativa | generada y editada |
| salidas | PPTX, PDF, `qa_report`, hashes |

"Regenerar" crea **una versión nueva**; nunca sobrescribe (clave `(periodo, versión)`).

### 11.2 API (borrador)
| Método | Ruta | Función |
|---|---|---|
| POST | `/runs` | Crea corrida (unidad, periodicidad, periodo) |
| POST | `/runs/{id}/files` | Sube Excel (valida extensión, tamaño, firma ZIP; rechaza `.xlsm`) |
| GET | `/runs/{id}/mapping` | Bloques y columnas detectados + pendientes de confirmar |
| PUT | `/runs/{id}/mapping` | Confirma/ajusta mapeo (opcional: guardar perfil) |
| POST | `/runs/{id}/compute` | Calcula + valida → KPIs, hallazgos, lineage |
| GET | `/runs/{id}/kpis/{key}/lineage` | Origen de un KPI |
| POST | `/runs/{id}/narrative` | Genera borrador (opt-in IA) |
| PUT | `/runs/{id}/narrative` | Guarda texto editado y notas |
| POST | `/runs/{id}/render` | PPTX → PDF → QA |
| GET | `/runs/{id}/download/{pptx\|pdf}` | Descarga (solo si QA aprobada) |
| GET | `/history` | Lista y versiones |

### 11.3 Seguridad y privacidad
- Procesamiento **local en el servidor propio**; sin servicios cloud por defecto. Si se activa IA: solo **agregados**, nunca el Excel, y se registra qué se envió.
- Subidas: límite de tamaño, verificación de tipo real (ZIP/OOXML), **macros no se ejecutan** (`openpyxl` no las ejecuta; `.xlsm` rechazado), nombres saneados, directorio aislado por corrida.
- Sin datos sensibles en logs (se registran IDs y hashes, no contenido).
- Conversión con LibreOffice en proceso aislado (usuario sin privilegios, sin red, tiempo límite).
- Autenticación: **fuera de alcance del MVP**; el modelo guarda `usuario` desde el primer día para añadirla (decisión §13).

---

## 12. Parámetros configurables (resuelven las preguntas abiertas)

`config/rules.yaml` con valores por defecto sacados de los originales:

| Parámetro | Default | Origen |
|---|---|---|
| `percent_decimals` | por tabla (GLP-1: 0; productos: 2; tráfico: 1) | PPTX |
| `money_decimals` | 0 (AETOPS), centavos opcional | PPTX |
| `top_n_productos` | 20 (tabla) / 10 (crec./decrec.) | PPTX |
| `exclude_zero_both_periods` | `false` (Agosto muestra $0) | PPTX |
| `delta_color_thresholds` | >0 verde, <0 rojo, 0 amarillo | PPTX |
| `share_denominator` | total del periodo (no de filas mostradas) | **P** a confirmar |
| `totals_tolerance` | 0.5 % | propuesta |
| `new_item_delta` | monto completo + bandera | PPTX Nov 2025 |

---

## 13. Pruebas

| Capa | Qué se prueba | Cómo |
|---|---|---|
| **Cálculo** | Fórmulas contra valores conocidos | Dorados desde los PPTX de ejemplo: Size B 1.67, V.Paciente $10,312.24, ticket $8,101, %Δ +67 %, delta Prolia $209,173… **tolerancia 0** |
| **Importador** | Columnas renombradas, hojas faltantes, vacíos, duplicados, negativos, formatos numéricos, bloques movidos | Excel sintéticos generados en el test + los de ejemplo |
| **Validador** | Cada regla del §7 con caso positivo y negativo | Incluye `IDENTICAL_PERIODS` con el caso real "Agosto = Septiembre" |
| **PPTX** | Se abre; tablas siguen siendo tablas; textos editables; sin marcadores sin rellenar; `chartEx` presente | `python-pptx` + inspección XML |
| **PDF** | Mismo nº de páginas; texto del PDF = texto del PPTX | `pdftotext` |
| **QA visual** | Detecta desbordamiento provocado a propósito | Casos negativos construidos |
| **Regresión** | AETOPS no altera GLP-1; mensual no rompe trimestral; cambiar plantilla no cambia KPIs | Hash de resultados de `calc` antes/después de tocar plantillas |
| **E2E** | Excel → PPTX+PDF con QA verde | Por cada uno de los 4 formatos |

Los criterios de aceptación del prompt maestro se marcan **solo con evidencia** (log de pruebas + capturas) en `docs/EVIDENCIA/`.

---

## 14. Estructura de repositorio

```
backend/
  app/ api.py  deps.py
  importer/   scan.py  blocks.py  mapping.py  period.py
  normalizer/ models.py  coerce.py
  calc/       indicators.py  tables_aetops.py  tables_glp1.py  lineage.py
  validator/  rules.py  runner.py
  narrative/  facts.py  verify.py  fallback.py  llm.py
  pptx/       fill.py  spec.py  conditional.py  chartex.py  fit.py
  pdf/        convert.py
  qa/         render.py  checks.py  compare.py
  history/    db.py  store.py
profiles/     aetops/ glp1/        # perfiles de importación (YAML)
templates/    aetops-mensual/1/{template.pptx,spec.yaml}  …(4 formatos)
config/       rules.yaml
frontend/     (la UI actual evoluciona; consume la API)
tests/        unit/ integration/ e2e/ golden/
docs/         ARQUITECTURA.md  DIAGNOSTICO_FASE1.md  MATRIZ_TRAZABILIDAD.md
Dockerfile    docker-compose.yml  requirements.txt
```

La app web estática actual se **conserva** (no se sobrescribe) mientras `frontend/` migra gradualmente; GitHub Pages seguirá sirviendo la versión estática hasta que el backend esté desplegado.

---

## 15. Plan de implementación

| Fase | Entregable | Criterio de salida |
|---|---|---|
| **4a** | Esqueleto: modelos, `calc` AETOPS panorama + canales + líneas, importador por bloques con perfil `aetops-mensual` | Pruebas doradas del panorama y canales en verde |
| **4b** | Resto de tablas AETOPS (productos, categorías, negados), validador, perfil trimestral | Dorados completos AETOPS |
| **4c** | GLP-1 (importador + `calc`) | Dorados GLP-1 |
| **5a** | Relleno PPTX AETOPS mensual con plantilla real + PDF + QA | Descarga habilitada con QA verde en ejemplo |
| **5b** | Otros 3 formatos | E2E verde ×4 |
| **6** | Narrativa estructurada + verificador + edición | Ninguna cifra sin evidencia |
| **7–8** | Historial/UI, pruebas de regresión, documentación y manual | Criterios §16 del prompt con evidencia |

---

## 15.1 Decisiones confirmadas (2026-11-02)

| # | Tema | Decisión |
|---|---|---|
| 1 | Despliegue del backend | **Docker local o en un servidor interno.** GitHub Pages (estático) no puede ejecutar Python: seguirá sirviendo solo la versión estática actual hasta que el backend esté disponible. |
| 2 | Fuente Aptos Narrow | **Aprobado:** fuente de métrica equivalente solo para PDF y revisión visual; el PPTX conserva Aptos Narrow. |
| 3 | IA externa | **Proveedor: Cohere**, siempre **opt-in por reporte**, con modo determinista como valor por defecto (ver §8.1). |
| 4 | GLP-1 trimestral | **Aprobado:** basarlo en el formato mensual con comparativo trimestral; se confirma cuando exista un PPTX de referencia. |

### 8.1 Narrativa con Cohere (implementado, opcional)

La aplicación corre en el navegador (GitHub Pages), así que **la llamada a Cohere sale del navegador del usuario con su propia clave** (`POST https://api.cohere.com/v2/chat`); no hay servidor intermedio.

- **Clave de API:** la escribe el usuario en la pantalla de revisión. Vive en `sessionStorage` (se olvida al cerrar la pestaña) o, si lo pide, en `localStorage` de ese navegador. **Nunca** va al repositorio, a los workflows ni al historial. Quien comparta el equipo comparte la clave guardada: se recomienda no marcar «Recordar» en equipos compartidos.
- **Qué sale del navegador:** únicamente el **texto de los párrafos ya calculados y verificados** (cifras agregadas, nombres de líneas, canales y productos), mostrado en pantalla **antes** de enviarlo, con confirmación explícita. Nunca el Excel, filas de pacientes o pedidos, ni el contexto escrito por el equipo. Lo enviado y lo recibido queda en `ia_log.json` junto al reporte.
- **Qué puede hacer la IA:** solo mejorar la **redacción**. Cada respuesta pasa por `verify_rewrite`: se descarta si **quita o agrega una cifra**, usa vocabulario causal, incluye enlaces o crece más de 1.5×; entonces queda el texto original. Las cifras vuelven a ponerse en negrita automáticamente.
- **Modelo:** configurable en pantalla (por defecto `command-a-03-2025`). Se pide JSON estructurado (`response_format: json_object`), una llamada por sección.
- **Descubrimiento único (implementado, opcional): una hoja completa, con la misma estructura cada mes y contenido que no repite el resto de la presentación.**
  - *Hoja de hechos* (`narrative/facts.py`, ~90–100 frases deterministas con id, tema y bandera `nuevo`). `nuevo=false` = lo que ya muestran las otras diapositivas (panorama, canales, líneas, categorías, productos, negados…); `nuevo=true` = lo que **ninguna otra diapositiva muestra**: descomposición volumen/precio por grupo, productividad por canal y línea, tasa de negado por línea, pacientes nuevos frente a recurrentes, concentración de pacientes, estados, mezcla canal × línea, canasta (pedidos de 1 vs 2+ productos), calendario (quincenas), tasas de add to cart por fuente/dispositivo/edad/sexo, pedidos por mil visitas por estado, y tendencias del historial (el «patrón» entre meses). Los cruces con filas crudas se calculan en `raw/*.py` (`extras`).
  - *Estructura fija:* titular + «Lo que dicen los datos» + «Lo que significa» + «Hipótesis a validar» (con «qué validar») + «Qué haríamos», más la **evidencia citada** textual a la derecha (`deck/extras.py::add_discovery_slide`).
  - *Verificación* (`verify_discovery`): cada texto cita hechos que existen y solo usa cifras de los hechos citados (el signo `-` cuenta; el `+` es opcional); sin vocabulario causal ni enlaces; **titular, datos, significado e hipótesis deben apoyarse en al menos un hecho nuevo**; en total, al menos dos hechos nuevos y dos temas distintos; las hipótesis traen qué validar. Al guardar, el servicio vuelve a verificar (la interfaz no puede saltarse la regla).
  - *Validación del usuario:* ve qué se envía (marcado «nuevo» / «ya en el reporte»), revisa la evidencia de cada parte, edita, desmarca y valida explícitamente. «Buscar otro ángulo» pide a la IA evitar los ya propuestos. Lo enviado y recibido queda en `ia_log.json`.
- **Redacción más humana:** el modo «Redactar mejor» admite tres estilos (ejecutivo cercano, conversacional profesional, narrativo) y el prompt pide variar el arranque de las frases, usar conectores naturales y evitar muletillas de reporte; las cifras siguen verificadas una a una.
- Sin clave o sin confirmación, todo funciona con el texto determinista.
- Antes de usarlo con información confidencial real, **revisar los términos de retención y uso de datos de Cohere** y la política interna de la empresa.
- Límite conocido: algunas redes corporativas bloquean la conexión a `api.cohere.com`; si el navegador no puede conectarse, la herramienta lo dice y sigue con el texto determinista.

## 16. Riesgos y decisiones pendientes del usuario

| # | Tema | Recomendación |
|---|---|---|
| 1 | ~~Despliegue del backend~~ → **resuelto** (§15.1) | Docker local/servidor interno |
| 2 | ~~Fuente Aptos Narrow~~ → **resuelto** (§15.1) | Métrica equivalente en PDF/QA |
| 3 | **Autenticación** | Fuera del MVP; esquema listo para añadirla |
| 4 | ~~IA externa~~ → **resuelto**: Cohere, opt-in (§8.1) | Revisar términos de datos antes de usar con información real |
| 5 | ~~GLP-1 trimestral~~ → **resuelto** (§15.1) | Basado en el mensual; confirmar con PPTX |
| 6 | Gráfica `chartEx` | Editar su XML; si algún cliente no la abre, degradar a tabla |
| 7 | Denominador de Share en GLP-1 | Total del periodo; confirmar |

---

## 17. Implementación de Fase 1 (modelo y línea base) — añadido

Fuente de verdad: `docs/fase1/ESPECIFICACION_FASE1_REPORT_INTELLIGENCE_FINAL.md`. Este apartado solo registra lo que **ya existe en el código**; no cambia el diseño de §1–§16.

| Pieza | Ubicación | Qué hace hoy |
|---|---|---|
| Hallazgo extendido | `backend/app/models.py` (`Finding`) | Siete campos opcionales por palabra clave; `severity` intacto (ver `docs/MODELO_HALLAZGOS.md`) |
| Configuración como datos | `backend/app/config/` (4 JSON + cargador/validador) | Solo carga y valida estructura; **nada la consume todavía** (ver `docs/CONFIGURACION_FASE1.md`) |
| Versiones | `backend/app/version.py` | Lee versión del modelo de hallazgos y de cada JSON; `app` y `motor` quedan en `None` |
| Línea base | `tools/capture_baseline.py`, `tests/regression/` | Foto del motor y huellas del deck sobre los machotes sintéticos (ver `docs/LINEA_BASE_FASE1.md`) |
| Fixtures sintéticas | `tools/make_fixtures_fase1.py`, `tests/fixtures/fase1/` | Deterministas, con manifiesto y `sintetico: true` |

El patrón de configuración como dato ya existía (`profiles/*.yaml`, `importer/profile.py`); la configuración de Fase 1 lo sigue, en JSON, dentro de `backend/app/` para que `tools/build_site.py` la empaquete sin cambios. No se modificaron pipeline, reglas actuales, narrativa, plantillas ni importadores.

### 17.1 Motor de reglas (Fase 2A) — añadido

`backend/app/validator/motor.py` y módulos asociados (ver `docs/MOTOR_REGLAS.md`, con diagrama). Flujo: lector existente (`raw/common.read_tables`) → `validator/normalizar.py` (`Contexto` de solo lectura) → `motor.ejecutar()` (catálogo en `config/reglas.json`) → reglas (`rules_datos.py`, `rules_conc.py`, `rel_pedidos_carritos.py`) → `Resultado` → `a_hallazgos()` → `Finding`. Ningún servicio lo consume todavía.
