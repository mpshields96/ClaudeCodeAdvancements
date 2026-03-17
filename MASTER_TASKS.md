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

**Status:** Not started. Infrastructure exists (nuclear_fetcher.py, subreddit_slug(), namespaced reports). Needs profile system + quick-scan mode.

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

## Priority Order

1. ~~**MT-0** (Kalshi self-learning integration)~~ Phase 1 COMPLETE — schema + patterns + tests shipped. Phase 2 = deploy to polybot
2. ~~**MT-2** (mermaid diagrams)~~ COMPLETE
3. ~~**MT-4** (design vocabulary)~~ COMPLETE
4. ~~**MT-3** (virtual design team)~~ COMPLETE
5. **MT-7** (trace analysis self-learning) — highest-impact new task, infrastructure exists, both CCA + Kalshi benefit
6. **MT-6** (nuclear at will) — infrastructure exists, needs profiles + quick-scan mode
7. **MT-8** (iPhone remote control) — needs research phase first
8. **MT-1** (Maestro visual grid) — largest, blocked on macOS SDK, may need custom build
9. **MT-5** (Claude Pro bridge) — future, needs research on Pro's capabilities
