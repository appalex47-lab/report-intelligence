// Verifica que el motor de reglas corre dentro de Pyodide (el mismo runtime que usa el navegador) y da EXACTAMENTE
// los mismos resultados que CPython. Solo lee data/ejemplos; no envía datos a ningún lado.
//
// Preparación (una vez, fuera del repositorio):
//   mkdir /tmp/pyo && cd /tmp/pyo && npm init -y && npm i pyodide@0.27.7
//   pip download --no-deps openpyxl==3.1.5 et-xmlfile==2.0.0 -d wh && mkdir sp && for w in wh/*.whl; do unzip -q -o $w -d sp; done
//   pip download --no-deps --only-binary=:all: --platform manylinux2014_x86_64 --python-version 3.12 pyyaml==6.0.3 -d src && unzip -q -o src/*.whl "yaml/*" -d sp
//   (PyYAML y openpyxl se montan como paquetes puros; en el navegador los instala el worker desde la CDN de Pyodide y las ruedas vendorizadas)
// Uso:
//   python tools/evidencia_reglas.py   # genera la referencia de CPython
//   node --experimental-default-type=module tools/pyodide_node_check.mjs /tmp/pyo /tmp/pyo/out_pyodide.json
//   python tools/comparar_pyodide.py /tmp/pyo/out_pyodide.json
import { createRequire } from "module";
import fs from "fs";
import path from "path";

const work = process.argv[2] || "/tmp/pyo";
const outFile = process.argv[3] || path.join(work, "out_pyodide.json");
const repo = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");
const require = createRequire(path.join(work, "x.js"));
const { loadPyodide } = require("pyodide");

const py = await loadPyodide();
py.mountNodeFS("/host_sp", path.join(work, "sp"));
py.mountNodeFS("/ej", path.join(repo, "data", "ejemplos"));
py.unpackArchive(new Uint8Array(fs.readFileSync(path.join(work, "app.zip"))), "zip", { extractDir: "/app" });   // app.zip: backend/ y profiles/ (tools/build_site.add_tree)
const out = await py.runPythonAsync(`
import sys, json, time
sys.path.insert(0, "/host_sp"); sys.path.insert(0, "/app")
print("Python", sys.version.split()[0])
from backend.app.models import Period
from backend.app.validator import motor
from backend.app.validator.normalizar import construir_contexto
res = {}
ESC = [("GLP1","mensual",2026,9,"GLP1_crudo_ejemplo.xlsx"),("GLP1","trimestral",2026,3,"GLP1_crudo_ejemplo.xlsx"),
       ("AETOPS","mensual",2026,9,"AETOPS_crudo_ejemplo.xlsx"),("AETOPS","trimestral",2026,3,"AETOPS_crudo_ejemplo.xlsx")]
for u,t,y,i,f in ESC:
    t0 = time.time()
    r = motor.ejecutar(construir_contexto("/ej/" + f, Period(u, t, y, i)))
    res[f"{u}_{t}_{y}-{i:02d}"] = {"resumen": motor.resumen(r), "resultados": [x.to_dict() for x in r]}
    print(u, t, "ok", round(time.time() - t0, 1), "s", motor.resumen(r)["por_estado"])
json.dumps(res, ensure_ascii=False, sort_keys=True, default=str)
`);
fs.writeFileSync(outFile, out);
