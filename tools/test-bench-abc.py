#!/usr/bin/env python3
"""Testes determinísticos do executor/consolidador de benchmark A/B/C."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "willtech_bench_abc", os.path.join(HERE, "willtech-bench-abc.py"))
BENCH = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(BENCH)


def _ev_text(txt):
    return [{"type": "text", "part": {"text": txt}}]


class TestBenchABC(unittest.TestCase):
    def test_01_evaluate_functional_strict_and_anti_stale(self):
        self.assertTrue(BENCH.evaluate_functional("T1", _ev_text('APP_VERSION = "3.4.2"')))
        self.assertFalse(BENCH.evaluate_functional("T1", _ev_text("versao desconhecida")))

        self.assertTrue(BENCH.evaluate_functional(
            "T2", _ev_text("MAX_TAXA vale 0.35 e levanta ValueError taxa_fora_do_intervalo")))
        self.assertFalse(BENCH.evaluate_functional("T2", _ev_text("MAX_TAXA vale 0.35 apenas")))

        # T3 exige 0.12 e 112, e rejeita resposta obsoleta 0.05 / 105.0
        self.assertTrue(BENCH.evaluate_functional(
            "T3", _ev_text("ALIQUOTA_PADRAO atual em src/tax.py e 0.12 e fechar_fatura(100, 0.0) retorna 112.0")))
        self.assertFalse(BENCH.evaluate_functional(
            "T3", _ev_text("ALIQUOTA_PADRAO vale 0.05 e fechar_fatura(100, 0.0) retorna 105.0")))

    def test_02_setup_lab_repo_jit_arms_and_t3_invalidation(self):
        with tempfile.TemporaryDirectory() as tmp:
            # T1: sem memória pertinente na Sala -> B não deve injetar ruído de calc/tax/formatter
            lab_t1 = os.path.join(tmp, "t1")
            BENCH.setup_lab_repo(lab_t1, "T1")
            auto_py = os.path.join(lab_t1, "tools", "willtech-auto.py")

            def run_prompt(lab, prompt, arm_env):
                env = dict(os.environ)
                env.update(arm_env)
                p = subprocess.run(
                    [sys.executable, auto_py],
                    input=json.dumps({
                        "hook_event_name": "UserPromptSubmit",
                        "cwd": lab,
                        "prompt": prompt,
                    }),
                    env=env, capture_output=True, text=True, check=True)
                if not p.stdout.strip():
                    return ""
                data = json.loads(p.stdout)
                return (data.get("hookSpecificOutput") or {}).get("additionalContext") or ""

            ctx_t1_a = run_prompt(lab_t1, BENCH.SCENARIOS["T1"]["prompt"], dict(BENCH.ARMS[0][1]))
            ctx_t1_b = run_prompt(lab_t1, BENCH.SCENARIOS["T1"]["prompt"], dict(BENCH.ARMS[1][1]))
            self.assertIn("DOSSIE absent", ctx_t1_a)
            self.assertEqual(ctx_t1_b, "")
            self.assertLess(len(ctx_t1_b), len(ctx_t1_a))

            # T2: memória validada pertinente -> B e C recuperam MAX_TAXA=0.35 + ValueError sem ruído
            lab_t2 = os.path.join(tmp, "t2")
            BENCH.setup_lab_repo(lab_t2, "T2")
            ctx_t2_b = run_prompt(lab_t2, BENCH.SCENARIOS["T2"]["prompt"], dict(BENCH.ARMS[1][1]))
            ctx_t2_c = run_prompt(lab_t2, BENCH.SCENARIOS["T2"]["prompt"], dict(BENCH.ARMS[2][1]))
            self.assertIn("0.35", ctx_t2_b)
            self.assertIn("ValueError", ctx_t2_b)
            self.assertNotIn("formatar_brl", ctx_t2_b)
            self.assertIn("0.35", ctx_t2_c)

            # T3: src/tax.py mudou (0.05 -> 0.12) -> B e C invalidam registro obsoleto e C inclui RepoMap direcionado
            lab_t3 = os.path.join(tmp, "t3")
            room_t3 = BENCH.setup_lab_repo(lab_t3, "T3")
            ctx_t3_b = run_prompt(lab_t3, BENCH.SCENARIOS["T3"]["prompt"], dict(BENCH.ARMS[1][1]))
            ctx_t3_c = run_prompt(lab_t3, BENCH.SCENARIOS["T3"]["prompt"], dict(BENCH.ARMS[2][1]))
            self.assertNotIn("0.05", ctx_t3_b)
            self.assertNotIn("0.05", ctx_t3_c)
            self.assertIn("MAP src/invoice.py:", ctx_t3_c)
            self.assertIn("fechar_fatura", ctx_t3_c)

            # Suíte unitária do laboratório deve passar
            tr = subprocess.run(
                [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"],
                cwd=lab_t3, capture_output=True, text=True)
            self.assertEqual(tr.returncode, 0, tr.stderr)

            # Revisão independente: handoff #6 tem conclusão privada que NÃO vaza ao revisor
            room_py = os.path.join(lab_t3, "tools", "willtech-room.py")
            rp = subprocess.run(
                [sys.executable, room_py, "context-pack", room_t3, "--repo", lab_t3,
                 "--for-agent", "reviewer", "--handoff-id", "6",
                 "--objective", "fechar_fatura ALIQUOTA_PADRAO"],
                capture_output=True, text=True, check=True)
            self.assertNotIn("CONCLUSAO_EXECUTOR_PRIVADA_NAO_VAZAR", rp.stdout)
            self.assertIn("omitido por política", rp.stdout)

    def test_03_consolidate_generates_markdown_and_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            in_dir = os.path.join(tmp, "in")
            os.makedirs(in_dir, exist_ok=True)
            base_run = {m: 100.0 for m in BENCH.COMPARE.EXTENDED_METRIC_NAMES}
            opt_run = {m: 80.0 for m in BENCH.COMPARE.EXTENDED_METRIC_NAMES}
            base_run["cost_usd"] = 0.0
            opt_run["cost_usd"] = 0.0

            sample = {
                "scenario": "T2",
                "scenario_meta": BENCH.SCENARIOS["T2"],
                "arms": [
                    {"label": "A", "runs": [base_run, base_run, base_run],
                     "stats": {m: {"mean": base_run[m], "stddev": 0.0} for m in base_run}},
                    {"label": "B", "runs": [opt_run, opt_run, opt_run],
                     "stats": {m: {"mean": opt_run[m], "stddev": 0.0} for m in opt_run}},
                    {"label": "C", "runs": [opt_run, opt_run, opt_run],
                     "stats": {m: {"mean": opt_run[m], "stddev": 0.0} for m in opt_run}},
                ],
                "deltas_vs_baseline": {
                    "B": {m: {"abs": -20.0, "pct": -20.0} for m in base_run},
                    "C": {m: {"abs": -20.0, "pct": -20.0} for m in base_run},
                },
                "functional": {
                    "A": {"passes": 3, "total": 3, "rate": 1.0},
                    "B": {"passes": 3, "total": 3, "rate": 1.0},
                    "C": {"passes": 3, "total": 3, "rate": 1.0},
                },
                "stale_invalidation_verified": True,
                "reviewer_pack_verified": True,
            }
            with open(os.path.join(in_dir, "T2-compare.json"), "w", encoding="utf-8") as fh:
                json.dump(sample, fh)

            out_json = os.path.join(tmp, "out.json")
            out_md = os.path.join(tmp, "out.md")
            rc = subprocess.call([
                sys.executable, os.path.join(HERE, "willtech-bench-abc.py"),
                "consolidate", "--in-dir", in_dir,
                "--out-json", out_json, "--out-md", out_md,
            ], stdout=subprocess.DEVNULL)
            self.assertEqual(rc, 0)
            with open(out_json, encoding="utf-8") as fh:
                cj = json.load(fh)
            self.assertEqual(cj["total_runs"], 9)
            self.assertEqual(cj["overall_deltas_vs_A"]["B"]["effective_tokens"]["pct"], -20.0)
            with open(out_md, encoding="utf-8") as fh:
                md = fh.read()
            self.assertIn("effective_tokens", md)
            self.assertIn("-20.00%", md)


if __name__ == "__main__":
    unittest.main()

# WillTech-General / WILLTECH-BH © 2026 · autoria: github.com/hebwil
