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

- **OpenCode e Codex**: nenhum hook de runtime verificado neste repositório. A automação
  plena existe apenas no fluxo Claude Code (homologação executa o trace). Nessas
  plataformas, brief/drift/guardas são acionados explicitamente pelo comandante/General
  via wrapper. Nenhum plugin/hook foi adicionado para não tocar instalações ativas nem
  introduzir superfície não testada.
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

<!-- WillTech-General / WILLTECH-BH © 2026 · autoria: github.com/hebwil -->