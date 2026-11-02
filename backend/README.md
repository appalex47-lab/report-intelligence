# Backend — Fase 4a (esqueleto del motor)

Implementa, según `docs/ARQUITECTURA.md`: importador por bloques de la hoja `Base` de AETOPS,
motor de cálculo (panorama, canales y líneas, YoY/MoM), validador y formato de presentación.
**Aún no genera PPTX/PDF ni tiene API** (Fases 5+).

```bash
pip install -r requirements.txt
python -m pytest -q                                    # pruebas (libro sintético)
REPORT_FIXTURES_DIR=/ruta/a/ejemplos python -m pytest  # + pruebas doradas con Excel reales
python -m backend.app.cli ruta/AETOPS_...xlsx          # resumen legible + hallazgos
```

## Qué hace
- `importer/`: detecta secciones YoY/MoM por anclas y las clasifica con el perfil `profiles/aetops/mensual.yaml`. Una columna sin mapeo aprobado **bloquea** (no se asigna a ciegas). Rechaza `.xlsm`.
- `calc/`: funciones puras con `Decimal`. Faltante ≠ cero; división entre cero → faltante. Ticket, Size B, V. Paciente, %Δ y Share se **recalculan**; lo pegado en el Excel solo se contrasta.
- `validator/`: `IDENTICAL_PERIODS`, `PERIOD_LABELS_INCONSISTENT`, `MISSING_COMPARISON`, `TOTALS_MISMATCH`, `TICKET_FORMULA_UNVERIFIED`, `PASTED_DIFFERS`, `COLUMN_UNMAPPED`.
- `format.py`: único lugar donde se redondea (mitad hacia arriba, como Excel y los PPTX).

## Limitaciones conocidas (4a)
- Solo hoja `Base`, perfil mensual. Categorías, productos y negados: pendientes (4b).
- Sin GLP-1 (4c). Sin `config/rules.yaml`: tolerancias fijas en `validator/rules.py`.
- Ticket por canal: se usa el valor pegado (ver hallazgo en `docs/DIAGNOSTICO_FASE1.md` §4.3).
