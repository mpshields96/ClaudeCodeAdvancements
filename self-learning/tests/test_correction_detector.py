"""Tests for correction_detector.py — error->correction sequence detection."""

import json
import os
import sys
import time
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Add parent to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from correction_detector import (
    CorrectionDetector,
    CorrectionEvent,
    ToolResult,
    detect_error,
    extract_resource,
    DEFAULT_BUFFER_SIZE,
    DEFAULT_MAX_AGE_SECONDS,
    MAX_OUTPUT_LENGTH,
)


class TestDetectError(unittest.TestCase):
    """Tests for the error detection heuristics."""

    def test_python_traceback(self):
        output = "Traceback (most recent call last):\n  File 'test.py', line 1"
        self.assertIsNotNone(detect_error(output))

    def test_file_not_found(self):
        output = "No such file or directory: '/foo/bar.py'"
        self.assertIsNotNone(detect_error(output))

    def test_permission_denied(self):
        output = "Permission denied: cannot write to /etc/hosts"
        self.assertIsNotNone(detect_error(output))

    def test_edit_old_string_not_found(self):
        output = "Error: old_string not found in the file"
        self.assertIsNotNone(detect_error(output))

    def test_edit_not_unique(self):
        output = "The string 'foo' is not unique in the file"
        self.assertIsNotNone(detect_error(output))

    def test_file_does_not_exist(self):
        output = "File does not exist. Note: your current working directory is /foo"
        self.assertIsNotNone(detect_error(output))

    def test_syntax_error(self):
        output = "SyntaxError: invalid syntax"
        self.assertIsNotNone(detect_error(output))

    def test_import_error(self):
        output = "ImportError: cannot import name 'foo' from 'bar'"
        self.assertIsNotNone(detect_error(output))

    def test_module_not_found(self):
        output = "ModuleNotFoundError: No module named 'nonexistent'"
        self.assertIsNotNone(detect_error(output))

    def test_exit_code_nonzero(self):
        output = "Command failed with exit code 1"
        self.assertIsNotNone(detect_error(output))

    def test_assertion_error(self):
        output = "AssertionError: expected 5, got 3"
        self.assertIsNotNone(detect_error(output))

    def test_type_error(self):
        output = "TypeError: unsupported operand type(s)"
        self.assertIsNotNone(detect_error(output))

    def test_value_error(self):
        output = "ValueError: invalid literal for int()"
        self.assertIsNotNone(detect_error(output))

    def test_key_error(self):
        output = "KeyError: 'missing_key'"
        self.assertIsNotNone(detect_error(output))

    def test_attribute_error(self):
        output = "AttributeError: 'NoneType' object has no attribute 'foo'"
        self.assertIsNotNone(detect_error(output))

    def test_name_error(self):
        output = "NameError: name 'undefined_var' is not defined"
        self.assertIsNotNone(detect_error(output))

    def test_command_not_found(self):
        output = "zsh: command not found: foobar"
        self.assertIsNotNone(detect_error(output))

    def test_file_exceeds_maximum(self):
        output = "File content (50000 tokens) exceeds maximum allowed tokens (10000)"
        self.assertIsNotNone(detect_error(output))

    def test_success_output_no_error(self):
        output = "All 50 tests passed in 2.3 seconds"
        self.assertIsNone(detect_error(output))

    def test_normal_file_content_no_error(self):
        output = "1\timport os\n2\timport sys\n3\t\n4\tdef main():\n5\t    pass"
        self.assertIsNone(detect_error(output))

    def test_empty_output_no_error(self):
        self.assertIsNone(detect_error(""))

    def test_git_status_no_error(self):
        output = "On branch main\nYour branch is up to date with 'origin/main'."
        self.assertIsNone(detect_error(output))


class TestExtractResource(unittest.TestCase):
    """Tests for resource extraction from tool inputs."""

    def test_read_file_path(self):
        result = extract_resource("Read", {"file_path": "/foo/bar.py"})
        self.assertEqual(result, "/foo/bar.py")

    def test_write_file_path(self):
        result = extract_resource("Write", {"file_path": "/foo/bar.py"})
        self.assertEqual(result, "/foo/bar.py")

    def test_edit_file_path(self):
        result = extract_resource("Edit", {"file_path": "/foo/bar.py"})
        self.assertEqual(result, "/foo/bar.py")

    def test_bash_command(self):
        result = extract_resource("Bash", {"command": "python3 test.py"})
        self.assertEqual(result, "python3 test.py")

    def test_bash_long_command_truncated(self):
        cmd = "python3 " + "x" * 300
        result = extract_resource("Bash", {"command": cmd})
        self.assertEqual(len(result), 200)

    def test_glob_pattern(self):
        result = extract_resource("Glob", {"pattern": "**/*.py"})
        self.assertEqual(result, "**/*.py")

    def test_grep_pattern(self):
        result = extract_resource("Grep", {"pattern": "def foo"})
        self.assertEqual(result, "def foo")

    def test_unknown_tool(self):
        result = extract_resource("Agent", {})
        self.assertEqual(result, "Agent")

    def test_missing_file_path(self):
        result = extract_resource("Read", {})
        self.assertEqual(result, "")


class TestCorrectionDetector(unittest.TestCase):
    """Tests for the core CorrectionDetector class."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_file = Path(self.tmpdir) / "test_state.json"
        self.detector = CorrectionDetector(
            buffer_size=8,
            max_age=60,
            state_file=self.state_file,
        )

    def tearDown(self):
        if self.state_file.exists():
            self.state_file.unlink()
        os.rmdir(self.tmpdir)

    def test_no_correction_on_first_call(self):
        result = self.detector.add("Read", "file contents here", {"file_path": "/foo.py"})
        self.assertIsNone(result)

    def test_no_correction_on_consecutive_successes(self):
        self.detector.add("Read", "file contents", {"file_path": "/foo.py"})
        result = self.detector.add("Read", "more contents", {"file_path": "/foo.py"})
        self.assertIsNone(result)

    def test_no_correction_on_consecutive_errors(self):
        self.detector.add("Edit", "Error: old_string not found", {"file_path": "/foo.py"})
        result = self.detector.add("Edit", "Error: old_string not found", {"file_path": "/foo.py"})
        self.assertIsNone(result)

    def test_correction_detected_edit_fail_then_succeed(self):
        """Edit fails on a file, then Edit succeeds on the same file."""
        self.detector.add(
            "Edit",
            "Error: old_string not found in the file",
            {"file_path": "/foo.py"},
        )
        result = self.detector.add(
            "Edit",
            "The file has been updated successfully",
            {"file_path": "/foo.py"},
        )
        self.assertIsNotNone(result)
        self.assertIsInstance(result, CorrectionEvent)
        self.assertEqual(result.error_tool, "Edit")
        self.assertEqual(result.fix_tool, "Edit")
        self.assertEqual(result.error_resource, "/foo.py")

    def test_correction_detected_read_fail_then_succeed(self):
        """Read fails (file not found), then Read succeeds on same path."""
        self.detector.add(
            "Read",
            "File does not exist.",
            {"file_path": "/bar.py"},
        )
        result = self.detector.add(
            "Read",
            "1\timport os\n2\timport sys",
            {"file_path": "/bar.py"},
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.error_tool, "Read")
        self.assertEqual(result.fix_tool, "Read")

    def test_correction_detected_bash_fail_then_succeed(self):
        """Bash command fails, then similar command succeeds."""
        self.detector.add(
            "Bash",
            "ModuleNotFoundError: No module named 'foo'",
            {"command": "python3 test_foo.py"},
        )
        result = self.detector.add(
            "Bash",
            "All 5 tests passed",
            {"command": "python3 test_foo.py"},
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.error_tool, "Bash")
        self.assertEqual(result.fix_tool, "Bash")

    def test_correction_cross_tool_edit_to_write(self):
        """Edit fails, then Write to same file (rewrote instead of edited)."""
        self.detector.add(
            "Edit",
            "Error: old_string not found in the file",
            {"file_path": "/foo.py"},
        )
        result = self.detector.add(
            "Write",
            "File written successfully",
            {"file_path": "/foo.py"},
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.error_tool, "Edit")
        self.assertEqual(result.fix_tool, "Write")

    def test_no_correction_different_files(self):
        """Error on file A, success on file B — not a correction."""
        self.detector.add(
            "Edit",
            "Error: old_string not found",
            {"file_path": "/foo.py"},
        )
        result = self.detector.add(
            "Edit",
            "Updated successfully",
            {"file_path": "/bar.py"},
        )
        self.assertIsNone(result)

    def test_no_correction_different_bash_commands(self):
        """Different base commands — not a correction."""
        self.detector.add(
            "Bash",
            "command not found: foobar",
            {"command": "foobar --version"},
        )
        result = self.detector.add(
            "Bash",
            "v1.2.3",
            {"command": "python3 --version"},
        )
        self.assertIsNone(result)

    def test_time_to_fix_recorded(self):
        """Correction event records time between error and fix."""
        self.detector.add(
            "Edit",
            "Error: old_string not found",
            {"file_path": "/foo.py"},
        )
        # Small delay
        result = self.detector.add(
            "Edit",
            "Updated successfully",
            {"file_path": "/foo.py"},
        )
        self.assertIsNotNone(result)
        self.assertGreaterEqual(result.time_to_fix, 0)

    def test_stale_errors_ignored(self):
        """Errors older than max_age are not matched."""
        detector = CorrectionDetector(
            max_age=0.01,  # 10ms
            state_file=self.state_file,
        )
        detector.add(
            "Edit",
            "Error: old_string not found",
            {"file_path": "/foo.py"},
        )
        time.sleep(0.02)  # Wait past max_age
        result = detector.add(
            "Edit",
            "Updated successfully",
            {"file_path": "/foo.py"},
        )
        self.assertIsNone(result)

    def test_buffer_respects_size_limit(self):
        """Buffer doesn't grow beyond buffer_size."""
        detector = CorrectionDetector(
            buffer_size=3,
            state_file=self.state_file,
        )
        for i in range(10):
            detector.add("Read", f"content {i}", {"file_path": f"/file{i}.py"})
        self.assertLessEqual(len(detector.buffer), 3)

    def test_most_recent_error_matched(self):
        """When multiple errors exist, the most recent one is matched."""
        self.detector.add(
            "Edit",
            "Error: old_string not found",
            {"file_path": "/foo.py"},
        )
        self.detector.add(
            "Read",
            "file contents ok",
            {"file_path": "/other.py"},
        )
        self.detector.add(
            "Edit",
            "is not unique in the file",
            {"file_path": "/foo.py"},
        )
        result = self.detector.add(
            "Edit",
            "Updated successfully",
            {"file_path": "/foo.py"},
        )
        self.assertIsNotNone(result)
        # Should match the "not unique" error, not the "not found" one
        self.assertIn("not unique", result.error_pattern)

    def test_stats_tracking(self):
        """Stats are updated correctly."""
        self.detector.add("Read", "content", {"file_path": "/foo.py"})
        self.detector.add("Edit", "Error: old_string not found", {"file_path": "/bar.py"})
        self.detector.add("Edit", "Updated", {"file_path": "/bar.py"})

        stats = self.detector.stats
        self.assertEqual(stats["total_processed"], 3)
        self.assertEqual(stats["corrections_detected"], 1)
        self.assertEqual(stats["buffer_size"], 3)

    def test_empty_resource_no_match(self):
        """Empty resources don't create false corrections."""
        self.detector.add("Edit", "Error: old_string not found", {"file_path": ""})
        result = self.detector.add("Edit", "Updated successfully", {"file_path": ""})
        self.assertIsNone(result)

    def test_empty_bash_command_no_match(self):
        """Empty bash commands don't match."""
        self.detector.add("Bash", "Error: something", {"command": ""})
        result = self.detector.add("Bash", "Success", {"command": ""})
        self.assertIsNone(result)


class TestCorrectionDetectorPersistence(unittest.TestCase):
    """Tests for state persistence."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_file = Path(self.tmpdir) / "test_state.json"

    def tearDown(self):
        if self.state_file.exists():
            self.state_file.unlink()
        os.rmdir(self.tmpdir)

    def test_save_and_load_state(self):
        detector = CorrectionDetector(state_file=self.state_file)
        detector.add("Read", "content", {"file_path": "/foo.py"})
        detector.add("Edit", "Error: not found", {"file_path": "/bar.py"})
        detector.save_state()

        # Load into fresh detector
        detector2 = CorrectionDetector(state_file=self.state_file)
        self.assertTrue(detector2.load_state())
        self.assertEqual(len(detector2.buffer), 2)
        self.assertEqual(detector2.buffer[0].tool_name, "Read")
        self.assertEqual(detector2.buffer[1].tool_name, "Edit")

    def test_load_nonexistent_file(self):
        detector = CorrectionDetector(state_file=Path("/nonexistent/state.json"))
        self.assertFalse(detector.load_state())

    def test_load_corrupt_file(self):
        self.state_file.write_text("not json{{{")
        detector = CorrectionDetector(state_file=self.state_file)
        self.assertFalse(detector.load_state())

    def test_correction_across_invocations(self):
        """Error in one invocation, correction detected in next."""
        d1 = CorrectionDetector(state_file=self.state_file)
        d1.add("Edit", "Error: old_string not found", {"file_path": "/foo.py"})
        d1.save_state()

        d2 = CorrectionDetector(state_file=self.state_file)
        d2.load_state()
        result = d2.add("Edit", "Updated successfully", {"file_path": "/foo.py"})
        self.assertIsNotNone(result)
        self.assertEqual(result.error_tool, "Edit")

    def test_reset_clears_state(self):
        detector = CorrectionDetector(state_file=self.state_file)
        detector.add("Read", "content", {"file_path": "/foo.py"})
        detector.save_state()
        self.assertTrue(self.state_file.exists())

        detector.reset()
        self.assertEqual(len(detector.buffer), 0)
        self.assertFalse(self.state_file.exists())

    def test_stats_persist(self):
        d1 = CorrectionDetector(state_file=self.state_file)
        d1.add("Edit", "Error: not found", {"file_path": "/foo.py"})
        d1.add("Edit", "Updated", {"file_path": "/foo.py"})
        d1.save_state()

        d2 = CorrectionDetector(state_file=self.state_file)
        d2.load_state()
        self.assertEqual(d2._corrections_detected, 1)
        self.assertEqual(d2._total_processed, 2)


class TestCorrectionEvent(unittest.TestCase):
    """Tests for CorrectionEvent serialization."""

    def test_to_dict(self):
        event = CorrectionEvent(
            error_tool="Edit",
            error_resource="/foo.py",
            error_output="Error: old_string not found",
            error_pattern="old_string not found",
            fix_tool="Edit",
            fix_resource="/foo.py",
            fix_output="Updated successfully",
            time_to_fix=5.3,
            timestamp=1000.0,
        )
        d = event.to_dict()
        self.assertEqual(d["error_tool"], "Edit")
        self.assertEqual(d["fix_tool"], "Edit")
        self.assertEqual(d["time_to_fix"], 5.3)
        self.assertEqual(d["error_pattern"], "old_string not found")

    def test_to_dict_truncates_long_output(self):
        event = CorrectionEvent(
            error_tool="Bash",
            error_resource="python3 test.py",
            error_output="x" * 1000,
            error_pattern="Error",
            fix_tool="Bash",
            fix_resource="python3 test.py",
            fix_output="y" * 1000,
            time_to_fix=2.0,
            timestamp=1000.0,
        )
        d = event.to_dict()
        self.assertLessEqual(len(d["error_output"]), 500)
        self.assertLessEqual(len(d["fix_output"]), 500)


class TestToolResult(unittest.TestCase):
    """Tests for ToolResult serialization."""

    def test_roundtrip(self):
        tr = ToolResult(
            tool_name="Read",
            resource="/foo.py",
            output_preview="content here",
            is_error=False,
            error_pattern="",
            timestamp=1000.0,
        )
        d = tr.to_dict()
        tr2 = ToolResult.from_dict(d)
        self.assertEqual(tr2.tool_name, "Read")
        self.assertEqual(tr2.resource, "/foo.py")
        self.assertEqual(tr2.is_error, False)
        self.assertEqual(tr2.timestamp, 1000.0)

    def test_from_dict_missing_error_pattern(self):
        """Backwards compat: old entries without error_pattern."""
        d = {
            "tool_name": "Edit",
            "resource": "/foo.py",
            "output_preview": "error",
            "is_error": True,
            "timestamp": 1000.0,
        }
        tr = ToolResult.from_dict(d)
        self.assertEqual(tr.error_pattern, "")


if __name__ == "__main__":
    unittest.main()
