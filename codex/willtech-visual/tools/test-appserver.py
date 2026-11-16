#!/usr/bin/env python3
"""Teste de protocolo REAL contra um binário descartável do codex-app-server.
Sem autenticação, sem modelo, sem rede externa: apenas o handshake JSON-RPC
oficial (initialize/initialized/thread/list) sobre stdio, com CODEX_HOME isolado.
Pula automaticamente se WILLTECH_CODEX_BIN não apontar para um binário existente.
Isto valida o contrato do cliente do App Server; NÃO é homologação de sessão real
(que exigiria autenticação do proprietário e gasto de modelo).
"""
import json
import os
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = "/Users/will/Library/Application Support/Codex/artifact-sessions/runtime-generations/generation-9FoqEE/runtime/bin/node"
BIN = os.environ.get("WILLTECH_CODEX_BIN", "")


@unittest.skipUnless(BIN and os.path.exists(BIN), "WILLTECH_CODEX_BIN ausente; protocolo real não exercitado")
class TestAppServerProtocol(unittest.TestCase):
    def test_initialize_and_thread_list(self):
        home = os.path.join(ROOT, ".appserver-home")
        os.makedirs(home, exist_ok=True)
        script = (
            "const {connect}=require('./appserver/client.cjs');"
            f"const c=connect({{bin:{json.dumps(BIN)},env:{{CODEX_HOME:{json.dumps(home)}}}}});"
            "(async()=>{const init=await c.start();"
            "const list=await c.request('thread/list',{});"
            "console.log(JSON.stringify({ua:init.result.userAgent,home:init.result.codexHome,data:Array.isArray(list.result.data)}));"
            "c.close();})().catch(e=>{console.error(e.message);process.exit(1);});"
        )
        out = subprocess.run([NODE, "-e", script], capture_output=True, text=True, cwd=ROOT, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        result = json.loads(out.stdout)
        self.assertTrue(result["ua"])
        self.assertEqual(result["home"], home)
        self.assertTrue(result["data"])


if __name__ == "__main__":
    unittest.main()