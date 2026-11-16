const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const packagePath = path.join(root, "opencode/plugins/willtech/visual");
const activity = require(path.join(packagePath, "activity.cjs"));
const Panel = Symbol("Panel");
const handlers = new Map();
const cleanups = [];
let panel;
let revisions = 0;
const element = () => ({
  dataset: {},
  style: { setProperty() {} },
  setAttribute() {},
  append() {},
});
const data = {
  session: { family: () => ["root", "general"] },
  on(type, handler) {
    handlers.set(type, handler);
    return () => handlers.delete(type);
  },
};
const sdk = {
  Plugin: { define: definition => definition },
  Panel,
  Command: Symbol("Command"),
  Style: Symbol("Style"),
  createKeyed: (source, callback) => callback(source()),
};
const solid = {
  createEffect() {},
  createSignal(value) {
    return [() => value, update => {
      value = typeof update === "function" ? update(value) : update;
      revisions++;
    }];
  },
  onCleanup: callback => cleanups.push(callback),
};
const context = {
  module: { exports: {} },
  document: { createElement: element },
  window: { matchMedia: () => ({ matches: false, addEventListener() {}, removeEventListener() {} }) },
  require(name) {
    if (name === "@opencode/plugin/gui") return sdk;
    if (name === "solid-js") return solid;
    if (name === "./activity.cjs") return activity;
    if (name === "./assets.cjs") return {};
    throw new Error("Unexpected module: " + name);
  },
};
const filename = process.argv[2] === "--bundle" ? "gui-experimental.cjs" : "gui-source.cjs";
vm.runInNewContext(fs.readFileSync(path.join(packagePath, filename), "utf8"), context, { filename });
context.module.exports.default.setup({
  options: { enabled: true },
  app: { platform: "desktop", version: "2.2.6" },
  add: (type, contribution) => { if (type === Panel) panel = contribution; },
});
assert.ok(panel);
panel.render({ session: { id: "root", key: "root", server: { data, connected: true, compatible: true } } });
assert.equal(handlers.size, 4);
const emit = (type, created, sessionID = "general") => handlers.get(type)({ type, created, data: { sessionID } });
emit("session.execution.started", 100);
assert.equal(revisions, 1);
emit("session.execution.started", 100);
assert.equal(revisions, 1, "Identical execution event must not trigger a second revision");
emit("session.execution.succeeded", 100);
assert.equal(revisions, 2, "Distinct terminal event in the same millisecond must be accepted");
emit("session.execution.failed", 99);
assert.equal(revisions, 2, "Older execution event must be ignored");
emit("session.execution.started", 101, "unrelated");
assert.equal(revisions, 2, "Unrelated session must be ignored");
cleanups.forEach(cleanup => cleanup());
assert.equal(handlers.size, 0, "Event subscriptions must be removed on cleanup");
console.log("PASS: headless event regression (simulated SDK, not native GUI), " + filename);
