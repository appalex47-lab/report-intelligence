"""Fase 3A-5 · estructura de seguridad de `.github/workflows/release.yml`: separación de jobs, permisos mínimos efectivos, condiciones de ejecución,
orden de las comprobaciones y ausencia de operaciones peligrosas. Se ejecuta en CI.

Son comprobaciones ESTRUCTURALES sobre el archivo (YAML y guiones de shell); no ejecutan el workflow en GitHub. Esa ejecución real (V-02) requiere publicar
una release y no se ha hecho."""
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WF = ROOT / ".github" / "workflows" / "release.yml"
PINS = {"actions/checkout": "v4", "actions/setup-python": "v5", "actions/upload-artifact": "v4", "actions/download-artifact": "v4"}
SUBCOMANDOS = {"preparar", "verificar-ci", "etiqueta-libre", "verificar-carpeta", "verificar-release"}
PROHIBIDOS = ("--clobber", "release delete", "tag -f", "tag --force", "push --force", "push -f", "--prerelease", "git push", "secrets.", "pull_request_target",
              "continue-on-error", "set +e", "|| true", "2>/dev/null", "eval ", "curl ", "wget ", "--no-verify", "--force")


def _pasos(job):
    return job["steps"]


def _runs(job):
    return [s.get("run", "") for s in _pasos(job)]


def _indice(job, fragmento):
    return [i for i, s in enumerate(_pasos(job)) if fragmento in s.get("run", "") or fragmento in s.get("uses", "")]


def problemas_workflow(texto: str) -> list[str]:
    """Incumplimientos de las garantías del workflow (lista vacía = correcto)."""
    p = []
    d = yaml.safe_load(texto)
    on = d.get("on", d.get(True))
    if not isinstance(on, dict) or set(on) != {"workflow_dispatch"}:
        p.append("debe dispararse solo con workflow_dispatch")
    entrada = ((on or {}).get("workflow_dispatch") or {}).get("inputs", {}).get("publicar") if isinstance(on, dict) else None
    if not entrada or entrada.get("type") != "boolean" or entrada.get("default") is not False:
        p.append("la entrada «publicar» debe ser booleana y valer false por omisión (ensayo)")
    if d.get("permissions") != {}:
        p.append("los permisos globales deben ser vacíos (cada job pide los suyos)")
    if (d.get("concurrency") or {}).get("cancel-in-progress") is not False:
        p.append("la concurrencia no debe cancelar una publicación en curso")
    jobs = d.get("jobs") or {}
    if set(jobs) != {"construir", "publicar"}:
        return p + ["debe haber exactamente dos jobs: construir y publicar"]
    a, b = jobs["construir"], jobs["publicar"]
    # --- Job A: construcción y validación, sin escritura
    if a.get("permissions") != {"contents": "read", "actions": "read"}:
        p.append("construir debe tener solo contents: read y actions: read")
    if a.get("if") != "github.ref == 'refs/heads/main'":
        p.append("construir debe limitarse a refs/heads/main")
    for r in _runs(a):
        if re.search(r"gh release|gh api (-X|--method) (POST|PATCH|PUT|DELETE)|git (push|tag)", r):
            p.append("construir no debe escribir en GitHub")
    ia = [_indice(a, x) for x in ("tools/build_site.py", "release_app.py preparar", "release_app.py verificar-ci", "release_app.py etiqueta-libre", "actions/upload-artifact")]
    if any(len(x) != 1 for x in ia) or [x[0] for x in ia] != sorted(x[0] for x in ia):
        p.append("construir debe ser: construir → preparar → verificar CI → etiqueta libre → subir artefacto")
    if set(a.get("outputs") or {}) != {"etiqueta", "version", "sha256", "commit"}:
        p.append("construir debe exponer etiqueta, version, sha256 y commit")
    # --- Job B: publicación
    if b.get("needs") != "construir":
        p.append("publicar debe depender de construir")
    if b.get("if") != "${{ inputs.publicar && github.ref == 'refs/heads/main' }}":      # exacta: sin always()/failure()/cancelled() que anulen `needs`
        p.append("publicar debe exigir exactamente inputs.publicar y refs/heads/main")
    if b.get("permissions") != {"contents": "write", "actions": "read"}:
        p.append("publicar debe pedir solo contents: write y actions: read")
    crear = [i for i, r in enumerate(_runs(b)) if "gh release create" in r]
    if len(crear) != 1 or "--draft" not in _runs(b)[crear[0]] or '--target "$SHA"' not in _runs(b)[crear[0]]:
        p.append("publicar crea la release una sola vez, como borrador y con --target \"$SHA\"")
    if sum("gh release create" in r for r in _runs(a)) or sum("gh release create" in r for r in _runs(b)) != 1:
        p.append("gh release create solo puede existir una vez y en publicar")
    ib = [_indice(b, x) for x in ("actions/download-artifact", "release_app.py verificar-carpeta", "release_app.py verificar-ci", "release_app.py etiqueta-libre",
                                 "gh release create", "verificar-release --modo borrador", "draft=false", "verificar-release --modo publicada")]
    if any(len(x) != 1 for x in ib) or [x[0] for x in ib] != sorted(x[0] for x in ib):
        p.append("publicar debe ser: descargar → verificar carpeta → CI → etiqueta libre → borrador → verificar borrador → publicar → verificar publicada")
    # --- ambos
    for nombre, job in (("construir", a), ("publicar", b)):
        for s in _pasos(job):
            u = s.get("uses")
            if u:
                n, _, v = u.partition("@")
                if PINS.get(n) != v:
                    p.append(f"{nombre}: acción sin la versión fijada esperada: {u}")
                if n == "actions/checkout" and (s.get("with") or {}).get("persist-credentials") is not False:
                    p.append(f"{nombre}: checkout debe usar persist-credentials: false")
        env = job.get("env") or {}
        if env.get("GH_TOKEN") != "${{ github.token }}":
            p.append(f"{nombre}: el único token debe ser github.token")
        for r in _runs(job):
            if "${{" in r:
                p.append(f"{nombre}: una expresión ${{{{ }}}} dentro de un script de shell (riesgo de inyección): úsese env")
    for pr in PROHIBIDOS:
        if pr in texto:
            p.append(f"no debe contener «{pr}»")
    return p


# ----------------------------------------------------------------------------------------------------------------- el workflow real
def test_el_workflow_cumple_todas_las_garantias():
    assert problemas_workflow(WF.read_text(encoding="utf-8")) == []


def test_dos_jobs_con_permisos_efectivamente_separados():
    d = yaml.safe_load(WF.read_text(encoding="utf-8"))
    assert d["permissions"] == {}                                                         # nada por omisión
    assert d["jobs"]["construir"]["permissions"] == {"contents": "read", "actions": "read"}   # sin escritura
    assert d["jobs"]["publicar"]["permissions"] == {"contents": "write", "actions": "read"}
    escritura = [n for n, j in d["jobs"].items() if "write" in (j.get("permissions") or {}).values()]
    assert escritura == ["publicar"]                                                      # el único job con escritura


def test_publicar_no_se_ejecuta_sin_marcar_publicar_ni_si_construir_falla():
    d = yaml.safe_load(WF.read_text(encoding="utf-8"))
    pub = d["jobs"]["publicar"]
    assert pub["needs"] == "construir"                                                    # sin `if: always()`: solo corre si construir tuvo éxito
    assert "always()" not in pub["if"] and "failure()" not in pub["if"] and "cancelled()" not in pub["if"]
    assert pub["if"] == "${{ inputs.publicar && github.ref == 'refs/heads/main' }}"
    assert d[True if True in d else "on"]["workflow_dispatch"]["inputs"]["publicar"]["default"] is False


def test_el_trabajo_de_construccion_no_puede_publicar_ni_reescribir():
    d = yaml.safe_load(WF.read_text(encoding="utf-8"))
    for r in _runs(d["jobs"]["construir"]):
        assert "gh release" not in r and "PATCH" not in r and "git tag" not in r and "git push" not in r


def test_los_scripts_de_shell_no_interpolan_expresiones_de_actions():
    """Las salidas y entradas llegan por `env`, nunca dentro del texto del script (evita la inyección de comandos)."""
    d = yaml.safe_load(WF.read_text(encoding="utf-8"))
    for job in d["jobs"].values():
        for r in _runs(job):
            assert "${{" not in r


def test_la_sintaxis_de_todos_los_scripts_de_shell_es_valida():
    d = yaml.safe_load(WF.read_text(encoding="utf-8"))
    for nombre, job in d["jobs"].items():
        for r in _runs(job):
            res = subprocess.run(["bash", "-n"], input=r, capture_output=True, text=True)
            assert res.returncode == 0, (nombre, r[:60], res.stderr)


def test_cada_llamada_a_release_app_usa_un_subcomando_y_opciones_que_existen():
    texto = WF.read_text(encoding="utf-8")
    llamadas = re.findall(r"tools/release_app\.py ([a-z-]+)((?: (?:--[a-z0-9-]+|\"[^\"]*\"|\S+))*)", texto)
    assert len(llamadas) >= 8
    for sub, resto in llamadas:
        assert sub in SUBCOMANDOS, sub
        ayuda = subprocess.run([sys.executable, str(ROOT / "tools/release_app.py"), sub, "--help"], capture_output=True, text=True).stdout
        for opcion in re.findall(r"(--[a-z0-9-]+)", resto.split("|")[0].split("\\")[0]):
            assert opcion in ayuda, (sub, opcion)


def test_no_hay_comandos_que_oculten_errores():
    texto = WF.read_text(encoding="utf-8")
    for x in ("|| true", "continue-on-error", "set +e", "2>/dev/null", "if-no-files-found: ignore"):
        assert x not in texto


def test_el_workflow_usa_las_mismas_versiones_de_acciones_que_pages():
    pages = (ROOT / ".github/workflows/pages.yml").read_text(encoding="utf-8")
    for nombre, ver in (("actions/checkout", "v4"), ("actions/setup-python", "v5")):
        assert f"{nombre}@{ver}" in pages and f"{nombre}@{ver}" in WF.read_text(encoding="utf-8")


def test_el_workflow_no_se_dispara_con_push_ni_pr_ni_programacion():
    d = yaml.safe_load(WF.read_text(encoding="utf-8"))
    assert list(d.get("on") or d[True]) == ["workflow_dispatch"]


def test_release_yml_no_se_empaqueta_en_el_sitio():
    sys.path.insert(0, str(ROOT))
    import tools.build_site as bs
    assert ".github/workflows/release.yml" not in bs.PACKAGED          # añadirlo cambiaría el cálculo de «dirty» y tools/build_site.py es protegido


def test_el_tope_de_la_ejecucion_de_ci_es_el_mismo_que_el_de_la_consulta():
    """`per_page=100` en el workflow y el rechazo de respuestas llenas en el script deben ir juntos."""
    assert "per_page=100" in WF.read_text(encoding="utf-8")
    sys.path.insert(0, str(ROOT / "tools"))
    import release_app
    with pytest.raises(release_app.ErrorRelease, match="incompleta"):
        release_app.verificar_ci({"total_count": 100, "workflow_runs": [
            {"path": ".github/workflows/tests.yml", "head_sha": "a" * 40, "status": "completed", "conclusion": "success"}] * 100}, "a" * 40)


# ----------------------------------------------------------------------------------------------------------------- mutaciones deliberadas
MUTACIONES = [
    ("disparo con push", "workflow_dispatch:\n    inputs:", "push:\n      branches: [main]\n  workflow_dispatch:\n    inputs:"),
    ("publicar=true por omisión", "        default: false", "        default: true"),
    ("permisos globales de escritura", "permissions: {}", "permissions:\n  contents: write"),
    ("construir con escritura", "    permissions:\n      contents: read\n      actions: read\n    env:", "    permissions:\n      contents: write\n      actions: read\n    env:"),
    ("construir sin actions: read", "    permissions:\n      contents: read\n      actions: read\n    env:", "    permissions:\n      contents: read\n    env:"),
    ("publicar con más permisos", "      contents: write\n      actions: read", "      contents: write\n      actions: write\n      packages: write"),
    ("sin guarda de rama en construir", "    if: github.ref == 'refs/heads/main'", "    if: always()"),
    ("publicar sin needs", "    needs: construir\n", ""),
    ("publicar aunque construir falle", "    if: ${{ inputs.publicar && github.ref == 'refs/heads/main' }}", "    if: ${{ always() && inputs.publicar && github.ref == 'refs/heads/main' }}"),
    ("publicar sin marcar publicar", "    if: ${{ inputs.publicar && github.ref == 'refs/heads/main' }}", "    if: ${{ github.ref == 'refs/heads/main' }}"),
    ("release no borrador", " --draft --target", " --target"),
    ("release sin target exacto", '--target "$SHA"', "--target main"),
    ("sobrescribir release", "--notes-file _release/NOTAS.md", "--notes-file _release/NOTAS.md --clobber"),
    ("acción flotante", "actions/download-artifact@v4", "actions/download-artifact@main"),
    ("checkout con credenciales", "          persist-credentials: false\n      - uses: actions/setup-python@v5\n        with:\n          python-version: \"3.12\"\n      - uses: actions/download-artifact@v4",
     "      - uses: actions/setup-python@v5\n        with:\n          python-version: \"3.12\"\n      - uses: actions/download-artifact@v4"),
    ("quitar la comprobación de CI", 'python tools/release_app.py verificar-ci --runs "$RUNNER_TEMP/runs.json" --commit "$SHA"\n          gh api "repos/$REPO/git/matching-refs', 'gh api "repos/$REPO/git/matching-refs'),
    ("saltar la verificación de la publicada", '--modo publicada', '--modo borrador'),
    ("ignorar errores", 'test "$COMMIT" = "$SHA"', 'test "$COMMIT" = "$SHA" || true'),
    ("expresión dentro del script", 'gh api -X PATCH "repos/$REPO/releases/$id" -F draft=false', 'gh api -X PATCH "repos/$REPO/releases/${{ needs.construir.outputs.etiqueta }}" -F draft=false'),
    ("token ajeno", "GH_TOKEN: ${{ github.token }}", "GH_TOKEN: ${{ secrets.PAT }}"),
    ("no cancelar la publicación en curso", "cancel-in-progress: false", "cancel-in-progress: true"),
    ("tercer job", "\n  publicar:\n", "\n  extra:\n    runs-on: ubuntu-latest\n    steps: []\n\n  publicar:\n"),
    ("borrar la release", '--notes-file _release/NOTAS.md', '--notes-file _release/NOTAS.md; gh release delete x'),
]


@pytest.mark.parametrize("nombre,mutacion,reemplazo", MUTACIONES, ids=[m[0] for m in MUTACIONES])
def test_mutaciones_deliberadas_del_workflow_son_detectadas(nombre, mutacion, reemplazo):
    texto = WF.read_text(encoding="utf-8")
    assert texto.count(mutacion) >= 1, nombre
    assert problemas_workflow(texto.replace(mutacion, reemplazo, 1)), nombre
