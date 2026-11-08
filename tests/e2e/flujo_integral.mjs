// Recorrido del flujo integrado en un navegador real (Playwright) con el motor REAL en Pyodide:
// escenario -> generar -> vista previa -> QA -> cambio (resultados obsoletos) -> regenerar -> caso bloqueante -> corrección -> descarga.
// Uso: node flujo_integral.mjs <url_del_sitio> <libro.xlsx> <carpeta_salida> [mes]
// Imprime una línea JSON con el resultado. No modifica nada del repositorio. Lo invoca tests/e2e/test_flujo_integral.py.
import { createRequire } from "node:module";
import fs from "node:fs";
const require = createRequire(process.env.PLAYWRIGHT_REQUIRE_FROM || import.meta.url);
const { chromium } = require("playwright");
const [, , site, xlsx, outdir, month = "9"] = process.argv;

const browser = await chromium.launch();
const out = { ok: false, consola: [], pasos: {} };
try {
  const ctx = await browser.newContext({ acceptDownloads: true, viewport: { width: 1280, height: 900 } });
  const p = await ctx.newPage();
  p.on("console", (m) => { if (m.type() === "error") out.consola.push(`${m.type()}: ${m.text().slice(0, 200)}`); });
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
  await p.click("#n5"); await p.waitForSelector("#go", { timeout: 60000 });

  // 1 · escenario y etapas antes de generar
  await p.waitForSelector("#escCard", { timeout: 60000 });
  out.pasos.escenario = await p.evaluate(() => ({ seleccionado: document.querySelector("#escSel").value, opciones: [...document.querySelectorAll("#escSel option")].map(o => o.value),
    etapas: [...document.querySelectorAll(".flow .fl")].map(x => x.textContent.trim()), adaptativo: document.querySelector("#adaptChk").checked }));

  // 2 · generar: vista previa, calidad y exportación
  // Espera a que el resultado CAMBIE y la generación termine (un #pvBox de la generación anterior no cuenta).
  const generar = async () => {
    await p.evaluate(() => { window.__antes = S.result; });
    await p.click("#go");
    await p.waitForFunction(() => S.result !== window.__antes && !S.busy && !!document.querySelector("#pvBox"), null, { timeout: 420000 });
  };
  const estado = () => p.evaluate(() => ({
    banner: (document.querySelector(".banner .sub")?.closest(".banner")?.innerText || "").replace(/\n/g, " | "),
    obsoleto: [...document.querySelectorAll(".banner")].some(b => /Resultados desactualizados/.test(b.innerText)),
    etapas: [...document.querySelectorAll(".flow .fl")].map(x => x.textContent.trim().replace(/\s+/g, " ")),
    dlHabilitado: [...document.querySelectorAll('button[data-dl$=".pptx"]')].every(b => !b.disabled) && !!document.querySelector('button[data-dl$=".pptx"]'),
    diapositivas: document.querySelectorAll(".pvit").length, formasDibujadas: document.querySelectorAll("#pvs .pvf").length,
    hallazgos: [...document.querySelectorAll(".find code")].map(c => c.textContent), errores: document.querySelectorAll(".find .sev.block").length,
    contextoEnVistaPrevia: JSON.stringify(S.pv || {}).includes("Cambio de contexto después de generar"),
  }));
  await generar();
  out.pasos.generado = await estado();
  await p.screenshot({ path: `${outdir}/vista_previa_1.png`, fullPage: false });

  // navegación de la vista previa
  const actual = () => p.evaluate(() => document.querySelector(".pvit.now")?.dataset.k);
  const k0 = await actual();
  await p.click("#pvNext"); const k1 = await actual();
  await p.click("#pvPrev"); const k2 = await actual();
  await p.locator(".pvit").nth(3).click(); const k3 = await actual();
  out.pasos.navegacion = { k0, k1, k2, k3, texto_diapositiva: await p.evaluate(() => document.querySelector("#pvs").innerText.slice(0, 80)), tablaDibujada: await p.evaluate(() => !!document.querySelector("#pvs .pvtab td")) };
  await p.screenshot({ path: `${outdir}/vista_previa_2.png`, fullPage: false });

  // 3 · un cambio después de generar invalida vista previa y QA
  await p.evaluate(() => document.querySelector("#escCard details").open = true);
  await p.fill("#escCtx", "Cambio de contexto después de generar");
  await p.click("#escSave"); await p.waitForFunction(() => /Resultados desactualizados/.test(document.body.innerText), null, { timeout: 60000 });
  out.pasos.obsoleto = { ...(await estado()), previewVisible: !!(await p.$("#pvBox")) };
  // 4 · regenerar: vuelve a ser vigente, ahora con el contexto del escenario en el reporte
  await generar();
  out.pasos.regenerado = await estado();

  // 5 · caso bloqueante: escenario propio que exige una diapositiva que el reporte no tiene
  const bloq = await p.evaluate(async () => {
    const e = S.plan.escenario;
    await api("/escenarios-reporte/exige-engagement", J("PUT", { nombre: "Prueba: exige engagement", perfil: "*", profundidad: "ejecutivo", tipo_conclusion: "acciones_priorizadas",
      orden_narrativo: [...e.orden_narrativo, "engagement_digital"], tipos_obligatorios: [...e.tipos_obligatorios, "engagement_digital"], indicadores_relevantes: e.indicadores_relevantes }));
    S.escCat = await api("/escenarios-reporte");
    S.plan = await api(`/runs/${S.run.id}/plan`, J("PUT", { escenario_id: "exige-engagement" }));
    render(); return S.plan.escenario_id;
  });
  await p.evaluate(() => { window.__antes = S.result; });
  await p.click("#go"); await p.waitForFunction(() => S.result !== window.__antes && !S.busy && /QA rechazado/.test(document.body.innerText), null, { timeout: 420000 });
  out.pasos.bloqueado = { escenario: bloq, ...(await estado()), descargaIntentada: await p.evaluate(async () => { try { await api(`/runs/${S.run.id}/files/${S.result.pptx}`); return "permitida" } catch (e) { return e.message } }) };
  await p.screenshot({ path: `${outdir}/calidad_bloqueada.png`, fullPage: true });
  // 6 · se corrige (otro escenario) y se vuelve a ejecutar el QA
  await p.evaluate(async () => { S.plan = await api(`/runs/${S.run.id}/plan`, J("PUT", { escenario_id: "aetops-mensual" })); render(); });
  await generar();
  out.pasos.corregido = await estado();

  // 7 · descarga real del PPTX vigente
  const btn = p.locator('button[data-dl$=".pptx"]');
  const espera = p.waitForEvent("download", { timeout: 60000 });
  await btn.click();
  const d = await espera;
  out.nombre = d.suggestedFilename(); out.ruta = `${outdir}/${out.nombre}`; await d.saveAs(out.ruta);
  const buf = fs.readFileSync(out.ruta);
  out.bytes = buf.length; out.primeros_bytes = buf.subarray(0, 4).toString("hex");
  out.ok = true;
} catch (e) {
  out.error = String(e).slice(0, 500);
} finally {
  await browser.close();
}
console.log("RESULTADO " + JSON.stringify(out));
process.exitCode = out.ok ? 0 : 1;
