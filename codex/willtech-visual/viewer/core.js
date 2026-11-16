const AGENTS = [
  { id: "willtech-general", name: "General", action: "Coordenando", color: "#87d8f5" },
  { id: "willtech-explorador", name: "Explorador", action: "Explorando código", color: "#8bd76b" },
  { id: "willtech-pesquisador", name: "Pesquisador", action: "Investigando", color: "#ba93f6" },
  { id: "willtech-visual", name: "Visual", action: "Trabalhando na interface", color: "#61dae1" },
  { id: "willtech-executor", name: "Executor", action: "Implementando", color: "#ffac65" },
  { id: "willtech-testador", name: "Testador", action: "Validando", color: "#f6d35f" },
  { id: "willtech-revisor", name: "Revisor", action: "Analisando", color: "#dce1eb" },
];
const TERMINAL = { succeeded: "completed", failed: "error", interrupted: "blocked" };
const EVENTS = {
  "session.execution.started": "working",
  "session.execution.succeeded": "completed",
  "session.execution.failed": "error",
  "session.execution.interrupted": "blocked",
};

function executionState(session, observation) {
  if (observation) return observation.state;
  const busy = session.time.busy || 0;
  const idle = session.time.idle || 0;
  // O cliente também marca running otimisticamente antes de receber execução nativa.
  if (session.status === "running" && busy > idle) return "working";
  if (busy > idle) return "waiting";
  if (session.pending) return "waiting";
  return TERMINAL[session.outcome] || "waiting";
}

function projectAgents(sessions, observations = new Map(), connected = true) {
  return AGENTS.map((agent) => {
    const matches = connected ? sessions.filter((session) => session.agent === agent.id) : [];
    const runs = matches.map((session) => {
      const observation = observations.get(session.id);
      let state = executionState(session, observation);
      if (state === "working" && session.permissions) state = "blocked";
      const at = observation?.at ?? Math.max(session.time.busy || 0, session.time.idle || 0);
      return { state, at, interrupted: state === "blocked" && !session.permissions };
    });
    const selected = runs.find((run) => run.state === "working")
      || runs.find((run) => run.state === "blocked")
      || runs.sort((a, b) => b.at - a.at)[0];
    const state = selected?.state || "waiting";
    const label = state === "working" ? agent.action
      : state === "completed" ? "Concluído"
      : state === "error" ? "Erro"
      : state === "blocked" ? selected.interrupted ? "Interrompido" : "Aguardando autorização"
      : connected ? "Aguardando" : "Sem conexão";
    return { ...agent, state, label, count: matches.length };
  });
}

export { AGENTS, EVENTS, projectAgents };
