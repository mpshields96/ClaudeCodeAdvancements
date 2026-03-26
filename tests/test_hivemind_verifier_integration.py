"""Tests for hivemind_session_validator + worker_verifier integration.

Wires worker_verifier output checks into the hivemind session validation
workflow so coordinators automatically verify worker output quality.
"""
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, ROOT_DIR)

import hivemind_session_validator as hsv
from worker_verifier import VerificationResult


def _make_queue(tmpdir, messages):
    path = os.path.join(tmpdir, "queue.jsonl")
    with open(path, "w") as f:
        for msg in messages:
            f.write(json.dumps(msg) + "\n")
    return path


def _clean_session_messages(worker_id="cli1"):
    """Standard clean session: assigned, completed, scope released."""
    return [
        {"sender": "desktop", "target": worker_id, "category": "handoff",
         "subject": "Build feature X", "priority": "high", "status": "read",
         "created_at": "2026-03-26T10:00:00Z", "read_at": "2026-03-26T10:01:00Z"},
        {"sender": worker_id, "target": "desktop", "category": "scope_claim",
         "subject": "feature_x", "priority": "high", "status": "unread",
         "created_at": "2026-03-26T10:01:30Z"},
        {"sender": worker_id, "target": "desktop", "category": "handoff",
         "subject": "WRAP: A — Built feature X. Tests: 15 new.", "priority": "high",
         "status": "unread", "created_at": "2026-03-26T10:30:00Z"},
        {"sender": worker_id, "target": "desktop", "category": "scope_release",
         "subject": "feature_x", "priority": "medium", "status": "unread",
         "created_at": "2026-03-26T10:30:05Z"},
    ]


class TestValidateWithVerification(unittest.TestCase):
    """Test the combined validation + verification workflow."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_all_pass_returns_accept(self):
        """Clean session + all verification checks pass = ACCEPT."""
        queue_path = _make_queue(self.tmpdir, _clean_session_messages())
        with patch("hivemind_session_validator.verify_worker_output") as mock_verify:
            mock_verify.return_value = {
                "verdict": "ACCEPT",
                "all_passed": True,
                "failures": [],
                "results": [
                    {"passed": True, "check_name": "tests_pass", "message": "OK"},
                    {"passed": True, "check_name": "no_regressions", "message": "OK"},
                    {"passed": True, "check_name": "committed", "message": "OK"},
                ],
            }
            result = hsv.validate_with_verification(
                "cli1", queue_path=queue_path,
                test_command="echo pass", before_count=100, after_count=110,
            )
        self.assertEqual(result["verdict"], "ACCEPT")
        self.assertTrue(result["task_assigned"])
        self.assertTrue(result["task_completed"])
        self.assertEqual(result["output_verdict"], "ACCEPT")

    def test_queue_pass_but_tests_fail_returns_review(self):
        """Clean session but worker output fails tests = REVIEW."""
        queue_path = _make_queue(self.tmpdir, _clean_session_messages())
        with patch("hivemind_session_validator.verify_worker_output") as mock_verify:
            mock_verify.return_value = {
                "verdict": "REJECT",
                "all_passed": False,
                "failures": ["tests_pass"],
                "results": [
                    {"passed": False, "check_name": "tests_pass", "message": "Tests failed"},
                ],
            }
            result = hsv.validate_with_verification(
                "cli1", queue_path=queue_path,
                test_command="echo fail", before_count=100, after_count=95,
            )
        # Queue PASS + output REJECT = worst case wins = REVIEW (not full FAIL)
        self.assertEqual(result["verdict"], "REVIEW")
        self.assertEqual(result["output_verdict"], "REJECT")

    def test_queue_fail_overrides_output_accept(self):
        """No task assigned (queue FAIL) even with output ACCEPT = FAIL."""
        queue_path = _make_queue(self.tmpdir, [])  # Empty queue = no assignment
        with patch("hivemind_session_validator.verify_worker_output") as mock_verify:
            mock_verify.return_value = {
                "verdict": "ACCEPT",
                "all_passed": True,
                "failures": [],
                "results": [],
            }
            result = hsv.validate_with_verification(
                "cli1", queue_path=queue_path,
                test_command="echo pass",
            )
        self.assertEqual(result["verdict"], "FAIL")
        self.assertFalse(result["task_assigned"])

    def test_no_verification_skips_output_check(self):
        """When skip_verification=True, only queue validation runs."""
        queue_path = _make_queue(self.tmpdir, _clean_session_messages())
        result = hsv.validate_with_verification(
            "cli1", queue_path=queue_path, skip_verification=True,
        )
        self.assertEqual(result["verdict"], "PASS")
        self.assertNotIn("output_verdict", result)

    def test_output_review_with_clean_queue_returns_review(self):
        """Queue PASS + output REVIEW = REVIEW (downgrades from PASS)."""
        queue_path = _make_queue(self.tmpdir, _clean_session_messages())
        with patch("hivemind_session_validator.verify_worker_output") as mock_verify:
            mock_verify.return_value = {
                "verdict": "REVIEW",
                "all_passed": False,
                "failures": ["committed"],
                "results": [
                    {"passed": True, "check_name": "tests_pass", "message": "OK"},
                    {"passed": False, "check_name": "committed", "message": "2 uncommitted"},
                ],
            }
            result = hsv.validate_with_verification(
                "cli1", queue_path=queue_path,
                test_command="echo pass",
            )
        self.assertEqual(result["verdict"], "REVIEW")
        self.assertEqual(result["output_verdict"], "REVIEW")
        self.assertIn("committed", result["output_failures"])

    def test_queue_warnings_plus_output_accept(self):
        """Queue PASS_WITH_WARNINGS + output ACCEPT = PASS_WITH_WARNINGS."""
        msgs = _clean_session_messages()
        msgs.append({
            "sender": "cli1", "target": "desktop", "category": "conflict_alert",
            "subject": "Conflict on shared file", "priority": "high", "status": "unread",
            "created_at": "2026-03-26T10:20:00Z",
        })
        queue_path = _make_queue(self.tmpdir, msgs)
        with patch("hivemind_session_validator.verify_worker_output") as mock_verify:
            mock_verify.return_value = {
                "verdict": "ACCEPT",
                "all_passed": True,
                "failures": [],
                "results": [],
            }
            result = hsv.validate_with_verification(
                "cli1", queue_path=queue_path,
                test_command="echo pass",
            )
        self.assertEqual(result["verdict"], "PASS_WITH_WARNINGS")
        self.assertEqual(result["output_verdict"], "ACCEPT")

    def test_verification_kwargs_forwarded(self):
        """Test command, before/after counts, timeout forwarded to verify_worker_output."""
        queue_path = _make_queue(self.tmpdir, _clean_session_messages())
        with patch("hivemind_session_validator.verify_worker_output") as mock_verify:
            mock_verify.return_value = {
                "verdict": "ACCEPT", "all_passed": True,
                "failures": [], "results": [],
            }
            hsv.validate_with_verification(
                "cli1", queue_path=queue_path,
                test_command="pytest -x", before_count=200, after_count=215,
                timeout=300,
            )
            mock_verify.assert_called_once_with(
                test_command="pytest -x",
                before_count=200,
                after_count=215,
                timeout=300,
            )

    def test_verification_exception_returns_review(self):
        """If verify_worker_output raises, degrade gracefully to REVIEW."""
        queue_path = _make_queue(self.tmpdir, _clean_session_messages())
        with patch("hivemind_session_validator.verify_worker_output") as mock_verify:
            mock_verify.side_effect = Exception("subprocess crash")
            result = hsv.validate_with_verification(
                "cli1", queue_path=queue_path,
                test_command="echo crash",
            )
        # Queue was clean = PASS, but verification errored = downgrade to REVIEW
        self.assertEqual(result["verdict"], "REVIEW")
        self.assertEqual(result["output_verdict"], "ERROR")
        self.assertIn("subprocess crash", result.get("output_error", ""))


class TestFormatForInitWithVerification(unittest.TestCase):
    """Test that format_for_init includes verification info when available."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.log_path = os.path.join(self.tmpdir, "hivemind_sessions.jsonl")

    def test_includes_output_verdict_in_history(self):
        """When session records include output_verdict, format_for_init reflects it."""
        entry = {
            "session": 191, "session_id": "S191",
            "timestamp": "2026-03-26T04:00:00Z",
            "verdict": "ACCEPT", "worker_id": "cli1",
            "task_assigned": True, "task_completed": True,
            "output_verdict": "ACCEPT",
        }
        with open(self.log_path, "w") as f:
            f.write(json.dumps(entry) + "\n")

        output = hsv.format_for_init(path=self.log_path)
        self.assertIn("1 sessions", output)


class TestVerdictCombination(unittest.TestCase):
    """Test the verdict combination logic."""

    def test_combine_pass_accept(self):
        self.assertEqual(hsv._combine_verdicts("PASS", "ACCEPT"), "ACCEPT")

    def test_combine_pass_review(self):
        self.assertEqual(hsv._combine_verdicts("PASS", "REVIEW"), "REVIEW")

    def test_combine_pass_reject(self):
        self.assertEqual(hsv._combine_verdicts("PASS", "REJECT"), "REVIEW")

    def test_combine_fail_accept(self):
        self.assertEqual(hsv._combine_verdicts("FAIL", "ACCEPT"), "FAIL")

    def test_combine_fail_reject(self):
        self.assertEqual(hsv._combine_verdicts("FAIL", "REJECT"), "FAIL")

    def test_combine_warnings_accept(self):
        self.assertEqual(hsv._combine_verdicts("PASS_WITH_WARNINGS", "ACCEPT"), "PASS_WITH_WARNINGS")

    def test_combine_warnings_review(self):
        self.assertEqual(hsv._combine_verdicts("PASS_WITH_WARNINGS", "REVIEW"), "REVIEW")

    def test_combine_pass_error(self):
        self.assertEqual(hsv._combine_verdicts("PASS", "ERROR"), "REVIEW")


if __name__ == "__main__":
    unittest.main()
