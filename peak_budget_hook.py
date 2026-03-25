#!/usr/bin/env python3
"""MT-38 Phase 3: Peak Budget PreToolUse Hook.

Blocks expensive tool calls (Agent spawns) during PEAK hours to conserve
rate limits. Warns during SHOULDER. Allows freely during OFF-PEAK/weekend.

Uses token_budget.py's get_budget() for time window detection.

Wire as PreToolUse hook in settings.local.json:
  {
    "hooks": {
      "PreToolUse": [{
        "matcher": "",
        "hooks": [{"type": "command", "command": "python3 .../peak_budget_hook.py"}]
      }]
    }
  }

Environment variables:
  PEAK_BUDGET_HOOK_DISABLED   - Set "1" to disable entirely
  PEAK_BUDGET_HOOK_TEST_TIME  - ISO datetime override for testing (e.g. "2026-03-24T10:00:00")
"""

import json
import os
import sys
from datetime import datetime

# Import get_budget from token_budget.py (same directory)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from token_budget import get_budget

# Tools that get blocked during PEAK / warned during SHOULDER.
# Agent is the expensive one (~100-150k tokens per spawn).
BLOCKED_TOOLS = frozenset({"Agent"})


def evaluate_tool_call(tool_name, tool_input, now=None):
    """Evaluate whether a tool call should be allowed, warned, or denied.

    Args:
        tool_name: The Claude Code tool being called
        tool_input: The tool's input parameters (unused for now)
        now: datetime override for testing

    Returns:
        dict with keys:
          - decision: "allow" | "warn" | "deny"
          - reason: human-readable explanation (only if warn/deny)
          - hook_output: JSON to print to stdout (only if warn/deny)
    """
    # Check disabled env var
    if os.environ.get("PEAK_BUDGET_HOOK_DISABLED") == "1":
        return {"decision": "allow"}

    # Non-blocked tools are always allowed
    if tool_name not in BLOCKED_TOOLS:
        return {"decision": "allow"}

    # Get current budget window
    budget = get_budget(now=now)
    window = budget["window"]

    if window == "PEAK":
        reason = (
            f"PEAK hours ({budget['hours']}). Agent spawns blocked to conserve rate limits. "
            f"Use gsd:quick instead, or wait for off-peak."
        )
        return {
            "decision": "deny",
            "reason": reason,
            "hook_output": {
                "hookSpecificOutput": {
                    "permissionDecision": "deny",
                    "reason": reason,
                }
            },
        }
    elif window == "SHOULDER":
        reason = (
            f"SHOULDER hours ({budget['hours']}). Single agent spawn allowed but avoid parallel spawns. "
            f"Budget: {budget['budget_pct']}%."
        )
        return {
            "decision": "warn",
            "reason": reason,
            "hook_output": {
                "additionalContext": f"[PEAK BUDGET] {reason}",
            },
        }
    else:
        # OFF-PEAK — allow silently
        return {"decision": "allow"}


def main():
    """Hook entry point — reads stdin, evaluates, prints output."""
    try:
        payload = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        # Malformed input — fail open
        sys.exit(0)

    tool_name = payload.get("tool_name", "")

    # Test time override
    test_time = os.environ.get("PEAK_BUDGET_HOOK_TEST_TIME")
    now = datetime.fromisoformat(test_time) if test_time else None

    result = evaluate_tool_call(tool_name, payload.get("tool_input", {}), now=now)

    if result.get("hook_output"):
        print(json.dumps(result["hook_output"]))


if __name__ == "__main__":
    main()
