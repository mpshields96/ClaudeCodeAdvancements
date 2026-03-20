#!/usr/bin/env python3
"""
test_wrap_tracker.py — Tests for session wrap assessment persistence.

S89: Persist wrap assessments to file (item 3 from SESSION_STATE Next list).

Run: python3 tests/test_wrap_tracker.py
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestWrapStorage(unittest.TestCase):
    """Test wrap assessment persistence (JSONL file)."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.path = self.tmp.name

    def tearDown(self):
        if os.path.exists(self.path):
            os.unlink(self.path)

    def test_log_assessment(self):
        from wrap_tracker import log_assessment
        entry = log_assessment(
            session=89,
            grade="A",
            wins=["Built 117 deep hivemind tests", "Fixed _make_id collision bug"],
            losses=["None significant"],
            next_different="Wire tip tracker into /cca-wrap",
            test_count=3475,
            test_suites=84,
            commits=5,
            path=self.path,
        )
        self.assertEqual(entry["session"], 89)
        self.assertEqual(entry["grade"], "A")
        self.assertEqual(len(entry["wins"]), 2)
        self.assertEqual(len(entry["losses"]), 1)
        self.assertIn("timestamp", entry)

    def test_assessment_persists_to_file(self):
        from wrap_tracker import log_assessment, load_assessments
        log_assessment(session=89, grade="B", wins=["X"], losses=["Y"],
                      test_count=100, path=self.path)
        assessments = load_assessments(self.path)
        self.assertEqual(len(assessments), 1)
        self.assertEqual(assessments[0]["session"], 89)

    def test_multiple_assessments_appended(self):
        from wrap_tracker import log_assessment, load_assessments
        log_assessment(session=87, grade="A", wins=["W1"], losses=[], test_count=3200, path=self.path)
        log_assessment(session=88, grade="B", wins=["W2"], losses=["L1"], test_count=3300, path=self.path)
        log_assessment(session=89, grade="A", wins=["W3"], losses=[], test_count=3475, path=self.path)
        assessments = load_assessments(self.path)
        self.assertEqual(len(assessments), 3)

    def test_load_empty_file(self):
        from wrap_tracker import load_assessments
        assessments = load_assessments(self.path)
        self.assertEqual(assessments, [])

    def test_load_nonexistent_file(self):
        from wrap_tracker import load_assessments
        assessments = load_assessments("/nonexistent/wraps.jsonl")
        self.assertEqual(assessments, [])

    def test_load_skips_malformed_lines(self):
        from wrap_tracker import load_assessments
        with open(self.path, "w") as f:
            f.write('{"session": 1, "grade": "A"}\n')
            f.write("not json\n")
            f.write('{"session": 2, "grade": "B"}\n')
        assessments = load_assessments(self.path)
        self.assertEqual(len(assessments), 2)

    def test_assessment_has_timestamp(self):
        from wrap_tracker import log_assessment
        entry = log_assessment(session=89, grade="A", wins=["X"], losses=[],
                              test_count=100, path=self.path)
        self.assertIn("T", entry["timestamp"])

    def test_optional_fields(self):
        from wrap_tracker import log_assessment
        entry = log_assessment(session=89, grade="A", wins=["X"], losses=[],
                              test_count=100, path=self.path)
        # next_different and commits are optional
        self.assertNotIn("next_different", entry)
        self.assertNotIn("commits", entry)
        self.assertNotIn("test_suites", entry)


class TestGradeValidation(unittest.TestCase):
    """Test grade validation."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.path = self.tmp.name

    def tearDown(self):
        if os.path.exists(self.path):
            os.unlink(self.path)

    def test_valid_grades(self):
        from wrap_tracker import log_assessment
        for grade in ["A", "A-", "B+", "B", "B-", "C", "D"]:
            log_assessment(session=1, grade=grade, wins=["X"], losses=[],
                          test_count=100, path=self.path)

    def test_invalid_grade_raises(self):
        from wrap_tracker import log_assessment
        with self.assertRaises(ValueError):
            log_assessment(session=1, grade="E", wins=["X"], losses=[],
                          test_count=100, path=self.path)

    def test_invalid_grade_f_raises(self):
        from wrap_tracker import log_assessment
        with self.assertRaises(ValueError):
            log_assessment(session=1, grade="F", wins=["X"], losses=[],
                          test_count=100, path=self.path)


class TestWrapAnalytics(unittest.TestCase):
    """Test wrap analytics / trend functions."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.path = self.tmp.name

    def tearDown(self):
        if os.path.exists(self.path):
            os.unlink(self.path)

    def test_get_stats_empty(self):
        from wrap_tracker import get_stats
        stats = get_stats(self.path)
        self.assertEqual(stats["total_sessions"], 0)

    def test_get_stats_basic(self):
        from wrap_tracker import log_assessment, get_stats
        log_assessment(session=87, grade="A", wins=["W"], losses=[], test_count=3200, path=self.path)
        log_assessment(session=88, grade="B", wins=["W"], losses=["L"], test_count=3300, path=self.path)
        log_assessment(session=89, grade="A", wins=["W"], losses=[], test_count=3475, path=self.path)
        stats = get_stats(self.path)
        self.assertEqual(stats["total_sessions"], 3)
        self.assertEqual(stats["grade_distribution"]["A"], 2)
        self.assertEqual(stats["grade_distribution"]["B"], 1)
        self.assertEqual(stats["latest_test_count"], 3475)

    def test_get_trend(self):
        from wrap_tracker import log_assessment, get_trend
        log_assessment(session=85, grade="C", wins=["W"], losses=["L"], test_count=3000, path=self.path)
        log_assessment(session=86, grade="B", wins=["W"], losses=["L"], test_count=3100, path=self.path)
        log_assessment(session=87, grade="A", wins=["W"], losses=[], test_count=3200, path=self.path)
        trend = get_trend(self.path)
        self.assertEqual(trend["direction"], "improving")
        self.assertEqual(len(trend["recent_grades"]), 3)

    def test_get_trend_declining(self):
        from wrap_tracker import log_assessment, get_trend
        log_assessment(session=85, grade="A", wins=["W"], losses=[], test_count=3000, path=self.path)
        log_assessment(session=86, grade="B", wins=["W"], losses=["L"], test_count=3100, path=self.path)
        log_assessment(session=87, grade="C", wins=["W"], losses=["L", "L2"], test_count=3100, path=self.path)
        trend = get_trend(self.path)
        self.assertEqual(trend["direction"], "declining")

    def test_get_trend_stable(self):
        from wrap_tracker import log_assessment, get_trend
        log_assessment(session=85, grade="B", wins=["W"], losses=["L"], test_count=3000, path=self.path)
        log_assessment(session=86, grade="B", wins=["W"], losses=["L"], test_count=3100, path=self.path)
        log_assessment(session=87, grade="B", wins=["W"], losses=["L"], test_count=3200, path=self.path)
        trend = get_trend(self.path)
        self.assertEqual(trend["direction"], "stable")

    def test_get_trend_empty(self):
        from wrap_tracker import get_trend
        trend = get_trend(self.path)
        self.assertEqual(trend["direction"], "unknown")

    def test_test_count_growth(self):
        from wrap_tracker import log_assessment, get_stats
        log_assessment(session=85, grade="B", wins=["W"], losses=[], test_count=3000, path=self.path)
        log_assessment(session=89, grade="A", wins=["W"], losses=[], test_count=3475, path=self.path)
        stats = get_stats(self.path)
        self.assertEqual(stats["test_count_growth"], 475)

    def test_format_for_init(self):
        from wrap_tracker import log_assessment, format_for_init
        log_assessment(session=87, grade="A", wins=["Built tests"], losses=[], test_count=3200, path=self.path)
        log_assessment(session=88, grade="B", wins=["Fixed bugs"], losses=["Slow debugging"], test_count=3300, path=self.path)
        output = format_for_init(self.path)
        self.assertIn("Last 2 sessions", output)
        self.assertIn("S87: A", output)
        self.assertIn("S88: B", output)

    def test_format_for_init_empty(self):
        from wrap_tracker import format_for_init
        output = format_for_init(self.path)
        self.assertEqual(output, "")

    def test_get_by_session(self):
        from wrap_tracker import log_assessment, get_by_session
        log_assessment(session=87, grade="A", wins=["W"], losses=[], test_count=3200, path=self.path)
        log_assessment(session=88, grade="B", wins=["W"], losses=["L"], test_count=3300, path=self.path)
        entry = get_by_session(88, self.path)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["grade"], "B")

    def test_get_by_session_not_found(self):
        from wrap_tracker import get_by_session
        entry = get_by_session(999, self.path)
        self.assertIsNone(entry)


class TestWrapCLI(unittest.TestCase):
    """Test CLI interface."""

    def test_cli_help(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, "wrap_tracker.py"],
            capture_output=True, text=True,
            cwd=str(Path(__file__).parent.parent),
        )
        self.assertIn("wrap_tracker.py", result.stdout)


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
