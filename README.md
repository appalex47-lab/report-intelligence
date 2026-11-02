# Report Intelligence

Aplicación web para automatizar reportes ejecutivos **AETOPS** y **GLP-1**.

100 % estática · Compatible con **GitHub Pages**.

---

## Demo / uso

1. Abre la app en el navegador.
2. **Generar reporte** → elige unidad (AETOPS / GLP-1) y periodo.
3. Carga el Excel operativo o el machote.
4. **Procesar y validar** → revisa KPIs.
5. **Generar PPTX** (descarga en el navegador).

Los cálculos son determinísticos (JavaScript). Excel es la fuente de datos; el motor de cálculos es la fuente de verdad.

---

## Stack

| Capa | Tecnología |
|------|------------|
| UI | HTML5, CSS3, Alpine.js |
| Excel | SheetJS (xlsx.js) |
| Cálculos | JavaScript puro |
| PPTX | PptxGenJS |
| Historial | localStorage |
| Hosting | GitHub Pages (estático) |

No requiere backend ni Python en el servidor.

---

## Estructura

```
report-intelligence/
├── index.html
├── css/styles.css
├── js/
│   ├── app.js
│   ├── import-engine.js
│   ├── calculations/
│   │   ├── common.js
│   │   ├── aetops.js
│   │   └── glp1.js
│   └── generators/
│       ├── pptx-aetops.js
│       └── pptx-glp1.js
├── data/                    # machotes de ejemplo
├── .nojekyll                # evita que Jekyll bloquee módulos ES
└── .github/workflows/pages.yml
```

---

## Despliegue en GitHub Pages

### Opción A — Repositorio dedicado (recomendado)

1. Crea un repo vacío en GitHub (ej. `report-intelligence`).
2. Sube **el contenido de esta carpeta** (no la carpeta padre):

```bash
cd report-intelligence
git init
git add .
git commit -m "Report Intelligence — app estática"
git branch -M main
git remote add origin https://github.com/<USUARIO>/report-intelligence.git
git push -u origin main
```

3. En el repo: **Settings → Pages**
   - Source: **GitHub Actions** (si usas el workflow incluido), **o**
   - Source: **Deploy from a branch** → branch `main` → folder `/ (root)`
4. Espera 1–2 minutos. La URL será:

```
https://<USUARIO>.github.io/report-intelligence/
```

### Opción B — Carpeta `/docs` en un repo existente

1. Copia el contenido de esta app a `docs/` en tu repo.
2. Settings → Pages → Deploy from branch → `main` → `/docs`.

### Importante

- Debe existir el archivo **`.nojekyll`** en la raíz publicada (ya incluido).
- Los paths son relativos (`css/`, `js/`); funciona en subrutas de GitHub Pages.
- La primera carga requiere red (CDN: Alpine, SheetJS, PptxGenJS).

---

## Uso local

```bash
cd report-intelligence
npx serve .
# o
python -m http.server 8080
```

Abre `http://localhost:3000` (o el puerto indicado).  
No abras `index.html` como `file://` si usas módulos ES: algunos navegadores los bloquean.

---

## Machotes

Incluidos en `data/`:

- `MACHETE_AETOPS_Report_Intelligence.xlsx`
- `MACHETE_GLP1_Report_Intelligence.xlsx`

También acepta los Excel operativos mensuales/trimestrales (hoja Base / hojas numeradas).

---

## Fórmulas AETOPS (motor)

| KPI | Fórmula |
|-----|---------|
| Size B | Piezas ÷ Pacientes |
| V. Paciente | Monto Venta ÷ Pacientes |
| Ticket Promedio | Monto Venta ÷ Pedidos |
| % Δ | (Actual − Anterior) ÷ Anterior |
| Share | Monto grupo ÷ Monto total |

Ranking productos: excluye venta 0 en ambos periodos, acumula ~80 % de la venta, tope 15, mínimo 8, empates se mantienen.

---

## Estado

| Fase | Estado |
|------|--------|
| Auditoría y arquitectura | ✅ |
| Importación Excel + cálculos + UI | ✅ |
| Generación PPTX (browser) | ✅ |
| PPTX/PDF de referencia (Python, offline) | ✅ (en `/artifacts`) |
| GitHub Pages | ✅ (esta carpeta lista) |
| Narrativa IA | ⏳ |
| QA formal / matriz de trazabilidad | ⏳ |

---

## Limitaciones conocidas

- La calidad del PPTX generado **en el navegador** (PptxGenJS) puede diferir del generador Python offline (gráficas como imagen, más slides).
- MoM depende de que el Excel traiga periodos distintos; si Agosto = Septiembre en el archivo, Δ MoM = 0 %.
- Historial solo en el navegador local (localStorage), no sincroniza entre dispositivos.
