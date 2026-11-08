"""Fase 5 · AC-14: comprobaciones de CIFRAS, FÓRMULAS, UNIDADES y DENOMINADORES sobre el PPTX exportado (spec Fase 1 §7.A, §3.2; RQ-13; T-11).

Se ejecutan sobre el `.pptx` ya guardado y reciben, además, los valores que calculó el motor (`recolectar_valores`). Lo que no pueden saber (el significado
de cada celda de cada plantilla) NO se adivina: solo se comprueba lo que se puede demostrar con lo impreso y con lo calculado.

  PPTX_CIFRA_NO_TRAZADA   un número impreso no coincide —dentro de la precisión con que se imprimió— con ningún valor del motor, ni con una cifra de la narrativa
                          verificada, ni se obtiene de dos números de la misma lámina (razón, diferencia o variación). Los formatos ($1.04 M, 56%, +$639.1 K), los redondeos y
                          el linaje no cuentan como diferencia.
  PPTX_FORMULA_NO_COINCIDE  en una tabla, un derivado impreso no sale de lo impreso en sus propias columnas: Ticket = Monto ÷ Pedidos; % de la fila de
                          variación = fila actual ÷ fila anterior − 1; «avanza X %» del embudo = etapa ÷ etapa anterior.
  PPTX_UNIDAD_AMBIGUA     una columna mezcla unidades (dinero con y sin `$`, conteos con `$` o `%`, porcentajes sin `%`) o aparece una moneda/unidad que ningún libro declara
                          (MXN, USD, pesos, dólares…).
  PPTX_SIN_DENOMINADOR    una oración con un porcentaje no dice respecto de qué (no hay base: «vs», «de la venta», «del avance», «de share», «del periodo», …).

Severidad: `warn`. Son comprobaciones heurísticas sobre texto: un falso positivo no debe bloquear la descarga de un reporte válido (los tokens técnicos, que sí
bloquean, están en `pptx_export`). Calibración: 0 hallazgos en los 4 decks de referencia; cada defecto inyectado se detecta (tests/unit/test_qa_cifras.py).

Límites declarados: no valida el SIGNIFICADO de una cifra (que «927» sean pedidos), solo que provenga del motor o de lo impreso; las columnas se reconocen por el
texto de su encabezado; las celdas que son nombres de producto, códigos o horas no se tratan como cifras.
"""
from __future__ import annotations

import bisect
import dataclasses
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .checks import Issue

NUM = re.compile(r"(?<![\w:/.\-])[+\-−]?\$?\d{1,3}(?:,\d{3})+(?:\.\d+)?(?:\s?[MK](?![A-Za-z]))?%?(?:\s?pp)?(?![\w/]|:\d|-\d)|(?<![\w:/.\-])[+\-−]?\$?\d+(?:\.\d+)?(?:\s?[MK](?![A-Za-z]))?%?(?:\s?pp)?(?![\w/]|:\d|-\d)")
ANIO = re.compile(r"(19|20)\d\d")
MAYUSCULAS = re.compile(r"\b[A-ZÁÉÍÓÚÑ]{2,}\b")
MONEDA_INVENTADA = re.compile(r"\b(MXN|USD|EUR|COP|ARS|CLP|PEN)\b|€|£|\b(pesos|d[oó]lares|euros)\b", re.I)
ANCLAS = re.compile(r"\bvs\b|\bde (la|las|los|el|lo) \w|\bdel \w|frente a|contra |respecto|convierte|conversi[oó]n|equivale|participaci|share|avance|\bsobre (la|el|los|las) ", re.I)
TOL_REL = Decimal("0.0001")


# --------------------------------------------------------------------------------------------- valores de origen
def recolectar_valores(obj, _vistos=None, _out=None) -> set[Decimal]:
    """Todos los `Value.v` numéricos (y Decimal sueltos) que contiene el resultado del motor, recorrido de forma genérica."""
    _vistos = _vistos if _vistos is not None else set()
    out = _out if _out is not None else set()
    if id(obj) in _vistos:
        return out
    if isinstance(obj, Decimal):
        out.add(obj)
        return out
    if isinstance(obj, (str, bytes, int, float, bool)) or obj is None:
        return out
    _vistos.add(id(obj))
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        for f in dataclasses.fields(obj):
            recolectar_valores(getattr(obj, f.name, None), _vistos, out)
    elif isinstance(obj, dict):
        for v in obj.values():
            recolectar_valores(v, _vistos, out)
    elif isinstance(obj, (list, tuple, set, frozenset)):
        for v in obj:
            recolectar_valores(v, _vistos, out)
    return out


# --------------------------------------------------------------------------------------------- números impresos
def analizar(token: str):
    """(valor, es_porcentaje, tolerancia) de un número impreso; la tolerancia es media unidad del último dígito impreso."""
    t = token.replace("−", "-").replace("$", "").replace(",", "").strip()
    mult, pct = Decimal(1), False
    if t.endswith("pp"):
        t = t[:-2].strip()
    if t.endswith("%"):
        pct, t = True, t[:-1]
    if t.endswith("M"):
        mult, t = Decimal(10) ** 6, t[:-1].strip()
    elif t.endswith("K"):
        mult, t = Decimal(10) ** 3, t[:-1].strip()
    try:
        v = Decimal(t)
    except InvalidOperation:
        return None
    dec = max(0, -v.as_tuple().exponent)
    return v * mult, pct, (Decimal(10) ** (-dec)) * mult / 2


def _es_nombre_o_codigo(token: str, texto: str, ini: int, fin: int) -> bool:
    """Un número plano (entero o decimal) dentro de un nombre de producto («ENZALUTAMIDA 40 MG») o un código (≥ 5 dígitos sin separadores) no es una cifra."""
    if re.fullmatch(r"\d{5,}", token):
        return True
    if re.fullmatch(r"\d+(?:\.\d+)?", token):
        previo = re.search(r"(\S+)\s*$", texto[:ini])
        sig = re.match(r"\s*(\S+)", texto[fin:])
        for w in (previo.group(1) if previo else "", sig.group(1) if sig else ""):
            if MAYUSCULAS.fullmatch(w.strip("()/,.")):
                return True
    return False


def numeros(texto: str):
    """(token, inicio, fin) de los números del texto que SÍ son cifras (sin años, índices de lista, horas, códigos ni nombres)."""
    for m in NUM.finditer(texto):
        tok = m.group(0).strip()
        if ANIO.fullmatch(tok) or re.fullmatch(r"\d{1,2}\.", texto[m.start():m.end() + 1].strip()) and m.start() == 0:
            continue
        if _es_nombre_o_codigo(tok, texto, m.start(), m.end()):
            continue
        if analizar(tok) is None:
            continue
        yield tok, m.start(), m.end()


class Indice:
    """Valores del motor ordenados para buscar coincidencias dentro de una tolerancia."""
    def __init__(self, valores):
        self.v = sorted({abs(x) for x in valores})
        self.f = [float(x) for x in self.v]

    def hay(self, objetivo: Decimal, tol: Decimal) -> bool:
        o, t = float(abs(objetivo)), float(tol) * 1.02 + 1e-12
        i = bisect.bisect_left(self.f, o - t)
        return i < len(self.f) and self.f[i] <= o + t


def trazable(tok: str, ind: Indice, narrativa: set[str]) -> bool:
    if tok in narrativa:
        return True
    a = analizar(tok)
    v, pct, tol = a
    if ind.hay(v, tol):
        return True
    if pct:                                              # un porcentaje impreso puede ser una fracción del motor (0.56 → 56%)
        return ind.hay(v / 100, tol / 100)
    return False


def derivable(tok: str, operandos: list[Decimal]) -> bool:
    """¿Es una razón o una variación de dos números cercanos? Solo para PORCENTAJES y con operandos acotados (la misma celda o párrafo, o las formas generadas `RI_*`
    de la lámina): con todos los números de una lámina habría coincidencias por azar y un porcentaje alterado pasaría por «derivable»."""
    v, pct, tol = analizar(tok)
    if not pct:
        return False
    for a in operandos:
        for b in operandos:
            if b == 0 or a == b:
                continue
            for calc in (a / b * 100, (a / b - 1) * 100):
                if abs(abs(calc) - abs(v)) <= tol * Decimal("1.05"):
                    return True
    return False


def _celdas_y_textos(prs, omitir=()):
    """(n.º de diapositiva, tipo, texto, forma) para cada celda de tabla y cada párrafo de texto."""
    for i, s in enumerate(prs.slides, 1):
        if i in omitir:
            continue
        for sh in s.shapes:
            if getattr(sh, "has_table", False) and sh.has_table:
                codigos = {j for j, c in enumerate(sh.table.rows[0].cells) if c.text_frame.text.strip().lower() == "sivec"}     # columna de CÓDIGOS de producto: no son cifras (un código de 4 cifras, «7928», parecía una)
                for r in sh.table.rows:
                    for j, c in enumerate(r.cells):
                        if j not in codigos and c.text_frame.text.strip():
                            yield i, "tab", c.text_frame.text, sh
            elif sh.has_text_frame:
                for p in sh.text_frame.paragraphs:
                    if p.text.strip():
                        yield i, "txt", p.text, sh


# --------------------------------------------------------------------------------------------- cifras
def comprobar_cifras(prs, valores, narrativa: set[str], omitir=()) -> list[Issue]:
    ind = Indice(valores)
    por_diap: dict[int, list] = {}
    for i, tipo, texto, sh in _celdas_y_textos(prs, omitir):
        por_diap.setdefault(i, []).append((texto, sh.name or ""))
    out: list[Issue] = []
    for i, items in por_diap.items():
        generados = [analizar(t)[0] for texto, nombre in items if nombre.startswith("RI_") for t, _, _ in numeros(texto) if not analizar(t)[1]]
        for texto, nombre in items:
            locales = [analizar(t)[0] for t, _, _ in numeros(texto) if not analizar(t)[1]]
            for tok, a, b in numeros(texto):
                if not trazable(tok, ind, narrativa) and not derivable(tok, locales + generados):
                    out.append(Issue("PPTX_CIFRA_NO_TRAZADA", "warn", i, f"La cifra «{tok}» no coincide con ningún valor del motor ni se obtiene de lo impreso junto a ella (en «{texto[:50]}»)."))
    return out


# --------------------------------------------------------------------------------------------- fórmulas y unidades en tablas
ROL = (("ticket", re.compile(r"ticket", re.I)), ("monto", re.compile(r"monto|venta|importe", re.I)), ("pedidos", re.compile(r"pedidos", re.I)),
       ("pacientes", re.compile(r"pacientes", re.I)), ("piezas", re.compile(r"piezas|cantidad", re.I)), ("pct", re.compile(r"share|%\s?Δ|% ?d|var|delta", re.I)))
DINERO, CONTEO = {"monto", "ticket"}, {"pedidos", "pacientes", "piezas"}


def _rol(encabezado: str) -> str | None:
    h = re.sub(r"\s+", " ", encabezado).strip()
    if re.search(r"venta mes|delta", h, re.I) and re.search(r"delta", h, re.I):
        return "pct" if re.search(r"%", h) else "delta"
    for nombre, rx in ROL:
        if rx.search(h):
            return nombre
    return None


def _valor(celda: str):
    m = next(iter(numeros(celda)), None)
    return None if m is None else (m[0], analizar(m[0]))


def _bloques(filas):
    """Una tabla puede apilar varios bloques (p. ej. productos y resumen por alta): cada fila con ≥ 2 encabezados reconocidos abre un bloque y una fila vacía lo cierra."""
    bloques, actual = [], None
    for f in filas:
        roles = [_rol(c) for c in f]
        if not any(c for c in f):
            actual = None
        elif sum(r is not None for r in roles) >= 2 and not any(_valor(c) for c in f):
            actual = (f, roles, [])
            bloques.append(actual)
        elif actual is not None:
            actual[2].append(f)
    return bloques


def comprobar_tablas(prs) -> list[Issue]:
    out: list[Issue] = []
    for i, s in enumerate(prs.slides, 1):
        for sh in s.shapes:
            if not (getattr(sh, "has_table", False) and sh.has_table):
                continue
            filas = [[c.text_frame.text.strip() for c in r.cells] for r in sh.table.rows]
            for hdr, roles, datos in _bloques(filas):
                out += _comprobar_bloque(i, hdr, roles, datos)
    return out


def _comprobar_bloque(i: int, hdr: list, roles: list, datos: list) -> list[Issue]:
    out: list[Issue] = []
    es_variacion = lambda r: any(_valor(c) for c in r) and all("%" in c for c in r if _valor(c))                      # noqa: E731
    base = [r for r in datos if not es_variacion(r)]                          # las filas de variación (todo en %) se comprueban aparte
    # --- unidades por columna
    for j, rol in enumerate(roles):
        celdas = [(r, r[j]) for r in (datos if rol == "pct" else base) if j < len(r) and _valor(r[j])]
        if not celdas or rol is None:
            continue
        con_dinero = [("$" in c) for _, c in celdas]
        con_pct = [("%" in c) for _, c in celdas]
        if rol in DINERO and not (all(con_dinero) or not any(con_dinero)):
            out.append(Issue("PPTX_UNIDAD_AMBIGUA", "warn", i, f"La columna «{hdr[j][:30]}» mezcla cifras con y sin `$`."))
        if rol in CONTEO and (any(con_dinero) or any(con_pct)):
            out.append(Issue("PPTX_UNIDAD_AMBIGUA", "warn", i, f"La columna de conteos «{hdr[j][:30]}» trae `$` o `%`."))
        if rol == "pct" and not all(con_pct):
            out.append(Issue("PPTX_UNIDAD_AMBIGUA", "warn", i, f"La columna de porcentajes «{hdr[j][:30]}» trae cifras sin `%`."))
    # --- fórmula: ticket = monto ÷ pedidos
    c_t = next((j for j, r in enumerate(roles) if r == "ticket"), None)
    c_m = next((j for j, r in enumerate(roles) if r == "monto"), None)
    c_p = next((j for j, r in enumerate(roles) if r == "pedidos"), None)
    if None not in (c_t, c_m, c_p):
        for r in base:
            t, m, p = (_valor(r[c]) if c < len(r) else None for c in (c_t, c_m, c_p))
            if t and p and p[1][0] == 0:
                out.append(Issue("PPTX_FORMULA_NO_COINCIDE", "warn", i, f"Ticket impreso {t[0]} con 0 pedidos: el denominador es cero, debería ser «No calculable»."))
            elif t and m and p and p[1][0] != 0:
                esperado = m[1][0] / p[1][0]
                tol = t[1][2] + m[1][2] / p[1][0] + abs(esperado) * p[1][2] / p[1][0]
                if abs(abs(t[1][0]) - abs(esperado)) > tol * Decimal("1.05"):
                    out.append(Issue("PPTX_FORMULA_NO_COINCIDE", "warn", i, f"Ticket impreso {t[0]} ≠ Monto {m[0]} ÷ Pedidos {p[0]} = {esperado:,.2f}."))
    # --- fórmula: fila de variación = actual ÷ anterior − 1
    for k in range(2, len(datos)):
        fila, act, ant = datos[k], datos[k - 1], datos[k - 2]
        if not es_variacion(fila):
            continue
        for j, c in enumerate(fila):
            pv = _valor(c)
            a1, a0 = (_valor(act[j]) if j < len(act) else None, _valor(ant[j]) if j < len(ant) else None)
            if pv and a1 and a0 and a0[1][0] != 0 and not a1[1][1] and not a0[1][1] and roles[j] in DINERO | CONTEO:
                esperado = (a1[1][0] / a0[1][0] - 1) * 100
                tol = pv[1][2] + (abs(a1[1][0] / a0[1][0]) * (a1[1][2] / abs(a1[1][0] or 1) + a0[1][2] / abs(a0[1][0]))) * 100
                if abs(pv[1][0] - esperado) > tol * Decimal("1.05"):
                    out.append(Issue("PPTX_FORMULA_NO_COINCIDE", "warn", i, f"Variación impresa {pv[0]} ≠ {a1[0]} ÷ {a0[0]} − 1 = {esperado:,.1f} % (columna «{hdr[j][:25]}»)."))
    return out


def comprobar_moneda(prs) -> list[Issue]:
    out: list[Issue] = []
    for i, tipo, texto, sh in _celdas_y_textos(prs):
        if m := MONEDA_INVENTADA.search(texto):
            out.append(Issue("PPTX_UNIDAD_AMBIGUA", "warn", i, f"Aparece «{m.group(0)}»: ningún libro declara la moneda; no se inventan monedas ni unidades."))
    return out


# --------------------------------------------------------------------------------------------- denominadores
def comprobar_denominadores(prs, omitir=()) -> list[Issue]:
    """Un párrafo con un porcentaje de PROPORCIÓN debe nombrar su base («de la venta», «de share», «del avance», «convierte … en …», …) en algún punto del párrafo
    (varias oraciones comparten la base que se declara una vez). Las variaciones con signo (+8 %, −3 %) o 0 % heredan su base de la comparación («vs agosto»).
    Solo se revisa el texto corrido, no las tablas."""
    out: list[Issue] = []
    for i, tipo, texto, sh in _celdas_y_textos(prs, omitir):
        if tipo != "txt" or len(texto) < 25:
            continue
        pcts = re.findall(r"[+\-−]?\d[\d,]*(?:\.\d+)?\s?%", texto)
        proporciones = [p for p in pcts if p[0] not in "+-−" and analizar(p)[0] != 0]
        if proporciones and not ANCLAS.search(texto):
            out.append(Issue("PPTX_SIN_DENOMINADOR", "warn", i, f"Porcentaje sin base declarada: «{texto[:70]}»."))
    return out


# --------------------------------------------------------------------------------------------- API
def revisar(path: str | Path, valores=None, narrativa: set[str] | None = None, omitir=()) -> list[Issue]:
    """Las cuatro comprobaciones. Sin `valores` del motor no se ejecuta la traza de cifras (queda constancia en el informe)."""
    from pptx import Presentation
    try:
        prs = Presentation(path)
    except Exception as e:                                               # noqa: BLE001
        return [Issue("PPTX_ZIP", "error", None, f"python-pptx no puede abrir el archivo ({type(e).__name__}).")]
    out: list[Issue] = []
    if valores is not None:
        out += comprobar_cifras(prs, valores, narrativa or set(), omitir)
    else:
        out.append(Issue("PPTX_CIFRA_NO_EVALUADA", "info", None, "No se comprobó la trazabilidad de las cifras: no se dispuso de los valores del motor."))
    out += comprobar_tablas(prs) + comprobar_moneda(prs) + comprobar_denominadores(prs, omitir)
    return out
