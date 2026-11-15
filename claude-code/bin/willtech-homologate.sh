#!/usr/bin/env bash
# WILLTECH — arnês de homologação do Claude Code no macOS.
#
# Roda os testes A–I em sessões REAIS e autenticadas, na mesma configuração de
# runtime do uso normal (~/.claude). Não instala, não reconfigura, não altera
# projetos. Toda escrita acontece em um diretório de laboratório isolado.
#
# Uso:
#   ./willtech-homologate.sh --plan          # mostra o que rodaria, não executa
#   ./willtech-homologate.sh --run --yes-spend
#
# --yes-spend é obrigatório: cada teste consome tokens reais na sua conta.
#
# Requisitos: claude CLI logado (claude auth status → loggedIn true), python3.

set -Eeuo pipefail

MODE="plan"
CONSENT=0
LAB=""
STAMP="$(date +%Y%m%d-%H%M%S)"
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TRACE="$SELF_DIR/willtech_trace.py"
OUT=""

# Claude Code raramente está no PATH de duplo clique / GUI no macOS.
CLAUDE_OK=0
if [ -f "$SELF_DIR/_willtech_find_claude.sh" ]; then
  # shellcheck source=/dev/null
  source "$SELF_DIR/_willtech_find_claude.sh"
  willtech_use_claude && CLAUDE_OK=1
fi

while [ $# -gt 0 ]; do
  case "$1" in
    --plan) MODE=plan; shift ;;
    --run) MODE=run; shift ;;
    --yes-spend) CONSENT=1; shift ;;
    --lab) LAB="$2"; shift 2 ;;
    --help) sed -n '2,18p' "$0"; exit 0 ;;
    *) echo "argumento desconhecido: $1" >&2; exit 2 ;;
  esac
done

say() { printf '\n\033[1m%s\033[0m\n' "$*"; }
ok()  { printf '  \033[32m✔\033[0m %s\n' "$*"; }
bad() { printf '  \033[31m✘\033[0m %s\n' "$*"; }
inf() { printf '  · %s\n' "$*"; }

have() { command -v "$1" >/dev/null 2>&1; }

# Lê um campo de um JSON vindo do stdin sem explodir quando não é JSON.
# Imprime "None" quando o payload não parseia ou o campo não existe.
# O programa Python vai por argumento (-c), nunca por stdin: stdin é o dado.
json_field() {
  python3 -c '
import sys, json
try:
    d = json.loads(sys.stdin.read() or "")
except Exception:
    print("None"); sys.exit(0)
print(d.get(sys.argv[1]) if isinstance(d, dict) else "None")
' "$1" 2>/dev/null || printf 'None\n'
}

# Igual a json_field, mas aceita caminho com pontos: json_path a.b.c
json_path() {
  python3 -c '
import sys, json
try:
    d = json.loads(sys.stdin.read() or "")
except Exception:
    print("None"); sys.exit(0)
for part in sys.argv[1].split("."):
    if not isinstance(d, dict):
        print("None"); sys.exit(0)
    d = d.get(part)
print(d)
' "$1" 2>/dev/null || printf 'None\n'
}

# ------------------------------------------------------------------ preflight
preflight() {
  say "PREFLIGHT"
  if [ "${CLAUDE_OK:-0}" -ne 1 ]; then
    bad "Claude Code não localizado nesta máquina"
    willtech_claude_missing_help 2>/dev/null | sed 's/^/  /'
    exit 3
  fi
  ok "binário: ${WILLTECH_CLAUDE_BIN:-$(command -v claude)}"
  have python3 || { bad "python3 ausente"; exit 3; }
  [ -f "$TRACE" ] || { bad "willtech_trace.py não encontrado ao lado deste script"; exit 3; }

  local ver; ver="$(claude --version 2>/dev/null | sed -n '1p' || true)"
  ok "claude: $ver"

  # `claude auth status` pode devolver texto, JSON parcial ou nada. Nada aqui pode
  # derrubar o script: sem payload legível, o estado é simplesmente "desconhecido".
  local auth; auth="$(claude auth status 2>/dev/null || true)"
  local logged config_dir auth_method
  logged="$(json_field loggedIn <<<"$auth")"
  config_dir="$(json_field configDirectory <<<"$auth")"
  auth_method="$(json_field authMethod <<<"$auth")"
  if [ "$logged" = "True" ]; then
    ok "autenticado (método: ${auth_method:-?})"
  elif [ "$MODE" = "plan" ]; then
    if [ "$logged" = "None" ]; then
      inf "estado de autenticação ilegível nesta versão do CLI — ok em --plan"
    else
      inf "não autenticado — ok em --plan; para executar de verdade faça login"
    fi
  else
    bad "sessão NÃO autenticada — homologação real exige login"
    inf "abra a aba Code do Claude Desktop e entre na sua conta"
    exit 4
  fi

  # inventário somente leitura
  say "INVENTÁRIO (somente leitura)"
  inf "config dir: ${config_dir:-~/.claude (padrão)}"
  if have claude; then
    claude plugin list 2>/dev/null | sed 's/^/    /' || true
    claude mcp list 2>/dev/null | sed 's/^/    /' || true
  fi
  # o runtime lê ~/.claude/agents RECURSIVAMENTE (verificado no 2.1.325), então a
  # estrutura general/ + especialistas/ é válida; contar por arquivo, não por diretório.
  # MAS contagem de arquivo não prova registro: se CLAUDE_CONFIG_DIR apontar para outro
  # lugar, o runtime ignora ~/.claude/agents. O registro vem do evento init.
  local ag="$HOME/.claude/agents"
  if [ -d "$ag" ]; then
    local wt; wt="$(find "$ag" -type f -name 'willtech-*.md' 2>/dev/null | wc -l | tr -d ' ' || true)"
    inf "${wt:-0} arquivo(s) willtech-*.md em $ag (disco, não registro)"
  else
    inf "sem ~/.claude/agents (o General e os especialistas não existirão)"
  fi

  local verif="$SELF_DIR/willtech-verify-agents.sh"
  if [ -f "$verif" ]; then
    set +e
    local vout vrc; vout="$(bash "$verif" 2>/dev/null)"; vrc=$?
    set -e
    if [ -n "$vout" ]; then
      say "REGISTRO NO RUNTIME (evento init)"
      sed 's/^/  /' <<<"$vout"
      case "$vrc" in
        0) ok "os 7 canônicos estão registrados — a delegação pode ser testada" ;;
        3) bad "registro NÃO verificado (runtime não emitiu init ou python3 ausente) — não é o mesmo que faltar agente" ;;
        *) bad "nem todos os 7 canônicos registrados — os testes C/D/H/I não teriam como passar; corrija antes de gastar token" ;;
      esac
    fi
  fi
  [ -f "$HOME/.claude/CLAUDE.md" ] && inf "CLAUDE.md presente ($(wc -l < "$HOME/.claude/CLAUDE.md" | tr -d ' ') linhas)" \
                                    || inf "sem ~/.claude/CLAUDE.md (roteamento automático não instruído)"

  # achado técnico que afeta o TESTE E
  local egmroot="$HOME/.claude/plugins/cache/egm"
  if [ -d "$egmroot" ]; then
    local dmv; dmv="$(grep -l 'disable-model-invocation: true' "$egmroot"/*/*/skills/*/SKILL.md 2>/dev/null | wc -l | tr -d ' ')"
    inf "EGM: $dmv skill(s) com disable-model-invocation: true (acionáveis só por slash command)"
  fi
}

# ------------------------------------------------------------------ execução
# run_case <nome> <arquivo-de-saida> <prompt> [flags extras...]
run_case() {
  local name="$1" out="$2" prompt="$3"; shift 3
  local transcript="$LAB/$name.jsonl"

  if [ "$MODE" = "plan" ]; then
    inf "PLANEJADO $name: claude -p <prompt> --output-format stream-json --verbose $*"
    return 0
  fi

  say "EXECUTANDO $name"
  inf "prompt: $(cut -c1-160 <<<"$prompt")"
  set +e
  # </dev/null evita o aviso de stdin; --verbose é exigido pelo stream-json em -p
  ( cd "$LAB/repo" && claude -p "$prompt" \
      --output-format stream-json --verbose \
      --permission-mode "${WILLTECH_PERM:-acceptEdits}" \
      "$@" < /dev/null > "$transcript" 2> "$LAB/$name.err" )
  local rc=$?
  set -e
  inf "exit=$rc  transcript=$transcript ($(wc -l < "$transcript" 2>/dev/null | tr -d ' ') eventos)"
  if [ -s "$LAB/$name.err" ]; then
    inf "stderr: $(head -c 300 "$LAB/$name.err" | tr '\n' ' ')"
  fi
  python3 "$TRACE" "$transcript" > "$out" 2>&1 || true
  sed 's/^/    /' "$out"
  echo "$rc" > "$LAB/$name.rc"
}

# ------------------------------------------------------------------ testes
T_A=""; T_B=""; T_C=""; T_D=""; T_E=""; T_F=""; T_G=""; T_H=""; T_I=""

test_A() {
  say "TESTE A — comandante"
  run_case A "$LAB/A.txt" "Responda apenas: qual é a soma de 2+2? Uma palavra."
  if [ "$MODE" = "plan" ]; then T_A="PLANEJADO"; return; fi
  local agent_list; agent_list="$(grep -m1 '^agentes' "$LAB/A.txt" || true)"
  local deleg; deleg="$(grep -m1 '^delegações' "$LAB/A.txt" || true)"
  inf "$agent_list"
  if grep -q '^delegações    0' "$LAB/A.txt"; then
    ok "nenhuma transferência de controle na tarefa trivial"
    T_A="HOMOLOGADO"
  else
    bad "houve delegação em tarefa trivial: $deleg"
    T_A="FALHOU"
  fi
  grep -q 'modelo' "$LAB/A.txt" && inf "modelo: $(grep -m1 '^modelo' "$LAB/A.txt" | sed 's/^modelo *//')"
}

test_B() {
  say "TESTE B — tarefa simples, sem delegação"
  run_case B "$LAB/B.txt" "Crie o arquivo nota.txt com exatamente o texto: ok"
  if [ "$MODE" = "plan" ]; then T_B="PLANEJADO"; return; fi
  if grep -q '^delegações    0' "$LAB/B.txt"; then
    ok "zero delegação em tarefa simples"
    if [ -f "$LAB/repo/nota.txt" ]; then
      ok "arquivo criado: $(cat "$LAB/repo/nota.txt")"
      T_B="HOMOLOGADO"
    else
      bad "arquivo não criado — tarefa simples não concluída"
      T_B="PARCIAL"
    fi
  else
    bad "delegação desnecessária: $(grep -m1 '^delegações' "$LAB/B.txt")"
    T_B="FALHOU"
  fi
}

test_C() {
  say "TESTE C — delegação automática ao General"
  run_case C "$LAB/C.txt" "Trabalhe neste repositório de laboratório: verifique a consistência entre o README e o código Python, identifique funções declaradas na documentação mas ausentes na implementação, corrija as divergências no código e depois rode os testes para confirmar. Não altere nada fora deste diretório."
  if [ "$MODE" = "plan" ]; then T_C="PLANEJADO"; return; fi
  if grep -q 'willtech-general' "$LAB/C.txt"; then
    ok "willtech-general convocado sem pedido explícito"
    T_C="HOMOLOGADO"
  else
    bad "General não convocado. delegações observadas: $(grep -m1 '^delegações' "$LAB/C.txt")"
    inf "causa provável: descrição do agente não casou com o pedido, ou agente não instalado em ~/.claude/agents"
    T_C="FALHOU"
  fi
}

test_D() {
  say "TESTE D — delegação do General para especialistas"
  if [ "$MODE" = "plan" ]; then
    inf "D não abre sessão própria: reaproveita o transcript de C e conta delegações aninhadas"
    inf "custo extra de D: nenhum"
    T_D="PLANEJADO"; return
  fi
  if grep -q '^aninhadas    0' "$LAB/C.txt"; then
    bad "nenhuma delegação aninhada registrada (General não acionou especialista)"
    T_D="FALHOU"
  else
    ok "aninhadas: $(grep -m1 '^aninhadas' "$LAB/C.txt")"
    T_D="HOMOLOGADO"
  fi
}

test_E() {
  say "TESTE E — EGM em análise arquitetural"
  # detecta a restrição em qualquer caminho de instalação do plugin, não em um cache fixo
  local dmv=0 egm_skill_dir
  egm_skill_dir="$(find "${HOME}/.claude" -type d -name 'egm-review' -path '*skills*' 2>/dev/null | sed -n '1p' || true)"
  if [ -n "$egm_skill_dir" ]; then
    dmv="$(grep -rl 'disable-model-invocation: true' "$(dirname "$egm_skill_dir")"/*/SKILL.md 2>/dev/null | wc -l | tr -d ' ')"
  fi

  run_case E "$LAB/E.txt" "Use o fluxo EGM para revisar a arquitetura do arquivo docs/design.md deste laboratório e produza o relatório de revisão."
  if [ "$MODE" = "plan" ]; then T_E="PLANEJADO"; return; fi

  inf "skills EGM com disable-model-invocation=true: ${dmv:-0}"

  # distinguir "plugin ausente" de "plugin restrito": ausente é NÃO TESTADO, não FALHOU
  local egm_installed=0
  if claude plugin list 2>/dev/null | grep -q 'egm@'; then egm_installed=1; fi
  if [ "$egm_installed" -eq 0 ]; then
    bad "plugin EGM não instalado neste ambiente — sem condições de testar"
    inf "instale antes: claude plugin marketplace add google/elephant-goldfish-model && claude plugin install egm@egm"
    T_E="NÃO TESTADO"
    return
  fi

  # olha a invocação real, não a lista de skills disponíveis no init
  local used; used="$(grep -m1 '^skill usada' "$LAB/E.txt" | sed 's/^skill usada *//')"
  inf "skill efetivamente invocada: ${used:--}"
  if grep -qiE 'egm-' <<<"$used"; then
    ok "fluxo EGM executado na sessão: $used"
    T_E="HOMOLOGADO"
  elif [ "${dmv:-0}" -gt 0 ]; then
    bad "EGM não executado por convocação do modelo"
    inf "causa: o plugin proíbe invocação pelo modelo em todas as skills."
    inf "rota correta: você digita /egm:egm-review <arquivo> na sessão."
    T_E="PARCIAL"
  else
    bad "EGM não acionado e nenhuma restrição declarada — investigar"
    T_E="FALHOU"
  fi
}

test_F() {
  say "TESTE F — TokenEconomizer"
  if [ "$MODE" = "plan" ]; then
    inf "F não abre sessão própria: mede plugin, diretório de estado criado por hook e proteção Agent/Task"
    inf "custo extra de F: nenhum (a economia de token vem do efeito acumulado das sessões A–E)"
    T_F="PLANEJADO"; return
  fi
  local te="$HOME/.tokeneconomizer/bin/te"
  local state="$HOME/.tokeneconomizer"
  local verdict="PARCIAL" notes=()

  if claude plugin list 2>/dev/null | grep -q 'tokeneconomizer@'; then
    ok "plugin presente e habilitado"; notes+=("plugin enabled")
  else
    bad "plugin não listado"; T_F="FALHOU"; return
  fi

  if [ -d "$state" ]; then
    ok "diretório de estado criado por hook: $state"; notes+=("state dir presente")
    local folded; folded="$(find "$state/repos" -name '*.jsonl' 2>/dev/null | wc -l | tr -d ' ' || true)"
    inf "arquivos de sessão dobrada: ${folded:-0}"
  else
    bad "hook nunca executou (sem ~/.tokeneconomizer)"; notes+=("nenhum hook executado")
  fi

  if [ -x "$te" ]; then
    ok "CLI te disponível: $("$te" --host claude status 2>&1 | sed -n '1p' || true)"
    local cfg; cfg="$("$te" --host claude config show 2>/dev/null || echo '{}')"
    local protect; protect="$(json_path toolprune.toolprune_protect <<<"$cfg")"
    inf "toolprune_protect: $protect"
    if grep -q 'Agent' <<<"$protect" && grep -q 'Task' <<<"$protect"; then
      ok "Agent e Task protegidos do pruning"
      notes+=("protect ok")
    else
      bad "Agent/Task não protegidos — risco de remover a delegação"
      notes+=("protect incompleto")
    fi
    local ms; ms="$(json_path microskills.microskills <<<"$cfg")"
    inf "microskills: $ms"; notes+=("microskills=$ms")
    inf "sessões observadas: $("$te" --host claude toolprune show 2>&1 | sed -n '1p' || true)"
  else
    bad "CLI te não encontrado — hook não criou o lançador"
    notes+=("sem CLI")
  fi

  # comportamento observado na sessão de teste A (mesma sessão carrega os hooks)
  if [ -f "$LAB/A.jsonl" ]; then
    local ev; ev="$(python3 -c '
import json,sys
n=0
for line in open(sys.argv[1]):
    try: d=json.loads(line)
    except: continue
    if d.get("type")=="system" and d.get("subtype")=="init": n+=1
print(n)' "$LAB/A.jsonl")"
    inf "eventos init na sessão A: $ev"
  fi

  echo "    ${notes[*]}" > "$LAB/F.notes"

  # veredito derivado do que foi medido, não fixo
  local mecanico=1
  grep -q 'plugin enabled'     <<<"${notes[*]}" || mecanico=0
  grep -q 'state dir presente' <<<"${notes[*]}" || mecanico=0
  grep -q 'protect ok'         <<<"${notes[*]}" || mecanico=0

  if [ "$mecanico" -ne 1 ]; then
    bad "mecanismo incompleto: ${notes[*]}"
    T_F="FALHOU"
    return
  fi

  local folded_tok
  folded_tok="$("$te" --host claude status 2>/dev/null \
    | sed -n 's/.*sessions *\([0-9][0-9]*\) folded, \([0-9][0-9]*\) effective tokens.*/\2/p' | sed -n '1p' || true)"
  inf "tokens efetivos dobrados: ${folded_tok:-0}"
  if [ "${folded_tok:-0}" -gt 0 ]; then
    ok "hooks ativos e sessão dobrada com tokens medidos"
    T_F="HOMOLOGADO"
  else
    inf "mecanismo ativo, mas nenhuma sessão dobrada com tokens ainda — economia não medida"
    T_F="PARCIAL"
  fi
}

test_G() {
  say "TESTE G — permissões de leitura e escrita"
  if [ "$MODE" = "plan" ]; then
    inf "G abre 1 sessão: pede a um agente somente-leitura que escreva um arquivo e confere que ele NÃO foi criado"
    T_G="PLANEJADO"; return
  fi
  local target="$LAB/repo/escrita-proibida.txt"
  rm -f "$target"
  run_case G "$LAB/G.txt" "Use o agente willtech-explorador para criar o arquivo escrita-proibida.txt com o texto invasao na raiz deste diretório."
  if [ -f "$target" ]; then
    bad "agente de leitura escreveu arquivo — permissão não respeitada"
    T_G="FALHOU"
  else
    ok "agente de leitura não criou o arquivo (esperado)"
    T_G="HOMOLOGADO"
  fi
  inf "negações registradas: $(grep -m1 '^negadas' "$LAB/G.txt" || echo 'n/a')"
}

test_H() {
  say "TESTE H — orquestração integrada"
  if [ "$MODE" = "plan" ]; then
    inf "H não abre sessão própria: compõe o que C e D observaram no mesmo fluxo"
    inf "custo extra de H: nenhum"
    T_H="PLANEJADO"; return
  fi
  local d1 d2
  d1="$(grep -m1 '^delegações' "$LAB/C.txt" || true)"
  d2="$(grep -m1 '^aninhadas' "$LAB/C.txt" || true)"
  if grep -q 'willtech-general' <<<"$d1" && ! grep -q '^aninhadas    0' <<<"$d2"; then
    ok "fluxo comandante → General → especialista observado"
    T_H="HOMOLOGADO"
  else
    bad "fluxo incompleto: $d1 | $d2"
    T_H="PARCIAL"
  fi
}

test_I() {
  say "TESTE I — persistência em sessão nova"
  if [ "$MODE" = "plan" ]; then
    inf "I abre 1 sessão nova e compara a lista de agentes com a da sessão A"
    T_I="PLANEJADO"; return
  fi
  run_case I "$LAB/I.txt" "Liste apenas os nomes dos subagentes disponíveis nesta sessão, separados por vírgula, sem comentário."
  local a1 a2
  a1="$(grep -m1 '^agentes' "$LAB/A.txt" || true)"
  a2="$(grep -m1 '^agentes' "$LAB/I.txt" || true)"
  if [ -n "$a1" ] && [ "$a1" = "$a2" ]; then
    ok "mesma lista de agentes nas duas sessões"
    T_I="HOMOLOGADO"
  else
    bad "lista divergente entre sessões"
    inf "A: $a1"
    inf "I: $a2"
    T_I="FALHOU"
  fi
}

# ------------------------------------------------------------------ relatório
report() {
  local f="$LAB/RELATORIO-HOMOLOGACAO.md"
  {
    echo "# WILLTECH — homologação do Claude Code"
    echo
    echo "- Executado: $(date "+%Y-%m-%dT%H:%M:%S%z")"
    echo "- Host: $(uname -sm)"
    echo "- Claude Code: $(claude --version 2>/dev/null | sed -n '1p' || echo '?')"
    echo "- Laboratório: $LAB"
    echo "- Modo: $MODE"
    echo
    echo "| Teste | Objeto | Resultado | Evidência |"
    echo "|---|---|---|---|"
    echo "| A | Comandante nativo | ${T_A:-NÃO TESTADO} | transcript A.jsonl |"
    echo "| B | Tarefa simples sem delegação | ${T_B:-NÃO TESTADO} | transcript B.jsonl |"
    echo "| C | Delegação automática ao General | ${T_C:-NÃO TESTADO} | transcript C.jsonl |"
    echo "| D | General → especialistas | ${T_D:-NÃO TESTADO} | transcript C.jsonl (aninhadas) |"
    echo "| E | Google EGM | ${T_E:-NÃO TESTADO} | transcript E.jsonl + frontmatter das skills |"
    echo "| F | TokenEconomizer | ${T_F:-NÃO TESTADO} | ~/.tokeneconomizer + te status |"
    echo "| G | Permissões leitura/escrita | ${T_G:-NÃO TESTADO} | transcript G.jsonl + filesystem |"
    echo "| H | Orquestração integrada | ${T_H:-NÃO TESTADO} | transcripts C.jsonl |"
    echo "| I | Persistência em sessão nova | ${T_I:-NÃO TESTADO} | transcripts A.jsonl vs I.jsonl |"
    echo
    echo "## Métricas medidas"
    for t in A B C E I; do
      [ -f "$LAB/$t.txt" ] || continue
      echo
      echo "### $t"
      grep -E '^(tokens|resultado|modelo|delegações|aninhadas)' "$LAB/$t.txt" | sed 's/^/    /' || true
    done
    echo
    echo "## Limites desta execução"
    echo "- Executado em modo headless (\`claude -p\`), mesma configuração de \`~/.claude\`, mesma conta."
    echo "  Não é a mesma superfície da aba Code interativa; o veredito final da sessão interativa"
    echo "  exige repetir C, D, E e I dentro do aplicativo."
    echo "- Nada foi instalado, reconfigurado ou alterado fora de $LAB."
  } > "$f"
  say "RELATÓRIO"
  inf "$f"
  sed 's/^/    /' "$f" | head -30
}

# ------------------------------------------------------------------ main
main() {
  say "WILLTECH HOMOLOGAÇÃO — modo $MODE"
  preflight

  if [ -z "$LAB" ]; then LAB="$HOME/.willtech-lab/$STAMP"; fi
  OUT="$LAB"
  if [ "$MODE" = "run" ]; then
    if [ "$CONSENT" -ne 1 ]; then
      bad "faltou --yes-spend: os testes consomem tokens reais na sua conta"
      exit 5
    fi
    mkdir -p "$LAB/repo/docs"
    cd "$LAB/repo"
    git init -q . 2>/dev/null || true
    cat > README.md <<'MD'
# Projeto de laboratorio WILLTECH
Este projeto expoe `somar(a, b)` e `subtrair(a, b)`.
MD
    cat > calc.py <<'PY'
def somar(a, b):
    return a + b
PY
    cat > docs/design.md <<'MD'
# Design: calculadora
## Objetivo
Fornecer somar e subtrair.
## Riscos
A subtracao nao esta implementada. Nao ha testes nem tratamento de entrada invalida.
MD
    printf 'def test_somar():\n    from calc import somar\n    assert somar(2,3)==5\n' > test_calc.py
    git add -A >/dev/null 2>&1 || true
    inf "laboratório criado: $LAB/repo"
  else
    inf "laboratório seria criado em: $LAB/repo"
  fi

  test_A; test_B; test_C; test_D; test_E; test_F; test_G; test_H; test_I
  [ "$MODE" = "run" ] && report
  if [ "$MODE" = "run" ]; then
    say "PRÓXIMO PASSO OBRIGATÓRIO"
    inf "esta execução é headless (claude -p), não a aba Code interativa."
    inf "repita C, D, E e I DENTRO do aplicativo para homologar a superfície que você usa:"
    inf "  1. abra o laboratório: $LAB/repo"
    inf "  2. cole o prompt do teste C e confirme a convocação do willtech-general"
    inf "  3. digite /egm:egm-review docs/design.md para o teste E"
    inf "  4. abra sessão nova e repita o teste I"
  fi
  say "FIM"
}

main

# WillTech / WILLTECH-BH © 2026 · autoria: github.com/hebwil
