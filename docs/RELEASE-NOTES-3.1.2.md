# WillTech-General v3.1.2 — resolução autônoma de Python >= 3.12 no OpenCode Desktop e robustez multiplataforma

**Escopo desta versão:** Versão patch de robustez e compatibilidade da linha v3.1. Preserva integralmente os sete agentes, contratos de autoridade, arquitetura da Sala dos Agentes SQLite v3, JIT adaptativo e as suítes de homologação das três plataformas (OpenCode, Codex e Claude Code).

---

## O que muda na v3.1.2

1. **Resolução Autônoma e Resiliente de Python >= 3.12 no Plugin OpenCode (`opencode/plugins/willtech/index.js`):**
   - No macOS, aplicativos iniciados pelo Finder/Dock (como o OpenCode Desktop) herdam o ambiente restrito do `launchd` (`PATH=/usr/bin:/bin:/usr/sbin:/sbin`), onde o Python padrão é frequentemente uma versão do sistema inferior a 3.12 (ex.: `/usr/bin/python3` 3.9.6 do Xcode Command Line Tools).
   - O plugin agora descobre autonomamente o interpretador compatível em diretórios padrão do sistema e de gerenciadores modernos (Homebrew, uv em `~/.local/share/uv/python/*/bin`, `~/.local/bin`, Python.framework, pyenv e AppData no Windows) e em `.willtech/installed.json`, validando rigorosamente cada candidato via `spawnSync` com checagem de versão `sys.version_info >= (3, 12)`.
   - Elimina por completo qualquer necessidade de soluções locais paliativas, como LaunchAgents, shims no PATH ou modificações nas variáveis globais do sistema operacional.

2. **Sanitização de AST e Guard Explícito de Versão em `tools/willtech-auto.py`:**
   - Correção da f-string com sanitização de expressões para garantir compatibilidade sintática (AST) em qualquer interpretador Python, evitando `SyntaxError` prematuro em versões < 3.12.
   - Adicionado guard explícito de versão no início do script: se invocado sob Python < 3.12, emite mensagem clara em `stderr` (`WillTech: Python >= 3.12 é obrigatório`) e finaliza de forma controlada com código 1, sem tracebacks corrompidos.

3. **Validação Estrita de Python >= 3.12 nos Instaladores (`tools/willtech-install.sh` e `willtech-install.ps1`):**
   - Ambos os instaladores agora verificam a disponibilidade de Python >= 3.12 antes de realizar alterações no projeto.
   - Caso nenhum interpretador compatível seja localizado, a instalação é recusada de forma limpa com código de saída 2 e mensagem orientativa ao desenvolvedor.
   - O interpretador detectado é registrado no arquivo de estado `.willtech/installed.json` (chave `python`), servindo de referência confiável para plugins e hooks.

4. **Nova Suíte de Testes Automatizada dos 4 Cenários (`tools/test-python-resolver.py`):**
   - **Cenário A (macOS Finder PATH):** Comprova que sob `PATH=/usr/bin:/bin:/usr/sbin:/sbin` o plugin do OpenCode descobre autonomamente o Python >= 3.12 e executa a automação sem falhas sintáticas.
   - **Cenário B (Ausência de Python compatível):** Comprova a recusa do instalador com código 2 e o comportamento seguro (fail-open) do plugin, sem travar o host do editor.
   - **Cenário C (Operação normal):** Comprova a instalação, escrita de `installed.json` e execução bem-sucedida de consultas e escrita na Sala SQLite v3.
   - **Cenário D (Multiplataforma e ausência de caminhos hardcoded):** Comprova a ausência de diretórios hardcoded de desenvolvimento e a integridade em Linux, macOS e Windows.

5. **Distribuição e Verificação da Release:**
   - Novo workflow de publicação `.github/workflows/publish-v3.1.2.yml` com integridade rigorosa pré e pós-release.
   - As tags anteriores `v3.0.0`, `v3.1.0` e `v3.1.1` permanecem imutáveis.

---

## Resultados e Paridade Tecnológica

- A inteligência adaptativa, a Sala dos Agentes SQLite v3 e a redução comprovada de até **−45,40% de novos tokens de entrada** no Modo B com **8/9 acertos funcionais** permanecem integralmente preservadas.
- Custo financeiro total: **US$ 0,00**.
