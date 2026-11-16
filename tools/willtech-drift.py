#!/usr/bin/env python3
"""Gate determinístico de drift (WillTech 2.2).

Verifica divergências objetivas entre documentação, implementação e roster de
agentes — sem modelo, sem rede, sem inferência semântica:

  1. README ↔ filesystem: todo caminho de arquivo citado entre crases no README
     existe na árvore.
  2. Contratos ↔ ferramenta: todo subcomando citado como
     `willtech-dossie.py <sub>` existe no argparse da ferramenta, e todo
     subcomando definido está documentado em pelo menos um contrato.
  3. Roster ↔ plataformas: os mesmos agentes existem em OpenCode, Codex e
     Claude Code.

Exit 0 = sem drift; 1 = drift listado; 2 = erro de uso (árvore ilegível).
Uso: willtech-drift.py [raiz] [--dossie CAMINHO]
Com --dossie (2.2): decisões sem evidência e entradas com hash divergente
também contam como drift (reusa entry_status/read_entries do dossiê).
"""
import glob
import importlib.util
import os
import re
import sys

CITED_FILE = re.compile(
    r"`([^`\s]+\.(?:py|sh|md|yml|yaml|toml|json|webp|apng|gif|command))`")
SUB_DEFINED = re.compile(r'sub\.add_parser\("([a-z][a-z-]*)"')
SUB_CITED = re.compile(r"(?:willtech-)?dossie\.py`?\s+([a-z][a-z-]*)")
CONTRACT_GLOBS = (
    "opencode/AGENTS.md",
    "opencode/agent/*.md",
    "claude-code/agents/general/*.md",
    "claude-code/agents/especialistas/*.md",
    "claude-code/settings/*.md",
    "codex/agents/*.toml",
)


def contract_files(root):
    files = []
    for pattern in CONTRACT_GLOBS:
        files.extend(sorted(glob.glob(os.path.join(root, pattern))))
    return files


def check_readme(root, problems):
    readme = os.path.join(root, "README.md")
    if not os.path.isfile(readme):
        problems.append("README.md ausente")
        return
    text = open(readme, encoding="utf-8").read()
    for cited in sorted(set(CITED_FILE.findall(text))):
        if not os.path.exists(os.path.join(root, cited)):
            problems.append(f"README cita arquivo inexistente: {cited}")


def check_subcommands(root, problems):
    tool = os.path.join(root, "tools", "willtech-dossie.py")
    if not os.path.isfile(tool):
        problems.append("tools/willtech-dossie.py ausente")
        return
    defined = set(SUB_DEFINED.findall(open(tool, encoding="utf-8").read()))
    files = contract_files(root)
    if not files:
        problems.append("nenhum contrato encontrado")
        return
    cited = set()
    blob = ""
    for path in files:
        text = open(path, encoding="utf-8").read()
        blob += text
        cited.update(SUB_CITED.findall(text))
    for sub in sorted(cited - defined):
        problems.append(f"contrato cita subcomando inexistente: {sub}")
    for sub in sorted(defined):
        if not re.search(r"\b" + re.escape(sub) + r"\b", blob):
            problems.append(f"subcomando sem documentação em contrato: {sub}")


def check_roster(root, problems):
    sets = {}
    for platform, pattern in (
        ("opencode", "opencode/agent/*.md"),
        ("codex", "codex/agents/*.toml"),
        ("claude-code", "claude-code/agents/especialistas/*.md"),
    ):
        sets[platform] = {os.path.splitext(os.path.basename(p))[0]
                        for p in glob.glob(os.path.join(root, pattern))}
    general = glob.glob(os.path.join(root, "claude-code/agents/general/*.md"))
    sets["claude-code"] |= {os.path.splitext(os.path.basename(p))[0] for p in general}
    if not all(sets.values()):
        problems.append("roster vazio em alguma plataforma")
        return
    reference = sets["opencode"]
    for platform, names in sets.items():
        missing = reference - names
        extra = names - reference
        if missing:
            problems.append(f"{platform} sem agentes: {', '.join(sorted(missing))}")
        if extra:
            problems.append(f"{platform} com agentes a mais: {', '.join(sorted(extra))}")


def check_dossie(root, dossie, problems):
    if not os.path.isfile(dossie):
        problems.append(f"dossiê ausente: {dossie}")
        return
    tool = os.path.join(root, "tools", "willtech-dossie.py")
    if not os.path.isfile(tool):
        problems.append("tools/willtech-dossie.py ausente (checagem de dossiê)")
        return
    spec = importlib.util.spec_from_file_location("willtech_dossie", tool)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for e in mod.read_entries(dossie) or []:
        label = e.get("path") or e.get("summary", "")[:60]
        if e.get("kind") == "decision" and not (e.get("path") or e.get("output_path")):
            problems.append(f"decisão sem evidência: {label}")
            continue
        status = mod.entry_status(e)
        if status != "OK":
            problems.append(f"evidência divergente ({status}): {label}")


def main():
    args = sys.argv[1:]
    dossie = None
    if "--dossie" in args:
        i = args.index("--dossie")
        if i + 1 >= len(args):
            print("erro: --dossie exige um caminho")
            return 2
        dossie = args[i + 1]
        del args[i:i + 2]
    root = args[0] if args else "."
    if not os.path.isdir(root):
        print("erro: raiz não é um diretório")
        return 2
    problems = []
    check_readme(root, problems)
    check_subcommands(root, problems)
    check_roster(root, problems)
    if dossie:
        check_dossie(root, dossie, problems)
    for p in problems:
        print(f"DRIFT {p}")
    print(f"{len(problems)} divergências")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

# WillTech-General / WILLTECH-BH © 2026 · autoria: github.com/hebwil
