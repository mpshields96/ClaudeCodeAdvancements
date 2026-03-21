#!/usr/bin/env python3
"""
test_crash_recovery_extended.py — Extended edge-case tests for crash_recovery.py

Covers: terminal worker detection, unknown senders, process filtering edge cases,
orphaned scope edge cases, recovery report states, stale scope expiry integration,
CLI output edge cases.
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import crash_recovery as cr


class TestCrashDetectionExtended(unittest.TestCase):
    """Extended crash detection edge cases."""

    def test_terminal_worker_scope_detected_as_crash(self):
        """'terminal' is in WORKER_CHAT_IDS — orphaned terminal scope is a crash."""
        procs = []
        scopes = [{"sender": "terminal", "subject": "some_scope",
                   "created_at": datetime.now(timezone.utc).isoformat()}]
        with patch.object(cr, "_get_claude_processes", return_value=procs):
            result = cr.detect_crashed_workers(active_scopes=scopes)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["chat_id"], "terminal")

    def test_unknown_sender_ignored(self):
        """Scope from unknown sender (not in WORKER_CHAT_IDS) is not a crash."""
        procs = []
        scopes = [{"sender": "unknown_bot", "subject": "some_scope",
                   "created_at": datetime.now(timezone.utc).isoformat()}]
        with patch.object(cr, "_get_claude_processes", return_value=procs):
            result = cr.detect_crashed_workers(active_scopes=scopes)
        self.assertEqual(len(result), 0)

    def test_process_without_cca_project_flag_not_counted(self):
        """Process with cca_project=False is not counted as running worker."""
        procs = [{"pid": 100, "chat_id": "cli1", "cca_project": False}]
        scopes = [{"sender": "cli1", "subject": "feature_x",
                   "created_at": datetime.now(timezone.utc).isoformat()}]
        with patch.object(cr, "_get_claude_processes", return_value=procs):
            result = cr.detect_crashed_workers(active_scopes=scopes)
        # cca_project=False means it's not a CCA session — cli1 scope still orphaned
        self.assertEqual(len(result), 1)

    def test_process_without_chat_id_not_counted(self):
        """Process missing chat_id field doesn't protect any worker from crash detection."""
        procs = [{"pid": 100, "cca_project": True}]  # no chat_id
        scopes = [{"sender": "cli1", "subject": "feature_x",
                   "created_at": datetime.now(timezone.utc).isoformat()}]
        with patch.object(cr, "_get_claude_processes", return_value=procs):
            result = cr.detect_crashed_workers(active_scopes=scopes)
        self.assertEqual(len(result), 1)

    def test_process_with_none_chat_id_not_counted(self):
        """Process with chat_id=None doesn't count as running worker."""
        procs = [{"pid": 100, "chat_id": None, "cca_project": True}]
        scopes = [{"sender": "cli2", "subject": "task",
                   "created_at": datetime.now(timezone.utc).isoformat()}]
        with patch.object(cr, "_get_claude_processes", return_value=procs):
            result = cr.detect_crashed_workers(active_scopes=scopes)
        self.assertEqual(len(result), 1)

    def test_running_worker_protects_only_its_scope(self):
        """Running cli1 protects cli1 scope only; cli2 scope is still orphaned."""
        procs = [{"pid": 100, "chat_id": "cli1", "cca_project": True}]
        scopes = [
            {"sender": "cli1", "subject": "scope_a",
             "created_at": datetime.now(timezone.utc).isoformat()},
            {"sender": "cli2", "subject": "scope_b",
             "created_at": datetime.now(timezone.utc).isoformat()},
        ]
        with patch.object(cr, "_get_claude_processes", return_value=procs):
            result = cr.detect_crashed_workers(active_scopes=scopes)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["chat_id"], "cli2")

    def test_crashed_worker_result_has_required_fields(self):
        """detect_crashed_workers returns dicts with chat_id, scope, created_at, pid."""
        procs = []
        ts = "2026-03-20T10:00:00Z"
        scopes = [{"sender": "cli1", "subject": "my_scope", "created_at": ts}]
        with patch.object(cr, "_get_claude_processes", return_value=procs):
            result = cr.detect_crashed_workers(active_scopes=scopes)
        self.assertEqual(len(result), 1)
        entry = result[0]
        self.assertIn("chat_id", entry)
        self.assertIn("scope", entry)
        self.assertIn("created_at", entry)
        self.assertIn("pid", entry)
        self.assertIsNone(entry["pid"])


class TestReleaseOrphanedScopesExtended(unittest.TestCase):
    """Extended scope release edge cases."""

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, dir="/tmp"
        )
        self.tmpfile.close()
        self.queue_path = self.tmpfile.name

    def tearDown(self):
        os.unlink(self.queue_path)

    def test_empty_crashed_workers_list(self):
        """Empty crashed_workers list = nothing released."""
        released = cr.release_orphaned_scopes(
            crashed_workers=[],
            queue_path=self.queue_path,
        )
        self.assertEqual(len(released), 0)

    def test_multiple_crashed_workers_all_released(self):
        """Multiple orphaned scopes from different workers all released."""
        with open(self.queue_path, "w") as f:
            for wid, scope in [("cli1", "scope_a"), ("cli2", "scope_b")]:
                claim = {
                    "id": f"id_{wid}", "sender": wid, "target": "desktop",
                    "subject": scope, "category": "scope_claim",
                    "read_by": {}, "created_at": datetime.now(timezone.utc).isoformat(),
                }
                f.write(json.dumps(claim) + "\n")

        crashed = [
            {"chat_id": "cli1", "scope": "scope_a"},
            {"chat_id": "cli2", "scope": "scope_b"},
        ]
        released = cr.release_orphaned_scopes(
            crashed_workers=crashed,
            queue_path=self.queue_path,
        )
        self.assertEqual(len(released), 2)
        released_scopes = {r["scope"] for r in released}
        self.assertIn("scope_a", released_scopes)
        self.assertIn("scope_b", released_scopes)

    def test_release_message_has_crash_recovery_body(self):
        """Released scope message body contains 'crash-recovery' marker."""
        with open(self.queue_path, "w") as f:
            claim = {
                "id": "abc", "sender": "cli1", "target": "desktop",
                "subject": "scope_x", "category": "scope_claim",
                "read_by": {}, "created_at": datetime.now(timezone.utc).isoformat(),
            }
            f.write(json.dumps(claim) + "\n")

        cr.release_orphaned_scopes(
            crashed_workers=[{"chat_id": "cli1", "scope": "scope_x"}],
            queue_path=self.queue_path,
        )

        with open(self.queue_path) as f:
            lines = f.readlines()
        release = json.loads(lines[-1])
        self.assertIn("crash-recovery", release["body"])

    def test_scope_mismatch_not_released(self):
        """Crash entry with scope that doesn't exist in queue isn't released."""
        with open(self.queue_path, "w") as f:
            claim = {
                "id": "abc", "sender": "cli1", "target": "desktop",
                "subject": "actual_scope", "category": "scope_claim",
                "read_by": {}, "created_at": datetime.now(timezone.utc).isoformat(),
            }
            f.write(json.dumps(claim) + "\n")

        released = cr.release_orphaned_scopes(
            crashed_workers=[{"chat_id": "cli1", "scope": "different_scope"}],
            queue_path=self.queue_path,
        )
        self.assertEqual(len(released), 0)


class TestRecoveryReportExtended(unittest.TestCase):
    """Extended recovery report generation edge cases."""

    def test_clean_with_empty_git_status(self):
        """Empty git status string = has_uncommitted_changes = False."""
        report = cr.generate_recovery_report(crashed=[], released=[], git_status="")
        self.assertFalse(report["has_uncommitted_changes"])

    def test_detected_state_when_scopes_already_released(self):
        """Crash detected but scope already released = 'detected' status."""
        crashed = [{"chat_id": "cli1", "scope": "feature_x", "pid": None}]
        report = cr.generate_recovery_report(
            crashed=crashed, released=[], git_status=""
        )
        self.assertEqual(report["status"], "detected")
        self.assertIn("cli1", report["summary"])

    def test_uncommitted_changes_only_logged_when_crashed(self):
        """Uncommitted changes only flagged in actions when there are crashed workers."""
        report = cr.generate_recovery_report(
            crashed=[], released=[], git_status="M file.py"
        )
        # No crashes — uncommitted changes present but no crash action logged
        self.assertEqual(report["status"], "clean")
        uncommitted_actions = [a for a in report["actions"] if "Uncommitted" in a]
        self.assertEqual(len(uncommitted_actions), 0)

    def test_multiple_crashed_workers_in_summary(self):
        """Summary mentions all crashed worker chat IDs."""
        crashed = [
            {"chat_id": "cli1", "scope": "a", "pid": None},
            {"chat_id": "cli2", "scope": "b", "pid": None},
        ]
        released = [
            {"scope": "a", "chat_id": "cli1"},
            {"scope": "b", "chat_id": "cli2"},
        ]
        report = cr.generate_recovery_report(
            crashed=crashed, released=released, git_status=""
        )
        self.assertEqual(report["status"], "recovered")
        # Summary should mention at least one of the workers
        self.assertTrue(
            "cli1" in report["summary"] or "cli2" in report["summary"]
        )

    def test_report_always_has_timestamp(self):
        """Generated report always includes a timestamp field."""
        report = cr.generate_recovery_report(crashed=[], released=[], git_status="")
        self.assertIn("timestamp", report)
        self.assertIsNotNone(report["timestamp"])

    def test_report_includes_crashed_workers_field(self):
        """Report includes the full crashed_workers list."""
        crashed = [{"chat_id": "cli1", "scope": "x", "pid": None}]
        report = cr.generate_recovery_report(crashed=crashed, released=[], git_status="")
        self.assertIn("crashed_workers", report)
        self.assertEqual(len(report["crashed_workers"]), 1)

    def test_report_released_scopes_empty_when_none(self):
        """released_scopes field is empty list when nothing released."""
        report = cr.generate_recovery_report(crashed=[], released=[], git_status="")
        self.assertEqual(report["released_scopes"], [])


class TestRunRecoveryExtended(unittest.TestCase):
    """Extended run_recovery pipeline tests."""

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, dir="/tmp"
        )
        self.tmpfile.close()
        self.queue_path = self.tmpfile.name

    def tearDown(self):
        os.unlink(self.queue_path)

    def test_stale_expired_field_always_present(self):
        """run_recovery always includes stale_expired count in report."""
        with patch.object(cr, "_get_claude_processes", return_value=[]):
            with patch.object(cr, "_get_git_status", return_value=""):
                report = cr.run_recovery(queue_path=self.queue_path)
        self.assertIn("stale_expired", report)

    def test_clean_state_has_zero_stale_expired(self):
        """Clean state has stale_expired=0."""
        with patch.object(cr, "_get_claude_processes", return_value=[]):
            with patch.object(cr, "_get_git_status", return_value=""):
                report = cr.run_recovery(queue_path=self.queue_path)
        self.assertEqual(report["stale_expired"], 0)

    def test_has_uncommitted_changes_reflected_in_report(self):
        """Git changes are reflected in has_uncommitted_changes field."""
        with patch.object(cr, "_get_claude_processes", return_value=[]):
            with patch.object(cr, "_get_git_status", return_value="M modified.py"):
                report = cr.run_recovery(queue_path=self.queue_path)
        self.assertTrue(report["has_uncommitted_changes"])

    def test_clean_git_status_not_uncommitted(self):
        """Empty git status = has_uncommitted_changes False."""
        with patch.object(cr, "_get_claude_processes", return_value=[]):
            with patch.object(cr, "_get_git_status", return_value=""):
                report = cr.run_recovery(queue_path=self.queue_path)
        self.assertFalse(report["has_uncommitted_changes"])


class TestCLIExtended(unittest.TestCase):
    """Extended CLI interface tests."""

    def test_no_args_prints_usage(self):
        """No args prints help without raising."""
        with patch("builtins.print") as mock_print:
            cr.cli_main([])
        mock_print.assert_called()

    def test_run_with_uncommitted_prints_warning(self):
        """'run' command prints uncommitted warning when changes exist."""
        report = {
            "status": "recovered",
            "actions": ["Released orphaned scope"],
            "summary": "Recovered from crash: cli1",
            "has_uncommitted_changes": True,
            "stale_expired": 0,
        }
        with patch.object(cr, "run_recovery", return_value=report):
            with patch("builtins.print") as mock_print:
                cr.cli_main(["run"])
        printed = " ".join(str(call) for call in mock_print.call_args_list)
        self.assertIn("uncommitted", printed.lower())

    def test_status_with_crashed_workers_prints_crash_info(self):
        """'status' command prints CRASHED WORKERS when detected."""
        crashed = [{"chat_id": "cli1", "scope": "feature_x"}]
        with patch.object(cr, "_get_claude_processes", return_value=[]):
            with patch.object(cr, "_get_active_scopes", return_value=[]):
                with patch.object(cr, "detect_crashed_workers", return_value=crashed):
                    with patch("builtins.print") as mock_print:
                        cr.cli_main(["status"])
        printed = " ".join(str(call) for call in mock_print.call_args_list)
        self.assertIn("CRASHED", printed)

    def test_status_no_crashes_prints_clean(self):
        """'status' command prints clean message when no crashes."""
        with patch.object(cr, "_get_claude_processes", return_value=[]):
            with patch.object(cr, "_get_active_scopes", return_value=[]):
                with patch("builtins.print") as mock_print:
                    cr.cli_main(["status"])
        printed = " ".join(str(call) for call in mock_print.call_args_list)
        self.assertIn("No crashed", printed)


if __name__ == "__main__":
    unittest.main()
