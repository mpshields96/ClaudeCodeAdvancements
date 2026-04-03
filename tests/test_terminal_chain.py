#!/usr/bin/env python3
"""
test_terminal_chain.py — Tests for terminal_chain.py (CLI session self-chaining).

terminal_chain.py is spawned by autoloop_trigger.py when a one-off CLI session
wraps. It waits for the parent claude process to exit, then launches
start_autoloop.sh to continue the work loop.
"""

import os
import sys
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock, call

sys.path.insert(0, str(Path(__file__).parent.parent))
import terminal_chain


PROJECT_DIR = "/Users/matthewshields/Projects/ClaudeCodeAdvancements"


class TestWaitForPid(unittest.TestCase):
    """wait_for_pid() returns True when PID exits within timeout."""

    def test_returns_true_immediately_for_dead_pid(self):
        """A PID that does not exist should return True immediately."""
        # Use a PID that definitely doesn't exist (high number)
        dead_pid = 999999999
        result = terminal_chain.wait_for_pid(dead_pid, timeout=2.0, poll_interval=0.1)
        self.assertTrue(result)

    def test_returns_false_on_timeout_for_live_pid(self):
        """A running PID should return False after timeout."""
        live_pid = os.getpid()  # ourselves — definitely alive
        result = terminal_chain.wait_for_pid(live_pid, timeout=0.3, poll_interval=0.1)
        self.assertFalse(result)

    def test_returns_true_when_process_exits(self):
        """Should return True when the watched process exits naturally.

        We use os.getpid() (ourselves) to test with a real PID, but mock
        os.kill to simulate the process dying after one poll cycle.
        """
        call_count = [0]
        real_kill = os.kill

        def fake_kill(pid, sig):
            call_count[0] += 1
            if call_count[0] >= 2:
                raise ProcessLookupError("fake exit")
            real_kill(os.getpid(), 0)  # first call: alive

        with patch("terminal_chain.os.kill", side_effect=fake_kill):
            result = terminal_chain.wait_for_pid(
                os.getpid(), timeout=5.0, poll_interval=0.01
            )
        self.assertTrue(result)


class TestLaunchAutoloop(unittest.TestCase):
    """launch_autoloop() spawns start_autoloop.sh."""

    def test_returns_false_if_script_missing(self):
        result = terminal_chain.launch_autoloop(
            autoloop_sh="/nonexistent/path/start_autoloop.sh",
            project_dir=PROJECT_DIR,
            dry_run=False,
        )
        self.assertFalse(result)

    def test_dry_run_returns_true_without_spawning(self):
        """Dry run must not call subprocess.Popen."""
        with patch("terminal_chain.subprocess") as mock_sp:
            result = terminal_chain.launch_autoloop(
                autoloop_sh="/fake/start_autoloop.sh",
                project_dir=PROJECT_DIR,
                dry_run=True,
            )
        self.assertTrue(result)
        mock_sp.Popen.assert_not_called()

    def test_spawns_popen_with_autoloop_sh(self):
        """Non-dry-run must call subprocess.Popen with start_autoloop.sh."""
        with patch("terminal_chain.os.path.exists", return_value=True), \
             patch("terminal_chain.subprocess") as mock_sp:
            mock_sp.Popen = MagicMock()
            result = terminal_chain.launch_autoloop(
                autoloop_sh="/fake/start_autoloop.sh",
                project_dir=PROJECT_DIR,
                dry_run=False,
            )
        self.assertTrue(result)
        mock_sp.Popen.assert_called_once()
        args, kwargs = mock_sp.Popen.call_args
        cmd = args[0] if args else kwargs.get("args", [])
        self.assertIn("/fake/start_autoloop.sh", " ".join(str(c) for c in cmd))

    def test_popen_detaches_from_parent(self):
        """Spawned process must use start_new_session=True to detach."""
        with patch("terminal_chain.os.path.exists", return_value=True), \
             patch("terminal_chain.subprocess") as mock_sp:
            mock_sp.Popen = MagicMock()
            terminal_chain.launch_autoloop(
                autoloop_sh="/fake/start_autoloop.sh",
                project_dir=PROJECT_DIR,
                dry_run=False,
            )
        args, kwargs = mock_sp.Popen.call_args
        self.assertTrue(kwargs.get("start_new_session", False))


class TestRunCLI(unittest.TestCase):
    """CLI entry point: terminal_chain.main(args)."""

    def test_dry_run_flag(self):
        """--dry-run flag should not spawn anything."""
        # Use a dead PID so wait_for_pid returns immediately
        dead_pid = 999999999
        with patch("terminal_chain.launch_autoloop") as mock_launch:
            mock_launch.return_value = True
            terminal_chain.main(["--pid", str(dead_pid), "--dry-run"])
        mock_launch.assert_called_once()
        _, kwargs = mock_launch.call_args
        self.assertTrue(kwargs.get("dry_run", False))

    def test_missing_pid_exits_nonzero(self):
        """Missing --pid must exit with error."""
        with self.assertRaises(SystemExit) as ctx:
            terminal_chain.main([])
        self.assertNotEqual(ctx.exception.code, 0)

    def test_invalid_pid_exits_nonzero(self):
        """Non-integer PID must exit with error."""
        with self.assertRaises(SystemExit) as ctx:
            terminal_chain.main(["--pid", "notanumber"])
        self.assertNotEqual(ctx.exception.code, 0)

    def test_status_flag(self):
        """--status flag must print state and exit 0."""
        with self.assertRaises(SystemExit) as ctx:
            terminal_chain.main(["--status"])
        self.assertEqual(ctx.exception.code, 0)

    def test_pid_with_dead_process_calls_launch(self):
        """When PID is already dead, launch_autoloop is called immediately."""
        dead_pid = 999999999
        with patch("terminal_chain.launch_autoloop") as mock_launch:
            mock_launch.return_value = True
            terminal_chain.main(["--pid", str(dead_pid)])
        mock_launch.assert_called_once()


class TestAutoloopTriggerIntegration(unittest.TestCase):
    """autoloop_trigger.py must call terminal_chain for one-off CLI sessions."""

    def setUp(self):
        self._orig_cli = os.environ.pop("CCA_AUTOLOOP_CLI", None)

    def tearDown(self):
        if self._orig_cli is not None:
            os.environ["CCA_AUTOLOOP_CLI"] = self._orig_cli
        else:
            os.environ.pop("CCA_AUTOLOOP_CLI", None)

    def test_is_one_off_cli_true_when_tty_and_no_outer_loop(self):
        """is_one_off_cli_mode() returns True when in terminal without outer loop."""
        import autoloop_trigger
        with patch("autoloop_trigger.sys") as mock_sys:
            mock_sys.stdout.isatty.return_value = True
            result = autoloop_trigger.is_one_off_cli_mode()
        self.assertTrue(result)

    def test_is_one_off_cli_false_when_outer_loop(self):
        """is_one_off_cli_mode() returns False when CCA_AUTOLOOP_CLI=1."""
        import autoloop_trigger
        os.environ["CCA_AUTOLOOP_CLI"] = "1"
        with patch("autoloop_trigger.sys") as mock_sys:
            mock_sys.stdout.isatty.return_value = True
            result = autoloop_trigger.is_one_off_cli_mode()
        self.assertFalse(result)

    def test_is_one_off_cli_false_when_not_tty(self):
        """is_one_off_cli_mode() returns False when not a TTY (Electron desktop)."""
        import autoloop_trigger
        with patch("autoloop_trigger.sys") as mock_sys:
            mock_sys.stdout.isatty.return_value = False
            result = autoloop_trigger.is_one_off_cli_mode()
        self.assertFalse(result)

    def test_chain_terminal_session_dry_run(self):
        """_chain_terminal_session(dry_run=True) returns True without spawning."""
        import autoloop_trigger
        with patch("autoloop_trigger.subprocess") as mock_sp:
            mock_sp.Popen = MagicMock()
            result = autoloop_trigger._chain_terminal_session(dry_run=True)
        self.assertTrue(result)
        mock_sp.Popen.assert_not_called()

    def test_chain_terminal_session_spawns_relay(self):
        """_chain_terminal_session() spawns terminal_chain.py with parent PID."""
        import autoloop_trigger
        with patch("autoloop_trigger.subprocess") as mock_sp:
            mock_sp.Popen = MagicMock()
            with patch("autoloop_trigger.os") as mock_os:
                mock_os.getppid.return_value = 42000
                mock_os.path = os.path  # preserve real path ops
                result = autoloop_trigger._chain_terminal_session(dry_run=False)
        self.assertTrue(result)
        mock_sp.Popen.assert_called_once()
        args, kwargs = mock_sp.Popen.call_args
        cmd = args[0] if args else []
        cmd_str = " ".join(str(c) for c in cmd)
        self.assertIn("terminal_chain", cmd_str)
        self.assertIn("42000", cmd_str)


if __name__ == "__main__":
    unittest.main()
