# Project Index: ClaudeCodeAdvancements
# Generated: 2026-02-19 (Session 1) | Last updated: 2026-02-20 (Session 2)
# Read this FIRST each session — ~94% token reduction vs reading all source files

---

## Quick Orientation

| What | Where |
|------|-------|
| Project rules + scope boundary | `CLAUDE.md` |
| Feature backlog + priorities | `ROADMAP.md` |
| Current state + next actions | `SESSION_STATE.md` |
| This file (read first) | `PROJECT_INDEX.md` |
| GitHub | https://github.com/mpshields96/ClaudeCodeAdvancements |

**Mission:** Build validated next-generation advancements for Claude Code users. NOT a betting project.

**Scope boundary:** Read + write `/Users/matthewshields/Projects/ClaudeCodeAdvancements/` ONLY. Absolute.

---

## Project Structure

```
ClaudeCodeAdvancements/
├── CLAUDE.md                        # Master rules — scope, rat poison, session workflow
├── ROADMAP.md                       # Authoritative feature backlog + sub-tasks
├── PROJECT_INDEX.md                 # This file
├── SESSION_STATE.md                 # Current state, test counts, next actions
│
├── memory-system/                   # Frontier 1: Persistent cross-session memory
│   ├── CLAUDE.md                    # Module rules
│   ├── schema.md                    # APPROVED data schema (MEM-1)
│   ├── hooks/
│   │   └── capture_hook.py          # PostToolUse + Stop capture (MEM-2) ✅
│   ├── tests/
│   │   └── test_memory.py           # 37 tests — all passing
│   └── research/
│       └── EVIDENCE.md              # Validated pain points + prior art
│
├── spec-system/                     # Frontier 2: Spec-driven development
│   ├── CLAUDE.md                    # Module rules
│   ├── commands/
│   │   ├── requirements.md          # /spec:requirements slash command (SPEC-1) ✅
│   │   ├── design.md                # /spec:design slash command (SPEC-2) ✅
│   │   ├── tasks.md                 # /spec:tasks slash command (SPEC-3) ✅
│   │   └── implement.md             # /spec:implement slash command (SPEC-4) ✅
│   ├── hooks/
│   │   └── validate.py              # PreToolUse spec guard (SPEC-5) ✅
│   ├── tests/
│   │   └── test_spec.py             # 26 tests — all passing
│   └── research/
│       └── EVIDENCE.md
│
├── context-monitor/                 # Frontier 3: Context health + compaction guard
│   ├── CLAUDE.md                    # Module rules
│   └── research/
│       └── EVIDENCE.md              # Compaction bug + transcript-parsing approach
│
├── agent-guard/                     # Frontier 4: Multi-agent conflict prevention
│   ├── CLAUDE.md                    # Module rules
│   └── research/
│       └── EVIDENCE.md
│
└── usage-dashboard/                 # Frontier 5: Token + cost transparency
    ├── CLAUDE.md                    # Module rules
    └── research/
        └── EVIDENCE.md              # Weekly cap problem + transcript approach
```

---

## Entry Points

| Command | What it does |
|---------|-------------|
| `python3 memory-system/tests/test_memory.py` | Run memory-system smoke tests (37 tests) |
| `python3 spec-system/tests/test_spec.py` | Run spec-system smoke tests (26 tests) |
| `python3 memory-system/hooks/capture_hook.py` | Stdin: hook JSON → stdout: memory JSON (direct test) |
| `python3 spec-system/hooks/validate.py` | Stdin: hook JSON → stdout: decision JSON (direct test) |

**Session start:** Run both test commands first. If anything fails, fix before touching other files.

---

## Core Module APIs

### memory-system/hooks/capture_hook.py (MEM-2)
Handles `PostToolUse` and `Stop` hook events. Reads JSON from stdin, writes JSON to stdout.

| Function | Purpose |
|----------|---------|
| `handle_post_tool_use(hook_input)` | Detects Write/Edit on significant files, injects file-tracking context |
| `handle_stop(hook_input)` | Extracts memories from `last_assistant_message` + transcript JSONL |
| `_extract_memories_from_message(msg, project)` | Keyword heuristics → MEDIUM confidence memories (≤5/session) |
| `_extract_from_transcript(path, project)` | "remember/always/never" patterns → HIGH confidence memories (≤10/session) |
| `_build_memory(content, type, project, tags, confidence, source)` | Validates + constructs memory dict. Returns None if invalid or credential-containing. |
| `_contains_credentials(content)` | Checks 5 regex patterns. Never stores API keys, tokens, secrets. |
| `_load_store(path)` / `_save_store(store, path)` | JSON persistence. Save is atomic (tmp + rename). |
| `_project_slug(cwd)` | `/Users/matt/Projects/ClaudeCodeAdvancements` → `claudecodeadvancements` |
| `_make_id()` | `mem_YYYYMMDD_HHMMSS_[8hex]` — collision-resistant |
| `_infer_tags(content)` | Keyword → tag mapping. Returns `["general"]` if no match. |

**Memory storage:** `~/.claude-memory/[project-slug].json`
**Memory types:** `decision` · `pattern` · `error` · `preference` · `glossary`
**Confidence:** `HIGH` (explicit) · `MEDIUM` (inferred) · `LOW` (speculative)
**Credential patterns blocked:** `sk-[...]` · `Bearer [...]` · `api_key=...` · `SUPABASE_KEY=` · `AKIA...`

---

### spec-system/hooks/validate.py (SPEC-5)
PreToolUse hook. Warns or blocks code writes when no approved spec exists.

| Function | Purpose |
|----------|---------|
| `_should_check(tool_name, file_path)` | True for Write/Edit on code files (`.py`, `.ts`, etc.) only |
| `_find_spec_file(start_dir, filename)` | Walks up directory tree looking for `requirements.md` etc. |
| `_is_approved(spec_path)` | Returns True if file contains `Status: APPROVED` |
| `_spec_status(cwd)` | Returns dict: has/approved for requirements, design, tasks |
| `_build_warning(spec_status, file_path, mode)` | Human-readable warning. Empty string = no warning needed. |
| `main()` | Entry point. Reads stdin JSON, writes decision JSON to stdout. |

**Modes:** `warn` (default, injects `additionalContext`) · `block` (set `SPEC_GUARD_MODE=block`, uses `permissionDecision: "deny"`)
**Always allowed:** spec files, test files, markdown, JSON
**Hook format:** `hookSpecificOutput.permissionDecision` — NOT top-level `decision` (PreToolUse is unique)

---

### spec-system/commands/ (SPEC-1 through SPEC-4)
Slash command Markdown files. Not Python — Claude reads and follows these as behavior instructions.

| File | Invocation | Output |
|------|-----------|--------|
| `requirements.md` | `/spec:requirements` | 15-question interview → `requirements.md` (DRAFT) |
| `design.md` | `/spec:design` | Reads approved requirements → `design.md` (DRAFT) |
| `tasks.md` | `/spec:tasks` | Reads approved design → `tasks.md` (≤20 tasks, DRAFT) |
| `implement.md` | `/spec:implement` | One task at a time, test → commit → stop, repeat |

**Approval flow:** User says "approved" → Status: DRAFT → Status: APPROVED → next command unlocks.
**Anti-pattern:** Never skip to implement without approved requirements + design + tasks.

---

## Memory Schema (MEM-1 — APPROVED)

```json
{
  "id": "mem_20260220_143022_a1b2c3d4",
  "type": "decision",
  "content": "Use stdlib-first. External packages require justification.",
  "project": "claudecodeadvancements",
  "tags": ["architecture", "dependencies"],
  "created_at": "2026-02-20T14:30:22Z",
  "last_used": "2026-02-20T14:30:22Z",
  "confidence": "HIGH",
  "source": "explicit"
}
```

**Storage file:** `~/.claude-memory/claudecodeadvancements.json`
**Schema version:** 1.0 — do not modify without updating capture_hook.py

---

## Hook Architecture (confirmed from Claude Code docs)

| Hook Event | Payload includes | Can deny? | Used by |
|-----------|-----------------|-----------|---------|
| `PreToolUse` | `tool_name`, `tool_input`, `cwd`, `session_id`, `transcript_path` | YES — `hookSpecificOutput.permissionDecision` | spec validate, agent-guard (planned) |
| `PostToolUse` | `tool_name`, `tool_input`, `tool_response`, `cwd`, `session_id` | NO decision control | memory capture (file tracking) |
| `Stop` | `last_assistant_message`, `cwd`, `session_id`, `transcript_path`, `stop_hook_active` | NO | memory capture (extraction) |

**Critical:** Token counts NOT in any hook payload. Context % NOT in any hook payload.
**Transcript path:** Available in both PostToolUse and Stop — parse JSONL for token estimation.
**Async hooks:** Cannot return decisions. Fire-and-forget only.

---

## Test Summary

| Module | File | Tests | Status |
|--------|------|-------|--------|
| memory-system | `tests/test_memory.py` | 37 | All passing |
| spec-system | `tests/test_spec.py` | 26 | All passing |
| **Total** | | **63** | **63/63** |

**Run before every session:** `python3 memory-system/tests/test_memory.py && python3 spec-system/tests/test_spec.py`

---

## Frontier Status & Next Actions

| # | Frontier | Code Status | Tests | Immediate Next |
|---|----------|-------------|-------|----------------|
| 1 | memory-system | MEM-1 ✅ MEM-2 ✅ MEM-3 [ ] MEM-4 [ ] MEM-5 [ ] | 37/37 | MEM-3: retrieval MCP server |
| 2 | spec-system | SPEC-1–5 ✅ | 26/26 | Register in `.claude/commands/` |
| 3 | context-monitor | Research ✅ Code [ ] | — | CTX-1: transcript-based meter hook |
| 4 | agent-guard | Research ✅ Code [ ] | — | AG-1: ownership manifest command |
| 5 | usage-dashboard | Research ✅ Code [ ] | — | USAGE-1: transcript-based token counter |

---

## Key Architecture Decisions (do not reverse)

| Decision | Rationale |
|----------|-----------|
| Local-first storage (`~/.claude-memory/`) | User owns data. No external dependency. Privacy by default. |
| Stop hook for memory extraction | Has `last_assistant_message` — better signal than PostToolUse alone |
| Transcript JSONL for explicit memories | `transcript_path` in Stop payload; explicit user instructions → HIGH confidence |
| `hookSpecificOutput.permissionDecision` for PreToolUse deny | Top-level `decision: "block"` silently fails on PreToolUse — confirmed from docs |
| Token counts via transcript, not hook payload | Hook payload does NOT expose token usage — confirmed from docs |
| Spec system as slash commands (not hooks) | Zero infrastructure, user-invoked at the right moment |
| SPEC_GUARD_MODE env var for block/warn | Default warn-only — never surprises or blocks existing workflow |
| 8-char UUID suffix for memory IDs | 3-char caused test collision at 100 rapid-fire creates |

---

## Session Resume Checklist

1. `python3 memory-system/tests/test_memory.py` — confirm 37/37
2. `python3 spec-system/tests/test_spec.py` — confirm 26/26
3. Read `SESSION_STATE.md` — exact current state and next actions
4. Read module `CLAUDE.md` for the frontier being worked on
5. State what you're building before touching any file

---

## Session History

| Session | Date | Deliverable |
|---------|------|-------------|
| 1 | 2026-02-19 | Research complete, all 5 frontier CLAUDE.md + EVIDENCE.md files, ROADMAP.md, master CLAUDE.md |
| 2 | 2026-02-20 | Hooks feasibility research, MEM-1 schema, MEM-2 capture hook (37 tests), SPEC-1–5 complete (26 tests) |
