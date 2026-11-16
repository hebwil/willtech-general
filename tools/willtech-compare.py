#!/usr/bin/env python3
"""Comparação reproduzível com/sem otimizações (WillTech 2.2).

Lê dois transcripts stream-json REAIS (baseline sem hooks vs execução com
hooks) e reporta tokens, turnos, duração, falhas e loops extraídos pelo mesmo
parser da homologação (willtech_trace.py). Apenas fatos do runtime; nenhum
percentual inventado, nenhuma chamada de modelo.

Uso: willtech-compare.py <baseline.jsonl> <otimizado.jsonl>
Exit 0 = comparação impressa; 2 = uso/entrada inválida.
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location(
    "willtech_trace", os.path.join(ROOT, "claude-code", "bin", "willtech_trace.py"))
TRACE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(TRACE)


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    for p in sys.argv[1:3]:
        if not os.path.isfile(p):
            print(f"transcript ausente: {p}")
            return 2
    a = TRACE.analyse(TRACE.load(sys.argv[1]))
    b = TRACE.analyse(TRACE.load(sys.argv[2]))
    ra, rb = a.get("result") or {}, b.get("result") or {}
    rows = [
        ("input_tokens", a["usage"]["input_tokens"], b["usage"]["input_tokens"]),
        ("output_tokens", a["usage"]["output_tokens"], b["usage"]["output_tokens"]),
        ("cache_read", a["usage"]["cache_read"], b["usage"]["cache_read"]),
        ("cache_creation", a["usage"]["cache_creation"], b["usage"]["cache_creation"]),
        ("num_turns", ra.get("num_turns") or 0, rb.get("num_turns") or 0),
        ("duration_ms", ra.get("duration_ms") or 0, rb.get("duration_ms") or 0),
        ("bash_failures", a.get("bash_failures", 0), b.get("bash_failures", 0)),
        ("failure_loops", len(a.get("failure_loops", [])), len(b.get("failure_loops", []))),
    ]
    print(f"{'métrica':<16}{'baseline':>12}{'otimizado':>12}{'delta':>12}")
    for name, x, y in rows:
        print(f"{name:<16}{x:>12}{y:>12}{y - x:>+12}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# WillTech-General / WILLTECH-BH © 2026 · autoria: github.com/hebwil