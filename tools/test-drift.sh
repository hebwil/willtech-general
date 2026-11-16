#!/bin/sh
# Testes determinísticos do gate de drift (WillTech 2.2), com mutações.
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO=$(CDPATH= cd -- "$ROOT/.." && pwd)
DRIFT="$ROOT/willtech-drift.py"

if ! command -v python3 >/dev/null 2>&1; then
  printf 'SKIP  python3 ausente\n'
  exit 0
fi

TMP=$(mktemp -d "${TMPDIR:-/tmp}/willtech-drift-test.XXXXXX")
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

T=$TMP/arvore
mkdir -p "$T"
cp "$REPO/README.md" "$T/"
cp -R "$REPO/tools" "$REPO/opencode" "$REPO/codex" "$REPO/claude-code" "$T/"

expect "árvore coerente sem drift" 0 python3 "$DRIFT" "$T"

printf '\n`tools/nao-existe.py`\n' >> "$T/README.md"
expect "drift: README cita arquivo inexistente" 1 python3 "$DRIFT" "$T"
cp "$REPO/README.md" "$T/README.md"

printf '\nFerramenta: willtech-dossie.py inventado\n' >> "$T/opencode/AGENTS.md"
expect "drift: contrato cita subcomando inexistente" 1 python3 "$DRIFT" "$T"
cp "$REPO/opencode/AGENTS.md" "$T/opencode/AGENTS.md"

rm "$T/codex/agents/willtech-revisor.toml"
expect "drift: roster divergente entre plataformas" 1 python3 "$DRIFT" "$T"
cp "$REPO/codex/agents/willtech-revisor.toml" "$T/codex/agents/"

python3 - "$T/tools/willtech-dossie.py" <<'PY'
import sys
p = sys.argv[1]
lines = [l for l in open(p, encoding="utf-8") if 'sub.add_parser("verify")' not in l]
open(p, "w", encoding="utf-8").writelines(lines)
PY
expect "drift: subcomando citado sem implementação" 1 python3 "$DRIFT" "$T"
cp "$REPO/tools/willtech-dossie.py" "$T/tools/"

expect "raiz inexistente = erro de uso" 2 python3 "$DRIFT" "$TMP/nao-existe"
expect "repositório real sem drift" 0 python3 "$DRIFT" "$REPO"

printf '\n%d PASS, %d FAIL\n' "$pass" "$fail"
[ "$fail" -eq 0 ] && printf 'Todos os testes de drift passaram.\n'
exit "$fail"

# WillTech-General / WILLTECH-BH © 2026 · autoria: github.com/hebwil
