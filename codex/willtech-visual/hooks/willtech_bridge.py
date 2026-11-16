#!/usr/bin/env python3
"""Ponte de hooks oficiais do Codex -> eventos normalizados do visualizador.

Lê o JSON de stdin enviado pelo runtime do Codex (contrato oficial de hooks:
session_id, hook_event_name, agent_id, agent_type, ...) e acrescenta UMA linha
normalizada ao feed JSONL consumido pelo visualizador complementar. Não chama
modelo, não faz rede, não altera o aplicativo Codex. Fail-open: qualquer erro
resulta em saída silenciosa (exit 0) para nunca bloquear a sessão real.

Eventos normalizados: {agent, state, at, session, event, permissions}
"""
import json
import os
import sys
import time

NAMES = ["general", "explorador", "pesquisador", "visual", "executor", "testador", "revisor"]


def willtech_id(text):
    if not text:
        return None
    text = str(text)
    if text.startswith("willtech-"):
        return text if text[len("willtech-"):] in NAMES else None
    return f"willtech-{text}" if text in NAMES else None


def normalize(payload):
    event = payload.get("hook_event_name")
    session = payload.get("agent_id") or payload.get("session_id") or "main"
    at = int(time.time() * 1000)
    agent = willtech_id(payload.get("agent_type")) or willtech_id(payload.get("agent_id"))
    general = "willtech-general"
    if event == "SessionStart":
        return {"agent": general, "state": "waiting", "session": session, "event": event, "at": at}
    if event == "SessionEnd":
        return {"agent": general, "state": "waiting", "session": session, "event": event, "at": at, "reset": True}
    if event == "UserPromptSubmit":
        return {"agent": general, "state": "working", "session": session, "event": event, "at": at}
    if event == "Stop":
        return {"agent": general, "state": "completed", "session": session, "event": event, "at": at}
    if event == "Interrupt":
        return {"agent": general, "state": "blocked", "session": session, "event": event, "at": at}
    if event == "PermissionRequest":
        return {"agent": general, "state": "blocked", "session": session, "event": event, "at": at, "permissions": True}
    if event == "SubagentStart":
        return {"agent": agent or general, "state": "working", "session": session, "event": event, "at": at}
    if event == "SubagentStop":
        return {"agent": agent or general, "state": "completed", "session": session, "event": event, "at": at}
    if event in ("PreToolUse", "PostToolUse") and agent:
        state = "working" if event == "PreToolUse" else "completed"
        return {"agent": agent, "state": state, "session": session, "event": event, "at": at}
    return None


def main():
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        record = normalize(payload)
        if record is None:
            return
        feed = os.environ.get("WILLTECH_CODEX_FEED")
        if not feed:
            cwd = payload.get("cwd") or os.getcwd()
            feed = os.path.join(cwd, ".codex", "willtech-events.jsonl")
        os.makedirs(os.path.dirname(feed), exist_ok=True)
        with open(feed, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


if __name__ == "__main__":
    main()