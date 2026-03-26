# MT-37 Phase 2: UBER Architecture Design

**Status:** Phase 2 — Architecture Design
**Foundation:** MT37_RESEARCH.md (42 papers, 10 areas, Phase 1 COMPLETE)
**Designed:** S182 (2026-03-25)

---

## System Overview

UBER (Unified Balanced Evidence-based Returns) is a wealth management intelligence
system that translates the 42-paper academic foundation into actionable portfolio
construction, monitoring, and optimization modules.

**What UBER does:**
- Constructs risk-aware portfolios using Black-Litterman + Risk Parity
- Applies evidence-based factor tilts (value, momentum, quality)
- Sizes positions using fractional Kelly with confidence scaling
- Monitors for regime changes and rebalancing triggers
- Generates tax-loss harvesting recommendations
- Provides withdrawal rate planning with guardrails

**What UBER does NOT do:**
- Execute trades (advisory only — outputs recommendations, not orders)
- Replace financial advisors (tool for informed decision-making)
- Guarantee returns (all models have estimation error)

---

## Module Decomposition

### Layer 1: Data Inputs

```
portfolio_loader.py — Parse holdings from CSV/JSON/brokerage export
market_data.py     — Price/return data retrieval (Yahoo Finance, FRED)
```

| Module | Purpose | Papers |
|--------|---------|--------|
| `portfolio_loader.py` | Parse user holdings (ticker, shares, cost basis) | — |
| `market_data.py` | Fetch returns, vol, factor exposures, macro data | — |

### Layer 2: Portfolio Construction

```
allocation.py       — Black-Litterman + Risk Parity base weights
factor_tilts.py     — Value, momentum, quality, low-vol factor overlays
```

| Module | Purpose | Papers |
|--------|---------|--------|
| `allocation.py` | Base weight generation via BL or risk parity | Markowitz 1952, Black-Litterman 1992, Qian 2005, Maillard et al. 2010 |
| `factor_tilts.py` | Factor tilt overlays on base allocation | FF 3/5-factor, Carhart 1997, Asness et al. 2013 |

### Layer 3: Position Sizing & Risk

```
kelly_sizer.py      — Fractional Kelly with confidence-scaled sizing
risk_monitor.py     — Drawdown tracking, regime detection, volatility alerts
```

| Module | Purpose | Papers |
|--------|---------|--------|
| `kelly_sizer.py` | Position sizing with growth-security tradeoff | Thorp 2006, Kelly 1956, MacLean et al. 2011 |
| `risk_monitor.py` | Regime detection, drawdown alerts, vol clustering | Ang 2014 (regime switching), Moskowitz et al. 2012 (TSMOM) |

### Layer 4: Tax & Withdrawal

```
tax_harvester.py    — Tax-loss harvesting opportunity scanner
withdrawal_planner.py — Safe withdrawal rate with CAPE-adjusted guardrails
```

| Module | Purpose | Papers |
|--------|---------|--------|
| `tax_harvester.py` | Identify TLH candidates, wash sale awareness | Constantinides 1983, Berkin & Ye 2003 |
| `withdrawal_planner.py` | CAPE-adjusted SWR, Guyton-Klinger guardrails | Bengen 1994, Kitces 2008, Guyton-Klinger 2006 |

### Layer 5: Output & Intelligence

```
rebalance_advisor.py  — When/how to rebalance (threshold + calendar hybrid)
portfolio_report.py   — Portfolio analytics (Sharpe, factor exposure, risk decomposition)
behavioral_guard.py   — Behavioral bias detection and counter-recommendations
```

| Module | Purpose | Papers |
|--------|---------|--------|
| `rebalance_advisor.py` | Rebalancing triggers and recommendations | DeMiguel et al. 2009, risk parity literature |
| `portfolio_report.py` | Analytics dashboard data (Sharpe, attribution, risk) | Sharpe 1964, FF factor decomposition |
| `behavioral_guard.py` | Detect and counter behavioral biases | Kahneman & Tversky 1979, Benartzi & Thaler 1995 |

---

## Data Flow

```
User Holdings (CSV/JSON)
    |
    v
portfolio_loader.py --> parsed holdings + cost basis
    |
    v
market_data.py --> returns, vol, factor exposures, macro
    |
    +---> allocation.py --> base weights (BL or RP)
    |         |
    |         v
    |     factor_tilts.py --> tilted weights
    |         |
    |         v
    |     kelly_sizer.py --> sized positions
    |
    +---> risk_monitor.py --> regime alerts, drawdown warnings
    |
    +---> tax_harvester.py --> TLH candidates
    |
    +---> withdrawal_planner.py --> SWR recommendation
    |
    v
rebalance_advisor.py --> rebalancing recommendations
    |
    v
portfolio_report.py --> Typst PDF report / JSON data
    |
    v
behavioral_guard.py --> bias warnings overlaid on recommendations
```

---

## Key Design Decisions

### 1. Advisory-only, no execution
UBER outputs recommendations (buy X shares of Y, harvest loss in Z), never executes
trades. This eliminates financial risk and compliance concerns. Users execute
recommendations through their own brokerage.

### 2. Black-Litterman over raw MVO
Raw mean-variance optimization is an "error maximizer" (DeMiguel et al. 2009).
Black-Litterman uses market-cap weights as the prior and blends in user views,
producing more stable and intuitive allocations. Risk parity offered as alternative
for users who don't want to specify views.

### 3. Only structurally justified factors
From the factor zoo of 400+ proposed factors (Harvey et al. 2016), UBER uses only
those with: (a) 20+ years of out-of-sample evidence, (b) structural economic
rationale, (c) survived multiple replication attempts. This means: value, momentum,
quality, low-volatility. NOT: short-term reversal, accruals, or most micro factors.

### 4. Fractional Kelly with conservative scaling
Full Kelly is theoretically optimal for log-wealth growth but produces unacceptable
drawdowns in practice. UBER defaults to half-Kelly (f* / 2), which sacrifices ~25%
of long-run growth but reduces max drawdown by ~50% (MacLean et al. 2011).

### 5. CAPE-adjusted withdrawal rates
Fixed 4% rule is outdated (Bengen 1994 assumed specific historical conditions).
UBER uses Kitces' CAPE-10 adjustment: lower withdrawal rate when CAPE is high
(expensive market), higher when CAPE is low. Guyton-Klinger guardrails provide
automatic adjustment based on portfolio performance.

### 6. Behavioral guardrails are first-class
Behavioral biases (loss aversion, disposition effect, recency) cause more wealth
destruction than bad asset selection (Benartzi & Thaler 1995). UBER's behavioral
guard module is not optional — it runs on every recommendation and flags when
the user's proposed action contradicts evidence-based behavior.

---

## Integration with Existing CCA/Kalshi Infrastructure

### Shared components:
- `design-skills/chart_generator.py` — SVG charts for portfolio visualizations
- `design-skills/report_generator.py` — Typst PDF generation for portfolio reports
- `self-learning/dynamic_kelly.py` — Kelly sizing already built for Kalshi, adaptable
- `self-learning/regime_detector.py` — Regime detection framework already built

### New dependencies (stdlib + minimal):
- `json`, `csv`, `math`, `statistics` — stdlib only for core logic
- `urllib` — for market data fetching (no requests library)
- Optional: `yfinance` for convenience (but fallback to raw urllib)

---

## Implementation Phases

| Phase | What | LOC est. | Tests est. |
|-------|------|----------|-----------|
| 3 | `portfolio_loader.py` — CSV/JSON parser + holdings model | ~200 | ~25 |
| 4 | `market_data.py` — Return/vol/factor data retrieval | ~300 | ~30 |
| 5 | `allocation.py` — BL + RP allocation engines | ~400 | ~40 |
| 6 | `factor_tilts.py` — Factor overlay system | ~250 | ~30 |
| 7 | `kelly_sizer.py` — Fractional Kelly with confidence | ~200 | ~25 |
| 8 | `risk_monitor.py` — Drawdown + regime detection | ~250 | ~25 |
| 9 | `tax_harvester.py` — TLH scanner | ~200 | ~20 |
| 10 | `withdrawal_planner.py` — SWR + guardrails | ~200 | ~20 |
| 11 | `rebalance_advisor.py` + `portfolio_report.py` | ~300 | ~25 |
| 12 | Integration + `behavioral_guard.py` | ~250 | ~20 |

**Total estimate:** ~2,550 LOC, ~260 tests across 10 modules

---

## Success Criteria

1. Given a portfolio CSV, UBER produces a rebalancing recommendation with:
   - Target allocation (BL or RP derived)
   - Factor tilt adjustments with academic citations
   - Position sizes scaled by fractional Kelly
   - TLH candidates with estimated tax savings
   - Behavioral warnings if applicable

2. Report generates as Typst PDF with portfolio charts via chart_generator.py

3. All recommendations traceable to specific academic papers (no black boxes)

4. Beats 1/N equal-weight in risk-adjusted terms on 10-year backtest OR
   explicitly recommends indexing (per Sharpe 1991 arithmetic)
