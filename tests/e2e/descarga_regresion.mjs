// Fase 5 · regresión de la descarga (INC-001 «data.htm») en un navegador real (Playwright, Chromium).
// Carga `frontend/index.html` y ejecuta la función `download()` REAL con respuestas del motor sustituidas (nombre y bytes controlados).
// Uso: node descarga_regresion.mjs <url> <casos.json> <carpeta_salida>   (casos: [{id, path, name, b64, ua?}])
// Imprime una línea JSON con, por caso: archivo descargado (nombre, bytes, tipo del Blob), texto del aviso y si se revocó la URL antes de tiempo.
import { createRequire } from "node:module";
import fs from "node:fs";
const require = createRequire(process.env.PLAYWRIGHT_REQUIRE_FROM || import.meta.url);
const { chromium } = require("playwright");
const [, , url, casosJson, outdir] = process.argv;
const casos = JSON.parse(fs.readFileSync(casosJson, "utf-8"));
const browser = await chromium.launch();
const resultados = {};
try {
  for (const c of casos) {
    const ctx = await browser.newContext({ acceptDownloads: true, ...(c.ua ? { userAgent: c.ua } : {}) });
    const p = await ctx.newPage();
    await p.goto(url, { waitUntil: "domcontentloaded" });
    await p.evaluate(() => {
      window.__blobs = []; window.__revocados = [];
      const crear = URL.createObjectURL.bind(URL), revocar = URL.revokeObjectURL.bind(URL);
      URL.createObjectURL = (b) => { window.__blobs.push({ tipo: b.type, bytes: b.size }); return crear(b); };
      URL.revokeObjectURL = (u) => { window.__revocados.push(Date.now()); return revocar(u); };
    });
    await p.evaluate(({ name, b64 }) => {
      const bin = Uint8Array.from(atob(b64), (ch) => ch.charCodeAt(0));
      window.fetchFile = async () => ({ name, buffer: bin.buffer });                  // el motor «devuelve» este nombre y estos bytes
    }, { name: c.name, b64: c.b64 });
    const espera = p.waitForEvent("download", { timeout: 3000 }).then((d) => d, () => null);
    await p.evaluate((path) => download(path), c.path);
    const d = await espera;
    const r = { descarga: null, toast: await p.evaluate(() => (document.querySelector(".toast") || {}).textContent || ""), blobs: await p.evaluate(() => window.__blobs), revocadas_antes_de_5s: 0 };
    if (d) {
      const ruta = `${outdir}/${c.id}__${d.suggestedFilename()}`;
      await d.saveAs(ruta);
      r.descarga = { nombre: d.suggestedFilename(), ruta, bytes: fs.statSync(ruta).size };
    }
    await p.waitForTimeout(5200);
    r.revocadas_antes_de_5s = await p.evaluate(() => window.__revocados.length);       // el código anterior revocaba a los 4 s
    resultados[c.id] = r;
    await ctx.close();
  }
} finally {
  await browser.close();
}
console.log("RESULTADO " + JSON.stringify(resultados));
