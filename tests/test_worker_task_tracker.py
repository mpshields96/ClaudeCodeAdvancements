"""
Tests for worker_task_tracker.py

Tests that the tracker correctly identifies when workers wrap without
completing all assigned tasks. TDD-first.
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from worker_task_tracker import (
    load_queue,
    parse_worker_sessions,
    detect_incomplete_sessions,
    report,
    WorkerSession,
)


def _make_msg(sender, target, subject, category="handoff", created_at=None):
    return {
        "id": f"cca_{hash(subject) & 0xFFFF:04x}",
        "sender": sender,
        "target": target,
        "subject": subject,
        "category": category,
        "status": "read",
        "created_at": created_at or "2026-03-20T10:00:00Z",
        "read_at": None,
    }


def _write_jsonl(msgs, path):
    with open(path, "w") as f:
        for m in msgs:
            f.write(json.dumps(m) + "\n")


class TestLoadQueue(unittest.TestCase):
    def test_load_empty_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write("")
            path = f.name
        try:
            result = load_queue(path)
            self.assertEqual(result, [])
        finally:
            os.unlink(path)

    def test_load_valid_messages(self):
        msgs = [
            _make_msg("desktop", "cli1", "task A"),
            _make_msg("cli1", "desktop", "WRAP: task A done"),
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for m in msgs:
                f.write(json.dumps(m) + "\n")
            path = f.name
        try:
            result = load_queue(path)
            self.assertEqual(len(result), 2)
        finally:
            os.unlink(path)

    def test_load_skips_blank_lines(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(json.dumps(_make_msg("desktop", "cli1", "task A")) + "\n")
            f.write("\n")
            f.write("\n")
            path = f.name
        try:
            result = load_queue(path)
            self.assertEqual(len(result), 1)
        finally:
            os.unlink(path)

    def test_load_missing_file_returns_empty(self):
        result = load_queue("/nonexistent/path.jsonl")
        self.assertEqual(result, [])


class TestParseWorkerSessions(unittest.TestCase):
    def _ts(self, h, m=0):
        return f"2026-03-20T{h:02d}:{m:02d}:00Z"

    def test_single_complete_session(self):
        msgs = [
            _make_msg("desktop", "cli1", "task A", created_at=self._ts(10, 0)),
            _make_msg("cli1", "desktop", "WRAP: task A done", created_at=self._ts(10, 30)),
            _make_msg("desktop", "cli1", "SHUTDOWN: exit", created_at=self._ts(10, 45)),
        ]
        sessions = parse_worker_sessions(msgs, "cli1")
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0].assigned_count, 1)
        self.assertEqual(sessions[0].wrap_count, 1)
        self.assertTrue(sessions[0].is_complete)

    def test_incomplete_session_missing_wrap(self):
        msgs = [
            _make_msg("desktop", "cli1", "task A", created_at=self._ts(10, 0)),
            _make_msg("desktop", "cli1", "task B", created_at=self._ts(10, 5)),
            _make_msg("cli1", "desktop", "WRAP: task A done", created_at=self._ts(10, 30)),
            _make_msg("desktop", "cli1", "SHUTDOWN: exit", created_at=self._ts(10, 45)),
        ]
        sessions = parse_worker_sessions(msgs, "cli1")
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0].assigned_count, 2)
        self.assertEqual(sessions[0].wrap_count, 1)
        self.assertFalse(sessions[0].is_complete)

    def test_multiple_sessions_separated_by_shutdown(self):
        msgs = [
            _make_msg("desktop", "cli1", "task A", created_at=self._ts(10, 0)),
            _make_msg("cli1", "desktop", "WRAP: task A done", created_at=self._ts(10, 30)),
            _make_msg("desktop", "cli1", "SHUTDOWN: exit", created_at=self._ts(10, 45)),
            _make_msg("desktop", "cli1", "task B", created_at=self._ts(11, 0)),
            _make_msg("desktop", "cli1", "SHUTDOWN: exit", created_at=self._ts(11, 45)),
        ]
        sessions = parse_worker_sessions(msgs, "cli1")
        self.assertEqual(len(sessions), 2)
        self.assertTrue(sessions[0].is_complete)
        self.assertFalse(sessions[1].is_complete)

    def test_shutdown_excluded_from_assignments(self):
        msgs = [
            _make_msg("desktop", "cli1", "SHUTDOWN: exit now"),
        ]
        sessions = parse_worker_sessions(msgs, "cli1")
        # SHUTDOWN alone doesn't create a session with assignments
        self.assertEqual(len(sessions), 0)

    def test_no_messages_for_worker(self):
        msgs = [
            _make_msg("desktop", "cli2", "task A"),
        ]
        sessions = parse_worker_sessions(msgs, "cli1")
        self.assertEqual(sessions, [])

    def test_ignores_non_handoff_messages(self):
        msgs = [
            _make_msg("desktop", "cli1", "task A"),
            _make_msg("cli1", "desktop", "scope_subject", category="scope_claim"),
            _make_msg("cli1", "desktop", "WRAP: task A done"),
            _make_msg("desktop", "cli1", "SHUTDOWN: exit"),
        ]
        sessions = parse_worker_sessions(msgs, "cli1")
        self.assertEqual(sessions[0].assigned_count, 1)
        self.assertEqual(sessions[0].wrap_count, 1)

    def test_wrap_without_assignment_still_counted(self):
        """Edge: worker sends wrap but no desktop assignment tracked."""
        msgs = [
            _make_msg("cli1", "desktop", "WRAP: spontaneous wrap"),
            _make_msg("desktop", "cli1", "SHUTDOWN: exit"),
        ]
        sessions = parse_worker_sessions(msgs, "cli1")
        # Wrap without prior assignment: 0 assigned, 1 wrap — unusual but not incomplete
        self.assertEqual(sessions[0].wrap_count, 1)

    def test_session_records_task_subjects(self):
        msgs = [
            _make_msg("desktop", "cli1", "build feature X"),
            _make_msg("desktop", "cli1", "build feature Y"),
            _make_msg("cli1", "desktop", "WRAP: X done"),
            _make_msg("desktop", "cli1", "SHUTDOWN: exit"),
        ]
        sessions = parse_worker_sessions(msgs, "cli1")
        self.assertIn("build feature X", sessions[0].task_subjects)
        self.assertIn("build feature Y", sessions[0].task_subjects)

    def test_trailing_open_session(self):
        """Session without SHUTDOWN (still running) is captured."""
        msgs = [
            _make_msg("desktop", "cli1", "task A"),
            _make_msg("desktop", "cli1", "task B"),
        ]
        sessions = parse_worker_sessions(msgs, "cli1")
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0].assigned_count, 2)
        self.assertFalse(sessions[0].is_complete)
        self.assertFalse(sessions[0].shutdown_received)


class TestDetectIncompleteSessions(unittest.TestCase):
    def test_no_incomplete_sessions(self):
        msgs = [
            _make_msg("desktop", "cli1", "task A"),
            _make_msg("cli1", "desktop", "WRAP: task A done"),
            _make_msg("desktop", "cli1", "SHUTDOWN: exit"),
        ]
        incomplete = detect_incomplete_sessions(msgs)
        self.assertEqual(incomplete, [])

    def test_detects_incomplete_for_cli1(self):
        msgs = [
            _make_msg("desktop", "cli1", "task A"),
            _make_msg("desktop", "cli1", "task B"),
            _make_msg("cli1", "desktop", "WRAP: task A done"),
            _make_msg("desktop", "cli1", "SHUTDOWN: exit"),
        ]
        incomplete = detect_incomplete_sessions(msgs)
        self.assertEqual(len(incomplete), 1)
        self.assertEqual(incomplete[0].worker_id, "cli1")

    def test_detects_across_multiple_workers(self):
        msgs = [
            _make_msg("desktop", "cli1", "task A"),
            _make_msg("desktop", "cli2", "task B"),
            _make_msg("desktop", "cli1", "SHUTDOWN: exit"),
            _make_msg("desktop", "cli2", "SHUTDOWN: exit"),
        ]
        incomplete = detect_incomplete_sessions(msgs)
        workers = {s.worker_id for s in incomplete}
        self.assertIn("cli1", workers)
        self.assertIn("cli2", workers)

    def test_complete_sessions_not_in_incomplete(self):
        msgs = [
            _make_msg("desktop", "cli1", "task A"),
            _make_msg("cli1", "desktop", "WRAP: task A done"),
            _make_msg("desktop", "cli1", "SHUTDOWN: exit"),
            _make_msg("desktop", "cli2", "task B"),
            _make_msg("desktop", "cli2", "SHUTDOWN: exit"),
        ]
        incomplete = detect_incomplete_sessions(msgs)
        workers = {s.worker_id for s in incomplete}
        self.assertNotIn("cli1", workers)
        self.assertIn("cli2", workers)

    def test_empty_messages_returns_empty(self):
        self.assertEqual(detect_incomplete_sessions([]), [])


class TestReport(unittest.TestCase):
    def test_all_complete_shows_ok(self):
        msgs = [
            _make_msg("desktop", "cli1", "task A"),
            _make_msg("cli1", "desktop", "WRAP: task A done"),
            _make_msg("desktop", "cli1", "SHUTDOWN: exit"),
        ]
        out = report(msgs)
        self.assertIn("OK", out)
        self.assertIn("cli1", out)

    def test_incomplete_shown_in_report(self):
        msgs = [
            _make_msg("desktop", "cli1", "task A"),
            _make_msg("desktop", "cli1", "task B"),
            _make_msg("cli1", "desktop", "WRAP: task A done"),
            _make_msg("desktop", "cli1", "SHUTDOWN: exit"),
        ]
        out = report(msgs)
        self.assertIn("INCOMPLETE", out)
        self.assertIn("cli1", out)
        self.assertIn("task B", out)

    def test_report_shows_assigned_and_wrap_counts(self):
        msgs = [
            _make_msg("desktop", "cli1", "task A"),
            _make_msg("desktop", "cli1", "task B"),
            _make_msg("cli1", "desktop", "WRAP: done"),
            _make_msg("desktop", "cli1", "SHUTDOWN: exit"),
        ]
        out = report(msgs)
        self.assertIn("2", out)  # assigned count
        self.assertIn("1", out)  # wrap count

    def test_empty_queue_report(self):
        out = report([])
        self.assertIn("No sessions", out)


class TestWorkerSession(unittest.TestCase):
    def test_is_complete_true_when_wraps_ge_assigned(self):
        s = WorkerSession("cli1")
        s.assigned_count = 2
        s.wrap_count = 2
        self.assertTrue(s.is_complete)

    def test_is_complete_false_when_wraps_lt_assigned(self):
        s = WorkerSession("cli1")
        s.assigned_count = 2
        s.wrap_count = 1
        self.assertFalse(s.is_complete)

    def test_is_complete_true_with_no_tasks(self):
        s = WorkerSession("cli1")
        s.assigned_count = 0
        s.wrap_count = 0
        self.assertTrue(s.is_complete)

    def test_missing_tasks_list(self):
        s = WorkerSession("cli1")
        s.task_subjects = ["task A", "task B"]
        s.wrap_count = 1
        s.assigned_count = 2
        missing = s.missing_tasks
        # Can't know exactly which tasks are missing without matching
        # but count should be assigned - wraps
        self.assertEqual(len(missing), 1)


if __name__ == "__main__":
    unittest.main()
