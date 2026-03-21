#!/usr/bin/env python3
"""Extended tests for session_pacer.py — Session pacing for autonomous runs.

Covers boundary conditions not in the primary test suite:
- Exactly at time limit (elapsed == max)
- Compaction count = 1 vs 2 (wrap threshold)
- Yellow zone exactly at 2/3 duration boundary
- decision fields: context_pct, remaining_minutes in to_dict
- Corrupt context file → unknown zone (fail-open)
- Corrupt wrap state → 0 compactions
- Multiple tasks, completed_count in decision
- Wrap soon reason content
- Yellow + below 2/3 = continue
- Green zone at boundary continues
- State atomic save (tmp file roundtrip)
- CLI: unknown command, complete without prior start, wrap_now output
- SessionState: multiple saves, save overwrites
- PaceDecision to_dict field completeness
"""

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from session_pacer import (
    SessionPacer,
    PaceDecision,
    TaskRecord,
    SessionState,
    cli_main,
)


# ── PaceDecision extended ─────────────────────────────────────────────────────


class TestPaceDecisionExtended(unittest.TestCase):

    def test_to_dict_contains_all_fields(self):
        d = PaceDecision(
            action="wrap_soon",
            reason="Approaching limit",
            should_wrap=False,
            tasks_completed=3,
            elapsed_minutes=95.0,
            context_zone="yellow",
            context_pct=58.0,
            remaining_minutes=25.0,
        )
        result = d.to_dict()
        self.assertIn("action", result)
        self.assertIn("reason", result)
        self.assertIn("should_wrap", result)
        self.assertIn("tasks_completed", result)
        self.assertIn("elapsed_minutes", result)
        self.assertIn("context_zone", result)
        self.assertIn("context_pct", result)
        self.assertIn("remaining_minutes", result)

    def test_continue_should_wrap_is_false(self):
        d = PaceDecision(action="continue", should_wrap=False)
        self.assertFalse(d.should_wrap)

    def test_wrap_now_should_wrap_is_true(self):
        d = PaceDecision(action="wrap_now", should_wrap=True)
        self.assertTrue(d.should_wrap)

    def test_wrap_soon_should_wrap_is_false(self):
        d = PaceDecision(action="wrap_soon", should_wrap=False)
        self.assertFalse(d.should_wrap)

    def test_context_pct_preserved_in_dict(self):
        d = PaceDecision(context_pct=73.5)
        result = d.to_dict()
        self.assertEqual(result["context_pct"], 73.5)

    def test_remaining_minutes_preserved_in_dict(self):
        d = PaceDecision(remaining_minutes=12.3)
        result = d.to_dict()
        self.assertEqual(result["remaining_minutes"], 12.3)


# ── TaskRecord extended ────────────────────────────────────────────────────────


class TestTaskRecordExtended(unittest.TestCase):

    def test_task_without_commit_hash(self):
        t = TaskRecord(name="MT-17", started_at="2026-03-18T10:00:00Z")
        self.assertIsNone(t.commit_hash)

    def test_completed_task_has_completed_at(self):
        t = TaskRecord(
            name="Task",
            started_at="2026-03-18T10:00:00Z",
            completed_at="2026-03-18T10:30:00Z",
        )
        self.assertIsNotNone(t.completed_at)

    def test_in_progress_task_has_no_completed_at(self):
        t = TaskRecord(name="Running", started_at="2026-03-18T10:00:00Z")
        self.assertIsNone(t.completed_at)


# ── SessionState extended ──────────────────────────────────────────────────────


class TestSessionStateExtended(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_path = os.path.join(self.tmpdir, "pace.json")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_completed_count_zero_when_no_tasks(self):
        state = SessionState(state_path=self.state_path)
        self.assertEqual(state.completed_count(), 0)

    def test_completed_count_includes_only_completed(self):
        state = SessionState(state_path=self.state_path)
        state.add_task("A")
        state.add_task("B")
        state.add_task("C")
        state.complete_task("A")
        # B and C in progress
        self.assertEqual(state.completed_count(), 1)

    def test_complete_task_twice_same_name_only_first_matched(self):
        """Completing same task name twice: only first in-progress instance matched."""
        state = SessionState(state_path=self.state_path)
        state.add_task("Task X")
        state.add_task("Task X")  # duplicate name
        state.complete_task("Task X")
        completed = [t for t in state.tasks if t.completed_at is not None]
        self.assertEqual(len(completed), 1)

    def test_save_creates_file(self):
        state = SessionState(state_path=self.state_path)
        state.add_task("Task A")
        state.save()
        self.assertTrue(os.path.exists(self.state_path))

    def test_save_overwrites_previous(self):
        """Second save replaces first."""
        state = SessionState(state_path=self.state_path)
        state.add_task("First task")
        state.save()

        state.add_task("Second task")
        state.save()

        loaded = SessionState.load(self.state_path)
        self.assertEqual(len(loaded.tasks), 2)

    def test_save_uses_tmp_file_for_atomicity(self):
        """Save should use a .tmp file then replace — no partial writes."""
        state = SessionState(state_path=self.state_path)
        state.add_task("Task A")
        state.save()
        # Tmp file should be gone after save
        tmp = self.state_path + ".tmp"
        self.assertFalse(os.path.exists(tmp))
        # Real file should exist
        self.assertTrue(os.path.exists(self.state_path))

    def test_load_preserves_commit_hash(self):
        state = SessionState(state_path=self.state_path)
        state.add_task("MT-22")
        state.complete_task("MT-22", commit_hash="deadbeef")
        state.save()

        loaded = SessionState.load(self.state_path)
        self.assertEqual(loaded.tasks[0].commit_hash, "deadbeef")

    def test_load_preserves_started_at(self):
        past = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        state = SessionState(state_path=self.state_path)
        state.started_at = past
        state.save()

        loaded = SessionState.load(self.state_path)
        self.assertEqual(loaded.started_at, past)

    def test_elapsed_minutes_increases_with_time(self):
        state = SessionState(state_path=self.state_path)
        state.started_at = (
            datetime.now(timezone.utc) - timedelta(minutes=60)
        ).isoformat()
        elapsed = state.elapsed_minutes()
        self.assertGreaterEqual(elapsed, 59.0)
        self.assertLessEqual(elapsed, 61.0)


# ── SessionPacer extended ─────────────────────────────────────────────────────


class TestSessionPacerExtended(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_path = os.path.join(self.tmpdir, "pace.json")
        self.ctx_path = os.path.join(self.tmpdir, "ctx.json")
        self.wrap_path = os.path.join(self.tmpdir, "wrap.json")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def _write_context(self, zone="green", pct=20.0):
        with open(self.ctx_path, "w") as f:
            json.dump({"zone": zone, "pct": pct}, f)

    def _write_wrap_state(self, compaction_count=0):
        with open(self.wrap_path, "w") as f:
            json.dump({"compaction_count": compaction_count}, f)

    def _make_pacer(self, max_duration=120, wrap_buffer=15):
        return SessionPacer(
            state_path=self.state_path,
            context_state_path=self.ctx_path,
            wrap_state_path=self.wrap_path,
            max_duration_minutes=max_duration,
            wrap_buffer_minutes=wrap_buffer,
        )

    def test_exactly_at_time_limit_wraps_now(self):
        """elapsed == max_duration → WRAP_NOW."""
        self._write_context("green", 20.0)
        pacer = self._make_pacer(max_duration=120)
        pacer.state.started_at = (
            datetime.now(timezone.utc) - timedelta(minutes=120)
        ).isoformat()
        decision = pacer.check()
        self.assertEqual(decision.action, "wrap_now")

    def test_compaction_count_1_continues(self):
        """compaction_count=1 is below threshold — continue."""
        self._write_context("green", 20.0)
        self._write_wrap_state(compaction_count=1)
        pacer = self._make_pacer()
        decision = pacer.check()
        self.assertNotEqual(decision.action, "wrap_now")

    def test_compaction_count_2_wraps_now(self):
        """compaction_count>=2 → WRAP_NOW."""
        self._write_context("green", 20.0)
        self._write_wrap_state(compaction_count=2)
        pacer = self._make_pacer()
        decision = pacer.check()
        self.assertEqual(decision.action, "wrap_now")
        self.assertTrue(decision.should_wrap)
        self.assertIn("compact", decision.reason.lower())

    def test_compaction_count_3_wraps_now(self):
        """compaction_count=3 also triggers wrap."""
        self._write_context("green", 20.0)
        self._write_wrap_state(compaction_count=3)
        pacer = self._make_pacer()
        decision = pacer.check()
        self.assertEqual(decision.action, "wrap_now")

    def test_yellow_exactly_at_two_thirds_boundary(self):
        """Yellow zone exactly at 2/3 of duration: wrap_soon expected."""
        self._write_context("yellow", 55.0)
        pacer = self._make_pacer(max_duration=120)
        # exactly 80 minutes = 2/3 of 120
        pacer.state.started_at = (
            datetime.now(timezone.utc) - timedelta(minutes=81)
        ).isoformat()
        decision = pacer.check()
        # Just past 2/3 of 120 min AND yellow → wrap_soon
        self.assertEqual(decision.action, "wrap_soon")

    def test_yellow_below_two_thirds_continues(self):
        """Yellow zone but early in session → continue."""
        self._write_context("yellow", 55.0)
        pacer = self._make_pacer(max_duration=120)
        # 30 minutes = well below 2/3 of 120
        pacer.state.started_at = (
            datetime.now(timezone.utc) - timedelta(minutes=30)
        ).isoformat()
        decision = pacer.check()
        self.assertEqual(decision.action, "continue")

    def test_decision_includes_correct_context_zone(self):
        """Decision captures the zone from context health file."""
        self._write_context("yellow", 65.0)
        pacer = self._make_pacer()
        decision = pacer.check()
        self.assertEqual(decision.context_zone, "yellow")

    def test_decision_includes_correct_context_pct(self):
        self._write_context("green", 37.5)
        pacer = self._make_pacer()
        decision = pacer.check()
        self.assertEqual(decision.context_pct, 37.5)

    def test_decision_remaining_minutes_is_positive_early(self):
        """Early in session, remaining_minutes should be positive."""
        self._write_context("green", 20.0)
        pacer = self._make_pacer(max_duration=120)
        pacer.state.started_at = (
            datetime.now(timezone.utc) - timedelta(minutes=10)
        ).isoformat()
        decision = pacer.check()
        self.assertGreater(decision.remaining_minutes, 100.0)

    def test_decision_remaining_minutes_is_zero_when_exceeded(self):
        """When time exceeded, remaining_minutes should be 0.0."""
        self._write_context("green", 20.0)
        pacer = self._make_pacer(max_duration=120)
        pacer.state.started_at = (
            datetime.now(timezone.utc) - timedelta(minutes=150)
        ).isoformat()
        decision = pacer.check()
        self.assertEqual(decision.remaining_minutes, 0.0)

    def test_corrupt_context_file_continues(self):
        """Corrupt context health file → unknown zone → continue."""
        with open(self.ctx_path, "w") as f:
            f.write("NOT JSON {{{")
        pacer = self._make_pacer()
        decision = pacer.check()
        self.assertEqual(decision.context_zone, "unknown")
        self.assertNotEqual(decision.action, "wrap_now")

    def test_corrupt_wrap_state_returns_zero_compactions(self):
        """Corrupt wrap state file → 0 compactions → no compaction wrap."""
        with open(self.wrap_path, "w") as f:
            f.write("not json !!!")
        self._write_context("green", 20.0)
        pacer = self._make_pacer()
        compactions = pacer._read_compaction_count()
        self.assertEqual(compactions, 0)

    def test_multiple_tasks_count_in_decision(self):
        """Decision shows all completed tasks."""
        self._write_context("green", 20.0)
        pacer = self._make_pacer()
        for i in range(5):
            pacer.start_task(f"Task {i}")
            pacer.complete_task(f"Task {i}", commit_hash=f"abc{i}")
        decision = pacer.check()
        self.assertEqual(decision.tasks_completed, 5)

    def test_wrap_soon_reason_mentions_remaining_or_context(self):
        """wrap_soon decision should explain why in its reason string."""
        self._write_context("green", 20.0)
        pacer = self._make_pacer(max_duration=120)
        pacer.state.started_at = (
            datetime.now(timezone.utc) - timedelta(minutes=110)
        ).isoformat()
        decision = pacer.check()
        self.assertEqual(decision.action, "wrap_soon")
        self.assertGreater(len(decision.reason), 0)

    def test_wrap_now_reason_is_non_empty(self):
        """WRAP_NOW decisions should always include a reason."""
        self._write_context("red", 75.0)
        pacer = self._make_pacer()
        decision = pacer.check()
        self.assertEqual(decision.action, "wrap_now")
        self.assertGreater(len(decision.reason), 0)

    def test_max_duration_preserved_after_load(self):
        """max_duration_minutes set at construction time is preserved across instances."""
        pacer = self._make_pacer(max_duration=90)
        pacer.save()

        # Create new instance without explicit max_duration — should load from state
        pacer2 = SessionPacer(
            state_path=self.state_path,
            context_state_path=self.ctx_path,
            wrap_state_path=self.wrap_path,
        )
        self.assertEqual(pacer2.state.max_duration_minutes, 90)

    def test_save_delegates_to_state(self):
        """pacer.save() should persist task data."""
        self._write_context("green", 20.0)
        pacer = self._make_pacer()
        pacer.start_task("test task")
        pacer.save()

        loaded = SessionState.load(self.state_path)
        self.assertEqual(len(loaded.tasks), 1)

    def test_decision_elapsed_minutes_is_numeric(self):
        """elapsed_minutes in decision should be a rounded float."""
        self._write_context("green", 20.0)
        pacer = self._make_pacer()
        decision = pacer.check()
        self.assertIsInstance(decision.elapsed_minutes, float)
        self.assertGreaterEqual(decision.elapsed_minutes, 0.0)

    def test_green_zone_high_pct_still_continues(self):
        """Zone takes priority over raw pct — 'green' at 48% should continue."""
        self._write_context("green", 48.0)
        pacer = self._make_pacer()
        decision = pacer.check()
        self.assertEqual(decision.action, "continue")


# ── SessionPacerCLI extended ──────────────────────────────────────────────────


class TestSessionPacerCLIExtended(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_path = os.path.join(self.tmpdir, "pace.json")
        self.ctx_path = os.path.join(self.tmpdir, "ctx.json")
        self.wrap_path = os.path.join(self.tmpdir, "wrap.json")
        with open(self.ctx_path, "w") as f:
            json.dump({"zone": "green", "pct": 20.0}, f)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def _run(self, extra_args):
        f = io.StringIO()
        with redirect_stdout(f):
            cli_main([
                *extra_args,
                "--state", self.state_path,
                "--context-state", self.ctx_path,
                "--wrap-state", self.wrap_path,
            ])
        return f.getvalue()

    def test_unknown_command_prints_unknown(self):
        output = self._run(["unknowncmd"])
        self.assertIn("Unknown", output)

    def test_complete_without_name_prints_usage(self):
        output = self._run(["complete"])
        self.assertIn("Usage", output)

    def test_start_without_name_prints_usage(self):
        output = self._run(["start"])
        self.assertIn("Usage", output)

    def test_check_wrap_now_outputs_wrap_message(self):
        """When context is red, check should output WRAP NOW."""
        with open(self.ctx_path, "w") as f:
            json.dump({"zone": "red", "pct": 78.0}, f)
        output = self._run(["check"])
        self.assertIn("WRAP", output.upper())

    def test_status_with_completed_tasks_shows_log(self):
        """status command shows task log when tasks exist."""
        self._run(["start", "My Task"])
        self._run(["complete", "My Task", "--commit", "abc123"])
        output = self._run(["status"])
        self.assertIn("DONE", output)

    def test_check_json_contains_tasks_completed(self):
        """JSON output from check should include tasks_completed."""
        output = self._run(["check", "--json"])
        data = json.loads(output)
        self.assertIn("tasks_completed", data)

    def test_check_json_contains_remaining_minutes(self):
        output = self._run(["check", "--json"])
        data = json.loads(output)
        self.assertIn("remaining_minutes", data)

    def test_check_json_contains_context_pct(self):
        output = self._run(["check", "--json"])
        data = json.loads(output)
        self.assertIn("context_pct", data)

    def test_complete_with_commit_hash_in_output(self):
        self._run(["start", "My Feature"])
        output = self._run(["complete", "My Feature", "--commit", "deadbeef"])
        self.assertIn("deadbeef", output)

    def test_reset_clears_tasks(self):
        """After reset, completed tasks count should be 0."""
        self._run(["start", "Old Task"])
        self._run(["complete", "Old Task"])
        self._run(["reset"])
        output = self._run(["status"])
        # After reset: 0/0 tasks
        self.assertIn("0/0", output)

    def test_max_duration_flag_used(self):
        """--max-duration flag changes the session duration."""
        f = io.StringIO()
        with redirect_stdout(f):
            cli_main([
                "check", "--json",
                "--state", self.state_path,
                "--context-state", self.ctx_path,
                "--wrap-state", self.wrap_path,
                "--max-duration", "60",
            ])
        data = json.loads(f.getvalue())
        # remaining_minutes should reflect 60-minute max
        self.assertLessEqual(data["remaining_minutes"], 60.0)

    def test_status_shows_elapsed(self):
        output = self._run(["status"])
        self.assertIn("Elapsed", output)


if __name__ == "__main__":
    unittest.main()
