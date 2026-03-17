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

**Status:** Phase 1 COMPLETE (Session 21). Trading domain schema built in CCA self-learning module:
- 6 new event types: bet_placed, bet_outcome, market_research, edge_discovered, edge_rejected, strategy_shift
- `get_trading_metrics()` with PnL tracking, win rate, by-market-type and by-strategy breakdowns, research effectiveness
- 4 trading pattern detectors: losing_strategy, research_dead_end, negative_pnl, strong_edge_discovery
- Trading section in strategy.json with bounded auto-adjust params
- 24 new tests (75 total self-learning)
- Phase 2: Deploy to polymarket-bot (requires cross-project work)

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

**Status:** Blocked on macOS 15.6 beta SDK. Check for new releases each session.

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

**Status:** Not started. Research complete (ACE reviewed, pattern understood).

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

**Status:** Not started. Requires MT-6 (nuclear at will profiles) as prerequisite infrastructure.

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

**Status:** Not started. Depends on MT-7 (trace analysis) for the observation layer.

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

**Status:** Not started. Partially enabled by MT-9 infrastructure.

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

**Status:** Not started. Needs Semantic Scholar + arXiv API research.

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

**Status:** Not started. Needs Xcode + environment verification + Reddit/GitHub research.

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

**Status:** Not started. Depends on MT-6 (profiles) for infrastructure.

---

## Priority Order

**COMPLETED:**
1. ~~**MT-0** (Kalshi self-learning integration)~~ Phase 1 COMPLETE — Phase 2 = deploy to polybot
2. ~~**MT-2** (mermaid diagrams)~~ COMPLETE
3. ~~**MT-4** (design vocabulary)~~ COMPLETE
4. ~~**MT-3** (virtual design team)~~ COMPLETE

**ACTIVE — Highest Impact:**
5. **MT-7** (trace analysis) — foundation for MT-10, both CCA + Kalshi benefit. Research DONE (Session 25).
6. **MT-10** (YoYo self-learning loop) — the master pattern; depends on MT-7
7. **MT-9** (autonomous subreddit intelligence) — force multiplier; depends on MT-6
8. **MT-6** (nuclear at will) — prerequisite for MT-9 and MT-14

**ACTIVE — High Value:**
9. **MT-11** (GitHub repo intelligence) — extends MT-9 to code repos
10. **MT-12** (academic paper integration) — reputable sources for real improvements
11. **MT-14** (re-scan previously scanned subs) — keep intelligence current
12. **MT-8** (iPhone remote control) — immediate productivity gain
13. **MT-13** (iOS app development) — new capability domain

**FUTURE:**
14. **MT-1** (Maestro visual grid) — blocked on macOS SDK
15. **MT-5** (Claude Pro bridge) — needs research
16. **MT-15** (detachable chat tabs) — Anthropic feature request: drag CC desktop chats into separate windows like Chrome/Arc tabs. Solves the "pauses work when not focused" ADHD-hostile behavior.
