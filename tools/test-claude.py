#!/usr/bin/env python3
"""Testes determinísticos do Mod Claude Code (sem modelo, sem rede)."""
import base64
import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MOD = ROOT / "claude/plugins/willtech-visual"
CANON = ROOT / "opencode/plugins/willtech/visual/activity.cjs"
NAMES = ["general", "explorador", "pesquisador", "visual", "executor", "testador", "revisor"]


class ClaudeModTests(unittest.TestCase):
    def test_shared_core_no_drift(self):
        core = CANON.read_text(encoding="utf-8")
        marker = "module.exports = { AGENTS, EVENTS, projectAgents };"
        body = core.rstrip()[: -len(marker)]
        esm = (MOD / "hooks/activity.js").read_text(encoding="utf-8")
        self.assertIn(body, esm)
        self.assertTrue(esm.rstrip().endswith("export { AGENTS, EVENTS, projectAgents };"))

    def test_reproducible_core(self):
        # Reprodutibilidade do nucleo ESM (copia do activity.cjs canonico):
        # portavel, sem sips — verificada em macOS, Linux e Windows.
        spec = importlib.util.spec_from_file_location("build_claude", ROOT / "tools/build-claude.py")
        build = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(build)
        before = (MOD / "hooks" / "activity.js").read_bytes()
        build.build_core()
        self.assertEqual(before, (MOD / "hooks" / "activity.js").read_bytes())

    @unittest.skipUnless(sys.platform == "darwin",
                         "rebuild de imagens usa sips (ferramenta macOS); "
                         "reprodutibilidade integral validada no job macos-latest")
    def test_reproducible_build(self):
        spec = importlib.util.spec_from_file_location("build_claude", ROOT / "tools/build-claude.py")
        build = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(build)
        before = {p.name: p.read_bytes() for p in (MOD / "hooks").glob("*.js")}
        before["icon.png"] = (MOD / ".claude-plugin/icon.png").read_bytes()
        build.main()
        after = {p.name: p.read_bytes() for p in (MOD / "hooks").glob("*.js")}
        after["icon.png"] = (MOD / ".claude-plugin/icon.png").read_bytes()
        self.assertEqual(before, after)

    def test_assets_and_svg_limits(self):
        assets = (MOD / "hooks/assets.js").read_text(encoding="utf-8")
        png = json.loads(re.search(r"export const PNG = (\{.*?\});\n", assets, re.S).group(1))
        frames = json.loads(re.search(r"export const FRAMES = (\{.*?\});\n", assets, re.S).group(1))
        self.assertEqual(sorted(png), sorted(f"willtech-{n}" for n in NAMES))
        for key, value in png.items():
            raw = base64.b64decode(value)
            self.assertEqual(raw[:8], b"\x89PNG\r\n\x1a\n")
            self.assertLess(len(value) + 400, 131072, f"Svg {key} acima do limite")
            self.assertEqual(len(frames[key]), 4)
            for frame in frames[key]:
                self.assertEqual(base64.b64decode(frame)[:8], b"\x89PNG\r\n\x1a\n")

    def test_observation_only_and_fail_open(self):
        source = (MOD / "hooks/register.js").read_text(encoding="utf-8")
        self.assertNotIn("$.model.complete", source)
        self.assertNotIn("$.agent.spawn", source)
        self.assertNotRegex(source, r"\b(setInterval|fetch|XMLHttpRequest|eval)\s*\(")
        self.assertEqual(source.count(".catch(($, e, next) => next(e))"), 2)
        manifest = json.loads((MOD / ".claude-plugin/plugin.json").read_text())
        self.assertEqual(manifest["license"], "MIT")
        self.assertIsInstance(manifest["author"], dict)
        hooks = json.loads((MOD / "hooks/hooks.json").read_text())
        self.assertEqual(hooks["modules"], ["./register.js"])


if __name__ == "__main__":
    unittest.main()