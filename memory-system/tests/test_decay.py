#!/usr/bin/env python3
"""Tests for memory-system/decay.py — Ebbinghaus decay function."""

import math
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from decay import (
    DECAY_RATES,
    DEFAULT_PRUNE_FLOOR,
    compute_effective_confidence,
    days_until_prune,
    get_decay_rate,
    half_life,
    should_prune,
)


class TestGetDecayRate(unittest.TestCase):
    def test_known_levels(self):
        self.assertEqual(get_decay_rate("HIGH"), 0.98)
        self.assertEqual(get_decay_rate("MEDIUM"), 0.96)
        self.assertEqual(get_decay_rate("LOW"), 0.93)

    def test_case_insensitive(self):
        self.assertEqual(get_decay_rate("high"), 0.98)
        self.assertEqual(get_decay_rate("Low"), 0.93)

    def test_unknown_raises(self):
        with self.assertRaises(ValueError):
            get_decay_rate("EXTREME")
        with self.assertRaises(ValueError):
            get_decay_rate("")


class TestComputeEffectiveConfidence(unittest.TestCase):
    def test_zero_days_no_decay(self):
        self.assertEqual(compute_effective_confidence(100.0, 0, "HIGH"), 100.0)
        self.assertEqual(compute_effective_confidence(50.0, 0, "LOW"), 50.0)

    def test_one_day_decay(self):
        # After 1 day at HIGH (0.98): 100 * 0.98 = 98.0
        self.assertEqual(compute_effective_confidence(100.0, 1, "HIGH"), 98.0)
        # After 1 day at LOW (0.93): 100 * 0.93 = 93.0
        self.assertEqual(compute_effective_confidence(100.0, 1, "LOW"), 93.0)

    def test_multi_day_decay(self):
        # 10 days at MEDIUM (0.96): 100 * 0.96^10
        expected = round(100.0 * (0.96 ** 10), 2)
        self.assertEqual(compute_effective_confidence(100.0, 10, "MEDIUM"), expected)

    def test_negative_days_clamped_to_zero(self):
        # Clock-skew protection: negative days treated as 0
        self.assertEqual(compute_effective_confidence(100.0, -5, "HIGH"), 100.0)

    def test_zero_base_returns_zero(self):
        self.assertEqual(compute_effective_confidence(0.0, 10, "HIGH"), 0.0)

    def test_negative_base_returns_zero(self):
        self.assertEqual(compute_effective_confidence(-10.0, 5, "MEDIUM"), 0.0)

    def test_custom_decay_rate_overrides_confidence(self):
        # Custom rate of 0.50: 100 * 0.50^1 = 50
        self.assertEqual(compute_effective_confidence(100.0, 1, "HIGH", decay_rate=0.50), 50.0)

    def test_large_days_approaches_zero(self):
        result = compute_effective_confidence(100.0, 1000, "LOW")
        self.assertAlmostEqual(result, 0.0, places=1)

    def test_fractional_days(self):
        result = compute_effective_confidence(100.0, 0.5, "MEDIUM")
        expected = round(100.0 * (0.96 ** 0.5), 2)
        self.assertEqual(result, expected)

    def test_result_never_negative(self):
        result = compute_effective_confidence(1.0, 10000, "LOW")
        self.assertGreaterEqual(result, 0.0)


class TestShouldPrune(unittest.TestCase):
    def test_fresh_memory_not_pruned(self):
        self.assertFalse(should_prune(100.0, 0, "HIGH"))

    def test_old_low_confidence_pruned(self):
        # LOW at 0.93/day, base 30: after 60 days -> 30 * 0.93^60 ≈ 0.39
        self.assertTrue(should_prune(30.0, 60, "LOW"))

    def test_high_confidence_survives_long(self):
        # HIGH at 0.98/day, base 100: after 100 days -> 100 * 0.98^100 ≈ 13.3
        self.assertFalse(should_prune(100.0, 100, "HIGH"))

    def test_custom_floor(self):
        # With floor=50, even moderate decay triggers prune
        self.assertTrue(should_prune(100.0, 35, "MEDIUM", floor=50.0))

    def test_already_below_floor(self):
        self.assertTrue(should_prune(3.0, 0, "HIGH", floor=5.0))

    def test_exact_floor_not_pruned(self):
        # Effective == floor should NOT prune (< not <=)
        self.assertFalse(should_prune(5.0, 0, "HIGH", floor=5.0))


class TestDaysUntilPrune(unittest.TestCase):
    def test_high_confidence_long_survival(self):
        days = days_until_prune(100.0, "HIGH")
        self.assertIsNotNone(days)
        # HIGH: log(5/100) / log(0.98) ≈ 148.3 days
        self.assertAlmostEqual(days, 148.3, delta=0.5)

    def test_low_confidence_short_survival(self):
        days = days_until_prune(100.0, "LOW")
        self.assertIsNotNone(days)
        # LOW: log(5/100) / log(0.93) ≈ 41.3 days
        self.assertAlmostEqual(days, 41.3, delta=0.5)

    def test_already_below_floor_returns_none(self):
        self.assertIsNone(days_until_prune(3.0, "HIGH"))

    def test_zero_base_returns_none(self):
        self.assertIsNone(days_until_prune(0.0, "MEDIUM"))

    def test_custom_floor(self):
        days = days_until_prune(100.0, "MEDIUM", floor=50.0)
        self.assertIsNotNone(days)
        # MEDIUM: log(50/100) / log(0.96) ≈ 17.0 days
        self.assertAlmostEqual(days, 17.0, delta=0.5)


class TestHalfLife(unittest.TestCase):
    def test_high_half_life(self):
        hl = half_life("HIGH")
        # log(0.5) / log(0.98) ≈ 34.3
        self.assertAlmostEqual(hl, 34.3, delta=0.5)

    def test_medium_half_life(self):
        hl = half_life("MEDIUM")
        # log(0.5) / log(0.96) ≈ 17.0
        self.assertAlmostEqual(hl, 17.0, delta=0.5)

    def test_low_half_life(self):
        hl = half_life("LOW")
        # log(0.5) / log(0.93) ≈ 9.6
        self.assertAlmostEqual(hl, 9.6, delta=0.5)

    def test_custom_rate(self):
        hl = half_life(decay_rate=0.50)
        self.assertAlmostEqual(hl, 1.0, delta=0.1)

    def test_no_decay_returns_inf(self):
        self.assertEqual(half_life(decay_rate=1.0), float("inf"))


class TestDecayRateConstants(unittest.TestCase):
    """Verify the decay rates produce expected half-lives."""

    def test_high_slower_than_medium(self):
        self.assertGreater(DECAY_RATES["HIGH"], DECAY_RATES["MEDIUM"])

    def test_medium_slower_than_low(self):
        self.assertGreater(DECAY_RATES["MEDIUM"], DECAY_RATES["LOW"])

    def test_all_rates_between_0_and_1(self):
        for level, rate in DECAY_RATES.items():
            self.assertGreater(rate, 0.0, f"{level} rate must be > 0")
            self.assertLess(rate, 1.0, f"{level} rate must be < 1")

    def test_prune_floor_positive(self):
        self.assertGreater(DEFAULT_PRUNE_FLOOR, 0.0)


if __name__ == "__main__":
    unittest.main()
