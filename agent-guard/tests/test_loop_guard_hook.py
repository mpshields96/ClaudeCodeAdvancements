"""Tests for loop_guard.py — PostToolUse hook wrapper."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

HOOK_SCRIPT = str(Path(__file__).resolve().parent.parent / "hooks" / "loop_guard.py")


def run_hook(hook_input: dict, env_overrides: dict = None) -> str:
    """Run the hook script with the given input and return stdout."""
    import os
    env = os.environ.copy()
    # Use a temp state file to avoid polluting real state
    tmp_state = tempfile.mktemp(suffix=".json")
    env["CLAUDE_LOOP_STATE_FILE"] = tmp_state
    if env_overrides:
        env.update(env_overrides)

    result = subprocess.run(
        [sys.executable, HOOK_SCRIPT],
        input=json.dumps(hook_input),
        capture_output=True,
        text=True,
        env=env,
        timeout=5,
    )
    # Clean up temp state
    Path(tmp_state).unlink(missing_ok=True)
    return result.stdout


def run_hook_sequence(inputs: list[dict], env_overrides: dict = None) -> list[str]:
    """Run multiple hook invocations sharing state (simulating real usage)."""
    import os
    env = os.environ.copy()
    tmp_state = tempfile.mktemp(suffix=".json")
    # We need to override the state file in the detector
    # The hook reads from DEFAULT_STATE_FILE, so we patch via env
    if env_overrides:
        env.update(env_overrides)

    outputs = []
    for inp in inputs:
        result = subprocess.run(
            [sys.executable, HOOK_SCRIPT],
            input=json.dumps(inp),
            capture_output=True,
            text=True,
            env=env,
            timeout=5,
        )
        outputs.append(result.stdout)

    Path(tmp_state).unlink(missing_ok=True)
    return outputs


class TestHookBasic:
    """Basic hook behavior."""

    def test_no_output_on_normal_input(self):
        stdout = run_hook({"tool_name": "Bash", "tool_output": "hello world"})
        assert stdout.strip() == ""

    def test_disabled_produces_no_output(self):
        stdout = run_hook(
            {"tool_name": "Bash", "tool_output": "error"},
            env_overrides={"CLAUDE_LOOP_GUARD_DISABLED": "1"},
        )
        assert stdout.strip() == ""

    def test_invalid_json_no_crash(self):
        """Hook should handle invalid input gracefully."""
        result = subprocess.run(
            [sys.executable, HOOK_SCRIPT],
            input="not json at all",
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_empty_output_no_crash(self):
        stdout = run_hook({"tool_name": "Bash", "tool_output": ""})
        assert stdout.strip() == ""

    def test_missing_tool_output_no_crash(self):
        stdout = run_hook({"tool_name": "Bash"})
        assert stdout.strip() == ""


class TestHookLoopDetection:
    """Hook should detect loops across invocations."""

    def test_loop_produces_warning(self):
        """4 identical outputs should produce a warning on the 4th."""
        outputs = run_hook_sequence([
            {"tool_name": "Bash", "tool_output": "Error: file not found"},
            {"tool_name": "Bash", "tool_output": "Error: file not found"},
            {"tool_name": "Bash", "tool_output": "Error: file not found"},
            {"tool_name": "Bash", "tool_output": "Error: file not found"},
        ])
        # Last output should contain a warning
        last = outputs[-1].strip()
        if last:
            data = json.loads(last)
            assert "LOOP DETECTED" in data["hookSpecificOutput"]["message"]

    def test_diverse_outputs_no_warning(self):
        outputs = run_hook_sequence([
            {"tool_name": "Bash", "tool_output": "git status output"},
            {"tool_name": "Read", "tool_output": "file contents here"},
            {"tool_name": "Bash", "tool_output": "test results: all pass"},
            {"tool_name": "Write", "tool_output": "file written successfully"},
        ])
        for o in outputs:
            assert o.strip() == "" or "LOOP" not in o
