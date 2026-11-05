# Registro de incidencias

Registro de incidencias de uso detectadas en la aplicación publicada, con su evidencia y estado. Una incidencia solo se marca **CERRADA** cuando existe evidencia de que el comportamiento esperado se obtiene en producción.

| ID | Incidencia | Estado | Cierre |
|---|---|---|---|
| INC-001 | «Descargar PPTX» (paso 5) entregaba `data.htm` | **CERRADA (resuelta funcionalmente)** | validación manual en producción, 5 nov 2026 |
| INC-002 | Tablas por grupos con una 5.ª línea (AE-D) invadían el pie (`OVERFLOW_ESTIMATED`) | CERRADA | PR #12 y #13; verificado con el archivo del usuario |
| INC-003 | Lámina «Conclusiones Clave» recortada contra el pie | CERRADA | PR #13 y #14; verificado con el archivo del usuario |

---

## INC-001 · «Descargar PPTX» entregaba `data.htm`

**Síntoma (reportado por el usuario):** en el paso 5, el botón «Descargar PPTX» descargaba un archivo `data.htm` en lugar de una presentación PowerPoint.

**Cambio aplicado:** commit `67fd179` (subido por el usuario), en `frontend/index.html` (`download()`) y `frontend/worker.js`: nombre de archivo de respaldo (`reporte.pptx`), comprobación de que el contenido de un `.pptx` empieza con la firma ZIP `PK` y tipo MIME explícito. No se hicieron cambios adicionales en el mecanismo de descarga.

**Causa raíz: no determinada.** No se logró reproducir `data.htm` en ningún caso:
- Con el motor real (Pyodide) en Chromium y con el frontend **anterior** a `67fd179`, la descarga ya entregaba un PPTX válido.
- Con respuestas simuladas, el código anterior sí tenía dos debilidades (sin nombre → `undefined.txt`; respuesta HTML entregada como `.pptx` sin aviso). El código actual las cubre: usa un nombre por omisión y rechaza lo que no es un ZIP.
- Hipótesis no verificadas: navegador o contexto de visualización distinto, o una respuesta HTML de la página servida en el momento del defecto.

### Evidencia

| # | Evidencia | Quién / cómo | Resultado |
|---|---|---|---|
| 1 | Recorrido completo con el motor real, frontend actual, libro sintético de septiembre | Automatizada local (Chromium + Pyodide 0.27.7) | `Resultados_AETOP_Septiembre_2026.pptx`, 142 580 bytes, firma `504b0304`, ZIP íntegro, 13 diapositivas |
| 2 | Ídem con el libro real del usuario (octubre) | Local | 144 582 bytes, `504b0304`, ZIP íntegro, 13 diapositivas, QA aprobado |
| 3 | Ídem con el frontend anterior a `67fd179` | Local | PPTX válido (no reproduce el defecto) |
| 4 | Prueba E2E versionada: `tests/e2e/test_descarga_pptx.py` + `descarga_pptx.mjs` | Automatizada; se omite con motivo si faltan Pyodide, Node/Playwright o la plantilla | 1 aprobada en la ejecución local; omitida en CI (documentado) |
| 5 | Archivo descargado en **Chrome para Android** desde el sitio publicado: `Resultados_AETOP_Octubre_2026_1.pptx` | Manual (usuario), revisado por el equipo | 147 810 bytes, firma `PK`, ZIP íntegro, 65 entradas, abre con python-pptx, 14 diapositivas |
| 6 | **Validación manual en producción** (5 nov 2026): la aplicación descarga un `.pptx`; ya no se descarga `data.htm`; el archivo abre correctamente en PowerPoint; las diapositivas se visualizan correctamente | **Declarada por el usuario** | Cierre funcional |

**Alcance de la evidencia:** los puntos 1 a 4 los ejecutó el equipo de desarrollo en un entorno sin acceso al sitio publicado; el punto 5 es un archivo real descargado de producción; el punto 6 (apertura en PowerPoint y verificación visual) es una validación manual del usuario, no automatizada.

**Límites que se conservan:**
- La prueba E2E no corre en CI (requiere una distribución local de Pyodide, la plantilla real y Playwright de Node). Se ejecuta localmente con `REPORT_PYODIDE_DIR`.
- Solo se automatizó AETOPS mensual en Chromium. No se probaron Firefox, Safari, GLP-1 ni AETOPS trimestral.
- La causa original de `data.htm` sigue sin explicación; si reaparece, abrir una incidencia nueva con navegador, versión y el paso exacto.

**Commits y PR relacionados:** `67fd179` (corrección de descarga), PR #14 (`2a4e803` prueba E2E, `4d847f0` registro de validación, `bc8660a` Conclusiones).

---

## INC-002 · Tabla con una 5.ª línea (AE-D) invadía el pie

**Síntoma:** el QA reportaba `OVERFLOW_ESTIMATED` en la lámina 6 «Tabla 2» con el catálogo del usuario (5 líneas).
**Causa:** la plantilla trae 4 grupos (18 filas); una 5.ª línea la lleva a 22 filas, y las celdas de relleno de la fila-título (NBSP a 18 pt) inflaban el alto mínimo de cada fila.
**Corrección:** `backend/app/deck/aetops_mensual.py` (`fill_grouped`), `pptx_ops.py` (`set_filler_font`, `compact_to_fit`), `qa/checks.py` (`row_content_floors`). Solo actúa si la tabla no cabe. En el trimestral, con más de 4 líneas se usa la misma tabla compactada en lugar de omitir la línea.
**Cierre:** PR #12 y PR #13; verificado con el archivo del usuario (QA aprobado y render sin recortes). Pruebas: `tests/unit/test_tabla_compacta.py`.

## INC-003 · «Conclusiones Clave» recortada contra el pie

**Síntoma:** con datos de octubre 2026 el texto de la lámina 12 invadía el pie y el QA marcaba `PDF_TEXT_MISMATCH`.
**Causa:** el patrón general separa todos los párrafos con un párrafo vacío, y un párrafo vacío toma 18 pt (tamaño por omisión). La plantilla original pone las cifras juntas.
**Corrección:** `conclusiones_paragraphs` (`aetops_mensual.py`) y `to_paragraphs_conclusiones` (`narrative/writer.py`): solo si el texto no cabe sobre el pie se usa el patrón de la plantilla; el encabezado «…:» se reconoce con o sin negritas (texto editado o reescrito con IA). Si cabe, el resultado no cambia.
**Cierre:** PR #13 y PR #14 (`bc8660a`); verificado con el archivo del usuario y con el PPTX descargado en Android.
