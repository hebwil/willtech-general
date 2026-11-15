#!/usr/bin/env bash
# WILLTECH — verificação do REGISTRO dos agentes no runtime (custo zero de token).
#
# Por que este script existe: contar arquivos `willtech-*.md` em ~/.claude/agents prova
# apenas que o arquivo foi copiado. Não prova que o runtime registrou o agente. O runtime
# registra um agente somente se o diretório de configuração que ele REALMENTE usa contém
# `agents/`. Quando CLAUDE_CONFIG_DIR aponta para outro lugar, ~/.claude/agents é ignorado
# e nenhum agente será registrado, embora todos os arquivos estejam no lugar certo.
#
# Método: `claude -p <prompt> --max-turns 0 --output-format stream-json` emite o evento
# `init`, que traz a lista `agents` realmente carregada. --max-turns 0 encerra antes de
# qualquer chamada ao modelo: output_tokens=0, total_cost_usd=0. É verificação, não teste.
#
# Uso:
#   ./willtech-verify-agents.sh            # verifica e imprime o relatório
#   ./willtech-verify-agents.sh --json     # só o JSON de resultado
#
# A lista dos 7 canônicos é fixa: eles são o contrato da estação. Não há --expect.
#
# Códigos de saída: 0 = todos registrados; 1 = faltando; 3 = não foi possível verificar.

set -Eeuo pipefail

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AS_JSON=0

while [ $# -gt 0 ]; do
  case "$1" in
    --json) AS_JSON=1; shift ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "argumento desconhecido: $1" >&2; exit 2 ;;
  esac
done

# Sem python3 não há como ler o stream-json. Isso é "não foi possível verificar"
# (código 3), nunca um falso "faltando" (1) — e nunca um traceback.
if ! command -v python3 >/dev/null 2>&1; then
  [ "$AS_JSON" -eq 1 ] && echo '{"status":"unverifiable","reason":"python3 ausente"}'
  [ "$AS_JSON" -eq 0 ] && echo "não foi possível verificar: python3 ausente"
  exit 3
fi

# `claude` raramente está no PATH de um duplo clique no macOS.
CLAUDE_OK=0
if [ -f "$SELF_DIR/_willtech_find_claude.sh" ]; then
  # shellcheck source=/dev/null
  source "$SELF_DIR/_willtech_find_claude.sh"
  willtech_use_claude && CLAUDE_OK=1
fi

if [ "$CLAUDE_OK" -ne 1 ]; then
  # Sem CLI não há evento init — mas o Claude DESKTOP não precisa de CLI para ler agentes:
  # ele lê ~/.claude/agents diretamente. Verificação estrutural é o máximo honesto aqui.
  # Ela prova os arquivos, o frontmatter e o diretório; NÃO prova o registro no runtime.
  if [ "$AS_JSON" -eq 1 ]; then
    python3 - "$HOME" <<'PY'
import json, os, re, sys
home = sys.argv[1]
base = os.path.join(home, ".claude", "agents")
expected = ["willtech-general","willtech-explorador","willtech-pesquisador","willtech-visual",
            "willtech-executor","willtech-testador","willtech-revisor"]
found, bad = {}, []
for root, _, files in os.walk(base):
    for f in files:
        if not f.endswith(".md"):
            continue
        p = os.path.join(root, f)
        try:
            txt = open(p, encoding="utf-8", errors="replace").read()
        except Exception:
            bad.append(f"{f}: ilegível"); continue
        m = re.search(r"^---\s*\n(.*?)\n---", txt, re.S)
        if not m:
            bad.append(f"{f}: sem frontmatter"); continue
        n = re.search(r"^name:\s*(\S+)", m.group(1), re.M)
        d = re.search(r"^description:\s*(\S.{15,})", m.group(1), re.M)
        if not n:
            bad.append(f"{f}: frontmatter sem name"); continue
        if not d:
            bad.append(f"{f}: description ausente/curta")
        found[n.group(1)] = os.path.relpath(p, base)
present = [n for n in expected if n in found]
missing = [n for n in expected if n not in found]
print(json.dumps({
    "status": "structural" if not missing and not bad else "missing",
    "score": f"{len(present)}/{len(expected)}",
    "mode": "estrutural (sem CLI)",
    "present": present, "missing": missing,
    "invalid": bad, "files": found,
    "proves": "arquivos presentes, frontmatter válido e diretório correto",
    "does_not_prove": "que o runtime carregou os agentes (exige o evento init)",
}, ensure_ascii=False))
PY
    exit $?
  fi

  echo "runtime claude não localizado nesta máquina."
  echo "Sem CLI não posso ler o evento init — mas o Claude Desktop lê ~/.claude/agents"
  echo "diretamente, sem precisar de CLI. Verificação estrutural dos arquivos:"
  echo
  python3 - "$HOME" <<'PY'
import os, re, sys
home = sys.argv[1]
base = os.path.join(home, ".claude", "agents")
expected = ["willtech-general","willtech-explorador","willtech-pesquisador","willtech-visual",
            "willtech-executor","willtech-testador","willtech-revisor"]
found, bad = {}, []
for root, _, files in os.walk(base):
    for f in files:
        if not f.endswith(".md"):
            continue
        p = os.path.join(root, f)
        try:
            txt = open(p, encoding="utf-8", errors="replace").read()
        except Exception:
            bad.append(f"{f}: ilegível"); continue
        m = re.search(r"^---\s*\n(.*?)\n---", txt, re.S)
        if not m:
            bad.append(f"{f}: sem frontmatter"); continue
        n = re.search(r"^name:\s*(\S+)", m.group(1), re.M)
        d = re.search(r"^description:\s*(\S.{15,})", m.group(1), re.M)
        if not n:
            bad.append(f"{f}: frontmatter sem name"); continue
        if not d:
            bad.append(f"{f}: description ausente/curta")
        found[n.group(1)] = os.path.relpath(p, base)
present = [n for n in expected if n in found]
missing = [n for n in expected if n not in found]
print(f"diretório: {base}")
print(f"arquivos  : {len(found)}/{len(expected)} canônicos com frontmatter válido")
for n in present:
    print(f"  ok  {n}  ({found[n]})")
for n in missing:
    print(f"  --  {n} (ausente)")
for b in bad:
    print(f"  !!  {b}")
print()
print("Isto prova: arquivos no lugar, frontmatter válido, estrutura de pastas correta.")
print("Isto NÃO prova: que o runtime carregou os agentes — isso exige o evento init,")
print("que por sua vez exige o CLI. Para provar de verdade, abra a aba Code e pergunte:")
print('  "quais subagentes você tem disponíveis?"')
sys.exit(0 if not missing and not bad else 1)
PY
  exit $?
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# 1) qual diretório de configuração o runtime usa de fato
#    Duas armadilhas reais, ambas já observadas:
#    - sem </dev/null o CLI injeta um aviso de stdin no stdout e corrompe o JSON;
#    - `auth status` sai com código 1 quando não há login, mesmo imprimindo JSON
#      válido — então o código de saída NÃO pode ser usado para descartar a saída.
CONFIG_DIR=""
claude auth status < /dev/null > "$WORK/auth.json" 2>/dev/null || true
[ -s "$WORK/auth.json" ] || : > "$WORK/auth.json"
CONFIG_DIR="$(python3 -c '
import json,sys
raw = open(sys.argv[1], encoding="utf-8", errors="replace").read()
i = raw.find("{")
if i < 0:
    print(""); raise SystemExit
try:
    d = json.loads(raw[i:])
except Exception:
    print(""); raise SystemExit
print(d.get("configDirectory") or "")
' "$WORK/auth.json" 2>/dev/null || true)"

# 2) evento init: a lista de agentes realmente carregada
#    roda em um diretório neutro para não confundir agentes de projeto com os do usuário
NEUTRAL="$WORK/neutral"; mkdir -p "$NEUTRAL"
INIT_OK=0
( cd "$NEUTRAL" && claude -p ok --max-turns 0 --output-format stream-json --verbose \
    < /dev/null > "$WORK/init.jsonl" 2> "$WORK/init.err" ) || true

python3 - "$WORK/init.jsonl" "$CONFIG_DIR" "$HOME" "$AS_JSON" <<'PY'
import json, os, sys

init_path, config_dir, home, as_json = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] == "1"

agents, found = [], False
tokens = None
with open(init_path, encoding="utf-8", errors="replace") as fh:
    for line in fh:
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("type") == "system" and d.get("subtype") == "init":
            agents = [a if isinstance(a, str) else (a or {}).get("name", "") for a in (d.get("agents") or [])]
            found = True
        if d.get("type") == "result":
            tokens = (d.get("usage") or {}).get("output_tokens")

willtech = sorted(a for a in agents if str(a).startswith("willtech-"))
expected_names = sorted([
    "willtech-general", "willtech-explorador", "willtech-pesquisador", "willtech-visual",
    "willtech-executor", "willtech-testador", "willtech-revisor",
])
# O placar conta CANÔNICOS, não "quantos willtech-* apareceram". Contar os vistos
# permite "7/7" com um canônico ausente, se um agente extra ocupar o lugar.
present = [n for n in expected_names if n in willtech]
missing = [n for n in expected_names if n not in willtech]
extras  = [a for a in willtech if a not in expected_names]
score   = f"{len(present)}/{len(expected_names)}"

# O diretório de config realmente usado difere do padrão? Então agentes em ~/.claude
# nunca serão vistos, mesmo estando no disco.
mismatch = bool(config_dir) and os.path.realpath(config_dir) != os.path.realpath(os.path.join(home, ".claude"))

if not found:
    status, reason = "unverifiable", "o runtime não emitiu o evento init (não foi possível ler a lista de agentes)"
elif missing:
    status = "missing"
    reason = f"{len(missing)} agente(s) canônico(s) não registrado(s): {', '.join(missing)}"
    if mismatch:
        reason += f"; o runtime usa configDirectory={config_dir}, não {home}/.claude — agentes ali são ignorados"
elif extras:
    status = "missing"
    reason = f"os {len(expected_names)} canônicos estão registrados, mas há extra(s): {', '.join(extras)}"
else:
    status, reason = "ok", f"{score} canônicos registrados"

if as_json:
    print(json.dumps({
        "status": status, "score": score, "registered": willtech,
        "present": present, "missing": missing, "extras": extras,
        "expected": len(expected_names),
        "configDirectory": config_dir or "(padrão)", "configMismatch": mismatch,
        "modelTokensUsed": tokens, "reason": reason,
    }, ensure_ascii=False))
else:
    print(f"configDirectory do runtime : {config_dir or '(padrão ~/.claude)'}")
    if mismatch:
        print("  ! ATENÇÃO: não é ~/.claude — agentes instalados em ~/.claude/agents são IGNORADOS")
    print(f"agentes willtech registrados: {score} (canônicos)")
    for n in present:
        print(f"  ok  {n}")
    for m in missing:
        print(f"  --  {m} (ausente)")
    for e in extras:
        print(f"  ??  {e} (registrado, mas fora dos 7 esperados)")
    if tokens is not None:
        print(f"tokens gastos na verificação: {tokens}")

sys.exit(0 if status == "ok" else (3 if status == "unverifiable" else 1))
PY

# WillTech / WILLTECH-BH © 2026 · autoria: github.com/hebwil
