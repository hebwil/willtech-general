#!/usr/bin/env python3
"""WillTech-General — ativação GUI experimental e opcional (OpenCode Desktop).

O painel visual dos sete agentes é um pacote GUI separado do núcleo de automação.
O Desktop o carrega a partir do servidor de fundo, que lê a lista `plugins` do
opencode.json GLOBAL. O instalador de automação (willtech-install.sh/.ps1) é
projeto-local e nunca toca configs globais; por isso a ativação GUI é esta
ferramenta dedicada, explícita e opt-in — não um instalador paralelo de automação.

Portável: o caminho do pacote é resolvido a partir da localização deste arquivo
(sem caminho absoluto fixo de uma máquina específica). Idempotente e reversível:
backup prévio, registro de posse, preservação de plugins/ajustes de terceiros.

Uso:
  python3 tools/willtech-gui.py --install   [--config PATH] [--yes]
  python3 tools/willtech-gui.py --disable   [--config PATH]
  python3 tools/willtech-gui.py --enable    [--config PATH]
  python3 tools/willtech-gui.py --uninstall [--config PATH] [--yes]

--config sobrescreve o opencode.json alvo (padrão: ~/.config/opencode/opencode.json).
Use --config com um fixture descartável para testes; nada é alterado sem o comando.
Sem IA, sem rede. Apenas edita o JSON de configuração com backup.
"""
import argparse
import hashlib
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PACKAGE = os.path.realpath(os.path.join(REPO, "opencode", "plugins", "willtech", "visual"))
DEFAULT_CONFIG = os.path.join(os.path.expanduser("~"), ".config", "opencode", "opencode.json")


def read_json(path):
    with open(path, encoding="utf-8-sig") as fh:
        return json.load(fh)


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def is_willtech(entry):
    """Identifica a entrada GUI WillTech pelo caminho do pacote (realpath)."""
    pkg = entry.get("package") if isinstance(entry, dict) else entry if isinstance(entry, str) else None
    if not isinstance(pkg, str):
        return False
    try:
        return os.path.realpath(pkg) == PACKAGE
    except OSError:
        return False


def sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def guard_paths(target):
    bak = target + ".willtech-gui-bak"
    registry = target + ".willtech-gui-managed.json"
    for path in (target, bak, registry):
        if os.path.islink(path):
            raise SystemExit(f"erro: symlink recusado: {path}")
    return bak, registry


def load_plugins(data):
    plugins = data.get("plugins")
    if plugins is None:
        return [], False, True
    if not isinstance(plugins, list):
        raise SystemExit("erro: 'plugins' não é uma lista; preserve e revise antes de ativar")
    return plugins, True, False


def install(target):
    bak, registry = guard_paths(target)
    state = read_json(registry) if os.path.isfile(registry) else {}
    created = not os.path.isfile(target)
    if not state and (os.path.exists(bak)):
        raise SystemExit("erro: backup sem registro de posse; preserve e revise antes de ativar: " + bak)
    data = read_json(target) if not created else {}
    plugins, had_plugins, null_plugins = load_plugins(data)
    if state.get("had_plugins") is not None:
        had_plugins = state["had_plugins"]
        null_plugins = state.get("null_plugins", null_plugins)
    # Remove entrada WillTech prévia (idempotente; preserva terceiros).
    plugins = [p for p in plugins if not is_willtech(p)]
    entry = {"package": PACKAGE, "options": {"enabled": True}}
    plugins.append(entry)
    data["plugins"] = plugins
    os.makedirs(os.path.dirname(target), exist_ok=True)
    if not created and not os.path.exists(bak):
        shutil.copy2(target, bak)
    write_json(target, data)
    state = {"entry": entry, "had_plugins": had_plugins, "null_plugins": null_plugins,
             "created": created, "sha256": sha256(target)}
    write_json(registry, state)
    print(("criado " if created else "atualizado ") + target)
    print("painel GUI WillTech ativado (enabled=true); abra o OpenCode Desktop e use o comando 'WillTech: mostrar/ocultar equipe'")


def set_enabled(target, value):
    bak, registry = guard_paths(target)
    if not os.path.isfile(registry):
        raise SystemExit("erro: nenhuma ativação GUI WillTech registrada; nada a alterar")
    data = read_json(target)
    plugins, _, _ = load_plugins(data)
    found = False
    for p in plugins:
        if is_willtech(p) and isinstance(p, dict):
            p.setdefault("options", {})["enabled"] = value
            found = True
    if not found:
        raise SystemExit("erro: entrada GUI WillTech não encontrada; preserve e revise")
    write_json(target, data)
    state = read_json(registry)
    state["sha256"] = sha256(target)
    write_json(registry, state)
    print(("ativado" if value else "desativado") + " painel GUI WillTech (enabled=" + str(value).lower() + ")")


def uninstall(target):
    bak, registry = guard_paths(target)
    if not os.path.isfile(registry):
        print("preservado: nenhuma ativação GUI WillTech registrada em " + target)
        return
    state = read_json(registry)
    created = state.get("created", not os.path.isfile(bak))
    unchanged = os.path.isfile(target) and sha256(target) == state.get("sha256")
    if os.path.isfile(bak) and unchanged:
        os.replace(bak, target)
        print("restaurado backup pré-ativação " + target)
    else:
        data = read_json(target)
        plugins, had_plugins, null_plugins = load_plugins(data)
        plugins = [p for p in plugins if not is_willtech(p)]
        if plugins:
            data["plugins"] = plugins
        elif not state.get("had_plugins", had_plugins):
            data.pop("plugins", None)
        else:
            data["plugins"] = None if state.get("null_plugins", null_plugins) else []
        if not data and created:
            os.remove(target)
        else:
            write_json(target, data)
        if os.path.isfile(bak):
            print("preservado backup original após alterações do usuário " + bak)
        print("removida entrada GUI WillTech de " + target)
    for path in (registry,):
        if os.path.isfile(path):
            os.remove(path)
    print("uninstall GUI concluído; plugins de terceiros preservados")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Ativação GUI experimental WillTech (OpenCode Desktop)")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--install", action="store_true")
    mode.add_argument("--disable", action="store_true")
    mode.add_argument("--enable", action="store_true")
    mode.add_argument("--uninstall", action="store_true")
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args(argv)
    target = os.path.realpath(args.config)
    if not os.path.isdir(PACKAGE) or not os.path.isfile(os.path.join(PACKAGE, "gui-experimental.cjs")):
        raise SystemExit("erro: pacote GUI ausente/incompleto em " + PACKAGE)
    if (args.install or args.uninstall) and not args.yes:
        print(f"Alvo: {target}\nPacote: {PACKAGE}\nAção: {'instalar/atualizar' if args.install else 'reverter'} a entrada GUI WillTech (backup prévio; terceiros preservados).")
        ans = input("Confirma? [s/N] ")
        if ans.strip().lower() not in ("s", "y", "sim", "yes"):
            print("cancelado")
            return 0
    if args.install:
        install(target)
    elif args.disable:
        set_enabled(target, False)
    elif args.enable:
        set_enabled(target, True)
    elif args.uninstall:
        uninstall(target)
    return 0


if __name__ == "__main__":
    sys.exit(main())