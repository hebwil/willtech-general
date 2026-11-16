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

# --- 2.1: cache seletivo por escopo ---
R2=$TMP/repo2
C2=$TMP/cache2.json
git init -q "$R2"
mkdir -p "$R2/src" "$R2/docs"
git -C "$R2" -c user.name=t -c user.email=t@t commit -q --allow-empty -m init
expect "cache-put com escopo src" 0 python3 "$TOOL" cache-put "$R2" "$C2" --map-file "$MAP" --paths src
expect "cache seletivo HIT limpo" 0 python3 "$TOOL" cache-check "$R2" "$C2" --paths src
printf 'fora do escopo\n' > "$R2/docs/nota.md"
expect "cache seletivo HIT com sujeira fora do escopo" 0 python3 "$TOOL" cache-check "$R2" "$C2" --paths src
expect "cache seletivo HIT sem --paths (usa escopo do mapa)" 0 python3 "$TOOL" cache-check "$R2" "$C2"
printf 'dentro do escopo\n' > "$R2/src/mod.py"
expect "cache seletivo MISS com sujeira no escopo" 1 python3 "$TOOL" cache-check "$R2" "$C2" --paths src
expect "cache seletivo MISS escopo pedido fora do mapa" 1 python3 "$TOOL" cache-check "$R2" "$C2" --paths docs
git -C "$R2" -c user.name=t -c user.email=t@t add -A
git -C "$R2" -c user.name=t -c user.email=t@t commit -qm segundo
expect "cache seletivo MISS após novo commit" 1 python3 "$TOOL" cache-check "$R2" "$C2" --paths src

# --- 2.1: compatibilidade com cache formato 2.0 ---
R3=$TMP/repo3
C3=$TMP/cache3.json
git init -q "$R3"
git -C "$R3" -c user.name=t -c user.email=t@t commit -q --allow-empty -m init
python3 "$TOOL" cache-put "$R3" "$C3" --map-file "$MAP" >/dev/null
python3 - "$C3" <<'PY'
import json, sys
p = sys.argv[1]
d = json.load(open(p))
d.pop("dirty", None)
d.pop("paths", None)
json.dump(d, open(p, "w"))
PY
expect "cache formato 2.0 ainda HIT" 0 python3 "$TOOL" cache-check "$R3" "$C3"
printf 'sujo\n' > "$R3/x.txt"
expect "cache formato 2.0 MISS com sujeira" 1 python3 "$TOOL" cache-check "$R3" "$C3"
git -C "$R3" -c user.name=t -c user.email=t@t add -A
git -C "$R3" -c user.name=t -c user.email=t@t commit -qm limpa

# --- 2.1: lições verificadas (learn/recall) ---
D6=$TMP/dossie6.jsonl
OUT2=$TMP/evidencia.txt
printf 'evidencia-lesson-ok\n' > "$OUT2"
expect "learn recusa saída ausente" 2 python3 "$TOOL" learn "$D6" --key k1 --resolution "r" --command "c" --output-file "$TMP/nao-existe.txt" --repo "$R3"
expect "learn recusa caminho de credencial" 2 python3 "$TOOL" learn "$D6" --key k1 --resolution "r" --command "c" --output-file "$TMP/.aws/credentials" --repo "$R3"
expect "learn com evidência verificada" 0 python3 "$TOOL" learn "$D6" --key k1 --resolution "usar python -m pytest" --command "python -m pytest" --output-file "$OUT2" --repo "$R3"
if grep -q 'evidencia-lesson-ok' "$D6"; then bad "lição vazou conteúdo da saída"; else ok "lição guarda hash, não conteúdo"; fi
RC=$TMP/recall.txt
python3 "$TOOL" recall "$D6" --key k1 --repo "$R3" > "$RC"
if grep -q '^USABLE ' "$RC"; then ok "recall devolve lição USABLE"; else bad "recall não marcou USABLE"; fi
python3 "$TOOL" recall "$D6" --key desconhecida --repo "$R3" > "$RC"
if grep -q '^NO_LESSON ' "$RC"; then ok "recall sem lição = NO_LESSON"; else bad "recall sem lição não informou NO_LESSON"; fi
expect "learn mesma chave (supersede)" 0 python3 "$TOOL" learn "$D6" --key k1 --resolution "usar python -m pytest -q" --command "python -m pytest -q" --output-file "$OUT2" --repo "$R3"
python3 "$TOOL" recall "$D6" --key k1 --repo "$R3" > "$RC"
if grep -q 'superseded=yes' "$RC" && [ "$(grep -c '^USABLE ' "$RC" || true)" -eq 1 ]; then ok "recall supersede lição antiga"; else bad "recall não supersede lição antiga"; fi

# --- 2.2: brief contextual e escopo por projeto ---
BR=$TMP/brief.txt
expect "brief somente leitura" 0 python3 "$TOOL" brief "$D6" --repo "$R3" --cache "$C3"
python3 "$TOOL" brief "$D6" --repo "$R3" --cache "$C3" > "$BR"
if grep -q '^LESSON USABLE key=k1 ' "$BR"; then ok "brief traz lição USABLE"; else bad "brief sem lição USABLE"; fi
if grep -q '^CACHE ' "$BR" && grep -q '^GUARD attempts=' "$BR" && grep -q '^VERIFY OK ' "$BR"; then ok "brief compõe cache+guardas+verify"; else bad "brief incompleto"; fi
python3 "$TOOL" recall "$D6" --key k1 --repo "$R2" > "$RC"
if grep -q 'scope=yes' "$RC" && ! grep -q '^USABLE ' "$RC"; then ok "lição de outro projeto = REVERIFY"; else bad "escopo de projeto não protegido"; fi
python3 "$TOOL" brief "$D6" --repo "$R3" --max-chars 20 > "$BR"
if [ "$(wc -c < "$BR" | tr -d ' ')" -le 21 ]; then ok "brief respeita teto de caracteres"; else bad "brief estourou teto"; fi
python3 "$TOOL" brief "$TMP/nao-existe.jsonl" --repo "$R3" > "$BR"
if grep -q '^DOSSIE absent' "$BR"; then ok "brief sem dossiê informa ausência"; else bad "brief sem dossiê não informou"; fi
printf 'evidencia-alterada\n' > "$OUT2"
python3 "$TOOL" recall "$D6" --key k1 --repo "$R3" > "$RC"
if grep -q '^USABLE ' "$RC"; then bad "recall confiou em evidência alterada"; else ok "recall marca REVERIFY com evidência alterada"; fi
expect "verify cobre lição com saída alterada" 1 python3 "$TOOL" verify "$D6"
printf 'evidencia-lesson-ok\n' > "$OUT2"
git -C "$R3" -c user.name=t -c user.email=t@t commit -q --allow-empty -m terceiro
python3 "$TOOL" recall "$D6" --key k1 --repo "$R3" > "$RC"
if grep -q 'stale=yes' "$RC" && ! grep -q '^USABLE ' "$RC"; then ok "recall invalida lição após novo commit"; else bad "recall não invalidou lição stale"; fi
expect "recall com dossiê ausente" 2 python3 "$TOOL" recall "$TMP/nao-existe.jsonl" --key k1

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