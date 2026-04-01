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


class TestDecayIntegrationWithMemoryStore(unittest.TestCase):
    """Integration tests: decay applied during MemoryStore.search()."""

    def setUp(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from memory_store import MemoryStore
        self.store = MemoryStore(":memory:")

    def tearDown(self):
        self.store.close()

    def test_search_returns_effective_confidence(self):
        """Search results include the effective_confidence field."""
        self.store.create_memory("testing decay integration", tags=["test"])
        results = self.store.search("decay")
        self.assertTrue(len(results) > 0)
        self.assertIn("effective_confidence", results[0])
        # Just created — effective confidence should be very close to 100
        self.assertGreater(results[0]["effective_confidence"], 95.0)

    def test_search_updates_last_accessed_at(self):
        """Searching touches last_accessed_at on returned memories."""
        mem = self.store.create_memory("access timestamp test", tags=["access"])
        # Initially last_accessed_at is empty
        row = self.store.get_by_id(mem["id"])
        self.assertEqual(row.get("last_accessed_at", ""), "")

        # Search should populate last_accessed_at
        self.store.search("access timestamp")
        row = self.store.get_by_id(mem["id"])
        self.assertTrue(row.get("last_accessed_at", ""), "last_accessed_at should be populated after search")
        self.assertIn("T", row["last_accessed_at"])  # ISO format

    def test_old_memory_has_lower_effective_confidence(self):
        """A memory with an old created_at has lower effective_confidence than a fresh one."""
        from datetime import datetime, timezone, timedelta
        # Create two memories
        fresh = self.store.create_memory("fresh memory for decay test", tags=["fresh"])
        old = self.store.create_memory("old memory for decay test", tags=["old"])

        # Manually backdate the old memory's updated_at and created_at
        old_date = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat().replace("+00:00", "Z")
        self.store._conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            (old_date, old_date, old["id"]),
        )
        self.store._conn.commit()

        results = self.store.search("memory decay test")
        self.assertEqual(len(results), 2)
        # Results are sorted by effective_confidence descending
        self.assertGreater(results[0]["effective_confidence"], results[1]["effective_confidence"])
        # Fresh should be first
        self.assertIn("fresh", results[0]["content"])

    def test_very_old_low_confidence_near_zero(self):
        """A LOW confidence memory from 365 days ago should have near-zero effective confidence."""
        from datetime import datetime, timezone, timedelta
        mem = self.store.create_memory("ancient low confidence memory", confidence="LOW", tags=["ancient"])
        old_date = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat().replace("+00:00", "Z")
        self.store._conn.execute(
            "UPDATE memories SET created_at = ?, updated_at = ? WHERE id = ?",
            (old_date, old_date, mem["id"]),
        )
        self.store._conn.commit()

        results = self.store.search("ancient low confidence")
        self.assertEqual(len(results), 1)
        # LOW at 0.93^365 ≈ 0.0 (effectively zero)
        self.assertLess(results[0]["effective_confidence"], 1.0)


if __name__ == "__main__":
    unittest.main()
