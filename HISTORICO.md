# Histórico das versões

Linhagem reconstruída a partir dos arquivos preservados na estação.

## v1 — Executor Técnico Subordinado (pré-comercial)

Arquivo: `history/willtech-general.pre-comercial.md`
Preservada em: `~/willtech/evidence/` (evidência de homologação)

- Papel: **executor direto** — investigava, editava e validava por conta própria,
  devolvendo evidências ao comandante.
- Frontmatter Claude: `tools: Bash, Read, Edit, Write, Glob, Grep`.
- Sem especialistas subordinados: não havia camada de delegação.

## v2 — Tenente Coordenador (Claude Code)

Arquivo: `claude-code/agents/general/willtech-general.md`
Origem: pacote "WILLTECH ULTRA PRO" (`willtech-station`), formato Claude Code.

- Mudança arquitetural: de executor para **coordenador** — passou a delegar aos
  6 especialistas e consolidar parecer único.
- Frontmatter: `tools: [Read, Grep, Glob, Agent]`, `model: inherit`, `color: cyan`.
- "Contrato de operação" com 7 pontos (escopo explícito, decomposição, mínimo de
  especialistas, delegação com contexto fechado, exigência de evidência, consolidação,
  revisão independente antes de declarar conclusão).
- Vem acompanhado do bloco de roteamento (`settings/willtech-routing.md`) que ensina
  o comandante a classificar tarefas: trivial / pequena / complexa / crítica.

## v3 — Tenente Coordenador OpenCode (ativa na estação)

Arquivo: `opencode/agent/willtech-general.md`
Instalada em: `~/.config/opencode/agent/` (14/11/2026)

- Adaptação de plataforma: frontmatter trocado para `mode: subagent`;
  delegação via ferramenta `subagent`.
- Contrato condensado (4 passos + matriz de especialistas), mantendo as regras
  essenciais: evidência obrigatória, 2 tentativas, REAPROVEITAR, sem sudo/push,
  sinalização "REVISÃO INDEPENDENTE RECOMENDADA".
- Instalada junto com os 6 especialistas adaptados ao mesmo formato.

## Correspondência de especialistas entre variantes

Os 6 especialistas existem nas duas variantes com o mesmo papel:

| Especialista | Claude Code | OpenCode |
|---|---|---|
| explorador, pesquisador, visual, executor, testador, revisor | `agents/especialistas/*.md` | `opencode/agent/*.md` |
