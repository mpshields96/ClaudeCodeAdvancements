# Codex Terminal Workflow

This is the Terminal.app version of the CCA/Kalshi chat launcher pattern.

Current preference:
- Codex runs in `Terminal.app`
- Codex desktop/Electron is on hold for now
- Model/access profile is pinned to `gpt-5.4` + high reasoning + danger-full-access + approval `never`

## Shell Shortcuts

Add these to `~/.zshrc`:

```bash
export CODEX_BIN="/Applications/Codex.app/Contents/Resources/codex"
if [[ -x "$CODEX_BIN" && ":$PATH:" != *":/Applications/Codex.app/Contents/Resources:"* ]]; then
  export PATH="$PATH:/Applications/Codex.app/Contents/Resources"
fi

codex54() {
  if [[ ! -x "$CODEX_BIN" ]]; then
    echo "Codex binary not found at $CODEX_BIN" >&2
    return 127
  fi

  "$CODEX_BIN" -m gpt-5.4 -c 'model_reasoning_effort="high"' -s danger-full-access -a never "$@"
}

cx() {
  local cwd root
  cwd="$PWD"
  root="$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null || true)"

  if [[ "$cwd" == "$HOME/Projects/ClaudeCodeAdvancements"* || "$root" == "$HOME/Projects/ClaudeCodeAdvancements" ]]; then
    export CCA_CHAT_ID=codex
  elif [[ "$cwd" == "$HOME/Projects/polymarket-bot"* || "$root" == "$HOME/Projects/polymarket-bot" ]]; then
    export CCA_CHAT_ID=codex
  fi

  codex54 "$@"
}

alias cxa='cd ~/Projects/ClaudeCodeAdvancements && cx'
alias cxbot='cd ~/Projects/polymarket-bot && cx'
```

What they do:
- `cx` starts Codex in the current repo with the full Codex profile and auto-sets `CCA_CHAT_ID=codex` when launched from CCA or Kalshi
- `cxa` starts Codex in CCA using that same smart `cx` behavior
- `cxbot` starts Codex in the Kalshi repo with that same smart `cx` behavior

Examples:
- `cxa "CCA init"`
- `cxa "CCA go: review launch scripts, no state-file edits"`
- `cxbot "Kalshi init"`

## Fresh Terminal Windows

Repo-local launcher:

```bash
cd ~/Projects/ClaudeCodeAdvancements
bash launch_codex.sh
bash launch_codex.sh cca "CCA init"
bash launch_codex.sh kalshi "Kalshi init"
```

What it does:
1. Opens a new `Terminal.app` window
2. Moves to the correct repo
3. Starts Codex with explicit `gpt-5.4` / high / danger-full-access / approval `never`
4. Sets `CCA_CHAT_ID=codex` for CCA sessions

## CCA Comms Identity

`cx` now auto-sets this when launched from either hivemind repo:

```bash
export CCA_CHAT_ID=codex
```

That makes the existing internal comms work as designed:
- `python3 cca_comm.py inbox`
- `python3 cca_comm.py say desktop "message"`
- `python3 cca_comm.py done "summary"`

## Startup Ritual

Recommended first prompts:
- `CCA init`
- `Kalshi init`
- `CCA go: <task>`

These reuse the existing Codex-side docs:
- `CODEX_CODEWORDS.md`
- `CODEX_QUICKSTART.md`
- `CODEX_OPERATING_MANUAL.md`

## Why This Matches The Existing CCA/Kalshi System

The launcher pattern is intentionally the same as `launch_worker.sh` and `launch_kalshi.sh`:
- fresh `Terminal.app` window
- explicit repo root
- explicit runtime profile
- minimal operator typing
- stable chat identity when coordination matters
