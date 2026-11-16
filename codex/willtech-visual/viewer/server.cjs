// Servidor local do visualizador complementar Codex. Serve os arquivos estáticos
// e um fluxo SSE (/events) que acompanha o feed JSONL produzido pelos hooks
// oficiais e/ou pelo cliente do App Server. Apenas stdlib do Node; sem IA, sem
// rede externa. Uso: node server.cjs [porta] [feed.jsonl] → abra o localhost na porta escolhida.
const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");

const DIR = __dirname;
const PORT = Number(process.argv[2] || 8741);
// Loopback por padrão: /history e /events expõem atividade de sessões e não
// devem ficar acessíveis pela rede. WILLTECH_CODEX_HOST permite override explícito.
const HOST = process.env.WILLTECH_CODEX_HOST || "127.0.0.1";
const FEED = process.argv[3] || process.env.WILLTECH_CODEX_FEED || path.join(process.cwd(), ".codex", "willtech-events.jsonl");
const MIME = { ".html": "text/html", ".js": "text/javascript", ".json": "application/json", ".webp": "image/webp" };

const clients = new Set();
let offset = 0;
function pump() {
  fs.readFile(FEED, "utf8", (err, text) => {
    if (err) return;
    if (text.length <= offset) { if (text.length < offset) offset = 0; return; }
    const chunk = text.slice(offset);
    offset = text.length;
    for (const line of chunk.split("\n")) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      for (const res of clients) res.write(`data: ${trimmed}\n\n`);
    }
  });
}
const pumpTimer = setInterval(pump, 300);
if (pumpTimer.unref) pumpTimer.unref();

const server = http.createServer((req, res) => {
  if (req.url === "/history") {
    fs.readFile(FEED, "utf8", (err, text) => {
      const records = err ? [] : text.split("\n").filter((l) => l.trim())
        .map((l) => { try { return JSON.parse(l); } catch { return null; } })
        .filter(Boolean);
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify(records));
    });
    return;
  }
  if (req.url === "/events") {
    res.writeHead(200, { "Content-Type": "text/event-stream", "Cache-Control": "no-cache", Connection: "keep-alive" });
    res.write("retry: 1000\n\n");
    clients.add(res);
    pump();
    req.on("close", () => clients.delete(res));
    return;
  }
  const rel = req.url === "/" ? "/index.html" : req.url.split("?")[0];
  const file = path.join(DIR, path.normalize(rel));
  if (!file.startsWith(DIR) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
    res.writeHead(404); res.end("not found"); return;
  }
  res.writeHead(200, { "Content-Type": MIME[path.extname(file)] || "application/octet-stream" });
  fs.createReadStream(file).pipe(res);
});
if (require.main === module) {
  server.listen(PORT, HOST, () => console.log(`willtech-codex-viewer em ${HOST}:${PORT} feed=${FEED}`));
}
module.exports = { server, HOST, PORT, FEED };