// Persistencia de escenarios propios con el motor REAL (Pyodide + SQLite) y el IndexedDB REAL de Chromium.
// PUT -> recargar -> aparece; DELETE -> recargar -> ya no aparece. Uso: node persistencia_escenarios.mjs <url_del_sitio>
// Imprime «RESULTADO {json}». Lo invoca tests/e2e/test_persistencia_escenarios.py.
import { createRequire } from "node:module";
const require = createRequire(process.env.PLAYWRIGHT_REQUIRE_FROM || import.meta.url);
const pw = require("playwright"); const chromium = pw[process.env.REPORT_BROWSER || "chromium"];     // REPORT_BROWSER: chromium | firefox | webkit
const [, , site] = process.argv;

const browser = await chromium.launch();
const out = { ok: false, consola: [], pasos: {} };
try {
  const ctx = await browser.newContext();
  const p = await ctx.newPage();
  p.on("pageerror", (e) => out.consola.push("pageerror: " + String(e).slice(0, 200)));
  const abrir = async (recargar) => { if (recargar) await p.reload(); else await p.goto(site); await p.waitForSelector("#boot", { state: "hidden", timeout: 300000 }); };
  const propios = () => p.evaluate(async () => (await api("/escenarios-reporte")).propios.map((e) => e.id));
  await abrir(false);
  out.pasos.inicial = await propios();
  await p.evaluate(async () => { await api("/escenarios-reporte/prueba-persistencia", { method: "PUT", headers: { "content-type": "application/json" }, body: JSON.stringify({ nombre: "Prueba de persistencia", objetivo: "Objetivo propio" }) }); });
  out.pasos.tras_put = await propios();
  await abrir(true);
  out.pasos.tras_recargar = await propios();
  out.pasos.contenido = await p.evaluate(async () => (await api("/escenarios-reporte")).propios.find((e) => e.id === "prueba-persistencia"));
  await p.evaluate(async () => { await api("/escenarios-reporte/prueba-persistencia", { method: "DELETE" }); });
  await abrir(true);
  out.pasos.tras_delete_y_recargar = await propios();
  out.ok = true;
} catch (e) {
  out.error = String(e).slice(0, 400);
} finally {
  await browser.close();
}
console.log("RESULTADO " + JSON.stringify(out));
