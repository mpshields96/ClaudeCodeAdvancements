# ClaudeCodeAdvancements — Session State
# Update at end of every session before closing.

---

## Current State (as of Session 128 — 2026-03-23)

**Phase:** Session 128 IN PROGRESS. Solo session. MT-30 Phase 8 — production hardening for autoloop.

**What was done this session (S128):**
- **Terminal.app close race condition FIXED**: Removed self-close from wrapper script (caused race with `exit`). Controller now waits 3s for shell to fully exit, uses `close w saving no`, handles "terminate?" dialog via System Events, retries close if window persists.
- **Pre-flight checks ADDED**: claude binary existence, Terminal.app running status, Accessibility permissions check, orphaned temp file cleanup from previous crashes.
- **Rate limit handling ADDED**: Exit codes 2 and 75 recognized as rate limits — get 5-minute extended cooldown instead of counting as crashes. No longer triggers 3-crash auto-stop.
- **Critical bug FIXED**: Python desktop wrapper was missing `--dangerously-skip-permissions` — would have blocked all automation with permission prompts.
- **Stale resume detection**: Logs when SESSION_RESUME.md unchanged between iterations (stuck loop diagnostic).
- **Prompt size truncation**: Resumes >100KB truncated to avoid CLI arg rejection.
- **Tests**: 204 suites passing. +31 new tests this session (85 → 116 in test_cca_autoloop.py).
- **Commits**: 3 this session so far.

**Next (prioritized):**
1. **Live supervised dry run**: Run `./start_autoloop.sh --desktop` with NO other CCA sessions running. Close THIS desktop app chat first.
2. **MT-0 Phase 2**: Deploy self-learning to Kalshi bot (requires Kalshi chat coordination).
3. **MT-31**: Build Flash-powered CCA tools now that Gemini Flash MCP is validated.

---

## Previous State (Session 126 — 2026-03-23)

**What was done this session (S126):**
- **MT-30 Phase 6 COMPLETE**: `cca_autoloop.py` — reads SESSION_RESUME.md, spawns claude with resume prompt + /cca-init + /cca-auto, loops on clean exit. 43 new tests. Safety: 3 consecutive crashes = stop, 3 short sessions = stop, max 50 iterations, 15s cooldown, audit logging.
- **start_autoloop.sh**: Bash loop runner that spawns claude in foreground (critical TTY fix — subprocess.run() doesn't give claude a real TTY). Supports `--tmux` mode for background operation.

---

## Previous State (Session 125 — 2026-03-23)

**What was done this session (S125):**
- **Gemini MCP E2E validated**: Flash works, Pro blocked (free tier, no API access). Matthew directive: Flash only. MT-31 scope narrowed.
- **MT-32: 2 new report charts**: `coverage_ratio` (tests/100 LOC per module), `hook_coverage` (hooks per lifecycle event). Both wired into Typst template. 16 new tests.
- **MT-0: deployment_verifier.py**: Validates self-learning integration in Kalshi bot — checks trading_journal.py, research_tracker.py, journal data, live.py wiring. CLI + programmatic. 24 new tests.
- **MT-26: signal pipeline E2E tests**: 30 scenarios (sniper bets, toxic contracts, chaotic regimes, graceful degradation, stability). 79 total pipeline tests. CCA scope effectively complete.
- **CCA_TO_POLYBOT bridge updated**: Was stale since S112 (13 sessions). Added MT-0 verifier, MT-33 report pipeline, MT-28 self-learning v2, actionable recommendations.
- **Doc drift fixed**: PROJECT_INDEX test counts (design-skills 1270->1299, usage-dashboard 369->384, total 8058->8001).
- **Priority picker updated**: MT-31 Flash-only, MT-26 near-complete, MT-32 last_touched.
- **Tests**: 203 suites, ~8040 tests passing. +70 new tests this session.
- **Commits**: 6 this session. Grade: A.

**Next (prioritized):**
1. **MT-0 Phase 2**: Run deployment verifier against real polybot. Coordinate with Kalshi chat to implement self-learning integration.
2. **MT-31**: Build Flash-powered CCA tools (code analysis, summarization).
3. **MT-32 continued**: Design system maturation (Pillar 7), dashboard enhancement (Pillar 6).
4. **Research ROI loop**: 46 deliveries with 0% implementation tracking — needs Kalshi chat action.

**What was done this session (S123):**
- **MT-33 Phase 6 COMPLETE**: `ReportSidecar` class in report_generator.py — saves JSON alongside every PDF, archives to `~/.cca-reports/{date}_S{session}.json`. Wired into main() pipeline automatically. `report_differ.py` (180 LOC) — structured diff between two report sidecars: test growth, LOC changes, MT transitions, Kalshi P&L, APF movement. `format_summary()` for human-readable trend text. 50 new tests (20 sidecar + 30 differ).
- **MT-33 hardening COMPLETE**: Edge case tests across all 3 collectors. kalshi_data_collector: +9, learning_data_collector: +11, report_differ: +10. Fixed format_summary detection logic.
- **MT-32 statistical charts**: 2 new CCA charts wired into /cca-report — `test_density_scatter` (ScatterPlot: tests vs LOC per module with trend line) and `module_composition` (StackedBarChart: source vs test LOC). Report now produces 9 base charts + conditional Kalshi/learning. 9 new tests.
- **MT-32 Typst wiring**: Both new charts placed in Module Deep-Dives section (2-column grid). Report now shows 19 charts total (9 base + 7 Kalshi + 3 learning).
- **Tests**: 201 suites, ~8058 tests passing. +188 new tests this session.
- **Commits**: 8 this session. Grade: A.

**Next (prioritized):**
1. **MT-32 continued**: More CCA statistical charts (per-file test distribution HistogramChart needs per-file data collector).
2. **Gemini Pro visual adapter**: MT-31 x MT-32 integration.
3. **MT-0 Phase 2**: Deploy self-learning to Kalshi bot.

**What was done this session (S122):**
- **MT-33 Phases 1-5 COMPLETE**: Full Strategic Intelligence Report pipeline. Mapped polybot.db schema, built kalshi_data_collector.py (265 LOC, 39 tests), wired 7 Kalshi charts into report_charts.py, Kalshi Financial Analytics page in Typst template, learning_data_collector.py (180 LOC, 18 tests), Self-Learning Intelligence section. Report: 17 SVG charts, 415 KB PDF.
- **Tests**: 199 suites, ~7870 tests passing. +70 new tests.
- **Commits**: 5 this session.

**What was done this session (S121):**
- **Session orchestrator live test PASSED**: register/set-mode/plan/status all work correctly. Orchestrator detects desktop running, recommends worker launch in 2chat mode.
- **ScatterPlot** (chart type 18): Multi-series XY correlation, optional least-squares trend lines, legend for multi-series, custom colors/point radius. 21 tests.
- **BoxPlot** (chart type 19): Box-and-whisker distribution comparison. Median, Q1/Q3, whisker caps, 1.5*IQR outlier detection as open circles. Custom colors. 21 tests.
- **HistogramChart** (chart type 20): Frequency distribution from raw values. Auto-binning via Sturges' rule or explicit bin count. Contiguous bars, bin edge labels. 25 tests.
- **ViolinPlot** (chart type 21): KDE-based distribution shape with mirrored Gaussian kernel density, embedded Q1/Q3 dashed lines, bold median line. Silverman's bandwidth. Handles bimodal/uniform/degenerate. 23 tests.
- **MT-33 created**: Strategic Intelligence Report — transform /cca-report into Kalshi analytics + self-learning + research pipeline artifact. 6 pillars, multi-session. Matthew S121 directive.
- **MT-34 logged**: Medical AI Tool (OpenEvidence replacement for PGY-3 Psychiatry). IDEA stage — Matthew refining concept.
- **Tests**: 197 suites, 7800 tests passing (was 194 suites). +90 new tests.
- **Commits**: 6 this session.

**Next (prioritized):**
1. **MT-33 Phase 1**: Deep dive research — map Kalshi DB schema, identify available metrics, design chart-to-data mappings.
2. **MT-32 continued**: Wire statistical charts into /cca-report (test distribution BoxPlot, session duration HistogramChart).
3. **Gemini Pro visual adapter**: MT-31 x MT-32 integration.
4. **MT-0 Phase 2**: Deploy self-learning to Kalshi bot.

**What was done this session (S119):**
- **Polybot queue hook E2E verified**: Simulated Kalshi main receiving CCA task assignments via cross_chat_queue.jsonl. Hook returns additionalContext with unread messages. Cleaned stale MT-0 task and test ping from km queue. The 3-chat coordination pipeline is functionally wired.
- **SankeyChart** (chart_generator.py): Flow diagram visualization — topological node ordering via BFS, cubic bezier flow bands with proportional thickness, custom node colors, multi-stage support (A->B->C). 25 tests. 16 chart types total.
- **Worker cli1 launched**: Assigned MT-32 svg.py evaluation + FunnelChart. Worker crashed before completing either task — no commits from worker. Tasks carry forward.
- **Tests**: 7611 passing (191 suites). +25 new tests (SankeyChart).
- **Commits**: 1 desktop (SankeyChart).

**Next (prioritized):**
1. **MT-32 Phase 2**: Evaluate svg.py (zero-dep SVG lib) as chart_generator.py foundation. Evaluate CeTZ-Plot for native Typst charts. Do this as desktop task, not worker.
2. **FunnelChart**: Build conversion funnel chart type (wide-to-narrow trapezoids). Was queued for worker but not completed.
3. **Gemini Pro visual adapter**: MT-31 x MT-32 integration.
4. **3-chat full loop**: polybot-auto must support task-driven work. Test with manual task assignment.
5. **MT-0 Phase 2**: Deploy self-learning to Kalshi bot.

**What was done this session (S118):**
- **MT-32 created**: "Visual Excellence & Design Engineering" — comprehensive 8-pillar MT covering ALL visual work (report generation, UI development, graphic design, data visualization, figure generation, dashboard enhancement, design system maturation, presentation design). Absorbs MT-24 and MT-25.
- **report_charts.py wired into /cca-report**: Auto-generates 6 SVG charts during PDF generation. Charts embedded via Typst `image()` in 4 report sections (module tests, frontiers, master tasks, intelligence). PDF with charts: 331 KB. Backwards compatible — works without charts too. +5 tests.
- **BubbleChart + TreemapChart**: 2 new chart types added to chart_generator.py. Bubble: scatter with sized circles for 3D data. Treemap: nested rectangles for hierarchical data. 32 tests. 14 chart types total.
- **Design token system**: Enhanced design-guide.md with explicit color tokens, spacing scale (8px base), typography scale, anti-AI-slop rules (no default purple, no generic cards, no verbose copy, no Tailwind defaults). Based on worker's nuclear scan findings.
- **3-chat coordination advances**: Updated /cca-auto-desktop coord round with Step 5d2 (Kalshi task management). Created KALSHI_TASK_CATALOG.md with 6 task categories for Kalshi main.
- **Worker cli1**: MT-32 Visual/Design Nuclear Scan — 14 findings across 5 subreddits + 8 GitHub repos. 5 BUILD/ADAPT, 7 REFERENCE, 2 SKIP. Top finds: svg.py (zero-dep SVG), CeTZ-Plot (native Typst charts), Altair (declarative). Key insight: "AI slop" = purple + Tailwind defaults; fix = design tokens.
- **Matthew directives saved**: (1) CCA may modify polybot settings if Kalshi main notified, (2) Kalshi runs as ONE chat (main+research combined), (3) Gemini Pro for visuals worth exploring.
- **Tests**: ~7618 passing (~192 suites). +37 new desktop tests + worker tests.
- **Commits**: 5 desktop + 1 worker = 6 total.

**Next (prioritized):**
1. **MT-32 Phase 2**: Act on nuclear scan findings — evaluate svg.py as chart_generator.py foundation (zero-dep, drop-in), evaluate CeTZ-Plot for native Typst charts (eliminate SVG intermediary).
2. **Wire queue_injector into polybot settings**: Matthew authorized CCA to modify polybot settings.local.json. Need to add UserPromptSubmit hook so Kalshi main receives CCA task assignments.
3. **Gemini Pro visual adapter**: MT-31 x MT-32 integration — build lightweight Gemini Pro MCP adapter for cross-model design review.
4. **3-chat full loop**: polybot-auto must support task-driven work (requires polybot-side changes). Test with manual task assignment first.
5. **MT-0 Phase 2**: Deploy self-learning to Kalshi bot (now possible via cca_comm.py task km + settings access).

**Key S117 insight**: Matthew correctly identified that Kalshi main running independently = NOT a 3-chat system. The cross-project routing in cca_comm.py is the foundation, but the full solution needs: (1) Kalshi main receiving and acting on tasks from CCA desktop, (2) /polybot-auto supporting task-driven work alongside monitoring, (3) CCA desktop coord round managing Kalshi task lifecycle.

**What was done this session (S116):**
- **3-CHAT TRIAL RUN #2: SUCCESS.** Desktop coordinator + CLI worker + Kalshi main. Worker completed StackedAreaChart (46 tests) + consistency audit tests (43 tests). Desktop built 5 new coordination tools. 8 desktop commits + 1 worker commit = 9 total. Key learning: fixed stale message clearing bug that prevented multi-task worker queuing.
- **handoff_generator.py**: Automated SESSION_HANDOFF file generation. Supports solo/2chat/3chat modes. Reads SESSION_STATE + git log. 50 tests.
- **launch_session.sh**: Unified multi-chat launcher with pre-flight safety checks (duplicates, peak hours, auth). 13 tests.
- **session_metrics.py**: Cross-session analytics aggregator (wrap_tracker + tip_tracker + apf data). Summary, growth, streaks. 55 tests.
- **coordination_dashboard.py**: At-a-glance multi-chat status (commits, worker state, peak hours). Full/compact/JSON modes. 22 tests.
- **cca_comm.py bug fix**: cmd_task() was clearing ALL unread messages from target inbox. Fixed to only clear >2h old messages. This was the root cause of workers only completing 1 task in S115 — queued tasks 2/3 were being eaten.
- **Chart font-size consistency fix**: Worker's audit tests found real inconsistency (some charts used 12, others 14 for "No data" text). Standardized to 14.
- **StackedAreaChart** (worker cli1): 9th chart type. Cumulative stacking, polygon-per-series, gradient fills, legend, label thinning. 46 tests.
- **test_chart_consistency.py** (worker cli1): 43 consistency audit tests across all 9 chart types.
- **Wired handoff_generator into /cca-wrap-desktop** (Step 9.9).
- **Tests**: 7333 passing (184 suites). +229 new tests this session.
- **Commits**: 9 this session (8 desktop + 1 worker).

**Chart types now available**: BarChart, HorizontalBarChart, LineChart, Sparkline, DonutChart, HeatmapChart, StackedBarChart, AreaChart, StackedAreaChart (9 total).

**Next (prioritized):**
1. **Kalshi bot maintenance** — Matthew's #1 priority.
2. **Design-skills continued expansion** — GroupedBarChart (worker task 2 was queued but worker wrapped before pickup), improved /cca-report using new chart types.
3. **Autonomous loop** (MT-22/MT-30) — CCA desktop auto-spawning new sessions.
4. **MT-0 Phase 2**: Deploy self-learning to Kalshi bot (requires Kalshi chat coordination).
5. **MT-31 Research**: Evaluate Gemini Pro as cross-model complement.

**Key S116 learning:** cca_comm.py `cmd_task()` was eating queued tasks by clearing ALL unread messages. Fixed with 2-hour threshold. This explains why S115 worker only completed 1 of 2 tasks. S117 multi-task queuing should work correctly now.

**Still pending (Matthew manual):**
- AUTH FIX: `sed -i '' 's/^export ANTHROPIC_API_KEY/# export ANTHROPIC_API_KEY/' ~/.zshrc`
- Bridge sync: `cp CCA_TO_POLYBOT.md ../polymarket-bot/CCA_TO_POLYBOT.md`

**What was done this session (S115):**
- **3-CHAT TRIAL RUN: SUCCESS.** Desktop coordinator + CLI worker + Kalshi main all ran without errors, scope conflicts, or interference. Worker launched, received task, executed (42 tests), committed, reported back, wrapped. Clean coordination throughout.
- **MT-27 Phase 5 COMPLETE**: `apf_session_tracker.py` — per-session APF trend tracking. Append-only JSONL snapshots at `~/.cca-apf-snapshots.jsonl`. Wired into `/cca-wrap` (Step 1.8) and `/cca-wrap-desktop` (Step 2.8). 27 tests.
- **StackedBarChart**: New chart type in `chart_generator.py` — stacked vertical bars for composition comparison (BUILD/ADAPT/SKIP per session). Legends, value labels, y-axis labels. 25 tests.
- **AreaChart**: New chart type — line with gradient fill below for volume/magnitude over time. Fill opacity, data points, label thinning. 29 tests.
- **HeatmapChart** (worker cli1): 2D colored grid for correlation/intensity data. `_lerp_color()` interpolation, contrast-aware value text. 42 tests. Committed by worker.
- **MT-31 added**: Gemini Pro Integration (Matthew has access via Google One $20/mo). Future research task.
- **Matthew priorities saved**: Kalshi bot > visuals/design > autonomous loop. All multi-session.
- **Doc drift fixed**: design-skills 534->630, self-learning 1752->1779, total 6981->7104.
- **Tests**: ~7104 passing (~178 suites). +123 new tests this session (27+25+29+42).
- **Commits**: 8 this session (7 desktop + 1 worker).

**Chart types now available**: BarChart, HorizontalBarChart, LineChart, Sparkline, DonutChart, HeatmapChart, StackedBarChart, AreaChart (8 total).

**Next (prioritized):**
1. **Kalshi bot maintenance** — Matthew's #1 priority.
2. **Design-skills continued expansion** — test growth timeline chart, APF trend sparkline in reports, improved /cca-report using new chart types.
3. **Autonomous loop** (MT-22/MT-30) — CCA desktop auto-spawning new sessions.
4. **MT-0 Phase 2**: Deploy self-learning to Kalshi bot (requires Kalshi chat coordination).
5. **MT-31 Research**: Evaluate Gemini Pro as cross-model complement.

**Still pending (Matthew manual):**
- AUTH FIX: `sed -i '' 's/^export ANTHROPIC_API_KEY/# export ANTHROPIC_API_KEY/' ~/.zshrc`
- Bridge sync: `cp CCA_TO_POLYBOT.md ../polymarket-bot/CCA_TO_POLYBOT.md`

**What was done this session (S114):**
- **MT-27 Phase 1 COMPLETE**: APF analysis — "Other" category dropped from 124/335 (37%) to 0/335 (0%). Expanded FRONTIER_PATTERNS from 8 to 15 categories with case-insensitive matching. 10 new tests.
- **MT-27 Phase 2 COMPLETE**: classify_post HAY expansion — 28 new sentiment/opinion HAY keywords (vibe coded, changed my life, model announcements, outage, team morale, etc.). 17 new tests. No false positives on technical posts.
- **MT-27 Phase 3 COMPLETE**: apf_checkpoint() compact one-liner function. Wired into autonomous_scanner.py ScanReport.summary(). CLI `checkpoint` command added. 6 new tests.
- **MT-29 Research COMPLETE**: Cowork/Pro Bridge — verdict SKIP. Cowork adds no value over our hivemind for dev workflows. No Pro↔Code bridge exists. Local MCP bugs (GitHub #23424). MT29_COWORK_RESEARCH.md written.
- **Doc drift fixes**: All module test counts in PROJECT_INDEX + ROADMAP updated to actuals. doc_drift_checker.py bug fixed (missed root-level test files, -74 undercount).
- **APF in self-learning/CLAUDE.md corrected**: 32.1% -> 22.7%.
- **Tests**: ~6981 passing (~174 suites). +33 new tests this session.
- **Commits**: 9 this session.

**Next (prioritized):**
1. **Bridge sync**: Matthew should run `cp CCA_TO_POLYBOT.md ../polymarket-bot/CCA_TO_POLYBOT.md`.
2. **AUTH FIX still pending**: Matthew must run `sed -i '' 's/^export ANTHROPIC_API_KEY/# export ANTHROPIC_API_KEY/' ~/.zshrc`.
3. **MT-0 Phase 2**: Deploy self-learning to Kalshi bot (requires Kalshi chat coordination).
4. **MT-26 Tier 3 Phase 2**: Full Kalman + EM + B-spline surface (needs numpy). Only after Phase 1 proves useful.
5. **MT-27 Phase 4**: NEEDLE precision improvement (diminishing returns — defer unless APF stalls).
6. **MT-27 Phase 5**: APF trend tracking per session.

**What was done this session (S112):**
- **MT-30 Phase 3: Session Daemon Core** (`session_daemon.py`): Poll loop, health checking, spawn/restart logic, peak hours enforcement, audit logging, PID file singleton, CLI interface. Integrates with session_registry + tmux_manager from Phase 2. 45 tests. Matthew directive: remaining Phase 4-5 (integration testing, hardening) spread over future sessions.
- **MT-26 Tier 3: Order Flow Intelligence** (`order_flow_intel.py`): FeeCalculator, FLBEstimator (OLS with category-specific psi coefficients from UCD WP2025_19), ReturnForecaster, RiskClassifier (TOXIC/UNFAVORABLE/NEUTRAL/FAVORABLE), BiasTracker, MakerTakerAnalyzer (Equation 6 maker pricing model). Stdlib only, 38 tests.
- **MT-26 Tier 3: Belief Volatility Surface Phase 1** (`belief_vol_surface.py`): LogitTransform (p <-> log-odds), BeliefGreeks (Delta_x, Gamma_x, belief-vega, martingale drift), RealizedVolEstimator (rolling vol from price history). Based on arXiv:2510.15205. Stdlib only, 27 tests.
- **MT-26 Tier 3 Design Doc** (`MT26_TIER3_DESIGN.md`): Full paper analysis for both Tier 3 modules with implementation plan.
- **Pipeline Integration**: order_flow_risk wired as Stage 6 in signal_pipeline.py (now 7-stage). TOXIC contracts get modifier=0.0 (hard SKIP). market_category field added to PipelineInput.
- **Bridge Updated**: CCA_TO_POLYBOT.md with Tier 3 intel, 5 actionable recommendations, code examples, pipeline guide.
- **Doc Drift Fixed**: PROJECT_INDEX test count (6880/172), MASTER_TASKS MT-24/MT-26/MT-30 statuses.
- **Kalshi main chat launched** via launch_kalshi.sh at 7:31 PM CDT (Matthew-authorized).
- **MT-23 EXTERNALLY RESOLVED**: Claude Code Channels shipped 2026-03-20. Native Telegram + Discord MCP channel servers. Two-way chat from phone, permission approval, sender gating. INSTALL_CHANNELS.md written with copy-paste setup steps.
- **StopFailure hook** (`context-monitor/hooks/stop_failure.py`): Handles CC v2.1.78+ StopFailure event. Classifies errors (rate_limit/auth/server), updates state file, logs to journal. 15 tests.
- **CC March features tracked**: rate_limits statusline, StopFailure hook, effort frontmatter, Channels, MCP elicitation — saved to memory.
- **Doc drift fixed**: design-skills test count (493->534), PROJECT_INDEX totals.
- **Statusline rate limit display**: Added RL:XX% to statusline using CC v2.1.80+ rate_limits field.
- **Tests**: ~6895 passing (~173 suites). Up from 6770/169. +125 new tests.
- **Commits**: 19 this session. Grade: A.

**Next (prioritized):**
1. **Bridge sync**: Matthew should run `cp CCA_TO_POLYBOT.md ../polymarket-bot/CCA_TO_POLYBOT.md` (now ~52K with Tier 3 intel).
2. **AUTH FIX still pending**: Matthew must run `sed -i '' 's/^export ANTHROPIC_API_KEY/# export ANTHROPIC_API_KEY/' ~/.zshrc`.
3. **MT-30 Phase 4**: Integration testing (dry run with 2 sessions). Multi-session per Matthew directive.
4. **MT-30 Phase 5**: Hardening (max restart limits, SIGTERM, PID file, log rotation).
5. **MT-26 Tier 3 Phase 2**: Full Kalman + EM + B-spline surface (needs numpy). Only after Phase 1 proves useful.
6. **MT-0 Phase 2**: Deploy self-learning to Kalshi bot (requires Kalshi chat coordination).
7. **MT-23**: Mobile remote control research (Telegram/Discord MCP evaluation).

**What was done this session (S109):**

**What was done this session (S108):**
- **Launch scripts fixed**: Replaced fragile AppleScript `keystroke "t"` + `front window` with `open -a Terminal` + temp script approach. Eliminates -1719 "Invalid index" errors. Added `bash launch_kalshi.sh both` convenience mode.
- **FIX_API_AUTH.md**: Documented root cause of API billing issue (ANTHROPIC_API_KEY export in ~/.zshrc) and 2-line fix. Matthew needs to run this.
- **MT-28 Phase 2 COMPLETE**: Pattern plugin registry for self-learning. Extracted 11 monolithic detectors from reflect.py into pluggable `@register_detector` architecture. New files: `pattern_registry.py` (registry + base class), `detectors.py` (11 built-in detectors). 42 new tests. Full backwards compatibility — all 124 existing reflect tests pass.
- **MT-26 Phase 1 started**: `regime_detector.py` — market regime classifier (TRENDING/MEAN_REVERTING/CHAOTIC/UNKNOWN). Uses volatility (log returns), trend strength (R-squared), mean reversion (Hurst exponent). 21 new tests. Zero external deps. Ready for Kalshi bot integration.
- **Tests**: 6304 passing (156 suites). Up from 6167/153.

**What was done this session (S107):**
- **Gameplan Phase 1 DONE**: Root cause found (ANTHROPIC_API_KEY env var in shell profile). Fix: `unset ANTHROPIC_API_KEY` in both launch_worker.sh and launch_kalshi.sh. Committed 277d6e8.
- **Gameplan Phase 2 DONE**: Bridge audit — CCA_TO_POLYBOT.md stale in polybot (9.2K vs 47.7K). POLYBOT_TO_CCA.md doesn't exist. BRIDGE_PROTOCOL.md created with format + dry run checklist.
- **Gameplan Phase 3 DONE**: Safety checklist — bot at Stage 1 ($5/bet), kill switch at 8 consecutive, emergency procedures documented, Matthew departure protocol added.
- **ORCHESTRATION_GAPS.md**: 6 gaps identified. 5 addressed this session (loop redesign, health check alias, bridge sync, peak hours, inbox in loop).
- **/cca-auto-desktop REDESIGNED**: Consolidated 4 scattered orchestration steps into single Coordination Round with 2-min time budget. COORD→WORK→COORD loop structure.
- **peak_hours.py**: Rate limit awareness utility (19 tests). Wired into both launch scripts.
- **test_reflect_principles.py**: 13 tests for MT-28 principle_registry integration path (was 0 tests).
- **crash_recovery.py**: Added `check` CLI alias for coordination round.
- **Bridge sync step**: Added to /cca-wrap-desktop (Step 2.6).
- **KALSHI_QUEUE_SETUP.md**: Documented how to wire queue_hook into polybot settings.
- **Doc drift fixed**: All 9 module test counts in PROJECT_INDEX.md updated from actuals.
- **MT-23 update**: Telegram reinstated as option (Matthew reversed S104 deprecation).
- **Memories saved**: 3 feedback (3-chat correctness, peak hours, daytime betting), 1 project (MT-23), 1 reference (tengu_onyx_plover feature flag).

**Matthew directives (S107, all prior permanent directives still active):**
- 3-chat correctness BEFORE speed. Multi-session timeline fine. Don't rush.
- Peak hours: watch token usage, no expensive agent spawns
- Bot: turn off if Matthew says leaving/shutting down. Small bets. Don't chase losses.
- Telegram is back as option for MT-23 (reversed S104)
- API budget: don't add $5 for CLI chats — fix is to unset the env var, not add money

**Next (prioritized):**
1. **VERIFY AUTH**: Matthew must launch a test terminal chat to confirm `unset ANTHROPIC_API_KEY` fix works. Can't progress to Phase 4 without this.
2. **Bridge sync**: Matthew should run `cp CCA_TO_POLYBOT.md ../polymarket-bot/CCA_TO_POLYBOT.md` to update stale copy.
3. **Kalshi queue wiring**: Apply KALSHI_QUEUE_SETUP.md to polymarket-bot settings.local.json.
4. **Gameplan Phase 4**: Dry run — launch all 3 chats, test round-trip bridge communication.
5. **MT-28 Phase 2**: Pattern plugin registry (reflect.py detectors). Multi-session.
6. **MT-26 Phase 1**: Build financial intelligence tools from MT26_FINANCIAL_INTEL_RESEARCH.md.

**Matthew directives (S106, all S105 permanent directives still active):**
- 3-chat system still THE priority — but DON'T RUSH. Verify infrastructure first.
- Previous chat (S105) was sloppy/expensive. Approach with hazmat suit.
- Small bets only. Turn bot off before wrapping. PERMANENT.
- Keep comms simple: bridge file cross-project, cca_comm.py internal only
- Use Kalshi RESEARCH chat (not main) when ready

**Next (prioritized):**
1. **Kalshi prep**: Verify bridge round-trip works end-to-end OFFLINE before live launch.
2. **Kalshi prep**: Fix launch_kalshi.sh to ensure Max subscription auth (not API credits).
3. **Kalshi prep**: Create integration checklist — what must be true before 3-chat is safe.
4. **Worker check**: Did cli1 fix CSS bug? Check git log.
5. **MT-28 Phase 2**: Pattern plugin registry (reflect.py detectors). Multi-session.
6. **MT-26 Phase 1**: Build financial intelligence tools from research doc.
3. **MT-26 Phase 1**: Use MT26_FINANCIAL_INTEL_RESEARCH.md to begin building financial intelligence tools.
4. **Worker fix**: website_generator_extended.py + dashboard_generator_extended.py CSS class bug.
5. **Paper digest spam**: Worker may or may not have completed the debounce fix. Check git log.

**What was done this session (S104):**
- **MT-23 Phase 2 COMPLETE**: Direction change (Matthew S103 explicit) — Remote Control is PRIMARY mobile path, Discord is SECONDARY, Telegram deprecated. MT23_MOBILE_RESEARCH.md fully rewritten. GitHub issue #28402 (reconnection broken, 17+ confirmations) identified as key gap for hop-on/hop-off. 6 CCA enhancement opportunities documented.
- **INSTALL_DISCORD_CHANNELS.md**: New ADHD-friendly copy-paste steps for Discord as secondary notification channel.
- **MT-28 Phase 1 COMPLETE**: Self-Learning v2 research. Two parallel agents (web research + codebase audit). MT28_SELF_LEARNING_V2_RESEARCH.md with 6-phase implementation plan. Key patterns: EvolveR principle scoring (Laplace-smoothed), pattern plugin registry, research outcomes feedback loop. 10 architectural gaps identified in current self-learning module.
- **Priority system overhauled**: MT-0 (Kalshi self-learning) added to priority_picker.py (was missing!) at base=10. MT-28 base=10, MT-26 base=9 (financial focus). MT-23 lowered to 5. Session counter updated to 104. 55 tests pass.
- **KALSHI_MT0_TASK_BRIEF.md**: Complete autonomous task brief for deploying self-learning to Kalshi bot (MT-0 Phase 2). 4 tasks: trading_journal.py, research_tracker.py, return channel, pattern summary.
- **Cross-chat coordination validated**: Bidirectional CCA<->KM queue tested, stale messages cleared. Kalshi chat launch attempted via AppleScript but failed to produce working session.
- **Cross-chat Requests 5+9**: Confirmed already answered in CCA_TO_POLYBOT.md (feature importance + non-stationarity). Will be picked up by next Kalshi chat.
- **Worker (cli1)**: Assigned paper digest spam fix + test coverage. Worker status unknown (terminal closed mid-session).

**Matthew directives (S104, permanent):**
- MT priority shift: self-learning + financial research > all other MTs
- MT-0 Phase 2 is THE #1 priority — deploy self-learning to Kalshi bot
- Remote Control is PRIMARY mobile path (not Telegram)
- 3-chat max on Max 5x plan; 4 chats too risky for rate limits
- Full authorization to launch Kalshi bot chats from CCA desktop
- CCA hivemind coordination extends cross-project (CCA desktop guides Kalshi chat)

**CAUTION**: S104 ran deep into context. Next session MUST verify all S104 changes are correct — priority_picker.py edits, MT23 research doc accuracy, MT28 research doc citations. High-context sessions produce more errors.

**Next (prioritized):**
1. **MT-0 Phase 2**: Launch Kalshi chat with KALSHI_MT0_TASK_BRIEF.md — deploy self-learning to bot. VERIFY the terminal launch actually works this time.
2. **MT-26 (Financial Intel Engine)**: Research agent was launched S104 but results didn't land. Re-run or check output.
3. **Paper digest spam**: Worker may not have completed fix. Check git log for debounce commit.
4. **MT-28 Phase 2**: Begin implementation — principle registry (Phase 1 of 6-phase plan in MT28 doc).
5. MT-25 BLOCKED: waiting on Matthew's presentation style samples.

**What was done this session (S98):**
- **priority_picker.py built** — 55 tests. Improved MT priority formula: completion bonus, ROI estimate, stagnation penalty. CLI interface for autonomous task selection. Wired into /cca-auto-desktop Step 2.
- **MASTER_TASKS.md priority system rewritten** — documents improved formula, CLI commands, stagnation flagging, blocked task re-evaluation.
- **MT-1 Claude Control evaluated** — active dev (last commit 2026-03-20), DMG install, auto-discovers Claude processes. INSTALL_CLAUDE_CONTROL.md written with explicit step-by-step instructions.
- **init_cache.py built** — 21 tests. Fast session startup via test caching. Smoke test (10 critical suites, ~15s) replaces full suite at init. Cache written at wrap.
- **test_validate.py** — 47 tests for spec-system/hooks/validate.py (was 316 LOC, 0 tests)
- **test_doc_drift_checker.py** — 55 tests for usage-dashboard/doc_drift_checker.py (was 488 LOC, 0 tests). Fixed tilde parsing bug.
- **MT-12 Phase 3** — Paper scanner ran across agents, prediction, statistics, context_management domains. Agents/context strongest. Mem0 paper found (198 citations, long-term memory for AI agents).
- **Daily intelligence scan** — OpenWolf ADAPT finding (80% token reduction via file anatomy indexing, 62pts). Claude Control developer posted their own tool (#10 on r/ClaudeCode).
- **Worker (cli1)**: Built test_cca_hivemind.py (71 tests), test_generate_report_pdf.py (49 tests), test_report_generator_extended.py (in progress).
- **Feedback saved**: simple explicit instructions to file (ADHD-friendly, copy-pasteable steps)

**Matthew directives (S51-S98, permanent):**
- All S51-S97 directives still active
- S98: When giving instructions, write to a file with simplest explicit steps
- S98: Worker should target 45-60 minutes productive work (excluding startup/wrap)
- S98: Compaction discussion — clean wrap preferred over compaction for heavy-rules projects

**Next (prioritized):**
1. Install Claude Control: open INSTALL_CLAUDE_CONTROL.md and follow steps (Matthew manual)
2. GitHub push still blocked: PAT needs `workflow` scope
3. MT-22 Trial #3 counts as S98 (supervised). Need to confirm pass in next session.
4. OpenWolf anatomy.md concept — adapt for context-monitor (reduce redundant reads)
5. MT-18/MT-13 stagnating — need decision: work, reduce base_value, or archive
6. Worker tasks 4+5 may need re-queuing if worker didn't complete them

---

## What Was Done in Session 97 (2026-03-21)

- MT-10 Phase 3A COMPLETE — trading_analysis_runner.py for real Kalshi schema
- strategy_health_scorer.py built — 200 LOC, 24 tests
- Paper/live trade separation
- 3 MTs graduated (MT-9, MT-10, MT-17)
- Worker: worker_task_tracker.py (26 tests)
- MT-22 Trial #2 observations

---

## What Was Done in Session 66 (2026-03-19)

1. plan_compliance.py built (SPEC-6, 38 tests)
2. spec_freshness wired into validate.py
3. journal.jsonl committed
