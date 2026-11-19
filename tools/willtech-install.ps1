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
foreach ($path in @($Base, (Join-Path $Base 'enabled'), (Join-Path $Base 'installed.json'))) {
  $item = Get-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
  if ($item -and ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) {
    throw "symlink em estado de instalação: $path"
  }
}

function Find-Python {
  if ($env:WILLTECH_PYTHON -and (Test-Path $env:WILLTECH_PYTHON)) {
    & $env:WILLTECH_PYTHON -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)" *> $null
    if ($LASTEXITCODE -eq 0) { return , @($env:WILLTECH_PYTHON, @()) }
  }
  foreach ($cand in @(
    @('py', @('-3.12')),
    @('py', @('-3.13')),
    @('py', @('-3')),
    @('python3', @()),
    @('python', @())
  )) {
    $c = $cand[0]; $pre = $cand[1]
    if (Get-Command $c -ErrorAction SilentlyContinue) {
      & $c @pre -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)" *> $null
      if ($LASTEXITCODE -eq 0) { return , @($c, $pre) }
    }
  }
  $localApp = $env:LOCALAPPDATA
  if ($localApp) {
    foreach ($v in @('Python312', 'Python313', 'Python314')) {
      $p = Join-Path $localApp "Programs\Python\$v\python.exe"
      if (Test-Path $p) {
        & $p -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)" *> $null
        if ($LASTEXITCODE -eq 0) { return , @($p, @()) }
      }
    }
  }
  return $null
}

function Want([string]$p) { return ($Platform -eq 'all') -or ($Platform -eq $p) }

function Invoke-UpdateComponent([string]$mode, [string]$target, [string]$template, $py) {
  $code = @'
import hashlib, json, os, shutil, sys
mode, target, template, exe, prefix, root = sys.argv[1:7]
prefix = "" if prefix == "@none" else prefix
py = [exe] + [p for p in prefix.split(",") if p]
root = os.path.realpath(root)
bak = target + ".willtech-bak"
owned = target + ".willtech-created"
registry = target + ".willtech-managed.json"
for path in (target, bak, owned, registry):
    if os.path.islink(path) or os.path.commonpath((root, os.path.realpath(path))) != root:
        raise ValueError("componente fora do projeto ou symlink: " + path)

def read_json(path):
    with open(path, encoding="utf-8-sig") as fh:
        return json.load(fh)

def write_json(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)

def remove_managed(hooks, groups):
    for event, added_groups in groups.items():
        entries = hooks.get(event, [])
        for added in reversed(added_groups):
            for handler in reversed(added.get("hooks", [])):
                found = False
                for i in range(len(entries) - 1, -1, -1):
                    group = entries[i]
                    if {k: v for k, v in group.items() if k != "hooks"} != {k: v for k, v in added.items() if k != "hooks"}:
                        continue
                    handlers = group.get("hooks", [])
                    for j in range(len(handlers) - 1, -1, -1):
                        if handlers[j] != handler:
                            continue
                        handlers.pop(j)
                        if not handlers and {k: v for k, v in group.items() if k != "hooks"} == {k: v for k, v in added.items() if k != "hooks"}:
                            entries.pop(i)
                        found = True
                        break
                    if found:
                        break
        if not entries:
            hooks.pop(event, None)

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

state = read_json(registry) if os.path.isfile(registry) else {}
created = not os.path.isfile(target)
if mode == "uninstall" and not state:
    print("preservado componente sem registro de posse " + target)
    sys.exit(0)
if mode == "install" and not state and (os.path.exists(bak) or os.path.exists(owned)):
    raise ValueError("backup/marcador sem registro de posse; preserve e revise antes de instalar: " + target)
kind = ("file" if template.endswith(".js") else "hooks") if mode == "install" else state["kind"]
if kind == "file" and not created and state:
    with open(target, "rb") as fh:
        changed = hashlib.sha256(fh.read()).hexdigest() != state["sha256"]
    if changed:
        print("preservado componente modificado e seu backup " + target)
        sys.exit(0)
if mode == "install":
    if kind == "hooks":
        data = read_json(target) if not created else {}
        had_hooks = state.get("had_hooks", "hooks" in data)
        null_hooks = state.get("null_hooks", data.get("hooks") is None)
        hooks = data.get("hooks") or {}
        remove_managed(hooks, state.get("groups", {}))
        groups = read_json(template)["hooks"]
        groups = {event: [dict(g, hooks=[adapt(h) for h in g.get("hooks", [])]) for g in entries] for event, entries in groups.items()}
        for event, added in groups.items():
            hooks[event] = hooks.get(event, []) + added
        data["hooks"] = hooks
    os.makedirs(os.path.dirname(target), exist_ok=True)
    if not created and not os.path.exists(owned) and not os.path.exists(bak):
        shutil.copy2(target, bak)
    if kind == "file":
        shutil.copyfile(template, target)
        state = {"kind": kind}
    else:
        write_json(target, data)
        state = {"kind": kind, "groups": groups, "had_hooks": had_hooks, "null_hooks": null_hooks}
    with open(target, "rb") as fh:
        state["sha256"] = hashlib.sha256(fh.read()).hexdigest()
    if created:
        with open(owned, "w", encoding="utf-8"):
            pass
    write_json(registry, state)
    print(("criado " if created else "mesclado ") + target)
else:
    if kind == "file":
        if os.path.isfile(bak):
            os.replace(bak, target)
        elif not created and os.path.isfile(owned):
            os.remove(target)
    elif not created:
        with open(target, "rb") as fh:
            unchanged = hashlib.sha256(fh.read()).hexdigest() == state["sha256"]
        data = read_json(target)
        hooks = data.get("hooks") or {}
        remove_managed(hooks, state["groups"])
        if hooks:
            data["hooks"] = hooks
        elif not state["had_hooks"]:
            data.pop("hooks", None)
        else:
            data["hooks"] = None if state["null_hooks"] else {}
        if os.path.isfile(bak) and (unchanged or data == read_json(bak)):
            os.replace(bak, target)
        else:
            if os.path.isfile(owned) and not data:
                os.remove(target)
            else:
                write_json(target, data)
            if os.path.isfile(bak):
                print("preservado backup original após alterações do usuário " + bak)
    for path in (owned, registry):
        if os.path.isfile(path):
            os.remove(path)
    print("revertido componente gerenciado " + target)
'@
  $exe = $py[0]; $pre = $py[1]
  $prefix = $pre -join ','
  if (-not $prefix) { $prefix = '@none' }
  $code | & $exe @pre - $mode $target $template $exe $prefix $Repo
  if ($LASTEXITCODE -ne 0) { throw "falha ao atualizar componente em $target" }
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
  Write-Error 'Python >= 3.12 não encontrado (python3/python/py). Instalação recusada: os controles obrigatórios não rodariam.'
  exit 2
}

# N3: valida o layout de distribuição ANTES de qualquer alteração (espelha o
# preflight do .sh). Componente ausente/inválido/symlink = erro preciso, exit 2,
# nenhuma instalação parcial.
if (-not $Uninstall) {
  $preflight = @'
import json, os, sys
src, repo, platform = sys.argv[1:4]
def want(p): return platform in ("all", p)
required = [("tools/willtech-auto.py", repo, "núcleo de automação"),
            ("tools/willtech-dossie.py", repo, "dossiê/cache/guardas")]
if want("claude"): required.append(("claude-code/settings/willtech-hooks.json", src, "template hooks claude"))
if want("codex"): required.append(("codex/hooks.json", src, "template hooks codex"))
if want("opencode"): required.append(("opencode/plugins/willtech/index.js", src, "plugin opencode"))
problems = []
for rel, base, label in required:
    path = os.path.join(base, rel)
    if os.path.islink(path):
        problems.append(f"{rel} ({label}): symlink recusado em {base}")
    elif not os.path.isfile(path):
        problems.append(f"{rel} ({label}): ausente em {base}")
    elif rel.endswith(".json"):
        try:
            with open(path, encoding="utf-8-sig") as fh:
                json.load(fh)
        except (OSError, ValueError):
            problems.append(f"{rel} ({label}): JSON inválido em {base}")
if problems:
    print("erro: layout de distribuição inválido; instalação abortada antes de qualquer alteração:")
    for p in problems:
        print("  " + p)
    sys.exit(2)
'@
  $exe = $py[0]; $pre = $py[1]
  $preflight | & $exe @pre - $Src $Repo $Platform
  if ($LASTEXITCODE -ne 0) { exit 2 }
}

if ($Uninstall) {
  if (-not (Confirm "Serão revertidos somente os componentes registrados da plataforma ${Platform}: handlers WillTech e plugin .opencode/plugins/willtech/index.js, com backups. Serão removidos .willtech/enabled e .willtech/installed.json. Diretórios, arquivos de terceiros, componentes modificados e dossiê/cache são preservados.")) {
    Write-Host 'cancelado'; exit 0
  }
  if (Want 'claude') { Invoke-UpdateComponent 'uninstall' (Join-Path $Repo '.claude\settings.json') '-' $py }
  if (Want 'codex') { Invoke-UpdateComponent 'uninstall' (Join-Path $Repo '.codex\hooks.json') '-' $py }
  if (Want 'opencode') { Invoke-UpdateComponent 'uninstall' (Join-Path $Repo '.opencode\plugins\willtech\index.js') '-' $py }
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
if (Want 'claude') { Invoke-UpdateComponent 'install' (Join-Path $Repo '.claude\settings.json') (Join-Path $Src 'claude-code\settings\willtech-hooks.json') $py }
if (Want 'codex') { Invoke-UpdateComponent 'install' (Join-Path $Repo '.codex\hooks.json') (Join-Path $Src 'codex\hooks.json') $py }
if (Want 'opencode') { Invoke-UpdateComponent 'install' (Join-Path $Repo '.opencode\plugins\willtech\index.js') (Join-Path $Src 'opencode\plugins\willtech\index.js') $py }
@{ platform = $Platform; repo = $Repo; python = $py[0] } | ConvertTo-Json -Compress | Set-Content -Encoding utf8 (Join-Path $Base 'installed.json')
New-Item -ItemType File -Force -Path (Join-Path $Base 'enabled') | Out-Null
Write-Host 'instalação concluída; automação ativa (.willtech/enabled)'
Write-Host 'desativar: -Disable | reverter: -Uninstall'

# WillTech-General / WILLTECH-BH © 2026 · autoria: github.com/hebwil