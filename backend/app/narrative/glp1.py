"""Narrativa GLP-1 mensual: hechos e interpretaciones verificables a partir de los bloques del motor (sin causas externas)."""
from __future__ import annotations

from decimal import Decimal

from ..format import quantize_half_up
from ..models import GBlock, GRow, Period
from .aetops import ND, Box, count, money, pct_d
from .rules import RULES, NarrativeRules
from .writer import Para, fit, para, verify_all

SEX = {"femenino": "Mujer", "masculino": "Hombre"}
KEYS = {"edad": "edad", "sexo": "sexo", "dispositivo": "dispositivo"}


def pct2(d: Decimal | None) -> str:
    return ND if d is None else f"{quantize_half_up(d * 100, 2):,.2f}%"


def sx(s: str) -> str:
    return SEX.get(s.lower(), s)


def short(name: str, n: int = 44) -> str:
    if len(name) <= n:
        return name
    cut = name[:n].rsplit(" ", 1)[0]
    return cut + "…"


def v(r: GRow, k: str) -> Decimal | None:
    x = r.values.get(k)
    return x.v if x is not None else None


def dl(r: GRow) -> Decimal | None:
    return r.delta.v if r.delta is not None else None


def sh(r: GRow) -> str:
    return pct_d(r.share.v if r.share else None, sign=False)


def move(rows: list[GRow], rules: NarrativeRules) -> tuple[list[GRow], list[GRow]]:
    up = sorted((r for r in rows if dl(r) is not None and dl(r) >= rules.relevance), key=lambda r: -dl(r))
    dn = sorted((r for r in rows if dl(r) is not None and dl(r) <= -rules.relevance), key=lambda r: dl(r))
    return up, dn


def top(rows: list[GRow], k: str) -> GRow | None:
    ok = [r for r in rows if v(r, k) is not None]
    return max(ok, key=lambda r: v(r, k)) if ok else None


def _name(r: GRow, label=lambda s: s) -> str:
    return label(r.key)


# ----------------------------------------------------------------------------- por diapositiva
def s_quien(B: dict[str, GBlock], period: Period, rules: NarrativeRules) -> list[Para]:
    ps: list[Para] = []
    ed, sxb, dv = B["edad"].rows, B["sexo"].rows, B["dispositivo"].rows
    t = top(ed, "visitas")
    ordered = sorted(ed, key=lambda r: -(v(r, "visitas") or 0))
    up, dn = move(ed, rules)

    def edad(w):
        s = (f"**Visitas por Edad:**\nEl grupo de {w.b(t.key)} años es el principal perfil de búsqueda, con {w.n(count(v(t, 'visitas')))} visitas, "
             f"{w.n(count(v(t, 'usuarios')))} usuarios, {w.n(count(v(t, 'atc')))} Add to Cart y {w.n(sh(t))} de share.")
        if len(ordered) > 2:
            s += f" Le siguen {w.t(ordered[1].key)} con {w.n(sh(ordered[1]))} y {w.t(ordered[2].key)} con {w.n(sh(ordered[2]))}."
        if up:
            s += f" Sube más {w.t(up[0].key)} ({w.n(pct_d(dl(up[0])))})."
        if dn:
            s += f" Baja más {w.t(dn[0].key)} ({w.n(pct_d(dl(dn[0])))})."
        return s
    if t:
        ps.append(para("hecho", edad, 1, evidence=["bloque edad"]))
    ts = top(sxb, "visitas")
    if ts:
        other = [r for r in sxb if r is not ts]
        ps.append(para("hecho", lambda w: (
            f"**Sexo:**\n{w.b(sx(ts.key))} concentra el interés con {w.n(count(v(ts, 'visitas')))} visitas, {w.n(count(v(ts, 'usuarios')))} usuarios, "
            f"{w.n(count(v(ts, 'atc')))} Add to Cart y {w.n(sh(ts))} de share ({w.n(pct_d(dl(ts)))} vs {w.t(period.previous_month_name)})"
            + (f"; {sx(other[0].key).lower()} {w.n(pct_d(dl(other[0])))}." if other else ".")), 2, evidence=["bloque sexo"]))
    td = top(dv, "visitas")
    if td:
        sec = sorted(dv, key=lambda r: -(v(r, "visitas") or 0))
        ps.append(para("hecho", lambda w: (
            f"**Dispositivo:**\n{w.b(td.key.capitalize())} es el principal punto de entrada: {w.n(sh(td))} de share, {w.n(count(v(td, 'visitas')))} visitas y "
            f"{w.n(count(v(td, 'usuarios')))} usuarios ({w.n(pct_d(dl(td)))})."
            + (f" {w.t(sec[1].key.capitalize())} aporta {w.n(sh(sec[1]))} con {w.n(count(v(sec[1], 'visitas')))} visitas." if len(sec) > 1 else "")), 2,
            evidence=["bloque dispositivo"]))
    if t and ts and td:
        ps.append(para("interpretacion", lambda w: (
            f"**Lectura:**\nEn {w.t(period.month_name)}, el usuario que más busca {w.t("GLP1")} es {w.b(sx(ts.key).lower())}, de {w.b(t.key)} años y desde "
            f"{w.b(td.key.lower())}."), 3, basis="mayor número de visitas en cada dimensión (edad, sexo, dispositivo)"))
    return ps


def s_producto_sexo(B: dict[str, GBlock], period: Period, rules: NarrativeRules) -> list[Para]:
    rows = B["producto_sexo"].rows
    by: dict[str, list[GRow]] = {}
    for r in rows:
        by.setdefault(r.key, []).append(r)
    prods = sorted(by, key=lambda p: -sum(v(r, "visitas") or 0 for r in by[p]))
    ps: list[Para] = []
    for i, p in enumerate(prods[:3]):
        rs = sorted(by[p], key=lambda r: -(v(r, "visitas") or 0))

        def build(w, p=p, rs=rs):
            a = rs[0]
            s = (f"**{w.t(p)}:**\n{w.b(sx(a.dim2))} registra {w.n(count(v(a, 'visitas')))} visitas, {w.n(count(v(a, 'usuarios')))} usuarios y "
                 f"{w.n(count(v(a, 'atc')))} Add to Cart ({w.n(pct_d(dl(a)))})")
            if len(rs) > 1:
                b = rs[1]
                s += f"; {sx(b.dim2).lower()} tiene {w.n(count(v(b, 'visitas')))} visitas y {w.n(count(v(b, 'usuarios')))} usuarios ({w.n(pct_d(dl(b)))})."
            else:
                s += "."
            return s
        ps.append(para("hecho", build, 1 + i, evidence=["bloque producto_sexo"]))
    rest = prods[3:]
    if rest:
        def build_rest(w):
            parts = []
            for p in rest:
                for r in sorted(by[p], key=lambda r: r.dim2):
                    parts.append(f"{w.t(p)} {sx(r.dim2).lower()} {w.n(pct_d(dl(r)))}")
            return "**Otros productos:**\n" + "; ".join(parts) + "."
        ps.append(para("hecho", build_rest, 4, evidence=["bloque producto_sexo"]))
    f_dn = sum(1 for r in rows if r.dim2.lower() == "masculino" and dl(r) is not None and dl(r) < 0)
    m_total = sum(1 for r in rows if r.dim2.lower() == "masculino" and dl(r) is not None)
    if m_total:
        ps.append(para("interpretacion", lambda w: (
            f"**Lectura:**\nLa búsqueda cae en hombres en {w.n(str(f_dn))} de {w.n(str(m_total))} productos; el comportamiento no es igual en todo el público."),
            5, basis="productos con variación negativa en hombres sobre el total de productos"))
    return ps


def s_region(B, period, rules) -> list[Para]:
    reg, est = B["region"].rows, B["trafico_estado"].rows
    ps: list[Para] = []
    t = reg[0] if reg else None
    if t:
        up, dn = move(reg[1:], rules)
        ps.append(para("hecho", lambda w: (
            f"**Región:**\n{w.b(t.key.capitalize())} concentra la mayor venta con {w.n(sh(t))} de share, {w.n(money(v(t, 'monto')))}, "
            f"{w.n(count(v(t, 'pedidos')))} pedidos y {w.n(count(v(t, 'piezas')))} piezas ({w.n(pct_d(dl(t)))} vs {w.t(period.previous_month_name)})."), 1,
            evidence=["bloque region"]))
        if up or dn:
            def mv(w):
                bits = [f"{w.t(r.key.capitalize())} {w.n(pct_d(dl(r)))}" for r in (up[:3] + dn[:3])]
                return "Otras regiones con movimiento relevante: " + ", ".join(bits) + "."
            ps.append(para("hecho", mv, 3, evidence=["bloque region"]))
    te = est[0] if est else None
    if te:
        ps.append(para("hecho", lambda w: (
            f"En tráfico, {w.b(te.key)} es el principal mercado digital con {w.n(count(v(te, 'visitas')))} visitas y {w.n(count(v(te, 'usuarios')))} usuarios "
            f"({w.n(pct_d(dl(te)))})."), 2, evidence=["bloque trafico_estado"]))
        neg = [r for r in est[1:6] if dl(r) is not None and dl(r) <= -rules.relevance]
        if neg:
            ps.append(para("hecho", lambda w: (
                "Con variación negativa entre los siguientes mercados: " + ", ".join(f"{w.t(r.key)} {w.n(pct_d(dl(r)))}" for r in neg) + "."), 4,
                evidence=["bloque trafico_estado"]))
    return ps


def s_pago(B, period, rules) -> list[Para]:
    pago, ent = B["pago"].rows, B["entrega"].rows
    ps: list[Para] = []
    if pago:
        t = pago[0]
        up, dn = move(pago[1:], rules)
        ps.append(para("hecho", lambda w: (
            f"**Forma de Pago:**\n{w.b(t.key)} es la forma de pago más fuerte con {w.n(sh(t))} de share, {w.n(count(v(t, 'pedidos')))} pedidos y "
            f"{w.n(money(v(t, 'monto')))} en venta ({w.n(pct_d(dl(t)))})."
            + (" " + ", ".join(f"{w.t(r.key)} {w.n(pct_d(dl(r)))}" for r in (up[:2] + dn[:2])) + "." if (up or dn) else "")), 1, evidence=["bloque pago"]))
    if ent:
        t = ent[0]
        o = ent[1:]
        ps.append(para("hecho", lambda w: (
            f"**Modo de Entrega:**\n{w.b(t.key)} concentra {w.n(sh(t))} de la venta con {w.n(count(v(t, 'pedidos')))} pedidos y "
            f"{w.n(money(v(t, 'monto')))} ({w.n(pct_d(dl(t)))})"
            + (f"; {w.t(o[0].key)} {w.n(pct_d(dl(o[0])))}." if o else ".")), 2, evidence=["bloque entrega"]))
    return ps


def funnel_drop(F: GBlock):
    """Mayor caída relativa entre etapas consecutivas del embudo (hasta compra)."""
    st = [(r.key, r.values["conteo"].v) for r in F.rows[:4] if r.values["conteo"].v is not None]
    best = None
    for (a, ca), (b, cb) in zip(st, st[1:]):
        if ca:
            loss = 1 - cb / ca
            if best is None or loss > best[0]:
                best = (loss, a, b)
    return best


def s_funnel(B, F: GBlock | None, period, rules) -> list[Para]:
    ps: list[Para] = []
    if F:
        c = {r.key: r for r in F.rows}
        ver, atc, ini, com, aba = (c.get(k) for k in ("ver producto", "agregar a carrito", "iniciar compra", "compra", "carritos abandonados"))
        ps.append(para("hecho", lambda w: (
            f"**Patrones de Compra:**\nDe {w.n(count(ver.values['conteo'].v))} vistas de producto se generan {w.n(count(atc.values['conteo'].v))} Add to Cart, "
            f"{w.n(count(ini.values['conteo'].v))} inicios de compra y {w.n(count(com.values['conteo'].v))} compras. La conversión final queda en "
            f"{w.n(pct2(com.values['tasa_calc'].v))} y los carritos abandonados suman {w.n(count(aba.values['conteo'].v))}."), 1,
            evidence=["embudo"]))
        d = funnel_drop(F)
        if d:
            ps.append(para("interpretacion", lambda w: (
                f"La mayor pérdida del embudo ocurre entre «{w.t(d[1])}» y «{w.t(d[2])}»: se pierde {w.n(pct_d(Decimal(str(round(d[0], 4))), sign=False))} de las sesiones."),
                2, basis="mayor caída relativa entre etapas consecutivas del embudo"))
    neg = B.get("negados")
    if neg and neg.rows:
        t = neg.rows[0]
        ps.append(para("hecho", lambda w: (
            f"En negados, {w.b(short(t.key))} concentra {w.n(sh(t))} del monto negado, con {w.n(count(v(t, 'pedidos')))} pedidos, "
            f"{w.n(count(v(t, 'piezas')))} piezas y {w.n(money(v(t, 'monto_negado')))}."
            + (f" También aparecen {w.t(short(neg.rows[1].key))} y {w.n(str(len(neg.rows) - 2))} productos más." if len(neg.rows) > 2 else "")), 3,
            evidence=["bloque negados"]))
    return ps


def s_productos(B, period, rules) -> list[Para]:
    rows = sorted(B["productos"].rows, key=lambda r: -(v(r, "pedidos") or 0))[:10]
    allr = B["productos"].rows
    ps: list[Para] = []
    if allr:
        t3 = allr[:3]
        ps.append(para("hecho", lambda w: (
            "Las presentaciones que más venden: " + "; ".join(f"{w.b(short(r.key))} ({w.n(sh(r))}, {w.n(money(v(r, 'monto')))})" for r in t3) + "."), 1,
            evidence=["bloque productos"]))
        up, dn = move(allr[:10], rules)
        if up or dn:
            def mv(w):
                s = []
                if up:
                    s.append("Suben: " + ", ".join(f"{w.t(short(r.key, 30))} {w.n(pct_d(dl(r)))}" for r in up[:3]))
                if dn:
                    s.append("Bajan: " + ", ".join(f"{w.t(short(r.key, 30))} {w.n(pct_d(dl(r)))}" for r in dn[:3]))
                return ". ".join(s) + "."
            ps.append(para("hecho", mv, 2, evidence=["bloque productos"]))
        tot = sum((v(r, "monto") or Decimal(0)) for r in allr)
        t3m = sum((v(r, "monto") or Decimal(0)) for r in allr[:3])
        if tot:
            share = t3m / tot
            ps.append(para("interpretacion", lambda w: (
                f"Las tres presentaciones principales suman {w.n(pct_d(share, sign=False))} de la venta: el portafolio está {'concentrado' if share >= Decimal('0.5') else 'diversificado'}."),
                3, basis="participación acumulada de las 3 presentaciones con más venta (concentrado si ≥ 50 %)"))
    return ps


def s_programas(B, period, rules) -> list[Para]:
    rows = B["programas"].rows if "programas" in B else []
    ps: list[Para] = []
    if rows:
        t = rows[0]
        up, dn = move(rows[1:], rules)
        ps.append(para("hecho", lambda w: (
            f"**Programas de Apoyo**\n{w.b(t.key.title())} es el programa que más sostiene la venta, con {w.n(sh(t))} de share, {w.n(count(v(t, 'pedidos')))} pedidos, "
            f"{w.n(count(v(t, 'pacientes')))} pacientes y {w.n(money(v(t, 'monto')))} ({w.n(pct_d(dl(t)))})."), 1, evidence=["bloque programas"]))
        if up or dn:
            ps.append(para("hecho", lambda w: ", ".join(f"{w.t(r.key.title())} {w.n(pct_d(dl(r)))} ({w.n(money(v(r, 'monto')))})" for r in (up[:3] + dn[:2])) + ".", 2,
                           evidence=["bloque programas"]))
    return ps


def s_fuentes(B, period, rules) -> list[Para]:
    rows = B["fuentes"].rows
    ps: list[Para] = []
    if rows:
        a = rows[:2]
        ps.append(para("hecho", lambda w: (
            f"**Fuentes de Tráfico:**\n{w.b(a[0].key)}" + (f" y {w.b(a[1].key)}" if len(a) > 1 else "") + " son las fuentes con mayor volumen de visitas. " +
            " ".join(f"{w.t(r.key)} registra {w.n(count(v(r, 'visitas')))} visitas y {w.n(count(v(r, 'usuarios')))} usuarios." for r in a)), 1, evidence=["bloque fuentes"]))
        ta = top(rows, "atc")
        if ta:
            ps.append(para("hecho", lambda w: (
                f"En Add to Cart, {w.b(ta.key)} lidera con {w.n(count(v(ta, 'atc')))} ({w.n(pct_d(dl(ta)))} en visitas)."), 2, evidence=["bloque fuentes"]))
        ratio = [(r, (v(r, "atc") or 0) / v(r, "visitas")) for r in rows if v(r, "visitas") and v(r, "visitas") >= 500]
        if len(ratio) >= 2:
            best = max(ratio, key=lambda x: x[1])
            ps.append(para("interpretacion", lambda w: (
                f"{w.b(best[0].key)} convierte mejor a Add to Cart: {w.n(pct_d(Decimal(str(round(best[1], 4))), sign=False))} de sus visitas."), 3,
                basis="Add to Cart ÷ visitas, entre fuentes con 500 visitas o más"))
    return ps


def s_conclusiones(B, F, period, rules, sections: dict[str, list[Para]]) -> list[Para]:
    ps: list[Para] = []
    prod = B["productos"].rows
    if prod:
        t = prod[0]
        ps.append(para("hecho", lambda w: (
            f"**Venta**\n{w.b(short(t.key))} es la presentación con más venta ({w.n(money(v(t, 'monto')))}, {w.n(sh(t))} de share, {w.n(pct_d(dl(t)))} vs "
            f"{w.t(period.previous_month_name)})."), 1, evidence=["bloque productos"]))
    reg, pago = B["region"].rows, B["pago"].rows
    if reg and pago:
        ps.append(para("hecho", lambda w: (
            f"**Dónde y cómo se compra**\n{w.b(reg[0].key.capitalize())} aporta {w.n(sh(reg[0]))} de la venta y {w.b(pago[0].key)} {w.n(sh(pago[0]))}."), 2,
            evidence=["bloque region", "bloque pago"]))
    ed, sxb, dv = B["edad"].rows, B["sexo"].rows, B["dispositivo"].rows
    if ed and sxb and dv:
        te, ts, td = top(ed, "visitas"), top(sxb, "visitas"), top(dv, "visitas")
        ps.append(para("interpretacion", lambda w: (
            f"**Insights:**\nEn {w.t(period.month_name)}, el interés se concentra en {w.b(sx(ts.key).lower())}, de {w.b(te.key)} años y en {w.b(td.key.lower())}."), 3,
            basis="mayor número de visitas en cada dimensión (edad, sexo, dispositivo)"))
    if F:
        c = {r.key: r for r in F.rows}
        d = funnel_drop(F)
        if d:
            ps.append(para("recomendacion", lambda w: (
                f"**Acción sugerida:**\nRevisar el paso «{w.t(d[1])}» a «{w.t(d[2])}» del embudo: es donde se pierde {w.n(pct_d(Decimal(str(round(d[0], 4))), sign=False))} de las sesiones; "
                f"la conversión final es {w.n(pct2(c['compra'].values['tasa_calc'].v))}."), 4,
                basis="mayor caída relativa entre etapas consecutivas del embudo"))
    neg = B.get("negados")
    if neg and neg.rows and prod:
        tot_neg = sum((v(r, "monto_negado") or Decimal(0)) for r in neg.rows)
        tot_v = sum((v(r, "monto") or Decimal(0)) for r in prod)
        if tot_v and tot_neg / tot_v >= rules.materiality:
            ps.append(para("recomendacion", lambda w: (
                f"**Abasto:**\nLos negados suman {w.n(money(tot_neg))}, {w.n(pct_d(tot_neg / tot_v, sign=False))} de la venta del periodo: priorizar el abasto de "
                f"{w.b(short(neg.rows[0].key))}."), 5, basis="monto negado ≥ 1 % de la venta del periodo (producto sin stock negado a la venta)"))
    return ps


def compose_glp1(B: dict[str, GBlock], F: GBlock | None, period: Period, boxes: dict[str, Box], rules: NarrativeRules = RULES) -> dict[str, list[Para]]:
    sec = {
        "quien": s_quien(B, period, rules), "producto_sexo": s_producto_sexo(B, period, rules), "region": s_region(B, period, rules),
        "pago": s_pago(B, period, rules), "funnel": s_funnel(B, F, period, rules), "productos": s_productos(B, period, rules),
        "programas": s_programas(B, period, rules), "fuentes": s_fuentes(B, period, rules),
    }
    sec["conclusiones"] = s_conclusiones(B, F, period, rules, sec)
    return {k: fit(ps, boxes[k].cpl, boxes[k].lines) if k in boxes else ps for k, ps in sec.items()}


def check(narr: dict[str, list[Para]]) -> list[str]:
    return [f"{k}: {p}" for k, ps in narr.items() for p in verify_all(ps)]
