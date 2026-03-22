#!/usr/bin/env python3
"""
Integration tests for session_daemon.py — MT-30 Phase 4.

Tests multi-cycle daemon behavior: full lifecycle flows, peak hour
transitions, crash recovery chains, audit trail consistency, and
mixed session type management.

These complement the unit tests in test_session_daemon.py.
"""

import json
import os
import sys
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from session_daemon import AuditLogger, SessionDaemon, DaemonState
from session_registry import SessionRegistry, SessionConfig, SessionState, SessionStatus


def _make_config(tmpdir, sessions, max_chats=3, max_restarts=5,
                 peak_deprioritize=None):
    """Create a temp config file with given sessions."""
    config = {
        "version": 1,
        "max_total_chats": max_chats,
        "max_restarts_per_hour": max_restarts,
        "check_interval_seconds": 1,
        "sessions": sessions,
        "peak_hours": {
            "max_chats": 2,
            "deprioritize": peak_deprioritize or [],
        },
    }
    path = os.path.join(tmpdir, "config.json")
    with open(path, "w") as f:
        json.dump(config, f)
    return path


def _make_daemon(tmpdir, sessions, **kwargs):
    """Create a daemon with temp config, log, and PID file."""
    config_path = _make_config(tmpdir, sessions, **kwargs)
    log_path = os.path.join(tmpdir, "daemon.log")
    pid_path = os.path.join(tmpdir, "daemon.pid")
    daemon = SessionDaemon(
        config_path=config_path,
        log_path=log_path,
        pid_path=pid_path,
    )
    # Mock tmux — all spawn calls succeed
    daemon.tmux = MagicMock()
    daemon.tmux.create_session = MagicMock()
    daemon.tmux.create_window = MagicMock(return_value=12345)
    daemon.tmux.is_alive = MagicMock(return_value=True)
    daemon.tmux.kill_window = MagicMock()
    daemon.tmux.has_wrap_marker = MagicMock(return_value=False)
    daemon.tmux.get_exit_code = MagicMock(return_value=1)
    return daemon


def _expire_restart_delays(daemon):
    """Backdate stopped_at on all crashed/stopped sessions so they pass delay checks."""
    for s in daemon.registry.get_all_sessions():
        if s.status in (SessionStatus.CRASHED, SessionStatus.STOPPED) and s.stopped_at:
            s.stopped_at = time.time() - 999


def _read_audit_log(tmpdir):
    """Read all audit log entries."""
    log_path = os.path.join(tmpdir, "daemon.log")
    if not os.path.exists(log_path):
        return []
    with open(log_path) as f:
        return [json.loads(line) for line in f if line.strip()]


# Use restart_delay_seconds=0 so respawns happen immediately in tests
TWO_SESSIONS = [
    {"id": "cca-desktop", "type": "cca", "role": "desktop",
     "command": "claude --session cca", "priority": 1,
     "restart_delay_seconds": 10},
    {"id": "kalshi-main", "type": "kalshi", "role": "main",
     "command": "claude --session kalshi", "priority": 2,
     "restart_delay_seconds": 10},
]

THREE_SESSIONS = TWO_SESSIONS + [
    {"id": "kalshi-research", "type": "kalshi", "role": "research",
     "command": "claude --session research", "priority": 3,
     "restart_delay_seconds": 10},
]


class TestLifecycleSpawnAndCrash(unittest.TestCase):
    """Full lifecycle: spawn -> detect crash -> respawn."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("session_daemon.peak_hours_get_status",
           return_value={"is_peak": False, "max_recommended_chats": 3})
    def test_initial_cycle_spawns_all_pending(self, mock_ph):
        """First cycle should spawn all PENDING sessions."""
        daemon = _make_daemon(self.tmpdir, TWO_SESSIONS)
        daemon.run_cycle()

        running = daemon.registry.get_running_sessions()
        self.assertEqual(len(running), 2)
        self.assertEqual(daemon.state.total_spawns, 2)

    @patch("session_daemon.peak_hours_get_status",
           return_value={"is_peak": False, "max_recommended_chats": 3})
    def test_crash_detected_and_respawned(self, mock_ph):
        """If a session dies, health check detects crash, then respawns after delay."""
        daemon = _make_daemon(self.tmpdir, TWO_SESSIONS)

        # Cycle 1: spawn both
        daemon.run_cycle()
        self.assertEqual(len(daemon.registry.get_running_sessions()), 2)

        # Simulate crash: cca-desktop tmux window dies
        def is_alive_side_effect(name):
            return name != "cca-desktop"
        daemon.tmux.is_alive = MagicMock(side_effect=is_alive_side_effect)

        # Cycle 2: detect crash (won't respawn yet due to delay)
        daemon.run_cycle()
        self.assertEqual(daemon.state.total_crashes, 1)

        # Expire delay, then cycle 3: respawn
        _expire_restart_delays(daemon)
        daemon.tmux.is_alive = MagicMock(side_effect=is_alive_side_effect)
        daemon.run_cycle()

        cca = daemon.registry._sessions["cca-desktop"]
        self.assertEqual(cca.status, SessionStatus.RUNNING)
        self.assertEqual(cca.restart_count, 1)
        self.assertEqual(daemon.state.total_spawns, 3)

    @patch("session_daemon.peak_hours_get_status",
           return_value={"is_peak": False, "max_recommended_chats": 3})
    def test_clean_wrap_detected(self, mock_ph):
        """Clean wrap (exit code 0, wrap marker) detected as STOPPED."""
        daemon = _make_daemon(self.tmpdir,
                              [{"id": "cca-desktop", "type": "cca",
                                "role": "desktop", "command": "claude",
                                "restart_delay_seconds": 10}])

        daemon.run_cycle()  # Spawn
        cca = daemon.registry._sessions["cca-desktop"]
        self.assertEqual(cca.status, SessionStatus.RUNNING)

        # Simulate clean exit
        daemon.tmux.is_alive = MagicMock(return_value=False)
        daemon.tmux.has_wrap_marker = MagicMock(return_value=True)
        daemon.tmux.get_exit_code = MagicMock(return_value=0)

        daemon.run_cycle()  # Detect clean wrap (delay=10s prevents immediate respawn)

        cca = daemon.registry._sessions["cca-desktop"]
        self.assertEqual(cca.status, SessionStatus.STOPPED)
        # Clean wrap doesn't increment restart_count (that happens on respawn)
        self.assertEqual(cca.last_error, "clean_wrap")

    @patch("session_daemon.peak_hours_get_status",
           return_value={"is_peak": False, "max_recommended_chats": 3})
    def test_multi_crash_exhausts_restarts(self, mock_ph):
        """Repeated crashes exhaust restart budget — session stays CRASHED.

        With max_restarts=2, can_restart allows <2 recent timestamps.
        After 2 restarts, further crashes leave session as CRASHED (no more
        restarts allowed). get_runnable_sessions filters them out.
        """
        daemon = _make_daemon(self.tmpdir,
                              [{"id": "cca-desktop", "type": "cca",
                                "role": "desktop", "command": "claude",
                                "restart_delay_seconds": 10}],
                              max_restarts=2)

        # Spawn
        daemon.run_cycle()

        # Two crash-respawn cycles (using up both allowed restarts)
        for i in range(2):
            daemon.tmux.is_alive = MagicMock(return_value=False)
            daemon.run_cycle()  # Detect crash
            _expire_restart_delays(daemon)
            daemon.run_cycle()  # Respawn after delay
            daemon.tmux.is_alive = MagicMock(return_value=True)

        # 3rd crash: already used 2 restarts, max=2 -> stays CRASHED
        daemon.tmux.is_alive = MagicMock(return_value=False)
        daemon.run_cycle()  # Detect crash
        _expire_restart_delays(daemon)
        daemon.run_cycle()  # No respawn (can_restart=False)

        cca = daemon.registry._sessions["cca-desktop"]
        self.assertEqual(cca.status, SessionStatus.FAILED)
        self.assertEqual(cca.restart_count, 2)
        self.assertEqual(cca.last_error, "max_restarts_exceeded")
        # Verify it's not in runnable anymore
        runnable = daemon.registry.get_runnable_sessions()
        self.assertEqual(len(runnable), 0)

    @patch("session_daemon.peak_hours_get_status",
           return_value={"is_peak": False, "max_recommended_chats": 3})
    def test_audit_trail_records_lifecycle(self, mock_ph):
        """Audit log should capture spawn, crash, and respawn events."""
        daemon = _make_daemon(self.tmpdir, TWO_SESSIONS)

        daemon.run_cycle()  # Spawn both

        # Crash cca-desktop
        def is_alive_side_effect(name):
            return name != "cca-desktop"
        daemon.tmux.is_alive = MagicMock(side_effect=is_alive_side_effect)
        daemon.run_cycle()  # Detect crash

        entries = _read_audit_log(self.tmpdir)
        events = [e["event"] for e in entries]
        self.assertIn("session_spawned", events)
        self.assertIn("session_crashed", events)

        # Verify spawn events include PID
        spawns = [e for e in entries if e["event"] == "session_spawned"]
        self.assertTrue(all("pid" in e["data"] for e in spawns))


class TestPeakHourTransitions(unittest.TestCase):
    """Test peak hour enforcement across multiple cycles."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("session_daemon.peak_hours_get_status")
    def test_peak_deprioritizes_low_priority_session(self, mock_ph):
        """During peak, low-priority sessions get deprioritized."""
        mock_ph.return_value = {"is_peak": False, "max_recommended_chats": 3}

        daemon = _make_daemon(self.tmpdir, THREE_SESSIONS,
                              peak_deprioritize=["kalshi-research"])

        # Off-peak: spawn all 3
        daemon.run_cycle()
        self.assertEqual(len(daemon.registry.get_running_sessions()), 3)

        # Switch to peak
        mock_ph.return_value = {"is_peak": True, "max_recommended_chats": 2}
        daemon.run_cycle()

        research = daemon.registry._sessions["kalshi-research"]
        self.assertEqual(research.status, SessionStatus.DEPRIORITIZED)

    @patch("session_daemon.peak_hours_get_status")
    def test_off_peak_restores_deprioritized(self, mock_ph):
        """When peak ends, deprioritized sessions become restartable."""
        mock_ph.return_value = {"is_peak": False, "max_recommended_chats": 3}

        daemon = _make_daemon(self.tmpdir, THREE_SESSIONS,
                              peak_deprioritize=["kalshi-research"])

        # Spawn all
        daemon.run_cycle()

        # Peak: deprioritize research
        mock_ph.return_value = {"is_peak": True, "max_recommended_chats": 2}
        daemon.run_cycle()

        research = daemon.registry._sessions["kalshi-research"]
        self.assertEqual(research.status, SessionStatus.DEPRIORITIZED)

        # Off-peak: restore and respawn
        mock_ph.return_value = {"is_peak": False, "max_recommended_chats": 3}
        daemon.run_cycle()

        research = daemon.registry._sessions["kalshi-research"]
        # restore_deprioritized sets status to STOPPED, then get_runnable picks it up
        self.assertIn(research.status,
                      [SessionStatus.RUNNING, SessionStatus.STOPPED])

    @patch("session_daemon.peak_hours_get_status")
    def test_peak_audit_trail(self, mock_ph):
        """Peak hour events should appear in audit log."""
        mock_ph.return_value = {"is_peak": False, "max_recommended_chats": 3}

        daemon = _make_daemon(self.tmpdir, THREE_SESSIONS,
                              peak_deprioritize=["kalshi-research"])

        daemon.run_cycle()  # Spawn

        mock_ph.return_value = {"is_peak": True, "max_recommended_chats": 2}
        daemon.run_cycle()  # Deprioritize

        entries = _read_audit_log(self.tmpdir)
        events = [e["event"] for e in entries]
        self.assertIn("session_deprioritized", events)

    @patch("session_daemon.peak_hours_get_status")
    def test_non_deprioritizable_sessions_survive_peak(self, mock_ph):
        """Sessions not in deprioritize list stay running during peak."""
        mock_ph.return_value = {"is_peak": False, "max_recommended_chats": 3}

        daemon = _make_daemon(self.tmpdir, THREE_SESSIONS,
                              peak_deprioritize=["kalshi-research"])

        daemon.run_cycle()

        mock_ph.return_value = {"is_peak": True, "max_recommended_chats": 2}
        daemon.run_cycle()

        cca = daemon.registry._sessions["cca-desktop"]
        kalshi = daemon.registry._sessions["kalshi-main"]
        self.assertEqual(cca.status, SessionStatus.RUNNING)
        self.assertEqual(kalshi.status, SessionStatus.RUNNING)


class TestMixedSessionTypes(unittest.TestCase):
    """Test behavior with mixed CCA + Kalshi sessions."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("session_daemon.peak_hours_get_status",
           return_value={"is_peak": False, "max_recommended_chats": 3})
    def test_mixed_types_all_spawn(self, mock_ph):
        """Both CCA and Kalshi sessions should spawn."""
        daemon = _make_daemon(self.tmpdir, TWO_SESSIONS)
        daemon.run_cycle()

        sessions = daemon.registry.get_running_sessions()
        types = {s.config.type for s in sessions}
        self.assertIn("cca", types)
        self.assertIn("kalshi", types)

    @patch("session_daemon.peak_hours_get_status",
           return_value={"is_peak": False, "max_recommended_chats": 3})
    def test_status_report_shows_all_types(self, mock_ph):
        """Status report should include session type information."""
        daemon = _make_daemon(self.tmpdir, THREE_SESSIONS)
        daemon.state.mark_started(pid=os.getpid())
        daemon.run_cycle()

        report = daemon.get_status_report()
        session_types = {s["type"] for s in report["sessions"]}
        self.assertIn("cca", session_types)
        self.assertIn("kalshi", session_types)

    @patch("session_daemon.peak_hours_get_status",
           return_value={"is_peak": False, "max_recommended_chats": 3})
    def test_format_status_readable(self, mock_ph):
        """format_status should produce non-empty human-readable output."""
        daemon = _make_daemon(self.tmpdir, TWO_SESSIONS)
        daemon.state.mark_started(pid=os.getpid())
        daemon.run_cycle()

        output = daemon.format_status()
        self.assertIn("Session Daemon", output)
        self.assertIn("cca-desktop", output)
        self.assertIn("kalshi-main", output)


class TestDaemonStateConsistency(unittest.TestCase):
    """Test that daemon state remains consistent across operations."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("session_daemon.peak_hours_get_status",
           return_value={"is_peak": False, "max_recommended_chats": 3})
    def test_spawn_count_tracks_all_spawns(self, mock_ph):
        """total_spawns should count initial + restart spawns."""
        daemon = _make_daemon(self.tmpdir, TWO_SESSIONS)

        daemon.run_cycle()  # 2 spawns
        self.assertEqual(daemon.state.total_spawns, 2)

        # Crash one
        def is_alive_side_effect(name):
            return name != "cca-desktop"
        daemon.tmux.is_alive = MagicMock(side_effect=is_alive_side_effect)
        daemon.run_cycle()  # Detect crash
        _expire_restart_delays(daemon)
        daemon.tmux.is_alive = MagicMock(side_effect=is_alive_side_effect)
        daemon.run_cycle()  # Respawn after delay
        self.assertEqual(daemon.state.total_spawns, 3)

    @patch("session_daemon.peak_hours_get_status",
           return_value={"is_peak": False, "max_recommended_chats": 3})
    def test_crash_count_accurate(self, mock_ph):
        """total_crashes should only count actual crashes, not clean stops."""
        daemon = _make_daemon(self.tmpdir, TWO_SESSIONS)
        daemon.run_cycle()

        # Crash cca-desktop, clean wrap kalshi-main
        daemon.tmux.is_alive = MagicMock(return_value=False)

        def wrap_marker(name):
            return name == "kalshi-main"
        daemon.tmux.has_wrap_marker = MagicMock(side_effect=wrap_marker)

        def exit_code(name):
            return 0 if name == "kalshi-main" else 1
        daemon.tmux.get_exit_code = MagicMock(side_effect=exit_code)

        daemon.run_cycle()
        self.assertEqual(daemon.state.total_crashes, 1)

    @patch("session_daemon.peak_hours_get_status",
           return_value={"is_peak": False, "max_recommended_chats": 3})
    def test_stop_preserves_session_states(self, mock_ph):
        """stop() should transition running sessions correctly."""
        daemon = _make_daemon(self.tmpdir, TWO_SESSIONS)
        daemon.state.mark_started(pid=os.getpid())
        daemon.run_cycle()

        daemon.stop(kill_sessions=True)

        for s in daemon.registry.get_all_sessions():
            self.assertNotEqual(s.status, SessionStatus.RUNNING)


class TestRestartDelayRespected(unittest.TestCase):
    """Test that restart delays are enforced across cycles."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("session_daemon.peak_hours_get_status",
           return_value={"is_peak": False, "max_recommended_chats": 3})
    def test_crash_waits_for_delay(self, mock_ph):
        """After crash, session waits restart_delay before respawning."""
        sessions = [
            {"id": "cca-desktop", "type": "cca", "role": "desktop",
             "command": "claude", "restart_delay_seconds": 300},
        ]
        daemon = _make_daemon(self.tmpdir, sessions)

        daemon.run_cycle()  # Spawn

        # Crash it
        daemon.tmux.is_alive = MagicMock(return_value=False)
        daemon.run_cycle()  # Detect crash

        cca = daemon.registry._sessions["cca-desktop"]
        # With 300s delay, should be CRASHED (not respawned yet)
        self.assertEqual(cca.status, SessionStatus.CRASHED)

    @patch("session_daemon.peak_hours_get_status",
           return_value={"is_peak": False, "max_recommended_chats": 3})
    def test_expired_delay_allows_respawn(self, mock_ph):
        """After delay expires, crashed sessions respawn on next cycle."""
        sessions = [
            {"id": "cca-desktop", "type": "cca", "role": "desktop",
             "command": "claude", "restart_delay_seconds": 10},
        ]
        daemon = _make_daemon(self.tmpdir, sessions)

        daemon.run_cycle()  # Spawn

        daemon.tmux.is_alive = MagicMock(return_value=False)
        daemon.run_cycle()  # Detect crash (delay not elapsed)

        cca = daemon.registry._sessions["cca-desktop"]
        self.assertEqual(cca.status, SessionStatus.CRASHED)

        # Expire delay
        _expire_restart_delays(daemon)
        daemon.run_cycle()  # Respawn

        self.assertEqual(cca.status, SessionStatus.RUNNING)
        self.assertEqual(cca.restart_count, 1)

    @patch("session_daemon.peak_hours_get_status",
           return_value={"is_peak": False, "max_recommended_chats": 3})
    def test_delay_elapsed_allows_respawn(self, mock_ph):
        """After delay elapses, crashed session can respawn."""
        sessions = [
            {"id": "cca-desktop", "type": "cca", "role": "desktop",
             "command": "claude", "restart_delay_seconds": 10},
        ]
        daemon = _make_daemon(self.tmpdir, sessions)

        daemon.run_cycle()  # Spawn

        daemon.tmux.is_alive = MagicMock(return_value=False)
        daemon.run_cycle()  # Detect crash (not respawned — delay=10s)

        cca = daemon.registry._sessions["cca-desktop"]
        self.assertEqual(cca.status, SessionStatus.CRASHED)

        # Simulate delay elapsed by backdating stopped_at
        cca.stopped_at = time.time() - 20
        daemon.run_cycle()

        self.assertEqual(cca.status, SessionStatus.RUNNING)
        self.assertEqual(cca.restart_count, 1)


class TestAuditLogCompleteness(unittest.TestCase):
    """Verify audit log captures all important events."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("session_daemon.peak_hours_get_status",
           return_value={"is_peak": False, "max_recommended_chats": 3})
    def test_all_events_have_timestamps(self, mock_ph):
        """Every audit log entry must have a timestamp."""
        daemon = _make_daemon(self.tmpdir, TWO_SESSIONS)
        daemon.run_cycle()

        entries = _read_audit_log(self.tmpdir)
        for entry in entries:
            self.assertIn("ts", entry)
            self.assertIsInstance(entry["ts"], str)

    @patch("session_daemon.peak_hours_get_status",
           return_value={"is_peak": False, "max_recommended_chats": 3})
    def test_spawn_events_have_session_id(self, mock_ph):
        """Spawn events must identify the session."""
        daemon = _make_daemon(self.tmpdir, TWO_SESSIONS)
        daemon.run_cycle()

        entries = _read_audit_log(self.tmpdir)
        spawns = [e for e in entries if e["event"] == "session_spawned"]
        self.assertEqual(len(spawns), 2)
        for spawn in spawns:
            self.assertIn("session", spawn["data"])

    @patch("session_daemon.peak_hours_get_status",
           return_value={"is_peak": False, "max_recommended_chats": 3})
    def test_exhausted_restarts_stay_crashed(self, mock_ph):
        """After exhausting restarts, session stays CRASHED and is not respawned."""
        daemon = _make_daemon(self.tmpdir,
                              [{"id": "cca-desktop", "type": "cca",
                                "role": "desktop", "command": "claude",
                                "restart_delay_seconds": 10}],
                              max_restarts=1)

        daemon.run_cycle()  # Spawn

        # Crash once -> detect + expire delay -> respawn (uses 1 restart)
        daemon.tmux.is_alive = MagicMock(return_value=False)
        daemon.run_cycle()
        _expire_restart_delays(daemon)
        daemon.run_cycle()
        daemon.tmux.is_alive = MagicMock(return_value=True)

        # Crash again -> detect + expire delay -> no respawn (exhausted)
        daemon.tmux.is_alive = MagicMock(return_value=False)
        daemon.run_cycle()
        _expire_restart_delays(daemon)
        daemon.run_cycle()

        cca = daemon.registry._sessions["cca-desktop"]
        self.assertEqual(cca.status, SessionStatus.FAILED)

        # Verify audit trail shows crashes and the final FAILED event
        entries = _read_audit_log(self.tmpdir)
        events = [e["event"] for e in entries]
        crash_events = [e for e in entries if e["event"] == "session_crashed"]
        self.assertEqual(len(crash_events), 2)
        self.assertIn("session_failed", events)

    @patch("session_daemon.peak_hours_get_status",
           return_value={"is_peak": False, "max_recommended_chats": 3})
    def test_audit_log_valid_jsonl(self, mock_ph):
        """Every line in the audit log should be valid JSON."""
        daemon = _make_daemon(self.tmpdir, TWO_SESSIONS)
        daemon.run_cycle()

        # Crash one to generate more events
        daemon.tmux.is_alive = MagicMock(return_value=False)
        daemon.run_cycle()

        log_path = os.path.join(self.tmpdir, "daemon.log")
        with open(log_path) as f:
            for i, line in enumerate(f):
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    self.fail(f"Line {i+1} is not valid JSON: {line}")
                self.assertIn("event", entry)
                self.assertIn("ts", entry)


class TestPIDFileSingleton(unittest.TestCase):
    """Test PID file enforcement across daemon instances."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_second_daemon_blocked_by_pid(self):
        """Second daemon instance should fail to acquire PID."""
        daemon1 = _make_daemon(self.tmpdir, TWO_SESSIONS)
        self.assertTrue(daemon1.acquire_pid_file())

        daemon2 = _make_daemon(self.tmpdir, TWO_SESSIONS)
        daemon2._pid_path = daemon1._pid_path  # Same PID file
        self.assertFalse(daemon2.acquire_pid_file())

        daemon1.release_pid_file()

    def test_stale_pid_cleaned_up(self):
        """Stale PID file (dead process) should be cleaned up."""
        pid_path = os.path.join(self.tmpdir, "daemon.pid")
        # Write a PID that doesn't exist
        with open(pid_path, "w") as f:
            f.write("999999999")

        daemon = _make_daemon(self.tmpdir, TWO_SESSIONS)
        daemon._pid_path = pid_path
        self.assertTrue(daemon.acquire_pid_file())
        daemon.release_pid_file()


class TestMultiCycleDaemon(unittest.TestCase):
    """Test daemon behavior across many cycles."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("session_daemon.peak_hours_get_status",
           return_value={"is_peak": False, "max_recommended_chats": 3})
    def test_stable_sessions_stay_running(self, mock_ph):
        """If no crashes, sessions stay running across many cycles."""
        daemon = _make_daemon(self.tmpdir, TWO_SESSIONS)

        daemon.run_cycle()  # Initial spawn

        # Run 5 more cycles with stable sessions
        for _ in range(5):
            daemon.run_cycle()

        running = daemon.registry.get_running_sessions()
        self.assertEqual(len(running), 2)
        # No additional spawns beyond initial 2
        self.assertEqual(daemon.state.total_spawns, 2)
        self.assertEqual(daemon.state.total_crashes, 0)

    @patch("session_daemon.peak_hours_get_status",
           return_value={"is_peak": False, "max_recommended_chats": 3})
    def test_multiple_sessions_crash_independently(self, mock_ph):
        """Each session's crash state is tracked independently."""
        daemon = _make_daemon(self.tmpdir, TWO_SESSIONS)
        daemon.run_cycle()

        # Crash only cca-desktop
        def only_kalshi_alive(name):
            return name == "kalshi-main"
        daemon.tmux.is_alive = MagicMock(side_effect=only_kalshi_alive)
        daemon.run_cycle()  # Detect crash

        # Expire delay, respawn
        _expire_restart_delays(daemon)
        daemon.tmux.is_alive = MagicMock(side_effect=only_kalshi_alive)
        daemon.run_cycle()

        cca = daemon.registry._sessions["cca-desktop"]
        kalshi = daemon.registry._sessions["kalshi-main"]
        self.assertEqual(cca.restart_count, 1)
        self.assertEqual(kalshi.restart_count, 0)

    @patch("session_daemon.peak_hours_get_status")
    def test_peak_to_offpeak_full_cycle(self, mock_ph):
        """Full peak transition: spawn -> peak deprioritize -> offpeak restore."""
        mock_ph.return_value = {"is_peak": False, "max_recommended_chats": 3}
        daemon = _make_daemon(self.tmpdir, THREE_SESSIONS,
                              peak_deprioritize=["kalshi-research"])

        # Cycle 1: spawn all 3
        daemon.run_cycle()
        self.assertEqual(len(daemon.registry.get_running_sessions()), 3)

        # Cycle 2: peak hits, research deprioritized
        mock_ph.return_value = {"is_peak": True, "max_recommended_chats": 2}
        daemon.run_cycle()
        self.assertEqual(len(daemon.registry.get_running_sessions()), 2)

        # Cycle 3: still peak, no change
        daemon.run_cycle()
        self.assertEqual(len(daemon.registry.get_running_sessions()), 2)

        # Cycle 4: off-peak, research restored
        mock_ph.return_value = {"is_peak": False, "max_recommended_chats": 3}
        daemon.run_cycle()

        research = daemon.registry._sessions["kalshi-research"]
        # Should be back in some restartable state
        self.assertNotEqual(research.status, SessionStatus.DEPRIORITIZED)


if __name__ == "__main__":
    unittest.main()
