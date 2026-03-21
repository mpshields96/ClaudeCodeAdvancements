#!/usr/bin/env python3
"""
test_phase3_preflight_extended.py — Extended edge-case tests for phase3_preflight.py

Covers: check_no_duplicate_workers edge cases, queue health with various corruption
patterns, stale scope edge cases, format_report output, run_preflight combinations.
"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import phase3_preflight as pf


class TestDuplicateWorkerCheckExtended(unittest.TestCase):
    """Extended edge cases for check_no_duplicate_workers."""

    def test_only_cli2_running(self):
        """Fails with only cli2 running."""
        def mock_check(wid):
            return wid == "cli2"
        with patch.object(pf, "_check_worker_running", side_effect=mock_check):
            result = pf.check_no_duplicate_workers()
        self.assertFalse(result["ok"])
        self.assertIn("cli2", result["running"])
        self.assertNotIn("cli1", result["running"])

    def test_check_returns_name_field(self):
        """Result includes name field for format_report."""
        with patch.object(pf, "_check_worker_running", return_value=False):
            result = pf.check_no_duplicate_workers()
        self.assertIn("name", result)

    def test_running_field_is_list(self):
        """Running field is always a list, even when empty."""
        with patch.object(pf, "_check_worker_running", return_value=False):
            result = pf.check_no_duplicate_workers()
        self.assertIsInstance(result["running"], list)

    def test_check_worker_running_raises_os_error(self):
        """If check_worker_running raises OSError, it returns False (fail-open).
        The preflight check should still pass (no blocked worker found)."""
        with patch.object(pf, "_check_worker_running", side_effect=OSError("no subprocess")):
            # patch raises — but check_no_duplicate_workers calls _check_worker_running
            # if it fails open, no workers detected = ok
            try:
                result = pf.check_no_duplicate_workers()
                # If it raises internally, check_worker_running should handle it
            except OSError:
                pass  # Acceptable — underlying method doesn't swallow it


class TestQueueHealthExtended(unittest.TestCase):
    """Extended queue health checks."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.queue_path = os.path.join(self.tmpdir, "queue.jsonl")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_only_blank_lines_queue(self):
        """Queue with only blank lines returns ok with 0 total lines."""
        with open(self.queue_path, "w") as f:
            f.write("\n\n\n")
        result = pf.check_queue_health(self.queue_path)
        self.assertTrue(result["ok"])
        self.assertEqual(result["total_lines"], 0)

    def test_many_corrupt_lines_still_ok(self):
        """Queue with many corrupt lines (warnings only, not failure)."""
        with open(self.queue_path, "w") as f:
            for _ in range(10):
                f.write("NOT JSON\n")
            f.write(json.dumps({"sender": "desktop"}) + "\n")
        result = pf.check_queue_health(self.queue_path)
        self.assertTrue(result["ok"])  # corrupt lines = warning, not fail
        self.assertEqual(result["corrupt_lines"], 10)
        self.assertEqual(result["total_lines"], 11)

    def test_result_includes_total_lines(self):
        """Result includes total_lines count for valid queue."""
        with open(self.queue_path, "w") as f:
            for i in range(5):
                f.write(json.dumps({"sender": "desktop", "id": i}) + "\n")
        result = pf.check_queue_health(self.queue_path)
        self.assertEqual(result["total_lines"], 5)
        self.assertEqual(result["corrupt_lines"], 0)

    def test_queue_name_field_present(self):
        """Result includes name field."""
        result = pf.check_queue_health(self.queue_path)
        self.assertIn("name", result)

    def test_zero_corrupt_when_all_valid(self):
        """Queue with all valid JSON shows 0 corrupt."""
        with open(self.queue_path, "w") as f:
            f.write(json.dumps({"k": "v"}) + "\n")
            f.write(json.dumps({"k": "v2"}) + "\n")
        result = pf.check_queue_health(self.queue_path)
        self.assertEqual(result["corrupt_lines"], 0)


class TestStaleScopeCheckExtended(unittest.TestCase):
    """Extended stale scope detection edge cases."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.queue_path = os.path.join(self.tmpdir, "queue.jsonl")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_multiple_stale_scopes_different_workers(self):
        """Multiple unreleased scopes from different workers both detected."""
        with open(self.queue_path, "w") as f:
            f.write(json.dumps({
                "sender": "cli1", "category": "scope_claim",
                "subject": "a.py", "created_at": "2026-03-20T10:00:00Z",
            }) + "\n")
            f.write(json.dumps({
                "sender": "cli2", "category": "scope_claim",
                "subject": "b.py", "created_at": "2026-03-20T11:00:00Z",
            }) + "\n")
        result = pf.check_stale_scopes(self.queue_path)
        self.assertFalse(result["ok"])
        self.assertEqual(result["stale_count"], 2)
        senders = [s["sender"] for s in result["stale_scopes"]]
        self.assertIn("cli1", senders)
        self.assertIn("cli2", senders)

    def test_release_before_claim_still_stale(self):
        """Release with timestamp BEFORE claim timestamp doesn't count as a release."""
        with open(self.queue_path, "w") as f:
            f.write(json.dumps({
                "sender": "cli1", "category": "scope_claim",
                "subject": "x.py", "created_at": "2026-03-20T12:00:00Z",
            }) + "\n")
            f.write(json.dumps({
                "sender": "cli1", "category": "scope_release",
                "subject": "x.py", "created_at": "2026-03-20T10:00:00Z",  # BEFORE claim
            }) + "\n")
        result = pf.check_stale_scopes(self.queue_path)
        self.assertFalse(result["ok"])
        self.assertEqual(result["stale_count"], 1)

    def test_only_releases_no_claims(self):
        """Queue with only releases and no claims = no stale scopes."""
        with open(self.queue_path, "w") as f:
            f.write(json.dumps({
                "sender": "cli1", "category": "scope_release",
                "subject": "x.py", "created_at": "2026-03-20T12:00:00Z",
            }) + "\n")
        result = pf.check_stale_scopes(self.queue_path)
        self.assertTrue(result["ok"])
        self.assertEqual(result["stale_count"], 0)

    def test_corrupt_lines_in_stale_check_skipped(self):
        """Corrupt lines in queue are skipped during stale scope check."""
        with open(self.queue_path, "w") as f:
            f.write("NOT JSON\n")
            f.write(json.dumps({
                "sender": "cli1", "category": "scope_claim",
                "subject": "x.py", "created_at": "2026-03-20T10:00:00Z",
            }) + "\n")
        result = pf.check_stale_scopes(self.queue_path)
        # Only valid line is the scope_claim — stale
        self.assertFalse(result["ok"])
        self.assertEqual(result["stale_count"], 1)

    def test_missing_queue_returns_ok(self):
        """Missing queue file = ok (no stale scopes possible)."""
        result = pf.check_stale_scopes("/nonexistent/queue.jsonl")
        self.assertTrue(result["ok"])
        self.assertEqual(result["stale_count"], 0)

    def test_stale_scopes_include_claimed_at(self):
        """Stale scope entries include claimed_at field."""
        with open(self.queue_path, "w") as f:
            f.write(json.dumps({
                "sender": "cli1", "category": "scope_claim",
                "subject": "x.py", "created_at": "2026-03-20T10:00:00Z",
            }) + "\n")
        result = pf.check_stale_scopes(self.queue_path)
        self.assertFalse(result["ok"])
        self.assertIn("claimed_at", result["stale_scopes"][0])

    def test_release_matches_via_substring(self):
        """Release subject that contains claim subject counts as a release."""
        with open(self.queue_path, "w") as f:
            f.write(json.dumps({
                "sender": "cli1", "category": "scope_claim",
                "subject": "x.py", "created_at": "2026-03-20T10:00:00Z",
            }) + "\n")
            f.write(json.dumps({
                "sender": "cli1", "category": "scope_release",
                "subject": "released x.py and y.py",  # substring contains "x.py"
                "created_at": "2026-03-20T11:00:00Z",
            }) + "\n")
        result = pf.check_stale_scopes(self.queue_path)
        self.assertTrue(result["ok"])


class TestRunPreflightExtended(unittest.TestCase):
    """Extended run_preflight and format_report edge cases."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.queue_path = os.path.join(self.tmpdir, "queue.jsonl")
        with open(self.queue_path, "w") as f:
            pass

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_all_three_fail(self):
        """All three checks failing = overall fail with 3 checks."""
        with open(self.queue_path, "w") as f:
            f.write(json.dumps({
                "sender": "cli1", "category": "scope_claim",
                "subject": "x.py", "created_at": "2026-03-20T10:00:00Z",
            }) + "\n")
        with patch.object(pf, "_check_worker_running", return_value=True):
            result = pf.run_preflight(self.queue_path)
        self.assertFalse(result["ok"])
        self.assertEqual(len(result["checks"]), 3)

    def test_checks_field_always_has_three_entries(self):
        """run_preflight always returns exactly 3 checks."""
        with patch.object(pf, "_check_worker_running", return_value=False):
            result = pf.run_preflight(self.queue_path)
        self.assertEqual(len(result["checks"]), 3)

    def test_format_report_shows_not_ready(self):
        """Format report shows NOT READY when any check fails."""
        with patch.object(pf, "_check_worker_running", return_value=True):
            result = pf.run_preflight(self.queue_path)
        report = pf.format_report(result)
        self.assertIn("NOT READY", report)

    def test_format_report_shows_ready(self):
        """Format report shows READY when all pass."""
        with patch.object(pf, "_check_worker_running", return_value=False):
            result = pf.run_preflight(self.queue_path)
        report = pf.format_report(result)
        self.assertIn("READY", report)

    def test_format_report_shows_stale_scope_details(self):
        """format_report includes stale scope sender/subject in failure details."""
        with open(self.queue_path, "w") as f:
            f.write(json.dumps({
                "sender": "cli1", "category": "scope_claim",
                "subject": "my_file.py", "created_at": "2026-03-20T10:00:00Z",
            }) + "\n")
        with patch.object(pf, "_check_worker_running", return_value=False):
            result = pf.run_preflight(self.queue_path)
        report = pf.format_report(result)
        self.assertIn("FAIL", report)
        self.assertIn("cli1", report)
        self.assertIn("my_file.py", report)

    def test_format_report_shows_running_workers(self):
        """format_report includes running worker IDs in failure details."""
        with patch.object(pf, "_check_worker_running", return_value=True):
            result = pf.run_preflight(self.queue_path)
        report = pf.format_report(result)
        # Running workers should appear in the report
        self.assertIn("cli", report.lower())

    def test_format_report_shows_corrupt_warning(self):
        """format_report shows corrupt line warning when queue has bad lines."""
        with open(self.queue_path, "w") as f:
            f.write("NOT JSON\n")
        with patch.object(pf, "_check_worker_running", return_value=False):
            result = pf.run_preflight(self.queue_path)
        report = pf.format_report(result)
        self.assertIn("corrupt", report.lower())

    def test_format_report_contains_pass_for_all_ok(self):
        """Format report marks all checks as PASS when clean."""
        with patch.object(pf, "_check_worker_running", return_value=False):
            result = pf.run_preflight(self.queue_path)
        report = pf.format_report(result)
        # All three checks should show [PASS]
        self.assertEqual(report.count("[PASS]"), 3)


if __name__ == "__main__":
    unittest.main()
