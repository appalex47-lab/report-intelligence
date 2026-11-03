"""Construye la matriz de pruebas de la Fase 2B a partir de un informe JUnit real (no declara aprobada ninguna prueba que no se ejecutó).

    python -m pytest tests/unit tests/regression tests/golden --junitxml=junit.xml
    python tools/matriz_pruebas_fase1.py junit.xml --salida docs/fase1/implementacion/F2B_MATRIZ_PRUEBAS.md

Una prueba de la especificación (T-xx) se asocia a las pruebas pytest cuyo nombre contiene `test_txx_` (o a los archivos
indicados). Estado: `aprobada` si todas las asociadas pasaron; `fallida` si alguna falló; `omitida (motivo)` si se saltaron
o si la funcionalidad que verifican no existe todavía (fase posterior): en ese caso NO se marca como aprobada.
"""
from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# id: (regla evaluada, datos de entrada, resultado esperado, patrones de nombre/clase, observaciones, motivo si no aplica aún)
M = {
 "T-01": ("R-REL-PAC-PED", "Contextos sintéticos: 1 pedido/1 paciente, paciente con varios pedidos, pedido sin paciente, pedido con 2 pacientes (m=1 y m=2), fechas contradictorias (dentro/fuera del periodo), duplicados, ids vacíos, ejemplo de §3.3",
          "C2=1, E=5, A=3, B=1, C=1, pacientes únicos=2, cobertura 60 %, razón 1,5; error en contradicciones; valid en los casos normales; nunca cuenta filas", ["test_t01_", "test_rel_pac_ped"], "Incluye F-04, F-05, F-06 y F-07", None),
 "T-02": ("R-CUADRE-DIM", "Contextos sintéticos con dimensión exclusiva, SKU compartido por pedido, paciente en varios canales/sucursales, pedido con varias categorías, 8 combinaciones declaradas, tolerancia, columna inexistente",
          "warning en no exclusivas con «no sumar subtotales»; not_verifiable si no hay propiedades declaradas; tabla de cuatro combinaciones; sin eliminar datos", ["test_t02_", "test_cuadre"], "Defecto D-2B-01 corregido (líneas sin paciente)", None),
 "T-03": ("R-CONC-COMPRAS", "Pedidos 100 frente a compras 70…130; trimestre con meses de tráfico faltantes; sin hoja de tráfico; GLP-1 y AETOPS; umbral configurable",
          "la brecha absoluta supera 20 % ⇒ warning neutral (no error); ≤ 20 % ⇒ valid; faltante ⇒ not_verifiable; AETOPS ⇒ not_applicable; fuentes separadas", ["test_t03_", "test_conc_compras"], "", None),
 "T-04": ("R-DENOM", "Razones con denominador válido, cero, negativo, vacío; numerador ausente/negativo; periodos, granularidades y fuentes distintos; regla sobre contexto",
          "Nunca un 0 % por denominador cero o faltante; warning con valor y limitación cuando difieren periodo/granularidad/fuente", ["test_t04_", "test_denom"], "", None),
 "T-05": ("R-COBERTURA-ATC", "Relación <, = y > 100 %; carritos 0 o faltantes; unidad no declarada; dos fuentes; periodos no coincidentes; AETOPS",
          "Estados calculable / con limitación / no calculable; > 100 % conservado con advertencia sin causa; sin complemento ni «abandono»", ["test_t05_"], "", None),
 "T-06": ("Modelo de hallazgos", "—", "Todo id histórico existe en validator/catalogo.py; compatibilidad de Finding", [], "Compatibilidad de Finding: las 17 pruebas de Fase 1 (tests/unit/test_hallazgo_compat.py) pasan, pero no sustituyen a T-06, que exige el catálogo por id.", "validator/catalogo.py (mapa de id histórico a tipo/gravedad/estado/efecto) no existe: es de una fase posterior"),
 "T-07": ("Procedencia", "—", "Manifiesto de 9 campos y hash reproducible", [], "", "provenance.py no existe (Fase 3 de implementación)"),
 "T-08": ("Reproducibilidad histórica", "—", "Estados exacta / parcial / no_reproducible", [], "", "provenance.py no existe (Fase 3)"),
 "T-09": ("Escenario E1", "—", "Fórmula M_neg×0,25 idéntica; conservador/optimista «No configurado»; etiqueta «Supuesto heredado, no validado» en panel/anexo", [], "La fórmula y la cifra no cambiaron (línea base idéntica; narrative/executive.py protegido); falta la etiqueta en panel/anexo.", "Etiquetas de escenarios, panel y anexo: Fase 4"),
 "T-10": ("IND-01 (R-COBERTURA-ATC)", "1 000 carritos y 250 pedidos; 1 200 pedidos; machote GLP-1 sept-2026; libros sin identificadores de carrito",
          "25 % exacto; 120 % conservado con advertencia; 12,48 % y 14,00 % independientes; sin denominaciones prohibidas ni complemento", ["test_t05_t10_", "test_t10_", "test_ind01", "test_machote_glp1"], "Parte del indicador en panel/anexo: Fase 4", None),
 "T-10b": ("Escenario E2", "—", "A×0,10×T idéntica; aclaración sobre carritos_abandonados solo en panel/anexo", [], "La fórmula y la lámina no cambiaron (línea base idéntica; glp1_exec.py protegido); falta la aclaración en panel/anexo.", "Aclaración en panel/anexo: Fase 4"),
 "T-11": ("QA estructural PPTX", "—", "Detección de defectos inyectados en el PPTX exportado", [], "", "qa/pptx_export.py no existe (Fase 5)"),
 "T-12": ("QA visual (condicional)", "—", "PNG por diapositiva e informe", [], "Condición de activación (soffice y pdftoppm en PATH) cumplida en este entorno, pero la prueba no existe.", "qa/visual.py no existe (Fase 5)"),
 "T-13": ("No regresión", "Línea base congelada (4 escenarios) y 74 archivos protegidos", "0 diferencias en motor, hallazgos, narrativa y huellas del deck; archivos protegidos idénticos", ["tests.regression"], "Los flags aún no gobiernan ningún comportamiento: la parte «flags activos/desactivados» es trivialmente idéntica.", None),
 "T-14": ("Privacidad e IA", "Código del motor; textos de resultados; reescrituras simuladas",
          "Sin red ni escritura; la IA no modifica reglas; reescrituras con cifras alteradas o causales se rechazan; toda salida con fuente", ["test_t14_"], "No se ejecutó ninguna llamada real a Cohere.", None),
 "T-15": ("Anonimización", "—", "Conteos y relaciones preservados", [], "", "tools/anonimizar_extracto.py no existe"),
 "T-16": ("build_site / versiones", "—", "app.zip con versión y SHA estampados", [], "Se comprobó aparte que build_site empaqueta los JSON de configuración (test_config_fase1).", "Estampado de versión: Fase 3"),
 "T-17": ("Incorporación de extractos", "—", "Mapeo sin cambios de código; modo informe", [], "", "mapeo_columnas.json aún no lo consume ningún código (Fase 3+)"),
 "T-18": ("Etiquetas de validación", "—", "«No validada con datos reales» en hallazgo, anexo y manifiesto", [], "La etiqueta existe en cada Resultado (estado_validacion); falta en anexo/manifiesto.", "Anexo y manifiesto: Fases 3 y 5"),
 "T-19": ("Rendimiento", "—", "Mediana con flags activos ≤ 1,15× la de flags desactivados", [], "Se midió el motor aparte (prueba de calidad): 200 000 líneas.", "Los flags no están cableados: no hay dos configuraciones que comparar"),
 "T-20": ("Fixtures sintéticas", "tools/make_fixtures_fase1.py", "Mismos bytes/hash en dos ejecuciones; sintetico: true", ["test_t20_", "test_fixtures_fase1", "test_dos_generaciones", "test_las_fixtures", "test_el_manifiesto", "test_todas_las_fixtures"], "", None),
 "T-21": ("Fuentes de pedidos", "Contextos con ambas fuentes y con una faltante", "Ninguna fuente sustituye ni se suma a la otra; cada cifra nombra su fuente", ["test_t21_"], "", None),
 "T-22": ("Aplicabilidad por unidad", "Encabezados reales de los machotes GLP-1 y AETOPS", "Columnas documentadas = reales; AETOPS no usa tráfico; sin referencias a columnas inexistentes", ["test_t22_"], "", None),
 "S-01": ("Suite unitaria existente", "tests/unit (sin editar)", "Todas pasan", ["tests.unit"], "Incluye las 181 originales y las pruebas nuevas de Fase 1, 2A y 2B", None),
 "S-02": ("Suite golden existente", "tests/golden (35)", "Todas pasan cuando se ejecuta", ["tests.golden"], "", None),
 "V-01": ("Validación con extractos reales", "—", "Informe revisado por el usuario", [], "", "No existen extractos reales (A-2 pendiente)"),
 "V-02": ("Workflow de release", "—", "Release app-vX.Y.Z con asset", [], "", "A-5 no autorizada; release.yml no existe"),
}


def leer(paths):
    casos = []
    for p in paths:
        root = ET.parse(p).getroot()
        for tc in root.iter("testcase"):
            estado = "aprobada"
            motivo = ""
            for ch in tc:
                if ch.tag in ("failure", "error"):
                    estado = "fallida"
                elif ch.tag == "skipped":
                    estado, motivo = "omitida", ch.get("message", "")
            casos.append((tc.get("classname", ""), tc.get("name", ""), estado, motivo, float(tc.get("time", 0))))
    return casos


def evaluar(i, casos):
    _, _, _, pats, _, motivo_na = M[i]
    sel = [c for c in casos if any(p in c[1] or p in c[0] for p in pats)] if pats else []
    if i == "S-01":
        sel = [c for c in casos if c[0].startswith("tests.unit")]
    if i == "T-13":
        sel = [c for c in casos if c[0].startswith("tests.regression")]
    if i == "S-02":
        sel = [c for c in casos if c[0].startswith("tests.golden")]
    if not sel:
        return "omitida", f"({motivo_na})" if motivo_na else "(sin pruebas asociadas)", 0, 0, 0, 0.0
    ok = sum(c[2] == "aprobada" for c in sel); mal = sum(c[2] == "fallida" for c in sel); sk = sum(c[2] == "omitida" for c in sel)
    t = sum(c[4] for c in sel)
    if mal:
        return "fallida", "", ok, mal, sk, t
    if ok and not sk:
        return "aprobada", "", ok, mal, sk, t
    if ok:
        return "aprobada (con omitidas)", f"{sk} omitida(s) por su condición", ok, mal, sk, t
    return "omitida", "; ".join(sorted({c[3] for c in sel if c[3]})[:2]) or "omitida", ok, mal, sk, t


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("junit", nargs="+")
    ap.add_argument("--salida", default=None)
    a = ap.parse_args(argv)
    casos = leer(a.junit)
    filas, resumen = [], {}
    for i, (regla, entrada, esperado, _p, obs, _m) in M.items():
        estado, motivo, ok, mal, sk, t = evaluar(i, casos)
        resumen[estado] = resumen.get(estado, 0) + 1
        obtenido = f"{ok + mal + sk} pruebas: {ok} aprobadas, {mal} fallidas, {sk} omitidas ({t:.1f} s)" if (ok + mal + sk) else "no ejecutada"
        filas.append(f"| {i} | {regla} | {entrada} | {esperado} | {obtenido} | **{estado}** {motivo} | junit: {', '.join(Path(p).name for p in a.junit)} | {obs} |")
    txt = ("# Matriz de pruebas ejecutadas — Fase 2B\n\nGenerada por `tools/matriz_pruebas_fase1.py` desde el informe JUnit de la ejecución real. "
           "Una prueba no ejecutada **no** figura como aprobada.\n\n"
           "| ID | Regla evaluada | Datos de entrada | Resultado esperado | Resultado obtenido | Estado | Evidencia | Observaciones |\n|---|---|---|---|---|---|---|---|\n"
           + "\n".join(filas) + f"\n\n**Resumen:** {resumen}\n")
    if a.salida:
        Path(a.salida).write_text(txt, encoding="utf-8")
    print(txt if not a.salida else f"escrita {a.salida}: {resumen}")
    return 1 if resumen.get("fallida") else 0


if __name__ == "__main__":
    sys.exit(main())
