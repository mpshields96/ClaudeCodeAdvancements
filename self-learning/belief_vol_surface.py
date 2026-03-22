#!/usr/bin/env python3
"""
belief_vol_surface.py — MT-26 Tier 3: Belief Volatility Surface (Phase 1).

Based on "Toward Black-Scholes for Prediction Markets" (Dalen, 2025)
arXiv:2510.15205. Implements the logit jump-diffusion (RN-JD) model
for prediction market pricing.

Phase 1 (this module): Core transforms, analytical Greeks, simple vol estimation.
Phase 2 (future): Full Kalman filter, EM separator, B-spline surface builder.

Components:
- LogitTransform: p <-> x = logit(p) conversions, S'(x), S''(x)
- BeliefGreeks: Delta_x, Gamma_x, belief-vega, martingale drift
- RealizedVolEstimator: Rolling realized belief volatility from price history

The key insight: transform bounded probability p in (0,1) to unbounded log-odds
x = log(p/(1-p)), then apply standard stochastic calculus. This is the prediction
market analog of the Black-Scholes log-price transform.

Stdlib only. No external dependencies.
"""

import math
from typing import Optional


# ---------------------------------------------------------------------------
# Logit Transform
# ---------------------------------------------------------------------------

class LogitTransform:
    """Probability <-> log-odds transformations.

    Core equations from arXiv:2510.15205:
    x = logit(p) = log(p / (1-p))
    p = S(x) = 1 / (1 + exp(-x))  (sigmoid)
    S'(x) = p(1-p)
    S''(x) = p(1-p)(1-2p)
    """

    EPSILON = 1e-10  # Clamp boundary to avoid log(0)

    @staticmethod
    def logit(p: float) -> float:
        """Transform probability to log-odds: x = log(p / (1-p))."""
        if p <= 0.0 or p >= 1.0:
            raise ValueError(f"logit requires 0 < p < 1, got {p}")
        return math.log(p / (1 - p))

    @staticmethod
    def sigmoid(x: float) -> float:
        """Transform log-odds to probability: p = 1 / (1 + exp(-x))."""
        if x >= 36:
            return 1.0 - 1e-15
        if x <= -36:
            return 1e-15
        return 1.0 / (1.0 + math.exp(-x))

    @classmethod
    def clamp(cls, p: float) -> float:
        """Clamp probability to valid range (epsilon, 1-epsilon)."""
        return max(cls.EPSILON, min(1.0 - cls.EPSILON, p))

    @staticmethod
    def s_prime(x: float) -> float:
        """First derivative of sigmoid: S'(x) = p(1-p).

        This is the Delta in probability space.
        """
        p = LogitTransform.sigmoid(x)
        return p * (1 - p)

    @staticmethod
    def s_double_prime(x: float) -> float:
        """Second derivative of sigmoid: S''(x) = p(1-p)(1-2p).

        This determines the convexity adjustment in the martingale drift.
        """
        p = LogitTransform.sigmoid(x)
        return p * (1 - p) * (1 - 2 * p)


# ---------------------------------------------------------------------------
# Belief Greeks
# ---------------------------------------------------------------------------

class BeliefGreeks:
    """Prediction market Greeks in logit space.

    Analogous to Black-Scholes Greeks but for event contracts:
    - Delta_x: sensitivity of p to changes in log-odds (= p(1-p))
    - Gamma_x: rate of change of Delta_x (= p(1-p)(1-2p))
    - Belief-vega: sensitivity to belief volatility sigma_b
    - Martingale drift: the no-arbitrage drift constraint
    """

    def delta_x(self, p: float) -> float:
        """Delta in logit space: dp/dx = p(1-p).

        Maximum at p=0.50 (= 0.25).
        Symmetric: delta(p) == delta(1-p).
        """
        return p * (1 - p)

    def gamma_x(self, p: float) -> float:
        """Gamma in logit space: d^2p/dx^2 = p(1-p)(1-2p).

        Zero at p=0.50.
        Positive for p < 0.50, negative for p > 0.50.
        """
        return p * (1 - p) * (1 - 2 * p)

    def belief_vega(self, p: float, sigma_b: float, tau: float) -> float:
        """Sensitivity of option value to belief volatility.

        vega = p(1-p) * sqrt(tau) * sigma_b
        Analogous to BS vega but in probability space.

        Args:
            p: Current probability.
            sigma_b: Current belief volatility.
            tau: Time to resolution (in any consistent unit).
        """
        if tau <= 0:
            return 0.0
        return p * (1 - p) * math.sqrt(tau) * sigma_b

    def martingale_drift(self, p: float, sigma_b: float) -> float:
        """Martingale drift constraint from Equation 3.

        mu = -[0.5 * S''(x) * sigma_b^2] / S'(x)

        This is the drift required for p_t to be a Q-martingale.
        Phase 1: no jump compensation (jump_lambda=0).

        Args:
            p: Current probability.
            sigma_b: Current belief volatility.
        """
        p_clamped = LogitTransform.clamp(p)
        x = LogitTransform.logit(p_clamped)
        sp = LogitTransform.s_prime(x)
        spp = LogitTransform.s_double_prime(x)

        if abs(sp) < 1e-15:
            return 0.0

        return -(0.5 * spp * sigma_b ** 2) / sp

    def all_greeks(self, p: float, sigma_b: float, tau: float) -> dict:
        """Compute all Greeks at once."""
        return {
            "delta_x": self.delta_x(p),
            "gamma_x": self.gamma_x(p),
            "belief_vega": self.belief_vega(p, sigma_b, tau),
            "martingale_drift": self.martingale_drift(p, sigma_b),
            "p": p,
            "x": LogitTransform.logit(LogitTransform.clamp(p)),
            "sigma_b": sigma_b,
            "tau": tau,
        }


# ---------------------------------------------------------------------------
# Realized Volatility Estimator
# ---------------------------------------------------------------------------

class RealizedVolEstimator:
    """Simple realized belief volatility from price history.

    Phase 1 approach: compute volatility of log-odds changes.
    This is the prediction market analog of realized volatility
    computed from log-returns in equity markets.

    Phase 2 will replace this with Kalman-filtered estimates.
    """

    def estimate(self, prices: list[float], timestamps: list[float]) -> float:
        """Estimate realized belief volatility from a price series.

        Computes standard deviation of log-odds changes:
        vol = std(dx_t) where dx_t = logit(p_{t+1}) - logit(p_t)

        Args:
            prices: Observed probabilities (0 to 1).
            timestamps: Corresponding timestamps.

        Returns:
            Realized belief volatility (annualization not applied).
        """
        if len(prices) < 2:
            return 0.0

        # Convert prices to log-odds
        log_odds = []
        for p in prices:
            clamped = LogitTransform.clamp(p)
            log_odds.append(LogitTransform.logit(clamped))

        # Compute changes
        changes = [log_odds[i + 1] - log_odds[i] for i in range(len(log_odds) - 1)]

        if not changes:
            return 0.0

        # Standard deviation
        n = len(changes)
        mean = sum(changes) / n
        variance = sum((c - mean) ** 2 for c in changes) / max(n - 1, 1)

        return math.sqrt(variance)

    def rolling(self, prices: list[float], timestamps: list[float],
                window: int = 20) -> list[dict]:
        """Compute rolling belief volatility.

        Returns list of {timestamp, vol} dicts.
        """
        if len(prices) < window:
            return []

        results = []
        for i in range(window, len(prices) + 1):
            chunk_prices = prices[i - window:i]
            chunk_ts = timestamps[i - window:i]
            vol = self.estimate(chunk_prices, chunk_ts)
            results.append({
                "timestamp": chunk_ts[-1],
                "vol": vol,
                "window": window,
            })

        return results

    def annualize(self, vol: float, observations_per_day: int = 96) -> float:
        """Annualize a per-observation volatility.

        Args:
            vol: Per-observation volatility.
            observations_per_day: Number of observations per day
                (e.g., 96 for 15-min bars, 1440 for 1-min bars).

        Returns:
            Annualized volatility (assuming 365 trading days for crypto).
        """
        return vol * math.sqrt(observations_per_day * 365)
