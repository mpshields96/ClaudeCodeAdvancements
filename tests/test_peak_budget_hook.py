#!/usr/bin/env python3
"""Tests for MT-38 Phase 3: Peak budget PreToolUse hook.

Blocks Agent tool spawns during PEAK hours, warns during SHOULDER,
allows freely during OFF-PEAK.
"""

import json
import os
import subprocess
import sys
import unittest
from datetime import datetime
from unittest.mock import patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from peak_budget_hook import evaluate_tool_call, BLOCKED_TOOLS


class TestEvaluateToolCall(unittest.TestCase):
    """Test the core evaluation logic."""

    # --- PEAK: block agent spawns ---

    def test_peak_blocks_agent(self):
        """Agent tool is denied during PEAK."""
        now = datetime(2026, 3, 24, 10, 0)  # Tuesday 10 AM ET = PEAK
        result = evaluate_tool_call("Agent", {}, now=now)
        self.assertEqual(result["decision"], "deny")
        self.assertIn("PEAK", result["reason"])

    def test_peak_blocks_agent_case_insensitive_check(self):
        """Tool name matching is exact (Agent, not agent)."""
        now = datetime(2026, 3, 24, 10, 0)
        result = evaluate_tool_call("Agent", {}, now=now)
        self.assertEqual(result["decision"], "deny")

    def test_peak_allows_read(self):
        """Read tool is always allowed, even during PEAK."""
        now = datetime(2026, 3, 24, 10, 0)
        result = evaluate_tool_call("Read", {}, now=now)
        self.assertEqual(result["decision"], "allow")

    def test_peak_allows_write(self):
        """Write tool is allowed during PEAK."""
        now = datetime(2026, 3, 24, 10, 0)
        result = evaluate_tool_call("Write", {}, now=now)
        self.assertEqual(result["decision"], "allow")

    def test_peak_allows_bash(self):
        """Bash tool is allowed during PEAK (only Agent is blocked)."""
        now = datetime(2026, 3, 24, 10, 0)
        result = evaluate_tool_call("Bash", {}, now=now)
        self.assertEqual(result["decision"], "allow")

    def test_peak_allows_edit(self):
        now = datetime(2026, 3, 24, 10, 0)
        result = evaluate_tool_call("Edit", {}, now=now)
        self.assertEqual(result["decision"], "allow")

    def test_peak_allows_glob(self):
        now = datetime(2026, 3, 24, 10, 0)
        result = evaluate_tool_call("Glob", {}, now=now)
        self.assertEqual(result["decision"], "allow")

    # --- SHOULDER: warn for agent spawns ---

    def test_shoulder_warns_agent(self):
        """Agent tool gets a warning during SHOULDER but is allowed."""
        now = datetime(2026, 3, 24, 15, 0)  # Tuesday 3 PM ET = SHOULDER
        result = evaluate_tool_call("Agent", {}, now=now)
        self.assertEqual(result["decision"], "warn")
        self.assertIn("SHOULDER", result["reason"])

    def test_shoulder_allows_read(self):
        now = datetime(2026, 3, 24, 15, 0)
        result = evaluate_tool_call("Read", {}, now=now)
        self.assertEqual(result["decision"], "allow")

    # --- OFF-PEAK: allow everything ---

    def test_offpeak_allows_agent(self):
        """Agent tool is allowed during OFF-PEAK."""
        now = datetime(2026, 3, 24, 20, 0)  # Tuesday 8 PM ET = OFF-PEAK
        result = evaluate_tool_call("Agent", {}, now=now)
        self.assertEqual(result["decision"], "allow")

    def test_offpeak_allows_all(self):
        """All tools allowed during OFF-PEAK."""
        now = datetime(2026, 3, 24, 22, 0)  # Tuesday 10 PM ET
        for tool in ["Agent", "Read", "Write", "Bash", "Edit", "Glob", "Grep"]:
            result = evaluate_tool_call(tool, {}, now=now)
            self.assertEqual(result["decision"], "allow", f"{tool} should be allowed off-peak")

    # --- WEEKEND: allow everything ---

    def test_weekend_allows_agent(self):
        """Agent tool is allowed on weekends."""
        now = datetime(2026, 3, 22, 10, 0)  # Saturday 10 AM
        result = evaluate_tool_call("Agent", {}, now=now)
        self.assertEqual(result["decision"], "allow")

    def test_weekend_saturday_morning(self):
        now = datetime(2026, 3, 22, 8, 0)  # Saturday 8 AM (would be PEAK on weekday)
        result = evaluate_tool_call("Agent", {}, now=now)
        self.assertEqual(result["decision"], "allow")

    def test_weekend_sunday(self):
        now = datetime(2026, 3, 29, 12, 0)  # Sunday noon (Mar 29 = Sun)
        result = evaluate_tool_call("Agent", {}, now=now)
        self.assertEqual(result["decision"], "allow")

    # --- Edge cases ---

    def test_peak_boundary_start(self):
        """8:00 AM is PEAK."""
        now = datetime(2026, 3, 24, 8, 0)  # Tuesday 8 AM
        result = evaluate_tool_call("Agent", {}, now=now)
        self.assertEqual(result["decision"], "deny")

    def test_peak_boundary_end(self):
        """2:00 PM is SHOULDER (not PEAK)."""
        now = datetime(2026, 3, 24, 14, 0)  # Tuesday 2 PM
        result = evaluate_tool_call("Agent", {}, now=now)
        self.assertEqual(result["decision"], "warn")  # SHOULDER, not PEAK

    def test_shoulder_boundary_morning(self):
        """6:00 AM is SHOULDER."""
        now = datetime(2026, 3, 24, 6, 0)
        result = evaluate_tool_call("Agent", {}, now=now)
        self.assertEqual(result["decision"], "warn")

    def test_offpeak_boundary_evening(self):
        """6:00 PM is OFF-PEAK."""
        now = datetime(2026, 3, 24, 18, 0)
        result = evaluate_tool_call("Agent", {}, now=now)
        self.assertEqual(result["decision"], "allow")

    def test_early_morning_offpeak(self):
        """3:00 AM is OFF-PEAK."""
        now = datetime(2026, 3, 24, 3, 0)
        result = evaluate_tool_call("Agent", {}, now=now)
        self.assertEqual(result["decision"], "allow")

    # --- Env var override ---

    def test_env_override_disables_hook(self):
        """PEAK_BUDGET_HOOK_DISABLED=1 disables all blocking."""
        now = datetime(2026, 3, 24, 10, 0)  # PEAK
        with patch.dict(os.environ, {"PEAK_BUDGET_HOOK_DISABLED": "1"}):
            result = evaluate_tool_call("Agent", {}, now=now)
            self.assertEqual(result["decision"], "allow")

    def test_env_override_zero_does_not_disable(self):
        """PEAK_BUDGET_HOOK_DISABLED=0 does NOT disable."""
        now = datetime(2026, 3, 24, 10, 0)
        with patch.dict(os.environ, {"PEAK_BUDGET_HOOK_DISABLED": "0"}):
            result = evaluate_tool_call("Agent", {}, now=now)
            self.assertEqual(result["decision"], "deny")

    # --- Blocked tools list ---

    def test_blocked_tools_contains_agent(self):
        """Agent is in the blocked tools list."""
        self.assertIn("Agent", BLOCKED_TOOLS)

    def test_non_blocked_tool_always_allowed(self):
        """Tools not in BLOCKED_TOOLS are always allowed regardless of window."""
        now = datetime(2026, 3, 24, 10, 0)  # PEAK
        for tool in ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "TodoWrite"]:
            result = evaluate_tool_call(tool, {}, now=now)
            self.assertEqual(result["decision"], "allow", f"{tool} should always be allowed")


class TestHookOutput(unittest.TestCase):
    """Test that the hook produces correct JSON output for Claude Code."""

    def test_deny_output_format(self):
        """Deny output uses hookSpecificOutput.permissionDecision format."""
        now = datetime(2026, 3, 24, 10, 0)
        result = evaluate_tool_call("Agent", {}, now=now)
        self.assertEqual(result["decision"], "deny")
        # Verify the output structure matches Claude Code PreToolUse deny format
        output = result.get("hook_output")
        self.assertIsNotNone(output)
        self.assertEqual(
            output["hookSpecificOutput"]["permissionDecision"], "deny"
        )

    def test_warn_output_has_message(self):
        """Warn output includes additionalContext message."""
        now = datetime(2026, 3, 24, 15, 0)  # SHOULDER
        result = evaluate_tool_call("Agent", {}, now=now)
        self.assertEqual(result["decision"], "warn")
        output = result.get("hook_output")
        self.assertIn("additionalContext", output)

    def test_allow_output_is_empty(self):
        """Allow has no hook_output (hook exits silently)."""
        now = datetime(2026, 3, 24, 20, 0)
        result = evaluate_tool_call("Agent", {}, now=now)
        self.assertEqual(result["decision"], "allow")
        self.assertIsNone(result.get("hook_output"))


class TestHookStdinProcessing(unittest.TestCase):
    """Test the full hook as a subprocess with stdin."""

    def _run_hook(self, tool_name, env_override=None):
        """Run the hook as subprocess with mocked stdin."""
        payload = json.dumps({
            "tool_name": tool_name,
            "tool_input": {}
        })
        env = os.environ.copy()
        # Force a PEAK time for testing
        env["PEAK_BUDGET_HOOK_TEST_TIME"] = "2026-03-24T10:00:00"
        if env_override:
            env.update(env_override)

        result = subprocess.run(
            [sys.executable, os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "peak_budget_hook.py"
            )],
            input=payload,
            capture_output=True,
            text=True,
            env=env,
            timeout=5,
        )
        return result

    def test_subprocess_agent_peak_denies(self):
        """Running as subprocess with Agent during PEAK produces deny JSON."""
        result = self._run_hook("Agent")
        self.assertEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_subprocess_read_peak_silent(self):
        """Running as subprocess with Read during PEAK produces no output."""
        result = self._run_hook("Read")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")

    def test_subprocess_agent_offpeak_silent(self):
        """Running as subprocess with Agent during OFF-PEAK produces no output."""
        result = self._run_hook("Agent", {"PEAK_BUDGET_HOOK_TEST_TIME": "2026-03-24T22:00:00"})
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")

    def test_subprocess_agent_shoulder_warns(self):
        """Running as subprocess with Agent during SHOULDER produces warn."""
        result = self._run_hook("Agent", {"PEAK_BUDGET_HOOK_TEST_TIME": "2026-03-24T15:00:00"})
        self.assertEqual(result.returncode, 0)
        output = json.loads(result.stdout)
        self.assertIn("additionalContext", output)

    def test_subprocess_disabled_env(self):
        """Disabled via env var produces no output even for Agent during PEAK."""
        result = self._run_hook("Agent", {"PEAK_BUDGET_HOOK_DISABLED": "1"})
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
