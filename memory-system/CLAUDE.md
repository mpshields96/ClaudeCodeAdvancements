# memory-system — Module Rules

## What This Module Does
Builds a persistent cross-session memory system for Claude Code.
Every session currently starts from zero. This fixes that.

## The Problem It Solves (Validated)
- GitHub Issue #14227: "Persistent Memory Between Claude Code Sessions" — one of the highest-voted Claude Code feature requests
- Community workarounds exist (claude-mem, memory-mcp, claude-cognitive) but are unofficial and brittle
- The compaction bug: CLAUDE.md rules are forgotten after context compaction fires

## Delivery Mechanism
1. **Capture**: Claude Code hooks (PostToolUse + Stop) detect and store significant events
2. **Retrieval**: Local MCP server serves memories as tool results on session start
3. **Management**: CLI tool for viewing, editing, and pruning memories

## Architecture Rules

**What gets stored:**
- Architectural decisions ("We decided to use SQLite instead of PostgreSQL because...")
- Error resolutions ("Fixed circular import by deferring X import to function body")
- User preferences ("Always use stdlib-first. No pandas unless explicitly asked.")
- Project glossary ("Sharp Score = weighted composite 0-100. Threshold=45.")
- File patterns ("All math lives in edge_calculator.py. Never mix API + math.")

**What NEVER gets stored:**
- Full conversation logs (too large, too noisy)
- Credentials, API keys, tokens (security boundary — absolute)
- Raw code snippets (too volatile — code changes; decisions don't)
- PII of any kind
- Anything from outside this project folder

## Storage Format
- Local JSON files (human-readable, no external DB)
- One file per project: `.claude-memory/[project-name].json`
- Each memory: `{id, type, content, project, created_at, last_used, confidence}`
- Confidence: HIGH (explicitly instructed) | MEDIUM (inferred) | LOW (speculative)

## File Structure
```
memory-system/
├── CLAUDE.md                   # This file
├── schema.md                   # Memory data schema (MEM-1)
├── capture_hook.py             # PostToolUse + Stop capture (MEM-2)
├── mcp_server.py               # Local MCP server for retrieval (MEM-3)
├── commands/
│   └── handoff.md              # /handoff slash command (MEM-4)
├── cli.py                      # Memory viewer + pruner (MEM-5)
├── tests/
│   └── test_memory.py          # Smoke tests
└── research/
    └── EVIDENCE.md             # Validated pain points + prior art
```

## Non-Negotiable Rules
- **Never read memory from other projects without explicit user instruction**
- **Never store credentials even if they appear in hook payloads — filter them out**
- **Schema must be approved before any code is written**
- **All storage is local — no network calls for memory read/write**
- **User can purge all memories with one command — no lock-in**

## Build Order (Do Not Reorder)
1. MEM-1: `schema.md` — approved schema before any code
2. MEM-2: `capture_hook.py` — capture before retrieval
3. MEM-3: `mcp_server.py` — retrieval after capture exists
4. MEM-4: `commands/handoff.md` — compaction-resistant handoff
5. MEM-5: `cli.py` — management UI last
