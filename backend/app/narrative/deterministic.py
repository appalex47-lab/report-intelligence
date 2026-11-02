"""Narrativa determinista (modo sin IA): solo hechos calculados, sin atribuir causas.

Entrada: tablas ya calculadas y validadas. Salida: párrafos con **negrita** en las cifras,
con el patrón de los reportes originales. La IA (Fase 6) podrá enriquecerlo, nunca inventar cifras.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from ..format import quantize_half_up
from ..models import Group, Period, ProductRow, Value

DASH = "n/d"


def pct(v: Value, sign: bool = True) -> str:
    if v.v is None:
        return DASH
    q = quantize_half_up(v.v * 100, 0)
    return (f"+{q:,.0f}%" if q > 0 and sign else f"{q:,.0f}%")


def money_short(v: Decimal | None, sign: bool = False) -> str:
    if v is None:
        return DASH
    a = abs(v)
    s = ("-" if v < 0 else "+" if sign and v > 0 else "")
    if a >= 1_000_000:
        return f"{s}${quantize_half_up(a / 1_000_000, 2):,.2f} M"
    if a >= 1_000:
        return f"{s}${quantize_half_up(a / 1_000, 1):,.1f} K"
    return f"{s}${quantize_half_up(a, 0):,.0f}"


def num(v: Value) -> str:
    return DASH if v.v is None else f"{quantize_half_up(v.v, 0):,.0f}"


def short(name: str) -> str:
    """'PROLIA 60MG/1ML JPRELL CAJ' -> 'Prolia'; 'RIM-VOQ 15 MG' -> 'Rim-Voq'."""
    w = name.split()[0] if name.split() else name
    return "-".join(p.capitalize() for p in w.split("-"))


def verb(v: Value, up="crece", down="cae", flat="se mantiene") -> str:
    if v.v is None:
        return "sin dato"
    return up if v.v > 0 else down if v.v < 0 else flat


def b(x: str) -> str:
    return f"**{x}**"


# --------------------------------------------------------------------------- panorama
def panorama(yoy: Group, mom: Group, period: Period) -> list[str]:
    c = yoy.current.values
    prev_year = yoy.previous.label
    p1 = (f"En {b(period.month_name)}, la venta total AETOP llega a {b(money_short(c['monto'].v))} y "
          f"{verb(yoy.pct['monto'])} {b(pct(yoy.pct['monto']))} vs {prev_year}.")
    p2 = (f"Piezas {b(pct(yoy.pct['piezas']))}, pacientes {b(pct(yoy.pct['pacientes']))} y "
          f"pedidos {b(pct(yoy.pct['pedidos']))} contra {prev_year}.")
    p3 = (f"Contra {period.previous_month_name}, la venta {verb(mom.pct['monto'], 'sube', 'baja')} "
          f"{b(pct(mom.pct['monto']))}; piezas {b(pct(mom.pct['piezas']))}, pacientes "
          f"{b(pct(mom.pct['pacientes']))} y pedidos {b(pct(mom.pct['pedidos']))}.")
    p4 = (f"El ticket promedio cambia {b(pct(yoy.pct['ticket']))} YoY y {b(pct(mom.pct['ticket']))} MoM. "
          f"Se venden {b(num(c['productos']))} productos.")
    return [p1, "", p2, "", p3, "", p4]


# --------------------------------------------------------------------------- grupos (canal / línea / categoría)
def groups(gs: list[Group], what: str) -> list[str]:
    out: list[str] = []
    for g in gs:
        c, p = g.current.values, g.pct
        out.append(f"{b(g.name)}: venta {b(pct(p['monto']))}, piezas {b(pct(p['piezas']))}, "
                   f"pacientes {b(pct(p['pacientes']))}, pedidos {b(pct(p['pedidos']))}; "
                   f"share {b(pct(c['share'], sign=False))}.")
        out.append("")
    return out[:-1] if out else [f"Sin {what} para mostrar."]


def groups_compact(gs: list[Group], detail: int = 3) -> list[str]:
    """Para listas largas (categorías): detalle de los extremos y una línea con el resto."""
    ok = [g for g in gs if g.pct["monto"].v is not None]
    if not ok:
        return ["Sin categorías para mostrar."]
    ranked = sorted(ok, key=lambda g: g.pct["monto"].v, reverse=True)
    picked: list[Group] = ranked[:2]
    worst = ranked[-1]
    if worst not in picked and worst.pct["monto"].v < 0:
        picked.append(worst)
    out: list[str] = []
    for g in picked[:detail]:
        c, p = g.current.values, g.pct
        out += [f"{b(g.name)}: venta {b(pct(p['monto']))}, piezas {b(pct(p['piezas']))}, "
                f"pedidos {b(pct(p['pedidos']))}; share {b(pct(c['share'], sign=False))}.", ""]
    rest = [g for g in ok if g not in picked]
    if rest:
        out.append("Resto: " + ", ".join(f"{b(g.name)} {b(pct(g.pct['monto']))}" for g in rest) + ".")
    else:
        out.pop()
    return out


# --------------------------------------------------------------------------- productos
def top_products(rows: list[ProductRow]) -> list[str]:
    if not rows:
        return ["Sin productos para mostrar."]
    top = rows[0]
    out = [f"{b(short(top.producto))} es el primer producto de la lista, con {b(money_short(top.actual.v))} y "
           f"{b(money_short(top.delta.v, sign=True))} contra el mes anterior."]
    if len(rows) > 1:
        rest = ", ".join(f"{b(short(r.producto))} ({b(money_short(r.actual.v))})" for r in rows[1:4])
        out += ["", f"Le siguen {rest}."]
    return out


def movers(rows: list[ProductRow], kind: str) -> list[str]:
    if not rows:
        return ["Sin productos para mostrar."]
    items = ", ".join(f"{b(short(r.producto))} ({b(money_short(r.delta.v, sign=True))})" for r in rows[:5])
    lead = "El crecimiento lo encabezan" if kind == "growth" else "Las principales caídas son"
    return [f"{lead} {items}."]


# --------------------------------------------------------------------------- negados
def negados(alta, producto) -> list[str]:
    if alta is None or not alta.rows:
        return ["Sin información de negados."]
    rows = sorted(alta.rows, key=lambda r: r.monto.v or Decimal(0), reverse=True)
    lead = rows[0]
    out = [f"El monto negado total asciende a {b(money_short(alta.total.v))}, concentrado principalmente en "
           f"{b(lead.name)} con {b(money_short(lead.monto.v))} y {b(pct(lead.share, sign=False))} de share."]
    if len(rows) > 1:
        out[0] += (f" Le sigue {b(rows[1].name)} con {b(money_short(rows[1].monto.v))} y "
                   f"{b(pct(rows[1].share, sign=False))}.")
    if producto and producto.rows:
        tops = sorted(producto.rows, key=lambda r: r.monto.v or Decimal(0), reverse=True)[:3]
        out += ["", "Los productos con mayor monto negado son " +
                ", ".join(f"{b(short(r.name))} ({b(money_short(r.monto.v))})" for r in tops) + "."]
    return out


# --------------------------------------------------------------------------- conclusiones
def conclusions(yoy: Group, mom: Group, canal: list[Group], linea: list[Group], period: Period,
                neg_total: Decimal | None) -> list[str]:
    def line(label: str, key: str) -> str:
        return (f"{label} {verb(yoy.pct[key], 'creció', 'cayó', 'se mantuvo')} "
                f"{b(pct(yoy.pct[key]))} YoY y {b(pct(mom.pct[key]))} MoM")
    out = [line("El monto de venta", "monto"), line("La cantidad de piezas", "piezas"),
           line("La cantidad de pacientes", "pacientes"), line("La cantidad de pedidos", "pedidos"),
           line("El ticket promedio", "ticket"), "", "**Insights clave:**"]
    def best(gs, key="monto"):
        ok = [g for g in gs if g.pct[key].v is not None]
        return (max(ok, key=lambda g: g.pct[key].v), min(ok, key=lambda g: g.pct[key].v)) if ok else (None, None)
    hi, lo = best(canal)
    if hi:
        out += ["", f"Por canal, {b(hi.name)} tiene el mayor avance YoY en venta ({b(pct(hi.pct['monto']))}) y "
                    f"{b(lo.name)} el menor ({b(pct(lo.pct['monto']))})."]
    hi, lo = best(linea)
    if hi:
        out += ["", f"Por línea, {b(hi.name)} tiene el mayor avance YoY ({b(pct(hi.pct['monto']))}) y "
                    f"{b(lo.name)} el menor ({b(pct(lo.pct['monto']))})."]
    if neg_total is not None:
        out += ["", f"Los negados suman {b(money_short(neg_total))}."]
    return out
