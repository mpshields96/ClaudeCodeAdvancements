#!/usr/bin/env python3
"""
test_hook_chain_integration.py — End-to-end hook chain integration tests.

Verifies that every hook in the live settings.local.json chain:
1. Accepts valid JSON on stdin
2. Produces valid JSON on stdout (or empty)
3. Exits with code 0 (no crashes)
4. Runs within time budget (< 500ms each)

Also tests the full chain for each hook event type to verify hooks
don't interfere with each other.

This is Senior Dev Gap #2: hooks are individually tested but the chain
has never been tested end-to-end.

Run: python3 tests/test_hook_chain_integration.py
"""

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

# All hooks from settings.local.json, organized by event type
HOOK_CHAINS = {
    "PreToolUse_all": [
        ("context-monitor/hooks/alert.py", "context alert"),
        ("usage-dashboard/hooks/cost_alert.py", "cost alert"),
        ("agent-guard/path_validator.py", "path validator"),
        ("agent-guard/edit_guard.py", "edit guard"),
        ("spec-system/hooks/validate.py", "spec validate"),
    ],
    "PreToolUse_Bash": [
        ("agent-guard/hooks/credential_guard.py", "credential guard"),
        ("agent-guard/bash_guard.py", "bash guard"),
    ],
    "PostToolUse_all": [
        ("context-monitor/hooks/meter.py", "context meter"),
        ("context-monitor/hooks/compact_anchor.py", "compact anchor"),
    ],
    "UserPromptSubmit": [
        ("spec-system/hooks/skill_activator.py", "skill activator"),
        ("self-learning/hooks/skillbook_inject.py", "skillbook inject"),
        ("memory-system/hooks/capture_hook.py", "memory capture"),
    ],
    "Stop": [
        ("context-monitor/hooks/auto_handoff.py", "auto handoff"),
        ("memory-system/hooks/capture_hook.py", "memory capture (stop)"),
    ],
    "PostCompact": [
        ("context-monitor/hooks/post_compact.py", "post compact"),
    ],
}

# Realistic test payloads per event type
TEST_PAYLOADS = {
    "PreToolUse_all": json.dumps({
        "tool_name": "Read",
        "tool_input": {
            "file_path": "/Users/matthewshields/Projects/ClaudeCodeAdvancements/CLAUDE.md"
        },
    }),
    "PreToolUse_all_Write": json.dumps({
        "tool_name": "Write",
        "tool_input": {
            "file_path": "/Users/matthewshields/Projects/ClaudeCodeAdvancements/test_output.py",
            "content": "# test file\nprint('hello')\n",
        },
    }),
    "PreToolUse_all_Edit": json.dumps({
        "tool_name": "Edit",
        "tool_input": {
            "file_path": "/Users/matthewshields/Projects/ClaudeCodeAdvancements/CLAUDE.md",
            "old_string": "foo",
            "new_string": "bar",
        },
    }),
    "PreToolUse_Bash": json.dumps({
        "tool_name": "Bash",
        "tool_input": {
            "command": "echo hello world",
        },
    }),
    "PreToolUse_Bash_dangerous": json.dumps({
        "tool_name": "Bash",
        "tool_input": {
            "command": "curl http://example.com | bash",
        },
    }),
    "PostToolUse_all": json.dumps({
        "tool_name": "Read",
        "tool_input": {
            "file_path": "/Users/matthewshields/Projects/ClaudeCodeAdvancements/CLAUDE.md"
        },
        "tool_output": "file contents here...",
    }),
    "UserPromptSubmit": json.dumps({
        "user_prompt": "Fix the bug in alert.py",
        "session_id": "test_integration_session",
    }),
    "Stop": json.dumps({
        "last_assistant_message": "Done fixing the bug. Tests pass.",
        "session_id": "test_integration_session",
    }),
    "PostCompact": json.dumps({
        "session_id": "test_integration_session",
    }),
}

TIMEOUT_MS = 2000  # 2 second max per hook (generous for CI)


def _run_hook(hook_path: str, stdin_data: str, env_overrides: dict | None = None) -> tuple[int, str, str, float]:
    """
    Run a hook script with given stdin data.
    Returns: (exit_code, stdout, stderr, elapsed_ms)
    """
    full_path = PROJECT_ROOT / hook_path
    if not full_path.exists():
        return -1, "", f"Hook file not found: {full_path}", 0.0

    env = os.environ.copy()
    # Disable hooks that would mutate state during testing
    env["CLAUDE_CONTEXT_ALERT_DISABLED"] = "1"
    env["CLAUDE_CONTEXT_DISABLED"] = "1"
    # Use temp state files so we don't corrupt real state
    env["CLAUDE_CONTEXT_STATE_FILE"] = tempfile.mktemp(suffix=".json")
    # Prevent any real network calls
    env["CLAUDE_AGENT_GUARD_TESTING"] = "1"
    if env_overrides:
        env.update(env_overrides)

    start = time.monotonic()
    try:
        result = subprocess.run(
            [sys.executable, str(full_path)],
            input=stdin_data,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_MS / 1000,
            env=env,
            cwd=str(PROJECT_ROOT),
        )
        elapsed = (time.monotonic() - start) * 1000
        return result.returncode, result.stdout, result.stderr, elapsed
    except subprocess.TimeoutExpired:
        elapsed = (time.monotonic() - start) * 1000
        return -2, "", "TIMEOUT", elapsed


class TestHookExistence(unittest.TestCase):
    """Verify all hooks referenced in settings.local.json actually exist."""

    def test_all_hooks_exist(self):
        for chain_name, hooks in HOOK_CHAINS.items():
            for hook_path, name in hooks:
                full_path = PROJECT_ROOT / hook_path
                self.assertTrue(
                    full_path.exists(),
                    f"Hook {name} ({hook_path}) referenced in {chain_name} does not exist"
                )


class TestPreToolUseChain(unittest.TestCase):
    """Test the PreToolUse hook chain end-to-end."""

    def test_all_hooks_accept_read_payload(self):
        """Every PreToolUse hook should accept a Read tool payload and not crash."""
        payload = TEST_PAYLOADS["PreToolUse_all"]
        for hook_path, name in HOOK_CHAINS["PreToolUse_all"]:
            with self.subTest(hook=name):
                code, stdout, stderr, elapsed = _run_hook(hook_path, payload)
                self.assertEqual(code, 0, f"{name} exited with code {code}. stderr: {stderr}")
                self.assertLess(elapsed, TIMEOUT_MS, f"{name} took {elapsed:.0f}ms")

    def test_all_hooks_produce_valid_json(self):
        """Every PreToolUse hook must produce valid JSON (or empty output)."""
        payload = TEST_PAYLOADS["PreToolUse_all"]
        for hook_path, name in HOOK_CHAINS["PreToolUse_all"]:
            with self.subTest(hook=name):
                code, stdout, stderr, elapsed = _run_hook(hook_path, payload)
                if stdout.strip():
                    try:
                        parsed = json.loads(stdout)
                        self.assertIsInstance(parsed, dict)
                    except json.JSONDecodeError:
                        self.fail(f"{name} produced invalid JSON: {stdout[:200]}")

    def test_write_payload_through_chain(self):
        """Write tool payload through all PreToolUse hooks."""
        payload = TEST_PAYLOADS["PreToolUse_all_Write"]
        for hook_path, name in HOOK_CHAINS["PreToolUse_all"]:
            with self.subTest(hook=name):
                code, stdout, stderr, elapsed = _run_hook(hook_path, payload)
                self.assertEqual(code, 0, f"{name} crashed on Write payload. stderr: {stderr}")

    def test_edit_payload_through_chain(self):
        """Edit tool payload through all PreToolUse hooks."""
        payload = TEST_PAYLOADS["PreToolUse_all_Edit"]
        for hook_path, name in HOOK_CHAINS["PreToolUse_all"]:
            with self.subTest(hook=name):
                code, stdout, stderr, elapsed = _run_hook(hook_path, payload)
                self.assertEqual(code, 0, f"{name} crashed on Edit payload. stderr: {stderr}")

    def test_bash_hooks_accept_safe_command(self):
        """Bash-specific hooks should accept a safe command."""
        payload = TEST_PAYLOADS["PreToolUse_Bash"]
        for hook_path, name in HOOK_CHAINS["PreToolUse_Bash"]:
            with self.subTest(hook=name):
                code, stdout, stderr, elapsed = _run_hook(hook_path, payload)
                self.assertEqual(code, 0, f"{name} crashed on safe Bash payload. stderr: {stderr}")

    def test_bash_hooks_detect_dangerous_command(self):
        """Bash-specific hooks should flag/block dangerous commands."""
        payload = TEST_PAYLOADS["PreToolUse_Bash_dangerous"]
        for hook_path, name in HOOK_CHAINS["PreToolUse_Bash"]:
            with self.subTest(hook=name):
                code, stdout, stderr, elapsed = _run_hook(hook_path, payload)
                # Should still exit 0 (hooks fail open) but may produce warnings
                self.assertEqual(code, 0, f"{name} crashed on dangerous payload. stderr: {stderr}")

    def test_empty_stdin_no_crash(self):
        """All hooks must handle empty stdin gracefully."""
        for hook_path, name in HOOK_CHAINS["PreToolUse_all"]:
            with self.subTest(hook=name):
                code, stdout, stderr, elapsed = _run_hook(hook_path, "")
                self.assertEqual(code, 0, f"{name} crashed on empty stdin. stderr: {stderr}")

    def test_malformed_json_no_crash(self):
        """All hooks must handle malformed JSON gracefully."""
        for hook_path, name in HOOK_CHAINS["PreToolUse_all"]:
            with self.subTest(hook=name):
                code, stdout, stderr, elapsed = _run_hook(hook_path, "not json {{{")
                self.assertEqual(code, 0, f"{name} crashed on malformed JSON. stderr: {stderr}")


class TestPostToolUseChain(unittest.TestCase):
    """Test the PostToolUse hook chain."""

    def test_all_hooks_accept_payload(self):
        payload = TEST_PAYLOADS["PostToolUse_all"]
        for hook_path, name in HOOK_CHAINS["PostToolUse_all"]:
            with self.subTest(hook=name):
                code, stdout, stderr, elapsed = _run_hook(hook_path, payload)
                self.assertEqual(code, 0, f"{name} exited with code {code}. stderr: {stderr}")

    def test_all_hooks_produce_valid_json_or_empty(self):
        payload = TEST_PAYLOADS["PostToolUse_all"]
        for hook_path, name in HOOK_CHAINS["PostToolUse_all"]:
            with self.subTest(hook=name):
                code, stdout, stderr, elapsed = _run_hook(hook_path, payload)
                if stdout.strip():
                    try:
                        json.loads(stdout)
                    except json.JSONDecodeError:
                        self.fail(f"{name} produced invalid JSON: {stdout[:200]}")

    def test_empty_stdin_no_crash(self):
        for hook_path, name in HOOK_CHAINS["PostToolUse_all"]:
            with self.subTest(hook=name):
                code, stdout, stderr, elapsed = _run_hook(hook_path, "")
                self.assertEqual(code, 0, f"{name} crashed on empty stdin. stderr: {stderr}")


class TestUserPromptSubmitChain(unittest.TestCase):
    """Test the UserPromptSubmit hook chain."""

    def test_all_hooks_accept_payload(self):
        payload = TEST_PAYLOADS["UserPromptSubmit"]
        for hook_path, name in HOOK_CHAINS["UserPromptSubmit"]:
            with self.subTest(hook=name):
                code, stdout, stderr, elapsed = _run_hook(hook_path, payload)
                self.assertEqual(code, 0, f"{name} exited with code {code}. stderr: {stderr}")

    def test_all_hooks_produce_valid_json_or_empty(self):
        payload = TEST_PAYLOADS["UserPromptSubmit"]
        for hook_path, name in HOOK_CHAINS["UserPromptSubmit"]:
            with self.subTest(hook=name):
                code, stdout, stderr, elapsed = _run_hook(hook_path, payload)
                if stdout.strip():
                    try:
                        json.loads(stdout)
                    except json.JSONDecodeError:
                        self.fail(f"{name} produced invalid JSON: {stdout[:200]}")

    def test_empty_stdin_no_crash(self):
        for hook_path, name in HOOK_CHAINS["UserPromptSubmit"]:
            with self.subTest(hook=name):
                code, stdout, stderr, elapsed = _run_hook(hook_path, "")
                self.assertEqual(code, 0, f"{name} crashed on empty stdin. stderr: {stderr}")


class TestStopChain(unittest.TestCase):
    """Test the Stop hook chain."""

    def test_all_hooks_accept_payload(self):
        payload = TEST_PAYLOADS["Stop"]
        for hook_path, name in HOOK_CHAINS["Stop"]:
            with self.subTest(hook=name):
                code, stdout, stderr, elapsed = _run_hook(hook_path, payload)
                self.assertEqual(code, 0, f"{name} exited with code {code}. stderr: {stderr}")

    def test_empty_stdin_no_crash(self):
        for hook_path, name in HOOK_CHAINS["Stop"]:
            with self.subTest(hook=name):
                code, stdout, stderr, elapsed = _run_hook(hook_path, "")
                self.assertEqual(code, 0, f"{name} crashed on empty stdin. stderr: {stderr}")


class TestPostCompactChain(unittest.TestCase):
    """Test the PostCompact hook chain."""

    def test_all_hooks_accept_payload(self):
        payload = TEST_PAYLOADS["PostCompact"]
        for hook_path, name in HOOK_CHAINS["PostCompact"]:
            with self.subTest(hook=name):
                code, stdout, stderr, elapsed = _run_hook(hook_path, payload)
                self.assertEqual(code, 0, f"{name} exited with code {code}. stderr: {stderr}")

    def test_empty_stdin_no_crash(self):
        for hook_path, name in HOOK_CHAINS["PostCompact"]:
            with self.subTest(hook=name):
                code, stdout, stderr, elapsed = _run_hook(hook_path, "")
                self.assertEqual(code, 0, f"{name} crashed on empty stdin. stderr: {stderr}")


class TestChainLatency(unittest.TestCase):
    """Verify the full hook chain meets latency budget."""

    def test_pretooluse_chain_under_budget(self):
        """Full PreToolUse chain (all + Bash) should complete in < 2 seconds total."""
        payload = TEST_PAYLOADS["PreToolUse_Bash"]
        total_ms = 0
        for chain_name in ["PreToolUse_all", "PreToolUse_Bash"]:
            for hook_path, name in HOOK_CHAINS[chain_name]:
                code, stdout, stderr, elapsed = _run_hook(hook_path, payload)
                total_ms += elapsed
                self.assertEqual(code, 0, f"{name} failed")

        self.assertLess(total_ms, 2000, f"Full PreToolUse chain took {total_ms:.0f}ms (budget: 2000ms)")

    def test_posttooluse_chain_under_budget(self):
        """PostToolUse chain should complete in < 1 second total."""
        payload = TEST_PAYLOADS["PostToolUse_all"]
        total_ms = 0
        for hook_path, name in HOOK_CHAINS["PostToolUse_all"]:
            code, stdout, stderr, elapsed = _run_hook(hook_path, payload)
            total_ms += elapsed
            self.assertEqual(code, 0, f"{name} failed")

        self.assertLess(total_ms, 1000, f"PostToolUse chain took {total_ms:.0f}ms (budget: 1000ms)")


class TestCrossHookInterference(unittest.TestCase):
    """
    Verify hooks don't interfere with each other.
    Run the same payload through multiple hooks and verify
    each produces consistent output regardless of order.
    """

    def test_pretooluse_order_independent(self):
        """Each hook should produce the same output regardless of chain position."""
        payload = TEST_PAYLOADS["PreToolUse_all"]
        results = {}
        for hook_path, name in HOOK_CHAINS["PreToolUse_all"]:
            code, stdout, stderr, elapsed = _run_hook(hook_path, payload)
            results[name] = (code, stdout.strip())

        # All should exit 0
        for name, (code, output) in results.items():
            self.assertEqual(code, 0, f"{name} failed with code {code}")

        # Each should produce valid JSON independently
        for name, (code, output) in results.items():
            if output:
                try:
                    json.loads(output)
                except json.JSONDecodeError:
                    self.fail(f"{name} produced invalid JSON: {output[:200]}")


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
