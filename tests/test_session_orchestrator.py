#!/usr/bin/env python3
"""Tests for session_orchestrator.py — 3-chat auto-launch decision logic."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from session_orchestrator import (
    SessionMode,
    SessionState,
    detect_running_sessions,
    decide_launches,
    LaunchDecision,
    build_launch_commands,
    load_session_preference,
    save_session_preference,
)


class TestSessionMode(unittest.TestCase):
    """SessionMode enum."""

    def test_solo_mode(self):
        self.assertEqual(SessionMode.SOLO.value, "solo")

    def test_two_chat_mode(self):
        self.assertEqual(SessionMode.TWO_CHAT.value, "2chat")

    def test_three_chat_mode(self):
        self.assertEqual(SessionMode.THREE_CHAT.value, "3chat")


class TestSessionState(unittest.TestCase):
    """SessionState detection from process list."""

    def test_empty_processes(self):
        state = detect_running_sessions([])
        self.assertFalse(state.desktop_running)
        self.assertFalse(state.worker_running)
        self.assertFalse(state.kalshi_running)

    def test_desktop_only(self):
        procs = [{"pid": 100, "chat_id": "desktop", "command": "claude"}]
        state = detect_running_sessions(procs)
        self.assertTrue(state.desktop_running)
        self.assertFalse(state.worker_running)
        self.assertFalse(state.kalshi_running)

    def test_worker_detected(self):
        procs = [
            {"pid": 100, "chat_id": "desktop", "command": "claude"},
            {"pid": 200, "chat_id": "cli1", "command": "claude"},
        ]
        state = detect_running_sessions(procs)
        self.assertTrue(state.desktop_running)
        self.assertTrue(state.worker_running)

    def test_kalshi_detected_by_path(self):
        procs = [
            {"pid": 100, "chat_id": "desktop", "command": "claude"},
            {"pid": 300, "chat_id": None, "command": "claude", "project": "polymarket-bot"},
        ]
        state = detect_running_sessions(procs)
        self.assertTrue(state.kalshi_running)

    def test_full_3chat(self):
        procs = [
            {"pid": 100, "chat_id": "desktop", "command": "claude"},
            {"pid": 200, "chat_id": "cli1", "command": "claude"},
            {"pid": 300, "chat_id": None, "command": "claude", "project": "polymarket-bot"},
        ]
        state = detect_running_sessions(procs)
        self.assertTrue(state.desktop_running)
        self.assertTrue(state.worker_running)
        self.assertTrue(state.kalshi_running)
        self.assertEqual(state.mode, SessionMode.THREE_CHAT)

    def test_mode_solo_when_desktop_only(self):
        procs = [{"pid": 100, "chat_id": "desktop", "command": "claude"}]
        state = detect_running_sessions(procs)
        self.assertEqual(state.mode, SessionMode.SOLO)

    def test_mode_2chat_with_worker(self):
        procs = [
            {"pid": 100, "chat_id": "desktop", "command": "claude"},
            {"pid": 200, "chat_id": "cli1", "command": "claude"},
        ]
        state = detect_running_sessions(procs)
        self.assertEqual(state.mode, SessionMode.TWO_CHAT)


class TestDecideLaunches(unittest.TestCase):
    """Launch decisions based on current state and target mode."""

    def test_solo_target_no_launches(self):
        state = SessionState(desktop_running=True)
        decisions = decide_launches(state, target=SessionMode.SOLO)
        self.assertEqual(len(decisions), 0)

    def test_2chat_target_launches_worker(self):
        state = SessionState(desktop_running=True)
        decisions = decide_launches(state, target=SessionMode.TWO_CHAT)
        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0].target, "worker")

    def test_3chat_target_launches_both(self):
        state = SessionState(desktop_running=True)
        decisions = decide_launches(state, target=SessionMode.THREE_CHAT)
        self.assertEqual(len(decisions), 2)
        targets = {d.target for d in decisions}
        self.assertEqual(targets, {"worker", "kalshi"})

    def test_3chat_worker_already_running(self):
        state = SessionState(desktop_running=True, worker_running=True)
        decisions = decide_launches(state, target=SessionMode.THREE_CHAT)
        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0].target, "kalshi")

    def test_3chat_kalshi_already_running(self):
        state = SessionState(desktop_running=True, kalshi_running=True)
        decisions = decide_launches(state, target=SessionMode.THREE_CHAT)
        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0].target, "worker")

    def test_3chat_all_running_no_launches(self):
        state = SessionState(
            desktop_running=True, worker_running=True, kalshi_running=True
        )
        decisions = decide_launches(state, target=SessionMode.THREE_CHAT)
        self.assertEqual(len(decisions), 0)

    def test_peak_hours_blocks_worker(self):
        state = SessionState(desktop_running=True)
        decisions = decide_launches(
            state, target=SessionMode.TWO_CHAT, is_peak=True
        )
        self.assertEqual(len(decisions), 1)
        self.assertTrue(decisions[0].blocked)
        self.assertIn("peak", decisions[0].reason.lower())

    def test_peak_hours_blocks_kalshi(self):
        state = SessionState(desktop_running=True)
        decisions = decide_launches(
            state, target=SessionMode.THREE_CHAT, is_peak=True
        )
        for d in decisions:
            self.assertTrue(d.blocked)

    def test_no_desktop_blocks_all(self):
        """Can't launch helpers without desktop running."""
        state = SessionState(desktop_running=False)
        decisions = decide_launches(state, target=SessionMode.THREE_CHAT)
        self.assertEqual(len(decisions), 0)


class TestBuildLaunchCommands(unittest.TestCase):
    """Convert decisions into shell commands."""

    def test_worker_command(self):
        decision = LaunchDecision(target="worker", blocked=False)
        cmd = build_launch_commands([decision], worker_task="build feature X")
        self.assertIn("launch_worker.sh", cmd[0])
        self.assertIn("build feature X", cmd[0])

    def test_kalshi_command(self):
        decision = LaunchDecision(target="kalshi", blocked=False)
        cmd = build_launch_commands([decision])
        self.assertIn("launch_kalshi.sh", cmd[0])

    def test_blocked_decisions_excluded(self):
        decision = LaunchDecision(target="worker", blocked=True, reason="peak hours")
        cmd = build_launch_commands([decision])
        self.assertEqual(len(cmd), 0)

    def test_both_commands(self):
        decisions = [
            LaunchDecision(target="worker", blocked=False),
            LaunchDecision(target="kalshi", blocked=False),
        ]
        cmds = build_launch_commands(decisions, worker_task="task")
        self.assertEqual(len(cmds), 2)

    def test_empty_worker_task(self):
        decision = LaunchDecision(target="worker", blocked=False)
        cmd = build_launch_commands([decision])
        self.assertIn("launch_worker.sh", cmd[0])
        # No task arg when task is empty
        self.assertNotIn('""', cmd[0])


class TestSessionPreference(unittest.TestCase):
    """Persist target mode preference."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.pref_file = os.path.join(self.tmpdir, "session_preference.json")

    def test_save_and_load(self):
        save_session_preference(SessionMode.THREE_CHAT, self.pref_file)
        mode = load_session_preference(self.pref_file)
        self.assertEqual(mode, SessionMode.THREE_CHAT)

    def test_default_solo(self):
        mode = load_session_preference("/nonexistent/path.json")
        self.assertEqual(mode, SessionMode.SOLO)

    def test_overwrite(self):
        save_session_preference(SessionMode.TWO_CHAT, self.pref_file)
        save_session_preference(SessionMode.THREE_CHAT, self.pref_file)
        mode = load_session_preference(self.pref_file)
        self.assertEqual(mode, SessionMode.THREE_CHAT)


class TestLaunchDecision(unittest.TestCase):
    """LaunchDecision dataclass."""

    def test_default_not_blocked(self):
        d = LaunchDecision(target="worker")
        self.assertFalse(d.blocked)
        self.assertEqual(d.reason, "")

    def test_blocked_with_reason(self):
        d = LaunchDecision(target="kalshi", blocked=True, reason="peak hours")
        self.assertTrue(d.blocked)
        self.assertEqual(d.reason, "peak hours")


if __name__ == "__main__":
    unittest.main()
