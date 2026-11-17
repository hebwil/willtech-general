#!/usr/bin/env python3
"""Núcleo determinístico de automação WILLTECH 2.2 (hooks das 3 plataformas).

Recebe o evento do runtime (JSON no stdin) e devolve a decisão no formato
nativo da plataforma. Zero chamadas de modelo: reusa willtech-dossie.py e
willtech_trace.py por importação — nenhuma implementação duplicada.

Uso (registrado pelos hooks/plugins, não pelo usuário):
  willtech-auto.py claude|codex   # JSON nativo do hook no stdin
  willtech-auto.py opencode       # JSON normalizado pelo plugin

Saída claude/codex: JSON hookSpecificOutput/decision no stdout, exit 0.
Saída opencode: {"block": bool, "reason": str, "context": str}, exit 0.

Regras:
- Sem .willtech/enabled o núcleo não faz nada (desativação simples).
- Auxiliares (brief/prune/drift) falham aberto: nunca interrompem tarefa comum.
- Controle obrigatório (guarda de loop no PreToolUse) falha fechado: dossiê
  corrompido ou falha interna bloqueiam o comando afetado.
- Limites: stdin 1 MiB, brief/sala BUDGET_CHARS (1200), drift 10 s, estado por sessão.
- Lições/brief são DADOS em quarentena, nunca instruções superiores.
- Candidatas de lição nascem verified=false; só o comandante confirma via learn.
"""
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STDIN_CAP = 1 << 20
DRIFT_TIMEOUT = 10
COMMAND_CAP = 200


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DOSSIE = load_module("willtech_dossie", os.path.join(HERE, "willtech-dossie.py"))
TRACE_PATH = os.path.join(ROOT, "claude-code", "bin", "willtech_trace.py")
TRACE = load_module("willtech_trace", TRACE_PATH) if os.path.isfile(TRACE_PATH) else None
SUP_PATH = os.path.join(HERE, "willtech-supervisor.py")
SUPERVISOR = load_module("willtech_supervisor", SUP_PATH) if os.path.isfile(SUP_PATH) else None
ROOM_PATH = os.path.join(HERE, "willtech-room.py")
try:
    ROOM = load_module("willtech_room", ROOM_PATH) if os.path.isfile(ROOM_PATH) else None
except Exception:            # M8: carga parcial/versão antiga não pode matar o
    ROOM = None              # hook (PreToolUse é fail-closed por contrato)
# Orçamento canônico único (3.0, achado N5): o valor canônico vive na sala
# (willtech-room.BUDGET_CHARS); BRIEF_CAP vira alias de compatibilidade
# para quem já o lia. Fail-open: sem sala, 1200.
BUDGET_CHARS = 1200
if ROOM is not None:
    BUDGET_CHARS = ROOM.BUDGET_CHARS
BRIEF_CAP = BUDGET_CHARS


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def repo_root(cwd):
    try:
        r = subprocess.run(["git", "-C", cwd or ROOT, "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return ROOT


def safe_session(sid):
    return re.sub(r"[^A-Za-z0-9_-]", "", str(sid or "default"))[:64] or "default"


def read_state(path):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def write_state(path, st):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(st, fh, ensure_ascii=False)
    os.replace(tmp, path)


def dossier_health(path):
    # N2: corrupção parcial (linhas válidas + inválidas) também é falha fechado.
    # read_dossie distingue absent/ok/partial/total sem descartar em silêncio.
    entries, status, _ = DOSSIE.read_dossie(path)
    return entries or [], status in ("partial", "total")


def redact_cmd(command):
    text = " ".join((command or "").split())[:COMMAND_CAP]
    return TRACE.redact(text) if TRACE else text


def bash_key(command):
    cmd = redact_cmd(command)
    if TRACE:
        return TRACE.sig("Bash\n" + cmd)
    return hashlib.sha256(("Bash\n" + cmd).encode("utf-8", "replace")).hexdigest()[:12]


def attempt_count(entries, key):
    return sum(1 for e in entries if e.get("kind") == "attempt" and e.get("key") == key)


def response_failed(resp):
    if isinstance(resp, dict):
        for k in ("exit_code", "exitCode", "exitstatus"):
            if k in resp:
                return resp[k] != 0
        return bool(resp.get("interrupted"))
    if isinstance(resp, str):
        return resp.startswith("Exit code") and not resp.startswith("Exit code 0")
    return False


def brief_context(dossie, repo, base):
    cache = os.path.join(base, "cache.json")
    return DOSSIE.brief_text(dossie, repo,
                             cache=cache if os.path.isfile(cache) else None,
                             max_chars=BUDGET_CHARS)


def room_brief(base, repo):
    # Fail-open: sem módulo da sala, sem room.db ou erro → nenhum contexto.
    if ROOM is None:
        return None
    room_db = os.path.join(base, "room.db")
    if not os.path.isfile(room_db):
        return None
    try:
        return ROOM.query_text(room_db, repo=repo, budget=BUDGET_CHARS)
    except Exception:
        return None


def ev_start(ev, base, dossie, repo, st):
    try:
        DOSSIE.prune_entries(dossie)
    except Exception:
        pass
    parts = []
    if DOSSIE.read_entries(dossie):
        parts.append(brief_context(dossie, repo, base))
    rb = room_brief(base, repo)
    if rb:
        parts.append(rb)
    sup = os.path.join(base, "delegations.json")
    if SUPERVISOR and os.path.isfile(sup):
        warnings = SUPERVISOR.tick_file(sup)
        if warnings:
            parts.append("SUPERVISOR " + "; ".join(warnings)[:300])
    return {"context": "\n".join(parts)} if parts else {}


def ev_prompt(ev, base, dossie, repo, st):
    parts = []
    pend = st.pop("pending_context", None)
    if pend:
        parts.append(pend)
    if len(ev.get("prompt") or "") >= DOSSIE.COMPLEX_CHARS:
        parts.append(brief_context(dossie, repo, base))
    rb = room_brief(base, repo)
    if rb:
        parts.append(rb)
    return {"context": "\n".join(parts)} if parts else {}


def ev_pre_tool(ev, base, dossie, repo, st):
    if ev.get("tool_name") != "Bash":
        return {}
    entries, corrupt = dossier_health(dossie)
    if corrupt:
        return {"block": True,
                "reason": "Controle de segurança indisponível: dossiê corrompido. "
                          "Repare .willtech/dossie.jsonl antes de repetir comandos."}
    key = bash_key((ev.get("tool_input") or {}).get("command", ""))
    n = attempt_count(entries, key)
    if n >= 2:
        return {"block": True,
                "reason": f"STOP guard-attempt: {n} falhas registradas para a chave {key}. "
                          "Não repita o mesmo comando; mude a abordagem ou, ao resolver com "
                          "evidência real, registre a lição (learn)."}
    return {}


def ev_post_failure(ev, base, dossie, repo, st):
    if ev.get("tool_name") != "Bash":
        return {}
    cmd = (ev.get("tool_input") or {}).get("command", "")
    key = bash_key(cmd)
    DOSSIE.append(dossie, {"ts": now(), "kind": "attempt", "key": key})
    st["last_failure"] = {"key": key, "command": redact_cmd(cmd)}
    entries = DOSSIE.read_entries(dossie) or []
    n = attempt_count(entries, key)
    if n >= 2:
        return {"context": f"Guarda WILLTECH: {n} falhas para a chave {key}; a próxima "
                           "repetição será bloqueada. Resolva com evidência e registre "
                           "learn, ou mude a abordagem."}
    return {}


def ev_post(ev, base, dossie, repo, st, platform):
    tn = ev.get("tool_name")
    inp = ev.get("tool_input") or {}
    if tn == "Bash":
        if platform == "codex" and response_failed(ev.get("tool_response")):
            return ev_post_failure(ev, base, dossie, repo, st)
        key = bash_key(inp.get("command", ""))
        lf = st.get("last_failure")
        if lf and lf.get("key") == key and TRACE:
            resp = ev.get("tool_response") or {}
            out = resp.get("stdout", "") if isinstance(resp, dict) else str(resp)
            DOSSIE.append(dossie, {
                "ts": now(), "kind": "candidate", "key": key,
                "failed_command": lf.get("command", ""),
                "resolution_command": redact_cmd(inp.get("command", "")),
                "evidence": {"sha256": hashlib.sha256(
                    str(out).encode("utf-8", "replace")).hexdigest()},
                "verified": False,
            })
            st.pop("last_failure", None)
            return {"context": f"Lição candidata registrada (NÃO verificada) key={key}. "
                               "Confirme a evidência e registre learn para torná-la USABLE."}
        return {}
    if tn in ("Edit", "Write", "apply_patch"):
        files = st.setdefault("edited_files", [])
        paths = [inp.get("file_path")] if inp.get("file_path") else []
        if tn == "apply_patch":
            paths = re.findall(r"^\*\*\* (?:Update|Add|Delete) File: (.+)$",
                               inp.get("command", ""), re.M)
        for fp in paths:
            if fp and fp not in files and len(files) < 200:
                files.append(fp)
    return {}


def run_drift(repo, dossie):
    tool = os.path.join(repo, "tools", "willtech-drift.py")
    if not os.path.isfile(tool):
        return 0, ""
    args = [sys.executable, tool, repo]
    if os.path.isfile(dossie):
        args += ["--dossie", dossie]
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=DRIFT_TIMEOUT)
        return r.returncode, r.stdout
    except (OSError, subprocess.TimeoutExpired):
        return 0, ""


def ev_stop(ev, base, dossie, repo, st, platform):
    if ev.get("stop_hook_active"):
        return {}
    files = st.get("edited_files") or []
    if not files:
        return {}
    review_needed = len(files) >= 3 or any(
        h in f for f in files for h in DOSSIE.SECURITY_HINTS)
    if review_needed and not st.get("review_done"):
        st["review_done"] = True
        reason = ("Revisão goldfish obrigatória antes de concluir: monte o pack "
                  "independente (willtech-dossie.py review-pack: diff + critérios de "
                  "aceite + evidências verificadas, sem conclusões do implementador) "
                  "e delegue ao willtech-revisor. Classifique cada apontamento com "
                  "willtech-dossie.py resolve (fix/contest com evidência, escalate ou "
                  "discard). Uma rodada; segunda só com --new-finding citando evidência "
                  "verificável de problema novo e relevante.")
        if platform == "opencode":
            st["pending_context"] = reason
            return {}
        return {"block": True, "reason": reason}
    if not st.get("drift_done"):
        code, out = run_drift(repo, dossie)
        if code == 1:
            st["drift_done"] = True
            reason = ("Drift detectado antes de concluir:\n" + out[:600] +
                      "\nCorrija as divergências e só então declare concluído.")
            if platform == "opencode":
                st["pending_context"] = reason
                return {}
            return {"block": True, "reason": reason}
    return {}


def render(platform, name, d):
    if platform == "opencode":
        print(json.dumps({"block": bool(d.get("block")),
                          "reason": d.get("reason", ""),
                          "context": d.get("context", "")}, ensure_ascii=False))
        return
    if d.get("block"):
        if name == "PreToolUse":
            out = {"hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": d["reason"]}}
        else:
            out = {"decision": "block", "reason": d["reason"]}
        print(json.dumps(out, ensure_ascii=False))
    elif d.get("context"):
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": name, "additionalContext": d["context"]}},
            ensure_ascii=False))


def main():
    platform = sys.argv[1] if len(sys.argv) > 1 else "claude"
    raw = sys.stdin.read(STDIN_CAP)
    try:
        ev = json.loads(raw) if raw.strip() else {}
    except ValueError:
        ev = {}
    if not isinstance(ev, dict):
        ev = {}
    name = ev.get("hook_event_name", "")
    decision = {}
    cwd = ev.get("cwd") or os.getcwd()
    repo = repo_root(cwd)
    base = os.path.join(repo, ".willtech")
    dossie = os.path.join(base, "dossie.jsonl")
    if os.path.isfile(os.path.join(base, "enabled")) and name:
        stp = os.path.join(base, f"state-{safe_session(ev.get('session_id'))}.json")
        st = read_state(stp)
        try:
            if name == "SessionStart":
                decision = ev_start(ev, base, dossie, repo, st)
            elif name == "UserPromptSubmit":
                decision = ev_prompt(ev, base, dossie, repo, st)
            elif name == "PreToolUse":
                decision = ev_pre_tool(ev, base, dossie, repo, st)
            elif name == "PostToolUseFailure":
                decision = ev_post_failure(ev, base, dossie, repo, st)
            elif name == "PostToolUse":
                decision = ev_post(ev, base, dossie, repo, st, platform)
            elif name == "Stop":
                decision = ev_stop(ev, base, dossie, repo, st, platform)
        except Exception:
            if name == "PreToolUse":
                decision = {"block": True,
                            "reason": "Controle de segurança indisponível (falha interna). "
                                      "Repare o dossiê antes de repetir comandos."}
            else:
                decision = {}
        try:
            write_state(stp, st)
        except OSError:
            pass
    render(platform, name, decision)
    return 0


if __name__ == "__main__":
    sys.exit(main())

# WillTech-General / WILLTECH-BH © 2026 · autoria: github.com/hebwil