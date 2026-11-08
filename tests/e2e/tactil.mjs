// Fase 6 · interacción TÁCTIL en un contexto de pantalla táctil de 390 × 844 (Playwright: hasTouch, y isMobile donde el motor lo admite).
// Recorre el flujo solo con toques (`tap`): cargar → validar → metas → narrativa → generar → navegar la vista previa → cambiar escenario → pestañas.
// Comprueba que cada toque produce el efecto esperado y que el objetivo táctil es alcanzable (visible y de al menos 24 px).
// Esto es emulación del motor del navegador; NO sustituye una prueba en un dispositivo físico.
// Uso: node tactil.mjs <url> <libro.xlsx> <carpeta_salida> [mes]. Imprime «RESULTADO {json}».
import { createRequire } from "node:module";
const require = createRequire(process.env.PLAYWRIGHT_REQUIRE_FROM || import.meta.url);
const pw = require("playwright"); const nombre = process.env.REPORT_BROWSER || "chromium"; const chromium = pw[nombre];
const [, , site, xlsx, outdir, month = "9"] = process.argv;

const browser = await chromium.launch();
const out = { ok: false, navegador: nombre, consola: [], pasos: {} };
try {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, hasTouch: true, ...(nombre === "firefox" ? {} : { isMobile: true }), deviceScaleFactor: 2 });
  const p = await ctx.newPage();
  p.on("console", (m) => { if (m.type() === "error") out.consola.push(m.text().slice(0, 200)); });
  p.on("pageerror", (e) => out.consola.push("pageerror: " + String(e).slice(0, 200)));
  const objetivo = async (sel) => p.evaluate((s) => { const e = document.querySelector(s); if (!e) return null; const r = e.getBoundingClientRect(); return { w: Math.round(r.width), h: Math.round(r.height), visible: r.width > 0 && r.height > 0 }; }, sel);
  // La aplicación muestra una capa de carga mientras trabaja el motor; un toque durante la carga no llega al control (es el comportamiento correcto). Se espera a que termine.
  const esperarCarga = () => p.waitForFunction(() => { const l = document.querySelector("#loader"); return !l || l.hidden; }, null, { timeout: 120000 });
  const toque = async (sel, etiqueta) => {
    out.ultimo_toque = etiqueta || sel;
    await esperarCarga();
    const loc = p.locator(sel).first();
    await loc.waitFor({ state: "visible", timeout: 60000 });
    (out.objetivos ||= {})[etiqueta || sel] = await objetivo(sel);
    await loc.scrollIntoViewIfNeeded({ timeout: 60000 });
    await loc.tap({ timeout: 60000 });
  };

  await p.goto(site);
  await p.waitForSelector("#boot", { state: "hidden", timeout: 300000 });
  out.pasos.es_tactil = await p.evaluate(() => ({ maxTouchPoints: navigator.maxTouchPoints, coarse: matchMedia("(pointer: coarse)").matches || navigator.maxTouchPoints > 0 }));
  await p.selectOption("#u", "aetops"); await p.selectOption("#p", "mensual");
  await p.fill("#y", "2026"); await p.selectOption("#i", month);
  await p.setInputFiles("#file", xlsx);
  await p.waitForFunction(() => !document.querySelector("#next").disabled, null, { timeout: 120000 });
  await toque("#next", "Continuar (cargar → validar)");
  await p.waitForSelector("#tg", { timeout: 120000 });
  out.pasos.paso_validar = await p.evaluate(() => S.step);
  await toque("#tg", "Capturar metas");
  await p.waitForSelector("#saveT");
  for (const t of await p.$$("[data-t]")) await t.fill((await t.getAttribute("data-t")) === "total" ? "12000000" : "3000000");
  await toque("#saveT", "Guardar metas"); await p.waitForTimeout(2500);
  await toque("#nx", "Continuar a la narrativa"); await p.waitForSelector("#n5", { timeout: 120000 });
  out.pasos.paso_narrativa = await p.evaluate(() => S.step);
  await toque("#n5", "Continuar a generar"); await p.waitForSelector("#go", { timeout: 60000 }); await p.waitForSelector("#escCard");
  out.pasos.paso_generar = await p.evaluate(() => S.step);

  // casilla del diseño adaptativo (objetivo táctil de 24 px) y escenario
  const antes = await p.evaluate(() => document.querySelector("#adaptChk").checked);
  await toque("#adaptChk", "Casilla de diseño adaptativo"); await p.waitForTimeout(800);
  out.pasos.casilla = { antes, despues: await p.evaluate(() => document.querySelector("#adaptChk").checked) };
  await toque("#adaptChk", "Casilla de diseño adaptativo (volver)"); await p.waitForTimeout(800);

  await toque("#go", "Generar reporte");
  await p.waitForFunction(() => !S.busy && !!document.querySelector("#pvBox"), null, { timeout: 420000 });
  out.pasos.generado = await p.evaluate(() => ({ descarga: [...document.querySelectorAll('button[data-dl$=".pptx"]')].every((b) => !b.disabled), diapositivas: document.querySelectorAll(".pvit").length }));

  // vista previa: siguiente, anterior y lista, solo con toques
  const idx = () => p.evaluate(() => +document.querySelector(".pvit.now").dataset.k);
  const k0 = await idx();
  await toque("#pvNext", "Vista previa: siguiente"); const k1 = await idx();
  await toque("#pvPrev", "Vista previa: anterior"); const k2 = await idx();
  out.ultimo_toque = "Vista previa: diapositiva 5 de la lista"; await esperarCarga(); await p.locator(".pvit").nth(4).scrollIntoViewIfNeeded(); await p.locator(".pvit").nth(4).tap({ timeout: 60000 }); const k3 = await idx();
  out.pasos.vista_previa = { k0, k1, k2, k3 };
  out.pasos.vista_previa_desplazable = await p.evaluate(() => { const w = document.querySelector(".pvwrap"); return { ancho_visible: w.clientWidth, ancho_diapositiva: document.querySelector("#pvs").getBoundingClientRect().width, desplaza: w.scrollWidth > w.clientWidth }; });
  await p.screenshot({ path: `${outdir}/tactil_vista_previa.png`, fullPage: false });

  // detalles plegables y pestañas
  await toque("#escCard details summary", "Ajustar este reporte (resumen plegable)");
  out.pasos.detalles_abierto = await p.evaluate(() => document.querySelector("#escCard details").open);
  await toque('.tab[data-tab="hist"]', "Pestaña Historial"); await p.waitForTimeout(1200);
  out.pasos.pestana_historial = await p.evaluate(() => ({ seleccionada: document.querySelector('.tab[data-tab="hist"]').getAttribute("aria-selected"), visible: !document.querySelector("#p-hist").hidden }));
  await toque('.tab[data-tab="rep"]', "Pestaña Reporte"); await p.waitForTimeout(500);
  out.pasos.vuelta_a_reporte = await p.evaluate(() => !document.querySelector("#p-rep").hidden);
  out.pasos.sin_desborde = await p.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);
  out.ok = true;
} catch (e) {
  out.error = String(e).slice(0, 400);
} finally {
  await browser.close();
}
console.log("RESULTADO " + JSON.stringify(out));
