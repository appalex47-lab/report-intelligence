"""D-7 · indicador «QA … · descarga …» del paso Generar (frontend/index.html). Comprobación ESTÁTICA que corre en CI: el recuadro se presenta como aviso (clase `warn`) y con
el texto «QA del reporte anterior (desactualizado) · descarga bloqueada» solo cuando el resultado es obsoleto; en los demás casos el texto y la clase siguen siendo los de siempre.
La comprobación en navegador está en tests/e2e/test_revision_visual.py (solo local). No sustituye a esa prueba: no ejecuta el JavaScript."""
import re
from pathlib import Path

HTML = (Path(__file__).resolve().parents[2] / "frontend" / "index.html").read_text(encoding="utf-8")
LINEA = next(ln for ln in HTML.splitlines() if 'data-qa-banner="' in ln)


def test_el_recuadro_usa_warn_y_el_texto_nuevo_solo_si_el_resultado_esta_desactualizado():
    assert 'class="banner ${obsoleto?"warn":r.qa_passed?"ok":"bad"}"' in LINEA
    assert '${obsoleto?"QA del reporte anterior (desactualizado) · descarga bloqueada":' in LINEA


def test_sin_obsolescencia_el_texto_anterior_se_conserva():
    assert 'QA ${r.qa_passed?"aprobado":"rechazado"} · descarga ${r.downloadable?"habilitada":"bloqueada"}' in LINEA


def test_no_se_alteran_los_valores_reales_ni_la_logica_de_bloqueo_en_la_interfaz():
    assert 'const obsoleto = r.vigente === false;' in HTML
    assert re.search(r'const dl = \(name, label\) => name \? `<button class="btn \$\{r\.downloadable\?"primary":""\}"[^`]*\$\{r\.downloadable\?"":"disabled"\}', HTML)     # el botón sigue gobernado por `downloadable`
    assert 'S.result.vigente!==false' in HTML and '(!S.result.qa_passed || S.result.vigente===false)' in HTML                                             # y el paso por `qa_passed`/`vigente`
