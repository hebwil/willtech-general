<!--
WILLTECH-GENERAL | PROJECT AUTHORSHIP
Copyright (c) 2026 WILLTECH-BH COMERCIO E SERVICOS LTDA
Project: WillTech-General
GitHub: https://github.com/hebwil/willtech-general
Maintainer: hebwil
Origin: WILLTECH custom multi-agent implementation
-->

<h1 align="center">WILLTECH-GENERAL</h1>

<p align="center">
  <strong>Inteligência Multiagente, Memória Contextual e Orquestração Nativa</strong><br>
  <em>Uma arquitetura. Sete agentes. Inteligência integrada. Um único comando.</em>
</p>

<p align="center">
  <sub>Versão atual: <strong>2.3</strong> (inteligência de orquestração) · Licença MIT · OpenCode V2, Codex e Claude Code</sub>
</p>

<p align="center">
  <img src="docs/assets/willtech-team-banner.webp" alt="Equipe WILLTECH-GENERAL: General ao centro, ladeado pelos seis especialistas" width="100%">
</p>

---

O **WillTech-General** é uma arquitetura open source de orquestração multiagente desenvolvida pela **WILLTECH-BH** para OpenCode, OpenAI Codex e Claude Code.

Combina coordenação especializada, aprendizado baseado em evidências, memória contextual, planejamento inteligente, revisão independente e automação nativa — preservando a autoridade do agente principal de cada plataforma.

Incorpora mecanismos próprios inspirados em conceitos do Microsoft TokenEconomizer e do Google Elephant-Goldfish Model, sem exigir a execução desses frameworks externos.

O resultado é uma arquitetura projetada para reduzir retrabalho, evitar loops, melhorar decisões e oferecer execução supervisionada com evidências verificáveis.

---

## Inteligência integrada

A partir das versões **2.0 → 2.3**, a arquitetura deixou de ser apenas hierarquia de delegação e passou a incorporar mecanismos determinísticos de inteligência operacional, acionados pelos hooks e plugins nativos de cada runtime:

| Capacidade | O que faz | Estado |
|---|---|---|
| 🧠 **Memória de experiências** | Lições registradas com comando + hash SHA-256 da saída real; nunca conteúdo de arquivo. Recusa caminhos de credenciais na entrada | ✅ Homologada |
| 🔄 **Aprendizado entre sessões** | Confirmação progressiva, contradição marca a lição antiga como `superseded`, invalidação por commit; `prune` automático descarta o que envelheceu | ✅ Homologada |
| 📦 **Cache contextual por projeto e commit** | Mapa de contexto com chave `HEAD + working tree`; escopo seletivo por caminhos — sujeira fora do escopo não invalida o cache | ✅ Homologada |
| 📋 **Brief contextual** | Contexto essencial injetado automaticamente no início de tarefas complexas; tarefa simples não recebe overhead | ✅ Homologada |
| 🗺️ **Planejamento com evidências** | Requisito → decisão → implementação → teste rastreáveis no dossiê; decisões entram com evidência em hash | 🧪 Validada em simulação |
| 🐟 **Revisão independente seletiva (Goldfish)** | Revisor em contexto fresco, acionado só em mudança crítica, arquitetural ou de segurança; uma rodada por padrão, sem herdar conclusões do implementador | 🧪 Validada em simulação |
| ⛔ **Controle determinístico de loops** | Terceira tentativa do mesmo comando falho é negada pelo runtime; registrar a lição verificada libera a guarda; sem juiz LLM, sem custo de modelo | ✅ Homologada |
| 🎯 **Seleção proporcional de especialistas** | Tarefa simples fica com o comandante; delegação declara apenas os recursos necessários — sem desativação automática de ferramentas | 🧪 Validada em simulação |
| 🛡️ **Proteção anti-injection e anti-vazamento** | Conteúdo de web/docs é dado, nunca instrução; segredos do trace são redigidos; dossiê corrompido bloqueia o controle (falha fechado) | ✅ Homologada |
| 🔍 **Detecção de drift** | Gate determinístico entre código, decisões e documentação: README ↔ arquivos, contratos ↔ subcomandos, decisões sem evidência | ✅ Homologada |
| ⚙️ **Automação nativa por hooks/plugins** | SessionStart, PreToolUse, Stop e afins do Claude Code e Codex; plugin V2 no OpenCode — zero chamadas de modelo, zero comandos manuais | 🧪 Validada em simulação |
| 🔧 **Instalação reversível** | Idempotente, projeto-local, com consentimento, backup, `--disable` e `--uninstall` que restaura o estado anterior | ✅ Homologada |
| 🐘 **Elephant/Goldfish determinístico** | `tools/willtech-dossie.py plan` classifica complexidade (DIRECT/PLAN/PLAN+REVIEW); `review-pack` entrega diff + aceite + evidências sem conclusões do executor; `resolve` classifica críticas com evidência; `catalyst` limita a exploração a uma alternativa após impasse | 🧪 Validada em simulação |
| 🗺️ **RepoMap incremental compartilhado** | `tools/willtech-repomap.py` indexa símbolos/dependências sem copiar conteúdo; reparse só do que mudou; briefings substituem releituras; trechos revalidados por hash; isolamento por projeto e exclusão de credenciais | 🧪 Validada em simulação |
| ⏱️ **Supervisor de delegações** | `tools/willtech-supervisor.py` rastreia cada delegação com soft/hard timeout, bloqueia recursão/duplicação/escrita concorrente, retry único reconciliado; timed_out nunca afirma interrupção; cancelamento só com confirmação do runtime | 🧪 Validada em simulação |

> **Nota de rigor:** nenhum percentual de economia de tokens é afirmado. A comparação com/sem otimizações (`tools/willtech-compare.py`) mede deltas de tokens, turnos, falhas e loops sobre transcripts reais, sem extrapolar métricas. A homologação da automação em runtime real (com gasto de modelo) permanece pendente e não é anunciada como concluída — classificação completa e evidências em [EVOLUCAO.md](EVOLUCAO.md).

### As três melhorias da rodada 2.3 (integradas na `main` via [PR #9](https://github.com/hebwil/willtech-general/pull/9))

1. **Planejamento seletivo Elephant/Goldfish com revisão independente** — `tools/willtech-dossie.py plan` classifica a tarefa por heurísticas determinísticas (DIRECT / PLAN / PLAN+REVIEW): tarefas simples executam direto; tarefas complexas exigem plano escrito com critérios de aceite; mudanças críticas/arquiteturais/de segurança acionam o Revisor em contexto fresco (`review-pack` entrega diff + aceite + evidências, sem conclusões do implementador). `resolve` classifica críticas com evidência em hash e `catalyst` limita a exploração a uma alternativa após impasse. Sem juiz LLM, sem custo de modelo.
2. **RepoMap incremental compartilhado** — `tools/willtech-repomap.py` mantém um índice de símbolos e dependências por hash de conteúdo: reparse apenas do que mudou, renames reaproveitam símbolos, isolamento por projeto e exclusão de credenciais. **Medição real em bancada** (fixture de 10 arquivos): leitura integral 380 bytes (~95 tokens estimados) vs briefing de 256 bytes (~64); parses na primeira rodada = 10, rodadas seguintes sem mudanças = 0. Valores medidos no cenário de teste, não extrapolados como percentual.
3. **Supervisor determinístico de delegações** — `tools/willtech-supervisor.py` registra cada delegação com soft/hard timeout honestos (`timed_out` nunca afirma interrupção sem confirmação), cancelamento somente com confirmação do runtime, anti-loop (recursão, duplicação e escrita concorrente bloqueadas) e retry único reconciliado. Estado e evidências ficam no dossiê (hashes, nunca conteúdo).

As três melhorias reutilizam o núcleo existente (dossiê, trace, guardas) e preservam os 7 agentes, hooks, instaladores e contratos das três plataformas (contratos 2.3 / 2.3.1 / 2.3.2). Validação por suítes determinísticas de laboratório; homologação em runtime real com modelo permanece pendente e não é anunciada como concluída.

---

## Arquitetura e hierarquia

```text
               COMANDANTE NATIVO
           Claude Code | Codex | OpenCode
                       |
                       v
                WILLTECH-GENERAL
      Coordenação, memória, guardas e evidências
                       |
        +--------------+--------------+
        |              |              |
        v              v              v
     ANÁLISE       IMPLEMENTAÇÃO    QUALIDADE
        |              |              |
   Explorador        Executor       Testador
   Pesquisador                       Revisor
   Visual
```

**Nível 1 — Comandante.** O agente principal da plataforma permanece responsável pelas decisões, autorizações, escopo e entrega final.

**Nível 2 — WillTech-General.** Recebe tarefas complexas, identifica dependências, organiza etapas, seleciona especialistas, acompanha resultados e consolida evidências. Não assume o controle da sessão nem substitui o comandante.

**Nível 3 — Especialistas.** Seis agentes com responsabilidades específicas. A arquitetura prioriza delegação seletiva, evitando mobilizar toda a equipe para operações simples.

### O coordenador

<p align="center">
  <picture>
    <source media="(prefers-reduced-motion: reduce)" srcset="docs/assets/willtech-general-static.webp" type="image/webp">
    <source srcset="docs/assets/willtech-general-animated.apng" type="image/apng">
    <img src="docs/assets/willtech-general-animated.gif" alt="WillTech-General: robô navy com clipboard holográfico e pulso de luz no emblema" width="300">
  </picture>
</p>

---

## Equipe dos sete agentes

<table>
  <tr>
    <td align="center" width="33%">
      <img src="docs/assets/willtech-explorador.webp" width="210" alt="Explorador: robô verde com lupa e scanner"><br>
      <strong>Explorador</strong><br>
      <sub>Análise estrutural de código, dependências e reconhecimento de repositórios</sub>
    </td>
    <td align="center" width="33%">
      <img src="docs/assets/willtech-pesquisador.webp" width="210" alt="Pesquisador: robô roxo com livro e documentos"><br>
      <strong>Pesquisador</strong><br>
      <sub>Investigação técnica, bibliotecas, documentação e requisitos</sub>
    </td>
    <td align="center" width="33%">
      <img src="docs/assets/willtech-visual.webp" width="210" alt="Visual: robô ciano com stylus e paleta"><br>
      <strong>Visual</strong><br>
      <sub>Engenharia de interfaces, UX, acessibilidade e análise visual</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <img src="docs/assets/willtech-executor.webp" width="210" alt="Executor: robô laranja com chave e engrenagens"><br>
      <strong>Executor</strong><br>
      <sub>Implementação controlada de alterações autorizadas</sub>
    </td>
    <td align="center">
      <img src="docs/assets/willtech-testador.webp" width="210" alt="Testador: robô amarelo com checklist e painel"><br>
      <strong>Testador</strong><br>
      <sub>Validação funcional, testes automatizados e investigação de falhas</sub>
    </td>
    <td align="center">
      <img src="docs/assets/willtech-revisor.webp" width="210" alt="Revisor: robô prata com lupa e clipboard"><br>
      <strong>Revisor</strong><br>
      <sub>Revisão independente, qualidade, arquitetura e regressões</sub>
    </td>
  </tr>
</table>

Cada agente possui um contrato operacional, com responsabilidades, limites e critérios de entrega. O modelo de permissões depende das capacidades e configurações de cada runtime — as restrições são verificadas tecnicamente, não apenas declaradas nos prompts.

---

## Compatibilidade e homologação

### Sistemas operacionais

| Sistema | Estado | Condição objetiva |
|---|---|---|
| **macOS** | Validado | Suítes determinísticas e smoke tests exercitados em macOS (arm64). Os wrappers de sandbox do OpenCode usam `sandbox-exec`, exclusivo do macOS |
| **Linux** | Não validado nesta estação | Código Unix (python3 stdlib + shell POSIX + git, com `fcntl` disponível em Linux). Requisitos: python3, git, sh. Sem ambiente Linux disponível para exercício; o sandbox `sandbox-exec` dos wrappers não se aplica |
| **Windows nativo** | Núcleo homologado; instalador homologado na versão `c70e5e8` | [Workflow nativo aprovado](https://github.com/hebwil/willtech-general/actions/runs/43892063828): `msvcrt.locking` 22/22 (8 processos × 25, anti-loop, hooks das 3 plataformas, `.env` recusado) e ciclo PowerShell 5.1 completo: backup, merge preservando configurações, idempotência, disable/enable/uninstall, caminho Unicode e integridade dos arquivos. Wrappers `sandbox-exec` não instalados — shell dos agentes segue restrito pelo runtime. Runtimes de IA em Windows não homologados por este teste |
| **Windows via WSL** | Não validado | Caminho Linux dentro da distribuição WSL (python3, git, sh; instalador `sh` utilizável). Sem ambiente Windows/WSL disponível para exercício; mesmas condições do Linux |

As três integrações de IA abaixo são independentes do sistema operacional: cada uma usa os mecanismos nativos do seu runtime.

### Plataformas de IA

| Plataforma | Agentes | Delegação hierárquica | Hooks / plugins (2.2.1) | Memória, revisão e controle de loops | Isolamento por agente |
|---|---|---|---|---|---|
| **OpenCode V2** | Subagentes Markdown + wrappers sandbox + plugin V2 | Delegação real comprovada; tarefa DeepSeek não homologada (leitura rejeitada) | Plugin V2 nativo | Contratos ativos; automação validada em simulação | Aplicado pelo runtime (2.2.6) |
| **OpenAI Codex** | Agentes nativos em TOML | Validada em runtime real | Hooks projeto-local com trust via `/hooks` | Contratos ativos; automação validada em simulação | Instrucional (limitação do runtime) |
| **Claude Code** | Subagentes Markdown + templates de hooks | Pacote implementado; homologação de runtime pendente | Templates de hooks com `onFailure: block` | Contratos ativos; automação validada em simulação | Depende dos controles do runtime |

**Terminologia:** *homologada em runtime real* indica execução comprovada em sessão autenticada com evidência registrada; *validada em simulação* indica comportamento exercitado por suítes determinísticas sobre contratos verificados na documentação oficial, com homologação em runtime ainda pendente; *implementado* indica o componente presente no pacote, pronto para homologação.

A estrutura conceitual é compartilhada; os mecanismos de delegação, execução e controle de permissões variam entre plataformas. A classificação completa, com evidências e limitações técnicas, está em [EVOLUCAO.md](EVOLUCAO.md).

---

## Comece aqui

**Pré-requisitos:** um dos runtimes suportados (OpenCode V2, Codex ou Claude Code) e `git`. As ferramentas de inteligência usam apenas a biblioteca padrão do Python 3 — sem dependências externas e sem custo de modelo. Os comandos abaixo são Unix (`sh`): executam em macOS, Linux e dentro do WSL, **não diretamente no PowerShell/Windows nativo** (condições por sistema na seção Compatibilidade).

### OpenCode V2 (variante homologada no runtime 2.2.6)

```sh
# 1. Backup
STAMP=$(date +%Y%m%d-%H%M%S)
mkdir -p ~/.willtech-backups/opencode-$STAMP
cp -a ~/.config/opencode/agent ~/.willtech-backups/opencode-$STAMP/

# 2. Instalar agentes, wrappers e política do comandante
cp opencode/agent/*.md ~/.config/opencode/agent/
mkdir -p ~/.config/opencode/bin && cp opencode/bin/* ~/.config/opencode/bin/
chmod +x ~/.config/opencode/bin/*
cp opencode/AGENTS.md ~/.config/opencode/AGENTS.md

# 3. Requisito para delegação aninhada (mesclar, sem sobrescrever o resto)
#    { "experimental": { "subagent_depth": 2 } }  em ~/.config/opencode/opencode.json

# 4. Reiniciar a sessão e verificar
opencode debug agents
sh opencode/tests/test-wrappers.sh   # regressão sem custo de modelo
```

### OpenAI Codex

```sh
mkdir -p ~/.codex/agents
# Backup apenas se já existirem agentes (instalação limpa não tem o que copiar)
if [ -n "$(ls -A ~/.codex/agents 2>/dev/null)" ]; then
  cp -a ~/.codex/agents ~/.codex/agents.backup-$(date +%Y%m%d-%H%M%S)
fi
cp codex/agents/*.toml ~/.codex/agents/
# Reinicie a sessão e confirme os sete nomes willtech-*
```

### Claude Code

```sh
mkdir -p ~/.claude/agents
# Backup apenas se já existirem agentes (instalação limpa não tem o que copiar)
if [ -n "$(ls -A ~/.claude/agents 2>/dev/null)" ]; then
  cp -a ~/.claude/agents ~/.claude/agents.backup-$(date +%Y%m%d-%H%M%S)
fi
cp -a claude-code/agents/. ~/.claude/agents/
```

> A variante Claude Code está implementada e pronta para uso; a homologação de delegação em runtime segue o mesmo protocolo aplicado às demais plataformas. Detalhes em [INSTALL.md](INSTALL.md).

### Automação nativa 2.2.1 (opcional, projeto-local, com consentimento)

```sh
sh tools/willtech-install.sh            # lista as mudanças e pede confirmação
sh tools/willtech-install.sh --platform opencode   # apenas uma plataforma
sh tools/willtech-install.sh --uninstall           # reverter com restauração de backups
```

Escreve **apenas dentro do repositório alvo** (`.claude/`, `.codex/`, `.opencode/`, `.willtech/`); as telas oficiais de trust/permissão de cada plataforma continuam valendo.

**Desativação e reversão:** `--disable` remove somente `.willtech/enabled`; `--uninstall` remove apenas handlers registrados pelo instalador e restaura os backups dos componentes, inclusive do plugin. Arquivos de terceiros, configurações acrescentadas depois, dossiê/cache e diretórios preexistentes são preservados. Componentes sem registro de posse ou plugins modificados pelo usuário não são apagados. Detalhes de distribuição por projeto e reversão em [INSTALL.md](INSTALL.md).

**Delegação DeepSeek — evidência parcial:** no OpenCode Desktop 2.2.6, o comandante acionou o General e este chamou o Explorador real por `subagent`, recebendo seu retorno de erro. A leitura foi rejeitada por `permission.rejected` no cliente não interativo; o processo terminou por timeout de 60 segundos. Isso comprova comunicação real, **não homologação completa da tarefa**. Profundidade 2 e permissões corretas não substituem a aprovação oficial do runtime. Registros e limitações em [EVOLUCAO.md](EVOLUCAO.md).

### Painel visual dos agentes (experimental, opt-in)

Contribuição gráfica independente para **OpenCode Desktop 2.2.6**, baseada na API oficial `@opencode/plugin/gui` e no export `gui-experimental`, integrada na `main` via [PR #8](https://github.com/hebwil/willtech-general/pull/8). Reutiliza os **sete mascotes originais** e exibe cinco estados por agente — **Aguardando, Coordenando/Executando, Concluído, Erro e Interrompido/Bloqueado** — observando apenas eventos nativos de execução, sem acionar agentes nem modelos. Ativação exige opt-in explícito (`enabled: true`), superfície desktop e versão compatível; respeita `prefers-reduced-motion`, oferece pausa reversível e fallback estático WebP, e limpa todas as inscrições no unmount/desconexão. Não altera os hooks nem é instalada pelo instalador de automação.

**Smoke headless de laboratório aprovado com o bundle real e os mascotes originais:** 64/64 verificações em três rodadas consecutivas + 3/3 em modo reduced-motion — carga das sete imagens, associação agente↔imagem por hash SHA-256, avanço de quadros do APNG provado por decodificação WebCodecs (18 quadros), estados, isolamento de eventos do General, deduplicação de atualizações, limpeza pós-unmount e zero chamadas de rede/modelo (evidência de rede: apenas `file://` e `data:`). Resultados, hashes e capturas de tela em [tools/smoke-evidence/](tools/smoke-evidence/).

**Homologação gráfica nativa no OpenCode Desktop: NÃO EXECUTADA.** O smoke é simulação de laboratório em navegador headless e não é anunciado como suporte nativo validado. Ativação, reversão e limites de Codex/Claude Code em [INSTALL.md](INSTALL.md#painel-visual-experimental-opencode-desktop).

### Smoke tests dos adaptadores

Os três adaptadores da `main` passaram em smoke tests mínimos com **código real publicado**: plugin/hooks carregados, núcleo Python executado e bloqueio anti-loop comprovado — a terceira tentativa idêntica é negada após duas falhas (OpenCode V2 via `throw` no plugin; Codex e Claude Code via JSON `deny` no contrato de hooks). Os testes simulam apenas o ambiente externo e os eventos; **não constituem homologação em sessão real com modelo**, que permanece pendente e documentada em [EVOLUCAO.md](EVOLUCAO.md).

---

## Segurança, automação e limitações

O WillTech-General foi concebido com separação de responsabilidades, proteção do escopo autorizado e revisão de resultados. Entretanto, **instruções de agentes não constituem, por si só, isolamento de segurança** — a proteção efetiva depende do runtime e deve ser verificada tecnicamente.

### OpenCode 2.2.6 — isolamento aplicado

No OpenCode, as permissões são ordenadas e a **última regra que casa vence**. Os agentes de leitura negam explicitamente `shell`, `edit`, `subagent`, `execute` e as ferramentas nativas de worktree.

Shell é liberado apenas pelos wrappers:

```sh
~/.config/opencode/bin/willtech-read-shell "COMANDO"
~/.config/opencode/bin/willtech-test-shell "COMANDO"
```

O comando deve ir **inteiro entre aspas duplas**. Sem aspas, o runtime nega a chamada — isso impede que `>`, `;`, `&&` e `|` sejam executados fora do sandbox. O wrapper de leitura bloqueia escrita; o de teste confina escrita a `~/willtech-lab`, bloqueia rede, SSH, `.env` e configurações sensíveis.

### Limitações por plataforma

| Plataforma | Isolamento real | Classificação |
|---|---|---|
| **OpenCode 2.2.6** | Por agente, aplicado pelo runtime + sandbox dos wrappers | Homologado nos testes documentados |
| **Codex** | Instrucional; o TOML não oferece permissão por agente | Limitação do runtime |
| **Claude Code** | Delegado aos controles nativos do runtime | Pendente de homologação |

Matriz completa, testes adversariais e limitações honestas (incluindo lacunas de runtime classificadas como tais) em [AUDITORIA.md](AUDITORIA.md) e [opencode/HOMOLOGACAO.md](opencode/HOMOLOGACAO.md).

---

## Documentação técnica

| Documento | Conteúdo |
|---|---|
| [EVOLUCAO.md](EVOLUCAO.md) | Registro completo das rodadas 2.0 → 2.3 e da publicação final: mecanismos, evidências, o que foi adiado e por quê |
| [AUDITORIA.md](AUDITORIA.md) | Testes de homologação, falhas adversariais e limitações por plataforma |
| [INSTALL.md](INSTALL.md) | Procedimentos completos de instalação, rollback e automação por plataforma |
| [HISTORICO.md](HISTORICO.md) | Linhagem das versões desde o executor técnico pré-comercial |
| [NOTICE.md](NOTICE.md) | Declaração formal de autoria e componentes externos |
| [opencode/HOMOLOGACAO.md](opencode/HOMOLOGACAO.md) | Matriz de permissões e limites dos wrappers sandbox |

**Estrutura principal:**

```text
willtech-general/
├── claude-code/     agentes Markdown, hooks e arnês de homologação (Claude Code)
├── codex/           agentes TOML e hooks projeto-local (Codex)
├── opencode/        agentes, wrappers sandbox, plugin V2, política e testes (OpenCode V2)
├── tools/           dossiê, drift, auto, compare, repomap, supervisor, smoke-evidence e suítes determinísticas (stdlib)
├── docs/assets/     identidade visual: cards e banner WebP, APNG/GIF/estático do General
└── history/         versões históricas da arquitetura
```

Validação direcionada de ativação/reversão e preservação de terceiros: `python3 tools/test-install.py` (shell real + Python embutido do PS1; não é homologação nativa Windows).

Suítes de regressão sem custo de modelo (executadas e aprovadas; registros em [EVOLUCAO.md](EVOLUCAO.md)): `sh tools/test-auto.sh` (39) · `sh tools/test-dossie.sh` (51) · `sh tools/test-drift.sh` (7 + gate de drift 0 divergências) · `sh tools/test-plan.sh` (21) · `sh tools/test-trace.sh` (10) · `python3 tools/test-repomap.py` (10) · `python3 tools/test-supervisor.py` (10) · `sh opencode/tests/test-wrappers.sh` (41) · `python3 tools/test-compat.py` (22, cross-platform: locks com processos concorrentes, recuperação anti-loop, dossiê antigo, hooks das 3 plataformas, falha fechado) · `python3 tools/test-install.py` (16) · `python3 tools/test-gui.py` (4) + eventos do painel em ambas as formas. Smoke headless do painel em navegador: 64/64 (×3 rodadas) + 3/3 reduced-motion, com evidências em [tools/smoke-evidence/](tools/smoke-evidence/).

---

## Desenvolvimento e licença

| | |
|---|---|
| **Projeto** | WillTech-General |
| **Desenvolvimento** | WILLTECH-BH |
| **Mantenedor** | [hebwil](https://github.com/hebwil) |
| **Repositório** | [github.com/hebwil/willtech-general](https://github.com/hebwil/willtech-general) |
| **Licença** | MIT |

O código e os arquivos próprios deste repositório são disponibilizados sob os termos da [Licença MIT](LICENSE), respeitadas as licenças aplicáveis a quaisquer componentes de terceiros.

---

## Créditos e referências

O WillTech-General é uma implementação personalizada da WILLTECH-BH. Os mecanismos de inteligência integrada são implementação própria, inspirados em conceitos públicos de projetos estudados — nenhum código foi copiado:

- [Microsoft TokenEconomizer](https://github.com/microsoft/TokenEconomizer) — conceitos adaptados: micro-skills (como lições verificadas por hash) e seleção econômica de ferramentas.
- [Google Elephant-Goldfish Model](https://github.com/google/elephant-goldfish-model) — conceito adaptado: revisão independente em contexto fresco, acionada seletivamente.
- [Multi-Agent Shogun](https://github.com/yohey-w/multi-agent-shogun), por [yohey-w](https://github.com/yohey-w) — referência de coordenação hierárquica de agentes.

O WillTech-General não é distribuição oficial desses projetos nem possui vínculo com seus mantenedores.

---

**WILLTECH-GENERAL — Engenharia multiagente com comando, especialização e evidências.**
