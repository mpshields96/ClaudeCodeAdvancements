#!/usr/bin/env python3
"""
test_hivemind_session_validator_extended.py — Extended edge-case tests for
hivemind_session_validator.py.

Covers: corrupt queue, missing queue, WRAP case variants, multiple assignments,
scope edge cases, history edge cases, consecutive_passes, check_phase1_gate
boundary conditions, format_for_init with various streak states.
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hivemind_session_validator as hsv


def _write_queue(path, messages):
    with open(path, "w") as f:
        for m in messages:
            f.write(json.dumps(m) + "\n")


class TestValidateSessionEdgeCases(unittest.TestCase):
    """Extended edge cases for validate_session."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.queue_path = os.path.join(self.tmpdir, "queue.jsonl")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_missing_queue_file_returns_fail(self):
        """Missing queue file = no assignments = FAIL."""
        result = hsv.validate_session("cli1", queue_path="/nonexistent/queue.jsonl")
        self.assertEqual(result["verdict"], "FAIL")
        self.assertFalse(result["task_assigned"])

    def test_corrupt_lines_skipped_valid_messages_processed(self):
        """Corrupt JSON lines are skipped; valid messages still drive verdict."""
        with open(self.queue_path, "w") as f:
            f.write("NOT JSON\n")
            f.write(json.dumps({"sender": "desktop", "target": "cli1", "category": "handoff", "subject": "task"}) + "\n")
            f.write("{bad\n")
            f.write(json.dumps({"sender": "cli1", "target": "desktop", "category": "handoff", "subject": "WRAP"}) + "\n")
        result = hsv.validate_session("cli1", queue_path=self.queue_path)
        self.assertEqual(result["verdict"], "PASS")

    def test_wrap_uppercase_counted(self):
        """'WRAP' in subject counts as completion."""
        _write_queue(self.queue_path, [
            {"sender": "desktop", "target": "cli1", "category": "handoff", "subject": "task"},
            {"sender": "cli1", "target": "desktop", "category": "handoff", "subject": "WRAP: done"},
        ])
        result = hsv.validate_session("cli1", queue_path=self.queue_path)
        self.assertTrue(result["task_completed"])

    def test_wrap_lowercase_also_counted(self):
        """'wrap' (lowercase) in subject counts because check uses .upper()."""
        _write_queue(self.queue_path, [
            {"sender": "desktop", "target": "cli1", "category": "handoff", "subject": "task"},
            {"sender": "cli1", "target": "desktop", "category": "handoff", "subject": "wrap: done"},
        ])
        result = hsv.validate_session("cli1", queue_path=self.queue_path)
        self.assertTrue(result["task_completed"])
        self.assertEqual(result["verdict"], "PASS")

    def test_multiple_assignments_all_counted(self):
        """Multiple assignments from desktop are all counted."""
        _write_queue(self.queue_path, [
            {"sender": "desktop", "target": "cli1", "category": "handoff", "subject": "task1"},
            {"sender": "desktop", "target": "cli1", "category": "handoff", "subject": "task2"},
            {"sender": "cli1", "target": "desktop", "category": "handoff", "subject": "WRAP"},
        ])
        result = hsv.validate_session("cli1", queue_path=self.queue_path)
        self.assertEqual(result["assignments"], 2)
        self.assertEqual(result["verdict"], "PASS")

    def test_no_scope_claims_scope_released_defaults_true(self):
        """Worker with no scope claims: scope_released is True (no claims = no obligation)."""
        _write_queue(self.queue_path, [
            {"sender": "desktop", "target": "cli1", "category": "handoff", "subject": "task"},
            {"sender": "cli1", "target": "desktop", "category": "handoff", "subject": "WRAP"},
        ])
        result = hsv.validate_session("cli1", queue_path=self.queue_path)
        self.assertTrue(result["scope_released"])
        self.assertEqual(result["verdict"], "PASS")

    def test_multiple_claims_require_equal_releases(self):
        """Two claims require two releases for scope_released=True."""
        _write_queue(self.queue_path, [
            {"sender": "desktop", "target": "cli1", "category": "handoff", "subject": "task"},
            {"sender": "cli1", "category": "scope_claim", "subject": "a.py"},
            {"sender": "cli1", "category": "scope_claim", "subject": "b.py"},
            {"sender": "cli1", "category": "scope_release", "subject": "a.py"},
            # b.py not released
            {"sender": "cli1", "target": "desktop", "category": "handoff", "subject": "WRAP"},
        ])
        result = hsv.validate_session("cli1", queue_path=self.queue_path)
        self.assertFalse(result["scope_released"])
        self.assertEqual(result["verdict"], "PASS_WITH_WARNINGS")

    def test_conflict_from_other_worker_not_counted(self):
        """Conflict alerts from cli2 don't count for cli1 validation."""
        _write_queue(self.queue_path, [
            {"sender": "desktop", "target": "cli1", "category": "handoff", "subject": "task"},
            {"sender": "cli2", "category": "conflict_alert", "subject": "conflict"},
            {"sender": "cli1", "target": "desktop", "category": "handoff", "subject": "WRAP"},
        ])
        result = hsv.validate_session("cli1", queue_path=self.queue_path)
        self.assertFalse(result["conflicts"])
        self.assertEqual(result["verdict"], "PASS")

    def test_cli2_worker_validated_independently(self):
        """validate_session works correctly for cli2 worker."""
        _write_queue(self.queue_path, [
            {"sender": "desktop", "target": "cli2", "category": "handoff", "subject": "task_for_cli2"},
            {"sender": "cli2", "target": "desktop", "category": "handoff", "subject": "WRAP: cli2 done"},
        ])
        result = hsv.validate_session("cli2", queue_path=self.queue_path)
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["worker_id"], "cli2")

    def test_cli1_task_not_counted_for_cli2(self):
        """cli1 task assignment doesn't count when validating cli2."""
        _write_queue(self.queue_path, [
            {"sender": "desktop", "target": "cli1", "category": "handoff", "subject": "task"},
            {"sender": "cli1", "target": "desktop", "category": "handoff", "subject": "WRAP: cli1 done"},
        ])
        result = hsv.validate_session("cli2", queue_path=self.queue_path)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertFalse(result["task_assigned"])

    def test_result_contains_all_required_fields(self):
        """validate_session result always includes all expected fields."""
        _write_queue(self.queue_path, [
            {"sender": "desktop", "target": "cli1", "category": "handoff", "subject": "task"},
            {"sender": "cli1", "target": "desktop", "category": "handoff", "subject": "WRAP"},
        ])
        result = hsv.validate_session("cli1", queue_path=self.queue_path)
        for field in ("verdict", "worker_id", "task_assigned", "task_completed",
                      "conflicts", "scope_released", "assignments", "completions", "conflict_count"):
            self.assertIn(field, result, f"Missing field: {field}")

    def test_wrap_with_extra_text_in_subject(self):
        """Subject like 'WRAP: Grade A — Built X (15 tests)' still counts."""
        _write_queue(self.queue_path, [
            {"sender": "desktop", "target": "cli1", "category": "handoff", "subject": "task"},
            {"sender": "cli1", "target": "desktop", "category": "handoff",
             "subject": "WRAP: Grade A — Built X. Tests: 15 new. Committed."},
        ])
        result = hsv.validate_session("cli1", queue_path=self.queue_path)
        self.assertTrue(result["task_completed"])

    def test_empty_queue_file_returns_fail(self):
        """Empty queue file = no data = FAIL."""
        _write_queue(self.queue_path, [])
        result = hsv.validate_session("cli1", queue_path=self.queue_path)
        self.assertEqual(result["verdict"], "FAIL")


class TestRecordSessionEdgeCases(unittest.TestCase):
    """Extended edge cases for record_session."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.log_path = os.path.join(self.tmpdir, "sessions.jsonl")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_record_returns_entry_dict(self):
        """record_session returns the written entry."""
        result = {"verdict": "PASS", "worker_id": "cli1"}
        entry = hsv.record_session(99, result, path=self.log_path)
        self.assertIsInstance(entry, dict)
        self.assertEqual(entry["session"], 99)
        self.assertEqual(entry["verdict"], "PASS")

    def test_record_with_minimal_result(self):
        """record_session handles result dict with only verdict field."""
        entry = hsv.record_session(100, {"verdict": "FAIL"}, path=self.log_path)
        self.assertEqual(entry["verdict"], "FAIL")
        self.assertEqual(entry["worker_id"], "unknown")  # default

    def test_multiple_sessions_different_workers(self):
        """Can record sessions from different workers."""
        hsv.record_session(90, {"verdict": "PASS", "worker_id": "cli1"}, path=self.log_path)
        hsv.record_session(91, {"verdict": "FAIL", "worker_id": "cli2"}, path=self.log_path)
        history = hsv.get_history(path=self.log_path)
        self.assertEqual(len(history), 2)
        workers = [e["worker_id"] for e in history]
        self.assertIn("cli1", workers)
        self.assertIn("cli2", workers)

    def test_entry_includes_timestamp(self):
        """Every recorded entry has a timestamp."""
        hsv.record_session(95, {"verdict": "PASS", "worker_id": "cli1"}, path=self.log_path)
        history = hsv.get_history(path=self.log_path)
        self.assertIn("timestamp", history[0])
        self.assertIn("Z", history[0]["timestamp"])  # UTC format


class TestHistoryAndStreakEdgeCases(unittest.TestCase):
    """Edge cases for get_history, consecutive_passes, check_phase1_gate."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.log_path = os.path.join(self.tmpdir, "sessions.jsonl")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_get_history_skips_malformed_lines(self):
        """Malformed JSON lines in history are skipped."""
        with open(self.log_path, "w") as f:
            f.write(json.dumps({"session": 90, "verdict": "PASS"}) + "\n")
            f.write("CORRUPTED LINE\n")
            f.write(json.dumps({"session": 91, "verdict": "FAIL"}) + "\n")
        history = hsv.get_history(path=self.log_path)
        self.assertEqual(len(history), 2)

    def test_get_history_skips_blank_lines(self):
        """Blank lines in history file are skipped."""
        with open(self.log_path, "w") as f:
            f.write("\n")
            f.write(json.dumps({"session": 90, "verdict": "PASS"}) + "\n")
            f.write("\n")
        history = hsv.get_history(path=self.log_path)
        self.assertEqual(len(history), 1)

    def test_consecutive_passes_zero_with_all_fails(self):
        """All FAIL sessions = streak of 0."""
        for i in range(3):
            hsv.record_session(90 + i, {"verdict": "FAIL", "worker_id": "cli1"}, path=self.log_path)
        self.assertEqual(hsv.consecutive_passes(path=self.log_path), 0)

    def test_consecutive_passes_all_pass(self):
        """All PASS sessions = streak equals total."""
        for i in range(5):
            hsv.record_session(90 + i, {"verdict": "PASS", "worker_id": "cli1"}, path=self.log_path)
        self.assertEqual(hsv.consecutive_passes(path=self.log_path), 5)

    def test_consecutive_passes_empty_history(self):
        """Empty history = streak of 0."""
        self.assertEqual(hsv.consecutive_passes(path=self.log_path), 0)

    def test_pass_with_warnings_counts_in_streak(self):
        """PASS_WITH_WARNINGS contributes to consecutive pass streak."""
        hsv.record_session(90, {"verdict": "PASS_WITH_WARNINGS", "worker_id": "cli1"}, path=self.log_path)
        hsv.record_session(91, {"verdict": "PASS", "worker_id": "cli1"}, path=self.log_path)
        self.assertEqual(hsv.consecutive_passes(path=self.log_path), 2)

    def test_streak_resets_after_fail(self):
        """Streak resets after a FAIL in the middle."""
        hsv.record_session(88, {"verdict": "PASS", "worker_id": "cli1"}, path=self.log_path)
        hsv.record_session(89, {"verdict": "PASS", "worker_id": "cli1"}, path=self.log_path)
        hsv.record_session(90, {"verdict": "FAIL", "worker_id": "cli1"}, path=self.log_path)
        hsv.record_session(91, {"verdict": "PASS", "worker_id": "cli1"}, path=self.log_path)
        self.assertEqual(hsv.consecutive_passes(path=self.log_path), 1)

    def test_gate_exactly_3_is_ready(self):
        """Exactly 3 consecutive passes = gate ready (boundary)."""
        for i in range(3):
            hsv.record_session(90 + i, {"verdict": "PASS", "worker_id": "cli1"}, path=self.log_path)
        gate = hsv.check_phase1_gate(path=self.log_path)
        self.assertTrue(gate["ready"])
        self.assertEqual(gate["consecutive_passes"], 3)

    def test_gate_exactly_2_not_ready(self):
        """2 consecutive passes = gate NOT ready (1 short)."""
        for i in range(2):
            hsv.record_session(90 + i, {"verdict": "PASS", "worker_id": "cli1"}, path=self.log_path)
        gate = hsv.check_phase1_gate(path=self.log_path)
        self.assertFalse(gate["ready"])
        self.assertEqual(gate["consecutive_passes"], 2)

    def test_gate_more_than_3_consecutive_also_ready(self):
        """5 consecutive passes = gate ready (more than threshold)."""
        for i in range(5):
            hsv.record_session(90 + i, {"verdict": "PASS", "worker_id": "cli1"}, path=self.log_path)
        gate = hsv.check_phase1_gate(path=self.log_path)
        self.assertTrue(gate["ready"])

    def test_gate_total_passes_and_fails(self):
        """Gate result includes correct total_passes and total_fails counts."""
        hsv.record_session(88, {"verdict": "FAIL", "worker_id": "cli1"}, path=self.log_path)
        hsv.record_session(89, {"verdict": "PASS", "worker_id": "cli1"}, path=self.log_path)
        hsv.record_session(90, {"verdict": "PASS_WITH_WARNINGS", "worker_id": "cli1"}, path=self.log_path)
        hsv.record_session(91, {"verdict": "PASS", "worker_id": "cli1"}, path=self.log_path)
        gate = hsv.check_phase1_gate(path=self.log_path)
        self.assertEqual(gate["total_sessions"], 4)
        self.assertEqual(gate["total_passes"], 3)
        self.assertEqual(gate["total_fails"], 1)


class TestFormatForInitEdgeCases(unittest.TestCase):
    """Edge cases for format_for_init."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.log_path = os.path.join(self.tmpdir, "sessions.jsonl")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_single_pass_shows_gate_needs_more(self):
        """1 PASS session shows how many more needed."""
        hsv.record_session(90, {"verdict": "PASS", "worker_id": "cli1"}, path=self.log_path)
        line = hsv.format_for_init(path=self.log_path)
        self.assertIn("2 more", line)

    def test_two_passes_shows_one_more_needed(self):
        """2 PASS sessions shows 1 more needed."""
        hsv.record_session(90, {"verdict": "PASS", "worker_id": "cli1"}, path=self.log_path)
        hsv.record_session(91, {"verdict": "PASS", "worker_id": "cli1"}, path=self.log_path)
        line = hsv.format_for_init(path=self.log_path)
        self.assertIn("1 more", line)

    def test_three_passes_shows_passed(self):
        """3 consecutive passes shows Phase 1: PASSED."""
        for i in range(3):
            hsv.record_session(90 + i, {"verdict": "PASS", "worker_id": "cli1"}, path=self.log_path)
        line = hsv.format_for_init(path=self.log_path)
        self.assertIn("Phase 1: PASSED", line)

    def test_pass_with_warnings_counts_for_gate(self):
        """PASS_WITH_WARNINGS sessions contribute to Phase 1 gate in format."""
        for i in range(3):
            hsv.record_session(90 + i, {"verdict": "PASS_WITH_WARNINGS", "worker_id": "cli1"}, path=self.log_path)
        line = hsv.format_for_init(path=self.log_path)
        self.assertIn("Phase 1: PASSED", line)

    def test_streak_broken_shows_reset_count(self):
        """After a FAIL, streak resets; format shows reduced consecutive count."""
        for i in range(3):
            hsv.record_session(88 + i, {"verdict": "PASS", "worker_id": "cli1"}, path=self.log_path)
        hsv.record_session(91, {"verdict": "FAIL", "worker_id": "cli1"}, path=self.log_path)
        hsv.record_session(92, {"verdict": "PASS", "worker_id": "cli1"}, path=self.log_path)
        line = hsv.format_for_init(path=self.log_path)
        # Streak is now 1, not 4
        self.assertIn("1 consecutive PASS", line)

    def test_total_session_count_shown(self):
        """Total session count shown in format_for_init output."""
        for i in range(4):
            hsv.record_session(90 + i, {"verdict": "PASS", "worker_id": "cli1"}, path=self.log_path)
        line = hsv.format_for_init(path=self.log_path)
        self.assertIn("4 sessions", line)


if __name__ == "__main__":
    unittest.main()
