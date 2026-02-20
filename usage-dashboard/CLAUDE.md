# usage-dashboard — Module Rules

## What This Module Does
Tracks token consumption and estimated costs per session, with weekly aggregation and threshold alerting — giving users real-time visibility into their Claude Code usage.

## The Problem It Solves (Validated)
- After Anthropic added weekly caps (August 2025), $200/month Max plan users started hitting weekly limits mid-week with zero warning
- No real-time dashboard exists showing remaining weekly allowance, per-session cost, or projected burn
- The absence of usage transparency is the #1 operational complaint from Claude Code power users
- The "Claude Is Dead" r/ClaudeCode thread after cap introduction is the clearest signal of demand

## Delivery Mechanism
1. **Counter hook**: PostToolUse captures token counts → local SQLite
2. **Aggregator**: weekly/daily summaries
3. **CLI viewer**: `python3 usage-dashboard/cli.py`
4. **Alert hook**: PreToolUse warns before expensive calls when near threshold
5. **Streamlit UI** (optional, after CLI is stable)

## Architecture Rules

**What Gets Tracked:**
- Input tokens per tool call
- Output tokens per tool call
- Model used (Sonnet vs Opus — different pricing)
- Session ID
- Timestamp
- Tool name (which tool consumed the tokens)

**What NEVER Gets Tracked:**
- Content of messages (never log conversation text)
- File contents (never log what was written/read)
- Credentials or API keys
- Anything from other projects on this computer

**Pricing Model (current as of Feb 2026, configurable):**
- Claude Sonnet 4.6: $3/M input tokens, $15/M output tokens
- Claude Opus 4.6: $15/M input tokens, $75/M output tokens
- These are estimates — actual pricing may differ based on Claude Max plan

**Storage:**
- SQLite database: `~/.claude-usage/usage.db`
- Schema: `(id, session_id, timestamp, model, tool_name, input_tokens, output_tokens, cost_estimate)`
- Retention: 90 days by default (configurable)

## File Structure
```
usage-dashboard/
├── CLAUDE.md                   # This file
├── hooks/
│   ├── counter.py              # PostToolUse: capture tokens → SQLite (USAGE-1)
│   └── alert.py                # PreToolUse: threshold warning (USAGE-4)
├── aggregator.py               # Session/weekly aggregation (USAGE-2)
├── cli.py                      # CLI viewer (USAGE-3)
├── app.py                      # Streamlit UI — build last (USAGE-5)
├── tests/
│   └── test_usage.py
└── research/
    └── EVIDENCE.md
```

## Non-Negotiable Rules
- **Never log message content** — token counts only, no text
- **Never log file contents** — track file paths written, not contents
- **SQLite only** — no network calls for storage (local-first, private)
- **Cost estimates are labeled as estimates** — not presented as exact billing
- **CLI must work without Streamlit installed** — Streamlit is optional, not required

## Key Technical Question (Resolve Before Building)
Does the PostToolUse hook payload include token counts?
- Check: hook input schema for `input_tokens`, `output_tokens`, `usage` fields
- If yes: read directly from hook payload (ideal)
- If no: cannot count tokens per-tool — may need to count cumulative from API response headers or use a proxy approach
- This is a critical feasibility question — answer it before writing counter.py

## Build Order
1. USAGE-1: `hooks/counter.py` — token capture (needs feasibility check first)
2. USAGE-2: `aggregator.py` — session and weekly summaries
3. USAGE-3: `cli.py` — human-readable viewer
4. USAGE-4: `hooks/alert.py` — threshold warning
5. USAGE-5: `app.py` — Streamlit dashboard (only if CLI is stable and used)
