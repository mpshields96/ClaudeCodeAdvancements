# NEXT CHAT HANDOFF — Chat 15.5 / 16 / 17

## Start Here
Run /cca-init. Last session was S247 Chat 15 on 2026-04-01.

---

## Context: What was done (Chat 15)

1. **15A: cca-scout agent BUILT + DEPLOYED** — 4th and final priority agent from CUSTOM_AGENTS_DESIGN.md. Sonnet, maxTurns 40, read-only. Scans r/ClaudeCode, r/ClaudeAI, r/vibecoding. Validated: 4 high-signal posts found from 10 test posts, proper rat-poison filtering, correct output format. 34K tokens, 41s. Command converted to thin orchestrator that spawns agent.
2. **15B: cca-test-runner HARDENED** — maxTurns bumped 10->15. Summary-first output pattern added (RESULT line emitted before detailed analysis). Validated: 342/350 suites, 12199 tests, completed in turn 1 (well within 15-turn limit).
3. **15C: Ebbinghaus decay INTEGRATED** — `decay.py` wired into `memory_store.py:search()`. New `last_accessed_at` column via migration. `search()` now returns `effective_confidence` per result (decay applied based on days since last access). Results sorted by effective_confidence. Touch-on-read refreshes decay clock. 4 new integration tests, all 117 tests pass.
4. **15D: claw-code architecture notes** — 5 patterns documented in `CLAW_CODE_ARCHITECTURE_NOTES.md`: token-based routing, budget-aware sessions, uniform execution registry, permission deny model, filtered tool pools. Reference only — informs Chat 16+ design.

**MILESTONE: All 4 priority agents from CUSTOM_AGENTS_DESIGN.md are now built and deployed.**

| Agent | Model | maxTurns | Status |
|-------|-------|----------|--------|
| cca-test-runner | haiku | 15 | VALIDATED + HARDENED |
| cca-reviewer | sonnet | 30 | VALIDATED |
| senior-reviewer | opus | 15 | VALIDATED |
| cca-scout | sonnet | 40 | VALIDATED |

Phase 4 shifts from "build agents" to "orchestrate agents" starting Chat 16.

---

## Chat 15.5 — Reddit Review Session (~30 min)

**Purpose:** Focused /cca-review session. No code changes. Pure intelligence gathering.

### Scout Finds (from Chat 15 test run)

Review these 4 high-signal posts from the cca-scout validation run:

1. **"Follow-up: Claude Code's source confirms the system prompt problem"** (r/ClaudeCode, 241 pts, 83 comments)
   URL: https://www.reddit.com/r/ClaudeCode/comments/1s99j2t/
   Why: Technical deep-dive on CC's internal system prompt structure — relevant to agent-guard and context-monitor.

2. **"Claude Code running locally with Ollama"** (r/ClaudeCode, 195 pts, 62 comments)
   URL: https://www.reddit.com/r/ClaudeCode/comments/1s90vd4/
   Why: Local model backend for CC — implications for offline preparedness and cost reduction.

3. **"Claude Code full reverse engineering breakdown"** (r/ClaudeCode, 101 pts, 18 comments)
   URL: https://www.reddit.com/r/ClaudeCode/comments/1s8w0so/
   Why: Pre-leak architectural analysis of CC internals — useful for hook system and tool-call budgeting.

4. **"Claude Code 2.1.89 released"** (r/ClaudeCode, 93 pts, 40 comments)
   URL: https://www.reddit.com/r/ClaudeCode/comments/1s9gubd/
   Why: New release thread — check for changelog items affecting hooks, Stop events, session limits.

### Matthew's Additional Links
<!-- Matthew: Add your Reddit/GitHub URLs here before running Chat 15.5 -->
5. (add URL here)
6. (add URL here)

### Workflow
1. Run `/cca-init` (slim)
2. For each URL above: run `/cca-review <url>` — full verdict (frontier mapping, rat poison check, BUILD/ADAPT/REFERENCE/SKIP)
3. Log all verdicts to FINDINGS_LOG.md
4. If any BUILD verdicts: note them for Chat 16+ task integration
5. Commit the FINDINGS_LOG.md update
6. Wrap with `/cca-wrap`

**Budget note:** This is a review-only session. If peak hours, use cca-reviewer agent (sonnet) for each URL to keep orchestrator context lean. If off-peak, inline reviews are fine.

**STOP CONDITION:** All URLs reviewed, verdicts logged, FINDINGS_LOG.md committed.

---

## Chat 16 — Agent Orchestration + Hooks (~60 min)

### 16A. Wire Agent Teams into /cca-nuclear (~25 min)
**Scope:** Make `/cca-nuclear` spawn parallel cca-reviewer agents for each URL instead of reviewing inline.

**Current state:** `/cca-nuclear` scans subreddits, finds high-signal posts, then reviews each one sequentially in the main context — burning orchestrator tokens on content that should be delegated.

**Target:** After cca-scout returns its ranked list, spawn one cca-reviewer agent per URL (in parallel batches of 3-4 to avoid rate limits). Each agent runs independently, returns verdict. Orchestrator collects verdicts and updates FINDINGS_LOG.md.

**Steps:**
1. Read `.claude/commands/cca-nuclear.md` — understand current flow
2. Modify the review step: instead of inline review, spawn `Agent(subagent_type="cca-reviewer", prompt="Review <url>...")` for each URL
3. Use parallel Agent calls (3-4 concurrent) — Claude Code supports multiple Agent tool calls in one message
4. Collect results, format FINDINGS_LOG.md entries, append
5. Test with 2-3 URLs from Chat 15.5's review session (use URLs already reviewed so we can compare quality)

**STOP CONDITION:** `/cca-nuclear` delegates to agents. Parallel review works. FINDINGS_LOG.md updated correctly.

### 16B. SessionStart Hook for Auto-Init (~20 min)
**Scope:** Create a hook that fires on session start and runs lightweight init checks automatically.

**What it should do:**
- Fire on CC session start (SessionStart event, if available — check CC docs)
- Run `slim_init.py` automatically (smoke test + priority picker)
- Output a 3-line status to the session: tests OK/FAIL, budget peak/off-peak, top task
- Does NOT replace `/cca-init` — it's a lightweight pre-check that makes init faster

**Steps:**
1. Check if SessionStart hook type exists in CC (may be `Notification` type or custom)
2. If available: create `hooks/session_start_hook.py` — runs slim_init.py, outputs status
3. Wire into `settings.local.json`
4. Test by starting a new CC session in a separate terminal
5. If SessionStart doesn't exist as a hook type: document the gap and propose using the existing Stop hook to write a "next session" breadcrumb instead

**STOP CONDITION:** Hook fires on session start OR gap documented with workaround.

### 16C. SubagentStart Hook for Spawn Budget (~15 min)
**Scope:** Track agent spawns and warn when cumulative cost exceeds budget.

**What it should do:**
- Fire on each Agent tool call (PreToolUse where tool matches "Agent")
- Count spawns this session, estimate cumulative token cost
- Warn if total estimated agent cost > 200K tokens (configurable threshold)
- Log each spawn to a session-level tracking file

**Steps:**
1. Create `hooks/spawn_budget_hook.py`
2. PreToolUse matcher: tool_name == "Agent" or tool_name == "agent"
3. Track count + estimated cost in `~/.claude-spawn-budget.json`
4. At threshold: output warning (don't block — just warn)
5. Wire into settings.local.json
6. Test by spawning 2-3 agents and checking the budget file

**STOP CONDITION:** Hook tracks spawns, warns at threshold. Budget file accumulates correctly.

---

## Chat 17 — Compaction + Cross-Chat + Phase 5 Plan (~60 min)

### 17A. Compaction Protection v2 (~25 min)
**Scope:** Upgrade context-monitor's compaction handling based on real session data.

**Current state:** `context-monitor/session_pacer.py` tracks context usage zones (green/yellow/red/critical). But it doesn't protect against the actual compaction bug — where CLAUDE.md rules and session context are lost after compression fires.

**Target:** Detect when compaction has fired (context usage drops suddenly) and re-inject critical rules.

**Steps:**
1. Read `context-monitor/session_pacer.py` — understand current zone tracking
2. Add compaction detection: if context usage drops >30% between checks, compaction likely fired
3. On detection: output a "COMPACTION DETECTED — re-reading critical context" message
4. Re-read CLAUDE.md rules (the most commonly lost content after compaction)
5. Test by simulating a context drop in the pacer's state file

**STOP CONDITION:** Pacer detects compaction events. Re-injection triggered on detection.

### 17B. Cross-Chat Delivery — Phase 3+4 Results (~15 min)
**Scope:** Write a comprehensive CCA_TO_POLYBOT.md delivery summarizing Phase 3 (research) and Phase 4 (custom agents) results that benefit the Kalshi bot.

**Deliverables for Kalshi chat:**
- Loop detection guard (agent-guard/loop_detector.py) — prevents infinite retry loops
- Session pacer with peak/off-peak awareness — saves tokens during rate-limited hours
- Custom agent pattern — Kalshi could have its own agents (e.g., market-scanner, edge-validator)
- Ebbinghaus decay for memory — applicable to Kalshi's self-learning journal (old patterns decay)

**Steps:**
1. Read current `~/.claude/cross-chat/CCA_TO_POLYBOT.md`
2. Append a new delivery section with the 4 items above
3. Include file paths, usage examples, and integration guidance
4. Mark as PENDING for Kalshi chat to acknowledge

**STOP CONDITION:** Delivery written with 4 items. Marked PENDING.

### 17C. Write Phase 5 Plan (~20 min)
**Scope:** Define Phase 5 of the Custom Agents milestone. Phase 4 was "build agents." Phase 5 is "production hardening + monitoring."

**Phase 5 candidates (from Chat 15 advancement tips + CLAW_CODE_ARCHITECTURE_NOTES.md):**
1. Tool-call budget hook (programmatic max_budget_tokens via PreToolUse — from claw-code patterns)
2. Agent registry with uniform .spawn() interface
3. Token-based prompt routing for /cca-nuclear URL dispatch
4. Agent performance dashboard (which agents cost what, success rates)
5. Agent retry/fallback patterns (if sonnet agent fails, retry with opus)

**Steps:**
1. Read `CUSTOM_AGENTS_DESIGN.md` for Phase 4 completion status
2. Read `CLAW_CODE_ARCHITECTURE_NOTES.md` for architectural patterns to implement
3. Write Phase 5 plan section in CUSTOM_AGENTS_DESIGN.md
4. Update TODAYS_TASKS.md with Phase 5 task list

**STOP CONDITION:** Phase 5 plan written and committed.

---

## Tests
350 suites, 12199 tests passing (342/350 clean — 8 pre-existing failures in reference dirs + autoloop).
10/10 quick smoke confirmed in Chat 15.

## Budget
Check time at init:
- **Peak (8AM-2PM ET weekday):** 40-50% budget. Skip 16C if needed. Limit agent test invocations.
- **Off-peak:** 100% budget. Agent spawns OK.

## Commit Cadence
Commit after each task. Do not batch.
