# Project Index: ClaudeCodeAdvancements
# Last updated: 2026-03-26 (Session 169)
# Read this FIRST each session for fast orientation (~150 lines)

---

## Quick Orientation

| What | Where |
|------|-------|
| Project rules + scope boundary | `CLAUDE.md` |
| Current state + next actions | `SESSION_STATE.md` |
| Feature backlog + priorities | `ROADMAP.md` |
| Detailed APIs, schemas, test list | `REFERENCE.md` |
| Session changelog (append-only) | `CHANGELOG.md` |
| Reddit review log (append-only) | `FINDINGS_LOG.md` |
| Severity-tracked learnings | `LEARNINGS.md` |
| Master-level aspirational tasks | `MASTER_TASKS.md` |
| Senior Dev gap analysis (MT-20) | `SENIOR_DEV_GAP_ANALYSIS.md` |
| Hivemind phased rollout (MT-21) | `HIVEMIND_ROLLOUT.md` |
| **CCA Prime Directive (S134)** | `CCA_PRIME_DIRECTIVE.md` |
| **Matthew Directives log (S181)** | `MATTHEW_DIRECTIVES.md` |

**Mission:** Build validated advancements for Claude Code users. CCA is part of the Kalshi bot ecosystem (S134).
**Two Pillars (CCA_PRIME_DIRECTIVE.md):** (1) Get Smarter — self-learning/evolution. (2) Get More Bodies — automation/multi-chat.
**Scope:** Full read+write to both `/Users/matthewshields/Projects/ClaudeCodeAdvancements/` and `/Users/matthewshields/Projects/polymarket-bot/` (S134).
**Top priority:** Desktop autoloop (MT-22/MT-30) → proven reliable → run constantly → knock out MTs at scale.

---

## Module Map

| Module | Path | Status | Tests |
|--------|------|--------|-------|
| Memory System | `memory-system/` | MEM-1-5 + OMEGA + FTS5 store + capture v2.0 + UserPromptSubmit + capture_hook tests | 340 |
| Spec System | `spec-system/` | SPEC-1-6 + spec_freshness + plan_compliance (wired into validate.py) | 205 |
| Context Monitor | `context-monitor/` | CTX-1-7 + Session Pacer + Session Notifier (ntfy.sh) + StopFailure hook | 434 |
| Agent Guard | `agent-guard/` | AG-1-10 + Edit Guard + Bash Guard (global hook, +cp/script/dd/tee evasion) + Worktree Guard (Agent Teams) + MT-20 Senior Dev (13 modules + ADR + /senior-review + coherence + rules + fp_filter + chat + git_context + LLM + intent + tradeoff) | 1102 |
| Usage Dashboard | `usage-dashboard/` | USAGE-1-3 + doc_drift_checker (root fix) + hook_profiler | 369 |
| Reddit Intelligence | `reddit-intelligence/` | MT-6,9(Phase 3 COMPLETE),11(Phase 3 autonomous trending + discover),14(Phase 3 COMPLETE),15,27(Phase 4 NEEDLE precision),40(Phase 1 scan scheduler) + subreddit_discoverer + url_reader tests | 498 |
| Self-Learning | `self-learning/` | MT-7,10,12,26(Tier 3+E2E),27(Phase 5),28(COMPLETE),37(Layer 5 COMPLETE + uber_pipeline + dca_advisor),49(Phase 6) + Sentinel + Resurfacer + Resurfacer Hook + Overnight Detector + micro_reflect + ROI Tracker + Trade Reflector + Strategy Health Scorer + principle_registry + pattern_registry + detectors + regime_detector + calibration_bias + cross_platform_signal + principle_transfer + dynamic_kelly + macro_regime + fear_greed_filter + signal_pipeline + outcome_feedback + predictive_recommender + sentinel_bridge + order_flow_intel + belief_vol_surface + apf_session_tracker + deployment_verifier + principle_seeder + monte_carlo_simulator (REQ-040) + meta_learning_dashboard (MT-49) + principle_discoverer (MT-49 Phase 3) + confidence_recalibrator (MT-49 Phase 4) + research_roi_resolver (MT-49 Phase 5) + fill_rate_simulator (REQ-042) + portfolio_loader (MT-37 Phase 3) + session_metrics (MT-49 Phase 6) + kelly_sizer (MT-37 Layer 3) + risk_monitor (MT-37 Layer 3) + tax_harvester (MT-37 Layer 4) + withdrawal_planner (MT-37 Layer 4) + rebalance_advisor (MT-37 Layer 5) + portfolio_report (MT-37 Layer 5) + behavioral_guard (MT-37 Layer 5) + uber_pipeline (MT-37 orchestrator) + dca_advisor (MT-37 DCA) + correlated_loss_analyzer (REQ-054) + volume_predictor (S187) + reflect tests | 2391 |
| Design Skills | `design-skills/` | MT-17 Phase 5 + daily snapshots + trading_chart (MT-24) + 29 chart types + consistency audit + report_charts (wired into /cca-report, 13 Kalshi + 13 base + 3 learning charts, +pareto +gauge S193) + kalshi_data_collector (13 chart methods) + learning_data_collector + report_sidecar + report_differ (MT-33) + Dashboard v2 (dark mode, sortable, search, collapsible) + figure integration (MT-32 Phase 7) + chartjs_bridge (MT-52/E2, 8 Chart.js types) + component_library (MT-32 Phase 4, 8 components, 75 tests) | 1679 |
| Pokemon Agent | `pokemon-agent/` | MT-53 ~35% — emulator_control + memory_reader(Crystal+Red) + game_state + navigation + config + tools + prompts + agent + main + battle_ai + boot_sequence(Red+Crystal) + crystal_data(251 species/moves). **PyBoy BANNED (S219) — migrate to mGBA.** Run first, build while playing. | 292 |
| Research | `research/` | Reddit scout, MT-8/MT-13 Phase 2 COMPLETE, S190 Agent Research (multi-agent/orchestration), MT-53 Pokemon Research (emulator+frameworks), MT-53 Intelligence Scan (S191) | 86 |

**Total: ~10,706 tests (~282 suites). All must pass before any work.**

Run all: `for f in $(find . -name "test_*.py" -type f | sort); do echo "=== $f ===" && python3 "$f" 2>&1 | tail -1; done`

---

## Key Files Per Module

**memory-system/** — Persistent cross-session memory
- `hooks/capture_hook.py` — PostToolUse + Stop capture
- `mcp_server.py` — MCP server for memory queries
- `memory_store.py` — SQLite+FTS5 storage backend (S61, 80 tests)
- `cli.py` — CLI viewer (`stats`, `search`, `list`)
- `research/EXTERNAL_COMPARISON.md` — engram/ClawMem/claude-mem architecture analysis (S60)

**spec-system/** — Spec-driven development workflow
- `commands/` — `/spec:requirements`, `/spec:design`, `/spec:tasks`, `/spec:implement`, `/spec:design-review`
- `hooks/validate.py` — PreToolUse spec guard (warn/block)
- `hooks/skill_activator.py` — UserPromptSubmit auto-activation
- `spec_freshness.py` — Spec rot/staleness detector (FRESH/STALE/RETIRED)

**context-monitor/** — Context health + compaction guard
- `hooks/meter.py` — PostToolUse token counter
- `hooks/alert.py` — PreToolUse warn/block at red/critical
- `hooks/auto_handoff.py` — Stop hook: blocks exit at critical
- `hooks/compact_anchor.py` — PostToolUse anchor writes
- `hooks/post_compact.py` — CTX-7: PostCompact recovery + journal logging
- `auto_wrap.py` — CTX-6: Automatic session wrap trigger
- `session_pacer.py` — Session pacing for 2-3h autonomous runs (CONTINUE/WRAP_SOON/WRAP_NOW)
- `session_notifier.py` — ntfy.sh push notifications on session end/error (MT-22, 19 tests)
- `hooks/stop_failure.py` — StopFailure hook: rate limit/auth/server error classification + state tracking (CC v2.1.78+, 15 tests, S112)

**agent-guard/** — Multi-agent conflict prevention + safety
- `hooks/mobile_approver.py` — AG-1: iPhone push approval (ntfy.sh)
- `hooks/credential_guard.py` — AG-3: Credential extraction guard
- `hooks/network_guard.py` — AG-5: Port/firewall exposure guard
- `hooks/session_guard.py` — AG-6: Slop detection + commit tracking
- `content_scanner.py` — AG-4: Autonomous scanning hazmat (9 threat categories)
- `path_validator.py` — AG-7: Dangerous path + command detection (LIVE in hooks)
- `ownership.py` — AG-2: File ownership manifest
- `edit_guard.py` — AG-8: Edit retry prevention for structured table files (LIVE in hooks)
- `bash_guard.py` — AG-9: Bash command safety guard (network, packages, processes, system, redirects, evasion) (LIVE in hooks)
- `worktree_guard.py` — AG-10: Worktree isolation guard for Agent Teams (delegate scope, shared state protection, git safety, 29 tests, S177)
- `satd_detector.py` — MT-20 Phase 1: SATD marker detection PostToolUse hook (TODO/FIXME/HACK/WORKAROUND/DEBT/XXX/NOTE)
- `effort_scorer.py` — MT-20 Phase 2: PR effort scoring (1-5 scale, Atlassian/Cisco research)
- `senior_dev_hook.py` — MT-20 Phase 3: PostToolUse orchestrator (runs SATD + effort + quality on Write/Edit) (LIVE in hooks)
- `code_quality_scorer.py` — MT-20 Phase 3: Aggregate quality scoring (0-100, A-F, 5 dimensions)
- `fp_filter.py` — MT-20 Phase 4: False positive filter (test files, vendored, low-confidence)
- `review_classifier.py` — MT-20 Phase 4: CRScore-style review category classification (6 categories)
- `tech_debt_tracker.py` — MT-20 Phase 5: SATD trend analysis over time
- `adr_reader.py` — MT-20 Full Vision: ADR discovery + relevance matching (MADR/Nygard/inline, PostToolUse hook)
- `senior_review.py` — MT-20 Phase 7: On-demand review engine (APPROVE/CONDITIONAL/RETHINK verdicts, blast radius, fp_filter, ADR reader)
- `senior_chat.py` — MT-20 Phase 8: Interactive CLI chat mode (review + REPL, prompt gen for LLM follow-ups)
- `coherence_checker.py` — MT-20 Phase 9: Architectural coherence (module structure, pattern consistency, import dependency graph, CLAUDE.md rule compliance)
- `git_context.py` — MT-20: Git history awareness (file history, blame ownership, churn detection, review formatting)

**usage-dashboard/** — Token + cost transparency
- `usage_counter.py` — USAGE-1: CLI token/cost counter
- `otel_receiver.py` — USAGE-2: OTLP HTTP/JSON receiver
- `hooks/cost_alert.py` — USAGE-3: PreToolUse cost threshold
- `arewedone.py` — Structural completeness checker
- `doc_drift_checker.py` — Doc accuracy verifier (test counts, file paths vs reality)
- `hook_profiler.py` — Hook chain latency diagnostic

**reddit-intelligence/** — Community signal research
- `reddit_reader.py` — Fetches posts + all comments
- `autonomous_scanner.py` — MT-9: Scan pipeline (prioritizer + safety)
- `github_scanner.py` — MT-11: GitHub repo intelligence
- `repo_tester.py` — MT-15: Sandboxed repo testing
- `profiles.py` — MT-6: Subreddit profiles + registry
- `subreddit_discoverer.py` — Domain-based subreddit discovery (claude/trading/research/dev, 25 tests, S179)
- `github_scanner.py` discover command — Domain-based repo discovery (16 tests, S179)

**design-skills/** — Professional visual output (MT-17)
- `report_generator.py` — CCA data collector + Typst renderer CLI
- `slide_generator.py` — Presentation slide generator (16:9 PDF)
- `design-guide.md` — Visual language (colors, fonts, layout)
- `templates/cca-report.typ` — Status report Typst template
- `templates/cca-slides.typ` — Presentation slide Typst template
- `dashboard_generator.py` — Self-contained HTML dashboard generator
- `chart_generator.py` — SVG chart generation (29 chart types incl bar, line, donut, heatmap, scatter, box, histogram, candlestick, forest, calibration, bullet, slope, lollipop, dumbbell, pareto)
- `website_generator.py` — Landing page + docs page HTML generator (665 LOC)
- `daily_snapshot.py` — Daily project metric snapshots with diff support (474 LOC, 50 tests)
- `report_charts.py` — SVG chart generation from report data for Typst embedding (13 base + 13 Kalshi + 3 learning charts, 102 tests). Wired into /cca-report pipeline — charts auto-generated and embedded in PDF.
- `kalshi_data_collector.py` — MT-33: Read-only Kalshi bot DB analytics (trades, strategies, P&L, bankroll). 8 chart-ready methods. 48 tests (S122/S123).
- `learning_data_collector.py` — MT-33: Self-learning intelligence (journal events, APF trend, domain distribution). 3 chart methods. 29 tests (S122/S123).
- `report_differ.py` — MT-33 Phase 6: Structured diff between two report sidecars (test growth, MT transitions, Kalshi P&L, APF). 30 tests (S123).
- `report_sidecar.py` — MT-33 Phase 5: JSON export alongside PDF (extract, save, load, find_latest). S134.
- `MT33_DATA_MAPPING.md` — Schema mapping, SQL queries, chart-to-data design doc (S122).
- `figure_generator.py` — MT-32 Phase 6: Multi-panel figure composer (grid layout, panel labels, captions, 3 annotation types, presets). 62 tests (S166).
- `chartjs_bridge.py` — MT-52/E2: Chart.js config generator for interactive HTML dashboards. 8 Chart.js types (bar, line, donut, stacked bar, scatter, horizontal bar, bubble, radar), CCA palette, CDN tag. 21 tests (S192).

**self-learning/** — New MT-37 modules (S185) + Kalshi intelligence toolkit (S188)
- `market_data.py` — MT-37 Phase 4: Returns, volatility, beta, factor exposures, correlation matrix, CSV/JSON parsers. 42 tests (S185).
- `allocation.py` — MT-37 Phase 5: Equal-weight, risk parity, Black-Litterman allocation. 28 tests (S185).
- `factor_tilts.py` — MT-37 Phase 6: Value/momentum/quality/low-vol factor overlays. 26 tests (S185).
- `sizing_optimizer.py` — Portfolio-level bet sizing optimizer: Kelly fractions, daily EV/SD, P(target), from_db, asset-weighted sizing. 47 tests (S188).
- `daily_outlook.py` — Daily P&L outlook predictor: BTC range → volume → EV/SD → verdict. 18 tests (S188).
- `hour_sizing.py` — Time-of-day sizing adjuster: hourly EV → multiplier schedule. 23 tests (S188).

**pokemon-agent/** — MT-53 Autonomous Pokemon Crystal bot (~35% complete, S219)
- `MT53_COMPLETION_PLAN.md` — Current source of truth for Crystal MVP vs Full MT-53, capability matrix, milestone order, and acceptance tests (S256)
- `agent.py` — Core CrystalAgent: step loop, auto-advance, action cache, stuck detection, battle AI, LLM integration (989 LOC)
- `emulator_control.py` — Emulator abstraction (swappable backends). **PyBoy backend exists but is BANNED — needs mGBA replacement**
- `memory_reader.py` — Crystal RAM addresses + state reading (party, battle, badges, position)
- `memory_reader_red.py` — Red-specific RAM addresses
- `crystal_data.py` — Complete data tables: 251 species, 251 moves, items, maps, type chart (S218 STEAL CODE)
- `game_state.py` — Dataclasses: GameState, MapPosition, MenuState, Party, Pokemon, BattleState, Badges
- `battle_ai.py` — Deterministic battle decisions: type effectiveness, heal/catch/flee/fight (Gen 1 chart, needs Gen 2 update)
- `boot_sequence.py` — Red intro automation (title → Oak's Lab)
- `boot_sequence_crystal.py` — Crystal intro automation (title → Elm's Lab, S219)
- `red_agent.py` — Red subclass with Red-specific components
- `navigation.py` — A* pathfinding (Red warps only, Crystal warps TODO)
- `main.py` — Entry point: ROM detection, agent creation, boot sequence, step loop
- `config.py` — Model, token limits, directories, thresholds
- `tools.py` — LLM tool definitions (press_buttons, navigate_to, wait, checkpoint, memory, markers, objectives)
- `prompts.py` — System prompt + user message builder for Opus
- **30 test suites, ~500+ tests**
- **PRIORITY: Implement mGBA backend, then offline test run with real Crystal ROM**

**self-learning/research/** — Academic research
- `MT37_RESEARCH.md` — MT-37 Phase 1: 42-paper synthesis across 10 areas (S178-S180)
- `MT37_ARCHITECTURE.md` — MT-37 Phase 2: UBER system architecture design (10 modules, 5 layers, S182)

**root/** — Loop hardening + coordination
- `resume_generator.py` — cca-loop hardening: auto-generate SESSION_RESUME.md from SESSION_STATE when stale (17 tests)
- `cca_internal_queue.py` — Desktop/Terminal coordination queue (69 tests)
- `cca_comm.py` — Structured cca-loop session communication (scope claim, wrap summary, task assignment)
- `loop_health.py` — Per-session health tracking for cca-loop (grade, test counts, regression detection, 54 tests)
- `queue_injector.py` — Cross-chat queue context injection hook (19 tests)
- `launch_worker.sh` — One-command dual-chat launcher: opens Terminal tab with CCA_CHAT_ID, starts worker
- `tip_tracker.py` — Advancement tip persistence across all chats (26 tests, S89)
- `wrap_tracker.py` — Session wrap assessment persistence with trend analysis (23 tests, S89)
- `hivemind_session_validator.py` — Desktop-side hivemind cycle validation + Phase 1 gate tracking (17 tests, S90)
- `hivemind_metrics.py` — Phase 1 validation metrics persistence (20 tests, S90, built by cli1 worker)
- `hivemind_dashboard.py` — Combined Phase 1 status reporter (16 tests, S90, built by cli1 worker)
- `overhead_timer.py` — Coordination overhead measurement for Phase 1 metrics (13 tests, S90)
- `chat_detector.py` — Duplicate Claude Code session detection + pre-launch safety (31 tests, S91)
- `crash_recovery.py` — Worker crash detection + orphaned scope auto-release (15 tests, S91)
- `worker_task_tracker.py` — Detect incomplete worker task completion (26 tests, S97)
- `worker_verifier.py` — MT-21: Automated worker output verification (tests/regressions/committed, ACCEPT/REVIEW/REJECT verdicts, 20 tests, S190)
- `priority_picker.py` — Automated MT priority selection with dust detection, growth scoring (93 tests, S98/S160)
- `peak_hours.py` — Rate limit awareness for multi-chat orchestration (19 tests, S107)
- `launch_kalshi.sh` — Kalshi chat launcher with auth fix + peak hours warning (S107)
- `session_registry.py` — MT-30 Phase 2: Session config loading + state tracking (60 tests, S111)
- `tmux_manager.py` — MT-30 Phase 2: Tmux window create/monitor/kill (40 tests, S111)
- `session_daemon_config.json` — Default daemon config (3 sessions, peak hours)
- `session_orchestrator.py` — 3-chat auto-launch decision logic: detect running sessions, decide launches, PID registry + heartbeat (55 tests, S120)
- `handoff_generator.py` — Automated SESSION_HANDOFF file generation for multi-chat (50 tests, S116)
- `launch_session.sh` — Unified multi-chat launcher with safety checks (13 tests, S116)
- `session_metrics.py` — Cross-session analytics aggregator (55 tests, S116)
- `coordination_dashboard.py` — At-a-glance multi-chat status view (22 tests, S116)
- `cca_autoloop.py` — MT-30 Phase 6+8: CCA auto-loop — reads SESSION_RESUME.md, spawns claude, loops. Production hardened: pre-flight checks, rate limit handling, Terminal.app dialog handling, stale resume detection (116 tests, S126/S128)
- `start_autoloop.sh` — One-command auto-loop launcher (tmux or foreground, S126)
- `session_daemon_cca_only.json` — CCA-only daemon config for auto-loop (1 session max, S126)
- `autoloop_trigger.py` — MT-22: CCA-internal autoloop trigger — called by /cca-wrap Step 10 to spawn next session (activate, Code tab, Cmd+N, paste, send). 18 tests (S138)
- `autoloop_pause.py` — MT-35 Phase 4: Pause/resume/toggle/status CLI for autoloop control. Flag file ~/.cca-autoloop-paused. 19 tests (S152)
- `token_budget.py` — MT-38: Peak/off-peak token budget detection. get_budget() API, --brief/--json CLI modes. PEAK 60%/SHOULDER 80%/OFF-PEAK 100%. 21 tests (S154)
- `overhead_tracker.py` — MT-38: Measure CCA startup token overhead. CCA=49K tokens (3x baseline). History, baselines, trend CLI. 17 tests (S185).
- `desktop_automator.py` — MT-22: AppleScript-based Claude.app control (activate, send, close, CPU idle detection, preflight, Code tab awareness). 85 tests (S132/S136)
- `desktop_autoloop.py` — MT-22: Self-sustaining desktop loop orchestrator (resume watcher, state tracking, model selection, Code tab awareness). 60 tests (S132/S136)
- `start_desktop_autoloop.sh` — MT-22: One-command desktop auto-loop launcher (S132)
- `DESKTOP_AUTOLOOP_SETUP.md` — MT-22: Setup guide (permissions, quick start, troubleshooting)
- `LEAGUES_CLAUDE_PROJECT_PACKAGING.md` — Leagues support playbook for packaging `OSRSLeaguesTool` wiki/community knowledge into Claude Project docs for claude.ai/iOS use
- `LEAGUES_CLAUDE_PROJECT_TEMPLATE_01_OVERVIEW.md` — Fill-in template for Claude Project overview/upload doc
- `LEAGUES_CLAUDE_PROJECT_TEMPLATE_02_REGIONS_RELICS_TASKS.md` — Fill-in template for the structured Leagues reference doc
- `LEAGUES_CLAUDE_PROJECT_TEMPLATE_03_COMMUNITY_META.md` — Fill-in template for distilled Discord/community consensus
- `LEAGUES_CLAUDE_PROJECT_TEMPLATE_04_QUERY_EXAMPLES.md` — Fill-in template for mobile/web query prompt examples
- `LEAGUES_CLAUDE_PROJECT_TEMPLATE_05_PLANNER_ROUTE_NOTES.md` — Fill-in template for planner/advisor outputs and route-specific guidance in the Claude Project pack
- `session_outcome_tracker.py` — MT-10: Session prompt-to-outcome JSONL tracker (planned vs completed, auto-grade, trend analysis, outcome analyzer with pattern detection + recommendations, 62 tests, S133/S136)
- `session_timer.py` — MT-36 Phase 1: Per-step timing instrumentation for session lifecycle (init/wrap/test/code/doc categories, context manager + manual timing, JSONL persistence, cross-session averages, outlier detection, 31 tests, S144)
- `efficiency_analyzer.py` — MT-36 Phase 2: Session overhead analyzer (SessionProfile, OverheadAnalyzer, static wrap analysis, slim wrap proposal, recommendations, 32 tests, S147)
- `batch_wrap_learning.py` — MT-36 Phase 3: Consolidated wrap self-learning (replaces 11 subprocess calls with single batch, JSONL writes for journal/wrap/tips/outcomes, 18 tests, S147)
- `autoloop_stop_hook.py` — S150: Fire-and-forget Stop hook for autoloop resilience. Spawns next session even when context exhaustion kills wrap. Breadcrumb anti-double-fire. (27 tests, S150)

**research/** — R&D and tools
- `ios_project_gen.py` — MT-13: Xcode project generator (SwiftUI + tests)
- `xcode_build.py` — MT-13: Python xcodebuild wrapper

**self-learning/** — Cross-session improvement
- `journal.py` — Structured event journal (JSONL)
- `reflect.py` — Pattern detection + strategy recommendations
- `improver.py` — MT-10: YoYo improvement loop
- `trace_analyzer.py` — MT-7: Transcript pattern analyzer
- `batch_report.py` — MT-10: Aggregate trace health
- `validate_strategies.py` — Skillbook validation
- `paper_scanner.py` — MT-12: Academic paper discovery (Semantic Scholar + arXiv)
- `paper_digest.py` — MT-12 Phase 3: Kalshi/CCA paper digest generator with bridge integration (35 tests)
- `hooks/skillbook_inject.py` — UserPromptSubmit strategy injection
- `resurfacer.py` — MT-10 Phase 3B: Findings re-surfacing + trade proposal integration
- `overnight_detector.py` — Objective time-stratified trading analysis (Wilson CI, CUSUM, SQL templates, audit)
- `research_outcomes.py` — Research ROI tracker: tracks CCA deliveries -> Kalshi implementation -> profit/loss
- `trade_reflector.py` — MT-10 Phase 3A: Kalshi trade pattern analysis (read-only DB, 5 detectors, proposals)
- `strategy_health_scorer.py` — Strategy health verdicts (HEALTHY/MONITOR/PAUSE/KILL, 24 tests)
- `principle_registry.py` — MT-28 Phase 1: EvolveR-style principle registry (Laplace-smoothed scoring, domain-tagged, 73 tests)
- `pattern_registry.py` — MT-28 Phase 2: Central plugin registry for pattern detectors (@register_detector, domain filtering, exception isolation, 14 tests)
- `detectors.py` — MT-28 Phase 2: 12 built-in pattern detectors (7 general, 6 trading, 28 tests)
- `regime_detector.py` — MT-26 Phase 1: Market regime classifier (TRENDING/MEAN_REVERTING/CHAOTIC, volatility+R²+Hurst, 21 tests)
- `calibration_bias.py` — MT-26 Phase 1: Calibration bias exploiter (FLB detection, mispricing zones, bias-adjusted probability, 43 tests)
- `cross_platform_signal.py` — MT-26 Phase 1: Cross-platform signal detector (Kalshi/Polymarket divergence, lag analysis, 30 tests)
- `principle_transfer.py` — MT-28 Phase 3: Cross-domain principle transfer (affinity scoring, transfer candidates, 34 tests)
- `dynamic_kelly.py` — MT-26 Tier 2: Dynamic Kelly with Bayesian updating (logit-space belief revision, time decay, fractional Kelly, 32 tests)
- `macro_regime.py` — MT-26 Tier 2: Macro regime context (FOMC/CPI/NFP calendar, CALM/ELEVATED/HIGH_IMPACT, sizing modifier, 30 tests)
- `fear_greed_filter.py` — MT-26 Tier 2: Fear & greed contrarian filter (5 zones, direction bias, sizing modifier, trend context, 38 tests)
- `signal_pipeline.py` — MT-26 Pipeline Orchestrator: chains all 6 MT-26 modules, graceful degradation, compound modifiers, BET/SKIP decision (32 tests)
- `outcome_feedback.py` — MT-28 Phase 4: Research outcomes feedback loop (bridges research_outcomes to principle_registry scoring, 16 tests)
- `predictive_recommender.py` — MT-28 Phase 5: Pre-session recommendations from principle scores + domain affinity (40 tests, S111)
- `sentinel_bridge.py` — MT-28 Phase 6: Bridge sentinel mutations to principle registry (30 tests, S111)
- `order_flow_intel.py` — MT-26 Tier 3: Order flow intelligence (FLB regression, Maker/Taker model, risk classifier, 38 tests, S112)
- `belief_vol_surface.py` — MT-26 Tier 3: Belief volatility surface Phase 1 (logit transforms, Greeks, realized vol, 27 tests, S112)
- `apf_session_tracker.py` — MT-27 Phase 5: APF trend tracking per session (append-only JSONL snapshots, 27 tests, S115)
- `monte_carlo_simulator.py` — REQ-040: Monte Carlo bankroll simulator (BetDistribution, MonteCarloSimulator, SyntheticBetGenerator, from_db DB bridge, CLI). 50 tests (S168).
- `meta_learning_dashboard.py` — MT-49 Phase 1: Self-learning meta-analysis (PrincipleAnalyzer, SessionTrendAnalyzer, ImprovementTracker, ResearchROITracker, JournalAnalyzer, MetaLearningDashboard). CLI: --json/--brief/--data-dir. 28 tests (S169).
- `principle_discoverer.py` — MT-49 Phase 3: Automated principle discovery from git patterns + journal (GitPatternDiscoverer, SessionPatternDiscoverer, PrincipleDiscoverer). CLI: discover [--dry-run], status. 27 tests (S171).
- `confidence_recalibrator.py` — MT-49 Phase 4: Bayesian staleness decay on principle scores (exponential decay, half-life ~70 sessions, floor 0.3). CLI: recalibrate [--session N], summary. 22 tests (S172).
- `research_roi_resolver.py` — MT-49 Phase 5: Research-to-production ROI tracking. Parses DELIVERY_ACK.md + scans Kalshi git commits. 3 resolution sources: req_id, fuzzy, commit_scan. CLI: resolve/report/summary. 36 tests (S173-S175).
- `outcomes_enricher.py` — MT-49 Phase 5: Enrich research_outcomes.jsonl with missing REQ delivery entries from CCA_TO_POLYBOT.md. CLI: scan/enrich. 25 tests (S175).
- `commit_scanner.py` — MT-49 Phase 5: Scan polymarket-bot git log for REQ-referencing commits, auto-detect implementation status. CLI: scan/match. 23 tests (S175).
- `fill_rate_simulator.py` — REQ-042: Maker sniper fill rate Monte Carlo (SpreadModel, FillRateSimulator, ParameterSweep, from_db calibration, CLI --sweep/--from-db). 30 tests (S174).
- `session_metrics.py` — MT-49 Phase 6: Session-over-session trend tracking (grade, test velocity, learnings, APF, win/pain). 37 tests (S195).
- `kelly_sizer.py` — MT-37 Layer 3: Fractional Kelly criterion with confidence scaling. 20 tests (S195).
- `risk_monitor.py` — MT-37 Layer 3: Drawdown/volatility risk dashboard. 22 tests (S195).
- `tax_harvester.py` — MT-37 Layer 4: TLH scanner with wash sale tracking. 23 tests (S195).
- `withdrawal_planner.py` — MT-37 Layer 4: CAPE-adjusted SWR with Guyton-Klinger guardrails. 20 tests (S195).
- `rebalance_advisor.py` — MT-37 Layer 5: Hybrid threshold+calendar rebalancing. DriftResult, RebalanceAdvisor, BUY/SELL actions. 23 tests (S196).
- `portfolio_report.py` — MT-37 Layer 5: Portfolio analytics (Sharpe, Sortino, max drawdown, risk attribution). 24 tests (S196).
- `behavioral_guard.py` — MT-37 Layer 5: 5 behavioral bias detectors (disposition, loss aversion, recency, home bias, overconfidence). 22 tests (S196).
- `uber_pipeline.py` — MT-37 UBER orchestrator: chains all 10 modules into single analyze_portfolio(). PortfolioInput, UBERConfig, UBERReport. 31 tests (S196).
- `dca_advisor.py` — MT-37: DCA planner for small recurring investments ($20/week, $50/month). allocate_deposit, rebalance_on_deposit, annual_projection, app recommendations. 18 tests (S196).
- `correlated_loss_analyzer.py` — REQ-054: Cross-asset loss correlation detector. WindowAnalyzer clusters BTC+ETH losses by time window, coincidence rate vs independence. 20 tests (S196).
- `market_diversifier.py` — REQ-055: HHI-based cross-market diversification analyzer. AssetClass enum, concentration_risk(), DiversificationAdvisor. 25 tests (S196).
- `loss_reduction_simulator.py` — REQ-057: Models avg_loss reduction impact on ruin probability. Sweep analysis, 5 named strategies, WR sensitivity, recovery ratios. 25 tests (S197).
- `strategy_allocator.py` — Multi-strategy capital allocation optimizer. Kelly-criterion proportional allocation, constraints, scenario analysis. 25 tests (S197).
- `edge_decay_detector.py` — Strategy edge stability monitoring. Rolling window regression, stable/improving/declining detection, WR drop alerts. 19 tests (S197).
- `bankroll_growth_planner.py` — Analytical bankroll trajectory projection. Day-by-day expected/P5/P95 bands, ruin decay, self-sustaining detection, milestones. 18 tests (S197).
- `wr_cliff_analyzer.py` — Binary search WR cliff detection via Monte Carlo. Cliff map across avg_loss levels, safety margin reporting. 12 tests (S197).
- `volatility_regime_classifier.py` — Market regime detection (LOW/NORMAL/HIGH). Adaptive parameter recommendations per regime. Rolling classification. 16 tests (S197).
- `risk_dashboard_runner.py` — Unified runner for 7 Kalshi risk analysis tools. Single run() → JSON report with health status, safety margin, recommendations. 10 tests (S197).
- `BATCH_ANALYSIS_S58.md` — Batch trace analysis of 50 sessions (avg 72.6, retry hotspots documented)
- `BATCH_ANALYSIS_S62.md` — Batch trace analysis of 10 recent sessions (avg 73.0, retry rate down to 40%)
- `research/SENIOR_DEV_AGENT_RESEARCH.md` — S70: Nuclear-level research for Senior Dev Agent MT (11 verified papers, 5 tools, industry standards, MVP architecture)
- `research/MT37_RESEARCH.md` — MT-37 UBER Phase 1: Academic foundation (areas 1-7 of 10). 1196 lines, 30 papers synthesized. (S178-S179)

---

## Integration Tests

| File | Purpose |
|------|---------|
| `tests/test_hook_chain_integration.py` | End-to-end hook chain: all 15 hooks, valid JSON, latency budget, cross-hook interference (22 tests) |
| `tests/test_queue_injector.py` | Cross-chat queue context injection hook (19 tests) |
| `tests/test_cross_chat_queue.py` | Bidirectional cross-chat JSONL message queue (44 tests) |
| `tests/test_cca_internal_queue.py` | Desktop/Terminal coordination queue (41 tests) |
| `tests/test_hivemind_deep.py` | Deep hivemind coverage: 117 tests across 31 classes (S89) |
| `tests/test_hivemind_session_validator.py` | Desktop-side hivemind cycle validation (17 tests, S90) |
| `tests/test_hivemind_metrics.py` | Phase 1+2 metrics persistence + queue throughput (26 tests, S90/S92) |
| `tests/test_chat_detector.py` | Duplicate session detection + pre-launch checks (31 tests, S91) |
| `tests/test_crash_recovery.py` | Worker crash detection + scope recovery (15 tests, S91) |
| `tests/test_phase2_e2e.py` | Phase 2 full lifecycle E2E + hardened workflows: conflict detection, stale recovery, high volume, 2-worker scopes (12 tests, S92/S93) |
| `tests/test_phase2_hardening.py` | Phase 2 hardening: atomic writes, scope conflicts, stale crash recovery (22 tests, S93) |
| `tests/test_session_daemon_integration.py` | MT-30 Phase 4: Daemon lifecycle, peak transitions, crash recovery chains, audit trail (27 tests, S113) |
| `tests/test_cusum_guard.py` | CUSUM drift detection for polybot auto_guard_discovery.py (13 tests, S176) |

CI/CD: `.github/workflows/tests.yml` — runs all 69 suites on push/PR against Python 3.10 + 3.12.

---

## Live Hooks (settings.local.json)

| Event | Hook | Purpose |
|-------|------|---------|
| PreToolUse (all) | `context-monitor/hooks/alert.py` | Warn/block at red/critical |
| PreToolUse (all) | `usage-dashboard/hooks/cost_alert.py` | Cost threshold |
| PreToolUse (all) | `agent-guard/path_validator.py` | Dangerous path/command detection |
| PreToolUse (all) | `agent-guard/edit_guard.py` | Edit retry prevention on structured files |
| PreToolUse (all) | `spec-system/hooks/validate.py` | Spec guard + plan compliance + freshness |
| PreToolUse (Bash) | `agent-guard/hooks/credential_guard.py` | Credential extraction guard |
| PreToolUse (Bash) | `agent-guard/bash_guard.py` | Bash command safety (network, packages, processes, system) |
| PostToolUse (all) | `context-monitor/hooks/meter.py` | Token counter |
| PostToolUse (all) | `context-monitor/hooks/compact_anchor.py` | Anchor writes |
| PostToolUse (all) | `agent-guard/senior_dev_hook.py` | Senior Dev: SATD + effort + quality scoring |
| UserPromptSubmit | `spec-system/hooks/skill_activator.py` | Skill auto-activation |
| UserPromptSubmit | `self-learning/hooks/skillbook_inject.py` | Strategy injection |
| UserPromptSubmit | `memory-system/hooks/capture_hook.py` | Real-time memory capture |
| UserPromptSubmit | `queue_injector.py` | Cross-chat queue context injection (wire in Kalshi chats) |
| Stop | `context-monitor/hooks/auto_handoff.py` | Block exit at critical |
| Stop | `memory-system/hooks/capture_hook.py` | Session-end memory capture |
| PostCompact | `context-monitor/hooks/post_compact.py` | Recovery + journal logging |

---

## Session Commands

| Command | Purpose |
|---------|---------|
| `/cca-init` | Session startup — reads context, runs tests, shows briefing |
| `/cca-auto` | Autonomous work — picks next task, executes |
| `/cca-wrap` | Session end — self-grade, update docs, resume prompt |
| `/cca-review <url>` | Review URL against frontiers — BUILD/SKIP verdict |
| `/cca-scout` | Scan subreddits for high-signal posts |
| `/cca-nuclear` | Autonomous deep-dive batch review |
| `/cca-report` | Generate professional PDF status report |
| `/cca-dashboard` | Generate interactive HTML dashboard |
| `/browse-url <url>` | Read any URL (no analysis) |


### Added in S158
- `doc_updater.py` — Batch doc updates for /cca-wrap optimization (25 tests, S158)
- `tests/test_doc_updater.py` — Tests for doc_updater.py (S158)

### Added in S160
- `efficiency_dashboard.py` — MT-36 Phase 5: Self-contained HTML dashboard (dark mode, overhead trends, scatter plot, 28 tests)
- `mt_originator.py` — MT-41 Phase 1: Synthetic MT origination from FINDINGS_LOG BUILD verdicts (22 tests)
- `scan_scheduler.py` — MT-40 Phase 1: Per-subreddit staleness policies + scan recommendation (17 tests)
- `tests/test_efficiency_dashboard.py`, `tests/test_mt_originator.py`, `tests/test_scan_scheduler.py`

### Added in S162
- `learning_loop.py` — Cross-chat learning feedback loop: OutcomeReport parser, ResearchPriority scorer, run_cycle() (23 tests)
- `scan_executor.py` — MT-40 Phase 4: Automated scan pipeline orchestrator (17 tests)
- `autoloop_toggle.sh` — MT-35 Phase 4: One-key autoloop pause/resume with macOS notifications
- `tests/test_learning_loop.py`, `tests/test_scan_executor.py`

### Added in S163
- `design-skills/design_linter.py` — MT-32 Phase 3: Design system lint rules (colors, fonts, spacing, anti-slop). 31 tests.
- `tests/test_mt_originator_phase2.py` — MT-41 Phase 2-3 tests (cluster scoring, append, briefing). 31 tests.
- `self-learning/tests/test_principle_seeder_findings.py` — MT-28 growth: findings seeder tests. 19 tests.

### Added in S164
- `design-skills/consistency_checker.py` — MT-32 Phase 4: Cross-format design consistency auditor. Scans generator source for orphan colors, token drift, font mismatches. 22 tests.
- `tests/test_polybot_comm_learning.py` — REQ-038: Tests for polybot_comm.py send_outcome_report + parse_research_priorities. 13 tests.


### Added in S198
- `self-learning/mandate_tracker.py` (S198)
- `self-learning/kelly_optimizer.py` (S198)
- `self-learning/window_frequency_estimator.py` (S198)
- `self-learning/mandate_dashboard.py` (S198)
- `self-learning/signal_threshold_analyzer.py` (S198)
- `self-learning/tests/test_mandate_tracker.py` (S198)
- `self-learning/tests/test_kelly_optimizer.py` (S198)
- `self-learning/tests/test_window_frequency_estimator.py` (S198)
- `self-learning/tests/test_mandate_dashboard.py` (S198)
- `self-learning/tests/test_signal_threshold_analyzer.py` (S198)


### Added in S200
- `pokemon-agent/emulator_control.py` (S200)
- `pokemon-agent/memory_reader.py` (S200)


### Added in S201
- `research/mt53/OPUS46_PERFORMANCE_INTEL.md` (S201)
- `research/mt53/AGENT_OUTPUTS_VERBATIM.md` (S201)
- `reddit-intelligence/subreddit_scanner.py` (S201)
- `reddit-intelligence/test_subreddit_scanner.py` (S201)


### Added in S202
- `pokemon-agent/config.py` — Agent configuration constants (S202, 10 tests)
- `pokemon-agent/tools.py` — Claude API tool definitions + validation (S202, 24 tests)
- `pokemon-agent/prompts.py` — System prompt, state formatting, stuck detection (S202, 40 tests)
- `pokemon-agent/agent.py` — Core agent loop, MockLLM, summarization (S202, 31 tests)
- `pokemon-agent/main.py` — CLI entry point with --headless/--offline (S202, 9 tests)


### Added in S203
- `pokemon-agent/test_integration.py` (S203)
- `research/mt53/ACADEMIC_PAPERS.md` (S203)
- `pokemon-agent/.gitignore` (S203)


### Added in S204
- `pokemon-agent/action_cache.py` (S204)
- `pokemon-agent/test_action_cache.py` (S204)
- `pokemon-agent/test_real_emulator.py` (S204)
- `pokemon-agent/MEWTOO_COMPARISON.md` (S204)


### Added in S205
- `pokemon-agent/movement_validator.py` (S205)
- `pokemon-agent/screen_detector.py` (S205)
- `pokemon-agent/diversity_checker.py` (S205)


### Added in S206
- `pokemon-agent/checkpoint.py` (S206)
- `pokemon-agent/text_reader.py` (S206)
- `pokemon-agent/bridge.py` (S206)
- `pokemon-agent/setup.sh` (S206)
- `.claude/commands/pokemon-play.md` (S206)


### Added in S207
- `pokemon-agent/viewer.html` (S207)
- `pokemon-agent/S207_HANDOFF.md` (S207)
- `.claude/launch.json` (S207)


### Added in S210
- `pokemon-agent/boot_sequence.py` (S210)
- `pokemon-agent/test_boot_sequence.py` (S210)
- `CODEX_BRIDGE_PROMPT.md` (S210)
- `CODEX_OPERATING_MANUAL.md` (S210)


### Added in S211
- `CODEX_QUICKSTART.md` (S211)


### Added in S212
- `pokemon-agent/text_reader_red.py` (S212)
- `pokemon-agent/test_text_reader_red.py` (S212)
- `pokemon-agent/mgba_bindings/` (S212)
- `CLAUDE_TO_CODEX.md` (S212)

### Added in S213
- `pokemon-agent/collision_reader_red.py` (S213) — RAM-based collision map reader for A* pathfinding
- `pokemon-agent/test_collision_reader_red.py` (S213) — 14 tests


### Added in S214
- `pokemon-agent/warp_data_red.py` (S214)
- `pokemon-agent/test_warp_data_red.py` (S214)
- `pokemon-agent/red_agent.py` (S214)
- `pokemon-agent/test_red_agent.py` (S214)


### Added in S215
- `pokemon-agent/battle_ai.py` (S215)
- `pokemon-agent/test_battle_ai.py` (S215)
- `pokemon-agent/move_data.py` (S216) — Gen 1 move table (165 moves: type, power, accuracy, category)
- `pokemon-agent/test_move_data.py` (S216)
- `pokemon-agent/test_boot_wiring.py` (S215)


### Added in S216
- `pokemon-agent/move_data.py` (S216)
- `pokemon-agent/test_move_data.py` (S216)


### Added in S217
- `pokemon-agent/species_types.py` (S217)
- `pokemon-agent/test_species_types.py` (S217)
- `pokemon-agent/test_enemy_data.py` (S217)


### Added in S218
- `pokemon-agent/crystal_data.py` (S218)
- `pokemon-agent/test_crystal_data.py` (S218)


### Added in S219
- `pokemon-agent/boot_sequence_crystal.py` (S219)
- `pokemon-agent/test_boot_sequence_crystal.py` (S219)


### Added in S222
- `pokemon-agent/setup_crystal_state.py` (S222)
- `pokemon-agent/test_setup_crystal_state.py` (S222)


### Added in S223
- `self-learning/meta_tracker.py` (S223)
- `self-learning/meta_snapshots.jsonl` (S223)
- `tests/test_meta_tracker.py` (S223)


### Added in S224
- `polymarket-bot/scripts/domain_knowledge_scanner.py` (S224)
- `polymarket-bot/scripts/test_domain_knowledge_scanner.py` (S224)


### Added in S225
- `pokemon-agent/gemini_client.py` (S225)
- `pokemon-agent/tests/test_gemini_client.py` (S225)


### Added in S228
- `self-learning/wrap_summary.py` (S228)
- `tests/test_confidence_recalibrator.py` (S228)


### Added in S256
- `pokemon-agent/MT53_COMPLETION_PLAN.md` (S256)
- `codex_cmd.py` (S256)
- `codex_shell_helpers.sh` (S256)
- `tests/test_codex_cmd.py` (S256)


### Added in S231
- `design-skills/design_tokens.py` — MT-32 Phase 3: Canonical design token module. Single source of truth for CCA colors, fonts, spacing, typography. Exports CSS, Typst, Python dict. 25 tests.
- `tests/test_launcher_aliases.py` — Validates cc/cca/ccbot shell aliases in ~/.zshrc. 10 tests.
- `LAUNCHER_ALIASES.md` — Usage reference for cc/cca/ccbot launcher aliases.


### Added in S231
- `design-skills/design_tokens.py` (S231)
- `tests/test_launcher_aliases.py` (S231)
- `LAUNCHER_ALIASES.md` (S231)


### Added in S237
- `memory-system/research/PRISM_TURBOQUANT_RESEARCH.md` (S237)


### Added in S238
- `agent-guard/loop_detector.py` (S238)
- `agent-guard/hooks/loop_guard.py` (S238)
- `agent-guard/tests/test_loop_detector.py` (S238)
- `agent-guard/tests/test_loop_guard_hook.py` (S238)


### Added in S239
- `memory-system/DREAM_INTEGRATION_DESIGN.md` (S239)


### Added in S240
- `batch_wrap_analysis.py` (S240)
- `tests/test_batch_wrap_analysis.py` (S240)
- `WRAP_REFERENCE.md` (S240)


### Added in S243
- `context-monitor/hooks/pre_compact.py` (S243)
- `context-monitor/COMPACTION_PROTECTION_DESIGN.md` (S243)
- `context-monitor/tests/test_pre_compact.py` (S243)


### Added in S244
- `CC_FEATURE_NOTES.md` (S244)
- `CUSTOM_AGENTS_DESIGN.md` (S244)
- `AGENT_TEAMS_VS_HIVEMIND.md` (S244)


### Added in S245
- `COORDINATOR_MODE_ANALYSIS.md` (S245)
- `COMPACTION_ANALYSIS.md` (S245)
- `CLAUDE_MD_TOKEN_AUDIT.md` (S245)
- `CC_SOURCE_DERIVATIVES.md` (S245)


### Added in S265
- `agent-guard/blast_radius.py` (S265)
- `agent-guard/tests/test_blast_radius.py` (S265)


### Added in S292
- `leagues6-companion/planner.py` (S292)
- `leagues6-companion/refresh_discord.py` (S292)
- `leagues6-companion/exports/claude-project/` (S292)
