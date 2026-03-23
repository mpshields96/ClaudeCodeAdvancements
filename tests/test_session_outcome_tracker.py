#!/usr/bin/env python3
"""Tests for session_outcome_tracker.py — prompt-to-outcome tracking per session."""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from session_outcome_tracker import (
    SessionOutcome,
    OutcomeStore,
    parse_session_state_planned,
    parse_session_state_completed,
    compute_completion_rate,
    compute_session_grade,
    trend_report,
)


class TestSessionOutcome(unittest.TestCase):
    """Test the SessionOutcome data class."""

    def test_create_minimal(self):
        outcome = SessionOutcome(session_id=133)
        self.assertEqual(outcome.session_id, 133)
        self.assertEqual(outcome.planned_tasks, [])
        self.assertEqual(outcome.completed_tasks, [])
        self.assertEqual(outcome.commits, 0)
        self.assertEqual(outcome.tests_added, 0)
        self.assertIsNone(outcome.grade)

    def test_create_full(self):
        outcome = SessionOutcome(
            session_id=133,
            chat_type="solo",
            planned_tasks=["Fix bug", "Build feature"],
            completed_tasks=["Fix bug"],
            blocked_tasks=["Build feature"],
            blockers=["Needs Matthew present"],
            commits=3,
            tests_added=15,
            tests_total=8363,
            grade="B+",
            duration_minutes=45,
        )
        self.assertEqual(outcome.chat_type, "solo")
        self.assertEqual(len(outcome.planned_tasks), 2)
        self.assertEqual(len(outcome.completed_tasks), 1)
        self.assertEqual(outcome.blockers, ["Needs Matthew present"])
        self.assertEqual(outcome.duration_minutes, 45)

    def test_to_dict(self):
        outcome = SessionOutcome(session_id=100, commits=5)
        d = outcome.to_dict()
        self.assertEqual(d["session_id"], 100)
        self.assertEqual(d["commits"], 5)
        self.assertIn("timestamp", d)

    def test_from_dict(self):
        d = {
            "session_id": 50,
            "chat_type": "worker",
            "planned_tasks": ["A", "B"],
            "completed_tasks": ["A"],
            "blocked_tasks": ["B"],
            "blockers": ["dependency"],
            "commits": 2,
            "tests_added": 10,
            "tests_total": 5000,
            "grade": "A",
            "duration_minutes": 60,
            "timestamp": "2026-03-23T12:00:00+00:00",
        }
        outcome = SessionOutcome.from_dict(d)
        self.assertEqual(outcome.session_id, 50)
        self.assertEqual(outcome.chat_type, "worker")
        self.assertEqual(outcome.planned_tasks, ["A", "B"])
        self.assertEqual(outcome.grade, "A")

    def test_from_dict_missing_fields(self):
        """Gracefully handle missing optional fields."""
        d = {"session_id": 1}
        outcome = SessionOutcome.from_dict(d)
        self.assertEqual(outcome.session_id, 1)
        self.assertEqual(outcome.planned_tasks, [])
        self.assertEqual(outcome.commits, 0)
        self.assertIsNone(outcome.grade)

    def test_roundtrip(self):
        outcome = SessionOutcome(
            session_id=99,
            planned_tasks=["X"],
            completed_tasks=["X"],
            commits=1,
            tests_added=5,
            grade="A",
        )
        d = outcome.to_dict()
        restored = SessionOutcome.from_dict(d)
        self.assertEqual(restored.session_id, 99)
        self.assertEqual(restored.planned_tasks, ["X"])
        self.assertEqual(restored.grade, "A")


class TestOutcomeStore(unittest.TestCase):
    """Test JSONL persistence."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store_path = os.path.join(self.tmpdir, "outcomes.jsonl")

    def tearDown(self):
        if os.path.exists(self.store_path):
            os.unlink(self.store_path)
        os.rmdir(self.tmpdir)

    def test_append_creates_file(self):
        store = OutcomeStore(self.store_path)
        outcome = SessionOutcome(session_id=1, commits=2)
        store.append(outcome)
        self.assertTrue(os.path.exists(self.store_path))

    def test_append_and_load(self):
        store = OutcomeStore(self.store_path)
        store.append(SessionOutcome(session_id=1, commits=2))
        store.append(SessionOutcome(session_id=2, commits=5))
        outcomes = store.load_all()
        self.assertEqual(len(outcomes), 2)
        self.assertEqual(outcomes[0].session_id, 1)
        self.assertEqual(outcomes[1].session_id, 2)

    def test_load_empty(self):
        store = OutcomeStore(self.store_path)
        outcomes = store.load_all()
        self.assertEqual(outcomes, [])

    def test_load_corrupted_line_skipped(self):
        """Corrupt lines are skipped, valid lines still loaded."""
        with open(self.store_path, "w") as f:
            f.write('{"session_id": 1, "commits": 3}\n')
            f.write("NOT JSON\n")
            f.write('{"session_id": 2, "commits": 7}\n')
        store = OutcomeStore(self.store_path)
        outcomes = store.load_all()
        self.assertEqual(len(outcomes), 2)

    def test_load_last_n(self):
        store = OutcomeStore(self.store_path)
        for i in range(10):
            store.append(SessionOutcome(session_id=i, commits=i))
        last3 = store.load_last(3)
        self.assertEqual(len(last3), 3)
        self.assertEqual(last3[0].session_id, 7)
        self.assertEqual(last3[2].session_id, 9)

    def test_load_last_more_than_available(self):
        store = OutcomeStore(self.store_path)
        store.append(SessionOutcome(session_id=1))
        last5 = store.load_last(5)
        self.assertEqual(len(last5), 1)

    def test_get_by_session_id(self):
        store = OutcomeStore(self.store_path)
        store.append(SessionOutcome(session_id=10, grade="A"))
        store.append(SessionOutcome(session_id=11, grade="B"))
        result = store.get_by_session_id(10)
        self.assertIsNotNone(result)
        self.assertEqual(result.grade, "A")

    def test_get_by_session_id_not_found(self):
        store = OutcomeStore(self.store_path)
        store.append(SessionOutcome(session_id=1))
        result = store.get_by_session_id(999)
        self.assertIsNone(result)

    def test_dedup_on_session_id(self):
        """If same session_id appended twice, load_all returns both but get_by returns last."""
        store = OutcomeStore(self.store_path)
        store.append(SessionOutcome(session_id=5, grade="B"))
        store.append(SessionOutcome(session_id=5, grade="A"))
        result = store.get_by_session_id(5)
        self.assertEqual(result.grade, "A")  # last wins


class TestParseSessionState(unittest.TestCase):
    """Test parsing SESSION_STATE.md for planned/completed tasks."""

    def test_parse_planned_tasks(self):
        content = """## Current State (as of Session 132 — 2026-03-23)

**Next (prioritized):**
1. **MT-22 SUPERVISED TRIAL**: Run something
2. **MT-22 enhancements**: Explore stuff
3. **CI/CD pipeline verify**: Matthew S130 directive.
"""
        tasks = parse_session_state_planned(content)
        self.assertEqual(len(tasks), 3)
        self.assertIn("MT-22 SUPERVISED TRIAL", tasks[0])
        self.assertIn("CI/CD pipeline verify", tasks[2])

    def test_parse_completed_tasks(self):
        content = """## Current State (as of Session 132 — 2026-03-23)

**What was done this session (S132):**
- **MT-22 Phase 1 COMPLETE**: desktop_automator.py built
- **MT-22 Phase 2 COMPLETE**: desktop_autoloop.py built
- **MT-22 Phase 3 COMPLETE**: launcher + setup guide
- **MT-27 Phase 4 COMPLETE**: 3-tier NEEDLE precision
"""
        tasks = parse_session_state_completed(content)
        self.assertEqual(len(tasks), 4)
        self.assertIn("MT-22 Phase 1 COMPLETE", tasks[0])

    def test_parse_planned_empty(self):
        content = "No prioritized section here."
        tasks = parse_session_state_planned(content)
        self.assertEqual(tasks, [])

    def test_parse_completed_empty(self):
        content = "No done section here."
        tasks = parse_session_state_completed(content)
        self.assertEqual(tasks, [])


class TestCompletionRate(unittest.TestCase):
    """Test completion rate calculation."""

    def test_perfect_completion(self):
        rate = compute_completion_rate(["A", "B", "C"], ["A", "B", "C"])
        self.assertAlmostEqual(rate, 1.0)

    def test_partial_completion(self):
        rate = compute_completion_rate(["A", "B", "C", "D"], ["A", "B"])
        self.assertAlmostEqual(rate, 0.5)

    def test_zero_planned(self):
        rate = compute_completion_rate([], ["A"])
        self.assertAlmostEqual(rate, 1.0)  # nothing planned = 100% (no gap)

    def test_zero_completed(self):
        rate = compute_completion_rate(["A", "B"], [])
        self.assertAlmostEqual(rate, 0.0)

    def test_overcomplete(self):
        """Completed more than planned (bonus tasks)."""
        rate = compute_completion_rate(["A"], ["A", "B", "C"])
        self.assertAlmostEqual(rate, 1.0)  # capped at 100%


class TestSessionGrade(unittest.TestCase):
    """Test grade computation from outcome metrics."""

    def test_grade_a_plus(self):
        grade = compute_session_grade(
            completion_rate=1.0, commits=8, tests_added=50
        )
        self.assertEqual(grade, "A+")

    def test_grade_a(self):
        # 0.75*40=30 + 5/5*30=30 + 20/30*30=20 = 80 => A
        grade = compute_session_grade(
            completion_rate=0.75, commits=5, tests_added=20
        )
        self.assertEqual(grade, "A")

    def test_grade_b(self):
        grade = compute_session_grade(
            completion_rate=0.6, commits=3, tests_added=15
        )
        self.assertEqual(grade, "B")

    def test_grade_c(self):
        grade = compute_session_grade(
            completion_rate=0.5, commits=2, tests_added=10
        )
        self.assertEqual(grade, "C")

    def test_grade_d(self):
        grade = compute_session_grade(
            completion_rate=0.0, commits=0, tests_added=0
        )
        self.assertEqual(grade, "D")

    def test_grade_no_tests_but_high_completion(self):
        """High completion with no tests still decent (doc-only sessions)."""
        grade = compute_session_grade(
            completion_rate=1.0, commits=5, tests_added=0
        )
        # Should still be decent but not A+ (tests matter)
        self.assertIn(grade, ["A", "B+", "B"])


class TestTrendReport(unittest.TestCase):
    """Test trend analysis across sessions."""

    def test_trend_with_data(self):
        outcomes = [
            SessionOutcome(session_id=1, commits=3, tests_added=10, grade="B"),
            SessionOutcome(session_id=2, commits=5, tests_added=20, grade="A"),
            SessionOutcome(session_id=3, commits=4, tests_added=15, grade="B+"),
        ]
        report = trend_report(outcomes)
        self.assertIn("avg_commits", report)
        self.assertIn("avg_tests_added", report)
        self.assertIn("total_sessions", report)
        self.assertEqual(report["total_sessions"], 3)
        self.assertAlmostEqual(report["avg_commits"], 4.0)
        self.assertAlmostEqual(report["avg_tests_added"], 15.0)

    def test_trend_empty(self):
        report = trend_report([])
        self.assertEqual(report["total_sessions"], 0)
        self.assertEqual(report["avg_commits"], 0)

    def test_trend_grade_distribution(self):
        outcomes = [
            SessionOutcome(session_id=1, grade="A"),
            SessionOutcome(session_id=2, grade="A"),
            SessionOutcome(session_id=3, grade="B"),
        ]
        report = trend_report(outcomes)
        self.assertEqual(report["grade_distribution"]["A"], 2)
        self.assertEqual(report["grade_distribution"]["B"], 1)

    def test_trend_completion_rate_avg(self):
        outcomes = [
            SessionOutcome(
                session_id=1,
                planned_tasks=["A", "B"],
                completed_tasks=["A", "B"],
            ),
            SessionOutcome(
                session_id=2,
                planned_tasks=["A", "B"],
                completed_tasks=["A"],
            ),
        ]
        report = trend_report(outcomes)
        self.assertAlmostEqual(report["avg_completion_rate"], 0.75)


if __name__ == "__main__":
    unittest.main()
