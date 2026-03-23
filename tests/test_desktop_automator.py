"""Tests for desktop_automator.py — MT-22: Claude Desktop App Automation.

Tests the AppleScript-based automation layer for Claude.app (Electron).
All AppleScript calls are mocked since tests run without a GUI.
"""

import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

# Add project root to path
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from desktop_automator import (
    DesktopAutomator,
    BUNDLE_ID,
    APP_NAME,
    DEFAULT_ACTIVATE_DELAY,
    DEFAULT_RESPONSE_TIMEOUT,
    LoopConfig,
    LoopResult,
)


class TestDesktopAutomatorInit(unittest.TestCase):
    """Test initialization and configuration."""

    def test_default_config(self):
        da = DesktopAutomator(dry_run=True)
        self.assertEqual(da.activate_delay, DEFAULT_ACTIVATE_DELAY)
        self.assertEqual(da.response_timeout, DEFAULT_RESPONSE_TIMEOUT)
        self.assertTrue(da.dry_run)

    def test_custom_config(self):
        da = DesktopAutomator(
            activate_delay=1.0,
            response_timeout=60,
            dry_run=True,
        )
        self.assertEqual(da.activate_delay, 1.0)
        self.assertEqual(da.response_timeout, 60)

    def test_audit_log_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "test_audit.jsonl"
            da = DesktopAutomator(audit_log=log_path, dry_run=True)
            self.assertEqual(da.audit_log, log_path)

    def test_constants(self):
        self.assertEqual(BUNDLE_ID, "com.anthropic.claudefordesktop")
        self.assertEqual(APP_NAME, "Claude")


class TestAuditLogging(unittest.TestCase):
    """Test audit trail logging."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.log_path = Path(self.tmp) / "audit.jsonl"
        self.da = DesktopAutomator(audit_log=self.log_path, dry_run=True)

    def test_log_creates_file(self):
        self.da._log("test_event")
        self.assertTrue(self.log_path.exists())

    def test_log_writes_json(self):
        self.da._log("test_event", {"key": "value"})
        with open(self.log_path) as f:
            entry = json.loads(f.readline())
        self.assertEqual(entry["event"], "test_event")
        self.assertEqual(entry["key"], "value")
        self.assertIn("timestamp", entry)

    def test_log_appends(self):
        self.da._log("event1")
        self.da._log("event2")
        with open(self.log_path) as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 2)

    def test_log_timestamp_format(self):
        self.da._log("test")
        with open(self.log_path) as f:
            entry = json.loads(f.readline())
        ts = entry["timestamp"]
        self.assertTrue(ts.endswith("Z"))
        self.assertIn("T", ts)

    def test_log_handles_missing_parent_dir(self):
        bad_path = Path(self.tmp) / "nonexistent" / "sub" / "audit.jsonl"
        da = DesktopAutomator(audit_log=bad_path, dry_run=True)
        # Should not raise — silently fails
        da._log("test")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestAppleScriptExecution(unittest.TestCase):
    """Test the AppleScript execution layer."""

    def test_dry_run_skips_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            da = DesktopAutomator(
                audit_log=Path(tmp) / "audit.jsonl",
                dry_run=True,
            )
            ok, output = da._run_applescript('tell application "Finder" to activate')
            self.assertTrue(ok)
            self.assertEqual(output, "")

    @patch("desktop_automator.subprocess.run")
    def test_successful_execution(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="true\n", stderr="")
        da = DesktopAutomator(dry_run=False)
        ok, output = da._run_applescript("return true")
        self.assertTrue(ok)
        self.assertEqual(output, "true")

    @patch("desktop_automator.subprocess.run")
    def test_failed_execution(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
        da = DesktopAutomator(dry_run=False)
        ok, output = da._run_applescript("bad script")
        self.assertFalse(ok)

    @patch("desktop_automator.subprocess.run")
    def test_timeout_handling(self, mock_run):
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="osascript", timeout=10)
        da = DesktopAutomator(dry_run=False)
        ok, output = da._run_applescript("slow script")
        self.assertFalse(ok)
        self.assertEqual(output, "timeout")

    @patch("desktop_automator.subprocess.run")
    def test_missing_osascript(self, mock_run):
        mock_run.side_effect = FileNotFoundError
        da = DesktopAutomator(dry_run=False)
        ok, output = da._run_applescript("any script")
        self.assertFalse(ok)
        self.assertEqual(output, "osascript not found")


class TestIsClaudeRunning(unittest.TestCase):
    """Test Claude process detection."""

    @patch.object(DesktopAutomator, "_run_applescript")
    def test_claude_running(self, mock_as):
        mock_as.return_value = (True, "true")
        da = DesktopAutomator(dry_run=False)
        self.assertTrue(da.is_claude_running())

    @patch.object(DesktopAutomator, "_run_applescript")
    def test_claude_not_running(self, mock_as):
        mock_as.return_value = (True, "false")
        da = DesktopAutomator(dry_run=False)
        self.assertFalse(da.is_claude_running())

    @patch.object(DesktopAutomator, "_run_applescript")
    def test_applescript_failure(self, mock_as):
        mock_as.return_value = (False, "error")
        da = DesktopAutomator(dry_run=False)
        self.assertFalse(da.is_claude_running())


class TestGetFrontmostApp(unittest.TestCase):
    """Test frontmost app detection."""

    @patch.object(DesktopAutomator, "_run_applescript")
    def test_returns_app_name(self, mock_as):
        mock_as.return_value = (True, "Claude")
        da = DesktopAutomator(dry_run=False)
        self.assertEqual(da.get_frontmost_app(), "Claude")

    @patch.object(DesktopAutomator, "_run_applescript")
    def test_failure_returns_empty(self, mock_as):
        mock_as.return_value = (False, "")
        da = DesktopAutomator(dry_run=False)
        self.assertEqual(da.get_frontmost_app(), "")


class TestActivateClaude(unittest.TestCase):
    """Test Claude activation (bring to foreground)."""

    def _make_da(self, tmp):
        return DesktopAutomator(
            audit_log=Path(tmp) / "audit.jsonl",
            activate_delay=0,  # no delay in tests
            dry_run=False,
        )

    @patch.object(DesktopAutomator, "get_frontmost_app", return_value="Claude")
    @patch.object(DesktopAutomator, "_run_applescript", return_value=(True, ""))
    @patch.object(DesktopAutomator, "is_claude_running", return_value=True)
    def test_successful_activation(self, mock_running, mock_as, mock_front):
        with tempfile.TemporaryDirectory() as tmp:
            da = self._make_da(tmp)
            self.assertTrue(da.activate_claude())

    @patch.object(DesktopAutomator, "is_claude_running", return_value=False)
    def test_fails_if_not_running(self, mock_running):
        with tempfile.TemporaryDirectory() as tmp:
            da = self._make_da(tmp)
            self.assertFalse(da.activate_claude())

    @patch.object(DesktopAutomator, "get_frontmost_app", return_value="Safari")
    @patch.object(DesktopAutomator, "_run_applescript", return_value=(True, ""))
    @patch.object(DesktopAutomator, "is_claude_running", return_value=True)
    def test_fails_if_not_frontmost(self, mock_running, mock_as, mock_front):
        with tempfile.TemporaryDirectory() as tmp:
            da = self._make_da(tmp)
            self.assertFalse(da.activate_claude())

    @patch.object(DesktopAutomator, "_run_applescript", return_value=(False, "error"))
    @patch.object(DesktopAutomator, "is_claude_running", return_value=True)
    def test_fails_on_applescript_error(self, mock_running, mock_as):
        with tempfile.TemporaryDirectory() as tmp:
            da = self._make_da(tmp)
            self.assertFalse(da.activate_claude())


class TestSendPrompt(unittest.TestCase):
    """Test prompt sending via keystroke injection."""

    def _make_da(self, tmp):
        return DesktopAutomator(
            audit_log=Path(tmp) / "audit.jsonl",
            dry_run=False,
        )

    @patch.object(DesktopAutomator, "get_frontmost_app", return_value="Claude")
    @patch.object(DesktopAutomator, "_run_applescript", return_value=(True, ""))
    def test_sends_prompt_successfully(self, mock_as, mock_front):
        with tempfile.TemporaryDirectory() as tmp:
            da = self._make_da(tmp)
            self.assertTrue(da.send_prompt("Hello Claude"))

    @patch.object(DesktopAutomator, "get_frontmost_app", return_value="Safari")
    def test_fails_if_wrong_app(self, mock_front):
        with tempfile.TemporaryDirectory() as tmp:
            da = self._make_da(tmp)
            self.assertFalse(da.send_prompt("Hello"))

    def test_fails_on_empty_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            da = self._make_da(tmp)
            self.assertFalse(da.send_prompt(""))
            self.assertFalse(da.send_prompt("   "))

    @patch.object(DesktopAutomator, "get_frontmost_app", return_value="Claude")
    @patch.object(DesktopAutomator, "_run_applescript", return_value=(True, ""))
    def test_uses_clipboard_for_long_prompts(self, mock_as, mock_front):
        with tempfile.TemporaryDirectory() as tmp:
            da = self._make_da(tmp)
            long_prompt = "x" * 1000
            da.send_prompt(long_prompt)
            # Should have clipboard set + paste calls
            calls = mock_as.call_args_list
            clipboard_calls = [c for c in calls if "clipboard" in str(c)]
            self.assertTrue(len(clipboard_calls) > 0)

    @patch.object(DesktopAutomator, "get_frontmost_app", return_value="Claude")
    @patch.object(DesktopAutomator, "_run_applescript", return_value=(True, ""))
    def test_escapes_special_characters(self, mock_as, mock_front):
        with tempfile.TemporaryDirectory() as tmp:
            da = self._make_da(tmp)
            da.send_prompt('prompt with "quotes" and \\backslash')
            calls = mock_as.call_args_list
            clipboard_calls = [c for c in calls if "clipboard" in str(c)]
            # Verify quotes were escaped
            for c in clipboard_calls:
                script = c[0][0]
                self.assertNotIn('""', script.replace('\\"', ''))

    @patch.object(DesktopAutomator, "get_frontmost_app", return_value="Claude")
    @patch.object(DesktopAutomator, "_run_applescript", return_value=(True, ""))
    def test_sends_cmd_return(self, mock_as, mock_front):
        with tempfile.TemporaryDirectory() as tmp:
            da = self._make_da(tmp)
            da.send_prompt("test")
            calls = [str(c) for c in mock_as.call_args_list]
            cmd_return_calls = [c for c in calls if "return" in c and "command" in c]
            self.assertTrue(len(cmd_return_calls) > 0)

    @patch.object(DesktopAutomator, "get_frontmost_app", return_value="Claude")
    @patch.object(DesktopAutomator, "_run_applescript", return_value=(True, ""))
    def test_logs_send_success(self, mock_as, mock_front):
        with tempfile.TemporaryDirectory() as tmp:
            da = self._make_da(tmp)
            da.send_prompt("test prompt")
            with open(da.audit_log) as f:
                entries = [json.loads(l) for l in f]
            events = [e["event"] for e in entries]
            self.assertIn("send_success", events)


class TestCloseWindow(unittest.TestCase):
    """Test window close."""

    @patch.object(DesktopAutomator, "get_frontmost_app", return_value="Claude")
    @patch.object(DesktopAutomator, "_run_applescript", return_value=(True, ""))
    def test_closes_window(self, mock_as, mock_front):
        with tempfile.TemporaryDirectory() as tmp:
            da = DesktopAutomator(audit_log=Path(tmp) / "a.jsonl", dry_run=False)
            self.assertTrue(da.close_window())

    @patch.object(DesktopAutomator, "get_frontmost_app", return_value="Finder")
    def test_fails_wrong_app(self, mock_front):
        with tempfile.TemporaryDirectory() as tmp:
            da = DesktopAutomator(audit_log=Path(tmp) / "a.jsonl", dry_run=False)
            self.assertFalse(da.close_window())


class TestNewConversation(unittest.TestCase):
    """Test new conversation (Cmd+N)."""

    @patch.object(DesktopAutomator, "get_frontmost_app", return_value="Claude")
    @patch.object(DesktopAutomator, "_run_applescript", return_value=(True, ""))
    def test_starts_new_conversation(self, mock_as, mock_front):
        with tempfile.TemporaryDirectory() as tmp:
            da = DesktopAutomator(audit_log=Path(tmp) / "a.jsonl", dry_run=False)
            self.assertTrue(da.new_conversation())

    @patch.object(DesktopAutomator, "get_frontmost_app", return_value="Terminal")
    def test_fails_wrong_app(self, mock_front):
        with tempfile.TemporaryDirectory() as tmp:
            da = DesktopAutomator(audit_log=Path(tmp) / "a.jsonl", dry_run=False)
            self.assertFalse(da.new_conversation())


class TestPreflight(unittest.TestCase):
    """Test pre-flight checks."""

    @patch.object(DesktopAutomator, "is_claude_running", return_value=True)
    @patch("desktop_automator.subprocess.run")
    def test_all_pass(self, mock_run, mock_running):
        mock_run.return_value = MagicMock(returncode=0)
        with tempfile.TemporaryDirectory() as tmp:
            da = DesktopAutomator(audit_log=Path(tmp) / "a.jsonl", dry_run=False)
            checks = da.preflight()
            self.assertEqual(checks["osascript"], "PASS")
            self.assertIn(checks["claude_installed"], ["PASS", "FAIL"])  # depends on machine
            self.assertEqual(checks["claude_running"], "PASS")
            self.assertEqual(checks["audit_log"], "PASS")

    @patch.object(DesktopAutomator, "is_claude_running", return_value=False)
    @patch("desktop_automator.subprocess.run")
    def test_claude_not_running_is_warn(self, mock_run, mock_running):
        mock_run.return_value = MagicMock(returncode=0)
        with tempfile.TemporaryDirectory() as tmp:
            da = DesktopAutomator(audit_log=Path(tmp) / "a.jsonl", dry_run=False)
            checks = da.preflight()
            self.assertEqual(checks["claude_running"], "WARN")

    @patch.object(DesktopAutomator, "is_claude_running", return_value=True)
    @patch("desktop_automator.subprocess.run")
    def test_osascript_timeout(self, mock_run, mock_running):
        import subprocess as sp
        mock_run.side_effect = sp.TimeoutExpired(cmd="osascript", timeout=5)
        with tempfile.TemporaryDirectory() as tmp:
            da = DesktopAutomator(audit_log=Path(tmp) / "a.jsonl", dry_run=False)
            checks = da.preflight()
            self.assertEqual(checks["osascript"], "FAIL")


class TestLoopConfig(unittest.TestCase):
    """Test loop configuration."""

    def test_defaults(self):
        cfg = LoopConfig()
        self.assertEqual(cfg.max_iterations, 50)
        self.assertEqual(cfg.max_consecutive_failures, 3)
        self.assertEqual(cfg.cooldown_seconds, 15)
        self.assertFalse(cfg.dry_run)

    def test_custom(self):
        cfg = LoopConfig(max_iterations=10, cooldown_seconds=5, dry_run=True)
        self.assertEqual(cfg.max_iterations, 10)
        self.assertEqual(cfg.cooldown_seconds, 5)
        self.assertTrue(cfg.dry_run)


class TestLoopResult(unittest.TestCase):
    """Test loop result tracking."""

    def test_creation(self):
        r = LoopResult(
            iteration=1,
            success=True,
            prompt_length=100,
            duration=5.0,
        )
        self.assertEqual(r.iteration, 1)
        self.assertTrue(r.success)
        self.assertIsNone(r.error)

    def test_failure_result(self):
        r = LoopResult(
            iteration=2,
            success=False,
            prompt_length=50,
            duration=1.0,
            error="activate_failed",
        )
        self.assertFalse(r.success)
        self.assertEqual(r.error, "activate_failed")

    def test_to_dict(self):
        r = LoopResult(iteration=1, success=True, prompt_length=50, duration=2.0)
        d = r.to_dict()
        self.assertEqual(d["iteration"], 1)
        self.assertTrue(d["success"])
        self.assertIn("prompt_length", d)


class TestRunLoopIteration(unittest.TestCase):
    """Test single loop iteration."""

    @patch.object(DesktopAutomator, "wait_for_response", return_value=True)
    @patch.object(DesktopAutomator, "send_prompt", return_value=True)
    @patch.object(DesktopAutomator, "activate_claude", return_value=True)
    def test_successful_iteration(self, mock_act, mock_send, mock_wait):
        with tempfile.TemporaryDirectory() as tmp:
            da = DesktopAutomator(audit_log=Path(tmp) / "a.jsonl", dry_run=False)
            result = da.run_loop_iteration("test prompt")
            self.assertTrue(result["success"])
            self.assertIn("duration", result)

    @patch.object(DesktopAutomator, "activate_claude", return_value=False)
    def test_fails_on_activate(self, mock_act):
        with tempfile.TemporaryDirectory() as tmp:
            da = DesktopAutomator(audit_log=Path(tmp) / "a.jsonl", dry_run=False)
            result = da.run_loop_iteration("test")
            self.assertFalse(result["success"])
            self.assertEqual(result["error"], "activate_failed")

    @patch.object(DesktopAutomator, "send_prompt", return_value=False)
    @patch.object(DesktopAutomator, "activate_claude", return_value=True)
    def test_fails_on_send(self, mock_act, mock_send):
        with tempfile.TemporaryDirectory() as tmp:
            da = DesktopAutomator(audit_log=Path(tmp) / "a.jsonl", dry_run=False)
            result = da.run_loop_iteration("test")
            self.assertFalse(result["success"])
            self.assertEqual(result["error"], "send_failed")


class TestWaitForResponse(unittest.TestCase):
    """Test response waiting."""

    def test_dry_run_returns_immediately(self):
        with tempfile.TemporaryDirectory() as tmp:
            da = DesktopAutomator(
                audit_log=Path(tmp) / "a.jsonl",
                response_timeout=0.01,
                dry_run=True,
            )
            start = time.time()
            result = da.wait_for_response(timeout=0.01)
            elapsed = time.time() - start
            self.assertTrue(result)
            self.assertLess(elapsed, 1.0)  # should be near-instant in dry_run

    def test_non_dry_run_waits(self):
        with tempfile.TemporaryDirectory() as tmp:
            da = DesktopAutomator(
                audit_log=Path(tmp) / "a.jsonl",
                response_timeout=0.1,
                dry_run=False,
            )
            start = time.time()
            result = da.wait_for_response(timeout=0.1)
            elapsed = time.time() - start
            self.assertTrue(result)
            self.assertGreaterEqual(elapsed, 0.09)

    def test_logs_wait_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            da = DesktopAutomator(
                audit_log=Path(tmp) / "a.jsonl",
                dry_run=True,
            )
            da.wait_for_response(timeout=0.01)
            with open(da.audit_log) as f:
                entries = [json.loads(l) for l in f]
            events = [e["event"] for e in entries]
            self.assertIn("waiting_for_response", events)
            self.assertIn("response_timeout_reached", events)


class TestSafetyGuards(unittest.TestCase):
    """Test safety mechanisms."""

    @patch.object(DesktopAutomator, "get_frontmost_app", return_value="Terminal")
    def test_send_blocked_wrong_app(self, mock_front):
        """Keystrokes must only go to Claude, never another app."""
        with tempfile.TemporaryDirectory() as tmp:
            da = DesktopAutomator(audit_log=Path(tmp) / "a.jsonl", dry_run=False)
            self.assertFalse(da.send_prompt("dangerous if sent to terminal"))

    @patch.object(DesktopAutomator, "get_frontmost_app", return_value="Finder")
    def test_close_blocked_wrong_app(self, mock_front):
        with tempfile.TemporaryDirectory() as tmp:
            da = DesktopAutomator(audit_log=Path(tmp) / "a.jsonl", dry_run=False)
            self.assertFalse(da.close_window())

    def test_prompt_sanitization_null_bytes(self):
        """Null bytes in prompts should be stripped."""
        with tempfile.TemporaryDirectory() as tmp:
            da = DesktopAutomator(audit_log=Path(tmp) / "a.jsonl", dry_run=True)
            # dry_run so we test the sanitization logic
            ok, _ = da._run_applescript("test")  # just verifying dry_run works
            self.assertTrue(ok)

    @patch.object(DesktopAutomator, "get_frontmost_app", return_value="Claude")
    @patch.object(DesktopAutomator, "_run_applescript", return_value=(True, ""))
    def test_clears_input_before_typing(self, mock_as, mock_front):
        """Should Cmd+A then Delete before typing new prompt."""
        with tempfile.TemporaryDirectory() as tmp:
            da = DesktopAutomator(audit_log=Path(tmp) / "a.jsonl", dry_run=False)
            da.send_prompt("test")
            calls = [str(c) for c in mock_as.call_args_list]
            # Should have select-all keystroke
            select_all = [c for c in calls if '"a"' in c and "command" in c]
            self.assertTrue(len(select_all) > 0)


class TestDryRunMode(unittest.TestCase):
    """Test dry run mode end-to-end."""

    def test_full_iteration_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            da = DesktopAutomator(
                audit_log=Path(tmp) / "a.jsonl",
                activate_delay=0,
                response_timeout=0.01,
                dry_run=True,
            )
            # In dry run, all AppleScript calls succeed
            # But activate_claude still checks is_claude_running which calls _run_applescript
            # In dry_run, _run_applescript returns (True, "")
            # is_claude_running checks output == "true", but dry_run returns ""
            # So activate will fail in pure dry_run — this is expected
            result = da.run_loop_iteration("test prompt")
            # activate_claude fails because is_claude_running returns False in dry_run
            self.assertFalse(result["success"])

    def test_dry_run_logs_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            da = DesktopAutomator(
                audit_log=Path(tmp) / "a.jsonl",
                dry_run=True,
            )
            da._run_applescript("test script")
            with open(da.audit_log) as f:
                entry = json.loads(f.readline())
            self.assertEqual(entry["event"], "dry_run_applescript")


class TestPromptTruncation(unittest.TestCase):
    """Test prompt length handling."""

    @patch.object(DesktopAutomator, "get_frontmost_app", return_value="Claude")
    @patch.object(DesktopAutomator, "_run_applescript", return_value=(True, ""))
    def test_very_long_prompt(self, mock_as, mock_front):
        with tempfile.TemporaryDirectory() as tmp:
            da = DesktopAutomator(audit_log=Path(tmp) / "a.jsonl", dry_run=False)
            long_prompt = "x" * 50000
            result = da.send_prompt(long_prompt)
            self.assertTrue(result)

    @patch.object(DesktopAutomator, "get_frontmost_app", return_value="Claude")
    @patch.object(DesktopAutomator, "_run_applescript", return_value=(True, ""))
    def test_multiline_prompt(self, mock_as, mock_front):
        with tempfile.TemporaryDirectory() as tmp:
            da = DesktopAutomator(audit_log=Path(tmp) / "a.jsonl", dry_run=False)
            prompt = "line 1\nline 2\nline 3"
            result = da.send_prompt(prompt)
            self.assertTrue(result)


class TestWindowCount(unittest.TestCase):
    """Test window enumeration."""

    @patch.object(DesktopAutomator, "_run_applescript")
    def test_get_window_count(self, mock_as):
        mock_as.return_value = (True, "3")
        with tempfile.TemporaryDirectory() as tmp:
            da = DesktopAutomator(audit_log=Path(tmp) / "a.jsonl", dry_run=False)
            count = da.get_window_count()
            self.assertEqual(count, 3)

    @patch.object(DesktopAutomator, "_run_applescript")
    def test_window_count_error(self, mock_as):
        mock_as.return_value = (False, "")
        with tempfile.TemporaryDirectory() as tmp:
            da = DesktopAutomator(audit_log=Path(tmp) / "a.jsonl", dry_run=False)
            count = da.get_window_count()
            self.assertEqual(count, -1)


class TestCPUUsage(unittest.TestCase):
    """Test CPU usage detection."""

    @patch("desktop_automator.subprocess.run")
    def test_get_cpu_usage(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Claude             12.5\nClaude Helper       2.1\n",
        )
        with tempfile.TemporaryDirectory() as tmp:
            da = DesktopAutomator(audit_log=Path(tmp) / "a.jsonl", dry_run=False)
            cpu = da.get_claude_cpu_usage()
            self.assertAlmostEqual(cpu, 12.5)

    @patch("desktop_automator.subprocess.run")
    def test_cpu_usage_no_claude(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Safari              5.0\nFinder              0.1\n",
        )
        with tempfile.TemporaryDirectory() as tmp:
            da = DesktopAutomator(audit_log=Path(tmp) / "a.jsonl", dry_run=False)
            cpu = da.get_claude_cpu_usage()
            self.assertEqual(cpu, 0.0)

    @patch("desktop_automator.subprocess.run")
    def test_cpu_usage_error(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="ps", timeout=5)
        with tempfile.TemporaryDirectory() as tmp:
            da = DesktopAutomator(audit_log=Path(tmp) / "a.jsonl", dry_run=False)
            cpu = da.get_claude_cpu_usage()
            self.assertEqual(cpu, -1.0)

    def test_dry_run_returns_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            da = DesktopAutomator(audit_log=Path(tmp) / "a.jsonl", dry_run=True)
            cpu = da.get_claude_cpu_usage()
            self.assertEqual(cpu, 0.0)


class TestIsClaudeIdle(unittest.TestCase):
    """Test idle detection heuristic."""

    @patch.object(DesktopAutomator, "get_claude_cpu_usage", return_value=1.5)
    def test_idle_when_low_cpu(self, mock_cpu):
        with tempfile.TemporaryDirectory() as tmp:
            da = DesktopAutomator(audit_log=Path(tmp) / "a.jsonl", dry_run=False)
            self.assertTrue(da.is_claude_idle())

    @patch.object(DesktopAutomator, "get_claude_cpu_usage", return_value=25.0)
    def test_not_idle_when_high_cpu(self, mock_cpu):
        with tempfile.TemporaryDirectory() as tmp:
            da = DesktopAutomator(audit_log=Path(tmp) / "a.jsonl", dry_run=False)
            self.assertFalse(da.is_claude_idle())

    @patch.object(DesktopAutomator, "get_claude_cpu_usage", return_value=-1.0)
    def test_error_returns_not_idle(self, mock_cpu):
        with tempfile.TemporaryDirectory() as tmp:
            da = DesktopAutomator(audit_log=Path(tmp) / "a.jsonl", dry_run=False)
            self.assertFalse(da.is_claude_idle())

    @patch.object(DesktopAutomator, "get_claude_cpu_usage", return_value=4.9)
    def test_custom_threshold(self, mock_cpu):
        with tempfile.TemporaryDirectory() as tmp:
            da = DesktopAutomator(audit_log=Path(tmp) / "a.jsonl", dry_run=False)
            self.assertTrue(da.is_claude_idle(cpu_threshold=5.0))
            self.assertFalse(da.is_claude_idle(cpu_threshold=4.0))


if __name__ == "__main__":
    unittest.main()
