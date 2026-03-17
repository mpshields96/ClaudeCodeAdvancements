# Kalshi Bot — Daily Operations Cheat Sheet

## Start Everything

```bash
dev-start           # CCA + both Kalshi chats, fully automated
dev-start kalshi    # just the 2 Kalshi chats (no CCA)
```

One command. Both chats launch, receive /polybot-init, /polybot-auto (or /polybot-autoresearch), and full operating instructions. They start working autonomously.

## Switch Between Chats

| Keys | Window |
|------|--------|
| `Ctrl+b, 0` | CCA (ClaudeCodeAdvancements) |
| `Ctrl+b, 1` | Kalshi main (live bets + monitoring) |
| `Ctrl+b, 2` | Kalshi research (new edges + bug prevention) |

## Chime In

Just switch to the chat window and type. Claude Code's prompt (`>`) is always at the bottom.

## Wrap Up

1. `Ctrl+b, 1` — switch to main chat, type `/polybot-wrap`
2. `Ctrl+b, 2` — switch to research chat, type `/polybot-wrapresearch`
3. Wait for both to finish their wrap-up
4. Start fresh next time with `dev-start` or `dev-start kalshi`

## If Something Goes Wrong

| Problem | Fix |
|---------|-----|
| tmux session already exists | `dev-start` auto-reattaches — just run it again |
| Need to kill everything | `tmux kill-session -t dev` |
| Script broke | Restore backup: `cp ~/.local/bin/dev-start.backup-20260316 ~/.local/bin/dev-start` |
| Claude takes too long to load | Edit `WAIT=10` to `WAIT=15` in `~/.local/bin/dev-start` |
| Detach without killing | `Ctrl+b, d` — sessions keep running in background |

## What Each Chat Does

**Main chat** (`kalshi-1`): Maintains live bets, monitors the bot for bugs/glitches, keeps guards running, wins money using sniper bet approach from March 14.

**Research chat** (`kalshi-2`): Finds new bets, markets, and edges. Ensures no bugs or guard fails. Does NOT touch live bets — that's the main chat's job.

Both chats run autonomously for 2 hours. When a session ends, they start a new one.

## Script Location

`~/.local/bin/dev-start`
