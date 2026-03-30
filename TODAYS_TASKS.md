# CCA Tasks for 2026-03-30
# Updated: S235. Read by ALL subsequent CCA chats today.
# Source: S234+S235 unified Reddit intelligence review (21 posts total across 2 sessions).
# Matthew approved this plan in S235. Follow it exactly.

---

## TODAY'S PRIORITY: Token Optimization + Research (S235 Plan)

Context: S234+S235 reviewed 21 Reddit posts. Three independent reports confirm a cache
invalidation bug in Claude Code that can 10-20x token costs. Matthew directive: optimize
token waste (init/wrap), investigate mitigations, gain cost visibility. After that, research
tools discovered in reviews that could improve CCA infrastructure.

---

## CHAT 1: Cache Mitigations + Wrap Audit + Statusline (~90 min)

Three tasks, all token-optimization focused. Do them in order A→B→C.

### A. Cache Bug Mitigations [DONE S236]
**Scope:** Investigate and document. Do NOT decompile binaries or patch runtime.
**Steps:**
1. Check installation type: `which claude` — is it standalone binary or npx?
2. Test adding `"ENABLE_TOOL_SEARCH": "false"` to env in settings.json
3. Confirm we're NOT using `--resume` (we prefer fresh sessions — verify this is true)
4. Check if `CLAUDE_CODE_DISABLE_1M_CONTEXT=1` env var is set (it should be)
5. Document all findings in a short section at bottom of this file
**STOP CONDITION:** After testing the 2 env vars and documenting, move to B. Do not rabbit-hole.
**References:** FINDINGS_LOG.md entries #1, #9, #31, #40

### B. /cca-wrap Token Audit [DONE S236]
**Scope:** Audit and propose. Implement ONLY quick wins (< 20 LOC changes).
**Steps:**
1. Read the /cca-wrap command file — measure how many files it reads/writes
2. Identify the heaviest token consumers in the wrap sequence
3. Identify any redundant reads (files read that could be skipped or deferred)
4. Propose optimizations with estimated token savings
5. Implement quick wins only (e.g., skip unnecessary file reads, reduce output verbosity)
6. If time permits, audit /cca-init the same way
**STOP CONDITION:** After proposing optimizations and implementing quick wins, move to C.
  Do NOT rewrite the entire wrap/init sequence. Heavy refactors become a future MT.
**Reference:** Matthew S232+S234 directive — init/wrap token waste is IMPERATIVE to optimize

### C. Rate Limits Statusline [DONE S236]
**Scope:** Enable and configure native CC rate_limits display.
**Steps:**
1. Research how to enable `rate_limits` in Claude Code statusline
2. Configure it in settings.json or settings.local.json
3. Verify it shows useful information
4. Document the setting for future sessions
**STOP CONDITION:** Once enabled and verified, chat is done. Wrap session.

---

## CHAT 2: Prism MCP + TurboQuant Research (~60 min)

### D. Frontier 1 Memory Evolution Research [DONE S237]
**Scope:** Pure research. Read paper, evaluate applicability. No code.
**Steps:**
1. Read arxiv paper 2504.19874 (Google TurboQuant — ICLR 2026)
2. Read Prism MCP source: github.com/dcostenco/prism-mcp (focus on turboquant.ts)
3. Evaluate: does 7-10x vector compression apply to our Frontier 1 memory schema?
4. Evaluate: Prism's mistake-learning pattern — applicable to self-learning journal?
5. Evaluate: Auto Dream integration path — how does Prism complement /dream?
6. Write findings to a research doc (e.g., PRISM_TURBOQUANT_RESEARCH.md)
**STOP CONDITION:** After writing research doc, wrap session. No implementation.
**References:** FINDINGS_LOG.md entry #39, also entry #11 (Auto Dream pivot)

---

## CHAT 3: Loop Detection Guard Build (~60 min)

### E. Autonomous Session Loop Detection [DONE S238]
**Scope:** Build MVP. Embedding-free v1 (string similarity, not vector similarity).
**Steps:**
1. Design: compare last N tool outputs for repetition (simple difflib similarity)
2. Threshold: if 3+ consecutive outputs are >80% similar, flag as loop
3. Integration point: could be a PostToolUse hook or inline check in /cca-auto
4. Build the detector module with tests
5. Wire as a PostToolUse hook (lightweight — just compares recent outputs)
**STOP CONDITION:** Working hook + tests. Do NOT add embedding infrastructure for v1.
  Embeddings are a v2 enhancement if v1 proves the concept.
**References:** FINDINGS_LOG.md entry #38 (Octopoda pattern)

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

---

## FUTURE TASKS (discovered in S234+S235, not for today)

- **Paseo evaluation** — mobile CC access, WebSocket agent management (Matthew likes this)
- **Computer use monitoring** — track token economics, revisit when stable (token cost too high now)
- **cc2codex bookmark** — LLM diversification tool, revisit if needed
- **Frontier 1 + Auto Dream integration** — design after Chat 2 research completes
- **Octopoda deep-dive** — shared knowledge spaces for MT-21 hivemind (after Chat 3 MVP)
- **Full wrap/init rewrite** — if Chat 1 audit reveals need for major refactor

---

## COMPLETED IN PREVIOUS SESSIONS (compressed archive)

All items from the 2026-03-28 version of this file (S176-S182, E1-E17, K1-K5, C1-C6)
remain completed. See git history for full details. Key: 338 suites, 11982 tests passing.

S234: 10 Reddit posts reviewed, cache bugs PSA found, 2 memories created, Kalshi AFML delivery
S235: 11 Reddit posts reviewed (21 total), unified plan created, this file updated
S236: Cache bug investigation findings documented below
S237: TurboQuant + Prism MCP research complete. Written to memory-system/research/PRISM_TURBOQUANT_RESEARCH.md
S238: Loop Detection Guard v1 built. agent-guard/loop_detector.py (core) + agent-guard/hooks/loop_guard.py (PostToolUse hook). 40 tests passing.

---

## S236 CACHE BUG INVESTIGATION FINDINGS

**Installation type:** Standalone binary (Mach-O arm64), v2.1.87. This IS the type affected by
cache bug #1 (CCH mutation in standalone binary). Not npx.

**ENABLE_TOOL_SEARCH:** Currently `auto` (Claude Code default). Setting to `false` would send
all tool schemas upfront, preventing cache invalidation when ToolSearch loads mid-conversation.
Tradeoff: ~2-5K more tokens on first message vs potentially major cache savings. Recommendation:
set to `false` in .zshrc — we use ToolSearch frequently and each load can invalidate the cache.

**CLAUDE_CODE_DISABLE_1M_CONTEXT:** Already in .zshrc (`export CLAUDE_CODE_DISABLE_1M_CONTEXT=1`)
but NOT present in current runtime env. This means either: (a) session was launched from a context
that didn't source .zshrc, or (b) the var was added after this session started. Verified by S234
research: 1M context degrades quality, shorter cache TTL (1hr Max vs 5min Pro). Keep it set.

**--resume flag:** NOT in use. We prefer fresh sessions. Correct — --resume causes full cache
miss since v2.1.69 per the Ghidra reverse-engineering report.

**Chat switching:** Each tab/window switch can invalidate the prompt cache. Our multi-chat setup
(3 chats) means we're taking cache hits on every switch. Mitigation: minimize switching, let
each chat run its full task before context-switching.

**Recommended env vars for .zshrc:**
```
export CLAUDE_CODE_DISABLE_1M_CONTEXT=1  # already present
export ENABLE_TOOL_SEARCH=false          # ADD THIS — prevents cache invalidation on tool load
```

**What we CAN'T mitigate:** Bug #1 (standalone binary CCH mutation) requires an Anthropic fix.
We're on the affected installation type. No user-side workaround exists.

## S236 /CCA-WRAP TOKEN AUDIT

**Command file size:** 612 lines, ~22KB, ~5,517 tokens loaded into context on every /cca-wrap.
**cca-init for comparison:** 332 lines, ~11.5KB, ~2,883 tokens. Combined lifecycle: ~8,400 tokens.

**Execution cost breakdown:**
- CRITICAL PATH (Steps 0.5, 1, 2.5, 3-5, 6-SLIM, 6i, 9, 10): ~2,100 tokens
- OPTIONAL STEPS (all others): ~13,150 tokens
- FULL WRAP EXECUTION: ~15,250 tokens
- TOTAL (file + execution): ~20,767 tokens per wrap

**Quick win IMPLEMENTED (S236):**
- Removed Step 6g (/arewedone skill load): saves ~3,000 tokens per wrap. This step loaded
  an entire skill command just for a structural status check — not worth it during wrap.

**PROPOSED optimizations for future sessions (not implemented — >20 LOC each):**
1. **Trim command file comments/docs** (~30% reduction = ~1,650 tokens saved)
   - Move step explanations to a separate WRAP_REFERENCE.md
   - Keep only the code blocks and one-line descriptions in the command file
   - Est: 1 session to rewrite

2. **Consolidate Steps 6b-6h into batch_wrap_analysis.py** (~5,000 tokens saved)
   - Currently 7 separate optional steps, each with its own bash call and context overhead
   - A single script could run reflect, escalate, validate, and evolve in one subprocess
   - Est: 1 session to build + test

3. **Default to SLIM wrap** (already partially done, but command still includes FULL instructions)
   - Remove full mode instructions from command file, keep only in separate reference
   - SLIM mode covers 90% of wraps; full mode instructions burn tokens even when skipped

4. **Make Step 7.5 (cross-chat) conditional on changes**
   - Currently always runs. Could skip if session had no Kalshi-relevant work.
   - Est: 5 LOC conditional check

**Bottom line:** Current wrap costs ~20K tokens. Critical path alone is ~7,600 tokens
(file + execution). Proposed optimizations could cut total to ~10-12K tokens — a 40-50% reduction.

## S236 RATE LIMITS STATUSLINE FINDINGS

**Status: ALREADY CONFIGURED.** cship (Mach-O binary at ~/.local/bin/cship) is installed and
configured in ~/.config/cship.toml with usage_limits module on line 2 of the statusline display.

**Current config (cship.toml):**
- Line 1: model name + cost + lines added/removed
- Line 2: context bar (10-char width) + usage limits (5h% + 7d%)
- Warning thresholds: 70% yellow, 90% red (both 5hr and 7day windows)
- TTL: 60s (rate limit data refreshes every minute)

**Note:** rate_limits data only appears after the first API response in a session.
In fresh sessions, the usage_limits section will be blank until the first tool call completes.
This is expected behavior — cship handles the missing data gracefully.

**No changes needed.** The feature was already active via cship before this investigation.

---

## SESSION RULES (Matthew directive, S178 — still active)
- **THIS FILE IS AUTHORITATIVE.** All CCA sessions work on TODO items here until complete.
- Do NOT use priority_picker or MASTER_TASKS until ALL TODOs here are done.
- Kalshi bot tasks: deliver via CCA_TO_POLYBOT.md, don't implement in polybot directly.
- Mark items [DONE SN] as they complete, but NEVER remove them
- Each subsequent CCA chat reads THIS FILE FIRST to know what to work on
- Matthew updates this file daily — follow it, don't second-guess it
- **STOP CONDITIONS are boundaries, not suggestions.** When a stop condition is hit, MOVE ON.
- **Do NOT engage in autoloop or autowork unless Matthew explicitly requests it.**
