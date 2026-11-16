#!/usr/bin/env python3
"""Homologação real WillTech 2.3 — correção dos 7 defeitos (P1 P2 P4 P6 N1 N2 N3).

Suíte determinística, sem modelo, sem rede, sem segredos reais: apenas
fixtures descartáveis. Cada classe cobre um defeito confirmado nas rodadas
de homologação funcional. Protocolo RED->FIX->GREEN->EDGE: esta suíte falha
no código anterior pela causa correta e passa após a correção.

Uso: python3 tools/test-homolog.py   (exit 0 = tudo passou)
"""
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PY = sys.executable
DOSSIE_TOOL = HERE / "willtech-dossie.py"
REPOMAP_TOOL = HERE / "willtech-repomap.py"
AUTO_TOOL = HERE / "willtech-auto.py"
INSTALL_SH = HERE / "willtech-install.sh"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run(*args, inp=None, cwd=None):
    return subprocess.run([str(a) for a in args], input=inp,
                          capture_output=True, text=True, cwd=cwd, timeout=60)


def dossie(*args, inp=None):
    return run(PY, DOSSIE_TOOL, *args, inp=inp)


def repomap(*args):
    return run(PY, REPOMAP_TOOL, *args)


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def init_repo(path):
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q")
    git(path, "config", "user.email", "lab@example.com")
    git(path, "config", "user.name", "lab")
    return path


def commit(repo, msg="base"):
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", msg)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


SENSITIVE = [".env-teste", "subdir/.env-teste", "config.env", "app.env",
             "secrets.txt", "credentials.json", ".envrc"]
PROTECTED = [".env", ".env.local", ".env.production", ".zsh_history",
             ".bash_history", ".ssh/id_rsa", ".aws/credentials"]
LEGIT = ["README.md", "src/main.py", "saida.txt", "docs/nota.md"]
SYNTH = "SYNTHETIC-NAO-E-SEGREDO-REAL-123456"


class Lab(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="willtech-homolog-")
        self.base = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def write(self, rel, content=SYNTH + "\n"):
        p = self.base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return p


class P1CredentialPaths(Lab):
    def test_add_rejects_all_seven_sensitive(self):
        d = self.base / "d.jsonl"
        for rel in SENSITIVE:
            self.write(rel)
            r = dossie("add", d, "--agent", "x", "--kind", "finding",
                       "--summary", "s", "--path", self.base / rel)
            self.assertEqual(r.returncode, 2, f"{rel}: {r.stdout}{r.stderr}")
        self.assertFalse(d.exists(), "dossiê criado despite recusa")

    def test_add_still_rejects_protected(self):
        d = self.base / "d.jsonl"
        for rel in PROTECTED:
            self.write(rel)
            r = dossie("add", d, "--agent", "x", "--kind", "finding",
                       "--summary", "s", "--path", self.base / rel)
            self.assertEqual(r.returncode, 2, rel)

    def test_add_accepts_legitimate(self):
        d = self.base / "d.jsonl"
        for rel in LEGIT:
            self.write(rel, "conteudo legitimo\n")
            r = dossie("add", d, "--agent", "x", "--kind", "finding",
                       "--summary", "s", "--path", self.base / rel)
            self.assertEqual(r.returncode, 0, f"{rel}: {r.stdout}{r.stderr}")

    def test_output_file_and_evidence_routes(self):
        d = self.base / "d.jsonl"
        self.write("secrets.txt")
        self.write("config.env")
        self.write(".env-teste")
        self.write("app.env")
        r = dossie("add", d, "--agent", "x", "--kind", "test", "--summary", "s",
                   "--output-file", self.base / "secrets.txt")
        self.assertEqual(r.returncode, 2, "add --output-file sensível aceito")
        r = dossie("learn", d, "--key", "k", "--resolution", "r", "--command", "c",
                   "--output-file", self.base / "config.env", "--repo", self.base)
        self.assertEqual(r.returncode, 2, "learn --output-file sensível aceito")
        r = dossie("resolve", d, "--id", "f", "--action", "fix", "--note", "n",
                   "--output-file", self.base / ".env-teste")
        self.assertEqual(r.returncode, 2, "resolve --output-file sensível aceito")
        cache = self.base / "cache.json"
        r = dossie("cache-put", self.base, cache, "--map-file", self.base / "app.env")
        self.assertEqual(r.returncode, 2, "cache-put --map-file sensível aceito")
        self.assertFalse(cache.exists(), "cache gravou conteúdo sensível")

    def test_no_synthetic_content_leak(self):
        d = self.base / "d.jsonl"
        for rel in SENSITIVE:
            self.write(rel)
            dossie("add", d, "--agent", "x", "--kind", "finding",
                   "--summary", "s", "--path", self.base / rel)
        if d.exists():
            self.assertNotIn(SYNTH, d.read_text(encoding="utf-8"))

    def test_policy_normalization(self):
        m = load("d", DOSSIE_TOOL)
        for p in ("subdir\\.env-teste", "C:\\repo\\config.env", "SECRETS.TXT",
                  "Credentials.Json", ".ENVRC", "sub/../.env-teste",
                  "/abs/path/app.env", ".env-teste"):
            self.assertTrue(m.is_credential_path(p), p)
        for p in ("src/main.py", "README.md", "C:\\repo\\src\\main.py",
                  "docs/nota.md", "environment.py"):
            self.assertFalse(m.is_credential_path(p), p)

    def test_repomap_never_indexes_sensitive(self):
        repo = init_repo(self.base / "repo")
        for rel in SENSITIVE + PROTECTED:
            (repo / rel).parent.mkdir(parents=True, exist_ok=True)
            (repo / rel).write_text(SYNTH + "\n", encoding="utf-8")
        (repo / "main.py").write_text("def ok():\n    return 1\n", encoding="utf-8")
        commit(repo)
        index = self.base / "index.json"
        r = repomap("update", repo, index)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        blob = index.read_text(encoding="utf-8")
        for rel in SENSITIVE + PROTECTED:
            self.assertNotIn(rel, blob, f"indexou {rel}")
        self.assertNotIn(SYNTH, blob)
        self.assertIn("main.py", blob)


class P2Classify(Lab):
    def setUp(self):
        super().setUp()
        self.m = load("d", DOSSIE_TOOL)

    def test_direct_for_simple(self):
        level, _ = self.m.classify_task("corrigir typo no README", ["README.md"])
        self.assertEqual(level, "simple")

    def test_plan_for_complex(self):
        level, _ = self.m.classify_task("refatorar arquitetura", ["a.py", "b.py", "c.py"])
        self.assertEqual(level, "complex")

    def test_critical_for_sensitive_paths(self):
        for p in (".env", ".env-teste", "secrets.txt", "credentials.json", "config.env"):
            level, _ = self.m.classify_task("ajuste", [p])
            self.assertEqual(level, "critical", p)

    def test_critical_for_text_reference(self):
        for t in ("ler secrets.txt", "corrigir .env", "ajustar subdir/.env-teste",
                  "revisar credentials.json"):
            level, _ = self.m.classify_task(t, [])
            self.assertEqual(level, "critical", t)

    def test_casual_word_not_sensitive(self):
        for t in ("adicionar secrets ao vault", "melhorar a segurança",
                  "documentar credentials management"):
            level, _ = self.m.classify_task(t, [])
            self.assertEqual(level, "simple", t)

    def test_cli_three_levels(self):
        d = self.base / "d.jsonl"
        r = dossie("plan", d, "--task", "corrigir typo", "--paths", "README.md")
        self.assertTrue(r.stdout.startswith("DIRECT"), r.stdout)
        r = dossie("plan", d, "--task", "refatorar arquitetura",
                   "--paths", "a.py,b.py,c.py")
        self.assertIn("PLAN complex", r.stdout)
        r = dossie("plan", d, "--task", "ajuste", "--paths", ".env-teste")
        self.assertIn("PLAN critical", r.stdout)
        self.assertIn("REVIEW", r.stdout)

    def test_sensitive_short_task_never_direct(self):
        d = self.base / "d.jsonl"
        r = dossie("plan", d, "--task", "ler secrets.txt")
        self.assertFalse(r.stdout.startswith("DIRECT"), r.stdout)
        self.assertIn("critical", r.stdout)

    def test_plan_does_not_persist_full_secret_path(self):
        d = self.base / "d.jsonl"
        dossie("plan", d, "--task", "ajuste", "--paths", ".env,src/main.py")
        self.assertTrue(d.exists(), "tarefa sensível não gerou plano (classificada simples)")
        entries = [json.loads(l) for l in d.read_text(encoding="utf-8").splitlines() if l.strip()]
        plans = [e for e in entries if e.get("kind") == "plan"]
        self.assertTrue(plans)
        for e in plans:
            self.assertNotIn(".env", e.get("paths", []))


class P4DepsRefs(Lab):
    def setUp(self):
        super().setUp()
        self.repo = init_repo(self.base / "repo")
        (self.repo / "pkg").mkdir()
        (self.repo / "pkg" / "__init__.py").write_text("", encoding="utf-8")
        (self.repo / "pkg" / "core.py").write_text(
            "import json\nfrom pkg import util\nfrom pkg.util import helper\n\n"
            "def run(x):\n    return helper(x)\n", encoding="utf-8")
        (self.repo / "pkg" / "util.py").write_text(
            "def helper(z):\n    return z\n", encoding="utf-8")
        (self.repo / "lib").mkdir()
        (self.repo / "lib" / "util.js").write_text(
            "function utilFn() {}\nmodule.exports = utilFn;\n", encoding="utf-8")
        (self.repo / "lib" / "thing.js").write_text(
            "export function thing() {}\n", encoding="utf-8")
        (self.repo / "app.js").write_text(
            "const util = require('./lib/util.js');\n"
            "import { thing } from './lib/thing';\nfunction main() {}\n", encoding="utf-8")
        commit(self.repo)
        self.index = self.base / "index.json"
        repomap("update", self.repo, self.index)

    def test_brief_includes_relevant_internal_deps(self):
        r = repomap("brief", self.index, "--paths", "pkg", "--max-chars", "1200")
        self.assertEqual(r.returncode, 0)
        self.assertIn("deps:", r.stdout)
        self.assertIn("pkg/util.py", r.stdout)
        self.assertNotIn("json", r.stdout.split("deps:")[1] if "deps:" in r.stdout else "")

    def test_brief_js_relative_deps(self):
        r = repomap("brief", self.index, "--paths", "app.js", "--max-chars", "1200")
        self.assertIn("lib/util.js", r.stdout)
        self.assertIn("lib/thing.js", r.stdout)

    def test_brief_respects_budget(self):
        r = repomap("brief", self.index, "--max-chars", "200")
        # +1 do newline final do print, mesma convenção de test-dossie.sh (≤21 p/ 20).
        self.assertLessEqual(len(r.stdout), 201)

    def test_refs_module_name_forms(self):
        for needle in ("util", "pkg.util", "pkg/util.py", "helper"):
            r = repomap("query", self.index, "--refs", needle)
            self.assertIn("pkg/core.py", r.stdout, f"--refs {needle}: {r.stdout}")

    def test_refs_js_forms(self):
        for needle in ("util", "lib/util.js", "thing"):
            r = repomap("query", self.index, "--refs", needle)
            self.assertIn("app.js", r.stdout, f"--refs {needle}: {r.stdout}")

    def test_refs_unknown_empty(self):
        r = repomap("query", self.index, "--refs", "modulo-inexistente-xyz")
        self.assertIn("nenhum resultado", r.stdout)

    def test_brief_no_duplicate_deps(self):
        r = repomap("brief", self.index, "--paths", "pkg/core.py", "--max-chars", "1200")
        dep_lines = [l for l in r.stdout.splitlines() if "deps:" in l]
        for l in dep_lines:
            deps = l.split("deps:")[1].strip().split(",")
            self.assertEqual(len(deps), len(set(deps)), l)


class P6Stale(Lab):
    def setUp(self):
        super().setUp()
        self.repo = init_repo(self.base / "repo")
        (self.repo / "mod.py").write_text("def alpha(x):\n    return x\n", encoding="utf-8")
        (self.repo / "other.py").write_text("import mod\n\ndef beta():\n    return mod.alpha(1)\n", encoding="utf-8")
        commit(self.repo)
        self.index = self.base / "index.json"
        repomap("update", self.repo, self.index)

    def test_query_without_repo_marks_unrevalidated(self):
        r = repomap("query", self.index, "--symbol", "alpha")
        self.assertEqual(r.returncode, 0)
        self.assertIn("NAO-REVALIDADO", r.stdout)

    def test_brief_without_repo_marks_unrevalidated(self):
        r = repomap("brief", self.index)
        self.assertIn("NAO-REVALIDADO", r.stdout)

    def test_query_repo_stale_on_change(self):
        (self.repo / "mod.py").write_text("def alpha(y):\n    return y + 1\n", encoding="utf-8")
        r = repomap("query", self.index, "--symbol", "alpha", "--repo", self.repo)
        self.assertIn("STALE", r.stdout)

    def test_query_path_repo_stale_on_change(self):
        (self.repo / "mod.py").write_text("def alpha(z):\n    return z\n", encoding="utf-8")
        r = repomap("query", self.index, "--path", "mod.py", "--repo", self.repo)
        self.assertIn("STALE", r.stdout)

    def test_query_refs_repo_stale_on_change(self):
        (self.repo / "mod.py").write_text("def alpha(w):\n    return w\n", encoding="utf-8")
        r = repomap("query", self.index, "--refs", "mod", "--repo", self.repo)
        self.assertIn("STALE", r.stdout)

    def test_query_repo_stale_on_remove(self):
        (self.repo / "mod.py").unlink()
        r = repomap("query", self.index, "--path", "mod.py", "--repo", self.repo)
        self.assertIn("STALE", r.stdout)

    def test_query_repo_stale_on_rename(self):
        (self.repo / "mod.py").rename(self.repo / "mod2.py")
        r = repomap("query", self.index, "--path", "mod.py", "--repo", self.repo)
        self.assertIn("STALE", r.stdout)

    def test_query_fresh_no_stale(self):
        r = repomap("query", self.index, "--symbol", "alpha", "--repo", self.repo)
        self.assertNotIn("STALE", r.stdout)
        self.assertNotIn("NAO-REVALIDADO", r.stdout)

    def test_isolation_preserved(self):
        other = init_repo(self.base / "other")
        (other / "x.py").write_text("x = 1\n", encoding="utf-8")
        commit(other, "outro")
        r = repomap("query", self.index, "--symbol", "alpha", "--repo", other)
        self.assertEqual(r.returncode, 2)
        self.assertIn("outro projeto", r.stdout)


class N1GoldfishEvidence(Lab):
    def setUp(self):
        super().setUp()
        self.repo = init_repo(self.base / "repo")
        (self.repo / "mod.py").write_text("a = 1\n", encoding="utf-8")
        commit(self.repo)
        (self.repo / "mod.py").write_text("a = 2\n", encoding="utf-8")
        self.d = self.base / "d.jsonl"

    def pack(self, *extra):
        return dossie("review-pack", self.d, "--repo", self.repo,
                      "--accept", "a deve valer 2", *extra)

    def test_first_review_approved(self):
        self.assertEqual(self.pack().returncode, 0)

    def test_second_without_finding_blocked(self):
        self.pack()
        r = self.pack()
        self.assertEqual(r.returncode, 3, r.stdout)

    def test_bare_flag_blocked(self):
        self.pack()
        r = self.pack("--new-finding")
        self.assertNotEqual(r.returncode, 0, "flag booleana vazia autorizou rodada")
        self.assertEqual(r.returncode, 2, r.stdout)

    def test_empty_finding_blocked(self):
        self.pack()
        r = self.pack("--new-finding", "")
        self.assertEqual(r.returncode, 2, r.stdout)

    def test_finding_without_verifiable_evidence_blocked(self):
        self.pack()
        r = self.pack("--new-finding", "algo errado em lugar nenhum")
        self.assertEqual(r.returncode, 2, r.stdout)

    def test_new_finding_with_evidence_allowed(self):
        self.pack()
        r = self.pack("--new-finding", "mod.py:2 regressao: a soma errada")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_same_finding_repetition_blocked(self):
        self.pack()
        self.pack("--new-finding", "mod.py:2 regressao: a soma errada")
        r = self.pack("--new-finding", "mod.py:2 regressao: a soma errada")
        self.assertEqual(r.returncode, 3, r.stdout)

    def test_distinct_finding_allowed(self):
        self.pack()
        self.pack("--new-finding", "mod.py:2 regressao: a soma errada")
        r = self.pack("--new-finding", "mod.py:1 outro problema distinto")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_credential_anchor_refused(self):
        (self.repo / ".env").write_text("X=1\n", encoding="utf-8")
        self.pack()
        r = self.pack("--new-finding", ".env:1 problema no arquivo")
        self.assertEqual(r.returncode, 2, r.stdout)


class N2DossierIntegrity(Lab):
    def setUp(self):
        super().setUp()
        self.auto = load("a", AUTO_TOOL)
        self.valid = json.dumps({"ts": "2026-01-01T00:00:00Z", "kind": "finding",
                                 "agent": "x", "summary": "ok"})
        self.lesson = json.dumps({"kind": "lesson", "key": "k1", "summary": "r",
                                  "command": "c", "confirmations": 1})

    def dossier(self, lines):
        p = self.base / "d.jsonl"
        p.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        return p

    def test_health_valid(self):
        entries, corrupt = self.auto.dossier_health(self.dossier([self.valid, self.valid]))
        self.assertFalse(corrupt)
        self.assertEqual(len(entries), 2)

    def test_health_total_corrupt(self):
        _, corrupt = self.auto.dossier_health(self.dossier(["lixo", "mais lixo"]))
        self.assertTrue(corrupt)

    def test_health_partial_corrupt(self):
        _, corrupt = self.auto.dossier_health(self.dossier([self.valid, "lixo", self.valid]))
        self.assertTrue(corrupt, "corrupção parcial silenciosa")

    def test_health_empty_file(self):
        entries, corrupt = self.auto.dossier_health(self.dossier([]))
        self.assertFalse(corrupt)
        self.assertEqual(entries, [])

    def test_health_absent(self):
        entries, corrupt = self.auto.dossier_health(self.base / "nao-existe.jsonl")
        self.assertFalse(corrupt)
        self.assertEqual(entries, [])

    def test_health_non_dict_json_is_corrupt(self):
        _, corrupt = self.auto.dossier_health(self.dossier([self.valid, "[1,2,3]"]))
        self.assertTrue(corrupt)

    def test_legacy_format_ok(self):
        legacy = json.dumps({"ts": "2026-01-01T00:00:00Z", "agent": "general",
                             "kind": "finding", "summary": "antigo"})
        entries, corrupt = self.auto.dossier_health(self.dossier([legacy]))
        self.assertFalse(corrupt)
        self.assertEqual(len(entries), 1)

    def test_verify_partial_signals(self):
        p = self.dossier([self.valid, "lixo", self.valid])
        r = dossie("verify", p)
        self.assertNotEqual(r.returncode, 0, "verify passou com corrupção parcial")
        self.assertIn("CORRUPT", r.stdout)

    def test_prune_preserves_original_bytes(self):
        p = self.dossier([self.valid, "lixo", self.lesson])
        before = p.read_bytes()
        r = dossie("prune", p)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(p.read_bytes(), before, "prune regravou silenciosamente")

    def test_learn_on_partial_fails_safe(self):
        p = self.dossier([self.valid, "lixo"])
        ev = self.write("ev.txt", "ok\n")
        r = dossie("learn", p, "--key", "k", "--resolution", "r", "--command", "c",
                   "--output-file", ev, "--repo", self.base)
        self.assertNotEqual(r.returncode, 0, "learn registrou sobre dossiê corrompido")

    def test_recall_partial_serves_valid_with_warning(self):
        p = self.dossier([self.lesson, "lixo"])
        r = dossie("recall", p, "--key", "k1", "--repo", self.base)
        self.assertIn("key=k1", r.stdout)
        self.assertIn("CORRUPT", r.stdout.upper())

    def test_pretool_partial_blocks(self):
        hlab = self.base / "hooks"
        (hlab / "tools").mkdir(parents=True)
        (hlab / "claude-code" / "bin").mkdir(parents=True)
        for f in ("willtech-dossie.py", "willtech-auto.py", "willtech-drift.py"):
            shutil.copy(HERE / f, hlab / "tools" / f)
        shutil.copy(ROOT / "claude-code" / "bin" / "willtech_trace.py",
                    hlab / "claude-code" / "bin" / "willtech_trace.py")
        (hlab / ".willtech").mkdir()
        (hlab / ".willtech" / "enabled").write_text("")
        (hlab / ".willtech" / "dossie.jsonl").write_text(self.valid + "\nlixo\n")
        git(hlab, "init", "-q")
        git(hlab, "config", "user.email", "l@l")
        git(hlab, "config", "user.name", "l")
        commit(hlab)
        ev = {"hook_event_name": "PreToolUse", "session_id": "s", "cwd": str(hlab),
              "tool_name": "Bash", "tool_input": {"command": "ls"}}
        r = run(PY, hlab / "tools" / "willtech-auto.py", "claude", inp=json.dumps(ev))
        out = json.loads(r.stdout) if r.stdout.strip() else {}
        denied = out.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"
        self.assertTrue(denied, f"corrupção parcial não bloqueou: {out}")


class N3InstallerLayout(Lab):
    AUX = ("tools/willtech-auto.py", "tools/willtech-dossie.py",
           "tools/willtech-drift.py", "claude-code/bin/willtech_trace.py")
    TEMPLATES = ("claude-code/settings/willtech-hooks.json", "codex/hooks.json",
                 "opencode/plugins/willtech/index.js")

    def make_repo(self):
        repo = self.base / "repo"
        for rel in self.AUX:
            dest = repo / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(ROOT / rel, dest)
        (repo / ".claude").mkdir(parents=True, exist_ok=True)
        (repo / ".claude" / "settings.json").write_text(
            '{"hooks":{"PreToolUse":[{"hooks":[{"type":"command","command":"echo user"}]}]}}',
            encoding="utf-8")
        (repo / "third-party.txt").write_text("terceiro\n", encoding="utf-8")
        return repo

    def make_src(self, omit=None, invalid=None, symlink=None):
        src = self.base / "src"
        (src / "tools").mkdir(parents=True)
        shutil.copy(INSTALL_SH, src / "tools" / "willtech-install.sh")
        for rel in self.TEMPLATES:
            if rel == omit:
                continue
            dest = src / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            if rel == symlink:
                external = self.base / "external-template"
                external.write_text((ROOT / rel).read_text(encoding="utf-8"), encoding="utf-8")
                dest.symlink_to(external)
            elif rel == invalid:
                dest.write_text("{ invalid json", encoding="utf-8")
            else:
                shutil.copy(ROOT / rel, dest)
        return src

    def install(self, src, repo, *extra, inp=None):
        return run("sh", src / "tools" / "willtech-install.sh",
                   "--repo", repo, *extra, inp=inp)

    def snapshot(self, repo):
        return {str(p.relative_to(repo)): p.read_bytes()
                for p in repo.rglob("*") if p.is_file()}

    def test_valid_layout_installs(self):
        repo = self.make_repo()
        src = self.make_src()
        r = self.install(src, repo, "--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue((repo / ".willtech" / "enabled").exists())

    def test_missing_template_precise_no_partial(self):
        repo = self.make_repo()
        src = self.make_src(omit="codex/hooks.json")
        before = self.snapshot(repo)
        r = self.install(src, repo, "--yes")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("codex/hooks.json", r.stdout + r.stderr)
        self.assertEqual(self.snapshot(repo), before, "instalação parcial por layout inválido")
        self.assertFalse((repo / ".claude" / "settings.json.willtech-bak").exists())

    def test_missing_dossie_in_target_precise(self):
        repo = self.make_repo()
        (repo / "tools" / "willtech-dossie.py").unlink()
        src = self.make_src()
        before = self.snapshot(repo)
        r = self.install(src, repo, "--yes")
        self.assertEqual(r.returncode, 2)
        self.assertIn("willtech-dossie.py", r.stdout + r.stderr)
        self.assertEqual(self.snapshot(repo), before)

    def test_invalid_json_template_no_changes(self):
        repo = self.make_repo()
        src = self.make_src(invalid="codex/hooks.json")
        before = self.snapshot(repo)
        r = self.install(src, repo, "--yes")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(self.snapshot(repo), before)

    def test_symlink_template_refused(self):
        repo = self.make_repo()
        src = self.make_src(symlink="opencode/plugins/willtech/index.js")
        before = self.snapshot(repo)
        r = self.install(src, repo, "--yes")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(self.snapshot(repo), before)

    def test_idempotent_install(self):
        repo = self.make_repo()
        src = self.make_src()
        self.install(src, repo, "--yes")
        first = self.snapshot(repo)
        r = self.install(src, repo, "--yes")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.snapshot(repo), first)

    def test_uninstall_yes_restores(self):
        repo = self.make_repo()
        src = self.make_src()
        before = self.snapshot(repo)
        self.install(src, repo, "--yes")
        r = self.install(src, repo, "--uninstall", "--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.snapshot(repo), before)

    def test_uninstall_interactive_consent(self):
        repo = self.make_repo()
        src = self.make_src()
        self.install(src, repo, "--yes")
        installed = self.snapshot(repo)
        r = self.install(src, repo, "--uninstall", inp="n\n")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.snapshot(repo), installed)

    def test_disable_enable(self):
        repo = self.make_repo()
        src = self.make_src()
        self.install(src, repo, "--yes")
        self.install(src, repo, "--disable")
        self.assertFalse((repo / ".willtech" / "enabled").exists())
        self.install(src, repo, "--enable")
        self.assertTrue((repo / ".willtech" / "enabled").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)

# WillTech-General / WILLTECH-BH © 2026 · autoria: github.com/hebwil