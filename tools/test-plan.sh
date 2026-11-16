#!/bin/sh
# Testes determinísticos Elephant/Goldfish (WillTech 2.3): plan, review-pack,
# resolve, catalyst. Sem modelo, sem rede: repositório git descartável.
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
TOOL="$ROOT/willtech-dossie.py"

if ! command -v python3 >/dev/null 2>&1; then
  printf 'SKIP  python3 ausente\n'
  exit 0
fi

TMP=$(mktemp -d "${TMPDIR:-/tmp}/willtech-plan-test.XXXXXX")
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

D=$TMP/dossie.jsonl

# 1. Tarefa simples não ativa etapas extras (sem entrada gravada).
out=$(python3 "$TOOL" plan "$D" --task "corrigir typo no README" --paths "README.md")
case "$out" in DIRECT*) ok "tarefa simples -> DIRECT" ;; *) bad "simples não retornou DIRECT: $out" ;; esac
if [ ! -f "$D" ]; then ok "simples não grava planejamento"; else bad "simples gravou entrada"; fi

# 2. Tarefa complexa produz planejamento compacto.
out=$(python3 "$TOOL" plan "$D" --task "refatorar o cache" --paths "tools/a.py,tools/b.py,tools/c.py")
case "$out" in
  *"PLAN complex"*REQUISITOS*CAUSA-RAIZ*DEPENDENCIAS*RISCOS*TESTES*) ok "complexa -> PLAN compacto completo" ;;
  *) bad "plan complexo incompleto: $out" ;;
esac
if [ "$(printf '%s' "$out" | wc -c)" -le 1200 ]; then ok "plan dentro do teto de 1200 chars"; else bad "plan excedeu teto"; fi
out=$(python3 "$TOOL" plan "$D" --task "$(printf 'x%.0s' $(seq 1 200))")
case "$out" in *"PLAN complex"*) ok "complexidade por tamanho (>=200 chars)" ;; *) bad "tamanho não classificou complexa" ;; esac

# Tarefa crítica (caminho de segurança) exige revisão.
out=$(python3 "$TOOL" plan "$D" --task "ajuste" --paths "opencode/bin/willtech-x")
case "$out" in *"PLAN critical"*REVIEW*) ok "crítica -> PLAN + REVIEW obrigatória" ;; *) bad "crítica sem REVIEW: $out" ;; esac

# 3. Revisão independente recebe contexto adequado, sem conclusões do executor.
R=$TMP/repo
mkdir -p "$R"
git -C "$R" init -q
git -C "$R" config user.email test@example.com
git -C "$R" config user.name test
printf 'a = 1\n' > "$R/mod.py"
git -C "$R" add mod.py
git -C "$R" commit -qm base
printf 'a = 2\n' > "$R/mod.py"
OUT=$TMP/saida.txt
printf '7 passed\n' > "$OUT"
python3 "$TOOL" add "$D" --agent testador --kind test --summary "suite ok" --command "sh suite.sh" --output-file "$OUT" >/dev/null
python3 "$TOOL" add "$D" --agent executor --kind decision --summary "CONCLUSAO-DO-EXECUTOR: tudo perfeito" --path "$R/mod.py" >/dev/null
pack=$(python3 "$TOOL" review-pack "$D" --repo "$R" --accept "a deve valer 2")
case "$pack" in
  *QUARENTENA*"ACEITE: a deve valer 2"*"EVIDENCE test"*"-a = 1"*"+a = 2"*) ok "pack tem aceite, evidência verificada e diff" ;;
  *) bad "pack incompleto: $pack" ;;
esac
case "$pack" in
  *CONCLUSAO-DO-EXECUTOR*) bad "pack vazou conclusão do executor" ;;
  *) ok "pack não entrega conclusão do executor como verdade" ;;
esac
expect "segunda rodada do mesmo diff bloqueada" 3 python3 "$TOOL" review-pack "$D" --repo "$R"
expect "segunda rodada com problema novo relevante permitida" 0 python3 "$TOOL" review-pack "$D" --repo "$R" --new-finding
printf 'a = 3\n' > "$R/mod.py"
expect "diff novo = nova rodada legítima" 0 python3 "$TOOL" review-pack "$D" --repo "$R"
expect "review-pack sem repositório git falha claro" 2 python3 "$TOOL" review-pack "$D" --repo "$TMP"

# 4. Críticas resolvidas sem ciclos infinitos.
expect "resolve fix sem evidência recusado" 2 python3 "$TOOL" resolve "$D" --id f1 --action fix --note "x"
expect "resolve fix com evidência" 0 python3 "$TOOL" resolve "$D" --id f1 --action fix --note "corrigido" --output-file "$OUT"
expect "resolve contest com evidência" 0 python3 "$TOOL" resolve "$D" --id f2 --action contest --note "procedente" --output-file "$OUT"
expect "resolve escalate sem evidência (decisão humana)" 0 python3 "$TOOL" resolve "$D" --id f3 --action escalate --note "fora do escopo"
expect "resolve discard registrado" 0 python3 "$TOOL" resolve "$D" --id f4 --action discard --note "irrelevante"
expect "resolve action inválida" 2 python3 "$TOOL" resolve "$D" --id f5 --action inventada

# 5. Catalyst: impasse demonstrado, uma alternativa, sem exploração indefinida.
expect "catalyst sem impasse recusado" 2 python3 "$TOOL" catalyst "$D" --key k1
python3 "$TOOL" guard-attempt "$D" --key k1 >/dev/null
python3 "$TOOL" guard-attempt "$D" --key k1 >/dev/null
expect "catalyst com impasse demonstrado" 0 python3 "$TOOL" catalyst "$D" --key k1
expect "segunda exploração da mesma chave bloqueada" 3 python3 "$TOOL" catalyst "$D" --key k1

printf '\n%d PASS, %d FAIL\n' "$pass" "$fail"
[ "$fail" -eq 0 ] || exit 1

# WillTech-General / WILLTECH-BH © 2026 · autoria: github.com/hebwil