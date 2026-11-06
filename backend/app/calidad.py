"""Fase 5 · Anexo de calidad de datos (RQ-19; docs/fase5/IMPLEMENTACION_FASE5.md).

Evalúa el libro cargado en 15 dimensiones y deja cada hallazgo con EVIDENCIA (hoja, columna, cuántas filas y ejemplos de filas), IMPACTO sobre los
indicadores y su NATURALEZA. Solo LEE: no corrige, no completa y no excluye datos. Un hallazgo no bloquea el reporte (la severidad del motor sigue siendo
la única que bloquea); el anexo informa para interpretar.

Naturaleza de cada dato (nunca se mezclan):
  observado      viene del libro tal cual
  faltante       celda o mes que debería existir y está vacío
  inferido       lo deduce el sistema (p. ej. `carritos_abandonados` = add_to_cart − compras cuando viene vacío); se marca siempre
  no_verificable no hay forma de comprobarlo con el libro
Origen del libro: el sistema NUNCA afirma que los datos sean reales. Puede inferir «ejemplo o sintético» por el nombre del archivo; si no, queda
«no declarado». Los resultados calculados con datos de ejemplo no son resultados de producción.

Severidades: alta (puede cambiar una cifra principal o impedir un indicador), media (limita su interpretación), baja (limpieza sin efecto en cifras),
informativa (contexto). No hay datos fabricados: lo que no se puede evaluar figura «no evaluable» con su motivo.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from decimal import Decimal

ESQUEMA = "anexo_calidad/1"
ETIQUETA = ("Anexo de calidad de datos generado automáticamente a partir del libro cargado. Informa; no corrige ni excluye datos. "
            "Los resultados obtenidos con libros de ejemplo o sintéticos no son resultados de producción.")
DIMENSIONES = (("estructural", "Calidad estructural"), ("semantica", "Calidad semántica"), ("temporal", "Calidad temporal"), ("integridad", "Integridad"),
               ("consistencia", "Consistencia entre fuentes"), ("completitud", "Completitud"), ("duplicados", "Duplicados"), ("vacios", "Valores vacíos"),
               ("tipos", "Tipos de datos"), ("unidades", "Unidades de medición"), ("trazabilidad", "Trazabilidad"),
               ("riesgo", "Riesgo de interpretación"), ("impacto", "Impacto sobre los indicadores"), ("no_verificables", "Datos no verificables"),
               ("supuestos", "Supuestos y limitaciones"))
CATEGORIAS = {"real": "Datos de producción: el sistema nunca lo afirma; solo lo puede declarar quien los aporta.",
              "sintetico": "Datos generados artificialmente para pruebas.", "ejemplo": "Libros de muestra que acompañan al proyecto (data/ejemplos).",
              "faltante": "Celdas o meses que debían existir y están vacíos.", "inferido": "Valores que deduce el sistema y que se marcan como tales.",
              "no_verificable": "Lo que el libro no permite comprobar."}
NOMBRE_EJEMPLO = re.compile(r"ejemplo|sint[eé]tic|synthetic|demo|muestra|sample", re.I)
SEVERIDADES = ("alta", "media", "baja", "informativa")
MAX_EJEMPLOS = 5


def _h(id_, desc, severidad, naturaleza, evidencia, impacto, indicadores=()) -> dict:
    assert severidad in SEVERIDADES and naturaleza in ("observado", "faltante", "inferido", "no_verificable"), (severidad, naturaleza)
    return {"id": id_, "descripcion": desc, "severidad": severidad, "naturaleza": naturaleza, "evidencia": evidencia, "impacto": impacto, "indicadores": list(indicadores)}


def _ev(hoja, columna=None, filas=None, **extra) -> dict:
    d = {"hoja": hoja}
    if columna:
        d["columna"] = columna
    if filas is not None:
        d["n_filas"] = len(filas)
        d["filas_ejemplo"] = sorted(filas)[:MAX_EJEMPLOS]
    return d | extra


def clasificar_origen(nombre: str | None) -> dict:
    """Origen del libro. Nunca «real»: solo se puede inferir «ejemplo o sintético» por el nombre, o dejarlo «no declarado»."""
    if nombre and NOMBRE_EJEMPLO.search(nombre):
        return {"clasificacion": "ejemplo_o_sintetico_inferido", "detalle": f"El nombre del archivo («{nombre}») indica un libro de ejemplo o sintético (inferido; no verificado).",
                "advertencia": "Los resultados obtenidos con este libro no son resultados de producción."}
    return {"clasificacion": "no_declarado", "detalle": "El libro no declara su origen: no se puede afirmar que sean datos reales ni sintéticos.",
            "advertencia": "No presentar estos resultados como datos de producción sin confirmarlo fuera del sistema."}


# --------------------------------------------------------------------------------------------- dimensiones sobre el contexto de datos crudos
def _ventas(ctx) -> dict:
    """Hallazgos agrupados por dimensión a partir de `ventas`, `catalogo` y `trafico` del contexto."""
    out: dict[str, list] = defaultdict(list)
    L = ctx.lineas
    per = ctx.lineas_periodo()
    n, nper = len(L), len(per)
    # --- estructural
    hojas = sorted(ctx.columnas)
    out["estructural"].append(_h("EST-HOJAS", f"Hojas leídas: {', '.join(hojas)}.", "informativa", "observado", {"hojas": hojas}, "Ninguno: el orden de las columnas no importa; se leen por nombre.", ()))
    for hoja, req in (("trafico", "tráfico (embudo)"), ("negados", "negados")):
        if hoja not in ctx.columnas and hoja == "trafico" and ctx.unidad == "GLP1":
            out["estructural"].append(_h("EST-SIN-TRAFICO", "GLP-1 sin hoja `trafico`.", "alta", "faltante", {"hoja": "trafico"},
                                         "No se calculan IND-01 ni E2; el embudo y los bloques de tráfico no existen.", ("IND-01", "E2")))
        if hoja not in ctx.columnas and hoja == "negados":
            out["estructural"].append(_h("EST-SIN-NEGADOS", "Libro sin hoja `negados`.", "media", "faltante", {"hoja": "negados"},
                                         "No se calcula E1 ni los bloques de negados.", ("E1",)))
    # --- fechas / tipos
    sin_fecha = [ln.fila for ln in L if ln.fecha is None and ln.valores.get("fecha_pedido", "") != ""]
    fecha_vacia = [ln.fila for ln in L if ln.valores.get("fecha_pedido", "") == ""]
    if sin_fecha:
        out["tipos"].append(_h("TIP-FECHA", f"{len(sin_fecha)} fila(s) con una fecha de pedido que no se puede leer.", "alta", "observado",
                               _ev("ventas", "fecha_pedido", sin_fecha), "Esas filas no pertenecen a ningún periodo: se excluyen de los cálculos sin avisar en las cifras.", ("ventas", "pedidos", "ticket")))
    for col, attr in (("monto_venta", "monto"), ("piezas", "piezas")):
        malas = [ln.fila for ln in L if getattr(ln, attr) is None and ln.valores.get(col, "") != ""]
        if malas:
            out["tipos"].append(_h(f"TIP-{col.upper()}", f"{len(malas)} fila(s) con `{col}` no numérico.", "alta", "observado", _ev("ventas", col, malas),
                                   "Esas líneas no cuentan como pedido válido (se excluyen).", ("ventas", "pedidos", "ticket")))
    # --- vacíos / completitud
    for col in sorted(ctx.columnas.get("ventas", ())):
        vac = [ln.fila for ln in per if ln.valores.get(col, "") == ""]
        if vac:
            req = col in ("fecha_pedido", "id_pedido", "id_paciente", "sku", "monto_venta", "piezas")
            out["vacios"].append(_h(f"VAC-{col.upper()}", f"`{col}` vacía en {len(vac)} de {nper} fila(s) del periodo ({len(vac) / nper:.1%}).",
                                    "alta" if req else "baja", "faltante", _ev("ventas", col, vac),
                                    "Las filas con esta columna requerida vacía no cuentan como pedido válido." if req else "Columna opcional: limita los desgloses que la usan.",
                                    ("pedidos", "ventas") if req else ("desgloses",)))
    if not sin_fecha and fecha_vacia:
        out["completitud"].append(_h("COM-FECHA", f"{len(fecha_vacia)} fila(s) sin fecha de pedido.", "alta", "faltante", _ev("ventas", "fecha_pedido", fecha_vacia),
                                     "No se pueden asignar a un periodo: quedan fuera de todos los cálculos.", ("ventas", "pedidos")))
    # --- semántica
    neg = [ln.fila for ln in per if ln.monto is not None and ln.monto < 0]
    cero = [ln.fila for ln in per if ln.monto is not None and ln.monto == 0]
    pz = [ln.fila for ln in per if ln.piezas is not None and ln.piezas <= 0]
    if neg:
        out["semantica"].append(_h("SEM-MONTO-NEG", f"{len(neg)} línea(s) con monto negativo en el periodo.", "alta", "observado", _ev("ventas", "monto_venta", neg),
                                   "El contrato no contempla devoluciones ni cancelaciones: un monto negativo reduce la venta sin explicación.", ("ventas", "ticket")))
    if cero:
        out["semantica"].append(_h("SEM-MONTO-CERO", f"{len(cero)} línea(s) con monto 0 en el periodo.", "baja", "observado", _ev("ventas", "monto_venta", cero),
                                   "Cuentan como pedido con monto 0 y bajan el ticket promedio.", ("ticket",)))
    if pz:
        out["semantica"].append(_h("SEM-PIEZAS", f"{len(pz)} línea(s) con piezas ≤ 0 en el periodo.", "media", "observado", _ev("ventas", "piezas", pz), "Distorsiona piezas por pedido.", ("piezas",)))
    sin_cat = [ln.fila for ln in per if ln.sku and ln.sku not in ctx.catalogo]
    if sin_cat:
        skus = sorted({ln.sku for ln in per if ln.sku and ln.sku not in ctx.catalogo})
        out["semantica"].append(_h("SEM-SKU-SIN-CATALOGO", f"{len(sin_cat)} línea(s) con {len(skus)} SKU ausente(s) del catálogo.", "alta", "observado",
                                   _ev("ventas", "sku", sin_cat, skus_ejemplo=skus[:MAX_EJEMPLOS]), "Esas líneas NO cuentan como pedido válido: la venta y los pedidos del motor son menores que los del libro.", ("ventas", "pedidos", "ticket")))
    # --- integridad
    pac: dict[str, set] = defaultdict(set)
    for ln in per:
        if ln.id_pedido and ln.id_paciente:
            pac[ln.id_pedido].add(ln.id_paciente)
    multi = sorted(k for k, v in pac.items() if len(v) > 1)
    if multi:
        out["integridad"].append(_h("INT-PEDIDO-MULTIPACIENTE", f"{len(multi)} pedido(s) con más de un paciente.", "media", "observado",
                                    {"hoja": "ventas", "columna": "id_pedido", "n_pedidos": len(multi), "ejemplos": multi[:MAX_EJEMPLOS]},
                                    "Un pedido de varios pacientes contradice la definición de pedido y afecta pacientes por pedido.", ("pacientes", "pedidos")))
    ids_per = {ln.id_pedido for ln in per if ln.id_pedido}
    validos = ctx.pedidos_sistema_ventas()
    if ids_per and len(ids_per) != len(validos):
        out["integridad"].append(_h("INT-PEDIDOS-EXCLUIDOS", f"{len(ids_per) - len(validos)} de {len(ids_per)} pedido(s) del periodo no cumplen los criterios de pedido válido.", "alta", "observado",
                                    {"hoja": "ventas", "pedidos_en_libro": len(ids_per), "pedidos_validos": len(validos)},
                                    "El motor y IND-01 cuentan solo los válidos (fecha, monto, piezas, paciente y SKU del catálogo).", ("pedidos", "IND-01", "ticket")))
    # --- temporal
    if nper == 0:
        out["temporal"].append(_h("TEM-PERIODO-VACIO", f"No hay ventas en el periodo {ctx.etiqueta_periodo()}.", "alta", "faltante", {"hoja": "ventas", "periodo": ctx.etiqueta_periodo()},
                                  "Sin ventas del periodo no hay cifras: todos los indicadores quedan sin calcular.", ("todos",)))
    fechas = [ln.fecha for ln in L if ln.fecha is not None]
    if fechas:
        out["temporal"].append(_h("TEM-RANGO", f"Fechas de pedido entre {min(fechas)} y {max(fechas)}.", "informativa", "observado",
                                  {"hoja": "ventas", "columna": "fecha_pedido", "desde": str(min(fechas)), "hasta": str(max(fechas))}, "Ninguno.", ()))
    if ctx.hoja_trafico:
        y, ms = ctx.ventana()
        faltan = [f"{y}-{m:02d}" for m in sorted(ms) if (y, m) not in ctx.trafico_sitio]
        if faltan:
            out["temporal"].append(_h("TEM-TRAFICO-MESES", f"Tráfico sin datos de nivel sitio para {', '.join(faltan)}.", "alta", "faltante", {"hoja": "trafico", "meses": faltan},
                                      "IND-01 no se calcula con meses incompletos (no se completa con 0).", ("IND-01", "E2")))
    out["temporal"].append(_h("TEM-NEGADOS-SIN-FECHA", "La hoja `negados` no trae fecha.", "media", "no_verificable", {"hoja": "negados"},
                              "Se asume que corresponde al periodo del reporte; no se puede comprobar.", ("E1",)))
    # --- duplicados
    cuenta = Counter(tuple(sorted(ln.valores.items())) for ln in per)
    dup = [(k, v) for k, v in cuenta.items() if v > 1]
    if dup:
        filas = [ln.fila for ln in per if cuenta[tuple(sorted(ln.valores.items()))] > 1]
        out["duplicados"].append(_h("DUP-LINEAS", f"{sum(v - 1 for _, v in dup)} línea(s) repetida(s) exactamente en el periodo ({len(dup)} grupo(s)).", "media", "observado",
                                    _ev("ventas", None, filas), "Si son un error de carga inflan venta y piezas; los pedidos (id_pedido distintos) no se afectan.", ("ventas", "piezas")))
    return dict(out)


def _trafico_y_fuentes(esc: dict | None) -> dict[str, list]:
    """Consistencia, unidades y riesgos que ya calculó el panel de escenarios (Fase 4); no se recalculan."""
    out: dict[str, list] = defaultdict(list)
    if not esc or esc.get("no_disponible"):
        return dict(out)
    i = esc.get("ind01") or {}
    f = i.get("fuentes_pedidos")
    if f:
        out["consistencia"].append(_h("CON-VENTAS-GA4", f"Pedidos del sistema de ventas ({f['sistema_ventas']['valor']}) frente a compras GA4 ({f['ga4_compras']['valor']}).", "media", "observado",
                                      {"fuentes": ["ventas.id_pedido", "trafico.compras"], "brecha_relativa": f.get("brecha_relativa")},
                                      "Son fuentes distintas con equivalencia NO VALIDADA; no se suman ni se sustituyen. La diferencia es información, no un error.", ("IND-01",)))
    u = i.get("unidad_carritos")
    if u:
        out["unidades"].append(_h("UNI-CARRITOS", f"Unidad de los carritos agregados: {u['estado']}.", "media" if u["estado"] != "DECLARADA" else "informativa", "no_verificable",
                                  {"hoja": "trafico", "columna": "add_to_cart", "unidad": u["declarada"]}, "IND-01 se calcula con interpretación limitada; un evento no equivale a un carrito individual.", ("IND-01",)))
    for r in i.get("resultados", []):
        if r.get("mayor_100"):
            out["riesgo"].append(_h(f"RIE-MAYOR-100-{r['fuente_pedidos']}", f"{r['nombre']}: {float(r['relacion']):.2f} % (> 100 %).", "alta", "observado",
                                    {"valor": r["relacion"], "clasificacion": r["mayor_100"]["clasificacion"]},
                                    "Se conserva sin modificar; puede deberse a unidades, fuentes, periodos o filtros distintos.", ("IND-01",)))
    for e in esc.get("escenarios", []):
        if e["estado"] == "calculable":
            out["riesgo"].append(_h(f"RIE-{e['id']}", f"{e['id']} usa un supuesto heredado, no validado.", "media", "no_verificable", {"escenario": e["id"]},
                                    "El monto ilustrativo no es un pronóstico ni un resultado observado.", (e["id"],)))
        for a in e.get("advertencias", []):
            out["completitud"].append(_h(f"COM-{e['id']}-NEGADOS", a, "media", "faltante", {"hoja": "negados", "columna": "monto_negado"}, "E1 puede estar subestimado.", (e["id"],)))
    return dict(out)


# --------------------------------------------------------------------------------------------- ensamblado
def construir(res, unidad: str, period, ctx=None, libro: dict | None = None, escenarios: dict | None = None) -> dict:
    """Anexo completo. `ctx` = Contexto de datos crudos (o None para libros en formato antiguo: la evaluación detallada queda «no evaluable»)."""
    libro = libro or {}
    por_dim: dict[str, list] = defaultdict(list)
    if ctx is not None:
        for k, v in _ventas(ctx).items():
            por_dim[k] += v
    for k, v in _trafico_y_fuentes(escenarios).items():
        por_dim[k] += v
    motor = [{"id": f.id, "severity": f.severity, "mensaje": f.message, "evidencia": f.evidence} for f in getattr(res, "findings", [])]
    for m in motor:                                                         # lo que ya detectó el motor también forma parte de la calidad
        dim = "integridad" if m["severity"] == "block" else "consistencia" if "DIFFERS" in m["id"] or "CONC" in m["id"] else "semantica"
        por_dim[dim].append(_h(f"MOT-{m['id']}", m["mensaje"], "alta" if m["severity"] == "block" else "media" if m["severity"] == "warn" else "informativa", "observado",
                               {"origen": "motor de validación", "id": m["id"], "detalle": str(m["evidencia"])[:200]}, "Ver el hallazgo del motor.", ()))
    # trazabilidad
    from . import version
    traz = [_h("TRA-ARCHIVO", f"Archivo de origen: {libro.get('nombre') or 'desconocido'}" + (f" (SHA-256 {libro['sha256'][:16]}…)" if libro.get("sha256") else "") + ".", "informativa", "observado",
               {"nombre": libro.get("nombre"), "sha256": libro.get("sha256"), "bytes": libro.get("bytes")}, "Permite verificar que el anexo corresponde al archivo cargado.", ()),
            _h("TRA-VERSIONES", f"Versiones: aplicación {version.APP_VERSION}, motor {version.ENGINE_VERSION}.", "informativa", "observado",
               {"app": version.APP_VERSION, "motor": version.ENGINE_VERSION}, "La procedencia del reporte (procedencia.json) registra además el hash del resultado.", ()),
            _h("TRA-HALLAZGOS", "Cada hallazgo de este anexo cita hoja, columna, número de filas y filas de ejemplo.", "informativa", "observado", {}, "Permite localizar el origen en el libro.", ())]
    por_dim["trazabilidad"] += traz
    # no verificables y supuestos
    glp = unidad == "glp1"
    por_dim["no_verificables"] += ([
        _h("NVE-ADD-TO-CART", "Unidad con que la fuente reporta `add_to_cart` (eventos, sesiones, usuarios u otra).", "media", "no_verificable", {"hoja": "trafico", "columna": "add_to_cart"}, "Limita la interpretación de IND-01.", ("IND-01",)),
        _h("NVE-GA4", "Duplicados, atribución y ventana de maduración de las compras GA4.", "media", "no_verificable", {"hoja": "trafico", "columna": "compras"}, "No se puede conciliar con los pedidos del sistema de ventas.", ("IND-01",)),
        _h("NVE-ABANDONADOS", "Qué cuenta la herramienta de analítica como `carritos_abandonados`.", "media", "no_verificable", {"hoja": "trafico", "columna": "carritos_abandonados"}, "E2 parte de una métrica heredada, no de abandono comprobado.", ("E2",))] if glp else []) + [
        _h("NVE-MONEDA", "Moneda de `monto_venta`: no está declarada en el libro.", "baja", "no_verificable", {"hoja": "ventas", "columna": "monto_venta"}, "Las cifras se muestran tal como vienen (sin IVA, cancelaciones ni devoluciones).", ("ventas",))]
    por_dim["supuestos"] += [
        _h("SUP-E1", "E1 usa un porcentaje de recuperación heredado (25 %), no validado con datos reales.", "media", "no_verificable", {"fuente": "backend/app/narrative/rules.py"}, "Monto ilustrativo, no pronóstico.", ("E1",))] + ([
        _h("SUP-E2", "E2 usa un porcentaje de cierre heredado (10 %), no validado con datos reales.", "media", "no_verificable", {"fuente": "backend/app/narrative/rules.py"}, "Monto ilustrativo, no pronóstico.", ("E2",))] if glp else []) + [
        _h("SUP-REGLAS", "Las reglas del motor" + (" y IND-01" if glp else "") + " están validadas solo con datos sintéticos.", "media", "no_verificable", {"fuente": "config/validacion_registro.json"}, "Falta su validación operacional.", ("IND-01",) if glp else ())]
    if ctx is None:
        por_dim["estructural"].append(_h("EST-FORMATO-ANTIGUO", "Libro en formato antiguo (por bloques, no de datos crudos): no hay filas de ventas que evaluar.", "informativa", "no_verificable",
                                         {}, "La evaluación detallada de las dimensiones sobre filas queda «no evaluable»; solo constan los hallazgos del motor.", ("todos",)))
    # impacto: por indicador
    impacto: dict[str, list] = defaultdict(list)
    for dim, hs in por_dim.items():
        for h in hs:
            if h["severidad"] in ("alta", "media"):
                for ind in h["indicadores"]:
                    impacto[ind].append(h["id"])
    por_dim["impacto"] += [_h(f"IMP-{ind}", f"{ind}: afectado por {len(ids)} hallazgo(s): {', '.join(sorted(set(ids))[:6])}.", "media", "observado", {"indicador": ind, "hallazgos": sorted(set(ids))},
                              "Interpretar el indicador con estos hallazgos a la vista.", (ind,)) for ind, ids in sorted(impacto.items())]
    evaluables = ctx is not None
    dims = []
    for id_, nombre in DIMENSIONES:
        hs = por_dim.get(id_, [])
        if not evaluables and id_ in ("semantica", "temporal", "completitud", "duplicados", "vacios", "tipos") and not hs:
            estado, motivo = "no_evaluable", "libro en formato antiguo: sin filas de datos crudos"
        else:
            estado = "con_hallazgos" if any(h["severidad"] in ("alta", "media", "baja") for h in hs) else "sin_hallazgos"
            motivo = None
        dims.append({"id": id_, "nombre": nombre, "estado": estado, "motivo": motivo, "hallazgos": hs})
    sev = Counter(h["severidad"] for d in dims for h in d["hallazgos"])
    return {"esquema": ESQUEMA, "etiqueta": ETIQUETA, "unidad": unidad, "periodo": f"{period.year}-{period.index:02d} ({period.periodicity})",
            "origen_datos": clasificar_origen(libro.get("nombre")) | {"categorias": CATEGORIAS},
            "resumen": {"severidades": {s: sev.get(s, 0) for s in SEVERIDADES}, "dimensiones_evaluadas": sum(d["estado"] != "no_evaluable" for d in dims), "dimensiones": len(dims),
                        "estado_global": "con_hallazgos_altos" if sev.get("alta") else "con_hallazgos" if sev.get("media") or sev.get("baja") else "sin_hallazgos"},
            "dimensiones": dims, "limitaciones": [
                "Evalúa lo que el libro permite: no valida los datos contra el sistema de origen.", "No detecta errores de captura que sean valores plausibles.",
                "No decide si el libro es real o sintético: solo infiere «ejemplo/sintético» por el nombre del archivo.",
                "El motor sigue siendo el único que bloquea la generación."]}
