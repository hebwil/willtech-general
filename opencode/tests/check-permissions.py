#!/usr/bin/env python3
"""Validador estrutural das permissões dos agentes WillTech (OpenCode).

Compara o frontmatter de cada agente com o contrato exato de permissões
(action, resource, effect, em ordem). Qualquer inversão, remoção ou adição
de regra falha — a suíte de regressão usa isto como teste de mutação.

Uso: check-permissions.py <diretorio-agentes>
Saída: 0 = contrato respeitado; 1 = divergência; 2 = uso inválido.
"""
import os
import re
import sys

READ_WRAPPER = '*/.config/opencode/bin/willtech-read-shell "*"'
TEST_WRAPPER = '*/.config/opencode/bin/willtech-test-shell "*"'

READ_RULES = [
    ("shell", "*", "deny"),
    ("shell", READ_WRAPPER, "allow"),
    ("edit", "*", "deny"),
    ("subagent", "*", "deny"),
    ("execute", "*", "deny"),
    ("opencode_worktree_create", "*", "deny"),
    ("opencode_worktree_remove", "*", "deny"),
]

CONTRACT = {
    "willtech-explorador": READ_RULES,
    "willtech-pesquisador": READ_RULES,
    "willtech-visual": READ_RULES,
    "willtech-revisor": READ_RULES,
    "willtech-general": [r for r in READ_RULES if r[0] != "subagent"],
    "willtech-executor": [
        ("subagent", "*", "deny"),
        ("execute", "*", "deny"),
        ("shell", "git push *", "deny"),
        ("shell", "sudo *", "deny"),
        ("shell", "rm -rf *", "deny"),
    ],
    "willtech-testador": [
        ("edit", "*", "deny"),
        ("subagent", "*", "deny"),
        ("execute", "*", "deny"),
        ("shell", "*", "deny"),
        ("shell", TEST_WRAPPER, "allow"),
        ("opencode_worktree_create", "*", "deny"),
        ("opencode_worktree_remove", "*", "deny"),
    ],
}


def unquote(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def parse_rules(path):
    text = open(path, encoding="utf-8").read()
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    if not m:
        return None, "sem frontmatter"
    fm = m.group(1)
    if not re.search(r"^mode:\s*subagent\s*$", fm, re.M):
        return None, "mode: subagent ausente"
    rules = []
    in_perms = False
    current = {}
    for line in fm.splitlines():
        if re.match(r"^permissions:\s*$", line):
            in_perms = True
            continue
        if not in_perms:
            continue
        if re.match(r"^\S", line):
            break
        ma = re.match(r"^\s*-\s*action:\s*(.+)$", line)
        mr = re.match(r"^\s*resource:\s*(.+)$", line)
        me = re.match(r"^\s*effect:\s*(.+)$", line)
        if ma:
            if current:
                rules.append(current)
            current = {"action": unquote(ma.group(1))}
        elif mr and current:
            current["resource"] = unquote(mr.group(1))
        elif me and current:
            current["effect"] = unquote(me.group(1))
    if current:
        rules.append(current)
    triples = []
    for r in rules:
        if set(r) != {"action", "resource", "effect"}:
            return None, f"regra incompleta: {r}"
        triples.append((r["action"], r["resource"], r["effect"]))
    return triples, None


def main():
    if len(sys.argv) != 2 or not os.path.isdir(sys.argv[1]):
        print("uso: check-permissions.py <diretorio-agentes>")
        return 2
    agent_dir = sys.argv[1]
    failures = 0
    for name, expected in sorted(CONTRACT.items()):
        path = os.path.join(agent_dir, name + ".md")
        if not os.path.isfile(path):
            print(f"FALHA {name}: arquivo ausente")
            failures += 1
            continue
        actual, err = parse_rules(path)
        if err:
            print(f"FALHA {name}: {err}")
            failures += 1
            continue
        if actual != expected:
            print(f"FALHA {name}: permissões divergem do contrato")
            for i, (a, e) in enumerate(zip(actual, expected)):
                if a != e:
                    print(f"  regra {i}: obtido {a} | esperado {e}")
            if len(actual) != len(expected):
                print(f"  contagem: obtido {len(actual)} | esperado {len(expected)}")
                for extra in actual[len(expected):]:
                    print(f"  regra extra: {extra}")
                for missing in expected[len(actual):]:
                    print(f"  regra ausente: {missing}")
            failures += 1
        else:
            print(f"OK    {name}: {len(actual)} regras conforme contrato")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

# WillTech-General / WILLTECH-BH © 2026 · autoria: github.com/hebwil