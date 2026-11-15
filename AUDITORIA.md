# Auditoria independente — 15/11/2026

## Resultado por plataforma

| Item | Claude Code | OpenCode | Codex |
|---|---|---|---|
| 7 agentes definidos | Sim | Sim | Sim |
| Instalação ativa local | Não (`~/.claude/agents` ausente) | Sim | Sim |
| Delegação real observada | Não | Não testado | Sim |
| Bloqueio real de escrita pelo explorador | Não | Não testado | Sim |

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
