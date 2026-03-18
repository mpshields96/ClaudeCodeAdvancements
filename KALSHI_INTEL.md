# Kalshi/Trading Intelligence — Cross-Chat Bridge
# Last updated: 2026-03-17 (Session 31)
#
# THREE-CHAT BRIDGE PROTOCOL:
# 1. CCA (this project) → WRITES intel to this file via autonomous scanning
# 2. Kalshi Research Chat → READS this file, picks up intel, uses for bot improvement
# 3. Kalshi Main Chat → READS this file for awareness of new capabilities/findings
#
# CCA operates: nuclear scans on trading subs, GitHub repo evaluation, academic research
# Kalshi Research: uses findings to improve bot, build Bayesian model, self-learning loop
# Kalshi Main: executes improved strategies, reports outcomes back
#
# COMMUNICATION PROTOCOL:
# - CCA appends new intel to "New Intel (Unprocessed)" section
# - Kalshi Research reads, acts on it, moves processed items to "Processed Intel"
# - If Kalshi Research needs specific research, add to "Research Requests" section
# - CCA checks "Research Requests" at session start and prioritizes those topics

---

## Self-Learning Infrastructure Ready for Adoption

CCA has built and validated a self-learning system that the Kalshi bot can adopt.
All code lives in `/Users/matthewshields/Projects/ClaudeCodeAdvancements/self-learning/`.

### What's Available

| Component | File | What It Does |
|-----------|------|-------------|
| Trading Event Schema | `journal.py` | 6 trading event types: bet_placed, bet_outcome, market_research, edge_discovered, edge_rejected, strategy_shift |
| Trading Metrics | `reflect.py` → `get_trading_metrics()` | PnL tracking, win rate, by-market-type and by-strategy breakdowns, research effectiveness |
| Trading Pattern Detectors | `reflect.py` | 4 detectors: losing_strategy, research_dead_end, negative_pnl, strong_edge_discovery |
| Trace Analyzer | `trace_analyzer.py` | RetryDetector, WasteDetector, EfficiencyCalculator, VelocityCalculator — works on any transcript JSONL |
| QualityGate | `improver.py` | Geometric mean scoring (Nash 1950). Any zero metric tanks composite score. Prevents Goodhart's Law gaming. |
| Improvement Proposals | `improver.py` | Auto-generates improvement proposals from trace patterns. Risk classification: LOW/MEDIUM/HIGH. |
| Strategy Tuning | `strategy.json` | Bounded parameter tuning with safety rails. Min sample N=20 before auto-adjustment. |

### How to Adopt

1. **Journal logging** (~0 tokens): Import journal.py event schema, log bet_placed/bet_outcome events as JSONL
2. **Pattern detection** (rule-based, no LLM): Run reflect.py trading detectors on journal data
3. **Trace analysis**: Run trace_analyzer.py on Kalshi session transcripts — find retry loops, wasted reads, efficiency
4. **QualityGate**: Use geometric mean scoring when evaluating strategy changes — any dimension at zero blocks the change
5. **PROFIT IS THE ONLY OBJECTIVE** — the system optimizes for net profit, never break-even or theoretical elegance

---

## Trading-Relevant Reddit Findings (Food Dishes)

### High-Priority Dishes

**PMXT — Free Polymarket Orderbook Data** (680pts, r/algotrading)
- github.com/pmxt-dev/pmxt — every orderbook event captured, dumped hourly, Parquet format
- archive.pmxt.dev/Polymarket — free historical data
- Kalshi data coming in Part 2
- DomeAPI=$40/mo, Telonex=$79/mo — PMXT is free
- adanos.org/polymarket-stock-sentiment for sentiment
- https://www.reddit.com/r/algotrading/comments/1rdhw2n/

**Kalshi-Polymarket Arbitrage Bot** (369pts, r/algotrading)
- github.com/realfishsam/prediction-market-arbitrage-bot — open source
- Strategy: buy YES on one, NO on other when spread widens
- Key criticism: Kalshi fees eat most 2c spread, legging risk, liquidity risk
- Comment: user turned $250 to $5k on Kalshi SPX hourly markets in 2 days
- Polymarket US app coming with API access
- pmxt library: unified API for prediction markets
- https://www.reddit.com/r/algotrading/comments/1qebxud/

**5-cent Arbitrage Spreads** (142pts, r/algotrading)
- More arb examples from same PMXT author
- Security warning: some open-source prediction market repos contain private key exfiltration code
- Claude Code good at catching this (content_scanner.py already detects)
- desolstice comment: 0.3% per 15-min interval on Kalshi, 95% win rate but 5% losses > gains
- Needs safeguards
- https://www.reddit.com/r/algotrading/comments/1q83w3d/

**Polymarket incrementNonce() Exploit Detector** (r/algotrading)
- Nonce Guard tool detects ghost fills where bad actors invalidate losing orders
- MIT licensed
- Directly relevant to Polymarket bot safety
- https://www.reddit.com/r/algotrading/comments/1rb6qay/

**Mean Reversion Scalping Improvements** (r/algotrading)
- Parallel parameter sets, pyramiding entries, ATR-based regime filtering
- High-quality comments on volatility regime detection, time-of-day filtering, correlation monitoring
- https://www.reddit.com/r/algotrading/comments/1rtepah/

### Reference Dishes (Read, Don't Build)

**40+ Algorithmic Trading Strategies** (534pts, r/algotrading)
- Comprehensive list of basic strategies
- https://www.reddit.com/r/algotrading/comments/1naoem2/

**VEI Volatility Expansion Signal** (436pts, r/algotrading)
- Python source code included
- https://www.reddit.com/r/algotrading/comments/1phv4zz/

**Multi-Agent AI Trading System** (188pts, r/algotrading)
- PrimoAgent: 4 LangGraph agents (data, technical, NLP, portfolio)
- Requires 4 APIs — heavy dependency
- https://www.reddit.com/r/algotrading/comments/1nf6ghg/

**Automated Research Agent for Stock Analysis** (183pts, r/algotrading)
- Quality evaluator loop: if analysis weak, auto-fetches more data and rebuilds
- PocketQuant: playbooks per sector
- https://www.reddit.com/r/algotrading/comments/1l82has/

### Critical Warning Dishes

**LLMs Burned Money in Prediction Arena** (167pts + 256pts, r/algotrading)
- predictionarena.ai competition — ALL LLMs lost money
- Gemini 3 Pro lost 30%
- Key insight: LLMs encode "midwit consensus" which is already priced in
- Better use: alternative data processing and regime detection, NOT raw prediction
- "Brought an LLM to an ML fight"
- Implication: Kalshi bot should use LLMs for research/analysis, not direct price prediction

---

## CCA Autonomous Scanning Status

CCA now has autonomous scanning infrastructure (MT-9 + MT-11):
- `autonomous_scanner.py`: picks which subreddits to scan, enforces safety, produces reports
- `github_scanner.py`: evaluates GitHub repos by metadata without cloning
- Trading subreddits in scan queue: r/algotrading, r/Kalshi, r/polymarket, r/investing, r/stocks, r/SecurityAnalysis, r/ValueInvesting, r/Bogleheads
- **NEW (Session 31)**: `/cca-nuclear autonomous` mode auto-picks highest-priority sub + `--domain trading` for targeted scans
- CCA scans run as part of /cca-auto sessions and append findings here

---

## Research Requests (Kalshi → CCA)

_Kalshi Research Chat: add requests here. CCA will prioritize scanning for these topics._

| Priority | Topic | Context | Requested By | Status |
|----------|-------|---------|-------------|--------|
| HIGH | Bayesian updating for prediction markets | Research chat building Bayesian model for bet sizing/probability | Kalshi Research | OPEN |
| HIGH | Sniper bet timing patterns | Statistical analysis of optimal entry timing for high-probability events | Kalshi Research | OPEN |
| MEDIUM | Market microstructure for event markets | How orderbook depth, spread dynamics differ from traditional markets | Kalshi Research | OPEN |

_CCA: When you see OPEN requests, use `/cca-nuclear autonomous --domain trading` or targeted web searches to find relevant intel. Move to DONE when findings are appended above._

---

## New Intel (Unprocessed)

_CCA appends new findings here. Kalshi Research processes them and moves to "Processed Intel" below._

(No new unprocessed intel at this time — run `/cca-nuclear autonomous --domain trading` to generate)

---

## Processed Intel

_Kalshi Research: move items here after incorporating into bot strategy/code._

(Empty — Kalshi Research has not yet processed any items from this bridge)
