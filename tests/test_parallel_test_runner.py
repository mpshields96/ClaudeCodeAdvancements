#!/usr/bin/env python3
"""Tests for parallel_test_runner.py — MT-36 Phase 3.

Runs test suites in parallel using multiprocessing to cut wrap test time.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from parallel_test_runner import (
    discover_test_files,
    run_single_suite,
    run_all_parallel,
    SuiteResult,
    format_results,
)


class TestDiscoverTestFiles(unittest.TestCase):
    """Test test file discovery."""

    def test_finds_test_files(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        files = discover_test_files(root)
        self.assertGreater(len(files), 50)
        for f in files:
            self.assertTrue(os.path.basename(f).startswith("test_"))
            self.assertTrue(f.endswith(".py"))

    def test_returns_absolute_paths(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        files = discover_test_files(root)
        for f in files:
            self.assertTrue(os.path.isabs(f))

    def test_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            files = discover_test_files(tmpdir)
            self.assertEqual(len(files), 0)


class TestSuiteResult(unittest.TestCase):
    """Test SuiteResult dataclass."""

    def test_create_pass(self):
        r = SuiteResult(path="test_foo.py", passed=True, tests_run=10,
                        duration_s=1.5, output="OK")
        self.assertTrue(r.passed)
        self.assertEqual(r.tests_run, 10)

    def test_create_fail(self):
        r = SuiteResult(path="test_foo.py", passed=False, tests_run=10,
                        duration_s=2.0, output="FAILED (failures=2)",
                        error="2 failures")
        self.assertFalse(r.passed)
        self.assertEqual(r.error, "2 failures")

    def test_to_dict(self):
        r = SuiteResult(path="test_foo.py", passed=True, tests_run=5,
                        duration_s=0.5, output="OK")
        d = r.to_dict()
        self.assertEqual(d["path"], "test_foo.py")
        self.assertTrue(d["passed"])


class TestRunSingleSuite(unittest.TestCase):
    """Test running a single test suite."""

    def test_run_passing_suite(self):
        # Use our own test file as a known-passing suite
        this_file = os.path.abspath(__file__)
        # Can't run ourselves, pick a known simple suite
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        simple = os.path.join(root, "tests", "test_tip_tracker.py")
        if os.path.exists(simple):
            result = run_single_suite(simple)
            self.assertTrue(result.passed)
            self.assertGreater(result.tests_run, 0)
            self.assertGreater(result.duration_s, 0)

    def test_run_nonexistent_file(self):
        result = run_single_suite("/nonexistent/test_foo.py")
        self.assertFalse(result.passed)
        self.assertIsNotNone(result.error)


class TestRunAllParallel(unittest.TestCase):
    """Test parallel execution."""

    def test_runs_multiple_suites(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # Pick 5 small suites for fast parallel test
        all_files = discover_test_files(root)
        small_suites = [f for f in all_files if "test_tip_tracker" in f
                       or "test_peak_hours" in f
                       or "test_overhead_timer" in f][:3]
        if len(small_suites) >= 2:
            results = run_all_parallel(small_suites, workers=2)
            self.assertEqual(len(results), len(small_suites))
            for r in results:
                self.assertIsInstance(r, SuiteResult)

    def test_single_worker_fallback(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        all_files = discover_test_files(root)
        small = [f for f in all_files if "test_tip_tracker" in f][:1]
        if small:
            results = run_all_parallel(small, workers=1)
            self.assertEqual(len(results), 1)


class TestFormatResults(unittest.TestCase):
    """Test result formatting."""

    def test_all_pass(self):
        results = [
            SuiteResult("test_a.py", True, 10, 1.0, "OK"),
            SuiteResult("test_b.py", True, 20, 2.0, "OK"),
        ]
        text = format_results(results)
        self.assertIn("2/2 suites passed", text)
        self.assertIn("30 tests", text)

    def test_some_fail(self):
        results = [
            SuiteResult("test_a.py", True, 10, 1.0, "OK"),
            SuiteResult("test_b.py", False, 5, 1.0, "FAILED", error="1 failure"),
        ]
        text = format_results(results)
        self.assertIn("1/2 suites passed", text)
        self.assertIn("FAILED", text)

    def test_empty(self):
        text = format_results([])
        self.assertIn("No test suites", text)


if __name__ == "__main__":
    unittest.main()
