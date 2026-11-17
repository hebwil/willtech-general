#!/usr/bin/env python3
"""Teste determinístico do adaptador OpenCode->stream-json (tools/opencode-trace.py).

Fixtures SINTÉTICAS no formato REAL observado do OpenCode v2.3.0 (shell/subagent,
state.metadata.metadata.exit, step_finish.tokens). Isto é teste da FERRAMENTA de
conversão, não benchmark: nenhum número de economia é reivindicado aqui.
"""
import importlib.util
import os
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(REPO, rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


TRACE = _load("opencode_trace", "tools/opencode-trace.py")
PARSER = _load("willtech_trace", "claude-code/bin/willtech_trace.py")


def shell(call_id, command, exit_code, status="completed", ts=1100):
    return {"type": "tool_use", "timestamp": ts, "sessionID": "ses_test",
            "part": {"id": call_id, "type": "tool", "tool": "shell",
                     "state": {"status": status, "input": {"command": command},
                               "output": "ok\n",
                               "metadata": {"metadata": {"exit": exit_code}},
                               "time": {"start": ts, "end": ts + 100}}}}


def subagent(call_id, agent, ts=1300):
    return {"type": "tool_use", "timestamp": ts, "sessionID": "ses_test",
            "part": {"id": call_id, "type": "tool", "tool": "subagent",
                     "state": {"status": "completed",
                               "input": {"agent": agent, "description": "d", "prompt": "p"},
                               "output": "done", "time": {"start": ts, "end": ts + 100}}}}


def finish(ti, to, cr, cw=0, ts=1200, reason="tool-calls"):
    return {"type": "step_finish", "timestamp": ts, "sessionID": "ses_test",
            "part": {"type": "step-finish", "reason": reason, "cost": 0,
                     "tokens": {"input": ti, "output": to, "reasoning": 0,
                                "cache": {"read": cr, "write": cw}}}}


def start(ts=1000):
    return {"type": "step_start", "timestamp": ts, "sessionID": "ses_test",
            "part": {"type": "step-start"}}


def text(t, ts=1500):
    return {"type": "text", "timestamp": ts, "sessionID": "ses_test",
            "part": {"type": "text", "text": t}}


class TestAdapter(unittest.TestCase):
    def test_map_tool(self):
        self.assertEqual(TRACE.map_tool("shell"), "Bash")
        self.assertEqual(TRACE.map_tool("subagent"), "Task")
        self.assertEqual(TRACE.map_tool("task"), "Task")
        self.assertEqual(TRACE.map_tool("grep"), "Grep")

    def test_tool_exit_nested_metadata(self):
        self.assertEqual(TRACE.tool_exit({"metadata": {"metadata": {"exit": 3}}}), 3)
        self.assertEqual(TRACE.tool_exit({"metadata": {"exit": 4}}), 4)
        self.assertIsNone(TRACE.tool_exit({}))

    def test_delegation_tokens_and_no_result_usage(self):
        evs = [start(), shell("c1", "echo ok", 0), finish(100, 10, 50),
               subagent("c2", "willtech-explorador"), finish(200, 20, 150, reason="stop"),
               text("resultado final")]
        conv = TRACE.convert(evs, model="llamacpp/qwen3-1.7b")
        out = PARSER.analyse(conv)
        self.assertEqual([d["subagent_type"] for d in out["delegations"]],
                         ["willtech-explorador"])
        self.assertIn("Bash", out["tool_names_used"])
        self.assertIn("Task", out["tool_names_used"])
        self.assertEqual(out["usage"]["input_tokens"], 300)
        self.assertEqual(out["usage"]["output_tokens"], 30)
        self.assertEqual(out["usage"]["cache_read"], 200)
        self.assertEqual(out["bash_failures"], 0)
        self.assertIn("resultado final", (out["result"] or {}).get("result", ""))
        results = [e for e in conv if e.get("type") == "result"]
        self.assertTrue(results)
        self.assertNotIn("usage", results[-1])
        self.assertIn("tools", out["init_fields_missing"])
        self.assertIn("agents", out["init_fields_missing"])

    def test_bash_failure_and_loop(self):
        evs = [start(), shell("c1", "make build", 1, ts=1100),
               shell("c2", "make build", 1, ts=1300), finish(50, 5, 10),
               text("falhou")]
        out = PARSER.analyse(TRACE.convert(evs))
        self.assertEqual(out["bash_failures"], 2)
        self.assertTrue(out["failure_loops"])
        self.assertEqual(out["failure_loops"][0]["count"], 2)

    def test_error_tool_status_marks_failure(self):
        evs = [start(), shell("c1", "echo x", 0, status="error"), finish(10, 1, 0),
               text("err")]
        out = PARSER.analyse(TRACE.convert(evs))
        self.assertEqual(out["bash_failures"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)