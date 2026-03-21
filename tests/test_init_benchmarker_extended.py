#!/usr/bin/env python3
"""
test_init_benchmarker_extended.py — Extended edge-case tests for init_benchmarker.py

Covers: from_dict with extra fields, corrupt bench file lines, zero-baseline division,
speedup calculations, multi-trial verdict, format_comparison_table edge cases.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from init_benchmarker import (
    SessionMetrics,
    save_metrics,
    load_metrics,
    compute_averages,
    compare_trial,
    compute_verdict,
    format_comparison_table,
)


class TestSessionMetricsExtended(unittest.TestCase):
    """Extended edge cases for SessionMetrics."""

    def test_from_dict_ignores_extra_fields(self):
        """from_dict ignores unknown keys not in dataclass fields."""
        d = {
            "session_id": "S99", "init_type": "slim",
            "time_to_first_commit_min": 4.0, "total_commits": 6,
            "new_tests": 77, "loc_shipped": 500, "quality_issues": 0,
            "duration_min": 45,
            "extra_unknown_field": "should be ignored",
        }
        m = SessionMetrics.from_dict(d)
        self.assertEqual(m.session_id, "S99")
        self.assertEqual(m.init_type, "slim")

    def test_to_dict_round_trips_all_fields(self):
        """to_dict includes all required fields for faithful round-trip."""
        m = SessionMetrics("S100", "full", 13.0, 7, 150, 400, 1, 55)
        d = m.to_dict()
        self.assertEqual(d["session_id"], "S100")
        self.assertEqual(d["init_type"], "full")
        self.assertEqual(d["time_to_first_commit_min"], 13.0)
        self.assertEqual(d["total_commits"], 7)
        self.assertEqual(d["new_tests"], 150)
        self.assertEqual(d["loc_shipped"], 400)
        self.assertEqual(d["quality_issues"], 1)
        self.assertEqual(d["duration_min"], 55)

    def test_from_dict_to_dict_round_trip(self):
        """from_dict -> to_dict produces same values."""
        original = SessionMetrics("S101", "slim", 3.5, 5, 60, 200, 0, 40)
        restored = SessionMetrics.from_dict(original.to_dict())
        self.assertEqual(original.session_id, restored.session_id)
        self.assertEqual(original.time_to_first_commit_min, restored.time_to_first_commit_min)


class TestLoadMetricsExtended(unittest.TestCase):
    """Extended edge cases for load_metrics."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.bench_file = Path(self.tmpdir) / "bench.jsonl"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_corrupt_lines_skipped(self):
        """Corrupt JSON lines in bench file are skipped."""
        with open(self.bench_file, "w") as f:
            f.write(json.dumps(SessionMetrics("S95", "full", 12, 5, 100, 300, 0, 50).to_dict()) + "\n")
            f.write("CORRUPTED\n")
            f.write(json.dumps(SessionMetrics("S96", "full", 14, 6, 120, 350, 0, 55).to_dict()) + "\n")
        loaded = load_metrics(bench_file=self.bench_file)
        self.assertEqual(len(loaded), 2)

    def test_blank_lines_skipped(self):
        """Blank lines in bench file are silently ignored."""
        with open(self.bench_file, "w") as f:
            f.write("\n")
            f.write(json.dumps(SessionMetrics("S95", "full", 12, 5, 100, 300, 0, 50).to_dict()) + "\n")
            f.write("\n")
        loaded = load_metrics(bench_file=self.bench_file)
        self.assertEqual(len(loaded), 1)

    def test_no_filter_returns_all(self):
        """load_metrics(init_type=None) returns all sessions regardless of type."""
        save_metrics(SessionMetrics("S95", "full", 12, 5, 100, 300, 0, 50), bench_file=self.bench_file)
        save_metrics(SessionMetrics("S99a", "slim", 4, 6, 77, 500, 0, 45), bench_file=self.bench_file)
        loaded = load_metrics(init_type=None, bench_file=self.bench_file)
        self.assertEqual(len(loaded), 2)

    def test_filter_full_returns_only_full(self):
        """Filter by 'full' returns only full sessions."""
        save_metrics(SessionMetrics("S95", "full", 12, 5, 100, 300, 0, 50), bench_file=self.bench_file)
        save_metrics(SessionMetrics("S96", "full", 14, 6, 120, 350, 0, 55), bench_file=self.bench_file)
        save_metrics(SessionMetrics("S99a", "slim", 4, 6, 77, 500, 0, 45), bench_file=self.bench_file)
        full = load_metrics(init_type="full", bench_file=self.bench_file)
        self.assertEqual(len(full), 2)
        self.assertTrue(all(m.init_type == "full" for m in full))

    def test_multiple_saves_appended(self):
        """Multiple save_metrics calls append to the file."""
        for i in range(4):
            save_metrics(SessionMetrics(f"S{95+i}", "full", 12+i, 5, 100, 300, 0, 50),
                         bench_file=self.bench_file)
        loaded = load_metrics(bench_file=self.bench_file)
        self.assertEqual(len(loaded), 4)


class TestComputeAveragesExtended(unittest.TestCase):
    """Extended edge cases for compute_averages."""

    def test_sessions_with_quality_issues(self):
        """Average includes non-zero quality issues."""
        sessions = [
            SessionMetrics("S1", "full", 10, 5, 100, 300, 2, 50),
            SessionMetrics("S2", "full", 12, 5, 100, 300, 0, 50),
        ]
        avg = compute_averages(sessions)
        self.assertAlmostEqual(avg["quality_issues"], 1.0)

    def test_averages_keys_present(self):
        """compute_averages returns all expected keys."""
        sessions = [SessionMetrics("S1", "full", 10, 5, 100, 300, 0, 50)]
        avg = compute_averages(sessions)
        for key in ("time_to_first_commit_min", "total_commits", "new_tests",
                    "loc_shipped", "quality_issues", "duration_min"):
            self.assertIn(key, avg)

    def test_empty_sessions_all_zeros(self):
        """Empty sessions return all-zero averages."""
        avg = compute_averages([])
        for v in avg.values():
            self.assertEqual(v, 0)


class TestCompareTrialExtended(unittest.TestCase):
    """Extended edge cases for compare_trial."""

    def test_zero_baseline_init_time_not_faster(self):
        """When baseline init time is 0, trial is not marked as faster."""
        baseline_avg = {"time_to_first_commit_min": 0, "total_commits": 5, "new_tests": 100,
                        "loc_shipped": 300, "quality_issues": 0, "duration_min": 50}
        trial = SessionMetrics("S99a", "slim", 3.0, 6, 80, 400, 0, 45)
        result = compare_trial(trial, baseline_avg)
        self.assertFalse(result["init_faster"])
        self.assertEqual(result["init_speedup_pct"], 0)

    def test_zero_baseline_commits_ratio_zero(self):
        """When baseline commits is 0, commits_ratio is 0."""
        baseline_avg = {"time_to_first_commit_min": 10, "total_commits": 0, "new_tests": 100,
                        "loc_shipped": 300, "quality_issues": 0, "duration_min": 50}
        trial = SessionMetrics("S99a", "slim", 4.0, 6, 80, 400, 0, 45)
        result = compare_trial(trial, baseline_avg)
        self.assertEqual(result["commits_ratio"], 0)

    def test_zero_baseline_tests_ratio_zero(self):
        """When baseline tests is 0, tests_ratio is 0."""
        baseline_avg = {"time_to_first_commit_min": 10, "total_commits": 5, "new_tests": 0,
                        "loc_shipped": 300, "quality_issues": 0, "duration_min": 50}
        trial = SessionMetrics("S99a", "slim", 4.0, 6, 80, 400, 0, 45)
        result = compare_trial(trial, baseline_avg)
        self.assertEqual(result["tests_ratio"], 0)

    def test_speedup_percentage_calculation(self):
        """Speedup pct = (baseline - trial) / baseline * 100."""
        baseline_avg = {"time_to_first_commit_min": 10.0, "total_commits": 5, "new_tests": 100,
                        "loc_shipped": 300, "quality_issues": 0, "duration_min": 50}
        trial = SessionMetrics("S99a", "slim", 5.0, 6, 80, 400, 0, 45)
        result = compare_trial(trial, baseline_avg)
        self.assertTrue(result["init_faster"])
        self.assertAlmostEqual(result["init_speedup_pct"], 50.0, places=1)

    def test_negative_speedup_when_slower(self):
        """Trial slower than baseline gets negative speedup pct."""
        baseline_avg = {"time_to_first_commit_min": 10.0, "total_commits": 5, "new_tests": 100,
                        "loc_shipped": 300, "quality_issues": 0, "duration_min": 50}
        trial = SessionMetrics("S99a", "slim", 20.0, 4, 50, 200, 0, 60)
        result = compare_trial(trial, baseline_avg)
        self.assertFalse(result["init_faster"])
        self.assertLess(result["init_speedup_pct"], 0)

    def test_no_quality_issues_flagged_correctly(self):
        """Trial with 0 quality issues: has_quality_issues = False."""
        baseline_avg = {"time_to_first_commit_min": 10.0, "total_commits": 5, "new_tests": 100,
                        "loc_shipped": 300, "quality_issues": 0, "duration_min": 50}
        trial = SessionMetrics("S99a", "slim", 4.0, 6, 80, 400, 0, 45)
        result = compare_trial(trial, baseline_avg)
        self.assertFalse(result["has_quality_issues"])

    def test_result_includes_raw_metrics(self):
        """compare_trial result includes raw trial metric values."""
        baseline_avg = {"time_to_first_commit_min": 10.0, "total_commits": 5, "new_tests": 100,
                        "loc_shipped": 300, "quality_issues": 0, "duration_min": 50}
        trial = SessionMetrics("S99a", "slim", 4.0, 6, 80, 400, 0, 45)
        result = compare_trial(trial, baseline_avg)
        self.assertEqual(result["time_to_first_commit_min"], 4.0)
        self.assertEqual(result["total_commits"], 6)
        self.assertEqual(result["new_tests"], 80)
        self.assertEqual(result["quality_issues"], 0)


class TestComputeVerdictExtended(unittest.TestCase):
    """Extended edge cases for compute_verdict."""

    def test_exactly_two_trials_sufficient(self):
        """Exactly 2 trials is sufficient for verdict."""
        comparisons = [
            {"init_faster": True, "init_speedup_pct": 60, "has_quality_issues": False},
            {"init_faster": True, "init_speedup_pct": 65, "has_quality_issues": False},
        ]
        verdict = compute_verdict(comparisons)
        self.assertTrue(verdict["approved"])

    def test_three_trials_all_good(self):
        """3 trials all passing = approved."""
        comparisons = [
            {"init_faster": True, "init_speedup_pct": 60, "has_quality_issues": False},
            {"init_faster": True, "init_speedup_pct": 65, "has_quality_issues": False},
            {"init_faster": True, "init_speedup_pct": 70, "has_quality_issues": False},
        ]
        verdict = compute_verdict(comparisons)
        self.assertTrue(verdict["approved"])

    def test_approved_message_contains_approved(self):
        """Approved verdict recommendation contains 'APPROVED'."""
        comparisons = [
            {"init_faster": True, "init_speedup_pct": 70, "has_quality_issues": False},
            {"init_faster": True, "init_speedup_pct": 65, "has_quality_issues": False},
        ]
        verdict = compute_verdict(comparisons)
        self.assertIn("APPROVED", verdict["recommendation"])

    def test_approved_includes_avg_speedup_in_message(self):
        """Approved verdict includes average speedup percentage."""
        comparisons = [
            {"init_faster": True, "init_speedup_pct": 70.0, "has_quality_issues": False},
            {"init_faster": True, "init_speedup_pct": 50.0, "has_quality_issues": False},
        ]
        verdict = compute_verdict(comparisons)
        # Average speedup = 60%
        self.assertIn("60", verdict["recommendation"])

    def test_rejected_both_quality_and_slower(self):
        """Quality issues take priority in rejection message."""
        comparisons = [
            {"init_faster": False, "init_speedup_pct": -5, "has_quality_issues": True},
            {"init_faster": True, "init_speedup_pct": 60, "has_quality_issues": False},
        ]
        verdict = compute_verdict(comparisons)
        self.assertFalse(verdict["approved"])
        self.assertIn("Quality", verdict["recommendation"])

    def test_verdict_comparisons_field_present(self):
        """Verdict result always includes comparisons list."""
        comparisons = [
            {"init_faster": True, "init_speedup_pct": 70, "has_quality_issues": False},
            {"init_faster": True, "init_speedup_pct": 65, "has_quality_issues": False},
        ]
        verdict = compute_verdict(comparisons)
        self.assertIn("comparisons", verdict)
        self.assertEqual(len(verdict["comparisons"]), 2)

    def test_need_more_trials_message(self):
        """Single trial shows how many more are needed."""
        comparisons = [
            {"init_faster": True, "init_speedup_pct": 70, "has_quality_issues": False},
        ]
        verdict = compute_verdict(comparisons)
        self.assertFalse(verdict["approved"])
        self.assertIn("1", verdict["recommendation"])  # Have 1, need 2


class TestFormatComparisonTableExtended(unittest.TestCase):
    """Extended edge cases for format_comparison_table."""

    def test_multiple_trials_shown(self):
        """Multiple trial columns appear in the table."""
        baseline_avg = {"time_to_first_commit_min": 13.5, "total_commits": 6.5,
                        "new_tests": 157.5, "quality_issues": 0}
        trials = [
            {"session_id": "S99a", "time_to_first_commit_min": 4.0,
             "total_commits": 6, "new_tests": 77, "quality_issues": 0},
            {"session_id": "S100a", "time_to_first_commit_min": 3.5,
             "total_commits": 7, "new_tests": 90, "quality_issues": 0},
        ]
        table = format_comparison_table(baseline_avg, trials)
        self.assertIn("S99a", table)
        self.assertIn("S100a", table)

    def test_baseline_present_but_no_trials(self):
        """Baseline present but empty trials list = no data."""
        baseline_avg = {"time_to_first_commit_min": 13.5, "total_commits": 6.5,
                        "new_tests": 157.5, "quality_issues": 0}
        table = format_comparison_table(baseline_avg, [])
        self.assertIn("no", table.lower())

    def test_table_contains_metric_labels(self):
        """Table includes expected metric labels."""
        baseline_avg = {"time_to_first_commit_min": 13.5, "total_commits": 6.5,
                        "new_tests": 157.5, "quality_issues": 0}
        trials = [{"session_id": "S99a", "time_to_first_commit_min": 4.0,
                   "total_commits": 6, "new_tests": 77, "quality_issues": 0}]
        table = format_comparison_table(baseline_avg, trials)
        self.assertIn("Init time", table)
        self.assertIn("Quality", table)


if __name__ == "__main__":
    unittest.main()
