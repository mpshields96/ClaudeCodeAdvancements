# ClaudeCodeAdvancements — Changelog
# Append-only. Never truncate.

---

## Session 9 — 2026-03-15

**What changed:**
- SESSION_STATE.md updated to reflect 404/404 tests and session 9 wrap
- CHANGELOG.md created (this file)
- LEARNINGS.md created

**Why:**
- Wrap-only session. No new code. Confirmed all 13 suites pass (404 tests total).
- Identified critical gap: sessions 7+8 work (AG-2, AG-3, CTX-1–5, MEM-5, reddit-intel) was
  never committed despite being complete and tested.

**Tests:** 404/404 passing

**Lessons:**
- Sessions must commit before closing. Having 83+ untracked files across multiple sessions
  is a recovery liability. Commit discipline: ship each task, commit before the next.

---

## Session 8 — 2026-03-08

**What changed:**
- `context-monitor/hooks/auto_handoff.py` — CTX-4: Stop hook blocks exit at critical context
- `context-monitor/hooks/compact_anchor.py` — CTX-5: writes anchor file every N tool calls
- `context-monitor/tests/test_auto_handoff.py` — 27 tests
- `context-monitor/tests/test_compact_anchor.py` — 22 tests
- `memory-system/cli.py` — MEM-5: CLI viewer (list/search/delete/purge/stats)
- `memory-system/tests/test_cli.py` — 28 tests
- `agent-guard/ownership.py` — AG-2: ownership manifest CLI
- `agent-guard/tests/test_ownership.py` — 27 tests
- `.claude/commands/ag-ownership.md` — slash command
- CTX-1 bug fix: transcript format corrected (entry["message"]["usage"] for assistant entries)
- `context-monitor/tests/test_meter.py` — grew from 33 to 36 tests

**Why:**
- Context Monitor frontier completion (CTX-4/5 were the last two hooks)
- Memory system CLI gives users introspection into stored memories
- Ownership manifest helps multi-agent sessions detect file contention

**Tests:** 321/321 passing (sessions 7+8 combined, before credential_guard + reddit_reader)

**Lessons:**
- Stop hook block format: `{"decision": "block", "reason": "..."}` — different from PreToolUse
  which uses `hookSpecificOutput.permissionDecision`
- argparse subparsers don't inherit parent options — add `--project` to each subcommand

---

## Session 7 — 2026-03-01 (approx)

**What changed:**
- `reddit-intelligence/` — full plugin: reddit_reader.py, 43 tests, ri-scan/ri-read/ri-loop commands
- `reddit-intelligence/tests/test_reddit_reader.py` — 43 tests
- `.claude/commands/reddit-intel/` — symlinks to plugin commands
- `agent-guard/hooks/credential_guard.py` — AG-3: credential-extraction guard
- `agent-guard/tests/test_credential_guard.py` — 40 tests
- `context-monitor/hooks/meter.py` — CTX-1: token counter PostToolUse hook
- `context-monitor/hooks/alert.py` — CTX-3: PreToolUse alert for expensive tools
- `context-monitor/statusline.py` — CTX-2: ANSI statusline
- `context-monitor/tests/test_meter.py` — 33 tests
- `context-monitor/tests/test_alert.py` — 24 tests

**Why:**
- Context Monitor and Agent Guard frontiers largely completed in this session block
- reddit-intel provides ongoing community signal research for frontier validation

**Tests:** Suites passing; exact count captured in session 8

**Lessons:**
- Transcript path: `project_hash = os.getcwd().replace('/', '-')` → `~/.claude/projects/<hash>/<session>.jsonl`
- Real Claude Code transcripts: usage at `entry["message"]["usage"]`, not `entry["usage"]`

---

## Sessions 1–6 — 2026-02-19 to 2026-03-01

**What changed (cumulative):**
- Frontier 1 (memory-system): MEM-1 schema, MEM-2 capture hook, MEM-3 MCP server, MEM-4 /handoff, MEM-5 CLI
- Frontier 2 (spec-system): SPEC-1–6 slash commands + guard hook
- Frontier 4 (agent-guard): AG-1 mobile approver (iPhone push via ntfy.sh)
- Foundation: CLAUDE.md, PROJECT_INDEX.md, SESSION_STATE.md, ROADMAP.md, MASTER_ROADMAP.md
- Research: reddit_scout.py, EVIDENCE.md, browse-url global skill

**Why:**
- Initial project build-out — all five frontiers scoped and first three completed

**Tests:** 157/157 passing (as of session 6)

**Lessons:**
- PreToolUse deny: `hookSpecificOutput.permissionDecision: "deny"` — top-level `decision: "block"` silently fails
- Anthropic key regex must include hyphens: `sk-[A-Za-z0-9\-]{20,}` not `sk-[A-Za-z0-9]{20,}`
- Memory ID suffix: 8 hex chars minimum (3-char caused collisions at 100 rapid-fire creates)

---
