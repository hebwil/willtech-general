(() => {
  let owner = null;
  let effect = null;
  const queue = new Set();
  let queued = false;
  function scope() { return { effects: new Set(), cleanups: [] }; }
  function dispose(target) {
    target.effects.forEach((item) => { item.live = false; item.dependencies.forEach((deps) => deps.delete(item)); queue.delete(item); });
    target.cleanups.splice(0).reverse().forEach((cleanup) => cleanup());
  }
  function under(target, fn) {
    const previous = owner;
    owner = target;
    try { return fn(); } finally { owner = previous; }
  }
  function createSignal(initial) {
    let value = initial;
    const dependencies = new Set();
    return [() => {
      if (effect) { dependencies.add(effect); effect.dependencies.add(dependencies); }
      return value;
    }, (next) => {
      value = typeof next === "function" ? next(value) : next;
      dependencies.forEach((item) => queue.add(item));
      if (!queued) {
        queued = true;
        queueMicrotask(() => {
          queued = false;
          const current = [...queue];
          queue.clear();
          current.forEach((item) => { if (item.live) item.run(); });
        });
      }
      return value;
    }];
  }
  function createEffect(fn) {
    const target = owner;
    const item = { live: true, dependencies: new Set(), run() {
      item.dependencies.forEach((deps) => deps.delete(item));
      item.dependencies.clear();
      const previous = effect;
      effect = item;
      try { under(target, fn); } finally { effect = previous; }
    } };
    target.effects.add(item);
    item.run();
  }
  function onCleanup(fn) { owner.cleanups.push(fn); }
  function createKeyed(read, fn, options) {
    let key;
    let child;
    onCleanup(() => { if (child) dispose(child); });
    createEffect(() => {
      const next = read();
      if (key && options.equals(key, next)) return;
      if (child) dispose(child);
      key = next;
      child = scope();
      const previous = effect;
      effect = null;
      try { under(child, () => fn(next)); } finally { effect = previous; }
    });
  }
  const sdk = { Plugin: { define: (value) => value }, Panel: "Panel", Command: "Command", Style: "Style", createKeyed };
  window.module = { exports: {} };
  window.require = (id) => {
    if (id === "@opencode/plugin/gui") return sdk;
    if (id === "solid-js") return { createSignal, createEffect, onCleanup };
    throw new Error(`Dependência não fornecida pelo host de teste: ${id}`);
  };

  const names = ["general", "explorador", "pesquisador", "visual", "executor", "testador", "revisor"];
  const tick = () => new Promise((resolve) => setTimeout(resolve, 0));
  function fixture(overrides = {}) {
    const [records, setRecords] = createSignal(names.map((name) => ({ id: name, agent: `willtech-${name}`, time: { busy: 0, idle: 0 }, status: "idle", permissions: 0, pending: 0 })));
    const [connected, setConnected] = createSignal(true);
    const [compatible, setCompatible] = createSignal(true);
    const [visible, setVisible] = createSignal(true);
    const [selected, setSelected] = createSignal("general");
    const listeners = new Map();
    const data = {
      on(type, handler) {
        if (!listeners.has(type)) listeners.set(type, new Set());
        listeners.get(type).add(handler);
        return () => listeners.get(type).delete(handler);
      },
      session: {
        family: () => records().map((row) => row.id),
        get: (id) => records().find((row) => row.id === id),
        status: (id) => records().find((row) => row.id === id)?.status || "idle",
        permission: { list: (id) => Array(records().find((row) => row.id === id)?.permissions || 0).fill({}) },
        pending: { list: (id) => Array(records().find((row) => row.id === id)?.pending || 0).fill({}) },
      },
    };
    const server = { data, get connected() { return connected(); }, get compatible() { return compatible(); } };
    const props = { get session() { return { id: selected(), key: `test\n${selected()}`, server }; } };
    const registrations = [];
    const controller = new AbortController();
    const target = scope();
    const ctx = {
      id: "willtech-general-visual", options: { enabled: true }, app: { platform: "desktop", version: "2.2.6" }, signal: controller.signal,
      sessions: { current: () => props.session },
      layout: { state: () => visible() ? "visible" : "closed", toggle: () => setVisible((value) => !value) },
      add(registry, value) {
        registrations.push({ registry, value });
        if (registry === "Style") {
          const style = document.createElement("style");
          style.textContent = value;
          document.head.append(style);
          onCleanup(() => style.remove());
        }
      },
      ...overrides,
    };
    under(target, () => module.exports.default.setup(ctx));
    const panel = registrations.find((item) => item.registry === "Panel")?.value;
    const node = panel ? under(target, () => panel.render(props)) : null;
    if (node) document.getElementById("preview").replaceChildren(node);
    let time = 100;
    return {
      node, registrations, panel, records, setRecords, setConnected, setCompatible, setVisible, setSelected,
      change(id, fields) { setRecords((rows) => rows.map((row) => row.id === id ? { ...row, ...fields } : row)); },
      emit(type, id) { listeners.get(type)?.forEach((handler) => handler({ type, created: ++time, data: { sessionID: id } })); },
      state(id) { return node.querySelector(`[data-agent="willtech-${id}"]`)?.dataset.state; },
      image(id) { return node.querySelector(`[data-agent="willtech-${id}"] img`); },
      listeners: () => [...listeners.values()].reduce((sum, group) => sum + group.size, 0),
      dispose() { controller.abort(); dispose(target); },
    };
  }

  window.__under = under;
  window.__dispose = dispose;
  window.runGuiTests = async () => {
    if (window.guiTestRunning || window.guiTestResults) throw new Error("Rodada já iniciada; sem repetição automática");
    window.guiTestRunning = true;
    document.getElementById("result").textContent = "Executando uma rodada simulada; nenhum modelo ou agente será acionado.";
    const passed = [];
    const check = (condition, name) => { if (!condition) throw new Error(name); passed.push(name); };
    let active;
    try {
      for (const overrides of [{ options: {} }, { options: { enabled: false } }, { app: { platform: "web", version: "2.2.6" } }, { app: { platform: "desktop", version: "2.2.5" } }, { app: { platform: "desktop", version: "2.2.7" } }]) {
        const f = fixture(overrides);
        check(f.registrations.length === 0, `Opt-in/versão/superfície: ${JSON.stringify(overrides)}`);
        f.dispose();
      }
      active = fixture();
      const f = active;
      check(f.registrations.length === 3 && f.listeners() === 4, "Panel, Style e Command registrados; quatro eventos, nenhum polling");
      check(f.panel.list({ open: [] }).length === 0 && f.panel.list({ open: ["team"] })[0] === f.panel.list({ open: ["team"] })[0], "Abertura opcional e identidade estável da aba");
      check(names.every((name) => f.state(name) === "waiting"), "Sete agentes aguardando, sem atividade inventada");
      f.change("general", { status: "running" });
      await tick();
      check(f.state("general") === "waiting", "Running otimista não anima antes de execução real");
      f.emit("session.execution.started", "unrelated");
      await tick();
      check(names.every((name) => f.state(name) === "waiting"), "Eventos de outras famílias ignorados");
      f.emit("session.execution.started", "general");
      await tick();
      check(f.state("general") === "working" && names.slice(1).every((name) => f.state(name) === "waiting"), "Evento de início muda somente General");
      check(f.image("general").src.startsWith(window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "data:image/webp" : "data:image/apng"), "APNG ativo ou WebP com reduced-motion");
      f.node.querySelector("button").click();
      await tick();
      check(f.image("general").src.startsWith("data:image/webp") && f.node.dataset.motion === "off", "Pausa reversível sem interromper execução");
      f.node.querySelector("button").click();
      f.setVisible(false);
      await tick();
      check(f.image("general").src.startsWith("data:image/webp") && f.node.dataset.motion === "off", "Painel oculto não anima");
      f.setVisible(true);
      f.change("general", { permissions: 1 });
      await tick();
      check(f.state("general") === "blocked" && f.image("general").src.startsWith("data:image/webp"), "Autorização pendente bloqueia animação");
      f.change("general", { permissions: 0 });
      await tick();
      check(f.state("general") === "working", "Resposta à autorização restaura execução observada");
      f.emit("session.execution.failed", "general");
      await tick();
      check(f.state("general") === "error" && f.image("general").src.startsWith("data:image/webp"), "Erro terminal encerra APNG mesmo com snapshot atrasado");
      for (const name of names) {
        f.emit("session.execution.started", name);
        await tick();
        check(f.state(name) === "working", `Identidade nativa: willtech-${name}`);
        f.emit("session.execution.succeeded", name);
        await tick();
        check(f.state(name) === "completed", `Conclusão encerra atividade: willtech-${name}`);
      }
      f.emit("session.execution.started", "explorador");
      f.emit("session.execution.interrupted", "explorador");
      await tick();
      check(f.state("explorador") === "blocked", "Interrupção nunca é conclusão bem-sucedida");
      f.setConnected(false);
      await tick();
      check(names.every((name) => f.state(name) === "waiting") && f.listeners() === 0, "Desconexão limpa observações, animações e inscrições");
      f.setConnected(true);
      await tick();
      check(f.listeners() === 4 && names.every((name) => f.state(name) === "waiting"), "Reconexão não reaproveita observações antigas");
      f.change("visual", { status: "running", time: { busy: 20, idle: 10 } });
      await tick();
      check(f.state("visual") === "working", "Inicialização por execução nativa já sincronizada");
      f.change("visual", { agent: "build" });
      await tick();
      check(f.state("visual") === "waiting", "Comandante build não é atribuído ao Visual ou General");
      f.change("visual", { agent: "willtech-visual", fork: { sessionID: "other" } });
      await tick();
      check(f.state("visual") === "waiting", "Fork importado não simula execução própria");
      f.change("visual", { fork: undefined, status: "idle", time: { busy: 10, idle: 20 }, outcome: "failed" });
      f.setSelected("explorador");
      await tick();
      check(f.state("visual") === "error" && f.listeners() === 4, "Troca de sessão reavalia getters e substitui inscrições");
      f.setCompatible(false);
      await tick();
      check(names.every((name) => f.state(name) === "waiting") && f.listeners() === 0, "Servidor incompatível desativa indicação de atividade");
      f.dispose();
      check(f.listeners() === 0 && f.node.dataset.motion === "off", "Desativação/unmount limpa recursos e congela imagens");
      const preview = fixture();
      active = preview;
      preview.emit("session.execution.started", "general");
      preview.emit("session.execution.started", "explorador");
      preview.emit("session.execution.succeeded", "pesquisador");
      preview.emit("session.execution.started", "visual");
      preview.emit("session.execution.failed", "executor");
      preview.emit("session.execution.succeeded", "testador");
      preview.emit("session.execution.interrupted", "revisor");
      await tick();
      // decode() de imagens animadas pode aguardar indefinidamente numa janela oculta.
      for (const image of preview.node.querySelectorAll("img")) {
        if (image.complete) continue;
        await new Promise((resolve, reject) => {
          const cleanup = () => {
            clearTimeout(timer);
            image.removeEventListener("load", loaded);
            image.removeEventListener("error", failed);
          };
          const loaded = () => { cleanup(); resolve(); };
          const failed = () => { cleanup(); reject(new Error("Imagem indisponível na bancada")); };
          const timer = setTimeout(failed, 5000);
          image.addEventListener("load", loaded, { once: true });
          image.addEventListener("error", failed, { once: true });
        });
      }
      check([...preview.node.querySelectorAll("img")].every((image) => image.naturalWidth > 0), "Sete mascotes originais carregados no navegador");
      const css = document.querySelector("style:last-of-type").textContent;
      check(css.includes("prefers-reduced-motion: reduce") && css.includes("animation: none !important"), "CSS acessível sem movimento obrigatório");
      window.guiFixture = preview;
      window.guiTestResults = { status: "PASS", tests: passed.length, passed, nativeHomologation: "NÃO TESTADA", simulation: true };
      document.getElementById("result").textContent = `${passed.length} verificações de laboratório aprovadas.\nHomologação OpenCode Desktop: NÃO TESTADA.`;
      return window.guiTestResults;
    } catch (error) {
      active?.dispose();
      window.guiTestResults = { status: "FAIL", tests: passed.length, error: error.message, simulation: true };
      document.getElementById("result").textContent = JSON.stringify(window.guiTestResults);
      return window.guiTestResults;
    }
  };
})();
