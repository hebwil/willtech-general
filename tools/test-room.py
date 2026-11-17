#!/usr/bin/env python3
"""Testes determinísticos da Sala dos Agentes (WillTech 3.0, PASSO 1-2).

Sem modelo, sem rede: diretórios temporários descartáveis. Cobre: init
idempotente e schema versionado; put/get roundtrip; idempotência de put;
recusa de segredos (caminho e conteúdo); isolamento por projeto (exit 2);
check (integrity_check + contagens); export JSONL; lock sidecar.
PASSO 2: query JIT — budget, header QUARENTENA, neutralização de
delimitadores, filtros por especialidade/status e isolamento.

Padrão: tools/test-repomap.py (unittest, subprocess, sem estado compartilhado).
"""
import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "willtech-room.py"
AUTO = ROOT / "tools" / "willtech-auto.py"


def run(*args):
    r = subprocess.run([sys.executable, str(TOOL), *args],
                       capture_output=True, text=True)
    return r.returncode, r.stdout


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def mkrepo(base, name):
    repo = Path(base) / name
    (repo / "tools").mkdir(parents=True)
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "test")
    return repo


def load_mod(path):
    spec = importlib.util.spec_from_file_location("mod_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class RoomCoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="willtech-room-")
        cls.repo = mkrepo(cls.tmp.name, "repo")
        for f in ("willtech-room.py", "willtech-dossie.py"):
            (cls.repo / "tools" / f).write_text((ROOT / "tools" / f).read_text())
        git(cls.repo, "add", "-A")
        git(cls.repo, "commit", "-qm", "base")
        cls.room = str(cls.repo / ".willtech" / "room.db")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_01_init_idempotent_schema(self):
        code, out = run("init", self.room, "--repo", str(self.repo))
        self.assertEqual(code, 0, out)
        self.assertIn("user_version=1", out)
        con = sqlite3.connect(self.room)
        try:
            tables = {r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertIn("records", tables)
            self.assertIn("records_fts", tables)
            self.assertIn("schema_migrations", tables)
            self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], 1)
            idx = {r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='index'")}
            for i in ("idx_records_project", "idx_records_kind",
                      "idx_records_specialty", "idx_records_status"):
                self.assertIn(i, idx)
            cols = {r[1] for r in con.execute("PRAGMA table_info(records)")}
            for c in ("id", "kind", "project_id", "specialty", "summary",
                      "path_ref", "source_hash", "evidence_hash", "status",
                      "created_at", "updated_at", "attrs"):
                self.assertIn(c, cols)
        finally:
            con.close()
        code, out = run("init", self.room, "--repo", str(self.repo))
        self.assertEqual(code, 0, out)
        con = sqlite3.connect(self.room)
        try:
            self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], 1)
        finally:
            con.close()

    def test_02_put_get_roundtrip(self):
        run("init", self.room, "--repo", str(self.repo))
        code, out = run("put", self.room, "--repo", str(self.repo),
                        "--kind", "finding", "--specialty", "explorer",
                        "--summary", "endpoint /v1/ingest aceita JSONL ate 5MiB",
                        "--path-ref", "tools/willtech-room.py",
                        "--evidence-hash", "aaaaaaaaaaaa")
        self.assertEqual(code, 0, out)
        self.assertIn("id=", out)
        code, out = run("get", self.room, "--repo", str(self.repo), "--id", "1")
        self.assertEqual(code, 0, out)
        self.assertIn("finding", out)
        self.assertIn("explorer", out)
        self.assertIn("/v1/ingest", out)
        self.assertIn("candidate", out)

    def test_03_put_idempotent_no_duplicate(self):
        run("init", self.room, "--repo", str(self.repo))
        args = ("put", self.room, "--repo", str(self.repo), "--kind", "skill",
                "--specialty", "tester", "--summary", "rodar suite antes de commit",
                "--path-ref", "tools/test-room.py")
        run(*args)
        code, out = run(*args)
        self.assertEqual(code, 0, out)
        self.assertIn("updated", out)
        con = sqlite3.connect(self.room)
        try:
            n = con.execute("SELECT COUNT(*) FROM records WHERE kind='skill'").fetchone()[0]
            self.assertEqual(n, 1, "put idempotente nao duplica registro")
        finally:
            con.close()

    def test_04_secret_path_refused(self):
        run("init", self.room, "--repo", str(self.repo))
        code, out = run("put", self.room, "--repo", str(self.repo),
                        "--kind", "ref", "--specialty", "explorer",
                        "--summary", "nota sobre config", "--path-ref", ".env")
        self.assertEqual(code, 2)
        self.assertIn("recusado", out.lower())
        code, out = run("put", self.room, "--repo", str(self.repo),
                        "--kind", "ref", "--specialty", "explorer",
                        "--summary", "deploy com API_KEY=valor123 em producao",
                        "--path-ref", "tools/willtech-room.py")
        self.assertEqual(code, 2)
        self.assertIn("recusado", out.lower())
        self.assertNotIn("valor123", out)

    def test_05_project_isolation(self):
        run("init", self.room, "--repo", str(self.repo))
        other = mkrepo(self.tmp.name, "other")
        code, out = run("get", self.room, "--repo", str(other), "--id", "1")
        self.assertEqual(code, 2)
        self.assertIn("outro projeto", out.lower())
        code, out = run("put", self.room, "--repo", str(other),
                        "--kind", "finding", "--specialty", "explorer",
                        "--summary", "invasao de projeto vizinho")
        self.assertEqual(code, 2)
        code, out = run("query", self.room, "--repo", str(other),
                        "--objective", "qualquer coisa")
        self.assertEqual(code, 2)
        self.assertIn("outro projeto", out.lower())

    def test_06_check_integrity_and_counts(self):
        run("init", self.room, "--repo", str(self.repo))
        run("put", self.room, "--repo", str(self.repo), "--kind", "decision",
            "--specialty", "general", "--summary", "adotar WAL e sidecar lock",
            "--path-ref", "tools/willtech-room.py")
        code, out = run("check", self.room, "--repo", str(self.repo))
        self.assertEqual(code, 0, out)
        self.assertIn("integrity", out.lower())
        self.assertIn("ok", out.lower())
        self.assertIn("records=", out)

    def test_07_export_jsonl(self):
        run("init", self.room, "--repo", str(self.repo))
        run("put", self.room, "--repo", str(self.repo), "--kind", "risk",
            "--specialty", "reviewer", "--summary", "banco binario menos auditavel",
            "--path-ref", "docs/design.md")
        code, out = run("export", self.room, "--repo", str(self.repo))
        self.assertEqual(code, 0, out)
        lines = [l for l in out.splitlines() if l.strip()]
        self.assertTrue(lines, "export devolve JSONL nao vazio")
        rec = json.loads(lines[-1])
        self.assertEqual(rec["kind"], "risk")
        self.assertIn("summary", rec)
        self.assertIn("source_hash", rec)

    def test_08_lock_sidecar_exists(self):
        run("init", self.room, "--repo", str(self.repo))
        self.assertTrue(os.path.isfile(self.room + ".lock"))

    def test_09_get_refuses_non_git_repo(self):
        run("init", self.room, "--repo", str(self.repo))
        nogit = Path(self.tmp.name) / "nogit"
        nogit.mkdir(exist_ok=True)
        code, out = run("get", self.room, "--repo", str(nogit), "--id", "1")
        self.assertEqual(code, 2)
        self.assertIn("reposit", out.lower())

    def test_10_refusal_does_not_echo_path(self):
        run("init", self.room, "--repo", str(self.repo))
        code, out = run("put", self.room, "--repo", str(self.repo),
                        "--kind", "ref", "--specialty", "explorer",
                        "--summary", "nota", "--path-ref", "keys/id_rsa")
        self.assertEqual(code, 2)
        self.assertIn("recusado", out.lower())
        self.assertNotIn("id_rsa", out)

    def test_11_reput_preserves_validated_status(self):
        run("init", self.room, "--repo", str(self.repo))
        args = ("put", self.room, "--repo", str(self.repo), "--kind", "decision",
                "--specialty", "general", "--summary", "status preservado no re-put",
                "--path-ref", "tools/willtech-room.py")
        run(*args)
        con = sqlite3.connect(self.room)
        try:
            con.execute("UPDATE records SET status='validated' WHERE kind='decision'")
            con.commit()
        finally:
            con.close()
        code, out = run(*args)
        self.assertEqual(code, 0, out)
        self.assertIn("updated", out)
        con = sqlite3.connect(self.room)
        try:
            st = con.execute("SELECT status FROM records WHERE kind='decision'").fetchone()[0]
            self.assertEqual(st, "validated", "re-put idempotente nao rebaixa status")
        finally:
            con.close()


class RoomQueryTests(unittest.TestCase):
    """PASSO 2: consulta JIT com orcamento canonico."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="willtech-room-q-")
        cls.repo = mkrepo(cls.tmp.name, "repoq")
        for f in ("willtech-room.py", "willtech-dossie.py"):
            (cls.repo / "tools" / f).write_text((ROOT / "tools" / f).read_text())
        git(cls.repo, "add", "-A")
        git(cls.repo, "commit", "-qm", "base")
        cls.room = str(cls.repo / ".willtech" / "room.db")
        run("init", cls.room, "--repo", str(cls.repo))
        run("put", cls.room, "--repo", str(cls.repo), "--kind", "skill",
            "--specialty", "executor", "--summary",
            "usar script dedicado para writes no banco da sala",
            "--path-ref", "tools/willtech-room.py")
        run("put", cls.room, "--repo", str(cls.repo), "--kind", "skill",
            "--specialty", "tester", "--summary",
            "rodar suite deterministica com TMPDIR aprovado antes de commit",
            "--path-ref", "tools/test-room.py")
        run("put", cls.room, "--repo", str(cls.repo), "--kind", "finding",
            "--specialty", "explorer", "--summary",
            "mapa de simbolo e indice incremental no repomap",
            "--path-ref", "tools/willtech-repomap.py")
        run("put", cls.room, "--repo", str(cls.repo), "--kind", "finding",
            "--specialty", "explorer", "--summary",
            "nota descartada sobre budget antigo do repomap",
            "--path-ref", "tools/willtech-repomap.py")
        con = sqlite3.connect(cls.room)
        try:
            con.execute("UPDATE records SET status='dropped' WHERE summary LIKE '%descartada%'")
            fence = chr(96) * 3
            con.execute("UPDATE records SET summary=? WHERE summary LIKE '%simbolo%'",
                        ("mapa de simbolo\ncom quebra interna e " + fence + "fence" + fence + " no meio",))
            con.commit()
        finally:
            con.close()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_10_query_budget_respected(self):
        code, out = run("query", self.room, "--repo", str(self.repo),
                        "--objective", "simbolo repomap", "--budget-chars", "200")
        self.assertEqual(code, 0, out)
        self.assertLessEqual(len(out), 200)
        code, out = run("query", self.room, "--repo", str(self.repo),
                        "--objective", "simbolo repomap")
        self.assertEqual(code, 0)
        self.assertLessEqual(len(out), 1200, "default de orcamento e 1200 chars")

    def test_11_query_header_and_provenance(self):
        code, out = run("query", self.room, "--repo", str(self.repo),
                        "--objective", "suite tester")
        self.assertEqual(code, 0, out)
        self.assertIn("QUARENTENA", out)
        self.assertIn("nunca instru", out.lower())
        self.assertIn("source_hash", out)
        self.assertIn("tools/test-room.py", out)

    def test_12_query_neutralizes_delimiters(self):
        code, out = run("query", self.room, "--repo", str(self.repo),
                        "--objective", "quebra interna fence")
        self.assertEqual(code, 0, out)
        self.assertNotIn("\ncom quebra", out)
        self.assertNotIn(chr(96) * 3, out)
        self.assertIn("mapa de simbolo", out)

    def test_13_query_filter_specialty_and_status(self):
        code, out = run("query", self.room, "--repo", str(self.repo),
                        "--specialty", "tester", "--objective", "suite")
        self.assertEqual(code, 0, out)
        self.assertIn("tester", out)
        self.assertNotIn("executor", out)
        self.assertNotIn("descartada", out)

    def test_14_query_isolation(self):
        other = mkrepo(self.tmp.name, "otherq")
        code, out = run("query", self.room, "--repo", str(other),
                        "--objective", "suite")
        self.assertEqual(code, 2)
        self.assertIn("outro projeto", out.lower())

    def test_15_budget_constant_shared_with_hook(self):
        src_auto = AUTO.read_text()
        self.assertIn("BUDGET_CHARS = 1200", src_auto)
        self.assertIn("BRIEF_CAP", src_auto)
        m = load_mod(AUTO)
        self.assertEqual(m.BUDGET_CHARS, 1200)
        self.assertEqual(m.BRIEF_CAP, m.BUDGET_CHARS)
        rm = load_mod(TOOL)
        self.assertEqual(rm.BUDGET_CHARS, 1200)


if __name__ == "__main__":
    unittest.main(verbosity=2)

# WillTech-General / WILLTECH-BH © 2026 · autoria: github.com/hebwil
