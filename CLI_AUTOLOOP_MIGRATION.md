# CLI Autoloop Migration Guide

Full migration from Claude Desktop (Electron) to Claude CLI (Terminal.app).
Reduces MacBook thermal load by eliminating Electron renderer processes.

---

## Quick Start (CCA)

Open Terminal.app and run:

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements

# Option A: Shell-based loop (recommended — simplest)
./start_autoloop.sh

# Option B: Python-based loop (more options)
python3 cca_autoloop.py start

# Option C: Run in tmux (detach and come back later)
./start_autoloop.sh --tmux
```

That's it. The loop reads SESSION_RESUME.md, spawns `claude`, waits for it to finish, reads the new SESSION_RESUME.md, and repeats.

---

## What Happens

1. Loop reads `SESSION_RESUME.md` (written by `/cca-wrap`)
2. Spawns: `claude --dangerously-skip-permissions --model opus "/cca-init ... resume prompt ..."`
3. Claude runs autonomously: `/cca-init` -> `/cca-auto` -> `/cca-wrap`
4. `/cca-wrap` writes new `SESSION_RESUME.md`
5. Claude exits, loop reads new resume, spawns next session
6. Repeats until max iterations (50) or safety stop

---

## Configuration

Environment variables (optional):

```bash
# Max iterations before stopping (default: 50)
CCA_AUTOLOOP_MAX=10 ./start_autoloop.sh

# Cooldown between sessions in seconds (default: 15)
CCA_AUTOLOOP_COOLDOWN=30 ./start_autoloop.sh

# Model strategy: round-robin | opus-primary | sonnet-primary (default: round-robin)
MODEL_STRATEGY=opus-primary ./start_autoloop.sh
```

---

## Controls

```bash
# Check status
./start_autoloop.sh --status
# or
python3 cca_autoloop.py status

# Pause (loop stays alive but stops spawning new sessions)
python3 autoloop_pause.py pause

# Resume
python3 autoloop_pause.py resume

# Toggle pause/resume
python3 autoloop_pause.py toggle

# Stop: Ctrl-C in the terminal running the loop
```

---

## Safety Features

- **Max 50 iterations** — prevents infinite loops
- **3 consecutive crashes = auto-stop** — something is broken
- **3 consecutive short sessions (<30s) = auto-stop** — something is wrong
- **Rate limit detection** — exit codes 2/75 trigger 5-minute cooldown
- **Duplicate session guard** — won't start if another CCA CLI session is running
- **Stale resume detection** — logs when SESSION_RESUME.md hasn't changed
- **ANTHROPIC_API_KEY unset** — always uses Max subscription, never API credits
- **Audit log** — every iteration logged to `~/.cca-autoloop.log`

---

## CLI Mode Environment Variable

When running under the autoloop, `CCA_AUTOLOOP_CLI=1` is set automatically.
This tells the in-session trigger (Step 10 of /cca-wrap) and the stop hook
to skip desktop automation — the outer loop handles session chaining.

You do NOT need to set this manually. The loop sets it for you.

---

## tmux Setup (Recommended for Overnight)

```bash
# Create a tmux session and start the loop
./start_autoloop.sh --tmux

# Detach: Ctrl-B then D
# Reattach later:
tmux attach -t cca-workspace:cca-autoloop

# Check status without attaching:
./start_autoloop.sh --status
```

---

## Thermal Comparison

| Setup | Approximate RAM | CPU Idle |
|-------|----------------|----------|
| Claude Desktop (Electron) | ~500-800 MB | 3-5% |
| Claude CLI (`claude` binary) | ~50-100 MB | <1% |
| Savings per chat | ~400-700 MB | ~3-4% |

With 3 chats (CCA + Codex + Kalshi), CLI saves ~1.5-2 GB RAM and ~10% CPU.

---

## Preflight Check

Before first run, verify everything is ready:

```bash
python3 cca_autoloop.py preflight
```

Expected output: all PASS. If any FAIL, fix before launching.

---

## Files Changed (S226)

| File | Change |
|------|--------|
| `autoloop_trigger.py` | Added `is_cli_mode()` — writes breadcrumb only in CLI mode; outer loop handles chaining |
| `autoloop_stop_hook.py` | Added `is_cli_mode()` — skips trigger fire in CLI mode |
| `start_autoloop.sh` | Sets `CCA_AUTOLOOP_CLI=1` before spawning claude |
| `cca_autoloop.py` | Sets `CCA_AUTOLOOP_CLI=1` in subprocess env |
| `tests/test_autoloop_stop_hook.py` | 9 new CLI mode tests (38 total) |
