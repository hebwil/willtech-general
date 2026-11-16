#!/bin/sh
# Testes determinísticos do parser de transcript (WillTech 2.2).
# Fixture sintética stream-json: sem modelo, sem rede, sem sessão real.
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
TRACE="$ROOT/../claude-code/bin/willtech_trace.py"

if ! command -v python3 >/dev/null 2>&1; then
  printf 'SKIP  python3 ausente\n'
  exit 0
fi

TMP=$(mktemp -d "${TMPDIR:-/tmp}/willtech-trace-test.XXXXXX")
trap 'rm -rf "$TMP"' EXIT
pass=0
fail=0
ok() { pass=$((pass + 1)); printf 'PASS  %s\n' "$1"; }
bad() { fail=$((fail + 1)); printf 'FAIL  %s\n' "$1"; }
expect() {
  desc=$1; want=$2; shift 2
  "$@" >/dev/null 2>&1 && rc=0 || rc=$?
  if [ "$rc" -eq "$want" ]; then ok "$desc"; else bad "$desc (rc=$rc, esperado $want)"; fi
}

T=$TMP/transcript.jsonl
python3 - "$T" <<'PY'
import json, sys
events = [
    {"type": "system", "subtype": "init", "session_id": "s1", "model": "m",
     "tools": ["Bash", "Read", "Edit", "NotebookEdit"], "cwd": "/tmp"},
]
def call(tid, name, inp):
    events.append({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": tid, "name": name, "input": inp}]}})
def result(tid, text, error=False):
    events.append({"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": tid, "content": text, "is_error": error}]}})
call("t1", "Bash", {"command": "pytest"})
result("t1", "ERROR: pytest not found conteudo-privado-do-erro", True)
call("t2", "Bash", {"command": "pytest"})
result("t2", "ERROR: pytest not found conteudo-privado-do-erro", True)
call("t3", "Bash", {"command": "pytest"})
result("t3", "3 passed")
call("t4", "Bash", {"command": "export API_KEY=abc123secret && pytest"})
result("t4", "falha qualquer", True)
call("t5", "Read", {"file_path": "x.py"})
result("t5", "conteudo do arquivo")
events.append({"type": "result", "subtype": "success", "is_error": False,
               "num_turns": 5, "usage": {"input_tokens": 10, "output_tokens": 5}})
with open(sys.argv[1], "w", encoding="utf-8") as fh:
    for ev in events:
        fh.write(json.dumps(ev) + "\n")
PY

TXT=$TMP/saida.txt
JSON=$TMP/saida.json
expect "trace texto em transcript válido" 0 python3 "$TRACE" "$T"
python3 "$TRACE" "$T" > "$TXT"
expect "trace --json" 0 python3 "$TRACE" "$T" --json
python3 "$TRACE" "$T" --json > "$JSON"

if python3 - "$JSON" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
assert d["bash_failures"] == 3, d["bash_failures"]
assert len(d["failure_loops"]) == 1 and d["failure_loops"][0]["count"] == 2
assert d["failure_loops"][0]["guard_key"], "loop sem chave determinística"
assert len(d["lesson_candidates"]) == 1
c = d["lesson_candidates"][0]
assert c["verified"] is False
assert c["resolution_command"] == "pytest"
assert len(c["evidence"]["result_sha256"]) == 64
assert d["tools_unused"] == ["Edit", "NotebookEdit"], d["tools_unused"]
assert d["tool_usage"]["Bash"] == 4
PY
then ok "assertions JSON (loops, lição candidata, evidência, ociosas)"; else bad "assertions JSON"; fi

if grep -q 'loop suspeito' "$TXT"; then ok "texto reporta loop suspeito"; else bad "texto sem loop suspeito"; fi
if grep -q 'lição candidata (NÃO verificada)' "$TXT"; then ok "texto marca candidata como não verificada"; else bad "texto não marca candidata"; fi
if grep -q 'ferr. ociosas' "$TXT"; then ok "texto reporta ferramentas ociosas"; else bad "texto sem ociosas"; fi
if grep -q 'abc123secret' "$TXT" "$JSON"; then bad "segredo vazou na saída"; else ok "segredo redigido em comando"; fi
if grep -q 'conteudo-privado-do-erro' "$TXT" "$JSON"; then bad "conteúdo de erro vazou"; else ok "erro vira hash, não conteúdo"; fi
if grep -q 'conteudo do arquivo' "$TXT" "$JSON"; then bad "conteúdo de tool_result vazou"; else ok "tool_result não é exposto"; fi
expect "transcript ausente = erro de uso" 2 python3 "$TRACE" "$TMP/nao-existe.jsonl"

printf '\n%d PASS, %d FAIL\n' "$pass" "$fail"
[ "$fail" -eq 0 ] && printf 'Todos os testes de trace passaram.\n'
exit "$fail"

# WillTech-General / WILLTECH-BH © 2026 · autoria: github.com/hebwil
