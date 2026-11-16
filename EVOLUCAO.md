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
- **Caminhos pessoais**: varredura `git grep` pelo caminho absoluto do usuário
  da estação = 0 ocorrências nos arquivos
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
| Lógica do instalador PS1 simulada deterministicamente: sintaxe dos blocos Python, adaptação `py -3`, preservação de hooks do usuário, backup, idempotência, restauração, caminho com espaço + Unicode | PASS (simulação) |

**Classificação honesta:** macOS = VALIDADO POR REGRESSÃO (exercitado nesta
estação). Windows nativo = **PENDENTE DE HOMOLOGAÇÃO NATIVA** — sem runner
Windows acessível (0 workflows no repo; token sem escopo `workflow`, não
solicitado; sem máquina Windows, sem pwsh/wine nesta estação). A execução
real do PS1, dos locks `msvcrt` e dos hooks em Windows não foi exercitada;
nada foi anunciado como aprovado nativamente. Linux/WSL = não exercitados
(sem ambiente), requisitos inalterados. O PR permanece aberto até que um
runner Windows real execute `python3 tools/test-compat.py` e o instalador.

## Rodada homologação Windows nativa — windows-latest real (2026-11-16)

Runner real obtido sem novo OAuth: workflow `.github/workflows/windows-compat.yml`
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

**Bloqueio ao encerrar aquela rodada (resolvido na rodada final abaixo):**
o ciclo completo do `willtech-install.ps1` falhava no runner: PS 5.1
**descarta argumentos de string vazia** em chamadas nativas — o prefixo do
launcher (vazio para `python`, `-3` para `py`) sumia do argv e o programa de
merge recebia 4 valores em vez de 5 (`ValueError: not enough values to unpack`,
run 43885449180). O orçamento de tentativas daquela missão foi encerrado;
o PR #6 ficou aberto, com núcleo homologado e instalador ainda bloqueado.

## Rodada final PR #6 — núcleo e instalador homologados (2026-11-16)

[Workflow Windows nativo 43892063828: SUCCESS](https://github.com/hebwil/willtech-general/actions/runs/43892063828).
Checkout exato do produto: `c70e5e80f8183cdb06dea6febee73249e5d9b98f`.
Runner `windows-latest`, Python 3.12.10 (`os.name == 'nt'`) e Windows
PowerShell 5.1 real; nenhum modelo de IA chamado.

- **Correção do bloqueio final (`7129daf`):** transporte do prefixo vazio
  usando `@none`, convertido de volta para vazio no Python; os cinco
  argumentos chegam intactos. Contratos, parâmetros, código via stdin,
  UTF-8 sem BOM e leitura `utf-8-sig` preservados.
- **Único defeito adicional comprovado (`43891790256`):** reinstalação criava
  backup dos hooks Codex que o próprio instalador havia criado; uninstall
  restaurava esse backup indevidamente. Correção localizada (`c70e5e8`):
  marcador `.willtech-created` apenas para arquivos criados pelo instalador,
  impedindo backups indevidos; marcador removido no uninstall.
- **Workflow existente reutilizado (`548a615`):** verificações acrescentadas
  apenas para caminho com espaços e Unicode (`wt lab Ação`), sentinela sem
  vazamento nos hooks, integridade do plugin/núcleo e restauração integral
  das configurações. Permissões `contents: read` e timeout mantidos.
- **PASS nativo:** `tools/test-compat.py` 22/22, lock `msvcrt` com 8 processos
  × 25 appends + prune concorrente, anti-loop, dossiê legado, hooks das três
  plataformas, fail-closed e recusa real de `.env` via CLI (exit 2).
- **Ciclo PowerShell completo PASS:** instalação, backup, merge preservando
  hooks e dados do usuário, idempotência (1 → 1), disable, enable e uninstall;
  configuração original restaurada integralmente, Codex/plugin criados
  removidos, Unicode nos caminhos preservado e hashes sem alterações.
- **Economia:** uma execução de produto e a única reexecução autorizada
  após o defeito adicional. Um acionamento com referência incorreta foi
  cancelado no checkout, antes de qualquer teste de produto.
- **Preservação:** regressão macOS previamente aprovada reutilizada; código
  Unix, instalador sh, núcleo auto, General, especialistas, contratos,
  assets, assinaturas e MIT sem alterações nesta rodada. Linux/WSL não
  exercitados; nenhum suporte adicional de sandbox foi anunciado.

**Resultado:** núcleo Windows e instalador PowerShell **HOMOLOGADOS NATIVAMENTE**.
Sem bloqueio remanescente para publicar o PR #6. Homologação de runtimes de
IA em Windows não faz parte deste workflow; os três incrementos futuros
não foram iniciados.

## Consolidação distribuível — ativação, reversão e delegação (2026-11-16)

Base publicada: `38ce81b5fb9f173a4823c33300c37edd6559d010` (PR #6 incorporado).
Escopo exclusivo do repositório; nenhuma instalação pessoal acessada nesta
consolidação e nenhuma nova chamada de modelo. Evidências de IA abaixo são
reaproveitadas de execuções anteriores, não repetidas nesta rodada.

### Ativação e reversão

- **Já existente:** instaladores oficiais sh/PowerShell, alvo projeto-local,
  consentimento inicial, seleção de plataforma e disable/enable/uninstall.
  Não foi criado outro instalador. INSTALL.md esclarece o uso de `--repo`/`-Repo`
  e os quatro auxiliares necessários no alvo, sem caminhos pessoais.
- **Lacunas corrigidas:** o instalador Unix ainda criava backup de arquivos que
  ele próprio havia criado na reinstalação; ambos removiam hooks por substring
  e podiam apagar JSON com dados de terceiros quando não restassem hooks.
  O plugin era sobrescrito/removido sem backup; diretórios preexistentes vazios
  também podiam ser removidos.
- **Reversão por posse:** `.willtech-managed.json` registra somente os handlers
  adicionados ou o hash do plugin; `.willtech-created` marca arquivos criados;
  `.willtech-bak` conserva o arquivo original byte a byte. Reinstalação remove
  somente handlers registrados, não ocorrências de texto em hooks de terceiros.
  Uninstall restaura o original intacto quando não houve alteração posterior;
  caso contrário, retira só os handlers registrados e preserva os outros dados.
  Configuração alterada conserva o backup quando restaurá-lo apagaria mudanças.
  Plugin modificado pelo usuário e seu backup são preservados, com aviso.
  Backups/marcadores sem registro não são adotados automaticamente: a instalação
  para nesse componente e exige revisão manual, sem apagá-los.
- **Preservação:** arquivos sem registro de posse não são removidos. Diretórios
  não são apagados, nem `tools/`, `claude-code/` ou `.willtech/`; auxiliares,
  dossiê/cache e arquivos de terceiros permanecem. Symlinks no estado de
  instalação e componentes fora do alvo são recusados. O marcador de ativação
  é gravado somente após os componentes, nunca antes de uma instalação falha.
- **Validação direcionada:** uma execução de `python3 tools/test-install.py`:
  **16 testes aprovados, zero falhas, 2,075 s**. Exercita somente os instaladores
  modificados e a integridade documental/visual. O shell é
  executado no código real do repositório; os blocos Python embutidos do PS1
  são executados deterministicamente, preservando `@none`, `py -3` e Unicode.
  Isso não é uma nova homologação nativa do PowerShell. O workflow Windows
  histórico `43892063828` continua comprovando a versão `c70e5e8`; núcleo,
  locks e plugin não foram modificados nem retestados nesta consolidação.

### Delegação real — resultado parcial, não homologação completa

OpenCode Desktop 2.2.6; modelo registrado nas sessões:
`willtech-bifrost2/deepseek-v4.1-1017`. O modelo interno upstream e o custo de
faturamento do provedor não foram verificados; `cost: 0` do runtime não prova
execução gratuita.

- No smoke anterior, comandante → General aconteceu, mas o encaminhamento
  dizia "você mesmo faz a leitura"; o General executou três `read`, sem chamar
  especialista. Esse registro não comprova bloqueio do mecanismo de delegação.
- Profundidade efetiva 2 permite Comandante → General → Explorador. O General
  tinha permissão de `subagent`; Explorador estava registrado e invocável.
  Não houve bloqueio objetivo de configuração que justificasse alterá-la.
- Uma tentativa de cliente externo falhou antes de criar sessão por exigir
  autenticação: 0,154 s, zero tokens de modelo. Não foi falha dos agentes ou
  do DeepSeek. O acesso foi resolvido depois pela descoberta autenticada do
  cliente oficial do serviço existente, sem expor senha nem mudar configuração.

| Sessão real | Evento comprovado | Resultado |
|---|---|---|
| Comandante `ses_e1afc2e47ffel1fNHvegYZkXDV` | `subagent` criou o General como filho | Interrompido no timeout |
| General `ses_e1afbb7f7ffeO4TuZF2bQLiON6` | `subagent` para `willtech-explorador`, filho real, chamada concluída | Recebeu retorno de erro; resposta final ao comandante interrompida |
| Explorador `ses_e1afb91f6ffepg1nGR7N5W3K1j` | Uma chamada `read` no arquivo pequeno autorizado | `permission.rejected`; devolveu a impossibilidade, sem inventar função |

Erro real: `This non-interactive run cannot ask the user for permission, so the request was rejected. Continue without this action.` O estado `succeeded`
da sessão do Explorador significa que devolveu a resposta de erro, **não**
que conseguiu ler o arquivo. Nenhum nome de função foi obtido.

**Resultado do processo: TIMEOUT.** Uma execução; SIGINT aos 60,005 s;
encerramento aos 60,079 s, exit 130. Comandante e General confirmados
`interrupted`; arquivo de teste intacto até a remoção do laboratório. Tokens registrados nas três
sessões: entrada 44.056, saída 699, raciocínio 251, cache lido 256, cache escrito 0;
contabilização possivelmente parcial pelo cancelamento.

A comunicação General → Explorador → General está comprovada com retorno de
erro. A leitura e a consolidação completa da tarefa **não estão homologadas**.
A correção distribuível necessária é documental: usar workspace autorizado e
aprovação interativa oficial quando exigida, sem flexibilizar permissões ou
repetir testes pagos. Contratos dos sete agentes, hierarquia, hooks/plugin,
memória, anti-loop e revisão independente permanecem intactos.

Banner, sete mascotes, APNG/GIF/estáticos, layout premium, autoria WILLTECH-BH,
MIT e créditos preservados.

## Painel visual experimental — OpenCode Desktop (2026-11-16)

Base publicada: `57f8bb458218e1dfb844722fc19b9abba1d94add`. Branch isolada:
`qoder/agent-activity-panel`. Nenhum subagente, modelo, instalação pessoal,
configuração de provedor ou permissão foi acionado/modificado nesta rodada.

### Implementação e contrato oficial

- SDK GUI confirmado na fonte da release oficial OpenCode **2.2.6**, incluindo
  `Plugin.define`, `Panel`, `Command`, `Style`, `createKeyed` e `gui-experimental`.
- Contribuição em `opencode/plugins/willtech/visual/`, **GUI-only**, opt-in e
  limitada à versão/superfície verificadas. Nenhum export de servidor: carregar
  o pacote não executa nem duplica o plugin de automação.
- Estado proveniente de `Session.Info.agent`, família de sessões sincronizada,
  execução nativa `session.execution.*` e pedidos de permissão. Marcadores
  otimistas, títulos e texto de respostas não simulam trabalho.
- Oito imagens originais embutidas byte a byte: sete WebP e APNG do General.
  Bundle reproduzível de **830948 bytes**, sem build dependencies, polling,
  chamadas de ferramenta/modelo, escrita, WebGL ou nova delegação.
- Movimento somente durante trabalho observado, com pausa local, suspensão
  quando o painel fica oculto e `prefers-reduced-motion`. Desativação pelo
  ciclo de vida oficial retira recursos sem interferir na automação.

### Validação consolidada e bloqueios

- **4/4 testes determinísticos** de distribuição, em 0,040 s: build idêntico,
  oito imagens originais, pacote sem servidor/dependências e preservação de
  núcleo, instaladores, agentes, hooks, assets, HTML premium, MIT e créditos.
- `git diff --check`: aprovado. Não foram repetidas auditorias/suítes anteriores.
- Bancada Browser Use com bundle real e **host/eventos simulados** percorreu os
  estados dos sete agentes, pausa, ocultação, permissão, fim/erro/interrupção,
  desconexão, troca de sessão e servidor incompatível até a montagem final.
  Inspeção estrutural encontrou sete imagens completas com dimensões válidas.
  **Não há resultado PASS consolidado da bancada:** a chamada atingiu o timeout
  do navegador de 15 s enquanto aguardava `image.decode()` do APNG.
- Screenshot: **BLOQUEADO** por `NATIVE_BROWSER_VIEWPORT_UNAVAILABLE`, com
  `visible=false` e `visibilityState=hidden`. A seleção oficial com
  `bringToFront=true` não tornou a superfície visível. Nenhuma imagem de uma
  interface fictícia foi criada para substituir essa evidência.
- Helper da bancada passou a aguardar eventos de carga com timeout e impedir
  execução concorrente. **Correção não revalidada**, para não repetir a rodada.
- Carregamento no OpenCode Desktop, evento de agente real, término/erro real e
  não regressão gráfica/orquestração: **NÃO TESTADOS**. Código preservado e
  simulação não equivalem à homologação nativa. O escopo não autoriza acessar
  instalações pessoais nem iniciar IA para gerar essa demonstração.

O único PR desta rodada deve permanecer **draft, sem merge**. A autorização de
merge é condicional aos testes necessários; não foi satisfeita pela simulação.
A contribuição permanece experimental, desativada por padrão e não anunciada
como plataforma efetivamente homologada.

### Codex e Claude Code

Codex documenta plugins/MCP e recursos UI em hosts MCP Apps, particularmente
ChatGPT, mas as fontes consultadas não comprovam painel nativo passivo Codex
com assinatura dos eventos dos agentes. Nada gráfico foi implementado no Codex.

Claude Code documenta agora **mods** com panes, `ui.render` e `$.agent.list()`
em versões mais novas (referência 2.1.290+), e diferentes elementos por
superfície. `Image` consta para terminal, não Desktop/VS Code. Não se afirma
que Claude Code não possui API de extensão visual; a animação dos mascotes
originais não foi homologada e nenhuma GUI Claude Code é distribuída.
Fontes oficiais e configuração opt-in estão em INSTALL.md.

## Rodada de correção do painel — deduplicação e bancada consolidada (2026-11-16)

- Defeito real corrigido em `gui-source.cjs`: a guarda de eventos usava apenas
  `at > event.created`, então um evento idêntico (mesmo tipo e mesmo timestamp)
  produzia uma segunda revisão. A guarda agora também compara o estado quando
  os timestamps coincidem; eventos distintos no mesmo milissegundo e eventos
  posteriores mais novos continuam aceitos. Bundle regerado por `build-gui.py`.
- Novo teste determinístico `tools/test-gui-events.cjs` (Node, SDK simulado):
  reproduzia a duplicação (2 revisões para 1 evento) e agora passa nas duas
  formas, `gui-source.cjs` e `gui-experimental.cjs`, cobrindo também evento
  terminal distinto no mesmo milissegundo, evento antigo, sessão fora da
  família e limpeza das quatro inscrições no cleanup.
- Bancada Browser Use (`tools/test-gui.html`, bundle real, host simulado):
  **PASS consolidado, 42/42 verificações**, incluindo os sete mascotes originais
  decodificados no navegador, estados dos sete agentes, pausa, ocultação,
  permissão, erro, interrupção, desconexão/reconexão, troca de sessão, servidor
  incompatível, unmount e CSS com `prefers-reduced-motion`. O timeout de 15 s
  da chamada ocorreu de novo, mas o resultado foi lido do estado da página
  após a conclusão; screenshot real da bancada capturado com os sete cards.
  Isto continua sendo **laboratório simulado, não homologação nativa**.
- Regressão proporcional: `tools/test-gui.py` 4/4 (build reprodutível, bytes
  originais dos assets, pacote GUI-only, núcleo/instaladores intactos vs
  `57f8bb4`) e `tools/test-drift.sh` 7/7.
- Homologação no OpenCode Desktop real permanece **NÃO TESTADA**; nenhuma
  instalação pessoal foi acessada e nenhum aplicativo gráfico foi aberto.

## Rodada inteligência 2.3 — Elephant/Goldfish, RepoMap e supervisor (2026-11-16)

Três melhorias incrementais sobre o núcleo existente, em branch própria
(`qoder/intelligence-orchestration`, base `57f8bb4`), separadas do PR #8.
Nenhum agente novo, nenhum framework, nenhuma chamada de modelo extra.

### 1. Elephant/Goldfish determinístico (commit 9a6ed7b)
- `willtech-dossie.py plan`: DIRECT para tarefa simples (sem etapas extras,
  sem gravação); PLAN compacto (requisitos, causa-raiz, dependências, riscos,
  testes + zoom-out + readiness) para complexa (≥3 caminhos, ≥200 chars ou
  palavras-chave); PLAN critical com REVIEW obrigatória para caminhos de
  segurança. `review-pack`: pack independente (diff + aceite + evidências
  verificadas, sem conclusões do executor), uma rodada por diff (segunda só
  com --new-finding, senão exit 3). `resolve`: fix/contest exigem evidência;
  escalate/discard registrados. `catalyst`: uma alternativa após impasse
  demonstrado (≥2 falhas); segunda exploração = exit 3.
- `willtech-auto.py` reusa as constantes compartilhadas e o Stop aponta para
  o pack independente. Testes: `tools/test-plan.sh` 21/21.

### 2. RepoMap incremental compartilhado (commit 5a86a28)
- `tools/willtech-repomap.py`: índice de símbolos/assinaturas/dependências
  (Python ast; JS/TS/sh regex), nunca conteúdo nem credenciais; incremental
  por hash (reparse só do que mudou), renames reaproveitam símbolos, remoções
  saem; bug real corrigido: arquivos rastreados mas apagados do worktree
  quebravam a detecção de rename (filtro de existência em disco).
- `brief` entrega pacote pequeno em quarentena ao especialista; `query`
  (--symbol/--path/--refs) devolve trechos lidos da fonte ao vivo e
  revalidados por hash (STALE recusado). Isolamento por projeto e tetos de
  arquivos/símbolos/bytes/resposta reusam o dossiê.
- Medição real (fixture de 10 arquivos): leitura integral 380 bytes (~95
  tokens estimados) vs brief 256 bytes (~64); parses primeiro=10,
  incremental=0; tempos equivalentes no fixture pequeno (git domina).
  Nenhum percentual anunciado sem medição. Testes: `tools/test-repomap.py` 10/10.

### 3. Supervisor de delegações (commit c46442a)
- `tools/willtech-supervisor.py`: start/finish/tick/cancel/retry/report/
  capabilities; estados pending/running/completed/failed/timed_out/cancelled;
  lock OS no sidecar (msvcrt no Windows, flock POSIX) bloqueia escritas
  concorrentes na mesma tarefa; recursão, duplicação e teto por tarefa
  bloqueados; retry único com --reconciled preserva registro/trabalho parcial.
- Honestidade: timed_out = espera esgotada, nunca interrupção confirmada;
  cancel sem --confirmed = cancel_requested + limitação documentada
  (CAPABILITIES: nenhum runtime oferece cancelamento real confirmado).
- Integração fail-open: SessionStart do `willtech-auto.py` reporta SLOW/
  TIMED_OUT junto ao brief; sem `.willtech/enabled` nada roda. Testes:
  `tools/test-supervisor.py` 10/10, incluindo concorrência real entre
  processos e integração com o hook.

### Compatibilidade e preservação
- Detecção de capacidades limitada ao ponto de benefício comprovado
  (cancelamento); limitações por runtime documentadas nos contratos 2.3.x
  das três plataformas. Adaptadores, hooks, instaladores, memória, anti-loop,
  roster dos sete agentes e painel visual do PR #8 intactos (branch separada).
- Regressão: test-dossie 51/51, test-auto 39/39, test-drift 7/7, drift 0
  divergências; suítes Windows/instalação/trace reexecutadas na consolidação.
- Homologação em runtime real (com gasto de modelo) permanece PENDENTE e não
  é anunciada como concluída; nada publicado remotamente.

## Rodada smoke final (homologação de laboratório)

- Novo harness `tools/test-smoke.cjs` (Node): extrai o literal `ASSETS` do bundle
  real e confere por SHA-256 as 8 chaves contra os bytes dos arquivos originais
  (`willtech-general-static.webp`, seis `willtech-<nome>.webp`,
  `willtech-general-animated.apng`); conta 18 quadros fcTL e asserta ausência de
  `fetch`/`XMLHttpRequest`/`WebSocket`/`EventSource` no bundle. PASS.
- Novo harness de navegador `tools/test-smoke.html` + `tools/test-smoke.js`:
  bundle real + host reativo do `test-gui.js` + eventos determinísticos.
  **PASS 64/64 em três execuções consecutivas**: sete personagens carregados;
  associação agente→imagem por hash da data URL; estados aguardando/executando/
  concluído/erro/interrompido dos sete; General isolado dos eventos dos
  especialistas e reagindo ao próprio; pausa/retomada com fallback estático;
  deduplicação provada por MutationObserver (evento válido atualiza, idêntico
  não duplica, distinto no mesmo ms é aceito); unmount remove listeners, congela
  animação e ignora eventos posteriores. **PASS 3/3 reduced-motion** (stub de
  `matchMedia` com `matches=true`: General working usa WebP, motion off, listener
  de media removido no cleanup).
- Avanço de quadros do APNG: o navegador automatizado suprime o playback ao vivo
  de imagens animadas (canvas estático mesmo com rAF ativo e página visível);
  a prova determinística usa WebCodecs `ImageDecoder` sobre o APNG em uso:
  18 quadros, quadro 0 ≠ quadro 9 (214 pixels amostrados diferem). O resultado
  registra `livePaintingAdvanced=false` e a nota de limitação de ambiente —
  sem aprovação inventada de playback ao vivo.
- Dois defeitos do próprio harness corrigidos na causa: `ImageDecoder.tracks.
  selectedTrack` só existe após o primeiro decode; e `MutationObserver.takeRecords()`
  após `await` devolve sempre 0 porque a entrega ao callback esvazia a fila —
  a contagem agora ocorre no callback (isto também eliminou uma aprovação
  trivialmente falsa do check pós-unmount).
- `tools/test-gui.js` ganhou apenas duas linhas de exposição (`__under`,
  `__dispose`) para o smoke; bancada reexecutada: **42/42 PASS**.
- Regressão proporcional reexecutada: `test-gui.py` 4/4, `test-gui-events.cjs`
  PASS nas duas formas, drift do branch 0 divergências. Regressão consolidada
  do branch de inteligência (sem alterações novas): dossiê 51/51, auto 39/39,
  drift 7/7, plan 21/21, trace 10/10, repomap 10/10, supervisor 10/10,
  compat 22/22, install 16/16.
- Evidências em `tools/smoke-evidence/`: `full-results.json`,
  `reduced-results.json`, `node-assets.json`/`.log`, `bench-results.json`,
  `network-evidence.json` (somente `file://` e `data:`, zero http/https, zero
  IA) e screenshots `smoke-full-pass.png`, `smoke-states.png` (fixture manual
  com os sete estados), `smoke-reduced-motion.png`.
- Continua **laboratório simulado, não homologação nativa**; nenhum aplicativo
  Desktop aberto, nenhuma instalação pessoal tocada, nenhum push/publicação.

## Rodada de publicação final no GitHub (2026-11-16)

**Autorização expressa do proprietário** para publicar as alterações homologadas
em laboratório. Executada com mecanismos normais do GitHub, sem force push e
sem reescrita de histórico publicado.

- **PR #8 — painel visual experimental** (`qoder/agent-activity-panel`):
  atualizado com os commits `b2e8939` (correção de causa da deduplicação) e
  `9ac55f1` (smoke headless final + evidências); corpo documentando mascotes,
  animações, estados, smoke aprovado e limitações (integração nativa no
  OpenCode Desktop **NÃO EXECUTADA**; contribuição experimental). Retirado de
  draft e **merged na `main`** — merge commit
  `01e4ec693c67c44acca48dc2cf73333dd67c0bce`.
- **PR #9 — inteligência 2.3** (`qoder/intelligence-orchestration`), novo PR
  separado do #8: Elephant/Goldfish + revisão independente, RepoMap incremental
  (medição real: 380 B/~95 tokens de leitura integral vs brief 256 B/~64;
  parses 10 → 0) e supervisor de delegações. Commits `9a6ed7b`, `5a86a28`,
  `c46442a`, `68b6e96` + merge `f38914b` com `origin/main` (único conflito em
  EVOLUCAO.md, resolvido em ordem cronológica; README combinado). Gate de drift
  reexecutado após a resolução: **0 divergências, 7/7 PASS**. Contratos
  2.3/2.3.1/2.3.2 das três plataformas preservados. **Merged na `main`** —
  merge commit `edc99506f993df09bb2b8af7ff743570c8098124`.
- **README premium atualizado na `main`** para o estado real: versão 2.3,
  seção objetiva das três melhorias com a medição do RepoMap, painel
  experimental com os cinco estados e o smoke 64/64 (×3) + 3/3 reduced-motion,
  evidências em `tools/smoke-evidence/`, suítes de regressão com contagens
  reais, compatibilidade de SO/plataformas e limitações honestas. Design,
  banner, mascotes, animações e autoria WILLTECH-BH/MIT preservados.
- **Sanitização forward** deste registro: duas linhas históricas que citavam
  caminhos absolutos pessoais foram reescritas sem o caminho (sem reescrever
  histórico publicado). Varredura final dos arquivos rastreados: 0 ocorrências
  de caminhos pessoais; evidências publicadas contêm apenas hashes, contagens
  e URLs `file://`/`data:` relativas à bancada.
- Nenhuma instalação pessoal (OpenCode/Codex/Claude Code), configuração global,
  VPS ou serviço foi alterado; OpenCode Desktop/Electron não foi aberto; os
  commits das duas branches não foram misturados.
- Simulação de laboratório continua **não anunciada como homologação nativa**:
  painel no Desktop, automação com modelo real e tarefa DeepSeek permanecem
  pendentes, classificados como tal no README e neste registro.

## Rodada 2.3 visual — sete mascotes reagindo à atividade real (2026-11-16)

Missão exclusivamente visual sobre a main `fbb2427`. Investigação obrigatória
contra as documentações oficiais vigentes antes de qualquer código; um PR por
plataforma; nada do núcleo de inteligência, instaladores, hooks de automação,
README premium e identidade visual foi tocado.

### OpenCode — causa corrigida, painel existente concluído (PR #10, `36f2666`, merge `fa7c1f4`)
- **Causa comprovada do painel invisível:** o plugin travava o registro do
  painel a um pin exato de versão (`ctx.app.version !== "2.2.6"`); o Desktop
  atual (2.3.0) falhava na comparação e o painel nunca era registrado.
  Correção mínima: piso `versionAtLeast(…, "2.2.6")`, preservando opt-in
  (`enabled === true`), trava de plataforma desktop e guardas de runtime.
- **Validação em laboratório (versão atual 2.3.0):** `tools/test-gui.py` 4/4,
  `tools/test-gui.js` 44/44, `tools/test-smoke.js` 64/64 + reduced-motion 3/3;
  SHA-256 dos 8 data URLs do bundle = mascotes originais; captura
  `tools/smoke-evidence/mission5-gui-v230.png` rotulada como laboratório.
- **Limitação registrada:** homologação no OpenCode Desktop nativo NÃO
  realizada (sem instância descartável; instalação pessoal é proibida).

### Claude Code — Mod oficial criado (PR #11, `158b78d`, merge `ffa8ccb`)
- Mods são realmente suportados (CLI local v2.1.325). Mod `willtech-visual`
  completo: `plugin.json` + `hooks.json` + ESM `register.js`; sete mascotes em
  dois locais oficiais de render (`Pane` desktop com SVG+SMIL; terminal com
  `Image` chavada + `$.ui.blit` a 240 ms); estados por eventos reais
  (`agent.spawn`, `turn.*`, `tool.check`, `session.*`); observação pura com
  fail-open (`catch → next(e)`); núcleo `activity.cjs` reutilizado verbatim
  (teste anti-drift).
- **Validação:** `claude plugin validate` ✓; kit oficial `claude plugin test`
  3/3 em runtime real de hooks (zero modelo/rede); `tools/test-claude.py` 4/4;
  captura `evidence/preview-lab.png` (SMIL e troca de quadros ao vivo no
  laboratório, rotulada como NÃO pintura nativa).
- **Limitações comprovadas:** Mods não expõem API de SO para reduced-motion
  (pausa manual + `options.reducedMotion`); pintura nativa no app real NÃO
  observada (sem instância descartável autorizada).

### Codex — visualizador complementar independente (PR #12, `2221ddd`+e2e, merge `03939bd`)
- **Limitação oficial comprovada:** não existe API nativa de painel de 7
  agentes (Pets = 1 companheiro agregado 1536×1872; extensão de IDE não
  suporta pets/plugins). Entrega: visualizador local claramente identificado,
  **sem modificar o aplicativo Codex**.
- **Eventos oficiais:** hooks de projeto (`SubagentStart/Stop`, `Stop`,
  `Interrupt`, `PermissionRequest`, `SessionStart/End`, `UserPromptSubmit`)
  normalizados por `willtech_bridge.py` (async, fail-open, trust via `/hooks`);
  cliente App Server JSON-RPC (`initialize`/`thread/list` + mapeamento de
  `turn/*`).
- **Pipeline real exercitado de ponta a ponta:** stdin dos hooks → feed JSONL
  → SSE (`/events` com replay `/history`) → EventSource → projeção dos sete
  (Interrompido/Trabalhando/Concluído), animação CSS viva comprovada por
  transform computado; captura `evidence/viewer-lab.png`.
- **Protocolo real:** handshake contra binário oficial `codex-app-server`
  v0.169.0 em instância descartável, `CODEX_HOME` isolado, offline
  (`tools/test-appserver.py`, pula sem binário).
- **Limitação registrada:** eventos `turn/*` de uma sessão real exigem
  autenticação do proprietário e gasto de modelo — não exercitados; o
  handshake prova o contrato do cliente, não uma sessão nativa.

### Classificação final da rodada
- OpenCode: **PARCIAL** (causa corrigida e verificada em laboratório; nativo
  não testado). Claude Code: **PARCIAL** (validado pelo tooling oficial e kit
  em runtime real; pintura nativa não observada). Codex: **PARCIAL** (pipeline
  real completo; sessão nativa não exercitada; painel nativo inexistente na
  API oficial).
- Nenhuma simulação, compilação ou decodificação foi anunciada como
  homologação nativa. README, INSTALL e EVOLUCAO declaram as três integrações
  como **experimentais**, com estas limitações explícitas.

<!-- WillTech-General / WILLTECH-BH © 2026 · autoria: github.com/hebwil -->