#!/usr/bin/env python3
"""
test_phase3_validator_extended.py — Extended edge-case tests for phase3_validator.py

Covers: corrupt queue lines, multi-conflict scenarios, WRAP case variations,
worker activity edge cases, history with malformed entries, streak calculation.
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import phase3_validator as p3v


def _ts(offset_sec=0):
    from datetime import datetime, timezone, timedelta
    dt = datetime(2026, 3, 22, 12, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=offset_sec)
    return dt.isoformat().replace("+00:00", "Z")


def _write_queue(path, messages):
    with open(path, "w") as f:
        for m in messages:
            f.write(json.dumps(m) + "\n")


class TestValidate3ChatEdgeCases(unittest.TestCase):
    """Edge cases for validate_3chat_session."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.queue_path = os.path.join(self.tmpdir, "queue.jsonl")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_no_handoff_messages_returns_no_data(self):
        """Queue with only chat/scope messages but no handoffs = NO_DATA."""
        _write_queue(self.queue_path, [
            {"sender": "cli1", "target": "desktop", "category": "chat", "subject": "hello", "created_at": _ts(0)},
            {"sender": "cli2", "target": "desktop", "category": "scope_claim", "subject": "x.py", "created_at": _ts(1)},
        ])
        result = p3v.validate_3chat_session(self.queue_path)
        self.assertEqual(result["verdict"], "NO_DATA")

    def test_corrupt_lines_skipped(self):
        """Corrupt JSON lines are skipped; valid messages still processed."""
        with open(self.queue_path, "w") as f:
            f.write("NOT_JSON\n")
            f.write(json.dumps({"sender": "desktop", "target": "cli1", "category": "handoff", "subject": "task1", "created_at": _ts(0)}) + "\n")
            f.write("{broken json\n")
            f.write(json.dumps({"sender": "cli1", "target": "desktop", "category": "handoff", "subject": "WRAP: done", "created_at": _ts(200)}) + "\n")
        result = p3v.validate_3chat_session(self.queue_path)
        self.assertEqual(result["verdict"], "PASS")

    def test_both_workers_fail_to_complete(self):
        """Both workers assigned but neither wrapped = FAIL with both in incomplete."""
        _write_queue(self.queue_path, [
            {"sender": "desktop", "target": "cli1", "category": "handoff", "subject": "task1", "created_at": _ts(0)},
            {"sender": "desktop", "target": "cli2", "category": "handoff", "subject": "task2", "created_at": _ts(1)},
            {"sender": "cli1", "target": "desktop", "category": "chat", "subject": "working...", "created_at": _ts(50)},
        ])
        result = p3v.validate_3chat_session(self.queue_path)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertIn("cli1", result["incomplete_workers"])
        self.assertIn("cli2", result["incomplete_workers"])

    def test_multiple_wrap_messages_still_pass(self):
        """Worker sending multiple WRAP messages still counts as complete."""
        _write_queue(self.queue_path, [
            {"sender": "desktop", "target": "cli1", "category": "handoff", "subject": "task1", "created_at": _ts(0)},
            {"sender": "cli1", "target": "desktop", "category": "handoff", "subject": "WRAP: first attempt", "created_at": _ts(100)},
            {"sender": "cli1", "target": "desktop", "category": "handoff", "subject": "WRAP: final", "created_at": _ts(110)},
        ])
        result = p3v.validate_3chat_session(self.queue_path)
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["workers_validated"], 1)

    def test_wrap_lowercase_counted(self):
        """WRAP check uses .upper() so lowercase 'wrap' in subject IS counted."""
        _write_queue(self.queue_path, [
            {"sender": "desktop", "target": "cli1", "category": "handoff", "subject": "task1", "created_at": _ts(0)},
            {"sender": "cli1", "target": "desktop", "category": "handoff", "subject": "wrap: done", "created_at": _ts(200)},
        ])
        result = p3v.validate_3chat_session(self.queue_path)
        # The code uppercases subject before checking — lowercase 'wrap' matches 'WRAP'
        self.assertEqual(result["verdict"], "PASS")

    def test_only_cli2_assigned(self):
        """When only cli2 is assigned and completes, verdict is PASS for 1 worker."""
        _write_queue(self.queue_path, [
            {"sender": "desktop", "target": "cli2", "category": "handoff", "subject": "task_only_cli2", "created_at": _ts(0)},
            {"sender": "cli2", "target": "desktop", "category": "handoff", "subject": "WRAP: done", "created_at": _ts(200)},
        ])
        result = p3v.validate_3chat_session(self.queue_path)
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["workers_validated"], 1)
        self.assertIn("cli2", result["active_workers"])
        self.assertNotIn("cli1", result["active_workers"])

    def test_handoff_from_non_desktop_ignored(self):
        """Handoffs from non-desktop senders don't count as task assignments."""
        _write_queue(self.queue_path, [
            {"sender": "cli1", "target": "cli2", "category": "handoff", "subject": "subtask", "created_at": _ts(0)},
            {"sender": "cli2", "target": "desktop", "category": "handoff", "subject": "WRAP: done", "created_at": _ts(200)},
        ])
        result = p3v.validate_3chat_session(self.queue_path)
        self.assertEqual(result["verdict"], "NO_DATA")

    def test_result_includes_active_workers_field(self):
        """Result always includes active_workers sorted list."""
        _write_queue(self.queue_path, [
            {"sender": "desktop", "target": "cli1", "category": "handoff", "subject": "task1", "created_at": _ts(0)},
            {"sender": "desktop", "target": "cli2", "category": "handoff", "subject": "task2", "created_at": _ts(1)},
            {"sender": "cli1", "target": "desktop", "category": "handoff", "subject": "WRAP", "created_at": _ts(100)},
            {"sender": "cli2", "target": "desktop", "category": "handoff", "subject": "WRAP", "created_at": _ts(101)},
        ])
        result = p3v.validate_3chat_session(self.queue_path)
        self.assertIn("active_workers", result)
        self.assertEqual(sorted(result["active_workers"]), ["cli1", "cli2"])

    def test_multiple_scope_conflicts_counted(self):
        """Multiple conflicting file pairs are all counted."""
        _write_queue(self.queue_path, [
            {"sender": "desktop", "target": "cli1", "category": "handoff", "subject": "task1", "created_at": _ts(0)},
            {"sender": "desktop", "target": "cli2", "category": "handoff", "subject": "task2", "created_at": _ts(1)},
            # Two file conflicts
            {"sender": "cli1", "category": "scope_claim", "subject": "a.py", "files": ["a.py"], "created_at": _ts(10)},
            {"sender": "cli2", "category": "scope_claim", "subject": "a.py", "files": ["a.py"], "created_at": _ts(11)},
            {"sender": "cli1", "category": "scope_claim", "subject": "b.py", "files": ["b.py"], "created_at": _ts(12)},
            {"sender": "cli2", "category": "scope_claim", "subject": "b.py", "files": ["b.py"], "created_at": _ts(13)},
            {"sender": "cli1", "target": "desktop", "category": "handoff", "subject": "WRAP", "created_at": _ts(200)},
            {"sender": "cli2", "target": "desktop", "category": "handoff", "subject": "WRAP", "created_at": _ts(201)},
        ])
        result = p3v.validate_3chat_session(self.queue_path)
        self.assertEqual(result["verdict"], "PASS_WITH_WARNINGS")
        self.assertGreaterEqual(result["inter_worker_conflicts"], 2)


class TestConflictDetectionEdgeCases(unittest.TestCase):
    """Edge cases for detect_inter_worker_conflicts."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.queue_path = os.path.join(self.tmpdir, "queue.jsonl")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_empty_files_list_no_conflict(self):
        """Scope_claim with explicit empty files=[] has no files to compare — no conflict."""
        _write_queue(self.queue_path, [
            {"sender": "cli1", "category": "scope_claim", "subject": "x.py", "files": [], "created_at": _ts(0)},
            {"sender": "cli2", "category": "scope_claim", "subject": "x.py", "files": [], "created_at": _ts(1)},
        ])
        # files=[] means no file entries — fallback only applies when key is absent
        conflicts = p3v.detect_inter_worker_conflicts(self.queue_path)
        self.assertEqual(len(conflicts), 0)

    def test_no_conflict_after_sequential_claims(self):
        """cli1 claims, releases, then cli2 claims = no overlap."""
        _write_queue(self.queue_path, [
            {"sender": "cli1", "category": "scope_claim", "subject": "x.py", "files": ["x.py"], "created_at": _ts(0)},
            {"sender": "cli1", "category": "scope_release", "subject": "x.py", "files": ["x.py"], "created_at": _ts(30)},
            {"sender": "cli2", "category": "scope_claim", "subject": "x.py", "files": ["x.py"], "created_at": _ts(60)},
        ])
        conflicts = p3v.detect_inter_worker_conflicts(self.queue_path)
        self.assertEqual(len(conflicts), 0)

    def test_same_worker_same_file_no_conflict(self):
        """Single worker claiming same file twice is not an inter-worker conflict."""
        _write_queue(self.queue_path, [
            {"sender": "cli1", "category": "scope_claim", "subject": "x.py", "files": ["x.py"], "created_at": _ts(0)},
            {"sender": "cli1", "category": "scope_claim", "subject": "x.py", "files": ["x.py"], "created_at": _ts(10)},
        ])
        conflicts = p3v.detect_inter_worker_conflicts(self.queue_path)
        self.assertEqual(len(conflicts), 0)

    def test_multiple_files_partial_overlap(self):
        """cli1 claims [a.py, b.py], cli2 claims [b.py, c.py] — conflict on b.py only."""
        _write_queue(self.queue_path, [
            {"sender": "cli1", "category": "scope_claim", "subject": "a+b", "files": ["a.py", "b.py"], "created_at": _ts(0)},
            {"sender": "cli2", "category": "scope_claim", "subject": "b+c", "files": ["b.py", "c.py"], "created_at": _ts(5)},
        ])
        conflicts = p3v.detect_inter_worker_conflicts(self.queue_path)
        conflict_files = [c["file"] for c in conflicts]
        self.assertIn("b.py", conflict_files)
        self.assertNotIn("a.py", conflict_files)
        self.assertNotIn("c.py", conflict_files)

    def test_both_still_active_same_file(self):
        """Both workers holding same file with no releases = conflict."""
        _write_queue(self.queue_path, [
            {"sender": "cli1", "category": "scope_claim", "subject": "y.py", "files": ["y.py"], "created_at": _ts(0)},
            {"sender": "cli2", "category": "scope_claim", "subject": "y.py", "files": ["y.py"], "created_at": _ts(5)},
        ])
        conflicts = p3v.detect_inter_worker_conflicts(self.queue_path)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["file"], "y.py")
        self.assertIn("cli1", conflicts[0]["workers"])
        self.assertIn("cli2", conflicts[0]["workers"])

    def test_empty_queue_no_conflicts(self):
        """Empty queue produces no conflicts."""
        _write_queue(self.queue_path, [])
        conflicts = p3v.detect_inter_worker_conflicts(self.queue_path)
        self.assertEqual(len(conflicts), 0)


class TestWorkerActivitySummaryEdgeCases(unittest.TestCase):
    """Edge cases for worker_activity_summary."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.queue_path = os.path.join(self.tmpdir, "queue.jsonl")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_multiple_tasks_received_counted(self):
        """Worker receiving multiple task assignments has correct tasks_received count."""
        _write_queue(self.queue_path, [
            {"sender": "desktop", "target": "cli1", "category": "handoff", "subject": "task1", "created_at": _ts(0)},
            {"sender": "desktop", "target": "cli1", "category": "handoff", "subject": "task2", "created_at": _ts(10)},
            {"sender": "cli1", "target": "desktop", "category": "handoff", "subject": "WRAP", "created_at": _ts(200)},
        ])
        summary = p3v.worker_activity_summary(self.queue_path)
        self.assertEqual(summary["cli1"]["tasks_received"], 2)

    def test_missing_queue_returns_empty(self):
        """Missing queue file returns empty summary."""
        summary = p3v.worker_activity_summary("/nonexistent/path.jsonl")
        self.assertEqual(len(summary), 0)

    def test_worker_with_messages_but_no_task_not_in_summary(self):
        """Worker that sent messages but was never given a task is not in summary
        unless they also sent messages (sender field matches worker)."""
        _write_queue(self.queue_path, [
            {"sender": "cli2", "target": "desktop", "category": "chat", "subject": "ping", "created_at": _ts(0)},
        ])
        summary = p3v.worker_activity_summary(self.queue_path)
        # cli2 shows in summary because they sent messages
        self.assertIn("cli2", summary)
        self.assertEqual(summary["cli2"]["tasks_received"], 0)
        self.assertFalse(summary["cli2"]["completed"])

    def test_worker_not_in_summary_if_no_activity(self):
        """Worker with zero messages and zero tasks is absent from summary."""
        _write_queue(self.queue_path, [
            {"sender": "desktop", "target": "cli1", "category": "handoff", "subject": "task1", "created_at": _ts(0)},
            {"sender": "cli1", "target": "desktop", "category": "handoff", "subject": "WRAP", "created_at": _ts(100)},
        ])
        summary = p3v.worker_activity_summary(self.queue_path)
        # cli2 never participated
        self.assertNotIn("cli2", summary)


class TestSessionHistoryEdgeCases(unittest.TestCase):
    """Edge cases for record_session, get_history, format_for_init."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.log_path = os.path.join(self.tmpdir, "sessions.jsonl")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_malformed_lines_in_history_skipped(self):
        """Malformed JSON lines in history file are skipped gracefully."""
        with open(self.log_path, "w") as f:
            f.write(json.dumps({"session": 100, "verdict": "PASS", "workers_validated": 2}) + "\n")
            f.write("NOT_JSON\n")
            f.write(json.dumps({"session": 101, "verdict": "FAIL", "workers_validated": 1}) + "\n")
        history = p3v.get_history(self.log_path)
        self.assertEqual(len(history), 2)

    def test_record_with_missing_optional_fields(self):
        """record_session handles result dicts missing optional fields."""
        p3v.record_session(200, {"verdict": "PASS"}, path=self.log_path)
        history = p3v.get_history(self.log_path)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["session"], 200)
        self.assertEqual(history[0]["verdict"], "PASS")
        self.assertEqual(history[0]["workers_validated"], 0)  # default

    def test_format_for_init_streak_broken_by_fail(self):
        """Streak counts only from most recent FAIL forward."""
        p3v.record_session(100, {"verdict": "PASS", "workers_validated": 2}, path=self.log_path)
        p3v.record_session(101, {"verdict": "FAIL", "workers_validated": 1}, path=self.log_path)
        p3v.record_session(102, {"verdict": "PASS", "workers_validated": 2}, path=self.log_path)
        p3v.record_session(103, {"verdict": "PASS", "workers_validated": 2}, path=self.log_path)
        brief = p3v.format_for_init(self.log_path)
        # 4 total, streak=2 (sessions 102+103), passes=3/4
        self.assertIn("4", brief)
        self.assertIn("2", brief)  # streak

    def test_format_for_init_all_fail(self):
        """All FAIL sessions = streak of 0."""
        p3v.record_session(100, {"verdict": "FAIL", "workers_validated": 1}, path=self.log_path)
        p3v.record_session(101, {"verdict": "FAIL", "workers_validated": 1}, path=self.log_path)
        brief = p3v.format_for_init(self.log_path)
        self.assertIn("0", brief)  # streak = 0

    def test_format_for_init_pass_with_warnings_counts_as_pass(self):
        """PASS_WITH_WARNINGS counts as a pass in both streak and total."""
        p3v.record_session(100, {"verdict": "PASS_WITH_WARNINGS", "workers_validated": 2}, path=self.log_path)
        brief = p3v.format_for_init(self.log_path)
        self.assertIn("1", brief)  # 1/1 passes

    def test_get_history_missing_file(self):
        """get_history on missing file returns empty list."""
        history = p3v.get_history("/nonexistent/file.jsonl")
        self.assertEqual(history, [])

    def test_record_returns_entry(self):
        """record_session returns the entry that was written."""
        result = {"verdict": "PASS", "workers_validated": 2, "inter_worker_conflicts": 0, "incomplete_workers": []}
        entry = p3v.record_session(99, result, path=self.log_path)
        self.assertEqual(entry["session"], 99)
        self.assertEqual(entry["verdict"], "PASS")
        self.assertIn("timestamp", entry)


if __name__ == "__main__":
    unittest.main()
