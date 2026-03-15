# Project Index: ClaudeCodeAdvancements
# Generated: 2026-02-19 (Session 1) | Last updated: 2026-03-15 (Session 9)
# Read this FIRST each session — ~94% token reduction vs reading all source files

---

## Quick Orientation

| What | Where |
|------|-------|
| Project rules + scope boundary | `CLAUDE.md` |
| Feature backlog + priorities | `ROADMAP.md` |
| Master roadmap + session prompts | `MASTER_ROADMAP.md` |
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
├── MASTER_ROADMAP.md                # Objective session-by-session plan with prompts
├── PROJECT_INDEX.md                 # This file
├── SESSION_STATE.md                 # Current state, test counts, next actions
│
├── memory-system/                   # Frontier 1: Persistent cross-session memory
│   ├── CLAUDE.md                    # Module rules
│   ├── schema.md                    # APPROVED data schema (MEM-1) ✅
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
├── context-monitor/                 # Frontier 3: Context health + compaction guard — COMPLETE ✅
│   ├── CLAUDE.md                    # Module rules
│   ├── statusline.py                # CTX-2: ANSI statusline (reads native context_window.used_percentage)
│   ├── hooks/
│   │   ├── meter.py                 # CTX-1: PostToolUse token counter → ~/.claude-context-health.json
│   │   ├── alert.py                 # CTX-3: PreToolUse warn/block before expensive tools in red/critical
│   │   ├── auto_handoff.py          # CTX-4: Stop hook — blocks exit at critical, prompts /handoff
│   │   └── compact_anchor.py        # CTX-5: PostToolUse — writes .claude-compact-anchor.md every N turns
│   ├── tests/
│   │   ├── test_meter.py            # 36 tests
│   │   ├── test_alert.py            # 24 tests
│   │   ├── test_auto_handoff.py     # 27 tests
│   │   └── test_compact_anchor.py   # 22 tests
│   └── research/
│       └── EVIDENCE.md
│
├── agent-guard/                     # Frontier 4: Multi-agent conflict prevention
│   ├── CLAUDE.md                    # Module rules
│   ├── ownership.py                 # AG-2: CLI ownership manifest (git history → conflict detection)
│   ├── hooks/
│   │   ├── mobile_approver.py       # AG-1: PreToolUse iPhone push approval via ntfy.sh
│   │   └── credential_guard.py      # AG-3: PreToolUse credential-extraction guard
│   ├── tests/
│   │   ├── test_mobile_approver.py  # 36 tests
│   │   ├── test_ownership.py        # 27 tests
│   │   └── test_credential_guard.py # 40 tests
│   └── research/
│       └── EVIDENCE.md
│
├── reddit-intelligence/             # Community signal research plugin
│   ├── reddit_reader.py             # Fetches Reddit posts + all comments (no API key needed)
│   ├── reddit_scout.py              # Daily community signal sweep
│   ├── commands/
│   │   ├── ri-scan.md               # /reddit-intel:ri-scan — weekly multi-subreddit scan
│   │   ├── ri-read.md               # /reddit-intel:ri-read [url] — read specific post
│   │   └── ri-loop.md               # /reddit-intel:ri-loop — schedule recurring scans
│   ├── tests/
│   │   └── test_reddit_reader.py    # 43 tests
│   └── findings/                    # Output directory for scan results
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
| `python3 memory-system/tests/test_memory.py` | memory-system smoke tests (37 tests) |
| `python3 memory-system/tests/test_mcp_server.py` | MCP server tests (29 tests) |
| `python3 memory-system/tests/test_cli.py` | CLI viewer tests (28 tests) |
| `python3 spec-system/tests/test_spec.py` | spec-system tests (26 tests) |
| `python3 research/tests/test_reddit_scout.py` | reddit scout tests (29 tests) |
| `python3 agent-guard/tests/test_mobile_approver.py` | iPhone hook tests (36 tests) |
| `python3 agent-guard/tests/test_ownership.py` | ownership manifest tests (27 tests) |
| `python3 agent-guard/tests/test_credential_guard.py` | credential guard tests (40 tests) |
| `python3 context-monitor/tests/test_meter.py` | context meter tests (36 tests) |
| `python3 context-monitor/tests/test_alert.py` | alert hook tests (24 tests) |
| `python3 context-monitor/tests/test_auto_handoff.py` | auto-handoff tests (27 tests) |
| `python3 context-monitor/tests/test_compact_anchor.py` | compact anchor tests (22 tests) |
| `python3 reddit-intelligence/tests/test_reddit_reader.py` | reddit reader tests (43 tests) |
| `python3 memory-system/cli.py stats` | Show memory stats |
| `python3 agent-guard/ownership.py` | Show file ownership manifest |

**Total:** 404/404 tests. **Session start:** Run all 13 suites. If anything fails, fix before touching other files.

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
| memory-system (capture) | `tests/test_memory.py` | 37 | All passing |
| memory-system (mcp_server) | `tests/test_mcp_server.py` | 29 | All passing |
| memory-system (cli) | `tests/test_cli.py` | 28 | All passing |
| spec-system | `tests/test_spec.py` | 26 | All passing |
| research | `tests/test_reddit_scout.py` | 29 | All passing |
| agent-guard (mobile_approver) | `tests/test_mobile_approver.py` | 36 | All passing |
| agent-guard (ownership) | `tests/test_ownership.py` | 27 | All passing |
| agent-guard (credential_guard) | `tests/test_credential_guard.py` | 40 | All passing |
| context-monitor (meter) | `tests/test_meter.py` | 36 | All passing |
| context-monitor (alert) | `tests/test_alert.py` | 24 | All passing |
| context-monitor (auto_handoff) | `tests/test_auto_handoff.py` | 27 | All passing |
| context-monitor (compact_anchor) | `tests/test_compact_anchor.py` | 22 | All passing |
| reddit-intelligence | `tests/test_reddit_reader.py` | 43 | All passing |
| **Total** | | **404** | **404/404** |

---

## Frontier Status & Next Actions

| # | Frontier | Code Status | Tests | Immediate Next |
|---|----------|-------------|-------|----------------|
| 1 | memory-system | MEM-1–5 ✅ COMPLETE | 94/94 | — |
| 2 | spec-system | SPEC-1–6 ✅ COMPLETE | 26/26 | — |
| 3 | context-monitor | CTX-1–5 ✅ COMPLETE | 109/109 | — |
| 4 | agent-guard | AG-1 ✅ AG-2 ✅ AG-3 ✅ | 103/103 | USAGE-1 next |
| 5 | usage-dashboard | Research ✅ Code [ ] | — | USAGE-1: token counter (macOS menubar or Streamlit) |

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

1. **CRITICAL FIRST:** Commit all untracked files from sessions 7+8 (see SESSION_STATE.md)
2. Run all 13 test suites — confirm 404/404
3. Read `SESSION_STATE.md` — exact current state and next actions
4. Read module `CLAUDE.md` for the frontier being worked on
5. State what you're building before touching any file

---

## Session History

| Session | Date | Deliverable |
|---------|------|-------------|
| 1 | 2026-02-19 | Research complete, all 5 frontier CLAUDE.md + EVIDENCE.md files, ROADMAP.md, master CLAUDE.md |
| 2 | 2026-02-20 | Hooks feasibility research, MEM-1 schema, MEM-2 capture hook (37 tests), SPEC-1–5 complete (26 tests) |
| 3 | 2026-02-20 | GitHub live, CLAUDE.md gotchas added, SESSION_STATE updated, MASTER_ROADMAP.md created |
