# Backend — Fases 4a, 4b y 4c (motor AETOPS y GLP-1)

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

## GLP-1 (4c)
- `importer/glp1_blocks.py` + `profiles/glp1/*.yaml`: localiza 17 tablas de las hojas 1–9 por el texto de su encabezado (no por posición), incluye bloques apilados, lado a lado, el bloque del periodo anterior y el embudo (sin encabezado).
- Una columna desconocida **dentro** de las esperadas bloquea; lo que está más allá (bloque vecino) se ignora. Erratas conocidas (`& de rebote`, `Carritos abadonados`) se aceptan con aviso.
- Un hueco en una tabla (`BLANK_ROW_INSIDE`) **bloquea**: leer solo hasta el hueco perdería datos en silencio.
- Share se recalcula (Σ del bloque). **%Δ y Ticket: se publica el valor pegado** porque, en los libros reales, ninguno equivale al recálculo (ver `DIAGNOSTICO_FASE1.md` §4.5); el recálculo queda como contraste.

## Limitaciones conocidas
- Productos: se leen los bloques de `Tablas` tal como los arma el Excel; no se recalcula el Top desde el universo completo (hojas `Venta <mes>`).
- `Negados`: el segundo bloque de productos (duplicado en el mensual, distinto en el Q3) se ignora y no se valida todavía. Sin `config/rules.yaml`: tolerancias fijas en `validator/rules.py`.
- Ticket por canal: se usa el valor pegado (ver hallazgo en `docs/DIAGNOSTICO_FASE1.md` §4.3).
