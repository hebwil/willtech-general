# Design — WillTech-General 3.0 "Shared Intelligence"

**Data:** 2026-11-16 · **Base:** `main` (`ece7429`) · **Branch:** `qoder/shared-intelligence` (worktree isolado) · **Status:** implementado (Passos 0.5–6) — pendências declaradas em `docs/SHARED-INTELLIGENCE.md` §Limitações honestas

## Intent e o porquê

Evoluir o WillTech-General para 7 agentes com UMA inteligência compartilhada local: reduzir tokens, releituras e retrabalho preservando qualidade, segurança e taxa de sucesso. Especialistas sob demanda, memória verificável por evidência, nada de novos agentes nem hierarquia nova. Especificação de origem: missão QODER 3.0 (this conversation) + relatório de Fase 1 (inventário/lacunas) + revisão independente do desenho.

## Goals / Non-goals / Anti-goals

**Goals**
1. Sala dos agentes: SQLite+FTS5, stdlib-only, projeto-local (`.willtech/room.db`), registros tipados (skills, descobertas, decisões, handoffs, referências, pendências), provenance (arquivo+hash) por registro.
2. Consulta just-in-time com orçamento canônico único e FTS5 (projeto×especialidade×arquivos×objetivo).
3. Micro-skills por especialidade com ciclo de vida (evidência→confirmação→descarte) e **gate humano de promoção**.
4. Handoff compacto entre agentes, com **validação mecânica** de que o pack do revisor não contém prosa do executor.
5. Delegação determinística (classificador **advisory**, nunca bloqueante).
6. Benchmark real estendendo `tools/willtech-compare.py` (N execuções, sem percentual inventado).

**Non-goals:** novos agentes; MCP/servidor/semântica remota; amarrar a provedor; substituir guardas/supervisor/dossiê; reescrita dos plugins.

**Anti-goals (falha mesmo funcionando):** segredos no banco; sala como autoridade executável; lições duplicadas dossiê↔sala; injeção de prompt via conteúdo da sala; banco corrompível sem backup.

## Constraints

- Stdlib Python (`sqlite3`, `hashlib`, `argparse`, `pathlib`; locks `fcntl`/`msvcrt` sidecar como hoje).
- Multiplataforma OpenCode/Claude Code/Codex; macOS/Linux/Windows (FTS5 gate no CI Windows).
- Quarentena: header QUARENTENA + neutralização de delimitadores + provenance em toda injeção; dados nunca instruções.
- Reversibilidade: banco aditivo, `--uninstall` intacto, dossiê legado preservado.
- Sem push/merge/release sem autorização.

## Approaches considerados

| Abordagem | Trade-off | Veredito |
|---|---|---|
| **A. Evoluir JSONL do dossiê** com campos novos | Zero risco de migração, mas sem FTS/busca, sem schema versionado, scan linear, sem eixo de especialidade — não atende Req. 1-3 do QODER | Descartada |
| **B. SQLite+FTS5 como sala; dossiê permanece autoridade de lições/attempts; sala = índice derivado reconstruível + dona de entidades novas** | Migration trivial (materialização idempotente, `source_hash`→dossiê); risco: banco binário menos auditável → mitigado com export/dump JSONL periódico | **Escolhida** (revisão independente: aprovada com ajustes) |
| **C. Portar o dossiê inteiro para SQLite** | Fonte única nova, mas quebra guardas/compat 2.0 e duplica verdades durante transição; maior risco | Descartada |

## O desenho (decisões tomadas)

1. **Base:** `main` (`ece7429`) — custo ~zero (`git cherry` = 1 commit de docs na branch antiga). Worktree isolado criado.
2. **Módulo novo:** `tools/willtech-room.py` — dono da sala. Subcomandos implementados: `init`, `put`, `get`, `query` (JIT, `--budget-chars`), `handoff-record/-fetch/-pack`, `skill-add/-promote/-drop/-supersede/-list/-import-candidates`, `export`, `check`. (`migrate`/`rebuild` do índice derivado **não** foram implementados — as lições seguem autoridade do dossiê e a sala é populada por `put`/`skill-add`.)
3. **Schema versionado** (`PRAGMA user_version`), WAL + `busy_timeout`, **lock sidecar `.lock` (nunca `flock` no `.db`)**, backup + `PRAGMA integrity_check` antes de prune/migração. Migração JSONL→SQLite **não destrutiva**: lições continuam autoridade no dossiê; sala materializa índice derivado com `source_hash` e comando `rebuild`.
4. **Consulta JIT:** um único orçamento canônico (unifica `BRIEF_CAP=1200` do hook vs default 1500 do dossiê — achado N5), `--budget-chars` aplicado pela ferramenta, FTS5 com fallback documentado caso o gate Windows falhe (LIKE/índice próprio). Fallback FTS5 (Windows): consulta LIKE + índice próprio, mesma interface.
5. **Injeção segura:** header QUARENTENA + provenance (arquivo+hash) por registro + neutralização de quebras de linha/fences/delimitadores no renderer.
6. **Micro-skills:** nascem `verified:false` (trace já produz candidatas); promoção a auto-load exige evidência verificada + aprovação humana explícita (achado N2); descarte automático quando contraditas.
7. **Handoff:** tabela própria (objetivo, IDs de evidência, arquivos/símbolos, resultado, pendências, próximo responsável, estado de validação); pack do revisor montado **pela ferramenta** a partir de IDs — executor não escreve no pack; validação mecânica por teste.
8. **Delegação:** extensão de `classify_task`/`plan` (main) → `suggested_specialist` advisory; drift estendido para validar especialistas citados contra o roster 7×3.
9. **Integração:** hooks injetam brief da sala no SessionStart e, no prompt, apenas em tarefa não trivial com objetivo derivado do prompt; a sala é opt-in (init manual) — o instalador não a automatiza.
10. **Benchmark:** `willtech-compare.py` estendido (N execuções, agregação, tokens/turnos/loops/releituras) — só números medidos.

## Ordem (alinhada ao QODER + ajuste do revisor) · **Status: 0.5–6 implementados** (delegação advisory via `SPECIALIST_HINTS` no dossiê; compare com N execuções e AMOSTRA INSUFICIENTE) — Fase 9: docs + instalação reversível.

0. base `main` ✅ · 0.5 **gate CI Windows FTS5** (bloqueia congelar schema) · 1. núcleo sala (RED primeiro) · 2. consulta JIT · 3. handoff (paralelizável com 4/5) · 4. micro-skills · 5. delegação determinística · 6. integração + benchmark · 7-10. testes, docs, regressão, revisão independente do delta.

## O que fica para o builder

Nomes exatos de colunas/flags, mensagens de erro, layout do dump JSONL, keyword lists PT/EN do classificador (dados versionados), e o roteiro de benchmark (tarefas representativas do §9 do QODER).
