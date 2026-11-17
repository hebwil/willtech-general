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

### Delegação e autorizações

Os contratos já orientam o comandante a acionar o General e este a selecionar
especialistas reais. Ao pedir essa cadeia, não encaminhe instruções conflitantes
como "você mesmo faz a leitura" ao General. Indique explicitamente o arquivo e
que a leitura cabe ao `willtech-explorador`.

Use um arquivo dentro do workspace autorizado. Se a ação exigir aprovação,
use a interface interativa oficial: o cliente não interativo pode retornar
`permission.rejected` porque não consegue consultar o usuário. Não amplie
permissões nem use aprovação indiscriminada para forçar o teste.

Para o serviço já gerenciado pelo Desktop, prefira a descoberta automática do
cliente oficial. Uma URL de servidor explícita pode exigir autenticação adicional;
use apenas autenticação/pareamento oficiais, sem registrar senhas em comandos,
URLs ou logs e sem desabilitar autenticação. A delegação real já foi observada,
mas o teste DeepSeek com leitura rejeitada e timeout não homologou a tarefa
completa; detalhes em EVOLUCAO.md.

### Painel visual experimental (OpenCode Desktop)

**Contrato oficial verificado para 2.2.6; homologação gráfica nativa pendente.**
A API `@opencode/plugin/gui` é experimental. Outras versões, inclusive 2.2.7,
ficam desativadas nesta implementação até a validação do contrato correspondente.
O painel não funciona no OpenCode terminal nem substitui os sete agentes nativos.
Integrado na `main` via [PR #8](https://github.com/hebwil/willtech-general/pull/8);
smoke headless de laboratório aprovado com o bundle real (64/64 em três rodadas
+ 3/3 reduced-motion; evidências em `tools/smoke-evidence/`). O smoke é simulação
em navegador headless e **não constitui homologação nativa no Desktop**.

O pacote `opencode/plugins/willtech/visual/` contribui somente GUI: não tem
export de servidor. Assim, carregar o painel não duplica nem modifica o plugin
de automação `opencode/plugins/willtech/index.js`. O instalador projeto-local
continua copiando apenas a automação; `--disable` e `--uninstall` da automação
não controlam este pacote visual independente.

Para experimentar, mantenha o checkout deste repositório disponível e, pela
configuração oficial do Desktop, **mescle uma única entrada** no array `plugins`
do `opencode.json` ou `opencode.jsonc` que seu servidor de fundo efetivamente
carrega. Não substitua o arquivo nem o array existente:

```json
{
  "plugins": [
    {
      "package": "./opencode/plugins/willtech/visual",
      "options": { "enabled": true }
    }
  ]
}
```

O caminho relativo acima pressupõe configuração na raiz deste checkout.
Em outra localização, use o caminho absoluto da pasta `visual` no checkout,
selecionado por você. Isso não altera provedores, modelos, permissões, agentes
ou profundidade de delegação. Nenhuma configuração pessoal é modificada por
scripts deste pacote. O Desktop carrega GUI pelos plugins de **seu próprio
servidor de fundo**: instalar o plugin em um projeto/servidor remoto não garante
que sua GUI apareça na janela. Não registre novamente o plugin de automação.

Recarregue pela interface oficial de extensões e use o comando
**WillTech: mostrar/ocultar equipe** com uma sessão aberta. O painel começa
fechado. Ele mostra somente a família da sessão aberta e sessões que o cliente
já sincronizou; agentes não observados ficam aguardando, nunca trabalhando.
Os nomes vêm de `Session.Info.agent`, não de títulos, prompts ou mensagens.
Sessões de fork não são usadas como execução própria.

| Evidência nativa | Indicação |
| --- | --- |
| Sem execução observada ou sem dados suficientes | Aguardando |
| `session.execution.started`, ou execução em dados sincronizados | Trabalhando na especialidade correspondente |
| `session.execution.succeeded` | Concluído |
| `session.execution.failed` | Erro |
| Pedido de permissão pendente durante execução | Aguardando autorização |
| `session.execution.interrupted` | Interrompido, nunca concluído com sucesso |
| Desconexão/servidor incompatível | Sem conexão, sem animação |

O marcador otimista `running` do cliente, sozinho, não indica trabalho.
Falhas recuperáveis de ferramentas não são confundidas com falha terminal da
execução. O General usa o APNG original somente durante trabalho observado;
os demais mascotes mantêm seus WebP originais com efeito CSS leve. Pausar,
ocultar o painel e `prefers-reduced-motion` removem o movimento, usando o WebP
estático do General. Nenhum WebGL, modelo, polling, ferramenta, escrita ou
nova delegação é acionado pelo painel. Os oito arquivos de imagem usados são
embutidos com seus bytes originais no bundle, sem CDN ou requisições externas.

**Reversão segura:** desligue o pacote visual em Settings > Extensions > Plugins,
ou mude sua opção `enabled` para `false`, ou remova **somente sua entrada** do
array `plugins`. Inscrições e contribuições GUI são retiradas pelo ciclo de vida
oficial. Não apague diretórios compartilhados nem remova a automação. O botão
Pausar animações afeta somente a apresentação, não interrompe agentes.

**Outras plataformas:** a documentação do Codex descreve plugins/MCP e UI em
hosts MCP Apps, particularmente ChatGPT; não comprova uma API passiva de painel
nativo Codex com eventos de todos os agentes. Nenhuma GUI Codex é distribuída.
Claude Code possui agora uma API oficial de **mods**, com `Pane`, `ui.render`
e `$.agent.list()` em versões mais novas (referência 2.1.290+); portanto não se
afirma ausência de extensão gráfica. Seu suporte a elementos varia por
superfície: `Image` é documentado para terminal, não para Desktop/VS Code.
A animação dos mascotes originais por essa API não foi homologada nesta entrega;
nenhuma GUI Claude Code é distribuída e os hooks existentes permanecem intactos.

Build reproduzível, sem instalar dependências:

```sh
python3 tools/build-gui.py
python3 tools/test-gui.py
```

`tools/test-gui.html` é uma bancada de navegador com **host e eventos simulados**,
rotulada como tal. Sirva a raiz do checkout em um servidor HTTP local que envie
`.cjs` como JavaScript, abra essa página e use seu botão de execução única.
Seu resultado não prova carregamento no Desktop nem execução real dos agentes.
Nesta rodada, o navegador embutido permaneceu oculto: a captura foi bloqueada
por `NATIVE_BROWSER_VIEWPORT_UNAVAILABLE`, e a bancada não retornou resultado
consolidado ao aguardar `image.decode()` do APNG. O helper foi limitado a eventos
de carga com timeout, sem repetir a rodada; essa correção da bancada não foi
revalidada. Nenhum screenshot ou PASS gráfico é anunciado. Para homologar, ainda são necessários carregamento pela API
no Desktop 2.2.6, evento de agente real, término/erro, sete identidades,
regressão de orquestração e desativação segura. Não execute chamadas pagas
somente para produzir uma demonstração, nem apresente replay como teste nativo.

Fontes oficiais, verificadas em 2026-11-16:
- [OpenCode GUI API](https://opencode.ai/docs/build/plugins/gui/)
- [SDK da release 2.2.6](https://github.com/anomalyco/opencode/blob/v2.2.6/packages/plugin/src/gui/index.ts)
- [Sessões e projeção de eventos 2.2.6](https://github.com/anomalyco/opencode/blob/v2.2.6/packages/client/src/solid/data.ts)
- [UI de plugins OpenAI/MCP Apps](https://developers.openai.com/plugins/build/chatgpt-ui)
- [Mods e superfícies Claude Code](https://code.claude.com/docs/en/plugins/mods/reference.md)

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
revisão goldfish e drift automaticamente. O instalador existente já oferece
**ativação projeto-local com consentimento**: sem `--yes`, lista as alterações
no alvo e pede confirmação; `--yes` representa consentimento explícito.
Escreve **apenas dentro do repo alvo** (`.claude/`, `.codex/`, `.opencode/`,
`.willtech/`); nada global é alterado e as telas oficiais de trust/permissão
continuam valendo. Não instala agentes globalmente nem altera provedores.

Por padrão, o alvo é este checkout. Para outro projeto, use
`--repo "/caminho/do/projeto"` (PowerShell: `-Repo "C:\caminho\projeto"`).
O alvo precisa conter `tools/willtech-auto.py`, `tools/willtech-dossie.py`,
`tools/willtech-drift.py` e `claude-code/bin/willtech_trace.py`, com caminhos
relativos preservados. Disponibilize esses arquivos do pacote sem sobrescrever
arquivos de terceiros; o instalador não copia nem remove essas pastas de código.
Os templates continuam vindo do checkout de origem. Nenhum caminho pessoal é
necessário. A ativação acontece somente depois que os componentes são gravados.

```sh
sh tools/willtech-install.sh            # lista as mudanças e pede confirmação
sh tools/willtech-install.sh --yes      # instalação idempotente (consentimento dado)
sh tools/willtech-install.sh --platform opencode   # só uma plataforma
sh tools/willtech-install.sh --disable  # desliga (remove .willtech/enabled)
sh tools/willtech-install.sh --enable   # religa
sh tools/willtech-install.sh --uninstall  # restaura backups pré-instalação
```

### Sala dos agentes 3.0 (opt-in, comando manual)

A sala (`tools/willtech-room.py`) é **dado de projeto**, não automação: o instalador de hooks não a cria sozinho — o banco exige um repositório git inicializado e a adoção é decisão do projeto. Para adotar, rode uma vez no projeto alvo:

```sh
python3 tools/willtech-room.py init .willtech/room.db --repo .
```

Idempotente: migra `user_version` 1→2→3 sem perda de dados, faz backup verificado `.bak-<timestamp>` (API `sqlite3.backup` + `PRAGMA integrity_check` na cópia) e restaura com `restore --from BACKUP`. Requisito: Python 3 com `sqlite3` da stdlib; FTS5 é opcional (gate no CI Windows; sem ele, a consulta usa fallback LIKE portável, implementado e testado). Lock cross-processo via transação SQLite (`BEGIN IMMEDIATE` em sidecar `.lock`) — sem `fcntl`/`msvcrt`, portável macOS/Linux/Windows. `--disable` e `--uninstall` do instalador **não removem** `.willtech/room.db` (dado do usuário, preservado como dossiê/cache) — eles apenas param a automação; para descartar a sala manualmente, apague `.willtech/room.db`, `.willtech/room.db.lock` e os `.willtech/room.db.bak-*`.

<!-- Decisão: o instalador não roda `room init` automaticamente — test-install.py homologa idempotência/posse/preflight do instalador (risco de regressão multiplataforma), o banco exige repo git (indisponível no momento de instalação em cópias frescas) e falha silenciosa deixaria o usuário acreditando que a sala existe. Comando manual único, idempotente e falha-alta. -->

- **Claude Code**: mescla `claude-code/settings/willtech-hooks.json` no
  `.claude/settings.json` do projeto (backup prévio). O projeto precisa ser
  confiado na tela oficial do Claude Code.
- **Codex**: mescla `codex/hooks.json` em `.codex/hooks.json` do projeto. Hooks
  não gerenciados exigem revisão e trust do usuário via `/hooks` — sem isso,
  não executam.
- **OpenCode V2**: copia `opencode/plugins/willtech/index.js` para
  `.opencode/plugins/willtech/` (descoberta automática). V1 não é suportado.

### Reversão preservando terceiros

`--disable`/`-Disable` remove somente `.willtech/enabled`, sem apagar hooks,
plugin, diretórios, dossiê ou cache. `--uninstall`/`-Uninstall` usa registros
`.willtech-managed.json` ao lado dos componentes para retirar somente os
handlers adicionados; texto semelhante em um hook de terceiros não é critério
de remoção. `.willtech-created` marca arquivos criados pelo instalador;
`.willtech-bak` conserva os originais, inclusive o plugin.

Se o componente não foi alterado depois, o backup é restaurado byte a byte.
Se configurações/hooks de terceiros foram acrescentados ou editados, são
preservados e o backup original permanece quando restaurá-lo apagaria essas
mudanças. Plugin modificado pelo usuário, seu backup e registro são preservados
com aviso. Diretórios não são removidos, nem `tools/`, `claude-code/` ou
`.willtech/`; os auxiliares de código e arquivos de terceiros ficam intactos.

Componentes sem registro de posse não são apagados. Backups/marcadores antigos
sem registro também não são adotados automaticamente: a instalação para nesse
componente, preservando-o. Revise e restaure os originais manualmente antes de
reinstalar; não apague backups para contornar a proteção. Symlinks no estado de
instalação e componentes que resolvam fora do alvo são recusados.

Validação direcionada dos instaladores: `python3 tools/test-install.py`.
Executa o shell real e os blocos Python embutidos do PS1 em laboratório dentro
do checkout, sem instalar em runtimes pessoais ou chamar modelos. A execução
do helper PS1 não equivale a homologação nativa do PowerShell.

Suíte geral já existente: `sh tools/test-auto.sh` (40 verificações; a simulação
do plugin V2 usa node quando disponível — `NODE_BIN` aceita um binário
alternativo; sem node, esse item é SKIP e os demais rodam). Não foi repetida
nesta consolidação, pois núcleo/hooks/plugin não foram modificados.

## Interface visual dos sete agentes (experimental)

Painel/visualizador dos sete mascotes reagindo à atividade real. Núcleo único
de interpretação (`opencode/plugins/willtech/visual/activity.cjs`); zero
chamadas de IA. **Estado experimental**: aprovado em laboratório (suítes
determinísticas, kit oficial do Claude Code, binário descartável do App
Server, capturas headless); homologação nativa em sessão real **não
realizada** — limitações detalhadas em EVOLUCAO.md.

### OpenCode Desktop (painel nativo do plugin, ≥ 2.2.6)

O painel já acompanha o plugin visual existente (`opencode/plugins/willtech/`,
opt-in `enabled: true`). Correção 2.3: versões atuais do Desktop (2.2.7+,
2.3.0) voltam a exibir o painel, que antes era travado ao pin exato 2.2.6.

### Claude Code (Mod oficial)

```sh
claude plugin validate claude/plugins/willtech-visual   # validação oficial
claude plugin test claude/plugins/willtech-visual       # kit oficial (3/3)
claude plugin install ./claude/plugins/willtech-visual  # instalação
```

No aplicativo, o comando `/willtech-team` abre o painel com os sete mascotes
(desktop: SVG+SMIL; terminal: `Image` + `$.ui.blit`). Pausa manual e
`options.reducedMotion` controlam a animação (Mods não expõem API de SO para
reduced-motion).

### Codex (visualizador complementar, independente)

O Codex não expõe painel nativo de 7 agentes; este visualizador é uma página
local separada alimentada pelos hooks oficiais e pelo App Server. O aplicativo
Codex não é modificado.

```sh
# 1. Mesclar hooks/hooks.json ao .codex/hooks.json do projeto (trust via /hooks)
# 2. Gerar núcleo e assets (cópia verbatim do núcleo compartilhado)
python3 codex/willtech-visual/tools/build-codex.py
# 3. Subir o servidor local e abrir no navegador
node codex/willtech-visual/viewer/server.cjs 8741
```

Testes: `python3 -m unittest tools.test-codex` (determinísticos) e
`WILLTECH_CODEX_BIN=<binário> python3 -m unittest tools.test-appserver`
(handshake real, opcional). Feed padrão: `.codex/willtech-events.jsonl`.

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

**Evidência histórica:** núcleo e instalador da versão `c70e5e8` homologados
em Windows nativo real (`windows-latest`, Python 3.12.10, Windows PowerShell 5.1):
[workflow 43892063828 aprovado](https://github.com/hebwil/willtech-general/actions/runs/43892063828).
Bateria `tools/test-compat.py` 22/22, recusa real de `.env` e ciclo completo
com backup, merge preservando configurações, idempotência, desativação,
reativação e restauração integral. Caminho com espaços e Unicode (`Ação`)
preservado; plugin copiado e núcleo do laboratório sem alterações.
A sentinela `@none` preserva o argumento vazio do launcher sem vazar para
os hooks. Arquivos criados pelo instalador recebem `.willtech-created`,
removido no uninstall, para não gerar backups indevidos na reinstalação.
A consolidação posterior corrige a reversão em ambos os instaladores, validando
o shell e o Python embutido do PS1; o ciclo PowerShell não foi reexecutado
nativamente nessa rodada. Núcleo e testes de compatibilidade já aprovados foram
preservados, sem repetição. Linux/WSL não exercitados; runtimes de IA não foram
homologados por este workflow e nenhum modelo foi chamado.

## Desinstalação

- OpenCode: remover os arquivos `~/.config/opencode/agent/willtech-*.md`.
- Claude Code: remover `~/.claude/agents/general/` e `~/.claude/agents/especialistas/`
  (ou apenas os arquivos `willtech-*.md`).
- Visual: OpenCode — o painel pertence ao plugin (removê-lo desativa o painel);
  Claude Code — `claude plugin uninstall willtech-visual`; Codex — remover o
  bloco visual de `.codex/hooks.json` (o visualizador local é encerrado ao
  parar o servidor).
- Windows nativo: `tools\willtech-install.ps1 -Uninstall` reverte a automação
  com restauração de backups; agentes copiados manualmente são removidos dos
  diretórios de agentes de cada runtime.
