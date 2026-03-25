# Master-Level Tasks — CCA Aspirational Goals
# These are high-value, multi-session targets that define where CCA is heading.
# Not all will be completed in one session. Track progress here.

---

## MT-0: Kalshi Bot Self-Learning Integration (BIGGEST)

**Source:** CCA self-learning architecture (YoYo-inspired) + live Kalshi bot performance data
**What Matthew wants:** The Kalshi bot objectively perfects and enhances itself through deep self-learning integration — without becoming an amalgamated mess. Specifically:
- **Sniper bets work.** The bot has proven success with this approach. The self-learning system should understand WHY sniper bets work (the mathematical edge, the timing patterns, the market conditions) and encode those principles.
- **Research quality is the bottleneck.** The bot struggles to discover new markets, edges, or bet types that match or exceed sniper bet quality. It uses academic papers, probability theory, and statistics — but the research chat doesn't reliably surface actionable edges.
- **Self-learning must close the research gap.** The system should track which research paths led to profitable discoveries vs dead ends, build a model of "what a good edge looks like" from historical wins, and prune research directions that consistently underperform.

**Why this is MT-0:** This is the highest-stakes application of CCA's self-learning work. The architecture (journal.py, reflect.py, strategy.json) was designed for exactly this — but currently lives only in CCA's own operational metrics. Deploying it into the Kalshi bot is where the real value lands.

**Technical path:**
- Adapt journal.py event schema for trading domain: market_research, bet_placed, bet_outcome, edge_discovered, edge_rejected, strategy_shift
- Pain/win tracking per research session: what research paths led to actual profitable bets vs wasted cycles
- Pattern detection tuned for trading: "sniper-like" edge fingerprinting (what statistical signature do successful edges share?)
- Closed feedback loop: bet outcomes feed back into research prioritization automatically
- Academic paper effectiveness tracking: which papers/approaches produced real edges vs theoretical dead ends
- Minimum sample size guards (N=20) before any strategy auto-adjustment — same safety as CCA
- PROFIT IS THE ONLY OBJECTIVE — the system optimizes for net profit, never break-even or theoretical elegance
- Must remain clean and modular — one file = one job, no amalgamation

**What "next-level but efficient" means here:**
- Journal logging: ~0 token cost (append JSONL, no LLM calls)
- Pattern detection: rule-based statistical analysis, not LLM-powered reflection
- Strategy adjustments: bounded parameter tuning with safety rails, not code rewriting
- The expensive part (research chat) already exists — self-learning makes it SMARTER, not MORE EXPENSIVE

**Relationship to CCA:** The self-learning module in CCA is the R&D lab. The Kalshi deployment is the production application. Patterns proven in CCA get promoted to Kalshi. This is R&D-before-production applied to self-learning itself.

**Status:** COMPLETE (Phase 1: S21, Phase 2: deployed via polymarket-bot monitoring chat).
- Phase 1 (CCA): 6 event types, trading metrics, 4 pattern detectors, 24 tests
- Phase 2 (Polybot): Deployed via different implementation path (DB-direct vs JSONL journal):
  - `kalshi_self_learning.py` (916 LOC): Bucket stats, Wilson CI, CUSUM, learning proposals, persistent state
  - `trade_reflector.py` (791 LOC): Trade pattern analysis, 5 detectors
  - `calibration_bias.py` (426 LOC): Systematic mispricing detection
  - `dynamic_kelly.py` (341 LOC): Per-bucket optimal sizing
  - `strategy_health_scorer.py` (296 LOC): HEALTHY/MONITOR/PAUSE/KILL verdicts
  - `overnight_detector.py` (497 LOC): Time-stratified analysis
  - `trading_analysis_runner.py` (391 LOC): Unified runner
  - Total: 7 modules, 4225 LOC — closed feedback loop active (bet outcomes -> bucket analysis -> proposals)

---

## MT-5: Claude Pro ↔ Claude Code Bridge

**What:** Make it easier for Claude Pro (chat) to access and discuss Claude Code project files, architecture, and plans — enabling Matthew to scheme, design, and strategize in Claude Pro while Claude Code handles implementation.
**Why:** Currently Claude Pro can't see project files without manual copy-paste. Matthew wants to discuss high-level strategy in Pro and execute in Code.

**Technical path (speculative — needs research):**
- MCP server that exposes project files to Claude Pro via tool use
- Or: automated project summary export that Claude Pro can reference
- Or: Claude Projects feature with synced file uploads
- Research what's currently possible with Claude Pro's capabilities

**Status:** Future task. Needs research on Claude Pro's current integration options.

---

## MT-1: Maestro-Style Visual Grid UI

**Source:** https://www.reddit.com/r/ClaudeCode/comments/1qq2lur/
**What Matthew wants:** The exact visual setup from Maestro — grid of sessions, real-time status indicators, git worktree isolation, visual git graph, quick action buttons, template presets.
**NOT a loose interpretation.** The grid UI with multiple sessions side by side, status per session, at-a-glance what each agent is doing.

**Technical path:**
- Maestro is Tauri + React + Rust (native macOS)
- Previously built v0.2.4 from source but crashed on macOS 15.6 beta SDK
- Options: (A) Retry Maestro install when stable release drops, (B) Build our own using Electron/Tauri/SwiftUI, (C) Streamlit web-based approximation
- MCP server approach for real-time session status (Maestro's pattern)

**Status:** MOSTLY SELF-RESOLVED (S96). Multiple tools now exist:
- **Claude Control** (github.com/sverrirsig/claude-control) — ADAPT finding S96. Electron + Next.js. Auto-discovers Claude processes, shows full lifecycle (working->approval->PR/CI). Hook-based status detection + CPU/JSONL heuristics. Permission approval from dashboard. macOS only, free/open source.
- **PATAPIM** (patapim.ai) — Terminal IDE with 9-session grid, pattern-matching status detection. Electron + xterm.js + node-pty.
- **Nimbalyst** — Third-party Claude session manager.
- **Our own infra**: cca_comm.py coordination, crash_recovery.py, chat_detector.py, session_pacer.py already provide the backend. What's missing is the VISUAL layer only.

**Recommended next step:** Try Claude Control first (install + test). If it works, it solves MT-1 immediately. If not, our backend + their visual approach = build our own.
Last updated: S96 (2026-03-21).

---

## MT-2: Mermaid Architecture Diagrams in Spec System

**Source:** https://www.reddit.com/r/ClaudeCode/comments/1rek0y9/
**What:** Automatically generate mermaid architecture diagrams as part of the `/spec:design` phase. Every design doc gets a visual architecture diagram before implementation begins.
**Why:** Mermaid renders natively in GitHub, VS Code, and Obsidian — zero dependencies. Visual spec artifact is reviewable.

**Technical path:**
- Enhance `spec-system/commands/design.md` to include a mermaid diagram step
- Claude generates the diagram as part of design.md output
- Already noted in spec-system rules (`spec-system.md`)

**Status:** COMPLETE (Session 19). Mermaid diagram requirement added to spec:design at lines 34 and 109.

---

## MT-3: Virtual Design Team Plugin

**Source:** https://www.reddit.com/r/ClaudeCode/comments/1rppl4w/
**What:** Multi-persona design review — UX researcher, visual designer, accessibility expert, frontend architect all review the same design and provide feedback from their perspective.
**Why:** Single-perspective design reviews miss blind spots. Multi-persona catches more issues.

**Technical path:**
- Slash command that prompts Claude to adopt 3-4 expert personas sequentially
- Each persona reviews the current design.md and provides feedback
- Consolidated feedback drives revisions before implementation
- Could be a `/spec:design-review` command

**Status:** COMPLETE (Session 21). `/spec:design-review` command created with 4 expert personas (UX, Security, Performance, Maintainability). Consolidated review with APPROVE/REVISE/REDESIGN verdict.

---

## MT-4: Frontend Design Excellence via Design Vocabulary

**Source:** https://www.reddit.com/r/ClaudeCode/comments/1p8qz7v/ (comments)
**What:** Incorporate the community-validated patterns for achieving professional-quality UI design:
1. Design vocabulary from Midjourney/PromptHero (cinematic, golden ratio, moody palette)
2. Multi-model pipeline (Gemini creates design guide from screenshots, feed to Claude)
3. Screenshot-reference approach (give Claude 2-3 reference UIs)
4. 5-template-then-pick workflow + 100-line theme guide

**Technical path:**
- Add optional "design reference" step to `/spec:design`
- Create a `design-guide.md` template that captures aesthetic preferences
- When building any UI (USAGE-5 Streamlit, or future launcher), apply these patterns

**Status:** COMPLETE (Session 21). Section 1b "Design References" added to spec:design — optional for UI features, includes reference UIs, design vocabulary, layout pattern, color constraints. Asks user once if no preferences specified.

---

## MT-6: On-Demand Subreddit Scanner ("Nuclear at Will")

**Source:** Matthew's request (Session 24) + nuclear scan infrastructure already built
**What:** Expand /cca-nuclear to be a frictionless on-demand scanner for ANY subreddit. Matthew wants to scan:
- Claude Code ecosystem: r/ClaudeCode, r/ClaudeAI, r/vibecoding, r/LocalLLaMA, r/MachineLearning
- Trading/prediction markets: r/algotrading, r/Kalshi, r/predictit, r/polymarket, r/sportsbook
- Any subreddit on a whim — one command, full deep-dive

**Why this matters:** The nuclear scan proved its value (411 posts, 7 BUILD, 24 ADAPT across 4 subs). But currently each scan is a heavyweight operation requiring a dedicated session. Matthew wants lightweight "scan this sub right now" capability with the same rigor.

**Technical path:**
- /cca-nuclear already accepts arbitrary subreddit argument (Session 19)
- Upgrade needed: (A) Predefined subreddit profiles with optimized settings (min-score, sort, time range per sub), (B) Quick-scan mode (~25 posts, title-first triage, deep-read top 5-10 only), (C) Persistent sub registry with last-scan timestamps to avoid re-scanning, (D) Cross-sub dedup against FINDINGS_LOG, (E) One-line summary output for quick scans vs full NUCLEAR_REPORT for deep scans
- Subreddit profiles: r/ClaudeCode (min-score 30, Top/Month), r/algotrading (min-score 50, filter prediction-markets), etc.
- Quick-scan should complete in 5-10 minutes, not 45-60

**Lifecycle (non-negotiable):**
1. Research: Scan how power users do multi-sub monitoring (Reddit posts, tools like reddit-scout patterns)
2. Plan: Design profile schema, quick-scan algorithm, dedup strategy
3. Build: Implement profile system + quick-scan mode
4. Test: Unit tests for profiles, quick-scan triage, dedup. Integration test: run quick-scan on r/ClaudeCode, verify output quality matches full nuclear scan
5. Validate: Compare quick-scan findings vs full nuclear scan on same sub — must catch same BUILD/ADAPT candidates
6. Backtest: Re-run against already-scanned subs (r/ClaudeCode 138 posts) — quick-scan should surface the same top-5 BUILD candidates

**Status:** COMPLETE (Session 27). Delivered:
- `profiles.py`: 10 builtin subreddit profiles (4 domains: claude/trading/dev/research), scan registry with yield tracking, quick-scan triage mode
- `--profile` and `--quick` flags added to nuclear_fetcher.py
- 43 tests (all passing)
- CLI: `python3 profiles.py list|info|stale|history`
- Backtested against 138-post r/ClaudeCode nuclear queue — validates quick-scan catches top signals while full nuclear finds deeper BUILD candidates
- Scan registry tracks last-scan timestamps, posts scanned, builds, adapts, and yield score per sub

---

## MT-7: Programmatic Trace Analysis for Self-Learning (ACE Pattern)

**Source:** https://www.reddit.com/r/ClaudeCode/comments/1rvhqgc/ (ACE framework, 2000+ stars)
**What:** Adapt ACE's RLM Reflector pattern into CCA's self-learning system. Instead of only learning from structured journal events (bet_placed, strategy_shift, etc.), also learn from raw execution traces by programmatically querying transcript JSONL across sessions.

**Why this is potentially huge:**
- Current self-learning (reflect.py) only sees what we explicitly log. ACE showed 30% of "successful" runs have hidden retry loops and context waste that structured logging misses entirely.
- 34.3% improvement on tau2-bench from one cycle of trace analysis.
- CCA already reads transcript JSONL (meter.py). The infrastructure exists.
- This closes the gap between "what we chose to log" and "what actually happened."

**Technical path:**
- DON'T install ACE framework (external dependency). ADAPT the pattern.
- New module: `self-learning/trace_analyzer.py`
- Read N most recent transcript JSONL files for current project
- Detect patterns programmatically: retry loops (same tool called 3+ times on same file), context waste (large Read calls on files not subsequently used), tool call efficiency (Edit attempts that fail and retry), session velocity (tasks completed per 100k tokens)
- Feed detected patterns into reflect.py as auto-generated journal events
- Skillbook equivalent: append proven patterns to LEARNINGS.md or strategy.json automatically
- Minimum sample: analyze 10+ sessions before any strategy recommendation

**Applies to both CCA and Kalshi bot:** CCA traces show development efficiency patterns. Kalshi traces show research quality and bet execution patterns.

**Lifecycle (non-negotiable):**
1. Research: ACE framework reviewed (DONE). Analyze 5+ CCA transcript JSONL files manually — what patterns exist? What does a retry loop look like in raw data? What does context waste look like?
2. Plan: Design trace_analyzer.py schema — input format, pattern definitions, output format, integration with reflect.py
3. Build: Implement trace_analyzer.py with TDD (tests first for each pattern detector)
4. Test: Unit tests for each pattern detector (retry loops, context waste, tool efficiency). Must have 30+ tests.
5. Validate: Run analyzer against real CCA transcripts. Do the detected patterns match known session quality? (e.g., Session 24 was efficient — does analyzer confirm? Sessions with known issues — does analyzer detect them?)
6. Backtest: Analyze all available CCA transcripts (Sessions 1-24). Produce a "CCA development efficiency report" that shows patterns over time. If the report reveals nothing useful, the feature isn't ready.
7. Iterate: Tune pattern thresholds based on backtest results before deploying to Kalshi traces

**Status:** COMPLETE (Session 26). Delivered:
- `self-learning/trace_analyzer.py`: TranscriptEntry, TranscriptSession, RetryDetector, WasteDetector, EfficiencyCalculator, VelocityCalculator, TraceAnalyzer
- 50 tests — all passing
- Validated on 3+ real CCA transcripts (scores 40-70, retry/waste/efficiency detection working)
- CLI: `python3 self-learning/trace_analyzer.py <session.jsonl>`

---

## MT-8: iPhone Remote Control Perfection

**Source:** Matthew's request (Session 24)
**What:** Perfect Anthropic's remote control feature so Matthew can flawlessly use his iPhone (Claude iOS app) to talk into Claude Code sessions, coordinate chats, and manage CLI terminals as if sitting at his MacBook.

**Why:** Matthew runs 2-3 concurrent Claude Code sessions (CCA + Kalshi main + Kalshi research). Being able to monitor, instruct, and coordinate from his phone while away from his desk is a massive productivity multiplier. Current remote control exists but has friction points.

**Technical path — needs research phase:**
- Scan r/ClaudeCode + r/ClaudeAI for remote control posts, tips, known issues, workarounds
- Document current remote control capabilities + limitations
- Identify all friction points (latency, session switching, terminal output visibility, voice-to-text accuracy)
- Build/configure optimizations: (A) tmux session naming + mobile-friendly status output, (B) Slash commands optimized for voice input (short names, no special chars), (C) Status summary command that gives phone-friendly output, (D) Quick-switch between CCA and Kalshi sessions from phone
- Test with actual iPhone → Claude iOS → remote Claude Code workflow
- Produce a REMOTE_CONTROL_GUIDE.md with setup + workflow

**Lifecycle (non-negotiable):**
1. Research: Nuclear quick-scan r/ClaudeCode + r/ClaudeAI for "remote control", "iPhone", "mobile", "iOS app" posts. Document all known capabilities, limitations, and community workarounds.
2. Plan: Map current workflow (tmux sessions, dev-start script, slash commands) against iPhone constraints. Identify every friction point.
3. Build: Implement optimizations (mobile-friendly status commands, voice-optimized slash names, quick-switch)
4. Test: Actually use iPhone -> Claude iOS -> remote control for a real work session. Document what works and what breaks.
5. Validate: Complete a full CCA task (review + log + commit) entirely from iPhone. Time it. Compare to MacBook workflow.
6. Debug: Fix every friction point found during validation testing
7. Iterate: Repeat test-validate-debug until workflow is genuinely "flawless" — Matthew's word, Matthew's standard

**Status:** Not started. Needs r/ClaudeCode + r/ClaudeAI research sweep for remote control posts.

---

## MT-9: Autonomous Cross-Subreddit Intelligence Gathering

**Source:** Matthew's directive (Session 25) — "is there any objective utility in allowing you to use /cca-nuclear in autonomous fashion for other subreddits at your whim? or even github repos?"
**What Matthew wants:** Claude autonomously scans subreddits and GitHub repos — at its own discretion — to discover objectively useful improvements. Not random browsing. Targeted, intelligent, self-directed research that surfaces viable tools, patterns, and approaches, then autonomously recreates the useful ones by building, testing, validating, backtesting, logging, and debugging.

**Why this matters:** Currently all intelligence gathering is Matthew-directed ("scan this sub", "review this URL"). Matthew wants Claude to independently identify high-signal sources, scan them, and act on findings — but with ironclad safety guardrails. This transforms CCA from a tool Matthew operates into a system that grows itself.

**The Frankenstein guardrail (Matthew's exact words):** "I don't want an amalgamated monster like Frankenstein." Every autonomous discovery must be:
- Objectively useful (traces to a validated pain point or measurable improvement)
- Clean and modular (one file = one job, no amalgamation)
- Tested before integration (TDD, validation, backtesting)
- Logged transparently (what was found, why it was built, what it replaced)

**Safety protections (NON-NEGOTIABLE):**
1. **No executable downloads** — never run downloaded scripts, binaries, or installers. Read source code only.
2. **No credential exposure** — never enter API keys, passwords, or tokens into any external service
3. **No system modifications** — never modify system files, install global packages, or change macOS settings
4. **No financial actions** — never interact with payment systems, wallets, or financial APIs
5. **No outbound data** — never send Matthew's code, data, or personal info to external services
6. **Sandboxed evaluation** — all discovered code is read-only analysis first, then rebuilt from scratch using CCA patterns if warranted
7. **Scam detection** — skip any repo/post that: has <10 stars, was created <7 days ago, promises unrealistic returns, requires payment, asks for API keys, or has no tests
8. **Rate limiting** — max 50 posts per scan, max 10 repos per session, minimum 30-second delay between fetches
9. **Audit trail** — every autonomous discovery logged to FINDINGS_LOG.md with full provenance (source URL, star count, reason for BUILD/SKIP, what was built)

**Domains Matthew explicitly approved for autonomous scanning:**
- Claude Code ecosystem: r/ClaudeCode, r/ClaudeAI, r/vibecoding, r/LocalLLaMA, r/MachineLearning
- Trading/prediction markets: r/algotrading, r/Kalshi, r/predictit, r/polymarket
- Investing/stocks (Session 28): r/investing, r/stocks, r/SecurityAnalysis, r/ValueInvesting, r/Bogleheads
- UI/frontend development: r/webdev, r/reactjs, r/frontend, r/UI_Design
- Academic research: r/MachineLearning, r/statistics, r/datascience (for reputable papers only)
- iOS development: r/iOSProgramming, r/SwiftUI, r/apple (for MT-13)
- GitHub: trending repos in Python, TypeScript, Rust related to AI agents, trading bots, developer tools

**Technical path:**
- Extend /cca-nuclear with `--autonomous` flag that enables self-directed scanning
- Build a subreddit priority queue based on last-scan timestamps and historical yield (BUILD/ADAPT ratio)
- GitHub scanner: use GitHub trending API + search for repos matching CCA frontier keywords
- Decision engine: for each discovery, score against (1) frontier relevance, (2) implementation feasibility, (3) test coverage of source, (4) Matthew's stated interests
- Auto-build pipeline: if score > threshold, clone pattern (NOT code) → write tests → implement → validate → commit with full provenance
- Kill switch: `~/.cca-autonomous-pause` file instantly pauses all autonomous activity

**What "autonomously recreate" means (critical distinction):**
- DO NOT fork or copy external code
- DO analyze what the tool does, why it works, and what pattern it uses
- DO rebuild the useful pattern from scratch using CCA architecture (one file = one job, tests first, stdlib-first)
- DO log the provenance: "Inspired by [repo] which does X. Rebuilt as Y because Z."

**Lifecycle (non-negotiable):**
1. Research: Scan 3+ subreddits autonomously, produce findings report, compare quality to Matthew-directed scans
2. Plan: Design autonomous decision engine — scoring rubric, safety checks, build/skip threshold
3. Build: Implement autonomous scanner with all 9 safety protections
4. Test: Unit tests for safety guardrails (must block malicious repos, scams, credential theft). 40+ tests.
5. Validate: Run autonomous scan on r/ClaudeCode (already manually scanned) — does it find the same top BUILD candidates?
6. Backtest: Compare autonomous findings vs Matthew-directed Session 14-15 nuclear scan. Must match or exceed signal quality.
7. Supervised trial: Run with Matthew monitoring for 3 sessions before full autonomy

**Status:** Phase 2 COMPLETE (Session 31). Delivered:

Phase 1 (Session 30):
- `autonomous_scanner.py`: ScanPrioritizer (staleness + yield + diversity scoring), SafetyGate (kill switch + rate limiting + content scanner), AutonomousScanner orchestrator, ScanReport.
- All 9 safety protections enforced. Kill switch at `~/.cca-autonomous-pause`.
- CLI: `rank` (prioritized queue), `status` (safety gate), `pick` (next target with --domain filter).

Phase 2 (Session 31):
- `execute_scan()`: End-to-end pipeline — fetch → filter → dedup → classify → record → report.
- `ScanResult` dataclass with to_dict/save_json for structured output.
- Auto-resolves fetch params from subreddit profiles.
- Updates scan_registry after each scan for rotation.
- CLI `scan` command: auto-pick or --target, --json output, --domain, --limit/--timeframe.
- `/cca-nuclear autonomous` mode: auto-picks highest-priority sub via scanner.
- 54 tests — all passing.
- Phase 3: Supervised trial — run with Matthew monitoring for 3 sessions.

---

## MT-10: YoYo-Pattern Continuous Self-Learning and Self-Building

**Source:** Matthew's directive (Session 25) — "I want to see you take the yoyo concept and my prompts to continue self-learning and building essentially"
**What Matthew wants:** The complete YoYo closed-loop pattern applied across CCA and the Kalshi bot: Claude learns from its own execution traces, identifies what works and what doesn't, and autonomously improves itself — building new capabilities, refining existing ones, and pruning what doesn't work. Not a one-time analysis but a continuous, session-over-session growth loop.

**The dual mandate:**
1. **Kalshi bot: profit and self-sustaining cash flow.** The self-learning system must optimize for net profit. Every learning cycle should make the bot smarter about which bets to take, which markets to enter, which research paths to pursue. The goal is self-sustaining cash flow that pays for Claude Max and beyond.
2. **CCA: evolve to be useful in any way applicable.** The system should identify where CCA's tools can be improved, extended, or applied to new domains — not just the original 5 frontiers.

**What "self-learning and self-building" means concretely:**
- **Self-learning (already started):** journal.py + reflect.py + strategy.json track events, detect patterns, recommend adjustments. MT-7 adds trace analysis. This is the observation layer.
- **Self-building (new):** When the self-learning system identifies a recurring pattern (e.g., "WebFetch fails 54% of the time" or "Edit retries waste 200+ tokens per session"), it doesn't just log it — it autonomously builds a fix, tests it, validates it, and commits it.
- **The loop:** Observe (traces) → Detect (patterns) → Hypothesize (what fix would help) → Build (implement fix with TDD) → Validate (does the fix actually reduce the pattern?) → Commit (with full provenance) → Observe again

**Anti-Frankenstein principle:** Each self-built improvement must be:
- A single, focused module (not a patch on an existing file)
- Tested independently (30+ tests or proportional)
- Validated against real data (not hypothetical improvement)
- Reversible (can be disabled without breaking anything)
- Logged (what pattern triggered it, what was built, what the measured improvement is)

**Technical path:**
- Extend reflect.py with `auto_improve()` method that generates improvement proposals
- Each proposal: { pattern_detected, proposed_fix, expected_improvement, test_plan, risk_level }
- Risk levels: LOW (new utility script), MEDIUM (new hook), HIGH (modifying existing hook) — only LOW auto-executes, MEDIUM/HIGH logged for Matthew review
- Build pipeline: for LOW-risk proposals, auto-execute: write tests → implement → validate → commit
- Improvement journal: `self-learning/improvements.jsonl` — every auto-build logged with before/after metrics
- Guard: max 2 auto-builds per session, each must pass all existing tests before commit

**Applies to:**
- CCA development efficiency (reduce retry loops, optimize tool usage)
- Kalshi bot research quality (prune dead-end research, amplify winning patterns)
- Kalshi bot execution quality (reduce slippage, improve fill rates)
- Any future domain Matthew applies the system to

**Lifecycle (non-negotiable):**
1. Research: Document the complete YoYo loop as applied to CCA + Kalshi. Define "improvement" precisely.
2. Plan: Design auto_improve() API — proposal schema, risk classification, build pipeline, validation criteria
3. Build: Implement with TDD. Start with LOW-risk only (new utility scripts).
4. Test: 40+ tests. Must include: safety rails (never auto-modifies production hooks), proposal quality (rejects trivial/impossible improvements), build pipeline (tests pass before commit).
5. Validate: Run for 5 sessions on CCA. Measure: does session efficiency actually improve? Are the auto-built improvements useful?
6. Backtest: Analyze hypothetical improvements against historical transcripts. Would they have helped?
7. Graduate: Once validated on CCA, adapt for Kalshi bot (separate deployment, same architecture)

**Status:** Phase 1 COMPLETE (Session 28), QualityGate added (Session 29), E2E validated (Session 29).
- `improver.py`: ImprovementProposal lifecycle, ImprovementStore (JSONL), ProposalGenerator, risk classification, dedup, safety guards
- `QualityGate`: Geometric mean anti-gaming (Nash 1950 / sentrux pattern). Prevents Goodhart's Law gaming — any zero metric tanks composite score. Configurable threshold, minimum 2 metrics, identifies weakest metric.
- Wired into reflect.py: trace analysis auto-generates proposals, --propose flag for reflect patterns
- 64 tests — all passing
- E2E validation: Pipeline tested on 3 real CCA transcripts (scores 40-70), 6 proposals generated, QualityGate correctly passes balanced improvements and rejects gamed ones
- Phase 2 COMPLETE (Sessions 42-44): 5/5 validation sessions, 36 transcripts analyzed. Avg score 70.8/100, median 75, improving trend (65->85->71->80->75). Distribution: 41% excellent, 33% good, 19% poor, 5% critical. 14 proposals generated (7 approved), dedup preventing explosion. QualityGate + Sentinel working correctly.
- Phase 3: Two tracks: (A) Graduate self-learning to Kalshi bot (requires cross-project work). (B) **Findings re-surfacing** — automatically connect old FINDINGS_LOG entries to current work context (e.g., "in session 15 we reviewed X as REFERENCE for Y, now we're building Y"). Matthew directive (Session 44).

---

## MT-11: Autonomous GitHub Repository Intelligence

**Source:** Matthew's directive (Session 25) — "or even github repos?"
**What Matthew wants:** Claude autonomously discovers, evaluates, and learns from GitHub repositories — not by installing them, but by reading their source code, understanding their patterns, and rebuilding useful approaches using CCA architecture.

**Domains of interest (Matthew-specified):**
- AI agent frameworks and tools (for CCA improvements)
- Trading bots and market analysis tools (for Kalshi bot improvements)
- UI/frontend frameworks and design systems (for MT-1, MT-4, any future UI work)
- Academic research implementations (papers with code, for learning from reputable sources)
- iOS/SwiftUI projects (for MT-13)

**Safety protections (inherit all 9 from MT-9, plus):**
10. **No `git clone` into CCA directory** — analysis happens via GitHub API / web scraping only
11. **No dependency installation** — never run `pip install`, `npm install`, or any package manager for discovered repos
12. **License check** — skip repos with no license or restrictive licenses (GPL if we'd need to relicense)
13. **Recency check** — prioritize repos with commits in last 90 days (active maintenance)

**Technical path:**
- GitHub trending scraper: daily check of trending Python/TypeScript/Rust repos
- Keyword-targeted search: repos matching CCA frontier terms, trading bot terms, UI framework terms
- Evaluation rubric: stars (>50), tests (must have test directory), docs (must have README), activity (commits in 90 days)
- Pattern extraction: read source, identify architecture patterns, document in structured format
- Rebuild decision: if pattern is applicable to CCA/Kalshi, rebuild from scratch with CCA conventions

**Lifecycle (non-negotiable):**
1. Research: Manually evaluate 10 GitHub repos from different domains. Define what "useful pattern" means.
2. Plan: Design evaluation rubric, extraction pipeline, rebuild decision criteria
3. Build: GitHub scanner + evaluator + pattern extractor
4. Test: 30+ tests. Must block: malicious repos, no-license repos, abandoned repos, scam repos.
5. Validate: Run on 20 repos. Compare Claude's evaluation vs Matthew's manual assessment.
6. Iterate: Tune rubric based on validation results

**Status:** Phase 2 COMPLETE (Session 83). Delivered:

Phase 1 (Session 30):
- `github_scanner.py`: RepoMetadata (from GitHub API), RepoEvaluator (0-100 scoring on stars/activity/license/relevance/age), EvaluationResult (EVALUATE/SKIP/BLOCKED), GitHubScanner orchestrator with JSONL audit log.
- FRONTIER_KEYWORDS: 9 frontier domains with keyword lists for relevance scoring.
- Safety: scam detection, content_scanner integration, GPL flagging, no cloning.
- 30 tests — all passing.

Phase 2 (Session 83):
- `fetch_trending()`: GitHub search API with date filters to approximate trending repos.
- `_build_trending_query()`: configurable language, days, min_stars filters.
- `TrendingScanner` class: per-language scanning, trending history JSONL log, CCA_LANGUAGES list.
- CLI `trending` command: --language, --days, --all, --json flags.
- Live validation: Python + TypeScript scans returned 19 EVALUATE repos (AutoResearchClaw 7071 stars, CLI-Anything 19864 stars, OpenMAIC 10079 stars).
- 62 tests — all passing (+32 new).
- Phase 3: Wire trending scanner into MT-9 autonomous pipeline for scheduled runs.

---

## MT-12: Academic Research Paper Integration

**Source:** Matthew's directive (Session 25) — "I also appreciate advancements for... academic research papers for learning from reputable sources"
**What Matthew wants:** Systematic discovery and integration of academic research that is directly applicable to CCA and the Kalshi bot. Not theoretical papers — papers with code, data, and reproducible results that translate to real improvements.

**Matthew's background context:** Matthew is a psychiatry resident with academic writing experience. He values rigor, reproducibility, and evidence-based approaches. He's not interested in hype papers — he wants papers that produce measurable, deployable improvements.

**Domains of interest:**
- **Prediction markets and forecasting:** calibration, market microstructure, information aggregation, automated trading
- **AI agent architecture:** self-improvement, tool use optimization, context management, multi-agent coordination
- **Statistical methods:** Bayesian inference, time series, anomaly detection — applied to trading and agent behavior
- **Human-AI interaction:** prompt engineering science, UI/UX for AI tools, cognitive load management

**What "integration" means:**
- Read the paper (via arXiv, Semantic Scholar, or direct PDF)
- Extract the core methodology — not the narrative, the math/algorithm
- Evaluate applicability: does this solve a real problem in CCA or Kalshi?
- If applicable: implement the methodology with TDD, validate against real data, backtest
- Log the paper, methodology, and results in `self-learning/research/papers.jsonl`

**Safety and quality controls:**
- Only papers from: arXiv, NIPS/NeurIPS, ICML, ACL, AAAI, IEEE, or journals with impact factor >2
- Must have: reproducible methodology, at least 10 citations (or <6 months old from top venue)
- Never cite or use: preprints from unknown authors, papers behind paywalls without institutional access, papers with retraction notices

**Technical path:**
- Semantic Scholar API for paper discovery (free, no API key for basic search)
- arXiv API for full paper access (free)
- Paper evaluation rubric: venue quality, citation count, code availability, methodology clarity
- Integration pipeline: read → extract → evaluate → implement → validate → log
- Cross-reference with Kalshi bot dead ends: if a paper's methodology was already tried and failed, skip

**Lifecycle (non-negotiable):**
1. Research: Manually read 5 papers from different domains. Define what "applicable" means for CCA and Kalshi.
2. Plan: Design paper discovery pipeline, evaluation rubric, integration workflow
3. Build: Paper scanner + evaluator + methodology extractor
4. Test: 25+ tests. Must filter out: low-quality venues, irreproducible methods, already-tried approaches.
5. Validate: Implement one methodology from a paper. Measure actual improvement on CCA or Kalshi.
6. Iterate: Refine discovery pipeline based on hit rate (useful papers / total papers scanned)

**Status:** Phase 4 COMPLETE (Session 101). Delivered:
- `self-learning/paper_scanner.py`: Semantic Scholar + arXiv API integration, 7 CCA-relevant domains (agents, prediction, statistics, interaction, code_review, trading_systems, context_management), paper evaluation scoring (citations/venue/relevance/recency/open-access), JSONL logging to `self-learning/research/papers.jsonl`
- `self-learning/paper_digest.py`: Kalshi/CCA digest generator with cross-chat bridge integration (35 tests)
- 54 + 35 = 89 tests — all passing
- Phase 1 (S38): Live API validated, first paper logged
- Phase 2: Ran across 4 domains, increased delay to 3s (429 rate limit)
- Phase 3 (S100): paper_digest.py built, expanded prediction/statistics queries (+8 queries, +12 keywords), bridge wiring
- Phase 4 (S101): Expanded scans across prediction, statistics, trading_systems, context_management. Papers: 25 -> 1242. Domain coverage balanced. 63 Kalshi-relevant papers (score>=55), top 10 sent to bridge.
- Phase 5 (S102): Implemented confidence calibrator from ConfTuner (Li et al., 2025). Verbal confidence extraction (%, fraction, decimal, labels, verbal), prediction logging with outcome tracking, ECE calibration metrics, per-source bias detection, confidence adjustment. 29 tests. `self-learning/confidence_calibrator.py`.
- Phase 6 (S102): Built hit_rate_tracker.py (32 tests). Computes APF from FINDINGS_LOG.md. Current APF=22.7% (target 40%). Frontier 2 (44.2%) and 4 (45.8%) exceed target. CLI: report/apf/by-frontier/trend/json. Wired confidence_calibrator into senior_chat LLMClient.ask_with_confidence().
- COMPLETE. All 6 phases done. Iterate: improve APF by targeting high-noise categories ("Other" at 9.7%).

---

## MT-13: iOS App Development Capability

**Source:** Matthew's directive (Session 25) — "ALSO add to the master-level tasks iOS app development"
**What Matthew wants:** Build the capability to develop iOS apps using Claude Code — SwiftUI-first, targeting Matthew's iPhone. This enables building custom mobile tools for:
- Kalshi bot monitoring and control (mobile dashboard)
- CCA session management from phone (extends MT-8 remote control)
- Personal productivity tools (baby tracker, schedule manager, medical reference)
- Any future mobile-first idea Matthew has

**Why this is a master task:** iOS development is a distinct skill domain. Claude Code can write Swift/SwiftUI, but the workflow (Xcode project setup, simulator testing, device deployment, App Store submission) requires specific infrastructure and validated patterns. Building this once makes every future iOS project faster.

**Technical path — needs research phase:**
- Scan r/iOSProgramming, r/SwiftUI, r/apple for "Claude Code" + iOS development posts
- Research: Can Claude Code create, build, and test Xcode projects from the CLI? (xcodebuild, swift package manager, xctest)
- Research: SwiftUI previews from CLI? Hot reload options?
- Research: TestFlight deployment from CLI?
- Build a starter template: SwiftUI app scaffold with CCA conventions (one file = one view, tests for each view model)
- First app target: Kalshi bot mobile dashboard (reads from polybot.db via local API, shows P&L, active strategies, recent bets)

**Prerequisites:**
- Xcode installed and configured (check `xcodebuild -version`)
- Apple Developer account (check if Matthew has one)
- iOS simulator setup

**Lifecycle (non-negotiable):**
1. Research: Scan Reddit + GitHub for Claude Code + iOS development patterns. Document what's possible from CLI.
2. Plan: Design iOS development workflow for Claude Code (project setup, build, test, deploy)
3. Build: Create starter template + build scripts. First target: "Hello World" that builds and runs in simulator.
4. Test: Build pipeline tests (does xcodebuild succeed? do xctest tests run?). 20+ tests for the workflow itself.
5. Validate: Build a real micro-app (Kalshi dashboard read-only view). Deploy to simulator. Screenshot.
6. Ship: Deploy to Matthew's iPhone via TestFlight or direct install.

**Scope Expansion (Session 44):** Matthew added macOS app development. Native macOS
apps benefit CCA directly (session monitors, design previews, launcher UIs) and
Matthew's other projects. Same SwiftUI toolchain, same Xcode requirement.

**Status:** Phase 2 COMPLETE (Session 49). Delivered:

Phase 1 (Session 44): Research complete — ecosystem survey, prerequisites identified.

Phase 2 (Session 49):
- `ios_project_gen.py`: Generates complete Xcode projects from CLI (SwiftUI + test target + CLAUDE.md + .gitignore)
- `xcode_build.py`: Python xcodebuild wrapper (build, clean, test, scheme/simulator listing, error parsing)
- Deterministic pbxproj generation (24-char hex UUIDs from seed)
- E2E validated: generated KalshiDashboard project builds + tests pass on iOS Simulator
- 57 tests (40 + 17) — all passing
- Xcode 26.3 installed (Build 17C529), iPhone 17 Pro + iPad Pro simulators available
- Phase 3: Build first real app (Kalshi mobile dashboard) or install SwiftUI Agent Skill

---

## MT-14: Autonomous Re-Scanning of Previously Scanned Subreddits

**Source:** Matthew's directive (Session 25) — "feel free to return back to previous subreddits with /cca nuclear command for different reviews and introspections"
**What Matthew wants:** Periodically re-scan previously scanned subreddits (r/ClaudeCode, r/ClaudeAI, r/Anthropic, r/algotrading, r/vibecoding) to catch new posts, evolving discussions, and emerging tools that appeared after the last scan. The community moves fast — a scan from 2 weeks ago is already stale.

**Why this is distinct from MT-6/MT-9:**
- MT-6 is about making scanning easier (profiles + quick-scan)
- MT-9 is about scanning NEW subreddits autonomously
- MT-14 is about REVISITING already-scanned subs with fresh eyes and new context

**The value of re-scanning:**
- New posts appear daily in active subs (r/ClaudeCode gets 20-50 posts/day)
- Previously REFERENCE-rated posts may become BUILD-worthy as CCA evolves
- Comment threads on old posts continue to grow — new insights appear weeks later
- Matthew's priorities shift — a post that was SKIP last month might be relevant now

**Technical path:**
- Extend nuclear scanner with `--rescan` mode: only fetch posts newer than last_scan_timestamp
- Delta scanning: compare new findings against FINDINGS_LOG.md, only surface genuinely new intelligence
- Re-evaluation: for previously scanned posts with significant new comments (20+), re-read and re-evaluate
- Staleness tracking: `self-learning/scan_registry.json` with per-sub last_scan timestamps and next_scan_due dates
- Auto-schedule: if a sub hasn't been scanned in 14 days, flag it for autonomous re-scan

**Lifecycle (non-negotiable):**
1. Research: Analyze how quickly r/ClaudeCode content changes (new posts per day, comment growth rate)
2. Plan: Design delta-scan algorithm, staleness thresholds, re-evaluation criteria
3. Build: Implement --rescan mode + scan registry + staleness tracker
4. Test: 25+ tests. Must handle: empty delta (no new posts), duplicate detection, re-evaluation logic.
5. Validate: Re-scan r/ClaudeCode (last scanned Session 14). Do new posts surface new BUILD candidates?
6. Automate: Wire into MT-9 autonomous pipeline so re-scans happen on a cadence

**Status:** Phase 1 COMPLETE (Session 35). Delivered:
- `rescan_sub()` method on AutonomousScanner: delta-scanning with timestamp filtering
- `get_stale_subs()` helper for identifying overdue subs
- CLI `rescan` (auto-pick or --target) and `stale` commands
- 8 new tests (73 total autonomous scanner)
- Phase 2: Run rescan on a real stale sub, validate delta filtering works. Phase 3 COMPLETE (Session 84): `execute_rescan_stale()` method, `rescan-all` CLI command with --max-age/--json, `--include-rescan` flag on daily command. 16 new tests (101 total autonomous_scanner).

---

## MT-17: UI/Design Excellence and Professional Report Generation

**Source:** Matthew's directive (Session 39) + https://www.reddit.com/r/ClaudeCode/comments/1rppl4w/ (Design Studio, 259pts)
**What Matthew wants:** Claude Code's visual/design output is notoriously weak — PDFs, reports, and UI generated by Claude look amateur. Matthew tried to generate a CCA status report PDF and it was "atrocious." The r/ClaudeCode community widely agrees UI/design is Claude's weakest capability. Matthew wants design excellence across ALL visual output formats:
1. Professional-quality PDF report generation (status reports, project overviews, dashboards)
2. Presentations/slides (conference talks, project updates, pitch decks)
3. Graphics and visual assets (charts, diagrams, infographics)
4. Website/HTML design (dashboards, landing pages, documentation sites)
5. Design skills/prompts that make Claude produce visually polished output across all formats
6. Structured design workflow for any UI-facing work in CCA or any project

**Why this matters:** Every CCA module eventually produces visual output (usage dashboard, status reports, scan results). Without design discipline, these outputs undermine the project's credibility.

**What the Design Studio taught us:**
- The core concept is sound: structured design prompts genuinely improve Claude's visual output
- But don't overengineer it — Design Studio was 8,000 lines of markdown for what could be a single CLAUDE.md section
- Accessibility hooks and structured workflow are the high-value parts
- The "team of specialists" metaphor is marketing — one LLM with good instructions produces the same result
- Figma integration requires external MCPs we don't need — focus on HTML/CSS/PDF

**Technical path:**
- `design-skills/` module with design reference prompts (color palettes, typography scales, layout patterns)
- `design-skills/design-guide.md` — CCA visual language for all output formats
- `design-skills/report_generator.py` — Python CLI that collects CCA data and calls Typst
- `design-skills/templates/` — Typst templates for different report types
- `/cca-report` command for one-command PDF generation
- Future: Typst slide templates, HTML report templates, SVG chart generation
- Add UI/visual-focused subreddits to autonomous scan targets: r/webdev, r/reactjs, r/frontend, r/UI_Design

**Output format roadmap:**
- Phase 1: PDF reports via Typst (DONE) - status reports, session summaries
- Phase 2: Presentations via Typst slides - project updates, conference talks
- Phase 3: HTML reports - interactive dashboards, web-viewable reports
- Phase 4: Graphics/charts - SVG/PNG via Python (matplotlib/plotly) with CCA design language
- Phase 5: Website templates - landing pages, documentation sites

**Lifecycle:**
1. Research: Evaluate PDF generation libraries (DONE — Typst selected)
2. Plan: Design guide template, report command spec (DONE)
3. Build: design-guide.md + /cca-report + report_generator.py + Typst templates (Phase 1 DONE)
4. Test: Generate sample reports, compare to professional standards
5. Validate: Matthew reviews output quality. Iterate until "not atrocious."
6. Expand: Presentations, HTML, graphics, websites

**Status:** Phase 1 COMPLETE (Session 41). Delivered:
- `design-skills/` module with CLAUDE.md, design-guide.md (color palette, typography, layout rules)
- `design-skills/report_generator.py` — CCADataCollector + ReportRenderer + CLI (21 tests)
- `design-skills/templates/cca-report.typ` — Professional status report template
- `/cca-report` slash command for one-command PDF generation
- Typst installed (`brew install typst`)
- First real CCA status report generated (87.8 KB PDF)
- Phase 2 COMPLETE (Session 47): `slide_generator.py` + `/cca-slides` command (25 tests)
- Phase 3 COMPLETE (Session 48): `dashboard_generator.py` + `/cca-dashboard` command — self-contained HTML dashboard with module grid, metric cards, master task table. 33 tests. XSS-safe, responsive.
- Phase 4 COMPLETE (Session 49): `chart_generator.py` — pure SVG chart generation (bar, horizontal bar, line, sparkline, donut) with CCA design language. 42 tests. Integrated inline into dashboard_generator.py.
- Phase 5: Website templates — landing pages, documentation sites

---

## MT-18: Academic Writing Workspace (ClaudePrism-Inspired)

**Source:** Matthew's directive (Session 39) + https://www.reddit.com/r/ClaudeCode/comments/1ru9lnr/ (ClaudePrism, 273pts, 98% upvoted)
**What Matthew wants:** A local academic writing setup that enables Matthew to produce professional scientific documents — papers, presentations, posters, case reports — for his psychiatry career. This is a LONG-TERM CAREER TOOL, not a CCA frontier.

**Matthew's context:** Psychiatry resident. Academic writing is part of the career path. Needs to produce:
- Case reports and clinical research papers (LaTeX or Typst)
- Conference presentations (slides)
- Literature reviews
- Grant applications
- Teaching materials

**What ClaudePrism does right (and what to adapt):**
- Runs Claude Code as subprocess — gets all CC tools for free, auto-improves as CC improves
- Offline compilation (no cloud, unpublished research stays local)
- Git-based version history
- 100+ scientific domain skills (could add psychiatry/neuroscience)
- PDF preview with "Capture & Ask" (select region, Claude explains)
- Typst support coming (simpler than LaTeX, renders to PDF)

**What to build (NOT fork ClaudePrism):**
- Install and configure ClaudePrism locally as the writing environment
- Add psychiatry-specific domain skills (DSM-5-TR diagnostic criteria formatting, APA citation style, clinical trial report structure, IRB protocol templates)
- Add CCA's academic paper scanner (MT-12) integration for literature search
- Create writing templates: case report, clinical study, review article, conference poster
- Evaluate Typst vs LaTeX for Matthew's use case (Typst is simpler, growing fast)

**Relationship to MT-12:** MT-12 discovers papers. MT-18 uses those papers as references in Matthew's writing. The two form a research-to-writing pipeline.

**Lifecycle:**
1. Research: Install ClaudePrism, evaluate capabilities, identify gaps for psychiatry
2. Plan: Domain skills needed, template designs, Typst vs LaTeX decision
3. Build: Psychiatry domain skills + templates + MT-12 integration
4. Test: Write a sample case report using the full pipeline
5. Validate: Matthew reviews output quality and workflow friction

**Status:** Not started. ClaudePrism repo: github.com/delibae/claude-prism. Session 39 created this task.

---

## MT-19: Local LLM Fine-Tuning Capability (Long-Term)

**Source:** https://www.reddit.com/r/LocalLLaMA/comments/1rw9jmf/ (Unsloth Studio, 813pts, 98% upvoted)
**What:** Explore fine-tuning small local models on CCA-specific patterns or Kalshi trading domain data using Unsloth Studio. This is a LONG-TERM exploration, not an immediate priority.

**Why it's interesting:**
- Train 500+ models 2x faster, 70% less VRAM
- Auto-create datasets from existing files (PDF, CSV, DOCX)
- Mac support (MLX coming)
- Could fine-tune a small model on CCA's self-learning patterns
- Could fine-tune on Kalshi trading patterns for faster inference
- Open source, free, no cloud dependency

**Reality check:** This requires GPU resources, significant dataset preparation, and evaluation infrastructure. It's a "when the time is right" task, not urgent. CCA's current approach (Claude API via Anthropic) works well.

**Status:** Not started. Long-term exploration. Unsloth repo: github.com/unslothai/unsloth.

---

## MT-20: Senior Developer Agent

**Source:** Session 70 nuclear research (self-learning/research/SENIOR_DEV_AGENT_RESEARCH.md) — 11 academic papers, 9 verified.
**Evidence base:** RovoDev (Atlassian, ICSE 2026): 38.7% comment action rate, 30.8% PR cycle time reduction. SWE-agent (NeurIPS 2024, 806 citations): ACI design > model capability. Tencent hybrid: 76% FP rate reduced to 2-6% with LLM+static hybrid. LLM QA survey (arXiv:2511.10271): maintainability is the most needed, least addressed quality dimension.

**What to build:** A senior developer review agent that catches what AI misses — SATD markers, effort signals, consistency violations, and architectural drift — delivered via PostToolUse hook and on-demand skill. NOT a replacement for human review. A quality-gate layer that surfaces the highest-value issues before they ship.

**Core insight from research:** AI catches ~46-48% of production bugs at best. The gap is exactly the senior developer's value: intent mismatches, architectural coherence, business logic errors. A Senior Dev Agent must filter its own output (quality gate is non-negotiable for developer trust).

**MVP (2-3 sessions):**
1. **SATD Detector** — Scan Write/Edit targets for TODO/FIXME/HACK/WORKAROUND/DEBT/XXX markers. Delivered as PostToolUse hook. Output: additionalContext with type, line, severity.
2. **Effort Scorer** — Estimate review complexity (1-5 scale) based on diff size, file count, cyclomatic complexity proxy. Helps prioritize review attention.
3. **False Positive Filter** — Wrap static analysis output through a confidence classifier to surface only high-value findings. Reduces noise before developer sees it.
4. **CRScore-Style Classifier** — Classify review output by type (bugfix/refactor/test/doc). Surface only bugfix + correctness first. Validated taxonomy from arXiv:2409.19801 (0.54 Spearman correlation).

**Full Vision (multi-session):**
- ADR Reader + Gap Detector: reads Architecture Decision Records, flags new patterns with no ADR backing
- Tech Debt Tracker: trends SATD markers over time, identifies hotspot modules
- Architectural Coherence Checker: verifies new code patterns match existing module patterns
- Blast-Radius Estimator: static dependency graph for change impact estimation
- Session Memory Integration: links findings to memory_store.py for cross-session learning

**Architecture:**
- Delivered as `agent-guard/satd_detector.py` (PostToolUse hook, extends AG module concept)
- Delivered as `/cca-review-pr` skill for on-demand review
- Filters output via quality gate (non-negotiable per RovoDev findings)
- Stdlib only + optional LLM API call for false positive filtering

**Status:** COMPLETE (S71-S83). All 10 gaps closed + E2E validated 10/10 with real API (claude-haiku-4-5-20251001, S83).

Built (S71-S81): 13 modules, ~3,000 LOC, ~890 tests, all passing:
- Infrastructure (S71-S74): satd_detector, effort_scorer, code_quality_scorer, fp_filter,
  review_classifier, tech_debt_tracker, adr_reader, senior_dev_hook — PostToolUse LIVE in hooks
- Intelligence layer (S78-S81): coherence_checker, senior_review, senior_chat (with LLMClient,
  intent verification, trade-off judgment), git_context — /senior-review skill LIVE

**Phases completed:**
- Phase 6: Hook output rewrite — natural language advice (S78) DONE
- Phase 7: /senior-review skill — APPROVE/CONDITIONAL/RETHINK verdicts (S78) DONE
- Phase 8: Interactive CLI chat — REPL + LLMClient + Anthropic API (S79-S80) DONE
- Phase 9: Architectural coherence — module structure, patterns, imports, rules (S78-S79) DONE
- Gap closure: Intent verification + trade-off judgment prompts (S81) DONE
- E2E test suite: 10 tests covering real API calls, skip without key (S81) DONE

**Next:** DONE. MT-20 is feature-complete. Converge with MT-21 Hivemind Phase 1.

---

## MT-21: Hivemind Multi-Chat Coordination

**Source:** Sessions 72-74 (initial build), Session 77 (gap analysis + phased rollout plan).
**What Matthew wants:** Desktop CCA chat coordinates 1 CLI chat (Phase 1), then 2 CLI chats (Phase 2+), to multiply development throughput while maintaining quality. NOT a 3-chat sprint from day one — prove 2-chat works over multiple sessions before scaling.

**What's built (S72-S74):**
- cca_hivemind.py (625 LOC, 22 tests) — process detection, AppleScript injection, safety
- cca_internal_queue.py (584 LOC, 69 tests) — JSONL queue, scope tracking, conflict detection
- cca_comm.py (249 LOC, 18 tests) — CLI wrappers for queue operations
- loop_health.py (251 LOC, 54 tests) — session health grading
- queue_injector.py (~150 LOC, 19 tests) — UserPromptSubmit hook
- /cca-init, /cca-auto, /cca-wrap made hivemind-aware (S74)

**What's NOT proven:**
- Sustained 2-chat operation (only tested once in S72)
- Error recovery (crash mid-scope-claim)
- Queue reliability under real load
- Worker productivity vs. overhead

**Phased rollout (HIVEMIND_ROLLOUT.md):**
- Phase 1: Validated 2-chat (Desktop + 1 CLI), 3-5 sessions, must pass all gates
- Phase 2: Hardened 2-chat with complex tasks, 3-5 sessions
- Phase 3: 3-chat operation (Desktop + 2 CLI), only after Phase 2 gate passes

**Relationship to MT-20:** Hivemind provides the transport + coordination layer.
Senior Dev (MT-20 Phase 8) provides the intelligence + review layer. They converge:
a proven hivemind + a proven senior dev skill = a CLI chat acting as your senior
developer colleague.

**Status:** Infrastructure COMPLETE. Phase 1 validation IN PROGRESS (S86).
- S86: 2 of 3-5 validation tests passed (trivial + real task). Zero coordination failures.
- Built launch_worker.sh (one-command launcher), fixed scope dedup, added assign alias, fixed task chaining.
- **Next:** 1-3 more validation tests, then Phase 1 gate assessment.

**Matthew's Extended Vision (S86 directive, documented in memory):**
- Phase 3 (NEW): Automated loop — CCA auto-starts worker, no manual intervention
- Phase 4 (NEW): Cross-project — CCA also launches Kalshi bot chats (main + research)
- Phase 5 (NEW): One-command full workspace (all 4 chats)
- Design requirement: User can chime in to ANY chat at any time, hivemind still coordinates
- Ultimate goal: CCA + Kalshi bot operate as unified system, financial profitability self-sustains subscription

---

## MT-22: Autonomous 1-Hour Loop (Desktop + Worker)

**Source:** Matthew's directive (Session 94) — "I want to be able to let you the CCA desktop chat and the helper CLI chat to work autonomously for at least 1 hour segments fully autonomy."
**What Matthew wants:** CCA desktop + CLI worker run autonomously for 1+ hour segments with zero human intervention. The pair picks tasks, executes with TDD, commits, chains to next task, and wraps cleanly when time is up.

**Why this is high priority:** Every minute Matthew has to babysit the chats is a minute he's not doing other work. The dual-chat system (MT-21) is proven. The safety guards (AG-9 bash_guard, path_validator, credential_guard) are all LIVE. The infrastructure is ready — what's missing is end-to-end validation of sustained autonomous operation.

**Safety status (S65 gaps now CLOSED):**
| Gap | Solution | Status |
|-----|----------|--------|
| Bash command blocklist | bash_guard.py (AG-9) | LIVE in hooks |
| Network egress guard | bash_guard.py | LIVE |
| Disk write guard | path_validator.py | LIVE |
| Process management guard | bash_guard.py | LIVE |
| Per-session runtime timeout | session_pacer.py | LIVE in cca-auto-desktop (S94) |
| Error notification | session_notifier.py (ntfy.sh) | LIVE in cca-wrap-desktop (S95, 19 tests) |
| Crash recovery | crash_recovery.py | Built (S91) |

**What needs to happen:**
1. ~~**Wire session_pacer into /cca-auto-desktop**~~ DONE (S94) — Step 0 reset, Step 5.7 mandatory check, Step 5.8 health check
2. ~~**Auto-wrap on timer**~~ DONE (S94) — pacer triggers WRAP_NOW/WRAP_SOON
3. ~~**Health check loop**~~ DONE (S94) — Step 5.8 runs full test suite every 2nd task
4. ~~**Failure recovery**~~ DONE (S94) — log blocker, skip task, continue pacing
5. ~~**Notification on wrap**~~ DONE (S95) — session_notifier.py sends ntfy.sh push on wrap/error
6. **E2E validation** — run 3 supervised 1-hour segments before trusting unsupervised

**What this is NOT:**
- NOT overnight operation (still risky, still deferred)
- NOT --dangerously-skip-permissions (use properly scoped allow list)
- NOT unguarded (all AG-9 safety hooks remain active)

**Lifecycle:**
1. Wire session_pacer into desktop/worker auto commands
2. Build auto-wrap timer integration
3. Health check loop (tests pass between tasks)
4. Supervised 1-hour trial #1 (Matthew at computer, not intervening)
5. Supervised 1-hour trial #2
6. Supervised 1-hour trial #3
7. Gate: 3/3 trials clean → approved for autonomous use

**Status:** GATE PASSED (S99) for CLI auto-loop. Now pivoting to DESKTOP ELECTRON APP automation (Matthew S130/S132 directive — #1 priority, equal to YoYo).

**NEW SCOPE (S131-132): Desktop Electron App Automation**
- S131: Research COMPLETE — Claude.app confirmed Electron, AppleScript viable, 5-phase plan
- S132 Phase 1 COMPLETE: `desktop_automator.py` — AppleScript control (activate, send, close, CPU idle, preflight). 66 tests.
- S132 Phase 2 COMPLETE: `desktop_autoloop.py` — Self-sustaining loop (ResumeWatcher, state, model selection). 49 tests.
- S132 Phase 3 COMPLETE: `start_desktop_autoloop.sh` launcher + `DESKTOP_AUTOLOOP_SETUP.md` setup guide.
- S132: Live preflight VALIDATED — all checks PASS. CPU idle detection working.
- **NEXT**: Supervised trial (Matthew watches 2 iterations). Then 3/3 clean runs to approve.
- Base value: 10. Last touched: S132.

---

## MT-23: Mobile Remote Control v2 (Telegram/Discord Channels)

**Source:** Matthew S103 vision — seamless iPhone experience for Claude Code communication
**What Matthew wants:** An app-like experience on iPhone to:
- Chat with active Claude Code sessions from phone
- Leave for minutes to an hour, hop right back in seamlessly
- Memory functions across mobile sessions
- Replace ntfy (Matthew: "ntfy doesn't seem optimal")

**Why this matters:** Currently the mobile approver uses ntfy which is fire-and-forget push notifications. The new official Anthropic Telegram/Discord channels MCP enables bidirectional chat from phone — a fundamentally better experience.

**Reddit intelligence (S103):**
- Official Anthropic feature (364 upvotes, 98%): Telegram and Discord channels via MCP
- Community already had custom solutions (Openclaw, tmux daemons) — Anthropic productized it
- Bug reported: context loss after long sessions (needs investigation)
- Signal support requested by community but not available yet

**Technical path:**
1. Research: Evaluate official Telegram/Discord channels MCP setup
2. Compare: Telegram vs Discord vs Signal (when available) for Matthew's use case
3. Build: Configure MCP integration, test session persistence
4. Validate: Hop-on/hop-off test — leave for 30 min, return, context intact
5. Wire: Replace ntfy mobile approver with channels-based communication
6. Polish: Memory persistence, session status display, quick-action buttons

**Status:** EXTERNALLY RESOLVED (S112). Claude Code Channels shipped March 20, 2026.
- Official Anthropic feature: native Telegram + Discord MCP channel servers
- Research preview, requires Claude Code v2.1.80+, claude.ai login
- Two-way: send commands from phone, get responses, approve permissions
- Plugin architecture: `--channels plugin:telegram@anthropic`
- Custom channels supported via `--dangerously-load-development-channels`
- Sender gating built in (allowlist-based, pairing flow for auth)
- Docs: https://code.claude.com/docs/en/channels-reference
- Source: https://github.com/anthropics/claude-plugins-official/tree/main/external_plugins
- **Next step for Matthew:** Install Telegram channel plugin and test with Kalshi bot session.

---

## MT-24: Visualization & Graphics Engine

**Source:** Matthew S103 vision — "exponentially smarter and better" visual capabilities
**What Matthew wants:**
- Diagrams (architecture, flow, sequence — beyond basic mermaid)
- Charts (data visualization, performance metrics, trading analytics)
- Figures (publication-quality for academic presentations)
- Interactive dashboards (beyond current HTML dashboard)

**Technical path (needs research):**
- Evaluate: matplotlib, plotly, seaborn for chart generation
- Evaluate: D3.js or Chart.js for interactive web dashboards
- Evaluate: graphviz, mermaid-cli for diagram generation
- Build: Chart generator module that produces publication-quality visuals
- Integration: Wire into reports, slides, dashboards, and academic writing

**Relationship to existing work:**
- MT-17 (Design/Reports) delivered basic reports/slides/dashboard — COMPLETED
- This goes deeper: interactive, publication-quality, trading-specific

**Status:** Phase 1 COMPLETE (S111) — `trading_chart.py` (5 SVG chart types: PnL curve, win rate, strategy matrix, drawdown, heatmap). 41 tests.

---

## MT-25: Presentation Generator (Matthew's Style)

**Source:** Matthew S103 vision — Grand Rounds and psychopharmacology lecture presentations
**What Matthew wants:**
- Perfect PowerPoint generator specific to his presentation style
- NOT "AI slop" — must match his actual aesthetic and structure preferences
- Port Claude Pro presentation workflow to Claude Code capability
- Encode his style rules (layout, fonts, colors, content density, slide transitions)

**WAITING:** Matthew to provide style samples and further info before implementation begins.

**Technical path (after style info received):**
1. Analyze: Study Matthew's existing presentations to extract style rules
2. Encode: Build a presentation style profile (similar to Reddit Post #1 infosec Skills pattern)
3. Build: PowerPoint generator that applies the style profile
4. Validate: Generate a test presentation, Matthew reviews for "AI slop" detection
5. Iterate: Refine based on feedback until indistinguishable from manual work

**Status:** NOT STARTED. BLOCKED on style samples from Matthew.

---

## MT-26: Financial Intelligence Engine

**Source:** Matthew S103 vision — academic research + market analysis backbone for trading
**What Matthew wants:**
- CCA becomes the research/analysis backbone for Kalshi profitability
- Academic papers on prediction markets, Bayesian methods, probability theory
- Market condition analysis: read and interpret market conditions quickly
- Adaptation speed: respond to changing conditions faster
- Statistical rigor: proper significance testing, sample size guards
- Long-term: extend to investments/stocks after Kalshi proves profitable

**Financial targets (ordered milestones):**
- A: Cover Claude Max 5x ($125/mo)
- B: Cover Claude Max 20x ($250/mo)
- C: Compounding passive income (few hundred USD/mo)
- D: Transition to investments/stocks (long-term)

**Relationship to existing work:**
- MT-0 (Kalshi self-learning) covers Phase 1 — trading domain schema
- MT-12 (Academic papers) built the scanner — COMPLETED
- This MT extends both: specialized financial research + actionable intelligence

**Technical path:**
1. Research: Survey what financial intelligence tools exist (papers, APIs, data sources)
2. Design: Financial intelligence pipeline (data ingestion → analysis → signal → cross-chat delivery)
3. Build: Specialized research modules for prediction markets, economics, Bayesian methods
4. Wire: Connect to Kalshi cross-chat bridge for direct bot intelligence
5. Validate: Track which intelligence items led to profitable trades (closed feedback loop)
6. Expand: Add investment/stocks domain when Kalshi profitability proven

**Status:**
- Research COMPLETE (S104-105): MT26_FINANCIAL_INTEL_RESEARCH.md — papers, data sources, repos, 3-tier plan
- Tier 1 COMPLETE (S108-110): regime_detector.py (21 tests), calibration_bias.py (43 tests), cross_platform_signal.py (30 tests)
- Tier 2 COMPLETE (S110): dynamic_kelly.py (32 tests), macro_regime.py (30 tests), fear_greed_filter.py (38 tests)
- Pipeline COMPLETE (S110): signal_pipeline.py (32 tests) — chains all 6 modules, compound modifiers, BET/SKIP
- Tier 3 Phase 1 COMPLETE (S112): order_flow_intel.py (38 tests, FLB regression, risk classifier, Maker/Taker model), belief_vol_surface.py (27 tests, logit transforms, Greeks, realized vol)
- Tier 3 Design COMPLETE (S112): MT26_TIER3_DESIGN.md — full paper analysis for both modules
- Pipeline updated (S112): order_flow_risk wired as Stage 6 (7-stage pipeline), market_category input added
- Bridge updated (S112): CCA_TO_POLYBOT.md with Tier 3 intel for Kalshi bot
- Tier 3 Phase 2 DEFERRED: Kalman filter + EM separator + B-spline surface (needs numpy)

---

## MT-27: CCA Nuclear v2 (Enhanced Scanning)

**Source:** Matthew S103 vision — better Reddit/GitHub scanning with safety-first approach
**What Matthew wants:**
- Better signal-to-noise ratio (APF currently 22.7%, target 40%)
- Reduce "Other" category drag (9.7% = misclassified posts)
- Enhanced GitHub trending repo analysis
- ABSOLUTE safety: no rat poison, no malware, no personal info exposure

**Technical path:**
1. Analyze: Why is "Other" at 9.7%? Better frontier tagging or scan filtering
2. Build: Improved post classifier with more granular category mapping
3. Wire: hit_rate_tracker into /cca-wrap as APF checkpoint
4. Validate: APF improvement measured session-over-session
5. GitHub: Enhance github_scanner with better repo quality signals

**Relationship to existing work:**
- MT-6 (Nuclear at will) — COMPLETED, built profiles.py
- MT-9 (Autonomous scanning) — COMPLETED, built autonomous_scanner.py
- MT-11 (GitHub intelligence) — COMPLETED, built github_scanner.py
- This MT improves quality of the existing scanning infrastructure

**Status:** Phases 1-5 COMPLETE.
- Phase 1: APF analysis — "Other" category dropped from 124/335 (37%) to 0/335 (0%). Expanded FRONTIER_PATTERNS from 8 to 15 categories. 10 new tests.
- Phase 2: classify_post HAY expansion — 28 new sentiment/opinion HAY keywords (vibe coded, changed my life, model announcements, outage, etc.). 17 new tests.
- Phase 3: apf_checkpoint() function + scan report integration. 6 new tests.
- Phase 4 (S129/S132): 3-tier NEEDLE precision improvement. Split keywords into strong (always NEEDLE) and weak (need engagement signals: score>=100 OR body>=500 OR comments>=25). Reduces false positives from low-value showcase posts. +37 new tests.
- Phase 5 (S115): apf_session_tracker.py — per-session APF trend tracking. Append-only JSONL snapshots at ~/.cca-apf-snapshots.jsonl. Wired into /cca-wrap + /cca-wrap-desktop. 27 tests.

---

## MT-28: Self-Learning v2 (Multi-Domain)

**Source:** Matthew S103 vision — significant YoYo improvements across multiple facets
**What Matthew wants:**
- Cross-domain learning: CCA self-improvement informs Kalshi self-improvement
- Predictive capability (not just pattern detection)
- Sentinel-style adaptive mutation: analyze failures, generate counter-strategies
- Closed feedback loop from Kalshi outcomes → research prioritization

**Relationship to existing work:**
- MT-10 (YoYo self-learning) — COMPLETED, Phase 3 validated
- MT-0 (Kalshi self-learning) — Phase 1 done, Phase 2 = deploy
- journal.py, reflect.py, strategy.json, improver.py — all built
- This MT takes existing pieces and makes them work across domains

**Technical path:**
1. Research: Cross-domain transfer learning patterns in self-improvement systems
2. Design: Multi-domain journal schema (CCA ops, Kalshi trading, research effectiveness)
3. Build: Domain adapter layer so same reflect/improve pipeline works across domains
4. Wire: Closed loop — Kalshi outcomes feed back into research prioritization
5. Validate: Measurable improvement in research hit rate AND trading ROI
6. Iterate: Sentinel-style mutation — counter-strategies for repeated failure patterns

**Status:** COMPLETED (S111). All 6 phases done:
- Phase 1: principle_registry.py (73 tests) — Laplace-scored principles by domain
- Phase 2: pattern_registry.py + detectors.py (42 tests) — Plugin detector architecture
- Phase 3: principle_transfer.py (34 tests) — Cross-domain affinity-based transfer
- Phase 4: outcome_feedback.py (16 tests) — Research outcomes → principle scoring
- Phase 5: predictive_recommender.py (40 tests) — Pre-session ranked recommendations
- Phase 6: sentinel_bridge.py (30 tests) — SentinelMutator → principle registry bridge

---

## MT-29: Cowork + Claude Pro Bridge Hivemind

**Source:** Matthew S103 vision — Cowork integration + Pro↔Code bridge
**What Matthew wants:**
- Evaluate Claude Cowork for CCA workflows (is it objectively better than current hivemind?)
- Bridge Claude Pro (web/desktop) with Claude Code for unified experience
- Strategy discussions in Pro, implementation in Code, shared context
- Extends MT-5 (partially self-resolved) and MT-21 (hivemind coordination)

**Technical path (needs research):**
1. Research: What Cowork can and can't do vs our current worker pattern
2. Research: Claude Pro MCP access, shared context mechanisms
3. Evaluate: Is Cowork objectively better for our use cases?
4. Design: Pro↔Code bridge architecture
5. Build: If Cowork adds value, integrate. If not, document why and close.
6. Wire: Connect to hivemind coordination (MT-21)

**Status:** Research COMPLETE (S114). Verdict: SKIP. Cowork adds no value over our hivemind for dev workflows. No Pro↔Code bridge exists. Local MCP bugs (GitHub #23424). See MT29_COWORK_RESEARCH.md.
Revisit when: Anthropic ships native shared context, or Cowork local MCP bugs fixed.

---

## MT-30: Session Daemon (Tmux-Based Auto-Spawn)

**Source:** S109-110 — identified as #1 force multiplier
**What it does:**
- Tmux-based session lifecycle manager
- Watches for session endings, auto-spawns replacements
- Detects crashes, cleans up orphaned scopes
- Respects peak hours (fewer chats during peak)
- One command to start/stop all sessions

**Technical path (design doc complete — SESSION_DAEMON_DESIGN.md):**
1. DESIGN COMPLETE (S110): Full architecture, 5-phase plan
2. Phase 2: session_registry.py + tmux_manager.py (building blocks)
3. Phase 3: session_daemon.py (poll loop, health checking, spawn/restart)
4. Phase 4: Integration testing (dry run with 2 sessions)
5. Phase 5: Hardening (max restart limits, PID file, log rotation)

**Key constraint:** Matthew explicit S110: "NOT something to build within 1 chat. Spread over several chats."

**Reuses existing infrastructure:**
- chat_detector.py (process health)
- crash_recovery.py (orphaned scope cleanup)
- peak_hours.py (rate limit awareness)
- cca_comm.py (queue messages)
- session_pacer.py (wrap timing)

**Status:** Phase 8 COMPLETE (S128). S129: +preflight command, +rich --status with audit log, +AUTOLOOP_SETUP.md. Ready for live supervised dry run.
- Phase 2 (S111): `session_registry.py` (60 tests) + `tmux_manager.py` (40 tests)
- Phase 3 (S112): `session_daemon.py` — poll loop, health checking, spawn/restart, peak hours (45 tests)
- Phase 4 (S113): Integration tests — lifecycle, peak transitions, crash recovery chains (27 tests)
- Phase 5 (S113): Hardening — `_mark_exhausted_sessions` FAILED state fix, log rotation (9 tests)
- Phase 6 (S126): `cca_autoloop.py` — reads SESSION_RESUME.md, spawns claude, loops (43 tests)
  - `start_autoloop.sh` — one-command tmux launcher
  - `session_daemon_cca_only.json` — CCA-only daemon config (1 session max)
  - Safety: 3 consecutive crashes = stop, 3 short sessions = stop, max 50 iterations, cooldown 15s
- Phase 7 (S127): Desktop mode + model alternation (85 tests)
  - `--desktop` opens visible Terminal.app windows via osascript
  - Model alternation: round-robin/opus-primary/sonnet-primary strategies
  - `--dangerously-skip-permissions` for full automation
  - Session de-duplication pre-flight check
- Phase 8 (S128): Production hardening (116 tests)
  - Terminal.app close race condition fixed (shell exits before close)
  - Terminate dialog handled via System Events + retry close
  - Pre-flight: claude binary check, Terminal.app status, Accessibility permissions, orphan cleanup
  - Rate limit handling: exit codes 2/75 get 5min cooldown, not counted as crashes
  - Stale resume detection + prompt size truncation (>100KB)

**How to use (Matthew):**
1. `python3 cca_autoloop.py preflight --desktop` — check all prerequisites first
2. `./start_autoloop.sh --desktop` — opens visible Terminal.app windows (recommended)
3. `./start_autoloop.sh` — runs in current terminal (tmux recommended)
4. `./start_autoloop.sh --tmux` — launches in tmux window
5. `python3 cca_autoloop.py status` — rich status with audit history
6. `MODEL_STRATEGY=opus-primary ./start_autoloop.sh --desktop` — Opus only
7. Ctrl-C to stop
8. See `AUTOLOOP_SETUP.md` for Accessibility permissions setup

**Next: Live supervised dry run. Close desktop app chat first, then run from plain terminal.**
Last updated: S128 (2026-03-23).

---

## MT-31: Gemini Pro Integration (Cross-Model Leverage)

**Source:** Matthew directive (S115) — has Gemini Pro access via Google account ($20/mo Google One subscription includes 2TB storage + Gemini Pro)
**What Matthew wants:** Explore how Gemini Pro can be beneficial alongside Claude Code. NOT a replacement — a complement.

**Potential use cases (to be researched):**
- Cross-model code review (Gemini reviews Claude's output, different training biases = different blind spots — validated by community in MT-20 research)
- Gemini as design reference generator (MT-4 pattern: Gemini creates design guides from screenshots, feed to Claude)
- Multi-model research validation (same question to both models, compare answers for higher confidence)
- Gemini for large document processing (different context window trade-offs)
- MCP server that bridges Gemini Pro API into Claude Code workflows

**What this is NOT:**
- Not replacing Claude with Gemini for any core task
- Not building a Gemini-only workflow
- Not a priority over Kalshi bot, visuals/design, or autonomous loop

**Technical path:**
- Research: What APIs/integrations does Gemini Pro provide? Can it be called from Python stdlib?
- Design: Which CCA workflows would benefit from a second model's perspective?
- Build: Lightweight adapter (one file) that sends queries to Gemini and returns structured results
- Test: Compare cross-model review quality vs single-model review

**Matthew's current priorities (S115, explicit):**
1. Kalshi bot maintenance
2. Visuals/UI/graphics/design expansion
3. Autonomous loop (CCA desktop auto-spawning new sessions)
4. All of the above are multi-session, not single-chat

**Status:** S125 E2E validation: Gemini Flash WORKS via @rlabs-inc/gemini-mcp (v0.8.1). Pro UNAVAILABLE — Google One gives web app Pro access only, not API access. API Pro requires separate Google Cloud billing. Matthew directive: Flash only (Option 1). Scope narrowed to Gemini Flash integration.
Last updated: S125 (2026-03-23).

---

## MT-32: Visual Excellence & Design Engineering (Comprehensive)

**Source:** Matthew directive (S118, 2026-03-21) — "advancements doesn't just mean different types of charts it means enhancements in UI development or graphic designs or visuals or report generation or figures or images like any of this"
**What Matthew wants:** A single comprehensive MT that covers ALL visual/design/graphics work across CCA. This is the umbrella task for everything visual — from chart types to UI frameworks to report generation to image creation to design systems.

**Scope — 8 pillars:**

1. **Report Development** — Enhance /cca-report pipeline. Wire report_charts.py into Typst template. Richer layouts (multi-column, pull-quotes, sidebar callouts). Automated visual storytelling. Report version comparison (diff highlights). Professional output that rivals consultancy deliverables.

2. **UI Development** — Building better web interfaces, component libraries, responsive design patterns. Interactive web apps Claude Code can generate. Reusable UI component catalog (buttons, cards, tables, navigation). CSS framework integration (Tailwind, etc.). Accessibility-first patterns.

3. **Graphic Design** — Visual assets, branding, icons, infographics, visual summaries. SVG icon generation. Logo and brand identity tools. Infographic templates for presenting complex data. Visual abstracts for academic papers.

4. **Data Visualization** — Beyond current 12 chart types. Interactive charts (zoom, hover, filter). Real-time data dashboards. D3.js-quality visualizations. Animation/transition support. Publication-quality statistical graphics (box plots, violin, scatter matrix, forest plots).

5. **Figure & Image Generation** — Publication-quality figures for academic/professional use. SVG/PNG export pipelines. Diagram generation (architecture, flow, sequence, ER). Scientific figure layout (multi-panel, consistent axes, proper legends). Screenshot annotation tools.

6. **Dashboard Enhancement** — Current HTML dashboard is functional but basic. Interactive filtering and sorting. Real-time data updates. Responsive mobile layouts. Dark/light theme. Embeddable dashboard widgets. Dashboard-as-a-service pattern.

7. **Design System Maturation** — Expand design-guide.md into a real design system. Color tokens, spacing scale, typography hierarchy. Design lint rules (detect violations). Cross-output consistency (same visual language in PDFs, HTML, slides). Design system documentation generator.

8. **Presentation & Slide Design** — Advanced slide generation. Custom themes. Animation sequencing. Speaker notes integration. Multi-format export (PDF, HTML, PPTX). (Subsumes MT-25 when Matthew provides style samples.)

**Relationship to existing MTs:**
- MT-17 (COMPLETE): Laid the foundation — reports, slides, dashboard, charts, website, daily_snapshot. 867 tests in `design-skills/`.
- MT-24 (Phase 1 COMPLETE): Visualization engine — trading_chart.py, 41 tests. **Absorbed into MT-32 Pillar 4.**
- MT-25 (WAITING): Matthew's presentation style. **Absorbed into MT-32 Pillar 8** — will proceed when style samples arrive.
- MT-32 drives the NEXT LEVEL of ALL visual work, building on MT-17's foundation.

**What exists today (starting inventory):**
- `design-skills/` module: 867 tests, 12 chart types, report_generator.py, slide_generator.py, dashboard_generator.py, chart_generator.py, website_generator.py, daily_snapshot.py, report_charts.py
- `design-skills/design-guide.md`: Color palette, typography, layout rules
- `design-skills/templates/`: Typst templates (cca-report.typ, cca-slides.typ)
- `/cca-report`, `/cca-dashboard`, `/cca-slides`, `/cca-website` commands
- trading_chart.py: 5 trading-specific SVG chart types

**Research needed (worker nuclear scan targets):**
- **Subreddits**: r/webdev, r/reactjs, r/frontend, r/UI_Design, r/dataisbeautiful, r/datavisualization, r/web_design, r/graphic_design, r/css, r/tailwindcss, r/ClaudeCode (visual posts), r/ChatGPTCoding (visual posts), r/svelte, r/nextjs
- **GitHub**: Trending repos tagged visualization, design-system, chart, svg, report-generator, dashboard, ui-library, infographic
- **Focus**: What tools/techniques produce the best AI-assisted visual output? What are the community's biggest pain points with LLM-generated UIs? What design patterns survive beyond the demo?
- **Rat poison filter**: No 8000-line prompt libraries (MT-17 lesson from Design Studio). No Figma MCP dependencies. No "team of specialists" metaphors. Seek concrete, buildable, testable improvements.

**Phased approach:**
- Phase 1: Wire report_charts.py into /cca-report (immediate — S118). Research scan.
- Phase 2: Advanced chart types (interactive, animated, publication-quality statistical graphics)
- Phase 3: Design system v2 (design tokens, lint rules, cross-format consistency)
- Phase 4: UI component library (reusable patterns for Claude Code web outputs)
- Phase 5: Dashboard v2 (interactive, real-time, responsive, themeable)
- Phase 6: Figure/image generation pipeline (multi-panel, annotation, export)
- Phase 7: Integration — all pillars feeding into reports, dashboards, slides, websites

**Success criteria:** A CCA session can produce visual outputs (reports, dashboards, charts, web pages) that look professional WITHOUT manual post-processing. The visual quality gap between Claude Code output and professional design tools shrinks measurably.

**Status:** NEW (S118). Phase 1 starting — report_charts.py integration + research scan.
Last updated: S118 (2026-03-21).

---

## Priority Scoring System (Improved — S98)

**Automated:** `python3 priority_picker.py recommend` — runs the improved formula and returns actionable picks.

**Improved formula (S98):** `score = base_value + aging_capped + completion_bonus + roi_estimate + stagnation_penalty`

| Component | What | Range |
|-----------|------|-------|
| `base_value` | Force-multiplier (1-10) | 1-10 |
| `aging_capped` | sessions_since_touch * rate, capped at 1x base | 0 to base |
| `completion_bonus` | 50-74% = +1, 75-89% = +2, 90%+ = +3 | 0-3 |
| `roi_estimate` | Near done (85%+) = +2, close (70%+) = +1 | 0-2 |
| `stagnation_penalty` | At cap AND untouched 10+ sessions = -1 | -1 or 0 |

**Why this beats the old formula:**
- Old formula let capped tasks (MT-18, MT-13) permanently tie with high-base tasks — no way to distinguish
- Completion bonus rewards finishing what's started over starting new things
- Stagnation penalty flags tasks that need a decision: work them or archive them
- ROI estimate prioritizes quick wins (1-session-to-complete)
- Blocked tasks with self-resolution notes now surface via `--include-blocked`

**CLI commands:**
```bash
python3 priority_picker.py pick          # Top 3 tasks to work on
python3 priority_picker.py recommend     # Full recommendations with context
python3 priority_picker.py table         # Markdown priority table
python3 priority_picker.py rank          # Quick ranked list
python3 priority_picker.py stagnating    # Tasks that need attention
python3 priority_picker.py json          # Export for programmatic use
```

- Current session: 103.

### Completed (no scoring needed)

| MT | Task | Status |
|----|------|--------|
| MT-0 | Kalshi self-learning integration | COMPLETE — Phase 2 deployed via kalshi_self_learning.py (916 LOC) + 6 analysis modules (4225 LOC total) in polymarket-bot |
| MT-2 | Mermaid diagrams | COMPLETE |
| MT-3 | Virtual design team | COMPLETE |
| MT-4 | Design vocabulary | COMPLETE |
| MT-6 | Nuclear at will | COMPLETE — profiles.py, 43 tests |
| MT-7 | Trace analysis | COMPLETE — trace_analyzer.py, 50 tests |
| MT-8 | iPhone remote control | EXTERNALLY RESOLVED (S94) — native Remote Control + ServerCC/Moshi apps |
| MT-9 | Autonomous scanning | COMPLETE (S95) — autonomous_scanner.py, Phase 3 E2E validated, 101 tests |
| MT-10 | YoYo self-learning | COMPLETE (S97) — Phase 3A real DB validated, Phase 3B resurfacer done, 28 tests |
| MT-11 | GitHub intelligence | COMPLETE (S83) — github_scanner.py + trending, 62 tests |
| MT-14 | Rescan stale subs | COMPLETE (S84) — execute_rescan_stale + rescan-all CLI, 101 tests |
| MT-15 | GitHub repo tester | COMPLETE — repo_tester.py, 51 tests |
| MT-17 | Design/reports | COMPLETE (S96) — 6 phases done: reports, slides, dashboard, charts, website, daily_snapshot. 213 tests |
| MT-20 | Senior Dev Agent | COMPLETE (S83, LLM validated S101) — 13 modules, ~890 tests, session_id.py wired (7 modules), E2E LLM confirmed |
| MT-12 | Academic research papers | COMPLETE (S102) — 6 phases: paper scanner, digest, cross-chat bridge, 1242 papers, confidence calibrator, hit_rate_tracker. ~150 tests |
| MT-22 | Autonomous 1-hour loop | COMPLETE (S99/S132) — CLI autoloop gate passed (S99). Desktop autoloop built (S132): desktop_automator.py, desktop_autoloop.py, 115 tests. Awaiting supervised trial. |
| MT-27 | CCA Nuclear v2 | COMPLETE (S115/S129) — 5/5 phases: NEEDLE classifier, APF tracking, precision improvement. 440 tests. |
| MT-28 | Self-Learning v2 | COMPLETE (S111) — 6/6 phases: principle_registry, pattern_registry, principle_transfer, outcome_feedback, predictive_recommender, sentinel_bridge. ~230 tests. |
| MT-30 | Session Daemon | COMPLETE (S128) — 8/8 phases: cca_autoloop.py, start_autoloop.sh, preflight checks, audit logging, rate limit handling. 116 tests. Awaiting supervised trial. |

### Matthew's Priority Override (S134 — CCA_PRIME_DIRECTIVE.md)

**The Two Pillars override scoring.** Desktop autoloop (MT-22/MT-30) is the #1 priority
until proven reliable through supervised trials. Self-learning evolution is the permanent
background process. Everything else serves these two axes. See `CCA_PRIME_DIRECTIVE.md`.

**Immediate sequence:** Supervised trial -> Perfect error handling -> Prove quality -> Run constantly -> Knock out MTs at scale.

### Active Priority Queue (S134 updated)

| Rank | MT | Task | Base | Age | Comp% | Bonus | ROI | Stag | **Score** | Urgency | Next |
|------|----|------|------|-----|-------|-------|-----|------|-----------|---------|------|
| **P1** | **MT-22/30** | **Desktop autoloop supervised trial** | **—** | **—** | **100%** | **—** | **—** | **—** | **OVERRIDE** | **S134 DIRECTIVE** | **Run supervised trial -> perfect -> prove -> run constantly** |
| 1 | MT-21 | Hivemind coordination | 8 | +1.0 | 67% | +1.0 | +0.0 | 0.0 | **10.0** | routine | Phase 2 PASSED (6th). Phase 3 = 3-chat |
| 2 | MT-33 | Strategic Intelligence Report | 9 | +0.0 | 50% | +0.0 | +1.0 | 0.0 | **10.0** | S121 | Phase 4-6: chart integration, self-reference, hardening. kalshi_data_collector + learning_data_collector + report_differ built (S122-S123). |
| 3 | MT-23 | Mobile Remote Control v2 | 8 | +0.0 | 0% | +0.0 | +1.0 | 0.0 | **9.0** | NEW (S103) | Research: evaluate Telegram/Discord channels MCP |
| 4 | MT-26 | Financial Intelligence Engine | 7 | +0.0 | 92% | +0.0 | +1.0 | 0.0 | **8.0** | S103 | CCA scope COMPLETE. Tier 3 Phase 2 deferred (needs numpy). 79 pipeline tests. |
| 5 | MT-32 | Visual Excellence & Design Engineering | 8 | +0.0 | 15% | +0.0 | +0.0 | 0.0 | **8.0** | S118 | Phase 2+: nuclear scan, Kalshi charts, consistency. report_charts wired (S117). |
| — | MT-34 | Medical AI (OpenEvidence replacement) | 6 | +0.0 | 0% | +0.0 | +0.0 | 0.0 | **6.0** | IDEA (S121) | BLOCKED: Matthew refining concept. Do not start. |
| 6 | MT-24 | Visualization & Graphics Engine | — | — | — | — | — | — | **ABSORBED** | — | Absorbed into MT-32 Pillar 4 |
| 7 | MT-25 | Presentation Generator | — | — | — | — | — | — | **ABSORBED** | — | Absorbed into MT-32 Pillar 8 (WAITING: style samples) |
| 8 | MT-29 | Cowork + Pro Bridge Hivemind | 5 | +0.0 | 0% | +0.0 | +0.0 | 0.0 | **5.0** | NEW (S103) | Research: evaluate Cowork, bridge Pro↔Code |
| 9 | MT-18 | Academic writing | 4 | +4.0 | 0% | +0.0 | +0.0 | -1.0 | **7.0** | stagnating | Research: install/evaluate ClaudePrism |
| 10 | MT-13 | iOS/macOS app dev | 4 | +4.0 | 33% | +0.0 | +0.0 | -1.0 | **7.0** | stagnating | Phase 3: first real app |

### Blocked / External (surfaced via `--include-blocked`)

| MT | Task | Reason | Self-Resolution | **Score (if unblocked)** |
|----|------|--------|-----------------|--------------------------|
| MT-1 | Maestro visual grid | macOS SDK | MOSTLY SELF-RESOLVED: Claude Control best candidate | **8.0** |
| MT-5 | Claude Pro bridge | Needs research | PARTIALLY SELF-RESOLVED: Remote Control + Chrome ext | **9.0** |
| MT-16 | Detachable chat tabs | Anthropic feature | STILL OPEN: GitHub issues filed | N/A |
| MT-19 | Local LLM fine-tuning | GPU resources | STILL OPEN: not self-resolving | N/A |

---

## MT-33: Strategic Intelligence Report (Kalshi + Self-Learning + Research)

**Source:** Matthew directive (S121, 2026-03-22) — "would love to see statistical analysis regarding the overall bets, or bets from that day, market trends... also incorporate the self-learning section there or a whole section talking about future research"

**What Matthew wants:** Transform /cca-report from a project status document into a strategic intelligence artifact that future chats can reference. Merge CCA project health with Kalshi bot financial analytics, self-learning insights, and research pipeline status — all in one professional PDF.

**Why this matters:** Right now the report is a snapshot of CCA's codebase health. Matthew wants it to be the single document he can look at to understand: how the bot is performing, what the self-learning system has discovered, what research is pending, and where CCA is heading. It also stress-tests the chart library with real financial data.

**Scope — 6 pillars:**

1. **Kalshi Bot Financial Analytics Section**
   - Overall P&L summary (cumulative, daily, weekly)
   - Win rate and confidence calibration charts
   - Bet volume and market category breakdown
   - Signal pipeline performance (which signals are working)
   - Regime-stratified analysis (trending vs mean-reverting vs chaotic)
   - Uses: ScatterPlot (win rate vs confidence), BoxPlot (profit distribution by market), HistogramChart (bet size distribution), LineChart (cumulative P&L)
   - Data source: Kalshi bot SQLite DB (READ-ONLY access per CLAUDE.md)

2. **Self-Learning Intelligence Section**
   - Pattern detection summary (what the system learned this period)
   - Principle registry health (which principles are scoring well)
   - Strategy health verdicts (HEALTHY/MONITOR/PAUSE/KILL)
   - Sentinel mutation log (what adaptations were made)
   - Research outcomes ROI (which CCA deliveries produced Kalshi profit)
   - Uses: BarChart (principle scores), RadarChart (strategy dimensions), GaugeChart (overall learning health)

3. **Research Pipeline Section**
   - Academic papers discovered and their relevance scores
   - Research-to-implementation pipeline status
   - Pending research topics and priority
   - Cross-domain transfer opportunities
   - Uses: FunnelChart (papers -> evaluated -> implemented -> profitable)

4. **Market Context Section**
   - Macro regime current state (CALM/ELEVATED/HIGH_IMPACT)
   - Upcoming calendar events (FOMC, CPI, NFP)
   - Cross-platform signals (Kalshi vs Polymarket divergence)
   - Fear & greed indicator current reading
   - Uses: HeatmapChart (market activity by category/time), GaugeChart (regime indicator)

5. **Actionable Recommendations Section**
   - Top 3 research priorities for next session
   - Strategy adjustments based on self-learning
   - Risk alerts (drawdown trends, stagnation, regime shifts)
   - "What to build next" based on where the gaps are
   - This section is the bridge: CCA tells Kalshi what to do

6. **Self-Reference Hook**
   - Report data exportable as structured JSON alongside PDF
   - Future chats can parse previous reports for continuity
   - Trend comparison: "this report vs last report" diff highlights
   - Report becomes a persistent knowledge artifact, not just a visual

**Data Sources (all READ-ONLY):**
- Kalshi bot SQLite DB: `~/Projects/polymarket-bot/kalshi_bot.db` (or equivalent)
- Self-learning journal: `self-learning/journal.jsonl`
- Principle registry: `~/.cca-principles.json`
- Research outcomes: `~/.cca-research-outcomes.jsonl`
- APF snapshots: `~/.cca-apf-snapshots.jsonl`
- Existing report_generator.py data collection pipeline

**Cardinal Safety:**
- NEVER expose account balances, API keys, or wallet addresses in the report
- Financial data shown as relative (percentages, ratios) not absolute amounts where sensitive
- P&L can be shown in dollar amounts (Matthew-authorized) but never account credentials
- All DB access is read-only via Python sqlite3 — no writes, no schema changes

**Multi-session execution (Matthew explicit: "not something that could be developed in one chat"):**
- Phase 1: Deep dive research — what metrics matter, what data is available, what charts fit
- Phase 2: Data collection layer — SQL queries, data transformers, schema mapping
- Phase 3: Report section templates — Typst layouts for each pillar
- Phase 4: Chart integration — wire real data into chart_generator.py chart types
- Phase 5: Self-reference hook — JSON export, report diffing, chat-parseable format
- Phase 6: Hardening — edge cases (empty DB, no bets today, missing data), test suite

**Relationship to existing infrastructure:**
- Extends report_generator.py (existing /cca-report pipeline)
- Consumes self-learning/ module outputs (journal, principles, strategies)
- Consumes Kalshi bot DB (cross-project READ per CLAUDE.md authorization)
- Uses chart_generator.py's 21 chart types (the real test for MT-32)
- Feeds into cross-chat bridge (CCA_TO_POLYBOT.md recommendations)

**Success criteria:**
- Matthew can glance at one PDF and know: bot health, learning progress, research pipeline, next actions
- Future chats can load the JSON sidecar for continuity
- Charts make the data genuinely easier to understand than raw numbers

---

---

## MT-34: Medical AI Tool — OpenEvidence Replacement (Provider-Grade)

**Source:** Matthew directive (S121, 2026-03-22) — "I hate OpenEvidence... I want to ClaudeCode an objectively superior, smarter, more capable, more accurate, more effective, less contradictory, less lying form of OpenEvidence"

**What Matthew wants:** An AI tool for himself as a PGY-3 Psychiatry resident and medical provider that answers clinical questions better than OpenEvidence. Not a standalone app — something that augments Claude (Pro or Code) to function as a reliable, evidence-based medical reference.

**Why this matters:** Matthew is a practicing physician who needs accurate, citation-backed medical answers on the fly. OpenEvidence exists but is unreliable (contradictory, inaccurate). A provider-grade tool built by a provider who knows what's actually needed would be genuinely useful.

**Status:** IDEA LOGGED — Matthew needs more time to refine the concept. Do NOT start building until Matthew gives the green light.

**Research needed before any implementation:**
1. Deep dive on OpenEvidence: how it works, data sources, delivery format, why users love/hate it (Reddit, GitHub, medical forums)
2. What medical databases/APIs are available (PubMed, UpToDate, Cochrane, DynaMed, clinical guidelines)
3. How Claude Pro handles medical questions today — what's missing
4. What form factor works: CLAUDE.md-style system prompt? MCP server connecting to medical DBs? Custom slash commands? Project-specific knowledge base?
5. PGY-3 Psychiatry-specific needs: DSM-5-TR, prescribing guidelines, drug interactions, evidence levels, treatment algorithms
6. Accuracy/citation requirements: every claim needs a source, confidence levels, contradictions flagged not hidden

**Possible form factors (TBD — Matthew to decide):**
- Claude Pro project with curated system prompt + medical knowledge rules
- MCP server that queries PubMed/medical databases and injects citations
- Claude Code slash commands for specific clinical workflows
- Hybrid: Claude Code builds the knowledge layer, Claude Pro consumes it

**Cardinal safety (medical-specific):**
- This is a PROVIDER tool, not patient-facing — assumes medical training
- Must always cite sources — never present unsourced claims as fact
- Must flag uncertainty and contradictions explicitly
- Must include recency of evidence (guidelines change)
- NOT a diagnostic tool — it's a reference/lookup augmentation

**Relationship to CCA:**
- Falls under "personal tools for Matthew" scope (like academic writing MT-18)
- Could leverage existing CCA infrastructure: paper_scanner.py, research pipeline
- REFERENCE-PERSONAL verdict category in nuclear scans

---

## MT-35: Background Autoloop — Non-Intrusive Desktop Loop

**Source:** Matthew directive (S142, 2026-03-23) — "I want to be able to use my macbook as much as I want to freely while you engage in the automated loop. I'm okay with letting you take control of the mouse and prompting for a few seconds if it means I can immediately go right back to Reddit or any other program while you're working."

**What Matthew wants:** The desktop autoloop (MT-22) should be virtually invisible during normal laptop use. The loop can briefly take mouse/keyboard control for the few seconds needed to spawn a new Claude Code session (activate app, click New Session, paste prompt, send), then immediately release control so Matthew can go right back to browsing, reading, or whatever he's doing. The rest of the time — while CCA is actually working — Matthew has full control of his machine.

**Core requirements:**
1. **Minimal takeover window**: Only grab mouse/keyboard for the absolute minimum time needed (activate + new session + paste + send = ~3-5 seconds max)
2. **Immediate release**: After the prompt is sent, immediately return focus to whatever app Matthew was using before
3. **No modal blocking**: Never leave Claude.app in the foreground waiting for input. Send prompt and get out.
4. **User-awareness**: Detect if Matthew is actively typing/clicking and delay the loop spawn by a few seconds until idle
5. **Foreground restore**: Save the frontmost app before activation, restore it after prompt send
6. **Status visibility**: Some non-intrusive way to know the loop is running (menu bar icon, tmux status, notification)

**Implementation approach (incremental):**
- Phase 1: Save/restore frontmost app around autoloop trigger (AppleScript: get frontmost app name, activate Claude, do work, activate saved app)
- Phase 2: Idle detection — wait for 2-3 seconds of no mouse/keyboard activity before triggering
- Phase 3: Menu bar status indicator or periodic ntfy.sh notification of loop health
- Phase 4: Keyboard shortcut to pause/resume loop without killing it

**Status:**
- Phase 1 COMPLETE (S142): save/restore frontmost app around autoloop trigger (~3-5s takeover)
- Phase 2 COMPLETE (S143): idle detection via CoreGraphics CGEventSourceSecondsSinceLastEventType. Waits for 3s idle before triggering. Configurable via CCA_IDLE_THRESHOLD/CCA_IDLE_TIMEOUT env vars. Fails open on timeout.
- Phase 3 COMPLETE (S144): ntfy.sh loop health notifications. `notify_loop_health()` (periodic low-priority ping) + `notify_loop_stopped()` (high-priority on crash). 30-min cooldown rate limiter (`CCA_NTFY_COOLDOWN_MIN`). +23 tests.
- Phase 4: TODO — keyboard shortcut to pause/resume loop

**Files:** `autoloop_trigger.py`, `desktop_automator.py`, `desktop_autoloop.py`, `context-monitor/session_notifier.py`

**Relationship:** Extends MT-22 (Desktop Autoloop). Part of "Get More Bodies" pillar.

---

## MT-36: Session Efficiency Optimizer — Quality-Preserving Speed

**Source:** Matthew directive (S143, 2026-03-23) — "a thorough but carefully constructed tool for all this optimization type deal... maintaining equal or greater quality production and output while optimizing coding, start up time for CCA, wrap up time for CCA, same thing for Kalshi bot chat if applicable"

**What Matthew wants:** A systematic tool/framework that measures and optimizes the time spent on session overhead (init, wrap, test runs, doc updates) and coding velocity WITHOUT sacrificing output quality. Applies to both CCA and Kalshi bot sessions.

**Core requirements:**
1. **Measure current baselines**: Time spent on /cca-init, /cca-wrap, test suites, doc reads, coding. Break down where time goes.
2. **Identify waste**: Which init/wrap steps take disproportionate time? Are any steps redundant? Can test runs be parallelized or cached?
3. **Optimize without quality loss**: Faster init (cached test results? incremental test runs?), leaner wrap (parallel doc updates?), smarter coding (fewer retry loops, better first-attempt code). Quality gates remain — tests must pass, docs must be accurate.
4. **Kalshi applicability**: Same analysis for /polybot-init, /polybot-auto, /polybot-wrap. Different session shape but same optimization principles.
5. **Dashboard/reporting**: Track efficiency metrics over time. Are sessions getting faster? Is quality (grade, test count, regressions) maintained?

**What this is NOT:**
- NOT about removing safety checks, tests, or documentation
- NOT about rushing through work at the cost of bugs
- NOT about cutting wrap steps that produce valuable data (journal, learnings, etc.)

**Technical approach (incremental):**
- Phase 1: Instrumentation — time every major step in init/wrap/auto, produce per-session timing breakdown
- Phase 2: Analysis — identify top 3 time sinks, propose optimizations with quality impact assessment
- Phase 3: Implement quick wins — parallel test runs, incremental testing, cached reads, smarter doc updates
- Phase 4: Kalshi session optimization — apply same analysis to polybot sessions
- Phase 5: Dashboard — track efficiency metrics, quality metrics, and their correlation over time

**Existing infrastructure to leverage:**
- `overhead_timer.py` — already measures coordination overhead
- `session_outcome_tracker.py` — tracks planned vs completed tasks, auto-grades
- `wrap_tracker.py` — session quality trends
- `hook_profiler.py` — hook chain latency diagnostics
- `session_pacer.py` — session pacing for autonomous runs

**Status:** NOT STARTED — created S143 per Matthew directive.

**Relationship:** Part of "Get Smarter" pillar — self-optimizing sessions.

---

## MT-37: AI-Driven Investment Research & Portfolio Intelligence (Long-Term)

**Source:** Matthew directive (S148, 2026-03-24) — "need to eventually seek investments/stock long-term safe savings with ETFs whatever the objective recommendation here... CCA developing the ability to look into objective AI algo investing elite level with significant academic research, economic financial data EVERYTHING related to this very long-term conquest"

**What Matthew wants:** A comprehensive, research-heavy capability for CCA to provide objective, academically-grounded investment intelligence. Long-term safe savings via ETFs, index funds, and algorithmic portfolio construction — built on the same rigor standard as the Kalshi bot (structural basis + math validation + backtesting). This is NOT a trading bot — it's a research and recommendation engine for long-term wealth building.

**Core scope (8 pillars):**

1. **Academic Foundation** — Survey the quantitative finance literature: Modern Portfolio Theory, Fama-French factor models, Black-Litterman, risk parity, momentum/value/quality factors, tax-loss harvesting theory. Every recommendation traces to peer-reviewed research. No speculation, no vibes.

2. **ETF/Index Fund Universe** — Build a structured database of ETFs and index funds: expense ratios, tracking error, AUM, sector/geographic exposure, factor loadings. Objective comparison tooling. Eliminate high-fee funds that underperform benchmarks.

3. **Portfolio Construction** — Implement and backtest portfolio allocation strategies: mean-variance optimization, risk parity, equal weight, target-date glide paths, Kelly criterion for long-horizon investing. Compare Sharpe ratios, max drawdown, CAGR across strategies.

4. **Economic Data Integration** — Ingest and analyze macro indicators: Fed funds rate, CPI, GDP, unemployment, yield curve, corporate earnings. Regime detection (expansion/contraction/crisis) that feeds portfolio allocation. Use FRED, BLS, BEA data APIs.

5. **Risk Analysis** — Tail risk measurement (CVaR, VaR), correlation regime shifts, drawdown analysis, sequence-of-returns risk for retirement planning. Monte Carlo simulations for retirement projections. Stress testing against historical crises (2008, 2020, dot-com).

6. **Tax Optimization** — Tax-loss harvesting strategies, Roth vs traditional analysis, asset location optimization (which assets in which account types), capital gains management. Country-specific (US-focused initially).

7. **Reporting & Visualization** — Leverage MT-32 infrastructure for professional portfolio reports, allocation pie charts, historical performance charts, risk dashboards. Make complex financial data accessible.

8. **Self-Learning Integration** — Feed portfolio performance data back into the self-learning pipeline. Track recommendation accuracy over time. Use the same principle_registry/pattern_registry architecture from MT-28.

**What this is NOT:**
- NOT a day-trading or active trading system (that's the Kalshi bot)
- NOT financial advice (always disclaim — Matthew makes his own decisions)
- NOT speculative (no crypto recommendations, no options, no leveraged products unless academically justified)
- NOT a replacement for a financial advisor (augmentation, not replacement)

**Research needed (EXTENSIVE — this is primarily a research MT):**
- Academic papers: Fama-French, Carhart 4-factor, AQR research, Vanguard research papers, Dimensional Fund Advisors research
- Data sources: FRED API, Yahoo Finance, Alpha Vantage, Quandl, SEC EDGAR
- Existing tools: QuantLib, zipline, backtrader, PyPortfolioOpt, Riskfolio-Lib
- Books: "A Random Walk Down Wall Street", "The Intelligent Investor", "Quantitative Portfolio Management" (Isichenko), "Expected Returns" (Ilmanen)
- Subreddits: r/Bogleheads, r/investing, r/financialindependence, r/portfolios, r/quantfinance

**Phased approach (very long-term, no rush):**
- Phase 1: Deep academic research survey — produce RESEARCH.md with literature review, methodology comparison, factor model summary
- Phase 2: Data pipeline — FRED API integration, ETF universe builder, basic factor loading calculator
- Phase 3: Portfolio constructor — implement 3-5 allocation strategies with backtest framework
- Phase 4: Risk analysis toolkit — VaR/CVaR, Monte Carlo, stress testing
- Phase 5: Tax optimization layer — asset location, TLH simulation
- Phase 6: Reporting integration — wire into CCA report/dashboard infrastructure
- Phase 7: Self-learning feedback loop — track recommendations vs outcomes

**Relationship to existing CCA infrastructure:**
- Uses self-learning pipeline (MT-28) for outcome tracking
- Uses design-skills (MT-32) for visualization
- Uses research infrastructure (paper_scanner.py, paper_digest.py) for academic papers
- Leverages Kalshi bot experience with probability, Kelly criterion, regime detection
- Cross-chat coordination: investment insights may inform Kalshi macro regime detector

**Status:** IDEA LOGGED (S148) — Long-term, research-first. Do NOT start building until Phase 1 research is complete. No rush — Matthew directive.

---

---

## MT-38: Peak/Off-Peak Token Budget System

**Source:** Matthew directive (S154) — observed Anthropic rate limit instability affecting all plan tiers
**What Matthew wants:** All CCA and Kalshi chats automatically adjust token usage intensity based on time of day. More conservative during peak Claude Code usage hours (US business hours), full power during off-peak/overnight/weekends. This persists permanently — not tied to any specific Anthropic promotion.

**Why it matters:** Rate limits are a real constraint. Heavy usage during peak hours risks hitting limits faster when server load is highest. Shifting expensive work to off-peak windows maximizes throughput per dollar.

**Phase 1 (COMPLETE — S154):** Global rule deployed to `~/.claude/rules/peak-offpeak-budgeting.md`. Defines PEAK (8AM-2PM ET, 60%), SHOULDER (6-8AM/2-6PM ET, 80%), OFF-PEAK (6PM-6AM ET + weekends, 100%). All chats read this immediately.

**Phase 2:** Build `token_budget.py` utility that:
- Detects current time window
- Returns budget percentage and behavioral guidelines
- Integrates with `/cca-init` and `/polybot-init` briefings
- Provides `get_budget()` API for other tools

**Phase 3:** Hook integration — PreToolUse hook that warns/blocks expensive operations during PEAK:
- Block agent spawns during PEAK
- Warn on agent spawns during SHOULDER
- No restrictions during OFF-PEAK

**Phase 4:** Autoloop scheduling — autoloop prefers off-peak windows, defers heavy tasks during peak.

**Status:** Phase 1 COMPLETE (S154). Rule active globally. Phase 2-4 are enhancement.

---

### Scoring Rules

1. **After working on a task:** Update `get_known_tasks()` in `priority_picker.py`, run `python3 priority_picker.py table`.
2. **New tasks:** Add to `get_known_tasks()` with base_value assigned. ADHD protocol: log but don't start until it rises naturally.
3. **Re-rank every session:** Run `python3 priority_picker.py recommend` at session start.
4. **Graduation:** When all phases complete, remove from `get_known_tasks()`, add to Completed table.
5. **Self-resolution scan:** Every 5 sessions, check if blocked MTs are solvable. Run `python3 priority_picker.py stagnating`.
6. **Stagnation review:** Tasks flagged as stagnating need a decision: (A) work them this session, (B) reduce base_value, or (C) archive.
