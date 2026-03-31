# CCA Tasks — 2026-03-30 (Updated S241, Chat 7)
# Source: S234-S241 unified plan. Phases 1-2 complete. Phase 3 planned in S241 Chat 7.
# Read by ALL subsequent CCA chats. This is the ONLY task authority.

---

## PHASE 1: COMPLETED (S236-S238)

Tasks A-E from the original S235 plan. All investigation/research/build work done.
Chats 1-3 executed as planned. See "Completion Archive" at bottom for details.

| Task | Session | Status | Output |
|------|---------|--------|--------|
| A. Cache Bug Mitigations | S236 | DONE | .zshrc env vars set, findings documented |
| B. /cca-wrap Token Audit | S236 | DONE | Step 6g removed (~3K saved), 4 proposals documented |
| C. Rate Limits Statusline | S236 | DONE | Already configured via cship — no changes needed |
| D. Prism/TurboQuant Research | S237 | DONE | Research doc: memory-system/research/PRISM_TURBOQUANT_RESEARCH.md |
| E. Loop Detection Guard | S238 | DONE | agent-guard/loop_detector.py + hooks/loop_guard.py, 40 tests, hook wired |

### Uncommitted work from Phase 1 (must be committed in Chat 4):
- S236: .claude/commands/cca-wrap.md (Step 6g removal) — modified but never committed
- S237: memory-system/research/PRISM_TURBOQUANT_RESEARCH.md — untracked, never committed
- S236 findings in this file — never committed as standalone commit

---

## PHASE 2: BUILD + HARDEN (Chats 4-7)

Everything below builds on Phase 1 research. Ordered by ROI: token savings first,
then workflow improvements, then learning/evaluation.

---

### CHAT 4: Cleanup + Env Verification + Dream Design (~45 min)

Four tasks. Do them in order 4A-4D.

#### 4A. Commit Phase 1 Uncommitted Work [DONE S239]
**Scope:** Git hygiene — commit everything Phase 1 left behind.
**Steps:**
1. `git add .claude/commands/cca-wrap.md` — S236 wrap quick win
2. `git add memory-system/research/PRISM_TURBOQUANT_RESEARCH.md` — S237 research
3. Commit with message referencing S236+S237 work
**STOP CONDITION:** One clean commit. Move to 4B.

#### 4B. Verify Environment Variables Are Active [DONE S239 — set in .zshrc, takes effect next launch]
**Scope:** Confirm S236 cache mitigations are live in this session.
**Steps:**
1. Run `echo $ENABLE_TOOL_SEARCH` — should be `false` (not `auto`)
2. Run `echo $CLAUDE_CODE_DISABLE_1M_CONTEXT` — should be `1`
3. If either is wrong: `source ~/.zshrc` or note that it takes effect on next launch
4. Confirm loop guard state file exists: `ls ~/.claude-loop-detector.json`
**STOP CONDITION:** Both vars confirmed or documented as "next launch." Move to 4C.

#### 4C. Smoke Test Loop Guard in Real Usage [DONE S239 — fires correctly on 3+ similar outputs, no false positives]
**Scope:** Validate the loop guard actually fires when it should.
**Steps:**
1. Run 4 identical bash commands (e.g., `echo "test loop"` four times)
2. Check if the hook outputs a LOOP DETECTED warning after the 4th
3. If no warning: check `~/.claude-loop-detector.json` to see if state is accumulating
4. If hook isn't firing: verify settings.local.json has the PostToolUse entry
**STOP CONDITION:** Guard fires correctly OR issue identified and logged. Move to 4D.

#### 4D. Task F: Auto Dream Integration Design [DONE S239 — memory-system/DREAM_INTEGRATION_DESIGN.md]
**Scope:** SHORT design note — 1 page max. No code.
**Context:** `/dream` is Anthropic's native memory consolidation (runs at session end,
writes learnings to CLAUDE.md). CCA's Frontier 1 memory system must complement, not compete.
**Steps:**
1. Read `/dream` docs (official CC docs or test it once to see what it produces)
2. Answer: What does CCA memory do that /dream doesn't?
   - Structured types with TTL/confidence scoring
   - Cross-session FTS5 search
   - Auto-capture from hooks (not just session-end)
   - Typed categories (user, feedback, project, reference)
3. Answer: What does /dream do that CCA memory doesn't?
   - Native integration (survives compaction, auto-loaded)
   - Zero configuration
   - Anthropic maintains it
4. Write `DREAM_INTEGRATION_DESIGN.md` in memory-system/ — 1 page, clear separation
**STOP CONDITION:** Design note written and committed. Do NOT build anything.
**Reference:** FINDINGS_LOG entry #11 (Auto Dream pivot), D research doc

---

### CHAT 5: Wrap/Init Token Optimization Build (~60 min)

The highest-ROI build remaining. Every token saved here compounds across every future session.

#### 5A. Build batch_wrap_analysis.py [DONE S240]
**Scope:** Consolidate wrap Steps 6b-6h into a single Python script.
**Context:** Currently 7 separate optional steps, each with its own bash call and
context overhead in the wrap command. A single script runs reflect, escalate, validate,
and evolve in one subprocess call.
**Steps:**
1. Read current Steps 6b-6h in .claude/commands/cca-wrap.md
2. Build `batch_wrap_analysis.py` that runs all 7 analyses and outputs combined results
3. Write tests
4. Replace Steps 6b-6h in cca-wrap.md with single `python3 batch_wrap_analysis.py` call
**Expected savings:** ~5,000 tokens per wrap (7 bash blocks → 1)
**STOP CONDITION:** Script works, tests pass, wrap command updated. Move to 5B.

#### 5B. Trim Wrap Command to Slim-Only [DONE S240]
**Scope:** Move verbose documentation out of the command file into a reference doc.
**Steps:**
1. Create `WRAP_REFERENCE.md` with full step explanations (the "why" behind each step)
2. Reduce cca-wrap.md to code blocks + one-line descriptions only
3. Remove full-mode instructions (SLIM covers 90% of wraps; full mode in reference only)
4. Target: 600 lines → ~250 lines (~1,650 tokens saved on every wrap load)
**STOP CONDITION:** Wrap command is leaner, reference doc has the details, wrap still works.

#### 5C. Conditional Cross-Chat Step [DONE S240]
**Scope:** Make Step 7.5 (cross-chat coordination) skip if no Kalshi-relevant work.
**Steps:**
1. Add check: if session touched no Kalshi-related files/topics, skip the cross-chat write
2. ~5 LOC conditional
**STOP CONDITION:** Implemented and tested.

**Chat 5 target:** Wrap cost drops from ~20K to ~12K tokens (40% reduction).

---

### CHAT 6: Claude Code Guide Study + Paseo Evaluation (~45 min)

Two evaluation/learning tasks that pair well — neither produces CCA code.

#### 6A. Claude-Howto Best Practices Study [DONE S241]
**Scope:** Read shanraisshan/claude-code-best-practice repo (25K+ stars, 10 modules).
This is Matthew's personal learning resource — CCA reads it and produces a gap analysis.
**Steps:**
1. Read the repo's module index / table of contents
2. For each module: summarize what it teaches vs what CCA already does
3. Flag any gaps — things the guide covers that we DON'T do yet
4. Prioritize the CLAUDE.md layering section, hooks deep-dive, and MCP server setup
5. Write a short `CLAUDE_HOWTO_GAP_ANALYSIS.md` — what to focus on, what to skip
**STOP CONDITION:** Gap analysis written. Do NOT implement anything from it in this chat.
**Reference:** FINDINGS_LOG entry #5, entry #72. github.com/shanraisshan/claude-code-best-practice

#### 6B. Task G: Paseo Evaluation [DONE S241 — DEFER verdict]
**Scope:** Install, test, and evaluate Paseo for mobile Claude Code access.
**Steps:**
1. Clone getpaseo/paseo repo
2. Read architecture docs — understand daemon + WebSocket model
3. Install and run locally
4. Test: can you connect to a running CC session from a second device?
5. Evaluate: latency, reliability, security (E2EE?), mobile UX
6. Write verdict: ADOPT / DEFER / SKIP with reasoning
**STOP CONDITION:** Verdict written. Adopt only if it works reliably.
**Reference:** FINDINGS_LOG entry #67 (Paseo review)

---

### CHAT 7: Mistake-Learning Build + Kalshi Port (~60 min)

#### 7A. Mistake-Learning Pattern from Prism (Task D follow-up) [DONE S241]
**Scope:** Build auto-capture of error corrections into self-learning journal.
**Context:** Prism MCP's mistake-learning pattern: when an agent makes an error and
then corrects it, the correction is auto-captured and resurfaced as a warning in future
sessions. This turns reactive debugging into proactive prevention.
**Steps:**
1. Design: detect error→correction sequences in tool output
2. Build: capture module that writes corrections to self-learning/journal.jsonl
3. Integration: PostToolUse or Stop hook that identifies the pattern
4. Tests
**STOP CONDITION:** Working capture + tests. Resurfacing is a separate enhancement.
**Reference:** S237 research doc (PRISM_TURBOQUANT_RESEARCH.md), FINDINGS_LOG entry #39

#### 7B. Port Improvements to Kalshi Project [DONE S241]
**Scope:** Apply CCA workflow improvements to polymarket-bot project.
**Steps:**
1. Add loop guard hook to Kalshi project's settings (settings.local.json or project settings)
2. Verify env vars (ENABLE_TOOL_SEARCH, DISABLE_1M_CONTEXT) apply to Kalshi sessions
3. Apply any wrap optimizations built in Chat 5 that are project-agnostic
4. Write CCA_TO_POLYBOT.md delivery noting all changes
**STOP CONDITION:** Kalshi project has parity with CCA's workflow improvements.

---

## STANDING TASKS (all chats)

### Cross-Chat Coordination
- Check POLYBOT_TO_CCA.md at start of every chat
- Write CCA_TO_POLYBOT.md deliveries as findings warrant
- Lopez de Prado AFML delivery already written (S234)

### CLI Migration Status
- Phase 1 (CCA): DONE S227
- Phase 2 (Codex): PENDING — not today's priority
- Phase 3 (Kalshi): PENDING — not today's priority

### Loop Guard Validation (passive — all autonomous sessions)
- Loop guard is wired as PostToolUse hook in ~/.claude/settings.local.json
- Monitor for false positives or missed loops across Chats 4-7
- If threshold needs tuning, adjust CLAUDE_LOOP_THRESHOLD env var (default: 0.80)

---

## PHASE 3: COMPLETE THE PATTERNS + HARDEN (Chats 8-11)

Phase 1 found problems (reddit research). Phase 2 built first fixes. Phase 3 completes
the patterns and hardens the infrastructure. Each task closes a loop that Phase 1-2 opened.

**Evidence chain:**
- Correction capture (7A) built capture-only → need resurfacing to complete the pattern
- Gap analysis (6A) found 18 unused hooks, 11 unused subagent fields → pick highest ROI
- Prism research (S237) recommended Ebbinghaus decay → replace crude TTL cliffs
- Multiple sessions documented compaction state loss → PreCompact/PostCompact hooks

**Key reference documents:**
- `CLAUDE_HOWTO_GAP_ANALYSIS.md` — hook events, subagent fields, orchestration pattern
- `memory-system/research/PRISM_TURBOQUANT_RESEARCH.md` — Ebbinghaus decay, correction patterns
- `memory-system/DREAM_INTEGRATION_DESIGN.md` — how CCA memory layers on AutoDream

---

### CHAT 8: Correction Resurfacing + PostToolUseFailure (~45 min)

Complete the Prism mistake-learning pattern. Chat 7 built capture. Chat 8 builds resurfacing.

#### 8A. Correction Resurfacing at Session Init [TODO]
**Scope:** Query recent corrections from journal.jsonl and surface them as warnings.
**Context:** correction_detector.py captures error->fix sequences to journal.jsonl as
`correction_captured` events. But they're never read back. Prism's pattern auto-surfaces
high-importance corrections as warnings in future sessions. Without resurfacing,
corrections are logged but never prevent repeat mistakes.
**Steps:**
1. Read self-learning/journal.py — understand the query API (get_recent, _load_journal)
2. Build `self-learning/resurfacer.py`:
   - `get_recent_corrections(days=7)` — query journal for correction_captured events
   - `format_warnings(corrections)` — format as concise one-line warnings
   - Return list of strings suitable for injection into session context
3. Write tests for resurfacer.py
4. Integration point: /cca-init can call `python3 self-learning/resurfacer.py` and
   display recent corrections during session briefing
**Expected output:** "Recent corrections (last 7 days): Edit failed on X due to
non-unique match — use larger context string. (3 occurrences, last 2h ago)"
**STOP CONDITION:** resurfacer.py works with tests. Integration into /cca-init is
a separate step (can be done in 8A or left for later). Do NOT build importance
scoring or Ebbinghaus decay here — that's 9A.

#### 8B. Wire PostToolUseFailure Hook [TODO]
**Scope:** Add PostToolUseFailure as a cleaner error signal for correction_detector.
**Context:** Currently correction_capture.py runs on PostToolUse and uses heuristic
regex to detect errors in tool output (ERROR_PATTERNS list in correction_detector.py).
PostToolUseFailure fires only when a tool actually fails — no false positives.
**Steps:**
1. Verify PostToolUseFailure hook exists in current CC version:
   `claude --help` or check hook documentation
2. If it exists: create `self-learning/hooks/failure_capture.py` — simpler than
   correction_capture.py because the failure is definitive (no heuristic needed)
3. Wire in settings.local.json alongside existing PostToolUse hooks
4. The failure_capture hook records the error; the existing correction_capture hook
   on PostToolUse still detects when the correction happens. Together they give:
   - Definitive error signal (PostToolUseFailure) + correction detection (PostToolUse)
5. If PostToolUseFailure doesn't exist: document this, move on. The current
   heuristic approach in correction_capture.py is the fallback.
**STOP CONDITION:** Hook wired if available, or documented as unavailable. Move to 8C.

#### 8C. Cross-Chat Delivery [TODO]
**Scope:** If any Kalshi-relevant improvements were made, write CCA_TO_POLYBOT.md.
**STOP CONDITION:** Delivery written if applicable, skip if not.

---

### CHAT 9: Memory Decay + Subagent Hardening (~45 min)

Two independent improvements: principled memory decay, and frontmatter hardening.

#### 9A. Ebbinghaus Decay for Memory Confidence [TODO]
**Scope:** Replace hard TTL cutoffs with continuous exponential decay.
**Context:** CCA memory uses cliff-edge TTL: HIGH=365d, MEDIUM=180d, LOW=90d.
A memory at day 89 (LOW) has full weight. At day 91 it vanishes. Prism uses
`effective = base * 0.95^days` — smooth decay where memories fade gradually.
This is more principled and avoids the cliff.
**Steps:**
1. Read memory-system/schema.md — understand current confidence/TTL model
2. Design the decay function:
   - Input: base_confidence (0-100), days_since_last_access
   - Output: effective_confidence (0-100)
   - Decay rate: configurable, default 0.95/day (Prism's value)
   - Floor: minimum effective confidence before pruning (e.g., 5)
3. Build `memory-system/decay.py`:
   - `compute_effective_confidence(base, days, decay_rate=0.95)` → float
   - `should_prune(base, days, floor=5)` → bool
   - `get_decay_rate_for_confidence(level)` → float
     (HIGH decays slower than LOW — e.g., HIGH=0.98, MEDIUM=0.96, LOW=0.93)
4. Write tests — verify decay curves, edge cases (0 days, negative days, very old)
5. Do NOT integrate into the memory system yet — this is the function only.
   Integration requires schema changes (adding `last_accessed_at` field).
**STOP CONDITION:** decay.py + tests. Integration is a future task.
**Reference:** PRISM_TURBOQUANT_RESEARCH.md Section 3B, recommendation #3

#### 9B. Subagent Frontmatter Hardening [TODO]
**Scope:** Add protective frontmatter fields to all CCA agent commands.
**Context:** Gap analysis found we use ~5/16 available subagent frontmatter fields.
Key missing fields that require zero code — just YAML frontmatter edits:
- `maxTurns`: Prevents runaway agents (no current protection)
- `effort`: Tunes per-agent quality (low for quick checks, high for complex work)
- `disallowedTools`: Scope down agent tool access for safety
**Steps:**
1. List all CCA commands that spawn agents:
   `grep -rl "subagent_type\|Agent(" .claude/commands/`
2. For each command, add appropriate frontmatter:
   - Worker agents: `maxTurns: 50`, `effort: medium`
   - Research agents: `maxTurns: 30`, `effort: high`
   - Quick check agents: `maxTurns: 10`, `effort: low`
   - All agents: `disallowedTools: [Write(~/.claude/*)]` (prevent modifying global config)
3. No code changes — frontmatter only. Verify commands still load correctly.
**STOP CONDITION:** All agent-spawning commands have maxTurns + effort set.
**NOTE:** If commands use the Agent tool programmatically (not via frontmatter),
this may require a different approach — document what's possible vs not.

#### 9C. Cross-Chat Delivery [TODO]
**Scope:** Write CCA_TO_POLYBOT.md if applicable.
**STOP CONDITION:** Delivery written or skipped.

---

### CHAT 10: Compaction Protection Hooks (~60 min)

**NOTE:** This chat starts with a design step. The gap analysis identified
PreCompact/PostCompact as valuable but didn't define what to save or how.

#### 10A. Design Compaction Protection Protocol [TODO]
**Scope:** Define exactly what state to preserve through compaction events.
**Steps:**
1. Read gap analysis Module 8 (hooks deep dive) for PreCompact/PostCompact details
2. Verify these hooks exist in current CC version (check docs/test)
3. If they exist, design the protocol:
   - **What to save (PreCompact):** Current task list (TodoWrite state), files being
     edited, active file paths from recent tool calls, session progress markers
   - **Where to save:** `~/.claude-compaction-snapshot.json` (atomic write)
   - **What to restore (PostCompact):** Re-inject critical context as a system message
     or read the snapshot file on next tool call
   - **What NOT to save:** Full conversation content (too large), tool outputs (stale)
4. Write the design as a short note: `context-monitor/COMPACTION_PROTECTION_DESIGN.md`
5. If hooks don't exist: document this, evaluate alternative approaches (e.g.,
   periodic state snapshots independent of compaction events)
**STOP CONDITION:** Design note written. Build only if hooks confirmed available.

#### 10B. Build Compaction Protection (if hooks available) [TODO]
**Scope:** Implement the protocol from 10A.
**Steps:**
1. Build `context-monitor/hooks/pre_compact.py` — PreCompact handler
2. Build `context-monitor/hooks/post_compact.py` — PostCompact handler
3. Wire in settings.local.json
4. Tests
**STOP CONDITION:** Hooks wired and tested, or documented as unavailable.

#### 10C. Cross-Chat Delivery [TODO]
**Scope:** Port compaction protection to Kalshi if applicable.

---

### CHAT 11: Architecture Study + Phase 4 Planning (~45 min)

This is a learning + planning session, not a build session. Output is design notes
and a Phase 4 plan, not code.

#### 11A. Hands-On CC Feature Exploration [TODO]
**Scope:** Try features identified in gap analysis that we've never used.
**Steps:**
1. Try `/btw` for side queries — does it preserve main context?
2. Try `--bare` mode: `claude -p --bare "hello"` — measure startup time vs normal
3. Try `/batch` if available — understand parallel changeset workflow
4. Try `context: fork` in a test command — verify isolated execution
5. Document findings: what works, what's useful, what's not worth it
**STOP CONDITION:** Each feature tried once, findings documented. ~20 min max.

#### 11B. Command->Agent->Skill Architecture Evaluation [TODO]
**Scope:** Evaluate the orchestration pattern from gap analysis Module 9.
**Context:** Current CCA commands do everything inline. The Module 9 pattern separates:
- Command (lightweight coordinator) → Agent (background executor with preloaded skills)
  → Skill (reusable domain knowledge)
**Steps:**
1. Pick one CCA command as a case study (suggest /cca-wrap — most complex)
2. Sketch how it would look refactored into Command->Agent->Skill
3. Evaluate: would this actually be better? Or is it overengineering for our scale?
4. Write findings in `ARCHITECTURE_EVALUATION.md`
**STOP CONDITION:** Evaluation written. Do NOT refactor anything. This is analysis only.

#### 11C. Native Agent Teams vs Hivemind Evaluation [TODO]
**Scope:** Compare Anthropic's native agent teams with our cca_comm.py hivemind.
**Steps:**
1. Check if `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` is available
2. If available: try spawning a basic 2-agent team, evaluate coordination
3. Compare: shared task list (native) vs JSONL queue (ours). Pros/cons.
4. Write verdict: ADOPT (replace hivemind) / COMPLEMENT (use alongside) / SKIP
**STOP CONDITION:** Verdict written. This informs MT-21 direction.

#### 11D. Write Phase 4 Plan [TODO]
**Scope:** Based on Chats 8-11 findings, write Phase 4 task list.
**Steps:**
1. Review what Chats 8-10 delivered vs what they deferred
2. Incorporate Chat 11 findings (which features are worth adopting)
3. Write Phase 4 plan following the same format as Phases 2-3
**STOP CONDITION:** Phase 4 plan written into this file.

---

## DEFERRED (not scheduled, revisit when relevant)

- **TurboQuant vector compression** — only when Frontier 1 hits storage scale problems
- **Computer use monitoring** — token costs catastrophic, revisit when Anthropic stabilizes pricing
- **cc2codex** — LLM diversification tool, revisit if needed
- **Octopoda shared knowledge spaces** — MT-21 hivemind enhancement, after basic hivemind is proven
- **Loop guard v2 (embeddings)** — only if v1 string similarity proves insufficient

---

## PHASE 2: COMPLETED (S239-S241)

Chats 4-7 from Phase 2 plan. All build/evaluation/port work done.

| Chat | Session | Status | Output |
|------|---------|--------|--------|
| 4: Cleanup + Dream Design | S239 | DONE | Phase 1 committed, env vars verified, loop guard smoke tested, DREAM_INTEGRATION_DESIGN.md |
| 5: Wrap Optimization | S240 | DONE | batch_wrap_analysis.py, slim cca-wrap.md, conditional cross-chat (~40% wrap token reduction) |
| 6: Learning + Evaluation | S241 | DONE | CLAUDE_HOWTO_GAP_ANALYSIS.md (13 modules, top gaps: subagents, hooks, orchestration), Paseo DEFER |
| 7: Mistake-Learning + Port | S241 | DONE | correction_detector.py + correction_capture.py hook (68 tests), Kalshi port (hooks + env vars) |

---

## COMPLETION ARCHIVE (Phase 1, S236-S238)

S234: 10 Reddit posts reviewed, cache bugs PSA found, 2 memories created, Kalshi AFML delivery
S235: 11 Reddit posts reviewed (21 total), unified plan created, this file updated
S236: Cache bug investigation + wrap audit + statusline check. Findings documented. Quick win (Step 6g removal) implemented.
S237: TurboQuant + Prism MCP research complete. Written to memory-system/research/PRISM_TURBOQUANT_RESEARCH.md
S238: Loop Detection Guard v1 built. agent-guard/loop_detector.py + hooks/loop_guard.py. 40 tests. Hook wired globally.

---

## SESSION RULES (Matthew directive, S178 — still active)
- **THIS FILE IS AUTHORITATIVE.** All CCA sessions work on TODO items here until complete.
- Do NOT use priority_picker or MASTER_TASKS until ALL TODOs here are done.
- Kalshi bot tasks: deliver via CCA_TO_POLYBOT.md, don't implement in polybot directly.
- Mark items [DONE SN] as they complete, but NEVER remove them.
- Each subsequent CCA chat reads THIS FILE FIRST to know what to work on.
- Matthew updates this file daily — follow it, don't second-guess it.
- **STOP CONDITIONS are boundaries, not suggestions.** When a stop condition is hit, MOVE ON.
- **Do NOT engage in autoloop or autowork unless Matthew explicitly requests it.**
