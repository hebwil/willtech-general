#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="${0:A:h}"
cd "$SCRIPT_DIR"

printf '\nWillTech-General — instalação Claude Code\n'
printf 'Origem: %s\n' "$SCRIPT_DIR"
printf 'Destino: ~/.claude/agents\n\n'
printf 'O instalador faz backup antes de copiar e não altera outras plataformas.\n'
printf 'Para ver o plano sem instalar: ./bin/willtech-bootstrap.sh --check\n\n'

read -r "REPLY?Executar instalação agora? [y/N] "
case "$REPLY" in
  [Yy]|[Yy][Ee][Ss])
    ./bin/willtech-bootstrap.sh --apply
    ;;
  *)
    printf '\nInstalação cancelada.\n'
    exit 0
    ;;
esac

printf '\nConcluído. Abra uma sessão nova do Claude Code e verifique os sete agentes willtech-*.\n'

printf '\nA homologação (testes A–I) abre sessões reais e consome tokens da sua conta.\n'
read -r "REPLY?Rodar a homologação agora? [y/N] "
case "$REPLY" in
  [Yy]|[Yy][Ee][Ss])
    ./bin/willtech-homologate.sh --run --yes-spend
    ;;
  *)
    printf '\nHomologação adiada. Para ver o plano sem custo: ./bin/willtech-homologate.sh --plan\n'
    ;;
esac

# WillTech-General / WILLTECH-BH © 2026 · autoria: github.com/hebwil
