# WillTech-General — Arquitetura Autoral de Orquestração Multiagente

> Repositório privado de preservação da arquitetura WILLTECH de hierarquia multiagente
> (comandante → tenente coordenador → especialistas), com variantes para
> **Claude Code**, **OpenCode** e **Codex**.

## O que é

A estação WILLTECH organiza agentes de IA em uma **hierarquia de comando** com
responsabilidades e permissões estritas: um agente principal (o "comandante") coordena
a sessão e delega tarefas complexas a um tenente coordenador (`willtech-general`),
que por sua vez aciona especialistas de função única e consolida as evidências.

Esta implementação é **autoral e personalizada da WILLTECH**. Ela NÃO copia código de
terceiros; os componentes externos citados abaixo são apenas **referências de integração**
e mantêm seus próprios repositórios e licenças:

| Componente externo | Origem | Papel na estação |
|---|---|---|
| Elephant Goldfish Model (EGM) | `github.com/google/elephant-goldfish-model` | Revisão independente em contexto fresco (fluxo opcional citado nos prompts) |
| TokenEconomizer | `github.com/microsoft/TokenEconomizer` | Economia de tokens (plugin separado, não faz parte desta arquitetura) |

Nenhuma reivindicação de autoria é feita sobre esses componentes externos.

## Hierarquia

```
┌─────────────────────────────────────────────┐
│  COMANDANTE (agente principal nativo)       │
│  decide escopo, autoriza alterações         │
└──────────────────┬──────────────────────────┘
                   │ subagent
┌──────────────────▼──────────────────────────┐
│  willtech-general (tenente coordenador)     │
│  decompõe, delega, consolida evidências     │
└──┬───────┬───────┬───────┬───────┬───────┬──┘
   ▼       ▼       ▼       ▼       ▼       ▼
explorador pesquisador visual executor testador revisor
(leitura) (leitura) (leitura) (escrita (lab     (leitura,
                             restrita) isolado) contexto fresco)
```

### Matriz de acionamento

| Especialista | Função | Permissão |
|---|---|---|
| `willtech-explorador` | Investigar repositórios, código, dependências | Somente leitura |
| `willtech-pesquisador` | Documentação oficial, GitHub, fontes técnicas | Somente leitura |
| `willtech-visual` | Interface, UX, acessibilidade, Astro | Somente leitura (análise) |
| `willtech-executor` | Implementar mudanças **expressamente autorizadas** | Escrita apenas no escopo aprovado |
| `willtech-testador` | Executar testes em ambiente isolado | Laboratório dedicado |
| `willtech-revisor` | Revisão independente de código e regressões | Somente leitura, contexto fresco |

### Regras transversais

- Escopo autorizado vem sempre do comandante; o General não decide escopo sozinho.
- Tarefa trivial não é delegada (economia de tokens e de contexto).
- Máximo de 2 tentativas por problema; bloqueio é registrado e a execução segue.
- Proibido: sudo, `git push` sem aprovação, credenciais, `.env`, gateways, VPS, produção.
- Toda conclusão exige evidência (comando, saída, arquivo, resultado de teste).

## Estrutura deste repositório

```
willtech-general/
├── claude-code/            variante Claude Code (pacote original "willtech-station")
│   ├── agents/general/         willtech-general com frontmatter Claude
│   ├── agents/especialistas/   os 6 especialistas (formato Claude)
│   ├── settings/               bloco de roteamento para CLAUDE.md
│   ├── bin/                    bootstrap, homologação e verificação
│   └── README.md, HOMOLOGACAO.md, COMECE-AQUI.md
├── codex/                  variante Codex (configuração ativa em ~/.codex/agents)
│   ├── agents/                 os 7 agentes em formato TOML
│   └── README.md               instalação e limites específicos do Codex
├── opencode/               variante OpenCode (versão ativa na estação)
│   └── agent/                  os 7 agentes em formato mode: subagent
├── history/                versões históricas
│   └── willtech-general.pre-comercial.md   (v1: executor técnico)
├── INSTALL.md              orientações de instalação por plataforma
└── HISTORICO.md            linhagem das versões
```

## Diferenças entre plataformas

| Aspecto | Claude Code (`claude-code/`) | OpenCode (`opencode/`) | Codex (`codex/`) |
|---|---|---|---|
| Formato | Frontmatter Markdown | Frontmatter Markdown | TOML |
| Delegação | Ferramenta `Agent` | Ferramenta `subagent` | Ferramenta de subagentes do runtime |
| Instalação | `~/.claude/agents/` | `~/.config/opencode/agent/` | `~/.codex/agents/` |
| Permissões | Ferramentas por agente | Permissões declaradas por agente | `developer_instructions` |

O comportamento hierárquico é idêntico; muda apenas o formato de registro dos agentes.

## Status

- Snapshot canônico da arquitetura em uso na estação WILLTECH (Novembro/2026).
- Os arquivos em `opencode/agent/` refletem os agentes ativos, exceto pela
  assinatura de autoria adicionada no final de cada arquivo.
- Os arquivos em `codex/agents/` refletem os agentes ativos em `~/.codex/agents/`.
- `INSTALAR.command` é citado nos documentos originais mas não consta neste snapshot;
  a instalação oficial documentada é via `bin/willtech-bootstrap.sh` (ver INSTALL.md).

## Licença e autoria

Conteúdo autoral **WILLTECH-BH** (conta GitHub: `hebwil`), uso privado — assinatura
completa em [NOTICE.md](NOTICE.md). Componentes externos (EGM, TokenEconomizer)
pertencem a seus respectivos autores e são citados apenas como integrações.

---

## Créditos

A hierarquia de comando desta arquitetura (comandante → coordenador → especialistas)
foi concebida de forma independente pela WILLTECH-BH. Referência de inspiração no
paradigma de orquestração hierárquica de múltiplos agentes:

- **[Multi-Agent Shogun](https://github.com/yohey-w/multi-agent-shogun)** —
  orquestração hierárquica estilo samurai (Shogun → Karo → Ashigaru) por
  [yohey-w](https://github.com/yohey-w). A WILLTECH-BH agradece a referência pública;
  nenhum código deste repositório provém desse projeto.

Outros componentes externos citados: [Elephant Goldfish Model](https://github.com/google/elephant-goldfish-model)
(revisão independente) e [TokenEconomizer](https://github.com/microsoft/TokenEconomizer)
(economia de tokens) — autoria de seus respectivos donos.
