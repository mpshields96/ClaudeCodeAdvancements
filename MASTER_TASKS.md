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

**Status:** Architecture designed in CCA. Ready for adaptation to trading domain. Multi-session implementation.

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

**Status:** Ready to implement. Low complexity. Good gsd:quick target.

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

**Status:** Ready to implement. Medium complexity.

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

**Status:** Ready to implement. Enhances MT-2 and MT-3.

---

## Priority Order

1. **MT-0** (Kalshi self-learning integration) — BIGGEST, highest stakes, proven architecture ready to deploy
2. **MT-2** (mermaid diagrams) — smallest, most immediately useful, already in spec rules
3. **MT-4** (design vocabulary) — enhances spec:design, low effort
4. **MT-3** (virtual design team) — medium effort, high value for quality
5. **MT-1** (Maestro visual grid) — largest, blocked on macOS SDK, may need custom build
6. **MT-5** (Claude Pro bridge) — future, needs research on Pro's capabilities
