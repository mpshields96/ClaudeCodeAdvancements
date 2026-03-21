"""Tests for loop_health.py — per-session health tracking for cca-loop."""

import json
import unittest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timezone

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from loop_health import (
    SessionHealth,
    parse_session_state,
    record_session,
    load_history,
    detect_regressions,
    get_summary,
    format_history_table,
)


# ── Helper ────────────────────────────────────────────────────────────────────

def make_health(
    session_id="s1",
    grade="A",
    test_pass=100,
    test_fail=0,
    duration_secs=3600,
    error_type=None,
    notes="",
    timestamp=None,
):
    return SessionHealth(
        session_id=session_id,
        timestamp=timestamp or datetime.now(timezone.utc).isoformat(),
        grade=grade,
        test_pass=test_pass,
        test_fail=test_fail,
        duration_secs=duration_secs,
        error_type=error_type,
        notes=notes,
    )


# ── parse_session_state ───────────────────────────────────────────────────────

class TestParseSessionState(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.tmp = Path(self.tmpdir)
        self.state_file = self.tmp / "SESSION_STATE.md"
        self.state_file.write_text(
            "# CCA State\n"
            "## Current State (as of Session 73 — 2026-03-20)\n"
            "**Phase:** Session 73 WRAP. Tests: 2897/2897 passing (72 suites). Git: clean.\n"
        )
        self.failing_state = self.tmp / "failing.md"
        self.failing_state.write_text(
            "# CCA State\n"
            "## Session 74\n"
            "Tests: 2850/2897 passing (72 suites).\n"
        )
        self.empty_state = self.tmp / "empty.md"
        self.empty_state.write_text("# CCA State\nNo test info here.\n")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_parses_passing_tests(self):
        result = parse_session_state(self.state_file)
        self.assertEqual(result["test_pass"], 2897)
        self.assertEqual(result["test_total"], 2897)
        self.assertEqual(result["test_fail"], 0)

    def test_grade_a_when_all_pass(self):
        result = parse_session_state(self.state_file)
        self.assertEqual(result["grade"], "A")

    def test_grade_b_at_97_percent(self):
        f = self.tmp / "s.md"
        f.write_text("Tests: 97/100 passing\n")
        result = parse_session_state(f)
        self.assertEqual(result["grade"], "B")

    def test_grade_c_at_90_percent(self):
        f = self.tmp / "s.md"
        f.write_text("Tests: 90/100 passing\n")
        result = parse_session_state(f)
        self.assertEqual(result["grade"], "C")

    def test_grade_d_at_75_percent(self):
        f = self.tmp / "s.md"
        f.write_text("Tests: 75/100 passing\n")
        result = parse_session_state(f)
        self.assertEqual(result["grade"], "D")

    def test_grade_f_below_70(self):
        f = self.tmp / "s.md"
        f.write_text("Tests: 60/100 passing\n")
        result = parse_session_state(f)
        self.assertEqual(result["grade"], "F")

    def test_extracts_session_number(self):
        result = parse_session_state(self.state_file)
        self.assertEqual(result["session_num"], 73)

    def test_missing_file_returns_empty(self):
        result = parse_session_state(self.tmp / "nonexistent.md")
        self.assertEqual(result, {})

    def test_no_test_info_returns_unknown_grade(self):
        result = parse_session_state(self.empty_state)
        self.assertEqual(result["grade"], "unknown")

    def test_failing_tests_counted(self):
        result = parse_session_state(self.failing_state)
        self.assertEqual(result["test_fail"], 47)
        self.assertEqual(result["test_pass"], 2850)

    def test_grade_b_boundary_exactly_95(self):
        f = self.tmp / "s.md"
        f.write_text("Tests: 95/100 passing\n")
        result = parse_session_state(f)
        self.assertEqual(result["grade"], "B")

    def test_grade_d_boundary_exactly_70(self):
        f = self.tmp / "s.md"
        f.write_text("Tests: 70/100 passing\n")
        result = parse_session_state(f)
        self.assertEqual(result["grade"], "D")


# ── record_session ────────────────────────────────────────────────────────────

class TestRecordSession(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.tmp = Path(self.tmpdir)
        self.health_file = self.tmp / ".cca-loop-health.jsonl"
        self.state_file = self.tmp / "SESSION_STATE.md"
        self.state_file.write_text(
            "# CCA State\n"
            "## Current State (as of Session 73 — 2026-03-20)\n"
            "**Phase:** Session 73 WRAP. Tests: 2897/2897 passing (72 suites). Git: clean.\n"
        )

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_creates_health_file(self):
        record_session("s1", 3600, health_file=self.health_file, state_path=self.state_file)
        self.assertTrue(self.health_file.exists())

    def test_appends_jsonl(self):
        record_session("s1", 3600, health_file=self.health_file, state_path=self.state_file)
        record_session("s2", 1800, health_file=self.health_file, state_path=self.state_file)
        lines = [l for l in self.health_file.read_text().strip().split("\n") if l]
        self.assertEqual(len(lines), 2)

    def test_records_correct_fields(self):
        h = record_session("s42", 5400, health_file=self.health_file, state_path=self.state_file)
        self.assertEqual(h.session_id, "S42")
        self.assertEqual(h.duration_secs, 5400)
        self.assertEqual(h.grade, "A")
        self.assertEqual(h.test_pass, 2897)

    def test_records_error_type(self):
        h = record_session("s1", 100, error_type="timeout", health_file=self.health_file, state_path=self.state_file)
        self.assertEqual(h.error_type, "timeout")

    def test_records_notes(self):
        h = record_session("s1", 100, notes="test note", health_file=self.health_file, state_path=self.state_file)
        self.assertEqual(h.notes, "test note")

    def test_timestamp_is_utc_iso(self):
        h = record_session("s1", 100, health_file=self.health_file, state_path=self.state_file)
        dt = datetime.fromisoformat(h.timestamp)
        self.assertIsNotNone(dt.tzinfo)

    def test_missing_state_records_unknowns(self):
        missing = self.tmp / "missing.md"
        h = record_session("s1", 100, health_file=self.health_file, state_path=missing)
        self.assertEqual(h.grade, "unknown")
        self.assertEqual(h.test_pass, 0)


# ── load_history ──────────────────────────────────────────────────────────────

class TestLoadHistory(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.tmp = Path(self.tmpdir)
        self.health_file = self.tmp / ".cca-loop-health.jsonl"
        self.state_file = self.tmp / "SESSION_STATE.md"
        self.state_file.write_text(
            "# CCA State\n"
            "## Current State (as of Session 73 — 2026-03-20)\n"
            "**Phase:** Session 73 WRAP. Tests: 2897/2897 passing (72 suites). Git: clean.\n"
        )

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_empty_file_returns_empty(self):
        self.health_file.write_text("")
        result = load_history(health_file=self.health_file)
        self.assertEqual(result, [])

    def test_missing_file_returns_empty(self):
        result = load_history(health_file=self.tmp / "missing.jsonl")
        self.assertEqual(result, [])

    def test_loads_all_records(self):
        for i in range(5):
            record_session(f"s{i}", 100 * i, health_file=self.health_file, state_path=self.state_file)
        result = load_history(health_file=self.health_file)
        self.assertEqual(len(result), 5)

    def test_n_limits_to_last_n(self):
        for i in range(10):
            record_session(f"s{i}", 100, health_file=self.health_file, state_path=self.state_file)
        result = load_history(n=3, health_file=self.health_file)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[-1].session_id, "S9")

    def test_returns_session_health_objects(self):
        record_session("s1", 100, health_file=self.health_file, state_path=self.state_file)
        result = load_history(health_file=self.health_file)
        self.assertIsInstance(result[0], SessionHealth)

    def test_skips_blank_lines(self):
        record_session("s1", 100, health_file=self.health_file, state_path=self.state_file)
        with open(self.health_file, "a") as f:
            f.write("\n\n")
        record_session("s2", 200, health_file=self.health_file, state_path=self.state_file)
        result = load_history(health_file=self.health_file)
        self.assertEqual(len(result), 2)


# ── detect_regressions ────────────────────────────────────────────────────────

class TestDetectRegressions(unittest.TestCase):
    def test_empty_history_no_regressions(self):
        self.assertEqual(detect_regressions([]), [])

    def test_single_session_no_regressions(self):
        h = [make_health("s1", grade="A", test_pass=100)]
        self.assertEqual(detect_regressions(h), [])

    def test_no_regression_stable(self):
        history = [
            make_health("s1", grade="A", test_pass=100),
            make_health("s2", grade="A", test_pass=100),
            make_health("s3", grade="A", test_pass=100),
        ]
        self.assertEqual(detect_regressions(history), [])

    def test_test_count_drop_detected(self):
        history = [
            make_health("s1", grade="A", test_pass=100, test_fail=0),
            make_health("s2", grade="A", test_pass=90, test_fail=0),
        ]
        result = detect_regressions(history)
        self.assertTrue(any("test_count_drop" in r for r in result))

    def test_test_count_drop_shows_values(self):
        history = [
            make_health("s1", grade="A", test_pass=100, test_fail=0),
            make_health("s2", grade="A", test_pass=80, test_fail=0),
        ]
        result = detect_regressions(history)
        self.assertIn("test_count_drop: 100 -> 80", result)

    def test_test_count_increase_no_regression(self):
        history = [
            make_health("s1", grade="A", test_pass=100),
            make_health("s2", grade="A", test_pass=110),
        ]
        self.assertEqual(detect_regressions(history), [])

    def test_single_grade_drop_not_regression(self):
        history = [
            make_health("s1", grade="A", test_pass=100),
            make_health("s2", grade="B", test_pass=100),
            make_health("s3", grade="A", test_pass=100),
        ]
        result = detect_regressions(history)
        self.assertFalse(any("grade_drop" in r for r in result))

    def test_two_consecutive_grade_drops_detected(self):
        history = [
            make_health("s1", grade="A", test_pass=100),
            make_health("s2", grade="B", test_pass=100),
            make_health("s3", grade="C", test_pass=100),
        ]
        result = detect_regressions(history)
        self.assertTrue(any("grade_drop" in r for r in result))

    def test_grade_drop_shows_sequence(self):
        history = [
            make_health("s1", grade="A", test_pass=100),
            make_health("s2", grade="B", test_pass=100),
            make_health("s3", grade="C", test_pass=100),
        ]
        result = detect_regressions(history)
        self.assertIn("grade_drop: A -> B -> C", result)

    def test_unknown_grade_skipped_in_drop_detection(self):
        history = [
            make_health("s1", grade="A", test_pass=100),
            make_health("s2", grade="unknown", test_pass=0),
            make_health("s3", grade="F", test_pass=0),
        ]
        result = detect_regressions(history)
        self.assertFalse(any("grade_drop" in r for r in result))

    def test_both_regressions_can_fire(self):
        history = [
            make_health("s1", grade="A", test_pass=100, test_fail=0),
            make_health("s2", grade="B", test_pass=90, test_fail=0),
            make_health("s3", grade="C", test_pass=80, test_fail=0),
        ]
        result = detect_regressions(history)
        self.assertEqual(len(result), 2)


# ── get_summary ───────────────────────────────────────────────────────────────

class TestGetSummary(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.tmp = Path(self.tmpdir)
        self.health_file = self.tmp / ".cca-loop-health.jsonl"
        self.state_file = self.tmp / "SESSION_STATE.md"
        self.state_file.write_text(
            "# CCA State\n"
            "## Current State (as of Session 73 — 2026-03-20)\n"
            "**Phase:** Session 73 WRAP. Tests: 2897/2897 passing (72 suites). Git: clean.\n"
        )

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_empty_returns_zeros(self):
        result = get_summary(health_file=self.health_file)
        self.assertEqual(result["sessions"], 0)
        self.assertEqual(result["current_streak"], 0)

    def test_sessions_count(self):
        for i in range(3):
            record_session(f"s{i}", 100, health_file=self.health_file, state_path=self.state_file)
        result = get_summary(health_file=self.health_file)
        self.assertEqual(result["sessions"], 3)

    def test_average_grade_all_a(self):
        for i in range(3):
            record_session(f"s{i}", 100, health_file=self.health_file, state_path=self.state_file)
        result = get_summary(health_file=self.health_file)
        self.assertEqual(result["average_grade"], "A")

    def test_test_pass_rate_perfect(self):
        record_session("s1", 100, health_file=self.health_file, state_path=self.state_file)
        result = get_summary(health_file=self.health_file)
        self.assertEqual(result["test_pass_rate"], 1.0)

    def test_last_error_none_on_success(self):
        record_session("s1", 100, health_file=self.health_file, state_path=self.state_file)
        result = get_summary(health_file=self.health_file)
        self.assertIsNone(result["last_error"])

    def test_last_error_set(self):
        record_session("s1", 100, error_type="timeout", health_file=self.health_file, state_path=self.state_file)
        result = get_summary(health_file=self.health_file)
        self.assertEqual(result["last_error"], "timeout")

    def test_streak_on_all_success(self):
        for i in range(5):
            record_session(f"s{i}", 100, health_file=self.health_file, state_path=self.state_file)
        result = get_summary(health_file=self.health_file)
        self.assertEqual(result["current_streak"], 5)

    def test_streak_resets_after_error(self):
        record_session("s1", 100, error_type="crash", health_file=self.health_file, state_path=self.state_file)
        record_session("s2", 100, health_file=self.health_file, state_path=self.state_file)
        record_session("s3", 100, health_file=self.health_file, state_path=self.state_file)
        result = get_summary(health_file=self.health_file)
        self.assertEqual(result["current_streak"], 2)

    def test_sessions_today_subset(self):
        for i in range(3):
            record_session(f"s{i}", 100, health_file=self.health_file, state_path=self.state_file)
        result = get_summary(health_file=self.health_file)
        self.assertEqual(result["sessions_today"], 3)

    def test_regressions_included(self):
        from dataclasses import asdict
        records = [
            make_health("s1", grade="A", test_pass=100),
            make_health("s2", grade="B", test_pass=100),
            make_health("s3", grade="C", test_pass=100),
        ]
        with open(self.health_file, "w") as f:
            for r in records:
                f.write(json.dumps(asdict(r)) + "\n")
        result = get_summary(health_file=self.health_file)
        self.assertGreater(len(result["regressions"]), 0)

    def test_n_limits_history_for_summary(self):
        for i in range(10):
            record_session(f"s{i}", 100, health_file=self.health_file, state_path=self.state_file)
        result = get_summary(n=3, health_file=self.health_file)
        self.assertEqual(result["sessions"], 3)


# ── format_history_table ──────────────────────────────────────────────────────

class TestFormatHistoryTable(unittest.TestCase):
    def test_empty_returns_no_history_message(self):
        result = format_history_table([])
        self.assertIn("No session history", result)

    def test_header_row_present(self):
        history = [make_health("s1")]
        result = format_history_table(history)
        self.assertIn("Grade", result)
        self.assertIn("Tests", result)
        self.assertIn("Duration", result)

    def test_session_id_in_output(self):
        history = [make_health("my-session-123")]
        result = format_history_table(history)
        self.assertIn("my-session-123", result)

    def test_grade_in_output(self):
        history = [make_health("s1", grade="B")]
        result = format_history_table(history)
        self.assertIn("B", result)

    def test_error_type_in_output(self):
        history = [make_health("s1", error_type="timeout")]
        result = format_history_table(history)
        self.assertIn("timeout", result)

    def test_no_error_shows_dash(self):
        history = [make_health("s1", error_type=None)]
        result = format_history_table(history)
        self.assertIn("-", result)

    def test_multiple_sessions_multiple_rows(self):
        history = [make_health(f"s{i}") for i in range(5)]
        result = format_history_table(history)
        lines = [l for l in result.split("\n") if l.strip()]
        self.assertGreaterEqual(len(lines), 7)


if __name__ == "__main__":
    unittest.main()
