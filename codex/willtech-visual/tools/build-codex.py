#!/usr/bin/env python3
"""Gera os artefatos do visualizador complementar Codex a partir do núcleo
compartilhado (activity.cjs) e dos mascotes oficiais (docs/assets/*.webp).
Sem dependências externas; apenas stdlib. O núcleo é copiado VERBATIM (corpo)
para core.js como ESM, garantindo uma única camada de interpretação de estado.
"""
import base64
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(os.path.dirname(ROOT))  # worktree root
CORE_SRC = os.path.join(REPO, "opencode", "plugins", "willtech", "visual", "activity.cjs")
ASSETS = os.path.join(REPO, "docs", "assets")
OUT = os.path.join(ROOT, "viewer")

IDS = ["general", "explorador", "pesquisador", "visual", "executor", "testador", "revisor"]


def core_body():
    with open(CORE_SRC, encoding="utf-8") as fh:
        text = fh.read()
    body = text.replace("module.exports = { AGENTS, EVENTS, projectAgents };", "").rstrip()
    return body


def build_core():
    body = core_body()
    esm = body + "\n\nexport { AGENTS, EVENTS, projectAgents };\n"
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "core.js"), "w", encoding="utf-8") as fh:
        fh.write(esm)
    return esm


def build_assets():
    lines = ["// Mascotes oficiais (docs/assets). Gerado por tools/build-codex.py.",
             "export const IMG = {"]
    for name in IDS:
        path = os.path.join(ASSETS, f"willtech-{name}.webp")
        with open(path, "rb") as fh:
            b64 = base64.b64encode(fh.read()).decode("ascii")
        lines.append(f'  "willtech-{name}": "data:image/webp;base64,{b64}",')
    lines.append("};")
    with open(os.path.join(OUT, "assets.js"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def main():
    build_core()
    build_assets()
    print("viewer/core.js + viewer/assets.js gerados")


if __name__ == "__main__":
    main()