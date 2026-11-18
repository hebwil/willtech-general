# BLOQUEIO DE PUBLICAÇÃO — WillTech-General v3.1.0

**Estado:** BLOQUEADO — documento de controle da release, não equivale a homologação. **Sem tag, sem release e sem merge automático deste PR.**

## Motivo

O proprietário determinou **não publicar com pendências reais**. A release v3.0.0 permanece publicada e imutável; a linha v3.1.0 não pode ser distribuída como versão final enquanto existirem os itens abaixo.

## Requisitos ainda não comprovados

1. **Modo C e preservação funcional:** no benchmark real [44402745515](https://github.com/hebwil/willtech-general/actions/runs/44402745515), baseline A e JIT B acertaram **8/9**, enquanto C acertou **7/9**. T3 complexa: A=2/3, B=2/3, C=1/3. Sem evidência de que seja regressão sistemática, mas **não há comprovação de não regressão do modo C**. Resolver por correção causal comprovada e novo benchmark comparável **ou** retirar o C do escopo distribuído/garantido com teste que prove desativação por padrão e ausência de impacto no comportamento final. Não alterar o gabarito para aumentar PASS.
2. **Painel gráfico nativo dos sete mascotes:** a aplicação OpenCode Desktop e o carregamento do plugin foram verificados, mas **a pintura/abertura do painel no Desktop real permanece NC**. Se o painel é requisito de publicação como funcional, obter evidência nativa autêntica; não converter teste Chromium ou imagem simulada em PASS.
3. **Integração com Codex e Claude Code em sessão autenticada com modelo:** documentação atual não demonstra fluxos completos de delegação/hooks com modelo real para ambos. Testes determinísticos e protocolo App Server não são equivalentes. Não usar credenciais ou cobrança pessoais; se não houver laboratório autorizado, manter BLOQUEADO e solicitar decisão explícita sobre escopo, sem declarar PASS.
4. **Distribuição v3.1.0 ainda não homologada:** executar CI 5/5 no **SHA exato** destinado à tag; gerar `willtech-general-3.1.0.tar.gz` com `MANIFEST.json` e `SHA256SUMS.txt`; provar instalação, atualização, desativação e desinstalação com artefato extraído e verificação remota. Teste de pacote **não** é publicação e não pode usar uma release pública prematuramente.
5. **Provas e revisão final:** evidências observáveis, limites, relatório sem contradições, revision SHA exato e revisor independente com parecer rastreável. Corrigir apenas falhas efetivamente reproduzidas. Sem loops de monitoramento ou PRs cosméticos.

## Condições para remover o bloqueio

Somente **depois de comprovar todos os itens exigidos** com links de execuções, artefatos, hashes e resultados funcionais é permitido:
- Criar novo commit retirando este bloqueio, com PR revisado.
- Executar os gates no commit exato da distribuição.
- Publicar **uma vez**, depois da verificação do draft, dos checksums e da instalação limpa.
- Verificar a release pública a partir do próprio arquivo baixado.

**Enquanto este arquivo existir na branch, a automação de publicação falhará antes de criar tag/release.** Não mudar a condição para passar sem evidências. Não modificar a tag/release `v3.0.0`.

**Estado desta versão:** EM PREPARAÇÃO. **NÃO PUBLICADA.**
