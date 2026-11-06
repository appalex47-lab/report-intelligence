# Fase 4 · Escenarios E1 y E2 e indicador IND-01

| | |
|---|---|
| Alcance oficial | Integrar los escenarios **E1** (recuperación de negados) y **E2** (recuperación de abandono) y el indicador **IND-01** (relación pedidos/carritos) en el análisis de Report Intelligence, de modo que se puedan **interpretar sin confundir** datos observados, calculados, supuestos heredados, hipótesis, información no verificable y limitaciones de las fuentes |
| Fuentes normativas | Encargo de la Fase 4 (instrucción del usuario) · `docs/fase1/ESPECIFICACION_FASE1_REPORT_INTELLIGENCE_FINAL.md` §8 (E1 §8.1, IND-01 §8.2, E2 §8.3, garantías §8.4), §3.5 (F-01, F-02, F-03, F-09 a F-12), AC-13, AC-22, AC-23, AC-29, AC-30, AC-31, AC-32; `docs/fase1/implementacion/F2B_TRAZABILIDAD.md` (RQ-05, RQ-16, RQ-17, RQ-18, RQ-28, RQ-31: «panel/anexo pendientes (Fase 4)») |
| Depende de | Fase 2B (motor de reglas: `validator/rel_pedidos_carritos.py`, `operandos.py`, `motor.py`) y Fase 3 (procedencia). **Ninguno de sus contratos cambia** |
| Estado | **Implementada y validada; integración pendiente de autorización** (PR independiente, sin fusionar) |
| Fuera de alcance | Fase 5 (QA del PPTX, **anexo de calidad de datos**, RQ-19), cambios en láminas (requieren la autorización A-3), nuevas fórmulas o valores, identificación individual de carritos (§8.5), release, 3B |

## 0. Interpretación documental adoptada

El repositorio no tenía un documento titulado «Fase 4»: solo las notas de aplazamiento de la Fase 2B («panel/anexo pendientes (Fase 4)») y la especificación de Fase 1 §8. El encargo define la Fase 4 como **«Escenarios e indicador»**, que coincide exactamente con esas notas y con §8. Se adoptó esa lectura; no se incorporó nada de las Fases 5 a 8. El **anexo** de calidad de datos pertenece a la Fase 5 (RQ-19, flag `anexo_calidad`) y no se creó: el lugar de consulta de la Fase 4 es el **panel** del paso «Validar».

## 1. Qué se implementó

| Requisito del encargo | Implementación | Dónde |
|---|---|---|
| E1 explicable, 25 % como «Supuesto heredado, no validado» | Ficha con fórmula, variables tipificadas, efecto del supuesto, variantes «No configurado», qué es confiable y qué necesita validación | `escenarios.escenario_e1`, `supuestos()` |
| E2 explicable, 10 % como supuesto heredado | Igual; conserva la denominación histórica y la aclaración obligatoria de §8.3; solo GLP-1 | `escenarios.escenario_e2` |
| Comparación E1 vs. E2 | Tabla lado a lado, sin sumar montos, con lo confiable y lo que requiere validación | `escenarios.comparar` |
| IND-01 según su definición | Reutiliza la regla `R-COBERTURA-ATC` (F-01, F-02); muestra fórmula, variables, procedencia, estado y limitaciones | `escenarios.ind01` |
| Pedidos del sistema de ventas ≠ compras GA4 | Dos resultados independientes; cifras por separado con su definición; brecha F-03 como información; equivalencia «NO VALIDADA»; diferencias documentadas (conteo, definición, duplicados, atribución, temporalidad, medición) | `ind01()["fuentes_pedidos"]` |
| Unidad de los carritos | Declarada o «NO VERIFICABLE»; nunca se convierten eventos en carritos individuales | `ind01()["unidad_carritos"]` |
| Relaciones > 100 % | Se conservan sin modificar, con aviso, variables, clasificación (limitación metodológica o anomalía matemática) y causas posibles con su estado de comprobación | `ind01()[…]["mayor_100"]`, `anomalia_matematica` |
| Interfaz | Panel plegable «Escenarios E1 y E2 e indicador IND-01» en el paso «Validar», con chips de naturaleza del dato | `frontend/index.html` (`escenariosHtml`) |
| Trazabilidad | Cada variable lleva `tipo` (observado, calculado, supuesto_heredado, no_verificable) y `fuente` | `_var()` |

## 2. Arquitectura y flujo

```
libro .xlsx ─► motor actual (run_glp1_raw / run_aetops_raw / run_glp1)          ─┐ mismos bloques que usa la narrativa
            └► validator.normalizar.construir_contexto (solo datos crudos GLP-1)  ─┤
                                                                                  ▼
                                   backend/app/escenarios.py  (solo lee y presenta)
                                     E1, E2  ◄── cifras del motor × porcentajes de NarrativeRules (los que se aplican de verdad)
                                     IND-01  ◄── validator/rel_pedidos_carritos.py (R-COBERTURA-ATC) + operandos
                                                                                  ▼
                     web/service.py: analyze() → clave `escenarios_indicador` ─► worker/bridge ─► frontend (panel)
```

* **Una sola fuente de verdad.** E1 y E2 no recalculan desde el libro: toman las MISMAS cifras que `narrative/executive.py` y `narrative/glp1_exec.py` (mismos bloques) y los porcentajes de `NarrativeRules`. Una prueba exige que el monto del panel sea el que aparece en la recomendación de la presentación.
* **No bloquea.** Si el panel falla, `analyze()` devuelve `no_disponible` y el análisis, los hallazgos y la generación continúan (principio S-3). La traza no llega al usuario.
* **No cambia lo existente.** No toca fórmulas, cifras, láminas, `ENGINE_VERSION`, el manifiesto ni el `hash_resultado`.

## 3. Definiciones

### E1 — Recuperación de negados (F-09)
`Ingreso ilustrativo = M_neg × r`; `Proporción = Ingreso ilustrativo ÷ Venta total`. `M_neg` = Σ `negados.monto_negado` (observado; `negados` no trae fecha: se asume del periodo, **no verificable**); `r` = 25 % (**SUPUESTO HEREDADO, NO VALIDADO**, `narrative/rules.py:21`); `Venta_total` observada. Condición: `M_neg` disponible y `Venta_total > 0`; si no, «no verificable» con `faltante` (nunca 0 ni otra fuente). GLP-1 y AETOPS. **Efecto del supuesto:** el resultado es proporcional a `r`; cada punto porcentual equivale a `M_neg × 1 %`. No existe otro valor aprobado; las variantes conservadora y optimista figuran «No configurado».

### E2 — Recuperación de abandono (F-10, F-11)
`Ingreso ilustrativo = A × c × T`, `T = monto_venta ÷ pedidos del sistema de ventas`, `c` = 10 % (**SUPUESTO HEREDADO, NO VALIDADO**, `narrative/rules.py:25`). `A` = `trafico.carritos_abandonados` (métrica agregada heredada: **no es abandono comprobado**; aclaración de §8.3 en toda salida). Condición vigente `A > 0` y `T > 0` y `Venta_total > 0`. Si la columna viene vacía, el embudo deriva `add_to_cart − compras`, pero el escenario conserva su condición vigente sobre el dato de la fuente y, por tanto, no se muestra (se declara en el panel). Solo GLP-1: en AETOPS «No aplica: sin hoja `trafico`». **No sustituye ni se alimenta de IND-01.**

### IND-01 — Relación pedidos/carritos (F-01, F-02)
`Relación = (Pedidos ÷ Carritos agregados) × 100`, con la fuente de pedidos nombrada: «Relación pedidos (sistema de ventas) / carritos agregados» y «Relación compras GA4 / carritos agregados». Siempre se muestran juntos el volumen de carritos (con su unidad), el volumen de pedidos (con su fuente) y la relación. Estados: `calculable`, `calculable_con_limitacion`, `no_calculable` (con `faltante`; nunca 0 %). Faltante ≠ cero: `pedidos = 0` informado con carritos > 0 es 0 % calculable. No es una tasa de abandono y **no se calcula su complemento**. Se calcula sin ningún identificador de carrito, transacción o sesión.

### Pedidos del sistema de ventas y compras GA4
Son dos fuentes distintas: pedidos creados (`id_pedido` distintos) frente a eventos de compra de GA4. **Nunca se suman, promedian, sustituyen ni usan indistintamente.** La brecha relativa (F-03) se muestra como información. **Equivalencia: NO VALIDADA.** Duplicados, atribución y ventana de maduración: **NO VERIFICABLE** con el libro agregado.

### Unidad de los carritos
El catálogo de definiciones del proyecto (`definiciones.json`, definición `evento`) clasifica `add_to_cart` como **métrica de eventos de analítica** («un evento no es una persona, una sesión ni un carrito individual»), definición **no validada con datos reales**. En cambio, la unidad con la que la fuente reporta los **carritos agregados** no está declarada en los libros ni en la configuración (`carritos_agregados.unidad = null`; «se trata como unidad no declarada»), y los datos no permiten comprobarla (en el libro de ejemplo `add_to_cart` = 18 883 frente a 62 643 usuarios y 76 176 visitas: no discrimina). El contrato de datos define `visitas` como sesiones. Estado: **NO VERIFICABLE**; el cálculo se permite con interpretación limitada y se advierte; los eventos no se convierten en carritos individuales. Se declara con el parámetro `unidad_carritos` de `reglas.json` (`eventos`, `sesiones`, `otra:<texto>`).

### Relaciones superiores a 100 %
Se muestran sin truncar ni ajustar, con el aviso de §8.2 (no afirma una causa), las variables y unidades que la originan, y una tabla de **causas posibles** con su estado: *concurre*, *no concurre* o *no verificable* (fuentes, periodos, granularidad, unidades, universo y filtros, duplicados, atribución, ventana temporal). **Clasificación:** *anomalía matemática* solo si hay una inconsistencia aritmética (numerador o denominador negativos, denominador cero); si no, *limitación metodológica, no demostrable como error*.

## 4. Decisiones técnicas

| ID | Decisión | Motivo |
|---|---|---|
| D4-1 | E1/E2 toman sus cifras de los bloques del motor, no del libro | Una sola fuente de verdad; evita duplicar lógica y divergir de la presentación |
| D4-2 | El valor efectivo de r y c es el de `NarrativeRules`; `reglas.json` los documenta y, si difieren, se declara `inconsistencia_configuracion` | No elegir en silencio entre dos fuentes |
| D4-3 | No se activan los flags (`relacion_pedidos_carritos`, `escenarios_estrictos`…); el panel es aditivo y de solo lectura | AC-21: la salida con flags desactivados debe ser idéntica a la línea base; el panel no altera deck, motor ni hash |
| D4-4 | Libros en formato antiguo (por bloques): IND-01 «no calculable» (requiere datos crudos); E1/E2 salen de los mismos bloques | IND-01 se define sobre `ventas.id_pedido` y `trafico`; no se inventa el cálculo |
| D4-5 | No se modificó el texto de las láminas ni el manifiesto | A-3 no autorizada; el contrato de procedencia (3A) está congelado |
| D4-6 | El panel va en el paso «Validar», plegable y abierto por defecto | El usuario lo encuentra antes de revisar narrativa; no satura los demás pasos |
| D4-7 | La clasificación de >100 % no afirma causas: informa qué se pudo comprobar | AC-30 y encargo Parte 7 |

## 5. Cambios técnicos

| Archivo | Cambio |
|---|---|
| `backend/app/escenarios.py` | **nuevo**: cálculo y presentación (solo lectura) |
| `backend/app/web/service.py` | **protegido, autorizado**: `analyze()` agrega la clave `escenarios_indicador` mediante `_escenarios()` (+11 líneas) |
| `frontend/index.html` | **protegido, autorizado**: panel `escenariosHtml` en `vValidate` (solo se agrega) |
| `tests/regression/protegidos.json` | hashes y motivos de los dos archivos autorizados (motivos anteriores conservados) |
| `tests/unit/test_escenarios.py` | **nuevo**: pruebas del módulo y del servicio |
| `tests/e2e/escenarios_panel.mjs`, `test_escenarios_panel.py` | **nuevos**: panel en navegador real con el motor real (Pyodide) |
| `docs/fase4/*` | **nuevos**: este documento y la auditoría de cierre |

No se modificó ningún otro archivo de `backend/`, `tools/`, `.github/workflows/`, contratos, líneas base ni pruebas existentes.

## 6. Pruebas

Ver `AUDITORIA_CIERRE_FASE4.md` §3 (resultados con SHA y evidencia). Resumen de cobertura: fórmulas exactas en `Decimal` y coincidencia con la narrativa; E1/E2 con datos faltantes, nulos y ceros; supuestos rotulados; comparación; IND-01 25 % exacto, machote 12,48 % y 14,00 %, fuentes independientes, faltantes, división entre cero, >100 % conservado y explicado, unidad declarada o no, universo con varios canales; sin identificadores; sin denominaciones prohibidas ni complemento; determinismo y no mutación; servicio (panel presente, falla sin bloquear, no altera el análisis); navegador real (panel visible, sin errores de consola, sin recursos caídos). Verificación por mutación: 12 defectos deliberados, 12 detectados (ver `AUDITORIA_CIERRE_FASE4.md` §8 para el estado tras la auditoría independiente).

## 7. Estado de lo declarado

| Etiqueta | Elemento |
|---|---|
| VERIFICADO | Fórmulas F-01, F-02, F-03, F-09, F-10, F-11 sobre los machotes y fixtures; misma cifra que la presentación; valores de §8.2 (12,48 % y 14,00 %); panel en navegador real |
| SUPUESTO HEREDADO, NO VALIDADO | r = 25 % (E1), c = 10 % (E2) |
| NO VERIFICABLE | Unidad con la que la fuente reporta los carritos agregados (el catálogo define `add_to_cart` como evento, sin validar); duplicados, atribución y ventana de maduración de GA4; que `negados` corresponda al periodo; qué cuenta la fuente como `carritos_abandonados` |
| NO VERIFICADO | Comportamiento con datos reales de producción (solo se usaron machotes y fixtures sintéticos, OBS-10) |
| LIMITACIÓN CONOCIDA | Ver auditoría §5 |
