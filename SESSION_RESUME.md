# NEXT CHAT HANDOFF — Chat 15

## Start Here
Run /cca-init. Last session was S246 Chat 14.5 on 2026-03-31.

You are Chat 15. Phase 4 (Custom Agents) continues. Three agents validated, one to build + one to harden. Then Ebbinghaus decay integration.

---

## Context: What was done (Chat 14 + 14.5)

1. **All 3 agents VALIDATED** — cca-test-runner (haiku), cca-reviewer (sonnet), senior-reviewer (opus). All frontmatter fields confirmed working: `model` switches behavior, `maxTurns` is a hard cap (truncated mid-response at limit), `disallowedTools` behavioral confirmation. Full results in `AGENT_PIPELINE_VALIDATION.md`.
2. **Two repos cloned** (DMCA preservation) to `references/` (gitignored, NOT in CCA git):
   - `references/claw-code/` — Python rewrite of Claude Code by instructkr. 36 .py files, 30 dirs. Key files: `src/runtime.py` (routing), `src/query_engine.py` (session/budget management), `src/execution_registry.py` (uniform command/tool interface), `src/permissions.py` (deny model).
   - `references/claude-code-source-build/` — Source map extraction by andrew-kramer-inno. CC v2.1.88 rebuilt from source maps. 4756 modules. ~90 feature flag names.
3. **Cache audit: HEALTHY** — 68-99% cache read ratios across recent sessions. The db8 bug (cache_read stuck at ~15K) is NOT active on this machine. No urgent auditor build needed.
4. **Reddit review #4 (Universal CLAUDE.md): ADAPT** — Two rules stolen in 14.5F: redundant-read guard + tool-call budget awareness added to CLAUDE.md Architecture Principles.
5. **Senior-reviewer real verdict on `agent-guard/senior_review.py`:** CONDITIONAL — 5 issues found (silent `except Exception: pass` swallowing, PEP8 `l` variable, inconsistent GitContext instantiation, hardcoded LOC>1000 not a constant, dead `fp_confidence` logic). Anti-rubber-stamp confirmed: opus agent finds real issues, not a yes-machine.

**Deployed agents (all in `~/.claude/agents/`, session-discoverable):**

| Agent | Model | maxTurns | Status | Token cost (observed) |
|-------|-------|----------|--------|-----------------------|
| cca-test-runner | haiku | 10 | VALIDATED | ~61K, 7s (quick smoke) |
| cca-reviewer | sonnet | 30 | VALIDATED | ~43K, 158s (thorough review) |
| senior-reviewer | opus | 15 | VALIDATED | ~40K, 168s (5 real issues) |

---

## Chat 15 Tasks (4 tasks, ~70 min total)

### 15A. Build `cca-scout` Agent (~25 min)
**Scope:** Convert `/cca-scout` command into agent. Last of the 4 priority agents from `CUSTOM_AGENTS_DESIGN.md`.

**CRITICAL GOTCHA:** Agent discovery is cached at session start. An agent created mid-session will NOT be discoverable via `subagent_type`. You MUST:
1. Build the agent file
2. Copy to `~/.claude/agents/cca-scout.md`
3. Test it using the `Agent` tool with `model: "sonnet"` parameter override (bypasses discovery requirement)
4. Full `subagent_type` testing happens in Chat 16 (next session)

**Frontmatter (from `CUSTOM_AGENTS_DESIGN.md` lines 108-119):**
```yaml
---
name: cca-scout
description: Scan subreddits for high-signal posts relevant to CCA frontiers. Use PROACTIVELY during /cca-nuclear sessions.
tools: Read, Bash, Grep, Glob, WebFetch
disallowedTools: Edit, Write, Agent
model: sonnet
maxTurns: 40
effort: medium
color: green
---
```

**Steps:**
1. Read `.claude/commands/cca-scout.md` (101 lines, 5 steps) — the current command to condense
2. Read `reddit-intelligence/reddit_reader.py` — understand the tool the agent will call
3. Create `.claude/agents/cca-scout.md` with frontmatter above + condensed prompt body containing:
   - Subreddit targets: `r/ClaudeCode` (top 50), `r/ClaudeAI` (top 50), `r/vibecoding` (top 25)
   - Reader invocation: `python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/reddit-intelligence/reddit_reader.py "r/ClaudeCode" top 50`
   - Filtering: score >= 50 OR comments >= 30; keyword match on tool/hook/agent/memory/MCP/etc
   - Rat poison exclusions: memes, opinion posts, model debates, company news, hype
   - Dedup: read `FINDINGS_LOG.md`, skip any URL already reviewed
   - Output format: numbered list with title, subreddit, score, comment count, one-line "why"
4. Copy to `~/.claude/agents/cca-scout.md` (global deploy):
   ```bash
   cp /Users/matthewshields/Projects/ClaudeCodeAdvancements/.claude/agents/cca-scout.md ~/.claude/agents/cca-scout.md
   ```
5. Convert `.claude/commands/cca-scout.md` into thin orchestrator (~15 lines) that spawns the agent
6. Test: invoke via `Agent(model: "sonnet", prompt="Scan r/ClaudeCode for high-signal posts")` — verify it returns a ranked post list. Do NOT use `subagent_type` (won't work until next session).
7. If the agent fails or returns garbage: check that `reddit_reader.py` path is correct, that WebFetch is in allowed tools, and that maxTurns 40 is enough for 3 subreddits

**STOP CONDITION:** Agent produces ranked post list. Both project and global copies deployed. Command converted to orchestrator. All 4 `CUSTOM_AGENTS_DESIGN.md` priority agents now complete.

---

### 15B. Harden `cca-test-runner` Based on Real Usage (~15 min)
**Scope:** Real usage in Chats 13-14 revealed edge cases. Fix them.

**Known issues from `AGENT_PIPELINE_VALIDATION.md`:**
- maxTurns 10 is a hard cap. Quick smoke (10 suites) completes in 7 turns. Full suite (349 suites) was CUT OFF at turn 10 mid-response — partial results lost.
- Agent doesn't output partial results before truncation. If cut off, you get nothing useful from the last turn.

**Steps:**
1. Read `~/.claude/agents/cca-test-runner.md` and `AGENT_PIPELINE_VALIDATION.md` sections on test-runner
2. Bump maxTurns from 10 to 15 (full suite needs ~12 turns: run + parse + rerun failures + summarize)
3. Add instruction in prompt: "Output your summary FIRST, then detailed results. If you run out of turns, the summary is already captured."
4. Update BOTH copies:
   ```bash
   cp /Users/matthewshields/Projects/ClaudeCodeAdvancements/.claude/agents/cca-test-runner.md ~/.claude/agents/cca-test-runner.md
   ```
5. Verify: invoke test runner with `Agent(subagent_type="cca-test-runner", prompt="Run full test suite")` — confirm it completes without truncation

**STOP CONDITION:** Test runner handles full suite without truncation. Summary-first output pattern confirmed.

---

### 15C. Integrate Ebbinghaus Decay into Memory System (~20 min)
**Scope:** Wire the decay function into actual memory queries. Currently dead code.

**Current state:**
- `memory-system/decay.py` (151 lines) — has `compute_effective_confidence()` function. Standalone, nothing imports it.
- `memory-system/tests/test_decay.py` (6.2K) — tests exist for the decay function itself.
- `memory-system/memory_store.py:326` — `search()` method does FTS5 query, returns `_row_to_dict()` results. NO decay applied.
- Schema (`memory_store.py:85-113`) has `created_at`, `updated_at` but NO `last_accessed_at` field.

**Integration plan:**
1. Add `last_accessed_at TEXT` column to the `memories` table. This requires a schema migration:
   ```python
   # In _init_schema or a migration method:
   ALTER TABLE memories ADD COLUMN last_accessed_at TEXT NOT NULL DEFAULT '';
   ```
   Set default to empty string (backwards compatible). On first access, populate with current timestamp.

2. In `search()` (line 326): after FTS5 returns rows and before `_row_to_dict()`, call `compute_effective_confidence()` for each result. Add `effective_confidence` to the returned dict. Sort by effective_confidence (decayed) instead of raw BM25 rank, or use a composite score.

3. In `search()`: update `last_accessed_at` for every returned memory (touch on read). This refreshes the decay clock.

4. Write integration tests in `tests/test_decay.py`:
   - Memory created 30 days ago with HIGH confidence: effective confidence should be slightly reduced
   - Memory created 365 days ago with LOW confidence: should be near zero
   - Memory accessed today: `last_accessed_at` timestamp updated
   - Search results ordered by effective confidence

**Files to modify:**
- `memory-system/memory_store.py` (~15 LOC changes: migration + search integration + access timestamp)
- `memory-system/tests/test_decay.py` (~40 LOC additions: integration tests)

**STOP CONDITION:** `search()` returns results with `effective_confidence` field. `last_accessed_at` updates on access. All existing tests still pass. New integration tests pass.

Run tests after:
```bash
cd /Users/matthewshields/Projects/ClaudeCodeAdvancements && python3 -m pytest memory-system/tests/test_decay.py memory-system/tests/test_memory_store.py -v
```

---

### 15D. (If time) claw-code Architecture Notes (~10 min)
**Scope:** Document architectural patterns from the cloned claw-code repo that inform CCA's agent dispatch design. Reference only — do NOT build anything.

**Key findings from Chat 14.5 study of `references/claw-code/src/`:**

| File | Pattern | CCA Relevance |
|------|---------|---------------|
| `runtime.py` (193 lines) | `route_prompt()` — token-based fuzzy matching routes to commands OR tools by keyword overlap scoring | Separation of routing (which agent?) from execution (run agent). Our `/cca-nuclear` could use this for auto-selecting which agent handles which URL type. |
| `query_engine.py` (194 lines) | `QueryEnginePort` — `max_turns` + `max_budget_tokens` + `compact_after_turns` + transcript persistence | Budget-aware session management. Their `max_budget_tokens=2000` is a hard cap on cumulative token usage. Directly informs our tool-call budget rule (15B). |
| `execution_registry.py` (52 lines) | `ExecutionRegistry` — `MirroredCommand` + `MirroredTool` with uniform `.execute()` interface | Clean registry pattern. Our agents could follow: `AgentRegistry` with uniform `.spawn()`. |
| `permissions.py` (21 lines) | `ToolPermissionContext` — `deny_names` frozenset + `deny_prefixes` tuple, `.blocks(tool_name)` | Permission model matching our `disallowedTools` frontmatter. Confirms our approach is aligned with CC internals. |
| `tool_pool.py` (38 lines) | `ToolPool` — assembled with `simple_mode`/`include_mcp`/`permission_context` filters | Pattern for building filtered agent pools per task type (e.g., research agents vs build agents). |

Write `CLAW_CODE_ARCHITECTURE_NOTES.md` (1 page max) in project root documenting these patterns.

**STOP CONDITION:** Notes written and committed. Do NOT build anything from these patterns. They inform Chat 16+ design work.

---

## After Chat 15

- **Chat 16:** Agent Teams in `/cca-nuclear` (parallel URL reviews) + SessionStart hook for auto-init + SubagentStart budget tracking
- **Chat 17:** Compaction v2 + cross-chat delivery + Phase 5 plan

**Tests:** 349 suites, 12199 tests passing (10/10 quick smoke confirmed in 14.5 wrap). Git: main, clean.
**Budget:** Check time at init. If off-peak (after 2PM ET or weekend): 100% budget, agent spawns OK. If peak (8AM-2PM ET weekday): 40-50%, skip 15D and limit agent test invocations.
**Commit cadence:** Commit after each task (15A, 15B, 15C, 15D). Do not batch.

**Milestone:** After 15A completes, all 4 priority agents from `CUSTOM_AGENTS_DESIGN.md` are built and deployed. Phase 4 shifts from "build agents" to "orchestrate agents" starting Chat 16.
