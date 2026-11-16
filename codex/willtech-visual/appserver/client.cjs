// Cliente oficial do App Server do Codex (JSON-RPC sobre stdio, JSONL).
// Observa notificações reais e as traduz para os mesmos eventos normalizados
// consumidos pelo visualizador complementar. Não chama modelo, não faz rede
// além do processo local do Codex, não altera o aplicativo. A granularidade de
// subagentes vem dos hooks oficiais; o App Server expõe o turno do laço principal.
const { spawn } = require("node:child_process");
const readline = require("node:readline");

const GENERAL = "willtech-general";

// Tradução determinística de notificações oficiais -> evento normalizado.
function mapNotification(method, params = {}) {
  const at = Date.now();
  const session = params.threadId || params.thread_id || "main";
  if (method === "turn/started") {
    return { agent: GENERAL, state: "working", session, event: method, at };
  }
  if (method === "turn/completed") {
    const aborted = params.aborted || params.status === "aborted" || params.status === "interrupted";
    const failed = params.status === "failed" || params.error;
    const state = aborted ? "blocked" : failed ? "error" : "completed";
    return { agent: GENERAL, state, session, event: method, at };
  }
  if (method === "thread/status/changed") {
    const status = params.status || params.state;
    if (status === "running" || status === "active") return { agent: GENERAL, state: "working", session, event: method, at };
    if (status === "idle" || status === "ready") return { agent: GENERAL, state: "waiting", session, event: method, at };
  }
  return null;
}

function connect({ bin, env = {}, onEvent, onReady }) {
  const child = spawn(bin, [], { env: { ...process.env, ...env }, stdio: ["pipe", "pipe", "pipe"] });
  const pending = new Map();
  let nextId = 1;
  const rl = readline.createInterface({ input: child.stdout });
  rl.on("line", (line) => {
    line = line.trim();
    if (!line) return;
    let msg;
    try { msg = JSON.parse(line); } catch { return; }
    if (msg.id != null && pending.has(msg.id)) {
      const { resolve } = pending.get(msg.id);
      pending.delete(msg.id);
      resolve(msg);
      return;
    }
    if (msg.method && msg.id == null) {
      const record = mapNotification(msg.method, msg.params);
      if (record && onEvent) onEvent(record);
    }
  });
  function send(obj) { child.stdin.write(JSON.stringify(obj) + "\n"); }
  function request(method, params, timeout = 20000) {
    const id = nextId++;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => { pending.delete(id); reject(new Error(`timeout ${method}`)); }, timeout);
      pending.set(id, { resolve: (msg) => { clearTimeout(timer); resolve(msg); } });
      send({ jsonrpc: "2.0", id, method, params });
    });
  }
  async function start() {
    const init = await request("initialize", {
      clientInfo: { name: "willtech-visual", title: "WillTech Visual (complementar)", version: "0.1.0" },
      capabilities: { experimentalApi: true },
    });
    send({ jsonrpc: "2.0", method: "initialized" });
    if (onReady) onReady(init.result);
    return init;
  }
  function close() { rl.close(); child.kill(); }
  return { start, request, close, child };
}

module.exports = { connect, mapNotification, GENERAL };