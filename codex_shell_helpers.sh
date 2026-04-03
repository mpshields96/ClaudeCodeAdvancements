# codex_shell_helpers.sh — Source this from ~/.zshrc for Terminal-first Codex workflow.

export CODEX_BIN="${CODEX_BIN:-/Applications/Codex.app/Contents/Resources/codex}"

__codex_find_bin() {
  if [[ -x "$CODEX_BIN" ]]; then
    printf '%s\n' "$CODEX_BIN"
    return 0
  fi

  local found
  found="$(command -v codex 2>/dev/null || true)"
  if [[ -n "$found" ]]; then
    printf '%s\n' "$found"
    return 0
  fi

  echo "Codex binary not found. Set CODEX_BIN or install Codex CLI." >&2
  return 127
}

__codex_prepare_env() {
  local cwd root
  cwd="$PWD"
  root="$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null || true)"

  if [[ "$cwd" == "$HOME/Projects/ClaudeCodeAdvancements"* || "$root" == "$HOME/Projects/ClaudeCodeAdvancements" ]]; then
    export CCA_CHAT_ID=codex
  elif [[ "$cwd" == "$HOME/Projects/polymarket-bot"* || "$root" == "$HOME/Projects/polymarket-bot" ]]; then
    export CCA_CHAT_ID=codex
  fi
}

codex() {
  __codex_prepare_env || return $?

  local sub="${1:-}"
  case "$sub" in
    init|auto|next|wrap)
      shift
      python3 "$HOME/Projects/ClaudeCodeAdvancements/codex_cmd.py" "$sub" --launch "$@"
      ;;
    chat)
      shift
      python3 "$HOME/Projects/ClaudeCodeAdvancements/codex_cmd.py" chat "$@"
      ;;
    *)
      local bin
      bin="$(__codex_find_bin)" || return $?
      "$bin" "$@"
      ;;
  esac
}

cx() {
  __codex_prepare_env || return $?

  if [[ $# -gt 0 ]]; then
    codex chat "$*"
    return $?
  fi

  echo "Codex workflow ready in: $PWD"
  echo "Next commands:"
  echo "  codex init"
  echo "  codex auto"
  echo "  codex wrap"
  echo "  codex chat \"<prompt>\""
  echo ""
  echo "Fresh-chat handoff artifact:"
  echo "  CODEX_AUTO_PROMPT.md"
}

alias cxa='cd ~/Projects/ClaudeCodeAdvancements && cx'
alias cxbot='cd ~/Projects/polymarket-bot && cx'
alias cxnext='codex auto'
