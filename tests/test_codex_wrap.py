#!/usr/bin/env python3
"""Tests for codex_wrap.py."""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from codex_wrap import (
    GitStatusEntry,
    WrapSnapshot,
    build_wrap_prompt,
    is_runtime_path,
    main,
    parse_git_status,
)


class TestParseGitStatus(unittest.TestCase):
    def test_parses_modified_and_untracked(self):
        entries = parse_git_status(" M foo.py\n?? bar.py\n")
        self.assertEqual(entries[0].code, " M")
        self.assertEqual(entries[0].path, "foo.py")
        self.assertEqual(entries[1].code, "??")
        self.assertEqual(entries[1].path, "bar.py")

    def test_parses_rename_to_new_path(self):
        entries = parse_git_status("R  old.py -> new.py\n")
        self.assertEqual(entries[0].path, "new.py")


class TestRuntimeFiltering(unittest.TestCase):
    def test_known_runtime_file(self):
        self.assertTrue(is_runtime_path(".queue_hook_last_check"))

    def test_known_runtime_prefix(self):
        self.assertTrue(is_runtime_path(".session_pids/desktop.pid"))

    def test_substantive_file(self):
        self.assertFalse(is_runtime_path("agent-guard/tool.py"))


class TestBuildWrapPrompt(unittest.TestCase):
    def test_prompt_contains_snapshot_sections(self):
        snapshot = WrapSnapshot(
            branch="codex/test",
            substantive=[GitStatusEntry(" M", "foo.py")],
            runtime=[GitStatusEntry(" M", ".queue_hook_last_check")],
            recent_commits=["abc1234 Example commit"],
        )
        prompt = build_wrap_prompt("/tmp/repo", snapshot)
        self.assertIn("$cca-desktop-workflow", prompt)
        self.assertIn("foo.py", prompt)
        self.assertIn(".queue_hook_last_check", prompt)
        self.assertIn("abc1234 Example commit", prompt)
        self.assertIn("Wrap checklist:", prompt)
        self.assertIn("SESSION_STATE.md", prompt)
        self.assertIn("SESSION_RESUME.md", prompt)
        self.assertIn("wrap_tracker", prompt)
        self.assertIn("session_outcome_tracker", prompt)

    def test_prompt_handles_empty_lists(self):
        snapshot = WrapSnapshot(
            branch="main",
            substantive=[],
            runtime=[],
            recent_commits=[],
        )
        prompt = build_wrap_prompt("/tmp/repo", snapshot)
        self.assertGreaterEqual(prompt.count("- none"), 3)


class TestCLI(unittest.TestCase):
    @patch("codex_wrap.normalize_cli_root")
    @patch("codex_wrap.collect_snapshot")
    def test_main_prints_prompt(self, mock_collect, mock_normalize):
        mock_normalize.return_value = ("/tmp/repo", None)
        snapshot = WrapSnapshot(
            branch="main",
            substantive=[],
            runtime=[],
            recent_commits=[],
        )
        mock_collect.return_value = snapshot
        with patch("sys.stdout.write") as mock_write:
            exit_code = main(["--root", "/tmp/repo"])
        self.assertEqual(exit_code, 0)
        self.assertTrue(mock_write.called)

    @patch("codex_wrap.normalize_cli_root")
    @patch("codex_wrap.collect_snapshot")
    def test_main_writes_file(self, mock_collect, mock_normalize):
        mock_normalize.return_value = ("/tmp/repo", None)
        snapshot = WrapSnapshot(
            branch="main",
            substantive=[],
            runtime=[],
            recent_commits=[],
        )
        mock_collect.return_value = snapshot
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "prompt.md")
            exit_code = main(["--root", tmpdir, "--write", out_path])
            self.assertEqual(exit_code, 0)
            self.assertTrue(os.path.exists(out_path))
            with open(out_path, encoding="utf-8") as handle:
                content = handle.read()
            self.assertIn("$cca-desktop-workflow", content)


if __name__ == "__main__":
    unittest.main()
