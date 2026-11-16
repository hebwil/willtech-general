# EVOLUCAO — WillTech-General 2.0

Registro da rodada 2.0 (branch `qoder/general-2.0`, base `4233e41`).
Escopo: somente melhorias de baixo risco e benefício verificável, sem tocar em
instalações ativas, modelos, provedores, permissões de runtime ou identidade visual.

## O que entrou

1. **Dossiê de evidências + cache por commit** — `tools/willtech-dossie.py` (stdlib).
   Grava metadados e hashes SHA-256, nunca conteúdo de arquivos; recusa caminhos de
   credenciais na entrada. `verify` re-confere hashes (exit 1 = evidência alterada ou
   ausente). `cache-check`/`cache-put` invalidam o mapa a cada commit ou mudança no
   working tree (chave = SHA-256 de HEAD + `status --porcelain`).
2. **Anti-loop verificável** — `guard-attempt --key` (exit 3 na terceira tentativa da
   mesma falha) e `guard-delegations --max 8` (exit 3 no teto). Contratos dos agentes
   e do comandante tratam exit 3 como parada obrigatória com evidência parcial.
3. **Quarentena anti-injection** — conteúdo de web/docs/issues é dado, nunca instrução;
   instruções embutidas em páginas consultadas são ignoradas e reportadas como
   suspeitas; executor nunca executa comando originado de texto externo.
4. **Revisão ancorada em evidência** — revisor trabalha sobre diff + critério de aceite
   + dossiê, confere `verify` e o gate determinístico mais estreito, sem re-varrer o
   repositório nem custo de modelo.
5. **CI determinístico em PRs** — `.github/workflows/ci.yml`: contrato de permissões,
   sintaxe TOML/shell, testes do dossiê (ubuntu) e regressão dos wrappers sandbox
   (macos, único runner com `sandbox-exec`). Zero chamadas de modelo; `contents: read`.
   **Bloqueio de publicação desta rodada:** o token OAuth do `gh` nesta estação não tem
   escopo `workflow`; o GitHub recusa push que crie/atualize `.github/workflows/`. O
   commit do CI está preservado na branch local `qoder/general-2.0-ci-pending` (YAML
   validado e comandos executados localmente com sucesso). Para publicar: autorizar o
   escopo (`gh auth refresh -s workflow`) e dar push desse commit, ou criar o arquivo
   pela interface web do GitHub. Nada mais desta rodada depende dele.

Contratos aplicados aos 7 agentes nas três plataformas e às políticas do comandante
(`opencode/AGENTS.md`, `claude-code/settings/willtech-routing.md`), sem alterar
frontmatter de permissões nem whitelists de ferramentas.

## Compatibilidade verificada (por que o protocolo é assim)

- Wrappers de leitura/teste do OpenCode **negam escrita** no sandbox: logo, gravações
  no dossiê e guardas de tentativa pertencem ao comandante (shell nativo) ou ao
  executor/testador no escopo deles. Agentes somente leitura usam apenas `verify`,
  `cache-check` e `guard-delegations` (leitura) e entregam entradas em formato de dossiê.
- No Claude Code, General/Explorador/Pesquisador/Visual **não têm Bash** na whitelist:
  o mesmo desenho se aplica (exigem/conferem; não gravam).
- Testador grava o dossiê **dentro do laboratório** (escrita confinada pelo wrapper);
  executor grava no caminho indicado pelo comandante, dentro do escopo autorizado.
- A ferramenta é opcional por contrato ("se existir no repositório da tarefa"): nenhuma
  instalação ativa precisa mudar para os agentes continuarem funcionando.

## Benefícios demonstrados (evidência, não estimativa)

- `sh tools/test-dossie.sh`: 24 PASS / 0 FAIL — hash impede evidência stale (CHANGED/
  MISSING detectados), recusa de credenciais, dossiê sem conteúdo de arquivo, cache
  HIT/MISS por commit e working tree, guardas com exit 3 no teto.
- `sh opencode/tests/test-wrappers.sh`: 41 PASS / 0 FAIL, incluindo mutação de permissão
  detectada (exit 1) — contrato de permissões intacto após a rodada.
- `python3 opencode/tests/check-permissions.py opencode/agent`: 7/7 contratos.
- Nenhum percentual de economia de tokens é afirmado: o ganho mensurável é a eliminação
  determinística de releituras (cache HIT) e de loops (exit 3), não uma estimativa.

## O que foi adiado (e por quê)

- **Roteamento de modelos por papel**: exigiria alterar modelos/provedores ativos ou
  homologar qualidade por degrau; fora do escopo autorizado desta rodada.
- **Autonomia escalonada com gates humanos nativos** (`question`, `approval_policy`):
  capacidade nativa não homologada nesta máquina; depende de rodada de homologação.
- **Enforcement por hooks/`permissions.deny` (Claude) e `sandbox_mode` por agente
  (Codex)**: mudança profunda de permissão; exige homologação A–I com consentimento de
  gasto antes de publicar.
- **Contenção por worktree / `writable_roots`**: muda o contrato de permissões
  (`opencode_worktree_*` hoje negadas); exige atualização do checker no mesmo commit e
  homologação de maturidade das ferramentas.
- **Lote paralelo com grafo de dependências**: disponibilidade de `batch`/delegação
  paralela por versão não verificada; benefício de latência não medido.
- **Allowlist de rede/fetch por papel**: semântica de permissão de webfetch por agente
  não confirmada; a quarentena contratual + rede negada nos wrappers já cobre o vetor
  principal sem mudança de runtime.
- **Rodada adversarial de C3/C4/C5 e homologação da delegação Claude Code**: pendências
  herdadas, registradas em `opencode/HOMOLOGACAO.md` e `AUDITORIA.md`.

## O que permaneceu intocado

Comandante nativo e hierarquia de três níveis; os sete agentes e seus papéis; contrato
exato de permissões OpenCode e wrappers sandbox; whitelists de ferramentas Claude;
modelos, provedores, Bifrost, MCPs, VPS, SSH e instalações ativas; mascotes, animações,
README (apenas acréscimos de documentação), assinatura de autoria e licença MIT.

<!-- WillTech-General / WILLTECH-BH © 2026 · autoria: github.com/hebwil -->