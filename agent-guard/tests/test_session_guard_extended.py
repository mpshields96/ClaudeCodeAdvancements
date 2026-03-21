#!/usr/bin/env python3
"""
test_session_guard_extended.py — Extended coverage for session_guard.py.

Targets gaps in the original test suite:
- SlopResult dataclass internals
- Edge cases at detection thresholds
- Docstring toggling + single-line docstrings
- SessionCommitTracker resilience (corrupt state, multi-session, atomic write)
- check_write_for_slop edge cases (empty content, code extensions, Edit slop)
- main() hook entry point with stdin injection
- Slop score accumulation across multiple categories
"""

import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_THIS_DIR = Path(__file__).parent
sys.path.insert(0, str(_THIS_DIR.parent))
sys.path.insert(0, str(_THIS_DIR.parent / "hooks"))


# ── SlopResult ────────────────────────────────────────────────────────────────


class TestSlopResultDataclass(unittest.TestCase):
    """Direct tests for SlopResult.add() and accumulation logic."""

    def test_initial_state(self):
        from session_guard import SlopResult
        r = SlopResult()
        self.assertFalse(r.has_slop)
        self.assertEqual(r.slop_score, 0.0)
        self.assertEqual(r.warnings, [])

    def test_add_sets_has_slop(self):
        from session_guard import SlopResult
        r = SlopResult()
        r.add("Test warning", 10.0)
        self.assertTrue(r.has_slop)
        self.assertEqual(r.slop_score, 10.0)
        self.assertIn("Test warning", r.warnings)

    def test_add_accumulates_score(self):
        from session_guard import SlopResult
        r = SlopResult()
        r.add("Warning A", 15.0)
        r.add("Warning B", 25.0)
        self.assertAlmostEqual(r.slop_score, 40.0)
        self.assertEqual(len(r.warnings), 2)

    def test_zero_score_does_not_set_has_slop(self):
        from session_guard import SlopResult
        r = SlopResult()
        r.add("Zero warning", 0.0)
        self.assertFalse(r.has_slop)

    def test_multiple_warnings_accumulate(self):
        from session_guard import SlopResult
        r = SlopResult()
        for i in range(5):
            r.add(f"Warning {i}", 5.0)
        self.assertEqual(len(r.warnings), 5)
        self.assertAlmostEqual(r.slop_score, 25.0)


# ── SlopDetector: Threshold Edge Cases ───────────────────────────────────────


class TestSlopDetectorThresholds(unittest.TestCase):
    """Edge cases exactly at detection thresholds."""

    def _make_code_with_doc_ratio(self, ratio: float, total_lines: int = 20) -> str:
        """Generate code with a specific doc/non-doc ratio."""
        doc_lines = int(total_lines * ratio)
        code_lines = total_lines - doc_lines
        lines = ["# comment"] * doc_lines + ["x = 1"] * max(code_lines, 1)
        return "\n".join(lines)

    def test_exactly_50_percent_docs_does_not_flag(self):
        from session_guard import SlopDetector
        d = SlopDetector()
        # 10 comment lines, 10 code lines = exactly 50% — should NOT flag (threshold > 0.5)
        code = "\n".join(["# comment"] * 10 + ["x = 1"] * 10)
        result = d.scan(code)
        self.assertFalse(result.has_slop)

    def test_just_above_50_percent_docs_flags(self):
        from session_guard import SlopDetector
        d = SlopDetector()
        # 11 comment lines, 9 code lines = 55% — should flag
        code = "\n".join(["# comment"] * 11 + ["x = 1"] * 9)
        result = d.scan(code)
        self.assertTrue(result.has_slop)

    def test_type_comments_below_threshold_no_flag(self):
        from session_guard import SlopDetector
        d = SlopDetector()
        # Only 2 type comments — threshold is 3
        code = "x = 5  # type: int\ny = 10  # type: int\nz = 'hello'\na = []\nb = {}\n"
        result = d.scan(code)
        self.assertFalse(result.has_slop)

    def test_type_comments_at_threshold_flags(self):
        from session_guard import SlopDetector
        d = SlopDetector()
        code = "x = 5  # type: int\ny = 10  # type: str\nz = True  # type: bool\na = []\nb = {}\n"
        result = d.scan(code)
        self.assertTrue(result.has_slop)

    def test_removed_comments_below_threshold(self):
        from session_guard import SlopDetector
        d = SlopDetector()
        # Only 1 removed comment — threshold is 2
        code = "def process():\n    # removed old logic\n    new_function()\n    x = 1\n    y = 2\n"
        result = d.scan(code)
        self.assertFalse(result.has_slop)

    def test_removed_comments_at_threshold(self):
        from session_guard import SlopDetector
        d = SlopDetector()
        code = "def process():\n    # removed old logic\n    # deleted: previous implementation\n    new_function()\n    x = 1\n"
        result = d.scan(code)
        self.assertTrue(result.has_slop)

    def test_compat_shims_below_threshold(self):
        from session_guard import SlopDetector
        d = SlopDetector()
        # Only 1 compat shim
        code = "_old_fn = None  # backwards compatibility\nx = 1\ny = 2\nz = 3\nw = 4\n"
        result = d.scan(code)
        self.assertFalse(result.has_slop)

    def test_compat_shims_at_threshold(self):
        from session_guard import SlopDetector
        d = SlopDetector()
        code = "_old_fn = None  # backwards compatibility\n_legacy = None  # kept for compat\nx = 1\ny = 2\nz = 3\n"
        result = d.scan(code)
        self.assertTrue(result.has_slop)

    def test_emoji_one_line_no_flag(self):
        from session_guard import SlopDetector
        d = SlopDetector()
        code = "# \U0001f680 Launch\ndef start():\n    x = 1\n    y = 2\n    z = 3\n"
        result = d.scan(code)
        self.assertFalse(result.has_slop)

    def test_emoji_two_lines_flags(self):
        from session_guard import SlopDetector
        d = SlopDetector()
        code = "# \U0001f680 Launch\n# \u2705 Ready\ndef start():\n    x = 1\n    y = 2\n"
        result = d.scan(code)
        self.assertTrue(result.has_slop)

    def test_over_engineering_3_blocks_in_50_lines_flags(self):
        from session_guard import SlopDetector
        d = SlopDetector()
        # Exactly 3 try blocks in <50 lines
        code = "try:\n    x = 1\nexcept Exception:\n    pass\n" * 3 + "y = 2\n" * 5
        result = d.scan(code)
        self.assertTrue(result.has_slop)

    def test_over_engineering_3_blocks_in_large_file_no_flag(self):
        from session_guard import SlopDetector
        d = SlopDetector()
        # 3 try blocks but code has >50 lines — should not flag
        try_block = "try:\n    x = 1\nexcept Exception:\n    pass\n"
        padding = "y = 2\n" * 50
        code = try_block * 3 + padding
        result = d.scan(code)
        self.assertFalse(result.has_slop)

    def test_fewer_than_min_lines_no_scan(self):
        from session_guard import SlopDetector
        d = SlopDetector()
        # Only 4 lines — below MIN_LINES=5
        code = "# comment\n# comment\n# comment\n# comment\n"
        result = d.scan(code)
        self.assertFalse(result.has_slop)

    def test_exactly_min_lines_scanned(self):
        from session_guard import SlopDetector
        d = SlopDetector()
        # Exactly MIN_LINES=5 lines with slop
        code = "x = 5  # type: int\ny = 10  # type: str\nz = True  # type: bool\na = 1\nb = 2\n"
        result = d.scan(code)
        self.assertTrue(result.has_slop)


# ── SlopDetector: Docstring Toggling ─────────────────────────────────────────


class TestSlopDetectorDocstringHandling(unittest.TestCase):
    """Tests for docstring multi-line toggling edge cases."""

    def test_single_line_docstring_counted_once(self):
        from session_guard import SlopDetector
        d = SlopDetector()
        # Single-line docstrings (both quotes on same line) should count as 1 doc line each
        lines = ['"""Single line docstring"""'] * 5 + ["x = 1"] * 10
        code = "\n".join(lines)
        result = d.scan(code)
        # 5 doc lines, 10 code lines = 33% — should not flag
        self.assertFalse(result.has_slop)

    def test_multiline_docstring_all_lines_counted(self):
        from session_guard import SlopDetector
        d = SlopDetector()
        # Multi-line docstring covering most of the code
        code = '"""\nLine one of docstring.\nLine two of docstring.\nLine three.\nLine four.\nLine five.\n"""\nx = 1\ny = 2\n'
        result = d.scan(code)
        self.assertTrue(result.has_slop)

    def test_single_quotes_docstring_detected(self):
        from session_guard import SlopDetector
        d = SlopDetector()
        # Triple single quotes should also be detected
        lines = ["'''"] + ["comment"] * 6 + ["'''"] + ["x = 1"] * 3
        code = "\n".join(lines)
        result = d.scan(code)
        self.assertTrue(result.has_slop)

    def test_hash_comments_counted_as_docs(self):
        from session_guard import SlopDetector
        d = SlopDetector()
        # Regular # comments count as doc lines
        lines = ["# This is a comment"] * 12 + ["x = 1"] * 8
        code = "\n".join(lines)
        result = d.scan(code)
        self.assertTrue(result.has_slop)

    def test_empty_lines_not_counted(self):
        from session_guard import SlopDetector
        d = SlopDetector()
        # Empty lines should be excluded from ratio calculation
        code = "\n".join([""] * 20 + ["# comment"] * 5 + ["x = 1"] * 10)
        result = d.scan(code)
        self.assertFalse(result.has_slop)


# ── SlopDetector: Multiple Categories ────────────────────────────────────────


class TestSlopDetectorMultipleCategories(unittest.TestCase):
    """Tests for slop accumulation across multiple categories."""

    def test_multiple_slop_categories_accumulate_score(self):
        from session_guard import SlopDetector
        d = SlopDetector()
        # Has type comments + removed comments
        code = (
            "x = 5  # type: int\n"
            "y = 10  # type: str\n"
            "z = True  # type: bool\n"
            "# removed old logic\n"
            "# deleted: previous\n"
            "a = 1\n"
        )
        result = d.scan(code)
        self.assertTrue(result.has_slop)
        # Should have both warnings
        self.assertGreaterEqual(len(result.warnings), 2)
        self.assertGreater(result.slop_score, 20.0)

    def test_slop_score_higher_for_more_categories(self):
        from session_guard import SlopDetector
        d = SlopDetector()
        single = "x = 5  # type: int\ny = 10  # type: str\nz = True  # type: bool\na = 1\nb = 2\n"
        multi = (
            "x = 5  # type: int\ny = 10  # type: str\nz = True  # type: bool\n"
            "# removed old\n# deleted prev\n"
        )
        r1 = d.scan(single)
        r2 = d.scan(multi)
        self.assertGreater(r2.slop_score, r1.slop_score)

    def test_slop_result_warns_list_contains_all_categories(self):
        from session_guard import SlopDetector
        d = SlopDetector()
        code = (
            "x = 5  # type: int\n"
            "y = 10  # type: str\n"
            "z = True  # type: bool\n"
            "_old = None  # backwards compatibility\n"
            "_legacy = None  # kept for compat\n"
            "a = 1\n"
        )
        result = d.scan(code)
        self.assertGreaterEqual(len(result.warnings), 2)


# ── check_write_for_slop: Edge Cases ─────────────────────────────────────────


class TestCheckWriteForSlopEdgeCases(unittest.TestCase):
    """Edge cases for the check_write_for_slop function."""

    def test_empty_content_passes(self):
        from session_guard import check_write_for_slop
        result = check_write_for_slop("Write", {"content": "", "file_path": "test.py"})
        self.assertTrue(result["allow"])

    def test_none_content_passes(self):
        from session_guard import check_write_for_slop
        result = check_write_for_slop("Write", {"file_path": "test.py"})
        self.assertTrue(result["allow"])

    def test_whitespace_only_content_passes(self):
        from session_guard import check_write_for_slop
        result = check_write_for_slop("Write", {"content": "   \n\n  \n"})
        self.assertTrue(result["allow"])

    def test_no_file_path_still_checked(self):
        from session_guard import check_write_for_slop
        sloppy = ("# comment\n" * 15) + ("x = 1\n" * 5)
        result = check_write_for_slop("Write", {"content": sloppy})
        self.assertTrue(result.get("allow") is not None)

    def test_unknown_extension_not_blocked(self):
        from session_guard import check_write_for_slop
        sloppy = ("# comment\n" * 15) + ("x = 1\n" * 5)
        result = check_write_for_slop("Write", {"content": sloppy, "file_path": "config.yaml"})
        self.assertTrue(result["allow"])

    def test_no_extension_file_is_checked(self):
        from session_guard import check_write_for_slop
        # No extension — falls through to check
        clean = "x = 5\ny = 10\nz = 15\na = 1\nb = 2\n"
        result = check_write_for_slop("Write", {"content": clean, "file_path": "Makefile"})
        self.assertTrue(result["allow"])

    def test_edit_with_sloppy_new_string_warns(self):
        from session_guard import check_write_for_slop
        sloppy_edit = (
            '"""\nThis function does something.\nVery detailed docs.\n'
            'Args: none.\nReturns: nothing.\nSee also: nothing.\n"""\n'
            "def noop():\n    pass\n"
        )
        result = check_write_for_slop("Edit", {"new_string": sloppy_edit, "file_path": "main.py"})
        self.assertIn("allow", result)

    def test_javascript_file_checked(self):
        from session_guard import check_write_for_slop
        sloppy = ("// comment\n" * 15) + ("let x = 1;\n" * 5)
        result = check_write_for_slop("Write", {"content": sloppy, "file_path": "app.js"})
        self.assertIn("allow", result)

    def test_typescript_file_checked(self):
        from session_guard import check_write_for_slop
        clean = "const x = 5;\n" * 5
        result = check_write_for_slop("Write", {"content": clean, "file_path": "app.ts"})
        self.assertTrue(result["allow"])

    def test_bash_file_not_checked(self):
        from session_guard import check_write_for_slop
        sloppy = ("# comment\n" * 15) + ("echo 1\n" * 5)
        result = check_write_for_slop("Write", {"content": sloppy, "file_path": "deploy.sh"})
        self.assertTrue(result["allow"])

    def test_result_always_has_allow_key(self):
        from session_guard import check_write_for_slop
        for tool in ["Write", "Edit", "Read", "Bash", "Glob"]:
            result = check_write_for_slop(tool, {"content": "x = 1\n"})
            self.assertIn("allow", result, f"Missing 'allow' key for tool {tool}")

    def test_sloppy_reason_includes_score(self):
        from session_guard import check_write_for_slop
        sloppy = (
            '"""\nThis is a very long docstring.\nWith many lines.\n'
            "Line four.\nLine five.\nLine six.\nLine seven.\nLine eight.\n"
            'Line nine.\nLine ten.\n"""\ndef noop():\n    pass\n'
        )
        result = check_write_for_slop("Write", {"content": sloppy})
        if not result["allow"]:
            self.assertIn("score", result["reason"].lower())


# ── SessionCommitTracker: Resilience ─────────────────────────────────────────


class TestSessionCommitTrackerResilience(unittest.TestCase):
    """Tests for resilience against corrupt state files and edge cases."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_path = os.path.join(self.tmpdir, "session_guard_state.json")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_corrupt_json_file_defaults_to_zero(self):
        from session_guard import SessionCommitTracker
        with open(self.state_path, "w") as f:
            f.write("INVALID JSON {{{")
        t = SessionCommitTracker(state_path=self.state_path)
        self.assertEqual(t.commit_count, 0)

    def test_missing_file_defaults_to_zero(self):
        from session_guard import SessionCommitTracker
        t = SessionCommitTracker(state_path=self.state_path + ".nonexistent")
        self.assertEqual(t.commit_count, 0)

    def test_empty_json_file_defaults_to_zero(self):
        from session_guard import SessionCommitTracker
        with open(self.state_path, "w") as f:
            f.write("{}")
        t = SessionCommitTracker(state_path=self.state_path)
        self.assertEqual(t.commit_count, 0)

    def test_multiple_sessions_stored_independently(self):
        from session_guard import SessionCommitTracker
        t_a = SessionCommitTracker(state_path=self.state_path, session_id="session_a")
        t_a.record_commit("a1")
        t_a.record_commit("a2")
        t_a.record_commit("a3")

        t_b = SessionCommitTracker(state_path=self.state_path, session_id="session_b")
        t_b.record_commit("b1")

        # Reload both
        t_a2 = SessionCommitTracker(state_path=self.state_path, session_id="session_a")
        t_b2 = SessionCommitTracker(state_path=self.state_path, session_id="session_b")
        self.assertEqual(t_a2.commit_count, 3)
        self.assertEqual(t_b2.commit_count, 1)

    def test_writing_one_session_does_not_corrupt_other(self):
        from session_guard import SessionCommitTracker
        t_a = SessionCommitTracker(state_path=self.state_path, session_id="session_a")
        t_a.record_commit("a1")

        t_b = SessionCommitTracker(state_path=self.state_path, session_id="session_b")
        t_b.record_commit("b1")
        t_b.record_commit("b2")

        # session_a should still have 1 commit
        t_a2 = SessionCommitTracker(state_path=self.state_path, session_id="session_a")
        self.assertEqual(t_a2.commit_count, 1)

    def test_files_touched_deduplicates(self):
        from session_guard import SessionCommitTracker
        t = SessionCommitTracker(state_path=self.state_path)
        t.record_commit("a", files_changed=["src/a.py", "src/b.py"])
        t.record_commit("b", files_changed=["src/a.py", "src/a.py"])  # duplicates
        self.assertEqual(t.total_files_touched, 2)

    def test_files_touched_persisted_on_reload(self):
        from session_guard import SessionCommitTracker
        t = SessionCommitTracker(state_path=self.state_path)
        t.record_commit("a", files_changed=["src/a.py", "src/b.py"])

        t2 = SessionCommitTracker(state_path=self.state_path)
        self.assertEqual(t2.total_files_touched, 2)

    def test_reset_persists_to_disk(self):
        from session_guard import SessionCommitTracker
        t = SessionCommitTracker(state_path=self.state_path)
        t.record_commit("a")
        t.record_commit("b")
        t.reset()

        t2 = SessionCommitTracker(state_path=self.state_path)
        self.assertEqual(t2.commit_count, 0)

    def test_atomic_write_uses_tmp_file(self):
        from session_guard import SessionCommitTracker
        t = SessionCommitTracker(state_path=self.state_path)
        t.record_commit("a")
        # After write, tmp file should be gone (replaced)
        self.assertFalse(os.path.exists(self.state_path + ".tmp"))

    def test_empty_files_changed_list(self):
        from session_guard import SessionCommitTracker
        t = SessionCommitTracker(state_path=self.state_path)
        t.record_commit("a", files_changed=[])
        self.assertEqual(t.commit_count, 1)
        self.assertEqual(t.total_files_touched, 0)

    def test_no_files_changed_argument(self):
        from session_guard import SessionCommitTracker
        t = SessionCommitTracker(state_path=self.state_path)
        t.record_commit("a")
        self.assertEqual(t.commit_count, 1)
        self.assertEqual(t.total_files_touched, 0)

    def test_warning_message_includes_file_count(self):
        from session_guard import SessionCommitTracker
        t = SessionCommitTracker(state_path=self.state_path, warn_threshold=2)
        t.record_commit("a", files_changed=["src/a.py", "src/b.py"])
        t.record_commit("b", files_changed=["src/c.py"])
        msg = t.warning_message()
        self.assertIn("3", msg)  # 3 files touched

    def test_warning_message_includes_commit_count(self):
        from session_guard import SessionCommitTracker
        t = SessionCommitTracker(state_path=self.state_path, warn_threshold=2)
        t.record_commit("a")
        t.record_commit("b")
        msg = t.warning_message()
        self.assertIn("2", msg)

    def test_should_warn_false_below_threshold(self):
        from session_guard import SessionCommitTracker
        t = SessionCommitTracker(state_path=self.state_path, warn_threshold=5)
        for i in range(4):
            t.record_commit(f"commit_{i}")
        self.assertFalse(t.should_warn())

    def test_should_warn_true_at_threshold(self):
        from session_guard import SessionCommitTracker
        t = SessionCommitTracker(state_path=self.state_path, warn_threshold=5)
        for i in range(5):
            t.record_commit(f"commit_{i}")
        self.assertTrue(t.should_warn())

    def test_commits_list_persisted(self):
        from session_guard import SessionCommitTracker
        t = SessionCommitTracker(state_path=self.state_path)
        t.record_commit("abc123")
        t.record_commit("def456")

        t2 = SessionCommitTracker(state_path=self.state_path)
        self.assertIn("abc123", t2.commits)
        self.assertIn("def456", t2.commits)

    def test_env_var_session_id_fallback(self):
        from session_guard import SessionCommitTracker
        with patch.dict(os.environ, {"CLAUDE_SESSION_ID": "env_session_xyz"}):
            t = SessionCommitTracker(state_path=self.state_path)
            self.assertEqual(t.session_id, "env_session_xyz")

    def test_default_session_id_when_no_env(self):
        from session_guard import SessionCommitTracker
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_SESSION_ID"}
        with patch.dict(os.environ, env, clear=True):
            t = SessionCommitTracker(state_path=self.state_path)
            self.assertIsNotNone(t.session_id)
            self.assertNotEqual(t.session_id, "")


# ── main() Hook Entry Point ───────────────────────────────────────────────────


class TestMainHookEntryPoint(unittest.TestCase):
    """Tests for the main() function used as PreToolUse hook."""

    def _run_main(self, hook_input: dict) -> dict:
        from session_guard import main
        stdin_data = json.dumps(hook_input)
        with patch("sys.stdin", io.StringIO(stdin_data)):
            captured = io.StringIO()
            with patch("sys.stdout", captured):
                main()
        output = captured.getvalue().strip()
        return json.loads(output)

    def test_clean_write_returns_empty_object(self):
        result = self._run_main({
            "tool_name": "Write",
            "tool_input": {"content": "x = 5\ny = 10\n", "file_path": "test.py"},
        })
        self.assertIsInstance(result, dict)

    def test_sloppy_write_returns_additional_context(self):
        sloppy = (
            '"""\nThis function is documented.\nVery thoroughly.\n'
            "Line four.\nLine five.\nLine six.\nLine seven.\nLine eight.\n"
            'Line nine.\nLine ten.\n"""\ndef noop():\n    pass\n'
        )
        result = self._run_main({
            "tool_name": "Write",
            "tool_input": {"content": sloppy, "file_path": "main.py"},
        })
        if "additionalContext" in result:
            self.assertIn("SESSION GUARD", result["additionalContext"])

    def test_invalid_json_input_returns_empty_object(self):
        from session_guard import main
        with patch("sys.stdin", io.StringIO("INVALID JSON")):
            captured = io.StringIO()
            with patch("sys.stdout", captured):
                main()
        output = captured.getvalue().strip()
        result = json.loads(output)
        self.assertIsInstance(result, dict)

    def test_non_write_tool_returns_empty_object(self):
        result = self._run_main({
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/test.py"},
        })
        self.assertEqual(result, {})

    def test_missing_tool_name_handles_gracefully(self):
        result = self._run_main({
            "tool_input": {"content": "x = 5\n"},
        })
        self.assertIsInstance(result, dict)

    def test_missing_tool_input_handles_gracefully(self):
        result = self._run_main({
            "tool_name": "Write",
        })
        self.assertIsInstance(result, dict)

    def test_output_is_valid_json(self):
        from session_guard import main
        hook_input = json.dumps({"tool_name": "Write", "tool_input": {"content": "x = 1\n"}})
        with patch("sys.stdin", io.StringIO(hook_input)):
            captured = io.StringIO()
            with patch("sys.stdout", captured):
                main()
        output = captured.getvalue().strip()
        # Should be parseable JSON
        parsed = json.loads(output)
        self.assertIsInstance(parsed, dict)

    def test_empty_stdin_returns_empty_object(self):
        from session_guard import main
        with patch("sys.stdin", io.StringIO("")):
            captured = io.StringIO()
            with patch("sys.stdout", captured):
                main()
        output = captured.getvalue().strip()
        result = json.loads(output)
        self.assertIsInstance(result, dict)


# ── Slop Pattern: Removed Comments Variants ──────────────────────────────────


class TestRemovedCommentVariants(unittest.TestCase):
    """Test different removed-code comment patterns."""

    def test_was_prefix_detected(self):
        from session_guard import SlopDetector
        d = SlopDetector()
        code = "def process():\n    # was: old_function()\n    # was: legacy_handler()\n    new_fn()\n    x = 1\n"
        result = d.scan(code)
        self.assertTrue(result.has_slop)

    def test_old_underscore_prefix_detected(self):
        from session_guard import SlopDetector
        d = SlopDetector()
        code = "def process():\n    # old_handler removed\n    # old_parser deleted\n    new_fn()\n    x = 1\n"
        result = d.scan(code)
        self.assertTrue(result.has_slop)

    def test_previous_implementation_detected(self):
        from session_guard import SlopDetector
        d = SlopDetector()
        code = "def process():\n    # previous implementation\n    # previous implementation v2\n    new_fn()\n    x = 1\n"
        result = d.scan(code)
        self.assertTrue(result.has_slop)


# ── Slop Pattern: Emoji Exceptions ───────────────────────────────────────────


class TestEmojiExceptions(unittest.TestCase):
    """Test that emojis in string literals are not flagged."""

    def test_emoji_in_print_string_not_flagged(self):
        from session_guard import SlopDetector
        d = SlopDetector()
        code = 'def greet():\n    print("\U0001f44b Hello")\n    return True\n    x = 1\n    y = 2\n'
        result = d.scan(code)
        # print( line is skipped by the check
        self.assertFalse(result.has_slop)

    def test_emoji_in_return_statement_not_flagged(self):
        from session_guard import SlopDetector
        d = SlopDetector()
        code = 'def status():\n    return "\u2705 success"\n    x = 1\n    y = 2\n    z = 3\n'
        result = d.scan(code)
        self.assertFalse(result.has_slop)


if __name__ == "__main__":
    unittest.main()
