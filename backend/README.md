# Backend — Fases 4a y 4b (motor AETOPS)

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
python tools/make_glp1_synthetic.py data/GLP1_sintetico_limpio.xlsx            # machote sintético GLP-1
```

## Qué hace
- `importer/`: detecta secciones YoY/MoM por anclas y las clasifica con el perfil `profiles/aetops/mensual.yaml`. Una columna sin mapeo aprobado **bloquea** (no se asigna a ciegas). Rechaza `.xlsm`.
- `calc/`: funciones puras con `Decimal`. Faltante ≠ cero; división entre cero → faltante. Ticket, Size B, V. Paciente, %Δ y Share se **recalculan**; lo pegado en el Excel solo se contrasta.
- `validator/`: `IDENTICAL_PERIODS`, `PERIOD_LABELS_INCONSISTENT`, `PERIOD_MISMATCH` (contra el periodo elegido), `MISSING_COMPARISON` (el formato exige YoY+MoM o solo YoY), `TOTALS_MISMATCH`, `TICKET_FORMULA_UNVERIFIED`, `PASTED_DIFFERS` (tolerante al redondeo del valor pegado), `SORT_ORDER`, `DUPLICATE_KEY`, `FORMULA_MASKS_MISSING` (`#N/A` + `IFERROR→0`), `COLUMN_UNMAPPED`.
- Productos: un producto sin venta previa es `new_item` (Delta = venta actual), no 0.
- `format.py`: único lugar donde se redondea (mitad hacia arriba, como Excel y los PPTX).

## Limitaciones conocidas
- Solo AETOPS. GLP-1 (4c) usará el machote sintético como fixture.
- Productos: se leen los bloques de `Tablas` tal como los arma el Excel; no se recalcula el Top desde el universo completo (hojas `Venta <mes>`).
- `Negados`: el segundo bloque de productos (duplicado en el mensual, distinto en el Q3) se ignora y no se valida todavía. Sin `config/rules.yaml`: tolerancias fijas en `validator/rules.py`.
- Ticket por canal: se usa el valor pegado (ver hallazgo en `docs/DIAGNOSTICO_FASE1.md` §4.3).
