#!/usr/bin/env python3
"""Comparação de execuções (WillTech 3.0, PASSO 6) — transcripts sintéticos.

Sem modelo, sem rede: valida N execuções por lado, agregação por média,
aviso de AMOSTRA INSUFICIENTE e compatibilidade 1x1 (2.2).
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "willtech-compare.py"


def write_transcript(path, turns, input_tokens, output_tokens):
    events = [{"type": "result", "subtype": "success", "is_error": False,
               "num_turns": turns,
               "usage": {"input_tokens": input_tokens,
                         "output_tokens": output_tokens,
                         "cache_read_input_tokens": 0,
                         "cache_creation_input_tokens": 0}}]
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n")


def run(*args):
    r = subprocess.run([sys.executable, str(TOOL), *args],
                       capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


class CompareTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.d = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_01_single_pair_compat_22(self):
        a, b = self.d / "a.jsonl", self.d / "b.jsonl"
        write_transcript(a, 5, 100, 50)
        write_transcript(b, 4, 80, 40)
        code, out = run(str(a), str(b))
        self.assertEqual(code, 0, out)
        self.assertIn("input_tokens", out)
        self.assertIn("-20", out)          # delta real medido

    def test_02_aggregates_n_executions(self):
        left = []
        for i, tokens in enumerate((100, 200)):
            p = self.d / f"l{i}.jsonl"
            write_transcript(p, 5, tokens, 10)
            left.append(str(p))
        right = []
        for i, tokens in enumerate((50, 70)):
            p = self.d / f"r{i}.jsonl"
            write_transcript(p, 3, tokens, 5)
            right.append(str(p))
        code, out = run("--label", "sem sala", *left, ":", *right)
        self.assertEqual(code, 0, out)
        self.assertIn("execuções: sem sala=2, otimizado=2", out)
        self.assertIn("150", out)          # média 100,200
        self.assertIn("60", out)           # média 50,70

    def test_03_insufficient_sample_is_declared(self):
        a, b = self.d / "a.jsonl", self.d / "b.jsonl"
        write_transcript(a, 5, 100, 50)
        write_transcript(b, 4, 80, 40)
        code, out = run("--repeat", "3", str(a), str(b))
        self.assertEqual(code, 0, out)
        self.assertIn("AMOSTRA INSUFICIENTE", out)

    def test_04_missing_transcript_refused(self):
        a = self.d / "a.jsonl"
        write_transcript(a, 5, 100, 50)
        code, out = run(str(a), str(self.d / "nao-existe.jsonl"))
        self.assertEqual(code, 2, out)
        self.assertIn("ausente", out)

    def test_06_invalid_repeat_is_usage_error(self):
        a, b = self.d / "a.jsonl", self.d / "b.jsonl"
        write_transcript(a, 5, 100, 50)
        write_transcript(b, 4, 80, 40)
        code, out = run("--repeat", "abc", str(a), str(b))
        self.assertEqual(code, 2, out)
        self.assertNotIn("Traceback", out)

    def test_07_explicit_baseline_optimized_partition(self):
        files = {}
        for name, tokens in (("a1", 100), ("a2", 200), ("b1", 50), ("b2", 70)):
            p = self.d / f"{name}.jsonl"
            write_transcript(p, 3, tokens, 5)
            files[name] = str(p)
        code, out = run("--baseline", files["a1"], "--baseline", files["a2"],
                        "--optimized", files["b1"], "--optimized", files["b2"])
        self.assertEqual(code, 0, out)
        self.assertIn("execuções: baseline=2, otimizado=2", out)
        self.assertIn("150", out)
        self.assertIn("60", out)

    def test_05_no_percent_claims_without_sample(self):
        a, b = self.d / "a.jsonl", self.d / "b.jsonl"
        write_transcript(a, 5, 100, 50)
        write_transcript(b, 4, 80, 40)
        code, out = run(str(a), str(b))
        self.assertEqual(code, 0, out)
        self.assertNotIn("%", out)

    def test_08_multi_arm_abc_stats_and_json_report(self):
        arms = {"A": (1000, 1100, 900), "B": (800, 820, 780), "C": (700, 720, 680)}
        arm_args = []
        for lbl, vals in arms.items():
            paths = []
            for idx, v in enumerate(vals):
                p = self.d / f"{lbl}_{idx}.jsonl"
                write_transcript(p, 3, v, 50)
                paths.append(str(p))
            arm_args.extend(["--arm", f"{lbl}={','.join(paths)}"])
        jout = self.d / "abc.json"
        code, out = run(*arm_args, "--json-out", str(jout))
        self.assertEqual(code, 0, out)
        self.assertIn("-20.00%", out)  # B input_tokens: 800 vs 1000
        self.assertIn("-30.00%", out)  # C input_tokens: 700 vs 1000
        data = json.loads(jout.read_text(encoding="utf-8"))
        self.assertTrue(data["sufficient_sample"])
        self.assertEqual(data["arms"][0]["stats"]["input_tokens"]["mean"], 1000.0)
        self.assertEqual(data["arms"][0]["stats"]["input_tokens"]["stddev"], 100.0)
        self.assertEqual(data["deltas_vs_baseline"]["C"]["input_tokens"]["pct"], -30.0)

    def test_09_multi_arm_under_3_reps_suppresses_percent(self):
        a1, b1 = self.d / "ma1.jsonl", self.d / "mb1.jsonl"
        write_transcript(a1, 3, 1000, 50)
        write_transcript(b1, 3, 700, 50)
        code, out = run("--arm", f"A={a1}", "--arm", f"B={b1}")
        self.assertEqual(code, 0, out)
        self.assertIn("AMOSTRA INSUFICIENTE", out)
        self.assertNotIn("%", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
