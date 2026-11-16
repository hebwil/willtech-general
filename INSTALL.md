# Instalação

## Sistemas operacionais

Os comandos das seções por plataforma são Unix (`sh`): executam em **macOS**
(validado nesta estação) e seguem os mesmos requisitos em **Linux** e dentro
do **WSL** (python3, git, shell POSIX) — esses dois caminhos não foram
exercitados aqui e não têm suporte anunciado. **Não execute comandos `sh`
diretamente no PowerShell**: para Windows nativo use o instalador PowerShell
dedicado (seção abaixo). Os wrappers de sandbox do OpenCode usam
`sandbox-exec`, exclusivo do macOS; em Linux/WSL/Windows permanecem as
permissões por agente do runtime, sem esse sandbox adicional — no Windows os
wrappers não são instalados e o shell dos agentes segue restrito.

As três integrações de IA (Codex, OpenCode V2, Claude Code) são independentes
do sistema operacional e estão separadas abaixo.

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
#    Backup apenas se já existirem agentes (instalação limpa não tem o que copiar)
mkdir -p ~/.claude/agents
if [ -n "$(ls -A ~/.claude/agents 2>/dev/null)" ]; then
  cp -a ~/.claude/agents ~/.claude/agents.backup-$(date +%Y%m%d-%H%M%S)
fi
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
Claude Code em macOS; revisar antes de reutilizar em outro ambiente.
O caminho correto dentro deste repositório é `claude-code/bin/`, e não a raiz.

**Estado desta variante:** pacote preservado e validado apenas sintaticamente
(`bash -n`, `zsh -n`, `py_compile`). A delegação real **não foi homologada**
(estado detalhado em EVOLUCAO.md). Não instale sem uma sessão autenticada e uma
rodada de testes na superfície real.

## Automação nativa 2.2.1 (projeto-local, opcional)

Ativa os hooks/plugins que acionam brief, guardas de loop, candidatas de lição,
revisão goldfish e drift automaticamente. Escreve **apenas dentro do repo alvo**
(`.claude/`, `.codex/`, `.opencode/`, `.willtech/`); nada global é alterado e as
telas oficiais de trust/permissão de cada plataforma continuam valendo.

```sh
sh tools/willtech-install.sh            # lista as mudanças e pede confirmação
sh tools/willtech-install.sh --yes      # instalação idempotente (consentimento dado)
sh tools/willtech-install.sh --platform opencode   # só uma plataforma
sh tools/willtech-install.sh --disable  # desliga (remove .willtech/enabled)
sh tools/willtech-install.sh --enable   # religa
sh tools/willtech-install.sh --uninstall  # restaura backups pré-instalação
```

- **Claude Code**: mescla `claude-code/settings/willtech-hooks.json` no
  `.claude/settings.json` do projeto (backup prévio). O projeto precisa ser
  confiado na tela oficial do Claude Code.
- **Codex**: mescla `codex/hooks.json` em `.codex/hooks.json` do projeto. Hooks
  não gerenciados exigem revisão e trust do usuário via `/hooks` — sem isso,
  não executam.
- **OpenCode V2**: copia `opencode/plugins/willtech/index.js` para
  `.opencode/plugins/willtech/` (descoberta automática). V1 não é suportado.

Regressão sem custo de modelo: `sh tools/test-auto.sh` (38 verificações; a
simulação do plugin V2 usa node quando disponível — `NODE_BIN` aceita um
binário alternativo; sem node, esse item é SKIP e os demais rodam).

## Windows nativo (PowerShell)

**Requisitos:** Windows 10/11, Python 3 (`python3`, `python` ou `py -3` no
PATH) e `git`. O núcleo usa lock real do sistema (`msvcrt.locking` em sidecar
`.lock`) — a mesma exclusão mútua do `flock` Unix, sem arquivos-sentinela.

```powershell
# A partir da raiz do repositório. -ExecutionPolicy Bypass vale SOMENTE para
# este processo; nenhuma política global é alterada.
powershell -ExecutionPolicy Bypass -File tools\willtech-install.ps1            # lista mudanças e pede confirmação
powershell -ExecutionPolicy Bypass -File tools\willtech-install.ps1 -Yes      # instalação idempotente (consentimento dado)
powershell -ExecutionPolicy Bypass -File tools\willtech-install.ps1 -Platform opencode
powershell -ExecutionPolicy Bypass -File tools\willtech-install.ps1 -Disable  # desliga (remove .willtech\enabled)
powershell -ExecutionPolicy Bypass -File tools\willtech-install.ps1 -Enable   # religa
powershell -ExecutionPolicy Bypass -File tools\willtech-install.ps1 -Uninstall  # restaura backups pré-instalação
```

O instalador é projeto-local (`.claude\`, `.codex\`, `.opencode\`,
`.willtech\`), faz backup prévio das configurações existentes
(`.willtech-bak`), preserva hooks do usuário e é idempotente. Sem Python
detectado, a instalação é **recusada** (os controles obrigatórios não
rodariam). Os hooks gravados usam o comando Python detectado no lugar de
`python3`; o formato JSON dos contratos não muda.

**Limites de segurança no Windows:** os wrappers `sandbox-exec` (macOS) não
são instalados; as ferramentas de shell dos agentes permanecem negadas pelas
permissões do runtime — nenhuma execução irrestrita é liberada para simular
compatibilidade. A disponibilidade dos runtimes Codex e Claude Code em
Windows nativo não foi verificada nesta estação; o OpenCode V2 carrega o
plugin normalmente onde o runtime existir.

**Estado:** implementação validada por regressão Unix completa e simulação
determinística da lógica do instalador (merge/backup/idempotência/restauração,
caminhos com espaços e Unicode). A execução nativa em Windows
**PENDENTE DE HOMOLOGAÇÃO** — sem runner Windows acessível (escopo
`workflow` ausente no token; sem máquina Windows). Regressão local:
`python3 tools\test-compat.py` (22 verificações, cross-platform).

## Desinstalação

- OpenCode: remover os arquivos `~/.config/opencode/agent/willtech-*.md`.
- Claude Code: remover `~/.claude/agents/general/` e `~/.claude/agents/especialistas/`
  (ou apenas os arquivos `willtech-*.md`).
- Windows nativo: `tools\willtech-install.ps1 -Uninstall` reverte a automação
  com restauração de backups; agentes copiados manualmente são removidos dos
  diretórios de agentes de cada runtime.
