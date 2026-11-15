#!/usr/bin/env bash
# WILLTECH ULTRA PRO — bootstrap idempotente da estação (Claude Desktop / Claude Code)
#
# Princípio: verificar antes de instalar. Componente já instalado, válido e compatível
# recebe apenas teste rápido e é registrado como VALIDADO — PULAR.
#
# Uso:
#   ./willtech-bootstrap.sh --check            # só inventário, não altera nada
#   ./willtech-bootstrap.sh --apply            # instala o que falta, faz backup antes
#   ./willtech-bootstrap.sh --apply --home /tmp/fh   # ensaio em HOME isolado
#
# Nunca usa sudo. Nunca toca OpenCode, VPS, gateways, credenciais ou produção.

set -Eeuo pipefail

APPLY=0
TARGET_HOME="${HOME}"
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# aceita layout pacote/{bin/agents} ou script solto ao lado de agents/
if [ -d "$SELF_DIR/agents" ]; then ROOT="$SELF_DIR"; else ROOT="$(cd "$SELF_DIR/.." && pwd)"; fi
STAMP="$(date +%Y%m%d-%H%M%S)"
LOG_DIR=""
declare -a REPORT=()

usage() { sed -n '2,14p' "$0"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --apply) APPLY=1; shift ;;
    --check) APPLY=0; shift ;;
    --home) TARGET_HOME="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "argumento desconhecido: $1" >&2; exit 2 ;;
  esac
done

CLAUDE_DIR="$TARGET_HOME/.claude"
BACKUP_DIR="$TARGET_HOME/.willtech-backups/$STAMP"
mkdir -p "$TARGET_HOME/.willtech-logs"
LOG_DIR="$TARGET_HOME/.willtech-logs"

say()  { printf '%s\n' "$*"; }
ok()   { printf '  \033[32m✔\033[0m %s\n' "$*"; }
skip() { printf '  \033[36m↷\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*"; }
bad()  { printf '  \033[31m✘\033[0m %s\n' "$*"; }
inf()  { printf '  · %s\n' "$*"; }

record() { REPORT+=("$1|$2|$3|$4"); }

have() { command -v "$1" >/dev/null 2>&1; }

# `claude plugin list` custa ~0,4s e é consultado em várias fases. Guarda o resultado
# uma vez por execução — evita repetir a saída crua na tela e acelera o duplo clique.
_PLUGIN_LIST=""
plugin_list() {
  if [ -z "$_PLUGIN_LIST" ]; then
    [ "${CLAUDE_OK:-0}" -eq 1 ] && _PLUGIN_LIST="$(claude plugin list 2>/dev/null || true)"
  fi
  printf '%s\n' "$_PLUGIN_LIST"
}

_MCP_LIST=""
mcp_list() {
  if [ -z "$_MCP_LIST" ]; then
    [ "${CLAUDE_OK:-0}" -eq 1 ] && _MCP_LIST="$(claude mcp list 2>/dev/null || true)"
  fi
  printf '%s\n' "$_MCP_LIST"
}

# Claude Code raramente está no PATH de um shell não-interativo no macOS.
# Localiza antes de qualquer uso e cria um shim para as chamadas `claude` funcionarem.
CLAUDE_OK=0
if [ -f "$SELF_DIR/_willtech_find_claude.sh" ]; then
  # shellcheck source=/dev/null
  source "$SELF_DIR/_willtech_find_claude.sh"
  willtech_use_claude && CLAUDE_OK=1
fi

# O lançador ~/.tokeneconomizer/bin/te só é criado pelo primeiro hook executado na sessão.
# Até lá, o mesmo CLI vive no cache do plugin. Esta função acha o que existir.
te_cmd() {
  if [ -x "$TARGET_HOME/.tokeneconomizer/bin/te" ]; then
    printf '%s' "$TARGET_HOME/.tokeneconomizer/bin/te"
    return 0
  fi
  local p
  # `sort -V` é GNU; o macOS traz BSD sort, que rejeita -V. Aqui não se ordena versão:
  # qualquer `te` do cache serve, então basta pegar o primeiro. Evitar -V evita que o
  # macOS conclua "CLI ausente" e reinstale o plugin desnecessariamente.
  p="$(ls -d "$CLAUDE_DIR"/plugins/cache/tokeneconomizer/*/*/scripts/te 2>/dev/null | sed -n '1p' || true)"
  if [ -n "$p" ] && [ -f "$p" ]; then
    printf 'sh %s' "$p"
    return 0
  fi
  p="$(ls -d "$TARGET_HOME"/.willtech-vendor/TokenEconomizer/plugin/scripts/te 2>/dev/null | tail -1)"
  [ -n "$p" ] && { printf 'sh %s' "$p"; return 0; }
  return 1
}

# ---------------------------------------------------------------- backup
backup_path() {
  local p="$1"
  [ -e "$p" ] || return 0
  local rel="${p#"$TARGET_HOME"/}"
  mkdir -p "$BACKUP_DIR/$(dirname "$rel")"
  cp -a "$p" "$BACKUP_DIR/$rel"
  say "    backup: $rel"
}

# ---------------------------------------------------------------- FASE 1: inventário
phase_inventory() {
  say ""
  say "FASE 1 — INVENTÁRIO"
  say "  alvo: $TARGET_HOME"
  if [ -d "$CLAUDE_DIR" ]; then ok "config do Claude encontrada: $CLAUDE_DIR"
  else warn "sem $CLAUDE_DIR (será criado)"; fi

  if [ "${CLAUDE_OK:-0}" -eq 1 ]; then
    ok "claude: $(claude --version 2>/dev/null | head -1)"
    inf "  binário: ${WILLTECH_CLAUDE_BIN:-$(command -v claude)}"
  else
    bad "Claude Code não localizado nesta máquina"
    willtech_claude_missing_help 2>/dev/null | sed 's/^/    /'
    record "Claude Code" "-" "BLOQUEADO" "binário não localizado; plugins e agentes ficam pendentes"
  fi

  if have node; then ok "node: $(node --version)"; else warn "node ausente"; fi
  if have git;  then ok "git:  $(git --version | awk '{print $3}')"; fi
  if have python3; then ok "python3: $(python3 -V 2>&1 | awk '{print $2}')"; fi
  have uv && ok "uv presente (pré-requisito da Serena)" || warn "uv ausente (pré-requisito da Serena)"

  if [ "${CLAUDE_OK:-0}" -eq 1 ]; then
    say ""
    say "  plugins carregados:"
    plugin_list | sed 's/^/    /'
    say "  MCPs conectados:"
    mcp_list | sed 's/^/    /'
  fi

  if [ -d "$CLAUDE_DIR/agents" ]; then
    say "  agentes no diretório do usuário:"
    ls "$CLAUDE_DIR/agents" 2>/dev/null | sed 's/^/    /' || true
  fi
}

# ---------------------------------------------------------------- EGM
phase_egm() {
  say ""
  say "FASE 5 — EGM (google/elephant-goldfish-model)"
  local installed=0
  if [ "${CLAUDE_OK:-0}" -eq 1 ]; then
    installed="$(plugin_list | grep -c 'egm@egm' || true)"
  fi
  if [ "${installed:-0}" -ge 1 ]; then
    ok "VALIDADO — PULAR: egm@egm já instalado"
    plugin_list | grep -A3 'egm@egm' | sed 's/^/    /'
    record "EGM" "$(plugin_list | grep -A3 'egm@egm' | grep -m1 Version | awk '{print $2}')" "VALIDADO — PULAR" "plugin ativo; skills e agentes aguardam nova sessão"
    return 0
  fi
  if [ "${CLAUDE_OK:-0}" -ne 1 ]; then
    bad "Claude Code não localizado — EGM não pode ser instalado agora"
    record "EGM" "-" "BLOQUEADO" "depende do binário do Claude Code"
    return 0
  fi
  if [ "$APPLY" -eq 0 ]; then
    warn "AUSENTE: rodar com --apply instala via marketplace oficial"
    record "EGM" "-" "AUSENTE" "comando oficial: claude plugin marketplace add google/elephant-goldfish-model"
    return 0
  fi
  claude plugin marketplace add google/elephant-goldfish-model
  claude plugin install egm@egm
  _PLUGIN_LIST=""   # o cache acima ficou velho depois da instalação
  ok "instalado egm@egm"
  record "EGM" "0.1.1" "INSTALADO MAS NÃO HOMOLOGADO" "requer sessão nova para carga de skills"
}

# ---------------------------------------------------------------- TokenEconomizer
phase_te() {
  say ""
  say "FASE 6 — TokenEconomizer (microsoft/TokenEconomizer)"
  local plugin_on=0
  [ "${CLAUDE_OK:-0}" -eq 1 ] && plugin_on="$(plugin_list | grep -c 'tokeneconomizer@' || true)"

  if [ "$plugin_on" -ge 1 ] && te_cmd >/dev/null; then
    ok "VALIDADO — PULAR: plugin e CLI presentes"
    # shellcheck disable=SC2046
    ( cd "$TARGET_HOME" && $(te_cmd) --host claude status 2>&1 | sed 's/^/    /' ) || warn "status falhou"
    record "TokenEconomizer" "0.1.0" "VALIDADO — PULAR" "plugin habilitado + te status executado"
    return 0
  fi

  if [ "${CLAUDE_OK:-0}" -ne 1 ]; then
    bad "Claude Code não localizado — TokenEconomizer não pode ser instalado agora"
    record "TokenEconomizer" "-" "BLOQUEADO" "depende do binário do Claude Code"
    return 0
  fi

  if [ "$APPLY" -eq 0 ]; then
    warn "AUSENTE: rodar com --apply clona e instala o plugin oficial"
    record "TokenEconomizer" "-" "AUSENTE" "clone oficial + marketplace local"
    return 0
  fi

  local clone="$TARGET_HOME/.willtech-vendor/TokenEconomizer"
  mkdir -p "$(dirname "$clone")"
  if [ -d "$clone/.git" ]; then
    skip "clone já existe, reaproveitando: $clone"
  else
    git clone --depth 1 https://github.com/microsoft/TokenEconomizer.git "$clone"
  fi
  claude plugin marketplace add "$clone"
  claude plugin install tokeneconomizer@tokeneconomizer
  _PLUGIN_LIST=""

  # configuração conservadora: envfacts, toolprune em propose, delegação protegida.
  # `set` é escopo de repositório: aplica no clone para valer como padrão da instalação.
  if te_cmd >/dev/null; then
    local te; te="$(te_cmd)"
    ( cd "$clone" && $te --host claude config set microskills=envfacts ) || true
    ( cd "$clone" && $te --host claude config set toolprune=propose )     || true
    ( cd "$clone" && $te --host claude config set toolprune_protect=Agent,Task ) || true
    ok "config conservadora aplicada em $clone (envfacts, toolprune=propose, Agent/Task protegidos)"
    warn "histórico importado: desligado por padrão; loop guard: padrão 'nudge' preservado"
    record "TokenEconomizer" "0.1.0" "INSTALADO MAS NÃO HOMOLOGADO" "config conservadora aplicada; hooks exigem sessão nova"
  else
    warn "CLI te não localizado após instalação"
    record "TokenEconomizer" "0.1.0" "INCOMPATÍVEL" "plugin instalado, CLI te ausente"
  fi
}

# ---------------------------------------------------------------- agentes WILLTECH
# A estrutura de pastas do pacote é preservada: agents/general/ e agents/especialistas/.
# Verificado no runtime 2.1.325 que ~/.claude/agents é lido recursivamente e que o nome
# do agente vem do campo `name` do frontmatter, não do nome do arquivo.
phase_agents() {
  say ""
  say "FASE 4 — hierarquia WILLTECH"
  local src="$ROOT/agents"
  if [ ! -d "$src" ]; then
    bad "pasta agents/ não encontrada em $ROOT"
    record "Agentes WILLTECH" "-" "AUSENTE" "pacote sem agents/ — nada a instalar"
    return 0
  fi
  # Distinguir "pacote vazio" de "find indisponível" — senão um PATH incomum faz o
  # instalador acusar pacote truncado e pular a cópia inteira.
  local amostra=""
  if have find; then
    amostra="$(find "$src" -type f -name '*.md' 2>/dev/null | sed -n '1p' || true)"
  else
    amostra="$(ls "$src"/*/*.md 2>/dev/null | sed -n '1p' || true)"
  fi
  if [ -z "$amostra" ]; then
    bad "pasta agents/ existe mas não contém nenhum .md — pacote incompleto"
    record "Agentes WILLTECH" "-" "AUSENTE" "agents/ sem arquivos .md; pacote truncado"
    return 0
  fi
  local dest="$CLAUDE_DIR/agents"
  local novos=0 iguais=0 migrados=0
  local lista=()

  # varredura recursiva: cada .md é copiado para o mesmo caminho relativo no destino
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    local rel="${f#"$src"/}"
    local b; b="$(basename "$f")"
    lista+=("$rel")

    # instalação anterior (achatada) deixaria o MESMO agente duas vezes e o
    # runtime resolveria por nome — duplicata silenciosa. Detecta e resolve.
    if [ "$rel" != "$b" ] && [ -f "$dest/$b" ]; then
      migrados=$((migrados+1))
      if [ "$APPLY" -eq 1 ]; then
        backup_path "$dest/$b"
        rm -f "$dest/$b"
        inf "cópia antiga achatada removida (backup acima): $b"
      fi
    fi

    if [ -f "$dest/$rel" ] && cmp -s "$f" "$dest/$rel"; then
      iguais=$((iguais+1)); continue
    fi
    novos=$((novos+1))
    if [ "$APPLY" -eq 1 ]; then
      mkdir -p "$dest/$(dirname "$rel")"
      [ -f "$dest/$rel" ] && backup_path "$dest/$rel"
      cp "$f" "$dest/$rel"
    fi
  done < <(find "$src" -type f -name '*.md' 2>/dev/null | sort)

  # Arquivo copiado NÃO é agente registrado. A contagem de .md prova apenas o disco.
  # O registro real só é observável na lista `agents` do evento init do runtime —
  # e o runtime ignora ~/.claude/agents quando CLAUDE_CONFIG_DIR aponta para outro lugar.
  # Por isso o estado registrado abaixo vem de willtech-verify-agents.sh, não do `cp`.
  local verif="$SELF_DIR/willtech-verify-agents.sh"
  local reg_status="" reg_n="" reg_why="" reg_cfg="" reg_tried=0
  if [ "$APPLY" -eq 1 ]; then
    if [ -f "$verif" ] && command -v python3 >/dev/null 2>&1; then
      reg_tried=1
      # HOME=$TARGET_HOME importa: a verificação precisa olhar o HOME que foi alvo,
      # não o HOME de quem chamou. Com --home, sem isso, o veredito seria de outro HOME.
      local vjson; vjson="$(HOME="$TARGET_HOME" bash "$verif" --json 2>/dev/null || true)"
      if [ -n "$vjson" ]; then
        reg_status="$(printf '%s' "$vjson" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("status",""))' 2>/dev/null || true)"
        reg_n="$(printf '%s' "$vjson" | python3 -c 'import json,sys;d=json.load(sys.stdin);print(d.get("score",""))' 2>/dev/null || true)"
        reg_why="$(printf '%s' "$vjson" | python3 -c 'import json,sys;d=json.load(sys.stdin);print(d.get("reason") or d.get("proves",""))' 2>/dev/null || true)"
        reg_cfg="$(printf '%s' "$vjson" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("configDirectory",""))' 2>/dev/null || true)"
      else
        reg_status="unverifiable"
        reg_why="o verificador não devolveu resultado (python3 ou runtime indisponível)"
      fi
    else
      # Sem verificador ou sem python3 não há prova de registro possível. Não se
      # declara sucesso por contagem de arquivo — diz-se que não foi verificado.
      warn "não foi possível verificar o registro (falta willtech-verify-agents.sh ou python3)"
      record "Agentes WILLTECH" "1.0" "INSTALADO MAS NÃO HOMOLOGADO" "$novos copiados em disco; registro NÃO verificado (sem verificador/python3)"
    fi
  fi

  if [ "$reg_tried" -eq 1 ] && [ -n "$reg_status" ]; then
    say ""
    if [ "$reg_status" = "structural" ]; then
      say "  verificação ESTRUTURAL dos agentes (sem CLI nesta máquina):"
      ok "$reg_n canônicos com frontmatter válido em $CLAUDE_DIR/agents"
      inf "o Claude Desktop lê esse diretório direto — não precisa do CLI"
      inf "para confirmar que o Desktop os carregou: na aba Code pergunte"
      inf '"quais subagentes você tem disponíveis?" — devem aparecer os 7 willtech-*'
      record "Agentes WILLTECH" "1.0" "INSTALADO — ESTRUTURA OK, REGISTRO NÃO PROVADO" "$reg_n com frontmatter válido; falta confirmar na aba Code"
    else
      say "  registro no runtime (evento init, custo 0 token):"
      inf "configDirectory: ${reg_cfg:-?}"
      if [ "$reg_status" = "ok" ]; then
        ok "$reg_n canônico(s) REGISTRADOS no runtime: $reg_why"
        record "Agentes WILLTECH" "1.0" "HOMOLOGADO (registro)" "$reg_n confirmados na lista agents do evento init; custo 0 token"
      elif [ "$reg_status" = "missing" ]; then
        bad "$reg_n registrados — $reg_why"
        record "Agentes WILLTECH" "1.0" "INSTALADO MAS NÃO REGISTRADO" "$reg_n no init; $reg_why"
      else
        warn "não foi possível verificar o registro: ${reg_why:-motivo desconhecido}"
        record "Agentes WILLTECH" "1.0" "INSTALADO MAS NÃO HOMOLOGADO" "$novos copiados em disco; ${reg_why:-verificação indisponível}"
      fi
    fi
  elif [ "$APPLY" -eq 1 ]; then
    :
  elif [ "$novos" -eq 0 ]; then
    # Só o disco foi conferido; o registro não foi medido (modo --check).
    ok "$iguais arquivo(s) já idênticos em $dest — sem registro verificado (modo --check)"
    record "Agentes WILLTECH" "1.0" "ARQUIVOS OK — REGISTRO NÃO VERIFICADO" "$iguais/7 arquivos idênticos; rode --apply para medir o evento init"
  elif [ "$APPLY" -eq 0 ]; then
    warn "$novos agente(s) a instalar, $iguais já idênticos — rodar com --apply"
    record "Agentes WILLTECH" "1.0" "AUSENTE" "$novos pendentes, $iguais presentes"
  else
    ok "$novos agente(s) instalado(s), $iguais preservado(s) sem alteração"
    record "Agentes WILLTECH" "1.0" "INSTALADO MAS NÃO HOMOLOGADO" "$novos instalados em disco; registro não verificado"
  fi
  # "substituída" só é verdade em --apply; em --check nada foi tocado ainda.
  if [ "$migrados" -gt 0 ]; then
    if [ "$APPLY" -eq 1 ]; then
      ok "$migrados cópia(s) achatada(s) da instalação anterior substituída(s)"
    else
      warn "$migrados cópia(s) achatada(s) a migrar — rodar com --apply"
    fi
  fi

  if [ "$APPLY" -eq 1 ]; then
    say ""
    say "  destino (lido recursivamente pelo runtime):"
    # pattern ausente faz o find falhar; sob pipefail isso abortaria antes do relatório.
    { find "$dest" -type f -name 'willtech-*.md' 2>/dev/null | sed "s|$dest/|    |" | sort; } || true
  fi
}

# ---------------------------------------------------------------- MCPs opcionais
phase_mcp() {
  say ""
  say "FASE 8 — MCPs (só o que acrescenta capacidade real)"
  if [ "${CLAUDE_OK:-0}" -ne 1 ]; then
    warn "Claude Code não localizado — MCPs ficam pendentes"
    record "Astro Docs MCP" "-" "BLOQUEADO" "depende do binário do Claude Code"
    record "Context7 MCP" "-" "BLOQUEADO" "depende do binário do Claude Code"
    record "Serena MCP" "-" "BLOQUEADO" "depende do binário do Claude Code"
    return 0
  fi
  local list; list="$(mcp_list)"

  # Astro Docs e Context7 são HTTP remotos, sem instalação local.
  # O estado registrado no relatório é o que ACONTECEU, não uma intenção.
  local astro_st="AUSENTE" ctx_st="AUSENTE"
  if grep -qi 'astro' <<<"$list"; then
    ok "VALIDADO — PULAR: Astro Docs MCP já configurado"; astro_st="VALIDADO — PULAR"
  elif [ "$APPLY" -eq 1 ]; then
    if claude mcp add --transport http --scope user astro-docs https://mcp.docs.astro.build/mcp; then
      ok "astro-docs adicionado"; astro_st="INSTALADO MAS NÃO HOMOLOGADO"; _MCP_LIST=""
    else
      bad "falha ao adicionar astro-docs"; astro_st="FALHOU"
    fi
  else
    skip "astro-docs: ausente (HTTP oficial https://mcp.docs.astro.build/mcp)"
  fi

  if grep -qi 'context7' <<<"$list"; then
    ok "VALIDADO — PULAR: Context7 já configurado"; ctx_st="VALIDADO — PULAR"
  elif [ "$APPLY" -eq 1 ]; then
    if claude mcp add --transport http --scope user context7 https://mcp.context7.com/mcp; then
      ok "context7 adicionado"; ctx_st="INSTALADO MAS NÃO HOMOLOGADO"; _MCP_LIST=""
    else
      bad "falha ao adicionar context7"; ctx_st="FALHOU"
    fi
  else
    skip "context7: ausente"
  fi

  if grep -qi 'serena' <<<"$list"; then
    ok "VALIDADO — PULAR: Serena já configurado"
  else
    if have serena; then
      if [ "$APPLY" -eq 1 ]; then
        claude mcp add --scope user serena -- serena start-mcp-server --context claude-code --project-from-cwd && ok "serena adicionado"
        _MCP_LIST=""
      else
        skip "serena: binário presente, MCP não configurado"
      fi
    else
      warn "serena ausente — instalar com: uv tool install -p 3.13 serena-agent"
      record "Serena MCP" "-" "AUSENTE" "requer uv tool install -p 3.13 serena-agent"
    fi
  fi

  record "Astro Docs MCP" "-" "$astro_st" "endpoint oficial https://mcp.docs.astro.build/mcp"
  record "Context7 MCP" "-" "$ctx_st" "endpoint oficial https://mcp.context7.com/mcp"
}

# ---------------------------------------------------------------- segurança
phase_security() {
  say ""
  say "FASE 9 — segurança"
  local s="$CLAUDE_DIR/settings.json"
  if [ -f "$s" ]; then
    ok "settings.json presente"
    python3 - "$s" <<'PY' || warn "settings.json não é JSON válido"
import json,sys
d=json.load(open(sys.argv[1]))
for k in ("bypassPermissions","dangerouslySkipPermissions"):
    if d.get(k): print(f"    ! {k} ativo — revisar")
print("    chaves:", ", ".join(sorted(d.keys())) or "(vazio)")
PY
  else
    warn "settings.json ausente"
  fi
  if [ -f "$TARGET_HOME/.claude/willtech_events.log" ]; then
    ok "log de hooks presente: $(wc -l < "$TARGET_HOME/.claude/willtech_events.log" | tr -d ' ') linha(s)"
  else
    skip "willtech_events.log não encontrado neste HOME"
  fi
  record "Hooks/segurança" "-" "VERIFICADO" "sem reconfiguração; nenhum hook duplicado"
}

write_report() {
  local f="$LOG_DIR/willtech-station-$STAMP.md"
  {
    echo "# WILLTECH — relatório de bootstrap"
    echo
    echo "- Executado: $(date "+%Y-%m-%dT%H:%M:%S%z")"
    echo "- Modo: $([ "$APPLY" -eq 1 ] && echo APPLY || echo CHECK)"
    echo "- HOME alvo: $TARGET_HOME"
    echo "- Backup: ${BACKUP_DIR}"
    echo
    echo "| Componente | Versão | Estado | Evidência |"
    echo "|---|---|---|---|"
    for r in "${REPORT[@]}"; do IFS='|' read -r a b c d <<<"$r"; echo "| $a | $b | $c | $d |"; done
  } > "$f"
  say ""
  say "relatório: $f"
}

main() {
  say "WILLTECH ULTRA PRO — bootstrap ($([ "$APPLY" -eq 1 ] && echo APPLY || echo CHECK))"
  if [ "$TARGET_HOME" != "$HOME" ]; then
    warn "--home redireciona só os arquivos deste script; 'claude plugin/mcp' gravam na config real do CLI."
    warn "agentes em $TARGET_HOME/.claude/agents NÃO serão registrados num runtime com HOME=$HOME."
  fi
  # CLAUDE_CONFIG_DIR, quando definido, substitui ~/.claude. Agentes copiados para
  # ~/.claude/agents seriam ignorados em silêncio — a causa exata do "0 agentes".
  if [ -n "${CLAUDE_CONFIG_DIR:-}" ]; then
    warn "CLAUDE_CONFIG_DIR=${CLAUDE_CONFIG_DIR} está definido: o runtime lê os agentes dali, não de $CLAUDE_DIR"
    warn "para registrar os agentes em ~/.claude, remova essa variável do ambiente e rode de novo"
  fi
  phase_inventory
  phase_agents
  phase_egm
  phase_te
  phase_mcp
  phase_security
  write_report
  say ""
  say "Nada foi alterado no OpenCode, em gateways, VPS, credenciais ou produção."
}

main

# WillTech / WILLTECH-BH © 2026 · autoria: github.com/hebwil
