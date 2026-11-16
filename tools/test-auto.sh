#!/bin/sh
# Suíte determinística da automação nativa WILLTECH 2.2 (sem custo de modelo).
# Cobre os 7 itens objetivos: (1) gatilho automático em tarefa complexa,
# (2) tarefa simples sem processamento extra, (3) memória entre sessões e
# projetos, (4) bloqueio de loop e reentrada, (5) permissões preservadas,
# (6) falha segura e recuperação, (7) instalar/desativar/reverter.
# Eventos simulados alimentam o núcleo exatamente como o runtime faria.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
TMP=$(mktemp -d "${TMPDIR:-/tmp}/willtech-auto.XXXXXX")
trap 'rm -rf "$TMP"' EXIT
PASS=0; FAIL=0
ok() { PASS=$((PASS + 1)); printf 'ok   %s\n' "$1"; }
no() { FAIL=$((FAIL + 1)); printf 'FAIL %s\n' "$1"; }
check() { if [ "$1" = 0 ]; then ok "$2"; else no "$2"; fi; }
has() { printf '%s' "$1" | grep -q "$2"; }

LAB=$TMP/repo
mkdir -p "$LAB/tools" "$LAB/claude-code/bin" "$LAB/.willtech"
cp "$ROOT/tools/willtech-auto.py" "$ROOT/tools/willtech-dossie.py" \
   "$ROOT/tools/willtech-drift.py" "$LAB/tools/"
cp "$ROOT/claude-code/bin/willtech_trace.py" "$LAB/claude-code/bin/"
git -C "$LAB" init -q
git -C "$LAB" -c user.email=lab@local -c user.name=lab commit -q --allow-empty -m init
: > "$LAB/.willtech/enabled"
D=$LAB/.willtech/dossie.jsonl
AUTO="$LAB/tools/willtech-auto.py"
DOSSIE="$LAB/tools/willtech-dossie.py"
ev() { printf '%s' "$2" | python3 "$AUTO" "$1"; }
J() { printf '{"hook_event_name":"%s","session_id":"%s","cwd":"%s"%s}' "$1" "$2" "$LAB" "$3"; }
# Falhas de verificação abaixo devem ser reportadas (FAIL), não abortar a suíte.
set +e

# --- (2) sessão nova sem memória: zero contexto -----------------------------
OUT=$(ev claude "$(J SessionStart s1 '')")
[ -z "$OUT" ]; check $? "sessão nova sem memória: nenhum contexto injetado"

# --- (1)(3) lição verificada entra no brief automático ----------------------
printf 'ok\n' > "$TMP/out.txt"
python3 "$DOSSIE" learn "$D" --key k1 --resolution "usar pytest -q" \
  --command "pytest -q" --output-file "$TMP/out.txt" --repo "$LAB" > /dev/null
OUT=$(ev claude "$(J SessionStart s2 '')")
has "$OUT" 'LESSON USABLE key=k1' && has "$OUT" 'QUARENTENA'
check $? "SessionStart injeta lição USABLE em quarentena"
OUT=$(ev claude "$(J SessionStart s3 '')")
has "$OUT" 'LESSON USABLE key=k1'
check $? "memória persiste entre sessões distintas"
OUT=$(python3 "$DOSSIE" recall "$D" --key k1 --repo "$ROOT")
has "$OUT" '^REVERIFY'
check $? "lição de outro projeto chega REVERIFY (sem contaminação)"

# --- (2) prompt simples não dispara brief -----------------------------------
OUT=$(ev claude "$(J UserPromptSubmit s4 ',"prompt":"oi"')")
[ -z "$OUT" ]; check $? "prompt simples: zero processamento extra"

# --- (1) prompt complexo dispara brief automaticamente ----------------------
LONG=$(python3 -c 'print("x" * 250)')
OUT=$(ev claude "$(J UserPromptSubmit s5 ",\"prompt\":\"$LONG\"")")
has "$OUT" 'LESSON USABLE key=k1'
check $? "prompt complexo (>=200 chars): brief automático"

# --- (4) loop: 2 falhas registradas, 3ª repetição bloqueada -----------------
FAIL_EV=$(J PostToolUseFailure s6 ',"tool_name":"Bash","tool_input":{"command":"pytest -q"},"error":"Exit code 1"')
ev claude "$FAIL_EV" > /dev/null
OUT=$(ev claude "$FAIL_EV")
has "$OUT" 'bloqueada'
check $? "2ª falha avisa que a próxima repetição será bloqueada"
PRE=$(J PreToolUse s6 ',"tool_name":"Bash","tool_input":{"command":"pytest -q"}')
OUT=$(ev claude "$PRE")
has "$OUT" '"permissionDecision": "deny"'
check $? "PreToolUse nega a 3ª repetição (guarda de loop)"
OUT=$(ev claude "$(J PreToolUse s6 ',"tool_name":"Bash","tool_input":{"command":"ls -la"}')")
[ -z "$OUT" ]; check $? "comando diferente não é bloqueado"

# --- (6) recuperação: sucesso após falha gera candidata NÃO verificada ------
OUT=$(ev claude "$(J PostToolUse s6 ',"tool_name":"Bash","tool_input":{"command":"pytest -q"},"tool_response":{"stdout":"1 passed"}')")
has "$OUT" 'candidata' && grep -q '"kind": "candidate"' "$D" && grep -q '"verified": false' "$D"
check $? "falhou→sucedeu registra candidata verified=false"

# --- (6) falha fechado: dossiê corrompido bloqueia o comando ----------------
cp "$D" "$TMP/dossie.bak"
printf 'nao-e-json\n' > "$D"
OUT=$(ev claude "$(J PreToolUse s7 ',"tool_name":"Bash","tool_input":{"command":"ls"}')")
has "$OUT" 'corrompido'
check $? "dossiê corrompido: PreToolUse falha fechado (deny)"
cp "$TMP/dossie.bak" "$D"

# --- (6) falha aberto: auxiliar quebrado não interrompe ---------------------
printf 'lixo' > "$LAB/.willtech/cache.json"
ev claude "$(J SessionStart s8 '')" > /dev/null
check $? "cache corrompido: SessionStart falha aberto (exit 0)"
rm -f "$LAB/.willtech/cache.json"

# --- (4) Stop proporcional + reentrada --------------------------------------
OUT=$(ev claude "$(J Stop s9 '')")
[ -z "$OUT" ]; check $? "Stop sem edições: nenhum gate"
for f in a.py b.py c.py; do
  ev claude "$(J PostToolUse s9 ",\"tool_name\":\"Edit\",\"tool_input\":{\"file_path\":\"$f\"}")" > /dev/null
done
OUT=$(ev claude "$(J Stop s9 '')")
has "$OUT" 'revisor'
check $? "Stop com 3 arquivos exige revisão goldfish (1ª vez)"
OUT=$(ev claude "$(J Stop s9 '')")
has "$OUT" 'Drift'
check $? "2º Stop roda drift e bloqueia divergência (1ª vez)"
OUT=$(ev claude "$(J Stop s9 '')")
[ -z "$OUT" ]; check $? "3º Stop libera (gates uma vez por sessão, sem loop)"
OUT=$(ev claude "$(J Stop s9 ',"stop_hook_active":true')")
[ -z "$OUT" ]; check $? "stop_hook_active=true: sem reentrada"

# --- (5) render opencode + permissões preservadas ---------------------------
OUT=$(ev opencode "$PRE")
has "$OUT" '"block": true'
check $? "núcleo opencode devolve block:true (plugin lança throw)"
OUT=$(ev opencode "$(J UserPromptSubmit s10 ',"prompt":"oi"')")
has "$OUT" '"block": false'
check $? "núcleo opencode em tarefa simples: block:false"
if grep -q 'permissionDecision": "allow' "$AUTO" || grep -q 'updatedInput' "$AUTO"; then
  no "núcleo nunca concede permissão nova"
else
  ok "núcleo nunca concede permissão nova (sem allow/updatedInput)"
fi

# --- (6) recuperação: learn verificado libera a guarda de loop ----------------
KEY=$(python3 -c 'import importlib.util,sys; s=importlib.util.spec_from_file_location("a",sys.argv[1]); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); print(m.bash_key("pytest -q"))' "$AUTO")
python3 "$DOSSIE" learn "$D" --key "$KEY" --resolution "fixture ok" \
  --command "pytest -q" --output-file "$TMP/out.txt" --repo "$LAB" > /dev/null
OUT=$(ev claude "$PRE")
[ -z "$OUT" ]; check $? "learn com evidência libera a guarda (recuperação pós-resolução)"

# --- (3) higiene: prune remove superseded e evidência ausente ---------------
python3 "$DOSSIE" learn "$D" --key k2 --resolution "r1" --command c \
  --output-file "$TMP/out.txt" --repo "$LAB" > /dev/null
python3 "$DOSSIE" learn "$D" --key k2 --resolution "r2" --command c \
  --output-file "$TMP/out.txt" --repo "$LAB" > /dev/null
printf 'saida3\n' > "$TMP/out3.txt"
python3 "$DOSSIE" learn "$D" --key k3 --resolution "r3" --command c \
  --output-file "$TMP/out3.txt" --repo "$LAB" > /dev/null
rm -f "$TMP/out3.txt"
OUT=$(python3 "$DOSSIE" prune "$D")
has "$OUT" '2 registros'
check $? "prune remove superseded + evidência ausente"
OUT=$(python3 "$DOSSIE" recall "$D" --key k2)
[ "$(printf '%s\n' "$OUT" | grep -c 'key=k2')" = 1 ]
check $? "após prune só a lição mais recente permanece"

# --- (3) reforço por confirmação independente -------------------------------
python3 "$DOSSIE" learn "$D" --key k4 --resolution "mesma resolucao" --command c \
  --output-file "$TMP/out.txt" --repo "$LAB" > /dev/null
python3 "$DOSSIE" learn "$D" --key k4 --resolution "mesma resolucao" --command c \
  --output-file "$TMP/out.txt" --repo "$LAB" > /dev/null
OUT=$(python3 "$DOSSIE" recall "$D" --key k4)
has "$OUT" 'confirmations=2'
check $? "mesma resolução confirmada 2× incrementa confirmations"

# --- (E) concorrência: appends paralelos sem perda nem corrupção --------------
OUT=$(python3 - "$DOSSIE" "$D" <<'PY'
import importlib.util, json, sys, threading
spec = importlib.util.spec_from_file_location("d", sys.argv[1])
d = importlib.util.module_from_spec(spec); spec.loader.exec_module(d)
before = len(d.read_entries(sys.argv[2]) or [])
def worker(n):
    for i in range(25):
        d.append(sys.argv[2], {"kind": "finding", "agent": f"w{n}", "summary": f"s{i}"})
ts = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
for t in ts: t.start()
for t in ts: t.join()
after = len(d.read_entries(sys.argv[2]) or [])
bad = 0
for line in open(sys.argv[2], encoding="utf-8"):
    if line.strip():
        try: json.loads(line)
        except ValueError: bad += 1
print("CONC-OK" if after - before == 200 and bad == 0 else f"CONC-FAIL delta={after - before} bad={bad}")
PY
)
has "$OUT" 'CONC-OK'
check $? "8 threads × 25 appends: sem perda nem corrupção (flock)"

# --- (6) linha corrompida isolada não derruba a memória ---------------------
printf 'linha-corrompida\n' >> "$D"
OUT=$(python3 "$DOSSIE" recall "$D" --key k1 --repo "$LAB")
has "$OUT" '^USABLE'
check $? "linha corrompida isolada é ignorada (recuperação)"

# --- (E) drift --dossie: decisão sem evidência ------------------------------
python3 "$DOSSIE" add "$D" --agent general --kind decision --summary "escolha X" > /dev/null
OUT=$(python3 "$LAB/tools/willtech-drift.py" "$LAB" --dossie "$D" || true)
has "$OUT" 'decisão sem evidência'
check $? "drift --dossie acusa decisão sem evidência"
printf 'decisao\n' > "$TMP/dec.txt"
python3 "$DOSSIE" add "$D" --agent general --kind decision --summary "escolha Y" \
  --path "$TMP/dec.txt" > /dev/null
OUT=$(python3 "$LAB/tools/willtech-drift.py" "$LAB" --dossie "$D" || true)
if has "$OUT" 'escolha Y'; then no "decisão com evidência não é acusada"; else ok "decisão com evidência não é acusada"; fi

# --- (D) comparação reproduzível com/sem otimizações ------------------------
python3 - "$TMP/base.jsonl" "$TMP/opt.jsonl" <<'PY'
import json, sys
def tr(path, tokens, fails):
    evs = [{"type": "system", "subtype": "init", "session_id": "t", "model": "m",
            "tools": ["Bash"], "permission_mode": "default"}]
    for i in range(fails):
        evs.append({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": f"u{i}", "name": "Bash",
             "input": {"command": "pytest -q"}}],
            "usage": {"input_tokens": tokens, "output_tokens": 10}}})
        evs.append({"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": f"u{i}", "is_error": True,
             "content": "Exit code 1"}]}})
    evs.append({"type": "result", "subtype": "success", "is_error": False,
                "num_turns": fails + 1, "duration_ms": 1000,
                "usage": {"input_tokens": tokens, "output_tokens": 10}})
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(json.dumps(e) for e in evs))
tr(sys.argv[1], 9000, 2)
tr(sys.argv[2], 4000, 0)
PY
OUT=$(python3 "$ROOT/tools/willtech-compare.py" "$TMP/base.jsonl" "$TMP/opt.jsonl")
has "$OUT" 'failure_loops' && has "$OUT" '\-5000'
check $? "compare reporta deltas reais de tokens e loops"
RC=0
python3 "$ROOT/tools/willtech-compare.py" "$TMP/nao-existe" "$TMP/opt.jsonl" > /dev/null 2>&1 || RC=$?
[ "$RC" = 2 ]; check $? "compare com transcript ausente: exit 2"

# --- (7) instalação idempotente, desativação e reversão ---------------------
LAB2=$TMP/repo2
mkdir -p "$LAB2/tools" "$LAB2/claude-code/bin" "$LAB2/.claude"
cp "$LAB/tools/"*.py "$LAB2/tools/"
cp "$LAB/claude-code/bin/willtech_trace.py" "$LAB2/claude-code/bin/"
git -C "$LAB2" init -q
git -C "$LAB2" -c user.email=lab@local -c user.name=lab commit -q --allow-empty -m init
printf '{"hooks":{"PreToolUse":[{"matcher":"Bash","hooks":[{"type":"command","command":"echo user-hook"}]}]}}' \
  > "$LAB2/.claude/settings.json"
sh "$ROOT/tools/willtech-install.sh" --repo "$LAB2" --yes > /dev/null
[ -f "$LAB2/.claude/settings.json" ] && [ -f "$LAB2/.codex/hooks.json" ] \
  && [ -f "$LAB2/.opencode/plugins/willtech/index.js" ] && [ -f "$LAB2/.willtech/enabled" ]
check $? "install cria hooks/plugin/marcador projeto-local"
N1=$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(sum("willtech-auto.py" in json.dumps(h) for g in d["hooks"].values() for x in g for h in x.get("hooks",[])))' "$LAB2/.claude/settings.json")
sh "$ROOT/tools/willtech-install.sh" --repo "$LAB2" --yes > /dev/null
N2=$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(sum("willtech-auto.py" in json.dumps(h) for g in d["hooks"].values() for x in g for h in x.get("hooks",[])))' "$LAB2/.claude/settings.json")
[ "$N1" = "$N2" ] && [ "$N1" = 6 ]
check $? "install 2× é idempotente (6 handlers, sem duplicar)"
grep -q 'echo user-hook' "$LAB2/.claude/settings.json"
check $? "hook pré-existente do usuário preservado"
sh "$ROOT/tools/willtech-install.sh" --repo "$LAB2" --disable > /dev/null
OUT=$(printf '%s' '{"hook_event_name":"UserPromptSubmit","session_id":"x","cwd":"'"$LAB2"'","prompt":"'"$LONG"'"}' | python3 "$LAB2/tools/willtech-auto.py" claude)
[ -z "$OUT" ]; check $? "--disable: núcleo vira no-op"
sh "$ROOT/tools/willtech-install.sh" --repo "$LAB2" --enable > /dev/null
OUT=$(printf '%s' '{"hook_event_name":"UserPromptSubmit","session_id":"x","cwd":"'"$LAB2"'","prompt":"'"$LONG"'"}' | python3 "$LAB2/tools/willtech-auto.py" claude)
[ -n "$OUT" ]; check $? "--enable: automação reativada"
sh "$ROOT/tools/willtech-install.sh" --repo "$LAB2" --uninstall --yes > /dev/null
if grep -q 'willtech-auto.py' "$LAB2/.claude/settings.json" 2>/dev/null; then
  no "uninstall restaura settings pré-instalação"
else
  ok "uninstall restaura settings pré-instalação"
fi
grep -q 'echo user-hook' "$LAB2/.claude/settings.json"
check $? "uninstall preserva o hook do usuário (backup restaurado)"
[ ! -f "$LAB2/.opencode/plugins/willtech/index.js" ] && [ ! -f "$LAB2/.willtech/enabled" ]
check $? "uninstall remove plugin e marcador"

# --- adaptador OpenCode V2 simulado em node (sem runtime real) --------------
# NODE_BIN opcional aponta para um binário node alternativo (ex.: Electron
# com ELECTRON_RUN_AS_NODE=1); sem node disponível, a simulação é SKIP.
NODE=${NODE_BIN:-node}
if command -v "$NODE" > /dev/null 2>&1; then
  cp "$ROOT/opencode/plugins/willtech/index.js" "$TMP/willtech-plugin.mjs"
  cat > "$TMP/sim.mjs" <<'JS'
import plugin from "./willtech-plugin.mjs";
import { spawnSync } from "node:child_process";
const dir = process.argv[2];
const hooks = {};
const ctx = {
  location: { directory: dir },
  tool: { hook: async (n, fn) => { hooks[n] = fn; } },
  session: { hook: async (n, fn) => { hooks["session." + n] = fn; } },
  event: { subscribe: () => ({ [Symbol.asyncIterator]() {
    return { next: async () => ({ done: true }) }; } }) },
};
const cleanup = await plugin.setup(ctx);
const core = (ev) => spawnSync("python3", [dir + "/tools/willtech-auto.py", "opencode"],
  { input: JSON.stringify(ev), encoding: "utf8" });
for (let i = 0; i < 2; i++) {
  core({ hook_event_name: "PostToolUseFailure", session_id: "nodesim", cwd: dir,
    tool_name: "Bash", tool_input: { command: "false" }, error: "Exit code 1" });
}
let blocked = false;
try {
  await hooks["execute.before"]({ tool: "bash", sessionID: "nodesim", input: { command: "false" } });
} catch (e) { blocked = /guard-a|bloquead|STOP/i.test(e.message); }
await hooks["session.prompt"]({ sessionID: "nodesim", prompt: { text: "x".repeat(250) } });
const sys = [];
await hooks["session.context"]({ system: sys });
const injected = sys.length === 1 && sys[0].text.includes("QUARENTENA");
const sys2 = [];
await hooks["session.context"]({ system: sys2 });
cleanup();
if (blocked && injected && sys2.length === 0) { console.log("SIM-OK"); process.exit(0); }
console.log("SIM-FAIL blocked=" + blocked + " injected=" + injected + " once=" + (sys2.length === 0));
process.exit(1);
JS
  OUT=$("$NODE" "$TMP/sim.mjs" "$LAB" 2>&1 || true)
  has "$OUT" 'SIM-OK'
  check $? "plugin V2 simulado: throw no loop + contexto injetado uma única vez"
else
  printf 'SKIP node ausente: simulação do plugin V2 não executada\n'
fi

# --- (5) desativação total no lab principal ---------------------------------
rm -f "$LAB/.willtech/enabled"
OUT=$(ev claude "$(J SessionStart s11 '')")
[ -z "$OUT" ]; check $? "sem marcador enabled: nenhuma automação executa"

printf '\n%s passed, %s failed\n' "$PASS" "$FAIL"
[ "$FAIL" = 0 ]

# WillTech-General / WILLTECH-BH © 2026 · autoria: github.com/hebwil