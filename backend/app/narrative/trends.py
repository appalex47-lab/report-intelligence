"""Tendencias a partir del historial (solo en la pantalla de revisión; no es una diapositiva del reporte).

Regla: 2 variaciones consecutivas del mismo signo (3 periodos contiguos), cada una fuera de la banda de estabilidad.
Con poco historial no se afirma nada ('información insuficiente')."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from ..history.store import Point, contiguous, series
from .aetops import money, pct_d
from .rules import RULES, NarrativeRules
from .writer import Para, para

LABELS = {"monto": "la venta", "pacientes": "los pacientes", "piezas": "las piezas", "pedidos": "los pedidos",
          "ticket": "el ticket promedio", "productos": "los productos vendidos"}
MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def plabel(periodicity: str, p: Point) -> str:
    return f"Q{p.idx} {p.year}" if periodicity == "trimestral" else f"{MONTHS[p.idx - 1]} {p.year}"


@dataclass
class Trend:
    metric: str
    direction: str                 # sube | baja | estable | insuficiente
    streak: int                    # variaciones consecutivas fuera de banda
    last: Decimal | None           # variación contra el periodo anterior
    cumulative: Decimal | None     # variación desde el inicio de la racha
    points: list[Point] = field(default_factory=list)
    para: Para | None = None


def analyze(periodicity: str, pts: list[Point], metric: str, rules: NarrativeRules = RULES) -> Trend:
    band = rules.relevance
    tail = pts[-6:]
    if len(tail) < 3:
        return Trend(metric, "insuficiente", 0, None, None, pts,
                     para("info_insuficiente", lambda w: (
                         f"Historial insuficiente para {LABELS.get(metric, metric)}: {w.n(str(len(pts)))} periodo(s); "
                         f"se necesitan al menos {w.n('3')}."), 3))
    # solo cuenta el tramo contiguo más reciente
    k = len(tail)
    while k > 1 and not contiguous(periodicity, tail[len(tail) - k:]):
        k -= 1
    seg = tail[len(tail) - k:]
    if len(seg) < 3:
        return Trend(metric, "insuficiente", 0, None, None, pts,
                     para("info_insuficiente", lambda w: f"Hay huecos en el historial de {LABELS.get(metric, metric)}.", 3))
    ch = [(b.value - a.value) / a.value for a, b in zip(seg, seg[1:]) if a.value]
    last = ch[-1]
    streak, sign = 0, 0
    for c in reversed(ch):
        s = 1 if c > band else -1 if c < -band else 0
        if s == 0 or (sign and s != sign):
            break
        sign, streak = s, streak + 1
    if streak < 2:
        t = Trend(metric, "estable" if abs(last) <= band else "mixta", streak, last, None, seg)
        t.para = para("hecho", lambda w: (
            f"{LABELS.get(metric, metric).capitalize()} no muestra una tendencia sostenida "
            f"({w.n(pct_d(last))} vs {w.t(plabel(periodicity, seg[-2]))})."), 4)
        return t
    start = seg[len(seg) - 1 - streak]
    cum = (seg[-1].value - start.value) / start.value
    word = "sube" if sign > 0 else "baja"
    ordinal = {2: "segundo", 3: "tercer", 4: "cuarto", 5: "quinto"}.get(streak, f"{streak}.º")
    unit = "trimestre" if periodicity == "trimestral" else "mes"
    t = Trend(metric, word, streak, last, cum, seg)
    t.para = para("interpretacion", lambda w: (
        f"{LABELS.get(metric, metric).capitalize()} {'crece' if sign > 0 else 'cae'} por {ordinal} {unit} consecutivo "
        f"({w.n(pct_d(last))} vs {w.t(plabel(periodicity, seg[-2]))} y {w.n(pct_d(cum))} desde {w.t(plabel(periodicity, start))})."), 2,
        basis=f"{streak} variaciones consecutivas del mismo signo, cada una fuera de la banda de ±{int(band * 100)} %")
    return t


def trends_for(con, unit: str, periodicity: str, metrics=("monto", "pacientes", "ticket"),
               scope: str = "panorama", name: str = "TOTAL", rules: NarrativeRules = RULES) -> list[Trend]:
    return [analyze(periodicity, series(con, unit, periodicity, scope, name, m), m, rules) for m in metrics]
