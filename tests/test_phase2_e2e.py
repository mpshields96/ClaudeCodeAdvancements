#!/usr/bin/env python3
"""
End-to-end integration tests for Phase 2 hivemind workflow.

Tests the full lifecycle: task assignment -> worker context -> scope claim ->
task completion -> done report -> session validation -> throughput measurement.

Proves all Phase 2 plumbing works together before live dual-chat sessions.

Run: python3 tests/test_phase2_e2e.py
"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cca_comm
import cca_internal_queue as ciq
import crash_recovery
import hivemind_metrics


class TestPhase2FullLifecycle(unittest.TestCase):
    """Test the complete Phase 2 hivemind workflow end-to-end."""

    def setUp(self):
        self.queue_tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.queue_tmp.close()
        self.queue_path = self.queue_tmp.name
        self._orig_queue = ciq.DEFAULT_QUEUE_PATH
        ciq.DEFAULT_QUEUE_PATH = self.queue_path

        self.metrics_tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.metrics_tmp.close()
        self.metrics_path = self.metrics_tmp.name
        self.metrics = hivemind_metrics.HivemindMetrics(path=self.metrics_path)

    def tearDown(self):
        ciq.DEFAULT_QUEUE_PATH = self._orig_queue
        os.unlink(self.queue_path)
        os.unlink(self.metrics_path)

    def test_full_lifecycle_no_crash(self):
        """Simulate a complete successful Phase 2 session."""
        # 1. Desktop assigns task to cli1
        cca_comm.cmd_task(["cli1", "Build test_foo.py with 20 tests for foo_module"])

        # Verify task is in cli1's inbox
        unread = ciq.get_unread("cli1", self.queue_path)
        self.assertEqual(len(unread), 1)
        self.assertIn("Build test_foo.py", unread[0]["subject"])

        # 2. Worker checks context (mock git commits)
        with patch("cca_comm._get_recent_commits") as mock_commits:
            mock_commits.return_value = [
                {"hash": "abc1234", "message": "S92: Build foo_module.py"},
            ]
            import io
            from contextlib import redirect_stdout
            f = io.StringIO()
            with redirect_stdout(f):
                cca_comm.cmd_context([])
            context_output = f.getvalue()
            self.assertIn("abc1234", context_output)

        # 3. Worker claims scope
        with patch.dict(os.environ, {"CCA_CHAT_ID": "cli1"}):
            cca_comm.cmd_claim(["foo_module/"])

        scopes = ciq.get_active_scopes(self.queue_path)
        self.assertGreaterEqual(len(scopes), 1)
        scope_subjects = [s["subject"] for s in scopes]
        self.assertIn("foo_module/", scope_subjects)

        # 4. Worker acknowledges task
        ciq.acknowledge_all("cli1", self.queue_path)

        # 5. Worker reports completion
        with patch.dict(os.environ, {"CCA_CHAT_ID": "cli1"}):
            cca_comm.cmd_done(["Built test_foo.py with 20 tests, all passing"])

        # 6. Worker releases scope
        with patch.dict(os.environ, {"CCA_CHAT_ID": "cli1"}):
            cca_comm.cmd_release(["foo_module/"])

        # Verify scope released
        scopes_after = ciq.get_active_scopes(self.queue_path)
        scope_subjects_after = [s["subject"] for s in scopes_after]
        self.assertNotIn("foo_module/", scope_subjects_after)

        # 7. Desktop checks inbox for completion summary
        desktop_unread = ciq.get_unread("desktop", self.queue_path)
        wrap_msgs = [m for m in desktop_unread if "WRAP:" in m.get("subject", "")]
        self.assertGreaterEqual(len(wrap_msgs), 1)

        # 8. Measure queue throughput
        stats = cca_comm.get_queue_stats(self.queue_path)
        self.assertGreater(stats["total_messages"], 0)
        self.assertIn("handoff", stats["by_category"])
        self.assertIn("scope_claim", stats["by_category"])
        self.assertIn("scope_release", stats["by_category"])

        # 9. Record metrics
        self.metrics.record_session(
            "S92_test", 1, 0, 1, 0, 0.08,
            queue_throughput=stats["total_messages"],
        )
        metrics_stats = self.metrics.get_stats()
        self.assertEqual(metrics_stats["total_sessions"], 1)
        self.assertEqual(metrics_stats["total_task_completions"], 1)
        self.assertEqual(metrics_stats["total_coordination_failures"], 0)

    def test_lifecycle_with_crash_recovery(self):
        """Simulate Phase 2 crash scenario: worker crashes, desktop recovers."""
        # 1. Desktop assigns task
        with patch.dict(os.environ, {"CCA_CHAT_ID": "desktop"}):
            cca_comm.cmd_task(["cli1", "Build bar_module.py"])

        # 2. Worker claims scope
        with patch.dict(os.environ, {"CCA_CHAT_ID": "cli1"}):
            cca_comm.cmd_claim(["bar_module/"])

        # Verify scope is active
        scopes = ciq.get_active_scopes(self.queue_path)
        self.assertTrue(any(s["subject"] == "bar_module/" for s in scopes))

        # 3. Worker "crashes" — no process running, scope still claimed
        # (In real scenario, cli1 process dies)

        # 4. Desktop detects crash via crash_recovery
        with patch.object(crash_recovery, "_get_claude_processes", return_value=[]):
            crashed = crash_recovery.detect_crashed_workers(scopes)
            self.assertEqual(len(crashed), 1)
            self.assertEqual(crashed[0]["chat_id"], "cli1")
            self.assertEqual(crashed[0]["scope"], "bar_module/")

            # 5. Desktop runs recovery
            released = crash_recovery.release_orphaned_scopes(
                crashed, queue_path=self.queue_path
            )
            self.assertEqual(len(released), 1)

        # 6. Verify scope is now released
        scopes_after = ciq.get_active_scopes(self.queue_path)
        self.assertFalse(any(s["subject"] == "bar_module/" for s in scopes_after))

        # 7. Desktop can reassign the task
        with patch.dict(os.environ, {"CCA_CHAT_ID": "desktop"}):
            cca_comm.cmd_task(["cli1", "RETRY: Build bar_module.py (recovered from crash)"])

        retry_msgs = ciq.get_unread("cli1", self.queue_path)
        # Recent messages are preserved (not cleared), so original task + RETRY both present
        retry_subjects = [m["subject"] for m in retry_msgs]
        self.assertTrue(any("RETRY" in s for s in retry_subjects))

    def test_multi_task_workflow(self):
        """Worker completes multiple tasks in sequence (Phase 2 multi-task loop)."""
        # Desktop assigns 3 tasks
        with patch.dict(os.environ, {"CCA_CHAT_ID": "desktop"}):
            # Task 1
            ciq.send_message("desktop", "cli1", "Task 1: build module_a",
                           category="handoff", priority="high", path=self.queue_path)
            # Task 2
            ciq.send_message("desktop", "cli1", "Task 2: build module_b",
                           category="handoff", priority="medium", path=self.queue_path)
            # Task 3
            ciq.send_message("desktop", "cli1", "Task 3: review module_c",
                           category="handoff", priority="low", path=self.queue_path)

        # Worker picks up all tasks
        unread = ciq.get_unread("cli1", self.queue_path)
        self.assertEqual(len(unread), 3)

        # Worker completes each task in priority order
        for i, task in enumerate(sorted(unread, key=lambda m: ["critical", "high", "medium", "low"].index(m.get("priority", "low")))):
            # Claim scope
            with patch.dict(os.environ, {"CCA_CHAT_ID": "cli1"}):
                scope = f"module_{chr(ord('a') + i)}"
                cca_comm.cmd_claim([scope])

            # Release scope
            with patch.dict(os.environ, {"CCA_CHAT_ID": "cli1"}):
                cca_comm.cmd_release([scope])

        # Worker sends single done report
        with patch.dict(os.environ, {"CCA_CHAT_ID": "cli1"}):
            cca_comm.cmd_done(["Completed 3 tasks: module_a, module_b, review module_c"])

        # Desktop gets wrap summary
        desktop_unread = ciq.get_unread("desktop", self.queue_path)
        wrap_msgs = [m for m in desktop_unread if "WRAP:" in m.get("subject", "")]
        self.assertGreaterEqual(len(wrap_msgs), 1)


class TestPhase2QueueVolume(unittest.TestCase):
    """Test queue handles Phase 2 message volume (50+ msgs/session)."""

    def setUp(self):
        self.queue_tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.queue_tmp.close()
        self.queue_path = self.queue_tmp.name
        self._orig_queue = ciq.DEFAULT_QUEUE_PATH
        ciq.DEFAULT_QUEUE_PATH = self.queue_path

    def tearDown(self):
        ciq.DEFAULT_QUEUE_PATH = self._orig_queue
        os.unlink(self.queue_path)

    def test_50_plus_messages_handled(self):
        """Queue handles 50+ messages without corruption."""
        for i in range(60):
            sender = "desktop" if i % 2 == 0 else "cli1"
            target = "cli1" if sender == "desktop" else "desktop"
            categories = ["fyi", "handoff", "scope_claim", "scope_release"]
            cat = categories[i % len(categories)]
            ciq.send_message(sender, target, f"msg_{i}",
                           category=cat, path=self.queue_path)

        stats = cca_comm.get_queue_stats(self.queue_path)
        self.assertEqual(stats["total_messages"], 60)
        self.assertGreaterEqual(stats["total_messages"], 50)

        # All messages should be readable
        all_msgs = ciq._load_queue(self.queue_path)
        self.assertEqual(len(all_msgs), 60)

        # No corruption — all have required fields
        for msg in all_msgs:
            self.assertIn("sender", msg)
            self.assertIn("target", msg)
            self.assertIn("subject", msg)
            self.assertIn("category", msg)

    def test_throughput_metric_integration(self):
        """Queue stats integrate correctly with hivemind_metrics."""
        metrics_tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        metrics_tmp.close()
        metrics = hivemind_metrics.HivemindMetrics(path=metrics_tmp.name)

        # Generate 55 messages
        for i in range(55):
            ciq.send_message("desktop", "cli1", f"msg_{i}", path=self.queue_path)

        stats = cca_comm.get_queue_stats(self.queue_path)
        metrics.record_session("S92", 1, 0, 3, 0, 0.08,
                             queue_throughput=stats["total_messages"])

        result = metrics.get_stats()
        self.assertEqual(result["max_queue_throughput"], 55)
        self.assertTrue(result["phase2_throughput_met"])

        line = metrics.format_for_init()
        self.assertIn("55", line)
        self.assertIn("MET", line)

        os.unlink(metrics_tmp.name)


class TestPhase2ContextAwareness(unittest.TestCase):
    """Test worker context awareness for Phase 2 'read desktop work' requirement."""

    def setUp(self):
        self.queue_tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.queue_tmp.close()
        self.queue_path = self.queue_tmp.name
        self._orig_queue = ciq.DEFAULT_QUEUE_PATH
        ciq.DEFAULT_QUEUE_PATH = self.queue_path

    def tearDown(self):
        ciq.DEFAULT_QUEUE_PATH = self._orig_queue
        os.unlink(self.queue_path)

    @patch("cca_comm._get_recent_commits")
    @patch("cca_comm._get_crashed_workers")
    def test_context_shows_all_sections(self, mock_crashed, mock_commits):
        """Context command should show commits, scopes, stats, and crash status."""
        mock_commits.return_value = [
            {"hash": "abc1234", "message": "S92: Build new module"},
            {"hash": "def5678", "message": "S92: Fix bug in old module"},
        ]
        mock_crashed.return_value = []

        # Add some queue activity
        ciq.send_message("desktop", "cli1", "task 1", category="handoff", path=self.queue_path)
        ciq.send_message("desktop", "cli1", "scope_x", category="scope_claim", path=self.queue_path)

        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            cca_comm.cmd_context([])
        output = f.getvalue()

        self.assertIn("RECENT COMMITS", output)
        self.assertIn("abc1234", output)
        self.assertIn("QUEUE STATS", output)
        self.assertIn("2", output)  # 2 total messages

    @patch("cca_comm._get_recent_commits")
    @patch("cca_comm._get_crashed_workers")
    def test_context_detects_crashed_worker(self, mock_crashed, mock_commits):
        """Context should show crashed workers when detected."""
        mock_commits.return_value = []
        mock_crashed.return_value = [
            {"chat_id": "cli1", "scope": "orphaned_module"}
        ]

        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            cca_comm.cmd_context([])
        output = f.getvalue()

        self.assertIn("CRASHED WORKERS", output)
        self.assertIn("cli1", output)
        self.assertIn("orphaned_module", output)


class TestPhase2HardenedWorkflows(unittest.TestCase):
    """S93: Tests for hardened Phase 2 workflows — conflict detection, stale recovery, atomic writes."""

    def setUp(self):
        self.queue_tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.queue_tmp.close()
        self.queue_path = self.queue_tmp.name
        self._orig_queue = ciq.DEFAULT_QUEUE_PATH
        ciq.DEFAULT_QUEUE_PATH = self.queue_path

    def tearDown(self):
        ciq.DEFAULT_QUEUE_PATH = self._orig_queue
        os.unlink(self.queue_path)

    @patch.dict(os.environ, {"CCA_CHAT_ID": "cli1"})
    def test_worker_blocked_from_claiming_desktop_scope(self):
        """Full E2E: desktop claims scope, worker tries same scope, gets blocked."""
        # Desktop claims agent-guard/
        with patch.dict(os.environ, {"CCA_CHAT_ID": "desktop"}):
            cca_comm.cmd_claim(["agent-guard/"])

        # cli1 tries to claim agent-guard/ — should be blocked
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            cca_comm.cmd_claim(["agent-guard/"])
        output = f.getvalue()
        self.assertIn("SCOPE CONFLICT", output)

        # cli1 claims a different scope — should succeed
        f2 = io.StringIO()
        with redirect_stdout(f2):
            cca_comm.cmd_claim(["memory-system/"])
        self.assertIn("Scope claimed", f2.getvalue())

    @patch.dict(os.environ, {"CCA_CHAT_ID": "cli1"})
    def test_worker_can_claim_after_desktop_releases(self):
        """Full E2E: desktop claims then releases, worker successfully claims."""
        with patch.dict(os.environ, {"CCA_CHAT_ID": "desktop"}):
            cca_comm.cmd_claim(["context-monitor/"])
            cca_comm.cmd_release(["context-monitor/"])

        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            cca_comm.cmd_claim(["context-monitor/"])
        self.assertIn("Scope claimed", f.getvalue())

    def test_stale_scope_recovery_in_full_pipeline(self):
        """Full E2E: worker scope goes stale, recovery pipeline cleans up, new claim succeeds."""
        from datetime import datetime, timezone, timedelta
        import json

        # Write a stale scope (45 min old) directly
        stale_time = (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat()
        stale_msg = {
            "id": "cca_stale_e2e",
            "sender": "cli1",
            "target": "desktop",
            "subject": "stale-work/",
            "body": "",
            "priority": "high",
            "category": "scope_claim",
            "status": "unread",
            "created_at": stale_time,
            "read_at": None,
        }
        with open(self.queue_path, "w") as f:
            f.write(json.dumps(stale_msg) + "\n")

        # Verify scope is active
        scopes_before = ciq.get_active_scopes(self.queue_path)
        self.assertTrue(any(s["subject"] == "stale-work/" for s in scopes_before))

        # Run recovery pipeline
        with patch.object(crash_recovery, "_get_claude_processes", return_value=[]):
            with patch.object(crash_recovery, "_get_git_status", return_value=""):
                report = crash_recovery.run_recovery(self.queue_path)

        # Verify stale scope was expired
        self.assertGreater(report.get("stale_expired", 0), 0)

        # Scope should now be released
        scopes_after = ciq.get_active_scopes(self.queue_path)
        self.assertFalse(any(s["subject"] == "stale-work/" for s in scopes_after))

        # cli2 can now claim the same scope
        with patch.dict(os.environ, {"CCA_CHAT_ID": "cli2"}):
            import io
            from contextlib import redirect_stdout
            f = io.StringIO()
            with redirect_stdout(f):
                cca_comm.cmd_claim(["stale-work/"])
            self.assertIn("Scope claimed", f.getvalue())

    def test_high_volume_queue_with_acknowledges(self):
        """Full E2E: 60+ messages with interleaved writes and acknowledges."""
        # Phase 2 requires 50+ msgs/session. Simulate realistic traffic.
        for i in range(30):
            ciq.send_message("desktop", "cli1", f"task_{i}", category="handoff",
                            priority="high", path=self.queue_path)
            ciq.send_message("cli1", "desktop", f"status_{i}", category="status_update",
                            path=self.queue_path)

        # cli1 acknowledges all its messages (triggers atomic _save_queue)
        count = ciq.acknowledge_all("cli1", self.queue_path)
        self.assertEqual(count, 30)

        # Verify total queue integrity after bulk ack
        all_msgs = ciq._load_queue(self.queue_path)
        self.assertEqual(len(all_msgs), 60)

        # All cli1-targeted msgs should be read
        cli1_msgs = [m for m in all_msgs if m["target"] == "cli1"]
        self.assertTrue(all(m["status"] == "read" for m in cli1_msgs))

        # Desktop messages still unread
        desktop_msgs = [m for m in all_msgs if m["target"] == "desktop"]
        self.assertTrue(all(m["status"] == "unread" for m in desktop_msgs))

        # Queue stats verify throughput
        stats = cca_comm.get_queue_stats(self.queue_path)
        self.assertGreaterEqual(stats["total_messages"], 50)

    def test_two_workers_non_overlapping_scopes(self):
        """Full E2E: cli1 and cli2 work on different scopes simultaneously."""
        # cli1 claims memory-system/
        with patch.dict(os.environ, {"CCA_CHAT_ID": "cli1"}):
            cca_comm.cmd_claim(["memory-system/"])

        # cli2 claims agent-guard/ (different scope — should succeed)
        with patch.dict(os.environ, {"CCA_CHAT_ID": "cli2"}):
            import io
            from contextlib import redirect_stdout
            f = io.StringIO()
            with redirect_stdout(f):
                cca_comm.cmd_claim(["agent-guard/"])
            self.assertIn("Scope claimed", f.getvalue())

        # Both scopes active
        scopes = ciq.get_active_scopes(self.queue_path)
        subjects = [s["subject"] for s in scopes]
        self.assertIn("memory-system/", subjects)
        self.assertIn("agent-guard/", subjects)

        # cli1 releases, cli2 still active
        with patch.dict(os.environ, {"CCA_CHAT_ID": "cli1"}):
            cca_comm.cmd_release(["memory-system/"])

        scopes_after = ciq.get_active_scopes(self.queue_path)
        subjects_after = [s["subject"] for s in scopes_after]
        self.assertNotIn("memory-system/", subjects_after)
        self.assertIn("agent-guard/", subjects_after)


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
