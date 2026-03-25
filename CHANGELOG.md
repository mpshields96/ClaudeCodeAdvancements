# ClaudeCodeAdvancements — Changelog
# Append-only. Never truncate.

---

## Session 160 — 2026-03-25

**What changed:**
- `efficiency_dashboard.py` (NEW): MT-36 Phase 5 — self-contained HTML dashboard (28 tests)
- `priority_picker.py`: MT-39 COMPLETE (3/3) — growth_score, dust CLI, ARCHIVED status, 8 MTs archived, SCAN ALERT integration, MT-42 created
- `mt_originator.py` (NEW): MT-41 Phase 1 — synthetic MT origination from FINDINGS_LOG (22 tests)
- `scan_scheduler.py` (NEW): MT-40 Phase 1+2 — staleness policies + init briefing integration (17 tests)
- `~/.claude/cross-chat/CCA_TO_POLYBOT.md`: REQ-036 CLV tracking design delivered
- `FINDINGS_LOG.md`: 6 new entries (3 Reddit reviews + 6 MT-1 research findings)
- `LEARNINGS.md`: 4 new learnings (aging_rate blindspot, URL keyword matching, Claude Control, MT archival)
- 8 MTs archived per Matthew: MT-5,8,16,19,23,25,31,34
- MT-42 created: Kalshi Smart Money Copytrading (order flow analysis)

**Why:**
- Matthew directive: "LOG ALL OF THIS, make them MTs"
- 15+ MTs collecting dust — priority picker aging_rate=0 blindspot
- Synthetic MT origination and scan scheduling never built
- Kalshi copytrading idea from Matthew (follow smart money, not broadcast)
- CLV tracking requested by Kalshi chat (REQ-036)

**Tests:** 9,067/9,067 passing (227 suites). 11 commits.

**Lessons:**
- aging_rate=0 makes completed MTs invisible to dust detection — use growth_score with dust bonus
- Keyword matching must exclude URLs (github in URLs matched MT-11)
- Claude Control v0.10.0 exists and solves MT-1 — install DMG

---

## Session 159 — 2026-03-24

**What changed:**
- `token_budget.py`: Added `get_autoloop_settings()` API for peak-aware autoloop scheduling (MT-38 Phase 4)
- `cca_autoloop.py`: Integrated peak-aware cooldown + model override during PEAK hours
- `autoloop_trigger.py`: Added peak context logging to trigger audit trail
- `design-skills/report_generator.py`: Added ACTION items to all Honest Assessment criticisms, fixed research outcomes path, added WHY_IT_MATTERS for 20+ MTs
- `design-skills/templates/cca-report.typ`: Removed 5 fluff charts, enhanced Self-Learning section with big metrics + Research ROI pipeline, card-based Architecture Decisions, ACTION callout boxes in Honest Assessment
- `~/.claude/cross-chat/CCA_TO_POLYBOT.md`: REQ-034 (Monte Carlo integration) + REQ-035 (daily sniper analysis) responses

**Why:**
- Matthew feedback: report was "uninspired", charts were "fluff", honest assessment needed actionable items
- MT-38 Phase 4: autoloop should adjust behavior based on peak/off-peak hours
- Kalshi cross-chat: 2 pending requests needed responses

**Tests:** 8,959/8,959 passing (223 suites)

**Lessons:**
- Opus 4.6 and Opus 4.6 (1M context) are the same model — context window is the only difference
- When user says "simplest cleanest solution," propose the simplest option first

---

## Session 156 — 2026-03-24

**What changed:**
- `design-skills/templates/cca-report.typ`: Condensed active MT section (compact rows with progress bar + status one-liner) and pending MT section (one-line rows). Saves ~2 pages.
- `design-skills/chart_generator.py`: Integer Y-axis labels for bar, stacked area, grouped bar charts when all values are whole numbers.
- `design-skills/report_generator.py`: 5 fixes — priorities parser markdown format, dynamic Kalshi criticism from research outcomes, phase progress from Comp% column, test count extraction from task body, dynamic risk detection (blocked MTs, stagnation, severity-3 learnings).
- `cross_chat_queue.py`: 24h deduplication in `send_message()`. Cleaned 200 duplicate paper digest messages.
- `~/.claude/cross-chat/CCA_TO_POLYBOT.md`: 2 deliveries — REQ-027 status + 5 economics sniper questions answered.

**Why:**
- MT-32: Report was too verbose with 7+ active MTs. Chart axes showed decimals for integer data.
- MT-33: Report content had stale/inaccurate data (wrong phase progress, missing test counts, hardcoded risks).
- Cross-chat queue was polluted with 200 duplicate messages from paper digest automation.

**Tests:** 223/223 passing (8959 total)

**Lessons:**
- When user says "no /cca-wrap now" they mean "no [to continuing], run /cca-wrap now" — default to interpreting ambiguous negations as the user wanting to change course.

---

## Session 143 — 2026-03-23

**What changed:**
- MT-35 Phase 2: `get_user_idle_seconds()` and `wait_for_idle()` on DesktopAutomator using CoreGraphics `CGEventSourceSecondsSinceLastEventType`. Autoloop trigger waits 3s idle before stealing focus. Env-configurable (CCA_IDLE_THRESHOLD, CCA_IDLE_TIMEOUT). Fails open.
- KXBTCD threshold analysis written to `CCA_TO_POLYBOT.md`: Le (2026) arXiv:2602.19520 + Burgi/Deng/Whelan (2025) SSRN:5502658. Verdict: paper-trade first, crypto well-calibrated at short horizons.
- MT-35 Phase 1+2 marked COMPLETE in `MASTER_TASKS.md`.
- MT-36 created (Matthew directive): Session Efficiency Optimizer — measure/optimize init/wrap/coding time while maintaining quality.

**Why:**
- MT-35 Phase 2 makes autoloop non-intrusive per Matthew directive (S142)
- KXBTCD research responds to monitoring chat S130 request for second FLB edge assessment
- MT-36 addresses Matthew's request for systematic session efficiency optimization

**Tests:** 212/212 passing (+16 new: 12 desktop_automator, 4 autoloop_trigger)

**Lessons:**
- Le (2026) provides domain-specific calibration data that changes the KXBTCD calculus — crypto is well-calibrated at short horizons unlike politics/sports

---

## Session 138 — 2026-03-23

**What changed:**
- `desktop_autoloop.py`: Removed `_is_first_iteration` — Cmd+N now fires every iteration. Updated docstrings.
- `autoloop_trigger.py`: NEW — CCA-internal autoloop trigger. Activate Claude.app -> Code tab -> Cmd+N -> paste resume -> send. 155 LOC.
- `tests/test_autoloop_trigger.py`: NEW — 18 tests (success flow, each failure mode, step ordering, prompt content, audit logging).
- `tests/test_desktop_autoloop.py`: Updated 4 tests for always-Cmd+N behavior.
- `.claude/commands/cca-wrap.md`: Added Step 10 — autoloop trigger as final wrap action.
- `CLAUDE.md`: Added full "Desktop Autoloop Workflow" section (app layout, exact cycle steps, critical rules, implementation files, failure modes).

**Why:**
- S137 trial found `_is_first_iteration` bug causing prompt injection into wrong session
- Matthew directive: autoloop must be CCA-internal (triggered by /cca-wrap), not from Terminal.app
- Code tab detection still broken (Electron accessibility limitation) — trigger lands on Chat tab

**Tests:** 211/211 suites passing, 8544 total (+18 new)

**Lessons:**
- Electron apps don't expose tab groups to macOS accessibility tree — need alternative approach for tab detection
- CCA autoloop is session-internal (wrap triggers next session), not external (Terminal.app script)
- Always activate Claude.app before frontmost check — bash subprocess runs in Terminal context

---

## Session 137 — 2026-03-23

**What changed:**
- `session_outcome_tracker.py`: `format_init_briefing()` + `init-briefing` CLI. Planned task parser scoped to current section (63->4 items fix).
- `.claude/commands/cca-init.md`: Step 2.95 — session outcome insights at init.
- `.claude/commands/cca-wrap.md`: Step 9 now writes SESSION_RESUME.md to disk for autoloop.
- `desktop_automator.py`: `_run_applescript` dry_run returns plausible output. `ensure_code_tab` proceeds optimistically.
- `tests/test_desktop_automator.py`: Updated 4 tests for new behavior.
- `tests/test_session_outcome_analyzer.py`: +8 tests for format_init_briefing.

**Why:**
- Making desktop autoloop production-ready. First real trial revealed Electron accessibility limitation and critical first-iteration Cmd+N skip bug.

**Tests:** 8526/8526 passing (210 suites)

**Lessons:**
- Electron apps don't expose web UI to macOS accessibility APIs — tab detection via System Events impossible.
- Autoloop must ALWAYS Cmd+N on first iteration — it runs from external context, not an empty chat.
- Run trials immediately, fix from failures. Don't over-research before trying.

---

## Session 135 — 2026-03-23

**What changed:**
- `design-skills/tests/test_report_sidecar_standalone.py`: 54 tests for standalone report_sidecar.py (extract, save, load, find_latest, Kalshi/learning extraction, edge cases)
- `tests/test_desktop_autoloop.py`: +8 idle detection tests (exit code 2 path — extended idle, min_session_time, counter reset, file change priority, state tracking)
- `LEARNINGS.md`: 2 new entries — autoloop external terminal pattern, Claude desktop UI layout (3-tab system)
- `DESKTOP_AUTOLOOP_SETUP.md`: ASCII UI diagram, Code tab awareness, recovery pattern
- `PROJECT_INDEX.md` + `ROADMAP.md`: Doc drift fix (design-skills 1299->1353, total 8406->8468)

**Why:**
- Test coverage gaps from S134 needed filling (report_sidecar standalone, idle detection)
- Attempted desktop autoloop trial revealed critical pattern: script must run from external terminal
- Matthew's UI walkthrough provided essential knowledge for autoloop tab navigation

**Tests:** 210/210 suites passing (~8468 total)

**Lessons:**
- Never run the desktop autoloop orchestrator from within a Claude Code session
- Claude desktop app has 3 tabs (Chat/Cowork/Code) — autoloop must ensure Code tab is active
- Terminal Accessibility permission is permanently granted

---

## Session 129 — 2026-03-23

**What changed:**
- `reddit-intelligence/nuclear_fetcher.py`: MT-27 Phase 4 — split NEEDLE keywords into strong (always NEEDLE) and weak (need engagement signals: score >= 50 OR body >= 300 OR comments >= 15). Reduces false positives from broad keywords like "tool", "built", "made".
- `cca_autoloop.py`: Added `parse_audit_log()` for JSONL audit log parsing, `format_status_report()` for rich status output, `run_preflight_checks()` for standalone prerequisite verification. New `status` and `preflight` CLI commands.
- `AUTOLOOP_SETUP.md`: New file — step-by-step Accessibility permissions guide for macOS 15 Sequoia, preflight instructions, model strategy options.
- `PROJECT_INDEX.md` + `ROADMAP.md`: Fixed stale test counts (usage-dashboard, reddit-intelligence, self-learning, design-skills, totals).
- `priority_picker.py`: Updated MT-27 Phase 4 complete, current_session=129.
- `MASTER_TASKS.md`: Updated MT-30 status with S129 additions.

**Why:**
- MT-27 Phase 4: NEEDLE precision was flagged as stagnating (10 sessions). Broad keywords were generating too many false positives in nuclear scans.
- MT-30 enhancements: Matthew asked about Accessibility permissions for autoloop dry run. Added tooling to make the first dry run safe and well-documented.
- Doc drift: Test counts had accumulated drift across multiple sessions.

**Tests:** 8205/8205 passing (+55 new: 30 NEEDLE precision, 16 audit log, 9 preflight)

**Lessons:**
- None new this session — focused execution, no regressions.

---

## Session 125 — 2026-03-23

**What changed:**
- `design-skills/report_charts.py`: +2 chart methods (coverage_ratio, hook_coverage), wired into generate_all
- `design-skills/templates/cca-report.typ`: New charts in Module Deep-Dives + Live Infrastructure sections
- `self-learning/deployment_verifier.py`: NEW — MT-0 deployment validation (CLI + API)
- `self-learning/tests/test_signal_pipeline_e2e.py`: NEW — 30 E2E scenarios for signal pipeline
- `self-learning/tests/test_deployment_verifier.py`: NEW — 24 tests
- `design-skills/tests/test_report_charts.py`: +16 tests (coverage ratio, hook coverage)
- `CCA_TO_POLYBOT.md`: Updated from S112 to S125 (MT-0 verifier, MT-33, MT-28, recommendations)
- `priority_picker.py`: MT-31 Flash-only, MT-26 near-complete, MT-32 refreshed
- `MASTER_TASKS.md`: MT-31 status updated (Pro unavailable, Flash scope)
- `PROJECT_INDEX.md`: Doc drift fix (design-skills, usage-dashboard, total)

**Why:**
- S124 resume directive: validate Gemini MCP E2E (done — Flash works, Pro blocked)
- Priority picker: MT-26 (21.0) and MT-0 (19.0) stagnating — addressed both
- Bridge file was 13 sessions stale — updated for Kalshi chat consumption
- Matthew directive: work on MT-26/MT-0

**Tests:** 8040/8040 passing (203 suites). +70 new tests.

**Lessons:**
- Google One AI Premium gives Gemini Pro in web app but NOT API access — these are separate products
- Signal pipeline is solid — 30 E2E scenarios all pass first try

---

## Session 121 — 2026-03-22

**What changed:**
- `design-skills/chart_generator.py`: Added 4 statistical chart types — ScatterPlot (multi-series, trend lines), BoxPlot (quartiles, outliers), HistogramChart (Sturges' auto-binning), ViolinPlot (Gaussian KDE, quartile lines). 21 chart types total.
- `design-skills/tests/test_chart_scatter_box.py`: 42 tests for ScatterPlot + BoxPlot
- `design-skills/tests/test_chart_histogram.py`: 25 tests for HistogramChart
- `design-skills/tests/test_chart_violin.py`: 23 tests for ViolinPlot
- `design-skills/tests/test_chart_consistency.py`: Updated for all 4 new types
- `MASTER_TASKS.md`: MT-33 (Strategic Intelligence Report) and MT-34 (Medical AI Tool) created
- Session orchestrator live test verified (register/plan/status working)

**Why:**
- MT-32 Pillar 4: statistical chart types needed for data analysis and future MT-33 financial analytics
- MT-33: Matthew wants /cca-report to include Kalshi bot analytics, self-learning insights, research pipeline
- MT-34: Matthew wants a provider-grade medical AI tool better than OpenEvidence (idea logged, not started)

**Tests:** 7800/7800 passing (197 suites)

**Lessons:**
- Grid lines and trend lines both use stroke-dasharray — use specific patterns ("6,3" vs "3,3") to distinguish in tests

---

## Session 119 — 2026-03-22

**What changed:**
- `design-skills/chart_generator.py`: Added SankeyChart (16th chart type) — flow diagrams with topological node ordering, cubic bezier bands, custom colors
- `design-skills/tests/test_chart_generator_sankey.py`: 25 tests for SankeyChart
- Polybot queue hook E2E verified — simulated km receiving CCA tasks via cross_chat_queue.jsonl
- Cleaned stale messages from km queue (old MT-0 task brief, test ping)

**Why:**
- MT-32 Visual Excellence: SankeyChart enables intelligence pipeline flow visualization (Scan -> Review -> BUILD/SKIP)
- Queue hook verification confirms the 3-chat coordination pipeline is functionally wired end-to-end

**Tests:** 7611/7611 passing (191 suites)

**Lessons:**
- Worker crashed before completing research task — for research-heavy tasks, run as desktop task instead of delegating to worker

---

## Session 118 — 2026-03-21

**What changed:**
- `MASTER_TASKS.md`: MT-32 Visual Excellence & Design Engineering created (8 pillars, absorbs MT-24/MT-25)
- `design-skills/report_generator.py`: Wired report_charts.py into /cca-report — 7 SVG charts auto-generated and embedded in PDF
- `design-skills/chart_generator.py`: Added BubbleChart + TreemapChart (14 chart types total, 32 tests)
- `design-skills/report_charts.py`: Added module_loc_treemap() — 7th chart type for reports
- `design-skills/templates/cca-report.typ`: Embeds charts in 4 report sections (module tests+treemap, frontiers, MT status+progress, intelligence+LOC)
- `design-skills/design-guide.md`: Design token system — color tokens, spacing scale, typography scale, anti-AI-slop rules
- `KALSHI_TASK_CATALOG.md`: 6 productive task categories for CCA desktop to assign Kalshi main
- `.claude/commands/cca-auto-desktop.md`: Added Step 5d2 Kalshi task management in coord round
- Polybot `settings.local.json`: Wired queue_hook.py UserPromptSubmit hook (Matthew-authorized)
- Worker: `MT32_VISUAL_DESIGN_SCAN.md` — 14 findings (5 BUILD/ADAPT, 7 REFERENCE, 2 SKIP)

**Why:**
- Matthew directive: comprehensive visuals/UI/design MT covering all visual work, not just charts
- 3-chat coordination: polybot hook enables Kalshi main to receive CCA task assignments automatically
- Design tokens: community-validated fix for "AI slop UI" (purple defaults, generic cards)

**Tests:** 7586/7586 passing (190 suites). +37 desktop tests.

**Lessons:**
- "AI slop" is a color/typography problem, not a layout problem — design tokens fix it cheaply
- svg.py is interesting but not worth the dependency for our current needs (REFERENCE not BUILD)
- Kalshi is ONE chat now (main+research combined) — simplifies 3-chat architecture

---

## Session 117 — 2026-03-21

**What changed:**
- `design-skills/report_charts.py`: SVG chart generator bridging CCA report data to chart_generator.py. 6 chart types for Typst PDF embedding (32 tests)
- `cca_comm.py`: Cross-project routing — `task km`, `say km`, `inbox km` now route through cross_chat_queue.py. Foundation for true 3-chat coordination (7 new tests)

**Why:**
- Report charts: CCA has 10+ chart types but reports use none of them. This bridges the gap.
- Cross-project routing: Matthew identified that Kalshi main running independently != true 3-chat. CCA desktop must orchestrate ALL chats.

**Tests:** 7490/7490 passing (188 suites, +157 new)

**Lessons:**
- Current "3-chat" is 2+1 independent. True coordination requires CCA desktop tasking Kalshi main with productive work, not just monitoring.
- Verify worker survives launch — check crash_recovery 5 min after.

---

## Session 110 — 2026-03-21

**What changed:**
- `self-learning/macro_regime.py`: MT-26 Tier 2 — Economic event proximity filter with built-in 2026 calendar (FOMC, CPI, NFP, jobless claims). CALM/ELEVATED/HIGH_IMPACT classification (30 tests)
- `self-learning/fear_greed_filter.py`: MT-26 Tier 2 — Sentiment contrarian filter. 5 zones, direction bias, sizing modifier, trend context support (38 tests)
- `self-learning/signal_pipeline.py`: MT-26 Pipeline Orchestrator — Chains all 6 MT-26 modules, graceful degradation, compound modifiers, BET/SKIP decision (32 tests)
- `self-learning/outcome_feedback.py`: MT-28 Phase 4 — Research outcomes feedback loop bridging research_outcomes to principle_registry scoring (16 tests)
- `SESSION_DAEMON_DESIGN.md`: MT-30 Phase 1 — Complete design for tmux-based session auto-manager (5-phase plan)
- `MASTER_TASKS.md`: Added MT-30 (Session Daemon)
- `priority_picker.py`: MT-26 4/6, MT-28 4/6, MT-30 1/5, session counter 110
- `CCA_TO_POLYBOT.md`: Added signal pipeline integration guide for Kalshi bot

**Why:**
- MT-26 Tier 2 is now fully complete (macro regime + fear & greed + dynamic kelly). The pipeline orchestrator chains all 6 modules into a single call for the bot. The bot can now get regime-aware, sentiment-adjusted, macro-filtered Kelly bet sizing from one function call.
- MT-28 Phase 4 closes the research-to-profit feedback loop — when Kalshi outcomes come back, principle scores update automatically.
- Session daemon design doc lays groundwork for the #1 force multiplier. Multi-chat build per Matthew directive.

**Tests:** 6559/6559 passing (164 suites, up from 6443/160)

**Lessons:**
- Wrap at ~70% context, not 96% — S109's tip was correct. This session wrapped cleanly with room to spare.
- Matthew's "spread over several chats" directive for the session daemon was wise — the design doc alone surfaced 4 open questions that need resolution before code.

---

## Session 109 — 2026-03-21

**What changed:**
- `self-learning/calibration_bias.py`: MT-26 Tier 1 — FLB mispricing zone detection, calibration curves, bias-adjusted probability (43 tests)
- `self-learning/cross_platform_signal.py`: MT-26 Tier 1 — Kalshi/Polymarket divergence detector, lag analysis (30 tests)
- `self-learning/dynamic_kelly.py`: MT-26 Tier 2 — Bayesian belief updating in logit space, time-decay Kelly, fractional multiplier (32 tests)
- `self-learning/principle_transfer.py`: MT-28 Phase 3 — Cross-domain principle transfer with affinity scoring (34 tests)
- `self-learning/detectors.py`: Added PrincipleTransferDetector as 12th registered detector
- `.gitignore`: Added runtime state files (.cca-init-benchmarks.jsonl, .cca-stagnation-log.jsonl, .cca-trial-results.jsonl)

**Why:**
- MT-26 financial intelligence engine: all 3 Tier 1 items now complete (regime detection + calibration bias + cross-platform signals). First Tier 2 item (dynamic Kelly) also done. These modules give the Kalshi bot regime-aware, calibration-corrected, cross-platform-informed bet sizing.
- MT-28 self-learning v2: Phase 3 completes the principle registry architecture. Principles that work in one domain now surface as transfer opportunities in related domains.

**Tests:** 6443/6443 passing (160 suites, up from 6304/156)

**Lessons:**
- Session daemon (tmux-based auto-spawn) is the #1 unlockable force multiplier — all coordination infrastructure is built, just needs the final "glue" watcher

---

## Session 108 — 2026-03-21

**What changed:**
- `launch_kalshi.sh`: Replaced AppleScript keystroke with `open -a Terminal` + temp script. Added `both` mode. Fixed -1719 error.
- `launch_worker.sh`: Same AppleScript fix.
- `FIX_API_AUTH.md`: New — documents ANTHROPIC_API_KEY in .zshrc root cause and fix.
- `self-learning/pattern_registry.py`: New — central plugin registry with `@register_detector`, `PatternDetector` base class, domain filtering, exception isolation.
- `self-learning/detectors.py`: New — 11 built-in detectors (6 general, 5 trading) extracted from reflect.py.
- `self-learning/reflect.py`: `detect_patterns()` refactored to delegate to registry (14 LOC vs 200+).
- `self-learning/regime_detector.py`: New — market regime classifier (volatility, R-squared, Hurst exponent). TRENDING/MEAN_REVERTING/CHAOTIC/UNKNOWN.
- `self-learning/tests/test_pattern_registry.py`: New — 14 tests.
- `self-learning/tests/test_detectors.py`: New — 28 tests.
- `self-learning/tests/test_regime_detector.py`: New — 21 tests.
- `self-learning/tests/test_reflect.py`: Updated mock paths for registry compatibility.
- `self-learning/tests/test_reflect_extended.py`: Updated mock paths for registry compatibility.

**Why:**
- Launch scripts were broken (AppleScript -1719 error when no Terminal window existed)
- API billing confusion: ANTHROPIC_API_KEY in .zshrc overrode Max subscription OAuth
- MT-28 Phase 2: Pattern registry enables new domains to add detectors without modifying reflect.py core
- MT-26 Phase 1: Regime detector gives Kalshi bot awareness of when to trade vs skip

**Tests:** 6304/6304 passing (156 suites). +137 tests, +3 suites from S107.

**Lessons:**
- AppleScript `front window` fails with -1719 when Terminal has zero windows — use `open -a Terminal` with a temp script instead
- When refactoring from inline to registry pattern, mock paths in tests must be updated to patch both old and new import locations

---

## Session 104 — 2026-03-21

**What changed:**
- `MT23_MOBILE_RESEARCH.md` — Full rewrite: Remote Control as PRIMARY mobile path, Discord as SECONDARY, Telegram deprecated. GitHub #28402 reconnection gap documented. 6 CCA enhancement opportunities.
- `INSTALL_DISCORD_CHANNELS.md` — NEW: ADHD-friendly copy-paste Discord setup steps
- `MT28_SELF_LEARNING_V2_RESEARCH.md` — NEW: Self-Learning v2 research (EvolveR principles, pattern plugin registry, feedback loop, 6-phase plan)
- `KALSHI_MT0_TASK_BRIEF.md` — NEW: Autonomous task brief for Kalshi bot self-learning deployment (4 tasks)
- `LAUNCH_KALSHI_MT0.md` — NEW: Launch instructions for Kalshi chat with MT-0 task brief
- `LAUNCH_KALSHI_CHAT.md` — NEW: Generic Kalshi chat launch instructions
- `priority_picker.py` — MT-0 added (base=10), MT-28 base=10, MT-26 base=9, MT-23 lowered to 5, session counter to 104

**Why:**
- Matthew S103 directive: Remote Control is PRIMARY mobile path (zero-setup)
- Matthew S104 directive: Shift priorities to self-learning + financial research for Kalshi bot profitability
- MT-0 Phase 2 (deploy self-learning to bot) is now THE #1 task — task brief written for cross-project hivemind coordination

**Tests:** 131/131 suites passing (all green)

**Lessons:**
- AppleScript terminal launch is unreliable for starting claude sessions — test the pipeline first
- Cross-chat queue must be cleaned of stale messages before launching a new chat (stale hour-block messages from S117 could have caused the Kalshi chat to re-implement reverted changes)
- Deep-context sessions (this one) need explicit verification flags in the resume prompt

---

## Session 97 — 2026-03-21

**What changed:**
- `self-learning/trading_analysis_runner.py` — Fixed for real Kalshi schema (pnl_cents/ticker/count/is_paper), auto-detect legacy vs current, paper/live separation, strategy health integration
- `self-learning/strategy_health_scorer.py` — NEW: Statistical strategy health scorer (HEALTHY/MONITOR/PAUSE/KILL verdicts, 200 LOC)
- `self-learning/tests/test_strategy_health_scorer.py` — NEW: 24 tests for health scorer
- `self-learning/tests/test_trading_analysis_runner.py` — +9 Kalshi schema tests (28 total)
- `MASTER_TASKS.md` — Graduated MT-9, MT-10, MT-17 to Completed. Priority queue recalculated for S97.
- `KALSHI_INTEL.md` — Real analysis data appended (4052 trades, $450.11 PnL, 21 strategies)
- `worker_task_tracker.py` — NEW (worker): Detect incomplete worker task completion (147 LOC, 26 tests)
- `tests/test_worker_task_tracker.py` — NEW (worker): 26 tests

**Why:**
- MT-10 Phase 3A (top priority at 11.0) — graduate self-learning to Kalshi cross-project
- Matthew directive: distinguish paper vs live bets, give worker more complex tasks
- Financial mission: strategy health verdicts give Kalshi research chat actionable kill/pause recommendations

**Tests:** 103/103 suites passing (~4050 total)

**Lessons:**
- Reading MASTER_TASKS.md in full eats context budget — build priority_picker.py to automate
- Give worker tasks before heavy context reads to maximize parallel time

---

## Session 96 — 2026-03-21

**What changed:**
- `memory-system/tests/test_capture_hook.py` (NEW) — 112 tests for capture_hook.py (664 LOC, was 0 tests)
- `self-learning/tests/test_reflect.py` (NEW, worker) — 61 tests for reflect.py (782 LOC, was 0 tests)
- `reddit-intelligence/tests/test_url_reader.py` (NEW, worker) — 30 tests for url_reader.py (163 LOC)
- `.claude/commands/cca-wrap-worker.md` — Added Step 5 self-learning journal + advancement tips. Step numbering fixed (5-8). Worker terminal close guarded with TERM_PROGRAM check.
- `launch_worker.sh` — Documented front-loading lesson: one task per message
- `FINDINGS_LOG.md` — 6 new entries from daily scan (1 ADAPT, 3 REFERENCE, 1 REF-PERSONAL, 1 SKIP)
- `KALSHI_INTEL.md` — Alternative data edge hierarchy insight
- `LEARNINGS.md` — Worker front-loading pattern (Severity 2)
- `PROJECT_INDEX.md` — Test counts corrected twice (3794 -> 3997, 98 -> 101 suites)

**Why:**
- MT-22 Supervised Trial #1: this session IS the trial. 5th consecutive hivemind PASS.
- Test coverage: filled top 3 untested modules (capture_hook, reflect, url_reader = 203 new tests)
- Process improvement: workers now have self-learning journal step in wrap
- Intelligence: daily nuclear scan validated; Claude Control (ADAPT) relevant to MT-1

**Tests:** 101/101 suites passing (3997 total, +203 new)

**Lessons:**
- Combined TASK 1+TASK 2 messages cause workers to cherry-pick the easiest task
- Workers are most productive when they find their own rhythm after completing first assignment
- Desktop best for: scans, docs, bridge intel, process improvements. Worker best for: code/tests.
- $TERM_PROGRAM is the reliable guard for Terminal.app-specific osascript calls

---

## Session 95 — 2026-03-20

**What changed:**
- `context-monitor/session_notifier.py` (NEW) — ntfy.sh push notifications for session end/error events (19 tests)
- `.claude/commands/cca-wrap-desktop.md` — Added Step 9.8: session-end notification
- `.claude/commands/cca-wrap.md` — Added Step 8.5: session-end notification
- `.claude/commands/cca-desktop.md` — Fixed launch sequence: init → worker → auto-desktop
- `agent-guard/effort_scorer.py` — CLI arg-parsing complexity discount (4 new tests, 46 total)
- `MASTER_TASKS.md` — MT-22 Phase 2 complete, priority queue updated
- Worker: `tests/test_autonomous_scanner_e2e.py` (NEW) — 24 E2E tests for autonomous scanner

**Why:**
- MT-22 Phase 2: session-end notification so Matthew knows when autonomous runs finish
- MT-20 validation: discovered and fixed effort_scorer false positive on CLI utility files
- Process improvement: worker launch sequence was wrong, costing parallel time

**Tests:** 98/98 suites passing (3794 total, +76 new)

**Lessons:**
- CLI arg-parsing inflates complexity scores — need pattern-aware discounting
- Worker wraps after first task without checking inbox for follow-ups — front-load tasks at launch
- macOS grep doesn't support -P flag — use Python or awk for PCRE patterns

---

## Session 93 — 2026-03-20

**What changed:**
- **3 critical Phase 2 infrastructure fixes** (`cca_internal_queue.py`, `cca_comm.py`, `crash_recovery.py`):
  - Atomic file writes for queue (tempfile + os.replace) — prevents corruption from concurrent access
  - Scope conflict detection wired into `cca_comm.py claim` — blocks workers from claiming owned scopes
  - Stale scope timeout wired into crash recovery pipeline — expires scopes >30min (catches hung workers)
- **tests/test_phase2_hardening.py** (22 tests) — tests for all 3 fixes
- **tests/test_phase2_e2e.py** expanded (5 new tests) — conflict-blocked claims, post-release re-claim, stale recovery, 60-msg bulk ack, dual-worker scopes
- **2 hardened simulated sessions**: S93 #2 (conflict detection, PASS), S93 #3 (crash+stale+2-worker+54 msgs, PASS)
- **HIVEMIND_ROLLOUT.md**: Phase 1 Matthew confirmation, Phase 2 gate marked PASSED

**Why:**
- Phase 2 gate required 3+ hardened sessions — needed infrastructure fixes + 2 more session passes
- Atomic writes prevent race condition at 50+ msgs/session target
- Scope conflict detection prevents the most likely dual-chat failure mode

**Tests:** 3687/3687 passing (94 suites)

**Lessons:**
- Don't check off gates without actually doing the work — paperwork isn't proof
- When Matthew gives direction, execute immediately instead of over-analyzing

---

## Session 92 — 2026-03-20

**What changed:**
- **Phase 2 crash recovery live test: PASS** — Simulated cli1 crash, crash_recovery.py auto-released orphaned scope
- **cca_comm.py `context` command** (13 new tests) — Workers see desktop's recent commits, active scopes, queue stats, crash status
- **hivemind_metrics.py queue throughput** (6 new tests) — Phase 2 50+ msgs/session metric tracking
- **tests/test_phase2_e2e.py** (7 tests) — E2E integration test for full Phase 2 lifecycle, crash recovery, multi-task
- **loop_health.py timezone fix** — get_summary() now uses UTC date to match UTC timestamps
- **Workflow wiring** — Worker init runs context, desktop wrap measures throughput
- **HIVEMIND_ROLLOUT.md** — Crash gate checked, suggested tasks for remaining sessions

**Why:**
- Phase 2 crash recovery gate criterion needed live proof
- Workers need visibility into desktop's recent work for Phase 2 tasks
- Need automated measurement of 50+ msgs/session target

**Tests:** 3660/3660 passing (93 suites)

**Lessons:**
- Timezone flake: always use UTC consistently when timestamps cross module boundaries
- macOS grep doesn't support -P flag (use python or other tools for Perl regex)

---

## Session 91 — 2026-03-20

**What changed:**
- **chat_detector.py** (202 LOC, 31 tests) — Duplicate Claude Code session detection, pre-launch safety, terminal close via AppleScript
- **crash_recovery.py** (180 LOC, 15 tests) — Orphaned scope detection + auto-release after worker crash
- **phase2_validator.py** (300 LOC, 22 tests) — Multi-module integration validator (built by cli1 worker, imports 3 modules)
- Multi-task worker loop in /cca-auto-worker with keep-busy fallback (review commits, scan TODOs when idle)
- Desktop front-loads 2-3 tasks to worker (/cca-auto-desktop Step 5.5)
- Terminal close on worker wrap (/cca-wrap-worker Step 6)
- Stale worker detection on desktop wrap (/cca-wrap-desktop Step 9.5)
- Duplicate check in launch_worker.sh (Step 0) and /cca-init (Step 4.5)
- ROADMAP.md doc drift fix (self-learning 526→560, TOTAL 3293→3614)
- Phase 2 live tests #1 and #2 logged in HIVEMIND_ROLLOUT

**Why:**
- Phase 1 confirmed complete by Matthew — moved to Phase 2 (hardened 2-chat with crash recovery + multi-task)
- Matthew explicit: close terminal windows on wrap, monitor duplicates, workers should multi-task not sit idle

**Tests:** 3636/3636 passing (92 suites). 68 new tests this session.

**Lessons:**
- crash_recovery sender must use crashed worker's chat_id, not "system" or "desktop" (cca_internal_queue validates sender)
- macOS grep doesn't support -P flag — use Python or awk for regex counting

---

## Session 90 — 2026-03-20

**What changed:**
- **PHASE 1 GATE: READY** — 3/3 consecutive live hivemind tests passed
- **hivemind_session_validator.py** (170 LOC, 17 tests) — Desktop-side cycle validation + Phase 1 gate tracking
- **overhead_timer.py** (120 LOC, 13 tests) — Coordination overhead measurement
- **hivemind_metrics.py** (149 LOC, 20 tests) — Phase 1 metrics persistence (built by cli1 worker)
- **hivemind_dashboard.py** (180 LOC, 20 tests) — Combined Phase 1 status reporter (built by cli1 worker)
- Wired session validator into /cca-init and /cca-wrap-desktop
- Added worker inbox check step to /cca-auto-desktop
- Updated HIVEMIND_ROLLOUT.md with actual Phase 1 validation results

**Why:**
- Prove dual-chat hivemind works in real operation (Matthew directive: automate and test)
- Complete Phase 1 of HIVEMIND_ROLLOUT — 4/5 gate criteria met, awaiting Matthew confirmation

**Tests:** 3568/3568 passing (89 suites). 70 new tests this session.

**Lessons:**
- Worker can handle escalating task difficulty (new module -> integration -> code modification)
- Worker sometimes needs multiple iterations on import path issues — TDD catches these
- rtk proxy interferes with `find` output piping — use Python glob for test counting

---

## Session 89 — 2026-03-20

**What changed:**
- **test_hivemind_deep.py** — 117 deep tests (31 classes) covering shutdown, error paths, scope dedup, cross-CLI conflicts, stress, queue injection safety, message ID uniqueness, and more.
- **_make_id collision bug** — Real bug found and fixed in `cca_internal_queue.py`, `cca_hivemind.py`, `cross_chat_queue.py`. Broadcast messages to 3 targets in same second produced identical IDs. Fixed by adding target to hash.
- **tip_tracker.py** — Advancement tip persistence (26 tests). Extracts, stores, filters tips from session responses. CLI interface + `format_for_init`.
- **wrap_tracker.py** — Session wrap assessment persistence (23 tests). Logs grade/wins/losses/test counts. Trend analysis (improving/declining/stable). `format_for_init` for session briefing.
- **Command wiring** — Both trackers wired into `/cca-wrap` (Steps 6a.6, 6a.7), `/cca-wrap-desktop` (Step 7.5), and `/cca-init` (Step 2.7).
- **wrap_assessments.jsonl** — Seeded with S82-S86 historical data from CHANGELOG for bootstrapping trends.
- **Queue cleanup** — Stale S86 shutdown signals cleared, hivemind preflight verified "ready".

**Why:**
- Matthew S86: "Test the hell out of hivemind functions" — deep testing found a real production bug
- Matthew S86 explicit: "Build advancement tip tracker" — tips now persist across all chats
- S86 priority #3: "Persist wrap assessments to file" — quality trends now trackable
- Tracker wiring ensures every future session auto-captures tips and grades

**Tests:** 3498/3498 passing (85 suites, +166 new this session)

**Lessons:**
- `_make_id` must include all distinguishing fields (sender + target + subject + timestamp). Omitting target caused ID collisions on broadcast messages — `acknowledge(msg_id)` would only ack the first match.
- macOS grep doesn't support `-P` (PCRE). Use `grep -o` with `awk` for extraction.
- Backfilling historical data into new tracking systems is important for bootstrapping — trend analysis needs 2+ data points to start computing.

---

## Session 86 — 2026-03-20

**What changed:**
- **Hivemind Phase 1 validation: 2/3-5 tests passed** — First real dual-chat tests. Desktop assigned tasks, workers (cli1) claimed scope, built code, committed, reported back. Zero coordination failures.
- **launch_worker.sh** — One-command dual-chat launcher (opens Terminal tab with CCA_CHAT_ID, starts `claude /cca-worker`)
- **cca_internal_queue.py** — Fixed scope dedup (broadcast claims counted 3x), added (sender, subject) deduplication
- **cca_comm.py** — Added `assign` alias for `task`, stale task auto-clearing on new assignment, `shutdown` command for clean worker termination
- **cca-auto-worker.md** — Workers check inbox twice before stopping (task chaining), SHUTDOWN message detection
- **cca-wrap.md + cca-wrap-desktop.md** — Auto-shutdown workers on Desktop wrap (prevents lingering CLI chats)
- **Worker commits (S87, S88)** — cli1 autonomously built `tests/test_hivemind_validation.py` (3 tests) and `self-learning/tests/test_journal.py` (34 tests, 411 LOC)
- **Strategic vision documented** — Matthew's 5-phase hivemind vision, $250/mo financial sustainability goal, advancement tip tracker need. All in memory system.

**Why:**
- Hivemind Phase 1 is the critical path to proving 2-chat > 1-chat for productivity
- Stale task bug (test #3) revealed a real design gap — fixed same session
- Worker shutdown mechanism prevents resource waste (Matthew's explicit request)

**Tests:** 3332/3332 passing (82 suites, +2 from workers)

**Lessons:**
- Broadcast messages (scope claims) create N-1 queue entries — deduplicate by (sender, subject)
- Workers need stale inbox clearing before new task assignment
- Workers don't auto-chain to new tasks after completing one — added double-check with wait
- grep -P doesn't work on macOS — use `grep -o` with `sed` instead

---

## Session 85 — 2026-03-20

**What changed:**
- **Dual-CCA command system** — 6 new slash commands (`cca-desktop`, `cca-worker`, `cca-auto-desktop`, `cca-auto-worker`, `cca-wrap-desktop`, `cca-wrap-worker`) mirroring the proven Kalshi main/research pattern. Desktop coordinates + owns shared docs; worker receives tasks + commits code.
- **daily_snapshot.py fix** — `_count_test_methods()` switched to AST parsing. Previous string matching counted `def test_` inside triple-quoted strings as real tests (3308 false vs 3293 actual).
- **Reddit daily scan** — 2 new FINDINGS_LOG entries (Epstein archive context drift, satellite tracker).
- **Paper scanner** — 4 new papers evaluated (25 total): Darwin Godel Machine, SEW, Code Graph Model, Trae Agent.

**Why:**
- Dual-CCA commands are the missing piece for MT-21 Hivemind Phase 1 validation. The Kalshi dual-chat works well because each chat has dedicated commands — CCA now has the same.
- Snapshot counter fix prevents future false doc drift alerts.

**Tests:** 3293/3293 passing (80 suites)

**Lessons:**
- `def test_` string matching is unreliable for counting tests — test files contain mock test content as string literals. AST parsing is the correct approach.
- The Kalshi dual-chat pattern works because of dedicated commands per role, not env var detection. Hardcoded behavior per command is cleaner than conditional logic in shared commands.

---

## Session 84 — 2026-03-20

**What changed:**
- **MT-14 Phase 3 COMPLETE** — `execute_rescan_stale()` method, `rescan-all` CLI command (--max-age/--json), `--include-rescan` flag on daily command. All wired into autonomous pipeline.
- **Reddit daily scan** — 1 new finding logged: cross-model review workflow (REFERENCE for MT-20 + Frontier 2).
- **Doc drift fix** — Test counts corrected 3277->3293 across PROJECT_INDEX + ROADMAP.

**Why:**
- MT-14 Phase 3 completes the rescan lifecycle: stale subs are now auto-rescanned during autonomous runs, reducing manual intervention.

**Tests:** 3293/3293 passing (80 suites, +16 new)

**Lessons:**
- Mock data for nuclear_fetcher tests must include `is_self` and `selftext` fields (classify_post requires them).

---

## Session 83 — 2026-03-20

**What changed:**
- **MT-20 COMPLETE** — Senior Dev Agent fully E2E validated (10/10 tests, claude-haiku-4-5-20251001). Matthew added $5 API credits + new key. False-pass bug fixed in E2E tests (error strings matching content assertions).
- **MT-11 COMPLETE** — GitHub Intelligence all phases done. Phase 2: `fetch_trending()`, `TrendingScanner`, CLI `trending` command (+32 tests). Phase 3: `execute_github_trending()` wired into `AutonomousScanner` with safety gates, `GitHubTrendingReport` dataclass, CLI `github-trending` command (+12 tests).
- Reddit rising scan — r/ClaudeCode rising posts reviewed. Community validates hooks-based safety approach (AG module). Cross-model review workflow emerging (Opus+GPT), relates to MT-20 senior_chat architecture.
- Doc drift fixes, MT priority recalculations, test count corrections across all docs.
- Live validation: `github-trending` command found 15 trending repos, 12 EVALUATE verdicts across 5 languages.

**Why:**
- MT-20 was the last major feature needing validation — $0.01 API call proves 13 modules work end-to-end.
- MT-11 Phase 3 closes the loop: trending discovery now runs through the autonomous safety pipeline.

**Tests:** 3277/3277 passing (80 suites). +29 new tests this session (12 autonomous_scanner, 17 earlier).

**Lessons:**
- Smallest possible API model (haiku) for E2E tests keeps costs near zero while proving integration works.
- TrendingScanner -> AutonomousScanner integration was clean because both follow the same safety gate pattern.

---

## Session 82 — 2026-03-20

**What changed:**
- ROADMAP.md — Fixed massive doc drift: agent-guard 633→889, design-skills 163→213, added root tests row (305), total corrected to 3248. Added MT-20/MT-21 to MT table. Session history S72-S82.
- agent-guard/bash_guard.py — cp destination outside project now blocked (was only mv). Script interpreter evasion vectors blocked: python3 -c, perl -e, ruby -e, node -e, pwsh -c. dd of= and tee to outside-project paths blocked.
- agent-guard/tests/test_bash_guard.py — +25 tests (TestCopyOutsideProject, TestScriptInterpreterEvasion, TestDdTeeEvasion). 86→111 tests.
- usage-dashboard/doc_drift_checker.py — Root module false positive fix: "root/" files now resolved against project root, not root/ subdir.
- usage-dashboard/tests/test_doc_drift.py — +2 tests (TestRootModuleFilePaths). 30→32 tests.
- FINDINGS_LOG.md — 7 new entries from r/ClaudeCode hot scan.
- MASTER_TASKS.md — Priority scores recalculated S77→S82.

**Why:**
- Reddit intelligence revealed real AG-9 evasion vectors (script interpreters, cp, dd, tee) — fixed immediately.
- Doc drift had grown to +399 uncounted tests over 14 sessions — now zero drift.
- Priority decay recalculation keeps task ordering accurate.

**Tests:** 3248/3248 passing (80 suites). 27 new tests this session.

**Lessons:**
- Reddit scans that find security gaps are highest-ROI autonomous work — immediate fix cycle.
- Doc drift compounds silently — the 399-test gap accumulated over S68-S82 without detection.

---

## Session 81 — 2026-03-20

**What changed:**
- agent-guard/senior_chat.py — `build_intent_check_prompt()` and `build_tradeoff_prompt()`: structured LLM prompts for intent verification (MATCH/GAPS/EXTRAS/RISKS) and trade-off judgment (COMPLEXITY/ABSTRACTION/EXTENSIBILITY/SIMPLIFICATION/RECOMMENDATION).
- agent-guard/tests/test_senior_chat_e2e.py (NEW) — 10 E2E tests for real Anthropic API: simple Q&A, conversation history, system prompt shaping, intent mismatch detection, tradeoff analysis. Skip without key.
- cca_internal_queue.py — `hivemind_preflight()`: combines queue health + stale scope auto-release + unread check + scope warnings into single readiness call.
- .claude/rules/hivemind-worker.md (NEW) — Worker persona instructions for CLI hivemind sessions.
- SENIOR_DEV_GAP_ANALYSIS.md — All 10/10 gap items marked CLOSED.
- MASTER_TASKS.md — MT-20 status updated to reflect S78-S81 phase completions.
- PROJECT_INDEX.md — Test counts updated (doc drift fix).

**Why:**
- MT-20 milestone: all 10 gap analysis items now have implementations. The remaining work is E2E validation with a real API key.
- MT-21 Phase 1 prep: all infrastructure ready for first real 2-chat test.

**Tests:** 3221/3221 passing (80 suites). 35 new tests this session.

**Lessons:**
- Structured LLM prompt templates can close "requires LLM" gaps without needing API access during development — build the scaffold, test later.
- Queue infrastructure was more complete than expected (queue_health, expire_stale_scopes already existed) — always check before building.

---

## Session 80 — 2026-03-20

**What changed:**
- agent-guard/senior_chat.py — LLMClient class: Anthropic Messages API (stdlib urllib), conversation history, token tracking, `--model`/`--no-llm` flags, `build_system_prompt()`, git_summary in ReviewContext.
- agent-guard/senior_dev_hook.py — `_humanize_finding()` rewrite: advice-first output, `_parse_satd_message()` helper.
- agent-guard/git_context.py (NEW) — Git history awareness: file_history, blame_summary, commit_count, is_high_churn, format_for_review.
- agent-guard/senior_review.py — Step 7: git context integration (git_commits, git_high_churn metrics, last-changed suggestion, high-churn concern).
- agent-guard/tests/test_git_context.py (NEW) — 26 tests.

**Why:**
- MT-20 gap closure: LLM API wiring (#1 priority from S79), format_context rewrite (natural language over metric dumps), git history awareness (context-aware review). 8/10 gap analysis items now closed.

**Tests:** 3186/3186 passing (79 suites). 60 new tests this session.

**Lessons:**
- macOS grep doesn't support -P (Perl regex). Use python for test counting on Mac.
- `_parse_satd_message()` helper makes humanization testable independently of finding generation.

---

## Session 78 — 2026-03-20

**What changed:**
- agent-guard/senior_review.py (NEW) — On-demand senior developer review engine. Orchestrates SATD + quality + effort + coherence into APPROVE/CONDITIONAL/RETHINK verdicts with blast radius analysis. 16 tests.
- agent-guard/coherence_checker.py (NEW) — Architectural coherence checker. Module structure checks, cross-file pattern consistency (docstrings, naming), import dependency graph with blast radius. 18 tests.
- .claude/commands/senior-review.md (NEW) — `/senior-review` slash command for on-demand code review.
- agent-guard/senior_review.py — Integrated coherence checker + blast radius into review output.
- Memory: feedback_slow_build_mt20_mt21.md (NEW) — S78 slow-build directive for MT-20/MT-21.

**Why:**
- MT-20 Phases 7+9: Building the intelligence layer on top of existing metric infrastructure. Phase 7 (on-demand skill) complete. Phase 9 (coherence checker) foundation laid with import graph.
- Matthew S78 directive: Slow build over 5-6+ chats. Blueprint -> test -> code -> validate. No rushing.

**Tests:** 3085/3085 passing (77 suites). 34 new tests this session.

**Lessons:**
- SATD detector source code contains HACK/FIXME/WORKAROUND as part of its regex patterns — self-referential false positives. fp_filter integration needed in senior_review.py.
- Import regex must allow leading whitespace to catch imports inside try/except blocks.

---

## Session 77 — 2026-03-20

**What changed:**
- SENIOR_DEV_GAP_ANALYSIS.md (NEW) — comprehensive audit of MT-20: 8 modules are static linters, not the senior dev experience Matthew wants. Phases 6-9 defined with clear deliverables.
- HIVEMIND_ROLLOUT.md (NEW) — phased validation plan: prove 2-chat (3-5 sessions) before 3-chat. Measurable gates at each phase.
- MASTER_TASKS.md — MT-20 status rewritten (infrastructure!=experience), MT-21 created for Hivemind, priority queue updated, session counter 56->77
- PROJECT_INDEX.md — added references to gap analysis + rollout plan
- SESSION_STATE.md — S77 state with new Matthew directives
- 3 new memory entries: senior_dev_gap, hivemind_rollout, slow_validation feedback

**Why:**
- Matthew S77 directive: S72-S74 hivemind sprint was too ambitious for one chat. Slow down, prove incrementally. Document everything so future chats have full context.
- Fresh-eyes audit revealed MT-20 "Senior Dev" modules are metric calculators, not the interactive colleague experience Matthew described.

**Tests:** 2980/2980 passing (75 suites) — no code changes this session, documentation only.

**Lessons:**
- "Infrastructure complete" != "feature complete". Building the metric calculators was necessary but not sufficient. The intelligence layer (natural language advice, interactive review, context awareness) is where the actual senior dev value lives.
- Ambitious multi-chat coordination requires phased validation, not single-sprint shipping.

---

## Session 76 — 2026-03-20

**What changed:**
- Generated CCA Status Report 2026-03-20 (276KB, 18 pages) via Typst pipeline
- Updated `design-skills/report_generator.py`: HOOKS 9->18, Agent Guard components 7->17, Self-Learning/Design Skills components expanded
- Added `collect_criticisms()` method to report_generator.py — 7 dynamic criticisms
- Added "Honest Assessment" section to `design-skills/templates/cca-report.typ` with severity-coded badges
- Updated TOC in Typst template to include Honest Assessment
- Fixed `test_hooks_defined` assertion in test_report_generator.py (9->18)

**Why:**
- Matthew requested fresh report with today's data + objective criticisms of project progress
- HOOKS list was stale since S52, significantly underreporting live infrastructure

**Tests:** 2980/2980 passing (75 suites)

**Lessons:**
- Hardcoded data in report generators drifts silently — the HOOKS list was wrong for 24 sessions

---

## Session 74 (Desktop cli3) — 2026-03-20

**What changed:**
- Goal #1 COMPLETE: cca-loop production-ready for daytime supervised use
- `cca-loop` wired `loop_health.record_session()` — health tracking was built but never called
- `/cca-init`, `/cca-auto`, `/cca-wrap` all made hivemind-aware (workers skip shared doc updates)
- `cca_internal_queue.py` upgraded: 2 -> 4 chat IDs (desktop, cli1, cli2, terminal)
- `cca_hivemind.py` rewritten: stable window IDs for AppleScript injection
- `cca_comm.py` (NEW, 18 tests) — 9-command communication wrapper for hivemind
- `daily_snapshot.py` (NEW, 50 tests) — point-in-time project metric captures with diff
- Full tool authorization directive saved to memory

**Why:**
- Matthew's directive: ship cca-loop as production-ready tonight
- Concurrent /cca-wrap was a safety gap for hivemind (workers would corrupt shared docs)
- Health recording was wired but never called — cca-loop history showed empty data

**Tests:** 3030/3030 passing (75 suites)

**Lessons:**
- When building for hivemind, every shared skill (/cca-wrap, /cca-init, /cca-auto) needs role-awareness
- Health tracking modules are useless if never called from the lifecycle they track

---

## Session 72 — 2026-03-20

**What changed (3-chat hivemind sprint — MT-20 Senior Dev Agent MVP):**

Desktop chat (coordinator):
- `agent-guard/senior_dev_hook.py` — NEW: PostToolUse orchestrator (48 tests). Runs SATD + effort + quality on Write/Edit. Graceful degradation for optional submodules.
- `agent-guard/code_quality_scorer.py` — NEW: 5-dimension quality scoring 0-100 (38 tests). debt_density, complexity, size, documentation, naming.
- `tests/test_hook_chain_integration.py` — UPDATED: Added senior_dev_hook + queue_hook to canary (17 hooks).
- `.claude/settings.local.json` — UPDATED: senior_dev_hook wired as PostToolUse, queue_hook wired as PostToolUse + UserPromptSubmit.
- `PROJECT_INDEX.md`, `ROADMAP.md`, `MASTER_TASKS.md` — UPDATED: test counts, module entries, MT-20 status.

CLI chat 1:
- `agent-guard/effort_scorer.py` — NEW: PR effort scoring 1-5 scale (42 tests). Atlassian/Cisco thresholds.

CLI chat 2:
- `agent-guard/fp_filter.py` — NEW: False positive filter (40 tests). Test file, vendored, low-confidence filtering.
- `agent-guard/review_classifier.py` — NEW: CRScore-style category classification (43 tests). 6 categories with weighted scores.
- `agent-guard/tech_debt_tracker.py` — NEW: SATD trend analysis over time (27 tests).

**Why:**
- MT-20 (Senior Dev Agent MVP) — all 6 modules complete: SATD detector, effort scorer, FP filter, review classifier, code quality scorer, hook orchestrator
- First successful 3-chat hivemind sprint — validated file ownership + queue coordination model
- Established hivemind wrap protocol: Desktop coordinator owns all doc updates, CLI chats commit + queue

**Tests:** 2849/2849 passing (70 suites)

**Lessons:**
- Hivemind wrap protocol is critical — 3 chats editing SESSION_STATE simultaneously causes merge conflicts
- Desktop coordinator must own all shared doc updates; CLI chats commit code + send queue summaries
- CLI<->Desktop bidirectional communication needs improvement (CLI chats lack easy send-to-desktop commands)
- regex pattern ordering matters — review_classifier had 5 test failures because "fix" matched before style/logging patterns

---

## Session 71 — 2026-03-20

**What changed (CLI chat 1):**
- `agent-guard/satd_detector.py` — COMPLETED: SATD marker detection PostToolUse hook (44 tests)
- `agent-guard/effort_scorer.py` — NEW: PR effort scoring 1-5 scale (42 tests)

**Tests:** 2649/2649 passing (65 suites)

---

## Session 70 — 2026-03-20

**What changed (Desktop chat — 3 parallel chats this session):**
- `usage-dashboard/doc_drift_checker.py` — NEW: Automated doc accuracy verification (30 tests). AST-counts tests per module, compares to PROJECT_INDEX + ROADMAP claims.
- `queue_injector.py` — NEW: UserPromptSubmit cross-chat context injection hook (19 tests).
- `queue_hook.py` — NEW: Unified PostToolUse + UserPromptSubmit queue check hook (22 tests). Replaces queue_injector with faster dual-event design. 30s throttle on PostToolUse.
- `cca_hivemind.py` — NEW: Multi-chat orchestrator (22 tests). Session detection, queue directives, AppleScript Terminal injection, dynamic window discovery, safety guards.
- `tests/test_queue_injector.py`, `tests/test_queue_hook.py`, `tests/test_hivemind.py`, `usage-dashboard/tests/test_doc_drift.py` — NEW test suites.
- `.github/workflows/tests.yml` — FIXED: doc_drift_checker wired correctly (was using nonexistent --exit-code flag).
- `PROJECT_INDEX.md` — UPDATED: test counts, new file listings, hook table.
- `ROADMAP.md` — UPDATED: test counts synced to reality, S69-S70 session entries added.

**Why:**
- Senior dev gap #4 (doc drift prevention) — ROADMAP was 43 sessions stale before S68 manual fix. Now automated.
- Cross-chat communication gap — Kalshi chats never saw CCA findings because no notification mechanism existed.
- Hivemind infrastructure — Matthew wants 3 chats working in coordinated unison on single projects.

**Tests:** 2563/2563 passing (63 suites)

**Lessons:**
- Doc drift checker should run at every /cca-wrap, not just in CI
- AppleScript Terminal injection works but needs accessibility permissions enabled first
- Window indices are ephemeral — must re-discover before each ping
- 3 parallel chats are viable on Max 5 if all stay in inline mode (no agent spawns)

---

## Session 67 — 2026-03-19

**What changed:**
- `KALSHI_ACTION_ITEMS.md` — NEW: Concise TL;DR bridge file for Kalshi main + research chats (top 3 items each)
- `CCA_TO_POLYBOT.md` — UPDATED: REQUEST 10 response with verified GWU 2026-001 FLB data (psi coefficients)
- `~/.local/bin/cca-loop` — NEW: Autonomous CCA session loop (tmux-based, interactive, start/stop/attach)
- `~/Desktop/CCA Loop Start.command` + `CCA Loop Stop.command` — NEW: Desktop launchers
- `SESSION_RESUME.md` — NEW: Machine-readable handoff file for loop continuity
- `~/.claude/commands/cca-wrap.md` — UPDATED: Step 9 writes SESSION_RESUME.md
- `.claude/settings.local.json` — UPDATED: Added capture_hook.py to UserPromptSubmit + bash_guard.py to PreToolUse Bash
- `agent-guard/bash_guard.py` — NEW: AG-9 Bash command safety guard (86 tests). Blocks network, packages, processes, system mods, redirects, evasion
- `agent-guard/tests/test_bash_guard.py` — NEW: 86 tests for bash_guard

**Why:**
- Kalshi cross-chat communication was one-way megadumps — ACTION_ITEMS.md fixes that
- GWU citation needed verification before Kalshi bot could use FLB weakening data
- Autonomous loop system enables supervised daytime session looping (MT-1 adjacent)
- UserPromptSubmit capture enables real-time memory capture (not just session-end)
- Bash guard closes the #1 safety gap for autonomous/unattended sessions

**Tests:** 2236/2236 passing (54 suites, +86 new)

**Lessons:**
- Overnight autonomy is not safe with current trust model (regex hooks + --dangerously-skip-permissions)
- Daytime supervised loops are the right middle ground
- Start Kalshi support first each session to respect the 1/3 allocation

---

## Session 66 — 2026-03-19

**What changed:**
- `spec-system/plan_compliance.py` — NEW: Plan compliance reviewer (SPEC-6). 38 tests. Parses tasks.md, detects scope creep/future-task drift. ComplianceStatus: COMPLIANT/SCOPE_CREEP/FUTURE_TASK/NO_SPEC/NOT_APPROVED/NO_ACTIVE_TASK.
- `spec-system/tests/test_plan_compliance.py` — NEW: Full TDD test suite for compliance reviewer.
- `spec-system/hooks/validate.py` — Added spec_freshness integration: _check_freshness_context() detects stale specs when tasks are approved. Staleness warning injected as additionalContext (non-blocking).
- `self-learning/journal.jsonl` — S65 session entries committed.

**Why:**
- plan_compliance.py addresses implementation drift problem — after tasks.md is approved, code silently strays outside planned scope. Conductor's automated 5-point review was identified as the strongest competitor feature (S64 Google Conductor research).
- spec_freshness → validate.py wiring closes the feedback loop: staleness is now surfaced at implementation time, not just via standalone CLI.

**Tests:** 2188/2188 passing (53 suites, +38 from plan_compliance)

**Lessons:**
- settings.local.json edits require user permission approval even with Write(*) in permissions — plan for this by flagging at session start rather than burning a task slot.

---

## Session 64 — 2026-03-19

**What changed:**
- `memory-system/hooks/capture_hook.py` — Added UserPromptSubmit handler for real-time "remember/always/never" memory capture. Overlap span detection prevents duplicate extraction. 13 new tests.
- `spec-system/spec_freshness.py` — NEW: Spec rot/staleness detector. Compares spec vs code mtime, supports RETIRED status, CLI + JSON output. 25 tests.
- `spec-system/tests/test_spec_freshness.py` — NEW: Full test suite for freshness detector.
- `FINDINGS_LOG.md` — Google Conductor competitive analysis + QuantVPS reference logged.

**Why:**
- UserPromptSubmit capture was S63 advancement tip — makes explicit memories available within same session instead of waiting for Stop hook
- spec_freshness.py addresses the spec rot gap identified from Reddit SDD discussion (S63) — specs that diverge from code become two conflicting sources of truth
- Google Conductor deep-read was #1 on S63 next-list — needed competitive intel for Frontier 2

**Tests:** 2150/2150 passing (52 suites)

**Lessons:**
- UserPromptSubmit prompts can match multiple regex patterns (e.g., "remember that we always use X" matches both "remember that" and "always use"). Must track matched spans to prevent duplicate extraction from overlapping patterns.

---

## Session 62 — 2026-03-19

**What changed:**
- `memory-system/memory_store.py` — NEW: SQLite+FTS5 storage backend (464 LOC, 80 tests). BM25 relevance search, atomic transactions, WAL mode, TTL cleanup.
- `memory-system/mcp_server.py` — REWRITTEN: v2.0.0. Swapped JSON file backend to MemoryStore (FTS5). O(n) substring -> BM25-ranked search. Project filtering via SQL.
- `memory-system/tests/test_mcp_server.py` — REWRITTEN: 28 tests for FTS5 backend (was 29 for JSON).
- `FINDINGS_LOG.md` — 27 new entries (daily scan + algotrading + batch reviews + Channels + TokToken)
- `self-learning/BATCH_ANALYSIS_S62.md` — NEW: Trace analysis of 10 most recent sessions. Avg 73.0/100.

**Why:**
- FTS5 migration was P0 from EXTERNAL_COMPARISON.md (S60) — the single highest-ROI improvement for Frontier 1
- MCP server swap completes the read side of the FTS5 migration
- Reddit reviews were Matthew-driven (saved posts during the day)
- Batch trace analysis tracks whether edit_guard.py (S58) is reducing retries (it is: 64%->40%)

**Tests:** 2108/2108 passing (51 suites)

**Lessons:**
- Build vs research ratio should be 75-80% build / 20-30% research. Daily scan 15 min max.
- APF is 32.1% — 68% of findings are REFERENCE/SKIP. Research has diminishing returns per session.
- macOS grep lacks -P flag — use Python re module for PCRE extraction in bash scripts.

---

## Session 60 — 2026-03-19

**What changed:**
- `self-learning/trade_reflector.py` — Fixed 5 schema mismatches against real polybot.db (strategy_name->strategy, win/loss->yes/no, hour_utc->derived from timestamp, cost_basis_cents->cost_usd, entry_price_cents->price_cents)
- `self-learning/tests/test_trade_reflector.py` — Updated all 47 tests to use real DB schema (REAL epoch timestamps, correct column names, non-overlapping date ranges)
- `memory-system/research/EXTERNAL_COMPARISON.md` — NEW: Architecture comparison of engram, ClawMem, claude-mem. P0: FTS5 migration. P1: recency decay. P2: structured fields.
- `self-learning/resurfacer.py` — NEW functions: proposal_to_finding(), resurface_with_proposals() for unified findings + trade proposal display
- `self-learning/tests/test_resurfacer.py` — 8 new tests for proposal integration (49 total)
- `SESSION_STATE.md` — Updated for S60
- `PROJECT_INDEX.md` — Updated test count to 2029/50, added EXTERNAL_COMPARISON.md

**Why:**
- trade_reflector schema validation was #1 priority from S59 — confirmed 5 real mismatches that would cause runtime failures on actual DB
- Memory architecture research informs Frontier 1 roadmap — FTS5 identified as highest-ROI improvement
- Resurfacer integration completes MT-10 Phase 3B — trade proposals now surface alongside FINDINGS_LOG entries

**Tests:** 2029/2029 passing (50 suites)

**Lessons:**
- Test DBs with overlapping timestamp ranges cause ordering-dependent failures — always push second dataset past first's end date
- macOS grep lacks -P flag — use sed or awk for PCRE-style extraction

---

## Session 59 — 2026-03-19

**What changed:**
- `self-learning/trade_reflector.py` — NEW: MT-10 Phase 3A Kalshi trade pattern analysis (read-only SQLite, 5 detectors, structured proposals)
- `self-learning/tests/test_trade_reflector.py` — NEW: 47 tests (init, win rate drift, time-of-day, streaks, edge trend, sizing, proposals, edge cases)
- `FINDINGS_LOG.md` — 10 new entries: 5 Reddit r/ClaudeCode (context management 114pts, Zero-to-Fleet, markdownmaxxing, Okan, Superpowers), 5 GitHub MT-11 (engram, ClawMem, claude-mem, claude-context, awesome-toolkit)
- `SESSION_STATE.md` — Updated for S59
- `PROJECT_INDEX.md` — Added trade_reflector.py, updated test count to 2021/50 suites

**Why:**
- trade_reflector.py was the #1 priority from S58 — design doc was ready, pure code execution
- Hotspot available for first time this session — knocked out network-dependent Reddit + GitHub scans
- 10 findings provide ecosystem awareness for Frontier 1 (memory) and validate CCA's architectural approach

**Tests:** 2021/2021 passing (50 suites)

**Lessons:**
- S51 NEEDLE URLs not persisted — fresh scan was more productive than hunting lost references
- trade_reflector needs validation against real kalshi_bot.db schema before declaring production-ready

---

## Session 57 — 2026-03-19

**What changed:**
- `self-learning/research_outcomes.py` — NEW: Research ROI tracker (Delivery class, OutcomeTracker, FINDINGS_LOG parser, CLI)
- `self-learning/tests/test_research_outcomes.py` — NEW: 31 tests (Delivery, OutcomeTracker, ROI metrics, bulk import, FINDINGS_LOG parser)
- `self-learning/research_outcomes.jsonl` — NEW: 46 Kalshi research deliveries seeded (S50-S56)
- `self-learning/reflect.py` — Added `auto_reflect_if_due(every_n, session_id)` autonomous mid-session trigger
- `self-learning/tests/test_self_learning.py` — 6 new tests for auto_reflect_if_due (TestAutoReflect class)
- `design-skills/report_generator.py` — collect_self_learning() now reads research outcomes ROI data
- `CROSS_CHAT_INBOX.md` — S57 consolidated pickup checklist, research outcomes CLI docs
- `KALSHI_INTEL.md` — Updated self-learning infrastructure table with research_outcomes.py + micro_reflect
- `CCA_TO_POLYBOT.md` — Added research outcomes tracking instructions
- `cca-report-s57.pdf` — NEW: Professional CCA status report (261KB, Typst)

**Why:**
- Critical gap identified: no closed loop between CCA research recommendations and Kalshi profit outcomes
- micro_reflect() was built in S56 but not wired to fire autonomously — now triggers every N journal entries
- MT-17 (report PDF) was on the queue since S54
- VA wifi blocked all URL-dependent work — focused entirely on local code deliverables

**Tests:** 1946/1946 passing (48 suites)

**Lessons:**
- VA wifi is unreliable for Reddit/SSRN/GitHub — plan local-only tasks when on hospital network
- research_outcomes tracker should be seeded at delivery time, not retroactively (future: auto-seed in /cca-auto)

---

## Session 56 — 2026-03-19

**What changed:**
- `self-learning/reflect.py` — Added `micro_reflect(last_n=10)` for mid-session lightweight pattern detection
- `self-learning/tests/test_self_learning.py` — 10 new tests for micro_reflect (TestMicroReflect class, 101 total)
- `KALSHI_INTEL.md` — 18 verified academic papers + 4 GitHub repo evaluations + r/algotrading deep intelligence
- `CCA_TO_POLYBOT.md` — Massive S56 delivery: 6 actionable patterns, 3 top papers, Reddit intel, updated overnight recommendation
- `CROSS_CHAT_INBOX.md` — S56 notification to both Kalshi chats
- `FINDINGS_LOG.md` — 10 new entries across trading + Claude Code domains
- `MASTER_TASKS.md` — Priority queue refresh for S56

**Why:**
- Matthew directive: investigate how Kalshi chats track overnight profitability data — concern analysis is not optimal
- Tsang & Yang (2026) paper VALIDATES overnight liquidity thinning hypothesis (participation peaks 09-20 UTC)
- Self-learning only triggered at wrap time — micro_reflect() enables mid-session pattern detection
- VA hospital wifi blocked some URLs; pivoted to accessible sources for maximum research output

**Tests:** 1909/1909 passing (47 suites)

**Lessons:**
- r/Kalshi is mostly scam posts — pivot faster to higher-signal subreddits (r/algotrading, r/ClaudeCode)
- micro_reflect() fills the gap between wrap-only reflection and continuous monitoring
- No existing trading bot repo implements time-of-day filtering — CCA is ahead of ecosystem on this

---

## Session 52 — 2026-03-18

**What changed:**
- `KALSHI_INTEL.md` — 12 NEW verified academic papers with Python implementations (Papers 6-13: multinomial Kelly, E-values, DSR, profit vs info, fractional Kelly, wash trading, CPCV, BOCPD)
- `CROSS_CHAT_INBOX.md` — Updated notification for 12-paper delivery
- `LEARNINGS.md` — CCA dual mission (50% Kalshi + 50% self-improvement) codified as severity-3
- `FINDINGS_LOG.md` — OMEGA memory deep-dive (BUILD), trigger-table pattern, KG token optimization, CC March 2026 changelog
- `SESSION_STATE.md` — Full session progress + next priorities

**Why:**
- S51 resume prompt requested nuclear academic paper scan — delivered 12 papers covering Kelly, sequential testing, overfitting, changepoint detection
- CCA self-improvement side: Frontier 1 reconnaissance found OMEGA (95.4% LongMemEval) with 5 adaptable patterns
- PostCompact hook identified as immediate build opportunity from CC March 2026 changelog

**Tests:** 1768/1768 passing (44 suites)

**Lessons:**
- Reddit NEEDLE deep-reads via web search fail — posts are unfindable. Use reddit_reader.py or skip.
- CCA dual mission must be balanced: this session was ~70% Kalshi / 30% CCA. Next session should flip.

---

## Session 51 — 2026-03-19

**What changed:**
- `CROSS_CHAT_INBOX.md` — All 3 Kalshi Research S108 requests marked COMPLETE
- `~/.claude/cross-chat/CCA_TO_POLYBOT.md` — OctagonAI eval, Le (2026) calibration formula, FLB alert, Prime Directive reinforcement

**Why:**
- Matthew directive: ROI = make money. CCA research must generate profit for Kalshi bot.
- Le (2026) calibration formula is directly programmable: true_prob = p^b / (p^b + (1-p)^b)
- Political markets b=1.83 vs crypto b=1.03 → Pillar 3 expansion candidate (5-13x more mispriced)
- OctagonAI repo: 73/100 code, 25/100 strategy (LLM-as-edge is anti-pattern, don't adopt)

**Tests:** 1768/1768 passing (44 suites)

**Lessons:**
- PDF extraction needs poppler/PyPDF2 — neither installed. Use WebFetch HTML or browser for papers.
- Paper scanner domain keywords too broad for "prediction market" — returns soil chemistry papers.
- Reddit reader designed for single posts, not listing pages — use autonomous scanner for bulk.
- When Matthew says ROI, he means financial. Don't build iOS dashboards before profit research.

---

## Session 50 — 2026-03-19

- Cross-chat Kalshi bet sizing review (all 5 strategies)
- Academic research: CUSUM h=5.0, Kelly for pred markets, FLB short-horizon (14 verified citations)
- Meta labeling 23 features recommendation
- Parameter changes queue to CCA_TO_POLYBOT.md
- Added cross-chat inbox check to /cca-init

---

## Session 49 — 2026-03-18
- Committed S48 wrap files
- MT-13 Phase 2 COMPLETE: iOS project generator + Xcode build helper
  - `ios_project_gen.py`: generates complete Xcode projects from CLI (40 tests)
  - `xcode_build.py`: Python xcodebuild wrapper with error parsing (17 tests)
  - E2E validated: KalshiDashboard project builds + tests pass on iOS Simulator
  - Xcode 26.3 confirmed installed (Build 17C529)
- MT-17 Phase 4 COMPLETE: SVG chart generator + dashboard integration
  - `chart_generator.py`: 5 chart types (bar, h-bar, line, sparkline, donut), 42 tests
  - Integrated inline SVG charts into dashboard_generator.py
- Tests: 1768/1768 (44 suites)

---

## Session 48 — 2026-03-18

**What changed:**
- Built `session_pacer.py` — objective pacing for 2-3h autonomous /cca-auto runs (35 tests)
- Integrated session pacer into `/cca-auto` command (replaces hardcoded % thresholds)
- Wired pacer reset into `/cca-init` startup ritual
- MT-17 Phase 3 COMPLETE: `dashboard_generator.py` — self-contained HTML dashboard (33 tests)
- Created `/cca-dashboard` slash command for one-command dashboard generation
- Enhanced dashboard with live project data parsing (MASTER_TASKS, SESSION_STATE, PROJECT_INDEX)
- Updated PROJECT_INDEX (test counts, new files), MASTER_TASKS (MT-17 score)

**Why:**
- Matthew requested extended autonomous sessions; pacer gives Claude objective stop signals
- MT-17 Phase 3 delivers web-viewable project status — no Typst/PDF dependency needed
- Live data parsing means `/cca-dashboard` shows real project state, not demo data

**Tests:** 1686/1686 passing (42 suites) — +68 tests (+2 suites)
**Commits:** 8

**Lessons:**
- Session pacer + auto_wrap.py = objective pacing stack; no more guessing "am I at 60%?"
- HTML dashboards are trivially self-contained — inline CSS beats external deps for portability

---

## Session 47 — 2026-03-18

**What changed:**
- Created `/cca-slides` slash command (`.claude/commands/cca-slides.md`) — one-command slide generation
- Updated MASTER_TASKS.md priority scores: MT-14 (13.0->6.0), MT-17 (7.0->6.0)

**Why:**
- /cca-slides mirrors /cca-report pattern for quick presentation generation
- Priority queue was stale — MT-14 and MT-17 both completed work in S46 but scores weren't updated

**Tests:** 1618/1618 passing (40 suites)
**Commits:** 1

**Lessons:**
- Short housekeeping sessions are fine — keeps scores accurate and reduces debt for next session

---

## Session 46 — 2026-03-18

**What changed:**
- Wired resurfacer into /cca-init (Step 3: surfaces past findings at startup)
- MT-14 COMPLETE: All 15 subreddits scanned (7 new: r/webdev, r/iOSProgramming, r/MachineLearning, r/Bogleheads, r/stocks, r/SecurityAnalysis, r/ValueInvesting)
- MT-17 Phase 2 COMPLETE: Slide template + generator (25 tests, 5 slide types)
- CHANGELOG + LEARNINGS updated for Session 45 (deferred from S45 context limit)
- Checked cross-chat bridge — no Kalshi reply yet
- Committed Session 45 journal.jsonl

**Why:**
- Resurfacer integration prevents knowledge loss during session startup
- MT-14 completion means all subreddits have baseline scans for delta detection
- MT-17 slide generator enables professional presentation output

**Tests:** 1618/1618 passing (40 suites, +25 from slide generator)
**Commits:** 6

**Lessons:**
- Investing/general subs (r/stocks, r/Bogleheads) are noise for CCA — 98% NEEDLE rate means classifier is too broad
- Context limits hit at S45 end deferred wrap work — always budget 10% for wrap

---

## Session 45 — 2026-03-18

**What changed:**
- MT-10 Phase 3B COMPLETE: `self-learning/resurfacer.py` — findings re-surfacing module (41 tests)
- Cross-chat communication system: `CROSS_CHAT_INBOX.md` shared inbox + `bridge-sync.sh`
- `CCA_TO_POLYBOT.md` — Universal bet analytics framework (5 verified academic tools: SPRT, Wilson CI, Brier, CUSUM, FLB)
- `KALSHI_PRIME_DIRECTIVE.md` — permanent three-pillar cross-chat directive
- `CLAUDE.md` updated: read-only access to polymarket-bot for cross-chat bridge
- MT-14: Added r/AutoGPT + r/LangChain profiles, first scans (3 findings logged)
- Fixed 3 failing mobile_approver tests (Bash moved to ALWAYS_ALLOW_TOOLS)

**Why:**
- Cross-chat bridge enables CCA to serve Kalshi research (Matthew directive: 1/3 sessions on Kalshi)
- Resurfacer prevents knowledge loss — past reviews resurface when working on matching frontiers
- KALSHI_PRIME_DIRECTIVE documents the three pillars: perfect engine, deep research, expand beyond

**Tests:** 1593/1593 passing (39 suites, +41 new from resurfacer)
**Commits:** 8

**Lessons:**
- Cross-chat communication needs a protocol — unstructured bridge files get ignored
- Academic citation verification is non-negotiable (caught unverified references in first draft)
- r/AutoGPT and r/LangChain are moderate-yield for CCA frontiers (agent patterns relevant)

---

## Session 44 — 2026-03-18

**What changed:**
- MT-10 Phase 2 COMPLETE — 5/5 validation sessions across 36 transcripts (avg 70.8, improving trend)
- MT-10 Phase 3 scope expanded: findings re-surfacing (Matthew directive, Session 44)
- MT-13 research COMPLETE — `research/MT-13_ios_dev_research.md` (NEW) — full iOS/macOS dev landscape
- MT-8 scope closed — native Remote Control covers use case, remaining config outside CCA scope
- MT-14 first-time scans: r/MachineLearning (15 posts), r/webdev (25 posts), r/iOSProgramming (14 posts)
- 14 findings logged to FINDINGS_LOG.md (iOS ecosystem, r/ClaudeCode intel, r/MachineLearning)
- `MASTER_TASKS.md` — MT-10 Phase 2 marked complete, MT-13 research complete, MT-8 closed

**Why:**
- MT-10 Phase 2 validation reaching natural conclusion (5-session protocol)
- MT-13 hit decay cap (8.0, never touched) — research revealed Xcode 26.3 + Claude Agent SDK
- Matthew expanded MT-13 scope to include macOS apps for CCA tooling

**Tests:** 1552/1552 passing (38 suites, no changes)
**Commits:** 9

**Lessons:**
- Xcode 26.3 solves most of what MT-13 was created for — CCA's role shifts from "build capability" to "configure and template"
- r/webdev and r/MachineLearning are low-yield for CCA frontiers (mostly meta-discussion and pure research)
- Answering Matthew's strategic questions inline during /cca-auto is productive — captures directives that would otherwise be lost

---

## Session 43 — 2026-03-18

**What changed:**
- MT-10 Phase 2: Session 3/5 validation (4 transcripts, avg 71.25)
- MT-9 Phase 4: Deep-read 4 r/ClaudeAI posts (2 REFERENCE, 2 SKIP)
- 3 CCA reviews: design skills ADAPT, harness thread REF, TraderAlice REF-PERSONAL
- Design guide: quality gates + rules added to design-guide.md
- 4 new skillbook strategies (S10-S13) — CLAUDE.md routing, retrospectives, Read before Edit, bloat tracking
- r/ClaudeAI classifier cap fixed (needle_ratio_cap=0.4)
- LEARNINGS.md: PROJECT_INDEX.md retry hotspot (severity 2)

**Tests:** 1552/1552 passing (38 suites)
**Commits:** 6

---

## Session 42 — 2026-03-18

**What changed:**
- `MASTER_TASKS.md` — NEW priority decay scoring system (base_value + chats_untouched * aging_rate)
- MT-10 Phase 2: YoYo self-learning validation sessions 1-2/5 (4 transcripts analyzed, 13 proposals, scores 65-95)
- MT-9 Phase 3: Supervised autonomous scan trial on r/ClaudeAI (25 posts, 16 NEEDLEs)
- MT-11 Phase 2: Live GitHub API validated (30+ repos evaluated, 97 total in log)
- MT-12 Phase 2: Paper scanner across agents + prediction domains (40 papers, 21 logged)
- MT-8: Research complete — native Remote Control solves 90% of requirements
- `research/MT-8_remote_control_research.md` (NEW) — Remote Control setup guide

- Self-resolution scan: MT-1 (visual grid) and MT-5 (Pro bridge) mostly solved by community tools
- Scoring rule 6 added: self-resolution scan every 5 sessions

**6 MTs advanced in one session (first time). Decay system working: priorities shifted correctly after each sub-session.**

**Why:**
- Matthew requested working strictly from MT list by priority, with decay-based aging
- Force-multiplier criterion: work on what makes Claude smarter/faster first

**Tests:** 1552/1552 passing (38 suites, no changes)
**Commits:** 5

**Lessons:**
- Self-resolution scan should run at session START, not end — it changes the priority queue
- 3-session sub-session model works well for one chat (A/B/C structure)

---

## Session 41 — 2026-03-18

**What changed:**
- `design-skills/` (NEW MODULE) — Professional visual output via Typst
- `design-skills/report_generator.py` (NEW) — CCADataCollector + ReportRenderer + CLI, 21 tests
- `design-skills/templates/cca-report.typ` (NEW) — Status report Typst template (metric cards, module table, master tasks, priorities)
- `design-skills/design-guide.md` (NEW) — CCA visual language (8 colors, 7 typography levels, layout rules)
- `design-skills/CLAUDE.md` (NEW) — Module rules and architecture decisions
- `.claude/commands/cca-report.md` (NEW) — One-command PDF generation
- `MASTER_TASKS.md` — MT-17 scope expanded to PDFs + presentations + graphics + websites
- `PROJECT_INDEX.md` — Added design-skills module, updated test count
- `SESSION_STATE.md` — Updated with Session 41 work

**Why:**
- Matthew's CCA status report PDF was "atrocious" — needed professional-quality output
- MT-17 research (Session 40) selected Typst as the tool — this session built the implementation
- Matthew directive: design capabilities should cover all visual formats, not just PDFs

**Tests:** 1546/1546 passing (38 suites — +21 new tests, +1 new suite)

**Lessons:**
- Typst resolves `sys.inputs` paths relative to the template file — use `--root /` with absolute paths
- Typst compiles in <100ms — fast enough for interactive report generation
- TDD worked cleanly: 21 tests red -> green in one pass (only 1 integration fix needed)

---

## Session 40 — 2026-03-18

**What changed:**
- `self-learning/research/MT17_DESIGN_RESEARCH.md` (NEW) — Full PDF library comparison: Typst recommended over WeasyPrint/ReportLab for professional report generation
- `FINDINGS_LOG.md` — 3 new entries: Playwright CLI (407pts), Reddit MCP (62pts), Naksha v4 (25pts)
- `generate_report_pdf.py` — Committed from previous session (the "atrocious" PDF generator)
- `CCA_STATUS_REPORT_2026-03-17.txt` — Committed text report from previous session
- `SESSION_STATE.md` — Updated with Session 40 summary and next priorities

**Why:**
- MT-17 research phase needed: Matthew's PDF report was poor quality, Typst solves this with professional typography
- Paper deep-reads fulfill Session 39's priority #1 (top-scored papers from scanner)
- r/ClaudeCode weekly scan keeps intelligence current

**Papers deep-read:**
- Deep Research Agents (80pts, 117 citations) — agent taxonomy, MCP integration patterns
- HALO (75pts, 11 citations) — MCTS workflow optimization, 14.4% SOTA improvement
- AutoP2C (75pts, 14 citations) — paper-to-code generation pipeline

**Tests:** 1525/1525 passing (37 suites, no changes)

**Lessons:**
- Search for arXiv IDs before guessing — Semantic Scholar paper IDs != arXiv IDs
- Typst is the right tool for CCA: JSON-native, single binary, millisecond compile

---

## Session 39 — 2026-03-18

**What changed:**
- `FINDINGS_LOG.md` — 7 new reviews: YoYo v2 (REFERENCE), Design Studio (ADAPT->MT-17), Traul (REFERENCE), ClaudePrism (BUILD->MT-18), Autoresearch (ADAPT), Unsloth Studio (REFERENCE-PERSONAL->MT-19), reddit-mcp-buddy (REFERENCE)
- `MASTER_TASKS.md` — Created MT-17 (UI/Design Excellence + Report Generation), MT-18 (Academic Writing Workspace), MT-19 (Local LLM Fine-Tuning). Updated MT-12 status to Phase 1 COMPLETE. Updated priority order.
- `self-learning/paper_scanner.py` — Delay increased from 1.5s to 3s (429 rate limit fix)
- `self-learning/research/papers.jsonl` — 20 papers logged from 4-domain scan (agents, prediction, statistics, interaction)

**Why:**
- Matthew reviewed 7 Reddit posts and wanted findings documented as future tasks
- Paper_scanner needed rate limit fix (hit 429 at 1.5s in Session 38)
- 4-domain scan was next priority from Session 38 queue

**Tests:** 1525/1525 passing (no change)

**Lessons:**
- Design Studio top comment (130pts audit) shows community values honest evaluation — our /cca-review verdicts should be equally rigorous
- Paper_scanner at 3s delay successfully completed all 4 domains without 429 errors

---

## Session 38 — 2026-03-17

**What changed:**
- `agent-guard/path_validator.py` — Wired into live PreToolUse hooks (settings.local.json). Blocks system dir writes, destructive commands, path traversal. Fixed SyntaxWarning.
- `PROJECT_INDEX.md` — Trimmed 72% (441->122 lines, 28KB->5.5KB). Addresses 74% retry rate from trace analysis.
- `REFERENCE.md` — NEW: detailed API docs, test summary, architecture decisions, session history (moved from PROJECT_INDEX)
- `self-learning/paper_scanner.py` — NEW: MT-12 academic paper discovery. Semantic Scholar + arXiv APIs, 4 CCA domains, evaluation scoring, JSONL logging, CLI. 54 tests.
- `self-learning/research/papers.jsonl` — NEW: first paper logged (Agent0, 69/100 IMPLEMENT)
- `.claude/commands/cca-status.md` — NEW: /cca-status nuclear-level project overview command
- `.claude/commands/cca-auto.md` — Marathon mode for 2-hour autonomous sessions
- `CLAUDE.md` — Updated test commands section (was listing 8 suites/283 tests, now 37 suites/1525)

**Why:**
- path_validator was built in S37 but not wired — now live
- PROJECT_INDEX was the #1 retry hotspot (74% of sessions) — dramatic trim needed
- MT-12 academic paper integration was next on the roadmap
- Matthew requested nuclear overview command and 2-hour autonomous capability

**Tests:** 1525/1525 passing (was 1471, +54)

**Lessons:**
- Semantic Scholar shared rate limit is aggressive — 429 after rapid queries even with 0.5s delay. Need 1.5-3s between queries.
- macOS grep doesn't support -P flag — use awk/sed instead for Perl regex patterns

---

## Session 37 — 2026-03-17

**What changed:**
- `self-learning/batch_report.py` — NEW: Aggregate trace health across sessions (score dist, retry hotspots). 13 tests.
- `agent-guard/path_validator.py` — NEW: Dangerous path + command detection (traversal, rm -rf, dd, curl|bash). 30 tests.
- Sentinel dialed to 5-10%, scan limit enforced
- 31-session trace analysis: identified PROJECT_INDEX.md 74% retry rate

**Tests:** 1471/1471 passing (was 1428, +43)

---

## Session 29 — 2026-03-17

**What changed:**
- `context-monitor/hooks/meter.py` — CLAUDE_AUTOCOMPACT_PCT_OVERRIDE awareness: get_autocompact_pct(), compute_autocompact_proximity(), state file now includes autocompact_pct + autocompact_proximity. 10 new tests (62 total).
- `context-monitor/hooks/alert.py` — Autocompact proximity warnings: yellow zone alerts when approaching auto-compact (<10 points), red/critical messages include proximity. should_warn_autocompact() + updated should_alert/build_message signatures. 16 new tests (40 total).
- `context-monitor/statusline.py` — AC:Xpts display when approaching compaction. AC:NOW at threshold. _get_autocompact_pct(), _autocompact_proximity(), _format_autocompact_part(). Import os added.
- `context-monitor/tests/test_statusline.py` — NEW: First test suite for statusline.py. 24 tests covering thresholds, zones, bar, window format, autocompact proximity.
- `context-monitor/hooks/compact_anchor.py` — Autocompact proximity line in anchor output. IMMINENT at 0 points, "X points away" otherwise. 3 new tests (25 total).
- `self-learning/improver.py` — QualityGate class: geometric mean anti-gaming (Nash 1950 / sentrux pattern). 20 new tests (64 total).
- `spec-system/commands/design.md` — Performance Specifications section (call frequency, latency budget, resource constraints)
- `spec-system/commands/implement.md` — TDD red-green ordering enforced
- `spec-system/commands/tasks.md` — Demo field (observable outcome per task)
- `FINDINGS_LOG.md` — 19 new entries (18 r/ClaudeCode + 1 cerebellum repo)
- `MASTER_TASKS.md` — MT-7 marked COMPLETE, MT-10 updated with QualityGate + E2E validation

**Why:**
- CLAUDE_AUTOCOMPACT_PCT_OVERRIDE is a new Claude Code env var that changes when auto-compaction fires. Users with 1M context windows need awareness of approaching compaction to /compact proactively (prevents losing CLAUDE.md rules to the compaction bug).
- QualityGate prevents Goodhart's Law gaming in self-improvement loops — any zero metric tanks the composite score.
- Spec system enhancements from ADAPT findings: CAS demo statements, performance awareness, TDD ordering.

**Tests:** 1093/1093 passing (26 suites)

**Lessons:**
- Context-monitor module is now very well-covered (5 test suites, 178 tests). Next session should build outside this module.
- User feedback: focus on building, not re-scanning same subreddits. Consider diminishing returns.

---

## Session 28 — 2026-03-17

**What changed:**
- `self-learning/improver.py` — NEW: MT-10 YoYo improvement loop core. ImprovementProposal lifecycle (proposed -> approved -> building -> validated -> committed/rejected), ImprovementStore (JSONL persistence), ProposalGenerator (from_trace_report + from_reflect_patterns), risk classification (LOW/MEDIUM/HIGH), cross-session dedup, safety guards (protected files, max proposals per session, trading always HIGH)
- `self-learning/tests/test_improver.py` — NEW: 44 tests covering proposals, store, generator, risk classification, safety guards
- `self-learning/reflect.py` — Wired improver: analyze_current_session() auto-generates proposals, --propose flag, --session flag for tracking
- `agent-guard/hooks/network_guard.py` — NEW: AG-5 PreToolUse hook blocking port/firewall exposure. 20 threat patterns: adb tcpip, ufw disable/allow, iptables, docker -p, ngrok/cloudflared, nc/socat, python http.server, ssh -R 0.0.0.0, /etc/hosts, sshd_config
- `agent-guard/tests/test_network_guard.py` — NEW: 53 tests (port exposure, firewall mods, network config, safe commands, hook responses)
- `SESSION_STATE.md` — Updated to Session 28
- `PROJECT_INDEX.md` — Updated with new files, test counts
- `reddit-intelligence/profiles.py` — Added 5 investing/stocks subreddit profiles (r/investing, r/stocks, r/SecurityAnalysis, r/ValueInvesting, r/Bogleheads) per Matthew's directive
- `MASTER_TASKS.md` — MT-9 approved domains expanded with investing subs
- `FINDINGS_LOG.md` — 4 new entries from autonomous scanning (1M context, retry loops, Qwen browser, r/LocalLLaMA triage)

**Why:**
- MT-10 priority 1: YoYo self-learning loop closes the Observe -> Detect -> Hypothesize -> Build -> Validate -> Commit cycle. improver.py is the Hypothesize step.
- AG-5 from "We got hacked" BUILD verdict (458pts, r/ClaudeCode): Claude exposed ADB port 5555 on Hetzner VM, crypto miner exploited within hours. Community consensus: firewall-first, localhost-bind.
- Investing/stocks expansion: Matthew plans to use Claude for low-cost stock investing research long-term.

**Tests:** 1040/1040 passing (25 suites)

**Lessons:**
- Background agents lost to context compaction — process results within 5 minutes of spawn
- r/webdev and r/LocalLLaMA confirmed as low-signal for CCA (reinforces existing learning)

---

## Session 27 — 2026-03-17

**What changed:**
- `agent-guard/content_scanner.py` — NEW: AG-4 hazmat suit for autonomous scanning. 9 threat categories (executable_install, credential_harvest, data_exfiltration, financial_threat, system_damage, prompt_injection, scam_signals, low_quality_repo, malicious_url). 25+ regex patterns, phishing domain detection with whitelist, repo metadata scanning
- `agent-guard/tests/test_content_scanner.py` — NEW: 50 adversarial tests, zero false positives on 138 real posts
- `self-learning/reflect.py` — Added `analyze_current_session()` function + `--trace` CLI flag for trace analyzer integration
- `self-learning/journal.py` — Added `trace_analysis` event type
- `reddit-intelligence/findings/POLYBOT_DISHES.md` — NEW: 2 trading food dishes for Kalshi bot (Polymarket ghost fill exploit, mean reversion improvements)
- `FINDINGS_LOG.md` — 15 new entries: 2 BUILD, 3 ADAPT, 6 REFERENCE, 2 REFERENCE-PERSONAL, 1 SKIP, 1 inaccessible
- `MASTER_TASKS.md` — MT-15 added (detachable chat tabs)
- `PROJECT_INDEX.md` — Updated with content_scanner.py, test_content_scanner.py entries

**Why:**
- Matthew's directive: "hazmat suit before nuclear wasteland" — safety-first autonomous scanning
- Self-learning conquest: autonomously scan high-quality subreddits, filter rat poison, serve trading finds as food dishes to Kalshi bot
- Pipeline validation: prove profiles -> fetcher -> scanner -> deep-read -> findings works end-to-end before scaling to GitHub/papers

**Tests:** 943/943 passing (+50 from content_scanner)

**Lessons:**
- Validate post URLs before spawning deep-read agents — failed Reddit reads waste ~45k tokens per agent
- r/ClaudeAI post IDs from nuclear_fetcher month-view can differ from search results — verify URL before deep-read
- Phishing regex must use whitelist approach (check legit_domains first) to avoid false positives on anthropic.com
- Anthropic's memory feature is marketing-first (prompt export) — our local-first structured memory is architecturally ahead
- YoYo proves self-evolution loops work at $12/4 days — 4-gate safety model is the pattern for MT-10

---

## Session 25 — 2026-03-16

**What changed:**
- `ROADMAP.md` — complete overhaul: was stale since Session 1 (all frontiers showing "Research phase"), now reflects all 5 COMPLETE + 15 MTs with priorities
- `self-learning/research/TRACE_ANALYSIS_RESEARCH.md` — NEW: MT-7 research output. Full JSONL schema from 5 real transcripts, 6 pattern detector definitions with real-data thresholds
- `MASTER_TASKS.md` — 6 new master tasks (MT-9 through MT-14): autonomous subreddit intelligence (9 safety protections), YoYo self-learning loop, GitHub repo intelligence, academic paper integration, iOS app development, re-scanning previously scanned subs
- `CLAUDE.md` — NEW SECTION: 7 Cardinal Safety Rules (non-negotiable, override all other instructions, apply to all modes including overnight autonomy)
- `SESSION_STATE.md` — session 25 log, overnight 3-chat architecture, next priorities
- Memory: `feedback_cardinal_safety.md`, `project_overnight_3chat.md`

**Why:**
- Matthew's vision (Session 25): autonomous self-learning and self-building system that grows CCA and Kalshi bot without human intervention — with ironclad safety
- Anti-Frankenstein principle: every autonomous discovery must be objectively useful, clean, modular, tested, logged
- Cardinal safety rules established before overnight autonomy: never break anything, never expose credentials, never install malware, never risk financial loss
- Overnight architecture: exactly 3 chats (Kalshi main + Kalshi research + ONE CCA)

**Tests:** 800/800 passing (no new tests — research/planning session)

**Lessons:**
- ROADMAP.md going 24 sessions without update is a documentation debt anti-pattern — update docs same session as the work they describe
- Trace analysis research is code-ready: 6 pattern detectors with exact JSON field paths, real thresholds from 5 transcripts, recommended class architecture — next session should go straight to TDD
- Planning-only sessions (no code shipped) should be avoided when research is complete and implementation is ready

---

## Session 19 — 2026-03-16

**What changed:**
- `MASTER_TASKS.md` — new file: 6 master-level aspirational tasks (MT-0 through MT-5)
- `.claude/commands/cca-nuclear.md` — subreddit flexibility: accepts any subreddit as argument, file namespacing by slug
- `reddit-intelligence/nuclear_fetcher.py` — added `subreddit_slug()` function for filesystem-safe slug conversion
- `reddit-intelligence/tests/test_nuclear_fetcher.py` — 8 new slug tests (44 total)
- `scripts/kalshi-launch.sh` — new Terminal.app dual-window Kalshi launcher (replaces tmux approach)
- `FINDINGS_LOG.md` — frontend-design plugin entry upgraded from REFERENCE to ADAPT with full analysis
- `SESSION_STATE.md` — session 19 log, master-level tasks, updated priorities
- `PROJECT_INDEX.md` — added scripts/ directory, updated test counts
- Memory: `project_kalshi_self_learning.md`, `project_claude_pro_bridge.md`, `feedback_thoroughness.md`

**Why:**
- MT-0 (Kalshi self-learning integration) is the highest-stakes application of CCA's architecture — user identified research quality as the bottleneck
- Honest CCA vs YoYo analysis revealed 5 gaps: no autonomous loop, no codebase-as-memory, no pain/win tracking, no self-awareness, no pruning
- Nuclear subreddit flexibility enables scanning any subreddit with same pipeline (not just r/ClaudeCode)
- Terminal.app launcher is simpler and more reliable than tmux for dual-chat startup

**Tests:** 742/742 passing (20 suites, 8 new)

**Lessons:**
- Self-learning plateau is real (u/inbetweenthebleeps): optimizes mechanics not architectural judgment — design around this limitation
- "Evolution is in the artifact, not the weights" (liyuanhao) — the codebase IS the memory, not just the journal file

---

## Session 18 — 2026-03-16

**What changed:**
- `.claude/settings.local.json` — wired cost_alert.py as PreToolUse hook (fires on all tool calls, self-filters cheap tools)
- `~/.local/bin/dev-start` — rewrote as tmux split-pane launcher for Kalshi dual-chat automation (outside CCA scope, with user permission)
- `KALSHI_CHEATSHEET.md` — daily operations quick reference for Kalshi bot

**Why:**
- USAGE-3 cost alert hook needed to be live to warn/block on expensive sessions
- User needed one-command launch for two autonomous Kalshi bot chats with full instruction delivery
- Iterated through AppleScript (failed: accessibility/targeting), Claude Squad (failed: worktrees break shared filesystem), landed on tmux send-keys

**Tests:** 734/734 passing (20 suites)

**Lessons:**
- tmux `send-keys` with exact pane targeting is the reliable approach for scripted CLI input — AppleScript keystroke simulation is fragile and window-dependent
- `tmux kill-server` can corrupt the socket at `/private/tmp/tmux-501/default` — always clean the socket file if tmux refuses to start
- Claude Code sessions can't visually attach tmux — user must run the script from their own Terminal

---

## Session 16 — 2026-03-15

**What changed:**
- `usage-dashboard/usage_counter.py` — CLI token/cost counter reading transcript JSONL (sonnet/opus/haiku pricing, per-session/daily/weekly views)
- `usage-dashboard/arewedone.py` — structural completeness checker for all 7 modules (CLAUDE.md, source, tests, stubs, syntax)
- `.claude/commands/arewedone.md` — /arewedone slash command
- `.claude/commands/cca-wrap.md` — added Review & Apply self-learning phase
- `reddit-intelligence/CLAUDE.md` — module rules (was missing)
- `self-learning/CLAUDE.md` — module rules (was missing)
- Committed sessions 10-15 backlog (28 files, 5604 insertions)
- Installed claude-devtools v0.4.8, Claude Usage Bar v0.0.6, Claude Island v1.2

**Why:**
- USAGE-1 was the highest community demand from nuclear scan (9+ posts, 807pts OTel + 879pts devtools)
- /arewedone catches structural gaps that silently accumulate (found 2 missing CLAUDE.md files)
- Self-learning integration in /cca-wrap enables pattern detection at session boundaries
- 8-session commit backlog was a critical risk to work preservation

**Tests:** 568/568 passing (17 suites, 94 new)

**Lessons:**
- Test fixtures containing TODO/FIXME must be excluded from stub scanning
- Claude Island auto-installs hooks — don't launch while other CC sessions are active

---

## Session 14 — 2026-03-15

**What changed:**
- `self-learning/journal.py` — structured event journal (JSONL), CLI interface, nuclear metrics aggregation
- `self-learning/reflect.py` — pattern detection engine, strategy auto-adjustment, recommendation generator
- `self-learning/strategy.json` — tunable parameters for nuclear scan, session workflow, review strategy
- `self-learning/tests/test_self_learning.py` — 34 tests covering journal, stats, reflection, strategy apply
- `.claude/commands/cca-nuclear-wrap.md` — nuclear wrap command with 13-step self-learning integration
- `reddit-intelligence/findings/NUCLEAR_REPORT.md` — interim report with self-learning section added
- `reddit-intelligence/findings/nuclear_progress.json` — 45 post IDs reviewed
- `FINDINGS_LOG.md` — 22 new entries (nuclear scan batch 1)
- `SESSION_STATE.md` — session 14 log, nuclear progress, self-learning status
- `PROJECT_INDEX.md` — self-learning module added

**Why:**
- Nuclear scan systematically mines r/ClaudeCode for actionable patterns across all 5 frontiers
- Self-learning system adapted from YoYo pattern — tracks session outcomes, detects recurring patterns, suggests strategy tuning
- User requested self-learning deployed for CCA/CLI, not just Polybot

**Nuclear scan results (batch 1):**
- 45/110 posts reviewed | 2 BUILD | 8 ADAPT | 22.2% signal rate
- Top BUILD: OTel metrics for USAGE-1, claude-devtools for context observability
- 7 specific learnings captured to journal

**Tests:** 517/517 passing (15 suites)

**Lessons:**
- Self-learning journal must have SPECIFIC learnings, not vague summaries — "OTel better than transcript parsing" not "reviewed some posts"
- Posts >500pts have ~3x higher BUILD/ADAPT rate than posts 30-200pts

---

## Session 12 — 2026-03-15

**What changed:**
- `SESSION_STATE.md` — added MASTER PLAN section (unified workspace + self-learning architecture), session 12 work log, updated open items
- `FINDINGS_LOG.md` — 5 new entries (Claude Squad, Agent Deck, Codeman, NTM, 15-tool comparison), 27 total entries
- `CHANGELOG.md` — this entry
- `~/.local/bin/dev-start` — upgraded to auto-launch Claude in all 3 windows, idempotent re-attach
- `~/.local/bin/cs-start` — new Claude Squad launcher (backup)

**Why:**
- User wants all Claude Code sessions (CCA + 2 Kalshi) in one tmux window with zero manual setup
- Self-learning architecture designed for Polybot to adopt (journal + strategy feedback loop)
- Maestro (preferred UI) crashed on macOS 15.6 beta — fell back to tmux + dev-start

**Reddit reviews (6 new posts):**
- YoYo self-evolving agent (ADAPT, 941pts) — journal pattern for self-learning
- Crucix intelligence center (SKIP) — data dashboard, not agent management
- Maestro orchestrator (BUILD, 476pts) — built from source, crashed on SDK issue
- Maestro teaser (REFERENCE, 424pts) — confirms demand
- Agent Teams walkthrough (ADAPT, 461pts) — sendMessage pattern, Cozempic pruner
- Personal Claude setup / Adderall (same as Maestro)

**Infrastructure:**
- Maestro v0.2.4 built (crashed — macOS 15.6 beta _NSUserActivityTypeBrowsingWeb)
- Claude Squad v1.0.17 installed via brew
- tmux workspace: 3 windows, Claude auto-launched, 20/20 integration tests passing
- CShip statusline verified rendering in tmux

**Tests:** 483/483 passing

**Lessons:**
- Tauri apps built from source may crash on beta macOS due to SDK symbol changes — always have a CLI fallback
- tmux is more reliable than native desktop apps for multi-session management (no SDK dependencies)
- Self-learning agent architecture = shared journal + reflection step + minimum sample sizes — adapted from YoYo pattern

---

## Session 11 — 2026-03-15

**What changed:**
- `FINDINGS_LOG.md` — 9 new entries (4 batch 1 + 5 batch 2), introduced REFERENCE-PERSONAL verdict
- `LEARNINGS.md` — new Severity 2: file-writing hooks trigger system-reminder context burn (160k tokens/3 rounds)
- `SESSION_STATE.md` — 7 new open items (UserPromptSubmit hook, linked repos, compact anchor investigation, Recon install, ClaudePrism, trading refs, agtx)
- `.claude/commands/cca-review.md` — added REFERENCE-PERSONAL verdict option + synced to global
- Memory: user_profile.md (psychiatry resident, Kalshi/trading, academic writing), feedback_personal_tools.md

**Reddit reviews (9 posts):**
- Algotrading strategy list (REFERENCE-PERSONAL, 534pts)
- VEI volatility signal (REFERENCE-PERSONAL, 436pts)
- "claude on a crusade" meme (REFERENCE — Holy Order + superpowers links)
- Beast post 6-month tips (ADAPT — skill auto-activation, build checker, context burn warning)
- ClaudePrism academic workspace (REFERENCE-PERSONAL)
- code-commentary sports narrator (SKIP)
- Recon tmux dashboard (BUILD — 530pts, multi-agent visibility)
- Membase memory layer (REFERENCE — conflict resolution pattern)
- agtx terminal kanban (REFERENCE — worktree isolation, GSD plugin)

**Infrastructure installed:**
- tmux 3.6a, Rust 1.94.0, Recon v0.1.0 (tmux-native CC agent dashboard)
- ~/.tmux.conf with Recon keybindings
- ~/.local/bin/dev-start (3-window tmux: CCA + 2 Kalshi sessions)

**Key findings:**
- UserPromptSubmit hook for skill auto-activation is a new pattern CCA doesn't have
- File-writing hooks (Prettier, compact_anchor) silently burn context via system-reminder diffs
- Recon solves the multi-chat management problem using tmux + CC's own session JSON files

**Tests:** 483/483 passing (no changes to code)

**Lessons:**
- Don't dismiss tools outside CCA frontiers — use REFERENCE-PERSONAL for personally useful tools (trading, academic writing)
- Commit backlog has grown across 3 sessions — must commit first thing next session

---

## Session 10 — 2026-03-15

**What changed:**
- `.claude/commands/cca-wrap.md` — new session end ritual (self-grade, learnings, resume prompt)
- `.claude/commands/cca-scout.md` — autonomous subreddit scanner for high-signal posts
- `CLAUDE.md` — added "URL Review — Auto-Trigger" section + "Session Commands" table
- `FINDINGS_LOG.md` — 8 new entries from Reddit reviews
- All 5 /cca-* commands copied to `~/.claude/commands/` for global availability
- Verified: CShip v1.0.80, RTK v0.29.0, mobile approver hook, claude-code-transcripts

**Why:**
- User needed effortless Reddit review pipeline — paste URL, get verdict, auto-log
- Session management commands bring CCA to parity with polybot framework patterns
- Global commands mean /cca-review and /cca-scout work from any project folder

**Tests:** 483/483 passing (13 suites — no new test files, count increase from existing suites)

**Lessons:**
- Project-scoped commands (`.claude/commands/`) only work when Claude Code is launched from that folder. Copy to `~/.claude/commands/` for global availability.
- Reddit JSON API `top` without `t=month` param only returns ~24hr top. Need to add time range support to reddit_reader.py.
- CCA scope boundary prevents installing tools outside the project folder — batch installs into one non-CCA terminal session.

---

## Session 9 — 2026-03-15

**What changed:**
- SESSION_STATE.md updated to reflect 404/404 tests and session 9 wrap
- CHANGELOG.md created (this file)
- LEARNINGS.md created

**Why:**
- Wrap-only session. No new code. Confirmed all 13 suites pass (404 tests total).
- Identified critical gap: sessions 7+8 work (AG-2, AG-3, CTX-1–5, MEM-5, reddit-intel) was
  never committed despite being complete and tested.

**Tests:** 404/404 passing

**Lessons:**
- Sessions must commit before closing. Having 83+ untracked files across multiple sessions
  is a recovery liability. Commit discipline: ship each task, commit before the next.

---

## Session 8 — 2026-03-08

**What changed:**
- `context-monitor/hooks/auto_handoff.py` — CTX-4: Stop hook blocks exit at critical context
- `context-monitor/hooks/compact_anchor.py` — CTX-5: writes anchor file every N tool calls
- `context-monitor/tests/test_auto_handoff.py` — 27 tests
- `context-monitor/tests/test_compact_anchor.py` — 22 tests
- `memory-system/cli.py` — MEM-5: CLI viewer (list/search/delete/purge/stats)
- `memory-system/tests/test_cli.py` — 28 tests
- `agent-guard/ownership.py` — AG-2: ownership manifest CLI
- `agent-guard/tests/test_ownership.py` — 27 tests
- `.claude/commands/ag-ownership.md` — slash command
- CTX-1 bug fix: transcript format corrected (entry["message"]["usage"] for assistant entries)
- `context-monitor/tests/test_meter.py` — grew from 33 to 36 tests

**Why:**
- Context Monitor frontier completion (CTX-4/5 were the last two hooks)
- Memory system CLI gives users introspection into stored memories
- Ownership manifest helps multi-agent sessions detect file contention

**Tests:** 321/321 passing (sessions 7+8 combined, before credential_guard + reddit_reader)

**Lessons:**
- Stop hook block format: `{"decision": "block", "reason": "..."}` — different from PreToolUse
  which uses `hookSpecificOutput.permissionDecision`
- argparse subparsers don't inherit parent options — add `--project` to each subcommand

---

## Session 7 — 2026-03-01 (approx)

**What changed:**
- `reddit-intelligence/` — full plugin: reddit_reader.py, 43 tests, ri-scan/ri-read/ri-loop commands
- `reddit-intelligence/tests/test_reddit_reader.py` — 43 tests
- `.claude/commands/reddit-intel/` — symlinks to plugin commands
- `agent-guard/hooks/credential_guard.py` — AG-3: credential-extraction guard
- `agent-guard/tests/test_credential_guard.py` — 40 tests
- `context-monitor/hooks/meter.py` — CTX-1: token counter PostToolUse hook
- `context-monitor/hooks/alert.py` — CTX-3: PreToolUse alert for expensive tools
- `context-monitor/statusline.py` — CTX-2: ANSI statusline
- `context-monitor/tests/test_meter.py` — 33 tests
- `context-monitor/tests/test_alert.py` — 24 tests

**Why:**
- Context Monitor and Agent Guard frontiers largely completed in this session block
- reddit-intel provides ongoing community signal research for frontier validation

**Tests:** Suites passing; exact count captured in session 8

**Lessons:**
- Transcript path: `project_hash = os.getcwd().replace('/', '-')` → `~/.claude/projects/<hash>/<session>.jsonl`
- Real Claude Code transcripts: usage at `entry["message"]["usage"]`, not `entry["usage"]`

---

## Sessions 1–6 — 2026-02-19 to 2026-03-01

**What changed (cumulative):**
- Frontier 1 (memory-system): MEM-1 schema, MEM-2 capture hook, MEM-3 MCP server, MEM-4 /handoff, MEM-5 CLI
- Frontier 2 (spec-system): SPEC-1–6 slash commands + guard hook
- Frontier 4 (agent-guard): AG-1 mobile approver (iPhone push via ntfy.sh)
- Foundation: CLAUDE.md, PROJECT_INDEX.md, SESSION_STATE.md, ROADMAP.md, MASTER_ROADMAP.md
- Research: reddit_scout.py, EVIDENCE.md, browse-url global skill

**Why:**
- Initial project build-out — all five frontiers scoped and first three completed

**Tests:** 157/157 passing (as of session 6)

**Lessons:**
- PreToolUse deny: `hookSpecificOutput.permissionDecision: "deny"` — top-level `decision: "block"` silently fails
- Anthropic key regex must include hyphens: `sk-[A-Za-z0-9\-]{20,}` not `sk-[A-Za-z0-9]{20,}`
- Memory ID suffix: 8 hex chars minimum (3-char caused collisions at 100 rapid-fire creates)

---

## Session 21 — 2026-03-16

**What changed:**
- `self-learning/journal.py` — 6 trading event types (bet_placed, bet_outcome, market_research, edge_discovered, edge_rejected, strategy_shift), trading domain, get_trading_metrics(), trading-stats CLI
- `self-learning/reflect.py` — 4 trading pattern detectors (losing_strategy, research_dead_end, negative_pnl, strong_edge_discovery), trading metrics in report output
- `self-learning/strategy.json` — trading section (min_sample_bets, min_liquidity, win_rate_alert_below, etc.) + 4 bounded params
- `self-learning/tests/test_self_learning.py` — 24 new tests (51 -> 75)
- `spec-system/commands/design-review.md` — NEW: multi-persona design review (4 expert personas)
- `.claude/commands/spec-design-review.md` — NEW: thin wrapper for /spec:design-review
- `spec-system/commands/design.md` — Section 1b "Design References" for UI/visual features
- `MASTER_TASKS.md` — MT-0/MT-2/MT-3/MT-4 status updated to COMPLETE

**Why:**
- MT-0: Kalshi self-learning integration — build the trading domain schema in CCA as R&D before deploying to polymarket-bot
- MT-3: Multi-persona design review catches blind spots that single-perspective reviews miss
- MT-4: Design vocabulary ensures professional-quality UI from the spec phase

**Tests:** 783/783 passing (24 new)

**Lessons:**
- Edit tool refuses after system-reminder clears file context — read immediately before editing files in spec-system/ or other dirs that trigger CLAUDE.md injection

---

## Session 23 — 2026-03-16

**What changed:**
- `reddit-intelligence/findings/nuclear_queue_anthropic.json` — 75 posts fetched and classified
- `reddit-intelligence/findings/nuclear_progress_anthropic.json` — scan complete
- `reddit-intelligence/findings/NUCLEAR_REPORT_anthropic.md` — full report: 0 BUILD, 6 REF, 65 FAST-SKIP
- `reddit-intelligence/findings/nuclear_queue_algotrading.json` — 98 posts fetched and classified
- `reddit-intelligence/findings/nuclear_progress_algotrading.json` — scan complete
- `reddit-intelligence/findings/NUCLEAR_REPORT_algotrading.md` — full report: 0 BUILD, 4 REF, 3 REF-PERSONAL
- `FINDINGS_LOG.md` — 35 new entries (r/Anthropic + r/algotrading)
- `SESSION_STATE.md` — session 23 log

**Why:**
- Session 22 resume prompt specified nuclear scans for r/Anthropic and r/algotrading as top priorities
- r/Anthropic: validate whether general Anthropic sub has CCA-relevant signal (answer: no, ~85% politics noise)
- r/algotrading: find prediction-market infrastructure for Polybot (found PMXT: free orderbook data)

**Tests:** 783/783 passing (no code changes)

**Lessons:**
- r/Anthropic is ~85% politics/corporate noise — not worth nuclear scanning for CCA
- r/algotrading is domain-specific — only prediction-market posts have Polybot relevance
- r/ClaudeCode remains the ONLY high-signal sub for CCA frontiers
- Title-based triage (learned Session 22) saved massive tokens — applied successfully to both subs
- All 4 nuclear scans now COMPLETE: 411 total posts scanned across 4 subreddits

---

## Session 24b (Continuation) — 2026-03-16

**What changed:**
- FINDINGS_LOG.md — 3 new entries (151 total): mass-building post, ACE trace analysis, traul comms search
- MASTER_TASKS.md — 3 new master tasks (MT-6, MT-7, MT-8) with full lifecycle requirements
- LEARNINGS.md — New Severity 3 entry: "Building without testing/validation is wasted work"
- SESSION_STATE.md — Updated with Session 24b work + revised next priorities

**Why:**
- Matthew requested reviews of 3 Reddit posts (one flagged as "potentially huge")
- Matthew directed: expand nuclear scanner, add iPhone remote control task, and ensure all work has full lifecycle (research/plan/build/test/validate/backtest/iterate)
- Matthew's key directive: "building doesn't mean shit without legitimate framework, testing, and proven ideas and success"

**Tests:** 800/800 passing

**Lessons:**
- ACE framework's RLM Reflector pattern (programmatic trace querying) is the highest-signal self-learning upgrade found in 411+ posts scanned
- Every MT now requires explicit lifecycle documentation — not just "build X" but the full validation chain
- ROADMAP.md still stale (Session 1) — must be updated next session (5-minute fix deferred 23 sessions)

---
## Session 26 — 2026-03-17

**What changed:**
- `self-learning/trace_analyzer.py` — NEW: MT-7 implementation. 7 classes: TranscriptEntry, TranscriptSession, RetryDetector, WasteDetector, EfficiencyCalculator, VelocityCalculator, TraceAnalyzer. CLI entry point with --json flag.
- `self-learning/tests/test_trace_analyzer.py` — NEW: 50 tests covering all 7 classes (TDD green-field)
- `SESSION_STATE.md` — updated to Session 26, next priority queue
- `PROJECT_INDEX.md` — updated test count to 850/850, new file entries, session history row

**Why:**
- MT-7 trace analysis research was 100% complete (TRACE_ANALYSIS_RESEARCH.md had full schema + 6 pattern defs). Implementation was the logical next step. Tool validates against real data immediately — 3 transcripts analyzed, scores 15/85/40.

**Tests:** 850/850 passing (21 suites)

**Lessons:**
- SESSION_STATE.md is the #1 retry-loop offender in real transcript analysis (5-8 consecutive Edits detected). This is expected for doc-update patterns; orientation files should probably be exempted from RetryDetector the same way WasteDetector exempts them.
- trace_analyzer validates immediately against real data with no schema changes needed — TRACE_ANALYSIS_RESEARCH.md was thorough enough to go straight to code.

---


## Session 36 — 2026-03-17

**What changed:**
- `.claude/commands/cca-wrap.md` — exit loop fix + validate_strategies (6h) + Sentinel evolve (6g.5)
- `.claude/commands/cca-auto.md` — exit loop fix
- `.claude/commands/cca-nuclear-wrap.md` — exit loop fix
- `self-learning/improver.py` — SentinelMutator class (mutate_from_failure, cross_pollinate, scan_weaknesses), Improver.evolve(), MUTATION_STRATEGIES dict
- `self-learning/tests/test_sentinel.py` — 26 tests for Sentinel
- `self-learning/improvements.jsonl` — 6 proposals from 3 real transcript traces
- `FINDINGS_LOG.md` — 5 new reviews (usage tracker, devtools, receipts, 25 tips, Anthropic harness)
- `reddit-intelligence/github_evaluations.jsonl` — 30 repos from 4 GitHub queries

**Why:**
- Exit loop: Claude kept saying "Done."/"Exit." after session wrap — no terminal stop instruction
- Sentinel: Matthew's directive for X-Men Sentinel-style adaptive self-learning
- MT-10: Generate real data for 5-session validation run
- MT-11: First live GitHub scan to find frontier-relevant repos

**Tests:** 1428/1428 passing (+26 sentinel)

**Lessons:**
- Exit loop is an LLM behavior pattern — completion signals ("done") trigger self-response loops. Fix with explicit "STOP RESPONDING" in command templates.
- Don't stop between /cca-init and /cca-auto to explain things — just keep working.

---

## Session 37 — 2026-03-17

**What changed:**
- `self-learning/improver.py` — Sentinel mutation dialed to 5-10% (MAX_MUTATIONS_PER_CYCLE: 5->2, MAX_MUTATION_DEPTH: 3->2)
- `self-learning/strategy.json` — scan limit params (max_consecutive_scan_sessions: 3, scan_cooldown_build_sessions: 2)
- `.claude/commands/cca-auto.md` — scan limit enforcement + context budget for wrap (stop at 60%, not 75%)
- `self-learning/batch_report.py` — NEW: aggregate trace health CLI (score distribution, retry hotspots, waste stats)
- `self-learning/tests/test_batch_report.py` — 13 tests
- `agent-guard/path_validator.py` — NEW: AG-7 dangerous path + command detection (system dirs, traversal, rm -rf, dd, curl|bash)
- `agent-guard/tests/test_path_validator.py` — 30 tests
- `FINDINGS_LOG.md` — 3 new GitHub repo evaluations (engram 1.5K, hooks-mastery 3.3K, multi-agent-coordination)
- MT-10: 31-session aggregate trace analysis (avg score 70, PROJECT_INDEX.md 74% retry rate)

**Why:**
- Sentinel 20% was arbitrary and risky — Matthew requested conservative 5-10% ceiling
- Scan limit: too many consecutive scan sessions without building — need to ship code
- Context budget: wrap self-learning ritual needs 15-20% context, was being squeezed out
- batch_report validates trace_analyzer on real data and provides ongoing health monitoring
- path_validator addresses BUILD findings from r/vibecoding (GPT wiped F: drive, Codex deleted S3)

**Tests:** 1471/1471 passing (+43: 13 batch_report, 30 path_validator)

**Lessons:**
- TraceAnalyzer API: constructor takes path string, not session object. Analyze() returns flat dict (waste/retries/efficiency/velocity), not nested detectors dict.
- PROJECT_INDEX.md retried in 74% of sessions — biggest single efficiency win. Next session should restructure or cache.

---

## Session 43 — 2026-03-18

**What changed:**
- `self-learning/journal.jsonl` — MT-10 validation 3/5 event logged (4 transcripts, avg 71.25)
- `FINDINGS_LOG.md` — 7 new findings: Recon Tamagotchi, 14yr journals, vibe coding, interactive, design skills, harness setups, TraderAlice
- `design-skills/design-guide.md` — Added Rules Do/Don't, Quality Gates, external design references (typeui.sh)
- `self-learning/SKILLBOOK.md` — 4 new strategies (S10-S13), APF updated to 31.4%, growth metrics through S43
- `reddit-intelligence/profiles.py` — r/ClaudeAI needle_ratio_cap=0.4, tightened keywords
- `LEARNINGS.md` — PROJECT_INDEX.md retry hotspot (severity 2), r/ClaudeAI classifier (severity 1)
- `SESSION_STATE.md` — Full 5-sub-session documentation

**Why:**
- MT-10 Phase 2 validation (session 3/5) — measuring self-learning system effectiveness across 37 real sessions
- MT-9 Phase 4 — deep-reading r/ClaudeAI NEEDLE posts for frontier intelligence
- Matthew-requested reviews (3 URLs) — design skills, harness setups, trading bot
- Self-learning expansion — encoding cross-project learnings as actionable strategies

**Tests:** 1552/1552 passing (38 suites, no changes)

**Lessons:**
- Always Read source files before calling functions — wasted cycles guessing class/method names on improver.py, journal.py
- r/ClaudeAI classifier at 76% NEEDLE is too loose — fixed with needle_ratio_cap=0.4
- Cross-project strategies (S10-S13) strengthen the self-learning system beyond CCA-specific patterns

---

## Session 50 — 2026-03-19

**What changed:**
- `.claude/commands/cca-init.md` — Added Step 2.5: cross-chat inbox check (POLYBOT_TO_CCA.md)
- `CROSS_CHAT_INBOX.md` — Marked CUSUM threshold request as DELIVERED
- `~/.claude/cross-chat/CCA_TO_POLYBOT.md` — First-ever responses: CUSUM h=5.0 analysis, Kelly/FLB/Bayesian research, bet sizing review, meta labeling features

**Why:**
- 3 URGENT cross-chat requests from Kalshi S105-S108 had been unanswered for 24h
- Cross-chat communication gap: /cca-init never checked the inbox
- Matthew requested objective review of live bet sizing and values

**Tests:** 1768/1768 passing (44 suites)

**Lessons:**
- Research agents timeout when given 4+ web search topics. Break into 1-topic-per-agent.
- Cross-chat outbox was empty for entire project lifetime — add inbox check to init sequences.

---

## Session 64 (continued) — 2026-03-20

**What changed:**
- Responded to ALL 12 pending Kalshi research requests (REQ 4-12) in `CCA_TO_POLYBOT.md`
- Objective hour-block analysis: 08:xx UTC (z=-4.30, p<0.0001) and 00:xx NO-side (z=-3.26, p<0.001) are the only statistically justified blocks
- Feature importance ranking for meta-labeling (Lopez de Prado framework applied to signal_features)
- ETH price bucket analysis (n=9-14 = noise, Wilson CIs overlap)
- Sol_drift Stage 3 pathway (Kelly says scale with bankroll, no shortcuts)
- XRP structural mechanism documented (thin books, Asia concentration, NO-side FLB asymmetry)
- Regime detection pointers (Hamilton HMM, Ardia GARCH, GARCH-Kelly)
- Volatility filter code scaffold (Option B: 1% 5-min change threshold)
- Earnings Mentions markets assessed (low priority, park for now)

**Why:**
- Matthew frustrated that cross-chat requests were unanswered for multiple sessions
- Urgent need to coordinate all 3 chats on overnight bet blocking — objective basis required

**Tests:** 2150/2150 passing (52 suites)

**Lessons:**
- Cross-chat bridge files at ~/.claude/cross-chat/ — always check there FIRST for pending requests
- Only z-scores exceeding -2.0 (p<0.05) should drive blocking decisions; marginal hours (z=-0.96 to -1.23) should be monitored, not blocked

---

## Session 70 — 2026-03-19

**What changed:**
- `self-learning/research/SENIOR_DEV_AGENT_RESEARCH.md` — NEW: Nuclear-level research for the Senior Developer Agent master task (677 lines, 11 verified papers, 5 open-source tools, industry standards synthesis, MVP architecture defined)

**Why:**
- Matthew requested a research-only session to ground the Senior Dev Agent in real engineering practices before any PLAN.md or implementation. Research must precede planning for a master-level task.

**Tests:** 2563/2563 passing (62 suites — 3 new suites from other chats visible this session)

**Lessons:**
- paper_scanner.py evaluate() 404s on all Semantic Scholar URLs — use WebFetch on arXiv directly instead
- paper_scanner.py search() returns low-signal results for SE topics — always supplement with direct WebSearch + WebFetch on high-citation papers; the scanner is better suited for prediction/agent/statistics domains
- Multiple background agents (7 parallel) can efficiently cover a large research space; synthesizing their outputs in a single sequential pass produces a coherent document without redundancy

---

## Session 72 Addendum — 2026-03-20 (cli2 post-wrap work)

**What changed:**
- `agent-guard/adr_reader.py` — NEW: ADR Reader (31 tests). Discovers Architectural Decision Records, parses MADR/Nygard/inline formats, surfaces relevant accepted/deprecated decisions via PostToolUse hook. Extends MT-20 Full Vision.
- `agent-guard/tests/test_adr_reader.py` — NEW: 31 tests covering discovery, parsing, relevance, hook I/O.
- `SESSION_STATE.md` — UPDATED: cli2 delivery complete, test count to 2897 (72 suites).
- `SESSION_RESUME.md` — UPDATED: ADR reader noted for next session.

**Why:**
- MT-20 Full Vision explicitly listed ADR Reader as next phase after MVP. Building it extends value of the senior dev agent from reactive (catch markers) to proactive (recall architectural decisions).

**Tests:** 2897/2897 passing (72 suites)

**Lessons:**
- In hivemind mode, check git status BEFORE building new modules — parallel chats may have already committed the file you're about to build. Avoids both redundant work and merge confusion.
- When another chat commits a file you were about to build, verify it's complete and test-covered before moving on, don't just skip it.

---
## Session 73 — 2026-03-20

**What changed:**
- `agent-guard/satd_detector.py` (44 tests) — SATD marker detection PostToolUse hook (TODO/FIXME/HACK/WORKAROUND/DEBT/XXX/NOTE with severity)
- `agent-guard/effort_scorer.py` (42 tests) — PR effort scoring 1-5 scale (Atlassian/Cisco LOC thresholds + complexity markers)
- `agent-guard/fp_filter.py` (40 tests) — False positive filter: test file / vendored file detection, confidence scoring
- `agent-guard/review_classifier.py` (43 tests) — CRScore-style category classifier (6 categories, NAACL 2025 priority scores)
- `agent-guard/tech_debt_tracker.py` (27 tests) — SATD trend tracker: scan, persist snapshots JSONL, hotspot detection with trends
- `resume_generator.py` (17 tests) — Auto-generate fresh SESSION_RESUME.md from SESSION_STATE.md when stale
- `cca-loop` script: `get_resume_prompt()` calls resume_generator.py if SESSION_RESUME.md is >6h stale
- Fixed: `cca_internal_queue.py` KeyError for unknown senders (hivemind) via `.get()` instead of direct dict lookup
- Fixed: effort_scorer subprocess test bug — relative script path vs absolute cwd mismatch

**Why:**
- MT-20 Senior Dev Agent MVP: research-backed hook chain to surface code quality issues before they ship
- cca-loop hardening: stale resume prompt was a root cause of degraded loop sessions (S67 content surviving into S69)

**Tests:** 2897/2897 passing (72 suites)

**Lessons:**
- Read `git log --oneline -10` at session start when resuming after a context limit — loop may have already built files you're about to build. Saves time and avoids duplicate commits.
- For subprocess tests: use `os.path.join(os.path.dirname(os.path.abspath(__file__)), "script.py")` for the script path, not a relative string, to avoid cwd-relative resolution errors.

---
## Session 74 (cli1) — 2026-03-20

**What changed:**
- `~/.local/bin/cca-loop`: Added `CCA_LOOP_SESSION_TIMEOUT` (default 90min) — `wait_for_claude_exit()` tracks elapsed, sends `/cca-wrap` at limit, 60s grace, returns code 3
- `~/.local/bin/cca-loop`: Added `notify_error()` — POSTs to ntfy.sh `cca-loop-alerts` on timeout (curl only, no new deps)
- `~/.local/bin/cca-loop`: Hardened `check_live_cca_sessions()` with `lsof +D CCA_DIR` to detect Desktop Claude Code app sessions that don't appear in ps argv
- `tests/test_loop_health.py`: Converted from pytest to stdlib unittest (54 tests, project convention)

**Why:**
- cca-loop sessions running indefinitely if Claude got stuck; needed automatic timeout + alert
- Desktop Claude Code app wasn't detected by ps-based dedup, allowing duplicate sessions
- test_loop_health.py used pytest which is not installed; caused test suite failure

**Tests:** 2980/2980 passing (73 suites)

**Lessons:**
- Always write tests with `unittest` — pytest is not installed in this project environment
- lsof-based process detection catches GUI/Electron apps that ps-argv misses

---

## Session 79 — 2026-03-20

**What changed:**
- `agent-guard/coherence_checker.py` — Added `RuleExtractor` (parses CLAUDE.md rule sections) + `RuleComplianceCheck` (validates code against rules, e.g., stdlib-only import checking). Project-root CLAUDE.md rules now apply to all modules.
- `agent-guard/senior_review.py` — Wired `FPFilter` (vendored=skip, test=reduced), `ADRReader` (discover + relevance matching), added `fp_confidence` and `relevant_adrs` to metrics. Now orchestrates 7 submodules.
- `agent-guard/senior_chat.py` — NEW: Interactive CLI chat mode (Phase 8). ReviewContext builder, terminal-formatted output, LLM prompt generator, argparse CLI with REPL + single-question modes.
- `.claude/commands/senior-review.md` — Enhanced output template with blast radius, fp_confidence, ADRs, coherence issues.
- `SENIOR_DEV_GAP_ANALYSIS.md` — Updated: 7/10 gaps closed in S78-S79, remaining gaps require LLM integration.

**Why:**
- Completing all 3 S78 priority items (Phase 9 completion, fp_filter wiring, ADR wiring)
- Building Phase 8 (interactive CLI chat) — Matthew's vision of senior dev as conversational colleague
- Closing the gap between "linter with a name" and actual senior developer experience

**Tests:** 3129/3129 passing (78 suites, 44 new tests this session)

**Lessons:**
- fp_filter integration order matters: must run BEFORE SATD counting, not after, to get correct totals
- Project-root CLAUDE.md rules serve as a "global policy" layer that module rules can't override

---

## Session 128 — 2026-03-23

**What changed:**
- `cca_autoloop.py`: Fixed Terminal.app close race condition, added pre-flight checks, rate limit handling, stale resume detection, prompt truncation, missing `--dangerously-skip-permissions` in Python wrapper
- `start_autoloop.sh`: Same fixes — pre-flight checks, rate limit cooldown, terminate dialog handling, retry close, orphan cleanup
- `tests/test_cca_autoloop.py`: 85 → 116 tests (+31 new)

**Why:**
- Production hardening for the autoloop (MT-30 Phase 8). S127 built the desktop mode but had race conditions and missing obstacle handling that would block live usage.
- Matthew flagged Terminal.app "terminate?" confirmation dialogs as a blocking issue.

**Tests:** 204/204 suites, ~8156 tests passing

**Lessons:**
- Terminal.app `close w` triggers a "terminate?" dialog if shell hasn't fully exited — must wait for clean exit before closing
- Self-close from within a wrapper script races with `exit` — always let the controller handle window lifecycle
- Rate limit exits (code 2/75) should NOT count as crashes — they're expected behavior needing longer cooldown

---

## Session 134 — 2026-03-23

**What changed:**
- `CCA_PRIME_DIRECTIVE.md` — NEW: Two Pillars framework (Get Smarter + Get More Bodies)
- `CLAUDE.md` — Scope boundary updated: polymarket-bot now full read+write (S134 auth)
- `CLAUDE.md` — Mission updated: references prime directive
- `.claude/commands/cca-wrap.md` — Step 6a.1: outcome tracker auto-record wired in
- `.claude/commands/cca-wrap-desktop.md` — Same outcome tracker wiring
- `MASTER_TASKS.md` — MT-27/28/30 moved to Completed, MT-22/30 P1 override, percentages fixed
- `desktop_autoloop.py` — Extended idle detection (exit code 2, 5min idle threshold)
- `design-skills/report_sidecar.py` — NEW: JSON sidecar export alongside PDF (MT-33 Phase 5)
- `PROJECT_INDEX.md` — References prime directive, updated scope, test counts 8397->8406
- `ROADMAP.md` — Test counts 8397->8406

**Why:**
- Matthew S134 directive: document the Two Pillars, grant full polybot access, prioritize autoloop
- Outcome tracker was S133's top recommendation — now wired into wrap workflow
- Status table was stale for multiple MTs — cleaned up for accuracy

**Tests:** 208/208 suites passing (8406 total)

**Lessons:**
- Check if work is already done before building — MT-33 Phase 4 charts were already implemented
- Prime directive documents should be created early — they prevent priority drift

---

## Session 141 — 2026-03-23

**What changed:**
- `self-learning/principle_seeder.py` — NEW: Bootstrap principle registry from LEARNINGS.md and journal patterns. 62 principles seeded across 6 domains. Closes Get Smarter feedback loop.
- `self-learning/tests/test_principle_seeder.py` — NEW: 26 tests for parser, domain mapping, seeding, idempotency, journal patterns.
- `self-learning/principles.jsonl` — NEW: 62 seeded principles (code_quality=16, session_management=15, cca_operations=14, nuclear_scan=11, trading_research=3, general=3).
- `SESSION_STATE.md` — Updated for S139-S141 (was stale at S138).
- `CCA_TO_POLYBOT.md` — Full Kalshi bot DB analysis delivered (sniper price optimization, weather kill, overall health).

**Why:**
- Principle registry was empty (0 principles) despite 62 learnings and 984 journal entries. Predictive recommender produced nothing. Seeder bridges this gap.
- Kalshi bot needed data-driven analysis — Matthew asked CCA to coordinate directly.

**Tests:** 212/212 suites passing (+1 new)

**Lessons:**
- 755/984 journal entries have "unknown" event_type/domain — early sessions wrote unstructured data. Seeder works around this by using LEARNINGS.md as primary source.
- Cross-chat queue is the fastest way to communicate; persistent files (CCA_TO_POLYBOT.md) are the most reliable.

---

## Session 144 — 2026-03-24

**What changed:**
- `session_timer.py` (NEW): MT-36 Phases 1-2. Per-step timing instrumentation for session lifecycle. SessionTimer class with context manager, 6 categories, JSONL persistence, cross-session averages, outlier detection. CLI mark/done workflow for live session timing. 42 tests.
- `context-monitor/session_notifier.py` (MODIFIED): MT-35 Phase 3. Loop health notifications (`notify_loop_health`, `notify_loop_stopped`). 30-minute notification cooldown rate limiter (`CCA_NTFY_COOLDOWN_MIN`). High priority bypasses cooldown. 42 tests (was 19).
- `FINDINGS_LOG.md` (APPENDED): 9 Reddit review entries (3 ADAPT, 3 REFERENCE, 1 REFERENCE-PERSONAL, 2 SKIP).
- `CCA_TO_POLYBOT.md` (APPENDED): Proactive status update + Reddit intel relevant to Kalshi.
- `MASTER_TASKS.md` (MODIFIED): MT-35 Phase 3 marked COMPLETE.

**Why:**
- MT-36 (Matthew directive S143): systematic measurement of session overhead — where time goes
- MT-35 Phase 3: loop health visibility without being physically present at the machine
- Notification cooldown (Matthew directive S144): ntfy.sh was too noisy, had to mute daily
- Reddit reviews: 9 URLs Matthew queued, strongest signal = claude-devtools (252pts) validating F3+F5

**Tests:** 213 suites, ~8683 tests passing

**Lessons:**
- Function default parameter capture: `def f(x=GLOBAL_VAR)` captures at definition time, not call time. Use `def f(x=None): if x is None: x = GLOBAL_VAR` for mutable module-level state.
- Effort scorer threshold tests that hardcode complexity bounds break when the target file grows. Use relative thresholds or wider bounds.

---

## Session 146 — 2026-03-24

**What changed:**
- `.claude/commands/cca-init.md` — Step 2.5 expanded: displays full cross-chat content, flags stale comms
- `.claude/commands/cca-auto.md` — Step 3.5 added: mid-session cross-chat check every 2nd task. Step 5: priority picker re-runs every iteration.
- `.claude/commands/cca-wrap.md` — Step 7.5 added: mandatory cross-chat comms update at wrap
- `priority_picker.py` — MT-27, MT-9, MT-11, MT-14 corrected from ACTIVE to COMPLETED
- `tests/test_priority_picker.py` — Updated stagnation and crown jewel tests for corrected statuses
- Cross-chat update written to CCA_TO_POLYBOT.md (REQ-025 acknowledged)

**Why:**
- Matthew directive: better MT prioritization process and more frequent Kalshi bot comms
- Recurring bug: stale ACTIVE statuses on completed MTs (2nd session in a row fixing these)

**Tests:** 213/213 passing

**Lessons:**
- Priority picker stale status is a recurring pattern — may need automated cross-check against MASTER_TASKS.md

---

## Session 148 — 2026-03-24

**What changed:**
- `design-skills/dashboard_generator.py`: Dashboard v2 — dark mode toggle (CSS custom properties + localStorage), sortable task table, module search filter, collapsible sections, --theme CLI flag. Fixed total test count regex for tilde-prefixed numbers.
- `design-skills/tests/test_dashboard_v2.py`: 28 new tests for v2 features.
- `MASTER_TASKS.md`: MT-37 (AI Investment Research & Portfolio Intelligence) documented — 8 pillars, 7 phases, long-term research MT.
- `priority_picker.py`: MT-37 added (blocked/long-term), MT-32 updated (Phase 5 done), MT-36 updated (Phases 2-3 done). Stagnation test adjusted for current registry.
- `MT36_KALSHI_ANALYSIS.md`: New file — Kalshi session optimization analysis. Verdict: already optimized.
- `PROJECT_INDEX.md`, `ROADMAP.md`: Doc drift fixed — test counts corrected (8468->8779).
- `~/.claude/cross-chat/CCA_TO_POLYBOT.md`: Reddit intel on CF Benchmarks BRTI + synthesis.trade API assessment + correction.
- `FINDINGS_LOG.md`: Logged r/PredictionsMarkets crypto price provider review.

**Why:**
- MT-32 Phase 5 was top priority (score 10.0). Dashboard needed interactivity for Matthew's use.
- MT-37 planted per Matthew directive for long-term investment research capability.
- MT-36 Phase 4 needed to assess Kalshi sessions — found they're already lean.
- Doc drift was caught by doc_drift_checker and fixed.

**Tests:** 217/217 suites passing (~8779 tests)

**Lessons:**
- Dashboard test count regex must handle optional tilde prefix (~8779 vs 8779)
- Kalshi sessions are already well-optimized — CCA was the correct MT-36 optimization target
- synthesis.trade is a prediction market aggregator, NOT a CF Benchmarks data provider

---

## Session 150 — 2026-03-24

**What changed:**
- autoloop_stop_hook.py: Fire-and-forget Stop hook for autoloop resilience (27 tests)
- autoloop_trigger.py: Added breadcrumb write on success for anti-double-fire
- self-learning/reflect.py: Added check_improvement_convergence() from trace scores + proposals
- self-learning/improver.py: Added Improver.check_convergence() + get_convergence_summary()
- self-learning/tests/test_convergence_wiring.py: 12 tests for convergence integration
- design-skills/chart_generator.py: Dynamic left margin for horizontal bar charts (fixes clipped labels)
- design-skills/templates/cca-report.typ: Fixed missing # prefix on embed-chart call
- design-skills/report_charts.py: Replace "No data" charts with invisible SVG
- design-skills/learning_data_collector.py: Filter infrastructure noise from self-learning charts
- .claude/settings.local.json: Wired autoloop_stop_hook as Stop hook
- CCA_STATUS_REPORT_2026-03-24.pdf: Regenerated with all fixes (436.6 KB)

**Why:**
- S149 autoloop chain broke when context exhaustion killed wrap before Step 10
- convergence_detector built S149 needed wiring into reflect + improver to be useful
- Matthew requested hard audit of CCA report — found 18 issues, fixed 4 critical ones

**Tests:** 220/220 suites passing (+39 new tests)

**Lessons:**
- Chart label clipping is caused by hardcoded margins — always use dynamic margins based on content
- "No data" chart placeholders should never appear in a report — either provide data or hide the chart
- Infrastructure noise (context_monitor_alert) dwarfs actual learning events in charts — always filter

---

## Session 152 — 2026-03-24

**What changed:**
- `autoloop_stop_hook.py`: Fixed breadcrumb stale detection — now compares resume mtime vs breadcrumb mtime to allow back-to-back sessions under 10min
- `autoloop_pause.py` (NEW): MT-35 Phase 4 — pause/resume/toggle/status CLI for autoloop control
- `autoloop_trigger.py`: Added pause check before session spawn
- `design-skills/templates/cca-report.typ`: TOC page numbers with labeled section headers and clickable links
- `tests/test_autoloop_pause.py` (NEW): 19 tests for pause/resume
- `tests/test_autoloop_stop_hook.py`: +2 tests for mtime comparison + fixed env-dependent test

**Why:**
- Autoloop was failing to chain sessions when they ran under 10 minutes (breadcrumb from session N blocked session N+1's stop hook)
- MT-35 Phase 4: Matthew needs ability to pause/resume the autoloop without disabling it entirely
- TOC page numbers make the report navigable for longer documents

**Tests:** 8888/8888 passing (221 suites, +21 net new)

**Kalshi coordination:**
- Delivered E-value implementation confirmation (pure Python, log-space, erosion thresholds)
- Updated REQ-030 spec to use cusum_s >= 4.0 as CONVERGING signal
- No new pending requests from Kalshi chat

---

## Session 154 — 2026-03-24

**What changed:**
- MT-32: Fixed StackedBarChart X-axis label overlap (3-tier rotation: <=4 none, 5-8 -45deg, 9+ -90deg, 13+ skip) — `chart_generator.py`
- MT-32: Fixed histogram integer axis formatting (Y-axis counts always int, X-axis int for int data) — `chart_generator.py`
- MT-32: Fixed cover title to single line at 32pt — `cca-report.typ`
- MT-38 NEW: Peak/off-peak token budget system Phase 1+2 — `token_budget.py`, `~/.claude/rules/peak-offpeak-budgeting.md`
- FLB research citations verified and delivered — `CCA_TO_POLYBOT.md`
- +8 chart tests in `test_chart_consistency.py`, +21 token budget tests in `test_token_budget.py`

**Why:**
- Chart label overlap made MT Phase Progress chart unreadable (S154 agent visual audit)
- Rate limit instability prompted MT-38 — time-aware token budgeting is now universal
- FLB research from S154 agents needed persistence and verified citations

**Tests:** 222 suites / 8917 tests passing (+1 suite, +29 tests)

**Lessons:**
- Background agent results must be persisted to disk immediately — session interruptions can lose context
- Peak/off-peak awareness prevents wasteful usage during high-demand windows

---

## Session 158 — 2026-03-24

**What changed:**
- C2: Typst template color palette synced with design-guide + chart SVGs
- Wrap optimization: doc_updater.py (25 tests) replaces 3-4 Read/Edit cycles
- C2: Report whitespace reduction via weak pagebreaks
- MT-32/36/38 status corrected in priority_picker + MASTER_TASKS
- Cross-chat: Signal pipeline gap flagged to Kalshi chat

**Why:**
- C2 color sync + whitespace fix, wrap optimization (doc_updater.py), MT status updates, cross-chat delivery

**Tests:** 8984/8984 passing (224 suites)

**Lessons:**
- Explored principle_registry integration before checking data volume (only 3 trading principles)

---
