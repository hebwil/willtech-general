# WILLTECH ULTRA PRO — instalador sem terminal (Claude Desktop / Claude Code)

Este pacote configura **somente o Claude**. Ele não altera OpenCode, VPS, gateways, Bifrost,
Magpie, credenciais, bancos, repositórios remotos nem produção.

## Instalar: duplo clique, sem terminal

1. Abra a pasta `willtech-station` no Finder.
2. Duplo clique em **`INSTALAR.command`**.
3. Confirme na janela que aparece e espere. No fim, o Finder abre o relatório.

Pronto. Você não digita comando, não abre Terminal e não precisa de `PATH`.

Na primeira vez o macOS pode avisar que o arquivo é de um desenvolvedor não identificado.
Nesse caso: clique com o botão direito em `INSTALAR.command` → **Abrir** → **Abrir**.
Só é necessário uma vez.

O instalador se encarrega de achar o Claude Code sozinho. Ele procura na seguinte ordem:
o `PATH`, os caminhos conhecidos de cada forma de instalação, o shell de login do macOS (o que
pega `nvm`, `fnm`, `mise`, `volta`, `bun`), o bundle do Claude Desktop, o `npm prefix -g` e, por
último, o `cli.js` do pacote `@anthropic-ai/claude-code` — que é como o Desktop e o npm instalam.
Se só existir o `cli.js`, ele cria um atalho que chama `node cli.js`; nada muda para você.

No fim ele pergunta se você quer rodar a homologação de verdade (testes A–I). Ela consome tokens
da sua conta, por isso o padrão é **"Agora não"**. Você pode rodar depois pelo mesmo arquivo.

## O que tem aqui

```
willtech-station/
├── INSTALAR.command              duplo clique: instala, valida e oferece homologar
├── agents/                       7 subagentes em formato oficial do Claude Code
│   ├── general/
│   │   └── willtech-general.md   tenente coordenador (Read, Grep, Glob, Agent)
│   └── especialistas/
│       ├── willtech-explorador.md    investigação somente leitura
│       ├── willtech-pesquisador.md   documentação oficial e issues
│       ├── willtech-visual.md        Astro, UI, acessibilidade
│       ├── willtech-executor.md      implementação autorizada
│       ├── willtech-testador.md      testes em ambiente isolado
│       └── willtech-revisor.md       revisão independente
├── settings/willtech-routing.md  bloco para colar no CLAUDE.md
├── bin/_willtech_find_claude.sh  localização do runtime (usado pelos dois scripts)
├── bin/willtech-bootstrap.sh     instalador idempotente com backup e inventário
├── bin/willtech-homologate.sh    arnês dos testes A–I em sessões reais
├── bin/willtech_trace.py         parser de evidência do stream-json
└── HOMOLOGACAO.md                estado real: o que está provado e o que falta
```

## Instalação por linha de comando (opcional)

Se algum dia você quiser pelo Terminal, os mesmos passos:

```sh
cd ~/Documents/"Projeto Cloude Code"/willtech-station
./bin/willtech-bootstrap.sh --check
./bin/willtech-bootstrap.sh --apply
./bin/willtech-homologate.sh --plan
./bin/willtech-homologate.sh --run --yes-spend
```

O script é idempotente: rodar de novo não reinstala nem sobrescreve o que já está igual.
Antes de qualquer alteração, copia o arquivo afetado para `~/.willtech-backups/<timestamp>/`.
Cada execução grava um relatório em `~/.willtech-logs/willtech-station-<timestamp>.md`.

### O que ele faz em cada fase

| Fase | Ação |
|---|---|
| 1 | Inventário: versões, plugins carregados, MCPs, agentes existentes |
| 4 | Copia os 7 agentes para `~/.claude/agents/` mantendo `general/` e `especialistas/`, preserva idênticos, faz backup dos diferentes e remove cópia achatada de instalação anterior |
| 5 | EGM: se já instalado, apenas valida e pula. Senão `claude plugin marketplace add google/elephant-goldfish-model` + `claude plugin install egm@egm` |
| 6 | TokenEconomizer: reusa clone e plugin existentes; configura `microskills=envfacts`, `toolprune=propose`, `toolprune_protect=Agent,Task` |
| 8 | MCPs: Astro Docs e Context7 por HTTP. Serena só se o binário já existir |
| 9 | Confere `settings.json` e o log de hooks, sem alterar |

## Rotas automáticas

Depois de instalar, cole o conteúdo de `settings/willtech-routing.md` no seu `~/.claude/CLAUDE.md`.
Isso faz o comandante escolher a faixa da tarefa sem você nomear agentes:

- pergunta simples → ele mesmo;
- 3+ arquivos ou investigação + implementação → `willtech-general`;
- arquitetura, migração, segurança → `willtech-general` + `willtech-revisor`, e fluxo EGM quando cabível;
- Astro → Astro Docs MCP; UI → `willtech-visual`.

## Depois de instalar, no Desktop

1. Abra o Claude Desktop e entre na **aba Code**.
2. Inicie uma **conversa nova**. Agentes, plugins e hooks só passam a existir em sessões abertas
   depois da instalação — uma aba já aberta continua com a configuração antiga.
3. Confira com uma pergunta simples: "quais agentes você tem disponíveis?"
   Os sete nomes `willtech-*` devem aparecer.

Se algo não aparecer, veja a seção "O que você precisa rodar" em `HOMOLOGACAO.md`. Lá está o que
foi medido de fato e o que ainda depende de sessão autenticada.

## Estado real medido

Medições feitas no runtime real do Claude Code 2.1.325, em HOME de ensaio:

| Componente | Resultado medido |
|---|---|
| `egm@egm` 0.1.1 | instalado, `enabled`; 7 skills, 10 adapters de revisor; custo fixo ~464 tokens/sessão |
| `tokeneconomizer@tokeneconomizer` 0.1.0 | instalado, `enabled`; 6 hooks, 7 slash-commands; ~209 tokens/sessão |
| `te --host claude status` | executou e imprimiu estado do repositório (evidência real, não só arquivo) |
| `te config set microskills=envfacts / toolprune=propose / toolprune_protect=Agent,Task` | aplicado e relido no `config show` |
| Astro Docs `https://mcp.docs.astro.build/mcp` | `✔ Connected` |
| Context7 `https://mcp.context7.com/mcp` | `✔ Connected` |
| 7 agentes WILLTECH | frontmatter validado: name/description/tools/model/color |
| Idempotência | 2ª execução: "VALIDADO — PULAR" nos agentes e plugins, 0 backups, 0 reescritas |
| Descoberta do runtime | achou o `claude` a partir de ambiente limpo (`env -i`, sem PATH) e também quando só existe `cli.js` |

## O que não pôde ser provado aqui

Esta sessão roda em **sandbox Linux isolado**, não no seu Mac. `~/.claude` do Mac é local protegido
e não pode ser montado. Portanto:

- os plugins foram instalados e verificados no runtime real do CLI (mesma versão 2.1.325), mas em
  HOME de ensaio — não no seu HOME;
- a carga efetiva de agentes e skills em uma sessão nova do seu Claude Desktop não foi observada;
- a delegação automática do comandante ao `willtech-general` **não foi observada** em sessão
  autenticada sua. É exatamente isso que os testes C, D e H do arnês medem;
- Bivia, Laya, GitHub MCP, Chrome DevTools e Playwright não foram instalados: exigem sua conta,
  seu token ou decisão de processo residente;
- OpenCode não foi tocado, por regra.

Rodar `INSTALAR.command` no seu Mac conclui a instalação de fato. Ele verifica antes de instalar,
então os itens já bons são pulados, não duplicados.
