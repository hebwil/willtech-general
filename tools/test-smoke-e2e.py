#!/usr/bin/env python3
"""Smoke E2E da sala WillTech 3.0 (missão final §9) — categoria: smoke
determinístico ponta a ponta em laboratório descartável, subprocess reais,
sem modelo e sem rede. Complementa (não duplica) as suítes:
  test-room.py      init/contratos/injeção/segredos/orçamento
  test-room-v3.py   BL1-BL4, concorrência, backup/restore, falha de banco
  test-handoff.py   pack do revisor e micro-skills
  test-jit.py       consulta JIT funcional + núcleo real do hook (3 formatos)
  test-install.py   instalação/atualização/reinstalação do distribuidor

Aqui ficam os cenários E2E ainda não cobertos de ponta a ponta:
  - fluxo completo num único laboratório (put→validate→handoff→fetch→query)
  - invalidação por mudança de código (source_hash divergente → stale)
  - desativação/reativação da sala pelo gate .willtech/enabled (hook real)
  - banco v1 FRESCO (não downgrade) migrado até v3 com dados preservados
  - ausência de dependências inesperadas (scan de imports = stdlib)
  - exportação sem vazamento após recusas de segredo sintético
"""
import ast
import glob
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


def run(*args):
    r = subprocess.run([sys.executable, str(TOOL), *args],
                       capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def load_mod(path):
    spec = importlib.util.spec_from_file_location("smoke_mod", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class SmokeE2E(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="willtech-smoke-e2e-")
        cls.repo = Path(cls.tmp.name) / "lab"
        (cls.repo / "tools").mkdir(parents=True)
        (cls.repo / "claude-code" / "bin").mkdir(parents=True)
        git(cls.repo, "init", "-q")
        git(cls.repo, "config", "user.email", "smoke@example.com")
        git(cls.repo, "config", "user.name", "smoke")
        for f in ("willtech-room.py", "willtech-dossie.py",
                  "willtech-auto.py", "willtech-drift.py"):
            (cls.repo / "tools" / f).write_text((ROOT / "tools" / f).read_text())
        (cls.repo / "claude-code" / "bin" / "willtech_trace.py").write_text(
            (ROOT / "claude-code" / "bin" / "willtech_trace.py").read_text())
        (cls.repo / "tools" / "notas.txt").write_text("evidencia smoke\n")
        (cls.repo / "tools" / "alvo.txt").write_text("versao 1 do alvo\n")
        git(cls.repo, "add", "-A")
        git(cls.repo, "commit", "-qm", "base")
        cls.base = cls.repo / ".willtech"
        cls.room = str(cls.base / "room.db")
        cls.mod = load_mod(cls.repo / "tools" / "willtech-room.py")
        cls.dossie = load_mod(cls.repo / "tools" / "willtech-dossie.py")
        cls.pid = cls.dossie.project_id(str(cls.repo))
        code, out = run("init", cls.room, "--repo", str(cls.repo))
        assert code == 0, out
        (cls.base / "enabled").write_text("")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def hook(self, event="SessionStart", extra=None):
        ev = {"hook_event_name": event, "session_id": "smoke-e2e",
              "cwd": str(self.repo)}
        ev.update(extra or {})
        r = subprocess.run(
            [sys.executable, str(self.repo / "tools" / "willtech-auto.py"),
             "claude"], input=json.dumps(ev), capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        return r.stdout

    def db_status(self, rid, room=None):
        con = sqlite3.connect(room or self.room)
        try:
            return con.execute("SELECT status FROM records WHERE id=?",
                               (rid,)).fetchone()[0]
        finally:
            con.close()

    def test_01_no_unexpected_dependencies(self):
        # Scan estático: todo import dos arquivos de produto é stdlib ou
        # módulo local willtech (carregado via importlib). Sem pip/vendor.
        allowed = set(sys.stdlib_module_names) | {
            "willtech_dossie", "willtech_trace", "willtech_room",
            "willtech_supervisor"}
        files = sorted(glob.glob(str(ROOT / "tools" / "willtech-*.py")))
        files.append(str(ROOT / "claude-code" / "bin" / "willtech_trace.py"))
        self.assertGreaterEqual(len(files), 8)
        for fp in files:
            tree = ast.parse(Path(fp).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for al in node.names:
                        top = al.name.split(".")[0]
                        self.assertIn(top, allowed, f"{fp}: import {al.name}")
                elif isinstance(node, ast.ImportFrom) and not node.level:
                    top = (node.module or "").split(".")[0]
                    self.assertIn(top, allowed, f"{fp}: from {node.module}")

    def test_02_full_flow_e2e(self):
        code, out = run("put", self.room, "--repo", str(self.repo),
                        "--kind", "finding", "--specialty", "explorer",
                        "--summary", "ZZFLOW endpoint do fluxo validado",
                        "--path-ref", "tools/notas.txt")
        self.assertEqual(code, 0, out)
        fid = out.split("id=")[1].split()[0]
        code, out = run("validate", self.room, "--repo", str(self.repo),
                        "--id", fid, "--by", "tester")
        self.assertEqual(code, 0, out)
        result = "ZZRESULT fluxo completo persistido com provenance"
        code, out = run("handoff-record", self.room, "--repo", str(self.repo),
                        "--objective", "revisar fluxo smoke",
                        "--evidence-ids", fid, "--next-owner", "reviewer",
                        "--result", result)
        self.assertEqual(code, 0, out)
        hid = out.split("id=")[1].split()[0]
        # handoff pending NÃO entra na consulta automática
        code, out = run("query", self.room, "--repo", str(self.repo),
                        "--objective", "ZZFLOW ZZRESULT")
        self.assertEqual(code, 0, out)
        self.assertIn("ZZFLOW", out)
        self.assertNotIn("ZZRESULT", out)
        # validação com evidência suficiente + autoridade
        code, out = run("handoff-validate", self.room, "--repo", str(self.repo),
                        "--id", hid, "--evidence-ids", fid, "--by", "reviewer")
        self.assertEqual(code, 0, out)
        # processo NOVO recupera o resultado exato + estado de validação
        code, out = run("handoff-fetch", self.room, "--repo", str(self.repo),
                        "--id", hid)
        self.assertEqual(code, 0, out)
        self.assertIn(result, out)
        self.assertIn("state=validated", out)
        self.assertIn("by=reviewer", out)
        self.assertIn("KNOWLEDGE_VERSION: 3", out)
        # export é JSONL válido e carrega o resultado persistido
        code, out = run("export", self.room, "--repo", str(self.repo))
        self.assertEqual(code, 0, out)
        rows = [json.loads(l) for l in out.splitlines()
                if l.strip().startswith("{")]
        self.assertTrue(rows)
        self.assertTrue(any(r.get("kind") == "handoff" for r in rows))

    def test_03_invalidation_by_code_change(self):
        alvo = self.repo / "tools" / "alvo.txt"
        code, out = run("put", self.room, "--repo", str(self.repo),
                        "--kind", "finding", "--specialty", "tester",
                        "--summary", "ZZINV comportamento do alvo",
                        "--path-ref", "tools/alvo.txt")
        self.assertEqual(code, 0, out)
        rid = int(out.split("id=")[1].split()[0])
        code, out = run("validate", self.room, "--repo", str(self.repo),
                        "--id", str(rid), "--by", "tester")
        self.assertEqual(code, 0, out)
        code, out = run("query", self.room, "--repo", str(self.repo),
                        "--objective", "ZZINV")
        self.assertIn("ZZINV", out)
        # mudança de código: hash diverge → stale + fora da injeção
        alvo.write_text("versao 2 do alvo, contrato mudou\n")
        code, out = run("query", self.room, "--repo", str(self.repo),
                        "--objective", "ZZINV")
        self.assertEqual(code, 0, out)
        self.assertNotIn("ZZINV", out)
        self.assertEqual(self.db_status(rid), "stale")
        # re-put atualiza o source_hash (COALESCE) e validate restaura
        code, out = run("put", self.room, "--repo", str(self.repo),
                        "--kind", "finding", "--specialty", "tester",
                        "--summary", "ZZINV comportamento do alvo",
                        "--path-ref", "tools/alvo.txt")
        self.assertEqual(code, 0, out)
        self.assertIn("updated", out)
        self.assertEqual(self.db_status(rid), "stale")
        code, out = run("validate", self.room, "--repo", str(self.repo),
                        "--id", str(rid), "--by", "tester")
        self.assertEqual(code, 0, out)
        code, out = run("query", self.room, "--repo", str(self.repo),
                        "--objective", "ZZINV")
        self.assertIn("ZZINV", out)
        # arquivo removido: evidência sumiu → stale de novo
        alvo.unlink()
        code, out = run("query", self.room, "--repo", str(self.repo),
                        "--objective", "ZZINV")
        self.assertNotIn("ZZINV", out)
        self.assertEqual(self.db_status(rid), "stale")
        alvo.write_text("versao 2 do alvo, contrato mudou\n")

    def test_04_disable_and_reenable_room(self):
        # conhecimento semeado por teste anterior (ordem alfabética)
        enabled = self.base / "enabled"
        out = self.hook()
        self.assertIn("QUARENTENA", out)
        self.assertIn("SALA", out)
        # desativação: gate simples remove TODA injeção da sala
        enabled.unlink()
        out = self.hook()
        self.assertNotIn("SALA", out)
        self.assertNotIn("QUARENTENA", out)
        # reativação: mesmo banco, conhecimento volta a ser injetado
        enabled.write_text("")
        out = self.hook()
        self.assertIn("SALA", out)
        self.assertIn("ZZFLOW", out)

    def test_05_fresh_v1_db_migrates_to_v3(self):
        legacy = str(self.base / "legacy.db")
        con = sqlite3.connect(legacy)
        try:
            con.executescript(self.mod.SCHEMA.replace(
                "SCHEMA_TS", "2026-01-01T00:00:00Z"))
            for kind, summary, status in (
                    ("finding", "ZZLEGACY finding da v1", "validated"),
                    ("skill", "ZZLEGACYSKILL skill da v1", "candidate")):
                con.execute(
                    "INSERT INTO records (kind, project_id, specialty, summary,"
                    " status, created_at, updated_at, attrs) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (kind, self.pid, "general", summary, status,
                     "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z", "{}"))
            con.commit()
            self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], 1)
        finally:
            con.close()
        code, out = run("init", legacy, "--repo", str(self.repo))
        self.assertEqual(code, 0, out)
        self.assertIn("user_version=3", out)
        self.assertIn("backup", out)          # migração gera backup verificado
        con = sqlite3.connect(legacy)
        try:
            self.assertEqual(con.execute("PRAGMA integrity_check").fetchone()[0],
                             "ok")
            st = con.execute("SELECT status FROM records WHERE summary=?",
                             ("ZZLEGACY finding da v1",)).fetchone()[0]
            self.assertEqual(st, "validated")   # status preservado
        finally:
            con.close()
        code, out = run("query", legacy, "--repo", str(self.repo),
                        "--objective", "ZZLEGACY")
        self.assertEqual(code, 0, out)
        self.assertIn("ZZLEGACY finding da v1", out)
        self.assertNotIn("ZZLEGACYSKILL", out)  # skill v1 nunca auto-injetada
        # banco migrado aceita o ciclo 3.0 completo
        code, out = run("handoff-record", legacy, "--repo", str(self.repo),
                        "--objective", "handoff pos migracao",
                        "--evidence-ids", "1", "--next-owner", "reviewer",
                        "--result", "ZZPOSMIG resultado")
        self.assertEqual(code, 0, out)
        code, out = run("check", legacy, "--repo", str(self.repo))
        self.assertEqual(code, 0, out)
        self.assertIn("integrity=ok", out)

    def test_06_export_without_secret_leak(self):
        aws = "AKIAIOSFODNN7EXAMPLE"          # fixture sintética (exemplo AWS)
        code, out = run("put", self.room, "--repo", str(self.repo),
                        "--kind", "finding", "--specialty", "general",
                        "--summary", "credencial " + aws)
        self.assertEqual(code, 2, out)
        self.assertNotIn(aws, out)            # recusa não ecoa o valor
        code, out = run("handoff-record", self.room, "--repo", str(self.repo),
                        "--objective", "revisar credencial",
                        "--evidence-ids", "1", "--next-owner", "reviewer",
                        "--result", "token=" + aws)
        self.assertEqual(code, 2, out)
        self.assertNotIn(aws, out)
        code, out = run("export", self.room, "--repo", str(self.repo))
        self.assertEqual(code, 0, out)
        self.assertNotIn(aws, out)            # export sem vazamento
        for l in out.splitlines():
            if l.strip().startswith("{"):
                json.loads(l)                 # JSONL válido


if __name__ == "__main__":
    unittest.main(verbosity=2)

# WillTech-General / WILLTECH-BH © 2026 · autoria: github.com/hebwil