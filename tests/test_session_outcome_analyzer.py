"""Tests for session outcome analysis features (Get Smarter pillar).

Tests the pattern detection and recommendation engine that reads
session outcome JSONL and produces actionable insights.
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from session_outcome_tracker import (
    SessionOutcome,
    OutcomeStore,
    analyze_outcomes,
    detect_recurring_blockers,
    detect_task_type_success,
    detect_productivity_trend,
    generate_recommendations,
)


_SENTINEL = object()

def _make_outcome(
    session_id, planned=_SENTINEL, completed=_SENTINEL, blocked=None,
    blockers=None, commits=3, tests_added=10, grade="B+",
):
    return SessionOutcome(
        session_id=session_id,
        planned_tasks=["task1", "task2"] if planned is _SENTINEL else planned,
        completed_tasks=["task1"] if completed is _SENTINEL else completed,
        blocked_tasks=blocked or [],
        blockers=blockers or [],
        commits=commits,
        tests_added=tests_added,
        grade=grade,
    )


class TestDetectRecurringBlockers(unittest.TestCase):
    """Test recurring blocker detection."""

    def test_no_blockers(self):
        outcomes = [_make_outcome(i) for i in range(5)]
        result = detect_recurring_blockers(outcomes)
        self.assertEqual(result, [])

    def test_single_blocker_not_recurring(self):
        outcomes = [_make_outcome(i) for i in range(5)]
        outcomes[2].blockers = ["rate limit"]
        result = detect_recurring_blockers(outcomes)
        self.assertEqual(result, [])

    def test_recurring_blocker_detected(self):
        outcomes = [_make_outcome(i) for i in range(5)]
        outcomes[1].blockers = ["rate limit"]
        outcomes[3].blockers = ["rate limit"]
        result = detect_recurring_blockers(outcomes)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["blocker"], "rate limit")
        self.assertEqual(result[0]["count"], 2)

    def test_multiple_recurring_blockers(self):
        outcomes = [_make_outcome(i) for i in range(6)]
        outcomes[0].blockers = ["rate limit"]
        outcomes[2].blockers = ["rate limit", "gh cli missing"]
        outcomes[4].blockers = ["gh cli missing"]
        result = detect_recurring_blockers(outcomes)
        self.assertEqual(len(result), 2)
        blockers = {r["blocker"] for r in result}
        self.assertIn("rate limit", blockers)
        self.assertIn("gh cli missing", blockers)

    def test_case_insensitive_matching(self):
        outcomes = [_make_outcome(i) for i in range(4)]
        outcomes[0].blockers = ["Rate Limit"]
        outcomes[2].blockers = ["rate limit"]
        result = detect_recurring_blockers(outcomes)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["count"], 2)

    def test_empty_outcomes(self):
        result = detect_recurring_blockers([])
        self.assertEqual(result, [])


class TestDetectTaskTypeSuccess(unittest.TestCase):
    """Test task type (MT prefix) success rate analysis."""

    def test_basic_mt_success_rates(self):
        outcomes = [
            _make_outcome(1, planned=["MT-22 Trial", "MT-10 YoYo"], completed=["MT-22 Trial"]),
            _make_outcome(2, planned=["MT-22 Code tab", "MT-10 Analyze"], completed=["MT-22 Code tab", "MT-10 Analyze"]),
        ]
        result = detect_task_type_success(outcomes)
        # MT-22: 2/2 completed = 100%, MT-10: 1/2 = 50%
        mt22 = next((r for r in result if r["type"] == "MT-22"), None)
        mt10 = next((r for r in result if r["type"] == "MT-10"), None)
        self.assertIsNotNone(mt22)
        self.assertIsNotNone(mt10)
        self.assertAlmostEqual(mt22["success_rate"], 1.0)
        self.assertAlmostEqual(mt10["success_rate"], 0.5)

    def test_non_mt_tasks_grouped(self):
        outcomes = [
            _make_outcome(1, planned=["Fix docs", "Run tests"], completed=["Fix docs"]),
        ]
        result = detect_task_type_success(outcomes)
        other = next((r for r in result if r["type"] == "other"), None)
        self.assertIsNotNone(other)
        self.assertEqual(other["planned"], 2)
        self.assertEqual(other["completed"], 1)

    def test_empty_outcomes(self):
        result = detect_task_type_success([])
        self.assertEqual(result, [])

    def test_no_planned_tasks(self):
        outcomes = [_make_outcome(1, planned=[], completed=[])]
        result = detect_task_type_success(outcomes)
        self.assertEqual(result, [])


class TestDetectProductivityTrend(unittest.TestCase):
    """Test productivity trend detection."""

    def test_upward_trend(self):
        outcomes = [
            _make_outcome(1, commits=2, tests_added=5),
            _make_outcome(2, commits=3, tests_added=10),
            _make_outcome(3, commits=5, tests_added=20),
            _make_outcome(4, commits=7, tests_added=30),
        ]
        result = detect_productivity_trend(outcomes)
        self.assertEqual(result["commits_trend"], "up")
        self.assertEqual(result["tests_trend"], "up")

    def test_downward_trend(self):
        outcomes = [
            _make_outcome(1, commits=7, tests_added=30),
            _make_outcome(2, commits=5, tests_added=20),
            _make_outcome(3, commits=3, tests_added=10),
            _make_outcome(4, commits=2, tests_added=5),
        ]
        result = detect_productivity_trend(outcomes)
        self.assertEqual(result["commits_trend"], "down")
        self.assertEqual(result["tests_trend"], "down")

    def test_stable_trend(self):
        outcomes = [
            _make_outcome(1, commits=3, tests_added=10),
            _make_outcome(2, commits=3, tests_added=10),
            _make_outcome(3, commits=3, tests_added=10),
        ]
        result = detect_productivity_trend(outcomes)
        self.assertEqual(result["commits_trend"], "stable")
        self.assertEqual(result["tests_trend"], "stable")

    def test_insufficient_data(self):
        outcomes = [_make_outcome(1)]
        result = detect_productivity_trend(outcomes)
        self.assertEqual(result["commits_trend"], "insufficient_data")

    def test_empty(self):
        result = detect_productivity_trend([])
        self.assertEqual(result["commits_trend"], "insufficient_data")

    def test_includes_recent_averages(self):
        outcomes = [
            _make_outcome(1, commits=2, tests_added=5),
            _make_outcome(2, commits=4, tests_added=15),
            _make_outcome(3, commits=6, tests_added=25),
        ]
        result = detect_productivity_trend(outcomes)
        self.assertIn("avg_commits_recent", result)
        self.assertIn("avg_tests_recent", result)
        self.assertGreater(result["avg_commits_recent"], 0)


class TestGenerateRecommendations(unittest.TestCase):
    """Test recommendation generation."""

    def test_recommends_fixing_recurring_blockers(self):
        outcomes = [_make_outcome(i) for i in range(4)]
        outcomes[0].blockers = ["rate limit"]
        outcomes[2].blockers = ["rate limit"]
        recs = generate_recommendations(outcomes)
        blocker_recs = [r for r in recs if "rate limit" in r.lower()]
        self.assertTrue(len(blocker_recs) > 0)

    def test_recommends_improving_low_success_types(self):
        outcomes = [
            _make_outcome(1, planned=["MT-22 Trial"], completed=[]),
            _make_outcome(2, planned=["MT-22 Trial2"], completed=[]),
            _make_outcome(3, planned=["MT-22 Trial3"], completed=[]),
        ]
        recs = generate_recommendations(outcomes)
        mt22_recs = [r for r in recs if "MT-22" in r]
        self.assertTrue(len(mt22_recs) > 0)

    def test_no_recommendations_for_healthy_sessions(self):
        outcomes = [
            _make_outcome(i, planned=["task"], completed=["task"],
                         commits=5, tests_added=20, grade="A+")
            for i in range(5)
        ]
        recs = generate_recommendations(outcomes)
        # May still have positive recommendations but no warnings
        warning_recs = [r for r in recs if "warning" in r.lower() or "fix" in r.lower()]
        self.assertEqual(len(warning_recs), 0)

    def test_empty_outcomes_no_crash(self):
        recs = generate_recommendations([])
        self.assertIsInstance(recs, list)

    def test_declining_productivity_recommendation(self):
        outcomes = [
            _make_outcome(1, commits=7, tests_added=30),
            _make_outcome(2, commits=5, tests_added=20),
            _make_outcome(3, commits=3, tests_added=10),
            _make_outcome(4, commits=1, tests_added=2),
        ]
        recs = generate_recommendations(outcomes)
        decline_recs = [r for r in recs if "declin" in r.lower() or "down" in r.lower()]
        self.assertTrue(len(decline_recs) > 0)


class TestAnalyzeOutcomes(unittest.TestCase):
    """Test the top-level analyze_outcomes function."""

    def test_returns_all_sections(self):
        outcomes = [_make_outcome(i) for i in range(3)]
        result = analyze_outcomes(outcomes)
        self.assertIn("recurring_blockers", result)
        self.assertIn("task_type_success", result)
        self.assertIn("productivity_trend", result)
        self.assertIn("recommendations", result)

    def test_empty_outcomes(self):
        result = analyze_outcomes([])
        self.assertIn("recurring_blockers", result)
        self.assertEqual(result["recurring_blockers"], [])

    def test_serializable(self):
        outcomes = [_make_outcome(i) for i in range(3)]
        result = analyze_outcomes(outcomes)
        # Must be JSON-serializable for injection into session context
        serialized = json.dumps(result)
        self.assertIsInstance(serialized, str)

    def test_with_store(self):
        """Test analyze via OutcomeStore."""
        with tempfile.TemporaryDirectory() as tmp:
            store_path = os.path.join(tmp, "test_outcomes.jsonl")
            store = OutcomeStore(store_path)
            for i in range(3):
                store.append(_make_outcome(i))
            outcomes = store.load_all()
            result = analyze_outcomes(outcomes)
            self.assertEqual(result["productivity_trend"]["session_count"], 3)


class TestGradeDistributionAnalysis(unittest.TestCase):
    """Test grade distribution in analysis."""

    def test_grade_trend_included(self):
        outcomes = [
            _make_outcome(1, grade="C"),
            _make_outcome(2, grade="B"),
            _make_outcome(3, grade="B+"),
            _make_outcome(4, grade="A"),
        ]
        result = analyze_outcomes(outcomes)
        trend = result["productivity_trend"]
        self.assertIn("grade_trend", trend)

    def test_improving_grades_detected(self):
        outcomes = [
            _make_outcome(1, grade="C"),
            _make_outcome(2, grade="B"),
            _make_outcome(3, grade="A"),
        ]
        result = analyze_outcomes(outcomes)
        self.assertEqual(result["productivity_trend"]["grade_trend"], "improving")

    def test_declining_grades_detected(self):
        outcomes = [
            _make_outcome(1, grade="A+"),
            _make_outcome(2, grade="B"),
            _make_outcome(3, grade="C"),
        ]
        result = analyze_outcomes(outcomes)
        self.assertEqual(result["productivity_trend"]["grade_trend"], "declining")


if __name__ == "__main__":
    unittest.main()
