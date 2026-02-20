# context-monitor — Research Evidence Base

## Primary Evidence

### Context Rot — Quantified
- Output quality degrades measurably as context fills
- Developer consensus: "past 60-70% full, output quality starts dropping noticeably"
- Sessions over 80%+ context produce "noticeably worse outputs"
- Source: aitooldiscovery.com, paddo.dev, claudefa.st/context-management

### The Compaction Bug — Specifically Documented
- After auto-compact fires, the assistant ignores `.claude/project-context.md` rules
- Previously following rules 100% → violating 100% after compaction
- Binary, not gradual — makes it particularly disruptive
- Source: paddo.dev "Claude Code 2.1 Pain Points Addressed" (confirmed still present post-2.1)

### Community Standard: "Compact at 60%"
- Most consistently recommended operational guideline in r/ClaudeCode
- Currently requires manual monitoring — no automation exists
- Source: aitooldiscovery.com synthesis, multiple blog posts

### Context Rot Is in the Top 3 Pain Points
- Appears in every developer pain point survey reviewed
- Specifically listed alongside rate limits and architectural quality as the top complaints
- Source: redmonk.com "10 Things Developers Want from their Agentic IDEs in 2025"

### The Handoff Pattern (Community-Invented Workaround)
- A `/handoff` command pattern has organically emerged: write a handoff doc before /compact
- Preserves session insights, prevents context loss
- Currently manual — users write this themselves
- Source: multiple r/ClaudeCode posts, awesome-claude-code repository

## Prior Art

| Tool | What It Does | What's Missing |
|------|-------------|----------------|
| Manual /compact | User manually compacts | No automation, no handoff |
| claudia-statusline | Shows context % in status line | No alerting, no handoff trigger |
| ccflare | Usage dashboard | Not context-health focused |
| CLAUDE.md manual review | User adds rules after forgetting | Not compaction-resistant |

**Our differentiator**: Automated threshold detection + auto-handoff trigger + compaction-resistant CLAUDE.md digest. End-to-end solution vs. point tools.

## Technical Research: Hook Payload Schema

### What Claude Code Hooks Receive (from docs, Feb 2026)
Based on Anthropic hooks documentation:
- **PreToolUse**: receives `tool_name`, `tool_input`, `session_id`, conversation history metadata
- **PostToolUse**: receives `tool_name`, `tool_input`, `tool_result`, `session_id`
- **Stop**: receives `stop_reason`, `last_assistant_message`, `session_id`

**Context window percentage availability:**
- Not explicitly documented as a hook field
- Possible approach 1: Parse conversation metadata for token counts if exposed
- Possible approach 2: Count tokens cumulatively across PostToolUse calls (estimation)
- Possible approach 3: Check if `session_id` can be used to query a status endpoint
- Resolution needed before building CTX-1

### Status Line Integration
- Claude Code status line is configurable via `statusline-setup`
- Can read from local state files (written by hooks)
- A hook writes `~/.claude-context-health.json` → status line reads it
- This pattern is the correct architecture (hook writes, statusline reads asynchronously)

## Risk Assessment

| Risk | Likelihood | Mitigation |
|------|-----------|-----------|
| Context % not available in hook payload | Medium | Fall back to cumulative token count estimation |
| Alert hook is too noisy (fires too often) | Medium | Default to warn-only mode, configurable threshold |
| Handoff document is poorly structured | Low | Template with mandatory fields |
| Compaction guard grows stale | Medium | Re-generate on every /compact, TTL on entries |
