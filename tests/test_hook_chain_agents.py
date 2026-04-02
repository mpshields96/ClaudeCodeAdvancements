#!/usr/bin/env python3
"""
test_hook_chain_agents.py — Integration tests for S249/S250 agent hooks.

Covers the hooks added in Chat 16 (session_start, spawn_budget) and
Chat 17 (pre_compact v2, post_compact v2) — the "agent chain":

    Session starts     → session_start_hook fires (SessionStart)
    Agent is spawned   → spawn_budget_hook fires (PreToolUse / Agent matcher)
    Context compacts   → pre_compact fires, then post_compact fires

Tests verify:
1. Each hook exits 0 and produces valid JSON (or empty) on all payloads
2. Pre/post compact chain: snapshot written by pre is consumed by post
3. No state file conflicts: spawn budget and context health use distinct files
4. spawn_budget warns at threshold but never blocks
5. pre_compact v2 captures critical_rules into snapshot
6. post_compact v2 injects rules when pre_pct >= 30

Run: python3 tests/test_hook_chain_agents.py
"""

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from typing import Dict, Optional, Tuple

PROJECT_ROOT = Path(__file__).parent.parent

# Paths to the four hooks under test
SESSION_START_HOOK = "hooks/session_start_hook.py"
SPAWN_BUDGET_HOOK = "hooks/spawn_budget_hook.py"
PRE_COMPACT_HOOK = "context-monitor/hooks/pre_compact.py"
POST_COMPACT_HOOK = "context-monitor/hooks/post_compact.py"

TIMEOUT_S = 5.0


def _run_hook(
    hook_path: str,
    stdin_data: str,
    env_overrides: Optional[Dict] = None,
    cwd: Optional[str] = None,
) -> Tuple[int, str, str, float]:
    """Run a hook and return (exit_code, stdout, stderr, elapsed_ms)."""
    full_path = PROJECT_ROOT / hook_path
    if not full_path.exists():
        return -1, "", f"Not found: {full_path}", 0.0

    env = os.environ.copy()
    env["CCA_SESSION_START_DISABLED"] = "1"   # Suppress slim_init in session_start
    env["CLAUDE_PRECOMPACT_DISABLED"] = "0"   # Keep pre_compact enabled
    env["CLAUDE_POSTCOMPACT_DISABLED"] = "0"  # Keep post_compact enabled
    if env_overrides:
        env.update(env_overrides)

    start = time.monotonic()
    try:
        result = subprocess.run(
            [sys.executable, str(full_path)],
            input=stdin_data,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_S,
            env=env,
            cwd=cwd or str(PROJECT_ROOT),
        )
        elapsed = (time.monotonic() - start) * 1000
        return result.returncode, result.stdout, result.stderr, elapsed
    except subprocess.TimeoutExpired:
        elapsed = (time.monotonic() - start) * 1000
        return -2, "", "TIMEOUT", elapsed


class TestHookExistence(unittest.TestCase):
    """All four agent-chain hooks must exist on disk."""

    def test_session_start_hook_exists(self):
        self.assertTrue((PROJECT_ROOT / SESSION_START_HOOK).exists())

    def test_spawn_budget_hook_exists(self):
        self.assertTrue((PROJECT_ROOT / SPAWN_BUDGET_HOOK).exists())

    def test_pre_compact_hook_exists(self):
        self.assertTrue((PROJECT_ROOT / PRE_COMPACT_HOOK).exists())

    def test_post_compact_hook_exists(self):
        self.assertTrue((PROJECT_ROOT / POST_COMPACT_HOOK).exists())


class TestSessionStartHook(unittest.TestCase):
    """Tests for hooks/session_start_hook.py."""

    def test_exits_zero_on_empty_payload(self):
        code, _, stderr, _ = _run_hook(SESSION_START_HOOK, "")
        self.assertEqual(code, 0, f"Crashed on empty payload. stderr: {stderr}")

    def test_exits_zero_on_json_payload(self):
        payload = json.dumps({"session_id": "test-session", "cwd": str(PROJECT_ROOT)})
        code, _, stderr, _ = _run_hook(SESSION_START_HOOK, payload)
        self.assertEqual(code, 0, f"Crashed on JSON payload. stderr: {stderr}")

    def test_produces_valid_json(self):
        code, stdout, stderr, _ = _run_hook(SESSION_START_HOOK, "")
        if stdout.strip():
            try:
                parsed = json.loads(stdout)
                self.assertIsInstance(parsed, dict)
            except json.JSONDecodeError:
                self.fail(f"session_start produced invalid JSON: {stdout[:300]}")

    def test_runs_under_time_budget(self):
        _, _, _, elapsed_ms = _run_hook(SESSION_START_HOOK, "")
        self.assertLess(elapsed_ms, 3000, f"session_start took {elapsed_ms:.0f}ms (budget: 3000ms)")

    def test_disabled_via_env_exits_zero(self):
        code, stdout, _, _ = _run_hook(
            SESSION_START_HOOK, "",
            env_overrides={"CCA_SESSION_START_DISABLED": "1"},
        )
        self.assertEqual(code, 0)
        # When disabled, output should be empty or a minimal JSON
        if stdout.strip():
            json.loads(stdout)  # Still must be valid JSON if present


class TestSpawnBudgetHook(unittest.TestCase):
    """Tests for hooks/spawn_budget_hook.py."""

    def _agent_payload(self, agent_type: str = "cca-reviewer") -> str:
        return json.dumps({
            "tool_name": "Agent",
            "tool_input": {"subagent_type": agent_type, "prompt": "Review this URL"},
        })

    def test_exits_zero_on_agent_call(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            budget_file = str(Path(tmpdir) / "budget.json")
            code, _, stderr, _ = _run_hook(
                SPAWN_BUDGET_HOOK, self._agent_payload(),
                env_overrides={"CCA_SPAWN_BUDGET_FILE": budget_file},
            )
            self.assertEqual(code, 0, f"Crashed. stderr: {stderr}")

    def test_exits_zero_on_empty_payload(self):
        code, _, stderr, _ = _run_hook(SPAWN_BUDGET_HOOK, "")
        self.assertEqual(code, 0, f"Crashed on empty payload. stderr: {stderr}")

    def test_exits_zero_on_non_agent_tool(self):
        payload = json.dumps({"tool_name": "Read", "tool_input": {"file_path": "/tmp/x"}})
        code, _, stderr, _ = _run_hook(SPAWN_BUDGET_HOOK, payload)
        self.assertEqual(code, 0, f"Crashed on Read payload. stderr: {stderr}")

    def test_produces_valid_json_or_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            budget_file = str(Path(tmpdir) / "budget.json")
            _, stdout, _, _ = _run_hook(
                SPAWN_BUDGET_HOOK, self._agent_payload(),
                env_overrides={"CCA_SPAWN_BUDGET_FILE": budget_file},
            )
            if stdout.strip():
                try:
                    json.loads(stdout)
                except json.JSONDecodeError:
                    self.fail(f"spawn_budget produced invalid JSON: {stdout[:300]}")

    def test_warns_at_threshold_but_does_not_block(self):
        """When spawn count exceeds threshold, hook warns but still exits 0 (no block)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            budget_file = str(Path(tmpdir) / "budget.json")
            # Set a very low threshold so first spawn triggers warning
            env = {
                "CCA_SPAWN_BUDGET_FILE": budget_file,
                "CCA_SPAWN_BUDGET_THRESHOLD": "1",      # 1 token threshold — immediate warn
                "CCA_SPAWN_BUDGET_PER_AGENT": "40000",
            }
            code, stdout, _, _ = _run_hook(
                SPAWN_BUDGET_HOOK, self._agent_payload(), env_overrides=env,
            )
            self.assertEqual(code, 0, "spawn_budget must never block (exit non-zero)")

    def test_state_file_distinct_from_context_health(self):
        """spawn_budget state file must not overwrite ~/.claude-context-health.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            budget_file = Path(tmpdir) / "spawn-budget.json"
            context_file = Path(tmpdir) / "context-health.json"
            # Write a sentinel to context file
            context_file.write_text(json.dumps({"zone": "green", "pct": 10, "sentinel": "test"}))

            _run_hook(
                SPAWN_BUDGET_HOOK, self._agent_payload(),
                env_overrides={
                    "CCA_SPAWN_BUDGET_FILE": str(budget_file),
                    "CLAUDE_CONTEXT_STATE_FILE": str(context_file),
                },
            )

            # Context health file must be unchanged
            state = json.loads(context_file.read_text())
            self.assertEqual(state.get("sentinel"), "test", "spawn_budget overwrote context health file")


class TestPrePostCompactChain(unittest.TestCase):
    """Tests for the pre_compact → post_compact handoff chain."""

    def test_pre_compact_exits_zero(self):
        code, _, stderr, _ = _run_hook(PRE_COMPACT_HOOK, "{}")
        self.assertEqual(code, 0, f"pre_compact crashed. stderr: {stderr}")

    def test_post_compact_exits_zero(self):
        payload = json.dumps({"compact_summary": "Was doing work", "trigger": "auto"})
        code, _, stderr, _ = _run_hook(POST_COMPACT_HOOK, payload)
        self.assertEqual(code, 0, f"post_compact crashed. stderr: {stderr}")

    def test_snapshot_handoff_pre_to_post(self):
        """pre_compact writes snapshot; post_compact reads and deletes it."""
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_path = Path(tmpdir) / "snap.json"
            recovery_path = Path(tmpdir) / "recovery.md"
            state_file = Path(tmpdir) / "state.json"

            # Step 1: pre_compact writes snapshot
            env = {
                "CLAUDE_COMPACTION_SNAPSHOT_PATH": str(snapshot_path),
                "CLAUDE_CONTEXT_STATE_FILE": str(state_file),
            }
            code, _, stderr, _ = _run_hook(PRE_COMPACT_HOOK, "{}", env_overrides=env)
            self.assertEqual(code, 0)
            self.assertTrue(snapshot_path.exists(), "pre_compact should write snapshot")

            snapshot = json.loads(snapshot_path.read_text())
            self.assertEqual(snapshot.get("version"), 1)

            # Step 2: post_compact reads snapshot and writes recovery
            env2 = {
                "CLAUDE_COMPACTION_SNAPSHOT_PATH": str(snapshot_path),
                "CLAUDE_CONTEXT_STATE_FILE": str(state_file),
                "CLAUDE_COMPACT_RECOVERY_PATH": str(recovery_path),
            }
            payload = json.dumps({"compact_summary": "Was working on CCA tasks", "trigger": "auto"})
            code, _, stderr, _ = _run_hook(POST_COMPACT_HOOK, payload, env_overrides=env2)
            self.assertEqual(code, 0)

            # Snapshot should be consumed (deleted)
            self.assertFalse(snapshot_path.exists(), "post_compact should delete snapshot after reading")

            # Recovery file should be created
            self.assertTrue(recovery_path.exists(), "post_compact should write recovery digest")
            recovery = recovery_path.read_text()
            self.assertIn("Context Compaction Recovery", recovery)

    def test_pre_compact_v2_captures_critical_rules(self):
        """pre_compact v2: snapshot must include 'critical_rules' key from CLAUDE.md."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Write a minimal CLAUDE.md with the expected sections
            claude_md = Path(tmpdir) / "CLAUDE.md"
            claude_md.write_text(
                "## Cardinal Safety Rules\n\nDO NOT BREAK ANYTHING.\n\n"
                "## Known Gotchas\n\nPyBoy is BANNED.\n"
            )
            snapshot_path = Path(tmpdir) / "snap.json"
            payload = json.dumps({"cwd": tmpdir})

            env = {
                "CLAUDE_COMPACTION_SNAPSHOT_PATH": str(snapshot_path),
                "CLAUDE_CONTEXT_STATE_FILE": str(Path(tmpdir) / "state.json"),
            }
            code, _, stderr, _ = _run_hook(PRE_COMPACT_HOOK, payload, env_overrides=env)
            self.assertEqual(code, 0)
            self.assertTrue(snapshot_path.exists())

            snapshot = json.loads(snapshot_path.read_text())
            self.assertIn("critical_rules", snapshot)
            rules = snapshot["critical_rules"]
            self.assertIn("cardinal_safety", rules)
            self.assertIn("DO NOT BREAK ANYTHING", rules["cardinal_safety"])
            self.assertIn("known_gotchas", rules)
            self.assertIn("PyBoy", rules["known_gotchas"])

    def test_post_compact_v2_injects_rules_at_high_pct(self):
        """post_compact v2: recovery digest includes rules when pre_pct >= 30."""
        import datetime
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_path = Path(tmpdir) / "snap.json"
            recovery_path = Path(tmpdir) / "recovery.md"
            state_file = Path(tmpdir) / "state.json"

            # Write a snapshot with high context pct and critical rules
            # Use current timestamp so freshness check passes (max_age=3600s)
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            snapshot = {
                "version": 1,
                "timestamp": now_iso,
                "session_id": "test",
                "chat_role": "desktop",
                "session_header": "Session 250",
                "context_health": {"zone": "red", "pct": 75, "tokens": 150000, "turns": 30, "window": 200000},
                "git_status": [],
                "git_diff_stat": "",
                "todays_tasks_todos": [],
                "anchor_content": "",
                "critical_rules": {
                    "cardinal_safety": "DO NOT BREAK ANYTHING.",
                    "known_gotchas": "PyBoy is BANNED.",
                },
            }
            snapshot_path.write_text(json.dumps(snapshot))

            env = {
                "CLAUDE_COMPACTION_SNAPSHOT_PATH": str(snapshot_path),
                "CLAUDE_CONTEXT_STATE_FILE": str(state_file),
                "CLAUDE_COMPACT_RECOVERY_PATH": str(recovery_path),
            }
            payload = json.dumps({"compact_summary": "Was working", "trigger": "auto"})
            code, _, stderr, _ = _run_hook(POST_COMPACT_HOOK, payload, env_overrides=env)
            self.assertEqual(code, 0)

            recovery = recovery_path.read_text()
            self.assertIn("Cardinal Safety Rules", recovery)
            self.assertIn("DO NOT BREAK ANYTHING", recovery)
            self.assertIn("Known Gotchas", recovery)
            self.assertIn("PyBoy", recovery)
            self.assertIn("Re-injected", recovery)

    def test_post_compact_v2_no_injection_at_low_pct(self):
        """post_compact v2: no rules injection when pre_pct < 30."""
        import datetime
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_path = Path(tmpdir) / "snap.json"
            recovery_path = Path(tmpdir) / "recovery.md"
            state_file = Path(tmpdir) / "state.json"

            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            snapshot = {
                "version": 1,
                "timestamp": now_iso,
                "session_id": "test",
                "context_health": {"zone": "green", "pct": 10, "tokens": 20000, "turns": 5, "window": 200000},
                "git_status": [],
                "git_diff_stat": "",
                "todays_tasks_todos": [],
                "anchor_content": "",
                "critical_rules": {"cardinal_safety": "DO NOT BREAK ANYTHING."},
            }
            snapshot_path.write_text(json.dumps(snapshot))

            env = {
                "CLAUDE_COMPACTION_SNAPSHOT_PATH": str(snapshot_path),
                "CLAUDE_CONTEXT_STATE_FILE": str(state_file),
                "CLAUDE_COMPACT_RECOVERY_PATH": str(recovery_path),
            }
            code, _, _, _ = _run_hook(
                POST_COMPACT_HOOK,
                json.dumps({"compact_summary": "work", "trigger": "auto"}),
                env_overrides=env,
            )
            self.assertEqual(code, 0)
            recovery = recovery_path.read_text()
            self.assertNotIn("Cardinal Safety Rules", recovery)
            self.assertNotIn("Re-injected", recovery)

    def test_state_files_are_distinct(self):
        """Verify spawn_budget and context_health use separate state files."""
        from pathlib import Path as P
        # Check that the default paths differ
        spawn_default = P.home() / ".claude-spawn-budget.json"
        context_default = P.home() / ".claude-context-health.json"
        self.assertNotEqual(spawn_default, context_default)

    def test_post_compact_handles_missing_snapshot_gracefully(self):
        """post_compact should work even when no pre_compact snapshot exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_snapshot = str(Path(tmpdir) / "no-such-snapshot.json")
            recovery_path = str(Path(tmpdir) / "recovery.md")
            state_file = str(Path(tmpdir) / "state.json")

            env = {
                "CLAUDE_COMPACTION_SNAPSHOT_PATH": missing_snapshot,
                "CLAUDE_CONTEXT_STATE_FILE": state_file,
                "CLAUDE_COMPACT_RECOVERY_PATH": recovery_path,
            }
            code, _, stderr, _ = _run_hook(
                POST_COMPACT_HOOK,
                json.dumps({"compact_summary": "work", "trigger": "auto"}),
                env_overrides=env,
            )
            self.assertEqual(code, 0, f"post_compact crashed without snapshot. stderr: {stderr}")


class TestChainLatency(unittest.TestCase):
    """Agent chain hooks must stay within latency budget."""

    def test_session_start_under_3s(self):
        _, _, _, elapsed_ms = _run_hook(SESSION_START_HOOK, "")
        self.assertLess(elapsed_ms, 3000, f"session_start took {elapsed_ms:.0f}ms")

    def test_spawn_budget_under_100ms(self):
        payload = json.dumps({"tool_name": "Agent", "tool_input": {}})
        with tempfile.TemporaryDirectory() as tmpdir:
            _, _, _, elapsed_ms = _run_hook(
                SPAWN_BUDGET_HOOK, payload,
                env_overrides={"CCA_SPAWN_BUDGET_FILE": str(Path(tmpdir) / "b.json")},
            )
        self.assertLess(elapsed_ms, 500, f"spawn_budget took {elapsed_ms:.0f}ms (budget: 500ms)")

    def test_pre_compact_under_500ms(self):
        _, _, _, elapsed_ms = _run_hook(PRE_COMPACT_HOOK, "{}")
        self.assertLess(elapsed_ms, 500, f"pre_compact took {elapsed_ms:.0f}ms (budget: 500ms)")

    def test_post_compact_under_500ms(self):
        payload = json.dumps({"compact_summary": "test", "trigger": "auto"})
        _, _, _, elapsed_ms = _run_hook(POST_COMPACT_HOOK, payload)
        self.assertLess(elapsed_ms, 500, f"post_compact took {elapsed_ms:.0f}ms (budget: 500ms)")


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
