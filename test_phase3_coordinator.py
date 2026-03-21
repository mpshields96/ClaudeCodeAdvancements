#!/usr/bin/env python3
"""
test_phase3_coordinator.py — Tests for phase3_coordinator.py

Phase 3 coordinator manages 2 CLI workers (cli1 + cli2) from the desktop.
Handles: worker status tracking, load-balanced task assignment, inter-worker
conflict prevention, and Phase 3 validation metrics.
"""

import json
import os
import tempfile
import unittest
from datetime import datetime, timezone


class TestWorkerRegistry(unittest.TestCase):
    """Test worker registration and status tracking."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_path = os.path.join(self.tmpdir, "phase3_state.json")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_register_two_workers(self):
        """Coordinator should track cli1 and cli2."""
        import phase3_coordinator as p3
        coord = p3.Coordinator(state_path=self.state_path)
        coord.register_worker("cli1")
        coord.register_worker("cli2")
        self.assertEqual(len(coord.workers), 2)
        self.assertIn("cli1", coord.workers)
        self.assertIn("cli2", coord.workers)

    def test_register_duplicate_worker_is_noop(self):
        """Registering same worker twice doesn't duplicate."""
        import phase3_coordinator as p3
        coord = p3.Coordinator(state_path=self.state_path)
        coord.register_worker("cli1")
        coord.register_worker("cli1")
        self.assertEqual(len(coord.workers), 1)

    def test_worker_status_defaults_to_idle(self):
        """New workers start as idle."""
        import phase3_coordinator as p3
        coord = p3.Coordinator(state_path=self.state_path)
        coord.register_worker("cli1")
        self.assertEqual(coord.get_worker_status("cli1"), "idle")

    def test_update_worker_status(self):
        """Can update worker status to busy/done/error."""
        import phase3_coordinator as p3
        coord = p3.Coordinator(state_path=self.state_path)
        coord.register_worker("cli1")
        coord.update_worker_status("cli1", "busy", task="build tests")
        status = coord.get_worker_status("cli1")
        self.assertEqual(status, "busy")

    def test_update_unregistered_worker_raises(self):
        """Updating status of unregistered worker raises ValueError."""
        import phase3_coordinator as p3
        coord = p3.Coordinator(state_path=self.state_path)
        with self.assertRaises(ValueError):
            coord.update_worker_status("cli99", "busy")

    def test_get_worker_task(self):
        """Can get the current task for a busy worker."""
        import phase3_coordinator as p3
        coord = p3.Coordinator(state_path=self.state_path)
        coord.register_worker("cli1")
        coord.update_worker_status("cli1", "busy", task="write tests for foo.py")
        self.assertEqual(coord.get_worker_task("cli1"), "write tests for foo.py")

    def test_idle_worker_has_no_task(self):
        """Idle worker returns None for task."""
        import phase3_coordinator as p3
        coord = p3.Coordinator(state_path=self.state_path)
        coord.register_worker("cli1")
        self.assertIsNone(coord.get_worker_task("cli1"))


class TestTaskAssignment(unittest.TestCase):
    """Test load-balanced task assignment across workers."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_path = os.path.join(self.tmpdir, "phase3_state.json")
        self.queue_path = os.path.join(self.tmpdir, "queue.jsonl")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_assign_to_idle_worker(self):
        """Task goes to idle worker when one is busy."""
        import phase3_coordinator as p3
        coord = p3.Coordinator(state_path=self.state_path, queue_path=self.queue_path)
        coord.register_worker("cli1")
        coord.register_worker("cli2")
        coord.update_worker_status("cli1", "busy", task="existing task")
        assigned = coord.assign_task("write test_bar.py", files=["test_bar.py"])
        self.assertEqual(assigned, "cli2")

    def test_assign_to_worker_with_fewer_tasks(self):
        """When both idle, assign to worker with fewer completed tasks."""
        import phase3_coordinator as p3
        coord = p3.Coordinator(state_path=self.state_path, queue_path=self.queue_path)
        coord.register_worker("cli1")
        coord.register_worker("cli2")
        # Simulate cli1 completed 3 tasks, cli2 completed 1
        coord.workers["cli1"]["completed_count"] = 3
        coord.workers["cli2"]["completed_count"] = 1
        assigned = coord.assign_task("next task")
        self.assertEqual(assigned, "cli2")

    def test_assign_when_both_busy_returns_none(self):
        """When no idle worker, returns None (queue it for later)."""
        import phase3_coordinator as p3
        coord = p3.Coordinator(state_path=self.state_path, queue_path=self.queue_path)
        coord.register_worker("cli1")
        coord.register_worker("cli2")
        coord.update_worker_status("cli1", "busy", task="task A")
        coord.update_worker_status("cli2", "busy", task="task B")
        assigned = coord.assign_task("task C")
        self.assertIsNone(assigned)

    def test_assign_avoids_scope_conflict(self):
        """Task assignment avoids worker whose active scope overlaps."""
        import phase3_coordinator as p3
        coord = p3.Coordinator(state_path=self.state_path, queue_path=self.queue_path)
        coord.register_worker("cli1")
        coord.register_worker("cli2")
        # cli1 has an active scope on foo.py
        coord.workers["cli1"]["active_scope"] = ["foo.py"]
        assigned = coord.assign_task("modify foo.py", files=["foo.py"])
        # Should assign to cli2 since cli1 has scope on foo.py
        self.assertEqual(assigned, "cli2")

    def test_assign_with_single_worker(self):
        """Works with just one worker registered."""
        import phase3_coordinator as p3
        coord = p3.Coordinator(state_path=self.state_path, queue_path=self.queue_path)
        coord.register_worker("cli1")
        assigned = coord.assign_task("some task")
        self.assertEqual(assigned, "cli1")


class TestInterWorkerConflictDetection(unittest.TestCase):
    """Test conflict detection between cli1 and cli2."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_path = os.path.join(self.tmpdir, "phase3_state.json")
        self.queue_path = os.path.join(self.tmpdir, "queue.jsonl")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_no_conflict_different_files(self):
        """No conflict when workers claim different files."""
        import phase3_coordinator as p3
        coord = p3.Coordinator(state_path=self.state_path, queue_path=self.queue_path)
        coord.register_worker("cli1")
        coord.register_worker("cli2")
        coord.workers["cli1"]["active_scope"] = ["foo.py"]
        coord.workers["cli2"]["active_scope"] = ["bar.py"]
        conflicts = coord.check_inter_worker_conflicts()
        self.assertEqual(len(conflicts), 0)

    def test_conflict_same_file(self):
        """Detects conflict when both workers claim same file."""
        import phase3_coordinator as p3
        coord = p3.Coordinator(state_path=self.state_path, queue_path=self.queue_path)
        coord.register_worker("cli1")
        coord.register_worker("cli2")
        coord.workers["cli1"]["active_scope"] = ["shared.py"]
        coord.workers["cli2"]["active_scope"] = ["shared.py"]
        conflicts = coord.check_inter_worker_conflicts()
        self.assertEqual(len(conflicts), 1)
        self.assertIn("shared.py", conflicts[0]["file"])

    def test_conflict_overlapping_directories(self):
        """Detects conflict when scopes share a directory prefix."""
        import phase3_coordinator as p3
        coord = p3.Coordinator(state_path=self.state_path, queue_path=self.queue_path)
        coord.register_worker("cli1")
        coord.register_worker("cli2")
        coord.workers["cli1"]["active_scope"] = ["memory-system/"]
        coord.workers["cli2"]["active_scope"] = ["memory-system/capture.py"]
        conflicts = coord.check_inter_worker_conflicts()
        self.assertGreater(len(conflicts), 0)

    def test_no_conflict_no_scopes(self):
        """No conflict when neither worker has scopes."""
        import phase3_coordinator as p3
        coord = p3.Coordinator(state_path=self.state_path, queue_path=self.queue_path)
        coord.register_worker("cli1")
        coord.register_worker("cli2")
        conflicts = coord.check_inter_worker_conflicts()
        self.assertEqual(len(conflicts), 0)


class TestStatePersistence(unittest.TestCase):
    """Test state save/load across coordinator instances."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_path = os.path.join(self.tmpdir, "phase3_state.json")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_save_and_load_state(self):
        """State persists across coordinator instances."""
        import phase3_coordinator as p3
        coord1 = p3.Coordinator(state_path=self.state_path)
        coord1.register_worker("cli1")
        coord1.register_worker("cli2")
        coord1.update_worker_status("cli1", "busy", task="task X")
        coord1.save_state()

        coord2 = p3.Coordinator(state_path=self.state_path)
        coord2.load_state()
        self.assertEqual(len(coord2.workers), 2)
        self.assertEqual(coord2.get_worker_status("cli1"), "busy")
        self.assertEqual(coord2.get_worker_task("cli1"), "task X")

    def test_load_missing_state_is_clean(self):
        """Loading from nonexistent file gives clean state."""
        import phase3_coordinator as p3
        coord = p3.Coordinator(state_path=self.state_path)
        coord.load_state()  # File doesn't exist yet
        self.assertEqual(len(coord.workers), 0)

    def test_load_corrupted_state_is_clean(self):
        """Loading corrupted JSON gives clean state (fail safe)."""
        import phase3_coordinator as p3
        with open(self.state_path, "w") as f:
            f.write("NOT VALID JSON{{{")
        coord = p3.Coordinator(state_path=self.state_path)
        coord.load_state()
        self.assertEqual(len(coord.workers), 0)


class TestPhase3Metrics(unittest.TestCase):
    """Test Phase 3 specific metrics tracking."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_path = os.path.join(self.tmpdir, "phase3_state.json")
        self.metrics_path = os.path.join(self.tmpdir, "phase3_metrics.jsonl")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_record_session_metrics(self):
        """Can record a full session's metrics."""
        import phase3_coordinator as p3
        coord = p3.Coordinator(state_path=self.state_path)
        entry = coord.record_session_metrics(
            session_number=100,
            workers_used=["cli1", "cli2"],
            tasks_assigned=5,
            tasks_completed=5,
            inter_worker_conflicts=0,
            coordination_overhead_pct=12.0,
            path=self.metrics_path,
        )
        self.assertEqual(entry["session"], 100)
        self.assertEqual(entry["verdict"], "PASS")
        self.assertEqual(entry["workers_used"], ["cli1", "cli2"])

    def test_session_with_conflicts_is_warning(self):
        """Session with inter-worker conflicts gets PASS_WITH_WARNINGS."""
        import phase3_coordinator as p3
        coord = p3.Coordinator(state_path=self.state_path)
        entry = coord.record_session_metrics(
            session_number=101,
            workers_used=["cli1", "cli2"],
            tasks_assigned=5,
            tasks_completed=5,
            inter_worker_conflicts=1,
            coordination_overhead_pct=15.0,
            path=self.metrics_path,
        )
        self.assertEqual(entry["verdict"], "PASS_WITH_WARNINGS")

    def test_session_incomplete_tasks_is_fail(self):
        """Session where tasks weren't completed is FAIL."""
        import phase3_coordinator as p3
        coord = p3.Coordinator(state_path=self.state_path)
        entry = coord.record_session_metrics(
            session_number=102,
            workers_used=["cli1", "cli2"],
            tasks_assigned=5,
            tasks_completed=3,
            inter_worker_conflicts=0,
            coordination_overhead_pct=10.0,
            path=self.metrics_path,
        )
        self.assertEqual(entry["verdict"], "FAIL")

    def test_session_high_overhead_is_warning(self):
        """Session with >20% overhead gets PASS_WITH_WARNINGS."""
        import phase3_coordinator as p3
        coord = p3.Coordinator(state_path=self.state_path)
        entry = coord.record_session_metrics(
            session_number=103,
            workers_used=["cli1", "cli2"],
            tasks_assigned=5,
            tasks_completed=5,
            inter_worker_conflicts=0,
            coordination_overhead_pct=25.0,
            path=self.metrics_path,
        )
        self.assertEqual(entry["verdict"], "PASS_WITH_WARNINGS")

    def test_metrics_append_to_log(self):
        """Multiple sessions append to the metrics log."""
        import phase3_coordinator as p3
        coord = p3.Coordinator(state_path=self.state_path)
        coord.record_session_metrics(100, ["cli1", "cli2"], 3, 3, 0, 10.0, self.metrics_path)
        coord.record_session_metrics(101, ["cli1", "cli2"], 4, 4, 0, 8.0, self.metrics_path)
        with open(self.metrics_path) as f:
            lines = [l for l in f if l.strip()]
        self.assertEqual(len(lines), 2)


class TestPhase3Gate(unittest.TestCase):
    """Test Phase 3 gate evaluation."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_path = os.path.join(self.tmpdir, "phase3_state.json")
        self.metrics_path = os.path.join(self.tmpdir, "phase3_metrics.jsonl")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_metrics(self, entries):
        with open(self.metrics_path, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

    def test_gate_not_ready_no_sessions(self):
        """Gate not ready with no sessions."""
        import phase3_coordinator as p3
        coord = p3.Coordinator(state_path=self.state_path)
        gate = coord.check_phase3_gate(self.metrics_path)
        self.assertFalse(gate["ready"])

    def test_gate_ready_after_3_passes(self):
        """Gate ready after 3 consecutive PASS sessions."""
        self._write_metrics([
            {"session": 100, "verdict": "PASS", "workers_used": ["cli1", "cli2"]},
            {"session": 101, "verdict": "PASS", "workers_used": ["cli1", "cli2"]},
            {"session": 102, "verdict": "PASS", "workers_used": ["cli1", "cli2"]},
        ])
        import phase3_coordinator as p3
        coord = p3.Coordinator(state_path=self.state_path)
        gate = coord.check_phase3_gate(self.metrics_path)
        self.assertTrue(gate["ready"])
        self.assertEqual(gate["consecutive_passes"], 3)

    def test_gate_resets_on_fail(self):
        """FAIL resets consecutive pass count."""
        self._write_metrics([
            {"session": 100, "verdict": "PASS", "workers_used": ["cli1", "cli2"]},
            {"session": 101, "verdict": "FAIL", "workers_used": ["cli1", "cli2"]},
            {"session": 102, "verdict": "PASS", "workers_used": ["cli1", "cli2"]},
        ])
        import phase3_coordinator as p3
        coord = p3.Coordinator(state_path=self.state_path)
        gate = coord.check_phase3_gate(self.metrics_path)
        self.assertFalse(gate["ready"])
        self.assertEqual(gate["consecutive_passes"], 1)

    def test_gate_warnings_count_as_pass(self):
        """PASS_WITH_WARNINGS counts toward gate."""
        self._write_metrics([
            {"session": 100, "verdict": "PASS", "workers_used": ["cli1", "cli2"]},
            {"session": 101, "verdict": "PASS_WITH_WARNINGS", "workers_used": ["cli1", "cli2"]},
            {"session": 102, "verdict": "PASS", "workers_used": ["cli1", "cli2"]},
        ])
        import phase3_coordinator as p3
        coord = p3.Coordinator(state_path=self.state_path)
        gate = coord.check_phase3_gate(self.metrics_path)
        self.assertTrue(gate["ready"])

    def test_gate_requires_2_workers(self):
        """Gate requires sessions with 2 workers (not just 1)."""
        self._write_metrics([
            {"session": 100, "verdict": "PASS", "workers_used": ["cli1"]},
            {"session": 101, "verdict": "PASS", "workers_used": ["cli1"]},
            {"session": 102, "verdict": "PASS", "workers_used": ["cli1"]},
        ])
        import phase3_coordinator as p3
        coord = p3.Coordinator(state_path=self.state_path)
        gate = coord.check_phase3_gate(self.metrics_path)
        self.assertFalse(gate["ready"])
        self.assertEqual(gate["reason"], "need sessions with 2+ workers")


class TestFormatBriefing(unittest.TestCase):
    """Test one-line briefing output."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_path = os.path.join(self.tmpdir, "phase3_state.json")
        self.metrics_path = os.path.join(self.tmpdir, "phase3_metrics.jsonl")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_format_no_sessions(self):
        """Shows no sessions message."""
        import phase3_coordinator as p3
        coord = p3.Coordinator(state_path=self.state_path)
        brief = coord.format_briefing(self.metrics_path)
        self.assertIn("No Phase 3 sessions", brief)

    def test_format_with_sessions(self):
        """Shows session count and gate status."""
        with open(self.metrics_path, "w") as f:
            f.write(json.dumps({"session": 100, "verdict": "PASS", "workers_used": ["cli1", "cli2"]}) + "\n")
        import phase3_coordinator as p3
        coord = p3.Coordinator(state_path=self.state_path)
        brief = coord.format_briefing(self.metrics_path)
        self.assertIn("1 session", brief)

    def test_format_shows_worker_count(self):
        """Briefing mentions 2-worker status."""
        import phase3_coordinator as p3
        coord = p3.Coordinator(state_path=self.state_path)
        coord.register_worker("cli1")
        coord.register_worker("cli2")
        brief = coord.format_briefing(self.metrics_path)
        self.assertIn("2 workers", brief)


class TestWorkerSummary(unittest.TestCase):
    """Test per-worker summary output."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_path = os.path.join(self.tmpdir, "phase3_state.json")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_summary_shows_all_workers(self):
        """Summary includes status for each worker."""
        import phase3_coordinator as p3
        coord = p3.Coordinator(state_path=self.state_path)
        coord.register_worker("cli1")
        coord.register_worker("cli2")
        coord.update_worker_status("cli1", "busy", task="writing tests")
        summary = coord.worker_summary()
        self.assertIn("cli1", summary)
        self.assertIn("cli2", summary)
        self.assertIn("busy", summary)
        self.assertIn("idle", summary)

    def test_summary_empty_when_no_workers(self):
        """Summary is empty string when no workers registered."""
        import phase3_coordinator as p3
        coord = p3.Coordinator(state_path=self.state_path)
        summary = coord.worker_summary()
        self.assertEqual(summary, "No workers registered.")


if __name__ == "__main__":
    unittest.main()
