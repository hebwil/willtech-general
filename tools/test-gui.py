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
                     "opencode/plugins/willtech/index.js", "codex/agents", "codex/hooks.json", "claude-code/settings",
                     "tools/willtech-auto.py", "tools/willtech-install.sh", "tools/willtech-install.ps1"]
        changed = subprocess.check_output(["git", "diff", "--name-only", BASE, "--", *protected], cwd=ROOT, text=True)
        self.assertEqual(changed, "")
        before = subprocess.check_output(["git", "show", f"{BASE}:README.md"], cwd=ROOT, text=True)
        after = (ROOT / "README.md").read_text()
        self.assertEqual(re.findall(r'<[^>]+>', before), re.findall(r'<[^>]+>', after))
        self.assertEqual(before[before.index("## Créditos e referências"):], after[after.index("## Créditos e referências"):])


if __name__ == "__main__":
    unittest.main(verbosity=2)
