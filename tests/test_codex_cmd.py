#!/usr/bin/env python3
"""Tests for codex_cmd.py."""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from codex_cmd import (
    PolybotSnapshot,
    build_polybot_auto_prompt,
    build_polybot_init_prompt,
    build_polybot_wrap_prompt,
    detect_repo_type,
    main,
    normalize_root,
    _parse_polybot_pending_tasks,
    _parse_polybot_state,
)


class TestPolybotParsing(unittest.TestCase):
    def test_parse_pending_tasks(self):
        content = """## PENDING TASKS (priority order)
1. Check bot liveness
2. Review CCA delivery

## STRATEGY STATUS
foo
"""
        tasks = _parse_polybot_pending_tasks(content)
        self.assertEqual(tasks, ["Check bot liveness", "Review CCA delivery"])

    def test_parse_bot_state(self):
        content = """## BOT STATE (S254 CCA — 2026-04-03 02:30 UTC)
Bot RUNNING PID 12448
All-time live P&L: +88.32 USD

## PENDING TASKS
1. x
"""
        state = _parse_polybot_state(content)
        self.assertEqual(state[0], "Bot RUNNING PID 12448")
        self.assertIn("+88.32 USD", state[1])


class TestRepoDetection(unittest.TestCase):
    def test_detect_repo_type_cca(self):
        self.assertEqual(detect_repo_type(os.path.expanduser("~/Projects/ClaudeCodeAdvancements")), "cca")

    def test_detect_repo_type_polybot(self):
        self.assertEqual(detect_repo_type(os.path.expanduser("~/Projects/polymarket-bot")), "polybot")


class TestPolybotPromptBuilders(unittest.TestCase):
    def setUp(self):
        self.snapshot = PolybotSnapshot(
            branch="main",
            substantive=[" M src/foo.py"],
            runtime=[" M bot.pid"],
            recent_commits=["abc1234 Example commit"],
            pending_tasks=["Check bot liveness", "Review CCA delivery"],
            bot_state=["Bot RUNNING PID 12448", "All-time live P&L: +88.32 USD"],
        )

    def test_init_prompt_contains_state_and_tasks(self):
        prompt = build_polybot_init_prompt("/tmp/polybot", self.snapshot)
        self.assertIn("SESSION_HANDOFF.md", prompt)
        self.assertIn("Check bot liveness", prompt)
        self.assertIn("+88.32 USD", prompt)

    def test_auto_prompt_uses_first_pending_task(self):
        prompt = build_polybot_auto_prompt("/tmp/polybot", self.snapshot)
        self.assertIn("Selected task: Check bot liveness", prompt)

    def test_wrap_prompt_contains_wrap_checklist(self):
        prompt = build_polybot_wrap_prompt("/tmp/polybot", self.snapshot)
        self.assertIn("Wrap checklist:", prompt)
        self.assertIn("src/foo.py", prompt)


class TestCLI(unittest.TestCase):
    @patch("codex_cmd.build_prompt")
    @patch("codex_cmd.normalize_root")
    def test_main_prints_generated_prompt(self, mock_normalize, mock_build_prompt):
        mock_normalize.return_value = ("/tmp/repo", "cca")
        mock_build_prompt.return_value = "prompt text\n"
        with patch("sys.stdout.write") as mock_write:
            exit_code = main(["init"])
        self.assertEqual(exit_code, 0)
        mock_write.assert_called_once_with("prompt text\n")

    @patch("codex_cmd.launch_codex")
    @patch("codex_cmd.build_prompt")
    @patch("codex_cmd.normalize_root")
    def test_main_launches_when_requested(self, mock_normalize, mock_build_prompt, mock_launch):
        mock_normalize.return_value = ("/tmp/repo", "cca")
        mock_build_prompt.return_value = "prompt text\n"
        mock_launch.return_value = 0
        with patch("codex_cmd.write_prompt") as mock_write_prompt:
            exit_code = main(["auto", "--launch"])
        self.assertEqual(exit_code, 0)
        mock_launch.assert_called_once()
        mock_write_prompt.assert_called_once_with("/tmp/repo/CODEX_AUTO_PROMPT.md", "prompt text\n")

    @patch("codex_cmd.launch_codex")
    @patch("codex_cmd.build_prompt")
    @patch("codex_cmd.normalize_root")
    def test_next_launch_writes_same_auto_handoff_file(self, mock_normalize, mock_build_prompt, mock_launch):
        mock_normalize.return_value = ("/tmp/repo", "cca")
        mock_build_prompt.return_value = "prompt text\n"
        mock_launch.return_value = 0
        with patch("codex_cmd.write_prompt") as mock_write_prompt:
            exit_code = main(["next", "--launch"])
        self.assertEqual(exit_code, 0)
        mock_write_prompt.assert_called_once_with("/tmp/repo/CODEX_AUTO_PROMPT.md", "prompt text\n")

    @patch("codex_cmd.normalize_root")
    def test_main_writes_output_file(self, mock_normalize):
        mock_normalize.return_value = ("/tmp/repo", "cca")
        with patch("codex_cmd.build_prompt", return_value="prompt text\n"):
            with tempfile.TemporaryDirectory() as tmpdir:
                path = os.path.join(tmpdir, "prompt.md")
                exit_code = main(["wrap", "--write", path])
                self.assertEqual(exit_code, 0)
                with open(path, encoding="utf-8") as handle:
                    self.assertEqual(handle.read(), "prompt text\n")


if __name__ == "__main__":
    unittest.main()
