#!/usr/bin/env python3
"""Tests for edit_guard.py — PreToolUse hook that prevents Edit retry storms
on structured table files by suggesting Write (full rewrite) instead.

The #1 finding from batch trace analysis (S58): PROJECT_INDEX.md Edit retries
in 64% of sessions (32/50), averaging 4.9 retries per instance.
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from edit_guard import (
    STRUCTURED_FILES,
    check_edit,
    should_guard,
)


class TestShouldGuard(unittest.TestCase):
    """Test which files are considered structured/problematic."""

    def test_project_index_guarded(self):
        self.assertTrue(should_guard("/some/path/PROJECT_INDEX.md"))

    def test_session_state_guarded(self):
        self.assertTrue(should_guard("/some/path/SESSION_STATE.md"))

    def test_master_tasks_guarded(self):
        self.assertTrue(should_guard("/some/path/MASTER_TASKS.md"))

    def test_regular_python_file_not_guarded(self):
        self.assertFalse(should_guard("/some/path/trace_analyzer.py"))

    def test_regular_md_file_not_guarded(self):
        self.assertFalse(should_guard("/some/path/README.md"))

    def test_claude_md_not_guarded(self):
        """CLAUDE.md is orientation but not a structured table file."""
        self.assertFalse(should_guard("/some/path/CLAUDE.md"))

    def test_none_path_not_guarded(self):
        self.assertFalse(should_guard(None))

    def test_empty_path_not_guarded(self):
        self.assertFalse(should_guard(""))

    def test_case_sensitive(self):
        """Filenames are case-sensitive on macOS (default)."""
        self.assertFalse(should_guard("/some/path/project_index.md"))

    def test_nested_path(self):
        self.assertTrue(should_guard("/Users/matt/Projects/CCA/PROJECT_INDEX.md"))

    def test_structured_files_is_set(self):
        """STRUCTURED_FILES must be a set for O(1) lookup."""
        self.assertIsInstance(STRUCTURED_FILES, (set, frozenset))


class TestCheckEdit(unittest.TestCase):
    """Test the main check_edit function that produces hook output."""

    def test_non_edit_tool_passes(self):
        """Non-Edit tools should always pass through."""
        result = check_edit("Read", {"file_path": "/x/PROJECT_INDEX.md"})
        self.assertIsNone(result)

    def test_edit_on_regular_file_passes(self):
        """Edit on a normal file should pass through."""
        result = check_edit("Edit", {"file_path": "/x/some_module.py"})
        self.assertIsNone(result)

    def test_edit_on_project_index_warns(self):
        """Edit on PROJECT_INDEX.md should return a warning."""
        result = check_edit("Edit", {"file_path": "/x/PROJECT_INDEX.md"})
        self.assertIsNotNone(result)
        self.assertIn("PROJECT_INDEX.md", result)
        self.assertIn("Write", result)

    def test_edit_on_session_state_warns(self):
        result = check_edit("Edit", {"file_path": "/x/SESSION_STATE.md"})
        self.assertIsNotNone(result)
        self.assertIn("SESSION_STATE.md", result)

    def test_edit_on_master_tasks_warns(self):
        result = check_edit("Edit", {"file_path": "/x/MASTER_TASKS.md"})
        self.assertIsNotNone(result)

    def test_edit_with_no_file_path_passes(self):
        """Edit with missing file_path should not crash."""
        result = check_edit("Edit", {})
        self.assertIsNone(result)

    def test_edit_with_none_input_passes(self):
        result = check_edit("Edit", None)
        self.assertIsNone(result)

    def test_warning_message_is_actionable(self):
        """Warning should tell Claude what to do instead."""
        result = check_edit("Edit", {"file_path": "/x/PROJECT_INDEX.md"})
        self.assertIn("Write", result)
        self.assertIn("retry", result.lower())


class TestHookIntegration(unittest.TestCase):
    """Test the hook's stdin/stdout JSON protocol."""

    def _run_hook(self, tool_name, tool_input):
        """Simulate hook invocation via subprocess."""
        import subprocess

        hook_path = os.path.join(os.path.dirname(__file__), "..", "edit_guard.py")
        payload = json.dumps({
            "tool_name": tool_name,
            "tool_input": tool_input,
        })
        result = subprocess.run(
            [sys.executable, hook_path],
            input=payload,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result

    def test_hook_passes_regular_edit(self):
        """Regular Edit should produce empty JSON (pass-through)."""
        result = self._run_hook("Edit", {"file_path": "/x/some.py", "old_string": "a", "new_string": "b"})
        self.assertEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        self.assertEqual(output, {})

    def test_hook_warns_on_project_index(self):
        """Edit on PROJECT_INDEX.md should produce a warning message."""
        result = self._run_hook("Edit", {"file_path": "/x/PROJECT_INDEX.md", "old_string": "a", "new_string": "b"})
        self.assertEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        # Should NOT block — just warn via message
        self.assertNotIn("permissionDecision", output.get("hookSpecificOutput", {}))
        # Should have a user-facing message
        self.assertIn("message", output)
        self.assertIn("PROJECT_INDEX.md", output["message"])

    def test_hook_handles_empty_stdin(self):
        """Empty stdin should not crash the hook."""
        import subprocess
        hook_path = os.path.join(os.path.dirname(__file__), "..", "edit_guard.py")
        result = subprocess.run(
            [sys.executable, hook_path],
            input="",
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        self.assertEqual(output, {})

    def test_hook_handles_malformed_json(self):
        """Malformed JSON should not crash the hook."""
        import subprocess
        hook_path = os.path.join(os.path.dirname(__file__), "..", "edit_guard.py")
        result = subprocess.run(
            [sys.executable, hook_path],
            input="not json",
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        self.assertEqual(output, {})

    def test_hook_passes_non_edit_tool(self):
        result = self._run_hook("Read", {"file_path": "/x/PROJECT_INDEX.md"})
        self.assertEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        self.assertEqual(output, {})


class TestStructuredFilesConfig(unittest.TestCase):
    """Ensure the guarded file list is reasonable."""

    def test_at_least_three_files(self):
        self.assertGreaterEqual(len(STRUCTURED_FILES), 3)

    def test_all_are_md_files(self):
        for f in STRUCTURED_FILES:
            self.assertTrue(f.endswith(".md"), f"Expected .md extension: {f}")

    def test_no_claude_md(self):
        """CLAUDE.md should NOT be guarded — it's text, not tables."""
        self.assertNotIn("CLAUDE.md", STRUCTURED_FILES)

    def test_no_changelog(self):
        """CHANGELOG.md is append-only — Edit is fine there."""
        self.assertNotIn("CHANGELOG.md", STRUCTURED_FILES)


if __name__ == "__main__":
    unittest.main()
