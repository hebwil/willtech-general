# WillTech-General 2.2 — instalação nativa Windows (projeto-local, idempotente).
# Espelha tools/willtech-install.sh: escreve APENAS dentro do repo alvo
# (.claude/, .codex/, .opencode/, .willtech/). Nada global é alterado; a
# ExecutionPolicy do PowerShell NÃO é modificada (o flag abaixo é de processo).
#
# Uso (PowerShell):
#   powershell -ExecutionPolicy Bypass -File tools\willtech-install.ps1
#   ... -Platform opencode | -Yes | -Disable | -Enable | -Uninstall | -Repo DIR
#
# Consentimento: sem -Yes, lista as mudanças e pede confirmação. -Disable
# remove só .willtech/enabled (núcleo vira no-op); -Enable religa; -Uninstall
# restaura backups pré-instalação. Requer Python 3 (python3, python ou py -3);
# sem ele a instalação é recusada (controles obrigatórios não rodariam).
# Os wrappers sandbox-exec (macOS) NÃO são instalados no Windows: as
# ferramentas de shell dos agentes permanecem restritas pelas permissões
# do runtime — nenhuma execução irrestrita é liberada para simular suporte.
[CmdletBinding()]
param(
  [string]$Repo,
  [ValidateSet('claude', 'opencode', 'codex', 'all')][string]$Platform = 'all',
  [switch]$Yes,
  [switch]$Disable,
  [switch]$Enable,
  [switch]$Uninstall
)
$ErrorActionPreference = 'Stop'
# Windows PowerShell 5.1 corrompe aspas embutidas em argumentos de executáveis
# nativos (-c); o código Python vai por stdin (python - args), sem aspas no argv.
# UTF8 sem BOM: [Encoding]::UTF8 do PS 5.1 emite U+FEFF e quebra o programa.
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$Src = Split-Path -Parent $PSScriptRoot
if (-not $Repo) { $Repo = $Src }
if (-not (Test-Path (Join-Path $Repo 'tools\willtech-auto.py'))) {
  Write-Error "erro: $Repo não contém tools\willtech-auto.py (use -Repo com o repo WillTech)"
  exit 2
}
$Repo = (Resolve-Path $Repo).Path
$Base = Join-Path $Repo '.willtech'

function Find-Python {
  foreach ($c in @('python3', 'python', 'py')) {
    if (Get-Command $c -ErrorAction SilentlyContinue) {
      $pre = @(); if ($c -eq 'py') { $pre = @('-3') }
      & $c @pre --version *> $null
      if ($LASTEXITCODE -eq 0) { return , @($c, $pre) }
    }
  }
  return $null
}

function Want([string]$p) { return ($Platform -eq 'all') -or ($Platform -eq $p) }

function Invoke-MergeHooks([string]$target, [string]$template, $py) {
  $code = @'
import json, os, sys
target, template, exe, prefix, root = sys.argv[1:6]
prefix = "" if prefix == "@none" else prefix
py = [exe] + [p for p in prefix.split(",") if p]
data = {}
created = not os.path.isfile(target)
owned = target + ".willtech-created"
if not created:
    with open(target, encoding="utf-8-sig") as fh:
        data = json.load(fh)
    bak = target + ".willtech-bak"
    if not os.path.exists(bak) and not os.path.exists(owned):
        with open(bak, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
hooks = data.get("hooks") or {}
with open(template, encoding="utf-8") as fh:
    tpl = json.load(fh)["hooks"]
def adapt(h):
    h = dict(h)
    cmd = h.get("command", "")
    if cmd == "python3":
        h["command"] = py[0]
        h["args"] = py[1:] + h.get("args", [])
    elif "$(git rev-parse --show-toplevel)" in cmd:
        tool = root.replace(os.sep, "/") + "/tools/willtech-auto.py"
        h["command"] = " ".join(['"' + py[0] + '"'] + py[1:] + ['"' + tool + '"', cmd.rsplit(" ", 1)[-1]])
    return h
for event, groups in tpl.items():
    kept = []
    for g in hooks.get(event, []):
        hs = [h for h in g.get("hooks", []) if "willtech-auto.py" not in json.dumps(h)]
        if hs:
            g = dict(g); g["hooks"] = hs; kept.append(g)
    ng = []
    for g in groups:
        g = dict(g); g["hooks"] = [adapt(h) for h in g.get("hooks", [])]; ng.append(g)
    hooks[event] = kept + ng
data["hooks"] = hooks
os.makedirs(os.path.dirname(target), exist_ok=True)
with open(target, "w", encoding="utf-8") as fh:
    json.dump(data, fh, indent=2, ensure_ascii=False)
if created:
    with open(owned, "w", encoding="utf-8"):
        pass
print(("criado " if created else "mesclado ") + target)
'@
  #_argv sem aspas duplas: PS 5.1 as corrompe em chamadas nativas; o prefixo
  # do launcher (ex.: -3) vai como texto simples separado por vírgula.
  $exe = $py[0]; $pre = $py[1]
  $prefix = $pre -join ','
  if (-not $prefix) { $prefix = '@none' }
  $code | & $exe @pre - $target $template $exe $prefix $Repo
  if ($LASTEXITCODE -ne 0) { throw "falha ao mesclar hooks em $target" }
}

function Invoke-UnmergeHooks([string]$target, $py) {
  $code = @'
import json, os, sys
target = sys.argv[1]
bak = target + ".willtech-bak"
if os.path.isfile(bak):
    os.replace(bak, target)
    print("restaurado backup " + target)
elif os.path.isfile(target):
    with open(target, encoding="utf-8-sig") as fh:
        data = json.load(fh)
    hooks = data.get("hooks") or {}
    for event in list(hooks):
        kept = []
        for g in hooks[event]:
            hs = [h for h in g.get("hooks", []) if "willtech-auto.py" not in json.dumps(h)]
            if hs:
                g = dict(g); g["hooks"] = hs; kept.append(g)
        if kept:
            hooks[event] = kept
        else:
            del hooks[event]
    if hooks:
        data["hooks"] = hooks
        with open(target, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
        print("removidos hooks WillTech de " + target)
    else:
        os.remove(target)
        print("removido " + target)
owned = target + ".willtech-created"
if os.path.isfile(owned):
    os.remove(owned)
'@
  $exe = $py[0]; $pre = $py[1]
  $code | & $exe @pre - $target
  if ($LASTEXITCODE -ne 0) { throw "falha ao reverter hooks em $target" }
}

function Confirm([string]$msg) {
  if ($Yes) { return $true }
  Write-Host $msg
  $ans = Read-Host 'Confirma? [s/N]'
  return ($ans -match '^[sSyY]')
}

if ($Disable) {
  Remove-Item (Join-Path $Base 'enabled') -ErrorAction SilentlyContinue
  Write-Host 'automação desativada (.willtech/enabled removido); hooks/plugins permanecem inertes'
  exit 0
}
if ($Enable) {
  New-Item -ItemType Directory -Force -Path $Base | Out-Null
  New-Item -ItemType File -Force -Path (Join-Path $Base 'enabled') | Out-Null
  Write-Host 'automação reativada (.willtech/enabled)'
  exit 0
}

$py = Find-Python
if (-not $py) {
  Write-Error 'Python 3 não encontrado (python3/python/py). Instalação recusada: os controles obrigatórios não rodariam.'
  exit 2
}

if ($Uninstall) {
  if (-not (Confirm "Será removido: hooks WillTech de .claude/settings.json e .codex/hooks.json (restaurando backups), o plugin .opencode/plugins/willtech/ e .willtech/enabled. O dossiê/cache (evidências) é preservado.")) {
    Write-Host 'cancelado'; exit 0
  }
  if (Want 'claude') { Invoke-UnmergeHooks (Join-Path $Repo '.claude\settings.json') $py }
  if (Want 'codex') { Invoke-UnmergeHooks (Join-Path $Repo '.codex\hooks.json') $py }
  if (Want 'opencode') {
    Remove-Item (Join-Path $Repo '.opencode\plugins\willtech\index.js') -ErrorAction SilentlyContinue
    foreach ($d in @('.opencode\plugins\willtech', '.opencode\plugins', '.opencode')) {
      $p = Join-Path $Repo $d
      if ((Test-Path $p) -and -not (Get-ChildItem $p -Force)) { Remove-Item $p }
    }
    Write-Host 'plugin removido'
  }
  Remove-Item (Join-Path $Base 'enabled'), (Join-Path $Base 'installed.json') -ErrorAction SilentlyContinue
  Write-Host 'uninstall concluído'
  exit 0
}

# install
$lines = @("Instalação projeto-local em $Repo (plataforma: $Platform):")
if (Want 'claude') { $lines += '  - mescla hooks em .claude/settings.json (backup prévio)' }
if (Want 'codex') { $lines += '  - mescla hooks em .codex/hooks.json (backup prévio; exige trust via /hooks no Codex)' }
if (Want 'opencode') { $lines += '  - copia plugin para .opencode/plugins/willtech/index.js' }
$lines += '  - cria .willtech/enabled (marcador de ativação)'
$lines += 'Nada global é alterado. Telas oficiais de trust/permissão continuam valendo.'
$lines += 'Windows: wrappers sandbox-exec (macOS) não instalados; shell dos agentes segue restrito pelo runtime.'
if (-not (Confirm ($lines -join "`n"))) { Write-Host 'cancelado'; exit 0 }

New-Item -ItemType Directory -Force -Path $Base | Out-Null
New-Item -ItemType File -Force -Path (Join-Path $Base 'enabled') | Out-Null
if (Want 'claude') { Invoke-MergeHooks (Join-Path $Repo '.claude\settings.json') (Join-Path $Src 'claude-code\settings\willtech-hooks.json') $py }
if (Want 'codex') { Invoke-MergeHooks (Join-Path $Repo '.codex\hooks.json') (Join-Path $Src 'codex\hooks.json') $py }
if (Want 'opencode') {
  $dst = Join-Path $Repo '.opencode\plugins\willtech'
  New-Item -ItemType Directory -Force -Path $dst | Out-Null
  Copy-Item (Join-Path $Src 'opencode\plugins\willtech\index.js') (Join-Path $dst 'index.js') -Force
  Write-Host "copiado $(Join-Path $dst 'index.js')"
}
@{ platform = $Platform; repo = $Repo } | ConvertTo-Json -Compress | Set-Content -Encoding utf8 (Join-Path $Base 'installed.json')
Write-Host 'instalação concluída; automação ativa (.willtech/enabled)'
Write-Host 'desativar: -Disable | reverter: -Uninstall'

# WillTech-General / WILLTECH-BH © 2026 · autoria: github.com/hebwil