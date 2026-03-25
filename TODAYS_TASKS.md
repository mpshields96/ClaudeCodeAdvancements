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

### C1. MT-26 Dead Code Cleanup [TODO]
- 2,110 LOC of unused signal pipeline in self-learning/
- S176 evaluation flagged: regime_detector, calibration_bias, cross_platform_signal,
  dynamic_kelly, macro_regime, fear_greed_filter, signal_pipeline — all unused by Kalshi bot
- Remove or wire into bot

### C2. Agent Teams/TeammateTool Awareness [TODO]
- BUILD verdict from S176 nuclear scan
- Official Anthropic multi-agent system uses worktree isolation
- CCA's agent-guard must handle TeammateTool conflicts + auto mode safety

### C3. memsearch Patterns [TODO]
- Study markdown-first hook patterns for CCA memory-system evolution
- REFERENCE from S176 nuclear scan

### C4. Context-Monitor 1M Recalibration [TODO]
- Update DEFAULT_WINDOW auto-detection for 1M context window

### C5. MT-37 UBER [TODO]
- Investment/AI trading master task

---

## COMPLETED TODAY (all sessions)

### S177 (current)
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

## SESSION RULES
- Autoloop ENABLED
- Mark items [DONE] as they complete, but NEVER remove them
- Each subsequent CCA chat reads THIS FILE to know what to work on
