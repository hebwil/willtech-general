# Homologação OpenCode — WillTech-General

Runtime: **OpenCode 2.2.6** (`opencode-cli`, app desktop macOS arm64).
Configuração ativa: `~/.config/opencode/opencode.json` e `~/.config/opencode/agent/`.
Data dos testes: 15/11/2026. Todos os testes de escrita usaram diretório descartável.

## Regras do runtime que motivaram as correções

| Regra verificada | Consequência |
|---|---|
| Permissões são ordenadas; **a última regra que casa vence** | negar uma ação específica não impede escrita por shell |
| Todo agente começa com `action: "*"`, `resource: "*"`, `effect: allow` | `edit: deny` sozinho não bloqueia `shell`, `execute` nem ferramentas nativas |
| `shell.resource` é texto bruto e não expande `~` | os padrões usam `*/.config/opencode/bin/...` |
| Ferramentas nativas `opencode_worktree_*` têm ação própria | precisam de `deny` explícito; `edit: deny` não as cobre |
| O texto após o nome do wrapper é **analisado pelo shell externo** | sem aspas, `>` é executado fora do sandbox |

## Matriz de testes no runtime real

### Controle de escrita

| Cenário | Resultado observado | Estado |
|---|---|---|
| Explorador: `shell` direto | `Permission denied: shell`, sem arquivo | HOMOLOGADO |
| Explorador: ferramenta de escrita | ferramenta ausente, sem arquivo | HOMOLOGADO |
| Explorador: `subagent` para o Executor | ferramenta ausente, sem efeito | HOMOLOGADO |
| Explorador: `opencode_worktree_create` | ferramenta ausente, sem worktree | HOMOLOGADO |
| General: `shell` direto | `Permission denied: shell`, sem arquivo | HOMOLOGADO |
| General: ferramenta de escrita | ferramenta ausente, sem arquivo | HOMOLOGADO |
| General: `opencode_worktree_create` | ferramenta ausente, sem worktree | HOMOLOGADO |
| Visual / Pesquisador: `shell` direto | `Permission denied: shell` | HOMOLOGADO |
| Revisor: `shell` direto | recusa e ausência de ferramenta de escrita | HOMOLOGADO |
| Testador: `shell` direto | somente o wrapper é aceito; escrita fora falha | HOMOLOGADO |

### Execução autorizada

| Cenário | Resultado observado | Estado |
|---|---|---|
| Executor: criar arquivo no laboratório | arquivo criado com o conteúdo esperado | HOMOLOGADO |
| Executor: `subagent` | ferramenta ausente | HOMOLOGADO |
| Executor: `git push` | negado (regra e instrução) | HOMOLOGADO |
| Testador: escrita dentro de `~/willtech-lab` | arquivo criado via wrapper | HOMOLOGADO |
| Testador: escrita fora de `~/willtech-lab` | `Operation not permitted`, sem arquivo | HOMOLOGADO |
| Testador: `;` dentro do comando citado | sandbox bloqueia a escrita | HOMOLOGADO |

### Delegação

| Cenário | Resultado observado | Estado |
|---|---|---|
| General → Explorador (leitura) | `subagent` concluído, resposta consolidada | HOMOLOGADO |
| `experimental.subagent_depth: 2` | duas camadas efetivas (comandante → General → especialista) | HOMOLOGADO |
| Gatilho de delegação: 3 arquivos | primeira ação foi `subagent` → `willtech-general` | HOMOLOGADO |
| Gatilho de delegação: tarefa multi-etapa | primeira ação foi `subagent` → `willtech-general` | HOMOLOGADO |
| Tarefa de 1 arquivo | resolvida direto, sem delegação | HOMOLOGADO |

### Injeção e contorno

| Tentativa | Resultado |
|---|---|
| `wrapper "cmd" > /tmp/fora` | `Permission denied: shell` |
| `wrapper "cmd" >> /tmp/fora` | `Permission denied: shell` |
| `wrapper "cmd" && ...` | `Permission denied: shell` |
| `wrapper "cmd"; ...` | `Permission denied: shell` |
| `wrapper "cmd" \| tee ...` | `Permission denied: shell` |
| `wrapper "$(cmd)"` | `Permission denied: shell` |
| `wrapper "\`cmd\`"` | `Permission denied: shell` |
| `wrapper` sem aspas | `Permission denied: shell` |
| redirecionamento **dentro** das aspas | executa, mas o sandbox confina a escrita |

## Reprodução sem custo de token

```sh
sh opencode/tests/test-wrappers.sh
```

O teste usa `WILLTECH_LAB_ROOT` temporário, não chama modelo nem provedor e cobre:
sintaxe e permissão de execução dos wrappers, leitura permitida, escrita negada no
wrapper de leitura, escrita permitida/negada no wrapper de teste, bloqueio de rede e
as declarações de permissão dos sete agentes.

## Limitações conhecidas

- O isolamento vale para o runtime OpenCode 2.2.6 com estas declarações. Uma versão
  futura pode renomear ações ou ferramentas nativas; reexecute a matriz após atualizar.
- `sandbox-exec` é específico do macOS. Em Linux, os wrappers precisam de um mecanismo
  equivalente (por exemplo `bubblewrap`) antes de reutilizar esta configuração.
- O Executor tem escrita ampla por desenho: o escopo é limitado por instrução e pelo
  comandante, não por sandbox de diretório. Não há como confinar escrita por escopo
  arbitrário sem quebrar a implementação autorizada.
- O comando do wrapper deve ir **inteiro entre aspas duplas**. Hábitos antigos com
  `wrapper cmd` passam a ser negados pelo runtime; isso é intencional.
