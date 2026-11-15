#!/usr/bin/env python3
"""Parser de evidência para homologação WILLTECH.

Lê um transcript stream-json do Claude Code (uma linha JSON por evento) e extrai
apenas fatos observáveis: sessão, agentes disponíveis, skills, chamadas de
delegação, skill acionada, uso de tokens e negações de permissão.

Não infere. Se um campo não estiver no stream, reporta como ausente.
Uso: willtech_trace.py <transcript.jsonl> [--json]
"""
import json
import sys


def load(path):
    events = []
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def walk_content(ev):
    """Rende blocos de conteúdo de mensagens assistant/user."""
    msg = ev.get("message")
    if isinstance(msg, dict):
        content = msg.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    yield block
        elif isinstance(content, str):
            yield {"type": "text", "text": content}


def analyse(events):
    out = {
        "session_id": None,
        "model": None,
        "permission_mode": None,
        "cwd": None,
        "tools": [],
        "agents": [],
        "skills": [],
        "mcp_servers": [],
        "delegations": [],      # chamadas Agent/Task do nível principal
        "nested_delegations": [],  # chamadas feitas dentro de subagente
        "skills_invoked": [],
        "tool_names_used": [],
        "permission_denials": [],
        "usage": {"input_tokens": 0, "output_tokens": 0,
                  "cache_read": 0, "cache_creation": 0},
        "result": None,
        "errors": [],
        "init_seen": False,
        "init_fields_missing": [],
    }

    for ev in events:
        etype = ev.get("type")

        if etype == "system" and ev.get("subtype") == "init":
            out["init_seen"] = True
            out["session_id"] = ev.get("session_id") or out["session_id"]
            out["model"] = ev.get("model") or out["model"]
            out["permission_mode"] = ev.get("permissionMode") or out["permission_mode"]
            out["cwd"] = ev.get("cwd") or out["cwd"]
            out["tools"] = ev.get("tools") or out["tools"]
            out["agents"] = ev.get("agents") or out["agents"]
            out["skills"] = ev.get("skills") or out["skills"]
            out["mcp_servers"] = ev.get("mcp_servers") or out["mcp_servers"]
            for key, field in (("tools", "tools"), ("agents", "agents"),
                               ("skills", "skills"), ("mcp_servers", "mcp_servers")):
                if key not in ev:
                    out["init_fields_missing"].append(field)

        elif etype == "assistant":
            parent = ev.get("parent_tool_use_id")
            for block in walk_content(ev):
                if block.get("type") != "tool_use":
                    continue
                name = block.get("name")
                inp = block.get("input") or {}
                out["tool_names_used"].append(name)
                if name in ("Agent", "Task"):
                    rec = {
                        "subagent_type": inp.get("subagent_type"),
                        "description": inp.get("description"),
                        "prompt_chars": len(inp.get("prompt") or ""),
                        "parent_tool_use_id": parent,
                    }
                    if parent:
                        out["nested_delegations"].append(rec)
                    else:
                        out["delegations"].append(rec)
                elif name == "Skill":
                    out["skills_invoked"].append(inp.get("skill") or inp.get("command"))

            usage = ev.get("message", {}).get("usage") if isinstance(ev.get("message"), dict) else None
            if not usage:
                usage = ev.get("usage")
            if isinstance(usage, dict):
                out["usage"]["input_tokens"] += usage.get("input_tokens", 0) or 0
                out["usage"]["output_tokens"] += usage.get("output_tokens", 0) or 0
                out["usage"]["cache_read"] += usage.get("cache_read_input_tokens", 0) or 0
                out["usage"]["cache_creation"] += usage.get("cache_creation_input_tokens", 0) or 0

        elif etype == "result":
            out["result"] = {
                "subtype": ev.get("subtype"),
                "is_error": ev.get("is_error"),
                "num_turns": ev.get("num_turns"),
                "duration_ms": ev.get("duration_ms"),
                "total_cost_usd": ev.get("total_cost_usd"),
                "result": (ev.get("result") or "")[:400],
            }
            usage = ev.get("usage") or {}
            if isinstance(usage, dict) and usage:
                out["usage"]["input_tokens"] = usage.get("input_tokens", out["usage"]["input_tokens"])
                out["usage"]["output_tokens"] = usage.get("output_tokens", out["usage"]["output_tokens"])

        elif etype == "user":
            for block in walk_content(ev):
                text = block.get("content") or block.get("text") or ""
                if isinstance(text, str) and ("permission" in text.lower() and
                                              ("denied" in text.lower() or "not allowed" in text.lower()
                                               or "deny" in text.lower())):
                    out["permission_denials"].append(text[:300])

        elif etype == "error":
            out["errors"].append(str(ev.get("error") or ev)[:300])

    # dedupe preservando ordem
    for k in ("tool_names_used", "skills_invoked", "permission_denials", "errors"):
        seen, uniq = set(), []
        for v in out[k]:
            if v not in seen:
                seen.add(v)
                uniq.append(v)
        out[k] = uniq
    return out


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    data = analyse(load(sys.argv[1]))
    if "--json" in sys.argv:
        print(json.dumps(data, indent=1, ensure_ascii=False))
        return 0

    print(f"sessão        {data['session_id']}")
    print(f"modelo        {data['model']}")
    print(f"permissão     {data['permission_mode']}")
    print(f"cwd           {data['cwd']}")
    print(f"init visto    {data['init_seen']}   campos ausentes: {data['init_fields_missing'] or 'nenhum'}")
    print(f"ferramentas   {len(data['tools'])}: {', '.join(data['tools']) or '-'}")
    print(f"agentes       {len(data['agents'])}: {', '.join(str(a) for a in data['agents']) or '-'}")
    print(f"skills        {len(data['skills'])}: {', '.join(str(s) for s in data['skills']) or '-'}")
    print(f"mcp           {len(data['mcp_servers'])}: {', '.join(str(m) for m in data['mcp_servers']) or '-'}")
    print(f"delegações    {len(data['delegations'])}: "
          f"{', '.join(str(d['subagent_type']) for d in data['delegations']) or '-'}")
    print(f"aninhadas     {len(data['nested_delegations'])}: "
          f"{', '.join(str(d['subagent_type']) for d in data['nested_delegations']) or '-'}")
    print(f"skill usada   {', '.join(str(s) for s in data['skills_invoked']) or '-'}")
    print(f"ferr. usadas  {', '.join(str(t) for t in data['tool_names_used']) or '-'}")
    print(f"negadas       {len(data['permission_denials'])}")
    for d in data["permission_denials"]:
        print(f"  - {d}")
    u = data["usage"]
    print(f"tokens        in={u['input_tokens']} out={u['output_tokens']} "
          f"cache_read={u['cache_read']} cache_write={u['cache_creation']}")
    if data["result"]:
        r = data["result"]
        print(f"resultado     {r['subtype']} erro={r['is_error']} turnos={r['num_turns']} "
              f"custo=${r['total_cost_usd']}")
        if r["result"]:
            print(f"texto         {r['result']}")
    if data["errors"]:
        print("erros:")
        for e in data["errors"]:
            print(f"  - {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# WillTech / WILLTECH-BH © 2026 · autoria: github.com/hebwil
