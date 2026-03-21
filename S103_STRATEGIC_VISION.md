# S103 Strategic Vision — Matthew's Master Direction
# Documented 2026-03-21, Session 103
# Source: Matthew's direct input + Reddit intelligence from 7 reviewed posts
#
# This document captures Matthew's comprehensive vision for CCA's future.
# Each theme maps to one or more proposed Master Tasks.
# Implementation: slow, incremental, quality-first. Never sacrifice quality for speed.

---

## Guiding Principles (Matthew-stated, S103)

1. **Quality over speed** — Never sacrifice output quality for the sake of faster delivery.
2. **Grow properly and safely** — Full process: objective planning, proper production, incremental validation.
3. **Token-conscious** — Optimize usage without degrading output quality. Equal or greater quality always.
4. **Safety-first** — Avoid all rat poison, malware, personal info exposure, financial risk.
5. **Long-term compounding** — Short-term: self-sustaining income. Long-term: passive income + investments.
6. **ABSOLUTE MACHINE SAFETY** — Matthew's MacBook must NEVER break, NOTHING must break, personal info and money must NEVER be stolen. This is universal across all CCA work, all MTs, all autonomous operations. Every tool, script, hook, and agent must be designed with this constraint as non-negotiable. See CLAUDE.md Cardinal Safety Rules 1-7.

---

## Theme 1: Kalshi Bot Financial Profitability (HIGHEST PRIORITY)

**Goal:** Self-sustaining income to cover Claude subscriptions, then compounding passive income.

**Financial targets (ordered):**
- Milestone A: Cover Claude Max 5x subscription ($125/mo)
- Milestone B: Cover Claude Max 20x subscription ($250/mo)
- Milestone C: Compounding passive income (few hundred USD/mo and growing)
- Milestone D (long-term): Transition proven strategies to investments/stocks

**What CCA's role is:**
- Build smarter self-learning (YoYo improvements) that feeds back into bot profitability
- Academic research pipeline (papers, probability theory, Bayesian methods, market conditions)
- Cross-chat intelligence that actually improves bot ROI
- Signal detection: quickly adapt/read/analyze/respond to prediction markets and betting conditions

**What this is NOT:**
- CCA does not directly trade. CCA researches, builds tools, and feeds intelligence to Kalshi chats.
- CCA builds the infrastructure; Kalshi bot makes the decisions.

**Relationship to existing MTs:**
- MT-0 (Kalshi self-learning) covers Phase 1 of this
- This vision expands MT-0 significantly with market adaptability, academic depth, and investment transition

---

## Theme 2: UI/Visual/Graphics Capabilities

**Goal:** Exponentially smarter and more capable visual output.

**Specific capabilities wanted:**
- Diagrams (architecture, flow, sequence)
- Charts (data visualization, performance metrics, trading analytics)
- Figures (publication-quality for academic presentations)
- Interactive dashboards (beyond current HTML dashboard)

**Relationship to existing MTs:**
- MT-17 (Design/Reports) covers basic reports/slides/dashboards — COMPLETED
- This vision goes significantly deeper: publication-quality, trading-specific, interactive

---

## Theme 3: Mobile Remote Control v2

**Goal:** Seamless iPhone app-like experience for communicating with Claude Code sessions.

**Specific requirements:**
- Hop on from phone, chat with ClaudeCode chat easily
- Leave for minutes to an hour, hop right back in seamlessly
- Memory functions across mobile sessions
- NOT ntfy (Matthew: "ntfy doesn't seem optimal")
- Look at how people develop better iOS-ClaudeCode communication

**Reddit intelligence (directly relevant):**
- Post #6 (364 upvotes, 98%): Official Anthropic feature — Telegram and Discord channels for Claude Code
- This is a native MCP integration, not a hack. Official support.
- Users report it works well for monitoring long tasks from phone
- Bug reported: context loss requiring computer restart (needs investigation)
- Community already had custom solutions (Openclaw, tmux daemons) — Anthropic productized it

**Technical path:**
- Evaluate official Telegram/Discord channels MCP
- Compare against current ntfy setup
- Consider Signal support (requested by community but not yet available)
- Build session persistence layer for seamless hop-on/hop-off

---

## Theme 4: Data Analysis (Excel, PowerPoint, etc.)

**Goal:** Enhanced ability to work with data in professional formats.

**Specific tools mentioned:**
- Excel (analysis, formatting, formulas, charts)
- PowerPoint (presentations)
- General data analysis capabilities

**Note:** CCA already has MCP tools for XLSX and PPTX. This theme is about making them work BETTER, not just "exist."

---

## Theme 5: PowerPoint Presentation Generator

**Goal:** Perfect powerpoint generator specific to Matthew's style and preferences.

**Context:**
- Matthew has Grand Rounds presentations (psychiatry)
- Psychopharmacology lecture powerpoints
- These are created in Claude Pro currently
- Want to bring that capability into CCA/Claude Code
- Must NOT produce "AI slop" — must match Matthew's actual presentation style

**Status:** WAITING for further info from Matthew before defining implementation.

**What this means:**
- Study Matthew's existing presentations to learn his style
- Build a presentation generator skill/template that encodes his preferences
- Similar pattern to Reddit Post #1 (infosec worker who encoded his document formats into Skills)

---

## Theme 6: Self-Learning / YoYo Improvements

**Goal:** Significant improvements in self-learning across multiple facets.

**What "multi-functional" means:**
- Not just CCA operational metrics — extend to trading domain
- Not just pattern detection — predictive capability
- Cross-domain learning: what works in CCA self-improvement informs Kalshi self-improvement
- Adaptive mutation (Sentinel-style): analyze failures, generate counter-strategies

**Relationship to existing work:**
- journal.py, reflect.py, strategy.json, improver.py — all built
- MT-0 Phase 1 deployed trading domain schema
- Need: closed-loop feedback from Kalshi outcomes → research prioritization

---

## Theme 7: Prediction Markets / Trading / Economics

**Goal:** CCA becomes the academic research + analysis backbone for trading intelligence.

**Specific capabilities:**
- Academic research: papers on prediction markets, Bayesian methods, probability theory
- Market condition analysis: read and interpret market conditions quickly
- Adaptation speed: respond to changing market conditions faster
- Statistical rigor: proper significance testing, sample size guards
- Economics knowledge: macro/micro factors affecting prediction markets

**Reddit intelligence (relevant):**
- Post #3 (345 upvotes): Satellite image analysis for hedge fund signals — shows Claude Code CAN build financial analysis pipelines. The moat is data, not engineering.
- Post #3 comments: Hedge funds use web scraping + credit card data now, satellite is outdated. Real alpha is in data access, not algorithms.
- Existing CCA work: MT-12 academic paper scanner, cross-chat SPRT analysis, confidence calibrator

---

## Theme 8: Investments / Stocks (Long-Term)

**Goal:** If Kalshi proves significant profitability over months, transition to long-term, safer, more profitable venues.

**Timeline:** This is explicitly long-term. Not for immediate implementation.
**Prerequisite:** Months of proven Kalshi profitability first.
**What "safer" means:** Diversified investments, lower-risk, compounding over time.

---

## Theme 9: CCA Nuclear Enhancement

**Goal:** Better deep-diving of Reddit and GitHub for high-quality posts.

**Specific improvements wanted:**
- Better signal-to-noise filtering
- APF currently at 22.7% (target 40%) — "Other" category at 9.7% drags overall
- Better frontier tagging to reduce misclassification
- Same approach for GitHub trending repos

**Safety requirements (Matthew-explicit):**
- Avoid ALL rat poison, viruses, malware
- Never cost personal info or money
- Same safety standard for GitHub scanning

---

## Theme 10: Token Optimization

**Goal:** Reduce token usage while maintaining or improving output quality.

**Constraint:** "Avoiding any optimization that worsens our output" — quality floor is current quality level.
**Approach:** Measure first, optimize second. Never blind optimization.

---

## Theme 11: Mobile Redefinition

**Goal:** Replace ntfy with a better mobile communication system.

**This overlaps with Theme 3 (Mobile Remote Control v2).**
**Key insight from Reddit:** Official Telegram/Discord channels now exist. This is the path.

---

## Theme 12: Claude Cowork Integration

**Goal:** Utilize Claude Cowork if objectively useful for CCA workflows.

**What Cowork offers:**
- Background agents that run tasks while you work
- Scheduled recurring tasks
- Agent orchestration without manual supervision

**Evaluation needed:** Is Cowork objectively better than our current hivemind/worker pattern?

---

## Theme 13: Claude Pro + Claude Code Bridge (Hivemind)

**Goal:** Bridge between Claude Pro (web/desktop chat) and Claude Code for a hivemind experience.

**What this enables:**
- High-level strategy discussions in Claude Pro (Matthew's natural thinking space)
- Implementation execution in Claude Code
- Shared context between the two environments
- Extends MT-5 (Claude Pro bridge) and MT-21 (Hivemind coordination)

**Relationship to existing MTs:**
- MT-5 was partially self-resolved (Remote Control + Chrome extension exist)
- MT-21 is at Phase 2 (2-chat proven). Phase 3 would be 3-chat.
- This vision goes further: Pro + Code as a unified system, not just parallel chats

---

## Proposed New Master Tasks

Based on the above themes, the following new MTs are proposed (pending Matthew approval):

| MT | Theme | Name | Priority | Notes |
|----|-------|------|----------|-------|
| MT-23 | 3+11 | Mobile Remote Control v2 (Telegram/Discord) | HIGH | Replace ntfy, official Anthropic support |
| MT-24 | 2 | Visualization & Graphics Engine | MEDIUM | Diagrams, charts, publication-quality figures |
| MT-25 | 5 | Presentation Generator (Matthew's Style) | MEDIUM | WAITING on further info from Matthew |
| MT-26 | 7+8 | Financial Intelligence Engine | HIGH | Academic research + market analysis backbone |
| MT-27 | 9 | CCA Nuclear v2 (Enhanced Scanning) | MEDIUM | Better APF, safety, signal quality |
| MT-28 | 6 | Self-Learning v2 (Multi-Domain) | HIGH | Cross-domain YoYo, Sentinel adaptive mutation |
| MT-29 | 12+13 | Cowork + Pro Bridge Hivemind | MEDIUM | Evaluate Cowork, bridge Pro↔Code, extend MT-5/MT-21 |

**NOT proposed as new MTs (folded into existing):**
- Theme 1 (Kalshi profitability) → Extends MT-0 + MT-26
- Theme 4 (Data analysis) → Subsumed by MT-24 + MT-25
- Theme 8 (Stocks/investments) → Long-term phase of MT-26
- Theme 10 (Token optimization) → Ongoing operational concern, not MT-worthy

---

## Reddit Intelligence Summary (S103)

7 posts reviewed. Key takeaways:
1. Official Telegram/Discord remote control is HERE — direct replacement for ntfy
2. Skills architecture (encoding workflows) is a proven pattern we already use
3. Financial analysis pipelines via Claude Code are validated (satellite post)
4. Hook-based safety is the right approach (community consensus over YOLO)
5. Anti-sycophancy frameworks have demand (150 mental models post)
6. Monthly self-review of skills/instructions is a good maintenance pattern
