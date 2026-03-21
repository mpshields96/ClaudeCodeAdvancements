#!/usr/bin/env python3
"""Tests for regime_detector.py — MT-26 Phase 1: Market Regime Detection."""

import os
import sys
import math
import unittest

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODULE_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, MODULE_DIR)
sys.path.insert(0, os.path.dirname(MODULE_DIR))


def _make_candle(close, high=None, low=None, volume=1000):
    """Helper to create a price candle dict."""
    if high is None:
        high = close * 1.005
    if low is None:
        low = close * 0.995
    return {"close": close, "high": high, "low": low, "volume": volume}


def _trending_up_candles(n=60, start=100.0, step=0.5):
    """Generate steadily rising price candles."""
    return [_make_candle(start + i * step) for i in range(n)]


def _trending_down_candles(n=60, start=100.0, step=0.5):
    """Generate steadily falling price candles."""
    return [_make_candle(start - i * step) for i in range(n)]


def _mean_reverting_candles(n=60, center=100.0, amplitude=1.0):
    """Generate oscillating price candles around a center."""
    import math
    return [_make_candle(center + amplitude * math.sin(i * 0.5)) for i in range(n)]


def _chaotic_candles(n=60, base=100.0):
    """Generate high-volatility erratic price candles with no net drift."""
    import random
    random.seed(42)
    candles = []
    price = base
    for i in range(n):
        # Large random jumps with mean-zero drift to avoid accidental trend
        jump = random.uniform(-8, 8)
        # Pull back toward base to prevent trend
        pull = (base - price) * 0.1
        price += jump + pull
        candles.append(_make_candle(
            price,
            high=price + random.uniform(2, 5),
            low=price - random.uniform(2, 5),
        ))
    return candles


class TestRegimeDetector(unittest.TestCase):
    """Test the RegimeDetector class."""

    def setUp(self):
        from regime_detector import RegimeDetector
        self.detector = RegimeDetector()

    def test_classify_returns_dict(self):
        """classify() returns a dict with required keys."""
        candles = _trending_up_candles(30)
        result = self.detector.classify(candles)
        self.assertIsInstance(result, dict)
        self.assertIn("regime", result)
        self.assertIn("confidence", result)
        self.assertIn("metrics", result)

    def test_regime_is_valid_value(self):
        """Regime is one of the valid enum values."""
        candles = _trending_up_candles(30)
        result = self.detector.classify(candles)
        self.assertIn(result["regime"], ["TRENDING", "MEAN_REVERTING", "CHAOTIC", "UNKNOWN"])

    def test_confidence_range(self):
        """Confidence is between 0 and 1."""
        candles = _trending_up_candles(30)
        result = self.detector.classify(candles)
        self.assertGreaterEqual(result["confidence"], 0.0)
        self.assertLessEqual(result["confidence"], 1.0)

    def test_trending_up_detected(self):
        """Strong uptrend should be classified as TRENDING."""
        candles = _trending_up_candles(60, step=1.0)
        result = self.detector.classify(candles)
        self.assertEqual(result["regime"], "TRENDING")

    def test_trending_down_detected(self):
        """Strong downtrend should be classified as TRENDING."""
        candles = _trending_down_candles(60, step=1.0)
        result = self.detector.classify(candles)
        self.assertEqual(result["regime"], "TRENDING")

    def test_mean_reverting_detected(self):
        """Oscillating prices should be classified as MEAN_REVERTING."""
        candles = _mean_reverting_candles(60, amplitude=2.0)
        result = self.detector.classify(candles)
        self.assertEqual(result["regime"], "MEAN_REVERTING")

    def test_chaotic_detected(self):
        """High-volatility erratic prices should be classified as CHAOTIC."""
        candles = _chaotic_candles(60)
        result = self.detector.classify(candles)
        self.assertEqual(result["regime"], "CHAOTIC")

    def test_insufficient_data(self):
        """Too few candles returns UNKNOWN."""
        candles = _trending_up_candles(3)
        result = self.detector.classify(candles)
        self.assertEqual(result["regime"], "UNKNOWN")
        self.assertEqual(result["confidence"], 0.0)

    def test_metrics_contains_volatility(self):
        """Metrics dict includes volatility measurement."""
        candles = _trending_up_candles(30)
        result = self.detector.classify(candles)
        self.assertIn("volatility", result["metrics"])
        self.assertIsInstance(result["metrics"]["volatility"], float)

    def test_metrics_contains_trend_strength(self):
        """Metrics dict includes trend strength."""
        candles = _trending_up_candles(30)
        result = self.detector.classify(candles)
        self.assertIn("trend_strength", result["metrics"])

    def test_metrics_contains_mean_reversion(self):
        """Metrics dict includes mean reversion score."""
        candles = _trending_up_candles(30)
        result = self.detector.classify(candles)
        self.assertIn("mean_reversion_score", result["metrics"])

    def test_flat_market(self):
        """Flat market (no movement) should not be CHAOTIC."""
        candles = [_make_candle(100.0) for _ in range(30)]
        result = self.detector.classify(candles)
        self.assertNotEqual(result["regime"], "CHAOTIC")


class TestRegimeMetrics(unittest.TestCase):
    """Test individual metric calculations."""

    def setUp(self):
        from regime_detector import RegimeDetector
        self.detector = RegimeDetector()

    def test_volatility_trending_vs_chaotic(self):
        """Chaotic candles have higher volatility than trending."""
        trending = _trending_up_candles(60, step=0.3)
        chaotic = _chaotic_candles(60)

        r_trend = self.detector.classify(trending)
        r_chaotic = self.detector.classify(chaotic)

        self.assertGreater(
            r_chaotic["metrics"]["volatility"],
            r_trend["metrics"]["volatility"],
        )

    def test_trend_strength_uptrend(self):
        """Strong uptrend has high trend_strength."""
        candles = _trending_up_candles(60, step=1.0)
        result = self.detector.classify(candles)
        self.assertGreater(result["metrics"]["trend_strength"], 0.5)

    def test_trend_strength_mean_reverting_low(self):
        """Mean-reverting market has low trend strength."""
        candles = _mean_reverting_candles(60, amplitude=2.0)
        result = self.detector.classify(candles)
        self.assertLess(result["metrics"]["trend_strength"], 0.5)

    def test_mean_reversion_score_oscillating(self):
        """Oscillating prices have high mean reversion score."""
        candles = _mean_reverting_candles(60, amplitude=2.0)
        result = self.detector.classify(candles)
        self.assertGreater(result["metrics"]["mean_reversion_score"], 0.3)


class TestRegimeDetectorCLI(unittest.TestCase):
    """Test CLI interface."""

    def test_from_json_list(self):
        """classify_from_prices accepts a list of floats."""
        from regime_detector import RegimeDetector
        detector = RegimeDetector()
        prices = [100 + i * 0.5 for i in range(30)]
        result = detector.classify_from_prices(prices)
        self.assertIn("regime", result)
        self.assertIn("confidence", result)

    def test_from_json_list_too_short(self):
        """Short price list returns UNKNOWN."""
        from regime_detector import RegimeDetector
        detector = RegimeDetector()
        result = detector.classify_from_prices([100, 101, 102])
        self.assertEqual(result["regime"], "UNKNOWN")


class TestRegimeTradeAdvice(unittest.TestCase):
    """Test trade advice generation from regime."""

    def setUp(self):
        from regime_detector import RegimeDetector
        self.detector = RegimeDetector()

    def test_trending_advice(self):
        """TRENDING regime suggests normal trading."""
        candles = _trending_up_candles(60, step=1.0)
        result = self.detector.classify(candles)
        self.assertIn("advice", result)
        self.assertIn("trade", result["advice"].lower())

    def test_chaotic_advice(self):
        """CHAOTIC regime suggests caution."""
        candles = _chaotic_candles(60)
        result = self.detector.classify(candles)
        self.assertIn("advice", result)
        # Should suggest skip/reduce/caution
        advice_lower = result["advice"].lower()
        self.assertTrue(
            any(w in advice_lower for w in ["skip", "reduce", "caution", "avoid"]),
            f"Advice should suggest caution for CHAOTIC regime, got: {result['advice']}"
        )

    def test_unknown_advice(self):
        """UNKNOWN regime gives insufficient data message."""
        candles = _trending_up_candles(3)
        result = self.detector.classify(candles)
        self.assertIn("advice", result)
        self.assertIn("insufficient", result["advice"].lower())


if __name__ == "__main__":
    unittest.main()
