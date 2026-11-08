// Revisión visual del paso «Generar» (Chromium + Pyodide real): escritorio y pantalla pequeña. Genera capturas y mide lo comprobable por máquina
// (desborde horizontal, etapas visibles, estados, vigencia). NO sustituye la mirada de una persona: lo que no se puede medir queda en el checklist
// de docs/bloque_integral/BLOQUE_INTEGRAL.md §15. Uso: node revision_visual.mjs <url> <libro.xlsx> <carpeta_salida> [mes]. Lo invoca test_revision_visual.py.
import { createRequire } from "node:module";
const require = createRequire(process.env.PLAYWRIGHT_REQUIRE_FROM || import.meta.url);
const { chromium } = require("playwright");
const [, , site, xlsx, outdir, month = "9"] = process.argv;

const browser = await chromium.launch();
const out = { ok: false, consola: [], vistas: {} };
try {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 1 });
  const p = await ctx.newPage();
  p.on("console", (m) => { if (m.type() === "error") out.consola.push(m.text().slice(0, 200)); });
  p.on("pageerror", (e) => out.consola.push("pageerror: " + String(e).slice(0, 200)));
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
  await p.click("#n5"); await p.waitForSelector("#go", { timeout: 60000 }); await p.waitForSelector("#escCard");

  const medir = (nombre) => p.evaluate((nombre) => {
    const de = document.documentElement, vis = (s) => { const e = document.querySelector(s); return !!e && e.getBoundingClientRect().width > 0; };
    const pptx = [...document.querySelectorAll('button[data-dl$=".pptx"]')];
    return { nombre, ancho: window.innerWidth, scrollW: de.scrollWidth, desborde_horizontal: de.scrollWidth > window.innerWidth + 1,
      etapas: [...document.querySelectorAll(".flow .fl")].map((x) => x.textContent.trim().replace(/\s+/g, " ")), escenario: vis("#escSel"), generar: vis("#go"),
      vista_previa: vis("#pvs"), lista_diapositivas: document.querySelectorAll(".pvit").length, hallazgos: document.querySelectorAll(".find").length,
      banner_obsoleto: /Resultados desactualizados/.test(document.body.innerText), descarga_habilitada: pptx.length > 0 && pptx.every((b) => !b.disabled),
      qa_banner: (() => { const e = document.querySelector("[data-qa-banner]"); return e ? { estado: e.dataset.qaBanner, clase_warn: e.classList.contains("warn"), clase_ok: e.classList.contains("ok"), clase_bad: e.classList.contains("bad"), titulo: e.querySelector("strong").textContent.trim() } : null; })(),
      valores_reales: (typeof S !== "undefined" && S.result) ? { qa_passed: S.result.qa_passed, vigente: S.result.vigente, downloadable: S.result.downloadable } : null };
  }, nombre);
  const captura = async (nombre) => { await p.screenshot({ path: `${outdir}/${nombre}.png`, fullPage: true }); };

  out.vistas.antes_escritorio = await medir("antes_escritorio"); await captura("antes_escritorio");
  await p.click("#go");
  await p.waitForFunction(() => !S.busy && !!document.querySelector("#pvBox"), null, { timeout: 420000 });
  out.vistas.generado_escritorio = await medir("generado_escritorio"); await captura("generado_escritorio");
  await p.setViewportSize({ width: 390, height: 844 }); await p.waitForTimeout(500);
  out.vistas.generado_movil = await medir("generado_movil"); await captura("generado_movil");
  await p.setViewportSize({ width: 1280, height: 900 });
  await p.evaluate(() => { document.querySelector("#escCard details").open = true; });
  await p.fill("#escCtx", "Cambio para comprobar la vigencia");
  await p.click("#escSave"); await p.waitForFunction(() => /Resultados desactualizados/.test(document.body.innerText), null, { timeout: 60000 });
  out.vistas.obsoleto_escritorio = await medir("obsoleto_escritorio"); await captura("obsoleto_escritorio");
  await p.setViewportSize({ width: 390, height: 844 }); await p.waitForTimeout(500);
  out.vistas.obsoleto_movil = await medir("obsoleto_movil"); await captura("obsoleto_movil");
  out.ok = true;
} catch (e) {
  out.error = String(e).slice(0, 400);
} finally {
  await browser.close();
}
console.log("RESULTADO " + JSON.stringify(out));
