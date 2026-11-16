#!/usr/bin/env python3
"""Testes determinísticos do RepoMap incremental (WillTech 2.3) + medição.

Sem modelo, sem rede: repositórios git descartáveis. A comparação de consumo
é medida (bytes, tokens estimados = bytes/4, tempo, parses), nunca extrapolada.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "willtech-repomap.py"


def run(*args):
    r = subprocess.run([sys.executable, str(TOOL), *args], capture_output=True, text=True)
    return r.returncode, r.stdout


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


class RepoMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="willtech-repomap-")
        cls.repo = Path(cls.tmp.name) / "repo"
        cls.repo.mkdir()
        git(cls.repo, "init", "-q")
        git(cls.repo, "config", "user.email", "test@example.com")
        git(cls.repo, "config", "user.name", "test")
        (cls.repo / "pkg").mkdir()
        (cls.repo / "pkg" / "a.py").write_text(
            "import b\n\ndef alpha(x):\n    return 'CORPO-SECRETO-NAO-INDEXAR'\n\nclass Gamma:\n    pass\n")
        (cls.repo / "pkg" / "b.py").write_text("def thing(z):\n    return z\n")
        for i in range(8):
            (cls.repo / f"mod{i}.py").write_text(f"def f{i}(a, b):\n    return a + b\n")
        (cls.repo / ".env").write_text("SECRET=valor-sensivel-123\n")
        (cls.repo / "credentials.pem").write_text("chave-sensivel-456\n")
        (cls.repo / ".aws").mkdir()
        (cls.repo / ".aws" / "credentials").write_text("aws-sensivel-789\n")
        (cls.repo / "bin.js").write_bytes(b"function ok() {}\n\x00binario")
        git(cls.repo, "add", "-A")
        git(cls.repo, "commit", "-qm", "base")
        cls.index = str(Path(cls.tmp.name) / "index.json")
        cls.nfiles = 10  # pkg/a, pkg/b, mod0..mod7

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_01_first_update(self):
        code, out = run("update", str(self.repo), self.index)
        self.assertEqual(code, 0)
        self.assertIn(f"parsed={self.nfiles} reused=0", out)
        data = json.loads(Path(self.index).read_text())
        syms = {s["n"]: s for s in data["files"]["pkg/a.py"]["symbols"]}
        self.assertEqual(syms["alpha"]["s"], "alpha(x)")
        self.assertEqual(syms["alpha"]["l"], 3)
        self.assertEqual(syms["Gamma"]["k"], "class")

    def test_02_incremental_reuse(self):
        run("update", str(self.repo), self.index)
        code, out = run("update", str(self.repo), self.index)
        self.assertEqual(code, 0)
        self.assertIn(f"parsed=0 reused={self.nfiles}", out)

    def test_03_single_file_change(self):
        run("update", str(self.repo), self.index)
        with open(self.repo / "pkg" / "b.py", "a") as fh:
            fh.write("\ndef nova(w):\n    return w\n")
        code, out = run("update", str(self.repo), self.index)
        self.assertIn(f"parsed=1 reused={self.nfiles - 1}", out)
        code, out = run("query", self.index, "--symbol", "nova")
        self.assertIn("pkg/b.py:4 function nova(w)", out)

    def test_04_uncommitted_stale_revalidation(self):
        run("update", str(self.repo), self.index)
        with open(self.repo / "pkg" / "a.py", "a") as fh:
            fh.write("\ndef extra():\n    pass\n")
        code, out = run("query", self.index, "--symbol", "alpha", "--repo", str(self.repo))
        self.assertEqual(code, 0)
        self.assertIn("STALE", out)
        run("update", str(self.repo), self.index)
        code, out = run("query", self.index, "--symbol", "alpha", "--repo", str(self.repo))
        self.assertNotIn("STALE", out)
        self.assertIn("CORPO-SECRETO-NAO-INDEXAR", out)  # trecho vem da fonte ao vivo

    def test_05_project_isolation(self):
        other = Path(self.tmp.name) / "other"
        other.mkdir()
        git(other, "init", "-q")
        code, out = run("query", self.index, "--symbol", "alpha", "--repo", str(other))
        self.assertEqual(code, 2)
        self.assertIn("outro projeto", out)
        code, out = run("brief", self.index, "--repo", str(other))
        self.assertEqual(code, 2)

    def test_06_sensitive_files_never_indexed(self):
        run("update", str(self.repo), self.index)
        blob = Path(self.index).read_text()
        for needle in (".env", "credentials.pem", ".aws", "valor-sensivel-123",
                       "chave-sensivel-456", "aws-sensivel-789", "bin.js"):
            self.assertNotIn(needle, blob)
        self.assertNotIn("CORPO-SECRETO-NAO-INDEXAR", blob)  # índice não copia conteúdo

    def test_07_references_and_precision(self):
        run("update", str(self.repo), self.index)
        code, out = run("query", self.index, "--refs", "b")
        self.assertIn("pkg/a.py referencia b", out)
        code, out = run("query", self.index, "--path", "pkg/a.py")
        self.assertIn("pkg/a.py:3 function alpha(x)", out)
        self.assertIn("pkg/a.py:6 class Gamma", out)

    def test_08_rename_and_remove(self):
        run("update", str(self.repo), self.index)
        os.rename(self.repo / "pkg" / "b.py", self.repo / "pkg" / "b2.py")
        code, out = run("update", str(self.repo), self.index)
        self.assertIn("renamed=1", out)
        self.assertIn("parsed=0", out)
        os.remove(self.repo / "mod7.py")
        code, out = run("update", str(self.repo), self.index)
        self.assertIn("dropped=1", out)
        data = json.loads(Path(self.index).read_text())
        self.assertNotIn("mod7.py", data["files"])
        self.assertIn("pkg/b2.py", data["files"])

    def test_09_brief_caps_and_quarantine(self):
        run("update", str(self.repo), self.index)
        code, out = run("brief", self.index, "--paths", "pkg", "--max-chars", "300")
        self.assertEqual(code, 0)
        self.assertLessEqual(len(out), 300)
        self.assertIn("QUARENTENA", out)
        self.assertIn("pkg/a.py", out)
        self.assertNotIn("mod0.py", out)

    def test_10_measured_consumption(self):
        run("update", str(self.repo), self.index)
        scope = ["pkg/a.py", "pkg/b2.py"] + [f"mod{i}.py" for i in range(7)]
        full_bytes = sum((self.repo / p).stat().st_size for p in scope)
        t0 = time.monotonic()
        code, full_out = run("update", str(self.repo), self.index)
        t_full = time.monotonic() - t0
        t0 = time.monotonic()
        code, inc_out = run("update", str(self.repo), self.index)
        t_inc = time.monotonic() - t0
        code, brief = run("brief", self.index, "--max-chars", "1200")
        brief_bytes = len(brief.encode("utf-8"))
        self.assertLess(brief_bytes, full_bytes)
        self.assertIn("parsed=0", inc_out)
        print(f"\nMEDIDO: leitura integral={full_bytes} bytes (~{full_bytes // 4} tokens) "
              f"vs brief={brief_bytes} bytes (~{brief_bytes // 4} tokens); "
              f"update incremental {t_inc:.3f}s vs rebuild {t_full:.3f}s; "
              f"parses: primeiro={self.nfiles}, incremental=0")


if __name__ == "__main__":
    unittest.main(verbosity=2)

# WillTech-General / WILLTECH-BH © 2026 · autoria: github.com/hebwil