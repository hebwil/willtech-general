#!/usr/bin/env python3
"""Comparação reproduzível com/sem otimizações (WillTech 2.2 → 3.0).

Lê transcripts stream-json REAIS (baseline sem hooks vs execução com hooks) e
reporta tokens, turnos, duração, falhas e loops extraídos pelo mesmo parser da
homologação (willtech_trace.py). Apenas fatos do runtime; nenhum percentual
inventado, nenhuma chamada de modelo.

WillTech 3.0 (PASSO 6): aceita N transcripts por lado e agrega — a média por
execução é o número comparável. Uso:

  willtech-compare.py A.jsonl B.jsonl                    (1×1, compat 2.2)
  willtech-compare.py --label "sem sala" a1 a2 : "com sala" b1 b2
  willtech-compare.py --repeat 3 --baseline a*.jsonl --optimized b*.jsonl

Sem amostra suficiente (menos de --repeat execuções de um lado) o relatório
declara AMOSTRA INSUFICIENTE em vez de sugerir economia.

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

METRICS = (
    ("input_tokens", lambda a, r: a["usage"]["input_tokens"]),
    ("output_tokens", lambda a, r: a["usage"]["output_tokens"]),
    ("cache_read", lambda a, r: a["usage"]["cache_read"]),
    ("cache_creation", lambda a, r: a["usage"]["cache_creation"]),
    ("num_turns", lambda a, r: r.get("num_turns") or 0),
    ("duration_ms", lambda a, r: r.get("duration_ms") or 0),
    ("bash_failures", lambda a, r: a.get("bash_failures", 0)),
    ("failure_loops", lambda a, r: len(a.get("failure_loops", []))),
)


def analyse_file(path):
    a = TRACE.analyse(TRACE.load(path))
    return a, a.get("result") or {}


def aggregate(paths):
    """Média por execução — só métricas observadas em TODAS as execuções."""
    n = len(paths)
    totals = {name: 0.0 for name, _ in METRICS}
    for p in paths:
        a, r = analyse_file(p)
        for name, fn in METRICS:
            totals[name] += float(fn(a, r))
    return {k: v / n for k, v in totals.items()}, n


def parse_args(argv):
    repeat = None
    labels = ("baseline", "otimizado")
    rest, baseline_files, optimized_files = [], [], []
    i = 0
    while i < len(argv):
        if argv[i] in ("--repeat",) and i + 1 < len(argv):
            try:
                repeat = int(argv[i + 1])
            except ValueError:
                return None, labels, None, None        # uso inválido → exit 2
            if repeat < 1:
                return None, labels, None, None
            i += 2
        elif argv[i] == "--label" and i + 1 < len(argv):
            raw = argv[i + 1]
            if ":" in raw:
                l, r = raw.split(":", 1)
                labels = (l.strip() or labels[0], r.strip() or labels[1])
                i += 2
            else:
                labels = (raw.strip(), labels[1])
                i += 2
        elif argv[i] == "--baseline" and i + 1 < len(argv):
            baseline_files.append(argv[i + 1])
            i += 2
        elif argv[i] == "--optimized" and i + 1 < len(argv):
            optimized_files.append(argv[i + 1])
            i += 2
        elif argv[i].endswith(".jsonl"):
            rest.append(argv[i])
            i += 1
        else:
            i += 1
    if baseline_files or optimized_files:
        # partição explícita: ignora posicionais ambíguos
        rest = baseline_files + optimized_files
        explicit = (len(baseline_files), len(optimized_files))
    else:
        explicit = None
    return repeat, labels, rest, explicit


def main():
    argv = sys.argv[1:]
    if not argv:
        print(__doc__)
        return 2
    repeat, labels, files, explicit = parse_args(argv)
    if files is None:
        print("uso inválido: --repeat exige inteiro >= 1")
        return 2
    # 1×1 clássico: dois caminhos posicionais.
    if len(files) == 2 and repeat is None:
        left, right = files[:1], files[1:]
    elif explicit and len(files) >= 2:
        n_l = explicit[0]
        left, right = files[:n_l], files[n_l:]
    elif len(files) >= 2:
        half = len(files) // 2
        left, right = files[:half], files[half:]
    else:
        print("uso inválido: informe ao menos 2 transcripts .jsonl")
        return 2
    for p in left + right:
        if not os.path.isfile(p):
            print(f"transcript ausente: {p}")
            return 2
    agg_l, n_l = aggregate(left)
    agg_r, n_r = aggregate(right)
    need = repeat if repeat else 1
    print(f"{'métrica':<16}{labels[0]:>14}{labels[1]:>14}{'delta':>12}")
    for name, _ in METRICS:
        x, y = agg_l[name], agg_r[name]
        def show(v, sign=False):
            s = str(int(v)) if float(v).is_integer() else f"{v:.1f}"
            return f"+{s}" if sign and v > 0 else s
        print(f"{name:<16}{show(x):>14}{show(y):>14}{show(y - x, True):>12}")
    print(f"\nexecuções: {labels[0]}={n_l}, {labels[1]}={n_r} (média por execução)")
    if n_l < need or n_r < need:
        print("AMOSTRA INSUFICIENTE: não declare economia; repita até "
              f"--repeat={need} em cada lado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# WillTech-General / WILLTECH-BH © 2026 · autoria: github.com/hebwil
