#!/usr/bin/env python3
"""Tests for codex_autoloop.py."""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from codex_autoloop import build_autoloop_prompt, main
from codex_init import InitSnapshot, SessionSummary, ValidationSummary


def _snapshot() -> InitSnapshot:
    return InitSnapshot(
        branch="main",
        substantive=[],
        runtime=[],
        recent_commits=["1a52288 S214: Wrap — docs, self-learning, project index"],
        session=SessionSummary(
            session_num=214,
            session_date="2026-03-27",
            phase="Session 214 COMPLETE. MT-53 shipped.",
            next_items=["Build codex_init.py", "Build codex_auto.py"],
        ),
        todos=["Build codex_autoloop.py"],
        inbox_subjects=[],
        unread_count=0,
        claude_notes=["[2026-03-27 21:50 UTC] — MESSAGE 2 — Autoloop Adoption"],
        validation=ValidationSummary(mode="smoke", passed=True, summary="Smoke: 10/10 passed"),
    )


class TestBuildAutoLoopPrompt(unittest.TestCase):
    def test_contains_all_three_phases(self):
        prompt = build_autoloop_prompt(
            "/tmp/repo",
            _snapshot(),
            wrap_prompt="Use $cca-desktop-workflow in wrap mode for /tmp/repo.\n",
        )
        self.assertIn("$cca-desktop-workflow", prompt)
        self.assertIn("Autoloop plan:", prompt)
        self.assertIn("Init phase prompt:", prompt)
        self.assertIn("Auto phase prompt:", prompt)
        self.assertIn("Wrap phase prompt:", prompt)
        self.assertIn("Build codex_autoloop.py", prompt)

    def test_respects_deliverable_limit(self):
        prompt = build_autoloop_prompt(
            "/tmp/repo",
            _snapshot(),
            max_deliverables=1,
            wrap_prompt="Use $cca-desktop-workflow in wrap mode for /tmp/repo.\n",
        )
        self.assertIn("Stop after 1 meaningful deliverable", prompt)

    def test_respects_task_override(self):
        prompt = build_autoloop_prompt(
            "/tmp/repo",
            _snapshot(),
            task_override="Wire boot_sequence for mGBA Red",
            wrap_prompt="Use $cca-desktop-workflow in wrap mode for /tmp/repo.\n",
        )
        self.assertIn("Wire boot_sequence for mGBA Red", prompt)
        self.assertIn("Task source: override", prompt)


class TestCLI(unittest.TestCase):
    @patch("codex_autoloop.collect_wrap_snapshot")
    @patch("codex_autoloop.collect_snapshot")
    def test_main_prints_prompt(self, mock_collect, mock_wrap_collect):
        mock_collect.return_value = _snapshot()
        mock_wrap_collect.return_value = type(
            "WrapSnapshot",
            (),
            {"branch": "main", "substantive": [], "runtime": [], "recent_commits": []},
        )()
        with patch("sys.stdout.write") as mock_write:
            exit_code = main(["--root", "/tmp/repo"])
        self.assertEqual(exit_code, 0)
        self.assertTrue(mock_write.called)

    @patch("codex_autoloop.collect_wrap_snapshot")
    @patch("codex_autoloop.collect_snapshot")
    def test_main_writes_file(self, mock_collect, mock_wrap_collect):
        mock_collect.return_value = _snapshot()
        mock_wrap_collect.return_value = type(
            "WrapSnapshot",
            (),
            {"branch": "main", "substantive": [], "runtime": [], "recent_commits": []},
        )()
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
