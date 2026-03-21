#!/usr/bin/env python3
"""
test_phase3_preflight.py — Tests for phase3_preflight.py

Pre-session safety checks for 3-chat hivemind:
- No duplicate workers already running
- Queue file accessible and not corrupted
- No stale scope claims from previous sessions
- Smoke tests passing
"""

import json
import os
import tempfile
import unittest
from unittest.mock import patch


class TestDuplicateWorkerCheck(unittest.TestCase):
    """Verify no cli1/cli2 already running."""

    def test_no_duplicates_clean_state(self):
        """Clean state: no workers running = pass."""
        import phase3_preflight as pf
        with patch.object(pf, "_check_worker_running", return_value=False):
            result = pf.check_no_duplicate_workers()
        self.assertTrue(result["ok"])
        self.assertEqual(result["running"], [])

    def test_cli1_already_running(self):
        """Fails if cli1 already running."""
        import phase3_preflight as pf
        def mock_check(wid):
            return wid == "cli1"
        with patch.object(pf, "_check_worker_running", side_effect=mock_check):
            result = pf.check_no_duplicate_workers()
        self.assertFalse(result["ok"])
        self.assertIn("cli1", result["running"])

    def test_both_running(self):
        """Fails if both workers already running."""
        import phase3_preflight as pf
        with patch.object(pf, "_check_worker_running", return_value=True):
            result = pf.check_no_duplicate_workers()
        self.assertFalse(result["ok"])
        self.assertEqual(len(result["running"]), 2)


class TestQueueHealthCheck(unittest.TestCase):
    """Verify queue file is accessible and parseable."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.queue_path = os.path.join(self.tmpdir, "queue.jsonl")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_valid_queue(self):
        """Valid JSONL queue passes."""
        import phase3_preflight as pf
        with open(self.queue_path, "w") as f:
            f.write(json.dumps({"sender": "desktop", "target": "cli1"}) + "\n")
        result = pf.check_queue_health(self.queue_path)
        self.assertTrue(result["ok"])

    def test_missing_queue_is_ok(self):
        """Missing queue file is fine (fresh start)."""
        import phase3_preflight as pf
        result = pf.check_queue_health("/nonexistent/queue.jsonl")
        self.assertTrue(result["ok"])
        self.assertEqual(result["reason"], "no queue file (fresh start)")

    def test_corrupted_queue(self):
        """Corrupted queue warns but doesn't fail."""
        import phase3_preflight as pf
        with open(self.queue_path, "w") as f:
            f.write("NOT JSON\n")
            f.write(json.dumps({"sender": "desktop"}) + "\n")
        result = pf.check_queue_health(self.queue_path)
        self.assertTrue(result["ok"])
        self.assertEqual(result["corrupt_lines"], 1)

    def test_empty_queue(self):
        """Empty queue file passes."""
        import phase3_preflight as pf
        with open(self.queue_path, "w") as f:
            pass
        result = pf.check_queue_health(self.queue_path)
        self.assertTrue(result["ok"])


class TestStaleScopeCheck(unittest.TestCase):
    """Check for stale scope claims from previous sessions."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.queue_path = os.path.join(self.tmpdir, "queue.jsonl")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_no_stale_scopes(self):
        """No active scopes = pass."""
        import phase3_preflight as pf
        with open(self.queue_path, "w") as f:
            pass
        result = pf.check_stale_scopes(self.queue_path)
        self.assertTrue(result["ok"])

    def test_stale_scope_detected(self):
        """Unreleased scope from previous session = warning."""
        import phase3_preflight as pf
        with open(self.queue_path, "w") as f:
            f.write(json.dumps({
                "sender": "cli1",
                "category": "scope_claim",
                "subject": "old_file.py",
                "created_at": "2026-03-20T10:00:00Z",
            }) + "\n")
        result = pf.check_stale_scopes(self.queue_path)
        self.assertFalse(result["ok"])
        self.assertEqual(result["stale_count"], 1)

    def test_released_scope_is_clean(self):
        """Scope that was properly released = pass."""
        import phase3_preflight as pf
        with open(self.queue_path, "w") as f:
            f.write(json.dumps({
                "sender": "cli1",
                "category": "scope_claim",
                "subject": "file.py",
                "created_at": "2026-03-20T10:00:00Z",
            }) + "\n")
            f.write(json.dumps({
                "sender": "cli1",
                "category": "scope_release",
                "subject": "file.py",
                "created_at": "2026-03-20T11:00:00Z",
            }) + "\n")
        result = pf.check_stale_scopes(self.queue_path)
        self.assertTrue(result["ok"])


class TestRunAllPreflight(unittest.TestCase):
    """Test the combined preflight check."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.queue_path = os.path.join(self.tmpdir, "queue.jsonl")
        with open(self.queue_path, "w") as f:
            pass

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_all_pass(self):
        """All checks pass = overall pass."""
        import phase3_preflight as pf
        with patch.object(pf, "_check_worker_running", return_value=False):
            result = pf.run_preflight(self.queue_path)
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["checks"]), 3)

    def test_one_failure_means_overall_fail(self):
        """One failing check = overall fail."""
        import phase3_preflight as pf
        with patch.object(pf, "_check_worker_running", return_value=True):
            result = pf.run_preflight(self.queue_path)
        self.assertFalse(result["ok"])

    def test_format_report(self):
        """Format produces readable output."""
        import phase3_preflight as pf
        with patch.object(pf, "_check_worker_running", return_value=False):
            result = pf.run_preflight(self.queue_path)
        report = pf.format_report(result)
        self.assertIn("PASS", report)
        self.assertIn("duplicate", report.lower())


if __name__ == "__main__":
    unittest.main()
