# ClaudeCodeAdvancements — Master Roadmap
# Created: 2026-02-19 (Session 1)
# Last updated: 2026-03-21 (Session 113)
# This is the authoritative feature backlog. Update status as items complete.

---

## Evidence Base

This roadmap is grounded in:
- Anthropic's 2026 Agentic Coding Trends Report (Jan 21, 2026)
- Reddit community intelligence: r/ClaudeAI, r/ClaudeCode, r/vibecoding, r/Anthropic, r/algotrading (411+ posts analyzed via nuclear scans)
- SWE-Bench Pro data: best models at 23.3% on long-horizon tasks
- GitHub issue tracker: Issue #14227 "Persistent Memory Between Claude Code Sessions"
- Validated developer pain points from aitooldiscovery.com, paddo.dev, faros.ai

**The Validation Mandate:** Every item in this roadmap traces to at least one documented, validated user pain point. No speculative features.

---

## FRONTIER 1 — Persistent Cross-Session Memory -- COMPLETE

**Status:** ALL TASKS COMPLETE (MEM-1 through MEM-5 + OMEGA + FTS5 store + capture v2.0 + UserPromptSubmit + capture_hook tests). 340 tests passing.

**Module:** `memory-system/`

| Task | Description | Status |
|------|-------------|--------|
| MEM-1 | Memory Schema Design (`schema.md`) | COMPLETE |
| MEM-2 | Capture Hook — PostToolUse + Stop (`hooks/capture_hook.py`) | COMPLETE |
| MEM-3 | Retrieval MCP Server (`mcp_server.py`) | COMPLETE |
| MEM-4 | Compaction-Resistant Handoff (`/handoff` command) | COMPLETE |
| MEM-5 | Memory Dashboard CLI (`cli.py`) | COMPLETE |

**Key decisions:** Local-first storage at `~/.claude-memory/`. Stop hook for extraction (has `last_assistant_message`). 8-char hex suffix for IDs. Credential patterns blocked.

---

## FRONTIER 2 — Spec-Driven Development System -- COMPLETE

**Status:** ALL TASKS COMPLETE (SPEC-1 through SPEC-6 + spec_freshness + plan_compliance). 205 tests passing.

**Module:** `spec-system/`

| Task | Description | Status |
|------|-------------|--------|
| SPEC-1 | Requirements Scaffold (`/spec:requirements`) | COMPLETE |
| SPEC-2 | Design Generator (`/spec:design`) | COMPLETE |
| SPEC-3 | Task Decomposer (`/spec:tasks`) | COMPLETE |
| SPEC-4 | Implementation Runner (`/spec:implement`) | COMPLETE |
| SPEC-5 | Spec Validator Hook (`hooks/validate.py`) | COMPLETE |
| SPEC-6 | Skill Activator Hook (`hooks/skill_activator.py`) | COMPLETE |

**Enhancements shipped:** Mermaid architecture diagrams (MT-2), design vocabulary/references (MT-4), multi-persona design review `/spec:design-review` (MT-3).

---

## FRONTIER 3 — Context Health Monitor -- COMPLETE

**Status:** ALL TASKS COMPLETE (CTX-1 through CTX-7 + Session Pacer + Session Notifier + StopFailure hook). 411 tests passing.

**Module:** `context-monitor/`

| Task | Description | Status |
|------|-------------|--------|
| CTX-1 | Context Meter Hook (`hooks/meter.py`) | COMPLETE |
| CTX-2 | Status Line Display (`statusline.py`) | COMPLETE |
| CTX-3 | Threshold Alert (`hooks/alert.py`) | COMPLETE |
| CTX-4 | Auto-Handoff at Threshold (`hooks/auto_handoff.py`) | COMPLETE |
| CTX-5 | Compact Anchor (`hooks/compact_anchor.py`) | COMPLETE |

**Key decisions:** Zones: green (<50%), yellow (50-70%), red (70-85%), critical (>=85%). Reads native `context_window.used_percentage`. Atomic state writes.

---

## FRONTIER 4 — Multi-Agent Conflict Guard -- COMPLETE

**Status:** ALL TASKS COMPLETE (AG-1 through AG-9 + Edit Guard + Bash Guard + MT-20 Senior Dev Agent: 13 modules). 1073 tests passing.

**Module:** `agent-guard/`

| Task | Description | Status |
|------|-------------|--------|
| AG-1 | Mobile Approver (`hooks/mobile_approver.py`) | COMPLETE |
| AG-2 | Ownership Manifest (`ownership.py`) | COMPLETE |
| AG-3 | Credential Guard (`hooks/credential_guard.py`) | COMPLETE |
| AG-4 | Content Scanner (`content_scanner.py`) | COMPLETE |
| AG-5 | Network Guard (`hooks/network_guard.py`) | COMPLETE |
| AG-6 | Session Guard (`hooks/session_guard.py`) | COMPLETE |
| AG-7 | Path Validator (`path_validator.py`) | COMPLETE — LIVE in hooks |
| AG-8 | Edit Guard (`edit_guard.py`) | COMPLETE — LIVE in hooks |
| AG-9 | Bash Guard (`bash_guard.py`) | COMPLETE — LIVE in hooks |
| MT-20P1 | SATD Detector (`satd_detector.py`) | COMPLETE — PostToolUse hook |

**Key decisions:** ntfy.sh for iPhone push approval. Git history for ownership detection. Credential regex includes hyphens. Bash guard blocks network egress, package installs, process kills, system mods, evasion techniques.

---

## FRONTIER 5 — Usage Transparency Dashboard -- COMPLETE

**Status:** ALL TASKS COMPLETE (USAGE-1 through USAGE-3 + /arewedone + doc_drift_checker + hook_profiler). 369 tests passing.

**Module:** `usage-dashboard/`

| Task | Description | Status |
|------|-------------|--------|
| USAGE-1 | Token Counter CLI (`usage_counter.py`) | COMPLETE |
| USAGE-2 | OTel Receiver (`otel_receiver.py`) | COMPLETE |
| USAGE-3 | Cost Alert Hook (`hooks/cost_alert.py`) | COMPLETE |
| /arewedone | Structural Completeness Checker (`arewedone.py`) | COMPLETE |

**Optional:** USAGE-5 Streamlit Dashboard (not started, not urgent — CLI covers all needs).

---

## SUPPORTING MODULES -- COMPLETE

### Reddit Intelligence Plugin (361 tests)
- `reddit_reader.py` — fetches Reddit posts + all comments (no API key)
- `autonomous_scanner.py` — MT-9: full scan pipeline (prioritizer + safety)
- `github_scanner.py` — MT-11: GitHub repo intelligence
- `repo_tester.py` — MT-15: Sandboxed repo testing
- `profiles.py` — MT-6: Subreddit profiles + registry
- Commands: `/ri-scan`, `/ri-read`, `/ri-loop`

### Self-Learning System (526 tests)
- `journal.py` — structured JSONL event journal
- `reflect.py` — pattern detection + strategy recommendations
- `improver.py` — MT-10: YoYo self-building improvement loop
- `trace_analyzer.py` — MT-7: Transcript pattern analyzer
- `batch_report.py` — MT-10: Aggregate trace health
- `validate_strategies.py` — Skillbook validation
- `paper_scanner.py` — MT-12: Academic paper discovery (Semantic Scholar + arXiv)
- `resurfacer.py` — MT-10 Phase 3B: Findings re-surfacing + trade proposals
- `overnight_detector.py` — Time-stratified trading analysis (Wilson CI, CUSUM)
- `research_outcomes.py` — Research ROI tracker
- `trade_reflector.py` — MT-10 Phase 3A: Kalshi trade pattern analysis (5 detectors)
- Trading domain schema (MT-0 Phase 1): bet_placed, bet_outcome, market_research, edge_discovered, edge_rejected, strategy_shift

### Design Skills (213 tests)
- `report_generator.py` — CCA data collector + Typst renderer CLI
- `slide_generator.py` — Presentation slide generator (16:9 PDF)
- `dashboard_generator.py` — Self-contained HTML dashboard generator
- `chart_generator.py` — SVG chart generation (bar, line, sparkline, donut)
- `website_generator.py` — Landing page + docs page HTML generator
- `daily_snapshot.py` — Daily project metric snapshots with diff support

### Research (86 tests)
- `ios_project_gen.py` — MT-13: Xcode project generator (SwiftUI + tests)
- `xcode_build.py` — MT-13: Python xcodebuild wrapper

---

## MASTER-LEVEL TASKS (Next Phase)

These are multi-session aspirational goals. See `MASTER_TASKS.md` for full details.

| ID | Task | Status | Priority |
|----|------|--------|----------|
| MT-0 | Kalshi Bot Self-Learning Integration | Phase 1 COMPLETE. trade_reflector + research_outcomes built | -- |
| MT-2 | Mermaid Architecture Diagrams | COMPLETE | -- |
| MT-3 | Virtual Design Team Plugin | COMPLETE | -- |
| MT-4 | Frontend Design Vocabulary | COMPLETE | -- |
| MT-6 | On-Demand Subreddit Scanner | COMPLETE — profiles.py + registry | -- |
| MT-7 | Programmatic Trace Analysis | COMPLETE — trace_analyzer.py + batch_report.py | -- |
| MT-9 | Autonomous Cross-Subreddit Intelligence | COMPLETE — autonomous_scanner.py | -- |
| MT-10 | YoYo Self-Learning + Self-Building Loop | COMPLETE — improver.py + resurfacer.py + overnight_detector | -- |
| MT-11 | Autonomous GitHub Repo Intelligence | COMPLETE — github_scanner.py | -- |
| MT-12 | Academic Research Paper Integration | COMPLETE — paper_scanner.py (Semantic Scholar + arXiv) | -- |
| MT-13 | iOS App Development Capability | Phase 2 COMPLETE — ios_project_gen.py + xcode_build.py | -- |
| MT-14 | Re-Scan Previously Scanned Subreddits | COMPLETE — built into autonomous_scanner | -- |
| MT-15 | Sandboxed Repo Testing | COMPLETE — repo_tester.py | -- |
| MT-17 | Professional Design Skills | COMPLETE — report/slide/dashboard/chart/website/snapshot | -- |
| MT-20 | Senior Developer Agent | COMPLETE — 13 modules, ~890 tests, E2E 10/10 validated (S83) | -- |
| MT-21 | Hivemind Multi-Chat Coordination | Infrastructure COMPLETE. Phase 1 validation NOT STARTED | -- |
| MT-8 | iPhone Remote Control Perfection | Mostly self-resolved by native Remote Control | 1 |
| MT-1 | Maestro Visual Grid UI | MOSTLY SELF-RESOLVED — evaluate existing tools | 2 |
| MT-5 | Claude Pro <> Claude Code Bridge | Future — needs research | 3 |

---

## Total Test Coverage

| Module | Tests |
|--------|-------|
| memory-system | 340 |
| spec-system | 205 |
| context-monitor | 411 |
| agent-guard | 1073 |
| usage-dashboard | 369 |
| reddit-intelligence | 440 |
| self-learning | 1859 |
| design-skills | 1299 |
| research | 86 |
| root (integration + coordination) | 2281 |
| **Total** | **8363** |

---

## What This Project Is NOT

- Not a betting tool. No sports data, no odds, no Kelly criterion.
- Not a general-purpose AI assistant framework. Every tool is specific to Claude Code workflows.
- Not a research paper. Every frontier must produce something Matthew can run today.
- Not vaporware. No feature ships without a smoke test.

---

## Session History

| Session | Date | Deliverable |
|---------|------|-------------|
| 1 | 2026-02-19 | Research complete, all 5 frontier scaffolds, ROADMAP.md, PROJECT_INDEX.md |
| 2 | 2026-02-20 | MEM-1 schema, MEM-2 capture hook (37 tests), SPEC-1-5 (26 tests) |
| 3 | 2026-02-20 | GitHub live, CLAUDE.md gotchas, MASTER_ROADMAP.md |
| 6 | 2026-03-08 | AG-1 mobile approver (36 tests), browse-url, Reddit scout |
| 7-9 | 2026-03-08 | CTX-1-5, AG-2/3, MEM-5, reddit-intel plugin — 404 tests |
| 10-13 | 2026-03-15 | cca-wrap, cca-scout, URL auto-review, tmux workspace — 483 tests |
| 14-15 | 2026-03-15 | Nuclear scan COMPLETE (138 posts), self-learning system — 517 tests |
| 16 | 2026-03-15 | USAGE-1 counter, /arewedone, cca-wrap self-learning — 568 tests |
| 17 | 2026-03-16 | USAGE-2 OTel receiver, SPEC-6 skill activator, USAGE-3 cost alert — 734 tests |
| 18 | 2026-03-16 | USAGE-3 hook wiring, Kalshi tmux automation — 734 tests |
| 19 | 2026-03-16 | MASTER_TASKS.md (MT-0-MT-5), nuclear subreddit flexibility — 742 tests |
| 20-21 | 2026-03-16 | MT-0 Phase 1 (trading domain schema), MT-2/3/4 COMPLETE — 800 tests |
| 22-23 | 2026-03-16 | Nuclear scans for r/Anthropic + r/algotrading (175 posts) — 800 tests |
| 24 | 2026-03-16 | 1M context adaptive thresholds, 3 Reddit reviews, MT-6/7/8 created — 800 tests |
| 25 | 2026-03-16 | ROADMAP.md updated, MT-7 research DONE, MT-9 through MT-14 created |
| 26-50 | 2026-03-16-18 | MT-6/7/9/10/11/12/13/14/15/17 built, self-learning expanded, design-skills module |
| 51-60 | 2026-03-18-19 | Trade reflector, research outcomes tracker, FTS5 memory store, overnight detector |
| 61-65 | 2026-03-19 | FTS5 memory store, cca-loop autonomous system, KALSHI_ACTION_ITEMS bridge |
| 66-67 | 2026-03-19 | plan_compliance.py, bash_guard.py (AG-9), UserPromptSubmit capture hook |
| 68 | 2026-03-19 | plan_compliance wired into validate.py PreToolUse hook, ROADMAP updated to S68 |
| 69 | 2026-03-19 | CI/CD GitHub Actions, hook chain integration test, cca_internal_queue, bash_guard global fix |
| 70 | 2026-03-20 | doc_drift_checker.py, queue_injector.py, doc drift fixes, 3-chat parallel workflow |
| 71 | 2026-03-20 | MT-20 Phase 1: satd_detector.py (44 tests), MT-17 Phase 5 website_generator.py (39 tests) |
| 72-74 | 2026-03-20 | MT-21 Hivemind infrastructure (cca_hivemind, cca_internal_queue, cca_comm, loop_health), 3-chat sprint |
| 75-77 | 2026-03-20 | MT-20 Phases 2-5 (effort_scorer, code_quality_scorer, fp_filter, senior_dev_hook), gap analysis |
| 78-79 | 2026-03-20 | MT-20 Phases 6-9 (coherence_checker, senior_review, senior_chat, git_context) |
| 80-81 | 2026-03-20 | MT-20 all 10 gaps closed (intent verification, trade-off judgment), E2E test suite, Hivemind Phase 1 prep |
| 82 | 2026-03-20 | ROADMAP doc drift fix (+399 tests uncounted), reddit intelligence scan |
