#!/usr/bin/env python3
"""
Tests for failure_capture.py — PostToolUseFailure hook.

Tests that definitive tool failures are fed to the correction detector
and logged to the journal.

Run: python3 self-learning/tests/test_failure_capture.py
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from io import StringIO

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))

from hooks.failure_capture import main


class TestFailureCapture(unittest.TestCase):
    """Test the failure_capture hook main() function."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_file = os.path.join(self.tmpdir, "detector.json")
        self.journal_file = os.path.join(self.tmpdir, "journal.jsonl")

    def tearDown(self):
        for f in [self.state_file, self.journal_file]:
            if os.path.exists(f):
                os.unlink(f)
        os.rmdir(self.tmpdir)

    def _run_hook(self, hook_input):
        """Run the hook with given input on stdin."""
        stdin_data = json.dumps(hook_input)
        with patch("sys.stdin", StringIO(stdin_data)), \
             patch("hooks.failure_capture.CorrectionDetector") as MockDetector, \
             patch("hooks.failure_capture._log_failure") as mock_log:
            instance = MagicMock()
            MockDetector.return_value = instance
            instance.load_state.return_value = True

            main()

            return instance, mock_log

    def test_basic_failure(self):
        """Tool failure should be fed to detector and logged."""
        detector, mock_log = self._run_hook({
            "tool_name": "Edit",
            "tool_output": "old_string not found in file",
            "tool_input": {"file_path": "/tmp/test.py"},
        })
        detector.add.assert_called_once()
        detector.save_state.assert_called_once()
        mock_log.assert_called_once()

    def test_dict_output_extracts_error(self):
        """Dict tool_output should extract error field."""
        detector, _ = self._run_hook({
            "tool_name": "Bash",
            "tool_output": {"error": "command not found", "stderr": "bash: foo: command not found"},
            "tool_input": {"command": "foo"},
        })
        call_args = detector.add.call_args
        # Should use the error field
        self.assertIn("command not found", call_args.kwargs.get("tool_output", call_args[1].get("tool_output", "")))

    def test_empty_output_gets_placeholder(self):
        """Empty output should get a placeholder error message."""
        detector, _ = self._run_hook({
            "tool_name": "Read",
            "tool_output": "",
            "tool_input": {"file_path": "/nonexistent"},
        })
        call_args = detector.add.call_args
        output = call_args.kwargs.get("tool_output", call_args[1].get("tool_output", ""))
        self.assertIn("failed", output.lower())

    def test_disabled_via_env(self):
        """Hook should be a no-op when disabled."""
        with patch.dict(os.environ, {"CLAUDE_FAILURE_CAPTURE_DISABLED": "1"}), \
             patch("sys.stdin", StringIO(json.dumps({"tool_name": "Edit"}))), \
             patch("hooks.failure_capture.CorrectionDetector") as MockDetector:
            main()
            MockDetector.assert_not_called()

    def test_invalid_json_stdin(self):
        """Invalid JSON on stdin should not crash."""
        with patch("sys.stdin", StringIO("not json")), \
             patch("hooks.failure_capture.CorrectionDetector") as MockDetector:
            main()  # Should not raise
            MockDetector.assert_not_called()

    def test_error_prefix_added(self):
        """Output not starting with 'Error' should get prefix for pattern matching."""
        detector, _ = self._run_hook({
            "tool_name": "Bash",
            "tool_output": "permission denied",
            "tool_input": {"command": "cat /root/secret"},
        })
        call_args = detector.add.call_args
        output = call_args.kwargs.get("tool_output", call_args[1].get("tool_output", ""))
        self.assertTrue(output.startswith("Error:"))

    def test_error_prefix_not_doubled(self):
        """Output already starting with 'Error' should not get double prefix."""
        detector, _ = self._run_hook({
            "tool_name": "Bash",
            "tool_output": "Error: file not found",
            "tool_input": {"command": "cat missing.txt"},
        })
        call_args = detector.add.call_args
        output = call_args.kwargs.get("tool_output", call_args[1].get("tool_output", ""))
        self.assertFalse(output.startswith("Error: Error:"))

    def test_tool_input_passed_through(self):
        """Tool input should be passed to the detector."""
        detector, _ = self._run_hook({
            "tool_name": "Edit",
            "tool_output": "old_string not unique",
            "tool_input": {"file_path": "/tmp/foo.py", "old_string": "def bar"},
        })
        call_args = detector.add.call_args
        tool_input = call_args.kwargs.get("tool_input", call_args[1].get("tool_input", {}))
        self.assertEqual(tool_input["file_path"], "/tmp/foo.py")

    def test_non_dict_tool_input_handled(self):
        """Non-dict tool_input should be converted to empty dict."""
        detector, _ = self._run_hook({
            "tool_name": "Bash",
            "tool_output": "error",
            "tool_input": "not a dict",
        })
        call_args = detector.add.call_args
        tool_input = call_args.kwargs.get("tool_input", call_args[1].get("tool_input", {}))
        self.assertEqual(tool_input, {})


class TestLogFailure(unittest.TestCase):
    """Test _log_failure journal logging."""

    def test_log_failure_calls_journal(self):
        from hooks.failure_capture import _log_failure
        with patch("journal.log_event") as mock_log:
            _log_failure("Edit", "old_string not found", {"file_path": "/tmp/test.py"})
            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args[1]
            self.assertEqual(call_kwargs["event_type"], "error")
            self.assertEqual(call_kwargs["domain"], "self_learning")
            self.assertIn("Edit", call_kwargs["notes"])

    def test_long_resource_truncated(self):
        from hooks.failure_capture import _log_failure
        with patch("journal.log_event") as mock_log:
            long_cmd = "x" * 500
            _log_failure("Bash", "error", {"command": long_cmd})
            call_kwargs = mock_log.call_args[1]
            self.assertLessEqual(len(call_kwargs["metrics"]["resource"]), 200)


if __name__ == "__main__":
    unittest.main()
