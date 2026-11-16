// Camada Node do smoke test (WillTech): o bundle real embute os bytes
// originais dos mascotes, com a chave certa por agente. Emite os hashes
// SHA-256 das data URLs para a camada de navegador conferir a associação
// card -> imagem sem trafegar os bytes. NÃO é homologação nativa.
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const pkg = path.join(root, "opencode/plugins/willtech/visual");
const src = fs.readFileSync(path.join(pkg, "gui-experimental.cjs"), "utf8");
const literal = src.match(/const ASSETS = (\{.*?\});\n/s);
assert.ok(literal, "literal ASSETS ausente no bundle");
const assets = JSON.parse(literal[1]);

const files = {
  "willtech-general": "willtech-general-static.webp",
  "willtech-explorador": "willtech-explorador.webp",
  "willtech-pesquisador": "willtech-pesquisador.webp",
  "willtech-visual": "willtech-visual.webp",
  "willtech-executor": "willtech-executor.webp",
  "willtech-testador": "willtech-testador.webp",
  "willtech-revisor": "willtech-revisor.webp",
  generalAnimated: "willtech-general-animated.apng",
};
assert.deepEqual(Object.keys(assets).sort(), Object.keys(files).sort());
const hashes = {};
for (const [key, name] of Object.entries(files)) {
  const bytes = fs.readFileSync(path.join(root, "docs/assets", name));
  const mime = name.endsWith(".apng") ? "apng" : "webp";
  assert.equal(assets[key], `data:image/${mime};base64,` + bytes.toString("base64"),
    `asset ${key} difere dos bytes originais`);
  hashes[key] = crypto.createHash("sha256").update(assets[key]).digest("hex");
}
assert.ok(!/\b(fetch|XMLHttpRequest|WebSocket|EventSource)\s*\(/.test(src),
  "bundle não pode conter chamadas de rede/IA");
const apng = fs.readFileSync(path.join(root, "docs/assets", files.generalAnimated));
const frames = apng.readUInt32BE(apng.indexOf("acTL") + 4);
assert.ok(frames > 1, "APNG precisa ser multi-quadro");
console.log(JSON.stringify({ hashes, frames, bytes: Buffer.byteLength(src) }));
console.error(`PASS: smoke node — 8 assets originais mapeados por chave, ${frames} quadros APNG, zero rede/IA no bundle`);