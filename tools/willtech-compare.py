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
import json
import math
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

EXTENDED_METRIC_NAMES = (
    "input_tokens",
    "output_tokens",
    "cache_read",
    "cache_creation",
    "effective_tokens",
    "api_weighted_tokens",
    "volume_tokens",
    "num_turns",
    "duration_ms",
    "delegations",
    "reads",
    "repeated_reads",
    "room_calls",
    "rework_edits",
    "bash_failures",
    "failure_loops",
    "cost_usd",
)


def analyse_file(path):
    events = TRACE.load(path)
    a = TRACE.analyse(events)
    return a, a.get("result") or {}, events


def detailed_metrics(path, cache_weight=0.0):
    a, r, events = analyse_file(path)
    inp = float(a["usage"]["input_tokens"])
    out = float(a["usage"]["output_tokens"])
    cread = float(a["usage"]["cache_read"])
    ccreate = float(a["usage"]["cache_creation"])
    read_counts = {}
    edit_counts = {}
    room_calls = 0
    reads = 0
    for ev in events:
        if ev.get("type") != "assistant":
            continue
        for blk in TRACE.walk_content(ev):
            if blk.get("type") != "tool_use":
                continue
            tname = blk.get("name") or ""
            tinp = blk.get("input") or {}
            if tname in ("Read", "Glob", "Grep"):
                reads += 1
                key = str(tinp.get("file_path") or tinp.get("filePath")
                          or tinp.get("path") or tinp.get("pattern") or "")
                if key:
                    read_counts[key] = read_counts.get(key, 0) + 1
            elif tname in ("Edit", "Write"):
                ekey = str(tinp.get("file_path") or tinp.get("filePath") or "")
                if ekey:
                    edit_counts[ekey] = edit_counts.get(ekey, 0) + 1
            if "willtech-room" in json.dumps(tinp, ensure_ascii=False):
                room_calls += 1
    repeated_reads = sum(c - 1 for c in read_counts.values() if c > 1)
    rework_edits = sum(c - 1 for c in edit_counts.values() if c > 1)
    delegations = len(a.get("delegations", [])) + len(a.get("nested_delegations", []))
    return {
        "input_tokens": inp,
        "output_tokens": out,
        "cache_read": cread,
        "cache_creation": ccreate,
        "effective_tokens": inp + out + (cache_weight * cread),
        "api_weighted_tokens": inp + out + (0.1 * cread) + (1.25 * ccreate),
        "volume_tokens": inp + out + cread,
        "num_turns": float(r.get("num_turns") or 0),
        "duration_ms": float(r.get("duration_ms") or 0),
        "delegations": float(delegations),
        "reads": float(reads),
        "repeated_reads": float(repeated_reads),
        "room_calls": float(room_calls),
        "rework_edits": float(rework_edits),
        "bash_failures": float(a.get("bash_failures", 0)),
        "failure_loops": float(len(a.get("failure_loops", []))),
        "cost_usd": float(r.get("total_cost_usd") or 0.0),
    }


def summarize_series(values):
    n = len(values)
    if n == 0:
        return {"mean": 0.0, "stddev": 0.0, "min": 0.0, "max": 0.0, "n": 0}
    mean = sum(values) / n
    if n >= 2:
        var = sum((x - mean) ** 2 for x in values) / (n - 1)
        sd = math.sqrt(var)
    else:
        sd = 0.0
    return {
        "mean": round(mean, 2),
        "stddev": round(sd, 2),
        "min": round(min(values), 2),
        "max": round(max(values), 2),
        "n": n,
    }


def aggregate_arm(paths, cache_weight=0.0):
    runs = [detailed_metrics(p, cache_weight=cache_weight) for p in paths]
    stats = {}
    for m in EXTENDED_METRIC_NAMES:
        stats[m] = summarize_series([r[m] for r in runs])
    return stats, runs


def aggregate(paths):
    """Média por execução — só métricas observadas em TODAS as execuções."""
    n = len(paths)
    totals = {name: 0.0 for name, _ in METRICS}
    for p in paths:
        a, r, _ = analyse_file(p)
        for name, fn in METRICS:
            totals[name] += float(fn(a, r))
    return {k: v / n for k, v in totals.items()}, n


def _pct_delta(base_val, cur_val):
    if base_val == 0:
        return None
    return round(((cur_val - base_val) / base_val) * 100.0, 2)


def run_multi_arm(arms, repeat=None, cache_weight=0.0, json_out=None):
    need = max(3, repeat or 3)
    for label, paths in arms:
        if not paths:
            print(f"uso inválido: braço '{label}' sem arquivos .jsonl")
            return 2
        for p in paths:
            if not os.path.isfile(p):
                print(f"transcript ausente: {p}")
                return 2
    arm_results = []
    sufficient = True
    for label, paths in arms:
        stats, runs = aggregate_arm(paths, cache_weight=cache_weight)
        if len(paths) < need:
            sufficient = False
        arm_results.append({"label": label, "n": len(paths), "stats": stats, "runs": runs})

    base_stats = arm_results[0]["stats"]
    deltas = {}
    if sufficient:
        for ar in arm_results[1:]:
            lbl = ar["label"]
            deltas[lbl] = {}
            for m in EXTENDED_METRIC_NAMES:
                bv = base_stats[m]["mean"]
                cv = ar["stats"][m]["mean"]
                deltas[lbl][m] = {
                    "abs": round(cv - bv, 2),
                    "pct": _pct_delta(bv, cv),
                }

    hdr = f"{'métrica':<22}" + "".join(f"{ar['label'] + ' (mean±sd)':>22}" for ar in arm_results)
    if sufficient:
        for ar in arm_results[1:]:
            hdr += f"{'Δ% ' + ar['label'] + ' vs ' + arm_results[0]['label']:>16}"
    print(hdr)
    for m in EXTENDED_METRIC_NAMES:
        row = f"{m:<22}"
        for ar in arm_results:
            st = ar["stats"][m]
            cell = f"{st['mean']:.1f}±{st['stddev']:.1f}"
            row += f"{cell:>22}"
        if sufficient:
            for ar in arm_results[1:]:
                pct = deltas[ar["label"]][m]["pct"]
                pstr = f"{pct:+.2f}%" if pct is not None else "n/a"
                row += f"{pstr:>16}"
        print(row)

    counts = ", ".join(f"{ar['label']}={ar['n']}" for ar in arm_results)
    print(f"\nexecuções: {counts} (cache_weight={cache_weight})")
    if not sufficient:
        print(f"AMOSTRA INSUFICIENTE: não declare economia percentual; mínimo {need} por braço.")

    if json_out:
        report = {
            "arms": arm_results,
            "baseline": arm_results[0]["label"],
            "sufficient_sample": sufficient,
            "min_required_per_arm": need,
            "cache_weight": cache_weight,
            "deltas_vs_baseline": deltas,
        }
        os.makedirs(os.path.dirname(os.path.abspath(json_out)) or ".", exist_ok=True)
        with open(json_out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2)
    return 0


def parse_args(argv):
    repeat = None
    labels = ("baseline", "otimizado")
    rest, baseline_files, optimized_files = [], [], []
    arms = []
    cache_weight = 0.0
    json_out = None
    i = 0
    while i < len(argv):
        if argv[i] in ("--repeat",) and i + 1 < len(argv):
            try:
                repeat = int(argv[i + 1])
            except ValueError:
                return None, labels, None, None, None, cache_weight, json_out
            if repeat < 1:
                return None, labels, None, None, None, cache_weight, json_out
            i += 2
        elif argv[i] == "--cache-weight" and i + 1 < len(argv):
            try:
                cache_weight = float(argv[i + 1])
            except ValueError:
                return None, labels, None, None, None, cache_weight, json_out
            i += 2
        elif argv[i] == "--json-out" and i + 1 < len(argv):
            json_out = argv[i + 1]
            i += 2
        elif argv[i] == "--arm" and i + 1 < len(argv):
            raw_arm = argv[i + 1]
            if "=" not in raw_arm:
                print("uso inválido: --arm exige NOME=arq1.jsonl,arq2.jsonl")
                return None, labels, None, None, None, cache_weight, json_out
            albl, afiles = raw_arm.split("=", 1)
            albl = albl.strip()
            plist = [x.strip() for x in afiles.split(",") if x.strip()]
            if not albl or not plist:
                print("uso inválido: --arm exige nome e lista de arquivos .jsonl")
                return None, labels, None, None, None, cache_weight, json_out
            arms.append((albl, plist))
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
        elif argv[i] in ("--baseline", "--optimized") and i + 1 < len(argv):
            target = baseline_files if argv[i] == "--baseline" else optimized_files
            if i + 2 < len(argv) and argv[i + 2].endswith(".jsonl"):
                print(f"uso inválido: {argv[i]} consome UM transcript por flag; "
                      "repita a flag ou expanda o glob no shell")
                return None, labels, None, None, None, cache_weight, json_out
            target.append(argv[i + 1])
            i += 2
        elif argv[i].endswith(".jsonl"):
            rest.append(argv[i])
            i += 1
        else:
            i += 1
    if baseline_files or optimized_files:
        rest = baseline_files + optimized_files
        explicit = (len(baseline_files), len(optimized_files))
    else:
        explicit = None
    return repeat, labels, rest, explicit, arms, cache_weight, json_out


def main():
    argv = sys.argv[1:]
    if not argv:
        print(__doc__)
        return 2
    repeat, labels, files, explicit, arms, cache_weight, json_out = parse_args(argv)
    if files is None:
        return 2
    if arms:
        if len(arms) < 2:
            print("uso inválido: informe ao menos 2 braços (--arm A=... --arm B=...)")
            return 2
        return run_multi_arm(arms, repeat=repeat, cache_weight=cache_weight,
                             json_out=json_out)
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
    if not left or not right:
        print("uso inválido: é preciso ao menos 1 transcript de cada lado")
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
