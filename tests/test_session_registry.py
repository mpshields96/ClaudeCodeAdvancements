#!/usr/bin/env python3
"""Tests for session_registry.py — MT-30 Phase 2."""

import json
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from session_registry import (
    SessionConfig, SessionState, SessionStatus, SessionRegistry, RegistryError
)


def _make_config(**overrides):
    """Helper to create a SessionConfig with defaults."""
    defaults = {
        "id": "test-session",
        "type": "cca",
        "role": "desktop",
        "command": "claude /cca-init",
        "auto_restart": True,
        "restart_delay_seconds": 30,
        "priority": 1,
    }
    defaults.update(overrides)
    return SessionConfig(**defaults)


def _make_valid_config_dict(**overrides):
    """Helper to create a valid config dict."""
    config = {
        "version": 1,
        "max_total_chats": 3,
        "sessions": [
            {
                "id": "cca-desktop",
                "type": "cca",
                "role": "desktop",
                "command": "claude /cca-init",
                "priority": 1,
                "restart_delay_seconds": 30,
            },
            {
                "id": "kalshi-main",
                "type": "kalshi",
                "role": "main",
                "command": "claude /kalshi-main",
                "priority": 2,
                "restart_delay_seconds": 60,
            },
        ],
        "peak_hours": {
            "max_chats": 2,
            "deprioritize": ["kalshi-main"]
        }
    }
    config.update(overrides)
    return config


class TestSessionStatus(unittest.TestCase):
    """Test SessionStatus enum."""

    def test_all_statuses_exist(self):
        statuses = [s.value for s in SessionStatus]
        self.assertIn("pending", statuses)
        self.assertIn("running", statuses)
        self.assertIn("stopped", statuses)
        self.assertIn("crashed", statuses)
        self.assertIn("failed", statuses)
        self.assertIn("paused", statuses)
        self.assertIn("deprioritized", statuses)

    def test_status_from_string(self):
        self.assertEqual(SessionStatus("running"), SessionStatus.RUNNING)
        self.assertEqual(SessionStatus("crashed"), SessionStatus.CRASHED)


class TestSessionConfig(unittest.TestCase):
    """Test SessionConfig dataclass."""

    def test_defaults(self):
        config = SessionConfig(id="x", type="cca", role="desktop", command="claude")
        self.assertTrue(config.auto_restart)
        self.assertEqual(config.restart_delay_seconds, 30)
        self.assertEqual(config.priority, 99)
        self.assertEqual(config.env, {})
        self.assertIsNone(config.cwd)

    def test_custom_values(self):
        config = _make_config(priority=5, cwd="/tmp/test", env={"FOO": "bar"})
        self.assertEqual(config.priority, 5)
        self.assertEqual(config.cwd, "/tmp/test")
        self.assertEqual(config.env, {"FOO": "bar"})


class TestSessionState(unittest.TestCase):
    """Test SessionState lifecycle management."""

    def test_initial_state_is_pending(self):
        state = SessionState(config=_make_config())
        self.assertEqual(state.status, SessionStatus.PENDING)
        self.assertIsNone(state.pid)
        self.assertEqual(state.restart_count, 0)

    def test_mark_running(self):
        state = SessionState(config=_make_config())
        state.mark_running(pid=12345, tmux_window="cca-desktop")
        self.assertEqual(state.status, SessionStatus.RUNNING)
        self.assertEqual(state.pid, 12345)
        self.assertEqual(state.tmux_window, "cca-desktop")
        self.assertIsNotNone(state.started_at)
        self.assertIsNone(state.stopped_at)

    def test_mark_stopped(self):
        state = SessionState(config=_make_config())
        state.mark_running(pid=12345, tmux_window="w")
        state.mark_stopped("clean_wrap")
        self.assertEqual(state.status, SessionStatus.STOPPED)
        self.assertIsNone(state.pid)
        self.assertIsNotNone(state.stopped_at)
        self.assertEqual(state.last_error, "clean_wrap")

    def test_mark_crashed(self):
        state = SessionState(config=_make_config())
        state.mark_running(pid=12345, tmux_window="w")
        state.mark_crashed("segfault")
        self.assertEqual(state.status, SessionStatus.CRASHED)
        self.assertIsNone(state.pid)
        self.assertEqual(state.last_error, "segfault")

    def test_mark_failed(self):
        state = SessionState(config=_make_config())
        state.mark_failed("max_restarts_exceeded")
        self.assertEqual(state.status, SessionStatus.FAILED)
        self.assertEqual(state.last_error, "max_restarts_exceeded")

    def test_mark_paused(self):
        state = SessionState(config=_make_config())
        state.mark_paused()
        self.assertEqual(state.status, SessionStatus.PAUSED)

    def test_mark_deprioritized(self):
        state = SessionState(config=_make_config())
        state.mark_deprioritized()
        self.assertEqual(state.status, SessionStatus.DEPRIORITIZED)

    def test_uptime_when_running(self):
        state = SessionState(config=_make_config())
        state.mark_running(pid=1, tmux_window="w")
        state.started_at = time.time() - 120  # 2 minutes ago
        uptime = state.uptime_seconds()
        self.assertIsNotNone(uptime)
        self.assertGreaterEqual(uptime, 119)
        self.assertLessEqual(uptime, 125)

    def test_uptime_when_not_running(self):
        state = SessionState(config=_make_config())
        self.assertIsNone(state.uptime_seconds())

    def test_can_restart_default(self):
        state = SessionState(config=_make_config())
        self.assertTrue(state.can_restart())

    def test_can_restart_false_when_auto_restart_disabled(self):
        config = _make_config(auto_restart=False)
        state = SessionState(config=config)
        self.assertFalse(state.can_restart())

    def test_can_restart_false_when_failed(self):
        state = SessionState(config=_make_config())
        state.mark_failed()
        self.assertFalse(state.can_restart())

    def test_can_restart_false_when_paused(self):
        state = SessionState(config=_make_config())
        state.mark_paused()
        self.assertFalse(state.can_restart())

    def test_can_restart_respects_hourly_limit(self):
        state = SessionState(config=_make_config())
        now = time.time()
        # Add 5 recent restarts
        state.restart_timestamps = [now - i for i in range(5)]
        self.assertFalse(state.can_restart(max_restarts_per_hour=5))

    def test_can_restart_old_timestamps_expire(self):
        state = SessionState(config=_make_config())
        # All timestamps are > 1 hour old
        state.restart_timestamps = [time.time() - 7200] * 10
        self.assertTrue(state.can_restart(max_restarts_per_hour=5))

    def test_record_restart(self):
        state = SessionState(config=_make_config())
        state.record_restart()
        self.assertEqual(state.restart_count, 1)
        self.assertEqual(len(state.restart_timestamps), 1)
        state.record_restart()
        self.assertEqual(state.restart_count, 2)
        self.assertEqual(len(state.restart_timestamps), 2)

    def test_to_dict(self):
        state = SessionState(config=_make_config(id="test-1"))
        state.mark_running(pid=999, tmux_window="w1")
        d = state.to_dict()
        self.assertEqual(d["session_id"], "test-1")
        self.assertEqual(d["status"], "running")
        self.assertEqual(d["pid"], 999)
        self.assertEqual(d["tmux_window"], "w1")


class TestRegistryValidation(unittest.TestCase):
    """Test config validation."""

    def test_valid_config(self):
        errors = SessionRegistry.validate_config(_make_valid_config_dict())
        self.assertEqual(errors, [])

    def test_missing_version(self):
        config = _make_valid_config_dict()
        del config["version"]
        errors = SessionRegistry.validate_config(config)
        self.assertTrue(any("version" in e for e in errors))

    def test_wrong_version(self):
        errors = SessionRegistry.validate_config(_make_valid_config_dict(version=99))
        self.assertTrue(any("version" in e.lower() for e in errors))

    def test_max_chats_too_high(self):
        errors = SessionRegistry.validate_config(_make_valid_config_dict(max_total_chats=10))
        self.assertTrue(any("safety limit" in e for e in errors))

    def test_max_chats_negative(self):
        errors = SessionRegistry.validate_config(_make_valid_config_dict(max_total_chats=-1))
        self.assertTrue(any("positive integer" in e for e in errors))

    def test_duplicate_session_ids(self):
        config = _make_valid_config_dict()
        config["sessions"][1]["id"] = "cca-desktop"  # duplicate
        errors = SessionRegistry.validate_config(config)
        self.assertTrue(any("Duplicate session id" in e for e in errors))

    def test_duplicate_priorities(self):
        config = _make_valid_config_dict()
        config["sessions"][1]["priority"] = 1  # same as session 0
        errors = SessionRegistry.validate_config(config)
        self.assertTrue(any("Duplicate priority" in e for e in errors))

    def test_missing_command(self):
        config = _make_valid_config_dict()
        del config["sessions"][0]["command"]
        errors = SessionRegistry.validate_config(config)
        self.assertTrue(any("command" in e for e in errors))

    def test_restart_delay_too_low(self):
        config = _make_valid_config_dict()
        config["sessions"][0]["restart_delay_seconds"] = 5
        errors = SessionRegistry.validate_config(config)
        self.assertTrue(any("too low" in e for e in errors))

    def test_too_many_sessions(self):
        config = _make_valid_config_dict(max_total_chats=1)
        errors = SessionRegistry.validate_config(config)
        self.assertTrue(any("sessions configured" in e for e in errors))

    def test_peak_max_exceeds_total(self):
        config = _make_valid_config_dict()
        config["peak_hours"]["max_chats"] = 5
        errors = SessionRegistry.validate_config(config)
        self.assertTrue(any("peak_hours.max_chats" in e for e in errors))

    def test_peak_deprioritize_unknown_session(self):
        config = _make_valid_config_dict()
        config["peak_hours"]["deprioritize"] = ["nonexistent"]
        errors = SessionRegistry.validate_config(config)
        self.assertTrue(any("nonexistent" in e for e in errors))

    def test_not_a_dict(self):
        errors = SessionRegistry.validate_config("not a dict")
        self.assertTrue(any("JSON object" in e for e in errors))

    def test_invalid_env(self):
        config = _make_valid_config_dict()
        config["sessions"][0]["env"] = "not a dict"
        errors = SessionRegistry.validate_config(config)
        self.assertTrue(any("env" in e for e in errors))


class TestRegistryLoadSave(unittest.TestCase):
    """Test config loading and state persistence."""

    def test_load_from_file(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(_make_valid_config_dict(), f)
            path = f.name
        try:
            registry = SessionRegistry(path)
            self.assertEqual(registry.max_total_chats, 3)
            sessions = registry.get_all_sessions()
            self.assertEqual(len(sessions), 2)
            self.assertEqual(sessions[0].config.id, "cca-desktop")
            self.assertEqual(sessions[1].config.id, "kalshi-main")
        finally:
            os.unlink(path)

    def test_load_nonexistent_raises(self):
        with self.assertRaises(RegistryError):
            SessionRegistry("/nonexistent/path.json")

    def test_load_invalid_json_raises(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{bad json")
            path = f.name
        try:
            with self.assertRaises(RegistryError):
                SessionRegistry(path)
        finally:
            os.unlink(path)

    def test_no_config_path_uses_defaults(self):
        registry = SessionRegistry()
        self.assertEqual(registry.max_total_chats, 3)
        self.assertEqual(len(registry.get_all_sessions()), 0)

    def test_save_and_load_state(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(_make_valid_config_dict(), f)
            config_path = f.name

        state_path = config_path + ".state"
        try:
            # Create and modify state
            reg1 = SessionRegistry(config_path)
            s = reg1.get_session("cca-desktop")
            s.mark_running(pid=12345, tmux_window="w1")
            s.record_restart()
            reg1.save_state(state_path)

            # Load into new registry
            reg2 = SessionRegistry(config_path)
            reg2.load_state(state_path)
            s2 = reg2.get_session("cca-desktop")
            self.assertEqual(s2.status, SessionStatus.RUNNING)
            self.assertEqual(s2.pid, 12345)
            self.assertEqual(s2.restart_count, 1)
        finally:
            os.unlink(config_path)
            if os.path.exists(state_path):
                os.unlink(state_path)

    def test_load_state_nonexistent_returns_false(self):
        registry = SessionRegistry()
        self.assertFalse(registry.load_state("/nonexistent/state.json"))


class TestRegistryOperations(unittest.TestCase):
    """Test registry session management operations."""

    def _make_registry(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(_make_valid_config_dict(), f)
            self._config_path = f.name
        return SessionRegistry(self._config_path)

    def tearDown(self):
        if hasattr(self, '_config_path') and os.path.exists(self._config_path):
            os.unlink(self._config_path)

    def test_get_session(self):
        reg = self._make_registry()
        s = reg.get_session("cca-desktop")
        self.assertIsNotNone(s)
        self.assertEqual(s.config.command, "claude /cca-init")

    def test_get_session_nonexistent(self):
        reg = self._make_registry()
        self.assertIsNone(reg.get_session("nonexistent"))

    def test_get_all_sessions_sorted_by_priority(self):
        reg = self._make_registry()
        sessions = reg.get_all_sessions()
        self.assertEqual(sessions[0].config.id, "cca-desktop")  # priority 1
        self.assertEqual(sessions[1].config.id, "kalshi-main")  # priority 2

    def test_get_running_sessions(self):
        reg = self._make_registry()
        self.assertEqual(len(reg.get_running_sessions()), 0)
        reg.get_session("cca-desktop").mark_running(1, "w")
        self.assertEqual(len(reg.get_running_sessions()), 1)

    def test_get_runnable_sessions_all_pending(self):
        reg = self._make_registry()
        runnable = reg.get_runnable_sessions()
        self.assertEqual(len(runnable), 2)

    def test_get_runnable_sessions_respects_max(self):
        reg = self._make_registry()
        reg.get_session("cca-desktop").mark_running(1, "w")
        reg.get_session("kalshi-main").mark_running(2, "w")
        # At 2/3, still one slot
        runnable = reg.get_runnable_sessions()
        self.assertEqual(len(runnable), 0)  # no pending sessions left

    def test_get_runnable_sessions_peak_hours(self):
        reg = self._make_registry()
        # During peak, kalshi-main is deprioritized
        runnable = reg.get_runnable_sessions(is_peak=True)
        ids = [s.config.id for s in runnable]
        self.assertNotIn("kalshi-main", ids)
        self.assertIn("cca-desktop", ids)

    def test_get_runnable_sessions_peak_max_chats(self):
        reg = self._make_registry()
        reg.get_session("cca-desktop").mark_running(1, "w")
        reg.get_session("kalshi-main").mark_running(2, "w")
        # Peak max is 2, already at 2 — no more runnable
        runnable = reg.get_runnable_sessions(is_peak=True)
        self.assertEqual(len(runnable), 0)

    def test_get_deprioritizable(self):
        reg = self._make_registry()
        reg.get_session("kalshi-main").mark_running(1, "w")
        depri = reg.get_deprioritizable(is_peak=True)
        self.assertEqual(len(depri), 1)
        self.assertEqual(depri[0].config.id, "kalshi-main")

    def test_get_deprioritizable_not_peak(self):
        reg = self._make_registry()
        reg.get_session("kalshi-main").mark_running(1, "w")
        self.assertEqual(len(reg.get_deprioritizable(is_peak=False)), 0)

    def test_add_session(self):
        reg = self._make_registry()
        config = _make_config(id="new-session", priority=3)
        state = reg.add_session(config)
        self.assertEqual(state.status, SessionStatus.PENDING)
        self.assertEqual(len(reg.get_all_sessions()), 3)

    def test_add_duplicate_raises(self):
        reg = self._make_registry()
        config = _make_config(id="cca-desktop")
        with self.assertRaises(RegistryError):
            reg.add_session(config)

    def test_remove_session(self):
        reg = self._make_registry()
        self.assertTrue(reg.remove_session("kalshi-main"))
        self.assertEqual(len(reg.get_all_sessions()), 1)

    def test_remove_nonexistent(self):
        reg = self._make_registry()
        self.assertFalse(reg.remove_session("nonexistent"))

    def test_remove_running_raises(self):
        reg = self._make_registry()
        reg.get_session("cca-desktop").mark_running(1, "w")
        with self.assertRaises(RegistryError):
            reg.remove_session("cca-desktop")

    def test_summary_output(self):
        reg = self._make_registry()
        reg.get_session("cca-desktop").mark_running(1, "w")
        summary = reg.summary()
        self.assertIn("cca-desktop", summary)
        self.assertIn("RUNNING", summary)
        self.assertIn("kalshi-main", summary)
        self.assertIn("PENDING", summary)

    def test_properties(self):
        reg = self._make_registry()
        self.assertEqual(reg.max_total_chats, 3)
        self.assertEqual(reg.max_restarts_per_hour, 5)
        self.assertEqual(reg.check_interval_seconds, 60)
        self.assertEqual(reg.peak_max_chats, 2)
        self.assertEqual(reg.peak_deprioritize, ["kalshi-main"])

    def test_crashed_session_is_runnable(self):
        reg = self._make_registry()
        reg.get_session("cca-desktop").mark_running(1, "w")
        reg.get_session("cca-desktop").mark_crashed("died")
        runnable = reg.get_runnable_sessions()
        ids = [s.config.id for s in runnable]
        self.assertIn("cca-desktop", ids)

    def test_failed_session_not_runnable(self):
        reg = self._make_registry()
        reg.get_session("cca-desktop").mark_failed()
        runnable = reg.get_runnable_sessions()
        ids = [s.config.id for s in runnable]
        self.assertNotIn("cca-desktop", ids)


if __name__ == "__main__":
    unittest.main()
