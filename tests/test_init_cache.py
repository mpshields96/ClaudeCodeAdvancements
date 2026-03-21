#!/usr/bin/env python3
"""Tests for init_cache.py — test result caching for fast session init."""

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))
from init_cache import (
    TestCache,
    SMOKE_SUITES,
    read_cache,
    init_summary,
    _find_test_files,
    _compute_test_file_hash,
)


class TestTestCache(unittest.TestCase):
    """Test TestCache dataclass."""

    def test_default_values(self):
        cache = TestCache()
        self.assertEqual(cache.total_tests, 0)
        self.assertEqual(cache.total_suites, 0)
        self.assertFalse(cache.all_passed)

    def test_age_minutes(self):
        cache = TestCache(timestamp=time.time() - 300)  # 5 min ago
        age = cache.age_minutes()
        self.assertAlmostEqual(age, 5.0, delta=0.5)

    def test_is_stale_no_timestamp(self):
        cache = TestCache(timestamp=0)
        self.assertTrue(cache.is_stale())

    def test_is_stale_old_cache(self):
        cache = TestCache(timestamp=time.time() - 5 * 3600)  # 5 hours ago
        self.assertTrue(cache.is_stale(max_age_hours=4.0))

    def test_to_json(self):
        cache = TestCache(total_tests=100, total_suites=10, all_passed=True)
        data = json.loads(cache.to_json())
        self.assertEqual(data["total_tests"], 100)
        self.assertEqual(data["total_suites"], 10)
        self.assertTrue(data["all_passed"])

    def test_from_json(self):
        original = TestCache(total_tests=200, total_suites=20, all_passed=True,
                           timestamp=12345.0, session="S98")
        restored = TestCache.from_json(original.to_json())
        self.assertEqual(restored.total_tests, 200)
        self.assertEqual(restored.total_suites, 20)
        self.assertEqual(restored.session, "S98")

    def test_roundtrip(self):
        original = TestCache(total_tests=50, total_suites=5, all_passed=True,
                           timestamp=time.time(), session="S99",
                           test_file_hash="abc123")
        restored = TestCache.from_json(original.to_json())
        self.assertEqual(restored.total_tests, original.total_tests)
        self.assertEqual(restored.test_file_hash, original.test_file_hash)

    def test_from_json_ignores_extra_fields(self):
        data = json.dumps({"total_tests": 10, "total_suites": 1,
                          "all_passed": True, "timestamp": 0,
                          "session": "", "test_file_hash": "",
                          "extra_field": "ignored"})
        cache = TestCache.from_json(data)
        self.assertEqual(cache.total_tests, 10)


class TestReadCache(unittest.TestCase):
    """Test reading cache from disk."""

    def test_returns_none_if_no_file(self):
        with patch("init_cache.CACHE_FILE", Path("/nonexistent/cache.json")):
            result = read_cache()
            self.assertIsNone(result)

    def test_reads_valid_cache(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            cache = TestCache(total_tests=100, total_suites=10,
                            all_passed=True, timestamp=time.time())
            f.write(cache.to_json())
            f.flush()
            with patch("init_cache.CACHE_FILE", Path(f.name)):
                result = read_cache()
                self.assertIsNotNone(result)
                self.assertEqual(result.total_tests, 100)
            os.unlink(f.name)

    def test_returns_none_for_invalid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not json")
            f.flush()
            with patch("init_cache.CACHE_FILE", Path(f.name)):
                result = read_cache()
                self.assertIsNone(result)
            os.unlink(f.name)


class TestInitSummary(unittest.TestCase):
    """Test init_summary output."""

    def test_no_cache(self):
        with patch("init_cache.read_cache", return_value=None):
            result = init_summary()
            self.assertIn("No test cache", result)

    def test_fresh_cache(self):
        cache = TestCache(total_tests=100, total_suites=10,
                        all_passed=True, timestamp=time.time(),
                        session="S98", test_file_hash=_compute_test_file_hash())
        with patch("init_cache.read_cache", return_value=cache):
            result = init_summary()
            self.assertIn("100 tests", result)
            self.assertIn("10 suites", result)

    def test_stale_cache(self):
        cache = TestCache(total_tests=100, total_suites=10,
                        timestamp=time.time() - 5 * 3600,
                        test_file_hash="old_hash")
        with patch("init_cache.read_cache", return_value=cache):
            result = init_summary()
            self.assertIn("stale", result.lower())


class TestFindTestFiles(unittest.TestCase):
    """Test finding test files in project."""

    def test_finds_test_files(self):
        files = _find_test_files()
        self.assertGreater(len(files), 0)
        for f in files:
            self.assertTrue(f.name.startswith("test_"))
            self.assertTrue(f.name.endswith(".py"))

    def test_files_are_sorted(self):
        files = _find_test_files()
        self.assertEqual(files, sorted(files))


class TestComputeHash(unittest.TestCase):
    """Test test file hash computation."""

    def test_returns_string(self):
        result = _compute_test_file_hash()
        self.assertIsInstance(result, str)

    def test_deterministic(self):
        h1 = _compute_test_file_hash()
        h2 = _compute_test_file_hash()
        self.assertEqual(h1, h2)


class TestSmokeSuites(unittest.TestCase):
    """Test that smoke suites are properly defined."""

    def test_smoke_suites_not_empty(self):
        self.assertGreater(len(SMOKE_SUITES), 0)

    def test_smoke_suites_are_relative_paths(self):
        for suite in SMOKE_SUITES:
            self.assertFalse(suite.startswith("/"), f"{suite} should be relative")
            self.assertTrue(suite.endswith(".py"), f"{suite} should be .py")

    def test_smoke_suites_exist(self):
        project_root = Path(__file__).parent.parent
        for suite in SMOKE_SUITES:
            path = project_root / suite
            self.assertTrue(path.exists(), f"Smoke suite not found: {suite}")


if __name__ == "__main__":
    unittest.main()
