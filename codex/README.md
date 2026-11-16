# WillTech-General — Codex

Variante para o Codex nativo, com `willtech-general` como subagente coordenador e
seis especialistas. Os arquivos `.toml` correspondem à configuração ativa em
`~/.codex/agents/`.

## Instalação

1. Faça backup:

   ```sh
   cp -a ~/.codex/agents ~/.codex/agents.backup-$(date +%Y%m%d-%H%M%S)
   ```

2. Copie os sete arquivos:

   ```sh
   cp codex/agents/*.toml ~/.codex/agents/
   ```

3. Inicie uma sessão nova e confirme os sete nomes `willtech-*`.

## Diferenças

O Codex usa `developer_instructions` em TOML e não publica um campo de permissões
por agente equivalente ao OpenCode. Os limites de leitura e escrita são
instruções de comportamento; a garantia final depende do runtime e do ambiente
de execução. Para operações sensíveis, mantenha aprovação do comandante e use o
especialista apropriado.

## Evidência local

- 7 agentes registrados em sessão real do Codex.
- Delegação comandante → General → especialista confirmada.
- Em teste adversarial de 15/11/2026, o runtime **permitiu** que o
  `willtech-explorador` escrevesse. Isso confirma que o TOML/instruções não são
  uma barreira de segurança no Codex; não trate esta variante como isolamento
  equivalente ao OpenCode.
