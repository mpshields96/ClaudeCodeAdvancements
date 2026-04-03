#!/usr/bin/env python3
"""Tests for codex_auto.py."""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from codex_auto import build_auto_prompt, main, pick_auto_task
from codex_init import GitStatusEntry, InitSnapshot, SessionSummary, ValidationSummary


class TestPickAutoTask(unittest.TestCase):
    def setUp(self):
        self.snapshot = InitSnapshot(
            branch="main",
            substantive=[],
            runtime=[],
            recent_commits=[],
            session=SessionSummary(next_items=["Wire boot_sequence for mGBA Red"]),
            todos=["Build codex_init.py", "Build codex_auto.py"],
            inbox_subjects=[],
            unread_count=0,
            claude_notes=[],
            validation=ValidationSummary(mode="smoke", passed=True, summary="Smoke: 10/10 passed"),
            resume_priorities=["Finish fresh-chat handoff"],
        )

    def test_prefers_override(self):
        task, source = pick_auto_task(self.snapshot, task_override="Build codex_auto.py")
        self.assertEqual(task, "Build codex_auto.py")
        self.assertEqual(source, "override")

    def test_prefers_todays_tasks_before_session_next(self):
        task, source = pick_auto_task(self.snapshot)
        self.assertEqual(task, "Build codex_init.py")
        self.assertEqual(source, "todays_tasks")

    def test_falls_back_to_session_next(self):
        self.snapshot.todos = []
        self.snapshot.resume_priorities = []
        task, source = pick_auto_task(self.snapshot)
        self.assertEqual(task, "Wire boot_sequence for mGBA Red")
        self.assertEqual(source, "session_state")

    def test_prefers_resume_priorities_before_session_next(self):
        self.snapshot.todos = []
        task, source = pick_auto_task(self.snapshot)
        self.assertEqual(task, "Finish fresh-chat handoff")
        self.assertEqual(source, "session_resume")

    def test_prefers_priority_picker_after_resume(self):
        self.snapshot.todos = []
        self.snapshot.resume_priorities = []
        self.snapshot.priority_recommendation = "**TOP PICK:** MT-32 (Visual Excellence)"
        task, source = pick_auto_task(self.snapshot)
        self.assertEqual(task, "**TOP PICK:** MT-32 (Visual Excellence)")
        self.assertEqual(source, "priority_picker")

    def test_validation_failure_becomes_task(self):
        self.snapshot.validation = ValidationSummary(
            mode="smoke",
            passed=False,
            summary="Smoke: 8/10 passed",
        )
        task, source = pick_auto_task(self.snapshot)
        self.assertIn("Fix failing baseline validation", task)
        self.assertEqual(source, "validation")


class TestBuildAutoPrompt(unittest.TestCase):
    def test_contains_selected_task_and_constraints(self):
        snapshot = InitSnapshot(
            branch="main",
            substantive=[GitStatusEntry("??", "codex_auto.py")],
            runtime=[GitStatusEntry(" M", ".queue_hook_last_check")],
            recent_commits=["1a52288 S214: Wrap — docs, self-learning, project index"],
            session=SessionSummary(next_items=["Wire boot_sequence for mGBA Red"]),
            todos=["Build codex_auto.py"],
            inbox_subjects=["Finish init command"],
            unread_count=1,
            claude_notes=["[2026-03-27 21:50 UTC] — MESSAGE 2 — Autoloop Adoption"],
            validation=ValidationSummary(mode="smoke", passed=True, summary="Smoke: 10/10 passed"),
            resume_priorities=["MT-32 Phase 5 dashboard refactor"],
            coordination_notes=["Kalshi relay pending: sports_game calibration follow-up"],
            wrap_trend="Trend: improving",
            pending_tips="PENDING TIPS (1 pending): keep fresh chats narrow",
            session_insights="SESSION INSIGHTS: short loops outperform broad sessions",
            recent_corrections="Recent corrections (last 7 days): re-anchor to canonical repo",
            priority_briefing="PRIORITY RANKING: MT-49 > MT-41 > MT-32",
            priority_recommendation="**TOP PICK:** MT-32 (Visual Excellence)",
            mt_proposals="MT PROPOSALS (2 above score 30.0): Claude /dream",
            session_timeline="Last 5 sessions: S256, S254, S253",
            hivemind_status="Hivemind: Phase 3 awaiting first 3-chat session",
        )
        prompt = build_auto_prompt("/tmp/repo", snapshot, task_override=None)
        self.assertIn("$cca-desktop-workflow", prompt)
        self.assertIn("Selected task: Build codex_auto.py", prompt)
        self.assertIn("Task source: todays_tasks", prompt)
        self.assertIn("Stop after 1 meaningful deliverable", prompt)
        self.assertIn("Finish init command", prompt)
        self.assertIn("MT-32 Phase 5 dashboard refactor", prompt)
        self.assertIn("sports_game calibration follow-up", prompt)
        self.assertIn("Trend: improving", prompt)
        self.assertIn("keep fresh chats narrow", prompt)
        self.assertIn("short loops outperform broad sessions", prompt)
        self.assertIn("re-anchor to canonical repo", prompt)
        self.assertIn("bridge_status.py", prompt)
        self.assertIn("PRIORITY RANKING", prompt)
        self.assertIn("TOP PICK", prompt)
        self.assertIn("MT PROPOSALS", prompt)
        self.assertIn("Last 5 sessions", prompt)
        self.assertIn("Hivemind:", prompt)
        self.assertIn("Smoke: 10/10 passed", prompt)


class TestCLI(unittest.TestCase):
    @patch("codex_auto.normalize_cli_root")
    @patch("codex_auto.collect_snapshot")
    def test_main_prints_prompt(self, mock_collect, mock_normalize):
        mock_normalize.return_value = ("/tmp/repo", None)
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
            exit_code = main(["--root", "/tmp/repo", "--task", "Build codex_auto.py"])
        self.assertEqual(exit_code, 0)
        self.assertTrue(mock_write.called)

    @patch("codex_auto.normalize_cli_root")
    @patch("codex_auto.collect_snapshot")
    def test_main_writes_file(self, mock_collect, mock_normalize):
        mock_normalize.return_value = ("/tmp/repo", None)
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
            exit_code = main(["--root", tmpdir, "--write", out_path, "--task", "Build codex_auto.py"])
            self.assertEqual(exit_code, 0)
            self.assertTrue(os.path.exists(out_path))
            with open(out_path, encoding="utf-8") as handle:
                content = handle.read()
            self.assertIn("$cca-desktop-workflow", content)


if __name__ == "__main__":
    unittest.main()
