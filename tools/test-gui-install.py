#!/usr/bin/env python3
"""Teste da distribuição/ativação GUI WillTech em fixtures DESCARTÁVEIS.
Nunca toca a configuração pessoal: todo alvo é um opencode.json temporário.
Cobre instalação, atualização idempotente, disable/enable, uninstall reversível,
preservação de plugins/ajustes de terceiros e portabilidade do caminho do pacote.
"""
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("willtech_gui", ROOT / "tools/willtech-gui.py")
gui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gui)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


class GuiInstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.config = os.path.join(self.tmp.name, "opencode.json")
        self.addCleanup(self.tmp.cleanup)

    def willtech_entries(self, data):
        return [p for p in data.get("plugins", []) if gui.is_willtech(p)]

    def test_install_creates_entry(self):
        gui.install(self.config)
        data = read(self.config)
        entries = self.willtech_entries(data)
        self.assertEqual(len(entries), 1)
        self.assertTrue(entries[0]["options"]["enabled"])
        self.assertEqual(os.path.realpath(entries[0]["package"]), gui.PACKAGE)
        self.assertTrue(os.path.isfile(self.config + ".willtech-gui-managed.json"))

    def test_install_preserves_third_party(self):
        original = {"model": "glm-4.6", "plugins": ["superpowers@latest", {"package": "/other/plugin", "options": {"x": 1}}], "mcp": {"keep": True}}
        with open(self.config, "w", encoding="utf-8") as fh:
            json.dump(original, fh)
        gui.install(self.config)
        data = read(self.config)
        self.assertEqual(data["model"], "glm-4.6")
        self.assertEqual(data["mcp"], {"keep": True})
        self.assertIn("superpowers@latest", data["plugins"])
        self.assertIn({"package": "/other/plugin", "options": {"x": 1}}, data["plugins"])
        self.assertEqual(len(self.willtech_entries(data)), 1)
        self.assertTrue(os.path.isfile(self.config + ".willtech-gui-bak"))

    def test_update_idempotent(self):
        with open(self.config, "w", encoding="utf-8") as fh:
            json.dump({"plugins": ["third-party@1"]}, fh)
        gui.install(self.config)
        gui.install(self.config)
        data = read(self.config)
        self.assertEqual(len(self.willtech_entries(data)), 1)
        self.assertIn("third-party@1", data["plugins"])

    def test_disable_enable(self):
        gui.install(self.config)
        gui.set_enabled(self.config, False)
        self.assertFalse(self.willtech_entries(read(self.config))[0]["options"]["enabled"])
        gui.set_enabled(self.config, True)
        self.assertTrue(self.willtech_entries(read(self.config))[0]["options"]["enabled"])

    def test_uninstall_restores_backup(self):
        original = {"model": "keep", "plugins": ["third-party@1"]}
        with open(self.config, "w", encoding="utf-8") as fh:
            json.dump(original, fh)
        gui.install(self.config)
        gui.uninstall(self.config)
        self.assertEqual(read(self.config), original)
        self.assertFalse(os.path.isfile(self.config + ".willtech-gui-managed.json"))
        self.assertFalse(os.path.isfile(self.config + ".willtech-gui-bak"))

    def test_uninstall_preserves_user_changes(self):
        with open(self.config, "w", encoding="utf-8") as fh:
            json.dump({"plugins": ["third-party@1"]}, fh)
        gui.install(self.config)
        data = read(self.config)
        data["model"] = "user-added-later"
        data["plugins"].append("user-plugin@2")
        with open(self.config, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        gui.uninstall(self.config)
        result = read(self.config)
        self.assertEqual(result["model"], "user-added-later")
        self.assertIn("user-plugin@2", result["plugins"])
        self.assertIn("third-party@1", result["plugins"])
        self.assertEqual(len(self.willtech_entries(result)), 0)
        self.assertTrue(os.path.isfile(self.config + ".willtech-gui-bak"))

    def test_uninstall_without_registry_preserves(self):
        with open(self.config, "w", encoding="utf-8") as fh:
            json.dump({"plugins": ["third-party@1"]}, fh)
        gui.uninstall(self.config)
        self.assertEqual(read(self.config), {"plugins": ["third-party@1"]})

    def test_portable_package_path(self):
        # O caminho do pacote deriva da localização do arquivo, não de um absoluto
        # pessoal fixo. Em qualquer máquina, aponta para o visual deste checkout.
        expected = os.path.realpath(os.path.join(str(ROOT), "opencode", "plugins", "willtech", "visual"))
        self.assertEqual(gui.PACKAGE, expected)
        gui.install(self.config)
        entry = self.willtech_entries(read(self.config))[0]
        self.assertEqual(os.path.realpath(entry["package"]), expected)
        source = (ROOT / "tools/willtech-gui.py").read_text(encoding="utf-8")
        self.assertNotIn("/Users/will", source)

    def test_symlink_refused(self):
        real = os.path.join(self.tmp.name, "real.json")
        with open(real, "w", encoding="utf-8") as fh:
            json.dump({}, fh)
        link = os.path.join(self.tmp.name, "link.json")
        os.symlink(real, link)
        with self.assertRaises(SystemExit):
            gui.install(link)


if __name__ == "__main__":
    unittest.main(verbosity=2)