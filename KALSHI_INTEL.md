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
| HIGH | Bayesian updating for prediction markets | Research chat building Bayesian model for bet sizing/probability | Kalshi Research | FOUND — See calibration paper (292M trades) + Bayesian inverse problems paper above |
| HIGH | Sniper bet timing patterns | Statistical analysis of optimal entry timing for high-probability events | Kalshi Research | FOUND — See price convergence paper (Operations Research) above |
| MEDIUM | Market microstructure for event markets | How orderbook depth, spread dynamics differ from traditional markets | Kalshi Research | PARTIAL — Binary tree microstructure paper found, need more event-market specific |

_CCA: When you see OPEN requests, use `/cca-nuclear autonomous --domain trading` or targeted web searches to find relevant intel. Move to DONE when findings are appended above._

---

## New Intel (Unprocessed)

_CCA appends new findings here. Kalshi Research processes them and moves to "Processed Intel" below._

### [2026-03-17] Mean Reversion with IBS Filter — Kalshi-Applicable Pattern
**Source:** r/algotrading (219pts, 99 comments) — https://www.reddit.com/r/algotrading/comments/1rjvxjy/
**Relevance:** The IBS (Internal Bar Strength) concept — detecting when price closes in bottom 30% of daily range — maps to detecting "oversold" event markets on Kalshi where probability pricing has temporarily dipped below fair value.

Key findings:
- Entry: `close < 10d high - 2.5 * ATR` AND `IBS < 0.3` (close near daily low = weakness)
- Exit: `close > yesterday's high` (simple reversion confirmation)
- 70-75% win rate across SPY/QQQ/AAPL over 20 years, 2.0+ profit factor
- Only in market 16-25% of the time — capital efficient, fits Kalshi's selective sniper approach
- Best comment: sentiment filter (enter only when social media is unusually bearish) cut entries 30% but disproportionately removed losers
- Criticism: Sharpe 0.46, avg loss > avg profit — but 70% win rate compensates

**Kalshi application:** IBS-like indicators for event market contracts. When a YES contract drops to near its session low AND is in a pullback from recent highs, mean reversion probability increases. The "sentiment filter" idea is directly applicable — enter only when sentiment is oversold relative to actual probability.

### [2026-03-17] Pre-Market ML for Intraday Direction Prediction
**Source:** r/algotrading (199pts, 172 comments) — https://www.reddit.com/r/algotrading/comments/1rrbdx5/
**Relevance:** Pre-market feature engineering for predicting SPY direction. Kalshi has SPY intraday contracts.

Key findings:
- Features from 4:00-9:30 AM window only (pre-market volume, price action)
- Three ML classifiers across different time horizons
- Validated with Combinatorial Purged Cross-Validation (CPCV) — proper financial ML validation
- Important insight: "daytime returns on average are basically zero, all real money is made overnight" (academic backing)
- Confidence threshold gating: hides prediction below certain confidence to avoid anchoring bias
- Built with Claude/Cursor (vibecoded) — production-quality despite AI-assisted development

**Kalshi application:**
1. Pre-market features for SPY hourly contracts — the 4:00-9:30 window has genuine signal
2. CPCV validation method should be adopted for any Kalshi ML models (prevents lookahead bias)
3. Confidence gating: bot should only take bets above a confidence threshold, not every signal
4. Overnight drift research: gap fades as a Kalshi strategy for SPY contracts

### [2026-03-17] CRITICAL: Kalshi Calibration Paper (2026) — 292M Trades Analyzed
**Source:** arxiv.org/abs/2602.19520 — "Decomposing Crowd Wisdom: Domain-Specific Calibration Dynamics"
**Data:** 292 million trades across 327,000 binary contracts on Kalshi AND Polymarket
**Relevance:** DIRECTLY addresses the Bayesian model the research chat is building

Key findings:
- Calibration decomposed into 4 components: horizon effect, domain bias, domain-by-horizon interaction, trade-size scale
- These 4 factors explain 87.3% of calibration variance on Kalshi
- **PERSISTENT UNDERCONFIDENCE in political markets** — prices cluster toward 50% regardless of true probability
- Markets don't provide unbiased probability estimates — consumers MUST adjust for predictable biases
- Bayesian hierarchical model confirmed with 96.3% posterior predictive coverage

**Kalshi application:**
1. The bot's Bayesian model should incorporate domain-specific calibration adjustments
2. When market prices cluster near 50%, there's likely an exploitable underconfidence bias
3. Trade-size affects calibration differently by domain — the bot should factor this in
4. The paper provides the mathematical framework for exactly what the research chat is building

### [2026-03-17] CRITICAL: Prediction Markets as Bayesian Inverse Problems (2026)
**Source:** arxiv.org/abs/2601.18815 — "Uncertainty Quantification, Identifiability, and Information Gain"
**Relevance:** Mathematical framework for extracting signal from Kalshi price-volume histories

Key findings:
- Formulates prediction markets as Bayesian inverse problem: infer binary outcome Y from price-volume
- Works in log-odds space (same as logistic regression — natural for the bot's Bayesian model)
- Models informed traders, uninformed traders, heavy-tailed noise, and adversarial/manipulative flow
- Provides identifiability criteria: when can you actually extract signal vs when is inference ill-posed?
- Explicit regime detection: informative-and-stable vs noise-dominated regimes
- Stability diagnostics: how sensitive are your beliefs to price-volume perturbations?

**Kalshi application:**
1. The regime detection is directly useful — bot should only bet in "informative and stable" regimes
2. The log-odds framework aligns with MAP estimation the research chat is building
3. Trader type decomposition helps the bot understand when prices are driven by informed traders vs noise
4. The stability diagnostics can serve as a confidence filter (don't bet when inference is unstable)

### [2026-03-17] Price Convergence Near Expiration — Academic Backing for Sniper Timing
**Source:** arxiv.org/abs/2205.08913 — "Price Interpretability of Prediction Markets: A Convergence Analysis" (Operations Research)
**Relevance:** Directly validates the sniper bet strategy — prices become more accurate near expiration

Key findings:
- Time until expiration NEGATIVELY affects price accuracy as a forecasting tool
- Near-expiration prices are "reasonably well calibrated" while far-future prices show "significant bias"
- Favourite/longshot bias direction varies with time horizon
- Limiting price converges to geometric mean of agent beliefs in exponential utility-based markets
- Miscalibration can be exploited when trader has relatively low discount rate

**Kalshi application:**
1. **Validates sniper approach**: Waiting for near-expiration contracts to reach high probability is academically supported
2. **Calibration improves near expiry** — sniper bets taken in the last hour have better probability-price alignment
3. **Favourite/longshot bias**: At 90-95c, contracts may still be slightly mispriced relative to true probability — the sniper edge
4. **Geometric mean convergence**: When all informed traders agree, price converges to truth — sniper bets detect this convergence

### [2026-03-17] Prediction Market Industry Growth — Context for Kalshi
**Source:** Multiple industry reports (2025-2026)
- Kalshi: from 3.3% → 66% market share in 2024-2025, now $100B+ annualized volume
- Nasdaq requesting SEC approval for binary options on Nasdaq-100
- Cboe launching Mini-SPX prediction contracts Q2 2026
- ICE investing up to $2B in Polymarket
- These new entrants will increase liquidity and create new arbitrage opportunities

### [2026-03-17] Autonomous Scan: r/algotrading Full Results
**Scan stats:** 100 posts fetched, 46 safe, 12 NEEDLE, 32 MAYBE, 2 HAY
**Domain:** trading
**Notable other NEEDLEs not yet deep-read:**
- "I reverse-engineered the IB Gateway and rebuilt it in Rust for low latency" (176pts)
- "I backtested a 400K views YouTube trading strategy (BRUTAL results)" (403pts) — backtesting methodology
- "I ADMIT IT. I OVERFIT. I HAVE SELECTION BIAS." (515pts) — overfitting awareness (important for Bayesian model)

### [2026-03-17] Autonomous Scan: r/polymarket Results (Session 32)
**Scan stats:** 50 posts fetched, 4 NEEDLE, 40 MAYBE, 6 HAY
**Domain:** trading
**First scan of r/polymarket.** Mostly discussion/sentiment posts — lower technical signal than r/algotrading but useful for market structure awareness.

### [2026-03-17] GitHub Repo Intelligence: Trading/Prediction Market Repos (Session 32)
**Source:** MT-11 Phase 2 live GitHub API scans — NEW CAPABILITY
CCA can now autonomously search GitHub and evaluate repos by quality rubric.

**Kalshi-Relevant Repos Found:**

| Repo | Stars | Score | Notes |
|------|-------|-------|-------|
| `OctagonAI/kalshi-deep-trading-bot` | 126 | 73/100 | Python, Kalshi-specific deep trading bot — evaluate architecture |
| `llgpqul/polymarket-copy-trading-bot` | 836 | 87/100 | TypeScript, copy trading patterns |
| `haredoggy/Prediction-Markets-Trading-Bot-Toolkits` | 185 | 83/100 | Rust, multi-market toolkit |
| `Krypto-Hashers-Community/polymarket-kalshi-arbitrage-bot-15min-market` | 184 | 63/100 | TypeScript, 15min arb strategy |
| `infraform/polymarket-kalshi-arbitrage-bot` | 174 | 63/100 | TypeScript, Kalshi-Polymarket arb |
| `kernc/backtesting.py` | 8062 | 71/100 | Python, best backtesting framework — evaluate for Kalshi strategy testing |
| `51bitquant/howtrader` | 889 | 75/100 | Python, quant trading framework |

**Safety note:** All evaluated via API metadata only (no cloning). Some repos may contain private key exfiltration code (content_scanner blocks these). Read source code before adopting any patterns.

**Kalshi application:**
1. `OctagonAI/kalshi-deep-trading-bot` — most directly relevant, evaluate its architecture patterns
2. `backtesting.py` — gold standard for strategy backtesting, evaluate for Kalshi strategy validation
3. Arbitrage bots — study their spread detection logic, timing, and fee handling
4. CAUTION: security warning from earlier r/algotrading finding about repos containing exfiltration code still applies

### [2026-03-17] HIGH-VALUE: Meta Labeling for Kalshi Signal Filtering (Session 32 Deep-Read)
**Source:** r/algotrading (610pts, 85 comments) — https://www.reddit.com/r/algotrading/comments/1lnm48w/
**Relevance:** HIGHEST-ROI addition to Kalshi bot. Uses ML to filter existing strategy signals — don't find new edge, amplify what already works.

Key findings:
- Train binary classifier on features at signal time to predict win/loss
- Author: win rate +1-3%, drawdown 35% to 23% (massively better risk-adjusted)
- Live 9 months on ES/NQ, 1.15 profit factor, 2.5 Calmar ratio
- Uses 6 base models with 20-70 features each, ensemble via Logistic Regression
- Needs minimum 1000+ trades (5000+ ideal) for the meta model
- CPCV (Combinatorial Purged Cross-Validation) for non-IID trades
- Calibrate each model's output with Platt scaling so probabilities are real-world accurate
- Google Vizier recommended over Optuna for hyperparameter tuning

**Kalshi application:**
1. Start logging ALL signals with features immediately (even before ML layer)
2. Label each signal win/loss after resolution
3. Train ensemble classifier to predict signal quality
4. Only execute high-confidence signals — aligns perfectly with sniper approach
5. The "ML amplifies existing edge, doesn't create it" mental model is correct

### [2026-03-17] HIGH-VALUE: Bayesian Regime Classification for Kalshi (Session 32 Deep-Read)
**Source:** r/algotrading (184pts, 67 comments) — https://www.reddit.com/r/algotrading/comments/1ob5xao/
**Relevance:** Condition ALL probability estimates on current market regime. Different strategies for different regimes.

Key findings:
- 5 regime types: strong bull, weak bull, bear, sideways, unpredictable
- Classified via SP500 moving averages + VIX
- Bayesian overnight reversal probabilities per regime, validated 10 years
- Live 3 months: 24% returns, 64.7% WR, Sharpe 3.51, low SP500 correlation (0.172)
- Day-of-week effect: overnight works best Mon-Wed
- Comment: use 7-9 regimes for more granularity
- Regime calculated at 3:50 PM EST — responsive to same-day conditions

**Kalshi application:**
1. Implement regime detection (bull/bear/sideways/volatile) before any bet
2. Different confidence thresholds per regime — tighter in volatile, looser in trending
3. Kalshi overnight + daily markets are the natural home for this
4. Condition the Bayesian model the research chat is building ON the regime state

### [2026-03-17] HIGH-VALUE: Pre-Market Feature Engineering for SPX Direction (Session 32 Deep-Read)
**Source:** r/algotrading (196pts, 172 comments) — https://www.reddit.com/r/algotrading/comments/1rrbdx5/
**Relevance:** Pre-open feature window (4:00-9:30 AM) has genuine signal for daily direction.

Key findings (expanded from earlier entry):
- 85-94% backtest accuracy but ONLY fires ~30% of days (selective, like sniper)
- Live commenter: up $34K since Jan 12 with similar system, fully automated
- Uses IBKR extended hours data, Massive for options chain
- Academic backing: pre-market price action predicts daily direction
- Confidence gating: hide prediction below threshold to prevent anchoring bias
- GEX (Gamma Exposure) + options walls layered in as additional features

**Kalshi application:**
1. Build pre-market feature extractor for SPX daily/hourly contracts
2. IBKR or similar data source for 4:00-9:30 AM window
3. Selective firing aligns perfectly with sniper timing
4. Gap fade strategy for SPY contracts using overnight drift data

---

## Processed Intel

_Kalshi Research: move items here after incorporating into bot strategy/code._

(Empty — Kalshi Research has not yet processed any items from this bridge)
