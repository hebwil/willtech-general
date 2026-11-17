# Homologação WillTech 3.0 — Shared Intelligence (relatório final)

Data: 2026-11-17 · Repositório: `hebwil/willtech-general` · `main`: `c4e593d17394b8070783f04efe4ad7f329201000` (PR #15 merged) · CI final: [run 44140677603](https://github.com/hebwil/willtech-general/actions/runs/44140677603) — **5/5 jobs SUCCESS**.

Este relatório distingue categorias sem confusão: **teste determinístico** (unittest/subprocess, labs git descartáveis, sem modelo/rede), **smoke de distribuição** (bancadas node/navegador com host simulado — os próprios benches declaram `simulation:true`), **integração real** (núcleo do hook alimentado com eventos nativos dos 3 formatos, em subprocess; e carga de plugin/hook em runtime oficial isolado), **CI nativo por SO** (execução real em runners macOS/Linux/Windows) e **homologação nativa com modelo** (runtime oficial autenticado executando com gasto de modelo). Nenhuma categoria é apresentada como outra.

## Estado de publicação

- Histórico reconciliado sem perda: a `main` remota (PR #14, `e311c5e`) foi incorporada por merge (`f26e799`); os três cherry-picks da linha multiplataforma NÃO foram reaplicados (já contidos no PR #14). Branch de segurança `safety/3.0-pre-publicacao` preservada.
- PR #15 (`qoder/shared-intelligence` → `main`) **merged** em `c4e593d`; CI 5/5 aprovado nesse estado.
- Release `v3.0.0`: publicada a partir do commit validado da `main`, com artefatos de distribuição + SHA-256 e verificação de instalação limpa a partir dos arquivos publicados (ver seção Distribuição).

## Matriz objetiva

| Área | Resultado | Teste real | Evidência |
|---|---|---|---|
| Sala compartilhada | RESOLVIDO | `tools/test-room.py` (53) + `tools/test-room-v3.py` (34) | init `user_version=3`, put idempotente, isolamento por projeto exit 2, orçamento 1200 aplicado pela ferramenta, QUARENTENA, neutralização |
| Handoff persistente | RESOLVIDO (BL1) | `test-room-v3.py::BL1ResultPersistence` + `tools/test-handoff.py` (11) | `result`/`result_hash`/`knowledge_version` gravados; processo NOVO recupera o resultado exato via `handoff-fetch`; pack do revisor sem o result do executor |
| Validação de conhecimento | RESOLVIDO (BL2) | `test-room-v3.py::BL2ValidationCycle` | `pending→validated/rejected/expired`; evidência + autoridade; idempotência; transição inválida exit 2; 4 processos concorrentes; persistência após restart |
| Segurança estrutural | RESOLVIDO (BL4) | `test-room-v3.py::BL4StructuralSecurity` + `test-room.py` | allowlists, tetos por campo/lista, caminhos relativos validados, charset de evidence-hash, trace ≤5 MiB; 12 formatos de segredo SINTÉTICO recusados sem eco; export sem vazamento |
| Concorrência SQLite | RESOLVIDO | `test-room-v3.py::BL3Portability` | 8 processos × put e 4 × validate sem perda; `integrity_check=ok`; lock portável `BEGIN IMMEDIATE` em sidecar SQLite (sem fcntl/msvcrt no núcleo da sala); WAL + busy_timeout |
| Windows/FTS5 fallback | IMPLEMENTADO, TESTADO E VALIDADO EM CI NATIVO | `test-room-v3.py::BL3Portability` + `tools/test-compat.py` (22) + CI `windows-latest`/`ubuntu-latest` | consulta REAL sem FTS5 (`WILLTECH_ROOM_NO_FTS5=1`): hits, ranking por termos, orçamento, skill validada via LIKE; sem FTS5 o `init` NÃO falha; passo "Fallback REAL sem FTS5" no CI; `msvcrt.locking` concorrente no Windows nativo |
| Consulta JIT | RESOLVIDO | `tools/test-jit.py` (12 — os 10 critérios do §5) | `query_text` REAL + núcleo REAL do hook (`willtech-auto.py` em subprocess com eventos nativos): init, consulta correta, pending NÃO injetado, validated injetado, orçamento (150/400/1200), outro projeto isolado, falha da sala não derruba o app |
| Sete agentes | PRESERVADO + COMPROVADO NO HOST OFICIAL | `opencode/tests/test-wrappers.sh` (41) + `tools/test-homolog.py` (61) + CI opencode-host | roster e permissões intactos; **7 agentes WillTech `mode=subagent` registrados no host oficial OpenCode 2.3.0** (CI, `/api/agent`) |
| OpenCode | CARGA DE PLUGIN + SessionStart REAIS NO HOST OFICIAL; sessão com modelo pendente | CI opencode-host (OpenCode 2.3.0 oficial) + `tools/test-auto.sh` (42, plugin V2 em node real) + wrappers (41) + `test-jit.py` + `tools/test-gui-install.py` (9) | servidor oficial autenticado (basic), `POST /api/session → 200`, **state-plugin-load.json gerado em .willtech/** (setup do plugin executou o núcleo determinístico real, custo zero); `OK host oficial: 7 agentes WillTech subagent; plugin setup=True` |
| Claude Code | INTEGRAÇÃO DETERMINÍSTICA OK; homologação de runtime pendente | `test-auto.sh` + `test-jit.py` (formato claude) + `tools/test-claude.py` (4) | pacote implementado; CLI headless sem auth devolve `Not logged in` (custo US$0); login pessoal não executado (proibido); integração Mod preservada (guard de orquestração passa) |
| Codex | PROTOCOLO REAL DO APP SERVER COMPROVADO NO CI; sessão com modelo pendente | `codex/willtech-visual/tools/test-appserver.py` + `test-codex.py` (12) no CI + `test-auto.sh`/`test-jit.py` (formato codex) | **binário oficial codex-app-server rust-v0.169.0** baixado da release oficial e exercitado em protocolo real nos 3 SOs (SKIP anterior ELIMINADO); evidência `tools/smoke-evidence/codex-appserver-real.json`; loopback/reset/hooks portáveis em node real |
| Smoke ponta a ponta | RESOLVIDO | `tools/test-smoke-e2e.py` (6) + `tools/test-install.py` (16) + `test-room-v3.py` (backup/restore/falha) | init limpo; banco v1 FRESCO migrado a v3 com dados; restart; 2+ processos; handoff completo; validação/rejeição; JIT; invalidação por mudança de código; isolamento; segredos sintéticos; recuperação/backup verificado; export sem vazamento; gate `enabled`; atualização de instalação anterior; imports = stdlib (scan AST) |
| Benchmark de tokens | NÃO MEDIDO (sem provedor autorizado) | `tools/willtech-compare.py` verificada por `tools/test-compare.py` (7) + `test-auto.sh` (fixtures sintéticas — teste da FERRAMENTA, não benchmark) | 0 execuções de cada lado: nenhum provedor de laboratório expressamente autorizado; AMOSTRA INSUFICIENTE declarada; nenhum percentual reivindicado; gasto real US$0,00 de orçamento US$2,00; evidências `tools/smoke-evidence/bench-3.0-nao-medido.json` e `bench-final-nao-medido.json` |
| Regressão determinística | 567 verificações + 2 bancadas node, 0 falhas | todas as suítes, rodada consolidada única pós-integração (macOS arm64 nativo) | bancadas navegador em Chromium headless real (44+64+3, host simulado — bundle byte-idêntico pós-merge, provado por `test_reproducible_bundle`/`test_original_asset_bytes`) |
| Regressão nativa CI | 5/5 jobs SUCCESS | `.github/workflows/homologacao-3.0.yml` (macOS/Linux/Windows + host oficial OpenCode + smoke inteligência) | [run 44140677603](https://github.com/hebwil/willtech-general/actions/runs/44140677603): suítes portáveis nos 3 SOs, fallback real sem FTS5, protocolo real App Server, suítes shell+instalador (Unix), ciclo PS1 completo (Windows), host oficial OpenCode 2.3.0, smoke inteligência 17/17 |
| Integração multiplataforma | RESOLVIDA | guard `test-gui.py` (4) + smoke final integrado | linha multiplataforma incorporada via PR #14 sem perda; `tools/smoke-evidence/smoke-final-integrado.json` |

## CI nativo por sistema operacional (run 44140677603)

| Job | SO | Resultado | Escopo real |
|---|---|---|---|
| nucleo | macos-latest | SUCCESS | suítes portáveis + fallback sem FTS5 + App Server real + suítes shell/instalador + wrappers `sandbox-exec` integrais |
| nucleo | ubuntu-latest | SUCCESS | suítes portáveis + fallback sem FTS5 + App Server real + suítes shell/instalador (contrato estrutural de permissões; `sandbox-exec` não se aplica) |
| nucleo | windows-latest | SUCCESS | suítes portáveis + fallback sem FTS5 + App Server real + `msvcrt.locking` concorrente + ciclo PowerShell 5.1 completo (backup, merge preservando config do usuário, idempotência, disable/enable/uninstall, caminho Unicode) |
| opencode-host | ubuntu-latest | SUCCESS | OpenCode 2.3.0 oficial; 7 agentes subagent; plugin setup real (state-plugin-load.json); custo zero |
| intelligence-smoke | ubuntu-latest | SUCCESS | smoke integrado da inteligência 3.0 (17 critérios, subprocess real) |

SKIPs condicionais entre SOs são classificados corretamente: os wrappers `sandbox-exec` são exclusivos do macOS e exercitados integralmente no job `macos-latest`; em Linux/Windows o teste declara NOTICE e valida o contrato estrutural de permissões (não é SKIP de requisito obrigatório nem falso PASS). Nenhum requisito obrigatório foi aprovado apenas por simulação ou SKIP.

## Defeitos reais corrigidos na finalização (histórico preservado)

1. **BL1** — `handoff-record --result` persistido com hash e versão, recuperável em processo novo.
2. **BL2** — ciclo de validação explícito com evidência + autoridade, idempotência e recusa de transição inválida.
3. **BL3** — dependência Unix-only (`fcntl`) eliminada do núcleo da sala; fallback sem FTS5 implementado e testado de ponta a ponta.
4. **BL4** — segurança estrutural (allowlists, tetos, caminhos, owners, charset, limites); detector de segredos estendido como defesa ADICIONAL.
5. **Backup/restore** — backup pela API `sqlite3.backup` com integrity_check NA CÓPIA; comando `restore` com backup de segurança.
6. **`query_text` fail-open** em erro de banco (nada injetado, app não cai); controle de loop PreToolUse segue fail-closed.
7. **Invalidação por mudança de código** — source_hash divergente marca `stale` e exclui da injeção; re-put + validate restaura.
8. **Portabilidade Windows real** — `os.fspath` em `willtech-dossie.py` (WindowsPath+str), `newline="\n"` em `build-claude.py`, `.gitattributes` `eol=lf` para reprodutibilidade byte-a-byte do bundle, limpeza de temp no Windows.
9. **ParserError PowerShell 5.1** — `willtech-install.ps1`: `"${Platform}:"` em vez de `"$Platform:"` (referência de variável inválida). Correção real comprovada no job `windows-latest`; guard de orquestração manteve exceção EXATA para esse único arquivo (conferência do arquivo inteiro), sem enfraquecer a proteção.
10. **Host OpenCode correto** — o instalador `opencode.ai/install` fornece apenas OpenCode 1 (contrato `default.server()`, chave `plugin`); o plugin WillTech é OpenCode 2 (`{id, setup(ctx)}`, chave `plugins`, descoberta automática de `.opencode/plugins/`). O CI passou a usar o instalador oficial `opencode.ai/v2/install` (OpenCode 2.3.0), eliminando a falha de carga por incompatibilidade de host.
11. **Caminho pessoal hardcoded no `test-appserver.py`** — descoberta portável (`WILLTECH_NODE` > `node`/`nodejs` no PATH).

## Economia efetivamente medida

**Nenhuma.** Zero execuções pagas realizadas (gasto US$0,00 do orçamento de US$2,00); nenhum percentual de economia é reivindicado. A ferramenta de comparação está verificada (testes determinísticos com fixtures sintéticas), mas isso não é benchmark. Sem provedor de laboratório expressamente autorizado, o resultado é registrado como **NÃO MEDIDO / AMOSTRA INSUFICIENTE** — não inventado. Evidências: `tools/smoke-evidence/bench-3.0-nao-medido.json` e `bench-final-nao-medido.json`.

## Limitações restantes (declaradas, não anunciadas como homologadas)

1. **Sessão real com modelo** em OpenCode, Codex e Claude Code: pendente. A carga do plugin e o hook SessionStart do OpenCode são reais no host oficial 2.3.0 (CI, custo zero); os demais hooks dependem de sessão com modelo, que exige provedor autenticado não disponível em ambiente isolado. Codex exige autenticação do proprietário para sessão real. Claude Code sem auth devolve `Not logged in`. Nada disso é anunciado como homologado.
2. **Benchmark real** não medido (consequência direta de 1; sem provedor autorizado).
3. **Render nativo do painel visual** no OpenCode Desktop: o smoke é laboratório headless (navegador real, host simulado); o painel é declarado **experimental** e a homologação gráfica nativa **NÃO EXECUTADA**. Codex não expõe painel nativo de 7 agentes (visualizador complementar).
4. **Detector de segredos** é heurístico para formatos DESCONHECIDOS; a proteção primária é estrutural (minimização + allowlists + neutralização).

## Distribuição e instalação verificada

- Artefatos definitivos gerados a partir do commit validado da `main`, com SHA-256 por arquivo (ver `SHA256SUMS` da release).
- Instalação limpa, atualização idempotente, desativação (`--disable`), desinstalação (`--uninstall`) e restauração de backups exercitados em ambientes descartáveis: `tools/test-install.py` (16, shell real + Python embutido do PS1), ciclo nativo PowerShell 5.1 no CI `windows-latest`, e smoke final integrado (`tools/smoke-evidence/smoke-final-integrado.json`).
- Instalação a partir dos arquivos publicados verificada em ambiente limpo após a publicação da release (download → conferência de hashes → instalação → smoke).

## Veredito final

**PUBLICÁVEL COM LIMITAÇÕES HONESTAS DECLARADAS.**

O código 3.0 está provado nas categorias determinística (567 verificações + 2 bancadas node, 0 falhas) e nativa por SO (CI 5/5: macOS, Linux, Windows, host oficial OpenCode 2.3.0 e smoke de inteligência). O protocolo real do App Server Codex foi comprovado com binário oficial (SKIP eliminado). A carga do plugin V2 e o hook SessionStart do OpenCode são reais no host oficial isolado. Instalação/atualização/reversão verificadas em ambientes descartáveis e a partir dos artefatos publicados. Documentação fiel ao estado real (README, INSTALL, EVOLUCAO, contratos), drift 0 divergências, guard de orquestração intacto.

As limitações restantes (sessão com modelo nas 3 plataformas, render nativo do painel, benchmark) são **dependências externas de autenticação/provedor**, não defeitos de código, e estão declaradas como pendentes/experimentais — nenhuma funcionalidade anunciada como homologada depende exclusivamente de simulação. A release não é falsamente homologada: os rótulos correspondem à evidência.

Restrições cumpridas: nenhuma instalação, credencial, conta ou configuração pessoal tocada; homologação exclusivamente em CI/ambientes isolados; histórico preservado; sem funcionalidades novas; testes não enfraquecidos; inferência paga não iniciada sem autorização.