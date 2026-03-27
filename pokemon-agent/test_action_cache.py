"""Tests for action_cache.py — LRU action cache for game states."""
import unittest
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from action_cache import ActionCache, CacheEntry


class TestCacheBasics(unittest.TestCase):
    """Test basic cache operations."""

    def test_empty_cache_returns_none(self):
        cache = ActionCache()
        self.assertIsNone(cache.get("overworld:3:5,4:no_battle"))

    def test_put_and_get(self):
        cache = ActionCache()
        cache.put("overworld:3:5,4:no_battle", ["right", "right", "a"])
        result = cache.get("overworld:3:5,4:no_battle")
        self.assertEqual(result, ["right", "right", "a"])

    def test_miss_increments_counter(self):
        cache = ActionCache()
        cache.get("nonexistent")
        self.assertEqual(cache.total_misses, 1)

    def test_hit_increments_counter(self):
        cache = ActionCache()
        cache.put("key1", ["a"])
        cache.get("key1")
        self.assertEqual(cache.total_hits, 1)

    def test_size(self):
        cache = ActionCache()
        self.assertEqual(cache.size(), 0)
        cache.put("k1", ["a"])
        cache.put("k2", ["b"])
        self.assertEqual(cache.size(), 2)

    def test_clear(self):
        cache = ActionCache()
        cache.put("k1", ["a"])
        cache.put("k2", ["b"])
        cache.clear()
        self.assertEqual(cache.size(), 0)
        self.assertIsNone(cache.get("k1"))

    def test_clear_preserves_stats(self):
        cache = ActionCache()
        cache.put("k1", ["a"])
        cache.get("k1")
        cache.clear()
        self.assertEqual(cache.total_hits, 1)


class TestCacheKeyGeneration(unittest.TestCase):
    """Test make_key produces correct keys."""

    def test_overworld_key(self):
        cache = ActionCache()
        key = cache.make_key("overworld", 3, 5, 4, False)
        self.assertEqual(key, "overworld:3:5,4:no_battle")

    def test_battle_key(self):
        cache = ActionCache()
        key = cache.make_key("battle", 3, 5, 4, True, "wild")
        self.assertEqual(key, "battle:3:5,4:wild")

    def test_dialog_key(self):
        cache = ActionCache()
        key = cache.make_key("dialog", 3, 5, 4, False)
        self.assertEqual(key, "dialog:3:5,4:no_battle")

    def test_different_positions_different_keys(self):
        cache = ActionCache()
        k1 = cache.make_key("overworld", 3, 5, 4, False)
        k2 = cache.make_key("overworld", 3, 6, 4, False)
        self.assertNotEqual(k1, k2)

    def test_different_maps_different_keys(self):
        cache = ActionCache()
        k1 = cache.make_key("overworld", 3, 5, 4, False)
        k2 = cache.make_key("overworld", 7, 5, 4, False)
        self.assertNotEqual(k1, k2)


class TestLRUEviction(unittest.TestCase):
    """Test LRU eviction when cache is full."""

    def test_evicts_lru_when_full(self):
        cache = ActionCache(max_size=3)
        cache.put("k1", ["a"])
        cache.put("k2", ["b"])
        cache.put("k3", ["start"])
        cache.put("k4", ["select"])  # Should evict k1
        self.assertIsNone(cache.get("k1"))
        self.assertEqual(cache.get("k2"), ["b"])

    def test_accessing_entry_prevents_eviction(self):
        cache = ActionCache(max_size=3)
        cache.put("k1", ["a"])
        cache.put("k2", ["b"])
        cache.put("k3", ["start"])
        cache.get("k1")  # Touch k1 — moves it to end
        cache.put("k4", ["select"])  # Should evict k2 (now LRU)
        self.assertEqual(cache.get("k1"), ["a"])
        self.assertIsNone(cache.get("k2"))

    def test_max_size_respected(self):
        cache = ActionCache(max_size=5)
        for i in range(20):
            cache.put(f"k{i}", ["a"])
        self.assertLessEqual(cache.size(), 5)


class TestExpiration(unittest.TestCase):
    """Test hit-based expiration."""

    def test_expires_after_max_hits(self):
        cache = ActionCache(max_hits=3)
        cache.put("k1", ["a"])
        cache.get("k1")  # hit 1
        cache.get("k1")  # hit 2
        cache.get("k1")  # hit 3 (at max)
        result = cache.get("k1")  # Should expire
        self.assertIsNone(result)

    def test_poor_success_rate_expires(self):
        cache = ActionCache()
        cache.put("k1", ["a"])
        # Record 5 uses with only 1 success (20% < 30% threshold)
        for _ in range(5):
            cache.get("k1")
        cache._cache["k1"].successes = 1
        cache._cache["k1"].hits = 5
        result = cache.get("k1")  # Should expire due to poor success rate
        self.assertIsNone(result)

    def test_good_success_rate_survives(self):
        cache = ActionCache()
        cache.put("k1", ["a"])
        for _ in range(5):
            cache.get("k1")
        cache._cache["k1"].successes = 4
        cache._cache["k1"].hits = 5
        result = cache.get("k1")  # Should survive (80% > 30%)
        self.assertEqual(result, ["a"])


class TestOutcomeTracking(unittest.TestCase):
    """Test success/failure outcome recording."""

    def test_record_success(self):
        cache = ActionCache()
        cache.put("k1", ["a"])
        cache.record_outcome("k1", True)
        self.assertEqual(cache._cache["k1"].successes, 1)

    def test_record_failure(self):
        cache = ActionCache()
        cache.put("k1", ["a"])
        cache.record_outcome("k1", False)
        self.assertEqual(cache._cache["k1"].failures, 1)

    def test_outcome_on_missing_key_is_noop(self):
        cache = ActionCache()
        cache.record_outcome("nonexistent", True)  # Should not crash


class TestCacheStats(unittest.TestCase):
    """Test stats reporting."""

    def test_hit_rate_empty(self):
        cache = ActionCache()
        self.assertEqual(cache.hit_rate(), 0.0)

    def test_hit_rate_all_hits(self):
        cache = ActionCache()
        cache.put("k1", ["a"])
        cache.get("k1")
        cache.get("k1")
        self.assertEqual(cache.hit_rate(), 1.0)

    def test_hit_rate_mixed(self):
        cache = ActionCache()
        cache.put("k1", ["a"])
        cache.get("k1")    # hit
        cache.get("miss")  # miss
        self.assertAlmostEqual(cache.hit_rate(), 0.5)

    def test_stats_dict(self):
        cache = ActionCache(max_size=100)
        cache.put("k1", ["a"])
        cache.get("k1")
        stats = cache.stats()
        self.assertEqual(stats["size"], 1)
        self.assertEqual(stats["max_size"], 100)
        self.assertEqual(stats["total_hits"], 1)
        self.assertEqual(stats["total_misses"], 0)


class TestUpdateExisting(unittest.TestCase):
    """Test updating an existing cache entry."""

    def test_put_overwrites_buttons(self):
        cache = ActionCache()
        cache.put("k1", ["a"])
        cache.put("k1", ["b", "start"])
        self.assertEqual(cache.get("k1"), ["b", "start"])

    def test_overwrite_does_not_increase_size(self):
        cache = ActionCache()
        cache.put("k1", ["a"])
        cache.put("k1", ["b"])
        self.assertEqual(cache.size(), 1)


if __name__ == "__main__":
    unittest.main()
