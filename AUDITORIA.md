# Auditoria independente — 15/11/2026

## Resultado por plataforma

| Item | Claude Code | OpenCode | Codex |
|---|---|---|---|
| 7 agentes definidos | Sim | Sim | Sim |
| Instalação ativa local | Não (`~/.claude/agents` ausente) | Sim | Sim |
| Delegação real observada | Não | **Sim** | Sim |
| Bloqueio real de escrita pelo explorador | Não testado | **Sim** | Não |

## Evidências

- Commit `60e3097cd90e922e06195e205520e052dd42aa40`, branch `main`, 29 arquivos.
- `git fsck --full --no-dangling`: sem erro.
- Comparação com o projeto original: apenas `.DS_Store` e assinaturas de autoria diferem.
- Comparação OpenCode publicada e ativa: apenas as assinaturas de autoria.
- Sessão Codex: 7 agentes visíveis; leitura delegada concluída; tentativa de escrita
  pelo explorador negada pelo runtime.
- `bash -n`: todos os scripts shell sintaticamente válidos.
- `python3 -m py_compile`: `willtech_trace.py` válido.
- Varredura de segredos: nenhuma credencial encontrada.

## Achados

1. A variante Codex, única com hierarquia ativa e permissão real observada, não estava no repositório.
2. O `~/.claude/agents` local não existe, portanto a variante Claude Code permanece pacote preservado, não instalação ativa.
3. O OpenCode tem permissões declaradas por agente; o Codex depende de instruções e do runtime.
4. A documentação admitia corretamente que a delegação automática em Claude Code ainda não estava homologada.

## Correção aplicada

- Inclusão da variante Codex com os sete agentes ativos.
- Atualização de `README.md` e `INSTALL.md`.
- Registro desta auditoria em `AUDITORIA.md`.

## Rodada 2 — validação real e pendências

### OpenCode

- Runtime OpenCode 2.2.6 localizado no app desktop e executado em modo headless.
- Agentes visíveis: `willtech-general`, `willtech-executor`, `willtech-explorador`,
  `willtech-pesquisador`, `willtech-revisor`, `willtech-testador` e `willtech-visual`.
- Delegação comandante → General → especialista executada com sucesso.
- Tentativa de escrita pelo `willtech-explorador` foi negada por ausência de
  ferramenta de escrita/perfil somente leitura.
- Repositório permaneceu inalterado após os testes.

### Falhas adversariais comprovadas (rodada 3)

Testes com comandos reais no runtime 2.2.6 mostraram quatro brechas que a
configuração anterior não fechava:

1. **Shell livre nos agentes de leitura.** Declarar apenas `edit: deny` não impedia
   `shell`, porque o runtime começa com `allow` e aplica a última regra que casa.
   General e especialistas de leitura conseguiam escrever via shell.
2. **Delegação a partir do Explorador.** O Explorador conseguia acionar o Executor e
   contornar a hierarquia.
3. **Testador sem isolamento efetivo.** Não havia confinamento de escrita por
   diretório.
4. **Ferramentas nativas de worktree.** `opencode_worktree_create` criou um worktree
   mesmo com `edit: deny` e `execute: deny`; a ferramenta tem ação de permissão
   própria.
5. **Redirecionamento fora do sandbox.** Com o wrapper sem aspas, o `>` era
   interpretado pelo shell externo antes do `sandbox-exec`, permitindo escrever
   fora do laboratório.

### Correções aplicadas

- Agentes de leitura (Explorador, Pesquisador, Visual, Revisor) e General:
  `shell`, `edit`, `subagent` (exceto General), `execute`,
  `opencode_worktree_create` e `opencode_worktree_remove` negados.
- Shell liberado apenas por `willtech-read-shell "COMANDO"` (leitura) e
  `willtech-test-shell "COMANDO"` (Testador), com o comando inteiro entre aspas.
- Executor: `subagent` e `execute` negados; `git push`, `sudo` e `rm -rf` negados.
- Testador: escrita confinada a `~/willtech-lab`; rede, SSH, `.env` e configuração
  bloqueados pelo `sandbox-exec`.
- Gatilho de delegação no `AGENTS.md` do comandante, versionado em
  `opencode/AGENTS.md`.

### Matriz de homologação (runtime real)

| Cenário | Resultado |
|---|---|
| Explorador: shell direto / escrita / `subagent` / worktree | todos negados, sem arquivo |
| General: shell direto / escrita / worktree | todos negados, sem arquivo |
| Visual, Pesquisador, Revisor: shell direto | negados |
| Executor: escrita no laboratório | concluída |
| Executor: `subagent` e `git push` | negados |
| Testador: shell direto | negado; somente o wrapper é aceito |
| Testador: escrita dentro de `~/willtech-lab` | concluída |
| Testador: escrita fora de `~/willtech-lab` | `Operation not permitted` |
| General → Explorador | `subagent` concluído |
| Comandante → General em 3 arquivos / multi-etapa | delegou ao General |
| Comandante em tarefa de 1 arquivo | resolveu direto, sem delegação |
| Injeção `>`, `>>`, `&&`, `;`, `\|`, `$()`, backtick, sem aspas | todas negadas |

Evidências reproduzíveis sem custo de modelo: `sh opencode/tests/test-wrappers.sh`
(37 verificações aprovadas). Matriz completa em `opencode/HOMOLOGACAO.md`.

### Instalação ativa

- Backup: `~/.willtech-backups/opencode-20261115-214945-final/`.
- Agentes em `~/.config/opencode/agent/` e wrappers em `~/.config/opencode/bin/`
  idênticos aos arquivos versionados.
- `opencode.json`, provedores, MCPs, Bifrost e VPS não foram alterados.
- `opencode debug agents` confirmou as permissões novas nos sete agentes.

### Estado final do repositório

| Item | Valor confirmado |
|---|---|
| Branch | `main` |
| Commit das correções | `52295092b1c39d31865e9b6efa99c0dc8b1aa34b` |
| Push para `origin/main` | confirmado por `git ls-remote` e API do GitHub |
| Visibilidade | **privada** |
| Árvore de trabalho | limpa e sincronizada |
| Wrappers/testes versionados | 3 arquivos com modo `100755` |
| Regressão pós-rebase | 37 PASS, 0 FAIL |

O commit documental imediatamente posterior registra este estado; o hash acima é
o commit de código e configuração efetivamente enviado ao remoto.

### Codex

- Os sete arquivos `.toml` permanecem idênticos aos agentes ativos.
- Novo teste de isolamento confirmou que o runtime permitiu escrita ao
  `willtech-explorador`; o arquivo de prova foi removido imediatamente.
- Risco real: isolamento no Codex é dependente do runtime e do contexto, não é
  garantia declarativa como no OpenCode.

### Claude Code

- `~/.claude/agents` permanece ausente; nenhuma instalação foi feita.
- A variante continua sendo pacote preservado e não homologado na superfície real.
- O `INSTALAR.command`, antes apenas citado, foi incluído como wrapper explícito do
  `willtech-bootstrap.sh --apply`.
- Delegação automática permanece **NÃO TESTADA** no Claude Code real.

### Referências e licença

- Referências quebradas ao `INSTALAR.command` foram resolvidas com o arquivo real.
- Caminhos de instalação do Claude Code corrigidos em `INSTALL.md`.
- Licença MIT presente e registrada no `README.md`.

## Nota de estado — 16/11/2026

- A visibilidade registrada acima (**privada**) era a vigente na data desta auditoria.
  O repositório foi tornado público posteriormente; acesso anônimo à API do GitHub
  confirmado em 16/11/2026. O registro histórico foi preservado sem alteração.
- Rodada independente de 16/11/2026 (Qoder): regressão dos wrappers reproduzida
  (37/37 na suíte original), denylist de credenciais ampliada, suíte endurecida com
  contrato estrutural e teste de mutação. Detalhes em `opencode/HOMOLOGACAO.md`.
