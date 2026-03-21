# Wiring Queue Hook into Kalshi Bot Settings
# S107 — Prep for 3-chat cross-chat communication
#
# Status: READY TO APPLY (manual step by Matthew or Kalshi chat)

## What This Does

The queue_hook.py lets Kalshi chats automatically see messages from CCA.
Currently only CCA chats have this hook wired. Adding it to the Kalshi
bot settings means Kalshi research/main chats will see CCA deliveries
without manually reading bridge files.

## What to Add

Add these two hook entries to `/Users/matthewshields/Projects/polymarket-bot/.claude/settings.local.json`:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/queue_hook.py"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/queue_hook.py"
          }
        ]
      }
    ]
  }
}
```

## Notes

- No env var needed — queue_hook.py auto-detects `km` (Kalshi main) from CWD containing "polymarket-bot"
- The hook reads from CCA's `cross_chat_queue.jsonl` — absolute path, works from any directory
- Throttled: PostToolUse checks every 30 seconds to avoid latency
- UserPromptSubmit always checks (user deserves fresh context)
- Performance: <5ms per invocation

## Important

This hook ONLY reads. It does NOT write to any files. The Kalshi chat
can send messages back by writing to `POLYBOT_TO_CCA.md` in its own project.

## When to Apply

Apply this BEFORE Phase 4 (dry run) of the 3-chat gameplan. It's a prerequisite
for automated cross-chat communication to work.
