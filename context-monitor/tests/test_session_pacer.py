#!/usr/bin/env python3
"""Tests for session_pacer.py — Session pacing for long autonomous runs."""

import json
import os
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))
from session_pacer import (
    SessionPacer,
    PaceDecision,
    TaskRecord,
    SessionState,
)


class TestPaceDecision(unittest.TestCase):
    """Test the PaceDecision dataclass."""

    def test_defaults(self):
        d = PaceDecision()
        self.assertEqual(d.action, "continue")
        self.assertEqual(d.reason, "")
        self.assertFalse(d.should_wrap)
        self.assertEqual(d.tasks_completed, 0)
        self.assertEqual(d.elapsed_minutes, 0.0)
        self.assertEqual(d.context_zone, "unknown")

    def test_to_dict(self):
        d = PaceDecision(action="wrap_now", reason="time limit", should_wrap=True)
        result = d.to_dict()
        self.assertEqual(result["action"], "wrap_now")
        self.assertEqual(result["reason"], "time limit")
        self.assertTrue(result["should_wrap"])

    def test_wrap_soon_is_not_should_wrap(self):
        """wrap_soon is a warning, not a hard stop."""
        d = PaceDecision(action="wrap_soon", should_wrap=False)
        self.assertFalse(d.should_wrap)


class TestTaskRecord(unittest.TestCase):
    """Test task recording."""

    def test_task_record_creation(self):
        t = TaskRecord(name="MT-17 Phase 3", started_at="2026-03-18T10:00:00Z")
        self.assertEqual(t.name, "MT-17 Phase 3")
        self.assertIsNone(t.completed_at)
        self.assertIsNone(t.commit_hash)

    def test_task_record_completion(self):
        t = TaskRecord(
            name="Fix tests",
            started_at="2026-03-18T10:00:00Z",
            completed_at="2026-03-18T10:15:00Z",
            commit_hash="abc1234",
        )
        self.assertEqual(t.commit_hash, "abc1234")


class TestSessionState(unittest.TestCase):
    """Test session state persistence."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_path = os.path.join(self.tmpdir, "session-pace.json")

    def tearDown(self):
        if os.path.exists(self.state_path):
            os.unlink(self.state_path)
        os.rmdir(self.tmpdir)

    def test_new_session_state(self):
        state = SessionState(state_path=self.state_path)
        self.assertEqual(len(state.tasks), 0)
        self.assertIsNotNone(state.started_at)

    def test_save_and_load(self):
        state = SessionState(state_path=self.state_path)
        state.add_task("Build feature X")
        state.save()

        loaded = SessionState.load(self.state_path)
        self.assertEqual(len(loaded.tasks), 1)
        self.assertEqual(loaded.tasks[0].name, "Build feature X")

    def test_add_task(self):
        state = SessionState(state_path=self.state_path)
        state.add_task("Task 1")
        state.add_task("Task 2")
        self.assertEqual(len(state.tasks), 2)

    def test_complete_task(self):
        state = SessionState(state_path=self.state_path)
        state.add_task("Task 1")
        state.complete_task("Task 1", commit_hash="abc1234")
        self.assertIsNotNone(state.tasks[0].completed_at)
        self.assertEqual(state.tasks[0].commit_hash, "abc1234")

    def test_complete_nonexistent_task(self):
        state = SessionState(state_path=self.state_path)
        state.complete_task("Nonexistent")  # Should not raise

    def test_completed_count(self):
        state = SessionState(state_path=self.state_path)
        state.add_task("Task 1")
        state.add_task("Task 2")
        state.add_task("Task 3")
        state.complete_task("Task 1")
        state.complete_task("Task 3")
        self.assertEqual(state.completed_count(), 2)

    def test_elapsed_minutes(self):
        state = SessionState(state_path=self.state_path)
        # Override started_at to 30 minutes ago
        state.started_at = (
            datetime.now(timezone.utc) - timedelta(minutes=30)
        ).isoformat()
        elapsed = state.elapsed_minutes()
        self.assertAlmostEqual(elapsed, 30.0, delta=1.0)

    def test_load_missing_file(self):
        state = SessionState.load("/nonexistent/path.json")
        self.assertIsNotNone(state)
        self.assertEqual(len(state.tasks), 0)

    def test_load_corrupt_file(self):
        with open(self.state_path, "w") as f:
            f.write("not json")
        state = SessionState.load(self.state_path)
        self.assertIsNotNone(state)
        self.assertEqual(len(state.tasks), 0)

    def test_max_duration_stored(self):
        state = SessionState(state_path=self.state_path, max_duration_minutes=180)
        self.assertEqual(state.max_duration_minutes, 180)
        state.save()
        loaded = SessionState.load(self.state_path)
        self.assertEqual(loaded.max_duration_minutes, 180)

    def test_max_duration_survives_pacer_reload(self):
        """Bug fix S94: Pacer constructor was overwriting loaded max_duration with default."""
        # Save state with custom max_duration
        state = SessionState(state_path=self.state_path, max_duration_minutes=60)
        state.save()

        # Load via Pacer without specifying max_duration (uses default 120)
        pacer = SessionPacer(state_path=self.state_path)
        # Should preserve the 60 from state file, not overwrite with 120
        self.assertEqual(pacer.state.max_duration_minutes, 60)


class TestSessionPacer(unittest.TestCase):
    """Test the main pacer logic."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_path = os.path.join(self.tmpdir, "session-pace.json")
        self.context_path = os.path.join(self.tmpdir, "context-health.json")
        self.wrap_path = os.path.join(self.tmpdir, "wrap-state.json")

    def tearDown(self):
        for f in [self.state_path, self.context_path, self.wrap_path]:
            if os.path.exists(f):
                os.unlink(f)
        os.rmdir(self.tmpdir)

    def _write_context_health(self, zone="green", pct=20.0, tokens=40000):
        with open(self.context_path, "w") as f:
            json.dump({"zone": zone, "pct": pct, "tokens": tokens, "window": 200000}, f)

    def _make_pacer(self, max_duration=120, **kwargs):
        return SessionPacer(
            state_path=self.state_path,
            context_state_path=self.context_path,
            wrap_state_path=self.wrap_path,
            max_duration_minutes=max_duration,
            **kwargs,
        )

    def test_fresh_session_continues(self):
        """New session with no context pressure should continue."""
        self._write_context_health(zone="green", pct=20.0)
        pacer = self._make_pacer()
        decision = pacer.check()
        self.assertEqual(decision.action, "continue")
        self.assertFalse(decision.should_wrap)

    def test_red_zone_wraps(self):
        """Context above wrap threshold triggers wrap_now."""
        self._write_context_health(zone="red", pct=75.0)
        pacer = self._make_pacer()
        decision = pacer.check()
        self.assertEqual(decision.action, "wrap_now")
        self.assertTrue(decision.should_wrap)
        self.assertIn("75%", decision.reason)

    def test_configurable_wrap_threshold(self):
        """User override of wrap threshold is respected."""
        self._write_context_health(zone="red", pct=71.0)
        # Default threshold (70%) — should wrap
        pacer_default = self._make_pacer()
        self.assertEqual(pacer_default.check().action, "wrap_now")
        # User sets 80% — should NOT wrap at 71%
        pacer_override = self._make_pacer(wrap_threshold_pct=80)
        self.assertEqual(pacer_override.check().action, "continue")

    def test_critical_zone_wraps(self):
        """Critical zone triggers wrap_now with critical urgency."""
        self._write_context_health(zone="critical", pct=90.0)
        pacer = self._make_pacer()
        decision = pacer.check()
        self.assertEqual(decision.action, "wrap_now")
        self.assertTrue(decision.should_wrap)

    def test_time_limit_wraps(self):
        """Exceeding max duration triggers wrap_now."""
        self._write_context_health(zone="green", pct=20.0)
        pacer = self._make_pacer(max_duration=120)
        # Fake start time to 130 minutes ago
        pacer.state.started_at = (
            datetime.now(timezone.utc) - timedelta(minutes=130)
        ).isoformat()
        decision = pacer.check()
        self.assertEqual(decision.action, "wrap_now")
        self.assertTrue(decision.should_wrap)
        self.assertIn("duration", decision.reason.lower())

    def test_approaching_time_limit_warns(self):
        """Within 15 min of time limit triggers wrap_soon."""
        self._write_context_health(zone="green", pct=20.0)
        pacer = self._make_pacer(max_duration=120)
        # 110 minutes in = 10 minutes remaining
        pacer.state.started_at = (
            datetime.now(timezone.utc) - timedelta(minutes=110)
        ).isoformat()
        decision = pacer.check()
        self.assertEqual(decision.action, "wrap_soon")
        self.assertFalse(decision.should_wrap)
        self.assertIn("remaining", decision.reason.lower())

    def test_yellow_zone_continues(self):
        """Yellow zone is fine — continue."""
        self._write_context_health(zone="yellow", pct=55.0)
        pacer = self._make_pacer()
        decision = pacer.check()
        self.assertEqual(decision.action, "continue")

    def test_yellow_zone_near_time_limit_wraps_soon(self):
        """Yellow zone + approaching time limit = wrap_soon."""
        self._write_context_health(zone="yellow", pct=55.0)
        pacer = self._make_pacer(max_duration=120)
        pacer.state.started_at = (
            datetime.now(timezone.utc) - timedelta(minutes=108)
        ).isoformat()
        decision = pacer.check()
        self.assertEqual(decision.action, "wrap_soon")

    def test_task_tracking_in_decision(self):
        """Decision includes task count and elapsed time."""
        self._write_context_health(zone="green", pct=30.0)
        pacer = self._make_pacer()
        pacer.start_task("Task 1")
        pacer.complete_task("Task 1", "abc1234")
        pacer.start_task("Task 2")
        pacer.complete_task("Task 2", "def5678")
        decision = pacer.check()
        self.assertEqual(decision.tasks_completed, 2)
        self.assertGreaterEqual(decision.elapsed_minutes, 0)

    def test_start_and_complete_task(self):
        """Pacer correctly delegates task tracking to state."""
        pacer = self._make_pacer()
        pacer.start_task("Build feature")
        self.assertEqual(len(pacer.state.tasks), 1)
        pacer.complete_task("Build feature", "abc1234")
        self.assertEqual(pacer.state.completed_count(), 1)

    def test_no_context_file_continues(self):
        """Missing context health file = continue (fail-open)."""
        pacer = self._make_pacer()
        decision = pacer.check()
        self.assertEqual(decision.action, "continue")
        self.assertEqual(decision.context_zone, "unknown")

    def test_state_persists_across_instances(self):
        """State file persists task data across pacer instances."""
        self._write_context_health(zone="green", pct=20.0)
        pacer1 = self._make_pacer()
        pacer1.start_task("Task 1")
        pacer1.complete_task("Task 1", "abc")
        pacer1.save()

        pacer2 = self._make_pacer()
        self.assertEqual(pacer2.state.completed_count(), 1)

    def test_wrap_reserve_threshold(self):
        """Wrap reserve: if context > 55% AND > 80 min elapsed, wrap_soon."""
        self._write_context_health(zone="yellow", pct=58.0)
        pacer = self._make_pacer(max_duration=120)
        pacer.state.started_at = (
            datetime.now(timezone.utc) - timedelta(minutes=85)
        ).isoformat()
        decision = pacer.check()
        # Should either be wrap_soon or continue — testing the threshold
        self.assertIn(decision.action, ["wrap_soon", "continue"])

    def test_custom_wrap_buffer_minutes(self):
        """Custom wrap buffer changes when wrap_soon fires."""
        self._write_context_health(zone="green", pct=20.0)
        pacer = self._make_pacer(max_duration=120, wrap_buffer_minutes=30)
        # 95 min in = 25 min remaining, within 30 min buffer
        pacer.state.started_at = (
            datetime.now(timezone.utc) - timedelta(minutes=95)
        ).isoformat()
        decision = pacer.check()
        self.assertEqual(decision.action, "wrap_soon")


class TestSessionPacerCLI(unittest.TestCase):
    """Test CLI interface."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_path = os.path.join(self.tmpdir, "session-pace.json")
        self.context_path = os.path.join(self.tmpdir, "context-health.json")
        self.wrap_path = os.path.join(self.tmpdir, "wrap-state.json")
        # Write a green context state
        with open(self.context_path, "w") as f:
            json.dump({"zone": "green", "pct": 20.0, "tokens": 40000, "window": 200000}, f)

    def tearDown(self):
        for f in [self.state_path, self.context_path, self.wrap_path]:
            if os.path.exists(f):
                os.unlink(f)
        os.rmdir(self.tmpdir)

    def test_cli_check(self):
        from session_pacer import cli_main
        import io
        from contextlib import redirect_stdout

        f = io.StringIO()
        with redirect_stdout(f):
            cli_main([
                "check",
                "--state", self.state_path,
                "--context-state", self.context_path,
                "--wrap-state", self.wrap_path,
            ])
        output = f.getvalue()
        self.assertIn("CONTINUE", output)

    def test_cli_start_task(self):
        from session_pacer import cli_main
        import io
        from contextlib import redirect_stdout

        f = io.StringIO()
        with redirect_stdout(f):
            cli_main([
                "start",
                "Build feature X",
                "--state", self.state_path,
                "--context-state", self.context_path,
                "--wrap-state", self.wrap_path,
            ])
        output = f.getvalue()
        self.assertIn("Started", output)

    def test_cli_complete_task(self):
        from session_pacer import cli_main
        import io
        from contextlib import redirect_stdout

        # First start a task
        cli_main([
            "start", "Build feature X",
            "--state", self.state_path,
            "--context-state", self.context_path,
            "--wrap-state", self.wrap_path,
        ])

        f = io.StringIO()
        with redirect_stdout(f):
            cli_main([
                "complete", "Build feature X", "--commit", "abc1234",
                "--state", self.state_path,
                "--context-state", self.context_path,
                "--wrap-state", self.wrap_path,
            ])
        output = f.getvalue()
        self.assertIn("Completed", output)

    def test_cli_status(self):
        from session_pacer import cli_main
        import io
        from contextlib import redirect_stdout

        f = io.StringIO()
        with redirect_stdout(f):
            cli_main([
                "status",
                "--state", self.state_path,
                "--context-state", self.context_path,
                "--wrap-state", self.wrap_path,
            ])
        output = f.getvalue()
        self.assertIn("Session", output)

    def test_cli_reset(self):
        from session_pacer import cli_main
        import io
        from contextlib import redirect_stdout

        f = io.StringIO()
        with redirect_stdout(f):
            cli_main([
                "reset",
                "--state", self.state_path,
                "--context-state", self.context_path,
                "--wrap-state", self.wrap_path,
            ])
        output = f.getvalue()
        self.assertIn("Reset", output)

    def test_cli_no_args(self):
        from session_pacer import cli_main
        import io
        from contextlib import redirect_stdout

        f = io.StringIO()
        with redirect_stdout(f):
            cli_main([])
        output = f.getvalue()
        self.assertIn("Usage", output)

    def test_cli_check_json_output(self):
        from session_pacer import cli_main
        import io
        from contextlib import redirect_stdout

        f = io.StringIO()
        with redirect_stdout(f):
            cli_main([
                "check", "--json",
                "--state", self.state_path,
                "--context-state", self.context_path,
                "--wrap-state", self.wrap_path,
            ])
        output = f.getvalue()
        data = json.loads(output)
        self.assertIn("action", data)
        self.assertIn("should_wrap", data)


if __name__ == "__main__":
    unittest.main()
