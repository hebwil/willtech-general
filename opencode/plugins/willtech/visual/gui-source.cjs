const { Plugin, Panel, Command, Style, createKeyed } = require("@opencode/plugin/gui");
const { createEffect, createSignal, onCleanup } = require("solid-js");
const { AGENTS, EVENTS, projectAgents } = require("./activity.cjs");
const ASSETS = require("./assets.cjs");

const CSS = `
.willtech-activity { color: #e5edf6; background: #09111e; padding: 18px; font: 13px/1.5 system-ui, sans-serif; height: 100%; overflow: auto; }
.willtech-activity * { box-sizing: border-box; }
.willtech-activity h2 { font-size: 21px; margin: 2px 0 8px; letter-spacing: -.4px; }
.willtech-activity .wt-kicker { color: #87d8f5; font-size: 10px; letter-spacing: 2px; }
.willtech-activity .wt-note { color: #a2b1c5; margin: 0 0 16px; font-size: 12px; }
.willtech-activity .wt-controls { display: flex; gap: 12px; align-items: center; margin-bottom: 14px; }
.willtech-activity button { font: inherit; color: #bdeeff; background: #102638; border: 1px solid #31516a; border-radius: 7px; padding: 6px 10px; cursor: pointer; }
.willtech-activity button:focus-visible { outline: 2px solid #87d8f5; outline-offset: 3px; }
.willtech-activity .wt-grid { display: grid; gap: 10px; grid-template-columns: repeat(2, minmax(0, 1fr)); }
.willtech-activity .wt-card { border: 1px solid #283346; border-radius: 12px; overflow: hidden; background: #0b1422; padding: 10px; min-width: 0; }
.willtech-activity .wt-card:first-child { grid-column: 1 / -1; display: grid; grid-template-columns: 120px 1fr; align-items: center; }
.willtech-activity .wt-card img { width: 100%; height: 112px; object-fit: contain; display: block; border-radius: 8px; }
.willtech-activity .wt-card:first-child img { height: 140px; }
.willtech-activity .wt-name { color: var(--wt-color); font-size: 15px; font-weight: 650; margin: 6px 0 3px; }
.willtech-activity .wt-state { color: #b4c2d3; font-size: 11px; min-height: 33px; }
.willtech-activity .wt-card[data-state=working] { border-color: var(--wt-color); }
.willtech-activity .wt-card[data-state=working] img { animation: wt-breathe 2.8s ease-in-out infinite; }
.willtech-activity .wt-card[data-state=completed] .wt-state { color: #8bd76b; }
.willtech-activity .wt-card[data-state=error] .wt-state { color: #ff9595; }
.willtech-activity .wt-card[data-state=blocked] .wt-state { color: #f6d35f; }
.willtech-activity[data-motion=off] img { animation: none !important; }
.willtech-activity footer { color: #8a9ab0; font-size: 10px; margin-top: 18px; }
@keyframes wt-breathe { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-3px); } }
@media (prefers-reduced-motion: reduce) { .willtech-activity img { animation: none !important; transition: none !important; } }
@media (max-width: 300px) { .willtech-activity .wt-grid { grid-template-columns: 1fr; } .willtech-activity .wt-card:first-child { display: block; } }
`;

function renderPanel(props, ctx) {
  const root = document.createElement("section");
  root.className = "willtech-activity";
  root.lang = "pt-BR";
  root.setAttribute("aria-label", "Atividade dos sete agentes WillTech-General");
  const kicker = document.createElement("div");
  kicker.className = "wt-kicker";
  kicker.textContent = "WILLTECH-GENERAL · EXPERIMENTAL";
  const title = document.createElement("h2");
  title.textContent = "Sua equipe em atividade";
  const note = document.createElement("p");
  note.className = "wt-note";
  const controls = document.createElement("div");
  controls.className = "wt-controls";
  const motionButton = document.createElement("button");
  motionButton.type = "button";
  const connection = document.createElement("span");
  connection.className = "wt-note";
  controls.append(motionButton, connection);
  const grid = document.createElement("div");
  grid.className = "wt-grid";
  const cards = AGENTS.map((agent) => {
    const card = document.createElement("article");
    card.className = "wt-card";
    card.dataset.agent = agent.id;
    card.style.setProperty("--wt-color", agent.color);
    const image = document.createElement("img");
    image.alt = `Mascote ${agent.name}`;
    image.width = 160;
    image.height = 140;
    image.decoding = "async";
    const text = document.createElement("div");
    const name = document.createElement("div");
    name.className = "wt-name";
    name.textContent = agent.name;
    const status = document.createElement("div");
    status.className = "wt-state";
    text.append(name, status);
    card.append(image, text);
    grid.append(card);
    return { card, image, status };
  });
  const footer = document.createElement("footer");
  footer.textContent = "WillTech-General / WILLTECH-BH © 2026 · github.com/hebwil · MIT";
  root.append(kicker, title, note, controls, grid, footer);

  const media = window.matchMedia("(prefers-reduced-motion: reduce)");
  const [reduced, setReduced] = createSignal(media.matches);
  const [paused, setPaused] = createSignal(false);
  const changed = () => setReduced(media.matches);
  media.addEventListener("change", changed);
  motionButton.onclick = () => setPaused((value) => !value);
  onCleanup(() => {
    media.removeEventListener("change", changed);
    motionButton.onclick = null;
    root.dataset.motion = "off";
    cards.forEach(({ image }, index) => { image.src = ASSETS[AGENTS[index].id]; });
  });

  createKeyed(
    () => [props.session.key, props.session.server.data, props.session.server.connected, props.session.server.compatible],
    ([, data, connected, compatible]) => {
      const observations = new Map();
      const [revision, setRevision] = createSignal(0);
      if (connected && compatible) {
        Object.entries(EVENTS).forEach(([type, state]) => {
          onCleanup(data.on(type, (event) => {
            const id = event.data.sessionID;
            if (!data.session.family(props.session.id).includes(id)) return;
            const previous = observations.get(id);
            if (previous && (previous.at > event.created || (previous.at === event.created && previous.state === state))) return;
            observations.set(id, { state, at: event.created });
            setRevision((value) => value + 1);
          }));
        });
      }
      createEffect(() => {
        revision();
        const online = connected && compatible && !ctx.signal.aborted;
        const sessions = online ? data.session.family(props.session.id).flatMap((id) => {
          const info = data.session.get(id);
          if (!info || info.fork) return [];
          return [{ ...info, status: data.session.status(id), permissions: data.session.permission.list(id)?.length || 0,
            pending: data.session.pending.list(id).length }];
        }) : [];
        const family = new Set(sessions.map((session) => session.id));
        for (const id of observations.keys()) if (!family.has(id)) observations.delete(id);
        const rows = projectAgents(sessions, observations, online);
        const motion = !paused() && !reduced() && online && ctx.layout.state(`${ctx.id}:team`, props.session) === "visible";
        root.dataset.motion = motion ? "on" : "off";
        motionButton.textContent = paused() ? "Ativar animações" : "Pausar animações";
        motionButton.setAttribute("aria-pressed", String(paused()));
        connection.textContent = online ? "Eventos nativos" : "Observação indisponível";
        note.textContent = online ? "Somente a família da sessão aberta e os dados já sincronizados. Nenhum agente é acionado pelo painel."
          : "Conexão ausente ou servidor incompatível. Nenhuma atividade é indicada.";
        rows.forEach((row, index) => {
          const { card, image, status } = cards[index];
          card.dataset.state = row.state;
          status.textContent = row.label + (row.count > 1 ? ` · ${row.count} sessões` : "");
          const src = row.id === "willtech-general" && row.state === "working" && motion
            ? ASSETS.generalAnimated : ASSETS[row.id];
          if (image.getAttribute("src") !== src) image.src = src;
        });
      });
    },
    { equals: (a, b) => a.every((value, index) => value === b[index]) },
  );
  return root;
}

// A API GUI é experimental e acompanha o Desktop; o piso 2.2.6 mantém o contrato
// verificado e libera as versões atuais (2.2.7, 2.3.0) em vez de travar num pin exato.
function versionAtLeast(version, minimum) {
  const parse = (value) => String(value).split(".").map((part) => parseInt(part, 10) || 0);
  const current = parse(version);
  const floor = parse(minimum);
  for (let index = 0; index < 3; index += 1) {
    if ((current[index] || 0) !== (floor[index] || 0)) return (current[index] || 0) > (floor[index] || 0);
  }
  return true;
}

module.exports.default = Plugin.define({
  setup(ctx) {
    if (ctx.options.enabled !== true || ctx.app.platform !== "desktop" || !versionAtLeast(ctx.app.version, "2.2.6")) return;
    ctx.add(Style, CSS);
    const tab = { id: "team", title: "WillTech · Equipe", closable: "compact", fallback: true };
    ctx.add(Panel, {
      id: "team", region: "side", width: 380,
      list: (input) => input.open.includes("team") ? [tab] : [],
      render: (props) => renderPanel(props, ctx),
    });
    ctx.add(Command, {
      id: "team.toggle", title: "WillTech: mostrar/ocultar equipe",
      run: () => {
        const session = ctx.sessions.current();
        if (session) ctx.layout.toggle(`${ctx.id}:team`, session);
      },
    });
  },
});

// WillTech-General / WILLTECH-BH © 2026 · autoria: github.com/hebwil
