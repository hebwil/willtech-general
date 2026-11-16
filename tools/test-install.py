#!/usr/bin/env python3
import copy
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SH = (ROOT / "tools/willtech-install.sh").read_text(encoding="utf-8")
PS1 = (ROOT / "tools/willtech-install.ps1").read_text(encoding="utf-8")
HELPERS = {
    "sh": next(code for code in re.findall(r"<<'PY'\n(.*?)\nPY", SH, re.S)
               if "mode, target, template, root" in code),
    "ps1-helper": re.search(r"\$code = @'\n(.*?)\n'@", PS1, re.S).group(1),
}
TARGETS = (".claude/settings.json", ".codex/hooks.json",
           ".opencode/plugins/willtech/index.js")
AUX = ("tools/willtech-auto.py", "tools/willtech-dossie.py",
       "tools/willtech-drift.py", "claude-code/bin/willtech_trace.py")
TEMPLATE = ROOT / "claude-code/settings/willtech-hooks.json"
PLUGIN = ROOT / "opencode/plugins/willtech/index.js"
USER_HOOK = {"type": "command", "command": "echo willtech-auto.py documentation"}


def run(args, inp=None):
    return subprocess.run([str(arg) for arg in args], input=inp,
                          capture_output=True, text=True, cwd=ROOT, timeout=20)


def json_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def json_read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def snapshot(repo):
    return {str(path.relative_to(repo)): path.read_bytes()
            for path in repo.rglob("*") if path.is_file()}


def handlers(data):
    return [hook for groups in data.get("hooks", {}).values()
            for group in groups for hook in group.get("hooks", [])]


class InstallerTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / ".willtech"
        parent.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="install-tests-", dir=parent)
        self.base = Path(self.temp.name)
        self.count = 0

    def tearDown(self):
        self.temp.cleanup()

    def repo(self, name=None):
        self.count += 1
        repo = self.base / (name or f"repo-{self.count}")
        for rel in AUX:
            dest = repo / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / rel, dest)
        for rel in ("tools/user.py", "claude-code/user.txt",
                    ".willtech/user.json", ".willtech/dossie.jsonl",
                    ".opencode/plugins/third-party/index.js"):
            path = repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"third-party content\n")
        return repo

    def wrapper(self, repo, *args, inp=None):
        return run(["sh", ROOT / "tools/willtech-install.sh", "--repo", repo,
                    *args], inp)

    def helper(self, platform, mode, target, repo, template=TEMPLATE,
               exe="python", prefix="@none"):
        args = [mode, str(target), str(template)]
        args += [str(repo)] if platform == "sh" else [exe, prefix, str(repo)]
        return run([sys.executable, "-", *args], HELPERS[platform])

    def ok(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def preserved(self, repo, before):
        for rel, content in before.items():
            self.assertTrue((repo / rel).is_file(), rel)
            self.assertEqual((repo / rel).read_bytes(), content, rel)

    def test_source_syntax_and_helper_parity(self):
        self.ok(run(["sh", "-n", ROOT / "tools/willtech-install.sh"]))
        for name, code in HELPERS.items():
            compile(code, name, "exec")
        unix = HELPERS["sh"].split("def read_json", 1)[1]
        windows = HELPERS["ps1-helper"].split("def read_json", 1)[1]
        windows = re.sub(r"def adapt\(h\):.*?    return h\n\n", "", windows, flags=re.S)
        windows = "\n".join(line for line in windows.split("\n")
                            if not line.strip().startswith("groups = {event:"))
        self.assertEqual(unix, windows)
        self.assertIn("$code | & $exe @pre - $mode $target $template $exe $prefix $Repo", PS1)
        self.assertIn("$OutputEncoding = [System.Text.UTF8Encoding]::new($false)", PS1)
        self.assertIn("Get-Item -LiteralPath $path", PS1)
        self.assertNotIn("-Recurse", PS1)

    def test_consent_refusal(self):
        repo = self.repo()
        before = snapshot(repo)
        self.ok(self.wrapper(repo, inp="n\n"))
        self.assertEqual(snapshot(repo), before)
        self.ok(self.wrapper(repo, "--yes"))
        installed = snapshot(repo)
        self.ok(self.wrapper(repo, "--uninstall", inp="n\n"))
        self.assertEqual(snapshot(repo), installed)

    def test_shell_complete_lifecycle_and_backups(self):
        repo = self.repo()
        json_write(repo / TARGETS[0], {"user": 1, "hooks": {
            "SessionStart": [{"hooks": [USER_HOOK]}]}})
        json_write(repo / TARGETS[1], {"customSetting": "keep", "hooks": None})
        plugin = repo / TARGETS[2]
        plugin.parent.mkdir(parents=True)
        plugin.write_bytes(b"original third-party plugin\n")
        empty = repo / ".opencode/plugins/preexisting-empty"
        empty.mkdir()
        before = snapshot(repo)
        self.ok(self.wrapper(repo, "--yes"))
        installed = snapshot(repo)
        self.ok(self.wrapper(repo, "--yes"))
        self.assertEqual(snapshot(repo), installed)
        for rel in TARGETS:
            self.assertEqual((repo / (rel + ".willtech-bak")).read_bytes(), before[rel])
        self.ok(self.wrapper(repo, "--disable"))
        disabled = snapshot(repo)
        self.assertEqual(disabled, {k: v for k, v in installed.items()
                                   if k != ".willtech/enabled"})
        self.ok(self.wrapper(repo, "--enable"))
        self.assertEqual(snapshot(repo), installed)
        self.ok(self.wrapper(repo, "--uninstall", "--yes"))
        self.assertEqual(snapshot(repo), before)
        self.assertTrue(empty.is_dir())

    def test_created_components_reinstall_and_removal(self):
        repo = self.repo()
        before = snapshot(repo)
        self.ok(self.wrapper(repo, "--yes"))
        self.ok(self.wrapper(repo, "--yes"))
        for rel in TARGETS:
            self.assertTrue((repo / (rel + ".willtech-created")).is_file())
            self.assertFalse((repo / (rel + ".willtech-bak")).exists())
        dirs = [path for path in repo.rglob("*") if path.is_dir()]
        self.ok(self.wrapper(repo, "--uninstall", "--yes"))
        self.assertEqual(snapshot(repo), before)
        for directory in dirs:
            self.assertTrue(directory.is_dir())

    def test_unregistered_components_are_preserved(self):
        repo = self.repo()
        for rel in TARGETS[:2]:
            json_write(repo / rel, {"hooks": {"Stop": [{"hooks": [USER_HOOK]}]}, "user": 1})
        plugin = repo / TARGETS[2]
        plugin.parent.mkdir(parents=True)
        plugin.write_bytes(b"unregistered plugin\n")
        before = snapshot(repo)
        self.ok(self.wrapper(repo, "--uninstall", "--yes"))
        self.assertEqual(snapshot(repo), before)

    def test_postinstall_settings_and_hooks_are_preserved(self):
        for platform in HELPERS:
            for existing in (False, True):
                with self.subTest(platform=platform, existing=existing):
                    repo = self.repo()
                    target = repo / TARGETS[0]
                    if existing:
                        json_write(target, {"userOriginal": 1})
                    original = target.read_bytes() if existing else None
                    self.ok(self.helper(platform, "install", target, repo))
                    data = json_read(target)
                    event = next(iter(data["hooks"]))
                    group = data["hooks"][event][0]
                    metadata = {k: v for k, v in group.items() if k != "hooks"}
                    group["hooks"].append(USER_HOOK)
                    data["hooks"]["ExternalEvent"] = [{"hooks": [USER_HOOK]}]
                    data["newSetting"] = "Ação"
                    if existing:
                        data["userOriginal"] = 2
                    json_write(target, data)
                    self.ok(self.helper(platform, "uninstall", target, repo, "-"))
                    expected = {"hooks": {
                        event: [dict(metadata, hooks=[USER_HOOK])],
                        "ExternalEvent": [{"hooks": [USER_HOOK]}]}, "newSetting": "Ação"}
                    if existing:
                        expected["userOriginal"] = 2
                        self.assertEqual(Path(str(target) + ".willtech-bak").read_bytes(), original)
                    self.assertEqual(json_read(target), expected)
                    self.assertFalse(Path(str(target) + ".willtech-managed.json").exists())
                    self.assertFalse(Path(str(target) + ".willtech-created").exists())

    def test_identical_and_similar_unmanaged_hooks_survive(self):
        for platform in HELPERS:
            with self.subTest(platform=platform):
                repo = self.repo()
                target = repo / TARGETS[0]
                self.ok(self.helper(platform, "install", target, repo))
                generated = json_read(target)
                self.ok(self.helper(platform, "uninstall", target, repo, "-"))
                event = next(iter(generated["hooks"]))
                original_group = copy.deepcopy(generated["hooks"][event][0])
                original_group["hooks"].append(USER_HOOK)
                original = {"hooks": {event: [original_group]}, "user": 1}
                json_write(target, original)
                self.ok(self.helper(platform, "install", target, repo))
                current = json_read(target)
                current["newSetting"] = "keep"
                json_write(target, current)
                self.ok(self.helper(platform, "uninstall", target, repo, "-"))
                self.assertEqual(json_read(target), dict(original, newSetting="keep"))

    def test_group_metadata_distinguishes_foreign_hooks(self):
        for platform in HELPERS:
            with self.subTest(platform=platform):
                repo = self.repo()
                target = repo / TARGETS[0]
                self.ok(self.helper(platform, "install", target, repo))
                data = json_read(target)
                event = next(iter(data["hooks"]))
                foreign = copy.deepcopy(data["hooks"][event][0])
                foreign["userMetadata"] = "not owned"
                data["hooks"][event].append(foreign)
                json_write(target, data)
                self.ok(self.helper(platform, "uninstall", target, repo, "-"))
                self.assertEqual(json_read(target), {"hooks": {event: [foreign]}})

    def test_plugins_backup_restore_and_user_modifications(self):
        for platform in HELPERS:
            for changed in (False, True):
                with self.subTest(platform=platform, changed=changed):
                    repo = self.repo()
                    target = repo / TARGETS[2]
                    target.parent.mkdir(parents=True)
                    original = b"original plugin\n"
                    target.write_bytes(original)
                    self.ok(self.helper(platform, "install", target, repo, PLUGIN))
                    self.ok(self.helper(platform, "install", target, repo, PLUGIN))
                    backup = Path(str(target) + ".willtech-bak")
                    self.assertEqual(backup.read_bytes(), original)
                    if changed:
                        target.write_bytes(b"user-modified plugin\n")
                        before = snapshot(repo)
                        self.ok(self.helper(platform, "uninstall", target, repo, "-"))
                        self.assertEqual(snapshot(repo), before)
                        self.ok(self.helper(platform, "install", target, repo, PLUGIN))
                        self.assertEqual(snapshot(repo), before)
                    else:
                        self.ok(self.helper(platform, "uninstall", target, repo, "-"))
                        self.assertEqual(target.read_bytes(), original)
                        self.assertFalse(backup.exists())

    def test_no_hooks_null_hooks_empty_events_and_bom_restore(self):
        for platform in HELPERS:
            for data in ({"user": 1}, {"hooks": None, "user": 1},
                         {"hooks": {"Empty": []}, "user": 1}):
                with self.subTest(platform=platform, data=data):
                    repo = self.repo()
                    target = repo / TARGETS[0]
                    target.parent.mkdir(parents=True)
                    original = b"\xef\xbb\xbf" + json.dumps(data, indent=4).encode("utf-8") + b"\n"
                    target.write_bytes(original)
                    self.ok(self.helper(platform, "install", target, repo))
                    self.ok(self.helper(platform, "uninstall", target, repo, "-"))
                    self.assertEqual(target.read_bytes(), original)

    def test_shell_unicode_spaces_quotes_and_platform_selection(self):
        repo = self.repo('Projeto "Ação"')
        before = snapshot(repo)
        self.ok(self.wrapper(repo, "--yes", "--platform", "codex"))
        self.assertEqual(json_read(repo / ".willtech/installed.json")["repo"], str(repo))
        self.assertFalse((repo / TARGETS[0]).exists())
        self.assertFalse((repo / TARGETS[2]).exists())
        self.ok(self.wrapper(repo, "--uninstall", "--yes", "--platform", "codex"))
        self.assertEqual(snapshot(repo), before)

    def test_ps1_launcher_sentinel_py3_and_unicode(self):
        for exe, prefix in (("python", "@none"), ("py", "-3")):
            for rel, template in ((TARGETS[0], TEMPLATE), (TARGETS[1], ROOT / "codex/hooks.json")):
                with self.subTest(exe=exe, rel=rel):
                    repo = self.repo(f"Projeto Ação {self.count + 1}")
                    target = repo / rel
                    self.ok(self.helper("ps1-helper", "install", target, repo, template, exe, prefix))
                    hooks = handlers(json_read(target))
                    for hook in hooks:
                        self.assertNotIn("@none", json.dumps(hook))
                        if rel == TARGETS[0]:
                            self.assertEqual(hook["command"], exe)
                            self.assertEqual(hook["args"][:1], ["-3"] if prefix == "-3" else ["${CLAUDE_PROJECT_DIR}/tools/willtech-auto.py"])
                        else:
                            self.assertIn(str(repo) + "/tools/willtech-auto.py", hook["command"])
                            self.assertEqual(" -3 " in hook["command"], prefix == "-3")
                    self.ok(self.helper("ps1-helper", "uninstall", target, repo, "-", exe, prefix))
                    self.assertFalse(target.exists())

    def test_symlink_components_and_sidecars_refused(self):
        for platform in HELPERS:
            for component in ("target", ".willtech-bak", ".willtech-created", ".willtech-managed.json"):
                with self.subTest(platform=platform, component=component):
                    repo = self.repo()
                    target = repo / TARGETS[0]
                    target.parent.mkdir(parents=True)
                    external = self.base / f"external-{self.count}.json"
                    external.write_bytes(b"{}\n")
                    link = target if component == "target" else Path(str(target) + component)
                    link.symlink_to(external)
                    result = self.helper(platform, "install", target, repo)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(external.read_bytes(), b"{}\n")
                    self.assertTrue(link.is_symlink())
        repo = self.repo()
        outside = self.base / "outside"
        outside.mkdir()
        (repo / ".claude").symlink_to(outside, target_is_directory=True)
        self.assertNotEqual(self.helper("sh", "install", repo / TARGETS[0], repo).returncode, 0)
        self.assertEqual(list(outside.iterdir()), [])

    def test_activation_not_written_on_failure_or_state_symlink(self):
        repo = self.repo()
        target = repo / TARGETS[0]
        target.parent.mkdir(parents=True)
        target.write_bytes(b"invalid JSON\n")
        before = snapshot(repo)
        self.assertNotEqual(self.wrapper(repo, "--yes").returncode, 0)
        self.assertEqual(snapshot(repo), before)
        state = repo / ".willtech"
        outside = self.base / "external-state"
        state.rename(outside)
        state.symlink_to(outside, target_is_directory=True)
        external_before = snapshot(outside)
        for mode in ("--yes", "--disable", "--uninstall"):
            self.assertNotEqual(self.wrapper(repo, mode, "--yes").returncode, 0)
            self.assertEqual(snapshot(outside), external_before)

    def test_legacy_backups_are_not_adopted_or_deleted(self):
        for platform in HELPERS:
            for sidecar in (".willtech-bak", ".willtech-created"):
                with self.subTest(platform=platform, sidecar=sidecar):
                    repo = self.repo()
                    target = repo / TARGETS[0]
                    json_write(target, {"user": 1})
                    Path(str(target) + sidecar).write_bytes(b"preserve legacy backup\n")
                    before = snapshot(repo)
                    self.assertNotEqual(self.helper(platform, "install", target, repo).returncode, 0)
                    self.assertEqual(snapshot(repo), before)
                    self.ok(self.helper(platform, "uninstall", target, repo, "-"))
                    self.assertEqual(snapshot(repo), before)

    def test_documentation_and_identity_integrity(self):
        protected = ["docs/assets", "LICENSE", "NOTICE.md", "opencode",
                     "codex/agents", "codex/hooks.json", "claude-code/agents",
                     "claude-code/settings", *AUX]
        self.ok(run(["git", "diff", "--exit-code", "origin/main", "--", *protected]))
        original = run(["git", "show", "origin/main:README.md"])
        self.ok(original)
        current = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"<[^>]+>", current), re.findall(r"<[^>]+>", original.stdout))
        marker = "## Desenvolvimento e licença"
        self.assertEqual(current.split(marker)[1], original.stdout.split(marker)[1])
        for name in ("README.md", "INSTALL.md", "EVOLUCAO.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            for target in re.findall(r"\]\(([^)]+)\)", text):
                if "://" not in target and not target.startswith("#"):
                    self.assertTrue((ROOT / target.split("#")[0]).exists(), (name, target))
        diff = run(["git", "diff", "--unified=0", "origin/main", "--",
                    "README.md", "INSTALL.md", "EVOLUCAO.md",
                    "tools/willtech-install.sh", "tools/willtech-install.ps1"])
        self.ok(diff)
        added = "\n".join(line for line in diff.stdout.splitlines()
                          if line.startswith("+") and not line.startswith("+++"))
        self.assertNotIn("/Users/", added)
        self.assertNotIn("/Applications/", added)
        self.assertIn("permission.rejected", current)
        self.ok(run(["git", "diff", "--check"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)

# WillTech-General / WILLTECH-BH © 2026 · autoria: github.com/hebwil
