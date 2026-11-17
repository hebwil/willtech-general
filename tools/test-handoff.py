#!/usr/bin/env python3
"""Testes determinísticos de handoff e micro-skills (WillTech 3.0, PASSOS 3-4).

Padrão: tools/test-room.py (unittest, subprocess, diretórios temporários).
Handoff: pack do revisor montado PELA FERRAMENTA a partir de IDs de
evidência — validação mecânica de que o pack NUNCA herda conclusões do
executor (result não entra no pack). Skills: ciclo de vida candidate →
validated (só com aprovação humana explícita) → dropped/superseded;
query só injeta skills validated; candidates do trace entram verified:false.
"""
import importlib.util
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "willtech-room.py"
TRACE = ROOT / "claude-code" / "bin" / "willtech_trace.py"


def run(*args):
    r = subprocess.run([sys.executable, str(TOOL), *args],
                       capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def load_mod(path):
    spec = importlib.util.spec_from_file_location("mod_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class HandoffSkillBase(unittest.TestCase):
    """Fixture comum: repo descartável + sala inicializada + 2 evidências."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="willtech-handoff-")
        cls.repo = Path(cls.tmp.name) / "repo"
        (cls.repo / "tools").mkdir(parents=True)
        git(cls.repo, "init", "-q")
        git(cls.repo, "config", "user.email", "test@example.com")
        git(cls.repo, "config", "user.name", "test")
        for f in ("willtech-room.py", "willtech-dossie.py"):
            (cls.repo / "tools" / f).write_text((ROOT / "tools" / f).read_text())
        (cls.repo / "tools" / "notas.txt").write_text("conteudo de evidencia\n")
        (cls.repo / "tools" / "impl.txt").write_text("arquivo do implementador\n")
        git(cls.repo, "add", "-A")
        git(cls.repo, "commit", "-qm", "base")
        cls.room = str(cls.repo / ".willtech" / "room.db")
        code, out = run("init", cls.room, "--repo", str(cls.repo))
        assert code == 0, out
        # evidência 1: finding apontando o arquivo de evidência
        run("put", cls.room, "--repo", str(cls.repo), "--kind", "finding",
            "--specialty", "explorer", "--summary", "endpoint validado com teste",
            "--path-ref", "tools/notas.txt")
        # evidência 2: test_result apontando outro arquivo
        run("put", cls.room, "--repo", str(cls.repo), "--kind", "test_result",
            "--specialty", "tester", "--summary", "suite verde 17/17",
            "--path-ref", "tools/willtech-room.py")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()


class HandoffTests(HandoffSkillBase):
    """PASSO 3: handoff com pack montado pela ferramenta."""

    def test_10_handoff_record_validates_evidence_ids(self):
        # IDs inexistentes são recusados (exit 2)
        code, out = run("handoff-record", self.room, "--repo", str(self.repo),
                        "--objective", "revisar integracao da sala",
                        "--evidence-ids", "999,1000", "--next-owner", "reviewer")
        self.assertEqual(code, 2, out)
        self.assertIn("recusado", out.lower())
        # IDs válidos criam o handoff
        code, out = run("handoff-record", self.room, "--repo", str(self.repo),
                        "--objective", "revisar integracao da sala",
                        "--evidence-ids", "1,2",
                        "--next-owner", "reviewer",
                        "--files", "tools/notas.txt,tools/willtech-room.py")
        self.assertEqual(code, 0, out)
        self.assertIn("id=", out)

    def test_11_handoff_fetch_quarantine_and_provenance(self):
        run("handoff-record", self.room, "--repo", str(self.repo),
            "--objective", "revisar fetch", "--evidence-ids", "1",
            "--next-owner", "reviewer")
        hid = self._last_handoff_id()
        code, out = run("handoff-fetch", self.room, "--repo", str(self.repo),
                        "--id", hid)
        self.assertEqual(code, 0, out)
        self.assertIn("QUARENTENA", out)
        self.assertIn("source_hash", out)      # provenance por evidência
        self.assertIn("revisar fetch", out)
        self.assertIn("reviewer", out)

    def _last_handoff_id(self):
        code, out = run("export", self.room, "--repo", str(self.repo))
        ids = [json.loads(l) for l in out.splitlines()
               if l.strip().startswith("{")]
        hs = [r for r in ids if r["kind"] == "handoff"
              and r["status"] != "dropped"]
        self.assertTrue(hs, "handoff de fixture ausente")
        return str(hs[-1]["id"])

    def test_12_pack_excludes_executor_conclusions(self):
        # RED central: handoff com 'result' do executor — o pack NUNCA
        # pode conter esse texto (validação mecânica do anti-vazamento).
        code, out = run("handoff-record", self.room, "--repo", str(self.repo),
                        "--objective", "revisar pack sem vazamento",
                        "--evidence-ids", "1,2",
                        "--next-owner", "reviewer",
                        "--result",
                        "CONCLUSAO-SECRETA-DO-EXECUTOR: integracao aprovada por mim")
        self.assertEqual(code, 0, out)
        hid = self._last_handoff_id()
        code, pack = run("handoff-pack", self.room, "--repo", str(self.repo),
                         "--handoff-id", hid)
        self.assertEqual(code, 0, pack)
        self.assertIn("QUARENTENA", pack)
        self.assertIn("revisar pack sem vazamento", pack)   # objetivo entra
        self.assertIn("tools/notas.txt", pack)              # evidência entra
        self.assertNotIn("CONCLUSAO-SECRETA-DO-EXECUTOR", pack)  # result NUNCA
        self.assertNotIn("conclus", pack.lower().split("QUARENTENA")[1].splitlines()[0])

    def test_13_pack_requires_existing_handoff(self):
        code, out = run("handoff-pack", self.room, "--repo", str(self.repo),
                        "--handoff-id", "424242")
        self.assertEqual(code, 2, out)
        self.assertIn("recusado", out.lower())

    def test_14_handoff_isolation_non_git_repo(self):
        nogit = Path(self.tmp.name) / "nogit-h"
        nogit.mkdir(exist_ok=True)
        code, out = run("handoff-fetch", self.room, "--repo", str(nogit),
                        "--id", "1")
        self.assertEqual(code, 2)


class SkillTests(HandoffSkillBase):
    """PASSO 4: micro-skills com ciclo de vida e gate humano."""

    def test_20_skill_add_needs_evidence_and_starts_candidate(self):
        # sem evidence-hash: recusado
        code, out = run("skill-add", self.room, "--repo", str(self.repo),
                        "--specialty", "tester",
                        "--instruction", "rodar suite antes de commit")
        self.assertEqual(code, 2, out)
        self.assertIn("recusado", out.lower())
        # com evidence-hash: nasce candidate
        code, out = run("skill-add", self.room, "--repo", str(self.repo),
                        "--specialty", "tester",
                        "--instruction", "rodar suite antes de commit",
                        "--evidence-hash", "e" * 12)
        self.assertEqual(code, 0, out)
        self.assertIn("id=", out)
        code, out = run("skill-list", self.room, "--repo", str(self.repo),
                        "--specialty", "tester", "--status", "candidate")
        self.assertIn("rodar suite antes de commit", out)

    def test_21_skill_promote_requires_human_flag(self):
        run("skill-add", self.room, "--repo", str(self.repo),
            "--specialty", "executor",
            "--instruction", "usar script dedicado para writes",
            "--evidence-hash", "f" * 12)
        sid = self._last_skill_id()
        # sem --i-approve-human: exit 2, mensagem clara
        code, out = run("skill-promote", self.room, "--repo", str(self.repo),
                        "--id", sid)
        self.assertEqual(code, 2, out)
        self.assertIn("i-approve-human", out.lower())
        # com a flag: validated
        code, out = run("skill-promote", self.room, "--repo", str(self.repo),
                        "--id", sid, "--i-approve-human")
        self.assertEqual(code, 0, out)
        code, out = run("skill-list", self.room, "--repo", str(self.repo),
                        "--status", "validated")
        self.assertIn("usar script dedicado", out)

    def _last_skill_id(self):
        code, out = run("export", self.room, "--repo", str(self.repo))
        ids = [json.loads(l) for l in out.splitlines()
               if l.strip().startswith("{")]
        return str([r for r in ids if r["kind"] == "skill"][-1]["id"])

    def test_22_skill_drop_and_supersede(self):
        run("skill-add", self.room, "--repo", str(self.repo),
            "--specialty", "visual",
            "--instruction", "preferir contraste alto em temas",
            "--evidence-hash", "a" * 12)
        sid = self._last_skill_id()
        code, out = run("skill-drop", self.room, "--repo", str(self.repo),
                        "--id", sid, "--reason", "contraditada por evidencia nova")
        self.assertEqual(code, 0, out)
        code, out = run("skill-list", self.room, "--repo", str(self.repo),
                        "--status", "dropped")
        self.assertIn("contraste alto", out)
        run("skill-add", self.room, "--repo", str(self.repo),
            "--specialty", "visual",
            "--instruction", "contraste minimo AA em temas",
            "--evidence-hash", "b" * 12)
        sid2 = self._last_skill_id()
        code, out = run("skill-supersede", self.room, "--repo", str(self.repo),
                        "--id", sid, "--by", sid2)
        self.assertEqual(code, 0, out)
        code, out = run("skill-list", self.room, "--repo", str(self.repo),
                        "--status", "superseded")
        self.assertIn("contraste alto", out)

    def test_23_query_only_injects_validated_skills(self):
        run("skill-add", self.room, "--repo", str(self.repo),
            "--specialty", "tester",
            "--instruction", "dica candidate nunca injetada ZZZ-CAND",
            "--evidence-hash", "c" * 12)
        run("skill-add", self.room, "--repo", str(self.repo),
            "--specialty", "tester",
            "--instruction", "dica validated para injecao ZZZ-VAL",
            "--evidence-hash", "d" * 12)
        sid = self._last_skill_id()
        run("skill-promote", self.room, "--repo", str(self.repo),
            "--id", sid, "--i-approve-human")
        run("skill-add", self.room, "--repo", str(self.repo),
            "--specialty", "tester",
            "--instruction", "dica dropped nunca injetada ZZZ-DROP",
            "--evidence-hash", "1" * 12)
        did = self._last_skill_id()
        run("skill-drop", self.room, "--repo", str(self.repo),
            "--id", did, "--reason", "teste")
        code, out = run("query", self.room, "--repo", str(self.repo),
                        "--objective", "dica injecao")
        self.assertEqual(code, 0, out)
        self.assertIn("ZZZ-VAL", out)          # validated entra
        self.assertNotIn("ZZZ-CAND", out)      # candidate nunca auto-injetado
        self.assertNotIn("ZZZ-DROP", out)      # dropped some

    def test_24_skill_instruction_neutralized_and_capped(self):
        fence = chr(96) * 3
        run("skill-add", self.room, "--repo", str(self.repo),
            "--specialty", "general",
            "--instruction", "linha1 " + fence + "fence" + fence + " fim " + "x" * 400,
            "--evidence-hash", "9" * 12)
        sid = self._last_skill_id()
        code, out = run("skill-list", self.room, "--repo", str(self.repo),
                        "--status", "candidate")
        self.assertEqual(code, 0, out)
        self.assertNotIn(fence, out)                        # fence neutralizado
        line = [l for l in out.splitlines() if "linha1" in l][0]
        self.assertLessEqual(len(line), 340)                # ≤300 + prefixo

    def test_25_skill_import_candidates_from_trace(self):
        # fixture JSON: saída 'analyse' do willtech_trace.py (lesson_candidates)
        fixture = self.tmp.name + "/trace.json"
        Path(fixture).write_text(json.dumps({
            "lesson_candidates": [{
                "key": "k-import",
                "failed_command": "pytest -q",
                "resolution_command": "pytest -q -x",
                "evidence": {"tool_use_id": "u1",
                             "result_sha256": "abc123"},
                "verified": False}]}, ensure_ascii=False))
        code, out = run("skill-import-candidates", self.room,
                        "--repo", str(self.repo), "--trace", fixture,
                        "--specialty", "tester")
        self.assertEqual(code, 0, out)
        self.assertIn("imported=1", out)
        code, out = run("skill-list", self.room, "--repo", str(self.repo),
                        "--status", "candidate")
        self.assertIn("pytest -q -x", out)      # resolution vira instrução
        # import idempotente: mesmo trace não duplica
        code, out = run("skill-import-candidates", self.room,
                        "--repo", str(self.repo), "--trace", fixture,
                        "--specialty", "tester")
        self.assertIn("imported=0", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)

# WillTech-General / WILLTECH-BH © 2026 · autoria: github.com/hebwil
