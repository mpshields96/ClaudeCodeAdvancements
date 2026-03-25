#!/usr/bin/env python3
"""Tests for handoff_generator.py — automated session handoff file generation."""

import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from handoff_generator import (
    HandoffConfig,
    SessionSummary,
    parse_session_state,
    generate_handoff,
    write_handoff,
    _mode_label,
    count_session_commits,
)


class TestHandoffConfig(unittest.TestCase):
    """Test HandoffConfig dataclass."""

    def test_auto_next_session(self):
        """next_session auto-computes from current_session."""
        config = HandoffConfig(current_session=115)
        self.assertEqual(config.next_session, 116)

    def test_explicit_next_session(self):
        """Explicit next_session overrides auto-compute."""
        config = HandoffConfig(current_session=115, next_session=120)
        self.assertEqual(config.next_session, 120)

    def test_invalid_mode_raises(self):
        """Invalid mode raises ValueError."""
        with self.assertRaises(ValueError):
            HandoffConfig(current_session=1, mode="invalid")

    def test_valid_modes(self):
        """All valid modes are accepted."""
        for mode in ("solo", "2chat", "3chat"):
            config = HandoffConfig(current_session=1, mode=mode)
            self.assertEqual(config.mode, mode)

    def test_3chat_sets_kalshi_running(self):
        """3chat mode automatically sets kalshi_running=True."""
        config = HandoffConfig(current_session=1, mode="3chat")
        self.assertTrue(config.kalshi_running)

    def test_solo_kalshi_not_running(self):
        """Solo mode does not set kalshi_running."""
        config = HandoffConfig(current_session=1, mode="solo")
        self.assertFalse(config.kalshi_running)

    def test_default_worker_tasks_empty(self):
        """Default worker_tasks is empty list."""
        config = HandoffConfig(current_session=1)
        self.assertEqual(config.worker_tasks, [])

    def test_default_model(self):
        """Default model is Opus 4.6."""
        config = HandoffConfig(current_session=1)
        self.assertEqual(config.model, "Opus 4.6")

    def test_trial_run_default_zero(self):
        """Default trial_run_number is 0 (not a trial)."""
        config = HandoffConfig(current_session=1)
        self.assertEqual(config.trial_run_number, 0)


class TestModeLabel(unittest.TestCase):
    """Test _mode_label helper."""

    def test_solo(self):
        self.assertEqual(_mode_label("solo"), "Solo CCA")

    def test_2chat(self):
        self.assertEqual(_mode_label("2chat"), "2-chat (desktop + worker)")

    def test_3chat(self):
        self.assertEqual(_mode_label("3chat"), "3-chat (desktop + worker + Kalshi)")

    def test_unknown_returns_raw(self):
        self.assertEqual(_mode_label("unknown"), "unknown")


class TestParseSessionState(unittest.TestCase):
    """Test SESSION_STATE.md parsing."""

    def _write_state(self, content: str) -> Path:
        """Write content to a temp file and return path."""
        f = tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False)
        f.write(content)
        f.close()
        self.addCleanup(lambda: os.unlink(f.name))
        return Path(f.name)

    def test_extract_session_number(self):
        path = self._write_state("## Current State (as of Session 115 — 2026-03-21)")
        summary = parse_session_state(path)
        self.assertEqual(summary.session_number, 115)

    def test_extract_date(self):
        path = self._write_state("## Current State (as of Session 115 — 2026-03-21)")
        summary = parse_session_state(path)
        self.assertEqual(summary.date, "2026-03-21")

    def test_extract_test_count(self):
        path = self._write_state("**Tests**: ~7104 passing (~178 suites).")
        summary = parse_session_state(path)
        self.assertEqual(summary.test_count, 7104)

    def test_extract_suite_count(self):
        path = self._write_state("**Tests**: ~7104 passing (~178 suites).")
        summary = parse_session_state(path)
        self.assertEqual(summary.suite_count, 178)

    def test_extract_pending_manual(self):
        content = textwrap.dedent("""\
            **Still pending (Matthew manual):**
            - AUTH FIX: run the command
            - Bridge sync: copy the file

            **Next (prioritized):**
        """)
        path = self._write_state(content)
        summary = parse_session_state(path)
        self.assertEqual(len(summary.pending_manual), 2)
        self.assertIn("AUTH FIX", summary.pending_manual[0])

    def test_extract_next_priorities(self):
        content = textwrap.dedent("""\
            **Next (prioritized):**
            1. **Kalshi bot maintenance** — priority one.
            2. **Design-skills expansion** — charts.
            3. **Autonomous loop** — sessions.

            **What was done this session (S112):**
        """)
        path = self._write_state(content)
        summary = parse_session_state(path)
        self.assertEqual(len(summary.next_priorities), 3)
        self.assertIn("Kalshi", summary.next_priorities[0])

    def test_missing_file_returns_empty(self):
        summary = parse_session_state(Path("/nonexistent/file.md"))
        self.assertEqual(summary.session_number, 0)
        self.assertEqual(summary.test_count, 0)

    def test_extract_what_was_done(self):
        content = textwrap.dedent("""\
            **What was done this session (S115):**
            - Built AreaChart
            - Built StackedBarChart
            - HeatmapChart by worker

            **Next (prioritized):**
        """)
        path = self._write_state(content)
        summary = parse_session_state(path)
        self.assertIn("AreaChart", summary.what_was_done)

    def test_empty_file(self):
        path = self._write_state("")
        summary = parse_session_state(path)
        self.assertEqual(summary.session_number, 0)


class TestGenerateHandoff(unittest.TestCase):
    """Test handoff content generation."""

    def _make_summary(self, **kwargs):
        defaults = {
            "session_number": 115,
            "date": "2026-03-21",
            "test_count": 7104,
            "suite_count": 178,
            "what_was_done": "- Built AreaChart\n- Built StackedBarChart",
            "pending_manual": ["AUTH FIX: run the fix", "Bridge sync: copy file"],
            "next_priorities": ["Kalshi bot", "Design expansion"],
        }
        defaults.update(kwargs)
        return SessionSummary(**defaults)

    def test_solo_header(self):
        config = HandoffConfig(current_session=116, mode="solo")
        content = generate_handoff(config, self._make_summary())
        self.assertIn("S116 -> S117", content)
        self.assertIn("Solo CCA", content)

    def test_3chat_header(self):
        config = HandoffConfig(current_session=116, mode="3chat")
        content = generate_handoff(config, self._make_summary())
        self.assertIn("3-chat", content)

    def test_trial_run_in_header(self):
        config = HandoffConfig(current_session=116, mode="3chat", trial_run_number=2)
        content = generate_handoff(config, self._make_summary())
        self.assertIn("TRIAL RUN #3", content)

    def test_resume_prompt_present(self):
        config = HandoffConfig(current_session=116, mode="solo")
        content = generate_handoff(config, self._make_summary())
        self.assertIn("RESUME PROMPT", content)
        self.assertIn("/cca-init", content)

    def test_test_count_in_output(self):
        config = HandoffConfig(current_session=116)
        content = generate_handoff(config, self._make_summary())
        self.assertIn("7104 tests", content)
        self.assertIn("178 suites", content)

    def test_pending_manual_items(self):
        config = HandoffConfig(current_session=116)
        content = generate_handoff(config, self._make_summary())
        self.assertIn("AUTH FIX", content)
        self.assertIn("Bridge sync", content)

    def test_chat_layout_table_for_3chat(self):
        config = HandoffConfig(current_session=116, mode="3chat")
        content = generate_handoff(config, self._make_summary())
        self.assertIn("Coordinator", content)
        self.assertIn("Worker", content)
        self.assertIn("Kalshi Main", content)
        self.assertIn("DO NOT interfere", content)

    def test_no_chat_layout_for_solo(self):
        config = HandoffConfig(current_session=116, mode="solo")
        content = generate_handoff(config, self._make_summary())
        self.assertNotIn("Coordinator", content)
        self.assertNotIn("YOU MUST LAUNCH", content)

    def test_worker_tasks_in_output(self):
        config = HandoffConfig(
            current_session=116, mode="3chat",
            worker_tasks=["Build StackedAreaChart", "Build GroupedBarChart", "Consistency audit"]
        )
        content = generate_handoff(config, self._make_summary())
        self.assertIn("PRIMARY", content)
        self.assertIn("SECONDARY", content)
        self.assertIn("TERTIARY", content)
        self.assertIn("StackedAreaChart", content)
        self.assertIn("GroupedBarChart", content)

    def test_no_worker_tasks_for_solo(self):
        config = HandoffConfig(current_session=116, mode="solo")
        content = generate_handoff(config, self._make_summary())
        self.assertNotIn("WORKER TASK", content)

    def test_desktop_focus_in_output(self):
        config = HandoffConfig(
            current_session=116, mode="2chat",
            desktop_focus="self-learning improvements"
        )
        content = generate_handoff(config, self._make_summary())
        self.assertIn("self-learning improvements", content)
        self.assertIn("Coordination rounds", content)

    def test_safety_rules_for_multichat(self):
        config = HandoffConfig(current_session=116, mode="2chat")
        content = generate_handoff(config, self._make_summary())
        self.assertIn("SAFETY RULES", content)
        self.assertIn("DO NOT rush", content)
        self.assertIn("Peak hours", content)

    def test_no_safety_rules_for_solo(self):
        config = HandoffConfig(current_session=116, mode="solo")
        content = generate_handoff(config, self._make_summary())
        self.assertNotIn("SAFETY RULES", content)

    def test_success_criteria_solo(self):
        config = HandoffConfig(current_session=116, mode="solo")
        content = generate_handoff(config, self._make_summary())
        self.assertIn("SUCCESS CRITERIA", content)
        self.assertIn("All tests pass", content)

    def test_success_criteria_3chat(self):
        config = HandoffConfig(current_session=116, mode="3chat")
        content = generate_handoff(config, self._make_summary())
        self.assertIn("Worker completes 2-3 tasks", content)
        self.assertIn("Kalshi chat runs undisturbed", content)

    def test_key_files_section(self):
        config = HandoffConfig(current_session=116, mode="3chat")
        content = generate_handoff(config, self._make_summary())
        self.assertIn("KEY FILES", content)
        self.assertIn("HIVEMIND_ROLLOUT", content)

    def test_key_files_solo_no_hivemind(self):
        config = HandoffConfig(current_session=116, mode="solo")
        content = generate_handoff(config, self._make_summary())
        self.assertIn("KEY FILES", content)
        self.assertNotIn("HIVEMIND_ROLLOUT", content)

    def test_what_was_done_truncated(self):
        """Long what_was_done is truncated to 4 bullet points."""
        summary = self._make_summary(what_was_done=(
            "- Item one here\n- Item two here\n- Item three here\n"
            "- Item four here\n- Item five should be cut\n- Item six cut too"
        ))
        config = HandoffConfig(current_session=116)
        content = generate_handoff(config, summary)
        # Should include first 4 items
        self.assertIn("Item one", content)
        self.assertIn("Item four", content)

    def test_no_test_count_when_zero(self):
        summary = self._make_summary(test_count=0, suite_count=0)
        config = HandoffConfig(current_session=116)
        content = generate_handoff(config, summary)
        # Check that "0 tests" doesn't appear in the success criteria / resume section
        # (git log in RECENT COMMITS may contain "tests" in commit messages — that's fine)
        sections_before_commits = content.split("## RECENT COMMITS")[0] if "## RECENT COMMITS" in content else content
        self.assertNotIn("0 tests", sections_before_commits)

    def test_2chat_layout_no_kalshi(self):
        config = HandoffConfig(current_session=116, mode="2chat")
        content = generate_handoff(config, self._make_summary())
        self.assertIn("Coordinator", content)
        self.assertIn("Worker", content)
        self.assertNotIn("Kalshi Main", content)


class TestWriteHandoff(unittest.TestCase):
    """Test writing handoff to file."""

    def test_write_creates_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = HandoffConfig(current_session=116)
            content = "# Test handoff content"
            with patch('handoff_generator.PROJECT_ROOT', Path(tmpdir)):
                path = write_handoff(config, content)
                self.assertTrue(path.exists())
                self.assertEqual(path.read_text(), content)
                self.assertEqual(path.name, "SESSION_HANDOFF_S116.md")

    def test_write_overwrites_existing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = HandoffConfig(current_session=116)
            existing = Path(tmpdir) / "SESSION_HANDOFF_S116.md"
            existing.write_text("old content")
            with patch('handoff_generator.PROJECT_ROOT', Path(tmpdir)):
                write_handoff(config, "new content")
                self.assertEqual(existing.read_text(), "new content")


class TestSessionSummaryDefaults(unittest.TestCase):
    """Test SessionSummary default values."""

    def test_defaults(self):
        s = SessionSummary()
        self.assertEqual(s.session_number, 0)
        self.assertEqual(s.date, "")
        self.assertEqual(s.test_count, 0)
        self.assertEqual(s.suite_count, 0)
        self.assertEqual(s.what_was_done, "")
        self.assertEqual(s.pending_manual, [])
        self.assertEqual(s.next_priorities, [])
        self.assertEqual(s.recent_commits, [])


class TestGetRecentCommits(unittest.TestCase):
    """Test git commit retrieval."""

    @patch('handoff_generator.subprocess.run')
    def test_returns_commits(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="abc1234 First commit\ndef5678 Second commit\n"
        )
        commits = []
        # Can't easily test without mocking PROJECT_ROOT, so just test the mock path
        from handoff_generator import get_recent_commits
        commits = get_recent_commits(2)
        self.assertEqual(len(commits), 2)
        self.assertIn("First commit", commits[0])

    @patch('handoff_generator.subprocess.run')
    def test_handles_git_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        from handoff_generator import get_recent_commits
        commits = get_recent_commits()
        self.assertEqual(commits, [])

    @patch('handoff_generator.subprocess.run')
    def test_handles_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired("git", 10)
        from handoff_generator import get_recent_commits
        commits = get_recent_commits()
        self.assertEqual(commits, [])


class TestEndToEnd(unittest.TestCase):
    """End-to-end test: parse state -> generate -> verify structure."""

    def test_full_pipeline(self):
        """Full pipeline produces valid markdown."""
        state_content = textwrap.dedent("""\
            ## Current State (as of Session 115 — 2026-03-21)

            **Phase:** Session 115 COMPLETE.

            **What was done this session (S115):**
            - Built AreaChart with gradient fill
            - Built StackedBarChart for composition
            - Worker built HeatmapChart (42 tests)

            **Still pending (Matthew manual):**
            - AUTH FIX: run the sed command
            - Bridge sync: copy the file

            **Next (prioritized):**
            1. Kalshi bot maintenance
            2. Design-skills expansion

            **Tests**: ~7104 passing (~178 suites).
        """)
        f = tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False)
        f.write(state_content)
        f.close()

        try:
            summary = parse_session_state(Path(f.name))
            config = HandoffConfig(
                current_session=115, mode="3chat",
                worker_tasks=["StackedAreaChart", "GroupedBarChart", "Consistency audit"],
                desktop_focus="self-learning module improvements",
                trial_run_number=1,
            )
            content = generate_handoff(config, summary)

            # Verify structure
            self.assertIn("S115 -> S116", content)
            self.assertIn("TRIAL RUN #2", content)
            self.assertIn("RESUME PROMPT", content)
            self.assertIn("7104 tests", content)
            self.assertIn("AUTH FIX", content)
            self.assertIn("3-CHAT LAYOUT", content)
            self.assertIn("WORKER TASK ASSIGNMENT", content)
            self.assertIn("PRIMARY", content)
            self.assertIn("DESKTOP FOCUS", content)
            self.assertIn("self-learning", content)
            self.assertIn("SAFETY RULES", content)
            self.assertIn("SUCCESS CRITERIA", content)
            self.assertIn("KEY FILES", content)
        finally:
            os.unlink(f.name)

    def test_solo_pipeline(self):
        """Solo mode produces simpler output."""
        summary = SessionSummary(
            session_number=116, date="2026-03-21",
            test_count=7200, suite_count=180,
        )
        config = HandoffConfig(current_session=116, mode="solo")
        content = generate_handoff(config, summary)

        self.assertIn("S116 -> S117", content)
        self.assertIn("Solo CCA", content)
        self.assertNotIn("WORKER TASK", content)
        self.assertNotIn("SAFETY RULES", content)
        self.assertNotIn("Coordinator", content)
        self.assertIn("SUCCESS CRITERIA", content)


import subprocess  # for TestGetRecentCommits mock


if __name__ == "__main__":
    unittest.main()
