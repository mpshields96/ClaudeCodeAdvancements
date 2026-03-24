#!/usr/bin/env python3
"""
test_session_timer.py — Tests for session_timer.py (MT-36 Phase 1)

Session Efficiency Optimizer: per-step timing instrumentation for
init/wrap/auto lifecycle. Measures WHERE time goes, not just total.

TDD: tests first.
"""

import json
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestStepTiming(unittest.TestCase):
    """Test the StepTiming dataclass."""

    def test_create_step_timing(self):
        from session_timer import StepTiming
        s = StepTiming(name="init:read_project_index", category="init", duration_s=1.5)
        self.assertEqual(s.name, "init:read_project_index")
        self.assertEqual(s.category, "init")
        self.assertAlmostEqual(s.duration_s, 1.5)

    def test_step_timing_to_dict(self):
        from session_timer import StepTiming
        s = StepTiming(name="wrap:update_docs", category="wrap", duration_s=3.2)
        d = s.to_dict()
        self.assertEqual(d["name"], "wrap:update_docs")
        self.assertEqual(d["category"], "wrap")
        self.assertAlmostEqual(d["duration_s"], 3.2)

    def test_step_timing_from_dict(self):
        from session_timer import StepTiming
        d = {"name": "test:run_suites", "category": "test", "duration_s": 45.0}
        s = StepTiming.from_dict(d)
        self.assertEqual(s.name, "test:run_suites")
        self.assertAlmostEqual(s.duration_s, 45.0)

    def test_valid_categories(self):
        from session_timer import StepTiming, VALID_CATEGORIES
        self.assertIn("init", VALID_CATEGORIES)
        self.assertIn("wrap", VALID_CATEGORIES)
        self.assertIn("test", VALID_CATEGORIES)
        self.assertIn("code", VALID_CATEGORIES)
        self.assertIn("doc", VALID_CATEGORIES)
        self.assertIn("other", VALID_CATEGORIES)

    def test_invalid_category_raises(self):
        from session_timer import StepTiming
        with self.assertRaises(ValueError):
            StepTiming(name="bad", category="invalid", duration_s=1.0)


class TestSessionTimer(unittest.TestCase):
    """Test the SessionTimer core timing engine."""

    def test_create_timer(self):
        from session_timer import SessionTimer
        t = SessionTimer(session_id=144)
        self.assertEqual(t.session_id, 144)
        self.assertEqual(len(t.steps), 0)

    def test_time_step_context_manager(self):
        from session_timer import SessionTimer
        t = SessionTimer(session_id=144)
        with t.time_step("init:read_files", category="init"):
            time.sleep(0.01)
        self.assertEqual(len(t.steps), 1)
        self.assertEqual(t.steps[0].name, "init:read_files")
        self.assertGreater(t.steps[0].duration_s, 0.005)

    def test_time_step_manual(self):
        from session_timer import SessionTimer
        t = SessionTimer(session_id=144)
        t.start_step("init:run_tests", category="test")
        time.sleep(0.01)
        elapsed = t.stop_step()
        self.assertGreater(elapsed, 0.005)
        self.assertEqual(len(t.steps), 1)

    def test_nested_steps_not_allowed(self):
        from session_timer import SessionTimer
        t = SessionTimer(session_id=144)
        t.start_step("init:step1", category="init")
        with self.assertRaises(RuntimeError):
            t.start_step("init:step2", category="init")
        t.stop_step()

    def test_stop_without_start_raises(self):
        from session_timer import SessionTimer
        t = SessionTimer(session_id=144)
        with self.assertRaises(RuntimeError):
            t.stop_step()

    def test_multiple_steps(self):
        from session_timer import SessionTimer
        t = SessionTimer(session_id=144)
        with t.time_step("init:read_files", category="init"):
            time.sleep(0.01)
        with t.time_step("init:run_tests", category="test"):
            time.sleep(0.01)
        with t.time_step("code:write_feature", category="code"):
            time.sleep(0.01)
        self.assertEqual(len(t.steps), 3)

    def test_total_duration(self):
        from session_timer import SessionTimer
        t = SessionTimer(session_id=144)
        with t.time_step("step1", category="init"):
            time.sleep(0.01)
        with t.time_step("step2", category="code"):
            time.sleep(0.01)
        total = t.total_duration()
        self.assertGreater(total, 0.01)

    def test_duration_by_category(self):
        from session_timer import SessionTimer
        t = SessionTimer(session_id=144)
        with t.time_step("init:a", category="init"):
            time.sleep(0.01)
        with t.time_step("init:b", category="init"):
            time.sleep(0.01)
        with t.time_step("code:c", category="code"):
            time.sleep(0.01)
        by_cat = t.duration_by_category()
        self.assertIn("init", by_cat)
        self.assertIn("code", by_cat)
        self.assertGreater(by_cat["init"], by_cat["code"])

    def test_category_percentages(self):
        from session_timer import SessionTimer
        t = SessionTimer(session_id=144)
        # Use add_step for deterministic timing
        t.add_step("init:a", "init", 10.0)
        t.add_step("code:b", "code", 30.0)
        t.add_step("test:c", "test", 10.0)
        pcts = t.category_percentages()
        self.assertAlmostEqual(pcts["init"], 20.0)
        self.assertAlmostEqual(pcts["code"], 60.0)
        self.assertAlmostEqual(pcts["test"], 20.0)

    def test_category_percentages_empty(self):
        from session_timer import SessionTimer
        t = SessionTimer(session_id=144)
        pcts = t.category_percentages()
        self.assertEqual(pcts, {})

    def test_add_step_directly(self):
        """Add a pre-measured step without using the timer."""
        from session_timer import SessionTimer
        t = SessionTimer(session_id=144)
        t.add_step("init:cached_tests", "init", 0.5)
        self.assertEqual(len(t.steps), 1)
        self.assertAlmostEqual(t.steps[0].duration_s, 0.5)

    def test_top_n_steps(self):
        from session_timer import SessionTimer
        t = SessionTimer(session_id=144)
        t.add_step("fast", "other", 1.0)
        t.add_step("slow", "code", 50.0)
        t.add_step("medium", "test", 10.0)
        top = t.top_steps(n=2)
        self.assertEqual(len(top), 2)
        self.assertEqual(top[0].name, "slow")
        self.assertEqual(top[1].name, "medium")


class TestSessionTimerPersistence(unittest.TestCase):
    """Test save/load of session timing data."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.log_path = os.path.join(self.tmpdir, "session_timings.jsonl")

    def tearDown(self):
        if os.path.exists(self.log_path):
            os.unlink(self.log_path)
        os.rmdir(self.tmpdir)

    def test_save_session(self):
        from session_timer import SessionTimer
        t = SessionTimer(session_id=144)
        t.add_step("init:read", "init", 2.0)
        t.add_step("code:write", "code", 30.0)
        t.save(self.log_path)
        self.assertTrue(os.path.exists(self.log_path))
        with open(self.log_path) as f:
            data = json.loads(f.readline())
        self.assertEqual(data["session_id"], 144)
        self.assertEqual(len(data["steps"]), 2)

    def test_save_appends(self):
        from session_timer import SessionTimer
        t1 = SessionTimer(session_id=144)
        t1.add_step("a", "init", 1.0)
        t1.save(self.log_path)
        t2 = SessionTimer(session_id=145)
        t2.add_step("b", "code", 2.0)
        t2.save(self.log_path)
        with open(self.log_path) as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 2)

    def test_load_history(self):
        from session_timer import SessionTimer, load_timing_history
        t = SessionTimer(session_id=144)
        t.add_step("init:read", "init", 2.0)
        t.save(self.log_path)
        history = load_timing_history(self.log_path)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["session_id"], 144)

    def test_load_empty_file(self):
        from session_timer import load_timing_history
        history = load_timing_history("/nonexistent/path.jsonl")
        self.assertEqual(history, [])

    def test_load_corrupted_line(self):
        from session_timer import load_timing_history
        with open(self.log_path, "w") as f:
            f.write("not json\n")
            f.write(json.dumps({"session_id": 1, "steps": []}) + "\n")
        history = load_timing_history(self.log_path)
        self.assertEqual(len(history), 1)


class TestTimingAnalysis(unittest.TestCase):
    """Test cross-session timing analysis."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.log_path = os.path.join(self.tmpdir, "session_timings.jsonl")
        # Seed 3 sessions of history
        from session_timer import SessionTimer
        for i, (init_t, test_t, code_t) in enumerate([
            (3.0, 45.0, 60.0),
            (4.0, 50.0, 55.0),
            (3.5, 47.0, 58.0),
        ]):
            t = SessionTimer(session_id=140 + i)
            t.add_step("init:read_files", "init", init_t)
            t.add_step("test:run_suites", "test", test_t)
            t.add_step("code:work", "code", code_t)
            t.save(self.log_path)

    def tearDown(self):
        if os.path.exists(self.log_path):
            os.unlink(self.log_path)
        os.rmdir(self.tmpdir)

    def test_compute_step_averages(self):
        from session_timer import compute_step_averages, load_timing_history
        history = load_timing_history(self.log_path)
        avgs = compute_step_averages(history)
        self.assertIn("init:read_files", avgs)
        self.assertAlmostEqual(avgs["init:read_files"], 3.5, places=1)
        self.assertAlmostEqual(avgs["test:run_suites"], 47.33, places=1)

    def test_compute_category_averages(self):
        from session_timer import compute_category_averages, load_timing_history
        history = load_timing_history(self.log_path)
        avgs = compute_category_averages(history)
        self.assertIn("init", avgs)
        self.assertIn("test", avgs)
        self.assertIn("code", avgs)

    def test_find_outliers(self):
        from session_timer import SessionTimer, find_outliers, load_timing_history
        # Add a session with an outlier init time (10x normal)
        t = SessionTimer(session_id=143)
        t.add_step("init:read_files", "init", 35.0)  # 10x the ~3.5 average
        t.add_step("test:run_suites", "test", 48.0)  # normal
        t.add_step("code:work", "code", 55.0)  # normal
        t.save(self.log_path)
        history = load_timing_history(self.log_path)
        outliers = find_outliers(history, threshold=2.0)
        # The last session's init:read_files (35.0) should be flagged
        outlier_names = [o["step_name"] for o in outliers if o["session_id"] == 143]
        self.assertIn("init:read_files", outlier_names)

    def test_find_outliers_empty(self):
        from session_timer import find_outliers
        outliers = find_outliers([], threshold=2.0)
        self.assertEqual(outliers, [])

    def test_find_outliers_single_session(self):
        """Single session = no baseline, no outliers."""
        from session_timer import find_outliers
        history = [{"session_id": 1, "steps": [{"name": "a", "category": "init", "duration_s": 5.0}]}]
        outliers = find_outliers(history, threshold=2.0)
        self.assertEqual(outliers, [])


class TestFormatBreakdown(unittest.TestCase):
    """Test human-readable output formatting."""

    def test_format_session_breakdown(self):
        from session_timer import SessionTimer, format_breakdown
        t = SessionTimer(session_id=144)
        t.add_step("init:read_files", "init", 3.0)
        t.add_step("test:run_suites", "test", 45.0)
        t.add_step("code:implement", "code", 60.0)
        t.add_step("wrap:update_docs", "wrap", 5.0)
        output = format_breakdown(t)
        self.assertIn("init", output)
        self.assertIn("test", output)
        self.assertIn("code", output)
        self.assertIn("wrap", output)
        self.assertIn("113.0s", output)  # total

    def test_format_empty_breakdown(self):
        from session_timer import SessionTimer, format_breakdown
        t = SessionTimer(session_id=144)
        output = format_breakdown(t)
        self.assertIn("No steps", output)

    def test_format_category_bar(self):
        """Visual bar chart of category distribution."""
        from session_timer import SessionTimer, format_category_bar
        t = SessionTimer(session_id=144)
        t.add_step("init:a", "init", 10.0)
        t.add_step("code:b", "code", 40.0)
        t.add_step("test:c", "test", 30.0)
        t.add_step("wrap:d", "wrap", 20.0)
        bar = format_category_bar(t)
        self.assertIn("init", bar)
        self.assertIn("code", bar)
        # Code should have the longest bar (40%)
        self.assertIn("%", bar)


class TestCLI(unittest.TestCase):
    """Test CLI entry points."""

    def test_cli_summary_no_data(self):
        """CLI summary with no active timer should not crash."""
        from session_timer import SessionTimer
        t = SessionTimer(session_id=144)
        # Just verify format_breakdown doesn't crash on empty
        from session_timer import format_breakdown
        output = format_breakdown(t)
        self.assertIsInstance(output, str)


if __name__ == "__main__":
    unittest.main()
