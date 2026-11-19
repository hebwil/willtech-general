#!/usr/bin/env python3
"""Validação dos 4 Cenários de Resolução de Interpretador Python (WillTech 3.1.2):
- Cenário A: macOS com PATH mínimo do Finder/launchd (/usr/bin:/bin)
- Cenário B: Ausência de Python compatível (>= 3.12) -> fail-safe / código 2
- Cenário C: Funcionamento normal (descoberta automática, installed.json, Sala v3)
- Cenário D: Integridade multiplataforma e ausência de caminhos hardcoded
"""
import glob
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def find_node():
    n = shutil.which("node")
    if n:
        return n
    candidates = [
        "/usr/local/bin/node",
        "/opt/homebrew/bin/node",
    ] + glob.glob("/Users/*/.local/node/*/bin/node") + glob.glob(str(Path.home() / ".local/node/*/bin/node"))
    for c in candidates:
        if os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None


def find_py312():
    if sys.version_info >= (3, 12):
        return sys.executable
    candidates = [
        shutil.which("python3.12"),
        shutil.which("python3.13"),
        "/opt/homebrew/bin/python3.12",
        "/usr/local/bin/python3.12",
        str(Path.home() / ".local/bin/python3.12"),
    ] + glob.glob(str(Path.home() / ".local/share/uv/python/*/bin/python3"))
    for c in candidates:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            try:
                res = subprocess.run([c, "-c", "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)"],
                                     capture_output=True)
                if res.returncode == 0:
                    return c
            except Exception:
                pass
    return sys.executable


BASH_BIN = shutil.which("bash") or "/bin/bash"
NODE_BIN = find_node()
PY312_BIN = find_py312()


class PythonResolverScenarioTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="willtech-resolver-test-")
        self.temp = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_scenario_a_macos_finder_path_resolution(self):
        """Cenário A: Em ambiente macOS com PATH mínimo do Finder/launchd,
        o plugin do OpenCode descobre autonomamente o Python >= 3.12 e executa
        willtech-auto.py com sucesso, sem SyntaxError."""
        if not NODE_BIN:
            self.skipTest("Node.js não encontrado no ambiente para teste do plugin")

        fake_home = self.temp / "fake_home"
        fake_home.mkdir()

        # Cria binário ~/.local/bin/python3.12 apontando para Python real >= 3.12
        local_bin = fake_home / ".local" / "bin"
        local_bin.mkdir(parents=True)
        py_target = local_bin / "python3.12"
        os.symlink(PY312_BIN, py_target)

        # Prepara teste em Node.js (módulo ESM)
        test_mjs = self.temp / "run_plugin_test.mjs"
        plugin_url = (ROOT / "opencode/plugins/willtech/index.js").as_uri()
        test_mjs.write_text(f"""
import plugin from {json.dumps(plugin_url)};

async function main() {{
    const toolHooks = {{}};
    const sessionHooks = {{}};
    const fakeCtx = {{
        location: {{ directory: {json.dumps(str(ROOT))} }},
        tool: {{ hook: (name, fn) => {{ toolHooks[name] = fn; }} }},
        session: {{ hook: (name, fn) => {{ sessionHooks[name] = fn; }} }},
        event: {{ subscribe: () => (async function*() {{}})() }}
    }};

    await plugin.setup(fakeCtx);

    const hook = toolHooks['execute.before'];
    if (!hook) {{
        console.error("Hook execute.before não registrado");
        process.exit(1);
    }}

    // Executa comando bash (gatilho do willtech-auto.py)
    await hook({{ id: "call_1", tool: "bash", input: {{ command: "echo ok" }} }}, {{ sessionID: "ses_1" }});
    console.log("EXECUTE_BEFORE_SUCCESS");
}}
main().catch(err => {{
    console.error(err);
    process.exit(1);
}});
""", encoding="utf-8")

        # PATH restrito do Finder do macOS: /usr/bin:/bin:/usr/sbin:/sbin
        finder_env = {
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
            "HOME": str(fake_home),
            "TMPDIR": str(self.temp),
        }

        proc = subprocess.run(
            [NODE_BIN, str(test_mjs)],
            cwd=str(ROOT),
            env=finder_env,
            capture_output=True,
            text=True
        )
        self.assertEqual(proc.returncode, 0, f"Node plugin falhou: {proc.stderr}")
        self.assertIn("EXECUTE_BEFORE_SUCCESS", proc.stdout)
        self.assertNotIn("SyntaxError", proc.stderr)

    def test_scenario_b_no_compatible_python(self):
        """Cenário B: Ausência de Python >= 3.12:
        1. Instalador sh recusa com saída código 2 e mensagem clara.
        2. willtech-auto.py falha com código 1 e mensagem de versão sem quebrar sintaxe.
        3. Plugin falha aberto com segurança sem lançar erro não tratado."""
        # 1. Teste do instalador sem Python compatível
        isolated_bin = self.temp / "isolated_bin"
        isolated_bin.mkdir()
        fake_home = self.temp / "empty_home"
        fake_home.mkdir()

        # Cria um python3 mock que simula Python 3.9 (falha na checagem >= 3.12)
        mock_py = isolated_bin / "python3"
        mock_py.write_text("""#!/bin/sh
if [ "$1" = "--version" ]; then
    echo "Python 3.9.6"
    exit 0
fi
if [ "$1" = "-c" ]; then
    # Checagem sys.version_info >= (3, 12) retorna código 1
    exit 1
fi
echo "Mock Python 3.9.6 invocado" >&2
exit 1
""", encoding="utf-8")
        mock_py.chmod(mock_py.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        dest_repo = self.temp / "dest_repo"
        shutil.copytree(str(ROOT / "tools"), str(dest_repo / "tools"))
        subprocess.run(["git", "init"], cwd=str(dest_repo), capture_output=True)

        env_no_py = {
            "PATH": f"{isolated_bin}:/bin:/usr/bin",
            "HOME": str(fake_home),
        }
        res_inst = subprocess.run(
            [BASH_BIN, str(ROOT / "tools/willtech-install.sh"), "--repo", str(dest_repo), "--platform", "all", "--yes"],
            env=env_no_py,
            capture_output=True,
            text=True
        )
        self.assertEqual(res_inst.returncode, 2, f"Instalador deveria recusar com código 2 (stdout={res_inst.stdout}, stderr={res_inst.stderr})")
        self.assertIn("Python >= 3.12 não encontrado", res_inst.stderr)
        self.assertFalse((dest_repo / ".willtech/enabled").exists(), "enabled não deve ser criado")

        # 2. Teste de willtech-auto.py sob Python < 3.12 (se /usr/bin/python3 for < 3.12)
        if os.path.exists("/usr/bin/python3"):
            py_ver = subprocess.run(["/usr/bin/python3", "-c", "import sys; print(sys.version_info[:2])"],
                                    capture_output=True, text=True).stdout.strip()
            if "3, 9" in py_ver or "3, 10" in py_ver or "3, 11" in py_ver:
                res_auto = subprocess.run(
                    ["/usr/bin/python3", str(ROOT / "tools/willtech-auto.py"), "opencode"],
                    input="{}",
                    capture_output=True,
                    text=True
                )
                self.assertEqual(res_auto.returncode, 1)
                self.assertIn("Python >= 3.12 é obrigatório", res_auto.stderr)
                self.assertNotIn("SyntaxError", res_auto.stderr)

        # 3. Teste do plugin em modo fail-open quando nenhum Python existe
        if NODE_BIN:
            test_mjs = self.temp / "test_failopen.mjs"
            plugin_url = (ROOT / "opencode/plugins/willtech/index.js").as_uri()
            test_mjs.write_text(f"""
import plugin from {json.dumps(plugin_url)};

async function main() {{
    const toolHooks = {{}};
    const fakeCtx = {{
        location: {{ directory: {json.dumps(str(self.temp))} }},
        tool: {{ hook: (name, fn) => {{ toolHooks[name] = fn; }} }},
        session: {{ hook: () => {{}} }},
        event: {{ subscribe: () => (async function*() {{}})() }}
    }};
    await plugin.setup(fakeCtx);
    const hook = toolHooks['execute.before'];
    // Sem Python compatível, a execução não deve lançar exceção fatal
    await hook({{ id: "call_1", tool: "bash", input: {{ command: "ls" }} }}, {{ sessionID: "s" }});
    console.log("FAILOPEN_SUCCESS");
}}
main().catch(err => {{
    console.error(err);
    process.exit(1);
}});
""", encoding="utf-8")
            res_failopen = subprocess.run(
                [NODE_BIN, str(test_mjs)],
                cwd=str(self.temp),
                env={"PATH": "/nonexistent", "HOME": str(fake_home)},
                capture_output=True,
                text=True
            )
            self.assertEqual(res_failopen.returncode, 0, f"Failopen falhou: {res_failopen.stderr}")
            self.assertIn("FAILOPEN_SUCCESS", res_failopen.stdout)

    def test_scenario_c_normal_operation(self):
        """Cenário C: Instalação e execução normais com Python >= 3.12:
        - instalador gera installed.json com campo 'python'
        - plugin executa willtech-auto.py e integra normalmente."""
        dest_repo = self.temp / "valid_project"
        shutil.copytree(str(ROOT / "tools"), str(dest_repo / "tools"))
        subprocess.run(["git", "init"], cwd=str(dest_repo), capture_output=True)

        res_inst = subprocess.run(
            [BASH_BIN, str(ROOT / "tools/willtech-install.sh"), "--repo", str(dest_repo), "--platform", "all", "--yes"],
            cwd=str(ROOT),
            capture_output=True,
            text=True
        )
        self.assertEqual(res_inst.returncode, 0, f"Instalação falhou: stdout={res_inst.stdout}, stderr={res_inst.stderr}")
        installed_json = json.loads((dest_repo / ".willtech/installed.json").read_text(encoding="utf-8"))
        self.assertIn("python", installed_json)
        self.assertTrue(os.path.exists(installed_json["python"]))

        # Executa willtech-auto.py usando o python detectado
        auto_proc = subprocess.run(
            [installed_json["python"], str(ROOT / "tools/willtech-auto.py"), "opencode"],
            input=json.dumps({"action": "permission", "tool": "read_file", "input": {"path": "README.md"}}),
            capture_output=True,
            text=True
        )
        self.assertEqual(auto_proc.returncode, 0)
        out = json.loads(auto_proc.stdout)
        self.assertIn("block", out)
        self.assertFalse(out["block"])

    def test_scenario_d_cross_platform_and_cleanliness(self):
        """Cenário D: Integridade multiplataforma e ausência de caminhos hardcoded."""
        # 1. Verifica ausência de referências a máquinas de desenvolvimento nos scripts
        sensitive = ["/Users/will", "/Applications/OpenCode.app", "C:\\Users\\"]
        checked_files = [
            ROOT / "tools/willtech-auto.py",
            ROOT / "opencode/plugins/willtech/index.js",
            ROOT / "tools/willtech-install.sh",
            ROOT / "tools/willtech-install.ps1",
        ]
        for f in checked_files:
            content = f.read_text(encoding="utf-8")
            for term in sensitive:
                self.assertNotIn(term, content, f"Caminho indevido {term} encontrado em {f.name}")

        # 2. Testa override via WILLTECH_PYTHON se Node estiver disponível
        if NODE_BIN:
            override_env = os.environ.copy()
            override_env["WILLTECH_PYTHON"] = PY312_BIN
            test_mjs = self.temp / "test_override.mjs"
            plugin_url = (ROOT / "opencode/plugins/willtech/index.js").as_uri()
            test_mjs.write_text(f"""
import plugin from {json.dumps(plugin_url)};

async function main() {{
    const toolHooks = {{}};
    const fakeCtx = {{
        location: {{ directory: {json.dumps(str(ROOT))} }},
        tool: {{ hook: (name, fn) => {{ toolHooks[name] = fn; }} }},
        session: {{ hook: () => {{}} }},
        event: {{ subscribe: () => (async function*() {{}})() }}
    }};
    await plugin.setup(fakeCtx);
    const hook = toolHooks['execute.before'];
    await hook({{ id: "call_ov", tool: "bash", input: {{ command: "echo override" }} }}, {{ sessionID: "s" }});
    console.log("OVERRIDE_OK");
}}
main().catch(err => {{
    console.error(err);
    process.exit(1);
}});
""", encoding="utf-8")
            res_ov = subprocess.run(
                [NODE_BIN, str(test_mjs)],
                cwd=str(ROOT),
                env=override_env,
                capture_output=True,
                text=True
            )
            self.assertEqual(res_ov.returncode, 0, f"Override falhou: {res_ov.stderr}")
            self.assertIn("OVERRIDE_OK", res_ov.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
