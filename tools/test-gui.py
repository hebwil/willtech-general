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
# Baseline de orquestração: cf1c8b8, que incorpora a correção REAL e autorizada
# do instalador Windows (willtech-install.ps1: "${Platform}:" em vez de
# "$Platform:" — ParserError genuíno do PowerShell 5.1, comprovado no job
# windows-latest; ordem mestra: "corrija somente falhas reais e comprovadas").
# O pin anterior (475943a, baseline 3.0 aprovada com as correções do PR #13 e a
# evolução legítima da 3.0) antecedia essa correção e falhava no HEAD. A
# proteção cobre IDENTIDADE e ORQUESTRAÇÃO (assets, licença, créditos, núcleo
# de automação, agents/hooks de automação, installers). Os subdiretórios
# VISUAIS (codex/willtech-visual, claude/plugins/willtech-visual) são alvo
# legítimo de correção da missão multiplataforma e ficam fora deste guard.
BASE = "cf1c8b8"


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
                     "opencode/plugins/willtech/index.js", "codex/agents", "codex/hooks.json", "claude-code/settings",
                     "tools/willtech-auto.py", "tools/willtech-install.sh"]
        changed = subprocess.check_output(["git", "diff", "--name-only", BASE, "--", *protected], cwd=ROOT, text=True)
        self.assertEqual(changed, "")
        # A única alteração permitida no PS1 desde BASE corrige o parser
        # PowerShell 5.1: '$Platform:' é interpretado como variável inválida.
        # Conferimos o ARQUIVO INTEIRO, sem abrir exceção genérica ao guard.
        baseline_ps1 = subprocess.check_output(
            ["git", "show", f"{BASE}:tools/willtech-install.ps1"], cwd=ROOT, text=True
        )
        parser_bug = "plataforma $Platform: handlers"
        parser_fix = "plataforma ${Platform}: handlers"
        self.assertEqual(baseline_ps1.count(parser_bug), 1)
        self.assertEqual(
            (ROOT / "tools/willtech-install.ps1").read_text(),
            baseline_ps1.replace(parser_bug, parser_fix),
        )
        before = subprocess.check_output(["git", "show", f"{BASE}:README.md"], cwd=ROOT, text=True)
        after = (ROOT / "README.md").read_text()
        self.assertEqual(re.findall(r'<[^>]+>', before), re.findall(r'<[^>]+>', after))
        self.assertEqual(before[before.index("## Créditos e referências"):], after[after.index("## Créditos e referências"):])


if __name__ == "__main__":
    unittest.main(verbosity=2)
