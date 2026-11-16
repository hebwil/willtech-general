#!/usr/bin/env python3
"""Supervisor determinístico de delegações (WillTech 2.3).

Ciclo de vida rastreável de cada delegação do General aos especialistas:
identificador, responsável, objetivo, início, limites soft/hard, estado,
resultado e evidências. Zero modelos, zero polling com IA: o runtime aciona
tick/finish por eventos; o SessionStart do willtech-auto.py reporta atrasos.

Estados: pending, running, completed, failed, timed_out, cancelled.

Honestidade de cancelamento: nenhum runtime oferece cancelamento real
confirmado da execução delegada (tabela CAPABILITIES, verificada nos
contratos oficiais). Sem --confirmed, cancel registra cancel_requested e
NUNCA afirma que o processo foi interrompido; timed_out significa apenas
tempo de espera esgotado.

Subcomandos:
  start <state.json> --agent A --goal G --task T [--parent ID]
      [--soft 300] [--hard 900] [--max-per-task 8] [--max-depth 2]
  finish <state.json> --id ID --status completed|failed [--summary S]
      [--files a,b] [--evidence F] [--pending P] [--reason R]
  tick <state.json> [--now EPOCH]   soft = sinaliza demora; hard = timed_out
  cancel <state.json> --id ID [--runtime R] [--confirmed]
  retry <state.json> --id ID --reconciled   UMA re-delegação segura
  report <state.json> --id ID       retorno estruturado ao General
  capabilities [--runtime R]        capacidades documentadas do runtime

Anti-loop: recursão limitada, trabalho duplicado e escritas concorrentes
bloqueados (lock OS no sidecar), teto por tarefa, retry único após
reconciliação; registros anteriores nunca são apagados (trabalho parcial
preservado).
"""
import argparse
import contextlib
import hashlib
import importlib.util
import json
import os
import sys
import time

if os.name != "nt":
    import fcntl

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("willtech_dossie", os.path.join(HERE, "willtech-dossie.py"))
DOSSIE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(DOSSIE)

ACTIVE = ("pending", "running")
TERMINAL = ("completed", "failed", "timed_out", "cancelled")
CAPABILITIES = {
    "opencode": {"real_cancel": False,
                 "note": "ferramenta subagent síncrona; sem API oficial de cancelamento da execução delegada"},
    "codex": {"real_cancel": False,
              "note": "hooks exigem trust; sem cancelamento oficial da execução delegada"},
    "claude-code": {"real_cancel": False,
                    "note": "hooks sem cancelamento da execução delegada"},
}


@contextlib.contextmanager
def _lock(path):
    if os.name == "nt":
        with DOSSIE._nt_lock(path):
            yield
        return
    with open(path + ".lock", "a+b") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


def read_state(path):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def update(path, fn):
    with _lock(path):
        st = read_state(path)
        st.setdefault("delegations", {})
        st.setdefault("seq", 0)
        result = fn(st)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(st, fh, ensure_ascii=False)
        os.replace(tmp, path)
        return result


def iso(epoch):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))


def cmd_start(a):
    def fn(st):
        dels = st["delegations"]
        parent = dels.get(a.parent) if a.parent else None
        if a.parent and (not parent or parent["state"] not in ACTIVE):
            return 2, "erro: parent inexistente ou já terminal; reconcilie antes de delegar"
        depth = (parent["depth"] + 1) if parent else 0
        if depth > a.max_depth:
            return 3, f"STOP: recursão bloqueada (profundidade {depth} > teto {a.max_depth})"
        active = [d for d in dels.values() if d["state"] in ACTIVE]
        if any(d["task"] == a.task and d["agent"] == a.agent for d in active):
            return 3, "STOP: trabalho duplicado já em execução para este especialista"
        if any(d["task"] == a.task for d in active):
            return 3, "STOP: escrita concorrente bloqueada; outra delegação ativa nesta tarefa"
        if sum(1 for d in dels.values() if d["task"] == a.task) >= a.max_per_task:
            return 3, f"STOP: teto de {a.max_per_task} delegações por tarefa atingido"
        st["seq"] += 1
        now = time.time()
        ident = hashlib.sha256(f"{a.task}|{a.agent}|{st['seq']}|{now}".encode()).hexdigest()[:12]
        dels[ident] = {"id": ident, "agent": a.agent, "goal": a.goal[:DOSSIE.SUMMARY_CAP],
                       "task": a.task, "parent": a.parent or "", "depth": depth,
                       "state": "running", "started": now, "started_iso": iso(now),
                       "soft": a.soft, "hard": a.hard, "slow": False,
                       "cancel_requested": False, "retries_used": 0, "retry_of": "",
                       "summary": "", "files": [], "evidence_path": "", "evidence_sha": "",
                       "pending": "", "reason": "", "finished": None}
        return 0, ident
    code, msg = update(a.state, fn)
    print(msg if code else f"running {msg}")
    return code


def cmd_finish(a):
    if a.status not in ("completed", "failed"):
        print("erro: finish aceita completed|failed")
        return 2
    def fn(st):
        d = st["delegations"].get(a.id)
        if not d:
            return 2, "erro: delegação inexistente"
        if d["state"] not in ACTIVE:
            return 2, f"erro: estado {d['state']} já terminal; reconcilie antes de nova tentativa"
        d["state"] = a.status
        d["finished"] = time.time()
        d["summary"] = a.summary[:DOSSIE.SUMMARY_CAP]
        d["files"] = DOSSIE.scope_list(a.files)
        d["pending"] = a.pending[:DOSSIE.SUMMARY_CAP]
        d["reason"] = a.reason[:DOSSIE.SUMMARY_CAP]
        if a.evidence and os.path.isfile(a.evidence):
            d["evidence_path"] = a.evidence
            d["evidence_sha"] = DOSSIE.sha256_file(a.evidence)
        return 0, f"{a.status} {a.id}"
    code, msg = update(a.state, fn)
    print(msg)
    return code


def tick_file(path, now=None):
    now = now if now is not None else time.time()
    warnings = []
    def fn(st):
        for d in st["delegations"].values():
            if d["state"] not in ACTIVE:
                continue
            elapsed = now - d["started"]
            if elapsed >= d["hard"]:
                d["state"] = "timed_out"
                d["finished"] = now
                d["reason"] = ("hard timeout: tempo de espera esgotado; interrupção do "
                               "processo NÃO confirmada pelo runtime")
                warnings.append(f"TIMED_OUT {d['id']} {d['agent']} (espera esgotada, não interrompido)")
            elif elapsed >= d["soft"] and not d["slow"]:
                d["slow"] = True
                warnings.append(f"SLOW {d['id']} {d['agent']} acima do soft timeout")
        return None
    update(path, fn)
    return warnings


def cmd_tick(a):
    warnings = tick_file(a.state, now=a.now)
    print("\n".join(warnings) if warnings else "tick: nenhuma delegação atrasada")
    return 0


def cmd_cancel(a):
    def fn(st):
        d = st["delegations"].get(a.id)
        if not d:
            return 2, "erro: delegação inexistente"
        if d["state"] not in ACTIVE:
            return 2, f"erro: estado {d['state']} já terminal"
        if a.confirmed:
            d["state"] = "cancelled"
            d["finished"] = time.time()
            d["reason"] = "cancelamento confirmado pelo runtime conforme contrato oficial"
            return 0, f"cancelled {a.id} (confirmado pelo runtime)"
        d["cancel_requested"] = True
        cap = CAPABILITIES.get(a.runtime, {"real_cancel": False, "note": "runtime desconhecido"})
        return 0, (f"cancel_requested {a.id}: {cap['note']}; solicitação registrada; "
                   "processo NÃO confirmado como interrompido")
    code, msg = update(a.state, fn)
    print(msg)
    return code


def cmd_retry(a):
    def fn(st):
        d = st["delegations"].get(a.id)
        if not d:
            return 2, "erro: delegação inexistente"
        if d["state"] not in ("failed", "timed_out", "cancelled"):
            return 3, "STOP: retry só após falha/timeout/cancelamento terminal"
        if d["retries_used"]:
            return 3, "STOP: retry único já utilizado; encerre com erro claro ou decida humano"
        if not a.reconciled:
            return 3, "STOP: reconcilie o estado (--reconciled) antes de re-delegar; trabalho parcial preservado"
        d["retries_used"] = 1
        st["seq"] += 1
        now = time.time()
        ident = hashlib.sha256(f"{d['task']}|{d['agent']}|retry|{st['seq']}|{now}".encode()).hexdigest()[:12]
        nd = dict(d)
        nd.update({"id": ident, "state": "running", "started": now, "started_iso": iso(now),
                   "slow": False, "cancel_requested": False, "retries_used": 0,
                   "retry_of": a.id, "finished": None, "reason": "", "summary": "",
                   "files": [], "pending": ""})
        st["delegations"][ident] = nd
        return 0, f"running {ident} (retry único de {a.id}; registro original preservado)"
    code, msg = update(a.state, fn)
    print(msg)
    return code


def cmd_report(a):
    st = read_state(a.state)
    d = st.get("delegations", {}).get(a.id)
    if not d:
        print("erro: delegação inexistente")
        return 2
    out = dict(d)
    out["elapsed"] = round((d["finished"] or time.time()) - d["started"], 3)
    print(json.dumps(out, ensure_ascii=False))
    return 0


def cmd_capabilities(a):
    if a.runtime:
        cap = CAPABILITIES.get(a.runtime)
        if not cap:
            print(f"erro: runtime desconhecido {a.runtime}")
            return 2
        print(json.dumps({a.runtime: cap}, ensure_ascii=False))
        return 0
    print(json.dumps(CAPABILITIES, ensure_ascii=False))
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("start")
    s.add_argument("state")
    s.add_argument("--agent", required=True)
    s.add_argument("--goal", required=True)
    s.add_argument("--task", required=True)
    s.add_argument("--parent")
    s.add_argument("--soft", type=float, default=300)
    s.add_argument("--hard", type=float, default=900)
    s.add_argument("--max-per-task", type=int, default=8)
    s.add_argument("--max-depth", type=int, default=2)
    s.set_defaults(fn=cmd_start)

    s = sub.add_parser("finish")
    s.add_argument("state")
    s.add_argument("--id", required=True)
    s.add_argument("--status", required=True)
    s.add_argument("--summary", default="")
    s.add_argument("--files", default="")
    s.add_argument("--evidence", default="")
    s.add_argument("--pending", default="")
    s.add_argument("--reason", default="")
    s.set_defaults(fn=cmd_finish)

    s = sub.add_parser("tick")
    s.add_argument("state")
    s.add_argument("--now", type=float)
    s.set_defaults(fn=cmd_tick)

    s = sub.add_parser("cancel")
    s.add_argument("state")
    s.add_argument("--id", required=True)
    s.add_argument("--runtime", default="unknown")
    s.add_argument("--confirmed", action="store_true")
    s.set_defaults(fn=cmd_cancel)

    s = sub.add_parser("retry")
    s.add_argument("state")
    s.add_argument("--id", required=True)
    s.add_argument("--reconciled", action="store_true")
    s.set_defaults(fn=cmd_retry)

    s = sub.add_parser("report")
    s.add_argument("state")
    s.add_argument("--id", required=True)
    s.set_defaults(fn=cmd_report)

    s = sub.add_parser("capabilities")
    s.add_argument("--runtime")
    s.set_defaults(fn=cmd_capabilities)

    a = p.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())

# WillTech-General / WILLTECH-BH © 2026 · autoria: github.com/hebwil