# ClaudeCodeAdvancements — Session State
# Update at end of every session before closing.

---

## Current State (as of Session 44 — 2026-03-18)

**Phase:** Session 44 COMPLETE (2 auto cycles). Tests: 1552/1552 passing (38 suites). Git: clean after final commit.
**Next session starts at:** Run /cca-init. Priority per decay: (1) MT-10 Phase 3: findings re-surfacing (Matthew directive). (2) MT-14 rescan remaining stale subs (4 never-scanned trading subs). (3) MT-17 Phase 2 slide templates. Matthew action: install Xcode 26.3 to unblock MT-13.

---

## What Was Done in Session 44 (2026-03-18)

### MT-10 Phase 2: YoYo Self-Learning Validation (Session 4/5)
- Analyzed 4 new transcripts (scores 90, 75, 90, 65 — avg 80.0, up from 71.5)
- Batch report across 36 sessions: avg 70.8, median 75, min 15, max 100
- Distribution: 15 excellent, 12 good, 7 poor, 2 critical
- 1 new proposal generated (dedup working correctly, system stabilizing)
- Sentinel evolution: 0 mutations, 0 cross-pollinations, 6 weakness gaps (same unexplored domains)
- Validation logged to journal. One more session (5/5) to complete Phase 2.

### MT-13: iOS/macOS Dev Research (COMPLETE)
- Scope expanded: macOS apps added per Matthew's request (design, CCA tools, project enhancements)
- Key discovery: Xcode 26.3 has native Claude Agent SDK integration (Feb 2026)
- Mapped ecosystem: SwiftUI Agent Skill (twostraws), iOS Dev Guide (keskinonur), Blitz MCP submission tool, Context macOS app case study (20K LOC, 95% Claude-generated)
- Scanned r/iOSProgramming, r/SwiftUI, r/macapps — no high-signal AI dev posts
- BLOCKER: Matthew's machine has no Xcode installed (CLI tools only)
- Research doc: research/MT-13_ios_dev_research.md
- 6 findings logged to FINDINGS_LOG.md

### MT-8: Scope Closure
- Remaining config (always-on toggle, dev-start --name flags) requires files outside CCA scope
- Marked as SOLVED in priority queue — Anthropic's native Remote Control covers the use case

### r/ClaudeCode Intelligence (3 deep-reads)
- Reddit MCP Buddy (92pts, 470 stars): Validates reddit research pattern. Top comment: MCP tools should provide natural language, not raw JSON dumps.
- Claude Code humbles data engineer (105pts): Community consensus matches F2 spec system — can't one-shot, need CLAUDE.md + vertical slices + continuous testing.
- 1M Context Window debate (12pts, 100% upvoted): Context drift still real even with 1M. GSD user (u/DevMoses) recommends framework and externalized state. Validates F3 context monitor.

### MT-10 Phase 2: FINAL Validation (Session 5/5) — PHASE COMPLETE
- Analyzed 4 more transcripts (scores 65, 75, 95, 65 — avg 75.0)
- FINAL batch across 36 sessions: avg 70.8, median 75, trend improving (65->85->71->80->75)
- 14 total proposals (7 approved), dedup preventing explosion
- Phase 2 marked COMPLETE in MASTER_TASKS.md
- Phase 3 scope expanded: Kalshi graduation + findings re-surfacing (Matthew directive)

### MT-14: First-Time Subreddit Scans
- r/MachineLearning (15 posts): AIBuildAI validates MT-10 YoYo concept
- r/webdev (25 posts): AI Copilot mystery dependencies validates AG-4 content scanning
- r/iOSProgramming + r/SwiftUI scanned earlier for MT-13
- 3 subs registered in scan registry (4 trading subs still unscanned)

### Additional r/ClaudeCode Intelligence
- Haiku usage patterns (25pts): Clean hierarchy — Opus orchestrates, Sonnet executes, Haiku validates. Validates F5 model routing.

### Matthew's Questions Answered
- Q1: Xcode is the only option for native iOS/macOS dev (downloading now)
- Q2: CCA references old reviews for dedup but lacks auto-resurfacing (logged as MT-10 Phase 3B)
- Q3: Yes, skills/commands use tiered token budgets (mandatory-skills-workflow.md)
- Q4: Skills developer not worth it now — current skills stable. Logged for future.
- Q5: (incomplete — Matthew typed "and 5)" but didn't finish)
- Q6: CCA lacks systematic Anthropic changelog tracking. Gap logged.

### Session Stats (Full Session 44)
- 8 commits, 0 regressions
- 14 findings logged (6 MT-13 + 5 r/ClaudeCode + 2 r/MachineLearning + 1 r/webdev)
- Tests: 1552/1552 passing throughout
- MT-10 Phase 2 COMPLETE (milestone achievement)

---

## What Was Done in Session 43A (2026-03-18)

### MT-10 Phase 2: YoYo Self-Learning Validation (Session 3/5)
- Analyzed 4 new transcripts (scores 75, 65, 60, 85 — avg 71.25)
- Batch report across 37 total sessions: avg 71.5, median 75, min 15, max 100
- Score distribution: 16 excellent, 12 good, 7 poor, 2 critical
- 0 new proposals generated — dedup correctly preventing duplicates, system stabilizing
- Top retry hotspot: PROJECT_INDEX.md causes retries in 68% of sessions (25/37)
- SESSION_STATE.md retries in 43% of sessions (16/37)
- Sentinel evolution: 0 mutations, 0 cross-pollinations, 6 weakness gaps (5 unexplored domains)
- Avg waste rate: 33.3% across all sessions
- Key finding: system has catalogued known patterns, needs expansion into non-self-learning domains

### MT-9 Phase 4: Deep-Read r/ClaudeAI NEEDLEs
- Fetched top 25 r/ClaudeAI posts (week), 19 classified as NEEDLE (76% — classifier too loose for r/ClaudeAI)
- Manually triaged to 5 frontier-relevant, deep-read 4
- 2 REFERENCE findings logged, 2 SKIP
- Recon Tamagotchi (707pts): Rust+Ratatui tmux agent monitor. Top request = context window metric (exactly our F3). Validates MT-1, F3, F4, MT-8
- 14 Years of Journals (1951pts): Pattern detection as killer feature. Month-by-month > dump-all. Privacy = non-negotiable. Validates F1 local-first approach
- Vibe coding failures (7460pts): SKIP — meta discussion, no actionable intel
- Claude interactive (754pts): SKIP — web chat artifacts, not CC

## What Was Done in Session 43C (2026-03-18)

### 3 CCA Reviews (Matthew-requested)
- Design skill files / typeui.sh (108pts, r/ClaudeAI): ADAPT for MT-17. 57 pre-built skill files, human-curated design systems. Widens CCA design range.
- Harness setups thread (9pts, r/ClaudeCode): REFERENCE. Key patterns: modular personas, CLAUDE.md as router, Get-It-Right retrospective loop, regex-triggered rules vs skills.
- TraderAlice/OpenAlice (47pts, r/OpenClawInstall): REFERENCE-PERSONAL for Kalshi. 4-role trading architecture (research/quant/execution/risk). AGPL-3.0 license.

## What Was Done in Session 43D (2026-03-18)

### Design Guide Enhancement (MT-17)
- Added Rules Do/Don't, Quality Gates sections to design-guide.md
- Studied typeui.sh skill file structure (10 sections, concrete tokens, anti-patterns)
- Added External Design References section pointing to typeui for future style expansion

### Skillbook Strategies (MT-10)
- S10: CLAUDE.md as router not monolith (confidence 45)
- S11: Retrospective at 80% implementation (confidence 40)
- APF updated: 31.4% (222 total findings, 70 actionable)
- Growth metrics updated through Session 43

## What Was Done in Session 43E (2026-03-18)

### r/ClaudeAI Classifier Fix
- Added needle_ratio_cap=0.4 to ClaudeAI profile (was 72% NEEDLE, now capped at 40%)
- Tightened keywords: added hook, mcp, agent, workflow, automation

### Skillbook Strategies (MT-10 continued)
- S12: Read before Edit on structured docs (confidence 60) — addresses 68% retry hotspot
- S13: CC generates bloat (confidence 40) — periodic LOC tracking

### LEARNINGS Updates
- PROJECT_INDEX.md chronic retry hotspot (severity 2, 25/37 sessions)
- r/ClaudeAI classifier too loose (severity 1)

---

## What Was Done in Session 42A (2026-03-18)

### MT Priority Decay System (NEW)
- Built decay-based scoring into MASTER_TASKS.md Priority Order section
- Formula: `priority = base_value + (chats_since_last_touched * aging_rate)`
- 1pt/chat for partial tasks, 0.5pt/chat for not-started, cap at 2x base
- 9 active MTs ranked, 7 completed, 4 blocked/external
- ADHD protocol: new ideas logged but not worked until they rise in priority

### MT-10 Phase 2: YoYo Self-Learning Validation (Session 1/5)
- Ran trace_analyzer on Sessions 40 and 41 transcripts (both scored 65/100)
- Generated 5 new improvement proposals (all LOW risk, auto-approved)
- Ran Sentinel evolution cycle: 0 mutations, 0 cross-pollinations, 6 weakness gaps
- Key finding: all proposals are retry-loop/efficiency — behavioral patterns, not code bugs
- Logged validation event to self-learning journal

### MT-9 Phase 3: Supervised Autonomous Scan Trial
- Autonomous scanner auto-picked r/ClaudeAI (never scanned, highest priority)
- Fetched 25 posts, 0 blocked by safety, 16 classified as NEEDLE (64% signal)
- Scan registered in registry with timestamp
- NEEDLEs need deep-reading in future session for BUILD/ADAPT/SKIP verdicts

### MT-14 Phase 2: Skipped
- All subreddits scanned today (overnight autonomous scan) — none stale
- Phase 2 requires stale subs (>14 days). Will validate when subs age naturally.

### Memory Updates
- Saved 5 new feedback memories: MT decay scoring, ADHD idea capture, advancement tip autonomy, process improvements welcome, chat session capacity
- Updated MEMORY.md index

---

## What Was Done in Session 42B (2026-03-18)

---

## What Was Done in Session 42C (2026-03-18)

### MT-8: iPhone Remote Control Research (MOSTLY SOLVED)
- Researched Anthropic's native Remote Control feature (shipped in Claude Code v2.1.51+)
- Native solution covers 90% of MT-8's scope: `claude remote-control`, QR code, named sessions, auto-reconnect
- Remaining: configure always-on, update dev-start script with `--name` flags
- Research doc: `research/MT-8_remote_control_research.md`

### MT-10 Phase 2: Session 2/5 Validation
- Analyzed 2 more transcripts (scores 75 and 95)
- Score 95 session had 0 retries — confirms analyzer correctly identifies quality
- 2 more proposals generated (13 total, 7 approved)
- Pipeline consistent across 4 different transcripts

---

### MT-11 Phase 2: Live GitHub API Validated
- Ran live GitHub search + evaluate pipeline across 4 queries
- 30+ repos evaluated, 97 total in evaluation log
- Key finds: garrytan/gstack (23K stars, 72/100), ryanfrigo/kalshi-ai-trading-bot (210 stars, 88/100), agentic-box/memora (322 stars, 88/100 — memory system), modelcontextprotocol/servers (81K stars, 83/100)
- Pipeline: search → evaluate → dedup → log all working end-to-end

### MT-12 Phase 2: Multi-Domain Paper Scan Validated
- Ran paper scanner on agents domain (20 papers) and prediction domain (20 papers)
- 21 total logged to papers.jsonl, 16 scored IMPLEMENT
- Top finds: "LLM Reasoning to Autonomous AI Agents" (117 citations, score 80), "PredictionMarketBench" (SWE-bench for prediction market backtesting — directly relevant to Kalshi)
- Average paper score: 67.1/100

---

## What Was Done in Session 41 (2026-03-18)

### MT-17 Phase 1: Design Skills Module (COMPLETE)
- Created `design-skills/` module directory with CLAUDE.md, design-guide.md
- **design-guide.md**: Complete CCA visual language — color palette (8 colors), typography scale (7 levels), layout rules, status indicators, chart guidelines
- **report_generator.py**: CCADataCollector (parses PROJECT_INDEX, MASTER_TASKS, FINDINGS_LOG, papers.jsonl, SESSION_STATE) + ReportRenderer (Typst subprocess) + CLI
- **cca-report.typ**: Professional Typst template — title page, 8 metric cards, module status table, master tasks table, next priorities
- **21 tests** (TDD: tests written first, all passing)
- **Integration tested**: Full pipeline generates 87.8 KB PDF from real CCA data
- `/cca-report` slash command created for one-command PDF generation
- Typst 0.14.2 installed via `brew install typst`

### MT-17 Scope Expansion
- Per Matthew's directive: MT-17 now covers PDFs + presentations + graphics + websites
- Updated MASTER_TASKS.md with 5-phase output format roadmap
- Design guide applies to all output formats (same colors, fonts, spacing)

### Files Created
- `design-skills/CLAUDE.md` (NEW) — Module rules
- `design-skills/design-guide.md` (NEW) — CCA visual language
- `design-skills/report_generator.py` (NEW) — Data collector + Typst renderer + CLI
- `design-skills/templates/cca-report.typ` (NEW) — Status report Typst template
- `design-skills/tests/test_report_generator.py` (NEW) — 21 tests
- `.claude/commands/cca-report.md` (NEW) — Slash command
- `CCA_STATUS_REPORT_2026-03-18.pdf` (NEW) — First real CCA status report

---

## What Was Done in Session 40 (2026-03-18)

### Paper Deep-Reads (3 papers from MT-12 scanner results)
- "Deep Research Agents" (80/100, 117 citations, arXiv 2506.18096) — Agent taxonomy: static vs dynamic workflows, MCP integration patterns. Validates CCA autonomous scanner architecture. Gap identified: sequential execution inefficiency (could parallelize).
- "HALO" (75/100, 11 citations, arXiv 2505.13516) — 3-level hierarchy (planning→role-design→inference) + MCTS for workflow optimization. 14.4% improvement over SOTA. ADAPT: MCTS task prioritization concept could optimize /cca-auto task ordering.
- "AutoP2C" (75/100, 14 citations, has code) — LLM-based code repo generation from academic papers. Relevant to MT-12 paper→implementation pipeline.

### MT-17 Research: PDF Generation Libraries
- Evaluated 5 libraries: Typst, WeasyPrint, ReportLab, fpdf2, pdf-reports
- **RECOMMENDATION: Typst** — millisecond compilation, single binary, built-in JSON/CSV parsers, professional typography, no Python deps
- Documented full comparison in `self-learning/research/MT17_DESIGN_RESEARCH.md`
- Implementation plan: 4 phases (foundation → report types → design excellence → autonomous UI scan)

### Reddit Deep-Reads (3 posts from r/ClaudeCode this week)
- Playwright CLI tip (407pts) — CLI > MCP for token efficiency. garrytan/gstack (YC CEO skills). frank-for-you/franks-original-recipe (memory with DAG + SQLite). Closed-loop visual testing pattern.
- Reddit MCP server (62pts) — reddit-mcp-buddy (470 stars). Our reddit_reader.py already serves same purpose. Validates our approach.
- Naksha/Design Studio v4 (25pts) — 38K lines, 206 files. Massively overengineered. Only novel pattern: Design Manager routing. CCA should stay minimal.

### Files Created/Modified
- `self-learning/research/MT17_DESIGN_RESEARCH.md` (NEW) — Full library comparison + implementation plan
- `FINDINGS_LOG.md` — 3 new entries
- `generate_report_pdf.py` — Committed previous session's report script
- `CCA_STATUS_REPORT_2026-03-17.txt` — Committed previous session's text report

---

## What Was Done in Session 38 (2026-03-17)

### AG-7 path_validator Wired into Live Hooks
- Added `agent-guard/path_validator.py` to PreToolUse global matcher in `settings.local.json`
- Verified: blocks /etc writes, curl|bash commands; allows in-project writes; ignores Read tool
- Fixed SyntaxWarning from invalid escape in docstring (`F:\)` -> `F:\\)`)

### MT-12 paper_scanner.py (NEW)
- Academic paper discovery and evaluation via Semantic Scholar + arXiv APIs
- Stdlib only (urllib, json, xml) — no external dependencies
- 4 CCA-relevant domains: agents, prediction, statistics, interaction
- Paper evaluation scoring: citations (25pts) + venue quality (25pts) + domain relevance (20pts) + recency (15pts) + open access/code (15pts)
- JSONL logging to `self-learning/research/papers.jsonl`
- CLI: `search`, `domain`, `evaluate`, `log`, `stats`
- 50 tests — all passing

### PROJECT_INDEX.md Retry Rate Fix
- Trimmed from 441 lines / 28KB to 122 lines / 5.5KB (72% line reduction, 80% byte reduction)
- Created `REFERENCE.md` for detailed API docs, schemas, test summary, architecture decisions, session history
- Removed: Entry Points table, Core Module APIs, Memory Schema, Hook Architecture, Test Summary table, Key Architecture Decisions, Session History, Session Resume Checklist
- Added: Module Map table, Key Files Per Module (compact), Live Hooks table
- Updated CLAUDE.md test commands section (was listing 8 suites / 283 tests; now 36 suites / 1471)

---

## What Was Done in Session 37 (2026-03-17)

### batch_report.py (MT-10)
- Aggregate trace health across sessions (score distribution, retry hotspots)
- 13 tests — all passing

### AG-7 path_validator.py
- Dangerous path + command detection (traversal, rm -rf, dd, curl|bash)
- 30 tests — all passing
- Not yet wired into hooks (done in Session 38)

### Other
- Sentinel dialed to 5-10%, scan limit enforced
- 31-session trace analysis (PROJECT_INDEX.md 74% retry rate identified)

---

## What Was Done in Session 36 (2026-03-17)

### Exit Loop Fix
- Added "STOP RESPONDING" directives to `/cca-wrap`, `/cca-auto`, `/cca-nuclear-wrap`
- Root cause: session-ending commands had no terminal stop instruction, causing Claude to loop "Done."/"Exit." responses

### validate_strategies Wired into /cca-wrap
- Added Step 6h to wrap ritual: runs `validate_strategies.py --brief` every session
- Output: 8 confirmed, 0 contradicted, 2 unchanged (10 strategies total)

### SentinelMutator Adaptive Mutation Engine (NEW)
- `improver.py`: SentinelMutator class with 3 adaptive behaviors:
  - `mutate_from_failure()`: rejected proposals spawn counter-strategies (capped at depth 3)
  - `cross_pollinate()`: validated strategies adapted across domains
  - `scan_weaknesses()`: proactive gap detection for uncovered domains
- `Improver.evolve()`: orchestrates all 3 Sentinel steps per cycle
- MUTATION_STRATEGIES dict: domain-specific alternative approaches (6 pattern types, 3 alternatives each)
- 26 tests — all passing
- Wired into /cca-wrap as Step 6g.5

### 3 NEEDLE Deep-Reads
- macOS usage tracker (912pts) → REFERENCE: crowded market, validates our usage_counter.py approach
- claude-devtools (881pts) → REFERENCE: session log tailing, validates context-monitor approach. Novel: sub-agent tree viz
- Paper receipts (1737pts) → REFERENCE: creative SessionEnd hook. QR code for session resume = clever idea

### MT-10 Phase 2: Trace Data Generation (Session 1 of 5)
- Ran trace_analyzer on 3 recent transcripts (sessions 34-36)
- Scores: 75, 50, 75. Common: retry loops + 27-31% read waste
- Generated 6 improvement proposals (all LOW risk)
- Sentinel evolve: 0 mutations, 0 cross-pollinations, 6 weakness gaps identified

---

## What Was Done in Session 35 (2026-03-17)

### MT-15: GitHub Repo Tester/Evaluator (NEW)
- `repo_tester.py`: LanguageDetector (Python/JS/TS/Rust/Go), SandboxRunner (env-stripped, timeout-enforced), RepoTester orchestrator, RepoTestResult with verdict (QUALITY/ACCEPTABLE/LOW_QUALITY)
- Safety: never clones into CCA dir, strips all API keys/tokens from sandbox env, timeout on all operations, no global installs
- 51 tests — all passing
- Wired into github_scanner.py via `deep_evaluate()` method and `--deep` CLI flag

### needle_ratio_cap (SKILLBOOK S3 Implementation)
- Added `needle_ratio_cap` field to SubredditProfile (default 0.6)
- r/investing capped at 0.35, r/LocalLLaMA at 0.4, r/stocks at 0.35
- `quick_scan_triage()` now demotes lowest-score NEEDLEs to MAYBE when ratio exceeds cap
- 6 new tests for cap behavior — all passing

### Skillbook Auto-Inject Hook
- `self-learning/hooks/skillbook_inject.py`: UserPromptSubmit hook
- Reads SKILLBOOK.md, extracts strategies with confidence >= 50, injects as additionalContext
- Only fires once per session (env flag), only for CCA project
- 26 tests — all passing

### /cca-auto Multi-Task Default
- Updated /cca-auto to default to 2-3 sessions worth of tasks
- Loop-back behavior: complete task -> pick next -> repeat until 2-3 done or context low

### Strategy Validation Loop (validate_strategies.py)
- `validate_strategies.py`: Reads SKILLBOOK.md + journal.jsonl, validates strategies against evidence
- Strategy/ValidationResult dataclasses, StrategyValidator with evidence matching (2+ keyword minimum)
- Confidence bump on CONFIRMED (+2 per positive, max +5), drop on CONTRADICTED (-3 per negative, max -10)
- CLI: `--brief` (one-line), `--json` (structured), full report
- 30 tests — all passing

### MT-14 Foundation: Rescan Mode
- `rescan_sub()` method on AutonomousScanner: delta-scanning for stale subs
- Only returns posts newer than last scan timestamp
- `get_stale_subs()` helper, CLI `rescan` and `stale` commands
- 8 new tests (73 total autonomous scanner tests)

### Skillbook Hook Wired
- Added skillbook_inject.py to settings.local.json UserPromptSubmit hooks

---

## What Was Done in Session 33 (2026-03-17)

### Deep-Read Agents (Completed)
- r/vibecoding safety posts — 4 posts (Codex wiped F: drive, Codex deleted S3, security mistakes, agent chat room). ALL validate Agent Guard as highest-demand CCA frontier. Key tools: safeexec, tirith (Rust command interceptors). New requirements: credential-access detection, autonomous-execution detection, process-outlives-session handling.
- r/algotrading NEEDLEs — 6 posts deep-read. Top 3 for Kalshi: meta labeling (ML signal filtering, 35%->23% drawdown), Bayesian regime classification (5-regime, 3.51 Sharpe live), PMXT free orderbook data (Kalshi data imminent).

### 5 CCA Reviews
- YoYo self-evolution (ADAPT) — Time-weighted memory synthesis, auto-compaction at 80%, validates MT-10
- Unsloth Studio (SKIP) — Local LLM training UI, zero frontier overlap, MCP integration planned
- Agent 34.2% accuracy (REFERENCE) — "Skillbook" pattern: memories as distilled strategies, not raw facts
- Obsidian+Claude memory (REFERENCE) — Validates Frontier 1 demand, memory promotion logic is hardest unsolved piece
- 100K lines solo dev (REFERENCE) — Diagram agents (UX + marketing roles) produce polished visuals, "orchestration not prompting"

### Skillbook + APF Hard Metric (NEW)
- Created `self-learning/SKILLBOOK.md` — distilled strategies, not raw journal entries
- **APF (Actionable Per Find) = 32.1%** — CCA's ruthless metric (like Kalshi's net profit)
- 10 active strategies (confidence >= 50), 2 emerging (30-49), 0 archived
- Top strategies: deep-read BUILD/ADAPT only (S1), parallel agents (S2), per-sub keyword tuning (S3)
- Growth tracking table: tests 283->1259, findings 0->212, modules 5->9+ across 33 sessions
- Updated self-learning/CLAUDE.md with Skillbook architecture and APF reporting rule

### Housekeeping
- r/LocalLLaMA scan logged: 50 NEEDLE (classifier saturated — all posts match keywords)
- All findings committed to FINDINGS_LOG.md

---

## What Was Done in Session 32 (2026-03-17)

### MT-11 Phase 2: Live GitHub API Integration (COMPLETE)
- `github_scanner.py` — Added `fetch_repo()`, `search_repos()`, `scan_query()`, `scan_all_queries()` via urllib (stdlib)
- New CLI commands: `fetch <owner/repo>` (live API), `scan <query>` (search+evaluate+log), `scan --all`, `scan --json`
- GitHub API auth: uses GITHUB_TOKEN/GH_TOKEN env vars if available (60 req/hr unauthenticated, 5000 with token)
- Live-tested: 32 repos evaluated across 4 queries (Claude MCP, Kalshi trading, backtesting, context management)
- 45 tests (30 → 45) — all passing

### Autonomous Subreddit Scans: 4 Never-Scanned Subs
- r/vibecoding: 50 fetched, 36 NEEDLE, 12 MAYBE, 2 HAY — mostly memes, key safety posts for Agent Guard
- r/polymarket: 50 fetched, 4 NEEDLE, 40 MAYBE, 6 HAY — market sentiment, lower technical signal
- r/investing: 50 fetched, 48 NEEDLE, 1 MAYBE, 1 HAY — very keyword-heavy
- r/LocalLLaMA: scan initiated (pending completion)

### KALSHI_INTEL Bridge — Session 32 Updates
- Added 7 Kalshi-relevant GitHub repos (OctagonAI/kalshi-deep-trading-bot, backtesting.py, copy-trading bots, arb bots)
- Added r/polymarket scan summary
- MT-11 Phase 2 capability announcement — Kalshi research can now request GitHub repo evaluations

### GitHub Repo Intelligence Highlights
- `anthropics/claude-code`: 79K stars, no license (!), score 63/100
- `OctagonAI/kalshi-deep-trading-bot`: Python, 126 stars, score 73/100 — Kalshi-specific
- `kernc/backtesting.py`: 8K stars, gold standard backtesting — score 71/100
- `rohitg00/awesome-claude-code-toolkit`: 837 stars — curated Claude Code tools

---

## What Was Done in Session 31 (2026-03-17)

### MT-9 Phase 2: execute_scan Pipeline + /cca-nuclear Autonomous Mode (COMPLETE)
- `autonomous_scanner.py` — Added `execute_scan()` end-to-end pipeline and `ScanResult` dataclass
- Full pipeline: fetch → filter → dedup → classify → record → report
- Auto-resolves fetch params from subreddit profiles
- Updates scan_registry after each scan for sub rotation
- CLI `scan` command: auto-pick or `--target`, `--json` output, `--domain`/`--limit`/`--timeframe`
- `/cca-nuclear autonomous` mode: auto-picks highest-priority sub
- 54 tests (37 → 54) — all passing

### CTX-6: auto_wrap.py — Recovered from Interrupted Session
- `context-monitor/auto_wrap.py` — Automatic session wrap-up trigger
- Monitors context health zone, compaction count, and token ceiling
- CLI interface: check/status/compact/reset
- 19 tests — all passing

### Kalshi Research Bridge — Fully Operational
- KALSHI_INTEL.md enhanced with structured 3-chat protocol (CCA → Research → Main)
- Research Requests section: 2 HIGH resolved, 1 MEDIUM partial
- Academic papers found:
  1. Calibration Dynamics (2026): 292M Kalshi/Polymarket trades, domain-specific biases
  2. Bayesian Inverse Problems (2026): log-odds framework, regime detection
  3. Price Convergence (Operations Research): validates sniper timing near expiration
- Trading sub scans: r/algotrading (100 posts, 12 NEEDLEs), r/Kalshi (50 posts, 9 NEEDLEs)
- r/ClaudeCode scanned (150→29 new after dedup, 14 NEEDLEs)
- IBS mean reversion strategy + pre-market ML system deep-read and summarized

### Housekeeping
- Committed 10 cross-project self-learning journal entries from Kalshi bot sessions
- Test count updated: 1188 → 1244 (30 suites)

---

## What Was Done in Session 30 (2026-03-17)

### MT-9 Phase 1: Autonomous Scanner Pipeline (COMPLETE)
- `reddit-intelligence/autonomous_scanner.py` — Full autonomous scanning orchestrator
- **ScanPrioritizer**: Ranks all 15 builtin subreddit profiles by staleness + yield + never-scanned bonus.
- **SafetyGate**: Kill switch, rate limiting (50 posts/scan, 10 scans/session, 30s delay), content scanner integration.
- **AutonomousScanner**: Orchestrates pick → filter → dedup → classify → report.
- **ScanReport**: Structured output with to_dict() and summary().
- 37 tests — all passing. All 9 MT-9 safety protections enforced.

### MT-11 Phase 1: GitHub Repository Intelligence Scanner (COMPLETE)
- `reddit-intelligence/github_scanner.py` — Repo metadata evaluation without cloning
- **RepoMetadata**: Structured from GitHub API responses (stars, forks, license, topics, activity).
- **RepoEvaluator**: 0-100 scoring rubric (stars/activity/license/relevance/age). Scam detection + content_scanner safety.
- **EvaluationResult**: EVALUATE/SKIP/BLOCKED verdicts with component breakdown.
- **GitHubScanner**: Orchestrates evaluation, JSONL audit log, dedup against prior evaluations.
- **FRONTIER_KEYWORDS**: 9 frontier domains with keyword lists for relevance scoring.
- 30 tests — all passing. Safety: no cloning, no installs, GPL flagged, scam blocked.

### AG-6: Fresh-Session Anti-Contamination Guard (COMPLETE)
- `agent-guard/hooks/session_guard.py` — PreToolUse slop detection + commit tracking
- **SlopDetector**: 6 pattern categories — excessive docs (>50% lines), redundant type comments, over-engineered try/except, removed-code comments, backwards-compat shims, emojis in code.
- **SessionCommitTracker**: Per-session commit counting with configurable threshold. Warns to start fresh session after N commits (context contamination prevention).
- Inspired by Desloppify (r/ClaudeCode, 98pts).
- 28 tests — all passing.

### KALSHI_INTEL.md Bridge Artifact
- Pre-digested trading intelligence from CCA scans for Kalshi bot research chat
- Self-learning infrastructure docs (journal.py trading schema, QualityGate, trace analyzer)
- 6 high-priority food dishes (PMXT orderbook data, arb bot, nonce guard, mean reversion)
- 4 reference dishes + 2 critical warning dishes (LLMs lose money in trading competitions)

---

## What Was Done in Session 29 (2026-03-17)

### CLAUDE_AUTOCOMPACT_PCT_OVERRIDE Awareness (All Context-Monitor Hooks)
- `context-monitor/hooks/meter.py` — Reads env var, computes proximity, writes to state file. 3 new functions, 10 new tests (62 total).
- `context-monitor/hooks/alert.py` — Yellow zone warns when approaching auto-compact (<10 points). Red/critical messages include proximity info. 16 new tests (40 total).
- `context-monitor/statusline.py` — Shows AC:Xpts in status bar when approaching compaction. AC:NOW at threshold. First test suite: 24 tests.
- `context-monitor/hooks/compact_anchor.py` — Anchor includes autocompact proximity line. IMMINENT at 0 points. 3 new tests (25 total).

### MT-10: QualityGate (Geometric Mean Anti-Gaming)
- `self-learning/improver.py` — QualityGate class using Nash 1950 geometric mean scoring. Any zero metric tanks composite score. 20 new tests (64 total).
- E2E validated on 3 real CCA transcripts (scores 40-70, 6 proposals).

### Spec System Enhancements
- `spec-system/commands/design.md` — Performance Specifications section (call frequency, latency budget, resource constraints)
- `spec-system/commands/implement.md` — TDD red-green ordering enforced (test FIRST, then implement)
- `spec-system/commands/tasks.md` — Demo field (plain-English observable outcome per task)

### Reddit Intelligence
- 18 new r/ClaudeCode findings (1 new finding in FINDINGS_LOG.md this continuation)
- MASTER_TASKS.md status updates (MT-7 marked COMPLETE, MT-10 updated)

### Test Growth
- Session start: 25 suites, 1040 tests
- Session end: 26 suites, 1093 tests (+53 net new, +1 new suite)

---

## What Was Done in Session 28 (2026-03-17)

### MT-10: YoYo Self-Learning Improvement Loop (CORE COMPLETE)
- `self-learning/improver.py` — Generates structured improvement proposals from patterns
- ImprovementProposal data structure with lifecycle: proposed -> approved -> building -> validated -> committed/rejected
- ImprovementStore: JSONL persistence, dedup across sessions, status tracking
- ProposalGenerator: from_trace_report() + from_reflect_patterns() — maps 8 pattern types to proposals
- Risk classification: LOW (new utility), MEDIUM (new hook/modify code), HIGH (modify hook/trading)
- Safety guards: protected files list, max proposals per session, trading always HIGH risk
- Wired into reflect.py: trace analysis auto-generates proposals, --propose flag for reflect patterns
- 44 tests — all passing

### AG-5: Network/Port Exposure Guard (COMPLETE)
- `agent-guard/hooks/network_guard.py` — PreToolUse hook blocking port/firewall exposure
- Built from "We got hacked" incident (458pts, r/ClaudeCode) — ADB port 5555 exposed on Hetzner VM
- 20 threat patterns: adb tcpip, ufw disable/allow, iptables flush/accept, docker -p (non-localhost), ngrok/cloudflared, nc/socat listeners, python http.server, ssh -R, /etc/hosts, sshd_config
- Critical threats block by default; high threats warn. Full blocking via CLAUDE_NET_GUARD_BLOCK=1
- 53 tests — all passing

---

## What Was Done in Session 25 (2026-03-16)

### ROADMAP.md Overhaul
- Updated from Session 1 state (all frontiers showing "[ ] Research phase") to actual state (all COMPLETE, 800 tests)
- Integrated master tasks with priorities
- Updated session history through Session 25

### MT-7 Trace Analysis Research (COMPLETE)
- Analyzed 5 real CCA transcript JSONL files (322K to 9.2MB)
- Documented complete JSONL schema: entry types, message formats, tool result shapes, token/usage data location
- Defined 6 pattern detectors: retry loops, context waste, tool efficiency, session velocity, error-prone tools, compaction frequency
- Real data findings: 31% of Read calls have no subsequent reference, WebFetch 54% error rate, 38% of entries are filterable noise
- Output: `self-learning/research/TRACE_ANALYSIS_RESEARCH.md`

### New Master Tasks (MT-9 through MT-14) — Matthew's Autonomous Vision
- MT-9: Autonomous Cross-Subreddit Intelligence Gathering — Claude scans subs at its own discretion with 9 safety protections
- MT-10: YoYo Continuous Self-Learning + Self-Building — observe/detect/hypothesize/build/validate/commit loop
- MT-11: Autonomous GitHub Repository Intelligence — discover, evaluate, learn from repos (read-only analysis, rebuild from scratch)
- MT-12: Academic Research Paper Integration — Semantic Scholar + arXiv for reputable, reproducible methodologies
- MT-13: iOS App Development Capability — SwiftUI-first, target: Kalshi mobile dashboard
- MT-14: Autonomous Re-Scanning of Previously Scanned Subreddits — delta scanning, staleness tracking
- Anti-Frankenstein principle documented: every autonomous discovery must be objectively useful, clean, modular, tested, logged
- Full safety protections for autonomous operations: no executables, no credentials, no system mods, sandboxed evaluation, scam detection

### Polybot Overnight Autonomy Guidance
- Analyzed polybot-auto.md and polybot-autoresearch.md for overnight extension
- Identified 5 line changes needed (time constraints only, no structural rewrites)
- Files are in ~/.claude/commands/ (outside CCA scope — changes must be applied from non-CCA session)

**Tests:** 800/800 passing (20 suites — no new tests, research/planning session)

---

## What Was Done in Session 24b — Continuation (2026-03-16)

### Reddit Reviews (3 posts)
- "Mass building with CC 6 weeks" (57pts, 173 comments) -> REFERENCE. Validates F1 TTL pruning (ultrathink-art: lessons.md contradictions by week 6-8). "apps:20, customers:0" meta-signal.
- "Recursively self-improve agents via execution traces" (34pts) -> ADAPT. ACE framework (github.com/kayba-ai/agentic-context-engine, 2000+ stars). RLM Reflector pattern: inject traces into sandboxed REPL, write Python to query patterns. 34.3% improvement. Potentially huge for self-learning.
- "Gave agent search engine across comms" (29pts) -> REFERENCE. traul (github.com/dandaka/traul) — local SQLite+FTS5 for multi-channel comms search.

### New Master Tasks (MT-6, MT-7, MT-8)
- MT-6: On-Demand Subreddit Scanner ("Nuclear at Will") — profiles + quick-scan mode for arbitrary subs
- MT-7: Programmatic Trace Analysis for Self-Learning — adapt ACE's RLM Reflector into reflect.py
- MT-8: iPhone Remote Control Perfection — research + optimize remote control workflow
- Each MT has explicit 7-step lifecycle: research -> plan -> build -> test -> validate -> backtest -> iterate

### Philosophy Encoded
- New Severity 3 learning: "Building without testing/validation is wasted work"
- All MTs now require full lifecycle documentation (not just "build X")

**Tests:** 800/800 passing (20 suites — no new tests, review/planning session)

---

## What Was Done in Session 24 (2026-03-16)

### 1M Context Adaptive Thresholds (CTX-1 upgrade)
- Added `adaptive_thresholds(window)` to meter.py — zones tighten for large windows
- Quality ceilings: yellow=250k, red=400k, critical=600k absolute tokens
- For 200k: unchanged (50/70/85%). For 1M: adaptive (25/40/60%)
- State file now records active `thresholds` dict for downstream consumers
- 16 new tests (52 total in test_meter.py)

### Statusline Adaptive Zones (CTX-2 upgrade)
- statusline.py now uses adaptive thresholds matching meter.py
- Shows window size (e.g. "1M") when it differs from standard 200k
- Zone colors now consistent between statusline and meter

### Compact Anchor Window Display (CTX-5 upgrade)
- compact_anchor.py formats window as "200k" or "1M" instead of raw number
- Shows active thresholds when present in state file

### arewedone.py False Positive Fix
- Documented `pass` overrides (with docstring) no longer flagged as stubs
- Undocumented `pass` functions still correctly flagged
- 1 new test (51 total in test_arewedone.py)

### Infrastructure Audit
- Reviewed all 7 modules for code quality, duplication, and objective improvements
- load_state() duplication across 3 files noted but not extracted (8 lines, simpler to duplicate)
- Committed Session 23 nuclear scan results (4613abf)

### Findings Log Analysis
- Reviewed all 148 entries across 411 scanned posts
- "No one cares" post (929pts) identified as critical meta-signal: CCA needs benchmarks/evals
- New recommendations: eval framework, github/spec-kit review

**Tests:** 800/800 passing (20 suites — 17 new tests)

---

## What Was Done in Session 23 (2026-03-16)

### Nuclear Scan: r/Anthropic — COMPLETE
- Fetched 75 posts (Top/Month, min-score 20)
- 65 fast-skipped (politics, Pentagon/DOD/Trump drama, praise posts, corporate news — ~85% noise)
- 10 deep-reviewed
- Verdicts: 0 BUILD, 0 ADAPT, 6 REFERENCE, 4 SKIP, 65 FAST-SKIP
- Key finds: import-memory feature (F1 validation), N1AI/claude-hidden-toolkit (28 internal tools), inference margins data (F5)
- NUCLEAR_REPORT_anthropic.md finalized
- Recommendation: Do NOT re-scan r/Anthropic — signal too low for CCA

### Nuclear Scan: r/algotrading — COMPLETE
- Fetched 100 posts (Top/Year, min-score 50), 98 after dedup
- 91 fast-skipped (equities/forex/crypto strategies, career questions, memes)
- 7 deep-reviewed (prediction market + AI agent posts)
- Verdicts: 0 BUILD, 0 ADAPT, 4 REFERENCE, 3 REFERENCE-PERSONAL, 91 FAST-SKIP
- POLYBOT-RELEVANT: PMXT free orderbook data (680pts), Kalshi-Polymarket arb bot (369pts), 5c arb spreads (142pts)
- LLM trading limitations: all LLMs lost money in prediction arena competition
- NUCLEAR_REPORT_algotrading.md finalized
- Recommendation: Do NOT re-scan r/algotrading for CCA. Monitor prediction-market posts only for Polybot.

### Session Stats
- 35 new FINDINGS_LOG entries (both subs combined)
- All 4 nuclear scans now COMPLETE: r/ClaudeCode (138), r/ClaudeAI (100), r/Anthropic (75), r/algotrading (98) = 411 total posts scanned

**Tests:** 783/783 passing (20 suites — no code changes, scan-only session)

---

## What Was Done in Session 22 (2026-03-16)

### Nuclear Scan: r/ClaudeAI — COMPLETE
- Fetched 100 posts (Top/Month, min-score 30)
- 59 fast-skipped (memes, news, politics, praise — r/ClaudeAI is ~60% noise vs ~40% for r/ClaudeCode)
- 41 deep-reviewed in 3 priority tiers: P1 (11 frontier-direct), P2 (11 workflow), P3 (19 reference/skip)
- Verdicts: 2 BUILD, 1 ADAPT, 24 REFERENCE, 21 SKIP
- BUILD: 1M context validation (F3), usage bars removed (F5)
- ADAPT: Anthropic memory import feature (F1 — shallow, web-chat only, validates our approach)
- Key tools: github/spec-kit (F2), Anamnese MCP (F1), cc-director (F4), ccstatusline-usage (F5)
- NUCLEAR_REPORT_claudeai.md finalized
- 28 new FINDINGS_LOG entries

### Reddit Reviews (Session Start)
- "Biggest productivity gain from Claude Code" (71pts) — REFERENCE, validates F1+F3
- "Obsidian as persistent brain for Claude" (297pts) — REFERENCE, massive F1 validation

### Committed Session 21 Work
- 14 files, 799 insertions (MT-0 P1, MT-3, MT-4, Session 22 reviews)

### Learnings for Next Nuclear Scans
1. r/ClaudeAI ~60% noise — title-based triage saves massive tokens
2. P1/P2/P3 tiering is effective — frontier-direct posts first
3. Comments contain better signal than posts (1-3pt comments have best tools)
4. r/Anthropic: expect more noise (politics, corporate news), use min-score 30+
5. r/algotrading: filter for prediction markets, skip equities/forex/crypto-specific

**Tests:** 783/783 passing (20 suites — no code changes, scan-only session)

---

## What Was Done in Session 21 (2026-03-16)

### MT-0: Trading Domain Schema (Phase 1 COMPLETE)
- Added 6 trading event types to `self-learning/journal.py`: bet_placed, bet_outcome, market_research, edge_discovered, edge_rejected, strategy_shift
- Added `trading` domain to VALID_DOMAINS
- Built `get_trading_metrics()` — aggregates PnL, win rate, by-market-type, by-strategy, research effectiveness
- Added `trading-stats` CLI subcommand
- Added 4 trading pattern detectors to `self-learning/reflect.py`: losing_strategy (per-strategy win rate), research_dead_end (0-actionable paths), negative_pnl (cumulative loss), strong_edge_discovery (high discovery rate)
- Added trading section + 4 bounded params to `self-learning/strategy.json`
- Added trading metrics display to reflect.py full report
- 24 new tests in `self-learning/tests/test_self_learning.py` (75 total)

### MT-3: Virtual Design Team (COMPLETE)
- Created `spec-system/commands/design-review.md` — multi-persona design review
- 4 expert personas: UX Researcher, Security & Privacy Engineer, Performance & Scalability Architect, Maintainability & Testing Engineer
- Each reviews design.md independently, consolidated into APPROVE/REVISE/REDESIGN verdict
- Thin wrapper at `.claude/commands/spec-design-review.md`

### MT-4: Design Vocabulary (COMPLETE)
- Added Section 1b "Design References" to `spec-system/commands/design.md`
- Optional for UI/visual features, skipped for backend/hook/library work
- Covers: reference UIs, design vocabulary, layout patterns, color constraints
- Auto-asks user once if preferences not specified

### MASTER_TASKS.md Updated
- MT-0: Status updated to Phase 1 COMPLETE
- MT-2: Status updated to COMPLETE (Session 19)
- MT-3: Status updated to COMPLETE
- MT-4: Status updated to COMPLETE
- Priority order: 4 of 6 struck through as complete

**Tests:** 783/783 passing (20 suites — 24 new tests)

---

## What Was Done in Session 20 (2026-03-16)

### Self-Learning Improvements (from CCA vs YoYo analysis)
- Enabled bounded auto_adjust in strategy.json with safety rails
- Added pain/win signal tracking to journal.py (new event types + get_pain_win_summary())
- Wired session-end self-learning into all 4 wrap commands (cca-wrap, wrap-up, polybot-wrap, polybot-wrapresearch)
- 17 new tests (bounded auto-adjust + pain/win signals)

### Reddit Reviews (5 posts)
- Architecture problem post (REFERENCE), Scryer shared memory MCP (REFERENCE), CLAUDE.md size post (REFERENCE), Clui CC (REFERENCE), 2x usage checker (REFERENCE)
- All logged to FINDINGS_LOG.md

### Memory Updates
- Saved 2x token promotion schedule (March 13-28)
- Saved detachable tabs feedback (ADHD-friendly UI requirement)
- Saved global self-learning ritual requirement

**Tests:** 759/759 passing (20 suites — 17 new tests)

---

## What Was Done in Session 19 (2026-03-16)

### CCA vs YoYo Comparative Analysis
- Thorough honest comparison: what CCA self-learning does well (structured schema, separated concerns, strategy-as-data, sample-size guards) vs where it falls short (no autonomous loop, no codebase-as-memory, no pain/win tracking, no self-awareness, no pruning)
- Incorporated u/ultrathink_art security insight (treat issue content as read-only data) and u/inbetweenthebleeps plateau observation (self-improvement optimizes mechanics, not architectural judgment)
- 6 concrete enhancement paths ranked by impact-per-token: (1) flip auto_adjust for bounded params, (2) pain/win signals, (3) session-end self-reflection hook, (4) relevance-weighted pattern detection, (5) artifact feedback, (6) quarterly pruning

### Master-Level Tasks (MASTER_TASKS.md)
- MT-0: Kalshi bot self-learning integration — BIGGEST task, detailed technical path for adapting journal.py to trading domain with edge fingerprinting, research path tracking, and pain/win signals
- MT-5: Claude Pro ↔ Claude Code bridge — future task for strategy discussions across interfaces
- Priority order updated: MT-0 → MT-2 → MT-4 → MT-3 → MT-1 → MT-5
- Both saved to persistent memory (project_kalshi_self_learning.md, project_claude_pro_bridge.md)

### CCA-Nuclear Subreddit Flexibility
- `/cca-nuclear` now accepts optional subreddit argument: `/cca-nuclear r/LocalLLaMA`
- Default remains r/ClaudeCode when no argument given
- All progress/queue/report files namespaced by subreddit slug (e.g., `nuclear_progress_localllama.json`)
- Backwards compatible: r/ClaudeCode uses original filenames (no suffix)
- Added `subreddit_slug()` function to `nuclear_fetcher.py` for filesystem-safe slug conversion
- 8 new tests for slug function (44 total in test_nuclear_fetcher.py)

### Terminal.app Kalshi Launcher
- New script: `scripts/kalshi-launch.sh` — opens two separate Terminal.app windows via AppleScript
- Uses tab references (not window indices) to reliably target each window for subsequent commands
- Custom window titles: "Kalshi Main" / "Kalshi Research" for visual identification
- Auto-runs: cd, claude --dangerously-skip-permissions, /polybot-init, auto commands, instructions
- Install: `cp scripts/kalshi-launch.sh ~/.local/bin/kalshi-launch && chmod +x ~/.local/bin/kalshi-launch`

### Frontend-Design Plugin Review (ADAPT)
- Thorough /cca-review of r/ClaudeCode post (631pts, 156 comments, all read)
- Plugin itself is trivial (markdown prompt) — real value in community comment patterns
- Key patterns: design vocabulary from Midjourney/PromptHero, multi-model pipeline (Gemini design guide -> Claude), screenshot-reference approach, 5-template-then-pick workflow
- Updated FINDINGS_LOG entry from REFERENCE to ADAPT with full analysis

**Tests:** 742/742 passing (20 suites — 8 new tests)

---

## What Was Done in Session 18 (2026-03-16)

### USAGE-3 Hook Wiring
- Wired `cost_alert.py` into `.claude/settings.local.json` as PreToolUse hook
- Added alongside existing `alert.py` in the empty-matcher group (fires on all tool calls)
- Hook self-filters: cheap tools (Read/Glob/Grep/TodoWrite) always silently pass
- Verified: JSON valid, hook returns `{}` for both cheap and expensive tools (no cost data yet)
- Once OTel receiver is running, the hook will have live cost data to check thresholds

### Kalshi Dual-Chat Automation
- Rewrote `~/.local/bin/dev-start` to use tmux split panes for side-by-side Kalshi chats
- Script creates 2 vertical split panes, each running `claude --dangerously-skip-permissions`
- Auto-sends `/polybot-init`, `/polybot-auto` (main) and `/polybot-autoresearch` (research) + full instructions
- Mouse mode enabled for click-to-switch between panes
- Debugged: AppleScript approach failed (Accessibility permissions, wrong-window targeting), Claude Squad failed (worktree breaks shared filesystem), final solution is tmux `send-keys`
- Fixed tmux socket corruption (`/private/tmp/tmux-501/default`) caused by `tmux kill-server`
- Created `KALSHI_CHEATSHEET.md` — daily operations quick reference

**Tests:** 734/734 passing (no new tests — infrastructure/wiring changes only)

---

## What Was Done in Session 17 (2026-03-16)

### USAGE-2: OTel OTLP Receiver (NEW — usage-dashboard/otel_receiver.py)
- Lightweight stdlib-only OTLP HTTP/JSON receiver for Claude Code's native OTel metrics
- Receives metrics + events on localhost:4318, stores as daily JSONL in `~/.claude-otel-metrics/`
- Parses `claude_code.token.usage`, `claude_code.cost.usage`, and 6 other CC metric types
- CLI: `start` (daemon), `status`, `query`, `summary`
- `usage_counter.py live` subcommand added — imports otel_receiver for real-time view
- 63 tests, all passing

### SPEC-6: Skill Auto-Activation Hook (NEW — spec-system/hooks/skill_activator.py)
- UserPromptSubmit hook that analyzes prompts for intent signals
- Injects skill activation reminders via additionalContext before Claude processes prompt
- Configurable via `skill_rules.json`: keywords, intent regex, exclude patterns, priority ordering
- 5 rules: spec-new-feature (priority 10), spec-design-needed (8), debug-systematic (7), tdd-reminder (5), review-url (9, disabled)
- Max 2 activations per prompt, log_activations to stderr
- Wired into `.claude/settings.local.json` as UserPromptSubmit hook
- 64 tests, all passing

### USAGE-3: Cost Threshold Alert Hook (NEW — usage-dashboard/hooks/cost_alert.py)
- PreToolUse hook that warns/blocks when session cost exceeds thresholds
- Dual-source: tries OTel receiver data first (real-time), falls back to transcript JSONL
- Cheap tools (Read/Glob/Grep/TodoWrite) always silently allowed
- Default thresholds: warn at $5, block at $20 (configurable via env vars)
- `CLAUDE_COST_BLOCK_ENABLED=1` to enable blocking (warn-only by default)
- 39 tests, all passing

### OTel Environment Setup
- `otel_setup.sh` script created for ~/.zshrc configuration
- OTel env vars configured in Matthew's ~/.zshrc:
  - `CLAUDE_CODE_ENABLE_TELEMETRY=1`
  - `OTEL_METRICS_EXPORTER=otlp`, `OTEL_LOGS_EXPORTER=otlp`
  - `OTEL_EXPORTER_OTLP_PROTOCOL=http/json`
  - `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318`

### Reddit Review
- RunMaestro/Maestro (2500 stars) — REFERENCE for Frontier 4+5, mature Cue trigger system
- B2B SaaS Growth Skill — SKIP (off-scope)

### Tests: 734/734 passing (20 suites — 166 new tests)

---

## What Was Done in Session 16 (2026-03-15)

### Implementation — Top BUILD Candidates from Nuclear Scan

**Commit backlog cleared:**
- Committed all sessions 10-15 work in single clean commit (0581d17)
- 28 files, 5604 insertions — revertable with `git revert 0581d17`

**USAGE-1: Token Counter CLI (NEW — usage-dashboard/usage_counter.py)**
- Reads Claude Code transcript JSONL for per-session token/cost breakdown
- Supports sonnet/opus/haiku pricing models
- Commands: sessions, session <id>, today, week, project [path]
- Revealed: $516.94 total across 11 CCA sessions
- 44 tests, all passing

**/arewedone: Structural Completeness Checker (NEW — usage-dashboard/arewedone.py)**
- Scans all 7 modules for: CLAUDE.md, source files, tests, test pass/fail
- Detects code stubs (TODO/FIXME/NotImplementedError) excluding test fixtures
- Reports uncommitted files, doc freshness, syntax errors
- --quiet mode for CI-style exit code (0=pass, 1=issues)
- 50 tests, all passing
- Found and fixed: missing CLAUDE.md in reddit-intelligence/ and self-learning/

**cca-wrap upgraded:**
- Added "Review & Apply" self-learning phase
- Runs reflect.py at session end, logs patterns, suggests rule updates

**External tools installed:**
- claude-devtools v0.4.8 — `brew install --cask` (read-only session log viewer)
- Claude Usage Bar v0.0.6 — /Applications (needs OAuth setup)
- Claude Island v1.2 — /Applications (NOT launched — auto-installs hooks, could affect Kalshi chats)

**Tests:** 568/568 passing (17 suites — 94 new tests)

---

## CRITICAL: Uncommitted Work From Sessions 7+8

All files below exist on disk and tests pass, but have never been committed. Commit first:

```bash
git add agent-guard/hooks/credential_guard.py
git add agent-guard/ownership.py
git add agent-guard/tests/test_credential_guard.py
git add agent-guard/tests/test_ownership.py
git add context-monitor/hooks/
git add context-monitor/statusline.py
git add context-monitor/tests/
git add memory-system/cli.py
git add memory-system/tests/test_cli.py
git add reddit-intelligence/
git add .claude/commands/ag-ownership.md
git add .claude/commands/cca-auto.md
git add .claude/commands/cca-init.md
git add .claude/commands/cca-review.md
git add .claude/commands/cca-wrap.md
git add .claude/commands/reddit-intel/
git add .claude/commands/reddit-research.md
git add FINDINGS_LOG.md
git add .claude/settings.local.json
git add CLAUDE.md
git add SESSION_STATE.md
```

Then commit with a message covering sessions 7+8 deliverables.

---

## What Was Done in Session 15 (2026-03-15)

### Nuclear Scan Session 2 — COMPLETED
- Reviewed remaining 65 posts (33 fast-skip + 32 deep-read)
- Nuclear scan now COMPLETE: all 138 posts processed, 110 unique reviews
- Final stats: 5 BUILD, 23 ADAPT, 20 REFERENCE, 6 SKIP, 57 FAST-SKIP
- Special flags: 1 polybot-relevant, 3 maestro-relevant, 9 usage-dashboard
- NUCLEAR_REPORT.md finalized with ranked BUILD candidates and grouped ADAPT patterns
- FINDINGS_LOG.md expanded from 54 to 82 entries
- Top BUILD candidates: (1) claude-devtools 879pts, (2) OTel Metrics 807pts, (3) Self-Improvement Loop 269pts, (4) Claude Island 309pts, (5) Usage Menu Bar 282pts

### Notes
- Maestro retry POSTPONED to 2026-03-16 (Kalshi bot running in terminal tonight)
- Uncommitted work from sessions 7-15 still needs committing (CRITICAL)

**Tests:** 517+ passing (15 suites)

---

## What Was Done in Session 14 (2026-03-15)

### Nuclear Scan Batch 1
- Reviewed 45/110 posts from r/ClaudeCode (Top > Year)
- 2 BUILD, 8 ADAPT, 9 REFERENCE, 5 SKIP, 21 FAST-SKIP
- Signal rate: 22.2% (BUILD+ADAPT / reviewed)
- Top BUILD: OTel metrics integration, claude-devtools desktop app
- Progress saved to `reddit-intelligence/findings/nuclear_progress.json`
- Interim report at `reddit-intelligence/findings/NUCLEAR_REPORT.md`
- 22 new entries in FINDINGS_LOG.md (54 total)

### Self-Learning System (NEW)
- `self-learning/journal.py` — structured append-only event log (JSONL)
- `self-learning/reflect.py` — pattern detection + strategy recommendations
- `self-learning/strategy.json` — tunable parameters (v1)
- `self-learning/tests/test_self_learning.py` — 34 tests, all passing
- `.claude/commands/cca-nuclear-wrap.md` — nuclear wrap command with self-learning integration
- 5 journal entries logged (1 batch, 2 BUILD verdicts, 1 pattern, 1 session outcome)
- 10 learnings captured

### Key Learnings
- CC natively emits OTel metrics — USAGE-1 should use this
- MCP tools consume 70k+ tokens even when unused (#1 context killer)
- ENABLE_LSP_TOOL hidden flag (50ms vs 30-60s navigation)
- evolve-yourself pattern: frequency-based skill auto-create at 3x/day

**Tests:** 517/517 passing (15 suites — includes 34 new self-learning tests)

---

## What Was Done in Session 12 (2026-03-15)

### Master Window Project + Research Deep Dive

**Reddit reviews (14 posts this session, 22 total in FINDINGS_LOG):**
- YoYo self-evolving agent (ADAPT — self-learning journal loop, 941pts)
- Crucix intelligence center (SKIP — data dashboard, not agent management)
- Maestro multi-session orchestrator (BUILD — 476pts, grid UI, macOS native)
- Maestro teaser post (REFERENCE — 424pts, confirms community demand)
- Agent Teams full walkthrough (ADAPT — sendMessage pattern, Cozempic pruner)
- Personal Claude setup / Adderall post (same as Maestro — already logged)

**Multi-agent tool research (15 tools evaluated):**
- Claude Squad, Recon, Agent Deck, Codeman, NTM, claude-tmux, Claude Dashboard,
  IttyBitty, CCManager, Amux, claude-code-monitor, claude-code-dashboard, TmuxCC,
  tmux-claude-code, Maestro

**Infrastructure built:**
- Maestro v0.2.4 built from source (Tauri + Rust, 2m55s compile)
  - CRASHED: macOS 15.6 beta SDK incompatibility (_NSUserActivityTypeBrowsingWeb symbol)
  - .dmg saved at /tmp/maestro-build/target/release/bundle/dmg/
- Claude Squad v1.0.17 installed (brew install claude-squad)
- tmux 3-session workspace configured and tested (20/20 tests passing):
  - Window 0: cca (ClaudeCodeAdvancements, normal perms)
  - Window 1: kalshi-1 (polymarket-bot, --dangerously-skip-permissions)
  - Window 2: kalshi-2 (polymarket-bot, --dangerously-skip-permissions)
- `~/.local/bin/dev-start` updated with auto-launch + idempotent re-attach
- `~/.local/bin/cs-start` created (Claude Squad launcher, backup option)

**Architecture designed:**
- Self-learning Polybot journal + strategy feedback loop (YoYo pattern adapted for trading)
- Cross-chat coordination via shared journal file
- Master plan documented in SESSION_STATE.md for future session persistence

**Tests:** 483/483 passing (no code changes to CCA modules)

---

## What Was Done in Session 11 (2026-03-15)

### Research + Tooling — Reddit Reviews + tmux/Recon Install

**Reddit reviews (9 posts — 2 batches):**
- Batch 1: algotrading strategy list (REF-PERSONAL), VEI signal (REF-PERSONAL), "crusade" meme (REF), Beast 6-month tips (ADAPT)
- Batch 2: ClaudePrism academic workspace (REF-PERSONAL), code-commentary (SKIP), Recon tmux dashboard (BUILD), Membase (REF), agtx kanban (REF)

**Key findings captured:**
- LEARNINGS: file-writing hooks trigger system-reminder context burn (Severity 2)
- UserPromptSubmit skill auto-activation hook — new buildable pattern from Beast post
- 3 linked repos to review: github/spec-kit, facetlayer/candle, dimitritholen/raggy

**Infrastructure installed:**
- tmux 3.6a (brew install tmux)
- Rust 1.94.0 (brew install rust)
- Recon v0.1.0 (cargo install, tmux-native CC agent dashboard)
- ~/.tmux.conf with Recon keybindings (prefix+g dashboard, prefix+i next input)
- ~/.local/bin/dev-start script (3-window tmux: CCA + 2 Kalshi bot sessions)

**Framework upgrades:**
- cca-review command: added REFERENCE-PERSONAL verdict (synced to global)
- Memory: user_profile.md, feedback_personal_tools.md
- CHANGELOG, FINDINGS_LOG, SESSION_STATE all updated

**Tests:** 483/483 passing (no code changes)

---

## What Was Done in Session 10 (2026-03-15)

### Framework Upgrade — Session Management + Reddit Pipeline

**New commands:**
- `/cca-wrap` — session end ritual with self-grading, learnings capture, resume prompts
- `/cca-scout` — autonomous subreddit scanner (filters by score, dedupes vs FINDINGS_LOG)

**CLAUDE.md upgrades:**
- Added "URL Review — Auto-Trigger" section (any URL pasted auto-triggers /cca-review)
- Added "Session Commands" reference table (all 7 CCA commands documented)

**Reddit reviews (8 posts):**
- Defuddle URL reading (ADAPT) — incorporated url_reader.py approach
- claude-code-best-practice 15k-star repo (REFERENCE) — confirmed CCA already follows most patterns
- OpenClaw/Public.com autonomous trading (REFERENCE) — flagged for polybot research chat
- CShip statusline (BUILD) — installed, wired into settings.json
- Autoresearch + Ouro Loop (ADAPT) — IRON LAWS prompt generated for polybot
- Session transcript tools (ADAPT) — installed claude-code-transcripts
- RTK token compression (BUILD) — confirmed already installed and working
- iOS shipping best practices (REFERENCE) — CLAUDE.md-as-contract pattern validated

**Infrastructure verified:**
- CShip v1.0.80 — running, statusline configured
- RTK v0.29.0 — running, hook wired
- All 5 /cca-* commands copied to ~/.claude/commands/ (global)
- Mobile approver hook — running
- claude-code-transcripts — installed via Homebrew

**Tests:** 483/483 passing (13 suites) — up from 404 (test count increase is from existing tests, no new test files)

---

## What Was Done in Session 9

Wrap-only session. No new code. Confirmed 404/404 tests passing across 13 suites.

---

## What Was Done in Session 8 (2026-03-08)

### CTX-4: Auto-Handoff Stop Hook (complete — 27 tests)

**File:** `context-monitor/hooks/auto_handoff.py`

**What it does:**
- Runs at session end (Stop hook)
- If context zone is `critical` → blocks exit, asks Claude to run `/handoff`
- If context zone is `red` → warns to stderr (non-blocking by default)
- If `HANDOFF.md` was written in the last 5 minutes → always allows exit (anti-loop)
- Silent pass-through for green/yellow/unknown

**Anti-loop mechanism:** `handoff_is_fresh(path, max_age_minutes)` checks mtime.

**Output format (Stop hook):**
- Allow: `{}`
- Block: `{"decision": "block", "reason": "..."}`

**Environment variables:**
- `CLAUDE_CONTEXT_STATE_FILE` — state file (default: `~/.claude-context-health.json`)
- `CLAUDE_CONTEXT_HANDOFF_PATH` — HANDOFF.md path (default: `./HANDOFF.md`)
- `CLAUDE_CONTEXT_HANDOFF_AGE` — max age minutes before re-triggering (default: 5)
- `CLAUDE_CONTEXT_HANDOFF_RED` — set "1" to also block on red zone
- `CLAUDE_CONTEXT_HANDOFF_DISABLED` — set "1" to disable

**Wired:** `Stop` hook in `.claude/settings.local.json`

---

### CTX-5: Compaction Anchor Hook (complete — 22 tests)

**File:** `context-monitor/hooks/compact_anchor.py`

**What it does:**
- Runs as PostToolUse hook (alongside meter.py)
- Every N tool calls (default: 10), writes `.claude-compact-anchor.md` to project root
- File contains: context zone/%, session ID prefix, last tool called, instructions to re-read SESSION_STATE.md after compaction
- Stores `turn_count` as a machine-parseable comment for round-trip integrity
- Atomic write via temp file

**Key functions:**
- `should_write(turn_count, write_every)` — True at turn 0 and every N turns
- `build_anchor_content(state, tool_name, turn_count, session_id)` — builds markdown
- `load_anchor_turn_count(path)` — reads back `<!-- turn_count: N -->` from anchor

**Environment variables:**
- `CLAUDE_CONTEXT_STATE_FILE` — state file path
- `CLAUDE_CONTEXT_ANCHOR_PATH` — anchor file path (default: `./.claude-compact-anchor.md`)
- `CLAUDE_CONTEXT_ANCHOR_EVERY` — write interval in turns (default: 10)
- `CLAUDE_CONTEXT_ANCHOR_DISABLED` — set "1" to disable

**Wired:** second hook in `PostToolUse` array in `.claude/settings.local.json`

---

### MEM-5: CLI Memory Viewer (complete — 28 tests)

**File:** `memory-system/cli.py`

**Usage:**
```bash
python3 memory-system/cli.py list                           # Current project memories
python3 memory-system/cli.py list --project myapp          # Specific project
python3 memory-system/cli.py list --global                 # Global memories
python3 memory-system/cli.py list --all                    # All projects
python3 memory-system/cli.py list --confidence HIGH        # Filter by confidence
python3 memory-system/cli.py list --type decision          # Filter by type
python3 memory-system/cli.py search "SQLite"               # Keyword/tag search
python3 memory-system/cli.py delete mem_20260219_143022_abc  # Delete by ID
python3 memory-system/cli.py purge                         # Remove expired memories
python3 memory-system/cli.py stats                         # Summary counts
```

**TTL by confidence:** HIGH=365 days, MEDIUM=180 days, LOW=90 days

---

### AG-2: Ownership Manifest (complete — 27 tests)

**Files:** `agent-guard/ownership.py`, `agent-guard/tests/test_ownership.py`, `.claude/commands/ag-ownership.md`

**What it does:**
- CLI tool: `python3 agent-guard/ownership.py`
- Reads last N git commits (default: 20), maps which files were changed by which session
- Detects "conflict risk" files — those appearing in 2+ commits in the window
- Shows uncommitted changes (files in-flight this session)
- Outputs Markdown report with columns: File | Last Session | Date | Commit
- Session label extraction: recognizes "AG-1:", "CTX-3:", "Session 6:" prefixes in commit subjects
- Available as `/ag-ownership` slash command

**Options:** `--commits N`, `--hours N`, `--conflicts-only`, `--output PATH`

---

### CTX-3: Alert Hook (complete — 24 tests)

**File:** `context-monitor/hooks/alert.py`

PreToolUse hook. Silent for cheap tools (Read/Glob/Grep/TodoWrite). Warns before expensive tools (Agent/WebSearch/WebFetch/Bash/Write/Edit) in red/critical zones. Opt-in blocking via `CLAUDE_CONTEXT_ALERT_BLOCK=1`.

---

### CTX-2: Statusline (complete)

**File:** `context-monitor/statusline.py`

Reads native `context_window.used_percentage` from stdin JSON (Claude Code provides this natively). ANSI-colored bar: `CTX [======    ] 45% ok   | $0.02 | Sonnet`. Wired in `~/.claude/settings.json` globally.

---

### CTX-1: Context Meter Hook (complete — 36 tests)

**Files:**
- `context-monitor/hooks/meter.py` — PostToolUse hook
- `context-monitor/tests/test_meter.py` — 36 tests

**What it does:**
1. Reads session transcript JSONL after every tool call
2. Extracts total prompt tokens from `entry["message"]["usage"]` (assistant entries)
3. Computes % of configured window (default 200k)
4. Classifies: green (<50%) / yellow (50–70%) / red (70–85%) / critical (≥85%)
5. Writes state atomically to `~/.claude-context-health.json`

**Transcript path derivation:**
```python
project_hash = os.getcwd().replace('/', '-')  # e.g. '-Users-matthewshields-...'
path = ~/.claude/projects/<project_hash>/<session_id>.jsonl
```

---

### AG-3: Credential-Extraction Guard (complete — 40 tests)

**File:** `agent-guard/hooks/credential_guard.py`

PreToolUse hook. Flags Bash commands that could extract env vars, read .env files, or exfiltrate credentials.

---

### reddit-intel plugin (complete — 43 tests)

**Files:** `reddit-intelligence/` — full plugin including reddit_reader.py, test suite, commands.

---

## What Was Done in Session 7

### reddit-intel Claude Code Plugin (complete)

`.claude/commands/reddit-intel/` contains symlinks to `reddit-intelligence/commands/ri-*.md`.
Available in this project as `/reddit-intel:ri-scan`, `/reddit-intel:ri-read`, `/reddit-intel:ri-loop`.

---

## What Was Done in Session 6

### AG-1: Mobile Approver iPhone Hook (complete — 36 tests)
- `agent-guard/hooks/mobile_approver.py` — PreToolUse hook using ntfy.sh
- Sends push notification to iPhone with Allow/Deny action buttons on lock screen
- Claude waits up to 60s for response; fails open if no network or no topic configured

### Reddit Scout + browse-url global skill (complete)

---

## Frontier Status

| Frontier | Module | Status | Tests | Next Action |
|----------|--------|--------|-------|-------------|
| 1: Persistent Memory | memory-system/ | MEM-1 ✅ MEM-2 ✅ MEM-3 ✅ MEM-4 ✅ MEM-5 ✅ | 94/94 | Frontier complete |
| 2: Spec System | spec-system/ | SPEC-1–6 ✅ | 90/90 | Frontier complete |
| 3: Context Monitor | context-monitor/ | CTX-1 ✅ CTX-2 ✅ CTX-3 ✅ CTX-4 ✅ CTX-5 ✅ + 1M adaptive | 125/125 | Frontier complete |
| 4: Agent Guard | agent-guard/ | AG-1 ✅ AG-2 ✅ AG-3 ✅ | 103/103 | Frontier nearly complete |
| 5: Usage Dashboard | usage-dashboard/ | USAGE-1 ✅ USAGE-2 ✅ USAGE-3 ✅ /arewedone ✅ | 197/197 | Streamlit UI (optional) |

---

## Total Test Count

| Module | Tests | Status |
|--------|-------|--------|
| memory-system (capture) | 37 | 37/37 passing |
| memory-system (mcp_server) | 29 | 29/29 passing |
| memory-system (cli) | 28 | 28/28 passing |
| spec-system (spec) | 26 | 26/26 passing |
| spec-system (skill_activator) | 64 | 64/64 passing |
| research (reddit_scout) | 29 | 29/29 passing |
| agent-guard (mobile_approver) | 36 | 36/36 passing |
| agent-guard (ownership) | 27 | 27/27 passing |
| agent-guard (credential_guard) | 40 | 40/40 passing |
| context-monitor (meter) | 52 | 52/52 passing |
| context-monitor (alert) | 24 | 24/24 passing |
| context-monitor (auto_handoff) | 27 | 27/27 passing |
| context-monitor (compact_anchor) | 22 | 22/22 passing |
| reddit-intelligence (reader) | 43 | 43/43 passing |
| reddit-intelligence (nuclear_fetcher) | 44 | 44/44 passing |
| self-learning | 75 | 75/75 passing |
| usage-dashboard (usage_counter) | 44 | 44/44 passing |
| usage-dashboard (otel_receiver) | 63 | 63/63 passing |
| usage-dashboard (cost_alert) | 39 | 39/39 passing |
| usage-dashboard (arewedone) | 51 | 51/51 passing |
| **Total** | **800** | **800/800 passing** |

---

## Key Architecture Decisions (cumulative)

| Decision | Rationale |
|----------|-----------|-
| Memory capture via Stop hook | Stop has `last_assistant_message` — better context than PostToolUse alone |
| Transcript JSONL for explicit memory | `transcript_path` in Stop payload; explicit user "remember/always/never" → HIGH confidence |
| 8-char UUID suffix for memory IDs | 3-char caused collisions at 100 rapid-fire creates. 8-char is collision-resistant. |
| SPEC_GUARD_MODE env var | Default warn-only — never surprises user. Opt-in blocking. |
| `hookSpecificOutput.permissionDecision` | PreToolUse ONLY event using hookSpecificOutput. Top-level `block` silently fails. |
| Stop hook block format | `{"decision": "block", "reason": "..."}` — NOT hookSpecificOutput (different from PreToolUse) |
| Spec system is slash commands | Zero-infrastructure, user-invoked. Only the guard is a hook. |
| Local-first storage (`~/.claude-memory/`) | User owns data. No external dependency. Privacy by default. |
| Transcript format | `entry["message"]["usage"]` for assistant entries. `input + cache_read + cache_create = total`. |
| `--project` per subparser | argparse subparsers don't inherit parent parser options — must add to each subcommand |

---

## Open Items

### USAGE-5: Streamlit Dashboard (optional)
- Visual UI for token/cost data (OTel receiver + transcript data)
- Only worth building if CLI + OTel receiver prove useful in daily use

### ~~Wire USAGE-3 cost_alert.py into settings.local.json~~ DONE (Session 18)
- Wired as PreToolUse hook in settings.local.json (empty matcher, all tools)
- Hook handles cheap/expensive filtering internally
- Live tested: cheap tools silently pass, expensive tools pass when no cost data

### Kalshi Dual-Chat Automation
- Automate /polybot-init, /polybot-auto, /polybot-autoresearch startup via RunMaestro/tmux
- See memory: project_kalshi_automation.md for full requirements

### REVIEW: Linked repos from Beast post comments
- `github/spec-kit` — GitHub's own spec-driven dev framework
- `facetlayer/candle` — MCP-based process manager
- `dimitritholen/raggy` — lightweight per-project RAG for dev docs

### INVESTIGATE: compact_anchor.py system-reminder context burn
- CTX-5 writes .claude-compact-anchor.md every 10 turns — may trigger system-reminder token drain
- See LEARNINGS.md entry for details
- Test: check if anchor writes produce system-reminder diffs in transcript JSONL

### INSTALL: ClaudePrism — scientific writing workspace
- Repo: github.com/delibae/claude-prism
- For: academic papers, research writing (psychiatry)
- Local-first, wraps CC as subprocess, LaTeX + PDF preview

### REFERENCE-PERSONAL: Trading/Kalshi resources
- r/algotrading strategy list (534pts) — 40+ basic algo strategies
- VEI volatility expansion signal with Python source (436pts) — fast/slow ATR ratio
- Both bookmarked in FINDINGS_LOG.md

### INVESTIGATE: Cozempic context pruner
- Repo: github.com/Ruya-AI/cozempic (pip install cozempic)
- Prunes duplicate system-reminders and oversized tool outputs that eat context
- Auto-checkpoints team state before compaction
- Directly relevant to CTX-5 compact_anchor investigation
- Found in Agent Teams post comments (r/ClaudeCode/comments/1qz8tyy)

---

## MASTER PLAN: Unified Workspace + Self-Learning Architecture

**Status:** IN PROGRESS — tmux setup complete, self-learning design ready for Polybot adoption

### Part 1: Master Window (COMPLETE)

**Goal:** All Claude Code sessions in one window. Open Terminal, type `dev-start`, everything launches.

**What was built:**
- tmux 3-session workspace via `~/.local/bin/dev-start`
- Window 0: `cca` — ClaudeCodeAdvancements (normal permissions)
- Window 1: `kalshi-1` — Polymarket/Kalshi main chat (--dangerously-skip-permissions)
- Window 2: `kalshi-2` — Polymarket/Kalshi research chat (--dangerously-skip-permissions)
- All sessions auto-launch Claude Code in correct project directories
- Idempotent: re-running `dev-start` attaches to existing session (no duplicates)
- CShip statusline renders correctly in tmux
- Sessions survive Terminal closure (tmux background)

**Keyboard shortcuts:**
- `Ctrl+b, 0/1/2` — jump to CCA / Kalshi Main / Kalshi Research
- `Ctrl+b, w` — visual window picker
- `Ctrl+b, d` — detach (sessions keep running)
- `Ctrl+b, c` — add a new window
- `Ctrl+b, &` — kill current window

**Tools evaluated (15 total):**
- Claude Squad v1.0.17 — INSTALLED (Go TUI, brew install, backup option)
- Maestro v0.2.4 — BUILT but crashes on macOS 15.6 beta (SDK symbol _NSUserActivityTypeBrowsingWeb missing from CoreServices). Retry when off beta or Maestro updates Tauri config.
- Recon — previously installed (tmux popup dashboard)
- Agent Deck, Codeman, NTM, claude-tmux, Claude Dashboard, IttyBitty, CCManager, Amux, claude-code-monitor, claude-code-dashboard, TmuxCC, tmux-claude-code — all evaluated, details in FINDINGS_LOG.md

**Adding/removing sessions:**
- Add: `Ctrl+b, c` then `cd /path/to/project && claude`
- Remove: `Ctrl+b, &` to kill current window
- Or edit `~/.local/bin/dev-start` to change the default template

### Part 2: Self-Learning Polybot Architecture (DESIGNED — needs Polybot adoption)

**Goal:** Kalshi main chat (monitors/bets) and research chat (coding/bugs) learn from outcomes and improve strategy autonomously.

**Architecture (adapted from YoYo self-evolving agent pattern):**

```
┌─────────────────────┐     writes outcomes     ┌──────────────────────┐
│   Kalshi Main Chat   │ ──────────────────────> │                      │
│   (live monitoring)  │                         │   Shared Journal     │
│   /polybot-auto      │ <────────────────────── │   (structured JSON)  │
│                      │     reads strategy      │                      │
└─────────────────────┘                         │   Location: TBD      │
                                                 │   ~/polybot-journal/ │
┌─────────────────────┐     reads outcomes       │   or project-local   │
│  Kalshi Research     │ ──────────────────────> │                      │
│  (coding/infra/bugs) │                         └──────────────────────┘
│  /polybot-autoresearch│
│                      │ ──> updates strategy config based on patterns
└─────────────────────┘
```

**Journal schema (proposed):**
```json
{
  "timestamp": "2026-03-15T21:00:00Z",
  "event_type": "bet_outcome | strategy_update | pattern_detected | error",
  "market_type": "crypto_15m | weather | sports | custom",
  "ticker": "KXBTC15M",
  "side": "yes | no",
  "price_cents": 95,
  "result": "win | loss | void",
  "pnl_cents": 500,
  "confidence": 0.85,
  "conditions": "low_liquidity, post_8pm, high_volatility",
  "strategy_version": "expiry_sniper_v1",
  "notes": "Lost on low-liquidity market — need min liquidity threshold"
}
```

**Self-learning loop (per session start):**
1. Research chat reads journal at `/polybot-auto` or `/polybot-init`
2. Aggregates: win rate by market type, time, conditions, strategy version
3. Detects patterns: "we lose on X conditions" or "strategy Y outperforms Z"
4. Updates strategy config (thresholds, filters, confidence adjustments)
5. Main chat reads updated config at next session start

**Key safeguards:**
- Minimum sample size (N=20) before any strategy change
- Strategy changes are logged with reason (no silent drift)
- Backtesting: replay past outcomes through new strategy before deploying
- Never expose API keys, account balances, or trade history in logs/commits

**What Polybot needs to implement:**
1. Journal writer in main chat (log every bet outcome)
2. Journal reader + pattern detector in research chat
3. Strategy config file that both chats read
4. Reflection step at session start (read journal, summarize learnings)

**Handoff to Polybot:** Tell either Kalshi chat:
> "Read SESSION_STATE.md in /Users/matthewshields/Projects/ClaudeCodeAdvancements — section 'MASTER PLAN Part 2: Self-Learning'. Adopt this architecture for the journal + strategy feedback loop."

### Part 3: Cross-Chat Coordination (FUTURE)

**Problem:** CCA and Polybot can't write to each other's folders (scope boundaries).
**Solution options:**
1. Shared file at `~/.claude-workspace-state.json` (neutral location)
2. Agent Teams sendMessage pattern (file-based inbox per agent)
3. Polybot reads CCA's SESSION_STATE.md (read-only cross-reference)

**Not urgent.** The tmux window switching (Ctrl+b, 0/1/2) makes manual coordination fast enough for now.

### Debugging Issues to Watch

| Issue | Risk | Mitigation |
|-------|------|------------|
| Maestro crash on macOS 15.6 beta | Known | Use tmux + dev-start instead. Retry Maestro after macOS stable or SDK update |
| CShip in tmux | Low (tested, works) | If ANSI breaks, set `TERM=xterm-256color` in tmux.conf |
| Hooks in tmux sessions | Low (tested, works) | Global hooks fire in all sessions. Project hooks fire per CWD |
| Duplicate sessions on re-run | None (fixed) | dev-start checks `tmux has-session` before creating |
| Old Terminal tab sessions | Clean up needed | Close old tabs after wrap commands finish |
| Context burn from 3 concurrent sessions | Medium | Only actively chat with 1-2 at a time. Idle sessions cost zero tokens |
| Credential exposure in logs/commits | CRITICAL | AG-3 credential guard active. Never log keys, balances, or trade data to git |
| Strategy drift in self-learning | Medium | Minimum sample size N=20 before changes. All changes logged with reason |

---

## Session 20 Start Protocol

1. Run /cca-init
2. COMMIT all Session 19 work immediately (nuclear flexibility, launcher, master tasks, analysis)
3. Run all 20 test suites — confirm 742+ passing
4. Begin MT-0 design: adapt journal.py event schema for trading domain (market_research, bet_outcome, edge_discovered)
5. Quick win: MT-2 mermaid diagrams in spec:design
6. Push to remote
