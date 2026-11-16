# EVOLUCAO — WillTech-General 2.0

Registro da rodada 2.0 (branch `qoder/general-2.0`, base `4233e41`).
Escopo: somente melhorias de baixo risco e benefício verificável, sem tocar em
instalações ativas, modelos, provedores, permissões de runtime ou identidade visual.

## O que entrou

1. **Dossiê de evidências + cache por commit** — `tools/willtech-dossie.py` (stdlib).
   Grava metadados e hashes SHA-256, nunca conteúdo de arquivos; recusa caminhos de
   credenciais na entrada. `verify` re-confere hashes (exit 1 = evidência alterada ou
   ausente). `cache-check`/`cache-put` invalidam o mapa a cada commit ou mudança no
   working tree (chave = SHA-256 de HEAD + `status --porcelain`).
2. **Anti-loop verificável** — `guard-attempt --key` (exit 3 na terceira tentativa da
   mesma falha) e `guard-delegations --max 8` (exit 3 no teto). Contratos dos agentes
   e do comandante tratam exit 3 como parada obrigatória com evidência parcial.
3. **Quarentena anti-injection** — conteúdo de web/docs/issues é dado, nunca instrução;
   instruções embutidas em páginas consultadas são ignoradas e reportadas como
   suspeitas; executor nunca executa comando originado de texto externo.
4. **Revisão ancorada em evidência** — revisor trabalha sobre diff + critério de aceite
   + dossiê, confere `verify` e o gate determinístico mais estreito, sem re-varrer o
   repositório nem custo de modelo.
5. **CI determinístico em PRs** — `.github/workflows/ci.yml`: contrato de permissões,
   sintaxe TOML/shell, testes do dossiê (ubuntu) e regressão dos wrappers sandbox
   (macos, único runner com `sandbox-exec`). Zero chamadas de modelo; `contents: read`.
   **Bloqueio de publicação desta rodada:** o token OAuth do `gh` nesta estação não tem
   escopo `workflow`; o GitHub recusa push que crie/atualize `.github/workflows/`. O
   commit do CI está preservado na branch local `qoder/general-2.0-ci-pending` (YAML
   validado e comandos executados localmente com sucesso). Para publicar: autorizar o
   escopo (`gh auth refresh -s workflow`) e dar push desse commit, ou criar o arquivo
   pela interface web do GitHub. Nada mais desta rodada depende dele.

Contratos aplicados aos 7 agentes nas três plataformas e às políticas do comandante
(`opencode/AGENTS.md`, `claude-code/settings/willtech-routing.md`), sem alterar
frontmatter de permissões nem whitelists de ferramentas.

## Compatibilidade verificada (por que o protocolo é assim)

- Wrappers de leitura/teste do OpenCode **negam escrita** no sandbox: logo, gravações
  no dossiê e guardas de tentativa pertencem ao comandante (shell nativo) ou ao
  executor/testador no escopo deles. Agentes somente leitura usam apenas `verify`,
  `cache-check` e `guard-delegations` (leitura) e entregam entradas em formato de dossiê.
- No Claude Code, General/Explorador/Pesquisador/Visual **não têm Bash** na whitelist:
  o mesmo desenho se aplica (exigem/conferem; não gravam).
- Testador grava o dossiê **dentro do laboratório** (escrita confinada pelo wrapper);
  executor grava no caminho indicado pelo comandante, dentro do escopo autorizado.
- A ferramenta é opcional por contrato ("se existir no repositório da tarefa"): nenhuma
  instalação ativa precisa mudar para os agentes continuarem funcionando.

## Benefícios demonstrados (evidência, não estimativa)

- `sh tools/test-dossie.sh`: 24 PASS / 0 FAIL — hash impede evidência stale (CHANGED/
  MISSING detectados), recusa de credenciais, dossiê sem conteúdo de arquivo, cache
  HIT/MISS por commit e working tree, guardas com exit 3 no teto.
- `sh opencode/tests/test-wrappers.sh`: 41 PASS / 0 FAIL, incluindo mutação de permissão
  detectada (exit 1) — contrato de permissões intacto após a rodada.
- `python3 opencode/tests/check-permissions.py opencode/agent`: 7/7 contratos.
- Nenhum percentual de economia de tokens é afirmado: o ganho mensurável é a eliminação
  determinística de releituras (cache HIT) e de loops (exit 3), não uma estimativa.

## O que foi adiado (e por quê)

- **Roteamento de modelos por papel**: exigiria alterar modelos/provedores ativos ou
  homologar qualidade por degrau; fora do escopo autorizado desta rodada.
- **Autonomia escalonada com gates humanos nativos** (`question`, `approval_policy`):
  capacidade nativa não homologada nesta máquina; depende de rodada de homologação.
- **Enforcement por hooks/`permissions.deny` (Claude) e `sandbox_mode` por agente
  (Codex)**: mudança profunda de permissão; exige homologação A–I com consentimento de
  gasto antes de publicar.
- **Contenção por worktree / `writable_roots`**: muda o contrato de permissões
  (`opencode_worktree_*` hoje negadas); exige atualização do checker no mesmo commit e
  homologação de maturidade das ferramentas.
- **Lote paralelo com grafo de dependências**: disponibilidade de `batch`/delegação
  paralela por versão não verificada; benefício de latência não medido.
- **Allowlist de rede/fetch por papel**: semântica de permissão de webfetch por agente
  não confirmada; a quarentena contratual + rede negada nos wrappers já cobre o vetor
  principal sem mudança de runtime.
- **Rodada adversarial de C3/C4/C5 e homologação da delegação Claude Code**: pendências
  herdadas, registradas em `opencode/HOMOLOGACAO.md` e `AUDITORIA.md`.

## O que permaneceu intocado

Comandante nativo e hierarquia de três níveis; os sete agentes e seus papéis; contrato
exato de permissões OpenCode e wrappers sandbox; whitelists de ferramentas Claude;
modelos, provedores, Bifrost, MCPs, VPS, SSH e instalações ativas; mascotes, animações,
README (apenas acréscimos de documentação), assinatura de autoria e licença MIT.

## Rodada 2.1 — inteligência seletiva

Estudo dirigido de dois repositórios públicos (apenas README, sem instalar nada):
`microsoft/TokenEconomizer` e `google/elephant-goldfish-model`, ambos Apache-2.0.
Nenhum código foi copiado; apenas ideias adaptadas ao contrato existente, com atribuição.

### Mecanismos estudados e decisão

- **Micro-skills (TokenEconomizer)** → adaptado como **lições verificadas** no dossiê
  (`learn`/`recall`). Diferença de projeto: o TokenEconomizer confirma um fato após três
  sessões e usa um modelo para propor fatos; aqui a evidência é determinística no momento
  do registro (comando + hash SHA-256 da saída real), sem custo de modelo. O fato
  contraditado é descartado lá; aqui a lição antiga é marcada `superseded` e o `recall`
  re-confere hash e HEAD, devolvendo `USABLE`, `REVERIFY` ou `NO_LESSON`.
- **Tool pruning (TokenEconomizer)** → descartado na forma original (desativa ferramentas
  via settings do agente). Adaptado como **seleção econômica por tarefa**: o comandante
  declara na delegação só os recursos necessários; nenhuma desativação automática, nenhuma
  mudança em configurações ou instalações ativas.
- **Failure-loop intervention (TokenEconomizer, juiz LLM com limiar de confiança)** →
  descartado: duplicaria o anti-loop determinístico já implementado no 2.0
  (`guard-attempt`, 2 tentativas, exit 3) e acrescentaria custo de modelo contínuo.
- **Goldfish (elephant-goldfish-model): revisores em contexto fresco, sem a conversa
  anterior** → adaptado como **revisão independente seletiva**: o `willtech-revisor`
  existente é acionado somente em decisão arquitetural crítica, mudança complexa
  (multi-módulo/contrato público) ou alteração de segurança/permissões; uma rodada por
  padrão; segunda rodada apenas após correção de achado bloqueante, sobre o delta
  corrigido. O papel do "elephant" (design com contexto) e a aprovação humana permanecem
  com o comandante e o usuário; nenhum plugin foi instalado.

### O que entrou

- `tools/willtech-dossie.py`: subcomandos `learn` e `recall`; cache seletivo por escopo
  (`cache-put --paths`, `cache-check --paths`), com compatibilidade de leitura do formato
  2.0. Lição exige comando e arquivo de saída reais; caminhos de credencial são recusados;
  a ferramenta grava hash, nunca conteúdo. `verify` já re-confere as saídas das lições.
- `tools/test-dossie.sh`: 21 verificações novas (45 no total; as 24 do 2.0 intactas).
- Contratos (17 arquivos, apenas acréscimos): políticas de lições, cache seletivo,
  revisão seletiva de uma rodada e seleção de ferramentas por tarefa, respeitando a
  compatibilidade real de cada plataforma — wrappers OpenCode somente leitura conferem
  `recall`/`cache-check` e não gravam; no Claude Code o General e o explorador (sem Bash)
  pedem `recall` ao comandante e exigem `learn` de executor/testador; no Codex as mesmas
  regras vivem em `developer_instructions`. Nenhuma permissão, whitelist ou frontmatter
  foi alterada.

### Comparação objetiva 2.0 → 2.1

| Aspecto | 2.0 | 2.1 |
| --- | --- | --- |
| Cache do mapa | chave HEAD+porcelain global; qualquer sujeira → MISS | escopo `--paths`; sujeira fora do escopo → HIT; novo commit → MISS; formato 2.0 ainda aceito |
| Conhecimento de falhas | nenhum registro reutilizável | `learn`/`recall` com evidência verificada; invalidação por hash/HEAD; supersede da lição antiga |
| Revisão independente | recomendada antes de declarar concluída qualquer alteração | seletiva (crítica/arquitetura/complexa/segurança); 1 rodada padrão; 2ª só após correção de bloqueante |
| Ferramentas | "sob demanda" genérico | seleção declarada por tarefa na delegação; sem desativação automática |
| Anti-loop | `guard-attempt` determinístico (2 tentativas, exit 3) | inalterado — não duplicado, sem juiz LLM |
| Testes do dossiê | 24 verificações | 45 verificações (24 antigas + 21 novas), 0 falhas |

Benefício demonstrado por teste, sem percentuais inventados: o caso "cache seletivo HIT
com sujeira fora do escopo" prova reaproveitamento do mapa que no 2.0 seria MISS (nova
varredura paga); `recall USABLE` evita redepurar falha já resolvida com evidência; a
revisão seletiva elimina a delegação do revisor em mudanças triviais/pequenas. Custo da
extensão: stdlib, zero chamadas de modelo, zero rede, zero dependências novas.

### Pendências e bloqueios desta rodada

- Publicação concluída posteriormente: PR #2 merged em `f14ad1c` e PR #3 (2.1) merged em
  `35d8748` (main). O escopo OAuth `workflow` continua ausente: o commit do CI
  (`05a4b9c`, apenas `.github/workflows/ci.yml`) permanece preservado na branch local
  `qoder/general-2.0`, com publicação adiada pelo usuário para etapa futura. A ausência
  do CI não invalida as funcionalidades testadas localmente.

## Rodada 2.2 — inteligência nativa unificada

Objetivo: um único WILLTECH-GENERAL incorporando nativamente os melhores mecanismos de
`microsoft/TokenEconomizer` e `google/elephant-goldfish-model` (Apache-2.0), sem executar
nenhum dos dois ao lado, sem instalar plugins e sem copiar código. Base: main `35d8748`
(2.0 + 2.1 já publicados). branch isolada `qoder/general-2.2`, PR único, sem merge.

### Comparação mecanismo a mecanismo

| Mecanismo original | Já existente (2.0/2.1) | Aperfeiçoamento 2.2 | Evidência de funcionamento | Custo adicional |
| --- | --- | --- | --- | --- |
| Micro-skills: aprender fatos do repositório a partir de sessões (TE) | `learn`/`recall` manual com evidência verificada | `willtech_trace.py` pareia `tool_use`/`tool_result` de transcripts **reais** e extrai candidatas de lição (mesmo comando falhou → depois sucedeu) com evidência em hash e `verified: false` | `tools/test-trace.sh` 10/10; fluxo real: `claude-code/bin/willtech-homologate.sh:188` já executa o trace em transcripts de sessões reais | 0 modelo; stdlib; 1 parse por transcript |
| Fato confirmado por 3 sessões / descartado se contraditado (TE) | supersede + `stale` por HEAD | escopo por projeto (toplevel + remote) nas lições; `recall`/`brief` devolvem REVERIFY fora do projeto de origem | `tools/test-dossie.sh`: "lição de outro projeto = REVERIFY" | 0 |
| Tool pruning: remover ferramentas não usadas via settings (TE) | política de seleção por tarefa (sem desativação) | evidência real de ociosidade: `tools_unused` = declaradas no init − usadas no transcript; o comandante decide, nada é desativado | `test-trace.sh`: `tools_unused == [Edit, NotebookEdit]`, `tool_usage` por ferramenta | 0 |
| Failure-loop intervention com juiz LLM (TE) | `guard-attempt` determinístico (2 tentativas, exit 3) | detecção automática de falha repetida no transcript → `guard_key` determinística pronta para `guard-attempt`; **sem juiz LLM** | `test-trace.sh`: `failure_loops` count=2 com `guard_key`; suíte de guardas intacta | 0 modelo (juiz descartado) |
| Goldfish: revisores em contexto fresco, sem a conversa anterior (EGM) | revisor seletivo, 1 rodada, diff+criterio+dossiê | pack mínimo determinístico: `brief` (cache + lições USABLE + guardas + verify, ≤1500 chars) como única evidência de contexto do revisor | `test-dossie.sh`: brief compõe cache+guardas+verify e respeita teto; contratos revisor 2.2 | 0 modelo extra; menos contexto enviado |
| Elephant: design com contexto do projeto (EGM) | comandante + dossiê | `brief` como pacote de planejamento antes de delegar (planejamento contextual sem releituras) | contratos general/routing 2.2; brief testado | 0 |
| Drift report: docs divergem do código (EGM) | inexistente | `tools/willtech-drift.py`: README↔arquivos, contratos↔subcomandos (citado sem implementação e implementado sem doc), roster↔3 plataformas | `tools/test-drift.sh` 7/7 **com mutações**; drift no repositório real = 0 | 0 modelo; milissegundos |
| Integração operacional (não só prompt) | contratos + scripts manuais | capacidades exercidas no fluxo real de homologação Claude (trace já invocado pelo script); brief/drift/guardas acionáveis pelo comandante/General via wrapper | `willtech-homologate.sh:188`; suítes determinísticas | 0 |

### Iniciativas próprias (não solicitadas no prompt)

- **Redação de segredos no parser**: comandos com `API_KEY=`, `TOKEN=`, `Bearer`, `ghp_`,
  `github_pat_`, `sk-…` são redigidos antes de qualquer saída; conteúdo de `tool_result`
  nunca é exposto (vira hash). Evidência: testes "segredo redigido em comando", "erro vira
  hash, não conteúdo", "tool_result não é exposto". Benefício: a aprendizagem a partir de
  sessões reais não pode vazar credenciais para o dossiê ou relatórios.
- **Gate de drift** (acima): verificação de decisões sem LLM, com testes de mutação.
- **Escopo por projeto nas lições**: evita contaminação de conhecimento entre projetos.
- **Teto de caracteres do `brief`**: economia de contexto garantida por teste, não por promessa.

### Limitações honestas (não anunciadas como funcionais)

- **OpenCode e Codex (rodada 2.2, superado pela 2.2.1)**: nenhum hook de runtime
  verificado naquele momento; brief/drift/guardas eram acionados explicitamente.
  A rodada 2.2.1 verificou os contratos oficiais de hooks das duas plataformas e
  entregou a automação nativa — ver seção abaixo. A homologação em runtime real
  com gasto de modelo continua pendente nas três plataformas.
- **Candidatas de lição não são auto-verificadas**: a detecção é automática; a gravação
  exige confirmação da evidência e `learn` com saída real. Não há "conhecimento automático"
  não verificado.
- A detecção de loop usa `is_error` do `tool_result` (fato observável); não infere
  sucesso/erro por texto.
- CI continua não publicado (escopo `workflow` ausente); commit `05a4b9c` preservado
  localmente. As suítes 2.2 rodam localmente e entrarão no gate quando o workflow for
  publicado.

### Validação consolidada (uma rodada)

- `sh tools/test-dossie.sh`: **51 PASS, 0 FAIL** (45 da 2.1 intactas + 6 novas: brief,
  escopo por projeto, teto de caracteres, dossiê ausente).
- `sh tools/test-trace.sh`: **10 PASS, 0 FAIL** (loops, candidata não verificada, evidência
  hash, ociosas, redação de segredos, não vazamento de conteúdo, transcript ausente).
- `sh tools/test-drift.sh`: **7 PASS, 0 FAIL** (árvore coerente + 4 mutações + erro de uso
  + repositório real sem drift).
- `sh opencode/tests/test-wrappers.sh`: suíte completa passou (mutação + contrato dos 7 agentes).
- `python3 opencode/tests/check-permissions.py opencode/agent`: 7/7 conforme contrato.
- TOML dos 7 agentes Codex: parse OK; `py_compile`/`sh -n`: OK.
- Contratos: apenas acréscimos; nenhuma permissão, whitelist ou frontmatter alterada.
  Instalações ativas, modelos, provedores, Bifrost, VPS e SSH não tocados; mascotes,
  animações, assinatura de autoria e licença MIT preservados.

## Rodada 2.2.1 — automação nativa definitiva (hooks de runtime)

Missão consolidada: transformar a inteligência 2.0–2.2 em funcionalidades
**acionadas pelo runtime**, sem comandos manuais, sem custo de modelo e sem
tocar instalações ativas. Continuou o PR #4 (branch `qoder/general-2.2`),
preservando o histórico.

### O que entrou

- **Núcleo compartilhado** `tools/willtech-auto.py`: recebe o evento do runtime
  (JSON no stdin) e devolve a decisão nativa. Reusa dossiê e trace por
  importação — nenhuma lógica duplicada. Sem `.willtech/enabled` é no-op.
- **Claude Code**: `claude-code/settings/willtech-hooks.json` (forma exec,
  `onFailure: block` no PreToolUse) mesclado no `.claude/settings.json` do
  projeto pelo instalador, com backup.
- **Codex**: `codex/hooks.json` projeto-local (contrato verificado na
  documentação oficial: mesmos eventos/JSON do Claude). Hooks não gerenciados
  exigem revisão e trust do usuário via `/hooks` — consentimento oficial.
- **OpenCode V2**: `opencode/plugins/willtech/index.js` (export default com
  `id` + `setup`, sem dependência externa; V1 não executa em V2 e foi
  descartado). `execute.before` bloqueia via throw; `session.idle` é consultivo
  (pendências de revisão/drift chegam no próximo prompt).
- **Instalador** `tools/willtech-install.sh`: idempotente, projeto-local,
  consentimento inicial (sem `--yes` pergunta), `--platform`, `--disable`,
  `--enable`, `--uninstall` com restauração de backups. Nunca escreve fora do
  repo alvo; hooks pré-existentes do usuário são preservados.
- **Gatilhos automáticos**: SessionStart → prune + brief (uma vez, só se houver
  memória); UserPromptSubmit → brief só em tarefa complexa (≥200 chars);
  PreToolUse → nega a 3ª repetição de comando que já falhou 2× (mesma chave
  determinística do trace); PostToolUseFailure → registra tentativa;
  falhou→sucedeu → candidata `verified=false`; Edit/Write/apply_patch →
  contagem de arquivos; Stop → revisão goldfish (≥3 arquivos ou caminhos de
  segurança) e drift, uma vez por sessão, com proteção de reentrada
  (`stop_hook_active`). Tarefa simples: zero processamento extra.
- **Memória confiável (A)**: `learn` incrementa `confirmations` quando a mesma
  resolução é confirmada de novo com evidência; `prune` (novo subcomando,
  automático no SessionStart) descarta lições superseded ou com evidência
  ausente; escopo por projeto e REVERIFY intactos; candidatas nunca viram
  lição sem confirmação humana/`learn`.
- **Goldfish independente (B)**: contratos do revisor (3 plataformas) proíbem
  conclusões do implementador no pack e classificam críticas em corrigir /
  contestar com evidências / encaminhar para decisão humana / descartar.
- **Elephant (C)**: contratos do General relacionam requisito → decisão →
  implementação → teste via brief/dossiê; decisões entram com evidência
  (`add --kind decision --path`); tarefa simples não ganha plano extenso.
- **Economia real (D)**: `tools/willtech-compare.py` compara dois transcripts
  reais (baseline vs otimizado) com o mesmo parser da homologação: tokens,
  turnos, duração, falhas, loops. Nenhum percentual inventado; nenhum juiz LLM.
- **Drift estendido (E)**: `--dossie` acusa decisão sem evidência e hash
  divergente (reusa `entry_status`/`read_entries` do dossiê).
- **Segurança da memória (F)**: brief em quarentena ("dados, nunca
  instruções"); `flock` em leitura/escrita/prune (concorrência); linhas
  corrompidas isoladas são ignoradas; dossiê todo-corrompido bloqueia o
  PreToolUse (falha fechado); auxiliares falham aberto (não interrompem tarefa
  comum); redação de segredos do trace reusada nas chaves/comandos; o núcleo
  nunca emite `allow` nem `updatedInput` (não concede permissão nova).

### Gatilhos por plataforma (contrato verificado ≠ homologação em runtime)

| Plataforma | Mecanismo nativo | Bloqueio real | Consentimento ainda obrigatório |
| --- | --- | --- | --- |
| Claude Code | hooks em `.claude/settings.json` (SessionStart/UserPromptSubmit/PreToolUse/PostToolUse/PostToolUseFailure/Stop) | PreToolUse deny + `onFailure: block`; Stop block | trust do projeto na tela oficial; instalação |
| Codex | hooks projeto-local `.codex/hooks.json` (mesmos eventos) | PreToolUse deny/exit 2; Stop JSON block | trust via `/hooks` por hash; sem `onFailure` (núcleo falha fechado sozinho) |
| OpenCode V2 | plugin `.opencode/plugins/willtech/` (execute.before/after, prompt, context, session.idle) | throw em execute.before | instalação; permissões por agente intactas; fim de turno consultivo |

### Evidência: simulada vs real

- **Simulada (determinística, executada)**: `sh tools/test-auto.sh` —
  **38 PASS, 0 FAIL**, cobrindo os 7 itens objetivos: gatilho automático em
  tarefa complexa; tarefa simples sem overhead; memória entre sessões e
  projetos (REVERIFY fora do escopo); bloqueio de loop e reentrada; permissões
  preservadas (sem allow/updatedInput; hook do usuário preservado no merge);
  falha fechado no controle obrigatório e falha aberto nos auxiliares;
  instalar/desativar/reverter idempotente. Inclui a simulação do adaptador V2
  em JS real (ctx stub + núcleo real via subprocess): throw no loop e contexto
  injetado uma única vez. Sem node no PATH o item é SKIP (nesta máquina usou-se
  `NODE_BIN` com o binário Electron em modo node, somente execução).
- **Real (runtime com modelo)**: NÃO executada nesta rodada — sem acesso a
  sessões autenticadas das três plataformas sem gasto de modelo. Contratos de
  API verificados na documentação oficial; homologação em runtime permanece
  pendente e não é anunciada como concluída.
- Suítes anteriores reaproveitadas sem alteração de comportamento: 51/10/7
  (dossiê/trace/drift), wrappers e checker 7/7 — reexecutadas uma vez na
  validação consolidada.

### Limitações honestas

- Homologação em runtime real pendente nas 3 plataformas (acima).
- Codex: sem `onFailure: block`; erro/timeout do hook pode deixar a ferramenta
  passar — por isso o núcleo falha fechado por conta própria no PreToolUse.
  Detecção de falha no PostToolUse do Codex usa heurística documentada
  (`exit_code`/prefixo "Exit code"), pois o evento não distingue sucesso/falha.
- OpenCode V2: `session.idle` não bloqueia; revisão/drift no fim de turno são
  consultivos (pendência entregue no próximo prompt). Bloqueio real existe no
  `execute.before` (loop).
- A proteção de segredos não depende só de filtro de texto: caminhos de
  credenciais são recusados na entrada, conteúdo nunca é gravado (só hash), e
  o dossiê corrompido bloqueia o controle em vez de seguir em frente.
- CI continua não publicado (escopo `workflow` ausente); commit `05a4b9c`
  preservado localmente. Fora do escopo desta rodada.

## Rodada 2.2.1-E — estabilização e homologação final (2026-11-16)

Missão única de encerramento sobre a main `6d483cd` (2.2.1 publicada). Sem novas
frentes de desenvolvimento, sem novos agentes, sem gasto de modelo, sem tocar
instalações ativas. Branch `qoder/general-2.2.1-stabilization`, PR único.

### Correções aplicadas (somente lacuna reproduzida)

- **Recuperação da guarda de loop após `learn`**: a mensagem de deny prometia
  liberação ao registrar lição verificada, mas as tentativas da chave
  persistiam — bloqueio permanente mesmo após resolução confirmada (lacuna
  reproduzível). `learn` agora reseta as tentativas da chave (`reset_attempts`),
  via read-modify-write sob `LOCK_EX` no próprio dossiê (`update_locked`,
  também usado pelo `prune`, eliminando a janela de corrida com appends
  concorrentes). Evidência: teste "learn com evidência libera a guarda".
- **Concorrência comprovada**: 8 threads × 25 appends paralelos → 200 entradas,
  zero perda, zero linha corrompida (`flock`). Evidência: teste novo na suíte.

### Reavaliação objetiva de C3/C4/C5 (sem novas sondagens)

- **C3/C4**: observações ao nível do padrão; a semântica do matcher do runtime
  só se confirma em sessão ativa com modelo (orçamento não autorizado).
  Exploração de C3 depende de arquivo plantado por terceiro; em C4 o Executor
  é o agente de escrita autorizada e a barreira principal segue sendo escopo +
  instrução. **Sem alteração nos componentes** — não transformar mitigação
  textual em alegação de isolamento. Classificação: LIMITAÇÃO DO RUNTIME.
- **C5**: Apple Events a apps externos dependem do TCC do macOS; testar
  acionaria aplicativos pessoais da estação (proibido nesta missão).
  Classificação: LIMITAÇÃO DO RUNTIME (mecanismo externo).
- Proteções de memória/hooks/permissões reconfirmadas pelas suítes: dossiê
  corrompido bloqueia o PreToolUse (falha fechado), núcleo nunca emite
  `allow`/`updatedInput`, brief em quarentena, caminhos de credenciais
  recusados, redação de segredos, permissões por agente intactas.

### Evidência de runtimes e versões (sem consumo de modelo)

- **Claude Code CLI 2.1.325** presente (≥ 2.1.295 → `onFailure: block`
  suportado na versão instalada). Cenários reais não executados: o CLI desta
  máquina roteia pelo Claude Code Router (gateway ativo do autor); orçamento
  de modelo não autorizado nesta missão.
- **OpenCode**: CLI ausente do PATH; `OpenCode.app` presente; sonda headless
  de versão inconclusiva (sem saída). Plugin V2 executado em **JS real** com
  ctx stub e núcleo real (simulação de runtime, não homologação).
- **Codex**: CLI ausente. Contrato de hooks verificado na documentação
  oficial; trust via `/hooks` continua obrigatório.
- **CI**: scopes do token gh = `gist, read:org, repo` — **sem `workflow`**;
  publicação exigiria nova permissão. Não tentada (OAuth não reaberto).
  Testes locais permanecem reproduzíveis.
- **Caminhos pessoais**: `git grep '/Users/will'` = 0 ocorrências nos arquivos
  rastreados. Instalador/hooks/plugin usam apenas caminhos relativos,
  `${CLAUDE_PROJECT_DIR}`, `git rev-parse --show-toplevel` e
  `ctx.location.directory` — nenhum caminho pessoal exigido de outros usuários.

### Classificação por capacidade

| Capacidade | Estado | Evidência |
| --- | --- | --- |
| Memória de experiências verificadas (hash, recusa de credencial) | HOMOLOGADA | dossiê 51/51; learn/recall/verify determinísticos |
| Aprendizado entre sessões, confirmação, contradições, invalidação | HOMOLOGADA | supersede→REVERIFY, stale por HEAD, confirmations, prune; auto 40/40 |
| Isolamento por projeto | HOMOLOGADA | lição de outro projeto = REVERIFY (teste) |
| Cache e recuperação contextual (brief) | HOMOLOGADA | cache HIT/MISS seletivo; brief ≤ teto; injeção automática testada |
| Planejamento inteligente com evidências | VALIDADA EM SIMULAÇÃO | brief no prompt complexo; pack de delegação é contrato (runtime pendente) |
| Revisão Goldfish independente + classificação de críticas | VALIDADA EM SIMULAÇÃO | gate Stop exige revisão com pack mínimo; contratos sem conclusões do implementador nas 3 plataformas; comportamento de modelo não executado |
| Prevenção automática de loops + recuperação | HOMOLOGADA (núcleo determinístico) | guard-attempt exit 3; PreToolUse deny na 3ª repetição; learn libera; stop_hook_active sem reentrada |
| Seleção econômica de ferramentas | VALIDADA EM SIMULAÇÃO | tools_unused do trace em transcripts reais (10/10); contrato por tarefa |
| Drift decisões↔docs↔código | HOMOLOGADA | drift 7/7 com mutações (rodada anterior, componente inalterado); --dossie; repo real = 0 |
| Proteção contra injection/vazamento | HOMOLOGADA (determinístico) | quarentena, redação, hash-only, recusa de credencial; armadilhas 46/46 (rodada anterior, wrappers inalterados) |
| Isolamento por agente OpenCode 2.2.6 | HOMOLOGADA (rodada anterior) | matriz + checker 7/7 + mutação; componentes inalterados nesta rodada |
| Isolamento por agente Codex | LIMITAÇÃO DO RUNTIME | TOML não oferece permissão por agente; instrucional |
| Automação nativa (Claude/Codex/OpenCode V2) | VALIDADA EM SIMULAÇÃO | contratos oficiais verificados; auto 40/40; plugin V2 em JS real; registro/disparo/reentrada/desativação exercitados por eventos simulados |
| Homologação em runtime real das 3 plataformas | BLOQUEADA | sem orçamento de modelo autorizado; CLI opencode/codex ausentes; claude via router ativo |
| C3 (prefixo do glob) / C4 (negações do Executor) | LIMITAÇÃO DO RUNTIME | matcher não confirmável sem sessão ativa com modelo |
| C5 (Apple Events / TCC) | LIMITAÇÃO DO RUNTIME | sondagem acionaria apps pessoais (proibida) |
| Instalação limpa, ativação, desativação, rollback | HOMOLOGADA | lab descartável: install 2× idempotente, hook do usuário preservado, --disable no-op, --uninstall restaura backup |
| Comparação com/sem otimizações | HOMOLOGADA (métricas indiretas) | compare sobre fixtures determinísticas: deltas de tokens/turnos/falhas/loops; sem métricas de runtime real, nenhum percentual inventado |
| CI público | BLOQUEADA | token sem escopo workflow; OAuth não reaberto por decisão do autor |

### Testes executados nesta rodada (apenas componentes alterados)

- `sh tools/test-dossie.sh`: **51/51** (learn com reset de tentativas não
  regrediu nenhum teste anterior).
- `sh tools/test-auto.sh`: **40/40** (38 anteriores + 2 novos: recuperação da
  guarda pós-learn; concorrência 8×25 appends). Simulação do plugin V2 em JS
  real incluída (`NODE_BIN` com binário Electron em modo node).
- `python3 tools/willtech-drift.py .`: **0 divergências**.
- `py_compile` / `sh -n`: OK.
- **Não repetidos** (componentes inalterados, aprovados na rodada anterior):
  trace 10/10, suíte drift 7/7, wrappers, checker 7/7, TOML 7/7.

### Limitações que permanecem (motivo objetivo)

- Homologação em runtime real pendente nas 3 plataformas (orçamento/CLI acima).
- Codex: detecção de falha no PostToolUse por heurística documentada; sem
  `onFailure: block` (núcleo falha fechado por conta própria).
- OpenCode V2: fim de turno consultivo (`session.idle` não bloqueia).
- CI não publicado (escopo ausente). C3/C4/C5 conforme acima.
- Nenhuma alegação de estabilidade absoluta ou de eliminação de riscos
  desconhecidos. Instalações ativas, modelos, provedores, Bifrost, VPS, SSH e
  credenciais: não tocados. Autoria, MIT, mascotes e animações: preservados.

## Rodada editorial — compatibilidade de SO e vitrine (2026-11-16)

Revisão documental única, sem alterações em agentes, núcleo ou instalador.

- **Sistemas operacionais (evidência, não anúncio):** macOS validado por
  exercício (suítes determinísticas e smoke tests nesta estação, arm64).
  Linux e Windows via WSL: requisitos objetivos registrados (python3, git,
  shell POSIX; `fcntl` disponível em Linux), **não exercitados** — nenhum
  ambiente Linux/WSL disponível (docker/podman/wsl ausentes). Windows nativo:
  **não suportado** — o dossiê importa `fcntl` (Unix-only,
  `tools/willtech-dossie.py`), scripts `sh` não executam em PowerShell e
  `sandbox-exec` é macOS. Nenhum instalador novo foi implementado.
- **Vitrine:** README separa a matriz de SO das três integrações de IA
  (OpenCode V2, Codex, Claude Code); expressões de máquina pessoal
  ("nesta máquina", "ambiente atual") substituídas por estado neutro com
  remissão a este documento; tom sem alertas alarmistas. Limitações técnicas
  verificáveis permanecem aqui e em INSTALL.md/AUDITORIA.md.
- **Resultados destacados:** smoke tests 3/3 dos adaptadores com código real
  da main, núcleo Python executado e bloqueio anti-loop comprovado **em
  simulação** — explicitamente não homologação em sessão real.
- **Instalação segura:** INSTALL.md declara que os comandos são Unix
  (macOS/Linux/WSL, não PowerShell) e adiciona backup condicional antes da
  cópia dos agentes Claude Code (sobrescrita sem backup corrigida).
- **Preservação:** banner, APNG/GIF, seis mascotes, layout, textos corretos,
  assinaturas de autoria e MIT intactos.

## Rodada compatibilidade Windows — implementação controlada (2026-11-16)

Branch `qoder/windows-compat`, PR único, sem merge automático (homologação
nativa indisponível). Solução incremental, sem reescrita:

- **Locks (bloqueio real, não sentinela):** macOS/Linux preservam
  `fcntl.flock` no próprio dossiê (caminho histórico byte-idêntico). Windows:
  `msvcrt.locking` (LK_NBLCK com espera até 10 s, liberação em `finally`) num
  sidecar `.lock`; o arquivo de dados nunca fica aberto durante `os.replace`
  (o Windows proíbe substituir arquivo aberto). Leituras também excluem no
  Windows (msvcrt não tem lock compartilhado — mais forte, nunca mais fraco).
  `append`, `read_entries`, `update_locked` (learn/prune/reset_attempts)
  cobertos pelo mesmo lock.
- **Caminhos/credenciais:** `is_credential_path` normaliza separadores
  Windows; corrigida falha pré-existente da âncora `.env` (o `/` final
  impedia o casamento — rejeição agora efetiva para `.env` e `.env.*`).
- **Processos:** plugin OpenCode resolve `python3` → `python` → `py -3`
  (primeiro que responder, em cache; `windowsHide`). Núcleo `auto.py` já era
  portável (`os.path`, `sys.executable`) — não alterado.
- **Instalador Windows:** `tools/willtech-install.ps1` projeto-local,
  consentimento, backup `.willtech-bak`, idempotente, `-Disable/-Enable/
  -Uninstall` com restauração; recusa instalar sem Python; hooks gravados com
  o comando Python detectado (formato JSON dos contratos intacto);
  ExecutionPolicy jamais alterada globalmente (flag de processo documentada).
  Lógica de merge/unmerge reutilizada do instalador sh via Python embutido.
- **Segurança preservada:** wrappers `sandbox-exec` (macOS) intactos e NÃO
  instalados no Windows — shell dos agentes segue restrito pelas permissões
  do runtime; nenhuma execução/escrita irrestrita liberada. Hierarquia,
  memória, cache, goldfish, anti-loop, segredos, delegação e as 3 integrações
  inalterados. Autoria/MIT/identidade visual preservados.

**Testes efetivamente executados (uma bateria consolidada, custo zero):**

| Verificação | Resultado |
|---|---|
| `tools/test-compat.py` (nova, cross-platform): import do núcleo, 8 processos × 25 appends + prune concorrente (200/200, 0 corrupção), recuperação anti-loop pós-learn, dossiê pré-2.2 legível, credenciais com `\`, deny da 3ª tentativa nas 3 plataformas, Stop→goldfish, falha fechado com dossiê corrompido | 22/22 PASS (POSIX) |
| Regressão `tools/test-dossie.sh` | 51/51 |
| Regressão `tools/test-auto.sh` (incl. plugin JS real via Electron-as-node com a nova resolução Python) | 40/40 |
| Regressão `tools/test-drift.sh` + gate `willtech-drift.py` | 7/7 · 0 divergências |
| Regressão `opencode/tests/test-wrappers.sh` (sandbox macOS intacto) | todos PASS |
| Lógica do instalador PS1 simulada deterministicamente: sintaxe dos blocos Python, adaptação `py -3`, preservação de hooks do usuário, backup, idempotência, restauração, caminho `C:/Users/will/Projeto Ação` (espaço + Unicode) | PASS (simulação) |

**Classificação honesta:** macOS = VALIDADO POR REGRESSÃO (exercitado nesta
estação). Windows nativo = **PENDENTE DE HOMOLOGAÇÃO NATIVA** — sem runner
Windows acessível (0 workflows no repo; token sem escopo `workflow`, não
solicitado; sem máquina Windows, sem pwsh/wine nesta estação). A execução
real do PS1, dos locks `msvcrt` e dos hooks em Windows não foi exercitada;
nada foi anunciado como aprovado nativamente. Linux/WSL = não exercitados
(sem ambiente), requisitos inalterados. O PR permanece aberto até que um
runner Windows real execute `python3 tools/test-compat.py` e o instalador.

## Rodada homologação Windows nativa — windows-latest real (2026-11-16)

Runner real obtido sem novo OAuth: workflow `.github/workflows/windows-compat.yml
criado na `main` pela interface web autenticada (commits `e83a7b0`, `392b875`)
e acionado por `gh api` (dispatch exige apenas escopo `repo`). Código do PR #6
testado por checkout do input `ref=qoder/windows-compat`.

**Comprovado em Windows nativo (Python 3.12.10, os.name == 'nt', runs
43884119785 → 43885449180, passos estáveis em todas as execuções):**

- `tools/test-compat.py` **22/22 PASS nativo**: lock real `msvcrt.locking`
  com 8 processos × 25 appends + prune concorrente (200/200, 0 corrupção),
  recuperação anti-loop pós-learn, dossiê pré-2.2 legível, credenciais com
  separadores Windows, deny da 3ª tentativa nas 3 plataformas, Stop→goldfish,
  falha fechado com dossiê corrompido.
- Rejeição real de `.env` via CLI em Windows (exit 2, mensagem de recusa).
- Regressão Unix do head permanece verde (51/40/7/wrappers/22 POSIX).

**Falhas reais corrigidas durante a homologação (cada uma com evidência de log):**

1. Harness: `pwsh` propaga `$LASTEXITCODE` residual da negação esperada de
   `.env` → `exit 0` explícito no workflow (produto estava correto).
2. Produto: PS 5.1 corrompe aspas embutidas em `-c` nativo → código Python
   passa por stdin (`python - args`) — commit `9a6a596`.
3. Produto: `[Encoding]::UTF8` do PS 5.1 emite BOM no stdin →
   `UTF8Encoding($false)` + leitura de configs existentes como `utf-8-sig`
   (arquivos reais do Windows têm BOM) — commit `355934e`.

**Bloqueio concreto remanescente (orçamento de tentativas esgotado):**
o ciclo completo do `willtech-install.ps1` ainda falha no runner: PS 5.1
**descarta argumentos de string vazia** em chamadas nativas — o prefixo do
launcher (vazio para `python`, `-3` para `py`) some do argv e o programa de
merge recebe 4 valores em vez de 5 (`ValueError: not enough values to unpack`,
run 43885449180). Correção exata para a próxima rodada autorizada: enviar o
prefixo com sentinela não vazia (ex.: `@none`) ou junto do stdin, filtrando no
lado Python. Nada foi mergeado; PR #6 permanece ABERTO. O núcleo Windows está
homologado nativamente; o instalador PowerShell não.

<!-- WillTech-General / WILLTECH-BH © 2026 · autoria: github.com/hebwil -->