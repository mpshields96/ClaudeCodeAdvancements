"""
Stop Hook — Idle Writer

Fires on every Stop event (Claude finishes a turn). Records the current UTC
timestamp as `idle_since` in the context health state file. The UserPromptSubmit
cache guard reads this to determine how long the session has been idle and warn
when the Anthropic prompt cache is likely cold.

Cache TTLs (Anthropic):
  Pro plan:  300s  (5 minutes)
  Max plan: 3600s  (60 minutes)

Wire in settings.local.json:
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /path/to/hooks/stop_hook_idle_writer.py"
          }
        ]
      }
    ]
  }
}

Environment variables:
  CCA_IDLE_WRITER_DISABLED  - Set to "1" to disable
  CLAUDE_CONTEXT_STATE_FILE - Override state file path (default: ~/.claude-context-health.json)
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

STATE_FILE = Path(os.environ.get(
    "CLAUDE_CONTEXT_STATE_FILE",
    Path.home() / ".claude-context-health.json",
))


def main() -> None:
    if os.environ.get("CCA_IDLE_WRITER_DISABLED") == "1":
        return

    # Read current state (create minimal state if missing)
    state: dict = {}
    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            state = {}

    # Stamp idle_since as now
    state["idle_since"] = datetime.now(timezone.utc).isoformat()

    # Atomic write
    try:
        tmp = tempfile.NamedTemporaryFile(
            mode="w",
            dir=STATE_FILE.parent,
            prefix=".tmp_health_",
            suffix=".json",
            delete=False,
        )
        json.dump(state, tmp, indent=2)
        tmp.close()
        os.replace(tmp.name, STATE_FILE)
    except OSError:
        pass  # Non-blocking — never fail a session over this


if __name__ == "__main__":
    main()
