# Project Index: ClaudeCodeAdvancements
# Last updated: 2026-03-23 (Session 132)
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
| Context Monitor | `context-monitor/` | CTX-1-7 + Session Pacer + Session Notifier (ntfy.sh) + StopFailure hook | 411 |
| Agent Guard | `agent-guard/` | AG-1-9 + Edit Guard + Bash Guard (global hook, +cp/script/dd/tee evasion) + MT-20 Senior Dev (13 modules + ADR + /senior-review + coherence + rules + fp_filter + chat + git_context + LLM + intent + tradeoff) | 1073 |
| Usage Dashboard | `usage-dashboard/` | USAGE-1-3 + doc_drift_checker (root fix) + hook_profiler | 369 |
| Reddit Intelligence | `reddit-intelligence/` | MT-6,9(Phase 3 COMPLETE),11(Phase 3 autonomous trending),14(Phase 3 COMPLETE),15,27(Phase 4 NEEDLE precision) + url_reader tests | 440 |
| Self-Learning | `self-learning/` | MT-7,10,12,26(Tier 3+E2E),27(Phase 5),28(COMPLETE) + Sentinel + Resurfacer + Resurfacer Hook + Overnight Detector + micro_reflect + ROI Tracker + Trade Reflector + Strategy Health Scorer + principle_registry + pattern_registry + detectors + regime_detector + calibration_bias + cross_platform_signal + principle_transfer + dynamic_kelly + macro_regime + fear_greed_filter + signal_pipeline + outcome_feedback + predictive_recommender + sentinel_bridge + order_flow_intel + belief_vol_surface + apf_session_tracker + deployment_verifier + principle_seeder + reflect tests | 1885 |
| Design Skills | `design-skills/` | MT-17 Phase 5 + daily snapshots + trading_chart (MT-24) + 21 chart types + consistency audit + report_charts (wired into /cca-report, +4 statistical MT-32) + BubbleChart + TreemapChart + SankeyChart + ScatterPlot + BoxPlot + HistogramChart + ViolinPlot + kalshi_data_collector + learning_data_collector + report_sidecar + report_differ (MT-33) | 1353 |
| Research | `research/` | Reddit scout, MT-8/MT-13 Phase 2 COMPLETE | 86 |

**Total: ~8683 tests (~213 suites). All must pass before any work.**

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

**design-skills/** — Professional visual output (MT-17)
- `report_generator.py` — CCA data collector + Typst renderer CLI
- `slide_generator.py` — Presentation slide generator (16:9 PDF)
- `design-guide.md` — Visual language (colors, fonts, layout)
- `templates/cca-report.typ` — Status report Typst template
- `templates/cca-slides.typ` — Presentation slide Typst template
- `dashboard_generator.py` — Self-contained HTML dashboard generator
- `chart_generator.py` — SVG chart generation (12 chart types: bar, horizontal bar, line, sparkline, donut, heatmap, stacked bar, area, stacked area, waterfall, radar, gauge)
- `website_generator.py` — Landing page + docs page HTML generator (665 LOC)
- `daily_snapshot.py` — Daily project metric snapshots with diff support (474 LOC, 50 tests)
- `report_charts.py` — SVG chart generation from report data for Typst embedding (13 chart types incl 7 Kalshi, 43 tests, S117/S122). Wired into /cca-report pipeline — charts auto-generated and embedded in PDF.
- `kalshi_data_collector.py` — MT-33: Read-only Kalshi bot DB analytics (trades, strategies, P&L, bankroll). 8 chart-ready methods. 48 tests (S122/S123).
- `learning_data_collector.py` — MT-33: Self-learning intelligence (journal events, APF trend, domain distribution). 3 chart methods. 29 tests (S122/S123).
- `report_differ.py` — MT-33 Phase 6: Structured diff between two report sidecars (test growth, MT transitions, Kalshi P&L, APF). 30 tests (S123).
- `report_sidecar.py` — MT-33 Phase 5: JSON export alongside PDF (extract, save, load, find_latest). S134.
- `MT33_DATA_MAPPING.md` — Schema mapping, SQL queries, chart-to-data design doc (S122).

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
- `priority_picker.py` — Automated MT priority selection with improved scoring (55 tests, S98)
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
- `desktop_automator.py` — MT-22: AppleScript-based Claude.app control (activate, send, close, CPU idle detection, preflight, Code tab awareness). 85 tests (S132/S136)
- `desktop_autoloop.py` — MT-22: Self-sustaining desktop loop orchestrator (resume watcher, state tracking, model selection, Code tab awareness). 60 tests (S132/S136)
- `start_desktop_autoloop.sh` — MT-22: One-command desktop auto-loop launcher (S132)
- `DESKTOP_AUTOLOOP_SETUP.md` — MT-22: Setup guide (permissions, quick start, troubleshooting)
- `session_outcome_tracker.py` — MT-10: Session prompt-to-outcome JSONL tracker (planned vs completed, auto-grade, trend analysis, outcome analyzer with pattern detection + recommendations, 62 tests, S133/S136)
- `session_timer.py` — MT-36 Phase 1: Per-step timing instrumentation for session lifecycle (init/wrap/test/code/doc categories, context manager + manual timing, JSONL persistence, cross-session averages, outlier detection, 31 tests, S144)

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
- `BATCH_ANALYSIS_S58.md` — Batch trace analysis of 50 sessions (avg 72.6, retry hotspots documented)
- `BATCH_ANALYSIS_S62.md` — Batch trace analysis of 10 recent sessions (avg 73.0, retry rate down to 40%)
- `research/SENIOR_DEV_AGENT_RESEARCH.md` — S70: Nuclear-level research for Senior Dev Agent MT (11 verified papers, 5 tools, industry standards, MVP architecture)

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
