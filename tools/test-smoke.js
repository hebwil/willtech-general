// Smoke test headless dos sete mascotes (WillTech). Bundle real + host do
// test-gui.js + eventos determinísticos. Prova: carga, associação por hash
// SHA-256 da data URL, avanço de quadros do APNG (canvas ao vivo + prova
// determinística WebCodecs), estados, deduplicação por MutationObserver,
// limpeza, fallback e reduced-motion.
// NÃO é homologação no OpenCode Desktop.
(() => {
  const { createSignal } = window.require("solid-js");
  const names = ["general", "explorador", "pesquisador", "visual", "executor", "testador", "revisor"];
  const tick = () => new Promise((resolve) => setTimeout(resolve, 0));
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  async function sha(text) {
    const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
    return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
  }
  function fixture() {
    const [records, setRecords] = createSignal(names.map((name) => ({
      id: name, agent: `willtech-${name}`, time: { busy: 0, idle: 0 },
      status: "idle", permissions: 0, pending: 0,
    })));
    const [connected] = createSignal(true);
    const [compatible] = createSignal(true);
    const [visible] = createSignal(true);
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
        permission: { list: () => [] },
        pending: { list: () => [] },
      },
    };
    const server = { data, get connected() { return connected(); }, get compatible() { return compatible(); } };
    const props = { get session() { return { id: "general", key: "smoke\ngeneral", server }; } };
    const registrations = [];
    const controller = new AbortController();
    const target = { effects: new Set(), cleanups: [] };
    const ctx = {
      id: "willtech-general-visual", options: { enabled: true },
      app: { platform: "desktop", version: "2.2.6" }, signal: controller.signal,
      sessions: { current: () => props.session },
      layout: { state: () => visible() ? "visible" : "closed", toggle() {} },
      add(registry, value) { registrations.push({ registry, value }); },
    };
    // host do test-gui.js: owner/scope internos; setup/render rodam no escopo raiz
    window.__under(target, () => module.exports.default.setup(ctx));
    const panel = registrations.find((item) => item.registry === "Panel").value;
    const node = window.__under(target, () => panel.render(props));
    document.getElementById("preview").replaceChildren(node);
    let clock = 100;
    return {
      node,
      emit(type, id, created) {
        const at = created ?? ++clock;
        listeners.get(type)?.forEach((handler) => handler({ type, created: at, data: { sessionID: id } }));
        return at;
      },
      state(id) { return node.querySelector(`[data-agent="willtech-${id}"]`)?.dataset.state; },
      label(id) { return node.querySelector(`[data-agent="willtech-${id}"] .wt-state`)?.textContent; },
      image(id) { return node.querySelector(`[data-agent="willtech-${id}"] img`); },
      listeners: () => [...listeners.values()].reduce((sum, group) => sum + group.size, 0),
      dispose() { controller.abort(); window.__dispose(target); },
    };
  }
  async function waitImages(node) {
    for (const image of node.querySelectorAll("img")) {
      if (image.complete && image.naturalWidth > 0) continue;
      await new Promise((resolve, reject) => {
        const done = (fn) => () => { clearTimeout(timer); image.removeEventListener("load", ok); image.removeEventListener("error", bad); fn(); };
        const ok = done(resolve);
        const bad = done(() => reject(new Error("imagem não carregou")));
        const timer = setTimeout(bad, 5000);
        image.addEventListener("load", ok, { once: true });
        image.addEventListener("error", bad, { once: true });
      });
    }
  }
  function frameSampler(image) {
    const canvas = document.createElement("canvas");
    canvas.width = 48; canvas.height = 48;
    const ctx2 = canvas.getContext("2d");
    return () => { ctx2.clearRect(0, 0, 48, 48); ctx2.drawImage(image, 0, 0, 48, 48); return canvas.toDataURL(); };
  }

  window.runSmoke = async () => {
    if (window.smokeRunning || window.smokeResults) throw new Error("rodada única");
    window.smokeRunning = true;
    const EXPECTED = window.__EXPECTED_HASHES;
    const passed = [];
    const check = (cond, name) => { if (!cond) throw new Error(name); passed.push(name); };
    let f;
    try {
      if (window.__REDUCED) {
        f = fixture();
        await waitImages(f.node);
        f.emit("session.execution.started", "general");
        await tick();
        check(await sha(f.image("general").src) === EXPECTED["willtech-general"],
          "reduced-motion: General working usa WebP estático");
        check(f.node.dataset.motion === "off", "reduced-motion: animação desligada");
        f.dispose();
        check(window.__mediaRemoved > 0, "reduced-motion: listener de media removido no cleanup");
        window.smokeResults = { status: "PASS", tests: passed.length, passed, mode: "reduced-motion", simulation: true, nativeHomologation: "NÃO TESTADA" };
        document.getElementById("result").textContent = `${passed.length} verificações reduced-motion aprovadas.`;
        return window.smokeResults;
      }
      f = fixture();
      window.__smokeFixture = f;
      await waitImages(f.node);
      check(f.node.querySelectorAll("img").length === 7 &&
        [...f.node.querySelectorAll("img")].every((i) => i.naturalWidth > 0),
        "1. sete personagens carregados");
      for (const name of names) {
        check(await sha(f.image(name).src) === EXPECTED[`willtech-${name}`],
          `2. willtech-${name} associado à imagem original correta`);
        check(f.state(name) === "waiting" && f.label(name) === "Aguardando", `4. willtech-${name} aguardando`);
      }
      for (const name of names.slice(1)) {
        f.emit("session.execution.started", name);
        await tick();
        check(f.state(name) === "working", `4. ${name} executando`);
        f.emit("session.execution.succeeded", name);
        await tick();
        check(f.state(name) === "completed" && f.label(name) === "Concluído", `4. ${name} concluído`);
        f.emit("session.execution.failed", name);
        await tick();
        check(f.state(name) === "error" && f.label(name) === "Erro", `4. ${name} erro`);
        f.emit("session.execution.interrupted", name);
        await tick();
        check(f.state(name) === "blocked" && f.label(name) === "Interrompido", `4. ${name} cancelado/interrompido`);
        check(f.state("general") === "waiting", `5. evento de ${name} não altera o General`);
      }
      f.emit("session.execution.started", "general");
      await tick();
      check(f.state("general") === "working", "5. General reage ao próprio evento de execução");
      check(await sha(f.image("general").src) === EXPECTED.generalAnimated, "3. General working usa o APNG original");
      const sample = frameSampler(f.image("general"));
      const frames = [sample()];
      for (let i = 0; i < 3; i++) { await sleep(450); frames.push(sample()); }
      const liveAdvanced = frames.some((a, i) => frames.some((b, j) => i < j && a !== b));
      // Prova determinística do avanço: decodifica o APNG em uso via WebCodecs.
      // Navegadores automatizados podem suprimir o playback ao vivo de imagens
      // animadas; nesse caso o canvas fica estático mesmo com a animação ativa.
      const buf = await (await fetch(f.image("general").src)).arrayBuffer();
      const decoder = new ImageDecoder({ data: buf, type: "image/apng" });
      await decoder.completed;
      const draw = (frame) => {
        const cv = document.createElement("canvas");
        cv.width = frame.displayWidth; cv.height = frame.displayHeight;
        const cx = cv.getContext("2d", { willReadFrequently: true });
        cx.drawImage(frame, 0, 0);
        return cx.getImageData(0, 0, cv.width, cv.height).data;
      };
      const d0 = draw((await decoder.decode({ frameIndex: 0 })).image);
      const frameCount = decoder.tracks.selectedTrack.frameCount;
      const dN = draw((await decoder.decode({ frameIndex: Math.min(9, frameCount - 1) })).image);
      let pixelDiff = 0;
      for (let i = 0; i < d0.length; i += 97) if (d0[i] !== dN[i]) pixelDiff++;
      decoder.close();
      check(frameCount > 1 && pixelDiff > 0,
        "3. APNG avança entre quadros (WebCodecs: quadro 0 difere do quadro 9)");
      const advanced = liveAdvanced || pixelDiff > 0;
      const control = frameSampler(f.image("explorador"));
      const c0 = control();
      await sleep(450);
      check(c0 === control(), "3. controle estático não muda (WebP sem animação)");
      const grid = f.node.querySelector(".wt-grid");
      // Registros são entregues ao callback no checkpoint de microtasks e a
      // fila é esvaziada; takeRecords() após await devolveria sempre 0.
      let mutations = 0;
      const observer = new MutationObserver((records) => { mutations += records.length; });
      observer.observe(grid, { subtree: true, childList: true, attributes: true, characterData: true });
      const drain = async () => { const before = mutations; await tick(); await tick(); return mutations - before; };
      const at = f.emit("session.execution.started", "explorador", 5000);
      check(await drain() > 0, "6. evento válido produz atualização");
      f.emit("session.execution.started", "explorador", at);
      check(await drain() === 0, "6. evento idêntico não produz atualização duplicada");
      f.emit("session.execution.succeeded", "explorador", at);
      check(await drain() > 0, "6. evento distinto no mesmo ms é aceito");
      observer.disconnect();
      f.node.querySelector("button").click();
      await tick();
      check(f.node.dataset.motion === "off" &&
        await sha(f.image("general").src) === EXPECTED["willtech-general"],
        "8. pausa usa fallback estático");
      f.node.querySelector("button").click();
      await tick();
      check(await sha(f.image("general").src) === EXPECTED.generalAnimated, "8. retomada restaura APNG");
      f.dispose();
      await tick();
      check(f.listeners() === 0, "7. encerramento remove todos os listeners");
      check(f.node.dataset.motion === "off", "7. encerramento congela animações");
      for (const name of names) {
        check(await sha(f.image(name).src) === EXPECTED[`willtech-${name}`], `7. ${name} volta ao estático no unmount`);
      }
      let postUnmount = 0;
      const after = new MutationObserver((records) => { postUnmount += records.length; });
      after.observe(grid, { subtree: true, childList: true, attributes: true, characterData: true });
      f.emit("session.execution.started", "general");
      await tick(); await tick();
      check(postUnmount === 0, "7. nenhum evento processado após o unmount");
      after.disconnect();
      window.smokeResults = {
        status: "PASS", tests: passed.length, passed, framesAdvanced: advanced,
        livePaintingAdvanced: liveAdvanced, decoderFrameCount: frameCount,
        decoderPixelDiff: pixelDiff,
        livePaintingNote: liveAdvanced ? "playback ao vivo observado"
          : "playback ao vivo suprimido pelo navegador automatizado; avanço provado por decodificação WebCodecs do APNG em uso",
        frameSamples: frames.length, mode: "full", simulation: true, nativeHomologation: "NÃO TESTADA",
      };
      document.getElementById("result").textContent =
        `${passed.length} verificações smoke aprovadas; APNG avançou quadros: ${advanced} ` +
        `(ao vivo: ${liveAdvanced}; WebCodecs: ${frameCount} quadros, diff ${pixelDiff}).\n` +
        "Homologação OpenCode Desktop: NÃO TESTADA.";
      return window.smokeResults;
    } catch (error) {
      window.smokeResults = { status: "FAIL", tests: passed.length, error: error.message, simulation: true };
      document.getElementById("result").textContent = JSON.stringify(window.smokeResults);
      return window.smokeResults;
    }
  };
  window.addEventListener("load", async () => {
    for (let i = 0; i < 300 && !window.__EXPECTED_HASHES; i++) await sleep(100);
    if (window.__EXPECTED_HASHES) window.runSmoke();
    else document.getElementById("result").textContent = "aguardando hashes esperados (injeção do harness)";
  });
})();