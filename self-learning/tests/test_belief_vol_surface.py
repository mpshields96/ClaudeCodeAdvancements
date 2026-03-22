#!/usr/bin/env python3
"""
Tests for belief_vol_surface.py — MT-26 Tier 3: Belief Volatility Surface (Phase 1).

Based on "Toward Black-Scholes for Prediction Markets" (Dalen, 2025)
arXiv:2510.15205.

Phase 1 covers: logit transforms, Greeks, simple realized vol estimation.
Phase 2 (future): Kalman filter, EM separator, B-spline surface.

TDD: Tests written BEFORE implementation.
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from belief_vol_surface import (
    LogitTransform,
    BeliefGreeks,
    RealizedVolEstimator,
)


class TestLogitTransform(unittest.TestCase):
    """Tests for probability <-> log-odds transforms."""

    def test_logit_50c(self):
        """logit(0.50) = 0."""
        self.assertAlmostEqual(LogitTransform.logit(0.50), 0.0, places=6)

    def test_logit_round_trip(self):
        """sigmoid(logit(p)) == p for various values."""
        for p in [0.01, 0.10, 0.25, 0.50, 0.75, 0.90, 0.99]:
            x = LogitTransform.logit(p)
            p_back = LogitTransform.sigmoid(x)
            self.assertAlmostEqual(p, p_back, places=10)

    def test_sigmoid_bounds(self):
        """sigmoid always returns (0, 1)."""
        self.assertTrue(0 < LogitTransform.sigmoid(-100) < 1)
        self.assertTrue(0 < LogitTransform.sigmoid(100) < 1)
        self.assertAlmostEqual(LogitTransform.sigmoid(0), 0.5)

    def test_logit_extreme_low(self):
        """logit near 0 is very negative."""
        self.assertLess(LogitTransform.logit(0.01), -4)

    def test_logit_extreme_high(self):
        """logit near 1 is very positive."""
        self.assertGreater(LogitTransform.logit(0.99), 4)

    def test_logit_invalid(self):
        """logit(0) and logit(1) raise or return extreme values."""
        with self.assertRaises((ValueError, ZeroDivisionError)):
            LogitTransform.logit(0.0)
        with self.assertRaises((ValueError, ZeroDivisionError)):
            LogitTransform.logit(1.0)

    def test_clamp(self):
        """Clamping keeps probability in valid range."""
        self.assertAlmostEqual(LogitTransform.clamp(0.5), 0.5)
        self.assertGreater(LogitTransform.clamp(0.0), 0.0)
        self.assertLess(LogitTransform.clamp(1.0), 1.0)

    def test_s_prime(self):
        """S'(x) = p(1-p) — derivative of sigmoid."""
        for p in [0.10, 0.30, 0.50, 0.70, 0.90]:
            x = LogitTransform.logit(p)
            expected = p * (1 - p)
            self.assertAlmostEqual(LogitTransform.s_prime(x), expected, places=8)

    def test_s_double_prime(self):
        """S''(x) = p(1-p)(1-2p)."""
        for p in [0.10, 0.30, 0.50, 0.70, 0.90]:
            x = LogitTransform.logit(p)
            expected = p * (1 - p) * (1 - 2 * p)
            self.assertAlmostEqual(LogitTransform.s_double_prime(x), expected, places=8)

    def test_s_prime_max_at_half(self):
        """S'(x) is maximized at x=0 (p=0.5)."""
        at_half = LogitTransform.s_prime(0.0)
        at_other = LogitTransform.s_prime(1.0)
        self.assertGreater(at_half, at_other)


class TestBeliefGreeks(unittest.TestCase):
    """Tests for prediction market Greeks in logit space."""

    def setUp(self):
        self.greeks = BeliefGreeks()

    def test_delta_x_at_50c(self):
        """Delta_x = p(1-p) is maximized at p=0.50."""
        delta = self.greeks.delta_x(0.50)
        self.assertAlmostEqual(delta, 0.25)

    def test_delta_x_symmetric(self):
        """Delta_x(p) == Delta_x(1-p)."""
        self.assertAlmostEqual(self.greeks.delta_x(0.20), self.greeks.delta_x(0.80))

    def test_delta_x_range(self):
        """Delta_x is always in [0, 0.25]."""
        for p in [0.01, 0.10, 0.50, 0.90, 0.99]:
            d = self.greeks.delta_x(p)
            self.assertGreaterEqual(d, 0)
            self.assertLessEqual(d, 0.25)

    def test_gamma_x_at_50c(self):
        """Gamma_x = p(1-p)(1-2p) is zero at p=0.50."""
        gamma = self.greeks.gamma_x(0.50)
        self.assertAlmostEqual(gamma, 0.0, places=10)

    def test_gamma_x_positive_below_half(self):
        """Gamma_x > 0 for p < 0.50."""
        self.assertGreater(self.greeks.gamma_x(0.30), 0)

    def test_gamma_x_negative_above_half(self):
        """Gamma_x < 0 for p > 0.50."""
        self.assertLess(self.greeks.gamma_x(0.70), 0)

    def test_belief_vega(self):
        """Belief vega = sensitivity to sigma_b changes."""
        vega = self.greeks.belief_vega(0.50, sigma_b=0.10, tau=1.0)
        self.assertGreater(vega, 0)

    def test_belief_vega_decreases_near_expiry(self):
        """Vega decreases as time to resolution approaches 0."""
        vega_far = self.greeks.belief_vega(0.50, sigma_b=0.10, tau=10.0)
        vega_near = self.greeks.belief_vega(0.50, sigma_b=0.10, tau=0.1)
        self.assertGreater(vega_far, vega_near)

    def test_martingale_drift(self):
        """Martingale drift computed from sigma_b."""
        drift = self.greeks.martingale_drift(p=0.50, sigma_b=0.10)
        # At p=0.50: S''(x)=0 so drift is only from jump compensation
        # With no jumps, drift should be near 0
        self.assertAlmostEqual(drift, 0.0, places=4)

    def test_martingale_drift_nonzero(self):
        """Drift is nonzero away from p=0.50."""
        drift = self.greeks.martingale_drift(p=0.30, sigma_b=0.20)
        self.assertNotAlmostEqual(drift, 0.0, places=4)

    def test_all_greeks(self):
        """all_greeks returns complete set."""
        result = self.greeks.all_greeks(p=0.50, sigma_b=0.10, tau=1.0)
        self.assertIn("delta_x", result)
        self.assertIn("gamma_x", result)
        self.assertIn("belief_vega", result)
        self.assertIn("martingale_drift", result)


class TestRealizedVolEstimator(unittest.TestCase):
    """Tests for simple realized belief volatility estimation."""

    def setUp(self):
        self.estimator = RealizedVolEstimator()

    def test_constant_prices_zero_vol(self):
        """Constant prices imply zero volatility."""
        prices = [0.50] * 20
        timestamps = list(range(20))
        vol = self.estimator.estimate(prices, timestamps)
        self.assertAlmostEqual(vol, 0.0, places=4)

    def test_volatile_prices_positive_vol(self):
        """Varying prices produce positive volatility."""
        import random
        random.seed(42)
        prices = [0.50 + random.gauss(0, 0.05) for _ in range(50)]
        prices = [max(0.01, min(0.99, p)) for p in prices]
        timestamps = list(range(50))
        vol = self.estimator.estimate(prices, timestamps)
        self.assertGreater(vol, 0)

    def test_minimum_data_points(self):
        """Requires minimum number of price observations."""
        vol = self.estimator.estimate([0.50, 0.51], [0, 1])
        # Should return something, even if noisy
        self.assertIsInstance(vol, float)

    def test_empty_returns_zero(self):
        """Empty or single-point data returns 0."""
        self.assertAlmostEqual(self.estimator.estimate([], []), 0.0)
        self.assertAlmostEqual(self.estimator.estimate([0.5], [0]), 0.0)

    def test_rolling_vol(self):
        """Rolling volatility produces a time series."""
        import random
        random.seed(42)
        prices = [0.50 + random.gauss(0, 0.05) for _ in range(100)]
        prices = [max(0.01, min(0.99, p)) for p in prices]
        timestamps = list(range(100))

        vols = self.estimator.rolling(prices, timestamps, window=20)
        self.assertTrue(len(vols) > 0)
        # All values should be non-negative
        for v in vols:
            self.assertGreaterEqual(v["vol"], 0)

    def test_annualized_vol(self):
        """Can annualize volatility."""
        import random
        random.seed(42)
        prices = [0.50 + random.gauss(0, 0.05) for _ in range(50)]
        prices = [max(0.01, min(0.99, p)) for p in prices]
        timestamps = list(range(50))

        vol = self.estimator.estimate(prices, timestamps)
        annual = self.estimator.annualize(vol, observations_per_day=96)  # 15-min bars
        self.assertGreater(annual, vol)


if __name__ == "__main__":
    unittest.main()
