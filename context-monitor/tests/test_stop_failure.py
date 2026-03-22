#!/usr/bin/env python3
"""Tests for stop_failure.py — StopFailure hook handler (CC v2.1.78+)."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks"))

from stop_failure import classify_error, update_state_file, STATE_FILE


class TestClassifyError(unittest.TestCase):
    """Tests for error classification."""

    def test_rate_limit_429(self):
        result = classify_error({"error": "429 Too Many Requests"})
        self.assertEqual(result["error_type"], "rate_limit")
        self.assertTrue(result["is_rate_limit"])
        self.assertEqual(result["severity"], "HIGH")

    def test_rate_limit_keyword(self):
        result = classify_error({"error": "Rate limit exceeded"})
        self.assertTrue(result["is_rate_limit"])

    def test_auth_failure_401(self):
        result = classify_error({"error": "401 Unauthorized"})
        self.assertEqual(result["error_type"], "auth_failure")
        self.assertFalse(result["is_rate_limit"])
        self.assertEqual(result["severity"], "CRITICAL")

    def test_auth_failure_403(self):
        result = classify_error({"error": "403 Forbidden"})
        self.assertEqual(result["error_type"], "auth_failure")

    def test_server_error_500(self):
        result = classify_error({"error": "500 Internal Server Error"})
        self.assertEqual(result["error_type"], "server_error")
        self.assertEqual(result["severity"], "MEDIUM")

    def test_server_error_503(self):
        result = classify_error({"error": "503 Service Unavailable"})
        self.assertEqual(result["error_type"], "server_error")

    def test_unknown_error(self):
        result = classify_error({"error": "Something went wrong"})
        self.assertEqual(result["error_type"], "unknown")
        self.assertEqual(result["severity"], "LOW")

    def test_empty_input(self):
        result = classify_error({})
        self.assertEqual(result["error_type"], "unknown")

    def test_recommendation_present(self):
        result = classify_error({"error": "429"})
        self.assertIn("recommendation", result)
        self.assertTrue(len(result["recommendation"]) > 0)


class TestUpdateStateFile(unittest.TestCase):
    """Tests for state file updates."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_path = os.path.join(self.tmpdir, "state.json")
        # Monkey-patch STATE_FILE
        import stop_failure
        self._orig = stop_failure.STATE_FILE
        stop_failure.STATE_FILE = type(self._orig)(self.state_path)

    def tearDown(self):
        import shutil
        import stop_failure
        stop_failure.STATE_FILE = self._orig
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_creates_state_file(self):
        classification = classify_error({"error": "429"})
        update_state_file(classification)
        self.assertTrue(os.path.exists(self.state_path))

    def test_records_failure(self):
        classification = classify_error({"error": "429"})
        update_state_file(classification)
        with open(self.state_path) as f:
            state = json.load(f)
        self.assertEqual(len(state["api_failures"]), 1)
        self.assertEqual(state["last_failure_type"], "rate_limit")

    def test_appends_failures(self):
        for error in ["429", "500", "401"]:
            classification = classify_error({"error": error})
            update_state_file(classification)
        with open(self.state_path) as f:
            state = json.load(f)
        self.assertEqual(len(state["api_failures"]), 3)

    def test_caps_at_20(self):
        for i in range(25):
            classification = classify_error({"error": f"error {i}"})
            update_state_file(classification)
        with open(self.state_path) as f:
            state = json.load(f)
        self.assertEqual(len(state["api_failures"]), 20)

    def test_counts_rate_limits(self):
        for error in ["429", "500", "429", "429"]:
            classification = classify_error({"error": error})
            update_state_file(classification)
        with open(self.state_path) as f:
            state = json.load(f)
        self.assertEqual(state["recent_rate_limit_count"], 3)

    def test_handles_corrupt_state(self):
        with open(self.state_path, "w") as f:
            f.write("not json")
        classification = classify_error({"error": "429"})
        update_state_file(classification)
        with open(self.state_path) as f:
            state = json.load(f)
        self.assertEqual(len(state["api_failures"]), 1)


if __name__ == "__main__":
    unittest.main()
