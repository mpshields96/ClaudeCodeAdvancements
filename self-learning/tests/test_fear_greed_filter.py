#!/usr/bin/env python3
"""Tests for fear_greed_filter.py — MT-26 Tier 2: Fear & Greed Contrarian Filter.

At sentiment extremes, crypto direction becomes more predictable (mean-reversion
at extreme fear, momentum breakout at extreme greed). This filter uses the
Alternative.me Fear & Greed Index as a signal quality modifier.

The module does NOT call external APIs — the bot provides the F&G value,
this module provides the interpretation and sizing adjustment.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fear_greed_filter import (
    FearGreedFilter,
    SentimentZone,
    SentimentSignal,
)


class TestSentimentZone(unittest.TestCase):
    """Test SentimentZone enum."""

    def test_zone_values(self):
        self.assertEqual(SentimentZone.EXTREME_FEAR.value, "EXTREME_FEAR")
        self.assertEqual(SentimentZone.FEAR.value, "FEAR")
        self.assertEqual(SentimentZone.NEUTRAL.value, "NEUTRAL")
        self.assertEqual(SentimentZone.GREED.value, "GREED")
        self.assertEqual(SentimentZone.EXTREME_GREED.value, "EXTREME_GREED")


class TestSentimentSignal(unittest.TestCase):
    """Test SentimentSignal data structure."""

    def test_create_signal(self):
        sig = SentimentSignal(
            zone=SentimentZone.EXTREME_FEAR,
            fg_value=12,
            sizing_modifier=1.2,
            direction_bias="UP",
            confidence=0.7,
            advice="Extreme fear — contrarian long bias.",
        )
        self.assertEqual(sig.zone, SentimentZone.EXTREME_FEAR)
        self.assertEqual(sig.fg_value, 12)
        self.assertEqual(sig.direction_bias, "UP")

    def test_signal_to_dict(self):
        sig = SentimentSignal(
            zone=SentimentZone.NEUTRAL,
            fg_value=50,
            sizing_modifier=1.0,
            direction_bias="NONE",
            confidence=0.5,
            advice="Neutral sentiment — no directional bias.",
        )
        d = sig.to_dict()
        self.assertEqual(d["zone"], "NEUTRAL")
        self.assertEqual(d["fg_value"], 50)
        self.assertEqual(d["direction_bias"], "NONE")
        self.assertIsInstance(d["sizing_modifier"], float)


class TestFearGreedFilter(unittest.TestCase):
    """Test FearGreedFilter classification."""

    def setUp(self):
        self.fgf = FearGreedFilter()

    # --- Zone classification ---

    def test_extreme_fear_zone(self):
        result = self.fgf.classify(10)
        self.assertEqual(result.zone, SentimentZone.EXTREME_FEAR)

    def test_fear_zone(self):
        result = self.fgf.classify(30)
        self.assertEqual(result.zone, SentimentZone.FEAR)

    def test_neutral_zone(self):
        result = self.fgf.classify(50)
        self.assertEqual(result.zone, SentimentZone.NEUTRAL)

    def test_greed_zone(self):
        result = self.fgf.classify(70)
        self.assertEqual(result.zone, SentimentZone.GREED)

    def test_extreme_greed_zone(self):
        result = self.fgf.classify(90)
        self.assertEqual(result.zone, SentimentZone.EXTREME_GREED)

    # --- Boundary tests ---

    def test_boundary_0(self):
        result = self.fgf.classify(0)
        self.assertEqual(result.zone, SentimentZone.EXTREME_FEAR)

    def test_boundary_20(self):
        result = self.fgf.classify(20)
        self.assertEqual(result.zone, SentimentZone.EXTREME_FEAR)

    def test_boundary_21(self):
        result = self.fgf.classify(21)
        self.assertEqual(result.zone, SentimentZone.FEAR)

    def test_boundary_40(self):
        result = self.fgf.classify(40)
        self.assertEqual(result.zone, SentimentZone.FEAR)

    def test_boundary_41(self):
        result = self.fgf.classify(41)
        self.assertEqual(result.zone, SentimentZone.NEUTRAL)

    def test_boundary_60(self):
        result = self.fgf.classify(60)
        self.assertEqual(result.zone, SentimentZone.NEUTRAL)

    def test_boundary_61(self):
        result = self.fgf.classify(61)
        self.assertEqual(result.zone, SentimentZone.GREED)

    def test_boundary_80(self):
        result = self.fgf.classify(80)
        self.assertEqual(result.zone, SentimentZone.GREED)

    def test_boundary_81(self):
        result = self.fgf.classify(81)
        self.assertEqual(result.zone, SentimentZone.EXTREME_GREED)

    def test_boundary_100(self):
        result = self.fgf.classify(100)
        self.assertEqual(result.zone, SentimentZone.EXTREME_GREED)

    # --- Direction bias ---

    def test_extreme_fear_has_up_bias(self):
        """Extreme fear = contrarian long bias (mean reversion expected)."""
        result = self.fgf.classify(10)
        self.assertEqual(result.direction_bias, "UP")

    def test_extreme_greed_has_down_bias(self):
        """Extreme greed = contrarian short bias (correction expected)."""
        result = self.fgf.classify(92)
        self.assertEqual(result.direction_bias, "DOWN")

    def test_neutral_has_no_bias(self):
        result = self.fgf.classify(50)
        self.assertEqual(result.direction_bias, "NONE")

    def test_moderate_fear_has_slight_up_bias(self):
        result = self.fgf.classify(30)
        self.assertIn(result.direction_bias, ["UP", "SLIGHT_UP"])

    def test_moderate_greed_has_slight_down_bias(self):
        result = self.fgf.classify(70)
        self.assertIn(result.direction_bias, ["DOWN", "SLIGHT_DOWN"])

    # --- Sizing modifier ---

    def test_neutral_modifier_is_1(self):
        result = self.fgf.classify(50)
        self.assertAlmostEqual(result.sizing_modifier, 1.0, places=1)

    def test_extreme_fear_increases_modifier(self):
        """Extreme fear = contrarian opportunity, can size UP."""
        result = self.fgf.classify(8)
        self.assertGreater(result.sizing_modifier, 1.0)

    def test_extreme_greed_may_reduce_modifier(self):
        """Extreme greed = potential for sharp correction, reduce sizing."""
        result = self.fgf.classify(95)
        self.assertLessEqual(result.sizing_modifier, 1.0)

    def test_modifier_range(self):
        """Modifier should be between 0.5 and 1.5 for any input."""
        for fg in range(0, 101):
            result = self.fgf.classify(fg)
            self.assertGreaterEqual(result.sizing_modifier, 0.5,
                                    f"Modifier too low for F&G={fg}")
            self.assertLessEqual(result.sizing_modifier, 1.5,
                                 f"Modifier too high for F&G={fg}")

    # --- Confidence ---

    def test_extreme_values_higher_confidence(self):
        """More extreme sentiment = higher confidence in the signal."""
        extreme = self.fgf.classify(5)
        moderate = self.fgf.classify(35)
        neutral = self.fgf.classify(50)
        self.assertGreater(extreme.confidence, moderate.confidence)
        self.assertGreater(moderate.confidence, neutral.confidence)

    def test_confidence_range(self):
        for fg in range(0, 101):
            result = self.fgf.classify(fg)
            self.assertGreaterEqual(result.confidence, 0.0)
            self.assertLessEqual(result.confidence, 1.0)

    # --- Custom thresholds ---

    def test_custom_thresholds(self):
        fgf = FearGreedFilter(
            extreme_fear_threshold=15,
            extreme_greed_threshold=85,
        )
        # 18 is extreme fear with default (<=20), but FEAR with custom (<=15)
        result = fgf.classify(18)
        self.assertEqual(result.zone, SentimentZone.FEAR)

    # --- Edge cases ---

    def test_clamping_below_0(self):
        result = self.fgf.classify(-5)
        self.assertEqual(result.zone, SentimentZone.EXTREME_FEAR)
        self.assertEqual(result.fg_value, 0)

    def test_clamping_above_100(self):
        result = self.fgf.classify(110)
        self.assertEqual(result.zone, SentimentZone.EXTREME_GREED)
        self.assertEqual(result.fg_value, 100)

    # --- With trend context ---

    def test_fear_with_uptrend_strengthens_signal(self):
        """Fear + uptrend = stronger contrarian signal."""
        result = self.fgf.classify_with_trend(fg_value=15, trend="UP")
        self.assertGreater(result.confidence, 0.5)

    def test_greed_with_downtrend_strengthens_signal(self):
        result = self.fgf.classify_with_trend(fg_value=90, trend="DOWN")
        self.assertGreater(result.confidence, 0.5)

    def test_fear_with_downtrend_weakens_signal(self):
        """Fear + downtrend = momentum may continue, weaker contrarian."""
        fear_down = self.fgf.classify_with_trend(fg_value=15, trend="DOWN")
        fear_up = self.fgf.classify_with_trend(fg_value=15, trend="UP")
        self.assertLessEqual(fear_down.confidence, fear_up.confidence)

    def test_neutral_with_any_trend(self):
        for trend in ["UP", "DOWN", "FLAT"]:
            result = self.fgf.classify_with_trend(fg_value=50, trend=trend)
            self.assertEqual(result.direction_bias, "NONE")

    # --- JSON serialization ---

    def test_json_serializable(self):
        result = self.fgf.classify(25)
        d = result.to_dict()
        json_str = json.dumps(d)
        self.assertIsInstance(json_str, str)

    # --- CLI ---

    def test_cli_output(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, os.path.join(
                os.path.dirname(__file__), "..", "fear_greed_filter.py"),
             "--value", "15"],
            capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertIn("zone", data)
        self.assertIn("sizing_modifier", data)
        self.assertIn("direction_bias", data)


if __name__ == "__main__":
    unittest.main()
