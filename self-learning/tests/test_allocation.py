#!/usr/bin/env python3
"""Tests for allocation.py — MT-37 Phase 5: Portfolio allocation engines.

TDD: Tests written before implementation.

Covers:
- Equal-weight (1/N) baseline allocation
- Risk parity (inverse-volatility weighting)
- Black-Litterman model (market-cap prior + user views)
- Constraint enforcement (min/max weights, no short)
- Rebalancing threshold detection
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestEqualWeight(unittest.TestCase):
    """Test 1/N equal-weight allocation."""

    def test_two_assets(self):
        from allocation import equal_weight
        w = equal_weight(["AAPL", "GOOG"])
        self.assertAlmostEqual(w["AAPL"], 0.5)
        self.assertAlmostEqual(w["GOOG"], 0.5)

    def test_five_assets(self):
        from allocation import equal_weight
        tickers = ["A", "B", "C", "D", "E"]
        w = equal_weight(tickers)
        for t in tickers:
            self.assertAlmostEqual(w[t], 0.2, places=6)

    def test_weights_sum_to_one(self):
        from allocation import equal_weight
        w = equal_weight(["X", "Y", "Z"])
        self.assertAlmostEqual(sum(w.values()), 1.0, places=8)

    def test_single_asset(self):
        from allocation import equal_weight
        w = equal_weight(["AAPL"])
        self.assertAlmostEqual(w["AAPL"], 1.0)

    def test_empty_raises(self):
        from allocation import equal_weight
        with self.assertRaises(ValueError):
            equal_weight([])


class TestRiskParity(unittest.TestCase):
    """Test inverse-volatility risk parity allocation."""

    def test_equal_vol_gives_equal_weight(self):
        from allocation import risk_parity
        vols = {"AAPL": 0.20, "GOOG": 0.20, "MSFT": 0.20}
        w = risk_parity(vols)
        for v in w.values():
            self.assertAlmostEqual(v, 1/3, places=6)

    def test_higher_vol_gets_lower_weight(self):
        from allocation import risk_parity
        vols = {"LOW_VOL": 0.10, "HIGH_VOL": 0.30}
        w = risk_parity(vols)
        self.assertGreater(w["LOW_VOL"], w["HIGH_VOL"])

    def test_weights_sum_to_one(self):
        from allocation import risk_parity
        vols = {"A": 0.15, "B": 0.25, "C": 0.35}
        w = risk_parity(vols)
        self.assertAlmostEqual(sum(w.values()), 1.0, places=8)

    def test_inverse_proportional(self):
        from allocation import risk_parity
        vols = {"A": 0.10, "B": 0.20}
        w = risk_parity(vols)
        # A has half the vol, should get ~2/3 weight
        self.assertAlmostEqual(w["A"], 2/3, places=4)
        self.assertAlmostEqual(w["B"], 1/3, places=4)

    def test_zero_vol_raises(self):
        from allocation import risk_parity
        with self.assertRaises(ValueError):
            risk_parity({"A": 0.0, "B": 0.20})

    def test_empty_raises(self):
        from allocation import risk_parity
        with self.assertRaises(ValueError):
            risk_parity({})


class TestBlackLitterman(unittest.TestCase):
    """Test Black-Litterman allocation model."""

    def test_no_views_returns_market_weights(self):
        from allocation import black_litterman
        market_weights = {"AAPL": 0.4, "GOOG": 0.3, "MSFT": 0.3}
        covariance = {
            "AAPL": {"AAPL": 0.04, "GOOG": 0.01, "MSFT": 0.01},
            "GOOG": {"AAPL": 0.01, "GOOG": 0.06, "MSFT": 0.02},
            "MSFT": {"AAPL": 0.01, "GOOG": 0.02, "MSFT": 0.05},
        }
        w = black_litterman(market_weights, covariance, views=[])
        # With no views, output should approximate market weights
        for t in market_weights:
            self.assertAlmostEqual(w[t], market_weights[t], places=2)

    def test_bullish_view_increases_weight(self):
        from allocation import black_litterman, View
        market_weights = {"AAPL": 0.5, "GOOG": 0.5}
        covariance = {
            "AAPL": {"AAPL": 0.04, "GOOG": 0.01},
            "GOOG": {"AAPL": 0.01, "GOOG": 0.04},
        }
        views = [View(ticker="AAPL", expected_return=0.15, confidence=0.8)]
        w = black_litterman(market_weights, covariance, views=views)
        self.assertGreater(w["AAPL"], 0.5)

    def test_weights_sum_to_one(self):
        from allocation import black_litterman
        market_weights = {"A": 0.5, "B": 0.5}
        covariance = {
            "A": {"A": 0.04, "B": 0.01},
            "B": {"A": 0.01, "B": 0.04},
        }
        w = black_litterman(market_weights, covariance, views=[])
        self.assertAlmostEqual(sum(w.values()), 1.0, places=4)

    def test_low_confidence_view_has_small_effect(self):
        from allocation import black_litterman, View
        market_weights = {"A": 0.5, "B": 0.5}
        covariance = {
            "A": {"A": 0.04, "B": 0.01},
            "B": {"A": 0.01, "B": 0.04},
        }
        views_high = [View(ticker="A", expected_return=0.20, confidence=0.9)]
        views_low = [View(ticker="A", expected_return=0.20, confidence=0.1)]
        w_high = black_litterman(market_weights, covariance, views=views_high)
        w_low = black_litterman(market_weights, covariance, views=views_low)
        # High confidence should move weights more than low confidence
        self.assertGreater(abs(w_high["A"] - 0.5), abs(w_low["A"] - 0.5))


class TestConstraints(unittest.TestCase):
    """Test weight constraint enforcement."""

    def test_min_weight(self):
        from allocation import apply_constraints
        weights = {"A": 0.01, "B": 0.99}
        constrained = apply_constraints(weights, min_weight=0.05)
        self.assertGreaterEqual(constrained["A"], 0.05)
        self.assertAlmostEqual(sum(constrained.values()), 1.0, places=6)

    def test_max_weight(self):
        from allocation import apply_constraints
        weights = {"A": 0.95, "B": 0.05}
        constrained = apply_constraints(weights, max_weight=0.60)
        self.assertLessEqual(constrained["A"], 0.60 + 1e-6)
        self.assertAlmostEqual(sum(constrained.values()), 1.0, places=6)

    def test_no_short(self):
        from allocation import apply_constraints
        weights = {"A": -0.1, "B": 1.1}
        constrained = apply_constraints(weights, no_short=True)
        self.assertGreaterEqual(constrained["A"], 0.0)
        self.assertAlmostEqual(sum(constrained.values()), 1.0, places=6)

    def test_already_valid_unchanged(self):
        from allocation import apply_constraints
        weights = {"A": 0.4, "B": 0.6}
        constrained = apply_constraints(weights, min_weight=0.05, max_weight=0.80)
        self.assertAlmostEqual(constrained["A"], 0.4, places=6)
        self.assertAlmostEqual(constrained["B"], 0.6, places=6)


class TestRebalanceTrigger(unittest.TestCase):
    """Test rebalancing threshold detection."""

    def test_within_threshold_no_rebalance(self):
        from allocation import needs_rebalance
        current = {"A": 0.48, "B": 0.52}
        target = {"A": 0.50, "B": 0.50}
        self.assertFalse(needs_rebalance(current, target, threshold=0.05))

    def test_exceeds_threshold_needs_rebalance(self):
        from allocation import needs_rebalance
        current = {"A": 0.35, "B": 0.65}
        target = {"A": 0.50, "B": 0.50}
        self.assertTrue(needs_rebalance(current, target, threshold=0.05))

    def test_exact_match_no_rebalance(self):
        from allocation import needs_rebalance
        w = {"A": 0.5, "B": 0.5}
        self.assertFalse(needs_rebalance(w, w, threshold=0.01))

    def test_zero_threshold_always_rebalance_if_different(self):
        from allocation import needs_rebalance
        current = {"A": 0.500001, "B": 0.499999}
        target = {"A": 0.50, "B": 0.50}
        self.assertTrue(needs_rebalance(current, target, threshold=0.0))


class TestViewDataclass(unittest.TestCase):
    """Test View dataclass."""

    def test_basic_view(self):
        from allocation import View
        v = View(ticker="AAPL", expected_return=0.10, confidence=0.7)
        self.assertEqual(v.ticker, "AAPL")
        self.assertAlmostEqual(v.expected_return, 0.10)
        self.assertAlmostEqual(v.confidence, 0.7)

    def test_confidence_bounds(self):
        from allocation import View
        # Confidence should be 0-1
        v = View(ticker="AAPL", expected_return=0.10, confidence=0.0)
        self.assertAlmostEqual(v.confidence, 0.0)
        v = View(ticker="AAPL", expected_return=0.10, confidence=1.0)
        self.assertAlmostEqual(v.confidence, 1.0)


class TestAllocationResult(unittest.TestCase):
    """Test AllocationResult container."""

    def test_construction(self):
        from allocation import AllocationResult
        result = AllocationResult(
            weights={"A": 0.6, "B": 0.4},
            method="risk_parity",
            metadata={"note": "test"},
        )
        self.assertEqual(result.method, "risk_parity")
        self.assertAlmostEqual(result.weights["A"], 0.6)

    def test_to_dict(self):
        from allocation import AllocationResult
        result = AllocationResult(
            weights={"A": 0.6, "B": 0.4},
            method="equal_weight",
        )
        d = result.to_dict()
        self.assertIn("weights", d)
        self.assertIn("method", d)

    def test_summary(self):
        from allocation import AllocationResult
        result = AllocationResult(
            weights={"AAPL": 0.6, "GOOG": 0.4},
            method="black_litterman",
        )
        s = result.summary()
        self.assertIn("AAPL", s)
        self.assertIn("60.0%", s)


if __name__ == "__main__":
    unittest.main()
