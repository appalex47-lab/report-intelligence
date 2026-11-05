# Modelo de hallazgos (Fase 1 · compatible con el modelo histórico)

Implementado en `backend/app/models.py` (`Finding`). Versión del modelo: `MODELO_HALLAZGOS_VERSION = "1.0.0"`.
Especificación: `docs/fase1/ESPECIFICACION_FASE1_REPORT_INTELLIGENCE_FINAL.md` §4.

## 1. Qué se conserva (sin cambios)
| Elemento | Estado |
|---|---|
| Firma posicional `Finding(id, severity, message, evidence="")` | Igual |
| `severity ∈ {block, warn, info}` | Igual; es lo único que leen `has_blockers()`, `web.service._finding` (lo que ve la interfaz) y el historial |
| Identificadores históricos de hallazgos (83 construcciones en `backend/app`) | Sin tocar |
| `has_blockers()` (`validator/rules.py`) | Sin tocar |
| `web.service._finding` (serialización hacia la interfaz) | Sin tocar: sigue devolviendo `{id, severity, message, evidence}` |

## 2. Campos nuevos (opcionales, solo por palabra clave)
| Campo | Tipo | Valores permitidos | Si no se aporta |
|---|---|---|---|
| `tipo` | `str \| None` | integridad, consistencia, cobertura, definicion, conciliacion, narrativa, presentacion | `None` |
| `gravedad` | `str \| None` | critica, alta, media, baja (no es `severity`) | `None` |
| `estado_verificacion` | `str \| None` | verificado, inconsistente, no_verificable, supuesto | `None` |
| `efecto_generacion` | `str \| None` | bloquear, advertir, informar | **Se deriva de `severity`** |
| `faltante` | `tuple` | elementos `{archivo, columna, granularidad}` | `()` |
| `regla_id` | `str \| None` | texto | `None` |
| `regla_version` | `str \| None` | texto | `None` |

Un quinto argumento posicional es un `TypeError`: los campos nuevos solo existen por palabra clave.

## 3. Correspondencia heredada
| `severity` | `efecto_generacion` |
|---|---|
| `block` | `bloquear` |
| `warn` | `advertir` |
| `info` | `informar` |

- Solo `severity` ⇒ `efecto_generacion` se **deriva**.
- Ambos ⇒ deben ser coherentes; si no, `ValueError("… incoherente …")`.
- Un valor fuera de las listas permitidas ⇒ `ValueError`.
- `estado_verificacion="no_verificable"` exige `faltante` no vacío (spec AC-04) ⇒ si no, `ValueError`.
- Un `severity` desconocido (no está en la tabla) no se valida ni se deriva: se conserva el comportamiento histórico, que no lo validaba.

## 4. Serialización
`Finding.to_dict()` incluye siempre `id`, `severity`, `message`, `evidence`; añade los campos nuevos **solo si tienen valor** (y `efecto_generacion`, que siempre se deriva). **La API y el historial actuales no usan `to_dict()`**: siguen con `web.service._finding`, por lo que sus salidas no cambian. Cablear los campos nuevos a la interfaz es trabajo de fases posteriores.

## 5. Limitaciones conocidas
- `Finding` es inmutable y se puede comparar y calcular su `hash`; si `faltante` contiene diccionarios, el `hash` falla (los diccionarios no son hashables). No se usa `hash` de hallazgos en el código actual.
- No existe todavía el catálogo `validator/catalogo.py` que asigna `tipo/gravedad/estado/efecto` por `id`; los hallazgos históricos quedan con `None` en esos campos (salvo `efecto_generacion` derivado).

## 6. Campos que usarán las fases siguientes
`tipo`, `gravedad`, `estado_verificacion`, `faltante`, `regla_id`, `regla_version`: los poblarán las reglas `R-REL-PAC-PED`, `R-CUADRE-DIM`, `R-CONC-COMPRAS`, `R-DENOM` y `R-COBERTURA-ATC` (fase 2) y el manifiesto de procedencia (fase 3).

## 7. Pruebas
`tests/unit/test_hallazgo_compat.py` (compatibilidad de firma, derivación, coherencia, serialización, `has_blockers`, interfaz) con las fixtures `tests/fixtures/fase1/hallazgos_compat.json`.
