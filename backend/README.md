# Backend — Fases 4a–4c (motor AETOPS y GLP-1), 5a–5b (PPTX/PDF AETOPS mensual y trimestral) y narrativa v2

Implementa, según `docs/ARQUITECTURA.md`, para AETOPS: importador por bloques (`Base`, `Tablas`, `Negados`),
motor de cálculo (panorama, canales, líneas y categorías YoY/MoM; productos Top/crecimiento/decrecimiento;
negados por producto y por línea), validador y formato de presentación. Perfiles `mensual` y `trimestral`.
**Aún no genera PPTX/PDF ni tiene API** (Fases 5+).

```bash
pip install -r requirements.txt
python -m pytest -q                                    # pruebas (libro sintético)
REPORT_FIXTURES_DIR=/ruta/a/ejemplos python -m pytest  # + pruebas doradas con Excel reales
python -m backend.app.cli ruta/AETOPS_...xlsx --perfil mensual --periodo 2026-9   # resumen + hallazgos
python -m backend.app.cli ruta/AETOPS_Q3.xlsx --perfil trimestral --periodo 2026-3
python -m backend.app.cli data/GLP1_sintetico_limpio.xlsx --unidad glp1 --periodo 2026-9   # GLP-1
python tools/make_glp1_synthetic.py data/GLP1_sintetico_limpio.xlsx            # regenerar el machote sintético
```

## Qué hace
- `importer/`: detecta secciones YoY/MoM por anclas y las clasifica con el perfil `profiles/aetops/mensual.yaml`. Una columna sin mapeo aprobado **bloquea** (no se asigna a ciegas). Rechaza `.xlsm`.
- `calc/`: funciones puras con `Decimal`. Faltante ≠ cero; división entre cero → faltante. Ticket, Size B, V. Paciente, %Δ y Share se **recalculan**; lo pegado en el Excel solo se contrasta.
- `validator/`: `IDENTICAL_PERIODS`, `PERIOD_LABELS_INCONSISTENT`, `PERIOD_MISMATCH` (contra el periodo elegido), `MISSING_COMPARISON` (el formato exige YoY+MoM o solo YoY), `TOTALS_MISMATCH`, `TICKET_FORMULA_UNVERIFIED`, `PASTED_DIFFERS` (tolerante al redondeo del valor pegado), `SORT_ORDER`, `DUPLICATE_KEY`, `FORMULA_MASKS_MISSING` (`#N/A` + `IFERROR→0`), `COLUMN_UNMAPPED`.
- Productos: un producto sin venta previa es `new_item` (Delta = venta actual), no 0.
- `format.py`: único lugar donde se redondea (mitad hacia arriba, como Excel y los PPTX).

## Generación AETOPS mensual y trimestral (5a, 5b)
`build.py` → `deck/aetops_mensual.py` rellena **en su lugar** el PPTX original (11 diapositivas), `render.py` convierte a PDF con LibreOffice (fuente sustituta Carlito solo para el render, `docker/fonts.conf`) y `qa/checks.py` decide si se habilita la descarga.
- Con hallazgos bloqueantes del Excel **no se genera** (`ReportBlocked`).
- QA (error = descarga bloqueada): páginas PDF = diapositivas; texto fuera de página; contenido invadiendo el pie; palabras superpuestas; texto del PPTX ausente en el PDF; tablas/imágenes/cuadros distintos a la plantilla; barras/logos/pie distintos al render de la plantilla; datos viejos de la plantilla sin sustituir; marcadores sin rellenar. Las reglas se calibraron con el PPTX original (debe pasar sin errores).
- Tablas, textos e imágenes siguen siendo objetos de PowerPoint (nada se rasteriza).
- Plantilla: `templates/README.md` (no se versiona). **Trimestral** (`deck/aetops_trimestral.py`): compara solo contra el mismo trimestre del año anterior; ajusta los bloques de canales (con su fila separadora), el Top sin columna Sivec, las dos tablas de categorías (las 3 que más suman y las 3 que más restan en pesos) y la tabla de negados con su mini-tabla por línea; actualiza los rótulos "Venta Q1…" al trimestre pedido.
- El QA compara logos, barras y pie de página usando la **geometría real** de esos elementos en la plantilla (no zonas fijas).
- **Narrativa** (`narrative/`): `insights.py` calcula hallazgos (descomposición volumen/valor, aporte al crecimiento, cambio de participación, base pequeña, lectura mixta, negados vs venta); `aetops.py` los redacta al estilo del analista y ajusta el texto al cuadro; `writer.py` registra cada cifra y **verifica** que toda cifra tenga evidencia y que no haya vocabulario causal. Cada párrafo es hecho, interpretación (con su regla) o información insuficiente. Se exporta `narrative.json` para edición. Propósito y reglas: `docs/OBJETIVO_Y_NARRATIVA.md`.
- **Resumen ejecutivo y recomendaciones** (`narrative/executive.py`, `deck/extras.py`): se clona la diapositiva «Conclusiones» de la plantilla para añadir un *Resumen Ejecutivo* (inicio: dónde estamos, descubrimientos, qué hacer) y *Recomendaciones* (final: acción, por qué, escenario ilustrativo, seguimiento). Cada recomendación sale de una regla, con prioridad = impacto × accionabilidad. Si el Excel trae dos totales de negados que se contradicen (> 10 %), el reporte se bloquea.
- **Contexto del periodo** (`context=[...]`, `--contexto "…"`): texto del equipo en el resumen ejecutivo, marcado y sin verificar; nunca se descarta (cede el espacio de los hallazgos de menor prioridad).
- **Historial** (`history/store.py`, `--historial db.sqlite`): SQLite **inmutable** (triggers impiden UPDATE/DELETE); cada generación guarda KPIs, SHA-256 de fuentes/plantilla/PPTX/PDF, hallazgos, narrativa y contexto como una versión nueva. **Tendencias** (`narrative/trends.py`, `trends.json`): solo en la pantalla de revisión; con < 3 periodos contiguos dice *información insuficiente*.

## GLP-1 (4c)
- `importer/glp1_blocks.py` + `profiles/glp1/*.yaml`: localiza 17 tablas de las hojas 1–9 por el texto de su encabezado (no por posición), incluye bloques apilados, lado a lado, el bloque del periodo anterior y el embudo (sin encabezado).
- Una columna desconocida **dentro** de las esperadas bloquea; lo que está más allá (bloque vecino) se ignora. Erratas conocidas (`& de rebote`, `Carritos abadonados`) se aceptan con aviso.
- Un hueco en una tabla (`BLANK_ROW_INSIDE`) **bloquea**: leer solo hasta el hueco perdería datos en silencio.
- Share se recalcula (Σ del bloque). **%Δ y Ticket: se publica el valor pegado** porque, en los libros reales, ninguno equivale al recálculo (ver `DIAGNOSTICO_FASE1.md` §4.5); el recálculo queda como contraste.

## Limitaciones conocidas
- 5a/5b: AETOPS mensual y trimestral. **GLP-1 mensual y trimestral aún sin generador de PPTX** (los datos ya se importan y validan). La narrativa es determinista con insights verificados (sin IA). Sin mapa de calor en la tabla de negados (Excel).
- Categorías: la plantilla muestra 7 (YoY) u 8 (MoM); el original elige a mano cuáles. Se toman por venta (YoY) o por signo del cambio (MoM) y las omitidas se informan. **[P]** regla editorial.
- Los títulos cruzados Líneas/Canales del original se corrigen y se informa (`fix_titles=False` los conserva).
- Productos: se leen los bloques de `Tablas` tal como los arma el Excel; no se recalcula el Top desde el universo completo (hojas `Venta <mes>`).
- `Negados`: el segundo bloque de productos (duplicado en el mensual, distinto en el Q3) se ignora y no se valida todavía. Sin `config/rules.yaml`: tolerancias fijas en `validator/rules.py`.
- Ticket por canal: se usa el valor pegado (ver hallazgo en `docs/DIAGNOSTICO_FASE1.md` §4.3).

## Pantalla de revisión (API + frontend)

```bash
pip install -r requirements.txt
uvicorn backend.app.web.app:app --port 8000      # http://localhost:8000
```

Variables: `REPORT_RUNS_DIR` (corridas, def. `runs/`), `REPORT_HISTORY_DB` (def. `historial/historial.sqlite`),
`REPORT_TEMPLATES_DIR` (def. `templates/`; plantilla = `<unidad>-<periodicidad>/1/template.pptx`).

Flujo: Cargar → Validar → Metas y contexto → Revisar narrativa (edición con verificación de cifras) → Generar (QA; la descarga
se bloquea si el QA no aprueba) + pestaña Historial y tendencias. Metas: obligatorias en AETOPS, opcionales en GLP-1.
GLP-1 (mensual y trimestral): genera la presentación desde datos crudos (`ventas`+`catalogo`+`trafico`+`negados`), con resumen ejecutivo, recomendaciones, contexto del equipo, meta opcional e historial. Plantillas: `templates/glp1-mensual/1/` y `templates/glp1-trimestral/1/`.

Machotes de captura: `python tools/make_machotes.py --todos --periodo 2026-9 --salida machotes/` (o desde la pantalla de carga).

CLI con metas: `--metas metas.json` o `--meta total=33000000 --meta AE-A=21000000 …` (obligatorias al generar AETOPS).

Docker (`Dockerfile`, `docker-compose.yml`): **sin verificar** en este entorno.
