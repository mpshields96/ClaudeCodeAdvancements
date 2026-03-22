#!/usr/bin/env python3
"""
Tests for session_daemon.py — MT-30 Phase 3: Daemon loop, health checking,
spawn/restart logic, audit logging, CLI interface.

TDD: These tests are written BEFORE implementation.
Target: session_daemon.py in the project root.

Tests cover:
- DaemonConfig: configuration and defaults
- AuditLogger: structured JSONL event logging
- SessionDaemon: core loop logic (mocked tmux + registry)
  - Health checking (detect dead sessions, trigger restart)
  - Spawn logic (respects max_chats, restart delay, restart count)
  - Peak hours enforcement (deprioritize/pause sessions)
  - Crash recovery integration (release orphaned scopes)
  - Graceful shutdown (SIGTERM/SIGINT handling)
- CLI: start/stop/status/restart/pause/resume/log commands
"""

import json
import os
import signal
import sys
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch, call

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from session_daemon import (
    AuditLogger,
    SessionDaemon,
    DaemonState,
)


class TestAuditLogger(unittest.TestCase):
    """Tests for the structured JSONL audit logger."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.log_path = os.path.join(self.tmpdir, "daemon.log")
        self.logger = AuditLogger(self.log_path)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_log_creates_file(self):
        """Logging creates the file if it doesn't exist."""
        self.logger.log("test_event", {"key": "value"})
        self.assertTrue(os.path.exists(self.log_path))

    def test_log_writes_jsonl(self):
        """Each log entry is a valid JSON line."""
        self.logger.log("daemon_started", {"pid": 12345})
        self.logger.log("session_spawned", {"session": "cca-desktop"})

        with open(self.log_path) as f:
            lines = f.readlines()

        self.assertEqual(len(lines), 2)
        entry1 = json.loads(lines[0])
        self.assertEqual(entry1["event"], "daemon_started")
        self.assertEqual(entry1["data"]["pid"], 12345)
        self.assertIn("ts", entry1)

    def test_log_has_timestamp(self):
        """Every log entry includes an ISO timestamp."""
        self.logger.log("test", {})
        with open(self.log_path) as f:
            entry = json.loads(f.readline())
        # Should be an ISO-format string
        self.assertRegex(entry["ts"], r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")

    def test_log_appends(self):
        """Multiple logs append to the same file."""
        for i in range(5):
            self.logger.log(f"event_{i}", {"i": i})

        with open(self.log_path) as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 5)

    def test_get_recent(self):
        """get_recent returns the last N entries."""
        for i in range(10):
            self.logger.log(f"event_{i}", {"i": i})

        recent = self.logger.get_recent(3)
        self.assertEqual(len(recent), 3)
        self.assertEqual(recent[0]["event"], "event_7")
        self.assertEqual(recent[2]["event"], "event_9")

    def test_get_recent_all(self):
        """get_recent with more than total returns all entries."""
        self.logger.log("only_one", {})
        recent = self.logger.get_recent(100)
        self.assertEqual(len(recent), 1)

    def test_get_recent_empty_file(self):
        """get_recent on non-existent file returns empty list."""
        logger = AuditLogger("/tmp/nonexistent_audit.log")
        self.assertEqual(logger.get_recent(5), [])

    def test_log_handles_non_serializable(self):
        """Logger handles non-JSON-serializable data gracefully."""
        # Should not raise, even with odd data
        self.logger.log("test", {"ts": time.time()})
        with open(self.log_path) as f:
            entry = json.loads(f.readline())
        self.assertEqual(entry["event"], "test")


class TestAuditLoggerRotation(unittest.TestCase):
    """Tests for AuditLogger log rotation."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.log_path = os.path.join(self.tmpdir, "daemon.log")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_no_rotation_under_limit(self):
        """Log file under max_bytes should not rotate."""
        logger = AuditLogger(self.log_path, max_bytes=10000, max_backups=3)
        logger.log("small_event", {"x": 1})
        self.assertTrue(os.path.exists(self.log_path))
        self.assertFalse(os.path.exists(f"{self.log_path}.1"))

    def test_rotation_creates_backup(self):
        """Log file exceeding max_bytes should create .1 backup."""
        logger = AuditLogger(self.log_path, max_bytes=100, max_backups=3)
        # Write enough to exceed 100 bytes
        for i in range(10):
            logger.log(f"event_{i}", {"data": "x" * 20})

        # After rotation, .1 should exist
        self.assertTrue(os.path.exists(f"{self.log_path}.1"))
        # Current log should be <= backup (post-rotation has fewer entries)
        self.assertLessEqual(os.path.getsize(self.log_path),
                             os.path.getsize(f"{self.log_path}.1"))

    def test_rotation_shifts_backups(self):
        """Multiple rotations shift .1 -> .2 -> .3."""
        logger = AuditLogger(self.log_path, max_bytes=50, max_backups=3)
        # Write many events to trigger multiple rotations
        for i in range(30):
            logger.log(f"event_{i}", {"data": "x" * 20})

        # Should have backup files
        self.assertTrue(os.path.exists(f"{self.log_path}.1"))

    def test_max_backups_respected(self):
        """Should not create more than max_backups backup files."""
        logger = AuditLogger(self.log_path, max_bytes=50, max_backups=2)
        for i in range(50):
            logger.log(f"event_{i}", {"data": "x" * 20})

        # .1 and .2 may exist, .3 should not
        self.assertFalse(os.path.exists(f"{self.log_path}.3"))

    def test_total_size_bytes(self):
        """total_size_bytes should sum log + all backups."""
        logger = AuditLogger(self.log_path, max_bytes=100, max_backups=3)
        for i in range(20):
            logger.log(f"event_{i}", {"data": "x" * 20})

        total = logger.total_size_bytes()
        self.assertGreater(total, 0)

    def test_total_size_bytes_no_file(self):
        """total_size_bytes returns 0 for non-existent files."""
        logger = AuditLogger(os.path.join(self.tmpdir, "nope.log"))
        self.assertEqual(logger.total_size_bytes(), 0)

    def test_rotation_preserves_recent_entries(self):
        """After rotation, most recent entries are in the current log."""
        logger = AuditLogger(self.log_path, max_bytes=100, max_backups=2)
        for i in range(20):
            logger.log(f"event_{i}", {"i": i})

        recent = logger.get_recent(100)
        # Current log has entries written after last rotation
        self.assertGreater(len(recent), 0)
        # Last entry should be the most recent event
        self.assertEqual(recent[-1]["data"]["i"], 19)

    def test_default_max_bytes(self):
        """Default max_bytes should be 5 MB."""
        logger = AuditLogger(self.log_path)
        self.assertEqual(logger.max_bytes, 5 * 1024 * 1024)

    def test_default_max_backups(self):
        """Default max_backups should be 3."""
        logger = AuditLogger(self.log_path)
        self.assertEqual(logger.max_backups, 3)


class TestDaemonState(unittest.TestCase):
    """Tests for daemon state tracking."""

    def test_initial_state(self):
        state = DaemonState()
        self.assertFalse(state.running)
        self.assertIsNone(state.pid)
        self.assertIsNone(state.started_at)
        self.assertEqual(state.total_spawns, 0)
        self.assertEqual(state.total_crashes, 0)

    def test_mark_started(self):
        state = DaemonState()
        state.mark_started(pid=12345)
        self.assertTrue(state.running)
        self.assertEqual(state.pid, 12345)
        self.assertIsNotNone(state.started_at)

    def test_mark_stopped(self):
        state = DaemonState()
        state.mark_started(pid=12345)
        state.mark_stopped()
        self.assertFalse(state.running)

    def test_uptime(self):
        state = DaemonState()
        state.mark_started(pid=1)
        state.started_at = time.time() - 120  # 2 minutes ago
        self.assertAlmostEqual(state.uptime_seconds(), 120, delta=2)

    def test_uptime_not_running(self):
        state = DaemonState()
        self.assertIsNone(state.uptime_seconds())

    def test_increment_counters(self):
        state = DaemonState()
        state.record_spawn("cca-desktop")
        state.record_spawn("kalshi-main")
        state.record_crash("kalshi-main")
        self.assertEqual(state.total_spawns, 2)
        self.assertEqual(state.total_crashes, 1)


class TestSessionDaemonInit(unittest.TestCase):
    """Tests for daemon initialization."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.tmpdir, "config.json")
        self.log_path = os.path.join(self.tmpdir, "daemon.log")
        self.state_path = os.path.join(self.tmpdir, "state.json")

        # Write a minimal valid config
        config = {
            "version": 1,
            "max_total_chats": 3,
            "max_restarts_per_hour": 5,
            "check_interval_seconds": 10,
            "sessions": [
                {
                    "id": "cca-desktop",
                    "type": "cca",
                    "role": "desktop",
                    "command": "claude /cca-init",
                    "priority": 1,
                    "env": {"CCA_CHAT_ID": "desktop"},
                },
                {
                    "id": "kalshi-main",
                    "type": "kalshi",
                    "role": "main",
                    "command": "claude /kalshi-main",
                    "priority": 2,
                    "cwd": "/tmp/polymarket-bot",
                },
            ],
            "peak_hours": {
                "max_chats": 1,
                "deprioritize": ["kalshi-main"],
            },
        }
        with open(self.config_path, "w") as f:
            json.dump(config, f)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_daemon_loads_config(self):
        """Daemon loads config from file."""
        daemon = SessionDaemon(
            config_path=self.config_path,
            log_path=self.log_path,
        )
        self.assertEqual(len(daemon.registry.get_all_sessions()), 2)

    def test_daemon_creates_audit_logger(self):
        """Daemon creates an audit logger."""
        daemon = SessionDaemon(
            config_path=self.config_path,
            log_path=self.log_path,
        )
        self.assertIsInstance(daemon.audit, AuditLogger)

    def test_daemon_initial_state(self):
        """Daemon starts in non-running state."""
        daemon = SessionDaemon(
            config_path=self.config_path,
            log_path=self.log_path,
        )
        self.assertFalse(daemon.state.running)


class TestSessionDaemonHealthCheck(unittest.TestCase):
    """Tests for health check logic — detecting dead sessions."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.tmpdir, "config.json")
        self.log_path = os.path.join(self.tmpdir, "daemon.log")

        config = {
            "version": 1,
            "max_total_chats": 3,
            "max_restarts_per_hour": 5,
            "check_interval_seconds": 10,
            "sessions": [
                {
                    "id": "cca-desktop",
                    "type": "cca",
                    "role": "desktop",
                    "command": "claude /cca-init",
                    "priority": 1,
                },
                {
                    "id": "kalshi-main",
                    "type": "kalshi",
                    "role": "main",
                    "command": "claude /kalshi-main",
                    "priority": 2,
                    "restart_delay_seconds": 10,
                },
            ],
            "peak_hours": {"max_chats": 2, "deprioritize": []},
        }
        with open(self.config_path, "w") as f:
            json.dump(config, f)

        self.daemon = SessionDaemon(
            config_path=self.config_path,
            log_path=self.log_path,
        )
        # Mock tmux manager
        self.daemon.tmux = MagicMock()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_check_health_detects_dead_session(self):
        """Health check detects when a running session dies."""
        session = self.daemon.registry.get_session("cca-desktop")
        session.mark_running(pid=111, tmux_window="cca-desktop")

        # Tmux reports session is dead
        self.daemon.tmux.is_alive.return_value = False
        self.daemon.tmux.has_wrap_marker.return_value = False
        self.daemon.tmux.get_exit_code.return_value = 1

        results = self.daemon.check_health()

        self.assertIn("cca-desktop", [r["session_id"] for r in results])
        dead = [r for r in results if r["session_id"] == "cca-desktop"][0]
        self.assertEqual(dead["status"], "crashed")

    def test_check_health_detects_clean_wrap(self):
        """Health check identifies clean wraps vs crashes."""
        session = self.daemon.registry.get_session("cca-desktop")
        session.mark_running(pid=111, tmux_window="cca-desktop")

        self.daemon.tmux.is_alive.return_value = False
        self.daemon.tmux.has_wrap_marker.return_value = True
        self.daemon.tmux.get_exit_code.return_value = 0

        results = self.daemon.check_health()

        dead = [r for r in results if r["session_id"] == "cca-desktop"][0]
        self.assertEqual(dead["status"], "stopped")

    def test_check_health_running_session_ok(self):
        """Health check returns nothing for healthy running sessions."""
        session = self.daemon.registry.get_session("cca-desktop")
        session.mark_running(pid=111, tmux_window="cca-desktop")

        self.daemon.tmux.is_alive.return_value = True

        results = self.daemon.check_health()
        dead = [r for r in results if r["session_id"] == "cca-desktop"]
        self.assertEqual(len(dead), 0)

    def test_check_health_skips_non_running(self):
        """Health check skips sessions that aren't marked as running."""
        # cca-desktop is PENDING (never started)
        session = self.daemon.registry.get_session("cca-desktop")
        self.assertEqual(session.status.value, "pending")

        results = self.daemon.check_health()
        self.assertEqual(len(results), 0)


class TestSessionDaemonSpawn(unittest.TestCase):
    """Tests for session spawn logic."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.tmpdir, "config.json")
        self.log_path = os.path.join(self.tmpdir, "daemon.log")

        config = {
            "version": 1,
            "max_total_chats": 3,
            "max_restarts_per_hour": 3,
            "check_interval_seconds": 10,
            "sessions": [
                {
                    "id": "cca-desktop",
                    "type": "cca",
                    "role": "desktop",
                    "command": "claude /cca-init",
                    "priority": 1,
                    "restart_delay_seconds": 10,
                },
                {
                    "id": "kalshi-main",
                    "type": "kalshi",
                    "role": "main",
                    "command": "claude /kalshi-main",
                    "priority": 2,
                    "restart_delay_seconds": 10,
                    "cwd": "/tmp/polymarket-bot",
                },
                {
                    "id": "kalshi-research",
                    "type": "kalshi",
                    "role": "research",
                    "command": "claude /kalshi-research",
                    "priority": 3,
                    "restart_delay_seconds": 10,
                    "cwd": "/tmp/polymarket-bot",
                },
            ],
            "peak_hours": {"max_chats": 1, "deprioritize": ["kalshi-research"]},
        }
        with open(self.config_path, "w") as f:
            json.dump(config, f)

        self.daemon = SessionDaemon(
            config_path=self.config_path,
            log_path=self.log_path,
        )
        self.daemon.tmux = MagicMock()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_spawn_session_calls_tmux(self):
        """Spawning a session creates a tmux window."""
        self.daemon.tmux.create_window.return_value = 222
        session = self.daemon.registry.get_session("cca-desktop")

        result = self.daemon.spawn_session(session)

        self.assertTrue(result)
        self.daemon.tmux.create_window.assert_called_once()
        self.assertEqual(session.status.value, "running")
        self.assertEqual(session.pid, 222)

    def test_spawn_respects_max_chats(self):
        """Cannot spawn if max_total_chats reached."""
        # Mark all 3 as running (max is 3)
        s1 = self.daemon.registry.get_session("cca-desktop")
        s1.mark_running(pid=111, tmux_window="cca-desktop")
        s2 = self.daemon.registry.get_session("kalshi-main")
        s2.mark_running(pid=222, tmux_window="kalshi-main")
        s3 = self.daemon.registry.get_session("kalshi-research")
        s3.mark_running(pid=333, tmux_window="kalshi-research")

        # Add a 4th session dynamically to test the limit
        from session_registry import SessionConfig
        extra = SessionConfig(id="extra", type="cca", role="test",
                              command="echo test", priority=4)
        s4 = self.daemon.registry.add_session(extra)
        result = self.daemon.spawn_session(s4)

        self.assertFalse(result)
        self.daemon.tmux.create_window.assert_not_called()

    def test_spawn_respects_restart_delay(self):
        """Cannot spawn if restart delay hasn't elapsed."""
        session = self.daemon.registry.get_session("cca-desktop")
        session.mark_stopped()
        session.stopped_at = time.time()  # Just stopped

        result = self.daemon.spawn_session(session)

        self.assertFalse(result)  # 10s delay not met

    def test_spawn_after_delay(self):
        """Can spawn after restart delay has elapsed."""
        self.daemon.tmux.create_window.return_value = 333
        session = self.daemon.registry.get_session("cca-desktop")
        session.mark_stopped()
        session.stopped_at = time.time() - 15  # 15s ago, delay is 10s

        result = self.daemon.spawn_session(session)

        self.assertTrue(result)

    def test_spawn_increments_restart_count(self):
        """Spawning a previously-stopped session increments restart count."""
        self.daemon.tmux.create_window.return_value = 444
        session = self.daemon.registry.get_session("cca-desktop")
        session.mark_stopped()
        session.stopped_at = time.time() - 100

        self.daemon.spawn_session(session)

        self.assertEqual(session.restart_count, 1)

    def test_spawn_fails_at_max_restarts(self):
        """Session marked FAILED after exceeding max restarts per hour."""
        session = self.daemon.registry.get_session("cca-desktop")
        # Fill up restart timestamps
        now = time.time()
        session.restart_timestamps = [now - 10, now - 20, now - 30]  # 3 = max
        session.mark_crashed()
        session.stopped_at = time.time() - 100

        result = self.daemon.spawn_session(session)

        self.assertFalse(result)
        self.assertEqual(session.status.value, "failed")

    def test_spawn_logs_audit_event(self):
        """Spawning logs a session_spawned audit event."""
        self.daemon.tmux.create_window.return_value = 555
        session = self.daemon.registry.get_session("cca-desktop")

        self.daemon.spawn_session(session)

        with open(self.log_path) as f:
            lines = f.readlines()
        events = [json.loads(l)["event"] for l in lines]
        self.assertIn("session_spawned", events)

    def test_spawn_records_state_counter(self):
        """Spawn increments daemon state counter."""
        self.daemon.tmux.create_window.return_value = 666
        session = self.daemon.registry.get_session("cca-desktop")

        self.daemon.spawn_session(session)

        self.assertEqual(self.daemon.state.total_spawns, 1)


class TestSessionDaemonPeakHours(unittest.TestCase):
    """Tests for peak hours enforcement."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.tmpdir, "config.json")
        self.log_path = os.path.join(self.tmpdir, "daemon.log")

        config = {
            "version": 1,
            "max_total_chats": 3,
            "max_restarts_per_hour": 5,
            "check_interval_seconds": 10,
            "sessions": [
                {
                    "id": "cca-desktop",
                    "type": "cca",
                    "role": "desktop",
                    "command": "claude /cca-init",
                    "priority": 1,
                },
                {
                    "id": "kalshi-research",
                    "type": "kalshi",
                    "role": "research",
                    "command": "claude /kalshi-research",
                    "priority": 3,
                    "cwd": "/tmp/polymarket-bot",
                },
            ],
            "peak_hours": {"max_chats": 1, "deprioritize": ["kalshi-research"]},
        }
        with open(self.config_path, "w") as f:
            json.dump(config, f)

        self.daemon = SessionDaemon(
            config_path=self.config_path,
            log_path=self.log_path,
        )
        self.daemon.tmux = MagicMock()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("session_daemon.peak_hours_get_status")
    def test_peak_enforcement_deprioritizes(self, mock_peak):
        """During peak hours, deprioritized sessions get paused."""
        mock_peak.return_value = {"is_peak": True, "max_recommended_chats": 1}

        # Both running
        s1 = self.daemon.registry.get_session("cca-desktop")
        s1.mark_running(pid=111, tmux_window="cca-desktop")
        s2 = self.daemon.registry.get_session("kalshi-research")
        s2.mark_running(pid=222, tmux_window="kalshi-research")

        actions = self.daemon.enforce_peak_hours()

        # kalshi-research should be deprioritized
        self.assertTrue(len(actions) > 0)
        self.assertEqual(actions[0]["session_id"], "kalshi-research")
        self.assertEqual(actions[0]["action"], "deprioritized")

    @patch("session_daemon.peak_hours_get_status")
    def test_off_peak_no_enforcement(self, mock_peak):
        """Off-peak hours don't deprioritize anything."""
        mock_peak.return_value = {"is_peak": False, "max_recommended_chats": 3}

        s1 = self.daemon.registry.get_session("cca-desktop")
        s1.mark_running(pid=111, tmux_window="cca-desktop")

        actions = self.daemon.enforce_peak_hours()
        self.assertEqual(len(actions), 0)

    @patch("session_daemon.peak_hours_get_status")
    def test_peak_to_off_peak_restores(self, mock_peak):
        """When peak hours end, deprioritized sessions become restartable."""
        mock_peak.return_value = {"is_peak": False, "max_recommended_chats": 3}

        session = self.daemon.registry.get_session("kalshi-research")
        session.mark_deprioritized()

        actions = self.daemon.restore_deprioritized()

        self.assertTrue(len(actions) > 0)
        # Session should be back to a restartable state
        self.assertIn(session.status.value, ("pending", "stopped"))


class TestSessionDaemonCycle(unittest.TestCase):
    """Tests for a single daemon cycle (check -> spawn -> enforce)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.tmpdir, "config.json")
        self.log_path = os.path.join(self.tmpdir, "daemon.log")

        config = {
            "version": 1,
            "max_total_chats": 2,
            "max_restarts_per_hour": 5,
            "check_interval_seconds": 10,
            "sessions": [
                {
                    "id": "cca-desktop",
                    "type": "cca",
                    "role": "desktop",
                    "command": "claude /cca-init",
                    "priority": 1,
                    "restart_delay_seconds": 10,
                },
            ],
            "peak_hours": {"max_chats": 2, "deprioritize": []},
        }
        with open(self.config_path, "w") as f:
            json.dump(config, f)

        self.daemon = SessionDaemon(
            config_path=self.config_path,
            log_path=self.log_path,
        )
        self.daemon.tmux = MagicMock()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("session_daemon.peak_hours_get_status")
    def test_single_cycle_spawns_pending(self, mock_peak):
        """A single daemon cycle spawns pending sessions."""
        mock_peak.return_value = {"is_peak": False, "max_recommended_chats": 3}
        self.daemon.tmux.create_window.return_value = 999
        self.daemon.tmux.is_alive.return_value = True

        self.daemon.run_cycle()

        self.daemon.tmux.create_window.assert_called_once()
        session = self.daemon.registry.get_session("cca-desktop")
        self.assertEqual(session.status.value, "running")

    @patch("session_daemon.peak_hours_get_status")
    def test_cycle_detects_crash_and_restarts(self, mock_peak):
        """Cycle detects crashed session and restarts after delay."""
        mock_peak.return_value = {"is_peak": False, "max_recommended_chats": 3}

        session = self.daemon.registry.get_session("cca-desktop")
        session.mark_running(pid=111, tmux_window="cca-desktop")

        # First cycle: detect crash
        self.daemon.tmux.is_alive.return_value = False
        self.daemon.tmux.has_wrap_marker.return_value = False
        self.daemon.tmux.get_exit_code.return_value = 1
        self.daemon.tmux.kill_window.return_value = True

        self.daemon.run_cycle()

        self.assertEqual(session.status.value, "crashed")

        # Second cycle: too soon to restart (delay not met)
        session.stopped_at = time.time()
        self.daemon.tmux.create_window.return_value = 888

        self.daemon.run_cycle()
        # Should NOT have spawned (10s delay)
        self.daemon.tmux.create_window.assert_not_called()

        # Third cycle: after delay
        session.stopped_at = time.time() - 15
        self.daemon.run_cycle()
        self.daemon.tmux.create_window.assert_called_once()


class TestSessionDaemonStatus(unittest.TestCase):
    """Tests for status reporting."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.tmpdir, "config.json")
        self.log_path = os.path.join(self.tmpdir, "daemon.log")

        config = {
            "version": 1,
            "max_total_chats": 3,
            "max_restarts_per_hour": 5,
            "check_interval_seconds": 10,
            "sessions": [
                {
                    "id": "cca-desktop",
                    "type": "cca",
                    "role": "desktop",
                    "command": "claude /cca-init",
                    "priority": 1,
                },
            ],
            "peak_hours": {"max_chats": 2, "deprioritize": []},
        }
        with open(self.config_path, "w") as f:
            json.dump(config, f)

        self.daemon = SessionDaemon(
            config_path=self.config_path,
            log_path=self.log_path,
        )

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_status_report_structure(self):
        """Status report has expected fields."""
        report = self.daemon.get_status_report()

        self.assertIn("daemon_running", report)
        self.assertIn("sessions", report)
        self.assertIn("total_spawns", report)
        self.assertIn("total_crashes", report)

    def test_status_report_session_detail(self):
        """Status report includes session details."""
        session = self.daemon.registry.get_session("cca-desktop")
        session.mark_running(pid=123, tmux_window="cca-desktop")

        report = self.daemon.get_status_report()

        s = report["sessions"][0]
        self.assertEqual(s["id"], "cca-desktop")
        self.assertEqual(s["status"], "running")
        self.assertEqual(s["pid"], 123)

    def test_format_status(self):
        """format_status produces human-readable output."""
        output = self.daemon.format_status()
        self.assertIn("Session Daemon", output)
        self.assertIn("cca-desktop", output)


class TestSessionDaemonShutdown(unittest.TestCase):
    """Tests for graceful shutdown."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.tmpdir, "config.json")
        self.log_path = os.path.join(self.tmpdir, "daemon.log")

        config = {
            "version": 1,
            "max_total_chats": 2,
            "max_restarts_per_hour": 5,
            "check_interval_seconds": 10,
            "sessions": [
                {
                    "id": "cca-desktop",
                    "type": "cca",
                    "role": "desktop",
                    "command": "claude /cca-init",
                    "priority": 1,
                },
            ],
            "peak_hours": {"max_chats": 2, "deprioritize": []},
        }
        with open(self.config_path, "w") as f:
            json.dump(config, f)

        self.daemon = SessionDaemon(
            config_path=self.config_path,
            log_path=self.log_path,
        )
        self.daemon.tmux = MagicMock()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_stop_sets_running_false(self):
        """stop() sets running to False."""
        self.daemon.state.mark_started(pid=os.getpid())
        self.daemon.stop()
        self.assertFalse(self.daemon.state.running)

    def test_stop_with_kill_sessions(self):
        """stop(kill_sessions=True) kills managed windows."""
        session = self.daemon.registry.get_session("cca-desktop")
        session.mark_running(pid=111, tmux_window="cca-desktop")
        self.daemon.state.mark_started(pid=os.getpid())

        self.daemon.stop(kill_sessions=True)

        self.daemon.tmux.kill_window.assert_called_with("cca-desktop", graceful=True)

    def test_stop_without_kill_leaves_sessions(self):
        """stop(kill_sessions=False) leaves sessions running."""
        session = self.daemon.registry.get_session("cca-desktop")
        session.mark_running(pid=111, tmux_window="cca-desktop")
        self.daemon.state.mark_started(pid=os.getpid())

        self.daemon.stop(kill_sessions=False)

        self.daemon.tmux.kill_window.assert_not_called()

    def test_stop_logs_event(self):
        """stop() logs a daemon_stopped event."""
        self.daemon.state.mark_started(pid=os.getpid())
        self.daemon.stop()

        with open(self.log_path) as f:
            lines = f.readlines()
        events = [json.loads(l)["event"] for l in lines]
        self.assertIn("daemon_stopped", events)


class TestSessionDaemonPIDFile(unittest.TestCase):
    """Tests for PID file singleton enforcement."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.tmpdir, "config.json")
        self.log_path = os.path.join(self.tmpdir, "daemon.log")
        self.pid_path = os.path.join(self.tmpdir, "daemon.pid")

        config = {
            "version": 1,
            "max_total_chats": 2,
            "max_restarts_per_hour": 5,
            "check_interval_seconds": 10,
            "sessions": [],
            "peak_hours": {"max_chats": 2, "deprioritize": []},
        }
        with open(self.config_path, "w") as f:
            json.dump(config, f)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_acquire_pid_creates_file(self):
        """acquire_pid_file creates the PID file."""
        daemon = SessionDaemon(
            config_path=self.config_path,
            log_path=self.log_path,
            pid_path=self.pid_path,
        )
        result = daemon.acquire_pid_file()
        self.assertTrue(result)
        self.assertTrue(os.path.exists(self.pid_path))
        with open(self.pid_path) as f:
            self.assertEqual(int(f.read().strip()), os.getpid())

    def test_acquire_pid_blocks_duplicate(self):
        """acquire_pid_file fails if another daemon is running."""
        # Write a PID of our own process (simulating existing daemon)
        with open(self.pid_path, "w") as f:
            f.write(str(os.getpid()))

        daemon = SessionDaemon(
            config_path=self.config_path,
            log_path=self.log_path,
            pid_path=self.pid_path,
        )
        result = daemon.acquire_pid_file()
        self.assertFalse(result)

    def test_acquire_pid_cleans_stale(self):
        """acquire_pid_file cleans up stale PID files (dead process)."""
        # Write a PID that doesn't exist
        with open(self.pid_path, "w") as f:
            f.write("99999999")

        daemon = SessionDaemon(
            config_path=self.config_path,
            log_path=self.log_path,
            pid_path=self.pid_path,
        )
        result = daemon.acquire_pid_file()
        self.assertTrue(result)

    def test_release_pid_removes_file(self):
        """release_pid_file removes the PID file."""
        daemon = SessionDaemon(
            config_path=self.config_path,
            log_path=self.log_path,
            pid_path=self.pid_path,
        )
        daemon.acquire_pid_file()
        daemon.release_pid_file()
        self.assertFalse(os.path.exists(self.pid_path))


if __name__ == "__main__":
    unittest.main()
