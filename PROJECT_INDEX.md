# Project Index: ClaudeCodeAdvancements
# Generated: 2026-02-19 (Session 1) | Last updated: 2026-03-16 (Session 21)
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
| Reddit review log (append-only) | `FINDINGS_LOG.md` |
| Session changelog (append-only) | `CHANGELOG.md` |
| Severity-tracked learnings | `LEARNINGS.md` |
| Master-level aspirational tasks | `MASTER_TASKS.md` |
| Kalshi bot daily operations | `KALSHI_CHEATSHEET.md` |
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
│   │   ├── validate.py              # PreToolUse spec guard (SPEC-5) ✅
│   │   └── skill_activator.py       # UserPromptSubmit skill auto-activation (SPEC-6) ✅
│   ├── skill_rules.json             # Configurable skill activation rules
│   ├── tests/
│   │   ├── test_spec.py             # 26 tests — all passing
│   │   └── test_skill_activator.py  # 64 tests — all passing
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
├── self-learning/                   # Cross-session self-learning system
│   ├── journal.py                   # Structured event journal (JSONL), CLI interface
│   ├── reflect.py                   # Pattern detection, strategy recommendations
│   ├── strategy.json                # Tunable parameters (nuclear scan, session, review)
│   ├── journal.jsonl                # Append-only event log (auto-generated)
│   ├── research/
│   │   └── TRACE_ANALYSIS_RESEARCH.md  # MT-7: Transcript JSONL schema + 6 pattern detector definitions
│   └── tests/
│       └── test_self_learning.py    # 75 tests — all passing
│
├── scripts/                         # Utility scripts (launcher, automation)
│   └── kalshi-launch.sh             # Terminal.app dual-window Kalshi launcher
│
└── usage-dashboard/                 # Frontier 5: Token + cost transparency
    ├── CLAUDE.md                    # Module rules
    ├── usage_counter.py             # USAGE-1: CLI token/cost counter (reads transcript JSONL)
    ├── otel_receiver.py             # USAGE-2: Lightweight OTLP HTTP/JSON receiver for CC native metrics
    ├── otel_setup.sh                # OTel env var setup script for ~/.zshrc
    ├── arewedone.py                 # Structural completeness checker (all 7 modules)
    ├── hooks/
    │   └── cost_alert.py            # USAGE-3: PreToolUse cost threshold warn/block hook
    ├── tests/
    │   ├── test_usage_counter.py    # 44 tests
    │   ├── test_otel_receiver.py    # 63 tests
    │   ├── test_cost_alert.py       # 39 tests
    │   └── test_arewedone.py        # 50 tests
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
| `python3 spec-system/tests/test_skill_activator.py` | skill activator tests (64 tests) |
| `python3 research/tests/test_reddit_scout.py` | reddit scout tests (29 tests) |
| `python3 agent-guard/tests/test_mobile_approver.py` | iPhone hook tests (36 tests) |
| `python3 agent-guard/tests/test_ownership.py` | ownership manifest tests (27 tests) |
| `python3 agent-guard/tests/test_credential_guard.py` | credential guard tests (40 tests) |
| `python3 context-monitor/tests/test_meter.py` | context meter tests (52 tests) |
| `python3 context-monitor/tests/test_alert.py` | alert hook tests (24 tests) |
| `python3 context-monitor/tests/test_auto_handoff.py` | auto-handoff tests (27 tests) |
| `python3 context-monitor/tests/test_compact_anchor.py` | compact anchor tests (22 tests) |
| `python3 reddit-intelligence/tests/test_reddit_reader.py` | reddit reader tests (43 tests) |
| `python3 reddit-intelligence/tests/test_nuclear_fetcher.py` | nuclear fetcher tests (44 tests) |
| `python3 self-learning/tests/test_self_learning.py` | self-learning tests (75 tests) |
| `python3 usage-dashboard/tests/test_usage_counter.py` | usage counter tests (44 tests) |
| `python3 usage-dashboard/tests/test_otel_receiver.py` | OTel receiver tests (63 tests) |
| `python3 usage-dashboard/tests/test_cost_alert.py` | cost alert tests (39 tests) |
| `python3 usage-dashboard/tests/test_arewedone.py` | arewedone tests (51 tests) |
| `python3 memory-system/cli.py stats` | Show memory stats |
| `python3 agent-guard/ownership.py` | Show file ownership manifest |
| `python3 usage-dashboard/usage_counter.py sessions` | Show per-session token/cost breakdown |
| `python3 usage-dashboard/arewedone.py` | Structural completeness check (all 7 modules) |

**Total:** 800/800 tests. **Session start:** Run all 20 suites. If anything fails, fix before touching other files.

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
| `design-review.md` | `/spec:design-review` | 4-persona review panel → APPROVE/REVISE/REDESIGN verdict |

**Approval flow:** User says "approved" → Status: DRAFT → Status: APPROVED → next command unlocks.
**Anti-pattern:** Never skip to implement without approved requirements + design + tasks.
**Design vocabulary (Section 1b):** Optional for UI features — reference UIs, aesthetic terms, layout patterns.

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
| spec-system (spec) | `tests/test_spec.py` | 26 | All passing |
| spec-system (skill_activator) | `tests/test_skill_activator.py` | 64 | All passing |
| research | `tests/test_reddit_scout.py` | 29 | All passing |
| agent-guard (mobile_approver) | `tests/test_mobile_approver.py` | 36 | All passing |
| agent-guard (ownership) | `tests/test_ownership.py` | 27 | All passing |
| agent-guard (credential_guard) | `tests/test_credential_guard.py` | 40 | All passing |
| context-monitor (meter) | `tests/test_meter.py` | 52 | All passing |
| context-monitor (alert) | `tests/test_alert.py` | 24 | All passing |
| context-monitor (auto_handoff) | `tests/test_auto_handoff.py` | 27 | All passing |
| context-monitor (compact_anchor) | `tests/test_compact_anchor.py` | 22 | All passing |
| reddit-intelligence (reader) | `tests/test_reddit_reader.py` | 43 | All passing |
| reddit-intelligence (nuclear) | `tests/test_nuclear_fetcher.py` | 44 | All passing |
| self-learning | `tests/test_self_learning.py` | 75 | All passing |
| usage-dashboard (counter) | `tests/test_usage_counter.py` | 44 | All passing |
| usage-dashboard (otel_receiver) | `tests/test_otel_receiver.py` | 63 | All passing |
| usage-dashboard (cost_alert) | `tests/test_cost_alert.py` | 39 | All passing |
| usage-dashboard (arewedone) | `tests/test_arewedone.py` | 51 | All passing |
| **Total** | | **800** | **800/800** |

---

## Frontier Status & Next Actions

| # | Frontier | Code Status | Tests | Immediate Next |
|---|----------|-------------|-------|----------------|
| 1 | memory-system | MEM-1–5 ✅ COMPLETE | 94/94 | — |
| 2 | spec-system | SPEC-1–6 ✅ COMPLETE | 90/90 | — |
| 3 | context-monitor | CTX-1–5 ✅ COMPLETE | 109/109 | — |
| 4 | agent-guard | AG-1 ✅ AG-2 ✅ AG-3 ✅ | 103/103 | Frontier nearly complete |
| 5 | usage-dashboard | USAGE-1 ✅ USAGE-2 ✅ USAGE-3 ✅ /arewedone ✅ | 196/196 | Streamlit UI (optional) |

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

## Session Commands (Global — work from any folder)

| Command | Purpose |
|---------|---------|
| `/cca-init` | Session startup — reads context, runs tests, shows briefing |
| `/cca-review <url>` | Review any URL against frontiers — BUILD/SKIP verdict, logs to FINDINGS_LOG.md |
| `/cca-auto` | Autonomous work — picks next task, executes via gsd:quick |
| `/cca-wrap` | Session end — self-grade, update docs, learnings capture, resume prompt |
| `/cca-scout` | Scan r/ClaudeCode + r/ClaudeAI for high-signal posts, dedupe vs findings log |
| `/cca-nuclear` | Autonomous deep-dive — batch review top 100-150 posts, resumes across sessions |
| `/cca-nuclear-wrap` | Nuclear session wrap-up with self-learning journal + reflection |
| `/browse-url <url>` | Read any URL (no analysis, just content) |

---

## Session Resume Checklist

1. Run `/cca-init`
2. Run all 20 test suites — confirm 742/742
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
| 6 | 2026-03-08 | AG-1 mobile approver (36 tests), browse-url skill, Reddit scout |
| 7-9 | 2026-03-08 | CTX-1–5, AG-2/3, MEM-5, reddit-intel plugin, session commands — 404 tests |
| 10-13 | 2026-03-15 | cca-wrap, cca-scout, URL auto-review, tmux workspace, tool installs — 483 tests |
| 14-15 | 2026-03-15 | Nuclear scan COMPLETE (138 posts), self-learning system, 517 tests |
| 16 | 2026-03-15 | USAGE-1 counter, /arewedone, cca-wrap self-learning, 3 tool installs — 568 tests |
| 17 | 2026-03-16 | USAGE-2 OTel receiver, SPEC-6 skill activator, USAGE-3 cost alert — 734 tests |
| 18 | 2026-03-16 | USAGE-3 hook wiring, Kalshi tmux automation, KALSHI_CHEATSHEET — 734 tests |
| 19 | 2026-03-16 | MASTER_TASKS.md (MT-0–MT-5), nuclear subreddit flexibility, Kalshi Terminal launcher, CCA vs YoYo analysis — 742 tests |
