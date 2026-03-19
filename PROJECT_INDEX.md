# Project Index: ClaudeCodeAdvancements
# Last updated: 2026-03-19 (Session 61)
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

**Mission:** Build validated advancements for Claude Code users. NOT a betting project.
**Scope:** Read + write `/Users/matthewshields/Projects/ClaudeCodeAdvancements/` ONLY.

---

## Module Map

| Module | Path | Status | Tests |
|--------|------|--------|-------|
| Memory System | `memory-system/` | MEM-1-5 + OMEGA + FTS5 store | 212 |
| Spec System | `spec-system/` | SPEC-1-6 COMPLETE | 90 |
| Context Monitor | `context-monitor/` | CTX-1-7 + Session Pacer | 266 |
| Agent Guard | `agent-guard/` | AG-1-8 + Edit Guard | 292 |
| Usage Dashboard | `usage-dashboard/` | USAGE-1-3 COMPLETE | 197 |
| Reddit Intelligence | `reddit-intelligence/` | MT-6,9,11,14,15 | 316 |
| Self-Learning | `self-learning/` | MT-7,10,12 + Sentinel + Resurfacer + Overnight Detector + micro_reflect + ROI Tracker + Trade Reflector | 511 |
| Design Skills | `design-skills/` | MT-17 Phase 4 COMPLETE | 124 |
| Research | `research/` | Reddit scout, MT-8/MT-13 Phase 2 COMPLETE | 86 |

**Total: 2109 tests (51 suites). All must pass before any work.**

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

**context-monitor/** — Context health + compaction guard
- `hooks/meter.py` — PostToolUse token counter
- `hooks/alert.py` — PreToolUse warn/block at red/critical
- `hooks/auto_handoff.py` — Stop hook: blocks exit at critical
- `hooks/compact_anchor.py` — PostToolUse anchor writes
- `hooks/post_compact.py` — CTX-7: PostCompact recovery + journal logging
- `auto_wrap.py` — CTX-6: Automatic session wrap trigger
- `session_pacer.py` — Session pacing for 2-3h autonomous runs (CONTINUE/WRAP_SOON/WRAP_NOW)

**agent-guard/** — Multi-agent conflict prevention + safety
- `hooks/mobile_approver.py` — AG-1: iPhone push approval (ntfy.sh)
- `hooks/credential_guard.py` — AG-3: Credential extraction guard
- `hooks/network_guard.py` — AG-5: Port/firewall exposure guard
- `hooks/session_guard.py` — AG-6: Slop detection + commit tracking
- `content_scanner.py` — AG-4: Autonomous scanning hazmat (9 threat categories)
- `path_validator.py` — AG-7: Dangerous path + command detection (LIVE in hooks)
- `ownership.py` — AG-2: File ownership manifest
- `edit_guard.py` — AG-8: Edit retry prevention for structured table files (LIVE in hooks)

**usage-dashboard/** — Token + cost transparency
- `usage_counter.py` — USAGE-1: CLI token/cost counter
- `otel_receiver.py` — USAGE-2: OTLP HTTP/JSON receiver
- `hooks/cost_alert.py` — USAGE-3: PreToolUse cost threshold
- `arewedone.py` — Structural completeness checker

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
- `chart_generator.py` — SVG chart generation (bar, line, sparkline, donut)

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
- `hooks/skillbook_inject.py` — UserPromptSubmit strategy injection
- `resurfacer.py` — MT-10 Phase 3B: Findings re-surfacing + trade proposal integration
- `overnight_detector.py` — Objective time-stratified trading analysis (Wilson CI, CUSUM, SQL templates, audit)
- `research_outcomes.py` — Research ROI tracker: tracks CCA deliveries -> Kalshi implementation -> profit/loss
- `trade_reflector.py` — MT-10 Phase 3A: Kalshi trade pattern analysis (read-only DB, 5 detectors, proposals)
- `BATCH_ANALYSIS_S58.md` — Batch trace analysis of 50 sessions (avg 72.6, retry hotspots documented)

---

## Live Hooks (settings.local.json)

| Event | Hook | Purpose |
|-------|------|---------|
| PreToolUse (all) | `context-monitor/hooks/alert.py` | Warn/block at red/critical |
| PreToolUse (all) | `usage-dashboard/hooks/cost_alert.py` | Cost threshold |
| PreToolUse (all) | `agent-guard/path_validator.py` | Dangerous path/command detection |
| PreToolUse (all) | `agent-guard/edit_guard.py` | Edit retry prevention on structured files |
| PreToolUse (Bash) | `agent-guard/hooks/credential_guard.py` | Credential extraction guard |
| PostToolUse (all) | `context-monitor/hooks/meter.py` | Token counter |
| PostToolUse (all) | `context-monitor/hooks/compact_anchor.py` | Anchor writes |
| UserPromptSubmit | `spec-system/hooks/skill_activator.py` | Skill auto-activation |
| UserPromptSubmit | `self-learning/hooks/skillbook_inject.py` | Strategy injection |
| Stop | `context-monitor/hooks/auto_handoff.py` | Block exit at critical |
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
