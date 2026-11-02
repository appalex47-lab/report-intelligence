"""Escritor de párrafos con registro de cifras y verificador (toda cifra del texto debe estar registrada)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Cifras: signo, $, dígitos con separadores y decimales, sufijo M/K, %, pp
NUMBER = re.compile(r"[+\-]?\$?\d+(?:,\d{3})*(?:\.\d+)?(?:\s?[MK])?%?(?:\s?pp)?")
CAUSAL = ("debido a", "por falta de", "porque", "gracias a", "causado", "se debe", "a raíz de",
          "por culpa", "como consecuencia de una")
KINDS = ("hecho", "interpretacion", "recomendacion", "contexto", "hipotesis", "info_insuficiente")


@dataclass
class Para:
    text: str                                   # con **negritas**
    kind: str
    priority: int = 5                           # 0 = obligatorio; mayor = se descarta antes
    basis: str = ""                             # regla que sustenta una interpretación
    evidence: list[str] = field(default_factory=list)
    nums: set[str] = field(default_factory=set)
    edited: bool = False
    visible: bool = True                        # False: nota de calidad de datos solo para narrative.json

    @property
    def plain(self) -> str:
        return self.text.replace("**", "")


class W:
    """Construye un párrafo y registra cada cifra que escribe."""

    def __init__(self):
        self.nums: set[str] = set()

    def n(self, s: str) -> str:                 # cifra en negrita
        self.nums.add(s.strip())
        return f"**{s}**"

    def t(self, s: str) -> str:                 # etiqueta que puede traer dígitos (nombres, periodos)
        self.nums.update(m.group(0).strip() for m in NUMBER.finditer(s))
        return s

    def b(self, s: str) -> str:                 # texto en negrita sin cifras (nombres)
        self.t(s)
        return f"**{s}**"


def para(kind: str, build, priority: int = 5, basis: str = "", evidence: list[str] | None = None) -> Para:
    w = W()
    text = build(w)
    return Para(text, kind, priority, basis, evidence or [], w.nums)


def verify(p: Para) -> list[str]:
    """Problemas del párrafo: cifras sin registrar, vocabulario causal, tipo inválido, interpretación sin regla."""
    problems = []
    if p.kind not in KINDS:
        problems.append(f"tipo inválido '{p.kind}'")
    if p.kind in ("hecho", "interpretacion", "recomendacion") and any(c in p.plain.lower() for c in CAUSAL):
        problems.append("vocabulario causal en un hecho/interpretación")
    if p.kind in ("interpretacion", "recomendacion") and not p.basis:
        problems.append(f"{p.kind} sin regla (basis)")
    if p.kind == "hipotesis":
        problems.append("hipótesis no permitida en modo determinista")
    for m in NUMBER.finditer(p.plain):
        tok = m.group(0).strip()
        if re.fullmatch(r"(19|20)\d\d", tok) or tok in p.nums:
            continue
        problems.append(f"cifra sin evidencia: '{tok}'")
    return problems


def verify_edited(text: str, allowed: set[str]) -> list[str]:
    """Texto editado a mano: no se le exige formato, pero una cifra que no existe en ningún insight se señala."""
    out = []
    if any(c in text.lower() for c in CAUSAL):
        out.append("vocabulario causal")
    for m in NUMBER.finditer(text.replace("**", "")):
        tok = m.group(0).strip()
        if not (re.fullmatch(r"(19|20)\d\d", tok) or tok in allowed):
            out.append(f"cifra no respaldada por los datos: '{tok}'")
    return out


def verify_all(paras: list[Para]) -> list[str]:
    return [f"{p.plain[:40]}…: {x}" for p in paras for x in verify(p)]


def fit(paras: list[Para], cpl: int, max_lines: int) -> list[Para]:
    """Quita párrafos de menor prioridad (mayor número) hasta que el texto quepa; nunca los de prioridad 0."""
    def lines(ps):
        return sum(max(1, -(-len(p.plain) // cpl)) for p in ps) + max(0, len(ps) - 1)

    keep = list(paras)
    while lines(keep) > max_lines:
        cand = [p for p in keep if p.priority > 0]
        if not cand:
            break
        keep.remove(max(cand, key=lambda p: (p.priority, keep.index(p))))
    return keep


def to_paragraphs(paras: list[Para]) -> list[str]:
    """Párrafos separados por un párrafo vacío, como en los originales."""
    out: list[str] = []
    for p in (q for q in paras if q.visible):
        if out:
            out.append("")
        out.append(p.text)
    return out
