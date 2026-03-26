#!/usr/bin/env python3
"""Tests for session_metrics.py — MT-49 Phase 6: Session-over-session metrics.

Tracks whether CCA is measurably getting smarter over time by computing
trends across session journal data: grades, test velocity, learnings captured,
win/pain ratios, principle counts, and APF.
"""
import json
import os
import sys
import tempfile
import unittest

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PARENT_DIR)

from session_metrics import (
    SessionSnapshot,
    MetricsTrend,
    SessionMetricsTracker,
    compute_trend_direction,
    grade_to_numeric,
)


class TestGradeToNumeric(unittest.TestCase):
    """Test grade string → numeric conversion."""

    def test_a_plus(self):
        self.assertAlmostEqual(grade_to_numeric("A+"), 4.3)

    def test_a(self):
        self.assertAlmostEqual(grade_to_numeric("A"), 4.0)

    def test_a_minus(self):
        self.assertAlmostEqual(grade_to_numeric("A-"), 3.7)

    def test_b_plus(self):
        self.assertAlmostEqual(grade_to_numeric("B+"), 3.3)

    def test_b(self):
        self.assertAlmostEqual(grade_to_numeric("B"), 3.0)

    def test_c(self):
        self.assertAlmostEqual(grade_to_numeric("C"), 2.0)

    def test_unknown_returns_none(self):
        self.assertIsNone(grade_to_numeric("X"))

    def test_empty_returns_none(self):
        self.assertIsNone(grade_to_numeric(""))

    def test_none_returns_none(self):
        self.assertIsNone(grade_to_numeric(None))


class TestComputeTrendDirection(unittest.TestCase):
    """Test trend computation from a series of values."""

    def test_improving_trend(self):
        result = compute_trend_direction([1.0, 2.0, 3.0, 4.0, 5.0])
        self.assertEqual(result.direction, "improving")
        self.assertGreater(result.slope, 0)

    def test_declining_trend(self):
        result = compute_trend_direction([5.0, 4.0, 3.0, 2.0, 1.0])
        self.assertEqual(result.direction, "declining")
        self.assertLess(result.slope, 0)

    def test_stable_trend(self):
        result = compute_trend_direction([3.0, 3.0, 3.0, 3.0, 3.0])
        self.assertEqual(result.direction, "stable")
        self.assertAlmostEqual(result.slope, 0.0)

    def test_too_few_points_returns_insufficient(self):
        result = compute_trend_direction([1.0])
        self.assertEqual(result.direction, "insufficient_data")

    def test_empty_returns_insufficient(self):
        result = compute_trend_direction([])
        self.assertEqual(result.direction, "insufficient_data")

    def test_two_points_works(self):
        result = compute_trend_direction([1.0, 3.0])
        self.assertIn(result.direction, ["improving", "stable", "declining"])

    def test_noisy_but_improving(self):
        # Overall upward despite noise
        result = compute_trend_direction([1.0, 3.0, 2.0, 4.0, 3.0, 5.0, 4.0, 6.0])
        self.assertEqual(result.direction, "improving")

    def test_trend_has_recent_avg(self):
        result = compute_trend_direction([1.0, 2.0, 3.0, 4.0, 5.0])
        self.assertIsNotNone(result.recent_avg)
        # Recent avg should be close to 4.5 (last 2 values avg)
        self.assertGreater(result.recent_avg, 3.0)


class TestSessionSnapshot(unittest.TestCase):
    """Test building session snapshots from journal entries."""

    def test_from_session_outcome_entry(self):
        entry = {
            "timestamp": "2026-03-20T00:00:00Z",
            "event_type": "session_outcome",
            "session_id": 100,
            "outcome": "success",
            "metrics": {"grade": "A", "tests_after": 5000, "tests_new": 50},
            "learnings": ["learning1", "learning2"],
        }
        snap = SessionSnapshot.from_journal_entry(entry)
        self.assertEqual(snap.session_id, 100)
        self.assertEqual(snap.grade, "A")
        self.assertAlmostEqual(snap.grade_numeric, 4.0)
        self.assertEqual(snap.tests_total, 5000)
        self.assertEqual(snap.tests_new, 50)
        self.assertEqual(snap.learnings_count, 2)

    def test_from_entry_without_grade(self):
        entry = {
            "timestamp": "2026-03-20T00:00:00Z",
            "event_type": "session_outcome",
            "session_id": 101,
            "outcome": "success",
            "metrics": {"tests_after": 5050},
            "learnings": [],
        }
        snap = SessionSnapshot.from_journal_entry(entry)
        self.assertEqual(snap.session_id, 101)
        self.assertIsNone(snap.grade)
        self.assertIsNone(snap.grade_numeric)

    def test_from_entry_with_signal_rate(self):
        entry = {
            "timestamp": "2026-03-20T00:00:00Z",
            "event_type": "session_outcome",
            "session_id": 102,
            "metrics": {"signal_rate": 0.35, "grade": "B+"},
            "learnings": ["a"],
        }
        snap = SessionSnapshot.from_journal_entry(entry)
        self.assertAlmostEqual(snap.apf, 0.35)

    def test_from_entry_with_commits(self):
        entry = {
            "timestamp": "2026-03-20T00:00:00Z",
            "event_type": "session_outcome",
            "session_id": 103,
            "metrics": {"commits": 5},
            "learnings": [],
        }
        snap = SessionSnapshot.from_journal_entry(entry)
        self.assertEqual(snap.commits, 5)


class TestSessionMetricsTracker(unittest.TestCase):
    """Test the main tracker that aggregates journal data into metrics."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.journal_path = os.path.join(self.tmpdir, "journal.jsonl")
        self.principles_path = os.path.join(self.tmpdir, "principles.jsonl")

    def _write_journal(self, entries):
        with open(self.journal_path, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

    def _write_principles(self, principles):
        with open(self.principles_path, "w") as f:
            for p in principles:
                f.write(json.dumps(p) + "\n")

    def _make_outcome(self, sid, grade="A", tests_after=1000, tests_new=10,
                      learnings=None, commits=3, signal_rate=None):
        entry = {
            "timestamp": f"2026-03-{sid:02d}T00:00:00Z",
            "event_type": "session_outcome",
            "session_id": sid,
            "outcome": "success",
            "metrics": {
                "grade": grade,
                "tests_after": tests_after,
                "tests_new": tests_new,
                "commits": commits,
            },
            "learnings": learnings or [],
        }
        if signal_rate is not None:
            entry["metrics"]["signal_rate"] = signal_rate
        return entry

    def test_load_journal_entries(self):
        entries = [self._make_outcome(1), self._make_outcome(2)]
        self._write_journal(entries)
        tracker = SessionMetricsTracker(journal_path=self.journal_path)
        self.assertEqual(len(tracker.snapshots), 2)

    def test_filters_non_outcome_events(self):
        entries = [
            self._make_outcome(1),
            {"event_type": "win", "timestamp": "2026-03-01T00:00:00Z"},
            {"event_type": "pain", "timestamp": "2026-03-01T00:00:00Z"},
            self._make_outcome(2),
        ]
        self._write_journal(entries)
        tracker = SessionMetricsTracker(journal_path=self.journal_path)
        self.assertEqual(len(tracker.snapshots), 2)

    def test_deduplicates_sessions_keeps_latest(self):
        entries = [
            self._make_outcome(1, grade="B"),
            self._make_outcome(1, grade="A"),  # Same session, later entry
        ]
        self._write_journal(entries)
        tracker = SessionMetricsTracker(journal_path=self.journal_path)
        self.assertEqual(len(tracker.snapshots), 1)
        self.assertEqual(tracker.snapshots[0].grade, "A")

    def test_grade_trend(self):
        entries = [
            self._make_outcome(1, grade="C"),
            self._make_outcome(2, grade="B"),
            self._make_outcome(3, grade="B+"),
            self._make_outcome(4, grade="A-"),
            self._make_outcome(5, grade="A"),
        ]
        self._write_journal(entries)
        tracker = SessionMetricsTracker(journal_path=self.journal_path)
        trend = tracker.grade_trend()
        self.assertEqual(trend.direction, "improving")

    def test_test_velocity_trend(self):
        entries = [
            self._make_outcome(1, tests_new=10),
            self._make_outcome(2, tests_new=20),
            self._make_outcome(3, tests_new=30),
            self._make_outcome(4, tests_new=40),
        ]
        self._write_journal(entries)
        tracker = SessionMetricsTracker(journal_path=self.journal_path)
        trend = tracker.test_velocity_trend()
        self.assertEqual(trend.direction, "improving")

    def test_learnings_trend(self):
        entries = [
            self._make_outcome(1, learnings=["a"]),
            self._make_outcome(2, learnings=["a", "b"]),
            self._make_outcome(3, learnings=["a", "b", "c"]),
        ]
        self._write_journal(entries)
        tracker = SessionMetricsTracker(journal_path=self.journal_path)
        trend = tracker.learnings_trend()
        self.assertEqual(trend.direction, "improving")

    def test_win_pain_ratio_tracking(self):
        entries = [
            self._make_outcome(1),
            {"event_type": "win", "session_id": 1, "timestamp": "2026-03-01T00:00:00Z"},
            {"event_type": "win", "session_id": 1, "timestamp": "2026-03-01T01:00:00Z"},
            {"event_type": "pain", "session_id": 1, "timestamp": "2026-03-01T02:00:00Z"},
            self._make_outcome(2),
            {"event_type": "win", "session_id": 2, "timestamp": "2026-03-02T00:00:00Z"},
        ]
        self._write_journal(entries)
        tracker = SessionMetricsTracker(journal_path=self.journal_path)
        ratios = tracker.win_pain_ratios()
        self.assertEqual(len(ratios), 2)
        # Session 1: 2 wins / 1 pain = 2.0
        self.assertAlmostEqual(ratios[0], 2.0)
        # Session 2: 1 win / 0 pain → 1 win / max(0,1) = 1.0
        self.assertGreaterEqual(ratios[1], 1.0)

    def test_summary_report_structure(self):
        entries = [
            self._make_outcome(i, grade="A", tests_new=10 + i, learnings=["l"] * i)
            for i in range(1, 8)
        ]
        self._write_journal(entries)
        tracker = SessionMetricsTracker(journal_path=self.journal_path)
        report = tracker.summary_report()
        self.assertIn("total_sessions", report)
        self.assertIn("grade_trend", report)
        self.assertIn("test_velocity_trend", report)
        self.assertIn("learnings_trend", report)
        self.assertIn("latest_session", report)

    def test_summary_report_latest_session(self):
        entries = [
            self._make_outcome(50, grade="A-", tests_after=10000, tests_new=45),
        ]
        self._write_journal(entries)
        tracker = SessionMetricsTracker(journal_path=self.journal_path)
        report = tracker.summary_report()
        self.assertEqual(report["latest_session"]["session_id"], 50)
        self.assertEqual(report["latest_session"]["grade"], "A-")

    def test_empty_journal(self):
        self._write_journal([])
        tracker = SessionMetricsTracker(journal_path=self.journal_path)
        report = tracker.summary_report()
        self.assertEqual(report["total_sessions"], 0)
        self.assertEqual(report["grade_trend"]["direction"], "insufficient_data")

    def test_briefing_text(self):
        entries = [
            self._make_outcome(i, grade="A", tests_new=10 * i) for i in range(1, 6)
        ]
        self._write_journal(entries)
        tracker = SessionMetricsTracker(journal_path=self.journal_path)
        text = tracker.briefing_text()
        self.assertIsInstance(text, str)
        self.assertGreater(len(text), 20)
        # Should contain direction words
        self.assertTrue(
            any(w in text.lower() for w in ["improving", "stable", "declining", "sessions"])
        )

    def test_principle_count_from_file(self):
        entries = [self._make_outcome(1)]
        self._write_journal(entries)
        # Write some principles
        self._write_principles([
            {"id": "p1", "text": "test first", "pruned": False},
            {"id": "p2", "text": "commit often", "pruned": False},
            {"id": "p3", "text": "old rule", "pruned": True},
        ])
        tracker = SessionMetricsTracker(
            journal_path=self.journal_path,
            principles_path=self.principles_path,
        )
        report = tracker.summary_report()
        self.assertEqual(report["principle_count"]["active"], 2)
        self.assertEqual(report["principle_count"]["pruned"], 1)

    def test_handles_malformed_journal_lines(self):
        with open(self.journal_path, "w") as f:
            f.write('{"event_type": "session_outcome", "session_id": 1, "metrics": {}, "learnings": [], "timestamp": "2026-03-01T00:00:00Z"}\n')
            f.write("NOT JSON\n")
            f.write('{"event_type": "session_outcome", "session_id": 2, "metrics": {}, "learnings": [], "timestamp": "2026-03-02T00:00:00Z"}\n')
        tracker = SessionMetricsTracker(journal_path=self.journal_path)
        self.assertEqual(len(tracker.snapshots), 2)

    def test_nonexistent_journal_returns_empty(self):
        tracker = SessionMetricsTracker(journal_path="/tmp/nonexistent_journal.jsonl")
        self.assertEqual(len(tracker.snapshots), 0)

    def test_apf_trend_when_available(self):
        entries = [
            self._make_outcome(1, signal_rate=0.10),
            self._make_outcome(2, signal_rate=0.20),
            self._make_outcome(3, signal_rate=0.30),
            self._make_outcome(4, signal_rate=0.50),
        ]
        self._write_journal(entries)
        tracker = SessionMetricsTracker(journal_path=self.journal_path)
        trend = tracker.apf_trend()
        self.assertEqual(trend.direction, "improving")


class TestMetricsTrend(unittest.TestCase):
    """Test the MetricsTrend data class."""

    def test_to_dict(self):
        trend = MetricsTrend(
            direction="improving",
            slope=0.5,
            recent_avg=3.8,
            values=[3.0, 3.5, 3.8, 4.0],
        )
        d = trend.to_dict()
        self.assertEqual(d["direction"], "improving")
        self.assertAlmostEqual(d["slope"], 0.5)
        self.assertAlmostEqual(d["recent_avg"], 3.8)
        self.assertEqual(len(d["values"]), 4)


if __name__ == "__main__":
    unittest.main()
