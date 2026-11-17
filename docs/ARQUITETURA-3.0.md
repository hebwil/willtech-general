# Arquitetura técnica — WillTech-General 3.0

**Referência implementada:** Shared Intelligence 3.0 · **Fonte de verdade:** código da branch main após os PRs #15, #16 e #17 · **Data:** 17/11/2026.

Este documento é um **mapa tecnológico navegável**, não uma proposta de funcionalidades. Os diagramas representam os contratos implementados e separam *controle*, *delegação*, *dados*, *observação* e *evidência*. A execução autônoma depende das capacidades do modelo e do runtime; ver a matriz de homologação ao final.

## 1. Topologia real: autoridade, sete agentes e Sala compartilhada

~~~mermaid
flowchart TB
    subgraph Host["Camada de autoridade do runtime"]
        Native["COMANDANTE NATIVO\nClaude Code | Codex | OpenCode"]
    end
    subgraph WT["Equipe WILLTECH — 7 agentes"]
        General["WILLTECH-GENERAL\ncoordena e consolida"]
        Explorer["Explorador\ncódigo e dependências"]
        Researcher["Pesquisador\nfontes e requisitos"]
        Visual["Visual\nUI e acessibilidade"]
        Executor["Executor\nedição autorizada"]
        Tester["Testador\ntestes em laboratório"]
        Reviewer["Revisor\nrevisão independente"]
    end
    subgraph Knowledge["Dados do projeto — não é agente"]
        Room[("SALA DOS AGENTES\n.willtech/room.db\nSQLite v3, JIT, handoffs")]
    end
    Native -->|"delegação autorizada"| General
    General -->|"trabalho selecionado"| Explorer
    General -->|"trabalho selecionado"| Researcher
    General -->|"trabalho selecionado"| Visual
    General -->|"implementação autorizada"| Executor
    General -->|"verificação"| Tester
    General -->|"parecer independente"| Reviewer
    General -.->|"consultar / registrar"| Room
    Explorer -.->|"consultar / registrar"| Room
    Researcher -.->|"consultar / registrar"| Room
    Visual -.->|"consultar / registrar"| Room
    Executor -.->|"consultar / registrar"| Room
    Tester -.->|"consultar / registrar"| Room
    Reviewer -.->|"consultar / registrar"| Room
    classDef runtime fill:#e5edf7,stroke:#40628a,color:#182b42;
    classDef coordinator fill:#d9e8fd,stroke:#2c5e9e,color:#182b42;
    classDef memory fill:#e0f3ea,stroke:#28765a,color:#163b2c;
    class Native runtime;
    class General coordinator;
    class Room memory;
~~~

**Legenda:** seta contínua = autoridade ou delegação; seta tracejada = acesso à API de conhecimento (consultas e registros, com retorno ao solicitante), **não** comando da Sala. O **comandante nativo não conta** entre os sete agentes. O **General é o primeiro dos sete** e coordena seis especialistas. A Sala **não delega**, não decide permissões e não é um oitavo agente. Não é obrigatório ativar os seis especialistas em uma mesma tarefa.

**Código:** [General OpenCode](../opencode/agent/willtech-general.md) · [roster](../opencode/agent/) · [Sala](../tools/willtech-room.py) · [README](../README.md).

## 2. Delegação, entrega, revisão e reutilização de conhecimento

~~~mermaid
sequenceDiagram
    autonumber
    participant C as Comandante nativo
    participant G as WillTech-General
    participant E as Explorador
    participant S as Sala SQLite
    participant X as Executor
    participant T as Testador
    participant R as Revisor
    C->>G: Tarefa complexa autorizada e critérios
    G->>S: query por objetivo / JIT
    S-->>G: Contexto rotulado QUARENTENA
    G->>E: Investigar escopo definido
    E->>S: put finding + provenance/hash
    E-->>G: Descoberta e referência da evidência
    G->>X: Delegar implementação autorizada
    X->>S: put decision / handoff-record
    X-->>G: Diff e resultado
    G->>T: Testar artefatos isolados
    T->>S: put test_result + evidência
    T-->>G: Resultado de teste
    opt Alteração crítica ou revisão necessária
        G->>R: Diff + aceite + evidências; sem conclusão do executor
        R->>S: handoff-fetch / evidências de contexto
        R-->>G: Parecer independente
    end
    G->>S: handoff-validate por autoridade e evidência
    G-->>C: Consolidação verificável; decisão final é do comandante
    Note over C,S: Nova sessão consulta conhecimento válido; stale não vira instrução
~~~

Este é o **fluxo arquitetural previsto e exercitado em contratos/smokes**, não uma afirmação de que toda execução com um modelo pequeno necessariamente completa cada etapa. Os testes com Qwen3-1.7B demonstraram delegações reais, mas não edição funcional completa nem registro manual de conhecimento pelo modelo. [Evidência zero custo](HOMOLOGACAO-ZERO-CUSTO.md).

## 3. Integrações oficiais: eventos de runtime versus inteligência

~~~mermaid
flowchart TB
    subgraph Hosts["Entradas por plataforma"]
        OC["OpenCode V2\nplugin index.js"]
        CC["Claude Code\nhooks e settings"]
        CX["Codex\nhooks, App Server"]
    end
    AUTO["Núcleo determinístico\nwilltech-auto.py"]
    subgraph Engines["Serviços projeto-locais"]
        DOS["Dossiê, lições e guardas\nwilltech-dossie.py"]
        ROOM["Consulta JIT\nwilltech-room.py"]
        SUP["Supervisor de delegação\nwilltech-supervisor.py"]
        TR["Trace e verificação\nwilltech_trace.py / drift"]
    end
    OUT["Resposta à plataforma\ncontexto em quarentena / veto de guarda / telemetria"]
    OC -->|"hooks setup, prompt, execute, idle"| AUTO
    CC -->|"SessionStart, UserPromptSubmit, Pre/PostToolUse, Stop"| AUTO
    CX -->|"eventos de hook homologados por formato"| AUTO
    AUTO --> DOS
    AUTO --> ROOM
    AUTO --> SUP
    AUTO --> TR
    DOS --> OUT
    ROOM --> OUT
    SUP --> OUT
    TR --> OUT
    OUT --> OC
    OUT --> CC
    OUT --> CX
~~~

**Distinção importante:** a automação do OpenCode em [index.js](../opencode/plugins/willtech/index.js) chama o [núcleo Python](../tools/willtech-auto.py). O pacote **visual** do OpenCode é separado e não equivale ao plugin de automação. O Codex usa também um **viewer complementar** alimentado por eventos do App Server; não há alegação de painel nativo de sete agentes no Codex. [Hooks Codex](../codex/willtech-visual/hooks/hooks.json) · [roteamento Claude](../claude-code/settings/willtech-routing.md) · [instalação](../INSTALL.md).

## 4. Estrutura física da Sala, indexação e isolamento

~~~mermaid
flowchart LR
    Agents["General e especialistas\nput, validate, query, handoff, skill"]
    Guard["Validação de entrada\nallowlists, caminhos, limites, segredos"]
    Scope["Isolamento por projeto\nSHA-256(git toplevel + remote)"]
    Query["Consulta e ranking\nvalidated antes de candidate"]
    FTS{"FTS5 disponível?"}
    FTSIndex["FTS5 + BM25\nrecords_fts + triggers"]
    Like["Fallback LIKE\nranking por termos"]
    DB[("room.db\nrecords, handoffs, skill_meta,\nschema_migrations")]
    Lock["Concorrência\nWAL, busy_timeout,\nSQLite sidecar BEGIN IMMEDIATE"]
    Output["Saída JIT\naté 1200 caracteres por consulta\nQUARENTENA"]
    Agents --> Guard --> Scope
    Scope --> DB
    DB --> Lock
    Agents --> Query --> FTS
    FTS -->|sim| FTSIndex --> DB
    FTS -->|não| Like --> DB
    DB --> Output
    Output -.-> Agents
~~~

~~~mermaid
erDiagram
    records ||--o| handoffs : "identifica handoff"
    records ||--o| skill_meta : "complementa skill"
    records ||--o| records_fts : "indexa se FTS5"
    records {
        INTEGER id PK
        TEXT kind
        TEXT project_id
        TEXT specialty
        TEXT summary
        TEXT path_ref
        TEXT source_hash
        TEXT evidence_hash
        TEXT status
        TEXT attrs
    }
    handoffs {
        INTEGER id PK
        INTEGER record_id FK
        TEXT objective
        TEXT evidence_ids
        TEXT next_owner
        TEXT validation_state
        TEXT result
        TEXT result_hash
        INTEGER knowledge_version
        TEXT validated_by
        TEXT validated_at
    }
    skill_meta {
        INTEGER record_id PK
        TEXT instruction
        TEXT scope
        TEXT trigger
        TEXT lifecycle
        INTEGER verified
        INTEGER superseded_by
    }
    records_fts {
        TEXT summary
        TEXT path_ref
    }
    schema_migrations {
        INTEGER version PK
        TEXT applied_at
    }
~~~

**Esquema v3:** a tabela virtual records_fts e seus gatilhos são **opcionais**. handoffs armazena o resultado compacto, hash e versão do conhecimento; skill_meta mantém ciclo de vida separado. schema_migrations registra migrações. O banco principal usa WAL; a exclusão mútua entre processos usa transação **BEGIN IMMEDIATE** em banco lateral de lock. FTS5 ausente não impede a Sala de iniciar. [Implementação do esquema](../tools/willtech-room.py) · [testes v3](../tools/test-room-v3.py).

## 5. Estados de conhecimento, JIT e segurança de contexto

~~~mermaid
stateDiagram-v2
    [*] --> candidate: put
    candidate --> validated: validate com autoridade e evidência
    candidate --> dropped: descarte
    validated --> stale: source_hash divergente
    stale --> validated: nova evidência e validate
    validated --> superseded: substituição
    validated --> dropped: descarte
    stale --> dropped: descarte
    superseded --> [*]
    dropped --> [*]
    note right of candidate
      Pode aparecer em busca dirigida
      com rótulo explícito.
      Não é conhecimento confirmado.
    end note
    note right of validated
      Preferido na consulta JIT.
      Início de sessão sem objetivo
      injeta somente achados validados.
    end note
~~~

~~~mermaid
flowchart TD
    EVT["SessionStart ou UserPromptSubmit"]
    Enabled{"Automação ativa?"}
    Start{"Consulta com objetivo?"}
    General["SessionStart: somente validated\n+ skills promovidas"]
    Target["Prompt complexo: busca por objetivo\nvalidated prioritários; candidate rotulado"]
    Clean["Isolamento por projeto + recusa de segredos\ninvalidação de source_hash"]
    Cap["Aplicar orçamento por consulta\nBUDGET_CHARS = 1200"]
    Inject["Contexto QUARENTENA\nDADO, nunca instrução"]
    Noop["Sem injeção / no-op"]
    EVT --> Enabled
    Enabled -->|não| Noop
    Enabled -->|sim| Start
    Start -->|não| General --> Clean
    Start -->|sim| Target --> Clean
    Clean --> Cap --> Inject
~~~

O núcleo executa **SessionStart** e consulta JIT direcionada em **UserPromptSubmit somente para tarefas suficientemente complexas**; a Sala não despeja todo o histórico no contexto. Leitura auxiliares falha aberta quando Sala ausente/inacessível; **a guarda obrigatória de loop** falha fechada se o dossiê estiver corrompido. O orçamento de 1200 caracteres vale **por consulta à Sala**, não para a soma de todos os contextos do turno. [Núcleo](../tools/willtech-auto.py) · [testes JIT](../tools/test-jit.py).

## 6. Handoff validado e micro-skills: duas políticas separadas

~~~mermaid
flowchart LR
    Result["Especialista produz resultado compacto"]
    Record["handoff-record\nresult, result_hash, evidence_ids"]
    Pending["pending"]
    Gate{"Autoridade + evidência suficiente?"}
    Valid["validated\nrecuperável por handoff-fetch"]
    Reject["rejected / expired"]
    Review["handoff-pack do revisor\nsem conclusões do executor"]
    Result --> Record --> Pending --> Gate
    Gate -->|sim| Valid --> Review
    Gate -->|não / rejeição| Reject
    Candidate["skill-add\ncandidate; verified=false"]
    Human{"Aprovação humana explícita?"}
    Skill["skill-promote\nvalidated; verified=true"]
    Exclude["Não auto-injetar"]
    Candidate --> Human
    Human -->|sim| Skill
    Human -->|não| Exclude
~~~

- Handoff não validado não é injetado automaticamente; a validação exige um responsável permitido e evidência suficiente. O resultado recuperado inclui hash e versão do conhecimento.
- O revisor recebe **diff, critérios de aceite e evidência**, nunca a conclusão pronta do executor.
- Micro-skills exigem **aprovação humana explícita**, ainda que tenham sido extraídas de trace; importadas começam como candidatas não verificadas.

[Contrato de handoff e skills](SHARED-INTELLIGENCE.md) · [testes de handoff](../tools/test-handoff.py) · [testes de Sala v3](../tools/test-room-v3.py).

## 7. Inteligência operacional: planejamento, RepoMap, supervisão e evidências

~~~mermaid
flowchart TB
    Task["Tarefa recebida e autorizada"]
    Class["Elephant: classificar\nDIRECT / PLAN / PLAN+REVIEW"]
    Map["RepoMap incremental\nsímbolos, dependências, hashes"]
    Brief["Brief do dossiê\ncache por HEAD + working tree + escopo"]
    General["General seleciona especialistas"]
    Supervisor["Supervisor\nsoft/hard timeout, anti-loop,\nconcorrência, retry reconciliado"]
    Specialists["Especialistas selecionados"]
    Trace["Trace + evidências verificáveis\nsem conteúdo de credenciais"]
    Reviewer["Goldfish: review-pack\ncontexto fresco, sem conclusão do executor"]
    Check["Verify + drift\nexigir evidência atual"]
    Finish["Comandante decide e entrega"]
    Task --> Class
    Class -->|"tarefa não trivial"| Map
    Class --> Brief
    Map --> Brief --> General
    General --> Supervisor --> Specialists --> Trace
    Trace -->|"mudança crítica"| Reviewer --> Check
    Trace -->|"gate determinístico suficiente"| Check
    Check --> Finish
    Class -->|"DIRECT: sem delegação desnecessária"| Finish
~~~

**Dossiê:** decisões, lições com prova, guards contra repetição e revisão seletiva; cache invalida por alterações relevantes. **RepoMap:** símbolos e trechos revalidados por hash, sem assumir que índice substitua arquivo atual. **Supervisor:** timeout registrado **não** significa execução cancelada; cancelamento requer confirmação oficial do runtime. **Drift:** confere coerência entre código, contratos e documentos. [Dossiê](../tools/willtech-dossie.py) · [RepoMap](../tools/willtech-repomap.py) · [Supervisor](../tools/willtech-supervisor.py) · [Drift](../tools/willtech-drift.py).

## 8. Fronteiras de segurança, lifecycle e interfaces de observação

~~~mermaid
flowchart LR
    subgraph Project["Escopo autorizado do projeto"]
        Installer["Instalador reversível\nsh / PowerShell"]
        Enabled[".willtech/enabled"]
        Data[("SQLite e dossiê\npreservação de dados do projeto")]
        Hooks["Hooks e plugin de automação"]
    end
    Third["Configuração e plugins de terceiros"]
    Installer -->|"install / update / enable"| Enabled
    Enabled --> Hooks
    Hooks -.-> Data
    Installer -->|"disable: desativa hooks"| Enabled
    Installer -->|"uninstall: desfaz arquivos gerenciados"| Third
    Installer -->|"backup / restore verificado"| Data
~~~

~~~mermaid
flowchart TB
    Events["Eventos oficiais de sessões e ferramentas"]
    OBS["Camada de observação\nsem criar delegações"]
    OpenGUI["OpenCode Desktop\nplugin visual experimental"]
    ClaudeGUI["Claude Code\nMod visual por superfície"]
    CodexGUI["Codex\nviewer complementar via App Server"]
    Events --> OBS
    OBS --> OpenGUI
    OBS --> ClaudeGUI
    OBS --> CodexGUI
~~~

O instalador de **automação** é projeto-local e reversível; a GUI do OpenCode tem **ativação independente e opt-in** por [willtech-gui.py](../tools/willtech-gui.py) para o servidor de fundo do Desktop. Desativar o painel não interrompe agentes. Mudanças não autorizadas em plugins de terceiros não devem ser apagadas. Dados locais do usuário são preservados no uninstall conforme contrato. [Instalação e rollback](../INSTALL.md).

**Limitação comprovada:** aplicativo OpenCode Desktop real e carga do plugin GUI foram verificados em laboratório macOS, mas **a exibição nativa do painel dos sete mascotes ainda não foi comprovada**. O benchmark gratuito 3×3 mediu menor releitura, porém **não comprovou economia líquida de tokens nem melhoria funcional** com Qwen3-1.7B. O Codex oferece aqui um **visualizador complementar**, não painel nativo de sete agentes. Não converter benchmarks ou testes de navegador simulado em certificação de interface nativa.

## 9. Rastreabilidade: módulo, teste e tipo de prova

| Camada | Fonte de implementação | Testes / evidência | Estado com limite |
|---|---|---|---|
| Comandante / General / seis especialistas | [contratos OpenCode](../opencode/agent/), [roteamento Claude](../claude-code/settings/willtech-routing.md) | [test-homolog](../tools/test-homolog.py), [CI 5/5](https://github.com/hebwil/willtech-general/actions/runs/44167263550) | Sete agentes carregados em host oficial; execução do modelo pequeno limitada |
| Sala / persistência / FTS5 / LIKE | [willtech-room.py](../tools/willtech-room.py) | [test-room](../tools/test-room.py), [test-room-v3](../tools/test-room-v3.py), [smoke 17/17](../tools/smoke-intelligence.py) | Integração SQLite real e fallback no CI |
| Consulta JIT / quarentena / hooks | [willtech-auto.py](../tools/willtech-auto.py) | [test-jit](../tools/test-jit.py), [test-auto](../tools/test-auto.sh) | Integração determinística; plugin V2 também testado no host oficial |
| Handoffs / skills / revisão independente | [room](../tools/willtech-room.py), [dossiê](../tools/willtech-dossie.py) | [test-handoff](../tools/test-handoff.py), [test-plan](../tools/test-plan.sh) | Persistência, autoridade e gate humano verificados |
| Planejamento / RepoMap / supervisor / drift | [dossiê](../tools/willtech-dossie.py), [RepoMap](../tools/willtech-repomap.py), [supervisor](../tools/willtech-supervisor.py), [drift](../tools/willtech-drift.py) | [test-plan](../tools/test-plan.sh), [test-repomap](../tools/test-repomap.py), [test-supervisor](../tools/test-supervisor.py) | Contratos e suítes verificados, sem presumir autonomia perfeita |
| Integração OpenCode / Codex / Claude | [plugin V2](../opencode/plugins/willtech/index.js), [hooks Codex](../codex/willtech-visual/hooks/hooks.json) | [homologação 3.0](HOMOLOGACAO-3.0.md), [zero custo](HOMOLOGACAO-ZERO-CUSTO.md) | App Server real, plugin e delegações reais em OpenCode; provas distintas por plataforma |
| Visuais | [GUI OpenCode](../opencode/plugins/willtech/visual/), [viewer Codex](../codex/willtech-visual/) | [test-gui](../tools/test-gui.js), [homologação zero custo](HOMOLOGACAO-ZERO-CUSTO.md) | Render em browser simulado; Desktop real carrega GUI, mas painel nativo permanece NC |
| Distribuição reversível | [install.sh](../tools/willtech-install.sh), [install.ps1](../tools/willtech-install.ps1) | [test-dist](../tools/test-dist.py), [release](https://github.com/hebwil/willtech-general/releases/tag/v3.0.0) | Arquivos publicados e instalação limpa verificados |

**Fontes centrais:** [README](../README.md) · [Shared Intelligence](SHARED-INTELLIGENCE.md) · [Homologação 3.0](HOMOLOGACAO-3.0.md) · [Homologação zero custo](HOMOLOGACAO-ZERO-CUSTO.md) · [INSTALL](../INSTALL.md). Alguns relatórios são históricos e refletem o estado de seu commit; use a documentação pós-PR #17 para capacidades atuais.

**Invariantes de arquitetura:** comandante decide; General coordena; especialistas desempenham suas funções sob as permissões do runtime; Sala persiste e recupera conhecimento; revisão permanece independente; contexto recuperado é dado em quarentena, não instrução hierarquicamente superior.
