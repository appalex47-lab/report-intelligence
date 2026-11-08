// Fase 6 · diseño adaptativo de la interfaz: mide cada pantalla de la aplicación (Chromium + Pyodide real) en cinco anchos:
// escritorio 1280, portátil 1024, tablet 768, móvil 390 y móvil pequeño 320. NO juzga la estética: mide lo comprobable por máquina
// (desborde horizontal, elementos fuera del área visible, tablas que no caben, controles táctiles pequeños, texto diminuto, solapamientos).
// Uso: node responsivo.mjs <url_del_sitio> <libro.xlsx> <carpeta_salida> [mes]. Imprime «RESULTADO {json}». Lo invoca test_responsivo.py.
import { createRequire } from "node:module";
const require = createRequire(process.env.PLAYWRIGHT_REQUIRE_FROM || import.meta.url);
const pw = require("playwright"); const chromium = pw[process.env.REPORT_BROWSER || "chromium"];     // REPORT_BROWSER: chromium | firefox | webkit
const [, , site, xlsx, outdir, month = "9"] = process.argv;

const ANCHOS = { escritorio: 1280, portatil: 1024, tablet: 768, movil: 390, movil_pequeno: 320 };
const browser = await chromium.launch();
const out = { ok: false, consola: [], pantallas: {} };

// Se ejecuta DENTRO de la página: todo lo medible de la pantalla visible con el ancho actual.
const medir = () => {
  const W = window.innerWidth, de = document.documentElement;
  const enDetallesCerrado = (e) => { for (let d = e.closest("details"); d; d = d.parentElement && d.parentElement.closest("details")) { if (!d.open && !(e.closest("summary") && e.closest("summary").parentElement === d)) return true; } return false; };   // Firefox da caja a lo que hay dentro de un <details> cerrado; no es contenido visible
  const vis = (e) => { const r = e.getBoundingClientRect(); const cs = getComputedStyle(e); return r.width > 0 && r.height > 0 && cs.visibility !== "hidden" && cs.display !== "none" && !enDetallesCerrado(e); };
  const sel = (e) => (e.id ? "#" + e.id : e.tagName.toLowerCase() + (e.className && typeof e.className === "string" ? "." + e.className.trim().split(/\s+/).slice(0, 2).join(".") : ""));
  const dentroDeContenedorConDesplazamiento = (e) => { for (let p = e.parentElement; p && p !== document.body; p = p.parentElement) { const o = getComputedStyle(p).overflowX; if ((o === "auto" || o === "scroll") && p.scrollWidth > p.clientWidth - 1) return true; if (o === "auto" || o === "scroll") return true; } return false; };
  const fuera = [...document.querySelectorAll("body *")].filter((e) => vis(e) && !e.closest("[hidden]") && !e.closest("#pvs") && !e.closest(".pvlist")).filter((e) => { const r = e.getBoundingClientRect(); return r.right > W + 1 && !dentroDeContenedorConDesplazamiento(e); });
  const tablas = [...document.querySelectorAll("table")].filter((t) => vis(t) && !t.closest("#pvs")).map((t) => ({ t, w: t.scrollWidth, cw: (t.parentElement || t).clientWidth })).filter((x) => x.w > x.cw + 1 && !dentroDeContenedorConDesplazamiento(x.t) && !/^(auto|scroll)$/.test(getComputedStyle(x.t).overflowX));    // una tabla con su propio desplazamiento no «se sale»
  const tactiles = [...document.querySelectorAll("button, a[href], input:not([type=hidden]), select, summary, [role=tab]")].filter((e) => vis(e) && !e.disabled && !e.closest("#pvs"))
    .filter((e) => { const r = e.getBoundingClientRect(); return Math.min(r.width, r.height) < 24; });          // 24 px: mínimo de WCAG 2.2 (criterio 2.5.8)
  const diminutos = [...document.querySelectorAll("body *")].filter((e) => vis(e) && !e.closest("#pvs") && [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()) && parseFloat(getComputedStyle(e).fontSize) < 10.5);
  const recortados = [...document.querySelectorAll(".btn, .step, .tab, .chip, .fl, .sev, button")].filter((e) => vis(e) && !e.closest("#pvs") && e.scrollWidth > e.clientWidth + 2 && getComputedStyle(e).overflowX !== "visible");
  return { ancho: W, scrollW: de.scrollWidth, desborde_horizontal: de.scrollWidth > W + 1, fuera: fuera.slice(0, 6).map(sel), n_fuera: fuera.length,
    tablas_que_no_caben: tablas.slice(0, 4).map((x) => sel(x.t) + ` ${x.w}>${x.cw}`), n_tablas: tablas.length, tactiles_pequenos: tactiles.slice(0, 6).map(sel), n_tactiles: tactiles.length,
    texto_diminuto: diminutos.slice(0, 4).map(sel), n_diminutos: diminutos.length, recortados: recortados.slice(0, 4).map(sel), n_recortados: recortados.length };
};

try {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 1 });
  const p = await ctx.newPage();
  p.on("console", (m) => { if (m.type() === "error") out.consola.push(m.text().slice(0, 200)); });
  p.on("pageerror", (e) => out.consola.push("pageerror: " + String(e).slice(0, 200)));

  const recorrer = async (nombre) => {
    out.pantallas[nombre] = {};
    for (const [k, w] of Object.entries(ANCHOS)) {
      await p.setViewportSize({ width: w, height: 900 }); await p.waitForTimeout(250);
      out.pantallas[nombre][k] = await p.evaluate(medir);
      if (k === "movil" || k === "tablet") await p.screenshot({ path: `${outdir}/${nombre}_${k}.png`, fullPage: true });
    }
    await p.setViewportSize({ width: 1280, height: 900 }); await p.waitForTimeout(150);
  };

  await p.goto(site);
  await p.waitForSelector("#boot", { state: "hidden", timeout: 300000 });
  await recorrer("1_cargar_vacio");
  await p.selectOption("#u", "aetops"); await p.selectOption("#p", "mensual");
  await p.fill("#y", "2026"); await p.selectOption("#i", month);
  await p.setInputFiles("#file", xlsx);
  await p.waitForFunction(() => !document.querySelector("#next").disabled, null, { timeout: 120000 });
  await recorrer("2_cargar_con_libro");
  await p.click("#next"); await p.waitForSelector("#tg", { timeout: 120000 });
  await recorrer("3_validar");
  await p.click("#tg"); await p.waitForSelector("#saveT");
  for (const t of await p.$$("[data-t]")) await t.fill((await t.getAttribute("data-t")) === "total" ? "12000000" : "3000000");
  await recorrer("4_metas_y_contexto");
  await p.click("#saveT"); await p.waitForTimeout(2500);
  await p.click("#nx"); await p.waitForSelector("#n5", { timeout: 120000 });
  await recorrer("5_narrativa");
  await p.click("#n5"); await p.waitForSelector("#go", { timeout: 60000 }); await p.waitForSelector("#escCard");
  await recorrer("6_generar_antes");
  await p.click("#go");
  await p.waitForFunction(() => !S.busy && !!document.querySelector("#pvBox"), null, { timeout: 420000 });
  await recorrer("7_generar_resultado");
  await p.evaluate(() => { document.querySelector("#escCard details").open = true; });
  await p.fill("#escCtx", "Cambio para comprobar la vigencia");
  await p.click("#escSave"); await p.waitForFunction(() => /Resultados desactualizados/.test(document.body.innerText), null, { timeout: 60000 });
  await recorrer("8_generar_desactualizado");
  await p.click('.tab[data-tab="hist"]'); await p.waitForTimeout(1500);
  await recorrer("9_historial");
  await p.click('.tab[data-tab="tpl"]'); await p.waitForTimeout(1000);
  await recorrer("10_plantillas");
  out.ok = true;
} catch (e) {
  out.error = String(e).slice(0, 400);
} finally {
  await browser.close();
}
console.log("RESULTADO " + JSON.stringify(out));
