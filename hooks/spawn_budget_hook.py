"""
Spawn Budget Hook — PreToolUse hook that tracks agent spawns and warns at threshold.

Fires on each Agent tool call (PreToolUse where tool matches "Agent").
Counts spawns this session, estimates cumulative token cost, and warns
when total estimated agent cost exceeds a configurable threshold.

Does NOT block — only warns. The orchestrator decides whether to proceed.

Wire as PreToolUse hook in settings.local.json:
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Agent",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /Users/matthewshields/Projects/ClaudeCodeAdvancements/hooks/spawn_budget_hook.py"
          }
        ]
      }
    ]
  }
}

Environment variables:
  CCA_SPAWN_BUDGET_DISABLED    - Set to "1" to disable
  CCA_SPAWN_BUDGET_THRESHOLD   - Token warning threshold (default: 200000)
  CCA_SPAWN_BUDGET_PER_AGENT   - Estimated tokens per agent spawn (default: 40000)
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

BUDGET_FILE = Path.home() / ".claude-spawn-budget.json"
DEFAULT_THRESHOLD = 200_000  # tokens
DEFAULT_PER_AGENT = 40_000   # estimated tokens per agent spawn


def load_budget() -> dict:
    """Load current session's spawn budget tracking."""
    if BUDGET_FILE.exists():
        try:
            data = json.loads(BUDGET_FILE.read_text())
            # Check if this is from today's session
            if data.get("date") == datetime.now().strftime("%Y-%m-%d"):
                return data
        except (json.JSONDecodeError, KeyError):
            pass
    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "spawns": [],
        "total_count": 0,
        "total_estimated_tokens": 0,
    }


def save_budget(budget: dict) -> None:
    """Save spawn budget state atomically."""
    tmp = BUDGET_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(budget, indent=2))
    tmp.rename(BUDGET_FILE)


def main() -> None:
    if os.environ.get("CCA_SPAWN_BUDGET_DISABLED") == "1":
        return

    # Read hook input from stdin
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return

    tool_name = hook_input.get("tool_name", "")

    # Only track Agent tool calls
    if tool_name.lower() != "agent":
        return

    # Extract agent details from tool input
    tool_input = hook_input.get("tool_input", {})
    agent_type = tool_input.get("subagent_type", "general-purpose")
    description = tool_input.get("description", "unknown task")
    model = tool_input.get("model", "inherited")

    # Load config from env
    threshold = int(os.environ.get("CCA_SPAWN_BUDGET_THRESHOLD", str(DEFAULT_THRESHOLD)))
    per_agent = int(os.environ.get("CCA_SPAWN_BUDGET_PER_AGENT", str(DEFAULT_PER_AGENT)))

    # Model-specific cost estimates (rough)
    model_multipliers = {
        "haiku": 0.3,     # ~12K tokens typical
        "sonnet": 1.0,    # ~40K tokens typical
        "opus": 2.5,      # ~100K tokens typical
    }
    multiplier = model_multipliers.get(model, 1.0)
    estimated_tokens = int(per_agent * multiplier)

    # Update budget
    budget = load_budget()
    budget["spawns"].append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "type": agent_type,
        "description": description,
        "model": model,
        "estimated_tokens": estimated_tokens,
    })
    budget["total_count"] += 1
    budget["total_estimated_tokens"] += estimated_tokens
    save_budget(budget)

    # Check threshold
    total = budget["total_estimated_tokens"]
    count = budget["total_count"]

    if total >= threshold:
        # Over budget — warn
        output = {
            "suppressOutput": False,
            "message": (
                f"SPAWN BUDGET WARNING: {count} agents spawned today, "
                f"~{total:,} estimated tokens (threshold: {threshold:,}). "
                f"Latest: {agent_type} ({description}). Consider batching or deferring."
            ),
        }
        print(json.dumps(output))
    elif total >= threshold * 0.75:
        # Approaching budget — soft warn
        pct = int(total / threshold * 100)
        output = {
            "suppressOutput": False,
            "message": (
                f"Spawn budget: {pct}% ({count} agents, ~{total:,} tokens). "
                f"Approaching {threshold:,} threshold."
            ),
        }
        print(json.dumps(output))
    # Under 75%: silent — no output


if __name__ == "__main__":
    main()
