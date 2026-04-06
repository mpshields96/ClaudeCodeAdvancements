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

Autocompact awareness:
  When the meter (CTX-1) detects CLAUDE_AUTOCOMPACT_PCT_OVERRIDE, the state file
  includes autocompact_proximity (percentage points until compaction fires).
  This hook warns when proximity is low (<10 points), even in yellow zone,
  so the user can /compact proactively rather than losing context to auto-compact.

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
from __future__ import annotations
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

DEFAULT_AUTOCOMPACT_PROXIMITY_THRESHOLD = 10  # warn when < 10 pct points from compaction

# Message templates per zone
WARN_TEMPLATES = {
    "yellow": (
        "Context is {pct:.0f}% full. "
        "Auto-compact fires in ~{autocompact_proximity:.0f} percentage points. "
        "Consider /compact now to avoid losing CLAUDE.md rules. "
        "Continuing."
    ),
    "red": (
        "Context is {pct:.0f}% full (red zone). "
        "Consider /compact before starting this operation.{autocompact_suffix} "
        "Continuing."
    ),
    "critical": (
        "Context is {pct:.0f}% full (CRITICAL). "
        "Strong recommendation: run /compact or /handoff before this call.{autocompact_suffix} "
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


def should_warn_autocompact(
    proximity: float | None,
    threshold: int = DEFAULT_AUTOCOMPACT_PROXIMITY_THRESHOLD,
) -> bool:
    """
    Return True if autocompact is configured and proximity is below threshold.

    proximity: percentage points remaining before auto-compact fires (None = not configured).
    threshold: warn when proximity < this many percentage points (default: 10).
    """
    if proximity is None:
        return False
    return proximity < threshold


def should_alert(
    zone: str,
    tool_name: str,
    autocompact_proximity: float | None = None,
) -> bool:
    """
    Return True if we should surface an alert for this tool at this zone.

    Alerts at red or critical for expensive tools. Also alerts in yellow zone
    when autocompact proximity is low (approaching auto-compaction threshold).
    Never alerts for cheap/fast tools.
    """
    if tool_name in QUIET_TOOLS:
        return False
    if zone in ("red", "critical"):
        return True
    if zone == "yellow" and should_warn_autocompact(autocompact_proximity):
        return True
    return False


def build_message(
    zone: str,
    pct: float,
    tool_name: str,
    blocking: bool,
    autocompact_proximity: float | None = None,
) -> str:
    """Format the alert message. Includes autocompact proximity when available."""
    template = WARN_TEMPLATES.get(zone, "")
    if not template:
        return ""

    block_msg = "Blocking this call." if blocking else "Continuing."

    # Yellow zone template needs autocompact_proximity directly
    if zone == "yellow":
        if autocompact_proximity is None:
            return ""
        return template.format(
            pct=pct, tool_name=tool_name,
            autocompact_proximity=autocompact_proximity,
        )

    # Red/critical: add autocompact suffix if proximity info available
    if autocompact_proximity is not None:
        autocompact_suffix = (
            f" Auto-compact in ~{autocompact_proximity:.0f} points."
        )
    else:
        autocompact_suffix = ""

    return template.format(
        pct=pct, tool_name=tool_name, block_msg=block_msg,
        autocompact_suffix=autocompact_suffix,
    )


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
    autocompact_proximity = state.get("autocompact_proximity")

    if not should_alert(zone, tool_name, autocompact_proximity=autocompact_proximity):
        print(json.dumps(_allow_response()))
        sys.exit(0)

    message = build_message(zone, pct, tool_name, blocking,
                            autocompact_proximity=autocompact_proximity)

    if blocking and zone == "critical":
        print(json.dumps(_block_response(message)))
    else:
        print(json.dumps(_warn_response(message)))

    sys.exit(0)


if __name__ == "__main__":
    main()
