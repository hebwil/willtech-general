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

merge_hooks() {
  python3 - "$1" "$2" <<'PY'
import json, os, sys
target, template = sys.argv[1], sys.argv[2]
data = {}
created = not os.path.isfile(target)
if not created:
    with open(target, encoding="utf-8") as fh:
        data = json.load(fh)
    bak = target + ".willtech-bak"
    if not os.path.exists(bak):
        with open(bak, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
hooks = data.get("hooks") or {}
with open(template, encoding="utf-8") as fh:
    tpl = json.load(fh)["hooks"]
for event, groups in tpl.items():
    kept = []
    for g in hooks.get(event, []):
        hs = [h for h in g.get("hooks", []) if "willtech-auto.py" not in json.dumps(h)]
        if hs:
            g = dict(g); g["hooks"] = hs; kept.append(g)
    hooks[event] = kept + groups
data["hooks"] = hooks
os.makedirs(os.path.dirname(target), exist_ok=True)
with open(target, "w", encoding="utf-8") as fh:
    json.dump(data, fh, indent=2, ensure_ascii=False)
print(("criado " if created else "mesclado ") + target)
PY
}

unmerge_hooks() {
  python3 - "$1" <<'PY'
import json, os, sys
target = sys.argv[1]
bak = target + ".willtech-bak"
if os.path.isfile(bak):
    os.replace(bak, target)
    print("restaurado backup " + target)
elif os.path.isfile(target):
    with open(target, encoding="utf-8") as fh:
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
    echo "Será removido: hooks WillTech de .claude/settings.json e .codex/hooks.json"
    echo "(restaurando backups pré-instalação quando existirem), o plugin"
    echo ".opencode/plugins/willtech/ e o marcador .willtech/enabled."
    echo "O dossiê/cache (evidências) é preservado."
    printf "Confirma? [s/N] "
    read -r ans
    case "$ans" in s|S|y|Y) ;; *) echo "cancelado"; exit 0 ;; esac
  fi
  if want claude; then unmerge_hooks "$REPO/.claude/settings.json"; fi
  if want codex; then unmerge_hooks "$REPO/.codex/hooks.json"; fi
  if want opencode; then
    rm -f "$REPO/.opencode/plugins/willtech/index.js"
    rmdir "$REPO/.opencode/plugins/willtech" "$REPO/.opencode/plugins" "$REPO/.opencode" 2>/dev/null || true
    echo "plugin removido"
  fi
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
: > "$BASE/enabled"
if want claude; then merge_hooks "$REPO/.claude/settings.json" "$SRC/claude-code/settings/willtech-hooks.json"; fi
if want codex; then merge_hooks "$REPO/.codex/hooks.json" "$SRC/codex/hooks.json"; fi
if want opencode; then
  mkdir -p "$REPO/.opencode/plugins/willtech"
  cp "$SRC/opencode/plugins/willtech/index.js" "$REPO/.opencode/plugins/willtech/index.js"
  echo "copiado $REPO/.opencode/plugins/willtech/index.js"
fi
printf '{"platform":"%s","repo":"%s"}\n' "$PLATFORM" "$REPO" > "$BASE/installed.json"
echo "instalação concluída; automação ativa (.willtech/enabled)"
echo "desativar: willtech-install.sh --disable | reverter: willtech-install.sh --uninstall"

# WillTech-General / WILLTECH-BH © 2026 · autoria: github.com/hebwil