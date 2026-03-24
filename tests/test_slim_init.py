"""
test_slim_init.py — Tests for slim_init.py

Codifies the slim init process: smoke test + priority pick + summary.
Replaces the 10-minute full init with a ~1 minute automated startup.

TDD: tests written first, implementation follows.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestSlimInitConfig(unittest.TestCase):
    """Test configuration and constants."""

    def test_has_required_steps(self):
        from slim_init import INIT_STEPS
        self.assertIn("smoke", INIT_STEPS)
        self.assertIn("priority", INIT_STEPS)
        self.assertIn("summary", INIT_STEPS)

    def test_default_session_state_path(self):
        from slim_init import SESSION_STATE_PATH
        self.assertTrue(str(SESSION_STATE_PATH).endswith("SESSION_STATE.md"))


class TestReadSessionState(unittest.TestCase):
    """Test reading SESSION_STATE.md for quick orientation."""

    def test_parse_session_number(self):
        from slim_init import parse_session_state
        content = "## Current State (as of Session 98 — 2026-03-22)\n\n**Phase:** Done."
        result = parse_session_state(content)
        self.assertEqual(result["session_num"], 98)

    def test_parse_session_date(self):
        from slim_init import parse_session_state
        content = "## Current State (as of Session 98 — 2026-03-22)\n\n**Phase:** Done."
        result = parse_session_state(content)
        self.assertEqual(result["session_date"], "2026-03-22")

    def test_parse_missing_session(self):
        from slim_init import parse_session_state
        content = "Nothing here."
        result = parse_session_state(content)
        self.assertIsNone(result.get("session_num"))

    def test_parse_test_count(self):
        from slim_init import parse_session_state
        content = "Tests: ~109 suites, ~4373 total passing."
        result = parse_session_state(content)
        self.assertEqual(result["test_count"], 4373)
        self.assertEqual(result["suite_count"], 109)

    def test_parse_test_count_alternative_format(self):
        from slim_init import parse_session_state
        content = "Tests: 2897/2897 passing"
        result = parse_session_state(content)
        self.assertEqual(result["test_count"], 2897)

    def test_parse_hivemind_status(self):
        from slim_init import parse_session_state
        content = "Hivemind: 7th consecutive PASS."
        result = parse_session_state(content)
        self.assertEqual(result["hivemind_streak"], 7)

    def test_parse_next_items(self):
        from slim_init import parse_session_state
        content = "**Next (prioritized):**\n1. Install Claude Control\n2. GitHub push\n3. MT-22 Trial"
        result = parse_session_state(content)
        self.assertEqual(len(result["next_items"]), 3)
        self.assertIn("Install Claude Control", result["next_items"][0])


class TestRunSmoke(unittest.TestCase):
    """Test smoke test runner wrapper."""

    @patch("slim_init.subprocess.run")
    def test_smoke_pass(self, mock_run):
        from slim_init import run_smoke
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Smoke: 10/10 passed",
            stderr=""
        )
        result = run_smoke()
        self.assertTrue(result["passed"])
        self.assertEqual(result["suites_passed"], 10)
        self.assertEqual(result["suites_total"], 10)

    @patch("slim_init.subprocess.run")
    def test_smoke_partial_fail(self, mock_run):
        from slim_init import run_smoke
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="Smoke: 8/10 passed\nFailed: test_bash_guard.py, test_alert.py",
            stderr=""
        )
        result = run_smoke()
        self.assertFalse(result["passed"])
        self.assertEqual(result["suites_passed"], 8)

    @patch("slim_init.subprocess.run")
    def test_smoke_timeout(self, mock_run):
        from slim_init import run_smoke
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired("python3", 60)
        result = run_smoke()
        self.assertFalse(result["passed"])
        self.assertIn("timeout", result.get("error", "").lower())


class TestRunPriority(unittest.TestCase):
    """Test priority picker wrapper."""

    @patch("slim_init.subprocess.run")
    def test_priority_recommend(self, mock_run):
        from slim_init import run_priority
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='**TOP PICK:** MT-22 (Autonomous 1-hour loop) — score 11.0\n  Next: Trial #3',
            stderr=""
        )
        result = run_priority()
        self.assertIn("MT-22", result["top_pick"])

    @patch("slim_init.subprocess.run")
    def test_priority_failure(self, mock_run):
        from slim_init import run_priority
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error: MASTER_TASKS.md not found"
        )
        result = run_priority()
        self.assertIn("error", result)


class TestInitSummary(unittest.TestCase):
    """Test the combined init summary."""

    def test_summary_all_good(self):
        from slim_init import build_summary
        smoke = {"passed": True, "suites_passed": 10, "suites_total": 10}
        priority = {"top_pick": "MT-22 (Autonomous loop)", "raw": "..."}
        state = {"session_num": 98, "test_count": 4373, "suite_count": 109}
        summary = build_summary(smoke, priority, state)
        self.assertTrue(summary["ready"])
        self.assertIn("MT-22", summary["top_pick"])
        self.assertEqual(summary["last_session"], 98)

    def test_summary_smoke_failed(self):
        from slim_init import build_summary
        smoke = {"passed": False, "suites_passed": 8, "suites_total": 10}
        priority = {"top_pick": "MT-22", "raw": "..."}
        state = {"session_num": 98}
        summary = build_summary(smoke, priority, state)
        self.assertFalse(summary["ready"])
        self.assertIn("smoke", summary["blockers"][0].lower())

    def test_summary_format_text(self):
        from slim_init import format_summary
        summary = {
            "ready": True,
            "last_session": 98,
            "top_pick": "MT-22",
            "smoke_status": "10/10 PASS",
            "blockers": [],
        }
        text = format_summary(summary)
        self.assertIn("READY", text)
        self.assertIn("MT-22", text)
        self.assertIn("10/10", text)


class TestRunTimeline(unittest.TestCase):
    """Test session timeline integration."""

    @patch("slim_init.subprocess.run")
    def test_timeline_returns_recent_sessions(self, mock_run):
        from slim_init import run_timeline
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Last 5 sessions:\n  S101: B+ | 183 tests | 11 commits | 3 wins\n  S98: A- | 55 tests | 8 commits | 4 wins",
            stderr=""
        )
        result = run_timeline()
        self.assertIn("raw", result)
        self.assertIn("S101", result["raw"])

    @patch("slim_init.subprocess.run")
    def test_timeline_parses_session_count(self, mock_run):
        from slim_init import run_timeline
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Last 5 sessions:\n  S101: B+ | 183 tests\n  S98: A- | 55 tests\n  S97: B | 60 tests",
            stderr=""
        )
        result = run_timeline()
        self.assertEqual(result["session_count"], 3)

    @patch("slim_init.subprocess.run")
    def test_timeline_handles_no_data(self, mock_run):
        from slim_init import run_timeline
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="No session data found.",
            stderr=""
        )
        result = run_timeline()
        self.assertEqual(result["session_count"], 0)

    @patch("slim_init.subprocess.run")
    def test_timeline_handles_error(self, mock_run):
        from slim_init import run_timeline
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="ModuleNotFoundError: No module named 'session_id'"
        )
        result = run_timeline()
        self.assertIn("error", result)

    @patch("slim_init.subprocess.run")
    def test_timeline_timeout(self, mock_run):
        from slim_init import run_timeline
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired("python3", 15)
        result = run_timeline()
        self.assertIn("error", result)
        self.assertIn("timeout", result["error"].lower())


class TestSummaryIncludesTimeline(unittest.TestCase):
    """Test that timeline data flows into the summary."""

    def test_format_summary_includes_timeline(self):
        from slim_init import format_summary
        summary = {
            "ready": True,
            "last_session": 101,
            "last_session_id": "S101",
            "top_pick": "MT-12",
            "smoke_status": "10/10 PASS",
            "blockers": [],
            "timeline_raw": "Last 5 sessions:\n  S101: B+ | 183 tests | 11 commits | 3 wins\n  S98: A- | 55 tests",
        }
        text = format_summary(summary)
        self.assertIn("Recent sessions", text)
        self.assertIn("S101", text)

    def test_format_summary_omits_empty_timeline(self):
        from slim_init import format_summary
        summary = {
            "ready": True,
            "last_session": 101,
            "last_session_id": "S101",
            "top_pick": "MT-12",
            "smoke_status": "10/10 PASS",
            "blockers": [],
        }
        text = format_summary(summary)
        self.assertNotIn("Recent sessions", text)


class TestSlimInitFull(unittest.TestCase):
    """Integration test for the full slim_init flow."""

    @patch("slim_init.run_timeline")
    @patch("slim_init.run_priority")
    @patch("slim_init.run_smoke")
    @patch("slim_init.Path.read_text")
    def test_full_init_happy_path(self, mock_read, mock_smoke, mock_priority, mock_timeline):
        from slim_init import run_slim_init

        mock_read.return_value = "## Current State (as of Session 98 — 2026-03-22)\n\nTests: ~109 suites, ~4373 total passing."
        mock_smoke.return_value = {"passed": True, "suites_passed": 10, "suites_total": 10}
        mock_priority.return_value = {"top_pick": "MT-22 (Autonomous loop)", "raw": "full output"}
        mock_timeline.return_value = {"raw": "Last 5 sessions:\n  S98: A-", "session_count": 1}

        result = run_slim_init()
        self.assertTrue(result["ready"])
        self.assertEqual(result["last_session"], 98)
        self.assertIn("timeline_raw", result)

    @patch("slim_init.run_timeline")
    @patch("slim_init.run_priority")
    @patch("slim_init.run_smoke")
    @patch("slim_init.Path.read_text")
    def test_full_init_smoke_failure_blocks(self, mock_read, mock_smoke, mock_priority, mock_timeline):
        from slim_init import run_slim_init

        mock_read.return_value = "## Current State (as of Session 98 — 2026-03-22)"
        mock_smoke.return_value = {"passed": False, "suites_passed": 7, "suites_total": 10, "error": "3 suites failed"}
        mock_priority.return_value = {"top_pick": "MT-22", "raw": "..."}
        mock_timeline.return_value = {"raw": "", "session_count": 0}

        result = run_slim_init()
        self.assertFalse(result["ready"])

    @patch("slim_init.run_timeline")
    @patch("slim_init.run_priority")
    @patch("slim_init.run_smoke")
    @patch("slim_init.Path.exists")
    def test_full_init_missing_session_state(self, mock_exists, mock_smoke, mock_priority, mock_timeline):
        from slim_init import run_slim_init

        mock_exists.return_value = False
        mock_smoke.return_value = {"passed": True, "suites_passed": 10, "suites_total": 10}
        mock_priority.return_value = {"top_pick": "MT-22", "raw": "..."}
        mock_timeline.return_value = {"raw": "", "session_count": 0}

        result = run_slim_init()
        # Should still work but note missing state
        self.assertIsNone(result.get("last_session"))


class TestRunPrincipleSeeder(unittest.TestCase):
    """Test principle seeder integration in slim init."""

    @patch("slim_init.subprocess.run")
    def test_seeder_returns_count(self, mock_run):
        from slim_init import run_principle_seeder
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Seeded 0 principles total\n  From LEARNINGS.md: 0\n  From journal: 0",
            stderr=""
        )
        result = run_principle_seeder()
        self.assertEqual(result["seeded"], 0)
        self.assertFalse(result.get("error"))

    @patch("slim_init.subprocess.run")
    def test_seeder_reports_new_seeds(self, mock_run):
        from slim_init import run_principle_seeder
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Seeded 5 principles total\n  From LEARNINGS.md: 3\n  From journal: 2",
            stderr=""
        )
        result = run_principle_seeder()
        self.assertEqual(result["seeded"], 5)

    @patch("slim_init.subprocess.run")
    def test_seeder_handles_failure(self, mock_run):
        from slim_init import run_principle_seeder
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="ImportError: no module"
        )
        result = run_principle_seeder()
        self.assertIn("error", result)
        self.assertEqual(result["seeded"], 0)

    @patch("slim_init.subprocess.run")
    def test_seeder_handles_timeout(self, mock_run):
        from slim_init import run_principle_seeder
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired("python3", 30)
        result = run_principle_seeder()
        self.assertIn("error", result)
        self.assertEqual(result["seeded"], 0)


class TestSummaryIncludesSeeder(unittest.TestCase):
    """Test that seeder results flow into the summary and format."""

    def test_format_summary_shows_seeder_count(self):
        from slim_init import format_summary
        summary = {
            "ready": True,
            "last_session": 141,
            "last_session_id": "S141",
            "top_pick": "MT-22",
            "smoke_status": "10/10 PASS",
            "blockers": [],
            "principles_seeded": 5,
        }
        text = format_summary(summary)
        self.assertIn("Principles", text)
        self.assertIn("5", text)

    def test_format_summary_omits_seeder_when_zero(self):
        from slim_init import format_summary
        summary = {
            "ready": True,
            "last_session": 141,
            "last_session_id": "S141",
            "top_pick": "MT-22",
            "smoke_status": "10/10 PASS",
            "blockers": [],
            "principles_seeded": 0,
        }
        text = format_summary(summary)
        self.assertNotIn("Principles", text)


class TestSlimInitIncludesSeeder(unittest.TestCase):
    """Test seeder is wired into the full slim init flow."""

    @patch("slim_init.run_principle_seeder")
    @patch("slim_init.run_timeline")
    @patch("slim_init.run_priority")
    @patch("slim_init.run_smoke")
    @patch("slim_init.Path.read_text")
    def test_full_init_calls_seeder(self, mock_read, mock_smoke, mock_priority, mock_timeline, mock_seeder):
        from slim_init import run_slim_init

        mock_read.return_value = "## Current State (as of Session 141 — 2026-03-23)"
        mock_smoke.return_value = {"passed": True, "suites_passed": 10, "suites_total": 10}
        mock_priority.return_value = {"top_pick": "MT-22", "raw": "output"}
        mock_timeline.return_value = {"raw": "", "session_count": 0}
        mock_seeder.return_value = {"seeded": 3, "raw": "Seeded 3 principles total"}

        result = run_slim_init()
        mock_seeder.assert_called_once()
        self.assertEqual(result.get("principles_seeded"), 3)


if __name__ == "__main__":
    unittest.main()
