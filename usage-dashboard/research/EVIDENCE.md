# usage-dashboard — Research Evidence Base

## Primary Evidence

### The Weekly Cap Addition (August 28, 2025) — Trigger Event
- Anthropic added weekly caps to Claude Code on top of existing 5-hour rotating limits
- $200/month Max plan subscribers reported hitting weekly caps before Friday
- No real-time usage meter was provided alongside the cap
- Viral "Claude Is Dead" thread on r/ClaudeCode followed
- Source: tessl.io, The Register (Jan 5, 2026), like2byte.com

### #1 Operational Frustration — Confirmed Across Multiple Sources
- Rate limits and usage transparency is the highest-frequency complaint across r/ClaudeCode
- Listed in top 3 frustrations in every developer pain point analysis reviewed
- "No granular token accounting dashboard for understanding consumption" — The Register, Jan 2026
- Source: aitooldiscovery.com, tessl.io, like2byte.com

### Community Workarounds (Demand Signal)
| Tool | What It Does | Status |
|------|-------------|--------|
| CC Usage | Token consumption tracker | Unofficial, community-built |
| ccflare | Usage dashboard | Unofficial |
| claudia-statusline | Context status in status bar | Partial (context %, not weekly totals) |

All are unofficial. Their existence is direct evidence of demand for native transparency.

### Power User Cost Reality
- Claude Code costs approximately $100-200/developer/month with Sonnet 4.6 under normal usage
- Parallel agent workflows multiply costs significantly (each agent = full token consumption)
- High variance with no visibility is the core problem
- Source: aitooldiscovery.com, aitools analysis

### Anthropic's Own Statement on Limits
- Pricing page says "extra usage limits apply" without specifying amounts or consequences
- No in-product usage meter exists as of February 2026
- Source: The Register, Jan 5, 2026

## Technical Feasibility

### Hook Payload Research: Token Data Availability
Research suggests PostToolUse hook payloads may include:
- `tool_result`: the output of the tool (varies by tool)
- `session_id`: for session-level aggregation
- Model metadata (model being used)

**Critical unknown**: whether `input_tokens` / `output_tokens` / usage metadata is explicitly exposed.

If token counts are NOT in the hook payload:
- Alternative 1: Count tokens cumulatively from session state (approximation)
- Alternative 2: Use tiktoken or a simple word-count approximation
- Alternative 3: Track tool call frequency as a cost proxy (imprecise but useful)

This requires testing before building counter.py.

### SQLite for Local Storage
- Python stdlib `sqlite3` — zero dependency
- Handles years of data at the usage volumes expected
- Human-readable via DB Browser for SQLite if user wants to inspect directly

### Pricing Model Accuracy
Current Claude Max plan pricing (February 2026, estimated):
- Users pay for the Max subscription, not per-token directly
- BUT: token counts still matter because they determine when caps are hit
- Dashboard value: knowing HOW MANY tokens you use helps predict when you'll hit limits
- "Cost estimate" = tokens × API rate (useful reference, not actual billing)

## Risk Assessment

| Risk | Likelihood | Mitigation |
|------|-----------|-----------|
| Token counts not in hook payload | Medium | Test before building; use approximation if needed |
| User hits limits before dashboard warns | Low | Alert fires before 80% threshold by default |
| SQLite DB grows large | Low | 90-day retention default, auto-prune |
| Pricing changes invalidate estimates | Medium | Label estimates as estimates; configurable rates |
| User thinks estimates are exact billing | Medium | Clear "ESTIMATE" label on all cost displays |
