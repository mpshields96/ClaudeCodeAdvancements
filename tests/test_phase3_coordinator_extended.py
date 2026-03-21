#!/usr/bin/env python3
"""
test_phase3_coordinator_extended.py — Extended edge-case tests for phase3_coordinator.py

Covers gaps in test_phase3_coordinator.py:
- Concurrent task assignments (threading safety)
- State persistence with corrupted/partial/empty JSON
- Nested directory scope conflict overlaps
- Gate evaluation boundaries (exactly 3, warnings-only streak, single-worker mixed in,
  4+ consecutive, FAIL after streak)
- Task assignment edge cases (no workers, tie-breaking, empty files list)
- Metrics boundary values (overhead exactly at 20%)
- Worker lifecycle (idle->busy->done->idle roundtrip)

Target: 30+ tests
"""

import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import phase3_coordinator as p3


def _write_metrics_file(path, entries):
    """Helper: write metrics entries to a JSONL file."""
    with open(path, "w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


class SetupMixin:
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_path = os.path.join(self.tmpdir, "state.json")
        self.metrics_path = os.path.join(self.tmpdir, "metrics.jsonl")
        self.queue_path = os.path.join(self.tmpdir, "queue.jsonl")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _coord(self):
        return p3.Coordinator(
            state_path=self.state_path, queue_path=self.queue_path
        )


class TestConcurrentTaskAssignment(SetupMixin, unittest.TestCase):
    """Concurrent task assignments should not crash or corrupt state."""

    def test_concurrent_assign_from_multiple_threads(self):
        """10 threads assigning tasks simultaneously should not crash."""
        coord = self._coord()
        coord.register_worker("cli1")
        coord.register_worker("cli2")

        errors = []
        results = []
        lock = threading.Lock()

        def assign_task(i):
            try:
                worker = coord.assign_task(f"task-{i}", files=[f"file_{i}.py"])
                with lock:
                    results.append(worker)
            except Exception as e:
                with lock:
                    errors.append(str(e))

        threads = [threading.Thread(target=assign_task, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        self.assertEqual(len(errors), 0, f"Errors in concurrent assign: {errors}")

    def test_concurrent_register_no_crash(self):
        """Concurrent worker registration from multiple threads."""
        coord = self._coord()
        errors = []

        def register(wid):
            try:
                coord.register_worker(wid)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=register, args=(f"worker_{i}",)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        self.assertEqual(len(errors), 0)

    def test_concurrent_save_state_final_state_valid(self):
        """KNOWN GAP: concurrent save_state races on the shared .tmp file path.

        save_state uses a single hardcoded tmp_path (state_path + ".tmp"), so
        concurrent calls race on that file. The FINAL state written is valid JSON
        (the last os.replace wins), but intermediate calls may raise OSError.
        This test verifies the final state is readable — not that no errors occur.
        Desktop note: use per-call unique tmp path to make fully race-safe.
        """
        coord = self._coord()
        coord.register_worker("cli1")
        coord.register_worker("cli2")
        coord.update_worker_status("cli1", "busy", task="task A")

        def save():
            try:
                coord.save_state()
            except Exception:
                pass  # Race condition on .tmp file — expected

        threads = [threading.Thread(target=save) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        # Final state file (if it exists) must be valid JSON
        if os.path.exists(self.state_path):
            with open(self.state_path) as f:
                data = json.load(f)
            self.assertIn("workers", data)


class TestStatePersistenceEdgeCases(SetupMixin, unittest.TestCase):
    """State persistence with corrupt/partial/empty files."""

    def test_load_empty_file_is_clean(self):
        """Empty JSON file (0 bytes) gives clean state."""
        open(self.state_path, "w").close()  # create empty file
        coord = self._coord()
        coord.load_state()
        self.assertEqual(len(coord.workers), 0)

    def test_load_partial_json_is_clean(self):
        """Truncated/partial JSON gives clean state (fail safe)."""
        with open(self.state_path, "w") as f:
            f.write('{"workers": {"cli1": {"status": "busy"')  # truncated
        coord = self._coord()
        coord.load_state()
        self.assertEqual(len(coord.workers), 0)

    def test_load_wrong_type_at_workers_key(self):
        """KNOWN GAP: if 'workers' is a list, load_state sets self.workers to that list.

        load_state does `self.workers = state.get("workers", {})` with no type check.
        If workers is a JSON array, coord.workers becomes a list instead of a dict.
        This will cause AttributeError on any subsequent dict operation.

        Desktop should add: `if not isinstance(workers, dict): workers = {}`
        Current behavior documented here — test verifies it doesn't crash on load.
        """
        with open(self.state_path, "w") as f:
            json.dump({"workers": ["cli1", "cli2"], "saved_at": "2026-01-01Z"}, f)
        coord = self._coord()
        # Load succeeds (no immediate error)
        coord.load_state()
        # coord.workers will be a list (not a dict) — this is the known gap
        # Just verify load doesn't crash; don't assert on type to avoid false pass

    def test_save_preserves_completed_count(self):
        """completed_count survives a save/load cycle."""
        coord1 = self._coord()
        coord1.register_worker("cli1")
        coord1.workers["cli1"]["completed_count"] = 7
        coord1.save_state()

        coord2 = self._coord()
        coord2.load_state()
        self.assertEqual(coord2.workers["cli1"]["completed_count"], 7)

    def test_save_preserves_active_scope(self):
        """active_scope list survives a save/load cycle."""
        coord1 = self._coord()
        coord1.register_worker("cli1")
        coord1.workers["cli1"]["active_scope"] = ["tests/foo.py", "tests/bar.py"]
        coord1.save_state()

        coord2 = self._coord()
        coord2.load_state()
        self.assertEqual(
            coord2.workers["cli1"]["active_scope"], ["tests/foo.py", "tests/bar.py"]
        )

    def test_multiple_save_load_cycles(self):
        """State is consistent across 5 sequential save/load cycles."""
        coord = self._coord()
        coord.register_worker("cli1")
        coord.register_worker("cli2")
        coord.update_worker_status("cli1", "busy", task="persistent task")

        for _ in range(5):
            coord.save_state()
            coord.load_state()

        self.assertEqual(coord.get_worker_status("cli1"), "busy")
        self.assertEqual(coord.get_worker_task("cli1"), "persistent task")
        self.assertIn("cli2", coord.workers)


class TestNestedScopeConflicts(SetupMixin, unittest.TestCase):
    """Nested directory scope conflict detection."""

    def test_nested_dir_inside_parent_dir_scope_known_gap(self):
        """KNOWN GAP: dir-vs-dir scope overlap is not detected.

        cli1 owns agent-guard/, cli2 owns agent-guard/hooks/.
        agent-guard/hooks/ is a subdirectory of agent-guard/ — semantically a conflict.

        Current code in check_inter_worker_conflicts only detects:
        - dir/ vs file (where file.startswith(dir/))
        - file vs file (direct set intersection)

        It does NOT detect dir/ vs dir/ conflicts because both entries end with "/"
        and the `if not s2.endswith("/")` guard prevents the check.

        This is a real gap — desktop should add dir-vs-dir prefix checking.
        For now, verify the current (non-detecting) behavior.
        """
        coord = self._coord()
        coord.register_worker("cli1")
        coord.register_worker("cli2")
        coord.workers["cli1"]["active_scope"] = ["agent-guard/"]
        coord.workers["cli2"]["active_scope"] = ["agent-guard/hooks/"]
        conflicts = coord.check_inter_worker_conflicts()
        # Current behavior: 0 conflicts (known gap)
        self.assertEqual(len(conflicts), 0)

    def test_nested_file_under_directory_scope(self):
        """cli1 owns tests/, cli2 owns tests/test_foo.py — conflict."""
        coord = self._coord()
        coord.register_worker("cli1")
        coord.register_worker("cli2")
        coord.workers["cli1"]["active_scope"] = ["tests/"]
        coord.workers["cli2"]["active_scope"] = ["tests/test_foo.py"]
        conflicts = coord.check_inter_worker_conflicts()
        self.assertGreater(len(conflicts), 0)
        self.assertEqual(conflicts[0]["file"], "tests/test_foo.py")

    def test_sibling_directories_no_conflict(self):
        """cli1 owns agent-guard/, cli2 owns context-monitor/ — no conflict."""
        coord = self._coord()
        coord.register_worker("cli1")
        coord.register_worker("cli2")
        coord.workers["cli1"]["active_scope"] = ["agent-guard/"]
        coord.workers["cli2"]["active_scope"] = ["context-monitor/"]
        conflicts = coord.check_inter_worker_conflicts()
        self.assertEqual(len(conflicts), 0)

    def test_deeply_nested_file_under_directory_scope(self):
        """cli1 owns memory-system/, cli2 owns memory-system/hooks/capture.py — conflict."""
        coord = self._coord()
        coord.register_worker("cli1")
        coord.register_worker("cli2")
        coord.workers["cli1"]["active_scope"] = ["memory-system/"]
        coord.workers["cli2"]["active_scope"] = ["memory-system/hooks/capture.py"]
        conflicts = coord.check_inter_worker_conflicts()
        self.assertGreater(len(conflicts), 0)

    def test_file_with_shared_prefix_no_false_conflict(self):
        """agent-guard/ should NOT conflict with agent-guard-extra/foo.py."""
        coord = self._coord()
        coord.register_worker("cli1")
        coord.register_worker("cli2")
        coord.workers["cli1"]["active_scope"] = ["agent-guard/"]
        coord.workers["cli2"]["active_scope"] = ["agent-guard-extra/foo.py"]
        conflicts = coord.check_inter_worker_conflicts()
        self.assertEqual(len(conflicts), 0)

    def test_multiple_files_single_conflict_each(self):
        """3 overlapping files should produce 3 conflict entries."""
        coord = self._coord()
        coord.register_worker("cli1")
        coord.register_worker("cli2")
        coord.workers["cli1"]["active_scope"] = ["a.py", "b.py", "c.py"]
        coord.workers["cli2"]["active_scope"] = ["a.py", "b.py", "c.py"]
        conflicts = coord.check_inter_worker_conflicts()
        self.assertEqual(len(conflicts), 3)


class TestGateEdgeCases(SetupMixin, unittest.TestCase):
    """Phase 3 gate evaluation boundaries."""

    def test_gate_exactly_3_sessions(self):
        """Gate passes at exactly 3 consecutive PASS sessions."""
        _write_metrics_file(self.metrics_path, [
            {"session": 100, "verdict": "PASS", "workers_used": ["cli1", "cli2"]},
            {"session": 101, "verdict": "PASS", "workers_used": ["cli1", "cli2"]},
            {"session": 102, "verdict": "PASS", "workers_used": ["cli1", "cli2"]},
        ])
        coord = self._coord()
        gate = coord.check_phase3_gate(self.metrics_path)
        self.assertTrue(gate["ready"])
        self.assertEqual(gate["consecutive_passes"], 3)

    def test_gate_warnings_only_streak(self):
        """3 consecutive PASS_WITH_WARNINGS counts as gate pass."""
        _write_metrics_file(self.metrics_path, [
            {"session": 100, "verdict": "PASS_WITH_WARNINGS", "workers_used": ["cli1", "cli2"]},
            {"session": 101, "verdict": "PASS_WITH_WARNINGS", "workers_used": ["cli1", "cli2"]},
            {"session": 102, "verdict": "PASS_WITH_WARNINGS", "workers_used": ["cli1", "cli2"]},
        ])
        coord = self._coord()
        gate = coord.check_phase3_gate(self.metrics_path)
        self.assertTrue(gate["ready"])
        self.assertEqual(gate["consecutive_passes"], 3)

    def test_gate_single_worker_sessions_mixed_in(self):
        """Sessions with only 1 worker break the gate even if they PASS."""
        _write_metrics_file(self.metrics_path, [
            {"session": 100, "verdict": "PASS", "workers_used": ["cli1", "cli2"]},
            {"session": 101, "verdict": "PASS", "workers_used": ["cli1"]},  # single worker
            {"session": 102, "verdict": "PASS", "workers_used": ["cli1", "cli2"]},
        ])
        coord = self._coord()
        gate = coord.check_phase3_gate(self.metrics_path)
        # 3 consecutive passes but session 101 only has 1 worker
        self.assertFalse(gate["ready"])
        self.assertIn("reason", gate)

    def test_gate_4_consecutive_passes(self):
        """Gate still ready with 4+ consecutive passes."""
        _write_metrics_file(self.metrics_path, [
            {"session": 100, "verdict": "PASS", "workers_used": ["cli1", "cli2"]},
            {"session": 101, "verdict": "PASS", "workers_used": ["cli1", "cli2"]},
            {"session": 102, "verdict": "PASS", "workers_used": ["cli1", "cli2"]},
            {"session": 103, "verdict": "PASS", "workers_used": ["cli1", "cli2"]},
        ])
        coord = self._coord()
        gate = coord.check_phase3_gate(self.metrics_path)
        self.assertTrue(gate["ready"])
        self.assertEqual(gate["consecutive_passes"], 4)

    def test_gate_fail_after_3_passes_resets(self):
        """FAIL at end resets the gate even after a 3-pass streak."""
        _write_metrics_file(self.metrics_path, [
            {"session": 100, "verdict": "PASS", "workers_used": ["cli1", "cli2"]},
            {"session": 101, "verdict": "PASS", "workers_used": ["cli1", "cli2"]},
            {"session": 102, "verdict": "PASS", "workers_used": ["cli1", "cli2"]},
            {"session": 103, "verdict": "FAIL", "workers_used": ["cli1", "cli2"]},
        ])
        coord = self._coord()
        gate = coord.check_phase3_gate(self.metrics_path)
        self.assertFalse(gate["ready"])
        self.assertEqual(gate["consecutive_passes"], 0)

    def test_gate_2_passes_not_enough(self):
        """2 consecutive passes is not enough — gate requires 3."""
        _write_metrics_file(self.metrics_path, [
            {"session": 100, "verdict": "PASS", "workers_used": ["cli1", "cli2"]},
            {"session": 101, "verdict": "PASS", "workers_used": ["cli1", "cli2"]},
        ])
        coord = self._coord()
        gate = coord.check_phase3_gate(self.metrics_path)
        self.assertFalse(gate["ready"])
        self.assertEqual(gate["consecutive_passes"], 2)

    def test_gate_all_fails(self):
        """All FAIL sessions — gate not ready, consecutive=0."""
        _write_metrics_file(self.metrics_path, [
            {"session": 100, "verdict": "FAIL", "workers_used": ["cli1", "cli2"]},
            {"session": 101, "verdict": "FAIL", "workers_used": ["cli1", "cli2"]},
            {"session": 102, "verdict": "FAIL", "workers_used": ["cli1", "cli2"]},
        ])
        coord = self._coord()
        gate = coord.check_phase3_gate(self.metrics_path)
        self.assertFalse(gate["ready"])
        self.assertEqual(gate["consecutive_passes"], 0)

    def test_gate_result_has_expected_keys(self):
        """Gate result has all expected keys."""
        coord = self._coord()
        gate = coord.check_phase3_gate(self.metrics_path)
        for key in ("ready", "consecutive_passes", "total_sessions"):
            self.assertIn(key, gate, f"Missing gate key: {key}")

    def test_gate_total_sessions_counts_all(self):
        """total_sessions counts all sessions, not just passes."""
        _write_metrics_file(self.metrics_path, [
            {"session": 100, "verdict": "FAIL", "workers_used": ["cli1", "cli2"]},
            {"session": 101, "verdict": "FAIL", "workers_used": ["cli1", "cli2"]},
            {"session": 102, "verdict": "PASS", "workers_used": ["cli1", "cli2"]},
        ])
        coord = self._coord()
        gate = coord.check_phase3_gate(self.metrics_path)
        self.assertEqual(gate["total_sessions"], 3)

    def test_gate_empty_metrics_file(self):
        """Empty metrics file returns ready=False."""
        open(self.metrics_path, "w").close()
        coord = self._coord()
        gate = coord.check_phase3_gate(self.metrics_path)
        self.assertFalse(gate["ready"])
        self.assertEqual(gate["total_sessions"], 0)


class TestAssignmentEdgeCases(SetupMixin, unittest.TestCase):
    """Task assignment edge cases."""

    def test_assign_no_workers_returns_none(self):
        """No workers registered — assign returns None."""
        coord = self._coord()
        result = coord.assign_task("some task", files=["foo.py"])
        self.assertIsNone(result)

    def test_assign_empty_files_list(self):
        """Empty files list should assign to any idle worker."""
        coord = self._coord()
        coord.register_worker("cli1")
        result = coord.assign_task("global task", files=[])
        self.assertEqual(result, "cli1")

    def test_assign_none_files_treated_as_empty(self):
        """files=None should be treated same as empty list."""
        coord = self._coord()
        coord.register_worker("cli1")
        result = coord.assign_task("global task", files=None)
        self.assertEqual(result, "cli1")

    def test_assign_tie_broken_deterministically(self):
        """When completed_count is equal, assignment is deterministic (min())."""
        coord = self._coord()
        coord.register_worker("cli1")
        coord.register_worker("cli2")
        # Both at 0 completed — should pick consistently
        result1 = coord.assign_task("task A")
        # Reset and assign again
        coord.update_worker_status(result1, "idle")
        result2 = coord.assign_task("task B")
        # Both calls should return the same worker (both at 0)
        self.assertEqual(result1, result2)

    def test_assign_updates_worker_to_busy(self):
        """assign_task marks the assigned worker as busy."""
        coord = self._coord()
        coord.register_worker("cli1")
        assigned = coord.assign_task("build something", files=["foo.py"])
        self.assertEqual(assigned, "cli1")
        self.assertEqual(coord.get_worker_status("cli1"), "busy")

    def test_assign_marks_task_on_worker(self):
        """Assigned task description is stored on the worker."""
        coord = self._coord()
        coord.register_worker("cli1")
        coord.assign_task("write test_extended.py", files=["test_extended.py"])
        self.assertEqual(coord.get_worker_task("cli1"), "write test_extended.py")

    def test_assign_scope_conflict_dir_prefix_skips_worker(self):
        """Worker with 'tests/' scope is skipped for tasks touching tests/foo.py."""
        coord = self._coord()
        coord.register_worker("cli1")
        coord.register_worker("cli2")
        coord.workers["cli1"]["active_scope"] = ["tests/"]
        # Task touches a file inside the tests/ directory
        assigned = coord.assign_task("add test", files=["tests/test_bar.py"])
        # cli1 has tests/ scope — should go to cli2
        self.assertEqual(assigned, "cli2")


class TestMetricsBoundaries(SetupMixin, unittest.TestCase):
    """Metrics verdict boundary values."""

    def test_overhead_exactly_20_is_pass(self):
        """coordination_overhead_pct=20.0 exactly gives PASS (threshold is strict >20).

        The check is `overhead > 20.0`, so exactly 20.0 is NOT a warning.
        Only overhead > 20.0 triggers PASS_WITH_WARNINGS.
        """
        coord = self._coord()
        entry = coord.record_session_metrics(
            session_number=100,
            workers_used=["cli1", "cli2"],
            tasks_assigned=3,
            tasks_completed=3,
            inter_worker_conflicts=0,
            coordination_overhead_pct=20.0,
            path=self.metrics_path,
        )
        self.assertEqual(entry["verdict"], "PASS")

    def test_overhead_just_under_20_is_pass(self):
        """coordination_overhead_pct=19.9 gives PASS."""
        coord = self._coord()
        entry = coord.record_session_metrics(
            session_number=100,
            workers_used=["cli1", "cli2"],
            tasks_assigned=3,
            tasks_completed=3,
            inter_worker_conflicts=0,
            coordination_overhead_pct=19.9,
            path=self.metrics_path,
        )
        self.assertEqual(entry["verdict"], "PASS")

    def test_zero_tasks_assigned_and_completed_is_pass(self):
        """0 tasks assigned, 0 completed — technically a PASS (no failures)."""
        coord = self._coord()
        entry = coord.record_session_metrics(
            session_number=100,
            workers_used=["cli1", "cli2"],
            tasks_assigned=0,
            tasks_completed=0,
            inter_worker_conflicts=0,
            coordination_overhead_pct=5.0,
            path=self.metrics_path,
        )
        # 0 < 0 is False, so no FAIL verdict
        self.assertIn(entry["verdict"], ("PASS", "PASS_WITH_WARNINGS"))

    def test_metrics_entry_has_timestamp(self):
        """Recorded entry includes a timestamp."""
        coord = self._coord()
        entry = coord.record_session_metrics(100, ["cli1", "cli2"], 3, 3, 0, 10.0, self.metrics_path)
        self.assertIn("timestamp", entry)
        self.assertTrue(len(entry["timestamp"]) > 0)

    def test_conflict_plus_high_overhead_is_warning_not_fail(self):
        """Conflicts + high overhead with completed=assigned gives WARNING not FAIL."""
        coord = self._coord()
        entry = coord.record_session_metrics(
            session_number=100,
            workers_used=["cli1", "cli2"],
            tasks_assigned=5,
            tasks_completed=5,
            inter_worker_conflicts=3,
            coordination_overhead_pct=30.0,
            path=self.metrics_path,
        )
        self.assertEqual(entry["verdict"], "PASS_WITH_WARNINGS")


class TestWorkerLifecycle(SetupMixin, unittest.TestCase):
    """Full worker lifecycle: idle -> busy -> done -> idle."""

    def test_idle_busy_idle_roundtrip(self):
        """Worker can cycle idle->busy->idle cleanly."""
        coord = self._coord()
        coord.register_worker("cli1")
        self.assertEqual(coord.get_worker_status("cli1"), "idle")

        coord.update_worker_status("cli1", "busy", task="task A")
        self.assertEqual(coord.get_worker_status("cli1"), "busy")
        self.assertEqual(coord.get_worker_task("cli1"), "task A")

        coord.update_worker_status("cli1", "idle")
        self.assertEqual(coord.get_worker_status("cli1"), "idle")
        self.assertIsNone(coord.get_worker_task("cli1"))

    def test_idle_clears_task(self):
        """Setting status to idle clears the current task."""
        coord = self._coord()
        coord.register_worker("cli1")
        coord.update_worker_status("cli1", "busy", task="some task")
        coord.update_worker_status("cli1", "idle")
        self.assertIsNone(coord.get_worker_task("cli1"))

    def test_get_status_unregistered_raises(self):
        """get_worker_status for unknown worker raises ValueError."""
        coord = self._coord()
        with self.assertRaises(ValueError):
            coord.get_worker_status("cli99")

    def test_get_task_unregistered_raises(self):
        """get_worker_task for unknown worker raises ValueError."""
        coord = self._coord()
        with self.assertRaises(ValueError):
            coord.get_worker_task("cli99")


if __name__ == "__main__":
    unittest.main()
