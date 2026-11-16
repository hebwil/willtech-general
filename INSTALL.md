# Instalação

## Codex (variante nativa ativa)

```sh
mkdir -p ~/.codex/agents
# Backup apenas se já existirem agentes (instalação limpa não tem o que copiar)
if [ -n "$(ls -A ~/.codex/agents 2>/dev/null)" ]; then
  cp -a ~/.codex/agents ~/.codex/agents.backup-$(date +%Y%m%d-%H%M%S)
fi
cp codex/agents/*.toml ~/.codex/agents/
```

Reinicie a sessão do Codex e confirme os sete nomes `willtech-*`.

**Limite de segurança:** o Codex não oferece, nesta configuração, permissão
declarativa por agente no TOML. Os limites de leitura/escrita são instruções; um
teste adversarial permitiu escrita pelo `willtech-explorador`. Não use esta
variante como isolamento forte sem controles adicionais do runtime.

## OpenCode (variante ativa, homologada no runtime 2.2.6)

Os agentes ficam em `~/.config/opencode/agent/` (diretório no singular).
Os wrappers de shell ficam em `~/.config/opencode/bin/`.

```sh
# 1. Backup do estado atual
STAMP=$(date +%Y%m%d-%H%M%S)
mkdir -p ~/.willtech-backups/opencode-$STAMP
cp -a ~/.config/opencode/agent ~/.willtech-backups/opencode-$STAMP/
cp -a ~/.config/opencode/AGENTS.md ~/.willtech-backups/opencode-$STAMP/

# 2. Copiar os 7 agentes, os wrappers e a política do comandante
cp opencode/agent/*.md ~/.config/opencode/agent/
mkdir -p ~/.config/opencode/bin
cp opencode/bin/* ~/.config/opencode/bin/
chmod +x ~/.config/opencode/bin/*
cp opencode/AGENTS.md ~/.config/opencode/AGENTS.md

# 3. Reiniciar a sessão do OpenCode (agentes carregam no início da sessão)

# 4. Verificar
opencode debug agents
#    Os 7 agentes willtech-* devem aparecer com as regras de permissão novas.
#    Se o binário não estiver no PATH, use o caminho do app instalado.

# 5. Rodar a regressão dos wrappers (não usa modelo, custo zero)
sh opencode/tests/test-wrappers.sh
```

Cada arquivo usa `mode: subagent` no frontmatter — formato nativo do OpenCode.
`~/.config/opencode/opencode.json` não é alterado: provedores, MCPs e
`experimental.subagent_depth` permanecem como estão.

**Requisito para a delegação aninhada:** o fluxo comandante → General →
especialista exige `experimental.subagent_depth: 2`. Numa instalação limpa,
mescle no `~/.config/opencode/opencode.json` existente (sem sobrescrever o
restante):

```json
{
  "experimental": {
    "subagent_depth": 2
  }
}
```

Sem essa profundidade, o General pode não conseguir acionar os especialistas.

### Rollback

```sh
BK=~/.willtech-backups/opencode-<STAMP>
cp -a "$BK/agent/." ~/.config/opencode/agent/
cp -a "$BK/AGENTS.md" ~/.config/opencode/AGENTS.md
```

Os wrappers podem ser removidos de `~/.config/opencode/bin/` após restaurar os
agentes antigos, que não os referenciam.

### Uso dos wrappers

```sh
~/.config/opencode/bin/willtech-read-shell "git status --short"
~/.config/opencode/bin/willtech-test-shell "npm test"
```

O comando vai **inteiro entre aspas duplas**. Sem aspas, o runtime nega a chamada;
isso impede que `>`, `;`, `&&` e `|` sejam executados fora do sandbox.

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

O instalador por duplo clique está em `claude-code/INSTALAR.command`. Para
instalação reproducível via terminal, use:

```sh
cd claude-code
./bin/willtech-bootstrap.sh --check   # inventário e simulação
./bin/willtech-bootstrap.sh --apply   # instalação idempotente com backup
```

Nota: os scripts de `claude-code/bin/` foram escritos para localizar o runtime do
Claude Code no macOS da estação original; revisar antes de reutilizar em outra máquina.
O caminho correto dentro deste repositório é `claude-code/bin/`, e não a raiz.

**Estado desta variante:** pacote preservado e validado apenas sintaticamente
(`bash -n`, `zsh -n`, `py_compile`). `~/.claude/agents` não existe nesta máquina e a
delegação real **não foi homologada**. Não instale sem uma sessão autenticada e uma
rodada de testes na superfície real.

## Desinstalação

- OpenCode: remover os arquivos `~/.config/opencode/agent/willtech-*.md`.
- Claude Code: remover `~/.claude/agents/general/` e `~/.claude/agents/especialistas/`
  (ou apenas os arquivos `willtech-*.md`).
