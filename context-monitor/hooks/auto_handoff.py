"""
CTX-4: Auto-Handoff Stop Hook

Runs at session end (Stop hook). If context is in the critical zone and no
recent HANDOFF.md exists, blocks exit and prompts Claude to run /handoff before
the session closes — preventing context loss when the window is nearly full.

Behavior:
  critical zone + no recent handoff → block exit, ask Claude to run /handoff
  red zone                          → warn-only (non-blocking) by default
  green / yellow / unknown          → silent pass-through

Anti-loop protection: if HANDOFF.md was written within the last 5 minutes,
always allow exit (handoff already done this session).

Environment variables (all optional):
  CLAUDE_CONTEXT_STATE_FILE       - State file path (default: ~/.claude-context-health.json)
  CLAUDE_CONTEXT_HANDOFF_PATH     - HANDOFF.md path (default: ./HANDOFF.md)
  CLAUDE_CONTEXT_HANDOFF_AGE      - Max HANDOFF.md age in minutes before it's "stale" (default: 5)
  CLAUDE_CONTEXT_HANDOFF_RED      - Set "1" to also block on red zone (default: critical only)
  CLAUDE_CONTEXT_HANDOFF_DISABLED - Set "1" to disable this hook entirely

Wire as Stop hook in .claude/settings.local.json:
  {
    "hooks": {
      "Stop": [
        {
          "matcher": "",
          "hooks": [{ "type": "command", "command": "python3 .../auto_handoff.py" }]
        }
      ]
    }
  }
"""
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_STATE_FILE = Path.home() / ".claude-context-health.json"
DEFAULT_HANDOFF_PATH = Path("HANDOFF.md")
DEFAULT_HANDOFF_AGE_MINUTES = 5
# Breadcrumb file written on first block — prevents infinite re-prompting
PROMPTED_BREADCRUMB = Path.home() / ".claude-handoff-prompted"
BREADCRUMB_MAX_AGE_MINUTES = 10


# ---------------------------------------------------------------------------
# Pure functions (all testable without filesystem side-effects)
# ---------------------------------------------------------------------------

def load_state(state_path: Path) -> dict:
    """Load context health state. Returns empty dict on any failure."""
    if not state_path.exists():
        return {}
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def handoff_is_fresh(handoff_path: Path, max_age_minutes: float) -> bool:
    """
    Return True if HANDOFF.md exists and was written within max_age_minutes.
    This prevents the hook from blocking exit again immediately after /handoff runs.
    """
    if not handoff_path.exists():
        return False
    age_seconds = time.time() - handoff_path.stat().st_mtime
    return (age_seconds / 60) <= max_age_minutes


def already_prompted(breadcrumb_path: Path, max_age_minutes: float) -> bool:
    """
    Return True if the Stop hook already prompted Claude this session.
    Prevents infinite block -> respond -> block loops when Claude responds
    to the handoff prompt but doesn't write HANDOFF.md (e.g., after /cca-wrap).
    """
    if not breadcrumb_path.exists():
        return False
    age_seconds = time.time() - breadcrumb_path.stat().st_mtime
    return (age_seconds / 60) <= max_age_minutes


def write_breadcrumb(breadcrumb_path: Path) -> None:
    """Write breadcrumb file to mark that we've prompted once."""
    try:
        breadcrumb_path.write_text(
            f"prompted_at={datetime.now(timezone.utc).isoformat()}\n"
        )
    except OSError:
        pass  # Best-effort — don't break the hook if write fails


def should_block(zone: str, handoff_fresh: bool, block_on_red: bool = False,
                 was_prompted: bool = False) -> bool:
    """
    Return True if we should block exit and prompt for /handoff.

    Rules:
    - Always allow if handoff was just written (anti-loop)
    - Always allow if we already prompted this session (anti-loop)
    - Block on critical zone
    - Block on red zone only if block_on_red is set
    - Allow on green / yellow / unknown
    """
    if handoff_fresh:
        return False
    if was_prompted:
        return False
    if zone == "critical":
        return True
    if zone == "red" and block_on_red:
        return True
    return False


def should_warn(zone: str, handoff_fresh: bool) -> bool:
    """
    Return True if we should emit a non-blocking warning.
    Used for red zone when block_on_red is not set.
    """
    if handoff_fresh:
        return False
    return zone == "red"


def build_block_message(zone: str, pct: float) -> str:
    return (
        f"Context window is {pct:.0f}% full ({zone} zone). "
        f"Run /handoff to save session state before exiting, "
        f"so the next session can resume without re-reading the transcript."
    )


def build_warn_message(zone: str, pct: float) -> str:
    return (
        f"[CTX-4] Context is {pct:.0f}% full (red zone). "
        f"Consider running /handoff before ending the session."
    )


def _allow_response() -> dict:
    return {}


def _block_response(message: str) -> dict:
    """Block exit — Claude Code reinvokes Claude with message as input."""
    return {"decision": "block", "reason": message}


# ---------------------------------------------------------------------------
# Hook entry point
# ---------------------------------------------------------------------------

def main() -> None:
    if os.environ.get("CLAUDE_CONTEXT_HANDOFF_DISABLED") == "1":
        print(json.dumps(_allow_response()))
        sys.exit(0)

    # Config
    state_file_str = os.environ.get("CLAUDE_CONTEXT_STATE_FILE", "")
    state_path = Path(state_file_str) if state_file_str else DEFAULT_STATE_FILE

    handoff_str = os.environ.get("CLAUDE_CONTEXT_HANDOFF_PATH", "")
    handoff_path = Path(handoff_str) if handoff_str else DEFAULT_HANDOFF_PATH

    max_age = float(os.environ.get("CLAUDE_CONTEXT_HANDOFF_AGE", str(DEFAULT_HANDOFF_AGE_MINUTES)))
    block_on_red = os.environ.get("CLAUDE_CONTEXT_HANDOFF_RED") == "1"

    # Read state
    state = load_state(state_path)
    zone = state.get("zone", "unknown")
    pct = float(state.get("pct", 0))

    # Check anti-loop protection (two mechanisms)
    fresh = handoff_is_fresh(handoff_path, max_age)
    was_prompted = already_prompted(PROMPTED_BREADCRUMB, BREADCRUMB_MAX_AGE_MINUTES)

    if should_block(zone, fresh, block_on_red, was_prompted):
        # Write breadcrumb BEFORE blocking — next fire will see it and allow exit
        write_breadcrumb(PROMPTED_BREADCRUMB)
        msg = build_block_message(zone, pct)
        print(json.dumps(_block_response(msg)))
        sys.exit(0)

    if should_warn(zone, fresh):
        # Warn but don't block — print to stderr so it shows in logs
        print(build_warn_message(zone, pct), file=sys.stderr)

    print(json.dumps(_allow_response()))
    sys.exit(0)


if __name__ == "__main__":
    main()
