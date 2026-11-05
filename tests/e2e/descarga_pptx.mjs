// Recorrido completo en un navegador real (Playwright) con el motor REAL en Pyodide:
// cargar libro -> validar -> metas -> narrativa -> generar -> pulsar «Descargar PPTX» y guardar el archivo.
// Uso: node descarga_pptx.mjs <url_del_sitio> <libro.xlsx> <carpeta_salida> [mes (valor del selector, 9 = septiembre)]
// Imprime una línea JSON con el resultado. No modifica nada del repositorio. Lo invoca tests/e2e/test_descarga_pptx.py.
import { createRequire } from "node:module";
import fs from "node:fs";
const require = createRequire(process.env.PLAYWRIGHT_REQUIRE_FROM || import.meta.url);
const { chromium } = require("playwright");
const [, , site, xlsx, outdir, month = "9"] = process.argv;

const browser = await chromium.launch();
const out = { ok: false, consola: [], red: [] };
try {
  const ctx = await browser.newContext({ acceptDownloads: true });
  const p = await ctx.newPage();
  p.on("console", (m) => { if (m.type() === "error" || m.type() === "warning") out.consola.push(`${m.type()}: ${m.text().slice(0, 160)}`); });
  p.on("pageerror", (e) => out.consola.push("pageerror: " + String(e).slice(0, 200)));
  p.on("requestfailed", (r) => out.red.push("FALLÓ " + r.url()));
  p.on("response", (r) => { if (r.status() >= 400) out.red.push(`${r.status()} ${r.url()}`); });

  await p.goto(site);
  await p.waitForSelector("#boot", { state: "hidden", timeout: 300000 });
  await p.selectOption("#u", "aetops"); await p.selectOption("#p", "mensual");
  await p.fill("#y", "2026"); await p.selectOption("#i", month);
  await p.setInputFiles("#file", xlsx);
  await p.waitForFunction(() => !document.querySelector("#next").disabled, null, { timeout: 120000 });
  await p.click("#next"); await p.waitForSelector("#tg", { timeout: 120000 }); await p.click("#tg");
  await p.waitForSelector("#saveT");
  for (const t of await p.$$("[data-t]")) await t.fill((await t.getAttribute("data-t")) === "total" ? "12000000" : "3000000");
  await p.click("#saveT"); await p.waitForTimeout(2500);
  await p.click("#nx"); await p.waitForSelector("#n5", { timeout: 120000 });
  await p.click("#n5"); await p.waitForSelector("#go", { timeout: 60000 });
  await p.click("#go"); await p.waitForSelector('[data-dl$=".pptx"]', { timeout: 420000 });
  out.banner = (await p.innerText(".banner")).replace(/\n/g, " | ");
  const btn = p.locator('button[data-dl$=".pptx"]');
  out.boton_habilitado = await btn.isEnabled();
  const espera = p.waitForEvent("download", { timeout: 60000 });
  await btn.click();
  const d = await espera;
  out.nombre = d.suggestedFilename();
  out.ruta = `${outdir}/${out.nombre}`;
  await d.saveAs(out.ruta);
  const buf = fs.readFileSync(out.ruta);
  out.bytes = buf.length; out.primeros_bytes = buf.subarray(0, 4).toString("hex");
  out.ok = true;
} catch (e) {
  out.error = String(e).slice(0, 400);
} finally {
  await browser.close();
}
console.log("RESULTADO " + JSON.stringify(out));
process.exit(out.ok ? 0 : 1);
