# Plantillas

La plantilla de cada formato es **el PPTX original publicado** (logos, barras, tipografías y tablas con su formato).
**No se versiona** (contiene marca y, en el original, datos comerciales). En la app web se cargan una vez en la pestaña **Plantillas** y quedan en el navegador; para el servidor/CLI se copian aquí. (En un repositorio privado se pueden publicar en `templates/<formato>/1/template.pptx` quitando la regla del `.gitignore`: el sitio las toma de ahí.)

| Formato | Ruta | Origen |
|---|---|---|
| AETOPS mensual (v1) | `templates/aetops-mensual/1/template.pptx` | `Resultados_AETOP_Agosto_2026.pptx` |
| AETOPS trimestral (v1) | `templates/aetops-trimestral/1/template.pptx` | `Resultados_AETOP_Q1_2026.pptx` |
| GLP-1 mensual (v1) | `templates/glp1-mensual/1/template.pptx` | `Resultados_GLP1_Agosto_2026.pptx` |

El relleno (`backend/app/deck/aetops_mensual.py`) sustituye el contenido **en su lugar** y falla con
`TemplateMismatch` si cambian los nombres de shapes o el tamaño de las tablas: una plantilla nueva requiere una
versión nueva (`.../2/`) y su especificación.

```bash
python -m backend.app.cli libro.xlsx --perfil mensual --periodo 2026-9 \
    --plantilla templates/aetops-mensual/1/template.pptx --salida salida/
```

Trimestral:

```bash
python -m backend.app.cli libro_q3.xlsx --perfil trimestral --periodo 2026-3 \
    --plantilla templates/aetops-trimestral/1/template.pptx --salida salida/
```

La plantilla trimestral trae rótulos fijos con el trimestre ("Venta Q1 Actual 2026"); el relleno los actualiza al periodo
pedido y el QA verifica que no sobreviva ningún "Q1" de la plantilla.
