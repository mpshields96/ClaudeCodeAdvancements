"""
test_init_benchmarker.py — Tests for init_benchmarker.py

Compares slim init trial metrics against full init baselines (S95-S98).
Determines if slim init should become the permanent default.

TDD: tests first.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestSessionMetrics(unittest.TestCase):
    """Test the SessionMetrics dataclass."""

    def test_create_metrics(self):
        from init_benchmarker import SessionMetrics
        m = SessionMetrics(
            session_id="S99a",
            init_type="slim",
            time_to_first_commit_min=4.0,
            total_commits=6,
            new_tests=77,
            loc_shipped=500,
            quality_issues=0,
            duration_min=45,
        )
        self.assertEqual(m.session_id, "S99a")
        self.assertEqual(m.init_type, "slim")

    def test_metrics_to_dict(self):
        from init_benchmarker import SessionMetrics
        m = SessionMetrics("S99a", "slim", 4.0, 6, 77, 500, 0, 45)
        d = m.to_dict()
        self.assertEqual(d["session_id"], "S99a")
        self.assertIn("init_type", d)

    def test_metrics_from_dict(self):
        from init_benchmarker import SessionMetrics
        d = {
            "session_id": "S95", "init_type": "full",
            "time_to_first_commit_min": 12.0, "total_commits": 5,
            "new_tests": 100, "loc_shipped": 300, "quality_issues": 0,
            "duration_min": 55,
        }
        m = SessionMetrics.from_dict(d)
        self.assertEqual(m.time_to_first_commit_min, 12.0)


class TestBaselineData(unittest.TestCase):
    """Test loading and computing baseline averages."""

    def test_baseline_averages(self):
        from init_benchmarker import compute_averages, SessionMetrics
        sessions = [
            SessionMetrics("S95", "full", 12.0, 5, 100, 300, 0, 50),
            SessionMetrics("S96", "full", 14.0, 8, 200, 600, 0, 60),
            SessionMetrics("S97", "full", 13.0, 6, 150, 400, 0, 55),
            SessionMetrics("S98", "full", 15.0, 7, 180, 500, 0, 58),
        ]
        avg = compute_averages(sessions)
        self.assertAlmostEqual(avg["time_to_first_commit_min"], 13.5)
        self.assertAlmostEqual(avg["total_commits"], 6.5)
        self.assertAlmostEqual(avg["new_tests"], 157.5)
        self.assertEqual(avg["quality_issues"], 0)

    def test_baseline_empty(self):
        from init_benchmarker import compute_averages
        avg = compute_averages([])
        self.assertEqual(avg["time_to_first_commit_min"], 0)

    def test_baseline_single(self):
        from init_benchmarker import compute_averages, SessionMetrics
        sessions = [SessionMetrics("S95", "full", 12.0, 5, 100, 300, 0, 50)]
        avg = compute_averages(sessions)
        self.assertEqual(avg["time_to_first_commit_min"], 12.0)


class TestComparison(unittest.TestCase):
    """Test comparing trial metrics against baseline."""

    def test_trial_beats_baseline(self):
        from init_benchmarker import compare_trial, SessionMetrics
        baseline_avg = {
            "time_to_first_commit_min": 13.5,
            "total_commits": 6.5,
            "new_tests": 157.5,
            "loc_shipped": 450.0,
            "quality_issues": 0,
            "duration_min": 55.75,
        }
        trial = SessionMetrics("S99a", "slim", 4.0, 7, 77, 500, 0, 45)
        result = compare_trial(trial, baseline_avg)
        self.assertTrue(result["init_faster"])
        self.assertGreater(result["init_speedup_pct"], 50)

    def test_trial_worse_than_baseline(self):
        from init_benchmarker import compare_trial, SessionMetrics
        baseline_avg = {
            "time_to_first_commit_min": 13.5,
            "total_commits": 6.5,
            "new_tests": 157.5,
            "loc_shipped": 450.0,
            "quality_issues": 0,
            "duration_min": 55.75,
        }
        trial = SessionMetrics("S99a", "slim", 20.0, 2, 10, 50, 3, 45)
        result = compare_trial(trial, baseline_avg)
        self.assertFalse(result["init_faster"])
        self.assertTrue(result["has_quality_issues"])

    def test_trial_equal_to_baseline(self):
        from init_benchmarker import compare_trial, SessionMetrics
        baseline_avg = {
            "time_to_first_commit_min": 5.0,
            "total_commits": 5,
            "new_tests": 100,
            "loc_shipped": 300,
            "quality_issues": 0,
            "duration_min": 45,
        }
        trial = SessionMetrics("S99a", "slim", 5.0, 5, 100, 300, 0, 45)
        result = compare_trial(trial, baseline_avg)
        self.assertFalse(result["init_faster"])  # not strictly faster
        self.assertFalse(result["has_quality_issues"])


class TestVerdict(unittest.TestCase):
    """Test the final verdict: should slim init become default?"""

    def test_approve_both_trials_good(self):
        from init_benchmarker import compute_verdict
        comparisons = [
            {"init_faster": True, "init_speedup_pct": 70, "has_quality_issues": False,
             "commits_ratio": 1.1, "tests_ratio": 0.8},
            {"init_faster": True, "init_speedup_pct": 65, "has_quality_issues": False,
             "commits_ratio": 1.0, "tests_ratio": 0.9},
        ]
        verdict = compute_verdict(comparisons)
        self.assertTrue(verdict["approved"])
        self.assertIn("approved", verdict["recommendation"].lower())

    def test_reject_quality_issues(self):
        from init_benchmarker import compute_verdict
        comparisons = [
            {"init_faster": True, "init_speedup_pct": 70, "has_quality_issues": True,
             "commits_ratio": 1.0, "tests_ratio": 0.5},
            {"init_faster": True, "init_speedup_pct": 65, "has_quality_issues": False,
             "commits_ratio": 1.0, "tests_ratio": 0.9},
        ]
        verdict = compute_verdict(comparisons)
        self.assertFalse(verdict["approved"])

    def test_reject_slower_init(self):
        from init_benchmarker import compute_verdict
        comparisons = [
            {"init_faster": False, "init_speedup_pct": -10, "has_quality_issues": False,
             "commits_ratio": 1.0, "tests_ratio": 0.9},
            {"init_faster": True, "init_speedup_pct": 65, "has_quality_issues": False,
             "commits_ratio": 1.0, "tests_ratio": 0.9},
        ]
        verdict = compute_verdict(comparisons)
        self.assertFalse(verdict["approved"])

    def test_reject_single_trial(self):
        """Need at least 2 trials to approve."""
        from init_benchmarker import compute_verdict
        comparisons = [
            {"init_faster": True, "init_speedup_pct": 70, "has_quality_issues": False,
             "commits_ratio": 1.1, "tests_ratio": 0.9},
        ]
        verdict = compute_verdict(comparisons)
        self.assertFalse(verdict["approved"])

    def test_empty_comparisons(self):
        from init_benchmarker import compute_verdict
        verdict = compute_verdict([])
        self.assertFalse(verdict["approved"])


class TestStorage(unittest.TestCase):
    """Test saving/loading benchmark data."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.bench_file = Path(self.tmpdir) / "benchmarks.jsonl"

    def tearDown(self):
        if self.bench_file.exists():
            self.bench_file.unlink()
        os.rmdir(self.tmpdir)

    def test_save_and_load(self):
        from init_benchmarker import save_metrics, load_metrics, SessionMetrics
        m = SessionMetrics("S99a", "slim", 4.0, 6, 77, 500, 0, 45)
        save_metrics(m, bench_file=self.bench_file)
        loaded = load_metrics(bench_file=self.bench_file)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].session_id, "S99a")

    def test_load_empty(self):
        from init_benchmarker import load_metrics
        loaded = load_metrics(bench_file=self.bench_file)
        self.assertEqual(loaded, [])

    def test_filter_by_type(self):
        from init_benchmarker import save_metrics, load_metrics, SessionMetrics
        save_metrics(SessionMetrics("S95", "full", 12, 5, 100, 300, 0, 50), bench_file=self.bench_file)
        save_metrics(SessionMetrics("S99a", "slim", 4, 6, 77, 500, 0, 45), bench_file=self.bench_file)
        slim = load_metrics(init_type="slim", bench_file=self.bench_file)
        self.assertEqual(len(slim), 1)
        self.assertEqual(slim[0].init_type, "slim")


class TestFormatReport(unittest.TestCase):
    """Test report formatting."""

    def test_format_comparison_table(self):
        from init_benchmarker import format_comparison_table
        baseline_avg = {"time_to_first_commit_min": 13.5, "total_commits": 6.5,
                       "new_tests": 157.5, "quality_issues": 0}
        trials = [
            {"session_id": "S99a", "time_to_first_commit_min": 4.0,
             "total_commits": 6, "new_tests": 77, "quality_issues": 0},
        ]
        table = format_comparison_table(baseline_avg, trials)
        self.assertIn("S99a", table)
        self.assertIn("13.5", table)

    def test_format_empty(self):
        from init_benchmarker import format_comparison_table
        table = format_comparison_table({}, [])
        self.assertIn("no", table.lower())


if __name__ == "__main__":
    unittest.main()
