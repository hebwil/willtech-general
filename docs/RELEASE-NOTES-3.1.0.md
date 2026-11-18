# WillTech-General v3.1.0 — inteligência adaptativa e Sala dos Agentes

**Escopo estável desta versão:** núcleo projeto-local, sete agentes (General + seis especialistas), SQLite Sala dos Agentes, JIT adaptativo, RepoMap direcionado, handoffs, guards e distribuição reversível. Autoridade continua com o comandante nativo (OpenCode, Codex, Claude Code). A Sala não é oitavo agente.

## Mudanças desde v3.0.0

- Sala SQLite v3 com evidências, isolamento entre projetos, validação, busca JIT, estados `candidate`/`validated`/`stale`, handoffs e micro-skills com aprovação humana.
- JIT adaptativo **opt-in**, seleção por relevância/especialidade e expansão sob demanda; comportamento anterior como fallback seguro.
- RepoMap com reuso por SHA-256, ranking por relações e busca direcionada.
- Pacotes de contexto por especialidade, preservando contexto integral sob demanda e revisão independente.
- Exportação/importação de padrões genéricos condicionada a autorização, sem compartilhar salas privadas.
- Saídas estruturadas opcionais com logs e hashes verificáveis; guardas anti-loop e tratamento de segredos preservados.
- Correções de compatibilidade de `read`/`grep` no host OpenCode e de `PWD` no laboratório.
- Distribuição reproduzível por VERSION + MANIFEST + SHA256SUMS; instalação/desativação/desinstalação verificadas em laboratório limpo.

## Resultados que realmente foram medidos

Benchmark autêntico [run 44402745515](https://github.com/hebwil/willtech-general/actions/runs/44402745515): 27 execuções, Qwen3-1.7B-Q4_K_M local em runners gratuitos, três tarefas × três repetições × três modos; os critérios não foram afrouxados.

| Métrica | A (sem novo JIT) | B (JIT adaptativo) | C (completo) |
| --- | ---: | ---: | ---: |
| Sucesso funcional | 8/9 | **8/9** | 7/9 |
| Novos tokens de entrada | 5.970,3 | **3.259,9 (−45,40%)** | 3.291,7 (−44,87%) |
| Tokens entrada+saída, sem cache | 6.139,0 | 3.433,8 (−44,07%) | 3.428,6 (−44,15%) |
| Volume incluindo leitura de cache | 13.167,3 | 16.090,3 (+22,20%) | 16.154,6 (+22,69%) |
| Duração média | 73,99 s | 76,67 s (+3,61%) | 65,91 s (−10,93%) |

T3 complexa: A=2/3, B=2/3, C=1/3. **C é experimental e não é recomendação universal**, pois apresentou regressão nessa amostra. A redução de tokens novos de B é um resultado medido neste laboratório; não equivale a redução comprovada de preço de API. Custo financeiro do benchmark local: US$ 0,00, não promessa de gratuidade de serviços externos.

## Homologação e distribuição

A publicação automatizada exige **CI 5/5 no SHA do pacote**, Windows, macOS, Ubuntu, host oficial OpenCode e smoke de inteligência; testes de distribuição a partir de um arquivo tar.gz real; manifestos e checksums iguais aos bytes distribuídos; tag imutável. Workflow: `.github/workflows/publish-v3.1.0.yml`. A aprovação deste workflow só é válida se **todos** os passos concluírem com `success`.

Artefatos esperados: `willtech-general-3.1.0.tar.gz`, `MANIFEST.json` e `SHA256SUMS.txt`. O arquivo pertence ao commit exato apontado pela tag. Verificação em runner limpo: `tools/verify-release.py`.

O `v3.0.0` anterior permanece imutável. A nova versão não altera configurações pessoais durante o build/teste; instaladores são projeto-locais, explícitos e reversíveis.

## Limitações declaradas — não converter em PASS

- **Modelo:** resultados funcionais não são 100% no Qwen3-1.7B; desempenho em modelos maiores, provedores pagos ou outros projetos não foi demonstrado por este benchmark.
- **Modo C:** 7/9 versus 8/9 da baseline, em apenas três tarefas; permaneça opt-in, com contexto integral disponível quando necessário.
- **Runtimes Codex e Claude Code com modelo autenticado:** hooks/contratos e App Server têm testes, mas execução completa com contas do usuário não foi homologada no laboratório gratuito. Não utilizar credenciais pessoais para fabricar PASS.
- **Painel visual nativo do OpenCode Desktop:** o Desktop e a carga do plugin GUI foram comprovados, mas o painel dos sete mascotes no Desktop real permanece **NC (não comprovado)**; validação Chromium não equivale ao render nativo.
- **Revisão independente:** testes de independência e CI não equivalem a aprovação formal de qualidade para todo modelo/projeto.
- **Não confundir** teste determinístico, integração, sessão real de modelo, distribuição e interface gráfica nativa.

O pacote pode ser distribuído como núcleo **v3.1.0** somente após passar os gates listados; as integrações e interfaces experimentais são identificadas como tais. Nunca anunciar "FULL PASS universal".
