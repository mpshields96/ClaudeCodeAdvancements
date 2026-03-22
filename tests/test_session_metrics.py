#!/usr/bin/env python3
"""Tests for session_metrics.py — cross-session analytics."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from session_metrics import (
    ProjectSummary,
    SessionDetail,
    GrowthMetrics,
    StreakInfo,
    _load_jsonl,
    _grade_to_letter,
    load_wraps,
    load_tips,
    load_apf,
    get_summary,
    get_session_detail,
    get_growth,
    get_streaks,
    format_summary,
    format_session,
    format_growth,
    format_streaks,
)


def _write_jsonl(entries: list) -> Path:
    """Write entries to a temp JSONL file."""
    f = tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False)
    for e in entries:
        f.write(json.dumps(e) + '\n')
    f.close()
    return Path(f.name)


SAMPLE_WRAPS = [
    {"session": 82, "grade": "B", "wins": ["Fix1"], "losses": ["Loss1"], "test_count": 3248, "timestamp": "2026-03-20T21:58:43Z"},
    {"session": 83, "grade": "A", "wins": ["MT-20", "MT-11"], "losses": ["None"], "test_count": 3277, "timestamp": "2026-03-20T22:00:00Z"},
    {"session": 84, "grade": "B", "wins": ["MT-14"], "losses": ["Drift"], "test_count": 3293, "timestamp": "2026-03-20T22:10:00Z"},
    {"session": 85, "grade": "A", "wins": ["Charts"], "losses": [], "test_count": 3400, "timestamp": "2026-03-20T23:00:00Z"},
    {"session": 86, "grade": "A", "wins": ["Hivemind"], "losses": [], "test_count": 3500, "timestamp": "2026-03-21T00:00:00Z"},
]

SAMPLE_TIPS = [
    {"id": "tip1", "text": "Tip one", "source": "desktop", "session": "S83", "status": "implemented"},
    {"id": "tip2", "text": "Tip two", "source": "desktop", "session": "S84", "status": "pending"},
    {"id": "tip3", "text": "Tip three", "source": "cli1", "session": "S85", "status": "implemented"},
]

SAMPLE_APF = [
    {"session": "S83", "apf_percent": 22.7, "timestamp": "2026-03-20T22:00:00Z"},
    {"session": "S84", "apf_percent": 24.1, "timestamp": "2026-03-20T22:10:00Z"},
]


class TestLoadJsonl(unittest.TestCase):
    """Test JSONL loading."""

    def test_load_valid(self):
        path = _write_jsonl([{"a": 1}, {"b": 2}])
        self.addCleanup(lambda: os.unlink(path))
        result = _load_jsonl(path)
        self.assertEqual(len(result), 2)

    def test_load_missing_file(self):
        result = _load_jsonl(Path("/nonexistent/file.jsonl"))
        self.assertEqual(result, [])

    def test_load_with_bad_lines(self):
        f = tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False)
        f.write('{"good": 1}\n')
        f.write('bad line\n')
        f.write('{"also_good": 2}\n')
        f.close()
        self.addCleanup(lambda: os.unlink(f.name))
        result = _load_jsonl(Path(f.name))
        self.assertEqual(len(result), 2)

    def test_load_empty_file(self):
        f = tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False)
        f.write('')
        f.close()
        self.addCleanup(lambda: os.unlink(f.name))
        result = _load_jsonl(Path(f.name))
        self.assertEqual(result, [])

    def test_load_blank_lines(self):
        f = tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False)
        f.write('{"a": 1}\n\n\n{"b": 2}\n')
        f.close()
        self.addCleanup(lambda: os.unlink(f.name))
        result = _load_jsonl(Path(f.name))
        self.assertEqual(len(result), 2)


class TestGradeToLetter(unittest.TestCase):
    """Test grade value to letter conversion."""

    def test_a(self):
        self.assertEqual(_grade_to_letter(4.0), "A")

    def test_a_minus(self):
        self.assertEqual(_grade_to_letter(3.7), "A-")

    def test_b_plus(self):
        self.assertEqual(_grade_to_letter(3.3), "B+")

    def test_b(self):
        self.assertEqual(_grade_to_letter(3.0), "B")

    def test_c(self):
        self.assertEqual(_grade_to_letter(2.0), "C")

    def test_d_minus(self):
        self.assertEqual(_grade_to_letter(0.5), "D-")


class TestGetSummary(unittest.TestCase):
    """Test project summary computation."""

    def setUp(self):
        self.wrap_path = _write_jsonl(SAMPLE_WRAPS)
        self.tips_path = _write_jsonl(SAMPLE_TIPS)
        self.apf_path = _write_jsonl(SAMPLE_APF)
        self.addCleanup(lambda: os.unlink(self.wrap_path))
        self.addCleanup(lambda: os.unlink(self.tips_path))
        self.addCleanup(lambda: os.unlink(self.apf_path))

    def test_total_sessions(self):
        s = get_summary(self.wrap_path, self.tips_path, self.apf_path)
        self.assertEqual(s.total_sessions, 5)

    def test_total_tests(self):
        s = get_summary(self.wrap_path, self.tips_path, self.apf_path)
        self.assertEqual(s.total_tests, 3500)

    def test_test_growth(self):
        s = get_summary(self.wrap_path, self.tips_path, self.apf_path)
        self.assertEqual(s.test_growth, 252)  # 3500 - 3248

    def test_avg_grade(self):
        s = get_summary(self.wrap_path, self.tips_path, self.apf_path)
        # B=3.0, A=4.0, B=3.0, A=4.0, A=4.0 -> avg=3.6
        self.assertAlmostEqual(s.avg_grade, 3.6, places=1)

    def test_grade_distribution(self):
        s = get_summary(self.wrap_path, self.tips_path, self.apf_path)
        self.assertEqual(s.grade_distribution["A"], 3)
        self.assertEqual(s.grade_distribution["B"], 2)

    def test_total_tips(self):
        s = get_summary(self.wrap_path, self.tips_path, self.apf_path)
        self.assertEqual(s.total_tips, 3)

    def test_implemented_tips(self):
        s = get_summary(self.wrap_path, self.tips_path, self.apf_path)
        self.assertEqual(s.implemented_tips, 2)

    def test_latest_apf(self):
        s = get_summary(self.wrap_path, self.tips_path, self.apf_path)
        self.assertAlmostEqual(s.latest_apf, 24.1)

    def test_session_range(self):
        s = get_summary(self.wrap_path, self.tips_path, self.apf_path)
        self.assertEqual(s.session_range, "S82-S86")

    def test_empty_data(self):
        empty = _write_jsonl([])
        self.addCleanup(lambda: os.unlink(empty))
        s = get_summary(empty, empty, empty)
        self.assertEqual(s.total_sessions, 0)
        self.assertEqual(s.total_tests, 0)

    def test_to_dict(self):
        s = get_summary(self.wrap_path, self.tips_path, self.apf_path)
        d = s.to_dict()
        self.assertIn("total_sessions", d)
        self.assertIn("avg_grade_letter", d)
        self.assertEqual(d["total_sessions"], 5)


class TestGetSessionDetail(unittest.TestCase):
    """Test single session detail retrieval."""

    def setUp(self):
        self.wrap_path = _write_jsonl(SAMPLE_WRAPS)
        self.tips_path = _write_jsonl(SAMPLE_TIPS)
        self.addCleanup(lambda: os.unlink(self.wrap_path))
        self.addCleanup(lambda: os.unlink(self.tips_path))

    def test_found_session(self):
        d = get_session_detail(83, self.wrap_path, self.tips_path)
        self.assertIsNotNone(d)
        self.assertEqual(d.grade, "A")
        self.assertEqual(d.test_count, 3277)

    def test_test_delta(self):
        d = get_session_detail(83, self.wrap_path, self.tips_path)
        self.assertEqual(d.test_delta, 29)  # 3277 - 3248

    def test_first_session_no_delta(self):
        d = get_session_detail(82, self.wrap_path, self.tips_path)
        self.assertEqual(d.test_delta, 0)  # no previous

    def test_tips_count(self):
        d = get_session_detail(83, self.wrap_path, self.tips_path)
        self.assertEqual(d.tips_generated, 1)

    def test_missing_session(self):
        d = get_session_detail(999, self.wrap_path, self.tips_path)
        self.assertIsNone(d)

    def test_wins_and_losses(self):
        d = get_session_detail(83, self.wrap_path, self.tips_path)
        self.assertEqual(d.wins, ["MT-20", "MT-11"])

    def test_to_dict(self):
        d = get_session_detail(83, self.wrap_path, self.tips_path)
        result = d.to_dict()
        self.assertEqual(result["session_number"], 83)
        self.assertIn("wins", result)


class TestGetGrowth(unittest.TestCase):
    """Test growth trajectory computation."""

    def setUp(self):
        self.wrap_path = _write_jsonl(SAMPLE_WRAPS)
        self.addCleanup(lambda: os.unlink(self.wrap_path))

    def test_total_growth(self):
        g = get_growth(self.wrap_path)
        self.assertEqual(g.total_growth, 252)

    def test_data_points(self):
        g = get_growth(self.wrap_path)
        self.assertEqual(len(g.data_points), 5)
        self.assertEqual(g.data_points[0], (82, 3248))

    def test_avg_growth(self):
        g = get_growth(self.wrap_path)
        self.assertAlmostEqual(g.avg_growth_per_session, 63.0)  # 252/4

    def test_peak(self):
        g = get_growth(self.wrap_path)
        self.assertEqual(g.peak_session, 86)
        self.assertEqual(g.peak_tests, 3500)

    def test_empty_data(self):
        empty = _write_jsonl([])
        self.addCleanup(lambda: os.unlink(empty))
        g = get_growth(empty)
        self.assertEqual(g.total_growth, 0)
        self.assertEqual(g.data_points, [])

    def test_single_session(self):
        path = _write_jsonl([SAMPLE_WRAPS[0]])
        self.addCleanup(lambda: os.unlink(path))
        g = get_growth(path)
        self.assertEqual(g.total_growth, 0)
        self.assertEqual(len(g.data_points), 1)

    def test_to_dict(self):
        g = get_growth(self.wrap_path)
        d = g.to_dict()
        self.assertIn("total_growth", d)
        self.assertIn("data_points", d)


class TestGetStreaks(unittest.TestCase):
    """Test streak analysis."""

    def test_current_streak(self):
        path = _write_jsonl(SAMPLE_WRAPS)
        self.addCleanup(lambda: os.unlink(path))
        s = get_streaks(path)
        self.assertEqual(s.current_streak_grade, "A")
        self.assertEqual(s.current_streak_length, 2)  # S85=A, S86=A

    def test_longest_a_streak(self):
        path = _write_jsonl(SAMPLE_WRAPS)
        self.addCleanup(lambda: os.unlink(path))
        s = get_streaks(path)
        self.assertEqual(s.longest_a_streak, 2)

    def test_all_a_streak(self):
        wraps = [
            {"session": i, "grade": "A", "test_count": 100 * i}
            for i in range(1, 6)
        ]
        path = _write_jsonl(wraps)
        self.addCleanup(lambda: os.unlink(path))
        s = get_streaks(path)
        self.assertEqual(s.longest_a_streak, 5)
        self.assertEqual(s.current_streak_length, 5)

    def test_improving_trend(self):
        wraps = [
            {"session": 1, "grade": "C", "test_count": 100},
            {"session": 2, "grade": "C", "test_count": 200},
            {"session": 3, "grade": "B", "test_count": 300},
            {"session": 4, "grade": "A", "test_count": 400},
            {"session": 5, "grade": "A", "test_count": 500},
        ]
        path = _write_jsonl(wraps)
        self.addCleanup(lambda: os.unlink(path))
        s = get_streaks(path)
        self.assertEqual(s.recent_trend, "improving")

    def test_declining_trend(self):
        wraps = [
            {"session": 1, "grade": "A", "test_count": 500},
            {"session": 2, "grade": "A", "test_count": 400},
            {"session": 3, "grade": "B", "test_count": 300},
            {"session": 4, "grade": "C", "test_count": 200},
            {"session": 5, "grade": "C", "test_count": 100},
        ]
        path = _write_jsonl(wraps)
        self.addCleanup(lambda: os.unlink(path))
        s = get_streaks(path)
        self.assertEqual(s.recent_trend, "declining")

    def test_stable_trend(self):
        wraps = [
            {"session": i, "grade": "B", "test_count": 100 * i}
            for i in range(1, 6)
        ]
        path = _write_jsonl(wraps)
        self.addCleanup(lambda: os.unlink(path))
        s = get_streaks(path)
        self.assertEqual(s.recent_trend, "stable")

    def test_empty_data(self):
        empty = _write_jsonl([])
        self.addCleanup(lambda: os.unlink(empty))
        s = get_streaks(empty)
        self.assertEqual(s.current_streak_length, 0)
        self.assertEqual(s.recent_trend, "unknown")

    def test_sessions_since_decline(self):
        path = _write_jsonl(SAMPLE_WRAPS)
        self.addCleanup(lambda: os.unlink(path))
        s = get_streaks(path)
        # S83=A->S84=B is a decline, then S85=A, S86=A = 2 sessions since
        self.assertEqual(s.sessions_since_last_decline, 2)

    def test_to_dict(self):
        path = _write_jsonl(SAMPLE_WRAPS)
        self.addCleanup(lambda: os.unlink(path))
        s = get_streaks(path)
        d = s.to_dict()
        self.assertIn("current_streak_grade", d)
        self.assertIn("recent_trend", d)


class TestFormatting(unittest.TestCase):
    """Test human-readable formatting."""

    def test_format_summary(self):
        s = ProjectSummary(
            total_sessions=5, total_tests=3500, test_growth=252,
            avg_grade=3.6, avg_grade_letter="A-",
            grade_distribution={"A": 3, "B": 2},
            total_tips=3, implemented_tips=2,
        )
        output = format_summary(s)
        self.assertIn("3,500", output)
        self.assertIn("A-", output)
        self.assertIn("252", output)

    def test_format_session(self):
        d = SessionDetail(
            session_number=83, grade="A", grade_value=4.0,
            test_count=3277, test_delta=29,
            wins=["MT-20", "MT-11"], losses=["None"],
        )
        output = format_session(d)
        self.assertIn("S83", output)
        self.assertIn("+29", output)
        self.assertIn("MT-20", output)

    def test_format_session_negative_delta(self):
        d = SessionDetail(
            session_number=84, grade="B", grade_value=3.0,
            test_count=3200, test_delta=-77,
        )
        output = format_session(d)
        self.assertIn("-77", output)

    def test_format_growth(self):
        g = GrowthMetrics(
            data_points=[(82, 3248), (83, 3277)],
            total_growth=252, avg_growth_per_session=63.0,
            peak_session=86, peak_tests=3500,
        )
        output = format_growth(g)
        self.assertIn("+252", output)
        self.assertIn("S86", output)

    def test_format_streaks(self):
        s = StreakInfo(
            current_streak_grade="A", current_streak_length=3,
            longest_a_streak=5, sessions_since_last_decline=10,
            recent_trend="improving",
        )
        output = format_streaks(s)
        self.assertIn("3x A", output)
        self.assertIn("improving", output)


class TestCLI(unittest.TestCase):
    """Test CLI execution."""

    def test_no_args_shows_help(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, str(Path(__file__).parent.parent / "session_metrics.py")],
            capture_output=True, text=True, timeout=10
        )
        self.assertIn("session_metrics", result.stdout)
        self.assertIn("summary", result.stdout)

    def test_summary_command(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, str(Path(__file__).parent.parent / "session_metrics.py"), "summary"],
            capture_output=True, text=True, timeout=10
        )
        self.assertIn("Project Health", result.stdout)

    def test_json_output(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, str(Path(__file__).parent.parent / "session_metrics.py"), "--json", "summary"],
            capture_output=True, text=True, timeout=10
        )
        data = json.loads(result.stdout)
        self.assertIn("total_sessions", data)

    def test_growth_command(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, str(Path(__file__).parent.parent / "session_metrics.py"), "growth"],
            capture_output=True, text=True, timeout=10
        )
        self.assertIn("Test Growth", result.stdout)

    def test_streaks_command(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, str(Path(__file__).parent.parent / "session_metrics.py"), "streaks"],
            capture_output=True, text=True, timeout=10
        )
        self.assertIn("Grade Streaks", result.stdout)


if __name__ == "__main__":
    unittest.main()
