#!/usr/bin/env python3
"""
order_flow_intel.py — MT-26 Tier 3: Order Flow Intelligence.

Based on "Makers and Takers: The Economics of the Kalshi Prediction Market"
(Burgi, Deng, Whelan, 2025) — UCD Working Paper WP2025_19.

Key finding: Investors buying contracts under 10c lose 60%+ of their money.
The favorite-longshot bias (FLB) is significant across ALL categories.
Crypto has the strongest FLB (psi=0.058).

Components:
- FeeCalculator: Kalshi fee model (theta * p * (1-p), theta=0.07)
- FLBEstimator: Favorite-longshot bias OLS regression
- ReturnForecaster: Expected return by price band + category
- RiskClassifier: Toxic longshot detection + contract scoring
- BiasTracker: FLB evolution tracking over time
- MakerTakerAnalyzer: Trade classification and return analysis

Stdlib only. No external dependencies.
"""

import math
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Fee Calculator
# ---------------------------------------------------------------------------

class FeeCalculator:
    """Kalshi fee model: theta * p * (1-p) per contract.

    Default theta=0.07 per Kalshi's documented fee structure.
    Fee is maximized at p=0.50, symmetric around 0.50.
    """

    def __init__(self, theta: float = 0.07):
        self.theta = theta

    def fee(self, price: float) -> float:
        """Compute fee for a contract at given price (0 to 1)."""
        return self.theta * price * (1 - price)

    def fee_pct(self, price: float) -> float:
        """Fee as a percentage of price. Higher for cheap contracts."""
        if price <= 0:
            return 0.0
        return self.fee(price) / price

    def breakeven_win_rate(self, price: float) -> float:
        """Minimum win rate to break even after fees.

        Investment = price + fee. Win payout = 1.0.
        Breakeven: win_rate * (1 - price - fee) = (1 - win_rate) * (price + fee)
        => win_rate = (price + fee) / 1.0 = price + fee
        """
        f = self.fee(price)
        return price + f

    def expected_return(self, price: float, win_rate: float) -> float:
        """Expected return given price and actual win rate.

        Return = (win_rate * (1 - price) - (1 - win_rate) * price - fee) / (price + fee)
        """
        f = self.fee(price)
        investment = price + f
        if investment <= 0:
            return 0.0
        profit = win_rate * (1 - price) - (1 - win_rate) * price - f
        return profit / investment


# ---------------------------------------------------------------------------
# FLB Estimator (OLS)
# ---------------------------------------------------------------------------

class FLBEstimator:
    """Favorite-Longshot Bias estimator using OLS regression.

    Mincer-Zarnowitz regression: y_ij - p_ij = alpha + psi * p_ij + epsilon
    Where y_ij = 1 if event occurs, p_ij = contract price.

    Rearranged: (outcome - price) = alpha + psi * price
    Or equivalently: outcome = (alpha + psi * price) + price = alpha + (1 + psi) * price

    Positive psi = FLB (cheap contracts overpriced, expensive underpriced).
    """

    # Paper's category-specific psi coefficients (Table 8)
    CATEGORY_PSI = {
        "all": 0.034,
        "financials": 0.032,
        "crypto": 0.058,
        "climate": 0.031,
        "politics": 0.022,
        "entertainment": 0.020,
        "economics": 0.034,
        "other": 0.053,
    }

    # Paper's category-specific alpha coefficients (Table 8)
    CATEGORY_ALPHA = {
        "all": -1.736,
        "financials": -1.431,
        "crypto": -1.944,
        "climate": -0.997,
        "politics": -1.912,
        "entertainment": -2.809,
        "economics": -0.978,
        "other": -2.392,
    }

    def __init__(self):
        self._alpha: Optional[float] = None
        self._psi: Optional[float] = None
        self._n: int = 0

    def fit(self, prices: list[float], outcomes: list[int]) -> dict:
        """Fit FLB regression: (outcome - price) = alpha + psi * price.

        Args:
            prices: Contract prices (0 to 1).
            outcomes: Binary outcomes (0 or 1).

        Returns:
            Dict with alpha, psi, r_squared, n.
        """
        if len(prices) < 5:
            raise ValueError("Need at least 5 observations for OLS fit")
        if len(prices) != len(outcomes):
            raise ValueError("prices and outcomes must have same length")

        n = len(prices)
        # Dependent variable: outcome - price (profit/loss)
        y = [outcomes[i] - prices[i] for i in range(n)]
        x = prices

        # OLS: y = alpha + psi * x
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(x[i] * y[i] for i in range(n))
        sum_x2 = sum(xi * xi for xi in x)

        x_bar = sum_x / n
        y_bar = sum_y / n

        ss_xy = sum_xy - n * x_bar * y_bar
        ss_xx = sum_x2 - n * x_bar * x_bar

        if ss_xx == 0:
            self._psi = 0.0
            self._alpha = y_bar
        else:
            self._psi = ss_xy / ss_xx
            self._alpha = y_bar - self._psi * x_bar

        self._n = n

        # R-squared
        ss_tot = sum((yi - y_bar) ** 2 for yi in y)
        y_pred = [self._alpha + self._psi * xi for xi in x]
        ss_res = sum((y[i] - y_pred[i]) ** 2 for i in range(n))
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

        return {
            "alpha": self._alpha,
            "psi": self._psi,
            "r_squared": r_squared,
            "n": n,
        }

    def predict_bias(self, price: float) -> float:
        """Predict bias (expected profit deviation) for a given price."""
        if self._psi is None:
            raise RuntimeError("Must call fit() before predict_bias()")
        return self._alpha + self._psi * price


# ---------------------------------------------------------------------------
# Return Forecaster
# ---------------------------------------------------------------------------

class ReturnForecaster:
    """Expected return by price band and category.

    Uses the paper's FLB regression coefficients to forecast expected returns.
    """

    # Price bands with empirical return ranges from the paper
    PRICE_BANDS = [
        (0.00, 0.10, "sub-10c"),
        (0.10, 0.20, "10c-20c"),
        (0.20, 0.30, "20c-30c"),
        (0.30, 0.50, "30c-50c"),
        (0.50, 0.70, "50c-70c"),
        (0.70, 0.90, "70c-90c"),
        (0.90, 1.00, "90c+"),
    ]

    def __init__(self):
        self._fee_calc = FeeCalculator()

    def get_price_bands(self) -> list[tuple]:
        """Return price band definitions."""
        return [(lo, hi, label) for lo, hi, label in self.PRICE_BANDS]

    def expected_return_by_band(self, price: float, category: str = "all") -> float:
        """Estimate expected return for a contract at given price and category.

        Uses the paper's FLB model:
        E[outcome] = price + alpha/100 + psi * price / 100
        E[return] = (E[outcome] - price - fee) / (price + fee)

        The alpha and psi from the regression are in percentage points of
        contract value (cents), so we scale appropriately.
        """
        psi = FLBEstimator.CATEGORY_PSI.get(category, FLBEstimator.CATEGORY_PSI["all"])
        alpha = FLBEstimator.CATEGORY_ALPHA.get(category, FLBEstimator.CATEGORY_ALPHA["all"])

        # The regression is: profit_pct = alpha + psi * price_cents
        # Where price_cents is in range 0-100 and profit_pct is in cents
        # Expected win rate implied by regression:
        # outcome = price + (alpha + psi * price_cents) / 100
        price_cents = price * 100
        bias_cents = alpha + psi * price_cents
        implied_win_rate = price + bias_cents / 100

        # Clamp to valid range
        implied_win_rate = max(0.001, min(0.999, implied_win_rate))

        return self._fee_calc.expected_return(price, implied_win_rate)


# ---------------------------------------------------------------------------
# Risk Classifier
# ---------------------------------------------------------------------------

class RiskClassifier:
    """Classify contracts by risk based on FLB research.

    Risk levels:
    - TOXIC: sub-10c, expected loss 60%+ (paper finding)
    - UNFAVORABLE: 10c-30c, negative expected return
    - NEUTRAL: 30c-50c, near-zero expected return
    - FAVORABLE: 50c+, small positive expected return
    """

    THRESHOLDS = {
        "TOXIC": (0.00, 0.10),
        "UNFAVORABLE": (0.10, 0.30),
        "NEUTRAL": (0.30, 0.50),
        "FAVORABLE": (0.50, 1.00),
    }

    REASONS = {
        "TOXIC": "Sub-10c contracts lose 60%+ of invested capital (Burgi et al. 2025)",
        "UNFAVORABLE": "10c-30c contracts have negative expected return due to FLB",
        "NEUTRAL": "30c-50c contracts near breakeven after fees",
        "FAVORABLE": "50c+ contracts have small positive expected return (FLB favors favorites)",
    }

    def __init__(self):
        self._forecaster = ReturnForecaster()

    def classify(self, price: float, category: str = "all") -> dict:
        """Classify a contract by risk level."""
        for risk, (lo, hi) in self.THRESHOLDS.items():
            if lo <= price < hi:
                return {
                    "price": price,
                    "risk": risk,
                    "reason": self.REASONS[risk],
                    "expected_return": self._forecaster.expected_return_by_band(price, category),
                    "category": category,
                }
        # price >= 1.0 edge case
        return {"price": price, "risk": "FAVORABLE", "reason": self.REASONS["FAVORABLE"],
                "expected_return": 0.0, "category": category}

    def should_trade(self, price: float, category: str = "all") -> bool:
        """Quick check: should the bot consider this contract?"""
        result = self.classify(price, category)
        return result["risk"] in ("NEUTRAL", "FAVORABLE")

    def score(self, price: float, category: str = "all") -> float:
        """Risk score 0-100 (higher = safer/more favorable).

        Maps FLB-implied expected return to a 0-100 scale.
        """
        ret = self._forecaster.expected_return_by_band(price, category)
        # Map: -1.0 -> 0, 0.0 -> 50, +0.5 -> 100
        score = 50 + ret * 100
        return max(0.0, min(100.0, score))


# ---------------------------------------------------------------------------
# Bias Tracker
# ---------------------------------------------------------------------------

@dataclass
class Observation:
    """A single price/outcome observation."""
    price: float
    outcome: int
    timestamp: float
    category: str = "all"


class BiasTracker:
    """Track FLB evolution over time to detect edge decay."""

    def __init__(self):
        self.observations: list[Observation] = []

    def add(self, price: float, outcome: int, timestamp: float,
            category: str = "all"):
        """Add a price/outcome observation."""
        self.observations.append(Observation(price, outcome, timestamp, category))

    def rolling_psi(self, window: int = 50) -> list[dict]:
        """Compute rolling psi coefficient over time."""
        if len(self.observations) < window:
            return []

        results = []
        estimator = FLBEstimator()
        sorted_obs = sorted(self.observations, key=lambda o: o.timestamp)

        for i in range(window, len(sorted_obs) + 1):
            chunk = sorted_obs[i - window:i]
            prices = [o.price for o in chunk]
            outcomes = [o.outcome for o in chunk]
            try:
                fit = estimator.fit(prices, outcomes)
                results.append({
                    "end_timestamp": chunk[-1].timestamp,
                    "psi": fit["psi"],
                    "alpha": fit["alpha"],
                    "n": window,
                })
            except (ValueError, ZeroDivisionError):
                continue

        return results

    def assess_edge_decay(self) -> dict:
        """Assess whether the FLB edge is decaying over time.

        Returns dict with:
        - trend: "increasing", "stable", "decreasing", "insufficient_data"
        - psi_first_half: psi in first half of data
        - psi_second_half: psi in second half of data
        """
        if len(self.observations) < 20:
            return {"trend": "insufficient_data"}

        sorted_obs = sorted(self.observations, key=lambda o: o.timestamp)
        mid = len(sorted_obs) // 2
        first = sorted_obs[:mid]
        second = sorted_obs[mid:]

        estimator = FLBEstimator()

        try:
            fit1 = estimator.fit([o.price for o in first], [o.outcome for o in first])
            fit2 = estimator.fit([o.price for o in second], [o.outcome for o in second])
        except (ValueError, ZeroDivisionError):
            return {"trend": "insufficient_data"}

        psi1 = fit1["psi"]
        psi2 = fit2["psi"]
        delta = psi2 - psi1

        if abs(delta) < 0.005:
            trend = "stable"
        elif delta > 0:
            trend = "increasing"
        else:
            trend = "decreasing"

        return {
            "trend": trend,
            "psi_first_half": psi1,
            "psi_second_half": psi2,
            "delta": delta,
        }


# ---------------------------------------------------------------------------
# Maker/Taker Analyzer
# ---------------------------------------------------------------------------

@dataclass
class Trade:
    """A single trade record."""
    price: float
    size: float
    is_maker: bool
    outcome: int
    category: str = "all"


class MakerTakerAnalyzer:
    """Analyze Maker vs Taker returns.

    Based on the paper's Equation 5-6:
    (1 - pi + delta) * p - (pi - delta) * (1 - p) - theta * p * (1-p) = gamma * [(1-p) + theta * p * (1-p)]
    """

    def __init__(self, theta: float = 0.07):
        self.trades: list[Trade] = []
        self._fee_calc = FeeCalculator(theta=theta)
        self._theta = theta

    def add_trade(self, price: float, size: float, is_maker: bool,
                  outcome: int, category: str = "all"):
        """Add a trade record."""
        self.trades.append(Trade(price, size, is_maker, outcome, category))

    def compare_returns(self) -> dict:
        """Compare average returns for Makers vs Takers."""
        maker_returns = []
        taker_returns = []

        for t in self.trades:
            fee = self._fee_calc.fee(t.price)
            if t.outcome == 1:
                profit = 1.0 - t.price - fee
            else:
                profit = -t.price - fee
            investment = t.price + fee
            ret = profit / investment if investment > 0 else 0

            if t.is_maker:
                maker_returns.append(ret)
            else:
                taker_returns.append(ret)

        maker_avg = sum(maker_returns) / len(maker_returns) if maker_returns else 0
        taker_avg = sum(taker_returns) / len(taker_returns) if taker_returns else 0

        return {
            "maker_return": maker_avg,
            "taker_return": taker_avg,
            "maker_count": len(maker_returns),
            "taker_count": len(taker_returns),
            "maker_advantage": maker_avg - taker_avg,
        }

    def maker_model_price(self, pi: float, delta: float = 0.02,
                          gamma: float = 0.05) -> float:
        """Compute Maker's optimal price using Equation 6 from the paper.

        theta(1+gamma) * p^2 + (1 - theta(1+gamma) + gamma) * p + (delta - pi - gamma) = 0

        Returns the economically meaningful (positive) solution.
        """
        a = self._theta * (1 + gamma)
        b = 1 - self._theta * (1 + gamma) + gamma
        c = delta - pi - gamma

        discriminant = b * b - 4 * a * c
        if discriminant < 0:
            return pi  # Fallback to unbiased price

        sqrt_d = math.sqrt(discriminant)
        p1 = (-b + sqrt_d) / (2 * a)
        p2 = (-b - sqrt_d) / (2 * a)

        # Return the positive solution in (0, 1)
        for p in [p1, p2]:
            if 0 < p < 1:
                return p

        return pi  # Fallback

    def summary(self) -> dict:
        """Summary statistics."""
        makers = [t for t in self.trades if t.is_maker]
        takers = [t for t in self.trades if not t.is_maker]

        return {
            "total_trades": len(self.trades),
            "maker_count": len(makers),
            "taker_count": len(takers),
            "categories": list(set(t.category for t in self.trades)),
        }
