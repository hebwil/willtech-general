#!/usr/bin/env python3
"""Testes determinísticos do visualizador complementar Codex (sem modelo/rede).
Cobre: núcleo compartilhado sem drift, mapeamento dos hooks oficiais, mapeamento
das notificações do App Server, limites de assets, formato oficial de hooks.json
e caráter somente-observação. O teste de protocolo real (test-appserver.py) é
separado e só roda quando um binário descartável do Codex está disponível.
"""
import importlib.util
import json
import os
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(os.path.dirname(ROOT))
NODE = "/Users/will/Library/Application Support/Codex/artifact-sessions/runtime-generations/generation-9FoqEE/runtime/bin/node"
NAMES = ["general", "explorador", "pesquisador", "visual", "executor", "testador", "revisor"]


def load_bridge():
    spec = importlib.util.spec_from_file_location("bridge", os.path.join(ROOT, "hooks", "willtech_bridge.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def node_eval(script):
    out = subprocess.run([NODE, "-e", script], capture_output=True, text=True, cwd=ROOT)
    if out.returncode != 0:
        raise AssertionError(out.stderr)
    return json.loads(out.stdout)


class TestCodex(unittest.TestCase):
    def test_shared_core_no_drift(self):
        with open(os.path.join(REPO, "opencode", "plugins", "willtech", "visual", "activity.cjs"), encoding="utf-8") as fh:
            canonical = fh.read().replace("module.exports = { AGENTS, EVENTS, projectAgents };", "").rstrip()
        with open(os.path.join(ROOT, "viewer", "core.js"), encoding="utf-8") as fh:
            core = fh.read()
        self.assertIn(canonical, core)
        self.assertIn("export { AGENTS, EVENTS, projectAgents };", core)

    def test_bridge_maps_official_hooks(self):
        bridge = load_bridge()
        for name in NAMES:
            start = bridge.normalize({"hook_event_name": "SubagentStart", "agent_type": f"willtech-{name}", "agent_id": f"s-{name}", "session_id": "main"})
            self.assertEqual(start["agent"], f"willtech-{name}")
            self.assertEqual(start["state"], "working")
            stop = bridge.normalize({"hook_event_name": "SubagentStop", "agent_type": name, "agent_id": f"s-{name}"})
            self.assertEqual(stop["state"], "completed")
        self.assertEqual(bridge.normalize({"hook_event_name": "SessionStart"})["state"], "waiting")
        self.assertEqual(bridge.normalize({"hook_event_name": "Stop"})["state"], "completed")
        self.assertEqual(bridge.normalize({"hook_event_name": "Interrupt"})["state"], "blocked")
        perm = bridge.normalize({"hook_event_name": "PermissionRequest"})
        self.assertEqual(perm["state"], "blocked")
        self.assertTrue(perm["permissions"])
        self.assertTrue(bridge.normalize({"hook_event_name": "SessionEnd"})["reset"])
        self.assertIsNone(bridge.normalize({"hook_event_name": "PreCompact"}))

    def test_appserver_maps_notifications(self):
        script = (
            "const {mapNotification}=require('./appserver/client.cjs');"
            "const out=["
            "mapNotification('turn/started',{threadId:'t'}),"
            "mapNotification('turn/completed',{threadId:'t'}),"
            "mapNotification('turn/completed',{threadId:'t',aborted:true}),"
            "mapNotification('turn/completed',{threadId:'t',status:'failed'}),"
            "mapNotification('thread/status/changed',{status:'running'}),"
            "mapNotification('thread/status/changed',{status:'idle'}),"
            "mapNotification('item/started',{})];"
            "console.log(JSON.stringify(out.map(r=>r&&r.state)));"
        )
        states = node_eval(script)
        self.assertEqual(states, ["working", "completed", "blocked", "error", "working", "waiting", None])

    def test_assets_and_exports(self):
        with open(os.path.join(ROOT, "viewer", "assets.js"), encoding="utf-8") as fh:
            assets = fh.read()
        for name in NAMES:
            self.assertIn(f'"willtech-{name}": "data:image/webp;base64,', assets)
        with open(os.path.join(ROOT, "viewer", "app.js"), encoding="utf-8") as fh:
            app = fh.read()
        self.assertIn("prefers-reduced-motion", app)
        self.assertIn("wt-breathe", app)
        with open(os.path.join(ROOT, "viewer", "index.html"), encoding="utf-8") as fh:
            html = fh.read()
        self.assertIn("NÃO É PAINEL NATIVO DO CODEX", html)
        self.assertIn("prefers-reduced-motion", html)

    def test_hooks_json_official_format(self):
        with open(os.path.join(ROOT, "hooks", "hooks.json"), encoding="utf-8") as fh:
            doc = json.load(fh)
        self.assertIn("hooks", doc)
        for event in ["SessionStart", "SubagentStart", "SubagentStop", "Stop", "Interrupt", "PermissionRequest"]:
            self.assertIn(event, doc["hooks"])
            entry = doc["hooks"][event][0]["hooks"][0]
            self.assertEqual(entry["type"], "command")
            self.assertTrue(entry.get("async"))
            self.assertIn("willtech_bridge.py", entry["command"])

    def test_observation_only_no_ai_no_external_network(self):
        for rel in ["hooks/willtech_bridge.py", "appserver/client.cjs", "viewer/server.cjs", "viewer/app.js"]:
            with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
                text = fh.read()
            for bad in ["model.complete", "api.openai.com", "https://", "http://", "fetch(\"http", "child_process.exec("]:
                self.assertNotIn(bad, text, f"{rel} contém {bad}")


if __name__ == "__main__":
    unittest.main()