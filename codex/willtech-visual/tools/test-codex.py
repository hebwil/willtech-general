#!/usr/bin/env python3
"""Testes determinísticos do visualizador complementar Codex (sem modelo/rede).
Cobre: núcleo compartilhado sem drift, mapeamento dos hooks oficiais, mapeamento
das notificações do App Server, limites de assets, formato oficial de hooks.json
(incl. portabilidade Windows via commandWindows/PLUGIN_ROOT), bind loopback do
servidor, reset de sessão escopado (não apaga sessões concorrentes) e caráter
somente-observação. O teste de protocolo real (test-appserver.py) é separado e só
roda quando um binário descartável do Codex está disponível.

Descoberta de Node portável: WILLTECH_NODE > node/nodejs no PATH. Os testes que
executam JS pulam com motivo explícito quando não há Node (não contam como PASS).
"""
import importlib.util
import json
import os
import shutil
import socket
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(os.path.dirname(ROOT))
NODE = os.environ.get("WILLTECH_NODE") or shutil.which("node") or shutil.which("nodejs")
NAMES = ["general", "explorador", "pesquisador", "visual", "executor", "testador", "revisor"]


def require_node():
    if not NODE:
        raise unittest.SkipTest("Node não disponível; defina WILLTECH_NODE ou instale node no PATH")


def load_bridge():
    spec = importlib.util.spec_from_file_location("bridge", os.path.join(ROOT, "hooks", "willtech_bridge.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def node_eval(script, cwd=ROOT):
    require_node()
    out = subprocess.run([NODE, "-e", script], capture_output=True, text=True, cwd=cwd)
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

    def test_hooks_windows_portable(self):
        # D3: todo handler tem commandWindows oficial (py -3), sem substituição
        # POSIX $(); o caminho usa PLUGIN_ROOT (variável oficial de plugin), não
        # uma cópia completa do WillTech no repo de trabalho. SessionEnd/Interrupt
        # respeitam o máximo oficial de 3s.
        with open(os.path.join(ROOT, "hooks", "hooks.json"), encoding="utf-8") as fh:
            doc = json.load(fh)
        for event, groups in doc["hooks"].items():
            entry = groups[0]["hooks"][0]
            win = entry.get("commandWindows")
            self.assertTrue(win, f"{event} sem commandWindows")
            self.assertIn("willtech_bridge.py", win)
            self.assertIn("py -3", win)
            self.assertIn("%PLUGIN_ROOT%", win)
            self.assertNotIn("$(", win)
            self.assertIn("${PLUGIN_ROOT}", entry["command"])
            self.assertNotIn("git rev-parse", entry["command"])
            if event in ("SessionEnd", "Interrupt"):
                self.assertLessEqual(entry.get("timeout", 1), 3, f"{event} timeout>3s (máx oficial)")
        manifest = os.path.join(ROOT, ".codex-plugin", "plugin.json")
        with open(manifest, encoding="utf-8") as fh:
            man = json.load(fh)
        self.assertEqual(man["hooks"], "./hooks/hooks.json")
        self.assertTrue(os.path.isfile(os.path.join(ROOT, "hooks", "willtech_bridge.py")))

    def test_server_binds_loopback(self):
        # D1: o servidor deve escutar SOMENTE em loopback por padrão. /history e
        # /events expõem atividade de sessões; bind em todas as interfaces vazaria
        # esses dados pela rede. Prova real via server.address() do Node.
        require_node()
        server_path = os.path.join(ROOT, "viewer", "server.cjs").replace("\\", "/")
        script = (
            f"const {{server,HOST}}=require({json.dumps(server_path)});"
            "server.listen(0,HOST,()=>{const a=server.address();"
            "console.log(JSON.stringify({host:HOST,address:a.address,family:a.family}));"
            "server.close();});"
        )
        info = node_eval(script)
        self.assertEqual(info["host"], "127.0.0.1")
        self.assertEqual(info["address"], "127.0.0.1")
        self.assertNotIn(info["address"], ("::", "0.0.0.0", "*"))

    def test_server_loopback_rejects_external(self):
        # D1 (ponta-a-ponta): sobe o CLI real e confirma que uma interface não-loopback
        # local NÃO consegue conectar, enquanto 127.0.0.1 consegue.
        require_node()
        ip = None
        try:
            for fam, _, _, _, sa in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
                if not sa[0].startswith("127."):
                    ip = sa[0]
                    break
        except OSError:
            ip = None
        if not ip:
            self.skipTest("sem interface IPv4 não-loopback para provar rejeição externa")
        with tempfile.TemporaryDirectory() as lab:
            feed = os.path.join(lab, "feed.jsonl")
            open(feed, "w").close()
            port = 8799
            proc = subprocess.Popen([NODE, os.path.join(ROOT, "viewer", "server.cjs"), str(port), feed],
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            try:
                import time
                deadline = time.time() + 5
                up = False
                while time.time() < deadline:
                    try:
                        with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                            up = True
                            break
                    except OSError:
                        time.sleep(0.1)
                self.assertTrue(up, "servidor não subiu em loopback")
                with self.assertRaises(OSError):
                    socket.create_connection((ip, port), timeout=1).close()
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                if proc.stdout:
                    proc.stdout.close()

    def test_viewer_reset_scoped(self):
        # D2: SessionEnd de uma sessão NÃO pode apagar sessões concorrentes ativas.
        # Dirige o app.js REAL num harness DOM descartável (cópia verbatim).
        require_node()
        with tempfile.TemporaryDirectory() as lab:
            for name in ("core.js", "assets.js", "app.js"):
                shutil.copyfile(os.path.join(ROOT, "viewer", name), os.path.join(lab, name))
            with open(os.path.join(lab, "package.json"), "w", encoding="utf-8") as fh:
                fh.write('{"type":"module"}')
            harness = r"""
function el(){return {className:"",dataset:{},style:{setProperty(){}},classList:{add(){}},append(){},addEventListener(){},textContent:"",width:0,height:0,src:"",alt:""};}
const grid=el(); grid.replaceChildren=function(...k){this.kids=k;};
const root=el(); const motion=el();
globalThis.document={getElementById:(id)=>id==="grid"?grid:id==="root"?root:motion,createElement:()=>el()};
globalThis.window={matchMedia:()=>({matches:false,addEventListener(){},removeEventListener(){}}),addEventListener(){},__LAB_NO_SSE:true};
await import("./app.js");
const W=globalThis.window; const row=(r,id)=>r.find(x=>x.id===id);
W.__applyEvents([
  {agent:"willtech-general",state:"working",session:"main",event:"UserPromptSubmit",at:1},
  {agent:"willtech-explorador",state:"working",session:"s-exp",event:"SubagentStart",at:2},
  {agent:"willtech-general",state:"working",session:"mainB",event:"UserPromptSubmit",at:3},
]);
const rows=W.__applyEvents([{agent:"willtech-general",state:"waiting",session:"main",event:"SessionEnd",at:4,reset:true}]);
console.log(JSON.stringify({explorer:row(rows,"willtech-explorador").state, sessions:W.__state().sessions, observations:W.__state().observations}));
"""
            hp = os.path.join(lab, "harness.mjs")
            with open(hp, "w", encoding="utf-8") as fh:
                fh.write(harness)
            out = subprocess.run([NODE, hp], capture_output=True, text=True, cwd=lab)
            if out.returncode != 0:
                raise AssertionError(out.stderr)
            res = json.loads(out.stdout)
            self.assertEqual(res["explorer"], "working", "SessionEnd apagou sessão ativa concorrente")
            self.assertEqual(res["sessions"], 2, "sessões concorrentes não preservadas")

    def test_bridge_runs_via_plugin_root(self):
        # Produto INSTALADO: num repositório de trabalho descartável SEM cópia do
        # WillTech (sem tools/, sem codex/), o comando real do hook resolve o bridge
        # via PLUGIN_ROOT (variável oficial de plugin) e produz o feed. Prova que a
        # execução não presume Bash do proprietário nem checkout completo no repo.
        if os.name != "posix":
            self.skipTest("execução do command Unix requer shell POSIX; Windows nativo via commandWindows (limitação registrada)")
        with open(os.path.join(ROOT, "hooks", "hooks.json"), encoding="utf-8") as fh:
            command = json.load(fh)["hooks"]["SessionStart"][0]["hooks"][0]["command"]
        with tempfile.TemporaryDirectory() as work:
            feed = os.path.join(work, "feed.jsonl")
            env = dict(os.environ, PLUGIN_ROOT=ROOT, WILLTECH_CODEX_FEED=feed)
            payload = json.dumps({"hook_event_name": "SessionStart", "session_id": "s1", "cwd": work})
            out = subprocess.run(command, shell=True, executable="/bin/sh", env=env,
                                 input=payload, capture_output=True, text=True, cwd=work)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertTrue(os.path.isfile(feed), "feed não produzido via PLUGIN_ROOT")
            with open(feed, encoding="utf-8") as fh:
                record = json.loads(fh.readline())
            self.assertEqual(record["agent"], "willtech-general")
            self.assertEqual(record["state"], "waiting")

    def test_server_history_replay_and_sse(self):
        # Eventos: /history replaya o feed completo (reinício do visualizador) e
        # /events (SSE) entrega novas linhas ao vivo. Prova real com o CLI servidor.
        require_node()
        import time
        import urllib.request
        with tempfile.TemporaryDirectory() as lab:
            feed = os.path.join(lab, "feed.jsonl")
            with open(feed, "w", encoding="utf-8") as fh:
                fh.write(json.dumps({"agent": "willtech-general", "state": "working", "session": "m", "at": 1}) + "\n")
                fh.write(json.dumps({"agent": "willtech-explorador", "state": "working", "session": "s", "at": 2}) + "\n")
            port = 8801
            proc = subprocess.Popen([NODE, os.path.join(ROOT, "viewer", "server.cjs"), str(port), feed],
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            try:
                base = f"http://127.0.0.1:{port}"
                deadline = time.time() + 5
                history = None
                while time.time() < deadline:
                    try:
                        with urllib.request.urlopen(base + "/history", timeout=1) as res:
                            history = json.loads(res.read().decode("utf-8"))
                        break
                    except OSError:
                        time.sleep(0.1)
                self.assertIsNotNone(history, "servidor não subiu")
                self.assertEqual(len(history), 2, "history não replaya o feed completo")
                # SSE: anexa um 3º evento e confirma entrega ao vivo.
                with urllib.request.urlopen(base + "/events", timeout=5) as stream:
                    time.sleep(0.4)
                    with open(feed, "a", encoding="utf-8") as fh:
                        fh.write(json.dumps({"agent": "willtech-revisor", "state": "completed", "session": "s", "at": 3}) + "\n")
                    delivered = None
                    end = time.time() + 4
                    while time.time() < end:
                        line = stream.readline().decode("utf-8").strip()
                        if line.startswith("data:"):
                            payload = json.loads(line[len("data:"):].strip())
                            if payload.get("agent") == "willtech-revisor":
                                delivered = payload
                                break
                    self.assertIsNotNone(delivered, "SSE não entregou o novo evento")
                    self.assertEqual(delivered["state"], "completed")
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                if proc.stdout:
                    proc.stdout.close()

    def test_observation_only_no_ai_no_external_network(self):
        for rel in ["hooks/willtech_bridge.py", "appserver/client.cjs", "viewer/server.cjs", "viewer/app.js"]:
            with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
                text = fh.read()
            for bad in ["model.complete", "api.openai.com", "https://", "http://", "fetch(\"http", "child_process.exec("]:
                self.assertNotIn(bad, text, f"{rel} contém {bad}")


if __name__ == "__main__":
    unittest.main()