# Kalshi Bot — Research & Self-Learning Prime Directive
# This document is permanent and authoritative. All Claude Code sessions
# (Kalshi main, Kalshi research, CCA, future chats) MUST reference this.
# Last updated: 2026-03-18 (Session 45, per Matthew's explicit directive)

---

## The One Objective: SMARTER AND MORE PROFITABLE

The bot's self-learning/self-improvement mechanism exists for ONE purpose:
**produce a smarter and more profitable bot.**

Not a more complex bot. Not a more academic bot. Not a bot that scans
more data. SMARTER and MORE PROFITABLE.

---

## Three Pillars of Self-Learning (ALL must be pursued)

### Pillar 1: Perfect the Current Engine
Use live bet results to automatically improve signals, guards, calibration,
and win rates. The Bayesian model, guards, and Page-Hinkley are EXAMPLES
of this pillar — they are not the whole pillar.

**What's working today:**
- Bayesian update loop (Dims 2-4): After every live drift bet settles,
  `settlement_loop` calls `BayesianDriftModel.update()` which adjusts
  the posterior over the sigmoid's intercept and slope. At n=301+ it's
  active — the drift strategies are rewriting their own prediction
  function from their own betting history, autonomously.
- Auto-guard discovery (Dim 1): Nightly DB scan finds market+direction+price
  combos that lose money at scale and blocks them permanently. The bot
  learned two guards from its own losses.
- Page-Hinkley detection (Dim 7): CUSUM sequential test watching whether
  a strategy's win rate is drifting downward over time.

**What's NOT yet being analyzed from sniper data (the gap):**
- Which 90-95c sub-buckets are trending toward degradation (Page-Hinkley
  only runs on drift strategies, not the sniper)
- Whether the 90-95c zone itself is shifting (is 91-92c noisier than 93-95c?)
- Using sniper results to recalibrate entry timing vs "too tight" markets
- Whether the sniper's edge is seasonal, correlated with BTC volatility,
  or eroding

**Highest-leverage next step:** Apply Page-Hinkley to the sniper's bucket-level
WR trends — detect sniper edge erosion automatically, not just drift degradation.

### Pillar 2: Deep Research
Academic papers (arXiv/SSRN), mathematical models, probability theory, Kelly
extensions, drift detection, calibration theory. Prove with math + DB backtest
before building.

**What "research" means — and does NOT mean:**
- DOES mean: Designing a smarter bot. Discovering and validating new mathematical
  approaches. Finding papers with proven results applicable to prediction markets.
  Building new signal generation methods backed by statistical rigor.
- DOES NOT mean: Daily news scans. Checking what happened yesterday. Routine market
  monitoring. That's operational, not research.

**Standard for new edges (non-negotiable):**
Structural basis + math validation + DB backtest + p-value. No exceptions.

### Pillar 3: Expand Beyond Current Parameters
Explore new edges, market types, bet structures of equal or greater quality to
the sniper. The bot must not be frozen.

**What "equal or greater quality" means:**
Not necessarily the same 97% WR or the same sniper-style approach. Different bet
types and strategies have different metrics. What matters is the same LEVEL of
success and profitability — consistent, reliable, positive-EV performance.
Win rates and metrics can change depending on the type of betting.

**The bot's growth path:**
USE the sniper bets and Bayesian model + PERFECT them + GROW beyond them with more.

---

## Financial Targets

1. **SELF-SUSTAINING:** ~250 USD/month to cover Claude Max20 subscription
2. **COMPOUNDING PASSIVE INCOME:** A few hundred USD/month and growing

The prime directive is to become self-sustaining first, then compound.

---

## What Self-Improvement Currently Means (Honest Assessment)

The drift strategies update their own signal generation from live data, and the
bot auto-discovers negative-EV buckets to block. The sniper runs on fixed rules
informed only by guard logic.

The compounding mechanism is: sniper earns reliably (~97% WR on guarded buckets),
drift strategies incrementally self-correct via Bayesian updates, and new losing
patterns get auto-guarded. Each session the guard stack grows and the drift
posteriors narrow.

---

## CCA's Role

CCA supports this mission through:
- Autonomous scanning of trading subreddits (r/algotrading, r/Kalshi, r/polymarket)
- Academic paper discovery (Semantic Scholar + arXiv)
- GitHub repo intelligence for trading tools
- Self-learning architecture (journal.py, reflect.py, improver.py) — R&D lab
- KALSHI_INTEL.md bridge: CCA writes findings, Kalshi chats consume

---

## Matthew's Directive (verbatim intent, Session 45)

"The self-learning/improvement mechanism strives to produce a smarter and a more
profitable bot. It utilizes the data and results from daily bets to make it smarter
and more profitable, it engages in deep research through academic papers, other high
quality forms of analysis, different theories and mathematical applications relevant
to probabilities and betting and coding but overall improvement. Smarter and more
profitable. Along with the other two components of the research and the
self-learning/improvement, it also means exploring and expanding beyond current
parameters, like perfecting the sniper bets and the Bayesian model but then still
looking into other sources/markets/edges/mathematical models. Our bot shouldn't be
frozen in just using the sniper bets and Bayesian model, we're using them, perfecting
them, but growing and progressing in them and with more."

---

## For All Chats: What This Means For You

**Kalshi Research Chat:** Your job is NOT daily scans. Your job is designing the
smarter, more profitable bot. Bayesian updating is one step, not the destination.
Pursue all three pillars simultaneously.

**Kalshi Main Chat:** Use the guards, signals, and improvements that research produces.
Report outcomes back for the feedback loop. Flag when things aren't working.

**CCA Chat:** Find high-quality trading papers, tools, and approaches through autonomous
scanning. Serve findings via KALSHI_INTEL.md. Build self-learning infrastructure.

**Any Future Chat:** Read this file first. The objective is SMARTER AND MORE PROFITABLE.
Everything else is a means to that end.
