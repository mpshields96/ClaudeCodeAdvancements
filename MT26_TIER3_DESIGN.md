# MT-26 Tier 3: Order Flow Intelligence + Belief Volatility Surface
# Design Document — S112 (2026-03-21)
# Status: RESEARCH COMPLETE, ready for TDD implementation over multiple sessions
#
# Papers verified: arXiv:2510.15205 (Dalen 2025), UCD WP2025_19 (Burgi/Deng/Whelan 2025)

---

## Module 7: Order Flow Intelligence

### Source Paper
"Makers and Takers: The Economics of the Kalshi Prediction Market" (Burgi, Deng, Whelan, 2025)
UCD Working Paper WP2025_19 — 49 pages, 300K+ contracts analyzed

### Key Finding
Investors who buy contracts costing less than 10c lose over 60% of their money. The
favorite-longshot bias (FLB) is statistically significant across ALL categories, ALL
volume quintiles, and ALL years (2021-2025).

### The Maker/Taker Model

Makers (limit orders) are informed; Takers (market orders) are noise traders.
The marginal Maker requires expected return gamma on investment:

```
(1 - pi + delta) * p - (pi - delta) * (1 - p) - theta * p * (1-p) = gamma * [(1-p) + theta * p * (1-p)]
```

Rearranges to quadratic (solvable with math.sqrt):
```
theta(1+gamma) * p^2 + (1 - theta(1+gamma) + gamma) * p + (delta - pi - gamma) = 0
```

Where:
- pi = true event probability
- delta = Maker over-optimism (winner's curse)
- theta = 0.07 (Kalshi fee parameter)
- gamma = required rate of return
- p = contract price

### FLB Regression (Mincer-Zarnowitz)
```
y_ij - p_ij = alpha + psi * p_ij + epsilon_ij
```

Category-specific psi coefficients:
| Category | psi | Significance |
|----------|-----|-------------|
| All | 0.034 | *** |
| Crypto | 0.058 | *** |
| Financials | 0.032 | *** |
| Climate | 0.031 | *** |
| Politics | 0.022 | ns |
| Entertainment | 0.020 | ns |
| Economics | 0.034 | *** |

Crypto has the LARGEST psi — strongest FLB. This validates the sniper edge.

### Inputs Needed
- Transaction-level data from Kalshi API: price, size, timestamp, Maker/Taker flag
- Contract metadata: event type, time to close
- Historical outcomes: win/loss per contract
- Order book snapshots: bid-ask spread, depth

### Outputs
1. Maker/Taker classification (Kalshi provides directly)
2. FLB bias score per contract category
3. Price band risk classification (sub-10c = "toxic longshot")
4. Fee-adjusted expected return: `E[return] = (win_rate - price - fee) / (price + fee)`
5. Maker information signal: cluster detection
6. Category-specific bias adjustment

### Implementation: `order_flow_intel.py`

Entirely stdlib-feasible (no numpy needed):

```python
# Core classes
class FeeCalculator:
    """Kalshi fee model: theta * p * (1-p), theta=0.07"""

class FLBEstimator:
    """OLS regression for favorite-longshot bias.
    Trivial without numpy: just sums of products."""

class MakerTakerAnalyzer:
    """Classify trades, compute Maker vs Taker returns."""

class ReturnForecaster:
    """Expected return by price band + category using psi coefficients."""

class RiskClassifier:
    """Flag toxic longshots, score contracts.
    Sub-10c = AVOID, 50c+ = FAVORABLE."""

class BiasTracker:
    """Track FLB evolution over time (is the edge shrinking?)."""
```

Target: ~300-400 LOC, 40+ tests. Stdlib only.

---

## Module 8: Belief Volatility Surface

### Source Paper
"Toward Black-Scholes for Prediction Markets" (Dalen, 2025)
arXiv:2510.15205 — 25 pages, Daedalus Research Team

### Core Mathematical Framework

Logit jump-diffusion (RN-JD) model. Transform probability p_t to log-odds x_t:

```
x_t = logit(p_t) = log(p_t / (1 - p_t))
S(x) = 1 / (1 + exp(-x))  # inverse (sigmoid)
```

Core SDE in log-odds space:
```
dx_t = mu(t, x_t) dt + sigma_b(t, x_t) dW_t + integral_R z N_tilde(dt, dz)
```

Where sigma_b is "belief volatility" — the tradable risk factor.

Drift mu is constrained by martingale condition (no-arbitrage):
```
mu = -[0.5 * S''(x) * sigma_b^2 + jump_compensation] / S'(x)
S'(x) = p(1-p)
S''(x) = p(1-p)(1-2p)
```

### Calibration Pipeline (5 steps)
1. Data conditioning: trade-weighted mid, clamp to [epsilon, 1-epsilon], resample to grid
2. Kalman filter: heteroskedastic state-space filter for latent x_t
3. EM separation: diffusion vs jump classification per price move
4. Drift enforcement: recompute mu with estimated parameters
5. Surface construction: smooth sigma_b across (tau, moneyness) with penalized least-squares

### Inputs Needed
- Transaction-level data: timestamps, prices, sizes, bid-ask spreads
- Order book: depth, spread, aggressor imbalance
- Event metadata: resolution dates, announcement times
- Frequency: high-frequency (100ms-1s grid), ~6000+ data points per calibration

### Outputs
- Belief volatility surface: sigma_b(tau, moneyness)
- Jump layer: lambda(tau, m) intensity + jump size variance
- Greeks: Delta_x = p(1-p), Gamma_x = p(1-p)(1-2p), belief-vega
- Reservation quotes: Avellaneda-Stoikov adapted to logit space

### Implementation Complexity: HIGH

This module requires:
- Kalman filter (implementable in stdlib but slow)
- EM algorithm (iterative, stdlib feasible)
- B-spline surface fitting (needs numpy or simple approximation)
- Matrix operations for covariance

### Recommended Approach: Multi-Phase

**Phase 1 (this MT):** Core transforms + Greeks only
```python
class LogitTransform:
    """p <-> x conversions, S'(x), S''(x), martingale drift"""

class BeliefGreeks:
    """Delta, Gamma, Vega in logit space — analytical formulas"""

class SimpleVolEstimator:
    """Realized belief volatility from price history (no Kalman)
    Use rolling window of log-odds changes."""
```

**Phase 2 (future):** Full Kalman + EM + surface
- Only build after Phase 1 proves useful
- Likely needs numpy as dependency

Target Phase 1: ~200 LOC, 30+ tests. Stdlib only.

---

## Implementation Priority

1. **Order Flow Intelligence first** — stdlib only, immediately actionable, directly
   validates/enhances sniper edge. Category-specific psi coefficients are pure gold
   for the Kalshi bot.

2. **Belief Volatility Phase 1 second** — logit transforms + Greeks are
   foundational math that everything else builds on.

3. **Belief Volatility Phase 2 later** — full calibration pipeline is a
   research-grade project. Only after Phase 1 proves useful.

---

## Integration with Existing Pipeline

Both modules plug into `signal_pipeline.py` as additional signal sources:

```
signal_pipeline.py
  ├── regime_detector.py        (Tier 1)
  ├── calibration_bias.py       (Tier 1)
  ├── cross_platform_signal.py  (Tier 1)
  ├── dynamic_kelly.py          (Tier 2)
  ├── macro_regime.py           (Tier 2)
  ├── fear_greed_filter.py      (Tier 2)
  ├── order_flow_intel.py       (Tier 3 — NEW)
  └── belief_vol_surface.py     (Tier 3 — NEW, Phase 1 only)
```

The pipeline's graceful degradation means new modules can fail without breaking
existing signals.

---

## Key Insight for Kalshi Bot

The Makers & Takers paper proves structurally that:
- The bot should ALWAYS act as a Maker (limit orders), not a Taker
- Sub-10c contracts are toxic longshots — hard guard against buying them
- Crypto has the strongest FLB (psi=0.058) — the sniper's edge is academically validated
- The FLB may be weakening over time (2025 psi smaller) — monitor for edge decay
