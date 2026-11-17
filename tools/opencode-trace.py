#!/usr/bin/env python3
"""Adaptador fiel: OpenCode `run --format json` (JSONL) -> stream-json do Claude.

Converte eventos REAIS do runtime OpenCode V2 para o formato que
claude-code/bin/willtech_trace.py já parseia, para que tools/willtech-compare.py
compare transcripts OpenCode com o MESMO parser da homologação. Nenhum número é
inventado: cada campo vem de um evento observado.

Mapeamento (verificado contra sessão real opencode v2.3.0):
  step_start                 -> marca turno
  tool_use (part.tool)       -> assistant tool_use + user tool_result (pareados
                                por part.id); 'shell'->'Bash', 'task'/'subagent'
                                ->'Task' (delegação), read/write/edit/glob/grep
                                -> nomes Claude equivalentes.
  step_finish (part.tokens)  -> assistant usage (input/output/cache.read/write);
                                part.cost acumula o custo real (0 em modelo local).
  text                       -> texto final do resultado.
  error                      -> evento de erro.

O evento `result` final NÃO carrega `usage` (preserva a soma dos assistant usage,
como no stream real do Claude). Campos que o OpenCode não expõe (lista de
ferramentas/agentes disponíveis) são OMITIDOS do init -> o parser os reporta
ausentes, em vez de inventá-los.

Uso: opencode-trace.py <oc.jsonl> <out.streamjson> [--model ID] [--cwd PATH]
Exit 0 = convertido; 2 = entrada inválida.
"""
import json
import os
import sys

TOOL_MAP = {
    "shell": "Bash", "bash": "Bash",
    "task": "Task", "subagent": "Task", "agent": "Task",
    "read": "Read", "write": "Write", "edit": "Edit",
    "glob": "Glob", "grep": "Grep", "skill": "Skill",
}


def map_tool(name):
    return TOOL_MAP.get((name or "").lower(), name or "")


def tool_exit(state):
    meta = state.get("metadata") or {}
    inner = meta.get("metadata")
    if isinstance(inner, dict) and "exit" in inner:
        return inner.get("exit")
    return meta.get("exit")


def convert(events, model=None, cwd=None):
    out = []
    sid = None
    turns = 0
    cost = 0.0
    last_text = ""
    had_error = False
    timestamps = []
    init_emitted = False

    def emit_init():
        nonlocal init_emitted
        if init_emitted:
            return
        init = {"type": "system", "subtype": "init", "session_id": sid}
        if model:
            init["model"] = model
        if cwd:
            init["cwd"] = cwd
        out.append(init)
        init_emitted = True

    for ev in events:
        if not isinstance(ev, dict):
            continue
        etype = ev.get("type")
        ts = ev.get("timestamp")
        if isinstance(ts, (int, float)):
            timestamps.append(ts)
        sid = ev.get("sessionID") or (ev.get("part") or {}).get("sessionID") or sid
        part = ev.get("part") or {}

        if etype == "step_start":
            emit_init()

        elif etype == "tool_use":
            emit_init()
            call_id = part.get("id") or part.get("partID") or part.get("callID")
            raw_tool = part.get("tool")
            name = map_tool(raw_tool)
            state = part.get("state") or {}
            inp = dict(state.get("input") or {})
            if name == "Task" and "subagent_type" not in inp:
                for k in ("agent", "subagent", "agentName"):
                    if k in inp:
                        inp["subagent_type"] = inp[k]
                        break
            out.append({"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": call_id, "name": name, "input": inp}]}})
            status = state.get("status")
            exit_code = tool_exit(state)
            is_error = (status == "error") or (exit_code not in (0, None))
            output = state.get("output")
            if not isinstance(output, str):
                output = json.dumps(output, ensure_ascii=False) if output is not None else ""
            out.append({"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": call_id,
                 "is_error": bool(is_error), "content": output}]}})

        elif etype == "step_finish":
            emit_init()
            turns += 1
            cost += float(part.get("cost") or 0)
            tok = part.get("tokens") or {}
            cache = tok.get("cache") or {}
            out.append({"type": "assistant", "message": {"role": "assistant", "content": [],
                "usage": {"input_tokens": tok.get("input", 0) or 0,
                          "output_tokens": tok.get("output", 0) or 0,
                          "cache_read_input_tokens": cache.get("read", 0) or 0,
                          "cache_creation_input_tokens": cache.get("write", 0) or 0}}})

        elif etype == "text":
            emit_init()
            txt = part.get("text")
            if isinstance(txt, str) and txt.strip():
                last_text = txt

        elif etype == "error":
            emit_init()
            had_error = True
            err = ev.get("error") or part.get("error") or ev
            out.append({"type": "error", "error": err if isinstance(err, str) else json.dumps(err, ensure_ascii=False)})

    emit_init()
    duration = int(max(timestamps) - min(timestamps)) if len(timestamps) >= 2 else 0
    out.append({"type": "result", "subtype": "error" if had_error else "success",
                "is_error": had_error, "num_turns": turns, "duration_ms": duration,
                "total_cost_usd": cost, "result": last_text[:400]})
    return out


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


def main():
    args = [a for a in sys.argv[1:]]
    model = cwd = None
    positional = []
    i = 0
    while i < len(args):
        if args[i] == "--model" and i + 1 < len(args):
            model = args[i + 1]; i += 2
        elif args[i] == "--cwd" and i + 1 < len(args):
            cwd = args[i + 1]; i += 2
        else:
            positional.append(args[i]); i += 1
    if len(positional) != 2:
        print(__doc__)
        return 2
    src, dst = positional
    if not os.path.isfile(src):
        print("transcript OpenCode ausente:", src)
        return 2
    out = convert(load(src), model=model, cwd=cwd)
    with open(dst, "w", encoding="utf-8") as fh:
        for ev in out:
            fh.write(json.dumps(ev, ensure_ascii=False) + "\n")
    print(f"convertido {src} -> {dst} ({len(out)} eventos stream-json)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# WillTech-General / WILLTECH-BH © 2026 · autoria: github.com/hebwil