# Memory System — Schema Design (MEM-1)
# Status: APPROVED — do not modify without updating capture_hook.py

---

## Storage Location

```
~/.claude-memory/
├── [project-slug].json        # One file per project (e.g., ClaudeCodeAdvancements.json)
└── _global.json               # Cross-project preferences and patterns
```

`project-slug` is derived from the project directory name, lowercased, hyphens for spaces.
Example: `/Users/matthewshields/Projects/ClaudeCodeAdvancements` → `claudecodeadvancements`

---

## Memory Entry Schema

Each memory is a JSON object with these fields:

```json
{
  "id": "mem_20260219_143022_abc",
  "type": "decision",
  "content": "Use SQLite for usage-dashboard storage. SQLite is Python stdlib; JSON is fine for small datasets but SQLite handles queries better at scale.",
  "project": "claudecodeadvancements",
  "tags": ["storage", "usage-dashboard", "architecture"],
  "created_at": "2026-02-19T14:30:22Z",
  "last_used": "2026-02-19T14:30:22Z",
  "confidence": "HIGH",
  "source": "explicit"
}
```

### Field Definitions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Unique. Format: `mem_YYYYMMDD_HHMMSS_xxx` (xxx = 3 random chars) |
| `type` | string | yes | One of the 5 memory types below |
| `content` | string | yes | The memory itself. Max 500 chars. Plain English. |
| `project` | string | yes | Project slug. `"_global"` for cross-project memories. |
| `tags` | string[] | yes | 1–5 tags for retrieval. Lowercase, no spaces (use hyphens). |
| `created_at` | ISO 8601 | yes | When this memory was created |
| `last_used` | ISO 8601 | yes | Last time this memory was surfaced in a session |
| `confidence` | string | yes | `"HIGH"` / `"MEDIUM"` / `"LOW"` (see below) |
| `source` | string | yes | `"explicit"` / `"inferred"` / `"session-end"` (see below) |

---

## Memory Types (5 Categories)

### 1. `decision`
Architectural or design choices with their rationale.

**Good decision memory:**
> "Use stdlib-first. External packages require justification. Anthropic SDK is acceptable; pandas is not unless user explicitly requests."

**Bad (too granular, too volatile):**
> "In capture_hook.py line 42, we use json.dumps with indent=2."

**Rule:** A decision memory must remain valid for at least one month without needing an update.

---

### 2. `pattern`
Recurring code patterns, file organization conventions, or naming rules.

**Good pattern memory:**
> "Hook files live in module/hooks/. Hook scripts read JSON from stdin, write JSON to stdout. Never import across modules."

**Good pattern memory:**
> "Test files: test_[module_name].py. Smoke test entry point: if __name__ == '__main__'. Always run smoke tests before promoting from research/."

---

### 3. `error`
Error resolutions — a mistake that was made, the diagnosis, and the fix.

**Good error memory:**
> "PostToolUse hooks do NOT receive token counts. The hook payload contains tool_input and tool_response only. For usage tracking, parse the transcript JSONL file instead."

**Good error memory:**
> "PreToolUse deny format uses hookSpecificOutput.permissionDecision, NOT top-level decision. Using top-level 'block' silently fails on PreToolUse."

---

### 4. `preference`
User-specific workflow preferences and communication style rules.

**Good preference memory:**
> "Always explain what code does in plain English alongside the code. No emojis. End every response with 'Advancement tip: ...'."

**Good preference memory:**
> "Read PROJECT_INDEX.md before SESSION_STATE.md. Never jump to implementation without reading schema.md first for memory-system."

---

### 5. `glossary`
Project-specific terms, abbreviations, and domain vocabulary.

**Good glossary memory:**
> "MEM-1 = memory schema design task. SPEC-1 = requirements slash command task. CTX-1 = context meter hook. Frontier 1 = memory-system module."

**Good glossary memory:**
> "rat poison = features that look useful but damage the work. In this project: overengineering, scope creep into Titanium, speculative features without evidence."

---

## Confidence Levels

| Level | Meaning | When to Use |
|-------|---------|-------------|
| `HIGH` | Explicitly instructed by user or confirmed correct multiple times | User said "always do X", or user confirmed after Claude did X |
| `MEDIUM` | Inferred from behavior, not explicitly stated | Claude noticed a pattern across 2–3 sessions |
| `LOW` | Speculative, single observation, uncertain | Captured once, not yet confirmed |

**Session start behavior:**
- `HIGH` memories: always surface
- `MEDIUM` memories: surface if relevant to current task
- `LOW` memories: surface only on explicit `/memory:search` calls

---

## Source Types

| Source | Meaning |
|--------|---------|
| `explicit` | User directly stated this (e.g., "remember that X", "always use Y") |
| `inferred` | Captured from hook observing tool usage patterns |
| `session-end` | Captured via the Stop hook from `last_assistant_message` summary |

---

## Storage File Format

`~/.claude-memory/[project-slug].json`:

```json
{
  "project": "claudecodeadvancements",
  "schema_version": "1.0",
  "created_at": "2026-02-19T14:00:00Z",
  "last_updated": "2026-02-19T14:30:22Z",
  "memories": [
    {
      "id": "mem_20260219_140000_abc",
      "type": "decision",
      "content": "...",
      "project": "claudecodeadvancements",
      "tags": ["architecture"],
      "created_at": "2026-02-19T14:00:00Z",
      "last_used": "2026-02-19T14:00:00Z",
      "confidence": "HIGH",
      "source": "explicit"
    }
  ]
}
```

---

## What NEVER Gets Stored (Absolute Rules)

These are filtered before any write, regardless of instruction:

1. **API keys and secrets** — regex filter: anything matching `sk-`, `Bearer `, `SUPABASE_KEY`, `API_KEY=`, AWS credential patterns
2. **Passwords and tokens** — regex filter: `password`, `token`, `secret`, `credential` adjacent to `=` or `:`
3. **Full file contents** — memory content max is 500 chars; never capture entire file dumps
4. **Full conversation logs** — capture summary/decisions only, not raw dialogue
5. **Data from other projects** — `project` field must match current working directory slug
6. **Anything outside the ClaudeCodeAdvancements folder** during this project

---

## Retrieval Logic (for MCP server, MEM-3)

On session start, surface memories in this order:
1. All `HIGH` confidence memories for the current project
2. All `_global` memories with `HIGH` confidence
3. `MEDIUM` memories matching tags of the current task (if task context provided)

Search behavior (`/memory:search [query]`):
- Tag exact match (highest priority)
- Content keyword match (substring, case-insensitive)
- Return max 10 results, sorted by `last_used` descending

---

## Retention Policy

- Default TTL: 180 days from `last_used`
- `HIGH` confidence memories: 365 days
- Auto-purge runs on `/memory:purge` command (MEM-5)
- User can delete any memory by id: `/memory:delete mem_20260219_143022_abc`

---

## Design Decisions (Rationale)

**Why 500-char content limit?**
Memories must be scannable in < 2 seconds. Longer entries become documentation, not memory.

**Why JSON not SQLite for storage?**
Human-readable without tooling. User can inspect and edit `~/.claude-memory/project.json` in any text editor. Migrate to SQLite if a project exceeds ~1000 memories (unlikely in practice).

**Why 5 types, not freeform?**
Freeform tagging without type discipline degrades into noise. 5 types forces the author (Claude or the user) to categorize clearly, which improves retrieval accuracy.

**Why local files, not MCP server storage?**
User owns the data. No external dependency. No credentials needed. Zero privacy surface.
