# Plantillas

La plantilla de cada formato es **el PPTX original publicado** (logos, barras, tipografías y tablas con su formato).
**No se versiona** (contiene marca y, en el original, datos comerciales): cópiala localmente.

| Formato | Ruta | Origen |
|---|---|---|
| AETOPS mensual (v1) | `templates/aetops-mensual/1/template.pptx` | `Resultados_AETOP_Agosto_2026.pptx` |

El relleno (`backend/app/deck/aetops_mensual.py`) sustituye el contenido **en su lugar** y falla con
`TemplateMismatch` si cambian los nombres de shapes o el tamaño de las tablas: una plantilla nueva requiere una
versión nueva (`.../2/`) y su especificación.

```bash
python -m backend.app.cli libro.xlsx --perfil mensual --periodo 2026-9 \
    --plantilla templates/aetops-mensual/1/template.pptx --salida salida/
```
