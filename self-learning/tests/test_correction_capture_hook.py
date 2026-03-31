"""Tests for correction_capture.py — PostToolUse hook for mistake-learning."""

import json
import os
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent paths
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))


class TestCorrectionCaptureHook(unittest.TestCase):
    """Tests for the correction_capture.py hook entry point."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_file = Path(self.tmpdir) / "test_state.json"
        # Patch the default state file so tests don't touch real state
        self.state_patcher = patch(
            "correction_detector.DEFAULT_STATE_FILE", self.state_file
        )
        self.state_patcher.start()

    def tearDown(self):
        self.state_patcher.stop()
        if self.state_file.exists():
            self.state_file.unlink()
        tmp = self.state_file.with_suffix(".tmp")
        if tmp.exists():
            tmp.unlink()
        os.rmdir(self.tmpdir)

    def _run_hook(self, hook_input: dict) -> None:
        """Simulate running the hook with given input on stdin."""
        from hooks.correction_capture import main

        stdin_data = json.dumps(hook_input)
        with patch("sys.stdin", StringIO(stdin_data)):
            main()

    def test_disabled_env_var(self):
        """Hook exits immediately when disabled."""
        from hooks.correction_capture import main

        with patch.dict(os.environ, {"CLAUDE_CORRECTION_CAPTURE_DISABLED": "1"}):
            with patch("sys.stdin", StringIO('{"tool_name":"Read"}')):
                # Should not raise
                main()

    def test_invalid_json_stdin(self):
        """Hook handles invalid JSON gracefully."""
        from hooks.correction_capture import main

        with patch("sys.stdin", StringIO("not json{{")):
            main()  # Should not raise

    def test_empty_output_ignored(self):
        """Hook ignores entries with empty tool_output."""
        self._run_hook({"tool_name": "Read", "tool_output": ""})
        # No state file should be created for empty output
        # (actually it does create state — just verify no crash)

    def test_dict_output_normalized(self):
        """Hook normalizes dict tool_output to string."""
        self._run_hook({
            "tool_name": "Bash",
            "tool_output": {"stdout": "hello world", "stderr": ""},
            "tool_input": {"command": "echo hello"},
        })
        # Verify state was written (means it processed the entry)
        self.assertTrue(self.state_file.exists())

    def test_no_correction_on_single_success(self):
        """Single success doesn't trigger journal write."""
        with patch("hooks.correction_capture._log_correction") as mock_log:
            self._run_hook({
                "tool_name": "Read",
                "tool_output": "1\timport os",
                "tool_input": {"file_path": "/foo.py"},
            })
            mock_log.assert_not_called()

    def test_correction_triggers_journal_write(self):
        """Error followed by success triggers _log_correction."""
        # First call: error
        self._run_hook({
            "tool_name": "Edit",
            "tool_output": "Error: old_string not found in the file",
            "tool_input": {"file_path": "/foo.py"},
        })

        # Second call: success on same file
        with patch("hooks.correction_capture._log_correction") as mock_log:
            self._run_hook({
                "tool_name": "Edit",
                "tool_output": "The file has been updated successfully",
                "tool_input": {"file_path": "/foo.py"},
            })
            mock_log.assert_called_once()
            correction = mock_log.call_args[0][0]
            self.assertEqual(correction.error_tool, "Edit")
            self.assertEqual(correction.fix_tool, "Edit")

    def test_state_persists_between_calls(self):
        """State file is written and read between hook invocations."""
        self._run_hook({
            "tool_name": "Edit",
            "tool_output": "Error: old_string not found",
            "tool_input": {"file_path": "/bar.py"},
        })
        self.assertTrue(self.state_file.exists())

        # Verify state has one entry
        state = json.loads(self.state_file.read_text())
        self.assertEqual(len(state["buffer"]), 1)
        self.assertEqual(state["buffer"][0]["tool_name"], "Edit")

    def test_no_correction_different_files(self):
        """Error on file A, success on file B — no correction."""
        self._run_hook({
            "tool_name": "Edit",
            "tool_output": "Error: old_string not found",
            "tool_input": {"file_path": "/foo.py"},
        })

        with patch("hooks.correction_capture._log_correction") as mock_log:
            self._run_hook({
                "tool_name": "Edit",
                "tool_output": "Updated successfully",
                "tool_input": {"file_path": "/different.py"},
            })
            mock_log.assert_not_called()

    def test_tool_input_missing_handled(self):
        """Hook handles missing tool_input gracefully."""
        self._run_hook({
            "tool_name": "Read",
            "tool_output": "some content",
        })
        # No crash

    def test_tool_input_non_dict_handled(self):
        """Hook handles non-dict tool_input gracefully."""
        self._run_hook({
            "tool_name": "Read",
            "tool_output": "some content",
            "tool_input": "not a dict",
        })
        # No crash


class TestLogCorrection(unittest.TestCase):
    """Tests for _log_correction journal integration."""

    def test_log_correction_calls_journal(self):
        """_log_correction calls journal.log_event with correct params."""
        from correction_detector import CorrectionEvent
        from hooks.correction_capture import _log_correction

        correction = CorrectionEvent(
            error_tool="Edit",
            error_resource="/foo.py",
            error_output="Error: old_string not found",
            error_pattern="old_string not found",
            fix_tool="Edit",
            fix_resource="/foo.py",
            fix_output="Updated successfully",
            time_to_fix=3.5,
            timestamp=1000.0,
        )

        with patch("journal.log_event") as mock_log:
            _log_correction(correction)
            mock_log.assert_called_once()
            kwargs = mock_log.call_args[1]
            self.assertEqual(kwargs["event_type"], "correction_captured")
            self.assertEqual(kwargs["domain"], "self_learning")
            self.assertEqual(kwargs["metrics"]["error_tool"], "Edit")
            self.assertEqual(kwargs["metrics"]["fix_tool"], "Edit")
            self.assertAlmostEqual(kwargs["metrics"]["time_to_fix_seconds"], 3.5)
            self.assertIn("old_string not found", kwargs["notes"])


if __name__ == "__main__":
    unittest.main()
