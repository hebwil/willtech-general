#!/usr/bin/env python3
"""Executor e consolidador do Benchmark Real A/B/C (WillTech-General 3.0).

Executa ou agrega cenários reais no laboratório gratuito (llama.cpp + Qwen3 +
OpenCode V2 oficial, custo US$ 0,00), comparando sob condições idênticas:
  - Braço A: General 3.0 atual (WILLTECH_ADAPTIVE_JIT=0, WILLTECH_SPECIALIZED_MEMORY=0)
  - Braço B: General com JIT adaptativo (WILLTECH_ADAPTIVE_JIT=1, WILLTECH_SPECIALIZED_MEMORY=0)
  - Braço C: General com JIT adaptativo + RepoMap direcionado + memória especializada
             (WILLTECH_ADAPTIVE_JIT=1, WILLTECH_SPECIALIZED_MEMORY=1)

Cenários:
  - T1 (simples, sem memória prévia pertinente): leitura objetiva de src/version.py
  - T2 (média, reuso entre sessões): regras de calcular_desconto + validar_taxa
  - T3 (complexa, invalidação stale + multi-arquivo + pack de revisão independente):
    fechar_fatura -> calcular_desconto + calcular_imposto após mudança 0.05 -> 0.12

Nenhum número é simulado ou estimado: todas as métricas vêm dos JSONLs reais do
OpenCode convertidos por tools/opencode-trace.py e agregados por tools/willtech-compare.py.
"""
import argparse
import glob
import hashlib
import importlib.util
import json
import math
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

_cmp_spec = importlib.util.spec_from_file_location(
    "willtech_compare", os.path.join(HERE, "willtech-compare.py"))
COMPARE = importlib.util.module_from_spec(_cmp_spec)
_cmp_spec.loader.exec_module(COMPARE)

_oc_spec = importlib.util.spec_from_file_location(
    "opencode_trace", os.path.join(HERE, "opencode-trace.py"))
OCTRACE = importlib.util.module_from_spec(_oc_spec)
_oc_spec.loader.exec_module(OCTRACE)

SCENARIOS = {
    "T1": {
        "name": "T1_simples_sem_memoria",
        "complexity": "simples",
        "prior_memory": False,
        "prompt": (
            "Leia o arquivo src/version.py com a ferramenta read deste repositorio para confirmar a "
            "configuracao atual de release do pacote. Informe exatamente qual string "
            "literal esta definida em APP_VERSION e o que a funcao obter_versao "
            "retorna, sem modificar nenhum arquivo."
        ),
    },
    "T2": {
        "name": "T2_media_reuso_sessao",
        "complexity": "media",
        "prior_memory": True,
        "prompt": (
            "Leia os arquivos src/calc.py e src/validator.py com a ferramenta read para revisar "
            "as regras do modulo de calculo e sua dependencia para documentar a API interna. "
            "Qual e o limite maximo numerico definido em MAX_TAXA e qual excecao "
            "calcular_desconto levanta quando a taxa e invalida?"
        ),
    },
    "T3": {
        "name": "T3_complexa_stale_revisao",
        "complexity": "complexa",
        "prior_memory": True,
        "stale_invalidation": True,
        "prompt": (
            "Leia os arquivos src/invoice.py e src/tax.py com a ferramenta read para analisar "
            "o fluxo multi-arquivo de faturamento a partir da funcao fechar_fatura e suas dependencias reais "
            "no codigo atual para auditoria independente. Qual e o valor numerico vigente de ALIQUOTA_PADRAO "
            "em src/tax.py e quanto fechar_fatura(100, 0.0) retorna?"
        ),
    },
}

ARMS = (
    ("A", {"WILLTECH_ADAPTIVE_JIT": "0", "WILLTECH_SPECIALIZED_MEMORY": "0"}),
    ("B", {"WILLTECH_ADAPTIVE_JIT": "1", "WILLTECH_SPECIALIZED_MEMORY": "0"}),
    ("C", {"WILLTECH_ADAPTIVE_JIT": "1", "WILLTECH_SPECIALIZED_MEMORY": "1"}),
)


def evaluate_functional(scenario_id, oc_events):
    """Avalia precisão funcional real contra o gabarito determinístico do código."""
    texts = []
    for ev in oc_events:
        if ev.get("type") == "text":
            t = (ev.get("part") or {}).get("text") or ""
            if t:
                texts.append(t)
    joined = " ".join(texts)
    low = joined.lower()
    if scenario_id == "T1":
        return "3.4.2" in joined
    if scenario_id == "T2":
        has_max = ("0.35" in joined) or ("0,35" in joined)
        has_exc = ("valueerror" in low) or ("taxa_fora_do_intervalo" in low)
        return has_max and has_exc
    if scenario_id == "T3":
        has_new_rate = ("0.12" in joined) or ("0,12" in joined) or ("12%" in joined)
        has_total = ("112" in joined)
        # Anti-stale: não pode afirmar que a alíquota vigente ainda é 0.05 / 105
        claims_stale = (("105.0" in joined or "retorna 105" in low) and "112" not in joined)
        return has_new_rate and has_total and (not claims_stale)
    return False


def setup_lab_repo(lab_dir, scenario_id, provider_id="llamacpp", model_id="qwen3-1.7b"):
    if os.path.exists(lab_dir):
        shutil.rmtree(lab_dir)
    os.makedirs(lab_dir, exist_ok=True)
    for sub in ("tools", "opencode"):
        shutil.copytree(os.path.join(ROOT, sub), os.path.join(lab_dir, sub))
    os.makedirs(os.path.join(lab_dir, "claude-code", "bin"), exist_ok=True)
    shutil.copy2(os.path.join(ROOT, "claude-code", "bin", "willtech_trace.py"),
                 os.path.join(lab_dir, "claude-code", "bin", "willtech_trace.py"))

    subprocess.run(["git", "-C", lab_dir, "init", "-q"], check=True)
    subprocess.run(["git", "-C", lab_dir, "config", "user.email", "lab@willtech"], check=True)
    subprocess.run(["git", "-C", lab_dir, "config", "user.name", "lab"], check=True)
    if os.name == "nt":
        subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File",
                        os.path.join(lab_dir, "tools", "willtech-install.ps1"),
                        "-Repo", lab_dir, "-Platform", "opencode", "-Yes"],
                       check=True, stdout=subprocess.DEVNULL)
    else:
        subprocess.run(["sh", os.path.join(lab_dir, "tools", "willtech-install.sh"),
                        "--repo", lab_dir, "--platform", "opencode", "--yes"],
                       check=True, stdout=subprocess.DEVNULL)

    ag_dst = os.path.join(lab_dir, ".opencode", "agent")
    os.makedirs(ag_dst, exist_ok=True)
    for md in glob.glob(os.path.join(lab_dir, "opencode", "agent", "*.md")):
        shutil.copy2(md, os.path.join(ag_dst, os.path.basename(md)))

    src_dir = os.path.join(lab_dir, "src")
    tst_dir = os.path.join(lab_dir, "tests")
    os.makedirs(src_dir, exist_ok=True)
    os.makedirs(tst_dir, exist_ok=True)

    with open(os.path.join(src_dir, "version.py"), "w", encoding="utf-8") as fh:
        fh.write('APP_VERSION = "3.4.2"\n\ndef obter_versao():\n    return APP_VERSION\n')
    with open(os.path.join(src_dir, "validator.py"), "w", encoding="utf-8") as fh:
        fh.write("MIN_TAXA = 0.0\nMAX_TAXA = 0.35\n\ndef validar_taxa(taxa):\n"
                 "    return MIN_TAXA <= taxa <= MAX_TAXA\n")
    with open(os.path.join(src_dir, "calc.py"), "w", encoding="utf-8") as fh:
        fh.write("from src.validator import validar_taxa\n\n"
                 "def calcular_desconto(valor, taxa):\n"
                 "    if not validar_taxa(taxa):\n"
                 '        raise ValueError("taxa_fora_do_intervalo")\n'
                 "    return round(valor * (1.0 - taxa), 2)\n")
    with open(os.path.join(src_dir, "tax.py"), "w", encoding="utf-8") as fh:
        fh.write("ALIQUOTA_PADRAO = 0.05\n\ndef calcular_imposto(base):\n"
                 "    return round(base * ALIQUOTA_PADRAO, 2)\n")
    with open(os.path.join(src_dir, "invoice.py"), "w", encoding="utf-8") as fh:
        fh.write("from src.calc import calcular_desconto\n"
                 "from src.tax import calcular_imposto\n\n"
                 "def fechar_fatura(bruto, desconto):\n"
                 "    liquido = calcular_desconto(bruto, desconto)\n"
                 "    return round(liquido + calcular_imposto(liquido), 2)\n")
    with open(os.path.join(src_dir, "formatter.py"), "w", encoding="utf-8") as fh:
        fh.write('def formatar_brl(valor):\n    return f"R$ {valor:.2f}"\n')
    with open(os.path.join(src_dir, "audit.py"), "w", encoding="utf-8") as fh:
        fh.write('def registrar_evento(tipo, payload):\n    return {"tipo": tipo, "ok": True}\n')
    with open(os.path.join(tst_dir, "test_billing.py"), "w", encoding="utf-8") as fh:
        fh.write(
            "import unittest\n"
            "from src.invoice import fechar_fatura\n\n"
            "class TestBilling(unittest.TestCase):\n"
            "    def test_fatura_base(self):\n"
            "        self.assertGreater(fechar_fatura(100, 0.0), 100)\n\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n"
        )

    oc_cfg = {
        "$schema": "https://opencode.ai/config.json",
        "providers": {
            provider_id: {
                "package": "@opencode/ai/providers/openai-compatible",
                "settings": {"baseURL": "http://127.0.0.1:8080/v1", "apiKey": "lab-no-auth"},
                "models": {
                    model_id: {
                        "capabilities": {"tools": True},
                        "limit": {"context": 8192, "output": 2048},
                        "cost": {"input": 0, "output": 0},
                    }
                },
            }
        },
        "plugins": ["./.opencode/plugins/willtech"],
    }
    with open(os.path.join(lab_dir, "opencode.json"), "w", encoding="utf-8") as fh:
        json.dump(oc_cfg, fh, indent=2)

    wt_dir = os.path.join(lab_dir, ".willtech")
    os.makedirs(wt_dir, exist_ok=True)
    open(os.path.join(wt_dir, "enabled"), "w", encoding="utf-8").close()

    subprocess.run(["git", "-C", lab_dir, "add", "-A"], check=True)
    subprocess.run(["git", "-C", lab_dir, "commit", "-qm", "base"], check=True)

    # Semeia conhecimento de sessão anterior realista na Sala
    room_db = os.path.join(wt_dir, "room.db")
    room_py = os.path.join(lab_dir, "tools", "willtech-room.py")
    subprocess.run([sys.executable, room_py, "init", room_db, "--repo", lab_dir],
                   check=True, stdout=subprocess.DEVNULL)

    seeds = [
        ("finding", "explorer",
         "calcular_desconto(valor, taxa) em src/calc.py valida taxa via validar_taxa (MAX_TAXA=0.35 em src/validator.py) e levanta ValueError taxa_fora_do_intervalo quando invalida",
         "src/calc.py"),
        ("finding", "explorer",
         "validar_taxa(taxa) em src/validator.py aceita MIN_TAXA=0.0 ate MAX_TAXA=0.35",
         "src/validator.py"),
        ("finding", "explorer",
         "formatar_brl(valor) em src/formatter.py formata moeda com prefixo R$ e duas casas decimais",
         "src/formatter.py"),
        ("decision", "executor",
         "registrar_evento(tipo, payload) em src/audit.py mantem retorno dicionario sem mutar estado global",
         "src/audit.py"),
        ("finding", "explorer",
         "ALIQUOTA_PADRAO em src/tax.py vale 0.05 e calcular_imposto retorna round(base*0.05, 2)",
         "src/tax.py"),
    ]
    seeded_ids = []
    for kind, spec, summary, pref in seeds:
        with open(os.path.join(lab_dir, pref), "rb") as fhb:
            h = hashlib.sha256(fhb.read()).hexdigest()
        r = subprocess.run(
            [sys.executable, room_py, "put", room_db, "--repo", lab_dir,
             "--kind", kind, "--specialty", spec, "--summary", summary,
             "--path-ref", pref, "--evidence-hash", h],
            check=True, capture_output=True, text=True)
        rid = r.stdout.split("id=")[1].split()[0]
        seeded_ids.append(rid)
        subprocess.run([sys.executable, room_py, "validate", room_db,
                        "--repo", lab_dir, "--id", rid, "--by", "reviewer"],
                       check=True, stdout=subprocess.DEVNULL)

    # No cenário T3, o código de src/tax.py muda DEPOIS do registro na Sala (0.05 -> 0.12),
    # exigindo invalidação automática de evidência obsoleta (stale) + verificação real!
    if scenario_id == "T3":
        with open(os.path.join(src_dir, "tax.py"), "w", encoding="utf-8") as fh:
            fh.write("ALIQUOTA_PADRAO = 0.12\n\ndef calcular_imposto(base):\n"
                     "    return round(base * ALIQUOTA_PADRAO, 2)\n")
        subprocess.run(["git", "-C", lab_dir, "add", "src/tax.py"], check=True)
        subprocess.run(["git", "-C", lab_dir, "commit", "-qm", "update tax 0.12"], check=True)
        # Registra handoff com conclusão do executor para validar revisão independente
        subprocess.run(
            [sys.executable, room_py, "handoff-record", room_db, "--repo", lab_dir,
             "--objective", "Auditar fechar_fatura apos mudanca tributaria",
             "--evidence-ids", seeded_ids[0], "--next-owner", "reviewer",
             "--result", "CONCLUSAO_EXECUTOR_PRIVADA_NAO_VAZAR"],
            check=True, stdout=subprocess.DEVNULL)

    # Gera índice RepoMap atualizado (usado pelo Braço C; ignorado em A e B)
    rm_py = os.path.join(lab_dir, "tools", "willtech-repomap.py")
    subprocess.run([sys.executable, rm_py, "update", lab_dir,
                    os.path.join(wt_dir, "repomap.json")],
                   check=True, stdout=subprocess.DEVNULL)
    return room_db


def warm_neutral_prefix(lab_base, provider_id="llamacpp", model_id="qwen3-1.7b"):
    """Aquece o slot KV do llama-server com o prefixo neutro padrão do OpenCode
    (sem injeção da Sala) antes de cada execução, garantindo condição inicial de
    cache 100% idêntica e imparcial entre A, B e C e entre as 3 repetições."""
    warm_dir = os.path.join(lab_base, "_warmup_neutral")
    if not os.path.isdir(warm_dir):
        os.makedirs(warm_dir, exist_ok=True)
        subprocess.run(["git", "-C", warm_dir, "init", "-q"], check=True)
        oc_cfg = {
            "$schema": "https://opencode.ai/config.json",
            "providers": {
                provider_id: {
                    "package": "@opencode/ai/providers/openai-compatible",
                    "settings": {"baseURL": "http://127.0.0.1:8080/v1", "apiKey": "lab-no-auth"},
                    "models": {
                        model_id: {
                            "capabilities": {"tools": True},
                            "limit": {"context": 8192, "output": 2048},
                            "cost": {"input": 0, "output": 0},
                        }
                    },
                }
            },
        }
        with open(os.path.join(warm_dir, "opencode.json"), "w", encoding="utf-8") as fh:
            json.dump(oc_cfg, fh, indent=2)
    env = dict(os.environ)
    env["OPENCODE_CONFIG"] = os.path.join(warm_dir, "opencode.json")
    try:
        subprocess.run(
            ["opencode", "run", "--standalone", "--model", f"{provider_id}/{model_id}",
             "--format", "json", "--auto", "Responda apenas com a palavra: PRONTO"],
            cwd=warm_dir, env=env, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, timeout=90)
    except Exception:
        pass


def cmd_run_scenario(a):
    sc = SCENARIOS.get(a.scenario)
    if not sc:
        print(f"cenário inválido: {a.scenario} (use {', '.join(SCENARIOS)})")
        return 2
    out_dir = os.path.abspath(a.out_dir)
    os.makedirs(out_dir, exist_ok=True)
    lab_base = os.path.abspath(a.lab_base)

    arm_conv_files = {}
    arm_func_stats = {}
    arm_jit_stats = {}
    arm_test_results = {}
    reviewer_pack_verified = None
    stale_verified = None

    for arm_name, arm_env in ARMS:
        lab_dir = os.path.join(lab_base, f"{a.scenario}_{arm_name}")
        room_db = setup_lab_repo(lab_dir, a.scenario,
                                 provider_id=a.provider, model_id=a.model)
        conv_list = []
        func_passes = 0

        for rep in range(1, a.repeat + 1):
            if not a.skip_warmup:
                warm_neutral_prefix(lab_base, provider_id=a.provider, model_id=a.model)
            oc_jsonl = os.path.join(out_dir, f"{a.scenario}-{arm_name}-{rep}.oc.jsonl")
            oc_err = os.path.join(out_dir, f"{a.scenario}-{arm_name}-{rep}.err")
            conv_jsonl = os.path.join(out_dir, f"{a.scenario}-{arm_name}-{rep}.stream.jsonl")

            env = dict(os.environ)
            env.update(arm_env)
            env["OPENCODE_CONFIG"] = os.path.join(lab_dir, "opencode.json")

            t0 = time.monotonic()
            timed_out = False
            with open(oc_jsonl, "w", encoding="utf-8") as fo, \
                    open(oc_err, "w", encoding="utf-8") as fe:
                try:
                    subprocess.run(
                        ["opencode", "run", "--standalone",
                         "--model", f"{a.provider}/{a.model}",
                         "--format", "json", "--auto", sc["prompt"]],
                        cwd=lab_dir, env=env, stdout=fo, stderr=fe,
                        timeout=a.timeout)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    fe.write("\n[willtech-bench-abc] TIMEOUT EXPIRED\n")
            elapsed_ms = int((time.monotonic() - t0) * 1000)

            oc_events = OCTRACE.load(oc_jsonl)
            passed = (not timed_out) and evaluate_functional(a.scenario, oc_events)
            if passed:
                func_passes += 1
            conv_events = OCTRACE.convert(
                oc_events, model=f"{a.provider}/{a.model}", cwd=lab_dir)
            # Se o runtime omitiu timestamps nos eventos, usa parede medida real
            if conv_events and conv_events[-1].get("type") == "result":
                if not conv_events[-1].get("duration_ms"):
                    conv_events[-1]["duration_ms"] = elapsed_ms
            with open(conv_jsonl, "w", encoding="utf-8") as fc:
                for ev in conv_events:
                    fc.write(json.dumps(ev, ensure_ascii=False) + "\n")
            conv_list.append(conv_jsonl)
            print(f"[{a.scenario}][Braço {arm_name}][rep {rep}/{a.repeat}] "
                  f"events={len(oc_events)} functional_pass={passed} wall_ms={elapsed_ms}",
                  flush=True)

        # Coleta telemetria JIT local (sem prompts privados)
        jit_mpath = os.path.join(lab_dir, ".willtech", "jit-metrics.jsonl")
        jit_entries = []
        if os.path.isfile(jit_mpath):
            with open(jit_mpath, encoding="utf-8") as fjm:
                jit_entries = [json.loads(l) for l in fjm if l.strip()]
        prompt_jits = [x for x in jit_entries if x.get("event") == "UserPromptSubmit"]
        arm_jit_stats[arm_name] = {
            "prompt_hook_calls": len(prompt_jits),
            "avg_injected_chars": round(
                sum(x.get("injected_chars", 0) for x in prompt_jits) / len(prompt_jits), 1
            ) if prompt_jits else None,
            "room_hits": sum(1 for x in prompt_jits if x.get("room_hit")),
            "repomap_hits": sum(1 for x in prompt_jits if x.get("repomap_hit")),
        }

        if a.scenario == "T3" and arm_name == "C":
            room_py = os.path.join(lab_dir, "tools", "willtech-room.py")
            cp_res = subprocess.run(
                [sys.executable, room_py, "context-pack", room_db,
                 "--repo", lab_dir, "--for-agent", "reviewer",
                 "--handoff-id", "6", "--objective", "fechar_fatura ALIQUOTA_PADRAO"],
                capture_output=True, text=True)
            reviewer_pack_verified = (
                cp_res.returncode == 0
                and "CONCLUSAO_EXECUTOR_PRIVADA_NAO_VAZAR" not in cp_res.stdout
                and "omitido por política" in cp_res.stdout
            )
            exp_res = subprocess.run(
                [sys.executable, room_py, "export", room_db, "--repo", lab_dir],
                capture_output=True, text=True)
            stale_verified = (exp_res.returncode == 0 and '"status": "stale"' in exp_res.stdout)

        # Executa a suíte de testes unitários do laboratório para registrar integridade
        tr = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"],
            cwd=lab_dir, capture_output=True, text=True)
        arm_test_results[arm_name] = {
            "passed": tr.returncode == 0,
            "returncode": tr.returncode,
        }

        arm_conv_files[arm_name] = conv_list
        arm_func_stats[arm_name] = {
            "passes": func_passes,
            "total": a.repeat,
            "rate": round(func_passes / a.repeat, 4),
        }

    compare_json = os.path.join(out_dir, f"{a.scenario}-compare.json")
    rc = COMPARE.run_multi_arm(
        [(lbl, arm_conv_files[lbl]) for lbl, _ in ARMS],
        repeat=a.repeat, cache_weight=0.0, json_out=compare_json)
    if rc != 0:
        return rc

    with open(compare_json, encoding="utf-8") as fh:
        comp_data = json.load(fh)
    comp_data["scenario"] = a.scenario
    comp_data["scenario_meta"] = sc
    comp_data["functional"] = arm_func_stats
    comp_data["lab_tests"] = arm_test_results
    comp_data["jit_telemetry"] = arm_jit_stats
    comp_data["reviewer_pack_verified"] = reviewer_pack_verified
    comp_data["stale_invalidation_verified"] = stale_verified
    comp_data["cost_real_usd"] = 0.0
    comp_data["simulation"] = False
    with open(compare_json, "w", encoding="utf-8") as fh:
        json.dump(comp_data, fh, ensure_ascii=False, indent=2)
    return 0


def cmd_consolidate(a):
    files = sorted(glob.glob(os.path.join(a.in_dir, "*-compare.json")))
    if not files:
        print("nenhum *-compare.json encontrado em", a.in_dir)
        return 2
    scenarios_data = []
    for f in files:
        with open(f, encoding="utf-8") as fh:
            scenarios_data.append(json.load(fh))

    # Agrega todas as execuções de todos os cenários por braço A, B, C
    by_arm_runs = {"A": [], "B": [], "C": []}
    func_totals = {"A": [0, 0], "B": [0, 0], "C": [0, 0]}
    for sd in scenarios_data:
        for ar in sd["arms"]:
            lbl = ar["label"]
            by_arm_runs[lbl].extend(ar["runs"])
        for lbl, fst in sd.get("functional", {}).items():
            func_totals[lbl][0] += fst["passes"]
            func_totals[lbl][1] += fst["total"]

    overall_stats = {}
    for lbl in ("A", "B", "C"):
        runs = by_arm_runs[lbl]
        overall_stats[lbl] = {
            m: COMPARE.summarize_series([r[m] for r in runs])
            for m in COMPARE.EXTENDED_METRIC_NAMES
        }

    base_s = overall_stats["A"]
    overall_deltas = {}
    for lbl in ("B", "C"):
        overall_deltas[lbl] = {}
        for m in COMPARE.EXTENDED_METRIC_NAMES:
            bv = base_s[m]["mean"]
            cv = overall_stats[lbl][m]["mean"]
            overall_deltas[lbl][m] = {
                "abs": round(cv - bv, 2),
                "pct": COMPARE._pct_delta(bv, cv),
            }

    consolidated = {
        "benchmark": "WillTech-General 3.0 — Economia e Inteligência Real A/B/C",
        "simulation": False,
        "cost_real_usd": 0.0,
        "total_runs": sum(len(v) for v in by_arm_runs.values()),
        "scenarios": scenarios_data,
        "overall_by_arm": overall_stats,
        "overall_deltas_vs_A": overall_deltas,
        "overall_functional": {
            lbl: {
                "passes": func_totals[lbl][0],
                "total": func_totals[lbl][1],
                "rate_pct": round(100.0 * func_totals[lbl][0] / max(1, func_totals[lbl][1]), 2),
            }
            for lbl in ("A", "B", "C")
        },
    }
    with open(a.out_json, "w", encoding="utf-8") as fh:
        json.dump(consolidated, fh, ensure_ascii=False, indent=2)

    # Renderiza tabela Markdown fiel aos números reais medidos
    md = [
        "# Benchmark Real A/B/C — WillTech-General 3.0 (Custo US$ 0,00)",
        "",
        f"- **Execuções reais medidas:** {consolidated['total_runs']} sessões OpenCode V2 + Qwen3-1.7B (`simulation: false`)",
        "- **Custo financeiro real:** US$ 0,00",
        "",
        "## Consolidado Geral (Média ± Desvio Padrão por Execução)",
        "",
        "| Métrica | A (3.0 atual) | B (JIT adaptativo) | C (JIT + RepoMap + Especializada) | Δ% B vs A | Δ% C vs A |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    key_metrics = COMPARE.EXTENDED_METRIC_NAMES
    for m in key_metrics:
        sa, sb, sc = overall_stats["A"][m], overall_stats["B"][m], overall_stats["C"][m]
        pb = overall_deltas["B"][m]["pct"]
        pc = overall_deltas["C"][m]["pct"]
        pbs = f"{pb:+.2f}%" if pb is not None else "n/a"
        pcs = f"{pc:+.2f}%" if pc is not None else "n/a"
        md.append(
            f"| `{m}` | {sa['mean']:.1f} ± {sa['stddev']:.1f} | "
            f"{sb['mean']:.1f} ± {sb['stddev']:.1f} | "
            f"{sc['mean']:.1f} ± {sc['stddev']:.1f} | **{pbs}** | **{pcs}** |"
        )
    fa = consolidated["overall_functional"]["A"]
    fb = consolidated["overall_functional"]["B"]
    fc = consolidated["overall_functional"]["C"]
    md.append(
        f"| `functional_pass` | {fa['passes']}/{fa['total']} ({fa['rate_pct']:.1f}%) | "
        f"{fb['passes']}/{fb['total']} ({fb['rate_pct']:.1f}%) | "
        f"{fc['passes']}/{fc['total']} ({fc['rate_pct']:.1f}%) | "
        f"{fb['rate_pct'] - fa['rate_pct']:+.1f} pp | {fc['rate_pct'] - fa['rate_pct']:+.1f} pp |"
    )
    md.append("")
    md.append("## Detalhamento por Cenário")
    for sd in scenarios_data:
        sid = sd["scenario"]
        f_arm = sd["functional"]
        md.append("")
        md.append(f"### {sid} — `{sd['scenario_meta']['name']}`")
        md.append(
            f"- Sucesso funcional: A={f_arm['A']['passes']}/{f_arm['A']['total']}, "
            f"B={f_arm['B']['passes']}/{f_arm['B']['total']}, "
            f"C={f_arm['C']['passes']}/{f_arm['C']['total']}"
        )
        if sd.get("stale_invalidation_verified") is not None:
            md.append(f"- Invalidação `stale` verificada no SQLite: `{sd['stale_invalidation_verified']}`")
        if sd.get("reviewer_pack_verified") is not None:
            md.append(f"- Pack independente do Revisor sem conclusão do Executor: `{sd['reviewer_pack_verified']}`")
        md.append("")
        md.append("| Métrica | A | B | C | Δ% B vs A | Δ% C vs A |")
        md.append("|---|---:|---:|---:|---:|---:|")
        s_map = {ar["label"]: ar["stats"] for ar in sd["arms"]}
        d_map = sd.get("deltas_vs_baseline", {})
        for m in ("input_tokens", "output_tokens", "cache_read", "effective_tokens",
                  "duration_ms", "reads", "repeated_reads"):
            pb = d_map.get("B", {}).get(m, {}).get("pct")
            pc = d_map.get("C", {}).get(m, {}).get("pct")
            pbs = f"{pb:+.2f}%" if pb is not None else "n/a"
            pcs = f"{pc:+.2f}%" if pc is not None else "n/a"
            md.append(
                f"| `{m}` | {s_map['A'][m]['mean']:.1f}±{s_map['A'][m]['stddev']:.1f} | "
                f"{s_map['B'][m]['mean']:.1f}±{s_map['B'][m]['stddev']:.1f} | "
                f"{s_map['C'][m]['mean']:.1f}±{s_map['C'][m]['stddev']:.1f} | {pbs} | {pcs} |"
            )

    md_text = "\n".join(md) + "\n"
    if a.out_md:
        with open(a.out_md, "w", encoding="utf-8") as fh:
            fh.write(md_text)
    print(md_text)
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("run-scenario")
    s.add_argument("--scenario", required=True, choices=sorted(SCENARIOS.keys()))
    s.add_argument("--repeat", type=int, default=3)
    s.add_argument("--out-dir", required=True)
    s.add_argument("--lab-base", required=True)
    s.add_argument("--provider", default="llamacpp")
    s.add_argument("--model", default="qwen3-1.7b")
    s.add_argument("--timeout", type=int, default=300)
    s.add_argument("--skip-warmup", action="store_true")
    s.set_defaults(fn=cmd_run_scenario)

    s = sub.add_parser("consolidate")
    s.add_argument("--in-dir", required=True)
    s.add_argument("--out-json", required=True)
    s.add_argument("--out-md")
    s.set_defaults(fn=cmd_consolidate)

    a = p.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())

# WillTech-General / WILLTECH-BH © 2026 · autoria: github.com/hebwil
