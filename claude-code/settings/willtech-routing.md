# WILLTECH — roteamento automático

Cole este bloco no seu `~/.claude/CLAUDE.md` (ou no `CLAUDE.md` do projeto, se quiser por projeto).
Não substitui `settings.json`; é instrução persistente.

---

## Estação WILLTECH

O comandante é o agente principal nativo desta sessão. A hierarquia abaixo é subordinada a ele;
nunca a substitui e nunca cria outro agente principal.

Antes de agir, classifique a tarefa e declare a faixa em uma linha:

- **trivial** — pergunta factual, um arquivo, mudança reversível: resolva sozinho, sem delegar.
- **pequena** — um ou dois arquivos localizados: resolva com suas ferramentas nativas.
- **complexa** — três ou mais arquivos, ou investigação somada a implementação e teste: delegue ao
  subagente `willtech-general`, que coordena os especialistas e devolve um parecer único.
- **crítica** — arquitetura, migração, segurança, dados, contrato público: `willtech-general` mais
  revisão independente de `willtech-revisor`. Em decisão arquitetural relevante, execute o fluxo
  EGM oficial (`/egm:egm-review`) com revisores em contexto novo.

Especialistas disponíveis: `willtech-explorador` (leitura), `willtech-pesquisador` (fontes
oficiais), `willtech-visual` (Astro, UI, acessibilidade), `willtech-executor` (escopo autorizado),
`willtech-testador` (ambiente isolado), `willtech-revisor` (revisão independente).

Regras de execução:

1. Não acione especialista para tarefa trivial. Não mantenha três agentes ativos por obrigação.
2. Antes de instalar ou configurar algo, verifique se já existe e funciona. Se sim, teste rápido e
   registre VALIDADO — PULAR. Não reinstale, não reconfigura, não duplica.
3. Um componente tem direito a uma instalação e uma correção com causa identificada. Depois disso,
   marque BLOQUEADO com o erro exato e siga adiante.
4. Não repita comando que já falhou pela mesma causa. Não alterne métodos de instalação.
5. Toda conclusão precisa de evidência: comando e saída, arquivo e linha, resultado de teste.
   Não declare homologado o que só rodou em sandbox.
6. Fora de escopo, sempre: credenciais e `.env`, gateways, VPS, bancos de produção, repositórios
   remotos, configuração do OpenCode, `sudo`, `bypassPermissions`, `git push`.
7. Ferramentas sob demanda: documentação oficial do framework em uso primeiro; Context7 para
   bibliotecas; Playwright para fluxo e regressão de navegador; Chrome DevTools para desempenho —
   não os dois por padrão. Bivia ou Laya só quando houver benefício concreto, e nunca as duas na
   mesma decisão.
8. Entregue em português, com o que foi feito, evidência, pendências e bloqueios.

Ferramentas de delegação, EGM e agentes nunca devem ser removidos por tool pruning.
