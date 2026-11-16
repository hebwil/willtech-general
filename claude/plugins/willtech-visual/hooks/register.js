// Mod oficial Claude Code: painel opcional dos sete agentes WillTech-General.
// Observa eventos reais (agent.spawn / turn.* / tool.check) e $.agent.list();
// nunca aciona agentes nem modelos. Animacao: SMIL no Svg (desktop/VS Code) e
// troca de quadros PNG via $.ui.blit (terminal). Sem chamadas de IA.
// Regra do loader: `$` so aparece como chamada $.noun.event(...) dentro dos
// hooks; helpers recebem apenas dados/elementos, nunca `$`.
import { AGENTS, projectAgents } from "./activity.js";
import { PNG, FRAMES, SIZE } from "./assets.js";

const PANE = "willtech-team";
const MAIN = "willtech-main-loop";
const FRAME_MS = 240;

export function register(on, options) {
  const observations = new Map();
  const permissions = new Map();
  const timers = new Map();
  let motion = options?.reducedMotion !== true;
  let seq = 0;
  let mainRunning = false;
  let mainOutcome;
  let surface = "terminal";

  const loopId = (e) => e.agentId || MAIN;
  const willtechId = (value) => {
    const text = String(value || "");
    const hit = AGENTS.find((a) => a.id === text || a.id === `willtech-${text}`);
    return hit ? hit.id : null;
  };
  const mark = (id, state) => observations.set(id, { state, at: ++seq });

  function sessionsFrom(list) {
    const sessions = [{
      id: MAIN, agent: "willtech-general",
      status: mainRunning ? "running" : "idle",
      time: { busy: mainRunning ? 1 : 0, idle: mainRunning ? 0 : 1 },
      pending: 0, permissions: permissions.get(MAIN) || 0, outcome: mainOutcome,
    }];
    for (const info of list) {
      const agent = willtechId(info.type) || willtechId(info.name);
      if (!agent) continue;
      const running = info.status === "running";
      sessions.push({
        id: info.id, agent,
        status: running ? "running" : "idle",
        time: { busy: running ? 1 : 0, idle: running ? 0 : 1 },
        pending: info.status === "waiting" ? 1 : 0,
        permissions: permissions.get(info.id) || 0,
        outcome: info.status === "completed" ? "succeeded"
          : info.status === "failed" ? "failed"
            : info.status === "killed" ? "interrupted" : undefined,
      });
    }
    return sessions;
  }

  function stopTimer(id) {
    const cancel = timers.get(id);
    if (cancel) { cancel(); timers.delete(id); }
  }
  function stopAll() {
    for (const id of [...timers.keys()]) stopTimer(id);
  }

  function svgFor(id, state) {
    const animate = state === "working" && motion
      ? '<animateTransform attributeName="transform" type="translate" values="0 0; 0 -3; 0 0" dur="2.8s" repeatCount="indefinite"/>'
      : "";
    return `<svg xmlns="http://www.w3.org/2000/svg" width="${SIZE.w}" height="${SIZE.h}" viewBox="0 0 ${SIZE.w} ${SIZE.h}">`
      + `<g>${animate}<image x="0" y="4" width="${SIZE.w}" height="${SIZE.h - 8}" href="data:image/png;base64,${PNG[id]}"/></g></svg>`;
  }

  function cardTree(elements, row) {
    const { Box, Text, Svg, Image } = elements;
    const picture = surface === "terminal"
      ? Image({ key: `wt-img-${row.id}`, source: { png: PNG[row.id] }, columns: 26, rows: 14, alt: `Mascote ${row.name}` })
      : Svg({ key: `wt-svg-${row.id}`, source: svgFor(row.id, row.state), alt: `Mascote ${row.name}`, width: 96, height: 102, isInteractive: true });
    return Box({
      flexDirection: "row", children: [
        picture,
        Box({
          flexDirection: "column", children: [
            Text({ key: `wt-name-${row.id}`, color: row.color, children: row.name }),
            Text({ key: `wt-state-${row.id}`, children: row.label + (row.count > 1 ? ` · ${row.count} sessões` : "") }),
          ],
        }),
      ],
    });
  }

  function paneTree(elements, rows, onMotion) {
    const { Box, Text, Button } = elements;
    return Box({
      flexDirection: "column", children: [
        Text({ children: "WillTech-General · sua equipe em atividade (experimental)" }),
        Button({ key: "wt-motion", children: motion ? "Pausar animações" : "Ativar animações", onPress: onMotion }),
        ...rows.map((row) => cardTree(elements, row)),
        Text({ children: "Somente eventos reais desta sessão; nenhum agente é acionado pelo painel." }),
      ],
    });
  }

  on("session.start", async ($, e, next) => {
    surface = e.surface || surface;
    await $.command.register({ name: "willtech-team", description: "Mostra os sete agentes WillTech-General" });
    return next(e);
  });

  on("command.run", { command: "willtech-team" }, async ($) => {
    await $.ui.open({ id: PANE, title: "WillTech · Equipe", focus: true, closeOnEscape: true });
    return {};
  });

  // Observacao pura: o catch replay-safe garante fail-open (nunca bloqueia agente).
  on("agent.spawn", async ($, e, next) => {
    const result = await next(e);
    if (result?.agentId) {
      mark(result.agentId, "working");
      $.ui.invalidate("ui.render");
    }
    return result;
  }).catch(($, e, next) => next(e));

  on("turn.start", async ($, e, next) => {
    mark(loopId(e), "working");
    if (!e.agentId) mainRunning = true;
    $.ui.invalidate("ui.render");
    return next(e);
  });

  on("turn.complete", async ($, e, next) => {
    mark(loopId(e), e.isAborted ? "blocked" : "completed");
    if (!e.agentId) { mainRunning = false; mainOutcome = e.isAborted ? "interrupted" : "succeeded"; }
    $.ui.invalidate("ui.render");
    return next(e);
  });

  on("tool.check", async ($, e, next) => {
    const id = loopId(e);
    permissions.set(id, (permissions.get(id) || 0) + 1);
    mark(id, "blocked");
    $.ui.invalidate("ui.render");
    const result = await next(e);
    const left = Math.max(0, (permissions.get(id) || 1) - 1);
    permissions.set(id, left);
    if (left === 0) mark(id, "working");
    $.ui.invalidate("ui.render");
    return result;
  }).catch(($, e, next) => next(e));

  on("session.end", async ($, e, next) => {
    stopAll();
    observations.clear();
    permissions.clear();
    mainRunning = false;
    mainOutcome = undefined;
    return next(e);
  });

  on("ui.render", { component: "Pane" }, async ($, e, next) => {
    if (e.requestId !== PANE) return next(e);
    surface = e.surface || surface;
    const rows = projectAgents(sessionsFrom(await $.agent.list()), observations, true);
    if (surface !== "terminal") {
      stopAll();
    } else {
      for (const row of rows) {
        const active = row.state === "working" && motion;
        if (active && !timers.has(row.id)) {
          const frames = FRAMES[row.id];
          let index = 0;
          const handle = $.clock.every(FRAME_MS, () => {
            index = (index + 1) % frames.length;
            $.ui.blit({ requestId: e.requestId, key: `wt-img-${row.id}`, source: { png: frames[index] } });
          });
          timers.set(row.id, () => handle.cancel());
        } else if (!active && timers.has(row.id)) {
          stopTimer(row.id);
          $.ui.blit({ requestId: e.requestId, key: `wt-img-${row.id}`, source: { png: PNG[row.id] } });
        }
      }
    }
    return paneTree($.ui.resolve(e), rows, () => {
      motion = !motion;
      $.ui.invalidate("ui.render");
    });
  });

  on("ui.render", { component: "AbovePrompt" }, async ($, e, next) => {
    const rows = projectAgents(sessionsFrom(await $.agent.list()), observations, true);
    const working = rows.filter((row) => row.state === "working").map((row) => row.name);
    const { Box, Text, Button } = $.ui.resolve(e);
    return Box({
      flexDirection: "row", children: [
        Text({ key: "wt-band", children: `WillTech · ${working.length ? working.join(", ") : "aguardando"}` }),
        Button({
          key: "wt-open", children: "Abrir equipe",
          onPress: () => $.ui.open({ id: PANE, title: "WillTech · Equipe", focus: true, closeOnEscape: true }),
        }),
      ],
    });
  });
}

// WillTech-General / WILLTECH-BH © 2026 · autoria: github.com/hebwil