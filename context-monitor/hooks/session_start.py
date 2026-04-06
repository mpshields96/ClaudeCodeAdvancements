#!/usr/bin/env python3
"""
session_start.py — SessionStart hook: clear stale context health state.

Runs once when Claude Code opens a new session. Writes pct=0/zone=green
to ~/.claude-context-health.json so the session pacer doesn't inherit
red/critical context percentages from the previous session.

Never blocks: always exits 0.
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_STATE_FILE = Path.home() / ".claude-context-health.json"


def main() -> None:
    state_path_str = os.environ.get("CLAUDE_CONTEXT_STATE_FILE", "")
    state_path = Path(state_path_str) if state_path_str else DEFAULT_STATE_FILE

    fresh = {
        "pct": 0.0,
        "zone": "green",
        "tokens": 0,
        "turns": 0,
        "window": int(os.environ.get("CLAUDE_CONTEXT_WINDOW", "200000")),
        "session_id": "session_start",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(fresh, indent=2))
        tmp.replace(state_path)
    except OSError:
        pass  # Non-fatal — staleness check in session_pacer is the backstop

    sys.exit(0)


if __name__ == "__main__":
    main()
