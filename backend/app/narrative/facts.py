"""Hoja de hechos para el «descubrimiento único» con IA.

Cada hecho es una frase determinista y verificada (cifras ya calculadas por el motor), con un id y un tema. La IA solo puede
combinar estos hechos —citándolos— y no puede usar ninguna cifra que no esté en los hechos que cita (ver `verify_discovery`).
Los hechos incluyen cruces entre dimensiones (canal × línea, fuente × conversión, región × tráfico…) para que cada reporte
pueda sostener un hallazgo propio y no solo el titular de siempre.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal

from ..models import GBlock, GRow, Period
from . import insights as I
from .aetops import count, money, pct_d, pp_s
from .glp1 import cur_label, prev_label, short, sx
from .rules import RULES
from .writer import CAUSAL, NUMBER

YEAR = re.compile(r"(19|20)\d\d")


@dataclass
class Fact:
    id: str
    tema: str
    texto: str
    nums: set[str] = field(default_factory=set)

    def to_dict(self) -> dict:
        return {"id": self.id, "tema": self.tema, "texto": self.texto, "cifras": sorted(self.nums)}


def norm_tok(t: str) -> str:
    """Normaliza una cifra para compararla: sin espacios y sin '+' (el signo '-' sí cuenta: cambia el sentido)."""
    return re.sub(r"\s+", "", t).lstrip("+")


def tokens(text: str) -> set[str]:
    return {norm_tok(m.group(0)) for m in NUMBER.finditer(text.replace("**", "")) if m.group(0).strip()}


PREFIX = {"panorama": "PA", "canal": "CA", "línea": "LI", "categoría": "CT", "cruce": "CR", "producto": "PR", "negados": "NE", "meta": "ME", "embudo": "EM",
          "edad": "ED", "sexo": "SX", "dispositivo": "DI", "fuentes": "FU", "region": "RE", "pago": "PG", "entrega": "EN", "productos": "PD", "programas": "PM"}


class _Sheet:
    def __init__(self):
        self.items: list[Fact] = []
        self._n: dict[str, int] = {}

    def add(self, tema: str, texto: str):
        k = PREFIX.get(tema, "XX")
        self._n[k] = self._n.get(k, 0) + 1
        self.items.append(Fact(f"{k}{self._n[k]}", tema, texto, tokens(texto)))


def _d(x):
    return x.v if x is not None else None


# ------------------------------------------------------------------------------------------------ AETOPS
def aetops_facts(result, period: Period, att=None) -> list[Fact]:
    S = _Sheet()
    T = result.tables
    if "aetops.panorama.yoy" not in T:
        return []
    py = T["aetops.panorama.yoy"].groups[0]
    pm = T["aetops.panorama.mom"].groups[0] if "aetops.panorama.mom" in T else None
    prev_y = period.prev_year_label
    sales, tp = _d(py.current.values["monto"]), _d(py.previous.values["monto"])
    lab = {"monto": "venta", "pacientes": "pacientes", "piezas": "piezas", "pedidos": "pedidos", "ticket": "ticket promedio", "productos": "productos vendidos"}
    for k, name in lab.items():
        cur = _d(py.current.values[k])
        fmt = (lambda v: money(v)) if k in ("monto", "ticket") else (lambda v: count(v))
        mom = f"; {pct_d(_d(pm.pct[k]))} vs {period.previous_month_name}" if pm else ""
        S.add("panorama", f"Panorama: {name} de {period.label}: {fmt(cur)} ({pct_d(_d(py.pct[k]))} vs {prev_y}{mom}).")
    dec = I.decompose_sales(py.previous, py.current, RULES)
    if dec:
        S.add("panorama", f"El cambio anual de la venta se explica {pct_d(Decimal(str(round(dec.volume, 4))), False)} por volumen (pacientes y piezas por paciente) y "
                          f"{pct_d(Decimal(str(round(dec.price, 4))), False)} por venta por pieza.")
    v_pac = _d(py.current.values.get("v_paciente"))
    if v_pac:
        S.add("panorama", f"Valor por paciente: {money(v_pac)} ({pct_d(_d(py.pct.get('v_paciente')))} vs {prev_y}); piezas por paciente: {_d(py.current.values.get('size_b')):.2f} "
                          f"({pct_d(_d(py.pct.get('size_b')))}).")
    for kind, key, nm in (("canal", "aetops.canal.yoy", "Canal"), ("línea", "aetops.linea.yoy", "Línea"), ("categoría", "aetops.categoria.yoy", "Categoría")):
        if key not in T:
            continue
        cs = I.contributions(T[key].groups, tp, sales)
        by = {c.group.name: c for c in cs}
        for g in T[key].groups:
            c = by.get(g.name)
            share = ""
            if c and c.share_prev is not None and c.share_cur is not None:
                share = f"; participación {pct_d(c.share_prev, False)} → {pct_d(c.share_cur, False)} ({pp_s(c.pp)})"
            aporte = f"; aporta {money(c.delta, True)}" + (f" ({pct_d(c.share_of_change, False)} del avance)" if c and c.share_of_change else "") if c else ""
            S.add(kind, f"{nm} {g.name}: venta {money(_d(g.current.values['monto']))} ({pct_d(_d(g.pct['monto']))} vs {prev_y}){share}{aporte}; "
                        f"pacientes {pct_d(_d(g.pct['pacientes']))}, ticket {money(_d(g.current.values['ticket']))} ({pct_d(_d(g.pct['ticket']))}).")
    if "aetops.canal.yoy" in T and "aetops.linea.yoy" in T:
        # cruce canal × línea: qué canal depende más de qué línea no se puede sin filas crudas; sí se compara ticket y pacientes entre canales
        ch = T["aetops.canal.yoy"].groups
        best_t = max(ch, key=lambda g: _d(g.current.values["ticket"]) or 0)
        low_t = min(ch, key=lambda g: _d(g.current.values["ticket"]) or 0)
        if best_t is not low_t:
            S.add("cruce", f"Entre canales, el ticket promedio más alto es de {best_t.name} ({money(_d(best_t.current.values['ticket']))}) y el más bajo de {low_t.name} "
                           f"({money(_d(low_t.current.values['ticket']))}).")
    prods = result.products or {}
    names = {}
    for k in ("top", "growth", "decline"):
        for r in (prods.get(f"aetops.productos.{k}").rows if prods.get(f"aetops.productos.{k}") else []):
            names[r.producto] = short(r.producto, 40)
    for r in (prods["aetops.productos.top"].rows[:6] if "aetops.productos.top" in prods else []):
        S.add("producto", f"Producto {names[r.producto]} ({r.aetop}): venta {money(_d(r.actual))}, cambio {money(_d(r.delta), True)}; se vende en {count(_d(r.canales))} canales.")
    for k, lead in (("growth", "alza"), ("decline", "caída")):
        for r in (prods[f"aetops.productos.{k}"].rows[:4] if f"aetops.productos.{k}" in prods else []):
            nuevo = " (sin venta en el periodo previo)" if r.delta.status == "new_item" else ""
            S.add("producto", f"Mayor {lead}: {names[r.producto]} ({r.aetop}) {money(_d(r.delta), True)}{nuevo}.")
    if "aetops.productos.growth" in prods and "aetops.productos.decline" in prods:
        net = I.net_by_line(prods["aetops.productos.growth"].rows + prods["aetops.productos.decline"].rows)
        for ln, v in sorted(net.items(), key=lambda t: -abs(t[1]))[:3]:
            S.add("cruce", f"En la línea {ln}, las mayores alzas y caídas de productos suman {money(v, True)} netos.")
    alta, neg = result.negados.get("aetops.negados.alta"), result.negados.get("aetops.negados.producto")
    if alta and alta.total.v and sales:
        S.add("negados", f"Negados (producto sin stock negado a la venta): {money(alta.total.v)}, {pct_d(alta.total.v / sales, False)} de la venta del periodo.")
        for r in alta.rows[:3]:
            S.add("negados", f"Negados en {r.name}: {money(_d(r.monto))} ({pct_d(_d(r.share), False)} del total negado), {count(_d(r.pedidos))} pedidos.")
    if neg:
        for r in neg.rows[:3]:
            S.add("negados", f"Producto más negado {short(r.name, 40)}: {money(_d(r.monto))}, {count(_d(r.pedidos))} pedidos, {count(_d(r.cantidad))} piezas.")
    for a in (att or []):
        S.add("meta", f"Meta {a.name}: la venta alcanza {pct_d(a.pct, False)} de la meta de {money(a.target)} ({money(a.gap, True)}).")
    return S.items


# ------------------------------------------------------------------------------------------------ GLP-1
def _rate(num, den):
    return (num / den) if num is not None and den else None


def glp1_facts(blocks: dict[str, GBlock], funnel: GBlock | None, period: Period) -> list[Fact]:
    S = _Sheet()
    cur, prev = cur_label(period), prev_label(period)
    pano = blocks.get("panorama")
    if pano:
        P = pano.rows[0].values

        def ch(k, suf):
            a, b = _d(P.get(k)), _d(P.get(k + suf))
            return pct_d((a - b) / b) if a is not None and b else "n/d"
        for k, name, fmt in (("monto", "venta", money), ("pedidos", "pedidos", count), ("pacientes", "pacientes", count), ("ticket", "ticket promedio", money),
                             ("pacientes_nuevos", "pacientes nuevos", count)):
            if k in P:
                S.add("panorama", f"Panorama: {name} de {cur}: {fmt(_d(P[k]))} ({ch(k, '_prev')} vs {prev}; {ch(k, '_yoy')} vs el mismo periodo del año anterior).")
        if "compras" in P and "vistas_producto" in P and _d(P["vistas_producto"]):
            conv = _rate(_d(P["compras"]), _d(P["vistas_producto"]))
            S.add("embudo", f"Embudo: {count(_d(P['vistas_producto']))} vistas de producto, {count(_d(P['add_to_cart']))} add to cart, {count(_d(P['begin_checkout']))} inicios de compra y "
                            f"{count(_d(P['compras']))} compras; conversión final {conv * 100:.2f}%; carritos abandonados {count(_d(P['carritos_abandonados']))}.".replace("%;", "%;"))
    for name, label, key in (("edad", "Edad", "visitas"), ("sexo", "Sexo", "visitas"), ("dispositivo", "Dispositivo", "visitas"), ("fuentes", "Fuente de tráfico", "visitas")):
        b = blocks.get(name)
        if not b:
            continue
        tot = sum((_d(r.values["visitas"]) or 0) for r in b.rows)
        tot_atc = sum((_d(r.values["atc"]) or 0) for r in b.rows)
        for r in b.rows[:8]:
            vis, atc = _d(r.values["visitas"]), _d(r.values["atc"])
            tasa = _rate(atc, vis)
            share = vis / tot if tot and vis else None
            S.add(name, f"{label} {sx(r.key) if name == 'sexo' else r.key}: {count(vis)} visitas ({pct_d(share, False)} del total; {pct_d(_d(r.delta))} vs {prev}), "
                        f"{count(atc)} add to cart ({tasa * 100:.1f}% de sus visitas contra {(tot_atc / tot) * 100:.1f}% del total).")
    for name, label in (("region", "Región"), ("pago", "Forma de pago"), ("entrega", "Modo de entrega"), ("productos", "Producto"), ("programas", "Programa")):
        b = blocks.get(name)
        if not b:
            continue
        for r in b.rows[:6]:
            yoy = _d(r.delta_yoy) if r.delta_yoy is not None else None
            S.add(name, f"{label} {short(r.key, 40)}: venta {money(_d(r.values['monto']))} ({pct_d(_d(r.share), False)} del total; {pct_d(_d(r.delta))} vs {prev}"
                        + (f"; {pct_d(yoy)} vs el mismo periodo del año anterior" if yoy is not None else "") + f"), {count(_d(r.values['pedidos']))} pedidos, ticket {money(_d(r.values['ticket']))}.")
    # cruces: sexo × producto, edad × producto
    ps = blocks.get("producto_sexo")
    if ps:
        by: dict[str, dict[str, GRow]] = {}
        for r in ps.rows:
            by.setdefault(r.key, {})[sx(r.dim2)] = r
        for p, d in list(by.items())[:5]:
            if len(d) == 2:
                a, b = (d[k] for k in sorted(d))
                S.add("cruce", f"{p}: {sorted(d)[0].lower()} {count(_d(a.values['visitas']))} visitas ({pct_d(_d(a.delta))}) frente a {sorted(d)[1].lower()} {count(_d(b.values['visitas']))} ({pct_d(_d(b.delta))}).")
    for k, b in blocks.items():
        if k.startswith("edad_producto:") and b.rows:
            lead = max(b.rows, key=lambda r: _d(r.values["visitas"]) or 0)
            S.add("cruce", f"En {k.split(':', 1)[1].capitalize()}, el grupo de edad con más visitas es {lead.key} ({count(_d(lead.values['visitas']))}; {pct_d(_d(lead.delta))} vs {prev}).")
    can = blocks.get("canal_resumen")
    if can and len(can.rows) >= 2:
        for r in can.rows:
            v, a = _d(r.values["visitas"]), _d(r.values["atc"])
            S.add("fuentes", f"Canal {r.key}: {count(v)} visitas y {count(a)} add to cart ({_rate(a, v) * 100:.1f}% de sus visitas).")
    neg = blocks.get("negados")
    if neg and neg.rows and pano:
        tot = sum((_d(r.values["monto_negado"]) or 0) for r in neg.rows)
        S.add("negados", f"Negados (producto sin stock negado a la venta): {money(tot)}, {pct_d(tot / _d(pano.rows[0].values['monto']), False)} de la venta.")
        for r in neg.rows[:3]:
            S.add("negados", f"Producto más negado {short(r.key, 40)}: {money(_d(r.values['monto_negado']))}, {count(_d(r.values['pedidos']))} pedidos.")
    return S.items


# ------------------------------------------------------------------------------------------------ verificación del descubrimiento
MAX_BULLETS, MAX_LEN = 6, 380
TIPOS = ("hecho", "interpretacion", "hipotesis")


def bold_numbers(text: str) -> str:
    plain = text.replace("**", "")
    return NUMBER.sub(lambda m: f"**{m.group(0)}**" if m.group(0).strip() and not YEAR.fullmatch(m.group(0).strip()) else m.group(0), plain)


def verify_discovery(facts: list[Fact], payload: dict, strict: bool = True) -> dict:
    """Valida lo que devolvió la IA. Cada viñeta debe citar hechos que existen, usar solo cifras de los hechos citados,
    no usar vocabulario causal, y las hipótesis deben traer qué validar. El conjunto debe cruzar al menos dos temas."""
    byid = {f.id: f for f in facts}
    out = {"ok": False, "problemas": [], "titulo": "", "angulo": "", "viñetas": []}
    if not isinstance(payload, dict):
        out["problemas"].append("respuesta con formato inválido")
        return out
    titulo = str(payload.get("titulo") or "").strip()
    if not titulo or len(titulo) > 64:
        out["problemas"].append("falta el título o es demasiado largo (máximo 64 caracteres)")
    elif re.search(r"\d", YEAR.sub("", titulo)):
        out["problemas"].append("el título no debe llevar cifras")
    out["titulo"], out["angulo"] = titulo, str(payload.get("angulo") or "").strip()[:120]
    items = payload.get("viñetas") if isinstance(payload.get("viñetas"), list) else payload.get("vinetas")
    if not isinstance(items, list) or not ((2 if strict else 1) <= len(items) <= MAX_BULLETS):
        out["problemas"].append(f"se esperan entre {2 if strict else 1} y {MAX_BULLETS} viñetas")
        return out
    temas: set[str] = set()
    for it in items:
        probs: list[str] = []
        texto = str(it.get("texto") or "").strip() if isinstance(it, dict) else ""
        tipo = str(it.get("tipo") or "").strip().lower() if isinstance(it, dict) else ""
        ids = [str(x).strip() for x in (it.get("hechos") or [])] if isinstance(it, dict) and isinstance(it.get("hechos"), list) else []
        validar = str(it.get("validar") or "").strip() if isinstance(it, dict) else ""
        if tipo not in TIPOS:
            probs.append("tipo inválido")
        if not texto or len(texto) > MAX_LEN:
            probs.append("texto vacío o demasiado largo")
        if not ids:
            probs.append("no cita hechos")
        bad = [i for i in ids if i not in byid]
        if bad:
            probs.append("cita hechos que no existen: " + ", ".join(bad[:3]))
        cited = [byid[i] for i in ids if i in byid]
        allowed = set().union(*(f.nums for f in cited)) if cited else set()
        extra = sorted(t for t in tokens(texto + " " + validar) if t not in allowed and not YEAR.fullmatch(t))
        if extra:
            probs.append("cifra(s) que no están en los hechos citados: " + ", ".join(extra[:4]))
        if any(c in (texto + " " + validar).lower() for c in CAUSAL):
            probs.append("vocabulario causal")
        if re.search(r"https?://|www\.", texto):
            probs.append("contiene enlaces")
        if tipo == "hipotesis" and not validar:
            probs.append("una hipótesis debe indicar qué validar")
        temas |= {f.tema for f in cited}
        out["viñetas"].append({"ok": not probs, "problemas": probs, "tipo": tipo, "texto": bold_numbers(texto) if not probs else texto, "validar": validar,
                               "hechos": ids, "evidencia": [byid[i].texto for i in ids if i in byid]})
    good = [b for b in out["viñetas"] if b["ok"]]
    if strict and len(temas) < 2:
        out["problemas"].append("el descubrimiento debe cruzar al menos dos temas distintos")
    if strict and len(good) < 2:
        out["problemas"].append("menos de dos viñetas pasaron la verificación")
    if not strict and len(good) != len(out["viñetas"]):
        out["problemas"].append("hay viñetas que no pasan la verificación")
    out["ok"] = not out["problemas"]
    return out
