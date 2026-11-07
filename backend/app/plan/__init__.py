"""Bloque integral: escenarios y SlideSpec, diseño adaptativo, QA integral y previsualización.

Cuatro piezas que comparten el mismo modelo (el PPTX generado y su SlideSpec) y un único flujo
(`flujo.analizar`): escenario → SlideSpec → diseño adaptativo → QA integral → vista previa → exportación.
No sustituye a los generadores por plantilla (`deck/`): los reutiliza y trabaja sobre su resultado.
"""
