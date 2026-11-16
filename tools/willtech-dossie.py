#!/usr/bin/env python3
"""Dossiê de evidências, cache por commit e guardas de orçamento (WillTech 2.0).

Artefato compartilhado entre comandante, General e especialistas. Grava apenas
metadados e hashes SHA-256 — nunca o conteúdo de arquivos nem segredos. Caminhos
de credenciais são recusados na entrada.

Subcomandos:
  add <dossie> --agent A --kind K --summary S [--path P] [--line N]
      [--command C] [--output-file F]
  verify <dossie>                  re-confere hashes; exit 1 se algo mudou/sumiu
  cache-check <repo> <cache.json>  HIT exit 0 | MISS exit 1 | erro exit 2
  cache-put <repo> <cache.json> --map-file F
  guard-attempt <dossie> --key K [--max 2]      exit 3 = parada obrigatória
  guard-delegations <dossie> [--max 8]          exit 3 = teto de delegações

Chave do cache = SHA-256(HEAD + status --porcelain): qualquer commit ou mudança
no working tree invalida o mapa registrado.
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


def git_key(repo):
    head = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"],
                          capture_output=True, text=True)
    dirty = subprocess.run(["git", "-C", repo, "status", "--porcelain"],
                           capture_output=True, text=True)
    if head.returncode != 0 or dirty.returncode != 0:
        return None, None
    key = hashlib.sha256((head.stdout + dirty.stdout).encode()).hexdigest()
    return key, head.stdout.strip()


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
        status = "OK"
        if e.get("sha256") is not None and e.get("path"):
            if not os.path.isfile(e["path"]):
                status = "MISSING"
            elif sha256_file(e["path"]) != e["sha256"]:
                status = "CHANGED"
        if status == "OK" and e.get("output_sha256"):
            op = e.get("output_path")
            if not op or not os.path.isfile(op):
                status = "MISSING"
            elif sha256_file(op) != e["output_sha256"]:
                status = "CHANGED"
        if status != "OK":
            bad += 1
        print(f"{status:7s} {e.get('agent')} {e.get('kind')} {e.get('path') or e.get('summary', '')[:60]}")
    print(f"{len(entries)} entradas, {bad} divergentes")
    return 1 if bad else 0


def cmd_cache_check(a):
    key, head = git_key(a.repo)
    if key is None:
        print("erro: não é um repositório git")
        return 2
    if not os.path.isfile(a.cache):
        print("MISS (sem cache)")
        return 1
    stored = json.load(open(a.cache, encoding="utf-8"))
    if stored.get("key") == key:
        print(f"HIT {head[:12]}")
        return 0
    print(f"MISS {head[:12]} (cache de {str(stored.get('head'))[:12]})")
    return 1


def cmd_cache_put(a):
    key, head = git_key(a.repo)
    if key is None:
        print("erro: não é um repositório git")
        return 2
    map_text = open(a.map_file, encoding="utf-8").read()[:MAP_CAP]
    with open(a.cache, "w", encoding="utf-8") as fh:
        json.dump({"key": key, "head": head, "map": map_text}, fh, ensure_ascii=False)
    print(f"cache gravado {head[:12]}")
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
    s.set_defaults(fn=cmd_cache_check)

    s = sub.add_parser("cache-put")
    s.add_argument("repo")
    s.add_argument("cache")
    s.add_argument("--map-file", required=True)
    s.set_defaults(fn=cmd_cache_put)

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