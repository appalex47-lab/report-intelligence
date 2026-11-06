// Fase 4 · panel «Escenarios E1/E2 e IND-01» en un navegador real (Playwright) con el motor REAL en Pyodide.
// Carga un libro, avanza hasta «Validar» y devuelve el contenido visible del panel y los errores de consola.
// Uso: node escenarios_panel.mjs <url_del_sitio> <libro.xlsx> <carpeta_salida> <unidad: glp1|aetops> [mes]
// Imprime una línea JSON. No modifica el repositorio. Lo invoca tests/e2e/test_escenarios_panel.py.
import { createRequire } from "node:module";
const require = createRequire(process.env.PLAYWRIGHT_REQUIRE_FROM || import.meta.url);
const { chromium } = require("playwright");
const [, , site, xlsx, outdir, unidad = "glp1", month = "9"] = process.argv;

const browser = await chromium.launch();
const out = { ok: false, consola: [], red: [] };
try {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 1800 } });
  const p = await ctx.newPage();
  p.on("console", (m) => { if (m.type() === "error" || m.type() === "warning") out.consola.push(`${m.type()}: ${m.text().slice(0, 160)}`); });
  p.on("pageerror", (e) => out.consola.push("pageerror: " + String(e).slice(0, 200)));
  p.on("requestfailed", (r) => out.red.push("FALLÓ " + r.url()));
  p.on("response", (r) => { if (r.status() >= 400) out.red.push(`${r.status()} ${r.url()}`); });

  await p.goto(site);
  await p.waitForSelector("#boot", { state: "hidden", timeout: 300000 });
  await p.selectOption("#u", unidad); await p.selectOption("#p", "mensual");
  await p.fill("#y", "2026"); await p.selectOption("#i", month);
  await p.setInputFiles("#file", xlsx);
  await p.waitForFunction(() => !document.querySelector("#next").disabled, null, { timeout: 120000 });
  await p.click("#next");
  await p.waitForSelector("#escPanel", { timeout: 180000 });
  out.panel_texto = (await p.innerText("#escPanel")).replace(/\s+/g, " ");
  out.escenarios = await p.$$eval("[data-esc]", (n) => n.map((e) => e.getAttribute("data-esc")));
  out.fuentes = await p.$$eval("[data-fuente]", (n) => n.map((e) => e.getAttribute("data-fuente")));
  out.tiene_ind01 = (await p.$$("[data-ind='IND-01']")).length;
  out.tiene_comparacion = (await p.$$("[data-cmp='E1-E2']")).length;
  out.paso_validar_visible = await p.isVisible("#escPanel");
  // la navegación del flujo normal sigue funcionando: el panel no rompe el paso «Validar» ni sus botones
  out.hay_boton_continuar = (await p.$$("#tg, #reload")).length > 0;
  await p.screenshot({ path: `${outdir}/panel_${unidad}.png`, fullPage: true });
  out.ok = true;
} catch (e) {
  out.error = String(e).slice(0, 400);
} finally {
  await browser.close();
}
console.log("RESULTADO " + JSON.stringify(out));
