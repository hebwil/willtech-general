# WILLTECH — homologação: o que já está provado e o que falta

Este documento substitui o `RELATORIO.md` anterior como fonte do estado de homologação.

## Resposta curta e honesta

**A arquitetura não está homologada.** Pela sua própria regra final, só posso declarar homologação
completa quando todos os testes passarem na instalação real do seu Mac, incluindo delegação
automática comprovada. Essa sessão não tem acesso ao seu Mac nem a uma sessão autenticada, então
os testes de delegação **não foram executados** aqui. Eu não vou simular.

O que fiz nesta rodada: reauditei o que é verificável sem login, encontrei dois defeitos reais de
configuração, e construí o arnês que roda a homologação completa na sua máquina.

## Onde exatamente está o bloqueio

| Bloqueio | Fato verificado | Consequência |
|---|---|---|
| Sem acesso ao `~/.claude` do Mac | montagem recusada: local protegido do host | não inventario seus agentes, plugins e hooks reais |
| Sessão sem autenticação | `claude auth status` → `loggedIn: false` | nenhum teste de modelo pode rodar |
| Ambiente Linux, não macOS | `uname -sm` → `Linux aarch64` | nada aqui vale como homologação do Mac |

E um bloqueio que **não** existe mais: a falha `claude CLI ausente do PATH` que você viu era do
script, não da sua instalação. O runtime estava lá. Os dois scripts agora localizam o binário
sozinhos — inclusive quando só existe o `cli.js` que o Desktop instala — e nunca dependem de `PATH`.

## Reauditoria — o que foi medido de fato nesta sessão

Comandos executados e resultado observado, sem exposição de segredo:

| Verificação | Comando | Resultado |
|---|---|---|
| Versão do runtime | `claude --version` | `2.1.325 (Claude Code)` |
| Autenticação | `claude auth status` | `loggedIn: false`, `authMethod: none` |
| Plugins habilitados | `claude plugin list --json` | 2 plugins, ambos `enabled: true` |
| Inventário EGM | `claude plugin details egm@egm` | 7 skills, **0 agents registrados**, 0 hooks, ~464 tok fixos |
| Inventário TE | `claude plugin details tokeneconomizer@...` | 7 skills, **6 hooks**, ~209 tok fixos |
| Hook SessionStart | `scripts/te-hook < payload` | exit 0, `{}`, criou `~/.tokeneconomizer/{bin,repos,locks}` |
| Hook UserPromptSubmit | `scripts/te-hook < payload` | exit 0, `{}` |
| Micro-skills | `te microskills` | "(nothing injected yet: no fact has cleared its firing gate)" |
| Catálogo de ferramentas | `te toolprune refresh-catalog` | 23 ferramentas, incluindo `Task` — **não** `Agent` |
| Proteção de delegação | `te config set toolprune_protect=Agent,Task` | gravado e relido como `['Agent','Task']` |
| MCP Astro Docs | `claude mcp list` | `✔ Connected` |
| MCP Context7 | `claude mcp list` | `✔ Connected` |

## Estrutura de pastas dos agentes — verificada no runtime

Os agentes ficam em `agents/general/` (o coordenador) e `agents/especialistas/` (os seis). Isso não
é só organização: eu verifiquei no binário 2.1.325 que `~/.claude/agents` é lido **recursivamente**
e que o nome do agente vem do campo `name` do frontmatter, não do nome do arquivo.

Três experimentos controlados, com `claude -p --output-format stream-json` lendo o campo `agents`
do evento `init`:

| Experimento | Resultado medido |
|---|---|
| agente em `agents/general/deep-agent.md` | apareceu no init como `deep-agent` — subpasta é carregada |
| agente em `agents/especialistas/sub/profundo.md` | apareceu como `profundo-3-niveis` — recursão até 3 níveis, nome do frontmatter |
| os 7 agentes WILLTECH na estrutura final | 7 nomes `willtech-*`, **sem duplicata** |

O instalador preserva a estrutura e trata o caso de quem instalou a versão anterior, em que os
arquivos ficavam soltos. Ao encontrar a cópia achatada, ele faz backup e remove a duplicata — sem
isso o runtime veria o mesmo agente duas vezes e resolveria por nome, em silêncio.

## Dois defeitos reais encontrados agora

**O plugin EGM registra zero agentes neste runtime.** `claude plugin details egm@egm` reporta
`Agents (0)`, e o próprio CLI emite o aviso: *"Default agents/ folder is ignored because the
manifest sets agents"*. Consequência prática: as personas revisoras Goldfish não existem como
subagentes nomeados; a revisão cai no caminho de fallback do próprio plugin (subagente genérico
lendo o arquivo de persona). Isso não é falha da sua instalação — é o comportamento do plugin na
versão 0.1.1 com este Claude Code. Registro como limitação, não como sucesso.

**O catálogo de ferramentas desta versão usa `Task`, não `Agent`.** O binário trata os dois nomes
(`e!=="Agent"&&e!=="Task"`), mas o catálogo do TokenEconomizer lista `Task`. Por isso o
`toolprune_protect` precisa conter **os dois**: proteger só `Agent` deixaria a delegação exposta ao
pruning. Meus agentes declaram `tools: [..., Agent]`; o arnês verifica ambos na proteção.

## Achado que muda o TESTE E

As **7 skills do EGM** têm `disable-model-invocation: true`. O modelo não pode acioná-las; só você,
digitando `/egm:egm-review`. Portanto "acionamento automático do EGM pelo modelo" não é um
comportamento que o plugin permite. O veredito possível é: o General sinaliza que o EGM é cabível,
e **você** dispara o comando. O arnês trata isso como `PARCIAL` quando detecta a restrição, em vez
de reprovar o plugin por obedecer ao próprio contrato.

## O que foi entregue para fechar a homologação

`bin/willtech-homologate.sh` roda A–I em sessões reais, na sua configuração normal, criando um
laboratório isolado em `~/.willtech-lab/<timestamp>/repo`. Ele não instala, não reconfigura e só
escreve dentro do laboratório. `--plan` mostra o que faria sem gastar token; `--run --yes-spend`
exige consentimento explícito de custo.

`bin/willtech_trace.py` é o parser de evidência: extrai do `stream-json` a sessão, o modelo, os
agentes disponíveis, as delegações de nível principal, as delegações aninhadas (General →
especialista), a skill realmente invocada, as negações de permissão e o uso de tokens. Se um campo
não estiver no stream, ele reporta ausente em vez de inferir.

### Como o veredito é decidido

A = nenhuma delegação em tarefa trivial. B = nenhuma delegação **e** arquivo criado. C = o
transcript contém `subagent_type: willtech-general` sem você ter pedido pelo nome. D = existe
delegação aninhada. E = `subagent_type` ou skill `egm-*` efetivamente invocada; se houver
`disable-model-invocation`, `PARCIAL` com causa; se o plugin não existir, `NÃO TESTADO`. F =
plugin habilitado **e** diretório de estado criado por hook **e** `Agent`+`Task` protegidos **e**
tokens dobrados acima de zero; caso contrário `PARCIAL` ou `FALHOU`. G = o agente de leitura tentou
escrever e o arquivo não existe no disco. I = a lista de agentes é idêntica entre duas sessões.

### Validação do arnês

Testei o arnês contra um `claude` falso que emite transcripts controlados, para provar que ele não
dá veredito por acidente. Cinco cenários: delegação presente → C e D homologados; ausência de
delegação em tarefa trivial → A homologado; EGM ausente do ambiente → `NÃO TESTADO`; EGM instalado
com restrição → `PARCIAL` com causa e rota; TE com tokens dobrados → `HOMOLOGADO`, sem tokens →
`PARCIAL`. Três defeitos de veredito apareceram nesse processo e foram corrigidos: E lia a lista de
skills disponíveis em vez da invocação real, B marcava homologado sem o arquivo existir, e F
devolvia `PARCIAL` fixo independentemente do que mediu.

## O que você precisa rodar

**Sem terminal:** duplo clique em `INSTALAR.command`. Ele instala o que falta e, no fim, pergunta se
você quer rodar a homologação. O padrão é "Agora não" porque os testes gastam tokens.

**Se preferir a linha de comando:**

```sh
cd ~/Documents/"Projeto Cloude Code"/willtech-station
./bin/willtech-homologate.sh --plan
./bin/willtech-homologate.sh --run --yes-spend
```

**Confira o registro antes de gastar token:**

```sh
./bin/willtech-verify-agents.sh
```

Cada linha acima é um comando completo. Não cole o `#` nem o texto que vem depois dele —
o script recusa com `argumento desconhecido` porque o `#` chega como argumento.

Se esse comando disser `0/7`, o problema não é o teste — é o registro, e a mensagem indica
se a causa é `CLAUDE_CONFIG_DIR` ou ausência dos arquivos. Gastar token antes disso é desperdício.

Nenhum dos dois depende de `claude` estar no `PATH`: ambos carregam `bin/_willtech_find_claude.sh`,
que localiza o runtime inclusive quando ele só existe como `cli.js` (o modo como o Desktop instala).

O relatório sai em `~/.willtech-lab/<timestamp>/RELATORIO-HOMOLOGACAO.md`, com a tabela por teste,
a evidência de cada um e as métricas de token medidas.

Depois, o passo que só você pode fazer: repetir C, D, E e I **dentro da aba Code**. O modo headless
e a sessão interativa não são a mesma superfície, e eu não vou tratar um como o outro.

## Rodada 2 — registro dos agentes (verificado no runtime real)

A rodada anterior afirmava "7 agentes" contando arquivos `.md` em disco. Isso não é registro.
Nesta rodada o registro foi medido onde ele existe de fato: a lista `agents` do evento `init`
do runtime 2.1.325, lida com `claude -p ... --max-turns 0 --output-format stream-json`, que
encerra antes da chamada ao modelo.

| Cenário | Método | Resultado medido |
|---|---|---|
| HOME com os 7 agentes | evento `init` | `7/7` registrados, `output_tokens=0`, custo `0` |
| HOME sem agentes (controle negativo) | evento `init` | `0/7` — o verificador não aprova por acidente |
| `CLAUDE_CONFIG_DIR` apontando para outro lugar | evento `init` | `0/7` + aviso de que `~/.claude/agents` é ignorado |
| 2ª execução no mesmo HOME | bootstrap `--apply` | `7/7` de novo, nada reescrito — idempotente |

**Causa raiz do "0 agentes"** — três defeitos, todos no ferramental, nenhum no conteúdo dos agentes:

1. **A verificação media disco, não registro.** O relatório imprimia `Agentes WILLTECH (0)` e
   `0 preservados`, e o estado saía `INSTALADO MAS NÃO HOMOLOGADO` lendo a contagem errada
   (`iguais` em vez do total). Agora o estado vem do evento `init`.
2. **`CLAUDE_CONFIG_DIR` substitui `~/.claude` em silêncio.** Com essa variável definida, os
   agentes são copiados para um diretório que o runtime nunca lê. O bootstrap agora avisa em
   voz alta quando ela existe, e o verificador compara `configDirectory` com `~/.claude`.
3. **O shim do `claude` apontava para si mesmo na segunda chamada** —
   `exec "/tmp/willtech-claude-shim/claude"` em laço infinito. Invisível antes porque cada
   script chamava `willtech_use_claude` uma única vez. Corrigido com guarda de identidade e
   wrapper idempotente; testado com 3 chamadas seguidas.

**Novo verificador sem custo:** `bin/willtech-verify-agents.sh` (também `--json`). Sai com 0 se
os 7 estão registrados, 1 se falta algum, 3 se não foi possível verificar. Gasta 0 token.

### Revisão independente — defeitos encontrados e corrigidos

A primeira versão das correções passou por revisão adversarial num bash 3.2.57 compilado do fonte
(o bash do macOS) e foi reprovada em dois pontos. Corrigidos e retestados:

| Defeito | Cenário que quebrava | Correção verificada |
|---|---|---|
| Placar contava `willtech-*` vistos, não os canônicos | 6 canônicos + `willtech-legado` no lugar do revisor imprimia **7/7** e aprovava | agora `6/7 (canônicos)` + `?? willtech-legado (fora dos 7 esperados)`, rc=1 |
| `--home` verificava o HOME do chamador | alvo com 7 verificava `$HOME` vazio → `0/7` falso | verificação roda com `HOME=$TARGET_HOME`; testado nas duas direções |
| Fallback silencioso para contagem de arquivos | sem python3, reportava `VALIDADO — PULAR` por `cmp` de arquivos | sem verificador/python3 agora registra `registro NÃO verificado`, nunca sucesso |
| python3 ausente estourava traceback (rc=127) | macOS sem CLT | guarda antes do uso → rc=3 com mensagem |
| `--expect` aceito e ignorado | `--expect 3` com 7 agentes dava rc=0 | opção removida: lista canônica é fixa, argumento desconhecido → rc=2 |
| `sort -V` (GNU) no `te_cmd` | BSD sort rejeita `-V` → concluía CLI ausente e **reinstalava** o plugin | removido; usa o primeiro `te` do cache |
| `date -Iseconds` (GNU) | BSD date imprime vazio no relatório | formato POSIX `+%Y-%m-%dT%H:%M:%S%z` |
| `find` sem pattern abortava sob `pipefail` | `agents/` vazio → rc=1 e **relatório não escrito** | `{ ... } \|\| true` + diagnóstico explícito de pacote truncado |
| Guarda do shim comparava só diretório | symlink para o shim recriava o laço | compara alvo resolvido; testado, sem laço |
| `PATH` empilhava o shim a cada chamada | 5 chamadas, 5 entradas | deduplicado |
| Interpolação sem escape no wrapper | caminho com `"` gerava script inválido | aspas simples com escaping POSIX |

**O que continua NÃO provado:** delegação real. Sem login (`loggedIn: false`), o evento `init`
sai normal, mas qualquer turno de modelo responde `Not logged in`. Os testes C, D, H e I exigem
uma sessão autenticada na sua máquina — não são homologáveis daqui, e eu não vou declará-los
como tal.

## Tabela de estado atual

| Componente | Versão | Instalado | Ativo | Teste real | Evidência | Pendência |
|---|---|---|---|---|---|---|
| Claude Code | 2.1.325 | sim | sim | NÃO TESTADO | `claude --version`, `auth status` | precisa de sessão logada no Mac |
| Comandante nativo | — | sim | sim | NÃO TESTADO | nenhuma sessão executada aqui | testes A e B no seu Mac |
| willtech-general | 1.0 | sim (lab) | **registrado** | REGISTRO HOMOLOGADO | `init` lista `willtech-general`; 0 token | teste C (delegação) exige login |
| 6 especialistas | 1.0 | sim (lab) | **registrado** | REGISTRO HOMOLOGADO | `init` lista os 6; 0 token | teste D (delegação aninhada) exige login |
| EGM | 0.1.1 | sim (sandbox) | sim | PARCIAL | 7 skills, 0 agents, 7 restrições de invocação | teste E com `/egm:egm-review` |
| TokenEconomizer | 0.1.0 | sim (sandbox) | sim | PARCIAL | hooks executados, protect reaplicado | teste F com sessões dobradas |
| Astro Docs MCP | — | sim | sim | PARCIAL | `✔ Connected` | consulta real de conteúdo |
| Context7 MCP | — | sim | sim | PARCIAL | `✔ Connected` | consulta real de conteúdo |
| Serena | — | não | não | NÃO TESTADO | binário ausente | `uv tool install -p 3.13 serena-agent` |
| Bivia / Laya | — | não | não | NÃO TESTADO | dependem da sua conta e do seu Mac | decisão sua |

Nenhuma linha acima diz "HOMOLOGADO" para delegação, porque delegação não foi observada em sessão
real sua. Instalar, habilitar e funcionar são três coisas diferentes; aqui só afirmei a primeira e,
onde houve execução direta de hook, a segunda.
