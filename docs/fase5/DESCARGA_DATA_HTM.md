# INC-001 · descarga que termina en `data.htm` (investigación de la Fase 5)

`docs/INCIDENCIAS.md` (histórico, no se modifica) cerró INC-001 funcionalmente el 5 de noviembre de 2026 con la **causa raíz no determinada**. Esta fase repitió la investigación con experimentos y endureció el flujo.

## 1. Flujo que genera el archivo

Todo ocurre en el navegador: el motor (Pyodide, en un worker) escribe el PPTX en su sistema de archivos virtual → `worker.js` lo devuelve como `{name, buffer}` → `fetchFile()` → `download()` crea un `Blob`, un enlace `<a download>` y lo pulsa. **No hay ninguna petición de red en la descarga**, de modo que un `data.htm` solo puede salir de tres lugares: el nombre/tipo que se le pone al archivo, el contenido que devolvió el motor, o cómo el navegador (o la app que lo aloja) trata un `blob:`.

## 2. Experimentos (Chromium real, Playwright)

| Condición | Nombre sugerido por el navegador |
|---|---|
| Blob con tipo PPTX y `download="reporte.pptx"` | `reporte.pptx` |
| Blob con tipo PPTX **sin** `download` | `<uuid>.pptx` |
| Blob `text/html` con `download="reporte.pptx"` | `reporte.pptx` (manda el atributo) |
| Blob **sin tipo** y `download=""` | `<uuid>.txt` |
| `data:text/html` y `download=""` | `download.html` |
| `data:` con `download=undefined` | `undefined` |
| URL revocada justo antes del clic | `reporte.pptx` |
| Enlace sin `download` a una página HTML del servidor | navega; no descarga |

**Ninguna condición reproduce `data.htm`.** Con el frontend anterior a `67fd179`, el motor real y Chromium, la descarga ya entregaba un PPTX válido (INC-001, evidencia 3).

## 3. Hipótesis

| # | Hipótesis | Estado |
|---|---|---|
| H1 | El nombre del archivo dependía del motor y llegaba vacío o con otra extensión | Cubierta: la extensión sale ahora de la ruta pedida |
| H2 | El motor devolvía HTML (página de error) y se entregaba como `.pptx` | Cubierta: el contenido se valida contra su formato; el HTML se rechaza con un mensaje |
| H3 | Una URL de blob revocada a los 4 s antes de que un equipo o red lentos empezara a guardar | Cubierta: se revoca a los 60 s. No es la causa de `data.htm` en Chromium (el experimento no lo reproduce) |
| H4 | Un navegador integrado de otra app (WebView, redes sociales, correo, Teams) que no sabe guardar `blob:` y nombra el archivo por su cuenta | **No verificada** (no hay un WebView en este entorno). Mitigación: aviso previo en esos entornos |
| H5 | Un navegador o dispositivo distinto del probado | **No verificada**; solo se probó Chromium |

**Causa raíz: NO REPRODUCIDA ni demostrada.** Se dejó de depender de lo que no controlamos; no se afirma haber encontrado la causa.

## 4. Corrección

En `frontend/index.html` (`download()`):

1. **Nombre y extensión de lo pedido:** `reporte.pptx`, `x.pdf`, `narrative.json`… salen de la ruta que pidió la interfaz; lo que devuelva el motor solo aporta el nombre base (sin rutas, sin caracteres de control, ≤ 120 caracteres). Si la ruta no trae extensión (machote, historial) se usa la del motor.
2. **Validación del contenido antes de entregar:** `.pptx` y `.xlsx` (ZIP que empieza con `PK\x03\x04`, termina con su registro final y contiene `[Content_Types].xml`), `.pdf` (`%PDF-`), `.json` (analizable), `.png`, `.sqlite`; cualquier página HTML se rechaza. El usuario ve el motivo y no se descarga nada.
3. **MIME explícito** por extensión (antes solo PPTX y PDF).
4. **Revocación de la URL a los 60 s** (antes 4 s).
5. **Aviso** en navegadores integrados: «abre este sitio en Chrome o Safari» (precaución sobre H4).

## 5. Pruebas de regresión (`tests/e2e/test_descarga_regresion.py`, 20 casos, Chromium real)

Ejecutan la función `download()` **real** con respuestas del motor sustituidas: PPTX válido (se abre con python-pptx y los bytes coinciden); 8 nombres hostiles del motor (`data.htm`, `data.html`, `download`, vacío, nulo, `../../etc/passwd`, `reporte.txt`, `a/b\c.docx`) → siempre `*.pptx`, sin separadores; 6 contenidos inválidos (HTML en tres formas, vacío, ZIP truncado, ZIP con registro final pero sin presentación); ZIP que no es Office; PDF, JSON y PNG con su tipo y su validación; machote e historial sin extensión en la ruta; URL no revocada antes de 5 s; aviso en un WebView simulado.

**Defecto propio hallado por estas pruebas:** mi primera versión admitía extensiones de 2 a 5 letras y `sqlite` tiene 6: el historial se habría llamado `historial.sqlite.bin`. Corregido.

Además sigue vigente la prueba de punta a punta con el motor real (`tests/e2e/test_descarga_pptx.py`): descarga un `.pptx` real, ZIP íntegro, firma `504b0304`, se abre con python-pptx.

## 6. Límites

* La causa original **sigue sin explicarse**; si reaparece hay que abrir una incidencia con navegador, versión del sistema y el paso exacto.
* Solo se automatizó Chromium. Firefox, Safari y WebViews reales no se probaron (H4 y H5).
* El aviso de navegador integrado se basa en el agente de usuario, que puede no delatar a todos.
