// Calcula el `hash_resultado` de los 4 escenarios de la línea base DENTRO de Pyodide (el mismo runtime que usa el navegador) para compararlo con
// CPython (tests/regression/hash_resultado.json). Solo lee data/ejemplos y el app.zip indicado; no envía datos a ningún lado.
//
// Preparación (una vez, fuera del repositorio; ver también tools/pyodide_node_check.mjs): una carpeta de trabajo con
//   node_modules/pyodide (npm i pyodide@0.27.7) y sp/ con openpyxl, et_xmlfile y yaml (paquetes Python puros).
// Uso: node --experimental-default-type=module hash_pyodide.mjs <carpeta_de_trabajo> <app.zip> <salida.json>
// Lo invoca tests/e2e/test_hash_pyodide.py.
import { createRequire } from "module";
import fs from "fs";
import path from "path";

const [, , work, appZip, outFile] = process.argv;
const repo = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..", "..");
const require = createRequire(path.join(work, "x.js"));
const { loadPyodide } = require("pyodide");

const py = await loadPyodide();
py.mountNodeFS("/host_sp", path.join(work, "sp"));
py.mountNodeFS("/ej", path.join(repo, "data", "ejemplos"));
py.unpackArchive(new Uint8Array(fs.readFileSync(appZip)), "zip", { extractDir: "/app" });
const out = await py.runPythonAsync(`
import sys, json, hashlib
sys.path.insert(0, "/host_sp"); sys.path.insert(0, "/app")
from backend.app.models import Period
from backend.app.pipeline import run_aetops_raw, run_glp1_raw
from backend.app import provenance as pv
ESC = {"aetops_mensual_2026-09": ("AETOPS","mensual",2026,9,"AETOPS_crudo_ejemplo.xlsx"),
       "aetops_trimestral_2026-Q3": ("AETOPS","trimestral",2026,3,"AETOPS_crudo_ejemplo.xlsx"),
       "glp1_mensual_2026-09": ("GLP1","mensual",2026,9,"GLP1_crudo_ejemplo.xlsx"),
       "glp1_trimestral_2026-Q3": ("GLP1","trimestral",2026,3,"GLP1_crudo_ejemplo.xlsx")}
res = {"python": sys.version.split()[0], "plataforma": sys.platform, "escenarios": {}}
for n, (u, t, y, i, f) in ESC.items():
    path = "/ej/" + f
    per = Period(u, t, y, i)
    r = (run_aetops_raw if u == "AETOPS" else run_glp1_raw)(path, per)
    sha = hashlib.sha256(open(path, "rb").read()).hexdigest()
    c = pv.canonico(per, [{"nombre": path, "sha256": sha}], r)
    res["escenarios"][n] = {"hash": pv.hash_resultado(c)["valor"], "bloques": pv.huellas_por_bloque(c), "bytes": len(pv.serializar(c))}
json.dumps(res, sort_keys=True)
`);
fs.writeFileSync(outFile, out);
console.log("RESULTADO " + outFile);
