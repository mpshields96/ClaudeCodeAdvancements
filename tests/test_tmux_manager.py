#!/usr/bin/env python3
"""Tests for tmux_manager.py — MT-30 Phase 2.

Tests use mocked subprocess calls to avoid requiring a live tmux session.
Integration tests that need real tmux are skipped if tmux is not available.
"""

import os
import subprocess
import sys
import unittest
from unittest.mock import patch, MagicMock, call

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tmux_manager import TmuxManager, TmuxError, WindowInfo


def _mock_result(stdout="", stderr="", returncode=0):
    """Create a mock CompletedProcess."""
    result = MagicMock(spec=subprocess.CompletedProcess)
    result.stdout = stdout
    result.stderr = stderr
    result.returncode = returncode
    return result


class TestTmuxAvailability(unittest.TestCase):
    """Test tmux availability detection."""

    @patch("tmux_manager.shutil.which", return_value="/usr/bin/tmux")
    def test_tmux_available(self, _):
        mgr = TmuxManager()
        self.assertTrue(mgr.is_tmux_available())

    @patch("tmux_manager.shutil.which", return_value=None)
    def test_tmux_not_available(self, _):
        mgr = TmuxManager()
        self.assertFalse(mgr.is_tmux_available())

    @patch("tmux_manager.shutil.which", return_value=None)
    def test_run_tmux_raises_when_not_available(self, _):
        mgr = TmuxManager()
        with self.assertRaises(TmuxError) as ctx:
            mgr._run_tmux(["list-sessions"])
        self.assertIn("not installed", str(ctx.exception))


class TestSessionManagement(unittest.TestCase):
    """Test tmux session create/check/destroy."""

    def setUp(self):
        self.mgr = TmuxManager("test-workspace")
        self.mgr._tmux_path = "/usr/bin/tmux"

    @patch("tmux_manager.subprocess.run")
    def test_session_exists_true(self, mock_run):
        mock_run.return_value = _mock_result(returncode=0)
        self.assertTrue(self.mgr.session_exists())
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertIn("has-session", args)
        self.assertIn("test-workspace", args)

    @patch("tmux_manager.subprocess.run")
    def test_session_exists_false(self, mock_run):
        mock_run.return_value = _mock_result(returncode=1, stderr="no session")
        self.assertFalse(self.mgr.session_exists())

    @patch("tmux_manager.subprocess.run")
    def test_create_session_new(self, mock_run):
        # First call: has-session (doesn't exist)
        # Second call: new-session (creates)
        mock_run.side_effect = [
            _mock_result(returncode=1),  # has-session fails
            _mock_result(returncode=0),  # new-session succeeds
        ]
        result = self.mgr.create_session()
        self.assertTrue(result)
        self.assertEqual(mock_run.call_count, 2)

    @patch("tmux_manager.subprocess.run")
    def test_create_session_already_exists(self, mock_run):
        mock_run.return_value = _mock_result(returncode=0)  # has-session succeeds
        result = self.mgr.create_session()
        self.assertFalse(result)

    @patch("tmux_manager.subprocess.run")
    def test_destroy_session(self, mock_run):
        mock_run.side_effect = [
            _mock_result(returncode=0),                          # has-session (session_exists)
            _mock_result(returncode=0),                          # has-session (list_windows -> session_exists)
            _mock_result(stdout="daemon\t100\t0\t0\t1\n"),       # list-windows (only daemon)
            _mock_result(returncode=0),                          # kill-session
        ]
        result = self.mgr.destroy_session()
        self.assertTrue(result)

    @patch("tmux_manager.subprocess.run")
    def test_destroy_nonexistent_session(self, mock_run):
        mock_run.return_value = _mock_result(returncode=1)  # has-session fails
        result = self.mgr.destroy_session()
        self.assertFalse(result)

    @patch("tmux_manager.subprocess.run")
    def test_destroy_with_active_windows_raises(self, mock_run):
        mock_run.side_effect = [
            _mock_result(returncode=0),                                          # has-session (session_exists)
            _mock_result(returncode=0),                                          # has-session (list_windows -> session_exists)
            _mock_result(stdout="daemon\t100\t0\t0\t1\ncca-desktop\t200\t0\t1\t0\n"),  # list-windows (tab-delimited)
        ]
        with self.assertRaises(TmuxError) as ctx:
            self.mgr.destroy_session(force=False)
        self.assertIn("active windows", str(ctx.exception))

    @patch("tmux_manager.subprocess.run")
    def test_destroy_force_ignores_active(self, mock_run):
        mock_run.side_effect = [
            _mock_result(returncode=0),  # has-session
            _mock_result(returncode=0),  # kill-session
        ]
        result = self.mgr.destroy_session(force=True)
        self.assertTrue(result)


class TestWindowManagement(unittest.TestCase):
    """Test window create/check/kill operations."""

    def setUp(self):
        self.mgr = TmuxManager("test-workspace")
        self.mgr._tmux_path = "/usr/bin/tmux"

    @patch("tmux_manager.subprocess.run")
    def test_window_exists_true(self, mock_run):
        mock_run.side_effect = [
            _mock_result(returncode=0),              # has-session
            _mock_result(stdout="daemon\ncca-desktop\n"),  # list-windows
        ]
        self.assertTrue(self.mgr.window_exists("cca-desktop"))

    @patch("tmux_manager.subprocess.run")
    def test_window_exists_false(self, mock_run):
        mock_run.side_effect = [
            _mock_result(returncode=0),       # has-session
            _mock_result(stdout="daemon\n"),   # list-windows (no cca-desktop)
        ]
        self.assertFalse(self.mgr.window_exists("cca-desktop"))

    @patch("tmux_manager.subprocess.run")
    def test_window_exists_no_session(self, mock_run):
        mock_run.return_value = _mock_result(returncode=1)  # has-session fails
        self.assertFalse(self.mgr.window_exists("cca-desktop"))

    @patch("tmux_manager.subprocess.run")
    def test_create_window(self, mock_run):
        mock_run.side_effect = [
            _mock_result(returncode=0),              # has-session (exists)
            _mock_result(returncode=0),              # has-session for window_exists
            _mock_result(stdout="daemon\n"),          # list-windows (no existing window)
            _mock_result(returncode=0),              # new-window
            # get_pane_pid calls:
            _mock_result(returncode=0),              # has-session for window_exists
            _mock_result(stdout="daemon\ncca-desktop\n"),  # list-windows
            _mock_result(stdout="12345\n"),           # list-panes (pid)
        ]
        pid = self.mgr.create_window("cca-desktop", "claude /cca-init")
        self.assertEqual(pid, 12345)

    @patch("tmux_manager.subprocess.run")
    def test_create_window_already_exists_raises(self, mock_run):
        mock_run.side_effect = [
            _mock_result(returncode=0),                        # has-session
            _mock_result(returncode=0),                        # has-session for window_exists
            _mock_result(stdout="daemon\ncca-desktop\n"),      # list-windows (exists!)
        ]
        with self.assertRaises(TmuxError) as ctx:
            self.mgr.create_window("cca-desktop", "claude")
        self.assertIn("already exists", str(ctx.exception))

    @patch("tmux_manager.subprocess.run")
    def test_create_window_with_env(self, mock_run):
        mock_run.side_effect = [
            _mock_result(returncode=0),     # has-session
            _mock_result(returncode=0),     # has-session for window_exists
            _mock_result(stdout="daemon\n"),  # list-windows
            _mock_result(returncode=0),     # new-window
            _mock_result(returncode=0),     # has-session for window_exists
            _mock_result(stdout="daemon\nw1\n"),  # list-windows
            _mock_result(stdout="999\n"),   # list-panes
        ]
        pid = self.mgr.create_window("w1", "echo hi", env={"CCA_CHAT_ID": "desktop"})
        # Verify the command included env setup
        new_window_call = mock_run.call_args_list[3]
        cmd = new_window_call[0][0]
        cmd_str = " ".join(cmd)
        self.assertIn("CCA_CHAT_ID", cmd_str)
        self.assertIn("unset ANTHROPIC_API_KEY", cmd_str)

    @patch("tmux_manager.subprocess.run")
    def test_create_window_invalid_env_name_raises(self, mock_run):
        mock_run.side_effect = [
            _mock_result(returncode=0),     # has-session
            _mock_result(returncode=0),     # has-session for window_exists
            _mock_result(stdout="daemon\n"),  # list-windows
        ]
        with self.assertRaises(TmuxError) as ctx:
            self.mgr.create_window("w", "echo", env={"bad;name": "val"})
        self.assertIn("Invalid env var", str(ctx.exception))

    @patch("tmux_manager.subprocess.run")
    def test_kill_window(self, mock_run):
        mock_run.side_effect = [
            _mock_result(returncode=0),                        # has-session
            _mock_result(stdout="daemon\ncca-desktop\n"),      # list-windows
            _mock_result(returncode=0),                        # send-keys C-c
            _mock_result(returncode=0),                        # kill-window
        ]
        result = self.mgr.kill_window("cca-desktop")
        self.assertTrue(result)

    @patch("tmux_manager.subprocess.run")
    def test_kill_window_nonexistent(self, mock_run):
        mock_run.side_effect = [
            _mock_result(returncode=0),       # has-session
            _mock_result(stdout="daemon\n"),   # list-windows (no match)
        ]
        result = self.mgr.kill_window("nonexistent")
        self.assertFalse(result)

    @patch("tmux_manager.subprocess.run")
    def test_kill_window_not_graceful(self, mock_run):
        mock_run.side_effect = [
            _mock_result(returncode=0),                        # has-session
            _mock_result(stdout="daemon\ncca-desktop\n"),      # list-windows
            _mock_result(returncode=0),                        # kill-window (no send-keys)
        ]
        result = self.mgr.kill_window("cca-desktop", graceful=False)
        self.assertTrue(result)
        # Verify send-keys was NOT called
        cmds = [c[0][0] for c in mock_run.call_args_list]
        send_keys_calls = [c for c in cmds if "send-keys" in c]
        self.assertEqual(len(send_keys_calls), 0)


class TestPaneOperations(unittest.TestCase):
    """Test pane PID, alive check, capture."""

    def setUp(self):
        self.mgr = TmuxManager("test-workspace")
        self.mgr._tmux_path = "/usr/bin/tmux"

    @patch("tmux_manager.subprocess.run")
    def test_get_pane_pid(self, mock_run):
        mock_run.side_effect = [
            _mock_result(returncode=0),                        # has-session
            _mock_result(stdout="daemon\ncca-desktop\n"),      # list-windows
            _mock_result(stdout="54321\n"),                     # list-panes
        ]
        pid = self.mgr.get_pane_pid("cca-desktop")
        self.assertEqual(pid, 54321)

    @patch("tmux_manager.subprocess.run")
    def test_get_pane_pid_nonexistent(self, mock_run):
        mock_run.side_effect = [
            _mock_result(returncode=0),       # has-session
            _mock_result(stdout="daemon\n"),   # list-windows
        ]
        self.assertIsNone(self.mgr.get_pane_pid("nonexistent"))

    @patch("tmux_manager.subprocess.run")
    def test_is_alive_true(self, mock_run):
        mock_run.side_effect = [
            _mock_result(returncode=0),                   # has-session
            _mock_result(stdout="daemon\ncca-desktop\n"), # list-windows
            _mock_result(stdout="0\n"),                    # list-panes pane_dead=0
        ]
        self.assertTrue(self.mgr.is_alive("cca-desktop"))

    @patch("tmux_manager.subprocess.run")
    def test_is_alive_false_dead(self, mock_run):
        mock_run.side_effect = [
            _mock_result(returncode=0),                   # has-session
            _mock_result(stdout="daemon\ncca-desktop\n"), # list-windows
            _mock_result(stdout="1\n"),                    # list-panes pane_dead=1
        ]
        self.assertFalse(self.mgr.is_alive("cca-desktop"))

    @patch("tmux_manager.subprocess.run")
    def test_is_alive_false_no_window(self, mock_run):
        mock_run.side_effect = [
            _mock_result(returncode=0),       # has-session
            _mock_result(stdout="daemon\n"),   # list-windows
        ]
        self.assertFalse(self.mgr.is_alive("nonexistent"))

    @patch("tmux_manager.subprocess.run")
    def test_capture_pane(self, mock_run):
        mock_run.side_effect = [
            _mock_result(returncode=0),                   # has-session
            _mock_result(stdout="daemon\ncca-desktop\n"), # list-windows
            _mock_result(stdout="line 1\nline 2\nline 3\n"),  # capture-pane
        ]
        output = self.mgr.capture_pane("cca-desktop", lines=3)
        self.assertIn("line 1", output)
        self.assertIn("line 3", output)

    @patch("tmux_manager.subprocess.run")
    def test_capture_pane_nonexistent(self, mock_run):
        mock_run.side_effect = [
            _mock_result(returncode=0),       # has-session
            _mock_result(stdout="daemon\n"),   # list-windows
        ]
        self.assertIsNone(self.mgr.capture_pane("nonexistent"))

    @patch("tmux_manager.subprocess.run")
    def test_has_wrap_marker_true(self, mock_run):
        mock_run.side_effect = [
            _mock_result(returncode=0),                   # has-session
            _mock_result(stdout="daemon\ncca-desktop\n"), # list-windows
            _mock_result(stdout="stuff\nSESSION_WRAPPED\nmore\n"),  # capture-pane
        ]
        self.assertTrue(self.mgr.has_wrap_marker("cca-desktop"))

    @patch("tmux_manager.subprocess.run")
    def test_has_wrap_marker_false(self, mock_run):
        mock_run.side_effect = [
            _mock_result(returncode=0),                   # has-session
            _mock_result(stdout="daemon\ncca-desktop\n"), # list-windows
            _mock_result(stdout="just some output\n"),     # capture-pane
        ]
        self.assertFalse(self.mgr.has_wrap_marker("cca-desktop"))

    @patch("tmux_manager.subprocess.run")
    def test_get_exit_code(self, mock_run):
        mock_run.side_effect = [
            _mock_result(returncode=0),                   # has-session (window_exists)
            _mock_result(stdout="daemon\ncca-desktop\n"), # list-windows
            # is_alive check:
            _mock_result(returncode=0),                   # has-session
            _mock_result(stdout="daemon\ncca-desktop\n"), # list-windows
            _mock_result(stdout="1\n"),                    # pane_dead=1 (not alive)
            _mock_result(stdout="0\n"),                    # pane_dead_status
        ]
        exit_code = self.mgr.get_exit_code("cca-desktop")
        self.assertEqual(exit_code, 0)

    @patch("tmux_manager.subprocess.run")
    def test_get_exit_code_still_alive(self, mock_run):
        mock_run.side_effect = [
            _mock_result(returncode=0),                   # has-session
            _mock_result(stdout="daemon\ncca-desktop\n"), # list-windows
            # is_alive:
            _mock_result(returncode=0),                   # has-session
            _mock_result(stdout="daemon\ncca-desktop\n"), # list-windows
            _mock_result(stdout="0\n"),                    # pane_dead=0 (alive)
        ]
        self.assertIsNone(self.mgr.get_exit_code("cca-desktop"))


class TestListWindows(unittest.TestCase):
    """Test window listing."""

    def setUp(self):
        self.mgr = TmuxManager("test-workspace")
        self.mgr._tmux_path = "/usr/bin/tmux"

    @patch("tmux_manager.subprocess.run")
    def test_list_windows(self, mock_run):
        mock_run.side_effect = [
            _mock_result(returncode=0),  # has-session
            _mock_result(stdout="daemon\t100\t0\t0\t1\ncca-desktop\t200\t0\t1\t0\n"),
        ]
        windows = self.mgr.list_windows()
        self.assertEqual(len(windows), 2)
        self.assertEqual(windows[0].name, "daemon")
        self.assertEqual(windows[0].pane_pid, 100)
        self.assertFalse(windows[0].pane_dead)
        self.assertTrue(windows[0].active)
        self.assertEqual(windows[1].name, "cca-desktop")
        self.assertEqual(windows[1].pane_pid, 200)

    @patch("tmux_manager.subprocess.run")
    def test_list_windows_no_session(self, mock_run):
        mock_run.return_value = _mock_result(returncode=1)  # has-session fails
        windows = self.mgr.list_windows()
        self.assertEqual(windows, [])

    @patch("tmux_manager.subprocess.run")
    def test_list_windows_empty(self, mock_run):
        mock_run.side_effect = [
            _mock_result(returncode=0),  # has-session
            _mock_result(stdout=""),      # list-windows empty
        ]
        windows = self.mgr.list_windows()
        self.assertEqual(windows, [])


class TestSendKeys(unittest.TestCase):
    """Test keystroke sending."""

    def setUp(self):
        self.mgr = TmuxManager("test-workspace")
        self.mgr._tmux_path = "/usr/bin/tmux"

    @patch("tmux_manager.subprocess.run")
    def test_send_keys(self, mock_run):
        mock_run.side_effect = [
            _mock_result(returncode=0),                   # has-session
            _mock_result(stdout="daemon\ncca-desktop\n"), # list-windows
            _mock_result(returncode=0),                   # send-keys
        ]
        result = self.mgr.send_keys("cca-desktop", "/cca-auto")
        self.assertTrue(result)

    @patch("tmux_manager.subprocess.run")
    def test_send_keys_nonexistent(self, mock_run):
        mock_run.side_effect = [
            _mock_result(returncode=0),       # has-session
            _mock_result(stdout="daemon\n"),   # list-windows
        ]
        result = self.mgr.send_keys("nonexistent", "test")
        self.assertFalse(result)


class TestSummary(unittest.TestCase):
    """Test summary output."""

    def setUp(self):
        self.mgr = TmuxManager("test-workspace")
        self.mgr._tmux_path = "/usr/bin/tmux"

    @patch("tmux_manager.subprocess.run")
    def test_summary_with_session(self, mock_run):
        mock_run.side_effect = [
            _mock_result(returncode=0),  # has-session
            _mock_result(returncode=0),  # has-session for list_windows
            _mock_result(stdout="daemon\t100\t0\t0\t1\ncca-desktop\t200\t0\t1\t0\n"),
        ]
        summary = self.mgr.summary()
        self.assertIn("test-workspace", summary)
        self.assertIn("daemon", summary)
        self.assertIn("cca-desktop", summary)
        self.assertIn("ALIVE", summary)

    @patch("tmux_manager.subprocess.run")
    def test_summary_no_session(self, mock_run):
        mock_run.return_value = _mock_result(returncode=1)
        summary = self.mgr.summary()
        self.assertIn("does not exist", summary)


class TestTimeout(unittest.TestCase):
    """Test timeout handling."""

    def setUp(self):
        self.mgr = TmuxManager("test-workspace")
        self.mgr._tmux_path = "/usr/bin/tmux"

    @patch("tmux_manager.subprocess.run")
    def test_timeout_raises(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="tmux", timeout=10)
        with self.assertRaises(TmuxError) as ctx:
            self.mgr._run_tmux(["list-sessions"])
        self.assertIn("timed out", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
