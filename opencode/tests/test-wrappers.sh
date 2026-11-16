#!/bin/sh
# Regression tests for the WillTech OpenCode wrappers.
# No model/provider is called: this validates the sandbox, the credential
# denylist (trap files in a disposable fake HOME) and the exact permission
# contract of the seven agents, including a negative mutation test.
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TMP=$(mktemp -d "${TMPDIR:-/tmp}/willtech-wrap-test.XXXXXX")
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT INT TERM

export WILLTECH_LAB_ROOT="$TMP/lab"
mkdir -p "$WILLTECH_LAB_ROOT"

READ="$ROOT/bin/willtech-read-shell"
TEST="$ROOT/bin/willtech-test-shell"
fail=0

pass() { printf 'PASS  %s\n' "$1"; }
fail() { printf 'FAIL  %s\n' "$1"; fail=1; }

[ -x "$READ" ] && pass "read-shell executável" || fail "read-shell sem permissão de execução"
[ -x "$TEST" ] && pass "test-shell executável" || fail "test-shell sem permissão de execução"

sh -n "$READ" && pass "read-shell sintaxe" || fail "read-shell sintaxe"
sh -n "$TEST" && pass "test-shell sintaxe" || fail "test-shell sintaxe"

printf 'conteudo\n' > "$TMP/fonte.txt"
if "$READ" "cat '$TMP/fonte.txt'" >/dev/null 2>&1; then
  pass "read-shell lê arquivo comum"
else
  fail "read-shell não leu arquivo comum"
fi

if "$READ" "printf X > '$TMP/read-escrita.txt'" >/dev/null 2>&1; then
  fail "read-shell permitiu escrita"
else
  [ -e "$TMP/read-escrita.txt" ] && fail "read-shell criou arquivo" || pass "read-shell bloqueia escrita"
fi

if "$TEST" "printf OK > '$WILLTECH_LAB_ROOT/dentro.txt'" >/dev/null 2>&1; then
  [ -e "$WILLTECH_LAB_ROOT/dentro.txt" ] && pass "test-shell escreve no laboratório" \
    || fail "test-shell não criou arquivo no laboratório"
else
  fail "test-shell recusou escrita legítima no laboratório"
fi

if "$TEST" "printf X > '$TMP/fora.txt'" >/dev/null 2>&1; then
  fail "test-shell permitiu escrita fora do laboratório"
else
  [ -e "$TMP/fora.txt" ] && fail "test-shell criou arquivo fora do laboratório" \
    || pass "test-shell bloqueia escrita fora do laboratório"
fi

if "$TEST" "curl -sS --max-time 3 https://example.com" >/dev/null 2>&1; then
  fail "test-shell permitiu rede"
else
  pass "test-shell bloqueia rede"
fi

# Permission declarations consumed by the OpenCode runtime.
need() {
  label=$1
  pattern=$2
  shift 2
  for file in "$@"; do
    if grep -qF -- "$pattern" "$file"; then
      pass "$label ($(basename "$file"))"
    else
      fail "$label ($(basename "$file"))"
    fi
  done
}

READONLY="$ROOT/agent/willtech-explorador.md $ROOT/agent/willtech-pesquisador.md \
$ROOT/agent/willtech-visual.md $ROOT/agent/willtech-revisor.md"

need "edit deny" "action: edit" $READONLY
need "shell deny" "action: shell" $READONLY
need "subagent deny" "action: subagent" $READONLY
need "execute deny" "action: execute" $READONLY
need "worktree create deny" "action: opencode_worktree_create" $READONLY
need "read-shell entre aspas" 'willtech-read-shell "*"' $READONLY

if grep -q 'resource: "\*"' "$ROOT/agent/willtech-explorador.md" \
   && grep -q 'effect: deny' "$ROOT/agent/willtech-explorador.md"; then
  pass "explorador nega shell genérico"
else
  fail "explorador não nega shell genérico"
fi

if grep -q 'action: opencode_worktree_create' "$ROOT/agent/willtech-testador.md"; then
  pass "testador nega worktree"
else
  fail "testador não nega worktree"
fi

if grep -q 'willtech-test-shell "\*"' "$ROOT/agent/willtech-testador.md"; then
  pass "testador usa wrapper entre aspas"
else
  fail "testador não exige wrapper entre aspas"
fi

if grep -q 'action: edit' "$ROOT/agent/willtech-general.md" \
   && grep -q 'action: execute' "$ROOT/agent/willtech-general.md" \
   && ! grep -q 'action: subagent' "$ROOT/agent/willtech-general.md"; then
  pass "general mantém delegação e nega escrita/Code Mode"
else
  fail "general com permissões divergentes"
fi

# --- Credential denylist: trap files in a disposable fake HOME -------------
# HOME is canonicalized because sandbox subpath rules do not follow symlinks
# (/tmp -> /private/tmp). Trap content is dummy text, never real credentials.
FAKE=$(mktemp -d "${TMPDIR:-/tmp}/willtech-trap-home.XXXXXX")
FAKE=$(CDPATH= cd -- "$FAKE" && pwd -P)
mkdir -p "$FAKE/.config/gh" "$FAKE/.aws" "$FAKE/.docker" "$FAKE/.codex" \
  "$FAKE/.claude" "$FAKE/.kube" "$FAKE/.gnupg" "$FAKE/.config/gcloud" \
  "$FAKE/.azure" "$FAKE/Library/Keychains" \
  "$FAKE/Library/Application Support/Google/Chrome/Default" "$FAKE/projeto"

TRAP_PATHS='.config/gh/hosts.yml
.aws/credentials
.docker/config.json
.codex/auth.json
.claude/.credentials.json
.kube/config
.gnupg/secring.gpg
.config/gcloud/credentials.db
.azure/accessTokens.json
.netrc
.git-credentials
.npmrc
.pypirc
.zsh_history
.bash_history
.sh_history
.zhistory
.python_history
.node_repl_history
.mysql_history
.psql_history
Library/Keychains/login.keychain-db
Library/Application Support/Google/Chrome/Default/Cookies'

# IFS de nova-linha: caminhos com espaço ("Application Support") não quebram.
OLDIFS=$IFS
IFS='
'
for p in $TRAP_PATHS; do
  printf 'TRAP-DUMMY-NOT-A-SECRET\n' > "$FAKE/$p"
done
IFS=$OLDIFS
printf 'print("codigo legivel")\n' > "$FAKE/projeto/codigo.py"

trap_blocked=0
trap_leaked=0
for wrapper in "$READ" "$TEST"; do
  wname=$(basename "$wrapper")
  OLDIFS=$IFS
  IFS='
'
  for p in $TRAP_PATHS; do
    out=$(HOME="$FAKE" "$wrapper" "cat '$FAKE/$p'" 2>/dev/null) && rc=0 || rc=$?
    if [ "$rc" -ne 0 ] && ! printf '%s' "$out" | grep -q 'TRAP-DUMMY'; then
      trap_blocked=$((trap_blocked + 1))
    else
      trap_leaked=$((trap_leaked + 1))
      fail "$wname leu armadilha de credencial: $p"
    fi
  done
  IFS=$OLDIFS
done
if [ "$trap_leaked" -eq 0 ]; then
  pass "denylist de credenciais: $trap_blocked leituras bloqueadas (2 wrappers)"
fi

if HOME="$FAKE" "$READ" "cat '$FAKE/projeto/codigo.py'" >/dev/null 2>&1; then
  pass "read-shell preserva leitura legítima de código"
else
  fail "read-shell bloqueou leitura legítima de código"
fi
rm -rf "$FAKE"

# --- Structural permission contract + negative mutation test ---------------
CHECK="$ROOT/tests/check-permissions.py"
if command -v python3 >/dev/null 2>&1; then
  if python3 "$CHECK" "$ROOT/agent" >/dev/null 2>&1; then
    pass "contrato estrutural de permissões dos 7 agentes"
  else
    fail "contrato estrutural de permissões divergente"
    python3 "$CHECK" "$ROOT/agent" 2>&1 | sed 's/^/      /'
  fi

  MUT="$TMP/mutant-agent"
  mkdir -p "$MUT"
  cp "$ROOT/agent/"*.md "$MUT/"
  sed 's/effect: deny/effect: allow/' "$ROOT/agent/willtech-explorador.md" \
    > "$MUT/willtech-explorador.md"
  if python3 "$CHECK" "$MUT" >/dev/null 2>&1; then
    fail "teste de mutação: edit: allow no explorador NÃO foi detectado"
  else
    pass "teste de mutação: inversão de permissão detectada"
  fi
else
  printf 'SKIP  contrato estrutural e mutação (python3 ausente)\n'
fi

[ "$fail" -eq 0 ] && printf '\nTodos os testes de wrapper passaram.\n'
[ "$fail" -eq 0 ] || printf '\nFalhas detectadas.\n'
exit "$fail"

# WillTech-General / WILLTECH-BH © 2026 · autoria: github.com/hebwil
