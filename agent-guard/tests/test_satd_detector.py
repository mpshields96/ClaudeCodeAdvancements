#!/usr/bin/env python3
"""Tests for satd_detector.py — MT-20 Senior Dev Agent: SATD marker detection.

SATD = Self-Admitted Technical Debt.
Detects TODO/FIXME/HACK/WORKAROUND/DEBT/XXX markers in code being written.
Delivered as a PostToolUse hook that surfaces markers as additionalContext.

Tests cover:
- Pattern detection for all SATD marker types
- Line number extraction
- Severity classification (FIXME/HACK > TODO > XXX)
- Hook I/O format
- Edge cases (empty content, non-code files)
- False positive avoidance (Markdown/comments that aren't code debt)
"""

import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from satd_detector import SATDDetector, SATDMarker, SATDLevel


class TestSATDMarker(unittest.TestCase):
    """Test the SATDMarker data structure."""

    def test_marker_fields(self):
        m = SATDMarker(line=10, text="TODO: fix this later", marker_type="TODO", level=SATDLevel.LOW)
        self.assertEqual(m.line, 10)
        self.assertEqual(m.text, "TODO: fix this later")
        self.assertEqual(m.marker_type, "TODO")
        self.assertEqual(m.level, SATDLevel.LOW)

    def test_marker_to_dict(self):
        m = SATDMarker(line=5, text="FIXME: broken", marker_type="FIXME", level=SATDLevel.HIGH)
        d = m.to_dict()
        self.assertEqual(d["line"], 5)
        self.assertEqual(d["text"], "FIXME: broken")
        self.assertEqual(d["marker_type"], "FIXME")
        self.assertEqual(d["level"], "HIGH")


class TestSATDLevel(unittest.TestCase):
    """Test severity level classification."""

    def test_levels_exist(self):
        self.assertIsNotNone(SATDLevel.HIGH)
        self.assertIsNotNone(SATDLevel.MEDIUM)
        self.assertIsNotNone(SATDLevel.LOW)

    def test_high_is_highest(self):
        self.assertGreater(SATDLevel.HIGH.value, SATDLevel.MEDIUM.value)
        self.assertGreater(SATDLevel.MEDIUM.value, SATDLevel.LOW.value)


class TestSATDDetectorPatterns(unittest.TestCase):
    """Test that all SATD patterns are detected."""

    def setUp(self):
        self.detector = SATDDetector()

    def test_detects_todo(self):
        markers = self.detector.scan("x = 1  # TODO: fix this")
        self.assertEqual(len(markers), 1)
        self.assertEqual(markers[0].marker_type, "TODO")

    def test_detects_fixme(self):
        markers = self.detector.scan("# FIXME: this breaks on edge cases")
        self.assertEqual(len(markers), 1)
        self.assertEqual(markers[0].marker_type, "FIXME")

    def test_detects_hack(self):
        markers = self.detector.scan("# HACK: workaround for upstream bug")
        self.assertEqual(len(markers), 1)
        self.assertEqual(markers[0].marker_type, "HACK")

    def test_detects_workaround(self):
        markers = self.detector.scan("# WORKAROUND: temp fix until v2")
        self.assertEqual(len(markers), 1)
        self.assertEqual(markers[0].marker_type, "WORKAROUND")

    def test_detects_debt(self):
        markers = self.detector.scan("# DEBT: needs refactor")
        self.assertEqual(len(markers), 1)
        self.assertEqual(markers[0].marker_type, "DEBT")

    def test_detects_xxx(self):
        markers = self.detector.scan("# XXX: danger zone")
        self.assertEqual(len(markers), 1)
        self.assertEqual(markers[0].marker_type, "XXX")

    def test_detects_note_as_low(self):
        markers = self.detector.scan("# NOTE: consider optimizing later")
        self.assertEqual(len(markers), 1)
        self.assertEqual(markers[0].level, SATDLevel.LOW)

    def test_case_insensitive(self):
        markers = self.detector.scan("# todo: lowercase works too")
        self.assertEqual(len(markers), 1)
        self.assertEqual(markers[0].marker_type, "TODO")

    def test_no_markers_returns_empty(self):
        markers = self.detector.scan("x = 1\ny = 2\nprint(x + y)")
        self.assertEqual(len(markers), 0)

    def test_empty_content_returns_empty(self):
        markers = self.detector.scan("")
        self.assertEqual(len(markers), 0)

    def test_multiple_markers(self):
        code = """def foo():
    # TODO: optimize this
    x = slow_function()
    # FIXME: this leaks memory
    return x
"""
        markers = self.detector.scan(code)
        self.assertEqual(len(markers), 2)
        types = {m.marker_type for m in markers}
        self.assertIn("TODO", types)
        self.assertIn("FIXME", types)

    def test_line_numbers_are_correct(self):
        code = "line 1\n# TODO: fix on line 2\nline 3"
        markers = self.detector.scan(code)
        self.assertEqual(markers[0].line, 2)

    def test_first_line_marker(self):
        code = "# FIXME: at the top\nrest = 'of code'"
        markers = self.detector.scan(code)
        self.assertEqual(markers[0].line, 1)


class TestSATDSeverity(unittest.TestCase):
    """Test severity level assignment."""

    def setUp(self):
        self.detector = SATDDetector()

    def test_fixme_is_high(self):
        markers = self.detector.scan("# FIXME: critical bug")
        self.assertEqual(markers[0].level, SATDLevel.HIGH)

    def test_hack_is_high(self):
        markers = self.detector.scan("# HACK: bad code")
        self.assertEqual(markers[0].level, SATDLevel.HIGH)

    def test_workaround_is_high(self):
        markers = self.detector.scan("# WORKAROUND: temp fix")
        self.assertEqual(markers[0].level, SATDLevel.HIGH)

    def test_debt_is_high(self):
        markers = self.detector.scan("# DEBT: needs refactor")
        self.assertEqual(markers[0].level, SATDLevel.HIGH)

    def test_todo_is_medium(self):
        markers = self.detector.scan("# TODO: add tests")
        self.assertEqual(markers[0].level, SATDLevel.MEDIUM)

    def test_xxx_is_medium(self):
        markers = self.detector.scan("# XXX: review this")
        self.assertEqual(markers[0].level, SATDLevel.MEDIUM)

    def test_note_is_low(self):
        markers = self.detector.scan("# NOTE: consider refactoring")
        self.assertEqual(markers[0].level, SATDLevel.LOW)


class TestSATDTextExtraction(unittest.TestCase):
    """Test that marker text is extracted cleanly."""

    def setUp(self):
        self.detector = SATDDetector()

    def test_text_includes_marker_and_message(self):
        markers = self.detector.scan("# TODO: refactor this function")
        self.assertIn("TODO", markers[0].text)
        self.assertIn("refactor this function", markers[0].text)

    def test_text_is_stripped(self):
        markers = self.detector.scan("   # TODO: lots of spaces   ")
        self.assertEqual(markers[0].text, markers[0].text.strip())

    def test_inline_marker_extracted(self):
        markers = self.detector.scan("x = expensive_op()  # FIXME: use cache")
        self.assertIn("FIXME", markers[0].text)


class TestSATDFileExtensions(unittest.TestCase):
    """Test that SATD detection works with file paths."""

    def setUp(self):
        self.detector = SATDDetector()

    def test_python_file_scanned(self):
        markers = self.detector.scan_file_content(
            "# TODO: fix",
            file_path="module/thing.py"
        )
        self.assertEqual(len(markers), 1)

    def test_non_code_file_skipped(self):
        # Markdown and documentation files should be skipped
        markers = self.detector.scan_file_content(
            "# TODO: write more docs",
            file_path="README.md"
        )
        self.assertEqual(len(markers), 0)

    def test_json_file_skipped(self):
        markers = self.detector.scan_file_content(
            '{"key": "TODO: this is data not code"}',
            file_path="data.json"
        )
        self.assertEqual(len(markers), 0)

    def test_yaml_file_skipped(self):
        markers = self.detector.scan_file_content(
            "# TODO: this is yaml config",
            file_path="config.yaml"
        )
        self.assertEqual(len(markers), 0)

    def test_no_extension_scanned(self):
        markers = self.detector.scan_file_content(
            "# TODO: fix this",
            file_path="Makefile"
        )
        self.assertEqual(len(markers), 1)


class TestSATDHookOutput(unittest.TestCase):
    """Test the PostToolUse hook JSON output."""

    def setUp(self):
        self.detector = SATDDetector()

    def test_no_markers_returns_empty_dict(self):
        output = self.detector.hook_output("clean code here", file_path="module.py")
        self.assertEqual(output, {})

    def test_markers_return_additional_context(self):
        output = self.detector.hook_output(
            "# TODO: add error handling\nx = 1",
            file_path="module.py"
        )
        self.assertIn("additionalContext", output)
        context = output["additionalContext"]
        self.assertIn("SATD", context)
        self.assertIn("TODO", context)

    def test_high_severity_markers_surfaced_prominently(self):
        output = self.detector.hook_output(
            "# FIXME: memory leak here",
            file_path="module.py"
        )
        context = output.get("additionalContext", "")
        self.assertIn("FIXME", context)

    def test_output_is_json_serializable(self):
        output = self.detector.hook_output(
            "# TODO: fix\n# HACK: quick fix",
            file_path="module.py"
        )
        # Should not raise
        json.dumps(output)

    def test_max_markers_reported(self):
        # When many markers, only report the highest severity ones
        lines = "\n".join([f"# TODO: item {i}" for i in range(20)])
        output = self.detector.hook_output(lines, file_path="module.py")
        context = output.get("additionalContext", "")
        # Should not be an overwhelming wall of text
        self.assertLess(len(context), 2000)


class TestSATDHookEntry(unittest.TestCase):
    """Test the main() hook entry point that reads stdin JSON."""

    def _run_hook(self, payload: dict) -> dict:
        script = os.path.join(os.path.dirname(os.path.dirname(__file__)), "satd_detector.py")
        result = subprocess.run(
            [sys.executable, script],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=5,
            cwd=os.path.dirname(os.path.dirname(__file__)),
        )
        if result.stdout.strip():
            return json.loads(result.stdout)
        return {}

    def test_write_with_satd_produces_context(self):
        payload = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "test_module.py",
                "content": "# TODO: fix this\nx = 1",
            },
        }
        output = self._run_hook(payload)
        self.assertIn("additionalContext", output)

    def test_write_clean_returns_empty(self):
        payload = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "clean.py",
                "content": "x = 1\ny = 2",
            },
        }
        output = self._run_hook(payload)
        self.assertEqual(output, {})

    def test_edit_with_new_string_scanned(self):
        payload = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "module.py",
                "old_string": "x = 1",
                "new_string": "x = 1  # FIXME: broken",
            },
        }
        output = self._run_hook(payload)
        self.assertIn("additionalContext", output)

    def test_read_tool_ignored(self):
        payload = {
            "tool_name": "Read",
            "tool_input": {"file_path": "module.py"},
        }
        output = self._run_hook(payload)
        self.assertEqual(output, {})

    def test_bash_tool_ignored(self):
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "echo '# TODO: fix'"},
        }
        output = self._run_hook(payload)
        self.assertEqual(output, {})

    def test_empty_stdin_no_crash(self):
        output = self._run_hook({})
        self.assertEqual(output, {})

    def test_non_code_file_ignored(self):
        payload = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "README.md",
                "content": "# TODO: write more docs",
            },
        }
        output = self._run_hook(payload)
        self.assertEqual(output, {})


if __name__ == "__main__":
    unittest.main()
