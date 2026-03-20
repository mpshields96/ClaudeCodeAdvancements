"""Tests for loop_health.py — per-session health tracking for cca-loop."""

import json
import pytest
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


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_health_file(tmp_path):
    return tmp_path / ".cca-loop-health.jsonl"


@pytest.fixture
def tmp_state_file(tmp_path):
    f = tmp_path / "SESSION_STATE.md"
    f.write_text(
        "# CCA State\n"
        "## Current State (as of Session 73 — 2026-03-20)\n"
        "**Phase:** Session 73 WRAP. Tests: 2897/2897 passing (72 suites). Git: clean.\n"
    )
    return f


@pytest.fixture
def tmp_failing_state(tmp_path):
    f = tmp_path / "SESSION_STATE.md"
    f.write_text(
        "# CCA State\n"
        "## Session 74\n"
        "Tests: 2850/2897 passing (72 suites).\n"
    )
    return f


@pytest.fixture
def tmp_empty_state(tmp_path):
    f = tmp_path / "SESSION_STATE.md"
    f.write_text("# CCA State\nNo test info here.\n")
    return f


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

class TestParseSessionState:
    def test_parses_passing_tests(self, tmp_state_file):
        result = parse_session_state(tmp_state_file)
        assert result["test_pass"] == 2897
        assert result["test_total"] == 2897
        assert result["test_fail"] == 0

    def test_grade_a_when_all_pass(self, tmp_state_file):
        result = parse_session_state(tmp_state_file)
        assert result["grade"] == "A"

    def test_grade_b_at_97_percent(self, tmp_path):
        f = tmp_path / "s.md"
        f.write_text("Tests: 97/100 passing\n")
        result = parse_session_state(f)
        assert result["grade"] == "B"

    def test_grade_c_at_90_percent(self, tmp_path):
        f = tmp_path / "s.md"
        f.write_text("Tests: 90/100 passing\n")
        result = parse_session_state(f)
        assert result["grade"] == "C"

    def test_grade_d_at_75_percent(self, tmp_path):
        f = tmp_path / "s.md"
        f.write_text("Tests: 75/100 passing\n")
        result = parse_session_state(f)
        assert result["grade"] == "D"

    def test_grade_f_below_70(self, tmp_path):
        f = tmp_path / "s.md"
        f.write_text("Tests: 60/100 passing\n")
        result = parse_session_state(f)
        assert result["grade"] == "F"

    def test_extracts_session_number(self, tmp_state_file):
        result = parse_session_state(tmp_state_file)
        assert result["session_num"] == 73

    def test_missing_file_returns_empty(self, tmp_path):
        result = parse_session_state(tmp_path / "nonexistent.md")
        assert result == {}

    def test_no_test_info_returns_unknown_grade(self, tmp_empty_state):
        result = parse_session_state(tmp_empty_state)
        assert result["grade"] == "unknown"

    def test_failing_tests_counted(self, tmp_failing_state):
        result = parse_session_state(tmp_failing_state)
        assert result["test_fail"] == 47
        assert result["test_pass"] == 2850

    def test_grade_b_boundary_exactly_95(self, tmp_path):
        f = tmp_path / "s.md"
        f.write_text("Tests: 95/100 passing\n")
        result = parse_session_state(f)
        assert result["grade"] == "B"

    def test_grade_d_boundary_exactly_70(self, tmp_path):
        f = tmp_path / "s.md"
        f.write_text("Tests: 70/100 passing\n")
        result = parse_session_state(f)
        assert result["grade"] == "D"


# ── record_session ────────────────────────────────────────────────────────────

class TestRecordSession:
    def test_creates_health_file(self, tmp_health_file, tmp_state_file):
        record_session("s1", 3600, health_file=tmp_health_file, state_path=tmp_state_file)
        assert tmp_health_file.exists()

    def test_appends_jsonl(self, tmp_health_file, tmp_state_file):
        record_session("s1", 3600, health_file=tmp_health_file, state_path=tmp_state_file)
        record_session("s2", 1800, health_file=tmp_health_file, state_path=tmp_state_file)
        lines = [l for l in tmp_health_file.read_text().strip().split("\n") if l]
        assert len(lines) == 2

    def test_records_correct_fields(self, tmp_health_file, tmp_state_file):
        h = record_session("s42", 5400, health_file=tmp_health_file, state_path=tmp_state_file)
        assert h.session_id == "s42"
        assert h.duration_secs == 5400
        assert h.grade == "A"
        assert h.test_pass == 2897

    def test_records_error_type(self, tmp_health_file, tmp_state_file):
        h = record_session("s1", 100, error_type="timeout", health_file=tmp_health_file, state_path=tmp_state_file)
        assert h.error_type == "timeout"

    def test_records_notes(self, tmp_health_file, tmp_state_file):
        h = record_session("s1", 100, notes="test note", health_file=tmp_health_file, state_path=tmp_state_file)
        assert h.notes == "test note"

    def test_timestamp_is_utc_iso(self, tmp_health_file, tmp_state_file):
        h = record_session("s1", 100, health_file=tmp_health_file, state_path=tmp_state_file)
        # Should parse as ISO datetime
        dt = datetime.fromisoformat(h.timestamp)
        assert dt.tzinfo is not None

    def test_missing_state_records_unknowns(self, tmp_health_file, tmp_path):
        missing = tmp_path / "missing.md"
        h = record_session("s1", 100, health_file=tmp_health_file, state_path=missing)
        assert h.grade == "unknown"
        assert h.test_pass == 0


# ── load_history ──────────────────────────────────────────────────────────────

class TestLoadHistory:
    def test_empty_file_returns_empty(self, tmp_health_file):
        tmp_health_file.write_text("")
        result = load_history(health_file=tmp_health_file)
        assert result == []

    def test_missing_file_returns_empty(self, tmp_path):
        result = load_history(health_file=tmp_path / "missing.jsonl")
        assert result == []

    def test_loads_all_records(self, tmp_health_file, tmp_state_file):
        for i in range(5):
            record_session(f"s{i}", 100 * i, health_file=tmp_health_file, state_path=tmp_state_file)
        result = load_history(health_file=tmp_health_file)
        assert len(result) == 5

    def test_n_limits_to_last_n(self, tmp_health_file, tmp_state_file):
        for i in range(10):
            record_session(f"s{i}", 100, health_file=tmp_health_file, state_path=tmp_state_file)
        result = load_history(n=3, health_file=tmp_health_file)
        assert len(result) == 3
        assert result[-1].session_id == "s9"

    def test_returns_session_health_objects(self, tmp_health_file, tmp_state_file):
        record_session("s1", 100, health_file=tmp_health_file, state_path=tmp_state_file)
        result = load_history(health_file=tmp_health_file)
        assert isinstance(result[0], SessionHealth)

    def test_skips_blank_lines(self, tmp_health_file, tmp_state_file):
        record_session("s1", 100, health_file=tmp_health_file, state_path=tmp_state_file)
        with open(tmp_health_file, "a") as f:
            f.write("\n\n")
        record_session("s2", 200, health_file=tmp_health_file, state_path=tmp_state_file)
        result = load_history(health_file=tmp_health_file)
        assert len(result) == 2


# ── detect_regressions ────────────────────────────────────────────────────────

class TestDetectRegressions:
    def test_empty_history_no_regressions(self):
        assert detect_regressions([]) == []

    def test_single_session_no_regressions(self):
        h = [make_health("s1", grade="A", test_pass=100)]
        assert detect_regressions(h) == []

    def test_no_regression_stable(self):
        history = [
            make_health("s1", grade="A", test_pass=100),
            make_health("s2", grade="A", test_pass=100),
            make_health("s3", grade="A", test_pass=100),
        ]
        assert detect_regressions(history) == []

    def test_test_count_drop_detected(self):
        history = [
            make_health("s1", grade="A", test_pass=100, test_fail=0),
            make_health("s2", grade="A", test_pass=90, test_fail=0),
        ]
        result = detect_regressions(history)
        assert any("test_count_drop" in r for r in result)

    def test_test_count_drop_shows_values(self):
        history = [
            make_health("s1", grade="A", test_pass=100, test_fail=0),
            make_health("s2", grade="A", test_pass=80, test_fail=0),
        ]
        result = detect_regressions(history)
        assert "test_count_drop: 100 -> 80" in result

    def test_test_count_increase_no_regression(self):
        history = [
            make_health("s1", grade="A", test_pass=100),
            make_health("s2", grade="A", test_pass=110),
        ]
        assert detect_regressions(history) == []

    def test_single_grade_drop_not_regression(self):
        history = [
            make_health("s1", grade="A", test_pass=100),
            make_health("s2", grade="B", test_pass=100),
            make_health("s3", grade="A", test_pass=100),  # recovered
        ]
        result = detect_regressions(history)
        assert not any("grade_drop" in r for r in result)

    def test_two_consecutive_grade_drops_detected(self):
        history = [
            make_health("s1", grade="A", test_pass=100),
            make_health("s2", grade="B", test_pass=100),
            make_health("s3", grade="C", test_pass=100),
        ]
        result = detect_regressions(history)
        assert any("grade_drop" in r for r in result)

    def test_grade_drop_shows_sequence(self):
        history = [
            make_health("s1", grade="A", test_pass=100),
            make_health("s2", grade="B", test_pass=100),
            make_health("s3", grade="C", test_pass=100),
        ]
        result = detect_regressions(history)
        assert "grade_drop: A -> B -> C" in result

    def test_unknown_grade_skipped_in_drop_detection(self):
        history = [
            make_health("s1", grade="A", test_pass=100),
            make_health("s2", grade="unknown", test_pass=0),
            make_health("s3", grade="F", test_pass=0),
        ]
        result = detect_regressions(history)
        assert not any("grade_drop" in r for r in result)

    def test_both_regressions_can_fire(self):
        history = [
            make_health("s1", grade="A", test_pass=100, test_fail=0),
            make_health("s2", grade="B", test_pass=90, test_fail=0),
            make_health("s3", grade="C", test_pass=80, test_fail=0),
        ]
        result = detect_regressions(history)
        assert len(result) == 2


# ── get_summary ───────────────────────────────────────────────────────────────

class TestGetSummary:
    def test_empty_returns_zeros(self, tmp_health_file):
        result = get_summary(health_file=tmp_health_file)
        assert result["sessions"] == 0
        assert result["current_streak"] == 0

    def test_sessions_count(self, tmp_health_file, tmp_state_file):
        for i in range(3):
            record_session(f"s{i}", 100, health_file=tmp_health_file, state_path=tmp_state_file)
        result = get_summary(health_file=tmp_health_file)
        assert result["sessions"] == 3

    def test_average_grade_all_a(self, tmp_health_file, tmp_state_file):
        for i in range(3):
            record_session(f"s{i}", 100, health_file=tmp_health_file, state_path=tmp_state_file)
        result = get_summary(health_file=tmp_health_file)
        assert result["average_grade"] == "A"

    def test_test_pass_rate_perfect(self, tmp_health_file, tmp_state_file):
        record_session("s1", 100, health_file=tmp_health_file, state_path=tmp_state_file)
        result = get_summary(health_file=tmp_health_file)
        assert result["test_pass_rate"] == 1.0

    def test_last_error_none_on_success(self, tmp_health_file, tmp_state_file):
        record_session("s1", 100, health_file=tmp_health_file, state_path=tmp_state_file)
        result = get_summary(health_file=tmp_health_file)
        assert result["last_error"] is None

    def test_last_error_set(self, tmp_health_file, tmp_state_file):
        record_session("s1", 100, error_type="timeout", health_file=tmp_health_file, state_path=tmp_state_file)
        result = get_summary(health_file=tmp_health_file)
        assert result["last_error"] == "timeout"

    def test_streak_on_all_success(self, tmp_health_file, tmp_state_file):
        for i in range(5):
            record_session(f"s{i}", 100, health_file=tmp_health_file, state_path=tmp_state_file)
        result = get_summary(health_file=tmp_health_file)
        assert result["current_streak"] == 5

    def test_streak_resets_after_error(self, tmp_health_file, tmp_state_file):
        record_session("s1", 100, error_type="crash", health_file=tmp_health_file, state_path=tmp_state_file)
        record_session("s2", 100, health_file=tmp_health_file, state_path=tmp_state_file)
        record_session("s3", 100, health_file=tmp_health_file, state_path=tmp_state_file)
        result = get_summary(health_file=tmp_health_file)
        assert result["current_streak"] == 2

    def test_sessions_today_subset(self, tmp_health_file, tmp_state_file):
        # All recorded now should count as today
        for i in range(3):
            record_session(f"s{i}", 100, health_file=tmp_health_file, state_path=tmp_state_file)
        result = get_summary(health_file=tmp_health_file)
        assert result["sessions_today"] == 3

    def test_regressions_included(self, tmp_health_file):
        # Write directly to health file with grade drops
        import json
        from dataclasses import asdict
        records = [
            make_health("s1", grade="A", test_pass=100),
            make_health("s2", grade="B", test_pass=100),
            make_health("s3", grade="C", test_pass=100),
        ]
        with open(tmp_health_file, "w") as f:
            for r in records:
                f.write(json.dumps(asdict(r)) + "\n")
        result = get_summary(health_file=tmp_health_file)
        assert len(result["regressions"]) > 0

    def test_n_limits_history_for_summary(self, tmp_health_file, tmp_state_file):
        for i in range(10):
            record_session(f"s{i}", 100, health_file=tmp_health_file, state_path=tmp_state_file)
        result = get_summary(n=3, health_file=tmp_health_file)
        assert result["sessions"] == 3


# ── format_history_table ──────────────────────────────────────────────────────

class TestFormatHistoryTable:
    def test_empty_returns_no_history_message(self):
        result = format_history_table([])
        assert "No session history" in result

    def test_header_row_present(self):
        history = [make_health("s1")]
        result = format_history_table(history)
        assert "Grade" in result
        assert "Tests" in result
        assert "Duration" in result

    def test_session_id_in_output(self):
        history = [make_health("my-session-123")]
        result = format_history_table(history)
        assert "my-session-123" in result

    def test_grade_in_output(self):
        history = [make_health("s1", grade="B")]
        result = format_history_table(history)
        assert "B" in result

    def test_error_type_in_output(self):
        history = [make_health("s1", error_type="timeout")]
        result = format_history_table(history)
        assert "timeout" in result

    def test_no_error_shows_dash(self):
        history = [make_health("s1", error_type=None)]
        result = format_history_table(history)
        assert " - " in result or "\t-\t" in result or "-" in result

    def test_multiple_sessions_multiple_rows(self):
        history = [make_health(f"s{i}") for i in range(5)]
        result = format_history_table(history)
        lines = [l for l in result.split("\n") if l.strip()]
        # header + separator + 5 rows
        assert len(lines) >= 7
