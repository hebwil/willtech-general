# Camada de localização do Claude Code — source por bootstrap e homologate.
# Motivo: no macOS o binário quase nunca está no PATH de um shell não-interativo
# (GUI, duplo clique, cron). Falhar por PATH não é falha de instalação.
#
# Duas formas de existir:
#   a) executável `claude`  → chamado direto
#   b) `cli.js` (o Desktop e o npm instalam assim) → chamado com node
# Uso:  source "bin/_willtech_find_claude.sh";  willtech_use_claude || exit

# Procura o pacote JS do Claude Code. Imprime "node <caminho-do-cli.js>".
willtech_find_claude_js() {
  local p
  for p in \
    "$HOME/.claude/local/node_modules/@anthropic-ai/claude-code/cli.js" \
    "/opt/homebrew/lib/node_modules/@anthropic-ai/claude-code/cli.js" \
    "/usr/local/lib/node_modules/@anthropic-ai/claude-code/cli.js" \
    "$HOME/.npm-global/lib/node_modules/@anthropic-ai/claude-code/cli.js" \
    "$HOME/.bun/install/global/node_modules/@anthropic-ai/claude-code/cli.js" \
    "/Applications/Claude.app/Contents/Resources/app.asar.unpacked/node_modules/@anthropic-ai/claude-code/cli.js"
  do
    if [ -f "$p" ]; then printf '%s\n' "$p"; return 0; fi
  done

  # npm global prefix (resolve nvm, fnm, mise, volta)
  if command -v npm >/dev/null 2>&1; then
    local prefix
    prefix="$(npm prefix -g 2>/dev/null || true)"
    if [ -n "$prefix" ] && [ -f "$prefix/lib/node_modules/@anthropic-ai/claude-code/cli.js" ]; then
      printf '%s\n' "$prefix/lib/node_modules/@anthropic-ai/claude-code/cli.js"; return 0
    fi
  fi

  # varredura rasa em últimos recursos
  local hit
  hit="$(find "$HOME" -maxdepth 6 -type f -path '*@anthropic-ai/claude-code/cli.js' 2>/dev/null \
         | grep -v '/\.Trash/' | sed -n '1p' || true)"
  if [ -n "$hit" ]; then printf '%s\n' "$hit"; return 0; fi

  return 1
}

# Diretório do shim criado por willtech_use_claude. Um `claude` que more ali é o NOSSO
# wrapper, não uma instalação real — aceitá-lo faz o wrapper apontar para si mesmo e o
# `exec` entrar em laço infinito. Esta guarda é o que impede isso.
willtech_shim_dir() { printf '%s' "${TMPDIR:-/tmp}/willtech-claude-shim"; }

willtech_is_own_shim() {
  local p="$1" d; d="$(willtech_shim_dir)"
  [ -n "$p" ] || return 1
  # Compara o alvo RESOLVIDO, não só o diretório: um symlink apontando para o wrapper
  # mora em outro diretório e passaria pela checagem de diretório, recriando o laço.
  local rp rd
  rp="$(cd "$(dirname "$p")" 2>/dev/null && pwd -P)/$(basename "$p")"
  rd="$(cd "$d" 2>/dev/null && pwd -P)/claude"
  # readlink -f existe no macOS 12.3+; quando não existir, cai na comparação de caminho
  local tp td
  tp="$(readlink -f "$rp" 2>/dev/null || printf '%s' "$rp")"
  td="$(readlink -f "$rd" 2>/dev/null || printf '%s' "$rd")"
  [ "$tp" = "$td" ] || [ "$rp" = "$rd" ]
}

willtech_find_claude() {
  # 1) já está no PATH — mas só vale se responder de verdade e não for o nosso shim
  if command -v claude >/dev/null 2>&1; then
    local c; c="$(command -v claude)"
    if ! willtech_is_own_shim "$c" && "$c" --version >/dev/null 2>&1; then
      printf '%s\n' "$c"
      return 0
    fi
  fi

  # 2) caminhos conhecidos de cada forma de instalação
  local p
  for p in \
    "$HOME/.claude/local/claude" \
    "$HOME/.local/bin/claude" \
    "$HOME/.npm-global/bin/claude" \
    "/opt/homebrew/bin/claude" \
    "/usr/local/bin/claude" \
    "$HOME/.bun/bin/claude" \
    "$HOME/.volta/bin/claude" \
    "$HOME/.asdf/shims/claude" \
    "/opt/local/bin/claude"
  do
    if [ -x "$p" ]; then printf '%s\n' "$p"; return 0; fi
  done

  # 3) perguntar ao shell de login do usuário (pega nvm, mise, asdf, bun, fnm…)
  local shell_bin="${SHELL:-/bin/zsh}"
  if [ -x "$shell_bin" ]; then
    local found
    # -ilc: shell interativo+login para carregar .zshrc/.zprofile/.bash_profile
    found="$("$shell_bin" -ilc 'command -v claude' 2>/dev/null | tail -1 | tr -d '\r')"
    if [ -n "$found" ] && [ -x "$found" ]; then printf '%s\n' "$found"; return 0; fi
  fi

  # 4) bundle do Claude Desktop, se o app trouxer um runtime do Code
  for p in \
    "/Applications/Claude.app/Contents/Resources/claude" \
    "/Applications/Claude.app/Contents/Resources/app.asar.unpacked/claude" \
    "$HOME/Applications/Claude.app/Contents/Resources/claude"
  do
    if [ -x "$p" ]; then printf '%s\n' "$p"; return 0; fi
  done

  # 5) npx / npm prefix
  if command -v npm >/dev/null 2>&1; then
    local prefix
    prefix="$(npm prefix -g 2>/dev/null)"
    if [ -n "$prefix" ] && [ -x "$prefix/bin/claude" ]; then
      printf '%s\n' "$prefix/bin/claude"; return 0
    fi
  fi

  # 6) varredura rasa em últimos recursos
  local hit
  hit="$(find "$HOME" -maxdepth 4 -type f -name claude -perm -u+x 2>/dev/null | grep -v '/\.Trash/' | head -1)"
  if [ -n "$hit" ]; then printf '%s\n' "$hit"; return 0; fi

  return 1
}

# Exporta um wrapper "claude" no PATH para os scripts poderem chamar `claude` normalmente.
# Se só existir o cli.js, o wrapper chama `node cli.js` — mesmo efeito, sem depender de PATH.
willtech_use_claude() {
  local bin="" js=""
  bin="$(willtech_find_claude)" || bin=""
  if [ -z "$bin" ]; then
    js="$(willtech_find_claude_js)" || js=""
  fi
  if [ -z "$bin" ] && [ -z "$js" ]; then return 1; fi

  local wrapper_dir; wrapper_dir="$(willtech_shim_dir)"
  mkdir -p "$wrapper_dir" 2>/dev/null || return 1

  # Aspas simples no wrapper, com escaping POSIX: um caminho contendo `"` geraria
  # script sintaticamente inválido se fosse interpolado dentro de aspas duplas.
  wrapper_quote() { printf "'%s'" "$(printf '%s' "$1" | sed "s/'/'\\\\''/g")"; }

  # Nunca reescrever o wrapper apontando para o próprio wrapper (laço). Se o alvo
  # resolvido for o shim, reaproveita o wrapper existente que já aponta para o real.
  if [ -n "$bin" ] && ! willtech_is_own_shim "$bin"; then
    export WILLTECH_CLAUDE_BIN="$bin"
    printf '#!/bin/sh\nexec %s "$@"\n' "$(wrapper_quote "$bin")" > "$wrapper_dir/claude"
  elif [ -n "$js" ]; then
    command -v node >/dev/null 2>&1 || return 1
    export WILLTECH_CLAUDE_BIN="node $js"
    printf '#!/bin/sh\nexec %s %s "$@"\n' "$(wrapper_quote "$(command -v node)")" "$(wrapper_quote "$js")" > "$wrapper_dir/claude"
  elif [ -s "$wrapper_dir/claude" ]; then
    # já existe wrapper válido de uma chamada anterior; só garante o PATH
    :
  else
    return 1
  fi

  chmod +x "$wrapper_dir/claude" 2>/dev/null || return 1
  # o wrapper precisa vencer qualquer outro `claude` do PATH — mas sem empilhar a
  # mesma entrada a cada chamada (5 chamadas viravam 5 entradas idênticas).
  case ":$PATH:" in
    *":$wrapper_dir:"*) : ;;
    *) PATH="$wrapper_dir:$PATH"; export PATH ;;
  esac
  return 0
}

# Mensagem acionável quando não achou.
willtech_claude_missing_help() {
  cat <<'MSG'
  O Claude Code não foi encontrado nesta máquina.

  Ele vem junto com o Claude Desktop, na aba Code. Para habilitar:
    abra o Claude Desktop → aba Code → entre na sua conta

  Se você já usa a aba Code normalmente, o runtime existe e a busca não achou.
  Rode este mesmo instalador de novo; ele procura em todos os locais conhecidos,
  no bundle do app e também pergunta ao shell de login do macOS.

  Se mesmo assim não achar, rode na aba Code uma conversa e peça:
    "onde está o executável do Claude Code nesta máquina?"
MSG
}

# WillTech / WILLTECH-BH © 2026 · autoria: github.com/hebwil
