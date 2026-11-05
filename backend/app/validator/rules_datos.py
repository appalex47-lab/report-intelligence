"""Reglas sobre los datos de `ventas`: R-REL-PAC-PED, R-CUADRE-DIM y R-DENOM (Fase 2A; spec §3.3).

Solo leen el `Contexto`; no filtran, no corrigen y no eliminan registros. Se ubican en un módulo nuevo (y no en
`validator/rules.py`) para no tocar las validaciones históricas.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal

from . import operandos
from .motor import Definicion, Resultado, evaluar_razon, regla


def _n(x) -> str:
    return f"{Decimal(x):,.0f}"


def _pct(frac: Decimal | None) -> str:
    return "n/d" if frac is None else f"{frac * 100:,.2f} %"


# ---------------------------------------------------------------------------------------------------- R-REL-PAC-PED
@regla("R-REL-PAC-PED")
def r_rel_pac_ped(ctx, d: Definicion) -> list[Resultado]:
    m = d.p("max_pacientes_por_pedido")
    if m is None:
        return [d.resultado("relacion_paciente_pedido", "not_verifiable", motivo="`max_pacientes_por_pedido` no está configurado",
                            faltante=({"archivo": "reglas.json", "columna": "max_pacientes_por_pedido", "granularidad": None},))]
    m = int(m)
    out: list[Resultado] = []

    # atributos por id_pedido (sobre todas las líneas del archivo)
    ped: dict[str, dict] = {}
    sin_id = 0
    for ln in ctx.lineas:
        if not ln.id_pedido:
            sin_id += 1
            continue
        g = ped.setdefault(ln.id_pedido, {"fechas": set(), "pac": set()})
        if ln.fecha:
            g["fechas"].add(ln.fecha)
        if ln.id_paciente:
            g["pac"].add(ln.id_paciente)

    # clases (C0 y C1 reservadas: no hay columna de estatus; ver docstring de la regla en la especificación §3.3)
    c2 = sorted(i for i, g in ped.items() if len(g["fechas"]) > 1)
    sf = sorted(i for i, g in ped.items() if len(g["fechas"]) == 0)
    elegibles = {i: g for i, g in ped.items() if len(g["fechas"]) == 1}
    identidad_a = len(ped) == 0 + 0 + len(c2) + len(sf) + len(elegibles)

    ou = {i: g for i, g in elegibles.items() if ctx.en_periodo(next(iter(g["fechas"])))}
    A = {i for i, g in ou.items() if 1 <= len(g["pac"]) <= m}
    B = {i for i, g in ou.items() if len(g["pac"]) == 0}
    C = {i for i, g in ou.items() if len(g["pac"]) > m}
    identidad_b = len(ou) == len(A) + len(B) + len(C)
    pu = set().union(*(ou[i]["pac"] for i in A)) if A else set()
    identidad_c = len(pu) <= m * len(A)
    c2_periodo = [i for i in c2 if any(ctx.en_periodo(f) for f in ped[i]["fechas"])]

    if not ou:
        return [d.resultado("relacion_paciente_pedido", "not_verifiable", motivo="no hay pedidos con fecha en el periodo",
                            faltante=({"archivo": "ventas", "columna": "fecha_pedido en el periodo", "granularidad": "pedido"},),
                            evidencia={"periodo": ctx.etiqueta_periodo(), "pedidos_archivo": len(ped)})]

    cob = Decimal(len(A)) / Decimal(len(ou))
    razon_rec = (Decimal(len(A)) / Decimal(len(pu))) if pu else None
    no_asig = len(c2)                                                          # C1 inactiva: |C1| = 0
    tasa_no_asig = (Decimal(no_asig) / Decimal(no_asig + len(elegibles))) if (no_asig + len(elegibles)) else None
    universo_motor = ctx.pedidos_sistema_ventas()
    evid = {"periodo": ctx.etiqueta_periodo(), "max_pacientes_por_pedido": m, "pedidos_archivo": len(ped),
            "no_asignables": no_asig, "tasa_no_asignables": None if tasa_no_asig is None else str(tasa_no_asig),
            "pedidos_universo_motor": len(universo_motor),
            "nota_universos": "este universo cuenta todo id_pedido con fecha única en el periodo; «pedidos del sistema de ventas» usa los criterios del motor actual (sku en catálogo, importes numéricos, ids no vacíos)",
            "clases": {"C0": 0, "C1": 0, "C2": len(c2), "sin_fecha": len(sf), "E": len(elegibles)},
            "universo_periodo": len(ou), "A": len(A), "B": len(B), "C": len(C), "pacientes_unicos": len(pu),
            "cobertura_paciente": str(cob), "razon_recurrencia": None if razon_rec is None else str(razon_rec),
            "clases_reservadas_inactivas": ["C0 (excluido por estatus)", "C1 (estatus mixto)"],
            "identidades": {"archivo": identidad_a, "universo": identidad_b, "pacientes": identidad_c}}

    problemas = []
    if C:
        problemas.append(f"{len(C)} pedido(s) con más de {m} paciente(s)")
    if c2_periodo:
        problemas.append(f"{len(c2_periodo)} pedido(s) con fechas contradictorias")
    if sin_id:
        problemas.append(f"{sin_id} línea(s) sin id_pedido")
    if problemas:
        out.append(d.resultado("relacion_paciente_pedido", "error", resumen="; ".join(problemas), evidencia=evid))
    else:
        out.append(d.resultado("relacion_paciente_pedido", "valid", n_pedidos=_n(len(ou)), m=m, n_pacientes=_n(len(pu)),
                               cobertura=_pct(cob), evidencia=evid))
    if C:
        out.append(d.resultado("paciente_contradictorio", "error", n=len(C), m=m,
                               evidencia={"n": len(C), "muestra_id_pedido": sorted(C)[:5], "decision": "permanecen en el universo de pedidos; fuera de A, pacientes únicos y cobertura"}))
    if c2_periodo:
        out.append(d.resultado("fecha_contradictoria", "error", n=len(c2_periodo),
                               evidencia={"n": len(c2_periodo), "muestra_id_pedido": c2_periodo[:5], "decision": "no se asignan a ningún periodo"}))
    if sin_id:
        out.append(d.resultado("lineas_sin_id_pedido", "error", n=sin_id, evidencia={"lineas": sin_id}))
    lp = [ln for ln in ctx.lineas_periodo() if ln.id_pedido]
    exactos = sum(c - 1 for c in Counter(tuple(sorted(ln.valores.items())) for ln in lp).values() if c > 1)
    repetidas = sum(c - 1 for c in Counter((ln.id_pedido, ln.sku) for ln in lp).values() if c > 1)
    if exactos:
        out.append(d.resultado("duplicado_exacto", "warning", verificacion="verificado", n=exactos, evidencia={"n": exactos, "tratamiento": "se informan; no se eliminan"}))
    if repetidas:
        out.append(d.resultado("linea_duplicada", "warning", verificacion="verificado", n=repetidas, evidencia={"n": repetidas, "tratamiento": "se informan; no se eliminan"}))
    if B:
        out.append(d.resultado("cobertura_paciente", "warning", verificacion="verificado", n_sin_paciente=len(B), cobertura=_pct(cob),
                               evidencia={"sin_paciente": len(B), "cobertura_paciente": str(cob), "muestra_id_pedido": sorted(B)[:5]}))
    else:
        out.append(d.resultado("cobertura_paciente", "valid", evidencia={"cobertura_paciente": str(cob)}))
    if d.p("estatus_excluidos") is not None:
        out.append(d.resultado("estatus_no_disponible", "warning", evidencia={"estatus_excluidos": d.p("estatus_excluidos")}))
    if not (identidad_a and identidad_b and identidad_c):
        out.append(d.resultado("identidad_control", "error", detalle=f"archivo={identidad_a}, universo={identidad_b}, pacientes={identidad_c}", evidencia=evid["identidades"]))
    return out


# ---------------------------------------------------------------------------------------------------- R-CUADRE-DIM
def _valor_dimension(ctx, dim: dict, ln) -> str:
    if dim.get("via") == "sku":
        v = ctx.catalogo.get(ln.sku, {}).get(dim["columna"])
        return "" if v is None else str(v).strip()
    return ln.valores.get(dim["columna"], "")


def _columna_existe(ctx, dim: dict) -> bool:
    return dim["columna"] in ctx.columnas.get(dim["hoja"], set())


def _condicion(excl: bool, exh: bool) -> str:
    return {(True, True): "suma = total", (True, False): "suma ≤ total", (False, True): "suma ≥ total",
            (False, False): "sin relación exigible (no exclusiva y no exhaustiva)"}[(excl, exh)]


@regla("R-CUADRE-DIM")
def r_cuadre_dim(ctx, d: Definicion) -> list[Resultado]:
    tol = Decimal(str(d.p("tolerancia_conteo") if d.p("tolerancia_conteo") is not None else 0))
    candidatas = d["dimensiones_candidatas"][ctx.unidad]
    declaradas = d["dimensiones_declaradas"]
    lineas_todas = ctx.lineas_periodo()
    if not any(ln.id_pedido or ln.id_paciente for ln in lineas_todas):
        return [d.resultado("cuadre_dimensiones", "not_verifiable", clave="columnas_faltantes.not_verifiable",
                            motivo="no hay líneas con fecha en el periodo", faltante=({"archivo": "ventas", "columna": "líneas del periodo", "granularidad": "línea"},))]
    detalle: list[Resultado] = []
    n_no_excl = n_decl = n_err = 0
    for dim in candidatas:
        if not _columna_existe(ctx, dim):
            detalle.append(d.resultado(f"dimension_{dim['id']}", "not_verifiable", clave="dimension_no_evaluable.not_verifiable", dimension=dim["id"],
                                       motivo=f"no existe la columna {dim['hoja']}.{dim['columna']}",
                                       faltante=({"archivo": dim["hoja"], "columna": dim["columna"], "granularidad": None},)))
            continue
        for ent, col_ent in d["entidades"].items():
            cats: dict[str, set] = defaultdict(set)
            for ln in lineas_todas:
                e = getattr(ln, col_ent)
                if not e:                                  # la línea no identifica a esta entidad: no entra en este análisis (no se elimina del dato)
                    continue
                v = _valor_dimension(ctx, dim, ln)
                cats[e]                                    # registra la entidad aunque no tenga valor (queda «sin categoría»)
                if v:
                    cats[e].add(v)
            total = len(cats)
            multi = {e: c for e, c in cats.items() if len(c) > 1}
            sin_cat = sum(1 for c in cats.values() if not c)
            decl = declaradas.get(dim["id"])
            codigo = f"dimension_{dim['id']}_{ent}"
            if decl and decl.get("entidad") == ent and decl.get("exclusiva") is not None and decl.get("exhaustiva") is not None:
                n_decl += 1
                excl, exh = bool(decl["exclusiva"]), bool(decl["exhaustiva"])
                suma = sum(len(c) for c in cats.values()) + (sin_cat if exh else 0)         # «Sin asignar» virtual solo si es exhaustiva
                ok = (abs(suma - total) <= tol if (excl and exh) else suma <= total + tol if excl else suma >= total - tol if exh else True)
                n_err += 0 if ok else 1
                detalle.append(d.resultado(codigo, "valid" if ok else "error", clave=f"dimension_declarada.{'valid' if ok else 'error'}",
                                           dimension=dim["id"], entidad=ent, condicion=_condicion(excl, exh), suma=_n(suma), total=_n(total),
                                           evidencia={"suma": suma, "total": total, "exclusiva": excl, "exhaustiva": exh, "tolerancia": str(tol),
                                                      "sin_categoria": sin_cat, "justificacion": decl.get("justificacion")}))
            elif multi:
                n_no_excl += 1
                suma = sum(len(c) for c in cats.values())
                ej = [{"id": e, "valores": sorted(c)[:5]} for e, c in sorted(multi.items())[:3]]
                detalle.append(d.resultado(codigo, "warning", clave="dimension_no_exclusiva.warning", verificacion="verificado", dimension=dim["id"], entidad=ent,
                                           n_multi=_n(len(multi)), n_total=_n(total), total=_n(total), suma=_n(suma),
                                           evidencia={"entidad": ent, "entidades_totales": total, "entidades_con_mas_de_un_valor": len(multi),
                                                      "suma_de_subtotales": suma, "ejemplos": ej, "sin_categoria": sin_cat,
                                                      "tratamiento": "no se filtra ni elimina ningún registro"}))
            else:
                detalle.append(d.resultado(codigo, "not_verifiable", clave="dimension_sin_solapamiento.not_verifiable", dimension=dim["id"], entidad=ent,
                                           faltante=({"archivo": "reglas.json", "columna": f"dimensiones.{dim['id']} (exclusiva/exhaustiva con justificación)", "granularidad": ent},),
                                           evidencia={"entidades_totales": total, "entidades_con_mas_de_un_valor": 0, "sin_categoria": sin_cat}))
    ev = {"periodo": ctx.etiqueta_periodo(), "combinaciones_no_exclusivas": n_no_excl, "declaradas_evaluadas": n_decl, "declaradas_incumplidas": n_err}
    if n_err:
        resumen = d.resultado("cuadre_dimensiones", "error", n_error=n_err, evidencia=ev)
    elif n_no_excl:
        resumen = d.resultado("cuadre_dimensiones", "warning", n_no_exclusivas=n_no_excl, evidencia=ev)
    elif n_decl:
        resumen = d.resultado("cuadre_dimensiones", "valid", n_declaradas=n_decl, evidencia=ev)
    else:
        resumen = d.resultado("cuadre_dimensiones", "not_verifiable", evidencia=ev,
                              faltante=({"archivo": "reglas.json", "columna": "dimensiones (propiedades declaradas)", "granularidad": None},))
    return [resumen] + detalle


# ---------------------------------------------------------------------------------------------------- R-DENOM
@regla("R-DENOM")
def r_denom(ctx, d: Definicion) -> list[Resultado]:
    out = []
    for r in operandos.razones(ctx, d.p("filtro_canal_relacion")):
        ev = evaluar_razon(r)
        op = lambda o: {"valor": o.valor, "fuente": o.fuente, "periodo": o.periodo, "granularidad": o.granularidad, "nombre": o.nombre}   # noqa: E731
        evid = {"razon": r.id, "numerador": op(r.numerador), "denominador": op(r.denominador), "problemas": list(ev.problemas),
                "valor": None if ev.valor is None else str(ev.valor), "por_cien": r.por_cien}
        clave = {"valid": "razon_valida.valid", "warning": "razon_con_limitacion.warning", "error": "razon_invalida.error",
                 "not_verifiable": "razon_no_calculable.not_verifiable"}[ev.estado]
        out.append(d.resultado(f"razon_{r.id}", ev.estado, clave=clave, valor=ev.valor, faltante=ev.faltante, evidencia=evid, razon=r.nombre,
                               numerador=_n(r.numerador.valor) if r.numerador.valor is not None else "n/d", fuente_num=f"({r.numerador.fuente})",
                               denominador=_n(r.denominador.valor) if r.denominador.valor is not None else "n/d", fuente_den=f"({r.denominador.fuente})",
                               periodo=r.denominador.periodo, problemas="; ".join(ev.problemas)))
    return out
