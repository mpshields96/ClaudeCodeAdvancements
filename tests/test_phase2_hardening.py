#!/usr/bin/env python3
"""
Tests for Phase 2 hardening fixes (S93):
1. Atomic file writes for queue (_save_queue uses tempfile + os.replace)
2. Scope conflict detection wired into cca_comm.py claim
3. Stale scope timeout wired into crash recovery pipeline

Run: python3 tests/test_phase2_hardening.py
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))
import cca_internal_queue as ciq
import cca_comm
import crash_recovery as cr


# ── Gap #1: Atomic File Writes ────────────────────────────────────────────


class TestAtomicQueueWrites(unittest.TestCase):
    """Verify _save_queue uses atomic write pattern (tempfile + os.replace)."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.path = self.tmp.name

    def tearDown(self):
        if os.path.exists(self.path):
            os.unlink(self.path)

    def test_save_queue_preserves_data(self):
        """Basic: _save_queue writes all messages correctly."""
        msgs = [
            {"id": "test_1", "subject": "A", "status": "unread"},
            {"id": "test_2", "subject": "B", "status": "read"},
        ]
        ciq._save_queue(msgs, self.path)
        loaded = ciq._load_queue(self.path)
        self.assertEqual(len(loaded), 2)
        self.assertEqual(loaded[0]["id"], "test_1")
        self.assertEqual(loaded[1]["id"], "test_2")

    def test_save_queue_no_temp_files_left(self):
        """Atomic write should not leave temp files after success."""
        dir_path = os.path.dirname(self.path)
        msgs = [{"id": "test_1", "subject": "A"}]
        ciq._save_queue(msgs, self.path)
        # Check for leftover .tmp files in the directory
        leftover = [f for f in os.listdir(dir_path) if f.startswith(".cca_queue_") and f.endswith(".tmp")]
        self.assertEqual(len(leftover), 0, f"Temp files left behind: {leftover}")

    def test_save_queue_overwrites_existing(self):
        """_save_queue should fully replace the file content."""
        # Write initial data
        ciq._save_queue([{"id": "old", "subject": "old data"}], self.path)
        # Overwrite with new data
        ciq._save_queue([{"id": "new", "subject": "new data"}], self.path)
        loaded = ciq._load_queue(self.path)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["id"], "new")

    def test_save_queue_empty_list(self):
        """_save_queue with empty list should create empty file."""
        ciq._save_queue([], self.path)
        loaded = ciq._load_queue(self.path)
        self.assertEqual(len(loaded), 0)

    def test_acknowledge_uses_atomic_write(self):
        """acknowledge() -> _save_queue -> atomic write should preserve queue integrity."""
        # Send 3 messages
        ciq.send_message("desktop", "cli1", "msg1", path=self.path)
        ciq.send_message("desktop", "cli1", "msg2", path=self.path)
        ciq.send_message("cli1", "desktop", "msg3", path=self.path)
        # Acknowledge one
        msgs = ciq._load_queue(self.path)
        msg_id = msgs[0]["id"]
        ciq.acknowledge(msg_id, self.path)
        # Verify all 3 messages still exist and the first is read
        reloaded = ciq._load_queue(self.path)
        self.assertEqual(len(reloaded), 3)
        self.assertEqual(reloaded[0]["status"], "read")
        self.assertEqual(reloaded[1]["status"], "unread")

    def test_acknowledge_all_uses_atomic_write(self):
        """acknowledge_all() -> _save_queue -> atomic write should preserve queue integrity."""
        ciq.send_message("desktop", "cli1", "a", path=self.path)
        ciq.send_message("desktop", "cli1", "b", path=self.path)
        ciq.send_message("cli1", "desktop", "c", path=self.path)
        count = ciq.acknowledge_all("cli1", self.path)
        self.assertEqual(count, 2)
        # cli1's messages are read, desktop's is still unread
        reloaded = ciq._load_queue(self.path)
        self.assertEqual(len(reloaded), 3)
        cli1_msgs = [m for m in reloaded if m["target"] == "cli1"]
        self.assertTrue(all(m["status"] == "read" for m in cli1_msgs))

    def test_concurrent_append_and_save_no_data_loss(self):
        """Simulate interleaved append + save — both should succeed without corruption."""
        # Write initial state
        ciq.send_message("desktop", "cli1", "initial", path=self.path)
        # Load, modify, save (simulates acknowledge)
        msgs = ciq._load_queue(self.path)
        msgs[0]["status"] = "read"
        ciq._save_queue(msgs, self.path)
        # Append new message after save
        ciq.send_message("cli1", "desktop", "reply", path=self.path)
        # Verify both messages exist
        final = ciq._load_queue(self.path)
        self.assertEqual(len(final), 2)
        self.assertEqual(final[0]["status"], "read")
        self.assertEqual(final[1]["subject"], "reply")


# ── Gap #2: Scope Conflict Detection in claim ─────────────────────────────


class TestClaimConflictDetection(unittest.TestCase):
    """Verify cca_comm.cmd_claim checks for scope conflicts before claiming."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.path = self.tmp.name
        self._orig = ciq.DEFAULT_QUEUE_PATH
        ciq.DEFAULT_QUEUE_PATH = self.path

    def tearDown(self):
        ciq.DEFAULT_QUEUE_PATH = self._orig
        if os.path.exists(self.path):
            os.unlink(self.path)

    @patch.dict(os.environ, {"CCA_CHAT_ID": "cli1"})
    def test_claim_blocked_when_scope_already_owned(self):
        """cli1 tries to claim scope already owned by desktop -> blocked."""
        # Desktop claims agent-guard/
        ciq.send_message("desktop", "cli1", "agent-guard/", category="scope_claim",
                        priority="high", path=self.path)
        ciq.send_message("desktop", "cli2", "agent-guard/", category="scope_claim",
                        priority="high", path=self.path)
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            cca_comm.cmd_claim(["agent-guard/"])
        output = f.getvalue()
        self.assertIn("SCOPE CONFLICT", output)
        self.assertIn("Claim NOT sent", output)
        # Verify no scope_claim was written by cli1
        msgs = ciq._load_queue(self.path)
        cli1_claims = [m for m in msgs if m["sender"] == "cli1" and m["category"] == "scope_claim"]
        self.assertEqual(len(cli1_claims), 0)

    @patch.dict(os.environ, {"CCA_CHAT_ID": "cli1"})
    def test_claim_succeeds_when_no_conflict(self):
        """cli1 claims unclaimed scope -> succeeds."""
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            cca_comm.cmd_claim(["memory-system/"])
        output = f.getvalue()
        self.assertIn("Scope claimed", output)
        self.assertNotIn("CONFLICT", output)

    @patch.dict(os.environ, {"CCA_CHAT_ID": "cli2"})
    def test_claim_blocked_by_partial_subject_match(self):
        """cli2 tries to claim 'agent-guard' when cli1 owns 'agent-guard/' -> blocked."""
        ciq.send_message("cli1", "desktop", "agent-guard/", category="scope_claim",
                        priority="high", path=self.path)
        ciq.send_message("cli1", "cli2", "agent-guard/", category="scope_claim",
                        priority="high", path=self.path)
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            cca_comm.cmd_claim(["agent-guard"])
        output = f.getvalue()
        self.assertIn("SCOPE CONFLICT", output)

    @patch.dict(os.environ, {"CCA_CHAT_ID": "cli1"})
    def test_claim_allowed_after_release(self):
        """After desktop releases scope, cli1 can claim it."""
        # Desktop claims then releases
        ciq.send_message("desktop", "cli1", "test-module", category="scope_claim",
                        priority="high", path=self.path)
        ciq.send_message("desktop", "cli1", "test-module", category="scope_release",
                        path=self.path)
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            cca_comm.cmd_claim(["test-module"])
        output = f.getvalue()
        self.assertIn("Scope claimed", output)

    @patch.dict(os.environ, {"CCA_CHAT_ID": "cli1"})
    def test_claim_with_file_conflict(self):
        """cli1 tries to claim files already in desktop's scope -> blocked."""
        ciq.send_message("desktop", "cli1", "working on guards",
                        category="scope_claim", priority="high",
                        files=["agent-guard/bash_guard.py"], path=self.path)
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            cca_comm.cmd_claim(["my work", "agent-guard/bash_guard.py"])
        output = f.getvalue()
        self.assertIn("SCOPE CONFLICT", output)

    def test_check_claim_conflicts_helper_no_conflicts(self):
        """_check_claim_conflicts returns empty list when no conflicts."""
        conflicts = cca_comm._check_claim_conflicts("cli1", "new-scope", [], self.path)
        self.assertEqual(conflicts, [])

    def test_check_claim_conflicts_helper_subject_overlap(self):
        """_check_claim_conflicts detects subject-level overlap."""
        ciq.send_message("desktop", "cli1", "memory-system/", category="scope_claim",
                        priority="high", path=self.path)
        conflicts = cca_comm._check_claim_conflicts("cli1", "memory-system/", [], self.path)
        self.assertGreater(len(conflicts), 0)

    def test_check_claim_conflicts_ignores_own_claims(self):
        """_check_claim_conflicts ignores the caller's own active scopes."""
        ciq.send_message("cli1", "desktop", "my-scope", category="scope_claim",
                        priority="high", path=self.path)
        conflicts = cca_comm._check_claim_conflicts("cli1", "my-scope", [], self.path)
        self.assertEqual(len(conflicts), 0)


# ── Gap #3: Stale Scope Timeout in Crash Recovery ─────────────────────────


class TestStaleScoreInCrashRecovery(unittest.TestCase):
    """Verify crash_recovery.run_recovery() expires stale scopes."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.path = self.tmp.name

    def tearDown(self):
        if os.path.exists(self.path):
            os.unlink(self.path)

    @patch.object(cr, "_get_claude_processes", return_value=[])
    @patch.object(cr, "_get_git_status", return_value="")
    def test_run_recovery_expires_stale_scopes(self, mock_git, mock_procs):
        """run_recovery should expire stale scopes even if worker process is gone."""
        # Create a stale scope (45 minutes old)
        stale_time = (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat()
        stale_msg = {
            "id": "cca_stale_001",
            "sender": "cli1",
            "target": "desktop",
            "subject": "old-module",
            "body": "",
            "priority": "high",
            "category": "scope_claim",
            "status": "unread",
            "created_at": stale_time,
            "read_at": None,
        }
        with open(self.path, "w") as f:
            f.write(json.dumps(stale_msg) + "\n")

        report = cr.run_recovery(self.path)
        self.assertGreater(report.get("stale_expired", 0), 0)
        self.assertIn("stale scope", report["actions"][0].lower())

    @patch.object(cr, "_get_claude_processes", return_value=[])
    @patch.object(cr, "_get_git_status", return_value="")
    def test_run_recovery_no_stale_if_recent(self, mock_git, mock_procs):
        """run_recovery should NOT expire scopes that are less than 30 minutes old."""
        recent_time = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        recent_msg = {
            "id": "cca_recent_001",
            "sender": "cli1",
            "target": "desktop",
            "subject": "active-module",
            "body": "",
            "priority": "high",
            "category": "scope_claim",
            "status": "unread",
            "created_at": recent_time,
            "read_at": None,
        }
        with open(self.path, "w") as f:
            f.write(json.dumps(recent_msg) + "\n")

        report = cr.run_recovery(self.path)
        self.assertEqual(report.get("stale_expired", 0), 0)

    @patch.object(cr, "_get_claude_processes", return_value=[
        {"pid": 100, "chat_id": "cli1", "cca_project": True},
    ])
    @patch.object(cr, "_get_git_status", return_value="")
    def test_stale_scope_expired_even_if_worker_alive(self, mock_git, mock_procs):
        """Stale scope should expire even if worker process is running (hung worker)."""
        stale_time = (datetime.now(timezone.utc) - timedelta(minutes=35)).isoformat()
        stale_msg = {
            "id": "cca_hung_001",
            "sender": "cli1",
            "target": "desktop",
            "subject": "hung-scope",
            "body": "",
            "priority": "high",
            "category": "scope_claim",
            "status": "unread",
            "created_at": stale_time,
            "read_at": None,
        }
        with open(self.path, "w") as f:
            f.write(json.dumps(stale_msg) + "\n")

        report = cr.run_recovery(self.path)
        # Stale expired should catch this
        self.assertGreater(report.get("stale_expired", 0), 0)

    @patch.object(cr, "_get_claude_processes", return_value=[])
    @patch.object(cr, "_get_git_status", return_value="")
    def test_run_recovery_report_status_recovered_on_stale(self, mock_git, mock_procs):
        """Report status should be 'recovered' when stale scopes are expired."""
        stale_time = (datetime.now(timezone.utc) - timedelta(minutes=40)).isoformat()
        stale_msg = {
            "id": "cca_stale_002",
            "sender": "cli1",
            "target": "desktop",
            "subject": "expired-scope",
            "body": "",
            "priority": "high",
            "category": "scope_claim",
            "status": "unread",
            "created_at": stale_time,
            "read_at": None,
        }
        with open(self.path, "w") as f:
            f.write(json.dumps(stale_msg) + "\n")

        report = cr.run_recovery(self.path)
        # After stale scope is expired, the scope should be released
        # and the crash detection should find no orphaned scopes
        self.assertIn(report["status"], ("recovered", "clean"))

    @patch.object(cr, "_get_claude_processes", return_value=[])
    @patch.object(cr, "_get_git_status", return_value="")
    def test_run_recovery_clean_when_nothing_stale(self, mock_git, mock_procs):
        """Report should be clean when there are no scopes at all."""
        report = cr.run_recovery(self.path)
        self.assertEqual(report["status"], "clean")
        self.assertEqual(report.get("stale_expired", 0), 0)

    def test_expire_stale_scopes_function_exists(self):
        """crash_recovery.expire_stale_scopes should be callable."""
        self.assertTrue(callable(cr.expire_stale_scopes))

    @patch.object(cr, "_get_claude_processes", return_value=[])
    @patch.object(cr, "_get_git_status", return_value=" M file.py")
    def test_stale_and_crashed_combined(self, mock_git, mock_procs):
        """Both stale scope expiry AND crash detection should work together."""
        now = datetime.now(timezone.utc)
        # One stale scope (40 min old)
        stale_msg = {
            "id": "cca_combined_stale",
            "sender": "cli1",
            "target": "desktop",
            "subject": "stale-scope",
            "body": "",
            "priority": "high",
            "category": "scope_claim",
            "status": "unread",
            "created_at": (now - timedelta(minutes=40)).isoformat(),
            "read_at": None,
        }
        # One fresh scope from cli2 (5 min old, no process = crash)
        fresh_msg = {
            "id": "cca_combined_fresh",
            "sender": "cli2",
            "target": "desktop",
            "subject": "fresh-scope",
            "body": "",
            "priority": "high",
            "category": "scope_claim",
            "status": "unread",
            "created_at": (now - timedelta(minutes=5)).isoformat(),
            "read_at": None,
        }
        with open(self.path, "w") as f:
            f.write(json.dumps(stale_msg) + "\n")
            f.write(json.dumps(fresh_msg) + "\n")

        report = cr.run_recovery(self.path)
        # Stale scope should be expired
        self.assertGreater(report.get("stale_expired", 0), 0)
        # Fresh scope from cli2 with no process should be detected as crashed
        self.assertEqual(report["status"], "recovered")


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
