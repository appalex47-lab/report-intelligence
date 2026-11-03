# Report Intelligence

Reportes ejecutivos **AETOPS** y **GLP-1** (Excel → PPTX) con cálculos deterministas, narrativa verificada, resumen ejecutivo,
recomendaciones, historial y tendencias.

**Todo corre en GitHub, sin servidor ni localhost**: la aplicación es un sitio de **GitHub Pages**; el motor de cálculo (Python)
se ejecuta **dentro de tu navegador** (Pyodide). Los Excel y los reportes **nunca salen de tu equipo**.

## Puesta en marcha (una sola vez)

1. En GitHub: **Settings → Pages → Build and deployment → Source: _GitHub Actions_**.
2. Haz merge a `main` (o ejecuta **Actions → Publicar en GitHub Pages → Run workflow**). El workflow arma el sitio y lo publica en
   `https://<usuario>.github.io/<repositorio>/`.
3. Abre esa dirección. La primera vez carga el motor (unos segundos; después queda en caché).
4. Pestaña **Plantillas**: carga una vez los PPTX originales (AETOPS mensual/trimestral y GLP-1 mensual/trimestral). Se guardan en
   tu navegador; no se publican en el repositorio porque llevan marca y datos.

## Uso

**Cargar → Validar → Metas y contexto → Revisar narrativa → Generar.**

- Entrada: el libro de datos crudos (`ventas`, `catalogo`, `negados` y, en GLP-1, `trafico`; ver `docs/CONTRATO_DATOS.md`) o los
  machotes por bloques. La pantalla de carga descarga el machote del periodo.
- La meta general es obligatoria en AETOPS y opcional en GLP-1. El contexto del equipo sale en el resumen, marcado como no verificado.
- Cada texto de la narrativa se puede editar; toda cifra nueva se verifica contra los datos.
- Se descarga el **PPTX** con tablas y textos editables.
- El **historial** (inmutable, con versiones) se guarda en tu navegador; se puede exportar e importar (pestaña *Historial*).

## Qué hay (y qué no) en la versión de GitHub

| | En el navegador (Pages) | Con LibreOffice (Docker / CI) |
|---|---|---|
| Validación, cálculos, narrativa, resumen, recomendaciones, historial | ✅ | ✅ |
| PPTX editable | ✅ | ✅ |
| QA estructural (tablas, imágenes, texto viejo, cifras sin evidencia, estimación de desborde) | ✅ | ✅ |
| PDF y QA visual (desborde y colisiones renderizados) | ❌ | ✅ |

El navegador no puede ejecutar LibreOffice. Para el **PDF** hay un flujo opcional en GitHub: **Actions → «PDF en GitHub»**
(sube el `.pptx` a `convertir/` en un repositorio privado y descarga el PDF del artefacto). O abre el PPTX en PowerPoint → *Guardar como PDF*.

## Desarrollo

```bash
pip install -r requirements.txt
python -m pytest tests/unit -q                     # las pruebas con plantillas reales se omiten si no están
python tools/build_site.py --out _site             # arma el sitio estático
python tools/make_realistic_samples.py --salida data/ejemplos   # datos de ejemplo (inventados) a escala real
```

- Motor y reglas: `backend/` (ver `backend/README.md`, `docs/`).
- Servidor opcional (Docker, con PDF y QA visual): `docker-compose up` — no es necesario para usar la aplicación.
- La app anterior (JavaScript) queda en `legacy/` y se publica en `/legacy/`.
