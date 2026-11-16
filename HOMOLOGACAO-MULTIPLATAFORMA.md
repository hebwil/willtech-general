# Homologação Multiplataforma — WillTech-General

Missão: analisar, corrigir, integrar e homologar o WillTech-General completo nas
três plataformas (OpenCode, Claude Code, Codex) como produto open-source
distribuível para diferentes máquinas/SOs. Base: `main` @ `ece7429` (PRs #10–#13).
Branch de trabalho: `qoder/multiplataforma-integracao` (worktree isolado).
**Sem push/merge/release** (aguarda autorização posterior).

Regra aplicada: não tratar hipóteses como causas confirmadas — cada defeito foi
reproduzido (RED) antes da correção e revalidado (GREEN) com o mesmo teste.
Instalações pessoais, Bifrost, modelos, MCPs, skills, VPS e produção **não foram
tocados**. Nenhum gasto de modelo. Laboratórios descartáveis em `/tmp` e fixtures
temporários; o runtime Node pessoal do Codex foi usado **somente-leitura** como
ferramenta de laboratório (o teste do produto descobre Node portavelmente).

## 1. Defeitos reais encontrados e corrigidos (RED → GREEN)

### D1 — Codex: visualizador exposto em todas as interfaces (segurança)
- **Causa:** `viewer/server.cjs` chamava `server.listen(PORT)` sem host → Node
  escuta em `*` (todas as interfaces). `/history` e `/events` expõem atividade de
  sessões pela rede.
- **RED:** `lsof` mostrou `TCP *:8799 (LISTEN)` (IPv6 wildcard), embora o log
  dissesse "localhost".
- **Correção:** host padrão `127.0.0.1` (`WILLTECH_CODEX_HOST` permite override
  explícito); `listen(PORT, HOST)`; módulo exportado e auto-listen guarded por
  `require.main` para teste; timer de pump com `unref`.
- **GREEN:** `lsof` mostra `TCP 127.0.0.1:8799 (LISTEN)`; teste real
  `server.address() == 127.0.0.1` e conexão por interface IPv4 não-loopback
  **recusada** (`test_server_binds_loopback`, `test_server_loopback_rejects_external`).

### D2 — Codex: `SessionEnd` apagava sessões concorrentes ativas
- **Causa:** `viewer/app.js` fazia `sessions.clear(); observations.clear()` em
  qualquer `reset`, e recriava a sessão encerrada como atividade fantasma.
- **RED:** harness DOM dirigindo o `app.js` real: com general(main) + explorador
  ativos, `SessionEnd` do main levou explorador de `working` → `waiting`
  (observations 2 → 1).
- **Correção:** reset remove **somente** a sessão correspondente
  (`sessions.delete(sid); observations.delete(sid)`) e retorna sem recriar fantasma.
- **GREEN:** explorador permanece `working`; sessões concorrentes preservadas
  (`test_viewer_reset_scoped`, 2 sessões restantes).

### D3 — Codex: hooks não portáveis para Windows + timeouts fora da spec
- **Causa:** `hooks/hooks.json` usava apenas `python3 "$(git rev-parse
  --show-toplevel)/codex/willtech-visual/hooks/willtech_bridge.py"` (POSIX, sem
  `commandWindows`), presumindo cópia completa do WillTech no repo de trabalho;
  `SessionEnd`/`Interrupt` com `timeout: 5` (máximo oficial desses eventos = 3s).
- **Fundamento oficial:** docs Codex confirmam `commandWindows` (override
  Windows-only) e que hooks de **plugin** recebem `PLUGIN_ROOT`/`PLUGIN_DATA`
  (e `CLAUDE_PLUGIN_ROOT`), com comandos rodando no `cwd` da sessão.
- **Correção:** pacote virou plugin bundled (`.codex-plugin/plugin.json` →
  `hooks/hooks.json`); caminho do bridge via `PLUGIN_ROOT` (Unix
  `python3 "${PLUGIN_ROOT}/..."`, Windows `py -3 "%PLUGIN_ROOT%\..."`);
  `SessionEnd`/`Interrupt` `timeout: 3`.
- **GREEN:** `test_hooks_windows_portable` (commandWindows presente, `py -3`,
  `%PLUGIN_ROOT%`, sem `$()`, timeouts ≤ 3s, manifesto válido) e
  `test_bridge_runs_via_plugin_root` — o comando real do hook executa num repo
  descartável **sem** cópia do WillTech e produz o feed (prova de portabilidade).
- **Limitação:** execução nativa Windows do `commandWindows` não homologada (sem
  ambiente Windows descartável nesta estação); estrutura validada deterministicamente.

### D4 — Codex: suíte com caminho pessoal de Node e falsos-negativos
- **Causa:** `tools/test-codex.py` hard-codava o Node pessoal do proprietário e
  não cobria bind de rede, reset cross-session nem portabilidade Windows.
- **Correção:** descoberta portável `WILLTECH_NODE` > `node`/`nodejs` no PATH;
  testes JS pulam com motivo explícito quando não há Node (não contam como PASS);
  novas regressões D1/D2/D3 + history/replay + SSE ao vivo.
- **GREEN:** 12/12 testes (`test_server_history_replay_and_sse` prova replay do
  feed no reinício e entrega SSE de novo evento).

### D5 — OpenCode: instalador não distribuía/registrava o pacote GUI
- **Causa:** `tools/willtech-install.sh/.ps1` são projeto-local e nunca tocam
  configs globais; o painel GUI exige registro no `opencode.json` global que o
  servidor de fundo do Desktop carrega. A ativação era manual, com caminho
  absoluto dependente da máquina do proprietário.
- **Correção:** ferramenta dedicada, opt-in, portável e reversível
  `tools/willtech-gui.py` (`--install/--disable/--enable/--uninstall`,
  `--config PATH`): mescla uma única entrada `plugins`, backup prévio, registro
  de posse, idempotente (sem duplicar), preserva plugins/ajustes de terceiros,
  caminho do pacote resolvido da localização do checkout (sem absoluto pessoal).
  Não é instalador paralelo de automação — é a superfície GUI, incompatível com o
  invariante projeto-local do instalador de automação.
- **GREEN:** `tools/test-gui-install.py` 9/9 em fixtures **descartáveis** (install,
  preservação de terceiros, update idempotente, disable/enable, uninstall restaura
  backup, uninstall preserva alterações do usuário, sem registro = no-op, caminho
  portável, symlink recusado). INSTALL.md atualizado com o fluxo automatizado.
- **Limitação:** render gráfico nativo no Desktop não comprovado nesta estação
  (sem Desktop descartável; permissão de Screen Recording negada; instalação
  pessoal não tocada). Bundle/eventos aprovados em laboratório headless.

### D6 — Guarda de teste obsoleto (falso-negativo pré-existente)
- **Causa:** `tools/test-gui.py::test_orchestration_identity_and_installers_unchanged`
  pinava `BASE=fbb2427`, anterior ao PR #13, que legitimamente evoluiu
  installers/willtech-auto.py/AGENTS.md. O guard **já falhava no HEAD** antes
  desta missão (provado: `git diff fbb2427 HEAD -- tools/willtech-install.sh ...`
  não-vazio por commits `693fa20`/`cf04aa4`, sem minhas edições).
- **Correção:** BASE atualizado para a baseline de orquestração pós-PR#13
  (`ece7429`); proteção restrita à **identidade/orquestração** (assets, LICENSE,
  NOTICE, créditos, `opencode/agent`, `AGENTS.md`, `bin`, plugin de automação
  `index.js`, `codex/agents`, `codex/hooks.json`, `claude-code/settings`,
  `willtech-auto.py`, installers). Subdiretórios **visuais**
  (`codex/willtech-visual`, `claude/plugins/willtech-visual`) são alvo legítimo
  de correção e ficam fora do guard de orquestração. A proteção da orquestração
  permanece integral; nenhuma proteção foi enfraquecida.
- **GREEN:** `test-gui.py` 4/4.

## 2. Matriz de evidências (10 componentes × 3 plataformas)

Classificação: **A** APROVADO · **L** APROVADO EM LABORATÓRIO · **LO** LIMITAÇÃO
OFICIAL · **NC** NÃO COMPROVADO · **R** REPROVADO.

| # | Componente | OpenCode | Claude Code | Codex |
|---|---|---|---|---|
| 1 | Instalação/atualização/desinstalação reversível | L (test-install 16; GUI test-gui-install 9) | L (test-install 16; Mod build reprodutível) | L (plugin bundled + test-install 16; bridge via PLUGIN_ROOT) |
| 2 | Carregamento de agentes + comandante→General→6 especialistas | L (test-homolog 61) | L (test-homolog 61) | L (test-homolog 61; agents/*.toml) |
| 3 | Delegação/permissões | L (test-homolog/test-auto) | L (test-homolog/test-auto) | L (test-homolog/test-auto) |
| 4 | Automação nativa (plugins/hooks) | L (test-auto 39; plugin index.js) | L (test-compat 22; hooks ${CLAUDE_PROJECT_DIR}) | L (test-codex 12; hooks oficiais + commandWindows) |
| 5 | Memória/dossiê/cache/aprendizado | L (test-dossie 51) | L (test-dossie 51) | L (test-dossie 51) |
| 6 | Elephant/Goldfish (revisão independente) | L (test-plan 23; test-dossie) | L (test-plan 23) | L (test-plan 23) |
| 7 | RepoMap incremental | L (test-repomap 10) | L (test-repomap 10) | L (test-repomap 10) |
| 8 | Supervisor/timeouts/anti-loop | L (test-supervisor 10; test-trace 10) | L (test-supervisor 10) | L (test-supervisor 10) |
| 9 | Segurança/isolamento/integridade | L (test-compat; política P1) | L (test-compat; fail-closed) | **A** (loopback real D1; reset D2; somente-observação) |
| 10 | Interface visual 7 mascotes + animações/estados/eventos | L (smoke headless + gui-events; bundle real) / render Desktop **NC** | L (test-claude 4; núcleo sem drift, fail-open) / render nativo **NC** | L (test-codex 12; viewer complementar) / painel nativo **LO** |

Notas por plataforma (componente 10):
- **OpenCode:** API GUI experimental; gates `enabled`/`desktop`/`>=2.2.6`.
  Bundle reproduzível com bytes originais; eventos headless aprovados. Render
  gráfico nativo no Desktop **não comprovado** (sem Desktop descartável).
- **Claude Code:** Mod oficial (`Pane`, `ui.render`, `$.agent.list()`); superfícies
  terminal (PNG/blit) vs Desktop/VS Code (SVG/SMIL). `Image` documentado para
  terminal. Animação nativa dos mascotes **não comprovada** (sem runtime descartável).
- **Codex:** **não expõe painel nativo de 7 agentes** (Codex Pets = 1 companheiro
  agregado; extensão IDE sem Pets/plugins de UI). Visualizador **complementar**
  local (não é painel nativo). Sessão real com modelo **não homologada** (LO).

## 3. Regressão consolidada (única, ao final)

| Suíte | Resultado |
|---|---|
| tools.test-claude | 4 OK |
| tools.test-gui | 4 OK |
| tools.test-gui-install (novo) | 9 OK |
| tools.test-install | 16 OK |
| tools.test-repomap | 10 OK |
| tools.test-supervisor | 10 OK |
| tools.test-homolog | 61 OK |
| codex tools.test-codex | 12 OK |
| tools/test-auto.sh | 39 PASS |
| tools/test-dossie.sh | 51 PASS |
| tools/test-plan.sh | 23 PASS |
| tools/test-trace.sh | 10 PASS |
| tools/test-drift.sh | 7 PASS |
| tools/test-compat.py | 22 PASS (posix) |
| tools/test-gui-events.cjs | PASS (headless, SDK simulado) |
| tools/test-smoke.cjs (camada Node) | PASS (8 assets originais, 18 quadros APNG) |

**Total: 277 asserções determinísticas + 2 scripts Node PASS, 0 falhas, 0 regressões.**
`test-appserver.py` (protocolo real) pula sem binário descartável do Codex — LO.
O bundle GUI OpenCode permanece byte-idêntico; o smoke headless anterior
(64/64 + 3/3 reduced-motion) continua válido.

## 4. Compatibilidade por SO

- **macOS (arm64):** exercitado nesta estação (posix). Suítes determinísticas e
  laboratórios de socket/DOM reais executados.
- **Linux:** mesmos caminhos posix; não exercitado nativamente aqui (sem ambiente
  Linux descartável). Requisitos objetivos registrados (python3, git, sh).
- **Windows nativo:** `commandWindows` (Codex) e `willtech-gui.py`/`willtech-install.ps1`
  portáveis; lógica PS1 verificada via Python embutido (test-install). **Execução
  nativa Windows não homologada** nesta estação (sem Windows descartável) — NC/LO.
  O teste do bridge Unix pula em `os.name != posix` com motivo explícito.

## 5. Arquivos alterados / criados

Alterados:
- codex/willtech-visual/viewer/server.cjs (D1)
- codex/willtech-visual/viewer/app.js (D2)
- codex/willtech-visual/hooks/hooks.json (D3)
- codex/willtech-visual/tools/test-codex.py (D4 + regressões)
- codex/willtech-visual/README.md (documentação)
- tools/test-gui.py (D6 — baseline/escopo do guard)
- INSTALL.md (ativação GUI automatizada; piso de versão)

Criados:
- codex/willtech-visual/.codex-plugin/plugin.json (manifesto de plugin)
- tools/willtech-gui.py (ativação GUI portável/reversível)
- tools/test-gui-install.py (distribuição GUI em fixtures descartáveis)
- HOMOLOGACAO-MULTIPLATAFORMA.md (este relatório)

## 6. Limitações oficiais e pendências comprovadas

- **LO** Codex não oferece API de painel nativo de 7 agentes; visualizador é
  complementar (claramente identificado).
- **LO** Sessão real Codex/Claude/OpenCode com gasto de modelo não homologada
  (fora do escopo autorizado; exigiria auth do proprietário).
- **NC** Render gráfico nativo OpenCode Desktop e animação nativa Claude Mod
  (sem aplicações nativas descartáveis; instalações pessoais proibidas de tocar).
- **NC** Execução nativa Windows (sem ambiente Windows descartável).
- **LO** `test-appserver.py` requer binário descartável do `codex-app-server`.

## 7. Preservação

Nenhuma instalação pessoal, config global pessoal, Bifrost, modelo, MCP, skill,
VPS, produção ou histórico foi alterado. Ativação GUI testada **apenas** em
fixtures temporários. Imagens originais, identidade visual, autoria e licença
intactos (guard de identidade verde). Sete agentes e comandante nativo não
recriados/substituídos.