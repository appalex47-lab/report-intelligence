// Fase 8 · estabilización en el navegador real (Chromium + Pyodide): rendimiento y persistencia.
//   · tiempos: arranque del motor, análisis, generación (todo con Pyodide real, que es el producto publicado);
//   · persistencia: tras generar un reporte, recargar la página (misma sesión de navegador / mismo IndexedDB) y comprobar que el historial conserva la corrida y que un escenario propio sigue ahí;
//   · integridad: el PPTX descargado en el navegador es un zip íntegro y su SHA-256 coincide con el del manifiesto.
// Uso: node estabilizacion_navegador.mjs <url> <libro.xlsx> <carpeta_salida> [mes]. Imprime «RESULTADO {json}». Lo invoca test_estabilizacion_navegador.py.
import { createRequire } from "node:module";
import fs from "node:fs";
import crypto from "node:crypto";
const require = createRequire(process.env.PLAYWRIGHT_REQUIRE_FROM || import.meta.url);
const pw = require("playwright"); const chromium = pw[process.env.REPORT_BROWSER || "chromium"];     // REPORT_BROWSER: chromium | firefox | webkit
const [, , site, xlsx, outdir, month = "9"] = process.argv;

const browser = await chromium.launch();
const out = { ok: false, consola: [], tiempos: {}, persistencia: {} };
const seg = (t0) => +((Date.now() - t0) / 1000).toFixed(2);
try {
  const ctx = await browser.newContext({ acceptDownloads: true, viewport: { width: 1280, height: 900 } });
  const p = await ctx.newPage();
  p.on("console", (m) => { if (m.type() === "error") out.consola.push(m.text().slice(0, 200)); });
  p.on("pageerror", (e) => out.consola.push("pageerror: " + String(e).slice(0, 200)));

  let t0 = Date.now();
  await p.goto(site);
  await p.waitForSelector("#boot", { state: "hidden", timeout: 300000 });
  out.tiempos.arranque_motor_s = seg(t0);

  await p.selectOption("#u", "aetops"); await p.selectOption("#p", "mensual");
  await p.fill("#y", "2026"); await p.selectOption("#i", month);
  await p.setInputFiles("#file", xlsx);
  t0 = Date.now();
  await p.waitForFunction(() => !document.querySelector("#next").disabled, null, { timeout: 120000 });
  out.tiempos.carga_del_libro_s = seg(t0);
  t0 = Date.now();
  await p.click("#next"); await p.waitForSelector("#tg", { timeout: 120000 });
  out.tiempos.analisis_s = seg(t0);
  await p.click("#tg"); await p.waitForSelector("#saveT");
  for (const t of await p.$$("[data-t]")) await t.fill((await t.getAttribute("data-t")) === "total" ? "12000000" : "3000000");
  await p.click("#saveT"); await p.waitForTimeout(2500);
  await p.click("#nx"); await p.waitForSelector("#n5", { timeout: 120000 });
  await p.click("#n5"); await p.waitForSelector("#go", { timeout: 60000 }); await p.waitForSelector("#escCard");

  // escenario propio (se comprueba su persistencia después de recargar)
  await p.evaluate(async () => { await api("/escenarios-reporte/estabilizacion", J("PUT", { nombre: "Escenario de estabilización", objetivo: "Prueba de persistencia" })); });

  t0 = Date.now();
  await p.click("#go");
  await p.waitForFunction(() => !S.busy && !!document.querySelector("#pvBox"), null, { timeout: 420000 });
  out.tiempos.generacion_s = seg(t0);

  // integridad del PPTX descargado en el navegador
  const [dl] = await Promise.all([p.waitForEvent("download", { timeout: 60000 }), p.click('button[data-dl$=".pptx"]')]);
  const ruta = `${outdir}/${dl.suggestedFilename()}`;
  await dl.saveAs(ruta);
  const bytes = fs.readFileSync(ruta);
  out.descarga = { nombre: dl.suggestedFilename(), bytes: bytes.length, zip: bytes[0] === 0x50 && bytes[1] === 0x4b, sha256: crypto.createHash("sha256").update(bytes).digest("hex") };
  out.manifiesto_sha256 = await p.evaluate(async () => { const m = await fetchFile(`/runs/${S.run.id}/files/manifest.json`); return JSON.parse(new TextDecoder().decode(new Uint8Array(m.buffer))).pptx_sha256; });
  out.run_id = await p.evaluate(() => S.run.id);

  // persistencia: recargar la página y consultar el historial y los escenarios
  await p.reload();
  await p.waitForSelector("#boot", { state: "hidden", timeout: 300000 });
  out.persistencia.historial = await p.evaluate(async () => { const r = await api("/history/runs"); return (Array.isArray(r) ? r : []).map((x) => ({ unidad: x.unidad, periodicidad: x.periodicidad, anio: x.anio, indice: x.indice, version: x.version, qa_ok: x.qa_ok, descargable: x.descargable })); });
  out.persistencia.escenarios = await p.evaluate(async () => (await api("/escenarios-reporte")).propios.map((e) => e.id));
  out.persistencia.tendencias = await p.evaluate(async () => { const r = await api("/history/trends?unit=aetops"); return Array.isArray(r) ? r.length : Object.keys(r || {}).length; }).catch(() => null);
  await p.click('.tab[data-tab="hist"]'); await p.waitForTimeout(1500);
  out.persistencia.historial_visible = await p.evaluate(() => /Reportes generados/.test(document.body.innerText));
  out.ok = true;
} catch (e) {
  out.error = String(e).slice(0, 400);
} finally {
  await browser.close();
}
console.log("RESULTADO " + JSON.stringify(out));
