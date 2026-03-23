#!/usr/bin/env python3
"""Tests for session_orchestrator PID file registry."""

import json
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from session_orchestrator import (
    PidRegistry,
    SessionMode,
    SessionState,
    detect_running_sessions_from_pidfiles,
)


class TestPidRegistry(unittest.TestCase):
    """PidRegistry — register/deregister/query sessions via PID files."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.registry = PidRegistry(self.tmpdir)

    def test_register_creates_file(self):
        self.registry.register("desktop", 12345)
        path = os.path.join(self.tmpdir, "desktop.pid")
        self.assertTrue(os.path.exists(path))

    def test_register_writes_pid(self):
        self.registry.register("desktop", 12345)
        data = self.registry.read("desktop")
        self.assertEqual(data["pid"], 12345)

    def test_register_writes_role(self):
        self.registry.register("cli1", 99999)
        data = self.registry.read("cli1")
        self.assertEqual(data["role"], "cli1")

    def test_register_writes_timestamp(self):
        self.registry.register("desktop", 12345)
        data = self.registry.read("desktop")
        self.assertIn("started_at", data)

    def test_deregister_removes_file(self):
        self.registry.register("desktop", 12345)
        self.registry.deregister("desktop")
        path = os.path.join(self.tmpdir, "desktop.pid")
        self.assertFalse(os.path.exists(path))

    def test_deregister_nonexistent_ok(self):
        # Should not raise
        self.registry.deregister("desktop")

    def test_read_nonexistent_returns_none(self):
        data = self.registry.read("desktop")
        self.assertIsNone(data)

    def test_list_active_empty(self):
        active = self.registry.list_active()
        self.assertEqual(len(active), 0)

    def test_list_active_with_sessions(self):
        self.registry.register("desktop", 100)
        self.registry.register("cli1", 200)
        active = self.registry.list_active()
        self.assertEqual(len(active), 2)

    def test_list_active_after_deregister(self):
        self.registry.register("desktop", 100)
        self.registry.register("cli1", 200)
        self.registry.deregister("cli1")
        active = self.registry.list_active()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["role"], "desktop")

    def test_is_alive_with_current_pid(self):
        # Use our own PID — guaranteed to be running
        self.registry.register("desktop", os.getpid())
        self.assertTrue(self.registry.is_alive("desktop"))

    def test_is_alive_with_dead_pid_and_expired_heartbeat(self):
        # PID 99999999 is extremely unlikely to exist
        self.registry.register("desktop", 99999999)
        # Expire the heartbeat so PID fallback is used
        data = self.registry.read("desktop")
        data["last_heartbeat"] = time.time() - 9999
        with open(os.path.join(self.tmpdir, "desktop.pid"), "w") as f:
            json.dump(data, f)
        self.assertFalse(self.registry.is_alive("desktop"))

    def test_is_alive_nonexistent_role(self):
        self.assertFalse(self.registry.is_alive("desktop"))

    def test_cleanup_stale_removes_dead(self):
        self.registry.register("desktop", 99999999)
        # Expire heartbeat so it's considered stale
        data = self.registry.read("desktop")
        data["last_heartbeat"] = time.time() - 9999
        with open(os.path.join(self.tmpdir, "desktop.pid"), "w") as f:
            json.dump(data, f)
        cleaned = self.registry.cleanup_stale()
        self.assertEqual(len(cleaned), 1)
        self.assertEqual(cleaned[0], "desktop")
        self.assertIsNone(self.registry.read("desktop"))

    def test_cleanup_stale_keeps_alive(self):
        self.registry.register("desktop", os.getpid())
        cleaned = self.registry.cleanup_stale()
        self.assertEqual(len(cleaned), 0)
        self.assertIsNotNone(self.registry.read("desktop"))


    def test_heartbeat_updates_timestamp(self):
        self.registry.register("desktop", os.getpid())
        data_before = self.registry.read("desktop")
        time.sleep(0.01)
        self.registry.heartbeat("desktop")
        data_after = self.registry.read("desktop")
        self.assertGreater(data_after["last_heartbeat"], data_before["last_heartbeat"])

    def test_heartbeat_nonexistent_does_nothing(self):
        # Should not raise
        self.registry.heartbeat("desktop")

    def test_is_alive_via_fresh_heartbeat_even_dead_pid(self):
        """Fresh heartbeat = alive, even if PID is dead."""
        self.registry.register("desktop", 99999999)
        # Heartbeat is fresh (just registered) -> alive
        self.assertTrue(self.registry.is_alive("desktop"))

    def test_register_includes_heartbeat(self):
        self.registry.register("desktop", 12345)
        data = self.registry.read("desktop")
        self.assertIn("last_heartbeat", data)


class TestDetectFromPidfiles(unittest.TestCase):
    """detect_running_sessions_from_pidfiles — build SessionState from PID files."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.registry = PidRegistry(self.tmpdir)

    def test_empty_registry(self):
        state = detect_running_sessions_from_pidfiles(self.registry)
        self.assertFalse(state.desktop_running)
        self.assertFalse(state.worker_running)
        self.assertFalse(state.kalshi_running)

    def test_desktop_registered(self):
        self.registry.register("desktop", os.getpid())
        state = detect_running_sessions_from_pidfiles(self.registry)
        self.assertTrue(state.desktop_running)

    def test_worker_registered(self):
        self.registry.register("cli1", os.getpid())
        state = detect_running_sessions_from_pidfiles(self.registry)
        self.assertTrue(state.worker_running)

    def test_kalshi_registered(self):
        self.registry.register("kalshi", os.getpid())
        state = detect_running_sessions_from_pidfiles(self.registry)
        self.assertTrue(state.kalshi_running)

    def test_full_3chat(self):
        self.registry.register("desktop", os.getpid())
        self.registry.register("cli1", os.getpid())
        self.registry.register("kalshi", os.getpid())
        state = detect_running_sessions_from_pidfiles(self.registry)
        self.assertEqual(state.mode, SessionMode.THREE_CHAT)

    def test_dead_pid_with_expired_heartbeat_ignored(self):
        self.registry.register("desktop", os.getpid())
        self.registry.register("cli1", 99999999)
        # Expire cli1 heartbeat
        data = self.registry.read("cli1")
        data["last_heartbeat"] = time.time() - 9999
        with open(os.path.join(self.tmpdir, "cli1.pid"), "w") as f:
            json.dump(data, f)
        state = detect_running_sessions_from_pidfiles(self.registry)
        self.assertTrue(state.desktop_running)
        self.assertFalse(state.worker_running)

    def test_cleanup_runs_automatically(self):
        """Dead PIDs with expired heartbeats are cleaned up during detection."""
        self.registry.register("cli1", 99999999)
        # Expire heartbeat
        data = self.registry.read("cli1")
        data["last_heartbeat"] = time.time() - 9999
        with open(os.path.join(self.tmpdir, "cli1.pid"), "w") as f:
            json.dump(data, f)
        detect_running_sessions_from_pidfiles(self.registry)
        self.assertIsNone(self.registry.read("cli1"))


if __name__ == "__main__":
    unittest.main()
