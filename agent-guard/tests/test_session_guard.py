#!/usr/bin/env python3
"""
Tests for session_guard.py — Fresh-session anti-contamination guard.

Detects when a session has accumulated too many self-approved changes
and warns about code quality degradation risk. Also detects "slop"
patterns in code being written.

TDD: Tests written first, then implementation.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).parent
sys.path.insert(0, str(_THIS_DIR.parent))
sys.path.insert(0, str(_THIS_DIR.parent / "hooks"))


class TestSessionCommitTracker(unittest.TestCase):
    """Tests for tracking commits within a session."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_path = os.path.join(self.tmpdir, "session_guard_state.json")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_import(self):
        from session_guard import SessionCommitTracker
        self.assertTrue(callable(SessionCommitTracker))

    def test_initial_count_zero(self):
        from session_guard import SessionCommitTracker
        t = SessionCommitTracker(state_path=self.state_path)
        self.assertEqual(t.commit_count, 0)

    def test_record_commit_increments(self):
        from session_guard import SessionCommitTracker
        t = SessionCommitTracker(state_path=self.state_path)
        t.record_commit("abc123")
        self.assertEqual(t.commit_count, 1)
        t.record_commit("def456")
        self.assertEqual(t.commit_count, 2)

    def test_state_persists(self):
        from session_guard import SessionCommitTracker
        t1 = SessionCommitTracker(state_path=self.state_path)
        t1.record_commit("abc123")
        t1.record_commit("def456")
        # Reload
        t2 = SessionCommitTracker(state_path=self.state_path)
        self.assertEqual(t2.commit_count, 2)

    def test_threshold_detection(self):
        from session_guard import SessionCommitTracker
        t = SessionCommitTracker(state_path=self.state_path, warn_threshold=3)
        t.record_commit("a")
        t.record_commit("b")
        self.assertFalse(t.should_warn())
        t.record_commit("c")
        self.assertTrue(t.should_warn())

    def test_default_threshold_is_reasonable(self):
        from session_guard import SessionCommitTracker
        t = SessionCommitTracker(state_path=self.state_path)
        self.assertGreaterEqual(t.warn_threshold, 5)
        self.assertLessEqual(t.warn_threshold, 20)

    def test_reset_clears_state(self):
        from session_guard import SessionCommitTracker
        t = SessionCommitTracker(state_path=self.state_path)
        t.record_commit("a")
        t.record_commit("b")
        t.reset()
        self.assertEqual(t.commit_count, 0)

    def test_files_touched_tracking(self):
        from session_guard import SessionCommitTracker
        t = SessionCommitTracker(state_path=self.state_path)
        t.record_commit("abc123", files_changed=["src/a.py", "src/b.py"])
        t.record_commit("def456", files_changed=["src/a.py", "src/c.py"])
        self.assertEqual(t.total_files_touched, 3)  # unique files


class TestSlopDetector(unittest.TestCase):
    """Tests for detecting 'slop' patterns in code output."""

    def test_import(self):
        from session_guard import SlopDetector
        self.assertTrue(callable(SlopDetector))

    def test_clean_code_passes(self):
        from session_guard import SlopDetector
        d = SlopDetector()
        code = '''def calculate_total(items):
    return sum(item.price for item in items)
'''
        result = d.scan(code)
        self.assertFalse(result.has_slop)

    def test_excessive_docstrings_detected(self):
        """Code where >50% of lines are docstrings/comments is suspicious."""
        from session_guard import SlopDetector
        d = SlopDetector()
        code = '''"""
This function calculates the total.

It takes a list of items and returns the sum of their prices.
Each item should have a price attribute.
The return value is a float representing the total.

Args:
    items: A list of item objects with price attributes.

Returns:
    float: The sum of all item prices.

Example:
    >>> calculate_total([Item(10), Item(20)])
    30
"""
def calculate_total(items):
    return sum(item.price for item in items)
'''
        result = d.scan(code)
        self.assertTrue(result.has_slop)
        self.assertTrue(any("docstring" in w.lower() or "comment" in w.lower() for w in result.warnings))

    def test_redundant_type_comments_detected(self):
        """Inline type comments on obvious assignments are slop."""
        from session_guard import SlopDetector
        d = SlopDetector()
        code = '''x = 5  # type: int
name = "hello"  # type: str
items = []  # type: list
result = True  # type: bool
count = 0  # type: int
'''
        result = d.scan(code)
        self.assertTrue(result.has_slop)

    def test_over_engineering_try_except_detected(self):
        """Wrapping simple operations in try/except is over-engineering slop."""
        from session_guard import SlopDetector
        d = SlopDetector()
        code = '''try:
    x = 5 + 3
except Exception as e:
    logging.error(f"Failed to add: {e}")
    raise
try:
    name = "hello"
except Exception as e:
    logging.error(f"Failed to assign: {e}")
    raise
try:
    result = items[0]
except Exception as e:
    logging.error(f"Failed to get item: {e}")
    raise
'''
        result = d.scan(code)
        self.assertTrue(result.has_slop)
        self.assertTrue(any("try" in w.lower() or "except" in w.lower() or "over" in w.lower() for w in result.warnings))

    def test_removed_code_comments_detected(self):
        """Comments like '# removed' or '# deleted' where code was are slop."""
        from session_guard import SlopDetector
        d = SlopDetector()
        code = '''def process():
    # old_function() removed
    # deleted: previous implementation
    # removed old logic
    # was: legacy_call()
    new_function()
'''
        result = d.scan(code)
        self.assertTrue(result.has_slop)

    def test_empty_code_returns_clean(self):
        from session_guard import SlopDetector
        d = SlopDetector()
        result = d.scan("")
        self.assertFalse(result.has_slop)

    def test_short_code_not_flagged(self):
        """Very short code snippets shouldn't trigger slop detection."""
        from session_guard import SlopDetector
        d = SlopDetector()
        result = d.scan("x = 5")
        self.assertFalse(result.has_slop)

    def test_scan_result_has_warnings_list(self):
        from session_guard import SlopDetector, SlopResult
        d = SlopDetector()
        result = d.scan("x = 5")
        self.assertIsInstance(result, SlopResult)
        self.assertIsInstance(result.warnings, list)

    def test_scan_result_has_score(self):
        """SlopResult should have a numeric slop_score."""
        from session_guard import SlopDetector
        d = SlopDetector()
        result = d.scan("x = 5")
        self.assertIsInstance(result.slop_score, (int, float))
        self.assertGreaterEqual(result.slop_score, 0)


class TestSessionGuardHook(unittest.TestCase):
    """Tests for the PreToolUse hook integration."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_path = os.path.join(self.tmpdir, "session_guard_state.json")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_import(self):
        from session_guard import check_write_for_slop
        self.assertTrue(callable(check_write_for_slop))

    def test_clean_write_passes(self):
        from session_guard import check_write_for_slop
        result = check_write_for_slop("Write", {"content": "x = 5\ny = 10\n"})
        self.assertTrue(result["allow"])

    def test_sloppy_write_warns(self):
        from session_guard import check_write_for_slop
        sloppy = '''"""
This function does something.

It takes no arguments.
It returns nothing.
It is very simple.
It exists for documentation purposes.
This is a very thorough docstring.
We believe in documentation.
Documentation is important.
Always document your code.
Never forget to document.
"""
def noop():
    pass
'''
        result = check_write_for_slop("Write", {"content": sloppy})
        self.assertFalse(result["allow"])
        self.assertIn("slop", result["reason"].lower())

    def test_non_write_tools_ignored(self):
        from session_guard import check_write_for_slop
        result = check_write_for_slop("Read", {"file_path": "/tmp/test.py"})
        self.assertTrue(result["allow"])

    def test_edit_tool_checked(self):
        from session_guard import check_write_for_slop
        result = check_write_for_slop("Edit", {"new_string": "x = 5\n"})
        self.assertTrue(result["allow"])

    def test_non_code_files_skipped(self):
        """Markdown, JSON, etc. should not be checked for slop."""
        from session_guard import check_write_for_slop
        result = check_write_for_slop("Write", {
            "file_path": "README.md",
            "content": '"""Very long docstring..."""\n' * 20,
        })
        self.assertTrue(result["allow"])

    def test_commit_warning_message(self):
        """Should produce a clear warning message about fresh sessions."""
        from session_guard import SessionCommitTracker
        t = SessionCommitTracker(state_path=self.state_path, warn_threshold=3)
        for i in range(3):
            t.record_commit(f"commit_{i}")
        msg = t.warning_message()
        self.assertIn("fresh session", msg.lower())

    def test_session_id_isolation(self):
        """Different session IDs should have independent commit counts."""
        from session_guard import SessionCommitTracker
        t1 = SessionCommitTracker(state_path=self.state_path, session_id="session_a")
        t1.record_commit("a1")
        t1.record_commit("a2")

        t2 = SessionCommitTracker(state_path=self.state_path, session_id="session_b")
        self.assertEqual(t2.commit_count, 0)


class TestSlopPatterns(unittest.TestCase):
    """Tests for individual slop pattern detection."""

    def test_backwards_compat_shim_detected(self):
        """Renaming unused vars with _ prefix is backwards-compat slop."""
        from session_guard import SlopDetector
        d = SlopDetector()
        code = '''def process():
    pass

_old_function = None  # backwards compatibility
_legacy_handler = None  # kept for backwards compat
_deprecated_method = None  # removed but kept for compat
'''
        result = d.scan(code)
        self.assertTrue(result.has_slop)

    def test_emoji_in_code_detected(self):
        """Emojis in Python code (not strings) are slop."""
        from session_guard import SlopDetector
        d = SlopDetector()
        code = '''# \U0001f680 Launch the application
def start():
    print("Starting...")  # \u2705 Ready to go
    # \U0001f389 Celebration time
    return True
'''
        result = d.scan(code)
        self.assertTrue(result.has_slop)


if __name__ == "__main__":
    unittest.main()
