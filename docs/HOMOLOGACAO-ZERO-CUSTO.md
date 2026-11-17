# Homologação ZERO CUSTO — WillTech-General 3.0 (modelo real gratuito)

Data: 2026-11-17 · Repositório público: `hebwil/willtech-general` · Branch de manutenção: `qoder/homologacao-zero-custo`.
**Orçamento: US$ 0,00.** Nenhum serviço pago, crédito, assinatura ou saldo pessoal consumido. Toda a inferência foi executada por um **modelo aberto local (Qwen3-1.7B GGUF) em runners gratuitos descartáveis do GitHub Actions** (`ubuntu-latest` / `macos-latest` / `macos-15`), com llama.cpp público. A release estável `v3.0.0` e a `main` **não foram alteradas** por esta homologação; correções vivem apenas neste branch, com CI e PR.

Categorias de evidência (nunca confundidas): **PASS REAL** (runtime/modelo/app oficial executando de fato, com logs/IDs/capturas), **PASS INTEGRAÇÃO** (núcleo real alimentado por eventos nativos em subprocess), **PASS DETERMINÍSTICO** (unittest/subprocess/labs git, sem modelo), **NC / NÃO COMPROVADO** (tentativa concreta feita, prova insuficiente, motivo técnico registrado), **BLOQUEADO** (dependência externa legítima). Nenhum falso PASS, nenhum SKIP de requisito obrigatório, nenhuma métrica inventada.

---

## §2 — Modelo real gratuito (critério A): PASS REAL

Lab no `ubuntu-latest` gratuito: llama.cpp build **b12483** (asset público `llama-b12483-bin-ubuntu-x64.tar.gz`) + GGUF público **`ggml-org/Qwen3-1.7B-GGUF` Q4_K_M** (apache-2.0). Servidor de inferência **CPU, bind 127.0.0.1:8080**, `--jinja -c 8192 --threads 4 -np 1 --chat-template-kwargs '{"enable_thinking":false}`. OpenCode **v2.3.0** oficial instalado no runner isolado, provider `@opencode/ai/providers/openai-compatible` apontando **somente** para o servidor local do lab (apiKey dummy `lab-no-auth`; nenhuma config global pessoal tocada).

Hashes de integridade do lab (artefato `lab-cache/SHA256SUMS.txt`):
- `llama.tar.gz` = `41a1d0df0abbec1c48b506f347781e4b3d10f74423f0b6359f8b277df7e09a0a`
- `model.gguf` = `d2387ca2dbfee2ffabce7120d3770dadca0b293052bc2f0e138fdc940d9bc7b5`

Provas ([run 44184914784](https://github.com/hebwil/willtech-general/actions/runs/44184914784), SUCCESS):
1. **PROVA 1 — inferência real:** resposta `content="LAB OK"`, `finish_reason=stop`, 3 completion tokens medidos. (Antes da correção, o thinking do Qwen3 consumia `max_tokens` e esvaziava `content` — defeito real de configuração corrigido com `enable_thinking=false` no servidor e na requisição; ver §7.)
2. **PROVA 2 — tool-calling real:** `finish_reason=tool_calls`, chamada `get_weather({"city":"Paris"})` emitida pelo modelo.
3. **PROVA 3 — sessão OpenCode autêntica com WillTech:** sessão `ses_e147cc129ffeBZzOMGKPuPO3Q3`, tool `shell` `echo WILLTECH_LAB_OK` exit 0, tokens in=6009+49 / out=25+28, **cost 0**; `llamacpp/qwen3-1.7b` listado; **7 agentes WillTech carregados**; `state-plugin-load.json` presente (plugin V2 executou o núcleo determinístico real).

Não há equivalência de capacidade declarada entre modelos: o Qwen3-1.7B é um modelo pequeno; suas limitações estão registradas em §3/§4 como limitação de capacidade, não como falha da arquitetura.

## §3 — Inteligência coletiva com modelo gratuito: PASS REAL (sessão + delegações); fluxo completo limitado pela capacidade do modelo

Sessão coletiva autêntica ([run 44187245309](https://github.com/hebwil/willtech-general/actions/runs/44187245309), artefato `homolog-inteligencia-gratuita`): sessão `ses_e1470114cffeeo60pLpngPeq5H`, **4 delegações `subagent` reais com status `completed`**, alvos `general`, `explore`, **`willtech-explorador`**, **`willtech-revisor`** (dois ids corretos do roster). O mecanismo de delegação comandante→General→especialistas do OpenCode V2.3.0 **funciona com o modelo gratuito** (tool `subagent`, input `agent`). Sessão anterior ([run 44186338843](https://github.com/hebwil/willtech-general/actions/runs/44186338843)) já registrara 3 deleg reais (`ses_e147530fcffemIQrXB1GEBuPZb`).

O que **NÃO** aconteceu (não aprovado como feito — limitação de capacidade do 1.7B, não da arquitetura):
- **Registro manual na sala pelo modelo: 0 chamadas** a `willtech-room.py` nas sessões coletivas. A sala foi semeada/validada pela ferramenta e a injeção JIT é automática (plugin), mas o modelo não executou o passo de registrar conhecimento.
- **Edição do executor: no-op rejeitado.** O tool `edit` foi chamado de verdade sobre `src/app.py`, mas com `oldString==newString` ("soma"→"soma"); o OpenCode recusou (status `error`). A modificação autorizada do arquivo de lab **não se consumou** por erro do modelo, não por falha do tool.
- Alguns ids de agente errados (`explore`, `general`, `testador`) e consolidação final vaga — o modelo pequeno nem sempre acerta o roster nem o protocolo multi-passo.

Persistência/reuso da sala provados independentemente do modelo: o finding semeado (`soma(a,b) em src/app.py retorna a+b`, `validated`, com `source_hash`/`evidence_hash`) sobreviveu entre sessões (`room-after.json`), e **sessões novas o recuperam** pela injeção JIT (cenário B do §4) e por consulta em processo novo (§6).

## §4 — Benchmark real custo zero (critério D): PASS REAL (medido); SEM economia de tokens reivindicada

Mesmo servidor/modelo/temperatura/tarefa/aceite; 3 repetições por cenário; tarefa de 295 chars (≥ `COMPLEX_CHARS=200`, logo o cenário B injeta de fato). Cenário A: `.willtech/enabled` removido (SI desativada). Cenário B: `enabled` presente + sala semeada/validada (SI ativada). Registros OpenCode JSONL reais convertidos pelo adaptador fiel `tools/opencode-trace.py` e comparados por `tools/willtech-compare.py --repeat 3`.

Médias por execução ([run 44187245309](https://github.com/hebwil/willtech-general/actions/runs/44187245309), `compare.txt`):

| métrica | sem SI (A) | com SI (B) | delta |
|---|---|---|---|
| input_tokens | 111.7 | 1462.7 | +1351 |
| output_tokens | 193.7 | 222.7 | +29 |
| cache_read | 12078.3 | 10841.0 | −1237.3 |
| cache_creation | 0 | 0 | 0 |
| num_turns | 2 | 2 | 0 |
| duration_ms | 41283.7 | 47204.3 | +5920.7 |
| bash_failures | 0 | 0 | 0 |
| failure_loops | 0 | 0 | 0 |

Métricas adicionais (`intel-summary.json`): reads 3/3; **repeated_reads A=2 → B=1** (a injeção reduziu uma releitura); delegations 0/0 (tarefa de agente único); room_calls 0/0 (injeção é automática, não chamada manual); failures 0/0; **cost_usd 0.0 em ambos; custo total US$ 0,00**; `simulation:false`.

Leitura honesta: a injeção JIT **acrescenta input fresco** (o brief entra no prompt e quebra o cache de prefixo — assinatura visível: input +1351 / cache_read −1237) e **reduz releituras** (2→1), mas **não produziu economia líquida de tokens nem ganho funcional neste modelo de 1.7B**. O heuristic `functional_correct` = 0 em ambos: o modelo procurou por "sum" em vez de "soma" e respondeu de forma vaga — limitação de capacidade, não da arquitetura. **Nenhum percentual de economia é reivindicado.** O requisito §4 (comparação autêntica + métricas + custo zero) está cumprido; o resultado é o que foi medido, não o que se desejaria.

## §5 — Interface visual nativa (critério C): app PASS REAL; plugin GUI carrega no Desktop real; painel NC (não comprovado)

Caminho real ordenado, em runners **macOS gratuitos descartáveis** (`macos-latest` = 26.7.2 e `macos-15` = 15.8.2, ambos arm64): aplicativo **OpenCode Desktop OFICIAL** (MIT, Anomaly) baixado do endpoint oficial, integridade verificada (`dmg sha256 = d98f355e835272fbd75bedcdd02c0fa5d871d88d757aeb8d05676e9626545aa8`, `codesign` oficial + `spctl`), isolado em `$RUNNER_TEMP/wt-desktop` (nunca `/Applications` pessoal). Probe: **WindowServer presente** (sessão Aqua), `screencapture` real permitido (baseline ~80 KB), **System Events/Acessibilidade concedida** (janela "OpenCode" listada). Electron 44.9.1 / app 2.3.0 lançou com `--no-sandbox --disable-gpu` em **ambos** os macOS (o hang do renderer electron#55368 não se manifestou).

- **Render nativo do APLICATIVO: PASS REAL.** Capturas reais verificadas **visualmente** (home e view de sessão), janela nativa confirmada por System Events e pelo renderer `--opencode-window`. Runs [44186834811](https://github.com/hebwil/willtech-general/actions/runs/44186834811), [44187717735](https://github.com/hebwil/willtech-general/actions/runs/44187717735), [44188421603](https://github.com/hebwil/willtech-general/actions/runs/44188421603), [44189589921](https://github.com/hebwil/willtech-general/actions/runs/44189589921), [44190169847](https://github.com/hebwil/willtech-general/actions/runs/44190169847).
- **Carga do plugin GUI no Desktop real: PASS REAL.** O servidor de fundo lê o config **global**; registro via `tools/willtech-gui.py --install` (enabled=true) no runner isolado. As deps públicas do GUI (`@opencode/plugin@2.3.0` — cujo subpath export `./gui` fornece a API —, `solid-js@1.9.16`, peers `@opentui/*`, `@opencode/theme`) foram instaladas no dir do plugin (**376 packages**, após corrigir o pin que causava ERESOLVE). O log completo do servidor mostra `loading plugin … gui-experimental.cjs` **sem erro de require** — o plugin GUI carrega de fato no Desktop oficial.
- **Painel de mascotes / 7 estados / animações / reduced-motion: NC (NÃO COMPROVADO nativamente).** A aba é `region:"side"` e só lista quando `layout.open` inclui "team" ([gui-source.cjs:163](file:///Users/will/Documents/willtech-general-30-shared-intelligence/opencode/plugins/willtech/visual/gui-source.cjs#L163)); o comando `team.toggle` exige **sessão atual** ([gui-source.cjs:166-171](file:///Users/will/Documents/willtech-general-30-shared-intelligence/opencode/plugins/willtech/visual/gui-source.cjs#L166)). Duas tentativas **bounded** de automação gráfica com Acessibilidade já concedida, ambas com captura verificada visualmente: (1) menu "/" do prompt — abriu de fato mas retornou **"No matching items"** para `/WillTech` (run [44191132248](https://github.com/hebwil/willtech-general/actions/runs/44191132248)): o menu "/" **não expõe comandos de plugin GUI**; (2) paleta **Cmd+K** — nenhuma paleta/painel apareceu, prompt permaneceu vazio (run [44191730672](https://github.com/hebwil/willtech-general/actions/runs/44191730672), macos-15). **Motivo técnico:** a affordance do Desktop que invoca comandos de plugin GUI / abre a aba lateral (`ctx.layout.toggle`) não foi alcançável por automação gráfica respeitosa às permissões nestas tentativas; logo o render nativo do painel (mascotes, 7 estados, animações, reduced-motion) **não foi comprovado**. Não é declarado PASS. O que É comprovado nativamente: render do app e carga do plugin GUI (acima).
- **Alternativas oficiais gratuitas isoladas já checadas:** a bancada Chromium headless real (44/44) exercita a lógica de render do painel com host simulado — é integração, **não** render nativo; o viewer Codex complementar **não** é painel nativo de 7 agentes; o Computer Use do Qoder (browser-use) tem alvo **browser**, não app macOS nativo. Nenhum deles é apresentado como prova nativa.
- **Nenhuma proteção contornada:** TCC/SIP/gravação de tela/acessibilidade não foram burlados; usou-se apenas o que o runner descartável já concede. Nenhum app, credencial ou config pessoal tocado.

## §6 — Absorção de conhecimento autorizado + recuperação em sessão/processo novo: PASS REAL

Conhecimento autorizado desta homologação registrado na sala local com evidência (hash do arquivo de origem), validado por autoridade do roster e **recuperado em processo novo** via consulta JIT:
- `put` finding/explorer (lab gratuito llama.cpp+Qwen3, `--path-ref .github/workflows/modelo-gratuito.yml`, evidence-hash) → `registered id=1` → `validate --by reviewer` → `validated`.
- `put` decision/executor (correção `enable_thinking=false`) → id=2 → validated.
- `put` ref/researcher (mapeamento do adaptador `opencode-trace.py`) → id=3 → validated.
- **Processo novo:** `query --objective "lab gratuito llama.cpp Qwen3 thinking adaptador" --budget-chars 1200` → header QUARENTENA, `SALA project=d8ba03757871 hits=3 budget=1200`, os 3 registros `validated` com `source_hash`/`evidence`. Recuperação comprovada fora do processo que escreveu.

Nenhuma skill foi auto-promovida: o gate humano (`skill-promote --i-approve-human`) permanece intacto e não foi contornado por esta homologação.

## §6b — Matriz requisito → implementação → teste → prova

| Requisito (spec 3.0) | Implementação | Teste | Prova |
|---|---|---|---|
| Sala SQLite stdlib, schema v3, FTS5 opcional + fallback LIKE | [tools/willtech-room.py:93](file:///Users/will/Documents/willtech-general-30-shared-intelligence/tools/willtech-room.py#L93), :188, :729 | test-room.py (53), test-room-v3.py (34), test-compat.py (22) | CI 5/5 [44140677603](https://github.com/hebwil/willtech-general/actions/runs/44140677603); fallback real sem FTS5 no CI |
| Provenance + invalidação por mudança de código (stale) | [tools/willtech-room.py:807](file:///Users/will/Documents/willtech-general-30-shared-intelligence/tools/willtech-room.py#L807), :959-982 | test-room-v3, test-jit.py | CI; §6 absorção (source_hash presente) |
| Escrita idempotente (`put`) | [tools/willtech-room.py:832](file:///Users/will/Documents/willtech-general-30-shared-intelligence/tools/willtech-room.py#L832) | test-room | CI |
| Validação explícita (evidência + autoridade) | [tools/willtech-room.py:1383](file:///Users/will/Documents/willtech-general-30-shared-intelligence/tools/willtech-room.py#L1383) | test-room-v3 BL2 | CI; §6 ids 1-3 validated |
| Ciclo de skills + gate humano | [tools/willtech-room.py:1590](file:///Users/will/Documents/willtech-general-30-shared-intelligence/tools/willtech-room.py#L1590), :1658 | test-room-v3, test-handoff.py | CI; gate não contornado (§6) |
| Handoff BL1 (result persistido) + BL2 (transições) | [tools/willtech-room.py:1518](file:///Users/will/Documents/willtech-general-30-shared-intelligence/tools/willtech-room.py#L1518) | test-handoff.py (11), test-room-v3 | CI |
| Pack do revisor sem result do executor | [tools/willtech-room.py:1329](file:///Users/will/Documents/willtech-general-30-shared-intelligence/tools/willtech-room.py#L1329), :1371 | test-handoff.py::test_12 | CI |
| Orçamento de contexto aplicado pela ferramenta | [tools/willtech-room.py:93](file:///Users/will/Documents/willtech-general-30-shared-intelligence/tools/willtech-room.py#L93), :1889 | test-jit.py (12) | CI; §6 query budget=1200 |
| Isolamento por projeto | [tools/willtech-dossie.py:246](file:///Users/will/Documents/willtech-general-30-shared-intelligence/tools/willtech-dossie.py#L246) | test-room-v3 | CI |
| Quarentena + neutralização + allowlists + tetos + caminhos | [tools/willtech-room.py:548](file:///Users/will/Documents/willtech-general-30-shared-intelligence/tools/willtech-room.py#L548) | test-room-v3 BL4 | CI; §6 header QUARENTENA |
| Lock portável (sidecar SQLite, sem fcntl/msvcrt) | [tools/willtech-room.py:298](file:///Users/will/Documents/willtech-general-30-shared-intelligence/tools/willtech-room.py#L298) | test-compat, test-room-v3 BL3 | CI windows (msvcrt concorrente) |
| Backup verificado + restore | [tools/willtech-room.py:683](file:///Users/will/Documents/willtech-general-30-shared-intelligence/tools/willtech-room.py#L683), :1530 | test-room-v3 | CI |
| Injeção JIT por objetivo + gate `enabled` + COMPLEX_CHARS | [tools/willtech-auto.py:175](file:///Users/will/Documents/willtech-general-30-shared-intelligence/tools/willtech-auto.py#L175), :344; [tools/willtech-dossie.py:90](file:///Users/will/Documents/willtech-general-30-shared-intelligence/tools/willtech-dossie.py#L90) | test-jit.py, test-auto.sh | CI; §4 delta de input do cenário B; §6 |
| Sete agentes roster/subagent | opencode/agent/*.md + wrappers | test-wrappers.sh (41), test-homolog.py (61) | CI opencode-host; §3 delegações reais a willtech-explorador/revisor |
| Carga real do plugin V2 + SessionStart | [opencode/plugins/willtech/index.js](file:///Users/will/Documents/willtech-general-30-shared-intelligence/opencode/plugins/willtech/index.js) | test-auto.sh (42) | CI state-plugin-load; §2 lab-state.txt |
| Ferramenta de benchmark | tools/willtech-compare.py | test-compare.py (7) | §4 comparação real 3×3 |
| Adaptador OpenCode→stream-json (novo) | [tools/opencode-trace.py](file:///Users/will/Documents/willtech-general-30-shared-intelligence/tools/opencode-trace.py) | test-opencode-trace.py (5, determinístico; na suíte CI) + conferência exata vs sessão real | §4 (usado na comparação); 5/5 local |
| Interface visual nativa (app + painel) | opencode/plugins/willtech/visual/gui-experimental.cjs; tools/willtech-gui.py | test-gui-install.py (9); Chromium 44/44 | §5 (render do app PASS REAL; painel ver §5) |

Comparação com o planejamento: tudo que a spec `docs/SHARED-INTELLIGENCE.md` e os contratos dos 7 agentes prometem está implementado e testado nas categorias acima. As duas limitações históricas ("benchmark NÃO MEDIDO" e "render nativo do painel NÃO EXECUTADO") foram atacadas nesta homologação: o benchmark agora é **medido com modelo real gratuito** (§4); o render nativo do **aplicativo** e a **carga do plugin GUI** são **PASS REAL** (§5); o painel de mascotes permanece **NC** com motivo técnico registrado (§5).

## §7 — Defeitos reais encontrados e corrigidos nesta homologação (branch de manutenção)

1. **Thinking do Qwen3 esvaziava a resposta** (`content=""`, `finish_reason=length`): corrigido com `--chat-template-kwargs '{"enable_thinking":false}'` no servidor + kwargs na requisição + `max_tokens` adequado. Comprovado: PROVA 1 `content="LAB OK"` (run 44184914784).
2. **Tarefa de benchmark curta demais para injetar** (<200 chars ⇒ A≈B por construção): corrigida para 295 chars com objetivo nos primeiros 200; path-filters por workflow para não disparar CI cruzado.
3. **Indicador falso de painel nativo** (`willtech_panel_captured=true` sem verificação visual): renomeado para `screenshot_after_plugin_install` (nunca implica painel renderizado); classificação do painel exige inspeção visual da captura.
4. **GUI plugin não carregava por config de projeto**: o Desktop lê o config **global**; registro via `tools/willtech-gui.py --install` no runner descartável (isolado, sem config pessoal).
5. **Deps públicas do GUI ausentes / pin errado**: `require("@opencode/plugin/gui")` (subpath export de `@opencode/plugin`) + `solid-js` + peers `@opentui/*`; primeiro install falhou por ERESOLVE (`solid-js@1.9.9` vs `^1.9.12` de `@opentui/solid@0.9.2`); pin corrigido para `1.9.16` e log completo do servidor capturado como ground truth (run 44190169847).
6. **Adaptador de trace inexistente para OpenCode**: criado `tools/opencode-trace.py`, fiel ao JSONL real v2.3.0 (shell→Bash, subagent→Task com `input.agent`→`subagent_type`, tokens de `step_finish`, `result` sem `usage` para preservar a soma); conferido contra sessão real com métricas exatas.

Nenhum teste enfraquecido, nenhuma função desativada para obter PASS, nenhuma falha disfarçada de SKIP.

## §8 — Entrega: matriz dos 4 requisitos obrigatórios

| Requisito | Classificação | Evidência |
|---|---|---|
| A — Inteligência coletiva com modelo gratuito (sessões + delegações) | **PASS REAL** (sessão + 4 delegações completed); fluxo multi-passo completo **limitado pela capacidade do 1.7B** (registro manual 0, edit no-op) — não aprovado como feito | runs 44184914784, 44186338843, 44187245309; `oc-coletiva.jsonl`, `room-after.json` |
| B — Sala: persistência real + reuso | **PASS REAL** | finding validado persiste entre sessões; injeção JIT em sessões novas (§4 B); recuperação em processo novo (§6); backup/restore CI |
| C — Interface visual nativa (app real + eventos + evidência visual) | **app: PASS REAL**; **plugin GUI carrega: PASS REAL**; **painel de mascotes: NC** (affordance da aba lateral não alcançável por automação gráfica bounded; motivo técnico registrado) | runs 44186834811, 44187717735, 44188421603, 44189589921, 44190169847, 44191132248, 44191730672; capturas + codesign + log do servidor |
| D — Benchmark autêntico + métricas + custo zero | **PASS REAL (medido)**; sem economia reivindicada | run 44187245309; `compare.txt`, `intel-summary.json`; custo US$0,00 |

Artefatos publicados sem segredos (logs, hashes, IDs de sessão, capturas, links de run). Release `v3.0.0` e `main` preservadas; correções apenas neste branch com CI + PR.

## Limitações honestas restantes

- O modelo gratuito de 1.7B **não executa reliably o protocolo coletivo completo** (registro manual na sala, edição útil, consolidação). A arquitetura (delegação, sala, JIT, gates) funciona; a capacidade do modelo é o fator limitante. Nenhum resultado de modelo maior é extrapolado.
- **Sem economia de tokens** medida neste modelo; a injeção acrescenta input fresco e quebra cache de prefixo. Economia positiva NÃO é reivindicada.
- Painel GUI nativo de mascotes: **NC**. O plugin carrega no Desktop real, mas a aba lateral (`region:"side"`, toggle por comando que exige sessão) não foi revelada por automação gráfica bounded ("/" não lista comandos GUI; Cmd+K sem paleta). Render nativo do painel não comprovado; a bancada Chromium (44/44) exercita a lógica de render mas é integração com host simulado, não nativo.
- Detector de segredos segue heurístico para formatos desconhecidos; proteção primária é estrutural.