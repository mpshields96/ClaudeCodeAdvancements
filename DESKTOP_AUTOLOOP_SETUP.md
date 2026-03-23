# Desktop Auto-Loop Setup Guide (MT-22)

Self-sustaining CCA loop in the Claude desktop app (Electron).
Like OpenClaw's Mac Mini pattern: starts sessions, works autonomously,
wraps, starts the next session. You watch and interact freely.

---

## Prerequisites

1. **Claude.app** installed at `/Applications/Claude.app`
2. **Accessibility permissions** for Terminal.app (or whatever app runs the script)
3. **SESSION_RESUME.md** exists (written by a previous `/cca-wrap`)

---

## Grant Accessibility Permissions (macOS 15 Sequoia)

The auto-loop sends keystrokes to Claude.app via System Events.
macOS requires explicit Accessibility permission for this.

1. Open **System Settings** > **Privacy & Security** > **Accessibility**
2. Click the **+** button
3. Add **Terminal.app** (or iTerm2, whatever runs the script)
4. Toggle ON
5. You may need to restart Terminal after granting

**Verify**: Run `python3 desktop_automator.py preflight` — all checks should PASS.

---

## Quick Start

```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements

# 1. Check readiness
./start_desktop_autoloop.sh --preflight

# 2. Open Claude.app (if not already running)
open /Applications/Claude.app

# 3. Start the auto-loop
./start_desktop_autoloop.sh
```

---

## How It Works

```
Loop iteration:
  1. Read SESSION_RESUME.md (written by previous /cca-wrap)
  2. Activate Claude.app (bring to foreground)
  3. Cmd+N to start new conversation (skipped on first iteration)
  4. Paste resume prompt via clipboard
  5. Cmd+Return to send
  6. Monitor SESSION_RESUME.md for mtime change (= session wrapped)
  7. Cooldown (15s default)
  8. Repeat from step 1
```

**Signal mechanism**: When `/cca-wrap` runs at the end of a session, it writes
a new `SESSION_RESUME.md`. The loop detects the file change and knows it's
time for the next iteration.

---

## Options

```bash
# Dry run (simulates without sending keystrokes)
./start_desktop_autoloop.sh --dry-run

# Limit iterations
./start_desktop_autoloop.sh --max-iterations 5

# Force a specific model
./start_desktop_autoloop.sh --model opus
./start_desktop_autoloop.sh --model sonnet

# Custom cooldown between sessions
./start_desktop_autoloop.sh --cooldown 30
```

---

## Safety

| Protection | Threshold | What happens |
|-----------|-----------|-------------|
| Max iterations | 50 (default) | Loop stops |
| Consecutive crashes | 3 | Loop stops |
| Consecutive short sessions | 3 (<30s each) | Loop stops |
| Keystroke safety | Always | Only sends if Claude is frontmost app |
| Audit trail | Always | Every action logged to ~/.cca-desktop-autoloop.jsonl |

---

## Monitoring

While the loop runs, you can:

- **Watch Claude.app** — it's right there on screen, working
- **Interact with it** — type in the chat, run commands, ask questions
- **Check status**: `./start_desktop_autoloop.sh --status`
- **Read audit log**: `tail -f ~/.cca-desktop-autoloop.jsonl | python3 -m json.tool`
- **Stop**: Ctrl+C in the terminal running the script

---

## Files

| File | Purpose |
|------|---------|
| `desktop_automator.py` | Low-level AppleScript control (activate, send, close) |
| `desktop_autoloop.py` | Loop orchestrator (resume watcher, state, iterations) |
| `start_desktop_autoloop.sh` | One-command launcher |
| `~/.cca-desktop-autoloop.jsonl` | Audit trail (every action timestamped) |
| `~/.cca-desktop-autoloop-state.json` | Persistent loop state |

---

## Troubleshooting

**"Accessibility permissions required"**
→ System Settings > Privacy & Security > Accessibility > Add Terminal.app

**"Claude not running"**
→ Open Claude.app first: `open /Applications/Claude.app`

**Keystrokes going to wrong app**
→ The automator always verifies Claude is frontmost. If another app steals focus,
  the iteration fails safely (logged as activate_failed, not sent to wrong app).

**Loop stops after 3 iterations**
→ Check if sessions are crashing (exit code != 0) or too short (<30s).
  Read the audit log: `cat ~/.cca-desktop-autoloop.jsonl | python3 -m json.tool`

**SESSION_RESUME.md not updating**
→ Make sure `/cca-wrap` runs at the end of each session. The auto commands
  (`/cca-auto`) should wrap automatically when context is exhausted.

---

## First Supervised Run

Before trusting unsupervised operation:

1. Run `./start_desktop_autoloop.sh --max-iterations 2`
2. Watch both iterations complete
3. Verify: Claude.app received the prompt, worked, wrapped, next session started
4. Check audit log for any errors
5. Once 3 clean supervised runs pass, approved for longer autonomous use
