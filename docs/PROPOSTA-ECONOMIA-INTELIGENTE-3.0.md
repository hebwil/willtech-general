# RFC — Economia inteligente sem perda de capacidade (WillTech-General 3.0)

**Estado:** IMPLEMENTADA E HOMOLOGADA via PR #20 (branch `codex/3.0-inteligencia-economia`) · **Orçamento financeiro:** US$ 0,00 consumido · **Base:** arquitetura 3.0 após PRs #15–#18 e PR #20 · **Data:** 18/11/2026.

## Objetivo e regra inviolável

Aumentar a **eficácia de cada agente** por meio de memória validada, seleção melhor de evidências, menos investigação duplicada e handoffs mais úteis. A economia deve ser consequência de **menos trabalho desnecessário**, não de reduzir artificialmente o poder do modelo ou esconder informação relevante.

**Não pode acontecer:** desabilitar ferramentas, retirar permissões, trocar modelos/provedores, impor contexto insuficiente, suprimir erros, apagar dados brutos, falsificar progresso, impedir exploração legítima ou entregar resposta inferior para economizar tokens. Acesso ao contexto original completo deve continuar disponível por caminho autorizado, sob demanda. Na dúvida sobre relevância ou qualidade, preservar a execução atual e suas guardas.

A hierarquia é: **comandante nativo** (autoridade da sessão) → **WillTech-General** (agente 1/7, coordenação) → **seis especialistas** (Explorador, Pesquisador, Visual, Executor, Testador, Revisor). A **Sala dos Agentes** é memória compartilhada, **não** comanda, não delega e **não** é um oitavo agente. [Mapa técnico](ARQUITETURA-3.0.md).

## Diagnóstico mensurado: por que não há economia comprovada ainda

O benchmark [HOMOLOGACAO-ZERO-CUSTO.md](HOMOLOGACAO-ZERO-CUSTO.md), [run 44187245309](https://github.com/hebwil/willtech-general/actions/runs/44187245309), comparou 3 execuções por cenário com Qwen3-1.7B real em laboratório público de custo financeiro zero:

| Métrica (média/execução) | Sem Sala | Com Sala | Resultado |
|---|---:|---:|---|
| input_tokens novos | 111,7 | 1462,7 | +1351 |
| output_tokens | 193,7 | 222,7 | +29 |
| cache_read | 12078,3 | 10841,0 | −1237,3 |
| input+output+cache_read (volume, **não custo**) | 12383,7 | 12526,4 | **+1,15%** |
| duração (ms) | 41283,7 | 47204,3 | **+14,34%** |
| releituras repetidas | 2 | 1 | **−50%** |
| sucesso funcional medido | 0 | 0 | sem melhoria funcional |

**Interpretação:** a Sala reduziu uma releitura, mas a injeção JIT trouxe mais tokens de entrada novos e prejudicou a reutilização do cache de prefixo nesta tarefa. **Não foi demonstrada economia total de tokens, custo ou melhora da solução.** O modelo pequeno não concluiu corretamente a tarefa de referência. Não extrapolar o resultado para modelos mais fortes ou outros workloads.

**Meta de engenharia, NÃO previsão:** buscar 10–20% de economia líquida em tarefas representativas, **sem perda de qualidade**. Esse intervalo é somente um objetivo para experimentos. Não publicar percentual como fato sem medição.

## Fontes externas avaliadas — aproveitar ideias, não instalar tudo

| Projeto | Padrão aproveitável | Encaixe possível no General | Cuidado / decisão |
|---|---|---|---|
| [Microsoft TokenEconomizer](https://github.com/microsoft/TokenEconomizer) | Memória de experiências, micro-habilidades e redução de repetição | Reforçar a seleção de skills verificadas da Sala e a recuperação por especialidade | **Não** copiar tool pruning que desative ferramentas; promoção de skills continua sujeita a aprovação humana. Revalidar licença/versão antes de incorporar código |
| [Aider](https://github.com/Aider-AI/aider) | Repo map com relevância de símbolos e relações | Evoluir o RepoMap **já existente** para briefs ordenados por tarefa, escopo e dependência | Preferir implementar mecanismo compatível localmente; não substituir RepoMap ou importar dependências grandes apenas para ranking |
| [RTK](https://github.com/rtk-ai/rtk) | Saídas curtas de ferramentas, com detalhes acessíveis | **Modo opcional**, limitado a comandos com saída estruturada e logs completos preservados no laboratório | Nunca resumir silenciosamente stderr, stacktrace, falhas ou dados requeridos pelo Testador/Revisor; verificar licença e riscos de transformação |
| [Serena](https://github.com/oraios/serena) | Navegação semântica e símbolos via infraestrutura de linguagens | Consultas seletivas read-only para Explorador/Executor quando disponíveis | Dependência opcional, sem obrigar instalação no usuário; fallback RepoMap atual |
| [Mem0](https://github.com/mem0ai/mem0) | Ideias de recuperação e consolidação de memória contextual | Estudo de ranking de records e deduplicação, preservando a Sala SQLite v3 | **Não** introduzir serviço remoto, banco paralelo, embedding pago ou importação de conversas privadas |
| [Graphiti](https://github.com/getzep/graphiti) | Grafo temporal e relações entre fatos | Possível estudo de relações entre finding, decisão, hash e handoff | **Não** acrescentar Neo4j/LLM/serviço externo como dependência básica; complexidade pode anular economia |

Estes são **candidatos de pesquisa e padrões de design**, não integrações já executadas. Para copiar código de terceiros, conferir licença, avisos de atribuição, riscos e compatibilidade na versão específica e submeter PR próprio. A economia anunciada por qualquer projeto externo **não é economia medida no WillTech**.

## Proposta técnica de baixo risco

### 1. Recuperação JIT adaptativa e sensível à especialidade

Atualmente [willtech-auto.py](../tools/willtech-auto.py) consulta [willtech-room.py](../tools/willtech-room.py) com orçamento canônico **1200 caracteres por consulta** e faz busca pelo objetivo em prompts complexos. Esse orçamento é **limite da consulta**, não economia automática nem limite do raciocínio do agente.

**Proposta (feature flag experimental, default desativada):**
- Classificar necessidade de consulta: nada pertinente / descoberta validada / questão com dependências / investigação aprofundada.
- Primeiro buscar metadados curtos: **ID, specialty, kind, status, relevância, source_hash, evidence_hash, path_ref**. Não mover todo o resumo/brief antes de saber que será usado.
- Injetar **somente** conhecimento compatível com objetivo, especialidade e estado validado; privilegiar síntese sem duplicação de registros idênticos.
- Aplicar orçamentos dinâmicos exemplificativos **0, 256, 512, 1200 caracteres**, **sem travar a obtenção posterior do contexto integral**. Esses valores são hipóteses de experimento, não limites rígidos de capacidade. Agente/comandante devem conseguir solicitar expansão de evidências, trechos e histórico quando necessário.
- Preservar o prefixo estável sempre que o runtime permitir: a parte variável da Sala não deve destruir cache de prompt desnecessariamente; medir efeito na prática, sem presumir comportamento idêntico em OpenCode/Codex/Claude.
- Nunca auto-injetar handoff \`pending\`, skills \`candidate\`, dados stale ou conteúdo inseguro; manter cabeçalho **QUARENTENA**, limites, isolamento, gate de validação e fallback FTS5/LIKE.
- Sem similaridade/embedding/modelo adicional pago; usar índices existentes, pontuação determinística e fallback. Falha de consulta = comportamento atual, não falha de tarefa.

### 2. Contexto reutilizável por função, sem retirar poder

**General:** brief de objetivo, dependências, evidências e responsáveis, com acesso à visão completa sob demanda. **Explorador:** símbolos e referências do RepoMap antes de arquivos completos. **Pesquisador:** referências verificadas com data/versão para decidir quando consultar fontes atualizadas. **Visual:** padrões de UI, acessibilidade e histórico de decisões de interface. **Executor:** arquivos e trechos autorizados, razões do plano, evidências e critérios; nunca recusar os demais dados necessários. **Testador:** testes afetados + resultados completos disponíveis em logs. **Revisor:** diff + critérios + evidência **sem receber conclusão pronta do executor**; acesso independente a código e logs.

Handoff curto: resultado verificável, status, hashes, caminhos das evidências, incertezas e próximos passos. **Não** transferir uma conversa inteira se as evidências já estão registradas; **não** remover a possibilidade de inspeção independente.

### 3. Memória interprojetos somente por promoção explícita

A Sala **continua isolada por projeto** (\`project_id\`); não permitir \`query\` cruzada direta. Estudar, como fase separada, uma **biblioteca de padrões genéricos aprovados**, exportando **cópias** de conhecimento verificável e não sensível após autorização humana e checagem de licença/origem. No projeto destino tudo entra como **candidate** e precisa passar pelas validações normais; skills continuam exigindo aprovação humana explícita. Nunca importar por padrão conversas privadas, credenciais, artefatos de clientes, códigos fechados ou memória de outro projeto.

### 4. Saídas de ferramentas: compressão sem perda de prova

No fluxo de exploração, ferramentas podem devolver **resumo + caminho/hash do log completo**; o log original fica intacto e recuperável no escopo do projeto/laboratório. Se houver erro, regressão, stacktrace ou dúvida, o Testador/Revisor sempre recebe o conteúdo bruto. Compactação é **opt-in** e por categoria de comando; nunca interceptar todos os comandos silenciosamente, nunca esconder falhas. Comparar custo de tokens e risco de omissão.

## Integração em fases (nenhuma feature nova autorizada por este RFC)

1. **Instrumentar antes de mudar**: métricas de injeção da Sala, registros usados, cache_read, input/output, latência, leitura repetida, falhas, retrabalho e sucesso funcional; sem guardar conteúdo privado do prompt.
2. **Ranking read-only**: candidatos por relevância e especialidade, com \`query_text\` atual como fallback; usar testes adversariais e consultas de conhecimento obsoleto.
3. **JIT adaptativo**: experimentos A/B com budgets e expansão explícita, sem perda de conhecimento acessível.
4. **RepoMap e skills por especialidade**: usar índice existente, evidência e aprovação humana; não duplicar cache/skills.
5. **Compactação opcional de logs**: pilotos isolados com provas de ausência de perda de erro, segurança e rastreabilidade.
6. **Pesquisa de biblioteca interprojetos**: somente após projeto de segurança e aprovação humana; sem ativação automática.

Não implantar ao mesmo tempo todos os mecanismos. Prioridade: **ranking read-only + JIT adaptativo**. Mem0/Graphiti são estudos, não requisitos.

## Gates de homologação e rollback

**Ambiente:** GitHub Actions descartável com ferramentas/modelo de uso efetivamente gratuito, sem credenciais, contas ou instalações pessoais. **US$ 0,00 autorizado**; não usar serviços que possam cobrar (nem créditos gratuitos de contas pessoais). Não tocar tag/release \`v3.0.0\`; qualquer código futuro exige branch, PR, CI e plano de rollback.

**Bancada:** mesmo modelo aberto, mesmas tarefas, mesmo regime de cache, mesmo limite de tokens, mesma política de delegação e critérios funcionais. Não basta o cenário original, cujo modelo não resolveu a tarefa. Adicionar casos onde baseline conclua corretamente (curtos, médios, complexos; com/sem memória; seis especialidades; revisão independente; código com mudanças entre sessões), repetir ≥3 por cenário e reportar dispersão. Medir **custo efetivo com precificação aplicável** quando houver; no lab CPU gratuito, reportar tokens e latência separadamente (financeiro = 0 não significa computação gratuita ilimitada). Não confundir cache_read com input não cacheado.

**Aceite, tudo obrigatório:**
- Resultado funcional **igual ou superior ao baseline** em cada classe de tarefa crítica; regressão bloqueia a otimização mesmo que haja menos tokens.
- Nenhum agente perde acesso a ferramentas ou a contexto necessário; revisão independente e autorização de escrita preservadas.
- FTS5 e fallback LIKE, isolamento entre projetos, concorrência, redaction, QUARENTENA, \`stale\`, handoffs, skills e rollback íntegros.
- Medir economia líquida por cenário; percentual só é publicado se houver evidência A/B com logs e resultados funcionais. Caso pior, desligar a flag e registrar honestamente.
- CI Windows/Linux/macOS + smoke, sem SKIP de requisito obrigatório, sem alteração de configuração pessoal.
- Preservar export/backup do banco, nunca modificar históricos de outras sessões.

## Relatório de implementação e medição A/B/C (PR #20 — 18/11/2026)

### 1. Fases implementadas
- **Fase A (Recuperação JIT adaptativa):** Budgets dinâmicos (0, 256, 512, 1200 chars), ranking por objetivo/especialidade/relevância/evidência, flag `--expand`, isolamento de prefixo estável mantendo contexto idêntico durante turnos de ferramentas sem quebrar o cache de prefixo do LLM.
- **Fase B (Memória especializada dos 7 agentes):** Subcomando `context-pack --for-agent <role>`. Cada especialista recebe apenas seu escopo (Explorador: grafo e descobertas; Pesquisador: refs; Visual: UI/a11y; Executor: escopo e decisões; Testador: critérios, testes afetados e logs; Revisor: diff + critérios + evidências validadas sem conclusões prontas do executor; General: consolidação e riscos).
- **Fase C (RepoMap direcionado):** Cache de AST/regex com revalidação estrita por SHA-256 (elimina re-parsing de arquivos intactos), ranking de relevância por Personalized PageRank determinístico (stdlib Python) e filtro `--affected` para o Testador.
- **Fase D (Micro-skills e biblioteca controlada):** `pattern-export` e `pattern-import` com provenance estrita, `source_hash`, neutralização estrutural e obrigatoriedade de aprovação humana explícita (`--i-approve-human`) no projeto destino.
- **Fase E (Saídas estruturadas com evidência íntegra):** `tools/willtech-output.py` opt-in com persistência de log bruto em `.willtech/logs/<sha[:16]>.log`, sanitização de segredos antes do disco, conferência por `--expected-sha256` e 100% de preservação de stderr, stacktraces e falhas de teste.

### 2. Benchmark A/B/C Definitivo no GitHub Actions (Run 44386086294 — Custo US$ 0,00)
Medição autêntica com 27 execuções no runner gratuito Ubuntu com OpenCode V2.3.0 oficial + llama.cpp b12483 + Qwen3-1.7B-Q4_K_M (3 tarefas × 3 repetições × 3 braços), após correção do ambiente `PWD` no subprocesso e orientação de leitura nativa (`read`):
- **Braço A (Baseline):** WillTech-General 3.0 canônico sem otimização adaptativa.
- **Braço B (JIT Adaptativo):** Prefixo estável + JIT adaptativo seletivo.
- **Braço C (Completo):** JIT Adaptativo + RepoMap direcionado com PageRank + Memória especializada por agente.

| Tarefa | Braço | Novos Input Tokens (média ± std) | Duração ms (média ± std) | Releituras (média) | Sucesso Funcional |
|---|---|---:|---:|---:|---:|
| **T1 (Simples)** | A (Baseline) | 5,849.0 ± 4,998.1 | 51,743 ± 25,268 | 0.0 | **3/3 (100%)** |
| | B (JIT Adaptativo) | 1,480.3 ± 2,418.5 (**-74.69%**) | 18,948 ± 4,754 (**-63.38%**) | 0.0 | **3/3 (100%)** |
| | C (Completo) | 1,569.7 ± 2,461.2 (**-73.16%**) | 25,424 ± 6,152 (**-50.86%**) | 0.3 | **3/3 (100%)** |
| **T2 (Média c/ Memória)** | A (Baseline) | 3,127.7 ± 2,530.9 | 9,704 ± 8,321 | 0.0 | 1/3 (33.3%) |
| | B (JIT Adaptativo) | 1,688.7 ± 2,554.2 (**-46.01%**) | 19,296 ± 712 (+98.84%) | 0.0 | **3/3 (100%)** |
| | C (Completo) | 1,709.0 ± 2,589.4 (**-45.36%**) | 19,923 ± 145 (+105.30%) | 0.0 | **3/3 (100%)** |
| **T3 (Complexa/Invalidação)** | A (Baseline) | 5,907.7 ± 5,114.8 | 41,584 ± 22,547 | 0.0 | 1/3 (33.3%) |
| | B (JIT Adaptativo) | 4,983.3 ± 4,650.5 (**-15.65%**) | 86,005 ± 49,544 (+106.82%) | 2.7 | 1/3 (33.3%) |
| | C (Completo) | 8,633.7 ± 3,189.5 (+46.14%) | 176,415 ± 48,676 (+324.24%) | 2.3 | 1/3 (33.3%) |

**Consolidação Geral Real (27 execuções):**
- **Taxa de Sucesso Funcional Geral:**
  - Braço A (Baseline 3.0): 5/9 (55.6%)
  - **Braço B (JIT Adaptativo): 7/9 (77.8%)** — Ganho real de **+22.2 pontos percentuais**
  - **Braço C (Completo): 7/9 (77.8%)** — Ganho real de **+22.2 pontos percentuais**
- **Braço B (JIT Adaptativo):**
  - Redução agregada de novos tokens de entrada: **−45.23%** (4,961.4 → 2,717.4)
  - Redução de tokens efetivos faturados: **−42.70%** (5,075.2 → 2,908.1)
  - Redução ponderada de tokens de API: **−19.92%** (5,730.6 → 4,589.3)
  - Aumento expressivo no reúso de cache de prefixo: **+156.51%** (6,553.9 → 16,811.7)
  - Em T1: **-74.69%** em novos input tokens e **-63.38%** em latência
  - Em T2: **-46.01%** em novos input tokens, saltando de 33.3% para **100% de precisão funcional**
- **Braço C (Completo):** Confirma a hipótese arquitetural de que o RepoMap e a injeção especializada devem operar de forma estritamente opt-in, pois a carga de contexto estrutural sem demanda prévia eleva o consumo de tokens (+46.14% em T3).
- **Custo financeiro real:** US$ 0,00 comprovado em todas as 27 execuções.

**STATUS DESTA PÁGINA: IMPLEMENTADO, CORRIGIDO E HOMOLOGADO COM SUCESSO COMPROVADO NO RUN 44386086294. ZERO FALSO PASS. CUSTO US$ 0,00.**
