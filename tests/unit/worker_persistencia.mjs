// Arnés de frontend/worker.js (sin navegador ni Pyodide): ejecuta el worker REAL en un contexto `vm` con IndexedDB, Pyodide y puente simulados
// y comprueba cuándo se persiste el historial. Imprime una línea JSON con los resultados; sale con código 1 si alguna comprobación falla.
import vm from "node:vm";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SRC = fs.readFileSync(process.env.WORKER_JS || path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../frontend/worker.js"), "utf8");
const SQLITE = new Uint8Array([...Buffer.from("SQLite format 3\0"), 1, 2, 3, 4]);
const resultados = {};
const fallos = [];
const ok = (nombre, cond, detalle) => { resultados[nombre] = !!cond; if (!cond) fallos.push(nombre + (detalle ? ": " + detalle : "")); };

function nuevoIDB(almacen) {                              // IndexedDB mínimo: una base, un almacén «files»; `almacen` (Map) sobrevive a «recargar»
  const peticion = (fn) => { const r = {}; setTimeout(() => { try { r.result = fn(); r.onsuccess && r.onsuccess(); } catch (e) { r.error = e; r.onerror && r.onerror(); } }, 0); return r; };
  return { open() { const r = {}; setTimeout(() => { r.result = {
      createObjectStore() {},
      transaction() { const t = {}; return { objectStore: () => ({ get: (k) => peticion(() => almacen.get(k)), put: (v, k) => { almacen.set(k, v); setTimeout(() => t.oncomplete && t.oncomplete(), 0); return {}; } }), set oncomplete(f) { t.oncomplete = f; }, set onerror(f) { t.onerror = f; } }; } };
      r.onupgradeneeded && r.onupgradeneeded(); r.onsuccess && r.onsuccess(); }, 0); return r; } };
}

// «Abre» el sitio: un worker nuevo (como tras recargar la página) sobre el mismo almacenamiento del navegador.
async function abrir(almacen, { historialSemilla = null } = {}) {
  const archivos = new Map(); const llamadas = []; const mensajes = []; let n = 0;
  const FS = { mkdirTree() {}, writeFile: (p, b) => archivos.set(p, new Uint8Array(b)), readFile: (p) => archivos.get(p), unlink: (p) => archivos.delete(p), analyzePath: (p) => ({ exists: archivos.has(p) }) };
  // Puente simulado: el historial «vive» en HIST; guardar/borrar un escenario lo modifica; responde como el real (status/json).
  const propios = new Map();
  const bridge = { handle(method, p, body) {
    llamadas.push([method, p]);
    let json = { ok: true }, status = 200;
    if (/\/escenarios-reporte\//.test(p) && method === "PUT") { propios.set(p.split("/").pop(), body); archivos.set("/data/historial.sqlite", new Uint8Array([...SQLITE, ...Buffer.from(JSON.stringify([...propios.keys()]))])); }
    else if (/\/escenarios-reporte\//.test(p) && method === "DELETE") { propios.delete(p.split("/").pop()); archivos.set("/data/historial.sqlite", new Uint8Array([...SQLITE, ...Buffer.from(JSON.stringify([...propios.keys()]))])); }
    else if (/\/generate$/.test(p) && method === "POST") archivos.set("/data/historial.sqlite", new Uint8Array([...SQLITE, 9]));
    else if (p === "/api/escenarios-reporte" && method === "GET") json = { propios: [...propios.keys()] };
    else if (p === "/api/runs/zzz/plan" && method === "PUT") { status = 400; return JSON.stringify({ status, error: "plan inválido" }); }
    return JSON.stringify({ status, json });
  } };
  const pyodide = { FS, globals: { set() {} }, runPython() {}, runPythonAsync: async () => {}, loadPackage: async () => {}, unpackArchive() {}, pyimport: () => bridge };
  const ctx = { self: null, indexedDB: nuevoIDB(almacen), importScripts() {}, loadPyodide: async () => pyodide, TextDecoder, URLSearchParams, Uint8Array, JSON, Math, setTimeout, Promise,
    fetch: async (u) => ({ ok: false, json: async () => (String(u).endsWith("index.json") ? [] : null), arrayBuffer: async () => new ArrayBuffer(0) }) };
  ctx.self = { location: { search: "", href: "http://x/y/worker.js" }, postMessage: (m) => mensajes.push(m) };
  vm.createContext(ctx); vm.runInContext(SRC, ctx);
  if (historialSemilla) await almacen.set("historial", historialSemilla);
  const enviar = async (m) => { const id = ++n; const k = mensajes.length; await ctx.self.onmessage({ data: { id, ...m } }); for (let i = 0; i < 50 && !mensajes.slice(k).some((x) => x.id === id); i++) await new Promise((r) => setTimeout(r, 5)); return mensajes.slice(k).find((x) => x.id === id); };
  return { enviar, archivos, llamadas, propios };
}
const guardado = (almacen) => almacen.get("historial");
const texto = (u8) => (u8 ? Buffer.from(u8).toString("latin1") : "");

// 1 ─ PUT de un escenario propio: se persiste en IndexedDB (antes del cambio solo se persistía tras «generate»).
let A = new Map(); let w = await abrir(A);
ok("put_responde_ok", (await w.enviar({ method: "PUT", path: "/api/escenarios-reporte/mio", body: { nombre: "Propio" } })).ok);
ok("put_persiste_historial", guardado(A) && texto(guardado(A)).includes('["mio"]'), texto(guardado(A)));

// 2 ─ «Recargar» (worker nuevo, mismo IndexedDB): el historial guardado se restaura en el sistema de archivos del motor.
let w2 = await abrir(A);
await w2.enviar({ method: "GET", path: "/api/escenarios-reporte" });
ok("recarga_restaura_historial", w2.archivos.has("/data/historial.sqlite") && texto(w2.archivos.get("/data/historial.sqlite")).includes('["mio"]'));

// 3 ─ DELETE tras recargar: también se persiste (el escenario borrado no reaparece en la siguiente recarga).
const rd = await w2.enviar({ method: "DELETE", path: "/api/escenarios-reporte/mio" });
ok("delete_responde_ok", rd.ok);
ok("delete_persiste_historial", texto(guardado(A)).includes("[]") && !texto(guardado(A)).includes("mio"), texto(guardado(A)));

// 4 ─ Compatibilidad con la persistencia anterior: «generate» sigue persistiendo; GET y otras rutas NO persisten.
A = new Map(); w = await abrir(A);
await w.enviar({ method: "GET", path: "/api/escenarios-reporte" });
await w.enviar({ method: "PUT", path: "/api/runs/abc/context", body: { items: [] } });
ok("get_y_otras_rutas_no_persisten", guardado(A) === undefined);
await w.enviar({ method: "POST", path: "/api/runs/abc/generate" });
ok("generate_sigue_persistiendo", guardado(A) && texto(guardado(A)).includes("SQLite format 3"));

// 5 ─ Un PUT/DELETE que falla (error del puente) no persiste.
A = new Map(); w = await abrir(A);
const e = await w.enviar({ method: "PUT", path: "/api/runs/zzz/plan", body: {} });
ok("error_no_persiste", e.ok === false && e.status === 400 && guardado(A) === undefined);

// 6 ─ Historial existente (anterior al bloque, sin tabla de escenarios) se restaura intacto y no se reescribe por solo cargar.
const previo = new Uint8Array([...SQLITE, ...Buffer.from("historial-anterior")]);
A = new Map(); A.set("historial", previo); w = await abrir(A);
await w.enviar({ method: "GET", path: "/api/info" });
ok("historial_existente_restaurado_intacto", texto(w.archivos.get("/data/historial.sqlite")).endsWith("historial-anterior") && texto(guardado(A)).endsWith("historial-anterior"));
await w.enviar({ method: "PUT", path: "/api/escenarios-reporte/nuevo", body: { nombre: "N" } });
ok("put_sobre_historial_existente_persiste", texto(guardado(A)).includes('["nuevo"]'));

// 7 ─ importHistory conserva su comportamiento (valida cabecera y persiste).
A = new Map(); w = await abrir(A);
ok("importar_rechaza_no_sqlite", (await w.enviar({ op: "importHistory", buffer: new Uint8Array([1, 2, 3]).buffer })).status === 400 && guardado(A) === undefined);
ok("importar_sqlite_persiste", (await w.enviar({ op: "importHistory", buffer: previo.buffer })).ok && texto(guardado(A)).endsWith("historial-anterior"));

console.log(JSON.stringify({ resultados, fallos }));
process.exit(fallos.length ? 1 : 0);
