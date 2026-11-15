# Instalação

## OpenCode (variante ativa)

Os agentes ficam em `~/.config/opencode/agent/` (diretório no singular).

```sh
# 1. Backup do estado atual
cp -a ~/.config/opencode/agent ~/.config/opencode/agent.backup-$(date +%Y%m%d-%H%M%S)

# 2. Copiar os 7 agentes
cp opencode/agent/*.md ~/.config/opencode/agent/

# 3. Reiniciar a sessão do OpenCode (agentes carregam no início da sessão)

# 4. Verificar
#    Em uma sessão nova, o agente principal deve listar os subagentes willtech-*
```

Cada arquivo usa `mode: subagent` no frontmatter — formato nativo do OpenCode.
Não há dependência de hooks, plugins ou configuração extra.

## Claude Code (variante original)

Estrutura de origem: pasta `claude-code/` deste repositório (pacote "willtech-station").

```sh
# 1. Copiar os agentes (o Claude Code lê ~/.claude/agents recursivamente)
mkdir -p ~/.claude/agents
cp -a claude-code/agents/. ~/.claude/agents/

# 2. (Opcional) Roteamento automático: colar o bloco
#    claude-code/settings/willtech-routing.md no fim do ~/.claude/CLAUDE.md

# 3. Iniciar conversa nova e perguntar: "quais agentes você tem disponíveis?"
#    Os 7 nomes willtech-* devem aparecer.
```

O pacote original incluía `INSTALAR.command` (instalador de duplo clique), que não
compõe este snapshot. Para instalação via terminal, o pacote original documentava:

```sh
./bin/willtech-bootstrap.sh --check   # inventário e simulação
./bin/willtech-bootstrap.sh --apply   # instalação idempotente com backup
```

Nota: os scripts de `claude-code/bin/` foram escritos para localizar o runtime do
Claude Code no macOS da estação original; revisar antes de reutilizar em outra máquina.

## Desinstalação

- OpenCode: remover os arquivos `~/.config/opencode/agent/willtech-*.md`.
- Claude Code: remover `~/.claude/agents/general/` e `~/.claude/agents/especialistas/`
  (ou apenas os arquivos `willtech-*.md`).
