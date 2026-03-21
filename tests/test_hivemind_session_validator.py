#!/usr/bin/env python3
"""
Tests for hivemind_session_validator.py — Desktop-side validation
that a hivemind session completed successfully.

TDD: Write tests first, then implementation.
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, ROOT_DIR)

import hivemind_session_validator as hsv


class TestValidateSession(unittest.TestCase):
    """Test the core validate_session function."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.queue_path = os.path.join(self.tmpdir, "queue.jsonl")
        self.log_path = os.path.join(self.tmpdir, "hivemind_sessions.jsonl")

    def _write_queue(self, messages):
        with open(self.queue_path, "w") as f:
            for msg in messages:
                f.write(json.dumps(msg) + "\n")

    def test_clean_session_passes(self):
        """A session with task assigned, completed, no conflicts = PASS."""
        messages = [
            {"sender": "desktop", "target": "cli1", "category": "handoff",
             "subject": "Build feature X", "priority": "high", "status": "read",
             "created_at": "2026-03-20T10:00:00Z", "read_at": "2026-03-20T10:01:00Z"},
            {"sender": "cli1", "target": "desktop", "category": "scope_claim",
             "subject": "feature_x", "priority": "high", "status": "unread",
             "created_at": "2026-03-20T10:01:30Z"},
            {"sender": "cli1", "target": "desktop", "category": "handoff",
             "subject": "WRAP: A — Built feature X. Tests: 15 new.", "priority": "high",
             "status": "unread", "created_at": "2026-03-20T10:30:00Z"},
            {"sender": "cli1", "target": "desktop", "category": "scope_release",
             "subject": "feature_x", "priority": "medium", "status": "unread",
             "created_at": "2026-03-20T10:30:05Z"},
        ]
        self._write_queue(messages)
        result = hsv.validate_session("cli1", queue_path=self.queue_path)
        self.assertEqual(result["verdict"], "PASS")
        self.assertTrue(result["task_assigned"])
        self.assertTrue(result["task_completed"])
        self.assertFalse(result["conflicts"])
        self.assertTrue(result["scope_released"])

    def test_no_task_assigned_fails(self):
        """If no handoff message from desktop to worker, FAIL."""
        self._write_queue([])
        result = hsv.validate_session("cli1", queue_path=self.queue_path)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertFalse(result["task_assigned"])

    def test_task_assigned_but_not_completed_fails(self):
        """Task assigned but no WRAP message back = FAIL."""
        messages = [
            {"sender": "desktop", "target": "cli1", "category": "handoff",
             "subject": "Build feature X", "priority": "high", "status": "read",
             "created_at": "2026-03-20T10:00:00Z", "read_at": "2026-03-20T10:01:00Z"},
        ]
        self._write_queue(messages)
        result = hsv.validate_session("cli1", queue_path=self.queue_path)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertTrue(result["task_assigned"])
        self.assertFalse(result["task_completed"])

    def test_conflict_alert_marks_conflict(self):
        """Conflict alerts should be flagged."""
        messages = [
            {"sender": "desktop", "target": "cli1", "category": "handoff",
             "subject": "Build feature X", "priority": "high", "status": "read",
             "created_at": "2026-03-20T10:00:00Z", "read_at": "2026-03-20T10:01:00Z"},
            {"sender": "cli1", "target": "desktop", "category": "conflict_alert",
             "subject": "Modified shared file", "priority": "high", "status": "unread",
             "created_at": "2026-03-20T10:15:00Z"},
            {"sender": "cli1", "target": "desktop", "category": "handoff",
             "subject": "WRAP: B — Built feature X with conflict.", "priority": "high",
             "status": "unread", "created_at": "2026-03-20T10:30:00Z"},
        ]
        self._write_queue(messages)
        result = hsv.validate_session("cli1", queue_path=self.queue_path)
        self.assertEqual(result["verdict"], "PASS_WITH_WARNINGS")
        self.assertTrue(result["conflicts"])

    def test_scope_not_released_warns(self):
        """If scope was claimed but not released, warn."""
        messages = [
            {"sender": "desktop", "target": "cli1", "category": "handoff",
             "subject": "Build feature X", "priority": "high", "status": "read",
             "created_at": "2026-03-20T10:00:00Z", "read_at": "2026-03-20T10:01:00Z"},
            {"sender": "cli1", "target": "desktop", "category": "scope_claim",
             "subject": "feature_x", "priority": "high", "status": "unread",
             "created_at": "2026-03-20T10:01:30Z"},
            {"sender": "cli1", "target": "desktop", "category": "handoff",
             "subject": "WRAP: A — Built feature X.", "priority": "high",
             "status": "unread", "created_at": "2026-03-20T10:30:00Z"},
        ]
        self._write_queue(messages)
        result = hsv.validate_session("cli1", queue_path=self.queue_path)
        self.assertEqual(result["verdict"], "PASS_WITH_WARNINGS")
        self.assertFalse(result["scope_released"])


class TestRecordSession(unittest.TestCase):
    """Test persisting session validation results."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.log_path = os.path.join(self.tmpdir, "hivemind_sessions.jsonl")

    def test_record_creates_file(self):
        result = {
            "verdict": "PASS", "task_assigned": True, "task_completed": True,
            "conflicts": False, "scope_released": True, "worker_id": "cli1",
        }
        hsv.record_session(90, result, path=self.log_path)
        self.assertTrue(os.path.exists(self.log_path))

    def test_record_appends(self):
        r1 = {"verdict": "PASS", "worker_id": "cli1"}
        r2 = {"verdict": "FAIL", "worker_id": "cli1"}
        hsv.record_session(90, r1, path=self.log_path)
        hsv.record_session(91, r2, path=self.log_path)
        with open(self.log_path) as f:
            lines = [l for l in f if l.strip()]
        self.assertEqual(len(lines), 2)

    def test_record_includes_session_and_timestamp(self):
        result = {"verdict": "PASS", "worker_id": "cli1"}
        hsv.record_session(90, result, path=self.log_path)
        with open(self.log_path) as f:
            entry = json.loads(f.readline())
        self.assertEqual(entry["session"], 90)
        self.assertIn("timestamp", entry)
        self.assertEqual(entry["verdict"], "PASS")


class TestGetHistory(unittest.TestCase):
    """Test reading session validation history."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.log_path = os.path.join(self.tmpdir, "hivemind_sessions.jsonl")

    def test_empty_history(self):
        history = hsv.get_history(path=self.log_path)
        self.assertEqual(history, [])

    def test_returns_all_entries(self):
        for i in range(3):
            hsv.record_session(90 + i, {"verdict": "PASS", "worker_id": "cli1"}, path=self.log_path)
        history = hsv.get_history(path=self.log_path)
        self.assertEqual(len(history), 3)

    def test_consecutive_passes_count(self):
        """Count consecutive PASS results for Phase 1 gate check."""
        hsv.record_session(88, {"verdict": "FAIL", "worker_id": "cli1"}, path=self.log_path)
        hsv.record_session(89, {"verdict": "PASS", "worker_id": "cli1"}, path=self.log_path)
        hsv.record_session(90, {"verdict": "PASS", "worker_id": "cli1"}, path=self.log_path)
        hsv.record_session(91, {"verdict": "PASS", "worker_id": "cli1"}, path=self.log_path)
        streak = hsv.consecutive_passes(path=self.log_path)
        self.assertEqual(streak, 3)


class TestFormatForInit(unittest.TestCase):
    """Test one-line briefing for /cca-init."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.log_path = os.path.join(self.tmpdir, "hivemind_sessions.jsonl")

    def test_no_history(self):
        line = hsv.format_for_init(path=self.log_path)
        self.assertIn("No hivemind sessions recorded", line)

    def test_with_history(self):
        hsv.record_session(90, {"verdict": "PASS", "worker_id": "cli1"}, path=self.log_path)
        hsv.record_session(91, {"verdict": "PASS", "worker_id": "cli1"}, path=self.log_path)
        line = hsv.format_for_init(path=self.log_path)
        self.assertIn("2 sessions", line)
        self.assertIn("2 consecutive", line)

    def test_phase1_gate_check(self):
        """When 3+ consecutive passes, format should mention Phase 1 gate."""
        for i in range(3):
            hsv.record_session(90 + i, {"verdict": "PASS", "worker_id": "cli1"}, path=self.log_path)
        line = hsv.format_for_init(path=self.log_path)
        self.assertIn("Phase 1: PASSED", line)


class TestCheckPhaseGate(unittest.TestCase):
    """Test Phase 1 readiness check."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.log_path = os.path.join(self.tmpdir, "hivemind_sessions.jsonl")

    def test_not_ready_with_zero_sessions(self):
        gate = hsv.check_phase1_gate(path=self.log_path)
        self.assertFalse(gate["ready"])

    def test_not_ready_with_failures(self):
        hsv.record_session(90, {"verdict": "PASS", "worker_id": "cli1"}, path=self.log_path)
        hsv.record_session(91, {"verdict": "FAIL", "worker_id": "cli1"}, path=self.log_path)
        hsv.record_session(92, {"verdict": "PASS", "worker_id": "cli1"}, path=self.log_path)
        gate = hsv.check_phase1_gate(path=self.log_path)
        self.assertFalse(gate["ready"])
        self.assertEqual(gate["consecutive_passes"], 1)

    def test_ready_with_3_consecutive_passes(self):
        for i in range(3):
            hsv.record_session(90 + i, {"verdict": "PASS", "worker_id": "cli1"}, path=self.log_path)
        gate = hsv.check_phase1_gate(path=self.log_path)
        self.assertTrue(gate["ready"])
        self.assertEqual(gate["consecutive_passes"], 3)
        self.assertEqual(gate["total_sessions"], 3)


if __name__ == "__main__":
    unittest.main()
