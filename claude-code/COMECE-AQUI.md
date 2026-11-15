# Comece aqui — instalar sem terminal

Três passos. Nenhum deles pede comando, PATH ou Terminal.

## 1. Duplo clique em `INSTALAR.command`

Abra a pasta `willtech-station` no Finder e dê duplo clique em `INSTALAR.command`.
Uma janela de terminal abre sozinha — isso é normal, ela mostra o progresso e pode ser fechada
no fim.

Na primeira vez o macOS pode bloquear: clique com o **botão direito** no arquivo → **Abrir** →
**Abrir**. Só precisa fazer isso uma vez.

Ele vai:

- localizar o Claude Code sozinho (inclusive quando ele só existe como `cli.js`, que é como o
  Desktop instala);
- instalar os 7 agentes em `~/.claude/agents/`;
- instalar EGM e TokenEconomizer, se ainda não estiverem;
- configurar Astro Docs e Context7;
- **não** tocar no que já está correto.

## 2. Abra o Claude Desktop na aba Code e comece uma conversa NOVA

Agentes, plugins e hooks só existem em sessões abertas **depois** da instalação. Uma aba que já
estava aberta continua com a configuração antiga. Esse é o passo que a maioria esquece.

Confira com uma pergunta simples, digitando na conversa:

> quais agentes você tem disponíveis?

Os sete nomes devem aparecer: `willtech-general`, `willtech-explorador`, `willtech-pesquisador`,
`willtech-visual`, `willtech-executor`, `willtech-testador`, `willtech-revisor`.

Eles ficam em `~/.claude/agents/general/` e `~/.claude/agents/especialistas/`. Subpasta não é
enfeite: o Claude Code lê esse diretório recursivamente e pega o nome do campo `name` de cada
arquivo. Isso foi verificado no runtime 2.1.325, não presumido.

## 3. Cole o roteamento no CLAUDE.md (opcional, mas é o que ativa a delegação automática)

Sem isso, os agentes existem mas ninguém os convoca por conta própria. Com isso, o comandante
escolhe a faixa da tarefa sozinho.

Abra `settings/willtech-routing.md`, copie o bloco, e cole no fim do arquivo
`~/.claude/CLAUDE.md`. Se o arquivo não existir, crie.

Pelo Finder: **Ir** → **Ir para a Pasta** → digite `~/.claude` → Enter. O `CLAUDE.md` fica lá.

---

Se você chegou até aqui e algo falhou: abra `~/.willtech-logs/`, o relatório mais recente diz
exatamente qual componente ficou pendente e por quê. Nada é declarado pronto sem evidência.
