"""Tests for worker_verifier.py — Automated worker output verification.

Based on MAST failure taxonomy (arXiv:2503.13657) Gap #3: insufficient task
verification. Workers report 'done' but coordinator doesn't validate output
before accepting. This module provides automated verification.
"""
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from worker_verifier import (
    VerificationResult,
    WorkerVerifier,
    check_tests_pass,
    check_no_regressions,
    check_committed,
    verify_worker_output,
)


class TestVerificationResult(unittest.TestCase):
    """Test VerificationResult data container."""

    def test_passed_result(self):
        r = VerificationResult(passed=True, check_name="tests", message="All pass")
        self.assertTrue(r.passed)
        self.assertEqual(r.check_name, "tests")

    def test_failed_result(self):
        r = VerificationResult(passed=False, check_name="tests", message="3 failures")
        self.assertFalse(r.passed)

    def test_to_dict(self):
        r = VerificationResult(passed=True, check_name="tests", message="OK")
        d = r.to_dict()
        self.assertEqual(d["passed"], True)
        self.assertEqual(d["check_name"], "tests")
        self.assertEqual(d["message"], "OK")


class TestCheckTestsPass(unittest.TestCase):
    """Test the test runner verification check."""

    def test_passing_tests(self):
        """When test command returns 0, check passes."""
        with patch("worker_verifier.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "10 tests passed"
            mock_run.return_value.stderr = ""
            result = check_tests_pass(test_command="python3 -m pytest")
            self.assertTrue(result.passed)
            self.assertEqual(result.check_name, "tests_pass")

    def test_failing_tests(self):
        """When test command returns non-zero, check fails."""
        with patch("worker_verifier.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stdout = "3 failures"
            mock_run.return_value.stderr = ""
            result = check_tests_pass(test_command="python3 -m pytest")
            self.assertFalse(result.passed)

    def test_test_command_timeout(self):
        """When test command times out, check fails gracefully."""
        import subprocess
        with patch("worker_verifier.subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 60)):
            result = check_tests_pass(test_command="python3 -m pytest", timeout=60)
            self.assertFalse(result.passed)
            self.assertIn("timeout", result.message.lower())


class TestCheckNoRegressions(unittest.TestCase):
    """Test regression detection check."""

    def test_no_regression(self):
        """Same or higher test count = no regression."""
        result = check_no_regressions(before_count=100, after_count=105)
        self.assertTrue(result.passed)
        self.assertIn("105", result.message)

    def test_regression_detected(self):
        """Lower test count = regression."""
        result = check_no_regressions(before_count=100, after_count=95)
        self.assertFalse(result.passed)
        self.assertIn("regression", result.message.lower())

    def test_same_count(self):
        result = check_no_regressions(before_count=100, after_count=100)
        self.assertTrue(result.passed)

    def test_zero_before(self):
        """No previous count = pass (first run)."""
        result = check_no_regressions(before_count=0, after_count=50)
        self.assertTrue(result.passed)


class TestCheckCommitted(unittest.TestCase):
    """Test git commit verification."""

    def test_clean_working_tree(self):
        """No uncommitted changes = pass."""
        with patch("worker_verifier.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = ""
            result = check_committed()
            self.assertTrue(result.passed)

    def test_uncommitted_changes(self):
        """Uncommitted changes = fail."""
        with patch("worker_verifier.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = " M src/foo.py\n M src/bar.py\n"
            result = check_committed()
            self.assertFalse(result.passed)
            self.assertIn("uncommitted", result.message.lower())


class TestWorkerVerifier(unittest.TestCase):
    """Test WorkerVerifier orchestrator."""

    def test_all_checks_pass(self):
        """When all checks pass, overall verdict is ACCEPT."""
        verifier = WorkerVerifier()
        results = [
            VerificationResult(True, "tests_pass", "OK"),
            VerificationResult(True, "no_regressions", "105 >= 100"),
            VerificationResult(True, "committed", "Clean"),
        ]
        verdict = verifier.judge(results)
        self.assertEqual(verdict["verdict"], "ACCEPT")
        self.assertTrue(verdict["all_passed"])

    def test_one_check_fails(self):
        """When any check fails, verdict is REVIEW."""
        verifier = WorkerVerifier()
        results = [
            VerificationResult(True, "tests_pass", "OK"),
            VerificationResult(False, "no_regressions", "95 < 100 — regression"),
            VerificationResult(True, "committed", "Clean"),
        ]
        verdict = verifier.judge(results)
        self.assertEqual(verdict["verdict"], "REVIEW")
        self.assertFalse(verdict["all_passed"])
        self.assertEqual(len(verdict["failures"]), 1)

    def test_all_checks_fail(self):
        """When all checks fail, verdict is REJECT."""
        verifier = WorkerVerifier()
        results = [
            VerificationResult(False, "tests_pass", "3 failures"),
            VerificationResult(False, "no_regressions", "regression"),
            VerificationResult(False, "committed", "uncommitted"),
        ]
        verdict = verifier.judge(results)
        self.assertEqual(verdict["verdict"], "REJECT")
        self.assertEqual(len(verdict["failures"]), 3)

    def test_verdict_to_json(self):
        verifier = WorkerVerifier()
        results = [VerificationResult(True, "tests_pass", "OK")]
        verdict = verifier.judge(results)
        json_str = json.dumps(verdict)
        self.assertIn("ACCEPT", json_str)

    def test_empty_results(self):
        """No checks run = ACCEPT (nothing to fail)."""
        verifier = WorkerVerifier()
        verdict = verifier.judge([])
        self.assertEqual(verdict["verdict"], "ACCEPT")


class TestVerifyWorkerOutput(unittest.TestCase):
    """Test the high-level verify_worker_output() function."""

    @patch("worker_verifier.check_committed")
    @patch("worker_verifier.check_no_regressions")
    @patch("worker_verifier.check_tests_pass")
    def test_full_pipeline(self, mock_tests, mock_regression, mock_committed):
        mock_tests.return_value = VerificationResult(True, "tests_pass", "OK")
        mock_regression.return_value = VerificationResult(True, "no_regressions", "OK")
        mock_committed.return_value = VerificationResult(True, "committed", "OK")

        verdict = verify_worker_output(
            test_command="python3 -m pytest",
            before_count=100,
            after_count=105,
        )
        self.assertEqual(verdict["verdict"], "ACCEPT")
        self.assertEqual(len(verdict["results"]), 3)

    @patch("worker_verifier.check_committed")
    @patch("worker_verifier.check_no_regressions")
    @patch("worker_verifier.check_tests_pass")
    def test_pipeline_with_failure(self, mock_tests, mock_regression, mock_committed):
        mock_tests.return_value = VerificationResult(False, "tests_pass", "FAIL")
        mock_regression.return_value = VerificationResult(True, "no_regressions", "OK")
        mock_committed.return_value = VerificationResult(True, "committed", "OK")

        verdict = verify_worker_output(
            test_command="python3 -m pytest",
            before_count=100,
            after_count=105,
        )
        self.assertEqual(verdict["verdict"], "REVIEW")

    @patch("worker_verifier.check_committed")
    @patch("worker_verifier.check_tests_pass")
    def test_pipeline_skip_regression_check(self, mock_tests, mock_committed):
        """When before_count is None, skip regression check."""
        mock_tests.return_value = VerificationResult(True, "tests_pass", "OK")
        mock_committed.return_value = VerificationResult(True, "committed", "OK")

        verdict = verify_worker_output(
            test_command="python3 -m pytest",
            before_count=None,
            after_count=None,
        )
        self.assertEqual(verdict["verdict"], "ACCEPT")
        self.assertEqual(len(verdict["results"]), 2)


if __name__ == "__main__":
    unittest.main()
