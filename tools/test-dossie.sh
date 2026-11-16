#!/bin/sh
# Testes determinísticos do dossiê/cache/guardas (WillTech 2.0).
# Sem modelo, sem rede, sem credenciais reais: apenas arquivos descartáveis.
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
TOOL="$ROOT/willtech-dossie.py"

if ! command -v python3 >/dev/null 2>&1; then
  printf 'SKIP  python3 ausente\n'
  exit 0
fi

TMP=$(mktemp -d "${TMPDIR:-/tmp}/willtech-dossie-test.XXXXXX")
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
F=$TMP/codigo.py
printf 'print("conteudo-sensivel-do-arquivo")\n' > "$F"

expect "add finding com hash" 0 python3 "$TOOL" add "$D" --agent explorador --kind finding --summary "achado de teste" --path "$F" --line 1
expect "verify OK com arquivo intacto" 0 python3 "$TOOL" verify "$D"
printf 'print("mudado")\n' > "$F"
expect "verify detecta arquivo alterado" 1 python3 "$TOOL" verify "$D"

D2=$TMP/dossie2.jsonl
G=$TMP/sumiu.py
printf 'x = 1\n' > "$G"
python3 "$TOOL" add "$D2" --agent explorador --kind finding --summary "some" --path "$G" >/dev/null
rm "$G"
expect "verify detecta arquivo ausente" 1 python3 "$TOOL" verify "$D2"

before=$(wc -l < "$D")
mkdir -p "$TMP/.aws"
printf 'dummy\n' > "$TMP/.aws/credentials"
expect "add recusa caminho de credencial" 2 python3 "$TOOL" add "$D" --agent explorador --kind finding --summary "x" --path "$TMP/.aws/credentials"
after=$(wc -l < "$D")
if [ "$before" -eq "$after" ]; then ok "dossiê inalterado após recusa"; else bad "dossiê mudou após recusa"; fi
if grep -q 'conteudo-sensivel-do-arquivo' "$D"; then bad "dossiê vazou conteúdo de arquivo"; else ok "dossiê guarda hash, não conteúdo"; fi
expect "add recusa histórico de shell" 2 python3 "$TOOL" add "$D" --agent explorador --kind finding --summary "x" --path "$TMP/.zsh_history"
expect "add recusa kind inválido" 2 python3 "$TOOL" add "$D" --agent explorador --kind inventado --summary "x"

D3=$TMP/dossie3.jsonl
OUT=$TMP/saida.txt
printf '41 passed\n' > "$OUT"
expect "add test com hash de saída" 0 python3 "$TOOL" add "$D3" --agent testador --kind test --summary "suite" --command "sh suite.sh" --output-file "$OUT"
expect "verify OK com saída intacta" 0 python3 "$TOOL" verify "$D3"
printf '40 passed\n' > "$OUT"
expect "verify detecta saída de teste alterada" 1 python3 "$TOOL" verify "$D3"

R=$TMP/repo
C=$TMP/cache.json
MAP=$TMP/mapa.md
git init -q "$R"
git -C "$R" -c user.name=t -c user.email=t@t commit -q --allow-empty -m init
printf '# mapa de módulos\n' > "$MAP"
expect "cache-put em repo git" 0 python3 "$TOOL" cache-put "$R" "$C" --map-file "$MAP"
expect "cache-check HIT sem mudanças" 0 python3 "$TOOL" cache-check "$R" "$C"
printf 'dirty\n' > "$R/novo.txt"
expect "cache-check MISS com working tree sujo" 1 python3 "$TOOL" cache-check "$R" "$C"
git -C "$R" -c user.name=t -c user.email=t@t add -A
git -C "$R" -c user.name=t -c user.email=t@t commit -qm segundo
expect "cache-check MISS após novo commit" 1 python3 "$TOOL" cache-check "$R" "$C"
expect "cache-check erro fora de repo git" 2 python3 "$TOOL" cache-check "$TMP" "$C"

D4=$TMP/dossie4.jsonl
expect "guard-attempt 1a tentativa" 0 python3 "$TOOL" guard-attempt "$D4" --key "falha-x"
expect "guard-attempt 2a tentativa" 0 python3 "$TOOL" guard-attempt "$D4" --key "falha-x"
expect "guard-attempt 3a tentativa = STOP" 3 python3 "$TOOL" guard-attempt "$D4" --key "falha-x"
expect "guard-attempt chave distinta libera" 0 python3 "$TOOL" guard-attempt "$D4" --key "falha-y"

D5=$TMP/dossie5.jsonl
i=1
while [ "$i" -le 7 ]; do
  python3 "$TOOL" add "$D5" --agent general --kind delegation --summary "del $i" >/dev/null
  i=$((i + 1))
done
expect "guard-delegations abaixo do teto" 0 python3 "$TOOL" guard-delegations "$D5" --max 8
python3 "$TOOL" add "$D5" --agent general --kind delegation --summary "del 8" >/dev/null
expect "guard-delegations no teto = STOP" 3 python3 "$TOOL" guard-delegations "$D5" --max 8

expect "verify com dossiê ausente" 2 python3 "$TOOL" verify "$TMP/nao-existe.jsonl"

printf '\n%d PASS, %d FAIL\n' "$pass" "$fail"
[ "$fail" -eq 0 ] && printf 'Todos os testes do dossiê passaram.\n'
exit "$fail"

# WillTech-General / WILLTECH-BH © 2026 · autoria: github.com/hebwil