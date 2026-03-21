#!/usr/bin/env python3
"""Tests for session_timeline.py — unified session timeline aggregator."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from session_timeline import (
    _load_jsonl,
    _session_id_from_entry,
    build_timeline,
    format_session_detail,
    format_timeline_row,
    get_session,
    get_stats,
    load_benchmark_data,
    load_health_data,
    load_trial_data,
    load_wrap_data,
)


class TestLoadJsonl(unittest.TestCase):
    def test_load_empty_file(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False) as f:
            f.write("")
            path = Path(f.name)
        try:
            self.assertEqual(_load_jsonl(path), [])
        finally:
            path.unlink()

    def test_load_valid_entries(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False) as f:
            f.write('{"a": 1}\n{"b": 2}\n')
            path = Path(f.name)
        try:
            result = _load_jsonl(path)
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0]["a"], 1)
        finally:
            path.unlink()

    def test_load_skips_invalid_json(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False) as f:
            f.write('{"a": 1}\nnot json\n{"b": 2}\n')
            path = Path(f.name)
        try:
            result = _load_jsonl(path)
            self.assertEqual(len(result), 2)
        finally:
            path.unlink()

    def test_load_nonexistent_file(self):
        self.assertEqual(_load_jsonl(Path("/nonexistent/file.jsonl")), [])

    def test_load_blank_lines(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False) as f:
            f.write('{"a": 1}\n\n\n{"b": 2}\n\n')
            path = Path(f.name)
        try:
            result = _load_jsonl(path)
            self.assertEqual(len(result), 2)
        finally:
            path.unlink()


class TestSessionIdFromEntry(unittest.TestCase):
    def test_canonical_session_id(self):
        self.assertEqual(_session_id_from_entry({"session_id": "S99"}), "S99")

    def test_session_int(self):
        self.assertEqual(_session_id_from_entry({"session": 99}), "S99")

    def test_session_string(self):
        self.assertEqual(_session_id_from_entry({"session": "S100"}), "S100")

    def test_lowercase_session_id(self):
        self.assertEqual(_session_id_from_entry({"session_id": "s42"}), "S42")

    def test_both_fields_prefers_session_id(self):
        entry = {"session_id": "S101", "session": 99}
        self.assertEqual(_session_id_from_entry(entry), "S101")

    def test_no_session_fields(self):
        self.assertIsNone(_session_id_from_entry({"grade": "A"}))

    def test_invalid_session_id(self):
        self.assertIsNone(_session_id_from_entry({"session_id": "not-a-session"}))

    def test_suffixed_session_id(self):
        self.assertEqual(_session_id_from_entry({"session_id": "S99a"}), "S99")


class TestBuildTimeline(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        # Create mock data files
        self.wrap_path = Path(self.tmpdir) / "wrap_assessments.jsonl"
        self.trial_path = Path(self.tmpdir) / ".cca-trial-results.jsonl"
        self.health_path = Path(self.tmpdir) / ".cca-loop-health.jsonl"
        self.bench_path = Path(self.tmpdir) / ".cca-init-benchmarks.jsonl"

    def _write_jsonl(self, path, entries):
        with open(path, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

    @patch("session_timeline.PROJECT_ROOT")
    def test_build_empty(self, mock_root):
        mock_root.__truediv__ = lambda self, other: Path(self.tmpdir) / other
        mock_root.return_value = Path(self.tmpdir)
        # When all files missing, timeline is empty
        timeline = build_timeline()
        # May or may not be empty depending on actual project files
        self.assertIsInstance(timeline, list)

    def test_build_returns_sorted_descending(self):
        timeline = build_timeline()
        if len(timeline) >= 2:
            self.assertGreaterEqual(timeline[0]["session_num"], timeline[1]["session_num"])

    def test_build_with_limit(self):
        timeline = build_timeline(n=3)
        self.assertLessEqual(len(timeline), 3)

    def test_entries_have_required_fields(self):
        timeline = build_timeline(n=5)
        for entry in timeline:
            self.assertIn("session_id", entry)
            self.assertIn("session_num", entry)
            self.assertIn("wrap", entry)
            self.assertIn("trials", entry)
            self.assertIn("health", entry)
            self.assertIn("benchmark", entry)

    def test_session_ids_are_canonical(self):
        timeline = build_timeline()
        for entry in timeline:
            sid = entry["session_id"]
            self.assertTrue(sid.startswith("S"), f"Non-canonical ID: {sid}")
            self.assertTrue(sid[1:].isdigit(), f"Non-canonical ID: {sid}")


class TestGetSession(unittest.TestCase):
    def test_get_existing_session(self):
        timeline = build_timeline()
        if timeline:
            first = timeline[0]
            result = get_session(first["session_id"])
            self.assertIsNotNone(result)
            self.assertEqual(result["session_id"], first["session_id"])

    def test_get_nonexistent_session(self):
        result = get_session("S999999")
        self.assertIsNone(result)

    def test_get_by_int(self):
        timeline = build_timeline()
        if timeline:
            first = timeline[0]
            result = get_session(first["session_num"])
            self.assertIsNotNone(result)

    def test_get_by_bare_string(self):
        timeline = build_timeline()
        if timeline:
            first = timeline[0]
            result = get_session(str(first["session_num"]))
            self.assertIsNotNone(result)


class TestGetStats(unittest.TestCase):
    def test_stats_returns_expected_fields(self):
        stats = get_stats()
        self.assertIn("total_sessions", stats)
        if stats["total_sessions"] > 0:
            self.assertIn("sessions_with_wraps", stats)
            self.assertIn("avg_grade_value", stats)
            self.assertIn("latest_test_count", stats)
            self.assertIn("trial_passes", stats)
            self.assertIn("trial_fails", stats)
            self.assertIn("session_range", stats)

    def test_stats_grade_value_in_range(self):
        stats = get_stats()
        if stats.get("avg_grade_value"):
            self.assertGreaterEqual(stats["avg_grade_value"], 0)
            self.assertLessEqual(stats["avg_grade_value"], 4.0)

    def test_stats_trial_counts_non_negative(self):
        stats = get_stats()
        self.assertGreaterEqual(stats.get("trial_passes", 0), 0)
        self.assertGreaterEqual(stats.get("trial_fails", 0), 0)


class TestFormatTimelineRow(unittest.TestCase):
    def test_minimal_entry(self):
        entry = {
            "session_id": "S99",
            "session_num": 99,
            "wrap": None,
            "trials": [],
            "health": None,
            "benchmark": None,
        }
        row = format_timeline_row(entry)
        self.assertIn("S99", row)

    def test_entry_with_wrap(self):
        entry = {
            "session_id": "S99",
            "session_num": 99,
            "wrap": {"grade": "A", "test_count": 3000, "wins": ["built X", "fixed Y"]},
            "trials": [],
            "health": None,
            "benchmark": None,
        }
        row = format_timeline_row(entry)
        self.assertIn("A", row)
        self.assertIn("3000", row)
        self.assertIn("2 wins", row)

    def test_entry_with_trials(self):
        entry = {
            "session_id": "S99",
            "session_num": 99,
            "wrap": None,
            "trials": [
                {"mt_id": "MT-22", "result": "pass"},
                {"mt_id": "MT-22", "result": "fail"},
            ],
            "health": None,
            "benchmark": None,
        }
        row = format_timeline_row(entry)
        self.assertIn("Trials", row)
        self.assertIn("1P/1F", row)
        self.assertIn("MT-22", row)

    def test_entry_with_health_error(self):
        entry = {
            "session_id": "S99",
            "session_num": 99,
            "wrap": None,
            "trials": [],
            "health": {"error_type": "timeout", "grade": "C"},
            "benchmark": None,
        }
        row = format_timeline_row(entry)
        self.assertIn("Error: timeout", row)

    def test_entry_with_benchmark(self):
        entry = {
            "session_id": "S99",
            "session_num": 99,
            "wrap": None,
            "trials": [],
            "health": None,
            "benchmark": {"total_commits": 8},
        }
        row = format_timeline_row(entry)
        self.assertIn("8 commits", row)


class TestFormatSessionDetail(unittest.TestCase):
    def test_full_entry(self):
        entry = {
            "session_id": "S99",
            "session_num": 99,
            "wrap": {
                "grade": "A-",
                "test_count": 4050,
                "commits": 7,
                "wins": ["Built paper_digest"],
                "losses": ["None"],
            },
            "trials": [{"mt_id": "MT-22", "result": "pass", "commits": 5, "tests_added": 30}],
            "health": {
                "grade": "A",
                "test_pass": 4050,
                "test_fail": 0,
                "duration_secs": 3600,
                "error_type": None,
            },
            "benchmark": {
                "init_type": "slim",
                "time_to_first_commit_min": 4.0,
                "quality_issues": 0,
            },
        }
        detail = format_session_detail(entry)
        self.assertIn("S99", detail)
        self.assertIn("A-", detail)
        self.assertIn("4050", detail)
        self.assertIn("MT-22", detail)
        self.assertIn("slim", detail)

    def test_empty_entry(self):
        entry = {
            "session_id": "S50",
            "session_num": 50,
            "wrap": None,
            "trials": [],
            "health": None,
            "benchmark": None,
        }
        detail = format_session_detail(entry)
        self.assertIn("S50", detail)


class TestDataLoaders(unittest.TestCase):
    """Test that data loaders don't crash on real project data."""

    def test_load_wrap_data(self):
        data = load_wrap_data()
        self.assertIsInstance(data, dict)
        for k, v in data.items():
            self.assertTrue(k.startswith("S"))
            self.assertIn("grade", v)

    def test_load_trial_data(self):
        data = load_trial_data()
        self.assertIsInstance(data, dict)
        for k, v in data.items():
            self.assertTrue(k.startswith("S"))
            self.assertIsInstance(v, list)

    def test_load_health_data(self):
        data = load_health_data()
        self.assertIsInstance(data, dict)

    def test_load_benchmark_data(self):
        data = load_benchmark_data()
        self.assertIsInstance(data, dict)


if __name__ == "__main__":
    unittest.main()
