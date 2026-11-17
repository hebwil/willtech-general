#!/usr/bin/env python3
"""Testes determinísticos do supervisor de delegações (WillTech 2.3).

Sem modelo, sem rede, sem aplicativos: estado descartável e relógio
injetável (--now). Inclui concorrência real via processos e integração
fail-open com o SessionStart do willtech-auto.py.
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
TOOL = ROOT / "tools" / "willtech-supervisor.py"
AUTO = ROOT / "tools" / "willtech-auto.py"


def run(*args):
    r = subprocess.run([sys.executable, str(TOOL), *args], capture_output=True, text=True)
    return r.returncode, r.stdout


def start(state, task, agent="willtech-executor", **kw):
    args = ["start", state, "--agent", agent, "--goal", f"objetivo {task}", "--task", task]
    for k, v in kw.items():
        args += [f"--{k.replace('_', '-')}", str(v)]
    code, out = run(*args)
    return code, out.split()[-1] if code == 0 else out


def report(state, ident):
    code, out = run("report", state, "--id", ident)
    return code, json.loads(out) if code == 0 else {}


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="willtech-sup-", ignore_cleanup_errors=True)
        self.state = str(Path(self.tmp.name) / "delegations.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_1_fast_specialist_returns(self):
        code, ident = start(self.state, "t1")
        self.assertEqual(code, 0)
        ev = Path(self.tmp.name) / "ev.txt"
        ev.write_text("ok\n")
        code, out = run("finish", self.state, "--id", ident, "--status", "completed",
                        "--summary", "feito", "--files", "a.py,b.py", "--evidence", str(ev))
        self.assertEqual(code, 0)
        code, d = report(self.state, ident)
        self.assertEqual(d["state"], "completed")
        self.assertEqual(d["files"], ["a.py", "b.py"])
        self.assertTrue(d["evidence_sha"])
        self.assertEqual(d["summary"], "feito")

    def test_2_slow_specialist_flagged(self):
        code, ident = start(self.state, "t2", soft=10, hard=100)
        _, d = report(self.state, ident)
        code, out = run("tick", self.state, "--now", str(d["started"] + 20))
        self.assertIn(f"SLOW {ident}", out)
        _, d = report(self.state, ident)
        self.assertEqual(d["state"], "running")
        self.assertTrue(d["slow"])

    def test_3_timeout_honest_no_silent_loss(self):
        code, ident = start(self.state, "t3", soft=10, hard=100)
        _, d0 = report(self.state, ident)
        code, out = run("tick", self.state, "--now", str(d0["started"] + 200))
        self.assertIn(f"TIMED_OUT {ident}", out)
        _, d = report(self.state, ident)
        self.assertEqual(d["state"], "timed_out")
        self.assertIn("NÃO confirmada", d["reason"])
        self.assertEqual(d["goal"], "objetivo t3")  # registro íntegro, sem perda silenciosa
        self.assertEqual(d["agent"], "willtech-executor")

    def test_4_recursion_blocked(self):
        _, p = start(self.state, "rec")
        _, c = start(self.state, "rec-c", parent=p)
        _, g = start(self.state, "rec-g", parent=c)
        code, out = start(self.state, "rec-gg", parent=g)
        self.assertEqual(code, 3)
        self.assertIn("recursão", out)
        run("finish", self.state, "--id", p, "--status", "completed")
        code, out = start(self.state, "rec-orphan", parent=p)
        self.assertEqual(code, 2)

    def test_5_duplicate_and_concurrent_writes(self):
        _, ident = start(self.state, "dup")
        code, out = start(self.state, "dup")
        self.assertEqual(code, 3)
        self.assertIn("duplicado", out)
        code, out = start(self.state, "dup", agent="willtech-testador")
        self.assertEqual(code, 3)
        self.assertIn("concorrente", out)
        run("finish", self.state, "--id", ident, "--status", "completed")
        code, _ = start(self.state, "dup", agent="willtech-testador")
        self.assertEqual(code, 0)
        # concorrência real: dois processos, mesma tarefa, um vencedor
        procs = [subprocess.Popen([sys.executable, str(TOOL), "start", self.state,
                                   "--agent", a, "--goal", "g", "--task", "race"],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                 for a in ("willtech-executor", "willtech-visual")]
        codes = []
        for p in procs:
            p.communicate()
            codes.append(p.returncode)
        self.assertEqual(sorted(codes), [0, 3])

    def test_6_failure_informative_general_continues(self):
        _, ident = start(self.state, "fail")
        run("finish", self.state, "--id", ident, "--status", "failed",
            "--reason", "dependência ausente", "--pending", "instalar dep")
        _, d = report(self.state, ident)
        self.assertEqual(d["state"], "failed")
        self.assertEqual(d["reason"], "dependência ausente")
        self.assertEqual(d["pending"], "instalar dep")
        code, _ = start(self.state, "next")
        self.assertEqual(code, 0)  # General segue operacional

    def test_7_cancel_respects_runtime_capability(self):
        code, out = run("capabilities", "--runtime", "opencode")
        self.assertFalse(json.loads(out)["opencode"]["real_cancel"])
        _, ident = start(self.state, "cancel")
        code, out = run("cancel", self.state, "--id", ident, "--runtime", "opencode")
        self.assertEqual(code, 0)
        self.assertIn("NÃO confirmado como interrompido", out)
        _, d = report(self.state, ident)
        self.assertEqual(d["state"], "running")
        self.assertTrue(d["cancel_requested"])
        code, out = run("cancel", self.state, "--id", ident, "--confirmed")
        self.assertEqual(code, 0)
        _, d = report(self.state, ident)
        self.assertEqual(d["state"], "cancelled")

    def test_8_single_safe_retry(self):
        _, ident = start(self.state, "retry")
        run("finish", self.state, "--id", ident, "--status", "failed", "--reason", "x")
        code, out = run("retry", self.state, "--id", ident)
        self.assertEqual(code, 3)
        self.assertIn("reconcilie", out)
        code, out = run("retry", self.state, "--id", ident, "--reconciled")
        self.assertEqual(code, 0)
        new = out.split()[1]
        _, d = report(self.state, new)
        self.assertEqual(d["retry_of"], ident)
        self.assertEqual(d["state"], "running")
        code, out = run("retry", self.state, "--id", ident, "--reconciled")
        self.assertEqual(code, 3)  # sem retry infinito
        _, old = report(self.state, ident)
        self.assertEqual(old["state"], "failed")  # trabalho parcial preservado
        _, ok = start(self.state, "retry-ok")
        run("finish", self.state, "--id", ok, "--status", "completed")
        code, _ = run("retry", self.state, "--id", ok, "--reconciled")
        self.assertEqual(code, 3)

    def test_9_per_task_cap(self):
        _, ident = start(self.state, "cap", max_per_task=1)
        run("finish", self.state, "--id", ident, "--status", "completed")
        code, out = start(self.state, "cap", max_per_task=1)
        self.assertEqual(code, 3)
        self.assertIn("teto", out)

    def test_10_auto_sessionstart_reports_supervisor(self):
        repo = Path(self.tmp.name) / "repo"
        repo.mkdir()
        subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True, capture_output=True)
        base = repo / ".willtech"
        base.mkdir()
        (base / "enabled").write_text("")
        now = time.time()
        (base / "delegations.json").write_text(json.dumps({"seq": 1, "delegations": {
            "lag1": {"id": "lag1", "agent": "willtech-testador", "goal": "g", "task": "t",
                     "parent": "", "depth": 0, "state": "running", "started": now - 100,
                     "soft": 10, "hard": 1000, "slow": False, "cancel_requested": False,
                     "retries_used": 0, "retry_of": "", "summary": "", "files": [],
                     "evidence_path": "", "evidence_sha": "", "pending": "", "reason": "",
                     "finished": None}}}))
        ev = json.dumps({"hook_event_name": "SessionStart", "session_id": "s1", "cwd": str(repo)})
        r = subprocess.run([sys.executable, str(AUTO), "opencode"], input=ev,
                           capture_output=True, text=True)
        out = json.loads(r.stdout)
        self.assertIn("SUPERVISOR SLOW lag1", out["context"])
        (base / "enabled").unlink()
        r = subprocess.run([sys.executable, str(AUTO), "opencode"], input=ev,
                           capture_output=True, text=True)
        self.assertEqual(json.loads(r.stdout)["context"], "")  # desativação simples preservada


if __name__ == "__main__":
    unittest.main(verbosity=2)

# WillTech-General / WILLTECH-BH © 2026 · autoria: github.com/hebwil