# ClaudeCodeAdvancements — Reference Guide
# Detailed API docs, schemas, and architecture decisions.
# Read PROJECT_INDEX.md first — this file is for deep-dives into specific modules.

---

## Entry Points (Tests + CLI)

Run all tests: `for f in $(find . -name "test_*.py" -type f | sort); do echo "=== $f ===" && python3 "$f" 2>&1 | tail -1; done`

### CLI Tools

| Command | What it does |
|---------|-------------|
| `python3 memory-system/cli.py stats` | Show memory stats |
| `python3 agent-guard/ownership.py` | Show file ownership manifest |
| `python3 usage-dashboard/usage_counter.py sessions` | Per-session token/cost breakdown |
| `python3 usage-dashboard/arewedone.py` | Structural completeness check (all 7 modules) |
| `python3 reddit-intelligence/autonomous_scanner.py rank` | Prioritized sub scan queue |
| `python3 reddit-intelligence/autonomous_scanner.py status` | Autonomous scan safety status |
| `python3 reddit-intelligence/autonomous_scanner.py pick` | Pick next target sub for scanning |
| `python3 reddit-intelligence/autonomous_scanner.py stale` | Subs due for rescan |
| `python3 reddit-intelligence/autonomous_scanner.py rescan` | MT-14: Delta-rescan stale sub |
| `python3 reddit-intelligence/github_scanner.py queries` | GitHub search queries for CCA frontiers |
| `python3 reddit-intelligence/repo_tester.py results` | Repo test result log |
| `python3 reddit-intelligence/repo_tester.py local <path>` | Test a local directory |
| `python3 self-learning/trace_analyzer.py <session.jsonl>` | Analyze a session transcript |
| `python3 self-learning/improver.py stats` | Show improvement proposal stats |
| `python3 self-learning/validate_strategies.py` | Validate Skillbook strategies against evidence |
| `python3 self-learning/validate_strategies.py --brief` | One-line validation summary |

---

## Core Module APIs

### memory-system/hooks/capture_hook.py (MEM-2)
Handles `PostToolUse` and `Stop` hook events. Reads JSON from stdin, writes JSON to stdout.

| Function | Purpose |
|----------|---------|
| `handle_post_tool_use(hook_input)` | Detects Write/Edit on significant files, injects file-tracking context |
| `handle_stop(hook_input)` | Extracts memories from `last_assistant_message` + transcript JSONL |
| `_extract_memories_from_message(msg, project)` | Keyword heuristics -> MEDIUM confidence memories (<=5/session) |
| `_extract_from_transcript(path, project)` | "remember/always/never" patterns -> HIGH confidence memories (<=10/session) |
| `_build_memory(content, type, project, tags, confidence, source)` | Validates + constructs memory dict. Returns None if invalid or credential-containing. |
| `_contains_credentials(content)` | Checks 5 regex patterns. Never stores API keys, tokens, secrets. |
| `_load_store(path)` / `_save_store(store, path)` | JSON persistence. Save is atomic (tmp + rename). |
| `_project_slug(cwd)` | `/Users/matt/Projects/ClaudeCodeAdvancements` -> `claudecodeadvancements` |
| `_make_id()` | `mem_YYYYMMDD_HHMMSS_[8hex]` -- collision-resistant |
| `_infer_tags(content)` | Keyword -> tag mapping. Returns `["general"]` if no match. |

**Memory storage:** `~/.claude-memory/[project-slug].json`
**Memory types:** `decision` / `pattern` / `error` / `preference` / `glossary`
**Confidence:** `HIGH` (explicit) / `MEDIUM` (inferred) / `LOW` (speculative)
**Credential patterns blocked:** `sk-[...]` / `Bearer [...]` / `api_key=...` / `SUPABASE_KEY=` / `AKIA...`

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

**Modes:** `warn` (default, injects `additionalContext`) / `block` (set `SPEC_GUARD_MODE=block`, uses `permissionDecision: "deny"`)
**Always allowed:** spec files, test files, markdown, JSON
**Hook format:** `hookSpecificOutput.permissionDecision` -- NOT top-level `decision` (PreToolUse is unique)

---

### spec-system/commands/ (SPEC-1 through SPEC-4)
Slash command Markdown files. Not Python -- Claude reads and follows these as behavior instructions.

| File | Invocation | Output |
|------|-----------|--------|
| `requirements.md` | `/spec:requirements` | 15-question interview -> `requirements.md` (DRAFT) |
| `design.md` | `/spec:design` | Reads approved requirements -> `design.md` (DRAFT) |
| `tasks.md` | `/spec:tasks` | Reads approved design -> `tasks.md` (<=20 tasks, DRAFT) |
| `implement.md` | `/spec:implement` | One task at a time, test -> commit -> stop, repeat |
| `design-review.md` | `/spec:design-review` | 4-persona review panel -> APPROVE/REVISE/REDESIGN verdict |

**Approval flow:** User says "approved" -> Status: DRAFT -> Status: APPROVED -> next command unlocks.
**Anti-pattern:** Never skip to implement without approved requirements + design + tasks.

---

## Memory Schema (MEM-1 -- APPROVED)

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
**Schema version:** 1.0 -- do not modify without updating capture_hook.py

---

## Hook Architecture (confirmed from Claude Code docs)

| Hook Event | Payload includes | Can deny? | Used by |
|-----------|-----------------|-----------|---------|
| `PreToolUse` | `tool_name`, `tool_input`, `cwd`, `session_id`, `transcript_path` | YES -- `hookSpecificOutput.permissionDecision` | spec validate, agent-guard, path_validator |
| `PostToolUse` | `tool_name`, `tool_input`, `tool_response`, `cwd`, `session_id` | NO decision control | memory capture (file tracking), meter, compact_anchor |
| `Stop` | `last_assistant_message`, `cwd`, `session_id`, `transcript_path`, `stop_hook_active` | NO | memory capture (extraction), auto_handoff |

**Critical:** Token counts NOT in any hook payload. Context % NOT in any hook payload.
**Transcript path:** Available in both PostToolUse and Stop -- parse JSONL for token estimation.
**Async hooks:** Cannot return decisions. Fire-and-forget only.

---

## Key Architecture Decisions (do not reverse)

| Decision | Rationale |
|----------|-----------|
| Local-first storage (`~/.claude-memory/`) | User owns data. No external dependency. Privacy by default. |
| Stop hook for memory extraction | Has `last_assistant_message` -- better signal than PostToolUse alone |
| Transcript JSONL for explicit memories | `transcript_path` in Stop payload; explicit user instructions -> HIGH confidence |
| `hookSpecificOutput.permissionDecision` for PreToolUse deny | Top-level `decision: "block"` silently fails on PreToolUse -- confirmed from docs |
| Token counts via transcript, not hook payload | Hook payload does NOT expose token usage -- confirmed from docs |
| Spec system as slash commands (not hooks) | Zero infrastructure, user-invoked at the right moment |
| SPEC_GUARD_MODE env var for block/warn | Default warn-only -- never surprises or blocks existing workflow |
| 8-char UUID suffix for memory IDs | 3-char caused test collision at 100 rapid-fire creates |

---

## Test Summary (detailed)

| Module | File | Tests |
|--------|------|-------|
| memory-system (capture) | `tests/test_memory.py` | 37 |
| memory-system (mcp_server) | `tests/test_mcp_server.py` | 29 |
| memory-system (cli) | `tests/test_cli.py` | 28 |
| spec-system (spec) | `tests/test_spec.py` | 26 |
| spec-system (skill_activator) | `tests/test_skill_activator.py` | 64 |
| research | `tests/test_reddit_scout.py` | 29 |
| agent-guard (mobile_approver) | `tests/test_mobile_approver.py` | 36 |
| agent-guard (ownership) | `tests/test_ownership.py` | 27 |
| agent-guard (credential_guard) | `tests/test_credential_guard.py` | 40 |
| agent-guard (content_scanner) | `tests/test_content_scanner.py` | 50 |
| agent-guard (network_guard) | `tests/test_network_guard.py` | 53 |
| agent-guard (session_guard) | `tests/test_session_guard.py` | 28 |
| agent-guard (path_validator) | `tests/test_path_validator.py` | 30 |
| context-monitor (meter) | `tests/test_meter.py` | 52 |
| context-monitor (alert) | `tests/test_alert.py` | 24 |
| context-monitor (auto_handoff) | `tests/test_auto_handoff.py` | 27 |
| context-monitor (compact_anchor) | `tests/test_compact_anchor.py` | 22 |
| context-monitor (statusline) | `tests/test_statusline.py` | 24 |
| context-monitor (auto_wrap) | `tests/test_auto_wrap.py` | 19 |
| reddit-intelligence (reader) | `tests/test_reddit_reader.py` | 43 |
| reddit-intelligence (nuclear) | `tests/test_nuclear_fetcher.py` | 44 |
| reddit-intelligence (profiles) | `tests/test_profiles.py` | 49 |
| reddit-intelligence (autonomous) | `tests/test_autonomous_scanner.py` | 73 |
| reddit-intelligence (github) | `tests/test_github_scanner.py` | 45 |
| reddit-intelligence (repo_tester) | `tests/test_repo_tester.py` | 51 |
| self-learning | `tests/test_self_learning.py` | 75 |
| self-learning (trace_analyzer) | `tests/test_trace_analyzer.py` | 50 |
| self-learning (improver) | `tests/test_improver.py` | 44 |
| self-learning (skillbook_inject) | `tests/test_skillbook_inject.py` | 26 |
| self-learning (validate_strategies) | `tests/test_validate_strategies.py` | 30 |
| self-learning (sentinel) | `tests/test_sentinel.py` | 26 |
| self-learning (batch_report) | `tests/test_batch_report.py` | 13 |
| self-learning (paper_scanner) | `tests/test_paper_scanner.py` | 50 |
| usage-dashboard (counter) | `tests/test_usage_counter.py` | 44 |
| usage-dashboard (otel_receiver) | `tests/test_otel_receiver.py` | 63 |
| usage-dashboard (cost_alert) | `tests/test_cost_alert.py` | 39 |
| usage-dashboard (arewedone) | `tests/test_arewedone.py` | 51 |
| **Total** | **37 suites** | **1521** |

---

## Session History

See `CHANGELOG.md` for full session-by-session history.
