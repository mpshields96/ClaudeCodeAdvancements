# MT-36 Phase 4: Kalshi Session Optimization Analysis

**Session:** S148 | **Date:** 2026-03-24

## Kalshi Session Structure (Current)

### Init (/polybot-init) — 256 lines, 4 steps
1. Read 5 context files (POLYBOT_INIT, SESSION_HANDOFF, CHANGELOG, PRINCIPLES, CHARTER)
2. Bot status check (ps, --health, --report)
3. Announce state (2-3 lines)
4. Route to work mode

**Assessment:** Already lean. No obvious fat to cut. The 5-file read is necessary for context.

### Auto (/polybot-auto) — 63 lines
- 5-min background monitoring loop
- Single DB query per cycle (6 fields)
- Restart on bot death, graduation watch, drought pivot

**Assessment:** Extremely efficient. The 5-min sleep + single DB query is near-optimal. The monitoring loop uses `run_in_background: true` correctly.

### Wrap (/polybot-wrap) — 136 lines, 5 steps
1. Bot health first (ps + --health + --report + --graduation-status)
2. Self-rating (grade + wins/losses)
3. Update 4 files (SESSION_HANDOFF, CHANGELOG, polybot-init, MEMORY.md)
4. Commit + push
5. Output next session prompt

**Assessment:** Already budget-aware ("costs ~5% of session budget"). The 4-file update is necessary. No redundant steps.

### Research wrap (/polybot-wrapresearch) — 126 lines
Similar to monitoring wrap but adapted for research sessions.

## Comparison: CCA vs Kalshi

| Metric | CCA Wrap | Kalshi Wrap |
|--------|----------|-------------|
| Lines | ~400+ (10 steps) | 136 (5 steps) |
| Files updated | 5 (SESSION_STATE, PROJECT_INDEX, CHANGELOG, LEARNINGS, journal) | 4 (SESSION_HANDOFF, CHANGELOG, polybot-init, MEMORY) |
| Self-learning | 11 subprocess calls (batch_wrap_learning.py reduces to 1) | None (bot self-learns via Bayesian model) |
| Tests run | Full suite (217 suites, ~2 min) | pytest -q (~30s) |
| Budget estimate | Was ~24K tokens, slim mode ~14K | ~5% of session budget |

## Findings

1. **Kalshi sessions are already efficient.** The wrap is 1/3 the size of CCA's. The monitoring loop is minimal (5-min sleep, single DB query). Init reads 5 files — all necessary.

2. **CCA was the bottleneck, not Kalshi.** MT-36 Phases 1-3 (session_timer, efficiency_analyzer, batch_wrap_learning) correctly targeted CCA overhead. The 47% deferrable tokens identified were in CCA wrap, not Kalshi.

3. **Cross-chat coordination is the shared overhead.** Both sessions spend time on:
   - Checking CCA_TO_POLYBOT.md / POLYBOT_TO_CCA.md (every 3rd Kalshi cycle)
   - Writing responses to cross-chat queue
   - This is useful overhead — it drives the Two Pillars strategy

4. **One potential Kalshi optimization:** The monitoring loop inline SQL query (40-char one-liner) could be extracted into a script. But the current approach works and avoids script file overhead.

## Recommendation

**MT-36 Phase 4 verdict: Kalshi sessions need no optimization.** The session structure is lean, budget-aware, and purpose-built. The monitoring loop is near-optimal. The wrap is efficient.

Focus remaining MT-36 effort on:
- Phase 5: Dashboard tracking of session efficiency metrics over time
- Continuing to optimize CCA sessions (the real overhead target)
