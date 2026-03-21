#!/usr/bin/env python3
"""
test_phase3_integration.py — Integration tests for Phase 3 hivemind components.

Tests that phase3_coordinator, phase3_validator, and existing queue/scope
infrastructure work together correctly for 3-chat operation.
"""

import json
import os
import tempfile
import unittest
from datetime import datetime, timezone, timedelta


def _ts(offset_sec=0):
    """ISO timestamp helper."""
    dt = datetime(2026, 3, 22, 12, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=offset_sec)
    return dt.isoformat().replace("+00:00", "Z")


def _write_queue(path, messages):
    with open(path, "w") as f:
        for m in messages:
            f.write(json.dumps(m) + "\n")


class TestCoordinatorValidatorIntegration(unittest.TestCase):
    """Test coordinator + validator work together."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_path = os.path.join(self.tmpdir, "state.json")
        self.queue_path = os.path.join(self.tmpdir, "queue.jsonl")
        self.metrics_path = os.path.join(self.tmpdir, "metrics.jsonl")
        self.sessions_path = os.path.join(self.tmpdir, "sessions.jsonl")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_full_3chat_lifecycle(self):
        """Simulate a complete 3-chat session: assign, work, validate, record."""
        import phase3_coordinator as p3c
        import phase3_validator as p3v

        # Setup coordinator
        coord = p3c.Coordinator(state_path=self.state_path, queue_path=self.queue_path)
        coord.register_worker("cli1")
        coord.register_worker("cli2")

        # Assign tasks
        w1 = coord.assign_task("write test_foo.py", files=["test_foo.py"])
        w2 = coord.assign_task("write test_bar.py", files=["test_bar.py"])
        self.assertEqual(w1, "cli1")
        self.assertEqual(w2, "cli2")

        # Simulate queue messages (as if workers did their work)
        _write_queue(self.queue_path, [
            {"sender": "desktop", "target": "cli1", "category": "handoff", "subject": "write test_foo.py", "created_at": _ts(0)},
            {"sender": "desktop", "target": "cli2", "category": "handoff", "subject": "write test_bar.py", "created_at": _ts(1)},
            {"sender": "cli1", "target": "desktop", "category": "scope_claim", "subject": "test_foo.py", "files": ["test_foo.py"], "created_at": _ts(10)},
            {"sender": "cli2", "target": "desktop", "category": "scope_claim", "subject": "test_bar.py", "files": ["test_bar.py"], "created_at": _ts(11)},
            {"sender": "cli1", "target": "desktop", "category": "scope_release", "subject": "test_foo.py", "files": ["test_foo.py"], "created_at": _ts(100)},
            {"sender": "cli2", "target": "desktop", "category": "scope_release", "subject": "test_bar.py", "files": ["test_bar.py"], "created_at": _ts(101)},
            {"sender": "cli1", "target": "desktop", "category": "handoff", "subject": "WRAP: test_foo.py done, 25 tests", "created_at": _ts(200)},
            {"sender": "cli2", "target": "desktop", "category": "handoff", "subject": "WRAP: test_bar.py done, 30 tests", "created_at": _ts(201)},
        ])

        # Validate
        result = p3v.validate_3chat_session(self.queue_path)
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["workers_validated"], 2)
        self.assertEqual(result["inter_worker_conflicts"], 0)

        # Record in both systems
        p3v.record_session(100, result, path=self.sessions_path)
        coord.record_session_metrics(
            100, ["cli1", "cli2"], 2, 2, 0, 10.0, path=self.metrics_path
        )

        # Gate check
        gate = coord.check_phase3_gate(self.metrics_path)
        self.assertFalse(gate["ready"])  # Need 3 sessions

    def test_conflict_detected_in_both_systems(self):
        """Scope conflict shows up in both coordinator and validator."""
        import phase3_coordinator as p3c
        import phase3_validator as p3v

        coord = p3c.Coordinator(state_path=self.state_path, queue_path=self.queue_path)
        coord.register_worker("cli1")
        coord.register_worker("cli2")
        coord.workers["cli1"]["active_scope"] = ["shared.py"]
        coord.workers["cli2"]["active_scope"] = ["shared.py"]

        # Coordinator detects
        coord_conflicts = coord.check_inter_worker_conflicts()
        self.assertGreater(len(coord_conflicts), 0)

        # Validator also detects from queue
        _write_queue(self.queue_path, [
            {"sender": "desktop", "target": "cli1", "category": "handoff", "subject": "task1", "created_at": _ts(0)},
            {"sender": "desktop", "target": "cli2", "category": "handoff", "subject": "task2", "created_at": _ts(1)},
            {"sender": "cli1", "target": "desktop", "category": "scope_claim", "subject": "shared.py", "files": ["shared.py"], "created_at": _ts(10)},
            {"sender": "cli2", "target": "desktop", "category": "scope_claim", "subject": "shared.py", "files": ["shared.py"], "created_at": _ts(11)},
            {"sender": "cli1", "target": "desktop", "category": "scope_release", "subject": "shared.py", "files": ["shared.py"], "created_at": _ts(100)},
            {"sender": "cli2", "target": "desktop", "category": "scope_release", "subject": "shared.py", "files": ["shared.py"], "created_at": _ts(101)},
            {"sender": "cli1", "target": "desktop", "category": "handoff", "subject": "WRAP: done", "created_at": _ts(200)},
            {"sender": "cli2", "target": "desktop", "category": "handoff", "subject": "WRAP: done", "created_at": _ts(201)},
        ])
        val_conflicts = p3v.detect_inter_worker_conflicts(self.queue_path)
        self.assertGreater(len(val_conflicts), 0)

    def test_coordinator_prevents_conflicting_assignment(self):
        """Coordinator won't assign to a worker if scope would conflict."""
        import phase3_coordinator as p3c

        coord = p3c.Coordinator(state_path=self.state_path, queue_path=self.queue_path)
        coord.register_worker("cli1")
        coord.register_worker("cli2")

        # cli1 already working on foo.py
        coord.workers["cli1"]["active_scope"] = ["foo.py"]
        coord.update_worker_status("cli1", "busy", task="working on foo")

        # New task also touches foo.py — should go to cli2
        assigned = coord.assign_task("also needs foo.py", files=["foo.py"])
        self.assertEqual(assigned, "cli2")

    def test_state_persistence_roundtrip(self):
        """Coordinator state survives save/load cycle."""
        import phase3_coordinator as p3c

        coord1 = p3c.Coordinator(state_path=self.state_path)
        coord1.register_worker("cli1")
        coord1.register_worker("cli2")
        coord1.update_worker_status("cli1", "busy", task="task A")
        coord1.workers["cli1"]["completed_count"] = 5
        coord1.save_state()

        coord2 = p3c.Coordinator(state_path=self.state_path)
        coord2.load_state()
        self.assertEqual(coord2.get_worker_status("cli1"), "busy")
        self.assertEqual(coord2.get_worker_task("cli1"), "task A")
        self.assertEqual(coord2.workers["cli1"]["completed_count"], 5)
        self.assertEqual(coord2.get_worker_status("cli2"), "idle")

    def test_gate_progression(self):
        """Gate progresses from not-ready to ready over 3 sessions."""
        import phase3_coordinator as p3c

        coord = p3c.Coordinator(state_path=self.state_path)

        for i in range(3):
            coord.record_session_metrics(
                100 + i, ["cli1", "cli2"], 3, 3, 0, 10.0, path=self.metrics_path
            )

        gate = coord.check_phase3_gate(self.metrics_path)
        self.assertTrue(gate["ready"])
        self.assertEqual(gate["consecutive_passes"], 3)

    def test_gate_resets_on_failure(self):
        """Gate resets if a session fails mid-streak."""
        import phase3_coordinator as p3c

        coord = p3c.Coordinator(state_path=self.state_path)
        coord.record_session_metrics(100, ["cli1", "cli2"], 3, 3, 0, 10.0, path=self.metrics_path)
        coord.record_session_metrics(101, ["cli1", "cli2"], 3, 2, 0, 10.0, path=self.metrics_path)  # FAIL
        coord.record_session_metrics(102, ["cli1", "cli2"], 3, 3, 0, 10.0, path=self.metrics_path)

        gate = coord.check_phase3_gate(self.metrics_path)
        self.assertFalse(gate["ready"])
        self.assertEqual(gate["consecutive_passes"], 1)


class TestLoadBalancing(unittest.TestCase):
    """Test that task assignment balances work across workers."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_path = os.path.join(self.tmpdir, "state.json")
        self.queue_path = os.path.join(self.tmpdir, "queue.jsonl")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_alternating_assignment(self):
        """Tasks alternate between workers when both idle."""
        import phase3_coordinator as p3c

        coord = p3c.Coordinator(state_path=self.state_path, queue_path=self.queue_path)
        coord.register_worker("cli1")
        coord.register_worker("cli2")

        # First task goes to one worker (both at 0 completed)
        w1 = coord.assign_task("task 1")
        self.assertIsNotNone(w1)
        # Mark complete, increment count
        coord.workers[w1]["completed_count"] += 1
        coord.update_worker_status(w1, "idle")

        # Second task should go to the other
        w2 = coord.assign_task("task 2")
        self.assertIsNotNone(w2)
        self.assertNotEqual(w1, w2)

    def test_no_assignment_when_all_busy(self):
        """Returns None when no workers available."""
        import phase3_coordinator as p3c

        coord = p3c.Coordinator(state_path=self.state_path, queue_path=self.queue_path)
        coord.register_worker("cli1")
        coord.register_worker("cli2")
        coord.update_worker_status("cli1", "busy", task="A")
        coord.update_worker_status("cli2", "busy", task="B")

        result = coord.assign_task("task C")
        self.assertIsNone(result)

    def test_scope_aware_assignment(self):
        """Respects scope claims when assigning."""
        import phase3_coordinator as p3c

        coord = p3c.Coordinator(state_path=self.state_path, queue_path=self.queue_path)
        coord.register_worker("cli1")
        coord.register_worker("cli2")
        coord.workers["cli1"]["active_scope"] = ["memory-system/"]

        # Task touches memory-system/ — should NOT go to cli1
        assigned = coord.assign_task("edit capture_hook.py", files=["memory-system/capture_hook.py"])
        self.assertEqual(assigned, "cli2")


class TestWorkerSummaryIntegration(unittest.TestCase):
    """Test worker summary reflects real queue state."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.queue_path = os.path.join(self.tmpdir, "queue.jsonl")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_activity_matches_queue(self):
        """Worker activity summary matches queue messages."""
        import phase3_validator as p3v

        _write_queue(self.queue_path, [
            {"sender": "desktop", "target": "cli1", "category": "handoff", "subject": "task1", "created_at": _ts(0)},
            {"sender": "desktop", "target": "cli2", "category": "handoff", "subject": "task2", "created_at": _ts(1)},
            {"sender": "desktop", "target": "cli2", "category": "handoff", "subject": "task3", "created_at": _ts(2)},
            {"sender": "cli1", "target": "desktop", "category": "chat", "subject": "question", "created_at": _ts(50)},
            {"sender": "cli1", "target": "desktop", "category": "handoff", "subject": "WRAP", "created_at": _ts(100)},
            {"sender": "cli2", "target": "desktop", "category": "handoff", "subject": "WRAP", "created_at": _ts(101)},
        ])

        summary = p3v.worker_activity_summary(self.queue_path)
        self.assertEqual(summary["cli1"]["tasks_received"], 1)
        self.assertEqual(summary["cli2"]["tasks_received"], 2)
        self.assertEqual(summary["cli1"]["messages_sent"], 2)  # question + WRAP
        self.assertEqual(summary["cli2"]["messages_sent"], 1)  # WRAP only
        self.assertTrue(summary["cli1"]["completed"])
        self.assertTrue(summary["cli2"]["completed"])


if __name__ == "__main__":
    unittest.main()
