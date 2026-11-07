"""Reglas compartidas por SlideSpec, diseño adaptativo y QA integral (una sola fuente: nadie las repite)."""
from __future__ import annotations

EMU_PT = 1 / 12700
LETRA_MIN_PT = 9.0                  # mismo piso que la revisión estructural de la Fase 5 (`pptx_export`: min(9 pt, mínimo de la plantilla))
MARGEN_SEGURO_PT = 6.0              # una forma que crece no debe acercarse al borde de la diapositiva más que esto
HOLGURA_DESBORDE = 1.0              # ocupación estimada ≤ 100 % del cuadro = cabe
UMBRAL_ACTUAR = 1.08                # el diseño adaptativo solo interviene si la estimación pasa de 108 %: la plantilla ya cabe con su propio ajuste
CONTRASTE_MIN = 3.0                 # WCAG 3:1 (texto grande); el QA visual con render usa 2,5 sobre muestreo real
FACTOR_ANCHO_CARACTER = 0.50        # ancho medio de un carácter ≈ 0,50 × tamaño (fuentes sans en español); estimación, no medición
FACTOR_ANCHO_ESTRECHA = 0.45        # fuentes estrechas (p. ej. «Aptos Narrow», la de las plantillas): calibrado contra tablas que el render real da por correctas
FACTOR_INTERLINEADO = 1.20
SIN_DATO = ("no verificable", "información insuficiente", "sin datos", "no disponible", "n/d", "no aplica")
ESTIMACION = ("supuesto heredado", "ilustrativo", "escenario", "estimad")
PREFIJO_AGREGADA = "RI_"            # formas que añade el generador (descubrimiento, anexo)
