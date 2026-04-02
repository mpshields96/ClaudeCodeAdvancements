# /cca-review — Review URL for ClaudeCodeAdvancements

Spawn the cca-reviewer agent to review the URL(s) in isolation.
Agent context keeps Reddit comment trees and analysis out of the main session.

## Usage

The user's message contains the URL (or multiple URLs). For each URL:

Spawn the cca-reviewer agent:

```
Agent(
  subagent_type="cca-reviewer",
  prompt="Review this URL: <URL>\n\nDeliver a full verdict in the standard format (REVIEW / FRONTIER / RAT POISON / WHAT IT IS / WHAT WE CAN STEAL / IMPLEMENTATION / VERDICT / WHY)."
)
```

For multiple URLs, spawn one agent per URL — all in a SINGLE message for parallelism.

## After the agent completes

Display the agent's verdict. Then:

**If verdict is BUILD or ADAPT:**
Run `/gsd:add-todo [one-line description of what to build, referencing the URL]`
This captures the idea so it doesn't get lost.

## Fallback

If the agent tool is unavailable or fails, review inline:
1. Read the URL (reddit_reader.py for Reddit, WebFetch for others)
2. Follow the review steps in `~/.claude/agents/cca-reviewer.md`
3. Deliver verdict in the standard format

## Rules

- Never ask the user questions — deliver the full verdict autonomously
- BUILD verdict requires: clear user pain point + feasible implementation + frontier mapping
- Most things are REFERENCE or SKIP — be honest
- If multiple URLs provided, review each one separately
- Do not expose API keys, balances, or financial info
