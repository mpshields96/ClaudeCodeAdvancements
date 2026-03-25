# MT-37: AI-Driven Investment Research & Portfolio Intelligence
# STATUS: UBER-LEVEL MASTER TASK — Matthew's Long-Term Financial Conquest
# Elevated: S169 (2026-03-26) — Matthew directive
# Origin: S148 (2026-03-24), S103 Strategic Vision Milestone D
#
# This is CCA's largest research-first MT. It represents the natural evolution
# from short-term prediction market profits (Kalshi) to long-term wealth building
# through academically-grounded, algorithmically-constructed portfolios.

---

## Matthew's Vision (verbatim, S148)

"Need to eventually seek investments/stock long-term safe savings with ETFs whatever
the objective recommendation here... CCA developing the ability to look into objective
AI algo investing elite level with significant academic research, economic financial
data EVERYTHING related to this very long-term conquest."

## Strategic Context

This is **Milestone D** from S103 Strategic Vision — the final financial milestone:

| Milestone | Target | Status |
|-----------|--------|--------|
| A | Cover Claude Max 5x ($125/mo) | IN PROGRESS (Kalshi sniper ~$261/mo pace) |
| B | Cover Claude Max 20x ($250/mo) | IN PROGRESS |
| C | Compounding passive income ($hundreds/mo) | NEXT |
| **D** | **Transition proven strategies to investments/stocks** | **THIS MT** |

The Kalshi bot proves the methodology works: structural basis + math validation +
backtesting + self-learning feedback loops. MT-37 applies the same rigor to a
fundamentally different domain: long-term wealth preservation and growth.

---

## The 8 Pillars

### Pillar 1: Academic Foundation (MASSIVE RESEARCH)

Survey the entire quantitative finance canon. Every recommendation must trace to
peer-reviewed research. No speculation, no vibes, no guru advice.

**Core literature to consume and synthesize:**

| Area | Key Works | Why |
|------|-----------|-----|
| Modern Portfolio Theory | Markowitz (1952), Sharpe (1964) CAPM, Black-Litterman (1992) | Foundation — mean-variance optimization, efficient frontier |
| Factor Models | Fama-French 3-factor (1993), Carhart 4-factor (1997), Fama-French 5-factor (2015) | Explains cross-section of returns — size, value, profitability, investment |
| Risk Parity | Bridgewater All Weather, Qian (2005, 2016) | Equal risk contribution — outperforms 60/40 in most regimes |
| Momentum & Value | Asness (2013) "Value and Momentum Everywhere", AQR research library | Two strongest documented anomalies — persistent across asset classes |
| Behavioral Finance | Kahneman & Tversky (1979), Shiller (2000), Thaler (2015) | Why markets misprice — loss aversion, overconfidence, herding |
| Tax-Loss Harvesting | Constantinides (1983), Berkin & Ye (2003) | Quantified TLH benefit: 0.5-1.5% annual alpha |
| Retirement Planning | Bengen (1994) 4% rule, Kitces (2008) dynamic spending, ERN (2017) Safe Withdrawal series | Sequence-of-returns risk, decumulation strategies |
| Kelly Criterion (Long-Horizon) | Thorp (2006), MacLean et al. (2011) | Position sizing for long-term geometric growth |
| Index Investing | Bogle (2007), Sharpe (1991) "The Arithmetic of Active Management" | Why passive beats active for most investors — net of fees |
| Alternative Risk Premia | Ilmanen (2011) "Expected Returns", Ang (2014) "Asset Management" | Carry, value, momentum, volatility — harvesting risk premia systematically |

**Research institutions to mine:**
- AQR Capital Management research library (100+ published papers)
- Vanguard Investment Strategy Group research
- Dimensional Fund Advisors research
- NBER Working Papers (finance section)
- Journal of Finance, Journal of Financial Economics, Review of Financial Studies
- Financial Analysts Journal (CFA Institute)
- SSRN Finance section

**Output:** A comprehensive RESEARCH.md (aim for 50+ papers synthesized) covering:
- Which factors have survived out-of-sample testing
- Which portfolio construction methods have the strongest empirical support
- What the academic consensus is on active vs passive
- Tax-efficient investing best practices
- Retirement planning mathematics

### Pillar 2: ETF/Index Fund Universe

Build a structured, queryable database of ETFs and index funds.

**Data to collect per fund:**
- Ticker, name, issuer, inception date
- Expense ratio (THE most important single metric for passive investing)
- AUM (liquidity proxy)
- Tracking error vs benchmark
- Sector/geographic/factor exposure
- Historical returns (1y, 3y, 5y, 10y, since inception)
- Tax efficiency (turnover rate, capital gains distributions)
- Factor loadings (market beta, size, value, momentum, quality)

**Universe scope (initial):**
- US total market (VTI, ITOT, SPTM)
- International developed (VXUS, IXUS, VEA, IEFA)
- Emerging markets (VWO, IEMG, EEM)
- US bonds (BND, AGG, SCHZ)
- International bonds (BNDX, IAGG)
- TIPS (VTIP, SCHP, TIP)
- REITs (VNQ, SCHH, IYR)
- Factor ETFs: value (VTV, IUSV), small-cap (VB, IJR), momentum (MTUM), quality (QUAL), low vol (USMV)
- Target-date funds (Vanguard, Fidelity, Schwab series)

**Data sources:**
- SEC EDGAR (fund filings, expense ratios, holdings)
- Yahoo Finance API / yfinance (historical prices, dividends)
- ETF.com / ETFdb.com (fund screener data)
- Morningstar (factor analysis, style box)
- Fund issuer websites (Vanguard, iShares, Schwab)

**Tooling to build:**
- `etf_universe.py` — ETF data fetcher + SQLite storage
- `fund_comparator.py` — head-to-head fund comparison (expense, tracking error, tax efficiency)
- `factor_analyzer.py` — regression-based factor loading calculator

### Pillar 3: Portfolio Construction

Implement and backtest 5+ allocation strategies. Compare rigorously.

**Strategies to implement:**

| Strategy | Description | Complexity |
|----------|-------------|------------|
| Bogle 3-Fund | US total market + International + US bonds | Simple |
| 60/40 Classic | 60% equities / 40% bonds | Simple |
| All Weather (Risk Parity) | Equal risk contribution across asset classes | Medium |
| Fama-French Factor Tilt | Overweight small-cap value, quality | Medium |
| Black-Litterman | Bayesian allocation with investor views | Hard |
| Target-Date Glide Path | Age-based equity/bond shift (custom) | Medium |
| Permanent Portfolio | 25% each: stocks, bonds, gold, cash | Simple |
| Larry Portfolio | 75% equities (factor tilt) / 25% short-term bonds | Medium |

**Backtest framework requirements:**
- Historical data: 20+ years minimum (1995-2025)
- Metrics: CAGR, Sharpe ratio, Sortino ratio, max drawdown, Calmar ratio, worst year
- Rebalancing: annual, semi-annual, threshold-based (5% band)
- Transaction costs: model realistic trading costs
- Tax impact: pre-tax vs after-tax returns
- Out-of-sample testing: train on 1995-2015, test on 2015-2025
- Crisis performance: 2000-2002, 2008-2009, 2020 March

**Tooling to build:**
- `portfolio_builder.py` — allocation strategy implementations
- `backtest_engine.py` — historical simulation with rebalancing
- `performance_analyzer.py` — Sharpe, drawdown, rolling returns analysis

### Pillar 4: Economic Data Integration

Ingest and analyze macro indicators for regime-aware allocation.

**Key indicators:**
- Fed funds rate (monetary policy regime)
- CPI / PCE (inflation regime)
- GDP growth rate (expansion/contraction)
- Unemployment rate (labor market health)
- Yield curve slope (2y-10y spread — recession predictor)
- Corporate earnings (S&P 500 EPS, P/E ratios)
- VIX (volatility regime)
- Credit spreads (HY-IG spread — risk appetite)
- Consumer sentiment (University of Michigan)
- PMI (manufacturing + services)

**Regime detection (reuse MT-26 architecture):**
- EXPANSION: GDP rising, unemployment falling, positive earnings
- LATE CYCLE: rising rates, tight labor, narrowing spreads
- CONTRACTION: negative GDP, rising unemployment, widening spreads
- RECOVERY: rates falling, stabilizing unemployment, bottoming earnings

**Data sources:**
- FRED API (free, 800K+ time series) — primary source
- BLS (Bureau of Labor Statistics) — employment, CPI
- BEA (Bureau of Economic Analysis) — GDP, PCE
- SEC EDGAR — corporate filings
- Quandl / Nasdaq Data Link

**Tooling to build:**
- `macro_data.py` — FRED API client + data storage
- `regime_classifier.py` — macro regime detection (reuse regime_detector.py patterns)
- `allocation_adjuster.py` — regime-dependent allocation shifts

### Pillar 5: Risk Analysis

Tail risk measurement, stress testing, retirement projections.

**Risk metrics to implement:**
- Value at Risk (VaR) — parametric, historical, Monte Carlo
- Conditional VaR (CVaR / Expected Shortfall) — what happens in the tail
- Maximum drawdown + recovery time
- Sequence-of-returns risk (critical for retirement)
- Correlation regime shifts (correlations spike in crises)
- Beta to benchmark
- Tracking error
- Information ratio

**Monte Carlo simulations:**
- Retirement projection: given savings rate, portfolio, age, spending — probability of success
- Withdrawal rate analysis: safe withdrawal rates under various scenarios
- Sensitivity analysis: what if returns are 2% lower? What if inflation is 1% higher?

**Stress testing:**
- Replay portfolio through historical crises
- Hypothetical scenarios: stagflation, hyperinflation, deflation, prolonged bear market
- Correlation breakdown scenarios

**Tooling to build:**
- `risk_analyzer.py` — VaR, CVaR, drawdown analysis
- `monte_carlo_retirement.py` — retirement projection simulator (reuse monte_carlo_simulator.py patterns)
- `stress_tester.py` — historical + hypothetical crisis replay

### Pillar 6: Tax Optimization

Tax-aware investing strategies (US-focused initially).

**Topics to cover:**
- Asset location: which funds in taxable vs tax-advantaged accounts
- Tax-loss harvesting: systematic TLH with wash sale rule compliance
- Roth vs Traditional: breakeven analysis based on current/future tax brackets
- Capital gains management: holding period optimization (short-term vs long-term)
- Qualified dividends vs ordinary income
- State tax considerations
- Estate planning basics (step-up in basis)

**Tooling to build:**
- `tax_optimizer.py` — asset location recommendations
- `tlh_simulator.py` — tax-loss harvesting backtest (with wash sale tracking)
- `roth_analyzer.py` — Roth conversion analysis

### Pillar 7: Reporting & Visualization

Leverage existing MT-32 design-skills infrastructure.

**Reports to generate:**
- Portfolio allocation pie/donut chart
- Historical performance vs benchmark line chart
- Risk dashboard (VaR, drawdown, correlation heatmap)
- Factor exposure radar chart
- Retirement projection fan chart (Monte Carlo confidence bands)
- Rebalancing recommendations table
- Tax-loss harvesting opportunities

**Reuse from MT-32:**
- chart_generator.py (12 chart types already built)
- report_generator.py (Typst PDF rendering)
- dashboard_generator.py (interactive HTML)
- figure_generator.py (multi-panel compositions)

### Pillar 8: Self-Learning Integration

Feed investment outcomes back into the learning pipeline.

**Track:**
- Which allocation strategies outperform over time
- Which factor tilts add value vs noise
- Regime detection accuracy (did we correctly identify transitions?)
- Rebalancing timing effectiveness
- TLH harvest value realized

**Reuse from MT-28:**
- principle_registry.py (score what works across domains)
- pattern_registry.py (register new detectors)
- outcome_feedback.py (close the loop)

---

## Phased Implementation Plan

| Phase | Scope | Effort | Prereqs |
|-------|-------|--------|---------|
| **1** | Deep academic research survey | 3-5 sessions | None |
| **2** | Data pipeline (FRED API, ETF universe) | 2-3 sessions | Phase 1 |
| **3** | Portfolio constructor (5+ strategies + backtest) | 3-5 sessions | Phase 2 |
| **4** | Risk analysis toolkit (VaR, Monte Carlo, stress) | 2-3 sessions | Phase 3 |
| **5** | Tax optimization layer | 2-3 sessions | Phase 3 |
| **6** | Reporting integration (wire into MT-32) | 1-2 sessions | Phase 3-5 |
| **7** | Self-learning feedback loop | 1-2 sessions | Phase 3+ |

**Total estimated: 14-23 sessions** (spread over weeks/months, no rush)

Phase 1 is PURE RESEARCH — no code. Read papers, synthesize findings, produce a
literature review that would pass academic peer review. This is the foundation
everything else builds on.

---

## CCA Infrastructure Already Available

MT-37 is not starting from zero. CCA has already built:

| Existing Module | How MT-37 Uses It |
|----------------|-------------------|
| `monte_carlo_simulator.py` (REQ-040) | Retire Monte Carlo — extend for retirement projections |
| `regime_detector.py` (MT-26) | Macro regime classification — extend for economic cycles |
| `dynamic_kelly.py` (MT-26) | Kelly criterion — adapt for long-horizon position sizing |
| `macro_regime.py` (MT-26) | FOMC/CPI/NFP calendar — extend for full macro data |
| `fear_greed_filter.py` (MT-26) | Sentiment — adapt for market-wide sentiment |
| `signal_pipeline.py` (MT-26) | Pipeline orchestration — reuse for allocation pipeline |
| `principle_registry.py` (MT-28) | Self-learning — reuse for investment principle tracking |
| `paper_scanner.py` (MT-12) | Academic paper discovery — point at finance venues |
| `paper_digest.py` (MT-12) | Paper digest generation — reuse for investment papers |
| `chart_generator.py` (MT-32) | 12 chart types ready for portfolio visualization |
| `report_generator.py` (MT-17) | PDF report generation with Typst |
| `dashboard_generator.py` (MT-32) | Interactive HTML dashboards |

---

## What This Is NOT

- NOT a day-trading or active trading system (that's the Kalshi bot)
- NOT financial advice (always disclaim — Matthew makes his own decisions)
- NOT speculative (no crypto, no options, no leveraged products unless academically justified)
- NOT a replacement for a financial advisor (augmentation, not replacement)
- NOT rushed (long-term conquest — research quality over speed)

---

## Rigor Standard (same as Kalshi bot)

Every recommendation, allocation strategy, or factor tilt must meet ALL FOUR:
1. **Structural basis** — academic paper with peer review
2. **Math validation** — formal derivation or proof
3. **Backtesting** — out-of-sample performance over 20+ years
4. **Statistical significance** — p-value, confidence intervals, or Bayesian evidence

No exceptions. No vibes. No "this guru said X." If the evidence doesn't meet all four
criteria, it does not get implemented.

---

## Key Subreddits for Community Intelligence

| Subreddit | Signal Type |
|-----------|------------|
| r/Bogleheads | Index investing consensus, 3-fund portfolio, tax optimization |
| r/investing | General market intelligence, fund comparisons |
| r/financialindependence | FIRE movement, withdrawal strategies, asset allocation |
| r/portfolios | Portfolio review, allocation feedback |
| r/quantfinance | Academic quantitative finance, factor models |
| r/SecurityAnalysis | Deep value investing, fundamental analysis |
| r/algotrading | Algorithmic strategies (overlap with Kalshi work) |

---

## Success Criteria

MT-37 is "done" when CCA can:
1. Answer "What ETFs should I hold and in what proportions?" with academically-grounded, backtested recommendations
2. Show projected retirement outcomes under multiple scenarios
3. Identify tax optimization opportunities specific to Matthew's situation
4. Detect macro regime shifts and adjust allocation recommendations
5. Track recommendation accuracy over time via self-learning
6. Present everything in professional, visual reports

This is the endgame of CCA's financial pillar — from Kalshi prediction markets to
long-term wealth building. Same rigor. Same self-learning. Much longer time horizon.
