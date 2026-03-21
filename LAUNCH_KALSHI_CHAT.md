# Launch Kalshi Bot Chat (3rd Chat)
# Copy-paste these steps in a NEW terminal window.

## Step 1: Open new Terminal window
Cmd+N in Terminal.app (new window, not tab — keeps it separate from CCA)

## Step 2: Navigate and launch
```bash
cd /Users/matthewshields/Projects/polymarket-bot
claude /kalshi-main
```

That's it. `/kalshi-main` runs `/polybot-init` then `/polybot-auto` automatically.

## What the bot chat will do on init:
1. Read SESSION_HANDOFF.md (bot currently STOPPED, all-time +12.28 USD)
2. Read CLAUDE.md (safety rules, architecture rules)
3. Read .planning/CHANGELOG.md (S119 was last session — hour blocks reverted)
4. Run verify.py to check connections
5. Check CCA_TO_POLYBOT.md for any intelligence deliveries (Requests 5+9 answered there)
6. Start autonomous 2-hour monitoring + trading

## Current bot state (as of S119):
- Bot: STOPPED (Matthew paused 2026-03-20)
- All-time P&L: +12.28 USD
- Bankroll: ~179.76 USD
- Sniper: 797 bets, 95.7% WR, +63.21 USD sniper-only
- Hour blocks: REVERTED (both were crash-contaminated)
- eth_drift: DISABLED
- sol_drift: HEALTHY (70% WR, +4.89 USD)
- xrp_drift: LIVE (direction_filter="yes")
- Tests: 1698 passing

## Rate limit note (Max 5x):
This is your 3rd concurrent chat. Keep sessions focused.
The bot chat should run on Sonnet if possible (model selection in /polybot-init).
