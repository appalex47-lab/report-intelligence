/* Motor Python (Pyodide) en un Web Worker: todo corre en el navegador; los archivos nunca salen del equipo.
   Mensajes: {id, method, path, body, file:{name,buffer}} -> {id, ok, status, json | error | file:{name,buffer}}
             {id, op:'importHistory', buffer} | {id, op:'exportHistory'} */
const params = new URLSearchParams(self.location.search);
const PY = (params.get("py") || "https://cdn.jsdelivr.net/pyodide/v0.27.7/full/").replace(/\/?$/, "/");
const BASE = self.location.href.replace(/[^/]*(\?.*)?$/, "");
let pyodide = null, bridge = null, ready = null;
const TEMPLATE_KEYS = ["aetops-mensual", "aetops-trimestral", "glp1-mensual", "glp1-trimestral"];
const HIST = "/data/historial.sqlite";

function say(msg) { self.postMessage({ progress: msg }); }

/* ---------------------------------------------------------------- persistencia (IndexedDB)
   Plantillas e historial se guardan en el navegador del usuario: no se suben a ningún servidor. */
function idb() {
  return new Promise((res, rej) => {
    const r = indexedDB.open("report-intelligence", 1);
    r.onupgradeneeded = () => r.result.createObjectStore("files");
    r.onsuccess = () => res(r.result);
    r.onerror = () => rej(r.error);
  });
}
async function idbGet(key) {
  try { const db = await idb(); return await new Promise((res, rej) => { const q = db.transaction("files").objectStore("files").get(key); q.onsuccess = () => res(q.result); q.onerror = () => rej(q.error); }); } catch { return undefined; }
}
async function idbPut(key, val) {
  try { const db = await idb(); await new Promise((res, rej) => { const t = db.transaction("files", "readwrite"); t.objectStore("files").put(val, key); t.oncomplete = res; t.onerror = () => rej(t.error); }); } catch { /* sin almacenamiento: sigue funcionando */ }
}

function writeFile(path, bytes) {
  const dir = path.replace(/\/[^/]*$/, "");
  pyodide.FS.mkdirTree(dir);
  pyodide.FS.writeFile(path, bytes);
}
const isZip = b => b && b.length > 3 && b[0] === 0x50 && b[1] === 0x4b;

async function init() {
  say("Cargando el motor de cálculo (la primera vez tarda unos segundos)…");
  importScripts(PY + "pyodide.js");
  pyodide = await loadPyodide({ indexURL: PY });
  say("Instalando librerías…");
  await pyodide.loadPackage(["micropip", "lxml", "pyyaml", "pillow", "sqlite3", "typing-extensions"]);
  const wheels = await (await fetch(BASE + "wheels/index.json")).json();
  pyodide.globals.set("WHEEL_URLS", wheels.map(w => BASE + "wheels/" + w));
  await pyodide.runPythonAsync(`
import micropip
for _u in WHEEL_URLS.to_py():
    await micropip.install(_u, deps=False)
`);
  say("Cargando la aplicación…");
  const zip = await (await fetch(BASE + "app.zip")).arrayBuffer();
  pyodide.unpackArchive(zip, "zip", { extractDir: "/app" });
  pyodide.runPython(`
import sys, os
sys.path.insert(0, "/app")
os.environ["REPORT_RUNS_DIR"] = "/runs"
os.environ["REPORT_HISTORY_DB"] = "${HIST}"
os.environ["REPORT_TEMPLATES_DIR"] = "/templates"
for d in ("/runs", "/data", "/templates", "/upload"):
    os.makedirs(d, exist_ok=True)
`);
  const hist = await idbGet("historial");
  if (hist) writeFile(HIST, new Uint8Array(hist));
  for (const k of TEMPLATE_KEYS) {
    let bytes = await idbGet("tpl:" + k);
    bytes = bytes ? new Uint8Array(bytes) : null;
    if (!bytes) {                                   // plantilla publicada junto al sitio (repos privados), si existe
      try { const r = await fetch(`${BASE}templates/${k}/1/template.pptx`); if (r.ok) { const b = new Uint8Array(await r.arrayBuffer()); if (isZip(b)) bytes = b; } } catch { /* no hay */ }
    }
    if (bytes) writeFile(`/templates/${k}/1/template.pptx`, bytes);
  }
  bridge = pyodide.pyimport("backend.app.web.bridge");
  say("Listo.");
}

async function persist() {
  try { if (pyodide.FS.analyzePath(HIST).exists) await idbPut("historial", pyodide.FS.readFile(HIST)); } catch { /* ignorar */ }
}

async function handle(m) {
  if (m.op === "importHistory") {
    const b = new Uint8Array(m.buffer);
    if (b.length < 16 || new TextDecoder().decode(b.slice(0, 15)) !== "SQLite format 3") return { ok: false, status: 400, error: "No es un historial válido (.sqlite)." };
    writeFile(HIST, b); await persist();
    return { ok: true, status: 200, json: { ok: true } };
  }
  let upPath = "", upName = "";
  if (m.file) {
    upPath = "/upload/" + Math.random().toString(16).slice(2);
    writeFile(upPath, new Uint8Array(m.file.buffer));
    upName = m.file.name;
  }
  const out = JSON.parse(bridge.handle(m.method, m.path, m.body ? JSON.stringify(m.body) : "", upPath, upName));
  if (upPath) { try { pyodide.FS.unlink(upPath); } catch { /* ya no está */ } }
  if (out.error) return { ok: false, status: out.status, error: out.error };
  if (m.method === "POST" && /\/(generate)$/.test(m.path)) await persist();
  if (m.method === "POST" && m.path.startsWith("/api/templates/")) {
    const key = m.path.split("/").pop();
    await idbPut("tpl:" + key, pyodide.FS.readFile(`/templates/${key}/1/template.pptx`));
  }
  if (out.file) {
    const data = pyodide.FS.readFile(out.file);
    const fname = out.name || String(out.file).split("/").pop() || "reporte.pptx";
    return { ok: true, status: 200, file: { name: fname, buffer: data.buffer.slice(data.byteOffset, data.byteOffset + data.byteLength) } };
  }
  return { ok: true, status: out.status, json: out.json };
}

self.onmessage = async (e) => {
  const m = e.data;
  try {
    if (!ready) ready = init();
    await ready;
    const r = await handle(m);
    const transfer = r.file ? [r.file.buffer] : [];
    self.postMessage({ id: m.id, ...r }, transfer);
  } catch (err) {
    self.postMessage({ id: m.id, ok: false, status: 500, error: String(err && err.message || err) });
  }
};
