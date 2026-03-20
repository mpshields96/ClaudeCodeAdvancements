#!/usr/bin/env python3
"""Tests for chat_detector.py — Duplicate Claude Code chat detection.

Covers:
- Process discovery (parsing ps output)
- Duplicate detection logic
- CCA project filtering
- Terminal close signal generation
"""
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chat_detector as cd


class TestProcessDiscovery(unittest.TestCase):
    """Test parsing of running processes to find Claude Code instances."""

    def test_parse_ps_line_basic(self):
        """Parse a basic ps output line into a process dict."""
        line = "12345 /usr/local/bin/claude --project /Users/matthewshields/Projects/ClaudeCodeAdvancements"
        result = cd.parse_ps_line(line)
        self.assertIsNotNone(result)
        self.assertEqual(result["pid"], 12345)
        self.assertIn("claude", result["command"])

    def test_parse_ps_line_no_pid(self):
        """Garbage lines return None."""
        self.assertIsNone(cd.parse_ps_line("not a real process line"))
        self.assertIsNone(cd.parse_ps_line(""))

    def test_parse_ps_line_with_env(self):
        """Line with CCA_CHAT_ID in environ output."""
        line = "99999 CCA_CHAT_ID=cli1 /usr/local/bin/claude"
        result = cd.parse_ps_line(line)
        self.assertIsNotNone(result)
        self.assertEqual(result["pid"], 99999)

    def test_find_claude_processes_returns_list(self):
        """find_claude_processes returns a list (possibly empty)."""
        with patch.object(cd, "_run_ps", return_value=""):
            result = cd.find_claude_processes()
            self.assertIsInstance(result, list)

    def test_find_claude_processes_parses_real_output(self):
        """Simulated ps output with multiple claude processes."""
        ps_output = (
            "12345 /usr/local/bin/claude --project /Users/matthewshields/Projects/ClaudeCodeAdvancements\n"
            "12346 /usr/local/bin/claude --project /Users/matthewshields/Projects/ClaudeCodeAdvancements\n"
            "99999 /usr/bin/python3 some_other_script.py\n"
        )
        with patch.object(cd, "_run_ps", return_value=ps_output):
            result = cd.find_claude_processes()
            self.assertEqual(len(result), 2)

    def test_find_claude_processes_excludes_grep(self):
        """grep processes should be excluded."""
        ps_output = (
            "12345 /usr/local/bin/claude --project /foo\n"
            "12346 grep claude\n"
        )
        with patch.object(cd, "_run_ps", return_value=ps_output):
            result = cd.find_claude_processes()
            self.assertEqual(len(result), 1)


class TestChatIDExtraction(unittest.TestCase):
    """Test extracting CCA_CHAT_ID from process environment."""

    def test_get_chat_id_from_env_file(self):
        """Read CCA_CHAT_ID from /proc-style environ (macOS: use ps eww)."""
        env_str = "CCA_CHAT_ID=cli1 HOME=/Users/foo PATH=/usr/bin"
        result = cd.extract_chat_id_from_env(env_str)
        self.assertEqual(result, "cli1")

    def test_get_chat_id_missing(self):
        """No CCA_CHAT_ID in environ returns None."""
        env_str = "HOME=/Users/foo PATH=/usr/bin"
        result = cd.extract_chat_id_from_env(env_str)
        self.assertIsNone(result)

    def test_get_chat_id_desktop(self):
        """desktop chat ID extracted correctly."""
        env_str = "CCA_CHAT_ID=desktop SHELL=/bin/zsh"
        result = cd.extract_chat_id_from_env(env_str)
        self.assertEqual(result, "desktop")

    def test_get_chat_id_cli2(self):
        env_str = "FOO=bar CCA_CHAT_ID=cli2 BAZ=qux"
        result = cd.extract_chat_id_from_env(env_str)
        self.assertEqual(result, "cli2")


class TestDuplicateDetection(unittest.TestCase):
    """Test identifying duplicate CCA chat sessions."""

    def test_no_duplicates(self):
        """Three unique chat IDs = no duplicates."""
        procs = [
            {"pid": 100, "chat_id": "desktop", "command": "claude", "cca_project": True},
            {"pid": 101, "chat_id": "cli1", "command": "claude", "cca_project": True},
            {"pid": 102, "chat_id": "cli2", "command": "claude", "cca_project": True},
        ]
        dupes = cd.find_duplicates(procs)
        self.assertEqual(len(dupes), 0)

    def test_duplicate_cli1(self):
        """Two cli1 processes = one duplicate pair."""
        procs = [
            {"pid": 100, "chat_id": "cli1", "command": "claude", "cca_project": True},
            {"pid": 101, "chat_id": "cli1", "command": "claude", "cca_project": True},
        ]
        dupes = cd.find_duplicates(procs)
        self.assertEqual(len(dupes), 1)
        self.assertEqual(dupes[0]["chat_id"], "cli1")
        self.assertEqual(len(dupes[0]["pids"]), 2)

    def test_duplicate_unknown_ids(self):
        """Two processes with no chat ID are duplicates (unknown role)."""
        procs = [
            {"pid": 100, "chat_id": None, "command": "claude", "cca_project": True},
            {"pid": 101, "chat_id": None, "command": "claude", "cca_project": True},
        ]
        dupes = cd.find_duplicates(procs)
        self.assertEqual(len(dupes), 1)
        self.assertEqual(dupes[0]["chat_id"], None)

    def test_non_cca_projects_ignored(self):
        """Claude processes for other projects don't count as CCA duplicates."""
        procs = [
            {"pid": 100, "chat_id": None, "command": "claude", "cca_project": True},
            {"pid": 101, "chat_id": None, "command": "claude", "cca_project": False},
        ]
        dupes = cd.find_duplicates(procs)
        self.assertEqual(len(dupes), 0)

    def test_mixed_duplicates(self):
        """Multiple duplicate groups detected."""
        procs = [
            {"pid": 100, "chat_id": "desktop", "command": "claude", "cca_project": True},
            {"pid": 101, "chat_id": "desktop", "command": "claude", "cca_project": True},
            {"pid": 102, "chat_id": "cli1", "command": "claude", "cca_project": True},
            {"pid": 103, "chat_id": "cli1", "command": "claude", "cca_project": True},
            {"pid": 104, "chat_id": "cli2", "command": "claude", "cca_project": True},
        ]
        dupes = cd.find_duplicates(procs)
        self.assertEqual(len(dupes), 2)
        ids = {d["chat_id"] for d in dupes}
        self.assertEqual(ids, {"desktop", "cli1"})


class TestCCAProjectDetection(unittest.TestCase):
    """Test whether a process is running in the CCA project."""

    def test_cca_path_detected(self):
        self.assertTrue(cd.is_cca_project(
            "/usr/local/bin/claude --project /Users/matthewshields/Projects/ClaudeCodeAdvancements"
        ))

    def test_other_project_not_detected(self):
        self.assertFalse(cd.is_cca_project(
            "/usr/local/bin/claude --project /Users/matthewshields/Projects/polymarket-bot"
        ))

    def test_cwd_based_detection(self):
        """CCA dir in command even without --project flag."""
        self.assertTrue(cd.is_cca_project(
            "claude /Users/matthewshields/Projects/ClaudeCodeAdvancements"
        ))

    def test_empty_command(self):
        self.assertFalse(cd.is_cca_project(""))


class TestStatusReport(unittest.TestCase):
    """Test the status report generation."""

    def test_clean_status(self):
        """No processes = clean report."""
        report = cd.generate_status_report([])
        self.assertEqual(report["status"], "clean")
        self.assertEqual(report["process_count"], 0)
        self.assertEqual(len(report["duplicates"]), 0)

    def test_healthy_status(self):
        """Processes with no duplicates = healthy."""
        procs = [
            {"pid": 100, "chat_id": "desktop", "command": "claude", "cca_project": True},
            {"pid": 101, "chat_id": "cli1", "command": "claude", "cca_project": True},
        ]
        report = cd.generate_status_report(procs)
        self.assertEqual(report["status"], "healthy")
        self.assertEqual(report["process_count"], 2)

    def test_duplicates_status(self):
        """Duplicates detected = warning status."""
        procs = [
            {"pid": 100, "chat_id": "desktop", "command": "claude", "cca_project": True},
            {"pid": 101, "chat_id": "desktop", "command": "claude", "cca_project": True},
        ]
        report = cd.generate_status_report(procs)
        self.assertEqual(report["status"], "duplicates_found")
        self.assertGreater(len(report["duplicates"]), 0)


class TestTerminalClose(unittest.TestCase):
    """Test terminal close AppleScript generation."""

    def test_generates_applescript(self):
        """Generate valid AppleScript to close a Terminal tab."""
        script = cd.generate_close_script()
        self.assertIn("Terminal", script)
        self.assertIn("close", script.lower())

    def test_close_returns_script_string(self):
        """The script is a non-empty string."""
        script = cd.generate_close_script()
        self.assertIsInstance(script, str)
        self.assertTrue(len(script) > 10)


class TestPreLaunchCheck(unittest.TestCase):
    """Test the pre-launch safety check used before starting new workers."""

    def test_safe_to_launch_no_existing(self):
        """No existing workers = safe to launch."""
        with patch.object(cd, "find_claude_processes", return_value=[]):
            result = cd.pre_launch_check("cli1")
            self.assertTrue(result["safe"])

    def test_unsafe_to_launch_duplicate_exists(self):
        """Existing cli1 worker = NOT safe to launch another cli1."""
        procs = [
            {"pid": 100, "chat_id": "cli1", "command": "claude", "cca_project": True},
        ]
        with patch.object(cd, "find_claude_processes", return_value=procs):
            result = cd.pre_launch_check("cli1")
            self.assertFalse(result["safe"])
            self.assertIn("cli1", result["reason"])

    def test_safe_to_launch_different_worker(self):
        """Existing cli1 worker = safe to launch cli2."""
        procs = [
            {"pid": 100, "chat_id": "cli1", "command": "claude", "cca_project": True},
        ]
        with patch.object(cd, "find_claude_processes", return_value=procs):
            result = cd.pre_launch_check("cli2")
            self.assertTrue(result["safe"])

    def test_stale_process_warning(self):
        """Process with no chat_id gets flagged as potentially stale."""
        procs = [
            {"pid": 100, "chat_id": None, "command": "claude", "cca_project": True},
        ]
        with patch.object(cd, "find_claude_processes", return_value=procs):
            result = cd.pre_launch_check("cli1")
            self.assertTrue(result["safe"])
            self.assertIn("stale", result.get("warnings", [""])[0].lower())


class TestCLI(unittest.TestCase):
    """Test CLI entry points."""

    def test_status_command(self):
        """'status' command runs without error."""
        with patch.object(cd, "find_claude_processes", return_value=[]):
            with patch("builtins.print"):
                cd.cli_main(["status"])

    def test_check_command(self):
        """'check' command for pre-launch validation."""
        with patch.object(cd, "find_claude_processes", return_value=[]):
            with patch("builtins.print"):
                cd.cli_main(["check", "cli1"])

    def test_unknown_command(self):
        """Unknown command prints usage."""
        with patch("builtins.print") as mock_print:
            cd.cli_main(["unknown_command"])
            mock_print.assert_called()


if __name__ == "__main__":
    unittest.main()
