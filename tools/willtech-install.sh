#!/bin/sh
# WillTech-General 2.2 — instalação idempotente da automação nativa.
# Projeto-local: escreve APENAS dentro do repo alvo (.claude/, .codex/,
# .opencode/, .willtech/). Nunca toca instalações ativas nem configs globais.
#
# Uso: willtech-install.sh [--repo DIR] [--platform claude|opencode|codex|all]
#                          [--yes] [--disable] [--enable] [--uninstall]
#
# Consentimento: sem --yes, lista as mudanças e pede confirmação (instalação
# e uninstall). --disable remove só o marcador .willtech/enabled (núcleo vira
# no-op); --enable religa; --uninstall restaura backups pré-instalação.
# O repo alvo precisa conter tools/willtech-auto.py (este repo ou uma cópia).
set -eu

SRC=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
REPO=$SRC
PLATFORM=all
YES=0
MODE=install

while [ $# -gt 0 ]; do
  case "$1" in
    --repo) REPO=$2; shift 2 ;;
    --platform) PLATFORM=$2; shift 2 ;;
    --yes) YES=1; shift ;;
    --disable) MODE=disable; shift ;;
    --enable) MODE=enable; shift ;;
    --uninstall) MODE=uninstall; shift ;;
    *) echo "argumento desconhecido: $1"; exit 2 ;;
  esac
done

case "$PLATFORM" in claude|opencode|codex|all) ;; *) echo "plataforma inválida: $PLATFORM"; exit 2 ;; esac
if [ ! -d "$REPO" ] || [ ! -f "$REPO/tools/willtech-auto.py" ]; then
  echo "erro: $REPO não contém tools/willtech-auto.py (use --repo com o repo WillTech)"
  exit 2
fi
REPO=$(CDPATH= cd -- "$REPO" && pwd -P)
BASE="$REPO/.willtech"
for path in "$BASE" "$BASE/enabled" "$BASE/installed.json"; do
  if [ -L "$path" ]; then
    echo "erro: symlink em estado de instalação: $path"
    exit 2
  fi
done

update_component() {
  python3 - "$1" "$2" "$3" "$REPO" <<'PY'
import hashlib, json, os, shutil, sys
mode, target, template, root = sys.argv[1:5]
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
PY
}

want() { [ "$PLATFORM" = all ] || [ "$PLATFORM" = "$1" ]; }

if [ "$MODE" = disable ]; then
  rm -f "$BASE/enabled"
  echo "automação desativada (.willtech/enabled removido); hooks/plugins permanecem inertes"
  exit 0
fi
if [ "$MODE" = enable ]; then
  mkdir -p "$BASE"
  : > "$BASE/enabled"
  echo "automação reativada (.willtech/enabled)"
  exit 0
fi

if [ "$MODE" = uninstall ]; then
  if [ "$YES" != 1 ]; then
    echo "Serão revertidos somente os componentes registrados da plataforma $PLATFORM:"
    echo "handlers WillTech e plugin .opencode/plugins/willtech/index.js, com backups."
    echo "Serão removidos .willtech/enabled e .willtech/installed.json."
    echo "Diretórios, arquivos de terceiros, componentes modificados e dossiê/cache são preservados."
    printf "Confirma? [s/N] "
    read -r ans
    case "$ans" in s|S|y|Y) ;; *) echo "cancelado"; exit 0 ;; esac
  fi
  if want claude; then update_component uninstall "$REPO/.claude/settings.json" -; fi
  if want codex; then update_component uninstall "$REPO/.codex/hooks.json" -; fi
  if want opencode; then update_component uninstall "$REPO/.opencode/plugins/willtech/index.js" -; fi
  rm -f "$BASE/enabled" "$BASE/installed.json"
  echo "uninstall concluído"
  exit 0
fi

# MODE=install
if [ "$YES" != 1 ]; then
  echo "Instalação projeto-local em $REPO (plataforma: $PLATFORM):"
  if want claude; then echo "  - mescla hooks em .claude/settings.json (backup prévio)"; fi
  if want codex; then echo "  - mescla hooks em .codex/hooks.json (backup prévio; exige trust via /hooks no Codex)"; fi
  if want opencode; then echo "  - copia plugin para .opencode/plugins/willtech/index.js"; fi
  echo "  - cria .willtech/enabled (marcador de ativação)"
  echo "Nada global é alterado. Telas oficiais de trust/permissão continuam valendo."
  printf "Confirma? [s/N] "
  read -r ans
  case "$ans" in s|S|y|Y) ;; *) echo "cancelado"; exit 0 ;; esac
fi

mkdir -p "$BASE"
if want claude; then update_component install "$REPO/.claude/settings.json" "$SRC/claude-code/settings/willtech-hooks.json"; fi
if want codex; then update_component install "$REPO/.codex/hooks.json" "$SRC/codex/hooks.json"; fi
if want opencode; then update_component install "$REPO/.opencode/plugins/willtech/index.js" "$SRC/opencode/plugins/willtech/index.js"; fi
python3 - "$PLATFORM" "$REPO" "$BASE/installed.json" <<'PY'
import json, sys
with open(sys.argv[3], "w", encoding="utf-8") as fh:
    json.dump({"platform": sys.argv[1], "repo": sys.argv[2]}, fh)
PY
: > "$BASE/enabled"
echo "instalação concluída; automação ativa (.willtech/enabled)"
echo "desativar: willtech-install.sh --disable | reverter: willtech-install.sh --uninstall"

# WillTech-General / WILLTECH-BH © 2026 · autoria: github.com/hebwil