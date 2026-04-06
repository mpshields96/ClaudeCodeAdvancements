"""Tests for session_start_hook.py — SessionStart hook."""

import json
import os
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import session_start_hook
from session_start_hook import get_budget_window, get_top_task, main


class TestBudgetWindow(unittest.TestCase):
    """Test peak/off-peak detection."""

    @patch("session_start_hook.datetime")
    def test_peak_weekday(self, mock_dt):
        from datetime import datetime as real_dt
        mock_dt.now.return_value = real_dt(2026, 4, 1, 10, 0)  # 10 AM Tue
        result = get_budget_window()
        self.assertIn("PEAK", result)

    @patch("session_start_hook.datetime")
    def test_offpeak_evening(self, mock_dt):
        from datetime import datetime as real_dt
        mock_dt.now.return_value = real_dt(2026, 4, 1, 20, 0)  # 8 PM Tue
        result = get_budget_window()
        self.assertIn("OFF-PEAK", result)

    @patch("session_start_hook.datetime")
    def test_offpeak_weekend(self, mock_dt):
        from datetime import datetime as real_dt
        mock_dt.now.return_value = real_dt(2026, 4, 4, 10, 0)  # 10 AM Fri... wait, 4th is Sat
        # April 4, 2026 is Saturday
        mock_dt.now.return_value = real_dt(2026, 4, 4, 10, 0)
        result = get_budget_window()
        self.assertIn("OFF-PEAK", result)


class TestGetTopTask(unittest.TestCase):
    """Test task extraction from TODAYS_TASKS.md."""

    def test_finds_todo(self):
        with patch.object(session_start_hook, "CCA_ROOT", Path(__file__).resolve().parents[2]):
            task = get_top_task()
        # Should return something (TODAYS_TASKS.md exists in CCA)
        self.assertIsInstance(task, str)
        self.assertTrue(len(task) > 0)

    def test_falls_back_to_session_state_next_block_when_no_todos(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "TODAYS_TASKS.md").write_text(
                "# Tasks\n\n### CHAT 35: Work\n\n#### 35A. Something [DONE]\n"
            )
            (root / "SESSION_STATE.md").write_text(
                "# Session State\n\n"
                "## Current State\n\n"
                "**Next:**\n"
                "1. Chat 35: /review slash command (BUILD #12)\n"
                "2. Chat 35: context-monitor 4 new advisory signals\n"
            )

            with patch.object(session_start_hook, "CCA_ROOT", root):
                task = get_top_task()

        self.assertEqual(task, "Chat 35: /review slash command (BUILD #12)")

    def test_session_state_fallback_skips_numeric_prefix(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "TODAYS_TASKS.md").write_text("# Tasks\nNo active TODO markers.\n")
            (root / "SESSION_STATE.md").write_text(
                "# Session State\n\n"
                "## Current State\n\n"
                "**Next:**\n"
                "2. Wire collision_reader_crystal into main.py\n"
            )

            with patch.object(session_start_hook, "CCA_ROOT", root):
                task = get_top_task()

        self.assertEqual(task, "Wire collision_reader_crystal into main.py")


class TestMainHook(unittest.TestCase):
    """Test the full hook pipeline."""

    @patch("session_start_hook.get_top_task", return_value="Top task")
    @patch("session_start_hook.get_budget_window", return_value="OFF-PEAK (100%)")
    @patch("session_start_hook.run_smoke_test", return_value=(True, "Smoke: 10/10 passed"))
    def test_unset_enable_tool_search_shows_advisory(self, _mock_smoke, _mock_budget, _mock_task):
        hook_input = json.dumps({
            "session_id": "test-123",
            "cwd": "/Users/matthewshields/Projects/ClaudeCodeAdvancements"
        })
        env = dict(os.environ)
        env.pop("ENABLE_TOOL_SEARCH", None)

        with patch.dict(os.environ, env, clear=True):
            with patch("sys.stdin", StringIO(hook_input)):
                with patch("sys.stdout", new_callable=StringIO) as mock_out:
                    main()
                    output = mock_out.getvalue().strip()

        data = json.loads(output)
        self.assertIn("ADVISORY: ENABLE_TOOL_SEARCH not set", data["message"])

    @patch("session_start_hook.get_top_task", return_value="Top task")
    @patch("session_start_hook.get_budget_window", return_value="OFF-PEAK (100%)")
    @patch("session_start_hook.run_smoke_test", return_value=(True, "Smoke: 10/10 passed"))
    def test_set_enable_tool_search_hides_advisory(self, _mock_smoke, _mock_budget, _mock_task):
        hook_input = json.dumps({
            "session_id": "test-123",
            "cwd": "/Users/matthewshields/Projects/ClaudeCodeAdvancements"
        })

        with patch.dict(os.environ, {"ENABLE_TOOL_SEARCH": "false"}, clear=True):
            with patch("sys.stdin", StringIO(hook_input)):
                with patch("sys.stdout", new_callable=StringIO) as mock_out:
                    main()
                    output = mock_out.getvalue().strip()

        data = json.loads(output)
        self.assertNotIn("ADVISORY: ENABLE_TOOL_SEARCH not set", data["message"])

    def test_cca_project_outputs_status(self):
        """Hook should output JSON for CCA project."""
        hook_input = json.dumps({
            "session_id": "test-123",
            "cwd": "/Users/matthewshields/Projects/ClaudeCodeAdvancements"
        })
        with patch("sys.stdin", StringIO(hook_input)):
            with patch("sys.stdout", new_callable=StringIO) as mock_out:
                main()
                output = mock_out.getvalue().strip()

        self.assertTrue(len(output) > 0, "Hook should produce output for CCA project")
        data = json.loads(output)
        self.assertIn("message", data)
        self.assertIn("Tests:", data["message"])
        self.assertIn("Budget:", data["message"])
        self.assertIn("Next:", data["message"])

    def test_non_cca_project_silent(self):
        """Hook should produce no output for non-CCA projects."""
        hook_input = json.dumps({
            "session_id": "test-456",
            "cwd": "/Users/matthewshields/Projects/polymarket-bot"
        })
        with patch("sys.stdin", StringIO(hook_input)):
            with patch("sys.stdout", new_callable=StringIO) as mock_out:
                main()
                output = mock_out.getvalue().strip()

        self.assertEqual(output, "", "Hook should be silent for non-CCA projects")

    def test_disabled_via_env(self):
        """Hook should be silent when disabled."""
        hook_input = json.dumps({
            "session_id": "test",
            "cwd": "/Users/matthewshields/Projects/ClaudeCodeAdvancements"
        })
        with patch.dict(os.environ, {"CCA_SESSION_START_DISABLED": "1"}):
            with patch("sys.stdin", StringIO(hook_input)):
                with patch("sys.stdout", new_callable=StringIO) as mock_out:
                    main()
                    output = mock_out.getvalue().strip()

        self.assertEqual(output, "", "Hook should be silent when disabled")

    def test_empty_stdin(self):
        """Hook should handle empty/missing stdin gracefully."""
        with patch("sys.stdin", StringIO("")):
            with patch("sys.stdout", new_callable=StringIO) as mock_out:
                main()  # Should not raise


if __name__ == "__main__":
    unittest.main()
