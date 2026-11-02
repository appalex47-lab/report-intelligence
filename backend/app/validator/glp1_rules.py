"""Reglas de validación GLP-1."""
from __future__ import annotations

from decimal import Decimal

from ..importer.glp1_blocks import RawGlp1
from ..importer.profile import GProfile, norm
from ..models import Finding, GBlock, Period

TOL = Decimal("0.005")           # 0.5 % entre hojas que deben cuadrar
MONEY_BLOCKS = ("region", "pago", "entrega", "programas")
TRAFFIC_BLOCKS = ("edad", "sexo", "dispositivo", "fuentes")


def _rounding_tol(p: Decimal) -> Decimal:
    exp = -p.normalize().as_tuple().exponent if p != 0 else 0
    return max(Decimal("0.000001"), Decimal("0.5") * Decimal(10) ** -max(exp, 0) + Decimal("0.000001"))


def _sum(b: GBlock, key: str) -> Decimal | None:
    vals = [r.values[key].v for r in b.rows if key in r.values and r.values[key].v is not None]
    return sum(vals, Decimal(0)) if vals else None


def _near(a: Decimal, b: Decimal) -> bool:
    return b != 0 and abs(a - b) / abs(b) <= TOL


def validate_glp1(raw: RawGlp1, blocks: dict[str, GBlock], funnel: GBlock | None,
                  profile: GProfile, period: Period | None) -> list[Finding]:
    out: list[Finding] = list(raw.findings)

    for name, b in blocks.items():
        if b.role == "prior":
            continue
        # claves duplicadas
        seen: dict[tuple, int] = {}
        for r in b.rows:
            k = (norm(r.key), norm(r.dim2))
            seen[k] = seen.get(k, 0) + 1
        dups = [k for k, n in seen.items() if n > 1]
        if dups:
            out.append(Finding("DUPLICATE_KEY", "warn", f"{name}: clave repetida {dups[0][0]!r}.", b.origin))
        # negativos
        for r in b.rows:
            for m in ("monto", "monto_negado", "piezas", "pedidos", "visitas"):
                v = r.values.get(m)
                if v is not None and v.v is not None and v.v < 0:
                    out.append(Finding("NEGATIVE_VALUE", "warn",
                                       f"{name} / {r.key}: {m} negativo ({v.v}).",
                                       v.src.cells if v.src else b.origin))
        # share pegado en 0 en todo el bloque
        pasted = [r.values["share"] for r in b.rows if "share" in r.values and r.values["share"].v is not None]
        if pasted and all(p.v == 0 for p in pasted):
            out.append(Finding("SHARE_ZERO", "warn",
                               f"{name}: la columna Share viene en 0 en todas las filas; se recalcula.", b.origin))
        elif pasted:
            bad = [r for r in b.rows if "share" in r.values and r.values["share"].v is not None
                   and r.share and r.share.v is not None
                   and abs(r.share.v - r.values["share"].v) > _rounding_tol(r.values["share"].v)]
            if bad:
                out.append(Finding("PASTED_DIFFERS", "warn",
                                   f"{name}: {len(bad)} share(s) pegados no coinciden con base ÷ total "
                                   f"(p. ej. {bad[0].key}).", b.origin))
        # ticket: definición del negocio = Monto ÷ Pedidos; el pegado solo se contrasta
        tk = [r for r in b.rows if r.ticket_calc and r.ticket_calc.v and r.pasted_ticket is not None and r.pasted_ticket.v
              and abs(r.ticket_calc.v - r.pasted_ticket.v) / r.pasted_ticket.v > TOL]
        if tk:
            r = tk[0]
            out.append(Finding("TICKET_PASTED_DIFFERS", "warn",
                               f"{name}: {len(tk)} fila(s) con Ticket del Excel ≠ Monto÷Pedidos (p. ej. {r.key}: "
                               f"Excel {float(r.pasted_ticket.v):,.2f} vs {float(r.ticket_calc.v):,.2f}). "
                               "Se usa Monto ÷ Pedidos (definición del negocio).",
                               r.pasted_ticket.src.cells if r.pasted_ticket.src else b.origin))
        # %Δ: MoM recalculado vs el pegado
        diff = [r for r in b.rows if r.engine_delta is not None and r.engine_delta.v is not None
                and r.pasted_delta and r.pasted_delta.v is not None
                and abs(r.engine_delta.v - r.pasted_delta.v) > max(Decimal("0.0005"), abs(r.pasted_delta.v) * Decimal("0.002"))]
        if diff:
            r = diff[0]
            out.append(Finding("DELTA_PASTED_DIFFERS", "warn",
                               f"{name}: {len(diff)} %Δ del Excel difieren del cambio contra el periodo anterior "
                               f"(p. ej. {r.key}: Excel {float(r.pasted_delta.v):+.4f} vs recalculado "
                               f"{float(r.engine_delta.v):+.4f}). Se usa el recalculado; revisar si el mes del libro "
                               "está completo.", r.pasted_delta.src.cells if r.pasted_delta.src else b.origin))
        elif b.role == "main" and not raw.blocks[name].prior and any(r.delta_src == "pasted" for r in b.rows):
            out.append(Finding("DELTA_FROM_EXCEL", "info",
                               f"{name}: el libro no trae el bloque del periodo anterior; se usa el %Δ del Excel.", b.origin))
        # nombres sin pareja en el periodo anterior / escritura distinta
        if b.role == "main" and raw.blocks[name].prior:
            prior = blocks.get(raw.blocks[name].prior["block"])
            if prior:
                pm = {norm(r.key): r.key for r in prior.rows}
                nomatch = [r.key for r in b.rows if norm(r.key) not in pm]
                if nomatch:
                    out.append(Finding("NO_PRIOR_MATCH", "info",
                                       f"{name}: sin pareja en el periodo anterior: {', '.join(nomatch[:3])}.",
                                       b.origin))
                variant = [(r.key, pm[norm(r.key)]) for r in b.rows if norm(r.key) in pm and pm[norm(r.key)] != r.key]
                if variant:
                    out.append(Finding("NAME_VARIANT", "info",
                                       f"{name}: misma entidad escrita distinto entre periodos "
                                       f"({variant[0][0]!r} vs {variant[0][1]!r}); se unió por nombre normalizado.",
                                       b.origin))
        # fila Total declarada vs suma
        for m, tv in b.declared_total.items():
            s = _sum(b, m)
            if s is not None and tv.v is not None and not _near(s, tv.v):
                out.append(Finding("TOTALS_MISMATCH", "warn",
                                   f"{name}: Σ {m} = {s} vs 'Total' del Excel {tv.v}.", b.origin))

    # --- cuadres entre hojas
    main = {n: b for n, b in blocks.items() if b.role == "main"}
    for metric in ("monto", "pedidos"):
        sums = {n: _sum(main[n], metric) for n in MONEY_BLOCKS if n in main}
        sums = {n: v for n, v in sums.items() if v is not None}
        if len(sums) >= 2:
            ref_n = "region" if "region" in sums else next(iter(sums))
            for n, v in sums.items():
                if n != ref_n and not _near(v, sums[ref_n]):
                    out.append(Finding("CROSS_SHEET_TOTALS", "warn",
                                       f"Σ {metric}: {n} = {v:,.0f} no cuadra con {ref_n} = {sums[ref_n]:,.0f}.",
                                       f"{main[n].sheet}"))
    prod, reg = main.get("productos"), main.get("region")
    if prod and reg:
        sp, sr = _sum(prod, "monto"), _sum(reg, "monto")
        if sp is not None and sr and sp > sr * (1 + TOL):
            out.append(Finding("CROSS_SHEET_TOTALS", "warn",
                               f"Σ monto de productos ({sp:,.0f}) excede el total de regiones ({sr:,.0f}).", "7"))
    vis = {n: _sum(main[n], "visitas") for n in TRAFFIC_BLOCKS if n in main}
    vis = {n: v for n, v in vis.items() if v is not None}
    if len(vis) >= 2:
        ref = vis.get("edad") or next(iter(vis.values()))
        for n, v in vis.items():
            if not _near(v, ref):
                out.append(Finding("CROSS_SHEET_TOTALS", "info",
                                   f"Σ visitas: {n} = {v:,.0f} vs edad = {ref:,.0f} (puede haber categorías "
                                   "sin clasificar).", main[n].sheet))
    if funnel and reg:
        compra = next((r for r in funnel.rows if norm(r.key) == "compra"), None)
        ped = _sum(reg, "pedidos")
        if compra and compra.values["conteo"].v is not None and ped is not None and not _near(compra.values["conteo"].v, ped):
            out.append(Finding("CROSS_SHEET_TOTALS", "info",
                               f"Embudo: Compra = {compra.values['conteo'].v:,.0f} vs Σ pedidos de región = {ped:,.0f} "
                               "(eventos de compra y pedidos pueden definirse distinto).", "5"))
    if funnel:
        for r in funnel.rows:
            t, tc = r.values["tasa"], r.values["tasa_calc"]
            if t.v is not None and tc.v is not None and abs(t.v - tc.v) > max(Decimal("0.0006"), abs(t.v) * Decimal("0.02")):
                out.append(Finding("PASTED_DIFFERS", "warn",
                                   f"Embudo / {r.key}: tasa pegada {float(t.v):.4f} vs conteo÷Ver producto "
                                   f"{float(tc.v):.4f}.", t.src.cells if t.src else "5"))

    # --- periodo
    if period is not None:
        d = raw.declared_period
        if d is None:
            out.append(Finding("PERIOD_UNDECLARED", "warn",
                               "El libro no declara su periodo; no se puede validar contra el periodo elegido "
                               "(revisar manualmente: los libros reales han mezclado periodos entre hojas).", ""))
        else:
            ok = (d[0] == "mes" and period.periodicity == "mensual" and d[1] == period.month_name and d[2] == period.year) \
                or (d[0] == "q" and period.periodicity == "trimestral" and d[1] == period.index and d[2] == period.year)
            if not ok:
                out.append(Finding("PERIOD_MISMATCH", "block",
                                   f"El libro declara {d[1]} {d[2]} pero el reporte es "
                                   f"{period.month_name if period.periodicity == 'mensual' else 'Q' + str(period.index)} "
                                   f"{period.year}.", ""))
    return out
