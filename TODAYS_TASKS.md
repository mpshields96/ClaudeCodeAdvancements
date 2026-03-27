# CCA Tasks for 2026-03-25
# Created: S177. Read by ALL subsequent CCA chats today.
# This file persists across sessions so nothing gets forgotten.

---

## Priority Allocation (Matthew directive)
- **50%+ time on Kalshi bot work** (higher priority)
- Remaining time on CCA improvements
- Frequent comms with Kalshi main chat
- Peak/off-peak budgeting UNIVERSAL (MT-38)

## IMPORTANT NOTES FOR ALL CCA CHATS (Matthew directive, S179)
- **TOKEN BUDGET:** We are in OFF-PEAK hours = 100% budget. Agents OK but pace usage
  across the full remaining limit window (~3 hours). Do NOT burn 55% remaining tokens
  in the first 30 minutes. Spread work evenly.
- **"DONE" items below had PROGRESS MADE, not necessarily fully completed.** C5 MT-37 is
  only 3/10 areas done. Read the notes on each item carefully — "[DONE S178 — Phase 1 partial]"
  means partial, not complete. Continue unfinished work.

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

### C5. MT-37 UBER [DONE S180 — Phase 1 COMPLETE]
- MT37_RESEARCH.md: 1762 lines, all 10 areas complete, 42 papers synthesized
- S178: Areas 1-3 (MPT, Factor Models, Risk Parity) — 745 lines, 15 papers
- S179: Areas 4-7 (Momentum & Value, Behavioral Finance, TLH, Retirement) — +451 lines, +15 papers
- S180: Areas 8-10 (Kelly Criterion, Index Investing, Alt Risk Premia) — +578 lines, +12 papers
- Phase 1 COMPLETE. Next: Phase 2 (Architecture Design) when prioritized.

### C6. Nuclear Reddit/GitHub Discovery Tools [DONE S180]
- S179: subreddit_discoverer.py (25 tests), github discover command (16 tests)
- S180: Wired Phase 0 (Discovery) into both /cca-nuclear-daily and /cca-nuclear-github
- S180: Added r/modelcontextprotocol to profiles.py (S179 discovery finding)
- Both nuclear commands now run discovery before their main scan phase

---

## NEW TASKS (Matthew directive, S181 — The Expansion Directive)

### E1. MT-37 Phase 2: Architecture Design
- Phase 1 (research) is DONE but MT-37 has MUCH more to do
- Phase 2: Design the architecture for a wealth management intelligence system
- Use the 42-paper synthesis in MT37_RESEARCH.md as foundation
- This is not "done" — this is just getting started

### E2. C6 Expansion: Act on Intelligence Findings
- S181 scan found 3 BUILD-rated tools. Act on them:
- **Chart.js integration** into dashboard_generator.py for interactive dashboards (~200 LOC)
- **Visualization decision matrix** from OpenGenerativeUI pattern — auto-map data shape to chart type
- **CloudCLI UI evaluation** (8.9K stars) for MT-47 external tool pipeline

### E3. Ongoing Kalshi Cross-Chat
- Kalshi work is NEVER finished (Matthew explicit)
- Check POLYBOT_TO_CCA.md every cycle
- Proactively identify new edges, guard improvements, strategy enhancements
- Write deliveries without being asked

### E4. MT Expansion Audit
- Review completed/stalled MTs for expansion opportunities
- Don't be satisfied with "done" — ask "can this be better?"
- Use synthetic MT origination (mt_originator.py) to auto-propose new phases
- Use intelligence findings (FINDINGS_LOG.md BUILD items) to generate new work
- North stars: (1) make CCA smarter, (2) make Kalshi bot more profitable

### E5. Reddit Links Review [DONE S181]
- Matthew dropped 9 Reddit links — all reviewed with /cca-review verdicts
- 1 BUILD (Google Stitch design pipeline), 3 ADAPT, 3 REFERENCE, 1 REFERENCE-PERSONAL, 1 SKIP
- All verdicts written to FINDINGS_LOG.md

### E6. MT-50: Kalshi Copytrade Bot Research (S181b directive)
- Two paths: (a) copytrade top Kalshi bettors, (b) mirror Polymarket whales → bet on Kalshi
- Requires significant R&D: API access, account identification, market mapping, TOS compliance
- Logged as UBER-LEVEL MT-50 in MASTER_TASKS.md

### E7. MT-51: New Kalshi Market Expansion (S181b directive)
- Crypto is NOT the only profitable market — research new categories aggressively
- Weather, economic data, political events, company events, etc.
- Logged as MT-51 in MASTER_TASKS.md

### E8. MT-52: Nuclear Synthetic Origination (S181b directive)
- Nuclear scan tools should auto-propose MTs/phases from BUILD findings
- Extend mt_originator.py with intelligence-driven origination
- Logged as MT-52 in MASTER_TASKS.md

### E9. Typst Color Token Cleanup [DONE S182]
- 4 new semantic tokens (tint-warm, warm-border, warm-label, warm-body) + 8 orphan replacements
- Zero orphan hex values remain in template body

### E10. Kalshi Pending Requests — Political Markets Probe [DONE S184 — DEFERRED]
- POLYBOT_TO_CCA.md REQUEST 1: Probed KXPRES/KXELECTION/KXCONGRESS
- S184 verdict: NOT suitable for daily sniper (long-dated, capital locked)
- House 84c Dem, Senate toss-up — wrong structure for 15M sniper
- Deferred until bankroll > $500 and dedicated political strategy is designed

### E11. Kalshi Pending Requests — Overnight/Time-of-Day Research [DONE S182]
- POLYBOT_TO_CCA.md REQUEST 4 (OPEN/URGENT): Academic evidence for time-of-day crypto effects
- 3 verified papers delivered to CCA_TO_POLYBOT.md:
  (1) Brauneis et al 2024 (DOI:10.1007/s11156-024-01304-1): volatility/illiquidity peaks 16-17 UTC
  (2) Hansen et al 2024 (arXiv:2109.12142): systematic periodicity growing stronger
  (3) Amberdata: 87% depth variation, 03-05 UTC = deep liquidity trough
- Structural basis CONFIRMED for 08:xx block, KXSOL 03/05:xx blocks, overnight underperformance

### E12. MT-52 Phase 1: Build Synthetic Origination Engine [DONE S182]
- Built 3-source intelligence engine: ADAPT verdicts + stalled MTs + cross-chat requests
- New types: MTStatus, CrossChatRequest, OriginationReport
- 26 new tests, all pass. Live run: 56 actionable items found.
- CLI: `python3 mt_originator.py --unified`

### E13. Chart.js Interactive Dashboard Bridge [DONE S182]
- chartjs_bridge.py: converts CCA chart data into Chart.js config objects
- 4 chart types: bar, line, donut, stacked bar
- 21 new tests, all pass
- Built from S181 BUILD finding (intelligence-driven per MATTHEW_DIRECTIVES.md)

### E14. MT-37 Phase 2 Architecture Design [DONE S182]
- MT37_ARCHITECTURE.md: 10-module system design using 42-paper foundation
- 5 layers: Data Input → Construction → Sizing/Risk → Tax/Withdrawal → Output
- Advisory-only (no trade execution), BL+RP allocation, half-Kelly sizing
- ~2,550 LOC, ~260 tests estimated across Phases 3-12

### E15. MT Expansion Audit [DONE S182]
- Ran origination engine against live data: 56 actionable items
- 18 stalled MTs identified (3 blocked by externals, 3 superseded, 12 actionable)
- 3 ADAPT extensions for existing MTs (MT-0, MT-22)
- REQ-4 answered, REQ-8/9 queued for next session

### E16. Cross-Chat Deep Dive
- Ongoing — check POLYBOT_TO_CCA.md for all pending requests
- REQ-8 (multi-parameter loss analysis) and REQ-9 (non-stationarity) still URGENT
- REQ-10-25 need triage — many may be resolved or superseded by newer data

### E17. MT-53 Pokemon Autonomous Bot [IN PROGRESS S208-S209]
- S208: Cloned 4 reference repos, built memory_reader_red.py, agent_memory.py, expanded tools.py (4→10)
- S209: Fixed movement bug (SNES dialog was blocking input), verified PyBoy movement works
- **STILL TODO:** Boot automation script (name char, clear dialogs, exit Red House to Pallet Town)
- **STILL TODO:** Get viewer.html showing live gameplay
- **STILL TODO:** Port A* pathfinding from reference repos
- **STILL TODO:** Build Claude agent loop for Pokemon Red

---

## COMPLETED TODAY (all sessions)

### S179
- [x] Kalshi MAX_LOSS audit: all 11 loop functions verified safe, delivery written to CCA_TO_POLYBOT.md
- [x] subreddit_discoverer.py built (25 tests) — domain-based subreddit discovery
- [x] github_scanner.py discover command added (16 tests) — domain-based repo discovery
- [x] MT-37 areas 4-7 (Momentum, Behavioral, TLH, Retirement — 451 lines, 15 papers)
- [ ] MT-37 areas 8-10 (Kelly, Index, Alt Risk Premia — still pending)
- [ ] Wire discovery tools into nuclear scan pipelines

### S178
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
