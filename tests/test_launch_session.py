#!/usr/bin/env python3
"""Tests for launch_session.sh — unified multi-chat session launcher.

Tests the script's argument parsing, mode validation, and help output.
Does NOT actually launch terminals (that would be destructive in tests).
"""

import os
import subprocess
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = str(PROJECT_ROOT / "launch_session.sh")


class TestLaunchSessionHelp(unittest.TestCase):
    """Test help and usage output."""

    def test_no_args_shows_help(self):
        """No arguments shows usage help."""
        result = subprocess.run(
            ["bash", SCRIPT],
            capture_output=True, text=True, timeout=10
        )
        self.assertIn("launch_session.sh", result.stdout)
        self.assertIn("solo", result.stdout)
        self.assertIn("2chat", result.stdout)
        self.assertIn("3chat", result.stdout)

    def test_help_flag(self):
        """--help shows usage."""
        result = subprocess.run(
            ["bash", SCRIPT, "--help"],
            capture_output=True, text=True, timeout=10
        )
        self.assertIn("launch_session.sh", result.stdout)

    def test_help_command(self):
        """help command shows usage."""
        result = subprocess.run(
            ["bash", SCRIPT, "help"],
            capture_output=True, text=True, timeout=10
        )
        self.assertIn("launch_session.sh", result.stdout)


class TestLaunchSessionValidation(unittest.TestCase):
    """Test input validation."""

    def test_invalid_mode_fails(self):
        """Invalid mode produces error and exits non-zero."""
        result = subprocess.run(
            ["bash", SCRIPT, "invalid_mode"],
            capture_output=True, text=True, timeout=10
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Invalid mode", result.stderr + result.stdout)

    def test_solo_mode_exits_cleanly(self):
        """Solo mode says nothing to launch and exits 0."""
        result = subprocess.run(
            ["bash", SCRIPT, "solo"],
            capture_output=True, text=True, timeout=10
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Solo mode", result.stdout)
        self.assertIn("no helper terminals", result.stdout)


class TestScriptStructure(unittest.TestCase):
    """Test script file structure."""

    def test_script_exists(self):
        """Script file exists."""
        self.assertTrue(os.path.exists(SCRIPT))

    def test_script_is_executable_content(self):
        """Script starts with shebang."""
        with open(SCRIPT) as f:
            first_line = f.readline()
        self.assertTrue(first_line.startswith("#!/bin/bash"))

    def test_script_has_safety_checks(self):
        """Script includes safety checks."""
        content = Path(SCRIPT).read_text()
        self.assertIn("set -euo pipefail", content)
        self.assertIn("peak_hours", content)
        self.assertIn("chat_detector", content)
        self.assertIn("ANTHROPIC_API_KEY", content)

    def test_script_supports_all_modes(self):
        """Script handles solo, 2chat, and 3chat."""
        content = Path(SCRIPT).read_text()
        self.assertIn('"solo"', content)
        self.assertIn('"2chat"', content)
        self.assertIn('"3chat"', content)

    def test_script_launches_kalshi_only_for_3chat(self):
        """Kalshi launch is gated behind 3chat mode check."""
        content = Path(SCRIPT).read_text()
        # The Kalshi launch should be inside a 3chat conditional
        self.assertIn('if [ "$MODE" = "3chat" ]', content)
        self.assertIn("launch_kalshi", content)

    def test_script_has_delay_between_launches(self):
        """Script includes delay between terminal launches."""
        content = Path(SCRIPT).read_text()
        self.assertIn("sleep", content)

    def test_script_has_worker_duplicate_check(self):
        """Script checks for duplicate workers before launching."""
        content = Path(SCRIPT).read_text()
        self.assertIn("BLOCKED", content)
        self.assertIn("chat_detector", content)

    def test_script_unsets_api_key_warning(self):
        """Script warns about ANTHROPIC_API_KEY."""
        content = Path(SCRIPT).read_text()
        self.assertIn("ANTHROPIC_API_KEY", content)
        self.assertIn("API credits", content)


if __name__ == "__main__":
    unittest.main()
