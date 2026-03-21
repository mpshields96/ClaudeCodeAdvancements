#!/usr/bin/env python3
"""
test_phase3_validator.py — Tests for phase3_validator.py

Validates 3-chat (desktop + cli1 + cli2) hivemind sessions by analyzing
queue messages for both workers. Extends hivemind_session_validator for
multi-worker scenarios.
"""

import json
import os
import tempfile
import unittest
from datetime import datetime, timezone


def _ts(offset_sec=0):
    """Helper: ISO timestamp with offset."""
    from datetime import timedelta
    dt = datetime(2026, 3, 22, 12, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=offset_sec)
    return dt.isoformat().replace("+00:00", "Z")


def _write_queue(path, messages):
    """Write queue messages to JSONL file."""
    with open(path, "w") as f:
        for m in messages:
            f.write(json.dumps(m) + "\n")


class TestValidate3ChatSession(unittest.TestCase):
    """Test validation of a full 3-chat session."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.queue_path = os.path.join(self.tmpdir, "queue.jsonl")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_full_pass_both_workers(self):
        """Both workers assigned, completed, no conflicts = PASS."""
        import phase3_validator as p3v
        _write_queue(self.queue_path, [
            {"sender": "desktop", "target": "cli1", "category": "handoff", "subject": "task1", "created_at": _ts(0)},
            {"sender": "desktop", "target": "cli2", "category": "handoff", "subject": "task2", "created_at": _ts(1)},
            {"sender": "cli1", "target": "desktop", "category": "scope_claim", "subject": "foo.py", "created_at": _ts(10)},
            {"sender": "cli2", "target": "desktop", "category": "scope_claim", "subject": "bar.py", "created_at": _ts(11)},
            {"sender": "cli1", "target": "desktop", "category": "scope_release", "subject": "foo.py", "created_at": _ts(100)},
            {"sender": "cli2", "target": "desktop", "category": "scope_release", "subject": "bar.py", "created_at": _ts(101)},
            {"sender": "cli1", "target": "desktop", "category": "handoff", "subject": "WRAP: done", "created_at": _ts(200)},
            {"sender": "cli2", "target": "desktop", "category": "handoff", "subject": "WRAP: done", "created_at": _ts(201)},
        ])
        result = p3v.validate_3chat_session(self.queue_path)
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["workers_validated"], 2)
        self.assertEqual(result["inter_worker_conflicts"], 0)

    def test_fail_when_worker_didnt_complete(self):
        """FAIL when one worker was assigned but didn't send WRAP."""
        import phase3_validator as p3v
        _write_queue(self.queue_path, [
            {"sender": "desktop", "target": "cli1", "category": "handoff", "subject": "task1", "created_at": _ts(0)},
            {"sender": "desktop", "target": "cli2", "category": "handoff", "subject": "task2", "created_at": _ts(1)},
            {"sender": "cli1", "target": "desktop", "category": "handoff", "subject": "WRAP: done", "created_at": _ts(200)},
            # cli2 never wrapped
        ])
        result = p3v.validate_3chat_session(self.queue_path)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertIn("cli2", result["incomplete_workers"])

    def test_warning_when_scope_conflict(self):
        """PASS_WITH_WARNINGS when inter-worker conflict detected."""
        import phase3_validator as p3v
        _write_queue(self.queue_path, [
            {"sender": "desktop", "target": "cli1", "category": "handoff", "subject": "task1", "created_at": _ts(0)},
            {"sender": "desktop", "target": "cli2", "category": "handoff", "subject": "task2", "created_at": _ts(1)},
            {"sender": "cli1", "target": "desktop", "category": "scope_claim", "subject": "shared.py", "files": ["shared.py"], "created_at": _ts(10)},
            {"sender": "cli2", "target": "desktop", "category": "scope_claim", "subject": "shared.py", "files": ["shared.py"], "created_at": _ts(11)},
            {"sender": "cli1", "target": "desktop", "category": "scope_release", "subject": "shared.py", "created_at": _ts(100)},
            {"sender": "cli2", "target": "desktop", "category": "scope_release", "subject": "shared.py", "created_at": _ts(101)},
            {"sender": "cli1", "target": "desktop", "category": "handoff", "subject": "WRAP: done", "created_at": _ts(200)},
            {"sender": "cli2", "target": "desktop", "category": "handoff", "subject": "WRAP: done", "created_at": _ts(201)},
        ])
        result = p3v.validate_3chat_session(self.queue_path)
        self.assertEqual(result["verdict"], "PASS_WITH_WARNINGS")
        self.assertEqual(result["inter_worker_conflicts"], 1)

    def test_pass_single_worker_session(self):
        """Single-worker 2-chat session still validates (backward compat)."""
        import phase3_validator as p3v
        _write_queue(self.queue_path, [
            {"sender": "desktop", "target": "cli1", "category": "handoff", "subject": "task1", "created_at": _ts(0)},
            {"sender": "cli1", "target": "desktop", "category": "handoff", "subject": "WRAP: done", "created_at": _ts(200)},
        ])
        result = p3v.validate_3chat_session(self.queue_path)
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["workers_validated"], 1)

    def test_empty_queue_returns_no_data(self):
        """Empty queue file returns NO_DATA verdict."""
        import phase3_validator as p3v
        _write_queue(self.queue_path, [])
        result = p3v.validate_3chat_session(self.queue_path)
        self.assertEqual(result["verdict"], "NO_DATA")

    def test_missing_queue_returns_no_data(self):
        """Missing queue file returns NO_DATA verdict."""
        import phase3_validator as p3v
        result = p3v.validate_3chat_session("/nonexistent/path.jsonl")
        self.assertEqual(result["verdict"], "NO_DATA")


class TestInterWorkerConflictDetection(unittest.TestCase):
    """Test scope conflict detection between cli1 and cli2."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.queue_path = os.path.join(self.tmpdir, "queue.jsonl")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_no_conflict_different_files(self):
        """No conflict when workers claim different files."""
        import phase3_validator as p3v
        _write_queue(self.queue_path, [
            {"sender": "cli1", "target": "desktop", "category": "scope_claim", "subject": "a.py", "files": ["a.py"], "created_at": _ts(0)},
            {"sender": "cli2", "target": "desktop", "category": "scope_claim", "subject": "b.py", "files": ["b.py"], "created_at": _ts(1)},
        ])
        conflicts = p3v.detect_inter_worker_conflicts(self.queue_path)
        self.assertEqual(len(conflicts), 0)

    def test_conflict_same_file(self):
        """Detects conflict when both claim same file simultaneously."""
        import phase3_validator as p3v
        _write_queue(self.queue_path, [
            {"sender": "cli1", "target": "desktop", "category": "scope_claim", "subject": "x.py", "files": ["x.py"], "created_at": _ts(0)},
            {"sender": "cli2", "target": "desktop", "category": "scope_claim", "subject": "x.py", "files": ["x.py"], "created_at": _ts(1)},
        ])
        conflicts = p3v.detect_inter_worker_conflicts(self.queue_path)
        self.assertEqual(len(conflicts), 1)

    def test_no_conflict_if_released_before_second_claim(self):
        """No conflict if first worker released before second claimed."""
        import phase3_validator as p3v
        _write_queue(self.queue_path, [
            {"sender": "cli1", "target": "desktop", "category": "scope_claim", "subject": "x.py", "files": ["x.py"], "created_at": _ts(0)},
            {"sender": "cli1", "target": "desktop", "category": "scope_release", "subject": "x.py", "files": ["x.py"], "created_at": _ts(50)},
            {"sender": "cli2", "target": "desktop", "category": "scope_claim", "subject": "x.py", "files": ["x.py"], "created_at": _ts(60)},
        ])
        conflicts = p3v.detect_inter_worker_conflicts(self.queue_path)
        self.assertEqual(len(conflicts), 0)

    def test_conflict_overlapping_time(self):
        """Detects conflict when scopes overlap in time."""
        import phase3_validator as p3v
        _write_queue(self.queue_path, [
            {"sender": "cli1", "target": "desktop", "category": "scope_claim", "subject": "x.py", "files": ["x.py"], "created_at": _ts(0)},
            {"sender": "cli2", "target": "desktop", "category": "scope_claim", "subject": "x.py", "files": ["x.py"], "created_at": _ts(10)},
            {"sender": "cli1", "target": "desktop", "category": "scope_release", "subject": "x.py", "files": ["x.py"], "created_at": _ts(50)},
            {"sender": "cli2", "target": "desktop", "category": "scope_release", "subject": "x.py", "files": ["x.py"], "created_at": _ts(60)},
        ])
        conflicts = p3v.detect_inter_worker_conflicts(self.queue_path)
        self.assertEqual(len(conflicts), 1)


class TestWorkerActivitySummary(unittest.TestCase):
    """Test per-worker activity summary from queue messages."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.queue_path = os.path.join(self.tmpdir, "queue.jsonl")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_summary_counts_messages(self):
        """Summary includes message counts per worker."""
        import phase3_validator as p3v
        _write_queue(self.queue_path, [
            {"sender": "desktop", "target": "cli1", "category": "handoff", "subject": "task1", "created_at": _ts(0)},
            {"sender": "desktop", "target": "cli2", "category": "handoff", "subject": "task2", "created_at": _ts(1)},
            {"sender": "cli1", "target": "desktop", "category": "handoff", "subject": "WRAP", "created_at": _ts(100)},
            {"sender": "cli2", "target": "desktop", "category": "handoff", "subject": "WRAP", "created_at": _ts(101)},
            {"sender": "cli1", "target": "desktop", "category": "chat", "subject": "question", "created_at": _ts(50)},
        ])
        summary = p3v.worker_activity_summary(self.queue_path)
        self.assertEqual(summary["cli1"]["messages_sent"], 2)
        self.assertEqual(summary["cli2"]["messages_sent"], 1)
        self.assertTrue(summary["cli1"]["completed"])
        self.assertTrue(summary["cli2"]["completed"])

    def test_summary_detects_incomplete(self):
        """Summary marks workers that didn't send WRAP as incomplete."""
        import phase3_validator as p3v
        _write_queue(self.queue_path, [
            {"sender": "desktop", "target": "cli1", "category": "handoff", "subject": "task1", "created_at": _ts(0)},
            {"sender": "cli1", "target": "desktop", "category": "chat", "subject": "help", "created_at": _ts(50)},
        ])
        summary = p3v.worker_activity_summary(self.queue_path)
        self.assertFalse(summary["cli1"]["completed"])

    def test_summary_empty_queue(self):
        """Empty queue returns empty summary."""
        import phase3_validator as p3v
        _write_queue(self.queue_path, [])
        summary = p3v.worker_activity_summary(self.queue_path)
        self.assertEqual(len(summary), 0)


class TestSessionRecord(unittest.TestCase):
    """Test recording 3-chat session results."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.log_path = os.path.join(self.tmpdir, "phase3_sessions.jsonl")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_record_and_read(self):
        """Can record a session and read it back."""
        import phase3_validator as p3v
        result = {
            "verdict": "PASS",
            "workers_validated": 2,
            "inter_worker_conflicts": 0,
            "incomplete_workers": [],
        }
        p3v.record_session(100, result, path=self.log_path)
        history = p3v.get_history(self.log_path)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["session"], 100)
        self.assertEqual(history[0]["verdict"], "PASS")

    def test_record_multiple_sessions(self):
        """Multiple sessions append correctly."""
        import phase3_validator as p3v
        for i in range(5):
            p3v.record_session(100 + i, {"verdict": "PASS", "workers_validated": 2}, path=self.log_path)
        history = p3v.get_history(self.log_path)
        self.assertEqual(len(history), 5)

    def test_format_for_init(self):
        """Init briefing includes session count."""
        import phase3_validator as p3v
        p3v.record_session(100, {"verdict": "PASS", "workers_validated": 2}, path=self.log_path)
        p3v.record_session(101, {"verdict": "PASS", "workers_validated": 2}, path=self.log_path)
        brief = p3v.format_for_init(self.log_path)
        self.assertIn("2", brief)
        self.assertIn("PASS", brief)

    def test_format_no_sessions(self):
        """Init briefing shows no data message."""
        import phase3_validator as p3v
        brief = p3v.format_for_init(self.log_path)
        self.assertIn("No Phase 3", brief)


if __name__ == "__main__":
    unittest.main()
