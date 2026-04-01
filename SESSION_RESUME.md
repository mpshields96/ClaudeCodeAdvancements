# NEXT CHAT HANDOFF — Chat 15

## Start Here
Run /cca-init. Last session was S246 Chat 14.5 on 2026-03-31.

You are Chat 15. Phase 4 (Custom Agents) continues. Three agents validated, one more to build.

**What was done (Chat 14 + 14.5):**
1. **All 3 agents VALIDATED** — cca-test-runner (haiku), cca-reviewer (sonnet), senior-reviewer (opus). All frontmatter fields confirmed working: model, maxTurns (hard cap), disallowedTools (behavioral). See `AGENT_PIPELINE_VALIDATION.md`.
2. **Two repos cloned** (DMCA preservation) to `references/` (gitignored, not in CCA git):
   - `references/claw-code/` — Python rewrite of Claude Code (instructkr/claw-code)
   - `references/claude-code-source-build/` — Source map extraction (andrew-kramer-inno)
3. **Cache audit: HEALTHY** — 68-99% cache read ratios. db8 bug NOT active. No urgent auditor needed.
4. **Reddit reviews (4 URLs):**
   - claw-code: SKIP (cloned for reference only)
   - claude-code-source-build: SKIP (cloned for reference only)
   - Cache fix (db8): ADAPT — validated bug, cache auditor is safe to build but NOT urgent (our cache is fine)
   - Universal CLAUDE.md: ADAPT — two rules worth stealing (14.5F skipped, do in this chat)
5. **Senior-reviewer verdict on senior_review.py:** CONDITIONAL — 5 real issues (silent exception swallowing, PEP8 `l` var, inconsistent GitContext, hardcoded LOC threshold, dead fp_confidence). Anti-rubber-stamp confirmed.

**Deployed agents (all in `~/.claude/agents/`):**
- `cca-test-runner.md` — haiku, maxTurns 10, VALIDATED
- `cca-reviewer.md` — sonnet, maxTurns 30, VALIDATED
- `senior-reviewer.md` — opus, maxTurns 15, VALIDATED

---

## Chat 15 Tasks

### 15A. Build `cca-scout` Agent (~25 min)
**Scope:** Convert /cca-scout command into agent. Last of the 4 priority agents from CUSTOM_AGENTS_DESIGN.md.

**Frontmatter (from CUSTOM_AGENTS_DESIGN.md):**
```yaml
---
name: cca-scout
description: Scan subreddits for high-signal posts relevant to CCA frontiers.
tools: Read, Bash, Grep, Glob, WebFetch
disallowedTools: Edit, Write, Agent
model: sonnet
maxTurns: 40
effort: medium
color: green
---
```

**Steps:**
1. Read `.claude/commands/cca-scout.md` (101 lines) — understand Steps 1-5
2. Create `.claude/agents/cca-scout.md` with frontmatter above + condensed prompt body
3. Prompt body must include: subreddit list, reddit_reader.py path, filtering criteria (score >= 50, keyword list), rat poison exclusions, FINDINGS_LOG.md dedup check, output format (ranked numbered list with verdicts)
4. Copy to `~/.claude/agents/cca-scout.md` (global deploy)
5. Convert `.claude/commands/cca-scout.md` into thin orchestrator that spawns the agent
6. Test: invoke via `Agent(subagent_type="cca-scout", prompt="Scan r/ClaudeCode for high-signal posts from past month")` — verify it produces a ranked post list
**STOP CONDITION:** Agent works, produces ranked post lists. All 4 CUSTOM_AGENTS_DESIGN.md agents complete.

### 15B. Steal Two CLAUDE.md Rules from Reddit Review #4 (~10 min)
**Scope:** Carried forward from 14.5F (skipped for time). Two rules from the "Universal CLAUDE.md" Reddit post:
1. **Redundant-read guard:** Before reading a file, check if it was already read in this conversation. Reduces wasted tool calls.
2. **Tool-call budget awareness:** Track approximate tool calls per task. If a simple task exceeds ~15 tool calls, pause and reassess approach.

**Steps:**
1. Add both rules to project CLAUDE.md under "Architecture Principles" or a new "Efficiency Rules" section
2. Keep them concise (2-3 lines each) — these are behavioral nudges, not infrastructure
**STOP CONDITION:** Two rules added to CLAUDE.md. No code changes.

### 15C. Harden `cca-test-runner` Based on Real Usage (~15 min)
**Scope:** Now that all 4 agents have real usage data, review and harden cca-test-runner.

**Context from validation:**
- maxTurns 10 is a hard cap that truncates mid-response — test runner hit this in Chat 14
- Agent completed in 7 turns for quick smoke but was cut off at 10 for full suite + reruns

**Steps:**
1. Review AGENT_PIPELINE_VALIDATION.md for any issues noted during real usage
2. If maxTurns 10 is too tight for full suite: bump to 12-15
3. Verify prompt handles truncation gracefully (outputs partial results if cut off)
4. Update both project and global copies
**STOP CONDITION:** Test runner handles edge cases. All 4 agents hardened.

### 15D. Integrate Ebbinghaus Decay into Memory System (~20 min)
**Scope:** Wire the decay function into actual memory queries. Currently `memory-system/decay.py` exists with `compute_effective_confidence()` but nothing calls it.

**Steps:**
1. Read `memory-system/decay.py` and `memory-system/schema.md`
2. Update schema.md — add `last_accessed_at` field
3. Update memory query path to call `compute_effective_confidence()`
4. Update memory access to refresh `last_accessed_at` timestamp
5. Write tests for integration (decay during query, timestamp updates)
**STOP CONDITION:** Memory queries return decayed confidence scores. Tests pass.

### 15E. (If time) claw-code Architecture Notes (~10 min)
**Scope:** Document what's useful in the cloned claw-code repo for CCA's agent dispatch.

**Key findings from Chat 14.5 study of `references/claw-code/src/`:**
- `runtime.py:PortRuntime.route_prompt()` — token-based fuzzy matching routes prompts to commands OR tools by scoring keyword overlap. Relevant pattern: separation of routing (which agent?) from execution (run the agent).
- `query_engine.py:QueryEnginePort` — session management with `max_turns`, `max_budget_tokens`, compaction after N turns, transcript persistence. Their `max_budget_tokens` is exactly what our tool-call budget rule (15B) should enforce.
- `execution_registry.py:ExecutionRegistry` — clean registry pattern: `MirroredCommand` and `MirroredTool` with uniform `.execute()` interface. Our agents could follow this: `AgentRegistry` with uniform `.spawn()`.
- `permissions.py:ToolPermissionContext` — `deny_names` + `deny_prefixes` as frozensets. Clean permission model similar to our `disallowedTools` frontmatter.
- `tool_pool.py:ToolPool` — assembled with filters (simple_mode, include_mcp, permission_context). Pattern for building filtered agent pools per task type.

Write a short `CLAW_CODE_ARCHITECTURE_NOTES.md` (1 page max) documenting these patterns for future reference.
**STOP CONDITION:** Notes written. Do NOT build anything from these patterns yet.

---

## After Chat 15: Continue 16-17
- Chat 16: Agent Teams in /cca-nuclear + SessionStart hook + SubagentStart budget
- Chat 17: Compaction v2 + cross-chat delivery + Phase 5 plan

**Tests:** 349 suites, 12199 tests passing. Git: main, clean.
**Time:** Off-peak (100% budget). All agent spawns OK.
**All 4 agents from CUSTOM_AGENTS_DESIGN.md should be complete after this chat.**
