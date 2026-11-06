# QA del PPTX: estructural y visual (Fase 5)

Las dos revisiones se mantienen **separadas** (spec §7): la estructural lee el archivo; la visual ve cómo se dibuja. Ninguna sustituye a la otra ni a la revisión humana de una muestra.

## 1. Revisión estructural (`backend/app/qa/pptx_export.py`)

Se ejecuta en cada generación, sobre el `.pptx` ya guardado (también en el navegador). Etiqueta fija: «Revisión estructural. La revisión visual requiere render.»

| Grupo | `id` | Severidad | Qué detecta |
|---|---|---|---|
| Paquete | `PPTX_ZIP` | error | ZIP ilegible o truncado, entradas duplicadas, rutas inseguras (`..`, `\`), partes obligatorias ausentes |
| | `PPTX_XML` | error | XML mal formado (el analizador no resuelve entidades externas ni accede a red) |
| | `PPTX_REL_ROTA` | error | relación a una parte inexistente |
| | `PPTX_HUERFANO` | warn | parte (diapositiva, imagen, gráfica) sin ninguna relación que la use |
| | `PPTX_IMAGEN` | error | imagen dañada o con firma incorrecta |
| | `PPTX_GRAFICO_VACIO` | error / info | gráfica sin series con datos; **info** si la plantilla ya la trae vacía |
| Diapositivas | `PPTX_TOKEN_TECNICO` | error | `{{`, `None`, `nan`, `Decimal(`, `RI_`, `KeyError`, `Traceback` (palabras completas: «Ninguna» o «Nanotecnología» no cuentan) |
| | `PPTX_DUPLICADO` | error | el mismo texto de ≥ 30 caracteres en dos formas de una diapositiva |
| | `PPTX_TEXTO` | warn | doble espacio (salvo el que ya trae la plantilla) |
| | `PPTX_FUENTE_MIN` | error | letra menor que `min(9 pt, mínimo de la plantilla)` |
| | `PPTX_FUENTE_INCONSISTENTE` | warn | familia de fuente ausente de la plantilla |
| | `PPTX_FUERA_DE_LIENZO` | error | forma fuera de la diapositiva (tolerancia 1 pt) |
| | `PPTX_SOLAPE_DECLARADO` | warn | dos recuadros de texto que se cubren más de la mitad |
| | `PPTX_TABLA_VACIA`, `PPTX_DIAPOSITIVA_VACIA`, `PPTX_FORMA_CERO` | warn | tabla sin texto, diapositiva sin contenido, forma con texto de ancho o alto 0 |

**No existe** (limitación L-1 de `IMPLEMENTACION_FASE5.md`): trazabilidad de cada cifra, recálculo de fórmulas, unidades y denominadores. AC-14 es **PARCIAL**.

**Calibración (0 falsos positivos):** 4 decks reales de referencia (AETOPS y GLP-1, mensual y trimestral; libros de ejemplo sintéticos; plantillas locales) → 0 hallazgos, salvo un `info` de la gráfica vacía heredada de la plantilla GLP-1. Sin calibrar con la plantilla, el umbral fijo de 9 pt marcaba 319 letras de GLP-1 como error: de ahí D5-1.

## 2. Revisión visual (`backend/app/qa/visual.py`, `tools/visual_qa.py`)

```
python tools/visual_qa.py deck.pptx --out carpeta [--plantilla template.pptx]
```
Salida 0 aprobada · 1 rechazada o error · 2 omitida (sin LibreOffice o `pdftoppm`; nunca «aprobada»). Genera un PNG por diapositiva, `informe.json` y `informe.html` (visor lado a lado, con el texto escapado).

| `id` | Origen | Qué detecta |
|---|---|---|
| `TEXT_OUT_OF_PAGE`, `OVERFLOW_INTO_FOOTER`, `TEXT_COLLISION`, `PDF_TEXT_MISMATCH` | `checks.check_render` (existente) | texto fuera de la página, invasión del pie, palabras superpuestas, texto del PPTX que no llega al PDF (LibreOffice recorta lo que sale de la página: aparece como `PDF_TEXT_MISMATCH`) |
| `VISUAL_DIAPOSITIVA_EN_BLANCO` | nuevo | render sin variación aunque el PPTX declare contenido |
| `VISUAL_GRAFICA_EN_BLANCO` | nuevo | una gráfica que se renderiza vacía |
| `VISUAL_CONTRASTE_BAJO` | nuevo | palabras con contraste < 2,5 en el render a 300 DPI |
| `VISUAL_INCONSISTENCIA_TITULO` | nuevo | título a más de 0,15 in de la mediana de las diapositivas del mismo diseño |

Límites: LibreOffice no es PowerPoint (Aptos Narrow se sustituye por Carlito); el contraste es un muestreo; no corre en el navegador.

## 3. Inspección visual de los decks generados

Se generaron con libros de ejemplo sintéticos y las plantillas locales, con render real, y se **miraron** (hoja de contacto de cada deck y diapositivas individuales). Las imágenes no se versionan: la plantilla lleva marca comercial y no se publica. Se pueden regenerar con `tools/visual_qa.py`. SHA-256 (16 primeros) de las hojas de contacto de esta inspección: AETOPS mensual `a11330618549b538`, AETOPS trimestral `952e771261e64f78`, GLP-1 mensual `2ec90be2bfd77f13`, GLP-1 trimestral `9caa883787eb254d`.

| # | Observación | Clase | Estado |
|---|---|---|---|
| V-1 | No se vieron textos cortados, solapes ni tablas desbordadas en las 49 diapositivas; la revisión automática también da 0 hallazgos | — | verificado en LibreOffice |
| V-2 | El primer criterio de contraste marcó 3 palabras blancas sobre azul (encabezado de la tabla de dispositivos, GLP-1) con relación 1,29: el «texto» detectado era un borde rojo de resaltado dentro de la caja | **defecto de la herramienta nueva** | corregido (D5-4) y fijado con una prueba de texto claro sobre fondo oscuro |
| V-3 | AETOPS mensual, diapositiva 1 (resumen ejecutivo): el último punto queda a 3,9 pt del pie (límite 1 pt para marcar desborde) | observación | sin desborde; vigilar si crece el resumen (el ajuste `fit()` ya lo acota) |
| V-4 | Algunos párrafos justificados dejan huecos anchos entre palabras (AETOPS, productos) y la tabla de negados tiene un espaciado de filas irregular | observación (estilo) | pertenecen a la plantilla; no se tocaron |
| V-5 | La plantilla GLP-1 trae una gráfica `chartEx` (embudo de Office) sin datos; en LibreOffice no se pinta y el embudo se dibuja con formas | **no verificable** sin PowerPoint | la revisión estructural la informa como `info` |

Defectos de los **reportes** encontrados: ninguno bloqueante. Defectos de las **herramientas nuevas** encontrados y corregidos: V-2, y los de §4.

## 4. Defectos hallados al probar las herramientas nuevas (todos corregidos)

| Defecto | Cómo se detectó | Corrección |
|---|---|---|
| Una diapositiva sin ninguna forma no entraba en la revisión (`PPTX_DIAPOSITIVA_VACIA` nunca saltaba) | prueba de defecto inyectado | se recorren todas las diapositivas |
| Un paquete con relación rota hacía lanzar una excepción a python-pptx al leer las diapositivas | prueba de relación rota | con el paquete roto no se leen las diapositivas y cualquier excepción es un hallazgo `PPTX_ZIP` |
| `revisar` visual lanzaba `BadZipFile` ante un archivo que no es PPTX | prueba de archivo no renderizable | el resultado es `error`, nunca una excepción ni «aprobada» |
| Umbral de letra fijo (9 pt) con 319 falsos positivos | calibración con decks reales | calibrado con la plantilla |
| Gráfica vacía heredada de la plantilla marcada como error | calibración con decks reales | se compara contra la plantilla |
