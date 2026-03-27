#!/usr/bin/env python3
"""Tests for codex_init.py."""

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from codex_init import (
    GitStatusEntry,
    InitSnapshot,
    SessionSummary,
    ValidationSummary,
    build_init_prompt,
    main,
    parse_claude_to_codex,
    parse_codex_inbox,
    parse_session_state,
    parse_todays_tasks,
    run_validation,
    select_top_task,
    suggest_reasoning_level,
)


class TestParseSessionState(unittest.TestCase):
    def test_extracts_session_phase_and_next_items(self):
        content = """## Current State (as of Session 214 — 2026-03-27)

**Phase:** Session 214 COMPLETE. MT-53 shipped.

**Next:**
1. Build codex_init.py
2. Build codex_auto.py
"""
        summary = parse_session_state(content)
        self.assertEqual(summary.session_num, 214)
        self.assertEqual(summary.session_date, "2026-03-27")
        self.assertIn("MT-53 shipped", summary.phase)
        self.assertEqual(summary.next_items[0], "Build codex_init.py")

    def test_handles_missing_sections(self):
        summary = parse_session_state("No structured state here.")
        self.assertIsNone(summary.session_num)
        self.assertEqual(summary.next_items, [])


class TestParseTodaysTasks(unittest.TestCase):
    def test_extracts_remaining_todos(self):
        content = """### C1. Build init command [TODO]
### C2. Build auto command [IN PROGRESS]
### C3. Add tests [TODO]
"""
        todos = parse_todays_tasks(content)
        self.assertEqual(
            todos,
            ["C1. Build init command", "C3. Add tests"],
        )


class TestCommsParsing(unittest.TestCase):
    def test_parse_codex_inbox_empty(self):
        inbox = parse_codex_inbox("No unread messages for Codex.\n")
        self.assertEqual(inbox.unread_count, 0)
        self.assertEqual(inbox.subjects, [])

    def test_parse_codex_inbox_with_subjects(self):
        inbox = parse_codex_inbox(
            "Inbox for Codex (2 unread):\n\n"
            "  [HIGH] Finish init command\n"
            "    Please land it.\n\n"
            "  [LOW] Optional docs cleanup\n"
        )
        self.assertEqual(inbox.unread_count, 2)
        self.assertEqual(inbox.subjects[0], "Finish init command")

    def test_parse_claude_to_codex_headings(self):
        headings = parse_claude_to_codex(
            "## [2026-03-27 21:50 UTC] — MESSAGE 1 — Emulator Swap\n"
            "Body\n\n"
            "## [2026-03-27 22:12 UTC] — UPDATE 3 — MT-53 Progress Report\n"
        )
        self.assertEqual(len(headings), 2)
        self.assertIn("Emulator Swap", headings[0])
        self.assertIn("MT-53 Progress Report", headings[1])


class TestTaskSelection(unittest.TestCase):
    def test_select_top_task_prefers_todays_tasks(self):
        task = select_top_task(
            todos=["Build init command", "Build auto command"],
            session_next=["Pokemon boot sequence"],
        )
        self.assertEqual(task, "Build init command")

    def test_reasoning_high_for_architecture_work(self):
        level = suggest_reasoning_level("Design autoloop coordination architecture")
        self.assertEqual(level, "high recommended")

    def test_reasoning_default_for_narrow_work(self):
        level = suggest_reasoning_level("Wire boot_sequence for mGBA Red")
        self.assertEqual(level, "default")


class TestValidation(unittest.TestCase):
    @patch("codex_init.subprocess.run")
    def test_uses_fresh_cache_without_smoke(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Cache: 100 tests, 10 suites, all passed (5m ago, session S214)\n",
            stderr="",
        )
        result = run_validation("/tmp/repo")
        self.assertTrue(result.passed)
        self.assertEqual(result.mode, "cache")
        self.assertIn("Cache:", result.summary)
        self.assertEqual(mock_run.call_count, 1)

    @patch("codex_init.subprocess.run")
    def test_runs_smoke_when_cache_is_stale(self, mock_run):
        mock_run.side_effect = [
            MagicMock(
                returncode=0,
                stdout="Cache stale (8320m old, test files changed). Run smoke or full suite.\n",
                stderr="",
            ),
            MagicMock(
                returncode=0,
                stdout="Smoke: 10/10 passed\n",
                stderr="",
            ),
        ]
        result = run_validation("/tmp/repo")
        self.assertTrue(result.passed)
        self.assertEqual(result.mode, "smoke")
        self.assertIn("10/10", result.summary)
        self.assertEqual(mock_run.call_count, 2)


class TestBuildInitPrompt(unittest.TestCase):
    def test_contains_required_briefing_fields(self):
        snapshot = InitSnapshot(
            branch="main",
            substantive=[GitStatusEntry(" M", "SESSION_RESUME.md")],
            runtime=[GitStatusEntry(" M", ".queue_hook_last_check")],
            recent_commits=["1a52288 S214: Wrap — docs, self-learning, project index"],
            session=SessionSummary(
                session_num=214,
                session_date="2026-03-27",
                phase="Session 214 COMPLETE. MT-53 shipped.",
                next_items=["Build codex_init.py", "Build codex_auto.py"],
            ),
            todos=["Build init command"],
            inbox_subjects=[],
            unread_count=0,
            claude_notes=["[2026-03-27 21:50 UTC] — MESSAGE 2 — Autoloop Adoption"],
            validation=ValidationSummary(
                mode="smoke",
                passed=True,
                summary="Smoke: 10/10 passed",
            ),
        )
        prompt = build_init_prompt("/tmp/repo", snapshot)
        self.assertIn("$cca-desktop-workflow", prompt)
        self.assertIn("Current branch: main", prompt)
        self.assertIn("Build init command", prompt)
        self.assertIn("Suggested reasoning level", prompt)
        self.assertIn("Immediate next step", prompt)
        self.assertIn("Smoke: 10/10 passed", prompt)


class TestCLI(unittest.TestCase):
    @patch("codex_init.collect_snapshot")
    def test_main_prints_prompt(self, mock_collect):
        mock_collect.return_value = InitSnapshot(
            branch="main",
            substantive=[],
            runtime=[],
            recent_commits=[],
            session=SessionSummary(),
            todos=[],
            inbox_subjects=[],
            unread_count=0,
            claude_notes=[],
            validation=ValidationSummary(mode="cache", passed=True, summary="Cache: fresh"),
        )
        with patch("sys.stdout.write") as mock_write:
            exit_code = main(["--root", "/tmp/repo"])
        self.assertEqual(exit_code, 0)
        self.assertTrue(mock_write.called)

    @patch("codex_init.collect_snapshot")
    def test_main_writes_file(self, mock_collect):
        mock_collect.return_value = InitSnapshot(
            branch="main",
            substantive=[],
            runtime=[],
            recent_commits=[],
            session=SessionSummary(),
            todos=[],
            inbox_subjects=[],
            unread_count=0,
            claude_notes=[],
            validation=ValidationSummary(mode="cache", passed=True, summary="Cache: fresh"),
        )
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
