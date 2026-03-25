# CCA Tasks for 2026-03-25
# Created: S177. Read by ALL subsequent CCA chats today.
# This file persists across sessions so nothing gets forgotten.

---

## Priority Allocation (Matthew directive)
- **50%+ time on Kalshi bot work** (higher priority)
- Remaining time on CCA improvements
- Frequent comms with Kalshi main chat
- Peak/off-peak budgeting UNIVERSAL (MT-38)

---

## KALSHI BOT WORK (HIGH PRIORITY — 50%+)

### K1. MAX_LOSS + kelly_scale in sizing.py [DONE S177]
- REQ-042: DEFAULT_MAX_LOSS_USD=$7.50 cap, kelly_scale multiplier from BayesianDriftModel
- 25 new tests in test_sizing.py, 0 regressions (1902 polybot tests pass)
- Still need: wire into main.py call sites

### K2. Wire MAX_LOSS + kelly_scale into main.py [DONE S177]
- All 5 call sites wired. Commit 784bdc5 in polybot.
- Delivery written to CCA_TO_POLYBOT.md

### K3. CUSUM Drift Detection [DONE S176]
- Wired into auto_guard_discovery.py, 13 CCA tests
- cusum_statistic(), guards promoted when CUSUM S >= 5.0 AND n >= 15 AND WR < break-even

### K4. REQ-042 Tail Loss Audit [DONE S176]
- 95.6% losses > $5, avg loss = -$17.30, guard coverage 64.4%
- Post-guard profile: WR 97.2%, PnL/trade $0.70 (7x improvement)

### K5. Ongoing Cross-Chat Coordination
- Check POLYBOT_TO_CCA.md every cycle
- Write CCA_TO_POLYBOT.md deliveries promptly

---

## CCA IMPROVEMENTS

### C1. MT-26 Dead Code Cleanup [DONE S178]
- S178 assessment: NOT dead code. All 7 modules form a tested 7-stage signal pipeline
  (2,559 LOC, 256 passing tests). regime_detector→calibration_bias→cross_platform_signal→
  macro_regime→fear_greed_filter→order_flow_intel→dynamic_kelly. Modifiers compound multiplicatively.
- Correct framing: "wire into production" not "remove dead code"
- Action: Schedule MT-26 Phase 3 (production integration) when bot capacity allows

### C2. Agent Teams/TeammateTool Awareness [DONE S177]
- AG-10: worktree_guard.py (265 LOC, 29 tests)
- Worktree detection, delegate isolation, shared state protection, git safety
- Commit 8edadbc

### C3. memsearch Patterns [DONE S178]
- memsearch (Zilliz) validates CCA's hook-based memory architecture
- Key finding: Markdown + FTS5 hybrid storage is the pragmatic middle ground
- P0 (highest ROI): Add markdown export/import alongside FTS5 (~400 LOC, 0 deps)
- P1: Compaction-aware markdown snapshots (~150 LOC, integrates with post_compact.py)
- P2: Handoff markdown export for agent teams (~200 LOC)
- Implementation deferred until prioritized in MASTER_TASKS

### C4. Context-Monitor 1M Recalibration [DONE S177]
- DEFAULT_WINDOW 200K→1M across meter.py, post_compact.py, compact_anchor.py, statusline.py
- Commit 59c42ff

### C5. MT-37 UBER [DONE S178 — Phase 1 partial]
- MT37_RESEARCH.md created: 745 lines, areas 1-3 complete (MPT, Factor Models, Risk Parity)
- 15 papers synthesized, 7 more areas pending (momentum, behavioral, tax-loss, etc.)
- Commit 58eef2f. Remaining areas continue in future sessions.

---

## COMPLETED TODAY (all sessions)

### S178 (current)
- [x] AG-10 worktree_guard wired as live PreToolUse hook (13 new tests, 42 total)
- [x] Cross-chat delivery: post-guard clean bet counter + 95c guard consolidation
- [x] C4 already done in S177 (marked)
- [x] TODAYS_TASKS.md directive wired into all CCA session files (8 files, 5 new tests)
- [x] slim_init.py shows TODAY'S TASKS in briefing (scan_todays_tasks())
- [x] resume_generator.py adds TODAYS_TASKS.md reminder to autoloop prompts
- [x] C1: MT-26 assessment complete — NOT dead code, 7-stage pipeline (2,559 LOC, 256 tests). KEEP all.
- [x] C3: memsearch research complete — markdown+FTS5 hybrid is the evolution path (P0/P1/P2 defined)
- [x] C5: MT-37 Phase 1 partial — MT37_RESEARCH.md (745 lines, areas 1-3, 15 papers). Commit 58eef2f.

### S177
- [x] MAX_LOSS cap + kelly_scale in polybot sizing.py (25 tests)
- [x] Wire into main.py (commit 784bdc5, delivery written)

### S176 (Grade A)
- [x] Self-learning evaluation (CCA + Kalshi)
- [x] CUSUM drift detection in auto_guard_discovery.py (13 tests)
- [x] REQ-042 complete (tail loss audit + position sizing formula)
- [x] outcomes_enricher + predictive_recommender wired into slim_init (15 tests)
- [x] Nuclear scan: 10 findings, 60% APF (3 BUILD, 3 ADAPT, 4 REFERENCE)
- 5 commits, 28 new tests (9750 total)

### S175 (Grade A)
- [x] MT-49 Phase 5: outcomes_enricher, commit_scanner, ROI resolver

### S174 (Grade A)
- [x] REQ-042 fill_rate_simulator.py (30 tests)

### S173-S170
- [x] MT-49 Phases 2-5, MT-48 Phases 2-3

---

## SESSION RULES (Matthew directive, S178)
- **THIS FILE IS AUTHORITATIVE.** All CCA sessions work on TODO items here until complete.
- Do NOT use priority_picker or MASTER_TASKS until ALL TODOs here are done.
- Kalshi bot tasks: deliver via CCA_TO_POLYBOT.md, don't implement in polybot directly.
- Autoloop ENABLED
- Mark items [DONE SN] as they complete, but NEVER remove them
- Each subsequent CCA chat reads THIS FILE FIRST to know what to work on
- Matthew updates this file daily — follow it, don't second-guess it
