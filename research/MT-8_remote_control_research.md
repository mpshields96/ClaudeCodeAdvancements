# MT-8: iPhone Remote Control Research
# Researched: Session 42C, 2026-03-18

## Current State of Remote Control

Anthropic shipped Remote Control officially. It's now built into Claude Code v2.1.51+.
No need to build custom tooling — the native solution covers Matthew's core use case.

## How It Works

1. Start: `claude remote-control` (server mode) or `claude --rc` (interactive mode) or `/rc` in existing session
2. Connect: QR code scan → iPhone Claude app → control the same session
3. Execution stays LOCAL on MacBook — phone is just a remote window

## Three Modes

| Mode | Command | Use Case |
|------|---------|----------|
| Server mode | `claude remote-control` | Headless server, waits for phone connections |
| Interactive + remote | `claude --rc` | Local terminal + phone both active |
| Existing session | `/remote-control` in session | Add remote access to running session |

## Key Features for Matthew's Workflow

- **Multi-session**: Server mode supports `--capacity 32` and `--spawn worktree` for parallel sessions
- **Auto-reconnect**: survives sleep/network drop, reconnects automatically
- **Always-on option**: `/config` → "Enable Remote Control for all sessions" = true
- **Named sessions**: `--name "CCA"` so phone shows clear session list
- **QR code**: press spacebar in server mode to show QR

## Optimizations for Matthew's 2-3 Chat Setup

### Recommended tmux Configuration

```bash
# In dev-start script, launch all sessions with remote control enabled
tmux new-session -d -s cca 'claude remote-control --name "CCA" --spawn worktree'
tmux new-window -t cca 'claude remote-control --name "Kalshi Main" --spawn same-dir'
tmux new-window -t cca 'claude remote-control --name "Kalshi Research" --spawn same-dir'
```

### Always-On Remote Control

Run this ONCE in any Claude Code session:
```
/config → Enable Remote Control for all sessions → true
```
Then every `claude` launch automatically registers for remote access.

### Voice Input Optimization

Slash commands that work well with iOS voice-to-text:
- `/cca-auto` — short, distinct
- `/cca-wrap` — short, distinct
- Simple natural language works: "check the priority queue" → Claude reads MASTER_TASKS.md

### Known Limitations

1. Terminal must stay open (laptop can sleep but not shut down)
2. 10-minute network timeout → session dies (restart needed)
3. One remote session per interactive process (use server mode for multiple)
4. API key auth not supported — must use claude.ai login

## What's Left to Build (CCA-specific)

The native Remote Control covers 90% of what MT-8 envisioned. What's left:
1. **Mobile-friendly status output**: A `/cca-status-mobile` command that outputs a compact summary optimized for small screens
2. **Quick-switch convenience**: With server mode + named sessions, the Claude app shows all sessions in a list — this is basically solved
3. **Voice-optimized slash commands**: Our existing commands are already short enough for voice

## Verdict

MT-8 is largely SOLVED by Anthropic's native Remote Control. Remaining work is minor:
- Configure always-on remote control
- Update dev-start script to use `--name` flags
- Optionally build a compact mobile status command

## Sources

- Official docs: https://code.claude.com/docs/en/remote-control
- Announcement: https://venturebeat.com/orchestration/anthropic-just-released-a-mobile-version-of-claude-code-called-remote
- Third-party (clauderc.com): https://clauderc.com/
