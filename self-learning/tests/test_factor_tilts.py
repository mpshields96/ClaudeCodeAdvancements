#!/usr/bin/env python3
"""Tests for factor_tilts.py — MT-37 Phase 6: Factor overlay system.

TDD: Tests written before implementation.

Covers:
- FactorScore dataclass
- Individual factor scoring (value, momentum, quality, low-vol)
- Composite factor tilt calculation
- Weight adjustment from base allocation
- Tilt magnitude controls
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestFactorScore(unittest.TestCase):
    """Test FactorScore dataclass."""

    def test_basic_construction(self):
        from factor_tilts import FactorScore
        fs = FactorScore(ticker="AAPL", factor="value", score=0.7, z_score=1.2)
        self.assertEqual(fs.ticker, "AAPL")
        self.assertEqual(fs.factor, "value")
        self.assertAlmostEqual(fs.score, 0.7)
        self.assertAlmostEqual(fs.z_score, 1.2)

    def test_score_bounds(self):
        from factor_tilts import FactorScore
        # Scores should be 0-1 normalized
        fs = FactorScore(ticker="X", factor="momentum", score=0.0, z_score=-2.0)
        self.assertAlmostEqual(fs.score, 0.0)


class TestValueScore(unittest.TestCase):
    """Test value factor scoring (cheap = high score)."""

    def test_low_pe_high_score(self):
        from factor_tilts import score_value
        # Low P/E = cheap = high value score
        score = score_value(pe_ratio=10.0, pb_ratio=1.0)
        self.assertGreater(score, 0.5)

    def test_high_pe_low_score(self):
        from factor_tilts import score_value
        score = score_value(pe_ratio=50.0, pb_ratio=5.0)
        self.assertLess(score, 0.5)

    def test_none_inputs_return_neutral(self):
        from factor_tilts import score_value
        score = score_value(pe_ratio=None, pb_ratio=None)
        self.assertAlmostEqual(score, 0.5)

    def test_negative_pe_treated_as_expensive(self):
        from factor_tilts import score_value
        # Negative P/E = losses = low value score
        score = score_value(pe_ratio=-5.0, pb_ratio=None)
        self.assertLess(score, 0.3)


class TestMomentumScore(unittest.TestCase):
    """Test momentum factor scoring (12-1 month return)."""

    def test_positive_momentum(self):
        from factor_tilts import score_momentum
        score = score_momentum(return_12m=0.30, return_1m=0.05)
        self.assertGreater(score, 0.5)

    def test_negative_momentum(self):
        from factor_tilts import score_momentum
        score = score_momentum(return_12m=-0.20, return_1m=-0.05)
        self.assertLess(score, 0.5)

    def test_12_minus_1_month(self):
        from factor_tilts import score_momentum
        # Momentum = 12m return - 1m return (Carhart 1997, Jegadeesh & Titman 1993)
        # Strong 12m but weak recent = still good momentum
        score = score_momentum(return_12m=0.25, return_1m=-0.02)
        self.assertGreater(score, 0.5)

    def test_none_returns_neutral(self):
        from factor_tilts import score_momentum
        score = score_momentum(return_12m=None, return_1m=None)
        self.assertAlmostEqual(score, 0.5)


class TestQualityScore(unittest.TestCase):
    """Test quality factor scoring (ROE, debt/equity, earnings stability)."""

    def test_high_quality(self):
        from factor_tilts import score_quality
        score = score_quality(roe=0.25, debt_to_equity=0.3, earnings_stability=0.9)
        self.assertGreater(score, 0.6)

    def test_low_quality(self):
        from factor_tilts import score_quality
        score = score_quality(roe=0.02, debt_to_equity=3.0, earnings_stability=0.2)
        self.assertLess(score, 0.4)

    def test_partial_data(self):
        from factor_tilts import score_quality
        # Missing some inputs should still produce a score
        score = score_quality(roe=0.15, debt_to_equity=None, earnings_stability=None)
        self.assertGreater(score, 0.0)
        self.assertLess(score, 1.0)


class TestLowVolScore(unittest.TestCase):
    """Test low-volatility factor scoring."""

    def test_low_vol_high_score(self):
        from factor_tilts import score_low_vol
        score = score_low_vol(volatility=0.10, market_vol=0.20)
        self.assertGreater(score, 0.5)

    def test_high_vol_low_score(self):
        from factor_tilts import score_low_vol
        score = score_low_vol(volatility=0.40, market_vol=0.20)
        self.assertLess(score, 0.5)

    def test_equal_vol_neutral(self):
        from factor_tilts import score_low_vol
        score = score_low_vol(volatility=0.20, market_vol=0.20)
        self.assertAlmostEqual(score, 0.5, places=1)


class TestCompositeTilt(unittest.TestCase):
    """Test composite factor tilt from multiple factors."""

    def test_composite_average(self):
        from factor_tilts import compute_composite_tilt
        scores = {"value": 0.8, "momentum": 0.6, "quality": 0.7, "low_vol": 0.5}
        tilt = compute_composite_tilt(scores)
        # Should be weighted average centered on 0 (score - 0.5)
        self.assertGreater(tilt, 0.0)

    def test_neutral_scores_zero_tilt(self):
        from factor_tilts import compute_composite_tilt
        scores = {"value": 0.5, "momentum": 0.5, "quality": 0.5, "low_vol": 0.5}
        tilt = compute_composite_tilt(scores)
        self.assertAlmostEqual(tilt, 0.0, places=4)

    def test_custom_weights(self):
        from factor_tilts import compute_composite_tilt
        scores = {"value": 1.0, "momentum": 0.0}
        # Equal factor weights: (1.0-0.5)*0.5 + (0.0-0.5)*0.5 = 0
        tilt_equal = compute_composite_tilt(scores, factor_weights={"value": 0.5, "momentum": 0.5})
        self.assertAlmostEqual(tilt_equal, 0.0, places=4)

        # Value-only: tilt should be positive
        tilt_value = compute_composite_tilt(scores, factor_weights={"value": 1.0, "momentum": 0.0})
        self.assertGreater(tilt_value, 0.0)

    def test_empty_scores_zero_tilt(self):
        from factor_tilts import compute_composite_tilt
        self.assertAlmostEqual(compute_composite_tilt({}), 0.0)


class TestApplyTilts(unittest.TestCase):
    """Test applying factor tilts to base allocation weights."""

    def test_positive_tilt_increases_weight(self):
        from factor_tilts import apply_tilts
        base = {"AAPL": 0.5, "GOOG": 0.5}
        tilts = {"AAPL": 0.1, "GOOG": -0.1}
        adjusted = apply_tilts(base, tilts, magnitude=1.0)
        self.assertGreater(adjusted["AAPL"], 0.5)
        self.assertLess(adjusted["GOOG"], 0.5)

    def test_weights_still_sum_to_one(self):
        from factor_tilts import apply_tilts
        base = {"A": 0.3, "B": 0.3, "C": 0.4}
        tilts = {"A": 0.2, "B": -0.1, "C": -0.05}
        adjusted = apply_tilts(base, tilts, magnitude=0.5)
        self.assertAlmostEqual(sum(adjusted.values()), 1.0, places=6)

    def test_zero_magnitude_no_change(self):
        from factor_tilts import apply_tilts
        base = {"A": 0.6, "B": 0.4}
        tilts = {"A": 0.5, "B": -0.5}
        adjusted = apply_tilts(base, tilts, magnitude=0.0)
        self.assertAlmostEqual(adjusted["A"], 0.6, places=6)
        self.assertAlmostEqual(adjusted["B"], 0.4, places=6)

    def test_no_negative_weights(self):
        from factor_tilts import apply_tilts
        base = {"A": 0.1, "B": 0.9}
        tilts = {"A": -0.5, "B": 0.5}
        adjusted = apply_tilts(base, tilts, magnitude=1.0)
        self.assertGreaterEqual(adjusted["A"], 0.0)
        self.assertAlmostEqual(sum(adjusted.values()), 1.0, places=6)


class TestTiltResult(unittest.TestCase):
    """Test TiltResult container."""

    def test_construction(self):
        from factor_tilts import TiltResult
        result = TiltResult(
            base_weights={"A": 0.5, "B": 0.5},
            tilted_weights={"A": 0.6, "B": 0.4},
            factor_scores={"A": {"value": 0.8}, "B": {"value": 0.3}},
            tilts={"A": 0.1, "B": -0.1},
        )
        self.assertAlmostEqual(result.tilted_weights["A"], 0.6)

    def test_to_dict(self):
        from factor_tilts import TiltResult
        result = TiltResult(
            base_weights={"A": 0.5, "B": 0.5},
            tilted_weights={"A": 0.6, "B": 0.4},
            factor_scores={},
            tilts={"A": 0.1, "B": -0.1},
        )
        d = result.to_dict()
        self.assertIn("base_weights", d)
        self.assertIn("tilted_weights", d)


if __name__ == "__main__":
    unittest.main()
