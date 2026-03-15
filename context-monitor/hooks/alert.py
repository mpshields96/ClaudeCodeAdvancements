"""
CTX-3: Context Alert Hook — PreToolUse

Reads the context health state file (written by CTX-1 meter.py) and warns
before expensive tool calls when context is in red or critical zone.

Default behavior: warn-only. Never blocks. The user can opt into blocking
mode by setting CLAUDE_CONTEXT_ALERT_BLOCK=1.

Expensive tools that trigger alerts in red/critical:
  Agent, WebSearch, WebFetch, Bash (long commands), Write, Edit

Fast/cheap tools that are always allowed silently:
  Read, Glob, Grep, TodoWrite — these are fine at any context level.

Environment variables (all optional):
  CLAUDE_CONTEXT_STATE_FILE    - State file path (default: ~/.claude-context-health.json)
  CLAUDE_CONTEXT_ALERT_BLOCK   - Set "1" to block (not just warn) at critical zone
  CLAUDE_CONTEXT_ALERT_DISABLED - Set "1" to disable this hook entirely

Wire as PreToolUse hook in ~/.claude/settings.json or .claude/settings.local.json:
  {
    "hooks": {
      "PreToolUse": [
        {
          "matcher": "",
          "hooks": [{ "type": "command", "command": "python3 .../alert.py" }]
        }
      ]
    }
  }
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_STATE_FILE = Path.home() / ".claude-context-health.json"

# Tools that are cheap/fast — never alert for these regardless of zone
QUIET_TOOLS = frozenset({
    "Read", "Glob", "Grep", "TodoWrite", "TodoRead",
    "LS", "Cat",  # common aliases
})

# Message templates per zone
WARN_TEMPLATES = {
    "red": (
        "Context is {pct:.0f}% full (red zone). "
        "Consider /compact before starting this operation. "
        "Continuing."
    ),
    "critical": (
        "Context is {pct:.0f}% full (CRITICAL). "
        "Strong recommendation: run /compact or /handoff before this call. "
        "{block_msg}"
    ),
}


def load_state(state_path: Path) -> dict:
    """Load context health state from file. Returns empty dict on any failure."""
    if not state_path.exists():
        return {}
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def should_alert(zone: str, tool_name: str) -> bool:
    """
    Return True if we should surface an alert for this tool at this zone.
    Only alert at red or critical. Never alert for cheap/fast tools.
    """
    if zone not in ("red", "critical"):
        return False
    if tool_name in QUIET_TOOLS:
        return False
    return True


def build_message(zone: str, pct: float, tool_name: str, blocking: bool) -> str:
    """Format the alert message."""
    template = WARN_TEMPLATES.get(zone, "")
    if not template:
        return ""
    block_msg = "Blocking this call." if blocking else "Continuing."
    return template.format(pct=pct, tool_name=tool_name, block_msg=block_msg)


def _allow_response() -> dict:
    return {}


def _warn_response(message: str) -> dict:
    """Warn but allow — PostToolUse format, non-blocking."""
    return {
        "hookSpecificOutput": {
            "permissionDecision": "allow",
        },
        "suppressOutput": False,
        "reason": message,
    }


def _block_response(message: str) -> dict:
    """Block the tool call. Only used when CLAUDE_CONTEXT_ALERT_BLOCK=1."""
    return {
        "hookSpecificOutput": {
            "permissionDecision": "deny",
            "denyReason": message,
        },
    }


def main() -> None:
    if os.environ.get("CLAUDE_CONTEXT_ALERT_DISABLED") == "1":
        print(json.dumps(_allow_response()))
        sys.exit(0)

    blocking = os.environ.get("CLAUDE_CONTEXT_ALERT_BLOCK") == "1"

    state_file_str = os.environ.get("CLAUDE_CONTEXT_STATE_FILE", "")
    state_path = Path(state_file_str) if state_file_str else DEFAULT_STATE_FILE

    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        payload = {}

    tool_name = payload.get("tool_name", "")

    # Cheap tools: pass through immediately without reading the state file
    if tool_name in QUIET_TOOLS:
        print(json.dumps(_allow_response()))
        sys.exit(0)

    state = load_state(state_path)
    zone = state.get("zone", "unknown")
    pct = float(state.get("pct", 0))

    if not should_alert(zone, tool_name):
        print(json.dumps(_allow_response()))
        sys.exit(0)

    message = build_message(zone, pct, tool_name, blocking)

    if blocking and zone == "critical":
        print(json.dumps(_block_response(message)))
    else:
        print(json.dumps(_warn_response(message)))

    sys.exit(0)


if __name__ == "__main__":
    main()
