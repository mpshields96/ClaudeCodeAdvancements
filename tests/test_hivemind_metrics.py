"""Tests for hivemind_metrics.py — Phase 1 validation metrics tracker."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hivemind_metrics import HivemindMetrics


class TestRecordSession(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.metrics = HivemindMetrics(path=self.tmp.name)

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_record_session_writes_entry(self):
        self.metrics.record_session(
            session_id="S90",
            sessions_completed=1,
            coordination_failures=0,
            task_completions=3,
            worker_regressions=0,
            overhead_ratio=0.07,
        )
        with open(self.tmp.name) as f:
            entry = json.loads(f.readline())
        self.assertEqual(entry["session_id"], "S90")
        self.assertEqual(entry["task_completions"], 3)

    def test_record_session_appends_multiple(self):
        for i in range(3):
            self.metrics.record_session(
                session_id=f"S{i}",
                sessions_completed=1,
                coordination_failures=0,
                task_completions=1,
                worker_regressions=0,
                overhead_ratio=0.05,
            )
        with open(self.tmp.name) as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 3)

    def test_record_session_includes_date(self):
        self.metrics.record_session(
            session_id="S90",
            sessions_completed=1,
            coordination_failures=0,
            task_completions=1,
            worker_regressions=0,
            overhead_ratio=0.08,
        )
        with open(self.tmp.name) as f:
            entry = json.loads(f.readline())
        self.assertIn("date", entry)
        self.assertRegex(entry["date"], r"\d{4}-\d{2}-\d{2}")

    def test_record_session_stores_all_fields(self):
        self.metrics.record_session(
            session_id="S91",
            sessions_completed=2,
            coordination_failures=1,
            task_completions=5,
            worker_regressions=1,
            overhead_ratio=0.12,
        )
        with open(self.tmp.name) as f:
            entry = json.loads(f.readline())
        self.assertEqual(entry["sessions_completed"], 2)
        self.assertEqual(entry["coordination_failures"], 1)
        self.assertEqual(entry["task_completions"], 5)
        self.assertEqual(entry["worker_regressions"], 1)
        self.assertAlmostEqual(entry["overhead_ratio"], 0.12)


class TestGetStats(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.metrics = HivemindMetrics(path=self.tmp.name)

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_get_stats_empty_returns_zeros(self):
        stats = self.metrics.get_stats()
        self.assertEqual(stats["total_sessions"], 0)
        self.assertEqual(stats["total_task_completions"], 0)
        self.assertEqual(stats["total_coordination_failures"], 0)
        self.assertEqual(stats["total_worker_regressions"], 0)
        self.assertIsNone(stats["last_session"])

    def test_get_stats_totals(self):
        self.metrics.record_session("S1", 1, 2, 4, 1, 0.08)
        self.metrics.record_session("S2", 1, 0, 3, 0, 0.06)
        stats = self.metrics.get_stats()
        self.assertEqual(stats["total_sessions"], 2)
        self.assertEqual(stats["total_coordination_failures"], 2)
        self.assertEqual(stats["total_task_completions"], 7)
        self.assertEqual(stats["total_worker_regressions"], 1)

    def test_get_stats_avg_overhead(self):
        self.metrics.record_session("S1", 1, 0, 2, 0, 0.08)
        self.metrics.record_session("S2", 1, 0, 2, 0, 0.12)
        stats = self.metrics.get_stats()
        self.assertAlmostEqual(stats["avg_overhead_ratio"], 0.10, places=5)

    def test_get_stats_failure_rate(self):
        self.metrics.record_session("S1", 1, 1, 3, 0, 0.07)
        self.metrics.record_session("S2", 1, 0, 2, 0, 0.05)
        stats = self.metrics.get_stats()
        # failure_rate = total_coordination_failures / total_sessions
        self.assertAlmostEqual(stats["failure_rate"], 0.5, places=5)

    def test_get_stats_regression_rate(self):
        self.metrics.record_session("S1", 1, 0, 4, 1, 0.07)
        self.metrics.record_session("S2", 1, 0, 4, 0, 0.07)
        stats = self.metrics.get_stats()
        # regression_rate = total_worker_regressions / total_task_completions
        self.assertAlmostEqual(stats["regression_rate"], 0.125, places=5)

    def test_get_stats_last_session(self):
        self.metrics.record_session("S1", 1, 0, 2, 0, 0.07)
        self.metrics.record_session("S2", 1, 0, 4, 0, 0.09)
        stats = self.metrics.get_stats()
        self.assertEqual(stats["last_session"]["session_id"], "S2")

    def test_get_stats_zero_task_completions_regression_rate(self):
        self.metrics.record_session("S1", 1, 1, 0, 0, 0.05)
        stats = self.metrics.get_stats()
        self.assertEqual(stats["regression_rate"], 0.0)

    def test_get_stats_zero_sessions_failure_rate(self):
        stats = self.metrics.get_stats()
        self.assertEqual(stats["failure_rate"], 0.0)


class TestFormatForInit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.metrics = HivemindMetrics(path=self.tmp.name)

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_format_for_init_no_data(self):
        line = self.metrics.format_for_init()
        self.assertIn("Hivemind", line)
        self.assertIn("0 sessions", line)

    def test_format_for_init_with_data(self):
        self.metrics.record_session("S1", 1, 0, 3, 0, 0.07)
        self.metrics.record_session("S2", 1, 1, 2, 1, 0.09)
        line = self.metrics.format_for_init()
        self.assertIn("2 sessions", line)
        self.assertIn("5 tasks", line)
        self.assertIn("1 failure", line)

    def test_format_for_init_is_one_line(self):
        self.metrics.record_session("S1", 1, 0, 2, 0, 0.07)
        line = self.metrics.format_for_init()
        self.assertNotIn("\n", line)

    def test_format_for_init_includes_overhead(self):
        self.metrics.record_session("S1", 1, 0, 2, 0, 0.08)
        line = self.metrics.format_for_init()
        self.assertIn("overhead", line.lower())

    def test_format_for_init_plural_sessions(self):
        self.metrics.record_session("S1", 1, 0, 3, 0, 0.07)
        line = self.metrics.format_for_init()
        self.assertIn("1 session", line)

    def test_format_for_init_plural_failures(self):
        self.metrics.record_session("S1", 1, 2, 3, 0, 0.07)
        line = self.metrics.format_for_init()
        self.assertIn("2 failure", line)


class TestDefaultPath(unittest.TestCase):
    def test_default_path_is_jsonl(self):
        m = HivemindMetrics()
        self.assertTrue(m.path.endswith(".jsonl"))

    def test_default_path_exists_after_record(self):
        tmp = tempfile.mktemp(suffix=".jsonl")
        m = HivemindMetrics(path=tmp)
        try:
            m.record_session("S1", 1, 0, 1, 0, 0.07)
            self.assertTrue(os.path.exists(tmp))
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)


if __name__ == "__main__":
    unittest.main()
