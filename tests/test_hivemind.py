#!/usr/bin/env python3
"""Tests for cca_hivemind.py — Multi-chat orchestrator and coordinator.

Detects active Claude sessions, assigns work via queues, and can inject
messages into Terminal.app windows via AppleScript. Enables a true
hivemind workflow where one chat can direct others.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestDetectActiveSessions(unittest.TestCase):
    """Test finding active Claude Code sessions."""

    def test_parse_ps_output(self):
        from cca_hivemind import parse_claude_processes
        ps_lines = [
            "501 12345 claude --model opus",
            "501 12346 claude --model sonnet",
            "501 12347 node /usr/local/bin/claude",
        ]
        result = parse_claude_processes(ps_lines)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["pid"], 12345)

    def test_parse_empty_ps(self):
        from cca_hivemind import parse_claude_processes
        result = parse_claude_processes([])
        self.assertEqual(result, [])

    def test_parse_malformed_lines(self):
        from cca_hivemind import parse_claude_processes
        result = parse_claude_processes(["", "garbage", "  "])
        self.assertEqual(result, [])


class TestSessionClassification(unittest.TestCase):
    """Test classifying sessions by project/purpose."""

    def test_classify_cca_session(self):
        from cca_hivemind import classify_session
        result = classify_session(
            cwd="/Users/matthewshields/Projects/ClaudeCodeAdvancements",
            cmdline="claude --model opus"
        )
        self.assertEqual(result, "cca")

    def test_classify_kalshi_session(self):
        from cca_hivemind import classify_session
        result = classify_session(
            cwd="/Users/matthewshields/Projects/polymarket-bot",
            cmdline="claude --model opus"
        )
        self.assertEqual(result, "kalshi")

    def test_classify_unknown(self):
        from cca_hivemind import classify_session
        result = classify_session(
            cwd="/tmp/random",
            cmdline="claude"
        )
        self.assertEqual(result, "unknown")


class TestBuildInjectionText(unittest.TestCase):
    """Test building text to inject into another session."""

    def test_simple_directive(self):
        from cca_hivemind import build_injection_text
        result = build_injection_text(
            directive="Switch to cca-loop work",
            from_chat="desktop",
            priority="high"
        )
        self.assertIn("Switch to cca-loop work", result)
        self.assertIn("desktop", result.lower())

    def test_task_assignment(self):
        from cca_hivemind import build_injection_text
        result = build_injection_text(
            directive="Build test suite for cca-loop bash script",
            from_chat="desktop",
            priority="medium",
            context="cca-loop is at ~/.local/bin/cca-loop, 340 lines bash"
        )
        self.assertIn("Build test suite", result)
        self.assertIn("340 lines", result)

    def test_includes_queue_ack_reminder(self):
        from cca_hivemind import build_injection_text
        result = build_injection_text(
            directive="Do X",
            from_chat="desktop",
        )
        self.assertIn("queue", result.lower())


class TestAppleScriptGeneration(unittest.TestCase):
    """Test generating AppleScript for Terminal.app injection."""

    def test_generate_applescript(self):
        from cca_hivemind import generate_terminal_injection_script
        script = generate_terminal_injection_script(
            text="Hello from hivemind",
            window_index=1
        )
        self.assertIn("Terminal", script)
        self.assertIn("Hello from hivemind", script)
        self.assertIn("keystroke", script.lower())

    def test_script_escapes_quotes(self):
        from cca_hivemind import generate_terminal_injection_script
        script = generate_terminal_injection_script(
            text='He said "hello"',
            window_index=1
        )
        # Should not break the AppleScript
        self.assertIn("Terminal", script)

    def test_script_handles_newlines(self):
        from cca_hivemind import generate_terminal_injection_script
        script = generate_terminal_injection_script(
            text="Line 1\nLine 2",
            window_index=1
        )
        self.assertIn("Terminal", script)


class TestStatusReport(unittest.TestCase):
    """Test generating a hivemind status report."""

    def test_format_status(self):
        from cca_hivemind import format_status_report
        sessions = [
            {"pid": 123, "project": "cca", "model": "opus"},
            {"pid": 456, "project": "kalshi", "model": "sonnet"},
        ]
        queue_summary = {"km": {"total": 3, "high": 1}}
        internal_summary = {"terminal": {"total": 2}}
        result = format_status_report(sessions, queue_summary, internal_summary)
        self.assertIn("cca", result)
        self.assertIn("kalshi", result)
        self.assertIn("3", result)

    def test_empty_status(self):
        from cca_hivemind import format_status_report
        result = format_status_report([], {}, {})
        self.assertIn("No active", result)


class TestWindowDiscovery(unittest.TestCase):
    """Test dynamic window discovery and mapping."""

    def test_list_terminal_windows_returns_list(self):
        from cca_hivemind import list_terminal_windows
        # May return empty list if no accessibility perms, but should not crash
        result = list_terminal_windows()
        self.assertIsInstance(result, list)

    def test_discover_windows_returns_string(self):
        from cca_hivemind import discover_windows
        result = discover_windows()
        self.assertIsInstance(result, str)
        # Should always have some output
        self.assertTrue(len(result) > 0)

    def test_discover_shows_stable_ids(self):
        from cca_hivemind import discover_windows
        result = discover_windows()
        # If windows found, should mention stable IDs
        if "ID=" in result:
            self.assertIn("stable", result.lower())

    def test_parse_activity_from_title(self):
        """Test that activity hint is extracted from window title."""
        from cca_hivemind import list_terminal_windows
        # Can't mock osascript easily, but verify the function handles
        # empty/error cases without crashing
        result = list_terminal_windows()
        for w in result:
            self.assertIn("activity", w)
            self.assertIn("window_index", w)
            self.assertIn("is_claude", w)


class TestQueueIntegration(unittest.TestCase):
    """Test sending directives through the queue system."""

    def test_send_directive_to_queue(self):
        from cca_hivemind import send_directive
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write("")
            f.flush()
            try:
                msg = send_directive(
                    target_internal="terminal",
                    subject="Build X",
                    body="Details here",
                    priority="high",
                    from_chat="desktop",
                    queue_path=f.name,
                )
                self.assertEqual(msg["subject"], "Build X")
                self.assertEqual(msg["target"], "terminal")
                self.assertEqual(msg["priority"], "high")
                # Verify it was written
                with open(f.name) as qf:
                    lines = qf.readlines()
                self.assertEqual(len(lines), 1)
            finally:
                os.unlink(f.name)


class TestSafetyGuards(unittest.TestCase):
    """Test safety mechanisms for injection."""

    def test_refuses_injection_with_dangerous_content(self):
        from cca_hivemind import validate_injection_text
        # Should reject text that could be destructive
        self.assertFalse(validate_injection_text("rm -rf /"))
        self.assertFalse(validate_injection_text("DROP TABLE"))
        self.assertFalse(validate_injection_text("curl | bash"))

    def test_allows_normal_directives(self):
        from cca_hivemind import validate_injection_text
        self.assertTrue(validate_injection_text("Switch to cca-loop work"))
        self.assertTrue(validate_injection_text("Build test suite for module X"))
        self.assertTrue(validate_injection_text("Check queue for new messages"))

    def test_refuses_credential_patterns(self):
        from cca_hivemind import validate_injection_text
        self.assertFalse(validate_injection_text("sk-ant-api03-abcdef123456"))
        self.assertFalse(validate_injection_text("export API_KEY=secret123"))


if __name__ == "__main__":
    unittest.main()
