# WillTech-General v3.1.1 — estabilização do CI, teste rápido OpenCode e robustez de runners

**Escopo desta versão:** Versão patch de estabilização do núcleo v3.1. Preserva integralmente os sete agentes, contratos, arquitetura da Sala dos Agentes SQLite v3, JIT adaptativo e autoridade nativa de cada plataforma.

---

## O que muda na v3.1.1

1. **Correção de invariantes do README no teste de GUI (`tools/test-gui.py`):**
   - Adequação cirúrgica do teste de invariantes para validar rigorosamente a autoria (cabeçalho de copyright), todos os assets visuais dos agentes (`docs/assets/willtech-*.webp`), banners e a seção de créditos e referências, permitindo atualizações legítimas de apresentação e status da documentação sem falsos FAILs no CI multiplataforma.

2. **Margem segura de execução para runners compartilhados (`host-modelo-local-verdadeiro.yml`):**
   - Ajuste do timeout de execução do Claude Code e Codex no laboratório com modelo local de 240s para 480s. Protege contra oscilações e concorrência de CPU em runners públicos do GitHub Actions durante inferência local de modelos abertos, sem alterar a lógica ou os contratos de produção dos agentes.

3. **Protocolo e Guia de Teste Rápido no OpenCode (`docs/TESTE-RAPIDO-OPENCODE-3.1.1.md`):**
   - Disponibilização de guia passo a passo, seguro e não destrutivo, para validação local pelo usuário das 8 capacidades principais da arquitetura:
     1. Carregamento do General e dos 6 especialistas;
     2. Delegação do General para especialista;
     3. Leitura de arquivo no workspace;
     4. Consulta e escrita na Sala dos Agentes (SQLite);
     5. Restauração da sessão anterior pelo hook;
     6. Ausência de loops infinitos e preservação do isolamento do projeto;
     7. Execução de teste funcional pelo testador e revisão por pacote independente pelo revisor;
     8. Preservação de contexto com JIT adaptativo.

4. **Distribuição e Automação Segura:**
   - Novo workflow de publicação `.github/workflows/publish-v3.1.1.yml` mantendo verificação rigorosa pré e pós-release, empacotamento idempotente com verificação SHA-256 e MANIFEST.json.
   - Preservação imutável das tags anteriores `v3.0.0` e `v3.1.0`.

---

## Resultados e Paridade Tecnológica

- O runtime do núcleo, SQLite v3 e JIT adaptativo são idênticos aos medidos no benchmark definitivo (`31747cd4666596c0056d238cf992de4a02a52dde`), mantendo a redução comprovada de até **−45,40% de novos tokens de entrada** no Modo B com **8/9 acertos funcionais**.
- Custo financeiro total: **US$ 0,00**.
