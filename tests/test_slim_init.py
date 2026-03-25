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


class TestRunMtProposals(unittest.TestCase):
    """Test MT-41 proposal surfacing in slim init."""

    @patch("slim_init.subprocess.run")
    def test_proposals_returned(self, mock_run):
        from slim_init import run_mt_proposals
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='Parsed 387 findings (24 BUILD)\n\nMT PROPOSALS (1 above score 30.0):\n\n  [90.0] "Claude Code can now /dream"',
            stderr=""
        )
        result = run_mt_proposals()
        self.assertEqual(result["count"], 1)
        self.assertIn("MT PROPOSALS", result["raw"])

    @patch("slim_init.subprocess.run")
    def test_no_proposals_above_threshold(self, mock_run):
        from slim_init import run_mt_proposals
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Parsed 50 findings (2 BUILD)\n\nNo proposals above score threshold.",
            stderr=""
        )
        result = run_mt_proposals()
        self.assertEqual(result["count"], 0)

    @patch("slim_init.subprocess.run")
    def test_proposals_empty_output(self, mock_run):
        from slim_init import run_mt_proposals
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="",
            stderr=""
        )
        result = run_mt_proposals()
        self.assertEqual(result.get("count", 0), 0)
        self.assertEqual(result["raw"], "")

    @patch("slim_init.subprocess.run")
    def test_proposals_failure(self, mock_run):
        from slim_init import run_mt_proposals
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="FileNotFoundError"
        )
        result = run_mt_proposals()
        self.assertEqual(result["raw"], "")

    @patch("slim_init.subprocess.run")
    def test_proposals_timeout(self, mock_run):
        from slim_init import run_mt_proposals
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired("python3", 30)
        result = run_mt_proposals()
        self.assertIn("error", result)
        self.assertEqual(result["count"], 0)

    @patch("slim_init.subprocess.run")
    def test_multiple_proposals(self, mock_run):
        from slim_init import run_mt_proposals
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='MT PROPOSALS (3 above score 30.0):\n\n  [90.0] "Dream"\n  [55.0] "Guard"\n  [32.0] "Lint"',
            stderr=""
        )
        result = run_mt_proposals()
        self.assertEqual(result["count"], 3)


class TestSummaryIncludesProposals(unittest.TestCase):
    """Test that MT proposals flow into the summary format."""

    def test_format_summary_shows_proposals(self):
        from slim_init import format_summary
        summary = {
            "ready": True,
            "last_session": 163,
            "last_session_id": "S163",
            "top_pick": "MT-32",
            "smoke_status": "10/10 PASS",
            "blockers": [],
            "mt_proposals_count": 2,
            "mt_proposals_raw": "MT PROPOSALS (2 above score 30.0):\n  [90.0] Dream\n  [55.0] Guard",
        }
        text = format_summary(summary)
        self.assertIn("MT proposals", text)
        self.assertIn("2", text)

    def test_format_summary_omits_proposals_when_zero(self):
        from slim_init import format_summary
        summary = {
            "ready": True,
            "last_session": 163,
            "last_session_id": "S163",
            "top_pick": "MT-32",
            "smoke_status": "10/10 PASS",
            "blockers": [],
        }
        text = format_summary(summary)
        self.assertNotIn("MT proposals", text)


class TestSlimInitIncludesProposals(unittest.TestCase):
    """Test MT proposals are wired into the full slim init flow."""

    @patch("slim_init.run_mt_proposals")
    @patch("slim_init.run_principle_seeder")
    @patch("slim_init.run_timeline")
    @patch("slim_init.run_priority")
    @patch("slim_init.run_smoke")
    @patch("slim_init.Path.read_text")
    def test_full_init_calls_mt_proposals(self, mock_read, mock_smoke, mock_priority, mock_timeline, mock_seeder, mock_proposals):
        from slim_init import run_slim_init

        mock_read.return_value = "## Current State (as of Session 163 — 2026-03-25)"
        mock_smoke.return_value = {"passed": True, "suites_passed": 10, "suites_total": 10}
        mock_priority.return_value = {"top_pick": "MT-32", "raw": "output"}
        mock_timeline.return_value = {"raw": "", "session_count": 0}
        mock_seeder.return_value = {"seeded": 0, "raw": ""}
        mock_proposals.return_value = {"count": 1, "proposals": ["[90.0]"], "raw": "MT PROPOSALS (1):\n  [90.0] Dream"}

        result = run_slim_init()
        mock_proposals.assert_called_once()
        self.assertEqual(result.get("mt_proposals_count"), 1)
        self.assertIn("MT PROPOSALS", result.get("mt_proposals_raw", ""))

    @patch("slim_init.run_mt_proposals")
    @patch("slim_init.run_principle_seeder")
    @patch("slim_init.run_timeline")
    @patch("slim_init.run_priority")
    @patch("slim_init.run_smoke")
    @patch("slim_init.Path.read_text")
    def test_full_init_no_proposals_omits_key(self, mock_read, mock_smoke, mock_priority, mock_timeline, mock_seeder, mock_proposals):
        from slim_init import run_slim_init

        mock_read.return_value = "## Current State (as of Session 163 — 2026-03-25)"
        mock_smoke.return_value = {"passed": True, "suites_passed": 10, "suites_total": 10}
        mock_priority.return_value = {"top_pick": "MT-32", "raw": "output"}
        mock_timeline.return_value = {"raw": "", "session_count": 0}
        mock_seeder.return_value = {"seeded": 0, "raw": ""}
        mock_proposals.return_value = {"count": 0, "proposals": [], "raw": ""}

        result = run_slim_init()
        self.assertNotIn("mt_proposals_count", result)
        self.assertNotIn("mt_proposals_raw", result)


class TestRunMetaLearning(unittest.TestCase):
    """Test meta_learning_dashboard --brief integration in slim init."""

    @patch("slim_init.subprocess.run")
    def test_meta_learning_returns_brief(self, mock_run):
        from slim_init import run_meta_learning
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Self-Learning: HEALTHY | 122 principles (avg 0.52) | 8 sessions (stable) | Improvement success: N/A",
            stderr=""
        )
        result = run_meta_learning()
        self.assertEqual(result["status"], "HEALTHY")
        self.assertIn("122 principles", result["brief"])

    @patch("slim_init.subprocess.run")
    def test_meta_learning_parses_degraded(self, mock_run):
        from slim_init import run_meta_learning
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Self-Learning: DEGRADED | 50 principles (avg 0.31) | 3 sessions (declining) | Improvement success: 40%",
            stderr=""
        )
        result = run_meta_learning()
        self.assertEqual(result["status"], "DEGRADED")
        self.assertIn("DEGRADED", result["brief"])

    @patch("slim_init.subprocess.run")
    def test_meta_learning_handles_failure(self, mock_run):
        from slim_init import run_meta_learning
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="ImportError: no module"
        )
        result = run_meta_learning()
        self.assertIn("error", result)
        self.assertEqual(result["brief"], "")

    @patch("slim_init.subprocess.run")
    def test_meta_learning_handles_timeout(self, mock_run):
        from slim_init import run_meta_learning
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired("python3", 30)
        result = run_meta_learning()
        self.assertIn("error", result)
        self.assertEqual(result["brief"], "")

    @patch("slim_init.subprocess.run")
    def test_meta_learning_empty_output(self, mock_run):
        from slim_init import run_meta_learning
        mock_run.return_value = MagicMock(
            returncode=0, stdout="", stderr=""
        )
        result = run_meta_learning()
        self.assertEqual(result["brief"], "")


class TestSummaryIncludesMetaLearning(unittest.TestCase):
    """Test that meta learning brief flows into the summary format."""

    def test_format_summary_shows_meta_learning(self):
        from slim_init import format_summary
        summary = {
            "ready": True,
            "last_session": 170,
            "last_session_id": "S170",
            "top_pick": "MT-49",
            "smoke_status": "10/10 PASS",
            "blockers": [],
            "meta_learning_brief": "Self-Learning: HEALTHY | 122 principles (avg 0.52) | 8 sessions (stable)",
        }
        text = format_summary(summary)
        self.assertIn("Self-Learning", text)
        self.assertIn("HEALTHY", text)

    def test_format_summary_omits_meta_learning_when_empty(self):
        from slim_init import format_summary
        summary = {
            "ready": True,
            "last_session": 170,
            "last_session_id": "S170",
            "top_pick": "MT-49",
            "smoke_status": "10/10 PASS",
            "blockers": [],
        }
        text = format_summary(summary)
        self.assertNotIn("Self-Learning", text)


class TestSlimInitIncludesMetaLearning(unittest.TestCase):
    """Test meta learning is wired into the full slim init flow."""

    @patch("slim_init.run_meta_learning")
    @patch("slim_init.run_mt_extensions")
    @patch("slim_init.run_mt_proposals")
    @patch("slim_init.run_principle_seeder")
    @patch("slim_init.run_timeline")
    @patch("slim_init.run_priority")
    @patch("slim_init.run_smoke")
    @patch("slim_init.Path.read_text")
    def test_full_init_calls_meta_learning(self, mock_read, mock_smoke, mock_priority, mock_timeline, mock_seeder, mock_proposals, mock_extensions, mock_meta):
        from slim_init import run_slim_init

        mock_read.return_value = "## Current State (as of Session 169 — 2026-03-26)"
        mock_smoke.return_value = {"passed": True, "suites_passed": 10, "suites_total": 10}
        mock_priority.return_value = {"top_pick": "MT-49", "raw": "output"}
        mock_timeline.return_value = {"raw": "", "session_count": 0}
        mock_seeder.return_value = {"seeded": 0, "raw": ""}
        mock_proposals.return_value = {"count": 0, "proposals": [], "raw": ""}
        mock_extensions.return_value = {"count": 0, "extensions": [], "raw": ""}
        mock_meta.return_value = {"status": "HEALTHY", "brief": "Self-Learning: HEALTHY | 122 principles"}

        result = run_slim_init()
        mock_meta.assert_called_once()
        self.assertEqual(result.get("meta_learning_brief"), "Self-Learning: HEALTHY | 122 principles")


class TestRunMTExtensions(unittest.TestCase):
    """Test run_mt_extensions() for phase extension proposals."""

    @patch("slim_init.subprocess.run")
    def test_extensions_found(self, mock_run):
        from slim_init import run_mt_extensions
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='Parsed 387 findings (24 BUILD)\nPHASE EXTENSIONS (2 proposals for existing MTs):\n\n  [72.0] MT-10 (YoYo): Self-evolution\n  [59.0] MT-1 (Grid): Claude Control',
            stderr=""
        )
        result = run_mt_extensions()
        self.assertEqual(result["count"], 2)
        self.assertIn("PHASE EXTENSIONS", result["raw"])

    @patch("slim_init.subprocess.run")
    def test_no_extensions(self, mock_run):
        from slim_init import run_mt_extensions
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Parsed 50 findings (2 BUILD)\nNo phase extensions found.",
            stderr=""
        )
        result = run_mt_extensions()
        self.assertEqual(result["count"], 0)

    @patch("slim_init.subprocess.run")
    def test_extensions_empty_output(self, mock_run):
        from slim_init import run_mt_extensions
        mock_run.return_value = MagicMock(
            returncode=0, stdout="", stderr=""
        )
        result = run_mt_extensions()
        self.assertEqual(result.get("count", 0), 0)

    @patch("slim_init.subprocess.run")
    def test_extensions_timeout(self, mock_run):
        from slim_init import run_mt_extensions
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired("python3", 30)
        result = run_mt_extensions()
        self.assertIn("error", result)
        self.assertEqual(result["count"], 0)

    @patch("slim_init.subprocess.run")
    def test_extensions_failure(self, mock_run):
        from slim_init import run_mt_extensions
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="Error"
        )
        result = run_mt_extensions()
        self.assertEqual(result["raw"], "")


class TestSlimInitIncludesExtensions(unittest.TestCase):
    """Test MT extensions are wired into the full slim init flow."""

    @patch("slim_init.run_mt_extensions")
    @patch("slim_init.run_mt_proposals")
    @patch("slim_init.run_principle_seeder")
    @patch("slim_init.run_timeline")
    @patch("slim_init.run_priority")
    @patch("slim_init.run_smoke")
    @patch("slim_init.Path.read_text")
    def test_full_init_includes_extensions(self, mock_read, mock_smoke, mock_priority, mock_timeline, mock_seeder, mock_proposals, mock_extensions):
        from slim_init import run_slim_init

        mock_read.return_value = "## Current State (as of Session 165 — 2026-03-25)"
        mock_smoke.return_value = {"passed": True, "suites_passed": 10, "suites_total": 10}
        mock_priority.return_value = {"top_pick": "MT-32", "raw": "output"}
        mock_timeline.return_value = {"raw": "", "session_count": 0}
        mock_seeder.return_value = {"seeded": 0, "raw": ""}
        mock_proposals.return_value = {"count": 0, "proposals": [], "raw": ""}
        mock_extensions.return_value = {"count": 2, "extensions": ["[72.0]", "[59.0]"], "raw": "PHASE EXTENSIONS (2):\n  [72.0] MT-10\n  [59.0] MT-1"}

        result = run_slim_init()
        mock_extensions.assert_called_once()
        self.assertEqual(result.get("mt_extensions_count"), 2)
        self.assertIn("PHASE EXTENSIONS", result.get("mt_extensions_raw", ""))

    @patch("slim_init.run_mt_extensions")
    @patch("slim_init.run_mt_proposals")
    @patch("slim_init.run_principle_seeder")
    @patch("slim_init.run_timeline")
    @patch("slim_init.run_priority")
    @patch("slim_init.run_smoke")
    @patch("slim_init.Path.read_text")
    def test_full_init_no_extensions_omits_key(self, mock_read, mock_smoke, mock_priority, mock_timeline, mock_seeder, mock_proposals, mock_extensions):
        from slim_init import run_slim_init

        mock_read.return_value = "## Current State (as of Session 165 — 2026-03-25)"
        mock_smoke.return_value = {"passed": True, "suites_passed": 10, "suites_total": 10}
        mock_priority.return_value = {"top_pick": "MT-32", "raw": "output"}
        mock_timeline.return_value = {"raw": "", "session_count": 0}
        mock_seeder.return_value = {"seeded": 0, "raw": ""}
        mock_proposals.return_value = {"count": 0, "proposals": [], "raw": ""}
        mock_extensions.return_value = {"count": 0, "extensions": [], "raw": ""}

        result = run_slim_init()
        self.assertNotIn("mt_extensions_count", result)
        self.assertNotIn("mt_extensions_raw", result)


class TestRunPrincipleDiscoverer(unittest.TestCase):
    """Test principle_discoverer --dry-run integration in slim init."""

    @patch("slim_init.subprocess.run")
    def test_discoverer_returns_count(self, mock_run):
        from slim_init import run_principle_discoverer
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Discovered: 3 patterns\nRegistered: 0 new principles\nSkipped: 0 (duplicate or low confidence)",
            stderr=""
        )
        result = run_principle_discoverer()
        self.assertEqual(result["discovered"], 3)
        self.assertFalse(result.get("error"))

    @patch("slim_init.subprocess.run")
    def test_discoverer_zero_patterns(self, mock_run):
        from slim_init import run_principle_discoverer
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Discovered: 0 patterns\nRegistered: 0 new principles\nSkipped: 0 (duplicate or low confidence)",
            stderr=""
        )
        result = run_principle_discoverer()
        self.assertEqual(result["discovered"], 0)

    @patch("slim_init.subprocess.run")
    def test_discoverer_handles_failure(self, mock_run):
        from slim_init import run_principle_discoverer
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="ImportError: no module"
        )
        result = run_principle_discoverer()
        self.assertIn("error", result)
        self.assertEqual(result["discovered"], 0)

    @patch("slim_init.subprocess.run")
    def test_discoverer_handles_timeout(self, mock_run):
        from slim_init import run_principle_discoverer
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired("python3", 30)
        result = run_principle_discoverer()
        self.assertIn("error", result)
        self.assertEqual(result["discovered"], 0)

    @patch("slim_init.subprocess.run")
    def test_discoverer_uses_dry_run(self, mock_run):
        from slim_init import run_principle_discoverer
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Discovered: 2 patterns\nRegistered: 0 new principles\nSkipped: 0",
            stderr=""
        )
        run_principle_discoverer()
        call_args = mock_run.call_args[0][0]
        self.assertIn("--dry-run", call_args)


class TestSummaryIncludesDiscoverer(unittest.TestCase):
    """Test that discoverer results flow into summary format."""

    def test_format_summary_shows_discoveries(self):
        from slim_init import format_summary
        summary = {
            "ready": True,
            "last_session": 172,
            "last_session_id": "S172",
            "top_pick": "MT-49",
            "smoke_status": "10/10 PASS",
            "blockers": [],
            "discoveries_count": 3,
        }
        text = format_summary(summary)
        self.assertIn("Discoveries", text)
        self.assertIn("3", text)

    def test_format_summary_omits_discoveries_when_zero(self):
        from slim_init import format_summary
        summary = {
            "ready": True,
            "last_session": 172,
            "last_session_id": "S172",
            "top_pick": "MT-49",
            "smoke_status": "10/10 PASS",
            "blockers": [],
        }
        text = format_summary(summary)
        self.assertNotIn("Discoveries", text)


class TestRunRecalibration(unittest.TestCase):
    """Test confidence recalibration integration in slim init."""

    @patch("slim_init.subprocess.run")
    def test_recalibration_returns_decayed_count(self, mock_run):
        from slim_init import run_recalibration
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Recalibration: 50 principles (session 172)\n  Decayed: 8  Stable: 42",
            stderr=""
        )
        result = run_recalibration(current_session=172)
        self.assertEqual(result["decayed"], 8)
        self.assertEqual(result["total"], 50)

    @patch("slim_init.subprocess.run")
    def test_recalibration_zero_decayed(self, mock_run):
        from slim_init import run_recalibration
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Recalibration: 30 principles (session 172)\n  Decayed: 0  Stable: 30",
            stderr=""
        )
        result = run_recalibration(current_session=172)
        self.assertEqual(result["decayed"], 0)

    @patch("slim_init.subprocess.run")
    def test_recalibration_handles_failure(self, mock_run):
        from slim_init import run_recalibration
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="Error"
        )
        result = run_recalibration()
        self.assertEqual(result["decayed"], 0)

    @patch("slim_init.subprocess.run")
    def test_recalibration_handles_timeout(self, mock_run):
        from slim_init import run_recalibration
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired("python3", 15)
        result = run_recalibration()
        self.assertIn("error", result)


class TestSummaryIncludesRecalibration(unittest.TestCase):
    """Test that recalibration results flow into summary format."""

    def test_format_summary_shows_recalibration(self):
        from slim_init import format_summary
        summary = {
            "ready": True,
            "last_session": 172,
            "last_session_id": "S172",
            "top_pick": "MT-49",
            "smoke_status": "10/10 PASS",
            "blockers": [],
            "recal_decayed": 8,
            "recal_total": 50,
        }
        text = format_summary(summary)
        self.assertIn("Recalibration", text)
        self.assertIn("8", text)

    def test_format_summary_omits_recalibration_when_zero(self):
        from slim_init import format_summary
        summary = {
            "ready": True,
            "last_session": 172,
            "last_session_id": "S172",
            "top_pick": "MT-49",
            "smoke_status": "10/10 PASS",
            "blockers": [],
        }
        text = format_summary(summary)
        self.assertNotIn("Recalibration", text)


class TestSlimInitIncludesDiscoverer(unittest.TestCase):
    """Test principle discoverer is wired into the full slim init flow."""

    @patch("slim_init.run_principle_discoverer")
    @patch("slim_init.run_meta_learning")
    @patch("slim_init.run_mt_extensions")
    @patch("slim_init.run_mt_proposals")
    @patch("slim_init.run_principle_seeder")
    @patch("slim_init.run_timeline")
    @patch("slim_init.run_priority")
    @patch("slim_init.run_smoke")
    @patch("slim_init.Path.read_text")
    def test_full_init_calls_discoverer(self, mock_read, mock_smoke, mock_priority,
                                         mock_timeline, mock_seeder, mock_proposals,
                                         mock_extensions, mock_meta, mock_discoverer):
        from slim_init import run_slim_init

        mock_read.return_value = "## Current State (as of Session 171 — 2026-03-25)"
        mock_smoke.return_value = {"passed": True, "suites_passed": 10, "suites_total": 10}
        mock_priority.return_value = {"top_pick": "MT-49", "raw": "output"}
        mock_timeline.return_value = {"raw": "", "session_count": 0}
        mock_seeder.return_value = {"seeded": 0, "raw": ""}
        mock_proposals.return_value = {"count": 0, "proposals": [], "raw": ""}
        mock_extensions.return_value = {"count": 0, "extensions": [], "raw": ""}
        mock_meta.return_value = {"status": "HEALTHY", "brief": "Self-Learning: HEALTHY"}
        mock_discoverer.return_value = {"discovered": 4, "raw": "Discovered: 4 patterns"}

        result = run_slim_init()
        mock_discoverer.assert_called_once()
        self.assertEqual(result.get("discoveries_count"), 4)

    @patch("slim_init.run_principle_discoverer")
    @patch("slim_init.run_meta_learning")
    @patch("slim_init.run_mt_extensions")
    @patch("slim_init.run_mt_proposals")
    @patch("slim_init.run_principle_seeder")
    @patch("slim_init.run_timeline")
    @patch("slim_init.run_priority")
    @patch("slim_init.run_smoke")
    @patch("slim_init.Path.read_text")
    def test_full_init_zero_discoveries_omits_key(self, mock_read, mock_smoke, mock_priority,
                                                    mock_timeline, mock_seeder, mock_proposals,
                                                    mock_extensions, mock_meta, mock_discoverer):
        from slim_init import run_slim_init

        mock_read.return_value = "## Current State (as of Session 171 — 2026-03-25)"
        mock_smoke.return_value = {"passed": True, "suites_passed": 10, "suites_total": 10}
        mock_priority.return_value = {"top_pick": "MT-49", "raw": "output"}
        mock_timeline.return_value = {"raw": "", "session_count": 0}
        mock_seeder.return_value = {"seeded": 0, "raw": ""}
        mock_proposals.return_value = {"count": 0, "proposals": [], "raw": ""}
        mock_extensions.return_value = {"count": 0, "extensions": [], "raw": ""}
        mock_meta.return_value = {"status": "HEALTHY", "brief": ""}
        mock_discoverer.return_value = {"discovered": 0, "raw": ""}

        result = run_slim_init()
        self.assertNotIn("discoveries_count", result)


class TestResearchROI(unittest.TestCase):
    """Test research ROI wiring into slim_init."""

    @patch("slim_init.subprocess.run")
    def test_run_research_roi_success(self, mock_run):
        from slim_init import run_research_roi
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"total_deliveries": 46, "resolved": 2, "by_status": {"delivered": 44, "implemented": 2}}',
            stderr="",
        )
        result = run_research_roi()
        self.assertEqual(result["total"], 46)
        self.assertEqual(result["resolved"], 2)

    @patch("slim_init.subprocess.run")
    def test_run_research_roi_zero_resolved(self, mock_run):
        from slim_init import run_research_roi
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"total_deliveries": 46, "resolved": 0, "by_status": {"delivered": 46}}',
            stderr="",
        )
        result = run_research_roi()
        self.assertEqual(result["resolved"], 0)

    @patch("slim_init.subprocess.run")
    def test_run_research_roi_timeout(self, mock_run):
        import subprocess
        from slim_init import run_research_roi
        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 15)
        result = run_research_roi()
        self.assertEqual(result["resolved"], 0)
        self.assertIn("error", result)

    @patch("slim_init.subprocess.run")
    def test_run_research_roi_failure(self, mock_run):
        from slim_init import run_research_roi
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
        result = run_research_roi()
        self.assertEqual(result["resolved"], 0)

    @patch("slim_init.run_recalibration")
    @patch("slim_init.run_principle_discoverer")
    @patch("slim_init.run_transfer_proposals")
    @patch("slim_init.run_meta_learning")
    @patch("slim_init.run_mt_extensions")
    @patch("slim_init.run_mt_proposals")
    @patch("slim_init.run_principle_seeder")
    @patch("slim_init.run_timeline")
    @patch("slim_init.run_priority")
    @patch("slim_init.run_smoke")
    @patch("slim_init.run_research_roi")
    @patch("slim_init.Path.read_text")
    def test_full_init_includes_roi(self, mock_read, mock_roi, mock_smoke, mock_priority,
                                     mock_timeline, mock_seeder, mock_proposals,
                                     mock_extensions, mock_meta, mock_transfer,
                                     mock_discoverer, mock_recal):
        from slim_init import run_slim_init
        mock_read.return_value = "## Current State (as of Session 173 — 2026-03-25)"
        mock_smoke.return_value = {"passed": True, "suites_passed": 10, "suites_total": 10}
        mock_priority.return_value = {"top_pick": "MT-49", "raw": "output"}
        mock_timeline.return_value = {"raw": "", "session_count": 0}
        mock_seeder.return_value = {"seeded": 0}
        mock_proposals.return_value = {"count": 0, "proposals": [], "raw": ""}
        mock_extensions.return_value = {"count": 0, "extensions": [], "raw": ""}
        mock_meta.return_value = {"status": "HEALTHY", "brief": ""}
        mock_transfer.return_value = {"pending": 0}
        mock_discoverer.return_value = {"discovered": 0, "raw": ""}
        mock_recal.return_value = {"decayed": 0, "total": 122}
        mock_roi.return_value = {"total": 46, "resolved": 5}

        result = run_slim_init()
        self.assertEqual(result.get("roi_resolved"), 5)
        self.assertEqual(result.get("roi_total"), 46)

    @patch("slim_init.run_recalibration")
    @patch("slim_init.run_principle_discoverer")
    @patch("slim_init.run_transfer_proposals")
    @patch("slim_init.run_meta_learning")
    @patch("slim_init.run_mt_extensions")
    @patch("slim_init.run_mt_proposals")
    @patch("slim_init.run_principle_seeder")
    @patch("slim_init.run_timeline")
    @patch("slim_init.run_priority")
    @patch("slim_init.run_smoke")
    @patch("slim_init.run_research_roi")
    @patch("slim_init.Path.read_text")
    def test_full_init_zero_roi_omits_key(self, mock_read, mock_roi, mock_smoke, mock_priority,
                                           mock_timeline, mock_seeder, mock_proposals,
                                           mock_extensions, mock_meta, mock_transfer,
                                           mock_discoverer, mock_recal):
        from slim_init import run_slim_init
        mock_read.return_value = "## Current State (as of Session 173 — 2026-03-25)"
        mock_smoke.return_value = {"passed": True, "suites_passed": 10, "suites_total": 10}
        mock_priority.return_value = {"top_pick": "MT-49", "raw": "output"}
        mock_timeline.return_value = {"raw": "", "session_count": 0}
        mock_seeder.return_value = {"seeded": 0}
        mock_proposals.return_value = {"count": 0, "proposals": [], "raw": ""}
        mock_extensions.return_value = {"count": 0, "extensions": [], "raw": ""}
        mock_meta.return_value = {"status": "HEALTHY", "brief": ""}
        mock_transfer.return_value = {"pending": 0}
        mock_discoverer.return_value = {"discovered": 0, "raw": ""}
        mock_recal.return_value = {"decayed": 0, "total": 122}
        mock_roi.return_value = {"total": 46, "resolved": 0}

        result = run_slim_init()
        self.assertNotIn("roi_resolved", result)


if __name__ == "__main__":
    unittest.main()
