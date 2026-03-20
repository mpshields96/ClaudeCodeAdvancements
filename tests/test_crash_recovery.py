#!/usr/bin/env python3
"""Tests for crash_recovery.py — Worker crash detection and recovery.

Phase 2 hivemind infrastructure: handles the case where a CLI worker crashes
mid-scope-claim, leaving stale scopes and potentially uncommitted work.
"""
import json
import os
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import crash_recovery as cr


class TestCrashDetection(unittest.TestCase):
    """Test detecting crashed/stale worker sessions."""

    def test_no_workers_no_crash(self):
        """No running workers = nothing crashed."""
        with patch.object(cr, "_get_claude_processes", return_value=[]):
            result = cr.detect_crashed_workers(active_scopes=[])
            self.assertEqual(len(result), 0)

    def test_active_worker_with_scope_not_crashed(self):
        """Running worker + matching scope = healthy, not crashed."""
        procs = [{"pid": 100, "chat_id": "cli1", "cca_project": True}]
        scopes = [{"sender": "cli1", "subject": "feature_x"}]
        with patch.object(cr, "_get_claude_processes", return_value=procs):
            result = cr.detect_crashed_workers(active_scopes=scopes)
            self.assertEqual(len(result), 0)

    def test_scope_without_running_worker_is_crashed(self):
        """Scope claim from cli1 but no cli1 process = crash detected."""
        procs = []  # No workers running
        scopes = [{"sender": "cli1", "subject": "feature_x",
                    "created_at": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()}]
        with patch.object(cr, "_get_claude_processes", return_value=procs):
            result = cr.detect_crashed_workers(active_scopes=scopes)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["chat_id"], "cli1")
            self.assertEqual(result[0]["scope"], "feature_x")

    def test_desktop_scope_ignored(self):
        """Desktop scopes are never considered 'crashed worker' scopes."""
        procs = []
        scopes = [{"sender": "desktop", "subject": "docs"}]
        with patch.object(cr, "_get_claude_processes", return_value=procs):
            result = cr.detect_crashed_workers(active_scopes=scopes)
            self.assertEqual(len(result), 0)

    def test_multiple_crashed_workers(self):
        """Multiple orphaned scopes from different workers."""
        procs = []
        scopes = [
            {"sender": "cli1", "subject": "feature_x",
             "created_at": datetime.now(timezone.utc).isoformat()},
            {"sender": "cli2", "subject": "feature_y",
             "created_at": datetime.now(timezone.utc).isoformat()},
        ]
        with patch.object(cr, "_get_claude_processes", return_value=procs):
            result = cr.detect_crashed_workers(active_scopes=scopes)
            self.assertEqual(len(result), 2)


class TestScopeRecovery(unittest.TestCase):
    """Test releasing orphaned scopes after a crash."""

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, dir="/tmp"
        )
        self.tmpfile.close()
        self.queue_path = self.tmpfile.name

    def tearDown(self):
        os.unlink(self.queue_path)

    def test_release_orphaned_scope(self):
        """Orphaned scope gets released with crash-recovery marker."""
        # Write a scope_claim to the queue
        claim = {
            "id": "test123",
            "sender": "cli1",
            "target": "desktop",
            "subject": "feature_x",
            "category": "scope_claim",
            "read_by": {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(self.queue_path, "w") as f:
            f.write(json.dumps(claim) + "\n")

        released = cr.release_orphaned_scopes(
            crashed_workers=[{"chat_id": "cli1", "scope": "feature_x"}],
            queue_path=self.queue_path,
        )
        self.assertEqual(len(released), 1)

        # Verify a scope_release was written
        with open(self.queue_path) as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 2)  # Original claim + release
        release_msg = json.loads(lines[1])
        self.assertEqual(release_msg["category"], "scope_release")
        self.assertIn("crash-recovery", release_msg["body"])

    def test_no_double_release(self):
        """Already-released scope is not released again."""
        claim = {
            "id": "test123", "sender": "cli1", "target": "desktop",
            "subject": "feature_x", "category": "scope_claim",
            "read_by": {}, "created_at": datetime.now(timezone.utc).isoformat(),
        }
        release = {
            "id": "test456", "sender": "cli1", "target": "desktop",
            "subject": "feature_x", "category": "scope_release",
            "read_by": {}, "created_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(self.queue_path, "w") as f:
            f.write(json.dumps(claim) + "\n")
            f.write(json.dumps(release) + "\n")

        released = cr.release_orphaned_scopes(
            crashed_workers=[{"chat_id": "cli1", "scope": "feature_x"}],
            queue_path=self.queue_path,
        )
        self.assertEqual(len(released), 0)


class TestRecoveryReport(unittest.TestCase):
    """Test generating a recovery report."""

    def test_empty_report(self):
        """No crashes = clean report."""
        report = cr.generate_recovery_report(crashed=[], released=[], git_status="clean")
        self.assertEqual(report["status"], "clean")
        self.assertEqual(len(report["actions"]), 0)

    def test_report_with_crash_and_release(self):
        """Crashed worker + released scope = recovery report."""
        crashed = [{"chat_id": "cli1", "scope": "feature_x", "pid": None}]
        released = [{"scope": "feature_x", "chat_id": "cli1"}]
        report = cr.generate_recovery_report(
            crashed=crashed, released=released, git_status="M feature_x.py"
        )
        self.assertEqual(report["status"], "recovered")
        self.assertGreater(len(report["actions"]), 0)
        self.assertIn("cli1", report["summary"])

    def test_report_with_uncommitted_changes(self):
        """Uncommitted changes from crashed worker flagged."""
        crashed = [{"chat_id": "cli1", "scope": "feature_x", "pid": None}]
        report = cr.generate_recovery_report(
            crashed=crashed, released=[], git_status="M feature_x.py\n?? new_file.py"
        )
        self.assertTrue(report["has_uncommitted_changes"])


class TestFullRecovery(unittest.TestCase):
    """Test the full recovery pipeline."""

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, dir="/tmp"
        )
        self.tmpfile.close()
        self.queue_path = self.tmpfile.name

    def tearDown(self):
        os.unlink(self.queue_path)

    def test_full_recovery_no_crashes(self):
        """Full pipeline with no crashes = clean."""
        with patch.object(cr, "_get_claude_processes", return_value=[]):
            with patch.object(cr, "_get_git_status", return_value=""):
                report = cr.run_recovery(queue_path=self.queue_path)
                self.assertEqual(report["status"], "clean")

    def test_full_recovery_with_crash(self):
        """Full pipeline detecting and recovering from a crash."""
        # Create an orphaned scope claim
        claim = {
            "id": "test789", "sender": "cli1", "target": "desktop",
            "subject": "feature_x", "category": "scope_claim",
            "read_by": {}, "created_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(self.queue_path, "w") as f:
            f.write(json.dumps(claim) + "\n")

        with patch.object(cr, "_get_claude_processes", return_value=[]):
            with patch.object(cr, "_get_git_status", return_value=""):
                report = cr.run_recovery(queue_path=self.queue_path)
                self.assertEqual(report["status"], "recovered")
                self.assertEqual(len(report["released_scopes"]), 1)


class TestCLI(unittest.TestCase):
    """Test CLI interface."""

    def test_run_command(self):
        """'run' command executes without error."""
        with patch.object(cr, "run_recovery", return_value={"status": "clean", "actions": [], "summary": "No issues"}):
            with patch("builtins.print"):
                cr.cli_main(["run"])

    def test_status_command(self):
        """'status' command shows crash detection without recovery."""
        with patch.object(cr, "_get_claude_processes", return_value=[]):
            with patch.object(cr, "_get_active_scopes", return_value=[]):
                with patch("builtins.print"):
                    cr.cli_main(["status"])

    def test_unknown_command(self):
        """Unknown command prints usage."""
        with patch("builtins.print") as mock_print:
            cr.cli_main(["badcommand"])
            mock_print.assert_called()


if __name__ == "__main__":
    unittest.main()
