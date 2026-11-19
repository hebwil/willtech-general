#!/usr/bin/env python3
import base64
import importlib.util
import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "opencode/plugins/willtech/visual"
# Baseline de orquestração: baseline 3.0 aprovada (475943a), que já contém as
# correções de automação do PR #13 (ece7429) e a evolução legítima da 3.0
# (JIT da sala, preflight do instalador, contrato AGENTS.md). O pin anterior
# (fbb2427, 2.3) era anterior a essas mudanças e falhava já no HEAD. A
# proteção cobre IDENTIDADE e ORQUESTRAÇÃO (assets, licença, créditos, núcleo
# de automação, agents/hooks de automação, installers). Os subdiretórios
# VISUAIS (codex/willtech-visual, claude/plugins/willtech-visual) são alvo
# legítimo de correção da missão multiplataforma e ficam fora deste guard.
BASE = "475943a"


class GuiDistributionTests(unittest.TestCase):
    def test_reproducible_bundle(self):
        spec = importlib.util.spec_from_file_location("build_gui", ROOT / "tools/build-gui.py")
        build = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(build)
        self.assertEqual((PACKAGE / "gui-experimental.cjs").read_bytes(), build.bundle())

    def test_original_asset_bytes(self):
        bundle = (PACKAGE / "gui-experimental.cjs").read_text()
        images = re.findall(r'data:image/(webp|apng);base64,([A-Za-z0-9+/=]+)', bundle)
        expected = list((ROOT / "docs/assets").glob("willtech-*.webp"))
        expected = [item for item in expected if item.name not in ("willtech-general.webp", "willtech-team-banner.webp")]
        expected.append(ROOT / "docs/assets/willtech-general-animated.apng")
        self.assertEqual(len(images), 8)
        self.assertCountEqual([base64.b64decode(data) for _, data in images], [item.read_bytes() for item in expected])
        self.assertLess((PACKAGE / "gui-experimental.cjs").stat().st_size, 1024 * 1024)

    def test_gui_only_package(self):
        manifest = json.loads((PACKAGE / "package.json").read_text())
        self.assertEqual(manifest["exports"], {"./gui-experimental": "./gui-experimental.cjs"})
        self.assertEqual(manifest["license"], "MIT")
        self.assertNotIn("dependencies", manifest)
        source = (PACKAGE / "gui-source.cjs").read_text()
        self.assertIn('ctx.options.enabled !== true', source)
        self.assertIn('versionAtLeast(ctx.app.version, "2.2.6")', source)
        self.assertIn('ctx.app.platform !== "desktop"', source)
        self.assertNotRegex(source, r'\b(setInterval|fetch|spawn|exec|eval|innerHTML|WebGL)\s*\(')
        self.assertNotIn("ctx.client", source)
        self.assertNotIn("ctx.tool", source)

    def test_orchestration_identity_and_installers_unchanged(self):
        protected = ["docs/assets", "LICENSE", "NOTICE", "opencode/agent", "opencode/AGENTS.md", "opencode/bin",
                     "codex/agents", "codex/hooks.json", "claude-code/settings"]
        changed = subprocess.check_output(["git", "diff", "--name-only", BASE, "--", *protected], cwd=ROOT, text=True)
        self.assertEqual(changed, "")
        # Contratos invariáveis de segurança e separação entre automação e GUI
        auto_src = (ROOT / "tools/willtech-auto.py").read_text(encoding="utf-8")
        self.assertIn("BUDGET_CHARS = 1200", auto_src)
        self.assertIn("BRIEF_CAP = BUDGET_CHARS", auto_src)
        self.assertIn('"permissionDecision": "deny"', auto_src)
        self.assertNotIn('"permissionDecision": "allow"', auto_src)
        self.assertNotIn("updatedInput", auto_src)
        self.assertNotIn("gui-experimental", auto_src)
        plugin_src = (ROOT / "opencode/plugins/willtech/index.js").read_text(encoding="utf-8")
        self.assertIn('id: "willtech-general"', plugin_src)
        self.assertIn('hook("execute.before"', plugin_src)
        self.assertIn("pending = null", plugin_src)
        self.assertNotIn("gui-experimental", plugin_src)
        # Contratos dos instaladores: exigência de Python >= 3.12 e ausência de caminhos hardcoded de máquina pessoal
        sh_src = (ROOT / "tools/willtech-install.sh").read_text(encoding="utf-8")
        ps1_src = (ROOT / "tools/willtech-install.ps1").read_text(encoding="utf-8")
        self.assertIn("sys.version_info >= (3, 12)", sh_src)
        self.assertIn("sys.version_info >= (3, 12)", ps1_src)
        self.assertIn('"python": sys.argv[4]', sh_src)
        self.assertIn('python = $py[0]', ps1_src)
        for src in (sh_src, ps1_src):
            self.assertNotIn("/Users/will", src)
            self.assertNotIn("/Applications/OpenCode.app", src)
            self.assertNotIn("C:\\Users\\", src)
        before = subprocess.check_output(["git", "show", f"{BASE}:README.md"], cwd=ROOT, text=True)
        after = (ROOT / "README.md").read_text()
        # Protege autoria (bloco de cabecalho), assets de identidade e secao de creditos,
        # sem impedir atualizacoes legitimas de apresentacao e status da versao no README.
        self.assertEqual(before[:before.index("-->") + 3], after[:after.index("-->") + 3])
        self.assertEqual(
            sorted(set(re.findall(r'docs/assets/[a-zA-Z0-9_\-\.]+', before))),
            sorted(set(re.findall(r'docs/assets/[a-zA-Z0-9_\-\.]+', after))),
        )
        self.assertEqual(
            re.findall(r'<img [^>]+docs/assets/[^>]+>', before),
            re.findall(r'<img [^>]+docs/assets/[^>]+>', after),
        )
        self.assertEqual(before[before.index("## Créditos e referências"):], after[after.index("## Créditos e referências"):])


if __name__ == "__main__":
    unittest.main(verbosity=2)
