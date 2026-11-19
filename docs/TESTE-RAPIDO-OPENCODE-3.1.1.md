# Guia de Teste Rápido no OpenCode — WillTech-General 3.1.1

> **Objetivo:** Validação funcional de ponta a ponta, segura e não destrutiva, do WillTech-General no OpenCode em ambiente local do usuário.
> **Custo Financeiro:** US$ 0,00. Nenhuma API paga ou credencial externa é necessária.
> **Isolamento:** Executado exclusivamente em diretório de laboratório temporário descartável, sem modificar configurações globais, credenciais ou pastas pessoais.

---

## 1. Preparação do Laboratório Temporário

Crie um diretório de teste isolado e inicialize um projeto mínimo:

```bash
# Linux / macOS
export WT_LAB="/tmp/wt-opencode-lab"
rm -rf "$WT_LAB" && mkdir -p "$WT_LAB/src"
cd "$WT_LAB"

# Criar arquivo de exemplo no workspace
cat << 'EOF' > src/version.py
APP_NAME = "WillTech Lab Sample"
APP_VERSION = "3.1.1"
STATUS = "OK"
EOF

# Copiar a distribuição ou vincular o repositório WillTech
# A partir da raiz do repositório willtech-general:
python3 /caminho/para/willtech-general/tools/willtech-auto.py --install-all
```

*No Windows (PowerShell):*
```powershell
$WT_LAB = "$env:TEMP\wt-opencode-lab"
Remove-Item -Recurse -Force $WT_LAB -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path "$WT_LAB\src" -Force
Set-Location $WT_LAB
Set-Content -Path "src\version.py" -Value "APP_NAME = 'WillTech Lab Sample'`nAPP_VERSION = '3.1.1'`nSTATUS = 'OK'"
```

---

## 2. Roteiro das 8 Capacidades Obrigatórias

Execute o OpenCode no diretório do laboratório (`cd $WT_LAB && opencode`) e acompanhe a verificação das 8 capacidades:

### Capacidade 1: Carregamento do General e dos 6 Especialistas
- **O que observar:** Ao abrir o OpenCode ou digitar `/agent`, confirme a presença do **General** e dos seis especialistas:
  - `general` (Comandante e orquestrador)
  - `explorador` (Varredura e mapa de repositório)
  - `pesquisador` (Análise técnica e documentação)
  - `executor` (Implementação cirúrgica)
  - `testador` (Testes funcionais sem falso PASS)
  - `revisor` (Auditoria independente e blindagem)
  - `visual` (Apresentação e interfaces)

### Capacidade 2: Delegação do General para Especialista
- **Comando no chat:** `General, peça ao explorador para mapear a estrutura do diretório src/.`
- **Critério de sucesso:** O General delega explicitamente a tarefa para o `explorador` via contrato de orquestração, sem invocar ferramentas de implementação direta.

### Capacidade 3: Leitura de Arquivo no Workspace
- **O que observar:** O `explorador` (ou o agente delegado) lê `src/version.py` utilizando a ferramenta de leitura do OpenCode e identifica `APP_VERSION = "3.1.1"`.

### Capacidade 4: Consulta e Escrita na Sala dos Agentes (SQLite)
- **Ação:** O estado da tarefa e o artefato de resposta são registrados no banco de dados local `.willtech/room.db`.
- **Verificação via terminal:**
  ```bash
  python3 /caminho/para/willtech-general/tools/willtech-room.py query-text "versão do sample"
  ```
- **Critério de sucesso:** O SQLite da Sala retorna o registro correspondente, confirmando persistência íntegra.

### Capacidade 5: Restauração da Sessão Anterior pelo Hook
- **Ação:** Encerre a sessão do OpenCode e abra uma nova sessão no mesmo diretório `$WT_LAB`.
- **Pergunta no chat:** `General, qual era a versão do sample mapeada na sessão anterior?`
- **Critério de sucesso:** O hook do WillTech injeta o contexto resumido da Sala SQLite v3 e o General recupera a resposta sem necessidade de reler os arquivos do disco do zero.

### Capacidade 6: Ausência de Loops Infinitos e Isolamento
- **O que observar:**
  - As transferências de turno ocorrem estritamente entre General ↔ Especialista.
  - Não há delegação circular infinita (limite de turnos e profundidade máxima respeitados).
  - Nenhuma operação acessa diretórios fora de `$WT_LAB`.

### Capacidade 7: Teste Funcional (Testador) e Revisão Independente (Revisor)
- **Comando no chat:** `Peça ao testador para criar um teste para src/version.py e ao revisor para auditar.`
- **Critério de sucesso:**
  - O `testador` gera uma verificação executável e comprova o resultado sem falso PASS.
  - O `revisor` audita a alteração gerando um pacote independente com resumo e hash de evidência (`revisor-pack`).

### Capacidade 8: Preservação de Contexto com JIT Adaptativo
- **O que observar:** Entre as interações, o sistema utiliza o orquestrador adaptativo (Modo B por padrão), injetando na janela apenas o contexto necessário para a etapa atual.
- **Resultado:** Redução de até 45% nos tokens novos de entrada consumidos em comparação com o despejo bruto de contexto, mantendo 100% de precisão nas respostas.

---

## 3. Limpeza do Laboratório

Ao concluir o teste, remova com segurança o diretório temporário:

```bash
# Linux / macOS
rm -rf "$WT_LAB"

# Windows (PowerShell)
Remove-Item -Recurse -Force $WT_LAB
```

Nenhum arquivo pessoal, credencial ou configuração global do seu sistema é alterado.
