// Visualizador COMPLEMENTAR e independente para Codex. Não é um painel nativo
// do aplicativo Codex (que não expõe injeção de UI de 7 agentes). Consome eventos
// normalizados vindos dos hooks oficiais e/ou do App Server, reusa o núcleo
// compartilhado (core.js) e anima os sete mascotes oficiais com CSS (respiração),
// sem nenhuma chamada de IA. Suporta reduced-motion e pausa manual.
import { AGENTS, projectAgents } from "./core.js";
import { IMG } from "./assets.js";

const sessions = new Map();
const observations = new Map();
let connected = true;
let motion = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
let seq = 0;

function applyEvent(record) {
  if (!record || !record.agent) return;
  const id = record.agent;
  const at = record.at ?? ++seq;
  if (record.reset) {
    // SessionEnd encerra UMA sessão: remove só a sessão correspondente e
    // preserva as demais sessões ativas (concorrentes). Não recria a sessão
    // encerrada como atividade fantasma.
    const sid = record.session || id;
    sessions.delete(sid);
    observations.delete(sid);
    render();
    return;
  }
  let session = sessions.get(record.session || id);
  if (!session) {
    session = { id: record.session || id, agent: id, status: "running", time: { busy: at, idle: 0 }, pending: 0, permissions: 0 };
    sessions.set(session.id, session);
  }
  session.time.busy = Math.max(session.time.busy || 0, at);
  session.permissions = record.permissions ? 1 : 0;
  observations.set(session.id, { state: record.state, at });
  render();
}

function card(agent) {
  const el = document.createElement("div");
  el.className = "wt-card";
  el.dataset.agent = agent.id;
  el.dataset.state = agent.state;
  el.style.setProperty("--accent", agent.color);
  const img = document.createElement("img");
  img.src = IMG[agent.id];
  img.alt = agent.name;
  img.width = 96; img.height = 96;
  if (agent.state === "working" && motion) img.classList.add("wt-breathe");
  const name = document.createElement("strong");
  name.textContent = agent.name;
  const state = document.createElement("span");
  state.className = "wt-state";
  state.textContent = agent.label;
  el.append(img, name, state);
  return el;
}

function render() {
  const rows = projectAgents([...sessions.values()], observations, connected);
  const grid = document.getElementById("grid");
  grid.replaceChildren(...rows.map(card));
  document.getElementById("root").dataset.motion = motion ? "on" : "off";
  const button = document.getElementById("motion");
  button.textContent = motion ? "Pausar animações" : "Ativar animações";
  return rows;
}

function setMotion(value) { motion = value; render(); }

window.__applyEvents = (list) => { list.forEach(applyEvent); return render(); };
window.__setMotion = setMotion;
window.__render = render;
window.__state = () => ({ sessions: sessions.size, observations: observations.size, motion, connected });

document.getElementById("motion").addEventListener("click", () => setMotion(!motion));
const media = window.matchMedia("(prefers-reduced-motion: reduce)");
const onMedia = (e) => setMotion(!e.matches);
media.addEventListener("change", onMedia);
window.addEventListener("beforeunload", () => media.removeEventListener("change", onMedia));

render();

// Fonte de eventos: SSE do servidor local (feed JSONL dos hooks/App Server).
if (!window.__LAB_NO_SSE) {
  fetch("/history").then((res) => res.json())
    .then((records) => { records.forEach(applyEvent); })
    .catch(() => {});
  const source = new EventSource("/events");
  source.onmessage = (e) => { try { applyEvent(JSON.parse(e.data)); } catch {} };
  source.onerror = () => { connected = false; render(); };
  source.onopen = () => { connected = true; render(); };
}
window.__labReady = true;