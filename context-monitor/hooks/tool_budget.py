"""
CTX-6: Tool-Call Budget Hook — PreToolUse

Tracks cumulative tool calls per session and warns/blocks when thresholds
are exceeded. Protects against runaway sessions that burn tool budget
making slow progress (the "30 tool calls for a 1-file bug fix" antipattern).

Behaviour:
  - Cheap tools (Read, Glob, Grep, TodoRead, TodoWrite, short Bash) are exempt
    from counting and never blocked.
  - At WARN threshold: injects an additionalContext warning into the hook response.
  - At BLOCK threshold: denies the tool call with a permissionDecision: "deny".
  - Session tracking: a new session_id resets the counter automatically.

State file: ~/.claude-tool-budget.json
  {
    "session_id": "<session_id>",
    "call_count": <int>,
    "warnings_issued": <int>,
    "updated_at": "<ISO timestamp>"
  }

Environment variables (all optional):
  CCA_TOOL_BUDGET_WARN      - Warn threshold (default: 15)
  CCA_TOOL_BUDGET_BLOCK     - Block threshold (default: 30)
  CCA_TOOL_BUDGET_DISABLED  - Set "1" to disable entirely
  CCA_TOOL_BUDGET_STATE     - Override state file path

Wire as PreToolUse hook in .claude/settings.local.json:
  {
    "hooks": {
      "PreToolUse": [
        {
          "matcher": "",
          "hooks": [{"type": "command", "command": "python3 .../tool_budget.py"}]
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

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_WARN = 15
DEFAULT_BLOCK = 30
DEFAULT_STATE_FILE = Path.home() / ".claude-tool-budget.json"

# Short Bash threshold — commands shorter than this (chars) are considered cheap
BASH_SHORT_THRESHOLD = 100

# Tools that are always exempt from budget counting.
# These are cheap reads/searches that don't contribute to session complexity.
EXEMPT_TOOLS = frozenset({
    "Read", "Glob", "Grep",
    "TodoRead", "TodoWrite",
    "LS",
})


# ---------------------------------------------------------------------------
# Pure logic (easily testable)
# ---------------------------------------------------------------------------

def is_exempt(tool_name: str, tool_input: dict) -> bool:
    """Return True if this tool call should be exempt from budget counting.

    Exemptions:
    - Any tool in EXEMPT_TOOLS
    - Bash calls with short commands (< BASH_SHORT_THRESHOLD chars)
    """
    if tool_name in EXEMPT_TOOLS:
        return True
    if tool_name == "Bash":
        command = tool_input.get("command", "")
        if len(command) < BASH_SHORT_THRESHOLD:
            return True
    return False


def load_state(path: Path) -> dict:
    """Load the budget state from disk. Returns a zeroed-out dict on any error."""
    if not path.exists():
        return {"session_id": "", "call_count": 0, "warnings_issued": 0}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {
            "session_id": str(data.get("session_id", "")),
            "call_count": int(data.get("call_count", 0)),
            "warnings_issued": int(data.get("warnings_issued", 0)),
        }
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return {"session_id": "", "call_count": 0, "warnings_issued": 0}


def save_state(path: Path, state: dict) -> None:
    """Atomically write state to disk. Silently swallows write errors."""
    record = {
        "session_id": state.get("session_id", ""),
        "call_count": state.get("call_count", 0),
        "warnings_issued": state.get("warnings_issued", 0),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    tmp = path.with_suffix(".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2)
        tmp.replace(path)
    except OSError:
        try:
            tmp.unlink()
        except OSError:
            pass


def check_budget(
    session_id: str,
    tool_name: str,
    tool_input: dict,
    state: dict,
    warn_threshold: int = DEFAULT_WARN,
    block_threshold: int = DEFAULT_BLOCK,
) -> tuple[str, dict]:
    """Core budget logic. Returns (action, updated_state).

    action is one of: "allow", "warn", "block".
    updated_state contains the new session state to persist.

    If session_id changed, counters reset before the new call is counted.
    Exempt tools always return ("allow", unchanged_state).
    """
    # Reset on new session
    if session_id and state.get("session_id") != session_id:
        state = {"session_id": session_id, "call_count": 0, "warnings_issued": 0}

    if is_exempt(tool_name, tool_input):
        # Update session_id but don't count
        if session_id:
            state = dict(state)
            state["session_id"] = session_id
        return "allow", state

    # Count this call
    new_count = state.get("call_count", 0) + 1
    new_state = {
        "session_id": session_id or state.get("session_id", ""),
        "call_count": new_count,
        "warnings_issued": state.get("warnings_issued", 0),
    }

    if new_count >= block_threshold:
        new_state["warnings_issued"] = new_state.get("warnings_issued", 0) + 1
        return "block", new_state

    if new_count >= warn_threshold:
        new_state["warnings_issued"] = new_state.get("warnings_issued", 0) + 1
        return "warn", new_state

    return "allow", new_state


def build_warn_output(call_count: int, block_threshold: int) -> dict:
    """Build the hookSpecificOutput dict for a warning response."""
    return {
        "hookSpecificOutput": {
            "additionalContext": (
                f"Tool-call budget: {call_count}/{block_threshold} calls this session. "
                f"If you're approaching {block_threshold}, reassess your approach — "
                f"a simple task should not need this many tool calls. "
                f"Consider: have you already read all needed files? Are you going in circles?"
            )
        }
    }


def build_block_output(call_count: int, block_threshold: int) -> dict:
    """Build the hookSpecificOutput dict for a block response."""
    return {
        "hookSpecificOutput": {
            "permissionDecision": "deny",
            "reason": (
                f"Tool-call budget exceeded: {call_count}/{block_threshold} calls this session. "
                f"STOP — do not make more tool calls. Diagnose why so many calls were needed, "
                f"then report to the user. Reset via: rm ~/.claude-tool-budget.json"
            ),
        }
    }


# ---------------------------------------------------------------------------
# Hook entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """PreToolUse hook entry point."""
    if os.environ.get("CCA_TOOL_BUDGET_DISABLED") == "1":
        sys.exit(0)

    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        payload = {}

    session_id = str(payload.get("session_id", ""))
    tool_name = str(payload.get("tool_name", ""))
    tool_input = payload.get("tool_input", {})
    if not isinstance(tool_input, dict):
        tool_input = {}

    # Read config
    state_path_str = os.environ.get("CCA_TOOL_BUDGET_STATE", "")
    state_path = Path(state_path_str) if state_path_str else DEFAULT_STATE_FILE

    try:
        warn_threshold = int(os.environ.get("CCA_TOOL_BUDGET_WARN", str(DEFAULT_WARN)))
    except (ValueError, TypeError):
        warn_threshold = DEFAULT_WARN

    try:
        block_threshold = int(os.environ.get("CCA_TOOL_BUDGET_BLOCK", str(DEFAULT_BLOCK)))
    except (ValueError, TypeError):
        block_threshold = DEFAULT_BLOCK

    # Load state, compute action
    state = load_state(state_path)
    action, new_state = check_budget(
        session_id=session_id,
        tool_name=tool_name,
        tool_input=tool_input,
        state=state,
        warn_threshold=warn_threshold,
        block_threshold=block_threshold,
    )

    # Persist updated state
    save_state(state_path, new_state)

    if action == "block":
        json.dump(build_block_output(new_state["call_count"], block_threshold), sys.stdout)
        sys.exit(0)

    if action == "warn":
        json.dump(build_warn_output(new_state["call_count"], block_threshold), sys.stdout)
        sys.exit(0)

    # allow — output nothing
    sys.exit(0)


if __name__ == "__main__":
    main()
