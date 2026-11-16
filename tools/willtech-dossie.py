#!/usr/bin/env python3
"""Dossiê de evidências, cache por commit e guardas de orçamento (WillTech 2.0/2.1).

Artefato compartilhado entre comandante, General e especialistas. Grava apenas
metadados e hashes SHA-256 — nunca o conteúdo de arquivos nem segredos. Caminhos
de credenciais são recusados na entrada.

Subcomandos:
  add <dossie> --agent A --kind K --summary S [--path P] [--line N]
      [--command C] [--output-file F]
  verify <dossie>                  re-confere hashes; exit 1 se algo mudou/sumiu
  cache-check <repo> <cache.json> [--paths a,b]  HIT 0 | MISS 1 | erro 2
  cache-put <repo> <cache.json> --map-file F [--paths a,b]
  learn <dossie> --key K --resolution R --command C --output-file F [--repo DIR]
  recall <dossie> --key K [--repo DIR]   lições verificadas; USABLE | REVERIFY
  brief <dossie> [--repo DIR] [--cache F] [--paths a,b] [--key K] [--max-chars N]
      pacote de contexto somente leitura (cache + lições + guardas + verify)
  guard-attempt <dossie> --key K [--max 2]      exit 3 = parada obrigatória
  guard-delegations <dossie> [--max 8]          exit 3 = teto de delegações

Cache 2.0: chave = SHA-256(HEAD + status --porcelain); qualquer commit ou
mudança no working tree invalida o mapa. Cache 2.1 (seletivo): com --paths o
mapa cobre um escopo; mudanças fora do escopo pedido não invalidam (HIT),
mudanças dentro invalidam (MISS); novo commit sempre invalida. Lições (2.1)
só entram com evidência verificável (comando + hash da saída); recall re-confere
hash e HEAD e marca REVERIFY o que mudou, foi superseded ou perdeu evidência.
Lições carregam escopo de projeto (toplevel + remote): recall/brief devolvem
REVERIFY quando o projeto atual difere do projeto onde a lição foi aprendida.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import PurePosixPath

KINDS = ("finding", "test", "decision", "delegation")
DENY_PREFIXES = (
    ".ssh", ".config/gh", ".config/gcloud", ".aws", ".azure", ".docker",
    ".codex", ".claude", ".kube", ".gnupg", "Library/Keychains",
    "Library/Cookies", "Library/Application Support/Google/Chrome",
    "Library/Application Support/Chromium", "Library/Application Support/BraveSoftware",
    "Library/Application Support/Microsoft Edge", "Library/Application Support/Firefox",
    "Library/Application Support/Claude",
)
DENY_NAMES = (
    ".netrc", ".git-credentials", ".npmrc", ".pypirc", ".zsh_history",
    ".bash_history", ".sh_history", ".zhistory", ".python_history",
    ".node_repl_history", ".mysql_history", ".psql_history",
)
SUMMARY_CAP = 240
MAP_CAP = 20000


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def is_credential_path(path):
    s = "/" + path.strip("/") + "/"
    for pref in DENY_PREFIXES:
        if "/" + pref + "/" in s:
            return True
    if PurePosixPath(path).name in DENY_NAMES:
        return True
    return bool(re.search(r"/\.env(\.[^/]*)?$", s))


def read_entries(path):
    if not os.path.isfile(path):
        return None
    entries = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def append(path, entry):
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def git_state(repo):
    head = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"],
                          capture_output=True, text=True)
    dirty = subprocess.run(["git", "-C", repo, "status", "--porcelain"],
                           capture_output=True, text=True)
    if head.returncode != 0 or dirty.returncode != 0:
        return None, None
    return head.stdout.strip(), dirty.stdout


def git_key(repo):
    head, dirty = git_state(repo)
    if head is None:
        return None, None
    key = hashlib.sha256((head + "\n" + dirty).encode()).hexdigest()
    return key, head


def dirty_paths(porcelain):
    paths = set()
    for line in porcelain.splitlines():
        if len(line) < 4:
            continue
        p = line[3:].strip()
        if " -> " in p:
            p = p.split(" -> ", 1)[1]
        paths.add(p.strip('"'))
    return paths


def scope_list(raw):
    return [p.strip().strip("/") for p in (raw or "").split(",") if p.strip()]


def project_id(repo):
    top = subprocess.run(["git", "-C", repo, "rev-parse", "--show-toplevel"],
                         capture_output=True, text=True)
    if top.returncode != 0:
        return ""
    rem = subprocess.run(["git", "-C", repo, "remote", "get-url", "origin"],
                         capture_output=True, text=True)
    basis = top.stdout.strip() + "\n" + (rem.stdout.strip() if rem.returncode == 0 else "")
    return hashlib.sha256(basis.encode()).hexdigest()[:12]


def lesson_flags(e, head, project):
    op = e.get("output_path")
    verified = bool(op) and os.path.isfile(op) and sha256_file(op) == e.get("output_sha256")
    stale = bool(e.get("head")) and bool(head) and e["head"] != head
    scope = bool(e.get("project")) and bool(project) and e["project"] != project
    return verified, stale, scope


def entry_status(e):
    if e.get("sha256") is not None and e.get("path"):
        if not os.path.isfile(e["path"]):
            return "MISSING"
        if sha256_file(e["path"]) != e["sha256"]:
            return "CHANGED"
    if e.get("output_sha256"):
        op = e.get("output_path")
        if not op or not os.path.isfile(op):
            return "MISSING"
        if sha256_file(op) != e["output_sha256"]:
            return "CHANGED"
    return "OK"


def cache_eval(repo, cache, paths):
    key, head = git_key(repo)
    if key is None:
        return 2, "erro: não é um repositório git"
    if not os.path.isfile(cache):
        return 1, "MISS (sem cache)"
    stored = json.load(open(cache, encoding="utf-8"))
    if "dirty" not in stored:
        if stored.get("key") == key:
            return 0, f"HIT {head[:12]}"
        return 1, f"MISS {head[:12]} (cache de {str(stored.get('head'))[:12]})"
    if stored.get("head") != head:
        return 1, f"MISS {head[:12]} (novo commit; cache de {str(stored.get('head'))[:12]})"
    put_scope = stored.get("paths") or []
    req = scope_list(paths) or put_scope
    if req and put_scope and not set(req) <= set(put_scope):
        return 1, f"MISS {head[:12]} (escopo pedido fora do mapa)"
    _, porcelain = git_state(repo)
    touched = dirty_paths(porcelain)
    if req:
        touched = {p for p in touched if any(p == s or p.startswith(s + "/") for s in req)}
    if touched:
        return 1, f"MISS {head[:12]} (mudança no escopo: {sorted(touched)[0]})"
    return 0, f"HIT {head[:12]} (seletivo)" if req else f"HIT {head[:12]}"


def cmd_add(a):
    if a.kind not in KINDS:
        print(f"kind inválido: {a.kind} (use {', '.join(KINDS)})")
        return 2
    if a.path and is_credential_path(a.path):
        print(f"recusado: caminho de credencial {a.path}")
        return 2
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "agent": a.agent,
        "kind": a.kind,
        "summary": a.summary[:SUMMARY_CAP],
    }
    if a.path:
        entry["path"] = a.path
        if a.line:
            entry["line"] = a.line
        entry["sha256"] = sha256_file(a.path) if os.path.isfile(a.path) else None
    if a.command:
        entry["command"] = a.command[:SUMMARY_CAP]
    if a.output_file:
        entry["output_path"] = a.output_file
        entry["output_sha256"] = sha256_file(a.output_file)
    append(a.dossie, entry)
    print(f"registrado {a.kind} por {a.agent}")
    return 0


def cmd_verify(a):
    entries = read_entries(a.dossie)
    if entries is None:
        print("dossiê ausente")
        return 2
    bad = 0
    for e in entries:
        status = entry_status(e)
        if status != "OK":
            bad += 1
        print(f"{status:7s} {e.get('agent')} {e.get('kind')} {e.get('path') or e.get('summary', '')[:60]}")
    print(f"{len(entries)} entradas, {bad} divergentes")
    return 1 if bad else 0


def cmd_cache_check(a):
    code, line = cache_eval(a.repo, a.cache, a.paths)
    print(line)
    return code


def cmd_cache_put(a):
    key, head = git_key(a.repo)
    if key is None:
        print("erro: não é um repositório git")
        return 2
    _, porcelain = git_state(a.repo)
    map_text = open(a.map_file, encoding="utf-8").read()[:MAP_CAP]
    with open(a.cache, "w", encoding="utf-8") as fh:
        json.dump({"key": key, "head": head, "dirty": sorted(dirty_paths(porcelain)),
                   "paths": scope_list(a.paths), "map": map_text}, fh, ensure_ascii=False)
    print(f"cache gravado {head[:12]}")
    return 0


def cmd_learn(a):
    if is_credential_path(a.output_file):
        print(f"recusado: caminho de credencial {a.output_file}")
        return 2
    if not os.path.isfile(a.output_file):
        print("recusado: lição sem evidência (arquivo de saída ausente)")
        return 2
    head, _ = git_state(a.repo)
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "kind": "lesson",
        "key": a.key,
        "summary": a.resolution[:SUMMARY_CAP],
        "command": a.command[:SUMMARY_CAP],
        "output_path": a.output_file,
        "output_sha256": sha256_file(a.output_file),
        "head": head or "",
        "project": project_id(a.repo),
    }
    append(a.dossie, entry)
    print(f"lição registrada key={a.key}")
    return 0


def cmd_recall(a):
    entries = read_entries(a.dossie)
    if entries is None:
        print("dossiê ausente")
        return 2
    matches = [e for e in entries if e.get("kind") == "lesson" and e.get("key") == a.key]
    if not matches:
        print(f"NO_LESSON key={a.key}")
        return 0
    head, _ = git_state(a.repo)
    head = head or ""
    project = project_id(a.repo)
    for i, e in enumerate(matches):
        verified, stale, scope = lesson_flags(e, head, project)
        superseded = i < len(matches) - 1
        status = "USABLE" if verified and not stale and not scope and not superseded else "REVERIFY"
        print(f"{status} key={a.key} verified={'yes' if verified else 'no'} "
              f"stale={'yes' if stale else 'no'} scope={'yes' if scope else 'no'} "
              f"superseded={'yes' if superseded else 'no'} "
              f"resolution={e.get('summary', '')} command={e.get('command', '')}")
    return 0


def cmd_brief(a):
    head, _ = git_state(a.repo)
    head = head or ""
    project = project_id(a.repo)
    lines = []
    if a.cache:
        _, line = cache_eval(a.repo, a.cache, a.paths)
        lines.append(f"CACHE {line}")
    entries = read_entries(a.dossie)
    if entries is None:
        lines.append("DOSSIE absent")
    else:
        latest = {}
        for e in entries:
            if e.get("kind") == "lesson" and (not a.key or e.get("key") == a.key):
                latest[e.get("key")] = e
        for k, e in latest.items():
            verified, stale, scope = lesson_flags(e, head, project)
            if verified and not stale and not scope:
                lines.append(f"LESSON USABLE key={k} resolution={e.get('summary', '')}")
            else:
                lines.append(f"LESSON REVERIFY key={k} verified={'yes' if verified else 'no'} "
                             f"stale={'yes' if stale else 'no'} scope={'yes' if scope else 'no'}")
        att = sum(1 for e in entries if e.get("kind") == "attempt")
        dele = sum(1 for e in entries if e.get("kind") == "delegation")
        bad = sum(1 for e in entries if entry_status(e) != "OK")
        lines.append(f"GUARD attempts={att} delegations={dele}")
        lines.append(f"VERIFY {'OK' if bad == 0 else 'DIVERGENT'} entries={len(entries)} bad={bad}")
    print("\n".join(lines)[:a.max_chars])
    return 0


def cmd_guard_attempt(a):
    entries = read_entries(a.dossie) or []
    n = sum(1 for e in entries if e.get("kind") == "attempt" and e.get("key") == a.key)
    if n >= a.max:
        print(f"STOP: {n} tentativas registradas para {a.key} (teto {a.max})")
        return 3
    append(a.dossie, {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                      "kind": "attempt", "key": a.key})
    print(f"tentativa {n + 1}/{a.max} para {a.key}")
    return 0


def cmd_guard_delegations(a):
    entries = read_entries(a.dossie) or []
    n = sum(1 for e in entries if e.get("kind") == "delegation")
    if n >= a.max:
        print(f"STOP: {n} delegações registradas (teto {a.max})")
        return 3
    print(f"delegações {n}/{a.max}")
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("add")
    s.add_argument("dossie")
    s.add_argument("--agent", required=True)
    s.add_argument("--kind", required=True)
    s.add_argument("--summary", required=True)
    s.add_argument("--path")
    s.add_argument("--line", type=int)
    s.add_argument("--command")
    s.add_argument("--output-file")
    s.set_defaults(fn=cmd_add)

    s = sub.add_parser("verify")
    s.add_argument("dossie")
    s.set_defaults(fn=cmd_verify)

    s = sub.add_parser("cache-check")
    s.add_argument("repo")
    s.add_argument("cache")
    s.add_argument("--paths")
    s.set_defaults(fn=cmd_cache_check)

    s = sub.add_parser("cache-put")
    s.add_argument("repo")
    s.add_argument("cache")
    s.add_argument("--map-file", required=True)
    s.add_argument("--paths")
    s.set_defaults(fn=cmd_cache_put)

    s = sub.add_parser("learn")
    s.add_argument("dossie")
    s.add_argument("--key", required=True)
    s.add_argument("--resolution", required=True)
    s.add_argument("--command", required=True)
    s.add_argument("--output-file", required=True)
    s.add_argument("--repo", default=".")
    s.set_defaults(fn=cmd_learn)

    s = sub.add_parser("recall")
    s.add_argument("dossie")
    s.add_argument("--key", required=True)
    s.add_argument("--repo", default=".")
    s.set_defaults(fn=cmd_recall)

    s = sub.add_parser("brief")
    s.add_argument("dossie")
    s.add_argument("--repo", default=".")
    s.add_argument("--cache")
    s.add_argument("--paths")
    s.add_argument("--key")
    s.add_argument("--max-chars", type=int, default=1500)
    s.set_defaults(fn=cmd_brief)

    s = sub.add_parser("guard-attempt")
    s.add_argument("dossie")
    s.add_argument("--key", required=True)
    s.add_argument("--max", type=int, default=2)
    s.set_defaults(fn=cmd_guard_attempt)

    s = sub.add_parser("guard-delegations")
    s.add_argument("dossie")
    s.add_argument("--max", type=int, default=8)
    s.set_defaults(fn=cmd_guard_delegations)

    a = p.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())

# WillTech-General / WILLTECH-BH © 2026 · autoria: github.com/hebwil