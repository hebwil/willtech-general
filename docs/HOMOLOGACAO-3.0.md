# Homologação WillTech 3.0 — Shared Intelligence (relatório final da missão)

Data: 2026-11-17 · Worktree: `/Users/will/Documents/willtech-general-30-shared-intelligence` · Branch: `qoder/shared-intelligence`

Este relatório distingue categorias sem confusão: **teste determinístico** (unittest/subprocess, labs git descartáveis, sem modelo/rede), **smoke de distribuição** (bancadas node/navegador com host simulado — os próprios benches declaram `simulation:true`), **integração real** (núcleo do hook alimentado com eventos nativos dos 3 formatos, em subprocess) e **homologação nativa** (runtime oficial executando com gasto de modelo). Nenhuma categoria é apresentada como outra.

## Matriz objetiva (§14)

| Área | Resultado | Teste real | Evidência |
|---|---|---|---|
| Sala compartilhada | RESOLVIDO | `tools/test-room.py` (53) + `tools/test-room-v3.py` (34) | init `user_version=3`, put idempotente, isolamento por projeto exit 2, orçamento 1200 aplicado pela ferramenta, QUARENTENA, neutralização |
| Handoff persistente | RESOLVIDO (BL1) | `test-room-v3.py::BL1ResultPersistence` + `tools/test-handoff.py` (11) | `result`/`result_hash`/`knowledge_version` gravados; processo NOVO recupera o resultado exato via `handoff-fetch`; pack do revisor sem o result do executor (asserção mecânica de ausência) |
| Validação de conhecimento | RESOLVIDO (BL2) | `test-room-v3.py::BL2ValidationCycle` | `pending→validated/rejected/expired`; evidência suficiente + autoridade (`reviewer/tester/general`); idempotência; transição inválida exit 2; 4 processos concorrentes; persistência após restart; `validate` de registros candidate/stale |
| Segurança estrutural | RESOLVIDO (BL4) | `test-room-v3.py::BL4StructuralSecurity` + `test-room.py` | allowlists (kinds/specialties/owners/validadores), tetos por campo e lista, caminhos relativos validados (`..`/absoluto/`~` recusados), charset de evidence-hash, trace ≤5 MiB; 12 formatos de segredo SINTÉTICO recusados sem eco (JSON, JWT, URL, Authorization, query, `=`, `:`, chave privada, AKIA, ghp_); export sem vazamento |
| Concorrência SQLite | RESOLVIDO | `test-room-v3.py::BL3Portability` | 8 processos × put e 4 × validate sem perda; `integrity_check=ok`; lock portável `BEGIN IMMEDIATE` em sidecar SQLite (sem fcntl/msvcrt); WAL + busy_timeout |
| Windows/FTS5 fallback | IMPLEMENTADO E TESTADO (simulação); nativo Windows pendente | `test-room-v3.py::BL3Portability` + `tools/test-compat.py` (22) | consulta REAL sem FTS5 (`WILLTECH_ROOM_NO_FTS5=1`): hits, ranking por termos, orçamento, skill validada via LIKE; backfill em runtime capaz; fonte sem `import fcntl`/`msvcrt`; workflow `.github/workflows/windows-compat.yml` pronto (disparo manual — push proibido nesta missão) |
| Consulta JIT | RESOLVIDO | `tools/test-jit.py` (12 — os 10 critérios do §5) | `query_text` REAL + núcleo REAL do hook (`willtech-auto.py` em subprocess com eventos nativos): init, conhecimento registrado, consulta correta, pending NÃO injetado, validated injetado, orçamento (150/400/1200), outro projeto isolado, falha da sala não derruba o app, falha explícita não silenciosa; regressão BL-1 (`path=`) |
| Sete agentes | PRESERVADO | `opencode/tests/test-wrappers.sh` (41) + `tools/test-plan.sh` (33) + `tools/test-homolog.py` (61) | roster e permissões intactos (teste de mutação detecta inversão); sala é dado, nunca autoridade; revisor recebe pack independente sem conclusões do executor |
| OpenCode | INTEGRAÇÃO DETERMINÍSTICA OK; homologação nativa 3.0 pendente | `tools/test-auto.sh` (42, incl. simulação do plugin V2 em node real v24.22.1) + wrappers (41) + `test-jit.py` (formato opencode) + `tools/test-gui-install.py` (9 — ativação GUI reversível, preservação de terceiros) | runtime `opencode` AUSENTE neste ambiente; homologação nativa 2.2.6 em `AUDITORIA.md` é histórica, não se estende à 3.0 |
| Claude Code | INTEGRAÇÃO DETERMINÍSTICA OK; homologação nativa pendente | `test-auto.sh` + `test-jit.py` (formato claude) + `tools/test-claude.py` (4) | CLI 2.1.326 presente, porém headless devolve `Not logged in · Please run /login` (evidência real, custo US$0); login pessoal não executado (proibido); integração Mod existente preservada (guard de orquestração passa) |
| Codex | INTEGRAÇÃO DETERMINÍSTICA OK; homologação nativa pendente | `test-auto.sh` (formato codex, PostToolUseFailure→candidata) + `test-jit.py` (formato codex) + `codex/willtech-visual/tools/test-codex.py` (12 — loopback, reset por sessão, hooks portáveis, node real) | runtime `codex` AUSENTE; protocolo REAL do app-server (`test-appserver.py`) SKIP honesto: binário `WILLTECH_CODEX_BIN` indisponível (runtime de artifact-sessions contém apenas node) |
| Smoke ponta a ponta | RESOLVIDO | `tools/test-smoke-e2e.py` (6) + `tools/test-install.py` (16) + `test-room-v3.py` (backup/restore/falha) | init limpo; banco v1 FRESCO migrado a v3 com dados; restart; 2+ processos; handoff completo; validação/rejeição; JIT; invalidação por mudança de código; isolamento; injeção; segredos sintéticos; falha de banco simulada; recuperação/backup verificado; export sem vazamento; desativação/reativação pelo gate `enabled`; atualização de instalação anterior (test-install); imports = stdlib (scan AST) |
| Benchmark de tokens | NÃO MEDIDO (bloqueio técnico) | `tools/willtech-compare.py` verificada por `tools/test-compare.py` (7) + `test-auto.sh` (fixtures sintéticas — teste da FERRAMENTA, não benchmark) | 0 execuções de cada lado: nenhum runtime nativo autenticado disponível; AMOSTRA INSUFICIENTE declarada; nenhum percentual reivindicado; gasto real US$0,00 de orçamento US$2,00; evidências: `tools/smoke-evidence/bench-3.0-nao-medido.json` e `bench-final-nao-medido.json` |
| Regressão completa | 567 verificações + 2 bancadas node, 0 falhas, 1 SKIP honesto | todas as suítes acima, rodada consolidada única pós-integração | macOS arm64 nativo (categoria determinística); bancadas navegador em Chromium headless real (44+64+3, host simulado — bundle byte-idêntico pós-merge, provado por `test_reproducible_bundle`/`test_original_asset_bytes`) |
| Integração multiplataforma | RESOLVIDA | cherry-picks `fb69f10`/`e2e13ae`/`e8cae91` + guard `test-gui.py` (4) + smoke final integrado | linha `qoder/multiplataforma-integracao` (b1a51c9, 586dfb6, 99c608d) integrada sem perda; conflito do guard resolvido (escopo refinado deles + pin 3.0 nosso); `tools/smoke-evidence/smoke-final-integrado.json` |

## Branch e commits

- Branch: `qoder/shared-intelligence` (worktree isolado; base histórica preservada — nenhum commit anterior apagado/reescrito).
- Novos commits locais (sem push, sem merge na main, sem release):
  - `c0bf5f7` feat(room): fecha BL1-BL4 da missão final 3.0 (núcleo da sala).
  - `9a55312` test(room): suítes v3 (34), JIT funcional (12) e smoke E2E (6).
  - `55b92e8` fix(test): higiene do lab auto (N2 parcial) e repin da baseline GUI 3.0.
  - `9f6819e` docs(3.0): contrato atualizado, relatório de homologação e evidência do benchmark.
  - `fb69f10` fix(codex): loopback viewer, scoped SessionEnd reset, portable plugin hooks (cherry-pick de b1a51c9, linha multiplataforma).
  - `e2e13ae` feat(opencode): portable reversible GUI activation + distribution tests (cherry-pick de 586dfb6; conflito em `tools/test-gui.py` resolvido: escopo orchestration/visual refinado da linha multiplataforma + pin `475943a` da baseline 3.0 aprovada — o pin `ece7429` original falharia na árvore consolidada porque a 3.0 evoluiu legitimamente `opencode/AGENTS.md` e `tools/willtech-auto.py`).
  - `e8cae91` docs: multiplatform homologation report and evolution round (cherry-pick de 99c608d; `HOMOLOGACAO-MULTIPLATAFORMA.md` + `EVOLUCAO.md`).
  - Commit final: fix de caminho pessoal hardcoded no `test-appserver.py`, evidências do smoke final/benchmark e atualização deste relatório.

## Defeitos corrigidos nesta sessão

1. **BL1** — `handoff-record --result` era descartado; agora persistido com hash e versão de conhecimento, recuperável em processo novo.
2. **BL2** — `validation_state` sem transições; agora ciclo explícito com evidência + autoridade, idempotência e recusa de transição inválida; handoffs fora do canal JIT automático.
3. **BL3** — dependência Unix-only (`fcntl`) eliminada do núcleo da sala (lock via transação SQLite); fallback sem FTS5 era só documentado — agora implementado e testado de ponta a ponta.
4. **BL4** — segurança estrutural adicionada (allowlists, tetos, caminhos, owners, charset, limites de trace/import); detector estendido aos formatos conhecidos (JSON, `:`, Authorization, URL, query, JWT, chave privada) como defesa ADICIONAL, sem ciclo infinito de regex.
5. **Backup sem verificação / sem restore** — backup pela API `sqlite3.backup` com integrity_check NA CÓPIA; comando `restore` com backup de segurança do estado atual.
6. **`query_text` não era fail-open em erro de banco** — exceção propagava para o chamador; agora falha de banco devolve None (nada injetado, app não cai), coerente com o contrato documentado.
7. **Invalidação por mudança de código inexistente** — status `stale` era inalcançável; agora source_hash divergente (ou arquivo removido) marca stale e exclui da injeção; re-put + validate restaura.
8. **Falha latente na simulação node do plugin V2** (`test-auto.sh`) — o teste de linha corrompida deixava o dossiê parcialmente corrompido; a simulação recebia o bloqueio de corrupção (correto, N2) em vez da guarda de loop. Corrigido com asserção explícita do fail-closed parcial + reparo do lab; simulação agora executa real (sem SKIP).
9. **Pin obsoleto no `test-gui.py`** — baseline 2.3 anterior à evolução legítima da orquestração nos commits 3.0 aprovados; repinado para a baseline 3.0 aprovada (`475943a`), mesmo invariante. Na integração, o escopo do guard foi refinado pela linha multiplataforma (subdiretórios visuais fora do guard de orquestração) mantendo o pin 3.0.
10. **Caminho pessoal hardcoded no `test-appserver.py`** (linha multiplataforma) — `NODE` apontava para um runtime pessoal de artifact-sessions; substituído por descoberta portável (`WILLTECH_NODE` > `node`/`nodejs` no PATH), mesmo padrão do `test-codex.py`.

## Testes executados (rodada consolidada única pós-integração)

- Python (unittest, determinístico): test-room 53 · test-handoff 11 · test-room-v3 34 · test-jit 12 · test-smoke-e2e 6 · test-repomap 10 · test-supervisor 10 · test-compare 7 · test-install 16 · test-homolog 61 · test-claude 4 · test-gui 4 · test-gui-install 9 · test-codex 12 (node real) · test-compat 22 verificações.
- Shell (determinístico): test-auto 42 · test-plan 33 · test-dossie 51 · test-drift 8 · test-trace 10 · test-wrappers 41.
- Node (smoke de distribuição): test-smoke.cjs PASS (8 assets, 18 quadros APNG) · test-gui-events.cjs PASS (SDK simulado).
- Navegador (Chromium headless real, host simulado): test-gui.html 44 PASS · test-smoke.html modo full 64 PASS (avanço de quadros provado por WebCodecs; pintura ao vivo suprimida pelo navegador automatizado — declarada no resultado) · modo reduced-motion 3 PASS. Bundle byte-idêntico após o merge (reproducibilidade + bytes de assets reassertados), por isso as bancadas de navegador não foram repetidas.
- Smoke final integrado (clone git descartável, processos reais): instalação limpa → sala v3 → handoff com resultado recuperado em processo novo → JIT → segredo/isolamento/invalidação → hooks (disable/enable, injeção de lição+sala) → GUI install/disable/enable/uninstall com preservação de terceiros → update idempotente → uninstall com `room.db` preservada. Evidência: `tools/smoke-evidence/smoke-final-integrado.json`.
- Total: **567 verificações + 2 bancadas node; 0 falhas; 1 SKIP honesto** (protocolo real do codex-app-server: binário indisponível — não contado como aprovação).

## Falhas e SKIPs reais

- 2 erros de harness no test-smoke-e2e (stderr do export misturado ao JSONL) — corrigidos no teste.
- 1 falha latente no test-auto.sh com node habilitado (higiene do lab, item 8 acima) — corrigida; antes era SKIP por node ausente, agora executa via `NODE_BIN` (Electron helper como node v24.22.1, somente leitura).
- 1 falha pré-existente no test-gui.py (pin obsoleto, item 9) — repin documentado; conflito de integração resolvido sem enfraquecer o guard (escopo deles + pin nosso, 4/4 OK).
- 1 SKIP remanescente: `test-appserver.py` exige `WILLTECH_CODEX_BIN` (binário oficial do codex-app-server); o runtime de artifact-sessions localizado contém apenas `node`. Protocolo real não exercitado — declarado, não aprovado.
- Estado final: nenhuma falha; 1 SKIP declarado.

## Economia efetivamente medida

**Nenhuma.** Zero execuções pagas realizadas (gasto US$0,00 do orçamento de US$2,00); nenhum percentual de economia é reivindicado. A ferramenta de comparação está verificada (testes determinísticos com fixtures sintéticas), mas isso não é benchmark. Reaproveitamento de transcrições existentes avaliado: `HOMOLOGACAO-MULTIPLATAFORMA.md` declara LO (sessão real com modelo não homologada) e os labs opencode 2.2.6 anteriores não têm contraparte 3.0 — par comparável impossível. Causa e evidências: `tools/smoke-evidence/bench-3.0-nao-medido.json` e `bench-final-nao-medido.json` (probe claude 2.1.326 com `--max-budget-usd 0.05` → `Not logged in`, custo 0).

## Limitações restantes

1. Homologação nativa 3.0 pendente em OpenCode, Claude Code e Codex (runtimes ausentes/não autenticados). Integração determinística nos 3 formatos existe e passa; não é homologação nativa.
2. Benchmark real não medido (consequência direta de 1).
3. Windows e Linux sem execução nativa nesta sessão — portabilidade sustentada por simulação (test-compat, fallback FTS5 real via env) e workflow CI pronto; código portável ≠ execução nativa comprovada.
4. Detector de segredos é heurístico para formatos DESCONHECIDOS; a proteção primária é estrutural (minimização + allowlists + neutralização).
5. Bancadas GUI rodam com host simulado (navegador real, não OpenCode Desktop); homologação nativa do painel segue declarada NÃO TESTADA pelos próprios benches.

## Veredito final

**NÃO PUBLICÁVEL.**

Integração (§8 da missão final): as DUAS linhas estão consolidadas em `qoder/shared-intelligence` — nenhuma correção conhecida perdida (Codex loopback/reset/hooks portáveis, ativação GUI reversível do OpenCode, integração Mod do Claude Code preservada pelo guard de orquestração); smoke final integrado e regressão única pós-merge passam; instalação/reversão verificadas em clone descartável.

Critérios do §11 atendidos com evidência: 1–6 (bloqueantes resolvidos, handoff persistente, transições, segurança estrutural, compatibilidade sustentada por testes, consulta JIT real), 8 (smoke completos), 9 (regressão consolidada sem falhas), 11 (instalação/atualização reversíveis — test-install 16 + test-gui-install 9 + smoke final), 12 (documentação coerente — drift 8 PASS), 13 (nenhum defeito bloqueante de código pendente).

Critérios NÃO atendidos (bloqueio técnico de ambiente, não de código):
- **7** — integração homologada nativamente nas superfícies declaradas: impossível sem runtime oficial autenticado.
- **10** — benchmark real documentado: impossível nas mesmas condições.

Causa raiz única: nenhum runtime nativo autenticado disponível (`claude` headless → `Not logged in`; `opencode`/`codex` ausentes; configs de provedor em labs descartáveis bloqueadas pela política de segurança do ambiente; login/credenciais pessoais não tocados — proibidos pela missão). Tentativas reais registradas: smoke headless do claude (evidência gravada), busca de binários em 7 locais, inspeção do instalador oficial do opencode para ambiente descartável.

**Caminho de desbloqueio** (para o proprietário, sem alterar o código): autenticar o `claude` (`/login`) OU instalar `opencode`/`codex` em ambiente descartável com provedor autorizado; então executar as suítes de integração nos runtimes oficiais e o benchmark com `tools/willtech-compare.py --repeat 3 --baseline ... --optimized ...` (mesma tarefa/modelo/fixture, orçamento limitado). O código 3.0 está pronto e provado na categoria determinística; o que falta é evidência nativa, não implementação.

Restrições da missão cumpridas: sem `git push`, sem merge na `main`, sem release, sem alteração em instalação pessoal, credenciais, Bifrost, pools, modelos, MCPs, VPS ou produção; histórico de commits anterior preservado.