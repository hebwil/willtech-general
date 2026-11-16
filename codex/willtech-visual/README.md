# WillTech · Visualizador complementar para Codex

**Isto NÃO é um painel nativo do aplicativo Codex.** É uma alternativa visual
**complementar, independente e claramente identificada**, conforme a Missão 5 §2:
o Codex não expõe uma API oficial para injetar um painel de sete agentes na sua
interface. Este visualizador roda como uma página local separada, alimentada
pelos **eventos oficiais** do Codex, sem modificar o aplicativo e sem nenhuma
chamada de IA.

## Por que complementar (limitações oficiais comprovadas)

- **Codex Pets** é o mecanismo visual nativo oficial: um único companheiro
  animado agregado (estados Running / Needs input / Ready / Blocked), com sprite
  sheet customizado de exatamente 1536×1872. Não representa sete agentes
  distintos nem a hierarquia WillTech.
- **Extensão de IDE do Codex**: não suporta Pets nem plugins de UI — não há
  injeção de painel nativo de sete agentes.
- **Plugins do Codex** = skills + MCP (+ UI MCP opcional) + hooks; não injetam
  UI de sete agentes no aplicativo.

Logo, a única alternativa oficial viável para os sete mascotes reagindo à
atividade real é um visualizador externo que consome os eventos oficiais.

## Fontes de eventos reais (oficiais)

1. **Hooks de projeto** (`.codex/hooks.json`): `SessionStart`, `SessionEnd`,
   `UserPromptSubmit`, `SubagentStart`/`SubagentStop` (com `agent_id`/`agent_type`),
   `PermissionRequest`, `Stop`, `Interrupt`. O runtime envia JSON por stdin
   (`session_id`, `hook_event_name`, `agent_id`, `agent_type`, `cwd`, ...).
   `hooks/willtech_bridge.py` normaliza cada evento e acrescenta uma linha ao
   feed JSONL. `async: true`, fail-open, sem modelo/rede. Exige trust do usuário
   via `/hooks` (consentimento oficial).
2. **App Server** (JSON-RPC sobre stdio, JSONL): `appserver/client.cjs` faz o
   handshake oficial (`initialize`/`initialized`) e traduz notificações reais
   (`turn/started`, `turn/completed`, `thread/status/changed`) para os mesmos
   eventos normalizados. A granularidade de subagentes vem dos hooks; o App
   Server expõe o turno do laço principal.

## Núcleo compartilhado

`viewer/core.js` é cópia **verbatim** (corpo) de
`opencode/plugins/willtech/visual/activity.cjs` — a mesma camada única de
interpretação de estado usada por OpenCode e Claude Code. O teste
`tools/test-codex.py::test_shared_core_no_drift` garante que não há divergência.
Os sete mascotes oficiais (`docs/assets/willtech-*.webp`) são embutidos em
`viewer/assets.js` por `tools/build-codex.py`.

## Animação e acessibilidade

- Respiração CSS (`@keyframes wt-breathe`) apenas nos cartões `working`.
- `prefers-reduced-motion: reduce` desliga a animação; botão de pausa manual.
- Zero chamadas de IA; nenhuma animação dispara modelo.

## Como executar (laboratório / uso local)

```bash
python3 tools/build-codex.py                 # gera core.js + assets.js
node viewer/server.cjs 8741 .codex/willtech-events.jsonl
# abra http://localhost:8741 — feed SSE dos hooks/App Server
```

Para alimentar pelos hooks reais, mescle `hooks/hooks.json` ao `.codex/hooks.json`
do projeto e aprove o trust em `/hooks`. O feed padrão é
`.codex/willtech-events.jsonl` (ou `WILLTECH_CODEX_FEED`).

## Testes

- `python3 -m unittest tools.test-codex` — determinísticos (núcleo sem drift,
  mapeamento de hooks oficiais, mapeamento de notificações do App Server,
  assets, formato oficial de hooks.json, somente-observação sem IA/rede).
- `WILLTECH_CODEX_BIN=<binário> python3 -m unittest tools.test-appserver` —
  protocolo **real** contra um binário descartável do `codex-app-server`
  (handshake `initialize` + `thread/list`, `CODEX_HOME` isolado, sem auth/modelo).
  Pula se o binário não estiver disponível.

## Evidência visual

`evidence/viewer-lab.png` — captura headless do visualizador com os sete
mascotes, estados reais simulados por eventos determinísticos e respiração CSS
ativa. **Laboratório complementar; não é pintura nativa do aplicativo Codex.**

## Limitação honesta de homologação

- O handshake do App Server foi validado contra o binário oficial v0.169.0 em
  instância descartável (offline, sem auth). Isso prova o **contrato do
  cliente**, não uma sessão real.
- A homologação nativa de uma sessão real (eventos `turn/*` e hooks disparados
  por um turno de modelo) **não foi realizada**: exigiria autenticação do
  proprietário e gasto de modelo, fora do escopo autorizado. Registrada como
  limitação, não como sucesso.