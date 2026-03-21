# Launch Kalshi Chat for MT-0 Phase 2
# Copy-paste in a NEW Terminal window (Cmd+N)

## Step 1: Open new Terminal window
Cmd+N in Terminal.app

## Step 2: Launch
```bash
cd /Users/matthewshields/Projects/polymarket-bot && claude
```

## Step 3: Paste this as your first message to the Kalshi chat:

```
Read these files IN ORDER before doing anything:

1. /Users/matthewshields/Projects/ClaudeCodeAdvancements/KALSHI_MT0_TASK_BRIEF.md
   (Your mission — MT-0 Phase 2 self-learning deployment)

2. SESSION_HANDOFF.md
   (Current bot state — STOPPED, +12.28 USD all-time)

3. .planning/PRINCIPLES.md
   (Safety rules for any strategy/risk changes)

Then execute the task brief autonomously. TDD. Commit after each component.

Start the bot in background first: source venv/bin/activate && python main.py --live > /tmp/polybot_s120.log 2>&1 &

Then build Task 1 (trading_journal.py) with tests.

Report progress to CCA via:
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/cross_chat_queue.py send --from km --to cca --priority medium --category status_update --subject "progress" --body "description"

When blocked or done with a task, check for CCA messages:
python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/cross_chat_queue.py unread --for km
```

## What happens next:
- Kalshi chat builds self-learning integration (Tasks 1-4)
- CCA Desktop (this chat) monitors via cross_chat_queue
- CCA Desktop reviews schemas, provides feedback, adjusts priorities
- Bot runs in background earning while development happens in foreground
