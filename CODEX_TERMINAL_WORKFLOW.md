# Codex Terminal Workflow

This is the Terminal.app version of the CCA/Kalshi chat launcher pattern.

Current preference:
- Codex runs in `Terminal.app`
- Codex desktop/Electron is on hold for now
- Model/access profile is pinned to `gpt-5.4` + high reasoning + danger-full-access + approval `never`

## Shell Shortcuts

One-time setup:

Add this to `~/.zshrc`:

```bash
source ~/Projects/ClaudeCodeAdvancements/codex_shell_helpers.sh
```

What they do:
- `cx` prepares the current terminal for the repo-local Codex workflow and prints the next commands
- `codex init` launches a fresh Codex chat with a repo-aware init prompt and refreshes `CODEX_INIT_PROMPT.md`
- `codex auto` launches a fresh Codex chat with a repo-aware auto-work prompt and refreshes `CODEX_AUTO_PROMPT.md`
- `codex next` launches from the same fresh-chat handoff path as `codex auto` and refreshes `CODEX_AUTO_PROMPT.md`
- `codex wrap` launches a fresh Codex chat with a repo-aware wrap prompt and refreshes `CODEX_WRAP_PROMPT.md`
- `codex chat "<prompt>"` launches a direct ad-hoc Codex chat
- `cxa` jumps to CCA then runs `cx`
- `cxbot` jumps to `polymarket-bot` then runs `cx`
- `cxnext` is a shorthand for `codex next`

Examples:
- `cxa`
- `codex init`
- `codex auto`
- `codex next`
- `cxbot`
- `codex init`

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

Recommended operator flow:

1. Open a new terminal
2. `cxa` or `cxbot`
3. `codex init`
4. Work that chat until a clean stopping point
5. `codex next` for the next fresh execution chat
6. `codex wrap` when closing out a session or changing scope

These reuse the existing Codex-side docs:
- `CODEX_CODEWORDS.md`
- `CODEX_QUICKSTART.md`
- `CODEX_OPERATING_MANUAL.md`

## When To Wrap And Start A New Codex Chat

Wrap the current Codex chat and start a fresh one when any of these is true:

- one branch or one focused task is complete
- 1-2 substantive deliverables have landed
- you need to switch repos, switch branches, or change problem domains
- the chat has become mixed-topic or muddy
- you are re-reading the same files because context has gotten stale
- you need a clean handoff after roughly 60-90 minutes of focused work

Do not keep one Codex chat alive across multiple unrelated tasks just to save startup time.
Fresh chats are usually cheaper than carrying muddy context.

## Fresh-Chat Handoff Artifact

`CODEX_AUTO_PROMPT.md` is now part of the command flow, not just documentation.

- `codex auto` refreshes it before launching
- `codex next` refreshes it before launching
- the next fresh Codex chat should treat it as the current handoff artifact

## Why This Matches The Existing CCA/Kalshi System

The launcher pattern is intentionally the same as `launch_worker.sh` and `launch_kalshi.sh`:
- fresh `Terminal.app` window
- explicit repo root
- explicit runtime profile
- minimal operator typing
- stable chat identity when coordination matters
